"""
L'adaptateur LLM — volontairement mince.

Le modèle ne reçoit **que** la liste d'identifiants qu'il a le droit d'utiliser
et un résumé chiffré de l'état. Il ne choisit pas *quoi* est possible : le
catalogue et l'état l'ont déjà décidé. Il ordonne, et il rédige.

Deux implémentations :

- `MistralLLM` — l'appel réel, qui lit `MISTRAL_API_KEY` dans l'environnement.
- `FakeLLM` — une sortie fixée d'avance, pour les tests.

`FakeLLM` n'est pas un pis-aller : c'est le seul moyen de tester ce qui compte,
à savoir que le **validateur tient quoi que le modèle réponde**. Une sortie
hostile fabriquée est un meilleur test qu'un appel réel qui se passe bien.
"""

from __future__ import annotations

import json
import os
import re

SYSTEME = """Tu aides à formuler des suggestions d'hygiène de vie pour une personne
diabétique de type 2, à partir d'un jumeau numérique.

Règles absolues :
- Tu choisis UNIQUEMENT parmi les identifiants d'interventions fournis. Tu n'en
  inventes aucun, tu n'en modifies aucun.
- Tu ne parles JAMAIS de médicament, d'insuline, de dose, de traitement, de
  posologie, ni de diagnostic.
- Tu n'affirmes rien sur la santé de la personne. Tu expliques ce que le jumeau
  a simulé.
- Trois suggestions au maximum, la plus utile en premier.
- Ton texte fait moins de 500 caractères, en français, sans emphase excessive.

Tu réponds EXCLUSIVEMENT en JSON :
{"interventions": ["ID1", "ID2"], "texte": "..."}"""


def construire_prompt(etat: dict, candidates) -> str:
    """Le message utilisateur : l'état chiffré, et rien que les choix permis."""
    lignes = [
        "État métabolique simulé :",
        f"- glycémie actuelle : {etat.get('glucose', 0):.0f} mg/dL",
        f"- tendance : {etat.get('pente_mg_min', 0):+.2f} mg/dL/min",
        f"- glucides encore en digestion : {etat.get('cob_g', 0):.0f} g",
        f"- intensité de l'activité : {etat.get('met', 1.0):.1f} MET",
        f"- pic simulé sur la journée : {etat.get('pic', 0):.0f} mg/dL",
        "",
        "Interventions autorisées (identifiant — effet simulé sur le pic) :",
    ]
    for i in candidates:
        lignes.append(f"- {i.id} — {i.titre} ({i.effet_pic:+.0f} mg/dL)")
    lignes.append("")
    lignes.append("Choisis au plus trois identifiants dans cette liste et explique.")
    return "\n".join(lignes)


def extraire_json(brut: str) -> dict:
    """Récupère le JSON même si le modèle l'entoure de texte ou de balises.

    Un modèle qui répond « Voici : ```json {...} ``` » ne doit pas faire échouer
    la chaîne pour une raison de forme — les vrais refus doivent venir du
    validateur, pas du parseur.
    """
    if not isinstance(brut, str):
        return {}
    texte = brut.strip()
    texte = re.sub(r"^```(?:json)?|```$", "", texte, flags=re.MULTILINE).strip()
    try:
        return json.loads(texte)
    except json.JSONDecodeError:
        pass
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut >= 0 and fin > debut:
        try:
            return json.loads(texte[debut:fin + 1])
        except json.JSONDecodeError:
            return {}
    return {}


class FakeLLM:
    """Renvoie une sortie fixée — pour tester le validateur, pas le modèle."""

    def __init__(self, reponse):
        self.reponse = reponse
        self.dernier_prompt: str | None = None

    def completer(self, systeme: str, utilisateur: str) -> str:
        self.dernier_prompt = utilisateur
        if isinstance(self.reponse, (dict, list)):
            return json.dumps(self.reponse, ensure_ascii=False)
        return str(self.reponse)


class LLMScripte:
    """Rejoue une suite de réponses fixées — pour tester une **boucle** d'agent.

    `FakeLLM` renvoie toujours la même chose, ce qui ne permet pas de tester un
    enchaînement (appeler un outil, lire l'observation, conclure). Ici chaque
    appel consomme la réponse suivante ; une fois la liste épuisée, la dernière
    est répétée — c'est ainsi qu'on fabrique un agent qui boucle sans fin.
    """

    def __init__(self, reponses, repeter_la_derniere: bool = True):
        self.reponses = list(reponses)
        self.repeter = repeter_la_derniere
        self.appels = 0
        self.prompts: list[str] = []

    @property
    def dernier_prompt(self) -> str | None:
        return self.prompts[-1] if self.prompts else None

    def completer(self, systeme: str, utilisateur: str) -> str:
        self.prompts.append(utilisateur)
        i = self.appels
        self.appels += 1
        if i >= len(self.reponses):
            if not self.repeter or not self.reponses:
                return ""
            i = len(self.reponses) - 1
        r = self.reponses[i]
        return json.dumps(r, ensure_ascii=False) if isinstance(r, (dict, list)) else str(r)


class MistralLLM:
    """Appel réel à l'API Mistral. Lit `MISTRAL_API_KEY` dans l'environnement.

    Aucune clé n'est jamais écrite dans le dépôt ni dans les journaux de run.
    """

    URL = "https://api.mistral.ai/v1/chat/completions"

    def __init__(self, modele: str = "mistral-small-latest", cle: str | None = None,
                 temperature: float = 0.2, timeout: int = 30):
        self.cle = cle or os.environ.get("MISTRAL_API_KEY", "")
        if not self.cle:
            raise RuntimeError(
                "MISTRAL_API_KEY absente de l'environnement. "
                "Placez-la dans un fichier .env (jamais committe) ou exportez-la."
            )
        self.modele, self.temperature, self.timeout = modele, temperature, timeout

    def completer(self, systeme: str, utilisateur: str) -> str:
        import urllib.error
        import urllib.request

        corps = json.dumps({
            "model": self.modele,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": systeme},
                         {"role": "user", "content": utilisateur}],
        }).encode("utf-8")
        req = urllib.request.Request(
            self.URL, data=corps, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.cle}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            # on ne relaie jamais le corps de l'erreur : il peut contenir la requete
            raise RuntimeError(f"API Mistral : HTTP {e.code}") from None
        except Exception as e:                                  # noqa: BLE001
            raise RuntimeError(f"API Mistral injoignable : {type(e).__name__}") from None
