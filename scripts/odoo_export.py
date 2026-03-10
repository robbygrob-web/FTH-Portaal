"""
Script om per model 1 voorbeeldrecord op te halen en veldgegevens te exporteren.
Toont alleen velden met daadwerkelijke data (niet False, None, lege string).
"""
import sys
import os
from pathlib import Path

# Voeg project root toe aan Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Laad environment variabelen
from dotenv import load_dotenv
load_dotenv()

from app.odoo_client import get_odoo_client


def format_value(value):
    """Format een waarde voor weergave. Retourneert None als waarde leeg/ongeldig is."""
    if value is None:
        return None
    # Boolean False is een geldige waarde (wordt apart afgehandeld)
    if isinstance(value, bool):
        return value
    # False voor non-boolean velden betekent "niet ingevuld" in Odoo
    if value is False:
        return None
    # Lege lijsten zijn niet interessant
    if isinstance(value, (list, tuple)):
        if len(value) == 0:
            return None
        # Odoo Many2one/Many2many format: [id, name] of [id]
        if len(value) == 2:
            return f"{value[1]} (ID: {value[0]})"
        return str(value[0]) if len(value) > 0 else None
    # Lege strings zijn niet interessant
    if isinstance(value, str) and value.strip() == "":
        return None
    # 0 is een geldige waarde (kan betekenisvol zijn)
    return value


def get_field_type_label(field_info):
    """Haal veldtype en label op uit field info"""
    field_type = field_info.get('type', 'unknown')
    field_label = field_info.get('string', '')
    return field_type, field_label


def export_model_fields(model_name, output_lines, print_output=True):
    """Export veldgegevens voor een specifiek model"""
    try:
        client = get_odoo_client()
        
        # Haal veld metadata op
        fields_info = client.execute_kw(
            model_name,
            "fields_get",
            [],
            {}
        )
        
        # Zoek 1 voorbeeldrecord
        record_ids = client.execute_kw(
            model_name,
            "search",
            [],
            {"limit": 1}
        )
        
        if not record_ids:
            if print_output:
                print(f"\n[WARNING] Model '{model_name}': Geen records gevonden")
            output_lines.append(f"\n## Model: {model_name}\n")
            output_lines.append(f"[WARNING] Geen records gevonden\n")
            return
        
        # Haal het record op met alle velden
        record = client.execute_kw(
            model_name,
            "read",
            [record_ids[0]],
            {"fields": list(fields_info.keys())}
        )[0]
        
        if print_output:
            print(f"\n{'='*80}")
            print(f"Model: {model_name}")
            print(f"Record ID: {record_ids[0]}")
            print(f"{'='*80}")
        
        output_lines.append(f"\n## Model: {model_name}\n")
        output_lines.append(f"**Record ID:** {record_ids[0]}\n")
        output_lines.append("| Veldnaam | Type | Label | Waarde |\n")
        output_lines.append("|----------|------|------|--------|\n")
        
        # Sorteer velden alfabetisch
        sorted_fields = sorted(fields_info.items())
        
        fields_with_data = []
        
        for field_name, field_info in sorted_fields:
            value = record.get(field_name)
            field_type = field_info.get('type', '')
            
            # Skip velden zonder waarde
            if value is None:
                continue
            
            # Boolean velden: behoud True en False
            if field_type == 'boolean':
                formatted_value = value
            else:
                # Voor non-boolean velden: False betekent "niet ingevuld" in Odoo
                if value is False:
                    continue
                formatted_value = format_value(value)
                # Skip None waarden (lege strings, lege lijsten, etc.)
                if formatted_value is None:
                    continue
            
            field_type, field_label = get_field_type_label(field_info)
            
            # Format waarde voor tabel
            if isinstance(formatted_value, bool):
                display_value = str(formatted_value)
            elif isinstance(formatted_value, (int, float)):
                display_value = str(formatted_value)
            else:
                display_value = str(formatted_value)
                # Escape pipe characters voor markdown tabel
                display_value = display_value.replace('|', '\\|')
                # Truncate lange waarden
                if len(display_value) > 100:
                    display_value = display_value[:97] + "..."
            
            fields_with_data.append({
                'name': field_name,
                'type': field_type,
                'label': field_label,
                'value': display_value
            })
            
            if print_output:
                print(f"  {field_name:40} [{field_type:15}] {field_label:30} = {display_value}")
        
        # Schrijf naar output
        for field in fields_with_data:
            output_lines.append(f"| `{field['name']}` | {field['type']} | {field['label']} | {field['value']} |\n")
        
        if not fields_with_data:
            output_lines.append("[WARNING] Geen velden met data gevonden\n")
            if print_output:
                print("  [WARNING] Geen velden met data gevonden")
        
    except Exception as e:
        error_msg = f"Fout bij exporteren van {model_name}: {str(e)}"
        if print_output:
            print(f"\n[ERROR] {error_msg}")
        output_lines.append(f"\n## Model: {model_name}\n")
        output_lines.append(f"[ERROR] {error_msg}\n")


def main():
    """Hoofdfunctie"""
    # Definieer modellen om te exporteren
    models = [
        "res.partner",
        "sale.order",
        "account.move",
        "mail.message",
    ]
    
    output_lines = []
    output_lines.append("# Odoo Field Export - Volledige Velden\n")
    output_lines.append(f"*Gegenereerd op: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
    output_lines.append("\nDit document bevat alle velden met data uit voorbeeldrecords per model.\n")
    
    print("="*80)
    print("Odoo Field Export Script")
    print("="*80)
    
    for model in models:
        export_model_fields(model, output_lines, print_output=True)
    
    # Schrijf naar bestand
    output_file = project_root / "docs" / "odoo_fields_full.md"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)
    
    print(f"\n{'='*80}")
    print(f"[SUCCESS] Export voltooid!")
    print(f"[INFO] Output geschreven naar: {output_file}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
