"""
Automatische 48u opvolging scheduler - verstuurt beschikbaarheid negatief of bevestiging B na 48 uur.
"""
import os
import logging
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from app.mail import stuur_mail
from app.templates import (
    render_beschikbaarheid_negatief,
    render_bevestiging_b
)

_LOG = logging.getLogger(__name__)


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    return database_url


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


async def check_en_verstuur_opvolging():
    """Check orders en verstuur automatisch opvolging mails na 48 uur bevestiging"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query voor orders die 48 uur geleden bevestigd zijn
        cur.execute("""
            SELECT 
                o.id, o.ordernummer, o.portaal_status,
                c.naam as voornaam, c.email
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            WHERE o.status = 'sale'
            AND c.email IS NOT NULL
            AND EXISTS (
                SELECT 1 FROM mail_logs ml
                WHERE ml.order_id = o.id
                AND ml.template_naam IN ('bevestiging_a', 'bevestiging_b')
                AND ml.verzonden_op AT TIME ZONE 'Europe/Amsterdam' <= 
                    (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam') - INTERVAL '48 hours'
            )
            AND NOT EXISTS (
                SELECT 1 FROM mail_logs ml2
                WHERE ml2.order_id = o.id
                AND ml2.template_naam IN ('beschikbaarheid_negatief', 'opvolging_bevestiging_b')
                AND DATE(ml2.verzonden_op AT TIME ZONE 'Europe/Amsterdam') >= 
                    (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date - INTERVAL '1 day'
            )
        """)
        
        orders = cur.fetchall()
        
        for order in orders:
            try:
                order_id = str(order["id"])
                ordernummer = order.get("ordernummer", "")
                portaal_status = order.get("portaal_status", "")
                voornaam = order.get("voornaam", "")
                email = order.get("email")
                
                if not email:
                    _LOG.warning(f"Order {order_id} heeft geen email, skip opvolging")
                    continue
                
                # Voornaam uit volledige naam (eerste deel)
                voornaam_clean = voornaam.split(' ')[0] if voornaam else "klant"
                
                # Bepaal welke mail te sturen op basis van portaal_status
                if portaal_status in ('nieuw', 'beschikbaar'):
                    # Stuur beschikbaarheid negatief mail
                    html = render_beschikbaarheid_negatief(voornaam=voornaam_clean)
                    onderwerp = "Update over uw aanvraag — Friettruck-huren.nl"
                    template_naam = "beschikbaarheid_negatief"
                elif portaal_status in ('claimed', 'transfer'):
                    # Stuur bevestiging variant B
                    onderwerp, html = render_bevestiging_b(voornaam=voornaam_clean)
                    template_naam = "opvolging_bevestiging_b"
                else:
                    # Skip onbekende status
                    _LOG.info(f"Order {order_id} heeft onbekende portaal_status: {portaal_status}, skip")
                    continue
                
                # Check dubbele verzending
                if check_duplicate_sending(cur, order_id, template_naam):
                    _LOG.info(f"Order {order_id} heeft al {template_naam} vandaag verstuurd, skip")
                    continue
                
                # Verstuur mail
                stuur_mail(
                    naar=email,
                    onderwerp=onderwerp,
                    inhoud=html,
                    order_id=order_id,
                    template_naam=template_naam,
                    attachments=None
                )
                
                _LOG.info(f"Opvolging email {template_naam} verstuurd voor order {order_id}")
                
            except Exception as e:
                _LOG.error(f"Fout bij opvolging email voor order {order.get('id')}: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                continue
        
    except Exception as e:
        _LOG.error(f"Fout bij automatische opvolging check: {e}", exc_info=True)
    finally:
        if conn:
            cur.close()
            conn.close()


async def run_daily_opvolging_check():
    """Run dagelijkse opvolging email check - draait elke 24 uur"""
    while True:
        try:
            await check_en_verstuur_opvolging()
        except Exception as e:
            _LOG.error(f"Fout in dagelijkse opvolging scheduler: {e}", exc_info=True)
        
        # Wacht 24 uur
        import asyncio
        await asyncio.sleep(24 * 60 * 60)  # 24 uur in seconden
