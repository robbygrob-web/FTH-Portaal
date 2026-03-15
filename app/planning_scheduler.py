"""
Automatische planning email scheduler - verstuurt planning emails op dag 9, 7, 5, 3 en 1 voor leverdatum.
"""
import os
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
from app.mail import stuur_mail
from app.templates import (
    render_planning_9dagen,
    render_planning_7dagen,
    render_planning_5dagen_betaald,
    render_planning_5dagen_onbetaald,
    render_planning_3dagen_betaald,
    render_planning_3dagen_onbetaald,
    render_planning_1dag_betaald,
    render_planning_1dag_onbetaald,
    format_dutch_date,
    format_time,
    format_currency
)
from app.factuur import generate_factuur_pdf

_LOG = logging.getLogger(__name__)


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    return database_url


def get_base_url() -> str:
    """Haal BASE_URL op uit environment, fallback naar hardcoded URL"""
    base_url = os.getenv("BASE_URL")
    if not base_url:
        base_url = "https://fth-portaal-production.up.railway.app"
    return base_url.rstrip('/')


def check_duplicate_sending(cur, order_id: str, template_naam: str) -> bool:
    """
    Check of deze template al vandaag verstuurd is voor deze order.
    Returns True als dubbele verzending, False als OK om te versturen.
    """
    cur.execute("""
        SELECT COUNT(*) as count
        FROM mail_logs
        WHERE order_id = %s
        AND template_naam = %s
        AND DATE(verzonden_op AT TIME ZONE 'Europe/Amsterdam') = (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date
    """, (order_id, template_naam))
    
    result = cur.fetchone()
    return result['count'] > 0 if result else False


def get_pakket_naam(cur, order_id: str) -> str:
    """
    Haal pakket naam op uit order_artikelen, exclusief reiskosten, toeslag, broodjes, drankjes, kids pakket.
    Returns eerste artikel naam of fallback.
    """
    cur.execute("""
        SELECT naam
        FROM order_artikelen
        WHERE order_id = %s
        AND LOWER(naam) NOT IN ('reiskosten', 'toeslag', 'broodjes', 'drankjes', 'kids pakket')
        ORDER BY id
        LIMIT 1
    """, (order_id,))
    
    result = cur.fetchone()
    if result and result['naam']:
        return result['naam']
    
    # Fallback: eerste artikel (ook exclusief reiskosten etc.)
    cur.execute("""
        SELECT naam
        FROM order_artikelen
        WHERE order_id = %s
        AND LOWER(naam) NOT IN ('reiskosten', 'toeslag', 'broodjes', 'drankjes', 'kids pakket')
        ORDER BY id
        LIMIT 1
    """, (order_id,))
    
    result = cur.fetchone()
    return result['naam'] if result else "Pakket"


def get_broodjes_ja_nee(cur, order_id: str) -> str:
    """
    Check of broodjes aanwezig zijn in order_artikelen.
    Returns "Ja" of "Nee".
    """
    cur.execute("""
        SELECT COUNT(*) as count
        FROM order_artikelen
        WHERE order_id = %s
        AND LOWER(naam) = 'broodjes'
    """, (order_id,))
    
    result = cur.fetchone()
    return "Ja" if result and result['count'] > 0 else "Nee"


def get_drankjes_ja_nee(cur, order_id: str) -> str:
    """
    Check of drankjes aanwezig zijn in order_artikelen.
    Returns "Ja" of "Nee".
    """
    cur.execute("""
        SELECT COUNT(*) as count
        FROM order_artikelen
        WHERE order_id = %s
        AND LOWER(naam) = 'drankjes'
    """, (order_id,))
    
    result = cur.fetchone()
    return "Ja" if result and result['count'] > 0 else "Nee"


def get_partner_telefoon(cur, contractor_id) -> str:
    """
    Haal partner telefoon op uit contacten via contractor_id.
    Fallback naar bedrijfstelefoon als contractor_id NULL of telefoon leeg.
    """
    if not contractor_id:
        return "085-212 7601"  # Fallback naar bedrijfstelefoon
    
    cur.execute("""
        SELECT telefoon
        FROM contacten
        WHERE id = %s
    """, (contractor_id,))
    
    result = cur.fetchone()
    telefoon = result['telefoon'] if result else None
    
    if not telefoon or telefoon.strip() == "":
        return "085-212 7601"  # Fallback naar bedrijfstelefoon
    
    return telefoon


def get_totaal_bedrag(cur, order_id: str) -> Decimal:
    """
    Bereken totaal bedrag via SUM(prijs_incl * aantal) FROM order_artikelen.
    Returns Decimal.
    """
    cur.execute("""
        SELECT SUM(prijs_incl * aantal) as totaal
        FROM order_artikelen
        WHERE order_id = %s
    """, (order_id,))
    
    result = cur.fetchone()
    totaal = result['totaal'] if result else Decimal('0')
    return Decimal(str(totaal)) if totaal else Decimal('0')


