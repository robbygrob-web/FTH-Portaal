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
- x_studio_selection_field_67u_1jj77rtf7 → platform status field

## Logic used in the portal

state = sent  → offerte  
state = sale  → verkooporder

## Platform Status Field

Field: `x_studio_selection_field_67u_1jj77rtf7`

Confirmed values:
- `nieuw` (default) - not yet visible in partner screen
- `beschikbaar` - available for claiming
- `claimed` - claimed by a partner
- `transfer` - transferred status

## Partner Screen Logic

Partner screen shows:
- Records with status `beschikbaar` AND `x_studio_contractor = 1361`
- Records with status `transfer` (regardless of contractor)

## Notes

- `id` is used for technical API operations
- `name` is only used for display
- business logic must always rely on `state`
- `x_studio_selection_field_67u_1jj77rtf7 = nieuw` means record is not visible in partner screen