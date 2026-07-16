#!/usr/bin/env python3
"""Update the TOP 3 des hypothèses les plus évaluées section in README.md.

Compte le nombre de sondages de 1er tour associés à chaque hypothèse (colonne
`hypothese` de polls.csv), croise avec la liste des candidats de hypotheses.csv,
et met à jour le tableau du classement entre les marqueurs TOP_HYPOTHESES dans
README.md. La description liste tous les candidats par ordre alphabétique.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

TOP_N = 3
START_MARKER = "<!-- TOP_HYPOTHESES:START -->"
END_MARKER = "<!-- TOP_HYPOTHESES:END -->"


FIRST_ROUND = "1er tour"


def count_polls_per_hypothesis(polls_path: Path) -> Counter:
    """Compte les sondages de 1er tour pour chaque identifiant d'hypothèse."""
    counter: Counter = Counter()
    with polls_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("tour") or "").strip().lower() != FIRST_ROUND:
                continue
            hyp = (row.get("hypothese") or "").strip()
            if hyp:
                counter[hyp] += 1
    return counter


def load_candidates_by_hypothesis(hypotheses_path: Path) -> dict[str, list[str]]:
    """Retourne un mapping id_hypothese -> liste des candidats (triés alpha.)."""
    candidates_by_id: dict[str, list[str]] = {}
    with hypotheses_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            hyp_id = (row.get("id_hypothese") or "").strip()
            if not hyp_id:
                continue
            candidates = [
                name.strip()
                for name in (row.get("hypothese_complete") or "").split(",")
                if name.strip()
            ]
            candidates_by_id[hyp_id] = sorted(candidates, key=str.casefold)
    return candidates_by_id


def _colored(name: str, color: str) -> str:
    """Nom coloré via la syntaxe mathématique GitHub (seule à rendre la couleur)."""
    return f"$\\textcolor{{{color}}}{{\\text{{{name}}}}}$"


def _diff_cell(reference: list[str], current: list[str]) -> str:
    """Diff vs référence : ajouts en vert (+), retraits en rouge (−)."""
    ref_set, cur_set = set(reference), set(current)
    added = sorted(cur_set - ref_set, key=str.casefold)
    removed = sorted(ref_set - cur_set, key=str.casefold)
    parts = [_colored(f"+ {name}", "green") for name in added]
    parts += [_colored(f"− {name}", "red") for name in removed]
    return ", ".join(parts) if parts else "_(candidats identiques au 🥇)_"


def build_table(
    counter: Counter, candidates_by_id: dict[str, list[str]], top_n: int = TOP_N
) -> str:
    """Construit le tableau markdown du TOP N des hypothèses les plus évaluées."""
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        "| Rang | Sondages | Candidats (🥇) / Diff vs 🥇 (🥈🥉) |",
        "|:----:|:--------:|----------------------------------|",
    ]
    # Tri par nombre de sondages décroissant, puis par identifiant pour la stabilité.
    ranking = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
    reference: list[str] = []
    for i, (hyp_id, count) in enumerate(ranking):
        rank = medals[i] if i < len(medals) else str(i + 1)
        candidates = candidates_by_id.get(hyp_id, [])
        if i == 0:
            reference = candidates
            cell = ", ".join(candidates) if candidates else "—"
        else:
            cell = _diff_cell(reference, candidates)
        lines.append(f"| {rank} | {count} | {cell} |")
    lines.append("")
    lines.append(
        "> 🥇 liste complète des candidats (référence). "
        "🥈🥉 diff vs 🥇 : "
        f"{_colored('+ ajouté', 'green')} en vert, "
        f"{_colored('− retiré', 'red')} en rouge."
    )
    return "\n".join(lines)


def update_readme(readme_path: Path, table: str) -> bool:
    """Remplace le contenu entre les marqueurs. Retourne True si modifié."""
    content = readme_path.read_text(encoding="utf-8")

    if START_MARKER not in content or END_MARKER not in content:
        raise ValueError(
            f"Marqueurs {START_MARKER} / {END_MARKER} introuvables dans README.md"
        )

    before, rest = content.split(START_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)

    new_content = f"{before}{START_MARKER}\n{table}\n{END_MARKER}{after}"

    if new_content != content:
        readme_path.write_text(new_content, encoding="utf-8")
        return True
    return False


def main() -> int:
    root = Path(__file__).parent
    polls_path = root / "polls.csv"
    hypotheses_path = root / "hypotheses.csv"
    readme_path = root / "README.md"

    for path in (polls_path, hypotheses_path, readme_path):
        if not path.exists():
            print(f"❌ Fichier introuvable : {path}")
            return 1

    counter = count_polls_per_hypothesis(polls_path)
    if not counter:
        print("❌ Aucune hypothèse trouvée dans polls.csv")
        return 1

    candidates_by_id = load_candidates_by_hypothesis(hypotheses_path)
    table = build_table(counter, candidates_by_id)

    modified = update_readme(readme_path, table)

    if modified:
        print("✅ Classement TOP 3 des hypothèses mis à jour dans README.md")
    else:
        print("ℹ️  Classement TOP 3 déjà à jour")

    return 0


if __name__ == "__main__":
    exit(main())
