#!/usr/bin/env python3
"""Update the poll count badge in README.md"""

from pathlib import Path
import re


def count_polls(polls_dir: Path) -> int:
    """Count the number of poll CSV files."""
    return len(list(polls_dir.glob("*.csv")))


def update_readme_badge(readme_path: Path, count: int) -> bool:
    """Update the poll count in the README badge.
    
    Returns True if the file was modified, False otherwise.
    """
    content = readme_path.read_text(encoding="utf-8")
    
    # Pattern to match the badge
    pattern = r'!\[Sondages agrégés\]\(https://img\.shields\.io/badge/sondages_agrégés-\d+-blue\)'
    replacement = f'![Sondages agrégés](https://img.shields.io/badge/sondages_agrégés-{count}-blue)'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        readme_path.write_text(new_content, encoding="utf-8")
        return True
    return False


def main():
    root = Path(__file__).parent
    polls_dir = root / "polls"
    readme_path = root / "README.md"
    
    if not polls_dir.exists():
        print(f"❌ Polls directory not found: {polls_dir}")
        return 1
    
    if not readme_path.exists():
        print(f"❌ README.md not found: {readme_path}")
        return 1
    
    count = count_polls(polls_dir)
    print(f"📊 Found {count} poll(s) in {polls_dir}")
    
    modified = update_readme_badge(readme_path, count)
    
    if modified:
        print(f"✅ Updated badge in README.md to {count} sondages")
    else:
        print(f"ℹ️  Badge already up to date ({count} sondages)")
    
    return 0


if __name__ == "__main__":
    exit(main())
