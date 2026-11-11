# Comment Prévo est construit

*English version: [METHODE.md](METHODE.md)*

Prévo est une GMAO (gestion de maintenance) libre et gratuite pour les PME industrielles. Son auteur, Nicolas Briand, est un technicien de maintenance devenu formateur ; le projet est publié avec SELECTIS (<https://selectis.eu>). Prévo n'a pas été tapé par une personne : il a été écrit par des agents IA (Claude Code) sous la direction d'un humain qui décide et valide. Cette page explique comment cela se passe concrètement, pour qui se demande si un logiciel construit par IA peut être contrôlé. C'est un résumé ; le récit détaillé est [PILOTAGE.md](PILOTAGE.md).

## 1. Écrire ce qui est attendu avant tout code

Trois documents précèdent la première ligne de code :

- un **cahier des charges** (le « brief »), rédigé par Nicolas Briand avec Claude : besoins, écrans, tables, règles de gestion, découpage en lots ;
- un **cahier des charges du chantier**, qui traduit le brief en engagements et que Nicolas valide avant tout code. Pour le premier lot : 18 décisions et 20 critères de succès mesurables ;
- un **contrat d'architecture** (`docs/ARCHITECTURE.md`) : format des fichiers, schéma des 22 tables, interfaces des modules, règles métier. Chaque agent le reçoit, ce qui permet à des fichiers écrits séparément de s'emboîter.

Les décisions qui engagent l'utilisateur restent à l'humain. L'IA les propose, avec leurs conséquences.

## 2. Des tâches, des vagues, un outil qui vérifie chaque vague

Le travail est découpé en petites tâches regroupées en **vagues** : les tâches d'une vague ne dépendent pas les unes des autres et avancent en parallèle. Le premier lot comptait 19 tâches en 7 vagues. Une session, l'**orchestrateur**, n'écrit pas le code : elle cadre les tâches, les confie à des **sous-agents** (chacun reçoit un énoncé précis : fichiers autorisés, fichiers interdits, commande de vérification), puis vérifie et décide.

La règle qui compte le plus : **une tâche n'est acceptée que si sa commande de vérification passe, relancée par l'orchestrateur lui-même.** Le compte rendu d'un sous-agent ne suffit jamais, car il peut se tromper ou conclure trop vite. À la fin de chaque vague, un **relecteur qui n'a pas écrit le code** le lit en cherchant des défauts. Chaque tâche donne un commit identifié par son numéro ; chaque vague validée, et chaque lot terminé, a une étiquette git (`lot-1` à `lot-7`, puis `v1.0.0` à `v1.2.1` et `v2.0.0-beta.1`, `-beta.2`).

## 3. Les tests d'abord, la suite complète avant chaque publication

Un défaut n'est corrigé qu'après avoir été **reproduit par un test qui échoue** ; le test passe ensuite avec la correction et reste dans la suite. Des scénarios de bout en bout tournent dans un vrai navigateur (Chromium), en mode serveur et en mode démo. Avant une publication, la suite complète est jouée d'un trait. Les tests n'utilisent jamais de données réelles d'entreprise, et aucun vrai modèle d'IA n'est lancé dans la suite : un faux fournisseur rend les tests rapides, reproductibles, et capables de simuler les pannes.

## 4. Les arrêts où l'humain valide

L'humain valide : le cahier des charges et chaque décision de produit ; les choix de sécurité ; chaque publication (étiquettes et releases ne partent qu'avec son accord) ; et tout ce qu'une IA ne peut pas vérifier seule : un vrai dossier partagé, un vrai téléphone, un bon de travail imprimé, une installation sur un PC sans Python. Ces vérifications restent notées comme prévues tant qu'il n'en a pas donné le résultat.

## 5. Des défauts trouvés par cette discipline

- **Perte de données sur fichier abîmé.** Quand un fichier de données était abîmé hors de Prévo (une note tapée dans Excel, un guillemet oublié), l'application pouvait le réécrire et perdre ce qu'elle n'avait pas su lire. La 1.2.1 et la 2.0.0 bêta 2 le corrigent : un fichier abîmé n'est jamais réécrit, un bandeau « Fichier abîmé » s'affiche et la saisie reste dans le formulaire. La bêta 1 était atteinte, ce que le README dit ouvertement.
- **Relectures du lot 1** : 5 défauts critiques, tous corrigés avant la suite, dont deux pertes de données possibles quand un autre poste écrit au même moment, et une règle de clôture d'ordre de travail contournable depuis deux postes à la fois.
- **Installation (lot 7)**, trouvés en écrivant le guide d'installation et par une recette en mode serveur qui suit le parcours de l'utilisateur : un zip de release sans la page d'entrée, une impasse au premier compte (personne ne pouvait plus entrer, assistant compris) et la clé privée du certificat qui partait dans les sauvegardes.
- **Wiki (lot 6)** : le journal compte une cinquantaine de défauts classés critiques, tous corrigés avant la vague suivante, par exemple des profils qui voyaient ce qu'ils ne devaient pas voir.

