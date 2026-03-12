-- FTH Portaal PostgreSQL Schema
-- Clean schema gebaseerd op Odoo velden analyse
-- Elke tabel heeft: id, created_at, updated_at

-- Extensies
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- CONTACTEN (res.partner)
-- ============================================================================
CREATE TABLE contacten (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Basis informatie
    naam VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    telefoon VARCHAR(50),
    
    -- Adres
    straat VARCHAR(255),
    postcode VARCHAR(20),
    stad VARCHAR(100),
    land_code VARCHAR(2) DEFAULT 'NL',
    
    -- Bedrijfsgegevens
    btw_nummer VARCHAR(50),
    kvk_nummer VARCHAR(20),
    bedrijfstype VARCHAR(20) DEFAULT 'company', -- company, person, contact
    
    -- Portaal specifiek
    is_portaal_partner BOOLEAN DEFAULT FALSE,
    partner_commissie DECIMAL(10, 2) DEFAULT 0.00,
    heeft_eigen_truck BOOLEAN DEFAULT FALSE,
    wordpress_id INTEGER,
    
    -- Peppol / EDI
    peppol_endpoint VARCHAR(255),
    peppol_eas VARCHAR(10),
    peppol_verificatie_status VARCHAR(50) DEFAULT 'not_verified',
    
    -- Bankgegevens
    iban VARCHAR(34),
    bank_tenaamstelling VARCHAR(255),
    
    -- Status
    actief BOOLEAN DEFAULT TRUE,
    
    -- Odoo sync (tijdelijk)
    odoo_id INTEGER UNIQUE,
    
    CONSTRAINT contacten_email_unique UNIQUE (email)
);

CREATE INDEX idx_contacten_email ON contacten(email);
CREATE INDEX idx_contacten_odoo_id ON contacten(odoo_id);
CREATE INDEX idx_contacten_portaal_partner ON contacten(is_portaal_partner) WHERE is_portaal_partner = TRUE;

-- ============================================================================
-- ORDERS (sale.order)
-- ============================================================================
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Order identificatie
    ordernummer VARCHAR(50) NOT NULL UNIQUE,
    
    -- Datums
    order_datum TIMESTAMP WITH TIME ZONE NOT NULL,
    leverdatum TIMESTAMP WITH TIME ZONE,
    vervaldatum DATE,
    
    -- Status
    status VARCHAR(20) NOT NULL, -- sent (offerte), sale (verkooporder)
    portaal_status VARCHAR(20) DEFAULT 'nieuw', -- nieuw, beschikbaar, claimed, transfer
    type_naam VARCHAR(50), -- Offerte / Verkooporder
    
    -- Relaties
    klant_id UUID REFERENCES contacten(id) ON DELETE SET NULL,
    contractor_id UUID REFERENCES contacten(id) ON DELETE SET NULL, -- Geclaimd door partner
    
    -- Bedragen
    totaal_bedrag DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    bedrag_excl_btw DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    bedrag_btw DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    inkoop_partner_incl_btw DECIMAL(10, 2) DEFAULT 0.00, -- Wat partner krijgt
    
    -- Order details
    plaats VARCHAR(255),
    aantal_personen INTEGER DEFAULT 0,
    aantal_kinderen INTEGER DEFAULT 0,
    ordertype VARCHAR(10), -- b2b, b2c
    
    -- Betaling
    betaaltermijn_id INTEGER, -- Referentie naar Odoo payment term
    betaaltermijn_naam VARCHAR(100),
    
    -- Extra
    opmerkingen TEXT,
    
    -- UTM Tracking (AFL UTM Tracker)
    utm_source VARCHAR(255),
    utm_medium VARCHAR(255),
    utm_campaign VARCHAR(255),
    utm_content VARCHAR(255),
    
    -- Odoo sync (tijdelijk)
    odoo_id INTEGER UNIQUE,
    
    CONSTRAINT orders_status_check CHECK (status IN ('sent', 'sale', 'draft', 'cancel')),
    CONSTRAINT orders_portaal_status_check CHECK (portaal_status IN ('nieuw', 'beschikbaar', 'claimed', 'transfer'))
);

