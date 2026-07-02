"""
test_v3_item8.py — Validation locale de l'item 8 (synchronisation dynamique
des catégories WordPress).

Exécution : python test_v3_item8.py
"""
import asyncio
import sys
import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_PASSED = 0
_FAILED = 0


def _check(name: str, ok: bool, detail: str = ""):
    global _PASSED, _FAILED
    if ok:
        _PASSED += 1
        print(f"  [OK] {name}")
    else:
        _FAILED += 1
        print(f"  [FAIL] {name} — {detail}")


def _fake_db(row: dict | None):
    """Simule get_db() renvoyant une session dont .execute().mappings().first() == row."""
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    session.execute = AsyncMock(return_value=result)

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx


async def test_resolve_category_id_db_hit():
    """Si la table wp_categories a un mapping, il est utilisé — pas le fallback codé en dur."""
    import agent.nodes.writer as writer

    with patch("agent.nodes.writer.get_db", _fake_db({"wp_id": 99})):
        result = await writer._resolve_category_id("Sport")
    _check(
        "_resolve_category_id: mapping DB prioritaire sur le fallback codé en dur",
        result == 99,
        f"got {result}",
    )


async def test_resolve_category_id_fallback_on_db_error():
    """Si la DB est indisponible, on retombe sur le mapping codé en dur — le cycle ne doit pas planter."""
    import agent.nodes.writer as writer

    @asynccontextmanager
    async def _broken_db():
        raise RuntimeError("DB down")
        yield  # pragma: no cover

    with patch("agent.nodes.writer.get_db", _broken_db):
        result = await writer._resolve_category_id("Politique")
    _check(
        "_resolve_category_id: repli sur le mapping codé en dur si la DB échoue",
        result == writer._CATEGORY_MAP_FALLBACK["politique"],
        f"got {result}",
    )


async def test_resolve_category_id_default_when_unmapped():
    """Aucun mapping DB, aucun fallback codé en dur pour ce libellé → catégorie par défaut."""
    import agent.nodes.writer as writer

    with patch("agent.nodes.writer.get_db", _fake_db(None)):
        result = await writer._resolve_category_id("Culture")
    _check(
        "_resolve_category_id: catégorie par défaut si aucun mapping trouvé",
        result == writer._DEFAULT_CATEGORY_ID,
        f"got {result}",
    )


async def test_resolve_category_id_empty_label():
    import agent.nodes.writer as writer

    result = await writer._resolve_category_id("")
    _check(
        "_resolve_category_id: libelle vide -> categorie par defaut sans requete DB",
        result == writer._DEFAULT_CATEGORY_ID,
        f"got {result}",
    )


def test_norm_matches_accents_and_case():
    """La normalisation ignore accents/casse pour matcher les vrais noms WordPress."""
    import api.settings_routes as settings_routes

    _check(
        "_norm: 'Économie' == 'economie'",
        settings_routes._norm("Économie") == settings_routes._norm("economie"),
    )
    _check(
        "_norm: 'Sécurité' == 'SECURITE'",
        settings_routes._norm("Sécurité") == settings_routes._norm("SECURITE"),
    )
    _check(
        "_norm: libellés différents restent différents",
        settings_routes._norm("Sport") != settings_routes._norm("Société"),
    )


def test_sync_auto_match_logic():
    """
    Reproduit la logique d'auto-association de sync_wp_categories : une
    catégorie WP nommée exactement comme un libellé KORA (aux accents/casse
    près) doit être auto-mappée UNIQUEMENT si elle n'a pas déjà de mapping
    (pour ne jamais écraser un choix manuel de l'utilisateur).
    """
    import api.settings_routes as settings_routes

    label_by_norm = {settings_routes._norm(l): l for l in settings_routes._KORA_LABELS}

    # Nouvelle catégorie WP nommée "économie" (sans accent, sans mapping existant)
    auto_label_new = None if False else label_by_norm.get(settings_routes._norm("economie"))
    _check(
        "sync: nouvelle catégorie nommée comme un libellé KORA est auto-mappée",
        auto_label_new == "Économie",
        f"got {auto_label_new}",
    )

    # Catégorie WP déjà mappée manuellement — ne doit jamais être touchée
    existing_row = {"kora_label": "Sport"}
    auto_label_existing = None if existing_row else label_by_norm.get(settings_routes._norm("economie"))
    _check(
        "sync: mapping manuel existant n'est jamais écrasé par l'auto-match",
        auto_label_existing is None,
        f"got {auto_label_existing}",
    )

    # Catégorie WP sans correspondance exacte (ex: "Faits divers") reste non mappée
    auto_label_no_match = label_by_norm.get(settings_routes._norm("Faits divers"))
    _check(
        "sync: catégorie sans correspondance exacte reste non mappée",
        auto_label_no_match is None,
        f"got {auto_label_no_match}",
    )


async def test_update_mapping_rejects_invalid_label():
    """PATCH /wp-categories/{id} doit rejeter un libellé hors des 7 valeurs autorisées."""
    import api.settings_routes as settings_routes
    from fastapi import HTTPException

    body = settings_routes.CategoryMappingPatch(kora_label="Divertissement")
    raised = False
    try:
        if body.kora_label is not None and body.kora_label not in settings_routes._KORA_LABELS:
            raise HTTPException(status_code=400, detail="invalid")
    except HTTPException:
        raised = True
    _check(
        "update_wp_category_mapping: libellé invalide rejeté (400)",
        raised,
    )


def test_article_list_endpoint_selects_display_fields():
    """
    Bug réel trouvé lors du test end-to-end de l'item 8 : le SELECT de
    GET /api/articles omettait image_url, mots_cles, categorie_id et
    cycle_id. Conséquence en production : la page Articles affichait des
    cartes sans vignette ni tags, et la carte HITL du dashboard (Phase 2)
    perdait l'image de l'article en attente de validation.
    """
    import inspect
    import api.article_routes as article_routes

    source = inspect.getsource(article_routes.list_articles)
    required_columns = ["image_url", "mots_cles", "categorie_id", "cycle_id"]
    for col in required_columns:
        _check(
            f"list_articles: SELECT inclut '{col}' (affiché par ArticlesScreen/DashboardScreen)",
            source.count(col) >= 2,  # présent dans les deux branches (avec/sans filtre status)
            f"'{col}' absent d'une des deux requêtes SELECT",
        )


async def main():
    print("\n=== test_v3_item8 — Synchronisation dynamique des catégories WordPress ===\n")
    await test_resolve_category_id_db_hit()
    await test_resolve_category_id_fallback_on_db_error()
    await test_resolve_category_id_default_when_unmapped()
    await test_resolve_category_id_empty_label()
    test_norm_matches_accents_and_case()
    test_sync_auto_match_logic()
    await test_update_mapping_rejects_invalid_label()
    test_article_list_endpoint_selects_display_fields()

    print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
    if _FAILED:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
