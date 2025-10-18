# 🤖 Auto-Détection des Nouveaux Sondages

## Vue d'ensemble

Le repository surveille automatiquement le [catalogue de la Commission des sondages](https://github.com/MieuxVoter/sondages-commission-index) et crée des issues GitHub pour chaque nouveau sondage présidentiel.

**Principe:** Un compteur (`.last_poll_count`) suit le nombre de sondages déjà traités. Le workflow compare ce compteur avec le nombre total dans le catalogue et crée des issues pour les nouveaux sondages.

## Comment ça marche

### 1. Workflow Automatique
**Fichier:** `.github/workflows/check-new-polls.yml`

- Exécution: tous les jours à 6h UTC (ou manuellement)
- Lit le compteur dans `.last_poll_count` (ex: 261)
- Récupère le catalogue (ex: 270 sondages)
- Crée des issues pour les nouveaux (sondages 262-270)
- Met à jour le compteur à 270 et le commit

### 2. Test Local
```bash
python check_new_polls.py
```

Affiche les nouveaux sondages détectés sans créer d'issues.

## Format des Issues

Chaque issue contient:
- **Fichier PDF:** Nom du fichier à vérifier (ex: `20240707_0708_hi_A.pdf`)
- **Lien direct:** URL du PDF dans le catalogue
- **Lien catalogue:** Repository `sondages-commission-index`
- **Checklist:** Étapes pour ajouter le sondage

**Labels:** `new-poll`, `automated`

## Configuration

### Modifier la fréquence
`.github/workflows/check-new-polls.yml`:
```yaml
schedule:
  - cron: '0 6 * * *'  # Tous les jours à 6h UTC
```

### Limite d'issues par exécution
Dans le workflow Python:
```python
for poll in new_polls[:10]:  # Max 10 issues
```

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
