#!/usr/bin/env python3
"""Triage des notices de sondage : y a-t-il des intentions de vote ?

Sans option de publication, le script tourne en dry-run et affiche le commentaire
exact qui serait publié. Avec --post (mode CI), il le publie sous l'issue et pose
le label correspondant.

    python mine_poll.py --issue 42            # aperçu
    python mine_poll.py --issue 42 --post     # publie (nécessite GITHUB_TOKEN)
    python mine_poll.py --txt notice.txt      # depuis un texte local
    python mine_poll.py --pdf notice.pdf      # depuis un PDF local (pdfplumber)

Stdlib uniquement, sauf --pdf qui importe pdfplumber à la demande.
"""

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote

# Réutilise le catalogue et le client HTTP GitHub déjà écrits pour les issues.
from check_new_polls import BLOB_BASE, MARKER_RE, RAW_BASE, _github_request, get_catalog_polls, notice_links
from mining import client as llm
from mining import notice, render, steps

DEFAULT_MAX_CALLS = 40


def issue_poll_filename(repo, number, token):
    """Le nom de fichier de la notice, lu dans le marqueur du corps de l'issue."""
    issue = _github_request(f"https://api.github.com/repos/{repo}/issues/{number}", token)
    match = MARKER_RE.search(issue.get("body") or "")
    if not match:
        raise SystemExit(f"❌ Issue #{number} : marqueur <!-- poll-file: … --> absent")
    return match.group(1).strip()


def notice_text_for(filename):
    """Le texte de la notice : TXT amont si disponible, sinon échec explicite."""
    rows = [r for r in get_catalog_polls() if (r.get("filename") or "").strip() == filename]
    if not rows:
        raise SystemExit(f"❌ {filename} : introuvable dans le catalogue amont")
    txt_url, _pdf_url, _source = notice_links(rows[0])
    if not txt_url:
        raise SystemExit(
            f"❌ {filename} : pas encore de texte extrait en amont.\n"
            "   Le dépôt sondages-commission-index le génère au fil de l'eau ; en attendant,\n"
            "   télécharger le PDF et utiliser --pdf."
        )
    return notice.fetch_text(notice.blob_to_raw(txt_url, BLOB_BASE, RAW_BASE))


def resolve_text(args, repo, token):
    if args.txt:
        return Path(args.txt).read_text(encoding="utf-8")
    if args.pdf:
        return notice.extract_pdf_text(args.pdf)
    return notice_text_for(issue_poll_filename(repo, args.issue, token))


def set_label(repo, number, token, issue, label):
    """Pose le label du verdict et retire les autres labels de triage."""
    current = [entry.get("name", "") for entry in issue.get("labels", [])]
    for stale in render.labels_to_remove(current, label):
        _github_request(f"https://api.github.com/repos/{repo}/issues/{number}/labels/{quote(stale)}", token, "DELETE")
    if label not in current:
        _github_request(
            f"https://api.github.com/repos/{repo}/issues/{number}/labels", token, "POST", {"labels": [label]}
        )


def publish(repo, number, token, body, label, force=False):
    """Publie le commentaire et pose le label. Il n'y a jamais qu'un commentaire.

    Sans --force on ne repasse pas sur une issue déjà traitée ; avec, le
    commentaire existant est réécrit plutôt que doublé.
    """
    issue = _github_request(f"https://api.github.com/repos/{repo}/issues/{number}", token)
    comments = _github_request(f"https://api.github.com/repos/{repo}/issues/{number}/comments?per_page=100", token)
    existing = render.find_marker_comment(comments)

    if render.already_commented(comments) and not force:
        print(f"⏭️  Issue #{number} : commentaire de triage déjà présent (--force pour le refaire)")
        return

    if existing:
        _github_request(
            f"https://api.github.com/repos/{repo}/issues/comments/{existing}", token, "PATCH", {"body": body}
        )
        action = "commentaire mis à jour"
    else:
        _github_request(f"https://api.github.com/repos/{repo}/issues/{number}/comments", token, "POST", {"body": body})
        action = "commentaire publié"

    set_label(repo, number, token, issue, label)
    print(f"✅ Issue #{number} : {action}, label « {label} » posé")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--issue", type=int, help="numéro de l'issue « nouveau sondage » à traiter")
    source.add_argument("--txt", help="fichier texte local, au lieu de la notice amont")
    source.add_argument("--pdf", help="PDF local, extrait avec pdfplumber")
    parser.add_argument(
        "--post", action="store_true", help="publier le commentaire et le label (nécessite GITHUB_TOKEN)"
    )
    parser.add_argument(
        "--force", action="store_true", help="refaire le triage d'une issue déjà traitée, en réécrivant le commentaire"
    )
    parser.add_argument(
        "--max-calls", type=int, default=DEFAULT_MAX_CALLS, help=f"plafond d'appels (défaut: {DEFAULT_MAX_CALLS})"
    )
    args = parser.parse_args(argv)

    repo = os.environ.get("GITHUB_REPOSITORY", "MieuxVoter/presidentielle2027")
    token = os.environ.get("GITHUB_TOKEN")
    if args.post:
        if not args.issue:
            parser.error("--post exige --issue")
        if not token:
            parser.error("--post exige GITHUB_TOKEN")

    providers = llm.providers_from_env()
    if not providers:
        raise SystemExit(
            "❌ Aucune clé d'API trouvée. Renseigner au moins une des variables :\n"
            "   OPENROUTER_API_KEY, MISTRAL_API_KEY, GEMINI_API_KEY"
        )
    print(f"🤖 Fournisseurs actifs : {', '.join(p.name for p in providers)}")

    pages = notice.strip_empty(notice.split_pages(resolve_text(args, repo, token)))
    if not pages:
        raise SystemExit("❌ Notice vide ou sans séparateurs de page")
    print(f"📄 {len(pages)} page(s) à examiner")

    conversation = llm.Client(providers=providers, max_calls=args.max_calls)
    result = steps.triage(conversation, pages)
    model = conversation.log[-1]["model"] if conversation.log else ""
    body = render.comment(result, model)
    label = render.label(result)

    if args.post:
        publish(repo, args.issue, token, body, label, force=args.force)
        return 0

    print(f"\n{'-' * 70}\nlabel : {label}\n{'-' * 70}\n{body}{'-' * 70}")
    print(f"💡 Pour publier : ajouter --post   ({conversation.calls} appel(s) consommé(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
