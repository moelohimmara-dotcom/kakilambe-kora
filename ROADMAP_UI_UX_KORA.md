# ROADMAP UI/UX — KORA V3

Feuille de route de la refonte visuelle, structurée en 4 piliers. Chaque item est marqué **✅ Fait** (déjà en production, avec référence de fichier) ou **🔲 À faire** (travail réel restant). Grammaire des parcours : 🟨 Page · 🟦 Action · 🟪 Condition.

Objectif : rendre KORA invisible en tant que technologie — un parcours rapide, scannable, sans bruit technique, au niveau des standards Claude/Canva/SaaS modernes.

---

## PILIER I — Épuration radicale & suppression du bruit

- ✅ **Fait** — Chat IA retiré intégralement (page, composant, nav, client API). Voir [UX_USERFLOW_SPEC.md](UX_USERFLOW_SPEC.md#suppression-du-chat-ia).
- ✅ **Fait** — Messages d'erreur bruts remplacés par des toasts contextuels en français clair (`AgentScreen.tsx`, `ArticleEditorScreen.tsx`) — plus de stack traces ni de JSON exposé à l'utilisateur.
- ✅ **Fait** — Écran `/agent` réduit à une seule action principale ("Lancer le cycle") + statut, sans logs techniques visibles par défaut.
- 🔲 **À faire** — Audit exhaustif de toutes les pages secondaires (`Historique`, `Sources RSS`, `Paramètres`) pour vérifier qu'aucun message d'erreur brut de l'API (ex. `detail` FastAPI non traduit) ne fuite tel quel dans l'IHM.

🟨 Pages concernées : toutes · 🟪 Condition : aucun texte technique (nom de fonction, stack trace, code HTTP brut) ne doit atteindre l'utilisateur final sans reformulation.

---

## PILIER II — Responsive Design Intelligent

- ✅ **Fait** — Menu burger mobile/tablette (`components/layout/MobileSidebar.tsx`) + barre de navigation basse (`BottomNav.tsx`) remplaçant la sidebar fixe sous le breakpoint desktop.
- ✅ **Fait** — Cibles tactiles ≥44px (sm/md) / 48px (lg) sur tous les boutons (`components/ui/Button.tsx`).
- ✅ **Fait** — Grille Articles responsive `grid-cols-1 sm:grid-cols-2 xl:grid-cols-3` (empilement mobile → grille desktop).
- ✅ **Fait** — Dashboard Agent en `md:grid-cols-2` (empilé mobile, côte-à-côte desktop).
- 🔲 **À faire** — Audit des espaces négatifs desktop (marges, alignement en grille asymétrique) sur `Dashboard` et `Historique` — actuellement fonctionnel mais pas encore optimisé visuellement pour la loi de Fitts (regroupement des actions fréquentes à portée de clic).
- 🔲 **À faire** — Vérification tablette (768–1024px) spécifique : les breakpoints actuels sautent de `sm` à `xl` sur Articles, un état intermédiaire tablette mérite une passe de vérification visuelle réelle (device testing, pas seulement resize navigateur).

🟨 Pages concernées : toutes · 🟦 Action : ouverture du menu burger sous 768px · 🟪 Condition : aucune cible cliquable <44px, aucun scroll horizontal involontaire.

---

## PILIER III — Révolution des previews et de la page Articles

- ✅ **Fait** — Cartes visuelles `/articles` : miniature 16:9, titre, chapeau tronqué à 2 lignes (`line-clamp-2`), badge de statut, source + date relative (`ArticlesScreen.tsx`).
- ✅ **Fait** — Génération d'image HD par article (illustrateur IA, `agent/nodes/illustrator.py`).
- ✅ **Fait** — Carte entièrement cliquable avec actions internes isolées (`stopPropagation`).
- 🔲 **À faire — le vrai delta de ce pilier** — **Micro-interactions manquantes** : le clic sur une carte ne déclenche aujourd'hui qu'un `hover:shadow-md` statique (vérifié dans `ArticlesScreen.tsx:175`), aucune transition fade-in/scale à l'ouverture n'existe. À implémenter :
  - Effet `scale` léger au survol (`hover:scale-[1.01] transition-transform`).
  - Transition de sortie de carte → page de révision (fade + léger scale via CSS transitions natives, pas de nouvelle dépendance lourde type Framer Motion sauf validation explicite du coût bundle).

🟨 Page : `/articles`, `/articles/{id}` · 🟦 Action : clic sur une carte · 🟪 Condition : la transition ne doit jamais dépasser ~200-250ms pour ne pas donner une impression de lenteur.

---

## PILIER IV — Fluidification des transitions & boucle de régénération

- ✅ **Fait** — Écran de transition plein écran avec rotation de 7 micro-messages chaleureux (fade 250ms / 1,3s), déclenché uniquement pour le travail actif de la session courante (`AgentScreen.tsx`, `_LOADING_MESSAGES`).
- ✅ **Fait** — Bouton "↻ Améliorer et régénérer" — boucle illimitée, nouvel angle + nouvelle image à chaque appel, coût réel accepté (`ArticleEditorScreen.tsx`, `POST /api/articles/{id}/regenerate`). Prouvé live via `test_regenerate_live.py` (7/7).
- ✅ **Fait** — Verrouillage strict du mode semi-automatique (HITL obligatoire), non désactivable depuis l'IHM (`Toggle checked={true} disabled`).
- ✅ **Fait** — Correction du faux-positif "Article prêt mais introuvable automatiquement" : le toast se base désormais sur une re-vérification live de l'état serveur juste avant affichage, plutôt que sur un état polled potentiellement périmé (throttling d'onglet en arrière-plan) — commit `8d38c93`.
- 🔲 **À faire** — Vérification finale post-déploiement du correctif ci-dessus sur `http://213.156.135.139/agent` (en cours de validation avec l'utilisateur au moment de la rédaction de cette roadmap).

🟨 Page : `/agent`, `/articles/{id}` · 🟦 Action : "Lancer le cycle", "Améliorer et régénérer" · 🟪 Condition : double-clic bloqué (`anyActionInFlight`), mode semi jamais désactivable, aucun écran de transition pour un cycle `PAUSED` ambiant découvert passivement.

---

## Synthèse — travail réellement restant

| # | Item | Pilier | Effort estimé |
|---|------|--------|----------------|
| 1 | Micro-interactions (scale/fade) sur les cartes Articles | III | Faible |
| 2 | Audit textes d'erreur bruts sur pages secondaires | I | Faible |
| 3 | Passe visuelle desktop (espaces négatifs, grille asymétrique) | II | Moyen |
| 4 | Vérification device réel tablette (768–1024px) | II | Faible |
| 5 | Confirmation finale correctif toast HITL en production | IV | En cours |

La majorité de la refonte demandée est déjà livrée en production ; cette roadmap cible les 5 items ci-dessus comme prochaine itération, plutôt que de redemander un travail déjà fait.
