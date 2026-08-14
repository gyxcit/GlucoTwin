"""
D'où viennent les chiffres du catalogue — et pourquoi ils sont vérifiables.

Le catalogue annonce un effet en mg/dL pour chaque intervention. Ces nombres ne
peuvent pas être posés à la main : ce serait exactement le défaut qu'on reproche
au LLM, une valeur plausible sans provenance. Ils sont donc **calculés** ici, par
le même chemin que tout le reste du projet :

    intervention → modification de l'emploi du temps → couche 1 (concepts)
                 → modèle réduit avec θ → glycémie simulée → écart de pic

Deux conséquences importantes :

1. **L'intervention est modifiée là où elle a un sens physiologique.** « Index
   glycémique bas » change le paramètre `gi` du repas, ce qui déplace le pic de
   la cinétique gamma d'absorption ; « ajouter des fibres » change `fiber_g`, qui
   ralentit cette même cinétique. Bricoler directement la série d'apparition du
   glucose donnerait un effet arbitraire, dépendant de la forme du bricolage.
2. **L'effet de population et l'effet personnel sont calculés par le MÊME code**,
   la seule différence étant θ. L'écart que l'agent annonce (« chez vous, -9 au
   lieu de -16 ») est donc entièrement attribuable à la calibration du patient,
   et à rien d'autre. C'est ce qui rend la phrase défendable.

Le test `test_le_catalogue_dit_ce_que_le_modele_calcule` compare les valeurs
écrites dans `catalogue.py` à celles recalculées ici : si le modèle change et
que le catalogue ne suit pas, la suite de tests casse.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from ..calibration import REDUCED_DEFAULT, simulate_glucose_reduced
from ..day_concepts import DaySchedule, Meal, ScheduledActivity, compute_day_concepts
from ..metabolic_engine import load_activities

#: Poids du sujet de référence — celui de la journée type de la couche 1.
POIDS_REFERENCE = 82.0

#: Index glycémique « bas » au sens de `Meal.gi` (0.78 bas · 1.0 moyen · 1.28 haut).
GI_BAS = 0.78
#: Fibres ajoutées par repas, en grammes — une portion de légumineuses.
FIBRES_AJOUTEES_G = 10.0
#: Fraction de glucides retirée par `REDUIRE_GLUCIDES`.
REDUCTION_GLUCIDES = 1.0 / 3.0


def journee_de_reference() -> DaySchedule:
    """La journée sur laquelle le catalogue est étalonné.

    Volontairement **sédentaire** : trois repas, une courte marche, une longue
    plage de bureau. Si la journée de référence contenait déjà 45 minutes de
    vélo, l'effet d'« ajouter du vélo » serait mesuré sur quelqu'un qui en fait
    déjà — et paraîtrait faible pour une raison qui n'a rien à voir avec le
    patient.
    """
    return DaySchedule(
        weight_kg=POIDS_REFERENCE, wake_h=7.0, bed_h=23.0,
        stress=0.4, metformin=True,
        meals=[Meal(time_h=7.75, carbs_g=55, protein_g=15, fat_g=12, fiber_g=6, gi=1.0),
               Meal(time_h=12.75, carbs_g=75, protein_g=30, fat_g=20, fiber_g=8, gi=1.1),
               Meal(time_h=20.5, carbs_g=65, protein_g=25, fat_g=18, fiber_g=5, gi=0.9)],
        activities=[ScheduledActivity("MAR04", start_h=8.5, duration_min=25),
                    ScheduledActivity("SED03", start_h=9.5, duration_min=180),
                    ScheduledActivity("SED03", start_h=14.0, duration_min=180)])


def appliquer_au_planning(inter_id: str, jour: DaySchedule) -> DaySchedule:
    """Traduit une intervention en modification de l'emploi du temps.

    C'est le niveau auquel une intervention est **réelle** : ce que la personne
    mange, quand, et ce qu'elle fait. Tout le reste en découle par la couche 1.
    """
    repas = [replace(m) for m in jour.meals]
    activites = [replace(a) for a in jour.activities]

    if inter_id == "REDUIRE_GLUCIDES":
        repas = [replace(m, carbs_g=m.carbs_g * (1.0 - REDUCTION_GLUCIDES))
                 for m in repas]
    elif inter_id == "INDEX_GLYCEMIQUE_BAS":
        repas = [replace(m, gi=min(m.gi, GI_BAS)) for m in repas]
    elif inter_id == "FIBRES":
        repas = [replace(m, fiber_g=m.fiber_g + FIBRES_AJOUTEES_G) for m in repas]
    elif inter_id == "MARCHE_POST_REPAS":
        activites += [ScheduledActivity("MAR04", start_h=m.time_h + 0.5,
                                        duration_min=30) for m in repas]
    elif inter_id == "VELO_MODERE":
        activites.append(ScheduledActivity("VEL03", start_h=18.0, duration_min=45,
                                           intensity_scale=0.8))
    elif inter_id == "AVANCER_DINER":
        dernier = max(range(len(repas)), key=lambda i: repas[i].time_h)
        repas[dernier] = replace(repas[dernier], time_h=repas[dernier].time_h - 2.5)
    elif inter_id == "FRACTIONNER_REPAS":
        gros = max(range(len(repas)), key=lambda i: repas[i].carbs_g)
        m = repas[gros]
        repas[gros] = replace(m, carbs_g=m.carbs_g / 2.0, protein_g=m.protein_g / 2.0,
                              fat_g=m.fat_g / 2.0, fiber_g=m.fiber_g / 2.0)
        repas.append(replace(repas[gros], time_h=m.time_h + 2.0))
    else:
        raise KeyError(f"intervention inconnue : {inter_id!r}")

    return replace(jour, meals=repas, activities=activites)


def series_du_planning(jour: DaySchedule, *, step_min: int = 5):
    """`(ra, exercice)` en mg/min — les deux entrées du modèle réduit."""
    from ..calibration import exercise_uptake_from_concepts

    frames = compute_day_concepts(jour, load_activities(), step_min=step_min)
    ra = np.array([f.carb_ra_g_min for f in frames], dtype=float) * 1000.0
    ex = exercise_uptake_from_concepts(
        np.array([f.glucose_uptake_mg_min for f in frames], dtype=float),
        np.array([f.dawn_factor for f in frames], dtype=float),
        jour.weight_kg)
    return ra, ex


def effet_de(inter_id: str, jour: DaySchedule, theta, *,
             g0: float | None = None, step_min: int = 5) -> dict:
    """Effet d'une intervention sur une journée, pour un θ donné.

    `g0` par défaut vaut `g_base` : on part de l'équilibre, sinon l'écart de pic
    dépendrait de la glycémie de départ arbitraire plutôt que de l'intervention.
    """
    theta = np.asarray(theta, dtype=float)
    g0 = float(theta[3]) if g0 is None else float(g0)
    ra, ex = series_du_planning(jour, step_min=step_min)
    avant = simulate_glucose_reduced(theta, ra, ex, jour.weight_kg, g0, step_min)
    ra2, ex2 = series_du_planning(appliquer_au_planning(inter_id, jour),
                                  step_min=step_min)
    apres = simulate_glucose_reduced(theta, ra2, ex2, jour.weight_kg, g0, step_min)
    return {"id": inter_id,
            "pic_avant": round(float(avant.max()), 1),
            "pic_apres": round(float(apres.max()), 1),
            "effet_pic": round(float(apres.max() - avant.max()), 1),
            "effet_moyenne": round(float(apres.mean() - avant.mean()), 1),
            "gain_temps_dans_cible_pts": round(float(
                ((apres >= 70) & (apres <= 180)).mean() * 100
                - ((avant >= 70) & (avant <= 180)).mean() * 100), 1)}


def effets_population(jour: DaySchedule | None = None, *, step_min: int = 5) -> dict:
    """Les effets **de population** : θ par défaut, journée de référence.

    Ce sont exactement les nombres qui figurent dans `catalogue.py`.
    """
    from .catalogue import CATALOGUE

    jour = journee_de_reference() if jour is None else jour
    return {i.id: effet_de(i.id, jour, REDUCED_DEFAULT, step_min=step_min)
            for i in CATALOGUE}
