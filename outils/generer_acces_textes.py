#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Produit les textes d'aide de l'accès et de l'installation, en une seule source (lot 7, D131, CS124, CS130 ;
ARCHITECTURE.md §22.2 et §22.10) : js/modules/acces-textes.js (objet AccesTextes, sans aucun texte : chaque texte est
un accesseur qui le lit par I18n.t dans la langue active) et le bloc « acces » de js/i18n/aide/fr.js et de js/i18n/aide/en.js (les
textes français et anglais, clés aide.acces.*), un fichier d'aide par langue comme l'aide à l'écran (contrat du
Lot 2, T247 ; l'anglais : T277, D158 ; écriture commune : outils/generer_aide_ecrans.py).

- « options » : le texte du « ? » de chaque clé de prevo.config.json, repris tel quel de CLES_CONFIGURATION de
  serveur.py (le même texte sert à « serveur.py --aide », à l'assistant, à Paramètres et au guide) ;
- « choix » : pour chaque choix de l'assistant (étude ETUDE-ACCES §5, validée par Nicolas le 2026-10-25), qui est
  concerné, ce que ça change, pourquoi, et le conseil selon la situation (seul, équipe, informaticien) ;
- SITUATIONS_EN, CHOIX_EN, OPTIONS_EN : l'anglais de ces textes, même structure, dans cet outil (serveur.py ne porte
  que le français ; OPTIONS_EN a les mêmes clés que CLES_CONFIGURATION).

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
from generer_aide_ecrans import (AIDE, FICHIERS, accesseur, chaine_js, ecrire_aide, nom_js, texte_aide,  # noqa: E402
                                 valeur_js)

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


# Anglais britannique de ces textes (chantier multilingue, Lot 3, T277 ; D158) : même structure et mêmes clés que
# SITUATIONS, CHOIX et CLES_CONFIGURATION (serveur.py, qui ne porte que le français). Vocabulaire : docs/GLOSSAIRE.md.
SITUATIONS_EN = {
    "seul": "Just me",
    "equipe": "A small team",
    "informaticien": "I am the company's IT person",
}

