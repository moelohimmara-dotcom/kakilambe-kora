"""
Test manuel (pas de réseau/DB) : preuve que (a) la date réelle d'une source
Tavily traverse le pipeline sans altération, et (b) qu'un article simulé
avec une date incohérente est bien détecté et bloqué avant publication.

Exécution : python test_date_consistency.py
"""
from datetime import datetime, timezone

from agent.nodes.scraper import _attach_published_at
from agent.nodes.writer import _validate_date_consistency, _extract_mentioned_dates


def test_real_source_date_preserved():
    # Résultat Tavily typique (topic="news") — published_date réel de la source.
    results = [
        {"url": "https://africaguinee.com/x", "title": "Titre", "published_date": "2026-07-14T09:30:00Z"},
    ]
    _attach_published_at(results)
    r = results[0]
    assert r["published_at"] is not None, "la date source aurait dû être parsée"
    assert r["published_at"] == datetime(2026, 7, 14, 9, 30, tzinfo=timezone.utc), (
        f"date altérée : {r['published_at']} au lieu de 2026-07-14T09:30:00Z"
    )
    print("OK  — date source réelle extraite sans altération (ISO 8601) :", r["published_at"].isoformat())


def test_real_tavily_rfc2822_format_preserved():
    # Format RÉEL observé lors d'un appel Tavily live (2026-07-15, topic="news") :
    # RFC 2822, pas ISO 8601 — root cause du bug de parsing corrigé ici.
    results = [
        {"url": "https://example.com/z", "title": "Titre 2", "published_date": "Tue, 14 Jul 2026 03:45:58 GMT"},
    ]
    _attach_published_at(results)
    r = results[0]
    assert r["published_at"] == datetime(2026, 7, 14, 3, 45, 58, tzinfo=timezone.utc), (
        f"date RFC 2822 mal parsée : {r['published_at']}"
    )
    print("OK  — date source réelle extraite sans altération (RFC 2822, format Tavily réel) :", r["published_at"].isoformat())


def test_missing_date_marked_unconfirmed():
    results = [{"url": "https://example.com/y", "title": "Sans date"}]
    _attach_published_at(results)
    assert results[0]["published_at"] is None, "l'absence de date doit rester None (non confirmée), jamais devinée"
    print("OK  — absence de date source correctement marquée non confirmée (None)")


def test_blocks_inconsistent_date_in_body():
    # Réplique le cas réel observé : source publiée le 14 juillet 2026, mais
    # le corps généré affirme un événement "annoncé le 3 mars 2026".
    source_published_at = datetime(2026, 7, 14, 8, 0, tzinfo=timezone.utc)
    chapeau = "Conakry active un plan d'évacuation pour les Guinéens en Iran."
    corps_incoherent = (
        "Une cellule de crise a été constituée à Conakry. La démarche, "
        "annoncée le 3 mars 2026, prévoit un transfert via la Turquie."
    )
    violations = _validate_date_consistency(chapeau, corps_incoherent, source_published_at)
    assert violations, "une date incohérente (3 mars 2026 != 14 juillet 2026) aurait dû être détectée et bloquée"
    print("OK  — date incohérente détectée et bloquée :", violations[0])


def test_allows_consistent_date_in_body():
    source_published_at = datetime(2026, 7, 14, 8, 0, tzinfo=timezone.utc)
    chapeau = "Conakry active un plan d'évacuation pour les Guinéens en Iran."
    corps_coherent = (
        "Une cellule de crise a été constituée à Conakry. La démarche, "
        "annoncée le 14 juillet 2026, prévoit un transfert via la Turquie."
    )
    violations = _validate_date_consistency(chapeau, corps_coherent, source_published_at)
    assert not violations, f"aucune violation attendue (date cohérente avec la source), obtenu : {violations}"
    print("OK  — date cohérente avec la source acceptée sans violation")


def test_blocks_future_date_even_without_source_date():
    # Source sans date confirmée (published_at=None) : la règle "jamais de
    # date future" doit quand même s'appliquer.
    chapeau = "Un test."
    corps = "L'événement est prévu pour le 1 janvier 2099, une date qui n'existe pas encore."
    violations = _validate_date_consistency(chapeau, corps, None)
    assert violations, "une date future doit être bloquée même sans date source connue"
    print("OK  — date future bloquée même sans date source confirmée :", violations[0])


def test_extract_dates_helper():
    dates = _extract_mentioned_dates("Le 3 mars 2026 puis le 14 juillet 2026, deux événements distincts.")
    assert len(dates) == 2
    print("OK  — extraction de dates multiples :", [d.isoformat() for d in dates])


if __name__ == "__main__":
    test_real_source_date_preserved()
    test_real_tavily_rfc2822_format_preserved()
    test_missing_date_marked_unconfirmed()
    test_blocks_inconsistent_date_in_body()
    test_allows_consistent_date_in_body()
    test_blocks_future_date_even_without_source_date()
    test_extract_dates_helper()
    print("\nTous les tests de cohérence de date sont passés.")
