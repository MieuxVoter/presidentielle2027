"""E2/E3 : les sorties de modèle sont vérifiées sans réseau."""

import datetime as dt
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from mining import extraction, notice, steps
from mining.client import BudgetExceeded

ROOT = Path(__file__).resolve().parents[1]
METHOD_PAGE = notice.Page(
    1,
    (
        "Les interviews ont été réalisées du 9 au 10 septembre 2026.",
        "Echantillon de 935 personnes inscrites sur les listes électorales, issu d'un échantillon de 1 001 personnes.",
    ),
)
TABLE_PAGE = notice.Page(
    2,
    (
        "L'intention de vote au premier tour de l'élection présidentielle.",
        "Nathalie Arthaud <1%",
        "Jean-Luc Mélenchon 20%",
        "François Hollande 10%",
        "Édouard Philippe 30%",
        "Marine Le Pen 39,5%",
        "690 personnes certaines d'aller voter.",
    ),
)
E2 = """INSTITUT: OpinionWay
COMMANDITAIRE: CNews
DEBUT: 2026-09-09
FIN: 2026-09-10
ECHANTILLON: 1001
INSCRITS: 935
POPULATION: représentatif de la population française âgée de 18 ans et plus
SOURCE_DATES: Les interviews ont été réalisées du 9 au 10 septembre 2026.
SOURCE_ECHANTILLON: Echantillon de 935 personnes inscrites sur les listes électorales, issu d'un échantillon de 1 001 personnes.
SOURCE_INSCRITS: Echantillon de 935 personnes inscrites sur les listes électorales, issu d'un échantillon de 1 001 personnes.
"""
E3 = """TABLEAU
TOUR: 1er Tour
EFFECTIFS: certains d'aller voter = 690
Nathalie Arthaud | 0.5 | Nathalie Arthaud <1%
Jean-Luc Mélenchon | 20 | Jean-Luc Mélenchon 20%
François Hollande | 10 | François Hollande 10%
Édouard Philippe | 30 | Édouard Philippe 30%
Marine Le Pen | 39.5 | Marine Le Pen 39,5%
FIN
"""


def test_e2_verifie_les_citations_dates_et_effectifs():
    result = extraction.parse_methodology(
        E2,
        [METHOD_PAGE],
        extraction.institutions_from_polls(ROOT / "polls.csv"),
        extraction.populations_from_polls(ROOT / "polls.csv"),
        dt.date(2026, 9, 11),
    )
    assert result.institute == "OpinionWay"
    assert result.sample == 1001 and result.registered == 935


def test_e2_refuse_une_citation_inventee():
    invalid = E2.replace("Les interviews ont été réalisées", "Les interviews seront réalisées")
    with pytest.raises(extraction.ValidationError, match="SOURCE_DATES"):
        extraction.parse_methodology(
            invalid,
            [METHOD_PAGE],
            extraction.institutions_from_polls(ROOT / "polls.csv"),
            extraction.populations_from_polls(ROOT / "polls.csv"),
        )


def test_e3_valide_la_convention_moins_de_un_pourcent_et_la_somme():
    tables, failures = extraction.parse_tables(E3, TABLE_PAGE, extraction.candidate_names(ROOT / "candidats.csv"))
    assert not failures
    assert len(tables) == 1
    assert tables[0].values[0].as_csv() == "0.5"
    assert tables[0].samples == (("certains d'aller voter", 690),)


def test_e3_ecarte_un_tableau_dont_la_citation_est_absente():
    tables, failures = extraction.parse_tables(
        E3.replace("François Hollande 10%", "François Hollande 11%", 1),
        TABLE_PAGE,
        extraction.candidate_names(ROOT / "candidats.csv"),
    )
    assert tables == []
    assert "citation introuvable" in failures[0]


class RecordingClient:
    """Rejoue E2 puis E3 et garde les questions posées."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def ask(self, system, prompt, max_tokens=None):
        self.prompts.append(prompt)
        return SimpleNamespace(text=self.answers.pop(0))


def test_extract_remplit_toutes_les_variables_des_prompts():
    # Template.safe_substitute laisse passer une variable mal nommée : le modèle
    # recevrait « $candidats » au lieu de la liste des noms autorisés.
    client = RecordingClient([E2, E3])
    triage = steps.Triage(pages_with_intentions=[2], methodo_pages=[1])
    journal = []
    result = extraction.extract(
        client,
        [METHOD_PAGE, TABLE_PAGE],
        triage,
        ROOT / "candidats.csv",
        ROOT / "polls.csv",
        dt.date(2026, 9, 11),
        log=journal.append,
    )
    assert not result.failures
    assert len(client.prompts) == 2
    # Les logs du job disent quelles pages ont été lues et ce qui en est sorti.
    assert any("E2 méthodologie : pages [1]" in line for line in journal)
    assert any("E3 page 2" in line for line in journal)
    assert any("1er Tour (5 candidats)" in line for line in journal)
    for prompt in client.prompts:
        assert not re.search(r"\$[A-Za-z_{]", prompt)
    assert "- Édouard Philippe" in client.prompts[1]


class ExhaustedClient:
    def ask(self, system, prompt, max_tokens=None):
        raise BudgetExceeded("plafond de 80 appels atteint")


def test_extract_rapporte_une_erreur_api_en_e2_sans_lever():
    triage = steps.Triage(pages_with_intentions=[2], methodo_pages=[1])
    result = extraction.extract(
        ExhaustedClient(), [METHOD_PAGE, TABLE_PAGE], triage, ROOT / "candidats.csv", ROOT / "polls.csv"
    )
    assert result.methodology is None
    assert result.tables == []
    assert result.failures == ["appel E2 impossible (plafond de 80 appels atteint)"]
