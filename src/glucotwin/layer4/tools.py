"""
Les outils de l'agent — le jumeau devient interrogeable.

Sans outils, un LLM reçoit un résumé pré-digéré et n'a plus qu'à le reformuler ;
l'effet annoncé de chaque intervention est alors une **moyenne de population**
écrite dans le catalogue. Avec outils, l'agent peut **simuler l'intervention sur
le jumeau calibré de ce patient** et lire l'effet réel. C'est la différence
entre « la marche fait baisser le pic d'environ 16 mg/dL » et « chez vous, elle
le fait baisser de 9 ».

Trois principes tenus par construction :

1. **Tous les outils sont en lecture seule.** Aucun n'écrit, n'appelle le
   réseau, ni ne modifie l'état. Le pire qu'un agent en boucle puisse faire est
   de perdre du temps.
2. **Les arguments sont validés avant exécution.** Un identifiant hors
   catalogue, un horizon absurde ou un argument manquant renvoie une erreur
   *à l'agent*, sans lever d'exception ni sortir du registre.
3. **Un outil refuse une intervention contre-indiquée**, même si l'agent
   insiste. La contre-indication n'est pas un conseil qu'on donne au modèle,
   c'est une porte fermée.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .catalogue import CATALOGUE, CATALOGUE_PAR_ID, interventions_possibles


@dataclass
class JumeauContext:
    """Tout ce dont les outils ont besoin — et rien de mutable.

    `theta` sont les paramètres **calibrés** du patient (modèle réduit :
    gain_ra, gain_ex, k, g_base). C'est ce qui rend la simulation personnelle
    plutôt que générique.
    """

    ra_mg_min: np.ndarray            # apparition du glucose alimentaire
    exercice_mg_min: np.ndarray      # captation a l'effort, part au-dessus du repos
    weight_kg: float
    theta: np.ndarray
    g0: float = 110.0
    step_min: float = 5.0
    etat: dict = field(default_factory=dict)
    #: emploi du temps, quand on l'a. **Change la façon de simuler une
    #: intervention** : avec lui, « index glycémique bas » modifie le paramètre
    #: `gi` du repas et repasse par la couche 1 — la voie physiologique, la même
    #: que l'étalonnage du catalogue. Sans lui (patient CGMacros, dont on n'a que
    #: les METs mesurés et les repas déclarés), on retombe sur une transformation
    #: directe de la série d'apparition, plus grossière et signalée comme telle.
    schedule: object | None = None

    @property
    def heures(self) -> np.ndarray:
        return np.arange(len(self.ra_mg_min)) * self.step_min / 60.0

    def simuler(self, ra=None, ex=None) -> np.ndarray:
        from ..calibration import simulate_glucose_reduced
        return simulate_glucose_reduced(
            self.theta,
            self.ra_mg_min if ra is None else ra,
            self.exercice_mg_min if ex is None else ex,
            self.weight_kg, self.g0, self.step_min)


def contexte_depuis_planning(jour, theta, *, g0: float | None = None,
                             step_min: int = 5,
                             etat: dict | None = None) -> JumeauContext:
    """Le contexte le plus riche : l'agent peut simuler par la voie physiologique."""
    from .etalonnage import series_du_planning

    theta = np.asarray(theta, dtype=float)
    ra, ex = series_du_planning(jour, step_min=step_min)
    return JumeauContext(ra_mg_min=ra, exercice_mg_min=ex,
                         weight_kg=float(jour.weight_kg), theta=theta,
                         g0=float(theta[3] if g0 is None else g0),
                         step_min=float(step_min), etat=dict(etat or {}),
                         schedule=jour)


def contexte_depuis_concepts(frames, weight_kg: float, theta, *,
                             g0: float = 110.0, step_min: float = 5.0,
                             etat: dict | None = None) -> JumeauContext:
    """Construit le contexte à partir des `ConceptFrame` de la couche 1.

    La séparation effort/basal passe par `exercise_uptake_from_concepts`, la
    **même fonction** que la calibration : θ a été ajusté sur ces entrées-là, il
    doit être appliqué aux mêmes.
    """
    from ..calibration import exercise_uptake_from_concepts

    ra = np.array([f.carb_ra_g_min for f in frames], dtype=float) * 1000.0
    ex = exercise_uptake_from_concepts(
        np.array([f.glucose_uptake_mg_min for f in frames], dtype=float),
        np.array([f.dawn_factor for f in frames], dtype=float),
        weight_kg)
    return JumeauContext(ra_mg_min=ra, exercice_mg_min=ex, weight_kg=float(weight_kg),
                         theta=np.asarray(theta, dtype=float), g0=float(g0),
                         step_min=float(step_min), etat=dict(etat or {}))


