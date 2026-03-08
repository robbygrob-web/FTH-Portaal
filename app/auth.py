import os
import logging
import requests
from fastapi import HTTPException
from typing import Optional
from functools import lru_cache
from app.config import get_odoo_base_url, get_odoo_db, get_odoo_login, get_odoo_api_key

_LOG = logging.getLogger(__name__)

class PartnerAuth:
    """Authenticatie voor partners (leveranciers) via Odoo"""
    
    def __init__(self):
        odoo_base_url = get_odoo_base_url()
        odoo_db = get_odoo_db()
        if not odoo_base_url or not odoo_db:
            raise RuntimeError("ODOO_BASE_URL en ODOO_DB zijn vereist voor partner authenticatie")
        
        self.url = f"{odoo_base_url.rstrip('/')}/jsonrpc"
        self.db = odoo_db
    
    def authenticate_partner(self, email: str, password: str) -> Optional[dict]:
        """
        Authenticeer een partner met email en wachtwoord.
        Retourneert partner informatie als succesvol, anders None.
        """
        try:
            # Login als partner
            payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "common",
                    "method": "login",
                    "args": [self.db, email, password]
                },
                "id": 1,
            }
            
            resp = requests.post(self.url, json=payload, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            
            uid = result.get("result")
            if not uid:
                return None
            
            # Haal partner informatie op
            partner_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": [
                        self.db,
                        uid,
                        password,
                        "res.partner",
                        "search_read",
                        [[["email", "=", email]]],
                        {"fields": ["id", "name", "email", "is_company"], "limit": 1}
                    ]
                },
                "id": 2,
            }
            
            partner_resp = requests.post(self.url, json=partner_payload, timeout=10)
            partner_resp.raise_for_status()
            partner_result = partner_resp.json()
            
            partners = partner_result.get("result", [])
            
            # Als partner niet gevonden via email, probeer via user record
            if not partners:
                user_payload = {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "service": "object",
                        "method": "execute_kw",
                        "args": [
                            self.db,
                            uid,
                            password,
                            "res.users",
                            "read",
                            [[uid]],
                            {"fields": ["partner_id", "name"]}
                        ]
                    },
                    "id": 3,
                }
                
                user_resp = requests.post(self.url, json=user_payload, timeout=10)
                user_resp.raise_for_status()
                user_result = user_resp.json()
                users = user_result.get("result", [])
                
                if users and users[0].get("partner_id"):
                    partner_id = users[0]["partner_id"][0]
                    partner_name = users[0]["partner_id"][1]
                    return {
                        "id": partner_id,
                        "name": partner_name,
                        "email": email,
                        "uid": uid,
                    }
                return None
            
            partner = partners[0]
            return {
                "id": partner["id"],
                "name": partner["name"],
                "email": partner.get("email", email),
                "uid": uid,
            }
            
        except Exception as e:
            _LOG.error(f"Partner authenticatie fout: {e}")
            return None
    
    def get_partner_by_id(self, partner_id: int) -> Optional[dict]:
        """
        Haal partner informatie op met admin credentials.
        Gebruikt voor verificatie zonder partner wachtwoord.
        """
        try:
            admin_username = get_odoo_login()
            admin_password = get_odoo_api_key()
            
            # Login als admin
            login_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "common",
                    "method": "login",
                    "args": [self.db, admin_username, admin_password]
                },
                "id": 1,
            }
            
            resp = requests.post(self.url, json=login_payload, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            
            uid = result.get("result")
            if not uid:
                return None
            
            # Haal partner op
            partner_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "object",
                    "method": "execute_kw",
                    "args": [
                        self.db,
                        uid,
                        admin_password,
                        "res.partner",
                        "read",
                        [[partner_id]],
                        {"fields": ["id", "name", "email", "is_company"]}
                    ]
                },
                "id": 2,
            }
            
            partner_resp = requests.post(self.url, json=partner_payload, timeout=10)
            partner_resp.raise_for_status()
            partner_result = partner_resp.json()
            
            partners = partner_result.get("result", [])
            if partners:
                return partners[0]
            return None
            
        except Exception as e:
            _LOG.error(f"Partner ophalen fout: {e}")
            return None

@lru_cache(maxsize=1)
def get_partner_auth() -> PartnerAuth:
    """
    Lazy instantiatie van PartnerAuth.
    Wordt alleen aangemaakt wanneer nodig, niet bij import.
    """
    return PartnerAuth()
