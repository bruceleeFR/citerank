"""
REST API layer — the door to the SaaS (point 37).

This is where the guiding principle pays off: the API reimplements NOTHING. It
calls `engine`, `competitive`, `report_html` — exactly like the CLI. The future
Lamarca dashboard will hit this API, and the engine won't even know it's serving
a SaaS rather than a terminal.

Built on aiohttp, already present: no new dependency. Deliberately minimal and
read-only — Readiness is free, so it's exposable; Visibility (costly) will sit
behind a quota in the hosted layer, not here.

Security: every URL passes through `validate_url` (anti-SSRF) before any request,
and a semaphore bounds concurrency so a traffic spike doesn't take the service
down.
"""

from __future__ import annotations

import asyncio

from aiohttp import web

from . import competitive, engine, report_html
from .crawl import validate_url

_LIMIT = asyncio.Semaphore(8)  # bound the number of concurrent audits


def _json_error(message: str, code: int = 400) -> web.Response:
    return web.json_response({"error": message}, status=code)


async def _health(_req: web.Request) -> web.Response:
    from . import __version__
    return web.json_response({"service": "citerank", "version": __version__, "ok": True})


async def _audit(req: web.Request) -> web.Response:
    data = await _body(req)
    url = (data or {}).get("url", "")
    if not url:
        return _json_error("field 'url' required")
    try:
        validate_url(url)                      # rejects localhost / private IPs / etc.
    except ValueError as e:
        return _json_error(f"URL refused: {e}", 422)
    async with _LIMIT:
        audit = await engine.audit(url)
    return web.json_response(audit.to_dict())


async def _competitors(req: web.Request) -> web.Response:
    data = await _body(req)
    url = (data or {}).get("url", "")
    competitors = (data or {}).get("competitors", [])
    if not url or not competitors:
        return _json_error("fields 'url' and 'competitors' (list) required")
    try:
        validate_url(url)
        for c in competitors:
            validate_url(c)
    except ValueError as e:
        return _json_error(f"URL refused: {e}", 422)
    async with _LIMIT:
        comp = await competitive.compare(url, list(competitors))
    return web.json_response({
        "target": comp.target.to_dict(),
        "table": comp.table(),
        "rank": comp.target_rank(),
        "explanation": competitive.explain_gap(comp),
    })


async def _report(req: web.Request) -> web.Response:
    url = req.query.get("url", "")
    if not url:
        return _json_error("query param 'url' required")
    try:
        validate_url(url)
    except ValueError as e:
        return _json_error(f"URL refused: {e}", 422)
    async with _LIMIT:
        audit = await engine.audit(url)
    html = report_html.render(audit, agency_brand=req.query.get("agency", ""))
    return web.Response(text=html, content_type="text/html")


async def _body(req: web.Request) -> dict | None:
    if req.can_read_body:
        try:
            return await req.json()
        except Exception:
            return None
    return None


def create_app() -> web.Application:
    app = web.Application()
    app.add_routes([
        web.get("/health", _health),
        web.post("/api/audit", _audit),
        web.post("/api/competitors", _competitors),
        web.get("/api/report", _report),           # returns the HTML report
    ])
    return app


def serve(host: str = "127.0.0.1", port: int = 8900) -> None:
    web.run_app(create_app(), host=host, port=port, print=lambda *_: None)
    # (silent print: the CLI prints its own banner)
