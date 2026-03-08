# Odoo Field Reference

## Model: sale.order

Fields used by the portal:

- id → internal Odoo record ID (used for API updates)
- name → visible order number in Odoo UI
- state → determines if record is an offerte or verkooporder
- type_name → readable label (Offerte / Verkooporder)
- partner_id → customer
- commitment_date → event / delivery date
- x_studio_contractor → assigned partner / supplier
- x_studio_plaats → location
- x_studio_aantal_personen → number of persons

## Logic used in the portal

state = sent  → offerte  
state = sale  → verkooporder

## Notes

- `id` is used for technical API operations
- `name` is only used for display
- business logic must always rely on `state`
