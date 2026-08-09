# V2 Architecture Proposal

## The finding on the upstream

`geo-seo-claude` (9.3k stars, MIT) is a **Claude Code skill**. Its analysis logic
lives in a dozen `SKILL.md` files that orchestrate a few Python scripts
(`fetch_page.py`, `citability_scorer.py`, `brand_scanner.py`). Consequences:

- **The product IS the interface.** You can't turn it into an API, a SaaS or a
  Jarvis brick without rewriting everything: the value is trapped in the skill
  format.
- **Citability is a word-count rule** ("134–167 words"), elevated into a universal
  threshold by the README itself.
- **No separation** between readiness, real visibility and share of voice: a
  single "GEO Score" aggregates things of different natures.
- **No labeling** of data nature: an inference and a measurement look alike in the
  report.

## The guiding principle (point 37)

> Claude Code must be **one** interface to the engine, not the engine.

```
        ┌─ Claude Code skill
        ├─ CLI                  ← shipped
GEO ────├─ REST API             ← shipped
ENGINE  ├─ Jarvis
        ├─ SaaS Lamarca
        └─ Client Dashboard
```

The open-source repo on GitHub is acquisition; the hosted version becomes the
paid SaaS. The free/paid line falls exactly on the Readiness/Visibility boundary,
which is also the local/expensive boundary: the three overlap, so the business
model is carried by the architecture itself.

## Shipped tree

```
citerank/
  models.py          Types (Finding, Score, CrawledPage, SiteAudit, …) — end of internal Markdown blobs
  crawl.py           Normalized, shared, cached crawl + anti-SSRF validation
  engine.py          Orchestrator — THE core entry point
  analyzers/
    technical.py     robots, sitemap, llms.txt, AI crawlers, HTTPS, head tags
    schema_ld.py     JSON-LD, entity vs transactional, sameAs
    citability.py    SEMANTIC citability (replaces the 150-word rule)
  providers/
    base.py          common contract; keys from the environment only
    openai_provider.py    OpenAI / OpenRouter-compatible
    anthropic_provider.py Anthropic (Claude)
    mock.py          deterministic, offline, for tests and demos
  visibility.py      multi-provider consensus + explicit confidence
  competitive.py     comparison + "why they win" + share of voice
  remediation.py     fix generation, never fabricating facts
  report.py          md / json
  report_html.py     standalone shareable HTML
  history.py         project mode + monitoring + regression detection
  api.py             REST API (the SaaS seam)
  cli.py             CLI skin (no business logic)
```

## EXISTING / IMPROVED / NEW matrix

| Capability | Upstream | CiteRank |
|---|---|---|
| Technical audit | ✅ skill | ✅ **typed engine** |
| Schema analysis | ✅ | ✅ entity vs transactional, sameAs |
| Citability | 150-word rule | 🔁 **semantic signals** |
| Shared crawl | ❌ (refetch) | 🆕 single cached crawl |
| Anti-SSRF | ❌ | 🆕 URL validation at entry |
| Readiness vs Visibility | ❌ mixed | 🆕 **separated** |
| Real visibility (LLM) | partial | 🆕 consensus + confidence |
| Measured/inferred labeling | ❌ | 🆕 everywhere |
| Independent engine | ❌ | 🆕 **reusable core** |
| Competitive intelligence | ❌ | ✅ comparison + "why they win" |
| Share of voice | ❌ | ✅ multi-brand |
| Remediation `fix` | ❌ | ✅ no fabricated facts |
| Shareable HTML report | ❌ | ✅ light/dark, white-label |
| Monitoring + regressions | ❌ | ✅ `.geo/` snapshots |
| REST API | ❌ | ✅ `citerank serve` |
| PDF report | ✅ | ⏳ roadmap |

## Roadmap

1. ✅ Engine + local Readiness + OpenAI/Anthropic visibility + reports + tests.
2. ✅ Competitive intelligence + share of voice.
3. ✅ Remediation (`fix`), never fabricating facts.
4. ✅ Shareable report + monitoring.
5. ✅ REST API layer.
6. Gemini and Perplexity adapters.
7. Deterministic query-universe generator (monthly comparisons).
8. Entity Intelligence (entity graph, sameAs, external sources).
9. "Consulting deliverable" PDF report + white-label agency mode.
10. REST API → dashboard → SaaS, without touching the engine.
