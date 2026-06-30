-- ═══════════════════════════════════════════════════════════════════
-- KORA — GuinéePress Intelligence
-- Migration 001 : Initialisation complète du schéma
-- Exécuter sur Supabase SQL Editor
-- ═══════════════════════════════════════════════════════════════════

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ═══════════════════════════════════════════════════════════════════
-- Table articles
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS articles (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titre             TEXT NOT NULL,
    formule_titre     TEXT,
    chapeau           TEXT,
    corps             TEXT,
    meta_description  TEXT,
    mots_cles         TEXT[],
    categorie_id      INTEGER,
    source_url        TEXT,
    source_nom        TEXT,
    source_level      INTEGER DEFAULT 1,
    image_prompt      TEXT,
    image_url         TEXT,
    wp_media_id       INTEGER,
    wp_post_id        INTEGER,
    wp_url            TEXT,
    status            TEXT DEFAULT 'DRAFT'
                      CHECK (status IN ('DRAFT','PENDING_REVIEW','PUBLISHED','REJECTED','FAILED')),
    origin            TEXT DEFAULT 'AGENT_AUTO'
                      CHECK (origin IN ('AGENT_AUTO','AGENT_SEMI','CHAT_EXPORT')),
    llm_provider_used TEXT,
    llm_model_used    TEXT,
    cycle_id          UUID,
    created_at        TIMESTAMPTZ DEFAULT now(),
    published_at      TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ DEFAULT now()
);

-- ═══════════════════════════════════════════════════════════════════
-- Table cycles
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS cycles (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode               TEXT CHECK (mode IN ('auto','semi')),
    status             TEXT DEFAULT 'RUNNING'
                       CHECK (status IN ('RUNNING','COMPLETED','FAILED','PAUSED')),
    articles_collected INTEGER DEFAULT 0,
    articles_selected  INTEGER DEFAULT 0,
    articles_published INTEGER DEFAULT 0,
    articles_rejected  INTEGER DEFAULT 0,
    provider_used      TEXT,
    tokens_consumed    INTEGER DEFAULT 0,
    error_log          TEXT,
    started_at         TIMESTAMPTZ DEFAULT now(),
    completed_at       TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════════
-- Table chat_sessions
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS chat_sessions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         TEXT,
    system_prompt TEXT,
    preset_used   TEXT,
    provider      TEXT,
    model         TEXT,
    temperature   FLOAT DEFAULT 0.7,
    max_tokens    INTEGER DEFAULT 2048,
    message_count INTEGER DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);

-- ═══════════════════════════════════════════════════════════════════
-- Table chat_messages
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS chat_messages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id    UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role          TEXT CHECK (role IN ('user','assistant')),
    content       TEXT NOT NULL,
    tokens_used   INTEGER DEFAULT 0,
    provider_used TEXT,
    model_used    TEXT,
    was_fallback  BOOLEAN DEFAULT false,
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- ═══════════════════════════════════════════════════════════════════
-- Table system_prompts
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS system_prompts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT UNIQUE NOT NULL,
    content     TEXT NOT NULL,
    is_default  BOOLEAN DEFAULT false,
    is_builtin  BOOLEAN DEFAULT false,
    temperature FLOAT DEFAULT 0.7,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

INSERT INTO system_prompts (name, content, is_builtin, is_default, temperature)
VALUES
  ('KORA Journaliste',
   'Tu es KORA, journaliste IA expert en actualité guinéenne et ouest-africaine pour kakilambe.com. '
   'Tu rédiges en français, style BBC News Afrique / New York Times. Neutre, factuel, accessible. '
   'Structure : titre informatif (max 70 caractères), chapeau d''accroche (2-4 phrases), corps en strates '
   '(faits bruts, pourquoi/comment, citations directes, contexte, enjeux chiffrés, perspective ouverte). '
   'Interdits : adjectifs non factuels, expressions floues, voix passive excessive, affirmations sans source. '
   'Jamais d''invention ni de parti pris politique.',
   true, true, 0.7),
  ('KORA Éditeur',
   'Tu es KORA en mode éditeur. Tu corriges, améliores et reformules les textes fournis. Conserve le sens, améliore la clarté.',
   true, false, 0.4),
  ('KORA SEO',
   'Tu génères des titres accrocheurs, méta-descriptions (155 car.) et tags pour les articles. Optimisé moteurs de recherche.',
   true, false, 0.5)
ON CONFLICT (name) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════
-- Table provider_states  (source de vérité — Redis a été retiré de l'architecture)
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS provider_states (
    provider           TEXT PRIMARY KEY,
    status             TEXT DEFAULT 'ACTIVE'
                       CHECK (status IN ('ACTIVE','RATE_LIMITED','EXHAUSTED','OFFLINE')),
    tokens_used_today  INTEGER DEFAULT 0,
    requests_today     INTEGER DEFAULT 0,
    last_error         TEXT,
    rate_limited_until TIMESTAMPTZ,
    exhausted_until    TIMESTAMPTZ,
    updated_at         TIMESTAMPTZ DEFAULT now()
);

INSERT INTO provider_states (provider) VALUES
  ('groq'), ('gemini'), ('cerebras'), ('openrouter')
ON CONFLICT (provider) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════
-- Table rss_sources
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS rss_sources (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    url         TEXT NOT NULL UNIQUE,
    category    TEXT,
    is_active   BOOLEAN DEFAULT true,
    last_synced TIMESTAMPTZ,
    error_count INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- ═══════════════════════════════════════════════════════════════════
-- Table app_settings
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO app_settings (key, value) VALUES
  ('cycle_hour',          '6'),
  ('cycle_timezone',      'Africa/Conakry'),
  ('articles_per_cycle',  '5'),
  ('semi_auto_mode',      'true'),
  ('delay_between_posts', '120'),
  ('daily_report',        'true'),
  ('error_alerts',        'true')
ON CONFLICT (key) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════
-- Indexes
-- ═══════════════════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_articles_status  ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_cycle   ON articles(cycle_id);
CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_msgs_session ON chat_messages(session_id, created_at);

-- ═══════════════════════════════════════════════════════════════════
-- Row Level Security (RLS)
-- ═══════════════════════════════════════════════════════════════════

-- Enable RLS on all tables
ALTER TABLE articles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE cycles          ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages   ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_prompts  ENABLE ROW LEVEL SECURITY;
ALTER TABLE provider_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE rss_sources     ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_settings    ENABLE ROW LEVEL SECURITY;

-- Default: deny all anonymous access
-- Only service_role (backend) has full access via bypass RLS
-- The backend connects with service_role key, so no policies needed for backend.
-- If you add anon/user auth later, add specific policies here.

-- Deny explicit policy for anon (belt-and-suspenders)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'articles' AND policyname = 'deny_anon_articles'
  ) THEN
    CREATE POLICY deny_anon_articles ON articles
      FOR ALL TO anon USING (false);
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════
-- Trigger: auto-update updated_at
-- ═══════════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_articles_updated_at
  BEFORE UPDATE ON articles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE OR REPLACE TRIGGER trg_chat_sessions_updated_at
  BEFORE UPDATE ON chat_sessions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE OR REPLACE TRIGGER trg_system_prompts_updated_at
  BEFORE UPDATE ON system_prompts
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
