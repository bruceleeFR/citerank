"""
Analyseur technique : robots.txt, sitemap, llms.txt, accessibilité aux
crawlers IA, en-têtes, canonique, langue.

100 % local et déterministe. Aucun appel à un moteur IA. C'est la brique qui
permet un audit gratuit et illimité (point 31) — la couche d'acquisition.
"""

from __future__ import annotations

from urllib.parse import urlparse

import aiohttp

from ..crawl import Crawler
from ..models import CrawledPage, Finding, Nature, Score, ScoreComponent, Severity, SiteContext

# Robots IA à considérer explicitement. Bloquer GPTBot, c'est se rendre
# invisible à ChatGPT ; c'est un choix légitime, mais qui doit être conscient.
CRAWLERS_IA = ["GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot",
               "Claude-Web", "PerplexityBot", "Google-Extended", "CCBot"]


async def analyser(url: str, crawler: Crawler, session: aiohttp.ClientSession,
                   page: CrawledPage) -> tuple[Score, list[Finding], SiteContext]:
    base = urlparse(page.final_url)
    racine = f"{base.scheme}://{base.netloc}"

    robots = await crawler.texte_brut(racine + "/robots.txt", session)
    llms = await crawler.texte_brut(racine + "/llms.txt", session)
    sitemap = await crawler.texte_brut(racine + "/sitemap.xml", session)

    findings: list[Finding] = []
    comps: list[ScoreComponent] = []

    # -- Accès des crawlers IA (25 pts) ------------------------------------
    bloques = _crawlers_bloques(robots)
    if not bloques:
        comps.append(ScoreComponent("ai_crawlers", "Crawlers IA autorisés", 25, 25,
                                    Nature.MEASURED, "aucun robot IA bloqué"))
    else:
        perdu = min(25, 4 * len(bloques))
        comps.append(ScoreComponent("ai_crawlers", "Crawlers IA autorisés",
                                    25 - perdu, 25, Nature.MEASURED,
                                    f"bloqués : {', '.join(bloques)}"))
        findings.append(Finding(
            id="ai-crawler-blocked", title="Des robots IA sont bloqués par robots.txt",
            severity=Severity.HIGH, nature=Nature.MEASURED, confidence=1.0,
            category="crawlers", source=racine + "/robots.txt",
            detail=f"Robots bloqués : {', '.join(bloques)}",
            evidence=_extrait_robots(robots, bloques),
            recommendation="Retirer ces agents du Disallow si la visibilité IA est recherchée.",
        ))

    # -- Sitemap (15 pts) --------------------------------------------------
    a_sitemap = bool(sitemap.strip()) and "<urlset" in sitemap or "<sitemapindex" in sitemap
    comps.append(ScoreComponent("sitemap", "Sitemap XML", 15 if a_sitemap else 0, 15,
                                Nature.MEASURED, "présent" if a_sitemap else "absent"))
    if not a_sitemap:
        findings.append(Finding(
            id="sitemap-missing", title="Sitemap XML absent", severity=Severity.MEDIUM,
            nature=Nature.MEASURED, confidence=1.0, category="technical",
            source=racine + "/sitemap.xml",
            recommendation="Publier /sitemap.xml pour guider l'exploration.",
        ))

    # -- llms.txt (15 pts) — standard émergent, bonus, pas obligation -------
    a_llms = bool(llms.strip())
    comps.append(ScoreComponent("llms_txt", "llms.txt", 15 if a_llms else 0, 15,
                                Nature.MEASURED, "présent" if a_llms else "absent"))
    if not a_llms:
        findings.append(Finding(
            id="llmstxt-missing", title="llms.txt absent",
            severity=Severity.LOW, nature=Nature.RECOMMENDED, confidence=0.7,
            category="crawlers", source=racine + "/llms.txt",
            detail="Standard émergent qui expose aux moteurs IA une carte du contenu.",
            recommendation="Générer un /llms.txt listant les pages de référence.",
        ))

    # -- HTTPS + en-têtes (15 pts) -----------------------------------------
    est_https = base.scheme == "https"
    hsts = "strict-transport-security" in page.headers
    pts = (10 if est_https else 0) + (5 if hsts else 0)
    comps.append(ScoreComponent("transport", "HTTPS & HSTS", pts, 15, Nature.MEASURED,
                                f"https={est_https}, hsts={hsts}"))
    if not est_https:
        findings.append(Finding(
            id="no-https", title="Site non servi en HTTPS", severity=Severity.CRITICAL,
            nature=Nature.MEASURED, confidence=1.0, category="technical",
            source=page.final_url, recommendation="Servir tout le site en HTTPS."))

    # -- Balises de tête (15 pts) ------------------------------------------
    pts_meta = 0
    if page.title:
        pts_meta += 6
    else:
        findings.append(Finding("title-missing", "Balise <title> absente",
                                Severity.HIGH, Nature.MEASURED, 1.0, "technical",
                                page.final_url, recommendation="Ajouter un <title> descriptif."))
    if page.meta_description:
        pts_meta += 5
    else:
        findings.append(Finding("meta-desc-missing", "Meta description absente",
                                Severity.MEDIUM, Nature.MEASURED, 1.0, "technical",
                                page.final_url, recommendation="Ajouter une meta description."))
    if page.lang:
        pts_meta += 4
    else:
        findings.append(Finding("lang-missing", "Attribut lang absent sur <html>",
                                Severity.LOW, Nature.MEASURED, 1.0, "technical",
                                page.final_url,
                                recommendation="Déclarer la langue (ex. <html lang=\"fr\">)."))
    comps.append(ScoreComponent("head", "Balises de tête", pts_meta, 15, Nature.MEASURED))

    # -- Structure des titres (15 pts) -------------------------------------
    n_h1 = len(page.h1)
    if n_h1 == 1:
        pts_h1, det = 15, "un seul H1, idéal"
    elif n_h1 == 0:
        pts_h1, det = 0, "aucun H1"
        findings.append(Finding("h1-missing", "Aucun titre H1", Severity.MEDIUM,
                                Nature.OBSERVED, 1.0, "content", page.final_url,
                                recommendation="Ajouter un H1 unique et descriptif."))
    else:
        pts_h1, det = 7, f"{n_h1} H1 (un seul recommandé)"
        findings.append(Finding("h1-multiple", f"{n_h1} balises H1", Severity.LOW,
                                Nature.OBSERVED, 1.0, "content", page.final_url,
                                recommendation="Conserver un seul H1 par page."))
    comps.append(ScoreComponent("headings", "Structure des titres", pts_h1, 15,
                                Nature.OBSERVED, det))

    score = Score(
        key="technical", label="SEO technique",
        value=sum(c.points for c in comps),
        nature=Nature.MEASURED, confidence=1.0, components=comps,
        methodology="Somme de composantes mesurées : accès crawlers IA, sitemap, "
                    "llms.txt, transport, balises de tête, structure des titres.",
    )
    ctx = SiteContext(url=page.final_url, domain=base.netloc, robots_txt=robots,
                      llms_txt=llms, sitemap_present=a_sitemap)
    return score, findings, ctx


def _crawlers_bloques(robots: str) -> list[str]:
    """Repère les agents IA sous un Disallow: / dans robots.txt."""
    bloques, agent_courant = [], None
    interdit_global = {}
    for ligne in robots.splitlines():
        l = ligne.strip()
        if not l or l.startswith("#"):
            continue
        cle, _, val = l.partition(":")
        cle, val = cle.strip().lower(), val.strip()
        if cle == "user-agent":
            agent_courant = val
            interdit_global.setdefault(agent_courant, False)
        elif cle == "disallow" and agent_courant is not None:
            if val == "/":
                interdit_global[agent_courant] = True
    for agent, interdit in interdit_global.items():
        if not interdit:
            continue
        if agent == "*":
            bloques.extend(CRAWLERS_IA)  # * bloque tout, IA comprise
        else:
            for c in CRAWLERS_IA:
                if c.lower() == agent.lower():
                    bloques.append(c)
    return sorted(set(bloques))


def _extrait_robots(robots: str, bloques: list[str]) -> str:
    lignes = [l for l in robots.splitlines() if l.strip()][:12]
    return "\n".join(lignes)
