"""Test script om leverancier te veranderen"""
import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """Test of de server draait"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def check_current_supplier(po_id):
    """Controleer huidige leverancier van een inkooporder"""
    try:
        response = requests.get(f"{BASE_URL}/check-po255", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Fout bij ophalen huidige leverancier: {e}")
        return None

def test_change_supplier(po_id, nieuwe_partner_id):
    """Test het wijzigen van leverancier"""
    try:
        url = f"{BASE_URL}/test-change-supplier/{po_id}/{nieuwe_partner_id}"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "Fout", "status_code": response.status_code, "bericht": response.text}
    except Exception as e:
        return {"status": "Fout", "foutmelding": str(e)}

if __name__ == "__main__":
    print("=" * 60)
    print("Test: Leverancier wijzigen")
    print("=" * 60)
    
    # Wacht tot server klaar is
    print("\n1. Controleren of server draait...")
    max_attempts = 10
    for i in range(max_attempts):
        if test_health():
            print("   [OK] Server is actief")
            break
        else:
            print(f"   Wachten op server... ({i+1}/{max_attempts})")
            time.sleep(2)
    else:
        print("   [FOUT] Server niet bereikbaar na 20 seconden")
        print("   Zorg ervoor dat de server draait: uvicorn main:app --reload")
        exit(1)
    
    # Test parameters
    po_id = 255
    nieuwe_partner_id = 87
    
    # Stap 1: Controleer huidige leverancier
    print(f"\n2. Huidige leverancier van inkooporder {po_id} ophalen...")
    huidige_status = check_current_supplier(po_id)
    if huidige_status:
        print(f"   Status: {huidige_status.get('status')}")
        print(f"   Huidige partner_id: {huidige_status.get('huidige_partner_id')}")
        print(f"   Partner naam: {huidige_status.get('partner_naam', 'N/A')}")
    
    # Stap 2: Wijzig leverancier
    print(f"\n3. Leverancier wijzigen naar partner_id {nieuwe_partner_id}...")
    result = test_change_supplier(po_id, nieuwe_partner_id)
    
    # Stap 3: Toon resultaat
    print("\n4. Resultaat:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Stap 4: Verifieer wijziging
    print(f"\n5. Verificatie: Huidige leverancier na wijziging...")
    time.sleep(1)
    nieuwe_status = check_current_supplier(po_id)
    if nieuwe_status:
        print(f"   Status: {nieuwe_status.get('status')}")
        print(f"   Nieuwe partner_id: {nieuwe_status.get('huidige_partner_id')}")
        print(f"   Partner naam: {nieuwe_status.get('partner_naam', 'N/A')}")
        
        if nieuwe_status.get('huidige_partner_id') == nieuwe_partner_id:
            print("\n   [SUCCES] TEST GESLAAGD: Leverancier succesvol gewijzigd!")
        else:
            print(f"\n   [FOUT] TEST MISLUKT: Verwacht {nieuwe_partner_id}, gekregen {nieuwe_status.get('huidige_partner_id')}")
    
    print("\n" + "=" * 60)
