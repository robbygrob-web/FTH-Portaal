"""
Mail verzending functionaliteit via Gmail API (OAuth2).
Ondersteunt mail verzending en automatische logging in mail_logs tabel.
"""
import os
import logging
import uuid
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional
import psycopg2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

_LOG = logging.getLogger(__name__)

# Gmail API configuratie
GMAIL_FROM_EMAIL = "info@friettruck-huren.nl"
GMAIL_FROM_NAME = "FTH Portaal"
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


def get_gmail_credentials():
    """
    Haal Gmail OAuth2 credentials op uit environment variabelen.
    Gebruikt refresh token flow voor service-to-service authenticatie.
    """
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
    
    if not client_id:
        raise ValueError("GMAIL_CLIENT_ID niet gevonden in environment variabelen")
    if not client_secret:
        raise ValueError("GMAIL_CLIENT_SECRET niet gevonden in environment variabelen")
    if not refresh_token:
        raise ValueError("GMAIL_REFRESH_TOKEN niet gevonden in environment variabelen")
    
    # Maak credentials object met refresh token
    credentials = Credentials(
        token=None,  # Wordt automatisch ververst
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )
    
    # Verfris token als nodig
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
    
    return credentials


def get_gmail_service():
    """
    Maak Gmail API service object met OAuth2 credentials.
    """
    credentials = get_gmail_credentials()
    service = build('gmail', 'v1', credentials=credentials)
    return service


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
        email_van: Email adres afzender (default: GMAIL_FROM_EMAIL)
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
            email_van = GMAIL_FROM_EMAIL
        
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


def create_message(to: str, subject: str, body: str, html: bool = True) -> dict:
    """
    Maak een Gmail API message object.
    
    Args:
        to: Email adres ontvanger
        subject: Email onderwerp
        body: Email inhoud (HTML of tekst)
        html: Of de inhoud HTML is (default: True)
    
    Returns:
        dict met 'raw' key die base64 encoded message bevat
    """
    message_id = f"<{uuid.uuid4()}@friettruck-huren.nl>"
    
    # Maak email bericht
    msg = MIMEMultipart('alternative')
    msg['From'] = f"{GMAIL_FROM_NAME} <{GMAIL_FROM_EMAIL}>"
    msg['To'] = to
    msg['Subject'] = subject
    msg['Message-ID'] = message_id
    
    # Voeg inhoud toe
    if html:
        msg.attach(MIMEText(body, 'html', 'utf-8'))
    else:
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    # Encode naar base64url format (Gmail API vereist)
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
    
    return {
        'raw': raw_message,
        'message_id': message_id
    }


def stuur_mail(
    naar: str,
    onderwerp: str,
    inhoud: str,
    order_id: Optional[str] = None,
    template_naam: Optional[str] = None,
    html: bool = True
) -> dict:
    """
    Stuur een email via Gmail API (OAuth2) en log in mail_logs tabel.
    
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
    message_id = None
    
    try:
        # Maak Gmail service
        service = get_gmail_service()
        
        # Maak email message
        message_data = create_message(naar, onderwerp, inhoud, html)
        message_id = message_data['message_id']
        
        # Verzend via Gmail API
        _LOG.info(f"Verzenden mail naar {naar} via Gmail API")
        
        message = service.users().messages().send(
            userId='me',
            body={'raw': message_data['raw']}
        ).execute()
        
        gmail_message_id = message.get('id')
        _LOG.info(f"Mail succesvol verzonden naar {naar} (Gmail ID: {gmail_message_id})")
        
        # Log succesvolle verzending in database
        log_id = log_mail_to_db(
            naar=naar,
            onderwerp=onderwerp,
            inhoud=inhoud,
            status="verzonden",
            order_id=order_id,
            template_naam=template_naam,
            email_van=GMAIL_FROM_EMAIL,
            message_id=message_id,
            heeft_fout=False
        )
        
        return {
            "success": True,
            "message_id": message_id,
            "log_id": str(log_id) if log_id else None,
            "error": None
        }
        
    except HttpError as e:
        error_msg = f"Gmail API fout: {str(e)}"
        _LOG.error(f"Mail verzending gefaald naar {naar}: {error_msg}")
        
        # Log gefaalde verzending in database
        log_id = log_mail_to_db(
            naar=naar,
            onderwerp=onderwerp,
            inhoud=inhoud,
            status="mislukt",
            order_id=order_id,
            template_naam=template_naam,
            email_van=GMAIL_FROM_EMAIL,
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
            email_van=GMAIL_FROM_EMAIL,
            message_id=message_id,
            heeft_fout=True
        )
        
        return {
            "success": False,
            "message_id": message_id,
            "log_id": str(log_id) if log_id else None,
            "error": error_msg
        }
