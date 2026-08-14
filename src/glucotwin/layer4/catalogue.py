"""
Le catalogue fermé — la seule chose que le système a le droit de proposer.

Trois règles ont présidé à son contenu :

1. **Aucune intervention médicamenteuse.** Ni insuline, ni dose, ni traitement.
   Ce prototype n'est pas un dispositif médical et n'a pas à s'en approcher.
2. **Chaque entrée porte ses contre-indications**, exprimées comme des
   conditions sur l'état métabolique — pas comme des consignes en langage
   naturel qu'un modèle pourrait réinterpréter.
3. **L'effet annoncé est calculé, pas posé.** Chaque `effet_pic` est produit par
   `scripts/etalonner_catalogue.py`, qui traduit l'intervention en modification
   de l'emploi du temps, la fait passer par la couche 1 puis par le modèle
   réduit avec θ de population, et lit l'écart de pic. Les valeurs sont
   archivées dans `results/catalogue_effets.json`, et un test compare le
   catalogue au recalcul : si le modèle bouge et que le catalogue ne suit pas,
   la suite de tests casse.

L'ablation sur données réelles conforte l'ordre obtenu : la branche alimentaire
porte 91 à 99 % du pouvoir explicatif, l'activité beaucoup moins. Les
interventions alimentaires sortent en tête — et c'est mesuré, pas décidé.

**Deux entrées ressortent à effet nul, et on les garde ainsi.** Le modèle réduit
n'a aucun mécanisme de sensibilité à l'insuline prolongée après l'effort, ni de
dégradation de la tolérance au glucose en soirée : le vélo de fin de journée et
l'avancement du dîner n'y changent donc pas le pic. C'est une limite du modèle,
pas une preuve que ces interventions sont inutiles — la littérature dit le
contraire. Les afficher à 0,0 est la lecture honnête : le jumeau ne sait pas
encore le voir.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Intervention:
    """Une action possible, avec les conditions qui l'interdisent."""

    id: str
    titre: str
    detail: str
    #: effet sur le pic glycémique, en mg/dL (négatif = abaisse). **Calculé**
    #: par `scripts/etalonner_catalogue.py` sur la journée de référence avec le
    #: θ de population — jamais saisi à la main.
    effet_pic: float
    categorie: str
    #: glycémie en dessous de laquelle l'intervention est interdite
    glycemie_min: float = 0.0
    #: interdite si la glycémie descend plus vite que ce seuil (mg/dL/min)
    pente_min: float = -99.0
    #: interdite pendant le sommeil
    interdite_si_endormi: bool = False
    #: interdite si un risque d'hypoglycémie est annoncé au-dessus de ce seuil
    risque_hypo_max: float = 1.0

    def applicable(self, etat: dict) -> tuple[bool, str]:
        """(applicable, raison du refus). L'ordre des tests est celui de la gravité."""
        g = float(etat.get("glucose", 120.0))
        pente = float(etat.get("pente_mg_min", 0.0))
        risque = float(etat.get("risque_hypo", 0.0))
        endormi = bool(etat.get("asleep", False))

        if g < self.glycemie_min:
            return False, f"glycemie {g:.0f} < {self.glycemie_min:.0f} mg/dL"
        if pente < self.pente_min:
            return False, f"glycemie en baisse rapide ({pente:.2f} mg/dL/min)"
        if risque > self.risque_hypo_max:
            return False, f"risque d'hypoglycemie annonce a {risque * 100:.0f} %"
        if endormi and self.interdite_si_endormi:
            return False, "la personne dort"
        return True, ""


#: Le catalogue. **Rien en dehors de cette liste ne peut être recommandé.**
CATALOGUE: list[Intervention] = [
    Intervention(
        id="REDUIRE_GLUCIDES",
        titre="Réduire la charge glucidique du prochain repas",
        detail="Diminuer d'environ un tiers la portion de féculents ou de sucres "
               "rapides, à composition égale par ailleurs.",
        effet_pic=-44.7, categorie="alimentation",
        glycemie_min=100.0, pente_min=-0.5, risque_hypo_max=0.10,
    ),
    Intervention(
        id="INDEX_GLYCEMIQUE_BAS",
        titre="Privilégier des aliments à index glycémique bas",
        detail="Remplacer les sucres rapides par des équivalents plus lents : "
               "légumineuses, céréales complètes.",
        effet_pic=-26.3, categorie="alimentation",
        glycemie_min=90.0, risque_hypo_max=0.15,
    ),
    Intervention(
        id="FIBRES",
        titre="Ajouter des fibres au repas",
        detail="Une portion de légumes ou de légumineuses ralentit l'absorption "
               "des glucides du même repas.",
        effet_pic=-11.3, categorie="alimentation",
        glycemie_min=90.0, risque_hypo_max=0.15,
    ),
    Intervention(
        id="MARCHE_POST_REPAS",
        titre="Marcher 30 minutes après le repas",
        detail="Une marche d'intensité modérée dans l'heure qui suit le repas.",
        effet_pic=-10.0, categorie="activite",
        glycemie_min=100.0, pente_min=-0.4,
        interdite_si_endormi=True, risque_hypo_max=0.08,
    ),
    Intervention(
        id="VELO_MODERE",
        titre="45 minutes de vélo en fin de journée",
        detail="Effort modéré et continu, en dehors des trois heures précédant "
               "le coucher.",
        effet_pic=0.0, categorie="activite",
        glycemie_min=110.0, pente_min=-0.3,
        interdite_si_endormi=True, risque_hypo_max=0.05,
    ),
    Intervention(
        id="AVANCER_DINER",
        titre="Avancer le dîner",
        detail="Décaler le dernier repas de deux à trois heures plus tôt, la "
               "tolérance au glucose se dégradant en soirée.",
        effet_pic=0.0, categorie="rythme",
        glycemie_min=90.0, risque_hypo_max=0.20,
    ),
    Intervention(
        id="FRACTIONNER_REPAS",
        titre="Fractionner le repas en deux prises",
        detail="Répartir la même quantité en deux prises espacées d'environ "
               "deux heures.",
        effet_pic=-29.8, categorie="rythme",
        glycemie_min=100.0, risque_hypo_max=0.10,
    ),
]

CATALOGUE_PAR_ID = {i.id: i for i in CATALOGUE}

#: Ce que le système répond quand l'état interdit tout conseil.
REFUS_ETAT_BAS = (
    "La glycémie est basse ou en baisse rapide. Ce prototype ne formule "
    "aucune recommandation dans cette situation."
)


def interventions_possibles(etat: dict) -> tuple[list[Intervention], list[tuple[str, str]]]:
    """Filtre le catalogue selon l'état métabolique courant.

    Renvoie `(retenues, refusees)`, `refusees` étant une liste de
    `(id, raison)` — parce qu'un refus silencieux est indébogable.

    Le tri est par effet décroissant : c'est le classement **déterministe**,
    celui sur lequel on retombe si le LLM échoue.
    """
    ok, ko = [], []
    for i in CATALOGUE:
        applicable, raison = i.applicable(etat)
        (ok if applicable else ko).append(i if applicable else (i.id, raison))
    ok.sort(key=lambda i: i.effet_pic)
    return ok, ko
