-- Migratie 006: Annuleer token veld
-- Datum: 2026-03-XX
-- 
-- Voegt toe aan orders tabel:
-- - annuleer_token: UUID (nullable)

-- Annuleer token veld
ALTER TABLE orders ADD COLUMN IF NOT EXISTS annuleer_token UUID;
