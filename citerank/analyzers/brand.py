"""
Brand Authority analyzer.

The last dimension the upstream graded and we lacked. AI engines lean on
third-party corroboration to trust a brand: does it link its social profiles, is
it on Wikipedia/Wikidata, does it show review signals, is it listed in
directories? An entity that other trusted sources verify is one an AI cites with
confidence.

Everything here is OBSERVED (links seen on the page) or MEASURED (counts) — never
inferred. Local, deterministic, no LLM.
"""

from __future__ import annotations

import re

from ..models import CrawledPage, Finding, Nature, Score, ScoreComponent, Severity

# Social / professional platforms whose presence signals a real, verifiable entity.
_SOCIAL = {
    "LinkedIn": r"linkedin\.com",
    "X/Twitter": r"(twitter\.com|x\.com)/",
    "GitHub": r"github\.com",
    "YouTube": r"youtube\.com|youtu\.be",
    "Instagram": r"instagram\.com",
    "Facebook": r"facebook\.com",
    "TikTok": r"tiktok\.com",
    "Mastodon": r"@[\w.]+@[\w.]+",
}
_ENCYCLOPEDIC = r"(wikipedia\.org|wikidata\.org)"
_REVIEW_SITES = r"(trustpilot\.com|g2\.com|capterra\.com|producthunt\.com|glassdoor\.)"
_DIRECTORIES = r"(crunchbase\.com|bloomberg\.com|angel\.co|wellfound\.com)"


def _haystack(page: CrawledPage) -> str:
    # External links + the raw HTML (sameAs lives in JSON-LD, not in <a>).
    return (" ".join(page.links_external) + " " + page.html).lower()


def analyze(page: CrawledPage) -> tuple[Score, list[Finding]]:
    findings: list[Finding] = []
    comps: list[ScoreComponent] = []
    hay = _haystack(page)

    # -- Social presence (35 pts) ------------------------------------------
    present = [name for name, rx in _SOCIAL.items() if re.search(rx, hay)]
    pts_social = min(35, 7 * len(present))
    comps.append(ScoreComponent("social", "Linked social profiles", pts_social, 35,
                                Nature.OBSERVED, ", ".join(present) or "none"))
    if len(present) < 2:
        findings.append(Finding(
            id="weak-social", title="Few or no linked social profiles",
            severity=Severity.LOW, nature=Nature.OBSERVED, confidence=0.8,
            category="brand", source=page.final_url,
            detail=f"Detected: {', '.join(present) or 'none'}.",
            recommendation="Link the brand's real profiles (LinkedIn, X, GitHub…) and "
                           "mirror them in Organization.sameAs — they corroborate the entity."))

    # -- Encyclopedic authority (25 pts) -----------------------------------
    has_encyc = bool(re.search(_ENCYCLOPEDIC, hay))
    comps.append(ScoreComponent("encyclopedic", "Wikipedia / Wikidata reference",
                                25 if has_encyc else 0, 25, Nature.OBSERVED,
                                "present" if has_encyc else "none"))
    if not has_encyc:
        findings.append(Finding(
            id="no-encyclopedic", title="No Wikipedia / Wikidata link",
            severity=Severity.INFO, nature=Nature.OBSERVED, confidence=0.7,
            category="brand", source=page.final_url,
            detail="A Wikipedia or Wikidata entry is one of the strongest entity-trust signals.",
            recommendation="If eligible, establish a Wikidata item and reference it via sameAs."))

    # -- Review signals (20 pts) -------------------------------------------
    has_reviews = bool(re.search(_REVIEW_SITES, hay)) or "aggregaterating" in hay
    comps.append(ScoreComponent("reviews", "Review / rating signals",
                                20 if has_reviews else 0, 20, Nature.OBSERVED,
                                "present" if has_reviews else "none"))

    # -- Directory / identifier (20 pts) -----------------------------------
    has_dir = bool(re.search(_DIRECTORIES, hay))
    comps.append(ScoreComponent("directory", "Directory / registry presence",
                                20 if has_dir else 0, 20, Nature.OBSERVED,
                                "present" if has_dir else "none"))

    score = Score(
        key="brand", label="Brand Authority",
        value=sum(c.points for c in comps), nature=Nature.OBSERVED, confidence=0.8,
        components=comps,
        methodology="Observed third-party corroboration: linked social profiles, a "
                    "Wikipedia/Wikidata reference, review signals, and directory presence. "
                    "The signals AI engines use to trust that an entity is real.",
    )
    return score, findings
