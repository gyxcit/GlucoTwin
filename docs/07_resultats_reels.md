# Résultats sur données réelles — CGMacros, 45 participants

**Jeu :** CGMacros v1.0.0 (PhysioNet, `10.13026/3z8q-x658`) · **capteur :** Dexcom G6 Pro
**Cohorte :** 45 participants · 395 journées · 114 155 pas de 5 min
**Groupes :** 15 sains · 16 prédiabétiques · 14 DT2 (seuils ADA sur l'HbA1c)
**Protocole :** leave-one-patient-out, baseline de persistance, intervalles conformes à 90 %
**Modèle :** HistGradientBoosting, cible en variation, 24 features

> Ce document remplace les résultats synthétiques comme référence du projet.
> Les chiffres synthétiques restent dans le README, clairement étiquetés — ils
> valident le logiciel, pas la physiologie.

---

## 1. La vérification qui compte : le pipeline est juste

| | notre run | repère publié |
|---|---:|---:|
| **Persistance à 30 min** | **13,41 mg/dL** | **13,39 mg/dL** |
| Modèle à 30 min | 12,33 mg/dL | 13,11 mg/dL |

La persistance — « la glycémie dans 30 minutes sera celle de maintenant » — ne
dépend d'**aucun modèle**. C'est une propriété des données seules : de leur
échantillonnage, de leur découpage en journées, de l'alignement des horizons.
Retomber à **0,02 mg/dL** du chiffre publié valide le chargement de bout en
bout. C'était la seule façon de savoir si l'adaptateur était correct sans avoir
la vérité terrain.

---

## 2. Le résultat principal

| horizon | MAE modèle | MAE persistance | gain | p (Wilcoxon) | patients gagnés | couverture conforme |
|---:|---:|---:|---:|---:|---:|---:|
| 30 min | **12,33** | 13,41 | **+1,08** | 1,3e-04 | 34/45 | 89,8 % |
| 60 min | 20,66 | 19,97 | −0,69 | 0,55 | 25/45 | 89,4 % |
| 90 min | 25,32 | 24,51 | −0,81 | 0,37 | 25/45 | 88,9 % |
| 120 min | 28,73 | 28,01 | −0,72 | 0,15 | 28/45 | 88,5 % |

**Le gain existe à 30 minutes et disparaît au-delà.** Passé 30 min, le modèle
ne bat plus la persistance : l'écart change de signe et n'est plus significatif.

### Ce qui contredit le run synthétique

Sur cohorte simulée, le gain **triplait** avec l'horizon (+2,06 → +5,72 mg/dL,
tous p < 1e-7). Le README annonçait : *« ce qui se transférera aux données
réelles, c'est la pente, pas les valeurs »*. **C'était faux.** La pente
s'inverse.

L'explication est dans la construction de la cohorte synthétique : la glycémie y
est engendrée à partir des concepts que le modèle reçoit. Plus l'horizon
s'allonge, plus la part explicable par les concepts domine le bruit — donc plus
le modèle paraît gagner. Sur données réelles, les déterminants non observés
(collations non déclarées, stress, sommeil réel, médicaments, variabilité
inter-jour) prennent le dessus et la persistance redevient imbattable.

**C'est un résultat, pas un échec.** Il dit quelque chose de vrai sur la
validation par données simulées, et il est mesuré, pas supposé.

---

## 3. Le résultat clinique : l'hypoglycémie n'est jamais vue

| horizon | événements hypo réels | sensibilité | événements hyper | sensibilité |
|---:|---:|---:|---:|---:|
| 30 min | 223 | **0 %** | 15 727 | 70 % |
| 60 min | 223 | **0 %** | 15 482 | 43 % |
| 90 min | 221 | 2 % | 15 238 | 30 % |
| 120 min | 221 | **0 %** | 15 020 | 24 % |

**Zéro.** Sur 223 hypoglycémies réelles, le modèle n'en annonce aucune, à aucun
horizon. Sur la cohorte synthétique il n'y avait pas assez d'événements pour
le voir.

L'erreur par zone dit la même chose :

