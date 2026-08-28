# Contribuer à presidentielle2027

Merci de contribuer au dépôt.

Ce document complète le README et le guide [COMMENT_AJOUTER_UN_SONDAGE.md](COMMENT_AJOUTER_UN_SONDAGE.md).

## 🤖 Contributions avec une IA / un LLM

Les contributions réalisées avec l’aide d’une IA, d’un LLM ou d’un agent de programmation sont autorisées.

Cependant, les mêmes règles s’appliquent à une contribution produite par une IA qu’à une contribution produite manuellement.

### Instructions pour les IA et agents de code

Si vous êtes une IA, un LLM ou un agent automatisé et que vous ouvrez une Pull Request sur ce dépôt, vous devez respecter les règles suivantes :

1. Lire `README.md` et `CONTRIBUTING.md` avant de modifier le dépôt.
2. Comprendre l’objectif de la modification avant d’écrire du code.
3. Modifier uniquement les fichiers nécessaires à cet objectif.
4. Ne jamais inventer de données, de sources, de sondages ou de résultats.
5. Ne pas déduire une information qui n’est pas présente dans la source.
6. Ne pas faire de refactoring ou de nettoyage général qui n’est pas nécessaire à la contribution.
7. Ne pas modifier le comportement existant sans raison directement liée à la Pull Request.
8. Vérifier le diff complet avant de proposer la Pull Request.
9. Exécuter les tests et vérifications disponibles avant de proposer la Pull Request.
10. Si l’intention du mainteneur n’est pas claire, demander une clarification ou proposer d’abord une Issue.

Une IA doit produire une contribution qu’elle est capable d’expliquer et de justifier.

## 📏 Taille des Pull Requests

Pour le code Python et le code/configuration CI :

- 200 lignes de code ou moins : taille normale.
- Entre 200 et 400 lignes : contribution importante, à justifier clairement.
- 400 lignes : maximum attendu pour une Pull Request.
- Plus de 400 lignes : la modification doit avoir été discutée au préalable dans une Issue.

Une Pull Request dépassant 400 lignes qui n’a pas été discutée auparavant dans une Issue peut être fermée ou ignorée.

Ces limites ont pour objectif de permettre une revue humaine efficace.

Elles ne doivent pas être contournées en découpant artificiellement une même modification en plusieurs Pull Requests.

Si une modification importante nécessite réellement plus de 400 lignes, ouvrir une Issue avant de commencer et expliquer :

- le problème à résoudre ;
- pourquoi la modification est nécessaire ;
- l’approche envisagée ;
- l’ordre de grandeur de la modification.

## 📝 Description de la Pull Request

La description de la Pull Request doit être rédigée par l’agent ou le contributeur lui-même et correspondre exactement aux changements réellement effectués.

Pour une Pull Request créée par une IA :

- l’IA doit rédiger elle-même la description ;
- elle ne doit pas utiliser une description générique ;
- elle ne doit pas prétendre avoir effectué des vérifications qu’elle n’a pas réellement effectuées ;
- elle doit expliquer concrètement ce qui a changé et pourquoi.

Les 300 premiers caractères de la description doivent suffire à comprendre l’essentiel de la Pull Request et doivent être écrits par un humain.

Ils doivent notamment permettre de comprendre :

- ce qui est modifié ;
- pourquoi c’est modifié ;
- le cas échéant, le problème corrigé ;
- dans les mots du contributeur.

## 🎯 Une Pull Request doit avoir un objectif unique

Une Pull Request doit correspondre à un objectif identifiable.

Éviter de mélanger dans une même PR :

- une correction de bug ;
- une refonte du code ;
- une mise à jour de dépendances ;
- une modification de la CI ;
- une modification de données sans rapport.

Si plusieurs changements sont nécessaires pour atteindre le même objectif, expliquer clairement leur relation dans la description.

## 🔍 Ne pas inventer

C’est une règle particulièrement importante pour ce dépôt.

Une IA ne doit jamais :

- inventer un sondage ;
- inventer une source ;
- inventer une date ;
- inventer un résultat ;
- inventer une méthodologie ;
- compléter une donnée manquante par une valeur supposée correcte.

En cas d’incertitude, il faut signaler l’incertitude plutôt que deviner.

## 📚 Sources et traçabilité

Toute donnée externe ajoutée au dépôt doit pouvoir être reliée à sa source.

Lorsque cela est pertinent, indiquer :

- la source ;
- la date ;
- l’institut ;
- les informations méthodologiques disponibles ;
- le contexte nécessaire à l’interprétation de la donnée.

Une IA ne doit pas transformer une information ambiguë en information certaine.

## 🧪 Tests et vérifications

