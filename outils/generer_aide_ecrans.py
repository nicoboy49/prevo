#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Produit l'aide à l'écran (encart de la première visite, ARCHITECTURE.md §23) : js/modules/aide-ecrans-textes.js
(objet AideEcransTextes : écrans, ancres du guide, variantes par profil, sans aucun texte) et le bloc « aide » de
js/i18n/aide/fr.js et js/i18n/aide/en.js (les textes français et anglais, clés aide.ecran.*) : un fichier d'aide par
langue (contrat du Lot 2, décision de Nicolas du 2026-11-05, T247 ; l'anglais : T277, D158).

- ECRANS_EN : l'anglais de ces textes, même structure et même ordre, juste dessous ;
- ECRANS : une entrée par identifiant d'écran (App.ecran) : titre, ancre de GUIDE.html, texte et geste « Essayez », ou
  une variante par profil ; « demo » = phrase ajoutée dans la version web. Un écran sans entrée prend celle de son
  parent ; À propos n'en a pas. Textes validés par Nicolas le 2026-10-25 (AIDE-ECRANS.md § 2, dossier de conception
  du site), repris tels quels du module que produisait un script hors du dépôt ;
- dans le module, chaque texte est un accesseur qui le lit par I18n.t dans la langue active, au moment de l'afficher ;
  une langue sans fichier d'aide, ou sans une clé, affiche le français, sans avertissement (js/i18n.js).

js/i18n/aide/fr.js a un bloc par outil, que chacun réécrit sans toucher à l'autre : « acces » (clés aide.acces.*,
outils/generer_acces_textes.py) et « aide » (clés aide.ecran.*, cet outil). Les clés aide.encart.* de l'aide courte
restent dans js/i18n/fr.js (section aide).

Lancer depuis la racine du dépôt, après toute modification d'un texte :
    py outils/generer_aide_ecrans.py
tests/test_aide_ecrans.py vérifie que les deux fichiers sont à jour (un second passage ne change aucun octet).
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

ICI = Path(__file__).resolve().parent
if str(ICI) not in sys.path:
    sys.path.insert(0, str(ICI))
import extraire_textes as ext  # noqa: E402  (format des blocs de dictionnaire, partagé avec les outils)

RACINE = ICI.parent
MODULE = "js/modules/aide-ecrans-textes.js"
AIDE = "js/i18n/aide/fr.js"
AIDE_EN = "js/i18n/aide/en.js"
SECTION = "aide"

ENTETE_AIDE = (
    "'use strict';\n"
    "// Aide longue de Prévo en français (clés aide.*), dans un fichier à part par langue (contrat du Lot 2).\n"
    "// Une clé aide.* absente de la langue active est prise ici, sans avertissement (js/i18n.js). Clés triées, une par\n"
    "// ligne, chaînes entre apostrophes simples, échappements gardés (jamais d'espace insécable écrit en clair :\n"
    "// \\u00a0, \\u202f).\n"
    "// Un bloc par outil, que chacun réécrit (ne pas retoucher à la main) : « acces » (aide de l'accès et de\n"
    "// l'installation, outils/generer_acces_textes.py, clés aide.acces.*) ; « aide » (aide à l'écran,\n"
    "// outils/generer_aide_ecrans.py, clés aide.ecran.*).\n"
    "\n"
)

# Fichiers d'aide par langue, et leur en-tête
FICHIERS = {"fr": AIDE, "en": AIDE_EN}

