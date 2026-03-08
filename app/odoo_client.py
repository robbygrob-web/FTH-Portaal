import logging
import xmlrpc.client
import threading
from fastapi import HTTPException
from functools import lru_cache
from app.config import get_odoo_base_url, get_odoo_db, get_odoo_login, get_odoo_api_key

_LOG = logging.getLogger(__name__)

class OdooClient:
    def __init__(self):
        odoo_base_url = get_odoo_base_url()
        odoo_db = get_odoo_db()
        odoo_login = get_odoo_login()
        odoo_api_key = get_odoo_api_key()
        
        if not odoo_base_url:
            raise RuntimeError("ODOO_BASE_URL is vereist maar niet ingesteld")
        if not odoo_db:
            raise RuntimeError("ODOO_DB is vereist maar niet ingesteld")
        if not odoo_login:
            raise RuntimeError("ODOO_LOGIN is vereist maar niet ingesteld")
        if not odoo_api_key:
            raise RuntimeError("ODOO_API_KEY is vereist maar niet ingesteld")
        
        # DEBUG: Toon ruwe ODOO_BASE_URL
        print(f"[DEBUG OdooClient.__init__] Ruwe ODOO_BASE_URL uit .env: {odoo_base_url}")
        
        base_url = odoo_base_url.rstrip('/')
        self.common_url = f"{base_url}/xmlrpc/2/common"
        self.object_url = f"{base_url}/xmlrpc/2/object"
        self.db = odoo_db
        self.username = odoo_login
        self.password = odoo_api_key
        
        # DEBUG: Toon samengestelde URL
        print(f"[DEBUG OdooClient.__init__] XML-RPC common endpoint: {self.common_url}")
        print(f"[DEBUG OdooClient.__init__] Protocol: XML-RPC (via xmlrpc.client)")

        self._common_proxy = xmlrpc.client.ServerProxy(self.common_url, allow_none=True)
        self._object_proxy = xmlrpc.client.ServerProxy(self.object_url, allow_none=True)
        self._auth_lock = threading.Lock()
        self.uid = self._login()

    def _login(self) -> int:
        # DEBUG: Toon authenticatie info
        print(f"[DEBUG _login] Authenticeren met XML-RPC authenticate()")
        print(f"[DEBUG _login] Database: {self.db}, Username: {self.username}")
        
        try:
            uid = self._common_proxy.authenticate(self.db, self.username, self.password, {})
            
            if not uid:
                _LOG.error("Odoo authenticate() mislukt - geen uid in result")
                raise RuntimeError(
                    "Odoo authenticate() mislukt. De server reageert, maar de authenticatie is geweigerd. "
                    "Controleer: gebruikersnaam (ODOO_LOGIN), API key (ODOO_API_KEY) en database naam (ODOO_DB)."
                )
            
            print(f"[DEBUG _login] Authenticatie succesvol, UID: {uid}")
            return uid
            
        except xmlrpc.client.Fault as e:
            error_detail = f"Odoo authenticate() fout: {e.faultCode} - {e.faultString}"
            _LOG.error("Odoo authenticate() fout: %r", e)
            raise RuntimeError(f"Odoo authenticate() mislukt. {error_detail}")
        except Exception as e:
            _LOG.error("Odoo verbinding fout: %s", e)
            raise HTTPException(status_code=502, detail="Odoo onbereikbaar.")

    def execute_kw(self, model: str, method: str, domain, options=None):
        try:
            result = self._object_proxy.execute_kw(
                self.db, self.uid, self.password,
                model, method, [domain], options or {}
            )
            return result
            
        except xmlrpc.client.Fault as e:
            # Check if it's an access denied error
            if e.faultCode == 1 or "access" in str(e.faultString).lower() or "denied" in str(e.faultString).lower():
                old_uid = self.uid
                with self._auth_lock:
                    if self.uid == old_uid:
                        _LOG.info("Odoo sessie verlopen. Herlogin uitgevoerd.")
                        self.uid = self._login()
                # Retry with new UID
                result = self._object_proxy.execute_kw(
                    self.db, self.uid, self.password,
                    model, method, [domain], options or {}
                )
                return result
            else:
                error_detail = f"Odoo verwerkingsfout: {e.faultCode} - {e.faultString}"
                _LOG.error("Odoo RPC Fout in %s.%s: %r", model, method, e)
                raise HTTPException(status_code=502, detail=error_detail)
        except Exception as e:
            _LOG.error("Odoo verbinding fout: %s", e)
            raise HTTPException(status_code=502, detail="Odoo onbereikbaar.")

@lru_cache(maxsize=1)
def get_odoo_client() -> OdooClient:
    return OdooClient()
