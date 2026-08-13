#!/usr/bin/env python3
"""
Couche 2 — script d'expérience.

Enchaîne : cohorte → concepts → features → évaluation leave-one-patient-out,
pour plusieurs horizons et plusieurs modèles, toujours face à la persistance.

    python3 scripts/run_layer2.py --patients 30 --days 6 --horizons 30 60 90 120

Le même code est appelé depuis le notebook Kaggle : la logique vit ici, le
notebook ne fait qu'orchestrer et tracer.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from glucotwin.layer2.cohort import build_cohort
from glucotwin.layer2.features import build_features
from glucotwin.layer2.evaluation import lopo_evaluate, print_report
from glucotwin.layer2.models import model_zoo


def main() -> None:
    ap = argparse.ArgumentParser(description="Experience couche 2")
    ap.add_argument("--patients", type=int, default=30)
    ap.add_argument("--days", type=int, default=6)
    ap.add_argument("--horizons", type=int, nargs="+", default=[30, 60])
    ap.add_argument("--target", choices=["delta", "level"], default="delta")
    ap.add_argument("--models", nargs="+", default=["ridge", "hgb"])
    ap.add_argument("--max-eval-patients", type=int, default=None,
                    help="limite le nombre de plis (utile pour un test rapide)")
    ap.add_argument("--alpha", type=float, default=0.1,
                    help="1-alpha = couverture visee des intervalles")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None, help="fichier JSON de resultats")
    args = ap.parse_args()

    print(f"Cohorte : {args.patients} patients x {args.days} jours")
    df = build_cohort(n_patients=args.patients, days_per_patient=args.days, seed=args.seed)
    print(f"  {len(df):,} pas de 5 min | glycemie moyenne {df.glucose.mean():.0f} mg/dL "
          f"| TIR {(df.glucose.between(70,180)).mean()*100:.0f} %")

    zoo = model_zoo()
    results = {}

    for h in args.horizons:
        X, y, groups, g_now, names = build_features(
            df, horizon_min=h, target=args.target
        )
        print(f"\n=== Horizon {h} min === {X.shape[0]:,} exemples, {X.shape[1]} features")

        for name in args.models:
            rep = lopo_evaluate(
                X, y, groups, g_now, zoo[name],
                target=args.target, alpha=args.alpha,
                max_patients=args.max_eval_patients, seed=args.seed,
            )
            print_report(rep, f"[{name}] horizon {h} min")
            results[f"{name}@{h}"] = rep.summary()

    print("\n" + "=" * 66)
    print("SYNTHESE — gain sur la persistance selon l'horizon")
    print("=" * 66)
    print(f"{'modele@horizon':<18} {'MAE mod.':>9} {'MAE pers.':>10} "
          f"{'gain':>8} {'p':>10} {'gagnes':>8}")
    for k, s in results.items():
        print(f"{k:<18} {s['mae_model']:>9.2f} {s['mae_persistence']:>10.2f} "
              f"{s['gain_mae']:>+8.2f} {s['p_value']:>10.1e} "
              f"{s['patients_gagnes']:>4}/{s['n_patients']}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False)
        print(f"\nResultats ecrits dans {args.out}")


if __name__ == "__main__":
    main()
