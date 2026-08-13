# Publier GlucoTwin sur GitHub — 3 minutes

Le dépôt est **déjà initialisé** : 8 commits, arbre propre, 25 tests qui passent.
Il ne manque que votre compte.

## 1. Créer le dépôt vide sur GitHub

Allez sur **https://github.com/new** et renseignez :

- **Repository name** : `GlucoTwin`
- **Description** : *Jumeau numérique du patient diabétique de type 2 — goulot métabolique interprétable et prévision glycémique évaluée honnêtement*
- **Public**
- ⚠️ **Ne cochez rien** — ni README, ni .gitignore, ni licence. Ils existent déjà.

## 2. Pousser

Dans le dossier décompressé :

```bash
git remote add origin https://github.com/VOTRE-COMPTE/GlucoTwin.git
git push -u origin main
```

C'est tout. L'intégration continue se déclenche automatiquement.

> Si Git demande un mot de passe : GitHub n'accepte plus les mots de passe.
> Créez un **jeton d'accès personnel** (Settings › Developer settings ›
> Personal access tokens › Fine-grained tokens, portée `Contents: read and write`)
> et utilisez-le comme mot de passe.

## 3. Vérifier

```bash
pip install -e ".[dev]"
pytest -q                      # 25 tests
python scripts/run_layer2.py --patients 12 --days 4 --horizons 30 60
```

## 4. Ensuite

- **Déployer la démo** : glissez `demo/index.html` sur https://app.netlify.com/drop
- **Entraîner sur Kaggle** : importez `notebooks/couche2_prevision.ipynb`, décommentez la cellule `git clone` en pointant sur votre dépôt
- **Inviter l'équipe** : Settings › Collaborators
- **Prochain jalon** : l'adaptateur CGMacros (voir la feuille de route du README)

---

## L'historique des commits

Il raconte honnêtement d'où vient quoi — c'est ce qu'un relecteur ou un recruteur regardera :

```
chore: initialiser le depot (MIT, attribution DiabetesTwin-AI)
feat(couche1): moteur metabolique interpretable
feat(couches0-1): emploi du temps -> flux de concepts metaboliques
feat(couche2): prevision glycemique et evaluation honnete
feat: notebook d'entrainement et demonstration web
docs: revue de litterature, architecture et plans
test: 25 tests et integration continue
chore: preserver l'arborescence data/ sans committer les donnees
```

Le premier commit crédite explicitement le dépôt de Jean, conformément à la licence MIT.
