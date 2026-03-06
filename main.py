import os
import logging
from dotenv import load_dotenv

# Laad omgevingsvariabelen uit .env bestand VOOR andere imports
# Dit is belangrijk omdat app.routes PartnerAuth() instantieert op module niveau
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from app.odoo_client import OdooClient
from app.routes import router

_LOG = logging.getLogger(__name__)

app = FastAPI(title="FTH Portaal")

# Tijdelijke fallback zodat de app niet crasht als SESSION_SECRET ontbreekt
SESSION_SECRET = os.getenv("SESSION_SECRET", "tijdelijk_geheim_wachtwoord_1234567890")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
)

# Include routes
app.include_router(router)


@app.get("/")
async def root(request: Request):
    """Redirect naar login of dashboard afhankelijk van sessie"""
    if request.session.get("partner"):
        return RedirectResponse(url="/dashboard", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok"}


@app.get("/test-connect")
def test_connect():
    """Test Odoo verbinding"""
    try:
        client = OdooClient()
        return {
            "status": "Verbonden!",
            "database": os.getenv("ODOO_DB"),
            "base_url": os.getenv("ODOO_BASE_URL"),
            "login": os.getenv("ODOO_LOGIN"),
            "uid": client.uid,
        }
    except Exception as e:
        return {"status": "Fout bij verbinden", "foutmelding": str(e)}


@app.get("/test-raw-po")
def test_raw_po():
    """Test raw Odoo call om exacte foutmelding te zien"""
    import requests
    import json
    
    try:
        base_url = os.getenv("ODOO_BASE_URL")
        url = f"{base_url.rstrip('/')}/jsonrpc"
        db = os.getenv("ODOO_DB")
        username = os.getenv("ODOO_LOGIN")
        password = os.getenv("ODOO_API_KEY")
        
        # Login eerst
        login_payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "common",
                "method": "login",
                "args": [db, username, password]
            },
            "id": 1,
        }
        
        login_resp = requests.post(url, json=login_payload, timeout=10)
        login_data = login_resp.json()
        uid = login_data.get("result")
        
        if not uid:
            return {"status": "Login mislukt", "response": login_data}
        
        # Test search
        search_payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [db, uid, password, "purchase.order", "search", [[]], {}]
            },
            "id": 1,
        }
        
        search_resp = requests.post(url, json=search_payload, timeout=20)
        search_data = search_resp.json()
        
        return {
            "status": "Raw test",
            "uid": uid,
            "search_response": search_data,
            "heeft_error": "error" in search_data,
            "error_details": search_data.get("error") if "error" in search_data else None,
        }
    except Exception as e:
        return {
            "status": "Fout",
            "foutmelding": str(e),
            "fout_type": type(e).__name__
        }


@app.get("/test-update")
def test_update():
    """Simpele test-route die de partner_id van inkooporder 255 naar 87 zet"""
    try:
        client = OdooClient()
        purchase_order_id = 255
        nieuwe_partner_id = 87

        result = client.execute_kw(
            "purchase.order",
            "write",
            [purchase_order_id],
            {"partner_id": nieuwe_partner_id},
        )

        return {
            "status": "Succesvol geüpdatet" if result else "Niet gewijzigd",
            "purchase_order_id": purchase_order_id,
            "nieuwe_partner_id": nieuwe_partner_id,
            "resultaat": result,
        }
    except Exception as e:
        return {
            "status": "Fout bij updaten van inkooporder",
            "foutmelding": str(e),
        }


