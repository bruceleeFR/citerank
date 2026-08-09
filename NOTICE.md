# Attribution

CiteRank is inspired by **[geo-seo-claude](https://github.com/zubair-trabzada/geo-seo-claude)**
by zubair-trabzada, released under the MIT License.

## What is reused, and what is not

CiteRank is a **rewrite**, not a fork. No file from the upstream project was
copied verbatim. What is inherited are **ideas** — the notion of a GEO audit, the
command palette (`audit`, `citability`, `schema`, `crawlers`, `llmstxt`…), the
"AI visibility over Google" framing.

What is **new and different**:

- a **Python engine independent of any interface**, where the upstream keeps its
  logic in Claude Code Markdown skills (here the CLI, the skill, an API and a
  SaaS are all just skins over the same core);
- a **strict separation** between readiness, real visibility and share of voice —
  the upstream mixes the three;
- **semantic citability** replacing the upstream's "134–167 words" rule, which its
  own README elevates into a universal threshold;
- **labeling the nature** of every data point (measured / observed / inferred /
  recommended), so an inference is never shown as a fact;
- **anti-SSRF URL validation** at the crawl boundary.

Per the MIT License, the upstream copyright notice is preserved. CiteRank does
not claim to be the original author of the idea of a GEO tool for Claude Code.

Copyright (c) 2025 zubair-trabzada — upstream `geo-seo-claude` (MIT).
Copyright (c) 2026 LAMARCA and CiteRank contributors.
