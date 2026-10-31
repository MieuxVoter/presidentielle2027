#!/usr/bin/env python3
"""Ajoute une proposition JSON de mining, en append-only.

python add_poll.py proposition.json --dry-run
python add_poll.py proposition.json
"""

import argparse
import json
from pathlib import Path

from mining import csvio
from mining.proposal import Proposal

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal", help="JSON produit par mine_poll.py --pr --proposal")
    parser.add_argument("--dry-run", action="store_true", help="vérifier et afficher, sans écrire")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    data = json.loads(Path(args.proposal).read_text(encoding="utf-8"))
    proposal = Proposal(**data)
    csvio.validate(proposal, args.root)
    print(f"Proposition valide : {csvio.summary(proposal)}")
    if args.dry_run:
        print("Dry run : aucun fichier modifié.")
        return 0
    csvio.apply(proposal, args.root)
    print("Ajout terminé.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
