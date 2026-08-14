#!/usr/bin/env python3
"""
Couche 3 — le run de référence sur les probabilités de risque.

Répond à une question précise : **la probabilité calibrée survit-elle à
l'effondrement de la détection par seuil ?** Le tableau produit met les deux
côte à côte, horizon par horizon.

    python scripts/run_risk.py --patients 30 --days 6            # synthetique
    python scripts/run_risk.py --cgmacros data/CGMacros          # reel

Comme partout ailleurs : leave-one-patient-out, et la **climatologie** comme
baseline — un modèle de risque qui ne bat pas « ça arrive x % du temps »
n'apporte rien.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from glucotwin.layer2.evaluation import HYPER_THRESHOLD, HYPO_THRESHOLD
from glucotwin.layer2.features import build_features
from glucotwin.layer2.models import model_zoo
from glucotwin.layer2.risk import (
    lopo_risk_evaluate,
    print_reliability,
    print_risk_report,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Couche 3 — risque calibre")
    ap.add_argument("--cgmacros", default=None,
                    help="dossier CGMacros ; sinon cohorte synthetique")
    ap.add_argument("--patients", type=int, default=30)
    ap.add_argument("--days", type=int, default=6)
    ap.add_argument("--horizons", type=int, nargs="+", default=[30, 60, 90, 120])
    ap.add_argument("--event", choices=["hyper", "hypo"], default="hyper")
    ap.add_argument("--reliability", action="store_true",
                    help="affiche la courbe de fiabilite de chaque horizon")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.cgmacros:
        from glucotwin.data.cgmacros import build_cohort_from_cgmacros
        df = build_cohort_from_cgmacros(args.cgmacros, verbose=False)
        source = f"CGMacros reel ({args.cgmacros})"
    else:
        from glucotwin.layer2.cohort import build_cohort
        df = build_cohort(n_patients=args.patients,
                          days_per_patient=args.days, seed=7)
        source = f"cohorte synthetique ({args.patients} patients x {args.days} jours)"

    threshold, above, name = (
        (HYPER_THRESHOLD, True, "hyperglycemie") if args.event == "hyper"
        else (HYPO_THRESHOLD, False, "hypoglycemie")
    )
    base = ((df.glucose > threshold) if above else (df.glucose < threshold)).mean()
    print("=" * 70)
    print(f"COUCHE 3 — {name} | {source}")
    print(f"{len(df):,} pas | {df.patient.nunique()} patients | "
          f"taux de base {base * 100:.1f} %")
    print("=" * 70)

    out = {}
    for h in args.horizons:
        X, y, g, gn, _ = build_features(df, horizon_min=h)
        r = lopo_risk_evaluate(X, y, g, gn, model_zoo()["hgb"],
                               threshold=threshold, above=above,
                               event=name, seed=args.seed)
        print_risk_report(r, f"[hgb] horizon {h} min")
        if args.reliability:
            print_reliability(r, n_bins=8)
        out[h] = r.summary()

    print("\n" + "=" * 70)
    print("SYNTHESE — le seuil s'effondre, et le classement ?")
    print("=" * 70)
    print(f"{'horizon':>8}{'sens. seuil':>13}{'AUROC/pat':>11}{'IC95':>18}"
          f"{'AP':>8}{'base':>8}{'gain clim.':>12}{'ECE':>7}")
    for h, s in out.items():
        lo, hi = s["auroc_ic95"]
        print(f"{h:>6} min{s['sensibilite_seuil'] * 100:>12.1f}%"
              f"{s['auroc_par_patient']:>11.3f}  [{lo:.3f}, {hi:.3f}]"
              f"{s['average_precision']:>8.3f}{s['taux_de_base']:>8.3f}"
              f"{s['brier_skill']:>+12.3f}{s['ece']:>7.3f}")

    aur = [s["auroc_par_patient"] for s in out.values()]
    skl = [s["brier_skill"] for s in out.values()]
    print("\nLecture :")
    if len(aur) < 2:
        print("  Un seul horizon : rien a conclure sur la degradation. "
              "Relancer avec\n  plusieurs horizons pour voir la pente.")
    elif min(aur) > 0.55 and min(skl) < 0:
        print("  Recuperation PARTIELLE. Le classement du risque survit a "
              "l'effondrement du\n  seuil (AUROC au-dessus du hasard partout), "
              "mais la quantification non :\n  le gain sur la climatologie "
              "devient negatif. A long horizon, le jumeau\n  peut ORDONNER le "
              "risque, plus le CHIFFRER.")
    elif min(skl) >= 0:
        print("  Recuperation COMPLETE : la probabilite reste informative ET "
              "calibree\n  a tous les horizons testes.")
    else:
        print("  Pas de recuperation : la probabilite perd l'information en "
              "meme temps\n  que le seuil.")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False, default=float)
        print(f"\nResultats ecrits dans {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