# Textes français de l'aide à l'écran, une entrée par identifiant d'écran (forme d'AideEcransTextes).
ECRANS = {
    "accueil": {
        "titre": "Accueil",
        "ancre": "accueil",
        "profils": {
            "responsable": {
                "texte": (
                    "Votre tableau de bord : ce qui demande une décision aujourd'hui. En haut, la synthèse et "
                    "« À traiter en premier » ; dessous, les demandes à traiter, les ordres de travail en "
                    "retard et trois tuiles à surveiller (articles à commander, contrôles et habilitations, "
                    "suggestions de préventif). Chaque chiffre mène à sa liste."
                ),
                "essayez": "cliquez sur le compteur « DI à traiter ».",
            },
            "technicien": {
                "texte": (
                    "Vos ordres de travail ouverts, du plus urgent au moins urgent. Un clic ouvre l'ordre, "
                    "avec sa check-list, ses temps et ses pièces."
                ),
                "essayez": "ouvrez le premier ordre et regardez l'onglet Exécution.",
            },
            "demandeur": {
                "texte": (
                    "Vos demandes d'intervention et ce qu'elles sont devenues : acceptée, différée ou refusée, "
                    "avec le motif."
                ),
                "essayez": "« Signaler un problème » pour créer une demande en cinq questions.",
            },
        },
        "demo": "Vous êtes dans la démo : essayez tout, rien n'est enregistré ailleurs que dans ce navigateur.",
    },
    "nouvelle-di": {
        "titre": "Signaler un problème",
        "ancre": "signaler",
        "texte": (
            "Cinq questions, depuis un PC ou un téléphone : quel équipement (recherche ou scan de son "
            "étiquette QR), que constatez-vous, quel impact, des précisions, une photo. Prévo calcule la "
            "priorité dès l'impact choisi, d'après la criticité de l'équipement : un impact Sécurité donne "
            "toujours P1."
        ),
        "essayez": "tapez « compresseur », choisissez l'impact Arrêt et regardez la priorité s'afficher.",
    },
    "liste-di": {
        "titre": "Demandes",
        "ancre": "demandes",
        "profils": {
            "responsable": {
                "texte": (
                    "Toutes les demandes d'intervention et leur statut. Pour chaque nouvelle demande, vous "
                    "décidez : Accepter crée l'ordre de travail, Regrouper la rattache à un ordre déjà ouvert "
                    "sur la même machine, Différer ou Refuser demandent un motif que le demandeur verra."
                ),
                "essayez": "ouvrez une demande « à traiter » et acceptez-la.",
            },
            "technicien": {
                "texte": (
                    "Les demandes d'intervention et leur statut. Un refus ou un report affiche toujours son "
                    "motif."
                ),
                "essayez": "ouvrez une demande pour voir son équipement et son historique.",
            },
            "demandeur": {
                "texte": (
                    "Les demandes d'intervention et leur statut. Un refus ou un report affiche toujours son "
                    "motif."
                ),
                "essayez": "ouvrez une demande pour voir son équipement et son historique.",
            },
        },
    },
    "fiche-di": {
        "titre": "Demande",
        "ancre": "demandes",
        "texte": (
            "Le détail d'une demande : équipement, constat, impact, priorité calculée, photo, et sa suite "
            "(ordre de travail créé, report, refus). L'encart « causes fréquentes » rappelle ce qui a déjà "
            "expliqué le même symptôme sur cette machine : une statistique de l'historique, pas un diagnostic."
        ),
        "essayez": "le bouton Accepter, si vous êtes responsable.",
    },
    "liste-ot": {
        "titre": "Ordres de travail",
        "ancre": "ordres",
        "profils": {
            "responsable": {
                "texte": (
                    "Tous les ordres de travail, à filtrer par statut, technicien, équipement ou priorité, et "
                    "à exporter en CSV. Un ordre va de Créé à Clôturé administrativement en passant par "
                    "Préparé, Planifié, En cours et Clôturé techniquement ; il peut être mis en attente ou "
                    "annulé, toujours avec un motif."
                ),
                "essayez": "filtrez sur « En retard ».",
            },
            "technicien": {
                "texte": "Vos ordres de travail et ceux de l'équipe. Les vôtres sont en tête.",
                "essayez": "ouvrez un ordre « En cours ».",
            },
        },
    },
    "fiche-ot": {
        "titre": "Ordre de travail",
        "ancre": "ordres",
        "profils": {
            "responsable": {
                "texte": (
                    "Quatre onglets : Préparation (travail à faire, pièces, technicien, date), Exécution "
                    "(check-list, temps, sorties de pièces), Compte rendu (symptôme, cause, remède, astuce "
                    "pour la prochaine fois) et Historique de l'équipement. Prévo refuse de planifier s'il "
                    "manque une pièce en stock et avertit si le technicien n'a pas l'habilitation requise."
                ),
                "essayez": "onglet Préparation, bouton Planifier.",
            },
            "technicien": {
                "texte": (
                    "Votre feuille de travail : la check-list à cocher dans Exécution, vos temps, les pièces "
                    "sorties du magasin, puis le compte rendu et la clôture technique. La procédure de "
                    "consignation s'affiche ici : la lire ne consigne rien."
                ),
                "essayez": "cochez une opération de la check-list.",
            },
        },
    },
    "planning": {
        "titre": "Planning",
        "ancre": "planning",
        "texte": (
            "La semaine, une ligne par technicien avec sa charge et sa capacité. En haut, les ordres « Préparé "
            "» à placer, les plus prioritaires d'abord. Glissez une carte sur un technicien et un jour, ou "
            "utilisez « Planifier… » sans souris. Les mêmes règles s'appliquent : pièce manquante, habilitation."
        ),
        "essayez": "glissez un ordre sur Julien Moreau, mardi.",
    },
    "preventif": {
        "titre": "Préventif",
        "ancre": "preventif",
        "texte": (
            "Les gammes : une maintenance à refaire régulièrement, déclenchée par une date, un compteur ou un "
            "seuil de mesure, avec sa check-list. Chaque gamme échue crée un seul ordre de travail à "
            "l'ouverture de Prévo, ou avec « Générer les OT échus ». L'onglet Calendrier montre les douze "
            "prochaines semaines ; l'onglet Suggestions, ce que l'historique conseille."
        ),
        "essayez": "ouvrez une gamme et lisez sa check-list.",
    },
    "preventif-gamme": {
        "titre": "Gamme de préventif",
        "ancre": "preventif",
        "texte": (
            "Une gamme : son équipement, son déclencheur (jours, heures de marche ou mesure), sa check-list "
            "avec les valeurs attendues, et ses derniers passages. À la clôture de l'ordre, la gamme repart de "
            "la date réelle de fin."
        ),
        "essayez": "le bouton « Générer les OT échus » si la gamme est échue.",
    },
    "magasin": {
        "titre": "Magasin",
        "ancre": "magasin",
        "texte": (
            "Articles, Mouvements, Inventaire, À commander, Achats, Fournisseurs. Le stock est recalculé à "
            "partir des mouvements ; toute sortie est imputée à un ordre de travail et une sortie qui rendrait "
            "le stock négatif est refusée. Sous le point de commande, l'article passe dans « À commander »."
        ),
        "essayez": "onglet À commander, puis « Demander l'achat ».",
    },
    "magasin-article": {
        "titre": "Article",
        "ancre": "magasin",
        "texte": (
            "Un article : stock calculé, point de commande (Prévo en suggère une valeur, vous la saisissez), "
            "fournisseur, prix, équipements qui l'utilisent et derniers mouvements."
        ),
        "essayez": "« Entrée en stock ».",
    },
    "parc": {
        "titre": "Parc",
        "ancre": "parc",
        "texte": (
            "L'arborescence du site : ateliers, lignes, équipements. Chaque fiche a son QR code, sa criticité "
            "A, B ou C, ses compteurs, ses gammes, ses contrôles et son historique. Le responsable ajoute et "
            "modifie ; les étiquettes QR s'impriment par atelier ou par ligne, planche A4 de 24 ou de 8."
        ),
        "essayez": "dépliez l'Atelier Usinage et ouvrez une machine.",
    },
    "equipement": {
        "titre": "Équipement",
        "ancre": "parc",
        "texte": (
            "La fiche d'une machine : fiche technique et procédure de consignation, QR code, compteurs et "
            "relevés, gammes de préventif, contrôles réglementaires, sous-équipements, pièces liées et toutes "
            "les interventions passées. Tout ce qu'il faut savoir avant d'intervenir est ici."
        ),
        "essayez": "l'onglet Historique.",
    },
    "parc-etiquettes": {
        "titre": "Étiquettes QR",
        "ancre": "parc",
        "texte": (
            "Choisissez un atelier ou une ligne, une planche de 24 ou de 8 étiquettes, un décalage "
            "d'impression si besoin, et imprimez. Le repère de l'équipement est toujours écrit en clair sous "
            "le code."
        ),
        "essayez": "l'Atelier Usinage, planche de 24, Aperçu.",
    },
    "controles": {
        "titre": "Contrôles réglementaires",
        "ancre": "controles",
        "texte": (
            "L'échéancier par équipement : en retard, observations à lever, à planifier sous trente jours, à "
            "jour. On enregistre un contrôle réalisé avec son rapport, on lève les observations, on crée un "
            "ordre réglementaire pré-rempli. Prévo calcule la date suivante d'après la périodicité que vous "
            "saisissez ; il ne fait pas de veille réglementaire."
        ),
        "essayez": "ouvrez un contrôle « en retard ».",
    },
    "controles-fiche": {
        "titre": "Contrôle réglementaire",
        "ancre": "controles",
        "texte": (
            "Un contrôle : équipement, type, périodicité, dernier passage, prochaine échéance calculée, "
            "rapport joint et observations à lever."
        ),
        "essayez": "« Enregistrer le contrôle réalisé ».",
    },
    "equipe": {
        "titre": "Équipe",
        "ancre": "equipe",
        "texte": (
            "Les techniciens, leur métier, leur capacité par semaine, et leurs habilitations avec leur "
            "échéance. Un renouvellement ajoute une ligne et garde l'historique. Les habilitations échues ou "
            "qui expirent sous soixante jours remontent sur l'accueil. Le taux horaire n'est visible que du "
            "responsable."
        ),
        "essayez": "ouvrez un technicien et ajoutez une habilitation.",
    },
    "equipe-fiche": {
        "titre": "Technicien",
        "ancre": "equipe",
        "texte": (
            "La fiche d'un technicien : métier, capacité, habilitations et leur validité, ordres de travail en "
            "cours."
        ),
        "essayez": "« Ajouter une habilitation ».",
    },
    "indicateurs": {
        "titre": "Indicateurs",
        "ancre": "indicateurs",
        "texte": (
            "Disponibilité, MTBF, MTTR, durée d'arrêt, part et respect du préventif, retards, délais, coûts et "
            "valeur du stock, sur la période, la criticité et l'atelier de votre choix. Chaque chiffre dit sur "
            "combien d'ordres il porte et donne la liste de ses sources ; un chiffre impossible à calculer dit "
            "pourquoi au lieu d'afficher zéro. L'onglet Rapports mensuels tient sur une page A4."
        ),
        "essayez": "cliquez sur le MTBF pour voir ses ordres sources.",
    },
    "parametres": {
        "titre": "Paramètres",
        "ancre": "parametres",
        "texte": (
            "Les réglages partagés par tous les postes : nom de l'entreprise, délais par priorité, seuils du "
            "préventif et des suggestions, seuil « réparer ou remplacer », codes de défaillance. Et les outils "
            "de la base : sauvegardes et restauration, contrôle de la base, import depuis Excel ou CSV, export "
            "en ZIP des 24 fichiers."
        ),
        "essayez": "les délais par priorité.",
    },
    "import": {
        "titre": "Importer des données",
        "ancre": "import-etapes",
        "texte": (
            "Reprenez vos listes et votre historique depuis Excel, OpenDocument ou CSV : choisissez le "
            "fichier, faites correspondre les colonnes, lisez l'aperçu et les erreurs avant de valider. Un "
            "import se contrôle avant d'écrire et s'annule après."
        ),
        "essayez": "la liste des modèles de fichiers.",
    },
    "controle": {
        "titre": "Contrôle de la base",
        "ancre": "parametres",
        "texte": (
            "Prévo relit toute la base et liste ce qui cloche : références cassées, doublons, valeurs hors "
            "format. Rien n'est corrigé sans vous."
        ),
        "essayez": "lancez le contrôle.",
    },
    "poste": {
        "titre": "Ce poste",
        "ancre": "ce-poste",
        "texte": (
            "Les réglages de ce navigateur seulement : nom du poste et profil, assistant IA (fournisseur, "
            "adresse, clé, test de connexion), dictée vocale, thème sombre ou clair, et l'aide à l'écran que "
            "vous lisez. Rien ici ne change les autres postes."
        ),
        "essayez": "changez de profil pour voir les écrans d'un technicien.",
    },
    "wiki": {
        "titre": "Wiki de maintenance",
        "ancre": "wiki",
        "texte": (
            "L'encyclopédie de l'atelier : une page par machine, panne, article, technicien, intervention et "
            "savoir-faire. Les faits sont calculés à partir des interventions ; les textes courts (« En bref "
            "», « Astuces », savoir-faire) viennent des comptes rendus et des astuces, et chaque phrase "
            "renvoie aux ordres qui la fondent."
        ),
        "essayez": "cherchez « fuite ».",
    },
    "wiki-liste": {
        "titre": "Wiki de maintenance",
        "ancre": "wiki",
        "texte": (
            "L'encyclopédie de l'atelier : une page par machine, panne, article, technicien, intervention et "
            "savoir-faire. Les faits sont calculés à partir des interventions ; les textes courts (« En bref "
            "», « Astuces », savoir-faire) viennent des comptes rendus et des astuces, et chaque phrase "
            "renvoie aux ordres qui la fondent."
        ),
        "essayez": "cherchez « fuite ».",
    },
    "wiki-page": {
        "titre": "Page du wiki",
        "ancre": "wiki-pages",
        "profils": {
            "technicien": {
                "texte": (
                    "Tout ce que l'atelier sait de cette machine, de cette panne ou de ce geste : la fiche et "
                    "la consignation en tête, puis les pannes, les interventions et les pièces. Les petits "
                    "numéros mènent aux ordres de travail cités ; « Pages qui renvoient ici » montre les liens."
                ),
                "essayez": "cliquez sur un petit numéro.",
            },
            "responsable": {
                "texte": (
                    "Tout ce que l'atelier sait de cette machine, de cette panne ou de ce geste : la fiche et "
                    "la consignation en tête, puis les pannes, les interventions et les pièces. Les petits "
                    "numéros mènent aux ordres de travail cités ; « Pages qui renvoient ici » montre les liens."
                ),
                "essayez": "cliquez sur un petit numéro.",
            },
            "demandeur": {
                "texte": (
                    "Tout ce que l'atelier sait de cette machine, de cette panne ou de ce geste : la fiche et "
                    "la consignation en tête, puis les pannes, les interventions et les pièces. Les petits "
                    "numéros donnent la date de l'intervention citée."
                ),
                "essayez": "cherchez votre machine.",
            },
        },
    },
    "wiki-ecrire": {
        "titre": "Écrire dans le wiki",
        "ancre": "wiki-ecrire",
        "texte": (
            "Le responsable corrige un texte ou crée un savoir-faire à la main. L'écriture est inscrite au "
            "journal, avec son auteur et sa date."
        ),
        "essayez": "corrigez une phrase et enregistrez.",
    },
    "wiki-journal": {
        "titre": "Journal du wiki",
        "ancre": "wiki-journal",
        "texte": (
            "Les ordres clôturés attendent ici d'entrer dans le wiki. « Traiter la file » les fait lire à "
            "l'assistant IA, qui propose des textes ; Prévo les contrôle, puis le responsable valide, rejette "
            "ou fait refaire chaque proposition. Les contradictions s'y tranchent aussi."
        ),
        "essayez": "ouvrez une proposition et regardez ce qu'elle change.",
        "demo": "Dans cette démo, l'assistant IA est coupé : regardez les propositions déjà préparées.",
    },
}


