"""
Tests de la calibration patient — le problème inverse.

Un ajustement à cinq paramètres trouve toujours *quelque chose*. La question
n'est pas s'il converge, mais si ce qu'il trouve veut dire quelque chose. Ces
tests attaquent donc l'identifiabilité d'abord : sur des données engendrées avec
des paramètres connus, on doit les retrouver. Le reste en découle.
"""

from __future__ import annotations

import numpy as np
import pytest

from glucotwin.calibration import (
    BOUNDS,
    DEFAULT_THETA,
    PARAM_NAMES,
    calibrate_cohort,
    fit_patient,
    simulate_glucose,
    summarize,
)


def _journee(seed=0, n=289, step_min=5):
    """Une journée plausible de branches couche 1 : trois repas, un effort."""
    rng = np.random.default_rng(seed)
    h = np.arange(n) * step_min / 60.0
    ra = np.zeros(n)
    for t0, g in ((8.0, 45.0), (12.5, 70.0), (19.5, 60.0)):
        tp = 0.75
        x = np.clip((h - t0) / tp, 0, None)
        ra += g * 1000.0 * x / (tp * 60.0) * np.exp(-x) * (h >= t0)
    hgp = 150.0 + 30.0 * np.sin(2 * np.pi * (h - 4) / 24.0)
    rd = 180.0 + 250.0 * ((h > 17.5) & (h < 18.5))
    rd += rng.normal(0, 4, n)
    return ra, hgp, rd


def _cohorte_synthetique(n_patients=8, n_days=6, seed=0, bruit=1.5):
    """Cohorte dont on CONNAÎT les paramètres — la seule façon de tester un inverse."""
    import pandas as pd

    rng = np.random.default_rng(seed)
    rows, verite = [], {}
    for i in range(n_patients):
        pid = f"P{i:03d}"
        theta = np.array([
            rng.uniform(0.6, 1.6),      # gain_ra
            rng.uniform(0.7, 1.4),      # gain_hgp
            rng.uniform(0.7, 1.4),      # gain_rd
            rng.uniform(0.008, 0.045),  # k
            rng.uniform(90.0, 150.0),   # g_base
        ])
        weight = float(rng.uniform(60, 110))
        verite[pid] = (theta, weight)
        for d in range(n_days):
            ra, hgp, rd = _journee(seed=seed * 100 + i * 10 + d)
            g = simulate_glucose(theta, ra, hgp, rd, weight,
                                 g0=theta[4] + rng.normal(0, 5))
            g = g + rng.normal(0, bruit, len(g))
            for j in range(len(g)):
                rows.append({
                    "patient": pid, "day": d, "t_h": j * 5 / 60.0,
                    "carb_ra_g_min": ra[j] / 1000.0,
                    "hepatic_output_mg_min": hgp[j],
                    "glucose_uptake_mg_min": rd[j],
                    "glucose": float(g[j]), "weight_kg": weight,
                })
    return pd.DataFrame(rows), verite


# --------------------------------------------------------------------------- #
# 1. Identifiabilité — la question qui décide de tout
# --------------------------------------------------------------------------- #

def test_les_parametres_connus_sont_retrouves():
    """Données engendrées avec θ connu, sans bruit : on doit retomber dessus."""
    theta_vrai = np.array([1.35, 0.85, 1.15, 0.030, 118.0])
    weight = 78.0
    days = []
    for d in range(4):
        ra, hgp, rd = _journee(seed=d)
        g = simulate_glucose(theta_vrai, ra, hgp, rd, weight, g0=118.0)
        days.append((ra, hgp, rd, g))

    theta, rmse, ok = fit_patient(days, weight)
    assert ok
    assert rmse < 1.0                     # reconstruction quasi exacte
    for nom, vrai, est in zip(PARAM_NAMES, theta_vrai, theta):
        rel = abs(est - vrai) / abs(vrai)
        assert rel < 0.15, f"{nom} : {est:.3f} au lieu de {vrai:.3f}"


def test_identifiabilite_resiste_au_bruit_capteur():
    """Avec 3 mg/dL de bruit — l'ordre de grandeur d'un CGM — ça doit tenir."""
    rng = np.random.default_rng(3)
    theta_vrai = np.array([1.10, 1.20, 0.90, 0.022, 128.0])
    weight = 92.0
    days = []
    for d in range(5):
        ra, hgp, rd = _journee(seed=50 + d)
        g = simulate_glucose(theta_vrai, ra, hgp, rd, weight, g0=128.0)
        days.append((ra, hgp, rd, g + rng.normal(0, 3.0, len(g))))

    theta, _, _ = fit_patient(days, weight)
    assert abs(theta[0] - theta_vrai[0]) / theta_vrai[0] < 0.25   # gain_ra
    assert abs(theta[4] - theta_vrai[4]) < 12.0                   # g_base


