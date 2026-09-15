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
import datetime as dt
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

# Réutilise le catalogue et le client HTTP GitHub déjà écrits pour les issues.
from check_new_polls import (
    BLOB_BASE,
    LEGACY_MARKER_RE,
    MARKER_RE,
    RAW_BASE,
    _github_request,
    _mirror_url,
    get_catalog_polls,
    notice_links,
)
from mining import client as llm
from mining import csvio, extraction, notice, pull_request, render, steps
from mining.proposal import ProposalError, build as build_proposal

DEFAULT_MAX_CALLS = 80


class NoticeUnavailable(Exception):
    """La notice n'est pas analysable : à dire sous l'issue, pas à faire échouer le job."""


def github_get(url, token):
    """GET sur l'API GitHub, anonyme quand aucun jeton n'est disponible.

    Lire une issue publique ne demande pas de jeton : l'aperçu doit donc marcher
    en local sans en configurer un, seule la publication en exige un.
    """
    if token:
        return _github_request(url, token)
    request = Request(url, headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "presidentielle2027"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def poll_filename_from_body(body):
    """Le nom de fichier de notice porté par une issue, ou None.

    Deux formats coexistent : le marqueur HTML des issues récentes, et l'ancien
    « Fichier PDF à vérifier » des issues plus anciennes. check_new_polls
    reconnaît déjà les deux pour son dédoublonnage, il faut en faire autant.
    """
    match = MARKER_RE.search(body or "") or LEGACY_MARKER_RE.search(body or "")
    return match.group(1).strip() if match else None


def issue_poll_filename(repo, number, token):
    """Le nom de fichier de la notice, lu dans le corps de l'issue."""
    url = f"https://api.github.com/repos/{repo}/issues/{number}"
    try:
        issue = github_get(url, token)
    except HTTPError as exc:
        raise SystemExit(f"❌ Issue #{number} : l'API GitHub répond {exc.code}. Dépôt ou numéro d'issue correct ?")
    except (URLError, TimeoutError, OSError) as exc:
        raise SystemExit(f"❌ Issue #{number} : l'API GitHub est injoignable ({exc})")
    filename = poll_filename_from_body(issue.get("body"))
    if not filename:
        raise NoticeUnavailable("le corps de l'issue n'indique aucun fichier de notice.")
    return filename


def notice_text_for(filename):
    """Le texte de la notice : le TXT amont s'il existe, sinon le PDF extrait ici.

    L'amont ne publie de version texte que depuis peu, et ne l'a pas fait
    rétroactivement : sans ce repli, l'outil serait inutilisable sur la quasi-
    totalité des issues déjà ouvertes. L'extraction reprend la même commande
    pdfplumber que l'amont, pour obtenir le même texte.
    """
    rows = [r for r in get_catalog_polls() if (r.get("filename") or "").strip() == filename]
    if not rows:
        raise NoticeUnavailable(f"`{filename}` est introuvable dans le catalogue amont.")

    txt_url, _pdf_url, _source = notice_links(rows[0])
    if txt_url:
        return notice.fetch_text(notice.blob_to_raw(txt_url, BLOB_BASE, RAW_BASE))

    pdf_path = (rows[0].get("pdf_path") or "").strip()
    if not pdf_path:
        raise NoticeUnavailable(f"`{filename}` n'a ni texte extrait ni PDF dans le catalogue amont.")

    print(f"📄 Pas de texte en amont pour {filename} : extraction du PDF")
    try:
        return notice.pdf_text_from_url(_mirror_url(RAW_BASE, pdf_path))
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise NoticeUnavailable(f"le PDF de `{filename}` n'a pas pu être téléchargé ({exc}).") from exc


def resolve_text(args, repo, token):
    if args.txt:
        return Path(args.txt).read_text(encoding="utf-8")
    if args.pdf:
        return notice.extract_pdf_text(args.pdf)
    return notice_text_for(issue_poll_filename(repo, args.issue, token))


def source_filename(args, repo, token, text):
    """Le PDF de référence, nécessaire pour écrire une proposition traçable."""
    if args.issue:
        return issue_poll_filename(repo, args.issue, token)
    header = notice.parse_header(text)
    return Path(header.get("source_pdf") or args.pdf or args.txt).name


def notice_date(text):
    """La date de création de la notice amont borne la date de terrain E2."""
    raw = notice.parse_header(text).get("pdf_creation-date", "")[:10]
    try:
        return dt.date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def log_triage(result, conversation):
    """Ce que le modèle a répondu et ce que Python en a retenu, dans les logs du job.

    Sans cette trace, un échec sous l'issue ne se comprend qu'en lisant le
    commentaire publié, et pas du tout quand la publication échoue.
    """
    for index, entry in enumerate(conversation.log, 1):
        cut = " — TRONQUÉE par max_tokens" if entry.get("truncated") else ""
        print(
            f"   appel {index} : {entry.get('provider')} / {entry.get('model')} — {len(entry.get('answer') or '')} car.{cut}"
        )
        print(f"   fin de la réponse : {extraction.tail(entry.get('answer'), 600)}")
    print(
        f"🔎 Triage : {result.verdict} · pages {result.pages_with_intentions or '-'} · "
        f"méthodo {result.methodo_pages or '-'} · {conversation.calls} appel(s)"
    )
    if result.invalid_pages or result.invalid_methodo_pages:
        print(f"   pages absentes du document : {result.invalid_pages} / méthodo {result.invalid_methodo_pages}")
    if result.failed:
        print(f"⚠️  {result.failed}")


def preview_proposal(proposal, failures):
    """Aperçu compact et copiable de la proposition."""
    print("\n" + "-" * 70)
    print("Proposition de données (à vérifier avant toute PR)")
    for poll in proposal.polls:
        print(f"- {poll['poll_id']} — {poll['tour']} — {poll['hypothese']}")
    if proposal.candidates:
        print("Candidats nouveaux : " + ", ".join(row["complete_name"] for row in proposal.candidates))
    if proposal.hypotheses:
        print("Hypothèses nouvelles : " + ", ".join(row["id_hypothese"] for row in proposal.hypotheses))
    if proposal.missing:
        print("⚠️  INCOMPLET — pages non dépouillées (relancer pour compléter) :\n- " + "\n- ".join(proposal.missing))
    if proposal.already_present:
        print("Déjà enregistrés, non reproposés :\n- " + "\n- ".join(proposal.already_present))
    if failures:
        print("Tableaux écartés :\n- " + "\n- ".join(failures))
    print("-" * 70)


def set_label(repo, number, token, issue, triage):
    """Accorde les labels de triage de l'issue au résultat, sans écraser un humain sur un échec."""
    current = [entry.get("name", "") for entry in issue.get("labels", [])]
    to_add, to_remove = render.label_changes(current, triage)
    for stale in to_remove:
        _github_request(f"https://api.github.com/repos/{repo}/issues/{number}/labels/{quote(stale)}", token, "DELETE")
    if to_add:
        _github_request(
            f"https://api.github.com/repos/{repo}/issues/{number}/labels", token, "POST", {"labels": to_add}
        )
    return to_add, to_remove


def publish(repo, number, token, body, triage, force=False):
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

    added, removed = set_label(repo, number, token, issue, triage)
    changes = ", ".join([f"+{name}" for name in added] + [f"-{name}" for name in removed]) or "labels inchangés"
    print(f"✅ Issue #{number} : {action} ({changes})")


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
    parser.add_argument(
        "--pr",
        action="store_true",
        help="extraire E2/E3 ; avec --post, créer ou mettre à jour une PR brouillon",
    )
    parser.add_argument("--apply", action="store_true", help="avec --pr, ajouter la proposition dans l'arbre local")
    parser.add_argument("--proposal", help="avec --pr, écrire aussi la proposition JSON à ce chemin")
    args = parser.parse_args(argv)

    if args.apply and not args.pr:
        parser.error("--apply exige --pr")
    if args.proposal and not args.pr:
        parser.error("--proposal exige --pr")
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

    conversation = llm.Client(providers=providers, max_calls=args.max_calls)
    try:
        text = resolve_text(args, repo, token)
        pages = notice.strip_empty(notice.split_pages(text))
        if not pages:
            raise NoticeUnavailable("le texte de la notice est vide ou ne comporte aucun séparateur de page.")
        print(f"📄 {len(pages)} page(s) à examiner")
        result = steps.triage(conversation, pages)
    except NoticeUnavailable as exc:
        # Une notice illisible est une information utile sous l'issue : on la
        # publie au lieu de faire échouer le job, qui ne dirait rien à personne.
        print(f"⚠️  Notice non analysable : {exc}")
        result = steps.Triage(failed=str(exc))

    log_triage(result, conversation)

    pr_status = ""
    if args.pr:
        if result.verdict != "oui":
            reason = result.failed or "le triage n'a pas trouvé d'intentions de vote"
            message = f"Aucune PR : {reason}."
            print("\n" + message)
            pr_status = f"> ⚠️ {message}"
        else:
            mined = extraction.extract(
                conversation,
                pages,
                result,
                Path(__file__).resolve().parent / "candidats.csv",
                Path(__file__).resolve().parent / "polls.csv",
                notice_date(text),
                log=print,
            )
            print(f"   {conversation.calls} appel(s) consommé(s) au total")
            if not mined.methodology:
                message = "Aucune PR : les métadonnées E2 ont été rejetées. " + "; ".join(mined.failures)
                print("\n" + message)
                pr_status = f"> ⚠️ {message}"
            else:
                try:
                    proposal = build_proposal(
                        source_filename(args, repo, token, text),
                        mined.methodology,
                        mined.tables,
                        Path(__file__).resolve().parent,
                        # Un dépouillement incomplet reste proposé : les tableaux
                        # obtenus sont vérifiés, une relance complétera.
                        missing=mined.api_failures,
                    )
                    proposal.failures.extend(mined.failures)
                    preview_proposal(proposal, mined.failures)
                    if args.proposal and not args.post:
                        Path(args.proposal).write_text(
                            json.dumps(proposal.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                        )
                        print(f"Proposition JSON écrite : {args.proposal}")
                    root = Path(__file__).resolve().parent
                    if args.post:
                        branch = pull_request.prepare_branch(args.issue, root)
                        csvio.apply(proposal, root)
                        models = [entry["model"] for entry in conversation.log if entry.get("model")]
                        created = pull_request.create_or_update(
                            args.issue, repo, proposal, root, models=models, calls=conversation.calls
                        )
                        if proposal.missing:
                            pr_status = (
                                f"> ⚠️ PR brouillon **incomplète** créée ou mise à jour : [#{created.number}]({created.url})"
                                f" — {len(proposal.polls)} tableau(x), {len(proposal.missing)} page(s) non dépouillée(s)."
                                " Relancer /mining-pr pour compléter."
                            )
                        else:
                            pr_status = f"> ✅ PR brouillon créée ou mise à jour : [#{created.number}]({created.url})."
                        if created.labels_warning:
                            pr_status += f" {created.labels_warning}."
                        print(f"✅ {branch} → {created.url}")
                    elif args.apply:
                        csvio.apply(proposal, Path(__file__).resolve().parent)
                        print("Proposition ajoutée localement. Lancez pytest puis python merge.py avant la PR.")
                except (ProposalError, pull_request.PullRequestError) as exc:
                    message = f"Aucune PR : {exc}"
                    print("\n" + message)
                    pr_status = f"> ⚠️ {message}"

    model = conversation.log[0]["model"] if conversation.log else ""
    body = render.comment(result, model, pr=pr_status)
    label = render.label(result)

    if args.post:
        publish(repo, args.issue, token, body, result, force=args.force)
        return 0

    print(f"\n{'-' * 70}\nlabel : {label}\n{'-' * 70}\n{body}{'-' * 70}")
    print(f"💡 Pour publier : ajouter --post   ({conversation.calls} appel(s) consommé(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
