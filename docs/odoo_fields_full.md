# Odoo Field Export - Volledige Velden
*Gegenereerd op: 2026-03-10 12:15:37*

Dit document bevat alle velden met data uit voorbeeldrecords per model.

## Model: res.partner
**Record ID:** 421
| Veldnaam | Type | Label | Waarde |
|----------|------|------|--------|
| `active` | boolean | Active | True |
| `active_lang_count` | integer | Active Lang Count | 2 |
| `autopost_bills` | selection | Auto-post bills | ask |
| `available_invoice_template_pdf_report_ids` | one2many | Available Invoice Template Pdf Report | 217 |
| `available_peppol_eas` | json | Available Peppol Eas | 9952 |
| `available_peppol_edi_formats` | json | Available Peppol Edi Formats | facturx |
| `available_peppol_sending_methods` | json | Available Peppol Sending Methods | manual |
| `avatar_1024` | binary | Avatar 1024 | iVBORw0KGgoAAAANSUhEUgAAADcAAABNCAYAAAACYvzhAAAABmJLR0QA/wD/AP+gvaeTAAAJCklEQVR42u2ae0xb1x3Hs6lbq... |
| `avatar_128` | binary | Avatar 128 | iVBORw0KGgoAAAANSUhEUgAAADcAAABNCAYAAAACYvzhAAAABmJLR0QA/wD/AP+gvaeTAAAJCklEQVR42u2ae0xb1x3Hs6lbq... |
| `avatar_1920` | binary | Avatar | iVBORw0KGgoAAAANSUhEUgAAADcAAABNCAYAAAACYvzhAAAABmJLR0QA/wD/AP+gvaeTAAAJCklEQVR42u2ae0xb1x3Hs6lbq... |
| `avatar_256` | binary | Avatar 256 | iVBORw0KGgoAAAANSUhEUgAAADcAAABNCAYAAAACYvzhAAAABmJLR0QA/wD/AP+gvaeTAAAJCklEQVR42u2ae0xb1x3Hs6lbq... |
| `avatar_512` | binary | Avatar 512 | iVBORw0KGgoAAAANSUhEUgAAADcAAABNCAYAAAACYvzhAAAABmJLR0QA/wD/AP+gvaeTAAAJCklEQVR42u2ae0xb1x3Hs6lbq... |
| `bank_account_count` | integer | Bank | 0 |
| `calendar_last_notif_ack` | datetime | Last notification marked as read from base Calendar | 2025-05-13 18:29:43 |
| `child_ids` | one2many | Contact | 422 |
| `city` | char | City | Zeewolde |
| `color` | integer | Color Index | 0 |
| `commercial_company_name` | char | Company Name Entity | 123watches |
| `commercial_partner_id` | many2one | Commercial Entity | 123watches (ID: 421) |
| `company_registry_label` | char | Company ID Label | Bedrijfs ID |
| `company_type` | selection | Company Type | company |
| `complete_name` | char | Complete Name | 123watches |
| `contact_address` | char | Complete Address | 123watches
Sleedoorn 22

