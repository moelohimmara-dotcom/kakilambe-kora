# KORA V3 — GuinéePress Intelligence

### Le premier pipeline éditorial autonome multi-agents pensé pour l'information panafricaine

---

## A. Une-line Pitch & Vision

> **KORA V3 est un pipeline éditorial autonome et semi-autonome, piloté par une architecture multi-agents LangGraph, qui capte, hiérarchise, réécrit et publie l'actualité guinéenne et panafricaine — en temps réel, à l'échelle, avec ou sans validation humaine.**

**Le problème.** La veille d'information panafricaine souffre d'un triple goulot d'étranglement : la fragmentation des sources (des dizaines de médias guinéens et continentaux à surveiller manuellement), le coût de la production éditoriale humaine à volume constant, et le risque de perte de contrôle qu'impose l'automatisation pure — publier sans supervision expose une rédaction à l'erreur factuelle ou à la dérive de ton.

**La proposition de valeur.** KORA V3 supprime ce compromis. Il automatise la chaîne complète — collecte, sélection, rédaction, illustration, publication — tout en laissant l'éditeur humain reprendre la main à l'instant précis où elle compte : avant publication. Résultat : une rédaction qui scale sans sacrifier ni la vitesse, ni la qualité, ni le contrôle éditorial.

---

## B. Fonctionnalités maîtresses

### 1. Veille & Ingestion Intelligente

- Capture automatisée par **lots identifiés (`batch_id`)**, garantissant traçabilité et déduplication entre cycles de collecte.
- Hiérarchisation à **trois niveaux de sources** : médias guinéens vérifiés (priorité éditoriale maximale), médias panafricains de référence, et un niveau de repli filtré sémantiquement pour ne jamais manquer une actualité pertinente hors périmètre curé.
- Enrichissement automatique du contenu complet (extraction Markdown) pour transformer un simple flux RSS en matière première rédactionnelle exploitable.

### 2. Moteur de Rédaction Journalistique Dé-IA-fié

- Calibrage éditorial strict sur les standards **BBC News Africa** : règle des **5W** imposée dès les deux premières phrases, structure en **pyramide inversée**, paragraphes courts optimisés lecture mobile.
- **Exclusion active** des tics de langage caractéristiques d'un texte généré par IA — un moteur de validation stylistique interne détecte et fait régénérer tout contenu non conforme avant qu'il n'atteigne l'éditeur humain.
- Signature éditoriale systématique, traçant chaque publication comme production de l'agent.

### 3. Tableau de Bord d'Administration Innovant

- **Double mode d'exécution exclusif** :
  - *Mode Autonome* — publication directe, orchestrée par file d'attente pour espacer intelligemment les publications successives d'un même cycle.
  - *Mode Semi-Automatique (HITL — Human-In-The-Loop)* — le pipeline s'interrompt avant publication, présente l'article prêt à l'éditeur, et attend validation ou rejet explicite.
- **Terminal de logs streamés en temps réel** (Server-Sent Events) : visibilité totale, nœud par nœud, sur l'exécution du pipeline, avec rejeu de l'historique et nettoyage intuitif en fin de cycle.
- **Console `/settings` avancée** : identifiants de publication, mapping des catégories, planification horaire du cycle quotidien, alertes email — piloté sans intervention technique.

---

## C. Architecture technique & infrastructure

Un écosystème de classe production, conçu pour la fiabilité et la scalabilité horizontale :

- **Frontend** — Next.js 15 (App Router) + TypeScript : interfaces scannables, réactives, pensées pour un usage éditorial quotidien.
- **Orchestration IA** — FastAPI (Python asynchrone) associé à **LangGraph** : architecture multi-agents organisée en graphe d'état cyclique typé, avec **système de checkpointing** dédié à la gestion fine des pauses HITL et à la reprise de session.
- **Chaîne LLM résiliente** — routage multi-fournisseurs avec bascule automatique en cascade, garantissant la continuité de service même en cas d'indisponibilité d'un fournisseur.
- **Base de données & stockage** — Supabase (PostgreSQL unifié), row-level security activée, connexions optimisées par **pooling** pour absorber la charge des cycles concurrents.
- **Hébergement & sécurité** — VPS dédié, isolation réseau via reverse proxy Nginx, panneau d'administration technique protégé par double couche d'authentification. Architecture prête pour un chiffrement **HTTPS de bout en bout (Certbot/Let's Encrypt)**, activable en quelques minutes dès la finalisation du nommage de domaine.

---

## D. Métriques de performance & scalabilité

- **Streaming UI natif** sur le module Chat IA : réponse token par token, latence perçue minimale, expérience conversationnelle fluide dès la première seconde.
- **Ingestion par lots** : la logique de `batch_id` limite drastiquement les requêtes redondantes en base, préservant les quotas de connexion et réduisant le coût d'infrastructure à volume de veille constant.
- **Reprise à chaud** : reprogrammation de la planification et des réglages critiques sans interruption de service, sans redémarrage.
- **Résilience multi-fournisseurs** : chaîne de repli LLM éliminant le point de défaillance unique sur la génération de contenu.

---

*KORA V3 — GuinéePress Intelligence. L'IA au service de l'information, jamais au détriment du contrôle éditorial.*
