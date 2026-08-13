# GlucoTwin — la démo

Application web **autonome** : un seul fichier `index.html`, aucune dépendance, aucune installation. Elle fonctionne hors-ligne — c'est votre garantie anti-plantage le jour de la présentation.

## Lancer

Double-cliquez sur `index.html`. C'est tout.

## Déployer une URL publique (2 min)

**Netlify Drop** — https://app.netlify.com/drop → glissez `index.html` → URL immédiate.
**Vercel** — https://vercel.com → Add New › Project → importez le dossier.
**GitHub Pages** — Settings › Pages › branche `main`, dossier `/demo`.

## Ce que la démo montre

L'application affiche **les quatre couches de l'architecture** à l'écran :

| Couche | Ce qu'on voit |
|---|---|
| **0** — Emploi du temps | patient, repas (heure, glucides, fibres, IG), activités choisies dans un catalogue de 78 |
| **1** — État métabolique | 8 concepts physiologiques mis à jour **au survol de la courbe** |
| **2** — Glycémie prédite | 24 h au pas de 5 min, zone cible, bandes sommeil et activité |
| **3** — États de risque | probabilités, tendance, et une explication **traçable** jusqu'au mécanisme |

Plus un **comparateur d'interventions** qui simule six journées alternatives et les classe par effet sur le pic glycémique.

## Le moment fort de la présentation

Le comparateur. Il produit un classement mesuré :

| Intervention | Effet sur le pic |
|---|---:|
| Réduire les glucides de 40 % | −46 mg/dL |
| Passer tous les repas en IG bas | −43 mg/dL |
| Marche de 30 min après chaque repas | −16 mg/dL |
| 45 min de vélo en fin de journée | −14 mg/dL |
| Avancer le dernier repas de 3 h | −4 mg/dL |
| Dormir une heure de plus | 0 mg/dL |

C'est ce qu'un jumeau numérique permet et qu'une simple mesure ne permet pas : **comparer des futurs qui n'ont pas eu lieu**. Et le résultat est honnête — il contredit l'idée reçue selon laquelle l'heure du repas pèserait autant que sa composition.

## Fondements physiologiques

Le moteur est un **port fidèle en JavaScript** des couches 0-1 Python (`glucotwin.day_concepts`), donc cohérent avec le code scientifique du dépôt :

- valeurs MET du **2024 Adult Compendium** (78 activités)
- oxydation des substrats par les **équations de Frayn (1983)**
- cinétique d'absorption gamma, modulée par l'index glycémique et les fibres
- **rythme circadien** de la sensibilité à l'insuline — un même repas de 65 g fait **+65 mg/dL à 8h contre +87 mg/dL à 22h**
- **phénomène de l'aube** réglable, ~+19 mg/dL avant le réveil à intensité 1
- production hépatique freinée par l'insuline, stimulée à l'effort et à l'aube

## Limite à énoncer

Modèle physiologique **simplifié, non validé cliniquement**, à visée pédagogique. Il ne recommande aucune dose ni traitement. Pour la version scientifique, la couche 2 est apprise sur données réelles (voir `notebooks/`).
