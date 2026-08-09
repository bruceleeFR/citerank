"""
Report generation.

Markdown only appears here, at the end of the chain. Every data point is labeled
by its nature — MEASURED / OBSERVED / INFERRED / RECOMMENDED — to never present
an inference as a measurement (point 18). This is the rule that makes the product
credible.
"""

from __future__ import annotations

import json

from .models import Nature, Severity, SiteAudit

_LABEL = {
    Nature.MEASURED: "MEASURED",
    Nature.OBSERVED: "OBSERVED",
    Nature.INFERRED: "INFERRED",
    Nature.RECOMMENDED: "RECOMMENDED",
}
_SEV_ORDER = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2,
              Severity.LOW: 3, Severity.INFO: 4}
_SEV_ICON = {Severity.CRITICAL: "🔴", Severity.HIGH: "🟠", Severity.MEDIUM: "🟡",
             Severity.LOW: "⚪", Severity.INFO: "🔵"}


def to_json(audit: SiteAudit) -> str:
    return json.dumps(audit.to_dict(), ensure_ascii=False, indent=2)


def to_markdown(audit: SiteAudit) -> str:
    L = []
    L.append(f"# CiteRank report — {audit.domain}")
    L.append(f"\n`{audit.url}` · analyzed on {audit.started_at}\n")

    L.append(f"## Overall AI-Search score: **{audit.overall():.0f}/100**\n")
    L.append("| Score | Value | Nature | Confidence |")
    L.append("|---|---:|---|---:|")
    for s in audit.scores:
        L.append(f"| {s.label} | **{s.value:.0f}**/100 | {_LABEL[s.nature]} | {s.confidence:.0%} |")
    L.append("")

    # Detail of each score and its components: the required transparency.
    for s in audit.scores:
        L.append(f"### {s.label} — {s.value:.0f}/100  _({_LABEL[s.nature]})_")
        if s.methodology:
            L.append(f"> {s.methodology}\n")
        if s.components:
            L.append("| Component | Points | Detail |")
            L.append("|---|---:|---|")
            for c in s.components:
                L.append(f"| {c.label} | {c.points:.0f}/{c.max_points:.0f} | {c.detail} |")
            L.append("")

    # Findings, sorted by severity.
    findings = sorted(audit.findings, key=lambda f: _SEV_ORDER.get(f.severity, 9))
    critical = [f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]
    if critical:
        L.append("## Priority issues\n")
        for f in critical:
            L.append(f"#### {_SEV_ICON[f.severity]} {f.title}  _({_LABEL[f.nature]}, "
                     f"confidence {f.confidence:.0%})_")
            if f.detail:
                L.append(f"{f.detail}\n")
            if f.evidence:
                L.append(f"> Evidence: `{f.evidence[:160].strip()}`\n")
            if f.recommendation:
                L.append(f"**Fix:** {f.recommendation}\n")

    others = [f for f in findings if f.severity not in (Severity.CRITICAL, Severity.HIGH)]
    if others:
        L.append("## Other findings and opportunities\n")
        for f in others:
            L.append(f"- {_SEV_ICON[f.severity]} **{f.title}** _({_LABEL[f.nature]})_ — "
                     f"{f.recommendation or f.detail}")
        L.append("")

    L.append("---")
    L.append("_Legend: **MEASURED** = read directly · **OBSERVED** = seen on the "
             "page · **INFERRED** = estimated by heuristic · **RECOMMENDED** = "
             "proposed action. An INFERRED score is not a guarantee._")
    return "\n".join(L)


def comparison_console(comp, reasons: list[str]) -> str:
    """Terminal rendering of the competitive comparison."""
    rows = comp.table()
    rank, total = comp.target_rank()
    L = ["\n  CiteRank · competitive comparison",
         f"  {'─' * 58}",
         f"  {'Domain':<28}{'Overall':>8}{'Ready':>7}{'Tech':>6}{'Schema':>8}{'Cite':>6}"]
    for r in sorted(rows, key=lambda x: x['overall'], reverse=True):
        mark = " ◄ you" if r["domain"] == comp.target.domain else ""
        L.append(f"  {r['domain'][:27]:<28}{r['overall']:>8.0f}"
                 f"{_n(r['readiness']):>7}{_n(r['technical']):>6}"
                 f"{_n(r['schema']):>8}{_n(r['citability']):>6}{mark}")
    L.append(f"\n  Your rank: {rank}/{total}")
    L.append("\n  Why the gap:")
    for r in reasons:
        clean = r.replace("**", "")
        L.append(f"    • {clean}")
    return "\n".join(L) + "\n"


def _n(v):
    return "—" if v is None else f"{v:.0f}"


def comparison_markdown(comp, reasons: list[str]) -> str:
    rows = sorted(comp.table(), key=lambda x: x["overall"], reverse=True)
    rank, total = comp.target_rank()
    L = [f"# Competitive comparison — {comp.target.domain}",
         f"\n**Your rank: {rank}/{total}**\n",
         "| Domain | Overall | Readiness | Technical | Schema | Citability |",
         "|---|---:|---:|---:|---:|---:|"]
    for r in rows:
        you = " **◄ you**" if r["domain"] == comp.target.domain else ""
        L.append(f"| {r['domain']}{you} | {r['overall']:.0f} | {_n(r['readiness'])} | "
                 f"{_n(r['technical'])} | {_n(r['schema'])} | {_n(r['citability'])} |")
    L.append("\n## Why your competitors win\n")
    for r in reasons:
        L.append(f"- {r}")
    L.append("\n---\n_Readiness comparison: measured and deterministic. It does not "
             "presume real visibility in AI answers — see Share of Voice for that._")
    return "\n".join(L)


def console_summary(audit: SiteAudit) -> str:
    """Compact terminal output."""
    L = [f"\n  CiteRank · {audit.domain}",
         f"  {'─' * 46}",
         f"  Overall AI-Search score: {audit.overall():.0f}/100\n"]
    for s in audit.scores:
        bar = "█" * int(s.value / 5) + "·" * (20 - int(s.value / 5))
        L.append(f"  {s.label:<26} {bar} {s.value:>3.0f}  [{_LABEL[s.nature]}]")
    crit = [f for f in audit.findings
            if f.severity in (Severity.CRITICAL, Severity.HIGH)]
    if crit:
        L.append(f"\n  {len(crit)} priority issue(s):")
        for f in crit[:6]:
            L.append(f"    {_SEV_ICON[f.severity]} {f.title}")
    return "\n".join(L) + "\n"
