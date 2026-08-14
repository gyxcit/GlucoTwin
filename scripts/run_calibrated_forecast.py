#!/usr/bin/env python3
"""
La calibration patient améliore-t-elle la **prévision** ?

Le problème inverse a montré qu'ajuster les paramètres physiologiques par
patient améliore le *modèle direct*. C'est une autre question que celle qui
compte pour l'architecture : est-ce que des concepts calculés avec ces
paramètres améliorent le *modèle appris* de la couche 2 ?

    python scripts/run_calibrated_forecast.py --pickle table.pkl --days-fit 3

## Le protocole, et pourquoi il est honnête

Les θ sont ajustés sur la glycémie du patient : les concepts calibrés en portent
la trace. Évaluer sur les journées d'ajustement serait donc une fuite pure. Le
protocole reproduit le **déploiement réel** :

    le jumeau observe la personne K jours, puis la sert.

Les K premières journées calibrent et **sortent de l'évaluation**. Les deux bras
— concepts d'origine et concepts calibrés — sont évalués sur **exactement les
mêmes journées, les mêmes plis, la même graine**. Seuls les concepts changent.

Un point de méthode subsiste et il est énoncé : dans le bras calibré, les
concepts du patient de test encodent sa physiologie propre, apprise de ses
propres journées d'observation. C'est légitime en déploiement — c'est même tout
l'intérêt d'un jumeau — mais ce n'est pas comparable à un modèle qui n'aurait
jamais vu le patient. La comparaison mesure la valeur de la **personnalisation**,
pas la généralisation à un inconnu.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from glucotwin.calibration import apply_calibration, calibrate_cohort
from glucotwin.layer2.evaluation import lopo_evaluate
from glucotwin.layer2.features import build_features
from glucotwin.layer2.models import model_zoo


def _run(df, horizon, seed, label):
    X, y, g, gn, _ = build_features(df, horizon_min=horizon)
    rep = lopo_evaluate(X, y, g, gn, model_zoo()["hgb"], seed=seed)
    s = rep.summary()
    c = rep.clinical()
    s["sens_hyper"] = c["hyper"]["sensibilite"]
    s["sens_hypo"] = c["hypo"]["sensibilite"]
    s["n_exemples"] = int(X.shape[0])
    print(f"  [{label:<9}] h={horizon:>3} min | MAE {s['mae_model']:6.2f} "
          f"| pers. {s['mae_persistence']:6.2f} | gain {s['gain_mae']:+5.2f} "
          f"| p {s['p_value']:.1e} | {s['patients_gagnes']}/{s['n_patients']}",
          flush=True)
    return s, rep


def main() -> int:
    ap = argparse.ArgumentParser(description="Calibration -> prevision")
    ap.add_argument("--pickle", default=None)
    ap.add_argument("--cgmacros", default=None)
    ap.add_argument("--days-fit", type=int, default=3)
    ap.add_argument("--horizons", type=int, nargs="+", default=[30, 60])
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.pickle:
        import pandas as pd
        df = pd.read_pickle(args.pickle)
    elif args.cgmacros:
        from glucotwin.data.cgmacros import build_cohort_from_cgmacros
        df = build_cohort_from_cgmacros(args.cgmacros, verbose=False)
    else:
        from glucotwin.layer2.cohort import build_cohort
        df = build_cohort(n_patients=20, days_per_patient=8, seed=7)

    print("=" * 78)
    print("LA CALIBRATION PATIENT AMELIORE-T-ELLE LA PREVISION ?")
    print(f"{len(df):,} pas | {df.patient.nunique()} patients | "
          f"{args.days_fit} journees d'observation, le reste evalue")
    print("=" * 78)

    print("\n1. Ajustement des parametres, patient par patient")
    res = calibrate_cohort(df, n_days_fit=args.days_fit, verbose=False)
    thetas = {r.patient: r.theta for r in res}
    print(f"   {len(thetas)} patients calibres")

    # Les deux bras, sur EXACTEMENT les memes journees.
    base = df[df["day"] >= args.days_fit].copy()
    cal = apply_calibration(df, thetas, days_from=args.days_fit)
    assert len(base) == len(cal), "les deux bras doivent porter sur les memes pas"

    print("\n2. Couche 2 sur les journees posterieures a l'observation")
    out = {}
    for h in args.horizons:
        s_base, rep_base = _run(base, h, args.seed, "origine")
        s_cal, rep_cal = _run(cal, h, args.seed, "calibre")

        # Test APPARIE entre les deux bras : memes patients, memes plis, meme
        # graine. Sans lui, un ecart de 0,5 mg/dL n'est qu'une impression.
        pb = {f.patient: f.mae_model for f in rep_base.folds}
        pc = {f.patient: f.mae_model for f in rep_cal.folds}
        communs = [k for k in pb if k in pc]
        a = np.array([pb[k] for k in communs])
        b = np.array([pc[k] for k in communs])
        d = a - b                                    # >0 : le calibre gagne
        n = len(d)
        se = d.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
        try:
            from scipy.stats import wilcoxon
            pval = float(wilcoxon(a, b).pvalue)
        except Exception:
            pval = float("nan")
        paire = {"n_patients": n, "gain_moyen": float(d.mean()),
                 "ic95": (float(d.mean() - 1.96 * se), float(d.mean() + 1.96 * se)),
                 "p_value": pval,
                 "patients_ameliores": int((d > 0).sum())}
        lo, hi = paire["ic95"]
        print(f"      -> apparie : {paire['gain_moyen']:+.2f} mg/dL "
              f"[IC95 {lo:+.2f}, {hi:+.2f}]  p={pval:.3f}  "
              f"{paire['patients_ameliores']}/{n} patients", flush=True)
        out[h] = {"origine": s_base, "calibre": s_cal, "apparie": paire}

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    print(f"{'horizon':>8}{'MAE origine':>13}{'MAE calibre':>13}{'ecart':>8}"
          f"{'p apparie':>11}{'gagnes':>9}{'hyper o.':>10}{'hyper c.':>10}")
    verdicts = []
    for h, d in out.items():
        o, c, pa = d["origine"], d["calibre"], d["apparie"]
        delta = o["mae_model"] - c["mae_model"]
        verdicts.append(delta)
        print(f"{h:>6} min{o['mae_model']:>13.2f}{c['mae_model']:>13.2f}"
              f"{delta:>+8.2f}{pa['p_value']:>11.3f}"
              f"{str(pa['patients_ameliores']) + '/' + str(pa['n_patients']):>9}"
              f"{o['sens_hyper'] * 100:>9.1f}%{c['sens_hyper'] * 100:>9.1f}%")

    m = float(np.mean(verdicts))
    signif = [h for h, d in out.items() if d["apparie"]["p_value"] < 0.05]
    print()
    if not signif:
        print("  VERDICT : aucun ecart n'atteint le seuil de significativite au")
        print("  test apparie. Avec ces patients, **la calibration n'ameliore pas")
        print("  la prevision de facon demontrable** — quel que soit le signe de")
        print(f"  l'ecart moyen ({m:+.2f} mg/dL).")
        print()
        pente = [out[h]["apparie"]["gain_moyen"] for h in sorted(out)]
        if len(pente) > 1 and pente[-1] > pente[0]:
            print("  Une tendance, a verifier sur plus de patients : l'ecart croit")
            print("  avec l'horizon (" + " -> ".join(f"{v:+.2f}" for v in pente) +
                  " mg/dL). C'est physiologiquement")
            print("  coherent — a court terme l'historique glycemique domine, a long")
            print("  terme la physiologie reprend du poids — mais ce n'est pas")
            print("  demontre.")
        print()
        print("  Lecture : le modele appris reconstruit deja, depuis l'historique")
        print("  glycemique, l'essentiel de ce que les gains patient encodent. La")
        print("  calibration reste utile la ou elle a ete validee — le modele")
        print("  DIRECT — pas au-dela.")
    elif m > 0:
        print(f"  VERDICT : la calibration ameliore la prevision, {m:+.2f} mg/dL en")
        print(f"  moyenne, significatif aux horizons "
              f"{', '.join(str(h) + ' min' for h in signif)}.")
    else:
        print(f"  VERDICT : la calibration DEGRADE la prevision ({m:+.2f} mg/dL),")
        print(f"  significativement aux horizons "
              f"{', '.join(str(h) + ' min' for h in signif)}.")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({str(k): v for k, v in out.items()}, fh,
                      indent=2, ensure_ascii=False, default=float)
        print(f"\nResultats ecrits dans {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
