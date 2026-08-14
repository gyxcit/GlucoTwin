"""
Tests de l'adaptateur CGMacros — sur un faux jeu conforme au dictionnaire.

On ne peut pas committer les vraies données (CC BY-NC-SA). On fabrique donc un
jeu au **schéma exact** de CGMacros et on vérifie que l'adaptateur en tire ce
qu'il faut : la bonne glycémie, le bon MET, les repas pondérés par la part
réellement consommée, et une fenêtre de sommeil plausible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from glucotwin.data.cgmacros import (
    MET_SCALE,
    resolve_weight_kg,
    ParticipantMeta,
    build_cohort_from_cgmacros,
    find_participant_files,
    infer_sleep_window,
    load_participant,
)
from glucotwin.layer2.features import CONCEPT_COLS


def _fake_participant(n_days=3, pid=1, seed=0):
    """Un CSV à la minute, aux colonnes exactes du DataDictionary."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_days):
        base = pd.Timestamp("2024-03-01") + pd.Timedelta(days=d)
        for minute in range(24 * 60):
            t = base + pd.Timedelta(minutes=minute)
            h = minute / 60.0
            asleep = h < 6.5 or h >= 23.0
            met = 0.95 if asleep else 1.3
            if 9.0 <= h < 9.75:                       # marche du matin
                met = 4.3
            if 18.0 <= h < 18.5:                      # vélo du soir
                met = 6.8
            glucose = (
                110 + 25 * np.sin(2 * np.pi * (h - 8) / 24)
                + rng.normal(0, 2)
            )
            row = {
                "Timestamp": t.strftime("%m/%d/%Y %H:%M"),
                "Libre GL": round(glucose + rng.normal(0, 4), 1),
                "Dexcom GL": round(glucose, 1),
                "HR": 52 if asleep else 70,
                "Calories (Activity)": round(met * 1.2, 2),
                "Mets": round(met * MET_SCALE),
                "Meal Type": "",
                "Calories": "",
                "Carbs": "",
                "Protein": "",
                "Fat": "",
                "Fiber": "",
                "Amount Consumed": "",
                "Image Path": "",
            }
            # trois repas, dont un à moitié terminé
            for hh, kind, carbs, amount in (
                (8.0, "Breakfast", 50, 100),
                (12.5, "Lunch", 80, 50),
                (19.5, "Dinner", 70, 100),
            ):
                if abs(h - hh) < 1e-9:
                    row |= {"Meal Type": kind, "Calories": carbs * 6,
                            "Carbs": carbs, "Protein": 20, "Fat": 15,
                            "Fiber": 6, "Amount Consumed": amount}
            rows.append(row)
    return pd.DataFrame(rows)


@pytest.fixture
def fake_root(tmp_path):
    for pid in (1, 2, 3):
        d = tmp_path / f"CGMacros-{pid:03d}"
        d.mkdir()
        _fake_participant(pid=pid, seed=pid).to_csv(
            d / f"CGMacros-{pid:03d}.csv", index=False
        )
    pd.DataFrame({
        "subject": [1, 2, 3],
        "Age": [54, 61, 38],
        "Body weight ": [82.0, 95.5, 68.0],
        "BMI": [27.7, 31.2, 22.4],
        "A1c PDL (Lab)": [6.8, 6.0, 5.2],
    }).to_csv(tmp_path / "bio.csv", index=False)
    return tmp_path


# --------------------------------------------------------------------------- #

def test_reperage_des_fichiers(fake_root):
    files = find_participant_files(fake_root)
    assert set(files) == {"P001", "P002", "P003"}


def test_glycemie_dexcom_preferee(fake_root):
    """Le Dexcom est au pas de 5 min : c'est lui qui doit être retenu."""
    path = fake_root / "CGMacros-001" / "CGMacros-001.csv"
    raw = pd.read_csv(path)
    days = load_participant(path, ParticipantMeta("P001", weight_kg=82.0))
    assert len(days) == 3
    _, _, g_grid, _, _ = days[0]
    # la grille doit coller au Dexcom, pas au Libre (bruité de 4 mg/dL)
    dex = pd.to_numeric(raw["Dexcom GL"])[: 24 * 60].to_numpy()
    assert abs(g_grid.mean() - dex.mean()) < 1.5


