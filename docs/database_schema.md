# FTH Database Schema

## agents (0 records)
| kolom | type | nullable | default | FK |
|-------|------|----------|---------|----|
| id | uuid | nee | uuid_generate_v4() |  |
| created_at | timestamp with time zone | nee | CURRENT_TIMESTAMP |  |
| updated_at | timestamp with time zone | nee | CURRENT_TIMESTAMP |  |
| naam | character varying | nee |  |  |
| model | character varying | nee |  |  |
| prompt | text | nee |  |  |
| actief | boolean | nee | true |  |
| temperatuur | numeric | nee | 0.7 |  |
| beschrijving | text | nee |  |  |

## artikelen (14 records)
| kolom | type | nullable | default | FK |
|-------|------|----------|---------|----|
| id | uuid | nee | uuid_generate_v4() |  |
| naam | character varying | nee |  |  |
| prijs_incl | numeric | nee | 0.00 |  |
| odoo_id | integer | nee |  |  |
| actief | boolean | nee | true |  |
| aangemaakt_op | timestamp with time zone | nee | CURRENT_TIMESTAMP |  |
| btw_tarief_id | uuid | nee |  | -> btw_tarieven.id |

## betalingen (0 records)
| kolom | type | nullable | default | FK |
|-------|------|----------|---------|----|
| id | uuid | nee | gen_random_uuid() |  |
| mollie_id | character varying | nee |  |  |
| bedrag | numeric | nee | 0 |  |
| status | character varying | nee |  |  |
| type | character varying | nee |  |  |
| betaald_op | timestamp without time zone | nee |  |  |
| aangemaakt_op | timestamp without time zone | nee | now() |  |
| order_id | uuid | nee |  | -> orders.id |
| factuur_id | uuid | nee |  | -> facturen.id |

## btw_tarieven (3 records)
| kolom | type | nullable | default | FK |
|-------|------|----------|---------|----|
| id | uuid | nee | uuid_generate_v4() |  |
| naam | character varying | nee |  |  |
| percentage | numeric | nee |  |  |
| actief | boolean | nee | true |  |
| created_at | timestamp with time zone | nee | CURRENT_TIMESTAMP |  |

## contacten (1020 records)
| kolom | type | nullable | default | FK |
|-------|------|----------|---------|----|
| id | uuid | nee | uuid_generate_v4() |  |
| created_at | timestamp with time zone | nee | CURRENT_TIMESTAMP |  |
| updated_at | timestamp with time zone | nee | CURRENT_TIMESTAMP |  |
| naam | character varying | nee |  |  |
| email | character varying | nee |  |  |
| telefoon | character varying | nee |  |  |
| straat | character varying | nee |  |  |
| postcode | character varying | nee |  |  |
| stad | character varying | nee |  |  |
| land_code | character varying | nee | 'NL'::character varying |  |
| btw_nummer | character varying | nee |  |  |
| kvk_nummer | character varying | nee |  |  |
| bedrijfstype | character varying | nee | 'company'::character varying |  |
| is_portaal_partner | boolean | nee | false |  |
| partner_commissie | numeric | nee | 0.00 |  |
| heeft_eigen_truck | boolean | nee | false |  |
| wordpress_id | integer | nee |  |  |
| peppol_endpoint | character varying | nee |  |  |
| peppol_eas | character varying | nee |  |  |
| peppol_verificatie_status | character varying | nee | 'not_verified'::character varying |  |
| iban | character varying | nee |  |  |
| bank_tenaamstelling | character varying | nee |  |  |
| actief | boolean | nee | true |  |
| odoo_id | integer | nee |  |  |
| adres | text | nee |  |  |
| land | character varying | nee |  |  |

## facturen (2 records)
| kolom | type | nullable | default | FK |
|-------|------|----------|---------|----|
| id | uuid | nee | uuid_generate_v4() |  |
| order_id | uuid | nee |  | -> orders.id |
| factuurnummer | character varying | nee |  |  |
| factuurdatum | date | nee |  |  |
| pdf_url | text | nee |  |  |
| created_at | timestamp with time zone | nee | CURRENT_TIMESTAMP |  |
| mollie_payment_id | character varying | nee |  |  |
| mollie_checkout_url | text | nee |  |  |

