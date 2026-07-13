# GuinéePress Intelligence — Kit de reprise

## Le projet est sur GitHub

**Cloner le projet :**
```bash
git clone https://github.com/moelohimmara-dotcom/guineepress-intelligence.git
cd guineepress-intelligence
npm install
```

## Tout le contexte est dans HANDOFF.md

Dans le dossier du projet cloné, ouvre `HANDOFF.md` — il contient :
- L'architecture complète
- Ce qui fonctionne / ce qui reste à faire
- Toutes les variables d'environnement nécessaires
- Les patterns de code à respecter
- Les liens vers tous les dashboards (Supabase, Groq, WordPress)

## Pour démarrer en local

1. Copier `.env.local.example` → `.env.local`
2. Remplir les variables (demander les valeurs au propriétaire du projet)
3. `npm run dev` → http://localhost:3000

## URLs importantes

| Service | URL |
|---------|-----|
| GitHub | https://github.com/moelohimmara-dotcom/guineepress-intelligence |
| WordPress admin | https://kakilambe.com/wp-admin |
| Recherche web (Agent) | POST /api/agent/search |
| Scraping (Agent) | POST /api/agent/scrape |

> Le projet n'est plus hébergé sur Vercel — les URLs `*.vercel.app` et le
> dashboard Vercel ont été retirés de cette table (hébergement de
> remplacement à documenter ici une fois choisi).

## Ce qui a été implémenté (26 juin 2026)

### Fonctionnalités complètes
- Pipeline complet RSS → IA → WordPress (6 crons quotidiens)
- Connexion WordPress kakilambe.com
- Agent IA avec tool calling (Groq function calling)
- Scraping web via Firecrawl (enrichissement contenu RSS)
- Recherche web temps réel via Tavily

### À compléter : obtenir les clés API
- **Firecrawl** : https://firecrawl.dev (500 crédits/mois gratuits)
- **Tavily** : https://tavily.com (1000 recherches/mois gratuites)

Ensuite, les ajouter aux variables d'environnement de l'hébergeur actuel et redéployer.

## Instruction pour l'IA de développement

Quand tu ouvres ce projet avec un assistant IA (Google, Anthropic, etc.), dis-lui :

> "Lis le fichier HANDOFF.md à la racine du projet pour comprendre l'architecture,
> l'état actuel et ce qui reste à faire."

---
*GuinéePress Intelligence — Mise à jour du 26 juin 2026*
