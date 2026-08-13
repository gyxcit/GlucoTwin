"""Tests du moteur métabolique (couche 1)."""

import math

import pytest

from glucotwin.metabolic_engine import (
    load_activities, vo2_from_met, rer_from_met, frayn_oxidation,
    compute_metabolic_state,
)

W = 82.0


@pytest.fixture(scope="module")
def catalogue():
    return load_activities()


def test_catalogue_charge(catalogue):
    assert len(catalogue) > 70
    assert catalogue["MAR04"].met == pytest.approx(4.3)


def test_energie_coherente_avec_la_formule_met(catalogue):
    """Frayn et la formule MET classique doivent concorder à quelques % près."""
    for code in ["MAR04", "VEL03", "CRS02"]:
        a = catalogue[code]
        st = compute_metabolic_state(a, 30, W)
        classique = a.met * 3.5 * W / 200.0 * 30
        assert abs(st.energy_kcal - classique) / classique < 0.06


def test_rer_dans_les_bornes_physiologiques():
    for met in [0.9, 1.3, 4.0, 8.0, 12.0]:
        assert 0.70 <= rer_from_met(met) <= 1.00


def test_oxydation_croissante_avec_l_intensite():
    prev = -1.0
    for met in [1.0, 2.0, 4.0, 6.0, 8.0, 10.0]:
        vo2 = vo2_from_met(met, W)
        cho, _ = frayn_oxidation(vo2, rer_from_met(met) * vo2)
        assert cho > prev
        prev = cho


def test_incertitude_encadre_l_estimation(catalogue):
    st = compute_metabolic_state(catalogue["MAR04"], 30, W)
    assert st.cho_oxidized_g_low < st.cho_oxidized_g < st.cho_oxidized_g_high
    assert st.cho_uncertainty_pct > 0
