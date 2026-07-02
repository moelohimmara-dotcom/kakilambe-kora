-- ═══════════════════════════════════════════════════════════════════
-- Migration 006 — Plan V3 Phase 2 : sources de presse réelles à deux
-- niveaux (Guinée / Panafricain) + table unique d'ingestion par lots.
--
-- Écarts volontaires par rapport à la liste fournie dans l'instruction :
-- ConakryPlanet (conakryplanet.com), Espace Media GN (espace.media.gn)
-- et BBCNewsAfrica (bbcnewsafrica.com) ne résolvent à AUCUNE adresse DNS
-- réelle (vérifié en direct avant migration) — exclus pour ne pas
-- polluer rss_sources avec des sources mortes. BBC Afrique déjà couverte
-- par le flux RSS officiel feeds.bbci.co.uk/afrique/rss.xml.
-- ═══════════════════════════════════════════════════════════════════

ALTER TABLE rss_sources ADD COLUMN IF NOT EXISTS source_level integer NOT NULL DEFAULT 2;

TRUNCATE TABLE rss_sources;

-- NIVEAU 1 : Médias guinéens (priorité absolue, jamais filtrés par pertinence)
INSERT INTO rss_sources (name, url, category, source_level) VALUES
('GuinéeActu',      'https://guineeactu.com/feed/',      'Général', 1),
('GuinéeNews',      'https://guineenews.org/feed/',      'Général', 1),
('MédiaGuinée',     'https://mediaguinee.org/feed/',     'Général', 1),
('Le Djely',        'https://ledjely.com',                'Général', 1),
('AfricaGuinée',    'https://africaguinee.com/rss.xml',   'Général', 1),
('MosaïqueGuinée',  'https://mosaiqueguinee.com/feed/',   'Général', 1),
('Guinée7',         'https://guinee7.com/feed/',          'Général', 1);

-- NIVEAU 2 : Médias panafricains (filtre thématique strict en aval, cf. selector.py)
INSERT INTO rss_sources (name, url, category, source_level) VALUES
('AfricaNews',           'https://africanews.com/feed/',            'Panafricain', 2),
('BBC Afrique',          'https://feeds.bbci.co.uk/afrique/rss.xml', 'Panafricain', 2),
('Jeune Afrique',        'https://www.jeuneafrique.com/feed/',      'Panafricain', 2),
('AllAfrica',            'https://allafrica.com',                    'Panafricain', 2),
('Forbes Afrique',       'https://forbesafrique.com/feed/',          'Panafricain', 2),
('Africa Intelligence',  'https://africaintelligence.com',           'Panafricain', 2);

-- Table unique et optimisée d'ingestion brute en temps réel — un seul
-- schéma générique pour tous les flux (pas de table par source, ce qui
-- épuiserait le pool de connexions du tier gratuit Supabase).
CREATE TABLE IF NOT EXISTS raw_feeds (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id      UUID NOT NULL,   -- = cycle_id du cycle KORA qui a produit ce lot
    source_url    TEXT NOT NULL,
    source_name   TEXT NOT NULL,
    title         TEXT NOT NULL,
    content       TEXT,
    extracted_at  TIMESTAMPTZ DEFAULT now(),
    is_processed  BOOLEAN DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_raw_feeds_batch ON raw_feeds(batch_id);
CREATE INDEX IF NOT EXISTS idx_raw_feeds_unprocessed ON raw_feeds(is_processed) WHERE is_processed = false;

ALTER TABLE raw_feeds ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'raw_feeds' AND policyname = 'deny_anon_raw_feeds'
  ) THEN
    CREATE POLICY deny_anon_raw_feeds ON raw_feeds FOR ALL TO anon USING (false);
  END IF;
END $$;
