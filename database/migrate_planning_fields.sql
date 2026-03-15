-- Migratie: Planning email systeem velden toevoegen aan orders tabel
-- Datum: 2026-03-10
-- 
-- Voegt toe:
-- - planning_afgemeld: BOOLEAN DEFAULT FALSE
-- - planning_afmeld_token: UUID (nullable)

-- Check of kolommen al bestaan voordat we ze toevoegen
DO $$
BEGIN
    -- Check planning_afgemeld
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'orders' AND column_name = 'planning_afgemeld'
    ) THEN
        ALTER TABLE orders 
        ADD COLUMN planning_afgemeld BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Kolom planning_afgemeld toegevoegd';
    ELSE
        RAISE NOTICE 'Kolom planning_afgemeld bestaat al';
    END IF;
    
    -- Check planning_afmeld_token
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'orders' AND column_name = 'planning_afmeld_token'
    ) THEN
        ALTER TABLE orders 
        ADD COLUMN planning_afmeld_token UUID;
        RAISE NOTICE 'Kolom planning_afmeld_token toegevoegd';
    ELSE
        RAISE NOTICE 'Kolom planning_afmeld_token bestaat al';
    END IF;
END $$;

-- Verifieer migratie
SELECT 
    column_name, 
    data_type, 
    column_default,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'orders' 
AND column_name IN ('planning_afgemeld', 'planning_afmeld_token')
ORDER BY column_name;