| zone (à 30 min) | n | MAE |
|---|---:|---:|
| hypoglycémie (< 70) | 223 | **37,77** |
| bas-normal (70–100) | 9 473 | 14,12 |
| normal (100–180) | 81 518 | **9,85** |
| élevé (180–250) | 12 862 | 21,60 |
| très élevé (> 250) | 2 969 | **37,36** |

Le modèle est excellent là où il ne se passe rien et mauvais aux extrêmes — à
120 min, la MAE en zone très élevée atteint **108 mg/dL**. Une MAE globale de
12,33 mg/dL masque entièrement cette structure.

---

## 4. L'équité : l'écart est réel et il change de signe

À 60 minutes :

| groupe | n | MAE modèle | MAE persistance | gain | patients gagnés | sensibilité hyper |
|---|---:|---:|---:|---:|---:|---:|
| diabétiques | 14 | 25,71 | 25,77 | **+0,06** | 10/14 | 46,8 % |
| prédiabétiques | 16 | 18,46 | 19,18 | +0,73 | 9/16 | 37,9 % |
| sains | 15 | 18,29 | 15,40 | **−2,89** | 6/15 | 29,1 % |

**Écart maximal 7,42 mg/dL, p = 0,019** au test de permutation des étiquettes de
groupe — au-delà de ce que le hasard produit avec 45 patients.

Et le **signe s'inverse** : le modèle aide les diabétiques et **dégrade** les
sains. C'est cohérent physiologiquement — chez un sujet sain la glycémie bouge
peu, la persistance est donc quasi parfaite et tout modèle ne fait qu'ajouter du
bruit. La quatrième affirmation du projet est démontrée.

Aux autres horizons :

| horizon | écart max | p | lecture |
|---:|---:|---:|---|
| 60 min | 7,42 | **0,019** | écart réel |
| 90 min | 9,76 | **0,040** | écart réel |
| 120 min | 11,66 | 0,074 | ne se distingue plus du bruit |

À 120 min l'écart est le plus grand *et* le moins significatif : la variance
inter-patient croît plus vite que l'écart. C'est exactement pourquoi le test de
permutation est nécessaire — sans lui, on aurait annoncé l'inéquité la plus
forte là où elle est la moins établie.

---

## 5. La couche 3 : reformuler en probabilité récupère beaucoup — sauf l'essentiel

La détection par seuil demande « la prédiction dépasse-t-elle 180 ? ». La
couche 3 demande autre chose : « quelle est la probabilité de dépasser 180 ? ».
Ce n'est pas la même question, et l'écart entre les deux est le sujet.

### Hyperglycémie — la reformulation marche

| horizon | détection par seuil | AUROC / patient | AP (hasard = 0,15) | gain sur la climatologie | ECE |
|---:|---:|---:|---:|---:|---:|
| 30 min | 71,7 % | **0,926** | 0,857 | **+0,623** | 0,004 |
| 60 min | 48,2 % | 0,772 | 0,601 | +0,310 | 0,021 |
| 90 min | 35,8 % | 0,687 | 0,426 | +0,142 | 0,038 |
| 120 min | 29,4 % | 0,666 | 0,339 | **+0,055** | 0,052 |

Le gain sur la climatologie reste **positif à tous les horizons**. À deux heures,
la probabilité bat encore « ça arrive 15 % du temps », avec une précision moyenne
2,3 fois le hasard. La quantification survit.

**Et c'est mieux que sur la cohorte synthétique**, où ce même gain devenait
*négatif* dès 60 min (−0,028 à −0,059). Troisième fois que la cohorte simulée
induit en erreur, cette fois par pessimisme.

### Hypoglycémie — le résultat qui compte, et sa limite

| horizon | détection par seuil | AUROC / patient | AP (hasard = 0,002) | gain sur la climatologie |
|---:|---:|---:|---:|---:|
| 30 min | **0,0 %** | **0,752** [0,623 – 0,880] | **0,042** — soit **20× le hasard** | +0,009 |
| 60 min | 0,0 % | 0,609 [0,481 – 0,737] | 0,007 | −0,009 |
| 90 min | 1,8 % | 0,532 [0,433 – 0,631] | 0,003 | −0,008 |
| 120 min | 0,0 % | 0,529 [0,447 – 0,611] | 0,003 | −0,009 |

