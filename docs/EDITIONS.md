# Editions — what's free, what's paid

This document freezes the boundary so the architecture doesn't drift. The rule is
simple and defensible:

> **Free = anything that costs €0 to run. Paid = anything that calls paid LLM
> APIs, or requires an always-on server.**

The customer never pays to *unlock* a crippled feature. They pay because
infrastructure absorbs a real cost on their behalf. Zero resentment.

## Open-Source edition (MIT, self-hosted)

Everything that is **local and deterministic**. It must be excellent on its own:
it's the acquisition, not a mutilated lead-gen product.

| Capability | Command |
|---|---|
| Audit + Readiness (technical, schema, citability) | `citerank audit` |
| Competitive comparison (on Readiness) | `citerank competitors` |
| Fix generation (JSON-LD, llms.txt, meta) | `citerank fix` |
| Standalone shareable HTML report | `citerank report` |
| Local snapshots and evolution | `citerank monitor` / `compare` |
| AI visibility **with your own API key** | `citerank visibility` |

Visibility works in open-source **if the user brings their own key**: they pay
their provider directly. That's honest and amputates nothing.

## Hosted edition (SaaS, separate private repo)

What is **structurally impossible** on a laptop, or **costs money to run**. The
MIT engine is imported as-is — nothing is rewritten (guiding principle).

| Capability | Why it's paid |
|---|---|
| Turnkey multi-engine AI visibility | we absorb the LLM call costs |
| Continuous share-of-voice measurement | same, at scale and over time |
| 24/7 monitoring + regression alerts | requires an always-on server |
| Team accounts, white-label client portals | multi-tenant, hosting |
| Historical dashboard, PDF at scale | server-side storage and rendering |
| Public "Analyze": paste a URL on the site | protected behind quota/account |

### The trap never to forget

A free, public "Analyze" that runs visibility for every stranger = an LLM bill
that explodes on the first traffic spike. On the hosted version, **Readiness stays
the free hook** (zero cost), **Visibility goes behind an account or quota**. The
hosted product's free/paid line is the same as the one between editions: local vs
expensive.

## Licensing

- **Engine** (`citerank/`): MIT. Maximum adoption — acquisition demands it.
- **SaaS layer** (dashboard, billing, multi-tenant): private repo, imports the
  engine. The moat isn't the code — it's the hosted infra and absorbing API
  costs. No restrictive license needed to protect it.
