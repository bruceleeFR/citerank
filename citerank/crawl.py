"""
Normalized, shared crawl.

Two ideas, both drawn from the upstream's weaknesses:

1. ONE fetch per URL, reused by every analyzer (point 23). The in-memory cache
   guarantees an audit never refetches the same page, even if ten analyzers ask
   for it.

2. URL validation AT ENTRY (point 17). By default we refuse localhost, private
   IPs and cloud metadata endpoints (169.254.169.254). A tool that accepts an
   arbitrary URL and goes to fetch it is a latent SSRF: here it's blocked before
   the first network byte.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

from .models import CrawledPage, now_iso

UA = "CiteRankBot/0.1 (+https://github.com/bruceleeFR/citerank; AI search readiness auditor)"


# Ranges forbidden by default: loopback, private networks, link-local (including
# the cloud metadata endpoint 169.254.169.254), reserved and multicast space.
# Only unlockable in explicit development mode.
def _is_safe_host(host: str) -> tuple[bool, str]:
    if not host:
        return False, "empty host"
    if host.lower() in {"localhost", "localhost.localdomain"}:
        return False, "localhost forbidden"
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, f"DNS resolution failed for {host}"
    for _family, *_rest, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, f"internal target forbidden ({ip})"
    return True, ""


def validate_url(url: str, allow_local: bool = False) -> str:
    """Return a normalized URL, or raise ValueError. First line of defense."""
    u = urlparse(url if "://" in url else "https://" + url)
    if u.scheme not in {"http", "https"}:
        raise ValueError(f"scheme refused: {u.scheme!r} (http/https only)")
    if not u.netloc:
        raise ValueError("URL without host")
    if not allow_local:
        safe, reason = _is_safe_host(u.hostname or "")
        if not safe:
            raise ValueError(f"URL blocked: {reason}")
    return u.geturl()


class Crawler:
    """
    Fetches and normalizes pages. One cache per instance: the same Crawler passed
    to every analyzer = zero duplicate requests.
    """

    def __init__(self, *, timeout: float = 20.0, concurrency: int = 5,
                 allow_local: bool = False):
        self._cache: dict[str, CrawledPage] = {}
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._sem = asyncio.Semaphore(concurrency)
        self._allow_local = allow_local

    async def get(self, url: str, session: aiohttp.ClientSession) -> CrawledPage:
        url = validate_url(url, self._allow_local)
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
                return self._parse(url, str(r.url), r.status, dict(r.headers), html)
        except asyncio.TimeoutError:
            return CrawledPage(url=url, status=0, final_url=url, fetched_at=now_iso(),
                               headers={}, html="", text="", error="timed out")
        except aiohttp.ClientError as e:
            return CrawledPage(url=url, status=0, final_url=url, fetched_at=now_iso(),
                               headers={}, html="", text="", error=f"network: {e}")

    def _parse(self, url, final_url, status, headers, html) -> CrawledPage:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "noscript", "template"]):
            tag.extract()
        # JSON-LD was removed above with the <script> tags, so we re-read it from
        # the raw HTML, not from the cleaned tree.
        json_ld = self._extract_json_ld(html)

        title = (soup.title.string or "").strip() if soup.title else ""
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
        internal, external = [], []
        for a in soup.find_all("a", href=True):
            href = urljoin(final_url, a["href"])
            hp = urlparse(href)
            if hp.scheme not in {"http", "https"}:
                continue
            (internal if hp.netloc == base.netloc else external).append(href)

        text = " ".join(soup.get_text(" ").split())

        return CrawledPage(
            url=url, status=status, final_url=final_url, fetched_at=now_iso(),
            headers={k.lower(): v for k, v in headers.items()},
            html=html, text=text, title=title, meta_description=meta_desc,
            lang=lang, h1=h1, headings=headings, json_ld=json_ld,
            links_internal=sorted(set(internal)), links_external=sorted(set(external)),
        )

    @staticmethod
    def _extract_json_ld(html: str) -> list[dict]:
        import json
        import re
        blocks = []
        for m in re.finditer(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.DOTALL | re.IGNORECASE,
        ):
            raw = m.group(1).strip()
            try:
                data = json.loads(raw)
                blocks.extend(data if isinstance(data, list) else [data])
            except json.JSONDecodeError:
                # Invalid JSON-LD is itself a finding, raised by the schema
                # analyzer. Here we just skip it.
                continue
        return blocks

    async def fetch_text(self, url: str, session: aiohttp.ClientSession) -> str:
        """For robots.txt / llms.txt: no HTML parsing."""
        url = validate_url(url, self._allow_local)
        try:
            async with session.get(url, allow_redirects=True) as r:
                if 200 <= r.status < 300:
                    return await r.text(errors="replace")
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        return ""


def new_session(timeout: float = 20.0) -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout),
        headers={"User-Agent": UA, "Accept-Language": "en,fr;q=0.8"},
    )
