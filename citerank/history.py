"""
Mode projet et monitoring (points 12, 20).

`citerank init` crée un dossier `.geo/` ; les audits suivants y déposent un
instantané horodaté. `citerank compare` mesure l'évolution — et surtout détecte
les RÉGRESSIONS, ce qui est le vrai intérêt d'un suivi : un score qui baisse est
plus urgent qu'un score bas et stable.

Tout est local et déterministe : aucun appel réseau, un simple magasin de JSON.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import SiteAudit

DOSSIER = ".geo"


def racine_projet(depart: str | None = None) -> Path:
    """Remonte l'arborescence jusqu'à trouver un .geo/, sinon le dossier courant."""
    p = Path(depart or os.getcwd()).resolve()
    for parent in [p, *p.parents]:
        if (parent / DOSSIER).is_dir():
            return parent / DOSSIER
    return p / DOSSIER


def init(depart: str | None = None) -> Path:
    base = Path(depart or os.getcwd()).resolve() / DOSSIER
    (base / "history").mkdir(parents=True, exist_ok=True)
    (base / "reports").mkdir(parents=True, exist_ok=True)
    cfg = base / "config.yaml"
    if not cfg.exists():
        cfg.write_text(
            "# Projet CiteRank\n"
            "agency:\n  name: \"\"\n  email: \"\"\n"
            "branding:\n  primary_color: \"#ff8a4c\"\n  accent_color: \"#8b7dff\"\n"
            "report:\n  show_methodology: true\n  show_competitors: true\n",
            encoding="utf-8")
    return base


def _slug(domaine: str) -> str:
    return domaine.replace(".", "_").replace(":", "_")


def enregistrer(audit: SiteAudit, base: Path | None = None) -> Path:
    base = base or racine_projet()
    hist = base / "history"
    hist.mkdir(parents=True, exist_ok=True)
    # L'horodatage vient de l'audit lui-même (audit.started_at), pas d'une
    # horloge lue ici : l'instantané reste fidèle au moment de la mesure.
    horodatage = audit.started_at.replace(":", "").replace("-", "").replace("+", "_")
    chemin = hist / f"{_slug(audit.domain)}-{horodatage}.json"
    chemin.write_text(json.dumps(audit.to_dict(), ensure_ascii=False, indent=2),
                      encoding="utf-8")
    return chemin


def instantanes(domaine: str, base: Path | None = None) -> list[dict]:
    base = base or racine_projet()
    hist = base / "history"
    if not hist.is_dir():
        return []
    fichiers = sorted(hist.glob(f"{_slug(domaine)}-*.json"))
    out = []
    for f in fichiers:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return out


def comparer(ancien: dict, nouveau: dict) -> dict:
    """
    Écart entre deux instantanés. Retourne un dict typé : évolution du score
    global, par score, et la liste des régressions (baisses) mises en avant.
    """
    def scores(snap):
        return {s["key"]: s["value"] for s in snap.get("scores", [])}

    sa, sn = scores(ancien), scores(nouveau)
    deltas = []
    for cle in sorted(set(sa) | set(sn)):
        avant, apres = sa.get(cle), sn.get(cle)
        if avant is None or apres is None:
            continue
        deltas.append({"key": cle, "avant": avant, "apres": apres,
                       "delta": round(apres - avant, 1)})

    regressions = [d for d in deltas if d["delta"] <= -3]
    gains = [d for d in deltas if d["delta"] >= 3]
    g_avant = ancien.get("overall_ai_search_score", 0)
    g_apres = nouveau.get("overall_ai_search_score", 0)
    return {
        "de": ancien.get("started_at"), "a": nouveau.get("started_at"),
        "global": {"avant": g_avant, "apres": g_apres,
                   "delta": round(g_apres - g_avant, 1)},
        "deltas": deltas,
        "regressions": regressions,
        "gains": gains,
    }
