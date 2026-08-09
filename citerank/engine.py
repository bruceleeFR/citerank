"""
Orchestrateur du moteur.

C'est LE point d'entrée du cœur, indépendant de toute interface (point 37). Le
skill Claude Code, la CLI, une future API REST ou le SaaS Lamarca appelleront
tous `audit()` / `readiness_score()` — ils ne réimplémentent rien, ils
habillent. La logique métier ne vit jamais dans un fichier Markdown de skill.

Le crawl est fait une seule fois et partagé (point 23). Les analyseurs locaux
sont déterministes et sans clé API : un audit de Readiness tourne hors ligne,
gratuitement, sur n'importe quelle URL.
"""

from __future__ import annotations

from urllib.parse import urlparse

from .analyzers import citability, schema_ld, technical
from .crawl import Crawler, nouvelle_session, valider_url
from .models import (Nature, Score, ScoreComponent, SiteAudit, now_iso)


async def audit(url: str, *, autoriser_local: bool = False) -> SiteAudit:
    """
    Audit de Readiness complet, 100 % local. Ne lance AUCUN moteur IA — c'est la
    couche gratuite. La Visibility (payante, coûteuse) est un appel séparé.
    """
    url = valider_url(url, autoriser_local)
    domain = urlparse(url).netloc
    audit = SiteAudit(url=url, domain=domain, started_at=now_iso())

    crawler = Crawler(autoriser_local=autoriser_local)
    async with nouvelle_session() as session:
        page = await crawler.get(url, session)

        if not page.ok:
            audit.finished_at = now_iso()
            from .models import Finding, Severity
            audit.findings.append(Finding(
                id="fetch-failed", title="Page inaccessible",
                severity=Severity.CRITICAL, nature=Nature.MEASURED, confidence=1.0,
                category="technical", source=url,
                detail=page.error or f"HTTP {page.status}",
                recommendation="Vérifier que l'URL est publique et répond en 200."))
            return audit

        s_tech, f_tech, ctx = await technical.analyser(url, crawler, session, page)
        s_schema, f_schema = schema_ld.analyser(page)
        s_cite, f_cite = citability.analyser(page)

    audit.context = ctx
    audit.scores.extend([s_tech, s_schema, s_cite])
    audit.findings.extend([*f_tech, *f_schema, *f_cite])

    # Le score de READINESS est un composite explicite des trois axes locaux.
    # On le nomme et on le sépare de la Visibility : un site parfaitement prêt
    # n'est pas forcément cité (distinction A/B du cahier des charges, point 1).
    readiness = _composite_readiness(s_tech, s_schema, s_cite)
    audit.scores.insert(0, readiness)

    audit.finished_at = now_iso()
    return audit


def _composite_readiness(s_tech: Score, s_schema: Score, s_cite: Score) -> Score:
    poids = {"technical": 0.45, "schema": 0.30, "citability": 0.25}
    comps = [
        ScoreComponent(s.key, s.label, s.value * poids[s.key], poids[s.key] * 100,
                       s.nature, f"{s.value:.0f}/100 pondéré {int(poids[s.key]*100)}%")
        for s in (s_tech, s_schema, s_cite)
    ]
    valeur = sum(c.points for c in comps)
    return Score(
        key="readiness", label="Préparation IA (Readiness)",
        value=valeur, nature=Nature.MEASURED, confidence=0.9, components=comps,
        methodology="Composite pondéré : technique 45 %, données structurées 30 %, "
                    "citabilité 25 %. Mesure la PRÉPARATION du site, distincte de sa "
                    "visibilité réelle dans les réponses IA.",
    )


async def readiness_score(url: str, *, autoriser_local: bool = False) -> float:
    """Raccourci : la note de Readiness seule."""
    a = await audit(url, autoriser_local=autoriser_local)
    s = a.score("readiness")
    return s.value if s else 0.0
