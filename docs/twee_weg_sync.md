# Twee-weg Contact Synchronisatie

Dit document beschrijft de twee-weg synchronisatie tussen Odoo en de eigen PostgreSQL database voor de overgangsfase.

## Overzicht

De synchronisatie bestaat uit twee flows:

1. **FLOW 1: Odoo → eigen DB** (via webhook)
2. **FLOW 2: eigen DB → Odoo** (via functie call)

## FLOW 1: Odoo → eigen DB

### Webhook Endpoint

**POST** `/webhooks/odoo/contact`

### Authenticatie

Verificatie via header:
```
X-Odoo-Webhook-Token: <WEBHOOK_SECRET>
```

### Request Body

```json
{
  "event": "create" | "update" | "delete",
  "data": {
    "id": 123,
    "name": "Bedrijfsnaam",
    "email": "contact@example.com",
    "phone": "+31612345678",
    "street": "Straatnaam 123",
    "zip": "1234 AB",
    "city": "Amsterdam",
    "country_code": "NL",
    "vat": "NL123456789B01",
    "company_type": "company",
    "is_company": true,
    "x_studio_portaal_partner": false,
    "x_studio_partner_commission": 0.0,
    "x_studio_self_owned": false,
    "x_studio_wordpress_id": 0,
    "peppol_endpoint": "",
    "peppol_eas": "",
    "peppol_verification_state": "not_verified",
    "active": true
  }
}
```

### Response

```json
{
  "status": "success",
  "event": "update",
  "odoo_id": 123
}
```

### Odoo Configuratie

In Odoo moet een webhook worden geconfigureerd die naar dit endpoint stuurt bij:
- `res.partner` create events
- `res.partner` write events  
- `res.partner` unlink events

**Belangrijk:** Configureer Odoo om webhooks alleen te triggeren bij handmatige wijzigingen, niet bij automatische synchronisaties.

## FLOW 2: eigen DB → Odoo

### Functie: `sync_contact_naar_odoo()`

Synchroniseer een contact van eigen DB naar Odoo.

**Locatie:** `app/odoo_sync.py`

**Gebruik:**

```python
from app.odoo_sync import sync_contact_naar_odoo

# Synchroniseer contact naar Odoo
contact_id = "uuid-van-contact"
odoo_id = sync_contact_naar_odoo(contact_id)

if odoo_id:
    print(f"Contact gesynchroniseerd naar Odoo: {odoo_id}")
else:
    print("Synchronisatie mislukt")
```

### Functie: `sync_bank_naar_odoo()`

Synchroniseer bankgegevens van eigen DB naar Odoo.

**Gebruik:**

```python
from app.odoo_sync import sync_bank_naar_odoo

contact_id = "uuid-van-contact"
success = sync_bank_naar_odoo(contact_id)

if success:
    print("Bankgegevens gesynchroniseerd")
```

### Integratie in Routes

Voeg synchronisatie toe bij create/update operaties:

```python
from app.odoo_sync import sync_contact_naar_odoo, sync_bank_naar_odoo

@router.post("/api/contacten")
async def create_contact(...):
    # ... maak contact aan in eigen DB ...
    
    # Synchroniseer naar Odoo
    sync_contact_naar_odoo(contact_id)
    sync_bank_naar_odoo(contact_id)
    
    return {"success": True, "contact_id": contact_id}
```

## Voorkomen van Loops

**Belangrijk:** Om oneindige synchronisatie loops te voorkomen:

1. **Odoo webhook** triggert alleen bij handmatige wijzigingen
2. **sync_contact_naar_odoo()** triggert GEEN webhook terug (Odoo configuratie)
3. Webhook endpoint controleert niet of wijziging van sync komt (Odoo moet dit voorkomen)

## Environment Variabelen

Voeg toe aan `.env`:

```env
WEBHOOK_SECRET=your-secret-webhook-token-here
DATABASE_URL=postgresql://user:password@host:port/database
```

## Velden Mapping

### Odoo → PostgreSQL

| Odoo Veld | PostgreSQL Veld | Opmerking |
|-----------|----------------|-----------|
| `id` | `odoo_id` | Unieke referentie |
| `name` | `naam` | |
| `email` | `email` | |
| `phone` | `telefoon` | |
| `street` | `straat` | |
| `zip` | `postcode` | |
| `city` | `stad` | |
| `country_code` | `land_code` | Default: "NL" |
| `vat` | `btw_nummer` | |
| `company_type` | `bedrijfstype` | company/person/contact |
| `x_studio_portaal_partner` | `is_portaal_partner` | |
| `x_studio_partner_commission` | `partner_commissie` | |
| `x_studio_self_owned` | `heeft_eigen_truck` | |
| `x_studio_wordpress_id` | `wordpress_id` | |
| `peppol_endpoint` | `peppol_endpoint` | |
| `peppol_eas` | `peppol_eas` | |
| `peppol_verification_state` | `peppol_verificatie_status` | |
| `active` | `actief` | |
| `res.partner.bank.acc_number` | `iban` | Via aparte query |
| `res.partner.bank.acc_holder_name` | `bank_tenaamstelling` | Via aparte query |

### PostgreSQL → Odoo

Omgekeerde mapping van bovenstaande tabel.

## Testing

### Test Webhook (FLOW 1)

```bash
curl -X POST http://localhost:8000/webhooks/odoo/contact \
  -H "Content-Type: application/json" \
  -H "X-Odoo-Webhook-Token: your-secret" \
  -d '{
    "event": "create",
    "data": {
      "id": 999,
      "name": "Test Contact",
      "email": "test@example.com",
      "active": true
    }
  }'
```

### Test Sync Functie (FLOW 2)

```python
from app.odoo_sync import sync_contact_naar_odoo

# Test met bestaand contact ID
contact_id = "uuid-van-test-contact"
odoo_id = sync_contact_naar_odoo(contact_id)
print(f"Odoo ID: {odoo_id}")
```

## Troubleshooting

### Webhook wordt niet aangeroepen

1. Controleer `WEBHOOK_SECRET` in `.env`
2. Controleer Odoo webhook configuratie
3. Controleer firewall/netwerk instellingen

### Synchronisatie loops

1. Controleer Odoo webhook configuratie (alleen handmatige wijzigingen)
2. Controleer of `sync_contact_naar_odoo()` niet wordt aangeroepen vanuit webhook handler

### Database errors

1. Controleer `DATABASE_URL` in `.env`
2. Controleer database connectie
3. Controleer tabel structuur (`contacten` tabel moet bestaan)
