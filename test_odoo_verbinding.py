"""Test script om Odoo verbinding te testen"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Laad omgevingsvariabelen uit .env bestand VOOR imports
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

from app.config import (
    ODOO_BASE_URL, ODOO_DB, ODOO_LOGIN, ODOO_API_KEY,
    validate_odoo_config
)
from app.odoo_client import get_odoo_client
from fastapi import HTTPException

def test_odoo_verbinding():
    """Test de Odoo verbinding"""
    print("=" * 60)
    print("Test: Odoo Verbinding")
    print("=" * 60)
    
    # Controleer omgevingsvariabelen
    print("\n0. Controleren omgevingsvariabelen...")
    is_valid, missing_vars = validate_odoo_config()
    
    # Toon configuratie waarden
    config_vars = {
        "ODOO_BASE_URL": ODOO_BASE_URL,
        "ODOO_DB": ODOO_DB,
        "ODOO_LOGIN": ODOO_LOGIN,
        "ODOO_API_KEY": ODOO_API_KEY,
    }
    
    for var, value in config_vars.items():
        if value:
            # Verberg gevoelige informatie
            if "KEY" in var or "PASSWORD" in var:
                display_value = "*" * min(len(value), 10) + "..." if len(value) > 10 else "*" * len(value)
            else:
                display_value = value
            print(f"   [OK] {var}: {display_value}")
        else:
            print(f"   [FOUT] {var}: NIET INGESTELD")
    
    if not is_valid:
        print(f"\n   [FOUT] Ontbrekende variabelen: {', '.join(missing_vars)}")
        print("   Zorg ervoor dat deze variabelen zijn ingesteld:")
        print("   - Lokaal: in het .env bestand")
        print("   - Railway: als omgevingsvariabelen in Railway dashboard")
        return False
    
    # Check .env bestand
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        print(f"\n   [INFO] .env bestand gevonden: {env_path}")
    else:
        print(f"\n   [INFO] .env bestand niet gevonden, gebruikt omgevingsvariabelen uit systeem")
    
    try:
        print("\n1. Initialiseren van OdooClient...")
        client = get_odoo_client()
        print(f"   [OK] OdooClient geïnitialiseerd")
        print(f"   - URL: {client.url}")
        print(f"   - Database: {client.db}")
        print(f"   - Gebruiker: {client.username}")
        print(f"   - User ID: {client.uid}")
        
        print("\n2. Test query uitvoeren (ophalen van gebruikersinformatie)...")
        user_info = client.execute_kw(
            'res.users',
            'read',
            [client.uid],
            {'fields': ['name', 'login', 'email']}
        )
        if user_info:
            print(f"   [OK] Query succesvol uitgevoerd")
            print(f"   - Gebruiker: {user_info[0].get('name', 'N/A')}")
            print(f"   - Login: {user_info[0].get('login', 'N/A')}")
            print(f"   - Email: {user_info[0].get('email', 'N/A')}")
        else:
            print("   [WAARSCHUWING] Query uitgevoerd maar geen resultaat")
        
        print("\n3. Test query: Aantal inkooporders ophalen...")
        po_count = client.execute_kw(
            'purchase.order',
            'search_count',
            [[('id', '>', 0)]]
        )
        print(f"   [OK] Aantal inkooporders: {po_count}")
        
        print("\n" + "=" * 60)
        print("[SUCCES] Odoo verbinding werkt correct!")
        print("=" * 60)
        return True
        
    except RuntimeError as e:
        print(f"\n   [FOUT] Runtime fout: {e}")
        error_msg = str(e)
        if "login mislukt" in error_msg.lower():
            print("\n   Mogelijke oorzaken:")
            print("   - Onjuiste gebruikersnaam of API key")
            print("   - Database naam is incorrect")
            print("   - Odoo server is niet bereikbaar")
            print("   - Gebruiker heeft geen toegang tot de database")
        elif "omgevingsvariabelen ontbreken" in error_msg.lower():
            print("\n   Zorg ervoor dat alle omgevingsvariabelen zijn ingesteld in het .env bestand")
        return False
    
    except HTTPException as e:
        print(f"\n   [FOUT] HTTP fout: {e.status_code} - {e.detail}")
        if e.status_code == 502:
            print("\n   Mogelijke oorzaken:")
            print("   - Odoo server is niet bereikbaar")
            print("   - Onjuiste ODOO_BASE_URL")
            print("   - Firewall of netwerkproblemen")
        elif e.status_code == 504:
            print("\n   Odoo server reageert te traag (timeout)")
        return False
        
    except Exception as e:
        print(f"\n   [FOUT] Onverwachte fout: {type(e).__name__}: {e}")
        import traceback
        print("\n   Traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_odoo_verbinding()
    sys.exit(0 if success else 1)
