"""Rendu du commentaire de triage et choix du label.

La formulation vit dans docs/comment_template_mining.md : la changer ne demande
pas de toucher au code, comme pour le gabarit des issues.
"""

import re
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_FILE = ROOT / "docs" / "comment_template_mining.md"
# Commentaire d'en-tête du gabarit (mode d'emploi), retiré avant envoi.
TEMPLATE_HEADER_RE = re.compile(r"\A\s*<!--.*?-->\s*", re.DOTALL)
# Marqueur d'idempotence : un seul commentaire de triage par issue.
MARKER = "<!-- llm-mining: triage -->"

LABELS = {
    "oui": "avec-intentions-de-vote",
    "non": "sans-intentions-de-vote",
    "incertain": "intentions-a-verifier",
}
PHRASES = {
    "oui": "Oui, il y a des intentions de vote.",
    "non": "Non, il n'y a pas d'intentions de vote.",
    "incertain": "Je n'ai pas pu déterminer si cette notice contient des intentions de vote.",
}


def load_template():
    body = TEMPLATE_HEADER_RE.sub("", TEMPLATE_FILE.read_text(encoding="utf-8"))
    if "-->" in body:
        print(f"⚠️  {TEMPLATE_FILE.name}: commentaire d'en-tête mal fermé, vérifier le rendu")
    return Template(body)


def _pages(numbers):
    return ", ".join(str(n) for n in numbers)


def _safe(text, limit=2000):
    """Neutralise le texte du modèle avant de le publier.

    Il est dérivé d'un PDF tiers : il ne doit pouvoir ni injecter de HTML, ni
    refermer le commentaire, ni fabriquer le marqueur d'idempotence.
    """
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    if len(text) > limit:
        text = text[:limit].rstrip() + "\n…(réponse tronquée)"
    return text


def final_block(triage):
    """La réponse finale du modèle, telle quelle."""
    return f"```\n{_safe(triage.final, 400)}\n```" if triage.final else ""


def reasoning_block(triage):
    """La réflexion du modèle, seulement s'il y en a une."""
    if not triage.reasoning:
        return ""
    return "<details open>\n<summary>Réflexion du modèle</summary>\n\n" f"{_safe(triage.reasoning)}\n\n</details>"


def details(triage):
    """Les preuves : quelles pages portent des intentions de vote."""
    lines = []
    if triage.pages_with_intentions:
        lines.append(f"- Pages contenant des intentions de vote : **{_pages(triage.pages_with_intentions)}**")
    elif not triage.failed:
        # Ne l'affirmer que si la notice a réellement été analysée : sinon on
        # ferait passer une analyse impossible pour une absence d'intentions.
        lines.append("- Aucune page ne présente de tableau d'intentions de vote.")
    if triage.invalid_pages:
        lines.append(f"- Numéros de page cités par le modèle mais absents du document : {_pages(triage.invalid_pages)}")
    if triage.failed:
        lines.append(f"- ⚠️ {triage.failed}")
    return "\n".join(lines)


def comment(triage, model, template=None):
    """Le corps du commentaire, marqueur d'idempotence inclus."""
    template = template or load_template()
    body = template.safe_substitute(
        phrase=PHRASES[triage.verdict],
        final=final_block(triage),
        reasoning=reasoning_block(triage),
        details=details(triage),
        model=model or "inconnu",
    )
    # Les blocs vides laissent des lignes blanches en trop.
    body = re.sub(r"\n{3,}", "\n\n", body)
    return f"{body.rstrip()}\n\n{MARKER}\n"


def label(triage):
    return LABELS[triage.verdict]


def already_commented(comments):
    """True si le marqueur est déjà présent, pour ne pas commenter deux fois.

    Volontairement indépendant de find_marker_comment : « déjà traité » et
    « identifiant connu » sont deux questions distinctes.
    """
    return any(MARKER in (c.get("body") or "") for c in comments)


def find_marker_comment(comments):
    """L'identifiant du commentaire de triage déjà publié, ou None.

    Permet de réécrire ce commentaire au lieu d'en empiler un second quand le
    triage est relancé à la main.
    """
    for comment in comments:
        if MARKER in (comment.get("body") or ""):
            return comment.get("id")
    return None


def labels_to_remove(current, keep):
    """Les labels de triage à retirer de l'issue pour n'en garder qu'un.

    Un second passage peut changer le verdict : laisser l'ancien label en place
    rendrait la liste d'issues trompeuse.
    """
    mine = set(LABELS.values())
    return sorted({name for name in current if name in mine and name != keep})


def label_changes(current, triage):
    """(labels à poser, labels à retirer) pour accorder l'issue au résultat.

    Un vrai verdict remplace les autres labels de triage. Un échec, lui, n'apporte
    aucune information : il ne retire jamais rien — pas même un label corrigé à la
    main après un échec précédent — et ne signale l'issue que si elle ne porte
    encore aucun label de triage.
    """
    wanted = label(triage)
    if triage.verdict == "incertain":
        already_labelled = any(name in LABELS.values() for name in current)
        return ([] if already_labelled else [wanted]), []
    return ([] if wanted in current else [wanted]), labels_to_remove(current, wanted)