**À 30 minutes, la reformulation récupère une information que le seuillage jetait
entièrement.** La prévision ponctuelle ne franchit jamais 70 mg/dL — sensibilité
strictement nulle — alors que la probabilité issue du *même modèle* classe les
instants à risque avec une AUROC de 0,752 et une précision moyenne vingt fois
supérieure au hasard. C'est l'argument le plus fort en faveur de la couche 3, et
il porte sur l'événement cliniquement le plus grave.

**Au-delà de 30 minutes, il n'y a plus rien.** L'AUROC tombe à 0,53 — l'intervalle
de confiance touche 0,5 — et le gain sur la climatologie devient négatif. Sur
223 événements répartis chez seulement 18 patients, il n'y a pas de quoi faire
mieux. La conclusion honnête est donc bornée : **la reformulation probabiliste
sauve la détection d'hypoglycémie à 30 minutes, et seulement à 30 minutes.**

### Ce qu'il faut en retenir

Trois questions, trois vitesses de dégradation :

| | 30 min | 120 min |
|---|---|---|
| valeur ponctuelle (MAE) | utile (+1,08 sur la persistance) | inutile (−0,72) |
| détection d'hyperglycémie | 71,7 % | 29,4 % |
| **risque d'hyperglycémie** | AUROC 0,926 | **AUROC 0,666, toujours utile** |
| détection d'hypoglycémie | **0 %** | 0 % |
| **risque d'hypoglycémie** | **AUROC 0,752** | 0,529 — plus rien |

Optimiser la MAE ne rend pas un jumeau cliniquement utile ; mais **poser la
question sous forme de probabilité récupère une partie de ce que le seuillage
détruit**. C'est mesuré, pas supposé.

---

## 5 bis. La prédiction conforme tient

Couverture observée **88,5 à 89,8 %** pour 90 % visés, sur les quatre horizons.
C'était le pari le plus risqué du projet : la garantie conforme suppose
l'échangeabilité, que rien ne garantit entre patients réels. Elle tient.

Prix à payer : la largeur d'intervalle passe de 57,7 mg/dL à 30 min à
121,2 mg/dL à 120 min. Un intervalle honnête à deux heures est un intervalle
inutilisable — ce qui est, encore une fois, une information.

---

## 5 ter. Calibration de la couche 1 par patient — le problème inverse

Le VCO₂ est la limite méthodologique numéro un du projet : les équations de
Frayn l'exigent, aucun objet connecté ne le mesure, et la partition
glucides/lipides en dépend à ±25 %. Plutôt que d'afficher un intervalle et de
s'arrêter là, on peut **inverser le problème** — on n'a pas besoin de mesurer le
mécanisme si on observe son effet, et la glycémie, elle, est mesurée en continu.

Cinq paramètres par patient : trois gains sur les branches de la couche 1
(apparition alimentaire, production hépatique, captation), une vitesse de retour
à l'équilibre et une glycémie d'équilibre. **Ajustés sur les 3 premières
journées, testés sur les 6 suivantes.**

| | RMSE sur les journées de test |
|---|---:|
| paramètres **calibrés par patient** | **27,33 mg/dL** |
| paramètres de population (médiane des *autres* patients) | 39,97 mg/dL |
| persistance | 35,95 mg/dL |

**Gain +12,64 mg/dL** [IC95 +8,31, +16,96], p = 1,1e-09, **40 patients sur 44**
améliorés. Le modèle direct calibré bat la persistance chez **42 sur 44**.

Le gain existe dans les trois sous-groupes, et il est le plus fort chez les
diabétiques (+17,47 contre +13,78 chez les sains) — c'est-à-dire là où la
physiologie s'écarte le plus de la moyenne.

### Ce que les paramètres racontent : le patient moyen n'existe pas

| paramètre | p10 | médiane | p90 | rapport p90/p10 |
|---|---:|---:|---:|---:|
| gain apparition glucidique | 0,230 | 0,915 | 2,319 | **10,1×** |
| gain production hépatique | 0,300 | 0,761 | 2,500 | 8,3× |
| gain captation | 0,300 | 1,045 | 2,500 | 8,3× |
| vitesse de retour à l'équilibre | 0,014 | 0,038 | 0,095 | 6,7× |
| glycémie d'équilibre | 92,0 | 128,8 | 166,5 | 1,8× |

