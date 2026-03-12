-- Orders: notitievelden
ALTER TABLE orders ADD COLUMN IF NOT EXISTS notitie_klant TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS notitie_partner TEXT;

-- Contacten: adresvelden
ALTER TABLE contacten ADD COLUMN IF NOT EXISTS adres TEXT;
ALTER TABLE contacten ADD COLUMN IF NOT EXISTS postcode VARCHAR(20);
ALTER TABLE contacten ADD COLUMN IF NOT EXISTS land VARCHAR(100);
