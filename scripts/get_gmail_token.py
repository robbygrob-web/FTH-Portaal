"""
Script om Gmail OAuth2 refresh token te genereren.
Voert OAuth2 flow uit en print de refresh token voor gebruik in .env
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

# Laad .env bestand
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Gmail API scopes (zowel send als readonly voor inkomende mail)
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly'
]

# OAuth2 credentials uit environment
CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")

if not CLIENT_ID:
    print("ERROR: GMAIL_CLIENT_ID niet gevonden in .env")
    sys.exit(1)

if not CLIENT_SECRET:
    print("ERROR: GMAIL_CLIENT_SECRET niet gevonden in .env")
    sys.exit(1)

# Maak OAuth2 client config dict
client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "redirect_uris": ["http://localhost"]
    }
}

def main():
    """Voer OAuth2 flow uit en print refresh token"""
    print("=" * 60)
    print("Gmail OAuth2 Refresh Token Generator")
    print("=" * 60)
    print(f"\nClient ID: {CLIENT_ID[:30]}...")
    print(f"Scopes: {', '.join(SCOPES)}")
    print("\nDe browser wordt geopend voor autorisatie...")
    print("Log in met: info@friettruck-huren.nl")
    print("=" * 60)
    
    try:
        # Start OAuth2 flow
        flow = InstalledAppFlow.from_client_config(
            client_config,
            SCOPES
        )
        
        # Voer flow uit (opent browser)
        # Probeer verschillende poorten als 8080 bezet is
        ports_to_try = [8080, 8081, 8082, 8083]
        credentials = None
        
        for port in ports_to_try:
            try:
                credentials = flow.run_local_server(
                    port=port,
                    prompt='consent',
                    open_browser=True
                )
                break
            except OSError as e:
                if "10048" in str(e) or "address already in use" in str(e).lower():
                    print(f"Poort {port} is bezet, probeer poort {port + 1}...")
                    continue
                else:
                    raise
        
        if not credentials:
            print("ERROR: Kon geen beschikbare poort vinden")
            sys.exit(1)
        
        # Haal refresh token op
        refresh_token = credentials.refresh_token
        
        if refresh_token:
            print("\n" + "=" * 60)
            print("SUCCESS: Refresh token gegenereerd!")
            print("=" * 60)
            print("\nVoeg deze regel toe aan je .env bestand:")
            print("-" * 60)
            print(f"GMAIL_REFRESH_TOKEN={refresh_token}")
            print("-" * 60)
            print("\nOf kopieer alleen de refresh token:")
            print("-" * 60)
            print(refresh_token)
            print("-" * 60)
            print("\nLet op: Deze refresh token geeft toegang tot Gmail.")
            print("Bewaar deze veilig en deel deze niet!")
            print("=" * 60)
        else:
            print("\nERROR: Geen refresh token ontvangen.")
            print("Probeer opnieuw en zorg dat je 'consent' geeft.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\nERROR: Fout bij OAuth2 flow: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