@app.get("/test-find-po")
def test_find_po():
    """Test of we inkooporders kunnen vinden"""
    try:
        client = OdooClient()
        resultaten = {}
        
        # Test 1: Zoek eerst alleen IDs - gebruik [] voor lege domain (wordt [[]] na wrapping)
        try:
            alle_po_ids = client.execute_kw(
                "purchase.order",
                "search",
                [],
            )
            resultaten["test1_alle_ids"] = {
                "succes": True,
                "aantal": len(alle_po_ids) if alle_po_ids else 0,
                "ids": alle_po_ids[:10] if alle_po_ids else []  # Eerste 10
            }
        except Exception as e1:
            resultaten["test1_alle_ids"] = {
                "succes": False,
                "fout": str(e1),
                "fout_type": type(e1).__name__
            }
        
        # Test 2: Zoek inkooporders met partner_id 1361 (gebruik zelfde syntax als routes.py)
        try:
            pos_met_partner_1361 = client.execute_kw(
                "purchase.order",
                "search_read",
                [["partner_id", "=", 1361]],
                {
                    "fields": ["id", "name", "partner_id", "date_order", "state"],
                    "limit": 10
                }
            )
            resultaten["test2_partner_1361"] = {
                "succes": True,
                "aantal": len(pos_met_partner_1361) if pos_met_partner_1361 else 0,
                "data": pos_met_partner_1361
            }
        except Exception as e2:
            resultaten["test2_partner_1361"] = {
                "succes": False,
                "fout": str(e2)
            }
        
        # Test 3: Zoek inkooporders met partner_id 87 (gebruik zelfde syntax als routes.py)
        try:
            pos_met_partner_87 = client.execute_kw(
                "purchase.order",
                "search_read",
                [["partner_id", "=", 87]],
                {
                    "fields": ["id", "name", "partner_id", "date_order", "state"],
                    "limit": 10
                }
            )
            resultaten["test3_partner_87"] = {
                "succes": True,
                "aantal": len(pos_met_partner_87) if pos_met_partner_87 else 0,
                "data": pos_met_partner_87
            }
        except Exception as e3:
            resultaten["test3_partner_87"] = {
                "succes": False,
                "fout": str(e3)
            }
        
        # Test 4: Zoek specifiek PO0255 (probeer verschillende naam varianten)
        try:
            # Probeer verschillende naam varianten
            naam_varianten = ["PO0255", "po0255", "PO-0255", "PO 0255"]
            po0255_ids = None
            gevonden_naam = None
            
            for naam in naam_varianten:
                try:
                    ids = client.execute_kw(
                        "purchase.order",
                        "search",
                        [["name", "=", naam]],
                    )
                    if ids:
                        po0255_ids = ids
                        gevonden_naam = naam
                        break
                except:
                    continue
            
            po0255_data = None
            if po0255_ids:
                po0255_data = client.execute_kw(
                    "purchase.order",
                    "read",
                    [po0255_ids[0]],
                    {"fields": ["id", "name", "partner_id", "date_order", "state", "amount_total"]},
                )
            
            resultaten["test4_po0255"] = {
                "succes": True,
                "gevonden": po0255_data is not None,
                "gevonden_naam": gevonden_naam,
                "data": po0255_data[0] if po0255_data else None
            }
        except Exception as e4:
            resultaten["test4_po0255"] = {
                "succes": False,
                "fout": str(e4)
            }
        
        # Test 5: Gebruik search_read om alle inkooporders te lezen (zoals in routes.py)
        try:
            alle_pos_data = client.execute_kw(
                "purchase.order",
                "search_read",
                [],
                {
                    "fields": ["id", "name", "partner_id", "date_order", "state"],
                    "limit": 5
                }
            )
            resultaten["test5_search_read_alle"] = {
                "succes": True,
                "aantal": len(alle_pos_data) if alle_pos_data else 0,
                "data": alle_pos_data[:3] if alle_pos_data else []  # Eerste 3
            }
        except Exception as e5:
            resultaten["test5_search_read_alle"] = {
                "succes": False,
                "fout": str(e5)
            }
        
        return {
            "status": "Test voltooid",
            "resultaten": resultaten,
        }
    except Exception as e:
        return {
            "status": "Fout bij zoeken van inkooporders",
            "foutmelding": str(e),
        }


