# Comment Prévo a été piloté

Prévo a été écrit par des IA (Claude Code) sous la direction de Nicolas Briand. Ce document décrit
la méthode de pilotage, ce qu'elle a permis de constater, et ce qu'elle n'a pas encore vérifié. Il
vise un lecteur qui se demande si un projet confié à une IA peut être contrôlé, et comment.

Les chiffres cités viennent de commandes lancées au moment de la rédaction (suite de tests, historique
git) ou du journal de chantier, qui consigne chaque vérification. Ce qui n'a pas été vérifié est
présenté comme prévu. Les sections 1 à 6 décrivent la méthode et le lot 1 ; la section 7 décrit le
lot 2, la section 8 le lot 3, la section 9 le lot 3 bis, la section 10 le lot 4, la section 11 le
lot 5, la section 12 le lot 6 et la section 13 le lot 7, menés de la même façon ; la section 14 en
tire les leçons.

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

### La clôture

La suite complète (907 tests) est passée en deux moitiés, chacune au premier plan : `test_[a-o]` (469
tests) le 21/10/2026 à 15 h 57, puis `test_[p-z]` (438 tests) en dernière vague, avant la pose des
étiquettes `lot-4` et **`v1.0.0`** sur le même commit. Sont sautés, en le disant, les essais qui
demandent le vrai Excel (`PREVO_TEST_EXCEL=1`) ou un vrai modèle d'IA (`PREVO_TEST_IA=1`, lancé à
part une fois, mesures ci-dessus). Les bibliothèques de `js/lib/` sont celles du lot 3, inchangées.

### La publication

Le dépôt privé a été créé par Nicolas, sous le nom qu'avait alors le projet (`nicoboy49/rouage` ; le
logiciel a pris le nom Prévo le 24 octobre, avec un nouveau dépôt, voir §12) ; l'historique a été réécrit avant le
premier envoi pour porter son adresse professionnelle (contenu identique, vérifié, sauvegarde gardée). Les
étiquettes `lot-1` à `lot-3-bis` y sont ; `lot-4` et `v1.0.0` sont envoyées à la clôture.

### Gel de l'interface avant le lancement (2026-10-22)

Après la refonte « bento » de l'accueil du responsable (menu latéral allégé, barre du bas en verre dépoli,
notification en bulle ; captures avant/après validées par Nicolas, PC 1440 et téléphone 390, clair et
sombre), **l'interface est gelée** : les captures du guide et du README sont régénérées sur cet état
(`outils/generer_captures.py`, horloge fixée à 9 h 30 du jour), et ce sont elles, puis les vidéos de
lancement, qui la montreront. Jusqu'au lancement, plus de changement visuel sans décision de Nicolas ;
les écrans Indicateurs et Rapport mensuel pourront reprendre ce style dans une passe suivante, sur demande.

## 11. Lot 5 : assistant d'import

Le lot 5 permet au responsable de **reprendre les données existantes** d'un atelier sans les ressaisir :
les référentiels (localisations, équipements, articles, fournisseurs, techniciens et habilitations, codes
de défaillance, compteurs, contrôles réglementaires, gammes) et l'**historique des interventions** d'une
autre GMAO, depuis Excel (.xlsx, .xls), OpenDocument (.ods), CSV ou un simple collage. Un assistant en
cinq étapes reconnaît les colonnes, montre un aperçu ligne par ligne et **n'écrit rien avant
« Importer »** ; une sauvegarde est faite juste avant, et l'import s'annule. Le format des fichiers ne
change pas. Même méthode qu'au lot 4 : l'orchestrateur a écrit le socle, la nouvelle règle de
disponibilité, la lecture des fichiers, l'écriture et l'annulation, les modèles à remplir et la consigne
de l'IA, et il a revérifié chaque tâche confiée ; des sous-agents ont écrit les fichiers d'essai, les
règles des référentiels et de l'historique, l'écran, la refonte de l'accueil (voir le gel de l'interface
ci-dessus), la recette et la documentation.

### Les décisions de Nicolas

Le cahier des charges compte **13 décisions** (D80 à D92) et **17 critères de succès** (CS79 à CS95).
Règle de fond : **rien n'est écrit sans validation** (aperçu complet, sauvegarde juste avant, journal,
« Annuler cet import »). La bibliothèque de lecture des classeurs, SheetJS 0.20.3, découle de sa réponse
de la veille (lire les .xls directement) ; elle est prise sur le site de l'éditeur, le paquet npm, plus
ancien, ayant deux failles corrigées depuis. Quatre questions ont été tranchées par Nicolas :

- **Quelles données** (D82) : les référentiels **et l'historique des interventions**, plus que l'option
  recommandée (les seuls référentiels) : les indicateurs et les suggestions de préventif servent dès le
  premier jour, au prix d'un effort plus grand et d'historiques très hétérogènes.
