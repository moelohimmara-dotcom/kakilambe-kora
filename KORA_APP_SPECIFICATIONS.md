# Cahier des Charges & Spécifications — KORA V3 (Application React Native Expo)

**Nom du projet :** GuinéePress Intelligence (nom de code : **KORA V3**)
**Plateforme cible :** Application Mobile & Tablette (iOS/Android) via **React Native (Expo)**
**Statut du document :** Cahier des charges global unifié (spécifications techniques, fonctionnelles et UI/UX).

---

## 1. Présentation générale & vision produit

### 1.1. Le concept
**KORA V3** est le premier pipeline éditorial autonome multi-agents pensé pour l'information panafricaine et guinéenne. Il s'agit d'un système capable de capter, hiérarchiser, réécrire et publier l'actualité en temps réel.

### 1.2. Le problème résolu
La veille de l'information panafricaine souffre de la fragmentation des sources (dizaines de médias locaux et continentaux) et du coût de production. Automatiser la veille comporte cependant un risque : la perte de contrôle éditorial.

### 1.3. La solution (Proposition de valeur)
KORA V3 supprime ce compromis. Il automatise toute la chaîne de valeur : **collecte, sélection, rédaction, illustration, publication** — tout en offrant à l'éditeur une interface (cette future application React Native) pour valider ou retravailler le contenu **avant publication** (approche *Human-In-The-Loop* - HITL).

