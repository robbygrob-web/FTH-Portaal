"""
Script om volledige order details te tonen.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Publieke Railway database URL
DATABASE_URL = "postgresql://postgres:bHmvLbuqHOvoAmZfYzWblUQERHnwdaBm@metro.proxy.rlwy.net:18535/railway"

conn = None
try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Voer query uit (gebruik created_at, niet aangemaakt_op)
    cur.execute("""
        SELECT * FROM orders ORDER BY created_at DESC LIMIT 3
    """)
    
    rows = cur.fetchall()
    
    # Toon resultaten
    print("=" * 80)
    print("LAATSTE 3 ORDERS - ALLE VELDEN")
    print("=" * 80)
    
    for idx, row in enumerate(rows, 1):
        print(f"\n--- ORDER {idx} ---")
        print("-" * 80)
        
        # Toon alle velden
        for key, value in row.items():
            if value is not None:
                # Format waarde voor leesbaarheid
                if isinstance(value, str) and len(value) > 100:
                    value_str = value[:100] + "..."
                else:
                    value_str = str(value)
                print(f"  {key:<30} = {value_str}")
            else:
                print(f"  {key:<30} = NULL")
        
        print()
    
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
