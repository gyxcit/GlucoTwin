"""
Couche 2 — construction des features et des cibles.

Assemble, pour chaque instant t :

- les **concepts** produits par la couche 1 (le goulot interprétable) ;
- l'**historique glycémique** récent (niveau, retards, vitesse, accélération) ;
- le **contexte statique** du patient.

et pour cible la glycémie à t + H minutes.

Deux formulations de cible sont proposées :

- ``level``  : prédire la valeur absolue → un modèle peut « tricher » en
  recopiant la glycémie actuelle (c'est la baseline de persistance) ;
- ``delta``  : prédire la **variation** → le modèle est forcé d'apprendre la
  dynamique. C'est la formulation à privilégier.

Le découpage respecte les frontières patient/jour : aucun retard ne traverse
une frontière, donc aucune fuite temporelle.
"""

from __future__ import annotations

import numpy as np

#: Concepts issus de la couche 1.
CONCEPT_COLS = [
    "asleep",
    "met_now",
    "energy_rate_kcal_min",
    "cho_ox_rate_g_min",
    "glucose_uptake_mg_min",
    "glycogen_deficit_g",
    "cob_g",
    "carb_ra_g_min",
    "circadian_factor",
    "insulin_sensitivity_index",
    "dawn_factor",
    "hepatic_output_mg_min",
    "net_glucose_flux_mg_min",
]

#: Contexte statique du patient.
STATIC_COLS = ["weight_kg"]

#: Retards glycémiques utilisés (en minutes).
LAGS_MIN = [15, 30, 60]


def build_features(
    df,
    horizon_min: int = 30,
    step_min: int = 5,
    target: str = "delta",
    concept_cols: list[str] | None = None,
):
    """Construit ``(X, y, groups, g_now, feature_names)``.

    ``g_now`` est renvoyé séparément : c'est la **baseline de persistance**, et
    il sert aussi à reconstruire le niveau absolu quand ``target='delta'``.
    """
    concept_cols = CONCEPT_COLS if concept_cols is None else concept_cols
    h_steps = horizon_min // step_min
    lag_steps = [m // step_min for m in LAGS_MIN]
    max_lag = max(lag_steps)

    X_parts, y_parts, grp_parts, now_parts = [], [], [], []

    for (pid, _day), block in df.groupby(["patient", "day"], sort=False):
        block = block.sort_values("t_h")
        n = len(block)
        if n <= max_lag + h_steps:
            continue

        g = block["glucose"].to_numpy(dtype=float)
        t_h = block["t_h"].to_numpy(dtype=float)
        concepts = block[concept_cols].to_numpy(dtype=float)
        static = block[STATIC_COLS].to_numpy(dtype=float)

        # Indices valides : assez d'historique en arrière, assez d'horizon devant.
        idx = np.arange(max_lag, n - h_steps)

        feats = [concepts[idx], static[idx]]
        # heure du jour, encodée cycliquement
        feats.append(np.c_[np.sin(2 * np.pi * t_h[idx] / 24.0),
                           np.cos(2 * np.pi * t_h[idx] / 24.0)])
        # glycémie courante et retards
        feats.append(g[idx].reshape(-1, 1))
        for ls in lag_steps:
            feats.append(g[idx - ls].reshape(-1, 1))
        # variations, vitesse, accélération
        d15 = g[idx] - g[idx - lag_steps[0]]
        d30 = g[idx] - g[idx - lag_steps[1]]
        feats.append(d15.reshape(-1, 1))
        feats.append(d30.reshape(-1, 1))
        vel = (g[idx] - g[idx - 1]) / step_min
        prev_vel = (g[idx - 1] - g[idx - 2]) / step_min
        feats.append(vel.reshape(-1, 1))
        feats.append(((vel - prev_vel) / step_min).reshape(-1, 1))

        X_parts.append(np.hstack(feats))
        future = g[idx + h_steps]
        y_parts.append(future - g[idx] if target == "delta" else future)
        now_parts.append(g[idx])
        grp_parts.append(np.full(len(idx), pid))

    X = np.vstack(X_parts)
    y = np.concatenate(y_parts)
    groups = np.concatenate(grp_parts)
    g_now = np.concatenate(now_parts)

    names = (
        list(concept_cols)
        + list(STATIC_COLS)
        + ["sin_hour", "cos_hour", "glucose_now"]
        + [f"glucose_lag{m}" for m in LAGS_MIN]
        + ["delta15", "delta30", "velocity", "acceleration"]
    )
    assert X.shape[1] == len(names), (X.shape[1], len(names))
    return X, y, groups, g_now, names


def to_absolute(pred, g_now, target: str = "delta"):
    """Ramène une prédiction au niveau glycémique absolu (mg/dL)."""
    return g_now + pred if target == "delta" else pred
