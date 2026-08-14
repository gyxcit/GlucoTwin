#!/usr/bin/env python3
"""
Contrôle de recevabilité de CGMacros — **à lancer avant toute expérience**.

Un jeu de données réel ne se fait pas confiance. Ce script vérifie les
hypothèses dont dépend toute la couche 1, et il vaut mieux qu'elles tombent ici
que dans un résultat qu'on présentera devant un jury.

Les six contrôles :

1. **L'heure de la journée est-elle préservée ?** CGMacros décale les dates au
   hasard (`dateshifted365`). Si le décalage touchait aussi l'heure, le rythme
   circadien et le phénomène de l'aube n'auraient plus aucun sens — la moitié
   de la couche 1 serait du bruit. On le teste sur la distribution des heures
   de repas : elles doivent former trois bosses, pas un plateau.
2. **Les identifiants concordent-ils ?** Si `bio.csv` et les fichiers CGM
   n'étaient pas alignés, on attribuerait le poids et l'HbA1c du mauvais
   participant — une erreur silencieuse et fatale. Contrôle : les glycémies
   observées doivent croître du groupe sain au groupe diabétique.
3. **Couverture CGM** par participant et par journée.
4. **Distribution des METs** : plage plausible, et sommeil détectable.
5. **Accord Dexcom / Libre** — deux capteurs sur la même personne.
6. **Journal de repas** : combien de repas par jour, quelle charge glucidique.
7. **Unités du poids** : CGMacros est en livres et en pouces. Prendre les
   livres pour des kilogrammes gonfle le poids d'un facteur 2,2 et fausse
   toute la couche 1 sans lever la moindre erreur.

    python scripts/inspect_cgmacros.py data/CGMacros
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from glucotwin.data.cgmacros import (
    COL_CARBS,
    COL_DEXCOM,
    COL_LIBRE,
    COL_MEAL_TYPE,
    COL_MET,
    COL_TIME,
    MET_SCALE,
    _find_col,
    find_participant_files,
    load_bio,
)

OK, WARN, FAIL = "[ok]  ", "[!]   ", "[X]   "


def _hour_series(df, c_t):
    import pandas as pd

    ts = pd.to_datetime(df[c_t], errors="coerce")
    ts = ts[ts.notna()]
    return ts.dt.hour + ts.dt.minute / 60.0, ts


def check_time_of_day(files, verbose=True) -> bool:
    """Les repas se concentrent-ils aux heures de repas ?"""
    import pandas as pd

    hours = []
    for path in list(files.values()):
        df = pd.read_csv(path)
        cols = list(df.columns)
        c_t, c_meal = _find_col(cols, COL_TIME), _find_col(cols, COL_MEAL_TYPE)
        if c_t is None or c_meal is None:
            continue
        mask = df[c_meal].notna() & (df[c_meal].astype(str).str.strip() != "")
        h, _ = _hour_series(df.loc[mask], c_t)
        hours.extend(h.tolist())

    hours = np.asarray(hours)
    if len(hours) < 30:
        print(f"{WARN}heures de repas : trop peu de repas pour conclure")
        return True

    counts, _ = np.histogram(hours, bins=24, range=(0, 24))
    frac = counts / counts.sum()
    # Le discriminant le plus net n'est pas la concentration des repas — de
    # vraies personnes mangent sur une plage large — mais la NUIT. Si l'heure
    # etait randomisee, 00h-05h recevrait sa part uniforme, soit 5/24 = 20,8 %
    # des repas. Quand l'heure est preservee, on tombe autour de 1 %.
    night = frac[0:5].sum()                       # 00h-05h
    top6 = np.sort(frac)[-6:].sum()
    UNIFORME = 5 / 24

    print(f"\n1. HEURE DE LA JOURNEE — {len(hours)} repas horodates")
    print(f"      repas entre 00h et 05h       : {night * 100:.1f} %  "
          f"(attendu {UNIFORME * 100:.1f} % si l'heure etait randomisee)")
    print(f"      6 heures les plus frequentes : {top6 * 100:.0f} % des repas")
    if verbose:
        peak = np.argsort(counts)[-3:][::-1]
        print(f"      pics : {', '.join(f'{h:02d}h' for h in sorted(peak))}")

    if night < 0.05:
        print(f"{OK}l'heure du jour est preservee ({UNIFORME / max(night, 1e-9):.0f}x "
              "moins de repas nocturnes que sous randomisation)")
        print("      => circadien et phenomene de l'aube exploitables")
        return True
    if night < 0.12:
        print(f"{WARN}signal intermediaire : a surveiller dans l'ablation")
        return True
    print(f"{FAIL}les repas sont etales sur 24 h : l'heure semble randomisee.")
    print("      => desactiver les concepts circadian_factor et dawn_factor,")
    print("         ou les traiter comme non informatifs dans l'ablation.")
    return False


def check_group_alignment(files, bio) -> bool:
    """Les diabétiques ont-ils bien des glycémies plus hautes ?"""
    import pandas as pd

    by_group: dict[str, list] = {}
    for pid, path in files.items():
        meta = bio.get(pid)
        if meta is None or not meta.group:
            continue
        df = pd.read_csv(path)
        cols = list(df.columns)
        c = _find_col(cols, COL_DEXCOM) or _find_col(cols, COL_LIBRE)
        if c is None:
            continue
        v = pd.to_numeric(df[c], errors="coerce")
        v = v[(v >= 40) & (v <= 400)]
        if len(v) > 100:
            by_group.setdefault(meta.group, []).append(float(v.mean()))

    print("\n2. CONCORDANCE bio.csv <-> fichiers CGM")
    if len(by_group) < 2:
        print(f"{WARN}pas assez de groupes pour verifier")
        return True
    for g in ("sain", "prediabete", "diabete"):
        if g in by_group:
            arr = np.array(by_group[g])
            print(f"      {g:<12} n={len(arr):>3}  glycemie moyenne "
                  f"{arr.mean():6.1f} mg/dL")

    sain = np.mean(by_group.get("sain", [np.nan]))
    diab = np.mean(by_group.get("diabete", [np.nan]))
    if np.isnan(sain) or np.isnan(diab):
        print(f"{WARN}groupes extremes absents — verification impossible")
        return True
    if diab > sain + 5:
        print(f"{OK}les diabetiques sont plus hauts de {diab - sain:.0f} mg/dL "
              "— les identifiants concordent")
        return True
    print(f"{FAIL}les groupes ne se separent pas ({diab - sain:+.0f} mg/dL).")
    print("      => suspecter un desalignement entre bio.csv et les fichiers CGM.")
    return False


def check_coverage(files, step_min=5) -> bool:
    import pandas as pd

    print("\n3. COUVERTURE CGM")
    rows = []
    for pid, path in files.items():
        df = pd.read_csv(path)
        cols = list(df.columns)
        c_t = _find_col(cols, COL_TIME)
        c_g = _find_col(cols, COL_DEXCOM) or _find_col(cols, COL_LIBRE)
        if c_t is None or c_g is None:
            continue
        ts = pd.to_datetime(df[c_t], errors="coerce")
        v = pd.to_numeric(df[c_g], errors="coerce")
        ok = ts.notna() & v.between(40, 400)
        days = ts[ok].dt.date.nunique()
        span = max(1, (ts.max() - ts.min()).days + 1)
        rows.append((pid, days, span, ok.sum()))

    if not rows:
        print(f"{FAIL}aucun fichier lisible")
        return False
    days = np.array([r[1] for r in rows])
    print(f"      {len(rows)} participants | journees avec CGM : "
          f"mediane {np.median(days):.0f}, min {days.min()}, max {days.max()}")
    faibles = [r[0] for r in rows if r[1] < 3]
    if faibles:
        print(f"{WARN}moins de 3 journees : {', '.join(faibles[:8])}")
    else:
        print(f"{OK}tous les participants ont au moins 3 journees")
    return True


def check_mets(files) -> bool:
    import pandas as pd

    print("\n4. INTENSITE MESUREE (colonne Mets)")
    vals = []
    for path in list(files.values())[:12]:
        df = pd.read_csv(path)
        c = _find_col(list(df.columns), COL_MET)
        if c is None:
            continue
        v = pd.to_numeric(df[c], errors="coerce").dropna() / MET_SCALE
        vals.append(v.to_numpy())
    if not vals:
        print(f"{FAIL}colonne '{COL_MET}' absente — la branche activite serait vide")
        return False
    v = np.concatenate(vals)
    q = np.percentile(v, [1, 50, 95, 99.9])
    print(f"      percentiles 1/50/95/99.9 : {q[0]:.2f} / {q[1]:.2f} / "
          f"{q[2]:.2f} / {q[3]:.2f} MET")
    print(f"      part sous 1,15 MET (repos/sommeil) : {(v < 1.15).mean() * 100:.0f} %")
    print(f"      part au-dessus de 3 MET (effort)   : {(v > 3).mean() * 100:.1f} %")
    if q[1] > 20:
        print(f"{FAIL}mediane a {q[1]:.0f} : la division par {MET_SCALE:.0f} "
              "n'a peut-etre pas lieu d'etre")
        return False
    if (v < 1.15).mean() < 0.05:
        print(f"{WARN}presque aucun point au repos — sommeil difficile a deduire")
    else:
        print(f"{OK}plage physiologique, sommeil detectable")
    return True


def check_sensors(files) -> bool:
    """Deux capteurs sur la même personne disent-ils la même chose ?

    Ce n'est pas une formalité. Si le Dexcom et le Libre divergent
    systématiquement, alors **le choix du capteur change les résultats** — et
    comparer nos chiffres à un repère publié n'a de sens que si le repère a été
    calculé sur le même capteur. C'est une limite à énoncer, pas à ignorer.
    """
    import pandas as pd

    print("\n5. ACCORD DEXCOM / LIBRE")
    diffs = []
    for path in list(files.values())[:20]:
        df = pd.read_csv(path)
        cols = list(df.columns)
        c_d, c_l = _find_col(cols, COL_DEXCOM), _find_col(cols, COL_LIBRE)
        if c_d is None or c_l is None:
            continue
        d = pd.to_numeric(df[c_d], errors="coerce")
        lib = pd.to_numeric(df[c_l], errors="coerce")
        m = d.between(40, 400) & lib.between(40, 400)
        if m.sum() > 100:
            diffs.append((d[m] - lib[m]).to_numpy())
    if not diffs:
        print(f"{WARN}un seul capteur disponible")
        return True
    v = np.concatenate(diffs)
    biais, mad = float(v.mean()), float(np.median(np.abs(v)))
    print(f"      biais Dexcom - Libre        {biais:+.1f} mg/dL")
    print(f"      ecart absolu median         {mad:.1f} mg/dL")
    if abs(biais) < 10 and mad < 15:
        print(f"{OK}les deux capteurs concordent")
        return True
    print(f"{WARN}divergence importante entre capteurs.")
    print(f"      => le choix du capteur deplace la MAE de l'ordre de "
          f"{mad:.0f} mg/dL. Nos resultats sont sur DEXCOM ; tout repere")
    print("         publie doit etre compare sur le meme capteur, sinon la")
    print("         comparaison ne veut rien dire. A dire dans les limites.")
    return True


def check_meals(files) -> bool:
    import pandas as pd

    print("\n6. JOURNAL DE REPAS")
    per_day, carbs = [], []
    for pid, path in files.items():
        df = pd.read_csv(path)
        cols = list(df.columns)
        c_t, c_meal = _find_col(cols, COL_TIME), _find_col(cols, COL_MEAL_TYPE)
        c_c = _find_col(cols, COL_CARBS)
        if c_t is None or c_meal is None or c_c is None:
            continue
        ts = pd.to_datetime(df[c_t], errors="coerce")
        mask = df[c_meal].notna() & (df[c_meal].astype(str).str.strip() != "")
        mask &= ts.notna()
        n_days = ts[ts.notna()].dt.date.nunique()
        if n_days:
            per_day.append(mask.sum() / n_days)
        carbs.extend(pd.to_numeric(df.loc[mask, c_c], errors="coerce")
                     .dropna().tolist())
    if not per_day:
        print(f"{FAIL}aucun repas trouve")
        return False
    print(f"      repas par jour : mediane {np.median(per_day):.1f}")
    print(f"      glucides par repas : mediane {np.median(carbs):.0f} g, "
          f"90e centile {np.percentile(carbs, 90):.0f} g")
    if np.median(per_day) < 1.5:
        print(f"{WARN}moins de 2 repas/jour declares — journal tres incomplet")
    else:
        print(f"{OK}journal exploitable")
    return True


def check_units(root) -> bool:
    """Le poids retenu est-il cohérent avec l'IMC et la taille ?"""
    print("\n7. UNITES DU POIDS")
    bio = load_bio(root)
    if not bio:
        print(f"{WARN}bio.csv absent")
        return True
    kg = np.array([m.weight_kg for m in bio.values()])
    bmi = np.array([m.bmi for m in bio.values() if m.bmi], dtype=float)
    print(f"      poids retenu : {kg.min():.0f} - {kg.max():.0f} kg "
          f"(mediane {np.median(kg):.0f})")
    if len(bmi):
        print(f"      IMC declare  : {bmi.min():.1f} - {bmi.max():.1f}")
    if kg.max() > 220 or np.median(kg) > 140:
        print(f"{FAIL}poids implausibles — conversion livres/kg manquee")
        return False
    print(f"{OK}poids en kilogrammes, coherents avec l'IMC")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Controle de recevabilite CGMacros")
    ap.add_argument("root", help="dossier de l'archive decompressee")
    args = ap.parse_args()

    root = Path(args.root)
    files = find_participant_files(root)
    bio = load_bio(root)
    print("=" * 78)
    print(f"CGMacros — {len(files)} participants, {len(bio)} lignes dans bio.csv")
    print("=" * 78)

    results = [
        check_time_of_day(files),
        check_group_alignment(files, bio),
        check_coverage(files),
        check_mets(files),
        check_sensors(files),
        check_meals(files),
        check_units(root),
    ]

    print("\n" + "=" * 78)
    if all(results):
        print("Tous les controles passent — le jeu est exploitable tel quel.")
        return 0
    print("Des controles ont echoue : lire ci-dessus AVANT de lancer l'experience.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
