# Jeu de données MET + moteur métabolique (couche 1)

Ressource externe pour la **couche 1** du jumeau numérique : convertir une activité déclarée dans l'emploi du temps en **concepts physiologiques interprétables** (dépense énergétique, glucides et lipides oxydés, captation musculaire du glucose).

Objectif : pouvoir tester **n'importe quelle activité**, y compris celles absentes de CGMacros.

---

## Contenu

| Fichier | Rôle |
|---|---|
| `met_activities.csv` | Table de référence : **78 activités** avec leur coût en METs |
| `metabolic_engine.py` | Moteur de conversion activité → concepts métaboliques |

### Structure du CSV

```
code,activite,categorie,met,intensite,notes
MAR04,Marche rapide (5.6 km/h),Marche,4.3,moderee,
VEL03,Velo soutenu (19-22 km/h),Velo,8.0,vigoureuse,
```

**Catégories couvertes :** Repos, Marche, Course, Vélo, Sport, Fitness, Domestique, Jardinage, Travail, Déplacement, Loisir.

Le champ `code` sert de clé stable : vous pouvez ajouter vos propres activités sans casser le reste.

---

## La chaîne de calcul

```
activité → MET → VO₂ → RER → VCO₂ → équations de Frayn → g/min
                        ↑
              estimé depuis l'intensité
```

1. **MET → VO₂** : `VO₂ (L/min) = MET × 3,5 × poids / 1000`
2. **Intensité → RER** (quotient respiratoire) : croissance saturante de 0,78 vers 1,00. Un sujet entraîné ou à jeun oxyde davantage de lipides → RER plus bas.
3. **Équations de Frayn (1983)** :
   - glucides (g/min) = `4,55 × VCO₂ − 3,21 × VO₂`
   - lipides (g/min) = `1,67 × (VO₂ − VCO₂)`
4. **Part sanguine** : tout le glucose oxydé ne vient pas du sang — une partie vient du glycogène musculaire. La fraction sanguine croît avec la durée (25 % → 55 % vers 90 min), car le glycogène s'épuise.

---

## Utilisation

```python
from metabolic_engine import load_activities, compute_metabolic_state

acts = load_activities("met_activities.csv")
state = compute_metabolic_state(acts["MAR04"], duration_min=30, weight_kg=78)

print(state.summary_fr())
# Marche rapide (5.6 km/h) — 30 min à 4.3 MET : 176 kcal,
# 28.3 g de glucides et 6.9 g de lipides oxydés ;
# captation sanguine ≈ 9.9 g (331 mg/min).
```

Le résultat (`MetabolicState`) **est** le vecteur de concepts du goulot d'étranglement, injectable tel quel dans le modèle de prévision glycémique (couche 2) :

`met`, `vo2_l_min`, `rer`, `energy_kcal`, `cho_oxidized_g`, `fat_oxidized_g`, `blood_glucose_uptake_g`, `glucose_uptake_mg_min`, `glycogen_deficit_g`

### Personnalisation

```python
compute_metabolic_state(
    acts["VEL03"], 45, 78,
    intensity_scale=1.15,  # séance plus soutenue que la moyenne
    fitness=1.2,           # sujet entraîné → oxyde plus de lipides
    fed=False,             # à jeun → RER plus bas
)
```

