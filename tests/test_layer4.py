"""
Tests de la couche 4 — écrits comme des attaques.

Un LLM bien élevé ne prouve rien. Ce qui compte est ce qui arrive quand il se
comporte mal : identifiants inventés, exercice conseillé à un patient qui
descend, mention d'insuline glissée dans une phrase anodine, JSON malformé,
API qui tombe. Chaque test ci-dessous est une de ces sorties, et le validateur
doit tenir.

La propriété centrale, testée explicitement : **l'ensemble des interventions
affichables est le même avec ou sans LLM**. Le modèle réordonne et rédige ; il
ne peut jamais élargir ce qui est permis.
"""

from __future__ import annotations

import json

import pytest

from glucotwin.layer4.catalogue import (
    CATALOGUE,
    CATALOGUE_PAR_ID,
    interventions_possibles,
)
from glucotwin.layer4.llm import FakeLLM, extraire_json
from glucotwin.layer4.recommend import recommander
from glucotwin.layer4.validator import (
    contient_vocabulaire_medical,
    etat_autorise_recommandation,
    valider,
)

ETAT_NORMAL = {"glucose": 165.0, "pente_mg_min": 0.2, "risque_hypo": 0.02,
               "cob_g": 40.0, "met": 1.3, "pic": 210.0}
ETAT_BAS = {"glucose": 78.0, "pente_mg_min": -0.1, "risque_hypo": 0.05}
ETAT_CHUTE = {"glucose": 150.0, "pente_mg_min": -0.9, "risque_hypo": 0.10}
ETAT_RISQUE = {"glucose": 140.0, "pente_mg_min": -0.1, "risque_hypo": 0.40}


# --------------------------------------------------------------------------- #
# 1. Le catalogue est réellement fermé
# --------------------------------------------------------------------------- #

def test_aucune_intervention_medicamenteuse():
    """Vérification du contenu : rien qui touche à un traitement."""
    interdits = ("insulin", "dose", "médicament", "metformin", "traitement")
    for i in CATALOGUE:
        blob = f"{i.id} {i.titre} {i.detail}".lower()
        for mot in interdits:
            assert mot not in blob, f"{i.id} evoque « {mot} »"


def test_les_identifiants_sont_uniques():
    ids = [i.id for i in CATALOGUE]
    assert len(ids) == len(set(ids))


def test_le_filtrage_respecte_les_contre_indications():
    ok, ko = interventions_possibles({"glucose": 95.0})
    assert all(i.glycemie_min <= 95.0 for i in ok)
    assert any(id_ == "REDUIRE_GLUCIDES" for id_, _ in ko)   # exige 100 mg/dL


def test_l_effort_est_interdit_pendant_le_sommeil():
    ok, ko = interventions_possibles({"glucose": 170.0, "asleep": True})
    refuses = {id_ for id_, _ in ko}
    assert "MARCHE_POST_REPAS" in refuses and "VELO_MODERE" in refuses


def test_le_classement_par_defaut_est_par_effet():
    ok, _ = interventions_possibles(ETAT_NORMAL)
    effets = [i.effet_pic for i in ok]
    assert effets == sorted(effets)          # du plus abaissant au moins


# --------------------------------------------------------------------------- #
# 2. L'état interdit prime sur tout
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("etat,motif", [
    (ETAT_BAS, "basse"), (ETAT_CHUTE, "chute"), (ETAT_RISQUE, "hypoglycemie")])
def test_aucun_conseil_dans_un_etat_a_risque(etat, motif):
    autorise, raison = etat_autorise_recommandation(etat)
    assert not autorise and motif in raison


def test_une_sortie_parfaite_est_refusee_si_l_etat_l_interdit():
    """Le point clé : la qualité de la sortie ne rachète pas l'état."""
    parfaite = {"interventions": ["INDEX_GLYCEMIQUE_BAS"], "texte": "Suggestion douce."}
    v = valider(parfaite, ETAT_BAS)
    assert not v.ok and v.etat_interdit


def test_le_systeme_refuse_plutot_que_de_conseiller():
    r = recommander(ETAT_BAS, llm=FakeLLM({"interventions": ["FIBRES"], "texte": "ok"}))
    assert r.source == "refus" and r.interventions == []


# --------------------------------------------------------------------------- #
# 3. Sorties hostiles du modèle
# --------------------------------------------------------------------------- #

def test_identifiant_invente_rejete():
    v = valider({"interventions": ["JEUNER_24H"], "texte": "Essayez ceci."}, ETAT_NORMAL)
    assert not v.ok
    assert any("hors catalogue" in r for r in v.refus)


def test_intervention_contre_indiquee_rejetee_meme_bien_orthographiee():
    """Vélo à 95 mg/dL : l'identifiant existe, l'état l'interdit."""
    etat = {"glucose": 95.0, "pente_mg_min": 0.0, "risque_hypo": 0.02}
    v = valider({"interventions": ["VELO_MODERE"], "texte": "Un peu de velo."}, etat)
    assert not v.ok
    assert any("contre-indiquee" in r for r in v.refus)


