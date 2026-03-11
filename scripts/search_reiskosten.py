"""
Script om Reiskosten product te zoeken in Odoo.
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

def main():
    """Hoofdfunctie"""
    print("=" * 80)
    print("REISKOSTEN PRODUCT ZOEKEN")
    print("=" * 80)
    
    search_terms = ["Reiskosten", "Reis", "kosten"]
    
    try:
        print("\n1. Verbinden met Odoo...")
        object_proxy, db, uid, password = get_odoo_connection()
        print("   [OK] Verbinding succesvol")
        
        all_results = []
        
        for term in search_terms:
            print(f"\nZoeken naar: '{term}'")
            
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
                    {'fields': ['id', 'name', 'list_price', 'taxes_id', 'active']}
                )
                
                print(f"  Gevonden: {len(products)} product(en)")
                for prod in products:
                    print(f"    - ID {prod['id']}: {prod['name']} (€{prod.get('list_price', 0)})")
                    all_results.append(prod)
        
        print("\n" + "=" * 80)
        print("GEVONDEN PRODUCTEN")
        print("=" * 80)
        
        # Unieke producten
        seen = set()
        unique_products = []
        for prod in all_results:
            if prod['id'] not in seen:
                seen.add(prod['id'])
                unique_products.append(prod)
        
        for prod in sorted(unique_products, key=lambda x: x['id']):
            print(f"  ID {prod['id']}: {prod['name']} (€{prod.get('list_price', 0)})")
        
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n[ERROR] Fout: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
