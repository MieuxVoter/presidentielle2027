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


def test_le_commentaire_affiche_le_statut_de_la_pr_sans_html_injecte():
    body = render.comment(
        Triage(pages_with_intentions=[12]),
        "un-modele",
        pr="> ✅ PR brouillon : [#42](https://example.test/42) <script>",
    )
    assert "PR brouillon" in body and "[#42](https://example.test/42)" in body
    assert "<script>" not in body


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


def test_find_marker_comment_renvoie_l_identifiant():
    comments = [{"id": 1, "body": "humain"}, {"id": 2, "body": f"triage\n{render.MARKER}"}]
    assert render.find_marker_comment(comments) == 2


def test_find_marker_comment_absent():
    assert render.find_marker_comment([{"id": 1, "body": "humain"}]) is None


@pytest.mark.parametrize(
    "courants,garde,attendu",
    [
        (["new-poll", "avec-intentions-de-vote"], "sans-intentions-de-vote", ["avec-intentions-de-vote"]),
        (["new-poll", "sans-intentions-de-vote"], "sans-intentions-de-vote", []),
        (["new-poll", "automated"], "avec-intentions-de-vote", []),
        # Un verdict qui change ne doit pas laisser l'ancien label derrière lui.
        (
            ["avec-intentions-de-vote", "intentions-a-verifier"],
            "sans-intentions-de-vote",
            ["avec-intentions-de-vote", "intentions-a-verifier"],
        ),
    ],
)
def test_labels_to_remove(courants, garde, attendu):
    assert render.labels_to_remove(courants, garde) == attendu


def test_labels_to_remove_ne_touche_pas_aux_labels_du_depot():
    courants = ["new-poll", "automated", "bug", "avec-intentions-de-vote"]
    assert render.labels_to_remove(courants, "avec-intentions-de-vote") == []


def test_une_analyse_impossible_ne_passe_pas_pour_une_absence_d_intentions():
    # Le piège : « aucune page ne présente d'intentions » alors que rien n'a été lu.
    body = render.comment(Triage(failed="le texte n'est pas encore publié en amont."), "un-modele")
    assert "Aucune page ne présente" not in body
    assert "pas encore publié" in body
    assert render.label(Triage(failed="peu importe")) == "intentions-a-verifier"


def test_label_changes_un_vrai_verdict_remplace_les_autres():
    courants = ["new-poll", "intentions-a-verifier"]
    attendu = (["avec-intentions-de-vote"], ["intentions-a-verifier"])
    assert render.label_changes(courants, Triage(pages_with_intentions=[3])) == attendu


def test_label_changes_un_echec_ne_retire_jamais_la_correction_humaine():
    # Cas réel, issue #194 : « avec » posé à la main après un échec du modèle.
    # Un nouvel échec ne doit pas l'effacer.
    courants = ["new-poll", "automated", "avec-intentions-de-vote"]
    assert render.label_changes(courants, Triage(failed="réponse coupée")) == ([], [])


def test_label_changes_un_echec_signale_une_issue_encore_vierge():
    assert render.label_changes(["new-poll"], Triage(failed="réponse coupée")) == (["intentions-a-verifier"], [])


def test_label_changes_rien_a_faire_si_deja_en_place():
    assert render.label_changes(["sans-intentions-de-vote"], Triage(answered_no=True)) == ([], [])
