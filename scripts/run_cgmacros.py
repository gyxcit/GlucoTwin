#!/usr/bin/env python3
"""
L'expérience sur **données réelles** — CGMacros, 45 participants.

Même protocole que `run_layer2.py`, même code d'évaluation, mêmes garde-fous :
leave-one-patient-out, baseline de persistance, intervalles conformes, métriques
cliniques. Seule la source change — et c'est tout l'intérêt : ce qui diffère
dans les résultats vient des données, pas du harnais.

S'y ajoute l'analyse d'équité par groupe glycémique, avec son test de
permutation : avec 14 à 16 patients par groupe, un écart apparent doit être
confronté à ce que le hasard produit avant d'être annoncé.

    python scripts/run_cgmacros.py data/CGMacros --horizons 30 60 90 120

Le protocole est gelé : on n'ajuste rien après avoir vu les résultats. C'est ce
qui rend la comparaison au run synthétique honnête.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from glucotwin.data.cgmacros import build_cohort_from_cgmacros
from glucotwin.layer2.evaluation import lopo_evaluate, print_report
from glucotwin.layer2.fairness import (
    gap_permutation_test,
    print_fairness,
    subgroup_report,
)
from glucotwin.layer2.features import build_features
from glucotwin.layer2.models import model_zoo

#: Repère publié sur CGMacros à 30 min — le point de comparaison honnête.
BENCHMARK_30 = {"modele": 13.11, "persistance": 13.39}


def main() -> int:
    ap = argparse.ArgumentParser(description="Couche 2 sur donnees reelles")
    ap.add_argument("root", help="dossier CGMacros decompresse")
    ap.add_argument("--horizons", type=int, nargs="+", default=[30, 60, 90, 120])
    ap.add_argument("--models", nargs="+", default=["hgb"])
    ap.add_argument("--target", choices=["delta", "level"], default="delta")
    ap.add_argument("--min-coverage", type=float, default=0.8)
    ap.add_argument("--max-participants", type=int, default=None)
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None, help="fichier JSON de resultats")
    args = ap.parse_args()

    print("=" * 70)
    print("CHARGEMENT — CGMacros")
    print("=" * 70)
    df = build_cohort_from_cgmacros(
        args.root, min_coverage=args.min_coverage,
        max_participants=args.max_participants,
    )
    n_days = df.groupby("patient").day.nunique()
    print(f"\n{len(df):,} pas de 5 min | {df.patient.nunique()} patients "
          f"| {n_days.sum()} journees (mediane {n_days.median():.0f}/patient)")
    print(f"glycemie moyenne {df.glucose.mean():.0f} mg/dL "
          f"| TIR {(df.glucose.between(70, 180)).mean() * 100:.0f} % "
          f"| hypo {(df.glucose < 70).mean() * 100:.1f} % "
          f"| hyper {(df.glucose > 180).mean() * 100:.1f} %")

    groups_map = {}
    if "group" in df.columns:
        groups_map = (df.groupby("patient").group.first().dropna().to_dict())
        if groups_map:
            counts = df.groupby("group").patient.nunique()
            print("groupes : " + " · ".join(f"{k} {v}" for k, v in counts.items()))

    zoo = model_zoo()
    results, reports = {}, {}

    for h in args.horizons:
        X, y, groups, g_now, names = build_features(df, horizon_min=h,
                                                    target=args.target)
        print(f"\n=== Horizon {h} min === {X.shape[0]:,} exemples, "
              f"{X.shape[1]} features")
        for name in args.models:
            rep = lopo_evaluate(
                X, y, groups, g_now, zoo[name],
                target=args.target, alpha=args.alpha, seed=args.seed,
            )
            print_report(rep, f"[{name}] horizon {h} min — DONNEES REELLES")
            results[f"{name}@{h}"] = rep.summary()
            reports[f"{name}@{h}"] = rep

            if groups_map:
                fr = subgroup_report(rep, groups_map)
                perm = gap_permutation_test(rep, groups_map, seed=args.seed)
                print_fairness(fr, perm, f"  Equite — [{name}] horizon {h} min")
                results[f"{name}@{h}"]["equite"] = {
                    k: {"n": v.n_patients, "mae": v.mae_model,
                        "gain": v.gain, "sens_hyper": v.sensibilite_hyper}
                    for k, v in fr.items()
                }
                results[f"{name}@{h}"]["equite_permutation"] = {
                    "ecart": perm["observed_gap"], "p": perm["p_value"]}

    # ------------------------------------------------------------------ #
    print("\n" + "=" * 70)
    print("SYNTHESE — donnees reelles")
    print("=" * 70)
    print(f"{'modele@horizon':<18} {'MAE mod.':>9} {'MAE pers.':>10} "
          f"{'gain':>8} {'p':>10} {'gagnes':>8}")
    for k, s in results.items():
        print(f"{k:<18} {s['mae_model']:>9.2f} {s['mae_persistence']:>10.2f} "
              f"{s['gain_mae']:>+8.2f} {s['p_value']:>10.1e} "
              f"{s['patients_gagnes']:>4}/{s['n_patients']}")

    # Confrontation au repère publié : la seule facon de savoir si notre
    # pipeline est dans les clous, independamment de nos propres chiffres.
    k30 = next((k for k in results if k.endswith("@30")), None)
    if k30:
        s = results[k30]
        print(f"\nRepere publie sur CGMacros a 30 min : "
              f"modele {BENCHMARK_30['modele']:.2f} / "
              f"persistance {BENCHMARK_30['persistance']:.2f} mg/dL")
        print(f"Nous                                : "
              f"modele {s['mae_model']:.2f} / "
              f"persistance {s['mae_persistence']:.2f} mg/dL")
        ecart = abs(s["mae_persistence"] - BENCHMARK_30["persistance"])
        if ecart < 3.0:
            print("  -> la persistance retombe sur le repere : pipeline coherent.")
        else:
            print(f"  -> ecart de {ecart:.1f} mg/dL sur la PERSISTANCE, qui ne "
                  "depend d'aucun modele.\n     Chercher la cause dans le "
                  "chargement (echantillonnage, unites, journees retenues).")

    print("\nRappel de lecture : la persistance est redoutable a 30 min. "
          "Un gain\nfaible a court horizon n'est pas un echec, c'est le "
          "resultat attendu —\nce qui compte est la pente avec l'horizon et "
          "la detection des evenements.")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False, default=float)
        print(f"\nResultats ecrits dans {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
