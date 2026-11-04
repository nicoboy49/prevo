# Prévo

**La GMAO libre et gratuite des PME industrielles.**

> **Version 1.2.1 — en test sur le terrain.** Prévo est utilisé dans de premières
> entreprises pilotes. Sauvegardez régulièrement votre dossier de données, et
> signalez tout problème dans l'onglet *Issues*.

## Pour qui, pourquoi

Dans beaucoup de PME, la maintenance tient sur un cahier, un tableur ou la mémoire
du technicien. Les GMAO du marché sont chères, longues à déployer et pensées pour
de grandes équipes. Prévo s'adresse aux entreprises de moins de 50 personnes dont
la maintenance repose sur 1 à 3 techniciens : il est gratuit, tourne sur un PC de
l'atelier, se consulte au téléphone, et garde les données dans des fichiers CSV qui
restent à l'entreprise. Il a été conçu par un technicien de maintenance devenu
formateur, à partir de vingt ans de terrain.

Prévo est une GMAO (gestion de maintenance assistée par ordinateur) pour un atelier ou une petite
industrie : parc d'équipements, demandes d'intervention, ordres de travail, maintenance préventive et
préventif suggéré, magasin de pièces, planning, contrôles réglementaires, indicateurs et rapport mensuel.
Elle tourne sans installation lourde ni abonnement : les données sont des fichiers CSV lisibles dans
Excel, stockés dans un dossier de votre choix. Le code est écrit en français, avec des bibliothèques
embarquées et aucun appel vers Internet (sauf l'assistant IA en ligne, s'il est autorisé et choisi).

![Accueil du responsable sur le jeu de démo : compteurs, demandes à traiter et ordres de travail en retard](docs/captures/accueil.png)

- **Guide d'utilisation** : [GUIDE.html](GUIDE.html), à ouvrir dans le navigateur (imprimable).
- **Format des fichiers** : [FICHE_TECHNIQUE_CSV.md](FICHE_TECHNIQUE_CSV.md).

Cette version, la **1.2.1**, contient les **lots 1 à 6** du cahier des charges, dont le wiki de maintenance et la reprise des données
existantes (lot 5) ; les nouveautés de chaque version sont dans [CHANGELOG.md](CHANGELOG.md).

## Essayer en 30 secondes

1. Ouvrez `index.html` dans Chrome ou Edge (double-clic ou glisser-déposer dans le navigateur).
2. Cliquez sur **Essayer avec les données de démo**, puis choisissez un profil (**Responsable** voit
   tout).

Le jeu de démo est un atelier entièrement fictif, avec treize mois d'historique dont les dates sont
recalées sur aujourd'hui. Il vit en mémoire : rien n'est enregistré, et un bouton permet de l'exporter
en ZIP.

## Installation

### Mode dossier (un seul poste, sans Python)

