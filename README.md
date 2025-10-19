# presidentielle2027

[![Validate polls and merge](https://github.com/MieuxVoter/presidentielle2027/actions/workflows/validate-polls.yml/badge.svg)](https://github.com/MieuxVoter/presidentielle2027/actions/workflows/validate-polls.yml)
![Sondages agrégés](https://img.shields.io/badge/sondages_agrégés-37-blue)

Compilation des sondages d'opinion produits à l'occasion des élections présidentielles 2027 en France.

## 📊 Données consolidées

Le fichier principal **`presidentielle2027.csv`** contient l'ensemble des résultats de sondages consolidés avec leurs métadonnées.

### Structure du fichier

Chaque ligne représente un candidat dans un sondage spécifique :

- **Métadonnées du sondage** : institut, commanditaire, dates, échantillon, hypothèse
- **Informations du candidat** : nom, parti, identifiant
- **Résultats** : intentions de vote, marges d'erreur

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
4. Testez localement avec `pytest` et `python merge.py`
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
