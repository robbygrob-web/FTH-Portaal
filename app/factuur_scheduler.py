"""
Automatische factuur scheduler - verstuurt facturen 7 dagen voor leverdatum.
"""
import os
import logging
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from app.mollie_client import create_payment
from app.mail import stuur_mail
import random

_LOG = logging.getLogger(__name__)


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    return database_url


async def check_en_verstuur_facturen():
    """Check orders en verstuur automatisch facturen 7 dagen voor leverdatum"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Bereken datum 7 dagen vanaf nu
        target_date = datetime.now().date() + timedelta(days=7)
        
        # Zoek orders waar:
        # - status = 'sale' (bevestigd)
        # - leverdatum is over 7 dagen
        # - betaal_status IS NULL of 'onbetaald'
        # - nog geen factuur verstuurd
        cur.execute("""
            SELECT 
                o.id, o.ordernummer, o.klant_id, o.totaal_bedrag, 
                o.bedrag_excl_btw, o.bedrag_btw, o.ordertype,
                c.email as klant_email, c.naam as klant_naam
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            WHERE o.status = 'sale'
            AND o.leverdatum::date = %s
            AND (o.betaal_status IS NULL OR o.betaal_status = 'onbetaald')
            AND NOT EXISTS (
                SELECT 1 FROM facturen f WHERE f.order_id = o.id
            )
            AND c.email IS NOT NULL
        """, (target_date,))
        
        orders = cur.fetchall()
        
        if not orders:
            _LOG.info(f"Geen orders gevonden voor automatische factuur op {target_date}")
            return
        
        _LOG.info(f"Gevonden {len(orders)} orders voor automatische factuur op {target_date}")
        
        for order in orders:
            try:
                order_id = str(order["id"])
                ordernummer = order.get("ordernummer", "")
                totaal_bedrag = float(order.get("totaal_bedrag", 0))
                ordertype = order.get("ordertype") or "b2c"
                klant_email = order.get("klant_email")
                klant_naam = order.get("klant_naam", "")
                
                if not klant_email:
                    _LOG.warning(f"Order {order_id} heeft geen email, skip factuur")
                    continue
                
                # Genereer factuurnummer
                today = datetime.now()
                random_suffix = random.randint(1000, 9999)
                factuurnummer = f"FTHINV{today.strftime('%Y%m%d')}{random_suffix:04d}"
                
                # Maak Mollie payment
                payment = create_payment(
                    amount=totaal_bedrag,
                    description=f"Factuur {ordernummer}",
                    redirect_url="https://fth-portaal-production.up.railway.app/betaling/bedankt",
                    webhook_url="https://fth-portaal-production.up.railway.app/webhooks/mollie",
                    metadata={"order_id": order_id}
                )
                
                mollie_payment_id = payment["id"]
                mollie_checkout_url = payment["checkout_url"]
                
                # Sla factuur op
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
                    "posted",
                    "not_paid",
                    "Invoice",
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
                        <p>Beste {klant_naam},</p>
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
                        <p>Beste {klant_naam},</p>
                        <p>Bij deze ontvangt u de factuur voor uw bestelling {ordernummer}.</p>
                        <p><strong>Te betalen bedrag: € {totaal_bedrag:,.2f}</strong></p>
                        <p>U kunt betalen via de onderstaande betaallink:</p>
                        <p><a href="{mollie_checkout_url}" style="background:#fec82a;color:#333;padding:12px 24px;text-decoration:none;border-radius:8px;display:inline-block;font-weight:bold;">Betaal nu</a></p>
                        <p>Met vriendelijke groet,<br>FTH Portaal</p>
                    </body>
                    </html>
                    """
                
                # Verstuur mail
                stuur_mail(
                    naar=klant_email,
                    onderwerp=f"Factuur {factuurnummer} - {ordernummer}",
                    inhoud=mail_body,
                    order_id=order_id,
                    template_naam="Factuur"
                )
                
                _LOG.info(f"Automatische factuur verstuurd voor order {order_id} - Factuur {factuurnummer}")
                
            except Exception as e:
                _LOG.error(f"Fout bij automatische factuur voor order {order.get('id')}: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                continue
        
    except Exception as e:
        _LOG.error(f"Fout bij automatische factuur check: {e}", exc_info=True)
    finally:
        if conn:
            cur.close()
            conn.close()


async def run_daily_factuur_check():
    """Run dagelijkse factuur check - draait elke 24 uur"""
    while True:
        try:
            await check_en_verstuur_facturen()
        except Exception as e:
            _LOG.error(f"Fout in dagelijkse factuur scheduler: {e}", exc_info=True)
        
        # Wacht 24 uur
        import asyncio
        await asyncio.sleep(24 * 60 * 60)  # 24 uur in seconden
