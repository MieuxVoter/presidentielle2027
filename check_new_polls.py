#!/usr/bin/env python3
"""
Détection des nouveaux sondages présidentiels dans le catalogue
sondages-commission-index, et création des issues GitHub correspondantes.

Sans option, le script tourne en dry-run et affiche le corps exact des issues
qui seraient créées. Avec --create-issues (mode CI), il les crée réellement et
met à jour .last_poll_count.

Stdlib uniquement : aucune dépendance à installer.
"""

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from string import Template
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

CATALOG_REPO = "MieuxVoter/sondages-commission-index"
CATALOG_URL = f"https://raw.githubusercontent.com/{CATALOG_REPO}/refs/heads/main/notices_catalog.csv"
CATALOG_REPO_URL = f"https://github.com/{CATALOG_REPO}"
BLOB_BASE = f"{CATALOG_REPO_URL}/blob/main/"
RAW_BASE = f"https://raw.githubusercontent.com/{CATALOG_REPO}/main/"

ROOT = Path(__file__).resolve().parent
LAST_COUNT_FILE = ROOT / ".last_poll_count"
# Corps des issues, éditable sans toucher au code.
TEMPLATE_FILE = ROOT / "docs" / "issue_template_nouveau_sondage.md"

DEFAULT_LIMIT = 10
TIMEOUT = 15

# Marqueur invisible qui porte le nom de fichier : sert au dédoublonnage.
MARKER_RE = re.compile(r"<!-- poll-file: ([^>]+?) -->")
# Commentaire d'en-tête du template (mode d'emploi), retiré avant envoi.
TEMPLATE_HEADER_RE = re.compile(r"\A\s*<!--.*?-->\s*", re.DOTALL)
# Ancien format d'issue, encore présent dans les issues ouvertes avant ce changement.
LEGACY_MARKER_RE = re.compile(r"\*\*Fichier PDF à vérifier:\*\* `([^`]+)`")


def get_last_poll_count():
    """Get the last recorded number of polls"""
    if LAST_COUNT_FILE.exists():
        return int(LAST_COUNT_FILE.read_text().strip())
    return 261  # Default starting count


def save_poll_count(count):
    """Save the current number of polls"""
    LAST_COUNT_FILE.write_text(str(count))
    print(f"📝 Updated counter to {count}")


def get_catalog_polls():
    """Fetch presidential polls from the catalog"""
    print(f"📥 Fetching catalog from: {CATALOG_URL}")

    try:
        with urlopen(CATALOG_URL, timeout=TIMEOUT) as response:
            content = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as e:
        print(f"❌ Error fetching catalog: {e}")
        return []

    reader = csv.DictReader(content.splitlines())
    return [row for row in reader if (row.get("categorie") or "").strip() == "Pres"]


def url_exists(url):
    """Return True if the URL answers to a HEAD request"""
    try:
        with urlopen(Request(url, method="HEAD"), timeout=TIMEOUT) as response:
            return 200 <= response.status < 300
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def _mirror_url(base, path):
    """Build a URL on the catalog mirror, keeping the path separators intact"""
    return base + quote(path.strip())


def notice_links(poll_data):
    """Return (txt_url, pdf_url, source_url) for a catalog row.

    Le TXT est préféré au PDF, mais la colonne txt_path du catalogue annonce des
    fichiers qui n'existent pas toujours en amont : on ne renvoie le lien que
    si le fichier répond réellement.
    """
    pdf_path = (poll_data.get("pdf_path") or "").strip()
    txt_path = (poll_data.get("txt_path") or "").strip()
    source_url = (poll_data.get("url") or "").strip()

    if not txt_path and pdf_path.startswith("archives/"):
        txt_path = "archives_txt/" + pdf_path[len("archives/") :]
        txt_path = txt_path[: -len(".pdf")] + ".txt" if txt_path.endswith(".pdf") else ""

    txt_url = None
    if txt_path and url_exists(_mirror_url(RAW_BASE, txt_path)):
        txt_url = _mirror_url(BLOB_BASE, txt_path)

    pdf_url = _mirror_url(BLOB_BASE, pdf_path) if pdf_path else source_url

    return txt_url, pdf_url, source_url


def load_template():
    """Load the issue body template, minus its leading how-to comment"""
    body = TEMPLATE_HEADER_RE.sub("", TEMPLATE_FILE.read_text(encoding="utf-8"))
    if "-->" in body:
        # Le commentaire d'en-tête contient la séquence qui le referme : il se termine
        # trop tôt et son mode d'emploi fuirait dans les issues.
        print(f"⚠️  {TEMPLATE_FILE.name}: commentaire d'en-tête mal fermé, vérifier le rendu")
    return Template(body)


def build_issue(poll_data, repo, template=None):
    """Build the (title, body) of the issue for a catalog row"""
    filename = (poll_data.get("filename") or "Unknown").strip()
    name = (poll_data.get("name") or "").strip()
    creation_date = (poll_data.get("pdf creation-date") or "").strip()

    txt_url, pdf_url, source_url = notice_links(poll_data)

    # Les deux liens sont toujours présents ; seul le TXT peut manquer en amont,
    # auquel cas sa place est tenue par une mention explicite.
    if txt_url:
        txt_link = f"📝 **[Notice en texte]({txt_url})**"
    else:
        txt_link = "📝 _texte extrait pas encore disponible en amont_"
    pdf_link = f"📄 **[PDF]({pdf_url})**"

    template = template or load_template()
    body = template.safe_substitute(
        name=name,
        filename=filename,
        year=(poll_data.get("year") or "").strip(),
        creation_date=creation_date,
        links=f"{txt_link} · {pdf_link}",
        txt_link=txt_link,
        pdf_link=pdf_link,
        txt_url=txt_url or "",
        pdf_url=pdf_url,
        source_url=source_url,
        repo=repo,
    )

    # Ajouté hors template : le dédoublonnage en dépend.
    body = f"{body.rstrip()}\n\n<!-- poll-file: {filename} -->\n"

    return f"📊 Nouveau sondage: {name}", body


