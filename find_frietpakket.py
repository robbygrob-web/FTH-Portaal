"""Script om Frietpakket product te vinden"""
import sys
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

from app.odoo_client import get_odoo_client

def find_frietpakket():
    """Zoek naar Frietpakket producten"""
    try:
        client = get_odoo_client()
        
        print("Zoeken naar producten met 'pakket' in de naam...")
        products = client.execute_kw(
            "product.product",
            "search_read",
            [("name", "ilike", "pakket")],
            {"fields": ["id", "name", "list_price"], "limit": 50}
        )
        
        if products:
            print(f"\n{len(products)} product(en) gevonden met 'pakket':")
            for p in products:
                print(f"  - ID {p['id']}: {p['name']} (€{p.get('list_price', 0)})")
        else:
            print("Geen producten met 'pakket' gevonden.")
        
        print("\nZoeken naar alle producten met 'friet'...")
        all_products = client.execute_kw(
            "product.product",
            "search_read",
            [("name", "ilike", "friet")],
            {"fields": ["id", "name", "list_price"], "limit": 100}
        )
        
        print(f"\n{len(all_products)} product(en) gevonden met 'friet':")
        for p in all_products[:20]:  # Toon eerste 20
            print(f"  - ID {p['id']}: {p['name']} (€{p.get('list_price', 0)})")
        
        return products if products else all_products
        
    except Exception as e:
        print(f"Fout: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    find_frietpakket()