CHOIX_EN = {
    "installation": {
        "titre": "Install on this PC or on a server?",
        "qui": "Whoever installs it. A “server” is simply a computer that stays switched on and that nobody uses "
               "for anything else (mini PC, Raspberry Pi, company server).",
        "change": "On your desktop PC: nothing more to buy, but Prévo stops when the PC is switched off or goes to "
                  "sleep. On a server: Prévo is always there.",
        "pourquoi": "Phones and colleagues can only reach Prévo while the machine that hosts it is switched on.",
        "conseil": {
            "seul": "Your PC is enough; Prévo will offer to stop it going to sleep.",
            "equipe": "A mini PC or a Raspberry Pi that stays switched on is the least trouble.",
            "informaticien": "Your server.",
        },
    },
    "mot_de_passe": {
        "titre": "Password or not?",
        "qui": "Everyone who will open Prévo.",
        "change": "Without a password, Prévo can only be reached from this PC (no phone, no colleague). With one, "
                  "each person has their own account and role; requesters can have just a device enrolled by QR code.",
        "pourquoi": "As soon as another device can reach Prévo, anyone on the same network could too: read the job "
                    "reports, delete work orders, restore an old backup. The password is not a formality, it is "
                    "the door.",
        "conseil": {
            "seul": "Alone on this PC: not needed. As soon as you want your phone: compulsory.",
            "equipe": "Compulsory: Prévo does not offer the alternative.",
            "informaticien": "Compulsory, for everyone, requesters included.",
        },
    },
    "etiquettes": {
        "titre": "QR labels or not?",
        "qui": "The requesters, who scan them, and whoever prints them and sticks them on.",
        "change": "A QR code on each machine opens its record and “Report a problem” without any searching. The "
                  "label contains Prévo's address: if it changes, the label no longer leads anywhere.",
        "pourquoi": "Requests arrive already filled in (right machine, photo); without a label, they are made by "
                    "searching for the name.",
        "conseil": {
            "seul": "Pointless as long as you are the only one reporting problems.",
            "equipe": "Yes, after reserving the PC's address in the router (the guide shows how).",
            "informaticien": "Yes, using the server's name on the company network.",
        },
    },
    "exterieur": {
        "titre": "Access from outside or not?",
        "qui": "People on call or travelling.",
        "change": "With: your phones reach Prévo from anywhere, through a private network (Tailscale, or the "
                  "company VPN). Without: Prévo can only be reached on the workshop Wi-Fi.",
        "pourquoi": "Prévo never opens your router to the Internet: a private network links your devices to each "
                    "other, encrypted, without exposing anything. Every phone that goes out needs the private "
                    "network's app.",
        "conseil": {
            "seul": "Yes if you want to check or close work orders from home.",
            "equipe": "Yes for maintenance, no for requesters.",
            "informaticien": "The company VPN.",
        },
    },
    "demarrage": {
        "titre": "Start with the PC?",
        "qui": "Whoever would otherwise have to remember to start Prévo every morning; everyone who is waiting "
               "for it to respond.",
        "change": "Yes: Prévo starts before anyone even signs in, with no window; you stop it from Settings. "
                  "No: a shortcut on the desktop, and a window that must not be closed.",
        "pourquoi": "A phone scanning a label at 7 a.m. must not land on “server unreachable”.",
        "conseil": {
            "seul": "Your choice if Prévo is only used on this PC; yes as soon as a phone is planned.",
            "equipe": "Yes.",
            "informaticien": "Yes, or the company's service tool.",
        },
    },
    "veille": {
        "titre": "Prevent sleep?",
        "qui": "The PC that hosts Prévo.",
        "change": "On mains power, the PC no longer goes to sleep (the screen still does). Consumption: a few tens "
                  "of watts, continuously.",
        "pourquoi": "While asleep, the PC answers nobody; wake-on-LAN is not reliable on a desktop PC.",
        "conseil": {
            "seul": "Yes if phones need to reach Prévo; no if Prévo is only used on this PC.",
            "equipe": "Yes.",
            "informaticien": "Not applicable on a server.",
        },
    },
    "certificat": {
        "titre": "Automatic certificate, through the private network, or your own?",
        "qui": "Every device that opens Prévo.",
        "change": "Automatic: Prévo makes a certificate for the workshop; each phone must “trust the workshop PC” "
                  "once (QR code, two minutes, guided step by step). Private network: certificate recognised "
                  "automatically, nothing to install, but only through the private network's address. Your own: two "
                  "PEM files.",
        "pourquoi": "Without https, the phone's browser refuses the camera (scanning in Prévo) and the microphone "
                    "(dictation), and the password would travel in clear over the Wi-Fi.",
        "conseil": {
            "seul": "The private network if you use Tailscale; otherwise automatic.",
            "equipe": "Automatic.",
            "informaticien": "Your own, or your reverse proxy.",
        },
    },
    "sauvegardes": {
        "titre": "Where should backups be copied?",
        "qui": "The manager.",
        "change": "Every night, Prévo copies the day's backup into the chosen folder and keeps the last 30.",
        "pourquoi": "The daily backups are on the same disk as the data: if the disk fails, everything goes with it.",
        "conseil": {
            "seul": "A USB stick left plugged in, a NAS or a OneDrive or Drive folder: any of them is better than "
                    "nothing.",
            "equipe": "A NAS or a synchronised folder.",
            "informaticien": "The company's backup, or a folder that it covers.",
        },
    },
    "ia": {
        "titre": "Online AI assistant?",
        "qui": "The manager, and the people whose job reports go to the provider.",
        "change": "The provider's address and the key are set on this PC, once for all workstations; there is no "
                  "longer any key on the phones.",
        "pourquoi": "The key no longer travels over the network, and the decision can no longer be bypassed from a "
                    "workstation.",
        "conseil": {
            "seul": "Leave it switched off until you need it.",
            "equipe": "Leave it switched off until you need it.",
            "informaticien": "According to the company's policy on employee data (see the GDPR section of the guide).",
        },
    },
}

