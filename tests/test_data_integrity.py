"""Validate integrity of metadata CSVs and cross-references."""

import csv
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_polls_csv_references_existing_files():
    """Each poll_id in polls.csv should have a corresponding CSV file."""
    polls_csv = ROOT / "polls.csv"
    polls_dir = ROOT / "polls"

    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            poll_id = row.get("poll_id", "").strip()
            if not poll_id:
                continue
            poll_file = polls_dir / f"{poll_id}.csv"
            assert poll_file.exists(), f"Missing poll file for {poll_id}: {poll_file.name}"


def test_polls_csv_has_unique_poll_ids():
    """poll_id should be unique in polls.csv."""
    polls_csv = ROOT / "polls.csv"
    seen = set()

    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            poll_id = row.get("poll_id", "").strip()
            if not poll_id:
                continue
            assert poll_id not in seen, f"Duplicate poll_id: {poll_id}"
            seen.add(poll_id)


def test_hypotheses_csv_well_formed():
    """hypotheses.csv must have id_hypothese and hypothese_complete."""
    hypotheses_csv = ROOT / "hypotheses.csv"
    with hypotheses_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"id_hypothese", "hypothese_complete"}
        assert required.issubset(set(reader.fieldnames or [])), f"hypotheses.csv missing columns: {required}"
        rows = list(reader)
        assert len(rows) > 0, "hypotheses.csv is empty"


def test_hypotheses_csv_has_unique_ids():
    """Hypothesis IDs should be unique in hypotheses.csv."""
    hypotheses_csv = ROOT / "hypotheses.csv"
    seen = set()

    with hypotheses_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hid = row.get("id_hypothese", "").strip()
            if not hid:
                continue
            assert hid not in seen, f"Duplicate id_hypothese: {hid}"
            seen.add(hid)


def test_candidats_csv_has_unique_ids():
    """candidate_id should be unique in candidats.csv."""
    candidats_csv = ROOT / "candidats.csv"
    seen = set()

    with candidats_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get("candidate_id", "").strip()
            if not cid:
                continue
            assert cid not in seen, f"Duplicate candidate_id: {cid}"
            seen.add(cid)


def test_candidats_csv_has_required_columns():
    """candidats.csv must have all required columns."""
    candidats_csv = ROOT / "candidats.csv"
    required = {"candidate_id", "complete_name", "name", "surname", "parti"}

    with candidats_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        assert required.issubset(fieldnames), f"candidats.csv missing columns: {required - fieldnames}"


def test_polls_csv_has_required_columns():
    """polls.csv must have all required columns."""
    polls_csv = ROOT / "polls.csv"
    required = {
        "poll_id",
        "hypothese",
        "nom_institut",
        "commanditaire",
        "debut_enquete",
        "fin_enquete",
        "echantillon",
        "population",
        "tour",
    }

    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        assert required.issubset(fieldnames), f"polls.csv missing columns: {required - fieldnames}"


def test_all_poll_files_referenced_in_metadata():
    """Every CSV file in polls/ should have metadata in polls.csv."""
    polls_csv = ROOT / "polls.csv"
    polls_dir = ROOT / "polls"

    # Load all poll_ids from metadata
    poll_ids_in_metadata = set()
    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            poll_id = row.get("poll_id", "").strip()
            if poll_id:
                poll_ids_in_metadata.add(poll_id)

    # Check all CSV files in polls/
    for poll_file in polls_dir.glob("*.csv"):
        poll_id = poll_file.stem
        assert poll_id in poll_ids_in_metadata, f"Poll file {poll_file.name} has no metadata entry in polls.csv"


def test_hypothesis_references_in_polls_are_valid():
    """All hypothesis IDs in polls.csv should exist in hypotheses.csv."""
    hypotheses_csv = ROOT / "hypotheses.csv"
    polls_csv = ROOT / "polls.csv"

    # Load valid hypothesis IDs
    valid_hypotheses = set()
    with hypotheses_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hid = row.get("id_hypothese", "").strip()
            if hid:
                valid_hypotheses.add(hid)

    # Check all hypothesis references in polls.csv
    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hyp = row.get("hypothese", "").strip()
            if hyp:
                assert hyp in valid_hypotheses, f"Poll {row.get('poll_id')} references unknown hypothesis: {hyp}"


