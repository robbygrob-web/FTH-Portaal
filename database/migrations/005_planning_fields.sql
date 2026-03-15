-- Migratie 005: Planning email systeem velden
-- Datum: 2026-03-10
-- 
-- Voegt toe aan orders tabel:
-- - planning_afgemeld: BOOLEAN DEFAULT FALSE
-- - planning_afmeld_token: UUID (nullable)
--
-- Voegt toe aan facturen tabel:
-- - mollie_payment_id: VARCHAR(100)
-- - mollie_checkout_url: TEXT

-- Planning email systeem velden
ALTER TABLE orders ADD COLUMN IF NOT EXISTS planning_afgemeld BOOLEAN DEFAULT FALSE;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS planning_afmeld_token UUID;

-- Mollie betaallink velden
ALTER TABLE facturen ADD COLUMN IF NOT EXISTS mollie_payment_id VARCHAR(100);
ALTER TABLE facturen ADD COLUMN IF NOT EXISTS mollie_checkout_url TEXT;
