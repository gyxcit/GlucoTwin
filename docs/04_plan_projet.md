# Plan de projet — Prévision glycémique DT2 : au-delà de la précision

**Projet :** *Personalized Diabetes Monitoring Twin* — Cours AI for Health (PGE5, Prof. A. Kar)
**Équipe :** Regis Likassi · Hakim Djomo · Jean Direl Nze · Xavier Ondo · Seth Ndinga
**Base technique :** pipeline CGMacros dérivé de `DiabetesTwin-AI` (MIT)
**Échéances :** présentation de 15 min en septembre 2026 · préprint dans la foulée · soumission revue ensuite
**Rédigé le 11 août 2026**

---

## 1. La thèse du projet

> **À 30 minutes, la prévision glycémique est un problème saturé : la persistance (« la glycémie ne bougera pas ») est quasi imbattable. La question intéressante n'est donc pas « quel modèle a la plus petite erreur », mais « où et quand la prévision a-t-elle une valeur clinique réelle — et sait-on quand elle est fiable ? »**

Tout le projet découle de cette phrase. Elle donne l'angle, elle donne les expériences, elle donne le titre du papier.

**Titre de travail :** *Accuracy is not enough — horizons, événements, incertitude et équité dans la prévision glycémique du diabète de type 2*

**Les quatre affirmations que nous voulons pouvoir défendre en fin de projet :**

1. La supériorité d'un modèle sur la persistance **dépend de l'horizon** — et devient réelle au-delà de 30 min.
2. La MAE moyenne **masque les événements cliniquement importants** (hypo/hyperglycémies).
3. Une prévision sans **intervalle de confiance** n'est pas utilisable cliniquement — et on peut en produire avec garantie.
4. La performance **n'est pas la même pour tous les sous-groupes** de patients.

---

## 2. Périmètre

**Dans le périmètre**
- Données : PhysioNet **CGMacros v1.0.0** (45 participants — 15 sains, 16 prédiabétiques, 14 DT2)
- Tâche : prévision de la glycémie à **30 / 60 / 90 / 120 min** + détection d'**événements** hypo/hyper
- Modèles : persistance, régression linéaire, Random Forest, HistGradientBoosting (+ un modèle séquentiel *en dernier, si le temps le permet*)
- Évaluation : leave-one-participant-out, métriques cliniques, incertitude conforme, analyse par sous-groupes, interprétabilité

**Hors périmètre (à dire explicitement dans la présentation)**
- Toute recommandation de traitement ou de dose d'insuline
- Toute revendication clinique ou réglementaire
- La collecte de données patients propres
- Le déploiement temps réel

---

## 3. Architecture du dépôt

Nouveau dépôt, avec attribution explicite du pipeline repris (voir `NOTICE.md`).

```text
glucobench/
├── LICENSE                    # MIT (copyright d'origine conservé + le nôtre)
├── NOTICE.md                  # ce qui est dérivé de DiabetesTwin-AI
├── README.md                  # la thèse en première ligne
├── pyproject.toml
├── data/                      # jamais committé (.gitignore)
├── src/glucobench/
│   ├── ingest/                # ← REPRIS : download, checksum, parsing CGMacros
│   ├── features.py            # ← ÉTENDU : vitesse, accélération, temps depuis repas,
│   │                          #   décroissance glucidique, interaction heure × repas
│   ├── targets.py             # ← NOUVEAU : niveau vs delta, horizons multiples, événements
│   ├── evaluation.py          # ← NOUVEAU : LOPO, GroupKFold répété, tests appariés
│   ├── clinical_metrics.py    # ← NOUVEAU : Clarke/Parkes, erreur par zone, détection hypo
│   ├── uncertainty.py         # ← NOUVEAU : prédiction conforme (couverture garantie)
│   ├── fairness.py            # ← NOUVEAU : performance par sous-groupe
│   └── explain.py             # ← NOUVEAU : SHAP + test de fidélité
├── experiments/               # un script par expérience, numéroté
├── results/                   # tableaux et figures versionnés
├── docs/
│   ├── PROTOCOL.md            # protocole gelé AVANT les expériences
│   ├── RESULTS.md
│   └── TRIPOD-AI.md           # grille de reporting remplie
└── tests/
```

