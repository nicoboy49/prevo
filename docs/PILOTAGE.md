# Comment Prévo a été piloté

Prévo a été écrit par des IA (Claude Code) sous la direction de Nicolas Briand. Ce document décrit
la méthode de pilotage, ce qu'elle a permis de constater, et ce qu'elle n'a pas encore vérifié. Il
vise un lecteur qui se demande si un projet confié à une IA peut être contrôlé, et comment.

Les chiffres cités viennent de commandes lancées au moment de la rédaction (suite de tests, historique
git) ou du journal de chantier, qui consigne chaque vérification. Ce qui n'a pas été vérifié est
présenté comme prévu. Les sections 1 à 6 décrivent la méthode et le lot 1 ; la section 7 décrit le
lot 2, la section 8 le lot 3 et la section 9 le lot 3 bis, menés de la même façon.

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

- Le lot 1 est découpé en **19 tâches réparties en 7 vagues**. Une vague regroupe des tâches
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
- **Suite de tests.** À la fin du lot 1 : 411 tests exécutés, tous verts, 2 sauts (l'aller-retour
  par le vrai Excel, non demandé). Toute erreur JavaScript dans le navigateur fait échouer le test
  en cours.

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
- Les lots 4 et « Import » ne sont pas réalisés.

## 7. Lot 2 : préventif, magasin, causes fréquentes

Le lot 2 ajoute la maintenance préventive, le magasin de pièces, la sortie de pièces depuis l'ordre
de travail, l'encart des causes fréquentes et un format de fichiers v2. Il a suivi exactement la
méthode du lot 1 : cahier des charges validé par Nicolas avant le code, contrat d'architecture
complété avant les tâches, vérification relancée par l'orchestrateur, relecture indépendante à
chaque vague, recette automatisée.

### Les décisions de Nicolas

Le cahier des charges du lot 2 compte **14 décisions** (D19 à D32) et **15 critères de succès**
(CS21 à CS35). Celles qui engageaient l'utilisateur ont été tranchées par Nicolas, sur des options
présentées avec leurs conséquences :

- **Lien entre une demande et le préventif où l'anomalie a été vue** (D21) : un champ de plus dans
  les demandes, pour que la demande et l'ordre de travail préventif se renvoient l'un à l'autre ;
  il servira au préventif suggéré du lot 3 bis.
- **Point de commande** (D23) : il reste **saisi** par le responsable ; Prévo affiche à côté une
  valeur suggérée, calculée sur la consommation de l'année, qu'un bouton permet de reprendre.
- **Lignes de check-list d'une gamme** (D26) : leur suppression est permise, seule exception à la
  règle « une ligne n'est jamais supprimée », car chaque ordre de travail garde sa propre copie ;
  la suppression est inscrite au journal.
- **Sauvegarde avant le changement de format** : décidée en cours de lot, après la validation du
  cahier des charges. À la première ouverture d'une base du lot 1, Prévo fait une sauvegarde
  complète (« Avant format 2 »), puis seulement passe la base au format 2 ; si la sauvegarde
  échoue, rien n'est changé et le passage est retenté plus tard. Une tâche a été ajoutée au plan
  pour cela.

D'autres choix, plus techniques, ont été pris par l'orchestrateur et signalés à Nicolas : ne pas
générer automatiquement les ordres de travail préventifs tant que la sauvegarde « avant format 2 »
n'a pas réussi ; garder l'avancement des gammes quand un compteur est remis à zéro ; tenir compte
des pièces déjà sorties avant de refuser la planification d'un ordre de travail.

### Les chiffres

- **18 tâches** (T20 à T37) réparties en **6 vagues** ; une étiquette git par vague validée.
- **5 relectures de vague** à la date de rédaction (vagues 1 à 5), qui ont trouvé **3 défauts
  critiques** (détail ci-dessous), tous corrigés.
- **581 tests** dans la suite (411 à la fin du lot 1). L'exécution complète finale du lot 2, lancée
  par l'outil de vérification à la clôture de la dernière vague, est verte (code retour 0) ; les
  tests du vrai Excel y sont sautés, car ils ne tournent qu'à la demande, et ont passé à part (4 sur 4).
