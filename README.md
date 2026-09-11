# presidentielle2027
![Sondages agrégés](https://img.shields.io/badge/sondages_agrégés-228-blue)

Compilation des sondages d'intention de vote à l'occasion des élections présidentielles 2027 en France.

## 📊 Données consolidées

Deux fichiers principaux contiennent l'ensemble des résultats de sondages consolidés avec leurs métadonnées:

➡️ [Le fichier CSV des sondages pour l'élection présidentielle 2027](presidentielle2027.csv)

➡️ [Le flux JSON des sondages pour l'élection présidentielle 2027](https://raw.githubusercontent.com/MieuxVoter/presidentielle2027/refs/heads/main/presidentielle2027.json)

## 🏆 TOP 3 des hypothèses les plus évaluées

Classement des scénarios (hypothèses de candidatures) les plus fréquemment testés par les instituts de sondage. Mis à jour automatiquement.

<!-- TOP_HYPOTHESES:START -->
| Rang | Sondages | Candidats (🥇) / Diff vs 🥇 (🥈🥉) |
|:----:|:--------:|----------------------------------|
| 🥇 | 11 | Bruno Retailleau, Fabien Roussel, Jean-Luc Mélenchon, Marine Le Pen, Marine Tondelier, Nathalie Arthaud, Nicolas Dupont-Aignan, Raphaël Glucksmann, Édouard Philippe, Éric Zemmour |
| 🥈 | 11 | $\textcolor{green}{\text{+ Gabriel Attal}}$, $\textcolor{red}{\text{− Édouard Philippe}}$ |
| 🥉 | 9 | $\textcolor{green}{\text{+ Jordan Bardella}}$, $\textcolor{red}{\text{− Marine Le Pen}}$ |

> 🥇 liste complète des candidats (référence). 🥈🥉 diff vs 🥇 : $\textcolor{green}{\text{+ ajouté}}$ en vert, $\textcolor{red}{\text{− retiré}}$ en rouge.
<!-- TOP_HYPOTHESES:END -->

## 🗂️ Structure du projet

```
presidentielle2027/
├── candidats.csv              # Liste des candidats avec identifiants
├── hypotheses.csv             # Scénarios avec différentes listes de candidats
├── polls.csv                  # Métadonnées des sondages
├── polls/                     # Résultats individuels par sondage
│   ├── 20240707_0708_hi_A.csv
│   ├── 20250326_0327_if_A.csv
│   └── ...
├── presidentielle2027.csv     # Fichier consolidé (généré automatiquement)
├── merge.py                   # Script de fusion des données
└── tests/                     # Suite de tests
```

## ➕ Contribuer

### Ajouter un nouveau sondage

Consultez le guide détaillé : **[COMMENT_AJOUTER_UN_SONDAGE.md](COMMENT_AJOUTER_UN_SONDAGE.md)**

En résumé :
1. Ajoutez une ligne dans `polls.csv` avec les métadonnées
2. Créez `polls/<poll_id>.csv` avec les résultats
3. Vérifiez que les candidats existent dans `candidats.csv`
4. Testez localement avec `pytest` et `python merge.py` (vérification locale avant PR)
5. Soumettez une Pull Request

### Validation automatique

GitHub Actions valide automatiquement :
- ✅ Format des fichiers CSV
- ✅ Cohérence des données
- ✅ Génération du fichier consolidé

Une fois mergé, `presidentielle2027.csv` est mis à jour automatiquement.

## 📋 Format des données

### candidats.csv

| Colonne | Description |
|---------|-------------|
| `candidate_id` | Identifiant court unique (ex: `EP`, `MLP`) |
| `complete_name` | Nom complet du candidat |
| `name` | Prénom |
| `surname` | Nom de famille |
| `parti` | Parti politique |

### polls.csv

| Colonne | Description |
|---------|-------------|
| `poll_id` | Identifiant unique (format: `YYYYMMDD_DDMM_ii_X`) |
| `hypothese` | Scénario (H1, H2, etc.) |
| `nom_institut` | Institut de sondage |
| `commanditaire` | Commanditaire |
| `debut_enquete` | Date de début (YYYY-MM-DD) |
| `fin_enquete` | Date de fin (YYYY-MM-DD) |
| `echantillon` | Taille échantillon |
| `population` | Description population |
| `tour` | Tour de scrutin |
| `filename` | Source (PDF, etc.) |

### polls/<poll_id>.csv

| Colonne | Description |
|---------|-------------|
| `candidat` | Nom du candidat |
| `intentions` | % intentions de vote |
| `erreur_sup` | Marge erreur supérieure (optionnel) |
| `erreur_inf` | Marge erreur inférieure (optionnel) |

## 📜 Licence

Ce projet est sous licence [MIT](LICENSE).

## 🗳️ Marre des sondages qui demandent de choisir un seul candidat ?

Les sondages actuels reposent principalement sur le **scrutin uninominal** : un candidat choisi, tous les autres écartés.

**MieuxVoter soutient le développement du Jugement majoritaire**, une méthode qui permet d'**exprimer avec nuance son opinion sur tous les candidats**.

> 🗳️ **[👉 Je soutiens MieuxVoter](https://www.paypal.com/donate/?hosted_button_id=QD6U4D323WV4S)**

*Chaque soutien contribue au développement du **Jugement majoritaire** et à l'émergence d'une autre façon de mesurer l'opinion.*

**Pourquoi on fait ça ?** Car on souhaite comparer les sondages classiques avec des sondages au jugement majoritaire.

<a href="https://www.paypal.com/donate/?hosted_button_id=QD6U4D323WV4S" target="_blank">
  <img width="2056" height="765" alt="Soutenir MieuxVoter" src="https://github.com/user-attachments/assets/33925f13-4fdf-4346-9d7b-973216073332" />
</a>
