# Journal des modifications

Toutes les modifications notables de Prévo sont consignées dans ce fichier.

Le format s'appuie sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et le projet
suit le [versionnage sémantique](https://semver.org/lang/fr/).

## [Non publié]

## [2.0.0-beta.2] - 2026-11-05

Deuxième bêta de la 2.0 (pré-version : pour essayer, pas pour la production ; la version stable reste la 1.2.1).
Elle se met par-dessus la bêta 1 : vos données sont migrées automatiquement, après une sauvegarde « avant mise à jour ».

### Corrigé

- **Plus de perte de données sur un fichier abîmé** : si un fichier de données est abîmé hors de Prévo (une note tapée
  dans Excel, un guillemet oublié), Prévo ne le réécrit plus jamais, ne perd plus ce qu'il n'avait pas su lire, affiche
  un bandeau « Fichier abîmé » et garde votre saisie dans le formulaire. Seules la restauration d'une sauvegarde et
  l'import ZIP peuvent le remplacer.
- **Un fichier abîmé ne bloque plus la sauvegarde quotidienne** : elle est faite, marquée « abîmé » au manifeste, et
  les 7 dernières sauvegardes saines sont toujours gardées.

### Ajouté

- **Un format de données versionné** : chaque base porte son format, décrit dans [docs/FORMAT.md](docs/FORMAT.md).
- **Migration automatique** : au démarrage, une base d'un format plus ancien est mise à niveau étape par étape, après
  une sauvegarde « avant mise à jour ».
- **Lecture seule d'une base plus récente** : si les données viennent d'une version de Prévo plus récente que la
  vôtre, Prévo les lit sans rien modifier.
- **Sauvegardes** : une avant chaque mise à jour, une par jour, gardées 30 jours ; celles d'avant mise à jour ne sont
  jamais effacées.
- **Export ZIP complet** (Paramètres › Sauvegardes) : tous les fichiers de données, les documents, les rapports figés
  et un manifeste. Le dossier des accès n'y est jamais ; avec les comptes, le responsable seul peut l'exporter.
- **Export « données seules »** (sans les documents) : plus léger, importable comme l'export complet ; l'import ne
  supprime alors aucun document existant. Avant un export complet de plus de 150 Mo, qui demande beaucoup de mémoire,
  Prévo prévient et propose les données seules.
- **Import ZIP** : contrôle du fichier, confirmation détaillée, sauvegarde avant remplacement, retour arrière
  automatique en cas d'échec.
- **Tout ce que Prévo exporte, Prévo peut le réimporter** : un ZIP produit par l'export est toujours accepté à
  l'import, y compris pour une grosse base ; l'export prévient avant de produire un ZIP que l'import refuserait. Limites
  d'un ZIP : 400 Mo et 10 000 entrées ; 50 Mo par table ; 10 Mo par document.
- **Base avec un fichier abîmé** : l'export la marque « abîmé » au manifeste et garde le fichier tel quel ; l'import le
  retrouve dans le même état, avec le bandeau « Fichier abîmé ».
- **Signalement des versions** : une bêta est prévenue de la 2.0.0 finale (comparaison correcte des numéros de version).

### Modifié

- **Hébergement derrière nginx ou IIS** : Prévo accepte l'enregistrement d'une table jusqu'à 50 Mo. Si Prévo est
  derrière un de ces serveurs, relevez sa limite d'envoi (nginx : `client_max_body_size 52m;` ; IIS :
  `maxAllowedContentLength="54525952"`), sinon les grosses tables seront refusées. Détail dans
  [docs/INSTALLATION.md](docs/INSTALLATION.md).

## [2.0.0-beta.1] - 2026-10-28

Publiée d'abord sous le numéro 2.0.0, renommée « bêta 1 » le 2026-11-04.

