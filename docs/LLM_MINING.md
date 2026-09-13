# Triage des notices par un modèle de langage

À l'ouverture d'une issue « nouveau sondage », un workflow demande à un modèle si la notice contient des
**intentions de vote**, publie la réponse en commentaire et pose un label. Aucun chiffre de sondage n'est
produit : le dépouillement reste manuel.

## Relancer le triage à la main

Commenter sous l'issue :

```
/triage
```

Réservé aux personnes ayant les droits d'écriture sur le dépôt — sinon n'importe qui pourrait vider le quota
d'API en commentant. Le commentaire existant est **réécrit**, jamais doublé, et le label est mis à jour si le
verdict change.

On peut aussi passer par *Actions → LLM mining - triage → Run workflow* en donnant un numéro d'issue, ce qui
a le même effet.

Conception d'ensemble et suite prévue : [ISSUE_llm_mining.md](ISSUE_llm_mining.md).

## Labels posés

| Label | Signification |
|---|---|
| `avec-intentions-de-vote` | au moins une page présente un tableau d'intentions de vote |
| `sans-intentions-de-vote` | aucune page n'en présente (popularité, cote de confiance, opinion…) |
| `intentions-a-verifier` | le modèle n'a pas répondu de façon exploitable, ou l'analyse s'est interrompue |

Ces trois labels sont à créer dans le dépôt avant d'activer le workflow.

## Configuration

Une seule clé suffit, à déclarer en secret de dépôt. Le client essaie les fournisseurs dans l'ordre et passe
au suivant en cas de quota épuisé ou de panne.

| Secret | Fournisseur | Remarque |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter | essayé en premier ; bascule aussi seul entre modèles `:free` |
| `MISTRAL_API_KEY` | Mistral | quota mensuel large, sans carte bancaire |
| `GEMINI_API_KEY` | Google Gemini | beaucoup d'appels par jour |

Sans aucune clé, le workflow s'arrête avec un avertissement au lieu d'échouer.

Réglages facultatifs (variables d'environnement) :

- `LLM_PROVIDERS` — impose l'ordre, par exemple `mistral,openrouter` ;
- `OPENROUTER_MODELS`, `MISTRAL_MODELS`, `GEMINI_MODELS` — la liste des modèles à essayer, séparés par des
  virgules. **Les catalogues gratuits changent souvent** : ce sont les premières valeurs à ajuster si le
  triage se met à échouer.

Si un appel échoue en `HTTP 404`, c'est que l'identifiant de modèle n'existe plus. Lister ceux du jour :

```bash
python - <<'EOF'
import json, urllib.request
with urllib.request.urlopen("https://openrouter.ai/api/v1/models") as r:
    for m in json.loads(r.read())["data"]:
        if m["id"].endswith(":free"):
            print(m["id"])
EOF
```

## Utilisation en local

```bash
export OPENROUTER_API_KEY=...

python mine_poll.py --issue 42          # aperçu : affiche le commentaire, ne publie rien
python mine_poll.py --txt notice.txt    # depuis un texte déjà téléchargé
python mine_poll.py --pdf notice.pdf    # depuis un PDF (voir dépendances ci-dessous)
```

### Dépendances

Le chemin nominal — `--issue` et `--txt` — n'utilise que la bibliothèque standard : **rien à installer**.

`--pdf` est la seule exception. Il extrait le texte d'un PDF local quand le dépôt amont n'a pas encore publié
sa version texte, et demande `pdfplumber`, déclaré à part comme dépendance optionnelle :

```bash
pip install -r requirements_mining.txt
```

La CI ne l'installe pas : le workflow passe toujours par le texte amont.

La publication (`--post`) demande en plus `GITHUB_TOKEN` ; elle est normalement faite par le workflow.

Le texte de la notice vient du dépôt `sondages-commission-index` (`archives_txt/`). Cette génération est
récente : pour une notice ancienne qui n'en a pas encore, télécharger le PDF et passer par `--pdf`.

## Modifier les questions ou la formulation

Aucun code à toucher :

- les questions posées au modèle sont dans [`mining/prompts/`](../mining/prompts/) ;
- le texte du commentaire est dans [comment_template_mining.md](comment_template_mining.md).

Prévisualiser le résultat : `python mine_poll.py --txt une_notice.txt`.

## Garde-fous

- Un marqueur invisible en fin de commentaire évite d'en publier deux sur la même issue.
- Le nombre d'appels par exécution est plafonné (`--max-calls`, 40 par défaut) : un quota ne peut pas être
  vidé par une notice anormalement longue.
- Le commentaire affiche les numéros de page qui justifient la réponse, et le modèle qui a répondu.
- Une réponse qui n'est pas exactement `OUI` ou `NON` est redemandée une fois, puis abandonnée — jamais
  réinterprétée.
