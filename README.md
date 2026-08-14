# 🩺 GlucoTwin

**Jumeau numérique du patient diabétique de type 2** — de l'emploi du temps à la glycémie, en passant par un **état métabolique interprétable**.

> **Avertissement.** Prototype de recherche et d'enseignement. Ce n'est **ni un dispositif médical, ni un outil de diagnostic, ni un CGM**. Il ne recommande aucun traitement ni aucune dose d'insuline.

---

## La thèse

> À 30 minutes, la prévision glycémique est un problème **saturé** : sur les 45
> participants réels de CGMacros, la persistance — « la glycémie ne bougera pas »
> — atteint 13,41 mg/dL, et un modèle entraîné 12,33. La question utile n'est
> donc pas *« quel modèle a la plus petite erreur »*, mais **où** la prévision a
> une valeur clinique réelle, **pour qui**, et **sait-on quand elle est fiable ?**

Ce dépôt répond en mesurant quatre choses que la MAE seule ne montre pas :
l'effet de l'**horizon**, la capacité à **détecter les événements**, la
**fiabilité annoncée** des prédictions, et l'**équité** entre sous-groupes.

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
| **3** — États et risques | Chiffres → probabilités calibrées | calibration | ✅ validé sur données réelles |
| **4** — Recommandations | LLM conditionné, catalogue fermé + validateur | non | ✅ validé (34 tests adverses) |

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

# Une expérience sur données réelles (après téléchargement de CGMacros)
python scripts/inspect_cgmacros.py data/CGMacros          # 7 contrôles de recevabilité
python scripts/run_cgmacros.py data/CGMacros --horizons 30 60 90 120
python scripts/run_ablation.py data/CGMacros                # la couche 1 sert-elle ?
python scripts/run_calibration.py --cgmacros data/CGMacros  # le probleme inverse

# La même chose sur cohorte synthétique, sans aucune donnée à télécharger
python scripts/run_layer2.py --patients 30 --days 6 --horizons 30 60 90 120 --models hgb

