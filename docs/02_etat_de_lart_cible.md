# État de l'art ciblé — Vers un jumeau numérique du diabète de type 2 précis, interprétable, équitable et validable

**Projet :** *Personalized Diabetes Monitoring Twin* — Cours « AI for Health » (PGE5, Prof. A. Kar)
**Groupe :** Regis Likassi, Hakim Djomo, Jean Direl Nze, Xavier Ondo, Seth Ndinga
**Document compagnon de la revue de littérature — août 2026**

---

## Problématique retenue

> « Comment concevoir un jumeau numérique du patient diabétique de type 2 qui soit non seulement **précis** dans sa prédiction glycémique, mais aussi **interprétable**, **équitable** et **validable**, afin de franchir le fossé entre preuve de concept et adoption clinique ? »

Cette problématique repose sur quatre exigences (précision, interprétabilité, équité, validabilité). Ce document recense **ce qui a déjà été fait sur chacun de ces axes**, puis montre où se situe le verrou que notre projet peut adresser : ces quatre briques existent séparément, mais **ne sont quasiment jamais co-conçues dans un même jumeau du DT2**.

---

## Axe 1 — Précision de la prédiction glycémique : bien avancé

C'est l'axe le plus mûr de la littérature.

- **Architectures.** L'état de l'art combine **Transformers** (attention, dépendances longues) et **LSTM bidirectionnels** (motifs courts). Xiong et al. (2025) atteignent des RMSE d'environ **10 mg/dL à 30 min** et **14 mg/dL à 120 min** sur données cliniques, avec **> 96 % des prédictions en zone de sécurité clinique** (grille de Clarke).
- **Modèles classiques encore compétitifs.** Le *gradient boosting* (XGBoost, CatBoost) et les *Random Forests* restent performants sur les données tabulaires/statiques et sont souvent combinés au LSTM pour la partie temporelle.
- **Grands modèles de langage (LLM).** Une étude Nature (2025) compare, pour le **DT2**, modèles traditionnels, *deep learning* et LLM (GPT-4.1, LLaMA) sur le jeu **ShanghaiT2DM** (100 patients) : GPT-4.1 est le meilleur à 30–60 min, LLaMA-7B à 90 min — une piste nouvelle mais encore exploratoire.
- **Jeux de données de référence.** OhioT1DM (T1D), ShanghaiT2DM (T2D), simulateur UVA/Padova (FDA, données synthétiques).

**Constat :** prédire la glycémie « avec un bon RMSE » est aujourd'hui un problème largement résolu et très concurrentiel. **La précision seule n'est plus un facteur différenciant.** La valeur se déplace vers les trois autres axes.

---

## Axe 2 — Interprétabilité : émergent, mais fragmenté

L'IA explicable (XAI) appliquée à la glycémie est un champ actif mais récent.

- **SHAP** est l'outil dominant : plusieurs travaux (Nature 2023 ; Nature 2025 sur le DT2) l'utilisent pour montrer que **les glycémies récentes du CGM sont les prédicteurs principaux**, devant les variables statiques (âge, IMC, durée du diabète).
- **Explications en langage naturel.** L'étude Nature 2025 fait générer par GPT-4.1 des explications textuelles **sans entraînement supplémentaire**, et montre qu'elles **s'alignent avec les résultats SHAP** — piste intéressante pour l'acceptabilité par le patient/clinicien.
- **RL explicable.** Des travaux appliquent l'analyse par **valeurs de Shapley** au *reinforcement learning* pour la surveillance glycémique (ScienceDirect 2026).
- **Modèles intrinsèquement interprétables.** Le cadre *proof-of-concept* de jumeau « *decision-aware* » (arXiv 2026) privilégie des ensembles classiques (boosting, forêts) « capturant les non-linéarités tout en restant interprétables », plutôt que des boîtes noires.

**Constat :** l'interprétabilité est surtout traitée en **post-hoc** (SHAP appliqué après coup) et **sur la seule tâche de prédiction**, rarement au niveau des **recommandations d'intervention** (« pourquoi le jumeau me conseille-t-il de réduire tel aliment ? »). L'interprétabilité *by design*, couplée à la décision, reste ouverte.

---

## Axe 3 — Équité : identifié comme problème, solutions encore instables

L'équité est reconnue comme un verrou majeur, mais les solutions sont immatures.

