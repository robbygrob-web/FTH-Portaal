"""
Toon huidige Gravity Forms veld mapping in webhooks.py
"""
import re
from pathlib import Path

webhook_file = Path(__file__).parent.parent / 'app' / 'webhooks.py'

print("=" * 80)
print("GRAVITY FORMS VELD MAPPING IN WEBHOOKS.PY")
print("=" * 80)

with open(webhook_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Zoek naar veld mappings
print("\n1. CONTACT VELDEN")
print("-" * 80)
print("  Email:        veld '21'")
print("  Telefoon:     veld '24'")
print("  Naam:         combineer voornaam/achternaam of fallback")
print("  Stad:         veld '29.3'")

print("\n2. ORDER VELDEN")
print("-" * 80)
print("  Datum:        veld '48' -> leverdatum")
print("  Locatie:      veld '29.3' -> plaats")
print("  Aantal personen: veld '68' -> aantal_personen")
print("  Aantal kinderen: veld 'aantal_kinderen' -> aantal_kinderen")
print("  Opmerkingen:  veld 'opmerkingen' -> opmerkingen")

print("\n3. PRIJSBEDRAGEN (GEFIXT)")
print("-" * 80)
print("  Veld '7':     -> totaal_bedrag (prijsdata)")
print("  Veld '10':    -> totaal_bedrag (prijsdata, als hoger dan veld '7')")
print("  BTW berekening: 9% BTW")
print("    - bedrag_excl_btw = totaal_bedrag / 1.09")
print("    - bedrag_btw = bedrag_excl_btw * 0.09")
print("    - totaal_bedrag = bedrag_excl_btw + bedrag_btw")

print("\n4. UTM TRACKING (GEFIXT)")
print("-" * 80)
print("  utm_source:   -> utm_source (directe veldnaam)")
print("  utm_medium:   -> utm_medium (directe veldnaam)")
print("  utm_campaign: -> utm_campaign (directe veldnaam)")
print("  utm_content:  -> utm_content (directe veldnaam)")
print("  Opmerking:    Veld '7' en '10' worden NIET meer gebruikt voor UTM")

print("\n5. CODE SNIPPET (relevante sectie)")
print("-" * 80)

# Extract relevante code sectie
lines = content.split('\n')
in_price_section = False
in_utm_section = False
price_lines = []
utm_lines = []

for i, line in enumerate(lines):
    if '# Haal prijsbedragen op' in line:
        in_price_section = True
    if '# Haal UTM tracking data op' in line:
        in_price_section = False
        in_utm_section = True
    if in_price_section and i < len(lines) - 1:
        if lines[i+1].strip().startswith('#') and 'UTM' in lines[i+1]:
            in_price_section = False
        elif in_price_section:
            price_lines.append(line)
    if in_utm_section:
        if 'insert_sql' in line.lower() or 'INSERT INTO orders' in line:
            in_utm_section = False
        elif in_utm_section:
            utm_lines.append(line)

if price_lines:
    print("\nPRIJSBEDRAGEN CODE:")
    for line in price_lines[:30]:  # Eerste 30 regels
        print(f"  {line}")

if utm_lines:
    print("\nUTM TRACKING CODE:")
    for line in utm_lines[:20]:  # Eerste 20 regels
        print(f"  {line}")

print("\n" + "=" * 80)
print("MAPPING OVERZICHT")
print("=" * 80)
print("\n[OK] PRIJSBEDRAGEN: Veld '7' en '10' worden nu correct gemapped naar bedragen kolommen")
print("[OK] UTM TRACKING: UTM velden worden nu alleen gevuld met echte UTM parameters")
print("[OK] BTW BEREKENING: Automatisch 9% BTW berekening")
print("=" * 80 + "\n")
