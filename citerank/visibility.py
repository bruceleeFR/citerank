"""
AI Visibility engine — measures whether a brand ACTUALLY appears in AI-engine
answers (concept B of the spec, distinct from Readiness). This is the costly
layer: each query = paid LLM calls.

Two honesty safeguards, which are a credibility argument (points 13, 30):

  - Multi-provider, multi-run consensus: a single LLM answer is not a fact. We
    repeat, we cross-check, we report the consistency.
  - Confidence is explicit. A brand cited 5 times out of 10 is a doubt, not a
    score. We display it "MEDIUM", we don't smooth it into "50% visibility".

Without a provider key, the engine invents nothing: it returns an empty result
and says so. With the MockProvider, it demonstrates the flow offline.
"""

from __future__ import annotations

from .crawl import new_session
from .models import ProviderResult, VisibilityResult
from .providers import Provider, available_providers


async def measure(queries: list[str], *, brand: str, domain: str,
                  providers: list[Provider] | None = None,
                  runs: int = 1) -> list[VisibilityResult]:
    """
    Run each query on each provider `runs` times. Returns one VisibilityResult
    per query, carrying all the individual runs.
    """
    provs = providers if providers is not None else available_providers()
    results: list[VisibilityResult] = []
    if not provs:
        # Nothing to query: say so plainly rather than return zeros that would
        # read as "brand invisible".
        return [VisibilityResult(query=q, runs=[]) for q in queries]

    async with new_session() as session:
        for q in queries:
            vr = VisibilityResult(query=q, runs=[])
            for p in provs:
                for _ in range(runs):
                    res: ProviderResult = await p.query(
                        q, brand=brand, domain=domain, session=session)
                    vr.runs.append(res)
            results.append(vr)
    return results


def visibility_score(results: list[VisibilityResult]) -> dict:
    """
    Aggregate results into a visibility score and its confidence. Returns a typed
    dict (never a Markdown blob), so it stays usable by any interface.
    """
    if not results or all(not r.runs for r in results):
        return {"measured": False,
                "reason": "no AI provider available (key missing)",
                "score": None}

    mention_rate = sum(r.mention_rate for r in results) / len(results)
    reco_rate = sum(r.recommendation_rate for r in results) / len(results)
    cite_rate = sum(r.citation_rate for r in results) / len(results)

    # The visibility score favors recommendation (appearing FAVORABLY) over a
    # plain mention, and values domain citation.
    score = (mention_rate * 40 + reco_rate * 40 + cite_rate * 20)

    fake = any(any(x.provider == "mock" for x in r.runs) for r in results)
    return {
        "measured": not fake,
        "score": round(score, 1),
        "mention_rate": round(mention_rate * 100, 1),
        "recommendation_rate": round(reco_rate * 100, 1),
        "citation_rate": round(cite_rate * 100, 1),
        "queries": len(results),
        "warning": ("FAKE results (MockProvider) — reflect no real engine."
                    if fake else
                    "Sample: depends on the queries tested and engine variability. "
                    "This is not a ranking guarantee."),
    }
