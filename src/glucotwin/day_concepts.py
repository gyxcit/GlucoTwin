"""
Couches 0 et 1 complètes — de l'emploi du temps au flux de concepts.

Couche 0 : structures de saisie (`DaySchedule`) — ce que la personne remplit.
Couche 1 : moteur qui produit, pas à pas sur 24 h, le vecteur de concepts
           physiologiquement interprétables consommé par la couche 2.

Trois branches alimentent le vecteur de concepts :

    activités  ──► captation musculaire du glucose, oxydation, déficit glycogénique
    repas      ──► glucides en cours d'absorption (COB) et débit d'apparition (Ra)
    contexte   ──► index de sensibilité à l'insuline (circadien × sommeil ×
                   stress × effet post-effort × metformine)

Sans dépendance externe (Python standard uniquement).
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .metabolic_engine import (
    Activity,
    load_activities,
    vo2_from_met,
    rer_from_met,
    frayn_oxidation,
)

# ---------------------------------------------------------------------------
# COUCHE 0 — l'emploi du temps
# ---------------------------------------------------------------------------


@dataclass
class ScheduledActivity:
    """Une activité placée dans la journée."""

    code: str                     # clé du catalogue MET (ex. "MAR04")
    start_h: float                # heure de début (7.5 = 07h30)
    duration_min: float
    intensity_scale: float = 1.0  # 0.8 = tranquille, 1.2 = soutenu


@dataclass
class Meal:
    """Un repas, avec sa composition."""

    time_h: float
    carbs_g: float
    protein_g: float = 0.0
    fat_g: float = 0.0
    fiber_g: float = 0.0
    gi: float = 1.0               # 0.78 bas · 1.0 moyen · 1.28 haut


@dataclass
class DaySchedule:
    """Tout ce que la personne saisit — l'entrée du jumeau."""

    weight_kg: float
    wake_h: float = 7.0
    bed_h: float = 23.5
    meals: list[Meal] = field(default_factory=list)
    activities: list[ScheduledActivity] = field(default_factory=list)
    stress: float = 0.4           # 0 → 1
    metformin: bool = True
    fitness: float = 1.0
    #: Intensité du phénomène de l'aube. 0 = absent, 1 = typique du DT2.
    #: Très variable d'un patient à l'autre — candidat naturel à la calibration.
    dawn_intensity: float = 1.0

    @property
    def awake_hours(self) -> float:
        """Durée d'éveil, calculée circulairement (gère le passage de minuit)."""
        return (self.bed_h - self.wake_h) % 24.0

    @property
    def sleep_hours(self) -> float:
        return 24.0 - self.awake_hours

    def is_asleep(self, hour: float) -> bool:
        """Vrai si la personne dort à cette heure.

        Le calcul est circulaire : il gère aussi bien un coucher après minuit
        qu'un travail de nuit (lever 16h, coucher 8h).
        """
        return ((hour - self.wake_h) % 24.0) >= self.awake_hours


# ---------------------------------------------------------------------------
# COUCHE 1 — les concepts
# ---------------------------------------------------------------------------


@dataclass
class ConceptFrame:
    """Le vecteur de concepts à un instant donné. Entrée de la couche 2."""

    t_h: float
    asleep: int
    # branche activité
    met_now: float
    energy_rate_kcal_min: float
    cho_ox_rate_g_min: float
    glucose_uptake_mg_min: float
    glycogen_deficit_g: float
    # branche repas
    cob_g: float                     # glucides restant à absorber
    carb_ra_g_min: float             # débit d'apparition du glucose
    # branche modulateurs
    circadian_factor: float          # >1 = tolérance dégradée (soir)
    insulin_sensitivity_index: float  # >1 = meilleure sensibilité
    dawn_factor: float               # bouffée hormonale de fin de nuit (0 → 1)
    # bilan du glucose sanguin
    hepatic_output_mg_min: float     # production hépatique (le foie recharge)
    net_glucose_flux_mg_min: float   # entrées − sorties : le moteur de la glycémie