`intensity_scale` est le levier de personnalisation le plus simple, et le premier candidat à une **calibration par patient** (la stratégie hybride décrite dans le document d'architecture).

---

## Contrôle de cohérence

Le moteur est vérifié contre la formule énergétique classique
`kcal = MET × 3,5 × poids / 200 × durée` :

| Activité (30 min, 78 kg) | Frayn | Formule MET | Écart |
|---|---:|---:|---:|
| Marche rapide | 175,6 kcal | 176,1 kcal | 0,3 % |
| Vélo soutenu | 336,1 kcal | 327,6 kcal | 2,6 % |
| Course 8 km/h | 349,2 kcal | 339,9 kcal | 2,8 % |

Les deux voies de calcul, indépendantes, concordent — c'est le test qui valide la chaîne.

---

## ⚠️ La question du VCO₂ — le point méthodologique central

Les équations de Frayn exigent **VO₂ et VCO₂**. Or le VCO₂ n'est mesurable qu'avec un chariot métabolique de laboratoire : **aucun objet connecté ne le mesure**, il est absent de CGMacros, et absent même du dataset WEEE (dont l'analyseur ne lit que l'oxygène).

Le moteur ne le mesure donc pas : il **l'infère** via `VCO₂ = RER × VO₂`, où le RER est estimé depuis l'intensité. C'est l'hypothèse de modélisation centrale de la couche 1, et il faut l'assumer explicitement.

### Combien ça coûte, exactement

Analyse de sensibilité (`sensitivity.py`) — erreur de ±0,05 sur le RER, sujet de 78 kg, 30 min :

| Activité | Glucides estimés | Variation | Énergie | Variation |
|---|---:|---:|---:|---:|
| Marche modérée | 21,2 g | **±31 %** | 141,7 kcal | ±3,2 % |
| Marche rapide | 28,3 g | **±28 %** | 175,6 kcal | ±3,2 % |
| Vélo soutenu | 66,1 g | **±23 %** | 336,1 kcal | ±3,1 % |
| Course 8 km/h | 69,4 g | **±22 %** | 349,2 kcal | ±3,1 % |
| Musculation | 44,9 g | **±25 %** | 248,8 kcal | ±3,1 % |

**Le résultat est net et exploitable :**

- 🟢 **L'énergie (kcal) est robuste** — elle ne dépend quasiment pas du RER. Ce concept est fiable.
- 🔴 **La partition glucides/lipides est fragile** — ±25 % d'incertitude typique. Ce concept doit **toujours** être affiché avec son intervalle.

C'est pourquoi `MetabolicState` renvoie désormais `cho_oxidized_g_low` et `cho_oxidized_g_high`, et que le résumé affiche `28,3 g [20,3–36,3]`.

### Les trois stratégies possibles

**(a) Assumer et quantifier** — *retenu pour le prototype*
On affiche la fourchette au lieu d'un faux chiffre précis. C'est honnête, immédiat, et c'est même un **argument de rigueur** : un jumeau qui affiche son incertitude est plus crédible qu'un jumeau qui affiche 28,3 g au dixième près.

**(b) Ne garder que l'énergie**
On abandonne la partition et on pilote la couche 2 avec la dépense énergétique seule (robuste). Plus sûr, mais on perd l'explication « combien de sucre consommé » qui fait tout l'intérêt pédagogique.

**(c) Inverser le problème** — ⭐ *la vraie contribution de recherche*
Le VCO₂ manque, mais **on a la conséquence** : la réponse glycémique mesurée par le CGM. On peut donc **calibrer le RER par patient** en ajustant le modèle pour que la captation prédite reproduise la baisse de glycémie réellement observée pendant l'effort.

> On n'a pas besoin de mesurer le mécanisme si on observe son effet. C'est un problème inverse classique — et c'est exactement ce que CGMacros permet, puisqu'il contient à la fois l'activité (METs Fitbit) et la glycémie continue.

C'est cette stratégie (c) qui transforme la faiblesse méthodologique en résultat publiable.

---

## Limites (à énoncer dans la présentation)

- **C'est une chaîne d'estimation, pas une mesure.** Une vraie mesure exigerait une calorimétrie indirecte (VO₂ *et* VCO₂ mesurés).
- **Le RER est modélisé depuis l'intensité**, pas mesuré. C'est l'approximation la plus forte de la chaîne.
- **Les valeurs MET sont des moyennes de population.** Le coût réel d'une activité varie fortement d'un individu à l'autre — d'où l'intérêt de la calibration par patient.
- **La contribution protéique est négligée** (acceptable hors contexte clinique).
- **Les valeurs MET de ce fichier sont des valeurs représentatives** cohérentes avec le standard du Compendium. Pour une publication, citez le *2024 Adult Compendium* officiel et vérifiez les codes d'activité exacts dans le PDF de référence.

---

## Sources

- **2024 Adult Compendium of Physical Activities** — référence mondiale des coûts énergétiques (PDF officiel) : https://pacompendium.com/adult-compendium/
  Article : *J Sport Health Sci* 2024. https://www.sciencedirect.com/science/article/pii/S2095254623001084
- **Frayn KN.** *Calculation of substrate oxidation rates in vivo from gaseous exchange.* J Appl Physiol. 1983;55(2):628-634.
- **WEEE dataset** — dépense énergétique mesurée par calorimétrie indirecte + 7 objets connectés, 17 participants, CC BY 4.0. Utile pour *valider* la couche 1 sur données réelles.
  https://www.nature.com/articles/s41597-022-01643-5 · https://doi.org/10.5281/zenodo.6420886
- **PAMAP2** — 18 activités, 9 sujets, centrales inertielles + cardiofréquencemètre, annoté en intensité. https://archive.ics.uci.edu/dataset/231/pamap2+physical+activity+monitoring

---

*Usage pédagogique et recherche. Ne convient pas à une décision clinique.*
