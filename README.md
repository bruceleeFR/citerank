# CiteRank

**Intelligence AI-Search open-source.** Mesurez, comprenez et améliorez la façon
dont une marque apparaît dans les réponses de ChatGPT, Gemini, Perplexity et
Claude — pas seulement dans Google.

CiteRank répond à quatre questions que les outils SEO classiques ne posent pas :

1. **Les moteurs IA comprennent-ils ce site ?** → score de *Readiness*
2. **Les moteurs IA mentionnent-ils cette marque ?** → score de *Visibilité*
3. **Pourquoi un concurrent est-il cité à sa place ?** → *intelligence concurrentielle*
4. **Que changer exactement ?** → *remédiation*

## Ce qui le distingue

- **Un vrai moteur, pas un paquet de fichiers Markdown.** Toute la logique vit
  dans un package Python (`citerank/`), indépendant de l'interface. La CLI, le
  skill Claude Code, une future API REST et un SaaS ne sont que des peaux sur ce
  cœur. C'est ce qui permet de passer d'un outil de terminal à un produit hébergé
  sans réécrire l'analyse.
- **Readiness ≠ Visibilité.** Un site parfaitement préparé n'est pas forcément
  cité. On ne confond jamais les deux, dans les scores comme dans les rapports.
- **La couche gratuite est locale.** L'audit de Readiness ne fait aucun appel LLM :
  déterministe, sans clé, illimité. La Visibilité (qui coûte de vrais appels
  d'API) est une couche séparée.
- **Honnêteté comme argument.** Chaque donnée est étiquetée *mesuré*, *observé*,
  *déduit* ou *recommandé*. La citabilité repose sur des signaux sémantiques, pas
  sur une règle « 134-167 mots ».

## Installation

```bash
git clone <repo> && cd citerank
pip install -e .
citerank doctor
```

Dépendances minimales : `aiohttp`, `beautifulsoup4`. Python 3.10+.

## Premier audit (gratuit, hors ligne)

```bash
citerank audit https://votresite.fr
```

```
  CiteRank · votresite.fr
  ──────────────────────────────────────────────
  Score global IA-Search : 50/100

  Préparation IA (Readiness)   ██████████··········  54  [MESURÉ]
  SEO technique                ████████████████████ 100  [MESURÉ]
  Données structurées          ████················  20  [MESURÉ]
  Citabilité                   ██··················  14  [DÉDUIT]

  1 problème(s) prioritaire(s) :
    🟠 Schéma Organization absent
```

Rapport détaillé : `citerank audit <url> --md rapport.md`
Sortie machine : `citerank audit <url> --json`

## Mesurer la visibilité réelle (nécessite une clé)

```bash
export OPENAI_API_KEY=sk-...
citerank visibility https://votresite.fr --brand "Votre Marque" --runs 3
```

Sans clé, `--mock` démontre le parcours hors ligne (résultats explicitement
étiquetés factices).

## Architecture

```
        ┌─ Skill Claude Code ─┐
        ├─ CLI ───────────────┤
        ├─ API REST (à venir) ─┤──► citerank/ (MOTEUR)
        ├─ SaaS ──────────────┤        ├─ crawl.py     (crawl normalisé + anti-SSRF)
        └─ Jarvis ────────────┘        ├─ analyzers/   (technique, schéma, citabilité)
                                       ├─ providers/   (OpenAI, … adaptateurs)
                                       ├─ visibility.py (consensus multi-moteurs)
                                       ├─ scoring       (multi-score transparent)
                                       └─ report.py     (md / json)
```

Le moteur ne dépend d'aucune interface. C'est le principe directeur.

## État

Phase 1 livrée : moteur, Readiness locale complète (technique, données
structurées, citabilité sémantique), abstraction de fournisseurs, Visibilité
fonctionnelle via OpenAI, rapports Markdown/JSON, tests hors réseau.

Feuille de route : Share of Voice, intelligence concurrentielle, moteur de
remédiation (`/geo fix`), monitoring historique, rapport PDF, adaptateurs Gemini
et Perplexity. Voir `docs/V2_ARCHITECTURE_PROPOSAL.md`.

## Licence

MIT. Inspiré de [geo-seo-claude](https://github.com/zubair-trabzada/geo-seo-claude) ;
voir `NOTICE.md` pour l'attribution.
