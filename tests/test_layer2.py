"""Tests de la couche 2 : features et évaluation."""

import numpy as np
import pytest

from glucotwin.layer2.cohort import build_cohort
from glucotwin.layer2.features import build_features
from glucotwin.layer2.evaluation import (
    conformal_quantile, coverage, event_detection, zone_errors, lopo_evaluate,
)


@pytest.fixture(scope="module")
def cohorte():
    return build_cohort(n_patients=6, days_per_patient=2, seed=1)


def test_cohorte_realiste(cohorte):
    assert cohorte.patient.nunique() == 6
    assert 70 < cohorte.glucose.mean() < 220
    assert cohorte.glucose.between(40, 400).all()


def test_features_sans_fuite_temporelle(cohorte):
    X, y, groups, g_now, names = build_features(cohorte, horizon_min=30)
    assert X.shape[1] == len(names)
    assert len(y) == len(groups) == len(g_now) == X.shape[0]
    assert not np.isnan(X).any()


def test_cible_delta_et_niveau_coherentes(cohorte):
    _, y_d, _, now_d, _ = build_features(cohorte, horizon_min=30, target="delta")
    _, y_l, _, now_l, _ = build_features(cohorte, horizon_min=30, target="level")
    assert np.allclose(now_d + y_d, y_l)


def test_quantile_conforme_garantit_la_couverture():
    rng = np.random.default_rng(0)
    res = np.abs(rng.normal(0, 10, 5000))
    q = conformal_quantile(res, alpha=0.1)
    assert coverage(rng.normal(0, 10, 5000), -q, q) > 0.85


def test_detection_evenement():
    vrai = np.array([60.0, 80.0, 65.0, 200.0])
    pred = np.array([65.0, 90.0, 75.0, 190.0])
    d = event_detection(vrai, pred, threshold=70, below=True)
    assert d["n_events"] == 2 and d["tp"] == 1 and d["fn"] == 1


def test_zones_partitionnent_les_donnees():
    vrai = np.array([50.0, 85.0, 140.0, 200.0, 300.0])
    z = zone_errors(vrai, vrai)
    assert sum(v["n"] for v in z.values()) == len(vrai)


def test_lopo_ne_voit_jamais_le_patient_de_test(cohorte):
    from sklearn.linear_model import Ridge
    X, y, groups, g_now, _ = build_features(cohorte, horizon_min=30)
    rep = lopo_evaluate(X, y, groups, g_now, lambda: Ridge(alpha=1.0),
                        max_patients=3, seed=0)
    assert len(rep.folds) == 3
    s = rep.summary()
    assert s["n_patients"] == 3
    assert np.isfinite(s["mae_model"]) and np.isfinite(s["mae_persistence"])
