"""
Tests de l'agent — écrits contre l'agent, pas pour lui.

Ajouter une boucle et des outils, c'est ajouter des façons de mal se comporter :
boucler sans fin, inventer un nom d'outil, passer de mauvais arguments, insister
sur une intervention contre-indiquée, ignorer les observations et broder. Chaque
test ci-dessous est l'une de ces dérives.

La propriété centrale est la même que sans agent, et c'est le point : **à état
donné, l'ensemble des interventions affichables est identique avec agent, avec
LLM simple, et sans modèle du tout.** L'agent gagne un chiffre personnel, jamais
un pouvoir supplémentaire.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from glucotwin.layer4.agent import MAX_ETAPES, executer_agent
from glucotwin.layer4.catalogue import CATALOGUE, interventions_possibles
from glucotwin.layer4.llm import LLMScripte
from glucotwin.layer4.tools import (
    OUTILS,
    JumeauContext,
    appliquer,
    decrire_outils,
    executer,
)

ETAT = {"glucose": 165.0, "pente_mg_min": 0.2, "risque_hypo": 0.02,
        "cob_g": 40.0, "met": 1.3, "pic": 210.0}
ETAT_BAS = {"glucose": 78.0, "pente_mg_min": -0.1, "risque_hypo": 0.05}


def contexte(etat=None) -> JumeauContext:
    """Une journée jouet : trois repas, une heure de marche l'après-midi.

    Les valeurs n'ont pas à être réalistes — ce qui est testé ici est la
    mécanique, pas la physiologie (elle l'est ailleurs, sur CGMacros).
    """
    n = 289                                   # 24 h au pas de 5 min
    h = np.arange(n) * 5 / 60.0
    ra = np.zeros(n)
    for debut, masse in ((8.0, 900.0), (12.5, 1400.0), (19.5, 1200.0)):
        m = (h >= debut) & (h < debut + 1.5)
        ra[m] = masse / m.sum()
    ex = np.zeros(n)
    ex[(h >= 15.0) & (h < 16.0)] = 250.0
    return JumeauContext(ra_mg_min=ra, exercice_mg_min=ex, weight_kg=82.0,
                         theta=np.array([1.1, 0.9, 0.02, 108.0]),
                         g0=110.0, step_min=5.0, etat=dict(etat or ETAT))


def rep(**kw) -> str:
    return json.dumps(kw, ensure_ascii=False)


FINAL_OK = rep(interventions=["INDEX_GLYCEMIQUE_BAS", "FIBRES"],
               texte="Chez vous, le jumeau simule un pic nettement plus plat "
                     "avec un repas à index bas et davantage de fibres.")


# --------------------------------------------------------------------------- #
# 1. Les outils eux-mêmes
# --------------------------------------------------------------------------- #

def test_le_registre_est_ferme():
    obs = executer("rm_rf", {}, contexte())
    assert "erreur" in obs and "outil inconnu" in obs["erreur"]
    assert set(obs["outils"]) == set(OUTILS)


def test_un_outil_ne_leve_jamais():
    """Quels que soient les arguments, on renvoie une observation, pas une trace."""
    ctx = contexte()
    for nom in OUTILS:
        for args in ({}, {"id": None}, {"inconnu": 3}, {"id": "PAS_UN_ID"}):
            obs = executer(nom, args, ctx)
            assert isinstance(obs, dict)


def test_arguments_illisibles_rejetes():
    assert "erreur" in executer("profil_patient", ["pas", "un", "dict"], contexte())


def test_l_outil_refuse_une_intervention_contre_indiquee():
    """Le point dur : l'agent peut insister, la porte reste fermée."""
    ctx = contexte({"glucose": 95.0, "pente_mg_min": 0.0, "risque_hypo": 0.02})
    obs = executer("simuler_intervention", {"id": "VELO_MODERE"}, ctx)
    assert obs.get("simulation_refusee") is True
    assert "avant" not in obs and "effet_mesure_mg_dl" not in obs


def test_la_simulation_donne_un_effet_mesure_different_de_la_population():
    """Ce pour quoi l'agent existe : un chiffre propre à ce patient."""
    obs = executer("simuler_intervention", {"id": "INDEX_GLYCEMIQUE_BAS"}, contexte())
    assert "effet_mesure_mg_dl" in obs and "effet_population_mg_dl" in obs
    assert obs["effet_mesure_mg_dl"] <= 0.0          # ça ne remonte pas le pic


def test_l_etalement_conserve_les_glucides():
    """Un étalement qui perdrait de la masse ferait baisser le pic pour rien."""
    ctx = contexte()
    for ident in ("INDEX_GLYCEMIQUE_BAS", "FIBRES", "FRACTIONNER_REPAS"):
        ra, _ = appliquer(ident, ctx)
        assert ra.sum() == pytest.approx(ctx.ra_mg_min.sum(), rel=1e-9)


def test_les_outils_ne_modifient_pas_le_contexte():
    ctx = contexte()
    avant = (ctx.ra_mg_min.copy(), ctx.exercice_mg_min.copy(), ctx.theta.copy())
    for nom in OUTILS:
        executer(nom, {"id": "FIBRES"}, ctx)
    assert np.array_equal(ctx.ra_mg_min, avant[0])
    assert np.array_equal(ctx.exercice_mg_min, avant[1])
    assert np.array_equal(ctx.theta, avant[2])


def test_la_description_des_outils_est_generee():
    """Le prompt ne peut pas se désynchroniser du registre : il en est dérivé."""
    texte = decrire_outils()
    for nom in OUTILS:
        assert nom in texte


# --------------------------------------------------------------------------- #
# 2. La boucle
# --------------------------------------------------------------------------- #

def test_l_agent_utilise_ses_outils_puis_conclut():
    llm = LLMScripte([rep(outil="etat_courant", arguments={}),
                      rep(outil="simuler_intervention",
                          arguments={"id": "INDEX_GLYCEMIQUE_BAS"}),
                      FINAL_OK])
    r = executer_agent(ETAT, contexte(), llm)
    assert r.source == "agent"
    assert r.ids == ["INDEX_GLYCEMIQUE_BAS", "FIBRES"]
    assert [e.outil for e in r.trace] == ["etat_courant", "simuler_intervention"]
    assert not any(e.en_erreur for e in r.trace)


def test_l_observation_de_simulation_porte_bien_l_ecart():
    llm = LLMScripte([rep(outil="simuler_intervention", arguments={"id": "FIBRES"}),
                      FINAL_OK])
    r = executer_agent(ETAT, contexte(), llm)
    obs = r.trace[0].observation
    assert obs["effet_mesure_mg_dl"] != obs["effet_population_mg_dl"]
    assert "mesuré" in r.trace[0].resume()


def test_une_boucle_infinie_epuise_son_budget_et_retombe_sur_le_repli():
    """L'agent n'appelle qu'un outil, encore et encore. Il ne bloque pas le système."""
    llm = LLMScripte([rep(outil="journee_simulee", arguments={})])
    r = executer_agent(ETAT, contexte(), llm)
    assert r.source == "repli" and r.interventions
    assert llm.appels == MAX_ETAPES
    assert "budget epuise" in r.validation.raison()


def test_un_outil_invente_revient_comme_observation_sans_tuer_la_boucle():
    llm = LLMScripte([rep(outil="acceder_au_dossier_medical", arguments={}),
                      FINAL_OK])
    r = executer_agent(ETAT, contexte(), llm)
    assert r.source == "agent"                    # la boucle a continué
    assert r.trace[0].en_erreur


def test_arguments_invalides_reviennent_comme_observation():
    llm = LLMScripte([rep(outil="simuler_intervention", arguments={"id": "JEUNER_24H"}),
                      FINAL_OK])
    r = executer_agent(ETAT, contexte(), llm)
    assert "identifiant inconnu" in r.trace[0].observation["erreur"]
    assert r.source == "agent"


def test_json_illisible_a_chaque_tour_donne_le_repli():
    r = executer_agent(ETAT, contexte(), LLMScripte(["pas du json"]))
    assert r.source == "repli" and r.interventions


def test_api_en_panne_pendant_la_boucle_donne_le_repli():
    class LLMCasse:
        def completer(self, *a, **k):
            raise RuntimeError("503")
    r = executer_agent(ETAT, contexte(), LLMCasse())
    assert r.source == "repli" and r.interventions


def test_sans_llm_l_agent_est_le_repli():
    r = executer_agent(ETAT, contexte(), None)
    assert r.source == "repli" and r.interventions


# --------------------------------------------------------------------------- #
# 3. La sûreté n'est pas contournable par la boucle
# --------------------------------------------------------------------------- #

def test_l_etat_a_risque_refuse_avant_meme_d_appeler_le_modele():
    llm = LLMScripte([FINAL_OK])
    r = executer_agent(ETAT_BAS, contexte(ETAT_BAS), llm)
    assert r.source == "refus" and r.interventions == []
    assert llm.appels == 0                       # le modèle n'a jamais été sollicité


def test_l_agent_ne_peut_pas_valider_ce_qu_un_outil_a_refuse():
    """Il simule un vélo interdit, l'outil refuse, il le recommande quand même."""
    etat = {"glucose": 95.0, "pente_mg_min": 0.0, "risque_hypo": 0.02}
    llm = LLMScripte([rep(outil="simuler_intervention", arguments={"id": "VELO_MODERE"}),
                      rep(interventions=["VELO_MODERE"], texte="Un peu de vélo.")])
    r = executer_agent(etat, contexte(etat), llm)
    assert r.source == "repli"
    assert "VELO_MODERE" not in r.ids
    assert any("contre-indiquee" in x for x in r.validation.refus)


def test_le_vocabulaire_medical_fait_echouer_la_sortie_de_l_agent():
    llm = LLMScripte([rep(interventions=["FIBRES"],
                          texte="Pensez à ajuster votre insuline avant le repas.")])
    r = executer_agent(ETAT, contexte(), llm)
    assert r.source == "repli"
    assert any("vocabulaire medical" in x for x in r.validation.refus)


ETATS = [{"glucose": 200.0}, {"glucose": 105.0},
         {"glucose": 130.0, "asleep": True},
         {"glucose": 160.0, "risque_hypo": 0.12}]


@pytest.mark.parametrize("etat", ETATS)
def test_l_agent_ne_peut_jamais_elargir_l_ensemble_permis(etat):
    """La propriété centrale, rejouée sur la boucle.

    L'agent réclame tout le catalogue, y compris ce qui est contre-indiqué. Ce
    qui sort reste inclus dans ce que l'état permet.
    """
    permis = {i.id for i in interventions_possibles(etat)[0]}
    glouton = LLMScripte([rep(interventions=[i.id for i in CATALOGUE],
                              texte="Tout, tout de suite.")])
    r = executer_agent(etat, contexte(etat), glouton)
    assert set(r.ids) <= permis, f"{etat} : {set(r.ids) - permis} en trop"
    assert r.ids, "test creux : rien n'a ete propose, l'inclusion est triviale"


@pytest.mark.parametrize("etat", ETATS)
def test_l_invariant_tient_aussi_quand_la_sortie_est_acceptee(etat):
    """Le test précédent passe par le repli ; celui-ci passe par l'agent.

    Sans lui, l'invariant ne serait vérifié que sur le chemin d'échec — c'est
    justement sur le chemin nominal qu'il compte.
    """
    permis = [i.id for i in interventions_possibles(etat)[0]][:3]
    llm = LLMScripte([rep(interventions=permis,
                          texte="Trois ajustements que le jumeau simule comme "
                                "efficaces sur votre journee.")])
    r = executer_agent(etat, contexte(etat), llm)
    assert r.source == "agent", r.validation and r.validation.raison()
    assert r.ids == permis


def test_une_intervention_interdite_glissee_parmi_des_permises_jette_tout():
    """On ne garde pas « la partie valide » d'une sortie fautive."""
    etat = {"glucose": 95.0, "pente_mg_min": 0.0, "risque_hypo": 0.02}
    llm = LLMScripte([rep(interventions=["FIBRES", "VELO_MODERE"],
                          texte="Des fibres, et un peu de velo.")])
    r = executer_agent(etat, contexte(etat), llm)
    assert r.source == "repli"
    assert r.texte != "Des fibres, et un peu de velo."


def test_le_prompt_de_l_agent_ne_montre_pas_les_interventions_interdites():
    etat = {"glucose": 95.0}
    permis = {i.id for i in interventions_possibles(etat)[0]}
    llm = LLMScripte([rep(interventions=[], texte="")])
    executer_agent(etat, contexte(etat), llm)
    for i in CATALOGUE:
        if i.id not in permis:
            assert i.id not in llm.dernier_prompt, f"{i.id} fuit dans le prompt"


def test_l_agent_et_le_repli_proposent_le_meme_ensemble_de_base():
    """Sans rien inventer, l'agent retrouve exactement le classement déterministe."""
    from glucotwin.layer4.recommend import recommander
    sans = recommander(ETAT, llm=None)
    avec = executer_agent(ETAT, contexte(), LLMScripte(["pas du json"]))
    assert avec.ids == sans.ids
