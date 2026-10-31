"""Tests du calcul des marges d'erreur (compute_confidence_intervals.py)."""

import pytest

from compute_confidence_intervals import (
    ECHANTILLON_COL,
    FOLDER,
    POLL_CSV,
    SAMPLE_COLS,
    confidence_margin,
    resolve_sample,
)
from merge import iter_polls_meta, read_poll_results


def get_poll_meta():
    """Retourne les métadonnées de tous les sondages déclarés dans polls.csv."""
    return list(iter_polls_meta(POLL_CSV))


def get_committed_polls():
    """Retourne (métadonnées, résultats commités) de chaque sondage ayant un fichier."""
    pairs = []
    for meta_row in get_poll_meta():
        poll_path = FOLDER / f"{meta_row['poll_id']}.csv"
        if poll_path.exists():
            pairs.append((meta_row, read_poll_results(poll_path)))
    return pairs


COMMITTED_POLLS = get_committed_polls()
COMMITTED_POLL_IDS = [meta_row["poll_id"] for meta_row, _ in COMMITTED_POLLS]


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


def test_confidence_margin_is_symmetric_in_the_common_case():
    """Hors bridage, la borne basse est l'opposée de la borne haute."""
    lower, upper = confidence_margin(12.0, 1000)
    assert upper == 2.01
    assert lower == -upper


def test_confidence_margin_lower_bound_is_capped_at_minus_the_score():
    """Régression: la borne bridée était renvoyée en proportion brute, positive.

    Un candidat à 0,5 % ne peut pas perdre plus de 0,5 point. Le garde-fou est
    conservé, mais exprimé en points de pourcentage négatifs comme le reste de
    la fonction — et non 0.005.
    """
    lower, upper = confidence_margin(0.5, 500)

    assert upper > 0.5, "ce cas n'a de sens que si la marge dépasse le score"
    assert lower == -0.5


@pytest.mark.parametrize("intentions", [0.0, 0.5, 1.0, 12.0, 36.5, 100.0])
def test_confidence_margin_lower_bound_is_never_positive(intentions: float):
    """La borne basse décrit une perte: elle ne peut jamais être positive."""
    lower, _ = confidence_margin(intentions, 1000)
    assert lower <= 0


@pytest.mark.parametrize("intentions", [0.5, 1.0, 12.0, 36.5])
def test_confidence_margin_never_sends_a_candidate_below_zero(intentions: float):
    """Le score augmenté de la borne basse reste positif ou nul."""
    lower, _ = confidence_margin(intentions, 1000)
    assert intentions + lower >= 0


@pytest.mark.parametrize("meta_row", get_poll_meta(), ids=lambda r: r["poll_id"])
def test_resolved_sample_belongs_to_the_poll_itself(meta_row: dict):
    """Chaque sondage se calcule sur une taille qu'il déclare lui-même."""
    sample = resolve_sample(meta_row)
    declared = declared_samples(meta_row)

    assert declared, f"{meta_row['poll_id']} ne déclare aucune taille d'échantillon"
    assert sample in declared, f"{meta_row['poll_id']} calculé sur {sample}, non déclaré parmi {sorted(declared)}"


@pytest.mark.parametrize("meta_row, rows", COMMITTED_POLLS, ids=COMMITTED_POLL_IDS)
def test_committed_margins_describe_a_valid_interval(meta_row: dict, rows: list):
    """erreur_sup est positive, erreur_inf négative, et les deux sont cohérentes.

    Les deux bornes sont symétriques, sauf quand la borne basse est bridée au
    score du candidat — auquel cas elle vaut exactement -score.
    """
    poll_id = meta_row["poll_id"]
    for row in rows:
        sup, inf = (row.get("erreur_sup") or "").strip(), (row.get("erreur_inf") or "").strip()
        if not sup or not inf:
            # La CI post-merge les renseigne : une PR de contributeur les laisse vides.
            continue

        sup, inf = float(sup), float(inf)
        intentions = float(row["intentions"])
        label = f"{poll_id} / {row['candidat']}"

        assert sup >= 0, f"{label}: erreur_sup négative ({sup})"
        assert inf <= 0, f"{label}: erreur_inf positive ({inf})"
        assert intentions + inf >= 0, f"{label}: la borne basse passe sous zéro"

        if sup <= intentions:
            assert inf == pytest.approx(-sup), f"{label}: bornes non symétriques ({inf} vs {-sup})"
        else:
            assert inf == pytest.approx(-intentions), f"{label}: borne basse non bridée au score"


@pytest.mark.parametrize("meta_row, rows", COMMITTED_POLLS, ids=COMMITTED_POLL_IDS)
def test_committed_margins_match_the_declared_sample(meta_row: dict, rows: list):
    """Chaque marge commitée est recalculable depuis l'échantillon de polls.csv.

    C'est ce test qui attrape une marge calculée sur la mauvaise base — par
    exemple héritée du sondage précédent.
    """
    poll_id = meta_row["poll_id"]
    sample = resolve_sample(meta_row)
    assert sample, f"{poll_id} ne déclare aucune taille d'échantillon"

    for row in rows:
        sup, inf = (row.get("erreur_sup") or "").strip(), (row.get("erreur_inf") or "").strip()
        if not sup or not inf:
            continue

        expected_inf, expected_sup = confidence_margin(float(row["intentions"]), sample)
        label = f"{poll_id} / {row['candidat']} (base {sample:g})"

        assert float(sup) == pytest.approx(expected_sup), f"{label}: erreur_sup {sup} attendue {expected_sup}"
        assert float(inf) == pytest.approx(expected_inf), f"{label}: erreur_inf {inf} attendue {expected_inf}"