Un facteur **dix** sur la sensibilité à la charge glucidique entre le dixième et
le quatre-vingt-dixième centile. C'est l'argument le plus direct en faveur d'un
jumeau *personnalisé* plutôt que d'un modèle de population — et il est mesuré
sur données réelles.

### La limite, et elle est sérieuse

**61 % des patients ont le gain hépatique collé à une borne**, et seuls **5 des
44** n'ont aucun paramètre saturé. Le gain médian est d'ailleurs plus grand chez
les patients saturés (+8,97) que chez les autres (+2,97) — signe qu'une part de
l'amélioration vient de paramètres poussés aux murs pour absorber les défauts du
modèle, pas d'une identification physiologique.

La cause est structurelle : **production hépatique et captation agissent toutes
deux sur le niveau de base**, et la glycémie d'équilibre aussi. Trois paramètres
pour un seul degré de liberté observable. Leur corrélation croisée le confirme
(r = 0,51 entre les deux gains, r = 0,49 entre captation et équilibre), et seul
leur **flux net** est réellement identifié — il s'étale de −220 à +170 mg/min
selon le patient.

**Conclusion honnête, en deux temps.** La calibration patient *généralise* : sur
des journées jamais vues, elle bat nettement des paramètres de population, et ce
n'est pas de la sur-adaptation puisque le découpage est temporel. Mais les
paramètres pris **un par un** ne sont pas interprétables en l'état. La suite
n'est pas de calibrer davantage, c'est de **reparamétrer** : fusionner les deux
branches basales en un flux net unique, ce qui rendrait le modèle identifiable
sans rien perdre de son pouvoir prédictif.

---

## 5 quater. La calibration améliore-t-elle la *prévision* ? Non — et c'est instructif

La section précédente montre qu'ajuster les paramètres physiologiques par
patient améliore nettement le **modèle direct**. Ce n'est pas la question qui
compte pour l'architecture. Celle-ci est : des concepts calculés avec ces
paramètres améliorent-ils le **modèle appris** de la couche 2 ?

**Protocole.** Les θ sont ajustés sur la glycémie du patient : évaluer sur les
journées d'ajustement serait une fuite pure. On reproduit donc le déploiement
réel — *le jumeau observe la personne 3 jours, puis la sert* — et les journées
d'observation **sortent de l'évaluation**. Les deux bras portent sur exactement
les mêmes journées, les mêmes plis, la même graine. Seuls les concepts changent.

| horizon | MAE concepts d'origine | MAE concepts calibrés | écart | p apparié | patients gagnés |
|---:|---:|---:|---:|---:|---:|
| 30 min | 12,18 | 12,33 | −0,15 | 0,268 | 19/44 |
| 60 min | 19,20 | 18,73 | +0,47 | 0,109 | 26/44 |
| 90 min | 23,43 | 22,56 | +0,87 | 0,151 | 24/44 |

**Aucun écart n'est significatif.** Avec 44 patients, la calibration n'améliore
pas la prévision de façon démontrable.

### Ce que ce résultat négatif apprend

Le modèle appris **reconstruit déjà**, depuis l'historique glycémique, l'essentiel
de ce que les gains patient encodent. Un patient qui absorbe vite laisse cette
signature dans ses vingt dernières minutes de glycémie, et le gradient boosting
la lit. Personnaliser les concepts en amont ne lui apprend rien qu'il n'ait
déduit lui-même.

C'est une information sur les architectures à goulot conceptuel en général : le
goulot sert l'**interprétabilité** — on peut dire *pourquoi* la glycémie monte —
mais il ne garantit pas un gain de précision, parce que l'historique de la
variable cible est un raccourci que le modèle prendra toujours.

### La tendance qu'on ne peut pas encore trancher