Le lot 7 : l'accès et l'installation (le détail est dans [docs/PILOTAGE.md](docs/PILOTAGE.md), l'installation pour
l'informaticien dans [docs/INSTALLATION.md](docs/INSTALLATION.md)). Version majeure : au-delà de ce PC, la connexion
devient obligatoire.

### Ajouté

- **Connexion et rôles** : au-delà de ce PC, chaque personne a son compte et le serveur vérifie les droits de chaque
  rôle ; un demandeur peut n'avoir qu'un téléphone enrôlé par QR, sans mot de passe.
- **Assistant d'installation** : trois questions au premier lancement (qui, depuis où, votre compte), le https de
  l'atelier, Tailscale hors de l'atelier, le démarrage avec le PC et la copie des sauvegardes ; Python est dans le zip.
- **Trois portées** : ce PC (comme avant, sans mot de passe), le Wi-Fi de l'atelier, aussi hors de l'atelier. Prévo
  refuse d'écouter le réseau sans comptes ni https.
- **https sans rien acheter** : une page d'entrée guide chaque téléphone pas à pas pour « faire confiance au PC
  atelier » (Android, iPhone), puis ouvre la fiche demandée en https ; le certificat de l'atelier est fabriqué par
  mkcert, livré dans le zip avec son empreinte vérifiée. Les étiquettes QR gardent l'adresse de la page d'entrée.
- **Équipe › Accès** (responsable) : comptes (rôle, technicien lié, mot de passe provisoire montré une fois,
  réinitialiser, désactiver), invitations QR pour les téléphones des demandeurs, révocation immédiate, journal des
  connexions consultable et exportable.
- **Écran de connexion** : « rester connecté sur cet appareil », changement obligatoire d'un mot de passe provisoire,
  déconnexion ; mot de passe oublié : `Reinitialiser_mot_de_passe.bat` sur le PC serveur.
- **Hors de l'atelier** : Tailscale détecté et guidé (jamais installé à votre place), signalé sur l'accueil du
  responsable s'il est déconnecté ou si sa clé expire ; ou derrière le mandataire inverse de l'entreprise (nginx,
  Caddy, IIS, Cloudflare Tunnel).
- **Démarrer avec le PC** : tâche planifiée au démarrage, règle du pare-feu en réseau privé et veille désactivée sur
  secteur, en une seule invite d'administrateur ; retrait depuis Paramètres.
- **Mode Solo** : pour une personne seule, menu allégé, technicien « moi », « Nouvel OT » en premier et clôture en une
  étape.
- **Sauvegardes** : copie externe chaque nuit (clé USB, NAS, dossier synchronisé ; 30 gardées), « Tester » une
  sauvegarde, une sauvegarde manuelle par minute au plus (60 gardées).
- **Paramètres › Accès et installation** : chaque réglage de l'assistant se refait depuis le PC serveur, avec l'état du
  serveur (actif depuis, adresses, Tailscale, copie externe, dernières lignes du journal).
- **Aide à l'écran** : à la première ouverture de chaque écran, un encart en haut de la page dit ce qu'il contient,
  ce qu'on y fait et propose un geste à essayer, avec un lien vers la partie du guide ; il ne bloque rien,
  « Compris » le ferme pour de bon sur ce poste. Les textes suivent le profil (accueil, demandes, ordres de travail,
  page du wiki) ; dans la démo en ligne, l'accueil rappelle qu'on peut tout essayer. Lien « Explications » dans le
  menu ; dans Ce poste, la case pour la couper et « Revoir toutes les explications ».
- **docs/INSTALLATION.md** : la configuration (`prevo.config.json`), les mandataires, les services, les comptes, le
  journal et les sauvegardes, pour l'informaticien.

### Modifié

- Le zip embarque Python 3.14 (paquet officiel Windows 64 bits) : rien à installer ; ailleurs, un Python 3.11 ou plus
  récent suffit.
- Sans configuration, le serveur n'écoute que sur ce PC (127.0.0.1) ; la console et l'accueil disent quand un
  téléphone ne peut pas joindre Prévo.
- Le guide : chapitre 2 réécrit autour de l'assistant, chapitre 3 « Les rôles et les profils », nouveau chapitre 8
  « Accès et installation » (connexion, faire confiance au PC atelier, Tailscale, démarrage, Solo, RGPD, annuaire).
- En mode serveur, le fournisseur d'IA et sa clé se règlent sur le PC serveur, jamais dans les navigateurs ; avec les
  comptes, l'assistant IA est réservé aux techniciens et au responsable.
- Documents joints : le serveur ajoute la date et l'heure devant leur nom ; `.doc` et `.xls` sont refusés ; les
  fichiers autres que les images, les PDF et les rapports figés s'ouvrent en téléchargement.

### Sécurité

- Corrections de l'audit de la version 1.1 : contrôle des fichiers CSV reçus (E2), clé de l'IA gardée sur le PC
  serveur (M1 à M3), en-têtes de sécurité (F1), limites de ressources : 32 requêtes à la fois et quota du dossier des
  documents (F2), documents (F4), chemins notés tels quels dans le journal du serveur (I2), rubrique RGPD du guide (I4).
- Mots de passe hachés (scrypt), sessions dans un cookie HttpOnly, attente puis blocage après des échecs de
  connexion, journal des connexions gardé un an ; la clé privée du certificat de l'atelier ne part jamais dans une
  sauvegarde.

### Migration

- Une installation 1.2 garde ses fichiers CSV : l'assistant les montre et n'y touche pas. Les profils mémorisés ne
  servent plus quand les comptes sont exigés. Les étiquettes QR imprimées en 1.2 restent valables (même adresse,
  même port : la page d'entrée). Lancé sans configuration, le serveur reste en portée « ce PC », comme avant.

## [1.2.0] - 2026-10-24

Le lot 6 : le wiki de maintenance, l'encyclopédie de l'atelier (le détail est dans
[docs/PILOTAGE.md](docs/PILOTAGE.md)). Le logiciel prend le nom **Prévo**.

### Ajouté

- **Wiki de maintenance** (menu « Wiki ») : une page par machine, par panne, par article, par technicien, par
  intervention et par savoir-faire, calculée à partir des données de l'atelier (pannes et ce qui les a réglées,
  interventions, pièces consommées, stock, consignation en tête de page, petits numéros vers les ordres de travail
  cités) et complétée par des textes courts (« En bref » et « Astuces » d'une machine, « À quoi il sert » d'un
  article, savoir-faire communs aux machines) ; recherche sans IA sur les noms, les interventions et les textes ;
  accueil « Ce que l'atelier sait » ; ce que voit chaque profil est borné (le demandeur ne voit ni les techniciens
  ni les interventions, les prix restent au responsable).
