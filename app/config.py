"""
Centrale configuratiemodule voor FTH Portaal.

Valideert vereiste configuratie en biedt toegang tot omgevingsvariabelen.
Let op: load_dotenv() wordt aangeroepen in main.py, niet hier.
"""
import os
import sys
from typing import Tuple

# Vereiste Odoo omgevingsvariabelen
REQUIRED_ODOO_VARS = [
    "ODOO_BASE_URL",
    "ODOO_DB",
    "ODOO_LOGIN",
    "ODOO_API_KEY",
]

# Optionele omgevingsvariabelen
OPTIONAL_VARS = {
    "SESSION_SECRET": "tijdelijk_geheim_wachtwoord_1234567890",
}

def validate_odoo_config() -> Tuple[bool, list]:
    """
    Valideer of alle vereiste Odoo omgevingsvariabelen zijn ingesteld.
    
    Returns:
        tuple: (is_valid, missing_vars)
    """
    missing = []
    for var in REQUIRED_ODOO_VARS:
        if not os.getenv(var):
            missing.append(var)
    
    return (len(missing) == 0, missing)

def get_config_value(key: str, default: str = None) -> str:
    """
    Haal een configuratie waarde op uit omgevingsvariabelen.
    
    Args:
        key: De naam van de omgevingsvariabele
        default: Optionele standaardwaarde
        
    Returns:
        De waarde van de omgevingsvariabele of de standaardwaarde
    """
    return os.getenv(key, default)

# Configuratie waarden
ODOO_BASE_URL = get_config_value("ODOO_BASE_URL")
ODOO_DB = get_config_value("ODOO_DB")
ODOO_LOGIN = get_config_value("ODOO_LOGIN")
ODOO_API_KEY = get_config_value("ODOO_API_KEY")
SESSION_SECRET = get_config_value("SESSION_SECRET", OPTIONAL_VARS["SESSION_SECRET"])

def startup_validation():
    """
    Voer startup validatie uit en rapporteer ontbrekende variabelen.
    Wordt aangeroepen bij applicatie start.
    
    Raises:
        SystemExit: Als vereiste variabelen ontbreken
    """
    is_valid, missing = validate_odoo_config()
    
    if not is_valid:
        print("=" * 60, file=sys.stderr)
        print("FOUT: Ontbrekende vereiste omgevingsvariabelen", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("\nDe volgende variabelen zijn vereist maar niet ingesteld:", file=sys.stderr)
        for var in missing:
            print(f"  - {var}", file=sys.stderr)
        print("\nZorg ervoor dat deze variabelen zijn ingesteld:", file=sys.stderr)
        print("  - Lokaal: in het .env bestand", file=sys.stderr)
        print("  - Railway: als omgevingsvariabelen in Railway dashboard", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        sys.exit(1)
    
    # Optionele validatie: waarschuw als SESSION_SECRET de standaardwaarde gebruikt
    if SESSION_SECRET == OPTIONAL_VARS["SESSION_SECRET"]:
        print("WAARSCHUWING: SESSION_SECRET gebruikt standaardwaarde. Stel een unieke waarde in voor productie.", file=sys.stderr)
