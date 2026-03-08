"""
Minimal verification test for Odoo connection
Uses existing OdooClient implementation
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env exactly like main.py does
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Import after loading .env
from app.odoo_client import get_odoo_client
from app.config import ODOO_BASE_URL

try:
    # Get client (this performs authentication)
    client = get_odoo_client()
    
    # Extract endpoint from client
    xmlrpc_endpoint = client.common_url
    
    # Print results
    print(f"ODOO_BASE_URL: {ODOO_BASE_URL}")
    print(f"XML-RPC endpoint: {xmlrpc_endpoint}")
    print(f"UID: {client.uid}")
    print(f"AUTH_SUCCESS: true")
    
    sys.exit(0)
    
except Exception as e:
    # Print failure details
    print(f"ODOO_BASE_URL: {ODOO_BASE_URL}")
    print(f"XML-RPC endpoint: {getattr(getattr(sys.modules.get('app.odoo_client'), 'OdooClient', None), 'common_url', None) if hasattr(sys.modules.get('app.odoo_client'), 'OdooClient') else 'N/A'}")
    print(f"UID: None")
    print(f"AUTH_SUCCESS: false")
    print(f"Exception: {type(e).__name__}: {e}")
    sys.exit(1)