# Anglais britannique de ces textes (chantier multilingue, Lot 3, T277 ; D158 : aide longue en français et en anglais) :
# même structure et même ordre que ECRANS, sans l'ancre (propre à GUIDE.html, la même dans toutes les langues). Noms
# d'écrans, de menus et de champs : les libellés de js/i18n/en.js ; vocabulaire : docs/GLOSSAIRE.md.
ECRANS_EN = {
    "accueil": {
        "titre": "Home",
        "profils": {
            "responsable": {
                "texte": (
                    "Your dashboard: what needs a decision today. At the top, the summary and “To handle first”; "
                    "below, the requests to handle, the overdue work orders and three tiles to keep an eye on "
                    "(items to order, inspections and authorisations, preventive suggestions). Each figure leads "
                    "to its list."
                ),
                "essayez": "click the “Requests to handle” counter.",
            },
            "technicien": {
                "texte": (
                    "Your open work orders, from the most urgent to the least. One click opens the work order, "
                    "with its checklist, its times and its parts."
                ),
                "essayez": "open the first work order and look at the Execution tab.",
            },
            "demandeur": {
                "texte": (
                    "Your requests and what became of them: accepted, deferred or declined, with the reason."
                ),
                "essayez": "use “Report a problem” to create a request in five questions.",
            },
        },
        "demo": "You are in the demo: try anything, nothing is saved anywhere except in this browser.",
    },
    "nouvelle-di": {
        "titre": "Report a problem",
        "texte": (
            "Five questions, from a PC or a phone: which equipment (search for it or scan its QR label), what "
            "you have noticed, what the impact is, any details, a photo. Prévo works out the priority as soon "
            "as you choose the impact, from the equipment's criticality: a Safety impact always gives P1."
        ),
        "essayez": "type “compressor”, choose the Stoppage impact and watch the priority appear.",
    },
    "liste-di": {
        "titre": "Requests",
        "profils": {
            "responsable": {
                "texte": (
                    "All the requests and their status. For each new request, you decide: Accept creates the "
                    "work order, Merge attaches it to a work order already open on the same machine, Defer and "
                    "Decline ask for a reason that the requester will see."
                ),
                "essayez": "open a request that is waiting to be handled and accept it.",
            },
            "technicien": {
                "texte": (
                    "The requests and their status. A refusal or a deferral always shows its reason."
                ),
                "essayez": "open a request to see its equipment and its history.",
            },
            "demandeur": {
                "texte": (
                    "The requests and their status. A refusal or a deferral always shows its reason."
                ),
                "essayez": "open a request to see its equipment and its history.",
            },
        },
    },
    "fiche-di": {
        "titre": "Request",
        "texte": (
            "The details of a request: equipment, fault, impact, calculated priority, photo, and what followed "
            "(work order created, deferral, refusal). The “common causes” panel recalls what has already "
            "explained the same symptom on this machine: a statistic from the history, not a diagnosis."
        ),
        "essayez": "the Accept button, if you are a manager.",
    },
    "liste-ot": {
        "titre": "Work orders",
        "profils": {
            "responsable": {
                "texte": (
                    "All the work orders, which you can filter by status, technician, equipment or priority, and "
                    "export to CSV. A work order goes from Created to Administratively closed through Prepared, "
                    "Scheduled, In progress and Technically closed; it can be put on hold or cancelled, always "
                    "with a reason."
                ),
                "essayez": "filter on “Overdue”.",
            },
            "technicien": {
                "texte": "Your work orders and the team's. Yours come first.",
                "essayez": "open an “In progress” work order.",
            },
        },
    },
    "fiche-ot": {
        "titre": "Work order",
        "profils": {
            "responsable": {
                "texte": (
                    "Four tabs: Preparation (work to be done, parts, technician, date), Execution (checklist, "
                    "times, parts issued), Job report (symptom, cause, remedy, tip for next time) and the "
                    "equipment history. Prévo refuses to schedule if a part is out of stock and warns you if the "
                    "technician does not have the required authorisation."
                ),
                "essayez": "Preparation tab, Schedule button.",
            },
            "technicien": {
                "texte": (
                    "Your worksheet: the checklist to tick in Execution, your times, the parts issued from the "
                    "stores, then the job report and the technical close. The isolation procedure is shown here: "
                    "reading it does not isolate anything."
                ),
                "essayez": "tick a task on the checklist.",
            },
        },
    },
    "planning": {
        "titre": "Planning",
        "texte": (
            "The week, one row per technician with their workload and capacity. At the top, the “Prepared” work "
            "orders waiting to be placed, highest priority first. Drag a card onto a technician and a day, or "
            "use “Schedule…” without a mouse. The same rules apply: missing part, authorisation."
        ),
        "essayez": "drag a work order onto Julien Moreau, Tuesday.",
    },
    "preventif": {
        "titre": "Preventive",
        "texte": (
            "The task lists: maintenance to be repeated regularly, triggered by a date, a meter or a measurement "
            "threshold, with its checklist. Each overdue task list creates a single work order when Prévo "
            "opens, or with “Generate overdue WOs”. The Calendar tab shows the next twelve weeks; the "
            "Suggestions tab, what the history recommends."
        ),
        "essayez": "open a task list and read its checklist.",
    },
    "preventif-gamme": {
        "titre": "Preventive task list",
        "texte": (
            "A task list: its equipment, its trigger (days, running hours or a measurement), its checklist with "
            "the expected values, and its latest visits. When the work order is closed, the task list restarts "
            "from the actual finish date."
        ),
        "essayez": "the “Generate overdue WOs” button, if the task list is overdue.",
    },
    "magasin": {
        "titre": "Stores",
        "texte": (
            "Items, Movements, Stocktake, To order, Purchases, Suppliers. Stock is recalculated from the "
            "movements; every issue is charged to a work order, and an issue that would make the stock negative "
            "is refused. Below the reorder point, the item moves to “To order”."
        ),
        "essayez": "To order tab, then “Request purchase”.",
    },
    "magasin-article": {
        "titre": "Item",
        "texte": (
            "An item: calculated stock, reorder point (Prévo suggests a value, you enter it), supplier, price, "
            "the equipment that uses it and the latest movements."
        ),
        "essayez": "“Stock receipt”.",
    },
    "parc": {
        "titre": "Equipment",
        "texte": (
            "The site tree: workshops, lines, equipment. Each record has its QR code, its criticality A, B or "
            "C, its meters, its task lists, its inspections and its history. The manager adds and edits; QR "
            "labels are printed by workshop or by line, on A4 sheets of 24 or 8."
        ),
        "essayez": "expand the Machining workshop and open a machine.",
    },
    "equipement": {
        "titre": "Equipment",
        "texte": (
            "A machine's record: technical details and isolation procedure, QR code, meters and readings, "
            "preventive task lists, statutory inspections, sub-equipment, linked parts and every past job. "
            "Everything you need to know before starting a job is here."
        ),
        "essayez": "the History tab.",
    },
    "parc-etiquettes": {
        "titre": "QR labels",
        "texte": (
            "Choose a workshop or a line, a sheet of 24 or 8 labels, a print offset if needed, and print. The "
            "equipment tag is always written in plain text under the code."
        ),
        "essayez": "the Machining workshop, sheet of 24, Preview.",
    },
    "controles": {
        "titre": "Statutory inspections",
        "texte": (
            "The schedule by equipment: overdue, observations to clear, to be scheduled within thirty days, up "
            "to date. You record a completed inspection with its report, clear the observations, and create a "
            "pre-filled statutory work order. Prévo calculates the next date from the interval you enter; it "
            "does not monitor regulations."
        ),
        "essayez": "open an “overdue” inspection.",
    },
    "controles-fiche": {
        "titre": "Statutory inspection",
        "texte": (
            "An inspection: equipment, type, interval, last visit, calculated next due date, attached report and "
            "observations to clear."
        ),
        "essayez": "“Save the completed inspection”.",
    },
    "equipe": {
        "titre": "Team",
        "texte": (
            "The technicians, their trade, their capacity per week, and their authorisations with their expiry "
            "date. A renewal adds a row and keeps the history. Authorisations that are overdue or expire within "
            "sixty days appear on the home screen. Only the manager can see the hourly rate."
        ),
        "essayez": "open a technician and add an authorisation.",
    },
    "equipe-fiche": {
        "titre": "Technician",
        "texte": (
            "A technician's record: trade, capacity, authorisations and their validity, work orders in progress."
        ),
        "essayez": "“Add an authorisation”.",
    },
    "indicateurs": {
        "titre": "Indicators",
        "texte": (
            "Availability, MTBF, MTTR, downtime, preventive share and compliance, delays, response times, "
            "costs and stock value, for the period, criticality and workshop of your choice. Each figure says "
            "how many work orders it covers and lists its sources; a figure that cannot be calculated says why "
            "instead of showing zero. The Monthly reports tab fits on one A4 page."
        ),
        "essayez": "click the MTBF to see its source work orders.",
    },
    "parametres": {
        "titre": "Settings",
        "texte": (
            "The settings shared by every workstation: company name, deadlines by priority, preventive and "
            "suggestion thresholds, the “repair or replace” threshold, failure codes. And the database tools: "
            "backups and restore, database check, import from Excel or CSV, ZIP export of the 24 files."
        ),
        "essayez": "the deadlines by priority.",
    },
    "import": {
        "titre": "Import data",
        "texte": (
            "Bring in your lists and your history from Excel, OpenDocument or CSV: choose the file, match the "
            "columns, read the preview and the errors before confirming. An import is checked before anything "
            "is written and can be undone afterwards."
        ),
        "essayez": "the list of file templates.",
    },
    "controle": {
        "titre": "Database check",
        "texte": (
            "Prévo reads through the whole database and lists what is wrong: broken references, duplicates, "
            "values in the wrong format. Nothing is corrected without you."
        ),
        "essayez": "run the check.",
    },
    "poste": {
        "titre": "This workstation",
        "texte": (
            "Settings for this browser only: workstation name and profile, AI assistant (provider, address, key, "
            "connection test), voice dictation, dark or light theme, and the on-screen help you are reading. "
            "Nothing here changes the other workstations."
        ),
        "essayez": "switch profile to see a technician's screens.",
    },
    "wiki": {
        "titre": "Maintenance wiki",
        "texte": (
            "The workshop's encyclopaedia: one page per machine, breakdown, item, technician, job and "
            "know-how. The facts are calculated from the jobs; the short texts (“In brief”, “Tips”, know-how) "
            "come from the job reports and the tips, and every sentence points to the work orders it is based "
            "on."
        ),
        "essayez": "search for “leak”.",
    },
    "wiki-liste": {
        "titre": "Maintenance wiki",
        "texte": (
            "The workshop's encyclopaedia: one page per machine, breakdown, item, technician, job and "
            "know-how. The facts are calculated from the jobs; the short texts (“In brief”, “Tips”, know-how) "
            "come from the job reports and the tips, and every sentence points to the work orders it is based "
            "on."
        ),
        "essayez": "search for “leak”.",
    },
    "wiki-page": {
        "titre": "Wiki page",
        "profils": {
            "technicien": {
                "texte": (
                    "Everything the workshop knows about this machine, this breakdown or this task: the record "
                    "and the isolation procedure first, then the breakdowns, jobs and parts. The small numbers "
                    "lead to the work orders cited; “Pages linking here” shows the links."
                ),
                "essayez": "click a small number.",
            },
            "responsable": {
                "texte": (
                    "Everything the workshop knows about this machine, this breakdown or this task: the record "
                    "and the isolation procedure first, then the breakdowns, jobs and parts. The small numbers "
                    "lead to the work orders cited; “Pages linking here” shows the links."
                ),
                "essayez": "click a small number.",
            },
            "demandeur": {
                "texte": (
                    "Everything the workshop knows about this machine, this breakdown or this task: the record "
                    "and the isolation procedure first, then the breakdowns, jobs and parts. The small numbers "
                    "give the date of the job cited."
                ),
                "essayez": "search for your machine.",
            },
        },
    },
    "wiki-ecrire": {
        "titre": "Write in the wiki",
        "texte": (
            "The manager corrects a text or creates a know-how page by hand. The change is entered in the log, "
            "with its author and date."
        ),
        "essayez": "correct a sentence and save.",
    },
    "wiki-journal": {
        "titre": "Wiki log",
        "texte": (
            "Closed work orders wait here to enter the wiki. “Process the queue” has the AI assistant read "
            "them and propose texts; Prévo checks them, then the manager validates, declines or sends back "
            "each proposal to be redone. Contradictions are settled here too."
        ),
        "essayez": "open a proposal and see what it changes.",
        "demo": "In this demo, the AI assistant is switched off: look at the proposals already prepared.",
    },
}


