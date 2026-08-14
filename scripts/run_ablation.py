#!/usr/bin/env python3
"""
Ablation des concepts — **la couche 1 sert-elle à quelque chose ?**

C'est la question la plus embarrassante qu'on puisse poser à une architecture à
goulot conceptuel, et elle mérite une réponse mesurée plutôt qu'une conviction.
Le modèle reçoit déjà l'historique glycémique du patient : ses vingt dernières
minutes, sa vitesse, son accélération. Si cet historique suffit, alors toute la
physiologie de la couche 1 est un ornement coûteux.

    python scripts/run_ablation.py --cgmacros data/CGMacros --horizons 30 60 90

## Pourquoi refaire l'ablation sur données réelles

Celle du dépôt tournait sur cohorte synthétique, où **la glycémie est engendrée
à partir des concepts fournis au modèle**. Y mesurer l'apport des concepts revient
à mesurer la circularité de la simulation : ils *doivent* aider, par construction.
Sur données réelles, cette circularité disparaît.

## Les quatre bras, emboîtés

| bras | ce que le modèle voit en plus |
|---|---|
| `historique` | rien de la couche 1 — glycémie passée, poids, heure du jour |
| `+ repas` | glucides en digestion, débit d'apparition |
| `+ activité` | METs, oxydation, captation, déficit glycogénique, sommeil |
| `+ modulateurs` | circadien, sensibilité insulinique, aube, foie, flux net |

Chaque bras est comparé au **précédent**, par un test apparié patient par
patient — la seule façon de dire si *ce groupe-là* apporte quelque chose, et pas
seulement si l'ensemble aide.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from glucotwin.layer2.evaluation import lopo_evaluate
from glucotwin.layer2.features import build_features
from glucotwin.layer2.models import model_zoo

#: Groupes emboîtés, dans l'ordre où on les ajoute.
GROUPES = [
    ("historique", []),
    ("+ repas", ["cob_g", "carb_ra_g_min"]),
    ("+ activite", ["asleep", "met_now", "energy_rate_kcal_min",
                    "cho_ox_rate_g_min", "glucose_uptake_mg_min",
                    "glycogen_deficit_g"]),
    ("+ modulateurs", ["circadian_factor", "insulin_sensitivity_index",
                       "dawn_factor", "hepatic_output_mg_min",
                       "net_glucose_flux_mg_min"]),
]


def _paired(a_folds, b_folds):
    """Test apparié entre deux bras — mêmes patients, mêmes plis."""
    a = {f.patient: f.mae_model for f in a_folds}
    b = {f.patient: f.mae_model for f in b_folds}
    keys = [k for k in a if k in b]
    x, y = np.array([a[k] for k in keys]), np.array([b[k] for k in keys])
    d = x - y                                   # >0 : le bras b (plus riche) gagne
    n = len(d)
    se = d.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    try:
        from scipy.stats import wilcoxon
        p = float(wilcoxon(x, y).pvalue)
    except Exception:
        p = float("nan")
    return {"gain": float(d.mean()),
            "ic95": (float(d.mean() - 1.96 * se), float(d.mean() + 1.96 * se)),
            "p_value": p, "patients_ameliores": int((d > 0).sum()), "n": n}


def main() -> int:
    ap = argparse.ArgumentParser(description="Ablation des concepts")
    ap.add_argument("--cgmacros", default=None)
    ap.add_argument("--pickle", default=None)
    ap.add_argument("--horizons", type=int, nargs="+", default=[30, 60, 90])
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.pickle:
        import pandas as pd
        df = pd.read_pickle(args.pickle)
        source = "table pre-construite"
    elif args.cgmacros:
        from glucotwin.data.cgmacros import build_cohort_from_cgmacros
        df = build_cohort_from_cgmacros(args.cgmacros, verbose=False)
        source = "CGMacros reel"
    else:
        from glucotwin.layer2.cohort import build_cohort
        df = build_cohort(n_patients=20, days_per_patient=8, seed=7)
        source = "cohorte synthetique (ATTENTION : circulaire)"

    print("=" * 78)
    print(f"ABLATION DES CONCEPTS — {source}")
    print(f"{len(df):,} pas | {df.patient.nunique()} patients")
    print("=" * 78)

    out = {}
    for h in args.horizons:
        print(f"\n=== Horizon {h} min ===")
        cols, reports, resume = [], [], []
        for nom, ajout in GROUPES:
            cols = cols + ajout
            X, y, g, gn, names = build_features(df, horizon_min=h, concept_cols=cols)
            rep = lopo_evaluate(X, y, g, gn, model_zoo()["hgb"], seed=args.seed)
            s = rep.summary()
            c = rep.clinical()
            s["sens_hyper"] = c["hyper"]["sensibilite"]
            s["n_features"] = int(X.shape[1])
            s["n_concepts"] = len(cols)
            reports.append(rep)
            resume.append((nom, s))
            print(f"  {nom:<15} {s['n_concepts']:>2} concepts, "
                  f"{s['n_features']:>2} features | MAE {s['mae_model']:6.2f} "
                  f"| pers. {s['mae_persistence']:6.2f} "
                  f"| hyper {s['sens_hyper'] * 100:4.1f} %", flush=True)

        print(f"\n  Apport de chaque groupe (test apparie contre le bras precedent)")
        print(f"    {'groupe ajoute':<16}{'gain MAE':>10}{'IC95':>20}"
              f"{'p':>9}{'patients':>10}")
        pas_a_pas = []
        for i in range(1, len(resume)):
            pr = _paired(reports[i - 1].folds, reports[i].folds)
            lo, hi = pr["ic95"]
            etoile = " *" if pr["p_value"] < 0.05 else ""
            print(f"    {resume[i][0]:<16}{pr['gain']:>+10.2f}"
                  f"   [{lo:+.2f}, {hi:+.2f}]{pr['p_value']:>9.3f}"
                  f"{str(pr['patients_ameliores']) + '/' + str(pr['n']):>10}{etoile}")
            pas_a_pas.append({"groupe": resume[i][0], **pr})

        total = _paired(reports[0].folds, reports[-1].folds)
        lo, hi = total["ic95"]
        print(f"    {'TOTAL couche 1':<16}{total['gain']:>+10.2f}"
              f"   [{lo:+.2f}, {hi:+.2f}]{total['p_value']:>9.3f}"
              f"{str(total['patients_ameliores']) + '/' + str(total['n']):>10}"
              f"{' *' if total['p_value'] < 0.05 else ''}")

        out[h] = {"bras": {n: s for n, s in resume},
                  "pas_a_pas": pas_a_pas, "total": total}

    # ------------------------------------------------------------------ #
    print("\n" + "=" * 78)
    print("VERDICT — la couche 1 apporte-t-elle quelque chose ?")
    print("=" * 78)
    print(f"{'horizon':>8}{'historique seul':>18}{'couche 1 complete':>20}"
          f"{'gain':>9}{'p':>9}")
    for h, d in out.items():
        a = d["bras"]["historique"]["mae_model"]
        b = d["bras"]["+ modulateurs"]["mae_model"]
        print(f"{h:>6} min{a:>18.2f}{b:>20.2f}{d['total']['gain']:>+9.2f}"
              f"{d['total']['p_value']:>9.3f}")

    signif = [h for h, d in out.items()
              if d["total"]["p_value"] < 0.05 and d["total"]["gain"] > 0]
    print()
    if len(signif) == len(out):
        print("  La couche 1 apporte a TOUS les horizons testes. Le goulot")
        print("  conceptuel n'est pas qu'un ornement interpretable : il porte de")
        print("  l'information que l'historique glycemique ne contient pas.")
    elif signif:
        print(f"  La couche 1 apporte aux horizons "
              f"{', '.join(str(h) + ' min' for h in signif)}, pas aux autres.")
    else:
        print("  La couche 1 n'apporte RIEN de demontrable : l'historique")
        print("  glycemique suffit. C'est un resultat serieux — il ne rend pas le")
        print("  goulot inutile (il reste ce qui rend le jumeau explicable et")
        print("  simulable), mais il interdit de le vendre comme un gain de")
        print("  precision.")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({str(k): v for k, v in out.items()}, fh,
                      indent=2, ensure_ascii=False, default=float)
        print(f"\nResultats ecrits dans {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
