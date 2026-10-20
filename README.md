# Prévo

Prévo est une GMAO (gestion de maintenance assistée par ordinateur) pour un atelier ou une petite
industrie : parc d'équipements, demandes d'intervention, ordres de travail, maintenance préventive
et magasin de pièces. Elle tourne sans installation lourde ni abonnement : les données sont des
fichiers CSV lisibles dans Excel, stockés dans un dossier de votre choix. Le code est écrit en
français, avec des bibliothèques embarquées et aucun appel vers Internet.

Cette version contient les **lots 1 et 2** ; les lots suivants sont listés plus bas. Une
présentation avec capture d'écran viendra au lot 4.

## Essayer en 30 secondes

1. Ouvrez `index.html` dans Chrome ou Edge (double-clic ou glisser-déposer dans le navigateur).
2. Cliquez sur **Essayer avec les données de démo**, puis choisissez un profil.

Le jeu de démo est entièrement fictif et vit en mémoire : rien n'est enregistré, et un bouton
permet de l'exporter en ZIP.

## Installation

### Mode dossier (un seul poste, sans Python)

Ouvrez `index.html` dans **Chrome ou Edge**, cliquez sur « Choisir le dossier de données » et
désignez un dossier de votre PC. Ce mode est fait pour **un seul poste à la fois** (un
avertissement s'affiche si une autre session semble ouverte) ; pour plusieurs postes ou des
téléphones, utilisez le mode serveur. Prévo lit et écrit les fichiers CSV dans ce dossier. Au lancement suivant, « Reprendre le dossier précédent »
évite de le choisir à nouveau. Ce mode utilise l'API d'accès aux fichiers de Chrome et d'Edge ;
Firefox et Safari ne la proposent pas.

### Mode serveur (plusieurs postes et téléphones)

Il faut Python 3.8 ou plus récent ; le serveur n'utilise que la bibliothèque standard.

- Windows : double-cliquez sur `Lancer_GMAO.bat`. Si Python est absent, le lanceur propose de
  l'installer avec winget (avec votre accord).
- Mac ou Linux : `./lancer.sh`.
- Directement : `py serveur.py` (Windows) ou `python3 serveur.py`. Options : `--port`,
  `--donnees CHEMIN`, `--sans-navigateur`.

Au premier lancement sous Windows, le pare-feu demande d'autoriser Python : **cochez uniquement
« Réseau privé »**, jamais « Réseau public ».

Pour connecter un téléphone, il doit être sur le **même Wi-Fi** que le PC. L'écran d'accueil
affiche un QR code de l'adresse du PC : scannez-le avec l'appareil photo du téléphone.

Les données du mode serveur sont dans le dossier `donnees/` (hors dépôt git), avec les sauvegardes
quotidiennes (`donnees/sauvegardes/`) et les documents joints.

## Ce que contient le lot 1

- Trois modes de stockage : dossier, serveur Python local, démo en mémoire.
- Écritures concurrentes gérées : en cas de conflit, la modification est rejouée sur la version la
  plus récente du fichier (trois essais).
- Profils Demandeur, Technicien et Responsable (menus et écrans adaptés).
- Parc : arborescence site, atelier, ligne ; fiche équipement avec historique et QR code.
- Demandes d'intervention : saisie en cinq champs, priorité calculée, décisions du responsable.
- Ordres de travail : cycle de vie complet, règles de clôture, coûts, habilitation vérifiée à
  l'affectation, bon de travail imprimable (règles RG1 à RG4, RG7, RG8).
- Accueil par profil, Paramètres (sauvegardes, restauration, contrôle de la base, export ZIP),
  À propos.

## Ce que contient le lot 2

- **Préventif** : gammes de maintenance déclenchées par une date, un compteur (heures,
  kilomètres…) ou un seuil de mesure ; état de chaque gamme (échue, bientôt, à jour…) ; éditeur de
  check-list ; calendrier des 12 prochaines semaines. À l'ouverture par un technicien ou un
  responsable, Prévo crée l'ordre de travail de chaque gamme échue (un seul par gamme, même si
  deux postes s'ouvrent en même temps) avec sa check-list ; la clôture de l'OT met la gamme à jour.
  Les relevés de compteur se saisissent depuis la fiche équipement.
- **Magasin** : articles, mouvements (entrée, sortie, retour, inventaire), stock recalculé depuis
  les mouvements, point de commande saisi avec une valeur suggérée, liste « À commander », demandes
  d'achat suivies de « demandée » à « reçue » (la réception fait entrer le stock), fournisseurs.
  Une sortie qui rendrait le stock négatif est refusée.
- **Pièces sorties depuis l'OT** : sortie et retour de pièces dans l'onglet Exécution ; le coût de
  l'OT compte les pièces réellement sorties.
- **Causes fréquentes** : sur les fiches DI et OT, un encart montre les causes les plus fréquentes
  d'un même symptôme sur cet équipement (ou sur ceux de même marque et modèle), dès 5 cas. C'est
  une statistique de l'historique, pas un diagnostic.
- **Anomalie pendant un préventif** : depuis l'OT préventif, un clic ouvre une DI liée, et l'OT est
  marqué « anomalie constatée ».
- **Accueil** : compteurs « préventifs de la semaine » et « articles à commander ».
- **Format des fichiers v2** : quatre colonnes ajoutées en fin de table (valeur de remplacement
  d'un équipement, code symptôme et OT d'origine d'une DI, anomalie constatée d'un OT). Une base du
  lot 1 se relit sans erreur. À sa première ouverture, Prévo fait **d'abord une sauvegarde
  complète** (« Avant format 2 », restaurable depuis Paramètres), puis seulement passe la base au
  format 2 ; si la sauvegarde échoue, rien n'est changé, les OT préventifs ne sont pas générés
  automatiquement, et le tout est retenté à l'ouverture suivante.
- Un jeu de démo fictif de treize mois d'historique.

## Ce qui vient ensuite

- **Lot 3** : indicateurs, planning, étiquettes QR, contrôles réglementaires, habilitations,
  rapport mensuel.
- **Lot 3 bis** : préventif suggéré, à partir des anomalies constatées pendant les préventifs.
- **Lot 4** : assistant IA, dictée vocale, `GUIDE.html`, `FICHE_TECHNIQUE_CSV.md`, présentation
  du projet avec capture d'écran.
- **Lot « Import »** : assistant d'import de fichiers existants (dont `.xls`).

Ces éléments ne sont pas encore réalisés. Les compteurs d'accueil correspondants (contrôles
réglementaires, habilitations) arriveront avec le lot 3.

