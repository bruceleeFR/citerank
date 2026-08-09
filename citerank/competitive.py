"""
Intelligence concurrentielle — le cœur de l'avantage de CiteRank.

Deux questions que l'outil amont ne pose pas :

  1. Où mon site perd-il des points face à un concurrent ? (comparaison de
     Readiness, 100 % locale, déterministe, sans clé API)
  2. Pourquoi un concurrent est-il cité à ma place dans les réponses IA ?
     (Share of Voice, nécessite des fournisseurs LLM)

Le module ne fabrique jamais un « pourquoi » : chaque explication est adossée à
un écart de score mesuré ou à un taux de citation observé. Une affirmation sans
preuve n'a pas sa place ici (point 25).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from . import engine, visibility
from .models import Nature, SiteAudit
from .providers import Provider


@dataclass
class Comparaison:
    cible: SiteAudit
    concurrents: list[SiteAudit] = field(default_factory=list)

    def tableau(self) -> list[dict]:
        """Une ligne par site, une colonne par score. Exploitable en JSON ou en Markdown."""
        cles = ["readiness", "technical", "schema", "citability"]
        lignes = []
        for a in [self.cible, *self.concurrents]:
            ligne = {"domaine": a.domain, "global": a.overall()}
            for k in cles:
                s = a.score(k)
                ligne[k] = round(s.value, 0) if s else None
            lignes.append(ligne)
        return lignes

    def rang_cible(self) -> tuple[int, int]:
        """Position de la cible (1 = tête) et nombre total de sites comparés."""
        classement = sorted([self.cible, *self.concurrents],
                            key=lambda a: a.overall(), reverse=True)
        rang = next(i for i, a in enumerate(classement, 1)
                    if a.domain == self.cible.domain)
        return rang, len(classement)


async def comparer(cible_url: str, concurrents_url: list[str], *,
                   autoriser_local: bool = False) -> Comparaison:
    """Audite la cible et ses concurrents en parallèle, puis assemble la comparaison."""
    urls = [cible_url, *concurrents_url]
    audits = await asyncio.gather(*[
        engine.audit(u, autoriser_local=autoriser_local) for u in urls
    ])
    return Comparaison(cible=audits[0], concurrents=list(audits[1:]))


def expliquer_ecart(comp: Comparaison) -> list[str]:
    """
    « Pourquoi ils passent devant » — uniquement à partir d'écarts mesurés.
    Chaque phrase cite le score, le concurrent et la différence. Aucune supposition.
    """
    raisons: list[str] = []
    cible = comp.cible
    axes = [("schema", "données structurées"), ("citability", "citabilité"),
            ("technical", "SEO technique"), ("readiness", "préparation globale")]

    for cle, label in axes:
        s_cible = cible.score(cle)
        if not s_cible:
            continue
        # Le meilleur concurrent sur cet axe.
        meilleurs = sorted(
            [(c, c.score(cle)) for c in comp.concurrents if c.score(cle)],
            key=lambda t: t[1].value, reverse=True)
        if not meilleurs:
            continue
        concurrent, s_conc = meilleurs[0]
        ecart = s_conc.value - s_cible.value
        if ecart >= 12:  # seuil : on ne commente que les écarts qui comptent
            nat = "" if s_cible.nature == Nature.MEASURED else f" ({s_cible.nature.value})"
            raisons.append(
                f"**{label}{nat}** : {concurrent.domain} obtient "
                f"{s_conc.value:.0f}/100 contre {s_cible.value:.0f} pour {cible.domain} "
                f"(écart de {ecart:.0f} points)."
            )

    # Constats critiques présents chez la cible mais absents chez le meneur.
    from .models import Severity
    ids_cible = {f.id for f in cible.findings
                 if f.severity in (Severity.CRITICAL, Severity.HIGH)}
    meneur = max(comp.concurrents, key=lambda a: a.overall(), default=None)
    if meneur:
        ids_meneur = {f.id for f in meneur.findings}
        propres_a_cible = ids_cible - ids_meneur
        for f in cible.findings:
            if f.id in propres_a_cible:
                raisons.append(
                    f"**{f.title}** vous pénalise et pas {meneur.domain} — {f.recommendation}")

    if not raisons:
        raisons.append("Aucun écart significatif : la cible tient la comparaison sur "
                       "les axes mesurés. L'écart, s'il existe, se joue sur la "
                       "visibilité réelle — voir le Share of Voice.")
    return raisons


# --- Share of Voice (nécessite des fournisseurs) -----------------------------

async def share_of_voice(marques: list[tuple[str, str]], queries: list[str], *,
                         providers: list[Provider] | None = None,
                         runs: int = 1) -> dict:
    """
    Part de voix IA entre plusieurs marques sur un même jeu de requêtes.

    `marques` : liste de (nom, domaine). La première est la cible.
    Retourne un dict typé avec, par marque : taux de mention, de recommandation,
    de citation — et la désignation des gagnants et des opportunités.
    """
    resultats = {}
    for nom, domaine in marques:
        vr = await visibility.mesurer(queries, marque=nom, domaine=domaine,
                                      providers=providers, runs=runs)
        s = visibility.score_visibilite(vr)
        resultats[nom] = s

    mesures = [(n, s) for n, s in resultats.items() if s.get("score") is not None]
    if not mesures:
        return {"mesuré": False,
                "raison": "aucun fournisseur IA disponible",
                "marques": resultats}

    classement = sorted(mesures, key=lambda t: t[1]["score"], reverse=True)
    cible_nom = marques[0][0]
    factice = any(s.get("mesuré") is False and s.get("score") is not None
                  for _, s in mesures)

    return {
        "mesuré": not factice,
        "classement": [{"marque": n, "score": s["score"],
                        "recommandation": s["taux_recommandation"],
                        "citation": s["taux_citation"]} for n, s in classement],
        "cible": cible_nom,
        "rang_cible": next(i for i, (n, _) in enumerate(classement, 1) if n == cible_nom),
        "total": len(classement),
        "avertissement": ("Résultats FACTICES (MockProvider)." if factice else
                          "Échantillon sur le jeu de requêtes fourni ; sensible à la "
                          "variabilité des moteurs."),
    }