def generate_afmeld_token(cur, order_id: str, conn) -> str:
    """
    Genereer UUID token voor afmeldlink en sla op in orders.planning_afmeld_token.
    Returns token string.
    """
    token = str(uuid.uuid4())
    
    cur.execute("""
        UPDATE orders
        SET planning_afmeld_token = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (token, order_id))
    
    conn.commit()
    return token


async def check_en_verstuur_planning_emails():
    """Check orders en verstuur automatisch planning emails op dag 9, 7, 5, 3 en 1 voor leverdatum"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        base_url = get_base_url()
        
        # Verwerk alle dagen in volgorde: 9, 7, 5, 3, 1
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
            
            # Bereken target datum
            target_date = (datetime.now() + timedelta(days=dagen)).date()
            
            # Query voor betaalde orders
            if dagen in [5, 3, 1]:
                cur.execute("""
                    SELECT 
                        o.id, o.ordernummer, o.leverdatum, o.plaats, 
                        o.aantal_personen, o.aantal_kinderen, o.contractor_id,
                        o.planning_afmeld_token, o.betaal_status,
                        c.voornaam, c.email
                    FROM orders o
                    LEFT JOIN contacten c ON o.klant_id = c.id
                    WHERE o.status = 'sale'
                    AND (o.leverdatum AT TIME ZONE 'Europe/Amsterdam')::date = %s
                    AND o.planning_afgemeld = FALSE
                    AND o.betaal_status = 'betaald'
                    AND c.email IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM mail_logs ml 
                        WHERE ml.order_id = o.id 
                        AND ml.template_naam = %s
                        AND DATE(ml.verzonden_op AT TIME ZONE 'Europe/Amsterdam') = (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date
                    )
                """, (target_date, f"{template_base}_betaald"))
                
                orders_betaald = cur.fetchall()
                
                for order in orders_betaald:
                    try:
                        order_id = str(order["id"])
                        ordernummer = order.get("ordernummer", "")
                        leverdatum = order.get("leverdatum")
                        plaats = order.get("plaats", "")
                        aantal_personen = order.get("aantal_personen", 0)
                        aantal_kinderen = order.get("aantal_kinderen", 0)
                        contractor_id = order.get("contractor_id")
                        planning_afmeld_token = order.get("planning_afmeld_token")
                        voornaam = order.get("voornaam", "")
                        email = order.get("email")
                        
                        if not email:
                            _LOG.warning(f"Order {order_id} heeft geen email, skip planning email")
                            continue
                        
                        # Check dubbele verzending
                        if check_duplicate_sending(cur, order_id, f"{template_base}_betaald"):
                            _LOG.info(f"Order {order_id} heeft al {template_base}_betaald vandaag verstuurd, skip")
                            continue
                        
                        # Haal data op
                        pakket = get_pakket_naam(cur, order_id)
                        partner_telefoon = get_partner_telefoon(cur, contractor_id)
                        totaal_bedrag = get_totaal_bedrag(cur, order_id)
                        totaal_str = f"€ {format_currency(totaal_bedrag)}"
                        datum = format_dutch_date(leverdatum) if leverdatum else ""
                        tijdstip = format_time(leverdatum) if leverdatum else ""
                        
                        # Token generatie (alleen dag 5)
                        if heeft_token and not planning_afmeld_token:
                            planning_afmeld_token = generate_afmeld_token(cur, order_id, conn)
                        
                        afmeldlink = f"{base_url}/planning/afmelden/{planning_afmeld_token}" if planning_afmeld_token else ""
                        
                        # Render HTML
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
                            afmeldlink=afmeldlink
                        ) if dagen == 5 else (
                            render_planning_3dagen_betaald(
                                voornaam=voornaam,
                                aantal_personen=aantal_personen,
                                aantal_kinderen=aantal_kinderen,
                                pakket=pakket,
                                locatie=plaats,
                                datum=datum,
                                tijdstip=tijdstip,
                                totaal=totaal_str,
                                partner_telefoon=partner_telefoon,
                                afmeldlink=afmeldlink
                            ) if dagen == 3 else render_planning_1dag_betaald(
                                voornaam=voornaam,
                                aantal_personen=aantal_personen,
                                aantal_kinderen=aantal_kinderen,
                                pakket=pakket,
                                locatie=plaats,
                                datum=datum,
                                tijdstip=tijdstip,
                                totaal=totaal_str,
                                partner_telefoon=partner_telefoon,
                                afmeldlink=afmeldlink
                            )
                        )
                        
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
                        
                        # Verstuur mail
                        stuur_mail(
                            naar=email,
                            onderwerp=f"Nog {dagen} {'dag' if dagen == 1 else 'dagen'} tot uw friettruck-feest!",
                            inhoud=html,
                            order_id=order_id,
                            template_naam=f"{template_base}_betaald",
                            attachments=attachments if attachments else None
                        )
                        
                        _LOG.info(f"Planning email {template_base}_betaald verstuurd voor order {order_id}")
                        
                    except Exception as e:
                        _LOG.error(f"Fout bij planning email {template_base}_betaald voor order {order.get('id')}: {e}", exc_info=True)
                        if conn:
                            conn.rollback()
                        continue
            
            # Query voor onbetaalde orders (alleen dag 5, 3, 1)
            if dagen in [5, 3, 1]:
                cur.execute("""
                    SELECT 
                        o.id, o.ordernummer, o.leverdatum, o.plaats, 
                        o.aantal_personen, o.aantal_kinderen, o.contractor_id,
                        f.mollie_checkout_url as betaallink,
                        c.voornaam, c.email
                    FROM orders o
                    LEFT JOIN contacten c ON o.klant_id = c.id
                    LEFT JOIN facturen f ON f.order_id = o.id
                    WHERE o.status = 'sale'
                    AND (o.leverdatum AT TIME ZONE 'Europe/Amsterdam')::date = %s
                    AND o.planning_afgemeld = FALSE
                    AND (o.betaal_status IS NULL OR o.betaal_status != 'betaald')
                    AND c.email IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM mail_logs ml 
                        WHERE ml.order_id = o.id 
                        AND ml.template_naam = %s
                        AND DATE(ml.verzonden_op AT TIME ZONE 'Europe/Amsterdam') = (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date
                    )
                """, (target_date, f"{template_base}_onbetaald"))
                
                orders_onbetaald = cur.fetchall()
                
                for order in orders_onbetaald:
                    try:
                        order_id = str(order["id"])
                        ordernummer = order.get("ordernummer", "")
                        leverdatum = order.get("leverdatum")
                        plaats = order.get("plaats", "")
                        aantal_personen = order.get("aantal_personen", 0)
                        aantal_kinderen = order.get("aantal_kinderen", 0)
                        contractor_id = order.get("contractor_id")
                        betaallink = order.get("betaallink", "")
                        voornaam = order.get("voornaam", "")
                        email = order.get("email")
                        
                        if not email:
                            _LOG.warning(f"Order {order_id} heeft geen email, skip planning email")
                            continue
                        
                        # Check dubbele verzending
                        if check_duplicate_sending(cur, order_id, f"{template_base}_onbetaald"):
                            _LOG.info(f"Order {order_id} heeft al {template_base}_onbetaald vandaag verstuurd, skip")
                            continue
                        
                        # Haal data op
                        pakket = get_pakket_naam(cur, order_id)
                        partner_telefoon = get_partner_telefoon(cur, contractor_id)
                        totaal_bedrag = get_totaal_bedrag(cur, order_id)
                        totaal_str = f"€ {format_currency(totaal_bedrag)}"
                        datum = format_dutch_date(leverdatum) if leverdatum else ""
                        tijdstip = format_time(leverdatum) if leverdatum else ""
                        
                        # Render HTML
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
                            betaallink=betaallink
                        ) if dagen == 5 else (
                            render_planning_3dagen_onbetaald(
                                voornaam=voornaam,
                                aantal_personen=aantal_personen,
                                aantal_kinderen=aantal_kinderen,
                                pakket=pakket,
                                locatie=plaats,
                                datum=datum,
                                tijdstip=tijdstip,
                                totaal=totaal_str,
                                partner_telefoon=partner_telefoon,
                                betaallink=betaallink
                            ) if dagen == 3 else render_planning_1dag_onbetaald(
                                voornaam=voornaam,
                                aantal_personen=aantal_personen,
                                aantal_kinderen=aantal_kinderen,
                                pakket=pakket,
                                locatie=plaats,
                                datum=datum,
                                tijdstip=tijdstip,
                                totaal=totaal_str,
                                partner_telefoon=partner_telefoon,
                                betaallink=betaallink
                            )
                        )
                        
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
                        
                        # Verstuur mail
                        stuur_mail(
                            naar=email,
                            onderwerp=f"Nog {dagen} {'dag' if dagen == 1 else 'dagen'} tot uw friettruck-feest!",
                            inhoud=html,
                            order_id=order_id,
                            template_naam=f"{template_base}_onbetaald",
                            attachments=attachments if attachments else None
                        )
                        
                        _LOG.info(f"Planning email {template_base}_onbetaald verstuurd voor order {order_id}")
                        
                    except Exception as e:
                        _LOG.error(f"Fout bij planning email {template_base}_onbetaald voor order {order.get('id')}: {e}", exc_info=True)
                        if conn:
                            conn.rollback()
                        continue
            
            # Query voor dag 9 en 7 (geen betaal_status check)
            if dagen in [9, 7]:
                query = """
                    SELECT 
                        o.id, o.ordernummer, o.leverdatum, o.plaats, 
                        o.aantal_personen, o.aantal_kinderen, o.contractor_id,
                        c.voornaam, c.email
                    FROM orders o
                    LEFT JOIN contacten c ON o.klant_id = c.id
                    WHERE o.status = 'sale'
                    AND (o.leverdatum AT TIME ZONE 'Europe/Amsterdam')::date = %s
                    AND o.planning_afgemeld = FALSE
                    AND c.email IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM mail_logs ml 
                        WHERE ml.order_id = o.id 
                        AND ml.template_naam = %s
                        AND DATE(ml.verzonden_op AT TIME ZONE 'Europe/Amsterdam') = (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date
                    )
                """
                
                if dagen == 7:
                    query += """
                    AND EXISTS (
                        SELECT 1 FROM facturen f WHERE f.order_id = o.id
                    )
                    """
                
                cur.execute(query, (target_date, template_base))
                
                orders = cur.fetchall()
                
                for order in orders:
                    try:
                        order_id = str(order["id"])
                        ordernummer = order.get("ordernummer", "")
                        leverdatum = order.get("leverdatum")
                        plaats = order.get("plaats", "")
                        aantal_personen = order.get("aantal_personen", 0)
                        aantal_kinderen = order.get("aantal_kinderen", 0)
                        contractor_id = order.get("contractor_id")
                        voornaam = order.get("voornaam", "")
                        email = order.get("email")
                        
                        if not email:
                            _LOG.warning(f"Order {order_id} heeft geen email, skip planning email")
                            continue
                        
                        # Check dubbele verzending
                        if check_duplicate_sending(cur, order_id, template_base):
                            _LOG.info(f"Order {order_id} heeft al {template_base} vandaag verstuurd, skip")
                            continue
                        
                        # Haal data op
                        pakket = get_pakket_naam(cur, order_id)
                        partner_telefoon = get_partner_telefoon(cur, contractor_id)
                        totaal_bedrag = get_totaal_bedrag(cur, order_id)
                        totaal_str = f"€ {format_currency(totaal_bedrag)}"
                        datum = format_dutch_date(leverdatum) if leverdatum else ""
                        tijdstip = format_time(leverdatum) if leverdatum else ""
                        
                        # Broodjes/drankjes (alleen dag 9)
                        broodjes_ja_nee = ""
                        drankjes_ja_nee = ""
                        if heeft_broodjes_drankjes:
                            broodjes_ja_nee = get_broodjes_ja_nee(cur, order_id)
                            drankjes_ja_nee = get_drankjes_ja_nee(cur, order_id)
                        
                        # Betaallink (alleen dag 7)
                        betaallink = ""
                        if dagen == 7:
                            cur.execute("""
                                SELECT mollie_checkout_url
                                FROM facturen
                                WHERE order_id = %s
                                LIMIT 1
                            """, (order_id,))
                            factuur_result = cur.fetchone()
                            betaallink = factuur_result['mollie_checkout_url'] if factuur_result else ""
                        
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
                                partner_telefoon=partner_telefoon
                            )
                        else:  # dag 7
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
                                betaallink=betaallink
                            )
                        
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
                        
                        # Verstuur mail
                        stuur_mail(
                            naar=email,
                            onderwerp=f"Nog {dagen} dagen tot uw friettruck-feest!",
                            inhoud=html,
                            order_id=order_id,
                            template_naam=template_base,
                            attachments=attachments if attachments else None
                        )
                        
                        _LOG.info(f"Planning email {template_base} verstuurd voor order {order_id}")
                        
                    except Exception as e:
                        _LOG.error(f"Fout bij planning email {template_base} voor order {order.get('id')}: {e}", exc_info=True)
                        if conn:
                            conn.rollback()
                        continue
        
    except Exception as e:
        _LOG.error(f"Fout bij automatische planning email check: {e}", exc_info=True)
    finally:
        if conn:
            cur.close()
            conn.close()


async def run_daily_planning_check():
    """Run dagelijkse planning email check - draait elke 24 uur"""
    while True:
        try:
            await check_en_verstuur_planning_emails()
        except Exception as e:
            _LOG.error(f"Fout in dagelijkse planning scheduler: {e}", exc_info=True)
        
        # Wacht 24 uur
        import asyncio
        await asyncio.sleep(24 * 60 * 60)  # 24 uur in seconden
