#!/usr/bin/env python3
"""
Merge individual poll result CSVs with metadata into a single presidentielle2027.csv.

Inputs (under repo root):
- candidats.csv: mapping of candidates (with id, name parts)
- hypotheses.csv: list of candidates per hypothesis id (H1..)
- polls.csv: poll metadata (poll_id, hypothese, institute, dates, ...)
- polls/<poll_id>.csv: per-poll results with columns: candidat,intentions,erreur_sup,erreur_inf

Output:
- presidentielle2027.csv: one row per (poll, candidate) with metadata and results.

This script purposefully avoids external deps (pandas) to run in CI easily.
"""
from __future__ import annotations

import csv
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parent


def _norm(s: str) -> str:
    """Normalize names: strip accents, normalize hyphens/apostrophes, collapse spaces, lowercase."""
    if s is None:
        return ""
    # Replace fancy punctuation with ASCII equivalents
    s2 = s.replace("’", "'").replace("`", "'").replace("–", "-").replace("—", "-").replace("‐", "-")
    # NFD then remove diacritics
    s2 = unicodedata.normalize("NFD", s2)
    s2 = "".join(ch for ch in s2 if unicodedata.category(ch) != "Mn")
    # Collapse whitespace
    s2 = " ".join(s2.split())
    return s2.lower().strip()


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    complete_name: str
    name: str
    surname: str
    parti: str

    def keys(self) -> List[str]:
        keys = []
        if self.complete_name:
            keys.append(_norm(self.complete_name))
        n = self.name or ""
        s = self.surname or ""
        if n or s:
            keys.append(_norm(f"{n} {s}"))
            keys.append(_norm(f"{s} {n}"))  # rare but defensive
        return [k for k in keys if k]


def load_candidates(path: Path) -> Tuple[Dict[str, Candidate], Dict[str, str]]:
    """Return mapping id->Candidate and nameKey->candidate_id."""
    id_map: Dict[str, Candidate] = {}
    name_to_id: Dict[str, str] = {}
    with path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        required = {"candidate_id", "complete_name", "name", "surname", "parti"}
        if not required.issubset(rdr.fieldnames or set()):
            raise ValueError(f"candidats.csv missing required columns: {required}")
        for row in rdr:
            c = Candidate(
                candidate_id=row["candidate_id"].strip(),
                complete_name=(row.get("complete_name") or "").strip(),
                name=(row.get("name") or "").strip(),
                surname=(row.get("surname") or "").strip(),
                parti=(row.get("parti") or "").strip(),
            )
            if not c.candidate_id:
                continue
            id_map[c.candidate_id] = c
            for k in c.keys():
                # Don't overwrite existing mappings to keep first occurrence
                name_to_id.setdefault(k, c.candidate_id)
    return id_map, name_to_id


def load_hypotheses(path: Path) -> Dict[str, List[str]]:
    """Map hypothesis id (e.g., H1) -> list of normalized candidate names in that hypothesis order."""
    mapping: Dict[str, List[str]] = {}
    with path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        if not {"id_hypothese", "hypothese_complete"}.issubset(set(rdr.fieldnames or [])):
            raise ValueError("hypotheses.csv missing required columns")
        for row in rdr:
            hid = (row.get("id_hypothese") or "").strip()
            raw = row.get("hypothese_complete") or ""
            # Split on commas, strip trailing punctuation/spaces
            names = [x.strip() for x in raw.split(",") if x.strip()]
            mapping[hid] = [_norm(x) for x in names]
    return mapping


