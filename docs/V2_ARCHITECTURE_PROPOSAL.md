# Proposition d'architecture V2

## Le constat sur l'amont

`geo-seo-claude` (9,3k étoiles, MIT) est un **skill Claude Code**. Sa logique
d'analyse vit dans une douzaine de fichiers `SKILL.md` qui orchestrent quelques
scripts Python (`fetch_page.py`, `citability_scorer.py`, `brand_scanner.py`).
Conséquences :

- **Le produit EST l'interface.** On ne peut pas en faire une API, un SaaS ou une
  brique Jarvis sans tout réécrire : la valeur est prisonnière du format skill.
- **La citabilité est une règle de comptage** (« 134-167 mots »), érigée en seuil
  universel par le README lui-même.
- **Pas de séparation** entre préparation, visibilité réelle et part de voix : un
  seul « GEO Score » agrège des choses de natures différentes.
- **Pas d'étiquetage** de la nature des données : une déduction et une mesure se
  ressemblent dans le rapport.

## Le principe directeur (cahier des charges, point 37)

> Claude Code doit être **une** interface du moteur, pas le moteur.

```
        ┌─ Skill Claude Code
        ├─ CLI                  ← livré
GEO ────├─ API REST             ← roadmap
ENGINE  ├─ Jarvis
        ├─ SaaS Lamarca
        └─ Client Dashboard
```

L'open-source sur GitHub sert d'acquisition ; la version hébergée devient le SaaS
payant. La frontière gratuit/payant tombe exactement sur la frontière
Readiness/Visibility, qui est aussi la frontière local/coûteux : les trois se
superposent, le modèle économique est donc porté par l'architecture elle-même.

## Arbre livré (Phase 1)

```
citerank/
  models.py          Types (Finding, Score, CrawledPage, SiteAudit, …) — fin des blobs Markdown internes
  crawl.py           Crawl normalisé, partagé, mis en cache + validation anti-SSRF
  engine.py          Orchestrateur — LE point d'entrée du cœur
  scoring            (dans engine + analyzers) multi-score transparent
  analyzers/
    technical.py     robots, sitemap, llms.txt, crawlers IA, HTTPS, balises
    schema_ld.py     JSON-LD, entité vs transactionnel, sameAs
    citability.py    citabilité SÉMANTIQUE (remplace la règle des 150 mots)
  providers/
    base.py          contrat commun ; clés depuis l'environnement uniquement
    openai_provider.py  fonctionnel (compatible OpenRouter via base_url)
    mock.py          déterministe, hors ligne, pour tests et démos
  visibility.py      consensus multi-fournisseurs + confiance explicite
  report.py          md / json, chaque donnée étiquetée par sa nature
  cli.py             peau CLI (aucune logique métier)
```

## Matrice EXISTANT / AMÉLIORÉ / NOUVEAU

| Capacité | Amont | CiteRank |
|---|---|---|
| Audit technique | ✅ skill | ✅ **moteur typé** |
| Analyse de schéma | ✅ | ✅ entité vs transactionnel, sameAs |
| Citabilité | règle 150 mots | 🔁 **signaux sémantiques** |
| Crawl partagé | ❌ (refetch) | 🆕 crawl unique mis en cache |
| Anti-SSRF | ❌ | 🆕 validation d'URL à l'entrée |
| Readiness vs Visibility | ❌ mélangés | 🆕 **séparés** |
| Visibilité réelle (LLM) | partielle | 🆕 consensus + confiance |
| Étiquetage mesuré/déduit | ❌ | 🆕 partout |
| Moteur indépendant | ❌ | 🆕 **cœur réutilisable** |
| Share of Voice | ❌ | ⏳ roadmap |
| Remédiation `/geo fix` | ❌ | ⏳ roadmap |
| Monitoring historique | ❌ | ⏳ roadmap |
| Rapport PDF | ✅ | ⏳ roadmap |

## Feuille de route

1. ✅ **Phase 1** — moteur + Readiness locale + Visibility OpenAI + rapports + tests.
2. Share of Voice + intelligence concurrentielle (`/geo competitors`).
3. Générateur d'univers de requêtes déterministe (comparaisons mensuelles).
4. Entity Intelligence (graphe d'entité, sameAs, sources externes).
5. Remédiation (`/geo fix`) : diffs proposés, jamais de faits fabriqués.
6. Monitoring + `/geo compare` (7 / 30 / 90 jours, détection de régressions).
7. Adaptateurs Gemini, Perplexity, Anthropic.
8. Rapport PDF « livrable de conseil » + mode marque blanche agence.
9. Couche API REST → dashboard → SaaS, sans toucher au moteur.
