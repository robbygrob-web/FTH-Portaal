import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from app.odoo_client import OdooClient
from app.routes import router

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
def health_check():
    """Health check endpoint voor Railway"""
    status = {.\.venv\Scripts\Activate.ps1
        "status": "ok",
        "BASE_URL_gevonden": bool(os.getenv("ODOO_BASE_URL")),
        "DB_gevonden": bool(os.getenv("ODOO_DB")),
        "LOGIN_gevonden": bool(os.getenv("ODOO_LOGIN")),
        "API_KEY_gevonden": bool(os.getenv("ODOO_API_KEY")),
        "SESSION_SECRET_gevonden": bool(os.getenv("SESSION_SECRET")),
    }
    return status

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
        }
    except Exception as e:
        return {"status": "Fout bij verbinden", "foutmelding": str(e)}

@app.get("/test-update")
def test_update():
    """Simpele test-route die de partner_id van inkooporder 255 naar 87 zet"""
    try:
        client = OdooClient()
        model = "purchase.order"
        purchase_order_id = 255
        nieuwe_partner_id = 87

        # We nemen aan dat OdooClient een .update methode heeft:
        # client.update(model, id, dict met te updaten waarden)
        result = client.update(model, purchase_order_id, {"partner_id": nieuwe_partner_id})
        return {
            "status": "Succesvol geüpdatet",
            "purchase_order_id": purchase_order_id,
            "nieuwe_partner_id": nieuwe_partner_id,
            "resultaat": result,
        }
    except Exception as e:
        return {
            "status": "Fout bij updaten van inkooporder",
            "foutmelding": str(e),
        }