## Format des données

Les données sont 22 fichiers CSV (format v2 depuis le lot 2) : séparateur `;`, UTF-8 avec BOM,
fins de ligne CRLF. Ils s'ouvrent et se modifient dans Excel. Comme Excel abîme certaines valeurs
(zéros de tête, formules, fractions prises pour des dates), Prévo les protège par une apostrophe
en tête de cellule et la retire à la lecture. À la lecture, il accepte aussi les dates écrites
`JJ/MM/AAAA` par Excel. Les détails sont dans `docs/ARCHITECTURE.md` (§3 ; format v2 : §4 et
§14.1), en attendant `FICHE_TECHNIQUE_CSV.md`.

Ne modifiez pas un fichier dans Excel pendant que quelqu'un enregistre dans Prévo : le serveur
signale un fichier verrouillé, et le mode dossier détecte le conflit.

## Lancer les tests

```
py -m unittest discover -s tests -v
```

Les tests de navigateur demandent Playwright et Chromium (`pip install playwright`, puis
`playwright install chromium`) ; ils ne servent qu'aux tests, pas à l'utilisation de Prévo. Pour
exécuter aussi l'aller-retour par le vrai Excel (Excel doit être installé sur le poste), définissez
`PREVO_TEST_EXCEL=1` ; sans cette variable, ce test est sauté. La suite complète prend plusieurs
minutes.

## Limites connues

- **Pas d'authentification.** Les profils adaptent l'interface ; ils ne sont pas une mesure de
  sécurité. Toute personne qui atteint le serveur peut lire et écrire les données.
- **Réseau local uniquement.** Le serveur n'est pas conçu pour être exposé sur Internet ; il n'a
  ni HTTPS ni gestion de comptes.
- **Le serveur ne sert que l'application.** Il répond seulement pour `index.html`, `favicon.svg`,
  `GUIDE.html` (quand il existera) et les dossiers `css/` et `js/` (liste blanche). Tout autre
  fichier du dossier (`README.md`, `docs/`, `tests/`, `outils/`, `serveur.py`…) répond « introuvable »
  (404), et le dossier `donnees/` n'est accessible que par l'API de l'application. Ce n'est pas une
  protection des données : sans authentification, l'API reste ouverte à qui atteint le serveur.
- **Chrome ou Edge requis pour le mode dossier** (API d'accès aux fichiers).
- **Coût des pièces au prix actuel.** Le coût d'un OT utilise le prix actuel de l'article ; une
  réception d'achat ne change pas ce prix (le responsable le modifie à la main), mais un changement
  de prix modifie aussi le coût des OT passés.
- Sur téléphone en mode serveur, la page est servie en HTTP : le scan par caméra intégrée à la
  page n'est pas proposé ; la photo passe par l'appareil photo du téléphone.

## Comment ce projet a été fait

Le cahier des charges a été rédigé par Nicolas Briand avec Claude ; le code a ensuite été produit
par des sous-agents Claude Code, sous la coordination d'un orchestrateur qui n'accepte une tâche
que si sa vérification passe, avec relecture indépendante à chaque étape. La méthode et les
preuves, lot 1 puis lot 2, sont détaillées dans [docs/PILOTAGE.md](docs/PILOTAGE.md).

## Licence et crédits

Code sous licence MIT (voir `LICENSE`), Copyright (c) 2026 Nicolas Briand — SELECTIS.

Prévo embarque, sans modification, PapaParse, qrcode-generator, jsQR, JSZip (et pako) et Apache
ECharts, ainsi que la police Sora (SIL Open Font License 1.1). Leurs licences sont reproduites dans
`js/lib/LICENCES.txt`.
