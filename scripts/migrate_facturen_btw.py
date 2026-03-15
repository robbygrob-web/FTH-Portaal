"""
Migratie script voor twee database wijzigingen:
1. Tabel facturen samenvoegen in orders
2. Tabel btw_tarieven aanmaken + koppelen aan artikelen

Gebruik:
  python migrate_facturen_btw.py        → alleen analyse (geen wijzigingen)
  python migrate_facturen_btw.py --run  → volledige migratie uitvoeren
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

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


def analyze_facturen_orders():
    """Analyseer facturen tabel en print records met order_id"""
    print("\n" + "="*80)
    print("STAP 1: ANALYSE - Facturen records")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        # Haal alle facturen op met order_id
        cur.execute("""
            SELECT 
                id,
                factuurnummer,
                factuurdatum,
                betalingsstatus,
                order_id,
                totaal_bedrag,
                klant_id
            FROM facturen
            ORDER BY factuurdatum DESC
        """)
        
        facturen = cur.fetchall()
        
        print(f"\n[INFO] Gevonden {len(facturen)} factuur record(s):\n")
        print(f"{'ID':<40} {'Factuurnummer':<20} {'Datum':<12} {'Status':<15} {'Order ID':<40}")
        print("-" * 150)
        
        for f in facturen:
            f_id, f_nummer, f_datum, f_status, o_id, f_bedrag, k_id = f
            f_datum_str = str(f_datum) if f_datum else 'NULL'
            o_id_str = str(o_id) if o_id else 'NULL'
            print(f"{str(f_id):<40} {str(f_nummer):<20} {f_datum_str:<12} {str(f_status):<15} {o_id_str:<40}")
        
        # Check welke kolommen in facturen zitten maar niet in orders
        print("\n" + "="*80)
        print("STAP 1: ANALYSE - Kolommen vergelijking")
        print("="*80)
        
        cur.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'facturen' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        facturen_cols = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
        
        cur.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'orders' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        orders_cols = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
        
        missing_cols = []
        for col_name, (col_type, col_default) in facturen_cols.items():
            if col_name not in orders_cols:
                # Skip standaard kolommen die niet gemigreerd hoeven
                if col_name not in ['id', 'created_at', 'updated_at', 'odoo_id']:
                    missing_cols.append((col_name, col_type, col_default))
        
        print(f"\n[INFO] Kolommen in facturen die NIET in orders zitten:")
        if missing_cols:
            for col_name, col_type, col_default in missing_cols:
                default_str = f" DEFAULT {col_default}" if col_default else ""
                print(f"  - {col_name}: {col_type}{default_str}")
        else:
            print("  (geen)")
        
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


def add_factuur_columns_to_orders():
    """Voeg factuur kolommen toe aan orders tabel"""
    print("\n" + "="*80)
    print("STAP 2: Kolommen toevoegen aan orders")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Kolommen die toegevoegd moeten worden
        columns_to_add = [
            ('factuurnummer', 'VARCHAR(50)'),
            ('factuurdatum', 'DATE'),
            ('referentie', 'VARCHAR(255)'),
            ('mollie_payment_id', 'VARCHAR(255)'),
            ('mollie_payment_url', 'VARCHAR(255)'),
            ('mollie_checkout_url', 'TEXT'),
            ('betaald_op', 'TIMESTAMP WITHOUT TIME ZONE'),
            ('openstaand_bedrag', 'NUMERIC(10,2) DEFAULT 0.00'),
            ('valuta_code', 'VARCHAR(3) DEFAULT \'EUR\''),
        ]
        
        # Check welke kolommen al bestaan
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'orders' AND table_schema = 'public'
        """)
        existing_columns = {row[0] for row in cur.fetchall()}
        
        added_count = 0
        for col_name, col_def in columns_to_add:
            if col_name not in existing_columns:
                try:
                    cur.execute(f"""
                        ALTER TABLE orders 
                        ADD COLUMN IF NOT EXISTS {col_name} {col_def}
                    """)
                    print(f"   [OK] Kolom '{col_name}' toegevoegd")
                    added_count += 1
                except psycopg2.Error as e:
                    print(f"   [FOUT] Kon kolom '{col_name}' niet toevoegen: {e}")
                    conn.rollback()
                    raise
            else:
                print(f"   [INFO] Kolom '{col_name}' bestaat al, overgeslagen")
        
        conn.commit()
        print(f"\n[OK] {added_count} kolom(men) toegevoegd aan orders tabel")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FOUT] Kolommen toevoegen gefaald: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def migrate_facturen_data():
    """Migreer data van facturen naar orders"""
    print("\n" + "="*80)
    print("STAP 3: Data migreren van facturen naar orders")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Update orders met factuur data
        cur.execute("""
            UPDATE orders 
            SET
                factuurnummer = f.factuurnummer,
                factuurdatum = f.factuurdatum,
                referentie = f.referentie,
                betaal_status = f.betalingsstatus,
                mollie_payment_id = f.mollie_payment_id,
                mollie_payment_url = f.mollie_payment_url,
                mollie_checkout_url = f.mollie_checkout_url,
                betaald_op = f.betaald_op,
                openstaand_bedrag = f.openstaand_bedrag,
                valuta_code = f.valuta_code
            FROM facturen f 
            WHERE f.order_id = orders.id
        """)
        
        updated_count = cur.rowcount
        conn.commit()
        
        print(f"\n[OK] {updated_count} order(s) geüpdatet met factuur data")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FOUT] Data migratie gefaald: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)