# --- Modèles de branche -----------------------------------------------------


def carb_absorption(meal: Meal, minutes_since: float) -> tuple[float, float]:
    """(COB restant en g, débit d'apparition en g/min) pour un repas.

    Cinétique gamma d'ordre 2, d'intégrale exactement égale aux glucides du
    repas. Le pic est plus précoce pour un index glycémique élevé ; les fibres
    ralentissent l'absorption.
    """
    if minutes_since <= 0:
        return 0.0, 0.0
    tp = 45.0 / max(0.6, meal.gi)                    # temps de pic (min)
    tp *= 1.0 + min(0.35, meal.fiber_g * 0.02)       # fibres → ralentissement
    x = minutes_since / tp
    ra = meal.carbs_g * minutes_since / (tp * tp) * math.exp(-x)
    cob = meal.carbs_g * (1.0 + x) * math.exp(-x)
    return cob, ra


#: Captation musculaire de glucose **sanguin** à l'effort, en mg/kg/min et par
#: MET au-dessus du repos. Calée sur la littérature : la consommation totale
#: atteint ~5–8 mg/kg/min au voisinage des efforts intenses.
EXERCISE_UPTAKE_MG_KG_PER_MET = 0.60


def exercise_glucose_uptake(
    weight_kg: float,
    met_now: float,
    elapsed_min: float,
) -> float:
    """Captation musculaire de glucose sanguin à l'effort (mg/min).

    Modélisée **directement**, et non comme une fraction de l'oxydation : elle
    croît donc de façon strictement monotone avec l'intensité, ce qui est la
    réalité physiologique (le muscle en contraction capte le glucose via GLUT4,
    indépendamment de l'insuline).

    Elle augmente aussi avec la durée : le glycogène musculaire s'épuisant, le
    muscle puise davantage dans la circulation.
    """
    intensity = max(0.0, met_now - 1.3)
    duration_gain = 1.0 + 0.30 * min(1.0, max(0.0, elapsed_min) / 90.0)
    return weight_kg * EXERCISE_UPTAKE_MG_KG_PER_MET * intensity * duration_gain


#: Production hépatique de glucose au repos, à jeun (mg/kg/min).
HEPATIC_BASAL_MG_KG_MIN = 2.0

#: Phénomène de l'aube — amplitudes à intensité 1.
#: Calibrées pour une remontée d'environ 25 mg/dL avant le réveil, ce qui
#: correspond à la fourchette observée dans le diabète de type 2 (10–30 mg/dL).
DAWN_HEPATIC_GAIN = 0.08    # hausse de la production hépatique
DAWN_DISPOSAL_DROP = 0.04   # baisse de la consommation basale
DAWN_ISI_DROP = 0.15        # baisse de la sensibilité à l'insuline (concept)
DAWN_SIGMA_H = 1.4          # largeur de la bouffée hormonale (heures)


def dawn_factor(hour: float, wake_h: float, intensity: float = 1.0) -> float:
    """Phénomène de l'aube — bouffée hormonale de fin de nuit (0 → intensity).

    En fin de nuit, cortisol, hormone de croissance et catécholamines montent.
    Ils **stimulent la production hépatique de glucose** et **réduisent la
    sensibilité à l'insuline** : la glycémie remonte avant même le réveil, sans
    aucun repas. C'est une cause majeure d'hyperglycémie matinale dans le DT2.

    La bouffée culmine environ une heure avant le lever.
    """
    peak = wake_h - 1.0
    d = (hour - peak + 12.0) % 24.0 - 12.0     # distance circulaire
    return intensity * math.exp(-(d * d) / (2.0 * DAWN_SIGMA_H ** 2))


