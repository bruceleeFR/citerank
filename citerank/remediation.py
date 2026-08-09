"""
Moteur de remédiation — de l'audit à la correction.

Un audit qui ne fait que constater est à moitié utile (point 10). Ce module
GÉNÈRE les correctifs : JSON-LD Organization, llms.txt, meta description,
suggestions de titres.

RÈGLE ABSOLUE, non négociable (point 10) : ne jamais fabriquer de fait. Pas de
faux avis, de fausse adresse, de faux chiffre, de fausse récompense, de faux
profil `sameAs`. Un correctif ne remplit que des champs DÉRIVÉS de ce qui existe
déjà (titre, domaine, description observée) ou explicitement fournis par
l'utilisateur. Un champ inconnu est laissé vide, jamais inventé.

Le moteur produit des objets `Fix` typés : chacun porte son contenu, sa cible et
la façon de l'appliquer. C'est l'appelant (CLI, skill, SaaS) qui décide d'écrire
ou de se contenter d'un extrait à coller — le moteur ne touche jamais un fichier
de lui-même.
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
    target: str          # où l'appliquer (<head>, /llms.txt, balise <meta>…)
    content: str
    note: str = ""


def _brand_from(page: CrawledPage, contexte: SiteContext | None) -> str:
    if contexte and contexte.brand:
        return contexte.brand
    # Dérivé du titre : le segment après le dernier tiret est souvent la marque.
    if page.title:
        for sep in (" — ", " – ", " | ", " - "):
            if sep in page.title:
                cand = page.title.split(sep)[-1].strip()
                if 1 < len(cand) <= 40:
                    return cand
    return urlparse(page.final_url).netloc.split(".")[0]


def _logo_from(page: CrawledPage) -> str:
    """Cherche un logo réel dans la page. Aucun ne sera inventé."""
    import re
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                  page.html, re.IGNORECASE)
    return m.group(1) if m else ""


def organization_jsonld(page: CrawledPage, contexte: SiteContext | None,
                        *, name: str = "", legal_name: str = "",
                        same_as: list[str] | None = None) -> Fix:
    """
    Génère un bloc Organization à partir des seuls faits disponibles. `same_as`
    n'est inclus que si l'utilisateur le fournit — jamais deviné.
    """
    racine = f"{urlparse(page.final_url).scheme}://{urlparse(page.final_url).netloc}"
    brand = name or _brand_from(page, contexte)
    org: dict = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": brand,
        "url": racine,
    }
    logo = _logo_from(page)
    if logo:
        org["logo"] = logo
    if page.meta_description:
        org["description"] = page.meta_description
    if legal_name and legal_name != brand:
        org["legalName"] = legal_name
    # sameAs : uniquement ce qui est fourni et vérifiable. Vide sinon.
    liens = [u for u in (same_as or []) if u.strip()]
    if liens:
        org["sameAs"] = liens

    contenu = ('<script type="application/ld+json">\n'
               + json.dumps(org, ensure_ascii=False, indent=2)
               + "\n</script>")
    return Fix(
        id="add-organization-jsonld",
        title="Ajouter un schéma Organization",
        kind="jsonld", target="<head>", content=contenu,
        note="À coller dans le <head>. sameAs laissé vide faute de profils vérifiés — "
             "à compléter avec les vrais liens LinkedIn/Wikidata quand ils existent.",
    )


def llms_txt(page: CrawledPage, contexte: SiteContext | None) -> Fix:
    """Génère un llms.txt à partir des liens internes réels de la page d'accueil."""
    brand = _brand_from(page, contexte)
    desc = page.meta_description or ""
    lignes = [f"# {brand}", ""]
    if desc:
        lignes += [f"> {desc}", ""]
    lignes.append("## Pages principales")
    vus = set()
    for lien in page.links_internal[:25]:
        chemin = urlparse(lien).path.strip("/")
        if not chemin or chemin in vus:
            continue
        vus.add(chemin)
        label = chemin.split("/")[-1].replace("-", " ").capitalize()
        lignes.append(f"- [{label}]({lien})")
    return Fix(
        id="generate-llms-txt", title="Générer un llms.txt",
        kind="file", target="/llms.txt", content="\n".join(lignes) + "\n",
        note="Fichier à publier à la racine. Liste dérivée des liens internes réels.",
    )


def meta_description(page: CrawledPage) -> Fix | None:
    if page.meta_description:
        return None
    # On propose un gabarit dérivé du titre — pas une phrase inventée sur le fond.
    base = page.title or _brand_from(page, None)
    contenu = (f'<meta name="description" content="{base[:150]}">')
    return Fix(
        id="add-meta-description", title="Ajouter une meta description",
        kind="meta", target="<head>", content=contenu,
        note="Gabarit dérivé du titre — à réécrire avec une phrase de valeur réelle.",
    )


def proposer(audit: SiteAudit, page: CrawledPage, *,
             name: str = "", legal_name: str = "",
             same_as: list[str] | None = None) -> list[Fix]:
    """
    Sélectionne les correctifs pertinents pour cet audit. On ne propose un fix
    que si le constat correspondant existe : pas de correctif pour un problème
    qui n'a pas été détecté.
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
