"""
Script om 3 specifieke producten op te halen uit Odoo en alle gevulde velden te tonen.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import xmlrpc.client
import json
from datetime import datetime

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

def is_value_filled(value):
    """Check of een waarde gevuld is (niet None, niet False, niet lege string)"""
    if value is None:
        return False
    if value is False:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    if isinstance(value, list) and len(value) == 0:
        return False
    return True

def fetch_product_by_id(object_proxy, db, uid, password, product_id):
    """Haal een product op op basis van ID"""
    try:
        # Probeer eerst zonder fields om alle velden te krijgen
        products = object_proxy.execute_kw(
            db, uid, password,
            'product.product',
            'read',
            [[product_id]],
            {}
        )
    except Exception:
        # Als dat niet werkt, gebruik een brede field lijst
        products = object_proxy.execute_kw(
            db, uid, password,
            'product.product',
            'read',
            [[product_id]],
            {'fields': [
                'name', 'default_code', 'barcode', 'list_price', 'standard_price',
                'categ_id', 'type', 'sale_ok', 'purchase_ok', 'active',
                'description', 'description_sale', 'description_purchase',
                'uom_id', 'uom_po_id', 'weight', 'volume',
                'taxes_id', 'supplier_taxes_id', 'company_id',
                'create_date', 'write_date', 'create_uid', 'write_uid',
                'image_1920', 'image_128', 'image_64',
                'sale_delay', 'purchase_method', 'purchase_line_warn',
                'sale_line_warn', 'tracking', 'tracking_serial', 'tracking_lot',
                'qty_available', 'virtual_available', 'incoming_qty', 'outgoing_qty',
                'id'
            ]}
        )
    
    if products:
        return products[0]
    return None

def analyze_product_fields(product):
    """Analyseer welke velden gevuld zijn"""
    filled_fields = {}
    
    for key, value in product.items():
        if is_value_filled(value):
            filled_fields[key] = value
    
    return filled_fields

def main():
    """Hoofdfunctie"""
    print("=" * 80)
    print("3 ODOO PRODUCTEN OPHALEN")
    print("=" * 80)
    
    # Producten die we willen ophalen (ID, naam)
    products_to_fetch = [
        (81, "Puntzak Verse Friet"),
        (85, "Verse Friet , Snacks & Burger ( onbeperkt)"),
        (86, "Kids Pakket")
    ]
    
    try:
        # Maak verbinding
        print("\n1. Verbinden met Odoo...")
        object_proxy, db, uid, password = get_odoo_connection()
        print("   [OK] Verbinding succesvol")
        
        all_products = []
        all_filled_fields = set()
        
        # Haal elk product op
        for idx, (product_id, product_name) in enumerate(products_to_fetch, 1):
            print(f"\n{idx}. Ophalen: {product_name} (ID: {product_id})")
            product = fetch_product_by_id(object_proxy, db, uid, password, product_id)
            
            if product:
                print(f"   [OK] Product gevonden")
                
                # Analyseer gevulde velden
                filled_fields = analyze_product_fields(product)
                all_products.append({
                    'name': product_name,
                    'id': product.get('id'),
                    'data': product,
                    'filled_fields': filled_fields
                })
                
                # Verzamel alle veldnamen
                all_filled_fields.update(filled_fields.keys())
                
                # Toon gevulde velden
                print(f"\n   Gevulde velden ({len(filled_fields)}):")
                print("   " + "-" * 76)
                for field_name, field_value in sorted(filled_fields.items()):
                    # Format waarde voor weergave
                    if isinstance(field_value, list):
                        value_str = str(field_value)
                    elif isinstance(field_value, dict):
                        value_str = json.dumps(field_value, indent=2, default=str)
                    else:
                        value_str = str(field_value)
                    
                    # Truncate lange waarden
                    if len(value_str) > 60:
                        value_str = value_str[:57] + "..."
                    
                    print(f"   {field_name:<30} = {value_str}")
            else:
                print(f"   [X] Product niet gevonden")
        
        # Toon samenvatting
        print("\n" + "=" * 80)
        print("SAMENVATTING")
        print("=" * 80)
        print(f"\nTotaal producten gevonden: {len(all_products)}")
        print(f"Totaal unieke velden met data: {len(all_filled_fields)}")
        print(f"\nAlle velden die minstens 1x gevuld zijn:")
        for field in sorted(all_filled_fields):
            print(f"  - {field}")
        
        # Sla resultaten op als JSON voor verdere analyse
        output_file = project_root / 'scripts' / 'odoo_products_3.json'
        output_data = {
            'fetched_at': datetime.now().isoformat(),
            'products': []
        }
        
        for prod in all_products:
            output_data['products'].append({
                'name': prod['name'],
                'id': prod['id'],
                'filled_fields': prod['filled_fields']
            })
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, default=str, ensure_ascii=False)
        
        print(f"\n[INFO] Ruwe data opgeslagen in: {output_file}")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n[ERROR] Fout: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
