"""
Admin order detail endpoints.
"""
import os
import logging
import json
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from app.config import SESSION_SECRET
from app.mail import stuur_mail
from app.admin_routes import verify_admin_session, get_database_url
from app.mollie_client import create_payment, cancel_payment
import random

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/order", tags=["admin"])


def load_template(template_name: str) -> Optional[str]:
    """Laad een mail template uit templates.json"""
    try:
        project_root = Path(__file__).parent.parent
        templates_file = project_root / "docs" / "templates.json"
        
        if not templates_file.exists():
            return None
        
        with open(templates_file, 'r', encoding='utf-8') as f:
            templates = json.load(f)
        
        if template_name in templates:
            return templates[template_name].get("original")
        
        return None
    except Exception as e:
        _LOG.error(f"Fout bij laden template {template_name}: {e}")
        return None


def calculate_order_totals(order_id: str, conn) -> dict:
    """Herbereken totaalprijs van order op basis van order_artikelen"""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT 
            COALESCE(SUM(prijs_incl), 0) as totaal_incl,
            COALESCE(SUM(prijs_excl), 0) as totaal_excl,
            COALESCE(SUM(btw_bedrag), 0) as totaal_btw
        FROM order_artikelen
        WHERE order_id = %s
    """, (order_id,))
    
    result = cur.fetchone()
    cur.close()
    
    return {
        "totaal_bedrag": float(result["totaal_incl"]) if result["totaal_incl"] else 0.00,
        "bedrag_excl_btw": float(result["totaal_excl"]) if result["totaal_excl"] else 0.00,
        "bedrag_btw": float(result["totaal_btw"]) if result["totaal_btw"] else 0.00
    }


def update_factuur_bij_orderwijziging(order_id: str, nieuwe_totaal: float, conn, background_tasks: BackgroundTasks):
    """
    Update factuur bij orderwijziging: annuleer oude Mollie payment, maak nieuwe aan, stuur mail.
    Alleen als betaal_status = 'factuur_verstuurd' (niet als al betaald).
    """
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check betaal_status
    cur.execute("SELECT betaal_status FROM orders WHERE id = %s", (order_id,))
    order = cur.fetchone()
    
    if not order or order.get("betaal_status") != "factuur_verstuurd":
        # Niet factuur_verstuurd of al betaald, geen update nodig
        return
    
    # Haal bestaande factuur op
    cur.execute("""
        SELECT id, mollie_payment_id, factuurnummer, klant_id
        FROM facturen
        WHERE order_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (order_id,))
    
    factuur = cur.fetchone()
    if not factuur:
        return
    
    mollie_payment_id = factuur.get("mollie_payment_id")
    factuurnummer = factuur.get("factuurnummer", "")
    factuur_id = factuur.get("id")
    
    if not mollie_payment_id:
        return
    
    # Annuleer oude Mollie payment
    oude_payment_id = mollie_payment_id
    try:
        cancel_success = cancel_payment(mollie_payment_id)
        if cancel_success:
            _LOG.info(f"Oude Mollie payment {mollie_payment_id} geannuleerd voor order {order_id}")
            # Wacht 1 seconde zodat Mollie tijd heeft om te verwerken
            import time
            time.sleep(1)
        else:
            _LOG.warning(f"Oude Mollie payment {mollie_payment_id} kon niet geannuleerd worden (waarschijnlijk al betaald/expired)")
    except Exception as e:
        _LOG.warning(f"Kon oude Mollie payment niet annuleren: {e}")
        # Ga door met nieuwe payment aanmaken
    
    # Haal order en klant info op voor nieuwe payment
    cur.execute("""
        SELECT o.ordernummer, o.bedrag_excl_btw, o.bedrag_btw, o.ordertype,
               c.email as klant_email, c.naam as klant_naam
        FROM orders o
        LEFT JOIN contacten c ON o.klant_id = c.id
        WHERE o.id = %s
    """, (order_id,))
    
    order_info = cur.fetchone()
    if not order_info:
        return
    
    ordernummer = order_info.get("ordernummer", "")
    ordertype = order_info.get("ordertype") or "b2c"
    klant_email = order_info.get("klant_email")
    
    if not klant_email:
        _LOG.warning(f"Geen email voor klant bij factuur update order {order_id}")
        return
    
    # Maak nieuwe Mollie payment
    try:
        payment = create_payment(
            amount=nieuwe_totaal,
            description=f"Factuur {factuurnummer}",
            redirect_url="https://fth-portaal-production.up.railway.app/betaling/bedankt",
            webhook_url="https://fth-portaal-production.up.railway.app/webhooks/mollie",
            metadata={"order_id": str(order_id)}
        )
        
        nieuwe_mollie_payment_id = payment["id"]
        nieuwe_mollie_checkout_url = payment["checkout_url"]
        
        # Update factuur record
        cur.execute("""
            UPDATE facturen
            SET mollie_payment_id = %s,
                mollie_checkout_url = %s,
                totaal_bedrag = %s,
                bedrag_excl_btw = %s,
                bedrag_btw = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            nieuwe_mollie_payment_id,
            nieuwe_mollie_checkout_url,
            nieuwe_totaal,
            float(order_info.get("bedrag_excl_btw", 0)),
            float(order_info.get("bedrag_btw", 0)),
            factuur_id
        ))
        
        conn.commit()
        
        # Stuur nieuwe factuurmail
        if ordertype == "b2b":
            mail_body = f"""
            <html>
            <body>
                <h2>Factuur {factuurnummer} (gewijzigd)</h2>
                <p>Beste {order_info.get('klant_naam', '')},</p>
                <p>De factuur voor uw bestelling {ordernummer} is gewijzigd.</p>
                <p><strong>Nieuw te betalen bedrag: € {nieuwe_totaal:,.2f}</strong></p>
                <p>U kunt betalen via de onderstaande betaallink:</p>
                <p><a href="{nieuwe_mollie_checkout_url}" style="background:#fec82a;color:#333;padding:12px 24px;text-decoration:none;border-radius:8px;display:inline-block;font-weight:bold;">Betaal nu</a></p>
                <p>Of maak het bedrag over naar:</p>
                <p><strong>Rekeningnummer:</strong> NL91ABNA0417164300<br>
                <strong>Ten name van:</strong> Treatlab VOF</p>
                <p>Met vriendelijke groet,<br>FTH Portaal</p>
            </body>
            </html>
            """
        else:
            mail_body = f"""
            <html>
            <body>
                <h2>Factuur {factuurnummer} (gewijzigd)</h2>
                <p>Beste {order_info.get('klant_naam', '')},</p>
                <p>De factuur voor uw bestelling {ordernummer} is gewijzigd.</p>
                <p><strong>Nieuw te betalen bedrag: € {nieuwe_totaal:,.2f}</strong></p>
                <p>U kunt betalen via de onderstaande betaallink:</p>
                <p><a href="{nieuwe_mollie_checkout_url}" style="background:#fec82a;color:#333;padding:12px 24px;text-decoration:none;border-radius:8px;display:inline-block;font-weight:bold;">Betaal nu</a></p>
                <p>Met vriendelijke groet,<br>FTH Portaal</p>
            </body>
            </html>
            """
        
        # Verstuur mail in background
        background_tasks.add_task(
            stuur_mail,
            naar=klant_email,
            onderwerp=f"Factuur {factuurnummer} gewijzigd - {ordernummer}",
            inhoud=mail_body,
            order_id=order_id,
            template_naam="Factuur gewijzigd"
        )
        
        # Log in mail_logs
        cur.execute("""
            INSERT INTO mail_logs (order_id, onderwerp, status, foutmelding)
            VALUES (%s, %s, %s, %s)
        """, (
            order_id,
            f"Factuur bijgewerkt na orderwijziging - Nieuwe payment {nieuwe_mollie_payment_id}",
            "success",
            None
        ))
        conn.commit()
        
        # Log duidelijk
        _LOG.info(f"Oude payment {oude_payment_id} geannuleerd, nieuwe payment {nieuwe_mollie_payment_id} aangemaakt voor order {order_id}")
        
    except Exception as e:
        _LOG.error(f"Fout bij updaten factuur voor order {order_id}: {e}", exc_info=True)
        conn.rollback()


@router.get("/{order_id}", response_class=HTMLResponse)
async def order_detail(request: Request, order_id: str, verified: bool = Depends(verify_admin_session)):
    """Detail pagina voor een aanvraag"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal order op met contact informatie en partner
        cur.execute("""
            SELECT 
                o.*,
                c.naam as klant_naam,
                c.email as klant_email,
                c.telefoon as klant_telefoon,
                p.naam as partner_naam
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            LEFT JOIN contacten p ON o.contractor_id = p.id
            WHERE o.id = %s
        """, (order_id,))
        
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order niet gevonden")
        
        # Haal order_artikelen op
        cur.execute("""
            SELECT 
                oa.*,
                a.naam as artikel_naam
            FROM order_artikelen oa
            LEFT JOIN artikelen a ON oa.artikel_id = a.id
            WHERE oa.order_id = %s
            ORDER BY oa.created_at
        """, (order_id,))
        
        artikelen = cur.fetchall()
        
        # Haal beschikbare artikelen op voor dropdown
        cur.execute("""
            SELECT id, naam, prijs_incl, prijs_excl, btw_pct
            FROM artikelen
            WHERE actief = TRUE
            ORDER BY naam
        """)
        
        beschikbare_artikelen = cur.fetchall()
        
        # Format datums voor display
        def format_datetime(dt):
            if not dt:
                return "-"
            if isinstance(dt, str):
                return dt[:16]
            return dt.strftime("%Y-%m-%d %H:%M")
        
        # Format datetime voor datetime-local input (YYYY-MM-DDTHH:MM)
        def format_datetime_local(dt):
            if not dt:
                return ""
            if isinstance(dt, str):
                # Als het al een string is, probeer te converteren
                try:
                    dt = datetime.strptime(dt[:16], "%Y-%m-%d %H:%M")
                except:
                    return dt[:16].replace(" ", "T")
            return dt.strftime("%Y-%m-%dT%H:%M")
        
        leverdatum_display = format_datetime(order.get("leverdatum"))
        leverdatum_input = format_datetime_local(order.get("leverdatum"))
        order_datum = format_datetime(order.get("order_datum"))
        
        # Status info
        portaal_status = order.get("portaal_status", "nieuw")
        order_status = order.get("status", "draft")
        
        # Build artikelen tabel
        artikelen_rows = ""
        totaal_prijs = 0.00
        for artikel in artikelen:
            artikel_id = str(artikel.get("id"))
            naam = artikel.get("naam") or artikel.get("artikel_naam") or "-"
            aantal = float(artikel.get("aantal", 0))
            prijs_incl = float(artikel.get("prijs_incl", 0))
            totaal_regel = aantal * prijs_incl
            totaal_prijs += totaal_regel
            
            artikelen_rows += f"""
            <tr>
                <td>{naam}</td>
                <td>{aantal}</td>
                <td>€ {prijs_incl:,.2f}</td>
                <td>€ {totaal_regel:,.2f}</td>
                <td>
                    <form method="post" action="/admin/order/{order_id}/artikel-verwijderen/{artikel_id}?token={SESSION_SECRET}" style="display:inline;">
                        <button type="submit" style="background:#dc3545;color:white;border:none;padding:6px 12px;border-radius:4px;cursor:pointer;">Verwijder</button>
                    </form>
                </td>
            </tr>
            """
        
        # Build artikelen dropdown
        artikel_options = '<option value="">-- Selecteer artikel --</option>'
        for artikel in beschikbare_artikelen:
            artikel_uuid = str(artikel.get("id"))
            artikel_naam = artikel.get("naam", "")
            artikel_prijs = float(artikel.get("prijs_incl", 0))
            artikel_options += f'<option value="{artikel_uuid}">{artikel_naam} (€ {artikel_prijs:,.2f})</option>'
        
        # Status knoppen
        status_knoppen = ""
        if portaal_status == "nieuw":
            status_knoppen += f'<form method="post" action="/admin/order/{order_id}/status?token={SESSION_SECRET}" style="display:inline;margin-right:10px;"><input type="hidden" name="portaal_status" value="beschikbaar"><button type="submit" class="btn">Zet beschikbaar</button></form>'
        
        # Claim knop altijd zichtbaar
        status_knoppen += f'<form method="post" action="/admin/order/{order_id}/claim?token={SESSION_SECRET}" style="display:inline;"><button type="submit" class="btn">Claim voor Aardappeltuin</button></form>'
        
        # Offerte knoppen
        offerte_knoppen = ""
        if order_status in ["draft", "sent"]:
            if order_status == "draft":
                offerte_knoppen += f'<form method="post" action="/admin/order/{order_id}/verstuur-offerte?token={SESSION_SECRET}" style="display:inline;"><button type="submit" class="btn">Verstuur offerte</button></form>'
            else:
                offerte_knoppen += f'<form method="post" action="/admin/order/{order_id}/verstuur-offerte?token={SESSION_SECRET}" style="display:inline;"><button type="submit" class="btn">Verstuur gewijzigde offerte</button></form>'
        
        # Bevestigingsknop (alleen als status != 'sale')
        if order_status != "sale":
            offerte_knoppen += f'<form method="post" action="/admin/order/{order_id}/bevestig?token={SESSION_SECRET}" style="display:inline;margin-left:10px;"><button type="submit" class="btn">Bevestig order</button></form>'
        
        # Factuur knoppen
        factuur_knoppen = ""
        betaal_status = order.get("betaal_status")
        
        if order_status == "sale":
            # Check of er al een factuur is
            cur.execute("SELECT id FROM facturen WHERE order_id = %s LIMIT 1", (order_id,))
            heeft_factuur = cur.fetchone()
            
            if betaal_status == "betaald":
                # Al betaald, geen wijziging mogelijk
                factuur_knoppen = '<p style="color:#666;">Order al betaald - geen wijzigingen mogelijk</p>'
            elif betaal_status == "factuur_verstuurd" and heeft_factuur:
                # Factuur al verstuurd, toon "nogmaals versturen" knop
                factuur_knoppen += f'<form method="post" action="/admin/order/{order_id}/verstuur-factuur-nogmaals?token={SESSION_SECRET}" style="display:inline;"><button type="submit" class="btn">Verstuur factuur nogmaals</button></form>'
            elif not betaal_status or betaal_status == "onbetaald":
                # Nog geen factuur verstuurd, toon normale knop
                if not heeft_factuur:
                    factuur_knoppen += f'<form method="post" action="/admin/order/{order_id}/verstuur-factuur?token={SESSION_SECRET}" style="display:inline;"><button type="submit" class="btn">Verstuur factuur</button></form>'
                else:
                    # Factuur bestaat maar nog niet verstuurd, toon "verstuur factuur" knop
                    factuur_knoppen += f'<form method="post" action="/admin/order/{order_id}/verstuur-factuur?token={SESSION_SECRET}" style="display:inline;"><button type="submit" class="btn">Verstuur factuur</button></form>'
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="nl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>FTH Admin - Aanvraag {order.get('ordernummer', '')}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: #fffdf2;
                    padding: 20px;
                }}
                .header {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header h1 {{
                    color: #333333;
                    margin-bottom: 10px;
                }}
                .back-link {{
                    color: #666;
                    text-decoration: none;
                    margin-bottom: 20px;
                    display: inline-block;
                }}
                .section {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .section h2 {{
                    color: #333333;
                    margin-bottom: 15px;
                    font-size: 20px;
                }}
                .info-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 15px;
                }}
                .info-item {{
                    padding: 10px;
                    background: #f9f9f9;
                    border-radius: 8px;
                }}
                .info-label {{
                    font-size: 12px;
                    color: #666;
                    margin-bottom: 4px;
                }}
                .info-value {{
                    font-size: 16px;
                    color: #333;
                    font-weight: 500;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 15px;
                }}
                th {{
                    text-align: left;
                    padding: 12px;
                    background: #f5f5f5;
                    font-weight: 600;
                    color: #333;
                    border-bottom: 2px solid #e0e0e0;
                }}
                td {{
                    padding: 12px;
                    border-bottom: 1px solid #e0e0e0;
                }}
                .btn {{
                    padding: 10px 20px;
                    background: #fec82a;
                    color: #333333;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 700;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                }}
                .btn:hover {{
                    background: #e2af13;
                }}
                .add-artikel-form {{
                    display: flex;
                    gap: 10px;
                    margin-top: 15px;
                    align-items: flex-end;
                }}
                .add-artikel-form select {{
                    flex: 1;
                    padding: 10px;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                }}
                .add-artikel-form input[type="number"] {{
                    width: 100px;
                    padding: 10px;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                }}
                .save-btn {{
                    padding: 12px 24px;
                    border: none;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: 700;
                    cursor: pointer;
                    transition: all 0.3s;
                }}
                .save-btn:disabled {{
                    background: #e0e0e0;
                    color: #999;
                    cursor: not-allowed;
                }}
                .save-btn.orange {{
                    background: #ff6b35;
                    color: white;
                }}
                .save-btn.orange:hover {{
                    background: #e55a2b;
                }}
                .save-btn.green {{
                    background: #28a745;
                    color: white;
                }}
                .editable-field {{
                    width: 100%;
                    padding: 8px;
                    border: 2px solid #e0e0e0;
                    border-radius: 6px;
                    font-size: 16px;
                    font-family: inherit;
                    color: #333;
                    background: white;
                }}
                .editable-field:focus {{
                    outline: none;
                    border-color: #fec82a;
                }}
                .editable-field textarea {{
                    resize: vertical;
                    min-height: 60px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <a href="/admin?token={SESSION_SECRET}" class="back-link">← Terug naar dashboard</a>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <h1>Aanvraag: {order.get('ordernummer', 'N/A')}</h1>
                        {f'<p style="color:#666;margin-top:5px;font-size:14px;">GF Referentie: {order.get("gf_referentie", "-")}</p>' if order.get('gf_referentie') else ''}
                    </div>
                    <button id="save-btn" class="save-btn" disabled>Geen wijzigingen</button>
                </div>
            </div>
            
            <div class="section">
                <h2>Klantgegevens</h2>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Naam</div>
                        <div class="info-value">{order.get('klant_naam') or '-'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Email</div>
                        <div class="info-value">{order.get('klant_email') or '-'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Telefoon</div>
                        <div class="info-value">{order.get('klant_telefoon') or '-'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Plaats</div>
                        <input type="text" id="plaats" class="editable-field" value="{order.get('plaats') or ''}" placeholder="Plaats">
                    </div>
                    <div class="info-item">
                        <div class="info-label">Leverdatum</div>
                        <input type="datetime-local" id="leverdatum" class="editable-field" value="{leverdatum_input}" placeholder="Leverdatum">
                    </div>
                    <div class="info-item">
                        <div class="info-label">Aantal personen</div>
                        <input type="number" id="aantal_personen" class="editable-field" value="{order.get('aantal_personen', 0)}" min="0" placeholder="0">
                    </div>
                    <div class="info-item">
                        <div class="info-label">Aantal kinderen</div>
                        <input type="number" id="aantal_kinderen" class="editable-field" value="{order.get('aantal_kinderen', 0)}" min="0" placeholder="0">
                    </div>
                    <div class="info-item">
                        <div class="info-label">Ordertype</div>
                        <div class="info-value">{order.get('ordertype', '-')}</div>
                    </div>
                    <div class="info-item" style="grid-column: 1 / -1;">
                        <div class="info-label">Opmerkingen</div>
                        <textarea id="opmerkingen" class="editable-field" rows="3" placeholder="Opmerkingen">{order.get('opmerkingen') or ''}</textarea>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2>Artikelen</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Artikel</th>
                            <th>Aantal</th>
                            <th>Prijs per stuk</th>
                            <th>Totaal</th>
                            <th>Actie</th>
                        </tr>
                    </thead>
                    <tbody>
                        {artikelen_rows if artikelen_rows else '<tr><td colspan="5" style="text-align:center;padding:20px;">Geen artikelen toegevoegd</td></tr>'}
                        <tr style="background:#f5f5f5;font-weight:600;">
                            <td colspan="3">Totaal</td>
                            <td>€ {totaal_prijs:,.2f}</td>
                            <td></td>
                        </tr>
                    </tbody>
                </table>
                
                <form method="post" action="/admin/order/{order_id}/artikel-toevoegen?token={SESSION_SECRET}" class="add-artikel-form">
                    <select name="artikel_id" required>
                        {artikel_options}
                    </select>
                    <input type="number" name="aantal" value="1" min="0.01" step="0.01" required placeholder="Aantal">
                    <button type="submit" class="btn">Toevoegen</button>
                </form>
            </div>
            
            <div class="section">
                <h2>Status</h2>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Status aanvraag</div>
                        <div class="info-value">{portaal_status}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Status offerte</div>
                        <div class="info-value">{order_status}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Partner</div>
                        <div class="info-value">{order.get('partner_naam') or 'Niet toegewezen'}</div>
                    </div>
                </div>
                <div style="margin-top: 15px;">
                    {status_knoppen if status_knoppen else '<p style="color:#666;">Geen acties beschikbaar</p>'}
                </div>
            </div>
            
            <div class="section">
                <h2>Offerte</h2>
                <div>
                    {offerte_knoppen if offerte_knoppen else '<p style="color:#666;">Geen acties beschikbaar</p>'}
                </div>
            </div>
            
            <div class="section">
                <h2>Factuur</h2>
                <div>
                    {factuur_knoppen if factuur_knoppen else '<p style="color:#666;">Geen acties beschikbaar</p>'}
                </div>
            </div>
            <script>
                document.addEventListener('DOMContentLoaded', function() {{
                    const saveBtn = document.getElementById('save-btn');
                    const fields = document.querySelectorAll('.editable-field');
                    let hasChanges = false;

                    if (!saveBtn) {{
                        console.error('Save button niet gevonden');
                        return;
                    }}

                    if (fields.length === 0) {{
                        console.error('Geen editable fields gevonden');
                        return;
                    }}

                    fields.forEach(function(field) {{
                        field.addEventListener('input', function() {{
                            hasChanges = true;
                            saveBtn.disabled = false;
                            saveBtn.className = 'save-btn orange';
                            saveBtn.textContent = 'Opslaan';
                        }});
                    }});

                    saveBtn.addEventListener('click', function() {{
                        if (!hasChanges) return;
                        const data = {{
                            plaats: document.getElementById('plaats').value,
                            leverdatum: document.getElementById('leverdatum').value,
                            aantal_personen: document.getElementById('aantal_personen').value,
                            aantal_kinderen: document.getElementById('aantal_kinderen').value,
                            opmerkingen: document.getElementById('opmerkingen').value
                        }};
                        fetch(window.location.pathname + '/opslaan' + window.location.search, {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify(data)
                        }})
                        .then(function(r) {{ return r.json(); }})
                        .then(function(result) {{
                            if (result.success) {{
                                hasChanges = false;
                                saveBtn.className = 'save-btn green';
                                saveBtn.textContent = 'Opgeslagen ✓';
                                setTimeout(function() {{
                                    saveBtn.disabled = true;
                                    saveBtn.className = 'save-btn';
                                    saveBtn.textContent = 'Geen wijzigingen';
                                }}, 3000);
                            }}
                        }})
                        .catch(function(error) {{
                            console.error('Fout bij opslaan:', error);
                            alert('Fout bij opslaan: ' + error.message);
                        }});
                    }});
                }});
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except HTTPException:
        raise
    except Exception as e:
        _LOG.error(f"Fout bij ophalen order detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij ophalen order: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{order_id}/artikel-toevoegen", response_class=RedirectResponse)
async def artikel_toevoegen(
    request: Request,
    order_id: str,
    background_tasks: BackgroundTasks,
    verified: bool = Depends(verify_admin_session),
    artikel_id: str = Form(...),
    aantal: float = Form(...)
):
    """Voeg artikel toe aan order"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal artikel op
        cur.execute("SELECT * FROM artikelen WHERE id = %s", (artikel_id,))
        artikel = cur.fetchone()
        if not artikel:
            raise HTTPException(status_code=404, detail="Artikel niet gevonden")
        
        # Bereken prijzen
        prijs_excl = float(artikel.get("prijs_excl", 0))
        btw_pct = float(artikel.get("btw_pct", 9.00))
        btw_bedrag = (prijs_excl * aantal) * (btw_pct / 100)
        prijs_incl = (prijs_excl * aantal) + btw_bedrag
        
        # Voeg artikel toe
        cur.execute("""
            INSERT INTO order_artikelen (
                order_id, artikel_id, naam, aantal, prijs_excl, btw_pct, btw_bedrag, prijs_incl
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            order_id, artikel_id, artikel.get("naam"), aantal,
            prijs_excl, btw_pct, btw_bedrag, prijs_incl
        ))
        
        # Herbereken totaalprijs
        totals = calculate_order_totals(order_id, conn)
        
        cur.execute("""
            UPDATE orders
            SET totaal_bedrag = %s, bedrag_excl_btw = %s, bedrag_btw = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (totals["totaal_bedrag"], totals["bedrag_excl_btw"], totals["bedrag_btw"], order_id))
        
        conn.commit()
        
        # Update factuur als nodig (alleen als betaal_status = 'factuur_verstuurd')
        try:
            update_factuur_bij_orderwijziging(order_id, totals["totaal_bedrag"], conn, background_tasks)
        except Exception as e:
            _LOG.error(f"Fout bij updaten factuur na artikel toevoegen: {e}", exc_info=True)
            # Ga door, dit is niet kritiek voor de redirect
        
        return RedirectResponse(url=f"/admin/order/{order_id}?token={SESSION_SECRET}", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij toevoegen artikel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij toevoegen artikel: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{order_id}/artikel-verwijderen/{artikel_line_id}", response_class=RedirectResponse)
async def artikel_verwijderen(
    request: Request,
    order_id: str,
    artikel_line_id: str,
    background_tasks: BackgroundTasks,
    verified: bool = Depends(verify_admin_session)
):
    """Verwijder artikel regel uit order"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verwijder artikel regel
        cur.execute("DELETE FROM order_artikelen WHERE id = %s AND order_id = %s", (artikel_line_id, order_id))
        
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Artikel regel niet gevonden")
        
        # Herbereken totaalprijs
        totals = calculate_order_totals(order_id, conn)
        
        cur.execute("""
            UPDATE orders
            SET totaal_bedrag = %s, bedrag_excl_btw = %s, bedrag_btw = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (totals["totaal_bedrag"], totals["bedrag_excl_btw"], totals["bedrag_btw"], order_id))
        
        conn.commit()
        
        # Update factuur als nodig (alleen als betaal_status = 'factuur_verstuurd')
        try:
            update_factuur_bij_orderwijziging(order_id, totals["totaal_bedrag"], conn, background_tasks)
        except Exception as e:
            _LOG.error(f"Fout bij updaten factuur na artikel verwijderen: {e}", exc_info=True)
            # Ga door, dit is niet kritiek voor de redirect
        
        return RedirectResponse(url=f"/admin/order/{order_id}?token={SESSION_SECRET}", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij verwijderen artikel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij verwijderen artikel: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{order_id}/status", response_class=RedirectResponse)
async def wijzig_status(
    request: Request,
    order_id: str,
    verified: bool = Depends(verify_admin_session),
    portaal_status: str = Form(...)
):
    """Wijzig portaal status van order"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE orders
            SET portaal_status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (portaal_status, order_id))
        
        conn.commit()
        
        return RedirectResponse(url=f"/admin/order/{order_id}?token={SESSION_SECRET}", status_code=303)
        
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij wijzigen status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij wijzigen status: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{order_id}/claim", response_class=RedirectResponse)
async def claim_order(
    request: Request,
    order_id: str,
    verified: bool = Depends(verify_admin_session)
):
    """Claim order voor Aardappeltuin (contractor_id = 87)"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Zoek Aardappeltuin contact (odoo_id = 87 of naam bevat "Aardappeltuin")
        cur.execute("SELECT id FROM contacten WHERE odoo_id = 87 OR naam ILIKE '%aardappeltuin%' LIMIT 1")
        contractor = cur.fetchone()
        
        if not contractor:
            raise HTTPException(status_code=404, detail="Aardappeltuin contact niet gevonden")
        
        contractor_id = contractor["id"]
        
        cur.execute("""
            UPDATE orders
            SET contractor_id = %s, portaal_status = 'claimed', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (contractor_id, order_id))
        
        conn.commit()
        
        return RedirectResponse(url=f"/admin/order/{order_id}?token={SESSION_SECRET}", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij claimen order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij claimen order: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{order_id}/verstuur-offerte", response_class=RedirectResponse)
async def verstuur_offerte(
    request: Request,
    order_id: str,
    background_tasks: BackgroundTasks,
    verified: bool = Depends(verify_admin_session)
):
    """Verstuur offerte via email"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal order op met contact
        cur.execute("""
            SELECT o.*, c.email as klant_email, c.naam as klant_naam
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            WHERE o.id = %s
        """, (order_id,))
        
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order niet gevonden")
        
        klant_email = order.get("klant_email")
        if not klant_email:
            raise HTTPException(status_code=400, detail="Geen email adres gevonden voor klant")
        
        # Bepaal template naam
        order_status = order.get("status", "draft")
        if order_status == "draft":
            template_name = "Verkoop: Offerte verzenden test 2.0"
        else:
            template_name = "Verkoop: Offerte aanpassing verzenden"
        
        # Laad template
        template_html = load_template(template_name)
        if not template_html:
            raise HTTPException(status_code=500, detail=f"Template '{template_name}' niet gevonden")
        
        # Genereer bevestig token (UUID4)
        bevestig_token = str(uuid.uuid4())
        
        # Sla token op in database
        cur.execute("""
            UPDATE orders
            SET bevestig_token = %s
            WHERE id = %s
        """, (bevestig_token, order_id))
        
        # Maak bevestigingslink
        bevestig_link = f"https://fth-portaal-production.up.railway.app/bevestig/{bevestig_token}"
        
        # Voeg bevestigingslink toe aan template
        # Zoek naar einde van body of voeg toe aan einde
        if "</body>" in template_html:
            bevestig_html = f'<p style="margin-top: 20px; padding: 15px; background: #f9f9f9; border-radius: 8px;"><strong>Bevestig uw aanvraag:</strong><br><a href="{bevestig_link}" style="color: #fec82a; font-weight: bold; text-decoration: none;">Klik hier om uw aanvraag te bevestigen</a></p>'
            template_html = template_html.replace("</body>", bevestig_html + "</body>")
        else:
            # Als geen body tag, voeg toe aan einde
            bevestig_html = f'<p style="margin-top: 20px; padding: 15px; background: #f9f9f9; border-radius: 8px;"><strong>Bevestig uw aanvraag:</strong><br><a href="{bevestig_link}" style="color: #fec82a; font-weight: bold; text-decoration: none;">Klik hier om uw aanvraag te bevestigen</a></p>'
            template_html = template_html + bevestig_html
        
        # Update order status direct (voor redirect)
        cur.execute("""
            UPDATE orders
            SET status = 'sent', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (order_id,))
        
        conn.commit()
        
        # Verstuur mail in background (niet blokkerend)
        background_tasks.add_task(
            stuur_mail,
            naar=klant_email,
            onderwerp=f"Offerte {order.get('ordernummer', '')}",
            inhoud=template_html,
            order_id=order_id,
            template_naam=template_name
        )
        
        return RedirectResponse(url=f"/admin/order/{order_id}?token={SESSION_SECRET}", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij versturen offerte: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij versturen offerte: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{order_id}/verstuur-factuur", response_class=RedirectResponse)
async def verstuur_factuur(
    request: Request,
    order_id: str,
    background_tasks: BackgroundTasks,
    verified: bool = Depends(verify_admin_session)
):
    """Verstuur factuur met Mollie betaallink"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal order op met contact
        cur.execute("""
            SELECT o.*, c.email as klant_email, c.naam as klant_naam
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            WHERE o.id = %s
        """, (order_id,))
        
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order niet gevonden")
        
        # Check of status = sale (bevestigd)
        if order.get("status") != "sale":
            raise HTTPException(status_code=400, detail="Order moet bevestigd zijn (status = sale) voordat factuur verstuurd kan worden")
        
        # Check betaal_status
        betaal_status = order.get("betaal_status")
        if betaal_status == "betaald":
            raise HTTPException(status_code=400, detail="Order al betaald - geen wijzigingen mogelijk")
        
        # Check of er al een factuur is
        cur.execute("""
            SELECT id, mollie_checkout_url, factuurnummer, totaal_bedrag
            FROM facturen WHERE order_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (order_id,))
        
        bestaande_factuur = cur.fetchone()
        
        if bestaande_factuur and betaal_status == "factuur_verstuurd":
            # Factuur bestaat al en is verstuurd, stuur bestaande link opnieuw
            mollie_checkout_url = bestaande_factuur.get("mollie_checkout_url")
            factuurnummer = bestaande_factuur.get("factuurnummer", "")
            totaal_bedrag = float(bestaande_factuur.get("totaal_bedrag", 0))
            ordertype = order.get("ordertype") or "b2c"
            
            if not mollie_checkout_url:
                raise HTTPException(status_code=400, detail="Factuur heeft geen Mollie betaallink")
            
            # Maak mail body (zelfde als verstuur-factuur-nogmaals)
            if ordertype == "b2b":
                mail_body = f"""
                <html>
                <body>
                    <h2>Factuur {factuurnummer}</h2>
                    <p>Beste {order.get('klant_naam', '')},</p>
                    <p>Bij deze ontvangt u de factuur voor uw bestelling {order.get('ordernummer', '')}.</p>
                    <p><strong>Te betalen bedrag: € {totaal_bedrag:,.2f}</strong></p>
                    <p>U kunt betalen via de onderstaande betaallink:</p>
                    <p><a href="{mollie_checkout_url}" style="background:#fec82a;color:#333;padding:12px 24px;text-decoration:none;border-radius:8px;display:inline-block;font-weight:bold;">Betaal nu</a></p>
                    <p>Of maak het bedrag over naar:</p>
                    <p><strong>Rekeningnummer:</strong> NL91ABNA0417164300<br>
                    <strong>Ten name van:</strong> Treatlab VOF</p>
                    <p>Met vriendelijke groet,<br>FTH Portaal</p>
                </body>
                </html>
                """
            else:
                mail_body = f"""
                <html>
                <body>
                    <h2>Factuur {factuurnummer}</h2>
                    <p>Beste {order.get('klant_naam', '')},</p>
                    <p>Bij deze ontvangt u de factuur voor uw bestelling {order.get('ordernummer', '')}.</p>
                    <p><strong>Te betalen bedrag: € {totaal_bedrag:,.2f}</strong></p>
                    <p>U kunt betalen via de onderstaande betaallink:</p>
                    <p><a href="{mollie_checkout_url}" style="background:#fec82a;color:#333;padding:12px 24px;text-decoration:none;border-radius:8px;display:inline-block;font-weight:bold;">Betaal nu</a></p>
                    <p>Met vriendelijke groet,<br>FTH Portaal</p>
                </body>
                </html>
                """
            
            # Verstuur mail in background
            background_tasks.add_task(
                stuur_mail,
                naar=klant_email,
                onderwerp=f"Factuur {factuurnummer} - {order.get('ordernummer', '')}",
                inhoud=mail_body,
                order_id=order_id,
                template_naam="Factuur"
            )
            
            return RedirectResponse(url=f"/admin/order/{order_id}?token={SESSION_SECRET}", status_code=303)
        
        klant_email = order.get("klant_email")
        if not klant_email:
            raise HTTPException(status_code=400, detail="Geen email adres gevonden voor klant")
        
        ordernummer = order.get("ordernummer", "")
        totaal_bedrag = float(order.get("totaal_bedrag", 0))
        ordertype = order.get("ordertype") or "b2c"
        
        # Genereer factuurnummer: FTHINVYYYYMMDDXXXX
        today = datetime.now()
        random_suffix = random.randint(1000, 9999)
        factuurnummer = f"FTHINV{today.strftime('%Y%m%d')}{random_suffix:04d}"
        
        # Maak Mollie payment
        try:
            payment = create_payment(
                amount=totaal_bedrag,
                description=f"Factuur {ordernummer}",
                redirect_url="https://fth-portaal-production.up.railway.app/betaling/bedankt",
                webhook_url="https://fth-portaal-production.up.railway.app/webhooks/mollie",
                metadata={"order_id": str(order_id)}
            )
        except Exception as e:
            _LOG.error(f"Fout bij aanmaken Mollie payment: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Fout bij aanmaken betaallink: {str(e)}")
        
        mollie_payment_id = payment["id"]
        mollie_checkout_url = payment["checkout_url"]
        
        # Sla factuur op in database
        cur.execute("""
            INSERT INTO facturen (
                factuurnummer, factuurdatum, klant_id, order_id,
                totaal_bedrag, bedrag_excl_btw, bedrag_btw,
                status, betalingsstatus, type_naam,
                mollie_payment_id, mollie_checkout_url
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            factuurnummer,
            today.date(),
            order.get("klant_id"),
            order_id,
            totaal_bedrag,
            float(order.get("bedrag_excl_btw", 0)),
            float(order.get("bedrag_btw", 0)),
            "posted",  # status
            "not_paid",  # betalingsstatus
            "Invoice",  # type_naam
            mollie_payment_id,
            mollie_checkout_url
        ))
        
        factuur_id = cur.fetchone()["id"]
        
        # Update order betaal_status
        cur.execute("""
            UPDATE orders
            SET betaal_status = 'factuur_verstuurd', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (order_id,))
        
        conn.commit()
        
        # Maak mail body
        if ordertype == "b2b":
            mail_body = f"""
            <html>
            <body>
                <h2>Factuur {factuurnummer}</h2>
                <p>Beste {order.get('klant_naam', '')},</p>
                <p>Bij deze ontvangt u de factuur voor uw bestelling {ordernummer}.</p>
                <p><strong>Te betalen bedrag: € {totaal_bedrag:,.2f}</strong></p>
                <p>U kunt betalen via de onderstaande betaallink:</p>
                <p><a href="{mollie_checkout_url}" style="background:#fec82a;color:#333;padding:12px 24px;text-decoration:none;border-radius:8px;display:inline-block;font-weight:bold;">Betaal nu</a></p>
                <p>Of maak het bedrag over naar:</p>
                <p><strong>Rekeningnummer:</strong> NL91ABNA0417164300<br>
                <strong>Ten name van:</strong> Treatlab VOF</p>
                <p>Met vriendelijke groet,<br>FTH Portaal</p>
            </body>
            </html>
            """
        else:
            mail_body = f"""
            <html>
            <body>
                <h2>Factuur {factuurnummer}</h2>
                <p>Beste {order.get('klant_naam', '')},</p>
                <p>Bij deze ontvangt u de factuur voor uw bestelling {ordernummer}.</p>
                <p><strong>Te betalen bedrag: € {totaal_bedrag:,.2f}</strong></p>
                <p>U kunt betalen via de onderstaande betaallink:</p>
                <p><a href="{mollie_checkout_url}" style="background:#fec82a;color:#333;padding:12px 24px;text-decoration:none;border-radius:8px;display:inline-block;font-weight:bold;">Betaal nu</a></p>
                <p>Met vriendelijke groet,<br>FTH Portaal</p>
            </body>
            </html>
            """
        
        # Verstuur mail in background
        background_tasks.add_task(
            stuur_mail,
            naar=klant_email,
            onderwerp=f"Factuur {factuurnummer} - {ordernummer}",
            inhoud=mail_body,
            order_id=order_id,
            template_naam="Factuur"
        )
        
        return RedirectResponse(url=f"/admin/order/{order_id}?token={SESSION_SECRET}", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij versturen factuur: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij versturen factuur: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{order_id}/bevestig", response_class=RedirectResponse)
async def bevestig_order(
    request: Request,
    order_id: str,
    verified: bool = Depends(verify_admin_session)
):
    """Bevestig order handmatig (zet status naar sale)"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check of order bestaat
        cur.execute("SELECT id, status FROM orders WHERE id = %s", (order_id,))
        order = cur.fetchone()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order niet gevonden")
        
        # Update order status
        cur.execute("""
            UPDATE orders
            SET status = 'sale', portaal_status = 'beschikbaar', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (order_id,))
        
        conn.commit()
        
        return RedirectResponse(url=f"/admin/order/{order_id}?token={SESSION_SECRET}", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij bevestigen order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij bevestigen order: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{order_id}/opslaan")
async def opslaan_order(
    request: Request,
    order_id: str,
    verified: bool = Depends(verify_admin_session)
):
    """Sla order wijzigingen op"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal request body op
        body = await request.json()
        
        plaats = body.get("plaats", "").strip()
        leverdatum_str = body.get("leverdatum", "").strip()
        aantal_personen = int(body.get("aantal_personen", 0)) if body.get("aantal_personen") else 0
        aantal_kinderen = int(body.get("aantal_kinderen", 0)) if body.get("aantal_kinderen") else 0
        opmerkingen = body.get("opmerkingen", "").strip()
        
        # Parse leverdatum (datetime-local format: YYYY-MM-DDTHH:MM)
        leverdatum = None
        if leverdatum_str:
            try:
                # Convert datetime-local to datetime
                leverdatum = datetime.strptime(leverdatum_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                # Try alternative format
                try:
                    leverdatum = datetime.strptime(leverdatum_str[:16], "%Y-%m-%d %H:%M")
                except ValueError:
                    _LOG.warning(f"Kon leverdatum niet parsen: {leverdatum_str}")
        
        # Update order
        cur.execute("""
            UPDATE orders
            SET plaats = %s,
                leverdatum = %s,
                aantal_personen = %s,
                aantal_kinderen = %s,
                opmerkingen = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            plaats if plaats else None,
            leverdatum,
            aantal_personen,
            aantal_kinderen,
            opmerkingen if opmerkingen else None,
            order_id
        ))
        
        conn.commit()
        
        return JSONResponse(content={"success": True})
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij opslaan order: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": f"Fout bij opslaan order: {str(e)}"}
        )
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{order_id}/verstuur-factuur-nogmaals", response_class=RedirectResponse)
async def verstuur_factuur_nogmaals(
    request: Request,
    order_id: str,
    background_tasks: BackgroundTasks,
    verified: bool = Depends(verify_admin_session)
):
    """Verstuur factuur nogmaals met bestaande Mollie link"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal order op met contact
        cur.execute("""
            SELECT o.*, c.email as klant_email, c.naam as klant_naam
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            WHERE o.id = %s
        """, (order_id,))
        
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order niet gevonden")
        
        klant_email = order.get("klant_email")
        if not klant_email:
            raise HTTPException(status_code=400, detail="Geen email adres gevonden voor klant")
        
        # Haal bestaande factuur op
        cur.execute("""
            SELECT factuurnummer, mollie_checkout_url, totaal_bedrag
            FROM facturen
            WHERE order_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (order_id,))
        
        factuur = cur.fetchone()
        if not factuur:
            raise HTTPException(status_code=404, detail="Geen factuur gevonden voor deze order")
        
        factuurnummer = factuur.get("factuurnummer", "")
        mollie_checkout_url = factuur.get("mollie_checkout_url")
        totaal_bedrag = float(factuur.get("totaal_bedrag", 0))
        
        if not mollie_checkout_url:
            raise HTTPException(status_code=400, detail="Factuur heeft geen Mollie betaallink")
        
        ordernummer = order.get("ordernummer", "")
        ordertype = order.get("ordertype") or "b2c"
        
        # Maak mail body (zelfde als verstuur-factuur)
        if ordertype == "b2b":
            mail_body = f"""
            <html>
            <body>
                <h2>Factuur {factuurnummer}</h2>
                <p>Beste {order.get('klant_naam', '')},</p>
                <p>Bij deze ontvangt u de factuur voor uw bestelling {ordernummer}.</p>
                <p><strong>Te betalen bedrag: € {totaal_bedrag:,.2f}</strong></p>
                <p>U kunt betalen via de onderstaande betaallink:</p>
                <p><a href="{mollie_checkout_url}" style="background:#fec82a;color:#333;padding:12px 24px;text-decoration:none;border-radius:8px;display:inline-block;font-weight:bold;">Betaal nu</a></p>
                <p>Of maak het bedrag over naar:</p>
                <p><strong>Rekeningnummer:</strong> NL91ABNA0417164300<br>
                <strong>Ten name van:</strong> Treatlab VOF</p>
                <p>Met vriendelijke groet,<br>FTH Portaal</p>
            </body>
            </html>
            """
        else:
            mail_body = f"""
            <html>
            <body>
                <h2>Factuur {factuurnummer}</h2>
                <p>Beste {order.get('klant_naam', '')},</p>
                <p>Bij deze ontvangt u de factuur voor uw bestelling {ordernummer}.</p>
                <p><strong>Te betalen bedrag: € {totaal_bedrag:,.2f}</strong></p>
                <p>U kunt betalen via de onderstaande betaallink:</p>
                <p><a href="{mollie_checkout_url}" style="background:#fec82a;color:#333;padding:12px 24px;text-decoration:none;border-radius:8px;display:inline-block;font-weight:bold;">Betaal nu</a></p>
                <p>Met vriendelijke groet,<br>FTH Portaal</p>
            </body>
            </html>
            """
        
        # Verstuur mail in background
        background_tasks.add_task(
            stuur_mail,
            naar=klant_email,
            onderwerp=f"Factuur {factuurnummer} - {ordernummer}",
            inhoud=mail_body,
            order_id=order_id,
            template_naam="Factuur"
        )
        
        return RedirectResponse(url=f"/admin/order/{order_id}?token={SESSION_SECRET}", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij nogmaals versturen factuur: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij nogmaals versturen factuur: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()
