"""
Script om artikelen tabel aan te maken met BTW velden en alle 7 producten op te slaan.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import xmlrpc.client
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
        database_url = database_url.replace(
            "postgres.railway.internal:5432",
            "metro.proxy.rlwy.net:18535"
        )
        if "***" in database_url:
            database_url = database_url.replace("***", "bHmvLbuqHOvoAmZfYzWblUQERHnwdaBm")
    
    return database_url

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

def create_artikelen_table(cur, conn):
    """Maak de artikelen tabel aan"""
    print("\n2. Aanmaken van artikelen tabel...")
    
    # Verwijder oude tabel als die bestaat (voor clean start)
    drop_sql = "DROP TABLE IF EXISTS artikelen CASCADE;"
    cur.execute(drop_sql)
    conn.commit()
    print("   [INFO] Oude tabel verwijderd (als die bestond)")
    
    # Maak nieuwe tabel
    create_table_sql = """
    CREATE TABLE artikelen (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        naam VARCHAR(255) NOT NULL,
        prijs_excl DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
        btw_pct DECIMAL(5, 2) NOT NULL DEFAULT 9.00,
        btw_bedrag DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
        prijs_incl DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
        odoo_id INTEGER UNIQUE NOT NULL,
        actief BOOLEAN DEFAULT TRUE,
        aangemaakt_op TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX idx_artikelen_odoo_id ON artikelen(odoo_id);
    CREATE INDEX idx_artikelen_actief ON artikelen(actief);
    CREATE INDEX idx_artikelen_naam ON artikelen(naam);
    """
    
    try:
        cur.execute(create_table_sql)
        conn.commit()
        print("   [OK] Tabel 'artikelen' aangemaakt")
    except Exception as e:
        conn.rollback()
        print(f"   [ERROR] Fout bij aanmaken tabel: {e}")
        raise

def fetch_product_by_id(object_proxy, db, uid, password, product_id):
    """Haal een product op op basis van ID"""
    try:
        products = object_proxy.execute_kw(
            db, uid, password,
            'product.product',
            'read',
            [[product_id]],
            {'fields': ['id', 'name', 'list_price', 'taxes_id', 'active']}
        )
        
        if products:
            return products[0]
        return None
    except Exception as e:
        print(f"      [ERROR] Fout bij ophalen product {product_id}: {e}")
        return None

def get_tax_rate(object_proxy, db, uid, password, tax_id):
    """Haal BTW percentage op uit Odoo"""
    try:
        taxes = object_proxy.execute_kw(
            db, uid, password,
            'account.tax',
            'read',
            [[tax_id]],
            {'fields': ['amount', 'name']}
        )
        
        if taxes:
            # amount is in percentage (bijv. 9.0 voor 9%)
            return float(taxes[0].get('amount', 9.0))
        return 9.0  # Standaard 9% als niet gevonden
    except:
        return 9.0  # Standaard 9% bij fout

def insert_product(cur, conn, product_data, btw_pct=9.0):
    """Voeg een product toe aan de artikelen tabel"""
    naam = product_data['name']
    odoo_id = product_data['id']
    prijs_excl = float(product_data.get('list_price', 0))
    actief = product_data.get('active', True)
    
    # Bereken BTW bedrag en prijs incl
    btw_bedrag = round(prijs_excl * (btw_pct / 100), 2)
    prijs_incl = round(prijs_excl + btw_bedrag, 2)
    
    insert_sql = """
    INSERT INTO artikelen (
        naam, prijs_excl, btw_pct, btw_bedrag, prijs_incl,
        odoo_id, actief
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s
    )
    ON CONFLICT (odoo_id) DO UPDATE SET
        naam = EXCLUDED.naam,
        prijs_excl = EXCLUDED.prijs_excl,
        btw_pct = EXCLUDED.btw_pct,
        btw_bedrag = EXCLUDED.btw_bedrag,
        prijs_incl = EXCLUDED.prijs_incl,
        actief = EXCLUDED.actief
    RETURNING id, naam, prijs_excl, btw_pct, btw_bedrag, prijs_incl
    """
    
    try:
        cur.execute(insert_sql, (
            naam, prijs_excl, btw_pct, btw_bedrag, prijs_incl,
            odoo_id, actief
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
    print("ARTIKELEN TABEL MET BTW AANMAKEN")
    print("=" * 80)
    
    # Product IDs die we willen ophalen
    # Gebaseerd op eerdere zoekresultaten
    # Format: (odoo_id, naam, btw_pct) - btw_pct kan None zijn om uit Odoo te halen
    product_ids = [
        (81, "Puntzak Verse Friet", 9.0),
        (83, "Puntzak Verse Friet & Snack", 9.0),  # "Snack Verse Friet & Snacks"
        (84, "Verse Friet & Snacks", 9.0),
        (85, "Verse Friet , Snacks & Burger ( onbeperkt)", 9.0),  # "Verse Friet, Snacks & Burger (onbeperkt)"
        (86, "Kids Pakket", 9.0),
        (10, "Broodjes", 9.0),
        (9, "Drankjes", 9.0),
        (8, "Reiskostenvergoeding", 9.0)  # Reiskosten heeft 9% BTW
    ]
    
    try:
        # Maak database verbinding
        print("\n1. Verbinden met database...")
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        print("   [OK] Database verbinding succesvol")
        
        # Maak Odoo verbinding
        print("\n3. Verbinden met Odoo...")
        object_proxy, db, uid, password = get_odoo_connection()
        print("   [OK] Odoo verbinding succesvol")
        
        # Maak tabel aan
        create_artikelen_table(cur, conn)
        
        # Haal producten op en sla op
        print("\n4. Producten ophalen en opslaan...")
        inserted_products = []
        
        for idx, (product_id, expected_name, default_btw) in enumerate(product_ids, 1):
            print(f"\n   {idx}. Ophalen: {expected_name} (Odoo ID: {product_id})")
            
            product = fetch_product_by_id(object_proxy, db, uid, password, product_id)
            
            if product:
                # Gebruik opgegeven BTW percentage, of haal uit Odoo als None
                btw_pct = default_btw
                if default_btw is None:
                    # Haal BTW percentage op uit Odoo
                    if 'taxes_id' in product and product['taxes_id']:
                        # Neem eerste BTW ID
                        tax_id = product['taxes_id'][0] if isinstance(product['taxes_id'], list) else product['taxes_id']
                        btw_pct = get_tax_rate(object_proxy, db, uid, password, tax_id)
                    else:
                        btw_pct = 9.0  # Standaard 9% als niet gevonden
                
                print(f"      BTW percentage: {btw_pct}%")
                
                try:
                    result = insert_product(cur, conn, product, btw_pct)
                    if result:
                        print(f"      [OK] Opgeslagen: {result['naam']}")
                        print(f"            Prijs excl: €{result['prijs_excl']:.2f}")
                        print(f"            BTW ({result['btw_pct']}%): €{result['btw_bedrag']:.2f}")
                        print(f"            Prijs incl: €{result['prijs_incl']:.2f}")
                        inserted_products.append(result)
                    else:
                        print(f"      [WAARSCHUWING] Geen resultaat terug")
                except Exception as e:
                    print(f"      [ERROR] {e}")
            else:
                print(f"      [X] Product niet gevonden")
        
        # Toon resultaten
        print("\n" + "=" * 80)
        print("RESULTATEN")
        print("=" * 80)
        
        cur.execute("SELECT COUNT(*) as count FROM artikelen")
        total_count = cur.fetchone()['count']
        print(f"\nTotaal artikelen in database: {total_count}")
        
        cur.execute("""
            SELECT id, naam, prijs_excl, btw_pct, btw_bedrag, prijs_incl, odoo_id, actief
            FROM artikelen
            ORDER BY naam
        """)
        all_products = cur.fetchall()
        
        print("\nAlle artikelen:")
        print("-" * 80)
        print(f"{'Naam':<45} {'Prijs excl':<12} {'BTW %':<8} {'BTW bedrag':<12} {'Prijs incl':<12}")
        print("-" * 80)
        for prod in all_products:
            print(f"{prod['naam']:<45} €{prod['prijs_excl']:>9.2f}  {prod['btw_pct']:>5.2f}%  €{prod['btw_bedrag']:>9.2f}  €{prod['prijs_incl']:>9.2f}")
        
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
