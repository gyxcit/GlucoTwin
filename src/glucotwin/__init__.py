"""GlucoTwin — jumeau numérique du patient diabétique de type 2.

Architecture en couches :

- ``metabolic_engine`` : activité → dépense énergétique et oxydation des substrats
- ``day_concepts``     : emploi du temps → flux de concepts métaboliques (couches 0-1)
- ``layer2``           : concepts → prévision glycémique et évaluation (couche 2)
"""

__version__ = "0.1.0"
