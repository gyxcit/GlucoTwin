# Revue de littérature — Jumeaux numériques pour le suivi personnalisé du diabète

**Projet :** *Personalized Diabetes Monitoring Twin* — Cours « AI for Health » (PGE5, Prof. A. Kar)
**Groupe :** Regis Likassi, Hakim Djomo, Jean Direl Nze, Xavier Ondo, Seth Ndinga
**Version :** brouillon de travail — août 2026

> Objectif de ce document : construire une compréhension approfondie du domaine des jumeaux numériques (*digital twins*) appliqués au diabète, cartographier l'état de l'art (définitions, architectures, modèles, données, résultats cliniques) et surtout **identifier clairement les problèmes et verrous** encore ouverts, afin de fonder une problématique de recherche solide pour notre projet.

---

## Résumé exécutif

Le jumeau numérique (JN) est une **réplique virtuelle dynamique d'une entité physique, mise à jour en continu par des données du monde réel**. Appliqué au diabète, il désigne une représentation virtuelle du patient (ou de son métabolisme glucose-insuline) capable de simuler, prédire et optimiser sa prise en charge de façon individualisée.

Le domaine connaît une **accélération très forte depuis 2022** : dans une revue de portée (*scoping review*) récente, près de la moitié des études recensées ont été publiées en 2024. Les résultats cliniques les plus marquants proviennent d'interventions commerciales de type « jumeau métabolique corps entier » (notamment Twin Health), qui rapportent des baisses d'HbA1c de l'ordre de **1,8 à 2,9 points**, des taux de **rémission du diabète de type 2 (DT2) de 60 à 76 %** et des réductions massives de médication sur des cohortes de plusieurs centaines à près de 2 000 patients.

Malgré ces promesses, le domaine reste **immature et fragmenté**. Les principaux problèmes identifiés sont : la **dépendance à la qualité et à l'observance des données**, l'**absence de standards d'interopérabilité** (seulement ~35 % des systèmes adoptent HL7 FHIR), la **faible intégration réelle dans les flux cliniques**, le **manque de validation indépendante à long terme et sur des populations diverses** (forte concentration géographique en Inde, sous-représentation du diabète de type 1), les **questions éthiques et de vie privée**, le **flou réglementaire**, et le **déficit d'interprétabilité** des modèles d'IA.

---

## 1. Contexte et motivation

Le diabète est une maladie chronique complexe dont la gestion repose sur un équilibre fin entre alimentation, activité physique, sommeil, stress, médication et physiologie individuelle. Deux difficultés structurelles rendent la prise en charge standardisée peu efficace :

- **Une forte variabilité inter-individuelle** : à repas identique, la réponse glycémique post-prandiale (PPGR, *postprandial glucose response*) varie considérablement d'un patient à l'autre. Les recommandations « universelles » sont donc sous-optimales.
- **Une dynamique temporelle** : la glycémie dépend de nombreux facteurs couplés (glucides, insuline, activité, stress, infections, sommeil, hormones), ce qui en fait un système difficile à prédire au-delà de quelques dizaines de minutes.

Le jumeau numérique propose un changement de paradigme : passer de **protocoles standardisés** à des **stratégies thérapeutiques hautement individualisées**, pilotées par les données propres de chaque patient et par la simulation « et si ? » (*what-if*).

Il faut noter que la santé reste un secteur émergent pour cette technologie : selon la revue de la *Frontiers in Medicine* (2023), seulement ~1 % des applications de jumeaux numériques concernent aujourd'hui le médical, contre ~47 % pour les *smart cities* — le concept étant initialement issu de l'aérospatiale (Air Force Research Laboratory, 2011 ; puis NASA).

---

## 2. Définitions et concepts fondamentaux

**Jumeau numérique (définition générale).** Représentation virtuelle dynamique d'une entité physique, continuellement mise à jour à l'aide de données du monde réel, permettant simulation, prédiction et aide à la décision.

**Jumeau numérique médical (MeDigiT).** « Système qui combine plusieurs méthodologies de science des données, chacune destinée à prédire un aspect particulier de la santé d'un patient » (Frontiers in Medicine, 2023).