ENTETE_AIDE_EN = (
    "'use strict';\n"
    "// Aide longue de Prévo en anglais britannique, en-GB (clés aide.*), dans un fichier à part par langue (contrat du\n"
    "// Lot 2 ; chantier multilingue, Lot 3, T277). Une clé aide.* absente de la langue active est prise dans le fichier\n"
    "// français, sans avertissement (js/i18n.js). Clés triées, une par ligne, chaînes entre apostrophes simples,\n"
    "// échappements gardés (jamais d'espace insécable écrit en clair : \\u00a0, \\u202f). Vocabulaire :\n"
    "// docs/GLOSSAIRE.md.\n"
    "// Un bloc par outil, que chacun réécrit (ne pas retoucher à la main) : « acces » (aide de l'accès et de\n"
    "// l'installation, outils/generer_acces_textes.py, clés aide.acces.*) ; « aide » (aide à l'écran,\n"
    "// outils/generer_aide_ecrans.py, clés aide.ecran.*). La source de ces textes anglais est dans ces deux outils, à\n"
    "// côté du français.\n"
    "\n"
)
ENTETES = {"fr": ENTETE_AIDE, "en": ENTETE_AIDE_EN}


# ---------------------------------------------------------------------------------------------------------
# Écriture en JavaScript (partagé avec outils/generer_acces_textes.py)
# ---------------------------------------------------------------------------------------------------------
RE_NOM = re.compile(r"^[A-Za-z_$][\w$]*$")