La finalité de l'application mobile est de permettre aux éditeurs de gérer ce flux (approuver, rejeter, régénérer) directement depuis leur smartphone ou tablette, de manière fluide et intuitive. L'application mobile cible le site web WordPress ([kakilambe.com](https://kakilambe.com)) pour la diffusion finale.

---

## 2. Architecture technique & stack logicielle

Le projet est divisé entre un backend de traitement lourd (déjà en production) et un nouveau frontend mobile (objet de ces spécifications).

### 2.1. Backend (Existant, à conserver tel quel)
- **Framework :** FastAPI (Python), asynchrone.
- **Orchestration IA :** LangGraph. Deux graphes d'état : `kora_graph_semi` (pause avant publication) et `kora_graph_auto` (autonome complet).
- **Modèles IA (LLM) :** Routeur multi-fournisseurs (Groq → Gemini → Cerebras → OpenRouter).
- **Base de données :** Supabase (PostgreSQL managé), RLS activé. Accès via pooler IPv4.
- **Planification :** QStash (Upstash) pour espacer les publications WordPress.
- **Serveur :** Hébergé sur un VPS Debian 12 avec Nginx comme reverse proxy.

### 2.2. Frontend Mobile (À développer)
- **Framework :** **React Native** propulsé par **Expo** (TypeScript recommandé).
- **UI / UX :** Composants natifs, navigation fluide, optimisé pour les interactions tactiles.
- **Authentification :** Le backend actuel utilise un système de cookies maison (`kora_session`). L'application React Native devra gérer ces sessions/cookies (ou adapter l'API pour renvoyer des tokens utilisables de manière sécurisée côté mobile).
- **Connectivité temps réel :** Le dashboard (écran d'agent) nécessite la prise en charge des **Server-Sent Events (SSE)** pour streamer les logs et les états du pipeline en temps réel.

---

## 3. Spécifications fonctionnelles (Core Features)

### 3.1. Veille & Ingestion Intelligente
- Le système backend capture les actualités par **lots (`batch_id`)**.
- **Trois niveaux de sources :**
  1. Sources guinéennes vérifiées (priorité max). Inclut le filtrage strict sur les mots clés locaux (ex: "Doumbouya", "CNRD", "Simandou").
  2. Médias panafricains de référence.
  3. Repli sémantique via recherche web (Tavily).
- Extraction automatique du contenu complet (Markdown) via Firecrawl / BrightData.

### 3.2. Moteur de Rédaction Journalistique Dé-IA-fié
- Calibrage éditorial strict (standards de type BBC News Africa) : pyramide inversée, règle des 5W dans les premières phrases, paragraphes courts adaptés au mobile.
- **Boucle de régénération :** Possibilité depuis l'appli de demander une nouvelle réécriture (changement d'angle, régénération d'image) sans limites.
- Signature en fin d'article : *Par Kakilambe Kora Agent*.

### 3.3. Tableau de bord d'Administration (L'Application Mobile)
L'application doit proposer les vues suivantes :
- **Dashboard Agent :** Un bouton central "Lancer le cycle" et le suivi en temps réel.
- **Gestion des articles (`/articles`) :** Grille/Liste visuelle des articles produits (miniature, titre, statut, source).
- **Éditeur d'article (Révision) :** Visualisation de l'article généré (HTML/Rich Text), l'image, les métadonnées SEO. Boutons d'action : `Approuver et publier`, `↻ Améliorer et régénérer`, `Rejeter`.
- **Réglages (`/settings`) :** Configuration WordPress, bascule mode Auto/Semi-Auto, limite quotidienne, mapping des catégories, planification horaire.
- *(Note: Le module Chat IA a été définitivement supprimé de la vision produit et ne doit pas être implémenté).*

---

## 4. Userflow & Recommandations UX/UI (React Native)

L'objectif est d'avoir une application où la technologie est invisible. Rapide, scannable, sans bruit technique.

### 4.1. Commandement (Dashboard)
- **Écran épuré :** Un seul CTA principal "Lancer le cycle".
- **Feedback visuel :** Lors du lancement, un overlay (ou modal pleine page) affiche des micro-messages chaleureux (qui tournent en boucle toutes les ~1.3s) tant que le processus backend travaille.
- **Sécurité :** Empêcher les doubles-clics (désactiver le bouton pendant le traitement).

### 4.2. Routage de Révision (HITL - Human In The Loop)
- Si le cycle est en mode semi-automatique (par défaut), l'agent se met en pause une fois l'article généré.
- **Redirection automatique :** L'appli bascule l'utilisateur sur l'écran de l'article fraîchement généré.
- **Micro-interactions :** L'écran de révision affiche l'article.
  - Si "Approuver" : publication sur WP via backend, retour à la liste.
  - Si "Régénérer" : Loader sur le bouton, le contenu se met à jour *en place* sans recharger la page entière.

### 4.3. Navigation & Design System Mobile
- **Menu / Navigation :** Utiliser une `Bottom Tab Navigation` pour les accès rapides (Dashboard, Articles, Historique, Paramètres) classique sur mobile, ou un Menu Burger intelligent (`Drawer Navigation`) pour la tablette.
- **Cibles tactiles :** Tous les boutons interactifs doivent avoir une hauteur minimale de `48px` pour le confort sur smartphone.
- **Affichage des cartes (Articles) :** Sur smartphone, liste verticale d'articles (1 colonne). Sur tablette, grille (2 colonnes). Image au format 16:9, titre clampé à 2 lignes.
- **Transitions :** Ajouter de légers effets de "Scale" (grossissement au touch) sur les cartes d'articles. Les transitions entre écrans doivent être natives (rapides, ~200ms).
- **Gestion des erreurs :** Aucun message technique brut (JSON, traceback) ne doit apparaître. Utiliser des Toasts ou Snackbars clairs et traduits en français (ex: "Une erreur est survenue lors de la publication").

---

## 5. Points d'attention pour l'intégration React Native

1. **Réseau et Sécurité :** L'API tourne actuellement en HTTP (pas de SSL certbot). Sur iOS (ATS) et Android (Cleartext Traffic), il faudra configurer les permissions pour autoriser les requêtes HTTP en clair vers l'IP du VPS (`213.156.135.139`) en attendant que le domaine soit configuré en HTTPS.
2. **Authentification Backend :** L'API FastAPI repose sur le fait que le navigateur gère les cookies `kora_session`. Sur React Native, il faudra intercepter ce cookie dans le header `Set-Cookie` lors du login et l'injecter manuellement dans les headers des requêtes suivantes (ou utiliser une librairie gérant le "Cookie Jar" automatiquement pour Axios/Fetch).
3. **SSE (Server Sent Events) :** React Native ne supporte pas nativement l'API `EventSource` web. Il faudra utiliser un polyfill (ex: `react-native-sse`) pour écouter les logs en temps réel sur la route `/api/agent`.

---
*Ce document fige les spécifications de développement pour le client mobile KORA V3.*
