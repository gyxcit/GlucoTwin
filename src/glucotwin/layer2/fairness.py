"""
Couche 2 — **équité** : la performance est-elle la même pour tout le monde ?

C'est la quatrième affirmation du projet, et celle qu'on peut le plus facilement
se raconter à soi-même. Un modèle qui affiche 12 mg/dL de MAE moyenne peut très
bien en faire 9 chez les participants sains et 17 chez les diabétiques — c'est-à-dire
être le meilleur là où ça sert le moins.

Le piège, avec 14 à 16 patients par groupe : **un écart apparent n'est pas un
écart réel**. Trois groupes tirés au hasard dans une même population montrent
presque toujours des moyennes différentes. Ce module mesure donc l'écart *et*
teste s'il dépasse ce que le hasard produit, par permutation des étiquettes de
groupe entre patients. Sans ce test, annoncer une inéquité est une faute de
méthode.

L'unité d'analyse est le **patient**, jamais le pas de temps : les points d'un
même patient ne sont pas indépendants.

    from glucotwin.layer2.fairness import subgroup_report, print_fairness
    rep = lopo_evaluate(...)
    fr = subgroup_report(rep, patient_to_group)
    print_fairness(fr)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .evaluation import (
    HYPER_THRESHOLD,
    HYPO_THRESHOLD,
    LopoReport,
    event_detection,
    mae,
)


@dataclass
class SubgroupResult:
    """Ce qu'on peut dire d'un sous-groupe, patient par patient."""

    name: str
    n_patients: int
    mae_model: float
    mae_persistence: float
    gain: float
    gain_ic95: tuple[float, float]
    patients_gagnes: int
    couverture: float
    #: sensibilité de détection, calculée sur les points du groupe
    sensibilite_hypo: float = float("nan")
    sensibilite_hyper: float = float("nan")
    n_hypo: int = 0
    n_hyper: int = 0
    maes: np.ndarray = field(default_factory=lambda: np.array([]))


def _fold_slices(report: LopoReport) -> dict[str, slice]:
    """Retrouve, pour chaque patient, sa tranche dans les tableaux concaténés.

    `lopo_evaluate` empile les prédictions dans l'ordre des plis ; on reconstruit
    donc les bornes en cumulant `n_test`. C'est exact tant que l'ordre est
    préservé — ce qui est garanti par construction dans `evaluation.py`.
    """
    out, start = {}, 0
    for f in report.folds:
        out[f.patient] = slice(start, start + f.n_test)
        start += f.n_test
    return out


def subgroup_report(
    report: LopoReport,
    patient_to_group: dict[str, str],
    *,
    min_patients: int = 3,
) -> dict[str, SubgroupResult]:
    """Décompose un rapport LOPO par sous-groupe.

    `patient_to_group` associe l'identifiant de patient à son groupe (par
    exemple `sain` / `prediabete` / `diabete`). Les groupes trop petits sont
    écartés : en dessous de trois patients, une moyenne ne veut rien dire.
    """
    slices = _fold_slices(report)
    buckets: dict[str, list] = {}
    for f in report.folds:
        g = patient_to_group.get(f.patient)
        if g is None:
            continue
        buckets.setdefault(str(g), []).append(f)

    out: dict[str, SubgroupResult] = {}
    for name, folds in sorted(buckets.items()):
        if len(folds) < min_patients:
            continue
        m = np.array([f.mae_model for f in folds])
        p = np.array([f.mae_persistence for f in folds])
        d = p - m
        n = len(d)
        se = d.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")

        idx = np.concatenate([np.arange(slices[f.patient].start,
                                        slices[f.patient].stop) for f in folds])
        y_true = report.y_true_abs[idx]
        y_pred = report.y_pred_abs[idx]
        hypo = event_detection(y_true, y_pred, HYPO_THRESHOLD, True)
        hyper = event_detection(y_true, y_pred, HYPER_THRESHOLD, False)

        out[name] = SubgroupResult(
            name=name,
            n_patients=n,
            mae_model=float(m.mean()),
            mae_persistence=float(p.mean()),
            gain=float(d.mean()),
            gain_ic95=(float(d.mean() - 1.96 * se), float(d.mean() + 1.96 * se)),
            patients_gagnes=int((d > 0).sum()),
            couverture=float(np.nanmean([f.interval_coverage for f in folds])),
            sensibilite_hypo=hypo["sensibilite"],
            sensibilite_hyper=hyper["sensibilite"],
            n_hypo=hypo["n_events"],
            n_hyper=hyper["n_events"],
            maes=m,
        )
    return out


def gap_permutation_test(
    report: LopoReport,
    patient_to_group: dict[str, str],
    *,
    metric: str = "mae_model",
    n_permutations: int = 5000,
    seed: int = 0,
) -> dict:
    """L'écart entre groupes dépasse-t-il ce que le hasard produit ?

    On mesure l'écart observé entre le meilleur et le pire groupe, puis on
    rebat les étiquettes de groupe entre patients `n_permutations` fois en
    gardant les tailles de groupe. La p-valeur est la fraction des tirages où
    l'écart au hasard égale ou dépasse l'écart observé.

    Une p-valeur élevée ne prouve pas l'équité : elle dit qu'avec ce nombre de
    patients, on ne peut pas distinguer l'écart du bruit. C'est une nuance à
    tenir dans la présentation.
    """
    vals, labels = [], []
    for f in report.folds:
        g = patient_to_group.get(f.patient)
        if g is None:
            continue
        vals.append(getattr(f, metric))
        labels.append(str(g))
    vals = np.asarray(vals, dtype=float)
    labels = np.asarray(labels)

    uniq = np.unique(labels)
    if len(uniq) < 2 or len(vals) < 4:
        return {"observed_gap": float("nan"), "p_value": float("nan"),
                "n_patients": len(vals), "groups": list(uniq)}

    def _gap(lab):
        means = [vals[lab == g].mean() for g in uniq if (lab == g).sum()]
        return float(max(means) - min(means))

    observed = _gap(labels)
    rng = np.random.default_rng(seed)
    perm = labels.copy()
    hits = 0
    for _ in range(n_permutations):
        rng.shuffle(perm)
        if _gap(perm) >= observed - 1e-12:
            hits += 1
    return {
        "observed_gap": observed,
        "p_value": (hits + 1) / (n_permutations + 1),
        "n_patients": int(len(vals)),
        "groups": [str(g) for g in uniq],
        "means": {str(g): float(vals[labels == g].mean()) for g in uniq},
    }


def print_fairness(
    results: dict[str, SubgroupResult],
    permutation: dict | None = None,
    title: str = "",
) -> None:
    """Affiche le tableau d'équité — la forme attendue dans un rapport."""
    if title:
        print(f"\n{title}")
    print("-" * 78)
    print(f"{'groupe':<14}{'n':>4}{'MAE mod.':>10}{'MAE pers.':>11}"
          f"{'gain':>9}{'gagnes':>8}{'sens. hyper':>13}")
    for r in results.values():
        sh = ("  n/a" if np.isnan(r.sensibilite_hyper)
              else f"{r.sensibilite_hyper * 100:5.1f} %")
        print(f"{r.name:<14}{r.n_patients:>4}{r.mae_model:>10.2f}"
              f"{r.mae_persistence:>11.2f}{r.gain:>+9.2f}"
              f"{r.patients_gagnes:>4}/{r.n_patients:<3}{sh:>13}")

    if permutation and not np.isnan(permutation.get("observed_gap", float("nan"))):
        gap, p = permutation["observed_gap"], permutation["p_value"]
        print("-" * 78)
        print(f"  Ecart max entre groupes       {gap:.2f} mg/dL")
        print(f"  p (permutation des groupes)   {p:.3f}")
        if p >= 0.05:
            print("  -> avec ce nombre de patients, l'ecart ne se distingue pas du bruit")
        else:
            print("  -> ecart superieur a ce que le hasard produit")


def worst_group(results: dict[str, SubgroupResult]) -> SubgroupResult | None:
    """Le groupe le moins bien servi — celui dont il faut parler."""
    if not results:
        return None
    return max(results.values(), key=lambda r: r.mae_model)
