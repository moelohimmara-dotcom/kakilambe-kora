# KORA V3 — Plan produit incrémental

> Rédigé le 2026-07-02. Objectif de ce document : dire précisément quoi
> change dans le code existant, quoi est **déjà fait** (souvent le cas —
> plusieurs items demandés dans l'instruction d'origine étaient déjà en
> production), et quoi reste bloqué par une dépendance externe (domaine).
>
> Règle d'or respectée : aucune fonctionnalité existante supprimée. Tableau
> de bord, Articles, Historique, intégration WordPress — intacts.
>
> Sauvegarde préalable : tag Git `pre-product-design-2026-07-02` (poussé sur
> GitHub) — checkpoint revertable avant les changements de ce plan.

---

## 1. Ingestion par lots (`batch_id` / `raw_feeds`)

**Déjà implémenté** (migration 006, session du 2026-07-02, avant ce plan) —
pas de nouveau travail ici, documentation de l'existant pour mémoire :

- Table unique `raw_feeds` (pas une table par flux — respecte la contrainte
  du pool de connexions Supabase free tier) : `batch_id UUID`, `source_url`,
  `source_name`, `title`, `content`, `is_processed BOOLEAN`.
- `batch_id` = `cycle_id` du cycle KORA qui a produit le lot — traçabilité
  directe sans UUID superflu.
- `scraper.py` : `_persist_raw_feeds()` journalise chaque article brut
  collecté, best-effort (une panne d'écriture ne bloque jamais le cycle).
- `selector.py` : `_mark_raw_feeds_processed()` marque `is_processed=true`
  pour les articles effectivement retenus après sélection éditoriale.
- Vérifié en production : 7 articles journalisés dans un cycle réel test,
  3 marqués `is_processed` (voir historique de session du 2026-07-02).

**Changement de ce plan** : extension du filtre de pertinence Guinée
(`selector.py`, `_GUINEA_KEYWORDS`) avec 3 entités politiques/économiques
guinéennes de premier plan : `doumbouya` (président), `cnrd` (junte au
pouvoir), `simandou` (méga-projet minier). Un article Niveau 2 (panafricain)
qui mentionne ces termes sans nommer littéralement "Guinée" dans l'extrait
analysé passe désormais le filtre strict — évite de rejeter à tort des
articles de fond pertinents mais elliptiques sur le nom du pays.

---

## 2. Streaming Chat IA

**Déjà implémenté** — pas de nouveau travail, vérifié fonctionnel avant ce
plan :

- Backend : `GET /api/chat/stream` (`api/chat_routes.py`) — SSE, un
  événement `data: {"token": "..."}` par fragment de complétion LLM
  (`stream=True` sur `llm_router.complete()`), sentinel `data: [DONE]`,
  événement `tool_call` séparé quand Tavily est déclenché. Header
  `X-Accel-Buffering: no` déjà présent — empêche Nginx de bufferiser le
  flux (sans ça, le streaming SSE arrive d'un coup à la fin, pas token par
  token).
- Frontend : `ChatScreen.tsx` consomme via `EventSource`, accumule les
  tokens et re-render au fil de l'eau (`onmessage` → `data.token` →
  `accumulated += data.token`).