# Les tests
pytest -q
```

---

## Résultats

Sur les **45 participants réels** de CGMacros (Dexcom G6 Pro, 395 journées,
114 155 pas de 5 min), évaluation *leave-one-patient-out*, modèle
*HistGradientBoosting* :

| Horizon | MAE modèle | MAE persistance | Gain | p | Patients gagnés | Couverture |
|---:|---:|---:|---:|---:|---:|---:|
| 30 min | **12,33** | 13,41 | **+1,08** | 1,3e-04 | 34/45 | 89,8 % |
| 60 min | 20,66 | 19,97 | −0,69 | 0,55 | 25/45 | 89,4 % |
| 90 min | 25,32 | 24,51 | −0,81 | 0,37 | 25/45 | 88,9 % |
| 120 min | 28,73 | 28,01 | −0,72 | 0,15 | 28/45 | 88,5 % |

**Le pipeline est validé contre une référence externe.** La persistance ne
dépend d'aucun modèle : c'est une propriété des données seules. Nos 13,41 mg/dL
tombent à **0,02 mg/dL** du repère publié sur CGMacros (13,39). Le modèle de
référence publié fait 13,11 ; le nôtre 12,33.

### Cinq résultats qui contredisent l'intuition

**1. Le gain disparaît au-delà de 30 minutes.** Sur cohorte synthétique il
*triplait* avec l'horizon (+2,06 → +5,72 mg/dL). Sur données réelles il devient
négatif et non significatif dès 60 min. Une version antérieure de ce README
annonçait que « la pente se transférera » — **elle s'inverse**. La cohorte
simulée engendrait la glycémie à partir des concepts fournis au modèle, ce qui
rendait la tâche d'autant plus facile que l'horizon s'allongeait.

**2. L'hypoglycémie n'est jamais détectée.** 223 événements réels, sensibilité
**0 %** à tous les horizons. L'erreur par zone dit la même chose : 9,85 mg/dL en
zone normale contre 37,8 en hypoglycémie et jusqu'à 108 en zone très élevée à
120 min. Une MAE globale de 12,33 masque entièrement cette structure.

**3. La performance n'est pas la même pour tous.** À 60 min, l'écart entre
groupes atteint 7,42 mg/dL (**p = 0,019**, test de permutation) — et le signe du
gain s'inverse : le modèle aide les diabétiques (+0,06) et **dégrade** les sujets
sains (−2,89). Chez un sujet sain la glycémie bouge peu, donc la persistance est
quasi parfaite et tout modèle ajoute du bruit.

**4. Mais reformuler en probabilité récupère une partie de ce que le seuillage
détruit.** À 30 min, la prévision ponctuelle ne franchit *jamais* le seuil de
70 mg/dL — sensibilité nulle — alors que la probabilité issue du **même modèle**
classe les hypoglycémies avec une AUROC de 0,752 et une précision moyenne
**20 fois supérieure au hasard**. Pour l'hyperglycémie, la probabilité bat la
climatologie à *tous* les horizons, jusqu'à deux heures. La limite est nette :
au-delà de 30 min, l'hypoglycémie redevient impossible à classer (AUROC 0,53).

**5. L'architecture apporte — mais une seule de ses branches.** L'ablation sur
données réelles (celle du dépôt était circulaire : sur cohorte simulée, la
glycémie est engendrée *à partir* des concepts) montre que la couche 1 bat
l'historique glycémique seul à tous les horizons, avec un gain qui croît de
+0,75 à +1,92 mg/dL (p<0,001). Mais le découpage par groupe est sans appel : les
**repas portent 91 à 99 % du gain**, l'activité n'atteint le seuil qu'à 120 min,
et les modulateurs — circadien, sensibilité insulinique, phénomène de l'aube,
production hépatique — **n'apportent rien de mesurable**. Le goulot conceptuel se
justifie par ce qu'il rend explicable et simulable ; vendre les quatorze concepts
comme également utiles serait faux.

**La prédiction conforme, elle, tient** : couverture de 88,5 à 89,8 % pour 90 %
visés, sur données réelles et sur les quatre horizons.

> **Analyse complète :** [`docs/07_resultats_reels.md`](docs/07_resultats_reels.md).
> **Sorties brutes des runs :** [`results/`](results/) — chaque chiffre cité est
> régénérable par un script du dépôt, avec commande, commit et versions de
> bibliothèques en en-tête de journal.

### Recommandations : le LLM est enfermé, pas encadré

La couche 4 ne demande pas à un modèle de langage d'être prudent — elle lui
retire les moyens de ne pas l'être. Il ne choisit que dans un **catalogue fermé**
de sept interventions non médicamenteuses, et tout ce qu'il produit passe par un
**validateur déterministe** qui peut le rejeter en bloc : identifiant inventé,
intervention contre-indiquée dans l'état courant, vocabulaire médical, forme
invalide. En cas d'échec, sa sortie n'est pas corrigée, elle est **jetée** — on
retombe sur le classement déterministe du catalogue.

Trois états déclenchent un **refus pur**, quelle que soit la qualité de la
sortie : glycémie basse, chute rapide, ou risque d'hypoglycémie annoncé. Le
système répond alors qu'il ne conseille pas.

La propriété est testée, pas espérée : **pour tout état, l'ensemble des
interventions affichables est le même avec ou sans LLM**. Le modèle réordonne et
rédige ; il ne peut jamais élargir. Trente-quatre tests l'attaquent — identifiants
inventés, exercice conseillé à un patient qui descend, « ajustez votre insuline »
glissé dans une phrase anodine, JSON malformé, API en panne.

L'appel réel se fait avec `python scripts/run_reco.py --llm`, qui lit
`MISTRAL_API_KEY` dans l'environnement. Sans clé, la couche fonctionne
entièrement — c'est même son mode de référence.

### Personnalisation : le problème inverse

Le VCO₂ n'est pas mesurable ; la glycémie l'est. On ajuste donc cinq paramètres
physiologiques par patient sur ses **3 premières journées**, et on teste sur les
suivantes :

| | RMSE sur journées de test |
|---|---:|
| **calibré par patient** | **27,33 mg/dL** |
| paramètres de population | 39,97 |
| persistance | 35,95 |

Gain **+12,64 mg/dL** [IC95 +8,3, +17,0], p = 1,1e-09, 40 patients sur 44. Et un
facteur **dix** sur la sensibilité à la charge glucidique entre le 10ᵉ et le 90ᵉ
centile : *le patient moyen n'existe pas*.

Le modèle à cinq paramètres généralisait mais ne s'identifiait pas : 61 % des
patients avaient un gain collé à une borne. **Reparamétré à quatre paramètres**
— bilan basal absorbé dans la glycémie d'équilibre — il garde la même précision
(27,31 contre 27,33) et fait passer la proportion de patients sans aucun
paramètre saturé de **11 % à 57 %**.

Et il devient **falsifiable** : la glycémie d'équilibre ajustée corrèle à
**r = 0,82** (p = 1,3e-11) avec la **glycémie à jeun mesurée au laboratoire**,
que la calibration n'a jamais vue — contre r = 0,30 pour la version à cinq
paramètres. Le paramètre n'absorbe pas du bruit : il estime une grandeur
biologique, à partir du seul CGM.

Une réserve demeure : **la calibration n'améliore pas la prévision**. Branchée
sur la couche 2, elle ne produit aucun écart significatif (p ≥ 0,11) — le modèle
appris reconstruit déjà, depuis l'historique glycémique, ce que les gains patient
encodent. Elle est utile là où elle est validée : le modèle **direct**, donc les
scénarios « et si ? » et l'estimation de paramètres physiologiques.

### Sur cohorte synthétique

Les chiffres synthétiques restent produits par `scripts/run_layer2.py`. Ils
valident le **logiciel** — l'absence de fuite, la mécanique d'évaluation, la
chaîne concepts → features → modèle. Ils ne valident **pas** la physiologie, et
le point 1 ci-dessus montre précisément où ils induisent en erreur.

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

**Sur la couverture conforme :** elle tient sur **données réelles** — 88,5 à 89,8 % pour 90 % visés, sur les quatre horizons. C'était le pari le plus risqué : la garantie conforme suppose l'échangeabilité, que rien ne garantit entre patients réels. Le prix est la largeur, qui passe de 57,7 mg/dL à 30 min à 121,2 mg/dL à 120 min — un intervalle honnête à deux heures est un intervalle inutilisable, ce qui est en soi une information. Piste en réserve : *Mondrian conformal*, ou calibration sur les premiers jours du patient lui-même.

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
results/     sorties brutes des runs de référence
notebooks/   entraînement (Kaggle)
demo/        applications web autonomes — atelier.html = la démo
docs/        revue de littérature, état de l'art, architecture, plans
tests/       124 tests
```

