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
from app.templates import (
    render_offerte_v10, format_dutch_date, format_time, format_currency, render_bevestiging_b,
    render_planning_9dagen, render_planning_7dagen,
    render_planning_5dagen_betaald, render_planning_5dagen_onbetaald,
    render_planning_3dagen_betaald, render_planning_3dagen_onbetaald,
    render_planning_1dag_betaald, render_planning_1dag_onbetaald
)
from app.planning_scheduler import (
    get_base_url, get_pakket_naam, get_broodjes_ja_nee, get_drankjes_ja_nee,
    get_partner_telefoon, get_totaal_bedrag, generate_afmeld_token
)
from app.factuur import generate_factuur_pdf
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


def is_definitief(order):
    """Check of order definitief is: status = 'sale' EN portaal_status IN ('claimed', 'transfer')"""
    return (order.get('status') == 'sale' and 
            order.get('portaal_status') in ('claimed', 'transfer'))


def calculate_order_totals(order_id: str, conn) -> dict:
    """Herbereken totaalprijs van order op basis van order_artikelen"""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT 
            COALESCE(SUM(prijs_incl * aantal), 0) as totaal_incl
        FROM order_artikelen
        WHERE order_id = %s
    """, (order_id,))
    
    result = cur.fetchone()
    cur.close()
    
    # Bereken prijs_excl en btw_bedrag on-the-fly (9% BTW)
    totaal_incl = float(result["totaal_incl"]) if result["totaal_incl"] else 0.00
    totaal_excl = round(totaal_incl / 1.09, 2)
    totaal_btw = round(totaal_incl - totaal_excl, 2)
    
    return {
        "totaal_bedrag": totaal_incl,
        "bedrag_excl_btw": totaal_excl,
        "bedrag_btw": totaal_btw
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
        
        # Debug logging
        _LOG.info(f"Update factuur {factuur_id} voor order {order_id}: nieuwe payment_id={nieuwe_mollie_payment_id}, checkout_url={nieuwe_mollie_checkout_url}")
        print(f"Nieuwe Mollie URL: {nieuwe_mollie_checkout_url}")
        
        # Update factuur record - gebruik WHERE id = factuur_id (meest recente factuur voor deze order)
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
        
        rows_updated = cur.rowcount
        _LOG.info(f"UPDATE facturen uitgevoerd: {rows_updated} rij(en) geupdate voor factuur_id {factuur_id} (order {order_id})")
        
        if rows_updated == 0:
            _LOG.error(f"GEEN factuur geupdate voor factuur_id {factuur_id}! Factuur bestaat mogelijk niet.")
        
        conn.commit()
        
        # Verifieer dat checkout URL is opgeslagen
        cur.execute("SELECT mollie_checkout_url FROM facturen WHERE order_id = %s ORDER BY updated_at DESC LIMIT 1", (order_id,))
        saved_factuur = cur.fetchone()
        if saved_factuur:
            saved_url = saved_factuur.get("mollie_checkout_url")
            _LOG.info(f"Factuur geupdate voor order {order_id}, opgeslagen checkout_url: {saved_url}")
            print(f"Nieuwe Mollie URL opgeslagen: {saved_url}")
            if saved_url != nieuwe_mollie_checkout_url:
                _LOG.warning(f"WAARSCHUWING: Opgeslagen URL ({saved_url}) verschilt van nieuwe URL ({nieuwe_mollie_checkout_url})")
                # Gebruik de opgeslagen URL voor mail
                nieuwe_mollie_checkout_url = saved_url if saved_url else nieuwe_mollie_checkout_url
        else:
            _LOG.error(f"GEEN factuur gevonden na UPDATE voor order {order_id}!")
        
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
            onderwerp=f"Aangepaste factuur {ordernummer} — Friettruck-huren.nl",
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


@router.get("/test-planning-flow/{order_id}", response_class=HTMLResponse)
async def test_planning_flow(
    request: Request,
    order_id: str,
    force: bool = False,
    verified: bool = Depends(verify_admin_session)
):
    """Test endpoint om alle planning emails te versturen voor een order"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal order op
        cur.execute("""
            SELECT 
                o.id, o.ordernummer, o.leverdatum, o.plaats, 
                o.aantal_personen, o.aantal_kinderen, o.contractor_id,
                o.planning_afmeld_token, o.betaal_status, o.status,
                c.naam as voornaam, c.email, c.adres as klant_adres
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            WHERE o.id = %s
        """, (order_id,))
        
        order = cur.fetchone()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order niet gevonden")
        
        email = order.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Order heeft geen email adres")
        
        ordernummer = order.get("ordernummer", "")
        leverdatum = order.get("leverdatum")
        plaats = order.get("plaats", "")
        klant_adres = order.get("klant_adres", "") or ""
        aantal_personen = order.get("aantal_personen", 0)
        aantal_kinderen = order.get("aantal_kinderen", 0)
        contractor_id = order.get("contractor_id")
        planning_afmeld_token = order.get("planning_afmeld_token")
        betaal_status = order.get("betaal_status")
        voornaam = order.get("voornaam", "klant") or "klant"
        
        base_url = get_base_url()
        
        # Haal basis data op
        pakket = get_pakket_naam(cur, order_id)
        partner_telefoon = get_partner_telefoon(cur, contractor_id)
        totaal_bedrag = get_totaal_bedrag(cur, order_id)
        totaal_str = f"€ {format_currency(totaal_bedrag)}"
        datum = format_dutch_date(leverdatum) if leverdatum else ""
        tijdstip = format_time(leverdatum) if leverdatum else ""
        
        # Resultaten lijst
        results = []
        
        # Dag configuratie
        dagen_config = [
            {"dagen": 9, "template_naam": "planning_9dagen", "heeft_broodjes_drankjes": True, "heeft_pdf": False, "heeft_token": False},
            {"dagen": 7, "template_naam": "planning_7dagen", "heeft_broodjes_drankjes": False, "heeft_pdf": True, "heeft_token": False},
            {"dagen": 5, "template_naam": "planning_5dagen", "heeft_broodjes_drankjes": False, "heeft_pdf": True, "heeft_token": True},
            {"dagen": 3, "template_naam": "planning_3dagen", "heeft_broodjes_drankjes": False, "heeft_pdf": True, "heeft_token": False},
            {"dagen": 1, "template_naam": "planning_1dag", "heeft_broodjes_drankjes": False, "heeft_pdf": True, "heeft_token": False},
        ]
        
        for dag_config in dagen_config:
            dagen = dag_config["dagen"]
            template_base = dag_config["template_naam"]
            heeft_broodjes_drankjes = dag_config["heeft_broodjes_drankjes"]
            heeft_pdf = dag_config["heeft_pdf"]
            heeft_token = dag_config["heeft_token"]
            
            try:
                # Check duplicate sending (overslaan als force=True)
                if not force:
                    from app.planning_scheduler import check_duplicate_sending
                    template_naam_check = f"{template_base}_betaald" if dagen in [5, 3, 1] and betaal_status == 'betaald' else (f"{template_base}_onbetaald" if dagen in [5, 3, 1] and betaal_status != 'betaald' else template_base)
                    if check_duplicate_sending(cur, order_id, template_naam_check):
                        results.append({
                            "template": template_naam_check,
                            "status": "overgeslagen",
                            "error": "Mail al vandaag verstuurd (gebruik ?force=true om te forceren)"
                        })
                        continue
                
                # Bepaal betaald/onbetaald voor dag 5, 3, 1
                is_betaald = (betaal_status == 'betaald') if dagen in [5, 3, 1] else None
                
                # Token generatie (alleen dag 5 betaald)
                if heeft_token and is_betaald and not planning_afmeld_token:
                    planning_afmeld_token = generate_afmeld_token(cur, order_id, conn)
                
                afmeldlink = f"{base_url}/planning/afmelden/{planning_afmeld_token}" if planning_afmeld_token else ""
                
                # Betaallink ophalen (voor dag 7, 5 onbetaald, 3 onbetaald, 1 onbetaald)
                betaallink = ""
                if dagen == 7 or (dagen in [5, 3, 1] and not is_betaald):
                    cur.execute("""
                        SELECT mollie_checkout_url
                        FROM facturen
                        WHERE order_id = %s
                        LIMIT 1
                    """, (order_id,))
                    factuur_result = cur.fetchone()
                    betaallink = factuur_result['mollie_checkout_url'] if factuur_result else ""
                
                # Broodjes/drankjes (alleen dag 9)
                broodjes_ja_nee = ""
                drankjes_ja_nee = ""
                if heeft_broodjes_drankjes:
                    broodjes_ja_nee = get_broodjes_ja_nee(cur, order_id)
                    drankjes_ja_nee = get_drankjes_ja_nee(cur, order_id)
                
                # Render HTML
                if dagen == 9:
                    html = render_planning_9dagen(
                        voornaam=voornaam,
                        aantal_personen=aantal_personen,
                        aantal_kinderen=aantal_kinderen,
                        pakket=pakket,
                        broodjes_ja_nee=broodjes_ja_nee,
                        drankjes_ja_nee=drankjes_ja_nee,
                        locatie=plaats,
                        datum=datum,
                        tijdstip=tijdstip,
                        totaal=totaal_str,
                        partner_telefoon=partner_telefoon,
                        klant_adres=klant_adres
                    )
                    template_naam = "planning_9dagen"
                elif dagen == 7:
                    html = render_planning_7dagen(
                        voornaam=voornaam,
                        aantal_personen=aantal_personen,
                        aantal_kinderen=aantal_kinderen,
                        pakket=pakket,
                        locatie=plaats,
                        datum=datum,
                        tijdstip=tijdstip,
                        totaal=totaal_str,
                        partner_telefoon=partner_telefoon,
                        betaallink=betaallink,
                        klant_adres=klant_adres
                    )
                    template_naam = "planning_7dagen"
                elif dagen == 5:
                    if is_betaald:
                        html = render_planning_5dagen_betaald(
                            voornaam=voornaam,
                            aantal_personen=aantal_personen,
                            aantal_kinderen=aantal_kinderen,
                            pakket=pakket,
                            locatie=plaats,
                            datum=datum,
                            tijdstip=tijdstip,
                            totaal=totaal_str,
                            partner_telefoon=partner_telefoon,
                            afmeldlink=afmeldlink,
                            klant_adres=klant_adres
                        )
                        template_naam = "planning_5dagen_betaald"
                    else:
                        html = render_planning_5dagen_onbetaald(
                            voornaam=voornaam,
                            aantal_personen=aantal_personen,
                            aantal_kinderen=aantal_kinderen,
                            pakket=pakket,
                            locatie=plaats,
                            datum=datum,
                            tijdstip=tijdstip,
                            totaal=totaal_str,
                            partner_telefoon=partner_telefoon,
                            betaallink=betaallink,
                            klant_adres=klant_adres
                        )
                        template_naam = "planning_5dagen_onbetaald"
                elif dagen == 3:
                    if is_betaald:
                        html = render_planning_3dagen_betaald(
                            voornaam=voornaam,
                            aantal_personen=aantal_personen,
                            aantal_kinderen=aantal_kinderen,
                            pakket=pakket,
                            locatie=plaats,
                            datum=datum,
                            tijdstip=tijdstip,
                            totaal=totaal_str,
                            partner_telefoon=partner_telefoon,
                            afmeldlink=afmeldlink,
                            klant_adres=klant_adres
                        )
                        template_naam = "planning_3dagen_betaald"
                    else:
                        html = render_planning_3dagen_onbetaald(
                            voornaam=voornaam,
                            aantal_personen=aantal_personen,
                            aantal_kinderen=aantal_kinderen,
                            pakket=pakket,
                            locatie=plaats,
                            datum=datum,
                            tijdstip=tijdstip,
                            totaal=totaal_str,
                            partner_telefoon=partner_telefoon,
                            betaallink=betaallink,
                            klant_adres=klant_adres
                        )
                        template_naam = "planning_3dagen_onbetaald"
                else:  # dag 1
                    if is_betaald:
                        html = render_planning_1dag_betaald(
                            voornaam=voornaam,
                            aantal_personen=aantal_personen,
                            aantal_kinderen=aantal_kinderen,
                            pakket=pakket,
                            locatie=plaats,
                            datum=datum,
                            tijdstip=tijdstip,
                            totaal=totaal_str,
                            partner_telefoon=partner_telefoon,
                            afmeldlink=afmeldlink,
                            klant_adres=klant_adres
                        )
                        template_naam = "planning_1dag_betaald"
                    else:
                        html = render_planning_1dag_onbetaald(
                            voornaam=voornaam,
                            aantal_personen=aantal_personen,
                            aantal_kinderen=aantal_kinderen,
                            pakket=pakket,
                            locatie=plaats,
                            datum=datum,
                            tijdstip=tijdstip,
                            totaal=totaal_str,
                            partner_telefoon=partner_telefoon,
                            betaallink=betaallink,
                            klant_adres=klant_adres
                        )
                        template_naam = "planning_1dag_onbetaald"
                
                # Genereer PDF bijlage indien nodig
                attachments = []
                if heeft_pdf:
                    try:
                        pdf_bytes = generate_factuur_pdf(order_id)
                        attachments.append({
                            "filename": f"factuur_{ordernummer}.pdf",
                            "content": pdf_bytes,
                            "content_type": "application/pdf"
                        })
                    except Exception as e:
                        _LOG.error(f"Fout bij PDF generatie voor order {order_id}: {e}", exc_info=True)
                        results.append({
                            "template": template_naam,
                            "status": "mislukt",
                            "error": f"PDF generatie gefaald: {str(e)}"
                        })
                        continue
                
                # Verstuur mail
                stuur_mail(
                    naar=email,
                    onderwerp=f"Nog {dagen} {'dag' if dagen == 1 else 'dagen'} tot uw friettruck-feest!",
                    inhoud=html,
                    order_id=order_id,
                    template_naam=template_naam,
                    attachments=attachments if attachments else None
                )
                
                results.append({
                    "template": template_naam,
                    "status": "verstuurd",
                    "error": None
                })
                
            except Exception as e:
                _LOG.error(f"Fout bij versturen {template_base} voor order {order_id}: {e}", exc_info=True)
                results.append({
                    "template": template_base,
                    "status": "mislukt",
                    "error": str(e)
                })
        
        # Genereer HTML response
        results_html = ""
        for result in results:
            if result["status"] == "verstuurd":
                status_badge = '<span style="background:#27ae60;color:white;padding:4px 12px;border-radius:4px;font-size:12px;font-weight:700;">VERSTUURD</span>'
            elif result["status"] == "overgeslagen":
                status_badge = '<span style="background:#f39c12;color:white;padding:4px 12px;border-radius:4px;font-size:12px;font-weight:700;">OVERGESLAGEN</span>'
            else:
                status_badge = '<span style="background:#e74c3c;color:white;padding:4px 12px;border-radius:4px;font-size:12px;font-weight:700;">MISLUKT</span>'
            error_text = f'<div style="color:#e74c3c;font-size:12px;margin-top:4px;">{result["error"]}</div>' if result["error"] else ""
            results_html += f"""
                <tr>
                    <td>{result["template"]}</td>
                    <td>{status_badge}</td>
                    <td>{error_text}</td>
                </tr>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="nl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Planning Flow Test - FTH</title>
            <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;900&display=swap" rel="stylesheet">
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: 'Montserrat', sans-serif;
                    background: #f5f5f5;
                    padding: 20px;
                }}
                .container {{
                    max-width: 1000px;
                    margin: 0 auto;
                    background: white;
                    padding: 30px;
                    border-radius: 12px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #2d2d2d;
                    margin-bottom: 30px;
                    font-size: 28px;
                }}
                .order-info {{
                    background: #f9f9f9;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 30px;
                }}
                .info-row {{
                    display: flex;
                    justify-content: space-between;
                    padding: 8px 0;
                    border-bottom: 1px solid #e0e0e0;
                }}
                .info-row:last-child {{
                    border-bottom: none;
                }}
                .info-label {{
                    color: #666;
                    font-weight: 600;
                }}
                .info-value {{
                    color: #2d2d2d;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                th, td {{
                    padding: 12px;
                    text-align: left;
                    border-bottom: 1px solid #e0e0e0;
                }}
                th {{
                    background: #f9f9f9;
                    font-weight: 700;
                    color: #2d2d2d;
                }}
                .back-link {{
                    display: inline-block;
                    margin-top: 30px;
                    color: #666;
                    text-decoration: none;
                    font-size: 14px;
                }}
                .back-link:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Planning Flow Test - Order {ordernummer}</h1>
                
                <div class="order-info">
                    <div class="info-row">
                        <span class="info-label">Ordernummer</span>
                        <span class="info-value">{ordernummer}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Email</span>
                        <span class="info-value">{email}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Leverdatum</span>
                        <span class="info-value">{datum} {tijdstip}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Betaal Status</span>
                        <span class="info-value">{betaal_status or 'N/A'}</span>
                    </div>
                </div>
                
                <h2 style="font-size:20px;margin-bottom:20px;color:#2d2d2d;">Test Resultaten</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Template</th>
                            <th>Status</th>
                            <th>Error</th>
                        </tr>
                    </thead>
                    <tbody>
                        {results_html}
                    </tbody>
                </table>
                
                <a href="/admin/order/{order_id}?token={SESSION_SECRET}" class="back-link">← Terug naar order detail</a>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij planning flow test: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij planning flow test: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()

@router.get("/debug-artikelen/{order_id}", response_class=JSONResponse)
async def debug_artikelen(order_id: str, verified: bool = Depends(verify_admin_session)):
    """Tijdelijk debug endpoint om artikelen op te halen"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT naam, aantal, prijs_incl 
            FROM order_artikelen 
            WHERE order_id = %s
            ORDER BY id
        """, (order_id,))
        
        artikelen = cur.fetchall()
        return JSONResponse(content={
            "order_id": order_id,
            "artikelen": [
                {
                    "naam": row["naam"],
                    "aantal": int(row["aantal"]),
                    "prijs_incl": float(row["prijs_incl"])
                }
                for row in artikelen
            ]
        })
    except Exception as e:
        _LOG.error(f"Fout bij ophalen artikelen: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            cur.close()
            conn.close()


@router.get("/{order_id}", response_class=HTMLResponse)
async def order_detail(request: Request, order_id: str, verified: bool = Depends(verify_admin_session)):
    """Detail pagina voor een aanvraag"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal order op met contact informatie en partner
        # Totaal wordt berekend uit order_artikelen via subquery
        cur.execute("""
            SELECT 
                o.*,
                COALESCE((
                    SELECT SUM(oa.prijs_incl * oa.aantal)
                    FROM order_artikelen oa
                    WHERE oa.order_id = o.id
                ), 0) as totaal_bedrag,
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
        
        # Haal vorige en volgende order op voor navigatie
        cur.execute("""
            SELECT id FROM orders 
            WHERE created_at < (SELECT created_at FROM orders WHERE id = %s)
            ORDER BY created_at DESC LIMIT 1
        """, (order_id,))
        vorige_order = cur.fetchone()
        vorige_order_id = str(vorige_order.get("id")) if vorige_order else None
        
        cur.execute("""
            SELECT id FROM orders 
            WHERE created_at > (SELECT created_at FROM orders WHERE id = %s)
            ORDER BY created_at ASC LIMIT 1
        """, (order_id,))
        volgende_order = cur.fetchone()
        volgende_order_id = str(volgende_order.get("id")) if volgende_order else None
        
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
            SELECT id, naam, prijs_incl
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
        
        # Bereken totaal excl. reiskosten eerst
        totaal_excl_reiskosten = 0.00
        for artikel in artikelen:
            naam = artikel.get("naam") or artikel.get("artikel_naam") or "-"
            aantal = float(artikel.get("aantal", 0))
            prijs_incl = float(artikel.get("prijs_incl", 0))
            totaal_regel = aantal * prijs_incl
            # Tel alleen mee voor minimum check als het geen reiskosten is
            if naam != "Reiskosten" and naam != "Toeslag":
                totaal_excl_reiskosten += totaal_regel
        
        # Automatische toeslag toevoegen/updaten als totaal < 500
        if totaal_excl_reiskosten < 500:
            benodigde_toeslag = 500 - totaal_excl_reiskosten
            
            # Zoek "Toeslag" artikel
            cur.execute("SELECT id, naam, prijs_incl FROM artikelen WHERE naam = 'Toeslag' AND actief = TRUE LIMIT 1")
            toeslag_artikel = cur.fetchone()
            
            if toeslag_artikel:
                toeslag_artikel_id = str(toeslag_artikel.get("id"))
                toeslag_prijs_incl = float(toeslag_artikel.get("prijs_incl", 1.00))
                # Aantal = benodigde_toeslag (want prijs_incl = €1.00)
                toeslag_aantal = benodigde_toeslag / toeslag_prijs_incl
                
                # Check of Toeslag al bestaat in order_artikelen
                cur.execute("""
                    SELECT id FROM order_artikelen 
                    WHERE order_id = %s AND naam = 'Toeslag'
                    LIMIT 1
                """, (order_id,))
                bestaande_toeslag = cur.fetchone()
                
                if bestaande_toeslag:
                    # Update bestaande toeslag
                    cur.execute("""
                        UPDATE order_artikelen
                        SET aantal = %s
                        WHERE id = %s
                    """, (toeslag_aantal, bestaande_toeslag.get("id")))
                else:
                    # Voeg nieuwe toeslag toe
                    cur.execute("""
                        INSERT INTO order_artikelen (order_id, artikel_id, naam, aantal, prijs_incl)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (order_id, toeslag_artikel_id, "Toeslag", toeslag_aantal, toeslag_prijs_incl))
                
                conn.commit()
                
                # Haal artikelen opnieuw op na toeslag toevoegen/updaten
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
        
        # Build artikelen tabel (na eventuele toeslag toevoegen)
        artikelen_rows = ""
        totaal_prijs = 0.00
        totaal_excl_reiskosten_final = 0.00
        for artikel in artikelen:
            artikel_id = str(artikel.get("id"))
            naam = artikel.get("naam") or artikel.get("artikel_naam") or "-"
            aantal = float(artikel.get("aantal", 0))
            prijs_incl = float(artikel.get("prijs_incl", 0))
            totaal_regel = aantal * prijs_incl
            totaal_prijs += totaal_regel
            # Tel alleen mee voor minimum check als het geen reiskosten is
            if naam != "Reiskosten":
                totaal_excl_reiskosten_final += totaal_regel
            
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
        if order_status != "cancel":
            if order_status in ["draft", "sent"]:
                if order_status == "draft":
                    offerte_knoppen += f'<form method="post" action="/admin/order/{order_id}/verstuur-offerte?token={SESSION_SECRET}" style="display:inline;"><button type="submit" class="btn">Verstuur offerte</button></form>'
                else:
                    offerte_knoppen += f'<form method="post" action="/admin/order/{order_id}/verstuur-offerte?token={SESSION_SECRET}" style="display:inline;"><button type="submit" class="btn">Verstuur gewijzigde offerte</button></form>'
            
            # Bevestigingsknop (alleen als status != 'sale')
            if order_status != "sale":
                offerte_knoppen += f'<form method="post" action="/admin/order/{order_id}/bevestig?token={SESSION_SECRET}" style="display:inline;margin-left:10px;"><button type="submit" class="btn">Bevestig order</button></form>'
            
            # Annuleer knop (alleen als status niet al geannuleerd)
            offerte_knoppen += f'<form method="post" action="/admin/order/{order_id}/annuleer?token={SESSION_SECRET}" style="display:inline;margin-left:10px;"><button type="submit" class="btn" style="background:#dc3545;">Annuleer order</button></form>'
        
        # Factuur knoppen
        factuur_knoppen = ""
        betaal_status = order.get("betaal_status")
        
        # Factuur alleen beschikbaar als order definitief is
        if is_definitief(order):
            # Check of er al een factuur is
            cur.execute("SELECT id FROM facturen WHERE order_id = %s LIMIT 1", (order_id,))
            heeft_factuur = cur.fetchone()
            
            if betaal_status == "betaald":
                # Al betaald, geen wijziging mogelijk
                factuur_knoppen = '<p style="color:#666;">Order al betaald - geen wijzigingen mogelijk</p>'
            elif betaal_status == "factuur_verstuurd" and heeft_factuur:
                # Factuur al verstuurd, toon "nogmaals versturen" knop (wordt dynamisch aangepast via JS)
                factuur_knoppen += f'<form method="post" action="/admin/order/{order_id}/verstuur-factuur-nogmaals?token={SESSION_SECRET}" style="display:inline;" onsubmit="window.factuurVerstuurd = true;"><button type="submit" id="factuur-btn" class="btn">Verstuur factuur nogmaals</button></form>'
            elif not betaal_status or betaal_status == "onbetaald":
                # Nog geen factuur verstuurd, toon normale knop
                if not heeft_factuur:
                    factuur_knoppen += f'<form method="post" action="/admin/order/{order_id}/verstuur-factuur?token={SESSION_SECRET}" style="display:inline;"><button type="submit" id="factuur-btn" class="btn">Verstuur factuur</button></form>'
                else:
                    # Factuur bestaat maar nog niet verstuurd, toon "verstuur factuur" knop
                    factuur_knoppen += f'<form method="post" action="/admin/order/{order_id}/verstuur-factuur?token={SESSION_SECRET}" style="display:inline;"><button type="submit" id="factuur-btn" class="btn">Verstuur factuur</button></form>'
        
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
                .btn.orange {{
                    background: #ff6b35;
                    color: white;
                }}
                .btn.orange:hover {{
                    background: #e55a2b;
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
                    <div style="display:flex;align-items:center;gap:15px;">
                        <div style="display:flex;gap:5px;">
                            <a href="{f'/admin/order/{vorige_order_id}?token={SESSION_SECRET}' if vorige_order_id else '#'}" 
                               class="btn" 
                               style="padding:8px 12px;text-decoration:none;{'pointer-events:none;opacity:0.5;' if not vorige_order_id else ''}"
                               {'onclick="return false;"' if not vorige_order_id else ''}>←</a>
                            <a href="{f'/admin/order/{volgende_order_id}?token={SESSION_SECRET}' if volgende_order_id else '#'}" 
                               class="btn" 
                               style="padding:8px 12px;text-decoration:none;{'pointer-events:none;opacity:0.5;' if not volgende_order_id else ''}"
                               {'onclick="return false;"' if not volgende_order_id else ''}>→</a>
                        </div>
                        <div>
                            <h1>Aanvraag: {order.get('ordernummer', 'N/A')}</h1>
                            {f'<p style="color:#666;margin-top:5px;font-size:14px;">GF Referentie: {order.get("gf_referentie", "-")}</p>' if order.get('gf_referentie') else ''}
                        </div>
                    </div>
                    <div style="display:flex;gap:10px;align-items:center;">
                        <form method="post" action="/admin/order/{order_id}/verwijder?token={SESSION_SECRET}" style="display:inline;" onsubmit="return confirm('Weet je zeker dat je deze order wilt verwijderen? Deze actie kan niet ongedaan worden gemaakt.');">
                            <button type="submit" class="btn" style="background:#dc3545;">Verwijder</button>
                        </form>
                        <button id="save-btn" class="save-btn" disabled>Geen wijzigingen</button>
                    </div>
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
                    <div class="info-item" style="grid-column: 1 / -1;">
                        <div class="info-label">Notitie klant</div>
                        <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Wordt meegestuurd op offerte, bevestiging, factuur en plannings mails</div>
                        <textarea id="notitie_klant" class="editable-field" rows="3" placeholder="Notitie klant">{order.get('notitie_klant') or ''}</textarea>
                    </div>
                    <div class="info-item" style="grid-column: 1 / -1;">
                        <div class="info-label">Notitie partner</div>
                        <div style="font-size: 12px; color: #666; margin-bottom: 4px;">Wordt weergegeven in partner overzicht en portaal</div>
                        <textarea id="notitie_partner" class="editable-field" rows="3" placeholder="Notitie partner">{order.get('notitie_partner') or ''}</textarea>
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
                        <div class="info-value">
                            {f'<span style="background:#dc3545;color:white;padding:4px 8px;border-radius:4px;font-size:12px;">Geannuleerd</span>' if order_status == 'cancel' else order_status}
                        </div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Partner</div>
                        <div class="info-value">{order.get('partner_naam') or 'Niet toegewezen'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Prijs partner incl. BTW</div>
                        <div style="display: flex; gap: 10px; align-items: center;">
                            <input type="number" id="prijs_partner" class="editable-field" value="{order.get('prijs_partner') or ''}" step="0.01" min="0" placeholder="0.00" style="flex: 1;">
                            <button type="button" id="reset-prijs-partner" class="btn" style="padding: 8px 16px; font-size: 14px;">↺ Reset</button>
                        </div>
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
                    const fields = Array.from(document.querySelectorAll('.editable-field'));
                    let hasChanges = false;
                    let factuurVerstuurd = false;
                    // Bereken origineel bedrag uit artikelen tabel (ALLE regels inclusief toeslag en reiskosten)
                    let origineelBedrag = 0;
                    document.querySelectorAll('table tbody tr').forEach(function(row) {{
                        const cells = row.querySelectorAll('td');
                        // Skip de "Totaal" rij
                        const eersteCel = cells[0] ? cells[0].textContent.trim() : '';
                        if (eersteCel === 'Totaal' || eersteCel === '') {{
                            return; // Skip deze rij
                        }}
                        if (cells.length >= 4) {{
                            const totaalCell = cells[3];
                            const totaalText = totaalCell.textContent.trim();
                            if (totaalText.startsWith('€')) {{
                                const bedragText = totaalText.replace('€', '').trim().replace(',', '.');
                                const bedrag = parseFloat(bedragText);
                                if (!isNaN(bedrag)) {{
                                    origineelBedrag += bedrag;
                                }}
                            }}
                        }}
                    }});
                    let huidigBedrag = origineelBedrag;
                    let betaalStatus = '{order.get("betaal_status") or ""}';
                    const orderId = '{order_id}';
                    const token = '{SESSION_SECRET}';

                    if (!saveBtn) {{
                        console.error('Save button niet gevonden');
                        return;
                    }}

                    if (fields.length === 0) {{
                        console.error('Geen editable fields gevonden');
                        return;
                    }}

                    // Expose factuurVerstuurd voor onsubmit handler
                    window.factuurVerstuurd = false;

                    // Functie om factuur knop aan te passen
                    function updateFactuurKnop() {{
                        const factuurBtn = document.getElementById('factuur-btn');
                        if (!factuurBtn) return;
                        
                        if (betaalStatus === 'betaald') {{
                            factuurBtn.textContent = 'Betaald ✓';
                            factuurBtn.className = 'btn';
                            factuurBtn.disabled = true;
                            factuurBtn.style.background = '#28a745';
                            factuurBtn.style.color = 'white';
                        }} else if (betaalStatus === 'factuur_verstuurd' && Math.abs(huidigBedrag - origineelBedrag) >= 0.01) {{
                            factuurBtn.textContent = 'Verstuur aangepaste factuur';
                            factuurBtn.className = 'btn orange';
                            factuurBtn.setAttribute('data-aangepast', 'true');
                            factuurBtn.disabled = false;
                        }} else if (betaalStatus === 'factuur_verstuurd') {{
                            factuurBtn.textContent = 'Verstuur factuur nogmaals';
                            factuurBtn.className = 'btn';
                            factuurBtn.removeAttribute('data-aangepast');
                            factuurBtn.disabled = false;
                        }} else {{
                            factuurBtn.textContent = 'Verstuur factuur';
                            factuurBtn.className = 'btn';
                            factuurBtn.removeAttribute('data-aangepast');
                            factuurBtn.disabled = false;
                        }}
                    }}

                    // Event listener voor factuur knop klik
                    const factuurBtn = document.getElementById('factuur-btn');
                    if (factuurBtn) {{
                        factuurBtn.addEventListener('click', function() {{
                            if (factuurBtn.getAttribute('data-aangepast') === 'true') {{
                                window.factuurVerstuurd = true;
                                factuurBtn.textContent = 'Bezig...';
                                factuurBtn.className = 'btn';
                                factuurBtn.disabled = true;
                            }}
                        }});
                    }}

                    // Check URL parameter voor saved status
                    const urlParams = new URLSearchParams(window.location.search);
                    if (urlParams.get('saved') === '1') {{
                        saveBtn.disabled = false;
                        saveBtn.className = 'save-btn green';
                        saveBtn.textContent = 'Opgeslagen ✓';
                        setTimeout(function() {{
                            saveBtn.disabled = true;
                            saveBtn.className = 'save-btn';
                            saveBtn.textContent = 'Geen wijzigingen';
                        }}, 3000);
                        
                        // Haal nieuw totaal bedrag op na redirect
                        const savedBedrag = sessionStorage.getItem('bedrag_voor_redirect');
                        if (savedBedrag) {{
                            huidigBedrag = parseFloat(savedBedrag);
                            sessionStorage.removeItem('bedrag_voor_redirect');
                            updateFactuurKnop();
                        }} else {{
                            // Haal totaal op via API
                            fetch(window.location.pathname + '/totaal' + window.location.search)
                                .then(function(r) {{ return r.json(); }})
                                .then(function(result) {{
                                    if (result.totaal !== undefined) {{
                                        huidigBedrag = parseFloat(result.totaal);
                                    }} else if (result.totaal_bedrag !== undefined) {{
                                        huidigBedrag = parseFloat(result.totaal_bedrag);
                                    }}
                                    if (result.betaal_status !== undefined) {{
                                        betaalStatus = result.betaal_status;
                                    }}
                                    updateFactuurKnop();
                                }});
                        }}
                    }}
                    
                    // Initialiseer factuur knop status
                    updateFactuurKnop();

                    // Voeg notitie velden toe aan editable fields
                    const notitieKlant = document.getElementById('notitie_klant');
                    const notitiePartner = document.getElementById('notitie_partner');
                    const prijsPartner = document.getElementById('prijs_partner');
                    if (notitieKlant) fields.push(notitieKlant);
                    if (notitiePartner) fields.push(notitiePartner);
                    if (prijsPartner) fields.push(prijsPartner);
                    
                    // Reset prijs partner knop
                    const resetPrijsPartnerBtn = document.getElementById('reset-prijs-partner');
                    console.log('Reset knop gevonden:', resetPrijsPartnerBtn);
                    console.log('Prijs partner veld gevonden:', prijsPartner);
                    
                    if (resetPrijsPartnerBtn && prijsPartner) {{
                        resetPrijsPartnerBtn.addEventListener('click', function(e) {{
                            e.preventDefault();
                            console.log('Reset knop geklikt!');
                            
                            // Bereken totaal uit artikelen tabel op pagina (ALLE regels inclusief toeslag en reiskosten)
                            let totaal = 0;
                            document.querySelectorAll('table tbody tr').forEach(function(row) {{
                                const cells = row.querySelectorAll('td');
                                // Skip de "Totaal" rij (heeft "Totaal" in eerste cel)
                                const eersteCel = cells[0] ? cells[0].textContent.trim() : '';
                                if (eersteCel === 'Totaal' || eersteCel === '') {{
                                    return; // Skip deze rij
                                }}
                                if (cells.length >= 4) {{
                                    const totaalCell = cells[3];
                                    const totaalText = totaalCell.textContent.trim();
                                    if (totaalText.startsWith('€')) {{
                                        // Parse bedrag: vervang komma door punt voor parsing
                                        const bedragText = totaalText.replace('€', '').trim().replace(',', '.');
                                        const bedrag = parseFloat(bedragText);
                                        if (!isNaN(bedrag)) {{
                                            totaal += bedrag;
                                        }}
                                    }}
                                }}
                            }});
                            console.log('Totaal bedrag (uit artikelen tabel, incl. toeslag en reiskosten):', totaal);
                            
                            // Commissie berekening: 15% tot 575, daarna 20%
                            const commissie = (Math.min(totaal, 575) * 0.15) + (Math.max(totaal - 575, 0) * 0.20);
                            console.log('Commissie:', commissie);
                            
                            // Prijs partner = totaal - commissie
                            const nieuwePrijsPartner = Math.round((totaal - commissie) * 100) / 100;
                            console.log('Nieuwe prijs partner:', nieuwePrijsPartner);
                            prijsPartner.value = nieuwePrijsPartner.toFixed(2);
                            
                            // Trigger change event om save knop te activeren
                            prijsPartner.dispatchEvent(new Event('input'));
                            console.log('Input event getriggerd');
                        }});
                    }} else {{
                        console.error('Reset knop of prijs partner veld niet gevonden!');
                        console.error('Reset knop:', resetPrijsPartnerBtn);
                        console.error('Prijs partner:', prijsPartner);
                    }}
                    
                    fields.forEach(function(field) {{
                        field.addEventListener('input', function() {{
                            hasChanges = true;
                            saveBtn.disabled = false;
                            saveBtn.className = 'save-btn orange';
                            saveBtn.textContent = 'Opslaan';
                        }});
                        field.addEventListener('change', function() {{
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
                            opmerkingen: document.getElementById('opmerkingen').value,
                            notitie_klant: document.getElementById('notitie_klant').value,
                            notitie_partner: document.getElementById('notitie_partner').value,
                            prijs_partner: document.getElementById('prijs_partner').value
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
                                
                                // Herbereken huidigBedrag uit artikelen tabel na opslaan
                                huidigBedrag = 0;
                                document.querySelectorAll('table tbody tr').forEach(function(row) {{
                                    const cells = row.querySelectorAll('td');
                                    const eersteCel = cells[0] ? cells[0].textContent.trim() : '';
                                    if (eersteCel === 'Totaal' || eersteCel === '') {{
                                        return;
                                    }}
                                    if (cells.length >= 4) {{
                                        const totaalCell = cells[3];
                                        const totaalText = totaalCell.textContent.trim();
                                        if (totaalText.startsWith('€')) {{
                                            const bedragText = totaalText.replace('€', '').trim().replace(',', '.');
                                            const bedrag = parseFloat(bedragText);
                                            if (!isNaN(bedrag)) {{
                                                huidigBedrag += bedrag;
                                            }}
                                        }}
                                    }}
                                }});
                                
                                // Update factuur knop als bedrag gewijzigd
                                if (Math.abs(huidigBedrag - origineelBedrag) >= 0.01 && betaalStatus === 'factuur_verstuurd') {{
                                    updateFactuurKnop();
                                }}
                                
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
                    
                    // beforeunload check voor factuur update
                    window.addEventListener('beforeunload', function(e) {{
                        if (window.factuurVerstuurd) return;  // al verstuurd
                        if (Math.abs(huidigBedrag - origineelBedrag) < 0.01) return;  // bedrag niet gewijzigd
                        if (betaalStatus !== 'factuur_verstuurd') return;
                        
                        // Verstuur factuur update via sendBeacon
                        const data = JSON.stringify({{trigger: 'pagina_verlaten'}});
                        navigator.sendBeacon(
                            window.location.pathname + '/update-factuur' + window.location.search,
                            data
                        );
                    }});
                    
                    // Expose factuurVerstuurd voor onsubmit handler
                    window.factuurVerstuurd = false;
                    
                    // Automatisch reset prijs_partner als leeg of 0
                    const prijsPartnerVeld = document.getElementById('prijs_partner');
                    if (prijsPartnerVeld) {{
                        const waarde = parseFloat(prijsPartnerVeld.value) || 0;
                        if (waarde === 0) {{
                            const resetBtn = document.getElementById('reset-prijs-partner');
                            if (resetBtn) {{
                                resetBtn.click();
                            }}
                        }}
                    }}
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
        cur.execute("SELECT id, naam, prijs_incl FROM artikelen WHERE id = %s", (artikel_id,))
        artikel = cur.fetchone()
        if not artikel:
            raise HTTPException(status_code=404, detail="Artikel niet gevonden")
        
        # Haal prijs_incl op uit artikelen tabel
        prijs_incl = float(artikel.get("prijs_incl", 0))  # Prijs per stuk
        
        # Voeg artikel toe (alleen prijs_incl, geen berekende velden)
        cur.execute("""
            INSERT INTO order_artikelen (
                order_id, artikel_id, naam, aantal, prijs_incl
            ) VALUES (
                %s, %s, %s, %s, %s
            )
        """, (
            order_id, artikel_id, artikel.get("naam"), aantal, prijs_incl
        ))
        
        # Totaal wordt altijd berekend uit order_artikelen, geen update nodig
        conn.commit()
        
        return RedirectResponse(url=f"/admin/order/{order_id}?saved=1&token={SESSION_SECRET}", status_code=303)
        
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
        
        # Totaal wordt altijd berekend uit order_artikelen, geen update nodig
        conn.commit()
        
        return RedirectResponse(url=f"/admin/order/{order_id}?saved=1&token={SESSION_SECRET}", status_code=303)
        
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
    background_tasks: BackgroundTasks,
    verified: bool = Depends(verify_admin_session)
):
    """Claim order voor Aardappeltuin (contractor_id = 87)"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal order op om status te checken
        cur.execute("""
            SELECT o.status, o.ordernummer, c.email as klant_email, c.naam as klant_naam
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            WHERE o.id = %s
        """, (order_id,))
        order = cur.fetchone()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order niet gevonden")
        
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
        
        # Check of order.status = 'sale' na claimen
        if order.get("status") == "sale":
            # Stuur bevestigingsmail variant B
            klant_email = order.get("klant_email")
            klant_naam = order.get("klant_naam", "")
            ordernummer = order.get("ordernummer", "")
            
            if klant_email:
                voornaam = klant_naam.split()[0] if klant_naam else "klant"
                onderwerp, html = render_bevestiging_b(voornaam)
                
                background_tasks.add_task(
                    stuur_mail,
                    naar=klant_email,
                    onderwerp=onderwerp,
                    inhoud=html,
                    order_id=order_id,
                    template_naam="bevestiging_b"
                )
        
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
        
        klant_naam = order.get("klant_naam", "")
        
        # Haal order_artikelen op
        cur.execute("""
            SELECT oa.naam, oa.aantal, oa.prijs_incl
            FROM order_artikelen oa
            WHERE oa.order_id = %s
            ORDER BY oa.created_at
        """, (order_id,))
        
        order_artikelen = cur.fetchall()
        
        # Bepaal pakket_naam: eerste artikel dat niet 'Reiskosten' of 'Toeslag' is
        pakket_naam = ""
        for artikel in order_artikelen:
            naam = artikel.get("naam", "")
            if naam and naam.lower() not in ["reiskosten", "toeslag"]:
                pakket_naam = naam
                break
        
        # Fallback als geen pakket gevonden
        if not pakket_naam and order_artikelen:
            pakket_naam = order_artikelen[0].get("naam", "Pakket")
        
        # Bereken totaal: SUM(prijs_incl * aantal) uit order_artikelen
        totaal = 0.0
        for artikel in order_artikelen:
            prijs_incl = float(artikel.get("prijs_incl", 0) or 0)
            aantal = float(artikel.get("aantal", 0) or 0)
            totaal += prijs_incl * aantal
        
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
        
        # Bepaal template naam (voor logging)
        order_status = order.get("status", "draft")
        if order_status == "draft":
            template_name = "Verkoop: Offerte verzenden test 2.0"
        else:
            template_name = "Verkoop: Offerte aanpassing verzenden"
        
        # Render template
        template_html = render_offerte_v10(
            voornaam=klant_naam.split()[0] if klant_naam else "klant",
            aantal_personen=order.get("aantal_personen") or 0,
            aantal_kinderen=order.get("aantal_kinderen") or 0,
            datum_str=format_dutch_date(order.get("leverdatum")),
            tijdstip=format_time(order.get("leverdatum")),
            locatie=order.get("plaats") or "",
            pakket_naam=pakket_naam,
            totaal_str=format_currency(totaal),
            bevestig_url=bevestig_link,
        )
        
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
            SELECT 
                o.*,
                COALESCE((
                    SELECT SUM(oa.prijs_incl * oa.aantal)
                    FROM order_artikelen oa
                    WHERE oa.order_id = o.id
                ), 0) as totaal_bedrag,
                c.email as klant_email, 
                c.naam as klant_naam
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
            SELECT id, mollie_payment_id, mollie_checkout_url, factuurnummer, totaal_bedrag
            FROM facturen WHERE order_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (order_id,))
        
        bestaande_factuur = cur.fetchone()
        order_totaal_bedrag = float(order.get("totaal_bedrag", 0))
        klant_email = order.get("klant_email")
        ordernummer = order.get("ordernummer", "")
        ordertype = order.get("ordertype") or "b2c"
        
        if bestaande_factuur:
            # Factuur bestaat al - gebruik update-factuur logica
            factuur_bedrag = float(bestaande_factuur.get("totaal_bedrag", 0))
            mollie_checkout_url = bestaande_factuur.get("mollie_checkout_url")
            factuurnummer = bestaande_factuur.get("factuurnummer", "")
            
            if not klant_email:
                raise HTTPException(status_code=400, detail="Geen email adres gevonden voor klant")
            
            # Vergelijk factuur.bedrag met orders.totaal_bedrag
            if abs(factuur_bedrag - order_totaal_bedrag) >= 0.01:
                # Bedrag ANDERS: cancel oude payment, maak nieuwe aan, update factuur
                update_factuur_bij_orderwijziging(order_id, order_totaal_bedrag, conn, background_tasks)
                conn.commit()
                return RedirectResponse(url=f"/admin/order/{order_id}?token={SESSION_SECRET}", status_code=303)
            else:
                # Bedrag ZELFDE: stuur mail opnieuw met bestaande link
                if not mollie_checkout_url:
                    raise HTTPException(status_code=400, detail="Factuur heeft geen Mollie betaallink")
                
                # Maak mail body
                if ordertype == "b2b":
                    mail_body = f"""
                    <html>
                    <body>
                        <h2>Factuur {factuurnummer}</h2>
                        <p>Beste {order.get('klant_naam', '')},</p>
                        <p>Bij deze ontvangt u de factuur voor uw bestelling {ordernummer}.</p>
                        <p><strong>Te betalen bedrag: € {order_totaal_bedrag:,.2f}</strong></p>
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
                        <p><strong>Te betalen bedrag: € {order_totaal_bedrag:,.2f}</strong></p>
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
                    onderwerp=f"Uw factuur {ordernummer}",
                    inhoud=mail_body,
                    order_id=order_id,
                    template_naam="Factuur"
                )
                
                # Update betaal_status als nog niet verstuurd
                if betaal_status != "factuur_verstuurd":
                    cur.execute("""
                        UPDATE orders
                        SET betaal_status = 'factuur_verstuurd', updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (order_id,))
                    conn.commit()
                
                return RedirectResponse(url=f"/admin/order/{order_id}?token={SESSION_SECRET}", status_code=303)
        
        klant_email = order.get("klant_email")
        if not klant_email:
            raise HTTPException(status_code=400, detail="Geen email adres gevonden voor klant")
        
        # Haal ALTIJD vers bedrag op uit order_artikelen
        cur.execute("""
            SELECT 
                COALESCE(SUM(prijs_incl * aantal), 0) as totaal_bedrag
            FROM order_artikelen
            WHERE order_id = %s
        """, (order_id,))
        vers_order = cur.fetchone()
        if not vers_order:
            raise HTTPException(status_code=404, detail="Order niet gevonden")
        
        vers_bedrag = float(vers_order.get("totaal_bedrag", 0)) if vers_order.get("totaal_bedrag") else 0.00
        # Bereken BTW bedragen on-the-fly (9% BTW)
        vers_bedrag_excl_btw = round(vers_bedrag / 1.09, 2)
        vers_bedrag_btw = round(vers_bedrag - vers_bedrag_excl_btw, 2)
        
        ordernummer = order.get("ordernummer", "")
        ordertype = order.get("ordertype") or "b2c"
        
        # Genereer factuurnummer: FTHINVYYYYMMDDXXXX
        today = datetime.now()
        random_suffix = random.randint(1000, 9999)
        factuurnummer = f"FTHINV{today.strftime('%Y%m%d')}{random_suffix:04d}"
        
        # Maak Mollie payment met vers bedrag
        try:
            payment = create_payment(
                amount=vers_bedrag,
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
        
        # Debug logging
        _LOG.info(f"Nieuwe Mollie payment aangemaakt voor order {order_id}: payment_id={mollie_payment_id}, checkout_url={mollie_checkout_url}")
        print(f"Nieuwe Mollie URL: {mollie_checkout_url}")
        
        # Sla factuur op in database met vers bedrag
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
            vers_bedrag,
            vers_bedrag_excl_btw,
            vers_bedrag_btw,
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
        
        # Verifieer dat checkout URL is opgeslagen
        cur.execute("SELECT mollie_checkout_url FROM facturen WHERE id = %s", (factuur_id,))
        saved_factuur = cur.fetchone()
        if saved_factuur:
            saved_url = saved_factuur.get("mollie_checkout_url")
            _LOG.info(f"Factuur {factuur_id} opgeslagen met checkout_url: {saved_url}")
            if saved_url != mollie_checkout_url:
                _LOG.warning(f"WAARSCHUWING: Opgeslagen URL ({saved_url}) verschilt van nieuwe URL ({mollie_checkout_url})")
                # Gebruik de opgeslagen URL voor mail
                mollie_checkout_url = saved_url if saved_url else mollie_checkout_url
        
        # Maak mail body met vers bedrag
        if ordertype == "b2b":
            mail_body = f"""
            <html>
            <body>
                <h2>Factuur {factuurnummer}</h2>
                <p>Beste {order.get('klant_naam', '')},</p>
                <p>Bij deze ontvangt u de factuur voor uw bestelling {ordernummer}.</p>
                <p><strong>Te betalen bedrag: € {vers_bedrag:,.2f}</strong></p>
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
                <p><strong>Te betalen bedrag: € {vers_bedrag:,.2f}</strong></p>
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


@router.post("/{order_id}/annuleer")
async def annuleer_order(
    request: Request,
    order_id: str,
    verified: bool = Depends(verify_admin_session)
):
    """Annuleer order (zet status naar cancel)"""
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
        
        # Update order status naar cancel
        cur.execute("""
            UPDATE orders
            SET status = 'cancel', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (order_id,))
        
        conn.commit()
        
        return RedirectResponse(url=f"/admin/order/{order_id}?token={SESSION_SECRET}", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij annuleren order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij annuleren order: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{order_id}/verwijder")
async def verwijder_order(
    request: Request,
    order_id: str,
    verified: bool = Depends(verify_admin_session)
):
    """Verwijder order en bijbehorende order_artikelen"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check of order bestaat
        cur.execute("SELECT id FROM orders WHERE id = %s", (order_id,))
        order = cur.fetchone()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order niet gevonden")
        
        # Verwijder order_artikelen eerst (CASCADE zou dit automatisch doen, maar expliciet is beter)
        cur.execute("DELETE FROM order_artikelen WHERE order_id = %s", (order_id,))
        
        # Verwijder order
        cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))
        
        conn.commit()
        
        return RedirectResponse(url=f"/admin?token={SESSION_SECRET}", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij verwijderen order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij verwijderen order: {str(e)}")
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
        notitie_klant = body.get("notitie_klant", "").strip()
        notitie_partner = body.get("notitie_partner", "").strip()
        prijs_partner_str = body.get("prijs_partner", "").strip()
        
        # Parse prijs_partner
        prijs_partner = None
        if prijs_partner_str:
            try:
                prijs_partner = float(prijs_partner_str)
            except (ValueError, TypeError):
                prijs_partner = None
        
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
                notitie_klant = %s,
                notitie_partner = %s,
                prijs_partner = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            plaats if plaats else None,
            leverdatum,
            aantal_personen,
            aantal_kinderen,
            opmerkingen if opmerkingen else None,
            notitie_klant if notitie_klant else None,
            notitie_partner if notitie_partner else None,
            prijs_partner,
            order_id
        ))
        
        conn.commit()
        
        # Haal totaal bedrag op uit order_artikelen
        cur.execute("""
            SELECT COALESCE(SUM(prijs_incl * aantal), 0) as totaal_bedrag
            FROM order_artikelen
            WHERE order_id = %s
        """, (order_id,))
        totaal_result = cur.fetchone()
        totaal_bedrag = float(totaal_result.get("totaal_bedrag", 0)) if totaal_result else 0.00
        
        return JSONResponse(content={"success": True, "totaal_bedrag": totaal_bedrag})
        
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


@router.get("/{order_id}/totaal")
async def get_order_totaal(
    request: Request,
    order_id: str,
    verified: bool = Depends(verify_admin_session)
):
    """Haal totaal bedrag op van order"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                COALESCE((
                    SELECT SUM(oa.prijs_incl * oa.aantal)
                    FROM order_artikelen oa
                    WHERE oa.order_id = o.id
                ), 0) as totaal_bedrag,
                o.betaal_status
            FROM orders o
            WHERE o.id = %s
        """, (order_id,))
        order = cur.fetchone()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order niet gevonden")
        
        totaal_bedrag = float(order.get("totaal_bedrag", 0)) if order.get("totaal_bedrag") else 0.00
        betaal_status = order.get("betaal_status") or ""
        
        return JSONResponse(content={"totaal": totaal_bedrag, "betaal_status": betaal_status})
        
    except HTTPException:
        raise
    except Exception as e:
        _LOG.error(f"Fout bij ophalen totaal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij ophalen totaal: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{order_id}/update-factuur")
async def update_factuur_pagina_verlaten(
    request: Request,
    order_id: str,
    background_tasks: BackgroundTasks,
    verified: bool = Depends(verify_admin_session)
):
    """Update factuur bij pagina verlaten als bedrag gewijzigd is"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal order op met totaal uit order_artikelen
        cur.execute("""
            SELECT 
                COALESCE((
                    SELECT SUM(oa.prijs_incl * oa.aantal)
                    FROM order_artikelen oa
                    WHERE oa.order_id = o.id
                ), 0) as totaal_bedrag,
                o.betaal_status, 
                o.ordernummer, 
                o.ordertype,
                c.email as klant_email, 
                c.naam as klant_naam
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            WHERE o.id = %s
        """, (order_id,))
        
        order = cur.fetchone()
        if not order:
            return JSONResponse(content={"success": False, "detail": "Order niet gevonden"})
        
        betaal_status = order.get("betaal_status")
        if betaal_status != "factuur_verstuurd":
            return JSONResponse(content={"success": False, "detail": "Factuur niet verstuurd"})
        
        # Haal factuur op
        cur.execute("""
            SELECT id, mollie_payment_id, factuurnummer, totaal_bedrag
            FROM facturen
            WHERE order_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (order_id,))
        
        factuur = cur.fetchone()
        if not factuur:
            return JSONResponse(content={"success": False, "detail": "Geen factuur gevonden"})
        
        factuur_bedrag = float(factuur.get("totaal_bedrag", 0))
        order_bedrag = float(order.get("totaal_bedrag", 0))
        
        # Check of bedrag gewijzigd is
        if abs(factuur_bedrag - order_bedrag) < 0.01:
            return JSONResponse(content={"success": False, "detail": "Bedrag niet gewijzigd"})
        
        # Gebruik bestaande update_factuur_bij_orderwijziging functie
        # Deze annuleert oude payment, maakt nieuwe aan en stuurt mail
        update_factuur_bij_orderwijziging(order_id, order_bedrag, conn, background_tasks)
        
        conn.commit()
        
        return JSONResponse(content={"success": True})
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij updaten factuur: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": f"Fout bij updaten factuur: {str(e)}"}
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
        
        # Haal vers bedrag op uit orders tabel
        cur.execute("""
            SELECT o.totaal_bedrag, o.betaal_status, o.ordernummer, o.ordertype,
                   c.email as klant_email, c.naam as klant_naam
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
        
        # Haal vers bedrag uit order
        vers_bedrag = float(order.get("totaal_bedrag", 0)) if order.get("totaal_bedrag") else 0.00
        ordernummer = order.get("ordernummer", "")
        ordertype = order.get("ordertype") or "b2c"
        klant_naam = order.get("klant_naam", "")
        
        # Haal volledige factuur op incl. bedrag en payment ID
        cur.execute("""
            SELECT id, factuurnummer, mollie_checkout_url,
                   mollie_payment_id, totaal_bedrag
            FROM facturen
            WHERE order_id = %s
            ORDER BY created_at DESC LIMIT 1
        """, (order_id,))
        
        factuur = cur.fetchone()
        if not factuur:
            raise HTTPException(status_code=404, 
                detail="Geen factuur gevonden")
        
        factuurnummer = factuur.get("factuurnummer", "")
        factuur_bedrag = float(factuur.get("totaal_bedrag") or 0)
        
        print(f"VERS BEDRAG: {vers_bedrag}")
        print(f"FACTUUR BEDRAG: {factuur_bedrag}")
        
        # Als bedrag gewijzigd: nieuwe Mollie payment
        if abs(vers_bedrag - factuur_bedrag) > 0.01:
            # Haal huidige payment ID op VOOR nieuwe payment
            cur.execute("""
                SELECT mollie_payment_id FROM facturen
                WHERE order_id = %s
                ORDER BY created_at DESC LIMIT 1
            """, (order_id,))
            huidige_factuur = cur.fetchone()
            oud_payment_id = huidige_factuur.get("mollie_payment_id") if huidige_factuur else None
            
            print(f"OUD PAYMENT ID: {oud_payment_id}")
            
            # Nieuwe Mollie payment
            nieuw_payment = create_payment(
                amount=vers_bedrag,
                description=f"Factuur {factuurnummer}",
                redirect_url="https://fth-portaal-production.up.railway.app/betaling/bedankt",
                webhook_url="https://fth-portaal-production.up.railway.app/webhooks/mollie",
                metadata={"order_id": str(order_id)}
            )
            mollie_checkout_url = nieuw_payment["checkout_url"]
            nieuw_payment_id = nieuw_payment["id"]
            
            # Update factuur in DB
            cur.execute("""
                UPDATE facturen 
                SET mollie_payment_id = %s,
                    mollie_checkout_url = %s,
                    totaal_bedrag = %s
                WHERE id = %s
            """, (nieuw_payment_id, mollie_checkout_url, 
                  vers_bedrag, factuur["id"]))
            conn.commit()
            
            # Annuleer oude payment DIRECT na nieuwe payment
            if oud_payment_id:
                try:
                    cancel_payment(oud_payment_id)
                    print(f"Geannuleerd: {oud_payment_id}")
                except Exception as e:
                    print(f"Cancel mislukt (al verlopen): {oud_payment_id} - {e}")
            
            print(f"NIEUWE URL: {mollie_checkout_url}")
            mail_onderwerp = f"Aangepaste factuur {ordernummer}"
        else:
            mollie_checkout_url = factuur.get("mollie_checkout_url")
            mail_onderwerp = f"Factuur {factuurnummer} - {ordernummer}"
            print(f"ZELFDE BEDRAG, oude URL: {mollie_checkout_url}")
        
        if not mollie_checkout_url:
            raise HTTPException(status_code=400, detail="Factuur heeft geen Mollie betaallink")
        
        # Maak mail body met vers bedrag uit orders tabel
        if ordertype == "b2b":
            mail_body = f"""
            <html>
            <body>
                <h2>Factuur {factuurnummer}</h2>
                <p>Beste {klant_naam},</p>
                <p>Bij deze ontvangt u de factuur voor uw bestelling {ordernummer}.</p>
                <p><strong>Te betalen bedrag: € {vers_bedrag:,.2f}</strong></p>
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
                <p>Beste {klant_naam},</p>
                <p>Bij deze ontvangt u de factuur voor uw bestelling {ordernummer}.</p>
                <p><strong>Te betalen bedrag: € {vers_bedrag:,.2f}</strong></p>
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
            onderwerp=mail_onderwerp,
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
