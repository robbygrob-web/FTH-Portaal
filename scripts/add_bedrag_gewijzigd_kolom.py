import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
database_url = os.getenv("DATABASE_URL")
conn = psycopg2.connect(database_url)
cur = conn.cursor()
cur.execute("""
    ALTER TABLE orders 
    ADD COLUMN IF NOT EXISTS 
    bedrag_gewijzigd_op TIMESTAMP
""")
conn.commit()
print("Kolom bedrag_gewijzigd_op toegevoegd")
cur.close()
conn.close()
