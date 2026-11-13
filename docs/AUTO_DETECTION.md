# 🤖 Auto-Détection des Nouveaux Sondages

## Vue d'ensemble

Le repository surveille automatiquement le [catalogue de la Commission des sondages](https://github.com/MieuxVoter/sondages-commission-index) et crée des issues GitHub pour chaque nouveau sondage présidentiel.

**Principe:** Un compteur (`.last_poll_count`) suit le nombre de sondages déjà traités. Le workflow compare ce compteur avec le nombre total dans le catalogue et crée des issues pour les nouveaux sondages.

## Comment ça marche

### 1. Workflow Automatique
**Fichier:** `.github/workflows/check-new-polls.yml`

Le workflow ne fait qu'appeler `python check_new_polls.py --create-issues` : toute la logique
(détection, format des issues, dédoublonnage) vit dans le script, en stdlib uniquement.

- Exécution: tous les jours à 9h UTC (ou manuellement)
- Lit le compteur dans `.last_poll_count` (ex: 261)
- Récupère le catalogue (ex: 270 sondages)
- Crée des issues pour les nouveaux (sondages 262-270)
- Met à jour le compteur à 270 et le commit

### 2. Test Local
```bash
python check_new_polls.py            # dry-run: affiche le corps exact des issues
python check_new_polls.py --limit 3  # n'en prévisualiser que 3
```

Aucune dépendance à installer. Le dry-run ne crée rien.

## Format des Issues

📝 **Le corps des issues est éditable sans toucher au code:**
[`docs/issue_template_nouveau_sondage.md`](issue_template_nouveau_sondage.md).
Les placeholders disponibles (`$name`, `$links`, `$filename`…) sont listés dans l'en-tête du
fichier, et `python check_new_polls.py` affiche le rendu réel pour vérifier une modification.

L'issue va droit au but: les liens vers la notice, trois cases à cocher correspondant aux
livrables, et le reste replié dans un bloc `<details>`.

- **Lien principal:** la notice en **texte** (`archives_txt/…​.txt` du catalogue)
- **Fallback:** le **PDF** (`archives/…​.pdf`), quand le texte extrait n'existe pas encore en amont
- **Repli d'aide:** format du `poll_id`, guide complet, lien vers la notice source (commission des sondages)
- **Marqueur:** `<!-- poll-file: <filename> -->` en fin de corps, utilisé pour le dédoublonnage

Le déploiement des `.txt` en amont est progressif : la colonne `txt_path` du catalogue annonce
parfois des fichiers absents, donc le script **vérifie l'existence du `.txt` (requête HEAD)**
avant d'en faire le lien principal.

**Labels:** `new-poll`, `automated`

## Configuration

### Modifier la fréquence
`.github/workflows/check-new-polls.yml`:
```yaml
schedule:
  - cron: '0 9 * * *'  # Tous les jours à 9h UTC
```

### Limite d'issues par exécution
Option `--limit` du script (défaut: 10), ou constante `DEFAULT_LIMIT` dans `check_new_polls.py`.

⚠️ Au-delà de cette limite, les sondages excédentaires sont perdus: voir
[`issue/compteur-plafond-10-issues.md`](../issue/compteur-plafond-10-issues.md).

## Déclenchement Manuel

1. **Actions** → **Check for New Presidential Polls**
2. **Run workflow** → Choisir la branche → **Run**

## Workflow Complet

```
1. [Auto] Workflow lit .last_poll_count (261)
2. [Auto] Récupère le catalogue (270 sondages)
3. [Auto] Crée 9 issues pour sondages 262-270
4. [Auto] Commit .last_poll_count avec 270
5. [Humain] Traite les issues (télécharge PDF, extrait données)
6. [Humain] Crée polls/<id>.csv et ajoute dans polls.csv
7. [Auto] Tests valident le format
8. [Auto] Merge génère presidentielle2027.csv
```

## Troubleshooting

**Pas d'issues créées?**
- Vérifier les logs du workflow
- Le compteur est peut-être déjà à jour

**Compteur incorrect?**
- Modifier manuellement `.last_poll_count`
- Commit et push

---

**Créé:** 18 octobre 2025
