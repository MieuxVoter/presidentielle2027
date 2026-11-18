"""Validate integrity of metadata CSVs and cross-references."""

import csv
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _split_candidates(hypothese_complete: str) -> list:
    """Découpe une hypothèse en noms de candidats (espaces retirés, entrées vides ignorées)."""
    return [c.strip() for c in hypothese_complete.split(",") if c.strip()]


def _normalize_name(name: str) -> str:
    """Normalise un nom pour comparaison : casse et accents ignorés (même logique que merge.py)."""
    nfd = unicodedata.normalize("NFD", name.strip().casefold())
    return "".join(c for c in nfd if not unicodedata.combining(c))


def _load_hypotheses() -> dict:
    """Retourne {id_hypothese: [candidats]} depuis hypotheses.csv."""
    hypotheses = {}
    with (ROOT / "hypotheses.csv").open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            hid = row.get("id_hypothese", "").strip()
            if hid:
                hypotheses[hid] = _split_candidates(row.get("hypothese_complete", ""))
    return hypotheses


def test_polls_csv_references_existing_files():
    """Each poll_id in polls.csv should have a corresponding CSV file."""
    polls_csv = ROOT / "polls.csv"
    polls_dir = ROOT / "polls"

    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            poll_id = row.get("poll_id", "").strip()
            if not poll_id:
                continue
            poll_file = polls_dir / f"{poll_id}.csv"
            assert poll_file.exists(), f"Missing poll file for {poll_id}: {poll_file.name}"


def test_polls_csv_has_unique_poll_ids():
    """poll_id should be unique in polls.csv."""
    polls_csv = ROOT / "polls.csv"
    seen = set()

    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            poll_id = row.get("poll_id", "").strip()
            if not poll_id:
                continue
            assert poll_id not in seen, f"Duplicate poll_id: {poll_id}"
            seen.add(poll_id)


def test_hypotheses_csv_well_formed():
    """hypotheses.csv must have id_hypothese and hypothese_complete."""
    hypotheses_csv = ROOT / "hypotheses.csv"
    with hypotheses_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"id_hypothese", "hypothese_complete"}
        assert required.issubset(set(reader.fieldnames or [])), f"hypotheses.csv missing columns: {required}"
        rows = list(reader)
        assert len(rows) > 0, "hypotheses.csv is empty"


def test_hypotheses_csv_has_unique_ids():
    """Hypothesis IDs should be unique in hypotheses.csv."""
    hypotheses_csv = ROOT / "hypotheses.csv"
    seen = set()

    with hypotheses_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hid = row.get("id_hypothese", "").strip()
            if not hid:
                continue
            assert hid not in seen, f"Duplicate id_hypothese: {hid}"
            seen.add(hid)


def test_candidats_csv_has_unique_ids():
    """candidate_id should be unique in candidats.csv."""
    candidats_csv = ROOT / "candidats.csv"
    seen = set()

    with candidats_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get("candidate_id", "").strip()
            if not cid:
                continue
            assert cid not in seen, f"Duplicate candidate_id: {cid}"
            seen.add(cid)


def test_candidats_csv_has_required_columns():
    """candidats.csv must have all required columns."""
    candidats_csv = ROOT / "candidats.csv"
    required = {"candidate_id", "complete_name", "name", "surname", "parti"}

    with candidats_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        assert required.issubset(fieldnames), f"candidats.csv missing columns: {required - fieldnames}"


def test_polls_csv_has_required_columns():
    """polls.csv must have all required columns."""
    polls_csv = ROOT / "polls.csv"
    required = {
        "poll_id",
        "hypothese",
        "nom_institut",
        "commanditaire",
        "debut_enquete",
        "fin_enquete",
        "echantillon",
        "population",
        "tour",
    }

    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        assert required.issubset(fieldnames), f"polls.csv missing columns: {required - fieldnames}"