def chaine_js(texte):
    """Corps d'une chaîne JavaScript entre apostrophes : \\, ', sauts de ligne et caractères invisibles échappés."""
    res = []
    for car in texte:
        if car == "\\":
            res.append("\\\\")
        elif car == "'":
            res.append("\\'")
        elif car == "\n":
            res.append("\\n")
        elif ord(car) < 0x20 or (car != " " and unicodedata.category(car) in ("Zs", "Zl", "Zp", "Cf", "Cc")):
            res.append("\\u%04x" % ord(car))
        else:
            res.append(car)
    return "".join(res)


def valeur_js(valeur):
    """Littéral JavaScript d'une valeur qui n'est pas un texte affiché (booléen, nombre, code)."""
    if isinstance(valeur, bool):
        return "true" if valeur else "false"
    if isinstance(valeur, int):
        return str(valeur)
    return "'%s'" % chaine_js(valeur)


def nom_js(nom):
    return nom if RE_NOM.match(nom) else json.dumps(nom)


def accesseur(nom, cle):
    """Propriété lue au moment de l'affichage : le texte de la clé dans la langue active."""
    return "get %s() { return I18n.t('%s'); }," % (nom_js(nom), cle)


def texte_aide(actuel, section, entrees, langue="fr"):
    """Contenu de js/i18n/aide/<langue>.js où le bloc `section` porte `entrees` ({clé: valeur au format du dictionnaire}),
    les autres blocs gardés tels quels, tous triés par nom après l'en-tête."""
    blocs = {m.group(1): m.group(0).rstrip("\n") + "\n" for m in ext.RE_BLOC.finditer(actuel or "")}
    blocs[section] = ext.ecrire_bloc(section, langue, entrees)
    return ENTETES[langue] + "\n".join(blocs[nom] for nom in sorted(blocs))


