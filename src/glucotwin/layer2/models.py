"""Modèles comparés en couche 2.

La **persistance** n'est pas ici : elle est traitée nativement par le harnais
d'évaluation, comme baseline obligatoire de toute comparaison.
"""

from __future__ import annotations


def model_zoo() -> dict:
    """Fabriques de modèles (callables sans argument)."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return {
        "ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "hgb": lambda: HistGradientBoostingRegressor(
            max_iter=250, learning_rate=0.06, max_depth=6,
            early_stopping=True, validation_fraction=0.12, random_state=0,
        ),
    }
