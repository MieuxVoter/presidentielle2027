"""Validate core file structure and encoding."""

import csv
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

# Core files that must exist
REQUIRED_FILES = [
    "candidats.csv",
    "hypotheses.csv",
    "polls.csv",
    "merge.py",
]


@pytest.mark.parametrize("filename", REQUIRED_FILES)
def test_required_files_exist(filename):
    """Core project files must exist."""
    file_path = ROOT / filename
    assert file_path.exists(), f"Required file missing: {filename}"


@pytest.mark.parametrize("filename", ["candidats.csv", "hypotheses.csv", "polls.csv"])
def test_csv_files_utf8_encoding(filename):
    """All CSV files must be UTF-8 encoded."""
    file_path = ROOT / filename
    try:
        with file_path.open("r", encoding="utf-8") as f:
            f.read()
    except UnicodeDecodeError as e:
        pytest.fail(f"File {filename} is not UTF-8 encoded: {e}")


@pytest.mark.parametrize("filename", ["candidats.csv", "hypotheses.csv", "polls.csv"])
def test_csv_files_valid_structure(filename):
    """All CSV files must be valid and parseable."""
    file_path = ROOT / filename
    with file_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames, f"{filename} has no header row"
        # Try to read at least one row to ensure it's valid
        try:
            rows = list(reader)
        except csv.Error as e:
            pytest.fail(f"{filename} has invalid CSV structure: {e}")


def test_polls_directory_exists():
    """The polls/ directory must exist."""
    polls_dir = ROOT / "polls"
    assert polls_dir.exists(), "polls/ directory is missing"
    assert polls_dir.is_dir(), "polls/ exists but is not a directory"


def test_polls_directory_contains_csv_files():
    """The polls/ directory must contain at least one CSV file."""
    polls_dir = ROOT / "polls"
    csv_files = list(polls_dir.glob("*.csv"))
    assert len(csv_files) > 0, "polls/ directory contains no CSV files"


@pytest.mark.parametrize("poll_path", list((ROOT / "polls").glob("*.csv")))
def test_poll_files_utf8_encoding(poll_path):
    """All poll CSV files must be UTF-8 encoded."""
    try:
        with poll_path.open("r", encoding="utf-8") as f:
            f.read()
    except UnicodeDecodeError as e:
        pytest.fail(f"Poll file {poll_path.name} is not UTF-8 encoded: {e}")


def test_merge_script_is_executable():
    """The merge.py script should be a valid Python file."""
    merge_path = ROOT / "merge.py"
    assert merge_path.exists()

    # Try to compile it (syntax check)
    with merge_path.open("r", encoding="utf-8") as f:
        code = f.read()
    try:
        compile(code, "merge.py", "exec")
    except SyntaxError as e:
        pytest.fail(f"merge.py has syntax errors: {e}")


def test_tests_directory_exists():
    """The tests/ directory must exist."""
    tests_dir = ROOT / "tests"
    assert tests_dir.exists(), "tests/ directory is missing"
    assert tests_dir.is_dir(), "tests/ exists but is not a directory"


def test_readme_exists():
    """README.md must exist."""
    readme = ROOT / "README.md"
    assert readme.exists(), "README.md is missing"


def test_license_exists():
    """LICENSE file should exist."""
    license_file = ROOT / "LICENSE"
    if not license_file.exists():
        pytest.skip("LICENSE file not present (optional)")
    # If it exists, verify it's readable
    with license_file.open("r", encoding="utf-8") as f:
        content = f.read()
        assert len(content) > 0, "LICENSE file is empty"


def test_github_workflows_exist():
    """GitHub Actions workflows should exist."""
    workflows_dir = ROOT / ".github" / "workflows"
    if not workflows_dir.exists():
        pytest.skip("No .github/workflows directory (optional for local dev)")

    yml_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    assert len(yml_files) > 0, ".github/workflows exists but has no workflow files"


def test_no_duplicate_column_names_in_csvs():
    """CSV files should not have duplicate column names."""
    for csv_file in ["candidats.csv", "hypotheses.csv", "polls.csv"]:
        file_path = ROOT / csv_file
        with file_path.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            seen = set()
            duplicates = []
            for col in header:
                if col in seen:
                    duplicates.append(col)
                seen.add(col)
            assert not duplicates, f"{csv_file} has duplicate columns: {duplicates}"