CREATE INDEX idx_orders_klant_id ON orders(klant_id);
CREATE INDEX idx_orders_contractor_id ON orders(contractor_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_portaal_status ON orders(portaal_status);
CREATE INDEX idx_orders_leverdatum ON orders(leverdatum);
CREATE INDEX idx_orders_odoo_id ON orders(odoo_id);
CREATE INDEX idx_orders_beschikbaar ON orders(portaal_status, contractor_id) WHERE portaal_status IN ('beschikbaar', 'transfer');

-- ============================================================================
-- ARTIKELEN (product.product)
-- ============================================================================
CREATE TABLE artikelen (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    naam VARCHAR(255) NOT NULL,
    prijs_excl DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    btw_pct DECIMAL(5, 2) NOT NULL DEFAULT 9.00,
    btw_bedrag DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    prijs_incl DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    odoo_id INTEGER UNIQUE NOT NULL,
    actief BOOLEAN DEFAULT TRUE,
    aangemaakt_op TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_artikelen_odoo_id ON artikelen(odoo_id);
CREATE INDEX idx_artikelen_actief ON artikelen(actief);
CREATE INDEX idx_artikelen_naam ON artikelen(naam);

-- ============================================================================
-- ORDER_ARTIKELEN (sale.order.line)
-- ============================================================================
CREATE TABLE order_artikelen (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Relaties
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    artikel_id UUID REFERENCES artikelen(id) ON DELETE SET NULL,
    
    -- Orderline informatie
    naam VARCHAR(500) NOT NULL, -- Product naam/omschrijving
    aantal DECIMAL(10, 2) NOT NULL DEFAULT 1.00, -- product_uom_qty
    prijs_excl DECIMAL(10, 2) NOT NULL DEFAULT 0.00, -- price_unit
    btw_pct DECIMAL(5, 2) NOT NULL DEFAULT 9.00, -- tax percentage
    btw_bedrag DECIMAL(10, 2) NOT NULL DEFAULT 0.00, -- calculated tax
    prijs_incl DECIMAL(10, 2) NOT NULL DEFAULT 0.00, -- price_subtotal_incl
    
    -- Odoo sync (tijdelijk)
    odoo_id INTEGER UNIQUE, -- sale.order.line ID
    
    CONSTRAINT order_artikelen_order_id_fk FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT order_artikelen_artikel_id_fk FOREIGN KEY (artikel_id) REFERENCES artikelen(id) ON DELETE SET NULL
);

CREATE INDEX idx_order_artikelen_order_id ON order_artikelen(order_id);
CREATE INDEX idx_order_artikelen_artikel_id ON order_artikelen(artikel_id);
CREATE INDEX idx_order_artikelen_odoo_id ON order_artikelen(odoo_id);

-- ============================================================================
-- FACTUREN (account.move)
-- ============================================================================
CREATE TABLE facturen (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Factuur identificatie
    factuurnummer VARCHAR(50) NOT NULL UNIQUE,
    referentie VARCHAR(255),
    
    -- Datums
    factuurdatum DATE NOT NULL,
    vervaldatum DATE,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'draft', -- draft, posted, cancel
    betalingsstatus VARCHAR(20) DEFAULT 'not_paid', -- not_paid, partial, paid
    type_naam VARCHAR(50), -- Invoice, Credit Note, Journal Entry
    
    -- Relaties
    klant_id UUID REFERENCES contacten(id) ON DELETE SET NULL,
    order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    
    -- Bedragen
    totaal_bedrag DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    bedrag_excl_btw DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    bedrag_btw DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    openstaand_bedrag DECIMAL(10, 2) DEFAULT 0.00,
    
    -- Valuta
    valuta_code VARCHAR(3) DEFAULT 'EUR',
    wisselkoers DECIMAL(10, 6) DEFAULT 1.0,
    
    -- Odoo sync (tijdelijk)
    odoo_id INTEGER UNIQUE,
    
    CONSTRAINT facturen_status_check CHECK (status IN ('draft', 'posted', 'cancel')),
    CONSTRAINT facturen_betalingsstatus_check CHECK (betalingsstatus IN ('not_paid', 'partial', 'paid'))
);

CREATE INDEX idx_facturen_klant_id ON facturen(klant_id);
CREATE INDEX idx_facturen_order_id ON facturen(order_id);
CREATE INDEX idx_facturen_status ON facturen(status);
CREATE INDEX idx_facturen_betalingsstatus ON facturen(betalingsstatus);
CREATE INDEX idx_facturen_factuurdatum ON facturen(factuurdatum);
CREATE INDEX idx_facturen_odoo_id ON facturen(odoo_id);

-- ============================================================================
-- MAIL LOGS (mail.message)
-- ============================================================================
CREATE TABLE mail_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Bericht informatie
    onderwerp VARCHAR(500),
    inhoud TEXT,
    email_van VARCHAR(255),
    message_id VARCHAR(255) UNIQUE, -- Message-Id header
    
    -- Relaties
    ontvanger_id UUID REFERENCES contacten(id) ON DELETE SET NULL,
    gerelateerd_model VARCHAR(100), -- res.partner, sale.order, etc.
    gerelateerd_id INTEGER, -- ID van gerelateerd record
    order_id UUID REFERENCES orders(id) ON DELETE SET NULL, -- Gerelateerde order
    
    -- Richting en kanaal
    richting VARCHAR(20), -- inkomend of uitgaand
    kanaal VARCHAR(20), -- mail of whatsapp
    naar VARCHAR(255), -- ontvanger emailadres
    
    -- Status
    bericht_type VARCHAR(50), -- email_outgoing, email_incoming, notification
    status VARCHAR(20), -- verzonden, mislukt, ontvangen
    heeft_fout BOOLEAN DEFAULT FALSE,
    heeft_sms_fout BOOLEAN DEFAULT FALSE,
    
    -- Template en timing
    template_naam VARCHAR(100), -- welke template gebruikt
    verzonden_op TIMESTAMP WITH TIME ZONE, -- wanneer verzonden
    
    -- Metadata
    preview TEXT, -- Eerste regels van bericht
    
    -- Odoo sync (tijdelijk)
    odoo_id INTEGER UNIQUE
);

CREATE INDEX idx_mail_logs_ontvanger_id ON mail_logs(ontvanger_id);
CREATE INDEX idx_mail_logs_gerelateerd ON mail_logs(gerelateerd_model, gerelateerd_id);
CREATE INDEX idx_mail_logs_bericht_type ON mail_logs(bericht_type);
CREATE INDEX idx_mail_logs_created_at ON mail_logs(created_at);
CREATE INDEX idx_mail_logs_odoo_id ON mail_logs(odoo_id);

-- ============================================================================
-- AGENTS
-- ============================================================================
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Agent configuratie
    naam VARCHAR(255) NOT NULL UNIQUE,
    model VARCHAR(100) NOT NULL, -- gpt-4, gpt-3.5-turbo, claude, etc.
    prompt TEXT NOT NULL,
    
    -- Instellingen
    actief BOOLEAN DEFAULT TRUE,
    temperatuur DECIMAL(3, 2) DEFAULT 0.7 CHECK (temperatuur >= 0 AND temperatuur <= 2),
    
    -- Metadata
    beschrijving TEXT
);

