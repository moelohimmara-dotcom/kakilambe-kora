-- ═══════════════════════════════════════════════════════════════════
-- Migration 005 — Plan V3 item 8 : synchronisation dynamique des
-- catégories WordPress réelles de kakilambe.com
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS wp_categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wp_id       INTEGER NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    slug        TEXT,
    -- kora_label : lequel des 7 libellés éditoriaux fixes (writer.py) cette
    -- catégorie WordPress réelle représente. NULL tant que non mappée.
    kora_label  TEXT CHECK (
        kora_label IN ('Politique','Économie','Société','Sport','Culture','Sécurité','International')
        OR kora_label IS NULL
    ),
    synced_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wp_categories_kora_label ON wp_categories(kora_label);

ALTER TABLE wp_categories ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'wp_categories' AND policyname = 'deny_anon_wp_categories'
  ) THEN
    CREATE POLICY deny_anon_wp_categories ON wp_categories FOR ALL TO anon USING (false);
  END IF;
END $$;
