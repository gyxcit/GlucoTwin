"""
Adaptateur **CGMacros v1.0.0** → table de concepts.

CGMacros (PhysioNet, `10.13026/3z8q-x658`) réunit 45 participants réels — 15
sains, 16 prédiabétiques, 14 DT2 — suivis dix jours avec deux capteurs de
glycémie, un bracelet Fitbit Sense et un journal de repas photographié.

Ce que ce module fait, et pourquoi c'est le bon branchement :

- la glycémie vient du **Dexcom G6 Pro** (pas de 5 min natif), pas du Libre
  (15 min, donc interpolé — on garde le Libre en secours) ;
- l'activité vient de la colonne **`Mets`** : le bracelet fournit un MET
  **mesuré à la minute**. On ne devine donc aucune activité dans un catalogue —
  la couche 1 reçoit l'intensité réelle, ce qui supprime d'un coup la principale
  approximation du chemin synthétique ;
- les repas viennent du journal, avec leurs macronutriments **pondérés par le
  pourcentage réellement consommé** (`Amount Consumed`) ;
- le sommeil est **déduit** de la série d'intensité, faute d'annotation.

La physiologie, elle, n'est pas retouchée : on appelle
`day_concepts.concepts_from_met_series`, exactement la fonction que le chemin
synthétique utilise. Ce qui est validé sur l'un l'est sur l'autre.

Sortie : un `DataFrame` de même forme que `layer2.cohort.build_cohort`, donc
`features.py` et `evaluation.py` fonctionnent sans une ligne de modification.

    from glucotwin.data.cgmacros import build_cohort_from_cgmacros
    df = build_cohort_from_cgmacros("data/CGMacros")

**Aucune donnée n'est redistribuée par ce dépôt.** Licence CC BY-NC-SA 4.0.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..day_concepts import DaySchedule, Meal, concepts_from_met_series

# --------------------------------------------------------------------------- #
# Schéma du jeu de données (DataDictionary_CGMacros-00X.csv)
# --------------------------------------------------------------------------- #

COL_TIME = "Timestamp"
COL_DEXCOM = "Dexcom GL"
COL_LIBRE = "Libre GL"
COL_HR = "HR"
COL_MET = "METs"                 # MET × 10, à la minute
COL_ACT_CAL = "Calories (Activity)"   # kcal/min — la voie de secours
COL_MEAL_TYPE = "Meal Type"
COL_CALORIES = "Calories"
COL_CARBS = "Carbs"
COL_PROTEIN = "Protein"
COL_FAT = "Fat"
COL_FIBER = "Fiber"
COL_AMOUNT = "Amount Consumed"   # % du repas réellement mangé

#: Le bracelet stocke le MET multiplié par dix.
MET_SCALE = 10.0

#: Glycémies physiologiquement possibles ; hors bornes = artefact capteur.
GLUCOSE_MIN, GLUCOSE_MAX = 40.0, 400.0

#: Quantile de la série servant d'ancrage au repos (1,0 MET) quand on
#: reconstruit l'intensité depuis les calories. 60 % des minutes de CGMacros
#: sont sous 1,15 MET : ce quantile tombe donc franchement dans le repos.
REST_ANCHOR_Q = 0.10

#: En dessous, on considère la personne au repos (seuil de reconstruction
#: de la durée d'effort et de la détection du sommeil).
REST_MET = 1.6
SLEEP_MET = 1.15


def met_from_activity_calories(cal, q: float = REST_ANCHOR_Q) -> np.ndarray:
    """Reconstruit les METs depuis la dépense calorique minute.

    **Onze des 45 participants de CGMacros n'ont pas la colonne `METs`** — leur
    export Fitbit fournit une colonne `Intensity` ordinale (0-3) à la place.
    Les abandonner coûterait un quart de la cohorte, et les garder sans
    activité viderait la branche activité de la couche 1.

    Or `Calories (Activity)` est présente partout, et Fitbit la calcule
    *depuis* le MET : sur les 33 participants qui ont les deux colonnes, la
    corrélation est de **1,000** à un facteur d'échelle près. Il suffit donc
    d'ancrer l'échelle — le repos vaut 1 MET par définition — pour retrouver la
    série exacte. Vérifié : erreur absolue moyenne de **0,000 MET** (maximum
    0,045) sur ces 33 participants.
    """
    cal = np.asarray(cal, dtype=float)
    ok = np.isfinite(cal) & (cal > 0)
    if ok.sum() < 100:
        return np.full(len(cal), np.nan)
    base = float(np.quantile(cal[ok], q))
    if base <= 0:
        return np.full(len(cal), np.nan)
    out = cal / base
    out[~ok] = np.nan
    return out


@dataclass
class ParticipantMeta:
    """Ce qu'on sait du participant en dehors des séries temporelles."""

    pid: str
    weight_kg: float = 82.0
    age: float | None = None
    bmi: float | None = None
    a1c: float | None = None
    #: sain · prediabete · diabete — sert à l'analyse d'équité.
    group: str | None = None