Ouvrez `index.html` dans **Chrome ou Edge**, cliquez sur « Choisir le dossier de données » et
désignez un dossier de votre PC. Ce mode est fait pour **un seul poste à la fois** (un
avertissement s'affiche si une autre session semble ouverte) ; pour plusieurs postes ou des
téléphones, utilisez le mode serveur. Prévo lit et écrit les fichiers CSV dans ce dossier. Au
lancement suivant, « Reprendre le dossier précédent » évite de le choisir à nouveau. Ce mode utilise
l'API d'accès aux fichiers de Chrome et d'Edge ; Firefox et Safari ne la proposent pas.

### Mode serveur (plusieurs postes et téléphones)

Il faut Python 3.8 ou plus récent ; le serveur n'utilise que la bibliothèque standard.

- Windows : double-cliquez sur `Lancer_GMAO.bat`. Si Python est absent, le lanceur propose de
  l'installer avec winget (avec votre accord).
- Mac ou Linux : `./lancer.sh`.
- Directement : `py serveur.py` (Windows) ou `python3 serveur.py`. Options : `--port`,
  `--donnees CHEMIN`, `--sans-navigateur`, `--hote NOM`, et `--certificat FICHIER --cle FICHIER`
  pour le https (voir plus bas). Les lanceurs transmettent ces options.

Au premier lancement sous Windows, le pare-feu demande d'autoriser Python : **cochez uniquement
« Réseau privé »**, jamais « Réseau public ».

Pour connecter un téléphone, il doit être sur le **même Wi-Fi** que le PC. L'écran d'accueil
affiche un QR code de l'adresse du PC : scannez-le avec l'appareil photo du téléphone.

Les données du mode serveur sont dans le dossier `donnees/` (hors dépôt git), avec les sauvegardes
quotidiennes (`donnees/sauvegardes/`) et les documents joints.

## Fonctions par module

- **Trois modes de stockage** : dossier, serveur Python local, démo en mémoire. Écritures concurrentes
  gérées : en cas de conflit, la modification est rejouée sur la version la plus récente du fichier
  (trois essais). Les tables modifiées sur un autre poste sont relues toutes seules.
- **Profils** Demandeur, Technicien et Responsable : menus et écrans adaptés (ce n'est pas une sécurité).
- **Accueil** par profil : compteurs du responsable (DI à traiter, OT en retard, P1 ouverts, préventifs
  de la semaine, articles à commander, contrôles sous 30 jours, habilitations à renouveler, suggestions
  de préventif), OT du technicien, demandes du demandeur ; QR code de connexion en mode serveur.
- **Demandes d'intervention** : saisie en cinq questions (sur téléphone aussi, photo comprise),
  priorité calculée à partir de la criticité et de l'impact (« sécurité » donne toujours P1),
  décisions du responsable (accepter, regrouper, différer, refuser avec un motif visible du demandeur).
  Un encart montre les causes fréquentes du même symptôme, avec la solidité de ses chiffres.
- **Ordres de travail** : cycle de vie complet (préparé, planifié, en cours, clôtures technique et
  administrative, attente et annulation avec motif), clôture technique contrôlée (codes cause et
  remède, compte rendu, remise en service), habilitation vérifiée à l'affectation, procédure de
  consignation affichée, pièces sorties depuis l'OT, coût calculé, bon de travail A4 imprimable,
  export CSV de la liste.
- **Planning de la semaine** : une ligne par technicien avec sa charge et sa capacité, OT à planifier
  glissés sur un jour ou placés par « Planifier… » (sans souris) ; liste par jour sur téléphone.
- **Préventif** : gammes déclenchées par une date, un compteur ou un seuil de mesure ; un seul OT par
  gamme échue, créé à l'ouverture avec sa check-list ; la clôture met la gamme à jour ; calendrier des
  12 prochaines semaines ; anomalie vue pendant un préventif → demande liée en un clic.
- **Préventif suggéré** : Prévo relit l'historique et propose de créer une gamme, de revoir le
  préventif, de revoir une gamme dont les visites trouvent souvent une anomalie, ou d'allonger une
  gamme sans constat (jamais en criticité A). Chaque suggestion montre sa règle et ses faits ; Prévo
  **ne modifie jamais une gamme tout seul**, et chaque décision est inscrite au journal.
- **Magasin** : articles, mouvements, stock recalculé depuis les mouvements, sortie refusée si le stock
  deviendrait négatif, point de commande suggéré, liste « À commander », demandes d'achat de
  « demandée » à « reçue », fournisseurs, inventaire.
- **Parc et étiquettes QR** : arborescence site, atelier, ligne ; fiche équipement (historique,
  compteurs, gammes, contrôles, pièces) ; étiquettes QR par lot sur planches A4 de 24 ou 8, repère
  écrit en clair.
- **Contrôles réglementaires** : échéancier par équipement, contrôle réalisé avec son rapport, levée
  des observations, OT réglementaire pré-rempli (sans veille réglementaire).
- **Équipe et habilitations** : techniciens, capacité, habilitations et leurs échéances, historique des
  renouvellements.
- **Indicateurs** (responsable) : disponibilité, MTBF, MTTR (dont attente de pièces), durée d'arrêt,
  part et respect du préventif, OT en retard, délais de prise en charge, coûts, valeur du stock ; chaque
  chiffre dit sur combien d'OT il porte, et un chiffre non calculable dit pourquoi. Graphiques avec
  leurs valeurs en tableau, exports CSV et image.
- **Rapport mensuel figé** : une page A4 par mois (chiffres comparés, faits marquants, points à
  examiner dont « réparer ou remplacer ? »), qui se rouvre sans Prévo ; « Préparer un courriel »
  ouvre la messagerie du poste, Prévo n'envoie rien lui-même.
- **Paramètres** : réglages partagés, codes de défaillance, sauvegardes et restauration, contrôle de la
  base, export ZIP.
- **Reprendre ses données** (responsable) : l'assistant « Importer des données » reprend, en cinq étapes,
  les listes d'un atelier (localisations, équipements, articles, fournisseurs, techniciens et
  habilitations, codes, compteurs, contrôles, gammes) et l'historique des interventions d'une autre GMAO, depuis Excel (.xlsx,
  .xls), OpenDocument (.ods), CSV ou un collage : colonnes reconnues par leur titre (l'IA peut en proposer,
  sur les seuls titres), aperçu ligne par ligne avant toute écriture, sauvegarde juste avant, « Annuler cet
  import ».
- **Assistant IA** (facultatif, désactivé par défaut) : Ollama sur un PC de l'atelier (modèle conseillé
  `qwen2.5:7b`) ou une API compatible OpenAI. Il propose un symptôme et un impact pour une demande, un
  compte rendu structuré, des codes de défaillance pris **uniquement** dans la liste existante, une
  check-list de gamme, un commentaire du rapport mensuel et les textes du wiki de maintenance (ci-dessous).
  L'IA propose, l'humain valide (« Utiliser », « Modifier », « Ignorer ») : rien n'est écrit sans clic.
  Une mention permanente dit où vont les textes (« reste sur ce PC »… « données envoyées à … ») ; les
  fournisseurs en ligne ne sont utilisables que si le responsable les autorise ; la clé d'accès reste
  dans le navigateur du poste. En mode serveur, les appels passent par le serveur de Prévo.
