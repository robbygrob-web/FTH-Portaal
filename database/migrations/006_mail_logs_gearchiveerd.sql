-- Migratie 006: Archiveer functionaliteit voor mail_logs
-- Datum: 2024-01-XX
-- 
-- Voegt gearchiveerd kolom toe aan mail_logs tabel voor archiveer functionaliteit.

ALTER TABLE mail_logs ADD COLUMN IF NOT EXISTS gearchiveerd BOOLEAN DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_mail_logs_gearchiveerd ON mail_logs(gearchiveerd);
