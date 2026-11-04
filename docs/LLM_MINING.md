# Triage des notices par un modèle de langage

À l'ouverture d'une issue « nouveau sondage », un workflow pose **une seule question** à un modèle de langage
sur le texte entier de la notice : contient-elle des intentions de vote pour la présidentielle 2027, et sur
quelles pages ? La réponse est publiée en commentaire sous l'issue, et un label est posé.

Quand la réponse est oui, le même run relève la méthodologie et les tableaux, vérifie chaque chiffre contre
sa ligne source, puis ouvre une **PR en brouillon** avec les lignes de `polls.csv` et les `polls/<poll_id>.csv`.
Rien n'est fusionné sans relecture : GitHub interdit de fusionner un brouillon tant qu'un humain ne l'a pas
marqué prêt.

Conception d'ensemble et suite prévue : [ISSUE_llm_mining.md](ISSUE_llm_mining.md).

## Déclencheurs

| Quand | Condition | Ce qui tourne | Si un commentaire existe déjà |
|---|---|---|---|
| Ouverture d'une issue | label `new-poll` | triage, puis PR brouillon si oui | il est laissé tel quel |
| Commentaire `/mining-pr` | droits d'écriture sur le dépôt | triage, puis PR brouillon si oui | il est **réécrit** |
| Commentaire `/triage` | droits d'écriture sur le dépôt | triage seul | il est **réécrit** |
| *Actions → LLM mining → Run workflow* | numéro d'issue et mode | au choix | il est **réécrit** |

Les commandes doivent **ouvrir une ligne** du commentaire, mais peuvent suivre du texte : « J'essaie à
nouveau. » puis `/mining-pr` à la ligne suivante déclenche bien le dépouillement. Une simple mention au fil
d'une phrase, non.

Une relance met à jour la PR ouverte de l'issue (branche `mining/issue-<n>`, réécrite par force-push) : des
corrections poussées à la main sur cette branche seraient perdues. Si la PR précédente a été fermée, une
nouvelle est ouverte.

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

Une notice IFOP de 13 hypothèses consomme une quinzaine de requêtes, le double avec les relances : les
50 requêtes par jour du palier gratuit d'OpenRouter s'épuisent vite : la limite vaut pour **tout le compte**,
changer de clé n'y fait rien, et elle se remet à zéro à 00:00 UTC. Deux remèdes : ajouter `MISTRAL_API_KEY` en
relais, ou créditer le compte OpenRouter de 10 crédits, ce qui porte la limite à 1000 requêtes gratuites par jour.

Si un appel au modèle est impossible en cours de dépouillement, les tableaux déjà vérifiés ne sont **pas perdus** :
la PR brouillon est ouverte avec eux, marquée « incomplète », et liste les pages manquantes. Une réponse vide ou
une coupure réseau n'empêche pas d'interroger les pages suivantes ; un quota épuisé, si. Relancer `/mining-pr`
complète le dépouillement, avant comme après la fusion : les hypothèses déjà enregistrées pour la notice ne sont
pas reproposées, et les nouvelles prennent les lettres de `poll_id` encore libres — l'ordre des lettres peut alors
ne plus suivre celui des pages.

**Réglages du dépôt pour la PR automatique**, à faire une fois à la main :

- *Settings → Actions → General → Workflow permissions* : cocher « Allow GitHub Actions to create and approve
  pull requests », sinon la création de PR répond 403 ;
- créer les labels `automated` et `needs-human-review`. En l'absence de `needs-human-review`, le label
  existant `need-screening !` est posé ; un label manquant est signalé dans le commentaire, sans bloquer.

Une PR ouverte avec `GITHUB_TOKEN` ne déclenche pas `validate-polls.yml` (protection anti-récursion de
GitHub). La validation tourne donc dans le job avant l'ouverture, puis `validate-polls.yml` repart quand un
humain passe la PR en « prête » (`ready_for_review`).

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

### Préparer une proposition de données locale

Le triage ne produit aucun chiffre par défaut. Pour demander ensuite la
méthodologie et les tableaux des pages retenues, ajoutez `--pr` : le nom signifie
« proposition pour une PR », il **n'ouvre pas** de PR et ne modifie rien sans
`--apply`.

```bash
# Aperçu des métadonnées, hypothèses et résultats proposés ; aucun fichier modifié
python mine_poll.py --txt notice.txt --pr --proposal /tmp/proposition.json

# Vérifier la proposition JSON de manière indépendante
python add_poll.py /tmp/proposition.json --dry-run

# Ajouter les lignes à la fin des CSV et créer les polls/<poll_id>.csv
python mine_poll.py --txt notice.txt --pr --apply
```

Chaque valeur est acceptée seulement si la ligne que le modèle cite est retrouvée
dans la page source (espaces normalisés). Pour la méthodologie (E2), les mots de
la citation doivent figurer dans l'ordre, mais peuvent être entrecoupés de ceux
d'une colonne voisine, que `pdfplumber` place sur la même ligne ; les lignes de
tableau (E3), elles, doivent être retrouvées d'un seul tenant. Python vérifie aussi les dates,
effectifs, candidats, sommes à 100 ± 1,5 et les hypothèses. Une table rejetée est
signalée dans l'aperçu et n'est jamais corrigée silencieusement. Après `--apply`,
exécutez `pytest -q` et `python merge.py` avant d'ouvrir une PR humaine.