def test_institut_names_have_consistent_casing():
    """A given institute should always be written the same way in polls.csv.

    csv_to_json.py copies nom_institut verbatim into the published JSON, so two
    spellings of the same institute look like two institutes to any consumer
    grouping by that field.
    """
    polls_csv = ROOT / "polls.csv"
    spellings = {}

    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("nom_institut", "").strip()
            if not name:
                continue
            spellings.setdefault(name.casefold(), set()).add(name)

    inconsistent = {key: sorted(names) for key, names in spellings.items() if len(names) > 1}
    assert not inconsistent, f"Institute written several ways: {inconsistent}"


def test_all_poll_files_referenced_in_metadata():
    """Every CSV file in polls/ should have metadata in polls.csv."""
    polls_csv = ROOT / "polls.csv"
    polls_dir = ROOT / "polls"

    # Load all poll_ids from metadata
    poll_ids_in_metadata = set()
    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            poll_id = row.get("poll_id", "").strip()
            if poll_id:
                poll_ids_in_metadata.add(poll_id)

    # Check all CSV files in polls/
    for poll_file in polls_dir.glob("*.csv"):
        poll_id = poll_file.stem
        assert poll_id in poll_ids_in_metadata, f"Poll file {poll_file.name} has no metadata entry in polls.csv"


def test_hypothesis_references_in_polls_are_valid():
    """All hypothesis IDs in polls.csv should exist in hypotheses.csv."""
    hypotheses_csv = ROOT / "hypotheses.csv"
    polls_csv = ROOT / "polls.csv"

    # Load valid hypothesis IDs
    valid_hypotheses = set()
    with hypotheses_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hid = row.get("id_hypothese", "").strip()
            if hid:
                valid_hypotheses.add(hid)

    # Check all hypothesis references in polls.csv
    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hyp = row.get("hypothese", "").strip()
            if hyp:
                assert hyp in valid_hypotheses, f"Poll {row.get('poll_id')} references unknown hypothesis: {hyp}"


def test_every_poll_has_a_hypothesis():
    """Chaque sondage de polls.csv doit déclarer une hypothèse.

    Sans hypothèse, un sondage échappe à tous les tests de cohérence (candidats connus,
    correspondance avec les résultats, doublons).
    """
    with (ROOT / "polls.csv").open("r", encoding="utf-8") as f:
        missing = [row.get("poll_id") for row in csv.DictReader(f) if not (row.get("hypothese") or "").strip()]
    assert not missing, (
        f"Sondages sans hypothèse dans polls.csv : {missing}. "
        "Renseigner la colonne hypothese (créer l'hypothèse dans hypotheses.csv si besoin)."
    )


def test_hypothesis_references_in_presidentielle2027_are_valid():
    """Toute hypothèse citée dans presidentielle2027.csv (fichier généré) doit exister dans hypotheses.csv."""
    valid_hypotheses = set(_load_hypotheses())

    unknown = set()
    with (ROOT / "presidentielle2027.csv").open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            hyp = row.get("hypothese", "").strip()
            if hyp and hyp not in valid_hypotheses:
                unknown.add((row.get("poll_id", "").strip(), hyp))

    assert not unknown, "presidentielle2027.csv référence des hypothèses inconnues de hypotheses.csv :\n" + "\n".join(
        f"  sondage {poll_id} → {hyp}" for poll_id, hyp in sorted(unknown)
    )


def test_hypotheses_candidates_exist_in_candidats_csv():
    """Chaque nom d'une hypothèse doit figurer dans la colonne complete_name de candidats.csv.

    Évite qu'une modalité de réponse (« Ne se prononcent pas », « Blanc / nul »…)
    ou une faute de frappe soit saisie comme candidat (cf. #348).
    """
    with (ROOT / "candidats.csv").open("r", encoding="utf-8") as f:
        known = {row.get("complete_name", "").strip() for row in csv.DictReader(f)}

    offenders = [
        (hid, name) for hid, candidates in _load_hypotheses().items() for name in candidates if name not in known
    ]

    assert not offenders, (
        "Hypothèses contenant des noms absents de candidats.csv (complete_name) :\n"
        + "\n".join(f"  {hid} : « {name} »" for hid, name in offenders)
        + "\n  → corriger le nom (orthographe exacte de candidats.csv) ou ajouter le candidat à candidats.csv."
    )


