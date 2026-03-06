app/odoo_client.py
import os
import logging
import requests
import threading
from fastapi import HTTPException
from functools import lru_cache

_LOG = logging.getLogger(__name__)

class OdooClient:
    def __init__(self):
        self.url = f"{os.getenv('ODOO_URL')}/jsonrpc"
        self.db = os.getenv("ODOO_DB")
        self.username = os.getenv("ODOO_USER")
        self.password = os.getenv("ODOO_PASS")

        if not all([self.url, self.db, self.username, self.password]):
            raise RuntimeError("Kritieke Odoo omgevingsvariabelen ontbreken in de configuratie.")

        self.session = requests.Session()
        # Locks voor thread-safety
        self._http_lock = threading.Lock()
        self._auth_lock = threading.Lock()
        self.uid = self._login()

    def _safe_post(self, payload: dict, timeout: int = 20) -> dict:
        try:
            with self._http_lock:
                r = self.session.post(self.url, json=payload, timeout=timeout)
                r.raise_for_status()
                try:
                    return r.json()
                except ValueError:
                    _LOG.error(
                        "Odoo non-JSON response. status=%s ct=%s head=%r",
                        r.status_code,
                        r.headers.get("content-type"),
                        (r.text or "")[:200],
                    )
                    raise HTTPException(status_code=502, detail="Odoo gaf een ongeldig antwoord.")
        except requests.exceptions.Timeout:
            raise HTTPException(status_code=504, detail="Odoo reageert te traag.")
        except requests.exceptions.RequestException as e:
            _LOG.error("Odoo verbinding fout: %s", e)
            raise HTTPException(status_code=502, detail="Odoo onbereikbaar.")

    def _is_access_denied(self, err: dict) -> bool:
        data = err.get("data") or {}
        name = (data.get("name") or "")
        msg = f"{err.get('message') or ''} {data.get('message') or ''}"
        blob = str(err)
        s = (name + " " + msg + " " + blob).lower()
        return any(x in s for x in ["accessdenied", "access denied", "session expired"])

    def _login(self) -> int:
        payload = {
            "jsonrpc": "2.0", "method": "call",
            "params": {
                "service": "common", "method": "login",
                "args": [self.db, self.username, self.password]
            },
            "id": 1,
        }
        resp = self._safe_post(payload, timeout=10)
        uid = resp.get("result")
        if not uid:
            raise RuntimeError("Odoo login mislukt. Controleer credentials.")
        return uid

    def execute_kw(self, model: str, method: str, *args, **kwargs):
        def _payload(uid: int):
            return {
                "jsonrpc": "2.0", "method": "call",
                "params": {
                    "service": "object", "method": "execute_kw",
                    "args": [self.db, uid, self.password, model, method, list(args), kwargs or {}]
                },
                "id": 1,
            }

        resp = self._safe_post(_payload(self.uid))

        # Dubbele check met lock om login-storms te voorkomen
        if "error" in resp and self._is_access_denied(resp["error"]):
            old_uid = self.uid
            with self._auth_lock:
                if self.uid == old_uid:
                    _LOG.info("Odoo sessie verlopen. Herlogin uitgevoerd.")
                    self.uid = self._login()
            resp = self._safe_post(_payload(self.uid))

        if "error" in resp:
            _LOG.error("Odoo RPC Fout in %s.%s: %r", model, method, resp["error"])
            raise HTTPException(status_code=502, detail="Odoo verwerkingsfout.")

        return resp.get("result")

@lru_cache(maxsize=1)
def get_odoo_client() -> OdooClient:
    return OdooClient()