def hepatic_output(
    weight_kg: float,
    cob_g: float,
    met_now: float,
    dawn: float = 0.0,
) -> float:
    """Production hépatique de glucose (mg/min).

    Le foie libère du glucose en continu pour maintenir la glycémie. Cette
    production est **freinée après un repas** (l'insuline la supprime),
    **stimulée à l'effort** (pour soutenir le muscle) et **stimulée à l'aube**
    (bouffée de cortisol).
    """
    base = HEPATIC_BASAL_MG_KG_MIN * weight_kg
    suppression = 1.0 - min(0.65, cob_g / 60.0 * 0.65)   # effet insuline
    exercise_boost = 1.0 + min(1.2, max(0.0, met_now - 2.0) * 0.18)
    dawn_boost = 1.0 + DAWN_HEPATIC_GAIN * dawn
    return base * suppression * exercise_boost * dawn_boost


def circadian_factor(hour: float) -> float:
    """Dégradation de la tolérance au glucose au fil de la journée.

    ~0,80 le matin (excursions atténuées) → ~1,30 le soir. Cohérent avec la
    littérature sur le rythme circadien de la sensibilité à l'insuline.
    """
    return max(0.75, min(1.30, 0.80 + 0.033 * (hour - 7.0)))


def insulin_sensitivity(
    schedule: DaySchedule,
    hour: float,
    glycogen_deficit_g: float,
    dawn: float = 0.0,
) -> float:
    """Index de sensibilité à l'insuline (>1 = plus sensible)."""
    isi = 1.0 / circadian_factor(hour)                      # circadien
    isi *= 1.0 - 0.045 * max(0.0, 7.0 - schedule.sleep_hours)  # dette de sommeil
    isi *= 1.0 - 0.18 * schedule.stress                     # stress (cortisol)
    isi *= 1.0 + min(0.30, glycogen_deficit_g / 120.0 * 0.30)  # post-effort
    isi *= 1.0 - DAWN_ISI_DROP * dawn                       # bouffée de l'aube
    if schedule.metformin:
        isi *= 1.15
    return max(0.35, min(2.2, isi))


# --- Le pipeline ------------------------------------------------------------


