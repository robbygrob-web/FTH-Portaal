"""
Test script dat 6 test-aanvragen naar de Gravity Forms webhook stuurt.
Haalt contactgegevens op uit het laatste record in de contacten tabel.
"""
import requests
import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

# Laad omgevingsvariabelen
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# BASE_URL instelbaar bovenaan script
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# Test orders configuratie
TEST_ORDERS = [
    {
        "pakket": "Frietpakket",
        "personen": 1,
        "kinderen": 0,
        "broodjes": False,
        "drankjes": False,
        "ordertype": "Particulier"
    },
    {
        "pakket": "Verse Friet & Snack",
        "personen": 10,
        "kinderen": 0,
        "broodjes": True,
        "drankjes": True,
        "ordertype": "Particulier"
    },
    {
        "pakket": "Verse Friet & Snacks (onbeperkt)",
        "personen": 40,
        "kinderen": 5,
        "broodjes": False,
        "drankjes": False,
        "ordertype": "Zakelijk"
    },
    {
        "pakket": "Verse Friet, Snacks & Burger (onbeperkt)",
        "personen": 100,
        "kinderen": 10,
        "broodjes": False,
        "drankjes": True,
        "ordertype": "Particulier"
    },
    {
        "pakket": "Frietpakket",
        "personen": 100,
        "kinderen": 20,
        "broodjes": True,
        "drankjes": True,
        "ordertype": "Zakelijk"
    },
    {
        "pakket": "Verse Friet & Snack",
        "personen": 40,
        "kinderen": 0,
        "broodjes": False,
        "drankjes": False,
        "ordertype": "Particulier"
    }
]


def get_last_contact():
    """Haal het laatste contact record op uit de contacten tabel"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("FOUT: DATABASE_URL niet gevonden in .env")
        sys.exit(1)
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal laatste contact op
        cur.execute("""
            SELECT 
                naam, email, telefoon, 
                adres, postcode, stad, land,
                straat
            FROM contacten
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        contact = cur.fetchone()
        cur.close()
        conn.close()
        
        if not contact:
            print("FOUT: Geen contact gevonden in contacten tabel")
            sys.exit(1)
        
        return dict(contact)
    except Exception as e:
        print(f"FOUT: Kon contact niet ophalen: {e}")
        sys.exit(1)


def split_naam(naam):
    """Split naam in voornaam en achternaam"""
    if not naam:
        return ("", "")
    
    parts = naam.split(" ", 1)
    if len(parts) == 2:
        return (parts[0], parts[1])
    else:
        return (parts[0], "")


def get_pakket_prijs(pakket_naam):
    """Haal prijs op voor pakket (placeholder - zou uit artikelen tabel moeten komen)"""
    # Dit zijn geschatte prijzen - in productie zou dit uit de artikelen tabel komen
    prijzen = {
        "Frietpakket": "5.00",
        "Verse Friet & Snack": "7.50",
        "Verse Friet & Snacks (onbeperkt)": "10.50",
        "Verse Friet, Snacks & Burger (onbeperkt)": "11.75"
    }
    return prijzen.get(pakket_naam, "5.00")


