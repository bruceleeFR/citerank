"""
Analyseur de citabilité — la vraie amélioration face au projet amont.

Le projet d'origine juge un passage citable s'il fait « 134-167 mots ». C'est
une fausse vérité universelle : un chiffre isolé, une définition d'une phrase ou
un tableau peuvent être infiniment plus repris par une IA qu'un paragraphe de
150 mots creux. Le cahier des charges (point 8) l'interdit explicitement.

On évalue donc la citabilité par des signaux SÉMANTIQUES, dont la longueur n'est
qu'un facteur mineur :

  - densité factuelle (chiffres, dates, pourcentages, unités) ;
  - présence d'entités nommées ;
  - réponse directe à une question (le passage suit un titre interrogatif) ;
  - autonomie (se comprend hors contexte) ;
  - définitions et statistiques ;
  - extractibilité (phrases nettes, pas un pavé).

C'est une heuristique — donc marquée INFERRED, jamais MEASURED. On ne prétend
pas mesurer ce qu'une IA reprendra ; on estime ce qu'elle a des chances de
reprendre, et on le dit.
"""

from __future__ import annotations

import re

from ..models import (CrawledPage, Finding, Nature, Score, ScoreComponent,
                      Severity)

_RE_NOMBRE = re.compile(r"\b\d+([.,]\d+)?\s?(%|€|\$|km|kg|ms|s|min|h|M|k|Md)?\b")
_RE_DATE = re.compile(r"\b(19|20)\d{2}\b|\b\d{1,2}\s+(janvier|février|mars|avril|mai|juin|"
                      r"juillet|août|septembre|octobre|novembre|décembre|jan|feb|mar|apr|"
                      r"jun|jul|aug|sep|oct|nov|dec)\b", re.IGNORECASE)
_RE_ENTITE = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+){0,2}\b")
_MOTS_QUESTION = ("comment", "pourquoi", "qu'est", "quel", "quelle", "combien",
                  "quand", "où", "what", "why", "how", "when", "where", "which", "who")


def _passages(page: CrawledPage) -> list[tuple[str, str]]:
    """
    Découpe en passages porteurs de sens. On associe chaque bloc de texte au
    titre qui le précède : un passage sous un titre interrogatif répond à une
    question, ce qui est le signal de citabilité le plus fort.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page.html, "html.parser")
    for b in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        b.extract()

    passages, titre_courant = [], ""
    for el in soup.find_all(["h2", "h3", "h4", "p", "li"]):
        txt = " ".join(el.get_text(" ").split())
        if el.name in ("h2", "h3", "h4"):
            titre_courant = txt
        elif len(txt) >= 40:
            passages.append((titre_courant, txt))
    return passages[:200]


def _score_passage(titre: str, texte: str) -> tuple[float, dict]:
    mots = texte.split()
    n = len(mots)

    nombres = len(_RE_NOMBRE.findall(texte))
    dates = len(_RE_DATE.findall(texte))
    entites = len(set(_RE_ENTITE.findall(texte)))
    repond_question = titre.lower().startswith(_MOTS_QUESTION) or any(
        titre.lower().startswith(q) for q in _MOTS_QUESTION)

    # Densité factuelle par tranche de 100 mots, plafonnée.
    densite = (nombres + dates) / max(n, 1) * 100

    signaux = {
        "densité_factuelle": min(1.0, densite / 4),       # 4 faits/100 mots = plein
        "entités": min(1.0, entites / 5),
        "répond_à_question": 1.0 if repond_question else 0.0,
        # La longueur compte, mais faiblement, et par plateau — pas une fenêtre
        # magique. Un passage trop court (<25 mots) ou trop long (>250) perd un peu.
        "autonomie_longueur": 1.0 if 25 <= n <= 250 else 0.5,
        "définition": 1.0 if re.search(r"\b(est|désigne|signifie|is|means|refers to)\b",
                                        texte[:120], re.IGNORECASE) else 0.0,
    }
    poids = {"densité_factuelle": 0.30, "entités": 0.15, "répond_à_question": 0.25,
             "autonomie_longueur": 0.15, "définition": 0.15}
    note = sum(signaux[k] * poids[k] for k in poids) * 100
    return note, signaux


def analyser(page: CrawledPage) -> tuple[Score, list[Finding]]:
    passages = _passages(page)
    findings: list[Finding] = []

    if not passages:
        score = Score("citability", "Citabilité", 0.0, Nature.INFERRED, 0.3,
                      [ScoreComponent("passages", "Passages analysables", 0, 100,
                                      Nature.OBSERVED, "aucun passage exploitable")],
                      "Aucun passage de texte suffisant n'a pu être isolé.")
        findings.append(Finding(
            "no-content", "Contenu textuel insuffisant pour la citabilité",
            Severity.MEDIUM, Nature.OBSERVED, 0.6, "content", page.final_url,
            recommendation="Étoffer le contenu rédactionnel de la page."))
        return score, findings

    notes = [(_score_passage(t, x)[0], t, x) for t, x in passages]
    notes.sort(reverse=True)
    moyenne = sum(n for n, _, _ in notes) / len(notes)

    haute = [x for x in notes if x[0] >= 60]
    faible = [x for x in notes if x[0] < 35]

    comps = [
        ScoreComponent("avg", "Citabilité moyenne des passages", moyenne, 100,
                       Nature.INFERRED, f"{len(passages)} passages"),
    ]
    # Le score global de citabilité tire la moyenne vers le haut si le site a au
    # moins quelques passages « pépites » : une IA n'a besoin que d'un bon extrait.
    bonus = min(15, 3 * len(haute))
    valeur = min(100, moyenne + bonus)

    score = Score(
        key="citability", label="Citabilité",
        value=valeur, nature=Nature.INFERRED, confidence=0.6, components=comps,
        methodology="Signaux sémantiques par passage (densité factuelle, entités, "
                    "réponse directe, autonomie, définition). La longueur en mots "
                    "n'est qu'un facteur mineur, jamais un seuil couperet.",
    )

    if faible and len(faible) > len(passages) * 0.5:
        findings.append(Finding(
            id="low-citability", title="Contenu peu extractible par les IA",
            severity=Severity.MEDIUM, nature=Nature.INFERRED, confidence=0.6,
            category="content", source=page.final_url,
            detail=f"{len(faible)}/{len(passages)} passages sous le seuil de citabilité.",
            evidence=faible[0][2][:200],
            recommendation="Réécrire les passages faibles en réponses autonomes et "
                           "factuelles : une idée par bloc, un chiffre ou une définition claire.",
        ))
    if haute:
        findings.append(Finding(
            id="citation-candidates", title=f"{len(haute)} passage(s) à fort potentiel de citation",
            severity=Severity.INFO, nature=Nature.INFERRED, confidence=0.6,
            category="content", source=page.final_url,
            detail="Passages qu'une IA a de bonnes chances de reprendre tels quels.",
            evidence=haute[0][2][:200]))
    return score, findings