- **Les fiches déjà présentes** (D84) : compléter et mettre à jour, au choix à chaque import (case cochée
  par défaut), seulement pour les colonnes importées et non vides : une cellule vide n'efface jamais.
- **L'IA dans l'import** (D87) : en complément, sur les **seuls titres des colonnes** ; aucune donnée de
  l'atelier ne part, et la proposition reste « à confirmer ».
- **Les références introuvables** (D88) : localisations et fournisseurs créés par l'import et montrés dans
  l'aperçu ; un équipement parent ou un technicien inconnu reste une erreur.

En validant le cahier des charges, Nicolas a ajusté la règle de l'historique (D92) sur trois points :
l'ancien numéro d'OT de l'autre logiciel est gardé dans le compte rendu (« Ancien n° : … ») ; les
doublons sont cherchés d'abord par ce numéro (réimporter ne recrée rien), sinon par équipement, date et
titre, et ces doublons **supposés** sont montrés dans l'aperçu avec le choix de les importer quand même,
jamais écartés en silence ; un OT sans durée d'arrêt est exclu du MTTR et de la disponibilité, jamais
compté pour 0 h. Il a demandé de lancer le lot avec un envoi sur le dépôt privé en fin de lot, comme au
lot 4.

Le troisième ajustement visait l'OT importé. L'ancrage sur le code a montré que la disponibilité comptait
jusque-là une panne sans durée comme 0 h d'arrêt : l'orchestrateur a appliqué la règle à **tous** les OT,
importés ou saisis, sinon un même OT aurait été compté de deux façons ; Nicolas l'a confirmée le
2026-10-22. Pendant le lot, Nicolas a aussi arrêté une passe de design générale au profit d'une refonte de
l'accueil du responsable (avec le menu, la barre du bas et les notifications), validée sur planches
avant/après avant tout commit. Le 2026-10-22, il a tranché les derniers points : les contrôles propres
aux formulaires (périodicité d'un contrôle, date d'obtention d'une habilitation…) s'appliquent aussi à
l'import — une ligne que le formulaire refuserait est refusée à l'aperçu, avec le même message (T92) — et
trois choix de l'écran sont gardés (seuls les champs encore libres sont proposés à l'IA, une colonne « à
confirmer » est importée telle quelle avec un avertissement, la correspondance est retenue sur le poste dès
« Continuer »).

### Les chiffres