def ecrire_aide(racine, section, entrees, langue="fr"):
    chemin = Path(racine) / FICHIERS[langue]
    actuel = chemin.read_bytes().decode("utf-8") if chemin.is_file() else ""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(texte_aide(actuel, section, entrees, langue).encode("utf-8"))


# ---------------------------------------------------------------------------------------------------------
# L'aide à l'écran
# ---------------------------------------------------------------------------------------------------------

def cle_ecran(id_ecran):
    return "aide.ecran." + id_ecran.replace("-", "_")


def entrees(langue="fr"):
    """{clé: valeur au format du dictionnaire} du bloc « aide » de js/i18n/aide/<langue>.js."""
    res = {}
    for id_ecran, entree in (ECRANS_EN if langue == "en" else ECRANS).items():
        base = cle_ecran(id_ecran)
        for champ, valeur in entree.items():
            if champ == "profils":
                for profil, variante in valeur.items():
                    for nom, texte in variante.items():
                        res["%s.%s.%s" % (base, profil, nom)] = chaine_js(texte)
            elif champ != "ancre":
                res["%s.%s" % (base, champ)] = chaine_js(valeur)
    return res


def bloc(langue="fr"):
    return ext.ecrire_bloc(SECTION, langue, entrees(langue))


def contenu():
    """Texte de js/modules/aide-ecrans-textes.js."""
    lignes = [
        "'use strict';",
        "// AideEcransTextes : textes de l'aide à l'écran (encart de la première visite), validés par Nicolas le 2026-10-25.",
        "// Produit par outils/generer_aide_ecrans.py (source : AIDE-ECRANS.md § 2, dossier de conception du site) : ne pas",
        "// retoucher à la main. Une entrée par identifiant d'écran (App.ecran) : titre, ancre du guide, texte et geste",
        "// « Essayez », ou une variante par profil ; « demo » = phrase ajoutée dans la version web. Un écran sans entrée",
        "// prend celle de son parent ; À propos n'en a pas. Les textes sont dans js/i18n/aide/<langue>.js (clés",
        "// aide.ecran.*) : chaque accesseur les lit dans la langue active au moment de l'affichage (repli français sans",
        "// avertissement, js/i18n.js).",
        "",
        "const AideEcransTextes = {",
    ]
    for id_ecran, entree in ECRANS.items():
        base = cle_ecran(id_ecran)
        lignes.append("  %s: {" % nom_js(id_ecran))
        for champ, valeur in entree.items():
            if champ == "ancre":
                lignes.append("    ancre: %s," % valeur_js(valeur))
            elif champ == "profils":
                lignes.append("    profils: {")
                for profil, variante in valeur.items():
                    lignes.append("      %s: {" % nom_js(profil))
                    lignes.extend("        " + accesseur(nom, "%s.%s.%s" % (base, profil, nom)) for nom in variante)
                    lignes.append("      },")
                lignes.append("    },")
            else:
                lignes.append("    " + accesseur(champ, "%s.%s" % (base, champ)))
        lignes.append("  },")
    lignes.append("};")
    return "\n".join(lignes) + "\n"


def ecrire(racine=RACINE):
    (Path(racine) / MODULE).write_bytes(contenu().encode("utf-8"))
    for langue in FICHIERS:
        ecrire_aide(racine, SECTION, entrees(langue), langue)


def main():
    ecrire()
    print("Écrit : %s et le bloc « %s » de %s" % (MODULE, SECTION, " et ".join(FICHIERS.values())))


if __name__ == "__main__":
    sys.exit(main())
