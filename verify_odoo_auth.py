"""
Minimal verification test for app/odoo_client.py
Tests the current implementation as-is without modifications
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env exactly like main.py does
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Import OdooClient after loading .env
from app.odoo_client import get_odoo_client

try:
    client = get_odoo_client()
    uid = client.uid
    print(f"UID: {uid}")
    print(f"AUTH_SUCCESS: true")
    sys.exit(0)
except Exception as e:
    print(f"UID: None")
    print(f"AUTH_SUCCESS: false")
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
