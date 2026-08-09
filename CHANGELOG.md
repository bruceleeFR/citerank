# Journal des versions

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).

## [Non publié]

### Ajouté
- Adaptateur fournisseur **Anthropic** — le consensus de visibilité repose
  désormais sur deux moteurs réels (OpenAI + Anthropic), pas un seul.
- `docs/EDITIONS.md` : frontière figée entre l'édition open-source et l'édition
  hébergée.
- `SECURITY.md`, `CONTRIBUTING.md`, intégration continue GitHub Actions.

## [0.1.0]

Première fondation — refonte indépendante inspirée de `geo-seo-claude` (MIT).

### Ajouté
- **Moteur Python découplé de l'interface** : CLI, skill, API et SaaS ne sont que
  des peaux sur `citerank/`.
- **Readiness** locale et déterministe : technique (robots, sitemap, llms.txt,
  crawlers IA, transport, balises), données structurées (entité vs
  transactionnel, sameAs), citabilité **sémantique** (remplace la règle
  « 134-167 mots » de l'amont).
- **Intelligence concurrentielle** : comparaison de Readiness et explication
  « pourquoi ils passent devant », adossée aux seuls écarts mesurés.
- **Share of Voice** entre marques, par consensus de fournisseurs.
- **Remédiation** (`fix`) : génère JSON-LD, llms.txt, meta — sans jamais fabriquer
  de fait.
- **Rapport HTML** autonome et partageable, thème clair/sombre, marque blanche.
- **Monitoring** : mode projet `.geo/`, instantanés datés, `compare` avec
  détection de régression.
- Étiquetage systématique de la nature des données (mesuré / observé / déduit /
  recommandé). Validation d'URL anti-SSRF. 10 tests hors réseau.