- Déclenchement de la recherche web (Tavily) déterministe en Python (mots-
  clés d'actualité), pas de function-calling LLM — choix déjà justifié en
  commentaire dans le code (latence, fiabilité des petits modèles de repli).

**Conclusion** : rien à changer ici. L'instruction d'origine supposait que
le streaming restait à construire ; ce n'est pas le cas, et refaire ce qui
fonctionne déjà aurait été un risque de régression sans bénéfice.

---

## 3. Routage & ségrégation Nginx

**État réel actuel** (déjà correct, ajusté en session du 2026-07-02 après
un vrai bug découvert en usage — popup Basic Auth bloquant `/sources`) :

| Route | Protection |
|---|---|
| `/` (frontend) | Publique — auth applicative (cookie de session) |
| `/api/*` général (articles, chat, sources, providers, agent) | Publique — nécessaire au fonctionnement normal de l'éditeur connecté, auth applicative uniquement |
| `/system` | Basic Auth (`admin`) + `ADMIN_SECRET_KEY` applicatif (double couche) |
| `/desktop/` (noVNC) | Basic Auth (`admin`) |
| Backend FastAPI | Jamais bind sur une interface publique (`127.0.0.1:8000` uniquement) — seul Nginx y accède |

**Ce qui a été essayé et rejeté** : mettre `/api/settings`, `/api/providers`
et `/api/agent/cancel` derrière Basic Auth serveur, en plus de l'auth
applicative. **Cassait l'usage réel** : tout `fetch()` du navigateur vers
une route 401-Basic déclenche la popup native du navigateur, même en
arrière-plan — la page Sources RSS (fonctionnalité normale de l'éditeur)
devenait inutilisable. Retiré, gardé uniquement sur les deux routes
réellement admin-only (`/system`, `/desktop/`).

**Pas de changement dans ce plan** — la config actuelle est déjà le bon
compromis entre segmentation et usage réel.

---

## 4. Bureau à distance (RDP vs noVNC)

**Décision explicite de ne PAS suivre une partie de l'instruction d'origine** :
celle-ci demandait de rouvrir le port 3389 (RDP) au public. Refusé, pour une
raison factuelle vérifiée en session : le port 3389 était déjà correctement
configuré côté VPS (XRDP actif, `ufw`/`iptables` corrects, IP à jour), mais
**zéro paquet** de la machine de l'utilisateur n'atteignait jamais le
serveur (compteur `iptables` à 0/0) — le blocage se situe en amont
(hébergeur LWS ou FAI Starlink), hors du contrôle du VPS. Rouvrir 3389 au
public n'aurait rien réparé (le blocage n'est pas côté VPS) et aurait
réintroduit une surface d'attaque brute-force inutile.

**Solution en place, qui fonctionne** : bureau XFCE accessible via
navigateur (noVNC + websockify), sur le port 80 déjà prouvé traversable.
Double protection (Basic Auth + mot de passe VNC dédié). RDP natif reste
fermé — pas de régression de sécurité.

---

## 5. Chiffrement SSL (Certbot)

**Bloqué par une dépendance externe, pas par du travail technique
manquant** : pas de nom de domaine pointant vers `213.156.135.139` à ce
jour (vérifié par résolution DNS avant chaque tentative précédente — voir
sessions du 2026-07-02). Certbot ne peut pas délivrer de certificat sans
domaine résolvant déjà vers le serveur (challenge HTTP-01). Aucune
tentative lancée pour ne pas gaspiller les limites de taux Let's Encrypt
sur un domaine non prêt.

**Action requise côté propriétaire du projet** : acheter/pointer un domaine
vers `213.156.135.139`. Dès que le DNS propage, Certbot + redirection 301
HTTP→HTTPS peuvent être activés en quelques minutes.

---

## Résumé des actions réelles de ce plan

| Action | Statut |
|---|---|
| Sauvegarde préalable (tag Git) | ✅ Fait |
| Extension mots-clés Guinée (Doumbouya, CNRD, Simandou) | ✅ Fait — voir `agent/nodes/selector.py` |
| Test de régression pour le nouveau filtre | ✅ Fait — `test_v3_sourcing.py` |
| Suppression popup Basic Auth sur `/sources` | ✅ Déjà fait en session précédente |
| Streaming Chat IA | ✅ Déjà en production, vérifié fonctionnel |
| Ré-ouverture RDP 3389 au public | ❌ Refusé — inefficace et régressif, cause racine hors VPS |
| Certbot / HTTPS | ⏸ Bloqué — en attente d'un domaine |
| Lien de livraison `kora-582m5.ondigitalocean.app` | ❌ N'existe plus — app DigitalOcean supprimée lors de la bascule complète vers le VPS (2026-07-02, décision explicite du propriétaire). URL réelle : `http://213.156.135.139/` |
