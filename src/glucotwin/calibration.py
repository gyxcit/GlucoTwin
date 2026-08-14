"""
Calibration de la couche 1 **par patient** — le problème inverse.

La limite méthodologique numéro un du projet est le VCO₂ : les équations de
Frayn l'exigent, aucun objet connecté ne le mesure, et l'analyse de sensibilité
montre que la partition glucides/lipides en dépend à ±25 %. On peut s'arrêter là
et afficher des intervalles. Ou **inverser le problème** :

    on n'a pas besoin de mesurer le mécanisme si on observe son effet.

La glycémie est mesurée en continu. Plutôt que de deviner les paramètres
physiologiques d'un patient, on les **ajuste** pour que le modèle direct
reproduise sa glycémie observée. C'est un problème inverse classique, et il se
valide de la seule façon honnête : **calibrer sur les premiers jours, tester sur
les suivants**.

## Le modèle direct

Un compartiment, cinq paramètres par patient :

    dG/dt = [ gᵣ·Ra + g_h·HGP − g_u·Rd ] / V  −  k·(G − G_b)

- `Ra` — apparition du glucose alimentaire (couche 1, mg/min)
- `HGP` — production hépatique (couche 1)
- `Rd` — captation, repos et effort (couche 1)
- `V` — volume de distribution, 2,0 dL/kg × poids
- `gᵣ, g_h, g_u` — **gains patient** sur chacune des trois branches
- `k` — vitesse de retour à l'équilibre (1/min), `G_b` — glycémie d'équilibre

Les trois gains sont exactement ce que la couche 1 ne peut pas connaître :
sensibilité digestive, production hépatique basale, efficacité de la captation.
Les estimer revient à mesurer indirectement ce que le VCO₂ aurait donné —
et davantage.

## Ce qui est testé, et comment

Trois questions, dans cet ordre, chacune falsifiable :

1. **Identifiabilité** — sur des données engendrées avec des paramètres connus,
   les retrouve-t-on ? Si non, tout le reste est du bruit ajusté.
2. **Généralisation** — les paramètres ajustés sur les premiers jours
   prédisent-ils les jours suivants **mieux que des paramètres de population** ?
   C'est la question qui décide si la calibration sert à quelque chose.
3. **Utilité** — le modèle calibré bat-il la **persistance** ? Sans cela, il est
   physiologiquement joli et cliniquement inutile.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Volume de distribution du glucose (dL/kg).
GLUCOSE_SPACE_DL_PER_KG = 2.0

#: Bornes des paramètres — larges, mais physiologiquement fermées.
#: Sans bornes, l'ajustement compense une branche par une autre et sort des
#: valeurs ininterprétables : le modèle « marche » et ne veut plus rien dire.
BOUNDS = {
    "gain_ra":  (0.20, 3.00),      # sensibilité à la charge glucidique
    "gain_hgp": (0.30, 2.50),      # production hépatique
    "gain_rd":  (0.30, 2.50),      # captation
    "k":        (0.002, 0.100),    # 1/min — demi-vie de 7 min à 6 h
    "g_base":   (70.0, 220.0),     # glycémie d'équilibre (mg/dL)
}
PARAM_NAMES = list(BOUNDS)

#: Point de départ : le patient « moyen », tous gains à 1.
DEFAULT_THETA = np.array([1.0, 1.0, 1.0, 0.02, 110.0])


@dataclass
class CalibrationResult:
    """Ce qu'on a appris d'un patient, et ce que ça vaut."""

    patient: str
    theta: np.ndarray
    n_days_fit: int
    n_days_test: int
    rmse_fit: float = float("nan")
    #: RMSE sur les journées de test — la seule qui compte
    rmse_test: float = float("nan")
    #: le même modèle avec les paramètres de population, sur les mêmes journées
    rmse_test_population: float = float("nan")
    #: « la glycémie ne bougera pas » sur le même pas de simulation
    rmse_test_persistance: float = float("nan")
    converged: bool = False

    @property
    def gain_vs_population(self) -> float:
        """>0 : calibrer ce patient a servi."""
        return self.rmse_test_population - self.rmse_test

    def as_dict(self) -> dict:
        d = {"patient": self.patient, "n_days_fit": self.n_days_fit,
             "n_days_test": self.n_days_test, "rmse_fit": self.rmse_fit,
             "rmse_test": self.rmse_test,
             "rmse_test_population": self.rmse_test_population,
             "rmse_test_persistance": self.rmse_test_persistance,
             "gain_vs_population": self.gain_vs_population,
             "converged": self.converged}
        d.update({n: float(v) for n, v in zip(PARAM_NAMES, self.theta)})
        return d


# --------------------------------------------------------------------------- #
# Le modèle direct
# --------------------------------------------------------------------------- #

def simulate_glucose(theta, ra, hgp, rd, weight_kg, g0, step_min=5.0):
    """Intègre le modèle à un compartiment sur une journée.

    `ra`, `hgp`, `rd` sont les trois branches de la couche 1, en mg/min ; `g0`
    la glycémie initiale observée. On rend la trajectoire complète.
    """
    gain_ra, gain_hgp, gain_rd, k, g_base = theta
    v_dl = GLUCOSE_SPACE_DL_PER_KG * weight_kg
    n = len(ra)
    g = np.empty(n)
    g[0] = g0
    for i in range(1, n):
        flux = gain_ra * ra[i - 1] + gain_hgp * hgp[i - 1] - gain_rd * rd[i - 1]
        dg = flux / v_dl - k * (g[i - 1] - g_base)
        g[i] = g[i - 1] + dg * step_min
        # garde-fou : au-delà, ce n'est plus de la physiologie
        if g[i] < 20.0:
            g[i] = 20.0
        elif g[i] > 600.0:
            g[i] = 600.0
    return g


def _day_arrays(block, step_min=5):
    """Extrait (ra, hgp, rd, glucose) d'une journée, en mg/min."""
    ra = block["carb_ra_g_min"].to_numpy(float) * 1000.0     # g/min → mg/min
    hgp = block["hepatic_output_mg_min"].to_numpy(float)
    rd = block["glucose_uptake_mg_min"].to_numpy(float)
    g = block["glucose"].to_numpy(float)
    return ra, hgp, rd, g


