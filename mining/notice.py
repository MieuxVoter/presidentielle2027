"""Récupération du texte d'une notice et découpage en pages.

Le texte vient en priorité du dépôt amont sondages-commission-index, qui publie
une extraction pdfplumber sous archives_txt/. Cette génération est récente : pour
les notices plus anciennes, on retombe sur une extraction locale du PDF, avec la
même commande pdfplumber que l'amont pour obtenir le même texte.

Stdlib uniquement, sauf le repli PDF qui importe pdfplumber à la demande.
"""

import re
from dataclasses import dataclass
from urllib.request import urlopen

PAGE_RE = re.compile(r"^--- page (\d+) ---\s*$")
HEADER_RE = re.compile(r"^#\s?(.*)$")
TIMEOUT = 30


@dataclass(frozen=True)
class Page:
    """Une page de notice, telle que découpée par l'extraction amont."""

    number: int
    lines: tuple

    @property
    def text(self):
        return "\n".join(self.lines)

    def numbered(self):
        """Le texte avec un numéro devant chaque ligne.

        Numéroter les lignes est ce qui permet à un petit modèle de désigner un
        emplacement sans avoir à le recopier.
        """
        return "\n".join(f"[{i}] {line}" for i, line in enumerate(self.lines, 1))


def parse_header(text):
    """Les métadonnées `# clé: valeur` en tête du fichier amont, avant la page 1."""
    header = {}
    for raw in text.splitlines():
        if PAGE_RE.match(raw):
            break
        match = HEADER_RE.match(raw)
        if not match:
            continue
        key, _, value = match.group(1).partition(":")
        if value:
            header[key.strip()] = value.strip()
    return header


def split_pages(text):
    """[Page] découpé sur les séparateurs `--- page N ---`.

    Le texte qui précède la première page (en-tête de métadonnées) est ignoré.
    """
    pages, number, lines = [], None, []
    for raw in text.splitlines():
        match = PAGE_RE.match(raw)
        if match:
            if number is not None:
                pages.append(Page(number, tuple(lines)))
            number, lines = int(match.group(1)), []
            continue
        if number is not None:
            lines.append(raw.rstrip())
    if number is not None:
        pages.append(Page(number, tuple(lines)))
    return pages


def fetch_text(url):
    """Le contenu texte d'une URL brute."""
    with urlopen(url, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8")


def extract_pdf_text(pdf_path):
    """Repli : extraire le texte d'un PDF local, comme le fait le dépôt amont.

    pdfplumber n'est importé qu'ici : le chemin nominal passe par le TXT amont et
    ne doit rien avoir à installer.
    """
    import pdfplumber

    parts = []
    with pdfplumber.open(pdf_path) as document:
        for number, page in enumerate(document.pages, 1):
            parts.append(f"--- page {number} ---\n" + (page.extract_text(layout=True) or ""))
    return "\n".join(parts)


def blob_to_raw(url, blob_base, raw_base):
    """Convertit un lien GitHub `blob` en lien `raw`.

    check_new_polls.notice_links() renvoie des liens blob, lisibles par un humain
    dans l'issue ; le téléchargement a besoin de la forme raw.
    """
    return url.replace(blob_base, raw_base) if url and url.startswith(blob_base) else url


def strip_empty(pages):
    """Écarte les pages sans aucun contenu : rien à demander à un modèle dessus."""
    return [page for page in pages if page.text.strip()]
