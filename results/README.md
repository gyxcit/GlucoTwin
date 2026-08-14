# Résultats

Chaque chiffre cité dans `docs/` ou dans la présentation doit être retrouvable
ici, avec **le script qui l'a produit et sa sortie brute**. Rien dans ce dossier
n'a été recopié à la main.

| Fichier | Produit par |
|---|---|
| `cgmacros_reel.json` | `scripts/run_cgmacros.py` — 45 patients, 4 horizons, équité |
| `logs/run_cgmacros_complet.log` | la sortie intégrale du même run, en-tête de provenance compris |
| `couche3_synthetique.json` | `scripts/run_risk.py` — probabilités de risque |
| `logs/run_risk_synthetique.log` | sa sortie intégrale, courbes de fiabilité comprises |

Chaque journal commence par la commande exacte, le commit, la date et les
versions de Python, NumPy et scikit-learn.

## Reproduire

```bash
python scripts/inspect_cgmacros.py data/CGMacros            # 7 controles de recevabilite
python scripts/run_cgmacros.py data/CGMacros \
    --horizons 30 60 90 120 --out results/cgmacros_reel.json
python scripts/run_risk.py --patients 30 --days 6 \
    --horizons 30 60 90 120 --reliability --out results/couche3_synthetique.json
```

**Aucune donnée patient ici** — uniquement des agrégats. CGMacros est en
CC BY-NC-SA 4.0 et se télécharge séparément (voir `NOTICE.md`).

L'analyse rédigée est dans [`docs/07_resultats_reels.md`](../docs/07_resultats_reels.md).

> **État de la couche 3 :** elle n'a tourné que sur cohorte **synthétique**.
> Le script accepte `--cgmacros data/CGMacros` — c'est le prochain run à faire.
