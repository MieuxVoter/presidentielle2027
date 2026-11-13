"""Création de PR : commandes contrôlées, sans réseau ni dépôt Git réel."""

from types import SimpleNamespace

import pytest

from mining import pull_request
from mining.proposal import Proposal


def _proposal():
    return Proposal(
        filename="notice.pdf",
        methodology={
            "institute": "OpinionWay",
            "commissioner": "CNews",
            "start": "2026-09-09",
            "end": "2026-09-10",
            "sample": 1001,
            "registered": 935,
            "population": "représentatif de la population française âgée de 18 ans et plus",
            "source_dates": "Du 9 au 10 septembre 2026",
            "source_sample": "1 001 personnes",
            "source_registered": "935 inscrits",
        },
        polls=[{"poll_id": "20260909_0910_ow_A", "hypothese": "H1", "tour": "1er Tour"}],
        results={"20260909_0910_ow_A": []},
        evidence={
            "20260909_0910_ow_A": {
                "page": 12,
                "values": [{"candidat": "Marine Le Pen", "intentions": "30", "source": "Marine Le Pen 30%"}],
            }
        },
        failures=["citation <inventée>"],
    )


def test_nom_de_branche_est_deterministe_et_borne():
    assert pull_request.branch_name(42) == "mining/issue-42"
    with pytest.raises(pull_request.PullRequestError):
        pull_request.branch_name(0)


def test_corps_de_pr_contient_citations_brouillon_et_echappe_le_modele():
    body = pull_request.body(42, _proposal(), ["model:free"], 5)
    assert "Closes #42" in body
    assert "comparé chaque tableau" in body
    assert "page 12" in body and "Marine Le Pen 30%" in body
    assert "&lt;inventée&gt;" in body
    assert "model:free" in body and "appels LLM : 5" in body


def test_prepare_branch_ne_change_que_la_branche_dediee(monkeypatch, tmp_path):
    commands = []

    def fake_run(command, root, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pull_request, "_run", fake_run)
    assert pull_request.prepare_branch(42, tmp_path) == "mining/issue-42"
    assert commands == [
        ["git", "status", "--porcelain"],
        ["git", "fetch", "origin", "main"],
        ["git", "switch", "-C", "mining/issue-42", "origin/main"],
    ]


def test_creation_de_pr_est_un_brouillon_et_applique_les_labels(monkeypatch, tmp_path):
    commands = []
    views = 0

    def fake_run(command, root, **kwargs):
        nonlocal views
        commands.append(command)
        if command[:3] == ["git", "diff", "--cached"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        if command[:3] == ["gh", "pr", "view"]:
            views += 1
            if views == 1:
                return SimpleNamespace(returncode=1, stdout="", stderr="not found")
            return SimpleNamespace(returncode=0, stdout='{"number": 7, "url": "https://example.test/pr/7"}', stderr="")
        if command[:3] == ["gh", "label", "list"]:
            return SimpleNamespace(
                returncode=0, stdout='[{"name": "automated"}, {"name": "needs-human-review"}]', stderr=""
            )
        if command[:3] == ["gh", "pr", "create"]:
            return SimpleNamespace(returncode=0, stdout="https://example.test/pr/7\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pull_request, "_run", fake_run)
    monkeypatch.setattr(pull_request, "_validate", lambda root: None)
    result = pull_request.create_or_update(42, "MieuxVoter/presidentielle2027", _proposal(), tmp_path)
    assert result.number == 7 and result.url.endswith("/7")
    create = next(command for command in commands if command[:3] == ["gh", "pr", "create"])
    assert "--draft" in create and "--head" in create and "mining/issue-42" in create
    labels = next(command for command in commands if command[:3] == ["gh", "pr", "edit"])
    assert "--add-label" in labels and "needs-human-review" in labels


@pytest.mark.parametrize("state,reused", [("OPEN", True), ("CLOSED", False), ("MERGED", False)])
def test_seule_une_pr_ouverte_est_reutilisee(monkeypatch, tmp_path, state, reused):
    def fake_run(command, root, **kwargs):
        return SimpleNamespace(
            returncode=0, stdout=f'{{"number": 7, "url": "https://example.test/pr/7", "state": "{state}"}}', stderr=""
        )

    monkeypatch.setattr(pull_request, "_run", fake_run)
    found = pull_request._existing_pr("MieuxVoter/presidentielle2027", "mining/issue-42", tmp_path)
    assert (found is not None) == reused


def test_une_pr_incomplete_le_dit_en_tete():
    proposal = _proposal()
    proposal.missing = ["page 40 : quota épuisé chez openrouter (remise à zéro 00:00 UTC)"]
    body = pull_request.body(42, proposal, ["model:free"], 5)
    assert "Dépouillement incomplet" in body and "page 40 : quota épuisé" in body
    assert body.index("Dépouillement incomplet") < body.index("Tableaux proposés")


def test_une_pr_complete_ne_parle_pas_d_incomplet():
    assert "Dépouillement incomplet" not in pull_request.body(42, _proposal(), ["model:free"], 5)
