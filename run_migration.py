import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

# Laad .env bestand
load_dotenv()

# Haal DATABASE_URL op
database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("ERROR: DATABASE_URL niet gevonden in environment")
    exit(1)

# Lees migratiebestand
migration_file = Path("database/migrations/004_notities_en_adres.sql")
if not migration_file.exists():
    print(f"ERROR: Migratiebestand niet gevonden: {migration_file}")
    exit(1)

with open(migration_file, "r") as f:
    migration_sql = f.read()

# Verbind met database
conn = None
try:
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    
    # Voer elke ALTER TABLE statement uit
    statements = [s.strip() for s in migration_sql.split(";") if s.strip() and not s.strip().startswith("--")]
    
    print("Uitvoeren migratie...")
    for statement in statements:
        if statement:
            try:
                cur.execute(statement)
                conn.commit()
                # Extract kolom naam uit statement
                if "ADD COLUMN" in statement:
                    col_name = statement.split("ADD COLUMN IF NOT EXISTS")[1].strip().split()[0]
                    table_name = statement.split("ALTER TABLE")[1].split()[0]
                    print(f"✓ Kolom {col_name} toegevoegd aan tabel {table_name}")
            except Exception as e:
                print(f"Fout bij uitvoeren statement: {e}")
                print(f"Statement: {statement}")
                conn.rollback()
    
    print("\nMigratie voltooid!")
    
except Exception as e:
    print(f"ERROR: {e}")
    if conn:
        conn.rollback()
    exit(1)
finally:
    if conn:
        cur.close()
        conn.close()
