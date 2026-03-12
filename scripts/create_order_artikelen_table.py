"""
Script om order_artikelen tabel aan te maken in PostgreSQL.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Voeg project root toe aan Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Laad environment variabelen
load_dotenv()

import psycopg2


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "DATABASE_URL niet gevonden in environment variabelen.\n"
            "Zorg ervoor dat DATABASE_URL is ingesteld in .env of als environment variabele."
        )
    return database_url


def main():
    """Maak order_artikelen tabel aan"""
    print("=" * 60)
    print("AANMAKEN ORDER_ARTIKELEN TABEL")
    print("=" * 60)
    
    # Connect naar PostgreSQL
    print("\n[1/2] Verbinden met PostgreSQL...")
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        print("  [OK] PostgreSQL verbinding succesvol")
    except Exception as e:
        print(f"  [ERROR] Fout bij PostgreSQL verbinding: {e}")
        return
    
    try:
        # Check of tabel al bestaat
        print("\n[2/2] Controleren of tabel bestaat...")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'order_artikelen'
            );
        """)
        exists = cur.fetchone()[0]
        
        if exists:
            print("  [WARNING] Tabel 'order_artikelen' bestaat al")
            response = input("  Wil je de tabel verwijderen en opnieuw aanmaken? (ja/nee): ")
            if response.lower() == 'ja':
                print("  Verwijderen bestaande tabel...")
                cur.execute("DROP TABLE IF EXISTS order_artikelen CASCADE;")
                conn.commit()
                print("  [OK] Tabel verwijderd")
            else:
                print("  Tabel blijft bestaan")
                return
        
        # Maak tabel aan
        print("  Aanmaken order_artikelen tabel...")
        cur.execute("""
            CREATE TABLE order_artikelen (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                
                -- Relaties
                order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                artikel_id UUID REFERENCES artikelen(id) ON DELETE SET NULL,
                
                -- Orderline informatie
                naam VARCHAR(500) NOT NULL,
                aantal DECIMAL(10, 2) NOT NULL DEFAULT 1.00,
                prijs_excl DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                btw_pct DECIMAL(5, 2) NOT NULL DEFAULT 9.00,
                btw_bedrag DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                prijs_incl DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                
                -- Odoo sync (tijdelijk)
                odoo_id INTEGER UNIQUE,
                
                CONSTRAINT order_artikelen_order_id_fk FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                CONSTRAINT order_artikelen_artikel_id_fk FOREIGN KEY (artikel_id) REFERENCES artikelen(id) ON DELETE SET NULL
            );
        """)
        
        # Maak indexes aan
        cur.execute("CREATE INDEX idx_order_artikelen_order_id ON order_artikelen(order_id);")
        cur.execute("CREATE INDEX idx_order_artikelen_artikel_id ON order_artikelen(artikel_id);")
        cur.execute("CREATE INDEX idx_order_artikelen_odoo_id ON order_artikelen(odoo_id);")
        
        # Voeg comment toe
        cur.execute("COMMENT ON TABLE order_artikelen IS 'Order regels (artikelen per order)';")
        
        conn.commit()
        print("  [OK] Tabel 'order_artikelen' succesvol aangemaakt")
        print("  [OK] Indexes aangemaakt")
        print("  [OK] Comments toegevoegd")
        
        print("\n" + "=" * 60)
        print("TABEL AANGEMAAKT")
        print("=" * 60)
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Fout tijdens aanmaken tabel: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
