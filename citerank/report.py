"""
Génération de rapport.

Le Markdown n'apparaît qu'ici, au bout de la chaîne. Chaque donnée est étiquetée
par sa nature — MESURÉ / OBSERVÉ / DÉDUIT / RECOMMANDÉ — pour ne jamais présenter
une déduction comme une mesure (point 18). C'est la règle qui fait la crédibilité
du produit.
"""

from __future__ import annotations

import json

from .models import Nature, Severity, SiteAudit

_ETIQ = {
    Nature.MEASURED: "MESURÉ",
    Nature.OBSERVED: "OBSERVÉ",
    Nature.INFERRED: "DÉDUIT",
    Nature.RECOMMENDED: "RECOMMANDÉ",
}
_SEV_ORDRE = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2,
              Severity.LOW: 3, Severity.INFO: 4}
_SEV_ICONE = {Severity.CRITICAL: "🔴", Severity.HIGH: "🟠", Severity.MEDIUM: "🟡",
              Severity.LOW: "⚪", Severity.INFO: "🔵"}


def en_json(audit: SiteAudit) -> str:
    return json.dumps(audit.to_dict(), ensure_ascii=False, indent=2)


def en_markdown(audit: SiteAudit) -> str:
    L = []
    L.append(f"# Rapport CiteRank — {audit.domain}")
    L.append(f"\n`{audit.url}` · analysé le {audit.started_at}\n")

    L.append(f"## Score global IA-Search : **{audit.overall():.0f}/100**\n")
    L.append("| Score | Valeur | Nature | Confiance |")
    L.append("|---|---:|---|---:|")
    for s in audit.scores:
        L.append(f"| {s.label} | **{s.value:.0f}**/100 | {_ETIQ[s.nature]} | {s.confidence:.0%} |")
    L.append("")

    # Détail de chaque score et de ses composantes : la transparence exigée.
    for s in audit.scores:
        L.append(f"### {s.label} — {s.value:.0f}/100  _({_ETIQ[s.nature]})_")
        if s.methodology:
            L.append(f"> {s.methodology}\n")
        if s.components:
            L.append("| Composante | Points | Détail |")
            L.append("|---|---:|---|")
            for c in s.components:
                L.append(f"| {c.label} | {c.points:.0f}/{c.max_points:.0f} | {c.detail} |")
            L.append("")

    # Constats, triés par sévérité.
    findings = sorted(audit.findings, key=lambda f: _SEV_ORDRE.get(f.severity, 9))
    critiques = [f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]
    if critiques:
        L.append("## Problèmes prioritaires\n")
        for f in critiques:
            L.append(f"#### {_SEV_ICONE[f.severity]} {f.title}  _({_ETIQ[f.nature]}, "
                     f"confiance {f.confidence:.0%})_")
            if f.detail:
                L.append(f"{f.detail}\n")
            if f.evidence:
                L.append(f"> Preuve : `{f.evidence[:160].strip()}`\n")
            if f.recommendation:
                L.append(f"**Correctif :** {f.recommendation}\n")

    autres = [f for f in findings if f.severity not in (Severity.CRITICAL, Severity.HIGH)]
    if autres:
        L.append("## Autres constats et opportunités\n")
        for f in autres:
            L.append(f"- {_SEV_ICONE[f.severity]} **{f.title}** _({_ETIQ[f.nature]})_ — "
                     f"{f.recommendation or f.detail}")
        L.append("")

    L.append("---")
    L.append("_Légende : **MESURÉ** = relevé directement · **OBSERVÉ** = constaté "
             "sur la page · **DÉDUIT** = estimé par heuristique · **RECOMMANDÉ** = "
             "action proposée. Un score DÉDUIT n'est pas une garantie._")
    return "\n".join(L)


def comparaison_console(comp, raisons: list[str]) -> str:
    """Rendu terminal de la comparaison concurrentielle."""
    lignes = comp.tableau()
    rang, total = comp.rang_cible()
    L = ["\n  CiteRank · comparaison concurrentielle",
         f"  {'─' * 58}",
         f"  {'Domaine':<28}{'Global':>7}{'Ready':>7}{'Tech':>6}{'Schéma':>8}{'Cite':>6}"]
    for i, r in enumerate(sorted(lignes, key=lambda x: x['global'], reverse=True), 1):
        marque = " ◄ vous" if r["domaine"] == comp.cible.domain else ""
        L.append(f"  {r['domaine'][:27]:<28}{r['global']:>7.0f}"
                 f"{_n(r['readiness']):>7}{_n(r['technical']):>6}"
                 f"{_n(r['schema']):>8}{_n(r['citability']):>6}{marque}")
    L.append(f"\n  Votre rang : {rang}/{total}")
    L.append("\n  Pourquoi l'écart :")
    for r in raisons:
        propre = r.replace("**", "")
        L.append(f"    • {propre}")
    return "\n".join(L) + "\n"


def _n(v):
    return "—" if v is None else f"{v:.0f}"


def comparaison_markdown(comp, raisons: list[str]) -> str:
    lignes = sorted(comp.tableau(), key=lambda x: x["global"], reverse=True)
    rang, total = comp.rang_cible()
    L = [f"# Comparaison concurrentielle — {comp.cible.domain}",
         f"\n**Votre rang : {rang}/{total}**\n",
         "| Domaine | Global | Readiness | Technique | Schéma | Citabilité |",
         "|---|---:|---:|---:|---:|---:|"]
    for r in lignes:
        vous = " **◄ vous**" if r["domaine"] == comp.cible.domain else ""
        L.append(f"| {r['domaine']}{vous} | {r['global']:.0f} | {_n(r['readiness'])} | "
                 f"{_n(r['technical'])} | {_n(r['schema'])} | {_n(r['citability'])} |")
    L.append("\n## Pourquoi vos concurrents passent devant\n")
    for r in raisons:
        L.append(f"- {r}")
    L.append("\n---\n_Comparaison de Readiness : mesurée et déterministe. Elle ne "
             "présume pas de la visibilité réelle dans les réponses IA — voir le "
             "Share of Voice pour cela._")
    return "\n".join(L)


def resume_console(audit: SiteAudit) -> str:
    """Sortie compacte pour le terminal."""
    L = [f"\n  CiteRank · {audit.domain}",
         f"  {'─' * 46}",
         f"  Score global IA-Search : {audit.overall():.0f}/100\n"]
    for s in audit.scores:
        barre = "█" * int(s.value / 5) + "·" * (20 - int(s.value / 5))
        L.append(f"  {s.label:<28} {barre} {s.value:>3.0f}  [{_ETIQ[s.nature]}]")
    crit = [f for f in audit.findings
            if f.severity in (Severity.CRITICAL, Severity.HIGH)]
    if crit:
        L.append(f"\n  {len(crit)} problème(s) prioritaire(s) :")
        for f in crit[:6]:
            L.append(f"    {_SEV_ICONE[f.severity]} {f.title}")
    return "\n".join(L) + "\n"
