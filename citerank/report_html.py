"""
Standalone HTML report — the shareable deliverable (points 18, 36).

A single file, no external dependency: inline CSS, inline SVG, no remote fonts,
no scripts. It opens anywhere, attaches to an email, drops onto static hosting.
This is the acquisition loop: someone shares their score, the link brings them
back to the product.

Light and dark themes via `prefers-color-scheme`. Every data point keeps its
nature label — the report stays honest even in its marketing form.
"""

from __future__ import annotations

import html as _html

from .models import Nature, Severity, SiteAudit

_LABEL = {Nature.MEASURED: "MEASURED", Nature.OBSERVED: "OBSERVED",
          Nature.INFERRED: "INFERRED", Nature.RECOMMENDED: "RECOMMENDED"}
_SEV = {Severity.CRITICAL: ("Critical", "#ff5c5c"), Severity.HIGH: ("High", "#ff8a4c"),
        Severity.MEDIUM: ("Medium", "#ffcf5c"), Severity.LOW: ("Minor", "#8b9bb4"),
        Severity.INFO: ("Info", "#8b7dff")}


def _e(s) -> str:
    return _html.escape(str(s))


def _ring(value: float, size: int = 132) -> str:
    """SVG score ring: a warm→cool gradient, the hole carries the number."""
    r = (size - 16) / 2
    circ = 2 * 3.14159 * r
    filled = circ * (value / 100)
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" aria-label="Score {value:.0f} out of 100">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#ff8a4c"/><stop offset="1" stop-color="#8b7dff"/>
  </linearGradient></defs>
  <circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="var(--rail)" stroke-width="12"/>
  <circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="url(#g)" stroke-width="12"
    stroke-linecap="round" stroke-dasharray="{filled:.1f} {circ:.1f}"
    transform="rotate(-90 {size/2} {size/2})"/>
  <text x="50%" y="50%" text-anchor="middle" dy="0.1em" font-size="34" font-weight="800" fill="var(--ink)">{value:.0f}</text>
  <text x="50%" y="50%" text-anchor="middle" dy="1.7em" font-size="11" fill="var(--muted)">/ 100</text>
