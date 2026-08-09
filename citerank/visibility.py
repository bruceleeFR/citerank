"""
Moteur de Visibilité IA — mesure si une marque APPARAÎT réellement dans les
réponses des moteurs IA (concept B du cahier des charges, distinct de la
Readiness). C'est la couche coûteuse : chaque requête = des appels LLM payants.

Deux garde-fous d'honnêteté, qui sont un argument de crédibilité (points 13, 30) :

  - Consensus multi-fournisseurs et multi-exécutions : une réponse unique d'un
    LLM n'est pas un fait. On répète, on croise, on rapporte la constance.
  - La confiance est explicite. Une marque citée 5 fois sur 10 est un doute, pas
    un score. On l'affiche « MEDIUM », on ne le lisse pas en « 50 % de visibilité ».

Sans clé de fournisseur, le moteur n'invente rien : il retourne un résultat vide
en le disant. Avec le MockProvider, on démontre le parcours hors ligne.
"""

from __future__ import annotations

from .crawl import nouvelle_session
from .models import ProviderResult, VisibilityResult
from .providers import Provider, fournisseurs_disponibles


async def mesurer(queries: list[str], *, marque: str, domaine: str,
                  providers: list[Provider] | None = None,
                  runs: int = 1) -> list[VisibilityResult]:
    """
    Exécute chaque requête sur chaque fournisseur `runs` fois. Retourne un
    VisibilityResult par requête, portant tous les passages individuels.
    """
    provs = providers if providers is not None else fournisseurs_disponibles()
    resultats: list[VisibilityResult] = []
    if not provs:
        # Rien à interroger : on le dit franchement plutôt que de rendre des zéros
        # qui se liraient comme « marque invisible ».
        return [VisibilityResult(query=q, runs=[]) for q in queries]

    async with nouvelle_session() as session:
        for q in queries:
            vr = VisibilityResult(query=q, runs=[])
            for p in provs:
                for _ in range(runs):
                    res: ProviderResult = await p.interroger(
                        q, marque=marque, domaine=domaine, session=session)
                    vr.runs.append(res)
            resultats.append(vr)
    return resultats


def score_visibilite(resultats: list[VisibilityResult]) -> dict:
    """
    Agrège les résultats en un score de visibilité et sa confiance. Retourne un
    dict typé (jamais un blob Markdown), pour rester exploitable par n'importe
    quelle interface.
    """
    if not resultats or all(not r.runs for r in resultats):
        return {"mesuré": False,
                "raison": "aucun fournisseur IA disponible (clé absente)",
                "score": None}

    taux_mention = sum(r.mention_rate for r in resultats) / len(resultats)
    taux_reco = sum(r.recommendation_rate for r in resultats) / len(resultats)
    taux_cite = sum(r.citation_rate for r in resultats) / len(resultats)

    # Le score de visibilité privilégie la recommandation (apparaître EN BIEN)
    # sur la simple mention, et valorise la citation du domaine.
    score = (taux_mention * 40 + taux_reco * 40 + taux_cite * 20)

    factices = any(any(x.provider == "mock" for x in r.runs) for r in resultats)
    return {
        "mesuré": not factices,
        "score": round(score, 1),
        "taux_mention": round(taux_mention * 100, 1),
        "taux_recommandation": round(taux_reco * 100, 1),
        "taux_citation": round(taux_cite * 100, 1),
        "requêtes": len(resultats),
        "avertissement": ("Résultats FACTICES (MockProvider) — ne reflètent aucun "
                          "moteur réel." if factices else
                          "Échantillon : dépend des requêtes testées et de la "
                          "variabilité des moteurs. Ce n'est pas une garantie de rang."),
    }
