-- ═══════════════════════════════════════════════════════════════════
-- Migration 011 — Veille passive : pool de contenu pré-collecté
--
-- Root cause du besoin (audit 2026-07-14) : chaque clic sur "Lancer un
-- cycle" déclenchait un balayage complet et en direct de toutes les
-- sources (Tavily + Firecrawl), même quand des informations fraîches du
-- jour étaient déjà potentiellement disponibles. `content_pool` stocke
-- désormais le résultat d'une veille planifiée (toutes les 2h) que le
-- cycle consomme en priorité avant tout scraping.
--
-- Chaque ligne = UN élément d'UNE seule source (jamais de fusion de
-- contenu entre sources à ce stade — la traçabilité de provenance est
-- structurelle : source_url/source_name sont NOT NULL et jamais
-- réécrits). `duplicate_of` LIE deux lignes de sources différentes
-- rapportant le même événement réel, sans jamais en supprimer une ni
-- fusionner leur contenu — la ligne dupliquée reste consultable et
-- traçable, seule la consommation la traite comme un groupe (même
-- logique qu'`aggregated_sources` déjà utilisée par writer.py).
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS content_pool (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url          TEXT NOT NULL,
    source_name         TEXT NOT NULL,
    title               TEXT NOT NULL,
    content             TEXT,
    -- Titre normalisé (minuscules, sans accents/ponctuation) utilisé
    -- UNIQUEMENT pour le calcul de similarité inter-sources — jamais
    -- affiché, jamais utilisé comme source de vérité du contenu.
    title_norm          TEXT NOT NULL,
    kora_label          TEXT CHECK (
        kora_label IN ('Politique','Économie','Société','Sport','Culture','Sécurité','International')
        OR kora_label IS NULL
    ),
    collected_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Frontière explicite du jour, indépendante du fuseau du serveur au
    -- moment de la requête — la consommation ET la purge filtrent
    -- TOUJOURS sur collection_date = CURRENT_DATE, jamais sur
    -- collected_at seul (défense en profondeur si la purge échoue).
    collection_date      DATE NOT NULL DEFAULT CURRENT_DATE,
    status               TEXT NOT NULL DEFAULT 'available' CHECK (
        status IN ('available', 'used', 'expired')
    ),
    used_at              TIMESTAMPTZ,
    used_by_article_id   UUID REFERENCES articles(id),
    -- NULL = élément primaire ou sans doublon détecté. Sinon, référence
    -- l'élément (autre source, même jour) rapportant le même événement.
    duplicate_of         UUID REFERENCES content_pool(id),
    UNIQUE(source_url, collection_date)
);

CREATE INDEX IF NOT EXISTS idx_content_pool_status ON content_pool(status);
CREATE INDEX IF NOT EXISTS idx_content_pool_date ON content_pool(collection_date);
CREATE INDEX IF NOT EXISTS idx_content_pool_source ON content_pool(source_name);
CREATE INDEX IF NOT EXISTS idx_content_pool_duplicate_of ON content_pool(duplicate_of);

ALTER TABLE content_pool ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'content_pool' AND policyname = 'deny_anon_content_pool'
  ) THEN
    CREATE POLICY deny_anon_content_pool ON content_pool FOR ALL TO anon USING (false);
  END IF;
END $$;

-- Historique des exécutions de veille (planifiée, manuelle-admin, ou
-- scraping de secours) — donne à l'admin une visibilité réelle sans
-- accès direct à la base (cf. GET /api/pool/status).
CREATE TABLE IF NOT EXISTS pool_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger             TEXT NOT NULL CHECK (
        trigger IN ('scheduled', 'manual_admin', 'exception_scrape')
    ),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at          TIMESTAMPTZ,
    sources_scanned      INTEGER DEFAULT 0,
    items_collected       INTEGER DEFAULT 0,
    duplicates_linked      INTEGER DEFAULT 0,
    status               TEXT NOT NULL DEFAULT 'running' CHECK (
        status IN ('running', 'completed', 'failed')
    ),
    error                TEXT
);

CREATE INDEX IF NOT EXISTS idx_pool_jobs_started_at ON pool_jobs(started_at DESC);

ALTER TABLE pool_jobs ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'pool_jobs' AND policyname = 'deny_anon_pool_jobs'
  ) THEN
    CREATE POLICY deny_anon_pool_jobs ON pool_jobs FOR ALL TO anon USING (false);
  END IF;
END $$;

-- Paramètres admin-configurables — réutilise app_settings (clé/valeur
-- générique déjà en place) plutôt qu'une nouvelle table dédiée.
INSERT INTO app_settings (key, value) VALUES
  ('pool_interval_hours',   '2'),
  ('pool_dedup_threshold',  '0.6')
ON CONFLICT (key) DO NOTHING;
