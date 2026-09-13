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
# Les modèles à raisonnement des catalogues gratuits pensent à voix haute avant
# de conclure : il leur faut de la place, sinon la conclusion est tronquée.
ANSWER_TOKENS = 1200
RAPPEL = (
    "\n\nRappel : termine ta réponse par une ligne contenant uniquement NON, "
    "ou bien par une ligne OUI suivie d'une ligne « PAGES: » listant les numéros de page."
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
    """(verdict, pages citées) — lecture brute de la réponse, sans vérification.

    verdict vaut True, False, ou None quand la réponse est inexploitable. La
    dernière conclusion l'emporte : un modèle qui hésite puis tranche est suivi
    sur ce qu'il a tranché. La vérification des pages se fait ailleurs.
    """
    lines = [line for line in (text or "").splitlines() if line.strip()]

    pages = []
    for line in lines:
        match = PAGES_RE.match(line)
        if match:
            pages = [int(n) for n in re.findall(r"\d+", match.group(1))]

    verdict = None
    for line in lines:
        word = _single_word(line)
        if word in YES:
            verdict = True
        elif word in NO:
            verdict = False

    return verdict, list(dict.fromkeys(pages))


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
        raw = client.ask(system, question, max_tokens=ANSWER_TOKENS).text
        verdict, cited = read_answer(raw)
        if verdict is None:
            raw = client.ask(system, question + RAPPEL, max_tokens=ANSWER_TOKENS).text
            verdict, cited = read_answer(raw)
    except BudgetExceeded as exc:
        result.failed = f"budget épuisé ({exc})"
        return result
    except LLMError as exc:
        result.failed = f"aucun fournisseur disponible ({exc})"
        return result

    result.reasoning, result.final = split_answer(raw)

    if verdict is False:
        result.answered_no = True
        return result
    if verdict is None:
        result.failed = "le modèle n'a pas répondu dans le format demandé"
        return result

    # Vérification : un numéro de page absent du document est écarté, pas corrigé.
    result.pages_with_intentions = sorted(n for n in cited if n in valid)
    result.invalid_pages = sorted(n for n in cited if n not in valid)
    if not result.pages_with_intentions:
        # Un OUI sans page vérifiable ne dit pas où regarder, et rien ne garantit
        # que le modèle a lu le document plutôt que deviné.
        result.failed = "le modèle a répondu OUI sans citer de page existante"
    return result
