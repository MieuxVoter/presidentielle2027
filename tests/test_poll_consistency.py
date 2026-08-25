"""Cross-file consistency checks on poll data.

These tests encode invariants that hold for a well-formed poll: the intentions
add up, the metadata of a given source PDF is stated the same way everywhere,
and the poll_id actually describes the survey it names.

Known anomalies are listed explicitly rather than being absorbed by a loose
tolerance, so that fixing one is a one-line deletion and nothing new slips in
unnoticed.
"""

import csv
import datetime
import re
from collections import defaultdict
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
POLLS_CSV = ROOT / "polls.csv"
POLLS_DIR = ROOT / "polls"

VALID_TOURS = {"1er Tour", "2nd Tour"}

# Rounding on published figures: institutes publish whole or half points, so the
# reported shares can legitimately miss 100 by a few tenths.
SUM_TOLERANCE = 0.5

# Polls whose published shares do not add up. Both are missing points rather
# than being off by rounding, so a candidate line is probably missing or wrong.
# TODO: re-read the source notices and either fix or document the gap.
KNOWN_SUM_ANOMALIES = {
    "20250402_0404_el_E": 97.5,
    "20250411_0418_if_A": 98.0,
}

# poll_id encodes the end date as MMDD (e.g. 20250326_0327 = 26 -> 27 March).
# These spell it DDMM instead. They are not old: they were added between May and
# July 2026, alongside MMDD ones, back when COMMENT_AJOUTER_UN_SONDAGE.md still
# documented the format as DDMM. The guide is fixed; renaming the ids is a
# separate call, since they are the join key of the published dataset.
DDMM_POLL_IDS = {
    "20260322_2203_hi_A",
    "20260322_2203_hi_B",
    "20260428_3004_hi_A",
    "20260428_3004_hi_B",
    "20260428_3004_hi_C",
    "20260428_3004_hi_D",
    "20260610_1106_ow_A",
    "20260610_1106_ow_B",
    "20260610_1106_ow_C",
    "20260610_1106_ow_D",
    "20260610_1106_ow_E",
    "20260610_1106_ow_F",
    "20260622_2406_if_A",
    "20260622_2406_if_B",
    "20260622_2406_if_C",
    "20260622_2406_if_D",
    "20260622_2406_if_E",
    "20260622_2406_if_F",
    "20260622_2406_if_G",
    "20260622_2406_if_H",
}

# Source PDFs credited to two different surveys. One of the two poll groups
# carries the wrong filename; the right notice still has to be identified.
KNOWN_FILENAME_CONFLICTS = {
    "9916-pres-elabe-bfmtv-tribune-dimanche-5-avril.pdf",
    "9930-pres-ifop-hexagone-5-mai.pdf",
}

POLL_ID_RE = re.compile(r"^(?P<start>\d{8})_(?P<end>\d{4})_(?P<institute>[a-z]{2})(?:_(?P<variant>\d?[A-Z]))?$")


def _clean(row: dict, key: str) -> str:
    return (row.get(key) or "").strip()


def load_polls_metadata():
    """Return polls.csv rows that name a poll."""
    with POLLS_CSV.open("r", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if _clean(row, "poll_id")]


POLLS_METADATA = load_polls_metadata()


def load_results(poll_id: str):
    """Return the non-empty result rows of polls/<poll_id>.csv."""
    path = POLLS_DIR / f"{poll_id}.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if _clean(row, "candidat")]


def poll_ids():
    return [_clean(row, "poll_id") for row in POLLS_METADATA]


@pytest.mark.parametrize("poll_id", poll_ids())
def test_intentions_sum_to_100(poll_id: str):
    """Published shares are percentages of expressed votes, so they add up to 100."""
    values = [float(_clean(r, "intentions")) for r in load_results(poll_id) if _clean(r, "intentions")]
    if not values:
        pytest.skip(f"{poll_id} has no numeric intentions")

    total = round(sum(values), 2)

    if poll_id in KNOWN_SUM_ANOMALIES:
        expected = KNOWN_SUM_ANOMALIES[poll_id]
        assert total == pytest.approx(expected, abs=0.01), (
            f"{poll_id} sums to {total}, but is listed in KNOWN_SUM_ANOMALIES as {expected}. "
            f"If it was fixed, remove it from that list."
        )
        return

    assert abs(total - 100) <= SUM_TOLERANCE, f"{poll_id} intentions sum to {total}, expected 100 ± {SUM_TOLERANCE}"


@pytest.mark.parametrize("row", POLLS_METADATA, ids=poll_ids())
def test_tour_is_a_known_value(row: dict):
    tour = _clean(row, "tour")
    assert tour in VALID_TOURS, f"{_clean(row, 'poll_id')} has tour '{tour}', expected one of {sorted(VALID_TOURS)}"


