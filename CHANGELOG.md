# Changelog

Format inspired by [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Changed
- Full English pass across the codebase: docs, comments, docstrings, identifiers
  and user-facing output. English is the working language of the project.

### Added
- **Agent Analytics** (`agents`): AI-crawler activity from an access log — which engines actually read the site, and which never did (MEASURED, from real logs).
- **Anthropic** provider adapter — visibility consensus now rests on two real
  engines (OpenAI + Anthropic), not one.
- **REST API** (`citerank serve`): `/api/audit`, `/api/competitors`,
  `/api/report`. The engine serves HTTP without rewriting anything.
- `docs/EDITIONS.md`: frozen boundary between the open-source and hosted editions.
- `SECURITY.md`, `CONTRIBUTING.md`, GitHub Actions CI.

## [0.1.0]

First foundation — independent rewrite inspired by `geo-seo-claude` (MIT).

### Added
- **Agent Analytics** (`agents`): AI-crawler activity from an access log — which engines actually read the site, and which never did (MEASURED, from real logs).
- **Interface-independent Python engine**: CLI, skill, API and SaaS are just
  skins over `citerank/`.
- **Readiness**, local and deterministic: technical (robots, sitemap, llms.txt,
  AI crawlers, transport, head tags), structured data (entity vs transactional,
  sameAs), **semantic** citability (replaces the upstream's "134–167 words" rule).
- **Competitive intelligence**: readiness comparison and a "why they win"
  explanation, backed only by measured gaps.
- **Share of voice** across brands, via provider consensus.
- **Remediation** (`fix`): generates JSON-LD, llms.txt, meta — never fabricating a
  fact.
- **Standalone HTML report**, shareable, light/dark theme, white-label.
- **Monitoring**: `.geo/` project mode, dated snapshots, `compare` with regression
  detection.
- Systematic labeling of data nature (measured / observed / inferred /
  recommended). Anti-SSRF URL validation. Offline tests.
