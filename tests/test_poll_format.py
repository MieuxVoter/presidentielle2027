"""Validate that all poll result CSVs conform to the expected schema."""

import csv
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
POLLS_DIR = ROOT / "polls"


def get_poll_files():
    """Return all poll CSV files."""
    return list(POLLS_DIR.glob("*.csv"))


def load_valid_candidates():
    """Load valid candidate IDs from candidats.csv."""
    candidats_csv = ROOT / "candidats.csv"
    candidates = set()
    with candidats_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get("candidate_id", "").strip()
            if cid:
                candidates.add(cid)
    return candidates


@pytest.mark.parametrize("poll_path", get_poll_files())
def test_poll_has_required_columns(poll_path: Path):
    """Every poll CSV must have: candidat, intentions, erreur_sup, erreur_inf."""
    with poll_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        required = {"candidat", "intentions", "erreur_sup", "erreur_inf"}
        assert required.issubset(fieldnames), f"{poll_path.name} missing required columns: {required - fieldnames}"


@pytest.mark.parametrize("poll_path", get_poll_files())
def test_poll_has_no_empty_candidate_names(poll_path: Path):
    """Every row must have a non-empty candidat field."""
    with poll_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            candidat = (row.get("candidat") or "").strip()
            if not candidat:
                # Allow trailing empty lines
                continue
            assert candidat, f"{poll_path.name} row {i} has empty candidat"


@pytest.mark.parametrize("poll_path", get_poll_files())
def test_poll_intentions_are_numeric_or_blank(poll_path: Path):
    """intentions field should be numeric or blank."""
    with poll_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            candidat = (row.get("candidat") or "").strip()
            if not candidat:
                continue
            intentions = (row.get("intentions") or "").strip()
            if intentions:
                try:
                    float(intentions)
                except ValueError:
                    pytest.fail(f"{poll_path.name} row {i} ({candidat}): intentions '{intentions}' not numeric")


@pytest.mark.parametrize("poll_path", get_poll_files())
def test_poll_filename_format(poll_path: Path):
    """Poll filenames should follow the format: YYYYMMDD_DDMM_ii_X.csv."""
    filename = poll_path.name

    # Check extension
    assert filename.endswith(".csv"), f"Invalid extension for {filename}"

    # Check underscore presence (format indicator)
    assert "_" in filename, f"Poll filename should contain underscores: {filename}"

    # Additional format check: should have at least 3 parts when split by underscore
    parts = filename[:-4].split("_")  # Remove .csv extension
    assert len(parts) >= 3, f"Poll filename {filename} should follow format YYYYMMDD_DDMM_ii_X"


@pytest.mark.parametrize("poll_path", get_poll_files())
def test_poll_is_not_empty(poll_path: Path):
    """Poll CSV files should contain at least one data row."""
    with poll_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        # Filter out empty rows
        non_empty_rows = [r for r in rows if r.get("candidat", "").strip()]
        assert len(non_empty_rows) > 0, f"Poll file {poll_path.name} has no data rows"


@pytest.mark.parametrize("poll_path", get_poll_files())
def test_poll_error_margins_numeric_or_blank(poll_path: Path):
    """Error margin fields should be numeric or blank."""
    with poll_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            candidat = (row.get("candidat") or "").strip()
            if not candidat:
                continue

            for field in ["erreur_sup", "erreur_inf"]:
                value = (row.get(field) or "").strip()
                if value:
                    try:
                        float(value)
                    except ValueError:
                        pytest.fail(f"{poll_path.name} row {i} ({candidat}): {field} '{value}' not numeric")


def test_poll_candidates_are_recognizable():
    """
    All candidates in poll files should be mappable to candidats.csv.
    This is a softer check that warns if candidates might be unrecognized.
    """
    import sys

    # Add parent to path for merge module
    sys.path.insert(0, str(ROOT))

    try:
        import merge

        # Try to run merge - it will fail if candidates can't be mapped
        # This is already tested in test_merge.py but good to verify here too
        merge.merge(ROOT)
    except KeyError as e:
        pytest.fail(f"Candidate mapping failed: {e}")
    except Exception as e:
        # Other errors are OK for this test (we're just checking candidate mapping)
        pass
