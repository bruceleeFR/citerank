"""
Crawl normalisé et partagé.

Deux idées, toutes deux tirées des faiblesses du projet amont :

1. UNE seule récupération par URL, réutilisée par tous les analyseurs (point 23).
   Le cache mémoire garantit qu'un audit ne retélécharge jamais la même page,
   même si dix analyseurs la demandent.

2. Validation d'URL DÈS l'entrée (point 17). On refuse par défaut localhost,
   les IP privées et les points de métadonnées cloud (169.254.169.254). Un
   outil qui accepte une URL arbitraire et va la chercher est une SSRF en
   puissance : ici c'est bloqué avant le moindre octet réseau.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

from .models import CrawledPage, now_iso

UA = "CiteRankBot/0.1 (+https://github.com/; AI search readiness auditor)"

# Plages interdites par défaut : boucle locale, réseaux privés, lien-local
# (dont le point de métadonnées cloud 169.254.169.254), et l'espace de
# documentation. Débloquables seulement en mode développement explicite.
def _est_hote_sur(host: str) -> tuple[bool, str]:
    if not host:
        return False, "hôte vide"
    if host.lower() in {"localhost", "localhost.localdomain"}:
        return False, "localhost interdit"
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, f"résolution DNS impossible pour {host}"
    for famille, *_rest, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, f"cible interne interdite ({ip})"
    return True, ""


def valider_url(url: str, autoriser_local: bool = False) -> str:
    """Renvoie une URL normalisée, ou lève ValueError. Première ligne de défense."""
    u = urlparse(url if "://" in url else "https://" + url)
    if u.scheme not in {"http", "https"}:
        raise ValueError(f"schéma refusé : {u.scheme!r} (http/https uniquement)")
    if not u.netloc:
        raise ValueError("URL sans hôte")
    if not autoriser_local:
        sur, motif = _est_hote_sur(u.hostname or "")
        if not sur:
            raise ValueError(f"URL bloquée : {motif}")
    return u.geturl()


class Crawler:
    """
    Récupère et normalise les pages. Un cache par instance : le même Crawler
    passé à tous les analyseurs = zéro requête en double.
    """

    def __init__(self, *, timeout: float = 20.0, concurrence: int = 5,
                 autoriser_local: bool = False):
        self._cache: dict[str, CrawledPage] = {}
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._sem = asyncio.Semaphore(concurrence)
        self._autoriser_local = autoriser_local

    async def get(self, url: str, session: aiohttp.ClientSession) -> CrawledPage:
        url = valider_url(url, self._autoriser_local)
        if url in self._cache:
            return self._cache[url]
        async with self._sem:
            page = await self._fetch(url, session)
        self._cache[url] = page
        return page

    async def _fetch(self, url: str, session: aiohttp.ClientSession) -> CrawledPage:
        try:
            async with session.get(url, allow_redirects=True) as r:
                html = await r.text(errors="replace")
                page = self._parse(url, str(r.url), r.status, dict(r.headers), html)
                return page
        except asyncio.TimeoutError:
            return CrawledPage(url=url, status=0, final_url=url, fetched_at=now_iso(),
                               headers={}, html="", text="", error="délai dépassé")
        except aiohttp.ClientError as e:
            return CrawledPage(url=url, status=0, final_url=url, fetched_at=now_iso(),
                               headers={}, html="", text="", error=f"réseau : {e}")

    def _parse(self, url, final_url, status, headers, html) -> CrawledPage:
        soup = BeautifulSoup(html, "html.parser")

        for balise in soup(["script", "style", "noscript", "template"]):
            balise.extract()
        # On garde le JSON-LD : il a été retiré ci-dessus avec les <script>, on
        # le relit donc sur le HTML brut, pas sur l'arbre nettoyé.
        json_ld = self._extraire_json_ld(html)

        titre = (soup.title.string or "").strip() if soup.title else ""
        meta_desc = ""
        m = soup.find("meta", attrs={"name": "description"})
        if m and m.get("content"):
            meta_desc = m["content"].strip()

        lang = ""
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            lang = html_tag["lang"].strip()

        h1 = [h.get_text(strip=True) for h in soup.find_all("h1")]
        headings = [(int(h.name[1]), h.get_text(strip=True))
                    for h in soup.find_all(["h1", "h2", "h3", "h4"])]

        base = urlparse(final_url)
        internes, externes = [], []
        for a in soup.find_all("a", href=True):
            href = urljoin(final_url, a["href"])
            hp = urlparse(href)
            if hp.scheme not in {"http", "https"}:
                continue
            (internes if hp.netloc == base.netloc else externes).append(href)

        texte = " ".join(soup.get_text(" ").split())

        return CrawledPage(
            url=url, status=status, final_url=final_url, fetched_at=now_iso(),
            headers={k.lower(): v for k, v in headers.items()},
            html=html, text=texte, title=titre, meta_description=meta_desc,
            lang=lang, h1=h1, headings=headings, json_ld=json_ld,
            links_internal=sorted(set(internes)), links_external=sorted(set(externes)),
        )

    @staticmethod
    def _extraire_json_ld(html: str) -> list[dict]:
        import json
        import re
        blocs = []
        for m in re.finditer(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.DOTALL | re.IGNORECASE,
        ):
            brut = m.group(1).strip()
            try:
                data = json.loads(brut)
                blocs.extend(data if isinstance(data, list) else [data])
            except json.JSONDecodeError:
                # Un JSON-LD invalide est en soi un constat, remonté par
                # l'analyseur de schéma. Ici on ne fait que le sauter.
                continue
        return blocs

    async def texte_brut(self, url: str, session: aiohttp.ClientSession) -> str:
        """Pour robots.txt / llms.txt : pas de parsing HTML."""
        url = valider_url(url, self._autoriser_local)
        try:
            async with session.get(url, allow_redirects=True) as r:
                if 200 <= r.status < 300:
                    return await r.text(errors="replace")
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        return ""


def nouvelle_session(timeout: float = 20.0) -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout),
        headers={"User-Agent": UA, "Accept-Language": "fr,en;q=0.8"},
    )
