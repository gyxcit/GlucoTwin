"""
Tests de la couche 3 — probabilités de risque.

Une probabilité est plus facile à falsifier qu'une prédiction : on connaît sa
valeur attendue. Ces tests s'appuient là-dessus — on fabrique des situations
dont on sait ce que le module doit répondre, y compris quand il doit répondre
« je n'apporte rien ».
"""

from __future__ import annotations

import numpy as np
import pytest

from glucotwin.layer2.risk import (
    IsotonicCalibrator,
    auroc,
    average_precision,
    brier_score,
    brier_skill_score,
    expected_calibration_error,
    reliability_curve,
    residual_risk,
)


# --- métriques -------------------------------------------------------------- #

def test_brier_parfait_et_pire():
    y = np.array([0, 1, 1, 0])
    assert brier_score(y, y.astype(float)) == 0.0
    assert brier_score(y, 1.0 - y) == 1.0


def test_climatologie_a_un_gain_nul():
    """Annoncer le taux de base partout : ni mieux ni pire que la référence."""
    rng = np.random.default_rng(0)
    y = (rng.random(5000) < 0.12).astype(int)
    p = np.full(len(y), y.mean())
    assert brier_skill_score(y, p) == pytest.approx(0.0, abs=1e-9)


def test_un_modele_inutile_a_un_gain_negatif():
    rng = np.random.default_rng(1)
    y = (rng.random(4000) < 0.1).astype(int)
    p = rng.random(4000)                       # probabilites au hasard
    assert brier_skill_score(y, p) < 0


