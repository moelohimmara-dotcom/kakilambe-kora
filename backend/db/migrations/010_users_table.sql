-- ═══════════════════════════════════════════════════════════════════
-- Migration 010 — Table utilisateurs réelle
-- Root cause (audit 2026-07-14) : KORA V3 n'avait AUCUNE table utilisateur
-- — l'authentification comparait email/mot de passe à des variables
-- d'environnement statiques (ADMIN_EMAIL/ADMIN_SECRET_KEY), et le bloc
-- "Éditeur / kakilambe.com" de la sidebar était du texte JSX en dur, sans
-- aucune donnée derrière. Impossible de personnaliser un nom affiché, un
-- thème ou de changer un mot de passe sans une vraie persistance par
-- utilisateur. Cette migration introduit cette table et migre le compte
-- unique existant dedans (mot de passe hashé, jamais en clair).
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL DEFAULT 'Éditeur',
    theme         TEXT NOT NULL DEFAULT 'light' CHECK (theme IN ('light', 'dark')),
    role          TEXT NOT NULL DEFAULT 'editor' CHECK (role IN ('editor', 'admin')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Le seed réel (email + hash du secret actuel) est fait par un script
-- Python séparé (db/scripts/seed_admin_user.py), PAS ici en SQL : bcrypt
-- n'est pas disponible côté Postgres, et hasher en clair dans une migration
-- SQL versionnée dans git violerait la règle "jamais de mot de passe en
-- clair, y compris dans les logs/fichiers de debug".