CREATE INDEX idx_agents_actief ON agents(actief) WHERE actief = TRUE;

-- ============================================================================
-- TRIGGERS voor updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_contacten_updated_at BEFORE UPDATE ON contacten
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_facturen_updated_at BEFORE UPDATE ON facturen
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_mail_logs_updated_at BEFORE UPDATE ON mail_logs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- COMMENTS voor documentatie
-- ============================================================================
COMMENT ON TABLE contacten IS 'Contacten/partners (klanten en leveranciers)';
COMMENT ON TABLE orders IS 'Verkooporders en offertes';
COMMENT ON TABLE order_artikelen IS 'Order regels (artikelen per order)';
COMMENT ON TABLE facturen IS 'Facturen en creditnota''s';
COMMENT ON TABLE mail_logs IS 'E-mail en bericht logs';
COMMENT ON TABLE agents IS 'AI agent configuraties';
COMMENT ON TABLE artikelen IS 'Producten/artikelen uit Odoo';

COMMENT ON COLUMN contacten.is_portaal_partner IS 'Of dit een portaal partner is (leverancier)';
COMMENT ON COLUMN contacten.partner_commissie IS 'Commissie percentage voor partner';
COMMENT ON COLUMN orders.portaal_status IS 'Status in portaal: nieuw, beschikbaar, claimed, transfer';
COMMENT ON COLUMN orders.contractor_id IS 'Partner die deze order heeft geclaimd';
COMMENT ON COLUMN orders.inkoop_partner_incl_btw IS 'Bedrag dat partner krijgt (inclusief BTW)';
COMMENT ON COLUMN facturen.betalingsstatus IS 'Betaling status: not_paid, partial, paid';
COMMENT ON COLUMN agents.temperatuur IS 'AI model temperatuur (0-2)';
