"""
Couche 4 — recommandations à **catalogue fermé**.

Un LLM qui écrit librement des conseils à un patient diabétique est un
générateur d'incidents. Cette couche l'enferme : il ne choisit que dans un
catalogue fixe d'interventions non médicamenteuses, et **tout ce qu'il produit
passe par un validateur déterministe** qui peut le refuser en bloc.

La règle est simple et elle ne se négocie pas : *si la validation échoue, on
n'affiche pas le texte du modèle*. On retombe sur le classement déterministe,
ou on refuse de conseiller.

L'agent (`agent.py`) ne change rien à cette règle : il ajoute des **outils**
qui lui permettent de simuler une intervention sur le jumeau calibré du patient
— donc de dire « chez vous, -9 mg/dL » plutôt que « en moyenne, -16 » — mais sa
reponse finale passe par le meme validateur, et le meme repli.
"""

from .catalogue import CATALOGUE, Intervention, interventions_possibles
from .validator import ValidationResult, valider
from .recommend import recommander
from .tools import JumeauContext, OUTILS, executer
from .agent import executer_agent

__all__ = ["CATALOGUE", "Intervention", "interventions_possibles",
           "ValidationResult", "valider", "recommander",
           "JumeauContext", "OUTILS", "executer", "executer_agent"]
