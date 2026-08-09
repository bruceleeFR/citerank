"""
Citability analyzer — the real improvement over the upstream.

The upstream judges a passage citable if it is "134–167 words". That's a false
universal truth: a lone figure, a one-sentence definition or a table can be far
more reusable by an AI than 150 words of fluff. The spec (point 8) explicitly
forbids it.

We therefore assess citability through SEMANTIC signals, where length is only a
minor factor:

  - factual density (numbers, dates, percentages, units);
  - presence of named entities;
  - direct answer to a question (the passage follows an interrogative heading);
  - self-containment (understandable out of context);
  - definitions and statistics;
  - extractability (clean sentences, not a wall of text).

This is a heuristic — so marked INFERRED, never MEASURED. We don't claim to
measure what an AI will reuse; we estimate what it has a chance of reusing, and
we say so.
"""

from __future__ import annotations

import re

from ..models import CrawledPage, Finding, Nature, Score, ScoreComponent, Severity

_RE_NUMBER = re.compile(r"\b\d+([.,]\d+)?\s?(%|€|\$|km|kg|ms|s|min|h|M|k|Md)?\b")
_RE_DATE = re.compile(r"\b(19|20)\d{2}\b|\b\d{1,2}\s+(january|february|march|april|may|june|"
                      r"july|august|september|october|november|december|jan|feb|mar|apr|"
                      r"jun|jul|aug|sep|oct|nov|dec)\b", re.IGNORECASE)
_RE_ENTITY = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+){0,2}\b")
_QUESTION_WORDS = ("what", "why", "how", "when", "where", "which", "who",
                   "comment", "pourquoi", "quel", "quelle", "combien", "où")


def _passages(page: CrawledPage) -> list[tuple[str, str]]:
    """
    Split into meaningful passages. We attach each text block to the heading that
    precedes it: a passage under an interrogative heading answers a question,
    which is the strongest citability signal.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page.html, "html.parser")
    for b in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        b.extract()

    passages, current_heading = [], ""
    for el in soup.find_all(["h2", "h3", "h4", "p", "li"]):
        txt = " ".join(el.get_text(" ").split())
        if el.name in ("h2", "h3", "h4"):
            current_heading = txt
        elif len(txt) >= 40:
            passages.append((current_heading, txt))
    return passages[:200]


def _score_passage(heading: str, text: str) -> tuple[float, dict]:
    words = text.split()
    n = len(words)

    numbers = len(_RE_NUMBER.findall(text))
    dates = len(_RE_DATE.findall(text))
    entities = len(set(_RE_ENTITY.findall(text)))
    answers_question = heading.lower().startswith(_QUESTION_WORDS)

    # Factual density per 100 words, capped.
    density = (numbers + dates) / max(n, 1) * 100

    signals = {
        "factual_density": min(1.0, density / 4),        # 4 facts/100 words = full
        "entities": min(1.0, entities / 5),
        "answers_question": 1.0 if answers_question else 0.0,
        # Length matters, but weakly and as a plateau — not a magic window. A
        # passage too short (<25 words) or too long (>250) loses a little.
        "self_containment_length": 1.0 if 25 <= n <= 250 else 0.5,
        "definition": 1.0 if re.search(r"\b(is|are|means|refers to|est|désigne|signifie)\b",
                                        text[:120], re.IGNORECASE) else 0.0,
    }
    weights = {"factual_density": 0.30, "entities": 0.15, "answers_question": 0.25,
               "self_containment_length": 0.15, "definition": 0.15}
    note = sum(signals[k] * weights[k] for k in weights) * 100
    return note, signals


def analyze(page: CrawledPage) -> tuple[Score, list[Finding]]:
    passages = _passages(page)
    findings: list[Finding] = []

    if not passages:
        score = Score("citability", "Citability", 0.0, Nature.INFERRED, 0.3,
                      [ScoreComponent("passages", "Analyzable passages", 0, 100,
                                      Nature.OBSERVED, "no usable passage")],
                      "No sufficient text passage could be isolated.")
        findings.append(Finding(
            "no-content", "Insufficient text content for citability",
            Severity.MEDIUM, Nature.OBSERVED, 0.6, "content", page.final_url,
            recommendation="Flesh out the page's written content."))
        return score, findings

    notes = [(_score_passage(t, x)[0], t, x) for t, x in passages]
    notes.sort(reverse=True)
    average = sum(n for n, _, _ in notes) / len(notes)

    high = [x for x in notes if x[0] >= 60]
    low = [x for x in notes if x[0] < 35]

    comps = [
        ScoreComponent("avg", "Average passage citability", average, 100,
                       Nature.INFERRED, f"{len(passages)} passages"),
    ]
    # The overall citability score is pulled up if the site has at least a few
    # "gem" passages: an AI only needs one good excerpt.
    bonus = min(15, 3 * len(high))
    value = min(100, average + bonus)

    score = Score(
        key="citability", label="Citability",
        value=value, nature=Nature.INFERRED, confidence=0.6, components=comps,
        methodology="Per-passage semantic signals (factual density, entities, "
                    "direct answer, self-containment, definition). Word count is "
                    "only a minor factor, never a hard threshold.",
    )

    if low and len(low) > len(passages) * 0.5:
        findings.append(Finding(
            id="low-citability", title="Content hard for AIs to extract",
            severity=Severity.MEDIUM, nature=Nature.INFERRED, confidence=0.6,
            category="content", source=page.final_url,
            detail=f"{len(low)}/{len(passages)} passages below the citability threshold.",
            evidence=low[0][2][:200],
            recommendation="Rewrite weak passages as self-contained, factual answers: "
                           "one idea per block, a clear figure or definition.",
        ))
    if high:
        findings.append(Finding(
            id="citation-candidates", title=f"{len(high)} high-citation-potential passage(s)",
            severity=Severity.INFO, nature=Nature.INFERRED, confidence=0.6,
            category="content", source=page.final_url,
            detail="Passages an AI has a good chance of reusing verbatim.",
            evidence=high[0][2][:200]))
    return score, findings
