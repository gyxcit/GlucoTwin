"""
Moteur métabolique — couche 1 du jumeau numérique.

Transforme une activité déclarée (emploi du temps) en concepts physiologiques
interprétables : dépense énergétique, oxydation des glucides et des lipides,
captation musculaire du glucose.

Chaîne de calcul
----------------
    activité  →  MET  →  VO2  →  RER  →  VCO2  →  équations de Frayn  →  g/min
                                (estimé depuis l'intensité)

Références
----------
- 2024 Adult Compendium of Physical Activities (valeurs MET de référence)
- Frayn KN. Calculation of substrate oxidation rates in vivo from gaseous
  exchange. J Appl Physiol. 1983;55(2):628-634.
- Relation intensité → quotient respiratoire : physiologie de l'exercice établie.

Avertissement : chaîne d'ESTIMATION, pas de mesure. Chaque étape introduit une
erreur. Usage pédagogique / recherche, jamais clinique.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

# --- Constantes physiologiques ---------------------------------------------

VO2_PER_MET = 3.5          # mL O2 / kg / min pour 1 MET
KCAL_PER_G_CHO = 4.0
KCAL_PER_G_FAT = 9.0
# Fraction du glucose oxydé prélevée dans le sang (le reste vient du glycogène
# musculaire). Croît avec la durée de l'effort.
BLOOD_GLUCOSE_FRACTION_BASE = 0.25
BLOOD_GLUCOSE_FRACTION_MAX = 0.55


# --- Table d'activités ------------------------------------------------------

@dataclass(frozen=True)
class Activity:
    code: str
    label: str
    category: str
    met: float
    intensity: str


DEFAULT_CATALOGUE = Path(__file__).with_name("met_activities.csv")


def load_activities(path: str | Path | None = None) -> dict[str, Activity]:
    """Charge la table de référence des activités (code -> Activity)."""
    path = DEFAULT_CATALOGUE if path is None else path
    table: dict[str, Activity] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            table[row["code"]] = Activity(
                code=row["code"],
                label=row["activite"],
                category=row["categorie"],
                met=float(row["met"]),
                intensity=row["intensite"],
            )
    return table


# --- Physiologie ------------------------------------------------------------

def vo2_from_met(met: float, weight_kg: float) -> float:
    """VO2 en L/min à partir des METs et du poids."""
    return met * VO2_PER_MET * weight_kg / 1000.0


def rer_from_met(met: float, fitness: float = 1.0, fed: bool = True) -> float:
    """Quotient respiratoire (RER) estimé à partir de l'intensité.

    RER 0.71 = lipides purs, 1.00 = glucides purs.

    `fitness` > 1 décrit un sujet entraîné (oxyde plus de lipides à intensité
    donnée, donc RER plus bas). `fed=False` (à jeun) abaisse aussi le RER.
    """
    # Croissance saturante du RER avec l'intensité relative.
    rer = 0.78 + 0.20 * (1.0 - 2.718281828 ** (-met / 6.0))
    rer -= 0.03 * (fitness - 1.0)
    if not fed:
        rer -= 0.03
    return max(0.71, min(1.00, rer))


def frayn_oxidation(vo2_l_min: float, vco2_l_min: float) -> tuple[float, float]:
    """Équations de Frayn : (glucides, lipides) oxydés en g/min.

    Contribution protéique négligée (usage non clinique).
    """
    cho = 4.55 * vco2_l_min - 3.21 * vo2_l_min
    fat = 1.67 * (vo2_l_min - vco2_l_min)
    return max(0.0, cho), max(0.0, fat)


def blood_glucose_fraction(duration_min: float) -> float:
    """Part du glucose oxydé prélevée dans le sang plutôt que dans le glycogène.

    Elle augmente avec la durée : le glycogène musculaire s'épuise et le muscle
    puise davantage dans la circulation.
    """
    ramp = min(1.0, duration_min / 90.0)
    span = BLOOD_GLUCOSE_FRACTION_MAX - BLOOD_GLUCOSE_FRACTION_BASE
    return BLOOD_GLUCOSE_FRACTION_BASE + span * ramp


# --- Sortie : le vecteur de concepts ---------------------------------------

@dataclass
class MetabolicState:
    """Les concepts interprétables du goulot d'étranglement (couche 1)."""

    activity: str
    duration_min: float
    met: float
    vo2_l_min: float
    rer: float
    energy_kcal: float
    cho_oxidized_g: float          # glucides oxydés sur la séance
    fat_oxidized_g: float          # lipides oxydés sur la séance
    blood_glucose_uptake_g: float  # part prélevée dans le sang
    glucose_uptake_mg_min: float   # débit de captation, mg/min
    glycogen_deficit_g: float      # déficit → sensibilité accrue post-effort

    # Incertitude due au RER estimé (VCO2 jamais mesuré hors laboratoire).
    # L'énergie est robuste (~±3 %) ; la partition des substrats ne l'est pas.
    cho_oxidized_g_low: float = 0.0
    cho_oxidized_g_high: float = 0.0

    @property
    def cho_uncertainty_pct(self) -> float:
        if self.cho_oxidized_g <= 0:
            return 0.0
        span = (self.cho_oxidized_g_high - self.cho_oxidized_g_low) / 2.0
        return span / self.cho_oxidized_g * 100.0

    def summary_fr(self) -> str:
        return (
            f"{self.activity} — {self.duration_min:.0f} min à {self.met:.1f} MET : "
            f"{self.energy_kcal:.0f} kcal, "
            f"{self.cho_oxidized_g:.1f} g de glucides "
            f"[{self.cho_oxidized_g_low:.1f}–{self.cho_oxidized_g_high:.1f}] "
            f"et {self.fat_oxidized_g:.1f} g de lipides oxydés ; "
            f"captation sanguine ≈ {self.blood_glucose_uptake_g:.1f} g "
            f"({self.glucose_uptake_mg_min:.0f} mg/min)."
        )


