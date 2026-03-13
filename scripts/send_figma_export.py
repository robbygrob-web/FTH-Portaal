"""
Script om figma_export.html te mailen als bijlage.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Laad .env bestand
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Voeg project root toe aan path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64
import uuid
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def get_gmail_credentials():
    """Haal Gmail OAuth2 credentials op uit environment variabelen."""
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
    
    if not client_id:
        raise ValueError("GMAIL_CLIENT_ID niet gevonden in environment variabelen")
    if not client_secret:
        raise ValueError("GMAIL_CLIENT_SECRET niet gevonden in environment variabelen")
    if not refresh_token:
        raise ValueError("GMAIL_REFRESH_TOKEN niet gevonden in environment variabelen")
    
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=['https://www.googleapis.com/auth/gmail.send']
    )
    
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
    
    return credentials

def create_message_with_attachment(to: str, subject: str, body: str, attachment_path: Path) -> dict:
    """Maak een Gmail API message object met bijlage."""
    message_id = f"<{uuid.uuid4()}@friettruck-huren.nl>"
    
    # Maak email bericht
    msg = MIMEMultipart()
    msg['From'] = "FTH Portaal <info@friettruck-huren.nl>"
    msg['To'] = to
    msg['Subject'] = subject
    msg['Message-ID'] = message_id
    
    # Voeg body toe
    msg.attach(MIMEText(body, 'html', 'utf-8'))
    
    # Voeg bijlage toe
    with open(attachment_path, 'rb') as f:
        attachment = MIMEBase('application', 'octet-stream')
        attachment.set_payload(f.read())
    
    encoders.encode_base64(attachment)
    attachment.add_header(
        'Content-Disposition',
        f'attachment; filename= {attachment_path.name}'
    )
    msg.attach(attachment)
    
    # Encode naar base64url format (Gmail API vereist)
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
    
    return {
        'raw': raw_message,
        'message_id': message_id
    }

def send_email_with_attachment(to: str, subject: str, body: str, attachment_path: Path):
    """Verstuur email met bijlage via Gmail API."""
    try:
        credentials = get_gmail_credentials()
        service = build('gmail', 'v1', credentials=credentials)
        
        # Maak message met bijlage
        message_data = create_message_with_attachment(to, subject, body, attachment_path)
        
        # Verzend via Gmail API
        print(f"Verzenden email naar {to}...")
        message = service.users().messages().send(
            userId='me',
            body={'raw': message_data['raw']}
        ).execute()
        
        print(f"Email succesvol verzonden! (Gmail ID: {message.get('id')})")
        return True
        
    except HttpError as e:
        print(f"Gmail API fout: {e}")
        return False
    except Exception as e:
        print(f"Fout bij verzenden email: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Bestandspad
    html_file = project_root / "docs" / "figma_export.html"
    
    if not html_file.exists():
        print(f"Fout: Bestand niet gevonden: {html_file}")
        sys.exit(1)
    
    # Email gegevens
    to_email = "doreen.j.dunkel@gmail.com"
    subject = "FTH Portaal - Figma Export HTML"
    body = """
    <html>
    <body>
        <h2>FTH Portaal - Figma Export</h2>
        <p>Beste Doreen,</p>
        <p>Hierbij ontvang je het HTML export bestand voor Figma van het FTH Partner Portaal.</p>
        <p>Het bestand bevat alle pagina's van het portaal als secties:</p>
        <ul>
            <li>Login pagina</li>
            <li>Login error pagina</li>
            <li>Onboarding form</li>
            <li>Contract pagina</li>
            <li>Dashboard</li>
            <li>Partner Orders tabel</li>
        </ul>
        <p>Je kunt dit bestand gebruiken met de HTML-to-Figma plugin in Figma.</p>
        <p>Groet,<br>FTH Portaal</p>
    </body>
    </html>
    """
    
    # Verstuur email
    success = send_email_with_attachment(to_email, subject, body, html_file)
    
    if success:
        print(f"\nEmail succesvol verzonden naar {to_email}")
    else:
        print(f"\nFout bij verzenden email naar {to_email}")
        sys.exit(1)
