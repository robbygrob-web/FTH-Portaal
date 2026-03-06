import os
import asyncio
from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends
from starlette.middleware.sessions import SessionMiddleware
from starlette.concurrency import run_in_threadpool
from app.odoo_client import OdooClient, get_odoo_client

app = FastAPI(title="FTH Partner Portal V6.3.2 - Test Ready")

# 1. Beveiliging & Sessie Configuratie
SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET or len(SESSION_SECRET) < 32:
    # Voor de allereerste test op Railway kun je tijdelijk een fallback gebruiken:
    SESSION_SECRET = "tijdelijk_geheim_wachtwoord_32_tekens_minimaal"

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=3600 * 24, # 24 uur geldig
    same_site="lax",
    https_only=os.getenv("HTTPS_ONLY", "false").lower() == "true",
)

router = APIRouter()
_order_locks: dict[int, asyncio.Lock] = {}

# --- TEST ROUTES (Backdoor voor eerste keer testen) ---

@app.get("/test-connect")
async def test_odoo_connection(odoo: OdooClient = Depends(get_odoo_client)):
    """Checkt of Railway verbinding heeft met Odoo"""
    try:
        version = await run_in_threadpool(odoo.execute, "common", "version")
        return {"status": "Verbinding geslaagd!", "odoo_versie": version}
    except Exception as e:
        return {"status": "Fout", "detail": str(e)}

@app.get("/force-login-test/{partner_id}")
async def force_login(partner_id: int, request: Request):
    """Fopt de app zodat je ingelogd bent als een specifieke partner"""
    request.session["user"] = {
        "id": partner_id, 
        "email": "test@partner.nl" # Zorg dat dit overeenkomt met een e-mail in Odoo res.partner
    }
    return {"bericht": f"Je bent nu tijdelijk ingelogd als Partner ID {partner_id}"}

# --- ECHTE LOGICA ---

async def _try_acquire(lock: asyncio.Lock) -> bool:
    try:
        await asyncio.wait_for(lock.acquire(), timeout=0.05)
        return True
    except asyncio.TimeoutError:
        return False

@router.post("/jobs/claim/{order_id}")
async def claim_job(order_id: int, request: Request, odoo: OdooClient = Depends(get_odoo_client)):
    # 1. Sessie validatie
    user = request.session.get("user")
    if not isinstance(user, dict):
        raise HTTPException(401, detail="Nog niet ingelogd. Gebruik /force-login-test/ID")

    p_id = int(user.get("id"))
    email = user.get("email").strip().lower()

    # 2. Gatekeeper lock (Voorkomt race-conditions)
    lock = _order_locks.setdefault(order_id, asyncio.Lock())
    if not await _try_acquire(lock):
        raise HTTPException(409, detail="Klus wordt momenteel verwerkt.")

    try:
        # A) Status Check op Purchase Order (PO)
        order = await run_in_threadpool(
            odoo.execute_kw, "purchase.order", "read", [[order_id], ["x_pool_status"]]
        )
        if not order:
            raise HTTPException(404, detail="Inkooporder niet gevonden.")
        
        o = order[0]
        if o.get("x_pool_status") not in ("available", "transfer"):
            raise HTTPException(409, detail="Helaas, deze klus is niet meer beschikbaar.")

        # B) De Claim Schrijven (Partner ID invullen op PO)
        ok = await run_in_threadpool(
            odoo.execute_kw,
            "purchase.order",
            "write",
            [[order_id], {
                "partner_id": p_id,        # De frietwagen wordt de leverancier
                "x_pool_status": "claimed" # Status wordt claimed
            }],
        )
        if not ok:
            raise HTTPException(502, detail="Odoo weigerde de wijziging.")

        return {"status": "success", "message": f"Order {order_id} is nu van jou!"}

    finally:
        if lock.locked():
            lock.release()
        _order_locks.pop(order_id, None)

app.include_router(router, prefix="/api")

@app.get("/")
def home():
    return {"bericht": "FTH Partner API is online. Ga naar /test-connect voor status."}

