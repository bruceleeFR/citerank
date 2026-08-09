"""
Command-line interface — a thin skin over the engine (point 37). It implements no
analysis logic: it calls `engine` / `visibility` and formats. The Claude Code
skill and the REST API do the same.

    python -m citerank audit <url> [--json] [--md file] [--allow-local]
    python -m citerank visibility <url> --brand "Name" [--queries f.txt] [--mock]
    python -m citerank doctor
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from urllib.parse import urlparse

from . import engine, report
from .providers import MockProvider, available_providers


def _cmd_audit(args) -> int:
    audit = asyncio.run(engine.audit(args.url, allow_local=args.allow_local))
    if args.json:
        print(report.to_json(audit))
    else:
        print(report.console_summary(audit))
    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(report.to_markdown(audit))
        print(f"  → Markdown report: {args.md}")
    # Exit code useful in CI: fail if a critical issue remains.
    from .models import Severity
    critical = [f for f in audit.findings if f.severity == Severity.CRITICAL]
    return 1 if critical else 0


def _cmd_visibility(args) -> int:
    from . import visibility
    domain = urlparse(args.url if "://" in args.url else "//" + args.url).netloc or args.url
    brand = args.brand or domain.split(".")[0]

    if args.queries:
        with open(args.queries, encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]
    else:
        queries = [
            f"Best company for {brand.lower()}?",
            f"Alternatives to {brand}?",
            f"Is {brand} reputable?",
        ]

    provs = [MockProvider()] if args.mock else available_providers()
    if not provs and not args.mock:
        print("  No AI provider configured. Set OPENAI_API_KEY, or use --mock for an "
              "offline demo.", file=sys.stderr)
        return 2

    res = asyncio.run(visibility.measure(queries, brand=brand, domain=domain,
                                         providers=provs, runs=args.runs))
    score = visibility.visibility_score(res)
    print(f"\n  AI Visibility · {brand}")
    print(f"  {'─' * 46}")
    if score.get("score") is None:
        print(f"  Not measured: {score.get('reason')}")
        return 2
    print(f"  Visibility score: {score['score']}/100")
    print(f"    mention        : {score['mention_rate']}%")
    print(f"    recommendation : {score['recommendation_rate']}%")
    print(f"    citation       : {score['citation_rate']}%")
    print(f"\n  ⚠ {score['warning']}\n")
    return 0


def _cmd_competitors(args) -> int:
    from . import competitive
    competitors = [u.strip() for u in (args.with_ or "").split(",") if u.strip()]
    if not competitors:
        print("  Provide at least one competitor: --with url1,url2", file=sys.stderr)
        return 2
    comp = asyncio.run(competitive.compare(args.url, competitors,
                                           allow_local=args.allow_local))
    reasons = competitive.explain_gap(comp)
    print(report.comparison_console(comp, reasons))
    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(report.comparison_markdown(comp, reasons))
        print(f"  → Markdown report: {args.md}")
    return 0


def _cmd_sov(args) -> int:
    from . import competitive
    # brands: "Name=domain.com", the first is the target.
    brands = []
    for item in args.brands:
        name, _, dom = item.partition("=")
        brands.append((name.strip(), (dom or name).strip()))
    if args.queries:
        with open(args.queries, encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]
    else:
        topic = args.topic or brands[0][0]
        queries = [f"Best service for {topic}?", f"Alternatives to {brands[0][0]}?",
                   f"Who do you recommend for {topic}?"]
    provs = [MockProvider()] if args.mock else available_providers()
    if not provs:
        print("  No AI provider. Set OPENAI_API_KEY or use --mock.", file=sys.stderr)
        return 2
    res = asyncio.run(competitive.share_of_voice(brands, queries, providers=provs,
                                                 runs=args.runs))
    print(f"\n  AI Share of Voice · target: {brands[0][0]}")
    print(f"  {'─' * 46}")
    if not res.get("ranking"):
        print(f"  Not measured: {res.get('reason')}")
        return 2
    for i, r in enumerate(res["ranking"], 1):
        you = " ◄ you" if r["brand"] == res["target"] else ""
        print(f"  {i}. {r['brand']:<20} score {r['score']:>5}  "
              f"reco {r['recommendation']:>5}%  cite {r['citation']:>5}%{you}")
    print(f"\n  Your rank: {res['target_rank']}/{res['total']}")
    print(f"  ⚠ {res['warning']}\n")
    return 0


def _cmd_fix(args) -> int:
    from . import remediation
    from .crawl import Crawler, new_session, validate_url

    async def _run():
        url = validate_url(args.url, args.allow_local)
        a = await engine.audit(url, allow_local=args.allow_local)
        # Fetch the page once more to generate fixes from its real content
        # (links, og:image, description).
        crawler = Crawler(allow_local=args.allow_local)
        async with new_session() as s:
            page = await crawler.get(url, s)
        same_as = [u.strip() for u in (args.same_as or "").split(",") if u.strip()]
        fixes = remediation.propose(a, page, name=args.name or "",
                                    legal_name=args.legal_name or "", same_as=same_as)
        return a, fixes

    a, fixes = asyncio.run(_run())
    if not fixes:
        print("  No automatic fix to propose (nothing detected to fix).")
        return 0
    print(f"\n  CiteRank · proposed fixes for {a.domain}")
    print(f"  {'─' * 50}")
    for f in fixes:
        print(f"\n  ▸ {f.title}  →  {f.target}")
        if f.note:
            print(f"    {f.note}")
        print("    " + "\n    ".join(f.content.splitlines()))
        if args.write_dir and f.kind == "file":
            import os
            path = os.path.join(args.write_dir, f.target.lstrip("/"))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f.content)
            print(f"    ✓ written: {path}")
    print("\n  The <head> blocks are to paste (or apply via the skill on a local "
          "project). No fact was fabricated.\n")
    return 0


def _cmd_report(args) -> int:
    from . import report_html
    comp = None
    if args.with_:
        from . import competitive
        competitors = [u.strip() for u in args.with_.split(",") if u.strip()]
        comp = asyncio.run(competitive.compare(args.url, competitors,
                                               allow_local=args.allow_local))
        audit = comp.target
    else:
        audit = asyncio.run(engine.audit(args.url, allow_local=args.allow_local))
    html = report_html.render(audit, comparison=comp, agency_brand=args.agency or "")
    out = args.out or f"citerank-{audit.domain.replace('.', '_')}.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  → standalone HTML report: {out}  (score {audit.overall():.0f}/100)")
    return 0


def _cmd_init(args) -> int:
    from . import history
    base = history.init(args.path)
    print(f"  CiteRank project initialized: {base}")
    return 0


def _cmd_monitor(args) -> int:
    from . import history
    audit = asyncio.run(engine.audit(args.url, allow_local=args.allow_local))
    path = history.save_snapshot(audit)
    print(f"  Snapshot saved: {path}  (score {audit.overall():.0f}/100)")
    return 0


def _cmd_compare(args) -> int:
    from . import history
    domain = urlparse(args.url if "://" in args.url else "//" + args.url).netloc or args.url
    snaps = history.snapshots(domain)
    if len(snaps) < 2:
        print(f"  Need at least 2 snapshots (found: {len(snaps)}). "
              f"Run `citerank monitor {args.url}` regularly.", file=sys.stderr)
        return 2
    d = history.compare(snaps[0], snaps[-1])
    print(f"\n  Evolution · {domain}")
    print(f"  {'─' * 46}")
    g = d["overall"]
    arrow = "▲" if g["delta"] > 0 else ("▼" if g["delta"] < 0 else "=")
    print(f"  Overall score: {g['before']:.0f} → {g['after']:.0f}  {arrow} {g['delta']:+.0f}")
    for x in d["deltas"]:
        a = "▲" if x["delta"] > 0 else ("▼" if x["delta"] < 0 else "=")
        print(f"    {x['key']:<14} {x['before']:.0f} → {x['after']:.0f}  {a} {x['delta']:+.0f}")
    if d["regressions"]:
        print(f"\n  ⚠ REGRESSION on: {', '.join(r['key'] for r in d['regressions'])}")
    print()
    return 0


def _cmd_serve(args) -> int:
    from . import api
    print(f"  CiteRank API on http://{args.host}:{args.port}")
    print("    GET  /health")
    print("    POST /api/audit          {\"url\": \"...\"}")
    print("    POST /api/competitors    {\"url\": \"...\", \"competitors\": [...]}")
    print("    GET  /api/report?url=...\n")
    api.serve(args.host, args.port)
    return 0


def _cmd_doctor(args) -> int:
    print("  CiteRank · diagnostic")
    print(f"  Python           : {sys.version.split()[0]}")
    try:
        import aiohttp, bs4  # noqa
        print("  dependencies     : bs4 ✓  aiohttp ✓")
    except ImportError as e:
        print(f"  dependencies     : MISSING — {e}")
        return 1
    provs = available_providers()
    if provs:
        print(f"  AI providers     : {', '.join(p.name for p in provs)}")
    else:
        print("  AI providers     : none (Readiness works without a key; "
              "Visibility needs OPENAI_API_KEY / ANTHROPIC_API_KEY)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="citerank",
                                description="Open-source AI-Search intelligence engine.")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="Readiness audit (local, free)")
    a.add_argument("url")
    a.add_argument("--json", action="store_true")
    a.add_argument("--md", metavar="FILE")
    a.add_argument("--allow-local", action="store_true",
                   help="allow localhost/private IPs (development only)")
    a.set_defaults(func=_cmd_audit)

    v = sub.add_parser("visibility", help="AI visibility measurement (needs a key)")
    v.add_argument("url")
    v.add_argument("--brand")
    v.add_argument("--queries", metavar="FILE")
    v.add_argument("--runs", type=int, default=1)
    v.add_argument("--mock", action="store_true", help="offline demo")
    v.set_defaults(func=_cmd_visibility)

    c = sub.add_parser("competitors", help="Readiness comparison vs competitors (local)")
    c.add_argument("url")
    c.add_argument("--with", dest="with_", metavar="URL1,URL2", required=True)
    c.add_argument("--md", metavar="FILE")
    c.add_argument("--allow-local", action="store_true")
    c.set_defaults(func=_cmd_competitors)

    sov = sub.add_parser("share-of-voice", help="AI share of voice across brands (needs a key)")
    sov.add_argument("brands", nargs="+", metavar="Name=domain.com",
                     help="brands compared; the first is the target")
    sov.add_argument("--topic")
    sov.add_argument("--queries", metavar="FILE")
    sov.add_argument("--runs", type=int, default=1)
    sov.add_argument("--mock", action="store_true")
    sov.set_defaults(func=_cmd_sov)

    fx = sub.add_parser("fix", help="Generate fixes (JSON-LD, llms.txt, meta)")
    fx.add_argument("url")
    fx.add_argument("--name", help="exact brand name (else derived from the title)")
    fx.add_argument("--legal-name", help="legal name, if different")
    fx.add_argument("--same-as", metavar="URL1,URL2",
                    help="verified profiles (LinkedIn, Wikidata…) — never guessed")
    fx.add_argument("--write-dir", metavar="FOLDER",
                    help="write generated files (llms.txt) into this folder")
    fx.add_argument("--allow-local", action="store_true")
    fx.set_defaults(func=_cmd_fix)

    rp = sub.add_parser("report", help="Standalone, shareable HTML report")
    rp.add_argument("url")
    rp.add_argument("--with", dest="with_", metavar="URL1,URL2",
                    help="add a competitive comparison")
    rp.add_argument("--out", metavar="FILE.html")
    rp.add_argument("--agency", help="white-label: agency name in the footer")
    rp.add_argument("--allow-local", action="store_true")
    rp.set_defaults(func=_cmd_report)

    ini = sub.add_parser("init", help="Initialize a project (.geo/) for tracking")
    ini.add_argument("path", nargs="?", default=".")
    ini.set_defaults(func=_cmd_init)

    mon = sub.add_parser("monitor", help="Save a dated snapshot")
    mon.add_argument("url")
    mon.add_argument("--allow-local", action="store_true")
    mon.set_defaults(func=_cmd_monitor)

    cmp = sub.add_parser("compare", help="Evolution between the first and last snapshot")
    cmp.add_argument("url")
    cmp.set_defaults(func=_cmd_compare)

    sv = sub.add_parser("serve", help="Run the REST API (SaaS layer)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8900)
    sv.set_defaults(func=_cmd_serve)

    d = sub.add_parser("doctor", help="Check the environment")
    d.set_defaults(func=_cmd_doctor)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
