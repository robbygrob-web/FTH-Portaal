import os
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from app.odoo_client import OdooClient

app = FastAPI(title="FTH Debug Mode")

# We gebruiken nu een vaste secret als de variabele mist, zodat de app niet crasht
SESSION_SECRET = os.getenv("SESSION_SECRET", "tijdelijk_geheim_wachtwoord_1234567890")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
)

@app.get("/")
def read_root():
    # Deze lijst laat precies zien wat de app ziet in Railway
    status = {
        "URL_gevonden": bool(os.getenv("ODOO_URL")),
        "DB_gevonden": bool(os.getenv("ODOO_DB")),
        "USER_gevonden": bool(os.getenv("ODOO_USER")),
        "PASSWORD_gevonden": bool(os.getenv("ODOO_PASSWORD")),
        "SESSION_SECRET_gevonden": bool(os.getenv("SESSION_SECRET")),
        "Bericht": "Als hierboven ergens 'false' staat, moet je die naam in Railway Variables controleren."
    }
    return status

@app.get("/test-connect")
def test_connect():
    try:
        client = OdooClient()
        return {"status": "Verbonden!", "database": os.getenv("ODOO_DB")}
    except Exception as e:
        return {"status": "Fout bij verbinden", "foutmelding": str(e)}
