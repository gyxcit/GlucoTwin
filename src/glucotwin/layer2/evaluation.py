"""
Couche 2 — évaluation honnête.

Trois principes, tenus par construction :

1. **Aucune fuite entre patients.** L'évaluation est en *leave-one-patient-out* :
   chaque patient sert de test à son tour, jamais vu à l'entraînement.
2. **Toujours comparé à la persistance.** « La glycémie dans H minutes sera la
   même que maintenant » est une baseline redoutable à court horizon. Un modèle
   qui ne la bat pas n'apporte rien, quel que soit son RMSE.
3. **Toujours avec une incertitude.** Les intervalles sont obtenus par
   **prédiction conforme**, qui garantit la couverture annoncée sans hypothèse
   sur la distribution des erreurs.

S'y ajoutent des métriques **cliniques** : l'erreur moyenne ne dit rien de la
capacité à détecter une hypoglycémie, qui est ce qui compte pour le patient.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

HYPO_THRESHOLD = 70.0
HYPER_THRESHOLD = 180.0

#: Zones glycémiques pour l'analyse d'erreur ciblée.
ZONES = [
    ("hypoglycemie", -np.inf, 70.0),
    ("bas-normal", 70.0, 100.0),
    ("normal", 100.0, 180.0),
    ("eleve", 180.0, 250.0),
    ("tres eleve", 250.0, np.inf),
]


# --------------------------------------------------------------------------- #
# Métriques
# --------------------------------------------------------------------------- #

def mae(y_true, y_pred) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true, y_pred) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def zone_errors(y_true_abs, y_pred_abs) -> dict:
    """MAE par zone glycémique — là où une erreur n'a pas le même prix."""
    out = {}
    for name, lo, hi in ZONES:
        m = (y_true_abs >= lo) & (y_true_abs < hi)
        out[name] = {
            "n": int(m.sum()),
            "mae": mae(y_true_abs[m], y_pred_abs[m]) if m.any() else float("nan"),
        }
    return out


def event_detection(y_true_abs, y_pred_abs, threshold=HYPO_THRESHOLD, below=True):
    """Sensibilité / précision de détection d'un événement glycémique.

    Une MAE excellente peut coexister avec une détection d'hypoglycémie nulle :
    les événements sont rares, donc invisibles dans une moyenne.
    """
    true_ev = y_true_abs < threshold if below else y_true_abs > threshold
    pred_ev = y_pred_abs < threshold if below else y_pred_abs > threshold
    tp = int((true_ev & pred_ev).sum())
    fp = int((~true_ev & pred_ev).sum())
    fn = int((true_ev & ~pred_ev).sum())
    return {
        "n_events": int(true_ev.sum()),
        "sensibilite": tp / (tp + fn) if (tp + fn) else float("nan"),
        "precision": tp / (tp + fp) if (tp + fp) else float("nan"),
        "tp": tp, "fp": fp, "fn": fn,
    }


# --------------------------------------------------------------------------- #
# Prédiction conforme
# --------------------------------------------------------------------------- #

def conformal_quantile(residuals_cal, alpha: float = 0.1) -> float:
    """Rayon d'intervalle garantissant une couverture ≥ 1-α (conforme fractionné)."""
    n = len(residuals_cal)
    if n == 0:
        return float("nan")
    level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(residuals_cal, level, method="higher"))


def coverage(y_true, lo, hi) -> float:
    return float(np.mean((y_true >= lo) & (y_true <= hi)))


# --------------------------------------------------------------------------- #
# Évaluation leave-one-patient-out
# --------------------------------------------------------------------------- #

@dataclass
class FoldResult:
    patient: str
    n_test: int
    mae_model: float
    mae_persistence: float
    rmse_model: float
    rmse_persistence: float
    interval_width: float = float("nan")
    interval_coverage: float = float("nan")


@dataclass
class LopoReport:
    folds: list[FoldResult] = field(default_factory=list)
    y_true_abs: np.ndarray | None = None
    y_pred_abs: np.ndarray | None = None
    y_pers_abs: np.ndarray | None = None

    # ---- agrégats ----
    @property
    def mae_model(self):
        return np.array([f.mae_model for f in self.folds])

    @property
    def mae_persistence(self):
        return np.array([f.mae_persistence for f in self.folds])

    def summary(self) -> dict:
        d = self.mae_persistence - self.mae_model      # >0 : le modèle gagne
        n = len(d)
        se = d.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
        try:
            from scipy.stats import wilcoxon
            p = float(wilcoxon(self.mae_model, self.mae_persistence).pvalue)
        except Exception:
            p = float("nan")
        return {
            "n_patients": n,
            "mae_model": float(self.mae_model.mean()),
            "mae_persistence": float(self.mae_persistence.mean()),
            "gain_mae": float(d.mean()),
            "ic95_gain": (float(d.mean() - 1.96 * se), float(d.mean() + 1.96 * se)),
            "p_value": p,
            "patients_gagnes": int((d > 0).sum()),
            "couverture": float(np.nanmean([f.interval_coverage for f in self.folds])),
            "largeur_intervalle": float(np.nanmean([f.interval_width for f in self.folds])),
        }

    def clinical(self) -> dict:
        return {
            "zones": zone_errors(self.y_true_abs, self.y_pred_abs),
            "hypo": event_detection(self.y_true_abs, self.y_pred_abs, HYPO_THRESHOLD, True),
            "hyper": event_detection(self.y_true_abs, self.y_pred_abs, HYPER_THRESHOLD, False),
        }


