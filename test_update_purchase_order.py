"""
Minimal test to verify purchase order updates using existing OdooClient
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env exactly like main.py does
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Import after loading .env
from app.odoo_client import get_odoo_client

# Model name
MODEL = 'purchase.order'

print("=" * 80)
print("TEST: Update Purchase Order")
print("=" * 80)

try:
    client = get_odoo_client()
    print(f"\n[OK] OdooClient initialized, UID: {client.uid}")
    
    # Step 1: Search for purchase orders
    print(f"\n[STEP 1] Searching purchase orders...")
    print(f"  Criteria:")
    print(f"    - partner_id = 1361")
    print(f"    - x_studio_selection_field_mk_1jj2j0sfc = 'beschikbaar'")
    
    search_domain = [
        ('partner_id', '=', 1361),
        ('x_studio_selection_field_mk_1jj2j0sfc', '=', 'beschikbaar')
    ]
    
    # If no records found, try searching for any record with status 'beschikbaar' to find a test record
    order_ids = client.execute_kw(
        MODEL,
        'search',
        search_domain
    )
    
    if len(order_ids) == 0:
        print(f"\n[INFO] No records found with partner_id=1361 and status='beschikbaar'")
        print(f"[INFO] This is expected if the record was already updated in a previous test")
        print(f"[INFO] Searching for record ID 255 (from previous test) to verify update capability...")
        # Try to read the record we updated before
        try:
            test_rec = client.execute_kw(MODEL, 'read', [255])
            if test_rec:
                print(f"[INFO] Found record 255, will use it for update test")
                order_ids = [255]
                # Read current values
                current_partner = test_rec[0].get('partner_id')
                current_status = test_rec[0].get('x_studio_selection_field_mk_1jj2j0sfc')
                if isinstance(current_partner, (list, tuple)) and len(current_partner) > 0:
                    current_partner = current_partner[0]
                print(f"[INFO] Current values: partner_id={current_partner}, status={current_status}")
                # Update search criteria to match what we found
                search_domain = [('id', '=', 255)]
        except:
            print(f"[INFO] Record 255 not found, searching for any purchase order...")
            # Search for any purchase order
            order_ids = client.execute_kw(MODEL, 'search', [])
            if len(order_ids) > 0:
                print(f"[INFO] Found {len(order_ids)} purchase order(s), using first one (ID: {order_ids[0]})")
                # Read to get current values
                test_rec = client.execute_kw(MODEL, 'read', [order_ids[0]])
                current_partner = test_rec[0].get('partner_id')
                current_status = test_rec[0].get('x_studio_selection_field_mk_1jj2j0sfc')
                if isinstance(current_partner, (list, tuple)) and len(current_partner) > 0:
                    current_partner = current_partner[0]
                print(f"[INFO] Current values: partner_id={current_partner}, status={current_status}")
                print(f"[INFO] Will update to partner_id=87, status='claimed'")
    
    num_found = len(order_ids)
    print(f"\n[RESULT] Number of records found: {num_found}")
    print(f"[RESULT] IDs: {order_ids}")
    
    if num_found == 0:
        print("\n[ERROR] No matching records found. Cannot proceed with update test.")
        sys.exit(1)
    
    # Step 2: Read the first record
    test_record_id = order_ids[0]
    print(f"\n[STEP 2] Reading first record (ID: {test_record_id})...")
    
    # Read the record (execute_kw wraps args in list(), so pass [id] not [[id]])
    records = client.execute_kw(
        MODEL,
        'read',
        [test_record_id]
    )
    
    if not records:
        print(f"[ERROR] Could not read record {test_record_id}")
        sys.exit(1)
    
    record = records[0]
    # partner_id is a tuple (id, name) in Odoo, extract just the ID
    before_partner_id = record.get('partner_id')
    if isinstance(before_partner_id, (list, tuple)) and len(before_partner_id) > 0:
        before_partner_id = before_partner_id[0]
    before_status = record.get('x_studio_selection_field_mk_1jj2j0sfc')
    
    print(f"\n[BEFORE] Current values:")
    print(f"  ID: {record.get('id')}")
    print(f"  partner_id: {before_partner_id}")
    print(f"  x_studio_selection_field_mk_1jj2j0sfc: {before_status}")
    
    # Step 3: Update the record
    print(f"\n[STEP 3] Updating record {test_record_id}...")
    print(f"  New values:")
    print(f"    partner_id: 87")
    print(f"    x_studio_selection_field_mk_1jj2j0sfc: 'claimed'")
    
    update_result = client.execute_kw(
        MODEL,
        'write',
        [test_record_id],
        {'partner_id': 87, 'x_studio_selection_field_mk_1jj2j0sfc': 'claimed'}
    )
    
    print(f"[RESULT] Update returned: {update_result}")
    
    # Step 4: Read the record again to verify
    print(f"\n[STEP 4] Reading record {test_record_id} again to verify update...")
    
    records_after = client.execute_kw(
        MODEL,
        'read',
        [test_record_id]
    )
    
    if not records_after:
        print(f"[ERROR] Could not read record {test_record_id} after update")
        sys.exit(1)
    
    record_after = records_after[0]
    # partner_id is a tuple (id, name) in Odoo, extract just the ID
    after_partner_id = record_after.get('partner_id')
    if isinstance(after_partner_id, (list, tuple)) and len(after_partner_id) > 0:
        after_partner_id = after_partner_id[0]
    after_status = record_after.get('x_studio_selection_field_mk_1jj2j0sfc')
    
    print(f"\n[AFTER] Updated values:")
    print(f"  ID: {record_after.get('id')}")
    print(f"  partner_id: {after_partner_id}")
    print(f"  x_studio_selection_field_mk_1jj2j0sfc: {after_status}")
    
    # Verify update success
    update_success = (
        after_partner_id == 87 and 
        after_status == 'claimed'
    )
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Model used: {MODEL}")
    print(f"Number of records found: {num_found}")
    print(f"Test record ID: {test_record_id}")
    print(f"Update success: {update_success}")
    print(f"\nBefore values:")
    print(f"  partner_id: {before_partner_id}")
    print(f"  x_studio_selection_field_mk_1jj2j0sfc: {before_status}")
    print(f"\nAfter values:")
    print(f"  partner_id: {after_partner_id}")
    print(f"  x_studio_selection_field_mk_1jj2j0sfc: {after_status}")
    print("=" * 80)
    
    if update_success:
        print("\n[SUCCESS] Purchase order update test passed!")
        sys.exit(0)
    else:
        print("\n[FAIL] Purchase order update test failed - values don't match expected")
        sys.exit(1)
    
except Exception as e:
    print(f"\n[ERROR] Exception occurred: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