def create_payload(contact, order_config):
    """Maak Gravity Forms payload voor één order"""
    voornaam, achternaam = split_naam(contact.get("naam", ""))
    
    # Gebruik adres of straat (adres heeft prioriteit)
    adres = contact.get("adres") or contact.get("straat") or ""
    stad = contact.get("stad") or ""
    postcode = contact.get("postcode") or ""
    land = contact.get("land") or "Nederland"
    
    # Datum en tijd (7 dagen vanaf nu)
    event_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    event_time = "14:00:00"
    
    # Pakket prijs
    pakket_prijs = get_pakket_prijs(order_config["pakket"])
    
    # Veld 69 format: "Pakketnaam|prijs"
    veld_69 = f"{order_config['pakket']}|{pakket_prijs}"
    
    # Veld 79 (broodjes): "Ja graag!|1" of leeg
    veld_79 = "Ja graag!|1" if order_config["broodjes"] else ""
    
    # Veld 44 (drankjes): "Ja graag!|1" of leeg
    veld_44 = "Ja graag!|1" if order_config["drankjes"] else ""
    
    payload = {
        # Contact gegevens
        "21": contact.get("email", ""),  # Email
        "24": contact.get("telefoon", ""),  # Telefoon
        "25": voornaam,  # Voornaam
        "26": achternaam,  # Achternaam
        "28": contact.get("naam", ""),  # Bedrijfsnaam (gebruik volledige naam)
        
        # Adres gegevens
        "29.1": adres,  # Adres
        "29.3": stad,  # Stad
        "29.5": postcode,  # Postcode
        "29.6": land,  # Land
        
        # Datum en tijd
        "48": event_date,  # Datum
        "63": event_time,  # Tijd
        
        # Order gegevens
        "68": str(order_config["personen"]),  # Aantal personen
        "80": str(order_config["kinderen"]),  # Aantal kinderen
        "81": order_config["ordertype"],  # Ordertype (Particulier/Zakelijk)
        "69": veld_69,  # Pakket naam|prijs
        "79": veld_79,  # Broodjes
        "44": veld_44,  # Drankjes
        "31": f"Test order: {order_config['pakket']} voor {order_config['personen']} personen"  # Opmerkingen
    }
    
    return payload


def send_test_order(contact, order_config, order_num):
    """Stuur één test order naar de webhook"""
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    if not webhook_secret:
        print("FOUT: WEBHOOK_SECRET niet gevonden in .env")
        sys.exit(1)
    
    url = f"{BASE_URL}/webhooks/gravity/aanvraag?token={webhook_secret}"
    payload = create_payload(contact, order_config)
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"\n{'='*80}")
    print(f"Order {order_num}: {order_config['pakket']}")
    print(f"{'='*80}")
    print(f"Personen: {order_config['personen']}, Kinderen: {order_config['kinderen']}")
    print(f"Broodjes: {'Ja' if order_config['broodjes'] else 'Nee'}, Drankjes: {'Ja' if order_config['drankjes'] else 'Nee'}")
    print(f"Ordertype: {order_config['ordertype']}")
    print(f"\nURL: {url}")
    print(f"\nPayload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response:")
        
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2, ensure_ascii=False))
            
            # Log ordernummer als succesvol
            if response.status_code == 200 and "ordernummer" in response_json:
                print(f"\n✓ Ordernummer: {response_json.get('ordernummer', 'N/A')}")
            else:
                print(f"\n✗ Fout: {response_json.get('detail', 'Onbekende fout')}")
        except:
            print(response.text)
        
        return response.status_code == 200
        
    except requests.exceptions.ConnectionError:
        print(f"\n✗ FOUT: Kon niet verbinden met endpoint")
        print(f"Zorg dat FastAPI draait of BASE_URL correct is ingesteld ({BASE_URL})")
        return False
    except Exception as e:
        print(f"\n✗ FOUT: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Hoofdfunctie"""
    print("="*80)
    print("Gravity Forms Webhook Test Script")
    print("="*80)
    print(f"\nBASE_URL: {BASE_URL}")
    
    # Haal contactgegevens op
    print("\nHaal contactgegevens op uit database...")
    contact = get_last_contact()
    print(f"Contact gevonden: {contact.get('naam', 'N/A')} ({contact.get('email', 'N/A')})")
    
    # Stuur 6 test orders
    print(f"\nStuur {len(TEST_ORDERS)} test orders naar webhook...")
    
    results = []
    for i, order_config in enumerate(TEST_ORDERS, 1):
        success = send_test_order(contact, order_config, i)
        results.append({
            "order_num": i,
            "pakket": order_config["pakket"],
            "success": success
        })
    
    # Samenvatting
    print(f"\n{'='*80}")
    print("SAMENVATTING")
    print(f"{'='*80}")
    
    success_count = sum(1 for r in results if r["success"])
    print(f"\nTotaal orders: {len(results)}")
    print(f"Succesvol: {success_count}")
    print(f"Gefaald: {len(results) - success_count}")
    
    print(f"\nDetails:")
    for result in results:
        status = "✓" if result["success"] else "✗"
        print(f"  {status} Order {result['order_num']}: {result['pakket']}")
    
    print(f"\n{'='*80}")
    
    return success_count == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
