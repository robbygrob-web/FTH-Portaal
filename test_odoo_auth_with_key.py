"""
ISOLATED ODOO AUTHENTICATION TEST WITH API KEY PARAMETER
=========================================================
Test Odoo connection with a specific API key to verify the authenticate() method works.
This allows testing with the correct API key without modifying .env.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
import xmlrpc.client

# Load .env for base config
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Get base config from .env
import os
ODOO_BASE_URL = os.getenv("ODOO_BASE_URL", "https://treatlab-test.odoo.com")
ODOO_DB = os.getenv("ODOO_DB", "treatlab-test")
ODOO_LOGIN = os.getenv("ODOO_LOGIN", "robbygrob@gmail.com")

# API key from working script (can be overridden via command line)
API_KEY_FROM_WORKING_SCRIPT = "418105568a3df8d4e71cd4244242ce4b09c220dd"

# Allow API key to be passed as command line argument
if len(sys.argv) > 1:
    test_api_key = sys.argv[1]
else:
    test_api_key = API_KEY_FROM_WORKING_SCRIPT

print("=" * 80)
print("TESTING ODOO AUTHENTICATION WITH SPECIFIC API KEY")
print("=" * 80)
print(f"\nConfiguration:")
print(f"  URL: {ODOO_BASE_URL}")
print(f"  DB: {ODOO_DB}")
print(f"  Username: {ODOO_LOGIN}")
print(f"  API Key: {test_api_key[:20]}...{test_api_key[-10:]}")
print(f"\nEndpoint: {ODOO_BASE_URL}/xmlrpc/2/common")

print("\n" + "=" * 80)
print("Testing XML-RPC authenticate() method (from working script)")
print("=" * 80)

try:
    common = xmlrpc.client.ServerProxy(f"{ODOO_BASE_URL}/xmlrpc/2/common", allow_none=True)
    
    print(f"\n[TEST] Calling authenticate() with:")
    print(f"  - Database: {ODOO_DB}")
    print(f"  - Username: {ODOO_LOGIN}")
    print(f"  - API Key: {test_api_key[:20]}...{test_api_key[-10:]}")
    print(f"  - User Agent: {{}}")
    
    uid = common.authenticate(ODOO_DB, ODOO_LOGIN, test_api_key, {})
    
    if uid:
        print(f"\n[SUCCESS] authenticate() returned UID: {uid}")
        
        # Get version info
        try:
            version = common.version()
            print(f"[INFO] Odoo Version: {version.get('server_version', 'unknown')}")
        except Exception as e:
            print(f"[INFO] Could not get version: {e}")
        
        print("\n" + "=" * 80)
        print("CONCLUSION")
        print("=" * 80)
        print("[RESULT] XML-RPC authenticate() method: SUCCESS")
        print("[RESULT] Local Odoo auth working: YES (with correct API key)")
        print("[NOTE] The authenticate() method works, but the API key in .env may be incorrect.")
        sys.exit(0)
    else:
        print(f"\n[FAIL] authenticate() returned False/None")
        print("\n" + "=" * 80)
        print("CONCLUSION")
        print("=" * 80)
        print("[RESULT] XML-RPC authenticate() method: FAILED")
        print("[RESULT] Local Odoo auth working: NO")
        print("[NOTE] Even with the API key from working script, authentication failed.")
        print("[NOTE] This suggests the API key may have expired or credentials changed.")
        sys.exit(1)
        
except xmlrpc.client.Fault as e:
    print(f"\n[ERROR] XML-RPC Fault: {e.faultCode} - {e.faultString}")
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print(f"[RESULT] XML-RPC authenticate() method: FAILED (Fault)")
    print(f"[ERROR] {e.faultCode}: {e.faultString}")
    sys.exit(1)
except Exception as e:
    print(f"\n[ERROR] Exception: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print(f"[RESULT] XML-RPC authenticate() method: FAILED (Exception)")
    print(f"[ERROR] {e}")
    sys.exit(1)
