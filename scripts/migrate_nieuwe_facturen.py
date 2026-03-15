"""
Migratie script voor nieuwe slanke facturen tabel + BTW tarieven:
1. Maak facturen_nieuw tabel aan (slanke structuur)
2. Migreer facturen data naar facturen_nieuw
3. Migreer betalingen FK
4. Maak BTW tarieven tabel aan
5. Koppel BTW tarieven aan artikelen

Gebruik:
  python migrate_nieuwe_facturen.py        → alleen analyse (geen wijzigingen)
  python migrate_nieuwe_facturen.py --run  → volledige migratie uitvoeren
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


def analyze():
    """Analyseer huidige facturen tabel structuur en records"""
    print("\n" + "="*80)
    print("STAP 1: ANALYSE - Facturen tabel")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        # Print tabel structuur
        print("\n[INFO] Huidige facturen tabel structuur:")
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'facturen' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        print(f"\n{'Kolom':<30} {'Type':<25} {'Nullable':<10} {'Default'}")
        print("-" * 100)
        for col_name, col_type, nullable, default in columns:
            default_str = str(default)[:30] if default else ""
            print(f"{col_name:<30} {col_type:<25} {nullable:<10} {default_str}")
        
        # Print records met order_id
        print("\n[INFO] Records met order_id (worden gemigreerd):")
        cur.execute("""
            SELECT 
                id,
                factuurnummer,
                factuurdatum,
                order_id,
                totaal_bedrag
            FROM facturen
            WHERE order_id IS NOT NULL
            ORDER BY factuurdatum DESC
        """)
        records_with_order = cur.fetchall()
        
        if records_with_order:
            print(f"\n{'ID':<40} {'Factuurnummer':<20} {'Datum':<12} {'Order ID':<40} {'Bedrag'}")
            print("-" * 120)
            for r in records_with_order:
                r_id, r_nummer, r_datum, o_id, r_bedrag = r
                r_datum_str = str(r_datum) if r_datum else 'NULL'
                print(f"{str(r_id):<40} {str(r_nummer):<20} {r_datum_str:<12} {str(o_id):<40} {str(r_bedrag)}")
            print(f"\n[INFO] Totaal: {len(records_with_order)} record(s) met order_id")
        else:
            print("\n[INFO] Geen records met order_id gevonden")
        
        # Print records zonder order_id
        print("\n[INFO] Records zonder order_id (worden NIET gemigreerd):")
        cur.execute("""
            SELECT COUNT(*) FROM facturen WHERE order_id IS NULL
        """)
        records_without_order = cur.fetchone()[0]
        
        if records_without_order > 0:
            print(f"[WAARSCHUWING] {records_without_order} record(s) zonder order_id gevonden")
            print("              Deze worden NIET gemigreerd naar facturen_nieuw")
        else:
            print("[OK] Geen records zonder order_id")
        
        cur.close()
        conn.close()
        
        print("\n" + "="*80)
        print("ANALYSE VOLTOOID")
        print("="*80)
        
    except Exception as e:
        print(f"\n[FOUT] Analyse gefaald: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def create_nieuwe_facturen_table():
    """Maak nieuwe slanke facturen_nieuw tabel aan"""
    print("\n" + "="*80)
    print("STAP 2: Nieuwe facturen tabel aanmaken")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS facturen_nieuw (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                order_id UUID NOT NULL REFERENCES orders(id),
                factuurnummer VARCHAR(50) NOT NULL UNIQUE,
                factuurdatum DATE NOT NULL,
                pdf_url TEXT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("\n[OK] Tabel 'facturen_nieuw' aangemaakt")
        
        # Verifieer
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'facturen_nieuw' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        print("\n[INFO] Kolommen in facturen_nieuw:")
        for col_name, col_type in columns:
            print(f"  - {col_name}: {col_type}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FOUT] Tabel aanmaken gefaald: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)


def migrate_betalingen_fk():
    """Migreer betalingen foreign key van facturen naar order_id en facturen_nieuw"""
    print("\n" + "="*80)
    print("STAP 3: betalingen foreign key migreren")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Check of betalingen tabel bestaat en of er records zijn
        cur.execute("""
            SELECT COUNT(*) FROM betalingen
        """)
        betalingen_count = cur.fetchone()[0]
        print(f"\n[INFO] Aantal betalingen records: {betalingen_count}")
        
        # Check of order_id kolom al bestaat
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'betalingen' AND column_name = 'order_id'
        """)
        if cur.fetchone():
            print("   [INFO] Kolom 'order_id' bestaat al in betalingen")
        else:
            # Voeg order_id kolom toe
            cur.execute("""
                ALTER TABLE betalingen 
                ADD COLUMN order_id UUID
            """)
            print("   [OK] Kolom 'order_id' toegevoegd aan betalingen")
        
        # Vul order_id via facturen join (als er records zijn)
        if betalingen_count > 0:
            cur.execute("""
                UPDATE betalingen 
                SET order_id = (
                    SELECT order_id 
                    FROM facturen 
                    WHERE facturen.id = betalingen.factuur_id
                )
                WHERE factuur_id IS NOT NULL
            """)
            updated_count = cur.rowcount
            print(f"   [OK] {updated_count} betaling(en) geüpdatet met order_id")
        
        # Zoek FK constraint naam op factuur_id
        cur.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'betalingen'
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name IN (
                SELECT constraint_name
                FROM information_schema.key_column_usage
                WHERE table_name = 'betalingen' AND column_name = 'factuur_id'
            )
        """)
        fk_constraint = cur.fetchone()
        
        if fk_constraint:
            constraint_name = fk_constraint[0]
            # Drop FK constraint
            cur.execute(f"""
                ALTER TABLE betalingen 
                DROP CONSTRAINT IF EXISTS {constraint_name}
            """)
            print(f"   [OK] Foreign key constraint '{constraint_name}' verwijderd")
        
        # Drop factuur_id kolom (oude FK naar facturen)
        cur.execute("""
            ALTER TABLE betalingen 
            DROP COLUMN IF EXISTS factuur_id
        """)
        print("   [OK] Kolom 'factuur_id' verwijderd uit betalingen")
        
        # Voeg nieuwe factuur_id kolom toe met FK naar facturen_nieuw (voor toekomstig gebruik)
        cur.execute("""
            ALTER TABLE betalingen 
            ADD COLUMN factuur_id UUID REFERENCES facturen_nieuw(id)
        """)
        print("   [OK] Nieuwe kolom 'factuur_id' toegevoegd met FK naar facturen_nieuw")
        
        conn.commit()
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FOUT] betalingen FK migratie gefaald: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)


def migrate_facturen_data():
    """Migreer data van facturen naar facturen_nieuw"""
    print("\n" + "="*80)
    print("STAP 4: Data migreren van facturen naar facturen_nieuw")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Migreer alleen records met order_id
        cur.execute("""
            INSERT INTO facturen_nieuw (order_id, factuurnummer, factuurdatum, created_at)
            SELECT 
                order_id,
                factuurnummer,
                factuurdatum,
                created_at
            FROM facturen
            WHERE order_id IS NOT NULL
        """)
        
        migrated_count = cur.rowcount
        conn.commit()
        
        print(f"\n[OK] {migrated_count} factuur record(s) gemigreerd naar facturen_nieuw")
        
        # Verifieer
        cur.execute("SELECT COUNT(*) FROM facturen_nieuw")
        new_count = cur.fetchone()[0]
        print(f"[INFO] Totaal records in facturen_nieuw: {new_count}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FOUT] Data migratie gefaald: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)


def drop_oude_facturen_table():
    """Hernoem facturen_nieuw naar facturen (alleen handmatig aanroepen!)"""
    print("\n" + "="*80)
    print("WAARSCHUWING: Hernoem facturen_nieuw naar facturen")
    print("="*80)
    print("\n[WAARSCHUWING] Je staat op het punt de oude facturen tabel te verwijderen")
    print("   en facturen_nieuw te hernoemen naar facturen.")
    print("   Zorg ervoor dat alle data succesvol is gemigreerd.")
    
    # Check voor --confirm flag voor niet-interactief gebruik
    if '--confirm' in sys.argv:
        response = 'JA'
        print("\n[INFO] --confirm flag gebruikt, hernoemen wordt uitgevoerd")
    else:
        try:
            response = input("\nWeet je zeker dat je door wilt gaan? (typ 'JA' om te bevestigen): ")
        except EOFError:
            print("\n[FOUT] Geen interactieve input beschikbaar")
            print("       Gebruik: python -c \"from scripts.migrate_nieuwe_facturen import drop_oude_facturen_table; import sys; sys.argv.append('--confirm'); drop_oude_facturen_table()\"")
            return
    
    if response != 'JA':
        print("\n[INFO] Hernoemen geannuleerd")
        return
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Drop oude facturen tabel
        cur.execute("DROP TABLE IF EXISTS facturen CASCADE")
        print("\n[OK] Oude 'facturen' tabel verwijderd")
        
        # Hernoem facturen_nieuw naar facturen
        cur.execute("ALTER TABLE facturen_nieuw RENAME TO facturen")
        print("[OK] 'facturen_nieuw' hernoemd naar 'facturen'")
        
        conn.commit()
        
        cur.close()
        conn.close()
        
        print("\n" + "="*80)
        print("SUCCES: facturen tabel succesvol vervangen")
        print("="*80)
        
    except Exception as e:
        print(f"\n[FOUT] Hernoemen gefaald: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)


def create_btw_tarieven_table():
    """Maak btw_tarieven tabel aan"""
    print("\n" + "="*80)
    print("STAP 6: BTW tarieven tabel aanmaken")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS btw_tarieven (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                naam VARCHAR(255) NOT NULL,
                percentage NUMERIC(5,2) NOT NULL,
                actief BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("\n[OK] Tabel 'btw_tarieven' aangemaakt")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FOUT] BTW tarieven tabel aanmaken gefaald: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)


def insert_default_btw_tarieven():
    """Voeg standaard BTW tarieven toe"""
    print("\n" + "="*80)
    print("STAP 7: Standaard BTW tarieven invoegen")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        tarieven = [
            ('Laag tarief', 9.00),
            ('Hoog tarief', 21.00),
            ('Nul tarief', 0.00),
        ]
        
        inserted_count = 0
        for naam, percentage in tarieven:
            # Check of tarief al bestaat
            cur.execute("""
                SELECT id FROM btw_tarieven WHERE naam = %s
            """, (naam,))
            
            if cur.fetchone():
                print(f"   [INFO] Tarief '{naam}' bestaat al, overgeslagen")
            else:
                cur.execute("""
                    INSERT INTO btw_tarieven (naam, percentage)
                    VALUES (%s, %s)
                """, (naam, percentage))
                inserted_count += 1
                print(f"   [OK] Tarief '{naam}' ({percentage}%) toegevoegd")
        
        conn.commit()
        print(f"\n[OK] {inserted_count} tarief(fen) toegevoegd")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FOUT] BTW tarieven invoegen gefaald: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)


def add_btw_tarief_to_artikelen():
    """Voeg btw_tarief_id kolom toe aan artikelen"""
    print("\n" + "="*80)
    print("STAP 8: btw_tarief_id toevoegen aan artikelen")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Check of kolom al bestaat
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'artikelen' AND column_name = 'btw_tarief_id'
        """)
        
        if cur.fetchone():
            print("\n[INFO] Kolom 'btw_tarief_id' bestaat al in artikelen")
        else:
            # Voeg kolom toe met foreign key
            cur.execute("""
                ALTER TABLE artikelen 
                ADD COLUMN btw_tarief_id UUID REFERENCES btw_tarieven(id)
            """)
            conn.commit()
            print("\n[OK] Kolom 'btw_tarief_id' toegevoegd aan artikelen")
            
            # Verifieer
            cur.execute("""
                SELECT COUNT(*) FROM artikelen WHERE btw_tarief_id IS NULL
            """)
            null_count = cur.fetchone()[0]
            print(f"[INFO] {null_count} artikel(en) hebben nog geen btw_tarief_id (NULL)")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FOUT] btw_tarief_id toevoegen gefaald: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)


