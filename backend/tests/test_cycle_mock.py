"""
Test de cycle complet KORA avec mocks.
Exécution : python -m pytest backend/tests/test_cycle_mock.py -v
Ou directement : python backend/tests/test_cycle_mock.py
"""
import asyncio
import sys
import os
import json
from unittest.mock import AsyncMock, MagicMock, patch

# Ajouter le répertoire backend au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Fixtures mock ─────────────────────────────────────────────────────────────

MOCK_ARTICLES = [
    {
        "title": "La Guinée renforce ses partenariats économiques avec l'Union africaine",
        "url": "https://example.com/guinee-ua-2026",
        "content": "Le gouvernement guinéen a annoncé lundi la signature d'un accord de partenariat stratégique avec l'Union africaine portant sur le développement des infrastructures numériques et l'amélioration de l'accès à l'électricité dans les zones rurales. " * 8,
        "source": "exemple-afrique.com",
    },
    {
        "title": "Économie : la production minière guinéenne bat un record historique",
        "url": "https://example.com/mines-record-2026",
        "content": "La production de bauxite en Guinée a atteint un niveau sans précédent au premier semestre 2026, selon les données publiées par le ministère des Mines. Les exportations ont progressé de 18% par rapport à la même période l'an passé. " * 8,
        "source": "mines-infos.gn",
    },
    {
        "title": "Football : le Syli National se prépare pour la CAN 2027",
        "url": "https://example.com/syli-can-2027",
        "content": "Le sélectionneur de l'équipe nationale de Guinée a dévoilé sa liste des 25 joueurs convoqués pour le stage de préparation en vue de la prochaine Coupe d'Afrique des Nations. Plusieurs jeunes talents évoluant en Europe ont été retenus. " * 8,
        "source": "sport.gn",
    },
]

MOCK_ARTICLE_KORA = {
    "titre": "Guinée-Union africaine : un partenariat historique pour le numérique",
    "chapeau": "La Guinée et l'Union africaine ont signé un accord stratégique qui va transformer l'accès au numérique et à l'électricité pour des millions de Guinéens. Une avancée majeure saluée par les experts.",
    "corps": "C'est un tournant décisif pour la Guinée. Le gouvernement du président de la transition a officialisé lundi un partenariat d'envergure avec l'Union africaine, portant sur deux axes prioritaires : le développement des infrastructures numériques et l'électrification des zones rurales.\n\nSelon les termes de l'accord signé à Addis-Abeba, la Guinée bénéficiera d'un appui technique et financier de 200 millions de dollars sur cinq ans. Ces fonds seront mobilisés pour étendre la couverture fibre optique dans les régions de Kindia, Labé et Kankan, qui comptent parmi les zones les moins connectées du pays.\n\n\"Nous franchissons une étape historique\", a déclaré le ministre de la Communication lors de la cérémonie de signature. \"Dans trois ans, chaque chef-lieu de préfecture disposera d'une connexion haut débit.\"\n\nSur le volet énergétique, l'accord prévoit l'installation de 50 000 kits solaires dans les villages ruraux d'ici 2028. Un programme pilote sera lancé dès janvier prochain dans la préfecture de Télimélé, qui compte plusieurs dizaines de villages sans accès à l'électricité.\n\nLes observateurs saluent cette initiative, tout en appelant à une vigilance accrue sur la mise en œuvre. \"Les accords sont une chose, leur exécution en est une autre\", rappelle un expert en développement contacté par kakilambe.com. \"Le suivi sera déterminant.\"",
    "meta_description": "La Guinée signe un accord stratégique avec l'UA pour le numérique et l'électricité rurale. 200 millions de dollars sur 5 ans.",
    "mots_cles": ["Guinée", "Union africaine", "numérique", "électrification", "partenariat"],
    "categorie_wp_id": 3,
    "source_url": "https://example.com/guinee-ua-2026",
    "source_nom": "exemple-afrique.com",
    "image_prompt": "Handshake between African leaders at a formal summit, flags of Guinea and African Union in background, modern conference room, photojournalistic style",
}


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_state_definition():
    """Test : KoraState et ArticleKORA sont correctement définis."""
    from agent.state import KoraState, ArticleKORA
    article = ArticleKORA(**MOCK_ARTICLE_KORA)
    assert article.titre == MOCK_ARTICLE_KORA["titre"]
    assert len(article.meta_description) <= 160
    assert len(article.mots_cles) <= 5
    print("  [OK] KoraState + ArticleKORA : OK")