## mail_logs (33454 records)
| kolom | type | nullable | default | FK |
|-------|------|----------|---------|----|
| id | uuid | nee | uuid_generate_v4() |  |
| created_at | timestamp with time zone | nee | CURRENT_TIMESTAMP |  |
| updated_at | timestamp with time zone | nee | CURRENT_TIMESTAMP |  |
| onderwerp | character varying | nee |  |  |
| inhoud | text | nee |  |  |
| email_van | character varying | nee |  |  |
| message_id | character varying | nee |  |  |
| ontvanger_id | uuid | nee |  | -> contacten.id |
| gerelateerd_model | character varying | nee |  |  |
| gerelateerd_id | integer | nee |  |  |
| bericht_type | character varying | nee |  |  |
| heeft_fout | boolean | nee | false |  |
| heeft_sms_fout | boolean | nee | false |  |
| preview | text | nee |  |  |
| odoo_id | integer | nee |  |  |
| richting | character varying | nee |  |  |
| kanaal | character varying | nee |  |  |
| naar | character varying | nee |  |  |
| order_id | uuid | nee |  | -> orders.id |
| template_naam | character varying | nee |  |  |
| status | character varying | nee |  |  |
| verzonden_op | timestamp with time zone | nee |  |  |
| foutmelding | text | nee |  |  |
| gearchiveerd | boolean | nee | false |  |

## order_artikelen (70 records)
| kolom | type | nullable | default | FK |
|-------|------|----------|---------|----|
| id | uuid | nee | uuid_generate_v4() |  |
| created_at | timestamp with time zone | nee | CURRENT_TIMESTAMP |  |
| order_id | uuid | nee |  | -> orders.id |
| artikel_id | uuid | nee |  | -> artikelen.id |
| naam | character varying | nee |  |  |
| aantal | numeric | nee | 1.00 |  |
| prijs_incl | numeric | nee | 0.00 |  |
| odoo_id | integer | nee |  |  |

## orders (25 records)
| kolom | type | nullable | default | FK |
|-------|------|----------|---------|----|
| id | uuid | nee | uuid_generate_v4() |  |
| created_at | timestamp with time zone | nee | CURRENT_TIMESTAMP |  |
| updated_at | timestamp with time zone | nee | CURRENT_TIMESTAMP |  |
| ordernummer | character varying | nee |  |  |
| order_datum | timestamp with time zone | nee |  |  |
| leverdatum | timestamp with time zone | nee |  |  |
| vervaldatum | date | nee |  |  |
| status | character varying | nee |  |  |
| portaal_status | character varying | nee | 'nieuw'::character varying |  |
| type_naam | character varying | nee |  |  |
| klant_id | uuid | nee |  | -> contacten.id |
| contractor_id | uuid | nee |  | -> contacten.id |
| totaal_bedrag | numeric | nee | 0.00 |  |
| bedrag_excl_btw | numeric | nee | 0.00 |  |
| bedrag_btw | numeric | nee | 0.00 |  |
| inkoop_partner_incl_btw | numeric | nee | 0.00 |  |
| plaats | character varying | nee |  |  |
| aantal_personen | integer | nee | 0 |  |
| aantal_kinderen | integer | nee | 0 |  |
| ordertype | character varying | nee |  |  |
| betaaltermijn_id | integer | nee |  |  |
| betaaltermijn_naam | character varying | nee |  |  |
| opmerkingen | text | nee |  |  |
| odoo_id | integer | nee |  |  |
| utm_source | character varying | nee |  |  |
| utm_medium | character varying | nee |  |  |
| utm_campaign | character varying | nee |  |  |
| utm_content | character varying | nee |  |  |
| halal | boolean | nee | false |  |
| flexible_time | character varying | nee |  |  |
| gclid | character varying | nee |  |  |
| bevestig_token | character varying | nee |  |  |
| gf_referentie | character varying | nee |  |  |
| betaal_status | character varying | nee | 'onbetaald'::character varying |  |
| notitie_klant | text | nee |  |  |
| notitie_partner | text | nee |  |  |
| prijs_partner | numeric | nee |  |  |
| planning_afgemeld | boolean | nee | false |  |
| planning_afmeld_token | uuid | nee |  |  |

## Redundantie signalen
| kolom | gevonden in |
|-------|------------|
| aangemaakt_op | artikelen,betalingen |
| actief | agents,artikelen,btw_tarieven,contacten |
| created_at | agents,btw_tarieven,contacten,facturen,mail_logs,order_artikelen,orders |
| id | agents,artikelen,betalingen,btw_tarieven,contacten,facturen,mail_logs,order_artikelen,orders |
| naam | agents,artikelen,btw_tarieven,contacten,order_artikelen |
| odoo_id | artikelen,contacten,mail_logs,order_artikelen,orders |
| order_id | betalingen,facturen,mail_logs,order_artikelen |
| prijs_incl | artikelen,order_artikelen |
| status | betalingen,mail_logs,orders |
| updated_at | agents,contacten,mail_logs,orders |