def main():
    """Hoofdfunctie - voert migratie uit op basis van --run flag"""
    print("="*80)
    print("MIGRATIE: Nieuwe facturen tabel + BTW Tarieven")
    print("="*80)
    
    if '--run' not in sys.argv:
        # Alleen analyse - geen migratie
        print("\n[INFO] Analyse modus - geen wijzigingen worden uitgevoerd")
        print("       Gebruik 'python migrate_nieuwe_facturen.py --run' voor volledige migratie\n")
        analyze()
        print("\n" + "="*80)
        print("ANALYSE VOLTOOID")
        print("="*80)
        print("\nGebruik 'python migrate_nieuwe_facturen.py --run' om migratie uit te voeren.")
    else:
        # Volledige migratie
        print("\n[INFO] Migratie modus - wijzigingen worden uitgevoerd\n")
        
        # DEEL 1 - Nieuwe facturen tabel
        create_nieuwe_facturen_table()
        migrate_betalingen_fk()
        migrate_facturen_data()
        
        # DEEL 2 - BTW tarieven
        create_btw_tarieven_table()
        insert_default_btw_tarieven()
        add_btw_tarief_to_artikelen()
        
        print("\n" + "="*80)
        print("MIGRATIE VOLTOOID")
        print("="*80)
        print("\n[WAARSCHUWING] Let op: facturen_nieuw tabel bestaat nu naast oude facturen tabel")
        print("   Roep drop_oude_facturen_table() handmatig aan om te hernoemen.")


if __name__ == "__main__":
    main()
