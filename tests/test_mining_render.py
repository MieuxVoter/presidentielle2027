"""Rendu du commentaire et choix du label."""

import pytest

from mining import render
from mining.steps import Triage


def test_verdict_oui_rend_la_phrase_et_le_label():
    triage = Triage(pages_with_intentions=[12, 13])
    assert triage.verdict == "oui"
    assert render.label(triage) == "avec-intentions-de-vote"
    assert "Oui, il y a des intentions de vote." in render.comment(triage, "un-modele")


def test_verdict_non_rend_la_phrase_et_le_label():
    triage = Triage(answered_no=True)
    assert render.label(triage) == "sans-intentions-de-vote"
    assert "Non, il n'y a pas d'intentions de vote." in render.comment(triage, "un-modele")


def test_verdict_incertain_ne_tranche_pas():
    # Ni pages retenues ni NON explicite : on ne conclut pas à la place du modèle.
    triage = Triage(failed="le modèle n'a pas répondu dans le format demandé")
    assert render.label(triage) == "intentions-a-verifier"
    assert "n'ai pas pu déterminer" in render.comment(triage, "un-modele")


def test_silence_du_modele_ne_vaut_pas_non():
    assert Triage().verdict == "incertain"


def test_le_commentaire_cite_les_pages_en_preuve():
    body = render.comment(Triage(pages_with_intentions=[12, 13]), "un-modele")
    assert "12, 13" in body


def test_le_commentaire_signale_les_pages_inventees():
    body = render.comment(Triage(pages_with_intentions=[12], invalid_pages=[99]), "un-modele")
    assert "99" in body and "absents du document" in body


def test_le_commentaire_signale_une_analyse_interrompue():
    body = render.comment(Triage(failed="budget épuisé après 40 appels"), "un-modele")
    assert "budget épuisé" in body


def test_le_commentaire_nomme_le_modele_et_avertit():
    body = render.comment(Triage(pages_with_intentions=[1]), "mon-modele:free")
    assert "mon-modele:free" in body
    assert "à vérifier" in body


def test_le_commentaire_porte_le_marqueur_d_idempotence():
    assert render.MARKER in render.comment(Triage(), "un-modele")


def test_le_mode_d_emploi_du_gabarit_ne_fuit_pas():
    body = render.comment(Triage(), "un-modele")
    assert "Placeholders disponibles" not in body
    assert "$phrase" not in body


@pytest.mark.parametrize(
    "comments,attendu",
    [
        ([], False),
        ([{"body": "un avis humain"}], False),
        ([{"body": f"déjà passé\n{render.MARKER}"}], True),
        ([{"body": None}, {"body": render.MARKER}], True),
    ],
)
def test_already_commented(comments, attendu):
    assert render.already_commented(comments) is attendu


def test_reponse_finale_affichee_telle_quelle():
    body = render.comment(Triage(pages_with_intentions=[12], final="OUI\nPAGES: 12"), "un-modele")
    assert "```\nOUI\nPAGES: 12\n```" in body


def test_reflexion_affichee_seulement_si_elle_existe():
    sans = render.comment(Triage(answered_no=True, final="NON"), "un-modele")
    assert "Réflexion du modèle" not in sans

    avec = render.comment(Triage(answered_no=True, final="NON", reasoning="Le document est un baromètre."), "m")
    assert "<details open>" in avec and "baromètre" in avec


def test_le_texte_du_modele_ne_peut_pas_injecter_de_html():
    piege = "<img src=x onerror=alert(1)> et <!-- llm-mining: triage -->"
    body = render.comment(Triage(answered_no=True, final="NON", reasoning=piege), "un-modele")
    assert "<img" not in body
    assert body.count(render.MARKER) == 1


def test_une_reflexion_tres_longue_est_tronquee():
    body = render.comment(Triage(answered_no=True, final="NON", reasoning="a" * 5000), "un-modele")
    assert "réponse tronquée" in body
