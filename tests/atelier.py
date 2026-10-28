"""Serveur Prévo en portée « atelier » pour les tests du lot 7 (ARCHITECTURE.md §22.1, §22.6 ; tâche T161).

    with ServeurAtelier() as atelier:
        atelier.adresse_reseau       # '192.168.1.20' : l'adresse réseau de ce PC (le téléphone simulé s'y connecte)
        atelier.url_porte            # 'http://192.168.1.20:<port_http>' : la porte, vue du réseau
        atelier.url_pc               # 'http://127.0.0.1:<port_http>' : le PC serveur lui-même (l'application en http)
        atelier.url_https            # 'https://192.168.1.20:<port_https>' : l'application en https
        atelier.serveur              # le ServeurPrevo de tests/commun.py (dossier, console)
        atelier.contexte_confiance   # ssl.SSLContext qui fait confiance à l'autorité de test
        atelier.rootca               # Path de rootCA.pem (le certificat public de l'autorité)
        atelier.comptes              # identifiant -> mot de passe des trois comptes

Le serveur écoute sur 0.0.0.0 avec des comptes (un responsable existe : sans lui, Prévo se replie sur 127.0.0.1), un
fichier de configuration à « port_https », et un certificat de test fabriqué par le faux mkcert (tests/faux_mkcert.py,
openssl) pour l'adresse réseau du PC, localhost et 127.0.0.1 ; l'autorité (rootCA.pem et sa clé) est dans
donnees/acces/autorite/ de la copie, comme avec le vrai mkcert. Le serveur voit le téléphone simulé comme un client du
réseau (adresse 192.168.x.x), et le PC comme 127.0.0.1 : aucun en-tête de test, aucune sortie du PC, aucune commande
d'administrateur. SkipTest si ce PC n'a pas d'adresse réseau ou si openssl manque.
"""
import http.client
import importlib.util
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

import commun
from commun import RACINE, port_libre

FAUX_MKCERT = RACINE / "tests" / "faux_mkcert.py"
AGENT_TEST = "Navigateur-de-test/1.0"
MOTS_DE_PASSE = {"nicolas.briand": "phrase du responsable 2026", "julien.moreau": "cle a molette et graisse",
                 "lea.martin": "une demande de lea 2026"}
_COMPTES_JSON = None


def charger_serveur(nom="serveur_prevo_atelier"):
    specification = importlib.util.spec_from_file_location(nom, RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def adresse_reseau():
    """Une adresse IPv4 de ce PC qui n'est pas 127.x, ou None."""
    serveur = charger_serveur("serveur_prevo_atelier_adresse")
    adresses = [a for a in serveur.adresses_ip_reseau() if not a.startswith("127.")]
    return adresses[0] if adresses else None


def openssl_present():
    if shutil.which("openssl"):
        return True
    return any(os.path.isfile(chemin) for chemin in (r"C:\Program Files\Git\usr\bin\openssl.exe",
                                                     r"C:\Program Files\Git\mingw64\bin\openssl.exe"))


def comptes_json():
    """comptes.json avec les trois comptes (responsable, technicien, demandeur), calculé une fois (scrypt coûte)."""
    global _COMPTES_JSON
    if _COMPTES_JSON is None:
        serveur = charger_serveur("serveur_prevo_atelier_comptes")
        dossier = Path(tempfile.mkdtemp(prefix="prevo-atelier-comptes-"))
        try:
            config = serveur.Configuration(str(dossier / "donnees"), [])
            serveur.creer_dossiers(config)
            serveur.creer_compte(config, "Nicolas", "Briand", "responsable", MOTS_DE_PASSE["nicolas.briand"])
            serveur.creer_compte(config, "Julien", "Moreau", "technicien", MOTS_DE_PASSE["julien.moreau"],
                                 technicien_id="TEC-0001")
            serveur.creer_compte(config, "Léa", "Martin", "demandeur", MOTS_DE_PASSE["lea.martin"])
            _COMPTES_JSON = (dossier / "donnees" / "acces" / "comptes.json").read_bytes()
        finally:
            shutil.rmtree(dossier, ignore_errors=True)
    return _COMPTES_JSON


def fabriquer_certificat(autorite, certificat, cle, noms):
    """Le faux mkcert (CAROOT = autorite) écrit rootCA.pem, rootCA-key.pem, puis le certificat pour « noms »."""
    environnement = dict(os.environ, CAROOT=str(autorite), PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, str(FAUX_MKCERT), "-cert-file", str(certificat), "-key-file", str(cle)] + list(noms),
                   check=True, capture_output=True, env=environnement, timeout=120)


