"""
Agent Analytics — do AI crawlers actually visit this site?

This is the third axis, alongside Readiness (is the site prepared?) and
Visibility (does the AI cite the brand?): does the AI actually come and READ the
site? It's the highest-confidence signal in the whole tool, because it's neither
an estimate nor a sample — it's real hits, read from the server's access log.
Everything here is MEASURED.

The value mirrors what closed enterprise tools charge for ("agent analytics"),
but from the user's own logs, locally, with no black box: which AI bots came,
how often, on which pages — and, above all, which major engines have NEVER
crawled the site (a blind spot you can't see any other way).

Input: an access log in Common or Combined format (nginx/Apache default). No
network, fully deterministic.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# AI-crawler signatures, grouped by operator. The regex matches the User-Agent.
# Only unambiguous AI agents — we don't guess Googlebot's intent.
SIGNATURES: dict[str, list[tuple[str, str]]] = {
    "OpenAI (ChatGPT)": [("GPTBot", r"GPTBot"), ("ChatGPT-User", r"ChatGPT-User"),
                         ("OAI-SearchBot", r"OAI-SearchBot")],
    "Anthropic (Claude)": [("ClaudeBot", r"ClaudeBot"), ("Claude-Web", r"Claude-Web"),
                           ("anthropic-ai", r"anthropic-ai"), ("Claude-User", r"Claude-User")],
    "Perplexity": [("PerplexityBot", r"PerplexityBot"), ("Perplexity-User", r"Perplexity-User")],
    "Google (AI)": [("Google-Extended", r"Google-Extended"), ("GoogleOther", r"GoogleOther")],
    "Meta (AI)": [("meta-externalagent", r"meta-externalagent"),
                  ("FacebookBot", r"FacebookBot")],
    "Common Crawl": [("CCBot", r"CCBot")],          # feeds the training set of many LLMs
    "ByteDance": [("Bytespider", r"Bytespider")],
    "Amazon": [("Amazonbot", r"Amazonbot")],
    "Apple (AI)": [("Applebot-Extended", r"Applebot-Extended")],
    "Cohere": [("cohere-ai", r"cohere-ai")],
    "You.com": [("YouBot", r"YouBot")],
    "Diffbot": [("Diffbot", r"Diffbot")],
}

# The answer engines whose absence is a real blind spot, worth calling out.
MAJOR_ENGINES = ["OpenAI (ChatGPT)", "Anthropic (Claude)", "Perplexity",
                 "Google (AI)", "Meta (AI)"]

_COMPILED = [(op, name, re.compile(rx)) for op, sigs in SIGNATURES.items()
             for name, rx in sigs]

# Common/Combined log line: IP ... [date] "METHOD path proto" status size "ref" "UA"
_RE_LINE = re.compile(
    r'^\S+ \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) [^"]*" (\d{3}) \S+ "[^"]*" "([^"]*)"')
_RE_DATE = re.compile(r"^(\d{2})/(\w{3})/(\d{4})")
_MONTHS = {m: f"{i:02d}" for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _day(raw_date: str) -> str:
    m = _RE_DATE.match(raw_date)
    if not m:
        return ""
    d, mon, y = m.groups()
    return f"{y}-{_MONTHS.get(mon, '00')}-{d}"


@dataclass
class AgentHit:
    day: str
    path: str
    status: int
    bot: str
    operator: str


@dataclass
class AgentReport:
    total_requests: int = 0
    ai_hits: int = 0
    by_bot: Counter = field(default_factory=Counter)
    by_operator: Counter = field(default_factory=Counter)
    by_path: Counter = field(default_factory=Counter)
    by_day: Counter = field(default_factory=Counter)
    engines_seen: set[str] = field(default_factory=set)

    @property
    def engines_missing(self) -> list[str]:
        return [e for e in MAJOR_ENGINES if e not in self.engines_seen]

    def to_dict(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "ai_crawler_hits": self.ai_hits,
            "by_operator": dict(self.by_operator.most_common()),
            "by_bot": dict(self.by_bot.most_common()),
            "top_paths": dict(self.by_path.most_common(15)),
            "by_day": dict(sorted(self.by_day.items())),
            "major_engines_seen": sorted(self.engines_seen),
            "major_engines_missing": self.engines_missing,
        }


def match_agent(ua: str) -> tuple[str, str] | None:
    """Return (operator, bot) if the User-Agent is a known AI crawler."""
    for operator, name, rx in _COMPILED:
        if rx.search(ua):
            return operator, name
    return None


def analyze_lines(lines) -> AgentReport:
    report = AgentReport()
    for line in lines:
        m = _RE_LINE.match(line)
        if not m:
            continue
        report.total_requests += 1
        raw_date, _method, path, status, ua = m.groups()
        hit = match_agent(ua)
        if not hit:
            continue
        operator, bot = hit
        report.ai_hits += 1
        report.by_bot[bot] += 1
        report.by_operator[operator] += 1
        report.by_path[path] += 1
        report.by_day[_day(raw_date)] += 1
        report.engines_seen.add(operator)
    return report


def analyze_file(path: str) -> AgentReport:
    with open(path, encoding="utf-8", errors="replace") as f:
        return analyze_lines(f)
