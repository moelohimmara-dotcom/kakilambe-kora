-- ═══════════════════════════════════════════════════════════════════
-- Migration 008 — Empêcher les doublons de sources RSS
-- Audité (CDC §7.4.2) : aucune contrainte n'empêchait d'ajouter deux fois
-- la même URL, ni côté front ni côté backend (INSERT simple sans
-- ON CONFLICT). Vérifié avant migration : aucun doublon existant en base.
-- ═══════════════════════════════════════════════════════════════════

ALTER TABLE rss_sources
  ADD CONSTRAINT rss_sources_url_unique UNIQUE (url);
