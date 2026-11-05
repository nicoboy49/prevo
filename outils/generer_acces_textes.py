#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Produit les textes d'aide de l'accès et de l'installation, en une seule source (lot 7, D131, CS124, CS130 ;
ARCHITECTURE.md §22.2 et §22.10) : js/modules/acces-textes.js (objet AccesTextes, sans aucun texte : chaque texte est
un accesseur qui le lit par I18n.t dans la langue active) et le bloc « acces » de js/i18n/aide/fr.js (les textes
français, clés aide.acces.*), un fichier d'aide par langue comme l'aide à l'écran (contrat du Lot 2, T247 ; écriture
commune : outils/generer_aide_ecrans.py).

- « options » : le texte du « ? » de chaque clé de prevo.config.json, repris tel quel de CLES_CONFIGURATION de
  serveur.py (le même texte sert à « serveur.py --aide », à l'assistant, à Paramètres et au guide) ;
- « choix » : pour chaque choix de l'assistant (étude ETUDE-ACCES §5, validée par Nicolas le 2026-10-25), qui est
  concerné, ce que ça change, pourquoi, et le conseil selon la situation (seul, équipe, informaticien).

Lancer depuis la racine du dépôt, après toute modification d'un texte :
    py outils/generer_acces_textes.py
tests/test_acces_textes.py vérifie que les deux fichiers sont à jour (un second passage ne change aucun octet).
"""
import importlib.util
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
if str(ICI) not in sys.path:
    sys.path.insert(0, str(ICI))
import extraire_textes as ext  # noqa: E402
from generer_aide_ecrans import AIDE, accesseur, chaine_js, ecrire_aide, nom_js, texte_aide, valeur_js  # noqa: E402

RACINE = ICI.parent
MODULE = "js/modules/acces-textes.js"
CIBLE = RACINE / MODULE
SECTION = "acces"

SITUATIONS = {
    "seul": "Moi seul",
    "equipe": "Une petite équipe",
    "informaticien": "Je suis l'informaticien de l'entreprise",
}

CHOIX = {
    "installation": {
        "titre": "Installer sur ce PC ou sur un serveur ?",
        "qui": "Celui qui installe. Un « serveur » est simplement un ordinateur qui reste allumé et que personne "
               "n'utilise pour autre chose (mini-PC, Raspberry Pi, serveur de l'entreprise).",
        "change": "Sur votre PC de bureau : rien de plus à acheter, mais Prévo s'arrête quand le PC s'éteint ou se met "
                  "en veille. Sur un serveur : Prévo est toujours là.",
        "pourquoi": "Les téléphones et les collègues joignent Prévo seulement quand la machine qui l'héberge est allumée.",
        "conseil": {
            "seul": "Votre PC suffit ; Prévo vous proposera de l'empêcher de se mettre en veille.",
            "equipe": "Un mini-PC ou un Raspberry Pi qui reste allumé est le plus tranquille.",
            "informaticien": "Votre serveur.",
        },
    },
    "mot_de_passe": {
        "titre": "Mot de passe ou pas ?",
        "qui": "Tous ceux qui ouvriront Prévo.",
        "change": "Sans mot de passe, Prévo n'est joignable que sur ce PC (pas de téléphone, pas de collègue). Avec, "
                  "chaque personne a son compte et son rôle ; les demandeurs peuvent n'avoir qu'un appareil enrôlé par QR.",
        "pourquoi": "Dès qu'un autre appareil peut joindre Prévo, n'importe qui sur le même réseau le pourrait aussi : lire "
                    "les comptes rendus, effacer des ordres de travail, restaurer une vieille sauvegarde. Le mot de passe "
                    "n'est pas une formalité, c'est la porte.",
        "conseil": {
            "seul": "Seul sur ce PC : pas besoin. Dès que vous voulez votre téléphone : obligatoire.",
            "equipe": "Obligatoire : Prévo ne propose pas l'inverse.",
            "informaticien": "Obligatoire, pour tout le monde, demandeurs compris.",
        },
    },
    "etiquettes": {
        "titre": "Étiquettes QR ou pas ?",
        "qui": "Les demandeurs, qui les scannent, et celui qui les imprime et les colle.",
        "change": "Un QR sur chaque machine ouvre sa fiche et « Signaler un problème » sans chercher. L'étiquette contient "
                  "l'adresse de Prévo : si elle change, l'étiquette ne mène plus nulle part.",
        "pourquoi": "Les demandes arrivent déjà renseignées (bonne machine, photo) ; sans étiquette, elles se font par "
                    "recherche du nom.",
        "conseil": {
            "seul": "Inutile tant que vous êtes le seul à déclarer.",
            "equipe": "Oui, après avoir réservé l'adresse du PC dans la box (le guide montre comment).",
            "informaticien": "Oui, avec le nom du serveur dans le réseau de l'entreprise.",
        },
    },
    "exterieur": {
        "titre": "Accès depuis l'extérieur ou pas ?",
        "qui": "Les personnes en astreinte ou en déplacement.",
        "change": "Avec : vos téléphones joignent Prévo partout, par un réseau privé (Tailscale, ou le VPN de "
                  "l'entreprise). Sans : Prévo n'est joignable que sur le Wi-Fi de l'atelier.",
        "pourquoi": "Prévo n'ouvre jamais votre box à Internet : un réseau privé relie vos appareils entre eux, chiffrés, "
                    "sans rien exposer. Il faut l'application du réseau privé sur chaque téléphone qui sort.",
        "conseil": {
            "seul": "Oui si vous voulez consulter ou clore depuis chez vous.",
            "equipe": "Oui pour la maintenance, non pour les demandeurs.",
            "informaticien": "Le VPN de l'entreprise.",
        },
    },
    "demarrage": {
        "titre": "Démarrer avec le PC ?",
        "qui": "Celui qui, sinon, devrait penser à lancer Prévo chaque matin ; tous ceux qui attendent qu'il réponde.",
        "change": "Oui : Prévo démarre avant même qu'on ouvre une session, sans fenêtre ; on l'arrête depuis Paramètres. "
                  "Non : un raccourci sur le bureau, et une fenêtre à ne pas fermer.",
        "pourquoi": "Un téléphone qui scanne une étiquette à 7 h du matin ne doit pas tomber sur « serveur injoignable ».",
        "conseil": {
            "seul": "Au choix si Prévo ne sert que sur ce PC ; oui dès qu'un téléphone est prévu.",
            "equipe": "Oui.",
            "informaticien": "Oui, ou l'outil de service de l'entreprise.",
        },
    },
    "veille": {
        "titre": "Empêcher la veille ?",
        "qui": "Le PC qui héberge Prévo.",
        "change": "Sur secteur, le PC ne se met plus en veille (l'écran, si). Consommation : quelques dizaines de watts en "
                  "continu.",
        "pourquoi": "En veille, le PC ne répond à personne ; le réveil par le réseau n'est pas fiable sur un PC de bureau.",
        "conseil": {
            "seul": "Oui si des téléphones doivent joindre Prévo ; non si Prévo ne sert que sur ce PC.",
            "equipe": "Oui.",
            "informaticien": "Sans objet sur un serveur.",
        },
    },
    "certificat": {
        "titre": "Certificat automatique, par le réseau privé, ou le vôtre ?",
        "qui": "Chaque appareil qui ouvre Prévo.",
        "change": "Automatique : Prévo fabrique un certificat pour l'atelier ; chaque téléphone doit « faire confiance au "
                  "PC atelier » une fois (QR, deux minutes, guidé pas à pas). Réseau privé : certificat reconnu d'office, "
                  "rien à installer, mais seulement par l'adresse du réseau privé. Le vôtre : deux fichiers PEM.",
        "pourquoi": "Sans https, le navigateur du téléphone refuse la caméra (scan dans Prévo) et le micro (dictée), et le "
                    "mot de passe circulerait en clair sur le Wi-Fi.",
        "conseil": {
            "seul": "Le réseau privé si vous utilisez Tailscale ; sinon automatique.",
            "equipe": "Automatique.",
            "informaticien": "Le vôtre, ou votre mandataire inverse.",
        },
    },
    "sauvegardes": {
        "titre": "Où copier les sauvegardes ?",
        "qui": "Le responsable.",
        "change": "Chaque nuit, Prévo copie la sauvegarde du jour dans le dossier choisi et garde les 30 dernières.",
        "pourquoi": "Les sauvegardes quotidiennes sont sur le même disque que les données : un disque qui lâche emporte tout.",
        "conseil": {
            "seul": "Une clé USB laissée branchée, un NAS ou un dossier OneDrive ou Drive : n'importe lequel vaut mieux que rien.",
            "equipe": "Un NAS ou un dossier synchronisé.",
            "informaticien": "La sauvegarde de l'entreprise, ou un dossier qu'elle couvre.",
        },
    },
    "ia": {
        "titre": "Assistant IA en ligne ?",
        "qui": "Le responsable, et les personnes dont les comptes rendus partent chez le fournisseur.",
        "change": "L'adresse du fournisseur et la clé sont réglées sur ce PC, une fois pour tous les postes ; plus aucune "
                  "clé sur les téléphones.",
        "pourquoi": "La clé ne circule plus sur le réseau, et la décision ne se contourne plus depuis un poste.",
        "conseil": {
            "seul": "Laissez-le désactivé tant que vous n'en avez pas besoin.",
            "equipe": "Laissez-le désactivé tant que vous n'en avez pas besoin.",
            "informaticien": "Selon la politique de l'entreprise sur les données des salariés (voir la rubrique RGPD du guide).",
        },
    },
}


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_textes", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def donnees():
    """Les textes français, sous la forme d'AccesTextes : { situations, choix, options: { cle: { aide, defaut, genre } } }."""
    serveur = charger_serveur()
    options = {cle: {"aide": aide, "defaut": defaut, "genre": genre}
               for cle, genre, defaut, aide in serveur.CLES_CONFIGURATION}
    return {"situations": SITUATIONS, "choix": CHOIX, "options": options}


def entrees(textes=None):
    """{clé: valeur au format du dictionnaire} du bloc « acces » de js/i18n/aide/fr.js."""
    textes = textes or donnees()
    res = {}
    for cle, texte in textes["situations"].items():
        res["aide.acces.situation." + cle] = chaine_js(texte)
    for nom, choix in textes["choix"].items():
        for champ, valeur in choix.items():
            if champ == "conseil":
                for situation, conseil in valeur.items():
                    res["aide.acces.choix.%s.conseil.%s" % (nom, situation)] = chaine_js(conseil)
            else:
                res["aide.acces.choix.%s.%s" % (nom, champ)] = chaine_js(valeur)
    for cle, option in textes["options"].items():
        res["aide.acces.option." + cle] = chaine_js(option["aide"])
    return res


def bloc():
    return ext.ecrire_bloc(SECTION, "fr", entrees())


def contenu():
    """Texte de js/modules/acces-textes.js."""
    textes = donnees()
    lignes = [
        "'use strict';",
        "// AccesTextes : textes d'aide de l'accès et de l'installation, une seule source pour l'assistant, Paramètres,",
        "// Équipe › Accès et le guide (lot 7, CS124, CS130). Produit par outils/generer_acces_textes.py à partir de",
        "// CLES_CONFIGURATION de serveur.py (options) et des textes de l'étude validée (choix) : ne pas retoucher à la main.",
        "// Les textes sont dans js/i18n/aide/<langue>.js (clés aide.acces.*) : chaque accesseur les lit dans la langue",
        "// active au moment de l'affichage (repli français sans avertissement, js/i18n.js).",
        "",
        "const AccesTextes = {",
        "  situations: {",
    ]
    lignes.extend("    " + accesseur(cle, "aide.acces.situation." + cle) for cle in textes["situations"])
    lignes += ["  },", "  choix: {"]
    for nom, choix in textes["choix"].items():
        lignes.append("    %s: {" % nom_js(nom))
        for champ, valeur in choix.items():
            if champ == "conseil":
                lignes.append("      conseil: {")
                lignes.extend("        " + accesseur(situation, "aide.acces.choix.%s.conseil.%s" % (nom, situation))
                              for situation in valeur)
                lignes.append("      },")
            else:
                lignes.append("      " + accesseur(champ, "aide.acces.choix.%s.%s" % (nom, champ)))
        lignes.append("    },")
    lignes += ["  },", "  options: {"]
    for cle, option in textes["options"].items():
        lignes.append("    %s: {" % nom_js(cle))
        lignes.append("      " + accesseur("aide", "aide.acces.option." + cle))
        lignes.append("      defaut: %s," % valeur_js(option["defaut"]))
        lignes.append("      genre: %s," % valeur_js(option["genre"]))
        lignes.append("    },")
    lignes += ["  },", "};"]
    return "\n".join(lignes) + "\n"


def ecrire(racine=RACINE):
    (Path(racine) / MODULE).write_bytes(contenu().encode("utf-8"))
    ecrire_aide(racine, SECTION, entrees())


def main():
    ecrire()
    print("Écrit : %s et le bloc « %s » de %s" % (MODULE, SECTION, AIDE))


if __name__ == "__main__":
    sys.exit(main())