- **Performance** mesurée sur un jeu de charge de 500 équipements et 5 000 ordres de travail :
  premier chargement, qui génère 20 ordres de travail préventifs, d'environ 1,1 s ; chargements
  suivants d'environ 0,5 s ; création d'une demande d'environ 0,07 s ; sortie d'une pièce depuis
  l'ordre de travail d'environ 0,27 s (budgets fixés d'avance : 2 s, 1 s et 1 s).

### Ce que les relectures et la recette ont trouvé

Les trois défauts critiques :

- une demande signalée depuis un ordre de travail préventif **verrouillé** (clôturé
  administrativement) **modifiait cet ordre de travail**, ce que la règle de verrouillage du lot 1
  interdit ; désormais la demande garde le lien, mais l'ordre de travail n'est jamais modifié ;
- une gamme **n'était pas recalée** quand la date de fin d'un ordre de travail, saisie par erreur
  un an trop tard, était corrigée après réouverture : la gamme gardait la date erronée et ne
  générait plus rien pendant treize mois ; désormais la date de l'ordre de travail le plus récent
  de la gamme fait foi ;
- le test de performance **ne pouvait pas échouer** sur la génération du préventif : il gardait la
  médiane de trois chargements, alors que seul le premier génère ; il vérifie maintenant le premier
  chargement lui-même, et l'orchestrateur a prouvé qu'il échoue quand on force un budget trop bas.

Parmi les autres défauts relevés et corrigés :

- la **remise à zéro d'un compteur** (compteur remplacé) faisait calculer à une gamme un usage
  négatif : l'entretien suivant aurait été sauté pendant environ trois ans ; la gamme garde
  maintenant son avancement, et l'ajustement est inscrit au journal ;
- la règle de planification **refusait à tort** un ordre de travail dont les pièces étaient déjà
  sorties du magasin (le stock était comparé au total prévu, sans déduire ce qui était déjà
  sorti) : signalé par le sous-agent des ordres de travail, la règle a été révisée ;
- des **zones tactiles trop petites sur téléphone** (de 19 à 45 px de haut au lieu de 48 px, la
  taille minimale retenue pour une zone tactile sur téléphone) dans l'encart des causes fréquentes, le préventif et le
  magasin, trouvées par une relecture puis par la recette ;
- un **test fragile** qui lisait un message d'information (toast) après sa disparition, au bout de
  4 s, quand le poste était chargé : il échouait au hasard ; les tests concernés enregistrent
  maintenant chaque message au moment où il s'affiche.

La règle du lot 1 est restée : reproduire un défaut par un test qui échoue, puis le corriger.

### Les preuves propres au lot 2

- **Vrai Excel au format v2.** Avec `PREVO_TEST_EXCEL=1`, Excel ouvre et réenregistre les fichiers
  qui portent les nouvelles colonnes : les valeurs v2 reviennent intactes. Une base complète du lot
  1, passée par Excel, s'ouvre : la sauvegarde « avant format 2 » est faite, la base passe au
  format 2, les colonnes manquantes ne donnent qu'une information, puis elles sont ajoutées en fin
  de fichier sans toucher aux autres cellules. Les 4 tests Excel réel ont passé lors de leur
  vérification par l'orchestrateur.
- **Recette en modes serveur et démo.** Les scénarios du lot 2 sont rejoués dans Chromium comme un
  utilisateur : panne sur pompe avec le stock du kit qui baisse de un, gamme mensuelle échue (un
  seul ordre de travail après trois rechargements, et avec deux postes ouverts en même temps),
  gammes au compteur et au seuil, sortie qui rendrait le stock négatif, achat jusqu'à la
  réception, causes fréquentes vues par les trois profils, anomalie pendant un préventif, liste
  blanche du serveur, affichage sur téléphone. Les scénarios du lot 1 repassent aussi.
- **Démo reproductible.** Le jeu de démo de treize mois, régénéré, est identique à l'octet au jeu
  versionné ; les tests lisent les identifiants des objets de scénario dans un fichier produit par
  le générateur, au lieu de numéros écrits en dur.
- **Serveur en liste blanche.** Le serveur ne sert plus que l'application : le cahier des charges,
  la documentation, les tests et le code du serveur répondent « introuvable ». Un relecteur a
  essayé 125 chemins d'attaque sur cette liste : aucune fuite.

## 8. Lot 3 : indicateurs, planning, contrôles, rapport mensuel

Le lot 3 ajoute le pilotage : indicateurs et graphiques, planning de la semaine, étiquettes QR par
lot, contrôles réglementaires, équipe et habilitations, et un rapport mensuel figé. Il a suivi la
même méthode : cahier des charges validé par Nicolas avant le code, contrat d'architecture écrit
avant les tâches (§15 de `docs/ARCHITECTURE.md`), vérification relancée par l'orchestrateur,
relecture indépendante, recette automatisée.

Une différence d'organisation : la méthode a été **allégée**. L'orchestrateur a écrit lui-même les
tâches courtes ou très liées au contrat (socle, règles des indicateurs, des contrôles, de l'équipe et
du planning, écran du planning, rapport mensuel, accueil, recette, performance, documentation) ; des
sous-agents ont écrit les autres (jeu de démo, étiquettes, contrôles, équipe, paramètres, écran des
indicateurs). Le code de l'orchestrateur a été relu comme celui des sous-agents, par des relecteurs
qui ne l'avaient pas écrit. C'est utile : six des huit défauts critiques trouvés étaient dans son
code ou dans ses corrections.

### Les décisions de Nicolas

Le cahier des charges du lot 3 compte **17 décisions** (D33 à D49) et **15 critères de succès**
(CS36 à CS50). Trois décisions ont été tranchées par Nicolas sur des options présentées avec leurs
conséquences, et trois propositions validées :

- **Définition du MTTR** (D36) : durée d'arrêt moyenne d'une panne, attentes comprises (le « temps
  moyen de rétablissement » de la norme CEI 60050-192) ; avec, en plus, « dont attente de pièces »
  quand l'historique des statuts de la panne est complet dans le journal.
- **Repère « réparer ou remplacer ? »** (D44) : seuil en paramètre modifiable, **50 %** par défaut,
  du coût de maintenance des 12 derniers mois rapporté à la valeur de remplacement ; l'équipement est
  signalé « à examiner », jamais « à remplacer ».
- **Diffusion du rapport** (D45) : Prévo n'envoie rien ; « Préparer un courriel » ouvre la
  messagerie du poste avec un résumé, et le rapport reste imprimable.
- Propositions validées : l'écran Équipe est ouvert au technicien **sans aucun taux horaire** ; le
  planning va du lundi au dimanche ; deux formats de planches d'étiquettes (24 et 8 par page).

D'autres choix, plus techniques, ont été pris par l'orchestrateur et signalés à Nicolas : un MTBF ou
une disponibilité qui serait négatif (durée d'arrêt plus longue que le temps requis de la période)
est déclaré non calculable, avec sa raison ; sans panne sur la période, la disponibilité vaut 100 % ;
pour un délai cible de 0 h (« immédiat »), seule la médiane est affichée, car une part « dans le
délai » de 0 % serait trompeuse ; une habilitation dont l'échéance est illisible est tenue pour échue.

### Les chiffres

- **14 tâches** (T41 à T54) réparties en **6 vagues** ; une étiquette git par vague validée, pour
  les vagues 1 à 5. La vérification outillée de la 6e, qui relance la suite complète d'un seul
  tenant, a été coupée deux fois par Claude Code faute de mémoire sur le poste. La suite complète a
  donc été passée en quatre lots, tous verts, et Nicolas a décidé de clore le lot sur cette preuve.
- **3 relectures** : vagues 1 et 2, vagues 3 à 5, puis une relecture finale des dernières tâches et
  de toutes les corrections. Elles ont trouvé **8 défauts critiques** (7, puis 1 à la relecture
  finale ; détail ci-dessous), tous corrigés : chaque fois, un test qui échouait d'abord.
- **718 tests** dans la suite (581 à la fin du lot 2).
- **Performance** mesurée sur le jeu de charge de 500 équipements et 5 000 ordres de travail :
  premier chargement d'environ 1,3 s (budget 2 s) ; écran Indicateurs sur 12 mois, ECharts compris,
  d'environ 0,6 s (budget 2 s) ; planning de la semaine en quelques millisecondes (budget 1 s) ;
  rapport mensuel figé d'environ 0,4 s (budget 5 s). Chaque budget a été forcé à 1 ms pour prouver
  que le test sait échouer.

### Ce que les relectures et la recette ont trouvé

Les huit défauts critiques :

- un document `.html` (un rapport mensuel, par exemple) ouvert **hors serveur** (modes dossier et
  démo) **exécutait ses scripts** : un fichier déposé dans les documents aurait pu agir dans Prévo ;
  il s'affiche maintenant dans un cadre isolé où aucun script ne s'exécute, comme en mode serveur ;
- le **MTBF et la disponibilité pouvaient être négatifs** quand la durée d'arrêt dépassait le temps
  requis de la période (panne à cheval sur une période courte) ; ils sont maintenant déclarés non
  calculables, avec la raison ;
- une demande **regroupée après coup** sur un OT pouvait dater la panne, trop tard, ce qui faussait le
  MTBF et les délais de prise en charge. Le défaut a été trouvé **deux fois** : la première correction
  laissait passer les OT sans lien direct vers leur demande ;
- la **part du préventif** affichait un nombre de saisies comme si c'était des heures : une régression
  introduite par une correction de l'orchestrateur ;
- sur téléphone, l'onglet des rapports mensuels **faisait défiler toute la page** de côté (classe CSS
  inexistante). La recette ne l'avait pas vu, car la liste des rapports y était vide ;
- les **liens vers les OT sources** de chaque chiffre, exigés par le cahier des charges (D35),
  manquaient à l'écran des indicateurs ;
- l'OT créé depuis un contrôle réglementaire n'avait pas le **titre prévu** par le cahier des charges
  (D40 : « Levée des observations — … » ou « Accompagnement du contrôle — … ») : le test vérifiait
  seulement que le titre contenait la nature du contrôle.

Parmi les autres défauts relevés et corrigés :

- un test du rapport mensuel avait le mois **écrit en dur** : il aurait échoué à partir du 1er novembre ;
  il calcule maintenant le mois écoulé depuis la date du jour ;
- un test du lot 2 **échouait chaque nuit avant 10 h** : il fixait une date de fin d'OT à 10 h le jour
  même, refusée comme « dans le futur » depuis la dernière vague du lot 2. Personne ne l'avait vu, car
  la suite tournait toujours en journée ; c'est le passage complet de la fin du lot 3, à 3 h du matin,
  qui l'a révélé ;
- une ancienne habilitation à l'échéance illisible **l'emportait sur un renouvellement** valide ;
- une date impossible (« 2026-02-30 ») était rangée dans le planning, et un contrôle à la date
  illisible passait pour « à jour » ;
- le **planning était illisible** à 1 440 px de large : vu par l'orchestrateur en relisant les
  captures de la recette, alors que les tests passaient ; la relecture finale a ensuite montré qu'à
  1 920 px la grille était plus étroite qu'à 1 440 px, et que le filtre sur un technicien se perdait
  au changement de semaine ;
- une modification de l'accueil a cassé un test du lot 1 (paramètres) que l'orchestrateur n'avait pas
  relancé : il n'avait lancé que les tests de l'accueil. Leçon notée : après une modification d'un
  écran partagé, relancer aussi les tests des écrans qui en dépendent.

### Les preuves propres au lot 3

- **Calcul à la main.** Pour trois équipements (dont un critique), les indicateurs **affichés** à
  l'écran sont égaux à ceux d'un calcul Python indépendant, écrit à part sur les fichiers CSV, en modes
  serveur et démo.
- **Rapport autonome.** Le rapport figé s'ouvre seul, sans Prévo ni réseau (aucune requête, aucun
  script) et s'imprime sur une page A4.
