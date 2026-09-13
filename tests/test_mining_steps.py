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

    def ask(self, system, prompt, **kwargs):
        if not self.answers:
            raise AssertionError("le client factice a été appelé plus que prévu")
        item = self.answers.pop(0)
        if isinstance(item, Exception):
            raise item
        self.calls += 1
        self.log.append({"provider": "fake", "model": "fake-model", "prompt": prompt, "answer": item})
        return Answer(item, "fake", "fake-model")


@pytest.mark.parametrize(
    "brut,attendu",
    [
        ("NON", (False, [])),
        ("non\n", (False, [])),
        ("OUI\nPAGES: 2", (True, [2])),
        ("OUI\nPAGES: 1, 2, 3", (True, [1, 2, 3])),
        ("oui\npages : 3,2", (True, [3, 2])),  # casse et séparateurs indifférents
        ("OUI\nPAGES: 2, 2, 2", (True, [2])),  # doublons écartés
        # Un modèle à raisonnement déroule sa réflexion avant de conclure.
        ("Le document présente un tableau d'intentions.\n\nOUI\nPAGES: 2\n", (True, [2])),
        # Conclusion finale prioritaire sur une hésitation antérieure.
        ("OUI peut-être\nNON", (False, [])),
        ("", (None, [])),
        ("Je ne sais pas trop", (None, [])),
        ("OUI", (True, [])),  # le parsing n'invalide pas : c'est triage() qui vérifie
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