def compute_day_concepts(
    schedule: DaySchedule,
    catalogue: dict[str, Activity],
    *,
    step_min: int = 5,
) -> list[ConceptFrame]:
    """Produit le flux de concepts sur 24 h, pas de `step_min` minutes."""
    frames: list[ConceptFrame] = []
    glycogen_deficit = 0.0
    steps = int(24 * 60 / step_min) + 1

    for i in range(steps):
        minute = i * step_min
        hour = minute / 60.0

        # --- branche activité ---
        # L'intensité courante est celle de l'activité en cours ; en dehors,
        # c'est le métabolisme de repos (le corps ne s'arrête jamais).
        met_now = 0.0
        elapsed_in_activity = 0.0

        for act in schedule.activities:
            start = act.start_h * 60.0
            if not (start <= minute < start + act.duration_min):
                continue
            met = max(0.9, catalogue[act.code].met * act.intensity_scale)
            if met > met_now:
                met_now = met
                elapsed_in_activity = minute - start

        if met_now == 0.0:
            met_now = 0.95 if schedule.is_asleep(hour) else 1.3

        # Oxydation calculée à TOUT instant, repos compris.
        vo2 = vo2_from_met(met_now, schedule.weight_kg)
        rer = rer_from_met(met_now, fitness=schedule.fitness)
        cho_rate, fat_rate = frayn_oxidation(vo2, rer * vo2)
        energy_rate = cho_rate * 4.0 + fat_rate * 9.0

        # Part prélevée dans le sang : élevée au repos (cerveau), plus basse en
        # début d'effort (le muscle vide d'abord son glycogène).
        exercise_uptake = exercise_glucose_uptake(
            schedule.weight_kg, met_now, elapsed_in_activity
        )
        # Consommation de glucose (Rd). Au repos et à jeun, l'organisme est à
        # l'équilibre : ce qu'il consomme égale ce que le foie produit. On pose
        # donc le repos comme état stationnaire, et l'effort ajoute par-dessus
        # la part sanguine de l'oxydation SUPPLÉMENTAIRE qu'il provoque.
        met_rest = 0.95 if schedule.is_asleep(hour) else 1.3
        vo2_rest = vo2_from_met(met_rest, schedule.weight_kg)
        rer_rest = rer_from_met(met_rest, fitness=schedule.fitness)
        cho_rest, _ = frayn_oxidation(vo2_rest, rer_rest * vo2_rest)

        # La bouffée de l'aube freine aussi la consommation basale (mais
        # faiblement : au repos elle est surtout cérébrale, donc peu
        # dépendante de l'insuline).
        dawn = dawn_factor(hour, schedule.wake_h, schedule.dawn_intensity)
        basal_disposal = (
            HEPATIC_BASAL_MG_KG_MIN * schedule.weight_kg
            * (1.0 - DAWN_DISPOSAL_DROP * dawn)
        )
        extra_cho = max(0.0, cho_rate - cho_rest)
        uptake_mg_min = basal_disposal + exercise_uptake

        # Ce que l'effort oxyde en plus, mais que le sang ne fournit pas,
        # vient forcément du glycogène musculaire. Bilan de masse cohérent,
        # et naturellement nul au repos (extra_cho y est nul).
        glycogen_rate = max(0.0, extra_cho - exercise_uptake / 1000.0)
        glycogen_deficit += glycogen_rate * step_min

        # --- branche repas ---
        cob_total = ra_total = 0.0
        for meal in schedule.meals:
            cob, ra = carb_absorption(meal, minute - meal.time_h * 60.0)
            cob_total += cob
            ra_total += ra

        # --- branche modulateurs ---
        circ = circadian_factor(hour)
        isi = insulin_sensitivity(schedule, hour, glycogen_deficit, dawn)

        # --- bilan du glucose sanguin ---
        hgp = hepatic_output(schedule.weight_kg, cob_total, met_now, dawn)
        net_flux = ra_total * 1000.0 + hgp - uptake_mg_min

        frames.append(
            ConceptFrame(
                t_h=round(hour, 4),
                asleep=int(schedule.is_asleep(hour)),
                met_now=round(met_now, 2),
                energy_rate_kcal_min=round(energy_rate, 4),
                cho_ox_rate_g_min=round(cho_rate, 4),
                glucose_uptake_mg_min=round(uptake_mg_min, 1),
                glycogen_deficit_g=round(glycogen_deficit, 2),
                cob_g=round(cob_total, 2),
                carb_ra_g_min=round(ra_total, 4),
                circadian_factor=round(circ, 3),
                insulin_sensitivity_index=round(isi, 3),
                dawn_factor=round(dawn, 3),
                hepatic_output_mg_min=round(hgp, 1),
                net_glucose_flux_mg_min=round(net_flux, 1),
            )
        )

    return frames