def test_mets_divises_par_dix(fake_root):
    """La colonne `Mets` est stockée ×10 — l'oublier fausserait tout."""
    path = fake_root / "CGMacros-001" / "CGMacros-001.csv"
    _, frames, _, _, _ = load_participant(
        path, ParticipantMeta("P001", weight_kg=82.0)
    )[0]
    met = np.array([f.met_now for f in frames])
    assert met.max() == pytest.approx(6.8, abs=0.1)     # le vélo du soir
    assert 0.9 <= met.min() <= 1.0                       # le sommeil


def test_repas_ponderes_par_la_part_consommee(fake_root):
    """Un déjeuner mangé à moitié doit peser 40 g, pas 80."""
    path = fake_root / "CGMacros-001" / "CGMacros-001.csv"
    _, frames, _, _, _ = load_participant(
        path, ParticipantMeta("P001", weight_kg=82.0)
    )[0]
    # COB juste après le déjeuner de 12h30 : le pic d'absorption suit le repas
    cob = {round(f.t_h, 2): f.cob_g for f in frames}
    midi = max(v for k, v in cob.items() if 12.5 <= k <= 13.5)
    matin = max(v for k, v in cob.items() if 8.0 <= k <= 9.0)
    # 80 g × 50 % = 40 g contre 50 g le matin → le midi doit peser MOINS
    assert midi < matin


def test_sommeil_deduit_de_l_intensite():
    hours = np.arange(289) * 5 / 60.0
    met = np.where((hours < 6.5) | (hours >= 23.0), 0.95, 1.3)
    wake, bed = infer_sleep_window(hours, met)
    assert wake == pytest.approx(6.5, abs=0.6)
    assert bed == pytest.approx(23.0, abs=0.6)


def test_sommeil_retombe_sur_le_defaut_si_illisible():
    hours = np.arange(289) * 5 / 60.0
    met = np.full(289, 2.5)                 # agité toute la nuit
    assert infer_sleep_window(hours, met) == (7.0, 23.0)


def test_cohorte_a_la_forme_attendue(fake_root):
    """La table réelle doit être consommable par features.py sans retouche."""
    df = build_cohort_from_cgmacros(fake_root, verbose=False)
    for col in CONCEPT_COLS + ["patient", "day", "glucose", "weight_kg", "t_h"]:
        assert col in df.columns, col
    assert df.patient.nunique() == 3
    assert df.groupby("patient").day.nunique().eq(3).all()
    assert df.glucose.between(40, 400).all()


def test_bio_lu_et_groupe_deduit(fake_root):
    df = build_cohort_from_cgmacros(fake_root, verbose=False)
    poids = df.groupby("patient").weight_kg.first()
    assert poids["P002"] == pytest.approx(95.5)
    groupes = df.groupby("patient").group.first()
    assert groupes["P001"] == "diabete"        # A1c 6,8
    assert groupes["P002"] == "prediabete"     # A1c 6,0
    assert groupes["P003"] == "sain"           # A1c 5,2


def test_journees_trop_trouees_ecartees(tmp_path):
    """Une journée à moitié absente ne doit pas être interpolée en douce."""
    d = tmp_path / "CGMacros-009"
    d.mkdir()
    df = _fake_participant(n_days=2, pid=9)
    # on efface 60 % du second jour
    jour2 = df.index[24 * 60:]
    df.loc[jour2[: int(len(jour2) * 0.6)], ["Dexcom GL", "Libre GL"]] = np.nan
    df.to_csv(d / "CGMacros-009.csv", index=False)
    days = load_participant(
        d / "CGMacros-009.csv", ParticipantMeta("P009"), min_coverage=0.8
    )
    assert len(days) == 1


