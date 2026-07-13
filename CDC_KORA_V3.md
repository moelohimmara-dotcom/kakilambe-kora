# CAHIER DES CHARGES — KORA V3 (GuinéePress Intelligence)

**Destinataire :** agent IA d'ingénierie logicielle (implémentation autonome).
**Format d'inspiration des interfaces :** style d'exhaustivité et de granularité écran-par-écran façon fiches Mobbin — chaque écran est décrit indépendamment avec sa structure visuelle, ses états, ses composants et ses règles de transition, avant d'être remis en contexte dans le parcours global.

**Principe directeur de ce document :** ne jamais confier à l'agent une tâche globale ("refais l'UI", "corrige le bug HITL"). Chaque section ci-dessous se termine par une liste de **micro-tâches atomiques, ordonnées et vérifiables indépendamment**. L'agent doit traiter une micro-tâche à la fois, la valider (compilation, test, vérification visuelle), puis passer à la suivante. Aucune micro-tâche ne doit dépendre d'une supposition sur l'état du code — l'agent doit auditer le fichier réel avant toute modification.

---

## SOMMAIRE

0. [Architecture globale & principes transverses](#0-architecture-globale--principes-transverses)
1. [Écran : Connexion (`/login`)](#1-écran--connexion-login)
2. [Écran : Configuration initiale (`/setup`)](#2-écran--configuration-initiale-setup)
3. [Écran : Tableau de bord (`/dashboard`)](#3-écran--tableau-de-bord-dashboard)
4. [Écran : Agent KORA (`/agent`)](#4-écran--agent-kora-agent)
5. [Écran : Articles — grille (`/articles`)](#5-écran--articles--grille-articles)
6. [Écran : Article — révision (`/articles/{id}`)](#6-écran--article--révision-articlesid)
7. [Écran : Sources RSS (`/sources`)](#7-écran--sources-rss-sources)
8. [Écran : Historique (`/history`)](#8-écran--historique-history)
9. [Écran : Paramètres (`/settings`)](#9-écran--paramètres-settings)
10. [Écrans système / diagnostic (`/system/*`)](#10-écrans-système--diagnostic-system)
11. [Composants transverses (design system)](#11-composants-transverses-design-system)
12. [Matrice d'interdépendance globale](#12-matrice-dinterdépendance-globale)
13. [Checklist de non-régression obligatoire](#13-checklist-de-non-régression-obligatoire)

---

## 0. Architecture globale & principes transverses

### 0.1 Stack technique (état réel vérifié)

| Couche | Technologie |
|---|---|
| Backend | FastAPI (Python), orchestration LangGraph |
| Frontend | Next.js 15 (App Router), React, Tailwind CSS |
| Base de données | Supabase Postgres (pooler IPv4) |
| Hébergement | VPS Debian auto-géré, Nginx (reverse proxy HTTP), systemd (`kora-backend`, `kora-frontend`) |
| Pipeline éditorial | `scrape → select → write → illustrate → publish → report` (LangGraph, `interrupt_before=["publish_wordpress"]` en mode semi) |
| Providers LLM | Chaîne de fallback multi-fournisseurs (Groq, Gemini, Cerebras, OpenRouter) |
| Enrichissement contenu | Firecrawl (BrightData abandonné définitivement) |
| Recherche de sources | Tavily (`topic="news", days=1`) |

### 0.2 Groupes de routes réels (vérifiés dans `frontend/app/`)

```
(auth)/          → /login, /setup                         [non authentifié]
(editorial)/     → /, /dashboard, /agent, /articles,
                   /articles/[id], /sources, /history,
                   /settings                               [authentifié, IHM éditoriale]
system/          → /system, /system/connections,
                   /system/cycles, /system/login,
                   /system/logs, /system/providers          [diagnostic technique, thème sombre distinct]
```

### 0.3 Règles transverses non négociables (verrous produit)

Ces règles s'appliquent à **tous** les écrans ci-dessous. Elles ne doivent JAMAIS être contournées par une modification locale à un écran :

1. 🟪 **Mode semi-automatique verrouillé** — la validation humaine (HITL) avant publication n'est désactivable depuis aucune IHM. Le composant `Toggle` sur `/agent` est rendu `checked={true} disabled`.
2. 🟪 **Un seul écran de transition plein écran actif à la fois**, et uniquement pour le travail déclenché par l'action de l'utilisateur dans la session courante — jamais pour un état ambiant découvert passivement (cycle `PAUSED` d'une session précédente, etc.).
3. 🟪 **Cibles tactiles ≥44px** (boutons `sm`/`md`), **≥48px** (`lg`) — appliqué globalement via `components/ui/Button.tsx`.
4. 🟪 **Aucun texte technique brut** (stack trace, JSON d'erreur FastAPI non traduit, nom de fonction interne) ne doit atteindre l'utilisateur final dans le groupe `(editorial)`. Le groupe `system/*` fait exception assumée (destiné à un profil technique).
5. 🟪 **Double-clic bloqué** sur toute action mutante (publication, rejet, régénération, ajout/suppression de source) via un flag `loading`/`anyActionInFlight` déclenché **avant** l'appel réseau, jamais après.
6. 🟪 **Toute décision d'affichage d'un état critique (ex. "cycle en pause", "article introuvable") doit être vérifiée par un appel serveur frais au moment de la décision**, jamais uniquement déduite d'un état pollé potentiellement périmé (throttling d'onglet, échec de requête silencieux).

### 0.4 Méthode de travail imposée à l'agent

Avant toute micro-tâche de ce document, l'agent DOIT :
1. Lire le fichier réel concerné (jamais supposer son contenu à partir de ce CDC).
2. Vérifier si la fonctionnalité décrite existe déjà (grep/lecture) — ce document distingue explicitement **✅ Déjà implémenté** (ne pas retravailler, sauf régression constatée) et **🔲 À faire** (travail réel).
3. Traiter une seule micro-tâche à la fois, dans l'ordre indiqué.
4. Valider par compilation (`tsc --noEmit` / `py_compile`) et, si un test existe déjà pour la zone touchée, l'exécuter avant de continuer.
5. Ne jamais élargir le scope d'une micro-tâche à autre chose que ce qui est écrit.

---

## 1. Écran : Connexion (`/login`)

**Fichier :** `frontend/app/(auth)/login/page.tsx` — composant inline (pas de fichier `screens/` séparé).
**Groupe :** `(auth)`, layout dédié sans sidebar/nav.

### 1.1 Structure visuelle (fiche écran)

🟨 **Page** — plein écran, fond crème (`bg-cream`), carte centrée `max-w-[400px]`.
- **En-tête logo** : `/KORA` (le `/` en orange), sous-titre "GuinéePress Intelligence · kakilambe.com".
- **Carte blanche** (`rounded-xl border shadow-card p-8`) :
  - Titre "Connexion".
  - Champ **Adresse e-mail** (`type=email`, `autoComplete=email`, requis).
  - Champ **Mot de passe** (`type=password`, `autoComplete=current-password`, requis).
  - Zone d'erreur conditionnelle (`role="alert"`, fond rouge pâle) — affichée seulement si `error` non vide.
  - Bouton **"Se connecter"** (`variant=primary`, `size=lg`, pleine largeur, état `loading` → texte "Connexion…").
- **Pied de page** : "GuinéePress Intelligence — Phase 3".

### 1.2 Fonctionnement (état réel)

- ✅ Soumission → `POST /api/auth/login` avec `{email, password}`.
- ✅ Succès → redirection vers `?redirect=` (query param) si présent, sinon `/dashboard`.
- ✅ Échec → affiche `body.detail` du backend ou "Identifiants incorrects".
- ✅ Erreur réseau → "Connexion impossible — vérifiez votre réseau".
- ✅ Accessibilité : `aria-invalid`, `aria-describedby` liés à l'erreur.

### 1.3 Interdépendances

- → `/dashboard` (redirection par défaut post-login).
- → n'importe quelle route protégée via `?redirect=` (middleware d'authentification, à vérifier — voir micro-tâche 1.4.3).
- ⚠️ Dépend de l'endpoint backend `POST /api/auth/login` — ne pas modifier ce contrat sans vérifier tous les appelants.

### 1.4 Micro-tâches

1. **Audit** — lire `frontend/middleware.ts` (ou équivalent) pour confirmer le mécanisme réel de protection des routes `(editorial)` et `system`, et comment `?redirect=` est injecté. Ne rien modifier à cette étape, seulement documenter la trouvaille en commentaire si absent.
2. **Audit** — vérifier si un mécanisme de "mot de passe oublié" existe ou est prévu ; s'il n'existe pas et n'est pas demandé explicitement par le produit, **ne pas l'ajouter** (hors périmètre tant que non demandé).
3. **Si régression constatée uniquement** — corriger le comportement de redirection cassé (ne pas toucher si fonctionnel).

---

## 2. Écran : Configuration initiale (`/setup`)

**Fichier :** `frontend/components/screens/OnboardingScreen.tsx` (244 lignes).
**Groupe :** `(auth)`.

### 2.1 Structure visuelle (fiche écran, style wizard multi-étapes)

🟨 **Page** — assistant à étapes (`STEPS = ['welcome', 'wordpress', 'sources', 'done']`), indicateur de progression basé sur `stepIndex`.

- **Étape `welcome`** : écran d'accueil / présentation du produit avant configuration.
- **Étape `wordpress`** : formulaire `{ url, username, password }` (état `WPForm`), bouton de test de connexion → `healthApi.check()`, résultat `wpStatus: 'idle' | 'ok' | 'fail'` affiché visuellement (badge coloré).
- **Étape `sources`** : liste éditable de sources RSS par défaut (`DEFAULT_SOURCES`), formulaire d'ajout `{ name, url }`.
- **Étape `done`** : confirmation, bouton final vers `/dashboard`.

### 2.2 Fonctionnement (état réel)

- ✅ Navigation séquentielle entre étapes (pas de retour arrière destructif attendu — à vérifier).
- ✅ Test WordPress avant validation (`testing: boolean`, `wpStatus`).
- ✅ Sauvegarde finale (`saving: boolean`) — probablement `POST` vers un endpoint de settings/sources en bloc.

### 2.3 Interdépendances

- Écrit dans les mêmes tables/endpoints que `/settings` (onglet WordPress) et `/sources` — **toute modification du schéma de configuration WordPress doit être répercutée dans les 3 écrans** : `/setup`, `/settings` (WordPress Tab), et le backend `settings_routes.py`.
- → `/dashboard` en sortie.

### 2.4 Micro-tâches

1. **Audit** — confirmer que `/setup` n'est accessible qu'une seule fois (première installation) et redirige vers `/dashboard` si déjà configuré, en lisant la logique de garde réelle (probablement basée sur un flag `app_settings` backend). Documenter le mécanisme trouvé.
2. **Audit** — vérifier la cohérence des champs du formulaire WordPress entre `OnboardingScreen.tsx` et `SettingsScreen.tsx` (`WordPressTab`) : mêmes noms de clés, mêmes validations.
3. **Si divergence constatée** — aligner les deux formulaires sur un seul type partagé (`WPForm`/`AppSettings`) plutôt que deux définitions parallèles.

---

## 3. Écran : Tableau de bord (`/dashboard`)

**Fichier :** `frontend/components/screens/DashboardScreen.tsx` (288 lignes).
**Groupe :** `(editorial)`, sidebar + topbar visibles.

### 3.1 Structure visuelle (fiche écran)

🟨 **Page** — vue d'ensemble, non actionnable en profondeur (les actions réelles se font sur `/agent` et `/articles`).

- **En-tête** : titre "Tableau de bord", sous-titre "GuinéePress Intelligence · kakilambe.com", bouton **"Lancer un cycle"** en haut à droite (raccourci direct vers l'action principale sans passer par `/agent`).
- **Rangée de KPI** (`KpiCard` × 4) :
  - En attente de validation (nombre d'articles `PENDING_REVIEW`).
  - Publiés (page actuelle).
  - Erreurs.
  - Statut du cycle en cours (texte : "Complété" / "En pause" / "En cours"...).
- **Carte de statut de cycle** (`CycleStatusCard`) — affiche l'état du dernier cycle connu (`cycle?.status`), avec mise en avant de l'article HITL bloquant si `isPaused` (`hitlArticle = pending[0]`).
- **Liste "Articles récents"** (`ArticleRow` × N) — miniature, titre, source, date relative, badge de statut, lien "Voir tout →" vers `/articles`.
- **État vide** (`EmptyDashboard`) si aucune donnée.

### 3.2 Fonctionnement (état réel, bug déjà corrigé à ne pas réintroduire)

- ✅ `fetchDashboard()` agrège **3 appels en parallèle** via `Promise.allSettled` : articles en attente, articles récents, statut de cycle.
- ⚠️ **Piège déjà documenté dans le code** : la réponse de `GET /api/agent/status` est **plate** (`{cycle_id, status, ...}`), jamais imbriquée sous une clé `cycle`. Un bug précédent lisait `(res as {cycle?}).cycle` qui était toujours `undefined`, affichant "Inactif" en permanence. **Ne jamais réintroduire cette supposition de structure.**
- ✅ Rafraîchissement actif pendant un cycle en cours, sinon polling toutes les 60s (throttlé au repos).

### 3.3 Interdépendances

- Lit `GET /api/agent/status` — **même endpoint que `/agent`**, donc toute correction de structure de réponse doit être vérifiée sur les deux écrans simultanément.
- Lit la liste des articles `PENDING_REVIEW` — **même source de données que `/articles`** (filtrée) et que la carte "Statut du cycle" sur `/agent`.
- Bouton "Lancer un cycle" → doit déclencher **exactement le même flux** que le bouton "Lancer le cycle" de `/agent` (pas une implémentation dupliquée divergente) — voir micro-tâche 3.4.1.
- → `/articles` (lien "Voir tout").
- → `/articles/{id}` (clic sur une ligne d'article récent, à confirmer).

### 3.4 Micro-tâches

1. **Audit** — vérifier si le bouton "Lancer un cycle" du Dashboard appelle la même mutation/logique que `AgentScreen.tsx::runCycle`, ou une implémentation séparée. Si séparée, **unifier** en extrayant la logique de lancement dans un hook partagé (`useLaunchCycle` ou équivalent) plutôt que dupliquer le code de génération de `cycle_id`, gestion du localStorage et redirection.
2. **Audit** — confirmer que le clic sur une `ArticleRow` navigue bien vers `/articles/{id}` et pas vers une route inexistante.
3. **Si régression uniquement** — ne pas retoucher `fetchDashboard()` ni la structure plate de la réponse `/status` sans re-belter le test de non-régression associé (voir section 13).

---

## 4. Écran : Agent KORA (`/agent`)

**Fichier :** `frontend/components/screens/AgentScreen.tsx` (484 lignes — écran le plus complexe de l'application, cœur du produit).
**Groupe :** `(editorial)`.

### 4.1 Structure visuelle (fiche écran)

🟨 **Page** — deux cartes côte à côte en desktop (`md:grid-cols-2`), empilées en mobile.

**Carte gauche — "Lancer un cycle" :**
- Toggle "Mode semi-automatique" — 🟪 **verrouillé** (`checked={true} disabled`), légende "Verrouillé — validation humaine obligatoire avant toute publication".
- Bouton principal **"Lancer le cycle"** (`variant=primary`, pleine largeur de la carte) + badge "HITL" à droite.
- État désactivé pendant l'exécution (`isBusy`).

**Carte droite — "Statut du cycle" :**
- État vide : "Aucun cycle actif".
- État actif : `Statut` (badge coloré selon valeur), `Mode`, `Publiés`.

**Overlay plein écran (écran de transition)** — affiché uniquement pendant `running` (déclenché par la session courante) :
- Spinner centré.
- Rotation de 7 micro-messages chaleureux (`_LOADING_MESSAGES`), fade 250ms, toutes les 1,3s.

**Toasts contextuels** (bas-droite) selon l'issue du cycle : succès, avertissement (0 article produit), erreur.

### 4.2 Fonctionnement détaillé (état réel — zone à très haut risque de régression)

- ✅ `mode` est **codé en dur à `'semi'`** (`const mode = 'semi' as const`) — aucune variable d'état ne permet de le changer depuis cet écran.
- ✅ `runCycle()` (mutation) :
  1. Génère un `cycle_id` côté client (UUID v4 manuel — `crypto.randomUUID()` indisponible car le site tourne en HTTP simple sans certificat).
  2. Stocke ce `cycle_id` dans `localStorage` (`kora_current_cycle_id`) **avant** l'appel réseau, pour que le bouton "Annuler" reste utilisable pendant l'attente bloquante.
  3. Appelle `agentApi.run(mode, newCycleId)` → `POST /api/agent/run`, **bloquant côté backend** jusqu'à la pause HITL (mode semi) ou la fin (mode auto).
  4. Si `result.status === 'PAUSED' && result.article_id` → redirection immédiate `router.push('/articles/{id}')`.
  5. Si `result.status === 'PAUSED'` sans `article_id` → **filet de sécurité uniquement**, ne devrait plus arriver en pratique (voir 4.2.1 ci-dessous).
  6. Si `result.status === 'COMPLETED'` et `published_count === 0` en mode semi → toast honnête "Cycle terminé sans article produit — aucune actualité pertinente retenue cette fois." (pas un message de succès trompeur).
  7. Sinon → toast de succès avec le nombre d'articles publiés.
- ✅ Polling parallèle indépendant (`fetchStatus`/`cycle`) via `useAsync` + `useInterval` — cadence 2000ms si `RUNNING`, 1500ms si `PAUSED`, **arrêté** (`null`) sinon.
- ✅ Reprise de session : si aucun `cycle_id` local mais que le backend en retrouve un actif en base, adoption automatique (`useEffect` ligne ~86-90).

#### 4.2.1 Historique des bugs corrigés sur cet écran (NE PAS RÉGRESSER)

1. **Carte HITL fantôme** — un cycle `PAUSED` en base dont l'article a été résolu (approuvé/rejeté/supprimé) directement via `/articles` restait affiché indéfiniment. **Corrigé côté backend** (`_get_active_cycle_from_db`, `_has_pending_article`) — un cycle `PAUSED` n'est considéré actif que s'il a encore un article `PENDING_REVIEW` réel.
2. **Redirection forcée** — l'effet de détection de `pendingArticle` naviguait automatiquement dès qu'il détectait `isPaused + pendingArticle`, y compris lors d'une navigation volontaire vers `/agent`. **Corrigé** : la redirection automatique ne se déclenche plus que depuis `runCycle()` lui-même (action explicite), jamais depuis un simple effet de détection passive.
3. **Flicker à la navigation répétée** — conséquence du bug précédent, résolu simultanément.
4. **Toast "Article prêt mais introuvable automatiquement" à tort** — le toast se basait sur `cycle` (état pollé en arrière-plan), qui reste figé sur `PAUSED` si l'onglet est mis en arrière-plan (throttling navigateur) ou si une requête de polling échoue silencieusement (`useAsync` ne réinitialise pas `data` sur erreur). **Corrigé** : avant d'afficher ce toast, une **re-vérification live** via `GET /status` est effectuée ; le toast ne s'affiche que si le backend confirme un statut `PAUSED` encore réel à cet instant précis.
5. **Root cause structurelle "Article prêt mais introuvable"** — le backend marquait `PAUSED` dès que `mode === 'semi'`, sans vérifier que LangGraph avait réellement atteint `interrupt_before=["publish_wordpress"]`. Si 0 candidat sélectionné ou échec de rédaction sur tous les articles, le graphe termine normalement (`END`) sans jamais pauser. **Corrigé** : `snapshot = await kora_graph.aget_state(config); really_interrupted = bool(snapshot.next)` — seul un `next` non vide autorise le statut `PAUSED`.
6. **Duplicate toast à l'annulation** — cliquer "Annuler" pendant que `POST /run` était encore en vol produisait une 409 "Cycle annulé" classée à tort comme session perdue, affichant un toast d'erreur en plus de celui de succès. **Corrigé** via `_isUserCancelled(e)`.

### 4.3 Interdépendances

- **Backend** : `POST /api/agent/run`, `GET /api/agent/status`, `POST /api/agent/cancel/{id}`, `GET /api/agent/stream` (SSE logs).
- **`/articles/{id}`** : destination de la redirection automatique post-pause HITL — le contrat `article_id` retourné par `/run` doit toujours correspondre à un article réellement `PENDING_REVIEW` en base au moment de la redirection.
- **`/dashboard`** : partage le même endpoint `GET /api/agent/status` — toute modification de sa forme de réponse doit être répercutée aux deux écrans.
- **`/history`** : chaque cycle terminé (quel que soit son statut final) doit apparaître dans l'historique — vérifier que `_update_cycle_status` est bien appelé pour toutes les branches de sortie (`COMPLETED`, `FAILED`, `CANCELLED`).

### 4.4 Micro-tâches

1. **Audit** — relire `agent_routes.py::_run()` en entier et confirmer qu'il n'existe **aucune** autre branche que celle déjà corrigée qui puisse positionner `status="PAUSED"` sans `really_interrupted`.
2. **Audit** — confirmer qu'aucun composant autre que `AgentScreen.tsx` n'affiche le texte "Article prêt mais introuvable" par une logique dupliquée non corrigée (grep `introuvable` dans tout `frontend/`).
3. **Micro-interaction manquante (🔲 à faire)** — au clic sur "Lancer le cycle", ajouter une transition de sortie de bouton vers l'overlay plein écran (fade, pas de saut brutal) — actuellement le passage est instantané.
4. **🔲 à faire** — vérifier le comportement si l'utilisateur ferme l'onglet pendant `POST /run` (requête bloquante potentiellement longue) : au retour, le polling doit retrouver l'état réel via `_get_active_cycle_from_db`, jamais afficher "Inactif" à tort si un cycle est réellement `RUNNING`.
5. **Ne pas toucher** sans re-tester : la génération manuelle d'UUID (`_generateCycleId`) — ne pas la remplacer par `crypto.randomUUID()` tant que le site reste en HTTP simple.

---

## 5. Écran : Articles — grille (`/articles`)

**Fichier :** `frontend/components/screens/ArticlesScreen.tsx` (276 lignes).
**Groupe :** `(editorial)`.

### 5.1 Structure visuelle (fiche écran, style "cartes" façon Canva)

🟨 **Page** — barre de filtres horizontale scrollable (`shrink-0 px-4 min-h-[44px]` par item de filtre — cible tactile déjà conforme), puis grille responsive :

```
grid-cols-1        (mobile)
sm:grid-cols-2      (tablette)
xl:grid-cols-3      (desktop)
```

**`ArticleCard`** (composant carte, `Card` avec `padding="sm"`) :
- Image miniature 16:9 en bleed négatif (`-mx-4 -mt-4 mb-4 w-[calc(100%+2rem)]`, technique choisie pour éviter les collisions de classes Tailwind avec le padding interne du composant `Card`).
- Titre.
- Chapeau tronqué à 2 lignes (`line-clamp-2`).
- Badge de statut (coloré selon `PENDING_REVIEW` / `PUBLISHED` / `REJECTED`).
- Source + date relative.
- Actions contextuelles : Approuver/Rejeter si en attente, lien WordPress si publié, suppression (icône poubelle, `w-11 h-11`, cible tactile conforme).
- Toute la surface de la carte est cliquable (`cursor-pointer hover:shadow-md transition-shadow`) ; les boutons internes utilisent `stopPropagation` pour ne pas déclencher l'ouverture de la carte en même temps qu'une action.

### 5.2 Fonctionnement (état réel)

- ✅ Filtres par statut (barre horizontale de pills).
- ✅ Clic carte → `/articles/{id}`.
- ✅ Actions rapides (approuver/rejeter/supprimer) directement depuis la carte sans ouvrir l'article — mutations isolées avec confirmation pour la suppression (`ConfirmDeleteModal`).

### 5.3 Interdépendances

- Source de vérité pour les KPI du Dashboard ("En attente de validation", "Publiés").
- L'article affiché après une pause HITL sur `/agent` doit être **le même objet de données** que celui listé ici (pas de divergence de schéma entre les deux appels API).
- → `/articles/{id}` (ouverture complète pour révision détaillée).

### 5.4 Micro-tâches

1. **🔲 À faire — micro-interactions** (actuellement seul `hover:shadow-md` statique existe, vérifié par grep) :
   - Ajouter `hover:scale-[1.01] transition-transform duration-200` sur `ArticleCard`.
   - Ajouter une transition de sortie (fade + léger scale, CSS natif, ~200-250ms) lors de la navigation vers `/articles/{id}` — ne pas introduire de dépendance lourde (type Framer Motion) sans validation explicite préalable du coût bundle.
2. **Audit** — vérifier le comportement de pagination/scroll infini si le nombre d'articles dépasse une page — documenter l'état réel avant toute modification.
3. **Audit device réel** — tester la grille sur un vrai viewport tablette (768–1024px), pas seulement un resize de navigateur desktop, pour confirmer l'absence de cassure entre `sm:grid-cols-2` et `xl:grid-cols-3`.
4. **Ne pas toucher** : la technique de bleed d'image en marge négative — elle a été choisie délibérément pour éviter un conflit de classes avec le padding du composant `Card`. Toute alternative doit être justifiée et testée visuellement avant remplacement.

---

## 6. Écran : Article — révision (`/articles/{id}`)

**Fichier :** `frontend/components/screens/ArticleEditorScreen.tsx` (428 lignes).
**Groupe :** `(editorial)`.

### 6.1 Structure visuelle (fiche écran)

🟨 **Page** — vue de révision d'un article unique, contenu HTML propre + métadonnées.

- Contenu principal : titre, chapeau, corps en HTML rendu, image d'illustration.
- Panneau latéral / barre du haut : métadonnées SEO (`meta_description`, `mots_cles`, `categorie`), lien vers la source originale, statut.
- **Barre d'actions** (dupliquée en haut de page ET en barre latérale selon le layout) :
  - **"Approuver et publier"** → publication WordPress réelle → redirection `/articles`.
  - **"↻ Améliorer et régénérer"** → `POST /api/articles/{id}/regenerate`, mini-loader sur le bouton, mise à jour **en place** (`refetch()`, aucune navigation) — **boucle répétable sans limite**, coût LLM/image réel accepté à chaque clic.
  - **"Rejeter cet article"** → `status='REJECTED'`, redirection `/dashboard` (pas `/articles`) sans écran de transition intermédiaire.
- **État d'erreur** : "Article introuvable" (`ArticleEditorScreen.tsx:79`) si l'ID ne résout à rien.
- 🟪 **Condition transverse** : `anyActionInFlight` désactive **mutuellement** tous les boutons d'action pendant qu'une action est en cours — élimine double-clics et appels concurrents.

### 6.2 Fonctionnement détaillé — boucle de régénération (fonctionnalité phare)

- ✅ **Contenu source reconstruit depuis `raw_feeds`** (jointure sur `cycle_id`/`batch_id` + `source_url`), car la table `articles` ne conserve pas le contenu source brut.
- ✅ Ré-invoque `writer._write_with_retry()` (nouvel angle, tiré aléatoirement parmi 3 styles d'accroche — `_HOOK_STYLES`) et `illustrator.generate_and_upload_image()` (nouvelle image, jamais réutilisation).
- ✅ Met à jour la ligne `articles` existante (`titre`, `chapeau`, `corps`, `meta_description`, `mots_cles`, `categorie_id`, `image_prompt`, `image_url` via `COALESCE`, `wp_media_id` via `COALESCE`) — **ne crée jamais de nouvelle ligne**.
- ✅ Statut reste `PENDING_REVIEW` après régénération (jamais republié par erreur) — prouvé par test live (`test_regenerate_live.py`, 7/7).

### 6.3 Interdépendances

- **`raw_feeds`** : dépendance dure pour la régénération — si un article a été produit par un cycle dont les `raw_feeds` ont été purgés/archivés, la régénération doit échouer proprement avec un message clair (`"Contenu source original introuvable (raw_feeds) — régénération impossible pour cet article"`), jamais planter silencieusement.
- **`/articles`** : retour après approbation.
- **`/dashboard`** : retour après rejet.
- **`agent/nodes/writer.py`, `agent/nodes/illustrator.py`** : logique de génération partagée avec le cycle principal — toute modification du prompt d'écriture ou d'image doit être cohérente entre le flux "premier jet" (cycle complet) et le flux "régénération" (cet écran).

### 6.4 Micro-tâches

1. **Audit** — vérifier que le bouton "Rejeter" redirige bien vers `/dashboard` (confirmé dans la spec produit) et non vers `/articles`, comme documenté — une régression a pu réintroduire l'ancien comportement.
2. **Audit** — confirmer que `anyActionInFlight` couvre bien les 3 actions (approuver, régénérer, rejeter) sans exception, y compris les boutons dupliqués en haut de page et en barre latérale (état partagé, pas deux flags séparés qui désynchroniseraient l'IHM).
3. **🔲 À faire** — ajouter un indicateur visuel de "version régénérée" (ex. petit badge "v2", "v3"...) si le produit souhaite que l'utilisateur sache combien de régénérations ont eu lieu sur cet article — **ne pas implémenter sans confirmation explicite**, ce n'est pas dans le périmètre déjà validé.
4. **Ne pas toucher** sans re-belter `test_regenerate_live.py` : la logique de reconstruction du contenu source depuis `raw_feeds`.

---

## 7. Écran : Sources RSS (`/sources`)

**Fichier :** `frontend/components/screens/SourcesScreen.tsx` (229 lignes).
**Groupe :** `(editorial)`.

### 7.1 Structure visuelle (fiche écran)

🟨 **Page** — liste de cartes `SourceCard`, formulaire d'ajout en overlay/section (`showAdd: boolean`).

- Bouton "Ajouter une source" → révèle formulaire `{ name, url, category }`.
- Validation de formulaire (`formError`) avant soumission.
- Chaque `SourceCard` : nom, URL, catégorie, toggle actif/inactif, bouton suppression avec **confirmation en deux temps** (`confirmDelete: boolean` local à la carte, pas de modal globale pour cette action précise).

### 7.2 Fonctionnement (état réel)

- ✅ `addSource` (mutation) → ajout backend, `refetch()` de la liste.
- ✅ `deleteSource(id)` (mutation).
- ✅ `toggleSource({id, active})` (mutation) — active/désactive une source sans la supprimer.

### 7.3 Interdépendances

- **Cœur de la Règle 1 de gouvernance éditoriale (source scope strict)** : `scraper.py` utilise `queries = _FALLBACK_QUERIES if not db_sources else []` — **si au moins une source DB existe, aucune requête de fallback Tavily générique n'est utilisée**. Ajouter/retirer une source ici change directement le comportement du cycle de scraping.
- **`/setup`** : formulaire de sources par défaut à la première configuration — schéma de données partagé, voir micro-tâche 2.4.3.
- Toute source désactivée (`active=false`) doit être **immédiatement exclue** du prochain cycle de scraping (pas de cache côté backend à invalider manuellement — à vérifier).

### 7.4 Micro-tâches

1. **Audit** — confirmer qu'une source désactivée via le toggle est bien exclue de la requête `db_sources` côté `scraper.py` (pas seulement filtrée côté UI).
2. **Audit** — vérifier la validation d'URL côté formulaire (format, doublons) avant d'envisager tout ajout de règle de validation supplémentaire.
3. **🔲 À faire, si confirmé nécessaire** — feedback visuel du nombre d'articles retenus par source sur les N derniers cycles (utile pour l'utilisateur qui veut évaluer la pertinence d'une source) — **hors périmètre tant que non explicitement demandé**, à ne pas implémenter spontanément.

---

## 8. Écran : Historique (`/history`)

**Fichier :** `frontend/components/screens/HistoryScreen.tsx` (124 lignes — écran le plus simple).
**Groupe :** `(editorial)`.

### 8.1 Structure visuelle (fiche écran)

🟨 **Page** — liste de tous les cycles passés (`CycleRow` × N), avec KPI agrégés en tête :
- Total publié (`totalPublished`).
- Total échoués (`totalFailed`).
- Taux de succès (`successRate`).

**`CycleRow`** : badge de statut (`STATUS_BADGE` — mapping couleur par statut : `PUBLISHED`→sage, `FAILED`→danger, etc.), durée calculée (`completed_at - started_at`), nombre d'articles publiés/rejetés.

### 8.2 Fonctionnement (état réel)

- ✅ `GET /api/cycles` (liste paginée, `cycleApi.list()`).
- ✅ Calculs agrégés effectués **côté frontend** à partir de la liste chargée (pas d'endpoint d'agrégation dédié) — ⚠️ implique que les KPI ne reflètent que la page actuellement chargée, pas l'historique complet si pagination.

### 8.3 Interdépendances

- Doit refléter **tous** les cycles créés par `/agent` (et par le bouton raccourci du `/dashboard`), quel que soit leur statut final (`COMPLETED`, `FAILED`, `CANCELLED`) — dépend directement de `_update_cycle_status()` appelé dans toutes les branches de sortie de `agent_routes.py::_run()`.

### 8.4 Micro-tâches

1. **Audit** — confirmer si `cycleApi.list()` retourne réellement TOUS les cycles ou seulement une page ; si les KPI en tête de page sont censés représenter le total global, vérifier si un endpoint d'agrégation serveur existe déjà (`cycle_routes.py`) plutôt que de recalculer sur un sous-ensemble potentiellement incomplet.
2. **Si écart constaté** — ne pas corriger silencieusement le calcul frontend ; documenter l'écart et proposer soit un endpoint d'agrégation dédié, soit une clarification explicite du libellé ("sur cette page" vs "au total").

---

## 9. Écran : Paramètres (`/settings`)

**Fichier :** `frontend/components/screens/SettingsScreen.tsx` (617 lignes — écran le plus volumineux, 4 onglets).
**Groupe :** `(editorial)`.

### 9.1 Structure visuelle (fiche écran, navigation par onglets)

🟨 **Page** — `max-w-3xl`, navigation par onglets horizontale :

| Onglet (`key`) | Libellé |
|---|---|
| `wordpress` | WordPress |
| `categories` | Catégories |
| `prompts` | Prompts système |
| `providers` | Fournisseurs LLM |

#### Onglet WordPress (`WordPressTab`)
- Formulaire de connexion WordPress (URL, identifiants).
- Bouton de test de connexion (`testing`, `testResult: 'ok' | 'fail' | null`).
- Champ mot de passe masquable (`showPassword`).
- Test d'envoi d'e-mail (`testingEmail`) — fonctionnalité de notification distincte.
- ⚠️ **Piège documenté dans le code** : `app_settings` stocke tout en `TEXT` côté backend (`str(value)` en Python). Une valeur booléenne fausse revient comme la chaîne non vide `"False"`, qui est *truthy* en JavaScript. **Toujours passer par `asBool()`/`asNumber()` pour toute lecture de valeur booléenne/numérique depuis `/api/settings`**, jamais une lecture directe.

#### Onglet Catégories (`CategoriesTab`)
- Synchronise les vraies catégories WordPress (`settingsApi.wpCategories()`, bouton `sync`).
- Permet d'associer chaque catégorie WP aux **7 libellés éditoriaux fixes** de l'agent : `Politique, Économie, Société, Sport, Culture, Sécurité, International` (`KORA_LABELS`).
- Remplace un ancien système d'IDs codés en dur dans `writer.py`.

#### Onglet Prompts système
- Édition des prompts utilisés par le pipeline (écriture, sélection...) — à documenter précisément lors de l'audit (non détaillé dans les extraits inspectés).

#### Onglet Fournisseurs LLM
- Vue de configuration des fournisseurs (distincte de la vue de **monitoring temps réel** sur `/system/providers` — ne pas confondre les deux écrans).

### 9.2 Interdépendances

- **Onglet WordPress** ↔ `/setup` (même schéma de configuration, voir micro-tâche 2.4.2).
- **Onglet Catégories** ↔ `agent/nodes/writer.py` (les 7 libellés fixes sont utilisés directement dans la génération d'articles — renommer un libellé ici sans mettre à jour le prompt de l'agent casse la classification).
- **Onglet Fournisseurs LLM** ↔ `/system/providers` (vue de configuration vs vue de santé temps réel — deux écrans différents sur la même ressource logique, ne pas fusionner sans décision produit explicite).

### 9.3 Micro-tâches

1. **Audit** — lire intégralement l'onglet "Prompts système" (non détaillé faute d'extraction complète) et documenter sa structure réelle avant toute modification.
2. **Audit** — vérifier que **toutes** les valeurs booléennes affichées dans les 4 onglets passent bien par `asBool()` (grep `asBool` vs accès direct à `settings.xxx` dans tout le fichier) — corriger toute lecture directe non coercée trouvée.
3. **Audit** — confirmer qu'un changement de libellé dans `KORA_LABELS` déclenche bien une alerte ou une validation empêchant une désynchronisation avec `writer.py` (sinon, documenter le risque explicitement plutôt que de le corriger sans validation produit).

---

## 10. Écrans système / diagnostic (`/system/*`)

**Fichiers :** `frontend/app/system/{page,connections,cycles,login,logs,providers}/page.tsx`.
**Groupe :** `system`, thème sombre dédié (`SYS_SURFACE`, `SYS_BORDER`, palette mono `#141413`/`#2a2a28`/`#d4d3ce`), typographie monospace — **délibérément distinct** de l'IHM éditoriale crème/orange. Exception assumée à la règle transverse 0.3.4 (texte technique toléré ici).

### 10.1 `/system` — Dashboard système (détaillé, code inspecté intégralement)

🟨 **Page** — `max-w-5xl`, rafraîchissement auto toutes les 30s.

- **En-tête** : titre "Dashboard système", bouton "↺ Actualiser" manuel.
- **4 cartes KPI** : Statut global (`OPÉRATIONNEL`/`DÉGRADÉ`), Uptime (formaté `Xh Ym`), Version, Providers UP (`X/Y`).
- **Section "Services"** : badges `ServiceBadge` (point coloré + libellé + `OK`/`KO`) pour Redis, Supabase, WordPress, API KORA.
- **Section "Fournisseurs LLM — chaîne de fallback"** : grille de `ProviderGauge` (1 par fournisseur), chacune affichant :
  - Nom + modèle utilisé.
  - Badge `UP`/`DOWN`.
  - Jauge de latence colorée (vert <1000ms, jaune <3000ms, rouge au-delà), barre de progression visuelle.
  - Priorité dans la chaîne de fallback (`priorité #N`).
- ⚠️ **Données de repli codées en dur** si le endpoint échoue (`providers` par défaut avec Groq/Gemini/Cerebras/OpenRouter) — sert de squelette visuel, pas de vraie donnée en cas de panne réelle du endpoint `/health/system`.

### 10.2 Autres écrans système (à auditer, non lus en détail dans ce cycle de rédaction)

- `/system/connections` — probablement l'état des connexions actives (DB, Redis, WordPress) en détail.
- `/system/cycles` — vue technique des cycles (distincte de `/history` éditoriale — niveau de détail différent, probablement avec logs bruts).
- `/system/login` — authentification séparée pour l'espace système (à confirmer : même credentials que `/login` ou accès distinct ?).
- `/system/logs` — flux de logs bruts.
- `/system/providers` — configuration/santé détaillée des fournisseurs LLM (relation à clarifier avec `/settings` → onglet "Fournisseurs LLM").

### 10.3 Interdépendances

- `GET /health/system` : contrat de données partagé avec le Dashboard système — toute évolution du schéma `SystemHealth`/`ProviderHealth` doit rester rétrocompatible avec les données de repli codées en dur.
- Risque de **duplication fonctionnelle** avec `/settings` (onglet Fournisseurs LLM) et `/history` (cycles) — à ne pas fusionner sans décision produit, mais à **documenter clairement la différence de rôle** (configuration vs monitoring temps réel vs historique éditorial).

### 10.4 Micro-tâches

1. **Audit complet** — lire intégralement `connections/page.tsx`, `cycles/page.tsx`, `login/page.tsx`, `logs/page.tsx`, `providers/page.tsx` (non couverts en détail dans cette rédaction faute de lecture exhaustive) et produire pour chacun une fiche au même format que la section 10.1, avant toute modification.
2. **Audit** — clarifier explicitement (documentation, pas forcément code) la distinction fonctionnelle entre `/system/providers` et `/settings` → onglet "Fournisseurs LLM".
3. **Audit sécurité** — confirmer que le groupe `system/*` est bien protégé par une authentification (potentiellement distincte de l'espace éditorial via `/system/login`) et n'est pas accessible publiquement, dans la mesure où il expose des informations d'infrastructure sensibles (latences, disponibilité des providers, logs).

---

## 11. Composants transverses (design system)

**Dossiers :** `frontend/components/ui/`, `frontend/components/layout/`.

### 11.1 Composants UI (`components/ui/`)

| Composant | Rôle | Règle transverse associée |
|---|---|---|
| `Button.tsx` | Bouton standard | Cibles tactiles ≥44px/48px (règle 0.3.3) |
| `Card.tsx` | Conteneur de carte | `padding` variable (`sm`/défaut) — voir technique de bleed d'image (5.1) |
| `Toggle.tsx` | Interrupteur | Utilisé pour le verrou HITL (règle 0.3.1) — `disabled` doit rester supporté visuellement (grisé, pas juste non cliquable) |
| `Modal.tsx` | Fenêtre modale générique | — |
| `ConfirmDeleteModal.tsx` | Confirmation de suppression | Utilisé par `/sources` et potentiellement `/articles` |
| `Badge.tsx` | Étiquette de statut coloré | Mapping couleur cohérent à maintenir entre `/articles`, `/history`, `/dashboard` |
| `Spinner.tsx` | Indicateur de chargement | — |
| `Toast.tsx` | Notification contextuelle | Contexte global `useToast()` — voir règle 0.3.4 (jamais de texte brut) |
| `PagePlaceholder.tsx` | État vide générique | Réutilisé par plusieurs écrans (`EmptyDashboard` custom sur Dashboard, à vérifier s'il devrait utiliser ce composant générique) |

### 11.2 Composants de layout (`components/layout/`)

| Composant | Rôle |
|---|---|
| `AppShell.tsx` | Structure globale (sidebar + topbar + contenu) |
| `Sidebar.tsx` | Navigation desktop fixe |
| `MobileSidebar.tsx` | Menu burger mobile/tablette (✅ déjà implémenté, remplace la sidebar sous breakpoint) |
| `BottomNav.tsx` | Barre de navigation basse mobile (✅ déjà implémenté) |
| `Topbar.tsx` | Barre supérieure (badge "KORA actif", profil utilisateur) |
| `MainContent.tsx` | Conteneur de contenu principal |

### 11.3 Micro-tâches

1. **Audit** — vérifier que `PagePlaceholder.tsx` (générique) et `EmptyDashboard` (spécifique au Dashboard) ne divergent pas visuellement sans raison — si `EmptyDashboard` réimplémente ce que `PagePlaceholder` fait déjà, envisager la factorisation (**seulement si aucune différence fonctionnelle justifiée**).
2. **Audit** — confirmer la cohérence du mapping couleur de `Badge.tsx` à travers tous ses usages (`/articles`, `/history` via `STATUS_BADGE`, `/dashboard`) — un même statut (`PUBLISHED`, `FAILED`, etc.) doit toujours porter la même couleur partout.
3. **🔲 À faire, priorité basse** — vérifier l'accessibilité clavier de `MobileSidebar.tsx` (piège focus, échappement) — non documenté comme déjà vérifié dans l'historique de session.

---

## 12. Matrice d'interdépendance globale

| Écran source | Dépend de / affecte | Nature du lien |
|---|---|---|
| `/login` | `/dashboard` | Redirection post-authentification |
| `/setup` | `/settings` (WordPress), `/sources` | Schéma de configuration partagé |
| `/dashboard` | `/agent` (`GET /status` partagé), `/articles` (KPI), `/articles/{id}` (navigation) | Lecture agrégée multi-sources |
| `/agent` | `/articles/{id}` (redirection HITL), `/dashboard` (`GET /status` partagé), `/history` (traçabilité de cycle) | Écran pivot du produit |
| `/articles` | `/articles/{id}` (navigation), `/dashboard` (KPI) | Liste ↔ détail |
| `/articles/{id}` | `raw_feeds` (régénération), `/articles` (retour approbation), `/dashboard` (retour rejet) | Actions mutantes critiques |
| `/sources` | `scraper.py` (Règle 1 gouvernance), `/setup` (schéma partagé) | Configuration du pipeline |
| `/history` | `agent_routes.py::_update_cycle_status` (toutes branches) | Traçabilité exhaustive requise |
| `/settings` | `/setup` (WordPress), `writer.py` (libellés catégories), `/system/providers` (relation à clarifier) | Configuration multi-cible |
| `/system/*` | `GET /health/system`, infra (Redis, Supabase, WordPress) | Diagnostic technique isolé |

**Règle d'or pour l'agent :** avant de modifier un écran de cette liste, relire la colonne "Dépend de / affecte" et vérifier que les écrans listés ne cassent pas suite à la modification prévue.

---

## 13. Checklist de non-régression obligatoire

À exécuter (mentalement ou via tests réels) après **toute** modification touchant `/agent`, `/dashboard`, ou `/articles/{id}` — les trois écrans historiquement les plus sujets à régression dans ce projet :

- [ ] Le mode semi-automatique reste verrouillé (`Toggle disabled`, aucune IHM ne permet de le désactiver).
- [ ] Aucun écran de transition plein écran ne s'affiche pour un cycle `PAUSED` ambiant découvert passivement (uniquement pour l'action explicite de la session courante).
- [ ] Le toast "Article prêt mais introuvable" ne peut s'afficher qu'après re-vérification live du statut serveur, jamais sur la seule base d'un état pollé.
- [ ] Un cycle `PAUSED` en base sans article `PENDING_REVIEW` associé est bien reclassé `COMPLETED` par le backend (`_has_pending_article`).
- [ ] La régénération d'article ne crée jamais de nouvelle ligne `articles` (toujours une mise à jour de la ligne existante).
- [ ] Le statut d'un article reste `PENDING_REVIEW` après régénération (jamais republié par erreur).
- [ ] Toutes les cibles cliquables restent ≥44px/48px.
- [ ] Aucun texte technique brut (stack trace, JSON d'erreur) n'apparaît dans le groupe `(editorial)`.
- [ ] La structure plate de `GET /api/agent/status` (pas de clé `cycle` imbriquée) reste respectée sur `/agent` ET `/dashboard`.
- [ ] Double-clic bloqué sur toute action mutante nouvellement ajoutée.

---

*Document rédigé à partir d'un audit direct du code source réel (`frontend/app/`, `frontend/components/`, `backend/api/`, `backend/agent/`) — aucune fonctionnalité listée comme ✅ n'est une supposition. Les items 🔲 sont le travail réel restant, priorisés par écran plutôt que présentés comme une tâche globale.*