**Règle d'or :** le protocole (`docs/PROTOCOL.md`) est écrit et committé **avant** de lancer la première expérience. C'est ce qui empêche de bricoler les résultats après coup, et c'est ce qui rend le travail crédible.

---

## 4. Phases et calendrier

Calendrier calé sur une présentation à **mi-septembre 2026** (~5 semaines).

### Semaine 1 — Fondations
**Objectif :** le dépôt existe, les données coulent, le protocole est gelé.

- Créer le dépôt, `LICENSE` + `NOTICE.md` + README avec la thèse
- Premier commit : import du pipeline d'ingestion CGMacros (message explicite MIT)
- Faire tourner le téléchargement + vérification checksum + parsing → reproduire les 621k lignes
- Rédiger et committer `docs/PROTOCOL.md` : questions, métriques, splits, critères de succès
- Mettre en place les tests + CI GitHub Actions

**Livrable :** dépôt public fonctionnel, protocole gelé, données reproductibles.
**Fini quand :** un membre de l'équipe peut cloner et régénérer la table de features de zéro.

---

### Semaine 2 — Le harnais d'évaluation (la brique la plus importante)
**Objectif :** pouvoir mesurer honnêtement. Aucun modèle nouveau à ce stade.

- `evaluation.py` : **leave-one-participant-out** (45 plis) + GroupKFold répété
- Baseline **persistance** systématique dans chaque sortie
- **Tests appariés** (Wilcoxon) + intervalles de confiance sur les différences
- Rejouer les baselines existantes (RF, HGB) dans ce nouveau harnais

**Livrable :** tableau « modèle × pli » avec moyenne ± IC et p-value contre persistance.
**Fini quand :** on peut dire « la différence est réelle » ou « c'est du bruit », avec un chiffre.

> ⚠️ Résultat attendu : à 30 min, les modèles **ne battront pas** significativement la persistance. C'est le point de départ de l'histoire, pas un échec.

---

### Semaine 3 — Changer la question
**Objectif :** montrer où la prévision devient réellement utile.

- `targets.py` : cible en **variation (delta)** au lieu du niveau
- **Horizons multiples** : 30 / 60 / 90 / 120 min
- **Événements** : classification hypo (<70) et hyper (>180) à venir dans l'heure
- `features.py` : vitesse, accélération, temps depuis le dernier repas, décroissance glucidique, **interaction heure × repas** (hypothèse circadienne)
- **Ablations** : glucose seul → + repas → + activité → + biologie → + circadien

**Livrable :** courbe « avantage sur la persistance en fonction de l'horizon » — **la figure centrale du projet**.
**Fini quand :** on sait à partir de quel horizon un modèle apporte quelque chose, et quelles features comptent.

---

### Semaine 4 — Métriques cliniques et incertitude
**Objectif :** parler le langage du clinicien, pas seulement celui du data scientist.

