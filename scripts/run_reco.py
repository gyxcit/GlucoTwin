#!/usr/bin/env python3
"""
Couche 4 — démonstration des recommandations à catalogue fermé.

    python scripts/run_reco.py                  # sans LLM, entierement deterministe
    python scripts/run_reco.py --llm            # avec Mistral (lit MISTRAL_API_KEY)
    python scripts/run_reco.py --llm --env .env # charge la cle depuis un fichier

**La clé n'est jamais lue depuis le dépôt ni écrite dans une sortie.** Elle vient
de l'environnement, ou d'un `.env` que `.gitignore` exclut.

Le script parcourt une série d'états métaboliques, dont plusieurs sont
volontairement à risque, et montre ce que la couche 4 répond dans chacun — y
compris quand elle refuse.
"""

from __future__ import annotations

import argparse
import os
import sys

from glucotwin.layer4.catalogue import interventions_possibles
from glucotwin.layer4.recommend import recommander

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


def main() -> int:
    ap = argparse.ArgumentParser(description="Couche 4 — recommandations")
    ap.add_argument("--llm", action="store_true", help="appeler Mistral")
    ap.add_argument("--env", default=".env", help="fichier de variables")
    ap.add_argument("--modele", default="mistral-small-latest")
    args = ap.parse_args()

    llm = None
    if args.llm:
        print("Chargement de la cle :")
        charger_env(args.env)
        from glucotwin.layer4.llm import MistralLLM
        try:
            llm = MistralLLM(modele=args.modele)
            print(f"  modele : {args.modele}\n")
        except RuntimeError as e:
            print(f"  {e}\n  -> on continue SANS LLM (mode deterministe).\n")

    print("=" * 74)
    print("COUCHE 4 — recommandations a catalogue ferme" +
          ("  [avec LLM]" if llm else "  [deterministe]"))
    print("=" * 74)

    refus = 0
    for titre, etat in SCENARIOS:
        possibles, ecartees = interventions_possibles(etat)
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
