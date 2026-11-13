"""Assemblage déterministe d'une proposition de CSV à partir des extractions validées."""

import csv
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from merge import _norm, load_hypotheses


class ProposalError(ValueError):
    """Une proposition ne peut pas être ajoutée sans ambiguïté au dépôt."""


@dataclass
class Proposal:
    """Objet sérialisable, commun à l'aperçu, add_poll.py et la future PR."""

    filename: str
    methodology: dict
    polls: list = field(default_factory=list)
    results: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    hypotheses: list = field(default_factory=list)
    candidates: list = field(default_factory=list)
    failures: list = field(default_factory=list)
    # Pages non dépouillées faute d'appel au modèle (quota, réseau) : la PR reste
    # utile avec les tableaux obtenus, et une relance complétera.
    missing: list = field(default_factory=list)
    # Tableaux écartés parce que leur hypothèse est déjà enregistrée pour ce PDF.
    already_present: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def _read_rows(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _institute_codes(polls):
    codes = {}
    for row in polls:
        match = re.match(r"^\d{8}_\d{4}_([a-z]+)_(?:2)?[A-Z]+$", row.get("poll_id", ""))
        if match and row.get("nom_institut", "").strip():
            codes.setdefault(row["nom_institut"].strip(), Counter())[match.group(1)] += 1
    return {name: counter.most_common(1)[0][0] for name, counter in codes.items()}


def _letter(number):
    """A, …, Z, AA : une notice ne devrait pas en avoir 27, mais c'est défini."""
    result = ""
    while True:
        number, remainder = divmod(number, 26)
        result = chr(ord("A") + remainder) + result
        if number == 0:
            return result
        number -= 1


def _next_poll_id(start, end, code, tour, used, counters):
    prefix = f"{start.replace('-', '')}_{end[5:7]}{end[8:10]}_{code}_"
    key = (prefix, tour)
    number = counters.get(key, 0)
    while True:
        suffix = ("2" if tour == "2nd Tour" else "") + _letter(number)
        candidate = prefix + suffix
        number += 1
        if candidate not in used:
            counters[key] = number
            used.add(candidate)
            return candidate


def _new_candidate_id(name, used):
    words = [word for word in re.findall(r"[A-Za-zÀ-ÿ]+", name) if word]
    base = "".join(word[0] for word in words).upper() or "C"
    candidate = base
    index = 2
    while candidate in used:
        # Conserver des identifiants lisibles plutôt que de réutiliser un ID.
        candidate = f"{base}{index}"
        index += 1
    used.add(candidate)
    return candidate


def _candidate_row(name, candidate_id):
    pieces = name.rsplit(" ", 1)
    first, surname = (pieces[0], pieces[1]) if len(pieces) == 2 else (name, "")
    return {
        "candidate_id": candidate_id,
        "complete_name": name,
        "name": first,
        "surname": surname,
        "parti": "",
        "annonce_candidature": "",
        "retrait_candidature": "",
        "second_round": "",
    }


def _next_hypothesis_id(tour, existing):
    if tour == "2nd Tour":
        values = [int(match.group(1)) for value in existing if (match := re.fullmatch(r"H2_(\d+)", value))]
        return f"H2_{max(values, default=0) + 1}"
    values = [int(match.group(1)) for value in existing if (match := re.fullmatch(r"H(\d+)", value))]
    return f"H{max(values, default=0) + 1}"


def _samples_for_metadata(methodology, table):
    fields = {
        "sous_echantillon1": methodology.registered or "",
        "sous_population1": "Inscrits sur les listes électorales" if methodology.registered else "",
        "sous_echantillon2": "",
        "sous_population2": "",
        "sous_echantillon3": "",
        "sous_population3": "",
    }
    for index, (label, count) in enumerate(sorted(table.samples, key=lambda item: -item[1])[:2], 2):
        fields[f"sous_echantillon{index}"] = count
        fields[f"sous_population{index}"] = label
    return fields


def build(filename, methodology, tables, root, missing=()):
    """Construit une proposition sans écrire un seul octet dans le dépôt.

    Une notice déjà (partiellement) dépouillée n'est pas refusée : seules les
    hypothèses qu'elle n'a pas encore enregistrées sont proposées, avec les
    lettres de poll_id encore libres. C'est ce qui permet de compléter plus tard
    un dépouillement interrompu par un quota.
    """
    root = Path(root)
    polls = _read_rows(root / "polls.csv")
    recorded = {
        (row.get("tour", "").strip(), row.get("hypothese", "").strip())
        for row in polls
        if row.get("filename", "").strip() == filename
    }
    codes = _institute_codes(polls)
    code = codes.get(methodology.institute)
    if not code:
        raise ProposalError(f"aucun code poll_id connu pour l'institut {methodology.institute}")

    candidate_rows = _read_rows(root / "candidats.csv")
    candidate_by_name = {_norm(row["complete_name"]): row["complete_name"] for row in candidate_rows}
    candidate_ids = {row["candidate_id"] for row in candidate_rows}
    hypotheses = load_hypotheses(root / "hypotheses.csv")
    hypothesis_sets = {
        ("2nd Tour" if identifier.startswith("H2_") else "1er Tour", frozenset(names)): identifier
        for identifier, names in hypotheses.items()
    }
    all_hypotheses = set(hypotheses)
    proposal = Proposal(filename, asdict(methodology), missing=list(missing))
    used_ids = {row["poll_id"] for row in polls}
    counters = {}

    for table in tables:
        names = []
        for value in table.values:
            canonical = candidate_by_name.get(_norm(value.name), value.name)
            names.append(canonical)
            key = _norm(canonical)
            if key not in candidate_by_name:
                candidate_by_name[key] = canonical
                proposal.candidates.append(_candidate_row(canonical, _new_candidate_id(canonical, candidate_ids)))
        name_set = frozenset(_norm(name) for name in names)
        hypothesis = hypothesis_sets.get((table.tour, name_set))
        if not hypothesis:
            hypothesis = _next_hypothesis_id(table.tour, all_hypotheses)
            all_hypotheses.add(hypothesis)
            hypothesis_sets[(table.tour, name_set)] = hypothesis
            proposal.hypotheses.append(
                {"id_hypothese": hypothesis, "hypothese_complete": ",".join(names), "commentaire": ""}
            )
        if (table.tour, hypothesis) in recorded:
            proposal.already_present.append(f"page {table.page} : {hypothesis} déjà enregistrée pour {filename}")
            continue
        poll_id = _next_poll_id(methodology.start, methodology.end, code, table.tour, used_ids, counters)
        metadata = {
            "poll_id": poll_id,
            "hypothese": hypothesis,
            "nom_institut": methodology.institute,
            "commanditaire": methodology.commissioner,
            "debut_enquete": methodology.start,
            "fin_enquete": methodology.end,
            "echantillon": methodology.sample,
            "population": methodology.population,
            "rolling": "",
            "media": "True",
            "tour": table.tour,
            "filename": filename,
        }
        metadata.update(_samples_for_metadata(methodology, table))
        proposal.polls.append(metadata)
        proposal.results[poll_id] = [
            {"candidat": name, "intentions": value.as_csv(), "erreur_sup": "", "erreur_inf": ""}
            for name, value in zip(names, table.values)
        ]
        proposal.evidence[poll_id] = {
            "page": table.page,
            "samples": list(table.samples),
            "values": [
                {"candidat": name, "intentions": value.as_csv(), "source": value.source}
                for name, value in zip(names, table.values)
            ],
        }
    if not proposal.polls:
        if proposal.already_present:
            raise ProposalError(f"tous les tableaux extraits sont déjà enregistrés pour {filename}")
        raise ProposalError("aucun tableau validé : aucune proposition à écrire")
    return proposal
