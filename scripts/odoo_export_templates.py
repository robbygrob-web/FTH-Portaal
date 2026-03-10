"""
Script om mail templates en automatiseringsregels uit Odoo te exporteren.
Slaat op als JSON bestanden voor documentatie.
"""
import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Voeg project root toe aan Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Laad .env bestand
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

from app.odoo_client import get_odoo_client

# Output directories
docs_dir = Path(__file__).parent.parent / 'docs'
docs_dir.mkdir(exist_ok=True)


def export_mail_templates():
    """Export alle mail templates uit Odoo"""
    print("=" * 60)
    print("Ophalen mail templates uit Odoo...")
    print("=" * 60)
    
    try:
        client = get_odoo_client()
        
        # Haal alle mail templates op
        templates = client.execute_kw(
            "mail.template",
            "search_read",
            [],  # Geen filter, haal alles op
            {
                "fields": [
                    "id",
                    "name",
                    "model_id",
                    "subject",
                    "body_html",
                    "email_from",
                    "email_to",
                    "email_cc",
                    "reply_to",
                    "active"
                ],
                "limit": 1000  # Genoeg voor alle templates
            }
        )
        
        print(f"   [OK] {len(templates)} mail templates gevonden")
        
        # Format voor JSON export
        export_data = []
        for template in templates:
            # Haal model naam op als model_id een tuple is
            model_name = None
            if template.get("model_id") and isinstance(template["model_id"], (list, tuple)):
                model_name = template["model_id"][1] if len(template["model_id"]) > 1 else None
            
            export_data.append({
                "id": template.get("id"),
                "naam": template.get("name"),
                "model": model_name,
                "model_id": template["model_id"][0] if isinstance(template.get("model_id"), (list, tuple)) else template.get("model_id"),
                "onderwerp": template.get("subject"),
                "body_html": template.get("body_html"),
                "email_from": template.get("email_from"),
                "email_to": template.get("email_to"),
                "email_cc": template.get("email_cc"),
                "reply_to": template.get("reply_to"),
                "actief": template.get("active", True)
            })
        
        # Sla op als JSON
        output_file = docs_dir / "odoo_mail_templates.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"   [OK] Opgeslagen in: {output_file}")
        return export_data
        
    except Exception as e:
        print(f"   [ERROR] Fout bij ophalen mail templates: {e}")
        import traceback
        traceback.print_exc()
        return None


def export_automations():
    """Export alle automatiseringsregels uit Odoo"""
    print("\n" + "=" * 60)
    print("Ophalen automatiseringsregels uit Odoo...")
    print("=" * 60)
    
    try:
        client = get_odoo_client()
        
        # Haal alle automatiseringsregels op (gebruik alleen basisvelden)
        automations = client.execute_kw(
            "base.automation",
            "search_read",
            [],  # Geen filter, haal alles op
            {
                "fields": [
                    "id",
                    "name",
                    "model_id",
                    "trigger",
                    "trg_date_id",
                    "trg_date_range",
                    "trg_date_range_type",
                    "active"
                ],
                "limit": 1000  # Genoeg voor alle automations
            }
        )
        
        print(f"   [OK] {len(automations)} automatiseringsregels gevonden")
        
        # Haal actie details op voor elke automation
        export_data = []
        for automation in automations:
            # Haal model naam op
            model_name = None
            if automation.get("model_id") and isinstance(automation["model_id"], (list, tuple)):
                model_name = automation["model_id"][1] if len(automation["model_id"]) > 1 else None
            
            # Haal actie details op via ir.actions.server (als automation actie heeft)
            action_details = None
            try:
                # Zoek naar gerelateerde server acties
                action_ids = client.execute_kw(
                    "ir.actions.server",
                    "search",
                    [("usage", "=", "ir_actions_server")],
                    {}
                )
                # Probeer actie te vinden die bij deze automation hoort
                # Dit is een benadering - base.automation heeft geen directe relatie
                if action_ids:
                    # Haal eerste paar acties op voor referentie
                    actions = client.execute_kw(
                        "ir.actions.server",
                        "read",
                        [action_ids[:5]],  # Limiteer tot eerste 5
                        {
                            "fields": [
                                "id",
                                "name",
                                "state",
                                "model_id",
                                "code",
                                "template_id",
                                "email_to",
                                "email_cc"
                            ]
                        }
                    )
                    # Note: We kunnen niet direct linken zonder extra velden
            except Exception as e:
                pass  # Negeer als acties niet opgehaald kunnen worden
            
            export_data.append({
                "id": automation.get("id"),
                "naam": automation.get("name"),
                "model": model_name,
                "model_id": automation["model_id"][0] if isinstance(automation.get("model_id"), (list, tuple)) else automation.get("model_id"),
                "trigger": automation.get("trigger"),
                "trg_date_id": automation.get("trg_date_id"),
                "trg_date_range": automation.get("trg_date_range"),
                "trg_date_range_type": automation.get("trg_date_range_type"),
                "actief": automation.get("active", True)
            })
        
        # Sla op als JSON
        output_file = docs_dir / "odoo_automations.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"   [OK] Opgeslagen in: {output_file}")
        return export_data
        
    except Exception as e:
        print(f"   [ERROR] Fout bij ophalen automatiseringsregels: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Hoofdfunctie"""
    print("\n" + "=" * 60)
    print("Odoo Templates & Automations Exporter")
    print("=" * 60)
    
    # Export mail templates
    templates = export_mail_templates()
    
    # Export automations
    automations = export_automations()
    
    # Samenvatting
    print("\n" + "=" * 60)
    print("EXPORT VOLTOOID")
    print("=" * 60)
    if templates:
        print(f"[OK] Mail templates: {len(templates)} stuks")
        print(f"  -> docs/odoo_mail_templates.json")
    if automations:
        print(f"[OK] Automatiseringsregels: {len(automations)} stuks")
        print(f"  -> docs/odoo_automations.json")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
