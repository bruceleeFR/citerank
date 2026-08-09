"""
Typed data models for the engine.

Reason to exist: the upstream project passes large Markdown blobs between its
components. Here, everything that flows through the engine is a typed object.
Markdown only appears at the very end, in the report generator — never as an
internal exchange format.

No dependencies: standard-library dataclasses. Pydantic would be a luxury; static
typing plus manual JSON serialization is enough, and keeps the engine installable
without a dependency tree.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Nature(str, Enum):
    """
    The product's cardinal distinction (point 18): never present an inference as
    a measurement. Every data point carries its nature.

      MEASURED   — read directly (an HTTP header, a JSON-LD block present).
      OBSERVED   — seen on the page (a FAQ exists, an H1 is there).
      INFERRED   — estimated by heuristic ("this passage is citable").
      RECOMMENDED — a proposed action, not a fact.
    """
    MEASURED = "measured"
    OBSERVED = "observed"
    INFERRED = "inferred"
    RECOMMENDED = "recommended"


@dataclass
class Finding:
    """
    A single finding. The evidence system (point 25) requires every finding to
    carry its source, severity, confidence and action.
    """
    id: str
    title: str
    severity: Severity
    nature: Nature
    confidence: float           # 0.0 → 1.0
    category: str
    source: str                 # exact URL or location
    detail: str = ""
    recommendation: str = ""
    evidence: str = ""          # raw excerpt that justifies the finding

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["nature"] = self.nature.value
        return d


@dataclass
class ScoreComponent:
    """One brick of a score. This is what makes a score transparent (point 2)."""
    key: str
    label: str
    points: float               # points earned
    max_points: float           # points possible
    nature: Nature
    detail: str = ""

    @property
    def ratio(self) -> float:
        return self.points / self.max_points if self.max_points else 0.0


@dataclass
class Score:
    """
    A score out of 100 — never a bare number: it carries its components, its
    method and its confidence. A Readiness score (measured) and a Visibility
    score (sampled) don't have the same authority, and saying so is a credibility
    argument, not an admission of weakness (point 30).
    """
    key: str
    label: str
    value: float                # 0 → 100
    nature: Nature
    confidence: float
    components: list[ScoreComponent] = field(default_factory=list)
    methodology: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": round(self.value, 1),
            "nature": self.nature.value,
            "confidence": round(self.confidence, 2),
            "methodology": self.methodology,
            "components": [
                {
                    "key": c.key, "label": c.label,
                    "points": round(c.points, 1), "max_points": c.max_points,
                    "nature": c.nature.value, "detail": c.detail,
                }
                for c in self.components
            ],
        }


@dataclass
class CrawledPage:
    """
    Normalized representation of a page, produced ONCE and shared by every
    analyzer (point 23). Without it, each analyzer would refetch the same page —
    the exact defect the spec points out.
    """
    url: str
    status: int
    final_url: str
    fetched_at: str
    headers: dict[str, str]
    html: str
    text: str                            # extracted visible text
    title: str = ""
    meta_description: str = ""
    lang: str = ""
    h1: list[str] = field(default_factory=list)
    headings: list[tuple[int, str]] = field(default_factory=list)  # (level, text)
    json_ld: list[dict] = field(default_factory=list)
    links_internal: list[str] = field(default_factory=list)
    links_external: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and 200 <= self.status < 400


@dataclass
class SiteContext:
    """What we know about the entity before querying an AI engine."""
    url: str
    domain: str
    brand: str = ""
    robots_txt: str = ""
    llms_txt: str = ""
    sitemap_present: bool = False


@dataclass
class SiteAudit:
    """The complete result of an audit. This is what the engine serializes."""
    url: str
    domain: str
    started_at: str
    finished_at: str = ""
    scores: list[Score] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    context: SiteContext | None = None

    def score(self, key: str) -> Score | None:
        return next((s for s in self.scores if s.key == key), None)

    def overall(self) -> float:
        """
        Overall score: weighted average of available scores. Deliberately
        conservative — a missing score does not count as a zero (which would
        punish a local audit that didn't run visibility); it is dropped from the
        denominator.
        """
        weights = {
            "readiness": 0.25, "technical": 0.15, "schema": 0.10,
            "citability": 0.15, "content": 0.10, "entity": 0.10,
            "visibility": 0.15,
        }
        num = den = 0.0
        for s in self.scores:
            w = weights.get(s.key, 0.0)
            if w:
                num += s.value * w
                den += w
        return round(num / den, 1) if den else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "domain": self.domain,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "overall_ai_search_score": self.overall(),
            "scores": [s.to_dict() for s in self.scores],
            "findings": [f.to_dict() for f in self.findings],
        }


# --- Visibility-layer models (sampled, non-deterministic) --------------------

@dataclass
class ProviderResult:
    """One AI engine's answer to one query, for one brand."""
    provider: str
    query: str
    brand_mentioned: bool
    brand_recommended: bool
    domain_cited: bool
    citation_url: str = ""
    position: int | None = None          # rank at which the brand appears
    competitors: list[str] = field(default_factory=list)
    sentiment: str = ""                  # positive / neutral / negative
    raw_excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VisibilityResult:
    """Multi-provider consensus for one query (point 13)."""
    query: str
    runs: list[ProviderResult] = field(default_factory=list)

    @property
    def mention_rate(self) -> float:
        return self._rate(lambda r: r.brand_mentioned)

    @property
    def recommendation_rate(self) -> float:
        return self._rate(lambda r: r.brand_recommended)

    @property
    def citation_rate(self) -> float:
        return self._rate(lambda r: r.domain_cited)

    def _rate(self, pred) -> float:
        return sum(1 for r in self.runs if pred(r)) / len(self.runs) if self.runs else 0.0

    @property
    def confidence(self) -> str:
        """
        Confidence comes from CONSISTENCY across runs and providers. A brand
        mentioned 9 times out of 10 is a fact; 5 out of 10 is a doubt. We say so,
        we don't smooth it over (point 13).
        """
        if not self.runs:
            return "none"
        r = self.mention_rate
        if r >= 0.8 or r <= 0.2:
            return "high"
        if 0.4 <= r <= 0.6:
            return "low"
        return "medium"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