- **18 tâches** (T77 à T94) en **13 vagues**, chacune validée par l'outil de vérification ; six se sont
  ajoutées en cours de lot à la demande de Nicolas (refonte de l'accueil en trois tâches, contrôles des
  formulaires à l'import) ou pour tenir la suite complète en quatre vérifications de moins de 10 minutes.
- **28 commits** depuis la version 1.0.0 avant la clôture : 18 de tâches, 8 de la passe de lancement
  (licence, README, modèles d'issues, CHANGELOG, rangement, démo en ligne), le contrat du lot et une
  correction de test.
- **1 070 tests** dans la suite (907 à la fin du lot 4), partagée en quatre vérifications : 330, 282 et
  458 tests (a-h, i-o, p-z) ; l'essai réel d'Excel reste lancé à part.
- **Plus de 100 défauts injectés** volontairement pour prouver que les tests savent échouer, dont un par
  l'orchestrateur sur chaque tâche d'un sous-agent ; 5 n'étaient pas détectés au premier essai et ont
  reçu un test ou un cas de plus.
- **Environ 2 850 lignes** de code pour l'import (huit fichiers `import-*.js`), 4 200 lignes ajoutées à
  l'application en tout (accueil repensé compris) et 7 200 lignes de tests ; aucune bibliothèque nouvelle
  hormis SheetJS CE 0.20.3 (empreinte vérifiée), chargée seulement à la première lecture d'un tableur.
- **Recette** sur une base vide : un atelier complet repris depuis les dix fichiers d'essai (dont un par
  l'écran de bout en bout et un collé) ; réimport complet : **0 fiche créée** ; annulation : fichiers
  rendus à l'octet ; l'historique importé compte dans les indicateurs (MTBF 718,8 h, MTTR 2,5 h,
  disponibilité 99,8 % sur l'équipement témoin, égaux au calcul Python).
- **Performance** sur le jeu de charge (500 équipements, 5 000 OT) : premier chargement 1,4 s et 0,76 s
  ensuite (budget 2 s), sans SheetJS ; import de 5 000 articles : aperçu 0,5 s (budget 3 s), écriture
  1,1 s (budget 5 s) ; de 5 000 OT d'historique : aperçu 0,75 s, écriture 1,8 s.
- **Durée** : du contrat du lot (21 octobre 2026, 18 h 06) au dernier commit avant la clôture (22 octobre,
  9 h 01), nuit comprise.

### Ce que les relectures et la recette ont trouvé

Les **fichiers d'essai**, écrits avant le code de lecture, ont trouvé dans la bibliothèque SheetJS trois
pièges que ni sa documentation ni le contrat ne signalaient :

- une date d'un fichier OpenDocument arrive à minuit heure locale : convertie en temps universel, elle
  devenait la veille. Prévo calcule désormais les dates depuis leur numéro de série ;
- un petit fichier OpenDocument piégé (cellules « répétées ») vaut un million de cellules : SheetJS les
  déplie, mais annonce une feuille minuscule, si bien que le plafond de colonnes ne le voyait pas. Le
  contrôle est fait sur le contenu du fichier, avant de l'ouvrir ;
- SheetJS rend des lignes « à trous », qu'il faut compléter avant de compter les colonnes.

Pour l'**écriture**, le contrat prévoyait, si un autre poste avait créé la même fiche entre l'aperçu et
l'import, de passer la ligne en « identique » ou en « mise à jour » et d'écrire quand même.
L'orchestrateur a préféré **ne rien écrire et montrer le nouvel aperçu** : Prévo n'écrit jamais autre
chose que ce que le responsable a vu. Un test à deux postes le vérifie. Un échec en cours d'écriture
laisse un import partiel, que « Annuler cet import » défait.

Chaque tâche d'un sous-agent a été revérifiée par l'orchestrateur avec un défaut de plus, injecté par
lui (mise à jour appliquée alors qu'elle n'est pas demandée, doublon supposé traité comme sûr, case
« Compléter et mettre à jour » décochée par défaut) : chacun a fait échouer les tests ; les fichiers
d'essai régénérés sont identiques à l'octet. Les règles de l'historique ont ajouté un titre de colonne
oublié (« Temps (h) »), et un parent d'équipement est accepté n'importe où dans le fichier, pas seulement
plus haut : l'ordre des lignes d'une liste de parc ne doit pas compter. Ces écarts au contrat sont
consignés dans `docs/ARCHITECTURE.md` (§18).

Hors du lot, trois échecs ont été trouvés en chemin : un test de l'IA du lot 4 échouait selon la
charge du poste (une attente fixe dans le test ; c'est très probablement l'échec isolé vu au
lot 4) ; un test du planning échouait selon la date du jour, sur la version 1.0.0 aussi (horloge
désormais fixée) ; le premier chargement d'une grande base, génération du préventif comprise, dépassait
son budget, déjà sur la version précédente. La recette en a trouvé la cause **par la mesure** (profil du
navigateur) et non par supposition : à chaque ordre de travail préventif créé à l'ouverture, Prévo
relisait toute la table pour choisir l'identifiant suivant. Corrigé (un seul parcours), le premier
chargement passe de 1,5 à 2 s environ à 1,4 s ; aucun budget n'a été relevé.

La suite complète a enfin montré qu'avec les contrôles des formulaires, la ligne d'exemple du modèle des
codes de défaillance (« Corrosion ») était refusée, ce libellé existant déjà dans la démo : l'exemple a
été changé. C'est le rôle de la suite complète : voir ce que les tests de chaque tâche, lancés seuls, ne
voient pas.

### Les preuves propres au lot 5

- **Fichiers d'essai réalistes**, générés de façon reproductible : liste Excel d'un atelier avec un titre
  au-dessus des colonnes, colonnes dans le désordre et noms variés, la même en .ods et en .xls, articles
  exportés en CSV Windows-1252, collages tabulés, historique d'une autre GMAO avec durées manquantes et
  doublons, fichiers piégés (trop de lignes, chiffré, vide, sans en-tête, cellules répétées).
- **Calcul indépendant** : l'aperçu attendu de chaque fichier d'essai (lignes créées, mises à jour,
  refusées, avec leurs raisons) est recalculé par un programme Python écrit à part.
- **Rien n'est écrit avant « Importer »** : les 22 fichiers restent identiques à l'octet pendant tout
  l'assistant, retours en arrière compris, et aucune requête d'écriture ne part.
- **Retour arrière exact** : la sauvegarde « Avant import » est écrite avant les données ; « Annuler cet
  import » rend les tables touchées identiques à l'octet, en modes serveur, dossier et démo ; une
  sauvegarde impossible n'écrit rien.
- **Ce qui part vers l'IA** : avec le faux fournisseur, seuls les titres des colonnes partent ; une valeur
  de cellule repérable n'apparaît jamais dans la requête.
- **Disponibilité** : les tests de la nouvelle règle ont été écrits avant le code et échouaient sur
  l'ancien calcul ; le calcul Python indépendant des indicateurs du lot 3 suit la même règle.
- **Recette d'un atelier complet** (`tests/test_recette_lot5.py`) : base vide reprise depuis les fichiers
  d'essai en mode serveur, réimport sans création, annulation à l'octet, historique compté dans les
  indicateurs, les causes fréquentes et les suggestions ; sur la démo, chaque fichier donne les totaux
  annoncés par son mode d'emploi.

### La clôture

La suite complète (1 070 tests) est passée en quatre vérifications, chacune au premier plan et en moins
de 10 minutes : `test_[a-h]`, `test_[i-o]`, `test_[p-r]`, puis `test_[s-z]` en dernière vague, avant la
pose des étiquettes `lot-5` et **`v1.1.0`** sur le même commit. Sont sautés, en le disant, les essais qui
demandent le vrai Excel (`PREVO_TEST_EXCEL=1`) ou un vrai modèle d'IA (`PREVO_TEST_IA=1`). Les
bibliothèques de `js/lib/` sont celles du lot 4, inchangées ; seule SheetJS s'y ajoute.

### La publication

`main` et les étiquettes `lot-5` et `v1.1.0` sont envoyées à la clôture sur le dépôt, toujours privé
(accord de Nicolas, comme au lot 4) ; les étiquettes internes du chantier restent sur le poste. Le
passage en public suivra une dernière vérification de tout l'historique, validée par Nicolas.

## 12. Lot 6 : wiki de maintenance, version 1.2.0

Le lot 6 ajoute l'**encyclopédie de l'atelier** : une page par machine, par panne, par article, par
technicien, par intervention et par savoir-faire, calculée à partir des données (pannes et ce qui les a
réglées, interventions, pièces, stock, consignation en tête) et complétée par des textes courts
(« En bref » et « Astuces » d'une machine, « À quoi il sert » d'un article, savoir-faire communs aux
machines). Les textes viennent de l'**astuce** saisie à la clôture technique et de l'**ingestion** par
l'assistant IA : à la clôture administrative, l'ordre de travail entre dans une file que le responsable
traite depuis le journal du wiki ; le modèle propose, Prévo contrôle, le responsable valide. Le lot
renomme aussi le logiciel (**Prévo**, l'ancien nom appartenant à une autre GMAO), recrée le dépôt sans
trace de l'ancien nom, et ajoute le **signalement des nouvelles versions**. Même méthode qu'aux lots
précédents : contrat écrit avant le code, tâches vérifiées sur preuve, relecteurs indépendants ; le lot a
connu une **refonte** en cours de route (voir plus bas), validée sur maquette.

### Les décisions de Nicolas

Le cahier des charges compte **28 décisions** (D93 à D120) et **23 critères de succès** (CS96 à CS118).
Règle de fond : **deux couches, toujours** (D94) — la couche calculée est complète et utile sans IA ; le
texte rédigé ne s'y substitue jamais, et chaque phrase cite l'ordre de travail qui la fonde. Les points
tranchés par Nicolas :

- **Qui rédige la démo** (D98) : Claude Sonnet, par l'outil en ligne de commande de Claude Code, un agent
  par ordre de travail, avec la consigne de Prévo ; la passe de comparaison avec un modèle local (D102)
  est supprimée, le modèle local restant possible pour les clients.
- **Quand ingérer** (D104) : à la clôture administrative, dans une file que le responsable traite
  lui-même (« Traiter la file »), sur son poste, où l'IA est réglée : la dépense reste sous son contrôle.
- **L'astuce** (D110, son ajout à la validation) : une phrase courte à la clôture technique, cherchée avec
  les pages du wiki.
- **Les contradictions dans la démo** (D109) et l'**ordre d'ingestion** (D111 : par date d'intervention,
  un ordre de travail antérieur aux faits de la page ne se présente jamais comme le plus récent).
- **La relance** (D106 révisée) : une réponse refusée par les contrôles repart une fois vers le modèle
  avec la raison du refus, au lieu d'arrêter la fabrication.
- **La refonte 2** (D113 à D115, 23 octobre) : après une première version centrée sur la machine et ses
  synthèses, Nicolas a demandé que le wiki devienne l'encyclopédie complète, avec une maquette validée
  (« c'est ce que je veux »), la visibilité par profil (le demandeur ne voit ni les techniciens ni les
  interventions, les prix restent au responsable) et une fabrication de la démo en deux temps, le coût
  estimé étant donné avant chaque temps.
- **Après le temps 1** (D116 à D119) : un seul savoir-faire par geste, commun aux machines ; « En bref »
  en trois phrases et soixante mots, réécrit en entier à chaque intervention ; les ordres de travail des
  pièces consommées en petits numéros ; une nuit autonome avec un relecteur indépendant, un budget de
  15 $ et l'arrêt au-delà de 10 % de réponses refusées.
- **Le signalement des nouvelles versions** (D120) : lecture d'un fichier sur prevo.pro, au plus une
  fois par jour et par poste, seulement avec l'accord du responsable ; rien ne s'installe tout seul.

### Les chiffres

- **44 tâches** (T95 à T147) en **29 vagues**, chacune validée par l'outil de vérification ; les sept
  tâches de la première version (T95 à T101) sont gardées pour l'historique, la refonte en a redéfini
  36, et cinq se sont ajoutées après le temps 1 de la fabrication et pour la mise à jour signalée.
- **85 commits** depuis la version 1.1.0, le renommage compris ; **115 fichiers** touchés, environ
  **28 800 lignes ajoutées** : 7 760 lignes de code pour le wiki et la mise à jour (treize fichiers
  `wiki-*.js`, `mise-a-jour.js`) et 13 100 lignes de tests pour eux ; aucune bibliothèque nouvelle.
- **1 443 tests** dans la suite (1 070 à la fin du lot 5), jouée d'un trait en 36 minutes avant la
  clôture, puis une dernière fois par la vérification de chaque vague.
- **La démo** : 227 ordres de travail clôturés intégrés par Claude Sonnet, 137 propositions acceptées,
  90 sans rien à ajouter, 0 refusée ; 42 pages (13 machines, 4 articles, 6 savoir-faire au temps 1,
  puis le reste) ; 15 réponses refusées par les contrôles sur 242, toutes corrigées à la relance
  (6,2 %) ; **0,026 $ par ordre de travail** (5,16 $ le passage final). En tout, la fabrication de la démo
  a coûté environ **33 $** d'appels : cinq passes arrêtées sur refus pendant la mise au point de la
  consigne (14,25 $), une passe complète de l'ancienne version (8,41 $), le temps 1 (0,90 $), puis les
  trois passages de la nuit (9,46 $, dont deux arrêtés par le garde-fou des 10 %).
- **Performance** sur le jeu de charge (500 équipements, 5 000 ordres de travail) : page du wiki de la
  machine la plus chargée 15 ms (budget 500), recherche 168 ms la première fois (construction de
  l'index) puis 1 ms (budget 300), requête d'ingestion construite en 14 ms (budget 1 s) ; aucune requête
  réseau pour afficher ou chercher.
- **Durée** : du contrat du lot (22 octobre 2026, 10 h 49) à la clôture (24 octobre au soir), deux
  nuits comprises ; la journée du 24 a aussi porté le renommage, la recréation du dépôt et la mise à
  jour signalée.

### Ce que les relectures et la recette ont trouvé

Chaque tâche a été relue par un relecteur qui n'avait pas écrit le code ; le journal du chantier compte
une cinquantaine de défauts classés critiques, tous corrigés avant la vague suivante. Les plus
instructifs :

- une **fuite de visibilité** : les habilitations de tous les techniciens étaient visibles de tous les
  profils sur la page d'un technicien ; corrigée par les règles du module Équipe ;
- un **budget dépassable** : le garde-fou de la fabrication comptait les appels en cours à leur coût
  moyen, si bien qu'un dernier appel pouvait franchir le plafond ; il compte désormais l'appel le plus
  cher ;
- des **savoir-faire en double** (« Changer » et « Remplacer une garniture mécanique ») et des « En bref »
  qui s'allongeaient au fil des interventions : d'où les décisions D116 et D117, et une règle du « même
  geste » dans les contrôles ;
- la **fabrication réelle** elle-même a été la meilleure relecture de la consigne : cinq arrêts sur refus
  (une page de seize phrases, un vocabulaire de sécurité, un mot de trop) ont chacun donné une phrase de
  consigne ou un contrôle, puis la relance avec la raison du refus a rendu les arrêts inutiles ; dans la
  nuit, le garde-fou des 10 % s'est déclenché deux fois pour des défauts de forme corrigés à la relance
  (quatre phrases dans « En bref », rubrique « Astuces » omise), chacun réglé par une phrase de consigne ;
- un relecteur indépendant a relu le temps 1 avec la grille de Nicolas (doublons, « En bref » qui
  s'allonge, phrases mécaniques, liens manquants, nombres non tirés des ordres de travail) : aucun nombre
  inventé, deux ordres de travail cités sur une phrase qu'ils ne disaient pas, sept « En bref » qui
  dépensaient une phrase sur un fait d'une seule intervention ; trois phrases de consigne en sont sorties.

### Les preuves propres au lot 6

- **Faux modèle déterministe** (`tests/faux_wiki.py`) : une réponse construite seulement à partir du
  message envoyé, pour que les tests soient rapides et reproductibles, avec un mode qui contredit la page
  pour tester les contradictions ; le vrai modèle n'entre jamais dans la suite de tests.
- **Calcul indépendant** (`tests/calcul_wiki.py`) : les pages, les listes et l'accueil du wiki de la démo
  sont recalculés en Python et comparés à l'écran.
- **Traces de chaque appel** : modèle, nombre de tours, jetons, coût, réponse brute ; la vérification de
  la démo exige un seul tour, aucun outil, et l'intégrité du journal figé ; une fabrication relancée
  reprend ses réponses sans rappeler le modèle.
- **Parallélisme** : le même wiki avec un ou cinq agents, jamais deux envois pour le même ordre de
  travail.
- **Garde-fous** : budget en dollars (arrêt propre avant de dépasser), part de réponses refusées, relance
  une fois avec la raison ; chacun testé avec un défaut réintroduit.
- **Rien ne part sans accord** : aucune requête réseau pour afficher ou chercher ; le nom du technicien
  ne figure jamais dans un message envoyé au modèle ; la mise à jour signalée ne lit rien sans le
  réglage du responsable.
- **Recette** (`tests/test_recette_lot6.py`) en mode serveur : clôture technique avec astuce, clôture
  administrative, file, « Traiter la file » avec le faux fournisseur par le relais du serveur,
  validation, page de la machine avec ses petits numéros, savoir-faire créé, recherche, contradiction
  tranchée, le tout vérifié sur le disque.

### La clôture

La suite complète (1 443 tests) a été jouée d'un trait en 36 minutes (`.chantier/suite-complete-2026-10-24-ok.log`),
puis vérifiée par vagues : `test_[a-h]` avec le guide, `test_[i-o]`, `test_[p-r]`, `test_[s-z]`. Les longues passes ont
montré deux pièges de l'environnement, notés pour la suite : Claude Code arrête les commandes de fond quand la mémoire
du poste baisse (d'où des vérifications lancées en processus détaché), et un dossier synchronisé en ligne ralentit
le disque pendant les tests (synchronisation suspendue pour les dernières vagues). Les étiquettes `lot-6` et **`v1.2.0`** sont
posées sur le même commit à la clôture. Sont sautés, en le disant, les essais qui
demandent le vrai Excel (`PREVO_TEST_EXCEL=1`) ou un vrai modèle d'IA (`PREVO_TEST_IA=1`). Les
bibliothèques de `js/lib/` sont celles du lot 5, inchangées.

### La publication

Le dépôt a été **recréé** le 24 octobre sous le nouveau nom (`nicoboy49/prevo`, privé), avec l'historique
réécrit pour ne plus porter l'ancien nom ; `main` et les étiquettes publiques y sont envoyées à la
clôture avec l'accord de Nicolas, les étiquettes internes du chantier restant sur le poste.

## 13. Lot 7 : accès et installation, version 2.0.0

Jusqu'à la version 1.2, le serveur écoutait tout le réseau sans authentification et les profils n'étaient
« pas une sécurité ». Le lot 7 rend Prévo **installable seul et joignable en sécurité**. Un **assistant
d'installation**, dans le navigateur, pose trois questions (qui l'utilise, depuis où, le compte du
responsable) et règle le reste : trois **portées** (ce PC, le Wi-Fi de l'atelier, aussi hors de
l'atelier), des **comptes** vérifiés par le serveur sur chaque route, des **téléphones enrôlés** par QR
pour les demandeurs, le **https** dès que Prévo quitte le PC (certificat local fabriqué par mkcert, page
d'entrée qui guide chaque téléphone pour « faire confiance au PC atelier »), **Tailscale** ou le mandataire
de l'entreprise pour l'extérieur sans ouvrir de port sur la box, le **démarrage avec le PC**, la **copie
externe des sauvegardes**, un **mode Solo** pour la personne seule et les **corrections de l'audit** de la
version 1.1. Python est dans le zip : rien à installer. Le lot s'est fait en deux temps : une **étude**
complète (benchmark de 23 logiciels, comparatif des accès distants, options techniques), validée par
Nicolas avec ses réponses à quinze questions, puis le cahier des charges et le chantier.

### Les décisions de Nicolas

Le cahier des charges compte **20 décisions** (D121 à D140) et **19 critères de succès** (CS119 à CS137).
Règle de fond, tirée du brief : **mot de passe et https obligatoires dès que Prévo est joignable au-delà du
PC**, et **jamais de port ouvert sur la box**. Les points tranchés par Nicolas :

- **Qui se connecte comment** (D124, D125) : un compte nominatif pour le responsable et les techniciens ;
  à l'atelier, un demandeur n'a qu'un téléphone enrôlé par QR, sans mot de passe ; en Intranet, un mot de
  passe pour tous.
- **Le https dès le Wi-Fi** (D127) : un téléphone non configuré ne doit jamais voir une erreur du
  navigateur. D'où une porte d'entrée en http qui guide pas à pas Android et iPhone, et des étiquettes qui
  gardent l'adresse de la porte : celles imprimées en 1.2 restent valables. Nicolas a ajouté ce critère à
  la validation du cahier des charges (CS137).
- **Hors de l'atelier** (D128) : Tailscale nommé, détecté et guidé, jamais installé à la place de
  l'utilisateur ; le VPN de l'entreprise en alternative.
- **La distribution** (D131) : Python embarqué dans le zip, `C:\Prevo` par défaut. La version 3.12 prévue
  ne recevant plus de paquets Windows corrigés, c'est la 3.14 qui est livrée, validée aux arbitrages.
- **Le mode Solo** (D132) : le compte responsable avec un technicien « moi », « Nouvel OT » en premier et
  la clôture en une étape.
- **Hors périmètre** (D135, D136, D139) : pas d'annuaire d'entreprise, l'hébergement « sur demande »,
  ECharts 6 et le contrôle des archives importées reportés.
- **Les arbitrages de fin de chantier** (28 octobre) : les points tranchés par l'orchestrateur faute de
  texte, présentés sur une page à cocher avec le contexte minimum de chacun. Tous validés sauf un :
  l'**assistant IA**, que le chantier laissait au demandeur pour reformuler sa demande, est **réservé aux
  techniciens et au responsable**.

### Les chiffres

- **33 tâches** (T148 à T181) en **12 vagues**, chacune validée par l'outil de vérification ; environ la
  moitié faite par des sous-agents dans des copies de travail séparées, reportées sur la branche
  principale par l'orchestrateur après relecture et preuve rejouée.
- **45 commits** depuis la version 1.2.0, l'aide à l'écran comprise ; **171 fichiers** touchés, environ
  **27 400 lignes ajoutées** : 11 000 lignes de code (serveur, écrans de connexion,
  d'accès et de l'assistant, page d'entrée, lanceurs), 13 700 lignes de tests (28 fichiers de tests
  nouveaux), 2 500 lignes de documentation ; aucune bibliothèque nouvelle, ni côté serveur ni côté
  navigateur.
- **1 762 tests** dans la suite (1 449 à la fin du lot 6), jouée d'un trait en 39 minutes avant la clôture.
- **Durée** : de la demande d'étude (25 octobre, 22 h 23) à la clôture (29 octobre, avant la recette
  réelle), dont environ deux jours d'arrêt (crédits d'usage épuisés, coupures réseau).

### Ce que les relectures et la recette ont trouvé

Chaque tâche a été relue et sa preuve rejouée par l'orchestrateur. Les quatre premiers défauts ci-dessous
ont été trouvés en écrivant la documentation d'installation, les deux suivants par la recette en mode
serveur, qui suit les parcours comme un utilisateur :

- un **zip incomplet** : la page d'entrée n'était pas dans le zip de release, si bien qu'une installation
  d'atelier aurait répondu par une erreur ; le test du zip exige maintenant ses fichiers ;
- une **impasse au premier compte** : avec les comptes exigés à la main et aucun responsable, personne ne
  pouvait plus entrer, assistant compris. L'assistant reste joignable depuis le PC serveur tant qu'on sait
  qu'aucun responsable n'existe ; un fichier des comptes abîmé garde tout fermé, sinon le premier compte
  créé aurait écrasé les autres ;
- un **dossier conseillé refusé** : le zip dézippé dans `C:\Prevo` donne un sous-dossier, que l'assistant
  proposait de déplacer, puis refusait de déplacer ;
- la **clé privée du certificat** partait dans les sauvegardes et leur copie externe (clé USB, NAS) ; elle
  n'y va plus et se refabrique au démarrage si elle manque ;
- une **limite de connexions mal placée** : le plafond de 32 requêtes à la fois (audit F2) était tenu par
  les connexions inactives que les navigateurs gardent ouvertes, si bien que cinq navigateurs ouverts
  bloquaient le sixième ; une place n'est prise qu'à l'arrivée d'une requête ;
- des **adresses qui ne répondaient pas** : en portée « ce PC », l'accueil proposait un QR à un téléphone
  qui ne pouvait pas joindre le PC ; il renvoie maintenant aux paramètres.

Plus tôt, un piège de Windows : écouter sur 127.0.0.1 réussissait sur un port déjà tenu par un autre
programme ; Prévo sonde maintenant le port avant d'écouter.

### Les preuves propres au lot 7

- **Aucune vraie commande d'administrateur dans les tests** : faux mkcert avec une autorité de test, faux
  Tailscale (le vrai n'est jamais lancé), scripts de démarrage vérifiés par l'analyseur de PowerShell sans
  être exécutés. L'élévation réelle, les vrais téléphones et Tailscale en 4G sont à la recette réelle.
- **Table des droits, route par route** : trois sessions (demandeur, technicien, responsable) et un appareil
  enrôlé ; chaque case interdite rend 403, chaque case permise 200. La liste des routes vient du code : une
  route oubliée dans la table fait échouer le test.
- **Mandataire de test** (`tests/mandataire_test.py`) : un mandataire inverse minimal qui joue
  `tailscale serve` ou celui de l'entreprise ; les en-têtes `X-Forwarded-*` forgés par un client direct
  restent sans effet.
- **Calcul indépendant** du hachage des mots de passe (scrypt) et horloge simulée pour le blocage de
  15 minutes après dix échecs.
- **Recette** (`tests/test_recette_lot7.py`) en mode serveur : quatre parcours de bout en bout (Solo,
  Atelier, Intranet, Tailscale), vérifiés à l'écran, sur le disque et dans la console, dont une étiquette
  QR relue par le décodeur de la caméra.

### La clôture

La suite complète (1 762 tests, dont 4 sautés) a été jouée d'un trait en 39 minutes
(`.chantier/suite-complete-2026-10-29-ok.log`), puis sa deuxième moitié (`test_[i-z]`) rejouée par la
vérification de la dernière vague. Sont sautés, en le disant, les essais qui demandent le vrai Excel
(`PREVO_TEST_EXCEL=1`) ou un vrai modèle d'IA (`PREVO_TEST_IA=1`). Un piège de l'outil de vérification
est noté pour la suite : un motif est lu comme une expression régulière quand il en est une ;
« ## [2.0.0] » cherchait un seul caractère et ne prouvait rien, il a fallu échapper les crochets.

Ce que seuls de vrais appareils prouvent passe par la **recette réelle de Nicolas**, en onze points :
installation Solo et Atelier depuis le zip, une seule invite d'administrateur, Android et iPhone non
configurés devant une étiquette, navigateur réglé « toujours https », connexion au téléphone, appareil enrôlé
puis révoqué, redémarrage sans ouvrir de session, Tailscale en 4G, mot de passe oublié, mode Solo de bout en
bout. Les étiquettes `lot-7` et **`v2.0.0`** sont posées une fois ces onze points à oui ; un « non » ouvre
d'abord une vague de correction.

### La publication

La branche principale a été envoyée sur le dépôt privé le 28 octobre, avec l'accord de Nicolas, jusqu'à
l'arbitrage sur l'assistant IA. Le zip de la release, Python et mkcert compris, se joint à la release GitHub
(`docs/RELEASE.md`).

*Mise à jour du 07/11/2026 (constat B10 du Lot 0).* Le dépôt `nicoboy49/prevo` est **public**. La version publiée le
28 octobre sous le numéro 2.0.0 a été renommée **2.0.0 bêta 1** le 4 novembre (pré-version), avant que la recette
réelle soit faite ; la version stable est restée la 1.2.x (1.2.1, correctif publié le 4 novembre), et la **2.0.0
bêta 2** a été publiée le 5 novembre. La 2.0.0 finale (français et anglais) suit le chantier multilingue, puis la
2.1.0 (turc, italien, portugais).

## 14. À retenir pour piloter une IA

1. Faire écrire et valider le cahier des charges et ses critères de succès avant le code.
2. Écrire le contrat entre les morceaux avant de distribuer le travail.
3. Accepter une tâche sur preuve relancée par soi-même, jamais sur déclaration.
4. Faire relire par quelqu'un qui n'a pas écrit le code.
5. Reproduire chaque défaut par un test avant de le corriger.
6. Réserver à l'humain les décisions, et lui demander les vérifications physiques.
7. Mesurer un modèle d'IA sur ses propres données plutôt que de le choisir sur réputation, et ne
   jamais laisser un vrai modèle dans la suite de tests : un faux fournisseur rend les tests
   rapides, reproductibles, et capables de simuler les pannes.
8. Avant une fabrication payante, faire relire un premier échantillon par un relecteur indépendant
   avec la grille du client ; pendant la fabrication, poser des garde-fous (budget, part de refus,
   relance avec la raison) et garder les réponses pour qu'une relance ne coûte rien.
9. Laisser l'humain fixer les seuils qui engagent l'argent et le ton (nombre de phrases, budget,
   taux d'arrêt), et noter au journal chaque décision prise sans lui.
10. Avant la clôture, faire suivre les parcours de bout en bout par un agent qui joue l'utilisateur,
    sur le vrai serveur, et faire écrire la documentation d'installation en suivant ses propres
    consignes : les défauts d'assemblage (un zip incomplet, une limite tenue par des connexions
    inactives, une impasse au premier compte) ne se voient pas tâche par tâche.
11. Présenter à l'humain les décisions prises sans lui avec le contexte minimum pour trancher (ce qui
    existe, ce qui a été choisi, ce que l'autre choix changerait), sur une page à cocher : une
    question nue, une fois le contexte oublié, ne permet pas de répondre.
