# Triage des notices par un modèle de langage

À l'ouverture d'une issue « nouveau sondage », un workflow pose **une seule question** à un modèle de langage
sur le texte entier de la notice : contient-elle des intentions de vote pour la présidentielle 2027, et sur
quelles pages ? La réponse est publiée en commentaire sous l'issue, et un label est posé.

Aucun chiffre de sondage n'est produit : le triage sert à savoir quelles notices méritent d'être dépouillées.
Le dépouillement lui-même reste manuel.

Conception d'ensemble et suite prévue : [ISSUE_llm_mining.md](ISSUE_llm_mining.md).

## Déclencheurs

| Quand | Condition | Si un commentaire existe déjà |
|---|---|---|
| Ouverture d'une issue | label `new-poll` | il est laissé tel quel |
| Commentaire `/triage` | droits d'écriture sur le dépôt | il est **réécrit** |
| *Actions → LLM mining - triage → Run workflow* | numéro d'issue | il est **réécrit** |

`/triage` doit **ouvrir une ligne** du commentaire, mais peut suivre du texte : « J'essaie à nouveau. » puis
`/triage` à la ligne suivante déclenche bien le triage. Une simple mention au fil d'une phrase, non.

La commande est réservée aux personnes ayant les droits d'écriture : sur un dépôt public, n'importe qui
pourrait sinon vider le quota d'API en commentant en boucle.

`/triage` fonctionne sur n'importe quelle issue, pas seulement celles étiquetées `new-poll`. En revanche
l'issue doit indiquer de quelle notice il s'agit, dans l'un des deux formats produits par
`check_new_polls.py` — le marqueur `<!-- poll-file: … -->` des issues récentes, ou le
`**Fichier PDF à vérifier:**` des plus anciennes.

## Labels posés

| Label | Signification |
|---|---|
| `avec-intentions-de-vote` | au moins une page présente un tableau d'intentions de vote |
| `sans-intentions-de-vote` | aucune n'en présente (popularité, cote de confiance, opinion…) |
| `intentions-a-verifier` | le modèle n'a pas répondu de façon exploitable, ou la notice n'a pas pu être lue |

**Ces trois labels sont à créer dans le dépôt** avant d'activer le workflow, sinon la pose échoue.

Un vrai verdict (`avec` ou `sans`) remplace les autres labels de triage. Un échec, lui, n'apporte aucune
information : il ne retire **jamais** un label — pas même celui qu'un humain a corrigé à la main — et ne
pose `intentions-a-verifier` que sur une issue qui ne porte encore aucun label de triage.

## D'où vient le texte de la notice

Le dépôt amont `sondages-commission-index` publie une extraction `pdfplumber` sous `archives_txt/`. Cette
génération est récente et n'a pas été faite rétroactivement : la grande majorité des notices n'en ont pas
encore. Dans ce cas le PDF amont est téléchargé et extrait à la volée, avec la même commande `pdfplumber`,
pour obtenir le même texte.

Si ni l'un ni l'autre n'est disponible, un commentaire l'explique sous l'issue et le label
`intentions-a-verifier` est posé — le workflow n'échoue pas, un job rouge n'informerait personne.

## Configuration

Une seule clé suffit, en secret de dépôt (*Settings → Secrets and variables → **Actions***). Le client essaie
les fournisseurs dans l'ordre et passe au suivant en cas de quota épuisé ou de panne.

| Secret | Fournisseur | Remarque |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter | essayé en premier ; bascule aussi seul entre modèles `:free` |
| `MISTRAL_API_KEY` | Mistral | quota mensuel large, sans carte bancaire |
| `GEMINI_API_KEY` | Google Gemini | beaucoup d'appels par jour |

Sans aucune clé, le workflow s'arrête avec un avertissement au lieu d'échouer.

Réglages facultatifs (variables d'environnement) :

- `LLM_PROVIDERS` — impose l'ordre, par exemple `mistral,openrouter` ;
- `OPENROUTER_MODELS`, `MISTRAL_MODELS`, `GEMINI_MODELS` — les modèles à essayer, séparés par des virgules.

**Les catalogues gratuits changent souvent.** Si un appel échoue en `HTTP 404`, c'est que l'identifiant de
modèle n'existe plus. Lister ceux du jour :

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

python mine_poll.py --issue 163           # aperçu : affiche le commentaire, ne publie rien
python mine_poll.py --txt notice.txt      # depuis un texte déjà extrait
python mine_poll.py --pdf notice.pdf      # depuis un PDF local
```

L'aperçu ne demande pas de `GITHUB_TOKEN` : lire une issue publique n'en a pas besoin. Seule la publication
en exige un, et elle est normalement faite par le workflow :

```bash
python mine_poll.py --issue 163 --post           # ne fait rien si l'issue est déjà commentée
python mine_poll.py --issue 163 --post --force   # réécrit le commentaire existant
```

### Dépendances

```bash
pip install -r requirements_mining.txt   # pdfplumber
```

Nécessaire à l'extraction des PDF, donc à la plupart des notices ; le workflow l'installe pour cette raison.
`--txt` reste utilisable sans rien installer.

## Modifier les questions ou la formulation

Aucun code à toucher :

- la question posée au modèle est dans [`mining/prompts/`](../mining/prompts/) ;
- le texte du commentaire est dans [comment_template_mining.md](comment_template_mining.md).

Le prompt liste les formulations réellement relevées dans les notices, institut par institut. Ce détail
compte : retirer l'une d'elles suffit à faire manquer les notices de l'institut correspondant.

Prévisualiser le résultat : `python mine_poll.py --txt une_notice.txt`.

## Garde-fous

Le modèle lit, Python vérifie. Concrètement :

- un numéro de page cité par le modèle mais absent du document est **écarté**, jamais corrigé ; un `OUI` sans
  aucune page vérifiable est refusé et devient `intentions-a-verifier` ;
- le commentaire affiche les pages qui justifient la réponse et le modèle qui a répondu, pour qu'un humain
  puisse vérifier en quelques secondes ;
- le texte produit par le modèle est échappé avant publication : une notice piégée ne peut pas injecter de
  HTML ni fabriquer le marqueur ;
- un marqueur invisible en fin de commentaire garantit qu'il n'y en a jamais deux sur une même issue ;
- le nombre d'appels par exécution est plafonné (`--max-calls`, 40 par défaut).

Le modèle peut réfléchir à voix haute — beaucoup de modèles gratuits le font — mais sa réponse doit se
terminer par une ligne contenant uniquement `OUI` ou `NON`. Une réponse hors format est redemandée une fois
avec un rappel du format. Une réponse **coupée par la limite de longueur** — cas des longues notices, où le
modèle passe les pages en revue — est redemandée avec trois fois plus de place et la consigne d'aller droit
au but. Dans les deux cas un second échec est abandonné, jamais réinterprété, et le commentaire dit laquelle
des deux situations s'est produite. Quand le modèle a réfléchi, sa réflexion est reproduite
dans le commentaire, dans un bloc dépliable.

## État

Validé en conditions réelles sur les issues #162 et #163, et sur six notices couvrant OpinionWay, IFOP,
ELABE, Cluster17 et CSA : une requête par notice, numéros de page exacts, et la notice de popularité CSA
correctement classée « sans intentions de vote ».

Limite connue, documentée dans [ISSUE_llm_mining.md](ISSUE_llm_mining.md) : la formulation de Cluster17 est
absente du prompt, ses baromètres sont donc classés `sans-intentions-de-vote`.
