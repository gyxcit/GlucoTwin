#!/usr/bin/env python3
"""
Reparamétrisation — cinq paramètres contre quatre.

Le modèle de calibration à cinq paramètres généralise bien mais **ne s'identifie
pas** : sur CGMacros, 61 % des patients ont un gain collé à une borne, et seuls
5 sur 44 n'en ont aucun de saturé. Production hépatique, captation basale et
glycémie d'équilibre agissent toutes trois sur le même niveau, dont une seule
résultante est observable.

Le modèle réduit absorbe le bilan basal dans la glycémie d'équilibre. Quatre
paramètres, chacun lisible sur une portion différente de la courbe.

    python scripts/run_reparam.py --pickle table.pkl --days-fit 3

Trois comparaisons :

1. **Identifiabilité** — combien de paramètres saturent, dans chaque modèle ?
2. **Généralisation** — le réduit perd-il en précision sur les journées de test ?
3. **Validation externe** — la glycémie d'équilibre ajustée correspond-elle à la
   **glycémie à jeun mesurée au laboratoire** ? C'est le test qui décide si le
   paramètre mesure quelque chose de réel ou s'il absorbe du bruit.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from glucotwin.calibration import (
    BOUNDS,
    PARAM_NAMES,
    REDUCED_BOUNDS,
    REDUCED_PARAM_NAMES,
    calibrate_cohort,
    saturation_rate,
    summarize,
)


def _bloc(res, bounds, names, titre):
    s = summarize(res)
    sat = saturation_rate([r.theta for r in res], bounds, names)
    print(f"\n{titre}")
    print("-" * 70)
    print(f"  Patients                      {s['n_patients']}")
    print(f"  RMSE test (calibre)           {s['rmse_calibre']:.2f} mg/dL")
    print(f"  RMSE test (population)        {s['rmse_population']:.2f} mg/dL")
    print(f"  RMSE test (persistance)       {s['rmse_persistance']:.2f} mg/dL")
    print(f"  Gain de la calibration        {s['gain_vs_population']:+.2f} mg/dL "
          f"(p={s['p_value']:.1e}, {s['patients_ameliores']}/{s['n_patients']})")
    print("  Saturation aux bornes :")
    for n in names:
        print(f"    {n:<12} {sat[n] * 100:5.1f} %")
    print(f"    {'AUCUN sature':<12} {sat['_aucun_sature'] * 100:5.1f} % des patients")
    return s, sat


def main() -> int:
    ap = argparse.ArgumentParser(description="Reparametrisation basale")
    ap.add_argument("--pickle", default=None)
    ap.add_argument("--cgmacros", default=None)
    ap.add_argument("--days-fit", type=int, default=3)
    ap.add_argument("--bio", default=None,
                    help="dossier contenant bio.csv, pour la validation externe")
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

    print("=" * 70)
    print("REPARAMETRISATION — 5 parametres contre 4")
    print(f"{len(df):,} pas | {df.patient.nunique()} patients | "
          f"{args.days_fit} journees d'ajustement")
    print("=" * 70)

    complet = calibrate_cohort(df, n_days_fit=args.days_fit, model="full",
                               verbose=False)
    reduit = calibrate_cohort(df, n_days_fit=args.days_fit, model="reduced",
                              verbose=False)

    s_c, sat_c = _bloc(complet, BOUNDS, PARAM_NAMES, "MODELE COMPLET (5 parametres)")
    s_r, sat_r = _bloc(reduit, REDUCED_BOUNDS, REDUCED_PARAM_NAMES,
                       "MODELE REDUIT (4 parametres)")

    print("\n" + "=" * 70)
    print("COMPARAISON")
    print("=" * 70)
    d_rmse = s_r["rmse_calibre"] - s_c["rmse_calibre"]
    d_sat = sat_r["_aucun_sature"] - sat_c["_aucun_sature"]
    print(f"  Precision sur les journees de test   {d_rmse:+.2f} mg/dL "
          f"({'le reduit perd' if d_rmse > 0 else 'le reduit gagne'})")
    print(f"  Patients sans aucun parametre sature {sat_c['_aucun_sature'] * 100:.0f} % "
          f"-> {sat_r['_aucun_sature'] * 100:.0f} %  ({d_sat * 100:+.0f} points)")

    # --- validation externe : le laboratoire ---
    ext = None
    if args.bio or args.cgmacros:
        from glucotwin.data.cgmacros import _find_col
        import pandas as pd
        racine = args.bio or args.cgmacros
        import pathlib
        hits = list(pathlib.Path(racine).rglob("bio.csv"))
        if hits:
            bio = pd.read_csv(hits[0])
            c_id = _find_col(list(bio.columns), "subject", "participant", "id")
            c_fg = _find_col(list(bio.columns), "Fasting GLU", "fasting", contains=True)
            if c_id and c_fg:
                import re
                lab = {}
                for _, row in bio.iterrows():
                    m = re.search(r"(\d+)", str(row[c_id]))
                    if m:
                        try:
                            lab[f"P{int(m.group(1)):03d}"] = float(row[c_fg])
                        except (TypeError, ValueError):
                            pass
                print("\n" + "=" * 70)
                print("VALIDATION EXTERNE — la glycemie d'equilibre ajustee")
                print("contre la GLYCEMIE A JEUN MESUREE AU LABORATOIRE")
                print("=" * 70)
                for res, noms, titre in ((complet, PARAM_NAMES, "complet"),
                                         (reduit, REDUCED_PARAM_NAMES, "reduit")):
                    j = noms.index("g_base")
                    pairs = [(r.theta[j], lab[r.patient]) for r in res
                             if r.patient in lab and np.isfinite(lab[r.patient])]
                    if len(pairs) < 5:
                        continue
                    a = np.array([p[0] for p in pairs])
                    b = np.array([p[1] for p in pairs])
                    r_p = float(np.corrcoef(a, b)[0, 1])
                    from scipy.stats import spearmanr, pearsonr
                    _, p_p = pearsonr(a, b)
                    rho, p_s = spearmanr(a, b)
                    print(f"  modele {titre:<8} n={len(pairs):>3}  "
                          f"Pearson r={r_p:+.3f} (p={p_p:.1e})  "
                          f"Spearman rho={rho:+.3f} (p={p_s:.1e})  "
                          f"ecart moyen {np.mean(a - b):+.1f} mg/dL")
                    if titre == "reduit":
                        ext = {"n": len(pairs), "pearson": r_p, "p_pearson": float(p_p),
                               "spearman": float(rho), "p_spearman": float(p_s),
                               "biais": float(np.mean(a - b))}
                if ext and ext["p_pearson"] < 0.05:
                    print("\n  Le parametre ajuste correle avec une mesure de laboratoire")
                    print("  qu'il n'a jamais vue. Ce n'est pas un facteur d'ajustement :")
                    print("  il estime une grandeur physiologique reelle.")
                elif ext:
                    print("\n  Aucune correlation significative avec le laboratoire : le")
                    print("  parametre absorbe autre chose que la glycemie a jeun.")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"complet": {"resume": s_c, "saturation": sat_c},
                       "reduit": {"resume": s_r, "saturation": sat_r},
                       "validation_externe": ext},
                      fh, indent=2, ensure_ascii=False, default=float)
        print(f"\nResultats ecrits dans {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
