#!/usr/bin/env python3
"""
Script to check for new presidential polls from the sondages-commission-index catalog.
Can be run locally to preview what issues would be created.
"""
import csv
import json
import sys
from pathlib import Path
from urllib.request import urlopen

CATALOG_URL = "https://raw.githubusercontent.com/MieuxVoter/sondages-commission-index/refs/heads/main/notices_catalog.csv"
CATALOG_REPO_URL = "https://github.com/MieuxVoter/sondages-commission-index"
ROOT = Path(__file__).resolve().parent
LAST_COUNT_FILE = ROOT / ".last_poll_count"


def get_last_poll_count():
    """Get the last recorded number of polls"""
    if LAST_COUNT_FILE.exists():
        return int(LAST_COUNT_FILE.read_text().strip())
    return 261  # Default starting count


def save_poll_count(count):
    """Save the current number of polls"""
    LAST_COUNT_FILE.write_text(str(count))
    print(f"📝 Updated counter to {count}")


def get_existing_polls():
    """Get list of existing poll IDs from polls.csv - DEPRECATED, kept for reference"""
    existing = set()
    polls_csv = ROOT / "polls.csv"
    if polls_csv.exists():
        with polls_csv.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                poll_id = row.get("poll_id", "").strip()
                filename = row.get("filename", "").strip()
                if poll_id:
                    existing.add(poll_id)
                if filename:
                    existing.add(filename)  # Also track by filename
    return existing


def get_catalog_polls():
    """Fetch presidential polls from the catalog"""
    print(f"📥 Fetching catalog from: {CATALOG_URL}")
    
    try:
        with urlopen(CATALOG_URL) as response:
            content = response.read().decode('utf-8')
    except Exception as e:
        print(f"❌ Error fetching catalog: {e}")
        return []
    
    polls = []
    lines = content.splitlines()
    reader = csv.DictReader(lines)
    
    for row in reader:
        category = row.get("categorie", "").strip()
        if category == "Pres":
            polls.append(row)
    
    return polls


def display_poll_summary(poll_data):
    """Display a nice summary of a poll"""
    filename = poll_data.get("filename", "Unknown")
    name = poll_data.get("name", "")
    year = poll_data.get("year", "")
    creation_date = poll_data.get("pdf creation-date", "")
    
    print(f"\n  📊 {name}")
    print(f"     Year: {year}")
    print(f"     Filename: {filename}")
    print(f"     Date: {creation_date}")


def main():
    print("=" * 70)
    print("🔍 Checking for New Presidential Polls")
    print("=" * 70)
    
    # Get last recorded count
    last_count = get_last_poll_count()
    print(f"\n📋 Last recorded poll count: {last_count}")
    
    # Get catalog polls
    catalog_polls = get_catalog_polls()
    if not catalog_polls:
        print("❌ Failed to fetch catalog or no presidential polls found.")
        return 1
    
    current_count = len(catalog_polls)
    print(f"📊 Current presidential polls in catalog: {current_count}")
    
    # Calculate new polls
    new_poll_count = current_count - last_count
    
    if new_poll_count <= 0:
        print(f"\n✅ No new polls detected!")
        print(f"   Count unchanged or decreased (was {last_count}, now {current_count})")
        return 0
    
    print(f"✨ New polls detected: {new_poll_count}")
    
    # Get the newest polls (last N polls from catalog)
    new_polls = catalog_polls[-new_poll_count:]
    
    if new_polls:
        print(f"\n{'=' * 70}")
        print(f"📝 The following {min(len(new_polls), 10)} issue(s) would be created:")
        print(f"{'=' * 70}")
        
        for i, poll in enumerate(new_polls[:10], 1):  # Show max 10
            print(f"\n{i}. ", end="")
            display_poll_summary(poll)
            filename = poll.get("filename", "")
            pdf_url = poll.get("url", "")
            print(f"     PDF URL: {pdf_url}")
            print(f"     Catalog: {CATALOG_REPO_URL}")
        
        if len(new_polls) > 10:
            print(f"\n... and {len(new_polls) - 10} more polls")
        
        print(f"\n{'=' * 70}")
        print(f"💡 To create these issues automatically:")
        print(f"   - Push to GitHub and the workflow will run daily")
        print(f"   - Or manually trigger: Actions → Check for New Presidential Polls → Run workflow")
        print(f"\n💾 Counter will be updated from {last_count} to {current_count} after issues are created")
        print(f"{'=' * 70}\n")
    
    # Show some recent catalog entries for reference
    if catalog_polls:
        print(f"\n{'=' * 70}")
        print(f"📋 Recent polls in catalog (last 5):")
        print(f"{'=' * 70}")
        for poll in catalog_polls[-5:]:
            display_poll_summary(poll)
        print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
