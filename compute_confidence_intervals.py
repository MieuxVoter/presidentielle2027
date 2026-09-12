"""
Calcule la marge d'erreur (intervalle de confiance à 95 %) de chaque sondage
et la réécrit dans polls/<poll_id>.csv.

Entrées:
- polls.csv: métadonnées des sondages, dont les tailles d'échantillon
- polls/<poll_id>.csv: colonnes candidat,intentions,erreur_sup,erreur_inf

Sortie: polls/<poll_id>.csv réécrit avec erreur_sup et erreur_inf renseignées.

La base de calcul retenue est la première sous-population déclarée, dans l'ordre
sous_echantillon3, sous_echantillon2, sous_echantillon1.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from merge import iter_polls_meta, read_poll_results

ROOT = Path(__file__).resolve().parent
FOLDER = ROOT / "polls"
POLL_CSV = ROOT / "polls.csv"

SAMPLE_COLS = ["sous_echantillon3", "sous_echantillon2", "sous_echantillon1"]
OUTPUT_COLS = ["candidat", "intentions", "erreur_sup", "erreur_inf"]
Z_95 = 1.96


def confidence_margin(intentions: float, sample: float, z: float = Z_95) -> Tuple[float, float]:
    """Retourne (borne basse, borne haute) de l'intervalle de confiance.

    Args:
        intentions: score du candidat, en pourcentage.
        sample: taille de la base de calcul.
        z: valeur critique pour le niveau de confiance.

    Returns:
        tuple: (erreur_inf, erreur_sup).
    """
    proportion = intentions / 100
    margin_of_error = z * (proportion * (1 - proportion) / sample) ** 0.5

    # Un candidat ne peut pas perdre plus que son propre score: la borne basse
    # est bridée quand la marge dépasse le score.
    lower = round(-margin_of_error * 100, 2) if proportion > margin_of_error else proportion
    return lower, round(margin_of_error * 100, 2)


def resolve_sample(meta_row: dict, previous: Optional[float] = None) -> Optional[float]:
    """Retourne la base de calcul d'un sondage: sa première sous-population déclarée.

    `previous` est renvoyé quand le sondage n'en déclare aucune.
    """
    for col in SAMPLE_COLS:
        value = (meta_row.get(col) or "").strip()
        if value:
            return float(value)
    return previous


def format_number(value: float) -> str:
    """Formate une marge pour le CSV, en laissant la cellule vide si elle est indéfinie."""
    if value is None or value != value:  # NaN
        return ""
    return str(value)


def write_poll_results(path: Path, rows: List[dict]) -> None:
    """Réécrit un fichier de résultats avec les colonnes dans l'ordre attendu."""
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in OUTPUT_COLS})


def main() -> int:
    sample: Optional[float] = None

    for meta_row in iter_polls_meta(POLL_CSV):
        poll_id = (meta_row.get("poll_id") or "").strip()
        poll_path = FOLDER / f"{poll_id}.csv"
        if not poll_path.exists():
            continue

        sample = resolve_sample(meta_row, sample)
        if sample is None:
            continue

        try:
            rows = read_poll_results(poll_path)
            for row in rows:
                intentions = (row.get("intentions") or "").strip()
                if not intentions:
                    row["erreur_inf"] = ""
                    row["erreur_sup"] = ""
                    continue
                lower, upper = confidence_margin(float(intentions), sample)
                row["erreur_inf"] = format_number(lower)
                row["erreur_sup"] = format_number(upper)

            write_poll_results(poll_path, rows)
        except Exception as e:
            print(f"Erreur pour le sondage {poll_id} : {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