def test_hypotheses_have_no_duplicates():
    """Deux hypothèses ne doivent pas avoir le même ensemble de candidats.

    L'ordre, les espaces, la casse, les accents et les entrées vides (virgule finale) sont ignorés.
    """
    ids_by_set = {}
    for hid, candidates in _load_hypotheses().items():
        if not candidates:
            continue
        key = frozenset(_normalize_name(c) for c in candidates)
        ids_by_set.setdefault(key, []).append(hid)

    duplicates = [ids for ids in ids_by_set.values() if len(ids) > 1]
    assert not duplicates, (
        "Hypothèses redondantes (même ensemble de candidats) :\n"
        + "\n".join(f"  {' = '.join(ids)}" for ids in duplicates)
        + "\n  → garder l'identifiant le plus ancien et y rediriger les références de polls.csv."
    )


def test_poll_candidates_match_declared_hypothesis():
    """Verify that candidates in each poll file match the declared hypothesis."""
    normalize_name = _normalize_name

    hypotheses_csv = ROOT / "hypotheses.csv"
    polls_csv = ROOT / "polls.csv"
    polls_dir = ROOT / "polls"

    # Load hypotheses: map id -> set of normalized candidate names
    hypotheses = {}
    with hypotheses_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hid = row.get("id_hypothese", "").strip()
            candidates_str = row.get("hypothese_complete", "").strip()
            if not hid or not candidates_str:
                continue

            candidates = [c.strip() for c in candidates_str.split(",") if c.strip()]
            hypotheses[hid] = set(normalize_name(c) for c in candidates)

    # Check each poll
    with polls_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            poll_id = row.get("poll_id", "").strip()
            declared_hyp = row.get("hypothese", "").strip()

            if not poll_id or not declared_hyp:
                continue

            # Read candidates from poll file
            poll_file = polls_dir / f"{poll_id}.csv"
            if not poll_file.exists():
                continue  # This is checked by another test

            poll_candidates = set()
            with poll_file.open("r", encoding="utf-8") as pf:
                poll_reader = csv.DictReader(pf)
                for poll_row in poll_reader:
                    candidat = poll_row.get("candidat", "").strip()
                    if candidat:
                        poll_candidates.add(normalize_name(candidat))

            # Get expected candidates from hypothesis
            if declared_hyp not in hypotheses:
                pytest.fail(f"Poll {poll_id} references unknown hypothesis: {declared_hyp}")

            expected_candidates = hypotheses[declared_hyp]

            # Compare
            if poll_candidates != expected_candidates:
                missing = expected_candidates - poll_candidates
                extra = poll_candidates - expected_candidates

                error_msg = [
                    f"\nPoll {poll_id} candidates don't match hypothesis {declared_hyp}:",
                ]

                if missing:
                    # Find original names from hypothesis for better error message
                    with hypotheses_csv.open("r", encoding="utf-8") as hf:
                        reader = csv.DictReader(hf)
                        for hrow in reader:
                            if hrow.get("id_hypothese", "").strip() == declared_hyp:
                                candidates_list = [
                                    c.strip() for c in hrow.get("hypothese_complete", "").split(",") if c.strip()
                                ]
                                missing_names = [c for c in candidates_list if normalize_name(c) in missing]
                                error_msg.append(f"  Missing in poll file: {missing_names}")
                                break

                if extra:
                    # Find original names from poll file
                    with poll_file.open("r", encoding="utf-8") as pf:
                        poll_reader = csv.DictReader(pf)
                        extra_names = [
                            poll_row.get("candidat", "").strip()
                            for poll_row in poll_reader
                            if normalize_name(poll_row.get("candidat", "").strip()) in extra
                        ]
                        error_msg.append(f"  Extra in poll file: {extra_names}")

                error_msg.append(f"  → Check if hypothesis {declared_hyp} is correct for this poll")
                pytest.fail("\n".join(error_msg))
