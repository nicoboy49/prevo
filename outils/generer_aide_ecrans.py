#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Produit l'aide à l'écran (encart de la première visite, ARCHITECTURE.md §23) : js/modules/aide-ecrans-textes.js
(objet AideEcransTextes : écrans, ancres du guide, variantes par profil, sans aucun texte) et le bloc « aide » de
js/i18n/aide/fr.js (les textes français, clés aide.ecran.*) : un fichier d'aide par langue (contrat du Lot 2,
décision de Nicolas du 2026-11-05, T247).

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
        "essayez": "le bouton « Générer l'OT » si la gamme est échue.",
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


def texte_aide(actuel, section, entrees):
    """Contenu de js/i18n/aide/fr.js où le bloc `section` porte `entrees` ({clé: valeur au format du dictionnaire}),
    les autres blocs gardés tels quels, tous triés par nom après l'en-tête."""
    blocs = {m.group(1): m.group(0).rstrip("\n") + "\n" for m in ext.RE_BLOC.finditer(actuel or "")}
    blocs[section] = ext.ecrire_bloc(section, "fr", entrees)
    return ENTETE_AIDE + "\n".join(blocs[nom] for nom in sorted(blocs))


def ecrire_aide(racine, section, entrees):
    chemin = Path(racine) / AIDE
    actuel = chemin.read_bytes().decode("utf-8") if chemin.is_file() else ""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(texte_aide(actuel, section, entrees).encode("utf-8"))


# ---------------------------------------------------------------------------------------------------------
# L'aide à l'écran
# ---------------------------------------------------------------------------------------------------------

def cle_ecran(id_ecran):
    return "aide.ecran." + id_ecran.replace("-", "_")


def entrees():
    """{clé: valeur au format du dictionnaire} du bloc « aide » de js/i18n/aide/fr.js."""
    res = {}
    for id_ecran, entree in ECRANS.items():
        base = cle_ecran(id_ecran)
        for champ, valeur in entree.items():
            if champ == "profils":
                for profil, variante in valeur.items():
                    for nom, texte in variante.items():
                        res["%s.%s.%s" % (base, profil, nom)] = chaine_js(texte)
            elif champ != "ancre":
                res["%s.%s" % (base, champ)] = chaine_js(valeur)
    return res


def bloc():
    return ext.ecrire_bloc(SECTION, "fr", entrees())


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
    ecrire_aide(racine, SECTION, entrees())


def main():
    ecrire()
    print("Écrit : %s et le bloc « %s » de %s" % (MODULE, SECTION, AIDE))


if __name__ == "__main__":
    sys.exit(main())
