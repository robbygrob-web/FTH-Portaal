import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

# Laad .env bestand
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Haal DATABASE_URL op en vervang internal URL indien nodig
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL niet gevonden in environment variabelen")

# Als interne URL, vervang met publieke URL
if "railway.internal" in database_url:
    database_url = database_url.replace(
        "postgres.railway.internal:5432",
        "metro.proxy.rlwy.net:18535"
    )
    # Vervang *** met echte password indien nodig
    if "***" in database_url:
        database_url = database_url.replace("***", "bHmvLbuqHOvoAmZfYzWblUQERHnwdaBm")

conn = psycopg2.connect(database_url)
cur = conn.cursor()

# Alle tabellen + record counts
cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' ORDER BY table_name
""")
tables = [r[0] for r in cur.fetchall()]

output = ["# FTH Database Schema\n"]

for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position
    """, (table,))
    cols = cur.fetchall()
    
    cur.execute("""
        SELECT kcu.column_name, ccu.table_name, ccu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s
    """, (table,))
    fks = {r[0]: f"{r[1]}.{r[2]}" for r in cur.fetchall()}
    
    output.append(f"## {table} ({count} records)")
    output.append("| kolom | type | nullable | default | FK |")
    output.append("|-------|------|----------|---------|----|")
    for col in cols:
        fk = f"-> {fks[col[0]]}" if col[0] in fks else ""
        nullable = "ja" if col[1] == "YES" else "nee"
        default = col[3] or ""
        output.append(f"| {col[0]} | {col[1]} | {nullable} | {default} | {fk} |")
    output.append("")

# Redundantie: kolommen die in 2+ tabellen voorkomen
cur.execute("""
    SELECT column_name, array_agg(table_name ORDER BY table_name)
    FROM information_schema.columns
    WHERE table_schema = 'public'
    GROUP BY column_name
    HAVING COUNT(*) > 1
    ORDER BY column_name
""")
dupes = cur.fetchall()

output.append("## Redundantie signalen")
output.append("| kolom | gevonden in |")
output.append("|-------|------------|")
for col, tbls in dupes:
    # tbls is een PostgreSQL array, converteer naar Python list
    if isinstance(tbls, list):
        tbls_str = ', '.join(tbls)
    else:
        # Als het een string is (sommige drivers), split op komma
        tbls_str = str(tbls).replace('{', '').replace('}', '')
    output.append(f"| {col} | {tbls_str} |")

result = "\n".join(output)
# Print met UTF-8 encoding voor Windows console
import sys
if sys.stdout.encoding != 'utf-8':
    try:
        print(result.encode('utf-8', errors='replace').decode('utf-8'))
    except:
        print(result)
else:
    print(result)

# Zorg dat docs directory bestaat
docs_dir = Path(__file__).parent.parent / "docs"
docs_dir.mkdir(exist_ok=True)

with open(docs_dir / "database_schema.md", "w", encoding="utf-8") as f:
    f.write(result)

print("\n[OK] Opgeslagen in docs/database_schema.md")
cur.close()
conn.close()
