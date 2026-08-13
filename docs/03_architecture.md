# Architecture — Jumeau numérique à goulot d'étranglement métabolique

**De l'emploi du temps à la recommandation, en passant par un état métabolique interprétable**

**Projet :** *Personalized Diabetes Monitoring Twin* — Cours AI for Health (PGE5, Prof. A. Kar)
**Équipe :** Regis Likassi · Hakim Djomo · Jean Direl Nze · Xavier Ondo · Seth Ndinga
**Août 2026**

---

## 1. Ce que vous avez décrit, en termes techniques

Votre idée : *l'emploi du temps → un modèle qui déduit la consommation de sucre/protéines selon l'activité → ces paramètres nourrissent le modèle de prévision glycémique → on traduit les chiffres en états (risque d'hypo, crise…) → un LLM conditionné produit des recommandations.*

Ce n'est pas une intuition naïve : c'est exactement le principe des **Concept Bottleneck Models** (Koh et al., ICML 2020). Au lieu d'aller directement `entrée → sortie` avec une boîte noire, on force le passage par une couche intermédiaire de **concepts interprétables par un humain**.

```
Approche classique (boîte noire)
   emploi du temps ──────────────────────────► glycémie prédite
                        (on ne sait pas pourquoi)

Votre approche (goulot d'étranglement)
   emploi du temps ──► ÉTAT MÉTABOLIQUE ──► glycémie prédite
                       (lisible, corrigeable,
                        traçable)
```

**Pourquoi c'est fort, concrètement :**

1. **Interprétabilité par construction**, pas rajoutée après coup avec SHAP. On ne dit plus « la variable 7 pesait 0,3 », on dit « votre séance de 45 min a consommé ~38 g de glucides, ce qui explique la baisse prévue ».
2. **Intervention possible** : un clinicien (ou le patient) peut **corriger un concept** — « non, ma séance était plus intense » — et la prédiction se recalcule. Impossible avec une boîte noire.
3. **Contrefactuels naturels** : le « et si ? » devient une manipulation directe des concepts, pas une re-simulation opaque.
4. **Recommandations traçables** : chaque conseil pointe vers le concept qui l'a déclenché. C'est ce qui rend la couche LLM auditables — et donc défendable.

---

## 2. La lecture honnête de la nouveauté

Il faut savoir où l'on est original et où on ne l'est pas. Sinon un reviewer le fera à notre place.

| Brique | État de la littérature | Notre positionnement |
|---|---|---|
| Prévision glycémique 30 min | **Saturé** — la persistance est quasi imbattable | Ce n'est pas là qu'on gagne |
| LLM pour la gestion du diabète | **Déjà encombré** — *DM-Bench* (2025), *LLM-CGM* (PSB 2025), prévision par LLM (2025) | On l'utilise, on ne le revendique pas comme contribution |
| Concept bottleneck en imagerie médicale | Établi (MICCAI 2024, ARDS, dermatologie) | Terrain connu |
| **Concept bottleneck métabolique pour la glycémie** | **Pas trouvé dans la littérature** | ⭐ **Notre contribution** |

**Formulation de la contribution :**

> Nous n'ajoutons pas une boîte noire de plus. Nous insérons entre l'emploi du temps et la glycémie un **goulot d'étranglement physiologiquement interprétable**, qui rend le jumeau explicable de bout en bout et permet de tracer chaque recommandation jusqu'à un mécanisme.

---

## 3. L'architecture en cinq couches

### Couche 0 — L'emploi du temps (l'entrée)
Ce que la personne remplit :
- **Activités** : type, heure de début, durée, intensité
- **Repas** : heure, glucides / protéines / lipides / fibres
- **Sommeil** : heures de coucher et de lever
- **Contexte** : stress, médication

*Déjà construit dans GlucoTwin.*

---

### Couche 1 — Emploi du temps → état métabolique ⭐ **le goulot**

C'est le cœur de l'idée. On calcule des grandeurs **physiologiquement réelles et lisibles** :

| Concept | Sens physiologique | Comment on l'obtient |
|---|---|---|
| `EE` — dépense énergétique | kcal/min | METs × poids × durée (Compendium of Physical Activities) |
| `CHO_ox` — oxydation des glucides | g/min | Partition des substrats selon l'intensité (le fameux « quotient respiratoire ») |
| `Glc_uptake` — captation musculaire | mg/min | Contraction musculaire → GLUT4, **indépendant de l'insuline** |
| `COB` — glucides en cours d'absorption | g | Cinétique d'absorption du repas |
| `Glyc_deficit` — déficit de glycogène | u.a. | Déclenche la sensibilité accrue post-effort (24–48 h) |
| `ISI` — index de sensibilité à l'insuline | multiplicateur | Modulé par circadien × sommeil × stress × effort récent |
| `Circ` — facteur circadien | multiplicateur | Décline sur la journée (meilleur le matin) |

> **La réponse précise à votre question « déduire la consommation de sucre selon l'activité » :** c'est `CHO_ox` et `Glc_uptake`. C'est de la physiologie établie — à faible intensité on brûle surtout des lipides, à intensité élevée surtout des glucides. La bascule est mesurable et modélisable.

---

### Couche 2 — État métabolique → glycémie prévue

**Entrée :** le vecteur de concepts + l'historique glycémique récent
**Sortie :** trajectoire prévue à **30 et 60 min**, **avec intervalle de confiance**

Modèle : gradient boosting ou modèle séquentiel, entraîné sur CGMacros. L'incertitude vient de la **prédiction conforme** (couverture garantie).

Point clé : comme l'entrée est le vecteur de concepts, on peut **modifier un concept et voir l'effet** — le « et si ? » devient mécanique et explicable.

---

### Couche 3 — Chiffres → états ⭐ *« juste des chiffres, ce n'est pas séduisant »* — vous avez raison

On ne montre pas « 142 mg/dL ». On montre un **état** :

| État | Ce qu'on calcule | Affichage |
|---|---|---|
| Risque d'hypoglycémie | Probabilité **calibrée** de passer < 70 dans l'heure | 🔴 Risque élevé (78 %) |
| Risque d'hyperglycémie | Probabilité de dépasser 180 | 🟠 Modéré (41 %) |
| Dynamique | Vitesse et accélération | ↗️ Montée rapide (+2,1 mg/dL/min) |
| Temps dans la cible projeté | % des 2 prochaines heures | 68 % |
| **Fiabilité** | Le modèle est-il en terrain connu ? | ⚠️ Faible confiance |

Ce dernier point est capital : **le système doit savoir dire qu'il ne sait pas.** Un jumeau qui prédit avec assurance dans une situation inhabituelle est dangereux.

---

### Couche 4 — LLM conditionné → recommandations

C'est la couche la plus **séduisante** et la plus **risquée**. Le principe de conception qui rend l'ensemble défendable :

> **Le LLM est un traducteur, pas un décideur.**

**Ce que le LLM reçoit :** uniquement l'état structuré (concepts + risques + fiabilité). Jamais les données brutes.

**Ce que le LLM fait :** choisir dans un **catalogue de recommandations validées** et formuler en langage naturel, personnalisé, avec l'explication du *pourquoi*.

**Ce que le LLM ne fait jamais :** inventer un conseil médical, proposer une dose d'insuline, modifier un traitement.

```
état structuré → sélection dans le catalogue validé → rédaction par le LLM
                                                            ↓
                                              validateur à base de règles
                                                            ↓
                                                     affichage au patient
```

**Les garde-fous, non négociables :**
1. Catalogue de recommandations **fermé et validé** (jamais de génération libre de contenu médical)
2. **Validateur automatique** en sortie : rejette toute mention de dose, de médicament, de diagnostic
3. **Traçabilité** : chaque conseil affiche le concept déclencheur
4. **Escalade** : si risque sévère ou faible fiabilité → « consultez un professionnel », point final
5. **Avertissement permanent** : outil pédagogique, pas dispositif médical

**Exemple de sortie :**

> ⚠️ **Risque d'hypoglycémie dans l'heure (78 %)**
> Votre séance de 45 min a consommé environ 38 g de glucides et votre glycémie descend à 2,1 mg/dL/min.
> 💡 Envisagez une collation glucidique avant votre sortie de 18 h.
> *Déclenché par : `Glc_uptake` élevé + `COB` faible. Ceci n'est pas un avis médical.*

---

## 4. Le problème difficile : la vérité terrain de la couche 1

**Il faut être lucide :** on ne peut pas *superviser* directement la couche 1 avec CGMacros. Il n'y a pas de calorimétrie indirecte dans ce jeu de données — donc pas d'étiquette « voici les vrais grammes de glucides oxydés ».

Trois stratégies, par ordre de risque croissant :

**(a) Concepts calculés, pas appris** — *recommandé pour le prototype*
On calcule les concepts avec les équations physiologiques établies (METs, partition des substrats). Seule la couche 2 est apprise. Simple, transparent, défendable immédiatement.

**(b) Supervision faible, bout en bout**
La couche 1 est apprise à travers la perte de la couche 2, avec des **contraintes physiologiques** (signe, ordre de grandeur, monotonie) pour que les concepts gardent leur sens. Plus puissant, plus risqué : sans contraintes, les « concepts » dérivent et perdent leur interprétabilité — c'est le fameux *concept leakage* de la littérature CBM.

**(c) Hybride, personnalisé** — *la vraie contribution de recherche*
On initialise avec les équations, puis on **calibre par patient** les coefficients (sensibilité individuelle à l'effort, aux glucides). C'est là qu'un jumeau devient réellement *personnalisé*, et c'est ça qui serait publiable.

**Plan :** (a) pour septembre, (c) comme contribution scientifique ensuite.

---

## 5. Ce qui est faisable, et quand

| Couche | Effort | Septembre | Après |
|---|---|---|---|
| 0 — Emploi du temps | ✅ fait | GlucoTwin | — |
| 1 — Goulot métabolique | Moyen | Version (a), équations | Version (c), calibration |
| 2 — Prévision + incertitude | Moyen | 30/60 min sur CGMacros | Horizons longs, séquentiel |
| 3 — États et risques | Faible | Complet | Calibration fine |
| 4 — LLM + garde-fous | Moyen | Catalogue + validateur | Évaluation de sécurité |

**Réaliste pour la présentation :** couches 0-1-2-3 complètes + couche 4 en version démonstration avec un petit catalogue. C'est déjà une démo très forte.

---

## 6. Comment ça se branche sur l'existant

Rien n'est à jeter, tout s'emboîte :

- **GlucoTwin** fournit la couche 0 (emploi du temps) et l'interface — il devient la vitrine du système
- **Le pipeline CGMacros** fournit les données pour entraîner la couche 2
- **Le harnais d'évaluation** du plan de projet valide la couche 2 (LOPO, métriques cliniques, conformal)
- **Les couches 1, 3 et 4 sont les nouvelles briques** — et ce sont elles qui portent la contribution

---

## 7. La phrase à retenir pour la présentation

> « La plupart des jumeaux numériques prédisent un chiffre. Le nôtre explique un mécanisme : de ce que vous faites, à ce que votre corps consomme, à ce que votre glycémie devient, jusqu'à ce que vous pouvez faire — chaque étape étant lisible et vérifiable. »

---

## 8. Références

**Fondement méthodologique**
- Koh P.W. et al. *Concept Bottleneck Models.* ICML 2020. https://dl.acm.org/doi/10.5555/3524938.3525433
- *Integrating Clinical Knowledge into Concept Bottleneck Models.* MICCAI 2024. https://papers.miccai.org/miccai-2024/415-Paper1786.html
- *Concept Complement Bottleneck Model for Interpretable Medical Image Diagnosis.* arXiv 2024. https://arxiv.org/html/2410.15446v1

**LLM et diabète (l'état du terrain)**
- *DM-Bench: Benchmarking LLMs for Personalized Decision Making in Diabetes Management.* arXiv 2025. https://arxiv.org/html/2510.00038v2
- *LLM-CGM: A Benchmark for LLM-Enabled Querying of CGM Data.* PSB 2025. http://psb.stanford.edu/psb-online/proceedings/psb25/healey.pdf
- *Personalized glucose forecasting for T1D using large language models.* ScienceDirect 2025. https://www.sciencedirect.com/science/article/pii/S0169260725001543

**Physiologie de la couche 1**
- Compendium of Physical Activities (valeurs MET) — Ainsworth et al.
- Partition des substrats à l'effort (oxydation glucides vs lipides selon l'intensité)
- Captation musculaire du glucose indépendante de l'insuline (GLUT4 / AMPK)

---

*Document de conception — à discuter en équipe et à valider avec la Prof. A. Kar.*