3892 CP Zeewolde
Netherlands |
| `contact_address_complete` | char | Contact Address Complete | Sleedoorn 22, 3892 CP Zeewolde, Netherlands |
| `contact_address_inline` | char | Inlined Complete Address | 123watches, Sleedoorn 22, 3892 CP Zeewolde, Netherlands |
| `country_code` | char | Country Code | NL |
| `country_id` | many2one | Country | Netherlands (ID: 165) |
| `create_date` | datetime | Created on | 2025-05-13 18:29:43 |
| `create_uid` | many2one | Created by | Robby Grob \| Friettruck-huren.nl (ID: 2) |
| `credit` | monetary | Total Receivable | 0.0 |
| `credit_limit` | float | Credit Limit | 0.0 |
| `credit_to_invoice` | monetary | Credit To Invoice | 0.0 |
| `currency_id` | many2one | Currency | EUR (ID: 125) |
| `customer_rank` | integer | Customer Rank | 4 |
| `days_sales_outstanding` | float | Days Sales Outstanding (DSO) | 0.0 |
| `debit` | monetary | Total Payable | 0.0 |
| `debit_limit` | monetary | Payable Limit | 0.0 |
| `display_invoice_edi_format` | boolean | Display Invoice Edi Format | True |
| `display_invoice_template_pdf_report_id` | boolean | Display Invoice Template Pdf Report | False |
| `display_name` | char | Display Name | 123watches |
| `document_count` | integer | Document Count | 0 |
| `duplicated_bank_account_partners_count` | integer | Duplicated Bank Account Partners Count | 0 |
| `email` | char | Email | daniel@123watches.nl |
| `email_formatted` | char | Formatted Email | "123watches" <daniel@123watches.nl> |
| `email_normalized` | char | Normalized Email | daniel@123watches.nl |
| `employee` | boolean | Employee | False |
| `fiscal_country_codes` | char | Fiscal Country Codes | NL |
| `followup_reminder_type` | selection | Reminders | automatic |
| `followup_status` | selection | Follow-up Status | no_action_needed |
| `has_call_in_queue` | boolean | Is in the Call Queue | False |
| `has_message` | boolean | Has Message | True |
| `has_moves` | boolean | Has Moves | True |
| `id` | integer | ID | 421 |
| `ignore_abnormal_invoice_amount` | boolean | Ignore Abnormal Invoice Amount | False |
| `ignore_abnormal_invoice_date` | boolean | Ignore Abnormal Invoice Date | False |
| `im_status` | char | IM Status | im_partner |
| `image_medium` | binary | Medium-sized image | iVBORw0KGgoAAAANSUhEUgAAADcAAABNCAYAAAACYvzhAAAABmJLR0QA/wD/AP+gvaeTAAAJCklEQVR42u2ae0xb1x3Hs6lbq... |
| `invoice_ids` | one2many | Invoices | 1307 (ID: 1478) |
| `invoice_warn` | selection | Invoice | no-message |
| `is_blacklisted` | boolean | Blacklist | False |
| `is_coa_installed` | boolean | Is Coa Installed | True |
| `is_company` | boolean | Is a Company | True |
| `is_peppol_edi_format` | boolean | Is Peppol Edi Format | False |
| `is_public` | boolean | Is Public | False |
| `is_ubl_format` | boolean | Is Ubl Format | False |
| `journal_item_count` | integer | Journal Items | 10 |
| `lang` | selection | Language | nl_NL |
| `meeting_count` | integer | # Meetings | 0 |
| `message_attachment_count` | integer | Attachment Count | 0 |
| `message_bounce` | integer | Bounce | 0 |
| `message_follower_ids` | one2many | Followers | 2079 |
| `message_has_error` | boolean | Message Delivery error | False |
| `message_has_error_counter` | integer | Number of errors | 0 |
| `message_has_sms_error` | boolean | SMS Delivery error | False |
| `message_ids` | one2many | Messages | 9423 |
| `message_is_follower` | boolean | Is Follower | True |
| `message_needaction` | boolean | Action Needed | False |
| `message_needaction_counter` | integer | Number of Actions | 0 |
| `message_partner_ids` | many2many | Followers (Partners) | 3 |
| `name` | char | Name | 123watches |
| `on_time_rate` | float | On-Time Delivery Rate | -1.0 |
| `opportunity_count` | integer | Opportunity Count | 0 |
| `partner_gid` | integer | Company database ID | 0 |
| `partner_latitude` | float | Geo Latitude | 0.0 |
| `partner_longitude` | float | Geo Longitude | 0.0 |
| `partner_share` | boolean | Share Partner | True |
| `partner_vat_placeholder` | char | Partner Vat Placeholder | NL123456782B90, of / indien niet van toepassing |
| `payment_token_count` | integer | Payment Token Count | 0 |
| `peppol_eas` | selection | Peppol e-address (EAS) | 0106 |
| `peppol_verification_state` | selection | Peppol status | not_verified |
| `perform_vies_validation` | boolean | Perform Vies Validation | False |
| `phone` | char | Phone | 0657157268 |
| `phone_blacklisted` | boolean | Blacklisted Phone is Phone | False |
| `phone_sanitized` | char | Sanitized Number | +31657157268 |
| `phone_sanitized_blacklisted` | boolean | Phone Blacklisted | False |
| `picking_warn` | selection | Stock Picking | no-message |
| `property_account_payable_id` | many2one | Account Payable | 130000 Creditors (ID: 133) |
| `property_account_receivable_id` | many2one | Account Receivable | 110000 Debtors (ID: 123) |
| `property_stock_customer` | many2one | Customer Location | Partners/Customers (ID: 5) |
| `property_stock_supplier` | many2one | Vendor Location | Partners/Vendors (ID: 4) |
| `purchase_order_count` | integer | Purchase Order Count | 0 |
| `purchase_warn` | selection | Purchase Order Warning | no-message |
| `receipt_reminder_email` | boolean | Receipt Reminder | False |
| `reminder_date_before_receipt` | integer | Days Before Receipt | 1 |
| `sale_order_count` | integer | Sale Order Count | 0 |
| `sale_warn` | selection | Sales Warnings | no-message |
| `self` | many2one | Self | 123watches (ID: 421) |
| `show_credit_limit` | boolean | Show Credit Limit | False |
| `signature_count` | integer | # Signatures | 0 |
| `signup_type` | char | Signup Token Type | signup |
| `street` | char | Street | Sleedoorn 22 |
| `supplier_invoice_count` | integer | # Vendor Bills | 0 |
| `supplier_rank` | integer | Supplier Rank | 0 |
| `task_count` | integer | # Tasks | 0 |
| `total_all_due` | monetary | Total All Due | 0.0 |
| `total_all_overdue` | monetary | Total All Overdue | 0.0 |
| `total_due` | monetary | Total Due | 0.0 |
| `total_invoiced` | monetary | Total Invoiced | 0.0 |
| `total_overdue` | monetary | Total Overdue | 0.0 |
| `trust` | selection | Degree of trust you have in this debtor | normal |
| `type` | selection | Address Type | contact |
| `tz_offset` | char | Timezone offset | +0000 |
| `unpaid_invoices_count` | integer | Unpaid Invoices Count | 0 |
| `use_partner_credit_limit` | boolean | Partner Limit | False |
| `vat_label` | char | Tax ID Label | VAT |
| `vies_valid` | boolean | Intra-Community Valid | False |
| `wa_channel_count` | integer | WhatsApp Channel Count | 0 |
| `write_date` | datetime | Last Updated on | 2025-07-03 14:42:41 |
| `write_uid` | many2one | Last Updated by | Robby Grob \| Friettruck-huren.nl (ID: 2) |
| `x_studio_akkoord_voorwaarden_selfbillingportaal` | boolean | Akkoord voorwaarden selfbilling/portaal | False |
| `x_studio_partner_commission` | float | Partnercommissie | 0.0 |
| `x_studio_portaal_partner` | boolean | Portaal partner | False |
| `x_studio_self_owned` | boolean | Eigen truck | False |
| `x_studio_wordpress_id` | integer | Wordpress ID | 0 |
| `zip` | char | Zip | 3892 CP |