OPTIONS_EN = {
    "certificat": "Server https certificate (PEM file), with its key.",
    "certificat_auto": "Certificate made by Prévo for the workshop, to be trusted once on each device.",
    "cle": "Private key of the certificate (PEM file).",
    "comptes": "Sign-in required: each person has an account, or an enrolled device for requesters.",
    "copie_sauvegardes": "Folder where the day's backup is copied each night (USB stick, NAS, synchronised folder); "
                         "empty: no copy.",
    "demandeurs_avec_compte": "No: a requester gives their name on a device enrolled by QR code. Yes: each requester "
                              "has a password.",
    "demarrage": "Prévo starts with the PC (systeme), when a user signs in (session), or by hand (aucun).",
    "ecoute": "Listening address: 127.0.0.1 (this PC only) or 0.0.0.0 (the network).",
    "ia_cle": "Key of the AI service, kept on this PC, never sent to browsers. The PREVO_IA_CLE environment variable "
              "takes precedence; never on the command line.",
    "ia_en_ligne": "Allow an online AI service: the texts sent go to this provider.",
    "ia_fournisseur": "Type of AI service: ollama (Ollama) or openai (any OpenAI-compatible API: LM Studio, "
                      "Mistral…).",
    "ia_url": "Address of the AI service that every workstation uses. Set here only, never on a phone.",
    "invitation_heures": "How long a device invitation stays valid (1 to 168 hours).",
    "mandataire": "Prévo is behind a reverse proxy (tailscale serve, Caddy, nginx, IIS) that provides https: the "
                  "X-Forwarded-Proto and X-Forwarded-Host headers coming from this PC are trusted.",
    "noms": "Names by which this PC is called, in addition to its address and its Windows name (Tailscale name, "
            "company network name). An unknown name is refused, for security.",
    "port_http": "Port of the application on this PC and of the entry point on the network. Changing the port makes "
                 "printed labels obsolete.",
    "port_https": "Port of the application over https on the network.",
    "portee": "Where Prévo can be opened from: this PC only, the workshop Wi-Fi, or also outside the workshop. "
              "Beyond this PC, a password and https are compulsory.",
    "quota_documents_mo": "Maximum space for attached documents, in megabytes.",
    "session_heures": "After this long without activity, you have to sign in again.",
    "session_longue_jours": "How long “stay signed in on this device” lasts.",
    "veille_desactivee": "The PC no longer goes to sleep when it is on mains power.",
}


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_textes", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def donnees(langue="fr"):
    """Les textes d'une langue, sous la forme d'AccesTextes : { situations, choix, options: { cle: { aide, defaut,
    genre } } } (le français des options vient de serveur.py, l'anglais de OPTIONS_EN)."""
    serveur = charger_serveur()
    options = {cle: {"aide": OPTIONS_EN[cle] if langue == "en" else aide, "defaut": defaut, "genre": genre}
               for cle, genre, defaut, aide in serveur.CLES_CONFIGURATION}
    if langue == "en":
        return {"situations": SITUATIONS_EN, "choix": CHOIX_EN, "options": options}
    return {"situations": SITUATIONS, "choix": CHOIX, "options": options}


def entrees(textes=None, langue="fr"):
    """{clé: valeur au format du dictionnaire} du bloc « acces » de js/i18n/aide/<langue>.js."""
    textes = textes or donnees(langue)
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


def bloc(langue="fr"):
    return ext.ecrire_bloc(SECTION, langue, entrees(langue=langue))


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
    for langue in FICHIERS:
        ecrire_aide(racine, SECTION, entrees(langue=langue), langue)


def main():
    ecrire()
    print("Écrit : %s et le bloc « %s » de %s" % (MODULE, SECTION, " et ".join(FICHIERS.values())))


if __name__ == "__main__":
    sys.exit(main())
