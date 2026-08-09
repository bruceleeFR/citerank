"""
Structured-data (JSON-LD) analyzer.

What AI engines read to understand WHO you are and WHAT you offer. We separate
the types that carry entity identity (Organization, Person, LocalBusiness) from
transactional types (Product, FAQPage, Article): the former weigh more, because
they are what makes a brand disambiguable to an AI.
"""

from __future__ import annotations

from ..models import CrawledPage, Finding, Nature, Score, ScoreComponent, Severity

ENTITY_TYPES = {"Organization", "Corporation", "LocalBusiness", "Person"}
USEFUL_TYPES = {"Product", "Offer", "FAQPage", "Article", "BreadcrumbList",
                "WebSite", "SoftwareApplication", "Review", "AggregateRating"}


def _types_of(block: dict) -> set[str]:
    t = block.get("@type", "")
    if isinstance(t, list):
        return {str(x) for x in t}
    return {str(t)} if t else set()


def analyze(page: CrawledPage) -> tuple[Score, list[Finding]]:
    findings: list[Finding] = []
    comps: list[ScoreComponent] = []

    all_types: set[str] = set()
    for block in page.json_ld:
        all_types |= _types_of(block)
    # @graph: some sites nest their entities.
    for block in page.json_ld:
        for sub in (block.get("@graph", []) if isinstance(block, dict) else []):
            if isinstance(sub, dict):
                all_types |= _types_of(sub)

    # -- Entity schema present (40 pts) ------------------------------------
    has_entity = bool(all_types & ENTITY_TYPES)
    comps.append(ScoreComponent("entity_schema", "Entity schema (Organization/Person)",
                                40 if has_entity else 0, 40, Nature.MEASURED,
                                ", ".join(sorted(all_types & ENTITY_TYPES)) or "absent"))
    if not has_entity:
        findings.append(Finding(
            id="org-schema-missing", title="Organization schema missing",
            severity=Severity.HIGH, nature=Nature.MEASURED, confidence=1.0,
            category="schema", source=page.final_url,
            detail="Without Organization/LocalBusiness, an AI struggles to identify the brand.",
            recommendation="Add an Organization JSON-LD block with name, url, logo, sameAs.",
            evidence=f"Types found: {', '.join(sorted(all_types)) or 'none'}",
        ))

    # -- sameAs: the bridge to entities that verify you (25 pts) -----------
    has_sameas = any("sameAs" in b for b in page.json_ld if isinstance(b, dict))
    comps.append(ScoreComponent("sameas", "sameAs links (external profiles)",
                                25 if has_sameas else 0, 25, Nature.MEASURED,
                                "present" if has_sameas else "absent"))
    if has_entity and not has_sameas:
        findings.append(Finding(
            id="sameas-missing", title="sameAs property missing",
            severity=Severity.MEDIUM, nature=Nature.MEASURED, confidence=1.0,
            category="schema", source=page.final_url,
            detail="sameAs links the entity to its profiles (LinkedIn, Wikidata, Crunchbase).",
            recommendation="Add sameAs pointing to the brand's verifiable profiles.",
        ))

    # -- Richness (20 pts): useful types present ---------------------------
    useful = all_types & USEFUL_TYPES
    pts_useful = min(20, 5 * len(useful))
    comps.append(ScoreComponent("richness", "Useful structured types",
                                pts_useful, 20, Nature.MEASURED,
                                ", ".join(sorted(useful)) or "none"))

    # -- Validity (15 pts): broken JSON-LD counts as absent ----------------
    has_json = bool(page.json_ld)
    comps.append(ScoreComponent("presence", "Valid JSON-LD present",
                                15 if has_json else 0, 15, Nature.MEASURED,
                                f"{len(page.json_ld)} block(s)"))
    if not has_json:
        findings.append(Finding(
            id="no-jsonld", title="No JSON-LD structured data",
            severity=Severity.HIGH, nature=Nature.MEASURED, confidence=1.0,
            category="schema", source=page.final_url,
            recommendation="Introduce JSON-LD (at least Organization + WebSite).",
        ))

    score = Score(
        key="schema", label="Structured data",
        value=sum(c.points for c in comps), nature=Nature.MEASURED, confidence=1.0,
        components=comps,
        methodology="Weighs the presence of an entity schema, sameAs links, the "
                    "richness of types, and JSON-LD validity.",
    )
    return score, findings
