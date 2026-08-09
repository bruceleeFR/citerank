"""
Tests du cœur, sans réseau (point 26). Le crawl est simulé par une CrawledPage
fabriquée à la main ; les fournisseurs par le MockProvider. Aucun test unitaire
ne dépend d'Internet.
"""

import asyncio

from citerank.models import CrawledPage, Nature, now_iso
from citerank.analyzers import schema_ld, citability
from citerank.crawl import valider_url
from citerank.providers import MockProvider
from citerank import visibility


def _page(**kw) -> CrawledPage:
    base = dict(url="https://ex.test/", status=200, final_url="https://ex.test/",
                fetched_at=now_iso(), headers={"strict-transport-security": "x"},
                html="<html><body><p>x</p></body></html>", text="x")
    base.update(kw)
    return CrawledPage(**base)


def test_validation_url_bloque_interne():
    for mauvais in ["http://localhost/", "http://127.0.0.1/", "http://169.254.169.254/"]:
        try:
            valider_url(mauvais)
        except ValueError:
            continue
        raise AssertionError(f"{mauvais} aurait dû être bloqué")


def test_validation_url_accepte_public():
    assert valider_url("example.com").startswith("https://example.com")


def test_schema_detecte_organization():
    page = _page(json_ld=[{"@type": "Organization", "name": "Acme", "sameAs": ["x"]}])
    score, findings = schema_ld.analyser(page)
    assert score.value >= 65
    assert not any(f.id == "org-schema-missing" for f in findings)


def test_schema_signale_absence():
    page = _page(json_ld=[])
    score, findings = schema_ld.analyser(page)
    assert any(f.id == "org-schema-missing" for f in findings)
    assert score.value < 30


def test_citabilite_est_deduite_pas_mesuree():
    page = _page(html="<html><body><h2>Qu'est-ce que X ?</h2>"
                      "<p>X est un service créé en 2021 qui traite 40% des cas en 3 minutes.</p>"
                      "</body></html>")
    score, _ = citability.analyser(page)
    assert score.nature == Nature.INFERRED  # jamais présenté comme un fait


def test_visibilite_sans_fournisseur_est_honnete():
    res = asyncio.run(visibility.mesurer(["q"], marque="X", domaine="x.test", providers=[]))
    s = visibility.score_visibilite(res)
    assert s["mesuré"] is False
    assert s["score"] is None


def test_mock_est_marque_factice():
    res = asyncio.run(visibility.mesurer(["q1", "q2"], marque="X", domaine="x.test",
                                         providers=[MockProvider()]))
    s = visibility.score_visibilite(res)
    assert s["mesuré"] is False           # le mock ne compte jamais comme mesuré
    assert "FACTICES" in s["avertissement"]


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    échecs = 0
    for fn in fns:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
        except AssertionError as e:
            échecs += 1
            print(f"  ✗ {fn.__name__} : {e}")
    print(f"\n  {len(fns) - échecs}/{len(fns)} tests au vert")
    sys.exit(1 if échecs else 0)