- **Recette en modes serveur et démo.** Planification avec avertissement d'habilitation, contrôle
  réalisé et habilitation renouvelée (le compteur de l'accueil baisse de un), étiquettes d'un atelier,
  rapport figé puis rouvert (et téléchargé en démo), 9 écrans × 3 profils, captures à 1 440 et 375 px
  relues. Les recettes des lots 1 et 2 repassent. Le relecteur final a injecté sept défauts dans une
  copie du code (MTTR faussé, droits d'un profil, débordement à 375 px, compteur, avertissement
  d'habilitation masqué, étiquette manquante…) : la recette les a tous détectés.
- **Rien d'autre n'a bougé.** Les bibliothèques de `js/lib/` sont identiques à celles du lot 1 (seule
  leur notice de licence a été corrigée : ECharts est en version 5.5.1, et non 5.6.0 comme écrit
  depuis le lot 1) ; le format des fichiers reste en version 2.

Limite connue : dans le graphique « charge et capacité », les semaines 1 et 4 restent proches pour
une personne atteinte de protanopie ; elles se distinguent par leur position, la légende et le
tableau des valeurs.

## 9. Lot 3 bis : préventif suggéré

Le lot 3 bis fait relire l'historique par Prévo pour proposer au responsable des **suggestions de
préventif** : créer une gamme là où les mêmes pannes se répètent, revoir le préventif d'un équipement
qui tombe en panne malgré sa gamme, revoir une gamme dont les visites trouvent souvent une anomalie,
allonger une gamme qui ne trouve jamais rien. Il rend aussi l'encart des « causes fréquentes » honnête
sur la solidité de ses chiffres. Même méthode qu'au lot 3, allégée : l'orchestrateur a écrit le socle,
les règles, l'encart, l'accueil, la recette et la documentation ; des sous-agents ont écrit le jeu de
démo et les écrans.

### Les décisions de Nicolas

Le cahier des charges compte **14 décisions** (D50 à D63) et **13 critères de succès** (CS51 à CS63).
Une règle de fond, posée avant tout le reste : **Prévo ne modifie jamais une gamme tout seul**. Une
suggestion montre sa règle, ses chiffres, ses dates et ses OT ; le responsable décide, et sa décision
(gamme créée ou modifiée, suggestion ignorée avec un motif) est inscrite au journal. Trois questions
ont été tranchées par Nicolas, chacune sur l'option recommandée :

- **Quelles pannes comptent pour « revoir le préventif »** (D53) : toutes les causes, sans changer le
  format des fichiers. Une gamme ne dit pas quelles pannes elle prévient ; la suggestion dit donc
  « à examiner », et le responsable ignore, avec un motif, celles qui sont sans objet. L'autre option
  ajoutait un champ à chaque gamme et un nouveau format de fichiers.
- **Aucune périodicité proposée** (D56) : Prévo montre les faits (périodicité actuelle, intervalle
  médian entre les pannes, dates des visites) et le responsable saisit la nouvelle valeur. La règle
  reconnue (inspecter à la moitié de l'intervalle entre le premier signe de dégradation et la panne)
  demande une donnée que Prévo n'a pas ; un « −25 % » pré-rempli aurait eu l'air d'un calcul.
- **Solidité des causes fréquentes** (D59) : sous une vingtaine de cas, la mention « Peu de cas : à
  prendre comme une piste », et la fourchette réelle de chaque cause dans un détail que l'on déplie
  (« 7 cas sur 12 », c'est « entre 32 % et 81 % des cas », intervalle de Wilson à 95 %).

Deux choix de l'orchestrateur, consignés au contrat : pour « allonger une gamme », une base passée de
l'ancien format au nouveau ne compte que les visites faites après ce passage (avant, l'absence
d'anomalie n'était pas saisie) ; une suggestion ignorée ne revient que si les faits **postérieurs**
à la décision atteignent de nouveau le seuil.

### Les chiffres

- **9 tâches** (T55 à T63) en **6 vagues**, toutes validées par l'outil de vérification ; une
  étiquette git par vague, puis l'étiquette `lot-3-bis`. La suite complète finale est partagée entre
  les deux dernières vagues (environ 7 minutes chacune), pour que chaque vérification tienne au
  premier plan sans être coupée faute de mémoire, comme au lot 3. Les vagues déjà validées ont été
  revérifiées après chaque série de corrections.
- **2 relectures** (les cinq premières tâches, puis une relecture finale des écrans, de la recette
  et de toutes les corrections) : **1 défaut critique** et 19 défauts mineurs, tous corrigés.
- **781 tests** dans la suite (718 à la fin du lot 3).
- **Performance** sur le jeu de charge (500 équipements, 5 000 OT) : l'onglet des suggestions
  s'affiche en moins de 0,1 s, mise en page comprise (budget 1 s ; 75 suggestions), et le chargement
  complet reste sous la seconde en médiane (budget 2 s). Le budget a été forcé à 1 ms pour prouver
  que le test sait échouer.

### Ce que les relectures ont trouvé

La relecture des cinq premières tâches n'a trouvé **aucun défaut critique** et neuf défauts mineurs,
tous corrigés. Le plus parlant : pour trois pannes survenues le même jour, la suggestion annonçait
« environ une par jour », une fréquence fausse ; elle n'en annonce plus aucune. Le relecteur a aussi
prouvé que le jeu de démo complété garde le contenu de toutes les lignes des lots précédents, alors
que leurs numéros se sont décalés.

La relecture finale a trouvé **un défaut critique** : les cartes « créer une gamme » et « revoir le
préventif » n'affichaient **aucune date**, alors que le critère CS53 exige les dates de chaque
suggestion. Le contrat d'architecture les avait oubliées, et ni les tests ni la recette ne les
vérifiaient : la vérification outillée passait donc. Chaque carte montre maintenant la période des
faits et la date de chaque OT lié. Parmi les dix défauts mineurs : un motif contenant un séparateur
de ligne Unicode était écrit au journal mais jamais relu (la suggestion restait ouverte) ; fermer la
fenêtre « Ignorer » avec Échap pendant l'écriture laissait un compteur faux ; sur téléphone, l'onglet
« Suggestions » ouvert depuis l'accueil était hors de vue dans sa barre. Chaque nouveau test a été
lancé sur l'ancien code pour prouver qu'il échouait. Le relecteur a aussi vérifié, sans y trouver de
défaut, que rien n'est écrit sans action (le fichier des gammes reste identique à l'octet sur
114 affichages, par les trois profils) et qu'un motif piégé s'affiche comme du texte.

### Les preuves propres au lot 3 bis

- **Calcul indépendant** : sur le jeu de démo, toutes les suggestions (clés, ordre, nombres, dates,
  OT, DI, décision précédente) sont égales à un calcul Python écrit à part, qui relit les CSV.
- **Défauts injectés** : quatre défauts introduits volontairement dans les règles (suggérer
  d'allonger une gamme d'un équipement critique, compter une panne de la minute même d'une décision,
  décaler la période d'un jour, oublier le passage au nouveau format) ont tous été détectés par les
  tests.
- **Rien n'est écrit sans action** : le fichier des gammes reste identique à l'octet après
  l'ouverture de Prévo, des onglets et des fiches par les trois profils.

## 10. Lot 4 : assistant IA, dictée, guide, version 1.0.0

Le lot 4 ajoute un **assistant IA** qui propose sans jamais décider (reformuler une demande, mettre en
forme un compte rendu, proposer les codes de défaillance, une check-list de départ, le résumé de
l'historique d'un équipement, le commentaire du rapport mensuel), la **dictée vocale** dans les champs
de texte, l'écran **« Ce poste »** (réglages propres à chaque navigateur, thème clair), le **https** en
option, un **guide d'utilisation** imprimable, la **fiche technique** des fichiers CSV et des finitions.
Il clôt la version **v1.0.0**. Même méthode qu'aux lots 3 et 3 bis : l'orchestrateur a écrit le socle,
le serveur, la fiche technique, la dictée, les fonctions IA de la gamme et du rapport, les finitions,
la recette et la documentation ; des sous-agents ont écrit les règles de l'IA, l'écran « Ce poste », les
fonctions IA de la demande et de l'OT, le guide, puis des corrections du relais du serveur.

### Les décisions de Nicolas

Le cahier des charges compte **16 décisions** (D64 à D79) et **15 critères de succès** (CS64 à CS78).
Règle de fond, celle du brief : **l'IA propose, l'humain valide**. Rien n'est enregistré sans le
bouton habituel ; sans IA, Prévo est identique et n'appelle rien. Quatre réponses de Nicolas :

- **Qui décide d'envoyer des données hors de l'atelier** (D67) : le responsable. Par défaut, seule une
  IA installée dans l'atelier (Ollama) est utilisable ; un service en ligne demande son autorisation,
  puis un avertissement explicite sur le poste.
- **Le modèle conseillé** (D72) : `qwen2.5:7b`, déjà installé, **mesuré** sur son PC plutôt que choisi
  sur la foi d'articles (aucune source ne mesure le français sur des textes de maintenance).
- **Le thème clair** (D76) : oui, réglé par poste.
- **La publication** (D79) : dépôt GitHub privé d'abord (ses élèves le testent), envoi en fin de lot
  seulement, adresse de commit professionnelle.

### Les chiffres

- **13 tâches** (T64 à T76) en **7 vagues**, chacune validée par l'outil de vérification et revérifiée
  après les corrections ; la suite complète finale est partagée entre les deux dernières vagues.
- **1 relecture complète** du lot (sous-agent, défauts reproduits dans une copie du dépôt) : **3 défauts
  critiques** et 12 mineurs, tous traités ; la recette de l'orchestrateur en avait trouvé un de plus
  avant la relecture.
- **Plus de 35 défauts injectés** volontairement pour prouver que les tests savent échouer ; 6 n'étaient
  pas détectés au premier essai et ont reçu un test.
- **907 tests** dans la suite (781 à la fin du lot 3 bis), plus l'essai réel de l'IA, lancé à part.
- **Performance** sur le jeu de charge (500 équipements, 5 000 OT) : chargement complet 1,3 s au
  premier passage et 0,6 s ensuite (budget 2 s), **aucun appel réseau à l'ouverture** tant que l'IA
  n'est pas activée (vérifié en mode serveur et en démo).
- **Essai réel du modèle conseillé** (`qwen2.5:7b` sur le PC de Nicolas, carte RTX 3060 6 Go) :
  **32 codes justes sur 36** (89 %) sur douze interventions réelles de la démo, aucun code inventé
  (liste fermée imposée au modèle), réponse en 8,6 s en médiane ; reformulation d'une demande en
  9 s, compte rendu structuré en 16 s. Ses erreurs sont des choix voisins, et il a une fois proposé
  l'impact « Sécurité » pour un compresseur qui « passe en sécurité » : la relecture humaine reste
  nécessaire, ce que le guide rappelle.

### Ce que les relectures et la recette ont trouvé

La recette a trouvé un défaut que les tests de chaque écran ne voyaient pas : quand le responsable
**retire** l'autorisation des services en ligne, le bouton IA restait affiché sur l'écran ouvert d'un
technicien. Rien ne partait (la demande était refusée), mais l'écran mentait. Les boutons suivent
désormais l'état de l'IA sans réafficher l'écran.

La relecture a trouvé **trois défauts critiques** :

- un commentaire proposé par l'IA pour **septembre** pouvait être figé dans le rapport d'**août**, avec
  les chiffres de septembre et la mention « relu et validé par le responsable » ;
- la dictée **effaçait** ce que l'on tapait au clavier pendant qu'elle écoutait (et une proposition
  de l'IA posée entre-temps), alors que la règle est « jamais d'écrasement » ;
- en thème clair, les **badges d'état** (« en retard », « en service », « Criticité B ») étaient sous
  le contraste exigé : le test ne mesurait que des couples de couleurs, pas les textes affichés. Il
  mesure maintenant chaque texte réellement affiché sur douze écrans.

Parmi les mineurs : le relais du serveur acceptait d'appeler un service en ligne même sans
l'autorisation du responsable (le contrôle n'était fait que dans le navigateur) ; un nombre écrit en
lettres (« trois points ») passait le contrôle des chiffres du commentaire ; aucun test ne prouvait
qu'une réponse piégée de l'IA (du code HTML) serait affichée comme du texte. Tous ont reçu un test qui
échouait avant la correction.

### Les preuves propres au lot 4

- **Jamais un vrai modèle dans la suite** : un faux fournisseur d'IA imite Ollama et les API
  compatibles OpenAI, y compris les réponses lentes, illisibles, inventées, chiffrées, tronquées,
  piégées ou trop grandes ; il garde chaque requête reçue, ce qui prouve ce qui part (aucun nom de
  personne, aucun taux, aucun coût d'OT) et que la clé ne va qu'au bon service.
- **Rien n'est écrit sans action** : avant le bouton habituel, les fichiers restent identiques à
  l'octet, quelle que soit la proposition utilisée ou ignorée.
- **La clé d'un service en ligne** n'apparaît dans aucun fichier, journal, console ni page.
- **Le guide** s'ouvre sans aucune ressource externe, s'imprime, et ses liens sont vérifiés.

### La publication

Le dépôt privé `nicoboy49/prevo` a été créé par Nicolas ; l'historique a été réécrit avant le premier
envoi pour porter son adresse professionnelle (contenu identique, vérifié, sauvegarde gardée). Les
étiquettes `lot-1` à `lot-3-bis` y sont ; `lot-4` et `v1.0.0` sont envoyées à la clôture.

## 11. À retenir pour piloter une IA

1. Faire écrire et valider le cahier des charges et ses critères de succès avant le code.
2. Écrire le contrat entre les morceaux avant de distribuer le travail.
3. Accepter une tâche sur preuve relancée par soi-même, jamais sur déclaration.
4. Faire relire par quelqu'un qui n'a pas écrit le code.
5. Reproduire chaque défaut par un test avant de le corriger.
6. Réserver à l'humain les décisions, et lui demander les vérifications physiques.
7. Mesurer un modèle d'IA sur ses propres données plutôt que de le choisir sur réputation, et ne
   jamais laisser un vrai modèle dans la suite de tests : un faux fournisseur rend les tests
   rapides, reproductibles, et capables de simuler les pannes.