def migrate_betalingen_fk():
    """Migreer betalingen.factuur_id naar betalingen.order_id"""
    print("\n" + "="*80)
    print("STAP 4: betalingen foreign key migreren")
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
        
        # Vul order_id via facturen join
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
        
        # Zoek FK constraint naam
        cur.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'betalingen'
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name LIKE '%factuur_id%'
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
        
        # Drop factuur_id kolom
        cur.execute("""
            ALTER TABLE betalingen 
            DROP COLUMN IF EXISTS factuur_id
        """)
        print("   [OK] Kolom 'factuur_id' verwijderd uit betalingen")
        
        conn.commit()
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FOUT] betalingen FK migratie gefaald: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)


def drop_facturen_table():
    """Drop facturen tabel (alleen handmatig aanroepen!)"""
    print("\n" + "="*80)
    print("WAARSCHUWING: DROP facturen tabel")
    print("="*80)
    print("\n⚠️  Je staat op het punt de facturen tabel te verwijderen!")
    print("   Zorg ervoor dat alle data succesvol is gemigreerd naar orders.")
    
    response = input("\nWeet je zeker dat je door wilt gaan? (typ 'JA' om te bevestigen): ")
    if response != 'JA':
        print("\n[INFO] Drop geannuleerd")
        return
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        cur.execute("DROP TABLE IF EXISTS facturen CASCADE")
        conn.commit()
        
        print("\n[OK] facturen tabel verwijderd")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FOUT] Drop gefaald: {e}")
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
    print("MIGRATIE: Facturen -> Orders + BTW Tarieven")
    print("="*80)
    
    if '--run' not in sys.argv:
        # Alleen analyse - geen migratie
        print("\n[INFO] Analyse modus - geen wijzigingen worden uitgevoerd")
        print("       Gebruik 'python migrate_facturen_btw.py --run' voor volledige migratie\n")
        analyze_facturen_orders()
        print("\n" + "="*80)
        print("ANALYSE VOLTOOID")
        print("="*80)
        print("\nGebruik 'python migrate_facturen_btw.py --run' om migratie uit te voeren.")
    else:
        # Volledige migratie
        print("\n[INFO] Migratie modus - wijzigingen worden uitgevoerd\n")
        
        # DEEL 1 - Facturen → Orders
        add_factuur_columns_to_orders()
        migrate_facturen_data()
        migrate_betalingen_fk()
        
        # DEEL 2 - BTW tarieven
        create_btw_tarieven_table()
        insert_default_btw_tarieven()
        add_btw_tarief_to_artikelen()
        
        print("\n" + "="*80)
        print("MIGRATIE VOLTOOID")
        print("="*80)
        print("\n⚠️  Let op: facturen tabel bestaat nog!")
        print("   Roep drop_facturen_table() handmatig aan om te droppen.")


if __name__ == "__main__":
    main()