L'écart croît avec l'horizon : −0,15 → +0,47 → +0,87 mg/dL. La direction est
physiologiquement cohérente — à court terme l'historique glycémique domine, à
long terme la physiologie reprend du poids — et la détection d'hyperglycémie
suit le même sens (68,2 → 69,4 %, 47,6 → 50,1 %, 34,5 → 37,3 %). Mais avec
p = 0,11 au mieux, **c'est une tendance, pas un résultat**. Il faudrait plus de
patients, ou des horizons plus longs, pour trancher.

### Où la calibration reste utile

Là où elle a été validée : le **modèle direct**, avec +12,64 mg/dL et
p = 1,1e-09. C'est-à-dire pour simuler des journées qui n'ont pas eu lieu — les
scénarios « et si ? » de la démonstration — pas pour prévoir la prochaine demi-heure.
La distinction n'est pas cosmétique : ce sont deux usages différents du même jumeau.

---

## 6. Trois pièges rencontrés dans les données

### `bio.csv` est en unités impériales

`Body weight` vaut 133,8 et `Height` vaut 65 : des **livres et des pouces**.
Pris pour des kilogrammes, le poids était surestimé de 120 % en moyenne — et le
poids pilote le VO₂, la production hépatique et la captation musculaire. Toute
la couche 1 aurait été fausse sans qu'aucune erreur ne soit levée.
`resolve_weight_kg` ne devine pas : il recoupe avec l'IMC et la taille.

### Onze participants n'ont pas de colonne `METs`

Leur export Fitbit fournit une colonne `Intensity` ordinale (0–3) à la place.
Les écarter coûtait un quart de la cohorte ; les garder sans activité vidait la
branche activité.

`Calories (Activity)` est présente partout, et Fitbit la calcule **depuis** le
MET : corrélation **1,000** sur les 33 participants qui ont les deux colonnes.
En ancrant le repos à 1 MET, on restitue la série exacte — erreur absolue
moyenne **0,000 MET**, maximum 0,045. Les 45 participants ont leur activité.

### Les deux capteurs ne disent pas la même chose

Biais Dexcom − Libre : **+30,3 mg/dL**. Écart absolu médian : **33,2 mg/dL**.

Le choix du capteur déplace la MAE **plus que n'importe quel modèle**. Nos
résultats sont sur Dexcom ; toute comparaison à un repère publié doit être faite
sur le même capteur, sinon elle ne veut rien dire. À énoncer dans les limites.

---

## 7. Limites

- **Un seul jeu de données.** Aucune validation externe.
- **Index glycémique non disponible** : tous les repas sont traités en IG moyen.
  Les fibres, elles, sont utilisées.
- **Sommeil déduit** de la série d'intensité, faute d'annotation. Le phénomène
  de l'aube est calé sur l'heure de lever ainsi estimée.
- **Médication inconnue** : la metformine est désactivée pour tous, faute
  d'information.
- **Journal de repas déclaratif**, avec les oublis et approximations habituels.
- Le jeu n'est **pas redistribué** par ce dépôt (CC BY-NC-SA 4.0).

---

## 8. Reproduire

```bash
# 1. Télécharger CGMacros depuis PhysioNet et décompresser (les CSV suffisent)
# 2. Contrôler la recevabilité — 7 vérifications
python scripts/inspect_cgmacros.py data/CGMacros

# 3. L'expérience complète, équité comprise
python scripts/run_cgmacros.py data/CGMacros --horizons 30 60 90 120 \
    --out results/cgmacros_reel.json

# 4. La couche 3 — risque calibre, sur les deux evenements
python scripts/run_risk.py --cgmacros data/CGMacros --event hyper \
    --horizons 30 60 90 120 --reliability --out results/couche3_reel_hyper.json
python scripts/run_risk.py --cgmacros data/CGMacros --event hypo \
    --horizons 30 60 90 120 --reliability --out results/couche3_reel_hypo.json
```

Chaque chiffre de ce document sort de [`results/logs/run_cgmacros_complet.log`](../results/logs/run_cgmacros_complet.log),
la sortie intégrale du run de référence — commande, commit, date et versions de
bibliothèques en en-tête. Les agrégats correspondants sont dans
[`results/cgmacros_reel.json`](../results/cgmacros_reel.json), **écrit par le
script lui-même**, jamais recopié à la main.
