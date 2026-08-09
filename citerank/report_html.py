"""
Rapport HTML autonome — le livrable qui se partage (points 18, 36).

Un seul fichier, aucune dépendance externe : CSS en ligne, SVG en ligne, aucune
police distante, aucun script. Il s'ouvre partout, se joint à un e-mail, se pose
sur un hébergement statique. C'est la boucle d'acquisition : quelqu'un partage
son score, le lien ramène au produit.

Thème clair et sombre gérés par `prefers-color-scheme`. Chaque donnée garde son
étiquette de nature — le rapport reste honnête même en version marketing.
"""

from __future__ import annotations

import html as _html

from .models import Nature, Severity, SiteAudit

_ETIQ = {Nature.MEASURED: "MESURÉ", Nature.OBSERVED: "OBSERVÉ",
         Nature.INFERRED: "DÉDUIT", Nature.RECOMMENDED: "RECOMMANDÉ"}
_SEV = {Severity.CRITICAL: ("Critique", "#ff5c5c"), Severity.HIGH: ("Élevé", "#ff8a4c"),
        Severity.MEDIUM: ("Moyen", "#ffcf5c"), Severity.LOW: ("Mineur", "#8b9bb4"),
        Severity.INFO: ("Info", "#8b7dff")}


def _e(s) -> str:
    return _html.escape(str(s))


def _anneau(valeur: float, taille: int = 132) -> str:
    """Anneau de score en SVG : un dégradé chaud→froid, le trou porte le chiffre."""
    r = (taille - 16) / 2
    circ = 2 * 3.14159 * r
    rempli = circ * (valeur / 100)
    return f"""<svg width="{taille}" height="{taille}" viewBox="0 0 {taille} {taille}" role="img" aria-label="Score {valeur:.0f} sur 100">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#ff8a4c"/><stop offset="1" stop-color="#8b7dff"/>
  </linearGradient></defs>
  <circle cx="{taille/2}" cy="{taille/2}" r="{r}" fill="none" stroke="var(--rail)" stroke-width="12"/>
  <circle cx="{taille/2}" cy="{taille/2}" r="{r}" fill="none" stroke="url(#g)" stroke-width="12"
    stroke-linecap="round" stroke-dasharray="{rempli:.1f} {circ:.1f}"
    transform="rotate(-90 {taille/2} {taille/2})"/>
  <text x="50%" y="50%" text-anchor="middle" dy="0.1em" font-size="34" font-weight="800" fill="var(--ink)">{valeur:.0f}</text>
  <text x="50%" y="50%" text-anchor="middle" dy="1.7em" font-size="11" fill="var(--muted)">/ 100</text>
</svg>"""


def _barre(valeur: float) -> str:
    return (f'<span class="bar"><span class="fill" style="width:{max(2, valeur):.0f}%"></span></span>')


def rendre(audit: SiteAudit, *, comparaison=None, marque_agence: str = "") -> str:
    findings = sorted(audit.findings, key=lambda f: list(_SEV).index(f.severity))
    prioritaires = [f for f in findings
                    if f.severity in (Severity.CRITICAL, Severity.HIGH)]

    lignes_scores = ""
    for s in audit.scores:
        lignes_scores += f"""<tr>
      <td>{_e(s.label)}</td>
      <td class="num">{s.value:.0f}</td>
      <td>{_barre(s.value)}</td>
      <td><span class="tag">{_ETIQ[s.nature]}</span></td></tr>"""

    bloc_probs = ""
    for f in prioritaires:
        lbl, col = _SEV[f.severity]
        preuve = f'<div class="ev">{_e(f.evidence[:180])}</div>' if f.evidence else ""
        bloc_probs += f"""<div class="finding">
      <div class="fhead"><span class="dot" style="background:{col}"></span>
        <strong>{_e(f.title)}</strong>
        <span class="sev" style="color:{col}">{lbl}</span>
        <span class="tag small">{_ETIQ[f.nature]}</span></div>
      {f'<p>{_e(f.detail)}</p>' if f.detail else ''}
      {preuve}
      {f'<p class="fix"><b>Correctif —</b> {_e(f.recommendation)}</p>' if f.recommendation else ''}
    </div>"""

    bloc_comp = ""
    if comparaison is not None:
        rang, total = comparaison.rang_cible()
        rows = ""
        for r in sorted(comparaison.tableau(), key=lambda x: x["global"], reverse=True):
            vous = ' class="you"' if r["domaine"] == audit.domain else ""
            rows += (f'<tr{vous}><td>{_e(r["domaine"])}</td><td class="num">{r["global"]:.0f}</td>'
                     f'<td class="num">{_n(r["readiness"])}</td><td class="num">{_n(r["technical"])}</td>'
                     f'<td class="num">{_n(r["schema"])}</td><td class="num">{_n(r["citability"])}</td></tr>')
        bloc_comp = f"""<section><h2>Face aux concurrents</h2>
      <p class="lead">Votre rang : <strong>{rang}/{total}</strong></p>
      <table class="grid"><thead><tr><th>Domaine</th><th>Global</th><th>Ready</th>
        <th>Tech</th><th>Schéma</th><th>Cite</th></tr></thead><tbody>{rows}</tbody></table></section>"""

    pied_agence = f'<div class="agency">Rapport préparé par {_e(marque_agence)}</div>' if marque_agence else ""

    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CiteRank — {_e(audit.domain)}</title>
<style>
:root{{--bg:#f7f7f9;--card:#fff;--ink:#12141c;--muted:#6a7180;--rail:#e7e8ee;
  --line:#ececf1;--chaud:#ff8a4c;--froid:#8b7dff}}
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
.fill{{display:block;height:100%;background:linear-gradient(90deg,var(--chaud),var(--froid))}}
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
.cta{{display:inline-block;margin-top:14px;font-size:12.5px;color:var(--froid);text-decoration:none}}
</style></head><body><div class="wrap">
  <div class="hero">
    {_anneau(audit.overall())}
    <div class="meta">
      <div class="brand">CiteRank · Score IA-Search</div>
      <h1>{_e(audit.domain)}</h1>
      <div class="sub">Analysé le {_e(audit.started_at[:10])} · {len(prioritaires)} problème(s) prioritaire(s)</div>
    </div>
  </div>

  <section><h2>Détail des scores</h2>
    <table><tbody>{lignes_scores}</tbody></table></section>

  {bloc_comp}

  {'<section><h2>Problèmes prioritaires</h2>' + bloc_probs + '</section>' if bloc_probs else ''}

  <div class="legend">
    <b>Légende —</b> MESURÉ : relevé directement · OBSERVÉ : constaté sur la page ·
    DÉDUIT : estimé par heuristique (pas une garantie) · RECOMMANDÉ : action proposée.<br>
    Un score de préparation ne présume pas de la visibilité réelle dans les réponses IA.
  </div>
  {pied_agence}
  <div style="text-align:center"><a class="cta" href="https://github.com/">Analysé avec CiteRank — moteur open-source AI-Search</a></div>
</div></body></html>"""


def _n(v):
    return "—" if v is None else f"{v:.0f}"
