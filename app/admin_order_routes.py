"""
Admin order detail endpoints.
"""
import os
import logging
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from app.config import SESSION_SECRET
from app.mail import stuur_mail
from app.admin_routes import verify_admin_session, get_database_url

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
        
        # Format datums
        def format_datetime(dt):
            if not dt:
                return "-"
            if isinstance(dt, str):
                return dt[:16]
            return dt.strftime("%Y-%m-%d %H:%M")
        
        leverdatum = format_datetime(order.get("leverdatum"))
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
            </style>
        </head>
        <body>
            <div class="header">
                <a href="/admin?token={SESSION_SECRET}" class="back-link">← Terug naar dashboard</a>
                <h1>Aanvraag: {order.get('ordernummer', 'N/A')}</h1>
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
                        <div class="info-value">{order.get('plaats') or '-'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Leverdatum</div>
                        <div class="info-value">{leverdatum}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Personen / Kinderen</div>
                        <div class="info-value">{order.get('aantal_personen', 0)} / {order.get('aantal_kinderen', 0)}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Ordertype</div>
                        <div class="info-value">{order.get('ordertype', '-')}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Opmerkingen</div>
                        <div class="info-value">{order.get('opmerkingen') or '-'}</div>
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
        
        # TODO: Vervang template variabelen met order data
        # Voor nu sturen we template zoals het is
        
        # Verstuur mail
        result = stuur_mail(
            naar=klant_email,
            onderwerp=f"Offerte {order.get('ordernummer', '')}",
            inhoud=template_html,
            order_id=order_id,
            template_naam=template_name
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=f"Mail verzending gefaald: {result.get('error')}")
        
        # Update order status
        cur.execute("""
            UPDATE orders
            SET status = 'sent', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (order_id,))
        
        conn.commit()
        
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
