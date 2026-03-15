import os
import logging
import asyncio
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
from app.templates import router as templates_router

# Import webhooks router met error handling voor debugging
try:
    from app.webhooks import router as webhooks_router
    print(f"[DEBUG] Webhooks router geïmporteerd: {len(webhooks_router.routes)} routes")
except Exception as e:
    print(f"[ERROR] Webhooks router import gefaald: {e}")
    import traceback
    traceback.print_exc()
    raise

# Import mail router met error handling voor debugging
mail_router = None
try:
    from app.mail_routes import router as mail_router
    print(f"[DEBUG] Mail router geïmporteerd: {len(mail_router.routes)} routes")
except Exception as e:
    print(f"[ERROR] Mail router import gefaald: {e}")
    print(f"[ERROR] Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()
    mail_router = None
    # Mail router is optioneel, niet kritiek voor startup

# Import chat router
chat_router = None
try:
    from app.chat_routes import router as chat_router
    print(f"[DEBUG] Chat router geïmporteerd: {len(chat_router.routes)} routes")
except Exception as e:
    print(f"[ERROR] Chat router import gefaald: {e}")
    print(f"[ERROR] Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()
    chat_router = None
    # Chat router is optioneel, niet kritiek voor startup

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
if mail_router is not None:
    try:
        app.include_router(mail_router)
        print(f"[DEBUG] Mail router geregistreerd in app met {len(mail_router.routes)} routes")
    except Exception as e:
        print(f"[ERROR] Mail router registratie gefaald: {e}")
        print(f"[ERROR] Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        # Mail router is optioneel, niet kritiek voor startup
else:
    print(f"[WARNING] Mail router niet beschikbaar - skip registratie")

app.include_router(templates_router)

# Include designer routes
from app.designer_routes import router as designer_router
app.include_router(designer_router)
print(f"[DEBUG] Designer router geregistreerd in app")

# Include admin routes
try:
    from app.admin_routes import router as admin_router, setup_router as admin_setup_router
    from app.admin_order_routes import router as admin_order_router
    from app.admin_klant_routes import router as admin_klant_router
    from app.admin_artikelen_routes import router as admin_artikelen_router
    app.include_router(admin_router)
    app.include_router(admin_setup_router)
    app.include_router(admin_order_router)
    app.include_router(admin_klant_router)
    app.include_router(admin_artikelen_router)
    print(f"[DEBUG] Admin routers geregistreerd in app")
except Exception as e:
    print(f"[WARNING] Admin router niet beschikbaar: {e}")

# Include chat routes
if chat_router is not None:
    try:
        app.include_router(chat_router)
        print(f"[DEBUG] Chat router geregistreerd in app met {len(chat_router.routes)} routes")
    except Exception as e:
        print(f"[ERROR] Chat router registratie gefaald: {e}")
        import traceback
        traceback.print_exc()
        # Chat router is optioneel, niet kritiek voor startup
else:
    print(f"[WARNING] Chat router niet beschikbaar - skip registratie")

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
# Verplaatst naar startup event zodat alle routers geregistreerd zijn


# Achtergrondtaak voor inkomende mail polling
async def poll_inkomende_mails():
    """Poll elke 60 seconden voor nieuwe inkomende mails"""
    while True:
        try:
            if mail_router is not None:
                from app.mail import haal_inkomende_mails
                result = haal_inkomende_mails()
                if result["success"] and result["aantal_verwerkt"] > 0:
                    print(f"[MAIL POLL] {result['aantal_verwerkt']} nieuwe mails verwerkt")
        except Exception as e:
            print(f"[MAIL POLL ERROR] Fout bij ophalen inkomende mails: {e}")
        
        await asyncio.sleep(60)  # Wacht 60 seconden


@app.on_event("startup")
async def startup_event():
    """Start achtergrondtaak voor mail polling bij startup en print routes"""
    # Print alle geregistreerde routes
    print_routes()
    
    # Start mail polling achtergrondtaak (alleen als enabled via env var)
    mail_polling_enabled = os.getenv("MAIL_POLLING_ENABLED", "false").lower() == "true"
    
    if mail_router is not None and mail_polling_enabled:
        print("[STARTUP] Start achtergrondtaak voor inkomende mail polling")
        asyncio.create_task(poll_inkomende_mails())
    elif mail_router is None:
        print("[STARTUP] Mail router niet beschikbaar - skip mail polling")
    else:
        print("[STARTUP] Mail polling uitgeschakeld (MAIL_POLLING_ENABLED niet 'true')")
    
    # Start dagelijkse factuur scheduler
    try:
        from app.factuur_scheduler import run_daily_factuur_check
        print("[STARTUP] Start achtergrondtaak voor automatische facturen")
        asyncio.create_task(run_daily_factuur_check())
    except Exception as e:
        print(f"[WARNING] Factuur scheduler niet beschikbaar: {e}")
    
    # Start dagelijkse planning scheduler
    try:
        from app.planning_scheduler import run_daily_planning_check
        print("[STARTUP] Start achtergrondtaak voor automatische planning emails")
        asyncio.create_task(run_daily_planning_check())
    except Exception as e:
        print(f"[WARNING] Planning scheduler niet beschikbaar: {e}")
    
    # Start dagelijkse herinnering scheduler
    try:
        from app.herinnering_scheduler import run_daily_herinnering_check
        print("[STARTUP] Start achtergrondtaak voor automatische herinneringen")
        asyncio.create_task(run_daily_herinnering_check())
    except Exception as e:
        print(f"[WARNING] Herinnering scheduler niet beschikbaar: {e}")
    
    # Start dagelijkse opvolging scheduler
    try:
        from app.opvolging_scheduler import run_daily_opvolging_check
        print("[STARTUP] Start achtergrondtaak voor automatische 48u opvolging")
        asyncio.create_task(run_daily_opvolging_check())
    except Exception as e:
        print(f"[WARNING] Opvolging scheduler niet beschikbaar: {e}")
    
    # Voer database migratie 004 uit
    try:
        from scripts.run_migration_004 import run_migration_004
        print("[STARTUP] Voer database migratie 004 uit...")
        run_migration_004()
    except Exception as e:
        print(f"[WARNING] Migratie 004 niet beschikbaar: {e}")
    
    # Voer database migratie 005 uit
    try:
        from scripts.run_migration_005 import run_migration_005
        print("[STARTUP] Voer database migratie 005 uit...")
        run_migration_005()
    except Exception as e:
        print(f"[WARNING] Migratie 005 niet beschikbaar: {e}")
    