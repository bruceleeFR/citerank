"""
Content & E-E-A-T analyzer.

The dimension the scan was missing. AI engines don't just parse structure — they
weigh whether a page shows Experience, Expertise, Authoritativeness and Trust:
who wrote it, when, how deep it is, whether it cites sources, whether the site
is contactable. This is exactly what the upstream tool grades under "Content
Quality & E-E-A-T", and it's where our scan was thin.

Everything here is OBSERVED (seen on the page) or MEASURED (counts) — never
inferred. Local, deterministic, no LLM.
"""

from __future__ import annotations

import re

from ..models import CrawledPage, Finding, Nature, Score, ScoreComponent, Severity


def _json_ld_flat(page: CrawledPage) -> list[dict]:
    out = []
    for b in page.json_ld:
        if isinstance(b, dict):
            out.append(b)
            for sub in b.get("@graph", []) if isinstance(b.get("@graph"), list) else []:
                if isinstance(sub, dict):
                    out.append(sub)
    return out


def _has_key_deep(blocks: list[dict], key: str) -> bool:
    return any(key in b for b in blocks)


def analyze(page: CrawledPage) -> tuple[Score, list[Finding]]:
    findings: list[Finding] = []
    comps: list[ScoreComponent] = []
    blocks = _json_ld_flat(page)
    words = len(page.text.split())

    # -- Depth of content (25 pts) -----------------------------------------
    # AI engines rarely cite a thin page. Not a hard rule — a plateau.
    if words >= 600:
        pts_depth, det = 25, f"{words} words"
    elif words >= 250:
        pts_depth, det = 16, f"{words} words (fuller is better)"
    else:
        pts_depth, det = 6, f"only {words} words"
        findings.append(Finding(
            id="thin-content", title="Thin page content",
            severity=Severity.MEDIUM, nature=Nature.MEASURED, confidence=1.0,
            category="content", source=page.final_url,
            detail=f"About {words} words of visible text.",
            recommendation="Add substantive, self-contained content — depth is what gets cited."))
    comps.append(ScoreComponent("depth", "Content depth", pts_depth, 25, Nature.MEASURED, det))

    # -- Authorship / E-E-A-T (20 pts) -------------------------------------
    has_author = (
        _has_key_deep(blocks, "author")
        or any(str(b.get("@type", "")).endswith("Person") for b in blocks)
        or bool(re.search(r'<meta[^>]+name=["\']author["\']', page.html, re.IGNORECASE))
        or bool(re.search(r'rel=["\']author["\']', page.html, re.IGNORECASE))
    )
    comps.append(ScoreComponent("author", "Author / byline", 20 if has_author else 0, 20,
                                Nature.OBSERVED, "present" if has_author else "none"))
    if not has_author:
        findings.append(Finding(
            id="no-author", title="No author or byline signal",
            severity=Severity.LOW, nature=Nature.OBSERVED, confidence=0.8,
            category="content", source=page.final_url,
            detail="AI engines weigh who stands behind content (the first E in E-E-A-T).",
            recommendation="Add author markup (Person schema or a visible byline)."))

    # -- Freshness (15 pts) ------------------------------------------------
    has_date = (
        _has_key_deep(blocks, "datePublished") or _has_key_deep(blocks, "dateModified")
        or bool(re.search(r'article:(published|modified)_time', page.html, re.IGNORECASE))
        or bool(re.search(r'<time[^>]+datetime=', page.html, re.IGNORECASE))
    )
    comps.append(ScoreComponent("freshness", "Date / freshness", 15 if has_date else 0, 15,
                                Nature.OBSERVED, "dated" if has_date else "no date"))
    if not has_date:
        findings.append(Finding(
            id="no-date", title="No publish / update date",
            severity=Severity.LOW, nature=Nature.OBSERVED, confidence=0.7,
            category="content", source=page.final_url,
            recommendation="Expose datePublished / dateModified — recency is a ranking signal."))

    # -- References / citations (15 pts) -----------------------------------
    ext = len(page.links_external)
    if ext >= 3:
        pts_ref, det = 15, f"{ext} external references"
    elif ext >= 1:
        pts_ref, det = 8, f"{ext} external reference(s)"
    else:
        pts_ref, det = 0, "no outbound references"
        findings.append(Finding(
            id="no-references", title="No outbound references",
            severity=Severity.LOW, nature=Nature.MEASURED, confidence=0.9,
            category="content", source=page.final_url,
            detail="Pages that cite sources read as more trustworthy to AI engines.",
            recommendation="Link out to authoritative sources where relevant."))
    comps.append(ScoreComponent("references", "Outbound references", pts_ref, 15, Nature.MEASURED, det))

    # -- Trust surface: about / contact reachable (10 pts) -----------------
    internal_join = " ".join(page.links_internal).lower()
    has_about = any(k in internal_join for k in ("/about", "/a-propos", "/qui-sommes"))
    has_contact = any(k in internal_join for k in ("/contact", "mailto:")) or "mailto:" in page.html.lower()
    trust = (5 if has_about else 0) + (5 if has_contact else 0)
    comps.append(ScoreComponent("trust", "About / contact reachable", trust, 10,
                                Nature.OBSERVED, f"about={has_about}, contact={has_contact}"))
    if trust < 10:
        findings.append(Finding(
            id="weak-trust-surface", title="Weak trust surface (about/contact)",
            severity=Severity.LOW, nature=Nature.OBSERVED, confidence=0.7,
            category="content", source=page.final_url,
            recommendation="Link an About and a Contact page — a real, reachable entity scores higher."))

    # -- Image alt coverage (15 pts) — accessibility & extractability ------
    imgs = re.findall(r"<img\b[^>]*>", page.html, re.IGNORECASE)
    with_alt = [i for i in imgs if re.search(r'\balt=["\'][^"\']', i)]
    if not imgs:
        pts_alt, det = 15, "no images"
    else:
        cover = len(with_alt) / len(imgs)
        pts_alt = round(15 * cover)
        det = f"{len(with_alt)}/{len(imgs)} images have alt text"
        if cover < 0.6:
            findings.append(Finding(
                id="low-alt-coverage", title="Many images missing alt text",
                severity=Severity.LOW, nature=Nature.MEASURED, confidence=1.0,
                category="content", source=page.final_url,
                detail=det,
                recommendation="Add descriptive alt text — it's content an engine can read."))
    comps.append(ScoreComponent("alt", "Image alt coverage", pts_alt, 15, Nature.MEASURED, det))

    score = Score(
        key="content", label="Content & E-E-A-T",
        value=sum(c.points for c in comps), nature=Nature.OBSERVED, confidence=0.85,
        components=comps,
        methodology="Observed E-E-A-T signals: content depth, authorship, freshness, "
                    "outbound references, an about/contact trust surface, and image alt "
                    "coverage. All measured or observed on the page — never inferred.",
    )
    return score, findings
