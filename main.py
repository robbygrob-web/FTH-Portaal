import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Laad omgevingsvariabelen uit .env bestand VOOR andere imports
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Import config en routes NA load_dotenv() zodat omgevingsvariabelen beschikbaar zijn
from app.config import SESSION_SECRET, startup_validation
from app.routes import router

# Import webhooks router met error handling voor debugging
try:
    from app.webhooks import router as webhooks_router
    print(f"[DEBUG] Webhooks router geïmporteerd: {len(webhooks_router.routes)} routes")
except Exception as e:
    print(f"[ERROR] Webhooks router import gefaald: {e}")
    import traceback
    traceback.print_exc()
    raise

# Voer startup validatie uit
startup_validation()

app = FastAPI(title="FTH Portaal")

# SESSION_SECRET voor sessie middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
)

# Include routes
app.include_router(router)
try:
    app.include_router(webhooks_router)
    print(f"[DEBUG] Webhooks router geregistreerd in app")
except Exception as e:
    print(f"[ERROR] Webhooks router registratie gefaald: {e}")
    import traceback
    traceback.print_exc()
    raise

# Include mail routes
try:
    from app.mail_routes import router as mail_router
    app.include_router(mail_router)
    print(f"[DEBUG] Mail router geregistreerd in app")
except Exception as e:
    print(f"[ERROR] Mail router registratie gefaald: {e}")
    import traceback
    traceback.print_exc()
    # Mail router is optioneel, niet kritiek voor startup

# DEBUG: Print alle geregistreerde routes bij startup
def print_routes():
    """Print alle geregistreerde routes voor debugging"""
    print("\n" + "=" * 60)
    print("DEBUG: Geregistreerde routes:")
    print("=" * 60)
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            methods = ', '.join(route.methods) if route.methods else 'N/A'
            print(f"  {methods:15} {route.path}")
        elif hasattr(route, 'path'):
            print(f"  {'N/A':15} {route.path}")
    print("=" * 60 + "\n")

# Print routes bij startup (alleen in development)
if __name__ != "__main__" or True:  # Altijd printen voor debugging
    print_routes()
