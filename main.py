import os
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from app.odoo_client import OdooClient

app = FastAPI(title="FTH Debug Mode")

# Tijdelijke fallback zodat de app niet crasht als SESSION_SECRET ontbreekt
SESSION_SECRET = os.getenv("SESSION_SECRET", "tijdelijk_geheim_wachtwoord_1234567890")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
)

@app.get("/")
def read_root():
    status = {
        "BASE_URL_gevonden": bool(os.getenv("ODOO_BASE_URL")),
        "DB_gevonden": bool(os.getenv("ODOO_DB")),
        "LOGIN_gevonden": bool(os.getenv("ODOO_LOGIN")),
        "API_KEY_gevonden": bool(os.getenv("ODOO_API_KEY")),
        "SESSION_SECRET_gevonden": bool(os.getenv("SESSION_SECRET")),
        "Bericht": "Als hierboven ergens 'false' staat, moet je die naam in Railway Variables controleren."
    }
    return status

@app.get("/test-connect")
def test_connect():
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
