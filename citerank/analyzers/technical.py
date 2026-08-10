"""
Technical analyzer: robots.txt, sitemap, llms.txt, AI-crawler access, headers,
canonical, language.

100% local and deterministic. No AI-engine call. This is the brick that enables
a free, unlimited audit (point 31) — the acquisition layer.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import aiohttp

from ..crawl import Crawler
from ..models import CrawledPage, Finding, Nature, Score, ScoreComponent, Severity, SiteContext

# AI crawlers to consider explicitly. Blocking GPTBot means going invisible to
# ChatGPT; it's a legitimate choice, but it must be a conscious one.
AI_CRAWLERS = ["GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot",
               "Claude-Web", "PerplexityBot", "Google-Extended", "CCBot"]


async def analyze(url: str, crawler: Crawler, session: aiohttp.ClientSession,
                  page: CrawledPage) -> tuple[Score, list[Finding], SiteContext]:
    base = urlparse(page.final_url)
    root = f"{base.scheme}://{base.netloc}"

    robots = await crawler.fetch_text(root + "/robots.txt", session)
    llms = await crawler.fetch_text(root + "/llms.txt", session)
    sitemap = await crawler.fetch_text(root + "/sitemap.xml", session)

    findings: list[Finding] = []
    comps: list[ScoreComponent] = []

    # -- AI-crawler access (25 pts) ----------------------------------------
    blocked = _blocked_crawlers(robots)
    if not blocked:
        comps.append(ScoreComponent("ai_crawlers", "AI crawlers allowed", 25, 25,
                                    Nature.MEASURED, "no AI bot blocked"))
    else:
        lost = min(25, 4 * len(blocked))
        comps.append(ScoreComponent("ai_crawlers", "AI crawlers allowed",
                                    25 - lost, 25, Nature.MEASURED,
                                    f"blocked: {', '.join(blocked)}"))
        findings.append(Finding(
            id="ai-crawler-blocked", title="AI crawlers blocked by robots.txt",
            severity=Severity.HIGH, nature=Nature.MEASURED, confidence=1.0,
            category="crawlers", source=root + "/robots.txt",
            detail=f"Blocked bots: {', '.join(blocked)}",
            evidence=_robots_excerpt(robots),
            recommendation="Remove these agents from Disallow if AI visibility is wanted.",
        ))

    # -- Sitemap (15 pts) --------------------------------------------------
    has_sitemap = bool(sitemap.strip()) and "<urlset" in sitemap or "<sitemapindex" in sitemap
    comps.append(ScoreComponent("sitemap", "XML sitemap", 15 if has_sitemap else 0, 15,
                                Nature.MEASURED, "present" if has_sitemap else "absent"))
    if not has_sitemap:
        findings.append(Finding(
            id="sitemap-missing", title="XML sitemap missing", severity=Severity.MEDIUM,
            nature=Nature.MEASURED, confidence=1.0, category="technical",
            source=root + "/sitemap.xml",
            recommendation="Publish /sitemap.xml to guide crawling.",
        ))

    # -- llms.txt (15 pts) — emerging standard, bonus, not a requirement ---
    has_llms = bool(llms.strip())
    comps.append(ScoreComponent("llms_txt", "llms.txt", 15 if has_llms else 0, 15,
                                Nature.MEASURED, "present" if has_llms else "absent"))
    if not has_llms:
        findings.append(Finding(
            id="llmstxt-missing", title="llms.txt missing",
            severity=Severity.LOW, nature=Nature.RECOMMENDED, confidence=0.7,
            category="crawlers", source=root + "/llms.txt",
            detail="Emerging standard that exposes a content map to AI engines.",
            recommendation="Generate a /llms.txt listing the reference pages.",
        ))

    # -- HTTPS + headers (15 pts) ------------------------------------------
    is_https = base.scheme == "https"
    hsts = "strict-transport-security" in page.headers
    pts = (10 if is_https else 0) + (5 if hsts else 0)
    comps.append(ScoreComponent("transport", "HTTPS & HSTS", pts, 15, Nature.MEASURED,
                                f"https={is_https}, hsts={hsts}"))
    if not is_https:
        findings.append(Finding(
            id="no-https", title="Site not served over HTTPS", severity=Severity.CRITICAL,
            nature=Nature.MEASURED, confidence=1.0, category="technical",
            source=page.final_url, recommendation="Serve the whole site over HTTPS."))

    # -- Head tags (15 pts) ------------------------------------------------
    pts_meta = 0
    if page.title:
        pts_meta += 6
    else:
        findings.append(Finding("title-missing", "<title> tag missing",
                                Severity.HIGH, Nature.MEASURED, 1.0, "technical",
                                page.final_url, recommendation="Add a descriptive <title>."))
    if page.meta_description:
        pts_meta += 5
    else:
        findings.append(Finding("meta-desc-missing", "Meta description missing",
                                Severity.MEDIUM, Nature.MEASURED, 1.0, "technical",
                                page.final_url, recommendation="Add a meta description."))
    if page.lang:
        pts_meta += 4
    else:
        findings.append(Finding("lang-missing", "lang attribute missing on <html>",
                                Severity.LOW, Nature.MEASURED, 1.0, "technical",
                                page.final_url,
                                recommendation="Declare the language (e.g. <html lang=\"en\">)."))
    comps.append(ScoreComponent("head", "Head tags", pts_meta, 15, Nature.MEASURED))

    # -- Heading structure (15 pts) ----------------------------------------
    n_h1 = len(page.h1)
    if n_h1 == 1:
        pts_h1, det = 15, "a single H1, ideal"
    elif n_h1 == 0:
        pts_h1, det = 0, "no H1"
        findings.append(Finding("h1-missing", "No H1 heading", Severity.MEDIUM,
                                Nature.OBSERVED, 1.0, "content", page.final_url,
                                recommendation="Add a single, descriptive H1."))
    else:
        pts_h1, det = 7, f"{n_h1} H1s (a single one is recommended)"
        findings.append(Finding("h1-multiple", f"{n_h1} H1 tags", Severity.LOW,
                                Nature.OBSERVED, 1.0, "content", page.final_url,
                                recommendation="Keep a single H1 per page."))
    comps.append(ScoreComponent("headings", "Heading structure", pts_h1, 15,
                                Nature.OBSERVED, det))

    # -- Discoverability meta (15 pts): canonical, Open Graph, Twitter, viewport, favicon
    html = page.html
    has_canonical = bool(re.search(r'<link[^>]+rel=["\']canonical["\']', html, re.IGNORECASE))
    has_og = bool(re.search(r'<meta[^>]+property=["\']og:(title|description|image)["\']', html, re.IGNORECASE))
    has_twitter = bool(re.search(r'<meta[^>]+name=["\']twitter:card["\']', html, re.IGNORECASE))
    has_viewport = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.IGNORECASE))
    has_favicon = bool(re.search(r'<link[^>]+rel=["\'][^"\']*icon', html, re.IGNORECASE))
    pts_disc = (sum([has_canonical, has_og, has_twitter, has_viewport, has_favicon]) * 3)
    comps.append(ScoreComponent("discovery", "Discoverability meta", pts_disc, 15, Nature.MEASURED,
                                f"canonical={has_canonical}, og={has_og}, twitter={has_twitter}, "
                                f"viewport={has_viewport}, favicon={has_favicon}"))
    if not has_canonical:
        findings.append(Finding("no-canonical", "No canonical URL", Severity.LOW,
                                Nature.MEASURED, 1.0, "technical", page.final_url,
                                recommendation="Add <link rel=\"canonical\"> to prevent duplicate-content dilution."))
    if not has_og:
        findings.append(Finding("no-opengraph", "No Open Graph tags", Severity.LOW,
                                Nature.MEASURED, 1.0, "technical", page.final_url,
                                detail="Open Graph controls how the page appears when shared and previewed.",
                                recommendation="Add og:title, og:description and og:image."))

    # -- Indexability (10 pts): a noindex here is a silent killer ----------
    noindex = bool(re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'][^"\']*noindex', html, re.IGNORECASE))
    comps.append(ScoreComponent("indexable", "Indexable (no meta noindex)",
                                0 if noindex else 10, 10, Nature.MEASURED,
                                "noindex present" if noindex else "indexable"))
    if noindex:
        findings.append(Finding("meta-noindex", "Page marked noindex", Severity.HIGH,
                                Nature.MEASURED, 1.0, "technical", page.final_url,
                                detail="A meta robots noindex tells engines to skip this page entirely.",
                                recommendation="Remove the noindex directive if this page should be found."))

    score = Score(
        key="technical", label="Technical SEO",
        value=round(sum(c.points for c in comps) / sum(c.max_points for c in comps) * 100, 1),
        nature=Nature.MEASURED, confidence=1.0, components=comps,
        methodology="Normalized sum of measured components: AI-crawler access, sitemap, "
                    "llms.txt, transport, head tags, heading structure, discoverability "
                    "meta (canonical/OG/Twitter/viewport/favicon), and indexability.",
    )
    ctx = SiteContext(url=page.final_url, domain=base.netloc, robots_txt=robots,
                      llms_txt=llms, sitemap_present=has_sitemap)
    return score, findings, ctx


def _blocked_crawlers(robots: str) -> list[str]:
    """Spot AI agents under a Disallow: / in robots.txt."""
    blocked = []
    disallowed = {}
    current_agent = None
    for line in robots.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        key, _, val = s.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent":
            current_agent = val
            disallowed.setdefault(current_agent, False)
        elif key == "disallow" and current_agent is not None:
            if val == "/":
                disallowed[current_agent] = True
    for agent, banned in disallowed.items():
        if not banned:
            continue
        if agent == "*":
            blocked.extend(AI_CRAWLERS)  # * blocks everything, AI included
        else:
            for c in AI_CRAWLERS:
                if c.lower() == agent.lower():
                    blocked.append(c)
    return sorted(set(blocked))


def _robots_excerpt(robots: str) -> str:
    lines = [line for line in robots.splitlines() if line.strip()][:12]
    return "\n".join(lines)
