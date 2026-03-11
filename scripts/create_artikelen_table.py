"""
Script om artikelen tabel aan te maken op basis van Odoo product velden
en de 3 producten op te slaan.
"""
import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Voeg project root toe aan Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Laad omgevingsvariabelen
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    
    # Als interne URL, vervang met publieke URL voor lokaal gebruik
    if "railway.internal" in database_url:
        print("[INFO] Vervang interne URL met publieke URL voor lokaal gebruik...")
        database_url = database_url.replace(
            "postgres.railway.internal:5432",
            "metro.proxy.rlwy.net:18535"
        )
        if "***" in database_url:
            database_url = database_url.replace("***", "bHmvLbuqHOvoAmZfYzWblUQERHnwdaBm")
    
    return database_url

def create_artikelen_table(cur, conn):
    """Maak de artikelen tabel aan op basis van Odoo velden"""
    print("\n2. Aanmaken van artikelen tabel...")
    
    # SQL voor het aanmaken van de tabel
    # Gebaseerd op gevulde velden uit Odoo producten
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS artikelen (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        
        -- Odoo sync
        odoo_id INTEGER UNIQUE NOT NULL,
        
        -- Product informatie
        naam VARCHAR(255) NOT NULL,
        display_name VARCHAR(255),
        partner_ref VARCHAR(255),
        
        -- Prijzen
        verkoopprijs DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
        inkoopprijs DECIMAL(10, 2) DEFAULT 0.00,
        price_extra DECIMAL(10, 2) DEFAULT 0.00,
        
        -- Status
        actief BOOLEAN DEFAULT TRUE,
        sale_ok BOOLEAN DEFAULT FALSE,
        purchase_ok BOOLEAN DEFAULT FALSE,
        
        -- Type en classificatie
        type VARCHAR(20), -- consu, service, product
        service_type VARCHAR(50), -- manual, timesheet, etc.
        service_tracking VARCHAR(20), -- no, lot, serial
        service_policy VARCHAR(50), -- ordered_prepaid, etc.
        
        -- Eenheid
        uom_id INTEGER,
        uom_name VARCHAR(50),
        
        -- BTW
        taxes_id INTEGER[], -- Array van BTW IDs
        supplier_taxes_id INTEGER[], -- Array van leverancier BTW IDs
        tax_string VARCHAR(255),
        
        -- Valuta
        currency_id INTEGER,
        cost_currency_id INTEGER,
        company_currency_id INTEGER,
        fiscal_country_codes VARCHAR(10),
        
        -- Voorraad (optioneel, voor referentie)
        qty_available DECIMAL(10, 2) DEFAULT 0.00,
        virtual_available DECIMAL(10, 2) DEFAULT 0.00,
        
        -- Fysieke eigenschappen
        weight DECIMAL(10, 2) DEFAULT 0.00,
        weight_uom_name VARCHAR(20),
        volume DECIMAL(10, 2) DEFAULT 0.00,
        volume_uom_name VARCHAR(20),
        
        -- Odoo timestamps
        odoo_create_date TIMESTAMP WITH TIME ZONE,
        odoo_write_date TIMESTAMP WITH TIME ZONE,
        
        -- Extra
        sequence INTEGER DEFAULT 1,
        color INTEGER DEFAULT 0
    );
    
    CREATE INDEX IF NOT EXISTS idx_artikelen_odoo_id ON artikelen(odoo_id);
    CREATE INDEX IF NOT EXISTS idx_artikelen_naam ON artikelen(naam);
    CREATE INDEX IF NOT EXISTS idx_artikelen_actief ON artikelen(actief);
    CREATE INDEX IF NOT EXISTS idx_artikelen_sale_ok ON artikelen(sale_ok);
    """
    
    try:
        cur.execute(create_table_sql)
        conn.commit()
        print("   [OK] Tabel 'artikelen' aangemaakt")
    except Exception as e:
        conn.rollback()
        print(f"   [ERROR] Fout bij aanmaken tabel: {e}")
        raise

def parse_odoo_date(date_str):
    """Parse Odoo datum string naar PostgreSQL timestamp"""
    if not date_str:
        return None
    try:
        # Odoo format: "2026-02-09 13:21:02"
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return dt
    except:
        return None

def insert_product(cur, conn, product_data):
    """Voeg een product toe aan de artikelen tabel"""
    filled_fields = product_data['filled_fields']
    
    # Extract relevante velden
    odoo_id = filled_fields.get('id')
    naam = filled_fields.get('name', '')
    display_name = filled_fields.get('display_name')
    partner_ref = filled_fields.get('partner_ref')
    
    verkoopprijs = float(filled_fields.get('list_price', 0))
    inkoopprijs = float(filled_fields.get('standard_price', 0))
    price_extra = float(filled_fields.get('price_extra', 0))
    
    actief = filled_fields.get('active', True)
    sale_ok = filled_fields.get('sale_ok', False)
    purchase_ok = filled_fields.get('purchase_ok', False)
    
    type_val = filled_fields.get('type')
    service_type = filled_fields.get('service_type')
    service_tracking = filled_fields.get('service_tracking')
    service_policy = filled_fields.get('service_policy')
    
    # UOM (eenheid)
    uom_id = None
    uom_name = None
    if 'uom_id' in filled_fields and isinstance(filled_fields['uom_id'], list):
        uom_id = filled_fields['uom_id'][0] if len(filled_fields['uom_id']) > 0 else None
    if 'uom_name' in filled_fields:
        uom_name = filled_fields['uom_name']
    
    # BTW IDs (arrays)
    taxes_id = None
    if 'taxes_id' in filled_fields:
        if isinstance(filled_fields['taxes_id'], list):
            taxes_id = filled_fields['taxes_id']
        else:
            taxes_id = [filled_fields['taxes_id']]
    
    supplier_taxes_id = None
    if 'supplier_taxes_id' in filled_fields:
        if isinstance(filled_fields['supplier_taxes_id'], list):
            supplier_taxes_id = filled_fields['supplier_taxes_id']
        else:
            supplier_taxes_id = [filled_fields['supplier_taxes_id']]
    
    tax_string = filled_fields.get('tax_string')
    
    # Valuta IDs
    currency_id = None
    if 'currency_id' in filled_fields and isinstance(filled_fields['currency_id'], list):
        currency_id = filled_fields['currency_id'][0] if len(filled_fields['currency_id']) > 0 else None
    
    cost_currency_id = None
    if 'cost_currency_id' in filled_fields and isinstance(filled_fields['cost_currency_id'], list):
        cost_currency_id = filled_fields['cost_currency_id'][0] if len(filled_fields['cost_currency_id']) > 0 else None
    
    company_currency_id = None
    if 'company_currency_id' in filled_fields and isinstance(filled_fields['company_currency_id'], list):
        company_currency_id = filled_fields['company_currency_id'][0] if len(filled_fields['company_currency_id']) > 0 else None
    
    fiscal_country_codes = filled_fields.get('fiscal_country_codes')
    
    # Voorraad
    qty_available = float(filled_fields.get('qty_available', 0))
    virtual_available = float(filled_fields.get('virtual_available', 0))
    
    # Fysieke eigenschappen
    weight = float(filled_fields.get('weight', 0))
    weight_uom_name = filled_fields.get('weight_uom_name')
    volume = float(filled_fields.get('volume', 0))
    volume_uom_name = filled_fields.get('volume_uom_name')
    
    # Odoo timestamps
    odoo_create_date = parse_odoo_date(filled_fields.get('create_date'))
    odoo_write_date = parse_odoo_date(filled_fields.get('write_date'))
    
    sequence = int(filled_fields.get('sequence', 1))
    color = int(filled_fields.get('color', 0))
    
    # Insert SQL
    insert_sql = """
    INSERT INTO artikelen (
        odoo_id, naam, display_name, partner_ref,
        verkoopprijs, inkoopprijs, price_extra,
        actief, sale_ok, purchase_ok,
        type, service_type, service_tracking, service_policy,
        uom_id, uom_name,
        taxes_id, supplier_taxes_id, tax_string,
        currency_id, cost_currency_id, company_currency_id, fiscal_country_codes,
        qty_available, virtual_available,
        weight, weight_uom_name, volume, volume_uom_name,
        odoo_create_date, odoo_write_date,
        sequence, color
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    ON CONFLICT (odoo_id) DO UPDATE SET
        naam = EXCLUDED.naam,
        display_name = EXCLUDED.display_name,
        partner_ref = EXCLUDED.partner_ref,
        verkoopprijs = EXCLUDED.verkoopprijs,
        inkoopprijs = EXCLUDED.inkoopprijs,
        price_extra = EXCLUDED.price_extra,
        actief = EXCLUDED.actief,
        sale_ok = EXCLUDED.sale_ok,
        purchase_ok = EXCLUDED.purchase_ok,
        type = EXCLUDED.type,
        service_type = EXCLUDED.service_type,
        service_tracking = EXCLUDED.service_tracking,
        service_policy = EXCLUDED.service_policy,
        uom_id = EXCLUDED.uom_id,
        uom_name = EXCLUDED.uom_name,
        taxes_id = EXCLUDED.taxes_id,
        supplier_taxes_id = EXCLUDED.supplier_taxes_id,
        tax_string = EXCLUDED.tax_string,
        currency_id = EXCLUDED.currency_id,
        cost_currency_id = EXCLUDED.cost_currency_id,
        company_currency_id = EXCLUDED.company_currency_id,
        fiscal_country_codes = EXCLUDED.fiscal_country_codes,
        qty_available = EXCLUDED.qty_available,
        virtual_available = EXCLUDED.virtual_available,
        weight = EXCLUDED.weight,
        weight_uom_name = EXCLUDED.weight_uom_name,
        volume = EXCLUDED.volume,
        volume_uom_name = EXCLUDED.volume_uom_name,
        odoo_create_date = EXCLUDED.odoo_create_date,
        odoo_write_date = EXCLUDED.odoo_write_date,
        sequence = EXCLUDED.sequence,
        color = EXCLUDED.color,
        updated_at = CURRENT_TIMESTAMP
    RETURNING id, naam, verkoopprijs
    """
    
    try:
        cur.execute(insert_sql, (
            odoo_id, naam, display_name, partner_ref,
            verkoopprijs, inkoopprijs, price_extra,
            actief, sale_ok, purchase_ok,
            type_val, service_type, service_tracking, service_policy,
            uom_id, uom_name,
            taxes_id, supplier_taxes_id, tax_string,
            currency_id, cost_currency_id, company_currency_id, fiscal_country_codes,
            qty_available, virtual_available,
            weight, weight_uom_name, volume, volume_uom_name,
            odoo_create_date, odoo_write_date,
            sequence, color
        ))
        
        result = cur.fetchone()
        conn.commit()
        return result
        
    except Exception as e:
        conn.rollback()
        raise Exception(f"Fout bij insert product {naam}: {e}")

def main():
    """Hoofdfunctie"""
    print("=" * 80)
    print("ARTIKELEN TABEL AANMAKEN EN PRODUCTEN OPSLAAN")
    print("=" * 80)
    
    # Laad product data
    json_file = project_root / 'scripts' / 'odoo_products_3.json'
    if not json_file.exists():
        print(f"[ERROR] Bestand niet gevonden: {json_file}")
        print("       Voer eerst scripts/fetch_3_odoo_products.py uit")
        sys.exit(1)
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    products = data['products']
    print(f"\n1. Geladen: {len(products)} product(en) uit JSON")
    
    # Maak database verbinding
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Maak tabel aan
        create_artikelen_table(cur, conn)
        
        # Voeg producten toe
        print("\n3. Producten toevoegen aan database...")
        inserted_products = []
        
        for idx, product in enumerate(products, 1):
            product_name = product['name']
            print(f"\n   {idx}. {product_name} (Odoo ID: {product['id']})")
            
            try:
                result = insert_product(cur, conn, product)
                if result:
                    print(f"      [OK] Opgeslagen: ID {result['id']}, €{result['verkoopprijs']}")
                    inserted_products.append(result)
                else:
                    print(f"      [WAARSCHUWING] Geen resultaat terug")
            except Exception as e:
                print(f"      [ERROR] {e}")
        
        # Toon resultaten
        print("\n" + "=" * 80)
        print("RESULTATEN")
        print("=" * 80)
        
        cur.execute("SELECT COUNT(*) as count FROM artikelen")
        total_count = cur.fetchone()['count']
        print(f"\nTotaal artikelen in database: {total_count}")
        
        cur.execute("""
            SELECT id, naam, verkoopprijs, inkoopprijs, actief, sale_ok, odoo_id
            FROM artikelen
            ORDER BY naam
        """)
        all_products = cur.fetchall()
        
        print("\nAlle artikelen:")
        print("-" * 80)
        for prod in all_products:
            print(f"  {prod['naam']:<40} €{prod['verkoopprijs']:>8.2f} (Odoo ID: {prod['odoo_id']})")
        
        print("=" * 80 + "\n")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[ERROR] Fout: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
