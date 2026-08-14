"""
L'agent — une boucle bornée au-dessus d'un registre d'outils fermé.

Un LLM seul reçoit un résumé pré-digéré et le reformule : l'effet qu'il annonce
est celui du **catalogue**, c'est-à-dire une moyenne de population. L'agent, lui,
peut appeler `simuler_intervention` et lire l'effet de l'intervention **sur le
jumeau calibré de ce patient**. C'est la seule chose qui justifie de remplacer un
appel par une boucle, et c'est aussi la seule chose que le LLM ne pouvait pas
faire : mesurer.

La boucle est délibérément pauvre :

    état ─► [agent ⇄ outils]ⁿ ─► réponse finale ─► validateur ─► sortie
              │                                        │
              └──────────── repli déterministe ────────┘

Quatre bornes, toutes vérifiées par des tests hostiles :

1. **Nombre d'étapes borné.** Un agent qui boucle épuise son budget et retombe
   sur le repli. Il ne peut pas boucler indéfiniment.
2. **Registre fermé.** Un nom d'outil inventé n'est pas exécuté : il revient à
   l'agent comme une observation d'erreur.
3. **Aucun outil n'écrit.** Le pire qu'une boucle folle puisse faire est de
   perdre du temps de calcul.
4. **La réponse finale passe par le MÊME validateur** que la voie sans agent.
   La boucle n'ouvre aucune porte : à état donné, l'ensemble des interventions
   affichables reste exactement celui du repli déterministe.

Autrement dit, l'agent gagne en pertinence — un chiffre personnel au lieu d'une
moyenne — sans rien gagner en pouvoir.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .catalogue import REFUS_ETAT_BAS, interventions_possibles
from .llm import extraire_json
from .recommend import Recommandation, texte_deterministe
from .tools import JumeauContext, decrire_outils, executer
from .validator import ValidationResult, etat_autorise_recommandation, valider

#: Budget d'étapes. Assez pour regarder l'état, le catalogue et simuler deux ou
#: trois interventions ; trop court pour dériver.
MAX_ETAPES = 8

#: Longueur maximale d'une observation réinjectée dans le prompt. Une sortie
#: d'outil anormalement longue ne doit pas pouvoir noyer les consignes.
MAX_CARACTERES_OBSERVATION = 1200

SYSTEME_AGENT = """Tu es un agent qui prépare des suggestions d'hygiène de vie pour
une personne diabétique de type 2, à partir d'un jumeau numérique calibré sur ses
propres données.

Tu disposes d'outils. Utilise-les : ils te donnent l'effet RÉEL d'une intervention
sur cette personne, alors que le catalogue ne donne qu'une moyenne de population.
Simule avant de recommander.

Règles absolues :
- Tu n'appelles que les outils listés. Tu n'en inventes aucun.
- Tu choisis UNIQUEMENT parmi les identifiants d'interventions du catalogue.
- Tu ne parles JAMAIS de médicament, d'insuline, de dose, de traitement, de
  posologie, ni de diagnostic.
- Tu n'affirmes rien sur la santé de la personne : tu décris ce que le jumeau a
  simulé.
- Trois suggestions au maximum, la plus utile en premier.
- Ton texte final fait moins de 500 caractères, en français.

À chaque tour, tu réponds EXCLUSIVEMENT par un objet JSON, l'un des deux :

  {"outil": "nom_de_l_outil", "arguments": {...}}
  {"interventions": ["ID1", "ID2"], "texte": "..."}

