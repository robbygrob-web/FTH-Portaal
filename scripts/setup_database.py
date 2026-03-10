"""
Script om PostgreSQL schema uit te voeren op Railway database.
Gebruikt DATABASE_URL uit environment variabelen.
"""
import sys
import os
from pathlib import Path

# Voeg project root toe aan Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Laad environment variabelen
from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "DATABASE_URL niet gevonden in environment variabelen.\n"
            "Zorg ervoor dat DATABASE_URL is ingesteld in .env of als environment variabele."
        )
    return database_url


def execute_schema():
    """Voer schema.sql uit op de database"""
    database_url = get_database_url()
    schema_file = project_root / "database" / "schema.sql"
    
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema bestand niet gevonden: {schema_file}")
    
    # Lees schema bestand
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    print("="*80)
    print("PostgreSQL Schema Setup")
    print("="*80)
    print(f"Database URL: {database_url.split('@')[1] if '@' in database_url else '***'}")  # Toon alleen host
    print(f"Schema bestand: {schema_file}")
    print("="*80)
    
    try:
        # Maak verbinding
        print("\n[1/3] Verbinden met database...")
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Voer schema uit
        print("[2/3] Schema uitvoeren...")
        cur.execute(schema_sql)
        
        # Verifieer tabellen
        print("[3/3] Verifiëren tabellen...")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = cur.fetchall()
        
        print("\n" + "="*80)
        print("✅ Schema succesvol uitgevoerd!")
        print("="*80)
        print(f"\nAangemaakte tabellen ({len(tables)}):")
        for table in tables:
            print(f"  ✓ {table[0]}")
        
        # Sluit verbinding
        cur.close()
        conn.close()
        
        print("\n" + "="*80)
        print("Klaar!")
        print("="*80)
        
    except psycopg2.Error as e:
        print(f"\n❌ Database fout: {e}")
        print(f"   Error code: {e.pgcode}")
        print(f"   Error message: {e.pgerror}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fout: {e}")
        sys.exit(1)


if __name__ == "__main__":
    execute_schema()
