# De devoir de classe à publication — Feuille de route

**Projet :** *Personalized Diabetes Monitoring Twin* — Cours « AI for Health » (PGE5, Prof. A. Kar)
**Groupe :** Regis Likassi, Hakim Djomo, Jean Direl Nze, Xavier Ondo, Seth Ndinga
**Décisions cadrées :** contribution de type **audit / benchmark** · données **publiques uniquement** · cible **revue à comité de lecture**
**Août 2026**

---

## 0. Ce qui change vraiment entre un devoir et un papier

Un devoir répond à « avons-nous construit quelque chose qui marche ? ». Un papier répond à « avons-nous produit une connaissance nouvelle, mesurée rigoureusement, que d'autres peuvent reproduire et sur laquelle ils peuvent s'appuyer ? ». Trois exigences non négociables :

1. **Une contribution claire et nouvelle** (« la seule chose que ce papier apprend au monde »). « On a combiné des méthodes existantes » ne suffit pas ; « on révèle un résultat empirique que personne n'avait mesuré » suffit.
2. **Une rigueur méthodologique** que des reviewers hostiles ne pourront pas casser (protocole propre, baselines, incertitude, tests).
3. **La reproductibilité** : code et données accessibles, résultats ré-exécutables.

Bonne nouvelle : votre trio de décisions (audit + données publiques + revue) est **parfaitement cohérent**. Un audit rigoureux sur données publiques est exactement le genre de papier qui passe en revue de rang correct sans exiger de données cliniques propres ni d'algorithme inédit.

---

## 1. Le papier proposé

**Titre de travail :**
*« Accuracy is not enough : a joint accuracy–fairness–interpretability audit of glucose-forecasting models for type 2 diabetes »*
(FR : *« La précision ne suffit pas : audit conjoint précision–équité–interprétabilité des modèles de prévision glycémique dans le diabète de type 2 »*)

**Question de recherche.** Quand on évalue des modèles de prévision glycémique pour le DT2 non plus seulement sur la précision, mais **conjointement sur la précision, l'équité entre sous-groupes et la fidélité des explications**, que découvre-t-on — et le « meilleur » modèle en RMSE reste-t-il le meilleur ?

**Contribution (la « seule chose nouvelle »).** Le **premier banc d'essai reproductible qui évalue les trois axes sur le même protocole et les mêmes données publiques de DT2**, révélant (hypothèses à confirmer) : (i) des **écarts d'équité entre sous-groupes** invisibles quand on ne rapporte que le RMSE agrégé ; (ii) un **compromis précision–équité** dans la *prévision temporelle* (et non plus la simple classification du risque, seul cas déjà étudié) ; (iii) un **désaccord des explications** entre familles de modèles, questionnant leur fiabilité clinique.

**Pourquoi c'est publiable (le gap, tiré de notre état de l'art).**
- L'équité a été étudiée sur la **classification** du risque de DT2, **pas sur la prévision glycémique continue** ni sur des sous-groupes cliniques réalistes.
- L'interprétabilité est traitée en **post-hoc** (« on a lancé SHAP ») sans **audit de fidélité/stabilité** ni comparaison entre modèles.
- **Aucun travail n'assemble les trois axes** sur un protocole unique. → connaissance nouvelle, sans algorithme inédit requis.

> C'est un **papier d'audit** : sa valeur vient de la **rigueur** et de la **nouveauté des mesures**, pas d'un modèle magique. C'est précisément ce qui le rend faisable pour un groupe étudiant.

---

## 2. Design expérimental (le cœur de la crédibilité)

### 2.1 Données (publiques, avec démographie — indispensable pour l'axe équité)
- **ShanghaiT2DM** (Zhao et al., *Scientific Data* 2023) : CGM + métadonnées cliniques et démographiques (âge, sexe, IMC, durée). **Jeu principal.**
- **DiaTrend** (*Scientific Data* 2023) : CGM longitudinal, pour **validation externe** (voir §3, piège n°2).
- **Simulateur UVA/Padova** : données synthétiques pour tests contrôlés/ablation.
- *(OhioT1DM en contraste T1D optionnel, pour montrer la généralité du protocole.)*

