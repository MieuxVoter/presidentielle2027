"""Garde-fous du déclenchement automatique de triage après création d'issue."""

import pytest

import check_new_polls


def test_trigger_llm_triage_declenche_le_workflow_avec_issue_et_mode(monkeypatch):
    called = {}

    def fake_request(url, token, method="GET", payload=None):
        called.update(url=url, token=token, method=method, payload=payload)
        return {}

    monkeypatch.setattr(check_new_polls, "_github_request", fake_request)

    check_new_polls.trigger_llm_triage("MieuxVoter/presidentielle2027", "token-test", 211, "main")

    assert called == {
        "url": "https://api.github.com/repos/MieuxVoter/presidentielle2027/actions/workflows/llm-mining.yml/dispatches",
        "token": "token-test",
        "method": "POST",
        "payload": {"ref": "main", "inputs": {"issue": "211", "mode": "triage"}},
    }


def test_run_create_issues_declenche_triage_pour_chaque_issue(monkeypatch):
    catalog = [{"filename": "old.pdf"}, {"filename": "new-1.pdf"}, {"filename": "new-2.pdf"}]
    new_polls = [{"filename": "new-1.pdf"}, {"filename": "new-2.pdf"}]

    monkeypatch.setattr(check_new_polls, "find_new_polls", lambda _limit: (catalog, new_polls))
    monkeypatch.setattr(check_new_polls, "get_existing_issues", lambda _repo, _token: set())
    monkeypatch.setattr(check_new_polls, "load_template", lambda: object())

    created = iter([101, 102])
    monkeypatch.setattr(
        check_new_polls,
        "create_issue",
        lambda _poll, _repo, _token, _template: {"number": next(created), "title": "issue"},
    )

    dispatched = []
    monkeypatch.setattr(
        check_new_polls, "trigger_llm_triage", lambda _repo, _token, number, ref: dispatched.append((number, ref))
    )

    saved = []
    monkeypatch.setattr(check_new_polls, "save_poll_count", lambda count: saved.append(count))
    monkeypatch.setenv("GITHUB_REF_NAME", "main")

    assert check_new_polls.run_create_issues("MieuxVoter/presidentielle2027", "token-test", 10) == 0
    assert dispatched == [(101, "main"), (102, "main")]
    assert saved == [len(catalog)]


class _FakeResponse:
    def __init__(self, text):
        self._data = text.encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _with_text(monkeypatch, text):
    monkeypatch.setattr(check_new_polls, "urlopen", lambda _url, timeout=None: _FakeResponse(text))


POLL = {"filename": "x.pdf", "pdf_path": "archives/2026/octobre/x.pdf"}
FILLER = " Méthodologie de l'enquête." * 20


def test_filtre_texte_garde_une_notice_d_intentions_de_vote(monkeypatch):
    _with_text(monkeypatch, "Intentions de vote au premier tour de l’élection présidentielle" + FILLER)
    assert check_new_polls.has_vote_intentions(POLL)


@pytest.mark.parametrize(
    "phrase",
    [
        "premier tour du scrutin présidentiel",
        "Premier tour de la présidentielle (2027)",
        "second tour de l'élection du Président de la République",
        "1 er tour de l’élection présidentielle",
        "1ᵉʳ tour de l'élection présidentielle",
        "1re tour de la présidentielle",
        "2nd tour de l' élection présidentielle",
        "2ème tour de l'élection présidentielle",
        "2e tour du scrutin présidentiel",
        "deuxième tour de l’élection présidentielle",
    ],
)
def test_filtre_texte_garde_les_formulations_voisines_du_tour_de_scrutin(monkeypatch, phrase):
    _with_text(monkeypatch, f"Intentions de vote au {phrase}" + FILLER)
    assert check_new_polls.has_vote_intentions(POLL)


@pytest.mark.parametrize(
    "question",
    [
        # YouGov / Datapraxis, avril 2022 (notice 9553)
        "Si demain avait lieu le premier tour de l’élection présidentielle, pour quel(le) candidat(e) "
        "y aurait-il le plus de chance que vous votiez ?",
        # Harris Interactive / Atlantico, 2017 (notice 8269)
        "Si le premier tour de l’élection présidentielle avait lieu dimanche prochain, parmi les candidats "
        "suivants, pour lequel y aurait-il le plus de chances que vous votiez ?",
    ],
)
def test_filtre_texte_garde_une_question_d_intention_de_vote_sans_l_expression(monkeypatch, question):
    _with_text(monkeypatch, question + FILLER)
    assert check_new_polls.has_vote_intentions(POLL)


def test_notices_ecartees_listees_dans_le_resume_du_run(monkeypatch, tmp_path, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    check_new_polls.report_skipped([{"filename": "x.pdf", "pdf_path": "archives/2026/octobre/x.pdf"}])

    assert "x.pdf" in capsys.readouterr().out
    content = summary.read_text(encoding="utf-8")
    assert "1 notice(s) écartée(s)" in content
    assert f"[x.pdf]({check_new_polls.BLOB_BASE}archives/2026/octobre/x.pdf)" in content


def test_filtre_texte_ecarte_un_tour_d_une_autre_election(monkeypatch):
    _with_text(monkeypatch, "Intentions de vote au premier tour de l'élection municipale" + FILLER)
    assert not check_new_polls.has_vote_intentions(POLL)


def test_filtre_texte_ecarte_une_notice_sans_intentions_de_vote(monkeypatch):
    _with_text(
        monkeypatch, "Le pouvoir d'achat des Français. Vote au 1er tour de l'élection présidentielle 2022" + FILLER
    )
    assert not check_new_polls.has_vote_intentions(POLL)


def test_filtre_texte_garde_la_notice_si_le_texte_manque(monkeypatch):
    def missing(_url, timeout=None):
        raise check_new_polls.URLError("404")

    monkeypatch.setattr(check_new_polls, "urlopen", missing)
    assert check_new_polls.has_vote_intentions(POLL)
    _with_text(monkeypatch, "scan")  # notice scannée : texte vide
    assert check_new_polls.has_vote_intentions(POLL)


def test_compteur_avance_si_toutes_les_nouvelles_notices_sont_ecartees(monkeypatch):
    catalog = [{"filename": "old.pdf"}, {"filename": "new.pdf"}]
    monkeypatch.setattr(check_new_polls, "find_new_polls", lambda _limit: (catalog, []))
    monkeypatch.setattr(check_new_polls, "get_last_poll_count", lambda: 1)
    saved = []
    monkeypatch.setattr(check_new_polls, "save_poll_count", lambda count: saved.append(count))

    assert check_new_polls.run_create_issues("MieuxVoter/presidentielle2027", "token-test", 10) == 0
    assert saved == [2]
