"""
Engine orchestrator.

This is THE entry point of the core, independent of any interface (point 37). The
Claude Code skill, the CLI, a future REST API and the Lamarca SaaS all call
`audit()` / `readiness_score()` — they reimplement nothing, they wrap. Business
logic never lives in a skill Markdown file.

The crawl happens once and is shared (point 23). The local analyzers are
deterministic and keyless: a Readiness audit runs offline, for free, on any URL.
"""

from __future__ import annotations

from urllib.parse import urlparse

from .analyzers import citability, content, schema_ld, technical
from .crawl import Crawler, new_session, validate_url
from .models import Nature, Score, ScoreComponent, SiteAudit, now_iso


async def audit(url: str, *, allow_local: bool = False) -> SiteAudit:
    """
    Full Readiness audit, 100% local. Runs NO AI engine — this is the free
    layer. Visibility (paid, costly) is a separate call.
    """
    url = validate_url(url, allow_local)
    domain = urlparse(url).netloc
    result = SiteAudit(url=url, domain=domain, started_at=now_iso())

    crawler = Crawler(allow_local=allow_local)
    async with new_session() as session:
        page = await crawler.get(url, session)

        if not page.ok:
            result.finished_at = now_iso()
            from .models import Finding, Severity
            result.findings.append(Finding(
                id="fetch-failed", title="Page unreachable",
                severity=Severity.CRITICAL, nature=Nature.MEASURED, confidence=1.0,
                category="technical", source=url,
                detail=page.error or f"HTTP {page.status}",
                recommendation="Check that the URL is public and returns 200."))
            return result

        s_tech, f_tech, ctx = await technical.analyze(url, crawler, session, page)
        s_schema, f_schema = schema_ld.analyze(page)
        s_cite, f_cite = citability.analyze(page)
        s_content, f_content = content.analyze(page)

    result.context = ctx
    result.scores.extend([s_tech, s_schema, s_cite, s_content])
    result.findings.extend([*f_tech, *f_schema, *f_cite, *f_content])

    # The READINESS score is an explicit composite of the three local axes. We
    # name it and separate it from Visibility: a perfectly prepared site is not
    # necessarily cited (the spec's A/B distinction, point 1).
    readiness = _composite_readiness(s_tech, s_schema, s_cite)
    result.scores.insert(0, readiness)

    result.finished_at = now_iso()
    return result


def _composite_readiness(s_tech: Score, s_schema: Score, s_cite: Score) -> Score:
    weights = {"technical": 0.45, "schema": 0.30, "citability": 0.25}
    comps = [
        ScoreComponent(s.key, s.label, s.value * weights[s.key], weights[s.key] * 100,
                       s.nature, f"{s.value:.0f}/100 weighted {int(weights[s.key]*100)}%")
        for s in (s_tech, s_schema, s_cite)
    ]
    value = sum(c.points for c in comps)
    return Score(
        key="readiness", label="AI Readiness",
        value=value, nature=Nature.MEASURED, confidence=0.9, components=comps,
        methodology="Weighted composite: technical 45%, structured data 30%, "
                    "citability 25%. Measures the site's PREPARATION, distinct "
                    "from its actual visibility in AI answers.",
    )


async def readiness_score(url: str, *, allow_local: bool = False) -> float:
    """Shortcut: the Readiness score alone."""
    a = await audit(url, allow_local=allow_local)
    s = a.score("readiness")
    return s.value if s else 0.0
