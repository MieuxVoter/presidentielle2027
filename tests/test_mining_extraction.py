"""E2/E3 : les sorties de modèle sont vérifiées sans réseau."""

import datetime as dt
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from mining import extraction, notice, steps
from mining.client import BudgetExceeded, LLMError, QuotaExhausted

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


# Page 3 réelle de la notice Harris Interactive de l'issue #194 : trois colonnes
# côte à côte, la phrase des dates est coupée par la colonne « Échantillon ».
HARRIS_PAGE3 = notice.strip_empty(
    notice.split_pages(
        (Path(__file__).parent / "fixtures" / "notices" / "harris_194_page3.txt").read_text(encoding="utf-8")
    )
)[0]
HARRIS_DATES = "Enquête réalisée en ligne du 08 au 10 septembre 2026."
HARRIS_E2 = """INSTITUT: Harris Interactive
COMMANDITAIRE: M6, RTL
DEBUT: 2026-09-08
FIN: 2026-09-10
ECHANTILLON: 2358
INSCRITS: 2052
POPULATION: représentatif de la population française âgée de 18 ans et plus
SOURCE_DATES: Enquête réalisée en ligne du 08 au 10 septembre 2026.
SOURCE_ECHANTILLON: Échantillon de 2 052 personnes inscrites sur les listes électorales, issu d’un échantillon de 2 358 personnes
SOURCE_INSCRITS: Échantillon de 2 052 personnes inscrites sur les listes électorales
"""


def test_e2_accepte_une_citation_coupee_par_une_colonne_voisine():
    result = extraction.parse_methodology(
        HARRIS_E2,
        [HARRIS_PAGE3],
        extraction.institutions_from_polls(ROOT / "polls.csv"),
        extraction.populations_from_polls(ROOT / "polls.csv"),
        dt.date(2026, 9, 11),
    )
    assert (result.institute, result.start, result.end) == ("Harris Interactive", "2026-09-08", "2026-09-10")
    assert (result.sample, result.registered) == (2358, 2052)


def test_la_citation_d_un_seul_tenant_reste_la_regle_par_defaut():
    # E3 garde ce mode : dans un tableau, un mot intercalé peut être le chiffre voisin.
    assert not extraction.citation_in_page(HARRIS_DATES, HARRIS_PAGE3)
    assert extraction.citation_in_page(HARRIS_DATES, HARRIS_PAGE3, extraction.CITATION_MAX_GAP)


@pytest.mark.parametrize(
    "citation",
    [
        "Enquête réalisée en ligne du 07 au 10 septembre 2026.",  # chiffre inventé
        "Enquête réalisée par téléphone du 08 au 10 septembre 2026.",  # mot inventé
        "Enquête réalisée en ligne du 10 au 08 septembre 2026.",  # ordre inversé
    ],
)
def test_une_citation_non_conforme_reste_refusee_malgre_les_colonnes(citation):
    assert not extraction.citation_in_page(citation, HARRIS_PAGE3, extraction.CITATION_MAX_GAP)


def test_des_mots_trop_eloignes_ne_forment_pas_une_citation():
    page = notice.Page(1, ("Enquête " + "mot " * 30 + "réalisée en ligne",))
    assert not extraction.citation_in_page("Enquête réalisée en ligne", page, 25)
    assert extraction.citation_in_page("Enquête réalisée en ligne", page, 30)


def test_un_jour_a_deux_chiffres_avec_zero_est_reconnu():
    assert extraction._source_has_date(HARRIS_DATES, "2026-09-08")
    assert extraction._source_has_date(HARRIS_DATES, "2026-09-10")
    assert not extraction._source_has_date(HARRIS_DATES, "2026-09-09")


