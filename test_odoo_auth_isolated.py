"""
ISOLATED ODOO AUTHENTICATION TEST
==================================
Minimal test to verify Odoo connection used by this codebase.
Tests both JSON-RPC (current) and XML-RPC (alternative).

This test is completely isolated from routes, UI, order logic, Railway, deployment.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import requests
import xmlrpc.client

# ============================================================================
# STEP 1: Load .env exactly like main.py does
# ============================================================================
print("=" * 80)
print("STEP 1: Loading .env file")
print("=" * 80)
env_path = Path(__file__).parent / '.env'
print(f"Env file path: {env_path}")
print(f"Env file exists: {env_path.exists()}")

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print("[OK] load_dotenv() called")
else:
    print("[WARNING] .env file not found, using system environment variables")
    load_dotenv()  # Try to load from current directory anyway

# ============================================================================
# STEP 2: Read environment variables (same as app/config.py)
# ============================================================================
print("\n" + "=" * 80)
print("STEP 2: Reading environment variables")
print("=" * 80)

ODOO_BASE_URL = os.getenv("ODOO_BASE_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_LOGIN = os.getenv("ODOO_LOGIN")
ODOO_API_KEY = os.getenv("ODOO_API_KEY")

print(f"ODOO_BASE_URL = {ODOO_BASE_URL}")
print(f"ODOO_DB = {ODOO_DB}")
print(f"ODOO_LOGIN = {ODOO_LOGIN}")
print(f"ODOO_API_KEY = {'*' * min(len(ODOO_API_KEY or ''), 20)}..." if ODOO_API_KEY else "ODOO_API_KEY = None")

# Validate all required vars are present
missing = []
if not ODOO_BASE_URL:
    missing.append("ODOO_BASE_URL")
if not ODOO_DB:
    missing.append("ODOO_DB")
if not ODOO_LOGIN:
    missing.append("ODOO_LOGIN")
if not ODOO_API_KEY:
    missing.append("ODOO_API_KEY")

if missing:
    print(f"\n[ERROR] Missing required environment variables: {', '.join(missing)}")
    sys.exit(1)

print("[OK] All required environment variables present")

# ============================================================================
# STEP 3: Build endpoints (same as app/odoo_client.py)
# ============================================================================
print("\n" + "=" * 80)
print("STEP 3: Building Odoo endpoints")
print("=" * 80)

base_url_clean = ODOO_BASE_URL.rstrip('/')
jsonrpc_url = f"{base_url_clean}/jsonrpc"
xmlrpc_common_url = f"{base_url_clean}/xmlrpc/2/common"
xmlrpc_object_url = f"{base_url_clean}/xmlrpc/2/object"

print(f"Base URL (cleaned): {base_url_clean}")
print(f"JSON-RPC endpoint: {jsonrpc_url}")
print(f"XML-RPC common endpoint: {xmlrpc_common_url}")
print(f"XML-RPC object endpoint: {xmlrpc_object_url}")

# ============================================================================
# STEP 4: Test JSON-RPC (current implementation)
# ============================================================================
print("\n" + "=" * 80)
print("STEP 4: Testing JSON-RPC (current implementation)")
print("=" * 80)

jsonrpc_success = False
jsonrpc_uid = None
jsonrpc_status = None
jsonrpc_response = None
jsonrpc_error = None

try:
    print(f"\n[TEST] Sending JSON-RPC login request to: {jsonrpc_url}")
    
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "common",
            "method": "login",
            "args": [ODOO_DB, ODOO_LOGIN, ODOO_API_KEY]
        },
        "id": 1,
    }
    
    print(f"[TEST] Payload: {payload}")
    
    response = requests.post(jsonrpc_url, json=payload, timeout=10)
    jsonrpc_status = response.status_code
    
    print(f"[RESULT] HTTP Status Code: {jsonrpc_status}")
    print(f"[RESULT] Response URL: {response.url}")
    print(f"[RESULT] Response Headers: {dict(response.headers)}")
    
    response.raise_for_status()
    
    jsonrpc_response = response.json()
    print(f"[RESULT] Response Body: {jsonrpc_response}")
    
    if "error" in jsonrpc_response:
        jsonrpc_error = jsonrpc_response["error"]
        print(f"[ERROR] JSON-RPC error: {jsonrpc_error}")
    else:
        jsonrpc_uid = jsonrpc_response.get("result")
        if jsonrpc_uid:
            jsonrpc_success = True
            print(f"[SUCCESS] JSON-RPC login successful, UID: {jsonrpc_uid}")
        else:
            print(f"[FAIL] JSON-RPC login failed - no UID in result")
            print(f"[RESULT] Full response: {jsonrpc_response}")
            
except requests.exceptions.RequestException as e:
    jsonrpc_error = str(e)
    print(f"[ERROR] JSON-RPC request failed: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"[ERROR] Response status: {e.response.status_code}")
        print(f"[ERROR] Response text: {e.response.text[:500]}")
except Exception as e:
    jsonrpc_error = str(e)
    print(f"[ERROR] JSON-RPC unexpected error: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# STEP 5: Test XML-RPC (alternative implementation)
# ============================================================================
print("\n" + "=" * 80)
print("STEP 5: Testing XML-RPC (alternative implementation)")
print("=" * 80)

xmlrpc_login_success = False
xmlrpc_login_uid = None
xmlrpc_login_error = None

xmlrpc_authenticate_success = False
xmlrpc_authenticate_uid = None
xmlrpc_authenticate_error = None

try:
    print(f"\n[TEST] Connecting to XML-RPC endpoint: {xmlrpc_common_url}")
    
    # Create XML-RPC proxy
    common_proxy = xmlrpc.client.ServerProxy(xmlrpc_common_url, allow_none=True)
    
    # Test 5a: XML-RPC login() method (traditional)
    print(f"\n[TEST 5a] Testing XML-RPC login() method:")
    print(f"  - Database: {ODOO_DB}")
    print(f"  - Username: {ODOO_LOGIN}")
    print(f"  - Password: {'*' * min(len(ODOO_API_KEY), 20)}...")
    
    xmlrpc_login_uid = common_proxy.login(ODOO_DB, ODOO_LOGIN, ODOO_API_KEY)
    
    if xmlrpc_login_uid:
        xmlrpc_login_success = True
        print(f"[SUCCESS] XML-RPC login() successful, UID: {xmlrpc_login_uid}")
    else:
        print(f"[FAIL] XML-RPC login() failed - returned False/None")
    
    # Test 5b: XML-RPC authenticate() method (API key method - from working script)
    print(f"\n[TEST 5b] Testing XML-RPC authenticate() method (API key method):")
    print(f"  - Database: {ODOO_DB}")
    print(f"  - Username: {ODOO_LOGIN}")
    print(f"  - API Key: {'*' * min(len(ODOO_API_KEY), 20)}...")
    print(f"  - User Agent: {{}}")
    
    xmlrpc_authenticate_uid = common_proxy.authenticate(ODOO_DB, ODOO_LOGIN, ODOO_API_KEY, {})
    
    if xmlrpc_authenticate_uid:
        xmlrpc_authenticate_success = True
        print(f"[SUCCESS] XML-RPC authenticate() successful, UID: {xmlrpc_authenticate_uid}")
        
        # Optionally get version info
        try:
            version = common_proxy.version()
            print(f"[INFO] Odoo Version: {version.get('server_version', 'unknown')}")
        except:
            pass
    else:
        print(f"[FAIL] XML-RPC authenticate() failed - returned False/None")
        
except xmlrpc.client.Fault as e:
    error_msg = f"XML-RPC Fault: {e.faultCode} - {e.faultString}"
    if not xmlrpc_login_error:
        xmlrpc_login_error = error_msg
    if not xmlrpc_authenticate_error:
        xmlrpc_authenticate_error = error_msg
    print(f"[ERROR] {error_msg}")
except Exception as e:
    error_msg = str(e)
    if not xmlrpc_login_error:
        xmlrpc_login_error = error_msg
    if not xmlrpc_authenticate_error:
        xmlrpc_authenticate_error = error_msg
    print(f"[ERROR] XML-RPC error: {e}")
    import traceback
    traceback.print_exc()

# Determine overall XML-RPC success
xmlrpc_success = xmlrpc_login_success or xmlrpc_authenticate_success
xmlrpc_uid = xmlrpc_authenticate_uid if xmlrpc_authenticate_uid else xmlrpc_login_uid
xmlrpc_error = xmlrpc_authenticate_error if xmlrpc_authenticate_error else xmlrpc_login_error

# ============================================================================
# STEP 6: Final Summary
# ============================================================================
print("\n" + "=" * 80)
print("STEP 6: FINAL SUMMARY")
print("=" * 80)

print("\n--- Environment Variables (Runtime Values) ---")
print(f"ODOO_BASE_URL = {ODOO_BASE_URL}")
print(f"ODOO_DB = {ODOO_DB}")
print(f"ODOO_LOGIN = {ODOO_LOGIN}")
print(f"ODOO_API_KEY = {'SET' if ODOO_API_KEY else 'NOT SET'}")

print("\n--- Final Endpoints ---")
print(f"JSON-RPC endpoint: {jsonrpc_url}")
print(f"XML-RPC common endpoint: {xmlrpc_common_url}")

print("\n--- JSON-RPC Test Results ---")
print(f"RPC Variant: JSON-RPC")
print(f"HTTP Status Code: {jsonrpc_status}")
print(f"Login Result (UID): {jsonrpc_uid}")
print(f"Error: {jsonrpc_error if jsonrpc_error else 'None'}")
print(f"AUTH_SUCCESS: {jsonrpc_success}")

print("\n--- XML-RPC Test Results ---")
print(f"RPC Variant: XML-RPC")
print(f"HTTP Status Code: N/A (XML-RPC uses different transport)")
print(f"XML-RPC login() Result (UID): {xmlrpc_login_uid}")
print(f"XML-RPC login() Error: {xmlrpc_login_error if xmlrpc_login_error else 'None'}")
print(f"XML-RPC login() AUTH_SUCCESS: {xmlrpc_login_success}")
print(f"XML-RPC authenticate() Result (UID): {xmlrpc_authenticate_uid}")
print(f"XML-RPC authenticate() Error: {xmlrpc_authenticate_error if xmlrpc_authenticate_error else 'None'}")
print(f"XML-RPC authenticate() AUTH_SUCCESS: {xmlrpc_authenticate_success}")
print(f"XML-RPC Overall AUTH_SUCCESS: {xmlrpc_success}")

print("\n--- Raw Response (JSON-RPC) ---")
if jsonrpc_response:
    print(jsonrpc_response)
else:
    print("No response received")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)

if jsonrpc_success:
    print("[RESULT] JSON-RPC authentication: SUCCESS")
    print("[RESULT] Local Odoo auth working in this project: YES (JSON-RPC)")
elif xmlrpc_authenticate_success:
    print("[RESULT] JSON-RPC authentication: FAILED")
    print("[RESULT] XML-RPC login() authentication: FAILED")
    print("[RESULT] XML-RPC authenticate() authentication: SUCCESS")
    print("[RESULT] Local Odoo auth working in this project: YES (XML-RPC with authenticate())")
    print("[NOTE] Current codebase uses JSON-RPC, but XML-RPC authenticate() works.")
    print("[NOTE] The working method is authenticate(), not login().")
    print("[NOTE] Consider switching to XML-RPC with authenticate() method.")
elif xmlrpc_login_success:
    print("[RESULT] JSON-RPC authentication: FAILED")
    print("[RESULT] XML-RPC login() authentication: SUCCESS")
    print("[RESULT] XML-RPC authenticate() authentication: FAILED")
    print("[RESULT] Local Odoo auth working in this project: YES (XML-RPC with login())")
    print("[NOTE] Current codebase uses JSON-RPC, but XML-RPC login() works.")
    print("[NOTE] Consider switching to XML-RPC with login() method.")
elif xmlrpc_success:
    print("[RESULT] JSON-RPC authentication: FAILED")
    print("[RESULT] XML-RPC authentication: SUCCESS (method unclear)")
    print("[RESULT] Local Odoo auth working in this project: YES (XML-RPC)")
    print("[NOTE] Current codebase uses JSON-RPC, but XML-RPC works. Consider switching to XML-RPC.")
else:
    print("[RESULT] All authentication methods FAILED")
    print("[RESULT] Local Odoo auth working in this project: NO")
    if jsonrpc_error:
        print(f"[INFO] JSON-RPC error: {jsonrpc_error}")
    if xmlrpc_login_error:
        print(f"[INFO] XML-RPC login() error: {xmlrpc_login_error}")
    if xmlrpc_authenticate_error:
        print(f"[INFO] XML-RPC authenticate() error: {xmlrpc_authenticate_error}")

print("=" * 80)

# Exit with appropriate code
sys.exit(0 if (jsonrpc_success or xmlrpc_success) else 1)
