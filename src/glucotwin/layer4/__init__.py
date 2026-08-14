"""
Couche 4 — recommandations à **catalogue fermé**.

Un LLM qui écrit librement des conseils à un patient diabétique est un
générateur d'incidents. Cette couche l'enferme : il ne choisit que dans un
catalogue fixe d'interventions non médicamenteuses, et **tout ce qu'il produit
passe par un validateur déterministe** qui peut le refuser en bloc.

La règle est simple et elle ne se négocie pas : *si la validation échoue, on
n'affiche pas le texte du modèle*. On retombe sur le classement déterministe,
ou on refuse de conseiller.
"""

from .catalogue import CATALOGUE, Intervention, interventions_possibles
from .validator import ValidationResult, valider
from .recommend import recommander

__all__ = ["CATALOGUE", "Intervention", "interventions_possibles",
           "ValidationResult", "valider", "recommander"]
