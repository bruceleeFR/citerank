"""
Competitive intelligence — the heart of CiteRank's edge.

Two questions the upstream tool doesn't ask:

  1. Where does my site lose points against a competitor? (Readiness comparison,
     100% local, deterministic, no API key)
  2. Why is a competitor cited instead of me in AI answers? (Share of Voice,
     needs LLM providers)

The module never fabricates a "why": every explanation is backed by a measured
score gap or an observed citation rate. A claim without evidence has no place
here (point 25).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from . import engine, visibility
from .models import Nature, SiteAudit
from .providers import Provider


@dataclass
class Comparison:
    target: SiteAudit
    competitors: list[SiteAudit] = field(default_factory=list)

    def table(self) -> list[dict]:
        """One row per site, one column per score. Usable as JSON or Markdown."""
        keys = ["readiness", "technical", "schema", "citability"]
        rows = []
        for a in [self.target, *self.competitors]:
            row = {"domain": a.domain, "overall": a.overall()}
            for k in keys:
                s = a.score(k)
                row[k] = round(s.value, 0) if s else None
            rows.append(row)
        return rows

    def target_rank(self) -> tuple[int, int]:
        """The target's position (1 = top) and the total number of sites compared."""
        ranking = sorted([self.target, *self.competitors],
                         key=lambda a: a.overall(), reverse=True)
        rank = next(i for i, a in enumerate(ranking, 1)
                    if a.domain == self.target.domain)
        return rank, len(ranking)


async def compare(target_url: str, competitor_urls: list[str], *,
                  allow_local: bool = False) -> Comparison:
    """Audit the target and its competitors in parallel, then assemble the comparison."""
    urls = [target_url, *competitor_urls]
    audits = await asyncio.gather(*[
        engine.audit(u, allow_local=allow_local, max_pages=1) for u in urls
    ])
    return Comparison(target=audits[0], competitors=list(audits[1:]))


def explain_gap(comp: Comparison) -> list[str]:
    """
    "Why they win" — only from measured gaps. Each sentence cites the score, the
    competitor and the difference. No guessing.
    """
    reasons: list[str] = []
    target = comp.target
    axes = [("schema", "structured data"), ("citability", "citability"),
            ("technical", "technical SEO"), ("readiness", "overall readiness")]

    for key, label in axes:
        s_target = target.score(key)
        if not s_target:
            continue
        # The best competitor on this axis.
        best = sorted(
            [(c, c.score(key)) for c in comp.competitors if c.score(key)],
            key=lambda t: t[1].value, reverse=True)
        if not best:
            continue
        competitor, s_comp = best[0]
        gap = s_comp.value - s_target.value
        if gap >= 12:  # threshold: only comment on gaps that matter
            nat = "" if s_target.nature == Nature.MEASURED else f" ({s_target.nature.value})"
            reasons.append(
                f"**{label}{nat}**: {competitor.domain} scores "
                f"{s_comp.value:.0f}/100 vs {s_target.value:.0f} for {target.domain} "
                f"(a {gap:.0f}-point gap)."
            )

    # Critical findings present on the target but absent on the leader.
    from .models import Severity
    target_ids = {f.id for f in target.findings
                  if f.severity in (Severity.CRITICAL, Severity.HIGH)}
    leader = max(comp.competitors, key=lambda a: a.overall(), default=None)
    if leader:
        leader_ids = {f.id for f in leader.findings}
        target_only = target_ids - leader_ids
        for f in target.findings:
            if f.id in target_only:
                reasons.append(
                    f"**{f.title}** penalizes you but not {leader.domain} — {f.recommendation}")

    if not reasons:
        reasons.append("No significant gap: the target holds up on the measured axes. "
                       "Any gap that exists plays out on real visibility — see Share of Voice.")
    return reasons


# --- Share of Voice (needs providers) ----------------------------------------

async def share_of_voice(brands: list[tuple[str, str]], queries: list[str], *,
                         providers: list[Provider] | None = None,
                         runs: int = 1) -> dict:
    """
    AI share of voice between several brands over the same query set.

    `brands`: list of (name, domain). The first is the target.
    Returns a typed dict with, per brand: mention, recommendation and citation
    rate — and the ranking with the target's position.
    """
    results = {}
    for name, domain in brands:
        vr = await visibility.measure(queries, brand=name, domain=domain,
                                      providers=providers, runs=runs)
        results[name] = visibility.visibility_score(vr)

    measured = [(n, s) for n, s in results.items() if s.get("score") is not None]
    if not measured:
        return {"measured": False,
                "reason": "no AI provider available",
                "brands": results}

    ranking = sorted(measured, key=lambda t: t[1]["score"], reverse=True)
    target_name = brands[0][0]
    fake = any(s.get("measured") is False and s.get("score") is not None
               for _, s in measured)

    return {
        "measured": not fake,
        "ranking": [{"brand": n, "score": s["score"],
                     "recommendation": s["recommendation_rate"],
                     "citation": s["citation_rate"]} for n, s in ranking],
        "target": target_name,
        "target_rank": next(i for i, (n, _) in enumerate(ranking, 1) if n == target_name),
        "total": len(ranking),
        "warning": ("FAKE results (MockProvider)." if fake else
                    "Sample over the provided query set; sensitive to engine variability."),
    }
