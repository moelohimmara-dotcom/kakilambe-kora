-- ═══════════════════════════════════════════════════════════════════
-- Migration 007 — Suppression de la fonctionnalité Chat IA
-- Le client ne souhaite pas de chat dans l'application (voir suppression
-- de backend/api/chat_routes.py et de la page /dashboard/agent du projet
-- guineepress-intelligence). Ces deux tables ne sont plus utilisées par
-- aucun code applicatif — DROP définitif et irréversible des données.
--
-- Ordre : chat_messages avant chat_sessions (FK ON DELETE CASCADE,
-- mais on reste explicite plutôt que de compter sur la cascade).
-- ═══════════════════════════════════════════════════════════════════

DROP TABLE IF EXISTS chat_messages;
DROP TABLE IF EXISTS chat_sessions;