class TruncatingClient:
    """Première réponse coupée par max_tokens, seconde complète."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.budgets = []
        self.prompts = []

    def ask(self, system, prompt, max_tokens=None):
        self.budgets.append(max_tokens)
        self.prompts.append(prompt)
        text, truncated = self.answers.pop(0)
        return SimpleNamespace(text=text, truncated=truncated)


def test_e2_tronquee_est_relancee_avec_plus_de_place():
    # Cas réel, issue #193 : réflexion Ipsos BVA coupée avant les lignes imposées.
    client = TruncatingClient([("INSTITUT: Ipsos BVA\nCOMMANDITAIRE: Le Monde\nDEBUT: 2026", True), (E2, False)])
    method = extraction._ask_methodology(
        client,
        [METHOD_PAGE],
        extraction.institutions_from_polls(ROOT / "polls.csv"),
        extraction.populations_from_polls(ROOT / "polls.csv"),
        dt.date(2026, 9, 11),
    )
    assert method.institute == "OpinionWay"
    assert client.budgets == [extraction.METHOD_TOKENS, extraction.METHOD_TOKENS_RETRY]
    assert "Sois bref" in client.prompts[1]


def test_e3_accepte_la_ligne_source_recopiee_en_tete():
    # Cas réel, issue #194 page 37 : « Marine Le Pen   34 | Marine Le Pen | 34 | Marine Le Pen   34 ».
    lignes = []
    for line in E3.splitlines():
        pieces = [piece.strip() for piece in line.split("|")]
        lignes.append(f"{pieces[2]} | {line}" if len(pieces) == 3 else line)
    tables, failures = extraction.parse_tables(
        "\n".join(lignes), TABLE_PAGE, extraction.candidate_names(ROOT / "candidats.csv")
    )
    assert not failures
    assert [(value.name, value.as_csv()) for value in tables[0].values] == [
        ("Nathalie Arthaud", "0.5"),
        ("Jean-Luc Mélenchon", "20"),
        ("François Hollande", "10"),
        ("Édouard Philippe", "30"),
        ("Marine Le Pen", "39.5"),
    ]


def test_une_ligne_sans_valeur_numerique_reste_refusee():
    tables, failures = extraction.parse_tables(
        E3.replace("Marine Le Pen | 39.5 |", "Marine Le Pen | beaucoup |"),
        TABLE_PAGE,
        extraction.candidate_names(ROOT / "candidats.csv"),
    )
    assert tables == [] and "ligne de tableau attendue" in failures[0]


class E2ThenFailure:
    """E2 répond, puis chaque appel E3 échoue."""

    def __init__(self):
        self.calls = 0

    def ask(self, system, prompt, max_tokens=None):
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(text=E2, truncated=False)
        raise BudgetExceeded("plafond atteint")


def test_un_appel_e3_impossible_est_trace_dans_le_journal():
    journal = []
    triage = steps.Triage(pages_with_intentions=[2], methodo_pages=[1])
    extraction.extract(
        E2ThenFailure(),
        [METHOD_PAGE, TABLE_PAGE],
        triage,
        ROOT / "candidats.csv",
        ROOT / "polls.csv",
        dt.date(2026, 9, 11),
        log=journal.append,
    )
    assert any("page 2 : appel E3 impossible (plafond atteint)" in line for line in journal)


@pytest.mark.parametrize(
    "effectifs,attendu",
    [
        # Cas réel, issue #194 : une entrée sans nombre faisait planter le run (int("")).
        ("certains d'aller voter =  ", ()),
        (
            "exprimé une intention de vote = 1188 | certains d'aller voter = ",
            (("exprimé une intention de vote", 1188),),
        ),
        # Libellé Harris Interactive : la base la plus étroite l'emporte.
        (
            "certains d'aller voter et ayant exprimé une intention de vote = 1339",
            (("certains d'aller voter", 1339),),
        ),
        ("ayant exprimé une intention de vote = 1 188", (("exprimé une intention de vote", 1188),)),
    ],
)
def test_effectifs_tolerants_aux_formulations_et_aux_entrees_vides(effectifs, attendu):
    assert extraction._parse_samples(effectifs) == attendu


def test_libelle_d_effectif_sans_rapport_reste_refuse():
    with pytest.raises(extraction.ValidationError, match="libellé d'effectif inconnu"):
        extraction._parse_samples("abstentionnistes = 200")


def test_une_erreur_de_conversion_ne_rejette_que_son_tableau(monkeypatch):
    def boom(value):
        raise ValueError("invalid literal for int() with base 10: ''")

    monkeypatch.setattr(extraction, "_parse_samples", boom)
    tables, failures = extraction.parse_tables(E3, TABLE_PAGE, extraction.candidate_names(ROOT / "candidats.csv"))
    assert tables == []
    assert "réponse illisible" in failures[0]


def test_e3_tronquee_est_relancee_avec_plus_de_place():
    client = TruncatingClient([(E2, False), ("", True), (E3, False)])
    triage = steps.Triage(pages_with_intentions=[2], methodo_pages=[1])
    result = extraction.extract(
        client, [METHOD_PAGE, TABLE_PAGE], triage, ROOT / "candidats.csv", ROOT / "polls.csv", dt.date(2026, 9, 11)
    )
    assert client.budgets == [extraction.METHOD_TOKENS, extraction.TABLE_TOKENS, extraction.TABLE_TOKENS_RETRY]
    assert len(result.tables) == 1


def test_aucun_tableau_sur_une_page_retenue_est_signale_et_relance():
    # Cas réel, issue #194 page 43 : « AUCUN TABLEAU » sur un vrai tableau.
    tables, failures = extraction.parse_tables(
        "AUCUN TABLEAU", TABLE_PAGE, extraction.candidate_names(ROOT / "candidats.csv")
    )
    assert tables == [] and "AUCUN TABLEAU" in failures[0]

    client = TruncatingClient([(E2, False), ("AUCUN TABLEAU", False), (E3, False)])
    triage = steps.Triage(pages_with_intentions=[2], methodo_pages=[1])
    result = extraction.extract(
        client, [METHOD_PAGE, TABLE_PAGE], triage, ROOT / "candidats.csv", ROOT / "polls.csv", dt.date(2026, 9, 11)
    )
    assert len(client.prompts) == 3
    assert "le triage a repéré" in client.prompts[2]
    assert len(result.tables) == 1


def test_une_meme_base_sous_deux_libelles_ne_remplit_qu_un_sous_echantillon():
    effectifs = "exprimé une intention de vote = 1339 | certains d'aller voter = 1339"
    assert extraction._parse_samples(effectifs) == (("certains d'aller voter", 1339),)
    ifop = "exprimé une intention de vote = 1188 | certains d'aller voter = 930"
    assert extraction._parse_samples(ifop) == (("exprimé une intention de vote", 1188), ("certains d'aller voter", 930))


def test_un_appel_impossible_arrete_les_pages_suivantes():
    # Cas réel, issue #194 : quota épuisé à la page 40, six appels brûlés en 429,
    # et une proposition construite avec 2 tableaux sur 8.
    autre_page = notice.Page(3, TABLE_PAGE.lines)
    client = E2ThenFailure()
    journal = []
    triage = steps.Triage(pages_with_intentions=[2, 3], methodo_pages=[1])
    result = extraction.extract(
        client,
        [METHOD_PAGE, TABLE_PAGE, autre_page],
        triage,
        ROOT / "candidats.csv",
        ROOT / "polls.csv",
        dt.date(2026, 9, 11),
        log=journal.append,
    )
    assert client.calls == 2  # E2, puis la page 2 ; la page 3 n'est pas interrogée
    assert result.api_failures == ["page 2 : plafond atteint"]
    assert any("arrêt" in line for line in journal)


def test_un_appel_e2_impossible_compte_comme_echec_d_api():
    triage = steps.Triage(pages_with_intentions=[2], methodo_pages=[1])
    result = extraction.extract(
        ExhaustedClient(), [METHOD_PAGE, TABLE_PAGE], triage, ROOT / "candidats.csv", ROOT / "polls.csv"
    )
    assert result.api_failures == ["E2 : plafond de 80 appels atteint"]


class ScriptedClient:
    """Réponses et erreurs dans l'ordre, sans réseau."""

    def __init__(self, items):
        self.items, self.prompts = list(items), []

    def ask(self, system, prompt, max_tokens=None):
        self.prompts.append(prompt)
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(text=item, truncated=False)


def _deux_pages(client):
    triage = steps.Triage(pages_with_intentions=[2, 3], methodo_pages=[1])
    return extraction.extract(
        client,
        [METHOD_PAGE, TABLE_PAGE, notice.Page(3, TABLE_PAGE.lines)],
        triage,
        ROOT / "candidats.csv",
        ROOT / "polls.csv",
        dt.date(2026, 9, 11),
    )


def test_un_appel_impossible_hors_quota_n_empeche_pas_les_pages_suivantes():
    # Une réponse vide sur une page ne doit pas faire perdre les tableaux des autres.
    client = ScriptedClient([E2, LLMError("aucun fournisseur n'a répondu — openrouter: réponse vide"), E3])
    result = _deux_pages(client)
    assert [table.page for table in result.tables] == [3]
    assert result.api_failures == ["page 2 : aucun fournisseur n'a répondu — openrouter: réponse vide"]


def test_un_quota_epuise_arrete_les_pages_suivantes():
    client = ScriptedClient([E2, QuotaExhausted("aucun fournisseur n'a répondu — openrouter: quota épuisé")])
    result = _deux_pages(client)
    assert len(client.prompts) == 2 and result.tables == []
    assert len(result.api_failures) == 1