class ServeurAtelier:
    """serveur.py en portée « atelier » (voir le module). Gestionnaire de contexte ; demarrer() / arreter() sinon."""

    def __init__(self, reglages=None, arguments=None, source=commun.SOURCE_AUTO):
        self.reglages = dict(reglages or {})
        self.arguments = list(arguments or [])
        self.source_demandee = source
        self.adresse_reseau = None
        self.racine = None
        self.serveur = None
        self.rootca = None
        self.contexte_confiance = None
        self.comptes = dict(MOTS_DE_PASSE)

    def __enter__(self):
        self.demarrer()
        return self

    def __exit__(self, type_exception, exception, trace):
        self.arreter()
        return False

    def demarrer(self):
        self.adresse_reseau = adresse_reseau()
        if self.adresse_reseau is None:
            raise unittest.SkipTest("aucune adresse réseau sur ce PC : impossible de simuler un téléphone")
        if not openssl_present():
            raise unittest.SkipTest("openssl introuvable : certificat de test impossible")
        self.racine = Path(tempfile.mkdtemp(prefix="prevo-atelier-"))
        source = self.racine / "source"
        if self.source_demandee == commun.SOURCE_AUTO and commun.DOSSIER_DEMO.is_dir():
            shutil.copytree(commun.DOSSIER_DEMO, source)
        elif self.source_demandee not in (commun.SOURCE_AUTO, None):
            shutil.copytree(self.source_demandee, source)
        else:
            source.mkdir()
        acces = source / "acces"
        acces.mkdir(parents=True, exist_ok=True)
        (acces / "comptes.json").write_bytes(comptes_json())
        # Certificat hors du dossier de données (chemins connus avant la copie) ; l'autorité dans la copie, comme mkcert.
        certificat, cle = self.racine / "certificat.pem", self.racine / "cle.pem"
        fabriquer_certificat(acces / "autorite", certificat, cle, [self.adresse_reseau, "localhost", "127.0.0.1"])
        self.rootca = acces / "autorite" / "rootCA.pem"
        self.contexte_confiance = ssl.create_default_context(cafile=str(self.rootca))
        reglages = {"ecoute": "0.0.0.0", "comptes": True, "port_https": port_libre()}
        reglages.update(self.reglages)
        configuration = self.racine / "prevo.config.json"
        configuration.write_text(json.dumps(reglages, ensure_ascii=False), encoding="utf-8")
        arguments = ["--config", str(configuration), "--certificat", str(certificat), "--cle", str(cle)] + self.arguments
        self.serveur = commun.ServeurPrevo(source=source, arguments=arguments)
        # ServeurPrevo croit l'adresse en https avec --certificat ; ici la porte répond en http sur 127.0.0.1.
        self.serveur.https = False
        try:
            self.serveur.demarrer()
        except BaseException:
            self.arreter()
            raise
        self.port_https = reglages["port_https"]

    def arreter(self):
        if self.serveur is not None:
            self.serveur.arreter()
            self.serveur = None
        if self.racine is not None:
            shutil.rmtree(self.racine, ignore_errors=True)
            self.racine = None

    @property
    def port_http(self):
        return self.serveur.port

    @property
    def url_porte(self):
        return "http://%s:%d" % (self.adresse_reseau, self.port_http)

    @property
    def url_pc(self):
        return "http://127.0.0.1:%d" % self.port_http

    @property
    def url_https(self):
        return "https://%s:%d" % (self.adresse_reseau, self.port_https)

    @property
    def dossier(self):
        return self.serveur.dossier

    def console(self):
        return self.serveur.sortie_console()


# ---------------------------------------------------------------------------
# Requêtes et appareil enrôlé (le chemin réel du lot 7 pour un téléphone, en attendant l'écran de T156)
# ---------------------------------------------------------------------------

class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))

    @property
    def texte(self):
        return self.octets.decode("utf-8", "replace")

    @property
    def cookie(self):
        """« nom=<jeton> » posé par la réponse, ou None."""
        valeur = self.entetes.get("set-cookie")
        return valeur.split(";")[0] if valeur else None


def requete(url, chemin, methode="GET", corps=None, entetes=None, contexte=None, cookie=None):
    """Une requête, une connexion ; `url` : origine (http://… ou https://…, avec son contexte TLS)."""
    morceaux = urlsplit(url)
    entetes = dict(entetes or {})
    entetes.setdefault("User-Agent", AGENT_TEST)
    if cookie:
        entetes["Cookie"] = cookie
    if isinstance(corps, (dict, list)):
        corps = json.dumps(corps).encode("utf-8")
    if morceaux.scheme == "https":
        connexion = http.client.HTTPSConnection(morceaux.hostname, morceaux.port, context=contexte, timeout=30)
    else:
        connexion = http.client.HTTPConnection(morceaux.hostname, morceaux.port, timeout=30)
    try:
        connexion.request(methode, chemin, body=corps, headers=entetes)
        reponse = connexion.getresponse()
        return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
    finally:
        connexion.close()


def connecter(url, identifiant, contexte=None):
    """Ouvre une session pour un des trois comptes ; rend la réponse (cookie « id=… »)."""
    reponse = requete(url, "/api/connexion", "POST", {"identifiant": identifiant, "mot_de_passe": MOTS_DE_PASSE[identifiant],
                                                       "rester": False}, {"X-Prevo": "1"}, contexte)
    assert reponse.statut == 200, reponse.octets
    return reponse


def enroler_appareil(atelier, contexte_navigateur, nom="Karim Benali"):
    """Appareil enrôlé (§22.3, T153) : invitation créée par le responsable (PC), puis POST /api/enroler envoyé depuis
    le contexte Playwright du téléphone (contexte.request partage ses cookies : le cookie « appareil » reste dans
    son navigateur, comme le fera l'écran d'enrôlement de T156). Rend l'invitation."""
    responsable = connecter(atelier.url_pc, "nicolas.briand").cookie
    invitation = requete(atelier.url_pc, "/api/acces/invitations", "POST", {}, {"X-Prevo": "1"}, cookie=responsable).json()
    reponse = contexte_navigateur.request.post(atelier.url_https + "/api/enroler", headers={"X-Prevo": "1"},
                                               data={"invitation": invitation["jeton"], "nom": nom})
    assert reponse.status == 200, reponse.text()
    return invitation


def tables_refusees_au_demandeur():
    serveur = charger_serveur("serveur_prevo_atelier_tables")
    return sorted(set(serveur.TABLES) - set(serveur.TABLES_DU_DEMANDEUR))


def motif_refus_du_demandeur():
    """Chromium note en console.error les 403 des tables qui ne sont pas au demandeur (vues comme absentes par
    stockage-serveur.js) : ce motif, pour CasNavigateur.autoriser_erreur, ne laisse passer que ces refus-là."""
    return re.compile(r"status of 403 .*/api/csv/(?:%s):" % "|".join(tables_refusees_au_demandeur()))