- `clinical_metrics.py` : grille d'erreur de **Clarke/Parkes**, erreur **par zone glycémique**, **sensibilité/précision de détection des hypos**
- `uncertainty.py` : **prédiction conforme** → intervalles à 90 % avec garantie de couverture
- Vérifier empiriquement la couverture (l'intervalle contient-il bien la vraie valeur 90 % du temps ?)

**Livrable :** tableau des métriques cliniques + démonstration que la MAE et la détection d'hypo ne classent **pas** les modèles pareil.
**Fini quand :** chaque prédiction sort avec un intervalle, et sa couverture est vérifiée.

---

### Semaine 5 — Équité, interprétabilité, présentation
**Objectif :** boucler les deux derniers axes et préparer les 15 minutes.

- `fairness.py` : performance par sous-groupe (sains / prédiabétiques / DT2, sexe, tranches d'âge, IMC) — avec **intervalles de confiance**, en assumant la faible puissance statistique
- `explain.py` : SHAP + **test de fidélité** (les variables jugées importantes le sont-elles vraiment ?)
- Rédiger `docs/RESULTS.md`
- Construire la présentation + répétition chronométrée
- Brancher **GlucoTwin** comme démo interactive de la partie « jumeau »

**Livrable :** présentation de 15 min + dépôt complet et reproductible.

---

### Après la présentation — Track publication
- Validation externe sur un second jeu de données (OhioT1DM, DiaTrend)
- Modèle séquentiel (LSTM/TCN/Transformer) comparé aux baselines solides
- Remplir la grille **TRIPOD+AI**
- Rédaction du manuscrit → **préprint** (arXiv/medRxiv) → soumission revue

---

## 5. Répartition dans l'équipe

| Membre | Responsabilité principale | Livrable dont il répond |
|---|---|---|
| **Regis Likassi** | Coordination, protocole, rédaction, intégration | `PROTOCOL.md`, présentation, manuscrit |
| **Jean Direl Nze** | Pipeline de données & infra (son expertise) | `ingest/`, CI, reproductibilité |
| **Hakim Djomo** | Features & cibles | `features.py`, `targets.py`, ablations |
| **Xavier Ondo** | Évaluation & métriques cliniques | `evaluation.py`, `clinical_metrics.py` |
| **Seth Ndinga** | Incertitude, équité, interprétabilité | `uncertainty.py`, `fairness.py`, `explain.py` |

**Rituel :** un point de 30 min par semaine — chacun montre son résultat de la semaine, on met à jour `RESULTS.md`. Pas de travail non partagé plus d'une semaine.

---

## 6. Les expériences à mener

| # | Expérience | Question à laquelle elle répond |
|---|---|---|
| E1 | Baselines en LOPO à 30 min | La persistance est-elle vraiment imbattable ? |
| E2 | Balayage des horizons (30→120) | À partir de quand un modèle apporte-t-il quelque chose ? |
| E3 | Cible niveau vs delta | Prédire la variation change-t-il le classement ? |
| E4 | Ablations de features | Quelles données comptent vraiment ? |
| E5 | Interaction heure × repas | L'hypothèse circadienne améliore-t-elle la prévision ? |
| E6 | Détection d'événements hypo/hyper | La MAE et l'utilité clinique coïncident-elles ? |
| E7 | Prédiction conforme | Peut-on garantir la fiabilité annoncée ? |
| E8 | Performance par sous-groupe | Le modèle est-il équitable ? |
| E9 | SHAP + fidélité | Les explications sont-elles fiables ? |

**Discipline expérimentale :** une seule modification à la fois, toujours comparée à la persistance, toujours avec un intervalle de confiance. Si trois choses changent ensemble, on n'apprend rien.

---

## 7. Risques et parades

| Risque | Parade |
|---|---|
| Aucun modèle ne bat la persistance, même à 120 min | **Ce n'est pas un échec** — c'est un résultat publiable, à condition d'être rigoureusement établi. L'histoire devient « voici pourquoi, et voici où chercher ». |
| Sous-groupes trop petits (14 DT2) → équité peu puissante | Rapporter les intervalles de confiance, nommer la limite, la traiter comme un argument pour la validation externe |
| Le temps manque avant septembre | Priorité absolue aux semaines 2 et 3 (évaluation + horizons). L'incertitude et l'équité peuvent glisser après la présentation. |
| Fuite de données ou bug silencieux | Splits au niveau participant, tests unitaires sur la construction des cibles, CI |
| Dispersion de l'équipe | Chaque membre a **un fichier** dont il répond ; point hebdomadaire |

---

## 8. Critères de réussite

**Pour le devoir (septembre)**
- Une démo qui tourne + une histoire claire en 15 min
- Au moins E1, E2 et E6 menées jusqu'au bout
- Les limites énoncées honnêtement

**Pour la publication**
- Les 9 expériences menées, protocole gelé respecté
- Validation externe sur un second jeu de données
- Grille TRIPOD+AI remplie, dépôt public reproductible
- Préprint en ligne

---

## 9. Le principe qui gouverne tout

> **Rapporter honnêtement ce qui ne marche pas.**

C'est ce qui rend un travail crédible aux yeux d'un reviewer, et c'est ce qui différencie un projet de recherche d'une démonstration commerciale. Un résultat négatif solidement établi vaut mieux qu'un résultat positif fragile.

---

*Document de travail — à valider avec la Prof. A. Kar, qui peut co-encadrer et orienter le choix de la revue.*
