"""
Interface en ligne de commande — une simple peau sur le moteur (point 37).
Elle n'implémente aucune logique d'analyse : elle appelle `engine` / `visibility`
et met en forme. Le skill Claude Code et l'API REST feront de même.

    python -m citerank audit <url> [--json] [--md fichier] [--allow-local]
    python -m citerank visibility <url> --brand "Nom" [--queries f.txt] [--mock]
    python -m citerank doctor
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from urllib.parse import urlparse

from . import engine, report
from .providers import MockProvider, fournisseurs_disponibles


def _cmd_audit(args) -> int:
    audit = asyncio.run(engine.audit(args.url, autoriser_local=args.allow_local))
    if args.json:
        print(report.en_json(audit))
    else:
        print(report.resume_console(audit))
    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(report.en_markdown(audit))
        print(f"  → rapport Markdown : {args.md}")
    # Code de sortie utile en CI : échec si un problème critique subsiste.
    from .models import Severity
    critiques = [f for f in audit.findings if f.severity == Severity.CRITICAL]
    return 1 if critiques else 0


def _cmd_visibility(args) -> int:
    from . import visibility
    domaine = urlparse(args.url if "://" in args.url else "//" + args.url).netloc or args.url
    marque = args.brand or domaine.split(".")[0]

    if args.queries:
        with open(args.queries, encoding="utf-8") as f:
            queries = [l.strip() for l in f if l.strip()]
    else:
        queries = [
            f"Meilleure entreprise pour {marque.lower()} ?",
            f"Alternatives à {marque} ?",
            f"{marque} est-il fiable ?",
        ]

    provs = [MockProvider()] if args.mock else fournisseurs_disponibles()
    if not provs and not args.mock:
        print("  Aucun fournisseur IA configuré. Définis OPENAI_API_KEY, ou utilise "
              "--mock pour une démonstration hors ligne.", file=sys.stderr)
        return 2

    res = asyncio.run(visibility.mesurer(queries, marque=marque, domaine=domaine,
                                         providers=provs, runs=args.runs))
    score = visibility.score_visibilite(res)
    print(f"\n  Visibilité IA · {marque}")
    print(f"  {'─' * 46}")
    if score.get("score") is None:
        print(f"  Non mesuré : {score.get('raison')}")
        return 2
    print(f"  Score de visibilité : {score['score']}/100")
    print(f"    mention        : {score['taux_mention']}%")
    print(f"    recommandation : {score['taux_recommandation']}%")
    print(f"    citation       : {score['taux_citation']}%")
    print(f"\n  ⚠ {score['avertissement']}\n")
    return 0


def _cmd_competitors(args) -> int:
    from . import competitive
    concurrents = [u.strip() for u in (args.with_ or "").split(",") if u.strip()]
    if not concurrents:
        print("  Fournis au moins un concurrent : --with url1,url2", file=sys.stderr)
        return 2
    comp = asyncio.run(competitive.comparer(args.url, concurrents,
                                            autoriser_local=args.allow_local))
    raisons = competitive.expliquer_ecart(comp)
    print(report.comparaison_console(comp, raisons))
    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(report.comparaison_markdown(comp, raisons))
        print(f"  → rapport Markdown : {args.md}")
    return 0


def _cmd_sov(args) -> int:
    from . import competitive
    from .providers import MockProvider, fournisseurs_disponibles
    # marques : "Nom=domaine.fr", la première est la cible.
    marques = []
    for item in args.brands:
        nom, _, dom = item.partition("=")
        marques.append((nom.strip(), (dom or nom).strip()))
    if args.queries:
        with open(args.queries, encoding="utf-8") as f:
            queries = [l.strip() for l in f if l.strip()]
    else:
        cat = args.topic or marques[0][0]
        queries = [f"Meilleur service pour {cat} ?", f"Alternatives à {marques[0][0]} ?",
                   f"Qui recommandes-tu pour {cat} ?"]
    provs = [MockProvider()] if args.mock else fournisseurs_disponibles()
    if not provs:
        print("  Aucun fournisseur IA. Définis OPENAI_API_KEY ou utilise --mock.",
              file=sys.stderr)
        return 2
    res = asyncio.run(competitive.share_of_voice(marques, queries, providers=provs,
                                                 runs=args.runs))
    print(f"\n  Share of Voice IA · cible : {marques[0][0]}")
    print(f"  {'─' * 46}")
    if not res.get("classement"):
        print(f"  Non mesuré : {res.get('raison')}")
        return 2
    for i, r in enumerate(res["classement"], 1):
        vous = " ◄ vous" if r["marque"] == res["cible"] else ""
        print(f"  {i}. {r['marque']:<20} score {r['score']:>5}  "
              f"reco {r['recommandation']:>5}%  cite {r['citation']:>5}%{vous}")
    print(f"\n  Votre rang : {res['rang_cible']}/{res['total']}")
    print(f"  ⚠ {res['avertissement']}\n")
    return 0


def _cmd_doctor(args) -> int:
    print("  CiteRank · diagnostic")
    print(f"  Python           : {sys.version.split()[0]}")
    try:
        import bs4, aiohttp  # noqa
        print("  dépendances      : bs4 ✓  aiohttp ✓")
    except ImportError as e:
        print(f"  dépendances      : MANQUANTE — {e}")
        return 1
    dispo = fournisseurs_disponibles()
    if dispo:
        print(f"  fournisseurs IA  : {', '.join(p.name for p in dispo)}")
    else:
        print("  fournisseurs IA  : aucun (Readiness fonctionne sans clé ; "
              "la Visibility nécessite OPENAI_API_KEY)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="citerank",
                                description="Moteur open-source d'intelligence AI-Search.")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="Audit de Readiness (local, gratuit)")
    a.add_argument("url")
    a.add_argument("--json", action="store_true")
    a.add_argument("--md", metavar="FICHIER")
    a.add_argument("--allow-local", action="store_true",
                   help="autorise localhost/IP privées (développement uniquement)")
    a.set_defaults(func=_cmd_audit)

    v = sub.add_parser("visibility", help="Mesure de visibilité IA (nécessite une clé)")
    v.add_argument("url")
    v.add_argument("--brand")
    v.add_argument("--queries", metavar="FICHIER")
    v.add_argument("--runs", type=int, default=1)
    v.add_argument("--mock", action="store_true", help="démonstration hors ligne")
    v.set_defaults(func=_cmd_visibility)

    c = sub.add_parser("competitors", help="Comparaison de Readiness vs concurrents (local)")
    c.add_argument("url")
    c.add_argument("--with", dest="with_", metavar="URL1,URL2", required=True)
    c.add_argument("--md", metavar="FICHIER")
    c.add_argument("--allow-local", action="store_true")
    c.set_defaults(func=_cmd_competitors)

    sov = sub.add_parser("share-of-voice", help="Part de voix IA entre marques (nécessite une clé)")
    sov.add_argument("brands", nargs="+", metavar="Nom=domaine.fr",
                     help="marques comparées ; la première est la cible")
    sov.add_argument("--topic")
    sov.add_argument("--queries", metavar="FICHIER")
    sov.add_argument("--runs", type=int, default=1)
    sov.add_argument("--mock", action="store_true")
    sov.set_defaults(func=_cmd_sov)

    d = sub.add_parser("doctor", help="Vérifie l'environnement")
    d.set_defaults(func=_cmd_doctor)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
