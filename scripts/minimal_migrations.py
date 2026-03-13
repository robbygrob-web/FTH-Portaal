"""
Minimale migraties voor FTH flow.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

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

def main():
    """Hoofdfunctie"""
    print("=" * 80)
    print("MINIMALE MIGRATIES VOOR FTH FLOW")
    print("=" * 80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Orders tabel - 5 kolommen toevoegen
        print("\n1. Orders tabel - kolommen toevoegen...")
        migrations = [
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS halal boolean DEFAULT false;",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS flexible_time varchar;",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS gclid varchar;",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS klant_notitie text;",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS vervaldatum timestamp;",
        ]
        
        for migration in migrations:
            try:
                cur.execute(migration)
                conn.commit()
                print(f"   [OK] {migration[:60]}...")
            except Exception as e:
                print(f"   [ERROR] {migration[:60]}... - {e}")
                conn.rollback()
        
        # 2. Facturen tabel aanmaken
        print("\n2. Facturen tabel aanmaken...")
        create_facturen = """
        CREATE TABLE IF NOT EXISTS facturen (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          order_id UUID REFERENCES orders(id),
          factuurnummer VARCHAR,
          bedrag_excl_btw NUMERIC DEFAULT 0,
          btw_bedrag NUMERIC DEFAULT 0,
          totaal_bedrag NUMERIC DEFAULT 0,
          betaal_status VARCHAR DEFAULT 'onbetaald',
          mollie_payment_url VARCHAR,
          mollie_payment_id VARCHAR,
          betaald_op TIMESTAMP,
          odoo_factuur_id INTEGER,
          aangemaakt_op TIMESTAMP DEFAULT NOW()
        );
        """
        
        try:
            cur.execute(create_facturen)
            conn.commit()
            print("   [OK] Facturen tabel aangemaakt")
        except Exception as e:
            print(f"   [ERROR] Facturen tabel: {e}")
            conn.rollback()
        
        # 3. Betalingen tabel aanmaken
        print("\n3. Betalingen tabel aanmaken...")
        create_betalingen = """
        CREATE TABLE IF NOT EXISTS betalingen (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          factuur_id UUID REFERENCES facturen(id),
          mollie_id VARCHAR,
          bedrag NUMERIC DEFAULT 0,
          status VARCHAR,
          type VARCHAR,
          betaald_op TIMESTAMP,
          aangemaakt_op TIMESTAMP DEFAULT NOW()
        );
        """
        
        try:
            cur.execute(create_betalingen)
            conn.commit()
            print("   [OK] Betalingen tabel aangemaakt")
        except Exception as e:
            print(f"   [ERROR] Betalingen tabel: {e}")
            conn.rollback()
        
        # 4. Toon schema van alle 3 tabellen
        print("\n" + "=" * 80)
        print("SCHEMA VAN ALLE 3 TABELLEN")
        print("=" * 80)
        
        tables = ['orders', 'facturen', 'betalingen']
        
        for table_name in tables:
            print(f"\n--- {table_name.upper()} ---")
            print("-" * 80)
            
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position;
            """, (table_name,))
            
            columns = cur.fetchall()
            
            print(f"{'Kolom':<30} {'Type':<25} {'Nullable':<10} {'Default'}")
            print("-" * 80)
            for col in columns:
                default_str = str(col['column_default'] or '')[:30]
                print(f"{col['column_name']:<30} {col['data_type']:<25} {col['is_nullable']:<10} {default_str}")
        
        print("\n" + "=" * 80)
        print("MIGRATIES VOLTOOID")
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