def lopo_evaluate(
    X, y, groups, g_now,
    model_factory,
    *,
    target: str = "delta",
    alpha: float = 0.1,
    calib_frac: float = 0.2,
    max_patients: int | None = None,
    seed: int = 0,
    verbose: bool = False,
) -> LopoReport:
    """Leave-one-patient-out, avec baseline de persistance et intervalles conformes.

    ``model_factory`` est un callable sans argument renvoyant un estimateur
    scikit-learn neuf (``fit`` / ``predict``).
    """
    rng = np.random.default_rng(seed)
    patients = list(dict.fromkeys(groups))
    if max_patients is not None:
        patients = patients[:max_patients]

    report = LopoReport()
    all_true, all_pred, all_pers = [], [], []

    for pi, pid in enumerate(patients):
        test = groups == pid
        train = ~test
        if test.sum() == 0 or train.sum() == 0:
            continue

        # Découpe entraînement / calibration (au niveau patient, sans fuite).
        train_pids = [p for p in dict.fromkeys(groups[train])]
        rng.shuffle(train_pids)
        n_cal = max(1, int(len(train_pids) * calib_frac))
        cal_pids = set(train_pids[:n_cal])
        cal = train & np.isin(groups, list(cal_pids))
        fit = train & ~cal

        model = model_factory()
        model.fit(X[fit], y[fit])

        pred_cal = model.predict(X[cal])
        radius = conformal_quantile(np.abs(y[cal] - pred_cal), alpha=alpha)

        pred = model.predict(X[test])
        y_te, now = y[test], g_now[test]

        # Ramené en niveau absolu pour les métriques cliniques.
        if target == "delta":
            true_abs, pred_abs = now + y_te, now + pred
        else:
            true_abs, pred_abs = y_te, pred
        pers_abs = now

        report.folds.append(FoldResult(
            patient=str(pid),
            n_test=int(test.sum()),
            mae_model=mae(true_abs, pred_abs),
            mae_persistence=mae(true_abs, pers_abs),
            rmse_model=rmse(true_abs, pred_abs),
            rmse_persistence=rmse(true_abs, pers_abs),
            interval_width=2 * radius,
            interval_coverage=coverage(y_te, pred - radius, pred + radius),
        ))
        all_true.append(true_abs); all_pred.append(pred_abs); all_pers.append(pers_abs)

        if verbose and (pi + 1) % 10 == 0:
            print(f"  {pi + 1}/{len(patients)} patients evalues")

    report.y_true_abs = np.concatenate(all_true)
    report.y_pred_abs = np.concatenate(all_pred)
    report.y_pers_abs = np.concatenate(all_pers)
    return report


def print_report(report: LopoReport, title: str = "") -> None:
    """Affiche un rapport lisible — la forme attendue dans un papier."""
    s = report.summary()
    if title:
        print(f"\n{title}")
    print("-" * 66)
    print(f"  Patients (leave-one-out)      {s['n_patients']}")
    print(f"  MAE modele                    {s['mae_model']:.2f} mg/dL")
    print(f"  MAE persistance               {s['mae_persistence']:.2f} mg/dL")
    lo, hi = s["ic95_gain"]
    print(f"  Gain                          {s['gain_mae']:+.2f} mg/dL  "
          f"[IC95 {lo:+.2f}, {hi:+.2f}]")
    print(f"  p (Wilcoxon apparie)          {s['p_value']:.2e}")
    print(f"  Patients ou le modele gagne   {s['patients_gagnes']}/{s['n_patients']}")
    print(f"  Couverture des intervalles    {s['couverture']*100:.1f} %  "
          f"(largeur moyenne {s['largeur_intervalle']:.1f} mg/dL)")

    c = report.clinical()
    print("\n  Erreur par zone glycemique")
    for name, v in c["zones"].items():
        if v["n"]:
            print(f"    {name:<14} n={v['n']:>7}   MAE {v['mae']:.2f} mg/dL")
    h = c["hypo"]
    print(f"\n  Detection hypoglycemie (<70)  {h['n_events']} evenements reels | "
          f"sensibilite {h['sensibilite']*100:.0f} % | precision {h['precision']*100:.0f} %"
          if h["n_events"] else "\n  Detection hypoglycemie : aucun evenement dans ce jeu")
    hy = c["hyper"]
    if hy["n_events"]:
        print(f"  Detection hyperglycemie (>180) {hy['n_events']} evenements | "
              f"sensibilite {hy['sensibilite']*100:.0f} % | precision {hy['precision']*100:.0f} %")