def test_hypotheses_have_no_duplicates():
    """Each hypothesis should have a unique set of candidates (no redundant hypotheses)."""
    hypotheses_csv = ROOT / "hypotheses.csv"
    
    # Map normalized candidate sets to hypothesis IDs
    candidate_sets = {}
    
    with hypotheses_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hid = row.get("id_hypothese", "").strip()
            candidates_str = row.get("hypothese_complete", "").strip()
            
            if not hid or not candidates_str:
                continue
            
            # Normalize: split by comma, strip whitespace, sort alphabetically, ignore empty strings
            candidates = [c.strip() for c in candidates_str.split(",") if c.strip()]
            candidates_normalized = tuple(sorted(c.lower() for c in candidates))
            
            if candidates_normalized in candidate_sets:
                existing_hid = candidate_sets[candidates_normalized]
                pytest.fail(
                    f"Redundant hypothesis detected:\n"
                    f"  {hid} and {existing_hid} have the same candidates:\n"
                    f"  {', '.join(sorted(candidates))}\n"
                    f"  Consider removing one of these hypotheses or verifying the data."
                )
            
            candidate_sets[candidates_normalized] = hid


def test_poll_candidates_match_declared_hypothesis():
    """Verify that candidates in each poll file match the declared hypothesis."""
    import unicodedata
    
    def normalize_name(name: str) -> str:
        """Normalize candidate name for comparison (same logic as merge.py)."""
        # NFD decomposition + filter combining marks
        nfd = unicodedata.normalize("NFD", name.strip().lower())
        return "".join(c for c in nfd if not unicodedata.combining(c))
    
    hypotheses_csv = ROOT / "hypotheses.csv"
    polls_csv = ROOT / "polls.csv"
    polls_dir = ROOT / "polls"
    
    # Load hypotheses: map id -> set of normalized candidate names
    hypotheses = {}
    with hypotheses_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hid = row.get("id_hypothese", "").strip()
            candidates_str = row.get("hypothese_complete", "").strip()
            if not hid or not candidates_str:
                continue
            
            candidates = [c.strip() for c in candidates_str.split(",") if c.strip()]
            hypotheses[hid] = set(normalize_name(c) for c in candidates)
    
    # Check each poll
    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            poll_id = row.get("poll_id", "").strip()
            declared_hyp = row.get("hypothese", "").strip()
            
            if not poll_id or not declared_hyp:
                continue
            
            # Read candidates from poll file
            poll_file = polls_dir / f"{poll_id}.csv"
            if not poll_file.exists():
                continue  # This is checked by another test
            
            poll_candidates = set()
            with poll_file.open("r", encoding="utf-8") as pf:
                poll_reader = csv.DictReader(pf)
                for poll_row in poll_reader:
                    candidat = poll_row.get("candidat", "").strip()
                    if candidat:
                        poll_candidates.add(normalize_name(candidat))
            
            # Get expected candidates from hypothesis
            if declared_hyp not in hypotheses:
                pytest.fail(f"Poll {poll_id} references unknown hypothesis: {declared_hyp}")
            
            expected_candidates = hypotheses[declared_hyp]
            
            # Compare
            if poll_candidates != expected_candidates:
                missing = expected_candidates - poll_candidates
                extra = poll_candidates - expected_candidates
                
                error_msg = [
                    f"\nPoll {poll_id} candidates don't match hypothesis {declared_hyp}:",
                ]
                
                if missing:
                    # Find original names from hypothesis for better error message
                    with hypotheses_csv.open("r", encoding="utf-8") as hf:
                        reader = csv.DictReader(hf)
                        for hrow in reader:
                            if hrow.get("id_hypothese", "").strip() == declared_hyp:
                                candidates_list = [c.strip() for c in hrow.get("hypothese_complete", "").split(",") if c.strip()]
                                missing_names = [c for c in candidates_list if normalize_name(c) in missing]
                                error_msg.append(f"  Missing in poll file: {missing_names}")
                                break
                
                if extra:
                    # Find original names from poll file
                    with poll_file.open("r", encoding="utf-8") as pf:
                        poll_reader = csv.DictReader(pf)
                        extra_names = [poll_row.get("candidat", "").strip() 
                                      for poll_row in poll_reader 
                                      if normalize_name(poll_row.get("candidat", "").strip()) in extra]
                        error_msg.append(f"  Extra in poll file: {extra_names}")
                
                error_msg.append(f"  → Check if hypothesis {declared_hyp} is correct for this poll")
                pytest.fail("\n".join(error_msg))
