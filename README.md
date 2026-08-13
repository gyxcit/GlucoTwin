# 🩺 GlucoTwin

**Jumeau numérique du patient diabétique de type 2** — de l'emploi du temps à la glycémie, en passant par un **état métabolique interprétable**.

> **Avertissement.** Prototype de recherche et d'enseignement. Ce n'est **ni un dispositif médical, ni un outil de diagnostic, ni un CGM**. Il ne recommande aucun traitement ni aucune dose d'insuline.

---

## La thèse

> À 30 minutes, la prévision glycémique est un problème **saturé** : sur données réelles, la persistance — « la glycémie ne bougera pas » — est quasi imbattable (13,39 mg/dL contre 13,11 pour un modèle entraîné, benchmark CGMacros). La question utile n'est donc pas *« quel modèle a la plus petite erreur »*, mais **où** la prévision a une valeur clinique réelle, et **sait-on quand elle est fiable ?**

Ce dépôt répond en mesurant trois choses que la MAE seule ne montre pas : l'effet de l'**horizon**, la capacité à **détecter les événements**, et la **fiabilité annoncée** des prédictions.

---

## Ce qui distingue ce projet

La plupart des jumeaux numériques vont directement des données à la glycémie, avec une boîte noire au milieu. Ici, on force le passage par un **goulot d'étranglement physiologiquement interprétable** — l'idée des *Concept Bottleneck Models* (Koh et al., ICML 2020), appliquée pour la première fois à notre connaissance à la glycémie.

```text
emploi du temps ──► ÉTAT MÉTABOLIQUE ──► glycémie prévue ──► états de risque
                    (14 concepts lisibles,
                     corrigeables, traçables)
```

Concrètement, le système ne dit pas « la variable 7 pesait 0,3 » mais **« votre séance de 45 min a consommé environ 38 g de glucides, d'où la baisse prévue »**.

---

## Architecture

| Couche | Rôle | Apprise ? | État |
|---|---|---|---|
| **0** — Emploi du temps | Repas, activités, sommeil, contexte | non | ✅ validé |
| **1** — Concepts métaboliques | Physiologie : METs, Frayn, absorption, circadien, phénomène de l'aube | **non** — équations | ✅ validé |
| **2** — Prévision glycémique | Concepts + historique → glycémie à H minutes | **oui** | ✅ logiciel validé · ⏳ données réelles |
| **3** — États et risques | Chiffres → probabilités calibrées | calibration | ⏳ à faire |
| **4** — Recommandations | LLM conditionné, catalogue fermé + validateur | non | ⏳ à faire |

La couche 1 n'apprend rien : c'est de la physiologie publiée. C'est ce qui la rend **vérifiable sans données**.

---

## Installation

```bash
git clone https://github.com/gyxcit/GlucoTwin.git
cd GlucoTwin
python -m venv .venv && source .venv/bin/activate    # Windows : .venv\Scripts\activate
pip install -e ".[dev]"
```

## Démarrage rapide

```bash
# Une journée du jumeau : emploi du temps → 14 concepts métaboliques
python -c "from glucotwin.day_concepts import *; import glucotwin.day_concepts as m; print(m.__doc__)"

# L'incertitude sur la partition glucides/lipides (le VCO₂ n'est jamais mesuré)
python scripts/sensitivity.py

# Une expérience de prévision, évaluée honnêtement
python scripts/run_layer2.py --patients 30 --days 6 --horizons 30 60 90 120 --models hgb

# Les tests
pytest -q
```

---

## Résultats

Sur cohorte **synthétique** (45 patients virtuels), horizon variable, modèle *HistGradientBoosting*, évaluation *leave-one-patient-out* :

| Horizon | MAE modèle | MAE persistance | Gain | p | Patients gagnés |
|---:|---:|---:|---:|---:|---:|
| 30 min | 6,25 | 8,30 | **+2,06** | 8,0e-09 | 40/45 |
| 60 min | 10,13 | 12,96 | **+2,83** | 7,3e-08 | 39/45 |
| 90 min | 11,85 | 16,04 | **+4,19** | 9,0e-09 | 39/45 |
| 120 min | 12,51 | 18,23 | **+5,72** | 1,7e-11 | 42/45 |

