# Éditions — ce qui est gratuit, ce qui est payant

Ce document fige la frontière pour que l'architecture ne dérive pas. La règle est
simple et défendable :

> **Gratuit = ce qui coûte 0 € à exécuter. Payant = ce qui appelle des API LLM
> payantes, ou exige un serveur toujours allumé.**

Le client ne paie jamais pour *débloquer* une fonction bridée. Il paie parce
qu'une infrastructure absorbe un coût réel à sa place. Zéro ressentiment.

## Édition Open-Source (MIT, auto-hébergée)

Tout ce qui est **local et déterministe**. Elle doit être excellente en
elle-même : c'est l'acquisition, pas un produit d'appel mutilé.

| Capacité | Commande |
|---|---|
| Audit + Readiness (technique, schéma, citabilité) | `citerank audit` |
| Comparaison concurrentielle (sur Readiness) | `citerank competitors` |
| Génération de correctifs (JSON-LD, llms.txt, meta) | `citerank fix` |
| Rapport HTML autonome et partageable | `citerank report` |
| Instantanés et évolution en local | `citerank monitor` / `compare` |
| Visibilité IA **avec ta propre clé API** | `citerank visibility` |

La visibilité fonctionne en open-source **si l'utilisateur fournit sa clé** : il
paie alors directement son fournisseur. C'est honnête et ça n'ampute rien.

## Édition Hébergée (SaaS, repo privé séparé)

Ce qui est **structurellement impossible** sur un laptop, ou qui **coûte de
l'argent à faire tourner**. Le moteur MIT est importé tel quel — rien n'est
réécrit (principe directeur, point 37).

| Capacité | Pourquoi c'est payant |
|---|---|
| Visibilité IA multi-moteurs clé en main | on absorbe le coût des appels LLM |
| Share of Voice mesuré en continu | idem, à l'échelle et dans le temps |
| Monitoring 24/7 + alertes de régression | exige un serveur toujours allumé |
| Comptes équipe, portails clients marque blanche | multi-tenant, hébergement |
| Tableau de bord historique, PDF à la chaîne | stockage et rendu côté serveur |
| « Analyze » public : coller une URL sur le site | on protège derrière quota/compte |

### Le piège à ne jamais oublier

Un « Analyze » gratuit et public qui lance la visibilité pour chaque inconnu =
une facture LLM qui explose au premier pic de trafic. Sur la version hébergée, la
**Readiness reste l'accroche gratuite** (coût nul), la **Visibilité passe derrière
un compte ou un quota**. La frontière gratuit/payant du produit hébergé est la
même que celle entre les deux éditions : local vs coûteux.

## Licence

- **Moteur** (`citerank/`) : MIT. Adoption maximale, l'acquisition l'exige.
- **Couche SaaS** (dashboard, facturation, multi-tenant) : repo privé, importe le
  moteur. Le moat n'est pas le code — c'est l'infra hébergée et l'absorption des
  coûts API. Pas besoin de licence restrictive pour le protéger.