### 2.2 Tâche
Prévision de la glycémie à **horizons 30 et 60 min** à partir d'une fenêtre de CGM (ex. 2 h) + variables statiques. Définition figée et documentée (fréquence d'échantillonnage, gestion des trous, unités).

### 2.3 Modèles et **baselines** (les baselines sont obligatoires)
- **Baseline naïve** : dernière valeur reportée / extrapolation linéaire *(sans elle → rejet quasi certain)*.
- **Statistique** : ARIMA.
- **Arbres** : XGBoost, Random Forest.
- **Deep** : LSTM, Transformer.
- *(Option exploratoire : un LLM en zero-shot, à cadrer prudemment.)*

### 2.4 Métriques sur **trois axes**
- **Précision** : RMSE, MAE **+ cliniquement pertinent** — grille d'erreur de **Clarke/Parkes**, détection des hypo/hyperglycémies (sensibilité/PPV), qualité du *Time-in-Range* prédit.
- **Équité** : écarts de performance entre sous-groupes (sexe, tranches d'âge, IMC) — **écart de RMSE**, **parité de rappel** sur la détection des hypoglycémies. Évaluation **multi-seed avec intervalles de confiance** (leçon directe de la littérature : les résultats d'équité sur une seule partition sont trompeurs).
- **Interprétabilité** : **fidélité** (les features jugées importantes le sont-elles vraiment ? tests de perturbation/suppression), **stabilité** entre graines, **accord** entre méthodes (SHAP vs attention vs importance par permutation).

### 2.5 Protocole rigoureux
- **Découpage au niveau patient** (aucun patient partagé entre train/validation/test) → évite la fuite de données.
- **Sélection des hyperparamètres sur une partition de validation indépendante** (jamais sur le test — erreur explicite pointée dans un des papiers de fairness que nous avons lus).
- **Validation croisée + répétitions multi-seed**, résultats en moyenne ± IC, **tests statistiques** pour les comparaisons.
- **Étude d'ablation** (impact des variables statiques, de la taille de fenêtre, etc.).

---

## 3. Les 7 pièges qui font rejeter ce type de papier

1. **Fuite de données** : chevauchement de patients entre train et test. → split patient-level strict.
2. **Un seul jeu de données** : pas de validation externe. → ShanghaiT2DM + DiaTrend.
3. **Pas de baseline simple** : sans « dernière valeur »/ARIMA, les gains du deep learning ne veulent rien dire.
4. **Équité sur une seule partition** : instable. → multi-seed + IC + sous-groupes de taille suffisante.
5. **Sur-vente clinique** : conclure à l'utilité clinique depuis des données publiques rétrospectives. → revendiquer un **audit**, pas une preuve d'efficacité.
6. **Interprétabilité = « on a lancé SHAP »** : sans évaluer la **fidélité** des explications. → tests de perturbation.
7. **Non reproductible** : pas de code, seeds non fixées. → dépôt public (§4).

---

## 4. Reproductibilité et standards attendus

- **Suivre TRIPOD+AI (2024)** — la grille de reporting de référence pour les modèles de prédiction cliniques en ML. La renseigner point par point rassure fortement les reviewers.
- **Dépôt de code public** (GitHub), seeds fixées, environnement figé (requirements/Docker), scripts de bout en bout.
- **Données** : déjà publiques → fournir les scripts de préparation (pas les données elles-mêmes si licence).
- **Déclaration d'éthique** : données publiques dé-identifiées → généralement exemptées, mais **le dire explicitement**.
- **Préenregistrer** le protocole (même informellement, dans le dépôt) renforce la crédibilité.

---

## 5. Plan en phases (et répartition possible dans le groupe)

| Phase | Objectif | Livrable | Pilote suggéré |
|---|---|---|---|
| **P0 — Cadrage (1–2 sem.)** | Figer question, gap, protocole | Note de protocole + dépôt Git initialisé | Regis (coordination) |
| **P1 — Données (2 sem.)** | Chargement, nettoyage, splits patient-level, fenêtrage | Pipeline de données reproductible | Hakim |
| **P2 — Modèles (2–3 sem.)** | Baselines + arbres + deep | Modèles entraînés, résultats de précision | Xavier |
| **P3 — Audit 3 axes (2–3 sem.)** | Équité multi-seed + fidélité des explications | Tableaux/figures des 3 axes | Seth (équité) + Jean Direl (interprétabilité) |
| **P4 — Rédaction (3–4 sem.)** | Papier + TRIPOD+AI + figures | Manuscrit v1 | Tous (Regis intègre) |
| **P5 — Préprint & soumission** | arXiv/medRxiv puis revue | Préprint public + soumission | Regis |

