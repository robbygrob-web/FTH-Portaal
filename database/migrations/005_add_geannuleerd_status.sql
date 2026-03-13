-- Migratie 005: Voeg 'geannuleerd' toe aan orders.status check constraint
-- Drop bestaande constraint
ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_status_check;

-- Maak nieuwe constraint aan met geannuleerd
ALTER TABLE orders ADD CONSTRAINT orders_status_check 
    CHECK (status IN ('draft', 'sent', 'sale', 'geannuleerd'));