@app.get("/check-po255")
def check_po255():
    """Controleer huidige leverancier van inkooporder 255"""
    po_id = 255
    try:
        client = OdooClient()
        
        # Eerst controleren of record bestaat met search
        try:
            po_ids = client.execute_kw(
                "purchase.order",
                "search",
                [("id", "=", po_id)],
            )
            
            if not po_ids:
                return {
                    "status": "Niet gevonden",
                    "bericht": f"Inkooporder met ID {po_id} bestaat niet",
                    "po_id": po_id,
                }
        except Exception as search_error:
            _LOG.error(f"Fout bij zoeken naar record {po_id}: {search_error}")
            print(f"Fout bij zoeken naar record {po_id}: {search_error}")
            return {
                "status": "Fout bij zoeken",
                "bericht": f"Kon niet controleren of record {po_id} bestaat",
                "foutmelding": str(search_error),
                "fout_type": type(search_error).__name__,
            }
        
        # Haal record 255 op
        try:
            po_data = client.execute_kw(
                "purchase.order",
                "read",
                [po_id],
                fields=["id", "name", "display_name", "partner_id"],
            )
        except Exception as read_error:
            _LOG.error(f"Fout bij lezen van record {po_id}: {read_error}")
            print(f"Fout bij lezen van record {po_id}: {read_error}")
            error_detail = str(read_error)
            if hasattr(read_error, 'detail'):
                error_detail = str(read_error.detail)
            return {
                "status": "Fout",
                "bericht": f"Kon record {po_id} niet ophalen",
                "foutmelding": error_detail,
                "fout_type": type(read_error).__name__,
                "po_id": po_id,
            }
        
        # Controleer of record bestaat
        if not po_data:
            return {
                "status": "Niet gevonden",
                "bericht": f"Inkooporder met ID {po_id} bestaat niet",
                "po_id": po_id,
            }
        
        po = po_data[0]
        display_name = po.get("display_name") or po.get("name", "N/A")
        huidige_partner_id = po.get("partner_id")
        
        # Odoo geeft partner_id terug als [id, name] tuple of False/None
        if huidige_partner_id and isinstance(huidige_partner_id, (list, tuple)):
            partner_id_nummer = huidige_partner_id[0]
            partner_naam = huidige_partner_id[1] if len(huidige_partner_id) > 1 else None
        elif not huidige_partner_id:
            partner_id_nummer = None
            partner_naam = None
        else:
            partner_id_nummer = huidige_partner_id
            partner_naam = None
        
        # Print naar console
        _LOG.info(f"Inkooporder {po_id}: display_name={display_name}, partner_id={partner_id_nummer}")
        print(f"Inkooporder {po_id}: display_name={display_name}, partner_id={partner_id_nummer}")
        
        return {
            "status": "Gevonden",
            "po_id": po_id,
            "display_name": display_name,
            "po_naam": po.get("name"),
            "huidige_partner_id": partner_id_nummer,
            "partner_naam": partner_naam,
            "is_1361": partner_id_nummer == 1361,
        }
    except Exception as e:
        _LOG.error(f"Onverwachte fout bij ophalen van inkooporder {po_id}: {e}")
        print(f"Onverwachte fout bij ophalen van inkooporder {po_id}: {e}")
        error_detail = str(e)
        if hasattr(e, 'detail'):
            error_detail = str(e.detail)
        return {
            "status": "Fout",
            "po_id": po_id,
            "foutmelding": error_detail,
            "fout_type": type(e).__name__,
        }