def iter_polls_meta(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            if not row.get("poll_id"):
                continue
            yield row


def read_poll_results(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        required = {"candidat", "intentions", "erreur_sup", "erreur_inf"}
        if not required.issubset(rdr.fieldnames or set()):
            raise ValueError(f"poll results {path.name} missing required columns: {required}")
        rows = []
        for row in rdr:
            # Skip blank lines
            if not row.get("candidat"):
                continue
            rows.append(row)
        return rows


def merge(repo_root: Path = ROOT) -> List[dict]:
    """Return merged rows as a list of dictionaries."""
    candidates_csv = repo_root / "candidats.csv"
    hypotheses_csv = repo_root / "hypotheses.csv"
    polls_csv = repo_root / "polls.csv"
    polls_dir = repo_root / "polls"

    id_to_candidate, name_to_id = load_candidates(candidates_csv)
    hypothesis_to_names = load_hypotheses(hypotheses_csv)

    merged: List[dict] = []
    for meta in iter_polls_meta(polls_csv):
        poll_id = meta["poll_id"].strip()
        hyp = meta.get("hypothese", "").strip()

        poll_file = polls_dir / f"{poll_id}.csv"
        if not poll_file.exists():
            raise FileNotFoundError(f"Missing poll results file: {poll_file}")

        results = read_poll_results(poll_file)
        # Validate candidates match the hypothesis set (order not enforced strictly)
        expected = set(hypothesis_to_names.get(hyp, []))
        got = {_norm(r["candidat"]) for r in results}
        # Only warn if hypothesis known and non-empty
        if expected and got != expected:
            # Soft warning on stderr, continue merging
            sys.stderr.write(f"Warning: Poll {poll_id} candidates differ from hypothesis {hyp}.\n")

        for r in results:
            name_key = _norm(r["candidat"])
            cid = name_to_id.get(name_key)
            if not cid:
                # Fallback: generate an ID from initials, keep other fields blank
                parts = [p for p in (r["candidat"].replace("-", " ").split()) if p]
                initials = "".join((p[0] for p in parts)) if parts else name_key[:2]
                cid = initials.upper()
                c = Candidate(candidate_id=cid, complete_name=r["candidat"], name="", surname="", parti="")
            else:
                c = id_to_candidate[cid]
            # Build merged row
            merged.append(
                {
                    # poll metadata
                    "poll_id": poll_id,
                    "hypothese": hyp,
                    "nom_institut": meta.get("nom_institut", ""),
                    "commanditaire": meta.get("commanditaire", ""),
                    "debut_enquete": meta.get("debut_enquete", ""),
                    "fin_enquete": meta.get("fin_enquete", ""),
                    "echantillon": meta.get("echantillon", ""),
                    "population": meta.get("population", ""),
                    "rolling": meta.get("rolling", ""),
                    "media": meta.get("media", ""),
                    "tour": meta.get("tour", ""),
                    "filename": meta.get("filename", ""),
                    # candidate info
                    "candidate_id": c.candidate_id,
                    "candidat": r.get("candidat", ""),
                    "complete_name": c.complete_name,
                    "name": c.name,
                    "surname": c.surname,
                    "parti": c.parti,
                    # results
                    "intentions": r.get("intentions", ""),
                    "erreur_sup": r.get("erreur_sup", ""),
                    "erreur_inf": r.get("erreur_inf", ""),
                }
            )

    return merged


def write_csv(rows: List[dict], out_path: Path) -> None:
    if not rows:
        # Write header only with a minimal schema
        fieldnames = [
            "poll_id",
            "hypothese",
            "nom_institut",
            "commanditaire",
            "debut_enquete",
            "fin_enquete",
            "echantillon",
            "population",
            "rolling",
            "media",
            "tour",
            "filename",
            "candidate_id",
            "candidat",
            "complete_name",
            "name",
            "surname",
            "parti",
            "intentions",
            "erreur_sup",
            "erreur_inf",
        ]
    else:
        # Preserve column order based on our construction above
        fieldnames = list(rows[0].keys())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        for row in rows:
            wr.writerow(row)


def main(argv: List[str]) -> int:
    root = ROOT
    out = root / "presidentielle2027.csv"
    rows = merge(root)
    write_csv(rows, out)
    print(f"Wrote {len(rows)} rows to {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
