"""
Tests de l'analyse d'équité.

Le point délicat n'est pas de calculer des moyennes par groupe : c'est de ne pas
crier à l'inéquité devant du bruit. Ces tests vérifient les deux directions —
un écart fabriqué doit être détecté, et une absence d'écart ne doit pas l'être.
"""

from __future__ import annotations

import numpy as np
import pytest

from glucotwin.layer2.evaluation import FoldResult, LopoReport
from glucotwin.layer2.fairness import (
    gap_permutation_test,
    subgroup_report,
    worst_group,
)


def _report(maes, n_test=100, seed=0):
    """Fabrique un rapport LOPO où chaque patient a la MAE demandée."""
    rng = np.random.default_rng(seed)
    rep = LopoReport()
    trues, preds, pers = [], [], []
    for i, m in enumerate(maes):
        pid = f"P{i:03d}"
        rep.folds.append(FoldResult(
            patient=pid, n_test=n_test,
            mae_model=float(m), mae_persistence=float(m) + 2.0,
            rmse_model=float(m) * 1.3, rmse_persistence=float(m) * 1.5,
            interval_width=40.0, interval_coverage=0.9,
        ))
        t = rng.normal(140, 40, n_test)
        trues.append(t)
        preds.append(t + rng.choice([-m, m], n_test))
        pers.append(t + rng.choice([-m - 2, m + 2], n_test))
    rep.y_true_abs = np.concatenate(trues)
    rep.y_pred_abs = np.concatenate(preds)
    rep.y_pers_abs = np.concatenate(pers)
    return rep


def _groups(n_per, names=("sain", "prediabete", "diabete")):
    out, k = {}, 0
    for name, n in zip(names, n_per):
        for _ in range(n):
            out[f"P{k:03d}"] = name
            k += 1
    return out


# --------------------------------------------------------------------------- #

def test_decoupage_par_groupe():
    maes = [10.0] * 5 + [14.0] * 5 + [18.0] * 5
    rep = _report(maes)
    res = subgroup_report(rep, _groups((5, 5, 5)))
    assert set(res) == {"sain", "prediabete", "diabete"}
    assert res["sain"].mae_model == pytest.approx(10.0)
    assert res["diabete"].mae_model == pytest.approx(18.0)
    assert all(r.n_patients == 5 for r in res.values())


def test_le_gain_reste_coherent_par_groupe():
    """La persistance est fabriquée à +2 mg/dL : le gain doit valoir 2 partout."""
    rep = _report([10.0] * 4 + [20.0] * 4)
    res = subgroup_report(rep, _groups((4, 4), names=("a", "b")))
    for r in res.values():
        assert r.gain == pytest.approx(2.0)
        assert r.patients_gagnes == r.n_patients


def test_groupe_trop_petit_ecarte():
    rep = _report([10.0] * 6 + [12.0] * 2)
    res = subgroup_report(rep, _groups((6, 2), names=("gros", "minuscule")))
    assert "gros" in res and "minuscule" not in res


def test_patient_sans_groupe_ignore():
    rep = _report([10.0] * 6)
    g = _groups((3,), names=("a",))          # seuls P000..P002 ont un groupe
    res = subgroup_report(rep, g)
    assert list(res) == ["a"] and res["a"].n_patients == 3


def test_ecart_franc_detecte():
    """8 vs 20 mg/dL sur 8 patients par groupe : le hasard ne fait pas ça."""
    rep = _report([8.0] * 8 + [20.0] * 8)
    perm = gap_permutation_test(rep, _groups((8, 8), names=("a", "b")),
                                n_permutations=2000, seed=1)
    assert perm["observed_gap"] == pytest.approx(12.0)
    assert perm["p_value"] < 0.01


def test_absence_d_ecart_non_signalee():
    """Même population coupée en deux : la p-valeur ne doit pas être petite."""
    rng = np.random.default_rng(3)
    maes = list(rng.normal(12.0, 2.0, 16))
    rep = _report(maes)
    perm = gap_permutation_test(rep, _groups((8, 8), names=("a", "b")),
                                n_permutations=2000, seed=2)
    assert perm["p_value"] > 0.05


def test_petit_effectif_reste_prudent():
    """Trois patients par groupe : même un écart visible ne doit pas convaincre.

    C'est le garde-fou qui compte pour ce projet : les sous-groupes de CGMacros
    font 14 à 16 patients, et il faut savoir dire quand on ne peut pas conclure.
    """
    rep = _report([11.0, 12.0, 13.0] + [15.0, 16.0, 17.0])
    perm = gap_permutation_test(rep, _groups((3, 3), names=("a", "b")),
                                n_permutations=2000, seed=4)
    assert perm["p_value"] > 0.02


def test_pire_groupe_identifie():
    rep = _report([9.0] * 4 + [21.0] * 4)
    res = subgroup_report(rep, _groups((4, 4), names=("bon", "mauvais")))
    assert worst_group(res).name == "mauvais"


def test_un_seul_groupe_pas_de_test():
    rep = _report([10.0] * 6)
    perm = gap_permutation_test(rep, _groups((6,), names=("seul",)))
    assert np.isnan(perm["p_value"])