def test_le_pipeline_ne_fuit_pas_le_groupe(fake_root):
    """`group` et `a1c` ne doivent jamais devenir des features."""
    from glucotwin.layer2.features import build_features

    df = build_cohort_from_cgmacros(fake_root, verbose=False)
    X, y, groups, g_now, names = build_features(df, horizon_min=30)
    assert "group" not in names and "a1c" not in names
    assert X.shape[0] == len(y) == len(groups) == len(g_now)


# --------------------------------------------------------------------------- #
# Unités : CGMacros est en livres et en pouces
# --------------------------------------------------------------------------- #

def test_poids_en_livres_converti():
    """Le vrai bio.csv : 133,8 lb / 65 in / IMC 22,27 → 60,7 kg."""
    assert resolve_weight_kg(133.8, 65.0, 22.265) == pytest.approx(60.7, abs=0.3)
    assert resolve_weight_kg(262.6, 66.0, 42.39) == pytest.approx(119.1, abs=0.5)


def test_poids_deja_en_kg_laisse_intact():
    """82 kg pour 1,80 m, IMC 25,3 : rien à convertir."""
    assert resolve_weight_kg(82.0, 180.0, 25.3) == pytest.approx(82.0, abs=0.5)


def test_poids_sans_imc_retombe_sur_la_plage():
    assert resolve_weight_kg(250.0, None, None) == pytest.approx(113.4, abs=0.5)
    assert resolve_weight_kg(78.0, None, None) == pytest.approx(78.0)


def test_poids_absent_donne_le_defaut():
    assert resolve_weight_kg(None, 65.0, 22.0) == 82.0
    assert resolve_weight_kg(0.0, 65.0, 22.0) == 82.0


def test_une_erreur_d_unite_serait_enorme():
    """Garde-fou : prendre les livres pour des kg gonfle le poids de 120 %."""
    vrai = resolve_weight_kg(262.6, 66.0, 42.39)
    naif = 262.6
    assert naif / vrai > 2.0


# --------------------------------------------------------------------------- #
# Reconstruction des METs depuis les calories
# --------------------------------------------------------------------------- #

def test_met_reconstruit_depuis_les_calories():
    """Fitbit calcule les calories DEPUIS le MET : ancrer le repos les restitue."""
    from glucotwin.data.cgmacros import met_from_activity_calories

    met_vrai = np.repeat([1.0, 1.0, 1.3, 4.3, 6.8], 200)
    k = 0.0175 * 82.0                      # kcal/min par MET pour 82 kg
    est = met_from_activity_calories(met_vrai * k)
    assert np.nanmax(np.abs(est - met_vrai)) < 0.01


def test_met_reconstruit_insensible_au_poids():
    """Le facteur d'échelle disparaît à l'ancrage — le poids n'a pas à être connu."""
    from glucotwin.data.cgmacros import met_from_activity_calories

    met_vrai = np.repeat([1.0, 1.0, 2.0, 5.0], 300)
    a = met_from_activity_calories(met_vrai * 0.0175 * 55.0)
    b = met_from_activity_calories(met_vrai * 0.0175 * 120.0)
    assert np.allclose(a, b, atol=1e-9)


def test_met_absent_si_trop_peu_de_calories():
    from glucotwin.data.cgmacros import met_from_activity_calories

    assert np.isnan(met_from_activity_calories(np.array([1.0, 2.0, 3.0]))).all()


def test_repli_sur_les_calories_quand_METs_manque(tmp_path):
    """Onze participants réels n'ont pas la colonne METs — ils doivent passer."""
    d = tmp_path / "CGMacros-011"
    d.mkdir()
    df = _fake_participant(n_days=2, pid=11)
    df["Calories (Activity)"] = df["Mets"] / MET_SCALE * 0.0175 * 82.0
    df = df.drop(columns=["Mets"])          # export Fitbit sans METs
    df.to_csv(d / "CGMacros-011.csv", index=False)

    days = load_participant(d / "CGMacros-011.csv",
                            ParticipantMeta("P011", weight_kg=82.0))
    assert len(days) == 2
    _, frames, _, _, source = days[0]
    assert source == "calories"
    met = np.array([f.met_now for f in frames])
    assert met.max() == pytest.approx(6.8, abs=0.15)   # le vélo du soir retrouvé
