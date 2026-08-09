"""
Remediation engine — from audit to fix.

An audit that only reports is half-useful (point 10). This module GENERATES the
fixes: Organization JSON-LD, llms.txt, meta description, title suggestions.

ABSOLUTE, non-negotiable rule (point 10): never fabricate a fact. No fake
reviews, address, number, award, profile. A fix only fills fields DERIVED from
what already exists (title, domain, observed description) or explicitly provided
by the user. An unknown field is left empty, never invented.

The engine produces typed `Fix` objects: each carries its content, its target
and how to apply it. It's the caller (CLI, skill, SaaS) that decides whether to
write or just emit a snippet to paste — the engine never touches a file itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlparse

from .models import CrawledPage, SiteAudit, SiteContext


@dataclass
class Fix:
    id: str
    title: str
    kind: str            # "jsonld" | "file" | "meta" | "snippet"
    target: str          # where to apply it (<head>, /llms.txt, <meta> tag…)
    content: str
    note: str = ""


def _brand_from(page: CrawledPage, context: SiteContext | None) -> str:
    if context and context.brand:
        return context.brand
    # Derived from the title: the segment after the last dash is often the brand.
    if page.title:
        for sep in (" — ", " – ", " | ", " - "):
            if sep in page.title:
                cand = page.title.split(sep)[-1].strip()
                if 1 < len(cand) <= 40:
                    return cand
    return urlparse(page.final_url).netloc.split(".")[0]


def _logo_from(page: CrawledPage) -> str:
    """Look for a real logo in the page. None will be invented."""
    import re
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                  page.html, re.IGNORECASE)
    return m.group(1) if m else ""


def organization_jsonld(page: CrawledPage, context: SiteContext | None,
                        *, name: str = "", legal_name: str = "",
                        same_as: list[str] | None = None) -> Fix:
    """
    Generate an Organization block from available facts only. `same_as` is
    included only if the user provides it — never guessed.
    """
    root = f"{urlparse(page.final_url).scheme}://{urlparse(page.final_url).netloc}"
    brand = name or _brand_from(page, context)
    org: dict = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": brand,
        "url": root,
    }
    logo = _logo_from(page)
    if logo:
        org["logo"] = logo
    if page.meta_description:
        org["description"] = page.meta_description
    if legal_name and legal_name != brand:
        org["legalName"] = legal_name
    # sameAs: only what is provided and verifiable. Empty otherwise.
    links = [u for u in (same_as or []) if u.strip()]
    if links:
        org["sameAs"] = links

    content = ('<script type="application/ld+json">\n'
               + json.dumps(org, ensure_ascii=False, indent=2)
               + "\n</script>")
    return Fix(
        id="add-organization-jsonld",
        title="Add an Organization schema",
        kind="jsonld", target="<head>", content=content,
        note="Paste into <head>. sameAs left empty for lack of verified profiles — "
             "fill it with the real LinkedIn/Wikidata links once they exist.",
    )


def llms_txt(page: CrawledPage, context: SiteContext | None) -> Fix:
    """Generate an llms.txt from the home page's real internal links."""
    brand = _brand_from(page, context)
    desc = page.meta_description or ""
    lines = [f"# {brand}", ""]
    if desc:
        lines += [f"> {desc}", ""]
    lines.append("## Main pages")
    seen = set()
    for link in page.links_internal[:25]:
        path = urlparse(link).path.strip("/")
        if not path or path in seen:
            continue
        seen.add(path)
        label = path.split("/")[-1].replace("-", " ").capitalize()
        lines.append(f"- [{label}]({link})")
    return Fix(
        id="generate-llms-txt", title="Generate an llms.txt",
        kind="file", target="/llms.txt", content="\n".join(lines) + "\n",
        note="File to publish at the root. List derived from real internal links.",
    )


def meta_description(page: CrawledPage) -> Fix | None:
    if page.meta_description:
        return None
    # We propose a title-derived template — not a sentence invented about substance.
    base = page.title or _brand_from(page, None)
    content = f'<meta name="description" content="{base[:150]}">'
    return Fix(
        id="add-meta-description", title="Add a meta description",
        kind="meta", target="<head>", content=content,
        note="Title-derived template — rewrite it with a real value sentence.",
    )


def propose(audit: SiteAudit, page: CrawledPage, *,
            name: str = "", legal_name: str = "",
            same_as: list[str] | None = None) -> list[Fix]:
    """
    Select the fixes relevant to this audit. We only propose a fix if the matching
    finding exists: no fix for a problem that wasn't detected.
    """
    ids = {f.id for f in audit.findings}
    fixes: list[Fix] = []
    if "org-schema-missing" in ids or "no-jsonld" in ids:
        fixes.append(organization_jsonld(page, audit.context, name=name,
                                         legal_name=legal_name, same_as=same_as))
    if "llmstxt-missing" in ids:
        fixes.append(llms_txt(page, audit.context))
    if "meta-desc-missing" in ids:
        m = meta_description(page)
        if m:
            fixes.append(m)
    return fixes
