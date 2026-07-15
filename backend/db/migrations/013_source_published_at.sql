-- ═══════════════════════════════════════════════════════════════════
-- Migration 013 : date réelle de publication de la source
--
-- Root cause (audit 2026-07-15) : Tavily fournit un champ published_date
-- par résultat (exploité par agent/nodes/scraper.py:_is_fresh comme simple
-- filtre de fraîcheur), mais cette valeur n'était jamais persistée — ni
-- dans raw_feeds, ni dans content_pool, ni dans articles. Le "Il y a Xh" /
-- la date affichés dans l'UI reposaient donc sur articles.created_at
-- (horodatage d'ÉCRITURE par KORA), pas sur la date réelle de publication
-- de l'article source. Cette migration ajoute une colonne dédiée à chaque
-- étape du pipeline pour que cette date survive du scraping jusqu'à
-- l'article final, sans jamais être générée/déduite par le LLM.
--
-- NULL = date non confirmée (aucune métadonnée fiable fournie par la
-- source) — jamais remplacée par une date inventée ou par created_at
-- silencieusement ; l'API expose explicitement ce cas au frontend.
-- ═══════════════════════════════════════════════════════════════════

ALTER TABLE raw_feeds    ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
ALTER TABLE content_pool ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;

-- Articles déjà existants : NULL (date non confirmée) plutôt que de leur
-- attribuer rétroactivement created_at comme s'il s'agissait d'une vraie
-- date source — ne pas fabriquer une confiance qui n'a jamais existé.
ALTER TABLE articles ADD COLUMN IF NOT EXISTS source_published_at TIMESTAMPTZ;