def _residuals(theta, days, weight_kg, step_min=5):
    """Écart simulation − observation, empilé sur toutes les journées."""
    out = []
    for ra, hgp, rd, g in days:
        sim = simulate_glucose(theta, ra, hgp, rd, weight_kg, g[0], step_min)
        out.append(sim - g)
    return np.concatenate(out)


def _rmse(theta, days, weight_kg, step_min=5) -> float:
    r = _residuals(theta, days, weight_kg, step_min)
    return float(np.sqrt(np.mean(r ** 2)))


def _rmse_persistence(days) -> float:
    """La trajectoire plate depuis la valeur initiale — la baseline du modèle direct.

    Sur une journée entière c'est une baseline exigeante : elle ne dérive pas.
    """
    out = []
    for _, _, _, g in days:
        out.append(np.full(len(g), g[0]) - g)
    r = np.concatenate(out)
    return float(np.sqrt(np.mean(r ** 2)))


# --------------------------------------------------------------------------- #
# L'ajustement
# --------------------------------------------------------------------------- #

def fit_patient(days, weight_kg, *, step_min=5, theta0=None, max_nfev=200):
    """Ajuste les cinq paramètres d'un patient sur les journées fournies.

    Moindres carrés bornés (`scipy.optimize.least_squares`, méthode `trf`).
    Retourne `(theta, rmse, converged)`. Si SciPy est absent, on retombe sur
    une recherche par coordonnées — plus lente, mais le module reste utilisable.
    """
    theta0 = DEFAULT_THETA.copy() if theta0 is None else np.asarray(theta0, float)
    lo = np.array([BOUNDS[n][0] for n in PARAM_NAMES])
    hi = np.array([BOUNDS[n][1] for n in PARAM_NAMES])
    theta0 = np.clip(theta0, lo, hi)

    try:
        from scipy.optimize import least_squares
    except ImportError:                                    # pragma: no cover
        return _fit_coordinate(days, weight_kg, theta0, lo, hi, step_min)

    res = least_squares(
        _residuals, theta0, bounds=(lo, hi), max_nfev=max_nfev,
        args=(days, weight_kg, step_min), xtol=1e-8, ftol=1e-8,
    )
    theta = np.clip(res.x, lo, hi)
    return theta, _rmse(theta, days, weight_kg, step_min), bool(res.success)


def _fit_coordinate(days, weight_kg, theta0, lo, hi, step_min, rounds=4):
    """Repli sans SciPy : descente par coordonnées sur une grille qui se resserre."""
    theta = theta0.copy()
    best = _rmse(theta, days, weight_kg, step_min)
    span = (hi - lo) / 4.0
    for _ in range(rounds):
        for j in range(len(theta)):
            grid = np.clip(np.linspace(theta[j] - span[j], theta[j] + span[j], 9),
                           lo[j], hi[j])
            for v in grid:
                cand = theta.copy()
                cand[j] = v
                r = _rmse(cand, days, weight_kg, step_min)
                if r < best:
                    best, theta = r, cand
        span /= 2.5
    return theta, best, True


# --------------------------------------------------------------------------- #
# Le protocole : calibrer sur le début, tester sur la suite
# --------------------------------------------------------------------------- #