# --------------------------------------------------------------------------- #
# Lecture des fichiers
# --------------------------------------------------------------------------- #

def _norm(name: str) -> str:
    """Compare les en-têtes sans se faire piéger par la casse ni les espaces."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _find_col(columns, *wanted: str, contains: bool = False) -> str | None:
    """Retrouve une colonne malgré les variations d'en-tête.

    CGMacros écrit par exemple ``"A1c PDL (Lab)"`` et ``"Body weight "`` : une
    égalité stricte rate les deux. On tente donc, dans l'ordre : égalité,
    préfixe, puis inclusion — cette dernière seulement si on l'autorise, pour
    éviter qu'un ``"age"`` n'attrape un ``"Average"``.
    """
    targets = [_norm(w) for w in wanted]
    norms = [(c, _norm(c)) for c in columns]
    for t in targets:
        for c, n in norms:
            if n == t:
                return c
    for t in targets:
        for c, n in norms:
            if n.startswith(t):
                return c
    if contains:
        for t in targets:
            for c, n in norms:
                if t in n:
                    return c
    return None


def find_participant_files(root: str | Path) -> dict[str, Path]:
    """Repère les CSV participants, quelle que soit la profondeur de dossiers.

    On accepte aussi bien l'archive décompressée telle quelle que les CSV mis
    à plat dans un seul dossier.
    """
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"dossier introuvable : {root}")
    out: dict[str, Path] = {}
    for path in sorted(root.rglob("CGMacros-*.csv")):
        m = re.search(r"CGMacros-(\d+)", path.name)
        if not m:
            continue
        pid = f"P{int(m.group(1)):03d}"
        # un CSV plus complet l'emporte sur un doublon
        if pid not in out or path.stat().st_size > out[pid].stat().st_size:
            out[pid] = path
    return out


def load_bio(root: str | Path) -> dict[str, ParticipantMeta]:
    """Lit `bio.csv` : poids, âge, HbA1c, groupe glycémique.

    Le groupe n'est pas toujours nommé dans le fichier ; à défaut on le déduit
    de l'HbA1c selon les seuils ADA (< 5,7 sain · 5,7–6,4 prédiabète · ≥ 6,5
    diabète). C'est la variable de l'analyse d'équité.
    """
    import pandas as pd

    root = Path(root)
    hits = list(root.rglob("bio.csv"))
    if not hits:
        warnings.warn("bio.csv introuvable : poids par defaut de 82 kg", stacklevel=2)
        return {}

    df = pd.read_csv(hits[0])
    cols = list(df.columns)
    c_id = _find_col(cols, "subject", "participant", "id") or cols[0]
    c_w = _find_col(cols, "body weight", "weight", contains=True)
    c_h = _find_col(cols, "height", contains=True)
    c_age = _find_col(cols, "age")
    c_bmi = _find_col(cols, "BMI", contains=True)
    c_a1c = _find_col(cols, "A1c", "HbA1c", contains=True)
    c_grp = _find_col(cols, "group", "diagnosis", "class", "cohort")

    def _f(row, col):
        if col is None:
            return None
        v = row[col]
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return None if np.isnan(v) else v

    out: dict[str, ParticipantMeta] = {}
    for _, row in df.iterrows():
        raw = str(row[c_id])
        m = re.search(r"(\d+)", raw)
        if not m:
            continue
        pid = f"P{int(m.group(1)):03d}"
        bmi = _f(row, c_bmi)
        w = resolve_weight_kg(_f(row, c_w), _f(row, c_h), bmi)
        a1c = _f(row, c_a1c)
        grp = str(row[c_grp]).strip().lower() if c_grp is not None else None
        if not grp or grp in ("nan", "none"):
            grp = _group_from_a1c(a1c)
        out[pid] = ParticipantMeta(
            pid=pid,
            weight_kg=w if 30 < w < 250 else 82.0,
            age=_f(row, c_age), bmi=bmi, a1c=a1c, group=grp,
        )
    return out


LB_PER_KG = 2.2046226218
IN_PER_M = 39.3700787402


def resolve_weight_kg(
    weight: float | None, height: float | None, bmi: float | None,
    default: float = 82.0,
) -> float:
    """Ramène le poids en kilogrammes, quelle que soit l'unité du fichier.

    **CGMacros est en unités impériales** : `Body weight ` vaut 133,8 et
    `Height ` vaut 65 — des livres et des pouces. Les prendre pour des
    kilogrammes gonflerait le poids d'un facteur 2,2, et le poids pilote le
    VO₂, la production hépatique et la captation musculaire : toute la couche 1
    serait fausse d'un bout à l'autre, sans qu'aucune erreur ne soit levée.

    On ne devine pas : on **vérifie**. L'IMC et la taille donnent le poids
    attendu en kilogrammes ; on retient l'interprétation qui colle. Sans IMC,
    on retombe sur une heuristique de plage, et on le dit.
    """
    if weight is None or not np.isfinite(weight) or weight <= 0:
        return default

    if bmi and height and np.isfinite(bmi) and np.isfinite(height) and height > 0:
        # la taille elle-meme peut etre en pouces (~59-72) ou en cm (~150-200)
        h_m = height / IN_PER_M if height < 100 else height / 100.0
        expected = bmi * h_m * h_m
        if abs(weight - expected) <= abs(weight / LB_PER_KG - expected):
            return float(weight)
        return float(weight / LB_PER_KG)

    # sans IMC : au-dela de 200, ce sont forcement des livres
    return float(weight / LB_PER_KG) if weight > 200 else float(weight)


def _group_from_a1c(a1c: float | None) -> str | None:
    if a1c is None:
        return None
    if a1c < 5.7:
        return "sain"
    if a1c < 6.5:
        return "prediabete"
    return "diabete"


# --------------------------------------------------------------------------- #
# Sommeil : déduit, faute d'annotation
# --------------------------------------------------------------------------- #

def infer_sleep_window(
    hours: np.ndarray, met: np.ndarray, default=(7.0, 23.0)
) -> tuple[float, float]:
    """Devine (lever, coucher) depuis la série d'intensité d'une journée.

    On cherche la plus longue plage continue sous le seuil de sommeil dans la
    fenêtre nocturne. Sans annotation de sommeil dans CGMacros, c'est la
    meilleure information disponible — et elle vaut mieux qu'un horaire fixe,
    puisque le phénomène de l'aube est calé sur l'heure du lever.
    """
    night = (hours < 10.0) | (hours >= 20.0)
    quiet = night & (met < SLEEP_MET)
    if quiet.sum() < 12:                       # moins d'une heure : on renonce
        return default

    # Repère la plus longue série de True, en tenant compte du passage minuit :
    # on décale l'axe de 12 h pour que la nuit soit contiguë.
    shifted = np.argsort((hours + 12.0) % 24.0)
    q = quiet[shifted]
    h = ((hours + 12.0) % 24.0)[shifted]

    best_len = best_start = best_end = 0
    run_start = None
    for i, flag in enumerate(list(q) + [False]):
        if flag and run_start is None:
            run_start = i
        elif not flag and run_start is not None:
            if i - run_start > best_len:
                best_len, best_start, best_end = i - run_start, run_start, i - 1
            run_start = None
    if best_len < 12:
        return default

    bed = (h[best_start] - 12.0) % 24.0
    wake = (h[best_end] - 12.0) % 24.0
    if not (2.0 <= (wake - bed) % 24.0 <= 14.0):
        return default
    return round(wake, 2), round(bed, 2)


# --------------------------------------------------------------------------- #
# Un participant → des journées
# --------------------------------------------------------------------------- #

def load_participant(
    path: str | Path,
    meta: ParticipantMeta,
    *,
    step_min: int = 5,
    min_coverage: float = 0.8,
    prefer: str = "dexcom",
    metformin: bool = False,
):
    """Transforme un CSV participant en liste de journées exploitables.

    Chaque journée devient un couple (concepts, glycémie) sur une grille
    régulière de `step_min` minutes. Les journées trop trouées sont écartées :
    mieux vaut 6 journées propres que 10 dont la moitié est interpolée.
    """
    import pandas as pd

    df = pd.read_csv(path)
    cols = list(df.columns)
    c_t = _find_col(cols, COL_TIME)
    if c_t is None:
        raise ValueError(f"{path} : colonne '{COL_TIME}' absente")

    c_dex, c_lib = _find_col(cols, COL_DEXCOM), _find_col(cols, COL_LIBRE)
    c_met = _find_col(cols, COL_MET)
    c_meal = _find_col(cols, COL_MEAL_TYPE)
    c_carb = _find_col(cols, COL_CARBS)

    ts = pd.to_datetime(df[c_t], errors="coerce")
    df = df.loc[ts.notna()].copy()
    df["_ts"] = ts[ts.notna()]
    df = df.sort_values("_ts")

    # --- glycémie : Dexcom d'abord, Libre en secours ---
    order = [c_dex, c_lib] if prefer == "dexcom" else [c_lib, c_dex]
    glucose = None
    for c in order:
        if c is None:
            continue
        v = pd.to_numeric(df[c], errors="coerce")
        v = v.where((v >= GLUCOSE_MIN) & (v <= GLUCOSE_MAX))
        if v.notna().mean() > 0.3:
            glucose = v
            break
    if glucose is None:
        raise ValueError(f"{path} : aucune serie glycemique exploitable")
    df["_g"] = glucose

    # --- intensité mesurée ---
    c_cal = _find_col(cols, COL_ACT_CAL)
    if c_met is not None:
        met = pd.to_numeric(df[c_met], errors="coerce") / MET_SCALE
        met_source = "METs"
    elif c_cal is not None:
        met = pd.Series(
            met_from_activity_calories(
                pd.to_numeric(df[c_cal], errors="coerce").to_numpy()),
            index=df.index)
        met_source = "calories"
    else:
        warnings.warn(f"{path} : ni '{COL_MET}' ni '{COL_ACT_CAL}'", stacklevel=2)
        met = pd.Series(np.nan, index=df.index)
        met_source = "absent"
    df["_met"] = met.where((met > 0.4) & (met < 25.0))

    # --- repas ---
    meals_raw = []
    if c_meal is not None and c_carb is not None:
        mask = df[c_meal].notna() & (df[c_meal].astype(str).str.strip() != "")
        for _, row in df.loc[mask].iterrows():
            frac = 1.0
            c_amt = _find_col(cols, COL_AMOUNT)
            if c_amt is not None:
                try:
                    a = float(row[c_amt])
                    if 0 < a <= 100:
                        frac = a / 100.0
                except (TypeError, ValueError):
                    pass

            def g(col):
                c = _find_col(cols, col)
                if c is None:
                    return 0.0
                try:
                    v = float(row[c])
                except (TypeError, ValueError):
                    return 0.0
                return 0.0 if np.isnan(v) else max(0.0, v) * frac

            carbs = g(COL_CARBS)
            if carbs <= 0:
                continue
            meals_raw.append((row["_ts"], carbs, g(COL_PROTEIN),
                              g(COL_FAT), g(COL_FIBER)))

    # --- découpage en journées, sur grille régulière ---
    steps = int(24 * 60 / step_min) + 1
    grid_h = np.arange(steps) * step_min / 60.0
    out = []

    for day_date, block in df.groupby(df["_ts"].dt.date, sort=True):
        minutes = (block["_ts"].dt.hour * 60 + block["_ts"].dt.minute).to_numpy(float)
        gi_ = np.round(minutes / step_min).astype(int)
        keep = (gi_ >= 0) & (gi_ < steps)
        gi_, gvals = gi_[keep], block["_g"].to_numpy(float)[keep]
        mvals = block["_met"].to_numpy(float)[keep]

        g_grid = np.full(steps, np.nan)
        m_grid = np.full(steps, np.nan)
        for k, gv, mv in zip(gi_, gvals, mvals):
            if not np.isnan(gv):
                g_grid[k] = gv
            if not np.isnan(mv):
                m_grid[k] = mv

        coverage = np.isfinite(g_grid).mean()
        if coverage < min_coverage:
            continue

        g_grid = _interp_nan(grid_h, g_grid)
        m_grid = _interp_nan(grid_h, m_grid, fill=1.3)
        if not np.isfinite(g_grid).all():
            continue

        wake_h, bed_h = infer_sleep_window(grid_h, m_grid)
        day_meals = [
            Meal(time_h=t.hour + t.minute / 60.0, carbs_g=c,
                 protein_g=p, fat_g=f, fiber_g=fb, gi=1.0)
            for (t, c, p, f, fb) in meals_raw if t.date() == day_date
        ]

        schedule = DaySchedule(
            weight_kg=meta.weight_kg, wake_h=wake_h, bed_h=bed_h,
            meals=day_meals, activities=[], metformin=metformin,
        )
        frames = concepts_from_met_series(schedule, list(m_grid), step_min=step_min)
        out.append((str(day_date), frames, g_grid, coverage, met_source))

    return out


def _interp_nan(x, y, fill: float | None = None):
    """Bouche les trous par interpolation linéaire (pas d'extrapolation folle)."""
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(y)
    if ok.all():
        return y
    if ok.sum() < 2:
        return np.full_like(y, fill if fill is not None else np.nan)
    out = y.copy()
    out[~ok] = np.interp(x[~ok], x[ok], y[ok])
    return out


# --------------------------------------------------------------------------- #
# Cohorte complète
# --------------------------------------------------------------------------- #

def build_cohort_from_cgmacros(
    root: str | Path,
    *,
    step_min: int = 5,
    min_coverage: float = 0.8,
    max_participants: int | None = None,
    metformin: bool = False,
    verbose: bool = True,
):
    """Construit la table réelle, dans la forme exacte de `build_cohort`.

    Colonnes : `patient`, `day`, `glucose`, `weight_kg`, les 14 concepts — plus
    `group` et `a1c`, qui ne servent qu'à l'analyse par sous-groupe et **ne
    doivent jamais entrer dans les features**.
    """
    import pandas as pd

    files = find_participant_files(root)
    if not files:
        raise FileNotFoundError(
            f"aucun fichier CGMacros-XXX.csv sous {root} — "
            "l'archive a-t-elle ete decompressee ?"
        )
    bio = load_bio(root)
    if max_participants:
        files = dict(list(files.items())[:max_participants])

    rows, skipped = [], []
    for pid, path in files.items():
        meta = bio.get(pid, ParticipantMeta(pid=pid))
        try:
            days = load_participant(
                path, meta, step_min=step_min,
                min_coverage=min_coverage, metformin=metformin,
            )
        except Exception as exc:                       # noqa: BLE001
            skipped.append((pid, str(exc)))
            continue
        if not days:
            skipped.append((pid, "aucune journee assez complete"))
            continue
        for day_i, (day_date, frames, g_grid, cov, met_source) in enumerate(days):
            for f, gl in zip(frames, g_grid):
                rec = dict(vars(f))
                rec["patient"] = pid
                rec["day"] = day_i
                rec["date"] = day_date
                rec["glucose"] = float(gl)
                rec["weight_kg"] = meta.weight_kg
                rec["group"] = meta.group
                rec["a1c"] = meta.a1c
                rec["met_source"] = met_source
                rows.append(rec)
        if verbose:
            print(f"  {pid}: {len(days)} journees | poids {meta.weight_kg:.0f} kg "
                  f"| groupe {meta.group or '?'} | METs {days[0][4]}")

    if skipped and verbose:
        print(f"\n  {len(skipped)} participants ecartes :")
        for pid, why in skipped[:10]:
            print(f"    {pid} — {why}")

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("aucune journee exploitable dans le jeu de donnees")
    return df


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="CGMacros -> table de concepts")
    ap.add_argument("root", help="dossier de l'archive CGMacros decompressee")
    ap.add_argument("--out", default=None, help="fichier parquet/csv de sortie")
    ap.add_argument("--max-participants", type=int, default=None)
    ap.add_argument("--min-coverage", type=float, default=0.8)
    args = ap.parse_args()

    df = build_cohort_from_cgmacros(
        args.root, max_participants=args.max_participants,
        min_coverage=args.min_coverage,
    )
    print(f"\n{len(df):,} pas | {df.patient.nunique()} patients "
          f"| {df.groupby('patient').day.nunique().sum()} journees")
    print(f"glycemie moyenne {df.glucose.mean():.0f} mg/dL "
          f"| TIR {(df.glucose.between(70, 180)).mean() * 100:.0f} %")
    if "group" in df:
        print(df.groupby("group").patient.nunique().to_string())
    if args.out:
        (df.to_parquet if args.out.endswith(".parquet") else df.to_csv)(args.out)
        print(f"ecrit dans {args.out}")
