# Journal des modifications

Toutes les modifications notables de Prévo sont consignées dans ce fichier.

Le format s'appuie sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et le projet
suit le [versionnage sémantique](https://semver.org/lang/fr/).

## [Non publié]

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

[Non publié]: https://github.com/nicoboy49/prevo/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/nicoboy49/prevo/releases/tag/v1.0.0
