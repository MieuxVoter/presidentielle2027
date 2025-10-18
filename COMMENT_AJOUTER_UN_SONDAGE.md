# Comment ajouter un nouveau sondage

Ce guide explique comment ajouter un nouveau sondage au projet **presidentielle2027**.

## Structure du projet

- **candidats.csv** : liste des candidats avec leurs identifiants
- **hypotheses.csv** : scénarios avec différentes listes de candidats
- **polls.csv** : métadonnées des sondages (institut, dates, échantillon, etc.)
- **polls/*.csv** : résultats individuels par sondage
- **presidentielle2027.csv** : fichier consolidé (généré automatiquement)

## Étapes pour ajouter un sondage

### 1. Ajouter les métadonnées dans `polls.csv`

Ajoutez une nouvelle ligne avec les informations suivantes :

| Champ | Description | Exemple |
|-------|-------------|---------|
| `poll_id` | Identifiant unique au format YYYYMMDD_DDMM_ii_X | `20250326_0327_if_A` |
| `hypothese` | Identifiant du scénario (H1, H2, etc.) | `H1` |
| `nom_institut` | Nom de l'institut de sondage | `IFOP` |
| `commanditaire` | Commanditaire du sondage | `JDD` |
| `debut_enquete` | Date de début (YYYY-MM-DD) | `2025-03-26` |
| `fin_enquete` | Date de fin (YYYY-MM-DD) | `2025-03-27` |
| `echantillon` | Taille de l'échantillon | `1200` |
| `population` | Description de la population | `représentatif de la population française âgée de 18 ans et plus` |
| `tour` | Tour de scrutin | `1er Tour` |
| `filename` | Nom du fichier source (PDF, etc.) | `9912-pres-ifop-jdd.pdf` |

**Note:** Les autres colonnes (`rolling`, `media`, `sous_echantillon*`, `sous_population*`) sont optionnelles.

### 2. Créer le fichier de résultats `polls/<poll_id>.csv`

Dans le répertoire `polls/`, créez un fichier CSV nommé `<poll_id>.csv` avec la structure suivante :

```csv
candidat,intentions,erreur_sup,erreur_inf
Nathalie Arthaud,1,,
Philippe Poutou,1,,
Jean-Luc Mélenchon,12,,
Fabien Roussel,4,,
Olivier Faure,4,,
Marine Tondelier,3,,
Édouard Philippe,25,,
Laurent Wauquiez,5,,
Nicolas Dupont-Aignan,4,,
Marine Le Pen,36,,
Éric Zemmour,5,,
```

**Colonnes obligatoires :**
- `candidat` : nom complet du candidat (doit correspondre à `candidats.csv` ou `hypotheses.csv`)
- `intentions` : pourcentage d'intentions de vote (numérique ou vide)
- `erreur_sup` : erreur supérieure (optionnel)
- `erreur_inf` : erreur inférieure (optionnel)

### 3. Vérifier les candidats

Assurez-vous que tous les candidats mentionnés dans votre fichier existent dans `candidats.csv`. Si un candidat est manquant :

1. Ouvrez `candidats.csv`
2. Ajoutez une ligne avec :
   - `candidate_id` : identifiant court (ex: `EP` pour Édouard Philippe)
   - `complete_name` : nom complet
   - `name` : prénom
   - `surname` : nom de famille
   - `parti` : parti politique (optionnel)

### 4. Tester localement

Avant de pousser vos modifications, testez que le merge fonctionne :

```bash
# Installer pytest si nécessaire
pip install pytest

# Lancer les tests
pytest tests/

# Générer le CSV consolidé
python merge.py
```

Si tout fonctionne, vous devriez voir :
- ✅ Tous les tests passent
- ✅ `presidentielle2027.csv` est créé/mis à jour

### 5. Soumettre une Pull Request

1. Committez vos modifications :
   ```bash
   git add polls.csv polls/<poll_id>.csv
   git commit -m "Ajout sondage <institut> du <date>"
   ```

2. Poussez sur votre branche :
   ```bash
   git push origin ma-branche
   ```

3. Créez une Pull Request sur GitHub

### Validation automatique

Lors de la PR, GitHub Actions va :
- ✅ Vérifier la structure des fichiers CSV
- ✅ Tester que le merge fonctionne
- ✅ Valider l'intégrité des données

Une fois la PR mergée, le fichier `presidentielle2027.csv` sera automatiquement mis à jour.

## Format de nommage des poll_id

Le format recommandé est : `YYYYMMDD_DDMM_ii_X`

- `YYYYMMDD` : date de début de l'enquête
- `DDMM` : date de fin (jour et mois)
- `ii` : initiales de l'institut (ex: `if` pour IFOP, `hi` pour Harris Interactive)
- `X` : lettre pour différencier les hypothèses (A, B, C, D...)

**Exemple :** `20250326_0327_if_A`
- Sondage du 26-27 mars 2025
- Institut : IFOP
- Hypothèse A

## Questions fréquentes

**Q: Que faire si un candidat a un nom avec accent ?**  
R: Le script normalise automatiquement les accents. Utilisez le nom avec accents dans le fichier de résultats.

**Q: Puis-je laisser des cellules vides ?**  
R: Oui, les colonnes `erreur_sup` et `erreur_inf` peuvent être vides.

**Q: Comment gérer plusieurs hypothèses du même sondage ?**  
R: Créez plusieurs fichiers avec des suffixes différents (A, B, C...) et des `poll_id` distincts.

## Support

En cas de problème, ouvrez une issue sur GitHub avec :
- Le fichier CSV problématique
- Le message d'erreur complet
- Les étapes que vous avez suivies
