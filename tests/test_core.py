"""
Core tests, no network (point 26). The crawl is simulated with a hand-built
CrawledPage; providers with the MockProvider. No unit test depends on the
internet.
"""

import asyncio

from citerank import visibility
from citerank.analyzers import citability, schema_ld
from citerank.crawl import validate_url
from citerank.models import CrawledPage, Nature, now_iso
from citerank.providers import MockProvider


def _page(**kw) -> CrawledPage:
    base = dict(url="https://ex.test/", status=200, final_url="https://ex.test/",
                fetched_at=now_iso(), headers={"strict-transport-security": "x"},
                html="<html><body><p>x</p></body></html>", text="x")
    base.update(kw)
    return CrawledPage(**base)


def test_validate_url_blocks_internal():
    for bad in ["http://localhost/", "http://127.0.0.1/", "http://169.254.169.254/"]:
        try:
            validate_url(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad} should have been blocked")


def test_validate_url_accepts_public():
    assert validate_url("example.com").startswith("https://example.com")


def test_schema_detects_organization():
    page = _page(json_ld=[{"@type": "Organization", "name": "Acme", "sameAs": ["x"]}])
    score, findings = schema_ld.analyze(page)
    assert score.value >= 65
    assert not any(f.id == "org-schema-missing" for f in findings)


def test_schema_flags_absence():
    page = _page(json_ld=[])
    score, findings = schema_ld.analyze(page)
    assert any(f.id == "org-schema-missing" for f in findings)
    assert score.value < 30


def test_citability_is_inferred_not_measured():
    page = _page(html="<html><body><h2>What is X?</h2>"
                      "<p>X is a service created in 2021 that handles 40% of cases in 3 minutes.</p>"
                      "</body></html>")
    score, _ = citability.analyze(page)
    assert score.nature == Nature.INFERRED  # never presented as a fact


def test_visibility_without_provider_is_honest():
    res = asyncio.run(visibility.measure(["q"], brand="X", domain="x.test", providers=[]))
    s = visibility.visibility_score(res)
    assert s["measured"] is False
    assert s["score"] is None


def test_mock_is_flagged_fake():
    res = asyncio.run(visibility.measure(["q1", "q2"], brand="X", domain="x.test",
                                         providers=[MockProvider()]))
    s = visibility.visibility_score(res)
    assert s["measured"] is False           # the mock never counts as measured
    assert "FAKE" in s["warning"]


def test_explain_gap_is_backed_by_scores():
    """The competitive explanation only comes from measured gaps, never thin air."""
    from citerank.competitive import Comparison, explain_gap
    from citerank.models import Score, SiteAudit

    def audit(dom, schema_val):
        a = SiteAudit(url=f"https://{dom}", domain=dom, started_at=now_iso())
        a.scores.append(Score("schema", "Structured data", schema_val, Nature.MEASURED, 1.0))
        a.scores.append(Score("readiness", "Readiness", schema_val, Nature.MEASURED, 1.0))
        return a

    comp = Comparison(target=audit("me.test", 20), competitors=[audit("them.test", 85)])
    reasons = explain_gap(comp)
    assert any("them.test" in r and "85" in r for r in reasons)
    assert comp.target_rank() == (2, 2)


def test_remediation_never_fabricates():
    """A fix only fills derived facts; sameAs empty when not provided."""
    import json as _json
    from citerank.remediation import organization_jsonld
    page = _page(final_url="https://ex.test/", title="Great thing - Acme",
                 meta_description="A real description.")
    fix = organization_jsonld(page, None)          # no sameAs provided
    data = _json.loads(fix.content.split(">", 1)[1].rsplit("<", 1)[0])
    assert data["name"] == "Acme"                  # derived from the title, not invented
    assert data["url"] == "https://ex.test"
    assert "sameAs" not in data                    # never guessed
    fix2 = organization_jsonld(page, None, same_as=["https://linkedin.com/company/acme"])
    data2 = _json.loads(fix2.content.split(">", 1)[1].rsplit("<", 1)[0])
    assert data2["sameAs"] == ["https://linkedin.com/company/acme"]


def test_compare_detects_regression():
    """The over-time comparison catches drops, not just gains."""
    from citerank.history import compare
    old = {"started_at": "2026-08-01", "overall_ai_search_score": 60,
           "scores": [{"key": "schema", "value": 80}, {"key": "technical", "value": 90}]}
    new = {"started_at": "2026-08-09", "overall_ai_search_score": 52,
           "scores": [{"key": "schema", "value": 55}, {"key": "technical", "value": 90}]}
    d = compare(old, new)
    assert d["overall"]["delta"] == -8
    assert any(r["key"] == "schema" for r in d["regressions"])
    assert not d["gains"]


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for fn in fns:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"  ✗ {fn.__name__}: {e}")
    print(f"\n  {len(fns) - failures}/{len(fns)} tests passing")
    sys.exit(1 if failures else 0)
