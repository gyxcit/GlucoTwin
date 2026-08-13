# 🩺 GlucoTwin

**Jumeau numérique du patient diabétique de type 2** — de l'emploi du temps à la glycémie, en passant par un **état métabolique interprétable**.

> **Avertissement.** Prototype de recherche et d'enseignement. Ce n'est **ni un dispositif médical, ni un outil de diagnostic, ni un CGM**. Il ne recommande aucun traitement ni aucune dose d'insuline.

---

## La thèse

> À 30 minutes, la prévision glycémique est un problème **saturé** : la persistance — « la glycémie ne bougera pas » — est quasi imbattable. La question utile n'est donc pas *« quel modèle a la plus petite erreur »*, mais **où** la prévision a une valeur clinique réelle, et **sait-on quand elle est fiable ?**

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
git clone https://github.com/<votre-compte>/GlucoTwin.git
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

| Horizon | MAE modèle | MAE persistance | Gain | p |
|---:|---:|---:|---:|---:|
| 30 min | 6,57 | 7,31 | **+0,74** | 1,2e-02 |
| 60 min | 9,60 | 11,12 | **+1,52** | 2,8e-03 |
| 90 min | 10,95 | 13,63 | **+2,68** | 8,7e-04 |
| 120 min | 11,20 | 15,35 | **+4,14** | 4,4e-06 |

**Le résultat le plus intéressant est une contradiction.** Pendant que le gain en MAE *monte* avec l'horizon, la **sensibilité de détection des hyperglycémies s'effondre** (28 % → 10 %). La cause est mesurée : l'écart-type des prédictions tombe à 0,77 fois celui des vraies valeurs — c'est de la **régression vers la moyenne**. Le modèle devient meilleur « en moyenne » et plus mauvais « quand ça compte ».

> ⚠️ **Ces chiffres valident le logiciel, pas la science.** La cohorte est **entièrement simulée** : aucun patient réel n'a été utilisé. Ils prouvent que la chaîne et le protocole fonctionnent. Les conclusions physiologiques exigent CGMacros.

---

## Méthodologie d'évaluation

Trois règles, tenues par construction dans `glucotwin/layer2/evaluation.py` :

1. **Aucune fuite entre patients** — *leave-one-patient-out* : chaque patient est testé sans jamais avoir été vu à l'entraînement.
2. **Toujours comparé à la persistance** — un modèle qui ne bat pas « rien ne bouge » n'apporte rien, quel que soit son RMSE.
3. **Toujours avec une incertitude** — intervalles par **prédiction conforme**, sans hypothèse sur la distribution des erreurs.

S'y ajoutent des métriques **cliniques** : erreur par zone glycémique et sensibilité de détection des événements — parce qu'une MAE excellente peut coexister avec une incapacité totale à annoncer une hypoglycémie.

**Limite connue et assumée :** la couverture conforme observée (≈ 87 %) est légèrement sous la cible (90 %). La garantie suppose des données échangeables, or on calibre sur certains patients et on teste sur un patient jamais vu. Piste : *Mondrian conformal* ou calibration sur les premiers jours du patient lui-même.

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
demo/        application web autonome — la démo de 15 minutes
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