L'avantage **triple** entre 30 et 120 minutes, et l'ablation des concepts est monotone :
19,00 mg/dL avec l'historique glycémique seul → 13,81 en ajoutant les repas → 12,84 avec
l'activité → **12,51** avec les modulateurs, soit **−34 %**.

**Le résultat le plus intéressant est une contradiction.** Pendant que le gain en MAE *triple* avec l'horizon, la **sensibilité de détection des hyperglycémies s'effondre** : 44,6 % → 11,4 % → 3,8 % → **1,7 %**. La cause est mesurée : l'écart-type des prédictions tombe de 0,87 à 0,69 fois celui des vraies valeurs — c'est de la **régression vers la moyenne**. Le modèle devient meilleur « en moyenne » et quasiment aveugle « quand ça compte ».

À 120 minutes, il gagne 5,72 mg/dL sur la persistance **et ne détecte plus que 1,7 % des hyperglycémies**. Optimiser la MAE ne rend pas un jumeau cliniquement utile.

> ⚠️ **Ces chiffres valident le logiciel, pas la science.** La cohorte est **entièrement simulée** : aucun patient réel n'a été utilisé.
>
> En particulier, la glycémie synthétique est engendrée à partir des concepts que le modèle reçoit : la tâche est **plus facile qu'en réalité**, surtout à court horizon. Sur les vraies données de CGMacros, un modèle comparable obtient 13,11 mg/dL contre 13,39 pour la persistance à 30 min — quasiment ex æquo. **Ce qui se transférera aux données réelles, c'est la pente, pas les valeurs.**

### Démonstration

L'atelier [`demo/atelier.html`](demo/atelier.html) est un **fichier autonome** :
on compose la journée sur une timeline, et le jumeau réagit en direct.

- timeline 00h00 → 23h59 : cliquer pour poser un repas ou une activité choisie
  parmi les **78 du catalogue** (recherche, filtres, badge MET) ;
- une carte patient dont le **personnage exécute le geste de l'activité en
  cours** — 20 gestes avec leurs accessoires, cadence indexée sur les METs ;
- des **arêtes pondérées**, à la manière d'un schéma de réseau, qui portent les
  flux métaboliques vers les graphes ;
- lecture de la journée à **×0,5 → ×8**, journée de référence figeable,
  comparateur d'interventions.

Voir [`demo/DEPLOIEMENT.md`](demo/DEPLOIEMENT.md) pour le mode d'emploi et la
mise en ligne.

### Présentation

Le support de soutenance (12 slides, anglais, avec le script complet en notes du
présentateur) est dans [`docs/GlucoTwin_presentation.pptx`](docs/GlucoTwin_presentation.pptx).
Il se régénère avec `node scripts/build_deck.js` depuis `docs/figures/`.

### Figures

Les figures du dernier run complet sont dans [`docs/figures/`](docs/figures/) :

| Figure | Ce qu'elle montre |
|---|---|
| `02_horizons.png` | **la figure centrale** — l'écart se creuse, avec la dispersion patient par patient |
| `03_ablation.png` | l'apport de chaque groupe de concepts |
| `04_importance.png` | ce sur quoi le modèle s'appuie vraiment |
| `05_mae_vs_clinical.png` | **la contradiction** — MAE et clinique disent l'inverse |
| `07_conforme.png` | la couverture des intervalles |

---

## Méthodologie d'évaluation

Trois règles, tenues par construction dans `glucotwin/layer2/evaluation.py` :

1. **Aucune fuite entre patients** — *leave-one-patient-out* : chaque patient est testé sans jamais avoir été vu à l'entraînement.
2. **Toujours comparé à la persistance** — un modèle qui ne bat pas « rien ne bouge » n'apporte rien, quel que soit son RMSE.
3. **Toujours avec une incertitude** — intervalles par **prédiction conforme**, sans hypothèse sur la distribution des erreurs.

