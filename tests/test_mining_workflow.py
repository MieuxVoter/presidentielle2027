"""Les garde-fous du workflow, vérifiés en exécutant ses scripts shell.

Sans PyYAML (absent de la CI) : on découpe le texte du workflow, puis on lance
les scripts `run:` avec bash et un faux `python` qui note ses arguments.
"""

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "llm-mining.yml"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash requis")


def _step(name):
    """Les lignes d'une étape, de son `- name:` à l'étape suivante."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {name}")
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = start + 1
    while end < len(lines) and not (lines[end].strip() and len(lines[end]) - len(lines[end].lstrip()) <= indent):
        end += 1
    return lines[start:end]


def _script(name):
    step = _step(name)
    run = next(i for i, line in enumerate(step) if line.strip() == "run: |")
    return textwrap.dedent("\n".join(step[run + 1 :])) + "\n"


def _bash(script, tmp_path, **env):
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    full_env = {"PATH": os.environ["PATH"], "GITHUB_OUTPUT": str(output), **env}
    subprocess.run(["bash", "-euo", "pipefail", "-c", script], env=full_env, check=True, cwd=tmp_path)
    return dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines() if line)


def test_workflow_declenche_pr_auto_et_commandes_restreintes():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "contents: write" in workflow and "pull-requests: write" in workflow
    assert 'OWNER","MEMBER","COLLABORATOR' in workflow


def test_validation_rejoue_a_la_sortie_du_brouillon():
    workflow = (ROOT / ".github" / "workflows" / "validate-polls.yml").read_text(encoding="utf-8")
    assert "ready_for_review" in workflow


def test_l_etape_de_commande_tourne_pour_tous_les_declencheurs():
    # Restreinte à issue_comment, elle laissait le mode vide à l'ouverture d'une
    # issue : aucune PR automatique n'aurait jamais été ouverte.
    step = _step("Vérifier la commande")
    assert not any(line.strip().startswith("if:") for line in step)
    assert not any("${{" in line for line in _script("Vérifier la commande").splitlines())


@pytest.mark.parametrize(
    "event,body,dispatch,attendu",
    [
        ("issues", "", "", {"mode": "mining-pr"}),
        ("workflow_dispatch", "", "triage", {"mode": "triage"}),
        ("workflow_dispatch", "", "mining-pr", {"mode": "mining-pr"}),
        ("issue_comment", "/mining-pr", "", {"mode": "mining-pr"}),
        ("issue_comment", "/triage", "", {"mode": "triage"}),
        ("issue_comment", "J'essaie à nouveau.\n  /mining-pr", "", {"mode": "mining-pr"}),
        ("issue_comment", "il faudrait lancer /mining-pr demain", "", {"skip": "true"}),
        ("issue_comment", "/mining-prs", "", {"skip": "true"}),
        ("issue_comment", "$(touch pwned) /triage", "", {"skip": "true"}),
    ],
)
def test_detection_de_la_commande(tmp_path, event, body, dispatch, attendu):
    outputs = _bash(_script("Vérifier la commande"), tmp_path, EVENT=event, BODY=body, DISPATCH_MODE=dispatch)
    assert outputs == attendu
    assert not (tmp_path / "pwned").exists()


@pytest.mark.parametrize(
    "mode,force,attendu",
    [
        ("mining-pr", "false", "--issue 42 --post --pr"),
        ("mining-pr", "true", "--issue 42 --post --force --pr"),
        ("triage", "true", "--issue 42 --post --force"),
    ],
)
def test_arguments_passes_a_mine_poll(tmp_path, mode, force, attendu):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "python"
    fake.write_text('#!/usr/bin/env bash\nshift\necho "$*" > "$ARGS_FILE"\n', encoding="utf-8")
    fake.chmod(0o755)
    args_file = tmp_path / "args"
    subprocess.run(
        ["bash", "-euo", "pipefail", "-c", _script("Miner la notice et créer la PR brouillon")],
        env={
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "ARGS_FILE": str(args_file),
            "ISSUE": "42",
            "MODE": mode,
            "FORCE": force,
        },
        check=True,
        cwd=tmp_path,
    )
    assert args_file.read_text(encoding="utf-8").strip() == attendu