*Astuce team : la présentation de septembre (devoir) devient la **répétition générale** du papier ; le manuscrit est une sur-couche du même travail.*

---

## 6. Cible et stratégie de soumission

**Revues réalistes pour un audit ML sur données publiques :**
- *Scientific Reports* (Nature) — généraliste, accepte les benchmarks solides.
- *Frontiers in Digital Health* — très aligné sur ce sujet (plusieurs papiers de notre biblio y sont).
- *JMIR Diabetes* / *JMIR AI* — santé numérique, apprécie la rigueur reporting.
- *IEEE JBHI* — plus technique, bon si l'aspect méthodo est fort.

**Stratégie recommandée :**
1. **Déposer un préprint** (arXiv cs.LG / medRxiv) dès le manuscrit v1 → antériorité, visibilité, retours. Compatible avec ces revues.
2. Choisir **une** revue cible et lire 2–3 papiers qu'elle a publiés pour caler le format.
3. Rédiger une **cover letter** qui énonce le gap et la contribution en 3 phrases.
4. Anticiper une **révision** (*major revision* quasi systématique) : garder du temps.

**Timeline honnête.** Le prototype + manuscrit v1 sont atteignables en **~2–3 mois** (donc compatibles avec une présentation en septembre + préprint). Mais **l'acceptation en revue prend typiquement 3 à 9 mois** (review + révisions). Objectif réaliste : **préprint à la rentrée, soumission peu après, acceptation courant 2027.**

---

## 7. Checklist « prêt à soumettre »

- [ ] Contribution énonçable en 1 phrase, gap étayé par la biblio
- [ ] ≥ 2 jeux de données (dont 1 validation externe)
- [ ] Baseline naïve + baseline statistique présentes
- [ ] Split patient-level, hyperparamètres réglés hors test
- [ ] Résultats multi-seed avec intervalles de confiance + tests stat
- [ ] Trois axes mesurés (précision clinique, équité sous-groupes, fidélité des explications)
- [ ] Étude d'ablation
- [ ] Grille TRIPOD+AI remplie
- [ ] Dépôt de code public, seeds fixées, environnement figé
- [ ] Limites honnêtes + pas de sur-vente clinique
- [ ] Préprint déposé

---

## 8. Références clés

*Données publiques*
- Zhao et al., *Chinese diabetes datasets (ShanghaiT1DM & ShanghaiT2DM)*, Scientific Data (2023). https://www.nature.com/articles/s41597-023-01940-7 · jeu : https://figshare.com/articles/dataset/Diabetes_Datasets-ShanghaiT1DM_and_ShanghaiT2DM/20444397
- *DiaTrend: a dataset from advanced diabetes technology*, Scientific Data (2023). https://www.nature.com/articles/s41597-023-02469-5

*Standards de reporting*
- *TRIPOD+AI statement*, BMJ (2024). https://pubmed.ncbi.nlm.nih.gov/38626948/ · https://www.equator-network.org/reporting-guidelines/tripod-statement/

*Ancrage scientifique (voir aussi l'état de l'art ciblé)*
- *Interpretable glucose forecasting for type 2 diabetes across traditional, deep, and large language models*, Scientific Reports (2025). https://www.nature.com/articles/s41598-025-32373-4
- *Adversarial debiasing for age-equitable diabetes prediction*, Frontiers in Digital Health (2026). https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2026.1816806/full
- *Survey on VVUQ of digital twins for precision medicine*, npj Digital Medicine (2025). https://www.nature.com/articles/s41746-025-01447-y

---

*Document de travail. À valider avec la Prof. A. Kar, qui peut co-encadrer/co-signer et orienter le choix de la revue.*
