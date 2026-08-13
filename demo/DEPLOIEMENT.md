# GlucoTwin — les démos

Deux applications web **autonomes** : un seul fichier chacune, aucune dépendance,
aucune installation. Elles fonctionnent hors-ligne — c'est la garantie
anti-plantage le jour de la présentation.

| Fichier | Ce que c'est | Quand s'en servir |
|---|---|---|
| **`atelier.html`** | **L'atelier** — on compose la journée sur une timeline verticale et le jumeau réagit en direct | **la démo de la soutenance** |
| `index.html` | La première version, à curseurs | secours, ou si le vidéoprojecteur est petit |

## L'atelier en trente secondes

L'écran est coupé en deux. À **gauche**, la journée : une timeline 00h00 → 23h59
où l'on clique pour poser un repas ou une activité, une carte patient au centre
avec un personnage qui **fait le geste de l'activité en cours**, et des arêtes
pondérées — comme un schéma de réseau — qui portent les flux métaboliques vers la
droite. À **droite**, ce que le corps fait de tout ça : glycémie sur 24 h, état
métabolique instantané, comparateur d'interventions, états de risque.

Ce qu'il faut savoir montrer :

- **cliquer sur la timeline** → choisir parmi les 78 activités du catalogue
  (recherche, filtres par famille, badge MET coloré) ou un des 4 types de repas ;
- **glisser un bloc** pour le déplacer dans la journée, **glisser les bords des
  bandes de sommeil** pour changer lever et coucher ;
- **▶ Dérouler la journée** avec le sélecteur de vitesse **×0,5 à ×8** : le
  personnage marche, pédale, nage, bêche, et sa cadence suit l'intensité (METs) ;
- **📌 Figer** une journée de référence, la modifier, et lire les écarts chiffrés.

Raccourcis : `espace` lecture/pause · `+` `−` vitesse · `←` `→` déplacer l'instant
· `Échap` fermer.

## Lancer

Double-cliquez sur `atelier.html`. C'est tout.

## Déployer une URL publique (2 min)

**Netlify Drop** — https://app.netlify.com/drop → glissez le dossier `demo/` → URL immédiate.
**Vercel** — https://vercel.com → Add New › Project → importez le dossier.
**GitHub Pages** — Settings › Pages › branche `main`, dossier `/demo`.

## Ce que la démo montre

L'application affiche **les quatre couches de l'architecture** à l'écran :

| Couche | Ce qu'on voit |
|---|---|
| **0** — Emploi du temps | patient, repas (heure, glucides, fibres, IG), activités choisies dans un catalogue de 78 |
| **1** — État métabolique | 8 concepts physiologiques mis à jour **au survol de la courbe** |
| **2** — Glycémie prédite | 24 h au pas de 5 min, zone cible, bandes sommeil et activité |
| **3** — États de risque | probabilités, tendance, et une explication **traçable** jusqu'au mécanisme |

Plus un **comparateur d'interventions** qui simule six journées alternatives et les classe par effet sur le pic glycémique.

## Le moment fort de la présentation

Le comparateur. Il produit un classement mesuré :

| Intervention | Effet sur le pic |
|---|---:|
| Réduire les glucides de 40 % | −46 mg/dL |
| Passer tous les repas en IG bas | −43 mg/dL |
| Marche de 30 min après chaque repas | −16 mg/dL |
| 45 min de vélo en fin de journée | −14 mg/dL |
| Avancer le dernier repas de 3 h | −4 mg/dL |
| Dormir une heure de plus | 0 mg/dL |

C'est ce qu'un jumeau numérique permet et qu'une simple mesure ne permet pas : **comparer des futurs qui n'ont pas eu lieu**. Et le résultat est honnête — il contredit l'idée reçue selon laquelle l'heure du repas pèserait autant que sa composition.

## Fondements physiologiques

Le moteur est un **port fidèle en JavaScript** des couches 0-1 Python (`glucotwin.day_concepts`), donc cohérent avec le code scientifique du dépôt :

- valeurs MET du **2024 Adult Compendium** (78 activités)
- oxydation des substrats par les **équations de Frayn (1983)**
- cinétique d'absorption gamma, modulée par l'index glycémique et les fibres
- **rythme circadien** de la sensibilité à l'insuline — un même repas de 65 g fait **+65 mg/dL à 8h contre +87 mg/dL à 22h**
- **phénomène de l'aube** réglable, ~+19 mg/dL avant le réveil à intensité 1
- production hépatique freinée par l'insuline, stimulée à l'effort et à l'aube

## Les gestes du personnage

Chaque code d'activité du catalogue est relié à un geste (table `ACT2GEST` dans
le fichier). Vingt gestes couvrent les 78 activités :

| Famille | Gestes | Accessoires |
|---|---|---|
| Repos, bureau | assis, clavier, conduite, debout, sommeil | chaise, bureau, volant, `zzz` |
| Repas | repas | table, assiette, fourchette |
| Déplacement | marche, randonnée, course, vélo | sac à dos, bâton, vélo |
| Sport | nage, ballon, danse, coup de pied, saut | eau, ballon, notes |
| Forme | yoga, musculation | tapis, haltères |
| Maison, jardin, métier | bêchage, ménage, cuisine, port de charges | pelle, balai, poêle, sacs |

La **cadence** du geste est calculée à partir des METs de l'activité — course à
0,25 s la foulée, marche lente à 0,64 s, yoga à 1,6 s — puis divisée par la
vitesse de lecture. Le personnage et les chiffres de droite sont pilotés par la
même grandeur physiologique : ce n'est pas une illustration posée à côté du
modèle, c'est le modèle qui bouge.

## Limite à énoncer

Modèle physiologique **simplifié, non validé cliniquement**, à visée pédagogique. Il ne recommande aucune dose ni traitement. Pour la version scientifique, la couche 2 est apprise sur données réelles (voir `notebooks/`).