L'aperçu ne demande pas de `GITHUB_TOKEN` : lire une issue publique n'en a pas besoin. Seule la publication
en exige un, et elle est normalement faite par le workflow :

```bash
python mine_poll.py --issue 163 --post             # ne fait rien si l'issue est déjà commentée
python mine_poll.py --issue 163 --post --force     # réécrit le commentaire existant
python mine_poll.py --issue 163 --post --pr        # CI : branche mining/issue-163 et PR brouillon
```

`--post --pr` exige un arbre Git propre et `gh` authentifié : il bascule sur la branche de l'issue, ajoute les
lignes, lance `pytest -q` et `python merge.py`, puis pousse. Un échec à n'importe quelle étape n'ouvre pas de
PR et sa raison est écrite dans le commentaire de l'issue.

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
- le nombre d'appels par exécution est plafonné (`--max-calls`, 80 par défaut) ;
- la PR est un brouillon, jamais fusionnée automatiquement ; un candidat absent de `candidats.csv` est
  ajouté et signalé en tête de PR.

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

## Signaler une erreur de notice à la Commission des sondages

Quand la vérification d'une notice révèle une erreur dans le PDF lui-même (titres de scénarios intervertis,
valeurs inversées entre deux candidats, coquille dans un tableau), on peut la signaler au secrétariat de la
Commission des sondages, qui la transmet à l'institut. Toute correction appliquée aux données du dépôt est
expliquée dans la PR, et le signalement se fait en parallèle.

La consigne ci-dessous sert à faire rédiger ce mail par un modèle de langage. Remplir les champs entre
accolades, puis relire le mail, en particulier les chiffres, avant de l'envoyer.

```
Tu rédiges un mail en français destiné au secrétariat de la Commission des sondages
(secretariat@commission-des-sondages.fr) pour signaler une erreur ou une incohérence
dans une notice de sondage publiée sur son site. L'expéditeur est Pierre Puchaud,
membre de l'association Mieux Voter, qui contribue à un projet ouvert recensant et
annotant les sondages d'intention de vote pour la présidentielle 2027.

## Informations fournies (à utiliser telles quelles, ne rien inventer)
- Numéro de la notice : {numero}
- Intitulé de l'étude : {intitule}
- Institut et commanditaire(s) : {institut} pour {commanditaires}
- Dates de terrain : {dates_terrain}
- Date de la notice : {date_notice}
- Page(s) concernée(s) : {pages}
- Description de l'anomalie : {anomalie}
- Éléments qui la rendent probable (autres scénarios, totaux, autres pages, vague
  précédente…) : {indices}
- Ce qui semble correct dans le reste du document : {perimetre}

S'il manque une information indispensable (numéro de notice, page, nature précise
de l'anomalie), pose la question au lieu de la deviner. Ne cite aucun chiffre qui
ne figure pas dans les informations fournies.

## Contenu du mail
1. Objet : « Signalement d'une [coquille / probable inversion / incohérence] dans la
   notice n°{numero} ({institut} – {intitule court}, {mois année}) ».
2. Identification complète de la notice en une phrase (numéro, intitulé, institut,
   commanditaires, terrain, date de la notice).
3. Constat factuel et localisé : page, tableau ou scénario, colonne si pertinent
   (ex. « Publié »), valeurs ou libellés exacts tels qu'ils apparaissent.
4. Pourquoi c'est probablement une erreur : indices concrets et vérifiables, en
   liste courte si besoin.
5. Périmètre : préciser ce qui paraît correct, pour circonscrire le problème.
6. Prudence : distinguer le constat (ce qui est écrit) de l'hypothèse (ce qui
   devrait être écrit). Ne jamais affirmer que l'institut s'est trompé ; parler
   d'incohérence « semblant » ou « paraissant » résulter d'une inversion, coquille…
   Expliquer en une phrase le risque pour le lecteur.
7. Contexte en une phrase : l'association Mieux Voter et le projet de recensement
   ouvert des sondages pour 2027.
8. Demande : transmettre le signalement à l'institut afin que la notice soit
   vérifiée et, le cas échéant, corrigée.
9. Formule de disponibilité, « Bien cordialement, », puis la signature :
   PUCHAUD Pierre
   Membre de l'association Mieux Voter

## Style
- Vouvoiement, formule d'appel « Madame, Monsieur, ».
- Ton courtois, neutre, factuel, sans jugement sur l'institut ni commentaire politique.
- Court : 150 à 250 mots hors signature.
- Pas de remerciements appuyés, pas de superlatifs, pas de jargon technique du dépôt
  (CSV, hypothèses H.., pdfplumber, etc.).
- Noms des candidats avec leurs accents (Édouard Philippe, Éric Zemmour…).
- Pourcentages au format français : « 35 % » avec une espace insécable.

## Sortie
Renvoie uniquement l'objet puis le corps du mail, prêts à copier-coller.
```

Exemples de signalements :

- notice n°10284 (IFOP, septembre 2026) : titres des scénarios Attal et Philippe intervertis pages 12 et 13 ;
  l'IFOP a transmis une notice corrigée ;
- notice n°10318 (OpinionWay PrésiTrack, octobre 2026) : scores de Marine Le Pen et d'Éric Zemmour
  vraisemblablement inversés page 13 (issue #271).
