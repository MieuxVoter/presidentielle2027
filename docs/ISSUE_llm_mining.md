<!--
Corps de l'issue de design « data-mining LLM des notices ».
À copier tel quel dans une nouvelle issue GitHub, ou à lire directement ici.
CONTRIBUTING.md demande une issue préalable pour une nouvelle fonctionnalité
importante et pour toute contribution dépassant 400 lignes : c'est celle-ci.
-->
# Data-mining des notices par un modèle de langage

## Le problème

Depuis peu, chaque issue « nouveau sondage » porte un lien vers la **version texte** de la notice, générée en
amont par `pdfplumber` dans `MieuxVoter/sondages-commission-index/archives_txt/`. Le texte est là ; le
dépouillement, lui, reste entièrement manuel : ouvrir le PDF, relever les hypothèses, saisir une ligne dans
`polls.csv` et un fichier `polls/<poll_id>.csv` par hypothèse, ouvrir la PR.

Deux besoins ressortent de la discussion :

- **trier** — une bonne partie des notices « Pres » ne contiennent aucune intention de vote (popularité,
  cote de confiance, questions d'opinion). Les repérer automatiquement éviterait d'ouvrir des PDF pour rien ;
- **dépouiller** — c'est fastidieux, et ça marche déjà bien avec un LLM quand on le fait à la main.

## Le principe retenu : le LLM lit, Python vérifie

**Pas de parseur de mise en page.** Les formats diffèrent d'un institut à l'autre et changent dans le temps.
Sur un échantillon de 6 notices seulement, on trouve déjà **4 mises en page incompatibles** (voir plus bas).
Écrire des règles de parsing revient à les ajuster sur les notices qu'on a sous la main, et à les voir casser
à la suivante. C'est le travail d'un modèle de langage.

Python ne cherche donc jamais à comprendre un tableau. Il fait trois choses, toutes indépendantes du format :

1. **découper** le texte en pages et fournir les lignes numérotées au modèle ;
2. **vérifier** chaque réponse — c'est le cœur du dispositif :
   - le modèle renvoie, avec chaque valeur, **la ligne source recopiée mot pour mot** ; on contrôle que cette
     ligne existe réellement dans la page et que la valeur y figure ;
   - chaque nom est confronté à `candidats.csv` (via `merge.py::_norm()`) ;
   - contrôles arithmétiques : somme ≈ 100, valeurs dans [0, 100], 2 candidats au 2nd tour ;
   - le jeu de candidats est rattaché à `hypotheses.csv` par égalité d'ensembles — la logique existe déjà
     dans `merge.py` (lignes 162-166) ;
3. **écrire** les CSV, générer le `poll_id`, ouvrir la PR.

Une réponse dont la citation est introuvable est **rejetée**, jamais corrigée en silence. Autrement dit : un
chiffre qui atterrit dans un CSV vient forcément d'une ligne présente mot pour mot dans la notice. C'est la
traduction technique de la règle « ne jamais inventer » de `CONTRIBUTING.md`.

## Ce qui reste manuel, et pourquoi

Le consensus de la discussion est conservé tel quel :

- **le dépouillement se déclenche à la main** — « a little friction forces me to review the output ». Seule
  la question de tri (« y a-t-il des intentions de vote ? ») est automatique, parce qu'elle ne produit
  aucune donnée : elle pose un label ;
- **toute PR est relue par un humain avant merge.** Jamais d'auto-merge, sur aucun chemin.

## Ce qu'on a appris en testant sur 6 notices réelles

Les 6 PDF disponibles ont été extraits avec `pdfplumber layout=True` et comparés aux **32 sondages** déjà
présents dans le dépôt pour ces notices. L'objectif n'était pas d'écrire un parseur mais de découvrir les
pièges — et il y en a, dont plusieurs qu'aucun modèle ne devinerait s'il n'en est pas averti :

| Observation | Conséquence |
|---|---|
| `<1%` est enregistré **`0.5`** dans le dépôt (28 occurrences), `-` signifie « non renseigné » | Convention **nulle part documentée**. À dire au modèle. |
| Colonnes rencontrées : `Publié`, `Brut`, `Redressé`, `Socio-Démo`, `+Présid2022`, `+Légis2024`. Le dépôt retient `Publié`, et `Redressé` quand `Publié` n'existe pas | Règle de choix à énoncer explicitement. |
| OpinionWay affiche **9 colonnes de chiffres par candidat**, et les 9 somment à 100 | La somme ne permet pas de choisir la colonne : il faut lire l'intitulé. |
| ELABE et IFOP écrivent les chiffres **sans `%`** (`Nathalie ARTHAUD 1,5`), virgule décimale | Ne pas se fier au signe `%`. |
| Lignes `N'expriment pas d'intention de vote`, `Abstention, vote blanc ou nul` | À exclure explicitement. |
| Un même PDF porte jusqu'à **13 hypothèses** (IFOP), 1er et 2nd tour mêlés | Une hypothèse = un tableau = une question. |
| Cluster17 demande « laquelle souhaitez-vous voir gagner » et **compte** comme 1er tour dans le dépôt ; la notice CSA popularité ne compte pas | La question de tri ne doit pas exiger la formule « pour qui voteriez-vous », mais doit exclure popularité / cote de confiance / notoriété. |
| Seules **3 notices sur 365** ont aujourd'hui un TXT en amont (génération récente) | Prévoir un repli d'extraction `pdfplumber` pour le rétroactif et pour l'évaluation. |
| L'extraction *layout* produit des **espaces irréguliers** (`laquelle␣␣souhaitez-vous␣␣␣␣␣␣voir gagner`) et coupe les questions sur plusieurs lignes | Toute vérification de citation « mot pour mot » devra normaliser les espaces avant de comparer. |

Ces 32 sondages, avec leurs chiffres exacts, constituent un **jeu d'évaluation** : ils permettent de mesurer
si tel modèle gratuit reproduit les données du dépôt, et de refaire la mesure quand un fournisseur change son
catalogue.

## Infrastructure

- **Pas de modèle sur le runner.** Les runners publics sont 4 vCPU / 16 Go / sans GPU : le seul *prefill*
  d'une notice (~12k tokens) prend plusieurs minutes par appel sur CPU, et un modèle ≤ 8B ne lit pas ces
  tableaux de façon fiable.
- **GitHub Models a été retiré le 30 juillet 2026** — il n'y a plus d'API LLM gratuite intégrée à Actions, et
  `actions/ai-inference` exige désormais un token Copilot. L'appel se fait donc en HTTP sortant, clé en
  secret de dépôt.
- **OpenRouter en tête**, avec son paramètre `models: [...]` qui bascule seul entre modèles `:free` en cas de
  429 ou d'indisponibilité. Le client sait enchaîner sur d'autres fournisseurs (Mistral, Gemini) si leurs
  clés sont présentes.

Sur un dépôt public, deux précautions non négociables : le déclenchement est réservé aux personnes ayant les
droits d'écriture (sinon n'importe qui vide le quota d'API en commentant), et le corps des commentaires n'est
jamais interpolé dans un `run:` (injection de script).

## Découpage proposé

Chaque lot livre une **fonction visible de bout en bout**, se déploie seul et rend service dès qu'il est
mergé. `CONTRIBUTING.md` plafonne une PR à 400 lignes, ce qui est respecté lot par lot.

| Lot | Ce qu'on voit | Contenu |
|---|---|---|
| **1 — Le triage** | À l'ouverture d'une issue `new-poll` : un commentaire « Oui / Non, il y a des intentions de vote » et un label `avec-intentions-de-vote` / `sans-intentions-de-vote` | Téléchargement du TXT (+ repli PDF), client LLM, la question de tri, le job automatique |
| **2 — Le décompte** | Le commentaire devient « Oui : 3 hypothèses pour le 1er tour et 2 pour le second tour » | Question « quel tour ? », question « libellé de l'hypothèse », vérification des citations |
| **3 — La fiche détaillée** | `/llm-mining` produit une fiche : candidats, pourcentages, candidats absents de `candidats.csv`, échantillons, populations — chacun avec sa citation source | Lecture des tableaux, méthodologie, contrôles arithmétiques |
| **4 — La PR automatique** | `/llm-mining --pr` ouvre une PR relisible avec `polls.csv` et `polls/<poll_id>.csv` remplis | Rattachement d'hypothèse, `poll_id`, écriture, barrière `pytest` + `merge.py` avant d'ouvrir la PR |
| **5 — La relecture côte à côte** | Une page qui affiche la page de notice à gauche, les lignes proposées à droite | C'est ce qui rend la relecture rapide, donc ce qui rend l'automatisation acceptable |

Le lot 1 a de la valeur même si rien d'autre n'est fait : il rend la liste d'issues filtrable et évite
d'ouvrir des notices sans intentions de vote. Les lots sont indépendants et peuvent être pris par des
personnes différentes.

## Garde-fous

- La PR produite porte le label `needs-human-review` et indique le modèle utilisé, la colonne retenue et les
  citations sources.
- Les tests et `merge.py` tournent **avant** l'ouverture de la PR : en échec, pas de PR, un commentaire
  rapporte l'erreur. (À noter : une PR ouverte avec `GITHUB_TOKEN` ne déclenche pas `validate-polls.yml`,
  protection anti-récursion de GitHub — d'où cette barrière dans le job lui-même.)
- Un candidat absent de `candidats.csv` est signalé en tête de PR plutôt qu'ajouté discrètement : c'est un
  jugement, pas une donnée.
- Tout est testable hors ligne, avec des réponses de modèle enregistrées : aucun quota consommé en CI.

## Limite connue : Cluster17

Le prompt de triage donne en exemple la formulation de chaque institut. Un test A/B sur la même notice et
le même modèle montre que ces exemples sont porteurs :

| Notice `10228-pres-barometre-cluster17-le-point-14-juillet.pdf` | Résultat |
|---|---|
| Prompt **avec** la formulation Cluster17 | `oui`, page 20 — conforme au dépôt |
| Prompt **sans** cette formulation | `non` |

La formulation de Cluster17 — « Parmi les personnalités suivantes, laquelle souhaitez-vous voir gagner
l'élection présidentielle en 2027 ? » — ne ressemble à aucune autre, et n'est actuellement **pas** dans le
prompt. Les baromètres Cluster17 seront donc classés `sans-intentions-de-vote`, alors que `polls.csv` en
enregistre 15.

À trancher : soit on rétablit la formulation dans le prompt, soit on assume que ces baromètres ne sont pas
des intentions de vote — et il faut alors revoir les 15 sondages concernés.

## Ce qui reste à valider

Aucune étape LLM n'a encore été exécutée — le travail ci-dessus est une étude des notices, pas une mesure de
performance des modèles. La première chose à faire après le lot 1 est de faire tourner le jeu d'évaluation
sur plusieurs modèles gratuits, en priorité sur la question de tri, puisque c'est la seule dont dépend
l'exactitude du commentaire automatique.

## Questions ouvertes

1. Le commentaire automatique de tri : sur **toutes** les nouvelles issues, ou seulement sur demande ?
2. Faut-il ajouter les labels `avec-intentions-de-vote` / `sans-intentions-de-vote` au dépôt, ou en réutiliser
   d'existants ?
3. Qui prend quel lot ?
