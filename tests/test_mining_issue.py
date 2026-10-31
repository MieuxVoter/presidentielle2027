"""Lecture du fichier de notice porté par une issue. Aucun accès réseau."""

import pytest

import mine_poll

RECENT = """## 📊 Un sondage

📝 **[Notice en texte](https://example.test/a.txt)**

<!-- poll-file: 10260-pres-iv-opinionway-cnews-11-septembre.pdf -->
"""

# Format des issues ouvertes avant l'introduction du marqueur : c'est celui-ci
# qui a fait échouer le premier passage du workflow en production.
ANCIEN = """## Nouveau sondage présidentiel détecté

**Fichier PDF à vérifier:** `10166a-pres-iv-opinionway-lopinion-30-mars.pdf`

**URL PDF:** http://www.commission-des-sondages.fr/notices/files/notices/2026/mars/10166a.pdf
"""


@pytest.mark.parametrize(
    "corps,attendu",
    [
        (RECENT, "10260-pres-iv-opinionway-cnews-11-septembre.pdf"),
        (ANCIEN, "10166a-pres-iv-opinionway-lopinion-30-mars.pdf"),
        ("une issue ordinaire, sans notice", None),
        ("", None),
        (None, None),
    ],
)
def test_poll_filename_from_body(corps, attendu):
    assert mine_poll.poll_filename_from_body(corps) == attendu


def test_le_marqueur_recent_prime_sur_l_ancien():
    corps = ANCIEN + "\n<!-- poll-file: recent.pdf -->\n"
    assert mine_poll.poll_filename_from_body(corps) == "recent.pdf"