def test_les_parametres_restent_dans_les_bornes():
    """Sans bornes, l'ajustement compense une branche par une autre."""
    rng = np.random.default_rng(7)
    weight = 80.0
    days = []
    for d in range(3):
        ra, hgp, rd = _journee(seed=d)
        days.append((ra, hgp, rd, rng.normal(140, 40, len(ra))))   # du bruit pur
    theta, _, _ = fit_patient(days, weight)
    for nom, v in zip(PARAM_NAMES, theta):
        lo, hi = BOUNDS[nom]
        assert lo - 1e-9 <= v <= hi + 1e-9, f"{nom} hors bornes : {v}"


# --------------------------------------------------------------------------- #
# 2. Généralisation — calibrer sert-il vraiment ?
# --------------------------------------------------------------------------- #

def test_la_calibration_bat_les_parametres_de_population():
    """Sur une cohorte réellement hétérogène, le sur-mesure doit gagner."""
    df, _ = _cohorte_synthetique(n_patients=8, n_days=6, seed=1)
    res = calibrate_cohort(df, n_days_fit=3, verbose=False)
    s = summarize(res)
    assert s["n_patients"] == 8
    assert s["gain_vs_population"] > 0
    assert s["patients_ameliores"] >= 6


def test_aucune_journee_de_test_ne_sert_a_l_ajustement():
    """Le découpage est temporel : trois jours pour ajuster, le reste pour tester."""
    df, _ = _cohorte_synthetique(n_patients=4, n_days=7, seed=2)
    res = calibrate_cohort(df, n_days_fit=3, verbose=False)
    for r in res:
        assert r.n_days_fit == 3
        assert r.n_days_test == 4


def test_le_gain_disparait_sur_une_cohorte_homogene():
    """Contre-épreuve : si tous les patients sont identiques, calibrer n'apporte rien.

    C'est le test qui empêche de crier victoire — un protocole qui trouve un
    gain même quand il n'y en a pas ne prouve rien quand il en trouve un.
    """
    import pandas as pd

    rng = np.random.default_rng(11)
    theta = np.array([1.0, 1.0, 1.0, 0.025, 120.0])
    rows = []
    for i in range(6):
        pid, weight = f"P{i:03d}", 82.0
        for d in range(6):
            ra, hgp, rd = _journee(seed=i * 10 + d)
            g = simulate_glucose(theta, ra, hgp, rd, weight, g0=120.0)
            g = g + rng.normal(0, 2.0, len(g))
            for j in range(len(g)):
                rows.append({"patient": pid, "day": d, "t_h": j * 5 / 60.0,
                             "carb_ra_g_min": ra[j] / 1000.0,
                             "hepatic_output_mg_min": hgp[j],
                             "glucose_uptake_mg_min": rd[j],
                             "glucose": float(g[j]), "weight_kg": weight})
    res = calibrate_cohort(pd.DataFrame(rows), n_days_fit=3, verbose=False)
    s = summarize(res)
    assert abs(s["gain_vs_population"]) < 1.5      # rien de notable


# --------------------------------------------------------------------------- #
# 3. Le modèle direct lui-même
# --------------------------------------------------------------------------- #

def test_un_repas_fait_monter_la_glycemie():
    ra, hgp, rd = _journee(seed=0)
    g = simulate_glucose(DEFAULT_THETA, ra, hgp, rd, 80.0, g0=110.0)
    apres_petit_dej = g[int(9.0 * 12)]
    avant = g[int(7.5 * 12)]
    assert apres_petit_dej > avant + 5


def test_la_glycemie_reste_physiologique():
    rng = np.random.default_rng(5)
    ra, hgp, rd = _journee(seed=1)
    for _ in range(20):
        theta = np.array([rng.uniform(*BOUNDS[n]) for n in PARAM_NAMES])
        g = simulate_glucose(theta, ra * 3, hgp * 2, rd * 2, 60.0, g0=200.0)
        assert np.all(np.isfinite(g))
        assert g.min() >= 20.0 and g.max() <= 600.0


def test_sans_apport_la_glycemie_rejoint_l_equilibre():
    n = 289
    zero = np.zeros(n)
    theta = np.array([1.0, 0.0, 0.0, 0.03, 100.0])     # ni repas ni foie ni captation
    g = simulate_glucose(theta, zero, zero, zero, 80.0, g0=250.0)
    assert g[-1] == pytest.approx(100.0, abs=3.0)