Le premier appelle un outil et tu recevras son résultat. Le second termine."""


@dataclass
class Etape:
    """Un tour de boucle, conservé pour la trace — un agent opaque est indébogable."""

    outil: str
    arguments: dict = field(default_factory=dict)
    observation: dict = field(default_factory=dict)

    @property
    def en_erreur(self) -> bool:
        return "erreur" in self.observation

    def resume(self) -> str:
        if self.en_erreur:
            return f"{self.outil} → {self.observation['erreur']}"
        if self.outil == "simuler_intervention":
            o = self.observation
            return (f"simuler_intervention({o.get('id')}) → mesuré "
                    f"{o.get('effet_mesure_mg_dl'):+.1f} mg/dL "
                    f"(population {o.get('effet_population_mg_dl'):+.0f})")
        return f"{self.outil} → ok"


def _observation_texte(obs: dict) -> str:
    txt = json.dumps(obs, ensure_ascii=False, sort_keys=True)
    if len(txt) > MAX_CARACTERES_OBSERVATION:
        txt = txt[:MAX_CARACTERES_OBSERVATION] + " …(tronqué)"
    return txt


def construire_prompt_agent(etat: dict, candidates, journal: list[str]) -> str:
    """Le message utilisateur : l'état, les outils, les choix permis, le journal.

    Comme pour la voie sans agent, **le modèle ne voit pas les interventions qu'il
    n'a pas le droit de proposer** : la contre-indication est appliquée avant le
    prompt, pas après.
    """
    lignes = [
        "État métabolique courant :",
        f"- glycémie : {etat.get('glucose', 0):.0f} mg/dL",
        f"- tendance : {etat.get('pente_mg_min', 0):+.2f} mg/dL/min",
        f"- glucides en digestion : {etat.get('cob_g', 0):.0f} g",
        f"- activité : {etat.get('met', 1.0):.1f} MET",
        "",
        "Outils disponibles :",
        decrire_outils(),
        "",
        "Interventions autorisées dans cet état (identifiant — effet de population) :",
    ]
    for i in candidates:
        lignes.append(f"- {i.id} — {i.titre} ({i.effet_pic:+.0f} mg/dL)")
    if journal:
        lignes += ["", "Ce que tu as déjà fait :"] + journal
    lignes += ["", "Réponds par un seul objet JSON."]
    return "\n".join(lignes)


def executer_agent(etat: dict, ctx: JumeauContext, llm,
                   *, max_etapes: int = MAX_ETAPES,
                   n_max: int = 3) -> Recommandation:
    """Fait tourner la boucle et renvoie une recommandation **validée**.

    En cas d'échec — budget épuisé, JSON illisible, sortie rejetée, API en
    panne — on ne rattrape pas la sortie du modèle : on renvoie le repli
    déterministe. Le repli est le comportement de référence, l'agent n'est
    qu'une amélioration de la formulation et de la précision du chiffre.
    """
    autorise, raison = etat_autorise_recommandation(etat)
    if not autorise:
        return Recommandation(
            interventions=[], texte=REFUS_ETAT_BAS, source="refus",
            validation=ValidationResult(ok=False, texte=REFUS_ETAT_BAS,
                                        refus=[f"etat interdit : {raison}"],
                                        etat_interdit=True))

    candidates, refusees = interventions_possibles(etat)
    repli = Recommandation(interventions=candidates[:n_max],
                           texte=texte_deterministe(candidates[:n_max]),
                           source="repli", refusees=refusees)
    if llm is None or not candidates:
        return repli

    ctx.etat = dict(etat)                     # l'état est copié : les outils lisent
    journal: list[str] = []
    trace: list[Etape] = []

    for _ in range(max_etapes):
        try:
            brut = llm.completer(SYSTEME_AGENT,
                                 construire_prompt_agent(etat, candidates, journal))
        except Exception:                                       # noqa: BLE001
            repli.trace = trace
            return repli

        message = extraire_json(brut)
        if not isinstance(message, dict) or not message:
            journal.append("- réponse illisible ; réponds par un seul objet JSON")
            continue

        nom = message.get("outil")
        if isinstance(nom, str) and nom:
            args = message.get("arguments")
            args = args if isinstance(args, dict) else {}
            obs = executer(nom, args, ctx)            # ne lève jamais
            etape = Etape(outil=nom, arguments=args, observation=obs)
            trace.append(etape)
            journal.append(f"- {nom}({json.dumps(args, ensure_ascii=False)}) → "
                           f"{_observation_texte(obs)}")
            continue

        # sortie finale : le même validateur que sans agent
        v = valider(message, etat)
        if not v.ok:
            repli.validation, repli.trace = v, trace
            return repli
        return Recommandation(interventions=v.interventions[:n_max], texte=v.texte,
                              source="agent", validation=v, refusees=refusees,
                              trace=trace)

    repli.trace = trace
    repli.validation = ValidationResult(
        ok=False, refus=[f"budget epuise ({max_etapes} etapes sans conclusion)"])
    return repli
