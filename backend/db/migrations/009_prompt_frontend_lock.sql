-- ═══════════════════════════════════════════════════════════════════
-- Migration 009 — Verrouillage backend du prompt principal
-- Jusqu'ici, PATCH /api/settings/prompts/{id} acceptait de modifier
-- N'IMPORTE QUEL prompt, y compris "KORA Journaliste" (le prompt par
-- défaut, cerveau éditorial du système) — aucune protection serveur,
-- seul le rendu du bouton "Modifier" dans l'UI aurait pu être retiré
-- (contournable via un appel API direct). frontend_locked=true rend ce
-- prompt non modifiable depuis AUCUNE route exposée au frontend (PATCH,
-- reset, refine, restore-from-primary) — seul un accès backend direct
-- (script/CLI) peut le modifier.
-- ═══════════════════════════════════════════════════════════════════

ALTER TABLE system_prompts ADD COLUMN IF NOT EXISTS frontend_locked BOOLEAN NOT NULL DEFAULT false;

UPDATE system_prompts SET frontend_locked = true WHERE name = 'KORA Journaliste' AND is_builtin = true;
