"""
Migratie script om mail_logs tabel uit te breiden met nieuwe velden.
Voegt velden toe voor mail én WhatsApp ondersteuning.
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


def migrate_mail_logs():
    """Voeg nieuwe kolommen toe aan mail_logs tabel"""
    print("="*80)
    print("Mail Logs Tabel Uitbreiding")
    print("="*80)
    
    try:
        # Verbind met database
        print("\n[1/5] Verbinden met database...")
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        print("   [OK] Verbonden")
        
        # Check of kolommen al bestaan
        print("\n[2/5] Controleren welke kolommen al bestaan...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'mail_logs'
        """)
        existing_columns = [row[0] for row in cur.fetchall()]
        
        # Definieer nieuwe kolommen die toegevoegd moeten worden
        new_columns = [
            {
                'name': 'richting',
                'type': 'VARCHAR(20)',
                'description': 'inkomend of uitgaand'
            },
            {
                'name': 'kanaal',
                'type': 'VARCHAR(20)',
                'description': 'mail of whatsapp'
            },
            {
                'name': 'naar',
                'type': 'VARCHAR(255)',
                'description': 'ontvanger emailadres'
            },
            {
                'name': 'order_id',
                'type': 'UUID REFERENCES orders(id) ON DELETE SET NULL',
                'description': 'gerelateerde order'
            },
            {
                'name': 'template_naam',
                'type': 'VARCHAR(100)',
                'description': 'welke template gebruikt'
            },
            {
                'name': 'status',
                'type': 'VARCHAR(20)',
                'description': 'verzonden, mislukt, ontvangen'
            },
            {
                'name': 'verzonden_op',
                'type': 'TIMESTAMP WITH TIME ZONE',
                'description': 'wanneer verzonden'
            }
        ]
        
        columns_to_add = [col for col in new_columns if col['name'] not in existing_columns]
        
        if not columns_to_add:
            print("   [OK] Alle nieuwe kolommen bestaan al, geen migratie nodig")
            cur.close()
            conn.close()
            print("\n" + "="*80)
            print("Klaar - Geen wijzigingen nodig")
            print("="*80)
            return
        
        print(f"   [INFO] {len(columns_to_add)} kolom(men) toe te voegen:")
        for col in columns_to_add:
            print(f"      - {col['name']} ({col['description']})")
        
        # Voeg kolommen toe
        print("\n[3/5] Nieuwe kolommen toevoegen...")
        for col in columns_to_add:
            try:
                # Voor foreign key constraints moet je eerst de kolom toevoegen, dan de constraint
                if 'REFERENCES' in col['type']:
                    # Split type: eerst kolom type, dan constraint
                    parts = col['type'].split(' REFERENCES ')
                    column_type = parts[0]
                    constraint = parts[1] if len(parts) > 1 else None
                    
                    # Voeg kolom toe zonder constraint eerst
                    cur.execute(f"""
                        ALTER TABLE mail_logs 
                        ADD COLUMN IF NOT EXISTS {col['name']} {column_type}
                    """)
                    print(f"   [OK] Kolom '{col['name']}' toegevoegd")
                    
                    # Voeg foreign key constraint toe als die nog niet bestaat
                    if constraint:
                        constraint_name = f"fk_mail_logs_{col['name']}"
                        try:
                            cur.execute(f"""
                                ALTER TABLE mail_logs 
                                ADD CONSTRAINT {constraint_name} 
                                FOREIGN KEY ({col['name']}) REFERENCES {constraint}
                            """)
                            print(f"   [OK] Foreign key constraint toegevoegd voor '{col['name']}'")
                        except psycopg2.ProgrammingError as e:
                            if "already exists" in str(e) or "duplicate" in str(e).lower():
                                print(f"   [INFO] Foreign key constraint voor '{col['name']}' bestaat al")
                            else:
                                raise
                else:
                    # Normale kolom zonder foreign key
                    cur.execute(f"""
                        ALTER TABLE mail_logs 
                        ADD COLUMN IF NOT EXISTS {col['name']} {col['type']}
                    """)
                    print(f"   [OK] Kolom '{col['name']}' toegevoegd")
            except psycopg2.Error as e:
                print(f"   [FOUT] Kon kolom '{col['name']}' niet toevoegen: {e}")
                conn.rollback()
                raise
        
        # Commit wijzigingen
        conn.commit()
        print("   [OK] Wijzigingen gecommit")
        
        # Verifieer
        print("\n[4/5] Verificatie...")
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns 
            WHERE table_name = 'mail_logs'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        print("   [OK] Kolommen in mail_logs tabel:")
        for col_name, col_type, max_length in columns:
            length_info = f"({max_length})" if max_length else ""
            print(f"      - {col_name}: {col_type}{length_info}")
        
        # Check foreign keys
        print("\n[5/5] Foreign key constraints controleren...")
        cur.execute("""
            SELECT
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'mail_logs'
        """)
        foreign_keys = cur.fetchall()
        
        if foreign_keys:
            print("   [OK] Foreign key constraints:")
            for fk_name, col_name, ref_table, ref_col in foreign_keys:
                print(f"      - {col_name} -> {ref_table}.{ref_col}")
        else:
            print("   [INFO] Geen foreign key constraints gevonden")
        
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
    migrate_mail_logs()