S'y ajoutent des métriques **cliniques** : erreur par zone glycémique et sensibilité de détection des événements — parce qu'une MAE excellente peut coexister avec une incapacité totale à annoncer une hypoglycémie.

**Sur la couverture conforme :** avec 45 patients, la couverture observée est de **89,2 à 89,8 % pour 90 % visés** — la garantie tient. Elle se dégradait à 84–88 % sur de petits échantillons (une dizaine de patients), la calibration inter-patients n'étant alors pas assez fournie. À surveiller sur données réelles, où le décalage entre patients est plus marqué ; piste en réserve : *Mondrian conformal* ou calibration sur les premiers jours du patient lui-même.

---

## Le point méthodologique central : le VCO₂

Les équations de Frayn exigent VO₂ **et** VCO₂. Or le VCO₂ n'est mesurable qu'en laboratoire : aucun objet connecté ne le mesure. Le moteur l'**infère** depuis l'intensité de l'effort.

Analyse de sensibilité (`scripts/sensitivity.py`), erreur de ±0,05 sur le quotient respiratoire :

- 🟢 **l'énergie est robuste** — ±3 %
- 🔴 **la partition glucides/lipides est fragile** — ±22 à 31 %

D'où l'affichage systématique d'un **intervalle** plutôt que d'un faux chiffre précis. Et d'où la piste de recherche : **inverser le problème** en calibrant le modèle par patient sur la réponse glycémique observée — on n'a pas besoin de mesurer le mécanisme si on observe son effet.

---

## Structure

```text
src/glucotwin/
├── metabolic_engine.py     activité → VO₂ → Frayn → glucides/lipides oxydés
├── day_concepts.py         couches 0-1 : emploi du temps → 14 concepts
├── met_activities.csv      catalogue de 78 activités (METs)
└── layer2/
    ├── cohort.py           cohorte virtuelle non circulaire
    ├── features.py         concepts + historique → features, cibles multi-horizons
    ├── models.py           modèles comparés
    └── evaluation.py       LOPO · persistance · conforme · métriques cliniques

scripts/     expériences en ligne de commande
notebooks/   entraînement (Kaggle)
demo/        applications web autonomes — atelier.html = la démo
docs/        revue de littérature, état de l'art, architecture, plans
tests/       25 tests
```

---

## Données

Ce dépôt **ne redistribue aucune donnée patient**.

- **Cohorte synthétique** — générée par `glucotwin.layer2.cohort`, pour valider le logiciel.
- **CGMacros v1.0.0** (PhysioNet, `10.13026/3z8q-x658`) — 45 participants réels. Licence **CC BY-NC-SA 4.0**, à télécharger séparément. Voir [`NOTICE.md`](NOTICE.md).

---

## Feuille de route

- [x] Moteur métabolique interprétable (couches 0-1) — 40 vérifications
- [x] Incertitude sur la partition des substrats
- [x] Phénomène de l'aube, réglable par patient
- [x] Harnais d'évaluation LOPO + persistance + conforme
- [x] Métriques cliniques par zone et détection d'événements
- [x] Application web de démonstration
- [ ] **Adaptateur CGMacros** — prochain jalon
- [ ] Calibration de la couche 1 par patient (problème inverse)
- [ ] Couche 3 : probabilités calibrées de risque
- [ ] Couche 4 : recommandations avec catalogue fermé et validateur
- [ ] Analyse d'équité par sous-groupes
- [ ] Validation externe sur un second jeu de données

---

## Équipe

Regis Likassi · Hakim Djomo · Jean Direl Nze · Xavier Ondo · Seth Ndinga

*AI for Health (PGE5) — Prof. Anuradha Kar*

## Licence

Code : **MIT** (voir [`LICENSE`](LICENSE)). Attributions et licences tierces : [`NOTICE.md`](NOTICE.md).
