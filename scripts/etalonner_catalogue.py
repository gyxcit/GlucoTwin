#!/usr/bin/env python3
"""
Étalonnage du catalogue de la couche 4 — d'où viennent les mg/dL.

    python scripts/etalonner_catalogue.py

Chaque intervention est traduite en **modification de l'emploi du temps** (moins
de glucides, un index glycémique plus bas, une marche en plus…), repassée par la
couche 1, puis simulée par le modèle réduit. L'écart de pic est l'effet.

Le script produit deux colonnes qui sont tout l'intérêt de la couche 4 :

- **population** : θ par défaut, le patient moyen — ce que le catalogue affiche ;
- **personnel** : θ médian calibré sur les 44 patients CGMacros — ce que l'agent
  lit avec son outil `simuler_intervention`.

Le même code calcule les deux. L'écart entre les colonnes est donc entièrement
imputable à θ, c'est-à-dire à la calibration du patient — et à rien d'autre.

Sorties : results/catalogue_effets.json · results/logs/etalonnage_catalogue.log
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from glucotwin.calibration import REDUCED_DEFAULT
from glucotwin.layer4.catalogue import CATALOGUE
from glucotwin.layer4.etalonnage import effet_de, journee_de_reference

RACINE = Path(__file__).resolve().parents[1]
SORTIE_JSON = RACINE / "results" / "catalogue_effets.json"
SORTIE_LOG = RACINE / "results" / "logs" / "etalonnage_catalogue.log"

#: θ médian du modèle réduit sur CGMacros — results/reparametrisation.json.
THETA_MEDIAN_CGMACROS = np.array([0.5617908640540168, 0.4997268310027497,
                                  0.035438440067852656, 130.52913322915543])


def entete() -> list[str]:
    """La provenance : sans elle, un chiffre archivé ne vaut rien."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RACINE,
                                capture_output=True, text=True).stdout.strip()
    except Exception:                                           # noqa: BLE001
        commit = "inconnu"
    return [
        "# GlucoTwin — etalonnage du catalogue de la couche 4",
        f"# commande : python scripts/etalonner_catalogue.py",
        f"# date     : {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"# commit   : {commit}",
        f"# python   : {platform.python_version()} · numpy {np.__version__}",
        "",
    ]


def main() -> int:
    lignes = entete()

    def dire(texte: str = "") -> None:
        print(texte)
        lignes.append(texte)

    jour = journee_de_reference()
    dire("Journee de reference (volontairement sedentaire) :")
    for m in jour.meals:
        dire(f"  repas {m.time_h:>5.2f} h · {m.carbs_g:>5.1f} g de glucides · "
             f"IG {m.gi:.2f} · fibres {m.fiber_g:.0f} g")
    for a in jour.activities:
        dire(f"  activite {a.code} a {a.start_h:>5.2f} h · {a.duration_min:.0f} min")
    dire()

    dire("theta population : " + ", ".join(f"{v:.4g}" for v in REDUCED_DEFAULT))
    dire("theta median CGMacros (44 patients, modele reduit) : "
         + ", ".join(f"{v:.4g}" for v in THETA_MEDIAN_CGMACROS))
    dire()

    dire(f"{'intervention':<22}{'population':>12}{'personnel':>11}{'ecart':>8}"
         f"{'moyenne':>9}{'TIR pts':>9}")
    dire("-" * 71)

    resultats = {}
    for i in CATALOGUE:
        pop = effet_de(i.id, jour, REDUCED_DEFAULT)
        perso = effet_de(i.id, jour, THETA_MEDIAN_CGMACROS)
        ecart = round(perso["effet_pic"] - pop["effet_pic"], 1)
        resultats[i.id] = {"population": pop, "personnel": perso,
                           "ecart_pic_mg_dl": ecart,
                           "catalogue_effet_pic": i.effet_pic}
        dire(f"{i.id:<22}{pop['effet_pic']:>+12.1f}{perso['effet_pic']:>+11.1f}"
             f"{ecart:>+8.1f}{pop['effet_moyenne']:>+9.1f}"
             f"{pop['gain_temps_dans_cible_pts']:>+9.1f}")

    dire()
    ecarts = [abs(r["catalogue_effet_pic"] - r["population"]["effet_pic"])
              for r in resultats.values()]
    dire(f"Ecart maximal entre catalogue.py et le recalcul : {max(ecarts):.2f} mg/dL")
    dire("(un test de la suite echoue si cet ecart depasse 0,1 mg/dL)")
    dire()

    nuls = [k for k, r in resultats.items() if abs(r["population"]["effet_pic"]) < 0.05]
    if nuls:
        dire("Effet nul sur le pic, et on l'assume : " + ", ".join(nuls))
        dire("  Le modele reduit n'a ni sensibilite prolongee apres l'effort, ni")
        dire("  penalite circadienne du soir. Ces interventions n'y changent donc")
        dire("  pas le pic. C'est une limite du modele, pas un resultat clinique.")
        dire()

    moy_pop = np.mean([r["population"]["effet_pic"] for r in resultats.values()])
    moy_perso = np.mean([r["personnel"]["effet_pic"] for r in resultats.values()])
    facteur = moy_pop / moy_perso
    dire(f"Effet moyen sur le pic : population {moy_pop:+.1f} mg/dL, "
         f"patient median CGMacros {moy_perso:+.1f} mg/dL "
         f"({moy_perso / moy_pop * 100:.0f} % de l'effet de population)")
    dire(f"Autrement dit, annoncer l'effet de population a ce patient-la le")
    dire(f"surestimerait d'un facteur {facteur:.1f}. C'est ce que l'agent corrige,")
    dire("et c'est la seule raison de lui donner des outils plutot qu'un resume.")

    SORTIE_JSON.parent.mkdir(parents=True, exist_ok=True)
    SORTIE_LOG.parent.mkdir(parents=True, exist_ok=True)
    SORTIE_JSON.write_text(json.dumps(resultats, indent=1, ensure_ascii=False),
                           encoding="utf-8")
    SORTIE_LOG.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"\n-> {SORTIE_JSON.relative_to(RACINE)}")
    print(f"-> {SORTIE_LOG.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