def calibrate_cohort(
    df,
    *,
    n_days_fit: int = 3,
    min_days: int = 5,
    step_min: int = 5,
    theta_population=None,
    verbose: bool = True,
):
    """Calibre chaque patient sur ses premières journées, teste sur les suivantes.

    Le découpage est **temporel et par patient** : aucune journée de test n'a
    servi à l'ajustement, et aucun patient n'emprunte quoi que ce soit à un
    autre — sauf les paramètres de population, qui servent de point de
    comparaison et sont estimés **sans** le patient évalué.
    """
    results = []
    patients = list(dict.fromkeys(df["patient"]))

    for pid in patients:
        sub = df[df["patient"] == pid]
        days = list(dict.fromkeys(sub["day"]))
        if len(days) < min_days:
            continue
        weight = float(sub["weight_kg"].iloc[0])

        fit_days = [_day_arrays(sub[sub["day"] == d], step_min)
                    for d in days[:n_days_fit]]
        test_days = [_day_arrays(sub[sub["day"] == d], step_min)
                     for d in days[n_days_fit:]]
        if not test_days:
            continue

        theta, rmse_fit, ok = fit_patient(fit_days, weight, step_min=step_min)
        r = CalibrationResult(
            patient=str(pid), theta=theta,
            n_days_fit=len(fit_days), n_days_test=len(test_days),
            rmse_fit=rmse_fit,
            rmse_test=_rmse(theta, test_days, weight, step_min),
            rmse_test_persistance=_rmse_persistence(test_days),
            converged=ok,
        )
        results.append((r, test_days, weight))
        if verbose:
            print(f"  {pid}: rmse ajust. {rmse_fit:5.1f} | test {r.rmse_test:5.1f} "
                  f"| theta " + " ".join(f"{v:.3f}" for v in theta), flush=True)

    # Paramètres de population : médiane des autres patients (jamais le patient
    # évalué). C'est la comparaison honnête — « calibrer sert-il, ou un patient
    # moyen suffit-il ? »
    thetas = np.array([r.theta for r, _, _ in results])
    out = []
    for i, (r, test_days, weight) in enumerate(results):
        if theta_population is not None:
            theta_pop = np.asarray(theta_population, float)
        else:
            others = np.delete(thetas, i, axis=0)
            theta_pop = np.median(others, axis=0) if len(others) else DEFAULT_THETA
        r.rmse_test_population = _rmse(theta_pop, test_days, weight, step_min)
        out.append(r)
    return out


def summarize(results) -> dict:
    """Agrège — l'unité reste le patient."""
    if not results:
        return {}
    test = np.array([r.rmse_test for r in results])
    pop = np.array([r.rmse_test_population for r in results])
    pers = np.array([r.rmse_test_persistance for r in results])
    d = pop - test
    n = len(d)
    se = d.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    try:
        from scipy.stats import wilcoxon
        p = float(wilcoxon(test, pop).pvalue)
    except Exception:                                       # pragma: no cover
        p = float("nan")
    return {
        "n_patients": n,
        "rmse_calibre": float(test.mean()),
        "rmse_population": float(pop.mean()),
        "rmse_persistance": float(pers.mean()),
        "gain_vs_population": float(d.mean()),
        "ic95": (float(d.mean() - 1.96 * se), float(d.mean() + 1.96 * se)),
        "p_value": p,
        "patients_ameliores": int((d > 0).sum()),
        "bat_la_persistance": int((test < pers).sum()),
        "theta_median": {n_: float(v) for n_, v in zip(
            PARAM_NAMES, np.median([r.theta for r in results], axis=0))},
    }


def print_summary(s: dict, title: str = "") -> None:
    if not s:
        print("aucun patient calibrable")
        return
    if title:
        print(f"\n{title}")
    print("-" * 70)
    print(f"  Patients calibres             {s['n_patients']}")
    print(f"  RMSE calibre par patient      {s['rmse_calibre']:.2f} mg/dL")
    print(f"  RMSE parametres de population {s['rmse_population']:.2f} mg/dL")
    print(f"  RMSE persistance              {s['rmse_persistance']:.2f} mg/dL")
    lo, hi = s["ic95"]
    print(f"  Gain de la calibration        {s['gain_vs_population']:+.2f} mg/dL "
          f"[IC95 {lo:+.2f}, {hi:+.2f}]")
    print(f"  p (Wilcoxon apparie)          {s['p_value']:.2e}")
    print(f"  Patients ameliores            {s['patients_ameliores']}/{s['n_patients']}")
    print(f"  Modele direct > persistance   {s['bat_la_persistance']}/{s['n_patients']}")
    print("  Parametres medians            " + "  ".join(
        f"{k}={v:.3f}" for k, v in s["theta_median"].items()))
