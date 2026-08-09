"""
CiteRank — open-source AI-Search intelligence engine.

Answers four separate questions:
  A. Can AI engines UNDERSTAND this site?          (Readiness)
  B. Do AI engines MENTION this brand?             (Visibility)
  C. WHY is a competitor cited instead?            (Competitive)
  D. WHAT exactly should change?                   (Remediation)

The core is independent of any interface: CLI, Claude Code skill, REST API and
SaaS are just skins over `engine` and `visibility`.
"""

__version__ = "0.1.0"

from . import engine, visibility  # noqa: F401