## Model: sale.order
**Record ID:** 867
| Veldnaam | Type | Label | Waarde |
|----------|------|------|--------|
| `access_token` | char | Security Token | e7da3dd4-110d-4bfb-9dfe-4a6785989f45 |
| `access_url` | char | Portal Access URL | /my/orders/867 |
| `amount_invoiced` | monetary | Already invoiced | 0.0 |
| `amount_paid` | float | Payment Transactions Amount | 0.0 |
| `amount_tax` | monetary | Taxes | 2672.73 |
| `amount_to_invoice` | monetary | Un-invoiced Balance | 15400.0 |
| `amount_total` | monetary | Total | 15400.0 |
| `amount_undiscounted` | float | Amount Before Discount | 12727.27 |
| `amount_untaxed` | monetary | Untaxed Amount | 12727.27 |
| `closed_task_count` | integer | Closed Task Count | 0 |
| `commitment_date` | datetime | Delivery Date | 2026-03-12 21:00:00 |
| `company_id` | many2one | Company | Treatlab VOF (ID: 1) |
| `company_price_include` | selection | Default Sales Price Include | tax_excluded |
| `completed_task_percentage` | float | Completed Task Percentage | 0.0 |
| `country_code` | char | Country code | NL |
| `create_date` | datetime | Creation Date | 2026-03-09 21:10:33 |
| `create_uid` | many2one | Created by | Robby Grob \| Friettruck-huren.nl (ID: 2) |
| `currency_id` | many2one | Currency | EUR (ID: 125) |
| `currency_rate` | float | Currency Rate | 1.0 |
| `date_order` | datetime | Order Date | 2026-03-09 22:13:39 |
| `delivery_count` | integer | Delivery Orders | 1 |
| `delivery_status` | selection | Delivery Status | pending |
| `display_name` | char | Display Name | S00870 |
| `dropship_picking_count` | integer | Dropship Count | 0 |
| `expected_date` | datetime | Expected Date | 2026-03-09 22:13:39 |
| `fiscal_position_id` | many2one | Fiscal Position | EU private B2C (ID: 3) |
| `has_active_pricelist` | boolean | Has Active Pricelist | False |
| `has_archived_products` | boolean | Has Archived Products | False |
| `has_message` | boolean | Has Message | True |
| `id` | integer | ID | 867 |
| `invoice_count` | integer | Invoice Count | 0 |
| `invoice_status` | selection | Invoice Status | to invoice |
| `is_expired` | boolean | Is Expired | False |
| `is_pdf_quote_builder_available` | boolean | Is Pdf Quote Builder Available | False |
| `is_product_milestone` | boolean | Is Product Milestone | False |
| `json_popover` | char | JSON data for the popover widget | {"popoverTemplate": "sale_stock.DelayAlertWidget", "late_elements": []} |
| `locked` | boolean | Locked | False |
| `message_attachment_count` | integer | Attachment Count | 0 |
| `message_follower_ids` | one2many | Followers | 7006 (ID: 7004) |
| `message_has_error` | boolean | Message Delivery error | False |
| `message_has_error_counter` | integer | Number of errors | 0 |
| `message_has_sms_error` | boolean | SMS Delivery error | False |
| `message_ids` | one2many | Messages | 41040 |
| `message_is_follower` | boolean | Is Follower | True |
| `message_needaction` | boolean | Action Needed | False |
| `message_needaction_counter` | integer | Number of Actions | 0 |
| `message_partner_ids` | many2many | Followers (Partners) | 58 (ID: 3) |
| `milestone_count` | integer | Milestone Count | 0 |
| `name` | char | Order Reference | S00870 |
| `order_line` | one2many | Order Lines | 2631 |
| `partner_id` | many2one | Customer | Roy Test (ID: 58) |
| `partner_invoice_id` | many2one | Invoice Address | Roy Test (ID: 58) |
| `partner_shipping_id` | many2one | Delivery Address | Roy Test (ID: 58) |
| `payment_term_id` | many2one | Payment Terms | 30 Days (ID: 4) |
| `picking_ids` | one2many | Transfers | 348 |
| `picking_policy` | selection | Shipping Policy | direct |
| `prepayment_percent` | float | Prepayment percentage | 1.0 |
| `procurement_group_id` | many2one | Procurement Group | S00870 (ID: 254) |
| `project_count` | integer | Number of Projects | 0 |
| `purchase_order_count` | integer | Number of Purchase Order Generated | 0 |
| `require_payment` | boolean | Online payment | False |
| `require_signature` | boolean | Online signature | True |
| `show_create_project_button` | boolean | Show Create Project Button | False |
| `show_json_popover` | boolean | Has late picking | False |
| `show_project_button` | boolean | Show Project Button | False |
| `show_task_button` | boolean | Show Task Button | False |
| `show_update_fpos` | boolean | Has Fiscal Position Changed | False |
| `show_update_pricelist` | boolean | Has Pricelist Changed | False |
| `state` | selection | Status | sale |
| `tasks_count` | integer | Tasks | 0 |
| `tax_calculation_rounding_method` | selection | Tax Calculation Rounding Method | round_per_line |
| `tax_country_id` | many2one | Tax Country | Netherlands (ID: 165) |
| `tax_totals` | binary | Tax Totals | {'currency_id': 125, 'currency_pd': 0.01, 'company_currency_id': 125, 'company_currency_pd': 0.01... |
| `team_id` | many2one | Sales Team | Sales (ID: 1) |
| `terms_type` | selection | Terms & Conditions format | plain |
| `type_name` | char | Type Name | Verkooporder |
| `user_id` | many2one | Salesperson | Robby Grob \| Friettruck-huren.nl (ID: 2) |
| `validity_date` | date | Expiration | 2026-04-08 |
| `visible_project` | boolean | Display project | False |
| `warehouse_id` | many2one | Warehouse | Treatlab VOF (ID: 1) |
| `website_message_ids` | one2many | Website Messages | 41035 |
| `write_date` | datetime | Last Updated on | 2026-03-09 22:14:10 |
| `write_uid` | many2one | Last Updated by | Robby Grob \| Friettruck-huren.nl (ID: 2) |
| `x_feedback_whatsapp_sent` | boolean | Feedback WhatsApp verzonden | False |
| `x_studio_aantal_kinderen` | integer | Aantal kinderen | 0 |
| `x_studio_aantal_personen` | integer | Aantal personen | 0 |
| `x_studio_aantal_personen_origineel` | integer | Aantal personen (origineel) | 0 |
| `x_studio_contractor` | many2one | Partner | robby r\trea (ID: 60) |
| `x_studio_feedback_whatsapp_verzonden` | boolean | Feedback WhatsApp verzonden | False |
| `x_studio_halal` | boolean | Halal | False |
| `x_studio_halal_1` | boolean | Halal | False |
| `x_studio_inkoop_partner_incl_btw` | monetary | Inkoop partner incl btw | 202.0 |
| `x_studio_inkoop_partner_incl_btw_1` | monetary | Inkoop partner incl btw | 0.0 |
| `x_studio_monetary_field_9dm_1jja3lqqe` | monetary | Nieuw Monetair | 0.0 |
| `x_studio_ordertype` | selection | Ordertype | b2c |
| `x_studio_partner_wordpress_id` | integer | Partner Wordpress ID | 0 |
| `x_studio_plaats` | char | Plaats | Heerhugowaard |
| `x_studio_portaal_partner` | boolean | Portaal partner | False |
| `x_studio_related_field_3ta_1j0m2d3ci` | char | Telefoon | 0612345678 |
| `x_studio_related_field_7uk_1iodv4trp` | many2one | Nieuw Relatieveld | Roy Test (ID: 58) |
| `x_studio_selection_field_67u_1jj77rtf7` | selection | Portaal status | transfer |
| `x_studio_x_studio_social_media_ok` | boolean | Toetemming social media | False |

## Model: account.move
**Record ID:** 2353
| Veldnaam | Type | Label | Waarde |
|----------|------|------|--------|
| `access_url` | char | Portal Access URL | # |
| `adjusting_entries_count` | integer | Adjusting Entries Count | 0 |
| `adjusting_entry_origin_moves_count` | integer | Adjusting Entry Origin Moves Count | 0 |
| `always_tax_exigible` | boolean | Always Tax Exigible | True |
| `amount_paid` | monetary | Amount paid | 0.0 |
| `amount_residual` | monetary | Amount Due | 0.0 |
| `amount_residual_signed` | monetary | Amount Due Signed | 0.0 |
| `amount_tax` | monetary | Tax | 0.0 |
| `amount_tax_signed` | monetary | Tax Signed | 0.0 |
| `amount_total` | monetary | Total | 185.28 |
| `amount_total_in_currency_signed` | monetary | Total in Currency Signed | 185.28 |
| `amount_total_signed` | monetary | Total Signed | 185.28 |
| `amount_total_words` | char | Amount total in words | Honderdvijfentachtig Euros en Achtentwintig Cents |
| `amount_untaxed` | monetary | Untaxed Amount | 0.0 |
| `amount_untaxed_in_currency_signed` | monetary | Untaxed Amount Signed Currency | 0.0 |
| `amount_untaxed_signed` | monetary | Untaxed Amount Signed | 0.0 |
| `asset_depreciated_value` | monetary | Cumulative Depreciation | 11500.0 |
| `asset_depreciation_beginning_date` | date | Date of the beginning of the depreciation | 2030-09-01 |
| `asset_id` | many2one | Asset | Friettruck 2 (ID: 8) |
| `asset_id_display_name` | char | Asset Id Display Name | Activum |
| `asset_move_type` | selection | Asset Move Type | depreciation |
| `asset_number_days` | integer | Number of days | 30 |
| `asset_remaining_value` | monetary | Depreciable Value | 0.0 |
| `asset_value_change` | boolean | Asset Value Change | False |
| `audit_trail_message_ids` | one2many | Audit Trail Messages | 29652 |
| `auto_post` | selection | Auto-post | at_date |
| `bank_partner_id` | many2one | Bank Partner | Shoebus (ID: 1050) |
| `checked` | boolean | Checked | True |
| `commercial_partner_id` | many2one | Commercial Entity | Shoebus (ID: 1050) |
| `company_currency_id` | many2one | Company Currency | EUR (ID: 125) |
| `company_id` | many2one | Company | Treatlab VOF (ID: 1) |
| `company_price_include` | selection | Default Sales Price Include | tax_excluded |
| `count_asset` | integer | Count Asset | 0 |
| `country_code` | char | Country Code | NL |
| `create_date` | datetime | Created on | 2025-10-23 09:23:23 |
| `create_uid` | many2one | Created by | Robby Grob \| Friettruck-huren.nl (ID: 2) |
| `currency_id` | many2one | Currency | EUR (ID: 125) |
| `date` | date | Date | 2030-09-30 |
| `depreciation_value` | monetary | Depreciation | 185.28 |
| `direction_sign` | integer | Direction Sign | 1 |
| `display_inactive_currency_warning` | boolean | Display Inactive Currency Warning | False |
| `display_name` | char | Display Name | Conceptboeking (Aanschafwaarde friettruck 2: Afschrijving) |
| `display_qr_code` | boolean | Display QR-code | False |
| `draft_asset_exists` | boolean | Draft Asset Exists | False |
| `expected_currency_rate` | float | Expected Currency Rate | 1.0 |
| `extract_can_show_banners` | boolean | Can show the ocr banners | False |
| `extract_can_show_send_button` | boolean | Can show the ocr send button | False |
| `extract_detected_layout` | integer | Extract Detected Layout Id | 0 |
| `extract_error_message` | text | Error message | An error occurred |
| `extract_state` | selection | Extract state | no_extract_requested |
| `extract_state_processed` | boolean | Extract State Processed | False |
| `fiscal_position_id` | many2one | Fiscal Position | EU private B2C (ID: 3) |
| `has_documents` | boolean | Has Documents | False |
| `has_message` | boolean | Has Message | True |
| `has_reconciled_entries` | boolean | Has Reconciled Entries | False |
| `hide_post_button` | boolean | Hide Post Button | True |
| `id` | integer | ID | 2353 |
| `impacting_cash_basis` | boolean | Impacting Cash Basis | False |
| `invoice_currency_rate` | float | Currency Rate | 0.0 |
| `invoice_date_due` | date | Due Date | 2025-10-23 |
| `invoice_has_outstanding` | boolean | Invoice Has Outstanding | False |
| `invoice_line_ids` | one2many | Invoice lines | 9393 (ID: 9392) |
| `invoice_partner_display_name` | char | Invoice Partner Display Name | Shoebus |
| `is_being_sent` | boolean | Is Being Sent | False |
| `is_in_extractable_state` | boolean | Is In Extractable State | False |
| `is_loan_payment_move` | boolean | Is Loan Payment Move | False |
| `is_manually_modified` | boolean | Is Manually Modified | False |
| `is_move_sent` | boolean | Is Move Sent | False |
| `is_purchase_matched` | boolean | Is Purchase Matched | False |
| `is_storno` | boolean | Is Storno | False |
| `journal_id` | many2one | Journal | Miscellaneous Operations (ID: 10) |
| `line_ids` | one2many | Journal Items | 9393 (ID: 9392) |
| `made_sequence_gap` | boolean | Made Sequence Gap | False |
| `message_attachment_count` | integer | Attachment Count | 0 |
| `message_follower_ids` | one2many | Followers | 5366 |
| `message_has_error` | boolean | Message Delivery error | False |
| `message_has_error_counter` | integer | Number of errors | 0 |
| `message_has_sms_error` | boolean | SMS Delivery error | False |
| `message_ids` | one2many | Messages | 29652 |
| `message_is_follower` | boolean | Is Follower | True |
| `message_needaction` | boolean | Action Needed | False |
| `message_needaction_counter` | integer | Number of Actions | 0 |
| `message_partner_ids` | many2many | Followers (Partners) | 3 |
| `move_sent_values` | selection | Sent | not_sent |
| `move_type` | selection | Type | entry |
| `name_placeholder` | char | Name Placeholder | MISC/2030/09/0001 |
| `need_cancel_request` | boolean | Need Cancel Request | False |
| `needed_terms` | binary | Needed Terms | {} |
| `needed_terms_dirty` | boolean | Needed Terms Dirty | True |
| `partner_id` | many2one | Partner | Shoebus (ID: 1050) |
| `payment_count` | integer | Payment Count | 0 |
| `payment_state` | selection | Payment Status | not_paid |
| `posted_before` | boolean | Posted Before | False |
| `purchase_order_count` | integer | Purchase Order Count | 0 |
| `quick_edit_mode` | boolean | Quick Edit Mode | False |
| `quick_edit_total_amount` | monetary | Total (Tax inc.) | 0.0 |
| `ref` | char | Reference | Aanschafwaarde friettruck 2: Afschrijving |
| `restrict_mode_hash_table` | boolean | Secure Posted Entries with Hash | False |
| `sale_order_count` | integer | Sale Order Count | 0 |
| `secure_sequence_number` | integer | Inalterability No Gap Sequence # | 0 |
| `secured` | boolean | Secured | False |
| `sequence_number` | integer | Sequence Number | 0 |
| `show_delivery_date` | boolean | Show Delivery Date | False |
| `show_discount_details` | boolean | Show Discount Details | False |
| `show_name_warning` | boolean | Show Name Warning | False |
| `show_payment_term_details` | boolean | Show Payment Term Details | False |
| `show_reset_to_draft_button` | boolean | Show Reset To Draft Button | False |
| `show_signature_area` | boolean | Show Signature Area | False |
| `show_update_fpos` | boolean | Has Fiscal Position Changed | False |
| `state` | selection | Status | draft |
| `status_in_payment` | selection | Status In Payment | not_paid |
| `suitable_journal_ids` | many2many | Suitable Journal | 10 |
| `tax_calculation_rounding_method` | selection | Tax calculation rounding method | round_per_line |
| `tax_closing_alert` | boolean | Tax Closing Alert | False |
| `tax_country_code` | char | Tax Country Code | NL |
| `tax_country_id` | many2one | Tax Country | Netherlands (ID: 165) |
| `transaction_count` | integer | Transaction Count | 0 |
| `type_name` | char | Type Name | Journal Entry |
| `write_date` | datetime | Last Updated on | 2025-10-23 09:23:23 |
| `write_uid` | many2one | Last Updated by | Robby Grob \| Friettruck-huren.nl (ID: 2) |

## Model: mail.message
**Record ID:** 41043
| Veldnaam | Type | Label | Waarde |
|----------|------|------|--------|
| `account_audit_log_activated` | boolean | Audit Log Activated | False |
| `account_audit_log_partner_id` | many2one | Partner | De Aardappeltuin (ID: 87) |
| `author_avatar` | binary | Author's avatar | PD94bWwgdmVyc2lvbj0nMS4wJyBlbmNvZGluZz0nVVRGLTgnID8+PHN2ZyBoZWlnaHQ9JzE4MCcgd2lkdGg9JzE4MCcgeG1sb... |
| `author_id` | many2one | Author | Robby Grob \| Friettruck-huren.nl (ID: 3) |
| `body` | html | Contents | <p>Beste partner,</p>
<p>Er is een nieuwe opdracht ingepland, of een geplande opdracht gewijzigd.... |
| `create_date` | datetime | Created on | 2026-03-10 05:30:20 |
| `create_uid` | many2one | Created by | Robby Grob \| Friettruck-huren.nl (ID: 2) |
| `date` | datetime | Date | 2026-03-10 05:30:20 |
| `display_name` | char | Display Name | De Aardappeltuin |
| `email_add_signature` | boolean | Email Add Signature | True |
| `email_from` | char | From | "Robby Grob \| Friettruck-huren.nl" <robbygrob@gmail.com> |
| `has_error` | boolean | Has error | False |
| `has_sms_error` | boolean | Has SMS error | False |
| `id` | integer | ID | 41043 |
| `is_current_user_or_guest_author` | boolean | Is Current User Or Guest Author | True |
| `is_internal` | boolean | Employee Only | False |
| `mail_ids` | one2many | Mails | 5127 |
| `message_id` | char | Message-Id | <475957540064758.1773120620.692167520523071-openerp-87-res.partner@eu519a.odoo.com> |
| `message_type` | selection | Type | email_outgoing |
| `model` | char | Related Document Model | res.partner |
| `needaction` | boolean | Need Action | False |
| `partner_ids` | many2many | Recipients | 87 |
| `preview` | char | Preview | Beste partner, Er is een nieuwe opdracht ingepland, of een geplande opdracht gewijzigd. In het ov... |
| `rating_value` | float | Rating Value | 0.0 |
| `record_name` | char | Message Record Name | De Aardappeltuin |
| `reply_to_force_new` | boolean | No threading for answers | False |
| `res_id` | many2one_reference | Related Document ID | 87 |
| `snailmail_error` | boolean | Snailmail message in error | False |
| `starred` | boolean | Starred | False |
| `subject` | char | Subject | Update op de planning - Friettruck-huren.nl |
| `write_date` | datetime | Last Updated on | 2026-03-10 06:27:07 |
| `write_uid` | many2one | Last Updated by | OdooBot (ID: 1) |
