# Journal des modifications

Toutes les modifications notables de Prévo sont consignées dans ce fichier.

Le format s'appuie sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et le projet
suit le [versionnage sémantique](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté

- **Aide à l'écran** : à la première ouverture de chaque écran, un encart en haut de la page dit ce qu'il contient,
  ce qu'on y fait et propose un geste à essayer, avec un lien vers la partie du guide ; il ne bloque rien,
  « Compris » le ferme pour de bon sur ce poste. Les textes suivent le profil (accueil, demandes, ordres de travail,
  page du wiki) ; dans la démo en ligne, l'accueil rappelle qu'on peut tout essayer. Lien « Explications » dans le
  menu ; dans Ce poste, la case pour la couper et « Revoir toutes les explications ».

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
