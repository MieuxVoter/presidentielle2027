"""Tests du calcul des marges d'erreur (compute_confidence_intervals.py)."""

from pathlib import Path

import pytest

from compute_confidence_intervals import ECHANTILLON_COL, POLL_CSV, SAMPLE_COLS, resolve_sample
from merge import iter_polls_meta

ROOT = Path(__file__).resolve().parents[1]


def get_poll_meta():
    """Retourne les métadonnées de tous les sondages déclarés dans polls.csv."""
    return list(iter_polls_meta(POLL_CSV))


def declared_samples(meta_row: dict) -> set:
    """Retourne toutes les tailles d'échantillon déclarées par un sondage."""
    sizes = set()
    for col in SAMPLE_COLS + [ECHANTILLON_COL]:
        value = (meta_row.get(col) or "").strip()
        if value:
            sizes.add(float(value))
    return sizes


def make_meta(**sizes) -> dict:
    """Construit une ligne de polls.csv, colonnes d'échantillon vides par défaut."""
    row = {col: "" for col in SAMPLE_COLS + [ECHANTILLON_COL]}
    row.update({k: str(v) for k, v in sizes.items()})
    return row


def test_resolve_sample_prefers_the_narrowest_sub_sample():
    """sous_echantillon3 l'emporte sur les deux autres et sur echantillon."""
    row = make_meta(sous_echantillon3=500, sous_echantillon2=776, sous_echantillon1=1206, echantillon=1300)
    assert resolve_sample(row) == 500.0


def test_resolve_sample_walks_down_to_the_first_declared_sub_sample():
    """Les sous-populations absentes sont ignorées, dans l'ordre 3, 2, 1."""
    row = make_meta(sous_echantillon2=776, sous_echantillon1=1206, echantillon=1300)
    assert resolve_sample(row) == 776.0


def test_resolve_sample_falls_back_to_echantillon():
    """Sans aucune sous-population, la base est l'échantillon total du sondage."""
    row = make_meta(echantillon=1000)
    assert resolve_sample(row) == 1000.0


def test_resolve_sample_returns_none_when_nothing_is_declared():
    assert resolve_sample(make_meta()) is None


def test_resolve_sample_does_not_inherit_from_the_previous_poll():
    """Régression: un sondage sans sous-population héritait de la base du précédent.

    La boucle de sélection ne sortait qu'en cas de succès ; quand aucune colonne
    n'était renseignée, la variable sample gardait la valeur du tour précédent.
    """
    previous = make_meta(sous_echantillon2=776, sous_echantillon1=1206, echantillon=1300)
    current = make_meta(echantillon=1000)

    assert resolve_sample(previous) == 776.0
    assert resolve_sample(current) == 1000.0, "la base doit venir du sondage lui-même"


@pytest.mark.parametrize("meta_row", get_poll_meta(), ids=lambda r: r["poll_id"])
def test_resolved_sample_belongs_to_the_poll_itself(meta_row: dict):
    """Chaque sondage se calcule sur une taille qu'il déclare lui-même."""
    sample = resolve_sample(meta_row)
    declared = declared_samples(meta_row)

    assert declared, f"{meta_row['poll_id']} ne déclare aucune taille d'échantillon"
    assert sample in declared, f"{meta_row['poll_id']} calculé sur {sample}, non déclaré parmi {sorted(declared)}"