- **Wiki de maintenance** : l'encyclopédie de l'atelier (menu « Wiki ») : une page par machine, panne,
  article, technicien, intervention et savoir-faire, toutes reliées. Les faits (pannes, interventions,
  pièces, stock, habilitations) sont calculés par Prévo sans IA, et la recherche n'utilise pas l'IA.
  Avec l'assistant IA, chaque OT clôturé administrativement entre dans une file que le responsable
  traite quand il le veut (« Traiter la file ») : l'IA propose des textes courts (« En bref » et
  « Astuces » d'une machine, « À quoi il sert » d'un article, savoir-faire tirés d'abord de l'« Astuce
  pour la prochaine fois » saisie à la clôture technique), Prévo les contrôle (chaque phrase cite un OT,
  aucun nombre ni date hors de l'OT, aucun comptage, aucune consigne de sécurité, longueurs) et le
  responsable valide, rejette ou relance ; une contradiction est signalée sur la page (« À trancher »),
  jamais écrasée. Coût mesuré sur la démo avec Claude Sonnet (`claude-sonnet-5-5`) : 227 OT intégrés
  pour 5,16 $, soit 0,026 $ par OT (environ 2,5 centimes) ; cela dépend du fournisseur et de la longueur
  des comptes rendus ; rien n'est facturé avec Ollama.
- **Dictée vocale** : bouton micro sur les champs de texte longs, texte ajouté à la fin du champ,
  avertissement à la première utilisation (la voix est transcrite par Google ou Microsoft), désactivable
  par poste ; sur téléphone sans https, Prévo rappelle le micro du clavier.
- **Ce poste** : écran ouvert à tous pour les réglages du navigateur (profil et nom du poste, assistant
  IA, dictée, **thème clair** ou sombre).
- **https en option** : `serveur.py --certificat … --cle …` avec un certificat que vous fournissez (le
  guide explique mkcert et l'installation sur Android et iPhone), pour avoir le micro et la caméra dans
  la page sur les téléphones. Les étiquettes QR imprimées en http sont alors à réimprimer.
- **Mise à jour signalée** (responsable, désactivée par défaut) : Paramètres, « Me signaler les nouvelles
  versions de Prévo » ; Prévo lit alors `https://prevo.pro/version.json` au plus une fois par jour et par
  poste et dit, sur l'accueil du responsable et dans « À propos », qu'une version plus récente existe, avec
  le lien de téléchargement. Rien ne s'installe tout seul ; sans accord, aucun appel.
- **Guide et fiche technique** : [GUIDE.html](GUIDE.html) (autonome, imprimable, avec captures) et
  [FICHE_TECHNIQUE_CSV.md](FICHE_TECHNIQUE_CSV.md), générée depuis le schéma.

## Format des données

Les données sont 24 fichiers CSV (format 3 depuis le lot 6) : séparateur `;`, UTF-8 avec BOM,
fins de ligne CRLF. Ils s'ouvrent et se modifient dans Excel. Comme Excel abîme certaines valeurs
(zéros de tête, formules, fractions prises pour des dates), Prévo les protège par une apostrophe
en tête de cellule et la retire à la lecture. À la lecture, il accepte aussi les dates écrites
`JJ/MM/AAAA` par Excel. Chaque fichier et chaque colonne sont décrits dans
[FICHE_TECHNIQUE_CSV.md](FICHE_TECHNIQUE_CSV.md).

Ne modifiez pas un fichier dans Excel pendant que quelqu'un enregistre dans Prévo : le serveur
signale un fichier verrouillé, et le mode dossier détecte le conflit.

### Si Prévo signale un fichier abîmé

Prévo n'enregistre jamais un fichier CSV qu'il ne peut pas relire sans perte (une note tapée à droite
du tableau dans Excel, un guillemet oublié, une copie interrompue) : un bandeau « Fichier abîmé » le
nomme dès l'ouverture, et toute modification de ce fichier est refusée sans rien effacer (la saisie
reste dans le formulaire). Le responsable ouvre alors **Paramètres › Sauvegardes** et clique sur
**Restaurer…** devant la sauvegarde du jour, ou celle de la veille si le fichier était déjà abîmé
(« Une seule table » ne remet que ce fichier) ; avant de restaurer, Prévo copie l'état actuel dans
une copie de sécurité. Il peut aussi réparer le fichier : ce qui ne va pas est décrit dans
**Paramètres › Contrôle de la base**. Besoin d'aide : https://github.com/nicoboy49/prevo/issues

Pour lancer les tests ou contribuer : voir CONTRIBUTING.md.

## Limites connues

- **Pas d'authentification.** Les profils adaptent l'interface ; ils ne sont pas une mesure de
  sécurité. Toute personne qui atteint le serveur peut lire et écrire les données.
- **Réseau local uniquement.** Le serveur n'est pas conçu pour être exposé sur Internet ; il n'a pas de
  gestion de comptes. Le https est une option, avec un certificat que vous fournissez.
- **Le serveur ne sert que l'application.** Il répond seulement pour `index.html`, `favicon.svg`,
  `GUIDE.html` et les dossiers `css/` et `js/` (liste blanche). Tout autre fichier du dossier
  (`README.md`, `docs/`, `tests/`, `outils/`, `serveur.py`…) répond « introuvable » (404), et le dossier
  `donnees/` n'est accessible que par l'API de l'application. Ce n'est pas une protection des données :
  sans authentification, l'API reste ouverte à qui atteint le serveur.
- **Chrome ou Edge requis pour le mode dossier** (API d'accès aux fichiers).
- **Coût des pièces au prix actuel.** Le coût d'un OT utilise le prix actuel de l'article ; une
  réception d'achat ne change pas ce prix (le responsable le modifie à la main), mais un changement
  de prix modifie aussi le coût des OT passés, et donc les indicateurs de coût. Un rapport mensuel
  figé, lui, garde les chiffres du jour où il a été figé (« Recalculer » en crée une nouvelle version).
- **Étiquettes QR et adresse du PC.** En mode serveur, le QR contient l'adresse réseau du PC. Si
  elle change (la box attribue une autre adresse, le port change), les étiquettes déjà collées ne
  mènent plus à la fiche : réservez une adresse fixe pour ce PC dans la box. En modes dossier et
  démo, le QR contient `GMAO:<identifiant>`, lisible seulement par le scan de Prévo sur ce poste.
- **Les indicateurs valent ce que vaut la saisie.** MTBF, MTTR et disponibilité reposent sur la durée
  d'arrêt saisie à la clôture et sur les heures de fonctionnement par jour de chaque équipement ; un
  équipement sans ces heures est exclu, et la liste des exclus est affichée. « Dont attente de
  pièces » n'est calculé que pour les pannes dont tout l'historique est au journal de Prévo (pas pour
  un OT ajouté à la main dans Excel).
- **Les suggestions sont des faits à examiner.** Elles comptent les pannes par cause codée à la
  clôture : une cause mal codée fausse le compte. Pour « revoir le préventif », toutes les causes
  comptent, même celles qu'une gamme ne vise pas : ignorez la suggestion avec un motif. Sur une base
  passée du format 1 au format 2, seules les visites faites après ce passage comptent pour « allonger
  une gamme » (avant, l'absence d'anomalie n'était pas saisie).
- **Assistant IA.** Une proposition peut être fausse : elle est toujours relue avant d'être utilisée.
  Un modèle local est lent sans carte graphique (plus d'une minute par réponse est possible). En modes
  dossier et démo, Ollama doit autoriser les pages ouvertes depuis le disque (`OLLAMA_ORIGINS`, voir
  le guide) ; un fournisseur en ligne reçoit les textes envoyés.
- **Wiki de maintenance.** Il ne se fabrique qu'à partir des OT clôturés administrativement ; ses textes
  rédigés sont contrôlés et validés, mais restent à relire. Les textes du wiki de la démo ont été écrits
  par Claude Sonnet (un agent par OT, avec la consigne de Prévo) puis relus : ils décrivent un atelier
  fictif. Le coût par OT n'a été mesuré qu'avec ce fournisseur ; avec une IA locale (Ollama), rien n'est
  facturé, mais la qualité des textes et la durée n'ont pas été mesurées.
- **Dictée.** Elle dépend du navigateur : Chrome et Edge envoient la voix à Google ou Microsoft, et
  le micro n'est permis que sur une page sécurisée (sur le PC lui-même, ou en https).
- Sur téléphone en mode serveur sans https, le scan par caméra intégrée à la page et la dictée ne sont
  pas proposés : la photo passe par l'appareil photo du téléphone, la dictée par le micro du clavier.

## Comment ce projet a été fait

Le cahier des charges a été rédigé par Nicolas Briand avec Claude ; le code a ensuite été produit
par des sous-agents Claude Code, sous la coordination d'un orchestrateur qui n'accepte une tâche
que si sa vérification passe, avec relecture indépendante à chaque étape. La méthode et les
preuves, lot par lot, sont détaillées dans [docs/PILOTAGE.md](docs/PILOTAGE.md).

## Licence et crédits

Code sous licence MIT (voir `LICENSE`), Copyright (c) 2026 Nicolas Briand — SELECTIS. Pour les
bibliothèques tierces et la police, voir `NOTICE`.

Prévo embarque, sans modification, PapaParse, qrcode-generator, jsQR, JSZip (et pako) et Apache
ECharts, ainsi que la police Sora (SIL Open Font License 1.1). Leurs licences sont reproduites dans
`js/lib/LICENCES.txt`.

## Contact

Nicolas Briand — SELECTIS, formation et maintenance industrielle.
Site : https://selectis.eu
