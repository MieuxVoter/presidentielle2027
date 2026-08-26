#!/usr/bin/env python3
"""
Recompute the margin of error of every poll in polls/ from its sample size.

For each poll, the margin is derived from the narrowest sub-sample the institute
declared, since that is the base the published percentages are computed on:
sous_echantillon3, then 2, then 1, and finally echantillon.

Like merge.py, this script avoids external dependencies so it can run in CI
without an install step.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import List, Optional, Tuple


ROOT = Path(__file__).resolve().parent
POLLS_DIR = ROOT / "polls"
POLLS_CSV = ROOT / "polls.csv"

# Narrowest base first: the published shares are percentages of that sub-sample.
SAMPLE_COLS = ("sous_echantillon3", "sous_echantillon2", "sous_echantillon1", "echantillon")

Z_95 = 1.96
RESULT_COLS = ["candidat", "intentions", "erreur_sup", "erreur_inf"]


def confidence_margin(share_pct: float, sample: int, z: float = Z_95) -> Tuple[float, float]:
    """Return (erreur_sup, erreur_inf) in percentage points for a published share.

    The lower margin is clamped so that share + erreur_inf never goes below 0:
    a candidate polling at 0.5% cannot lose more than 0.5 points.
    """
    if sample <= 0:
        raise ValueError(f"sample must be positive, got {sample}")

    proportion = share_pct / 100
    standard_error = (proportion * (1 - proportion) / sample) ** 0.5
    margin = z * standard_error

    return round(margin * 100, 2), -round(min(margin, proportion) * 100, 2)


def resolve_sample(meta: dict) -> Optional[int]:
    """Return the sample size the published shares are based on, or None."""
    for column in SAMPLE_COLS:
        raw = (meta.get(column) or "").strip()
        if not raw:
            continue
        try:
            sample = int(float(raw))
        except ValueError:
            continue
        if sample > 0:
            return sample
    return None


def load_polls_metadata(polls_csv: Path = POLLS_CSV) -> List[dict]:
    with polls_csv.open("r", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if (row.get("poll_id") or "").strip()]


def annotate_poll_file(path: Path, sample: int) -> bool:
    """Rewrite a poll result file with recomputed margins. Return True if it changed."""
    with path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    before = path.read_bytes()
    output: List[dict] = []
    for row in rows:
        candidat = (row.get("candidat") or "").strip()
        if not candidat:
            continue
        raw_share = (row.get("intentions") or "").strip()
        if raw_share:
            erreur_sup, erreur_inf = confidence_margin(float(raw_share), sample)
        else:
            erreur_sup, erreur_inf = "", ""
        # Keep candidat and intentions verbatim: this script owns the margins only.
        output.append(
            {
                "candidat": row.get("candidat", ""),
                "intentions": row.get("intentions", ""),
                "erreur_sup": erreur_sup,
                "erreur_inf": erreur_inf,
            }
        )

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_COLS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)

    return path.read_bytes() != before


def main(argv: List[str]) -> int:
    changed = 0
    skipped = []

    for meta in load_polls_metadata():
        poll_id = meta["poll_id"].strip()
        path = POLLS_DIR / f"{poll_id}.csv"
        if not path.exists():
            skipped.append(f"{poll_id}: no result file")
            continue

        sample = resolve_sample(meta)
        if sample is None:
            skipped.append(f"{poll_id}: no usable sample size")
            continue

        try:
            if annotate_poll_file(path, sample):
                changed += 1
        except ValueError as e:
            skipped.append(f"{poll_id}: {e}")

    for message in skipped:
        print(f"⚠️  {message}")
    print(f"Recomputed margins, {changed} file(s) updated")
    return 1 if skipped else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
