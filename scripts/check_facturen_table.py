"""
Check facturen tabel en voeg Mollie velden toe indien nodig.
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
    print("FACTUREN TABEL CHECK EN UPDATE")
    print("=" * 80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check welke kolommen al bestaan
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'facturen'
        """)
        existing_columns = [row['column_name'] for row in cur.fetchall()]
        
        print(f"\nBestaande kolommen: {', '.join(existing_columns)}")
        
        # Voeg Mollie velden toe als ze ontbreken
        mollie_columns = {
            'mollie_payment_url': 'VARCHAR',
            'mollie_payment_id': 'VARCHAR',
            'betaal_status': "VARCHAR DEFAULT 'onbetaald'",
            'betaald_op': 'TIMESTAMP',
        }
        
        print("\nControleren Mollie velden...")
        for col_name, col_def in mollie_columns.items():
            if col_name not in existing_columns:
                sql = f"ALTER TABLE facturen ADD COLUMN IF NOT EXISTS {col_name} {col_def};"
                try:
                    cur.execute(sql)
                    conn.commit()
                    print(f"  [OK] {col_name} toegevoegd")
                except Exception as e:
                    print(f"  [ERROR] {col_name}: {e}")
                    conn.rollback()
            else:
                print(f"  [INFO] {col_name} bestaat al")
        
        # Check of aangemaakt_op bestaat, anders toevoegen
        if 'aangemaakt_op' not in existing_columns:
            try:
                cur.execute("ALTER TABLE facturen ADD COLUMN IF NOT EXISTS aangemaakt_op TIMESTAMP DEFAULT NOW();")
                conn.commit()
                print("  [OK] aangemaakt_op toegevoegd")
            except Exception as e:
                print(f"  [ERROR] aangemaakt_op: {e}")
                conn.rollback()
        
        # Toon volledige schema
        print("\n" + "=" * 80)
        print("FACTUREN TABEL SCHEMA")
        print("=" * 80)
        
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'facturen'
            ORDER BY ordinal_position;
        """)
        
        columns = cur.fetchall()
        
        print(f"\n{'Kolom':<30} {'Type':<25} {'Nullable':<10} {'Default'}")
        print("-" * 80)
        for col in columns:
            default_str = str(col['column_default'] or '')[:30]
            print(f"{col['column_name']:<30} {col['data_type']:<25} {col['is_nullable']:<10} {default_str}")
        
        print("\n" + "=" * 80 + "\n")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[ERROR] Fout: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
