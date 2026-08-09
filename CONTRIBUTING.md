# Contribuer

Merci de l'intérêt. Quelques principes qui font l'identité du projet — les
respecter, c'est garder ce qui rend CiteRank crédible.

## Les règles non négociables

1. **Ne jamais présenter une déduction comme une mesure.** Toute donnée porte sa
   nature (`Nature` dans `models.py`). Une heuristique est `INFERRED`, pas
   `MEASURED`.
2. **Ne jamais fabriquer un fait.** La remédiation ne remplit que des champs
   dérivés du site ou fournis par l'utilisateur. Pas de faux avis, adresse,
   chiffre, profil.
3. **Le moteur reste indépendant de l'interface.** Aucune logique métier dans la
   CLI ou dans un futur skill : elle vit dans `citerank/`.
4. **Pas de secret dans le code ni les journaux.** Les clés viennent de
   l'environnement.

## Développement

```bash
pip install -e ".[dev]"
python tests/test_core.py     # tests hors réseau, aucun service requis
ruff check citerank           # style
```

Les tests unitaires ne doivent dépendre d'aucun réseau : simulez le crawl avec une
`CrawledPage` et les fournisseurs avec `MockProvider`.

## Ajouter un fournisseur IA

Implémentez `providers/base.Provider`, lisez la clé depuis l'environnement, ne
levez jamais d'exception (retournez un `ProviderResult` vide en cas d'erreur), et
enregistrez la classe dans `providers/__init__.py`.
