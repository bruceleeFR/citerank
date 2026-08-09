"""
Modèles de données typés du moteur.

Raison d'être : le projet amont fait circuler de gros blocs Markdown entre ses
composants (point faible n°24 du cahier des charges). Ici, tout ce qui traverse
le moteur est un objet typé. Le Markdown n'apparaît qu'au tout dernier moment,
dans le générateur de rapport — jamais comme structure d'échange interne.

Aucune dépendance : dataclasses de la bibliothèque standard. Pydantic serait un
luxe ; le typage statique et la sérialisation JSON manuelle suffisent, et gardent
le moteur installable sans arbre de dépendances.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
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
    Distinction cardinale du produit (point 18) : on ne présente jamais une
    déduction comme une mesure. Chaque donnée porte sa nature.

      MEASURED  — relevé directement (un en-tête HTTP, un bloc JSON-LD présent).
      OBSERVED  — constaté sur la page (une FAQ existe, un H1 est là).
      INFERRED  — estimé par heuristique (« ce passage est citable »).
      RECOMMENDED — action proposée, pas un fait.
    """
    MEASURED = "measured"
    OBSERVED = "observed"
    INFERRED = "inferred"
    RECOMMENDED = "recommended"


@dataclass
class Finding:
    """
    Un constat unitaire. Le système de preuve (point 25) impose que chaque
    constat porte sa source, sa sévérité, sa confiance et son action.
    """
    id: str
    title: str
    severity: Severity
    nature: Nature
    confidence: float           # 0.0 → 1.0
    category: str
    source: str                 # URL ou emplacement exact
    detail: str = ""
    recommendation: str = ""
    evidence: str = ""          # extrait brut qui justifie le constat

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["nature"] = self.nature.value
        return d


@dataclass
class ScoreComponent:
    """Une brique d'un score. C'est ce qui rend la note transparente (point 2)."""
    key: str
    label: str
    points: float               # points obtenus
    max_points: float           # points possibles
    nature: Nature
    detail: str = ""

    @property
    def ratio(self) -> float:
        return self.points / self.max_points if self.max_points else 0.0


@dataclass
class Score:
    """
    Un score sur 100, jamais un nombre nu : il porte ses composantes, sa
    méthode et son niveau de confiance. Un score de Readiness (mesuré) et un
    score de Visibility (échantillonné) n'ont pas la même autorité, et le dire
    est un argument de crédibilité, pas un aveu de faiblesse (point 30).
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
    Représentation normalisée d'une page, produite UNE fois et partagée par tous
    les analyseurs (point 23). Sans elle, chaque analyseur retéléchargerait la
    même page — le défaut exact que le cahier des charges pointe.
    """
    url: str
    status: int
    final_url: str
    fetched_at: str
    headers: dict[str, str]
    html: str
    text: str                            # texte visible extrait
    title: str = ""
    meta_description: str = ""
    lang: str = ""
    h1: list[str] = field(default_factory=list)
    headings: list[tuple[int, str]] = field(default_factory=list)  # (niveau, texte)
    json_ld: list[dict] = field(default_factory=list)
    links_internal: list[str] = field(default_factory=list)
    links_external: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and 200 <= self.status < 400


@dataclass
class SiteContext:
    """Ce qu'on sait de l'entité avant d'interroger un moteur IA."""
    url: str
    domain: str
    brand: str = ""
    robots_txt: str = ""
    llms_txt: str = ""
    sitemap_present: bool = False


@dataclass
class SiteAudit:
    """Le résultat complet d'un audit. C'est ce que sérialise le moteur."""
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
        Score global : moyenne pondérée des scores disponibles. Volontairement
        conservateur — un score absent ne compte pas comme un zéro (ce qui
        punirait un audit local qui n'a pas lancé la visibilité), il est retiré
        du dénominateur.
        """
        poids = {
            "readiness": 0.25, "technical": 0.15, "schema": 0.10,
            "citability": 0.15, "content": 0.10, "entity": 0.10,
            "visibility": 0.15,
        }
        num = den = 0.0
        for s in self.scores:
            w = poids.get(s.key, 0.0)
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


# --- Modèles de la couche Visibilité (échantillonnée, non déterministe) ------

@dataclass
class ProviderResult:
    """Réponse d'UN moteur IA à UNE requête, sur UN passage."""
    provider: str
    query: str
    brand_mentioned: bool
    brand_recommended: bool
    domain_cited: bool
    citation_url: str = ""
    position: int | None = None          # rang d'apparition de la marque
    competitors: list[str] = field(default_factory=list)
    sentiment: str = ""                  # positif / neutre / négatif
    raw_excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VisibilityResult:
    """Consensus multi-fournisseurs pour une requête (point 13)."""
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
        La confiance vient de la CONSTANCE entre exécutions et fournisseurs.
        Une marque citée 9 fois sur 10 est un fait ; 5 sur 10 est un doute. On
        le dit, on ne le lisse pas (point 13).
        """
        r = self.mention_rate
        spread = max((self._rate(lambda x: x.brand_mentioned) for _ in [0]), default=0)
        if not self.runs:
            return "none"
        if r >= 0.8 or r <= 0.2:
            return "high"
        if 0.4 <= r <= 0.6:
            return "low"
        return "medium"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
