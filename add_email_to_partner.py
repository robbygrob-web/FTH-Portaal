"""Script om emailadres toe te voegen aan partner"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Laad omgevingsvariabelen uit .env bestand VOOR imports
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

from app.odoo_client import get_odoo_client

def add_email_to_partner(partner_id=1374, email="info@bluebikesdelft.nl"):
    """Voeg emailadres toe aan partner"""
    print("=" * 60)
    print(f"Emailadres toevoegen aan partner {partner_id}")
    print("=" * 60)
    
    try:
        client = get_odoo_client()
        print(f"\n[OK] OdooClient geïnitialiseerd")
        
        # Stap 1: Haal huidige partner gegevens op
        print(f"\n1. Ophalen partner {partner_id}...")
        partner = client.execute_kw(
            "res.partner",
            "read",
            [partner_id],
            {"fields": ["id", "name", "email", "is_company"]}
        )
        
        if not partner:
            print(f"   [FOUT] Partner {partner_id} niet gevonden")
            return None
        
        partner_data = partner[0]
        print(f"   [OK] Partner gevonden: {partner_data.get('name', 'N/A')}")
        print(f"   - Huidig email: {partner_data.get('email', 'Geen email')}")
        print(f"   - Is bedrijf: {partner_data.get('is_company', False)}")
        
        # Stap 2: Update partner met emailadres
        print(f"\n2. Emailadres toevoegen: {email}...")
        result = client.execute_kw(
            "res.partner",
            "write",
            [partner_id],
            {"email": email}
        )
        
        if result:
            print(f"   [OK] Emailadres toegevoegd")
        else:
            print(f"   [FOUT] Kon emailadres niet toevoegen")
            return None
        
        # Stap 3: Verifieer de update
        print(f"\n3. Verifiëren update...")
        updated_partner = client.execute_kw(
            "res.partner",
            "read",
            [partner_id],
            {"fields": ["id", "name", "email"]}
        )
        
        if updated_partner:
            print(f"   [OK] Partner gegevens:")
            print(f"   - Naam: {updated_partner[0].get('name', 'N/A')}")
            print(f"   - Email: {updated_partner[0].get('email', 'Geen email')}")
        
        print("\n" + "=" * 60)
        print("SUCCES: Emailadres toegevoegd")
        print("=" * 60)
        print(f"\nPartner ID: {partner_id}")
        print(f"Naam: {partner_data.get('name', 'N/A')}")
        print(f"Email: {email}")
        
        return {
            "partner_id": partner_id,
            "name": partner_data.get('name'),
            "email": email
        }
        
    except Exception as e:
        print(f"\n[FOUT] Onverwachte fout: {type(e).__name__}: {e}")
        import traceback
        print("\nTraceback:")
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Voeg email toe aan bedrijf BlueBikes Delft (ID 1374)
    result = add_email_to_partner(partner_id=1374, email="info@bluebikesdelft.nl")
    sys.exit(0 if result else 1)