</svg>"""


def _bar(value: float) -> str:
    return f'<span class="bar"><span class="fill" style="width:{max(2, value):.0f}%"></span></span>'


def render(audit: SiteAudit, *, comparison=None, agency_brand: str = "") -> str:
    findings = sorted(audit.findings, key=lambda f: list(_SEV).index(f.severity))
    priority = [f for f in findings
                if f.severity in (Severity.CRITICAL, Severity.HIGH)]

    score_rows = ""
    for s in audit.scores:
        score_rows += f"""<tr>
      <td>{_e(s.label)}</td>
      <td class="num">{s.value:.0f}</td>
      <td>{_bar(s.value)}</td>
      <td><span class="tag">{_LABEL[s.nature]}</span></td></tr>"""

    issues_block = ""
    for f in priority:
        lbl, col = _SEV[f.severity]
        ev = f'<div class="ev">{_e(f.evidence[:180])}</div>' if f.evidence else ""
        issues_block += f"""<div class="finding">
      <div class="fhead"><span class="dot" style="background:{col}"></span>
        <strong>{_e(f.title)}</strong>
        <span class="sev" style="color:{col}">{lbl}</span>
        <span class="tag small">{_LABEL[f.nature]}</span></div>
      {f'<p>{_e(f.detail)}</p>' if f.detail else ''}
      {ev}
      {f'<p class="fix"><b>Fix —</b> {_e(f.recommendation)}</p>' if f.recommendation else ''}
    </div>"""

    comp_block = ""
    if comparison is not None:
        rank, total = comparison.target_rank()
        rows = ""
        for r in sorted(comparison.table(), key=lambda x: x["overall"], reverse=True):
            you = ' class="you"' if r["domain"] == audit.domain else ""
            rows += (f'<tr{you}><td>{_e(r["domain"])}</td><td class="num">{r["overall"]:.0f}</td>'
                     f'<td class="num">{_n(r["readiness"])}</td><td class="num">{_n(r["technical"])}</td>'
                     f'<td class="num">{_n(r["schema"])}</td><td class="num">{_n(r["citability"])}</td></tr>')
        comp_block = f"""<section><h2>Against competitors</h2>
      <p class="lead">Your rank: <strong>{rank}/{total}</strong></p>
      <table class="grid"><thead><tr><th>Domain</th><th>Overall</th><th>Ready</th>
        <th>Tech</th><th>Schema</th><th>Cite</th></tr></thead><tbody>{rows}</tbody></table></section>"""

    agency_footer = f'<div class="agency">Report prepared by {_e(agency_brand)}</div>' if agency_brand else ""

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CiteRank — {_e(audit.domain)}</title>
<style>
:root{{--bg:#f7f7f9;--card:#fff;--ink:#12141c;--muted:#6a7180;--rail:#e7e8ee;
  --line:#ececf1;--warm:#ff8a4c;--cool:#8b7dff}}
@media(prefers-color-scheme:dark){{:root{{--bg:#07080c;--card:#0f1118;--ink:#f4f5f7;
  --muted:#8b93a5;--rail:#20232e;--line:#20232e}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.6 'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:820px;margin:0 auto;padding:40px 22px 80px}}
.hero{{display:flex;gap:26px;align-items:center;background:var(--card);border:1px solid var(--line);
  border-radius:20px;padding:28px;margin-bottom:22px}}
.hero .meta{{flex:1;min-width:0}}.brand{{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}}
.hero h1{{font-size:23px;margin:6px 0 4px;letter-spacing:-.02em;word-break:break-all}}
.hero .sub{{color:var(--muted);font-size:13.5px}}
h2{{font-size:16px;letter-spacing:-.01em;margin:30px 0 12px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:9px 6px;border-bottom:1px solid var(--line);font-size:14px}}
th{{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}}
.num{{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}}
.grid td:first-child{{word-break:break-all}}.grid .you{{background:linear-gradient(90deg,rgba(255,138,76,.08),rgba(139,125,255,.08))}}
.bar{{display:block;height:7px;background:var(--rail);border-radius:99px;overflow:hidden;min-width:80px}}
.fill{{display:block;height:100%;background:linear-gradient(90deg,var(--warm),var(--cool))}}
.tag{{font-size:10px;font-weight:700;letter-spacing:.05em;color:var(--muted);border:1px solid var(--line);
  border-radius:6px;padding:2px 6px;white-space:nowrap}}.tag.small{{font-size:9px}}
.finding{{padding:14px 0;border-bottom:1px solid var(--line)}}.finding:last-child{{border:0}}
.fhead{{display:flex;align-items:center;gap:9px;flex-wrap:wrap}}.dot{{width:9px;height:9px;border-radius:50%}}
.sev{{font-size:12px;font-weight:700}}.finding p{{margin:7px 0 0;font-size:14px;color:var(--muted)}}
.finding .fix{{color:var(--ink)}}.ev{{margin-top:7px;font:12px/1.5 ui-monospace,Menlo,monospace;
  color:var(--muted);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:8px 10px;overflow-x:auto}}
.lead{{color:var(--muted);margin:0 0 12px}}
.legend{{color:var(--muted);font-size:12px;margin-top:24px;line-height:1.7}}
.agency{{text-align:center;color:var(--muted);font-size:12px;margin-top:18px}}
.cta{{display:inline-block;margin-top:14px;font-size:12.5px;color:var(--cool);text-decoration:none}}
</style></head><body><div class="wrap">
  <div class="hero">
    {_ring(audit.overall())}
    <div class="meta">
      <div class="brand">CiteRank · AI-Search score</div>
      <h1>{_e(audit.domain)}</h1>
      <div class="sub">Analyzed on {_e(audit.started_at[:10])} · {len(priority)} priority issue(s)</div>
    </div>
  </div>

  <section><h2>Score breakdown</h2>
    <table><tbody>{score_rows}</tbody></table></section>

  {comp_block}

  {'<section><h2>Priority issues</h2>' + issues_block + '</section>' if issues_block else ''}

  <div class="legend">
    <b>Legend —</b> MEASURED: read directly · OBSERVED: seen on the page ·
    INFERRED: estimated by heuristic (not a guarantee) · RECOMMENDED: proposed action.<br>
    A readiness score does not presume real visibility in AI answers.
  </div>
  {agency_footer}
  <div style="text-align:center"><a class="cta" href="https://github.com/bruceleeFR/citerank">Analyzed with CiteRank — open-source AI-Search engine</a></div>
</div></body></html>"""


def _n(v):
    return "—" if v is None else f"{v:.0f}"
