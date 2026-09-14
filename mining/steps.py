"""Les étapes de l'entonnoir : une question, un appel, une sortie contrainte.

Chaque étape valide la réponse du modèle avant de la rendre. Une réponse hors
format est rejouée une fois, puis abandonnée — jamais réinterprétée.

Lot 1 : seule l'étape E1 est implémentée. Elle porte sur le document ENTIER et
non page par page : le modèle a besoin du contexte pour distinguer un tableau
d'intentions d'un rappel de vote passé, et une notice ne doit coûter qu'un appel.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from string import Template

from mining.client import BudgetExceeded, LLMError

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

YES = {"oui", "yes", "o"}
NO = {"non", "no", "n"}
PAGES_RE = re.compile(r"^\s*pages?\s*[:=]\s*(.*)$", re.IGNORECASE)
METHODO_RE = re.compile(r"^\s*meth?odo(?:logie)?\s*[:=]\s*(.*)$", re.IGNORECASE)
# Les modèles à raisonnement des catalogues gratuits pensent à voix haute avant
# de conclure : il leur faut de la place, sinon la conclusion est tronquée. Une
# notice Harris Interactive de 72 pages a épuisé 1200 tokens avant d'y parvenir.
ANSWER_TOKENS = 4000
# Budget du second essai, quand le premier a été coupé par la limite.
ANSWER_TOKENS_RETRY = 12000
RAPPEL = (
    "\n\nRappel : termine ta réponse par une ligne contenant uniquement NON, "
    "ou bien par une ligne OUI suivie d'une ligne « PAGES: » listant les numéros de page."
)
BREF = (
    "\n\nSois bref : ne passe pas les pages en revue une par une et ne recopie pas le document. "
    "Repère les tableaux d'intentions de vote, puis termine directement par les lignes du format demandé."
)


def load_prompt(name):
    """Le gabarit d'une question. Éditer le fichier suffit, aucun code à toucher."""
    return Template((PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8"))


def system_prompt():
    return (PROMPTS_DIR / "system.txt").read_text(encoding="utf-8").strip()


def _single_word(line):
    cleaned = unicodedata.normalize("NFD", line.strip().lower())
    cleaned = "".join(c for c in cleaned if unicodedata.category(c) != "Mn")
    words = [w for w in re.split(r"[^a-z]+", cleaned) if w]
    return words[0] if len(words) == 1 else None


def read_answer(text):
    """(verdict, pages citées, pages de méthodologie), sans vérification.

    verdict vaut True, False, ou None quand la réponse est inexploitable. La
    dernière conclusion l'emporte : un modèle qui hésite puis tranche est suivi
    sur ce qu'il a tranché. La vérification des pages se fait ailleurs.
    """
    lines = [line for line in (text or "").splitlines() if line.strip()]

    # Une ligne sans numéro (« PAGES: list », gabarit recopié pendant la
    # réflexion) n'efface pas des pages déjà lues.
    pages, methodo_pages = [], []
    for line in lines:
        match = PAGES_RE.match(line)
        if match and re.search(r"\d", match.group(1)):
            pages = [int(n) for n in re.findall(r"\d+", match.group(1))]
        match = METHODO_RE.match(line)
        if match and re.search(r"\d", match.group(1)):
            methodo_pages = [int(n) for n in re.findall(r"\d+", match.group(1))]

    verdict = None
    for line in lines:
        word = _single_word(line)
        if word in YES:
            verdict = True
        elif word in NO:
            verdict = False

    return verdict, list(dict.fromkeys(pages)), list(dict.fromkeys(methodo_pages))


def split_answer(text):
    """(réflexion, réponse finale) — la réponse finale part de la ligne de verdict.

    Les modèles à raisonnement écrivent leur réflexion avant de conclure. Les
    deux parties sont séparées pour que le commentaire publié montre la
    conclusion, et la réflexion seulement quand il y en a une.
    """
    lines = (text or "").splitlines()
    verdict_line = None
    for index, line in enumerate(lines):
        if _single_word(line) in YES | NO:
            verdict_line = index
    if verdict_line is None:
        return (text or "").strip(), ""
    return "\n".join(lines[:verdict_line]).strip(), "\n".join(lines[verdict_line:]).strip()


@dataclass
class Triage:
    """Résultat de l'étape E1 sur une notice."""

    pages_with_intentions: list = field(default_factory=list)
    invalid_pages: list = field(default_factory=list)
    methodo_pages: list = field(default_factory=list)
    invalid_methodo_pages: list = field(default_factory=list)
    failed: str = ""
    answered_no: bool = False
    reasoning: str = ""
    final: str = ""

    @property
    def verdict(self):
        """'oui', 'non' ou 'incertain'."""
        if self.failed:
            return "incertain"
        if self.pages_with_intentions:
            return "oui"
        return "non" if self.answered_no else "incertain"


def document_text(pages):
    """Le document remis au modèle, séparateurs de page inclus."""
    return "\n".join(f"--- page {page.number} ---\n{page.text}" for page in pages)


def triage(client, pages):
    """E1 : un seul appel sur le document entier."""
    prompt = load_prompt("e1_intentions")
    question = prompt.safe_substitute(document=document_text(pages))
    system = system_prompt()
    valid = {page.number for page in pages}
    result = Triage()

    try:
        answer = client.ask(system, question, max_tokens=ANSWER_TOKENS)
        verdict, cited, methodo_cited = read_answer(answer.text)
        # Une réponse coupée n'a pas atteint sa conclusion : un « OUI » ou un
        # « PAGES: » lus dedans viennent de la réflexion, où le modèle recopie
        # souvent le format demandé (cas réel, issue #194). Elle est rejouée.
        if verdict is None or answer.truncated:
            # Une réponse coupée par la limite n'a pas ignoré la consigne : elle a
            # manqué de place. On lui en donne davantage en lui demandant d'aller
            # droit au but, plutôt que de lui rappeler un format qu'elle suivait.
            if answer.truncated:
                answer = client.ask(system, question + BREF, max_tokens=ANSWER_TOKENS_RETRY)
            else:
                answer = client.ask(system, question + RAPPEL, max_tokens=ANSWER_TOKENS)
            verdict, cited, methodo_cited = read_answer(answer.text)
    except BudgetExceeded as exc:
        result.failed = f"budget épuisé ({exc})"
        return result
    except LLMError as exc:
        result.failed = f"aucun fournisseur disponible ({exc})"
        return result

    result.reasoning, result.final = split_answer(answer.text)

    if answer.truncated:
        result.failed = "la réponse du modèle a été coupée par la limite de longueur avant sa conclusion"
        return result
    if verdict is False:
        result.answered_no = True
        return result
    if verdict is None:
        result.failed = "le modèle n'a pas répondu dans le format demandé"
        return result

    # Vérification : un numéro de page absent du document est écarté, pas corrigé.
    result.pages_with_intentions = sorted(n for n in cited if n in valid)
    result.invalid_pages = sorted(n for n in cited if n not in valid)
    result.methodo_pages = sorted(n for n in methodo_cited if n in valid)
    result.invalid_methodo_pages = sorted(n for n in methodo_cited if n not in valid)
    if not result.pages_with_intentions:
        # Un OUI sans page vérifiable ne dit pas où regarder, et rien ne garantit
        # que le modèle a lu le document plutôt que deviné.
        result.failed = "le modèle a répondu OUI sans citer de page existante"
    return result
