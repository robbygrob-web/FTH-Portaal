# Odoo Webhook Setup Instructies

Dit document beschrijft hoe je de webhook in Odoo instelt om automatisch contactwijzigingen te synchroniseren naar onze eigen database.

## Overzicht

- **Endpoint URL:** `https://fth-portaal-production.up.railway.app/webhooks/odoo/contact`
- **Method:** POST
- **Authenticatie:** Via header `X-Odoo-Webhook-Token`
- **Secret:** Zie `.env` bestand (WEBHOOK_SECRET)

## Stap 1: Test Endpoint Controleren

Controleer eerst of het endpoint bereikbaar is:

```bash
curl https://fth-portaal-production.up.railway.app/webhooks/test
```

Verwachte response:
```json
{
  "status": "success",
  "message": "Webhook endpoint is bereikbaar",
  "endpoint": "/webhooks/odoo/contact",
  "method": "POST",
  "required_header": "X-Odoo-Webhook-Token"
}
```

## Stap 2: Odoo Webhook Instellen

### Optie A: Via Odoo Studio (als beschikbaar)

1. **Ga naar Odoo Studio:**
   - Menu: **Apps** → **Studio**
   - Of direct: `https://treatlab-vof1.odoo.com/web#action=base.action_view_base_menu`

2. **Maak een Automatisering:**
   - Klik op **Automatiseringen** (of **Automations**)
   - Klik op **Maken** (Create)

3. **Configureer de Automatisering:**
   - **Naam:** `Sync Contacten naar FTH Portaal`
   - **Model:** `res.partner`
   - **Trigger:** `Bij het creëren en bijwerken van een record` (On create & update)
   - **Filter Domain:** Laat leeg (of gebruik `[('active', '=', True)]` voor alleen actieve contacten)

4. **Voeg Actie toe:**
   - **Actie Type:** `Webhook`
   - **URL:** `https://fth-portaal-production.up.railway.app/webhooks/odoo/contact`
   - **Method:** `POST`
   - **Headers:** 
     ```
     Content-Type: application/json
     X-Odoo-Webhook-Token: eGiEIi_sGOtZYzBCk5R0vSlsjFESE0MM85MRUFxLdS8
     ```
   - **Body (JSON):**
     ```json
     {
       "event": "{{ 'create' if trigger == 'on_create' else 'update' }}",
       "data": {
         "id": {{ object.id }},
         "name": "{{ object.name }}",
         "email": "{{ object.email or '' }}",
         "phone": "{{ object.phone or '' }}",
         "street": "{{ object.street or '' }}",
         "zip": "{{ object.zip or '' }}",
         "city": "{{ object.city or '' }}",
         "country_code": "{{ object.country_code or 'NL' }}",
         "vat": "{{ object.vat or '' }}",
         "company_type": "{{ object.company_type }}",
         "is_company": {{ object.is_company }},
         "x_studio_portaal_partner": {{ object.x_studio_portaal_partner }},
         "x_studio_partner_commission": {{ object.x_studio_partner_commission or 0 }},
         "x_studio_self_owned": {{ object.x_studio_self_owned }},
         "x_studio_wordpress_id": {{ object.x_studio_wordpress_id or 0 }},
         "peppol_endpoint": "{{ object.peppol_endpoint or '' }}",
         "peppol_eas": "{{ object.peppol_eas or '' }}",
         "peppol_verification_state": "{{ object.peppol_verification_state or 'not_verified' }}",
         "active": {{ object.active }}
       }
     }
     ```

5. **Sla op en Activeer**

### Optie B: Via Python Code (Aangepast Module)

Als Studio niet beschikbaar is, maak een aangepast Odoo module:

1. **Maak module structuur:**
   ```
   custom_webhooks/
   ├── __init__.py
   ├── __manifest__.py
   └── models/
       ├── __init__.py
       └── res_partner.py
   ```

2. **`__manifest__.py`:**
   ```python
   {
       'name': 'FTH Portaal Webhooks',
       'version': '1.0',
       'depends': ['base', 'contacts'],
       'data': [],
       'installable': True,
       'application': False,
   }
   ```

3. **`models/res_partner.py`:**
   ```python
   import requests
   import json
   import logging
   from odoo import models, api

   _logger = logging.getLogger(__name__)

   class ResPartner(models.Model):
       _inherit = 'res.partner'

       @api.model
       def create(self, vals):
           partner = super().create(vals)
           self._send_webhook(partner, 'create')
           return partner

       def write(self, vals):
           result = super().write(vals)
           if self:
               self._send_webhook(self, 'update')
           return result

       def unlink(self):
           for partner in self:
               self._send_webhook(partner, 'delete')
           return super().unlink()

       def _send_webhook(self, partner, event):
           try:
               url = 'https://fth-portaal-production.up.railway.app/webhooks/odoo/contact'
               headers = {
                   'Content-Type': 'application/json',
                   'X-Odoo-Webhook-Token': 'eGiEIi_sGOtZYzBCk5R0vSlsjFESE0MM85MRUFxLdS8'
               }
               
               data = {
                   'event': event,
                   'data': {
                       'id': partner.id,
                       'name': partner.name or '',
                       'email': partner.email or '',
                       'phone': partner.phone or '',
                       'street': partner.street or '',
                       'zip': partner.zip or '',
                       'city': partner.city or '',
                       'country_code': partner.country_code or 'NL',
                       'vat': partner.vat or '',
                       'company_type': partner.company_type,
                       'is_company': partner.is_company,
                       'x_studio_portaal_partner': partner.x_studio_portaal_partner,
                       'x_studio_partner_commission': partner.x_studio_partner_commission or 0.0,
                       'x_studio_self_owned': partner.x_studio_self_owned,
                       'x_studio_wordpress_id': partner.x_studio_wordpress_id or 0,
                       'peppol_endpoint': partner.peppol_endpoint or '',
                       'peppol_eas': partner.peppol_eas or '',
                       'peppol_verification_state': partner.peppol_verification_state or 'not_verified',
                       'active': partner.active
                   }
               }
               
               response = requests.post(url, headers=headers, json=data, timeout=10)
               response.raise_for_status()
               _logger.info(f"Webhook sent for partner {partner.id}: {event}")
               
           except Exception as e:
               _logger.error(f"Webhook failed for partner {partner.id}: {str(e)}")
   ```

