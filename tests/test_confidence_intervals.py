"""Unit tests for compute_confidence_intervals and the margins it produces."""

import csv
from pathlib import Path

import pytest

import compute_confidence_intervals as cci


ROOT = Path(__file__).resolve().parents[1]
POLLS_CSV = ROOT / "polls.csv"
POLLS_DIR = ROOT / "polls"


def _clean(row: dict, key: str) -> str:
    return (row.get(key) or "").strip()


POLLS_METADATA = cci.load_polls_metadata(POLLS_CSV)
POLL_IDS = [_clean(row, "poll_id") for row in POLLS_METADATA]


class TestConfidenceMargin:
    def test_margin_matches_the_textbook_formula(self):
        # 1.96 * sqrt(0.10 * 0.90 / 1000) = 1.86 points
        sup, inf = cci.confidence_margin(10, 1000)
        assert sup == 1.86
        assert inf == -1.86

    def test_margin_shrinks_as_the_sample_grows(self):
        small, _ = cci.confidence_margin(10, 500)
        large, _ = cci.confidence_margin(10, 4000)
        assert small > large

    def test_lower_margin_cannot_take_a_share_below_zero(self):
        """A candidate at 0.5% cannot lose more than 0.5 points."""
        sup, inf = cci.confidence_margin(0.5, 500)
        assert sup > 0.5, "this case is only interesting when the raw margin exceeds the share"
        assert inf == -0.5

    def test_both_margins_are_expressed_in_percentage_points(self):
        sup, inf = cci.confidence_margin(0.5, 500)
        assert abs(inf) <= 100 and abs(sup) <= 100

    def test_zero_share_has_no_margin(self):
        assert cci.confidence_margin(0, 1000) == (0.0, 0.0)

    def test_non_positive_sample_is_rejected(self):
        with pytest.raises(ValueError):
            cci.confidence_margin(10, 0)


class TestResolveSample:
    def test_prefers_the_narrowest_declared_sub_sample(self):
        meta = {
            "echantillon": "2000",
            "sous_echantillon1": "1800",
            "sous_echantillon2": "1500",
            "sous_echantillon3": "1200",
        }
        assert cci.resolve_sample(meta) == 1200

    def test_falls_back_through_the_sub_samples(self):
        assert cci.resolve_sample({"echantillon": "2000", "sous_echantillon1": "1800"}) == 1800

    def test_falls_back_to_the_full_sample(self):
        """Without this, a poll with no sub-sample used to inherit the previous poll's size."""
        assert cci.resolve_sample({"echantillon": "1000"}) == 1000

    def test_returns_none_when_no_size_is_usable(self):
        assert cci.resolve_sample({"echantillon": "", "sous_echantillon1": "n/a"}) is None


@pytest.mark.parametrize("poll_id", POLL_IDS)
def test_margins_are_signed_and_symmetric(poll_id: str):
    """erreur_sup is positive, erreur_inf negative, and both describe the same interval.

    They differ only when the lower margin is clamped at the candidate's share.
    """
    path = POLLS_DIR / f"{poll_id}.csv"
    if not path.exists():
        pytest.skip(f"{poll_id} has no result file")

    with path.open("r", encoding="utf-8") as f:
        rows = [row for row in csv.DictReader(f) if _clean(row, "candidat")]

    for row in rows:
        candidat = _clean(row, "candidat")
        raw_sup, raw_inf = _clean(row, "erreur_sup"), _clean(row, "erreur_inf")
        if not raw_sup and not raw_inf:
            continue

        sup, inf = float(raw_sup), float(raw_inf)
        assert sup >= 0, f"{poll_id} / {candidat}: erreur_sup should be positive, got {sup}"
        assert inf <= 0, f"{poll_id} / {candidat}: erreur_inf should be negative, got {inf}"

        share = float(_clean(row, "intentions")) if _clean(row, "intentions") else None
        if share is not None and abs(inf) < sup:
            assert abs(inf) == pytest.approx(share, abs=0.01), (
                f"{poll_id} / {candidat}: erreur_inf ({inf}) is smaller than erreur_sup ({sup}) "
                f"without being clamped at the share ({share})"
            )
        else:
            assert abs(sup + inf) < 0.02, f"{poll_id} / {candidat}: margins are not symmetric ({sup}, {inf})"


@pytest.mark.parametrize("row", POLLS_METADATA, ids=POLL_IDS)
def test_margins_match_the_declared_sample(row: dict):
    """Recomputing from polls.csv must reproduce what is committed."""
    poll_id = _clean(row, "poll_id")
    path = POLLS_DIR / f"{poll_id}.csv"
    if not path.exists():
        pytest.skip(f"{poll_id} has no result file")

    sample = cci.resolve_sample(row)
    assert sample is not None, f"{poll_id} declares no usable sample size"

    with path.open("r", encoding="utf-8") as f:
        results = [r for r in csv.DictReader(f) if _clean(r, "candidat")]

    for result in results:
        share = _clean(result, "intentions")
        if not share:
            continue
        expected_sup, expected_inf = cci.confidence_margin(float(share), sample)
        assert float(_clean(result, "erreur_sup")) == pytest.approx(expected_sup, abs=0.01), (
            f"{poll_id} / {_clean(result, 'candidat')}: erreur_sup does not match a sample of {sample}"
        )
        assert float(_clean(result, "erreur_inf")) == pytest.approx(expected_inf, abs=0.01), (
            f"{poll_id} / {_clean(result, 'candidat')}: erreur_inf does not match a sample of {sample}"
        )
