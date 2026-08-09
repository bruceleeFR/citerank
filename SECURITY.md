# Sécurité

## Surface et garde-fous

CiteRank va chercher des URL fournies par l'utilisateur. Deux risques sont traités
à la racine :

- **SSRF.** Toute URL est validée avant le moindre octet réseau
  (`citerank/crawl.py`). Sont refusés par défaut : `localhost`, les plages
  privées (RFC 1918), le lien-local — dont le point de métadonnées cloud
  `169.254.169.254` — ainsi que les schémas autres que `http`/`https`. Le
  déblocage local n'est possible qu'avec le drapeau explicite `--allow-local`.
- **Fuite de secrets.** Les clés d'API ne viennent que de l'environnement, jamais
  du code ni des journaux. Les rapports n'incluent aucun secret. Le fournisseur
  factice ne parle à aucun réseau.

## Ce que CiteRank envoie où

- L'audit de **Readiness** est 100 % local : il ne contacte que le site analysé.
- La **Visibilité** envoie les *requêtes de test* aux fournisseurs IA configurés
  (OpenAI, Anthropic…). Elle n'envoie **pas** le code source du site.
- Chaque fournisseur se désactive en retirant sa clé de l'environnement.

## Signaler une faille

Ouvrez une *issue* privée (Security advisory) plutôt qu'un ticket public. Décrivez
la reproduction. Nous répondons avant divulgation.
