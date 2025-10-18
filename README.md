# presidentielle2027

[![Validate polls and merge](https://github.com/MieuxVoter/presidentielle2027/actions/workflows/validate-polls.yml/badge.svg)](https://github.com/MieuxVoter/presidentielle2027/actions/workflows/validate-polls.yml)

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

## 🚀 Utilisation

### Générer le fichier consolidé

```bash
python merge.py
```

Cette commande produit `presidentielle2027.csv` à partir de tous les sondages disponibles.

### Lancer les tests

```bash
pip install pytest
pytest
```

Les tests valident :
- La structure des fichiers CSV
- L'intégrité des données
- Le fonctionnement du merge
- L'unicité des identifiants

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

## 🛠️ Développement

### Prérequis

- Python 3.11+
- pytest (pour les tests)

### Installation développeur

```bash
git clone https://github.com/MieuxVoter/presidentielle2027.git
cd presidentielle2027
pip install -r requirements_pytests.txt
```

### Workflow de développement

1. Créez une branche : `git checkout -b ajout-sondage-ifop-avril`
2. Ajoutez vos données
3. Testez : `pytest && python merge.py`
4. Committez : `git commit -m "Ajout sondage IFOP avril 2025"`
5. Pushez et créez une PR

## 📜 Licence

Ce projet est sous licence [MIT](LICENSE).

## 🤝 Partenaires

Projet porté par **[Mieux Voter](https://mieuxvoter.fr/)** pour promouvoir des méthodes de vote alternatives et la transparence démocratique.

## 📞 Contact

Pour toute question ou suggestion :
- Ouvrez une [issue](https://github.com/MieuxVoter/presidentielle2027/issues)
- Contactez Mieux Voter : contact@mieuxvoter.fr
