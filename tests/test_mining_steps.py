"""Étape E1 et validation de la réponse. Aucun appel réseau : client factice."""

from pathlib import Path

import pytest

from mining import notice, steps
from mining.client import Answer, BudgetExceeded, LLMError

FIXTURE = Path(__file__).parent / "fixtures" / "notices" / "mini_notice.txt"
PAGES = notice.strip_empty(notice.split_pages(FIXTURE.read_text(encoding="utf-8")))


class FakeClient:
    """Rejoue des réponses fixées, dans l'ordre, sans réseau."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0
        self.log = []
        self.prompts = []
        self.budgets = []

    def ask(self, system, prompt, **kwargs):
        if not self.answers:
            raise AssertionError("le client factice a été appelé plus que prévu")
        item = self.answers.pop(0)
        if isinstance(item, Exception):
            raise item
        self.calls += 1
        self.prompts.append(prompt)
        self.budgets.append(kwargs.get("max_tokens"))
        answer = item if isinstance(item, Answer) else Answer(item, "fake", "fake-model")
        self.log.append({"provider": "fake", "model": answer.model, "prompt": prompt, "answer": answer.text})
        return answer


@pytest.mark.parametrize(
    "brut,attendu",
    [
        ("NON", (False, [], [])),
        ("non\n", (False, [], [])),
        ("OUI\nPAGES: 2", (True, [2], [])),
        ("OUI\nPAGES: 1, 2, 3", (True, [1, 2, 3], [])),
        ("oui\npages : 3,2", (True, [3, 2], [])),  # casse et séparateurs indifférents
        ("OUI\nPAGES: 2, 2, 2", (True, [2], [])),  # doublons écartés
        ("OUI\nPAGES: 2\nMETHODO: 1, 1", (True, [2], [1])),
        # Un modèle à raisonnement déroule sa réflexion avant de conclure.
        ("Le document présente un tableau d'intentions.\n\nOUI\nPAGES: 2\n", (True, [2], [])),
        # Conclusion finale prioritaire sur une hésitation antérieure.
        ("OUI peut-être\nNON", (False, [], [])),
        ("", (None, [], [])),
        ("Je ne sais pas trop", (None, [], [])),
        ("OUI", (True, [], [])),  # le parsing n'invalide pas : c'est triage() qui vérifie
    ],
)
def test_read_answer(brut, attendu):
    assert steps.read_answer(brut) == attendu


def test_triage_ecarte_une_page_inventee():
    result = steps.triage(FakeClient(["OUI\nPAGES: 2, 42"]), PAGES)
    assert result.pages_with_intentions == [2]
    assert result.invalid_pages == [42]
    assert result.verdict == "oui"


def test_triage_refuse_un_oui_sans_page_existante():
    result = steps.triage(FakeClient(["OUI\nPAGES: 98, 99", "OUI\nPAGES: 98, 99"]), PAGES)
    assert result.verdict == "incertain"
    assert "sans citer de page existante" in result.failed


def test_triage_refuse_un_oui_sans_aucune_page():
    result = steps.triage(FakeClient(["OUI", "OUI"]), PAGES)
    assert result.verdict == "incertain"


def test_document_text_porte_les_separateurs_de_page():
    document = steps.document_text(PAGES)
    assert "--- page 1 ---" in document and "--- page 3 ---" in document
    assert "Jean-Luc Mélenchon" in document


def test_triage_ne_consomme_qu_un_appel():
    client = FakeClient(["OUI\nPAGES: 2"])
    result = steps.triage(client, PAGES)
    assert client.calls == 1
    assert result.pages_with_intentions == [2]
    assert result.verdict == "oui"


def test_triage_conserve_les_pages_de_methodologie_verifiees():
    result = steps.triage(FakeClient(["OUI\nPAGES: 2\nMETHODO: 1, 42"]), PAGES)
    assert result.methodo_pages == [1]
    assert result.invalid_methodo_pages == [42]


def test_triage_sans_intentions_donne_non():
    result = steps.triage(FakeClient(["NON"]), PAGES)
    assert result.pages_with_intentions == []
    assert result.verdict == "non"


def test_triage_relance_une_fois_sur_reponse_illisible():
    client = FakeClient(["je ne sais pas", "OUI\nPAGES: 2"])
    result = steps.triage(client, PAGES)
    assert client.calls == 2
    assert result.verdict == "oui"


def test_triage_abandonne_apres_la_relance():
    result = steps.triage(FakeClient(["bla", "bla encore"]), PAGES)
    assert result.verdict == "incertain"
    assert "format demandé" in result.failed


def test_triage_s_arrete_proprement_si_le_budget_est_epuise():
    result = steps.triage(FakeClient([BudgetExceeded("plafond de 1 appels atteint")]), PAGES)
    assert "budget épuisé" in result.failed
    assert result.verdict == "incertain"


def test_triage_s_arrete_si_aucun_fournisseur_ne_repond():
    result = steps.triage(FakeClient([LLMError("429 partout")]), PAGES)
    assert "aucun fournisseur" in result.failed
    assert result.verdict == "incertain"


def test_le_prompt_porte_le_placeholder_du_document():
    assert "$document" in (steps.PROMPTS_DIR / "e1_intentions.txt").read_text(encoding="utf-8")
    assert steps.system_prompt()


def test_le_prompt_exclut_le_rappel_de_vote_passe():
    # Le faux positif observé en conditions réelles : le rappel de vote 2022.
    texte = (steps.PROMPTS_DIR / "e1_intentions.txt").read_text(encoding="utf-8")
    assert "RAPPEL DE VOTE" in texte and "2022" in texte


def test_reponse_tronquee_relancee_avec_plus_de_place_et_consigne_de_brievete():
    # Cas réel, issue #194 : notice de 72 pages, réflexion coupée page 36.
    coupee = Answer("Page 33 : un tableau. Page 34 : un autre. Page 35", "fake", "m", truncated=True)
    client = FakeClient([coupee, "OUI\nPAGES: 2"])
    result = steps.triage(client, PAGES)
    assert result.verdict == "oui"
    assert client.budgets == [steps.ANSWER_TOKENS, steps.ANSWER_TOKENS_RETRY]
    assert steps.BREF in client.prompts[1] and steps.RAPPEL not in client.prompts[1]


def test_reponse_hors_format_non_tronquee_garde_le_rappel_de_format():
    client = FakeClient(["je ne sais pas", "OUI\nPAGES: 2"])
    steps.triage(client, PAGES)
    assert client.budgets == [steps.ANSWER_TOKENS, steps.ANSWER_TOKENS]
    assert steps.RAPPEL in client.prompts[1]


def test_deux_troncatures_donnent_un_message_exact():
    # « pas répondu dans le format demandé » était faux : le modèle avait manqué
    # de place, il n'avait pas ignoré la consigne.
    coupee = Answer("Page 33 : un tableau…", "fake", "m", truncated=True)
    result = steps.triage(FakeClient([coupee, coupee]), PAGES)
    assert result.verdict == "incertain"
    assert "coupée par la limite" in result.failed
    assert "format demandé" not in result.failed


def test_le_prompt_demande_de_ne_pas_passer_les_pages_en_revue():
    texte = (steps.PROMPTS_DIR / "e1_intentions.txt").read_text(encoding="utf-8")
    assert "une par une" in texte
