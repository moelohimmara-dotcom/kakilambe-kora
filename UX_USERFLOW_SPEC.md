# KORA V3 — Spécification du userflow (refonte UX)

Documente l'état réel du parcours utilisateur après la refonte, tel qu'implémenté et déployé — pas un plan aspirationnel. Grammaire : 🟨 Page · 🟦 Action · 🟪 Condition.

---

## Phase A — Commandement et attention

🟨 **Dashboard Agent (`/agent`)** — écran de commande épuré, un seul bouton d'action principal ("Lancer le cycle"), mode semi-automatique verrouillé (non désactivable depuis l'IHM). Grille `md:grid-cols-2` : empilé en une colonne sur mobile/tablette, côte-à-côte à partir du breakpoint desktop.

🟦 **Clic "Lancer le cycle"** → `runCycle()` génère un `cycle_id` côté client, verrouille le bouton (`isBusy`), affiche l'écran de transition.

🟨 **Écran de transition** — overlay plein écran, spinner + rotation de 7 micro-messages chaleureux (fade 250ms, toutes les 1,3s) tant que le cycle est `RUNNING`. Représente uniquement le travail actif de la session en cours — jamais affiché pour un cycle `PAUSED` découvert passivement (cf. bug corrigé : voir Notes de résilience).

---

## Phase B — Routage automatique et boucle de régénération

🟪 **Condition : pause HITL atteinte côté backend ?**
- *Non (échec)* → toast d'erreur, retour à l'état `idle`, aucun écran technique qui reste affiché.
- *Oui* → 🟦 **Redirection automatique** vers `/articles/{id}` dès réception de la réponse de `POST /api/agent/run` (bloquant côté serveur jusqu'à ce point précis, `article_id` inclus dans la réponse).

🟨 **Écran de révision (`/articles/{id}`)** — article en HTML propre, image, méta SEO, source originale.

🟪 **Condition : l'utilisateur est-il satisfait ?**
- **Branche 1 — Oui (`Approuver et publier`)** : 🟦 publication WordPress réelle → redirection vers `/articles`.
- **Branche 2 — Non (`↻ Améliorer et régénérer`)** : 🟦 `POST /api/articles/{id}/regenerate` — réécriture complète (nouvel angle d'accroche tiré aléatoirement parmi 3 styles, nouvelle image générée) à partir du contenu source d'origine reconstruit depuis `raw_feeds`. Mini-loader sur le bouton, la page se met à jour **en place** (`refetch()`, pas de navigation). **Boucle répétable sans limite** — chaque clic est un appel LLM + génération d'image réel (coût accepté explicitement).
- **Branche 3 — Rejet (`Rejeter cet article`)** : 🟦 `status='REJECTED'` en base, redirection vers `/dashboard` sans écran de transition intermédiaire.

Tous les boutons d'action de cette page se désactivent mutuellement pendant qu'une action est en vol (`anyActionInFlight`) — élimine les doubles-clics et les appels concurrents.

---

## Phase C — Flux des articles

🟨 **Page Articles (`/articles`)** — grille de cartes (1 colonne mobile, 2 tablette, 3 desktop), pas une liste de liens. Chaque carte : miniature 16:9 en tête, titre, chapeau tronqué à 2 lignes (`line-clamp-2`), badge de statut, source + date relative, actions contextuelles (Approuver/Rejeter si en attente, lien WordPress si publié, suppression).

🟦 **Clic sur une carte** → toute la surface de la carte est cliquable et ouvre `/articles/{id}` ; les boutons d'action internes stoppent la propagation (`stopPropagation`) pour ne pas déclencher l'ouverture en même temps qu'une action.

---

## Design system appliqué

- **Cibles tactiles** : tous les boutons ont une hauteur minimale de 44px (`sm`/`md`) ou 48px (`lg`) — corrigé, le composant `Button` ne respectait pas ce seuil sur `sm` (≈31px) avant cette refonte.
- **Feedback instantané** : chaque action verrouille son bouton (`loading`/`disabled`) avant l'appel réseau, jamais après.
- **Aucune superposition d'écrans** : l'overlay de transition ne peut apparaître que pour le travail actif de la session courante (voir Notes de résilience ci-dessous) — jamais pour un état ambiant découvert en arrière-plan.

---

## Suppression du Chat IA

Retiré intégralement à la demande explicite : page (`app/(editorial)/chat`), composant (`ChatScreen.tsx`, `components/chat/`), entrées de navigation (Sidebar, BottomNav, MobileSidebar), et le client API frontend (`chatApi` dans `lib/api.ts`). Les routes backend (`/api/chat/*`) n'ont pas été supprimées — aucun frontend ne les appelle plus, mais leur suppression n'était pas dans le périmètre demandé (uniquement "l'onglet"/l'espace applicatif).

---

## Notes de résilience (bugs réels corrigés dans les itérations précédentes, toujours valables)

- L'écran de transition ne se déclenche plus jamais pour un cycle `PAUSED` ambiant (ex. article laissé en attente d'une session précédente) — seule une bannière passive avec lien informe l'utilisateur, sans navigation forcée ni clignotement au retour sur `/agent`.
- Le bouton "Lancer le cycle" n'est bloqué que par un cycle actif de la session courante — jamais par un cycle `PAUSED` distinct, qui n'empêche pas d'en lancer un nouveau en parallèle (le backend supporte nativement plusieurs cycles concurrents, chacun avec son propre `thread_id` LangGraph).
