<!--
Corps des issues « nouveau sondage », utilisé par check_new_polls.py.
Ce bloc de commentaire d'en-tête est retiré avant l'envoi : il ne part pas dans l'issue.

Éditer ce fichier suffit à changer le format des issues — aucun code à toucher.
Prévisualiser le rendu réel : `python check_new_polls.py`

Placeholders disponibles (syntaxe $nom, ou ${nom} si collé à du texte) :

  $name           nom du sondage dans le catalogue (ex: 10260 Pres IV OPINIONWAY Cnews 11 septembre)
  $filename       nom du fichier PDF (ex: 10260-pres-iv-opinionway-cnews-11-septembre.pdf)
  $year           année
  $creation_date  date de création du PDF
  $links          les deux liens sur une ligne : "$txt_link · $pdf_link"
  $txt_link       lien markdown vers la notice en texte ; si le TXT n'existe pas encore
                  en amont, devient la mention "texte extrait pas encore disponible"
  $pdf_link       lien markdown vers le PDF (toujours présent)
  $txt_url        URL brute du TXT, ou vide si absent (pour composer soi-même)
  $pdf_url        URL brute du PDF sur le miroir GitHub
  $source_url     lien vers la notice sur commission-des-sondages.fr
  $repo           owner/repo courant (pour les liens internes)

Un placeholder mal orthographié n'échoue pas : il ressort tel quel dans l'issue.

Le marqueur de dédoublonnage (un commentaire HTML "poll-file") est ajouté
automatiquement en fin de corps : ne pas le recopier ici.

Attention : ce bloc d'en-tête est un commentaire HTML, il ne doit donc contenir
nulle part la séquence qui referme un commentaire.
-->
## 📊 $name

$links

`$filename` · notice du $creation_date

Vous pouvez traiter cette issue avec ou sans LLM.

### À faire **avec** LLM
- [ ] Relire le texte extrait en regard du PDF ($pdf_link) : l'extraction est automatique, elle peut déformer un tableau
- [ ] Passer le fichier txt à votre LLM et lui faire produire les deux fichiers ci-dessous
- [ ] Ajouter la/les ligne(s) dans `polls.csv` (une par hypothèse)
- [ ] Créer `polls/<poll_id>.csv` pour chaque hypothèse
- [ ] `pytest && python merge.py`, puis ouvrir la PR

### À faire **sans** LLM
- [ ] Relever les résultats directement dans le PDF ($pdf_link)
- [ ] Ajouter la/les ligne(s) dans `polls.csv` (une par hypothèse)
- [ ] Créer `polls/<poll_id>.csv` pour chaque hypothèse
- [ ] `pytest && python merge.py`, puis ouvrir la PR

<details>
<summary>Aide</summary>

- `poll_id` : `YYYYMMDD_DDMM_ii_X` (début, fin, initiales institut, lettre d'hypothèse)
- Candidat absent de `candidats.csv` → l'ajouter
- `erreur_sup` / `erreur_inf` : laisser vide, la CI post-merge les remplit
- 📖 [Guide complet](https://github.com/$repo/blob/main/COMMENT_AJOUTER_UN_SONDAGE.md)
- 🔗 [Notice source (commission des sondages)]($source_url)

</details>
