"""Garde-fous du déclenchement automatique de triage après création d'issue."""

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


def test_filtre_texte_ecarte_une_notice_sans_intentions_de_vote(monkeypatch):
    _with_text(monkeypatch, "Le pouvoir d'achat des Français. Vote au 1er tour de l'élection présidentielle 2022" + FILLER)
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