@pytest.mark.parametrize("row", POLLS_METADATA, ids=poll_ids())
def test_candidate_count_matches_tour(row: dict):
    """A runoff pits exactly two candidates; a first round needs at least three."""
    poll_id = _clean(row, "poll_id")
    count = len(load_results(poll_id))
    if not count:
        pytest.skip(f"{poll_id} has no result rows")

    if _clean(row, "tour") == "2nd Tour":
        assert count == 2, f"{poll_id} is a 2nd Tour poll with {count} candidates, expected 2"
    else:
        assert count >= 3, f"{poll_id} is a 1er Tour poll with only {count} candidates"


@pytest.mark.parametrize("row", POLLS_METADATA, ids=poll_ids())
def test_survey_dates_are_iso_and_ordered(row: dict):
    poll_id = _clean(row, "poll_id")
    parsed = {}
    for field in ("debut_enquete", "fin_enquete"):
        raw = _clean(row, field)
        try:
            parsed[field] = datetime.date.fromisoformat(raw)
        except ValueError:
            pytest.fail(f"{poll_id} has {field}='{raw}', expected an ISO date (YYYY-MM-DD)")

    assert parsed["debut_enquete"] <= parsed["fin_enquete"], (
        f"{poll_id} starts on {parsed['debut_enquete']} and ends on {parsed['fin_enquete']}"
    )


@pytest.mark.parametrize("row", POLLS_METADATA, ids=poll_ids())
def test_poll_id_describes_the_survey(row: dict):
    """poll_id is YYYYMMDD_MMDD_ii[_X]: full start date, then end month and day."""
    poll_id = _clean(row, "poll_id")
    match = POLL_ID_RE.match(poll_id)
    assert match, f"{poll_id} does not match YYYYMMDD_MMDD_ii[_X]"

    start = _clean(row, "debut_enquete")
    end = _clean(row, "fin_enquete")

    assert match.group("start") == start.replace("-", ""), (
        f"{poll_id} announces a start of {match.group('start')} but debut_enquete is {start}"
    )

    if poll_id in DDMM_POLL_IDS:
        pytest.skip(f"{poll_id} spells its end date DDMM")

    assert match.group("end") == f"{end[5:7]}{end[8:10]}", (
        f"{poll_id} announces an end of {match.group('end')} (MMDD) but fin_enquete is {end}"
    )


@pytest.mark.parametrize("row", POLLS_METADATA, ids=poll_ids())
def test_sample_sizes_are_consistent(row: dict):
    """Sub-samples are drawn from the sample, so none of them can be larger."""
    poll_id = _clean(row, "poll_id")
    raw_total = _clean(row, "echantillon")
    try:
        total = int(raw_total)
    except ValueError:
        pytest.fail(f"{poll_id} has echantillon='{raw_total}', expected an integer")

    assert total > 0, f"{poll_id} has a non-positive echantillon: {total}"

    for field in ("sous_echantillon1", "sous_echantillon2", "sous_echantillon3"):
        raw = _clean(row, field)
        if not raw:
            continue
        try:
            sub = int(raw)
        except ValueError:
            pytest.fail(f"{poll_id} has {field}='{raw}', expected an integer")
        assert 0 < sub <= total, f"{poll_id} has {field}={sub}, outside (0, echantillon={total}]"


@pytest.mark.parametrize("row", POLLS_METADATA, ids=poll_ids())
def test_declared_sub_populations_have_a_size(row: dict):
    """A sous_population label without its sous_echantillon leaves the base unusable."""
    poll_id = _clean(row, "poll_id")
    for index in (1, 2, 3):
        size = _clean(row, f"sous_echantillon{index}")
        label = _clean(row, f"sous_population{index}")
        assert bool(size) == bool(label), (
            f"{poll_id} has sous_echantillon{index}='{size}' and sous_population{index}='{label}'; "
            f"declare both or neither"
        )


def test_source_file_metadata_is_stated_consistently():
    """Two polls citing the same notice must agree on who ran it, when, and on whom."""
    fields = ("nom_institut", "debut_enquete", "fin_enquete", "echantillon")
    by_filename = defaultdict(set)

    for row in POLLS_METADATA:
        filename = _clean(row, "filename")
        if not filename:
            continue
        by_filename[filename].add(tuple(_clean(row, field) for field in fields))

    conflicts = {name: sorted(values) for name, values in by_filename.items() if len(values) > 1}
    unexpected = {name: values for name, values in conflicts.items() if name not in KNOWN_FILENAME_CONFLICTS}
    assert not unexpected, f"Source notices credited to different surveys: {unexpected}"

    stale = KNOWN_FILENAME_CONFLICTS - set(conflicts)
    assert not stale, f"These filenames no longer conflict, remove them from KNOWN_FILENAME_CONFLICTS: {sorted(stale)}"


@pytest.mark.parametrize("row", POLLS_METADATA, ids=poll_ids())
def test_every_poll_cites_a_source_file(row: dict):
    poll_id = _clean(row, "poll_id")
    assert _clean(row, "filename"), f"{poll_id} has no filename, its source notice cannot be traced"