- **Biais démographiques documentés.** Des revues systématiques sur l'IA du diabète pointent une **sous-déclaration de l'équité** et un **biais d'étiquette physiologique** (ex. l'HbA1c ne se comporte pas de façon identique selon l'origine ethnique, ce qui biaise les labels eux-mêmes). Le « *gender data gap* » est explicitement traité dans un article Frontiers 2025 sur les *equitable digital patient twins*.
- **Méthodes de dé-biaisage.** Deux familles principales : le **rééchantillonnage** des données (medRxiv 2023, DT2) et le **dé-biaisage adverse** (couche de renversement de gradient) pour rendre la représentation indépendante d'un attribut protégé (ex. l'âge, Frontiers 2026).
- **Résultat clé et sobre.** L'étude de dé-biaisage adverse (Frontiers 2026) montre que ces méthodes **améliorent parfois le sous-groupe le plus faible** (rappel des >50 ans : 0,56 → 0,78) **mais dégradent l'équité globale** (écart de rappel qui s'élargit), avec une **forte instabilité** (écart-type > 0,27 sur plusieurs graines aléatoires). Les auteurs concluent que « les évaluations sur une seule partition sont insuffisantes » et que l'équité doit être mesurée en **multi-seed** avec une représentation suffisante des sous-groupes.

**Constat :** on sait **mesurer et nommer** l'iniquité, mais **la corriger de façon stable et sans sacrifier la précision reste non résolu**. Peu de travaux appliquent ces méthodes **spécifiquement à un jumeau du DT2** (les études fairness portent surtout sur la *classification* du risque, pas sur la *prévision temporelle* ni sur les recommandations).

---

## Axe 4 — Validabilité : cadres existants, non appliqués aux jumeaux du diabète

C'est l'axe le plus structurant pour « franchir le fossé vers l'adoption clinique ».

- **Cadre de crédibilité.** La norme **ASME V&V 40 (2018)** et la **guidance FDA** sur la crédibilité des modèles computationnels fournissent un cadre « *fit-for-purpose* » (validation adaptée à l'usage précis visé). Une revue npj Digital Medicine (2025) fait le point sur la **VVUQ** (vérification, validation, quantification de l'incertitude) des jumeaux pour la médecine de précision.
- **Verrous propres aux jumeaux.** Contrairement à un modèle figé, un jumeau **se met à jour en continu** → question ouverte : **« à quelle fréquence re-valider ? »**. La validation par essais randomisés classiques est **mal adaptée** à un objet individualisé (**N-of-1**) ; les modèles sont souvent validés en **environnement contrôlé** peu représentatif ; et il manque des mécanismes de **détection « hors-spécification »** (quand la prédiction n'est plus fiable pour ce patient).
- **Essais in silico.** Idée de tester les interventions sur des cohortes de patients simulés **avant** la phase clinique ; **HeartFlow** (cardiologie) est cité comme succès réglementaire (autorisation FDA 510(k)) obtenu via une VVUQ rigoureuse — preuve qu'un modèle computationnel peut atteindre l'adoption clinique.
- **Décision plutôt que prédiction.** Le cadre arXiv 2026 propose un jumeau **« decision-aware »** : au lieu de prévoir une valeur isolée, il **simule des contrefactuels** (« réduire les glucides de 60 g à 30 g abaisse le pic de 179 à 153 mg/dL »), avec code et données publics — un pas vers la validabilité et la reproductibilité.

**Constat :** les **cadres de validation existent** (ASME V&V40, VVUQ, N-of-1, essais in silico) mais **ne sont presque jamais appliqués concrètement aux jumeaux du diabète**, qui restent majoritairement des preuves de concept non validées cliniquement (cf. revue de portée : ~35 % de designs conceptuels, suivi ≤ 1 an, forte concentration géographique).

---

## Cartographie synthétique

| Travail (année) | Précision | Interprétabilité | Équité | Validabilité | Type / données |
|---|:---:|:---:|:---:|:---:|---|
| Xiong et al., Transformer-LSTM (2025) | ●●● | ○ | ○ | ● (Clarke) | T1D, clinique + UVA/Padova |
| Nature — glucose forecasting interprétable T2D (2025) | ●●● | ●● (SHAP + LLM) | ○ | ○ | DT2, ShanghaiT2DM |
| Twin Health / RCT & real-world (2022–2024) | ●●● | ○ | ○ | ●● (RCT, mais mono-écosystème) | DT2, corps entier |
| Dé-biaisage adverse âge (Frontiers 2026) | ●● | ○ | ●● (instable) | ● (multi-seed) | Classification risque |
| *Equitable digital patient twins* (Frontiers 2025) | ○ | ● | ●●● | ● | Conceptuel / genre |
| Jumeau *decision-aware* (arXiv 2026) | ●● | ●● (ensembles + contrefactuels) | ○ | ●● (in silico, code ouvert) | Multi-type diabète |
| VVUQ pour la médecine de précision (npj 2025) | — | ● | — | ●●● (ASME V&V40, N-of-1) | Cadre / revue |

*Légende : ●●● fort · ●● moyen · ● faible · ○ absent.* On voit qu'**aucune ligne n'a de « ● » sur les quatre colonnes** : c'est précisément l'espace de contribution.

---

## Le « gap » : ce qui n'a pas encore été fait

En croisant les quatre axes, quatre lacunes ressortent :

1. **Aucune intégration des quatre exigences.** Chaque axe est traité isolément. Il n'existe pas, à notre connaissance, de jumeau du **DT2** qui soit **simultanément** précis, interprétable *by design*, audité pour l'équité, et validé selon un cadre de crédibilité reconnu.
2. **Interprétabilité limitée à la prédiction, pas à la décision.** Le SHAP explique « pourquoi cette glycémie prévue », rarement « pourquoi cette recommandation d'intervention ».
3. **Équité peu transférée au DT2 temporel.** Les méthodes de *fairness* sont testées sur la classification du risque, pas sur la prévision glycémique continue ni sur des sous-groupes cliniques réalistes, et restent instables.
4. **Validation « fit-for-purpose » absente des jumeaux du diabète.** Les cadres (ASME V&V40, VVUQ, N-of-1, essais in silico) existent mais ne sont pas opérationnalisés pour ce cas d'usage.

---

## Positionnement et contributions possibles pour notre projet

Dans le cadre d'un projet étudiant (15 min, prototype), nous ne validerons évidemment pas cliniquement un jumeau. Mais nous pouvons **démontrer une méthodologie intégrée** qui, elle, est originale. Pistes concrètes et réalistes :

- **Prototype prédictif** sur un jeu public (ShanghaiT2DM pour le DT2, ou OhioT1DM), avec une architecture hybride (boosting + LSTM/Transformer) — pour la brique précision.
- **Volet interprétabilité** : SHAP sur la prédiction **et** explication en langage naturel des recommandations (« vert/orange/rouge » justifié) — la partie « pourquoi » différenciante.
- **Volet équité** : audit des performances par sous-groupes (âge, sexe, IMC) avec métriques de *fairness* (écart de rappel), évaluation **multi-seed** — en assumant l'instabilité observée dans la littérature comme un **résultat honnête**.
- **Volet validabilité** : positionner le prototype dans le cadre **ASME V&V40 / VVUQ** (usage visé, niveau de crédibilité requis, plan de validation N-of-1), même sans le réaliser — cela montre la maturité méthodologique et « le chemin vers la clinique ».
- **Couche métavers** (thème du cours) : environnement de visualisation immersif où le patient explore ses contrefactuels (« et si je change ce repas ? »).

**Message central de la présentation :** *le vrai défi du domaine n'est plus la précision, mais l'assemblage précision + interprétabilité + équité + validabilité — et c'est cet assemblage que nous proposons de prototyper et de cadrer.*

---

## Bibliographie complémentaire (ciblée sur les 4 axes)

*Précision / prédiction*
- Xiong X. et al., *Transformer + LSTM for blood glucose prediction (T1D)*, Digital Health/SAGE (2025). https://journals.sagepub.com/doi/full/10.1177/20552076251328980
- *Interpretable glucose forecasting for type 2 diabetes across traditional, deep, and large language models*, Scientific Reports (2025). https://www.nature.com/articles/s41598-025-32373-4

*Interprétabilité (XAI)*
- *The importance of interpreting ML models for blood glucose prediction: a SHAP analysis*, Scientific Reports (2023). https://www.nature.com/articles/s41598-023-44155-x
- *A comparative study of explainability methods for time-series forecasting of blood glucose*, Discover AI / Springer (2026). https://link.springer.com/article/10.1007/s44163-026-01328-7
- *Explainable reinforcement learning for glucose monitoring based on Shapley value analysis*, ScienceDirect (2026). https://www.sciencedirect.com/science/article/abs/pii/S0169260726000349

*Équité / biais*
- *Adversarial debiasing for age-equitable diabetes prediction*, Frontiers in Digital Health (2026). https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2026.1816806/full
- *Enhancing Fairness and Accuracy in Type 2 Diabetes Prediction through Data Resampling*, medRxiv (2023). https://www.medrxiv.org/content/10.1101/2023.05.02.23289405v2.full
- *Beyond the gender data gap: co-creating equitable digital patient twins*, Frontiers in Digital Health (2025). https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2025.1584415/full
- *Comprehensive Evaluation of ML for T2D Risk Prediction: External Validation and Fairness Analysis*, arXiv (2026). https://arxiv.org/abs/2607.16253

*Validabilité / crédibilité*
- *Survey and perspective on VVUQ of digital twins for precision medicine*, npj Digital Medicine (2025). https://www.nature.com/articles/s41746-025-01447-y
- *Credibility assessment of in silico clinical trials for medical devices*, PLOS Computational Biology (2024). https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012289
- FDA — *Assessing the Credibility of Computational Modeling and Simulation in Medical Device Submissions*. https://www.fda.gov/media/154985/download

*Jumeau « decision-aware »*
- *A Proof-of-Concept Simulation-Driven Digital Twin Framework for Decision-Aware Diabetes Modeling*, arXiv (2026). https://arxiv.org/html/2605.11247

---

*Document de travail. Les chiffres et affirmations proviennent des sources listées et doivent être re-vérifiés avant inclusion dans le support final ou une soumission.*