- **Astuce pour la prochaine fois** : une phrase courte saisie à la clôture technique d'un ordre de travail,
  cherchée avec les pages du wiki.
- **Ingestion par l'assistant IA** : à la clôture administrative, l'ordre de travail entre dans la file du wiki ;
  le responsable la traite depuis le journal du wiki (« Traiter la file ») sur un poste où l'IA est réglée ; le
  modèle propose, Prévo contrôle (rien d'inventé, chaque phrase cite un ordre de travail, aucune consigne de
  sécurité, longueurs, un seul savoir-faire par geste, relance avec la raison du refus), le responsable valide,
  rejette ou relance ; les contradictions se tranchent ; l'écriture à la main et le contrôle du wiki restent
  possibles. Coût mesuré sur la démo avec Claude Sonnet : 0,026 $ par ordre de travail.
- **Signalement des nouvelles versions** (responsable, Paramètres > « Me signaler les nouvelles versions de
  Prévo », désactivé par défaut) : Prévo lit `https://prevo.pro/version.json` au plus une fois par jour et par
  poste et, quand une version plus récente existe, le dit sur l'accueil du responsable et dans « À propos », avec
  le lien de téléchargement et les nouveautés. Rien ne s'installe tout seul.
- Démo : son wiki a été rédigé par Claude Sonnet avec la consigne de Prévo (227 interventions, 42 pages), relu
  par un relecteur indépendant ; chapitre « Le wiki de maintenance » du guide ; outil de release qui écrit
  `version.json`.

### Modifié

- Le logiciel s'appelle désormais **Prévo** (l'ancien nom était déjà celui d'une autre GMAO). Le nom
  change partout : écrans, guide, documents, en-tête `X-Prevo`, variables `PREVO_*`, fichiers produits
  (`prevo-export-…`, `prevo-v…`). Sur chaque poste, le profil, le thème, les réglages de l'assistant
  et le dossier de données sont à choisir de nouveau une fois.
