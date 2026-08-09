# Attribution

CiteRank s'inspire de **[geo-seo-claude](https://github.com/zubair-trabzada/geo-seo-claude)**
de zubair-trabzada, publié sous licence MIT.

## Ce qui est repris et ce qui ne l'est pas

CiteRank est une **réécriture**, pas un fork. Aucun fichier du projet amont n'a
été copié tel quel. Ce qui est hérité, ce sont des **idées** — la notion d'audit
GEO, la palette de commandes (`audit`, `citability`, `schema`, `crawlers`,
`llmstxt`…), l'orientation « visibilité IA plutôt que Google ».

Ce qui est **nouveau et différent** :

- un **moteur Python indépendant** de toute interface, là où l'amont fait vivre
  sa logique dans des skills Markdown de Claude Code (le CLI, le skill, une API
  et un SaaS ne sont ici que des peaux sur le même cœur) ;
- la **séparation stricte** entre préparation (Readiness), visibilité réelle
  (Visibility) et part de voix (Share of Voice) — l'amont mélange les trois ;
- une **citabilité sémantique** en remplacement de la règle « 134-167 mots » du
  projet d'origine, que son propre README érige en seuil universel ;
- l'**étiquetage de la nature** de chaque donnée (mesuré / observé / déduit /
  recommandé), pour ne jamais présenter une déduction comme un fait ;
- la **validation d'URL anti-SSRF** dès l'entrée du crawl.

Conformément à la licence MIT, la notice de copyright amont est conservée dans
le fichier `LICENSE`. CiteRank ne prétend pas être l'auteur original de l'idée
d'outil GEO pour Claude Code.
