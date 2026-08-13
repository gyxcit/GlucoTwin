# GlucoTwin (v2) — Déploiement, utilisation & fondements scientifiques

Application web autonome (un seul fichier `index.html`, **aucune dépendance externe**). Elle fonctionne hors-ligne : idéal pour une présentation en direct sans risque de coupure réseau.

## Option A — Tester tout de suite (0 min)
Double-cliquez sur `index.html` : il s'ouvre dans le navigateur. Rien à installer.

## Option B — Déployer une vraie URL publique (~2 min)

**Netlify Drop (le plus simple) :** https://app.netlify.com/drop → glissez-déposez `index.html` → URL immédiate (`https://votre-nom.netlify.app`). Créez un compte gratuit pour la rendre permanente.

**Vercel :** https://vercel.com → « Add New… › Project » → importez le dossier → Deploy.

**GitHub Pages :** poussez `index.html` à la racine d'un dépôt → Settings › Pages › branche `main` → URL `https://<compte>.github.io/<repo>/`.

> Fichier statique → n'importe quel hébergeur statique convient. Pas de serveur, pas de base de données.

## Ce que fait la démo (v2)
- **Patient virtuel** : âge, sexe, IMC, ancienneté, sensibilité à l'insuline, metformine.
- **Emploi du temps de la journée** : heures de lever/coucher, des 3 repas, du créneau d'activité (durée + intensité). Le **sommeil** et la **dépense en kcal** sont déduits.
- **Modulation circadienne** : la sensibilité à l'insuline décline sur la journée — un même repas fait un pic plus élevé le soir que le matin.
- **Effets locaux** : marche après un repas → captation musculaire du glucose (aplatit le pic) ; exercice → baisse transitoire de la glycémie.
- **Sortie** : courbe 24 h avec zone cible 70–180, bandes sommeil/activité, métriques (moyenne, temps dans la cible, pic, HbA1c estimée).
- **Comparaison de scénarios** : figer une référence, tester « dîner plus tôt », « marche après le dîner », « réduire les glucides » et mesurer les deltas.
- **Interprétabilité** : contribution de chaque facteur, dont « **Horaires des repas** » qui isole l'effet du timing circadien.

## Fondements scientifiques (avec références, pour le rapport)
- **Rythme circadien de la tolérance au glucose** : le système circadien endogène et le désalignement circadien dégradent la tolérance au glucose par des mécanismes distincts. Scheer et al., *PNAS* (2015). https://www.pnas.org/doi/10.1073/pnas.1418955112
- **Chrononutrition** : le moment des repas influence le contrôle glycémique dans le DT2. *Nutrition & Diabetes* (2020). https://www.nature.com/articles/s41387-020-0109-6
- **Travail posté / manger le jour** : manger le jour prévient le désalignement circadien et l'intolérance au glucose en travail de nuit. *Science Advances* (2021). https://www.science.org/doi/10.1126/sciadv.abg9910
- **Disruption circadienne & DT2** : revue des implications métaboliques. *Diabetologia* (2020). https://link.springer.com/article/10.1007/s00125-019-05059-6
- **Exercice → glycémie** : la contraction musculaire augmente la captation du glucose indépendamment de l'insuline (GLUT4/AMPK) et améliore la sensibilité pendant 24–48 h. Voir *Syncing Exercise with Meals and Circadian Clocks*, PMC. https://pmc.ncbi.nlm.nih.gov/articles/PMC6295221/

## Note honnête pour la présentation
Le moteur est un **modèle physiologique simplifié** : réponse post-prandiale de type gamma + phénomène de l'aube + **modulation circadienne** de la sensibilité à l'insuline + effets locaux de l'exercice. Il est calibré pour des courbes réalistes à visée **pédagogique**, pas validé cliniquement — et c'est le message de votre conclusion : les vrais défis sont la **validation**, l'**équité** et l'**interprétabilité fidèle**. Pour la version publication, la modulation circadienne serait **apprise sur données horodatées** (ShanghaiT2DM contient les horaires des repas et le CGM horodaté).
