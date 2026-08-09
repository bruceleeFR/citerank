"""
CiteRank — moteur open-source d'intelligence AI-Search.

Répond à quatre questions séparées :
  A. Les moteurs IA COMPRENNENT-ils ce site ?          (Readiness)
  B. Les moteurs IA MENTIONNENT-ils cette marque ?     (Visibility)
  C. POURQUOI un concurrent est-il cité à sa place ?   (Competitive)
  D. QUE changer exactement ?                          (Remediation)

Le cœur est indépendant de toute interface : CLI, skill Claude Code, API REST et
SaaS ne sont que des peaux sur `engine` et `visibility`.
"""

__version__ = "0.1.0"

from . import engine, visibility  # noqa: F401
