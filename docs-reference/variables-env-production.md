# Variables d'environnement — Production

> Le projet n'est plus hébergé sur Vercel — ces variables doivent être
> configurées sur l'hébergeur de remplacement.
> Pour le développement local, copie .env.local.example → .env.local et remplis les valeurs.

## Variables actives en production (au 26 juin 2026)

| Variable | Valeur / Description |
|----------|---------------------|
| `SUPABASE_URL` | URL du projet Supabase (voir dashboard Supabase) |
| `SUPABASE_SERVICE_ROLE_KEY` | Clé service Supabase |
| `SUPABASE_ANON_KEY` | Clé publique Supabase |
| `GROQ_API_KEY` | Clé API Groq |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` |
| `WORDPRESS_URL` | `https://kakilambe.com` |
| `WORDPRESS_USERNAME` | `harvingt` |
| `WORDPRESS_APP_PASSWORD` | Application Password WordPress (26 caractères avec espaces) |
| `NEXTAUTH_SECRET` | Secret JWT NextAuth (32+ caractères) |
| `NEXTAUTH_URL` | URL de production actuelle (à mettre à jour — l'ancienne pointait vers *.vercel.app) |
| `ADMIN_EMAIL` | Email de connexion au dashboard |
| `ADMIN_PASSWORD_HASH` | Hash bcrypt du mot de passe admin |
| `NEXT_PUBLIC_APP_NAME` | `GuinéePress Intelligence` |
| `CRON_SECRET` | Secret pour sécuriser les routes /api/cron/* |
| `PIPELINE_MODE` | Mode du pipeline |

## Pour ajouter/modifier une variable

Utiliser l'interface (dashboard ou CLI) de l'hébergeur de remplacement —
utiliser `printf` (pas `echo`) si la commande d'ajout passe par un pipe, pour
éviter le BOM Windows.

## IMPORTANT — sécurité

- Ne jamais commiter `.env.local` dans Git
- Ce fichier ne contient pas les valeurs réelles — seulement les noms
- Les valeurs sont dans le dashboard de l'hébergeur actuel et sur les services respectifs
