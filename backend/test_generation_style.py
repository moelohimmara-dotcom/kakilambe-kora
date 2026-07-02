"""
test_generation_style.py — Validation en direct du calibrage BBC News Africa
du nœud rédacteur (writer.py), à partir d'une dépêche guinéenne brute réelle.

Appelle le VRAI routeur LLM (pas de mock) — nécessite les clés API configurées
(GROQ_API_KEY etc. via backend/.env). Génère un article complet et vérifie :
1. La signature "*Par Kakilambe Kora Agent*" est présente, à la toute fin, exacte.
2. Aucune des transitions scolaires interdites n'apparaît dans le corps.
3. Aucun des mots interdits n'apparaît.
4. Heuristique de longueur de paragraphe (mobile-first) : la majorité des
   paragraphes restent courts (proxy : nombre de mots par paragraphe).

Exécution : python test_generation_style.py
"""
import asyncio
import sys
import os

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


# Dépêche brute réelle (format identique à ce que scraper.py collecte via
# Tavily/Firecrawl — titre + contenu markdown).
_DEPECHE_TEST = {
    "title": "Simandou : le premier train de minerai de fer quitte la mine",
    "url": "https://africaguinee.com/simandou-premier-train",
    "source": "africaguinee.com",
    "markdown_content": (
        "Le premier convoi ferroviaire chargé de minerai de fer en provenance du "
        "gisement de Simandou, dans le sud-est de la Guinée, a quitté la mine ce "
        "matin en direction du port de Morebaya. Le projet Simandou, considéré "
        "comme l'un des plus importants gisements de fer non exploités au monde, "
        "doit permettre à la Guinée de devenir un acteur majeur du marché mondial "
        "du minerai de fer. Le ministre des Mines a déclaré : « Ce premier "
        "chargement marque le début d'une nouvelle ère pour notre économie. » "
        "Le chantier a mobilisé plus de 15 000 travailleurs guinéens depuis le "
        "début des travaux d'infrastructure, incluant la construction d'une "
        "ligne de chemin de fer de 650 kilomètres et d'un port en eau profonde. "
        "Les autorités guinéennes, sous la présidence de Mamadi Doumbouya et le "
        "CNRD, ont fait de Simandou une priorité nationale, avec un objectif "
        "d'exportation de 60 millions de tonnes de minerai par an à terme."
    ),
}

_BANNED_TRANSITIONS = (
    "en conclusion", "en résumé", "ainsi,", "il est important de rappeler",
    "en fin de compte", "force est de constater",
)
_BANNED_WORDS = (
    "révolutionnaire", "crucial", "indéniable", "explorer", "transcender",
    "de nos jours", "au cœur de", "véritable thriller", "catalyseur",
)
_SIGNATURE = "*Par Kakilambe Kora Agent*"


async def main():
    print("\n=== test_generation_style — Calibrage BBC News Africa (génération réelle) ===\n")

    import agent.nodes.writer as writer

    try:
        article = await writer._write_with_retry(_DEPECHE_TEST)
    except Exception as e:
        print(f"  [FAIL] Génération LLM échouée : {e}")
        sys.exit(1)

    corps = article.corps
    print(f"--- Titre généré ---\n{article.titre}\n")
    print(f"--- Corps généré ({len(corps)} caractères) ---\n{corps}\n")
    print("--- Fin de l'extrait ---\n")

    # 1. Signature exacte, en toute fin
    _check(
        "Signature présente exactement en fin d'article",
        corps.rstrip().endswith(_SIGNATURE),
        f"fin réelle : ...{corps.rstrip()[-60:]!r}",
    )

    corps_lower = corps.lower()

    # 2. Transitions scolaires bannies
    found_transitions = [t for t in _BANNED_TRANSITIONS if t in corps_lower]
    _check(
        "Aucune transition scolaire interdite détectée",
        not found_transitions,
        f"trouvé : {found_transitions}",
    )

    # 3. Mots interdits
    found_words = [w for w in _BANNED_WORDS if w in corps_lower]
    _check(
        "Aucun mot interdit détecté",
        not found_words,
        f"trouvé : {found_words}",
    )

    # 4a. De vrais sauts de paragraphe existent (pas tout collé sur une seule ligne)
    body_without_signature = corps.rsplit(_SIGNATURE, 1)[0].strip()
    has_real_breaks = "\n\n" in body_without_signature
    _check(
        "De vrais sauts de paragraphe (\\n\\n) présents dans le corps",
        has_real_breaks,
        "le corps est une seule ligne continue — sous-titres et texte collés ensemble",
    )

    # 4b. Heuristique mobile-first : paragraphes courts (hors sous-titres ##)
    blocks = [b.strip() for b in body_without_signature.split("\n\n") if b.strip()]
    paragraphs = [b for b in blocks if not b.startswith("#")]
    long_paragraphs = [p for p in paragraphs if len(p.split()) > 45]
    ratio_short = 1 - (len(long_paragraphs) / len(paragraphs)) if paragraphs else 0
    _check(
        f"Majorité des paragraphes courts (mobile-first) — {ratio_short:.0%} sous le seuil",
        not paragraphs or ratio_short >= 0.6,
        f"{len(long_paragraphs)}/{len(paragraphs)} paragraphes dépassent ~45 mots",
    )

    # 5. Catégorie cohérente (résolution déterministe, doit toujours aboutir à un ID)
    _check(
        "categorie_wp_id résolu (jamais None)",
        isinstance(article.categorie_wp_id, int),
        f"got {article.categorie_wp_id!r}",
    )

    print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
    if _FAILED:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