def contexte_depuis_bloc(block, weight_kg: float, theta, *,
                         step_min: float = 5.0, etat: dict | None = None,
                         g0: float | None = None) -> JumeauContext:
    """Construit le contexte à partir d'une journée de concepts (couche 1).

    On **réutilise** `_day_arrays_reduced` de la calibration plutôt que de
    refaire la séparation effort/basal : si les deux chemins divergeaient un
    jour, l'agent simulerait autre chose que ce sur quoi θ a été ajusté.
    """
    from ..calibration import _day_arrays_reduced

    ra, ex, g = _day_arrays_reduced(block, weight_kg, step_min)
    return JumeauContext(ra_mg_min=ra, exercice_mg_min=ex, weight_kg=float(weight_kg),
                         theta=np.asarray(theta, dtype=float),
                         g0=float(g[0] if g0 is None else g0),
                         step_min=float(step_min), etat=dict(etat or {}))


# --------------------------------------------------------------------------- #
# Comment chaque intervention modifie la journée simulée
# --------------------------------------------------------------------------- #

def _etaler(ra, facteur=2.0):
    """Étale l'apparition du glucose sans en changer la quantité totale.

    C'est ce que fait un index glycémique bas ou l'ajout de fibres : la même
    charge glucidique, absorbée plus lentement. La masse est conservée à la
    précision numérique près — un étalement qui perdrait des glucides ferait
    baisser le pic pour la mauvaise raison.
    """
    ra = np.asarray(ra, dtype=float)
    n = max(3, int(round(facteur * 6)) | 1)          # noyau impair
    noyau = np.ones(n) / n
    etale = np.convolve(ra, noyau, mode="same")
    total, total_e = ra.sum(), etale.sum()
    return etale * (total / total_e) if total_e > 0 else etale


def _ajouter_effort(ex, heures, debut_h, duree_h, intensite_mg_min):
    ex = np.asarray(ex, dtype=float).copy()
    m = (heures >= debut_h) & (heures < debut_h + duree_h)
    ex[m] += intensite_mg_min
    return ex


def _decaler(ra, heures, depuis_h, delta_h, step_min):
    """Avance dans le temps tout ce qui apparaît après `depuis_h`."""
    ra = np.asarray(ra, dtype=float)
    pas = int(round(delta_h * 60.0 / step_min))
    out = ra.copy()
    m = heures >= depuis_h
    out[m] = 0.0
    idx = np.where(m)[0]
    for i in idx:
        j = i - pas
        if 0 <= j < len(out):
            out[j] += ra[i]
    return out


def appliquer(inter_id: str, ctx: JumeauContext):
    """Renvoie `(ra, exercice)` modifiés par l'intervention.

    Si le contexte porte un emploi du temps, on passe par la **voie
    physiologique** : on modifie le planning, on recalcule les concepts, et on
    obtient exactement ce que mesure `scripts/etalonner_catalogue.py`. La seule
    différence avec la colonne « population » de ce script est alors θ.
    """
    if ctx.schedule is not None:
        from .etalonnage import appliquer_au_planning, series_du_planning
        return series_du_planning(appliquer_au_planning(inter_id, ctx.schedule),
                                  step_min=int(ctx.step_min))

    ra, ex, h = ctx.ra_mg_min.copy(), ctx.exercice_mg_min.copy(), ctx.heures
    poids = ctx.weight_kg

    if inter_id == "REDUIRE_GLUCIDES":
        ra = ra * 0.67
    elif inter_id == "INDEX_GLYCEMIQUE_BAS":
        ra = _etaler(ra, 2.5)
    elif inter_id == "FIBRES":
        ra = _etaler(ra, 1.6)
    elif inter_id == "MARCHE_POST_REPAS":
        for pic in _heures_de_repas(ra, h):
            ex = _ajouter_effort(ex, h, pic + 0.5, 0.5, 3.0 * poids)
    elif inter_id == "VELO_MODERE":
        ex = _ajouter_effort(ex, h, 18.0, 0.75, 6.5 * poids)
    elif inter_id == "AVANCER_DINER":
        ra = _decaler(ra, h, 18.5, 2.5, ctx.step_min)
    elif inter_id == "FRACTIONNER_REPAS":
        ra = _etaler(ra, 3.5)
    return ra, ex


def _heures_de_repas(ra, heures, seuil_ratio=0.25):
    """Repère les débuts de repas dans la série d'apparition."""
    ra = np.asarray(ra, dtype=float)
    if ra.max() <= 0:
        return []
    seuil = ra.max() * seuil_ratio
    dessus = ra > seuil
    debuts = np.where(dessus & ~np.r_[False, dessus[:-1]])[0]
    return [float(heures[i]) for i in debuts]


# --------------------------------------------------------------------------- #
# Le registre — la seule chose que l'agent peut appeler
# --------------------------------------------------------------------------- #

def _metriques(g: np.ndarray) -> dict:
    return {"pic": round(float(g.max()), 1),
            "moyenne": round(float(g.mean()), 1),
            "temps_dans_la_cible_pct": round(float(((g >= 70) & (g <= 180)).mean() * 100), 1),
            "minutes_au_dessus_180": int(((g > 180).sum()) * 5)}