@app.get("/test-change-supplier/{po_id}/{nieuwe_partner_id}")
def test_change_supplier(po_id: int, nieuwe_partner_id: int):
    """Test of we de leverancier van een inkooporder kunnen veranderen"""
    try:
        client = OdooClient()
        
        # Stap 1: Controleer huidige leverancier
        try:
            po_data_voor = client.execute_kw(
                "purchase.order",
                "read",
                [po_id],
                fields=["id", "name", "display_name", "partner_id"],
            )
            
            if not po_data_voor:
                return {
                    "status": "Niet gevonden",
                    "bericht": f"Inkooporder met ID {po_id} bestaat niet",
                    "po_id": po_id,
                }
            
            po_voor = po_data_voor[0]
            huidige_partner = po_voor.get("partner_id")
            
            # Parse huidige partner_id
            if huidige_partner and isinstance(huidige_partner, (list, tuple)):
                huidige_partner_id = huidige_partner[0]
                huidige_partner_naam = huidige_partner[1] if len(huidige_partner) > 1 else None
            elif not huidige_partner:
                huidige_partner_id = None
                huidige_partner_naam = None
            else:
                huidige_partner_id = huidige_partner
                huidige_partner_naam = None
                
        except Exception as read_error:
            error_detail = str(read_error)
            if hasattr(read_error, 'detail'):
                error_detail = str(read_error.detail)
            return {
                "status": "Fout bij ophalen",
                "bericht": f"Kon inkooporder {po_id} niet ophalen",
                "foutmelding": error_detail,
                "fout_type": type(read_error).__name__,
            }
        
        # Stap 2: Verander leverancier
        try:
            update_result = client.execute_kw(
                "purchase.order",
                "write",
                [po_id],
                {"partner_id": nieuwe_partner_id},
            )
        except Exception as write_error:
            error_detail = str(write_error)
            if hasattr(write_error, 'detail'):
                error_detail = str(write_error.detail)
            return {
                "status": "Fout bij updaten",
                "po_id": po_id,
                "huidige_partner_id": huidige_partner_id,
                "nieuwe_partner_id": nieuwe_partner_id,
                "foutmelding": error_detail,
                "fout_type": type(write_error).__name__,
            }
        
        # Stap 3: Verifieer de wijziging
        try:
            po_data_na = client.execute_kw(
                "purchase.order",
                "read",
                [po_id],
                fields=["id", "name", "display_name", "partner_id"],
            )
            
            if not po_data_na:
                return {
                    "status": "Update uitgevoerd (verificatie mislukt)",
                    "po_id": po_id,
                    "update_resultaat": update_result,
                    "bericht": "Kon inkooporder niet meer ophalen na update",
                }
            
            po_na = po_data_na[0]
            nieuwe_partner = po_na.get("partner_id")
            
            # Parse nieuwe partner_id
            if nieuwe_partner and isinstance(nieuwe_partner, (list, tuple)):
                nieuwe_partner_id_geverifieerd = nieuwe_partner[0]
                nieuwe_partner_naam = nieuwe_partner[1] if len(nieuwe_partner) > 1 else None
            elif not nieuwe_partner:
                nieuwe_partner_id_geverifieerd = None
                nieuwe_partner_naam = None
            else:
                nieuwe_partner_id_geverifieerd = nieuwe_partner
                nieuwe_partner_naam = None
                
        except Exception as verify_error:
            return {
                "status": "Update uitgevoerd (verificatie mislukt)",
                "po_id": po_id,
                "update_resultaat": update_result,
                "verificatie_fout": str(verify_error),
            }
        
        # Resultaat
        succes = nieuwe_partner_id_geverifieerd == nieuwe_partner_id
        
        return {
            "status": "Succesvol" if succes else "Mislukt",
            "po_id": po_id,
            "po_naam": po_voor.get("name"),
            "display_name": po_voor.get("display_name"),
            "voor_update": {
                "partner_id": huidige_partner_id,
                "partner_naam": huidige_partner_naam,
            },
            "na_update": {
                "partner_id": nieuwe_partner_id_geverifieerd,
                "partner_naam": nieuwe_partner_naam,
                "verwacht": nieuwe_partner_id,
            },
            "update_resultaat": update_result,
            "verificatie": {
                "correct": succes,
                "bericht": "Leverancier succesvol gewijzigd" if succes else f"Leverancier niet correct gewijzigd (verwacht {nieuwe_partner_id}, gekregen {nieuwe_partner_id_geverifieerd})"
            }
        }
        
    except Exception as e:
        error_detail = str(e)
        if hasattr(e, 'detail'):
            error_detail = str(e.detail)
        return {
            "status": "Fout",
            "po_id": po_id,
            "nieuwe_partner_id": nieuwe_partner_id,
            "foutmelding": error_detail,
            "fout_type": type(e).__name__,
        }


