# CiteRank

**Open-source AI-Search intelligence.** Measure, understand and improve how a
brand shows up in the answers of ChatGPT, Gemini, Perplexity and Claude — not
just in Google.

CiteRank answers four questions that classic SEO tools don't ask:

1. **Can AI engines understand this site?** → *Readiness* score
2. **Do AI engines actually mention this brand?** → *Visibility* score
3. **Why does a competitor get cited instead?** → *competitive intelligence*
4. **What exactly should change?** → *remediation*

## What makes it different

- **A real engine, not a pile of Markdown files.** All the logic lives in a
  Python package (`citerank/`), independent of any interface. The CLI, the Claude
  Code skill, a future REST API and a SaaS are just skins over that core. This is
  what lets it grow from a terminal tool into a hosted product without rewriting
  the analysis.
- **Readiness ≠ Visibility.** A perfectly prepared site isn't necessarily cited.
  The two are never conflated — not in the scores, not in the reports.
- **The free layer is local.** The Readiness audit makes no LLM calls:
  deterministic, no key, unlimited. Visibility (which costs real API calls) is a
  separate layer.
- **Honesty as a feature.** Every data point is labeled *measured*, *observed*,
  *inferred* or *recommended*. Citability rests on semantic signals, not a
  "134–167 words" rule.

## Install

```bash
git clone https://github.com/bruceleeFR/citerank && cd citerank
pip install -e .
citerank doctor
```

Minimal dependencies: `aiohttp`, `beautifulsoup4`. Python 3.10+.

## First audit (free, offline)

```bash
citerank audit https://yoursite.com
```

```
  CiteRank · yoursite.com
  ──────────────────────────────────────────────
  Overall AI-Search score : 50/100

  AI Readiness              ██████████··········  54  [MEASURED]
  Technical SEO             ████████████████████ 100  [MEASURED]
  Structured data           ████················  20  [MEASURED]
  Citability                ██··················  14  [INFERRED]

  1 priority issue(s):
    🟠 Organization schema missing
```

Detailed report: `citerank audit <url> --md report.md`
Machine output: `citerank audit <url> --json`
Shareable HTML: `citerank report <url> --with competitor.com`

## Measure real visibility (needs a key)

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
citerank visibility https://yoursite.com --brand "Your Brand" --runs 3
```

Without a key, `--mock` demonstrates the flow offline (results are explicitly
labeled fake). With two providers, consensus across engines becomes meaningful.

## Commands

| Command | What it does |
|---|---|
| `audit` | Readiness audit (local, free) |
| `competitors` | Readiness comparison vs competitors + "why they win" |
| `visibility` | Real AI visibility (needs an API key) |
| `share-of-voice` | AI share of voice across brands |
| `agents` | AI-crawler activity from your access log — which engines actually read you (MEASURED) |
| `fix` | Generate fixes (JSON-LD, llms.txt, meta) — never fabricates facts |
| `report` | Standalone, shareable HTML report |
| `init` / `monitor` / `compare` | Project mode: dated snapshots, regression detection |
| `serve` | REST API (the SaaS seam) |
| `doctor` | Check the environment |

## Architecture

```
        ┌─ Claude Code skill ─┐
        ├─ CLI ───────────────┤
        ├─ REST API ──────────┤──► citerank/ (ENGINE)
        ├─ SaaS ──────────────┤        ├─ crawl.py      (normalized crawl + anti-SSRF)
        └─ Jarvis ────────────┘        ├─ analyzers/    (technical, schema, citability)
                                       ├─ providers/    (OpenAI, Anthropic … adapters)
                                       ├─ visibility.py (multi-provider consensus)
                                       ├─ scoring       (transparent multi-score)
                                       └─ report*.py    (md / json / html)
```

The engine depends on no interface. That's the guiding principle.

## Editions

The free/paid line falls exactly on the Readiness/Visibility boundary — which is
also the local/expensive boundary. See [`docs/EDITIONS.md`](docs/EDITIONS.md).

## License

MIT. Inspired by [geo-seo-claude](https://github.com/zubair-trabzada/geo-seo-claude);
see [`NOTICE.md`](NOTICE.md) for attribution.
