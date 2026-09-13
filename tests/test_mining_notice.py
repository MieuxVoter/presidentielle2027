"""Découpage du texte d'une notice. Aucun accès réseau."""

from pathlib import Path

import pytest

from mining import notice

FIXTURE = Path(__file__).parent / "fixtures" / "notices" / "mini_notice.txt"
TEXT = FIXTURE.read_text(encoding="utf-8")


def test_parse_header_lit_les_metadonnees():
    header = notice.parse_header(TEXT)
    assert header["name"] == "Mini notice de test"
    assert header["categorie"] == "Pres"
    assert header["source_pdf"].endswith(".pdf")


def test_parse_header_ignore_le_corps():
    # "Publié" apparaît dans une page, pas dans l'en-tête : il ne doit pas remonter.
    assert all("Publié" not in key for key in notice.parse_header(TEXT))


def test_split_pages_numerote_les_pages():
    pages = notice.split_pages(TEXT)
    assert [p.number for p in pages] == [1, 2, 3, 4]


def test_split_pages_ignore_l_entete():
    first = notice.split_pages(TEXT)[0]
    assert "notice commission des sondages" not in first.text


def test_split_pages_sur_texte_sans_separateur():
    assert notice.split_pages("du texte sans page") == []


def test_strip_empty_retire_les_pages_vides():
    pages = notice.strip_empty(notice.split_pages(TEXT))
    assert [p.number for p in pages] == [1, 2, 3]


def test_page_text_conserve_les_lignes():
    page = notice.split_pages(TEXT)[1]
    assert "Jean-Luc Mélenchon" in page.text
    assert "<1%" in page.text


def test_numbered_prefixe_chaque_ligne():
    page = notice.split_pages(TEXT)[1]
    lines = page.numbered().splitlines()
    assert lines[0].startswith("[1] ")
    assert len(lines) == len(page.lines)


@pytest.mark.parametrize(
    "url,attendu",
    [
        ("https://github.com/o/r/blob/main/a/b.txt", "https://raw.githubusercontent.com/o/r/main/a/b.txt"),
        ("https://example.org/ailleurs.txt", "https://example.org/ailleurs.txt"),
        (None, None),
    ],
)
def test_blob_to_raw(url, attendu):
    blob = "https://github.com/o/r/blob/main/"
    raw = "https://raw.githubusercontent.com/o/r/main/"
    assert notice.blob_to_raw(url, blob, raw) == attendu
