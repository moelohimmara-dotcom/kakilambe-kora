-- ═══════════════════════════════════════════════════════════════════
-- Migration 003 — Historique du Chat IA : épingler / archiver
-- Ajoute les colonnes nécessaires au renommage inline + actions de la
-- sidebar de conversations. Ces colonnes n'existaient pas avant cette
-- migration malgré une instruction supposant le contraire.
-- ═══════════════════════════════════════════════════════════════════

ALTER TABLE chat_sessions
  ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived'));

CREATE INDEX IF NOT EXISTS idx_chat_sessions_pinned
  ON chat_sessions (is_pinned DESC, updated_at DESC);
