"""
Automatische herinnering email scheduler - verstuurt herinneringen op dag 3, 5 en 7 na offerte versturen.
"""
import os
import logging
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from app.mail import stuur_mail
from app.templates import (
    render_herinnering_3dagen,
    render_herinnering_5dagen,
    render_herinnering_7dagen
)

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


async def check_en_verstuur_herinneringen():
    """Check orders en verstuur automatisch herinneringen op dag 3, 5 en 7 na offerte versturen"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        base_url = get_base_url()
        
        # Verwerk alle dagen in volgorde: 3, 5, 7
        dagen_config = [
            {"dagen": 3, "template_naam": "herinnering_3dagen"},
            {"dagen": 5, "template_naam": "herinnering_5dagen"},
            {"dagen": 7, "template_naam": "herinnering_7dagen"},
        ]
        
        for dag_config in dagen_config:
            dagen = dag_config["dagen"]
            template_naam = dag_config["template_naam"]
            
            # Query voor orders die X dagen geleden een offerte hebben ontvangen
            cur.execute("""
                SELECT 
                    o.id, o.ordernummer, o.bevestig_token,
                    c.naam as voornaam, c.email
                FROM orders o
                LEFT JOIN contacten c ON o.klant_id = c.id
                WHERE o.status = 'sent'
                AND o.bevestig_token IS NOT NULL
                AND c.email IS NOT NULL
                AND EXISTS (
                    SELECT 1 FROM mail_logs ml
                    WHERE ml.order_id = o.id
                    AND ml.template_naam = 'offerte_v10'
                    AND DATE(ml.verzonden_op AT TIME ZONE 'Europe/Amsterdam') = 
                        (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date - INTERVAL '%s days'
                )
                AND NOT EXISTS (
                    SELECT 1 FROM mail_logs ml2
                    WHERE ml2.order_id = o.id
                    AND ml2.template_naam = %s
                    AND DATE(ml2.verzonden_op AT TIME ZONE 'Europe/Amsterdam') = 
                        (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date
                )
            """, (dagen, template_naam))
            
            orders = cur.fetchall()
            
            for order in orders:
                try:
                    order_id = str(order["id"])
                    ordernummer = order.get("ordernummer", "")
                    bevestig_token = order.get("bevestig_token")
                    voornaam = order.get("voornaam", "")
                    email = order.get("email")
                    
                    if not email:
                        _LOG.warning(f"Order {order_id} heeft geen email, skip herinnering")
                        continue
                    
                    if not bevestig_token:
                        _LOG.warning(f"Order {order_id} heeft geen bevestig_token, skip herinnering")
                        continue
                    
                    # Check dubbele verzending
                    if check_duplicate_sending(cur, order_id, template_naam):
                        _LOG.info(f"Order {order_id} heeft al {template_naam} vandaag verstuurd, skip")
                        continue
                    
                    # Genereer bevestiglink
                    bevestiglink = f"{base_url}/bevestig/{bevestig_token}"
                    
                    # Voornaam uit volledige naam (eerste deel)
                    voornaam_clean = voornaam.split(' ')[0] if voornaam else "klant"
                    
                    # Render HTML
                    if dagen == 3:
                        html = render_herinnering_3dagen(voornaam=voornaam_clean, bevestiglink=bevestiglink)
                    elif dagen == 5:
                        html = render_herinnering_5dagen(voornaam=voornaam_clean, bevestiglink=bevestiglink)
                    else:  # dagen == 7
                        html = render_herinnering_7dagen(voornaam=voornaam_clean, bevestiglink=bevestiglink)
                    
                    # Verstuur mail
                    stuur_mail(
                        naar=email,
                        onderwerp="Herinnering: uw offerte — Friettruck-huren.nl",
                        inhoud=html,
                        order_id=order_id,
                        template_naam=template_naam,
                        attachments=None
                    )
                    
                    _LOG.info(f"Herinnering email {template_naam} verstuurd voor order {order_id}")
                    
                except Exception as e:
                    _LOG.error(f"Fout bij herinnering email {template_naam} voor order {order.get('id')}: {e}", exc_info=True)
                    if conn:
                        conn.rollback()
                    continue
        
    except Exception as e:
        _LOG.error(f"Fout bij automatische herinnering check: {e}", exc_info=True)
    finally:
        if conn:
            cur.close()
            conn.close()


async def run_daily_herinnering_check():
    """Run dagelijkse herinnering email check - draait elke 24 uur"""
    while True:
        try:
            await check_en_verstuur_herinneringen()
        except Exception as e:
            _LOG.error(f"Fout in dagelijkse herinnering scheduler: {e}", exc_info=True)
        
        # Wacht 24 uur
        import asyncio
        await asyncio.sleep(24 * 60 * 60)  # 24 uur in seconden
