# Comment Prévo a été piloté

Prévo a été écrit par des IA (Claude Code) sous la direction de Nicolas Briand. Ce document décrit
la méthode de pilotage, ce qu'elle a permis de constater, et ce qu'elle n'a pas encore vérifié. Il
vise un lecteur qui se demande si un projet confié à une IA peut être contrôlé, et comment.

Les chiffres cités viennent de commandes lancées au moment de la rédaction (suite de tests, historique
git). Ce qui n'a pas été vérifié est présenté comme prévu.

## 1. Principe : écrire ce qui est attendu avant de coder

Trois documents précèdent tout code.

1. **Le cahier des charges (le « brief »)**, rédigé par Nicolas Briand avec Claude : besoins,
   écrans, tables, règles de gestion, découpage en quatre lots.
2. **Le cahier des charges du chantier**, qui traduit le brief en engagements pour le lot 1. Nicolas
   l'a validé avant le premier fichier de code : **18 décisions** (nom, périmètre, format des
   données, arbitrages) et **20 critères de succès mesurables**. Les décisions qui engagent
   l'utilisateur restent à l'humain ; l'IA les propose avec leurs conséquences.
3. **Le contrat d'architecture** (`docs/ARCHITECTURE.md`), écrit avant les tâches : format des CSV,
   schéma des 22 tables, API des modules, règles métier. Chaque sous-agent le reçoit comme
   référence, ce qui permet à des fichiers écrits séparément de s'emboîter.

## 2. Organisation : un orchestrateur, des sous-agents, des relecteurs

- Le chantier est découpé en **19 tâches réparties en 7 vagues**. Une vague regroupe des tâches
  qui peuvent avancer sans dépendre les unes des autres.
- **L'orchestrateur** (une session Claude Code) ne code pas les tâches : il les cadre, les confie,
  les vérifie et décide.
- Chaque tâche est confiée à un **sous-agent** Claude Code qui reçoit un énoncé précis : fichiers
  autorisés, interdits, commande de vérification.
- Une tâche n'est **acceptée que si sa commande de vérification passe, relancée par l'orchestrateur
  lui-même**. Le compte rendu du sous-agent ne suffit pas : il peut se tromper ou conclure trop vite.
- À la fin de chaque vague, un **relecteur indépendant**, qui n'a pas écrit le code, le lit en
  cherchant des défauts. Il y a eu 4 relectures pour le lot 1.
- Un lot n'est terminé que si **tous ses scénarios de recette** (ceux du cahier des charges :
  panne sur pompe, clôture refusée, conflit entre deux postes, téléphone, habilitation,
  sauvegarde, attaque du serveur, aller-retour Excel) passent, rejoués automatiquement dans un
  navigateur.
- Chaque tâche donne lieu à un commit identifié par son numéro (une correction après relecture
  porte le numéro de la tâche corrigée), chaque vague validée à une étiquette git, et le lot
  terminé à l'étiquette `lot-1`. Une étiquette fige aussi le cahier des charges validé.

## 3. Ce que la relecture a trouvé

Les 4 relectures ont trouvé **5 défauts critiques**, tous corrigés avant de passer à la suite :

- deux possibilités de **perte de données** dans le mode dossier, quand un autre poste écrit au
  même moment ;
- une règle de clôture d'ordre de travail **contournable** quand deux postes agissent en même
  temps ;
- un ordre de travail verrouillé qui restait **modifiable** depuis une page ouverte sur un autre
  poste ;
- une **saisie non enregistrée effacée** quand on enregistrait un autre bloc de la même fiche.

Les relecteurs ont aussi relevé une trentaine de défauts mineurs (contrastes, zones tactiles,
messages d'erreur, cas limites du format CSV, noms de marques réels dans la démo), corrigés au fil
de l'eau ou, pour quelques-uns, documentés pour la revue finale (par exemple la taille du module
des ordres de travail, à découper pour un lecteur débutant).

