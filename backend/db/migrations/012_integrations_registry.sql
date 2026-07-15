-- ═══════════════════════════════════════════════════════════════════
-- Migration 012 — Registre générique d'intégrations
--
-- Root cause du besoin (audit 2026-07-15) : aucune source commune ne
-- recensait "les intégrations disponibles" — la liste était câblée en dur
-- à 3 endroits indépendants (frontend/app/system/connections/page.tsx,
-- une route /health/* par service dans main.py, les clients concrets sous
-- integrations/). Rien n'empêchait ces trois vues de diverger (déjà
-- constaté : "Gemini" listé côté frontend alors qu'abandonné de la vraie
-- chaîne de fallback LLM depuis longtemps).
--
-- Cette table devient la source déclarative unique : ajouter une future
-- intégration (MCP server, API) = une ligne ici + un endpoint /health/*
-- répondant au contrat {"status": "ok"|"error", "detail"?: string} —
-- jamais une modification du code d'orchestration, de verrouillage, de
-- failover ou de veille déjà en place (principe ouvert/fermé).
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS integrations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key             TEXT UNIQUE NOT NULL,
    label           TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('llm', 'api', 'mcp', 'other')),
    description     TEXT,
    -- Endpoint de santé RELATIF (ex. "/health/wordpress") interrogé sur ce
    -- même backend — contrat générique {"status": "ok"|"error", "detail"?}.
    health_endpoint TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'integrations' AND policyname = 'deny_anon_integrations'
  ) THEN
    CREATE POLICY deny_anon_integrations ON integrations FOR ALL TO anon USING (false);
  END IF;
END $$;

-- Seed : les intégrations réellement en place aujourd'hui, reprises depuis
-- l'ancien tableau figé de connections/page.tsx — SANS "Gemini" (abandonné
-- de la vraie chaîne de fallback LLM, cf. core/llm_router.py PROVIDER_ORDER
-- = ["groq","cerebras","openrouter"] — le lister aurait perpétué l'écart
-- déjà constaté par l'audit entre ce que l'UI affiche et l'état réel).
INSERT INTO integrations (key, label, kind, description, health_endpoint) VALUES
  ('wordpress', 'WordPress',      'api',   'Publication des articles via l''API REST WP',       '/health/wordpress'),
  ('redis',     'Redis',          'other', 'Non utilisé dans cette architecture (retiré)',       '/health/redis'),
  ('supabase',  'Supabase (PostgreSQL)', 'api', 'Base de données principale',                    '/health/database'),
  ('groq',      'Groq API',       'llm',   'LLM principal — llama-3.3-70b-versatile',            '/health/providers/groq'),
  ('cerebras',  'Cerebras API',   'llm',   'LLM fallback #2 — gpt-oss-120b',                      '/health/providers/cerebras'),
  ('openrouter','OpenRouter API', 'llm',   'LLM fallback #3 — dernier recours',                   '/health/providers/openrouter'),
  ('tavily',    'Tavily Search',  'api',   'Moteur de recherche actualités africaines',           '/health/tavily'),
  ('image_gen', 'Pollinations.ai','api',   'Génération d''images d''illustration (sans clé API)', '/health/image_gen')
ON CONFLICT (key) DO NOTHING;
