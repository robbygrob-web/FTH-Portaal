"""
Test script voor Gravity Forms webhook endpoint.
Simuleert een Gravity Forms webhook call met dummy data.
"""
import requests
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Laad omgevingsvariabelen
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

import os

def test_gravity_webhook():
    """Test het Gravity Forms webhook endpoint"""
    
    # Haal webhook secret op
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    if not webhook_secret:
        print("FOUT: WEBHOOK_SECRET niet gevonden in .env")
        sys.exit(1)
    
    # Test URL (lokaal of production)
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    if base_url == "http://localhost:8000":
        print("Gebruik lokaal endpoint. Zorg dat FastAPI draait!")
    else:
        print(f"Gebruik production endpoint: {base_url}")
    
    # Voeg token toe als query parameter
    url = f"{base_url}/webhooks/gravity/aanvraag?token={webhook_secret}"
    
    # Dummy Gravity Forms data
    test_data = {
        "email": "test@example.com",
        "name": "Test Bedrijf BV",
        "phone": "+31612345678",
        "street": "Teststraat 123",
        "zip": "1234 AB",
        "city": "Amsterdam",
        "event_date": "2025-04-15 14:00:00",
        "location": "Amsterdam Centrum",
        "aantal_personen": 150,
        "aantal_kinderen": 20,
        "opmerkingen": "Test aanvraag vanuit Gravity Forms webhook test script"
    }
    
    # Headers (token verificatie is uitgeschakeld)
    headers = {
        "Content-Type": "application/json"
    }
    
    print("="*80)
    print("Gravity Forms Webhook Test")
    print("="*80)
    print(f"\nURL: {url}")
    print(f"\nData:")
    print(json.dumps(test_data, indent=2, ensure_ascii=False))
    print("\n" + "="*80)
    
    try:
        # Verstuur request
        response = requests.post(url, headers=headers, json=test_data, timeout=30)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response:")
        
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2, ensure_ascii=False))
        except:
            print(response.text)
        
        if response.status_code == 200:
            print("\n" + "="*80)
            print("SUCCES: Webhook test geslaagd!")
            print("="*80)
            return True
        else:
            print("\n" + "="*80)
            print(f"FOUT: Webhook test gefaald (status {response.status_code})")
            print("="*80)
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n" + "="*80)
        print("FOUT: Kon niet verbinden met endpoint")
        print("Zorg dat FastAPI draait of BASE_URL correct is ingesteld")
        print("="*80)
        return False
    except Exception as e:
        print(f"\nFOUT: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_gravity_webhook()
    sys.exit(0 if success else 1)