Règle appliquée : un défaut n'est corrigé qu'après avoir été **reproduit par un test qui échoue**,
puis ce test passe avec la correction. Les tests de régression restent dans la suite.

## 4. Les preuves, plutôt que les affirmations

- **Aller-retour par le vrai Excel.** Les fichiers ont été ouverts et réenregistrés par Excel :
  dates réécrites en `JJ/MM/AAAA`, zéros de tête perdus, formules abîmées. Nicolas a décidé la
  protection par apostrophe ; un test pilote Excel pour vérifier que les valeurs protégées
  survivent (ce test ne tourne que si l'on définit `PREVO_TEST_EXCEL=1`).
- **Attaques du serveur.** Traversées de chemin (`..`, encodages en `%2E`, `%2F`, `%5C`) et noms
  réservés de Windows ont été essayés ; les traversées testées reçoivent une réponse 400, et le
  serveur ne sert rien hors de son dossier de données.
- **Injection de script (XSS).** Quarante champs des fichiers de données ont été piégés avec du
  code, puis tous les écrans ont été parcourus avec les trois profils : aucun ne l'exécute.
- **Noms de marques.** Les noms « inventés » du jeu de démo ont été cherchés sur le web : dix
  existaient réellement et ont été renommés.
- **Recette automatisée.** Un scénario complet de bout en bout tourne dans Chromium, en mode
  serveur et en mode démo, y compris le chemin du QR code vers un téléphone simulé.
- **Performance mesurée.** Avec 500 équipements et 5 000 ordres de travail : chargement complet
  d'environ 0,4 s, création d'une demande d'intervention d'environ 0,08 s (budgets fixés
  d'avance à 2 s et 1 s).
- **Suite de tests.** Sur la dernière exécution de cette rédaction : 411 tests exécutés, tous
  verts, 2 sauts (l'aller-retour par le vrai Excel, non demandé). Toute erreur JavaScript dans le
  navigateur fait échouer le test en cours.

Un cas honnête : sur le poste de développement, Chromium rencontre au hasard une panne réseau du
système (`net::ERR_NO_BUFFER_SPACE`), reproduite hors de Prévo. Plutôt que de masquer l'échec, la
suite rejoue **une seule fois** le test concerné en le signalant ; toute autre erreur le fait
échouer.

## 5. Ce qui reste à l'humain

- Les **décisions** : nom du produit, périmètre de chaque lot, format des données, arbitrages entre
  commodité et sûreté.
- Les **vérifications que l'IA ne peut pas faire seule**, demandées à Nicolas : essai sur un vrai
  dossier partagé, sur un vrai téléphone, impression d'un bon de travail, installation de Python sur
  un poste qui n'en a pas. Elles sont **prévues** ; leur résultat n'est pas consigné ici.
- La **revue finale**, prévue par une session neuve qui n'a pas écrit le code.

## 6. Ce que cette méthode ne garantit pas

- Des tests verts prouvent que les cas écrits passent, pas qu'il n'existe pas d'autre défaut. La
  relecture indépendante réduit ce risque sans l'annuler.
- Les chiffres de performance sont ceux d'un poste et d'un jeu de données précis.
- Prévo n'a pas d'authentification (voir les limites dans le `README.md`) : c'est un choix de
  périmètre assumé, pas une propriété que la méthode corrigerait.
- Les lots 2 à 4 ne sont pas réalisés.

## 7. À retenir pour piloter une IA

1. Faire écrire et valider le cahier des charges et ses critères de succès avant le code.
2. Écrire le contrat entre les morceaux avant de distribuer le travail.
3. Accepter une tâche sur preuve relancée par soi-même, jamais sur déclaration.
4. Faire relire par quelqu'un qui n'a pas écrit le code.
5. Reproduire chaque défaut par un test avant de le corriger.
6. Réserver à l'humain les décisions, et lui demander les vérifications physiques.