def outil_profil(ctx: JumeauContext, **_) -> dict:
    """Le patient et ses paramètres calibrés."""
    noms = ["gain_ra", "gain_ex", "k", "g_base"]
    return {"poids_kg": round(ctx.weight_kg, 1),
            "parametres_calibres": {n: round(float(v), 3)
                                    for n, v in zip(noms, ctx.theta)},
            "glycemie_equilibre_estimee": round(float(ctx.theta[3]), 1)}


def outil_journee(ctx: JumeauContext, **_) -> dict:
    """La journée simulée telle quelle, sans intervention."""
    g = ctx.simuler()
    return {"reference": _metriques(g),
            "heures_de_repas": [round(x, 2) for x in
                                _heures_de_repas(ctx.ra_mg_min, ctx.heures)]}


def outil_etat(ctx: JumeauContext, **_) -> dict:
    """L'état métabolique courant, celui qui décide des contre-indications."""
    e = dict(ctx.etat)
    e.setdefault("glucose", float(ctx.simuler()[0]))
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in e.items()}


def outil_catalogue(ctx: JumeauContext, **_) -> dict:
    """Ce qui est autorisé dans l'état courant — et ce qui ne l'est pas, avec le motif."""
    ok, ko = interventions_possibles(ctx.etat)
    return {"autorisees": [{"id": i.id, "titre": i.titre,
                            "effet_population_mg_dl": i.effet_pic} for i in ok],
            "interdites": [{"id": i, "motif": m} for i, m in ko]}


def outil_simuler(ctx: JumeauContext, id: str = "", **_) -> dict:
    """**L'outil qui justifie l'agent** : l'effet réel de l'intervention sur CE patient.

    L'écart entre `effet_mesure_mg_dl` et l'effet du catalogue est l'information
    que le LLM seul n'aurait jamais eue.
    """
    if not isinstance(id, str) or id not in CATALOGUE_PAR_ID:
        return {"erreur": f"identifiant inconnu : {id!r}",
                "identifiants_valides": sorted(CATALOGUE_PAR_ID)}
    inter = CATALOGUE_PAR_ID[id]
    applicable, motif = inter.applicable(ctx.etat)
    if not applicable:
        return {"erreur": f"intervention contre-indiquee : {motif}",
                "id": id, "simulation_refusee": True}

    ref = ctx.simuler()
    ra, ex = appliquer(id, ctx)
    apres = ctx.simuler(ra=ra, ex=ex)
    m_ref, m_ap = _metriques(ref), _metriques(apres)
    return {"id": id,
            "avant": m_ref, "apres": m_ap,
            # les ecarts sont calcules sur les series brutes, pas sur les
            # metriques deja arrondies : sinon l'agent et le script
            # d'etalonnage afficheraient des valeurs differentes de 0,1
            # pour un simple effet d'arrondi, et le test de coherence
            # deviendrait un test de tolerance.
            # comparable a `effet_pic` du catalogue : le pic de la JOURNEE
            "effet_mesure_mg_dl": round(float(apres.max() - ref.max()), 1),
            # une intervention qui deplace un repas hors du pic ne change pas le
            # pic du jour : sans la moyenne, elle paraitrait sans effet
            "effet_moyenne_mg_dl": round(float(apres.mean() - ref.mean()), 1),
            "effet_population_mg_dl": inter.effet_pic,
            "voie": "planning" if ctx.schedule is not None else "series",
            "gain_temps_dans_cible_pts": round(
                m_ap["temps_dans_la_cible_pct"] - m_ref["temps_dans_la_cible_pct"], 1)}


#: Le registre fermé. Un nom hors de ce dictionnaire n'est pas appelable.
OUTILS = {
    "profil_patient": (outil_profil, "Poids et parametres physiologiques calibres."),
    "journee_simulee": (outil_journee, "Metriques de la journee sans intervention."),
    "etat_courant": (outil_etat, "Glycemie, tendance, risque d'hypoglycemie."),
    "catalogue": (outil_catalogue, "Interventions autorisees et interdites, avec motif."),
    "simuler_intervention": (
        outil_simuler,
        "Simule une intervention sur le jumeau CALIBRE du patient et rend son "
        "effet reel. Argument : id (identifiant du catalogue)."),
}


def decrire_outils() -> str:
    """La description injectée dans le prompt — générée, jamais recopiée à la main."""
    return "\n".join(f"- {nom} : {desc}" for nom, (_, desc) in OUTILS.items())


def executer(nom: str, args: dict, ctx: JumeauContext) -> dict:
    """Exécute un outil du registre. **Ne lève jamais** : renvoie l'erreur à l'agent."""
    if nom not in OUTILS:
        return {"erreur": f"outil inconnu : {nom!r}", "outils": sorted(OUTILS)}
    if not isinstance(args, dict):
        return {"erreur": "arguments illisibles"}
    fonction = OUTILS[nom][0]
    try:
        return fonction(ctx, **{k: v for k, v in args.items() if isinstance(k, str)})
    except TypeError as e:
        return {"erreur": f"arguments invalides : {e}"}
    except Exception as e:                                      # noqa: BLE001
        return {"erreur": f"echec de l'outil : {type(e).__name__}"}
