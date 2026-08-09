# Security

## Surface and safeguards

CiteRank fetches user-provided URLs. Two risks are handled at the root:

- **SSRF.** Every URL is validated before a single network byte
  (`citerank/crawl.py`). Refused by default: `localhost`, private ranges
  (RFC 1918), link-local — including the cloud metadata endpoint
  `169.254.169.254` — and schemes other than `http`/`https`. Local access is only
  possible with the explicit `--allow-local` flag.
- **Secret leakage.** API keys come only from the environment, never from code or
  logs. Reports contain no secrets. The mock provider talks to no network.

## What CiteRank sends where

- The **Readiness** audit is 100% local: it only contacts the analyzed site.
- **Visibility** sends *test queries* to the configured AI providers (OpenAI,
  Anthropic…). It does **not** send the site's source code.
- Each provider is disabled by removing its key from the environment.

## Reporting a vulnerability

Open a private Security advisory rather than a public issue. Describe the
reproduction. We respond before disclosure.