## 6. Ce que la méthode ne garantit pas

- Des tests verts prouvent que les cas écrits passent, pas qu'il n'existe pas d'autre défaut. La relecture indépendante réduit ce risque sans l'annuler.
- Les chiffres de performance sont ceux d'un poste et d'un jeu de données précis.
- Certaines preuves ne viennent que du vrai matériel (téléphones, connexion à distance, réseau réel). Elles passent par des recettes de l'humain, et leur résultat n'est consigné qu'une fois fait.
- La 2.0.0 et la 2.1.0 viennent de sortir : elles n'ont pas encore été éprouvées longtemps sur le terrain. La 1.2.1 reste disponible.

## 7. Les chiffres

| Chiffre | Valeur | Source |
|---|---|---|
| Commits du dépôt | 529, du 19/10/2026 au 08/11/2026 (jusqu'à la 2.1.0) | `git rev-list --count v2.1.0` |
| Étiquettes de lot | 14 (`lot-1` à `lot-7`, `lot-3-bis` ; `lot-i18n-1` à `lot-i18n-6` pour le chantier multilingue) | `git tag` |
| Tests à la fin du lot 1 | 411 | PILOTAGE.md §4 |
| Tests à la fin du lot 7 | 1 762 (suite jouée en 39 minutes) | PILOTAGE.md §13 |
| Tests de la dernière version | 2 831 tests sur 201 fichiers, sur la 2.2.0 bêta 1 (comptés, la suite complète est rejouée à la clôture) | `unittest discover` et `countTestCases()`, 12/11/2026 |
| Versions | 1.0.0 (21/10/2026), 1.1.0 (22/10/2026), 1.2.0 (24/10/2026 selon CHANGELOG), 1.2.1 (04/11/2026), 2.0.0 bêta 1 (28/10/2026), bêta 2 (05/11/2026), 2.0.0 (08/11/2026), 2.1.0 (08/11/2026), 2.1.1 (11/11/2026), 2.2.0 bêta 1 (12/11/2026) | CHANGELOG.md, étiquettes git |
| Organisation du lot 1 | 19 tâches, 7 vagues, 4 relectures, 5 défauts critiques | PILOTAGE.md §2 et §3 |
| Organisation du lot 7 | 33 tâches en 12 vagues, 45 commits | PILOTAGE.md §13 |
| Bibliothèques ajoutées au lot 7 | aucune | PILOTAGE.md §13 |
| Temps, sept premiers jours (19-25/10/2026, jusqu'à la 1.2.0) | 84 h de sessions actives dans Claude Code (nuits en autonomie comprises), plus 10 h de conception en chat | page du making-of |
| Coût, même période | 90 € au plus (abonnement Claude Max d'un mois, partagé avec d'autres projets) ; 1 674 € si les mêmes appels avaient été facturés au tarif public de l'API | page du making-of |
| Usage de l'IA, même période | 4,66 milliards de tokens pour 14 708 appels (98 % de relecture de cache) | page du making-of |

Ces chiffres de temps et de coût sont des minimums (la conception en chat n'est pas comptée en tokens), et le travail de la 2.0 n'y est pas. Source : [Création de Prevo](https://selectis.eu/ia/creation-de-prevo.html) (page du 25 octobre 2026).


## 8. Cinq points à retenir

1. Faire écrire et valider le cahier des charges et ses critères de succès avant le code.
2. Écrire le contrat entre les morceaux avant de distribuer le travail.
3. Accepter une tâche sur une preuve relancée par soi-même, jamais sur déclaration.
4. Faire relire par quelqu'un qui n'a pas écrit le code, et reproduire chaque défaut par un test avant de le corriger.
5. Réserver à l'humain les décisions, et lui demander les vérifications physiques.

La liste complète (onze points) est à la section 14 de [PILOTAGE.md](PILOTAGE.md).

---

*Chiffres datés du 12/11/2026 (Prévo 2.2.0-beta.1). Plus de détail : [PILOTAGE.md](PILOTAGE.md). Projet : <https://github.com/prevo-pro/prevo>.*
