"""
Couche API REST — la porte vers le SaaS (point 37).

C'est ici que le principe directeur paie : l'API ne réimplémente RIEN. Elle
appelle `engine`, `competitive`, `report_html` — exactement comme la CLI. Le
futur dashboard Lamarca tapera cette API, et le moteur ne saura même pas qu'il
sert un SaaS plutôt qu'un terminal.

Bâtie sur aiohttp, déjà présent : aucune dépendance nouvelle. Volontairement
minimale et en lecture seule — la Readiness est gratuite, donc exposable ; la
Visibilité (coûteuse) restera derrière un quota dans la couche hébergée, pas
ici.

Sécurité : chaque URL passe par `valider_url` (anti-SSRF) avant toute requête,
et un sémaphore borne la concurrence pour qu'un pic de trafic ne fasse pas
tomber le service.
"""

from __future__ import annotations

import asyncio

from aiohttp import web

from . import competitive, engine, report_html
from .crawl import valider_url

_LIMITE = asyncio.Semaphore(8)  # borne le nombre d'audits simultanés


def _json_erreur(message: str, code: int = 400) -> web.Response:
    return web.json_response({"error": message}, status=code)


async def _health(_req: web.Request) -> web.Response:
    from . import __version__
    return web.json_response({"service": "citerank", "version": __version__, "ok": True})


async def _audit(req: web.Request) -> web.Response:
    data = await _corps(req)
    url = (data or {}).get("url", "")
    if not url:
        return _json_erreur("champ 'url' requis")
    try:
        valider_url(url)                       # rejette localhost / IP privées / etc.
    except ValueError as e:
        return _json_erreur(f"URL refusée : {e}", 422)
    async with _LIMITE:
        audit = await engine.audit(url)
    return web.json_response(audit.to_dict())


async def _competitors(req: web.Request) -> web.Response:
    data = await _corps(req)
    url = (data or {}).get("url", "")
    concurrents = (data or {}).get("competitors", [])
    if not url or not concurrents:
        return _json_erreur("champs 'url' et 'competitors' (liste) requis")
    try:
        valider_url(url)
        for c in concurrents:
            valider_url(c)
    except ValueError as e:
        return _json_erreur(f"URL refusée : {e}", 422)
    async with _LIMITE:
        comp = await competitive.comparer(url, list(concurrents))
    return web.json_response({
        "cible": comp.cible.to_dict(),
        "tableau": comp.tableau(),
        "rang": comp.rang_cible(),
        "explication": competitive.expliquer_ecart(comp),
    })


async def _report(req: web.Request) -> web.Response:
    url = req.query.get("url", "")
    if not url:
        return _json_erreur("paramètre 'url' requis")
    try:
        valider_url(url)
    except ValueError as e:
        return _json_erreur(f"URL refusée : {e}", 422)
    async with _LIMITE:
        audit = await engine.audit(url)
    html = report_html.rendre(audit, marque_agence=req.query.get("agency", ""))
    return web.Response(text=html, content_type="text/html")


async def _corps(req: web.Request) -> dict | None:
    if req.can_read_body:
        try:
            return await req.json()
        except Exception:
            return None
    return None


def creer_app() -> web.Application:
    app = web.Application()
    app.add_routes([
        web.get("/health", _health),
        web.post("/api/audit", _audit),
        web.post("/api/competitors", _competitors),
        web.get("/api/report", _report),           # renvoie le rapport HTML
    ])
    return app


def servir(host: str = "127.0.0.1", port: int = 8900) -> None:
    web.run_app(creer_app(), host=host, port=port, print=lambda *_: None)
    # (print silencieux : la CLI affiche sa propre bannière)
