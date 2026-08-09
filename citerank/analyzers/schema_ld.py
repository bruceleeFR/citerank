"""
Analyseur de données structurées (JSON-LD).

Ce que les moteurs IA lisent pour comprendre QUI tu es et CE QUE tu proposes.
On distingue les types qui portent l'identité d'entité (Organization, Person,
LocalBusiness) des types transactionnels (Product, FAQPage, Article) : les
premiers pèsent plus lourd, car ce sont eux qui rendent une marque
désambiguïsable par une IA.
"""

from __future__ import annotations

from ..models import (CrawledPage, Finding, Nature, Score, ScoreComponent,
                      Severity)

TYPES_ENTITE = {"Organization", "Corporation", "LocalBusiness", "Person"}
TYPES_UTILES = {"Product", "Offer", "FAQPage", "Article", "BreadcrumbList",
                "WebSite", "SoftwareApplication", "Review", "AggregateRating"}


def _types_de(bloc: dict) -> set[str]:
    t = bloc.get("@type", "")
    if isinstance(t, list):
        return {str(x) for x in t}
    return {str(t)} if t else set()


def analyser(page: CrawledPage) -> tuple[Score, list[Finding]]:
    findings: list[Finding] = []
    comps: list[ScoreComponent] = []

    tous_types: set[str] = set()
    for bloc in page.json_ld:
        tous_types |= _types_de(bloc)
    # @graph : certains sites imbriquent les entités.
    for bloc in page.json_ld:
        for sous in bloc.get("@graph", []) if isinstance(bloc, dict) else []:
            if isinstance(sous, dict):
                tous_types |= _types_de(sous)

    # -- Présence d'un schéma d'entité (40 pts) ----------------------------
    a_entite = bool(tous_types & TYPES_ENTITE)
    comps.append(ScoreComponent("entity_schema", "Schéma d'entité (Organization/Person)",
                                40 if a_entite else 0, 40, Nature.MEASURED,
                                ", ".join(sorted(tous_types & TYPES_ENTITE)) or "absent"))
    if not a_entite:
        findings.append(Finding(
            id="org-schema-missing", title="Schéma Organization absent",
            severity=Severity.HIGH, nature=Nature.MEASURED, confidence=1.0,
            category="schema", source=page.final_url,
            detail="Sans Organization/LocalBusiness, une IA peine à identifier la marque.",
            recommendation="Ajouter un bloc JSON-LD Organization avec name, url, logo, sameAs.",
            evidence=f"Types trouvés : {', '.join(sorted(tous_types)) or 'aucun'}",
        ))

    # -- sameAs : le pont vers les entités qui te vérifient (25 pts) --------
    a_sameas = any("sameAs" in b for b in page.json_ld if isinstance(b, dict))
    comps.append(ScoreComponent("sameas", "Liens sameAs (profils externes)",
                                25 if a_sameas else 0, 25, Nature.MEASURED,
                                "présent" if a_sameas else "absent"))
    if a_entite and not a_sameas:
        findings.append(Finding(
            id="sameas-missing", title="Propriété sameAs absente",
            severity=Severity.MEDIUM, nature=Nature.MEASURED, confidence=1.0,
            category="schema", source=page.final_url,
            detail="sameAs relie l'entité à ses profils (LinkedIn, Wikidata, Crunchbase).",
            recommendation="Ajouter sameAs pointant vers les profils vérifiables de la marque.",
        ))

    # -- Richesse (20 pts) : types utiles présents -------------------------
    utiles = tous_types & TYPES_UTILES
    pts_util = min(20, 5 * len(utiles))
    comps.append(ScoreComponent("richness", "Types structurés utiles",
                                pts_util, 20, Nature.MEASURED,
                                ", ".join(sorted(utiles)) or "aucun"))

    # -- Validité (15 pts) : un JSON-LD cassé compte comme absent ----------
    a_json = bool(page.json_ld)
    comps.append(ScoreComponent("presence", "Présence de JSON-LD valide",
                                15 if a_json else 0, 15, Nature.MEASURED,
                                f"{len(page.json_ld)} bloc(s)"))
    if not a_json:
        findings.append(Finding(
            id="no-jsonld", title="Aucune donnée structurée JSON-LD",
            severity=Severity.HIGH, nature=Nature.MEASURED, confidence=1.0,
            category="schema", source=page.final_url,
            recommendation="Introduire du JSON-LD (au minimum Organization + WebSite).",
        ))

    score = Score(
        key="schema", label="Données structurées",
        value=sum(c.points for c in comps), nature=Nature.MEASURED, confidence=1.0,
        components=comps,
        methodology="Pondère la présence d'un schéma d'entité, des liens sameAs, "
                    "la richesse des types et la validité du JSON-LD.",
    )
    return score, findings
