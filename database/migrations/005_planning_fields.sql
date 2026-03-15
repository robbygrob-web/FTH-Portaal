-- Migratie 005: Planning email systeem velden
-- Datum: 2026-03-10
-- 
-- Voegt toe aan orders tabel:
-- - planning_afgemeld: BOOLEAN DEFAULT FALSE
-- - planning_afmeld_token: UUID (nullable)

-- Planning email systeem velden
ALTER TABLE orders ADD COLUMN IF NOT EXISTS planning_afgemeld BOOLEAN DEFAULT FALSE;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS planning_afmeld_token UUID;
