"""Script om nieuw contact en aanvraag aan te maken in Odoo"""
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Laad omgevingsvariabelen uit .env bestand VOOR imports
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

from app.odoo_client import get_odoo_client
from fastapi import HTTPException

def create_contact_and_aanvraag():
    """Maak nieuw contact en aanvraag aan in Odoo"""
    print("=" * 60)
    print("Aanmaken nieuw contact en aanvraag in Odoo")
    print("=" * 60)
    
    try:
        client = get_odoo_client()
        print(f"\n[OK] OdooClient geïnitialiseerd")
        
        # Stap 1: Maak bedrijf aan (res.partner met is_company=True)
        print("\n1. Aanmaken bedrijf 'BlueBikes Delft'...")
        company_values = {
            "name": "BlueBikes Delft",
            "is_company": True,
            "customer_rank": 1,  # Markeer als klant
        }
        
        # Voor create: geef waarden als lijst met één dict door
        # execute_kw maakt er automatisch [[values]] van voor Odoo
        company_id_result = client.execute_kw(
            "res.partner",
            "create",
            [company_values],
            None
        )
        # execute_kw geeft een lijst terug voor create, pak het eerste element
        company_id = company_id_result[0] if isinstance(company_id_result, list) else company_id_result
        print(f"   [OK] Bedrijf aangemaakt met ID: {company_id}")
        
        # Stap 2: Maak contactpersoon aan (res.partner met is_company=False)
        print("\n2. Aanmaken contactpersoon 'Laurens Schouten'...")
        contact_values = {
            "name": "Laurens Schouten",
            "is_company": False,
            "parent_id": company_id,  # Koppel aan bedrijf
        }
        
        contact_id_result = client.execute_kw(
            "res.partner",
            "create",
            [contact_values],
            None
        )
        # execute_kw geeft een lijst terug voor create, pak het eerste element
        contact_id = contact_id_result[0] if isinstance(contact_id_result, list) else contact_id_result
        print(f"   [OK] Contactpersoon aangemaakt met ID: {contact_id}")
        
        # Stap 3: Zoek product "Frietpakket"
        print("\n3. Zoeken naar product 'Frietpakket'...")
        products = client.execute_kw(
            "product.product",
            "search_read",
            [("name", "ilike", "Frietpakket")],
            {"fields": ["id", "name", "list_price"], "limit": 10}
        )
        
        if not products:
            print("   [WAARSCHUWING] Geen product 'Frietpakket' gevonden. Zoek naar alternatief...")
            # Zoek naar producten met "friet" in de naam
            products = client.execute_kw(
                "product.product",
                "search_read",
                [("name", "ilike", "friet")],
                {"fields": ["id", "name", "list_price"], "limit": 10}
            )
        
        if not products:
            print("   [FOUT] Geen geschikt product gevonden. Maak handmatig een order line aan.")
            product_id = None
        else:
            product_id = products[0]["id"]
            print(f"   [OK] Product gevonden: {products[0]['name']} (ID: {product_id})")
        
        # Stap 4: Maak order lines aan
        order_lines = []
        if product_id:
            # Frietpakket x300
            order_lines.append((0, 0, {
                "product_id": product_id,
                "product_uom_qty": 300,
                "price_unit": products[0].get("list_price", 0),
            }))
        
        # Stap 5: Maak sale.order aan
        print("\n4. Aanmaken sale.order (aanvraag)...")
        
        # Datum: 14 maart 2025, tijd: 13:00 - 16:00
        commitment_date = "2025-03-14 13:00:00"
        date_order = "2025-03-14 13:00:00"
        
        order_values = {
            "partner_id": company_id,  # Klant: BlueBikes Delft
            "date_order": date_order,
            "commitment_date": commitment_date,
            "x_studio_plaats": "Delft",
            "x_studio_aantal_personen": 300,  # Maximum aantal personen
            "x_studio_selection_field_67u_1jj77rtf7": "nieuw",  # Status: aanvraag (nieuw)
            "state": "draft",  # Draft status (nog geen sent/sale)
            "note": "Seizoensopening en ride-out\nDatum: 14 maart 2025\nTijd: 13:00 - 16:00\nLocatie: Delft\nAantal personen: 100-300 (300 als maximum)\nBestelling: Frietpakket x300, geen snacks, geen drinken, wel saus\nNotitie: Klant wil zelf kosten dekken, offerte gevraagd",
        }
        
        # Voeg order lines toe als product gevonden is
        if order_lines:
            order_values["order_line"] = order_lines
        
        order_id_result = client.execute_kw(
            "sale.order",
            "create",
            [order_values],
            None
        )
        # execute_kw geeft een lijst terug voor create, pak het eerste element
        order_id = order_id_result[0] if isinstance(order_id_result, list) else order_id_result
        print(f"   [OK] Sale order aangemaakt met ID: {order_id}")
        
        # Stap 6: Bevestig de aangemaakte records
        print("\n" + "=" * 60)
        print("SUCCES: Records aangemaakt")
        print("=" * 60)
        print(f"\nContactpersoon ID: {contact_id}")
        print(f"Bedrijf ID: {company_id}")
        print(f"Sale Order ID: {order_id}")
        print(f"\nDetails:")
        print(f"  - Contact: Laurens Schouten")
        print(f"  - Bedrijf: BlueBikes Delft")
        print(f"  - Aanvraag: {order_id}")
        print(f"  - Status: nieuw (aanvraag)")
        print(f"  - Datum: 14 maart 2025, 13:00 - 16:00")
        print(f"  - Locatie: Delft")
        print(f"  - Aantal personen: 300")
        
        return {
            "contact_id": contact_id,
            "company_id": company_id,
            "order_id": order_id
        }
        
    except HTTPException as e:
        print(f"\n[FOUT] HTTP fout: {e.status_code} - {e.detail}")
        return None
        
    except Exception as e:
        print(f"\n[FOUT] Onverwachte fout: {type(e).__name__}: {e}")
        import traceback
        print("\nTraceback:")
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = create_contact_and_aanvraag()
    sys.exit(0 if result else 1)