@pytest.mark.parametrize("phrase", [
    "Pensez à ajuster votre insuline avant le repas.",
    "Augmentez la dose du soir.",
    "Votre traitement mériterait une revue.",
    "Prenez 4 UI de plus.",
    "Ceci confirme le diagnostic de diabète.",
])
def test_vocabulaire_medical_fait_echouer_toute_la_sortie(phrase):
    v = valider({"interventions": ["FIBRES"], "texte": phrase}, ETAT_NORMAL)
    assert not v.ok
    assert any("vocabulaire medical" in r for r in v.refus)
    assert v.texte == ""                       # la sortie est jetee, pas nettoyee


def test_les_mots_innocents_ne_declenchent_pas_le_filtre():
    """« domestique » contient « dose »… en apparence seulement."""
    sain = ("Une activité domestique modérée et davantage de fibres suffisent "
            "à lisser le pic simulé.")
    assert contient_vocabulaire_medical(sain) == []


def test_trop_de_recommandations_rejetees():
    v = valider({"interventions": [i.id for i in CATALOGUE[:5]], "texte": "ok"},
                ETAT_NORMAL)
    assert not v.ok
    assert any("trop de recommandations" in r for r in v.refus)


def test_texte_trop_long_rejete():
    v = valider({"interventions": ["FIBRES"], "texte": "a" * 900}, ETAT_NORMAL)
    assert not v.ok and any("trop long" in r for r in v.refus)


@pytest.mark.parametrize("brut", ["pas du json", "", "{cassé", "null", "[1,2]"])
def test_json_malforme_ne_casse_rien(brut):
    r = recommander(ETAT_NORMAL, llm=FakeLLM(brut))
    assert r.source == "repli"
    assert r.interventions                     # le repli, lui, propose


def test_api_en_panne_donne_le_repli():
    class LLMCasse:
        def completer(self, *a, **k):
            raise RuntimeError("503")
    r = recommander(ETAT_NORMAL, llm=LLMCasse())
    assert r.source == "repli" and r.interventions


# --------------------------------------------------------------------------- #
# 4. La propriété centrale
# --------------------------------------------------------------------------- #

def test_le_llm_ne_peut_jamais_elargir_l_ensemble_permis():
    """Quoi qu'il propose, il ne sort pas de ce que l'état autorise.

    On lui fait proposer *tout* le catalogue, y compris les contre-indiquées :
    l'ensemble retenu doit rester inclus dans celui du repli déterministe.
    """
    for etat in ({"glucose": 200.0}, {"glucose": 105.0},
                 {"glucose": 130.0, "asleep": True},
                 {"glucose": 160.0, "risque_hypo": 0.12}):
        permis = {i.id for i in interventions_possibles(etat)[0]}
        glouton = FakeLLM({"interventions": [i.id for i in CATALOGUE],
                           "texte": "Tout, tout de suite."})
        r = recommander(etat, llm=glouton)
        assert set(r.ids) <= permis, f"{etat} : {set(r.ids) - permis} en trop"


def test_sans_llm_la_couche_fonctionne():
    r = recommander(ETAT_NORMAL, llm=None)
    assert r.source == "repli" and r.interventions and r.texte


def test_une_sortie_valide_du_llm_est_acceptee():
    bon = {"interventions": ["INDEX_GLYCEMIQUE_BAS", "FIBRES"],
           "texte": "Deux ajustements simples du prochain repas suffisent à "
                    "lisser le pic que le jumeau simule."}
    r = recommander(ETAT_NORMAL, llm=FakeLLM(bon))
    assert r.source == "llm"
    assert r.ids == ["INDEX_GLYCEMIQUE_BAS", "FIBRES"]


def test_le_prompt_ne_contient_que_les_interventions_permises():
    """Le modèle ne doit pas même voir ce qu'il n'a pas le droit de proposer."""
    etat = {"glucose": 95.0}
    permis = {i.id for i in interventions_possibles(etat)[0]}
    faux = FakeLLM({"interventions": [], "texte": ""})
    recommander(etat, llm=faux)
    for i in CATALOGUE:
        if i.id not in permis:
            assert i.id not in faux.dernier_prompt, f"{i.id} fuit dans le prompt"


# --------------------------------------------------------------------------- #
# 5. Le parseur tolère la forme, jamais le fond
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("enrobage", [
    '```json\n{"interventions": ["FIBRES"], "texte": "ok"}\n```',
    'Voici ma réponse : {"interventions": ["FIBRES"], "texte": "ok"} — voilà.',
    '{"interventions": ["FIBRES"], "texte": "ok"}',
])
def test_le_json_est_recupere_malgre_l_enrobage(enrobage):
    d = extraire_json(enrobage)
    assert d.get("interventions") == ["FIBRES"]


def test_le_parseur_ne_valide_rien_par_lui_meme():
    """Récupérer le JSON n'est pas l'accepter — la sûreté reste au validateur."""
    d = extraire_json('{"interventions": ["INVENTE"], "texte": "insuline"}')
    assert d["interventions"] == ["INVENTE"]           # le parseur laisse passer
    assert not valider(d, ETAT_NORMAL).ok              # le validateur refuse
