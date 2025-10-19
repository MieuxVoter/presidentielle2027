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


def load_csv(csv_path: Path) -> List[Dict[str, str]]:
    """Load the presidentielle2027.csv file."""
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


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


def main() -> int:
    """Main entry point."""
    csv_path = ROOT / "presidentielle2027.csv"
    json_path = ROOT / "presidentielle2027.json"

    if not csv_path.exists():
        print(f"Error: {csv_path} not found", file=sys.stderr)
        return 1

    try:
        data = csv_to_json(csv_path)

        # Write JSON with nice formatting
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Successfully converted {csv_path} to {json_path}")
        print(f"Total polls: {len(data)}")
        return 0

    except Exception as e:
        print(f"Error converting CSV to JSON: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
