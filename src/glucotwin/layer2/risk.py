"""
Couche 3 — de la prévision au **risque calibré**.

Le résultat le plus intéressant du projet est une contradiction : quand
l'horizon s'allonge, la MAE s'améliore alors que la détection des
hyperglycémies s'effondre — 44,6 % à 30 min, 1,7 % à 120 min. La cause est
mesurée : le modèle régresse vers la moyenne, ses prédictions s'aplatissent, et
elles franchissent de moins en moins le seuil de 180 mg/dL.

Mais « la prédiction ponctuelle ne dépasse pas 180 » et « le risque de dépasser
180 est faible » sont deux affirmations différentes. Une prédiction à 165 mg/dL
avec 40 mg/dL de dispersion résiduelle porte un risque réel important, que le
seuillage jette à la poubelle. Ce module teste donc l'hypothèse qui sauve
l'utilité clinique du jumeau :

    **une probabilité calibrée conserve-t-elle l'information là où la
    détection par seuil s'effondre ?**

Deux estimateurs, volontairement simples :

- **résiduel** — sans hypothèse de distribution : on lit la probabilité dans la
  distribution empirique des résidus de calibration. C'est le prolongement
  naturel de la prédiction conforme déjà en place.
- **isotonique** — on recalibre ensuite cette probabilité brute sur les
  fréquences réellement observées, patient exclu.

Et une baseline honnête : la **climatologie**, c'est-à-dire le taux de base de
l'événement. Un modèle de risque qui ne bat pas « ça arrive x % du temps »
n'apporte rien.

Toute l'évaluation reste en leave-one-patient-out.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .evaluation import HYPER_THRESHOLD, HYPO_THRESHOLD

# --------------------------------------------------------------------------- #
# Métriques de probabilité
# --------------------------------------------------------------------------- #

def brier_score(y_true_bin, p) -> float:
    """Erreur quadratique moyenne sur les probabilités. Plus bas = mieux."""
    y = np.asarray(y_true_bin, dtype=float)
    p = np.asarray(p, dtype=float)
    return float(np.mean((p - y) ** 2))


def brier_skill_score(y_true_bin, p, p_ref=None) -> float:
    """Gain relatif sur une référence — la climatologie par défaut.

    0 = aussi bon que « ça arrive x % du temps ». Négatif = pire que rien.
    C'est la métrique honnête pour un événement rare, là où le Brier brut
    paraît excellent simplement parce que l'événement est rare.
    """
    y = np.asarray(y_true_bin, dtype=float)
    if p_ref is None:
        p_ref = np.full_like(y, y.mean())
    ref = brier_score(y, p_ref)
    if ref <= 0:
        return float("nan")
    return float(1.0 - brier_score(y, p) / ref)


def reliability_curve(y_true_bin, p, n_bins: int = 10, *, quantile: bool = True):
    """Fréquence observée par tranche de probabilité annoncée.

    Renvoie `(prob_annoncee, freq_observee, effectifs)`. Un modèle calibré suit
    la diagonale : quand il annonce 30 %, l'événement survient 30 % du temps.

    **Le découpage compte.** Pour un événement rare, les probabilités annoncées
    s'entassent près de zéro : avec des tranches de largeur égale, 97 % des
    points tombent dans la première et la calibration paraît parfaite sans
    qu'on ait rien mesuré. Le découpage par **quantiles** (défaut) met le même
    nombre de points dans chaque tranche et regarde vraiment la courbe.
    """
    y = np.asarray(y_true_bin, dtype=float)
    p = np.asarray(p, dtype=float)
    if quantile:
        qs = np.quantile(p, np.linspace(0, 1, n_bins + 1)[1:-1])
        edges_inner = np.unique(qs)
    else:
        edges_inner = np.linspace(0.0, 1.0, n_bins + 1)[1:-1]
    if len(edges_inner) == 0:
        edges_inner = np.array([0.5])
    idx = np.digitize(p, edges_inner)
    n_eff = len(edges_inner) + 1
    mean_p, freq, counts = [], [], []
    for b in range(n_eff):
        m = idx == b
        counts.append(int(m.sum()))
        mean_p.append(float(p[m].mean()) if m.any() else np.nan)
        freq.append(float(y[m].mean()) if m.any() else np.nan)
    return np.array(mean_p), np.array(freq), np.array(counts)


def expected_calibration_error(
    y_true_bin, p, n_bins: int = 10, *, quantile: bool = True
) -> float:
    """Écart moyen entre probabilité annoncée et fréquence observée."""
    mean_p, freq, counts = reliability_curve(y_true_bin, p, n_bins,
                                             quantile=quantile)
    ok = counts > 0
    if not ok.any():
        return float("nan")
    w = counts[ok] / counts[ok].sum()
    return float(np.sum(w * np.abs(mean_p[ok] - freq[ok])))


def auroc(y_true_bin, score) -> float:
    """Aire sous la courbe ROC, par rangs — robuste aux ex aequo.

    Mesure le **classement** : le modèle place-t-il les instants à risque
    au-dessus des autres ? Indépendant de tout seuil, donc insensible à
    l'aplatissement qui tue la détection.
    """
    y = np.asarray(y_true_bin, dtype=bool)
    s = np.asarray(score, dtype=float)
    n_pos, n_neg = int(y.sum()), int((~y).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    ranks[order] = np.arange(1, len(s) + 1)
    # moyenne des rangs pour les ex aequo
    s_sorted = s[order]
    i = 0
    while i < len(s_sorted):
        j = i
        while j + 1 < len(s_sorted) and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return float((ranks[y].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def average_precision(y_true_bin, score) -> float:
    """Aire sous la courbe précision-rappel — la bonne mesure pour du rare."""
    y = np.asarray(y_true_bin, dtype=bool)
    s = np.asarray(score, dtype=float)
    if y.sum() == 0:
        return float("nan")
    order = np.argsort(-s, kind="mergesort")
    y = y[order]
    tp = np.cumsum(y)
    precision = tp / np.arange(1, len(y) + 1)
    return float(np.sum(precision * y) / y.sum())


# --------------------------------------------------------------------------- #
# Estimation de la probabilité
# --------------------------------------------------------------------------- #

def residual_risk(
    pred_abs, residuals_cal, threshold: float, *, above: bool = True
) -> np.ndarray:
    """P(glycémie franchit le seuil), lue dans les résidus de calibration.

    Aucune hypothèse de distribution : si un quart des résidus de calibration
    suffisent à faire passer la prédiction au-dessus du seuil, la probabilité
    annoncée est de 25 %. C'est le prolongement direct de la prédiction
    conforme — mêmes résidus, même absence d'hypothèse.

    Le calcul passe par la **fonction de répartition empirique** des résidus,
    et non par le produit croisé prédictions × résidus. Comme

        P(pred + r > seuil) = P(r > seuil − pred) = 1 − F(seuil − pred),

    une recherche dichotomique dans les résidus triés donne le **même résultat,
    exactement**, en O(n log n) au lieu de O(n×m). Ce n'est pas de la
    micro-optimisation : sur CGMacros, le pli de calibration compte ~20 000
    points, donc le produit croisé allouait une matrice de **3,1 Go** à chaque
    appel, deux fois par pli, 45 plis par horizon. L'expérience en devenait
    impraticable.
    """
    pred = np.asarray(pred_abs, dtype=float)
    res = np.asarray(residuals_cal, dtype=float)
    res = res[np.isfinite(res)]
    if res.size == 0:
        return np.full(pred.shape, np.nan)
    res = np.sort(res)
    seuil_moins_pred = threshold - pred
    if above:
        # P(r > seuil − pred) : résidus strictement au-dessus
        return 1.0 - np.searchsorted(res, seuil_moins_pred, side="right") / res.size
    # P(r < seuil − pred) : résidus strictement en dessous
    return np.searchsorted(res, seuil_moins_pred, side="left") / res.size


class IsotonicCalibrator:
    """Recalibrage monotone : probabilité brute → fréquence observée.

    Volontairement autonome (pas de dépendance à scikit-learn ici) et monotone
    par construction : l'ordre des risques est préservé, seule l'échelle change.
    """

    def __init__(self) -> None:
        self.x_: np.ndarray | None = None
        self.y_: np.ndarray | None = None

    def fit(self, p_raw, y_true_bin) -> IsotonicCalibrator:
        p = np.asarray(p_raw, dtype=float)
        y = np.asarray(y_true_bin, dtype=float)
        ok = np.isfinite(p) & np.isfinite(y)
        p, y = p[ok], y[ok]
        if len(p) < 10 or len(np.unique(y)) < 2:
            self.x_ = self.y_ = None            # pas de quoi calibrer
            return self
        order = np.argsort(p, kind="mergesort")
        self.x_, self.y_ = p[order], _pava(y[order])
        return self

    def predict(self, p_raw) -> np.ndarray:
        p = np.asarray(p_raw, dtype=float)
        if self.x_ is None:
            return p
        return np.clip(np.interp(p, self.x_, self.y_), 0.0, 1.0)


def _pava(y: np.ndarray) -> np.ndarray:
    """Régression isotonique (pool adjacent violators), poids uniformes."""
    y = y.astype(float).copy()
    n = len(y)
    weight = np.ones(n)
    level = y.copy()
    idx = list(range(n))
    i = 0
    while i < len(idx) - 1:
        if level[i] <= level[i + 1] + 1e-12:
            i += 1
            continue
        w = weight[i] + weight[i + 1]
        v = (level[i] * weight[i] + level[i + 1] * weight[i + 1]) / w
        level[i] = v
        weight[i] = w
        level = np.delete(level, i + 1)
        weight = np.delete(weight, i + 1)
        idx.pop(i + 1)
        if i > 0:
            i -= 1
    out = np.empty(n)
    start = 0
    for v, w in zip(level, weight):
        out[start:start + int(w)] = v
        start += int(w)
    return out


# --------------------------------------------------------------------------- #
# Évaluation leave-one-patient-out
# --------------------------------------------------------------------------- #

@dataclass
class RiskReport:
    """Ce que vaut la probabilité annoncée, pour un événement et un horizon.

    Deux AUROC sont rapportées, et l'écart entre les deux est instructif :

    - **par patient, moyennée** — c'est la bonne mesure, et la plus sévère.
      Elle demande : chez *ce* patient, le modèle place-t-il les instants à
      risque au-dessus des autres ? L'unité d'analyse est le patient, comme
      partout ailleurs dans ce dépôt.
    - **poolée** — tous les instants de tous les patients mélangés. Elle est
      en général **plus haute**, et c'est un artefact : les patients qui vivent
      haut font à la fois plus d'hyperglycémies et reçoivent des probabilités
      plus élevées, si bien que le classement inter-patients se fait tout seul.
      Une AUROC poolée flatteuse peut donc coexister avec un modèle incapable
      de distinguer les moments à risque *chez un patient donné* — or c'est
      cela que fait un jumeau, qui sert une personne à la fois.
    """

    event: str
    threshold: float
    n_events: int = 0
    n_total: int = 0
    brier: float = float("nan")
    brier_skill: float = float("nan")
    ece: float = float("nan")
    #: moyenne des AUROC patient par patient — la mesure de référence
    auroc: float = float("nan")
    auroc_ic95: tuple[float, float] = (float("nan"), float("nan"))
    #: AUROC calculée sur tous les instants mélangés
    auroc_poolee: float = float("nan")
    ap: float = float("nan")
    n_patients_evalues: int = 0
    #: sensibilité de la détection par seuil sur la prédiction ponctuelle,
    #: reprise ici pour la comparaison qui fait le sujet du module
    sensibilite_seuil: float = float("nan")
    aurocs_par_patient: np.ndarray = field(default_factory=lambda: np.array([]))
    y_true: np.ndarray = field(default_factory=lambda: np.array([]))
    p: np.ndarray = field(default_factory=lambda: np.array([]))

    @property
    def base_rate(self) -> float:
        return self.n_events / self.n_total if self.n_total else float("nan")

    def summary(self) -> dict:
        return {
            "event": self.event, "seuil": self.threshold,
            "n_events": self.n_events, "taux_de_base": self.base_rate,
            "brier": self.brier, "brier_skill": self.brier_skill,
            "ece": self.ece,
            "auroc_par_patient": self.auroc, "auroc_ic95": self.auroc_ic95,
            "auroc_poolee": self.auroc_poolee,
            "average_precision": self.ap,
            "n_patients_evalues": self.n_patients_evalues,
            "sensibilite_seuil": self.sensibilite_seuil,
        }


def lopo_risk_evaluate(
    X, y, groups, g_now,
    model_factory,
    *,
    target: str = "delta",
    threshold: float = HYPER_THRESHOLD,
    above: bool = True,
    event: str = "hyperglycemie",
    calib_frac: float = 0.2,
    isotonic: bool = True,
    max_patients: int | None = None,
    seed: int = 0,
) -> RiskReport:
    """Probabilité de franchissement, évaluée sans jamais voir le patient testé.

    Le découpage est celui de `lopo_evaluate` : patients d'entraînement,
    patients de calibration, patient de test. Les résidus qui servent à
    fabriquer la probabilité viennent des patients de calibration, jamais du
    patient évalué.
    """
    rng = np.random.default_rng(seed)
    patients = list(dict.fromkeys(groups))
    if max_patients is not None:
        patients = patients[:max_patients]

    all_y, all_p, all_point = [], [], []

    for pid in patients:
        test = groups == pid
        train = ~test
        if test.sum() == 0 or train.sum() == 0:
            continue

        train_pids = list(dict.fromkeys(groups[train]))
        rng.shuffle(train_pids)
        n_cal = max(1, int(len(train_pids) * calib_frac))
        cal_pids = set(train_pids[:n_cal])
        cal = train & np.isin(groups, list(cal_pids))
        fit = train & ~cal

        model = model_factory()
        model.fit(X[fit], y[fit])

        def _abs(pred, mask):
            return g_now[mask] + pred if target == "delta" else pred

        pred_cal = model.predict(X[cal])
        cal_abs = _abs(pred_cal, cal)
        true_cal_abs = _abs(y[cal], cal)
        residuals = true_cal_abs - cal_abs

        pred_te = model.predict(X[test])
        te_abs = _abs(pred_te, test)
        true_te_abs = _abs(y[test], test)

        p = residual_risk(te_abs, residuals, threshold, above=above)

        if isotonic:
            p_cal = residual_risk(cal_abs, residuals, threshold, above=above)
            y_cal = (true_cal_abs > threshold) if above else (true_cal_abs < threshold)
            p = IsotonicCalibrator().fit(p_cal, y_cal).predict(p)

        all_y.append((true_te_abs > threshold) if above else (true_te_abs < threshold))
        all_p.append(p)
        all_point.append((te_abs > threshold) if above else (te_abs < threshold))

    # AUROC patient par patient : un patient sans evenement (ou avec que des
    # evenements) ne peut pas etre classe, il sort de la moyenne.
    per_patient = np.array([
        auroc(yy, pp) for yy, pp in zip(all_y, all_p)
        if 0 < int(np.sum(yy)) < len(yy)
    ])
    per_patient = per_patient[np.isfinite(per_patient)]
    if len(per_patient):
        se = (per_patient.std(ddof=1) / np.sqrt(len(per_patient))
              if len(per_patient) > 1 else float("nan"))
        auroc_mean = float(per_patient.mean())
        ic = (auroc_mean - 1.96 * se, auroc_mean + 1.96 * se)
    else:
        auroc_mean, ic = float("nan"), (float("nan"), float("nan"))

    y_true = np.concatenate(all_y)
    p = np.concatenate(all_p)
    point = np.concatenate(all_point)

    tp = int((y_true & point).sum())
    fn = int((y_true & ~point).sum())

    return RiskReport(
        event=event, threshold=threshold,
        n_events=int(y_true.sum()), n_total=int(len(y_true)),
        brier=brier_score(y_true, p),
        brier_skill=brier_skill_score(y_true, p),
        ece=expected_calibration_error(y_true, p),
        auroc=auroc_mean, auroc_ic95=ic,
        auroc_poolee=auroc(y_true, p),
        ap=average_precision(y_true, p),
        n_patients_evalues=int(len(per_patient)),
        sensibilite_seuil=(tp / (tp + fn)) if (tp + fn) else float("nan"),
        aurocs_par_patient=per_patient, y_true=y_true, p=p,
    )


def print_risk_report(r: RiskReport, title: str = "") -> None:
    """Affiche le rapport de risque, avec la comparaison qui fait le sujet."""
    if title:
        print(f"\n{title}")
    print("-" * 70)
    print(f"  Evenement                     {r.event} (seuil {r.threshold:.0f} mg/dL)")
    print(f"  Taux de base                  {r.base_rate * 100:.1f} % "
          f"({r.n_events} sur {r.n_total})")
    print(f"  Brier                         {r.brier:.4f}")
    print(f"  Gain sur la climatologie      {r.brier_skill:+.3f}"
          f"   {'(pire que rien)' if r.brier_skill < 0 else ''}")
    print(f"  Erreur de calibration         {r.ece:.3f}")
    lo, hi = r.auroc_ic95
    print(f"  AUROC par patient             {r.auroc:.3f}  "
          f"[IC95 {lo:.3f}, {hi:.3f}]  sur {r.n_patients_evalues} patients")
    ecart = r.auroc_poolee - r.auroc
    print(f"  AUROC poolee                  {r.auroc_poolee:.3f}  "
          f"({ecart:+.3f} vs par patient — melange les patients)")
    print(f"  Average precision             {r.ap:.3f}  "
          f"(hasard = {r.base_rate:.3f})")
    print("  --- la question du module ---")
    print(f"  Detection par seuil           {r.sensibilite_seuil * 100:.1f} % "
          "de sensibilite")
    verdict = ("le classement reste informatif" if r.auroc > 0.7
               else "le classement s'affaiblit aussi" if r.auroc > 0.6
               else "plus d'information exploitable")
    print(f"  Probabilite calibree          AUROC {r.auroc:.3f} -> {verdict}")


def print_reliability(r: RiskReport, n_bins: int = 10) -> None:
    """Courbe de fiabilité en texte — lisible dans un terminal ou un rapport."""
    mean_p, freq, counts = reliability_curve(r.y_true, r.p, n_bins)
    print(f"\n  Fiabilite — {r.event}")
    print(f"    {'annonce':>9} {'observe':>9} {'n':>9}")
    for mp, f, c in zip(mean_p, freq, counts):
        if c == 0:
            continue
        flag = "  <-- surestime" if (f == f and mp - f > 0.15) else (
            "  <-- sous-estime" if (f == f and f - mp > 0.15) else "")
        print(f"    {mp * 100:>8.1f}% {f * 100:>8.1f}% {c:>9,}{flag}")


#: Les deux événements qui comptent, dans l'ordre de gravité clinique.
EVENTS = [
    ("hypoglycemie", HYPO_THRESHOLD, False),
    ("hyperglycemie", HYPER_THRESHOLD, True),
]
