#!/usr/bin/env python3
"""
Test the CSV to JSON conversion script.
"""
import json
from pathlib import Path
from csv_to_json import csv_to_json, convert_to_int_or_float

import pytest


ROOT = Path(__file__).resolve().parent.parent


def test_json_conversion_runs():
    """Test that JSON conversion runs without errors."""
    csv_path = ROOT / "presidentielle2027.csv"
    if not csv_path.exists():
        pytest.skip("presidentielle2027.csv not found")

    data = csv_to_json(csv_path)
    assert isinstance(data, list)
    assert len(data) > 0


def test_json_file_exists():
    """Test that presidentielle2027.json exists."""
    json_path = ROOT / "presidentielle2027.json"
    assert json_path.exists(), "presidentielle2027.json should exist"


def test_json_structure_valid():
    """Test that the JSON file has valid structure."""
    json_path = ROOT / "presidentielle2027.json"
    if not json_path.exists():
        pytest.skip("presidentielle2027.json not found")

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list), "JSON should be a list of polls"

    # Check first poll structure
    if len(data) > 0:
        poll = data[0]
        required_keys = {
            "poll_id",
            "institut",
            "commanditaire",
            "debut_enquete",
            "fin_enquete",
            "echantillon",
            "population",
            "hypothese",
            "tour",
            "candidats",
        }
        assert required_keys.issubset(poll.keys()), f"Poll missing required keys: {required_keys - set(poll.keys())}"

        # Check candidats structure
        assert isinstance(poll["candidats"], list), "candidats should be a list"
        if len(poll["candidats"]) > 0:
            candidat = poll["candidats"][0]
            candidat_required = {"candidate_id", "candidat", "complete_name", "name", "surname", "parti", "intentions"}
            assert candidat_required.issubset(
                candidat.keys()
            ), f"Candidat missing keys: {candidat_required - set(candidat.keys())}"


def test_json_poll_count_matches_csv():
    """Test that JSON has same number of polls as CSV."""
    csv_path = ROOT / "presidentielle2027.csv"
    json_path = ROOT / "presidentielle2027.json"

    if not csv_path.exists() or not json_path.exists():
        pytest.skip("CSV or JSON file not found")

    # Count unique poll_ids in CSV
    import csv

    poll_ids = set()
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            poll_ids.add(row["poll_id"])

    # Count polls in JSON
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == len(poll_ids), f"JSON has {len(data)} polls but CSV has {len(poll_ids)} unique poll_ids"


def test_convert_to_int_or_float():
    """Test the convert_to_int_or_float function."""
    assert convert_to_int_or_float("123") == 123
    assert convert_to_int_or_float("123.45") == 123.45
    assert convert_to_int_or_float("") is None
    assert convert_to_int_or_float("   ") is None
    assert convert_to_int_or_float("invalid") is None


def test_json_intentions_are_numeric():
    """Test that intentions in JSON are numeric (int or float) or None."""
    json_path = ROOT / "presidentielle2027.json"
    if not json_path.exists():
        pytest.skip("presidentielle2027.json not found")

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    for poll in data:
        for candidat in poll["candidats"]:
            intentions = candidat.get("intentions")
            assert intentions is None or isinstance(
                intentions, (int, float)
            ), f"intentions should be int, float, or None, got {type(intentions)}: {intentions}"


def test_json_echantillon_is_numeric():
    """Test that echantillon in JSON is numeric or None."""
    json_path = ROOT / "presidentielle2027.json"
    if not json_path.exists():
        pytest.skip("presidentielle2027.json not found")

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    for poll in data:
        echantillon = poll.get("echantillon")
        assert echantillon is None or isinstance(
            echantillon, (int, float)
        ), f"echantillon should be int, float, or None, got {type(echantillon)}: {echantillon}"