**Jumeau numérique du patient diabétique.** Réplique virtuelle dynamique du patient intégrant des données temps réel multi-sources pour simuler, prédire et optimiser la prise en charge personnalisée.

Trois notions structurent le concept :

1. **Le jumeau physique** — le patient réel (ou l'organe / le système physiologique modélisé).
2. **Le jumeau virtuel** — le modèle numérique qui le réplique.
3. **Le lien bidirectionnel** — le flux de données du réel vers le virtuel (mise à jour continue) et le retour du virtuel vers le réel (recommandations, alertes, aide à la décision), formant une **boucle fermée**.

Un JN se distingue ainsi d'une simple simulation (statique, non reliée à un patient précis) ou d'un modèle prédictif isolé : c'est la **connexion continue et personnalisée** aux données réelles qui fait sa spécificité.

**Échelles de modélisation.** La littérature distingue plusieurs granularités :
- **Niveau corps entier** (*whole-body*) : jumeau métabolique global (ex. Twin Health).
- **Niveau organe** : jumeau du pied diabétique, jumeau cardiaque (*Living Heart* de Dassault Systèmes, modèle Siemens), modélisation rénale pour l'insuffisance terminale.
- **Niveau moléculaire / cellulaire** : intégration multi-omique, atlas cellulaires, cellules numériques pour l'expérimentation virtuelle de médicaments.

**Cycle de gestion en trois phases** (Frontiers in Medicine, 2023) :
- **Pré-maladie** : évaluation du risque de développer un diabète (obésité, sédentarité, facteurs génétiques).
- **Gestion de la maladie** : recommandations thérapeutiques personnalisées et ajustements temps réel (ex. dose d'insuline en fonction de la glycémie continue).
- **Post-maladie** : prédiction des complications (cardiovasculaires, rénales, rétinopathie).

---

## 3. Architecture d'un jumeau numérique du diabète

Les revues récentes convergent vers une **architecture multi-couches** relativement stable :

**1. Couche d'acquisition des données.** Capteurs de glycémie en continu (CGM, ex. Abbott FreeStyle Libre Pro), objets connectés (montres, trackers d'activité type Fitbit), tensiomètres Bluetooth, balances connectées, pompes à insuline, dossiers médicaux électroniques (EHR/DME), et parfois plateformes multi-omiques. Certains systèmes fusionnent plus de 100 signaux physiologiques.

**2. Couche de traitement / infrastructure.** Cloud computing, *edge computing*, réseaux cellulaires sécurisés, calcul haute performance. La **fréquence de mise à jour** va du temps réel (quelques minutes) à l'agrégation épisodique (quotidienne, voire annuelle) selon l'usage. Connectivité : Bluetooth, NFC, WiFi, cellulaire, IoT.

**3. Couche analytique.** Modèles d'apprentissage automatique, cadres statistiques et moteurs de simulation physiologique. C'est le « cerveau » du jumeau (voir §4).

**4. Couche d'interface / restitution.** Applications mobiles, tableaux de bord web, portails d'aide à la décision clinique, interfaces pour les soignants et pour les patients (ex. codage couleur des aliments, alertes temps réel).

**Boucle de rétroaction et contrôle.** La mise à jour temps réel du modèle reflète les changements physiologiques, établissant une interaction en boucle fermée entre le physique et le virtuel — condition pour parler véritablement de « jumeau » plutôt que de modèle statique.

---

## 4. Approches de modélisation

La littérature distingue trois familles, de plus en plus souvent combinées.

### 4.1 Modèles mécanistes / physiologiques
Fondés sur des équations décrivant la dynamique glucose-insuline. Le plus emblématique est le **simulateur UVA/Padova (T1DM)**, approuvé par la FDA et largement utilisé pour générer des données synthétiques et tester des algorithmes. Autres approches : modèles à compartiments, « modèles minimaux » de la dynamique glucose-insuline, méthodes d'identification bayésienne pour personnaliser les paramètres à partir de données limitées.
*Avantages* : interprétabilité, respect des lois physiologiques, capacité à simuler des scénarios non observés. *Limites* : personnalisation difficile, calibration lourde.

### 4.2 Modèles pilotés par les données (*data-driven*, IA/ML)
Dominants dans les publications récentes. On y trouve :
- **LSTM / RNN** pour la prédiction des tendances glycémiques à partir du CGM ;
- **Random Forest**, **Gradient Boosting** (ex. CatBoost, XGBoost) pour l'analyse multi-paramètres et l'estimation des besoins en insuline ;
- **Réseaux de neurones** pour la reconnaissance de motifs multivariés ;
- **Régression logistique** pour la stratification du risque et la prédiction des complications ;
- **Transformers** (mécanismes d'attention) pour capturer les dépendances temporelles longues.

*Avantages* : capacité à modéliser des relations complexes et personnalisées. *Limites* : besoin de gros volumes de données de qualité, faible interprétabilité (« boîte noire »), risque de sur-apprentissage et de biais.

### 4.3 Approches hybrides
Combinaison des deux mondes : modèles compartimentaux personnalisés avec identification de paramètres assistée par ML, réseaux de neurones informés par la physique (*physics-informed*), ou architectures mêlant *gradient boosting* (features statiques) et LSTM (dépendances temporelles). Ces approches visent à concilier **précision** et **respect des contraintes physiologiques**, et représentent une direction de recherche prometteuse.

---

## 5. Sources de données

Un jumeau du diabète se nourrit de flux hétérogènes :

- **Glycémie en continu (CGM)** : cœur du dispositif, échantillonnage typique toutes les 5 minutes (≈ 96 à 288 mesures/jour).
- **Objets connectés / wearables** : activité, fréquence cardiaque, sommeil (Fitbit, montres).
- **Dossiers médicaux électroniques (EHR)** : bilans cliniques, résultats de laboratoire, historiques de médication, comorbidités.
- **Capteurs domestiques** : tensiomètres Bluetooth, balances connectées, pompes/capteurs d'insuline.
- **Données saisies par le patient** : journal alimentaire (bases de >100 000 aliments, ex. USDA ; jusqu'à 37 variables nutritionnelles), horaires de repas, prises d'insuline, sommeil, stress.
- **Données multi-omiques** : génomique, protéomique, métabolomique (jusqu'à >200 biomarqueurs dans certains cadres).

Cette richesse est aussi le **premier point de fragilité** : la valeur du jumeau dépend entièrement de la complétude, de la fiabilité et de l'harmonisation de ces données (voir §8).

---

## 6. Prédiction de la glycémie : état de l'art technique

La prédiction de la glycémie future (à 30, 60, 90, 120 min) est la brique technique centrale d'un jumeau du diabète. Elle conditionne les alertes d'hypo/hyperglycémie et l'aide à la décision.

**Modèles.** L'état de l'art s'oriente vers des architectures **hybrides Transformer + LSTM (bidirectionnel)** : le Transformer capte les dépendances temporelles longues (au-delà de 60 min, où un LSTM seul décroche), le LSTM les motifs courts. On trouve aussi des approches de **méta-apprentissage** et d'**apprentissage fédéré** pour la personnalisation.

**Jeux de données de référence.** Le **OhioT1DM** (patients T1D, données CGM + insuline + repas + activité) est le *benchmark* public le plus cité ; le **simulateur UVA/Padova** (FDA) fournit des données synthétiques pour l'entraînement et le test.

**Performances rapportées** (étude Xiong et al., 2025, modèle Transformer-LSTM) :

| Horizon | RMSE (données cliniques) | RMSE (données simulées) |
|--------:|:------------------------:|:-----------------------:|
| 30 min  | ≈ 10,2 mg/dL             | ≈ 2,0 mg/dL             |
| 60 min  | ≈ 10,6 mg/dL             | ≈ 3,5 mg/dL             |
| 120 min | ≈ 14,0 mg/dL             | —                       |

L'analyse de la grille d'erreur de Clarke montre **> 96 % des prédictions dans la zone de sécurité clinique** jusqu'à 120 min. Les systèmes commerciaux de recommandation nutritionnelle rapportent quant à eux un **R² > 0,85** et une **RMSE d'environ 25 mg/dL** sur la prédiction de la réponse post-prandiale.

**Difficultés propres à la prédiction glycémique :**
1. **Accumulation d'erreur** aux horizons longs (incertitude croissante sur repas, insuline, exercice).
2. **Variabilité individuelle** forte des réponses à l'insuline.
3. **Facteurs multiples et couplés** (glucides, insuline, activité, stress, infections, sommeil, hormones).
4. **Qualité des données** : valeurs manquantes, bruit capteur, discontinuités nécessitant un pré-traitement (filtrage, interpolation).
5. **Interprétabilité** : les mécanismes de décision internes restent opaques, freinant l'adoption clinique malgré de bons chiffres.

---

## 7. Applications cliniques et preuves d'efficacité

### 7.1 Panorama des applications
- **Optimisation du contrôle glycémique** : nutrition personnalisée temps réel, ajustement des doses d'insuline, prévention des hypo/hyperglycémies.
- **Rémission du diabète de type 2** : suivi et stadification de la « réversion » métabolique.
- **Prédiction des complications** : maladie rénale chronique (VPN 84–85 %), événements cardiovasculaires, épisodes hypoglycémiques.
- **Gestion des comorbidités** : hypertension, stéatose hépatique métabolique (MAFLD).
- **Aide à la décision d'exercice** : évaluation de sécurité pré-effort et recommandations individualisées.

### 7.2 Résultats cliniques marquants (interventions « corps entier »)

**Étude réelle rétrospective à 1 an** (Nature Scientific Reports, 2024 ; N = 1 853 patients ayant complété le suivi) :
- HbA1c : **8,1 % → 6,3 %** (−1,8 point) ; 89 % sous le seuil de 7 %.
- Poids : **−4,8 kg** en moyenne.
- Médication : de 1,9 à 0,5 médicament/patient (**−74 %**) ; 62,7 % en contrôle sans aucun antidiabétique.
- **Rémission** : 60,3 % avec HbA1c < 7 % sans médicament.
- Temps dans la cible (*Time in Range*) : **69,7 % → 86,9 %**.

**Essai contrôlé randomisé** (application de la technologie de jumeau à la nutrition prédictive, N ≈ 319) :
- HbA1c : 9,0 % → 6,1 % (groupe JN) vs 8,5 % → 8,2 % (soins standards, non significatif) ;
- **Rémission du DT2 : 72,7 % vs 0 %** ;
- Arrêt de médication : 94 % ; perte de poids ≥ 5 % : 73,8 % ;
- Rémission de l'hypertension : **50 % vs 0 %**.

Le mécanisme repose sur la **précision nutritionnelle** : le système prédit la réponse glycémique post-prandiale individuelle (modèles CatBoost / Random Forest + LSTM) et classe les aliments en « vert / orange / rouge » pour l'usager, en minimisant l'impact glycémique prédit tout en respectant la qualité nutritionnelle et les préférences.

> **Nuance méthodologique importante :** une grande partie de ces preuves provient d'un même écosystème industriel (Twin Health) et d'études majoritairement rétrospectives ou mono-centriques. Les chiffres sont impressionnants mais demandent une **validation indépendante** (voir §8).

---

## 8. Défis et problèmes du domaine

Cette section est le cœur de notre analyse : elle recense les verrous qui définissent les opportunités de recherche.

### 8.1 Données : qualité, observance, hétérogénéité
La performance du jumeau dépend d'un **enregistrement précis et complet** des repas, de l'activité et des constantes. Or l'observance fluctue (motivation, stress, priorités concurrentes), les journaux alimentaires sont auto-déclarés (biais de mesure), et les capteurs souffrent de bruit et de dérive de calibration. L'**harmonisation** de flux multi-sources et la gestion des **données manquantes** (sans standard d'imputation partagé) restent des problèmes ouverts.

### 8.2 Interopérabilité et standards
Fragmentation majeure : dans la revue de portée, seulement **~35 % des systèmes adoptent HL7 FHIR**, ~23 % utilisent des API propriétaires, le reste des méthodes non spécifiées. Sans standard commun, l'intégration aux systèmes hospitaliers et le partage de données restent laborieux.

### 8.3 Intégration clinique et flux de travail
**Faible intégration réelle** : ~35 % des systèmes sont pleinement intégrés au flux clinique, ~35 % ne le sont pas du tout. Il existe un **fossé entre les architectures conceptuelles et l'implémentation réelle** dans les DME. Manquent aussi la formation des soignants et des protocoles d'adoption clairs.

### 8.4 Validation, preuves et sécurité
- **Suivi court** : la plupart des études ne dépassent pas 1 an ; la **durabilité** des bénéfices est inconnue.
- **Échantillons souvent petits** et **designs rétrospectifs/conceptuels** (~35 % chacun), qui n'établissent pas la causalité.
- **Reporting des événements indésirables inconsistant, voire absent**, y compris dans les grands essais.
- Besoin de **méthodologies de validation unifiées** et de métriques comparables.

### 8.5 Généralisation et équité
- **Concentration géographique** : ~59 % des études proviennent d'Inde ; validation limitée dans d'autres systèmes de santé.
- **Sous-représentation du diabète de type 1** au profit du DT2.
- Critères d'inclusion restrictifs (durée de maladie < 8 ans, fonction organique normale) limitant la représentativité.
- **Faible diversité** en âge, ethnie et statut socio-économique ; risque d'amplifier les inégalités de santé (« *gender data gap* », biais algorithmiques race/genre).

### 8.6 Vie privée, sécurité et éthique
Le jumeau concentre des données ultra-sensibles (génétiques, comportementales, temps réel). Risques : vol de données génétiques, attaques par malware, accès non autorisés. Parades évoquées : chiffrement, authentification biométrique, contrôle d'accès par rôles. Enjeux éthiques : **effet de « labellisation »** (si le jumeau prédit une maladie future → stigmatisation, discrimination assurantielle), **fracture d'accès** (coût élevé → creusement des inégalités entre populations et entre pays), conformité **RGPD/HIPAA** en évolution constante.

### 8.7 Réglementation et gouvernance
Absence de **cadre réglementaire clair** pour la qualification d'un jumeau numérique en tant que dispositif médical, statut d'approbation souvent flou, gouvernance des données (*data stewardship*) encore immature.

### 8.8 Complexité technique et passage à l'échelle
Charge de calcul de l'intégration multi-omique, exigences de traitement temps réel en périphérie (*edge*), découverte et configuration automatique des appareils, **scalabilité** à de grandes populations.

### 8.9 Interprétabilité et confiance
Les modèles d'IA les plus performants restent des **boîtes noires**. L'« IA explicable et digne de confiance » (*explainable & trustworthy AI*) — explicitement citée comme thème du cours — est une condition d'adoption clinique encore mal satisfaite.

---

## 9. Synthèse des lacunes de recherche

En croisant les revues, six lacunes reviennent systématiquement :

1. **Résultats à long terme** — bénéfices au-delà de 1 an non démontrés.
2. **Coût-efficacité** — analyses médico-économiques quasi absentes.
3. **Généralisabilité** — preuves concentrées géographiquement, à valider ailleurs.
4. **Mécanisme d'action** — on ignore comment, précisément, le jumeau induit le changement de comportement.
5. **Cadres éthiques** — protection de la vie privée et atténuation des biais insuffisamment traitées.
6. **Populations diverses** — pédiatrie, personnes âgées, publics défavorisés très peu représentés.

---

## 10. Implications pour notre projet (*Personalized Diabetes Monitoring Twin*)

Ces constats orientent directement notre travail :

- **Choix du périmètre** : viser un jumeau **métabolique du DT2** centré sur la prédiction de la réponse glycémique post-prandiale et les recommandations de mode de vie est le cas d'usage le mieux documenté et le plus démontrable.
- **Approche de modélisation** : une architecture **hybride** (gradient boosting pour les features statiques + LSTM/Transformer pour la dynamique CGM) reflète l'état de l'art et équilibre performance et faisabilité.
- **Données** : s'appuyer sur des **jeux publics** (OhioT1DM, simulateur UVA/Padova) permet de prototyper sans collecte clinique, tout en discutant honnêtement les limites de généralisation.
- **Différenciation possible / angle de recherche** : puisque les verrous dominants sont l'**interprétabilité**, l'**équité/généralisation** et la **validation**, notre présentation gagnerait à intégrer un volet **IA explicable** et une **discussion critique de la reproductibilité** — ce qui nous distinguerait des démonstrations purement « chiffres impressionnants ».
- **Lien métavers** (thème du cours) : positionner l'environnement virtuel comme couche d'**interaction et de visualisation** du jumeau (le jumeau fournit données et intelligence ; le métavers, l'immersion).

Problématique candidate : *« Comment concevoir un jumeau numérique du patient diabétique de type 2 qui soit non seulement précis dans sa prédiction glycémique, mais aussi interprétable, équitable et validable, afin de franchir le fossé entre preuve de concept et adoption clinique ? »*

---

## 11. Bibliographie

*Revues et cadres conceptuels*
- *From Architecture to Outcomes: Mapping the Landscape of Digital Twins for Personalized Diabetes Care — A Scoping Review*, PMC (2025). https://pmc.ncbi.nlm.nih.gov/articles/PMC12653829/
- *The potential of the Medical Digital Twin in diabetes management: a review*, Frontiers in Medicine (2023). https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2023.1178912/full
- *Digital twin paradigm in diabetes prediction and management*, Diabetes Research and Clinical Practice / ScienceDirect (2025). https://www.sciencedirect.com/science/article/pii/S0168822725010903
- *Digital twins in healthcare: a comprehensive review and future directions*, Frontiers in Digital Health (2025). https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2025.1633539/full
- *Digital twins for health: a scoping review*, npj Digital Medicine (2024). https://www.nature.com/articles/s41746-024-01073-0

*Preuves cliniques (interventions « corps entier »)*
- *One-year outcomes of a digital twin intervention for type 2 diabetes: a retrospective real-world study*, Scientific Reports (2024). https://www.nature.com/articles/s41598-024-76584-7
- *Personalized nutrition in type 2 diabetes remission: application of digital twin technology for predictive glycemic control*, PMC (2024). https://pmc.ncbi.nlm.nih.gov/articles/PMC11615876/
- *Remission of T2DM by digital twin technology with reduction of cardiovascular risk*, European Heart Journal (2022). https://academic.oup.com/eurheartj/article/43/Supplement_1/ehab849.177/6521199
- *Digital Twin in Managing Hypertension Among People With Type 2 Diabetes: 1-Year RCT*, JACC: Advances (2024). https://www.jacc.org/doi/10.1016/j.jacadv.2024.101172

*Prédiction de la glycémie (technique)*
- Xiong X. et al., *Exploring the potential of deep learning models integrating transformer and LSTM in predicting blood glucose levels for T1D patients*, Digital Health / SAGE (2025). https://journals.sagepub.com/doi/full/10.1177/20552076251328980
- *Comparative Evaluation of ML and DL Models for Blood Glucose Prediction on the OhioT1DM Dataset* (2025). https://www.researchgate.net/publication/394809286
- *Personalized federated learning-based glucose prediction algorithm*, Scientific Reports (2025). https://www.nature.com/articles/s41598-025-22316-4.pdf

*Défis, éthique et gouvernance*
- *Medical Digital Twin Technology for Interoperability: Challenges and Opportunities* (2026). https://doi.org/10.1177/11795972261431928
- *Beyond the gender data gap: co-creating equitable digital patient twins*, Frontiers in Digital Health (2025). https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2025.1584415/full
- *Data Stewardship Barriers to Building Digital Twin Technology for Precision Medicine* (2024). https://doi.org/10.3390/aimed1030020

*Ressources fournies dans le cours*
- Nature — *Digital twins in healthcare* : https://www.nature.com/articles/s44287-024-00025-w
- IQVIA — *Digital Twins in Healthcare* (white paper) : https://www.iqvia.com/-/media/iqvia/pdfs/library/white-papers/digital-twins-in-healthcare-whitepaper-iqvia-medtech.pdf

---

*Document de travail — à enrichir au fil du projet. Les chiffres cités proviennent des sources listées et doivent être re-vérifiés avant toute inclusion dans un support de présentation ou une soumission à publication.*
