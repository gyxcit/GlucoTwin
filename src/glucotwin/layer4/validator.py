"""
Le validateur — le seul composant qui protège vraiment.

Un LLM peut inventer une intervention, conseiller de l'exercice à un patient qui
descend à 70 mg/dL, ou glisser une phrase sur l'insuline. Le prompt n'y change
rien : un prompt est une suggestion, pas une garantie. La garantie est ici, en
code déterministe et testé contre des sorties **volontairement hostiles**.

Cinq contrôles, du plus grave au plus formel :

1. **État interdit** — si la glycémie est basse ou chute vite, aucune
   recommandation n'est acceptable, même correctement formulée.
2. **Hors catalogue** — toute intervention dont l'identifiant n'existe pas est
   rejetée. Le modèle choisit, il n'invente pas.
3. **Contre-indication** — une intervention du catalogue mais interdite dans
   l'état courant est rejetée, même si le modèle l'a bien orthographiée.
4. **Vocabulaire médical** — toute mention de traitement, dose, insuline,
   médicament fait échouer la validation entière. Le prototype n'est pas un
   dispositif médical et ne doit jamais en avoir l'air.
5. **Forme** — nombre d'éléments, longueur du texte, champs attendus.

En cas d'échec, on ne « corrige » pas la sortie du modèle : on la **jette**.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .catalogue import CATALOGUE_PAR_ID, REFUS_ETAT_BAS, Intervention

#: Seuils au-delà desquels aucune recommandation n'est produite, quelle qu'elle
#: soit. Ils sont volontairement prudents : le coût d'un refus est nul, celui
#: d'un mauvais conseil ne l'est pas.
GLYCEMIE_REFUS = 90.0
PENTE_REFUS = -0.6          # mg/dL/min
RISQUE_HYPO_REFUS = 0.25

#: Vocabulaire strictement interdit. On teste sur des **frontières de mots**,
#: pour ne pas rejeter « domestique » à cause de « dose ».
TERMES_INTERDITS = [
    r"insulin\w*", r"dose\w*", r"posologi\w*", r"médicament\w*", r"medicament\w*",
    r"metformin\w*", r"traitement\w*", r"prescri\w*", r"ordonnance\w*",
    r"unités?\s+d[eu]", r"\bUI\b", r"injecter", r"injection\w*",
    r"augmenter\s+(?:votre|le|la)\s+trait\w*", r"arrêter\s+(?:votre|le|la)\s+trait\w*",
    r"diagnosti\w*", r"guéri\w*", r"gueri\w*",
]
_MOTIFS = [re.compile(t, re.IGNORECASE) for t in TERMES_INTERDITS]

#: Bornes de forme.
MAX_RECOMMANDATIONS = 3
MAX_CARACTERES_TEXTE = 600


@dataclass
class ValidationResult:
    """Verdict du validateur. `ok=False` ⇒ la sortie du modèle est jetée."""

    ok: bool
    interventions: list[Intervention] = field(default_factory=list)
    texte: str = ""
    refus: list[str] = field(default_factory=list)
    #: True quand l'état lui-même interdit toute recommandation
    etat_interdit: bool = False

    def raison(self) -> str:
        return " · ".join(self.refus) if self.refus else "valide"


def etat_autorise_recommandation(etat: dict) -> tuple[bool, str]:
    """Peut-on conseiller quoi que ce soit dans cet état ?

    Ce contrôle précède tout le reste et ne dépend pas du modèle : même une
    sortie parfaitement formée est refusée si la situation est à risque.
    """
    g = float(etat.get("glucose", 120.0))
    pente = float(etat.get("pente_mg_min", 0.0))
    risque = float(etat.get("risque_hypo", 0.0))
    if g < GLYCEMIE_REFUS:
        return False, f"glycemie basse ({g:.0f} mg/dL)"
    if pente < PENTE_REFUS:
        return False, f"chute rapide ({pente:.2f} mg/dL/min)"
    if risque > RISQUE_HYPO_REFUS:
        return False, f"risque d'hypoglycemie eleve ({risque * 100:.0f} %)"
    return True, ""


def contient_vocabulaire_medical(texte: str) -> list[str]:
    """Renvoie les termes interdits trouvés — vide si le texte est acceptable."""
    trouves = []
    for motif in _MOTIFS:
        m = motif.search(texte or "")
        if m:
            trouves.append(m.group(0).lower())
    return trouves


def valider(sortie: dict, etat: dict) -> ValidationResult:
    """Valide une sortie de LLM contre le catalogue et l'état métabolique.

    `sortie` est le dictionnaire renvoyé par le modèle :
    `{"interventions": ["ID", ...], "texte": "..."}`.
    """
    refus: list[str] = []

    # 1. l'état d'abord — il prime sur tout
    autorise, raison = etat_autorise_recommandation(etat)
    if not autorise:
        return ValidationResult(ok=False, texte=REFUS_ETAT_BAS,
                                refus=[f"etat interdit : {raison}"],
                                etat_interdit=True)

    if not isinstance(sortie, dict):
        return ValidationResult(ok=False, refus=["sortie du modele illisible"])

    ids = sortie.get("interventions")
    texte = sortie.get("texte", "") or ""
    if not isinstance(ids, list) or not ids:
        refus.append("aucune intervention proposee")
        ids = []
    if not isinstance(texte, str):
        refus.append("texte absent ou de mauvais type")
        texte = ""

    # 2. hors catalogue, 3. contre-indications
    retenues: list[Intervention] = []
    for raw in ids[:MAX_RECOMMANDATIONS + 3]:
        if not isinstance(raw, str) or raw not in CATALOGUE_PAR_ID:
            refus.append(f"hors catalogue : {raw!r}")
            continue
        inter = CATALOGUE_PAR_ID[raw]
        applicable, pourquoi = inter.applicable(etat)
        if not applicable:
            refus.append(f"contre-indiquee ({inter.id}) : {pourquoi}")
            continue
        if inter not in retenues:
            retenues.append(inter)

    if len(ids) > MAX_RECOMMANDATIONS:
        refus.append(f"trop de recommandations ({len(ids)} > {MAX_RECOMMANDATIONS})")

    # 4. vocabulaire médical — rédhibitoire
    interdits = contient_vocabulaire_medical(texte)
    if interdits:
        refus.append("vocabulaire medical : " + ", ".join(sorted(set(interdits))))

    # 5. forme
    if len(texte) > MAX_CARACTERES_TEXTE:
        refus.append(f"texte trop long ({len(texte)} caracteres)")

    if not retenues:
        refus.append("aucune intervention valide ne subsiste")

    return ValidationResult(ok=not refus, interventions=retenues,
                            texte=texte if not refus else "", refus=refus)
