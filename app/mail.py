"""
Mail verzending functionaliteit via Gmail SMTP.
Ondersteunt mail verzending en automatische logging in mail_logs tabel.
"""
import os
import logging
import smtplib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional
import psycopg2

_LOG = logging.getLogger(__name__)

# Gmail SMTP configuratie
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_FROM_EMAIL = "info@friettruck-huren.nl"
SMTP_FROM_NAME = "FTH Portaal"


def get_smtp_config():
    """Haal SMTP configuratie op uit environment"""
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_user:
        raise ValueError("SMTP_USER niet gevonden in environment variabelen")
    if not smtp_password:
        raise ValueError("SMTP_PASSWORD niet gevonden in environment variabelen")
    
    return {
        "user": smtp_user,
        "password": smtp_password,
        "server": SMTP_SERVER,
        "port": SMTP_PORT,
        "from_email": SMTP_FROM_EMAIL,
        "from_name": SMTP_FROM_NAME
    }


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    return database_url


def log_mail_to_db(
    naar: str,
    onderwerp: str,
    inhoud: str,
    status: str,
    order_id: Optional[str] = None,
    template_naam: Optional[str] = None,
    email_van: Optional[str] = None,
    message_id: Optional[str] = None,
    heeft_fout: bool = False,
    preview: Optional[str] = None
):
    """
    Log mail verzending in mail_logs tabel.
    
    Args:
        naar: Email adres ontvanger
        onderwerp: Email onderwerp
        inhoud: Email inhoud (HTML of tekst)
        status: 'verzonden', 'mislukt', 'ontvangen'
        order_id: Optionele UUID van gerelateerde order
        template_naam: Optionele naam van gebruikte template
        email_van: Email adres afzender (default: SMTP_FROM_EMAIL)
        message_id: Optionele Message-ID header
        heeft_fout: Of er een fout is opgetreden
        preview: Eerste regels van bericht voor preview
    """
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        # Genereer preview (eerste 200 karakters)
        if not preview:
            # Strip HTML tags voor preview
            import re
            text_content = re.sub(r'<[^>]+>', '', inhoud)
            preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
        
        # Genereer message_id als niet opgegeven
        if not message_id:
            message_id = f"<{uuid.uuid4()}@friettruck-huren.nl>"
        
        # Bepaal email_van
        if not email_van:
            email_van = SMTP_FROM_EMAIL
        
        # Bepaal verzonden_op op basis van status
        verzonden_op = datetime.now() if status == "verzonden" else None
        
        cur.execute("""
            INSERT INTO mail_logs (
                richting, kanaal, naar, onderwerp, inhoud, email_van,
                message_id, order_id, template_naam, status,
                bericht_type, heeft_fout, preview, verzonden_op
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            "uitgaand",  # richting
            "mail",  # kanaal
            naar,
            onderwerp,
            inhoud,
            email_van,
            message_id,
            order_id,
            template_naam,
            status,
            "email_outgoing",  # bericht_type
            heeft_fout,
            preview,
            verzonden_op
        ))
        
        log_id = cur.fetchone()[0]
        conn.commit()
        
        cur.close()
        conn.close()
        
        _LOG.info(f"Mail gelogd in database: {log_id} (naar: {naar}, status: {status})")
        return log_id
        
    except Exception as e:
        _LOG.error(f"Fout bij loggen mail in database: {e}", exc_info=True)
        # Fail silently - mail logging mag mail verzending niet blokkeren
        return None


def stuur_mail(
    naar: str,
    onderwerp: str,
    inhoud: str,
    order_id: Optional[str] = None,
    template_naam: Optional[str] = None,
    html: bool = True
) -> dict:
    """
    Stuur een email via Gmail SMTP en log in mail_logs tabel.
    
    Args:
        naar: Email adres ontvanger
        onderwerp: Email onderwerp
        inhoud: Email inhoud (HTML of tekst)
        order_id: Optionele UUID van gerelateerde order
        template_naam: Optionele naam van gebruikte template
        html: Of de inhoud HTML is (default: True)
    
    Returns:
        dict met status en details:
        {
            "success": bool,
            "message_id": str,
            "log_id": str (UUID),
            "error": str (als success=False)
        }
    """
    config = get_smtp_config()
    message_id = f"<{uuid.uuid4()}@friettruck-huren.nl>"
    
    try:
        # Maak email bericht
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{config['from_name']} <{config['from_email']}>"
        msg['To'] = naar
        msg['Subject'] = onderwerp
        msg['Message-ID'] = message_id
        
        # Voeg inhoud toe
        if html:
            msg.attach(MIMEText(inhoud, 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(inhoud, 'plain', 'utf-8'))
        
        # Verzend via SMTP
        _LOG.info(f"Verzenden mail naar {naar} via {config['server']}:{config['port']}")
        
        with smtplib.SMTP(config['server'], config['port']) as server:
            server.starttls()  # Start TLS encryptie
            server.login(config['user'], config['password'])
            server.send_message(msg)
        
        _LOG.info(f"Mail succesvol verzonden naar {naar}")
        
        # Log succesvolle verzending in database
        log_id = log_mail_to_db(
            naar=naar,
            onderwerp=onderwerp,
            inhoud=inhoud,
            status="verzonden",
            order_id=order_id,
            template_naam=template_naam,
            email_van=config['from_email'],
            message_id=message_id,
            heeft_fout=False
        )
        
        return {
            "success": True,
            "message_id": message_id,
            "log_id": str(log_id) if log_id else None,
            "error": None
        }
        
    except smtplib.SMTPException as e:
        error_msg = f"SMTP fout: {str(e)}"
        _LOG.error(f"Mail verzending gefaald naar {naar}: {error_msg}")
        
        # Log gefaalde verzending in database
        log_id = log_mail_to_db(
            naar=naar,
            onderwerp=onderwerp,
            inhoud=inhoud,
            status="mislukt",
            order_id=order_id,
            template_naam=template_naam,
            email_van=config.get('from_email'),
            message_id=message_id,
            heeft_fout=True
        )
        
        return {
            "success": False,
            "message_id": message_id,
            "log_id": str(log_id) if log_id else None,
            "error": error_msg
        }
        
    except Exception as e:
        error_msg = f"Onverwachte fout: {str(e)}"
        _LOG.error(f"Mail verzending gefaald naar {naar}: {error_msg}", exc_info=True)
        
        # Log gefaalde verzending in database
        log_id = log_mail_to_db(
            naar=naar,
            onderwerp=onderwerp,
            inhoud=inhoud,
            status="mislukt",
            order_id=order_id,
            template_naam=template_naam,
            email_van=config.get('from_email'),
            message_id=message_id,
            heeft_fout=True
        )
        
        return {
            "success": False,
            "message_id": message_id,
            "log_id": str(log_id) if log_id else None,
            "error": error_msg
        }