- Format des données en **version 3** : deux tables de plus (`wiki_pages.csv`, `wiki_journal.csv`, 24 fichiers)
  et la colonne `astuce` des ordres de travail, ajoutées au premier enregistrement après une sauvegarde
  « avant-format-v3 » ; les fichiers des versions 1 et 2 restent lus.
- La carte « Résumer l'historique » de la fiche d'un équipement (assistant IA du lot 4) est remplacée par le
  lien vers la page du wiki de la machine.

## [1.1.0] - 2026-10-22

Le lot 5 : reprendre ses données existantes (le détail est dans [docs/PILOTAGE.md](docs/PILOTAGE.md)).

### Ajouté

- Assistant « Importer des données » (responsable, depuis Paramètres ou l'accueil d'une base vide) : fichiers
  Excel (.xlsx, .xls), OpenDocument (.ods), CSV et collage ; colonnes reconnues par leur titre (proposition
  de l'IA possible, titres seulement) et retenues sur le poste ; aperçu de chaque ligne avant d'écrire (à
  créer, à mettre à jour, identique, refusée, doublon) ; sauvegarde « Avant import » puis « Annuler cet
  import » ; lignes refusées téléchargeables ; modèles à remplir.
- Reprise de l'historique des interventions d'une autre GMAO : ordres de travail clôturés, ancien numéro
  gardé dans le compte rendu, doublons sûrs et supposés montrés, durée d'arrêt jamais inventée.
- Accueil du responsable repensé (synthèse, « À traiter en premier », compteurs, tuiles à surveiller),
  menu latéral allégé, barre du bas en verre dépoli sur téléphone, notifications en bulle.
- Démo en ligne (outil de construction et guide de déploiement) et zip de release allégé ; licence MIT
  seule dans LICENSE et NOTICE pour les bibliothèques tierces ; guide de contribution, formulaires
  d'issues.

### Modifié

- Disponibilité : une panne sans durée d'arrêt n'est plus comptée 0 h ; elle est exclue du MTTR et de la
  disponibilité (et listée), pour tous les ordres de travail.
- Une ligne importée que le formulaire de l'écran refuserait est refusée de la même façon.

### Corrigé

- Ouverture plus rapide d'une grande base : la génération du préventif ne relit plus toute la table à
  chaque ordre de travail créé.

## [1.0.0] - 2026-10-21

Première version, qui réunit les lots 1 à 4 du cahier des charges (le détail, lot par lot, est dans
[docs/PILOTAGE.md](docs/PILOTAGE.md)).

### Ajouté

- Lot 1, le socle : trois modes de stockage (dossier, serveur Python local, démo en mémoire) avec
  écritures concurrentes gérées entre postes, profils Demandeur, Technicien et Responsable, parc
  d'équipements, demandes d'intervention et ordres de travail au cycle de vie complet.
- Lot 2 : maintenance préventive, magasin de pièces, sortie de pièces depuis l'ordre de travail,
  encart des causes fréquentes, format de fichiers v2 (sauvegarde « Avant format 2 » au passage).
- Lot 3 : indicateurs et graphiques, planning de la semaine, étiquettes QR par lot, contrôles
  réglementaires, équipe et habilitations, rapport mensuel figé.
- Lot 3 bis : préventif suggéré (créer une gamme, revoir le préventif, revoir ou allonger une
  gamme) ; Prévo ne modifie jamais une gamme tout seul.
- Lot 4 : assistant IA facultatif qui propose sans décider (Ollama dans l'atelier, ou service en
  ligne autorisé par le responsable), dictée vocale, écran « Ce poste » avec thème clair, https en
  option, guide d'utilisation imprimable, fiche technique des fichiers CSV.
- Données dans 22 fichiers CSV lisibles dans Excel ; 907 tests automatisés.

[Non publié]: https://github.com/nicoboy49/prevo/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/nicoboy49/prevo/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/nicoboy49/prevo/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/nicoboy49/prevo/releases/tag/v1.0.0