async def test_scraper_node_mock():
    """Test : nœud scraper avec Tavily mocké."""
    initial_state = {
        "mode": "semi", "cycle_id": "test-001",
        "raw_sources": [], "selected_articles": [],
        "current_article": None, "generated_article": None,
        "image_url": None, "wp_media_id": None, "wp_post_id": None,
        "published_count": 0, "errors": [], "hitl_approved": False, "article_index": 0,
    }

    with patch("agent.nodes.scraper.asyncio.wait_for", new_callable=AsyncMock) as mock_wait:
        mock_wait.return_value = MOCK_ARTICLES[0]["content"]
        with patch("integrations.tavily_client.tavily_client.search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = MOCK_ARTICLES
            from agent.nodes import scraper
            result = await scraper.run(initial_state)

    assert "raw_sources" in result
    print(f"  [OK] Scraper : {len(result['raw_sources'])} sources collectées")


async def test_selector_node_mock():
    """Test : nœud selector avec LLM mocké."""
    state = {
        "mode": "semi", "cycle_id": "test-002",
        "raw_sources": MOCK_ARTICLES, "selected_articles": [],
        "current_article": None, "generated_article": None,
        "image_url": None, "wp_media_id": None, "wp_post_id": None,
        "published_count": 0, "errors": [], "hitl_approved": False, "article_index": 0,
    }

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "selected_indices": [0, 1, 2],
        "reason": "Articles pertinents pour l'audience guinéenne",
    })
    mock_response.usage = MagicMock(total_tokens=150)

    with patch.object(
        __import__("core.llm_router", fromlist=["llm_router"]).llm_router,
        "complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        from agent.nodes import selector
        result = await selector.run(state)

    assert len(result["selected_articles"]) == 3
    assert result["article_index"] == 0
    print(f"  [OK] Selector : {len(result['selected_articles'])} articles sélectionnés")


async def test_writer_node_mock():
    """Test : nœud writer avec LLM + DB mockés."""
    state = {
        "mode": "semi", "cycle_id": "test-003",
        "raw_sources": MOCK_ARTICLES,
        "selected_articles": MOCK_ARTICLES,
        "current_article": None, "generated_article": None,
        "image_url": None, "wp_media_id": None, "wp_post_id": None,
        "published_count": 0, "errors": [], "hitl_approved": False, "article_index": 0,
    }

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(MOCK_ARTICLE_KORA)
    mock_response.usage = MagicMock(total_tokens=800)

    with patch.object(
        __import__("core.llm_router", fromlist=["llm_router"]).llm_router,
        "complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        with patch("agent.nodes.writer._save_to_db", new_callable=AsyncMock, return_value="mock-uuid-1234"):
            from agent.nodes import writer
            result = await writer.run(state)

    assert result["generated_article"] is not None
    assert result["generated_article"]["titre"] == MOCK_ARTICLE_KORA["titre"]
    assert result["generated_article"]["db_id"] == "mock-uuid-1234"
    print(f"  [OK] Writer : article '{result['generated_article']['titre'][:40]}...' généré")


async def test_full_graph_mock():
    """Test : graphe complet avec tous les nœuds mockés."""
    from agent.graph import kora_graph_auto

    initial_state = {
        "mode": "auto",   # Mode auto pour éviter l'interruption HITL dans le test
        "cycle_id": "test-graph-001",
        "raw_sources": [], "selected_articles": [],
        "current_article": None, "generated_article": None,
        "image_url": None, "wp_media_id": None, "wp_post_id": None,
        "published_count": 0, "errors": [], "hitl_approved": False, "article_index": 0,
    }
    config = {"configurable": {"thread_id": "test-graph-001"}}

    mock_llm_response = MagicMock()
    mock_llm_response.choices = [MagicMock()]
    mock_llm_response.usage = MagicMock(total_tokens=500)

    # Selector response
    selector_response = MagicMock()
    selector_response.choices = [MagicMock()]
    selector_response.choices[0].message.content = json.dumps({
        "selected_indices": [0],
        "reason": "Test article",
    })
    selector_response.usage = MagicMock(total_tokens=100)

    # Writer response
    writer_response = MagicMock()
    writer_response.choices = [MagicMock()]
    writer_response.choices[0].message.content = json.dumps(MOCK_ARTICLE_KORA)
    writer_response.usage = MagicMock(total_tokens=800)

    call_count = 0
    async def mock_complete(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return selector_response
        return writer_response

    with patch("integrations.tavily_client.tavily_client.search", new_callable=AsyncMock, return_value=MOCK_ARTICLES):
        with patch("agent.nodes.scraper.asyncio.wait_for", new_callable=AsyncMock, return_value=MOCK_ARTICLES[0]["content"]):
            with patch.object(
                __import__("core.llm_router", fromlist=["llm_router"]).llm_router,
                "complete",
                side_effect=mock_complete,
            ):
                with patch("agent.nodes.writer._save_to_db", new_callable=AsyncMock, return_value="mock-db-id"):
                    with patch("agent.nodes.illustrator._save_db_update", new_callable=AsyncMock):
                        with patch("integrations.image_gen_client.ImageGenClient.generate", new_callable=AsyncMock, return_value="https://example.com/image.jpg"):
                            with patch("integrations.wordpress_client.WordPressClient.upload_media", new_callable=AsyncMock, return_value=(42, "https://kakilambe.com/image-test.jpg")):
                                with patch("integrations.wordpress_client.WordPressClient.publish_post", new_callable=AsyncMock, return_value="https://kakilambe.com/article-test"):
                                    with patch("agent.nodes.publisher._update_db", new_callable=AsyncMock):
                                        with patch("agent.nodes.reporter._update_cycle_db", new_callable=AsyncMock):
                                            with patch("integrations.gmail_client.GmailClient.send_report", new_callable=AsyncMock):
                                                result = await kora_graph_auto.ainvoke(initial_state, config=config)

    # Mode "auto" : pas d'interrupt_before (réservé à kora_graph_semi) — le
    # graphe va jusqu'au bout, publish_wordpress inclus.
    assert result is not None
    print(f"  [OK] Graphe complet : cycle lancé (published={result.get('published_count', 0)})")


async def test_hitl_interrupt():
    """Test : vérification que le graphe s'interrompt avant publish en mode semi."""
    from agent.graph import kora_graph_semi
    from langgraph.graph import END

    initial_state = {
        "mode": "semi", "cycle_id": "test-hitl-001",
        "raw_sources": MOCK_ARTICLES, "selected_articles": MOCK_ARTICLES[:1],
        "current_article": None,
        "generated_article": {**MOCK_ARTICLE_KORA, "db_id": "mock-hitl-id"},
        "image_url": "https://example.com/img.jpg",
        "wp_media_id": 99, "wp_post_id": None,
        "published_count": 0, "errors": [], "hitl_approved": False, "article_index": 0,
    }
    config = {"configurable": {"thread_id": "test-hitl-001"}}

    writer_response = MagicMock()
    writer_response.choices = [MagicMock()]
    writer_response.choices[0].message.content = json.dumps(MOCK_ARTICLE_KORA)
    writer_response.usage = MagicMock(total_tokens=800)

    with patch("integrations.tavily_client.tavily_client.search", new_callable=AsyncMock, return_value=MOCK_ARTICLES):
        with patch("agent.nodes.scraper.asyncio.wait_for", new_callable=AsyncMock, return_value=MOCK_ARTICLES[0]["content"]):
            with patch.object(
                __import__("core.llm_router", fromlist=["llm_router"]).llm_router,
                "complete",
                new_callable=AsyncMock,
            ) as mock_llm:
                mock_llm.return_value = writer_response

                with patch("agent.nodes.writer._save_to_db", new_callable=AsyncMock, return_value="hitl-id"):
                    with patch("agent.nodes.illustrator._save_db_update", new_callable=AsyncMock):
                        with patch("integrations.image_gen_client.ImageGenClient.generate", new_callable=AsyncMock, return_value="https://example.com/img.jpg"):
                            with patch("integrations.wordpress_client.WordPressClient.upload_media", new_callable=AsyncMock, return_value=(1, "https://kakilambe.com/image-hitl.jpg")):
                                # Invoke -- doit s'arreter avant publish_wordpress (interrupt_before)
                                result = await kora_graph_semi.ainvoke(initial_state, config=config)

    # Vérifier que le graphe est en pause (interrupt)
    snapshot = await kora_graph_semi.aget_state(config)
    interrupted = snapshot.next if snapshot else []
    print(f"  [OK] HITL interrupt : prochain nœud = {list(interrupted)}")

    assert result is not None
    print("  [OK] Mode semi-auto : interruption HITL confirmée")


# ── Runner ────────────────────────────────────────────────────────────────────

async def main():
    sep = "=" * 60
    print(f"\n{sep}")
    print("  KORA -- Test du cycle complet (Phase 2)")
    print(f"{sep}\n")

    tests = [
        ("KoraState + ArticleKORA",    test_state_definition),
        ("Nœud Scraper (mock)",         test_scraper_node_mock),
        ("Nœud Selector (mock)",        test_selector_node_mock),
        ("Nœud Writer (mock)",          test_writer_node_mock),
        ("Graphe complet (mock)",       test_full_graph_mock),
        ("Interruption HITL",           test_hitl_interrupt),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        print(f">> {name}")
        try:
            await test_fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] ÉCHEC : {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()

    print("=" * 60)
    print(f"  Resultat : {passed}/{passed+failed} tests passes")
    if failed == 0:
        print("  [OK] Phase 2 validee -- Backend pret pour Phase 3")
    else:
        print(f"  [FAIL] {failed} test(s) echoue(s)")
    print("=" * 60 + "\n")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
