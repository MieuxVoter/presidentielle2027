"""Création sûre d'une PR brouillon à partir d'une proposition déjà validée.

Ce module ne lit aucun contenu de la notice et ne décide aucune valeur : il se
contente de créer une branche dédiée, d'exécuter les vérifications du dépôt, puis
d'appeler GitHub CLI. Les commandes sont passées sous forme de listes, jamais
construites à partir de texte de notice ou de commentaire.
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class PullRequestError(RuntimeError):
    """Une branche ou une PR n'a pas pu être créée ; la cause est publiable."""


@dataclass(frozen=True)
class PullRequest:
    number: int
    url: str
    branch: str
    labels_warning: str = ""


def branch_name(issue):
    """Nom déterministe et sans entrée libre : un rerun met à jour la même PR."""
    if not isinstance(issue, int) or issue <= 0:
        raise PullRequestError("numéro d'issue invalide")
    return f"mining/issue-{issue}"


def _run(command, root, *, input_text=None, allow_failure=False):
    """Exécute une commande et transforme son erreur en diagnostic court."""
    completed = subprocess.run(
        command,
        cwd=root,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode and not allow_failure:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        raise PullRequestError(f"{' '.join(command[:3])} a échoué : {detail[-1] if detail else 'erreur inconnue'}")
    return completed


def _working_tree_clean(root):
    status = _run(["git", "status", "--porcelain"], root).stdout.strip()
    if status:
        raise PullRequestError("l'arbre Git doit être propre avant de préparer la branche de mining")


def prepare_branch(issue, root):
    """Replace la branche de l'issue sur `origin/main`, avant l'écriture des CSV."""
    root = Path(root)
    _working_tree_clean(root)
    branch = branch_name(issue)
    _run(["git", "fetch", "origin", "main"], root)
    # Cette branche est strictement réservée à l'issue. La recréer à chaque run
    # remplace la proposition précédente, jamais une branche humaine.
    _run(["git", "switch", "-C", branch, "origin/main"], root)
    return branch


def _safe(text):
    """Le texte issu du modèle reste du texte, pas du Markdown exécutable."""
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("```", "'''")


def body(issue, proposal, models, calls):
    """Corps de PR relisible : toutes les valeurs pointent vers leur citation."""
    method = proposal.methodology
    lines = [
        "# Proposition de sondage générée automatiquement",
        "",
        f"Closes #{issue}",
        "",
        "> 🤖 Cette PR est un brouillon. Une comparaison humaine avec la notice/PDF est obligatoire avant fusion.",
        "",
        "- [ ] J'ai comparé chaque tableau et la méthodologie au PDF source.",
        "",
    ]
    if proposal.missing:
        lines.extend(
            [
                "## ⚠️ Dépouillement incomplet",
                "",
                "Ces pages n'ont pas pu être interrogées (quota ou réseau). Les tableaux ci-dessous sont vérifiés et"
                " peuvent être fusionnés tels quels ; relancer `/mining-pr` sous l'issue pour compléter, avant ou après"
                " la fusion : les hypothèses déjà enregistrées ne sont pas reproposées.",
                "",
            ]
        )
        lines.extend(f"- {_safe(item)}" for item in proposal.missing)
        lines.append("")
    if proposal.candidates:
        lines.extend(["## Candidats à ajouter", ""])
        lines.extend(f"- `{row['candidate_id']}` — {_safe(row['complete_name'])}" for row in proposal.candidates)
        lines.append("")
    lines.extend(
        [
            "## Méthodologie",
            "",
            f"- Institut : **{_safe(method.get('institute'))}**",
            f"- Commanditaire : {_safe(method.get('commissioner'))}",
            f"- Terrain : {method.get('start')} → {method.get('end')}",
            f"- Échantillon : {method.get('sample')} ; inscrits : {method.get('registered') or 'non indiqué'}",
            f"- Population : {_safe(method.get('population'))}",
            "",
            "<details><summary>Citations méthodologiques</summary>",
            "",
            f"- Dates : {_safe(method.get('source_dates'))}",
            f"- Échantillon : {_safe(method.get('source_sample'))}",
        ]
    )
    if method.get("source_registered"):
        lines.append(f"- Inscrits : {_safe(method['source_registered'])}")
    lines.extend(["", "</details>", ""])
    lines.extend(["## Tableaux proposés", ""])
    new_hypotheses = {row["id_hypothese"] for row in proposal.hypotheses}
    for poll in proposal.polls:
        evidence = proposal.evidence.get(poll["poll_id"], {})
        marker = "nouvelle" if poll["hypothese"] in new_hypotheses else "existante"
        lines.extend(
            [
                f"### `{poll['poll_id']}` — {poll['tour']}",
                "",
                f"Hypothèse {marker} : `{poll['hypothese']}` · page {evidence.get('page', '?')}",
                "",
                "| Candidat | Intention | Citation de la notice |",
                "| --- | ---: | --- |",
            ]
        )
        for value in evidence.get("values", []):
            source = _safe(value.get("source", "")).replace("|", "\\|")
            lines.append(f"| {_safe(value.get('candidat'))} | {value.get('intentions')} | {source} |")
        lines.append("")
    if proposal.failures:
        lines.extend(["## Tableaux écartés", ""])
        lines.extend(f"- {_safe(failure)}" for failure in proposal.failures)
        lines.append("")
    model_text = ", ".join(sorted(set(models))) or "inconnu"
    lines.extend(["---", f"Modèle(s) : {model_text} · appels LLM : {calls}."])
    return "\n".join(lines) + "\n"


def _validate(root):
    _run([sys.executable, "-m", "pytest", "-q"], root)
    _run([sys.executable, "merge.py"], root)


def _existing_pr(repo, branch, root):
    """La PR ouverte de la branche, ou None.

    `gh pr view <branche>` renvoie aussi une PR fermée ou fusionnée : la
    « mettre à jour » laisserait la nouvelle proposition invisible.
    """
    completed = _run(
        ["gh", "pr", "view", branch, "--repo", repo, "--json", "number,url,state"], root, allow_failure=True
    )
    if completed.returncode:
        return None
    try:
        view = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise PullRequestError("gh pr view a renvoyé un JSON illisible") from exc
    return view if view.get("state", "OPEN") == "OPEN" else None


def _available_labels(repo, root):
    completed = _run(
        ["gh", "label", "list", "--repo", repo, "--limit", "100", "--json", "name"], root, allow_failure=True
    )
    if completed.returncode:
        return set()
    try:
        return {row["name"] for row in json.loads(completed.stdout)}
    except (json.JSONDecodeError, KeyError, TypeError):
        return set()


def _apply_labels(repo, number, root):
    available = _available_labels(repo, root)
    wanted = [label for label in ("automated", "needs-human-review") if label in available]
    if "needs-human-review" not in available and "need-screening !" in available:
        wanted.append("need-screening !")
    if wanted:
        _run(
            ["gh", "pr", "edit", str(number), "--repo", repo, *sum((["--add-label", label] for label in wanted), [])],
            root,
        )
    missing = {"automated", "needs-human-review"} - available
    if "needs-human-review" in missing and "need-screening !" in available:
        missing.remove("needs-human-review")
    return "" if not missing else "Labels absents : " + ", ".join(sorted(missing))


def create_or_update(issue, repo, proposal, root, models=(), calls=0):
    """Valide, commit, pousse et crée ou met à jour la PR brouillon de l'issue."""
    root = Path(root)
    branch = branch_name(issue)
    _validate(root)
    paths = ["candidats.csv", "hypotheses.csv", "polls.csv", *(f"polls/{poll_id}.csv" for poll_id in proposal.polls)]
    _run(["git", "add", "--", *paths], root)
    staged = _run(["git", "diff", "--cached", "--quiet"], root, allow_failure=True)
    if staged.returncode == 0:
        raise PullRequestError("aucune donnée nouvelle à committer")
    _run(["git", "config", "user.name", "github-actions[bot]"], root)
    _run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], root)
    _run(["git", "commit", "-m", f"🤖 Ajout sondage depuis l'issue #{issue}"], root)
    _run(["git", "push", "--force-with-lease", "--set-upstream", "origin", branch], root)

    content = body(issue, proposal, models, calls)
    existing = _existing_pr(repo, branch, root)
    title = f"🤖 Proposition de sondage — issue #{issue}"
    if existing:
        number, url = existing["number"], existing["url"]
        _run(["gh", "pr", "edit", str(number), "--repo", repo, "--title", title, "--body", content], root)
    else:
        created = _run(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                repo,
                "--base",
                "main",
                "--head",
                branch,
                "--draft",
                "--title",
                title,
                "--body",
                content,
            ],
            root,
        )
        url = created.stdout.strip().splitlines()[-1]
        view = _existing_pr(repo, branch, root)
        if not view:
            raise PullRequestError("la PR a été créée mais GitHub ne permet pas de la relire")
        number, url = view["number"], view["url"] or url
    warning = _apply_labels(repo, number, root)
    return PullRequest(number, url, branch, warning)