def compute_metabolic_state(
    activity: Activity,
    duration_min: float,
    weight_kg: float,
    *,
    intensity_scale: float = 1.0,
    fitness: float = 1.0,
    fed: bool = True,
    rer_uncertainty: float = 0.05,
) -> MetabolicState:
    """Calcule le vecteur de concepts pour une activité donnée.

    `intensity_scale` permet d'ajuster l'effort perçu (0.8 = plus tranquille,
    1.2 = plus soutenu) — c'est le levier de personnalisation le plus simple.
    """
    met = max(0.9, activity.met * intensity_scale)
    vo2 = vo2_from_met(met, weight_kg)
    rer = rer_from_met(met, fitness=fitness, fed=fed)
    vco2 = rer * vo2

    cho_rate, fat_rate = frayn_oxidation(vo2, vco2)
    cho_total = cho_rate * duration_min
    fat_total = fat_rate * duration_min

    frac = blood_glucose_fraction(duration_min)
    blood_g = cho_total * frac
    uptake_mg_min = (blood_g * 1000.0 / duration_min) if duration_min > 0 else 0.0

    energy = cho_total * KCAL_PER_G_CHO + fat_total * KCAL_PER_G_FAT

    # Bornes dues à l'incertitude sur le RER : VCO2 n'est jamais mesuré hors
    # laboratoire, donc la partition glucides/lipides est modélisée, pas observée.
    cho_bounds = []
    for shift in (-rer_uncertainty, +rer_uncertainty):
        r = max(0.71, min(1.00, rer + shift))
        c, _ = frayn_oxidation(vo2, r * vo2)
        cho_bounds.append(c * duration_min)

    return MetabolicState(
        activity=activity.label,
        duration_min=duration_min,
        met=met,
        vo2_l_min=vo2,
        rer=rer,
        energy_kcal=energy,
        cho_oxidized_g=cho_total,
        fat_oxidized_g=fat_total,
        blood_glucose_uptake_g=blood_g,
        glucose_uptake_mg_min=uptake_mg_min,
        glycogen_deficit_g=cho_total * (1.0 - frac),
        cho_oxidized_g_low=min(cho_bounds),
        cho_oxidized_g_high=max(cho_bounds),
    )


# --- Démonstration ----------------------------------------------------------

if __name__ == "__main__":
    acts = load_activities(Path(__file__).with_name("met_activities.csv"))
    weight = 78.0

    print(f"Sujet de {weight:.0f} kg\n" + "=" * 78)
    for code, minutes in [
        ("SED03", 60),   # bureau
        ("MAR04", 30),   # marche rapide
        ("MAR07", 10),   # escaliers
        ("VEL03", 45),   # vélo soutenu
        ("CRS02", 30),   # course
        ("JAR02", 40),   # tondre la pelouse
        ("FIT05", 45),   # musculation soutenue
    ]:
        state = compute_metabolic_state(acts[code], minutes, weight)
        print(state.summary_fr())

    # Contrôle de cohérence : l'énergie issue de Frayn doit coller à la
    # formule classique kcal = MET × 3.5 × poids / 200 × durée.
    print("\nContrôle de cohérence énergétique")
    print("-" * 78)
    for code in ["MAR04", "VEL03", "CRS02"]:
        a = acts[code]
        st = compute_metabolic_state(a, 30, weight)
        classic = a.met * 3.5 * weight / 200.0 * 30
        delta = abs(st.energy_kcal - classic) / classic * 100
        print(
            f"{a.label:<28} Frayn {st.energy_kcal:6.1f} kcal | "
            f"formule MET {classic:6.1f} kcal | écart {delta:4.1f} %"
        )
