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
