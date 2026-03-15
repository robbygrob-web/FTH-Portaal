"""
Script om database migratie uit te voeren op Railway database.
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
from psycopg2.extras import RealDictCursor

def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "DATABASE_URL niet gevonden in environment variabelen.\n"
            "Zorg ervoor dat DATABASE_URL is ingesteld in .env of als environment variabele."
        )
    return database_url

def run_migration(migration_file: Path):
    """Voer migratie SQL bestand uit"""
    database_url = get_database_url()
    
    if not migration_file.exists():
        raise FileNotFoundError(f"Migratie bestand niet gevonden: {migration_file}")
    
    # Lees migratie bestand
    with open(migration_file, 'r', encoding='utf-8') as f:
        migration_sql = f.read()
    
    print("="*80)
    print("Database Migratie Uitvoeren")
    print("="*80)
    print(f"Migratie bestand: {migration_file}")
    print("="*80)
    
    try:
        # Maak verbinding
        print("\n[1/2] Verbinden met database...")
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Voer migratie uit
        print("[2/2] Migratie uitvoeren...")
        cur.execute(migration_sql)
        
        # Haal verificatie resultaten op (laatste SELECT statement)
        print("\n" + "="*80)
        print("Verificatie Resultaten:")
        print("="*80)
        
        # Verificatie query (laatste SELECT in het script)
        cur.execute("""
            SELECT 
                column_name, 
                data_type, 
                column_default,
                is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'orders' 
            AND column_name IN ('planning_afgemeld', 'planning_afmeld_token')
            ORDER BY column_name;
        """)
        
        results = cur.fetchall()
        
        if results:
            print("\nKolommen gevonden:")
            for row in results:
                print(f"  - {row['column_name']}:")
                print(f"      Type: {row['data_type']}")
                print(f"      Default: {row['column_default'] or 'NULL'}")
                print(f"      Nullable: {row['is_nullable']}")
        else:
            print("\n⚠️  Geen kolommen gevonden - migratie mogelijk niet uitgevoerd")
        
        conn.commit()
        
        # Sluit verbinding
        cur.close()
        conn.close()
        
        print("\n" + "="*80)
        print("✅ Migratie voltooid!")
        print("="*80)
        
        return results
        
    except psycopg2.Error as e:
        if 'conn' in locals():
            conn.rollback()
        print(f"\n❌ Database fout: {e}")
        if hasattr(e, 'pgcode'):
            print(f"   Error code: {e.pgcode}")
        if hasattr(e, 'pgerror'):
            print(f"   Error message: {e.pgerror}")
        sys.exit(1)
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        print(f"\n❌ Fout: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    migration_file = project_root / "database" / "migrate_planning_fields.sql"
    run_migration(migration_file)
