"""
Cohorte virtuelle — génération de données synthétiques multi-patients.

Sert à **valider le logiciel**, pas la science : on vérifie que la chaîne
concepts → features → modèle → évaluation fonctionne de bout en bout, avant de
la brancher sur CGMacros.

Pour que le test ne soit pas circulaire, la glycémie n'est PAS une fonction
directe des concepts. Elle est intégrée dans le temps avec :

- une **clairance dépendante de la glycémie** (rétroaction non linéaire absente
  des concepts — le modèle doit l'apprendre depuis l'historique glycémique) ;
- une **variabilité inter-patient** sur tous les paramètres physiologiques ;
- des **collations non déclarées**, invisibles des concepts → plancher d'erreur
  irréductible, comme dans la vraie vie ;
- un **bruit de capteur** réaliste.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..day_concepts import (
    DaySchedule,
    Meal,
    ScheduledActivity,
    compute_day_concepts,
)
from ..metabolic_engine import load_activities

#: Volume de distribution du glucose (dL/kg).
GLUCOSE_SPACE_DL_PER_KG = 2.0

#: Codes d'activité utilisés pour tirer des journées plausibles.
ACTIVITY_POOL = [
    "MAR03", "MAR04", "MAR07", "VEL01", "VEL03", "CRS01",
    "FIT04", "FIT05", "DOM03", "JAR02", "SED03", "TRV02",
]


@dataclass
class PatientParams:
    """Physiologie propre à un patient virtuel."""

    pid: str
    weight_kg: float
    baseline_glucose: float      # glycémie d'équilibre à jeun
    clearance: float             # vitesse de retour vers l'équilibre (1/min)
    sensitivity: float           # gain du flux net sur la glycémie
    dawn_intensity: float
    fitness: float
    metformin: bool
    stress: float
    wake_h: float
    bed_h: float


def sample_patient(rng: np.random.Generator, idx: int) -> PatientParams:
    """Tire un patient virtuel avec une physiologie plausible et variée."""
    return PatientParams(
        pid=f"P{idx:03d}",
        weight_kg=float(rng.uniform(58, 118)),
        baseline_glucose=float(rng.uniform(88, 148)),
        clearance=float(rng.uniform(0.030, 0.085)),
        sensitivity=float(rng.uniform(0.60, 1.45)),
        dawn_intensity=float(rng.uniform(0.0, 1.6)),
        fitness=float(rng.uniform(0.85, 1.25)),
        metformin=bool(rng.random() < 0.65),
        stress=float(rng.uniform(0.05, 0.85)),
        wake_h=float(rng.uniform(5.5, 8.5)),
        bed_h=float(rng.uniform(21.5, 24.5)) % 24.0,
    )


def sample_day(rng: np.random.Generator, p: PatientParams) -> DaySchedule:
    """Tire une journée : trois repas décalés et une à trois activités."""
    meals = []
    for anchor, carbs in ((p.wake_h + 0.8, 55), (12.7, 75), (20.0, 65)):
        meals.append(
            Meal(
                time_h=float(np.clip(anchor + rng.normal(0, 0.7), 4.5, 23.0)),
                carbs_g=float(max(15, rng.normal(carbs, 20))),
                protein_g=float(max(0, rng.normal(22, 8))),
                fat_g=float(max(0, rng.normal(16, 7))),
                fiber_g=float(max(0, rng.normal(6, 3))),
                gi=float(np.clip(rng.normal(1.0, 0.16), 0.7, 1.3)),
            )
        )

    activities = []
    for _ in range(int(rng.integers(1, 4))):
        activities.append(
            ScheduledActivity(
                code=str(rng.choice(ACTIVITY_POOL)),
                start_h=float(np.clip(rng.uniform(p.wake_h + 0.5, 21.0), 0, 23.5)),
                duration_min=float(rng.choice([15, 20, 30, 45, 60, 90])),
                intensity_scale=float(np.clip(rng.normal(1.0, 0.13), 0.7, 1.35)),
            )
        )

    return DaySchedule(
        weight_kg=p.weight_kg,
        wake_h=p.wake_h,
        bed_h=p.bed_h,
        meals=meals,
        activities=activities,
        stress=p.stress,
        metformin=p.metformin,
        fitness=p.fitness,
        dawn_intensity=p.dawn_intensity,
    )


def simulate_glucose(
    frames,
    p: PatientParams,
    rng: np.random.Generator,
    step_min: int = 5,
) -> np.ndarray:
    """Intègre la glycémie à partir du flux net, avec rétroaction et aléas.

    Le modèle génératif est **volontairement différent** de ce que la couche 2
    apprendra : clairance non linéaire, collations non déclarées, bruit capteur.
    """
    n = len(frames)
    volume_dl = GLUCOSE_SPACE_DL_PER_KG * p.weight_kg
    g = np.empty(n, dtype=float)
    g[0] = p.baseline_glucose + rng.normal(0, 6)

    # Collations non déclarées : invisibles des concepts, donc irréductibles.
    hidden = np.zeros(n)
    for _ in range(int(rng.integers(0, 3))):
        i = int(rng.integers(int(6 * 60 / step_min), n - 1))
        amount = rng.uniform(8, 28)                      # grammes
        span = max(1, int(50 / step_min))
        for k in range(span):
            if i + k < n:
                x = (k + 1) / span
                hidden[i + k] += amount * 1000 * x * math.exp(1 - x) / (span * 2.0)

    for i in range(n - 1):
        f = frames[i]
        inflow = (f.net_glucose_flux_mg_min + hidden[i]) * p.sensitivity
        # Clairance dépendante du niveau : plus la glycémie est haute, plus le
        # retour vers l'équilibre est fort (non linéarité absente des concepts).
        excess = g[i] - p.baseline_glucose
        clear = p.clearance * excess * (1.0 + 0.004 * max(0.0, excess))
        dg = (inflow / volume_dl) * step_min - clear * step_min
        g[i + 1] = g[i] + dg + rng.normal(0, 1.1)

    g += rng.normal(0, 2.0, size=n)          # bruit de capteur CGM
    return np.clip(g, 40, 400)


def build_cohort(
    n_patients: int = 45,
    days_per_patient: int = 8,
    seed: int = 7,
    step_min: int = 5,
):
    """Construit la cohorte : liste d'enregistrements par patient et par pas.

    Retourne un `pandas.DataFrame` avec une colonne `patient`, une colonne
    `glucose`, et une colonne par concept — exactement la forme qu'aura la
    table issue de CGMacros.
    """
    import pandas as pd

    catalogue = load_activities()
    rng = np.random.default_rng(seed)
    rows = []

    for idx in range(n_patients):
        p = sample_patient(rng, idx)
        for day_i in range(days_per_patient):
            schedule = sample_day(rng, p)
            frames = compute_day_concepts(schedule, catalogue, step_min=step_min)
            glucose = simulate_glucose(frames, p, rng, step_min=step_min)
            for f, gl in zip(frames, glucose):
                rec = dict(vars(f))
                rec["patient"] = p.pid
                rec["day"] = day_i
                rec["glucose"] = float(gl)
                rec["weight_kg"] = p.weight_kg
                rows.append(rec)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = build_cohort(n_patients=6, days_per_patient=2)
    print(df.shape)
    print(df[["patient", "day", "t_h", "glucose", "net_glucose_flux_mg_min"]].head())
    print("\nGlycémie par patient :")
    print(df.groupby("patient")["glucose"].agg(["mean", "min", "max"]).round(1))
