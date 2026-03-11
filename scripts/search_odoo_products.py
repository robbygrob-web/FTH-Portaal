"""
Script om producten te zoeken in Odoo met verschillende zoektermen.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import xmlrpc.client

# Voeg project root toe aan Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Laad omgevingsvariabelen
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

def get_odoo_connection():
    """Maak verbinding met Odoo via XML-RPC"""
    odoo_base_url = os.getenv("ODOO_BASE_URL")
    odoo_db = os.getenv("ODOO_DB")
    odoo_login = os.getenv("ODOO_LOGIN")
    odoo_api_key = os.getenv("ODOO_API_KEY")
    
    if not all([odoo_base_url, odoo_db, odoo_login, odoo_api_key]):
        raise ValueError("Ontbrekende Odoo credentials in .env")
    
    base_url = odoo_base_url.rstrip('/')
    common_url = f"{base_url}/xmlrpc/2/common"
    object_url = f"{base_url}/xmlrpc/2/object"
    
    common_proxy = xmlrpc.client.ServerProxy(common_url, allow_none=True)
    object_proxy = xmlrpc.client.ServerProxy(object_url, allow_none=True)
    
    # Authenticatie
    uid = common_proxy.authenticate(odoo_db, odoo_login, odoo_api_key, {})
    if not uid:
        raise RuntimeError("Odoo authenticatie mislukt")
    
    return object_proxy, odoo_db, uid, odoo_api_key

def search_products(object_proxy, db, uid, password, search_terms):
    """Zoek producten met verschillende zoektermen"""
    all_results = []
    
    for term in search_terms:
        print(f"\nZoeken naar: '{term}'")
        
        # Probeer exacte match
        product_ids = object_proxy.execute_kw(
            db, uid, password,
            'product.product',
            'search',
            [[('name', '=', term)]]
        )
        
        if not product_ids:
            # Probeer contains match
            product_ids = object_proxy.execute_kw(
                db, uid, password,
                'product.product',
                'search',
                [[('name', 'ilike', f'%{term}%')]]
            )
        
        if product_ids:
            products = object_proxy.execute_kw(
                db, uid, password,
                'product.product',
                'read',
                [product_ids],
                {'fields': ['id', 'name', 'default_code', 'list_price', 'sale_ok', 'purchase_ok']}
            )
            
            print(f"  Gevonden: {len(products)} product(en)")
            for prod in products:
                print(f"    - ID {prod['id']}: {prod['name']} (€{prod.get('list_price', 0)})")
                if prod not in all_results:
                    all_results.append(prod)
        else:
            print(f"  Geen resultaten")
    
    return all_results

def main():
    """Hoofdfunctie"""
    print("=" * 80)
    print("PRODUCTEN ZOEKEN IN ODOO")
    print("=" * 80)
    
    # Zoektermen voor de ontbrekende producten
    search_terms = [
        "Verse Friet",
        "onbeperkt",
        "Kids",
        "Pakket",
        "Friet & Snacks",
        "Kids Pakket"
    ]
    
    try:
        # Maak verbinding
        print("\n1. Verbinden met Odoo...")
        object_proxy, db, uid, password = get_odoo_connection()
        print("   [OK] Verbinding succesvol")
        
        # Zoek producten
        results = search_products(object_proxy, db, uid, password, search_terms)
        
        print("\n" + "=" * 80)
        print("SAMENVATTING")
        print("=" * 80)
        print(f"\nTotaal unieke producten gevonden: {len(results)}")
        
        if results:
            print("\nGevonden producten:")
            for prod in results:
                print(f"  - ID {prod['id']}: {prod['name']}")
        
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n[ERROR] Fout: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
