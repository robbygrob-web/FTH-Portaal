"""
Script om recente orders te controleren in de database.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

# Publieke Railway database URL
DATABASE_URL = "postgresql://postgres:bHmvLbuqHOvoAmZfYzWblUQERHnwdaBm@metro.proxy.rlwy.net:18535/railway"

conn = None
try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Voer query uit
    cur.execute("""
        SELECT ordernummer, created_at as aangemaakt_op, status 
        FROM orders 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    
    rows = cur.fetchall()
    
    # Toon resultaten
    print("=" * 80)
    print("LAATSTE 10 ORDERS")
    print("=" * 80)
    print(f"{'Ordernummer':<40} {'Aangemaakt op':<30} {'Status':<10}")
    print("-" * 80)
    
    for row in rows:
        ordernummer = row['ordernummer'] or 'N/A'
        aangemaakt_op = str(row['aangemaakt_op']) if row['aangemaakt_op'] else 'N/A'
        status = row['status'] or 'N/A'
        print(f"{ordernummer:<40} {aangemaakt_op:<30} {status:<10}")
    
    print("=" * 80)
    print(f"Totaal: {len(rows)} orders gevonden")
    print("=" * 80)
    
    cur.close()
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    if conn:
        conn.close()
