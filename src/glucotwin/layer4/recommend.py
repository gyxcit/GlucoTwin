"""
L'orchestration — et la garantie que le LLM ne peut pas la contourner.

    état ──► catalogue filtré ──► [LLM] ──► validateur ──► sortie
                    │                            │
                    └──────── repli déterministe ┘

Le point important est le **repli**. Si le modèle échoue, invente, dérape ou ne
répond pas, on n'affiche pas sa sortie : on affiche le classement déterministe
du catalogue, qui n'a jamais eu besoin de lui. Le LLM n'ajoute que de la
formulation ; il n'est jamais dans le chemin critique de la sûreté.

Conséquence testable, et testée : **pour tout état donné, l'ensemble des
interventions affichables est le même avec ou sans LLM.** Le modèle peut
réordonner et rédiger, jamais élargir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .catalogue import REFUS_ETAT_BAS, Intervention, interventions_possibles
from .llm import SYSTEME, construire_prompt, extraire_json
from .validator import ValidationResult, etat_autorise_recommandation, valider


@dataclass
class Recommandation:
    """Ce que la couche 4 rend, avec la trace de comment on y est arrivé."""

    interventions: list[Intervention] = field(default_factory=list)
    texte: str = ""
    #: "llm" · "repli" · "refus"
    source: str = "repli"
    validation: ValidationResult | None = None
    refusees: list[tuple[str, str]] = field(default_factory=list)
    #: trace des appels d'outils quand la recommandation vient de l'agent
    trace: list = field(default_factory=list)

    @property
    def ids(self) -> list[str]:
        return [i.id for i in self.interventions]

    def resume(self) -> str:
        if self.source == "refus":
            return REFUS_ETAT_BAS
        tete = " · ".join(i.titre for i in self.interventions)
        return f"[{self.source}] {tete}"


def texte_deterministe(interventions: list[Intervention]) -> str:
    """La formulation de repli : plate, exacte, sans modèle de langage."""
    if not interventions:
        return "Aucune suggestion applicable dans l'état actuel."
    bouts = [f"{i.titre.lower()} (" + (
                 "effet non restitué par le modèle réduit"
                 if abs(i.effet_pic) < 0.5
                 else f"effet simulé {i.effet_pic:+.0f} mg/dL sur le pic") + ")"
             for i in interventions]
    return ("D'après la simulation du jumeau, par effet décroissant : "
            + " ; ".join(bouts) + ".")


def recommander(etat: dict, llm=None, *, n_max: int = 3) -> Recommandation:
    """Produit une recommandation validée pour l'état donné.

    `llm` peut être `None` — la couche 4 fonctionne alors entièrement sans
    modèle de langage, et c'est le comportement de référence.
    """
    autorise, raison = etat_autorise_recommandation(etat)
    if not autorise:
        return Recommandation(
            interventions=[], texte=REFUS_ETAT_BAS, source="refus",
            validation=ValidationResult(ok=False, texte=REFUS_ETAT_BAS,
                                        refus=[f"etat interdit : {raison}"],
                                        etat_interdit=True))

    candidates, refusees = interventions_possibles(etat)
    repli = Recommandation(
        interventions=candidates[:n_max],
        texte=texte_deterministe(candidates[:n_max]),
        source="repli", refusees=refusees)

    if llm is None or not candidates:
        return repli

    try:
        brut = llm.completer(SYSTEME, construire_prompt(etat, candidates))
    except Exception:                                           # noqa: BLE001
        return repli                                            # le repli, toujours

    v = valider(extraire_json(brut), etat)
    if not v.ok:
        repli.validation = v
        return repli

    return Recommandation(interventions=v.interventions[:n_max], texte=v.texte,
                          source="llm", validation=v, refusees=refusees)