---

## Données

Ce dépôt **ne redistribue aucune donnée patient**.

- **CGMacros v1.0.0** (PhysioNet, `10.13026/3z8q-x658`) — 45 participants réels, **la référence du projet**. Licence **CC BY-NC-SA 4.0**, à télécharger séparément. Voir [`NOTICE.md`](NOTICE.md).
- **Cohorte synthétique** — générée par `glucotwin.layer2.cohort`, pour valider le logiciel sans données.

Trois pièges rencontrés dans CGMacros, tous silencieux et tous traités dans l'adaptateur : `bio.csv` est en **livres et en pouces** ; **11 participants sur 45** n'ont pas la colonne `METs` (reconstruite depuis les calories Fitbit, erreur absolue moyenne 0,000 MET) ; et le **Dexcom et le Libre divergent de 30 mg/dL** de biais, ce qui déplace la MAE plus que n'importe quel modèle. Détails dans [`docs/07_resultats_reels.md`](docs/07_resultats_reels.md).

---

## Feuille de route

- [x] Moteur métabolique interprétable (couches 0-1) — 40 vérifications
- [x] Incertitude sur la partition des substrats
- [x] Phénomène de l'aube, réglable par patient
- [x] Harnais d'évaluation LOPO + persistance + conforme
- [x] Métriques cliniques par zone et détection d'événements
- [x] Application web de démonstration
- [x] **Adaptateur CGMacros** — 45 patients réels, pipeline validé contre le repère publié
- [x] Analyse d'équité par sous-groupes, avec test de permutation
- [x] Couche 3 : probabilités calibrées de risque
- [x] **Calibration de la couche 1 par patient** (problème inverse) — +12,64 mg/dL sur le modèle direct, sans effet sur la prévision
- [x] **Ablation sur données réelles** — les repas portent 91 à 99 % du gain
- [x] **Reparamétrisation des branches basales** — saturation 11 % → 57 %, et la glycémie d'équilibre corrèle à r = 0,82 avec le laboratoire
- [x] **Couche 4** : catalogue fermé + validateur déterministe — le LLM ne peut jamais élargir l'ensemble permis
- [ ] Validation externe sur un second jeu de données

---

## Équipe

Regis Likassi · Hakim Djomo · Jean Direl Nze · Xavier Ondo · Seth Ndinga

*AI for Health (PGE5) — Prof. Anuradha Kar*

## Licence

Code : **MIT** (voir [`LICENSE`](LICENSE)). Attributions et licences tierces : [`NOTICE.md`](NOTICE.md).