def test_auroc_bornes():
    y = np.array([0, 0, 1, 1])
    assert auroc(y, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert auroc(y, np.array([0.9, 0.8, 0.2, 0.1])) == pytest.approx(0.0)
    assert auroc(y, np.array([0.5, 0.5, 0.5, 0.5])) == pytest.approx(0.5)


def test_auroc_indefini_sans_evenement():
    assert np.isnan(auroc(np.zeros(10), np.random.random(10)))


def test_average_precision_vaut_le_taux_de_base_au_hasard():
    rng = np.random.default_rng(2)
    y = (rng.random(20000) < 0.05).astype(int)
    ap = average_precision(y, rng.random(20000))
    assert ap == pytest.approx(0.05, abs=0.02)


def test_calibration_parfaite_a_une_ece_nulle():
    rng = np.random.default_rng(3)
    p = rng.random(40000)
    y = (rng.random(40000) < p).astype(int)     # calibre par construction
    assert expected_calibration_error(y, p) < 0.02


def test_ece_detecte_la_surconfiance():
    rng = np.random.default_rng(4)
    p_true = rng.random(20000)
    y = (rng.random(20000) < p_true).astype(int)
    p_over = np.clip(p_true + 0.25, 0, 1)       # annonce systematiquement trop
    assert expected_calibration_error(y, p_over) > 0.15


def test_courbe_de_fiabilite_compte_tout():
    rng = np.random.default_rng(5)
    p = rng.random(1000)
    y = (rng.random(1000) < p).astype(int)
    _, _, counts = reliability_curve(y, p, n_bins=10)
    assert counts.sum() == 1000


# --- probabilité résiduelle ------------------------------------------------- #

def test_probabilite_residuelle_lit_bien_la_distribution():
    """Résidus uniformes sur [-50, +50], prédiction à 180 : P(>180) = 50 %."""
    residuals = np.linspace(-50, 50, 1001)
    p = residual_risk(np.array([180.0]), residuals, 180.0, above=True)
    assert p[0] == pytest.approx(0.5, abs=0.01)


def test_probabilite_croit_avec_la_prediction():
    residuals = np.random.default_rng(6).normal(0, 30, 4000)
    preds = np.array([120.0, 150.0, 180.0, 210.0])
    p = residual_risk(preds, residuals, 180.0, above=True)
    assert np.all(np.diff(p) > 0)
    assert p[0] < 0.05 and p[-1] > 0.8


def test_le_risque_survit_la_ou_le_seuil_echoue():
    """Le cœur du module.

    Prédiction à 165 mg/dL : le seuillage dit « pas d'hyperglycémie », donc
    sensibilité nulle. Mais avec 40 mg/dL de dispersion, la probabilité réelle
    de dépasser 180 est loin d'être négligeable — et c'est cette information
    que la couche 3 récupère.
    """
    residuals = np.random.default_rng(7).normal(0, 40, 5000)
    p = residual_risk(np.array([165.0]), residuals, 180.0, above=True)[0]
    assert 0.25 < p < 0.50          # loin de 0, loin de la certitude


def test_sens_inverse_pour_l_hypoglycemie():
    residuals = np.random.default_rng(8).normal(0, 20, 4000)
    preds = np.array([60.0, 90.0])
    p = residual_risk(preds, residuals, 70.0, above=False)
    assert p[0] > p[1]


# --- calibration isotonique -------------------------------------------------- #

def test_isotonique_corrige_un_biais_systematique():
    rng = np.random.default_rng(9)
    p_true = rng.random(6000)
    y = (rng.random(6000) < p_true).astype(int)
    p_biaise = np.clip(p_true * 0.5, 0, 1)       # sous-estime d'un facteur deux
    cal = IsotonicCalibrator().fit(p_biaise, y)
    avant = expected_calibration_error(y, p_biaise)
    apres = expected_calibration_error(y, cal.predict(p_biaise))
    assert apres < avant / 2


def test_isotonique_ne_gagne_rien_hors_echantillon():
    """Calibrer ne doit pas améliorer le classement sur des données neuves.

    Piège subtil : **en in-sample, la régression isotonique fait légèrement
    monter l'AUROC**. Elle aplatit les plages où la relation observée n'est pas
    monotone, c'est-à-dire là où le score se trompait d'ordre, et transforme
    ces paires mal classées en ex aequo — ce qui rapporte un demi-point au lieu
    de zéro. C'est de la sur-adaptation, pas de la discrimination.

    D'où la règle tenue dans `lopo_risk_evaluate` : le calibrateur est ajusté
    sur des patients de calibration, jamais sur le patient évalué. Hors
    échantillon, le gain doit disparaître.
    """
    rng = np.random.default_rng(10)
    p_fit, p_test = rng.random(4000), rng.random(4000)
    y_fit = (rng.random(4000) < p_fit).astype(int)
    y_test = (rng.random(4000) < p_test).astype(int)

    cal = IsotonicCalibrator().fit(p_fit, y_fit)
    avant = auroc(y_test, p_test)
    apres = auroc(y_test, cal.predict(p_test))
    assert apres <= avant + 0.01          # aucun gain reel de classement
    assert apres > avant - 0.05           # et pas de degradation notable


def test_isotonique_sur_adapte_en_in_sample():
    """Le pendant du test precedent : on documente l'effet plutot que le nier."""
    rng = np.random.default_rng(10)
    p = rng.random(3000)
    y = (rng.random(3000) < p).astype(int)
    cal = IsotonicCalibrator().fit(p, y)
    assert auroc(y, cal.predict(p)) >= auroc(y, p)


def test_isotonique_sans_donnees_ne_casse_rien():
    cal = IsotonicCalibrator().fit(np.array([0.3, 0.4]), np.array([0, 1]))
    p = np.array([0.2, 0.9])
    assert np.allclose(cal.predict(p), p)       # renvoie l'entree telle quelle


def test_isotonique_sans_evenement_ne_casse_rien():
    p = np.random.default_rng(11).random(200)
    cal = IsotonicCalibrator().fit(p, np.zeros(200))
    assert np.allclose(cal.predict(p), p)


# --- bout en bout ------------------------------------------------------------ #

def test_lopo_risque_a_court_horizon():
    """À 30 min, la probabilité doit être informative ET battre la climatologie."""
    from glucotwin.layer2.cohort import build_cohort
    from glucotwin.layer2.features import build_features
    from glucotwin.layer2.models import model_zoo
    from glucotwin.layer2.risk import lopo_risk_evaluate

    df = build_cohort(n_patients=8, days_per_patient=3, seed=3)
    X, y, groups, g_now, _ = build_features(df, horizon_min=30)
    rep = lopo_risk_evaluate(
        X, y, groups, g_now, model_zoo()["hgb"],
        threshold=180.0, above=True, seed=1,
    )
    assert rep.n_events > 50
    assert rep.auroc > 0.7                      # classement, moyenne par patient
    assert rep.brier_skill > 0                  # bat « ca arrive x % du temps »
    assert 0.0 <= rep.ece <= 1.0
    assert rep.ap > rep.base_rate               # mieux que le hasard


def test_le_classement_survit_a_l_effondrement_du_seuil():
    """Le résultat du module, tenu comme un test.

    À 120 min, la détection par seuil tombe à zéro : le modèle ne prédit plus
    jamais au-dessus de 180. La probabilité calibrée, elle, continue de classer
    les instants à risque au-dessus des autres. C'est une récupération
    partielle — le classement survit, pas la quantification (voir le gain sur
    la climatologie, qui devient négatif à long horizon).
    """
    from glucotwin.layer2.cohort import build_cohort
    from glucotwin.layer2.features import build_features
    from glucotwin.layer2.models import model_zoo
    from glucotwin.layer2.risk import lopo_risk_evaluate

    df = build_cohort(n_patients=10, days_per_patient=4, seed=5)
    X, y, groups, g_now, _ = build_features(df, horizon_min=120)
    rep = lopo_risk_evaluate(
        X, y, groups, g_now, model_zoo()["hgb"],
        threshold=180.0, above=True, seed=1,
    )
    if rep.n_events < 50:
        import pytest as _p
        _p.skip("pas assez d'evenements dans cette cohorte")
    assert rep.sensibilite_seuil < 0.15         # le seuil ne detecte quasi rien
    assert rep.auroc > 0.55                     # le classement, lui, tient
    assert rep.ap > rep.base_rate               # et bat le hasard
