<!--
Corps du commentaire de triage publié par mine_poll.py.
Ce bloc d'en-tête est retiré avant l'envoi : il ne part pas dans le commentaire.

Éditer ce fichier suffit à changer la formulation — aucun code à toucher.
Prévisualiser le rendu réel : `python mine_poll.py --issue <n>`

Placeholders disponibles (syntaxe $nom) :

  $phrase     la réponse en une phrase
  $final      la réponse finale du modèle, telle quelle (vide si le modèle n'a pas conclu)
  $reasoning  la réflexion du modèle dans un bloc dépliant, vide s'il n'a pas réfléchi à voix haute
  $details    les pages retenues, et le cas échéant les anomalies
  $model      le modèle qui a répondu
  $pr         le lien de la PR brouillon, ou la raison de son absence

Un placeholder mal orthographié n'échoue pas : il ressort tel quel.
Le marqueur d'idempotence est ajouté automatiquement en fin de corps.
-->
$phrase

$final

$reasoning

$pr

<details>
<summary>Comment cette réponse a été obtenue</summary>

$details

Étape E1 — une seule question posée sur le document entier.
Modèle : $model

</details>

> 🤖 Réponse générée automatiquement, **à vérifier**. Elle ne remplace pas la lecture de la notice.
> Si une PR brouillon est indiquée ci-dessus, ses chiffres doivent être comparés au PDF par un humain avant
> fusion.