def export_csv(frames: list[ConceptFrame], path: str | Path) -> None:
    """Écrit le flux de concepts — le fichier d'entrée de la couche 2."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(frames[0]).keys()))
        writer.writeheader()
        for f in frames:
            writer.writerow(asdict(f))


# --- Démonstration ----------------------------------------------------------

if __name__ == "__main__":
    catalogue = load_activities()

    day = DaySchedule(
        weight_kg=82.0,
        wake_h=7.0,
        bed_h=23.0,
        stress=0.4,
        metformin=True,
        meals=[
            Meal(time_h=7.75, carbs_g=55, protein_g=15, fat_g=12, fiber_g=6, gi=1.0),
            Meal(time_h=12.75, carbs_g=75, protein_g=30, fat_g=20, fiber_g=8, gi=1.1),
            Meal(time_h=20.5, carbs_g=65, protein_g=25, fat_g=18, fiber_g=5, gi=0.9),
        ],
        activities=[
            ScheduledActivity("MAR04", start_h=8.5, duration_min=25),   # marche
            ScheduledActivity("SED03", start_h=9.5, duration_min=180),  # bureau
            ScheduledActivity("MAR07", start_h=13.5, duration_min=8),   # escaliers
            ScheduledActivity("VEL03", start_h=18.0, duration_min=45),  # vélo
        ],
    )

    frames = compute_day_concepts(day, catalogue)
    export_csv(frames, Path(__file__).with_name("concepts_jour.csv"))

    print(f"Journée simulée — sommeil déduit : {day.sleep_hours:.1f} h")
    print(f"{len(frames)} pas de 5 min → concepts_jour.csv\n")
    print(f"{'heure':>6} {'MET':>5} {'COB g':>7} {'Ra mg/min':>10} "
          f"{'foie':>7} {'captation':>10} {'FLUX NET':>9} {'ISI':>6}")
    print("-" * 74)
    for f in frames:
        if abs(f.t_h * 60 % 90) < 1e-6:  # une ligne toutes les 90 min
            h, m = int(f.t_h), int(round((f.t_h % 1) * 60))
            print(f"{h:02d}h{m:02d} {f.met_now:>5.1f} {f.cob_g:>7.1f} "
                  f"{f.carb_ra_g_min*1000:>10.0f} {f.hepatic_output_mg_min:>7.0f} "
                  f"{f.glucose_uptake_mg_min:>10.0f} {f.net_glucose_flux_mg_min:>+9.0f} "
                  f"{f.insulin_sensitivity_index:>6.2f}")

    # --- vérification du phénomène de l'aube ---
    print("\nPhénomène de l'aube — fin de nuit, à jeun, sans aucune activité")
    print("-" * 74)
    print(f"{'heure':>6} {'aube':>6} {'foie':>7} {'consommation':>13} {'FLUX NET':>9} {'ISI':>6}")
    for f in frames:
        if 2.0 <= f.t_h <= day.wake_h and abs(f.t_h * 60 % 30) < 1e-6:
            h, m = int(f.t_h), int(round((f.t_h % 1) * 60))
            print(f"{h:02d}h{m:02d} {f.dawn_factor:>6.2f} {f.hepatic_output_mg_min:>7.0f} "
                  f"{f.glucose_uptake_mg_min:>13.0f} {f.net_glucose_flux_mg_min:>+9.0f} "
                  f"{f.insulin_sensitivity_index:>6.2f}")

    # Remontée glycémique cumulée : masse accumulée / volume de distribution
    glucose_space_dl = 0.20 * day.weight_kg * 10.0     # ~0,20 L/kg -> dL
    night = [f for f in frames if 2.0 <= f.t_h <= day.wake_h]
    mass_mg = sum(f.net_glucose_flux_mg_min * 5 for f in night)
    print(f"\nRemontee estimee de 02h00 au lever : +{mass_mg / glucose_space_dl:.0f} mg/dL")
    print("   (fourchette attendue dans le DT2 : +10 a +30 mg/dL)")

    peak = max(frames, key=lambda f: f.carb_ra_g_min)
    upt = max(frames, key=lambda f: f.glucose_uptake_mg_min)
    print(f"\nPic d'absorption : {peak.carb_ra_g_min:.2f} g/min à {peak.t_h:.2f} h")
    print(f"Pic de captation : {upt.glucose_uptake_mg_min:.0f} mg/min à {upt.t_h:.2f} h")
    print(f"Déficit glycogénique en fin de journée : {frames[-1].glycogen_deficit_g:.1f} g")
    total = sum(f.carb_ra_g_min * 5 for f in frames)
    print(f"Contrôle — glucides absorbés {total:.1f} g "
          f"vs {sum(m.carbs_g for m in day.meals):.0f} g ingérés")
