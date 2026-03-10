"""
Migratie script om UTM tracking kolommen toe te voegen aan orders tabel.
Voegt utm_source, utm_medium, utm_campaign, utm_content kolommen toe.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2

# Laad omgevingsvariabelen
env_path = Path(__file__).parent.parent / '.env'
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
        # Vervang *** met echte password (tijdelijk voor lokaal gebruik)
        if "***" in database_url:
            database_url = database_url.replace("***", "bHmvLbuqHOvoAmZfYzWblUQERHnwdaBm")
    
    return database_url


def migrate_utm_columns():
    """Voeg UTM kolommen toe aan orders tabel"""
    print("="*80)
    print("UTM Kolommen Migratie")
    print("="*80)
    
    try:
        # Verbind met database
        print("\n[1/4] Verbinden met database...")
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        print("   [OK] Verbonden")
        
        # Check of kolommen al bestaan
        print("\n[2/4] Controleren of UTM kolommen al bestaan...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'orders' 
            AND column_name IN ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content')
        """)
        existing_columns = [row[0] for row in cur.fetchall()]
        
        columns_to_add = []
        if 'utm_source' not in existing_columns:
            columns_to_add.append('utm_source')
        if 'utm_medium' not in existing_columns:
            columns_to_add.append('utm_medium')
        if 'utm_campaign' not in existing_columns:
            columns_to_add.append('utm_campaign')
        if 'utm_content' not in existing_columns:
            columns_to_add.append('utm_content')
        
        if not columns_to_add:
            print("   [OK] Alle UTM kolommen bestaan al, geen migratie nodig")
            cur.close()
            conn.close()
            print("\n" + "="*80)
            print("Klaar - Geen wijzigingen nodig")
            print("="*80)
            return
        
        print(f"   [INFO] {len(columns_to_add)} kolom(men) toe te voegen: {', '.join(columns_to_add)}")
        
        # Voeg kolommen toe
        print("\n[3/4] UTM kolommen toevoegen...")
        for column in columns_to_add:
            try:
                cur.execute(f"""
                    ALTER TABLE orders 
                    ADD COLUMN IF NOT EXISTS {column} VARCHAR(255)
                """)
                print(f"   [OK] Kolom '{column}' toegevoegd")
            except psycopg2.Error as e:
                print(f"   [FOUT] Kon kolom '{column}' niet toevoegen: {e}")
                conn.rollback()
                raise
        
        # Commit wijzigingen
        conn.commit()
        print("   [OK] Wijzigingen gecommit")
        
        # Verifieer
        print("\n[4/4] Verificatie...")
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'orders' 
            AND column_name IN ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content')
            ORDER BY column_name
        """)
        columns = cur.fetchall()
        
        print("   [OK] UTM kolommen in orders tabel:")
        for col_name, col_type in columns:
            print(f"      - {col_name}: {col_type}")
        
        cur.close()
        conn.close()
        
        print("\n" + "="*80)
        print("SUCCES: Migratie voltooid!")
        print("="*80)
        
    except Exception as e:
        print(f"\n[FOUT] Migratie gefaald: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    migrate_utm_columns()
