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


# --------------------------------------------------------------------------- #
# Le modèle RÉDUIT — quatre paramètres, tous identifiables
# --------------------------------------------------------------------------- #
#
# Le modèle à cinq paramètres a un défaut mesuré : sur CGMacros, **61 % des
# patients** ont un gain collé à une borne, et seuls 5 sur 44 n'en ont aucun de
# saturé. La cause est structurelle, pas numérique — production hépatique,
# captation basale et glycémie d'équilibre agissent **toutes trois sur le même
# niveau**, et une seule chose est observable : leur résultante. À l'équilibre,
#
#     0 = (g_h·HGP − g_u·Rd_basal)/V − k·(G − G_b)
#
# n'a qu'une inconnue effective. Trois paramètres pour un degré de liberté :
# l'ajustement les fait glisser jusqu'aux murs sans que la trajectoire change.
#
# La correction n'est pas de mieux optimiser, c'est de **reparamétrer**. On
# absorbe le bilan basal dans la glycémie d'équilibre — qui est justement ce
# qu'il détermine — et il ne reste que des grandeurs à signature distincte :
#
#     dG/dt = [ gᵣ·Ra − g_e·Exercice ] / V − k·(G − G_b)
#
# - `G_b` — le plateau entre les repas, la nuit
# - `k`   — la vitesse de redescente après un repas
# - `gᵣ`  — l'amplitude des excursions post-prandiales
# - `g_e` — le creux pendant l'effort
#
# Chacun se lit sur une portion différente de la courbe : aucun ne peut
# compenser un autre. Et `G_b` devient une quantité **mesurable par ailleurs**
# — la glycémie à jeun — donc falsifiable contre le laboratoire.

REDUCED_BOUNDS = {
    "gain_ra": (0.20, 3.00),      # amplitude des excursions post-prandiales
    "gain_ex": (0.00, 3.00),      # profondeur du creux a l'effort
    "k":       (0.002, 0.100),    # vitesse de retour a l'equilibre
    "g_base":  (60.0, 260.0),     # glycemie d'equilibre = glycemie a jeun
}
REDUCED_PARAM_NAMES = list(REDUCED_BOUNDS)
REDUCED_DEFAULT = np.array([1.0, 1.0, 0.02, 110.0])


def exercise_uptake_from_concepts(uptake_mg_min, dawn_factor, weight_kg):
    """Sépare la captation à l'effort de la captation basale.

    La couche 1 les additionne dans un seul concept ; ici on refait la
    soustraction exacte, avec la même constante et la même correction de l'aube
    que `day_concepts`. Ce n'est pas une approximation : c'est l'inverse de
    l'addition qui les a réunies.
    """
    from .day_concepts import DAWN_DISPOSAL_DROP, HEPATIC_BASAL_MG_KG_MIN

    uptake = np.asarray(uptake_mg_min, dtype=float)
    dawn = np.asarray(dawn_factor, dtype=float)
    basal = HEPATIC_BASAL_MG_KG_MIN * weight_kg * (1.0 - DAWN_DISPOSAL_DROP * dawn)
    return np.maximum(0.0, uptake - basal)


def simulate_glucose_reduced(theta, ra, exercise, weight_kg, g0, step_min=5.0):
    """Le modèle réduit : quatre paramètres, un compartiment."""
    gain_ra, gain_ex, k, g_base = theta
    v_dl = GLUCOSE_SPACE_DL_PER_KG * weight_kg
    n = len(ra)
    g = np.empty(n)
    g[0] = g0
    for i in range(1, n):
        flux = gain_ra * ra[i - 1] - gain_ex * exercise[i - 1]
        dg = flux / v_dl - k * (g[i - 1] - g_base)
        g[i] = g[i - 1] + dg * step_min
        if g[i] < 20.0:
            g[i] = 20.0
        elif g[i] > 600.0:
            g[i] = 600.0
    return g


def _day_arrays_reduced(block, weight_kg, step_min=5):
    ra = block["carb_ra_g_min"].to_numpy(float) * 1000.0
    ex = exercise_uptake_from_concepts(
        block["glucose_uptake_mg_min"].to_numpy(float),
        block["dawn_factor"].to_numpy(float) if "dawn_factor" in block
        else np.zeros(len(block)),
        weight_kg)
    g = block["glucose"].to_numpy(float)
    return ra, ex, g


def _residuals_reduced(theta, days, weight_kg, step_min=5):
    out = []
    for ra, ex, g in days:
        out.append(simulate_glucose_reduced(theta, ra, ex, weight_kg, g[0], step_min) - g)
    return np.concatenate(out)


def _rmse_reduced(theta, days, weight_kg, step_min=5) -> float:
    return float(np.sqrt(np.mean(_residuals_reduced(theta, days, weight_kg, step_min) ** 2)))


def fit_patient_reduced(days, weight_kg, *, step_min=5, theta0=None, max_nfev=200):
    """Ajuste les quatre paramètres du modèle réduit."""
    theta0 = REDUCED_DEFAULT.copy() if theta0 is None else np.asarray(theta0, float)
    lo = np.array([REDUCED_BOUNDS[n][0] for n in REDUCED_PARAM_NAMES])
    hi = np.array([REDUCED_BOUNDS[n][1] for n in REDUCED_PARAM_NAMES])
    theta0 = np.clip(theta0, lo, hi)
    from scipy.optimize import least_squares
    res = least_squares(_residuals_reduced, theta0, bounds=(lo, hi),
                        max_nfev=max_nfev, args=(days, weight_kg, step_min),
                        xtol=1e-8, ftol=1e-8)
    theta = np.clip(res.x, lo, hi)
    return theta, _rmse_reduced(theta, days, weight_kg, step_min), bool(res.success)


