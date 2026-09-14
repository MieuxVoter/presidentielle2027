"""Les garde-fous du workflow sont vérifiés sans interpréter du YAML GitHub."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workflow_declenche_pr_auto_et_commandes_restreintes():
    workflow = (ROOT / ".github" / "workflows" / "llm-mining.yml").read_text(encoding="utf-8")
    assert "contents: write" in workflow and "pull-requests: write" in workflow
    assert "/mining-pr" in workflow and "/triage" in workflow
    assert "OWNER\",\"MEMBER\",\"COLLABORATOR" in workflow
    assert "--pr" in workflow and "--post" in workflow


def test_validation_rejoue_a_la_sortie_du_brouillon():
    workflow = (ROOT / ".github" / "workflows" / "validate-polls.yml").read_text(encoding="utf-8")
    assert "ready_for_review" in workflow
