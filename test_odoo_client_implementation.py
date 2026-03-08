"""
Test the actual OdooClient implementation from the codebase
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env exactly like main.py does
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

print("=" * 80)
print("TESTING ODOOCLIENT IMPLEMENTATION FROM CODEBASE")
print("=" * 80)

# Import after loading .env
from app.odoo_client import get_odoo_client
from app.config import ODOO_BASE_URL, ODOO_DB, ODOO_LOGIN

print(f"\nEnvironment variables:")
print(f"  ODOO_BASE_URL = {ODOO_BASE_URL}")
print(f"  ODOO_DB = {ODOO_DB}")
print(f"  ODOO_LOGIN = {ODOO_LOGIN}")

print("\n" + "=" * 80)
print("Initializing OdooClient (this will call _login() with authenticate())")
print("=" * 80)

try:
    client = get_odoo_client()
    
    print(f"\n[SUCCESS] OdooClient initialized")
    print(f"  Client UID: {client.uid}")
    print(f"  Common URL: {client.common_url}")
    print(f"  Object URL: {client.object_url}")
    
    # Test execute_kw to verify full flow works
    print("\n" + "=" * 80)
    print("Testing execute_kw() to verify full XML-RPC flow")
    print("=" * 80)
    
    user_info = client.execute_kw(
        'res.users',
        'read',
        [client.uid],
        {'fields': ['name', 'login']}
    )
    
    print(f"\n[SUCCESS] execute_kw() works")
    print(f"  User info: {user_info}")
    
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("[RESULT] OdooClient implementation: SUCCESS")
    print(f"[RESULT] Auth method: XML-RPC authenticate()")
    print(f"[RESULT] Endpoint: {client.common_url}")
    print(f"[RESULT] Login result: UID {client.uid}")
    print("[RESULT] Local Odoo authentication now works in this project: YES")
    sys.exit(0)
    
except RuntimeError as e:
    print(f"\n[FAIL] RuntimeError: {e}")
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("[RESULT] OdooClient implementation: FAILED (RuntimeError)")
    print(f"[ERROR] {e}")
    print("[RESULT] Local Odoo authentication now works in this project: NO")
    print("[NOTE] This may be due to incorrect API key in .env file")
    sys.exit(1)
except Exception as e:
    print(f"\n[FAIL] Exception: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("[RESULT] OdooClient implementation: FAILED (Exception)")
    print(f"[ERROR] {e}")
    print("[RESULT] Local Odoo authentication now works in this project: NO")
    sys.exit(1)
