# Plan de migration VPS — KORA

## Architecture cible

```
VPS Linux
├── Nginx (reverse proxy + SSL)
│   ├── api.kakilambe.com → :8000 (backend FastAPI)
│   └── kakilambe.com     → :3000 (frontend Next.js) OU static build
├── systemd
│   ├── kora-backend.service  (uvicorn)
│   └── kora-frontend.service (next start)
└── .env (hors git, sécurisé)
```

## Étapes

1. Installer les dépendances (Python 3.12, Node 20, Redis, Nginx)
2. Cloner le repo sur le VPS
3. Configurer les .env (backend + frontend)
4. Créer les services systemd
5. Configurer Nginx + SSL (Let's Encrypt)
6. Tester et basculer les DNS

## Services externes conservés
- Supabase (base de données) — pas de migration
- WordPress (kakilambe.com) — pas de migration
