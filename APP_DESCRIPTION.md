# GuinéePress Intelligence — KORA V3

Fiche technique et fonctionnelle de référence. Reflète l'état réel du dépôt et de l'infrastructure au 2026-07-03, vérifié directement dans le code et sur le VPS de production (pas une description aspirationnelle).

---

## A. Présentation générale & vision produit

- **Nom du projet :** GuinéePress Intelligence (nom de code : **KORA V3**).
- **Mission :** pipeline éditorial autonome et semi-automatique de veille, collecte, réécriture journalistique et diffusion d'actualités panafricaines et guinéennes.
- **Plateforme cible de diffusion :** WordPress ([kakilambe.com](https://kakilambe.com)), via l'API REST WordPress avec un compte applicatif dédié.
- **Interface d'exploitation :** tableau de bord web (`/dashboard`, `/agent`, `/articles`, `/chat`, `/sources`, `/history`, `/settings`) réservé à l'éditeur, plus un panneau d'administration technique séparé (`/system`) protégé par une double couche (cookie applicatif + Basic Auth Nginx).

---

## B. Architecture technique & stack logicielle

| Couche | Technologie | Détail |
|---|---|---|
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind CSS | Dashboard éditeur, éditeur d'article, chat IA, écrans admin |
| Backend API | FastAPI (Python), asynchrone | Routes montées sous `/api/*`, écoute en local (port 8000) derrière Nginx |
| Orchestration IA | LangGraph | Deux graphes d'état compilés depuis un même builder : `kora_graph_semi` (HITL) et `kora_graph_auto` (autonome) — voir section C.3 |
| LLM | LiteLLM / routeur multi-fournisseurs custom (`core/llm_router.py`) | Chaîne de repli **Groq → Gemini → Cerebras → OpenRouter** |
| Base de données | Supabase (PostgreSQL managé), RLS activé sur les tables | Accès depuis le VPS via le **pooler IPv4** (`aws-0-eu-west-1.pooler.supabase.com`) — la connexion directe Supabase est IPv6 seule et le VPS n'a pas d'IPv6 |
| Authentification | **Cookie de session applicatif maison**, comparaison directe à `ADMIN_SECRET_KEY` (pas de JWT, pas de bcrypt, **pas de Supabase Auth**) | `POST /api/auth/login` pose le cookie `kora_session` ; un second cookie `kora_admin_token` protège le panneau `/system` |
| Infrastructure | VPS Debian 12 (LWS, `vps121997.serveur-vps.net`) | Migration complète depuis DigitalOcean App Platform effectuée le 2026-07-02 (app DO supprimée) |
| Reverse proxy | Nginx | Unique point d'entrée public (port 80) ; route `/api/*` vers le backend (8000), tout le reste vers le frontend Next.js (3000), Basic Auth sur `/system` |
| Chiffrement SSL/TLS | **Non actif** | Bloqué par une dépendance externe, pas par un manque de travail : aucun nom de domaine ne pointe encore vers `213.156.135.139`, condition requise par le challenge HTTP-01 de Let's Encrypt/Certbot. Le trafic transite en HTTP clair en attendant qu'un domaine soit acheté et pointé. |
| Files d'attente / planification différée | QStash (Upstash) | Espace les publications WordPress d'un même cycle (le premier article publie en direct, les suivants sont mis en file avec un délai croissant) — intégration réelle (`integrations/qstash_client.py`, webhook de callback dans `api/webhook_routes.py`) |
| Orchestration tierce (n8n) | **Absente — choix d'architecture explicite** | Le pipeline n'utilise ni n8n ni Airtable : l'orchestration passe entièrement par des graphes d'état LangGraph typés en Python, la persistance par Supabase/Postgres |

---

## C. Fonctionnalités clés et modules cœurs

### 1. Le scraper dynamique et la hiérarchie de sources à 3 niveaux

Le pipeline de collecte (`agent/nodes/scraper.py`, `agent/nodes/selector.py`) hiérarchise les sources par `source_level` en base (`rss_sources`) :

- **Niveau 1** — sources guinéennes vérifiées, sondées plus largement (priorité éditoriale).
- **Niveau 2** — médias panafricains de référence.
- **Niveau 3** — repli : résultats Tavily hors sources curées, soumis au même filtre strict de pertinence.

Chaque lot de collecte est identifié par un `batch_id`, persisté dans `raw_feeds` puis marqué traité (`_mark_raw_feeds_processed`) pour éviter les doublons entre cycles. Firecrawl vient enrichir le contenu Markdown complet des articles retenus ; BrightData sert de repli supplémentaire.

### 2. Le nœud rédacteur (`writer.py`) — calibrage éditorial BBC News Africa

Confirmé dans le code : structure en pyramide inversée, règle des **5W** imposée sur les deux premières phrases du chapeau, détection et rejet des sous-titres génériques ("Conclusion", "Enjeux"...), fonction `_validate_style()` qui retente la génération en cas de non-conformité, et signature déterministe ajoutée systématiquement en fin d'article :

```
*Par Kakilambe Kora Agent*
```

### 3. Le système bimode et la machine à états HITL

Un seul graphe LangGraph est construit par un builder commun (`build_kora_graph`), compilé en deux variantes :

- **`kora_graph_semi`** — compilé avec `interrupt_before=["publish_wordpress"]` et un checkpointer `MemorySaver`. Le graphe s'arrête juste avant publication ; l'article passe en base au statut `PENDING_REVIEW` ; l'interface affiche la carte de validation HITL. La reprise (`POST /api/agent/resume/{cycle_id}`) réinjecte l'état et relance le graphe depuis le point d'interruption.
  - Limite architecturale connue et assumée : le checkpointer `MemorySaver` vit en mémoire du process — un cycle mis en pause survit à un rafraîchissement de page mais **pas** à un redémarrage du backend.
- **`kora_graph_auto`** — même graphe, sans interruption : publication directe en fin de pipeline.

Le mode réellement utilisé par le cycle planifié (cron quotidien) est piloté dynamiquement par le seul réglage exposé côté dashboard (`auto_publish_enabled`), pas par une valeur codée en dur.

### 4. Le terminal de logs interactif

Console web temps réel (écran `/agent`) connectée en Server-Sent Events au backend, avec rejeu de l'historique persisté (`cycle_logs`) à la connexion. Nettoyage automatique intuitif en fin de cycle : fade-out puis vidage 7 secondes après une clôture réussie (`status: COMPLETED`), et vidage immédiat au lancement d'un nouveau cycle.

### 5. Le module de paramètres avancés (`/settings`)

Réglages réellement persistés en base et appliqués par le backend (`api/settings_routes.py`) :

- Identifiants WordPress (`wp_url`, `wp_username`, `wp_app_password`).
- Activation de la publication automatique (`auto_publish_enabled`) — seul levier qui bascule le cron entre mode auto et mode semi.
- Limite quotidienne d'articles (`daily_article_limit`).
- Mapping des catégories WordPress (`update_wp_category_mapping`).
- Heure d'exécution du cycle planifié (`cycle_hour`), avec reprogrammation à chaud du scheduler sans redémarrage de service.
- E-mail de destination des rapports de cycle (`admin_email`).
- Éditeur des prompts système avec réinitialisation aux valeurs par défaut.

---

## D. Écarts connus avec une architecture générique n8n/Airtable

Documentés explicitement dans les specs internes du projet :

- Pas de workflow visuel n8n — orchestration par nœuds Python typés dans un graphe d'état.
- Pas d'Airtable — persistance Postgres via Supabase, RLS activé sur les tables sensibles.
- Statuts d'articles propres à KORA (`PENDING_REVIEW` / `DRAFT` / `PUBLISHED` / `REJECTED` / `FAILED`), sans équivalence directe avec un vocabulaire générique de type "candidat/prêt/publié/erreur".

---

## E. Points d'attention infrastructure (au 2026-07-03)

- **HTTPS** : en attente d'un nom de domaine à pointer vers `213.156.135.139` ; Certbot n'a pas encore été sollicité pour ne pas consommer les quotas de taux Let's Encrypt sur des tentatives vouées à l'échec sans DNS résolu.
- **Déploiement** : plus de déploiement automatique depuis la suppression de l'app DigitalOcean — un `git push` ne met plus le VPS à jour seul ; le déploiement (pull + rebuild frontend + redémarrage des services `systemd`) est manuel.
- **Base de données** : connexion depuis le VPS exclusivement via le pooler IPv4 Supabase, la résolution directe étant IPv6 uniquement.
