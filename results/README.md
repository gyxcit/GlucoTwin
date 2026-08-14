# Résultats

Chaque chiffre cité dans `docs/` ou dans la présentation doit être retrouvable
ici, avec **le script qui l'a produit et sa sortie brute**. Rien dans ce dossier
n'a été recopié à la main.

| Fichier | Produit par |
|---|---|
| `cgmacros_reel.json` | `scripts/run_cgmacros.py` — 45 patients, 4 horizons, équité |
| `logs/run_cgmacros_complet.log` | la sortie intégrale du même run, en-tête de provenance compris |
| `couche3_reel_hyper.json` · `couche3_reel_hypo.json` | `scripts/run_risk.py --cgmacros` — risque calibré sur données réelles |
| `couche3_synthetique.json` | le même, sur cohorte synthétique |
| `logs/run_risk_reel.log` · `logs/run_risk_synthetique.log` | leurs sorties intégrales, courbes de fiabilité comprises |
| `ablation_reelle.json` | `scripts/run_ablation.py` — l'apport de chaque groupe de concepts |
| `logs/run_ablation_reel.log` | sa sortie intégrale |
| `calibration_reelle.json` | `scripts/run_calibration.py` — les 44 patients, paramètre par paramètre |
| `logs/run_calibration_reel.log` | sa sortie intégrale |
| `calibration_vs_prevision.json` | `scripts/run_calibrated_forecast.py` — la calibration aide-t-elle la prévision ? |
| `logs/run_calibration_prevision.log` | sa sortie intégrale |

Chaque journal commence par la commande exacte, le commit, la date et les
versions de Python, NumPy et scikit-learn.

## Reproduire

```bash
python scripts/inspect_cgmacros.py data/CGMacros            # 7 controles de recevabilite
python scripts/run_cgmacros.py data/CGMacros \
    --horizons 30 60 90 120 --out results/cgmacros_reel.json
python scripts/run_risk.py --cgmacros data/CGMacros --event hyper \
    --horizons 30 60 90 120 --reliability --out results/couche3_reel_hyper.json
python scripts/run_ablation.py --cgmacros data/CGMacros \
    --horizons 30 60 90 120 --out results/ablation_reelle.json
python scripts/run_calibration.py --cgmacros data/CGMacros --days-fit 3 \
    --out results/calibration_reelle.json
python scripts/run_calibrated_forecast.py --cgmacros data/CGMacros \
    --days-fit 3 --out results/calibration_vs_prevision.json
```

**Aucune donnée patient ici** — uniquement des agrégats. CGMacros est en
CC BY-NC-SA 4.0 et se télécharge séparément (voir `NOTICE.md`).

L'analyse rédigée est dans [`docs/07_resultats_reels.md`](../docs/07_resultats_reels.md).

Tous les runs ont désormais tourné sur **données réelles**. Les runs synthétiques
sont conservés à côté, pour la comparaison — et parce que deux d'entre eux
montrent précisément où la simulation induit en erreur.
