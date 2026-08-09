# Contributing

Thanks for the interest. A few principles define the project's identity —
respecting them keeps CiteRank credible.

## Non-negotiable rules

1. **Never present an inference as a measurement.** Every data point carries its
   nature (`Nature` in `models.py`). A heuristic is `INFERRED`, not `MEASURED`.
2. **Never fabricate a fact.** Remediation only fills fields derived from the site
   or provided by the user. No fake reviews, addresses, numbers, profiles.
3. **The engine stays interface-independent.** No business logic in the CLI or a
   future skill: it lives in `citerank/`.
4. **No secrets in code or logs.** Keys come from the environment.

## Development

```bash
pip install -e ".[dev]"
python tests/test_core.py     # offline tests, no service required
ruff check citerank           # style
```

Unit tests must not depend on the network: mock the crawl with a `CrawledPage`
and providers with `MockProvider`.

## Adding an AI provider

Implement `providers/base.Provider`, read the key from the environment, never
raise (return an empty `ProviderResult` on error), and register the class in
`providers/__init__.py`.
