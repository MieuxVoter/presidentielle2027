#!/usr/bin/env python3
"""Quick verification script to check repository health."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check_file_exists(path: Path, name: str) -> bool:
    """Check if a file exists."""
    if path.exists():
        print(f"✅ {name} exists")
        return True
    else:
        print(f"❌ {name} missing")
        return False


def main() -> int:
    print("🔍 Checking presidentielle2027 repository health...\n")

    all_ok = True

    # Check core data files
    all_ok &= check_file_exists(ROOT / "candidats.csv", "candidats.csv")
    all_ok &= check_file_exists(ROOT / "hypotheses.csv", "hypotheses.csv")
    all_ok &= check_file_exists(ROOT / "polls.csv", "polls.csv")
    all_ok &= check_file_exists(ROOT / "merge.py", "merge.py")

    # Check directories
    polls_dir = ROOT / "polls"
    if polls_dir.is_dir():
        poll_files = list(polls_dir.glob("*.csv"))
        print(f"✅ polls/ directory exists with {len(poll_files)} CSV files")
    else:
        print("❌ polls/ directory missing")
        all_ok = False

    # Check tests
    tests_dir = ROOT / "tests"
    if tests_dir.is_dir():
        test_files = list(tests_dir.glob("test_*.py"))
        print(f"✅ tests/ directory exists with {len(test_files)} test files")
    else:
        print("❌ tests/ directory missing")
        all_ok = False

    # Check GitHub Actions
    workflows_dir = ROOT / ".github" / "workflows"
    if workflows_dir.is_dir():
        workflow_files = list(workflows_dir.glob("*.yml"))
        print(f"✅ .github/workflows/ exists with {len(workflow_files)} workflows")
    else:
        print("❌ .github/workflows/ missing")
        all_ok = False

    # Check if merge output exists
    merged = ROOT / "presidentielle2027.csv"
    if merged.exists():
        with merged.open("r") as f:
            lines = sum(1 for _ in f)
        print(f"✅ presidentielle2027.csv exists with {lines} rows (including header)")
    else:
        print("⚠️  presidentielle2027.csv not generated yet (run: python merge.py)")

    print("\n" + "=" * 60)
    if all_ok:
        print("✅ Repository structure is healthy!")
        print("\nNext steps:")
        print("  1. Run tests: pytest")
        print("  2. Generate merged CSV: python merge.py")
        print("  3. Add a new poll: see COMMENT_AJOUTER_UN_SONDAGE.md")
        return 0
    else:
        print("❌ Some files are missing. Please check the structure.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
