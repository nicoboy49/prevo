'use strict';
// AccesTextes : textes d'aide de l'accès et de l'installation, une seule source pour l'assistant, Paramètres,
// Équipe › Accès et le guide (lot 7, CS124, CS130). Produit par outils/generer_acces_textes.py à partir de
// CLES_CONFIGURATION de serveur.py (options) et des textes de l'étude validée (choix) : ne pas retoucher à la main.

const AccesTextes = {
  "situations": {
    "seul": "Moi seul",
    "equipe": "Une petite équipe",
    "informaticien": "Je suis l'informaticien de l'entreprise"
  },
  "choix": {
    "installation": {
      "titre": "Installer sur ce PC ou sur un serveur ?",
      "qui": "Celui qui installe. Un « serveur » est simplement un ordinateur qui reste allumé et que personne n'utilise pour autre chose (mini-PC, Raspberry Pi, serveur de l'entreprise).",
      "change": "Sur votre PC de bureau : rien de plus à acheter, mais Prévo s'arrête quand le PC s'éteint ou se met en veille. Sur un serveur : Prévo est toujours là.",
      "pourquoi": "Les téléphones et les collègues joignent Prévo seulement quand la machine qui l'héberge est allumée.",
      "conseil": {
        "seul": "Votre PC suffit ; Prévo vous proposera de l'empêcher de se mettre en veille.",
        "equipe": "Un mini-PC ou un Raspberry Pi qui reste allumé est le plus tranquille.",
        "informaticien": "Votre serveur."
      }
    },
    "mot_de_passe": {
      "titre": "Mot de passe ou pas ?",
      "qui": "Tous ceux qui ouvriront Prévo.",
      "change": "Sans mot de passe, Prévo n'est joignable que sur ce PC (pas de téléphone, pas de collègue). Avec, chaque personne a son compte et son rôle ; les demandeurs peuvent n'avoir qu'un appareil enrôlé par QR.",
      "pourquoi": "Dès qu'un autre appareil peut joindre Prévo, n'importe qui sur le même réseau le pourrait aussi : lire les comptes rendus, effacer des ordres de travail, restaurer une vieille sauvegarde. Le mot de passe n'est pas une formalité, c'est la porte.",
      "conseil": {
        "seul": "Seul sur ce PC : pas besoin. Dès que vous voulez votre téléphone : obligatoire.",
        "equipe": "Obligatoire : Prévo ne propose pas l'inverse.",
        "informaticien": "Obligatoire, pour tout le monde, demandeurs compris."
      }
    },
    "etiquettes": {
      "titre": "Étiquettes QR ou pas ?",
      "qui": "Les demandeurs, qui les scannent, et celui qui les imprime et les colle.",
      "change": "Un QR sur chaque machine ouvre sa fiche et « Signaler un problème » sans chercher. L'étiquette contient l'adresse de Prévo : si elle change, l'étiquette ne mène plus nulle part.",
      "pourquoi": "Les demandes arrivent déjà renseignées (bonne machine, photo) ; sans étiquette, elles se font par recherche du nom.",
      "conseil": {
        "seul": "Inutile tant que vous êtes le seul à déclarer.",
        "equipe": "Oui, après avoir réservé l'adresse du PC dans la box (le guide montre comment).",
        "informaticien": "Oui, avec le nom du serveur dans le réseau de l'entreprise."
      }
    },
    "exterieur": {
      "titre": "Accès depuis l'extérieur ou pas ?",
      "qui": "Les personnes en astreinte ou en déplacement.",
      "change": "Avec : vos téléphones joignent Prévo partout, par un réseau privé (Tailscale, ou le VPN de l'entreprise). Sans : Prévo n'est joignable que sur le Wi-Fi de l'atelier.",
      "pourquoi": "Prévo n'ouvre jamais votre box à Internet : un réseau privé relie vos appareils entre eux, chiffrés, sans rien exposer. Il faut l'application du réseau privé sur chaque téléphone qui sort.",
      "conseil": {
        "seul": "Oui si vous voulez consulter ou clore depuis chez vous.",
        "equipe": "Oui pour la maintenance, non pour les demandeurs.",
        "informaticien": "Le VPN de l'entreprise."
      }
    },
    "demarrage": {
      "titre": "Démarrer avec le PC ?",
      "qui": "Celui qui, sinon, devrait penser à lancer Prévo chaque matin ; tous ceux qui attendent qu'il réponde.",
      "change": "Oui : Prévo démarre avant même qu'on ouvre une session, sans fenêtre ; on l'arrête depuis Paramètres. Non : un raccourci sur le bureau, et une fenêtre à ne pas fermer.",
      "pourquoi": "Un téléphone qui scanne une étiquette à 7 h du matin ne doit pas tomber sur « serveur injoignable ».",
      "conseil": {
        "seul": "Au choix si Prévo ne sert que sur ce PC ; oui dès qu'un téléphone est prévu.",
        "equipe": "Oui.",
        "informaticien": "Oui, ou l'outil de service de l'entreprise."
      }
    },
    "veille": {
      "titre": "Empêcher la veille ?",
      "qui": "Le PC qui héberge Prévo.",
      "change": "Sur secteur, le PC ne se met plus en veille (l'écran, si). Consommation : quelques dizaines de watts en continu.",
      "pourquoi": "En veille, le PC ne répond à personne ; le réveil par le réseau n'est pas fiable sur un PC de bureau.",
      "conseil": {
        "seul": "Oui si des téléphones doivent joindre Prévo ; non si Prévo ne sert que sur ce PC.",
        "equipe": "Oui.",
        "informaticien": "Sans objet sur un serveur."
      }
    },
    "certificat": {
      "titre": "Certificat automatique, par le réseau privé, ou le vôtre ?",
      "qui": "Chaque appareil qui ouvre Prévo.",
      "change": "Automatique : Prévo fabrique un certificat pour l'atelier ; chaque téléphone doit « faire confiance au PC atelier » une fois (QR, deux minutes, guidé pas à pas). Réseau privé : certificat reconnu d'office, rien à installer, mais seulement par l'adresse du réseau privé. Le vôtre : deux fichiers PEM.",
      "pourquoi": "Sans https, le navigateur du téléphone refuse la caméra (scan dans Prévo) et le micro (dictée), et le mot de passe circulerait en clair sur le Wi-Fi.",
      "conseil": {
        "seul": "Le réseau privé si vous utilisez Tailscale ; sinon automatique.",
        "equipe": "Automatique.",
        "informaticien": "Le vôtre, ou votre mandataire inverse."
      }
    },
    "sauvegardes": {
      "titre": "Où copier les sauvegardes ?",
      "qui": "Le responsable.",
      "change": "Chaque nuit, Prévo copie la sauvegarde du jour dans le dossier choisi et garde les 30 dernières.",
      "pourquoi": "Les sauvegardes quotidiennes sont sur le même disque que les données : un disque qui lâche emporte tout.",
      "conseil": {
        "seul": "Une clé USB laissée branchée, un NAS ou un dossier OneDrive ou Drive : n'importe lequel vaut mieux que rien.",
        "equipe": "Un NAS ou un dossier synchronisé.",
        "informaticien": "La sauvegarde de l'entreprise, ou un dossier qu'elle couvre."
      }
    },
    "ia": {
      "titre": "Assistant IA en ligne ?",
      "qui": "Le responsable, et les personnes dont les comptes rendus partent chez le fournisseur.",
      "change": "L'adresse du fournisseur et la clé sont réglées sur ce PC, une fois pour tous les postes ; plus aucune clé sur les téléphones.",
      "pourquoi": "La clé ne circule plus sur le réseau, et la décision ne se contourne plus depuis un poste.",
      "conseil": {
        "seul": "Laissez-le désactivé tant que vous n'en avez pas besoin.",
        "equipe": "Laissez-le désactivé tant que vous n'en avez pas besoin.",
        "informaticien": "Selon la politique de l'entreprise sur les données des salariés (voir la rubrique RGPD du guide)."
      }
    }
  },
  "options": {
    "portee": {
      "aide": "D'où Prévo peut être ouvert : ce PC seulement, le Wi-Fi de l'atelier, ou aussi hors de l'atelier. Au-delà de ce PC, mot de passe et https sont obligatoires.",
      "defaut": "ce-pc",
      "genre": "choix:ce-pc|atelier|dehors"
    },
    "ecoute": {
      "aide": "Adresse d'écoute : 127.0.0.1 (ce PC seulement) ou 0.0.0.0 (le réseau).",
      "defaut": "127.0.0.1",
      "genre": "choix:127.0.0.1|0.0.0.0"
    },
    "port_http": {
      "aide": "Port de l'application sur ce PC et de la porte d'entrée sur le réseau. Changer de port rend les étiquettes imprimées caduques.",
      "defaut": 8080,
      "genre": "entier"
    },
    "port_https": {
      "aide": "Port de l'application en https sur le réseau.",
      "defaut": 8443,
      "genre": "entier"
    },
    "noms": {
      "aide": "Noms par lesquels on appelle ce PC, en plus de son adresse et de son nom Windows (nom Tailscale, nom du réseau de l'entreprise). Un nom inconnu est refusé, par sécurité.",
      "defaut": [],
      "genre": "liste"
    },
    "certificat": {
      "aide": "Certificat https du serveur (fichier PEM), avec sa clé.",
      "defaut": "",
      "genre": "texte"
    },
    "cle": {
      "aide": "Clé privée du certificat (fichier PEM).",
      "defaut": "",
      "genre": "texte"
    },
    "certificat_auto": {
      "aide": "Certificat fabriqué par Prévo pour l'atelier, à faire reconnaître une fois par appareil.",
      "defaut": true,
      "genre": "booleen"
    },
    "mandataire": {
      "aide": "Prévo est derrière un mandataire (tailscale serve, Caddy, nginx, IIS) qui porte le https : les en-têtes X-Forwarded-Proto et X-Forwarded-Host venus de ce PC sont crus.",
      "defaut": false,
      "genre": "booleen"
    },
    "comptes": {
      "aide": "Connexion obligatoire : chaque personne a son compte, ou son appareil enrôlé pour les demandeurs.",
      "defaut": false,
      "genre": "booleen"
    },
    "demandeurs_avec_compte": {
      "aide": "Non : un demandeur donne son nom sur un appareil enrôlé par QR. Oui : chaque demandeur a un mot de passe.",
      "defaut": false,
      "genre": "booleen"
    },
    "session_heures": {
      "aide": "Au bout de ce temps sans activité, il faut se reconnecter.",
      "defaut": 12,
      "genre": "entier"
    },
    "session_longue_jours": {
      "aide": "Durée de « rester connecté sur cet appareil ».",
      "defaut": 30,
      "genre": "entier"
    },
    "invitation_heures": {
      "aide": "Durée de validité d'une invitation d'appareils (1 à 168 heures).",
      "defaut": 24,
      "genre": "entier"
    },
    "demarrage": {
      "aide": "Prévo démarre avec le PC (systeme), à l'ouverture de session (session), ou à la main (aucun).",
      "defaut": "aucun",
      "genre": "choix:aucun|systeme|session"
    },
    "veille_desactivee": {
      "aide": "Le PC ne se met plus en veille quand il est sur secteur.",
      "defaut": false,
      "genre": "booleen"
    },
    "copie_sauvegardes": {
      "aide": "Dossier où la sauvegarde du jour est copiée chaque nuit (clé USB, NAS, dossier synchronisé) ; vide : aucune copie.",
      "defaut": "",
      "genre": "texte"
    },
    "quota_documents_mo": {
      "aide": "Place maximale des documents joints, en mégaoctets.",
      "defaut": 2048,
      "genre": "entier"
    },
    "ia_url": {
      "aide": "Adresse du service d'IA que tous les postes utilisent. Réglée ici seulement, jamais sur un téléphone.",
      "defaut": "http://localhost:11434",
      "genre": "texte"
    },
    "ia_cle": {
      "aide": "Clé du service d'IA, gardée sur ce PC, jamais envoyée aux navigateurs.",
      "defaut": "",
      "genre": "texte"
    },
    "ia_en_ligne": {
      "aide": "Autoriser un service d'IA en ligne : les textes envoyés partent chez ce fournisseur.",
      "defaut": false,
      "genre": "booleen"
    }
  }
};