4. **Installeer module in Odoo**

### Optie C: Via Odoo Automatisering (Basis Automatisering)

Als je Odoo Automatisering hebt (niet Studio):

1. **Ga naar Automatisering:**
   - Menu: **Instellingen** → **Technisch** → **Automatisering** → **Automatiseringen**
   - Of: `https://treatlab-vof1.odoo.com/web#action=base.action_ir_automation`

2. **Maak nieuwe Automatisering:**
   - **Naam:** `Sync Contacten naar FTH Portaal`
   - **Model:** `res.partner`
   - **Trigger:** `Bij het creëren en bijwerken van een record`
   - **Filter:** `[('active', '=', True)]` (optioneel)

3. **Actie Type:** `Python Code`

4. **Python Code:**
   ```python
   import requests
   import json

   url = 'https://fth-portaal-production.up.railway.app/webhooks/odoo/contact'
   headers = {
       'Content-Type': 'application/json',
       'X-Odoo-Webhook-Token': 'eGiEIi_sGOtZYzBCk5R0vSlsjFESE0MM85MRUFxLdS8'
   }

   event = 'create' if trigger == 'on_create' else 'update'
   
   data = {
       'event': event,
       'data': {
           'id': record.id,
           'name': record.name or '',
           'email': record.email or '',
           'phone': record.phone or '',
           'street': record.street or '',
           'zip': record.zip or '',
           'city': record.city or '',
           'country_code': record.country_code or 'NL',
           'vat': record.vat or '',
           'company_type': record.company_type,
           'is_company': record.is_company,
           'x_studio_portaal_partner': record.x_studio_portaal_partner,
           'x_studio_partner_commission': record.x_studio_partner_commission or 0.0,
           'x_studio_self_owned': record.x_studio_self_owned,
           'x_studio_wordpress_id': record.x_studio_wordpress_id or 0,
           'peppol_endpoint': record.peppol_endpoint or '',
           'peppol_eas': record.peppol_eas or '',
           'peppol_verification_state': record.peppol_verification_state or 'not_verified',
           'active': record.active
       }
   }

   try:
       response = requests.post(url, headers=headers, json=data, timeout=10)
       response.raise_for_status()
       log(f"Webhook sent successfully: {response.json()}")
   except Exception as e:
       log(f"Webhook failed: {str(e)}", level='error')
   ```

## Stap 3: Testen

### Test 1: Test Endpoint

```bash
curl https://fth-portaal-production.up.railway.app/webhooks/test
```

### Test 2: Webhook Endpoint (met token)

```bash
curl -X POST https://fth-portaal-production.up.railway.app/webhooks/odoo/contact \
  -H "Content-Type: application/json" \
  -H "X-Odoo-Webhook-Token: eGiEIi_sGOtZYzBCk5R0vSlsjFESE0MM85MRUFxLdS8" \
  -d '{
    "event": "create",
    "data": {
      "id": 999,
      "name": "Test Contact",
      "email": "test@example.com",
      "phone": "+31612345678",
      "active": true
    }
  }'
```

Verwachte response:
```json
{
  "status": "success",
  "event": "create",
  "odoo_id": 999
}
```

### Test 3: Live Test in Odoo

1. Maak een test contact aan in Odoo
2. Controleer de logs in Odoo (Instellingen → Technisch → Logboeken)
3. Controleer of het contact in de eigen database staat

## Belangrijke Opmerkingen

1. **Geen Loops:** De webhook wordt alleen getriggerd bij handmatige wijzigingen in Odoo, niet bij automatische synchronisaties vanuit onze eigen DB.

2. **Secret Beveiliging:** 
   - De WEBHOOK_SECRET staat in `.env` (niet in GitHub)
   - Gebruik dezelfde secret in Odoo configuratie

3. **Error Handling:** 
   - Odoo logt fouten in het logboek
   - Ons endpoint retourneert duidelijke foutmeldingen

4. **Timeout:** 
   - Webhook heeft 10 seconden timeout
   - Bij timeout wordt de actie als gefaald gemarkeerd in Odoo

## Troubleshooting

### Webhook wordt niet aangeroepen

1. Controleer of automatisering actief is
2. Controleer Odoo logs voor fouten
3. Test endpoint met curl om connectiviteit te controleren
4. Controleer firewall/netwerk instellingen

### 401 Unauthorized

1. Controleer WEBHOOK_SECRET in `.env`
2. Controleer header naam: `X-Odoo-Webhook-Token` (case-sensitive)
3. Controleer of secret exact overeenkomt

### 500 Internal Server Error

1. Controleer DATABASE_URL in `.env`
2. Controleer database connectie
3. Controleer Odoo logs voor details

## URL Overzicht

- **Test Endpoint:** `https://fth-portaal-production.up.railway.app/webhooks/test`
- **Webhook Endpoint:** `https://fth-portaal-production.up.railway.app/webhooks/odoo/contact`
- **Method:** POST
- **Content-Type:** application/json
- **Authenticatie Header:** `X-Odoo-Webhook-Token: eGiEIi_sGOtZYzBCk5R0vSlsjFESE0MM85MRUFxLdS8`
