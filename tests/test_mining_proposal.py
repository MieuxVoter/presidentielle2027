"""Assemblage et écriture append-only d'une proposition validée."""

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from mining import csvio, extraction, proposal

ROOT = Path(__file__).resolve().parents[1]


def _methodology():
    return extraction.Methodology(
        "OpinionWay",
        "CNews",
        "2099-09-09",
        "2099-09-10",
        1001,
        935,
        "représentatif de la population française âgée de 18 ans et plus",
        "source dates",
        "source sample",
    )


def _table():
    return extraction.ExtractedTable(
        2,
        "2nd Tour",
        (("certains d'aller voter", 690),),
        (
            extraction.CandidateValue("Édouard Philippe", Decimal("50"), "Édouard Philippe 50"),
            extraction.CandidateValue("Marine Le Pen", Decimal("50"), "Marine Le Pen 50"),
        ),
    )


def _copy_data(tmp_path):
    for name in ("candidats.csv", "hypotheses.csv", "polls.csv"):
        shutil.copy(ROOT / name, tmp_path / name)
    shutil.copytree(ROOT / "polls", tmp_path / "polls")


def test_build_reutilise_l_hypothese_existante_et_le_code_institut(tmp_path):
    _copy_data(tmp_path)
    built = proposal.build("future.pdf", _methodology(), [_table()], tmp_path)
    assert built.polls[0]["hypothese"] == "H2_2"
    assert built.polls[0]["poll_id"] == "20990909_0910_ow_2A"
    assert built.hypotheses == [] and built.candidates == []


def test_apply_ajoute_sans_reformater_les_octets_existants(tmp_path):
    _copy_data(tmp_path)
    original = (tmp_path / "polls.csv").read_bytes()
    built = proposal.build("future.pdf", _methodology(), [_table()], tmp_path)
    csvio.apply(built, tmp_path)
    updated = (tmp_path / "polls.csv").read_bytes()
    assert updated.startswith(original)
    assert (tmp_path / "polls" / "20990909_0910_ow_2A.csv").exists()
    assert "Édouard Philippe,50,," in (tmp_path / "polls" / "20990909_0910_ow_2A.csv").read_text(encoding="utf-8")


def _second_tour(page, left, right):
    return extraction.ExtractedTable(
        page,
        "2nd Tour",
        (),
        (
            extraction.CandidateValue(left, Decimal("40"), f"{left} 40"),
            extraction.CandidateValue(right, Decimal("60"), f"{right} 60"),
        ),
    )


def test_une_proposition_incomplete_garde_ses_tableaux_et_liste_les_manques(tmp_path):
    # Cas réel, issue #194 : quota épuisé à la page 40, deux tableaux déjà vérifiés.
    _copy_data(tmp_path)
    built = proposal.build("future.pdf", _methodology(), [_table()], tmp_path, missing=["page 40 : quota épuisé"])
    assert [poll["poll_id"] for poll in built.polls] == ["20990909_0910_ow_2A"]
    assert built.missing == ["page 40 : quota épuisé"]


def test_une_relance_complete_sans_dupliquer_les_tableaux_deja_enregistres(tmp_path):
    _copy_data(tmp_path)
    csvio.apply(proposal.build("future.pdf", _methodology(), [_table()], tmp_path), tmp_path)
    melenchon = _second_tour(5, "Jean-Luc Mélenchon", "Marine Le Pen")
    built = proposal.build("future.pdf", _methodology(), [_table(), melenchon], tmp_path)
    # Le tableau déjà fusionné n'est pas reproposé ; le nouveau prend la lettre libre suivante.
    assert [(poll["poll_id"], poll["hypothese"]) for poll in built.polls] == [("20990909_0910_ow_2B", "H2_9")]
    assert built.already_present == ["page 2 : H2_2 déjà enregistrée pour future.pdf"]
    csvio.apply(built, tmp_path)


def test_une_notice_entierement_enregistree_ne_propose_rien(tmp_path):
    _copy_data(tmp_path)
    csvio.apply(proposal.build("future.pdf", _methodology(), [_table()], tmp_path), tmp_path)
    with pytest.raises(proposal.ProposalError, match="déjà enregistrés"):
        proposal.build("future.pdf", _methodology(), [_table()], tmp_path)
