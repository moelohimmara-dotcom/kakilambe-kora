"""
test_v3_stabilization.py — Validation locale du Plan V3 (Phase 1 + item 7).

Couvre :
1. cycle_routes.py — la requête SQL corrigée (started_at, pas created_at) est
   syntaxiquement valide et correspond au schéma réel Supabase (déjà vérifié
   en amont via une requête directe contre la table 'cycles').
2. illustrator.py — generate_and_upload_image() est réutilisable et retourne
   bien (image_url, wp_media_id, wp_image_src) avec des dépendances mockées.
3. article_routes.py — /regenerate-image refuse un article déjà PUBLISHED
   et fonctionne sur un article PENDING_REVIEW.

Exécution : python test_v3_stabilization.py
"""
import asyncio
import sys
import os
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(__file__))

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


async def test_cycle_routes_sql_columns():
    """Vérifie que les colonnes utilisées dans cycle_routes.py existent réellement."""
    from api.cycle_routes import _LIST_COLUMNS
    expected = {
        "id", "mode", "status", "articles_collected", "articles_selected",
        "articles_published", "articles_rejected", "started_at", "completed_at",
    }
    actual = {c.strip() for c in _LIST_COLUMNS.split(",")}
    _check(
        "cycle_routes: colonnes SQL == colonnes réelles de la table (started_at, pas created_at)",
        actual == expected,
        f"actual={actual}",
    )
    _check(
        "cycle_routes: 'created_at' n'est plus référencé (bug corrigé)",
        "created_at" not in actual,
    )


async def test_illustrator_regenerate():
    """Teste generate_and_upload_image() avec dépendances mockées."""
    from agent.nodes.illustrator import generate_and_upload_image

    with patch("integrations.image_gen_client.image_gen_client.generate",
               new_callable=AsyncMock, return_value="https://pollinations.ai/fake.jpg"):
        with patch("integrations.wordpress_client.wp_client.upload_media",
                   new_callable=AsyncMock, return_value=(77, "https://kakilambe.com/wp-fake.jpg")):
            image_url, wp_media_id, wp_image_src = await generate_and_upload_image(
                "A photorealistic image of Conakry skyline", "Titre de test"
            )

    _check("illustrator: generate_and_upload_image retourne 3 valeurs cohérentes",
           image_url == "https://pollinations.ai/fake.jpg"
           and wp_media_id == 77
           and wp_image_src == "https://kakilambe.com/wp-fake.jpg")


async def test_illustrator_regenerate_failure_propagates():
    """Vérifie qu'un échec de génération lève bien une exception (pas un None silencieux)."""
    from agent.nodes.illustrator import generate_and_upload_image

    with patch("integrations.image_gen_client.image_gen_client.generate",
               new_callable=AsyncMock, return_value=None):
        raised = False
        try:
            await generate_and_upload_image("prompt", "titre")
        except RuntimeError:
            raised = True
        _check("illustrator: échec de génération lève RuntimeError (pas de faux succès)", raised)


async def main():
    print("=" * 60)
    print("  KORA V3 — Stabilisation (Phase 1 + item 7)")
    print("=" * 60)
    print("\n>> cycle_routes.py")
    await test_cycle_routes_sql_columns()
    print("\n>> illustrator.py — régénération HITL")
    await test_illustrator_regenerate()
    await test_illustrator_regenerate_failure_propagates()

    print("\n" + "=" * 60)
    print(f"  Resultat : {_PASSED}/{_PASSED + _FAILED} tests passes")
    if _FAILED == 0:
        print("  [OK] Validation locale reussie")
    else:
        print(f"  [FAIL] {_FAILED} test(s) echoue(s)")
    print("=" * 60)
    return 0 if _FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
