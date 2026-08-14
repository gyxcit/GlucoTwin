#!/usr/bin/env python3
"""
Calibration de la couche 1 par patient — le run de référence.

    python scripts/run_calibration.py --cgmacros data/CGMacros --days-fit 3
    python scripts/run_calibration.py --days-fit 3            # synthetique

Protocole : les `--days-fit` premières journées de chaque patient servent à
ajuster ses cinq paramètres physiologiques ; **toutes les suivantes** servent à
tester. Trois comparaisons, dans l'ordre où elles doivent tomber :

1. contre les **paramètres de population** (médiane des autres patients) —
   calibrer sert-il, ou un patient moyen suffit-il ?
2. contre la **persistance** — le modèle direct vaut-il mieux que « rien ne
   bouge » ?
3. par **sous-groupe** — la calibration profite-t-elle à tout le monde ?
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from glucotwin.calibration import calibrate_cohort, print_summary, summarize


def main() -> int:
    ap = argparse.ArgumentParser(description="Calibration patient de la couche 1")
    ap.add_argument("--cgmacros", default=None, help="dossier CGMacros decompresse")
    ap.add_argument("--pickle", default=None, help="table de concepts deja construite")
    ap.add_argument("--patients", type=int, default=20, help="cohorte synthetique")
    ap.add_argument("--days", type=int, default=8, help="cohorte synthetique")
    ap.add_argument("--days-fit", type=int, default=3)
    ap.add_argument("--min-days", type=int, default=5)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.pickle:
        import pandas as pd
        df = pd.read_pickle(args.pickle)
        source = f"table pre-construite ({args.pickle})"
    elif args.cgmacros:
        from glucotwin.data.cgmacros import build_cohort_from_cgmacros
        df = build_cohort_from_cgmacros(args.cgmacros, verbose=False)
        source = "CGMacros reel"
    else:
        from glucotwin.layer2.cohort import build_cohort
        df = build_cohort(n_patients=args.patients, days_per_patient=args.days, seed=7)
        source = f"cohorte synthetique ({args.patients} patients)"

    print("=" * 70)
    print(f"CALIBRATION DE LA COUCHE 1 — {source}")
    print(f"{len(df):,} pas | {df.patient.nunique()} patients | "
          f"{args.days_fit} journees d'ajustement, le reste en test")
    print("=" * 70)

    res = calibrate_cohort(df, n_days_fit=args.days_fit, min_days=args.min_days)
    s = summarize(res)
    print_summary(s, "RESULTAT")

    # --- par sous-groupe, si l'information existe ---
    if "group" in df.columns:
        groups = df.groupby("patient").group.first().dropna().to_dict()
        print("\n  Par sous-groupe")
        print(f"    {'groupe':<14}{'n':>4}{'calibre':>10}{'population':>12}{'gain':>9}")
        for g in sorted(set(groups.values())):
            sel = [r for r in res if groups.get(r.patient) == g]
            if len(sel) < 3:
                continue
            cal = np.mean([r.rmse_test for r in sel])
            pop = np.mean([r.rmse_test_population for r in sel])
            print(f"    {g:<14}{len(sel):>4}{cal:>10.2f}{pop:>12.2f}{pop - cal:>+9.2f}")

    # --- ce que les parametres racontent ---
    print("\n  Dispersion des parametres ajustes (le patient moyen n'existe pas)")
    th = np.array([r.theta for r in res])
    from glucotwin.calibration import PARAM_NAMES
    print(f"    {'parametre':<12}{'p10':>9}{'mediane':>10}{'p90':>9}{'rapport p90/p10':>17}")
    for j, nom in enumerate(PARAM_NAMES):
        p10, med, p90 = np.percentile(th[:, j], [10, 50, 90])
        print(f"    {nom:<12}{p10:>9.3f}{med:>10.3f}{p90:>9.3f}{p90 / max(p10, 1e-9):>17.1f}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"resume": s, "patients": [r.as_dict() for r in res]},
                      fh, indent=2, ensure_ascii=False, default=float)
        print(f"\nResultats ecrits dans {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
