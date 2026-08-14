#!/usr/bin/env python3
"""
Couche 4 — démonstration des recommandations à catalogue fermé.

    python scripts/run_reco.py                    # sans LLM, entierement deterministe
    python scripts/run_reco.py --llm              # avec Mistral (lit MISTRAL_API_KEY)
    python scripts/run_reco.py --llm --agent      # agent + outils sur le jumeau calibre
    python scripts/run_reco.py --llm --env .env   # charge la cle depuis un fichier

**La clé n'est jamais lue depuis le dépôt ni écrite dans une sortie.** Elle vient
de l'environnement, ou d'un `.env` que `.gitignore` exclut.

Le script parcourt une série d'états métaboliques, dont plusieurs sont
volontairement à risque, et montre ce que la couche 4 répond dans chacun — y
compris quand elle refuse.

Avec `--agent`, le modèle ne reçoit plus un résumé pré-digéré : il dispose
d'outils et peut **simuler chaque intervention sur le jumeau calibré**. La trace
des appels est affichée, et l'écart entre l'effet mesuré sur ce patient et
l'effet de population du catalogue est ce que l'agent apporte. Les bornes ne
changent pas : registre fermé, budget d'étapes, et la réponse finale passe par
le même validateur.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

from glucotwin.layer4.agent import executer_agent
from glucotwin.layer4.catalogue import interventions_possibles
from glucotwin.layer4.etalonnage import journee_de_reference
from glucotwin.layer4.recommend import recommander
from glucotwin.layer4.tools import contexte_depuis_planning

#: Paramètres médians du modèle réduit, **mesurés sur les 44 patients CGMacros**
#: (results/reparametrisation.json). Le jumeau de démonstration n'est donc pas
#: inventé : c'est le patient median de la cohorte reelle.
THETA_MEDIAN = np.array([0.5617908640540168, 0.4997268310027497,
                         0.035438440067852656, 130.52913322915543])


SCENARIOS = [
    ("apres un repas copieux",
     {"glucose": 205.0, "pente_mg_min": 0.8, "risque_hypo": 0.01,
      "cob_g": 65.0, "met": 1.3, "pic": 248.0}),
    ("plateau de milieu d'apres-midi",
     {"glucose": 148.0, "pente_mg_min": -0.1, "risque_hypo": 0.03,
      "cob_g": 8.0, "met": 1.6, "pic": 190.0}),
    ("glycemie limite, pas de danger immediat",
     {"glucose": 98.0, "pente_mg_min": 0.0, "risque_hypo": 0.08,
      "cob_g": 2.0, "met": 1.3, "pic": 140.0}),
    ("PENDANT LE SOMMEIL",
     {"glucose": 155.0, "pente_mg_min": -0.05, "risque_hypo": 0.04,
      "asleep": True, "cob_g": 0.0, "met": 0.95, "pic": 175.0}),
    ("GLYCEMIE BASSE — le systeme doit refuser",
     {"glucose": 76.0, "pente_mg_min": -0.2, "risque_hypo": 0.12}),
    ("CHUTE RAPIDE — le systeme doit refuser",
     {"glucose": 145.0, "pente_mg_min": -1.1, "risque_hypo": 0.18}),
    ("RISQUE D'HYPO ANNONCE — le systeme doit refuser",
     {"glucose": 135.0, "pente_mg_min": -0.2, "risque_hypo": 0.42}),
]


def charger_env(chemin: str) -> None:
    """Charge un .env minimal, sans dépendance, sans jamais afficher les valeurs."""
    if not os.path.exists(chemin):
        print(f"  (pas de fichier {chemin})")
        return
    n = 0
    with open(chemin, encoding="utf-8") as fh:
        for ligne in fh:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            cle, val = ligne.split("=", 1)
            os.environ.setdefault(cle.strip(), val.strip().strip('"').strip("'"))
            n += 1
    print(f"  {n} variable(s) chargee(s) depuis {chemin} (valeurs non affichees)")


def table_des_effets(ctx) -> None:
    """Ce que les outils mesurent — **sans aucun LLM**.

    C'est le contenu que l'agent va chercher : pour chaque intervention, l'effet
    simulé sur *ce* jumeau, en face de l'effet de population du catalogue. Le
    tableau est déterministe et reproductible ; le modèle de langage n'ajoute
    ensuite que la sélection et la formulation.
    """
    from glucotwin.layer4.catalogue import CATALOGUE
    from glucotwin.layer4.tools import executer

    print("Effet mesure sur ce jumeau contre effet de population (outil "
          "simuler_intervention) :")
    print(f"  {'intervention':<22} {'pic mesure':>11} {'moyenne':>9} "
          f"{'population':>11} {'ecart':>8}")
    for i in CATALOGUE:
        o = executer("simuler_intervention", {"id": i.id}, ctx)
        if "erreur" in o:
            print(f"  {i.id:<22} {o['erreur']}")
            continue
        ecart = o["effet_mesure_mg_dl"] - o["effet_population_mg_dl"]
        print(f"  {i.id:<22} {o['effet_mesure_mg_dl']:>+11.1f} "
              f"{o['effet_moyenne_mg_dl']:>+9.1f} "
              f"{o['effet_population_mg_dl']:>+11.1f} {ecart:>+8.1f}")
    print("  L'ecart est l'information que le LLM seul n'aurait pas eue : le")
    print("  catalogue annonce une moyenne, le jumeau calibre repond pour ce patient.\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Couche 4 — recommandations")
    ap.add_argument("--llm", action="store_true", help="appeler Mistral")
    ap.add_argument("--agent", action="store_true",
                    help="boucle agent + outils sur le jumeau calibre")
    ap.add_argument("--simuler-llm", action="store_true",
                    help="agent avec un LLM SCRIPTE (deterministe, pour la trace)")
    ap.add_argument("--env", default=".env", help="fichier de variables")
    ap.add_argument("--modele", default="mistral-small-latest")
    args = ap.parse_args()

    llm = None
    if args.simuler_llm:
        # Un modèle scripté, pas un modèle. Sert uniquement à montrer la trace
        # d'appels d'outils quand le réseau n'est pas disponible ; la sortie
        # passe par exactement le même validateur que le modèle réel.
        from glucotwin.layer4.llm import LLMScripte
        llm = LLMScripte([
            json.dumps({"outil": "etat_courant", "arguments": {}}),
            json.dumps({"outil": "simuler_intervention",
                        "arguments": {"id": "REDUIRE_GLUCIDES"}}),
            json.dumps({"outil": "simuler_intervention",
                        "arguments": {"id": "FRACTIONNER_REPAS"}}),
            json.dumps({"interventions": ["REDUIRE_GLUCIDES", "FRACTIONNER_REPAS"],
                        "texte": "Sur votre jumeau, alleger le prochain repas "
                                 "d'un tiers abaisse le pic de 17 mg/dL et le "
                                 "fractionner de 12 — nettement moins que les "
                                 "45 et 30 annonces en moyenne."}),
        ])
        args.agent = True
        print("LLM SCRIPTE (aucun appel reseau) — sert a montrer la trace.\n")
    if args.llm:
        print("Chargement de la cle :")
        charger_env(args.env)
        from glucotwin.layer4.llm import MistralLLM
        try:
            llm = MistralLLM(modele=args.modele)
            print(f"  modele : {args.modele}\n")
        except RuntimeError as e:
            print(f"  {e}\n  -> on continue SANS LLM (mode deterministe).\n")

    ctx = None
    if args.agent:
        ctx = contexte_depuis_planning(journee_de_reference(), THETA_MEDIAN)
        g = ctx.simuler()
        print("Jumeau de demonstration : patient median CGMacros "
              f"(theta reduit, results/reparametrisation.json)")
        print(f"  journee simulee : pic {g.max():.0f} mg/dL, "
              f"moyenne {g.mean():.0f} mg/dL\n")
        ctx.etat = dict(SCENARIOS[0][1])
        table_des_effets(ctx)

    print("=" * 74)
    mode = "[deterministe]"
    if args.simuler_llm:
        mode = "[agent + outils, LLM scripte]"
    elif llm and args.agent:
        mode = "[agent + outils]"
    elif llm:
        mode = "[avec LLM]"
    elif args.agent:
        mode = "[agent sans LLM = repli]"
    print("COUCHE 4 — recommandations a catalogue ferme  " + mode)
    print("=" * 74)

    refus = 0
    for titre, etat in SCENARIOS:
        possibles, ecartees = interventions_possibles(etat)
        if args.agent:
            r = executer_agent(etat, ctx, llm)
        else:
            r = recommander(etat, llm=llm)
        print(f"\n— {titre}")
        print(f"  glycemie {etat['glucose']:.0f} mg/dL · "
              f"tendance {etat.get('pente_mg_min', 0):+.2f} · "
              f"risque hypo {etat.get('risque_hypo', 0) * 100:.0f} %"
              + ("  · endormi" if etat.get("asleep") else ""))
        print(f"  catalogue : {len(possibles)} possibles, {len(ecartees)} ecartees")
        if r.source == "refus":
            refus += 1
            print("  >> REFUS — " + r.texte)
            continue
        for e in r.trace:
            print("     · " + e.resume())
        print(f"  >> [{r.source}] " + " · ".join(r.ids))
        print("     " + r.texte[:220])
        if r.validation and not r.validation.ok:
            print(f"     (sortie du LLM rejetee : {r.validation.raison()})")

    print("\n" + "=" * 74)
    print(f"{refus} scenarios sur {len(SCENARIOS)} ont declenche un refus.")
    print("Le refus n'est pas un echec : c'est la reponse correcte quand l'etat")
    print("interdit de conseiller. Aucune sortie de modele ne peut le contourner.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