def _github_request(url, token, method="GET", payload=None):
    """Call the GitHub API and return the decoded JSON response"""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "presidentielle2027-check-new-polls",
        },
    )
    with urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def get_existing_issues(repo, token):
    """Get filenames already covered by an open issue, to avoid duplicates"""
    existing_filenames = set()
    page = 1

    while True:
        url = (
            f"https://api.github.com/repos/{repo}/issues"
            f"?state=open&labels=new-poll&per_page=100&page={page}"
        )
        issues = _github_request(url, token)
        if not issues:
            break

        for issue in issues:
            body = issue.get("body") or ""
            match = MARKER_RE.search(body) or LEGACY_MARKER_RE.search(body)
            if match:
                existing_filenames.add(match.group(1).strip())

        page += 1

    return existing_filenames


def create_issue(poll_data, repo, token, template=None):
    """Create a GitHub issue for a new poll"""
    title, body = build_issue(poll_data, repo, template)
    payload = {"title": title, "body": body, "labels": ["new-poll", "automated"]}
    return _github_request(f"https://api.github.com/repos/{repo}/issues", token, "POST", payload)


def find_new_polls(limit):
    """Return (catalog_polls, new_polls) or (polls, []) when nothing is new"""
    last_count = get_last_poll_count()
    print(f"📋 Last recorded poll count: {last_count}")

    catalog_polls = get_catalog_polls()
    if not catalog_polls:
        return [], []

    current_count = len(catalog_polls)
    print(f"📊 Current presidential polls in catalog: {current_count}")

    new_poll_count = current_count - last_count
    if new_poll_count <= 0:
        print(f"✅ No new polls detected (was {last_count}, now {current_count})")
        return catalog_polls, []

    print(f"✨ Detected {new_poll_count} new poll(s)")
    new_polls = catalog_polls[-new_poll_count:]
    if len(new_polls) > limit:
        print(f"⚠️  Limiting to the {limit} most recent poll(s)")

    return catalog_polls, new_polls


def run_dry_run(repo, limit):
    """Preview the issues that would be created"""
    catalog_polls, new_polls = find_new_polls(limit)
    if not catalog_polls:
        print("❌ Failed to fetch catalog or no presidential polls found.")
        return 1

    if not new_polls:
        return 0

    print(f"\n{'=' * 70}")
    print(f"📝 The following {min(len(new_polls), limit)} issue(s) would be created:")
    print(f"{'=' * 70}")

    template = load_template()
    for poll in new_polls[:limit]:
        title, body = build_issue(poll, repo, template)
        print(f"\n{'-' * 70}\n{title}\n{'-' * 70}\n{body}")

    print(f"{'=' * 70}")
    print("💡 To create them: workflow quotidien, ou Actions → Check for New Presidential Polls")
    print(f"💾 Counter would go from {get_last_poll_count()} to {len(catalog_polls)}")
    print(f"{'=' * 70}\n")

    return 0


def run_create_issues(repo, token, limit):
    """Create the issues for real (CI mode)"""
    catalog_polls, new_polls = find_new_polls(limit)
    if not catalog_polls:
        return 1

    if not new_polls:
        return 0

    existing_issue_filenames = get_existing_issues(repo, token)
    print(f"🎫 Found {len(existing_issue_filenames)} open issue(s) already")

    polls_to_create = [
        poll
        for poll in new_polls
        if (poll.get("filename") or "").strip()
        and (poll.get("filename") or "").strip() not in existing_issue_filenames
    ]
    print(f"📝 Will create {len(polls_to_create[:limit])} new issue(s)")

    template = load_template()
    created_count = 0
    for poll in polls_to_create[:limit]:
        try:
            issue = create_issue(poll, repo, token, template)
            print(f"✅ Created issue #{issue['number']}: {issue['title']}")
            created_count += 1
        except Exception as e:  # noqa: BLE001 - on veut continuer sur les autres sondages
            print(f"❌ Failed to create issue for {poll.get('filename')}: {e}")

    if created_count > 0:
        save_poll_count(len(catalog_polls))

    print(f"\n📊 Summary:")
    print(f"  - Current count: {len(catalog_polls)}")
    print(f"  - New polls: {len(new_polls)}")
    print(f"  - Issues created: {created_count}")

    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--create-issues",
        action="store_true",
        help="créer réellement les issues GitHub (mode CI, nécessite GITHUB_TOKEN)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"nombre maximum d'issues par exécution (défaut: {DEFAULT_LIMIT})",
    )
    args = parser.parse_args(argv)

    print("=" * 70)
    print("🔍 Checking for New Presidential Polls")
    print("=" * 70)

    repo = os.environ.get("GITHUB_REPOSITORY", "MieuxVoter/presidentielle2027")

    if not args.create_issues:
        return run_dry_run(repo, args.limit)

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN is required with --create-issues")
        return 1

    return run_create_issues(repo, token, args.limit)


if __name__ == "__main__":
    sys.exit(main())
