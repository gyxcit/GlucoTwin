"""Tests des couches 0 et 1 : emploi du temps → concepts."""

import math

import pytest

from glucotwin.metabolic_engine import load_activities
from glucotwin.day_concepts import (
    DaySchedule, Meal, ScheduledActivity, compute_day_concepts,
    carb_absorption, dawn_factor,
)


@pytest.fixture(scope="module")
def catalogue():
    return load_activities()


@pytest.fixture
def jour():
    return DaySchedule(
        weight_kg=82.0, wake_h=7.0, bed_h=23.0, stress=0.4, metformin=True,
        meals=[Meal(7.75, 55, 15, 12, 6, 1.0),
               Meal(12.75, 75, 30, 20, 8, 1.1),
               Meal(20.5, 65, 25, 18, 5, 0.9)],
        activities=[ScheduledActivity("MAR04", 8.5, 25),
                    ScheduledActivity("VEL03", 18.0, 45)],
    )


def test_flux_complet_sur_24h(jour, catalogue):
    frames = compute_day_concepts(jour, catalogue)
    assert len(frames) == 289
    assert len(vars(frames[0])) == 14


def test_aucun_concept_degenere(jour, catalogue):
    """Le métabolisme de repos doit être calculé en permanence."""
    frames = compute_day_concepts(jour, catalogue)
    assert all(f.cho_ox_rate_g_min > 0 for f in frames)
    assert all(f.glucose_uptake_mg_min > 0 for f in frames)
    assert all(f.hepatic_output_mg_min > 0 for f in frames)


def test_conservation_des_glucides(jour, catalogue):
    frames = compute_day_concepts(jour, catalogue)
    absorbe = sum(f.carb_ra_g_min * 5 for f in frames)
    ingere = sum(m.carbs_g for m in jour.meals)
    assert abs(absorbe + frames[-1].cob_g - ingere) < 1.0


def test_signes_du_flux_net(jour, catalogue):
    frames = compute_day_concepts(jour, catalogue)
    assert all(abs(f.net_glucose_flux_mg_min) < 2 for f in frames if 0 < f.t_h < 2)
    assert all(f.net_glucose_flux_mg_min > 0 for f in frames if 8.0 < f.t_h < 8.5)
    assert all(f.net_glucose_flux_mg_min < 0 for f in frames if 18.1 < f.t_h < 18.7)


def test_captation_monotone_avec_l_intensite(catalogue):
    """Plus d'effort ne doit jamais consommer moins de glucose."""
    class Fake:
        pass
    prev = None
    for met in [i / 2 for i in range(2, 25)]:
        a = Fake(); a.met = met
        catalogue["TEST"] = a
        d = DaySchedule(weight_kg=82.0, wake_h=7.0, bed_h=23.0, dawn_intensity=0,
                        meals=[], activities=[ScheduledActivity("TEST", 12.0, 60)])
        f = [x for x in compute_day_concepts(d, catalogue)
             if abs(x.t_h - 12.0833) < 1e-3][0]
        if prev is not None:
            assert f.glucose_uptake_mg_min >= prev - 0.2
        prev = f.glucose_uptake_mg_min


def test_deficit_glycogenique_monotone(jour, catalogue):
    g = [f.glycogen_deficit_g for f in compute_day_concepts(jour, catalogue)]
    assert all(g[i] <= g[i + 1] + 1e-9 for i in range(len(g) - 1))
    assert g[0] == 0


@pytest.mark.parametrize("wake,bed,sommeil,dort,eveille", [
    (7.0, 23.0, 8.0, 2.0, 12.0),     # journée normale
    (7.0, 1.0, 6.0, 3.0, 23.0),      # coucher après minuit
    (16.0, 8.0, 8.0, 12.0, 20.0),    # travail de nuit
])
def test_sommeil_circulaire(wake, bed, sommeil, dort, eveille):
    d = DaySchedule(weight_kg=82.0, wake_h=wake, bed_h=bed)
    assert d.sleep_hours == pytest.approx(sommeil)
    assert d.is_asleep(dort)
    assert not d.is_asleep(eveille)


def test_aube_culmine_avant_le_lever():
    for wake in [5.0, 7.0, 8.5]:
        vals = [(h / 10, dawn_factor(h / 10, wake)) for h in range(0, 240)]
        pic = max(vals, key=lambda x: x[1])[0]
        assert abs(pic - (wake - 1.0)) < 0.15


def test_aube_desactivable(jour, catalogue):
    jour.dawn_intensity = 0.0
    assert all(f.dawn_factor == 0 for f in compute_day_concepts(jour, catalogue))


def test_absorption_glucidique_integre_le_repas():
    m = Meal(8.0, 60, gi=1.0)
    total = sum(carb_absorption(m, t)[1] for t in range(1, 600))
    assert total == pytest.approx(60, rel=0.02)


def test_activites_superposees_prennent_le_maximum(catalogue):
    d = DaySchedule(weight_kg=82.0, wake_h=7.0, bed_h=23.0,
                    activities=[ScheduledActivity("MAR04", 10.0, 60),
                                ScheduledActivity("VEL03", 10.5, 30)])
    frames = [f for f in compute_day_concepts(d, catalogue) if 10.6 < f.t_h < 10.9]
    assert all(abs(f.met_now - 8.0) < 0.01 for f in frames)
