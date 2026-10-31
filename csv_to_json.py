#!/usr/bin/env python3
"""
Convert presidentielle2027.csv to presidentielle2027.json in the format used for 2022.

The JSON format groups polls by institute and poll_id, with candidates listed
for each poll including their voting intentions.

Input: presidentielle2027.csv (merged CSV file)
Output: presidentielle2027.json

This script purposefully avoids external deps (pandas) to run in CI easily.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent


SOURCE_METADATA = {
    "name": "Mieux Voter",
    "repository": "https://github.com/MieuxVoter/presidentielle2027",
    "csv": "https://raw.githubusercontent.com/MieuxVoter/presidentielle2027/refs/heads/main/presidentielle2027.csv",
    "traceability": "Chaque ligne du jeu de données est traçable jusqu’à la notice PDF d’origine publiée par la Commission des sondages.",
}


USAGE_GUIDELINES = [
    {
        "id": "source",
        "title": "Citer la source sur chaque graphique",
        "instruction": "La source du dépôt de Mieux Voter doit apparaître directement sur chaque graphique afin de rester visible en cas de capture ou de réutilisation.",
        "recommended_text": "Données : Mieux Voter — github.com/MieuxVoter/presidentielle2027",
        "additional_requirement": "Le dépôt Mieux Voter doit également être cité dans la page ou section méthodologique, et pas uniquement la Commission des sondages.",
    },
    {
        "id": "uncertainty",
        "title": "Afficher les points et l'incertitude",
        "instruction": "Ne pas présenter uniquement une courbe moyenne ou lissée. Afficher les points correspondant aux sondages et, lorsque cela est possible, un intervalle ou un couloir d'incertitude.",
        "interpretation": "Lorsque les intervalles d'incertitude de deux candidats se chevauchent, éviter de présenter leur classement comme certain.",
    },
    {
        "id": "smoothing",
        "title": "Documenter le lissage",
        "instruction": "Toute méthode de lissage utilisée doit être explicitement documentée.",
    },
    {
        "id": "population",
        "title": "Tenir compte de la population interrogée",
        "instruction": "Vérifier la population couverte par chaque sondage avant de l'intégrer à une série nationale.",
        "warning": "Certains sondages portent sur des populations spécifiques, par exemple un échantillon LGBTQIA+, et ne doivent pas être assimilés à des sondages représentatifs de la population nationale.",
        "action": "Filtrer ces sondages des agrégations nationales ou les identifier explicitement comme relevant d'une population spécifique.",
    },
    {
        "id": "hypotheses",
        "title": "Distinguer les différentes hypothèses d'un même sondage",
        "instruction": "Un même sondage peut contenir plusieurs hypothèses correspondant à différentes candidatures ou configurations de second tour.",
        "warning": "Ne pas confondre le dernier sondage publié avec la dernière hypothèse disponible dans ce sondage.",
        "action": "Identifier explicitement l'hypothèse utilisée avant toute agrégation ou comparaison temporelle.",
    },
]


CONTRIBUTION_METADATA = {
    "welcome": True,
    "repository": "https://github.com/MieuxVoter/presidentielle2027",
}


def load_csv(csv_path: Path) -> List[Dict[str, str]]:
    """Load the presidentielle2027.csv file."""
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_hypotheses(hypotheses_path: Path) -> List[Dict[str, Any]]:
    """Load hypotheses.csv and return JSON-friendly hypothesis metadata."""
    hypotheses: List[Dict[str, Any]] = []
    with hypotheses_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hypothesis_id = row.get("id_hypothese", "").strip()
            if not hypothesis_id:
                continue
            candidates = [c.strip() for c in row.get("hypothese_complete", "").split(",") if c.strip()]
            hypothesis = {
                "id": hypothesis_id,
                "candidates": candidates,
            }
            commentaire = row.get("commentaire", "").strip()
            if commentaire:
                hypothesis["comment"] = commentaire
            hypotheses.append(hypothesis)
    return hypotheses


def convert_to_int_or_float(value: str) -> int | float | None:
    """Convert a string to int or float, return None if empty or invalid."""
    if not value or not value.strip():
        return None
    try:
        # Try int first
        if "." not in value:
            return int(value)
        return float(value)
    except (ValueError, TypeError):
        return None


def csv_to_json(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Convert presidentielle2027.csv to JSON format similar to 2022.

    The structure groups data by poll, where each poll contains:
    - institut: polling institute name
    - commanditaire: poll commissioner
    - debut_enquete: start date
    - fin_enquete: end date
    - echantillon: sample size
    - population: population description
    - hypothese: hypothesis ID
    - tour: election round (1er Tour or 2nd Tour)
    - candidats: list of candidates with their results
    """
    rows = load_csv(csv_path)

    # Group rows by poll_id
    polls_dict: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"candidats": []})

    for row in rows:
        poll_id = row["poll_id"]

        # If this is the first row for this poll, set metadata
        if not polls_dict[poll_id].get("poll_id"):
            polls_dict[poll_id].update(
                {
                    "poll_id": poll_id,
                    "institut": row.get("nom_institut", ""),
                    "commanditaire": row.get("commanditaire", ""),
                    "debut_enquete": row.get("debut_enquete", ""),
                    "fin_enquete": row.get("fin_enquete", ""),
                    "echantillon": convert_to_int_or_float(row.get("echantillon", "")),
                    "population": row.get("population", ""),
                    "hypothese": row.get("hypothese", ""),
                    "tour": row.get("tour", ""),
                    "rolling": row.get("rolling", ""),
                    "media": row.get("media", ""),
                    "filename": row.get("filename", ""),
                }
            )

        # Add candidate data
        intentions = convert_to_int_or_float(row.get("intentions", ""))
        erreur_sup = convert_to_int_or_float(row.get("erreur_sup", ""))
        erreur_inf = convert_to_int_or_float(row.get("erreur_inf", ""))

        candidate_data = {
            "candidate_id": row.get("candidate_id", ""),
            "candidat": row.get("candidat", ""),
            "complete_name": row.get("complete_name", ""),
            "name": row.get("name", ""),
            "surname": row.get("surname", ""),
            "parti": row.get("parti", ""),
            "annonce_candidature": row.get("annonce_candidature", ""),
            "retrait_candidature": row.get("retrait_candidature", ""),
            "second_round": row.get("second_round", ""),
            "intentions": intentions,
        }

        # Only add error margins if they exist
        if erreur_sup is not None:
            candidate_data["erreur_sup"] = erreur_sup
        if erreur_inf is not None:
            candidate_data["erreur_inf"] = erreur_inf

        polls_dict[poll_id]["candidats"].append(candidate_data)

    # Convert to list sorted by poll_id
    polls_list = sorted(polls_dict.values(), key=lambda x: x["poll_id"])

    return polls_list


def build_json_payload(csv_path: Path, hypotheses_path: Path) -> Dict[str, Any]:
    """Build the published JSON payload with data and usage guidance."""
    return {
        "source": SOURCE_METADATA,
        "usage_guidelines": USAGE_GUIDELINES,
        "hypotheses": load_hypotheses(hypotheses_path),
        "polls": csv_to_json(csv_path),
        "contribution": CONTRIBUTION_METADATA,
    }


def main() -> int:
    """Main entry point."""
    csv_path = ROOT / "presidentielle2027.csv"
    hypotheses_path = ROOT / "hypotheses.csv"
    json_path = ROOT / "presidentielle2027.json"

    if not csv_path.exists():
        print(f"Error: {csv_path} not found", file=sys.stderr)
        return 1
    if not hypotheses_path.exists():
        print(f"Error: {hypotheses_path} not found", file=sys.stderr)
        return 1

    try:
        data = build_json_payload(csv_path, hypotheses_path)

        # Write JSON with nice formatting
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Successfully converted {csv_path} to {json_path}")
        print(f"Total polls: {len(data['polls'])}")
        print(f"Total hypotheses: {len(data['hypotheses'])}")
        return 0

    except Exception as e:
        print(f"Error converting CSV to JSON: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
