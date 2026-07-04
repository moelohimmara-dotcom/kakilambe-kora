"""
test_scraper_live_freshness.py — Vérifie en conditions réelles que le
filtre Jour-J (topic="news", days=1) et l'anti-duplication inter-cycles
ajoutés à scraper.py n'assèchent pas le pipeline (risque opérationnel réel :
la couverture Tavily "news" sur les médias africains régionaux peut être
plus faible que la recherche générale utilisée jusqu'ici).

N'invoque QUE le nœud scraper (pas tout le graphe) — aucun appel LLM ni
génération d'image, coût minimal.

Exécution (sur le VPS, où vivent les clés API) :
    venv/bin/python test_scraper_live_freshness.py
"""
import asyncio
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_PASSED = 0
_FAILED = 0


def _check(name, ok, detail=""):
    global _PASSED, _FAILED
    if ok:
        _PASSED += 1
        print(f"  [OK] {name}")
    else:
        _FAILED += 1
        print(f"  [FAIL] {name} — {detail}")


async def main():
    print("\n=== test_scraper_live_freshness ===\n")
    from agent.nodes import scraper

    cycle_id = str(uuid.uuid4())
    state = {
        "cycle_id": cycle_id,
        "mode": "semi",
        "errors": [],
        "raw_sources": [],
    }

    print(">> Exécution du nœud scraper (topic=news, days=1, anti-dup inter-cycles)")
    result = await scraper.run(state)
    raw_sources = result.get("raw_sources", [])

    print(f"    -> {len(raw_sources)} article(s) valides collectés")
    for a in raw_sources[:5]:
        print(f"       - {a.get('title', '(sans titre)')} — {a.get('url', '')}")

    _check(
        "au moins 1 article collecté malgré le filtre Jour-J (pas de pipeline asséché)",
        len(raw_sources) > 0,
        "0 article — risque réel : le filtre days=1 de Tavily est peut-être trop strict pour la couverture Afrique",
    )
    _check("aucune erreur remontée dans state.errors", len(state.get("errors", [])) == 0, str(state.get("errors")))

    print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
    sys.exit(0 if _FAILED == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
