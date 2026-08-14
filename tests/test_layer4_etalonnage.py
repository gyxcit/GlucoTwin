"""
Tests de l'étalonnage — les chiffres du catalogue doivent rester vrais.

Un catalogue dont les valeurs ont été saisies à la main est un catalogue qui
ment dès que le modèle change. Le test central ci-dessous recalcule chaque
effet et le compare à ce qui est écrit dans `catalogue.py` : toucher au modèle
sans réétalonner casse la suite.

Le reste vérifie que l'intervention est appliquée là où elle a un sens — un
repas modifié, pas une série de nombres bricolée — et que l'écart entre l'effet
de population et l'effet personnel vient bien de θ, et de rien d'autre.
"""

from __future__ import annotations

import numpy as np
import pytest

from glucotwin.calibration import REDUCED_DEFAULT
from glucotwin.layer4.catalogue import CATALOGUE, CATALOGUE_PAR_ID
from glucotwin.layer4.etalonnage import (
    FIBRES_AJOUTEES_G,
    GI_BAS,
    appliquer_au_planning,
    effet_de,
    effets_population,
    journee_de_reference,
    series_du_planning,
)
from glucotwin.layer4.tools import contexte_depuis_planning, executer

#: θ médian du modèle réduit sur les 44 patients CGMacros.
THETA_CGMACROS = np.array([0.5617908640540168, 0.4997268310027497,
                           0.035438440067852656, 130.52913322915543])


def test_le_catalogue_dit_ce_que_le_modele_calcule():
    """**Le test qui tient le catalogue honnête.**

    Si quelqu'un modifie la physiologie, la journée de référence ou une
    transformation, les valeurs écrites dans `catalogue.py` cessent d'être
    vraies — et ce test le dit, plutôt que de laisser un chiffre périmé partir
    en présentation.
    """
    calcule = effets_population()
    for i in CATALOGUE:
        assert i.effet_pic == pytest.approx(calcule[i.id]["effet_pic"], abs=0.1), (
            f"{i.id} : catalogue {i.effet_pic}, recalcul "
            f"{calcule[i.id]['effet_pic']} → relancer "
            f"scripts/etalonner_catalogue.py")


def test_l_intervention_modifie_bien_le_repas_et_pas_la_serie():
    """« Index glycémique bas » doit changer `gi`, « fibres » doit changer `fiber_g`."""
    jour = journee_de_reference()
    bas = appliquer_au_planning("INDEX_GLYCEMIQUE_BAS", jour)
    assert all(m.gi <= GI_BAS for m in bas.meals)
    fibres = appliquer_au_planning("FIBRES", jour)
    for avant, apres in zip(jour.meals, fibres.meals):
        assert apres.fiber_g == pytest.approx(avant.fiber_g + FIBRES_AJOUTEES_G)


def test_reduire_les_glucides_retire_bien_un_tiers():
    jour = journee_de_reference()
    moins = appliquer_au_planning("REDUIRE_GLUCIDES", jour)
    total_avant = sum(m.carbs_g for m in jour.meals)
    total_apres = sum(m.carbs_g for m in moins.meals)
    assert total_apres == pytest.approx(total_avant * 2 / 3)


def test_fractionner_conserve_les_glucides():
    """Fractionner, c'est répartir — pas retirer."""
    jour = journee_de_reference()
    deux = appliquer_au_planning("FRACTIONNER_REPAS", jour)
    assert sum(m.carbs_g for m in deux.meals) == pytest.approx(
        sum(m.carbs_g for m in jour.meals))
    assert len(deux.meals) == len(jour.meals) + 1


def test_la_journee_de_reference_est_sedentaire():
    """Sinon l'effet d'« ajouter du sport » serait mesuré sur quelqu'un qui en fait."""
    jour = journee_de_reference()
    assert not any(a.code.startswith("VEL") for a in jour.activities)


def test_l_intervention_inconnue_est_refusee():
    with pytest.raises(KeyError):
        appliquer_au_planning("JEUNER_24H", journee_de_reference())


def test_l_ecart_population_personnel_ne_vient_que_de_theta():
    """Même journée, même code, seul θ change — et l'écart est substantiel.

    C'est la justification de l'agent : lire le catalogue à ce patient
    surestimerait l'effet d'un facteur voisin de deux.
    """
    jour = journee_de_reference()
    pop = [effet_de(i.id, jour, REDUCED_DEFAULT)["effet_pic"] for i in CATALOGUE]
    perso = [effet_de(i.id, jour, THETA_CGMACROS)["effet_pic"] for i in CATALOGUE]
    assert all(p <= 0.0 for p in pop + perso)            # rien ne remonte le pic
    assert abs(np.mean(perso)) < abs(np.mean(pop))       # effet personnel plus faible
    assert abs(np.mean(pop)) / abs(np.mean(perso)) > 1.5


def test_theta_identique_donne_exactement_les_memes_chiffres():
    """Contrôle de la tautologie inverse : sans changement de θ, aucun écart."""
    jour = journee_de_reference()
    for i in CATALOGUE:
        a = effet_de(i.id, jour, REDUCED_DEFAULT)["effet_pic"]
        b = effet_de(i.id, jour, REDUCED_DEFAULT)["effet_pic"]
        assert a == b


def test_l_outil_de_l_agent_retrouve_la_valeur_etalonnee():
    """L'agent et le script d'étalonnage doivent lire le même nombre.

    S'ils divergeaient, l'agent annoncerait au patient un effet que rien dans le
    dépôt ne permettrait de reproduire.
    """
    jour = journee_de_reference()
    etat = {"glucose": 165.0, "pente_mg_min": 0.1, "risque_hypo": 0.02}
    ctx = contexte_depuis_planning(jour, REDUCED_DEFAULT, etat=etat)
    for i in CATALOGUE:
        if not i.applicable(etat)[0]:
            continue
        obs = executer("simuler_intervention", {"id": i.id}, ctx)
        assert obs["voie"] == "planning"
        assert obs["effet_mesure_mg_dl"] == pytest.approx(i.effet_pic, abs=0.1)


def test_sans_planning_l_outil_signale_l_autre_voie():
    """La voie dégradée existe pour les patients mesurés — elle est étiquetée."""
    jour = journee_de_reference()
    ra, ex = series_du_planning(jour)
    from glucotwin.layer4.tools import JumeauContext

    ctx = JumeauContext(ra_mg_min=ra, exercice_mg_min=ex, weight_kg=jour.weight_kg,
                        theta=REDUCED_DEFAULT, g0=110.0, step_min=5.0,
                        etat={"glucose": 165.0})
    obs = executer("simuler_intervention", {"id": "FIBRES"}, ctx)
    assert obs["voie"] == "series"


def test_la_journee_de_reference_est_deterministe():
    a, b = series_du_planning(journee_de_reference())
    c, d = series_du_planning(journee_de_reference())
    assert np.array_equal(a, c) and np.array_equal(b, d)