def saturation_rate(thetas, bounds, names, tol=1e-6) -> dict:
    """Part des patients dont chaque paramètre bute sur une borne.

    C'est le diagnostic d'identifiabilité le plus direct : un paramètre qui
    sature est un paramètre que les données ne contraignent pas.
    """
    th = np.atleast_2d(np.asarray(thetas, dtype=float))
    out = {}
    for j, n in enumerate(names):
        lo, hi = bounds[n]
        v = th[:, j]
        out[n] = float(((np.abs(v - lo) < tol) | (np.abs(v - hi) < tol)).mean())
    aucun = np.ones(len(th), dtype=bool)
    for j, n in enumerate(names):
        lo, hi = bounds[n]
        aucun &= ~((np.abs(th[:, j] - lo) < tol) | (np.abs(th[:, j] - hi) < tol))
    out["_aucun_sature"] = float(aucun.mean())
    return out


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
        noms = REDUCED_PARAM_NAMES if len(self.theta) == 4 else PARAM_NAMES
        d.update({n: float(v) for n, v in zip(noms, self.theta)})
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
    model: str = "full",
    verbose: bool = True,
):
    """Calibre chaque patient sur ses premières journées, teste sur les suivantes.

    `model="full"` : cinq paramètres, trois gains de branche (la version
    d'origine). `model="reduced"` : quatre paramètres, bilan basal absorbé dans
    la glycémie d'équilibre — voir le commentaire en tête de section.

    Le découpage est **temporel et par patient** : aucune journée de test n'a
    servi à l'ajustement, et aucun patient n'emprunte quoi que ce soit à un
    autre — sauf les paramètres de population, qui servent de point de
    comparaison et sont estimés **sans** le patient évalué.
    """
    reduced = model == "reduced"
    names = REDUCED_PARAM_NAMES if reduced else PARAM_NAMES
    default = REDUCED_DEFAULT if reduced else DEFAULT_THETA

    results = []
    patients = list(dict.fromkeys(df["patient"]))

    for pid in patients:
        sub = df[df["patient"] == pid]
        days = list(dict.fromkeys(sub["day"]))
        if len(days) < min_days:
            continue
        weight = float(sub["weight_kg"].iloc[0])

        def _arrays(d):
            block = sub[sub["day"] == d]
            return (_day_arrays_reduced(block, weight, step_min) if reduced
                    else _day_arrays(block, step_min))

        fit_days = [_arrays(d) for d in days[:n_days_fit]]
        test_days = [_arrays(d) for d in days[n_days_fit:]]
        if not test_days:
            continue

        if reduced:
            theta, rmse_fit, ok = fit_patient_reduced(fit_days, weight, step_min=step_min)
            rmse_test = _rmse_reduced(theta, test_days, weight, step_min)
        else:
            theta, rmse_fit, ok = fit_patient(fit_days, weight, step_min=step_min)
            rmse_test = _rmse(theta, test_days, weight, step_min)

        pers = float(np.sqrt(np.mean(np.concatenate(
            [np.full(len(d[-1]), d[-1][0]) - d[-1] for d in test_days]) ** 2)))

        r = CalibrationResult(
            patient=str(pid), theta=theta,
            n_days_fit=len(fit_days), n_days_test=len(test_days),
            rmse_fit=rmse_fit, rmse_test=rmse_test,
            rmse_test_persistance=pers, converged=ok,
        )
        results.append((r, test_days, weight))
        if verbose:
            print(f"  {pid}: rmse ajust. {rmse_fit:5.1f} | test {rmse_test:5.1f} "
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
            theta_pop = np.median(others, axis=0) if len(others) else default
        r.rmse_test_population = (_rmse_reduced(theta_pop, test_days, weight, step_min)
                                  if reduced
                                  else _rmse(theta_pop, test_days, weight, step_min))
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
            (REDUCED_PARAM_NAMES if len(results[0].theta) == 4 else PARAM_NAMES),
            np.median([r.theta for r in results], axis=0))},
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


# --------------------------------------------------------------------------- #
# Injecter les paramètres ajustés dans les concepts
# --------------------------------------------------------------------------- #

def apply_calibration(df, thetas: dict, *, days_from: int | None = None):
    """Réécrit la table de concepts avec les gains propres à chaque patient.

    Les trois gains multiplient les trois branches de la couche 1, et le flux
    net est recalculé en conséquence. Un patient sans θ garde ses concepts
    d'origine — on ne lui invente pas des paramètres.

    **Sur la fuite d'information.** Les θ sont ajustés sur la glycémie du
    patient : les concepts calibrés en portent donc la trace. Le seul protocole
    honnête est celui du déploiement réel — le jumeau **observe la personne
    pendant K jours**, puis la sert. `days_from` coupe les journées
    d'observation, pour que l'évaluation ne porte que sur des journées
    postérieures à la calibration.
    """
    out = df.copy()
    ra = out["carb_ra_g_min"].to_numpy(float).copy()
    hgp = out["hepatic_output_mg_min"].to_numpy(float).copy()
    rd = out["glucose_uptake_mg_min"].to_numpy(float).copy()
    pat = out["patient"].to_numpy()

    for pid, theta in thetas.items():
        m = pat == pid
        if not m.any():
            continue
        g_ra, g_hgp, g_rd = float(theta[0]), float(theta[1]), float(theta[2])
        ra[m] *= g_ra
        hgp[m] *= g_hgp
        rd[m] *= g_rd

    out["carb_ra_g_min"] = ra
    out["hepatic_output_mg_min"] = hgp
    out["glucose_uptake_mg_min"] = rd
    out["net_glucose_flux_mg_min"] = ra * 1000.0 + hgp - rd

    if days_from is not None:
        out = out[out["day"] >= days_from].copy()
    return out
