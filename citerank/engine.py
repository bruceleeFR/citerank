"""
Engine orchestrator.

This is THE entry point of the core, independent of any interface (point 37). The
Claude Code skill, the CLI, a future REST API and the Lamarca SaaS all call
`audit()` / `readiness_score()` — they reimplement nothing, they wrap. Business
logic never lives in a skill Markdown file.

An audit crawls the home page plus a handful of key internal pages (about,
pricing, blog, …), runs the local analyzers on each, and aggregates: site-wide
signals (robots/sitemap/llms.txt/transport) come from the home page, page-level
signals (schema, citability, content) are averaged across the pages crawled. The
crawl is shared and cached (point 23), and each URL is SSRF-validated. All local,
deterministic, keyless — the free layer.
"""

from __future__ import annotations

import re
from statistics import mean
from urllib.parse import urlparse

from .analyzers import brand, citability, content, schema_ld, technical
from .crawl import Crawler, new_session, validate_url
from .models import (
    CrawledPage,
    Finding,
    Nature,
    Score,
    ScoreComponent,
    Severity,
    SiteAudit,
    now_iso,
)

# Sections worth sampling first: they carry the entity, the offer and the depth.
_PRIORITY = ("about", "a-propos", "qui-sommes", "contact", "pricing", "tarifs",
             "price", "product", "produit", "service", "feature", "solution",
             "blog", "docs", "faq", "team", "equipe", "case", "customer",
             "work", "portfolio", "how-it-works")
_SKIP_EXT = re.compile(r"\.(pdf|jpe?g|png|gif|svg|webp|ico|css|js|zip|mp4|xml|json)$", re.IGNORECASE)


def _pick_pages(home: CrawledPage, n: int) -> list[str]:
    """Choose up to n internal pages with distinct first path segments, meaningful ones first."""
    def rank(u: str) -> int:
        path = urlparse(u).path.lower()
        return 0 if any(k in path for k in _PRIORITY) else 1

    seen_seg: set[str] = set()
    picked: list[str] = []
    for u in sorted(home.links_internal, key=rank):
        path = urlparse(u).path.rstrip("/")
        if not path or _SKIP_EXT.search(path):
            continue
        seg = path.strip("/").split("/")[0]
        if seg in seen_seg:
            continue
        seen_seg.add(seg)
        picked.append(u)
        if len(picked) >= n:
            break
    return picked


def _average(scores: list[Score], key: str, label: str, methodology: str) -> Score:
    """Aggregate a per-page dimension across pages by averaging its value."""
    vals = [s.value for s in scores]
    nat = scores[0].nature
    conf = scores[0].confidence
    # Keep the strongest page's components for the breakdown — the reader sees
    # concrete signals, and the value reflects the whole set.
    best = max(scores, key=lambda s: s.value)
    return Score(key=key, label=label, value=round(mean(vals), 1), nature=nat,
                 confidence=conf, components=best.components,
                 methodology=methodology + f" Averaged over {len(scores)} page(s).")


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    """
    Collapse the same finding seen on several pages into one, noting the count.
    Without this a 6-page crawl would print "Organization schema missing" six times.
    """
    by_id: dict[str, list[Finding]] = {}
    for f in findings:
        by_id.setdefault(f.id, []).append(f)
    out: list[Finding] = []
    for group in by_id.values():
        f = group[0]
        if len(group) > 1:
            extra = f" (on {len(group)} pages)"
            f = Finding(id=f.id, title=f.title, severity=f.severity, nature=f.nature,
                        confidence=f.confidence, category=f.category, source=f.source,
                        detail=(f.detail + extra).strip(), recommendation=f.recommendation,
                        evidence=f.evidence)
        out.append(f)
    return out


async def audit(url: str, *, allow_local: bool = False, max_pages: int = 5) -> SiteAudit:
    """
    Full Readiness audit, 100% local. Runs NO AI engine — this is the free layer.
    Crawls up to `max_pages` (home + key internal pages); set max_pages=1 for a
    single-page audit. Visibility (paid, costly) is a separate call.
    """
    url = validate_url(url, allow_local)
    domain = urlparse(url).netloc
    result = SiteAudit(url=url, domain=domain, started_at=now_iso())

    crawler = Crawler(allow_local=allow_local)
    async with new_session() as session:
        home = await crawler.get(url, session)
        if not home.ok:
            result.finished_at = now_iso()
            result.findings.append(Finding(
                id="fetch-failed", title="Page unreachable",
                severity=Severity.CRITICAL, nature=Nature.MEASURED, confidence=1.0,
                category="technical", source=url,
                detail=home.error or f"HTTP {home.status}",
                recommendation="Check that the URL is public and returns 200."))
            return result

        # Site-wide technical (robots/sitemap/llms.txt/transport) from the home page.
        s_tech, f_tech, ctx = await technical.analyze(url, crawler, session, home)

        pages = [home]
        if max_pages > 1:
            for u in _pick_pages(home, max_pages - 1):
                p = await crawler.get(u, session)
                if p.ok:
                    pages.append(p)

        # Page-level dimensions, run on every crawled page.
        schema_scores, cite_scores, content_scores, brand_scores = [], [], [], []
        page_findings: list[Finding] = []
        for p in pages:
            ss, sf = schema_ld.analyze(p)
            cs, cf = citability.analyze(p)
            cts, ctf = content.analyze(p)
            bs, bf = brand.analyze(p)
            schema_scores.append(ss)
            cite_scores.append(cs)
            content_scores.append(cts)
            brand_scores.append(bs)
            page_findings.extend([*sf, *cf, *ctf, *bf])

    result.context = ctx
    result.pages_crawled = len(pages)

    s_schema = _average(schema_scores, "schema", "Structured data",
                        "Entity schema, sameAs, type richness and JSON-LD validity.")
    s_cite = _average(cite_scores, "citability", "Citability",
                      "Per-passage semantic signals; word count is only a minor factor.")
    s_content = _average(content_scores, "content", "Content & E-E-A-T",
                         "Observed E-E-A-T signals: depth, authorship, freshness, references, "
                         "trust surface, alt coverage.")
    s_brand = _average(brand_scores, "brand", "Brand Authority",
                       "Third-party corroboration: social profiles, Wikipedia/Wikidata, "
                       "reviews, directories.")

    readiness = _composite_readiness(s_tech, s_schema, s_cite)
    result.scores = [readiness, s_tech, s_schema, s_cite, s_content, s_brand]
    result.findings = _dedupe_findings([*f_tech, *page_findings])

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
