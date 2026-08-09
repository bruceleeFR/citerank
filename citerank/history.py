"""
Project mode and monitoring (points 12, 20).

`citerank init` creates a `.geo/` folder; subsequent audits drop a timestamped
snapshot into it. `citerank compare` measures the evolution — and above all
detects REGRESSIONS, which is the real point of tracking: a falling score is
more urgent than a low but stable one.

Everything is local and deterministic: no network call, just a JSON store.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import SiteAudit

FOLDER = ".geo"


def project_root(start: str | None = None) -> Path:
    """Walk up the tree to find a .geo/, otherwise the current folder."""
    p = Path(start or os.getcwd()).resolve()
    for parent in [p, *p.parents]:
        if (parent / FOLDER).is_dir():
            return parent / FOLDER
    return p / FOLDER


def init(start: str | None = None) -> Path:
    base = Path(start or os.getcwd()).resolve() / FOLDER
    (base / "history").mkdir(parents=True, exist_ok=True)
    (base / "reports").mkdir(parents=True, exist_ok=True)
    cfg = base / "config.yaml"
    if not cfg.exists():
        cfg.write_text(
            "# CiteRank project\n"
            "agency:\n  name: \"\"\n  email: \"\"\n"
            "branding:\n  primary_color: \"#ff8a4c\"\n  accent_color: \"#8b7dff\"\n"
            "report:\n  show_methodology: true\n  show_competitors: true\n",
            encoding="utf-8")
    return base


def _slug(domain: str) -> str:
    return domain.replace(".", "_").replace(":", "_")


def save_snapshot(audit: SiteAudit, base: Path | None = None) -> Path:
    base = base or project_root()
    hist = base / "history"
    hist.mkdir(parents=True, exist_ok=True)
    # The timestamp comes from the audit itself (audit.started_at), not from a
    # clock read here: the snapshot stays faithful to the moment of measurement.
    stamp = audit.started_at.replace(":", "").replace("-", "").replace("+", "_")
    path = hist / f"{_slug(audit.domain)}-{stamp}.json"
    path.write_text(json.dumps(audit.to_dict(), ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


def snapshots(domain: str, base: Path | None = None) -> list[dict]:
    base = base or project_root()
    hist = base / "history"
    if not hist.is_dir():
        return []
    files = sorted(hist.glob(f"{_slug(domain)}-*.json"))
    out = []
    for f in files:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return out


def compare(old: dict, new: dict) -> dict:
    """
    Difference between two snapshots. Returns a typed dict: overall-score
    evolution, per-score evolution, and the list of regressions (drops) surfaced.
    """
    def scores(snap):
        return {s["key"]: s["value"] for s in snap.get("scores", [])}

    so, sn = scores(old), scores(new)
    deltas = []
    for key in sorted(set(so) | set(sn)):
        before, after = so.get(key), sn.get(key)
        if before is None or after is None:
            continue
        deltas.append({"key": key, "before": before, "after": after,
                       "delta": round(after - before, 1)})

    regressions = [d for d in deltas if d["delta"] <= -3]
    gains = [d for d in deltas if d["delta"] >= 3]
    g_before = old.get("overall_ai_search_score", 0)
    g_after = new.get("overall_ai_search_score", 0)
    return {
        "from": old.get("started_at"), "to": new.get("started_at"),
        "overall": {"before": g_before, "after": g_after,
                    "delta": round(g_after - g_before, 1)},
        "deltas": deltas,
        "regressions": regressions,
        "gains": gains,
    }
