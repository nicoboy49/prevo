# Prévo

*English version: [README.md](README.md)*

**La GMAO libre et gratuite des PME industrielles.**

[![Dernière version](https://img.shields.io/github/v/release/nicoboy49/prevo?label=version)](https://github.com/nicoboy49/prevo/releases/latest)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)
[![Langues](https://img.shields.io/badge/langues-fran%C3%A7ais%20%7C%20English-green)](#langues)

Site : **[prevo.pro](https://prevo.pro)** · Démo en ligne : **[prevo.pro/demo](https://prevo.pro/demo/)** ·
Téléchargement : **[dernière version](https://github.com/nicoboy49/prevo/releases/latest)**

> **Prévo 2.0** apporte l'assistant d'installation, les comptes et l'accès depuis le téléphone, l'anglais à côté du
> français, un format de données versionné avec sauvegardes automatiques, et l'export et l'import ZIP. La 1.2.1 reste
> disponible pour qui ne veut pas encore changer. Avant de mettre à jour, copiez votre dossier de données ; signalez
> tout problème dans l'onglet *Issues*.

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
Excel, stockés dans un dossier de votre choix. L'interface est en français et en anglais ; le code est écrit en
français, avec des bibliothèques embarquées. Ce qui sort du PC est décrit plus bas
([Confidentialité](#confidentialité)).

![Une matinée dans l'atelier avec Prévo : odeur de brûlé, signalement au téléphone en 30 secondes, demande traitée au bureau, ordre de travail créé et planifié (extrait de la vidéo de présentation)](docs/captures/prevo-demo.gif)

![Accueil du responsable sur le jeu de démo : compteurs, demandes à traiter et ordres de travail en retard](docs/captures/accueil.png)

- **Guide d'utilisation** : [GUIDE.html](GUIDE.html) (en anglais : [GUIDE.en.html](GUIDE.en.html)), à ouvrir dans
  le navigateur (imprimable).
- **Format des fichiers** : [FICHE_TECHNIQUE_CSV.md](FICHE_TECHNIQUE_CSV.md).
- **Feuille de route** : [ROADMAP.fr.md](ROADMAP.fr.md) (intentions, sans dates).

La **2.0** contient les **lots 1 à 7** du cahier des charges, dont le wiki de maintenance, la reprise des données
existantes (lot 5) et l'accès sécurisé avec son assistant d'installation (lot 7), et le chantier multilingue
(français et anglais) ; les nouveautés de chaque version sont dans [CHANGELOG.md](CHANGELOG.md).

## Essayer en 30 secondes

1. Ouvrez `index.html` dans Chrome ou Edge (double-clic ou glisser-déposer dans le navigateur).
2. Cliquez sur **Essayer avec les données de démo**, puis choisissez un profil (**Responsable** voit
   tout).

Le jeu de démo est un atelier entièrement fictif, avec treize mois d'historique dont les dates sont
recalées sur aujourd'hui. Il vit en mémoire : rien n'est enregistré, et un bouton permet de l'exporter
en ZIP.

## Installation

1. **Dézippez** le zip de la [dernière version](https://github.com/nicoboy49/prevo/releases/latest) et placez son
   dossier en `C:\Prevo` (conseillé ; ailleurs, l'assistant propose de l'y déplacer).
2. **Double-cliquez sur `Lancer_GMAO.bat`** : Python est dans le zip, il n'y a rien d'autre à installer. Sur Mac
   ou Linux : `./lancer.sh` (Python 3.11 ou plus récent).
3. **Suivez l'assistant** qui s'ouvre dans le navigateur : trois questions (qui utilise Prévo, d'où, votre
   compte) et la langue de Prévo ; il règle le reste et prépare la fiche d'accès à imprimer.

Tant que l'installation n'est pas terminée, Prévo n'est joignable que sur ce PC. Au-delà de ce PC, comptes et
https sont obligatoires : Prévo refuse de démarrer autrement. Tout se refait ensuite dans Paramètres › Accès et
installation, sur le PC serveur. Le guide détaille chaque étape ([GUIDE.html](GUIDE.html), chapitres 2 et 8).
Vous aviez Prévo 1.2 ou une bêta de la 2.0 ? Mettez la nouvelle version dans le même dossier : le zip n'a pas de
dossier `donnees/`, vos fichiers CSV restent, et l'assistant n'en remplace aucun ; Prévo fait une sauvegarde « avant
mise à jour », puis met vos données au format courant.

Vous restez en 1.2 ? La [1.2.1](https://github.com/nicoboy49/prevo/releases/tag/v1.2.1) n'a ni assistant ni
comptes : elle s'installe comme décrit dans [son README](https://github.com/nicoboy49/prevo/blob/v1.2.1/README.md)
(mode dossier dans Chrome ou Edge, ou mode serveur avec Python 3.8 ou plus récent).

### Quelle installation pour vous ?

| | Solo | Atelier | Intranet | Hébergé |
| --- | --- | --- | --- | --- |
| **Pour qui** | Une personne en maintenance | Une équipe de 1 à 3 techniciens, et des demandeurs | Une entreprise avec un informaticien | Une entreprise qui ne veut rien installer |
| **Où tourne Prévo** | Votre PC | Un PC ou un mini-PC de l'atelier | Un serveur de l'entreprise | Chez un hébergeur |
| **Qui installe** | Vous, avec l'assistant | Le responsable, avec l'assistant ; puis deux minutes par téléphone, une seule fois | L'informaticien, avec [docs/INSTALLATION.fr.md](docs/INSTALLATION.fr.md) | Un prestataire |
| **Téléphone dans l'atelier** | Oui, avec votre mot de passe | Oui, étiquettes QR comprises | Oui | Oui |
| **Téléphone hors de l'atelier** | Oui, par un réseau privé (Tailscale) | Oui, par Tailscale | Par le VPN de l'entreprise | Oui |
| **Comptes** | Aucun sur ce PC seul ; le vôtre dès qu'un téléphone se connecte | Un par technicien ; les demandeurs par téléphone enrôlé (QR, sans mot de passe) | Un par personne, demandeurs compris | Un par personne |
| **Démarre avec la machine** | Au choix | Oui | Oui (tâche planifiée ou service) | — |
| **Sauvegardes** | Chaque jour, et copie externe chaque nuit | Chaque jour, et copie externe chaque nuit | Chaque jour, et celles de l'entreprise | Celles de l'hébergeur |
| **Disponible** | Dans Prévo 2 | Dans Prévo 2 | Dans Prévo 2 | Sur demande, auprès de SELECTIS (https://selectis.eu) |

Hébergé n'est pas dans le zip : c'est une prestation, étudiée sur demande avec SELECTIS.

### Pour l'informaticien

Configuration (`prevo.config.json` et chacune de ses clés), mandataires inverses (`tailscale serve`, Caddy, nginx,
IIS, Cloudflare Tunnel), démarrage en tâche planifiée ou en service, comptes, journaux, sauvegardes, mise à jour et
désinstallation : [docs/INSTALLATION.fr.md](docs/INSTALLATION.fr.md) (en anglais :
[docs/INSTALLATION.md](docs/INSTALLATION.md)). Ce document n'est pas dans le zip : lisez-le dans le dépôt
(https://github.com/nicoboy49/prevo/blob/main/docs/INSTALLATION.fr.md).

### Pare-feu et téléphones

Quand Prévo démarre avec le PC, l'assistant ajoute lui-même une règle au pare-feu de Windows, limitée au réseau
privé de l'atelier. Sinon, au premier lancement sur le réseau, Windows demande d'autoriser Python : **cochez
uniquement « Réseaux privés »**, jamais « Réseaux publics ».

Un téléphone doit être sur le **même Wi-Fi** que le PC serveur (ou sur le réseau privé Tailscale). Il scanne le QR
code de l'accueil du responsable, ou l'adresse de la fiche d'accès. La première fois, la page « Faites confiance au
PC atelier » guide l'installation du certificat de l'atelier (Android, iPhone) ; ensuite Prévo s'ouvre en https,
avec la caméra et le micro. Un demandeur n'a pas de mot de passe : le responsable lui envoie une invitation (QR).

Les données du mode serveur sont dans le dossier `donnees/` (hors dépôt git), avec les sauvegardes
quotidiennes (`donnees/sauvegardes/`), les documents joints et les comptes (`donnees/acces/`).

### Mode dossier (un seul poste, sans serveur)

Ouvrez `index.html` dans **Chrome ou Edge**, cliquez sur « Choisir le dossier de données » et désignez un dossier
de votre PC : Prévo y lit et écrit les fichiers CSV. Ce mode est fait pour **un seul poste à la fois**, sans
téléphone ni compte ; « Reprendre le dossier précédent » évite de le choisir à nouveau. Il utilise l'API d'accès
aux fichiers de Chrome et d'Edge ; Firefox et Safari ne la proposent pas. Pour travailler à plusieurs, avec des
téléphones ou avec l'assistant IA, installez Prévo (ci-dessus) : même seul sur un PC, c'est le mode conseillé.

## Fonctions par module

- **Trois modes de stockage** : dossier, serveur Python local, démo en mémoire. Écritures concurrentes
  gérées : en cas de conflit, la modification est rejouée sur la version la plus récente du fichier
  (trois essais). Les tables modifiées sur un autre poste sont relues toutes seules.
- **Rôles** Demandeur, Technicien et Responsable : menus et écrans adaptés. Avec les comptes, le serveur vérifie
  le rôle à chaque requête (un demandeur ne voit ni coûts ni techniciens, un technicien ni taux horaire ni prix) ;
  sans comptes (ce PC seul, mode dossier, démo), le profil adapte seulement les écrans.
- **Accès et comptes** (mode serveur) : trois portées (ce PC, le Wi-Fi de l'atelier, aussi hors de l'atelier) ;
  au-delà de ce PC, connexion obligatoire et https. Comptes vérifiés par le serveur (mot de passe gardé en
  empreinte, blocage après dix échecs, « Rester connecté sur cet appareil »), créés et désactivés dans Équipe ›
  Accès, avec le journal des connexions exportable ; téléphones des demandeurs enrôlés par un QR d'invitation, sans
  mot de passe, révocables à tout moment. Le https sans rien acheter : une porte d'entrée en http conduit chaque
  appareil en https, avec un certificat que Prévo fabrique pour l'atelier ; hors de l'atelier par Tailscale, sans
  ouvrir la box ; démarrage avec le PC (tâche planifiée Windows, service systemd). Assistant d'installation en trois
  questions, fiche d'accès imprimable, et Paramètres › Accès et installation pour tout refaire depuis le PC serveur.
- **Mode Solo** (une personne fait tout) : le profil responsable avec un menu allégé, « Nouvel OT » en premier, le
  technicien « moi » pré-rempli et la clôture en une étape.
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
- **Paramètres** : réglages partagés, codes de défaillance, sauvegardes (test d'une sauvegarde, copie externe
  chaque nuit en mode serveur) et restauration, contrôle de la base, export ZIP.
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
  Une mention permanente dit où vont les textes (« reste sur ce PC »… « données envoyées à … »). En mode
  serveur, le fournisseur, son adresse et sa clé sont réglés une fois sur le PC serveur, jamais dans un
  navigateur, et le serveur relaie les demandes de tous les postes ; un fournisseur en ligne n'est utilisable que
  si le PC serveur l'autorise. Avec les comptes, l'IA est réservée aux techniciens et au responsable. En mode
  dossier, la clé reste dans le navigateur du poste.
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
  par poste ; sans page sécurisée, Prévo rappelle le micro du clavier.
- **Ce poste** : écran ouvert à tous pour les réglages du navigateur (langue, profil et nom du poste sans comptes,
  assistant IA, dictée, **thème clair** ou sombre).
- **Langues** : voir [ci-dessous](#langues).
- **Saisie gardée et brouillons** : si la session prend fin pendant une saisie, l'écran de connexion s'affiche sans
  rien effacer, et le même compte retrouve sa saisie. La déclaration d'un problème et le compte rendu d'un OT sont
  gardés au fur et à mesure dans le navigateur de l'appareil, pour le compte qui les a tapés (7 jours au plus) : un
  téléphone resté en veille les retrouve.
- **Mise à jour signalée** (activée par défaut, désactivable dans Paramètres › Mises à jour) : Prévo lit
  `https://prevo.pro/version.json` au plus une fois par jour et par poste et dit, sur l'accueil du responsable et dans
  « À propos », qu'une version plus récente existe, avec le lien de téléchargement (prevo.pro ou ce dépôt
  seulement). Un bandeau l'explique une fois. Rien ne s'installe tout seul ; jamais dans la démo.
- **« Suggérer une amélioration »** (À propos et pied du menu) : ouvre un formulaire GitHub pré-rempli avec la
  version, la langue et le navigateur, rien d'autre ; à défaut, contact@prevo.pro.
- **Guide et fiche technique** : [GUIDE.html](GUIDE.html) et [GUIDE.en.html](GUIDE.en.html) (autonomes, imprimables,
  avec captures) et [FICHE_TECHNIQUE_CSV.md](FICHE_TECHNIQUE_CSV.md), générée depuis le schéma.

## Langues

Prévo s'affiche en **français** et en **anglais** (anglais britannique ; nombres, montants et dates au format de la
langue). La langue suit cet ordre : celle du **compte** connecté, sinon le choix fait sur **ce poste** (ou sur la porte
des téléphones), sinon la **langue de l'installation** (Paramètres › Entreprise). La démo s'ouvre dans la langue du
navigateur. Les textes que Prévo écrit lui-même dans les données (historique des OT, titres pré-remplis…) sont dans la
langue de l'installation ; les valeurs des listes restent en français dans les fichiers CSV, et traduites à l'écran.
La devise se règle aussi (EUR par défaut), sans conversion des montants.

**Ajouter ou corriger une langue** : voir [CONTRIBUTING.fr.md](CONTRIBUTING.fr.md#ajouter-ou-corriger-une-langue). Le
turc, l'italien et le portugais sont prévus pour la 2.1 ([feuille de route](ROADMAP.fr.md)).

## Confidentialité

Prévo ne collecte rien : aucune statistique, aucun identifiant d'installation, aucun compte chez nous. Vos données
restent dans votre dossier, sur votre PC. Ce qui peut sortir du PC, et quand :

- **Signalement des nouvelles versions** (activé par défaut, désactivable) : une lecture par jour et par poste du
  fichier public `https://prevo.pro/version.json`, sans cookie, sans adresse de page, sans redirection. Le serveur de
  prevo.pro voit, comme pour toute page, l'adresse IP et le navigateur. Jamais dans la démo.
- **Assistant IA** (désactivé par défaut) : avec Ollama sur un PC de l'atelier, rien ne sort ; avec une IA en ligne,
  les textes envoyés (une liste fixe de champs, décrite dans le guide) partent chez le fournisseur choisi, et une
  mention permanente le dit.
- **Dictée vocale** : dans Chrome et Edge, la voix est transcrite par Google ou Microsoft ; Prévo le dit à la première
  utilisation, et la dictée se coupe dans « Ce poste ».
- **« Suggérer une amélioration »** : seulement quand vous cliquez ; ouvre GitHub avec la version de Prévo, la
  langue et le navigateur réduit (par exemple « Chrome 130, Windows »), rien d'autre.
- **Tailscale** (accès hors de l'atelier, si vous le choisissez) : un service tiers, avec son propre compte.

Les brouillons restent dans le navigateur de l'appareil ; les sauvegardes et la copie externe restent chez vous.

## Format des données

Les données sont 24 fichiers CSV (format 3 depuis le lot 6) : séparateur `;`, UTF-8 avec BOM,
fins de ligne CRLF. Ils s'ouvrent et se modifient dans Excel. Comme Excel abîme certaines valeurs
(zéros de tête, formules, fractions prises pour des dates), Prévo les protège par une apostrophe
en tête de cellule et la retire à la lecture. À la lecture, il accepte aussi les dates écrites
`JJ/MM/AAAA` par Excel. Chaque fichier et chaque colonne sont décrits dans
[FICHE_TECHNIQUE_CSV.md](FICHE_TECHNIQUE_CSV.md).

Ne modifiez pas un fichier dans Excel pendant que quelqu'un enregistre dans Prévo : le serveur
signale un fichier verrouillé, et le mode dossier détecte le conflit.

Pour lancer les tests ou contribuer : voir [CONTRIBUTING.fr.md](CONTRIBUTING.fr.md) ; pour signaler une faille :
[SECURITY.md](SECURITY.md) (jamais dans une issue publique).

## Limites connues

- **Un certificat à reconnaître par appareil.** Sur le Wi-Fi de l'atelier, chaque téléphone et chaque autre poste
  fait confiance au PC atelier une fois, guidé par la page de Prévo ; d'ici là, il reste sur cette page et n'ouvre
  pas Prévo. Un certificat fourni par l'informaticien, ou l'accès par Tailscale, évite cette étape.
- **Hors de l'atelier, il faut Tailscale ou un VPN.** Tailscale demande un compte chez Tailscale (un service
  tiers), son application sur le PC serveur et sur chaque téléphone. Prévo n'ouvre jamais la box. N'exposez Prévo
  sur Internet que derrière Tailscale, le VPN de l'entreprise ou un mandataire inverse en https
  ([docs/INSTALLATION.fr.md](docs/INSTALLATION.fr.md)) : Prévo n'a pas de double facteur.
- **Pas d'annuaire d'entreprise.** Ni Active Directory, ni LDAP, ni connexion unique : des comptes locaux, l'export
  du journal des connexions, et le mandataire inverse ou le VPN de l'entreprise pour vos propres contrôles d'accès.
- **L'hébergement n'est pas fourni.** Prévo s'installe chez vous, sur un PC qui doit rester allumé ; un hébergement
  se discute sur demande avec SELECTIS.
- **Sans comptes, les profils ne protègent rien.** Sur ce PC seul, en mode dossier et en démo, chacun choisit son
  profil : les profils adaptent les écrans. C'est pourquoi Prévo refuse d'écouter le réseau sans comptes ni https.
- **Le serveur ne sert que l'application.** Il répond seulement pour `index.html`, `favicon.svg`, `GUIDE.html` et
  les dossiers `css/`, `js/` et `acces/` (la porte d'entrée) : c'est une liste blanche. Tout autre fichier du dossier
  (`README.md`, `docs/`, `tests/`, `outils/`, `serveur.py`…) répond « introuvable » (404). Les données ne passent
  que par l'API de l'application, après connexion et selon le rôle ; `donnees/acces/` (comptes, sessions) n'est
  jamais servi.
- **Python.** Le zip embarque Python pour Windows 64 bits ; ailleurs, il faut Python 3.11 ou plus récent (et, pour
  le certificat de l'atelier, le mkcert du système : voir [docs/INSTALLATION.fr.md](docs/INSTALLATION.fr.md)).
- **Chrome ou Edge requis pour le mode dossier** (API d'accès aux fichiers).
- **Mémoire de l'export et de l'import ZIP mesurée sous Chrome seulement** : Edge et Firefox n'ont pas été mesurés.
- **Coût des pièces au prix actuel.** Le coût d'un OT utilise le prix actuel de l'article ; une
  réception d'achat ne change pas ce prix (le responsable le modifie à la main), mais un changement
  de prix modifie aussi le coût des OT passés, et donc les indicateurs de coût. Un rapport mensuel
  figé, lui, garde les chiffres du jour où il a été figé (« Recalculer » en crée une nouvelle version).
- **Étiquettes QR et adresse du PC.** En mode serveur, le QR contient l'adresse réseau du PC (celle de la
  porte d'entrée, en http : elle ne change pas avec le https). Si elle change (la box attribue une autre
  adresse, le port change), les étiquettes déjà collées ne mènent plus à la fiche : réservez une adresse fixe
  pour ce PC dans la box. En modes dossier et démo, le QR contient `GMAO:<identifiant>`, lisible seulement par
  le scan de Prévo sur ce poste.
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
  dossier et démo, Ollama refuse la page ouverte depuis le disque : pour l'IA, lancez Prévo en mode serveur,
  même seul sur un PC. Un fournisseur en ligne reçoit les textes envoyés.
- **Wiki de maintenance.** Il ne se fabrique qu'à partir des OT clôturés administrativement ; ses textes
  rédigés sont contrôlés et validés, mais restent à relire. Les textes du wiki de la démo ont été écrits
  par Claude Sonnet (un agent par OT, avec la consigne de Prévo) puis relus : ils décrivent un atelier
  fictif. Le coût par OT n'a été mesuré qu'avec ce fournisseur ; avec une IA locale (Ollama), rien n'est
  facturé, mais la qualité des textes et la durée n'ont pas été mesurées.
- **Dictée.** Elle dépend du navigateur : Chrome et Edge envoient la voix à Google ou Microsoft, et
  le micro n'est permis que sur une page sécurisée (sur le PC lui-même, ou en https).
- **Deux langues pour l'instant.** Français et anglais ; les données de la démo, le journal des requêtes de la
  console et l'aide de la ligne de commande (`--aide`) restent en français.

## Comment ce projet a été fait

Le cahier des charges a été rédigé par Nicolas Briand avec Claude ; le code a ensuite été produit
par des sous-agents Claude Code, sous la coordination d'un orchestrateur qui n'accepte une tâche
que si sa vérification passe, avec relecture indépendante à chaque étape. En résumé :
[docs/METHODE.fr.md](docs/METHODE.fr.md) ; la méthode et les preuves, lot par lot :
[docs/PILOTAGE.md](docs/PILOTAGE.md).

## Licence et crédits

Code sous licence MIT (voir `LICENSE`), Copyright (c) 2026 Nicolas Briand — SELECTIS. Pour les
bibliothèques tierces et la police, voir `NOTICE`.

Prévo embarque, sans modification, PapaParse, qrcode-generator, jsQR, Apache ECharts et SheetJS
Community Edition, ainsi que la police Sora (SIL Open Font License 1.1). Leurs licences sont reproduites dans
`js/lib/LICENCES.txt` ; le zip Windows y ajoute Python et mkcert, avec leurs licences (voir `NOTICE`).

Chacun participe dans le respect du [code de conduite](CODE_OF_CONDUCT.md).

## Contact

Nicolas Briand — SELECTIS, formation et maintenance industrielle.
Site : https://selectis.eu
Courriel : contact@prevo.pro