Avant d’ouvrir une Pull Request, exécuter les tests et vérifications pertinents.

La description de la PR doit indiquer les vérifications réellement effectuées et référer à une issue.

Si un test ne peut pas être exécuté, l’indiquer clairement et expliquer pourquoi.

## 🔎 Vérification du diff

Avant d’ouvrir une Pull Request, vérifier le diff final.

L’agent doit notamment rechercher :

- les modifications involontaires ;
- les fichiers modifiés sans rapport ;
- les fichiers temporaires ;
- les changements de formatage inutiles ;
- les changements massifs non justifiés ;
- les données modifiées accidentellement.

Une Pull Request ne doit pas contenir de modifications uniquement parce qu’un outil les a générées automatiquement.

## 🚫 Pas de refactoring opportuniste

Une contribution destinée à corriger X ne doit pas profiter de l’occasion pour réécrire Y et Z.

Les refactorings importants doivent faire l’objet d’une contribution séparée ou être discutés dans une Issue.

Le code peut être amélioré lorsque cette amélioration est directement nécessaire à la contribution, mais « tant qu’on y est » n’est pas une justification suffisante.

## 📦 Dépendances

Ne pas ajouter de dépendance simplement parce qu’elle facilite légèrement une tâche.

Toute nouvelle dépendance doit avoir une justification claire.

Une IA ne doit pas ajouter automatiquement une bibliothèque lorsqu’une solution raisonnable existe déjà dans le projet ou dans la bibliothèque standard.

## 🗂️ Fichiers générés

Si un fichier est généré automatiquement, modifier en priorité sa source plutôt que le fichier généré.

Si la modification d’un fichier généré est nécessaire, l’expliquer dans la Pull Request.

Ne pas générer de changements massifs simplement parce qu’un outil permet de régénérer l’ensemble du dépôt.

## 💬 Quand ouvrir une Issue ?

Une Issue est recommandée, et peut être nécessaire, avant :

- une modification de plus de 400 lignes de code ;
- une nouvelle fonctionnalité importante ;
- une modification de l’architecture ;
- un changement du format des données ;
- une modification importante du comportement existant ;
- une nouvelle dépendance structurante ;
- une refonte importante de la CI.

En cas de doute sur une modification importante, discuter avant d’implémenter.

## 🧑‍💻 Responsabilité du contributeur

Utiliser une IA ne transfère pas la responsabilité de la Pull Request à l’IA.

Le contributeur qui ouvre la PR doit vérifier que :

- les changements correspondent à son intention ;
- les données sont exactes ;
- les tests sont pertinents ;
- la description est honnête ;
- la contribution respecte les règles du dépôt.

## 🤖 Checklist spécifique aux agents IA

Avant d’ouvrir une Pull Request, un agent IA doit pouvoir répondre « oui » aux questions suivantes :

- Ai-je compris ce que le dépôt attend de cette contribution ?
- Ai-je lu les instructions du dépôt ?
- Ai-je limité mes modifications au strict nécessaire ?
- Ai-je vérifié mes sources ?
- Ai-je évité toute supposition ou invention ?
- Ai-je vérifié mon diff ?
- Ai-je exécuté les tests pertinents ?
- Ma description correspond-elle exactement à ce que j’ai réellement changé ?
- Les 300 premiers caractères expliquent-ils clairement la PR ?
- Ma PR respecte-t-elle la limite de 400 lignes de code Python/CI ?
- Si elle dépasse cette limite, une Issue a-t-elle été discutée au préalable ?

Une contribution petite, ciblée, vérifiable et correctement décrite est préférable à une contribution volumineuse générée automatiquement.

## 📄 Extraction des données PDF

Pour transformer des fichiers PDF en CSV, privilégier une extraction reproductible et vérifiable.

Dans ce dépôt, `pdfplumber` est recommandé pour extraire le contenu avant mise en forme en `.csv`.

Le dossier `sandbox/` (ignoré par git) sert d'espace de travail pour cette étape :

- déposer le PDF source du sondage dans `sandbox/` (jamais ailleurs dans le dépôt) ;
- la librarie `pdfplumber` est **très recommandé** pour exporter un fichier intermédiaire (texte brut, tableau extrait, JSON de debug…), l'écrire aussi dans `sandbox/`, pour ensuite être donné à un LLM;
- ces fichiers ne doivent jamais être ajoutés à la Pull Request : seuls `polls.csv`, `polls/<poll_id>.csv` et, si nécessaire, `candidats.csv`/`hypotheses.csv` en sont issus et doivent être committés.

Le nom du PDF source doit être reporté tel quel dans la colonne `filename` de `polls.csv`, afin de garder une source vérifiable même si le fichier lui-même n'est pas versionné.