@app.get("/test-po0255")
def test_po0255():
    """Haal inkooporder met ID 255 op en verander leverancier naar 1361"""
    po_id = 255
    try:
        client = OdooClient()
        
        # Eerst controleren of record bestaat met search
        try:
            po_ids = client.execute_kw(
                "purchase.order",
                "search",
                [("id", "=", po_id)],
            )
            
            if not po_ids:
                return {
                    "status": "Niet gevonden",
                    "bericht": f"Inkooporder met ID {po_id} bestaat niet",
                    "po_id": po_id,
                }
        except Exception as search_error:
            _LOG.error(f"Fout bij zoeken naar record {po_id}: {search_error}")
            print(f"Fout bij zoeken naar record {po_id}: {search_error}")
            error_detail = str(search_error)
            if hasattr(search_error, 'detail'):
                error_detail = str(search_error.detail)
            return {
                "status": "Fout bij zoeken",
                "bericht": f"Kon niet controleren of record {po_id} bestaat",
                "foutmelding": error_detail,
                "fout_type": type(search_error).__name__,
            }
        
        # Probeer direct record 255 op te halen met read methode
        try:
            po_data = client.execute_kw(
                "purchase.order",
                "read",
                [po_id],
                fields=["id", "name", "display_name", "partner_id"],
            )
        except Exception as read_error:
            _LOG.error(f"Fout bij lezen van record {po_id}: {read_error}")
            print(f"Fout bij lezen van record {po_id}: {read_error}")
            error_detail = str(read_error)
            if hasattr(read_error, 'detail'):
                error_detail = str(read_error.detail)
            return {
                "status": "Fout",
                "bericht": f"Kon record {po_id} niet ophalen",
                "foutmelding": error_detail,
                "fout_type": type(read_error).__name__,
            }
        
        # Controleer of record bestaat
        if not po_data:
            return {
                "status": "Niet gevonden",
                "bericht": f"Inkooporder met ID {po_id} bestaat niet",
                "po_id": po_id,
            }
        
        po = po_data[0]
        display_name = po.get("display_name") or po.get("name", "N/A")
        huidige_partner_id = po.get("partner_id")
        
        # Odoo geeft partner_id terug als [id, name] tuple of False/None
        if huidige_partner_id and isinstance(huidige_partner_id, (list, tuple)):
            huidige_partner_id = huidige_partner_id[0]
        elif not huidige_partner_id:
            huidige_partner_id = None
        
        # Print naar console
        _LOG.info(f"Inkooporder gevonden: ID={po_id}, display_name={display_name}, partner_id={huidige_partner_id}")
        print(f"Inkooporder gevonden: ID={po_id}, display_name={display_name}, partner_id={huidige_partner_id}")
        
        # Update partner_id naar 1361
        try:
            result = client.execute_kw(
                "purchase.order",
                "write",
                [po_id],
                {"partner_id": 1361},
            )
        except Exception as write_error:
            _LOG.error(f"Fout bij updaten van record {po_id}: {write_error}")
            print(f"Fout bij updaten van record {po_id}: {write_error}")
            error_detail = str(write_error)
            if hasattr(write_error, 'detail'):
                error_detail = str(write_error.detail)
            return {
                "status": "Fout bij updaten",
                "po_id": po_id,
                "display_name": display_name,
                "huidige_partner_id": huidige_partner_id,
                "foutmelding": error_detail,
                "fout_type": type(write_error).__name__,
            }
        
        # Verifieer de wijziging
        try:
            po_data_na = client.execute_kw(
                "purchase.order",
                "read",
                [po_id],
                {"fields": ["id", "name", "display_name", "partner_id"]},
            )
        except Exception as verify_error:
            _LOG.warning(f"Update uitgevoerd maar verificatie mislukt: {verify_error}")
            print(f"Update uitgevoerd maar verificatie mislukt: {verify_error}")
            return {
                "status": "Update uitgevoerd (verificatie mislukt)",
                "po_id": po_id,
                "display_name": display_name,
                "oude_partner_id": huidige_partner_id,
                "update_resultaat": result,
                "verificatie_fout": str(verify_error),
            }
        
        nieuwe_partner_id = None
        if po_data_na:
            nieuwe_partner = po_data_na[0].get("partner_id")
            if nieuwe_partner and isinstance(nieuwe_partner, (list, tuple)):
                nieuwe_partner_id = nieuwe_partner[0]
            elif nieuwe_partner:
                nieuwe_partner_id = nieuwe_partner
        
        _LOG.info(f"Update uitgevoerd: partner_id gewijzigd naar {nieuwe_partner_id}")
        print(f"Update uitgevoerd: partner_id gewijzigd naar {nieuwe_partner_id}")
        
        return {
            "status": "Succesvol geüpdatet" if result else "Niet gewijzigd",
            "po_id": po_id,
            "display_name": display_name,
            "po_naam": po.get("name"),
            "oude_partner_id": huidige_partner_id,
            "nieuwe_partner_id": nieuwe_partner_id,
            "update_resultaat": result,
            "verificatie": {
                "partner_id_na_update": nieuwe_partner_id,
                "verwacht": 1361,
                "correct": nieuwe_partner_id == 1361,
            },
        }
    except Exception as e:
        _LOG.error(f"Onverwachte fout bij updaten van inkooporder {po_id}: {e}")
        print(f"Onverwachte fout bij updaten van inkooporder {po_id}: {e}")
        error_detail = str(e)
        if hasattr(e, 'detail'):
            error_detail = str(e.detail)
        return {
            "status": "Fout bij updaten van inkooporder",
            "po_id": po_id,
            "foutmelding": error_detail,
            "fout_type": type(e).__name__,
        }