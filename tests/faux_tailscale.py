"""Faux tailscale pour les tests du lot 7 (CS127, §22.8) : mêmes commandes que le vrai, réponses pilotées par des
variables d'environnement, jamais de réseau ni d'installation.

    faux_tailscale.py version                                  → « 1.80.0 »
    faux_tailscale.py status --json                            → l'état (BackendState, Self.DNSName, Self.KeyExpiry…)
    faux_tailscale.py serve --bg --https=443 http://127.0.0.1:N → note la cible dans FAUX_TAILSCALE_DOSSIER/serve.json
    faux_tailscale.py serve status --json                      → rend ce qui a été noté ({} sinon)
    faux_tailscale.py set --unattended=true                    → note seulement
    faux_tailscale.py up | down | login | logout | install …   → sortie d'erreur et code 1 : un test qui les voit échoue

Variables :
    FAUX_TAILSCALE_ETAT        Running (défaut) | Stopped | absent (toute commande échoue, code 1 : le service manque)
    FAUX_TAILSCALE_NOM         Self.DNSName, point final compris (défaut « prevo.tail1234.ts.net. »)
    FAUX_TAILSCALE_EXPIRATION  Self.KeyExpiry en RFC 3339 UTC ; vide : la clé n'expire pas (champ absent)
    FAUX_TAILSCALE_DOSSIER     dossier de lancements.txt (une ligne par lancement : les tests comptent) et serve.json
    FAUX_TAILSCALE_ATTENTE     secondes d'attente avant de répondre (test du délai)

L'état cite un autre appareil du tailnet (Peer, adresse 100.64.0.9) : /api/info ne doit jamais le laisser passer.
"""
import json
import os
import sys
import time
from pathlib import Path

VERSION = "1.80.0"
ADRESSE_AUTRE_APPAREIL = "100.64.0.9"
COMMANDES_INTERDITES = ("up", "down", "login", "logout", "install", "update")


def dossier():
    chemin = os.environ.get("FAUX_TAILSCALE_DOSSIER")
    if not chemin:
        return None
    dossier_ = Path(chemin)
    dossier_.mkdir(parents=True, exist_ok=True)
    return dossier_


def noter_lancement(arguments):
    dossier_ = dossier()
    if dossier_ is not None:
        with open(dossier_ / "lancements.txt", "a", encoding="utf-8") as journal:
            journal.write(" ".join(arguments) + "\n")


def etat_json(etat, nom, expiration):
    soi = {"ID": "nFAUX1", "HostName": "PC-ATELIER", "DNSName": nom, "OS": "windows", "TailscaleIPs": ["100.64.0.7"],
           "Online": etat == "Running"}
    if expiration:
        soi["KeyExpiry"] = expiration
    return {"Version": VERSION, "BackendState": etat, "Self": soi, "MagicDNSSuffix": "tail1234.ts.net",
            "Peer": {"nodekey:faux": {"HostName": "telephone", "DNSName": "telephone.tail1234.ts.net.",
                                      "TailscaleIPs": [ADRESSE_AUTRE_APPAREIL], "Online": True}}}


def main(arguments):
    noter_lancement(arguments)
    attente = os.environ.get("FAUX_TAILSCALE_ATTENTE")
    if attente:
        time.sleep(float(attente))
    etat = os.environ.get("FAUX_TAILSCALE_ETAT") or "Running"
    nom = os.environ.get("FAUX_TAILSCALE_NOM", "prevo.tail1234.ts.net.")
    expiration = os.environ.get("FAUX_TAILSCALE_EXPIRATION", "")
    if not arguments:
        sys.stderr.write("faux tailscale : commande attendue\n")
        return 1
    if arguments[0] in COMMANDES_INTERDITES:
        sys.stderr.write("faux tailscale : « tailscale %s » ne doit jamais être lancé par Prévo\n" % arguments[0])
        return 1
    if etat == "absent":
        sys.stderr.write("failed to connect to local tailscaled; it doesn't appear to be running\n")
        return 1
    if arguments == ["version"]:
        sys.stdout.write(VERSION + "\n  tailscale commit: faux\n")
        return 0
    if arguments == ["status", "--json"]:
        sys.stdout.write(json.dumps(etat_json(etat, nom, expiration)) + "\n")
        return 0
    if arguments == ["serve", "status", "--json"]:
        dossier_ = dossier()
        fichier = dossier_ / "serve.json" if dossier_ is not None else None
        sys.stdout.write((fichier.read_text(encoding="utf-8") if fichier and fichier.is_file() else "{}") + "\n")
        return 0
    if arguments[:3] == ["serve", "--bg", "--https=443"] and len(arguments) == 4 and arguments[3].startswith("http://"):
        dossier_ = dossier()
        if dossier_ is None:
            sys.stderr.write("faux tailscale : FAUX_TAILSCALE_DOSSIER manquant\n")
            return 1
        hote = nom.rstrip(".") + ":443"
        serve = {"TCP": {"443": {"HTTPS": True}}, "Web": {hote: {"Handlers": {"/": {"Proxy": arguments[3]}}}},
                 "AllowFunnel": {}}
        (dossier_ / "serve.json").write_text(json.dumps(serve), encoding="utf-8")
        sys.stdout.write("Available within your tailnet:\n\nhttps://%s/\n|-- proxy %s\n" % (nom.rstrip("."), arguments[3]))
        return 0
    if arguments == ["set", "--unattended=true"]:
        return 0
    sys.stderr.write("faux tailscale : commande inconnue « %s »\n" % " ".join(arguments))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
