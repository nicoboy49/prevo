'use strict';
// AideEcransTextes : textes de l'aide à l'écran (encart de la première visite), validés par Nicolas le 2026-10-25.
// Source : AIDE-ECRANS.md § 2 (dossier de conception du site), produit par un script ; ne pas retoucher à la main
// sans reporter la modification dans la source. Une entrée par identifiant d'écran (App.ecran) : titre, ancre du
// guide, texte et geste « Essayez », ou une variante par profil ; « demo » = phrase ajoutée dans la version web.
// Un écran sans entrée prend celle de son parent ; À propos n'en a pas.

const AideEcransTextes = {
  "accueil": {
    "titre": "Accueil",
    "ancre": "accueil",
    "profils": {
      "responsable": {
        "texte": "Votre tableau de bord : ce qui demande une décision aujourd'hui. En haut, la synthèse et « À traiter en premier » ; dessous, les demandes à traiter, les ordres de travail en retard et trois tuiles à surveiller (articles à commander, contrôles et habilitations, suggestions de préventif). Chaque chiffre mène à sa liste.",
        "essayez": "cliquez sur le compteur « DI à traiter »."
      },
      "technicien": {
        "texte": "Vos ordres de travail ouverts, du plus urgent au moins urgent. Un clic ouvre l'ordre, avec sa check-list, ses temps et ses pièces.",
        "essayez": "ouvrez le premier ordre et regardez l'onglet Exécution."
      },
      "demandeur": {
        "texte": "Vos demandes d'intervention et ce qu'elles sont devenues : acceptée, différée ou refusée, avec le motif.",
        "essayez": "« Signaler un problème » pour créer une demande en cinq questions."
      }
    },
    "demo": "Vous êtes dans la démo : essayez tout, rien n'est enregistré ailleurs que dans ce navigateur."
  },
  "nouvelle-di": {
    "titre": "Signaler un problème",
    "ancre": "signaler",
    "texte": "Cinq questions, depuis un PC ou un téléphone : quel équipement (recherche ou scan de son étiquette QR), que constatez-vous, quel impact, des précisions, une photo. Prévo calcule la priorité dès l'impact choisi, d'après la criticité de l'équipement : un impact Sécurité donne toujours P1.",
    "essayez": "tapez « compresseur », choisissez l'impact Arrêt et regardez la priorité s'afficher."
  },
  "liste-di": {
    "titre": "Demandes",
    "ancre": "demandes",
    "profils": {
      "responsable": {
        "texte": "Toutes les demandes d'intervention et leur statut. Pour chaque nouvelle demande, vous décidez : Accepter crée l'ordre de travail, Regrouper la rattache à un ordre déjà ouvert sur la même machine, Différer ou Refuser demandent un motif que le demandeur verra.",
        "essayez": "ouvrez une demande « à traiter » et acceptez-la."
      },
      "technicien": {
        "texte": "Les demandes d'intervention et leur statut. Un refus ou un report affiche toujours son motif.",
        "essayez": "ouvrez une demande pour voir son équipement et son historique."
      },
      "demandeur": {
        "texte": "Les demandes d'intervention et leur statut. Un refus ou un report affiche toujours son motif.",
        "essayez": "ouvrez une demande pour voir son équipement et son historique."
      }
    }
  },
  "fiche-di": {
    "titre": "Demande",
    "ancre": "demandes",
    "texte": "Le détail d'une demande : équipement, constat, impact, priorité calculée, photo, et sa suite (ordre de travail créé, report, refus). L'encart « causes fréquentes » rappelle ce qui a déjà expliqué le même symptôme sur cette machine : une statistique de l'historique, pas un diagnostic.",
    "essayez": "le bouton Accepter, si vous êtes responsable."
  },
  "liste-ot": {
    "titre": "Ordres de travail",
    "ancre": "ordres",
    "profils": {
      "responsable": {
        "texte": "Tous les ordres de travail, à filtrer par statut, technicien, équipement ou priorité, et à exporter en CSV. Un ordre va de Créé à Clôturé administrativement en passant par Préparé, Planifié, En cours et Clôturé techniquement ; il peut être mis en attente ou annulé, toujours avec un motif.",
        "essayez": "filtrez sur « En retard »."
      },
      "technicien": {
        "texte": "Vos ordres de travail et ceux de l'équipe. Les vôtres sont en tête.",
        "essayez": "ouvrez un ordre « En cours »."
      }
    }
  },
  "fiche-ot": {
    "titre": "Ordre de travail",
    "ancre": "ordres",
    "profils": {
      "responsable": {
        "texte": "Quatre onglets : Préparation (travail à faire, pièces, technicien, date), Exécution (check-list, temps, sorties de pièces), Compte rendu (symptôme, cause, remède, astuce pour la prochaine fois) et Historique de l'équipement. Prévo refuse de planifier s'il manque une pièce en stock et avertit si le technicien n'a pas l'habilitation requise.",
        "essayez": "onglet Préparation, bouton Planifier."
      },
      "technicien": {
        "texte": "Votre feuille de travail : la check-list à cocher dans Exécution, vos temps, les pièces sorties du magasin, puis le compte rendu et la clôture technique. La procédure de consignation s'affiche ici : la lire ne consigne rien.",
        "essayez": "cochez une opération de la check-list."
      }
    }
  },
  "planning": {
    "titre": "Planning",
    "ancre": "planning",
    "texte": "La semaine, une ligne par technicien avec sa charge et sa capacité. En haut, les ordres « Préparé » à placer, les plus prioritaires d'abord. Glissez une carte sur un technicien et un jour, ou utilisez « Planifier… » sans souris. Les mêmes règles s'appliquent : pièce manquante, habilitation.",
    "essayez": "glissez un ordre sur Julien Moreau, mardi."
  },
  "preventif": {
    "titre": "Préventif",
    "ancre": "preventif",
    "texte": "Les gammes : une maintenance à refaire régulièrement, déclenchée par une date, un compteur ou un seuil de mesure, avec sa check-list. Chaque gamme échue crée un seul ordre de travail à l'ouverture de Prévo, ou avec « Générer les OT échus ». L'onglet Calendrier montre les douze prochaines semaines ; l'onglet Suggestions, ce que l'historique conseille.",
    "essayez": "ouvrez une gamme et lisez sa check-list."
  },
  "preventif-gamme": {
    "titre": "Gamme de préventif",
    "ancre": "preventif",
    "texte": "Une gamme : son équipement, son déclencheur (jours, heures de marche ou mesure), sa check-list avec les valeurs attendues, et ses derniers passages. À la clôture de l'ordre, la gamme repart de la date réelle de fin.",
    "essayez": "le bouton « Générer l'OT » si la gamme est échue."
  },
  "magasin": {
    "titre": "Magasin",
    "ancre": "magasin",
    "texte": "Articles, Mouvements, Inventaire, À commander, Achats, Fournisseurs. Le stock est recalculé à partir des mouvements ; toute sortie est imputée à un ordre de travail et une sortie qui rendrait le stock négatif est refusée. Sous le point de commande, l'article passe dans « À commander ».",
    "essayez": "onglet À commander, puis « Demander l'achat »."
  },
  "magasin-article": {
    "titre": "Article",
    "ancre": "magasin",
    "texte": "Un article : stock calculé, point de commande (Prévo en suggère une valeur, vous la saisissez), fournisseur, prix, équipements qui l'utilisent et derniers mouvements.",
    "essayez": "« Entrée en stock »."
  },
  "parc": {
    "titre": "Parc",
    "ancre": "parc",
    "texte": "L'arborescence du site : ateliers, lignes, équipements. Chaque fiche a son QR code, sa criticité A, B ou C, ses compteurs, ses gammes, ses contrôles et son historique. Le responsable ajoute et modifie ; les étiquettes QR s'impriment par atelier ou par ligne, planche A4 de 24 ou de 8.",
    "essayez": "dépliez l'Atelier Usinage et ouvrez une machine."
  },
  "equipement": {
    "titre": "Équipement",
    "ancre": "parc",
    "texte": "La fiche d'une machine : fiche technique et procédure de consignation, QR code, compteurs et relevés, gammes de préventif, contrôles réglementaires, sous-équipements, pièces liées et toutes les interventions passées. Tout ce qu'il faut savoir avant d'intervenir est ici.",
    "essayez": "l'onglet Historique."
  },
  "parc-etiquettes": {
    "titre": "Étiquettes QR",
    "ancre": "parc",
    "texte": "Choisissez un atelier ou une ligne, une planche de 24 ou de 8 étiquettes, un décalage d'impression si besoin, et imprimez. Le repère de l'équipement est toujours écrit en clair sous le code.",
    "essayez": "l'Atelier Usinage, planche de 24, Aperçu."
  },
  "controles": {
    "titre": "Contrôles réglementaires",
    "ancre": "controles",
    "texte": "L'échéancier par équipement : en retard, observations à lever, à planifier sous trente jours, à jour. On enregistre un contrôle réalisé avec son rapport, on lève les observations, on crée un ordre réglementaire pré-rempli. Prévo calcule la date suivante d'après la périodicité que vous saisissez ; il ne fait pas de veille réglementaire.",
    "essayez": "ouvrez un contrôle « en retard »."
  },
  "controles-fiche": {
    "titre": "Contrôle réglementaire",
    "ancre": "controles",
    "texte": "Un contrôle : équipement, type, périodicité, dernier passage, prochaine échéance calculée, rapport joint et observations à lever.",
    "essayez": "« Enregistrer le contrôle réalisé »."
  },
  "equipe": {
    "titre": "Équipe",
    "ancre": "equipe",
    "texte": "Les techniciens, leur métier, leur capacité par semaine, et leurs habilitations avec leur échéance. Un renouvellement ajoute une ligne et garde l'historique. Les habilitations échues ou qui expirent sous soixante jours remontent sur l'accueil. Le taux horaire n'est visible que du responsable.",
    "essayez": "ouvrez un technicien et ajoutez une habilitation."
  },
  "equipe-fiche": {
    "titre": "Technicien",
    "ancre": "equipe",
    "texte": "La fiche d'un technicien : métier, capacité, habilitations et leur validité, ordres de travail en cours.",
    "essayez": "« Ajouter une habilitation »."
  },
  "indicateurs": {
    "titre": "Indicateurs",
    "ancre": "indicateurs",
    "texte": "Disponibilité, MTBF, MTTR, durée d'arrêt, part et respect du préventif, retards, délais, coûts et valeur du stock, sur la période, la criticité et l'atelier de votre choix. Chaque chiffre dit sur combien d'ordres il porte et donne la liste de ses sources ; un chiffre impossible à calculer dit pourquoi au lieu d'afficher zéro. L'onglet Rapports mensuels tient sur une page A4.",
    "essayez": "cliquez sur le MTBF pour voir ses ordres sources."
  },
  "parametres": {
    "titre": "Paramètres",
    "ancre": "parametres",
    "texte": "Les réglages partagés par tous les postes : nom de l'entreprise, délais par priorité, seuils du préventif et des suggestions, seuil « réparer ou remplacer », codes de défaillance. Et les outils de la base : sauvegardes et restauration, contrôle de la base, import depuis Excel ou CSV, export en ZIP des 24 fichiers.",
    "essayez": "les délais par priorité."
  },
  "import": {
    "titre": "Importer des données",
    "ancre": "import-etapes",
    "texte": "Reprenez vos listes et votre historique depuis Excel, OpenDocument ou CSV : choisissez le fichier, faites correspondre les colonnes, lisez l'aperçu et les erreurs avant de valider. Un import se contrôle avant d'écrire et s'annule après.",
    "essayez": "la liste des modèles de fichiers."
  },
  "controle": {
    "titre": "Contrôle de la base",
    "ancre": "parametres",
    "texte": "Prévo relit toute la base et liste ce qui cloche : références cassées, doublons, valeurs hors format. Rien n'est corrigé sans vous.",
    "essayez": "lancez le contrôle."
  },
  "poste": {
    "titre": "Ce poste",
    "ancre": "ce-poste",
    "texte": "Les réglages de ce navigateur seulement : nom du poste et profil, assistant IA (fournisseur, adresse, clé, test de connexion), dictée vocale, thème sombre ou clair, et l'aide à l'écran que vous lisez. Rien ici ne change les autres postes.",
    "essayez": "changez de profil pour voir les écrans d'un technicien."
  },
  "wiki": {
    "titre": "Wiki de maintenance",
    "ancre": "wiki",
    "texte": "L'encyclopédie de l'atelier : une page par machine, panne, article, technicien, intervention et savoir-faire. Les faits sont calculés à partir des interventions ; les textes courts (« En bref », « Astuces », savoir-faire) viennent des comptes rendus et des astuces, et chaque phrase renvoie aux ordres qui la fondent.",
    "essayez": "cherchez « fuite »."
  },
  "wiki-liste": {
    "titre": "Wiki de maintenance",
    "ancre": "wiki",
    "texte": "L'encyclopédie de l'atelier : une page par machine, panne, article, technicien, intervention et savoir-faire. Les faits sont calculés à partir des interventions ; les textes courts (« En bref », « Astuces », savoir-faire) viennent des comptes rendus et des astuces, et chaque phrase renvoie aux ordres qui la fondent.",
    "essayez": "cherchez « fuite »."
  },
  "wiki-page": {
    "titre": "Page du wiki",
    "ancre": "wiki-pages",
    "profils": {
      "technicien": {
        "texte": "Tout ce que l'atelier sait de cette machine, de cette panne ou de ce geste : la fiche et la consignation en tête, puis les pannes, les interventions et les pièces. Les petits numéros mènent aux ordres de travail cités ; « Pages qui renvoient ici » montre les liens.",
        "essayez": "cliquez sur un petit numéro."
      },
      "responsable": {
        "texte": "Tout ce que l'atelier sait de cette machine, de cette panne ou de ce geste : la fiche et la consignation en tête, puis les pannes, les interventions et les pièces. Les petits numéros mènent aux ordres de travail cités ; « Pages qui renvoient ici » montre les liens.",
        "essayez": "cliquez sur un petit numéro."
      },
      "demandeur": {
        "texte": "Tout ce que l'atelier sait de cette machine, de cette panne ou de ce geste : la fiche et la consignation en tête, puis les pannes, les interventions et les pièces. Les petits numéros donnent la date de l'intervention citée.",
        "essayez": "cherchez votre machine."
      }
    }
  },
  "wiki-ecrire": {
    "titre": "Écrire dans le wiki",
    "ancre": "wiki-ecrire",
    "texte": "Le responsable corrige un texte ou crée un savoir-faire à la main. L'écriture est inscrite au journal, avec son auteur et sa date.",
    "essayez": "corrigez une phrase et enregistrez."
  },
  "wiki-journal": {
    "titre": "Journal du wiki",
    "ancre": "wiki-journal",
    "texte": "Les ordres clôturés attendent ici d'entrer dans le wiki. « Traiter la file » les fait lire à l'assistant IA, qui propose des textes ; Prévo les contrôle, puis le responsable valide, rejette ou fait refaire chaque proposition. Les contradictions s'y tranchent aussi.",
    "essayez": "ouvrez une proposition et regardez ce qu'elle change.",
    "demo": "Dans cette démo, l'assistant IA est coupé : regardez les propositions déjà préparées."
  }
};
