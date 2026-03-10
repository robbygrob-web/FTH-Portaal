"""Script om product in sale order handmatig aan te passen"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Laad omgevingsvariabelen uit .env bestand VOOR imports
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

from app.odoo_client import get_odoo_client

def update_order_product(order_id=868, product_id=None):
    """Pas het product aan in de sale order"""
    print("=" * 60)
    print(f"Product aanpassen in sale order {order_id}")
    print("=" * 60)
    
    try:
        client = get_odoo_client()
        print(f"\n[OK] OdooClient geïnitialiseerd")
        
        # Stap 1: Haal de huidige order op om order lines te zien
        print(f"\n1. Ophalen sale order {order_id}...")
        order = client.execute_kw(
            "sale.order",
            "read",
            [order_id],
            {"fields": ["id", "name", "order_line", "partner_id"]}
        )
        
        if not order:
            print(f"   [FOUT] Sale order {order_id} niet gevonden")
            return None
        
        order_data = order[0]
        print(f"   [OK] Order gevonden: {order_data.get('name', 'N/A')}")
        print(f"   - Partner: {order_data.get('partner_id', 'N/A')}")
        
        # Stap 2: Zoek product of gebruik opgegeven product_id
        if product_id:
            print(f"\n2. Gebruik opgegeven product ID: {product_id}...")
            product_info = client.execute_kw(
                "product.product",
                "read",
                [product_id],
                {"fields": ["id", "name", "list_price"]}
            )
            if not product_info:
                print(f"   [FOUT] Product {product_id} niet gevonden")
                return None
            product_id = product_info[0]["id"]
            print(f"   [OK] Product: {product_info[0]['name']}")
        else:
            # Zoek alle producten met "Frietpakket" in de naam
            print("\n2. Zoeken naar producten met 'Frietpakket'...")
            products = client.execute_kw(
                "product.product",
                "search_read",
                [("name", "ilike", "Frietpakket")],
                {"fields": ["id", "name", "list_price"], "limit": 20}
            )
            
            if not products:
            print("   [WAARSCHUWING] Geen producten met 'Frietpakket' gevonden.")
            print("   Zoeken naar alternatieve producten met 'friet' in de naam...")
            # Zoek naar alle producten met "friet" in de naam
            all_friet_products = client.execute_kw(
                "product.product",
                "search_read",
                [("name", "ilike", "friet")],
                {"fields": ["id", "name", "list_price"], "limit": 50}
            )
            
            if all_friet_products:
                print(f"   [INFO] {len(all_friet_products)} alternatief(e) product(en) gevonden:")
                for p in all_friet_products:
                    print(f"     - ID {p['id']}: {p['name']} (€{p.get('list_price', 0)})")
                
                # Zoek naar het beste match (pakket of portie)
                best_match = None
                for p in all_friet_products:
                    name_lower = p['name'].lower()
                    if 'pakket' in name_lower or 'portie' in name_lower:
                        best_match = p
                        break
                
                if best_match:
                    product_id = best_match["id"]
                    print(f"\n   [INFO] Beste match gevonden: {best_match['name']} (ID: {product_id})")
                else:
                    # Gebruik het eerste product
                    product_id = all_friet_products[0]["id"]
                    print(f"\n   [INFO] Gebruik eerste product: {all_friet_products[0]['name']} (ID: {product_id})")
            else:
                print("   [FOUT] Geen geschikte producten gevonden")
                return None
        else:
            print(f"   [OK] {len(products)} product(en) gevonden:")
            for p in products:
                print(f"     - ID {p['id']}: {p['name']} (€{p.get('list_price', 0)})")
            
            # Gebruik het eerste product dat "Frietpakket" bevat
                product_id = products[0]["id"]
                print(f"\n   [INFO] Gebruik product: {products[0]['name']} (ID: {product_id})")
        
        # Stap 3: Haal huidige order lines op
        print(f"\n3. Ophalen order lines van order {order_id}...")
        order_line_ids = order_data.get("order_line", [])
        
        if order_line_ids:
            print(f"   [INFO] {len(order_line_ids)} order line(s) gevonden")
            lines = client.execute_kw(
                "sale.order.line",
                "read",
                order_line_ids,
                {"fields": ["id", "product_id", "name", "product_uom_qty", "price_unit"]}
            )
            
            print("   Huidige order lines:")
            for line in lines:
                product_name = line.get("product_id", ["N/A"])[1] if isinstance(line.get("product_id"), list) else "N/A"
                print(f"     - Line ID {line['id']}: {product_name} x{line.get('product_uom_qty', 0)}")
            
            # Verwijder bestaande order lines en maak nieuwe aan
            print("\n4. Verwijderen bestaande order lines en aanmaken nieuwe...")
            
            # Verwijder bestaande lines
            client.execute_kw(
                "sale.order.line",
                "unlink",
                order_line_ids,
                None
            )
            print(f"   [OK] {len(order_line_ids)} order line(s) verwijderd")
        
        # Stap 4: Maak nieuwe order line aan met het juiste product
        print("\n5. Aanmaken nieuwe order line met Frietpakket x300...")
        
        # Haal product details op
        product_info = client.execute_kw(
            "product.product",
            "read",
            [product_id],
            {"fields": ["id", "name", "list_price", "uom_id"]}
        )
        
        if not product_info:
            print(f"   [FOUT] Product {product_id} niet gevonden")
            return None
        
        product_data = product_info[0]
        print(f"   [OK] Product: {product_data['name']}")
        
        # Maak nieuwe order line aan
        new_line_values = {
            "order_id": order_id,
            "product_id": product_id,
            "product_uom_qty": 300,
            "price_unit": product_data.get("list_price", 0),
        }
        
        new_line_id_result = client.execute_kw(
            "sale.order.line",
            "create",
            [new_line_values],
            None
        )
        
        new_line_id = new_line_id_result[0] if isinstance(new_line_id_result, list) else new_line_id_result
        print(f"   [OK] Nieuwe order line aangemaakt met ID: {new_line_id}")
        
        # Stap 5: Bevestiging
        print("\n" + "=" * 60)
        print("SUCCES: Product aangepast")
        print("=" * 60)
        print(f"\nSale Order ID: {order_id}")
        print(f"Product: {product_data['name']} (ID: {product_id})")
        print(f"Aantal: 300")
        print(f"Order Line ID: {new_line_id}")
        
        return {
            "order_id": order_id,
            "product_id": product_id,
            "product_name": product_data['name'],
            "line_id": new_line_id
        }
        
    except Exception as e:
        print(f"\n[FOUT] Onverwachte fout: {type(e).__name__}: {e}")
        import traceback
        print("\nTraceback:")
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Gebruik order ID 868 (laatste aangemaakte order)
    # Voor Frietpakket: gebruik "Puntzak Verse Friet" (ID 81) of een pakket product
    # Je kunt een product_id meegeven als tweede argument
    import sys
    product_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    result = update_order_product(order_id=868, product_id=product_id)
    sys.exit(0 if result else 1)
