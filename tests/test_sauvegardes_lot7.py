"""Lot 7 — sauvegardes (ARCHITECTURE.md §22.11 ; D133 ; CS133 ; tâche T175).

Ce qui est vérifié :
    copie externe  faite à la première écriture après 2 h du matin (horloge simulée), pas avant, une fois par jour ; au
                   démarrage du serveur ; la sauvegarde quotidienne la plus récente, acces/ compris, jamais sessions.json,
                   par un dossier temporaire renommé à la fin ; 30 copies gardées, seuls les dossiers nommés AAAA-MM-JJ
                   comptés et supprimés (fichier et dossiers étrangers intacts) ; dossier absent : erreur gardée dans
                   donnees/copie-externe.json et écrite dans journal-serveur.log, jours sans copie comptés par /api/info,
                   jamais le chemin complet ; une copie réussie efface l'erreur ; jamais deux copies à la fois ;
    tester         POST /api/sauvegarde/tester : lignes de chaque table égales à un calcul indépendant, ordre du schéma,
                   fichier vide ou colonne absente signalés, sauvegarde d'un format plus ancien (Excel, Windows-1252,
                   « , ») acceptée, rien d'écrit ; nom refusé 400, sauvegarde absente ou incomplète 404 ;
    plafond        deuxième sauvegarde manuelle dans la minute : 429, Retry-After et message ; sauvegardes à motif jamais
                   limitées ; la minute se lit sur le nom de la dernière (tient après un redémarrage) ;
    purge          au-delà de 60 sauvegardes manuelles, les plus anciennes supprimées ; quotidiennes et « …_avant-… » ni
                   comptées ni touchées ;
    acces/         copié dans les sauvegardes sans sessions.json, jamais restauré par /api/restauration ;
    écrans         bouton « Tester » de Paramètres (mode serveur ; absent en démo et en mode dossier), message du 429 ;
                   avertissement de l'accueil du responsable avec le nombre de jours, rien quand tout va bien.

Trois façons de lancer : serveur.py importé et servi dans ce processus, horloge simulée (config.horloge), pour ce qui
dépend du temps (2 h du matin, jours sans copie, minute du plafond) ; serveur réel (ServeurPrevo de tests/commun.py)
pour le 429, la purge, « Tester » et la copie au démarrage ; navigateur (CasNavigateur) pour les écrans. Aucune sortie
réseau, aucune commande d'administrateur.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_sauvegardes_lot7.py" -v
"""
import csv
import datetime
import hashlib
import http.client
import importlib.util
import json
import re
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import commun
from commun import (CasNavigateur, RACINE, ServeurStatique, attendre_pret, installer_dossier_simule,
                    preregler_profil, url_fichier)

SCRIPT = RACINE / "serveur.py"


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_sauvegardes", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()

BOM = bytes((0xEF, 0xBB, 0xBF))
CRLF = bytes((13, 10))
MINUTE, JOUR = 60, 86400
MESSAGE_PLAFOND = "Une sauvegarde manuelle par minute au plus : réessayez dans %d s."
MOTIF_MANUELLE = re.compile(r"\d{4}-\d{2}-\d{2}_\d{6}")
MOTIF_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
ERREUR_PING_ABSENT = re.compile(r"status of 404.*/api/ping")      # serveur statique : pas de /api/ping
# Fichiers d'accès : octets écrits et comparés tels quels (write_text passerait les fins de ligne en CRLF sous Windows).
COMPTES_JSON = json.dumps({"version": 1, "comptes": [{"identifiant": "nicolas.briand", "role": "responsable",
                                                      "actif": True}]}, indent=2).encode("utf-8")
SESSIONS_JSON = json.dumps({"0" * 64: {"identifiant": "nicolas.briand",
                                       "cree_le": "2026-06-15T08:00:00"}}).encode("utf-8")


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------

def instant(annee, mois, jour, heure=0, minute=0, seconde=0):
    """Secondes d'une heure locale (les noms des sauvegardes sont en heure locale) ; dates loin des changements
    d'heure."""
    return datetime.datetime(annee, mois, jour, heure, minute, seconde).timestamp()


def csv_de(table, *lignes):
    """CSV au format Prévo (BOM, « ; », CRLF) : en-tête du schéma, puis les lignes données (texte)."""
    entete = ";".join(serveur.COLONNES_PAR_TABLE[table]).encode("utf-8")
    return BOM + CRLF.join([entete] + [ligne.encode("utf-8") for ligne in lignes]) + CRLF


def version(octets):
    return hashlib.sha256(octets).hexdigest()[:16]


def compter_lignes(chemin):
    """Calcul indépendant : lignes de données d'un CSV Prévo (en-tête exclu, lignes entièrement vides ignorées)."""
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        lignes = [ligne for ligne in csv.reader(fichier, delimiter=";") if any(cellule.strip() for cellule in ligne)]
    return len(lignes) - 1


def contenu_du_dossier(dossier):
    """{chemin relatif: octets} de tous les fichiers d'un dossier."""
    dossier = Path(dossier)
    return {chemin.relative_to(dossier).as_posix(): chemin.read_bytes()
            for chemin in sorted(dossier.rglob("*")) if chemin.is_file()}


def etat_du_dossier(dossier):
    """{chemin relatif: (taille, date, empreinte)} de tout ce que contient un dossier (dossiers compris)."""
    dossier = Path(dossier)
    etat = {}
    for chemin in sorted(dossier.rglob("*")):
        statistiques = chemin.stat()
        empreinte = hashlib.sha256(chemin.read_bytes()).hexdigest() if chemin.is_file() else "dossier"
        etat[chemin.relative_to(dossier).as_posix()] = (statistiques.st_size, statistiques.st_mtime_ns, empreinte)
    return etat


def copies_datees(dossier):
    """Dossiers d'un dossier de copie dont le nom est une vraie date AAAA-MM-JJ, triés."""
    noms = []
    for chemin in Path(dossier).iterdir():
        if chemin.is_dir() and MOTIF_DATE.fullmatch(chemin.name):
            try:
                datetime.datetime.strptime(chemin.name, "%Y-%m-%d")
            except ValueError:
                continue
            noms.append(chemin.name)
    return sorted(noms)


def manuelles(dossier_sauvegardes):
    return sorted(chemin.name for chemin in Path(dossier_sauvegardes).iterdir()
                  if chemin.is_dir() and MOTIF_MANUELLE.fullmatch(chemin.name))


def attendre(condition, delai=15, message="condition jamais remplie"):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError(message)


class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))


def requete(port, methode, chemin, corps=None, entetes=None):
    """Requête vers un serveur Prévo de 127.0.0.1 (une connexion par requête) ; X-Prevo sur les écritures."""
    entetes = dict(entetes or {})
    if isinstance(corps, (dict, list)):
        corps = json.dumps(corps).encode("utf-8")
    if methode in ("PUT", "POST"):
        corps = corps if corps is not None else b""
        entetes.setdefault("X-Prevo", "1")
        entetes["Content-Length"] = str(len(corps))
    connexion = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        connexion.request(methode, chemin, body=corps, headers=entetes)
        reponse = connexion.getresponse()
        return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
    finally:
        connexion.close()


# ---------------------------------------------------------------------------
# Serveur dans ce processus : horloge simulée
# ---------------------------------------------------------------------------

class ServeurDansLeProcessus:
    """serveur.py importé et servi dans un fil de ce processus ; config.horloge rend self.instant."""

    def __init__(self, dossier_donnees, copie=""):
        self.instant = instant(2026, 6, 15, 1, 30)
        self.config = serveur.Configuration(str(dossier_donnees), [])
        self.config.reglages["copie_sauvegardes"] = str(copie)
        self.config.horloge = lambda: self.instant
        serveur.creer_dossiers(self.config)
        self.http = serveur.ServeurPrevo(("127.0.0.1", 0), self.config)
        self.config.port = self.http.server_address[1]
        self.fil = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.fil.start()

    def requete(self, methode, chemin, corps=None, entetes=None):
        return requete(self.config.port, methode, chemin, corps, entetes)

    def ecrire_parametres(self, nom_entreprise):
        """PUT /api/csv/parametres (version lue sur le disque), comme un poste qui enregistre."""
        chemin = Path(self.config.dossier_donnees) / "parametres.csv"
        attendue = version(chemin.read_bytes()) if chemin.is_file() else "aucune"
        reponse = self.requete("PUT", "/api/csv/parametres", csv_de("parametres", "entreprise_nom;" + nom_entreprise),
                               {"X-Version-Attendue": attendue})
        if reponse.statut != 200:
            raise AssertionError("écriture refusée : %d %r" % (reponse.statut, reponse.octets))
        return reponse

    def attendre_copie(self):
        """Attend la fin de la dernière copie externe lancée (fil gardé dans config.fil_copie_externe)."""
        fil = self.config.fil_copie_externe
        if fil is not None:
            fil.join(timeout=30)
            if fil.is_alive():
                raise AssertionError("copie externe toujours en cours au bout de 30 s")

    def arreter(self):
        self.attendre_copie()
        if self.http is not None:
            self.http.shutdown()
            self.http.server_close()
            self.fil.join(timeout=5)
            self.http = None


class CasDansLeProcessus(unittest.TestCase):
    """Dossier de données neuf (parametres, equipements, acces/ avec comptes et sessions), dossier de copie externe
    vide (« Cle USB/Sauvegardes Prevo »), serveur dans ce processus à horloge simulée, console capturée."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp(prefix="prevo-sauvegardes-"))
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.donnees = self.racine / "donnees"
        self.sauvegardes = self.donnees / "sauvegardes"
        self.copie = self.racine / "Cle USB" / "Sauvegardes Prevo"
        self.copie.mkdir(parents=True)
        (self.donnees / "acces").mkdir(parents=True)
        (self.donnees / "parametres.csv").write_bytes(csv_de("parametres", "entreprise_nom;Atelier test"))
        (self.donnees / "equipements.csv").write_bytes(csv_de("equipements", "EQ-0001;'PO-01;Pompe"))
        (self.donnees / "acces" / "comptes.json").write_bytes(COMPTES_JSON)
        (self.donnees / "acces" / "sessions.json").write_bytes(SESSIONS_JSON)
        (self.donnees / "acces" / "cle.pem").write_bytes(b"-----BEGIN PRIVATE KEY-----\nessai\n")
        self.console = []
        espion = mock.patch.object(serveur, "afficher", side_effect=self.console.append)
        espion.start()
        self.addCleanup(espion.stop)
        self.serveur = ServeurDansLeProcessus(self.donnees, self.copie)
        self.addCleanup(self.serveur.arreter)

    def etat_copie(self):
        return json.loads((self.donnees / "copie-externe.json").read_text(encoding="utf-8"))

    def copie_externe_de_info(self):
        reponse = self.serveur.requete("GET", "/api/info")
        self.assertEqual(reponse.statut, 200, reponse.octets)
        return reponse.json()["copie_externe"]


class TestCopieExterne(CasDansLeProcessus):

    def test_copie_a_la_premiere_ecriture_apres_2_h_et_pas_avant(self):
        s = self.serveur
        s.instant = instant(2026, 6, 15, 1, 30)
        s.ecrire_parametres("Avant 2 h")
        quotidienne = self.sauvegardes / "2026-06-15"
        self.assertTrue(quotidienne.is_dir())                   # sauvegarde du jour faite avant la 1re écriture
        self.assertIsNone(s.config.fil_copie_externe)           # avant 2 h du matin : aucune copie
        self.assertEqual(list(self.copie.iterdir()), [])
        self.assertEqual(self.copie_externe_de_info(), {"derniere_reussie": None, "jours_sans_copie": None,
                                                        "erreur": None})

        s.instant = instant(2026, 6, 15, 2, 0)                  # 2 h pile : la première écriture lance la copie
        s.ecrire_parametres("Après 2 h")
        s.attendre_copie()
        attendu = contenu_du_dossier(quotidienne)
        self.assertEqual(contenu_du_dossier(self.copie / "2026-06-15"), attendu)
        self.assertEqual(attendu["acces/comptes.json"], COMPTES_JSON)
        self.assertNotIn("acces/sessions.json", attendu)
        self.assertNotIn("acces/cle.pem", attendu)              # la clé privée du certificat ne quitte pas le PC
        self.assertIn(b"Atelier test", attendu["parametres.csv"])  # l'état d'avant la première écriture du jour
        self.assertEqual([chemin.name for chemin in self.copie.iterdir()], ["2026-06-15"])   # aucun dossier temporaire
        self.assertEqual(self.etat_copie()["derniere_reussie"], "2026-06-15")
        self.assertIsNone(self.etat_copie()["erreur"])
        self.assertEqual(self.copie_externe_de_info(), {"derniere_reussie": "2026-06-15", "jours_sans_copie": 0,
                                                        "erreur": None})

        premiere = s.config.fil_copie_externe
        s.instant = instant(2026, 6, 15, 15, 0)                 # le même jour : pas de deuxième copie
        s.ecrire_parametres("Après-midi")
        self.assertIs(s.config.fil_copie_externe, premiere)
        s.instant = instant(2026, 6, 16, 1, 59)                 # le lendemain avant 2 h : toujours rien
        s.ecrire_parametres("Nuit")
        self.assertIs(s.config.fil_copie_externe, premiere)
        self.assertEqual(copies_datees(self.copie), ["2026-06-15"])
        s.instant = instant(2026, 6, 16, 7, 45)                 # première écriture après 2 h : copie du jour
        s.ecrire_parametres("Matin")
        s.attendre_copie()
        self.assertEqual(copies_datees(self.copie), ["2026-06-15", "2026-06-16"])
        # La sauvegarde du 16 (faite avant l'écriture de 1 h 59) garde l'état de la veille au soir.
        self.assertIn("Après-midi".encode("utf-8"), (self.copie / "2026-06-16" / "parametres.csv").read_bytes())

    def test_trente_copies_gardees_sans_toucher_le_reste_du_dossier(self):
        s = self.serveur
        (self.copie / "notes.txt").write_bytes(b"a garder")
        (self.copie / "2026-05-02").write_bytes(b"fichier au nom de date")
        (self.copie / "photos").mkdir()
        (self.copie / "photos" / "atelier.jpg").write_bytes(b"jpg")
        (self.copie / "2026-13-45").mkdir()                     # nom de date impossible : pas une copie de Prévo
        premier = datetime.date(2026, 6, 1)
        for numero in range(31):
            jour = premier + datetime.timedelta(days=numero)
            s.instant = instant(jour.year, jour.month, jour.day, 8, 0)
            s.ecrire_parametres("Jour %d" % numero)
            s.attendre_copie()
            copies = copies_datees(self.copie)
            self.assertEqual(len(copies), min(numero + 1, 30), jour)
            self.assertEqual(copies[-1], jour.isoformat())
        self.assertEqual(copies[0], "2026-06-02")               # la 31e copie a supprimé la plus ancienne
        self.assertIn(b"Jour 29", (self.copie / "2026-07-01" / "parametres.csv").read_bytes())
        self.assertEqual((self.copie / "notes.txt").read_bytes(), b"a garder")
        self.assertEqual((self.copie / "2026-05-02").read_bytes(), b"fichier au nom de date")
        self.assertEqual((self.copie / "photos" / "atelier.jpg").read_bytes(), b"jpg")
        self.assertTrue((self.copie / "2026-13-45").is_dir())
        self.assertEqual(sorted(chemin.name for chemin in self.copie.iterdir() if not chemin.name[:1].isdigit()),
                         ["notes.txt", "photos"])               # aucun dossier temporaire laissé

    def test_dossier_absent_erreur_jours_comptes_puis_copie_reussie(self):
        s = self.serveur
        s.instant = instant(2026, 6, 10, 8, 0)
        s.ecrire_parametres("Jour 1")
        s.attendre_copie()
        self.assertEqual(copies_datees(self.copie), ["2026-06-10"])
        debranchee = self.copie.with_name("Sauvegardes debranchees")
        self.copie.rename(debranchee)                           # clé USB retirée
        for jour in (11, 12, 13):
            s.instant = instant(2026, 6, jour, 8, 0)
            s.ecrire_parametres("Jour du %d" % jour)
            s.attendre_copie()
        etat = self.etat_copie()
        self.assertEqual(etat["derniere_reussie"], "2026-06-10")
        self.assertEqual(etat["erreur"], "Dossier de copie « Sauvegardes Prevo » introuvable (clé USB absente ou "
                                         "partage réseau injoignable ?).")
        self.assertEqual(self.copie_externe_de_info(), {"derniere_reussie": "2026-06-10", "jours_sans_copie": 3,
                                                        "erreur": etat["erreur"],
                                                        "erreur_code": "copie.dossier_introuvable",
                                                        "erreur_valeurs": {"nom": "Sauvegardes Prevo"}})
        reponse = self.serveur.requete("GET", "/api/info").octets.decode("utf-8")
        self.assertNotIn("Cle USB", reponse)                    # jamais le chemin complet aux autres postes
        self.assertNotIn(self.racine.name, reponse)
        # Chaque échec est écrit dans journal-serveur.log (local au PC serveur : le chemin y est) et sur la console.
        journal = (self.donnees / "journal-serveur.log").read_text(encoding="utf-8")
        self.assertEqual(journal.count("Copie externe des sauvegardes impossible"), 3)
        self.assertIn("Sauvegardes Prevo", journal)
        self.assertEqual(sum("Copie externe des sauvegardes impossible" in ligne for ligne in self.console), 3)
        # Sans écriture, le compte suit l'horloge du serveur.
        s.instant = instant(2026, 6, 14, 1, 0)
        self.assertEqual(self.copie_externe_de_info()["jours_sans_copie"], 4)
        # Clé rebranchée : la copie suivante réussit et efface l'erreur.
        debranchee.rename(self.copie)
        s.instant = instant(2026, 6, 14, 8, 0)
        s.ecrire_parametres("Jour 5")
        s.attendre_copie()
        self.assertEqual(copies_datees(self.copie), ["2026-06-10", "2026-06-14"])
        self.assertIsNone(self.etat_copie()["erreur"])
        self.assertEqual(self.copie_externe_de_info(), {"derniere_reussie": "2026-06-14", "jours_sans_copie": 0,
                                                        "erreur": None})

    def test_jours_sans_copie_seulement_quand_une_sauvegarde_attend(self):
        s = self.serveur
        s.instant = instant(2026, 6, 5, 8, 0)                   # vendredi : copie faite
        s.ecrire_parametres("Vendredi")
        s.attendre_copie()
        # Un week-end sans aucune écriture : rien de nouveau à copier, aucune alerte le lundi matin.
        s.instant = instant(2026, 6, 8, 6, 30)
        self.assertEqual(self.copie_externe_de_info(), {"derniere_reussie": "2026-06-05", "jours_sans_copie": 0,
                                                        "erreur": None})
        # Une sauvegarde du jour faite avant 2 h attend sa copie : les jours comptent, même sans erreur.
        s.instant = instant(2026, 6, 9, 1, 0)
        s.ecrire_parametres("Mardi, 1 h")
        self.assertEqual(self.copie_externe_de_info()["jours_sans_copie"], 4)
        s.instant = instant(2026, 6, 9, 7, 0)
        s.ecrire_parametres("Mardi matin")
        s.attendre_copie()
        self.assertEqual(self.copie_externe_de_info(), {"derniere_reussie": "2026-06-09", "jours_sans_copie": 0,
                                                        "erreur": None})

    def test_jamais_deux_copies_a_la_fois(self):
        s = self.serveur
        s.instant = instant(2026, 6, 20, 1, 0)
        s.ecrire_parametres("Sauvegarde du jour")               # avant 2 h : sauvegarde du jour, pas de copie
        vraie_copie = serveur.copier_vers_l_exterieur
        commencee, liberee = threading.Event(), threading.Event()

        def copie_lente(config, cible):
            commencee.set()
            liberee.wait(10)
            return vraie_copie(config, cible)

        with mock.patch.object(serveur, "copier_vers_l_exterieur", side_effect=copie_lente) as espion:
            premiere = serveur.lancer_copie_externe(s.config)
            self.assertTrue(commencee.wait(10))
            self.assertIsNone(serveur.lancer_copie_externe(s.config))      # une copie est en cours
            self.assertIsNone(serveur.faire_copie_externe(s.config))
            # Écriture après 2 h pendant la copie : rien n'est lancé, et le jour n'est pas marqué (réessayé ensuite).
            s.instant = instant(2026, 6, 20, 2, 30)
            s.ecrire_parametres("Pendant la copie")
            self.assertIs(s.config.fil_copie_externe, premiere)
            self.assertIsNone(s.config.copie_externe_jour)
            liberee.set()
            premiere.join(10)
            self.assertEqual(espion.call_count, 1)
        self.assertEqual(copies_datees(self.copie), ["2026-06-20"])
        shutil.rmtree(self.copie / "2026-06-20")
        s.instant = instant(2026, 6, 20, 2, 31)                 # écriture suivante : la copie due part enfin
        s.ecrire_parametres("Après la copie")
        self.assertIsNot(s.config.fil_copie_externe, premiere)
        s.attendre_copie()
        self.assertEqual(s.config.copie_externe_jour, "2026-06-20")
        self.assertEqual(copies_datees(self.copie), ["2026-06-20"])


class TestPlafondEtAcces(CasDansLeProcessus):

    def test_plafond_lu_sur_le_nom_de_la_derniere_tient_apres_un_redemarrage(self):
        s = self.serveur
        s.instant = instant(2026, 6, 15, 10, 0, 0)
        # Sauvegarde manuelle faite 10 s plus tôt par le serveur d'avant le redémarrage : seul son nom la date.
        (self.sauvegardes / "2026-06-15_095950").mkdir()
        refus = s.requete("POST", "/api/sauvegarde")
        self.assertEqual(refus.statut, 429, refus.octets)
        self.assertEqual(refus.entetes["retry-after"], "50")
        self.assertEqual(refus.json(), {"erreur": MESSAGE_PLAFOND % 50, "erreur_code": "sauvegardes.plafond_manuelles",
                                        "erreur_valeurs": {"n": 50}, "attente_secondes": 50})
        self.assertEqual(manuelles(self.sauvegardes), ["2026-06-15_095950"])   # rien de créé par le refus
        # Une sauvegarde à motif n'est jamais limitée (avant un import, avant un changement de format).
        for motif in ("avant-import", "avant-format-v3"):
            reponse = s.requete("POST", "/api/sauvegarde", {"motif": motif})
            self.assertEqual((reponse.statut, reponse.json()["sauvegarde"]), (200, "2026-06-15_100000_" + motif))
        s.instant += 49
        self.assertEqual(s.requete("POST", "/api/sauvegarde").entetes["retry-after"], "1")
        s.instant += 1                                          # une minute après la précédente (10 h 00 min 50 s)
        reponse = s.requete("POST", "/api/sauvegarde")
        self.assertEqual((reponse.statut, reponse.json()), (200, {"sauvegarde": "2026-06-15_100050"}))
        # Horloge reculée (passage à l'heure d'hiver) : un nom « dans le futur » ne bloque pas.
        s.instant = instant(2026, 6, 15, 9, 30, 0)
        self.assertEqual(s.requete("POST", "/api/sauvegarde").statut, 200)

    def test_nom_horodate_pris_puis_horloge_arretee_503(self):
        s = self.serveur
        s.instant = instant(2026, 6, 15, 11, 0, 0)
        self.assertEqual(s.requete("POST", "/api/sauvegarde", {"motif": "avant-import"}).statut, 200)
        # Même seconde, même motif : le serveur attend la seconde suivante ; une horloge qui n'avance plus rend 503
        # au lieu de boucler (ici 2 essais au lieu de 25 pour aller vite).
        with mock.patch.object(serveur, "ESSAIS_NOM_HORODATE", 2):
            reponse = s.requete("POST", "/api/sauvegarde", {"motif": "avant-import"})
        self.assertEqual(reponse.statut, 503, reponse.octets)
        self.assertIn("horloge", reponse.json()["erreur"])
        s.instant += 1
        self.assertEqual(s.requete("POST", "/api/sauvegarde", {"motif": "avant-import"}).json()["sauvegarde"],
                         "2026-06-15_110001_avant-import")

    def test_acces_copie_sans_sessions_et_jamais_restaure(self):
        s = self.serveur
        s.instant = instant(2026, 6, 15, 10, 0)
        nom = s.requete("POST", "/api/sauvegarde").json()["sauvegarde"]
        sauvegarde = self.sauvegardes / nom
        self.assertEqual((sauvegarde / "acces" / "comptes.json").read_bytes(), COMPTES_JSON)
        self.assertFalse((sauvegarde / "acces" / "sessions.json").exists())
        self.assertFalse((sauvegarde / "acces" / "cle.pem").exists())
        # Après la sauvegarde : un compte change, une table aussi.
        changes = json.dumps({"version": 1, "comptes": [{"identifiant": "nicolas.briand", "role": "responsable",
                                                          "actif": False}]}, indent=2).encode("utf-8")
        (self.donnees / "acces" / "comptes.json").write_bytes(changes)
        (self.donnees / "equipements.csv").write_bytes(csv_de("equipements", "EQ-0002;'PO-02;Compresseur"))
        s.instant += MINUTE
        reponse = s.requete("POST", "/api/restauration", {"sauvegarde": nom})
        self.assertEqual(reponse.statut, 200, reponse.octets)
        self.assertEqual(reponse.json()["restaurees"], ["equipements", "parametres"])
        self.assertEqual((self.donnees / "equipements.csv").read_bytes(), csv_de("equipements", "EQ-0001;'PO-01;Pompe"))
        self.assertEqual((self.donnees / "acces" / "comptes.json").read_bytes(), changes)
        self.assertEqual((self.donnees / "acces" / "sessions.json").read_bytes(), SESSIONS_JSON)
        copie_securite = self.sauvegardes / reponse.json()["copie_securite"]
        self.assertEqual((copie_securite / "acces" / "comptes.json").read_bytes(), changes)
        self.assertFalse((copie_securite / "acces" / "sessions.json").exists())


# ---------------------------------------------------------------------------
# Serveur réel (tests/commun.py)
# ---------------------------------------------------------------------------

class TestServeurReel(unittest.TestCase):

    def test_deuxieme_sauvegarde_manuelle_de_la_minute_429(self):
        with commun.ServeurPrevo() as reel:
            premiere = requete(reel.port, "POST", "/api/sauvegarde")
            self.assertEqual(premiere.statut, 200, premiere.octets)
            seconde = requete(reel.port, "POST", "/api/sauvegarde")
            self.assertEqual(seconde.statut, 429, seconde.octets)
            attente = int(seconde.entetes["retry-after"])
            self.assertTrue(1 <= attente <= 60, attente)
            self.assertEqual(seconde.json(), {"erreur": MESSAGE_PLAFOND % attente,
                                              "erreur_code": "sauvegardes.plafond_manuelles",
                                              "erreur_valeurs": {"n": attente}, "attente_secondes": attente})
            self.assertEqual(manuelles(reel.dossier / "sauvegardes"), [premiere.json()["sauvegarde"]])
            # Un corps sans motif (ou motif null) est une sauvegarde manuelle, limitée elle aussi.
            self.assertEqual(requete(reel.port, "POST", "/api/sauvegarde", {"motif": None}).statut, 429)
            avec_motif = requete(reel.port, "POST", "/api/sauvegarde", {"motif": "avant-import"})
            self.assertEqual(avec_motif.statut, 200, avec_motif.octets)

    def test_purge_au_dela_de_60_sauvegardes_manuelles(self):
        with commun.ServeurPrevo() as reel:
            dossier = reel.dossier / "sauvegardes"
            depart = datetime.datetime.now().replace(microsecond=0) - datetime.timedelta(days=30)
            fabriquees = [(depart + datetime.timedelta(minutes=numero)).strftime("%Y-%m-%d_%H%M%S")
                          for numero in range(62)]
            avant = (depart - datetime.timedelta(minutes=5)).strftime("%Y-%m-%d_%H%M%S")
            autres = [(depart - datetime.timedelta(days=1)).strftime("%Y-%m-%d"), avant + "_avant-import",
                      avant + "_avant-restauration", avant + "_avant-format-v3"]
            for nom in fabriquees + autres:
                (dossier / nom).mkdir()
                (dossier / nom / "parametres.csv").write_bytes(csv_de("parametres", "entreprise_nom;" + nom))
            reponse = requete(reel.port, "POST", "/api/sauvegarde")
            self.assertEqual(reponse.statut, 200, reponse.octets)
            nouvelle = reponse.json()["sauvegarde"]
            # 63 manuelles : les 3 plus anciennes supprimées ; quotidienne et « avant-… » (plus vieilles) intactes.
            self.assertEqual(manuelles(dossier), sorted(fabriquees[3:] + [nouvelle]))
            for nom in autres:
                self.assertTrue((dossier / nom / "parametres.csv").is_file(), nom)
            noms = [s["nom"] for s in requete(reel.port, "GET", "/api/sauvegardes").json()["sauvegardes"]]
            self.assertNotIn(fabriquees[0], noms)
            self.assertIn(fabriquees[3], noms)
            self.assertTrue(set(autres) <= set(noms))

    def test_tester_une_sauvegarde_compte_les_lignes_sans_rien_ecrire(self):
        with commun.ServeurPrevo() as reel:
            nom = requete(reel.port, "POST", "/api/sauvegarde").json()["sauvegarde"]
            sauvegarde = reel.dossier / "sauvegardes" / nom
            avant = etat_du_dossier(reel.dossier)
            reponse = requete(reel.port, "POST", "/api/sauvegarde/tester", {"nom": nom})
            self.assertEqual(reponse.statut, 200, reponse.octets)
            resultat = reponse.json()
            attendu = {chemin.stem: compter_lignes(chemin) for chemin in sorted(sauvegarde.glob("*.csv"))}
            self.assertEqual(len(attendu), 24)
            self.assertEqual((resultat["nom"], resultat["ok"]), (nom, True))
            self.assertEqual([table["table"] for table in resultat["tables"]], list(serveur.TABLES))   # ordre du schéma
            self.assertEqual({table["table"]: table["lignes"] for table in resultat["tables"]}, attendu)
            self.assertEqual({table["erreur"] for table in resultat["tables"]}, {None})
            self.assertGreater(attendu["equipements"], 10)
            self.assertEqual(etat_du_dossier(reel.dossier), avant)                 # rien d'écrit

            # Fichiers abîmés dans la sauvegarde : l'erreur est dite table par table.
            (sauvegarde / "equipements.csv").write_bytes(BOM + b"id;repere;marque" + CRLF + b"EQ-0001;'PO-01;X" + CRLF)
            (sauvegarde / "fournisseurs.csv").write_bytes(b"")
            resultat = requete(reel.port, "POST", "/api/sauvegarde/tester", {"nom": nom}).json()
            par_table = {table["table"]: table for table in resultat["tables"]}
            self.assertFalse(resultat["ok"])
            self.assertEqual(par_table["equipements"]["lignes"], 1)
            self.assertTrue(par_table["equipements"]["erreur"].startswith("Colonnes du schéma absentes de l'en-tête : "
                                                                          "designation, localisation_id"),
                            par_table["equipements"]["erreur"])
            self.assertEqual(par_table["fournisseurs"], {"table": "fournisseurs", "lignes": None,
                                                         "erreur": "Fichier vide : la ligne d'en-tête manque.",
                                                         "erreur_code": "sauvegardes.test_vide"})
            self.assertEqual(par_table["demandes"], {"table": "demandes", "lignes": attendu["demandes"], "erreur": None})

            # Sauvegarde d'un format plus ancien, réenregistrée par Excel : acceptée (lecture tolérante).
            ancienne = reel.dossier / "sauvegardes" / "2025-03-04_101010_avant-format-v3"
            ancienne.mkdir()
            colonnes = serveur.COLONNES_PAR_TABLE
            sans = lambda table, retirees: [colonne for colonne in colonnes[table] if colonne not in retirees]
            (ancienne / "ordres_travail.csv").write_bytes(           # format 2 : sans « astuce »
                BOM + ";".join(sans("ordres_travail", ("astuce",))).encode("utf-8") + CRLF + b"OT-0001;correctif" + CRLF)
            entete_excel = ";".join(nom_colonne.upper().replace("DESIGNATION", "Désignation")
                                    for nom_colonne in sans("equipements", ("valeur_remplacement",)))
            (ancienne / "equipements.csv").write_bytes(               # format 1, Windows-1252, en-tête en capitales
                (entete_excel + "\r\nEQ-0001;PO-01;Pompe à eau\r\n;;\r\n").encode("cp1252"))
            (ancienne / "demandes.csv").write_bytes(                  # format 1, séparateur « , »
                (",".join(sans("demandes", ("symptome_code", "ot_origine_id")))
                 + "\r\nDI-0001,2025-03-01 08:00,Léa\r\nDI-0002,2025-03-02 09:00,Karim\r\n").encode("utf-8"))
            resultat = requete(reel.port, "POST", "/api/sauvegarde/tester", {"nom": ancienne.name}).json()
            self.assertEqual(resultat, {"nom": ancienne.name, "ok": True, "tables": [
                {"table": "equipements", "lignes": 1, "erreur": None},
                {"table": "demandes", "lignes": 2, "erreur": None},
                {"table": "ordres_travail", "lignes": 1, "erreur": None}]})

            # Noms refusés (400), sauvegarde absente ou incomplète (404), corps invalide (400).
            incomplete = reel.dossier / "sauvegardes" / "2025-01-01"
            incomplete.mkdir()
            (incomplete / ".en-cours").write_bytes(b"")
            for corps, statut in (({"nom": "../donnees"}, 400), ({"nom": "2026-01-01_x"}, 400), ({}, 400),
                                  ({"nom": 5}, 400), (b"pas du json", 400), (["2025-01-01"], 400),
                                  ({"nom": "1999-01-01"}, 404), ({"nom": "2025-01-01"}, 404)):
                with self.subTest(corps=corps):
                    reponse = requete(reel.port, "POST", "/api/sauvegarde/tester", corps)
                    self.assertEqual(reponse.statut, statut, reponse.octets)
                    self.assertIn("erreur", reponse.json())

    def test_copie_au_demarrage_du_serveur_sans_sessions(self):
        racine = Path(tempfile.mkdtemp(prefix="prevo-sauvegardes-demarrage-"))
        self.addCleanup(shutil.rmtree, racine, True)
        source = racine / "source"
        shutil.copytree(commun.DOSSIER_DEMO, source)
        # T187 : la quotidienne du jour (le serveur ne la refait donc pas à son démarrage, et une quotidienne de plus
        # de 30 jours serait supprimée par la rotation).
        jour = datetime.date.today().isoformat()
        quotidienne = source / "sauvegardes" / jour
        (quotidienne / "acces").mkdir(parents=True)
        shutil.copy2(source / "parametres.csv", quotidienne / "parametres.csv")
        (quotidienne / "acces" / "comptes.json").write_bytes(COMPTES_JSON)
        # Une sauvegarde qui contiendrait des sessions (faite à la main, version d'avant) : jamais recopiées.
        (quotidienne / "acces" / "sessions.json").write_bytes(SESSIONS_JSON)
        cible = racine / "NAS" / "Prevo"
        cible.mkdir(parents=True)
        configuration = racine / "prevo.config.json"
        configuration.write_text(json.dumps({"copie_sauvegardes": str(cible)}), encoding="utf-8")
        with commun.ServeurPrevo(source=source, arguments=["--config", str(configuration)]) as reel:
            attendre(lambda: (reel.dossier / "copie-externe.json").is_file(), message=reel.sortie_console())
            self.assertEqual(contenu_du_dossier(cible / jour), {
                "acces/comptes.json": COMPTES_JSON,
                "parametres.csv": (source / "parametres.csv").read_bytes()})
            self.assertEqual(copies_datees(cible), [jour])
            self.assertEqual([chemin.name for chemin in cible.iterdir()], [jour])
            info = requete(reel.port, "GET", "/api/info").json()["copie_externe"]
            self.assertEqual(info, {"derniere_reussie": datetime.date.today().isoformat(), "jours_sans_copie": 0,
                                    "erreur": None})
            console = reel.sortie_console()
            self.assertIn("Copie externe    : %s" % cible, console)
            self.assertIn("Copie externe des sauvegardes : sauvegarde du %s à jour" % jour, console)


class TestCoherenceSchema(CasNavigateur):

    def test_colonnes_des_formats_suivants_identiques_a_schema_js(self):
        self.page.goto(url_fichier("index.html"))
        self.page.wait_for_function("typeof Schema !== 'undefined'")
        recentes = self.page.evaluate("""Object.fromEntries(Schema.nomsTables()
            .map((nom) => [nom, Schema.table(nom).champs.filter((c) => c.depuisVersion !== undefined).map((c) => c.nom)])
            .filter(([, champs]) => champs.length))""")
        self.assertEqual({table: list(champs) for table, champs in serveur.COLONNES_DES_FORMATS_SUIVANTS.items()},
                         recentes)
        for table, champs in recentes.items():
            with self.subTest(table=table):            # toujours en fin de table (lecture d'un format plus ancien)
                self.assertEqual(list(serveur.COLONNES_PAR_TABLE[table][-len(champs):]), champs)


# ---------------------------------------------------------------------------
# Écrans
# ---------------------------------------------------------------------------

class TestEcrans(CasNavigateur):

    def ouvrir(self, reel, route):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(reel.url + "/" + route)
        attendre_pret(self.page)
        return self.page

    def attendre_toast(self, extrait):
        self.page.wait_for_function(
            "extrait => document.getElementById('toast').textContent.includes(extrait)", arg=extrait)

    def fermer_la_fenetre(self):
        self.page.click("dialog .fenetre-actions .btn-primaire")
        self.page.wait_for_selector("dialog", state="detached")

    def test_parametres_bouton_tester_et_message_du_429(self):
        self.autoriser_erreur("status of 429")                  # Chromium logue toute réponse ≥ 400
        with commun.ServeurPrevo() as reel:
            nom = requete(reel.port, "POST", "/api/sauvegarde").json()["sauvegarde"]
            sauvegarde = reel.dossier / "sauvegardes" / nom
            page = self.ouvrir(reel, "#/parametres")
            page.wait_for_selector('button[data-tester="%s"]' % nom)
            self.assertEqual(page.locator("#carte-sauvegardes button[data-tester]").count(),
                             page.locator("#carte-sauvegardes button[data-restaurer]").count())
            ligne = page.locator('#carte-sauvegardes tr:has(button[data-tester="%s"])' % nom)
            self.assertEqual(ligne.locator('button[data-restaurer="%s"]' % nom).count(), 1)   # à côté de « Restaurer… »
            self.assertIn("Une sauvegarde manuelle par minute au plus", page.inner_text("#note-sauvegardes-serveur"))

            page.click('button[data-tester="%s"]' % nom)
            page.wait_for_selector("#resultat-test-sauvegarde")
            attendu = {chemin.stem: compter_lignes(chemin) for chemin in sauvegarde.glob("*.csv")}
            for table, lignes in attendu.items():
                self.assertEqual(page.inner_text('#resultat-test-sauvegarde [data-lignes="%s"]' % table), str(lignes))
            texte = page.inner_text("#resultat-test-sauvegarde")
            self.assertIn("Sauvegarde lisible : 24 tables relues, %d lignes en tout." % sum(attendu.values()),
                          " ".join(texte.split()))
            self.assertEqual(page.get_attribute("#resultat-test-sauvegarde", "data-ok"), "1")
            self.fermer_la_fenetre()

            # Une table abîmée sur le disque : l'erreur s'affiche à sa ligne.
            (sauvegarde / "equipements.csv").write_bytes(BOM + b"id;repere" + CRLF + b"EQ-0001;'PO-01" + CRLF)
            page.click('button[data-tester="%s"]' % nom)
            page.wait_for_selector('#resultat-test-sauvegarde [data-erreur="equipements"]')
            self.assertIn("designation", page.inner_text('#resultat-test-sauvegarde [data-erreur="equipements"]'))
            self.assertIn("Problème trouvé", page.inner_text("#resultat-test-sauvegarde"))
            self.assertEqual(page.get_attribute("#resultat-test-sauvegarde", "data-ok"), "0")
            self.fermer_la_fenetre()

            # « Sauvegarder maintenant » dans la minute de la précédente : le message du serveur s'affiche.
            requete(reel.port, "POST", "/api/sauvegarde")      # une manuelle récente, quelle que soit la durée du test
            page.click("#btn-sauvegarder")
            self.attendre_toast("Une sauvegarde manuelle par minute au plus : réessayez dans ")

    def test_parametres_sans_bouton_tester_en_demo(self):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        page.evaluate("location.hash = '#/parametres'")
        page.wait_for_selector("#carte-sauvegardes")
        self.assertIn("Indisponible en démo", page.inner_text("#carte-sauvegardes"))
        self.assertEqual(page.locator("button[data-tester]").count(), 0)
        self.assertEqual(page.locator("#note-sauvegardes-serveur").count(), 0)

    def test_parametres_sans_bouton_tester_en_mode_dossier(self):
        self.autoriser_erreur(ERREUR_PING_ABSENT)
        installer_dossier_simule(self.contexte, "donnees-sauvegardes-lot7")
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurStatique(RACINE) as statique:
            page.goto(statique.url + "/index.html")
            page.wait_for_selector("#btn-dossier")
            page.click("#btn-dossier")
            page.wait_for_selector("#ecran-base-vide", state="visible")
            page.click("#btn-base-demo")
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.mode"), "dossier")
            nom = page.evaluate("App.adaptateur.sauvegarder()")
            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_selector('button[data-restaurer="%s"]' % nom)
            self.assertEqual(page.locator("button[data-tester]").count(), 0)
            self.assertEqual(page.locator("#note-sauvegardes-serveur").count(), 0)
            self.assertFalse(page.evaluate("typeof App.adaptateur.testerSauvegarde === 'function'"))

    def test_accueil_avertit_avec_le_nombre_de_jours(self):
        racine = Path(tempfile.mkdtemp(prefix="prevo-sauvegardes-accueil-"))
        self.addCleanup(shutil.rmtree, racine, True)
        source = racine / "source"
        shutil.copytree(commun.DOSSIER_DEMO, source)
        il_y_a_trois_jours = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
        (source / "copie-externe.json").write_text(json.dumps({
            "derniere_reussie": il_y_a_trois_jours, "sauvegarde_copiee": il_y_a_trois_jours, "erreur": None}),
            encoding="utf-8")
        configuration = racine / "prevo.config.json"
        configuration.write_text(json.dumps({"copie_sauvegardes": str(racine / "Cle USB" / "Sauvegardes Prevo")}),
                                 encoding="utf-8")                # clé absente
        with commun.ServeurPrevo(source=source, arguments=["--config", str(configuration)]) as reel:
            attendre(lambda: "Copie externe des sauvegardes impossible" in reel.sortie_console(),
                     message=reel.sortie_console())             # la copie du démarrage a échoué
            page = self.ouvrir(reel, "#/accueil")
            page.wait_for_selector("#alerte-copie-externe")
            texte = " ".join(page.inner_text("#alerte-copie-externe").split())
            self.assertIn("Copie externe des sauvegardes : aucune copie depuis 3 jours.", texte)
            self.assertIn("Dossier de copie « Sauvegardes Prevo » introuvable (clé USB absente", texte)
            self.assertNotIn("Cle USB", texte)
            self.assertIn("attention", page.get_attribute("#alerte-copie-externe", "class"))
            journal = (reel.dossier / "journal-serveur.log").read_text(encoding="utf-8")
            self.assertIn("Copie externe des sauvegardes impossible", journal)

    def test_accueil_rien_quand_tout_va_bien_ou_sans_dossier(self):
        racine = Path(tempfile.mkdtemp(prefix="prevo-sauvegardes-accueil-ok-"))
        self.addCleanup(shutil.rmtree, racine, True)
        source = racine / "source"
        shutil.copytree(commun.DOSSIER_DEMO, source)
        (source / "sauvegardes" / "2026-06-01").mkdir(parents=True)
        shutil.copy2(source / "parametres.csv", source / "sauvegardes" / "2026-06-01" / "parametres.csv")
        cible = racine / "NAS"
        cible.mkdir()
        configuration = racine / "prevo.config.json"
        configuration.write_text(json.dumps({"copie_sauvegardes": str(cible)}), encoding="utf-8")
        with commun.ServeurPrevo(source=source, arguments=["--config", str(configuration)]) as reel:
            attendre(lambda: (reel.dossier / "copie-externe.json").is_file(), message=reel.sortie_console())
            page = self.ouvrir(reel, "#/accueil")
            page.wait_for_selector("#copie-externe-zone[data-lu='1']", state="attached")
            self.assertEqual(page.locator("#alerte-copie-externe").count(), 0)     # copie à jour : rien
            page.goto("about:blank")                            # la page quitte ce serveur avant son arrêt
        with commun.ServeurPrevo() as reel:                     # aucun dossier de copie réglé : rien
            self.assertIsNone(requete(reel.port, "GET", "/api/info").json()["copie_externe"])
            page = self.ouvrir(reel, "#/accueil")
            page.wait_for_selector("#copie-externe-zone[data-lu='1']", state="attached")
            self.assertEqual(page.locator("#alerte-copie-externe").count(), 0)

    def test_texte_de_l_avertissement(self):
        self.page.goto(url_fichier("index.html"))
        self.page.wait_for_function("typeof Accueil !== 'undefined' && typeof Accueil.avertissementCopieExterne === 'function'")
        erreur = "Dossier de copie « Clé » introuvable (clé USB absente ou partage réseau injoignable ?)."
        cas = [None,
               {"derniereReussie": "2026-06-10", "joursSansCopie": 0, "erreur": None},
               {"derniereReussie": "2026-06-10", "joursSansCopie": 1, "erreur": None},
               {"derniereReussie": "2026-06-10", "joursSansCopie": 2, "erreur": None},
               {"derniereReussie": "2026-06-10", "joursSansCopie": 1, "erreur": erreur},
               {"derniereReussie": "2026-06-10", "joursSansCopie": 0, "erreur": erreur},
               {"derniereReussie": None, "joursSansCopie": None, "erreur": erreur}]
        textes = self.page.evaluate("""(cas) => cas.map((copie) => {
            const fragment = Accueil.avertissementCopieExterne(copie);
            return fragment ? UI.element(UI.html`<div>${fragment}</div>`).textContent.replace(/\\s+/g, ' ').trim() : '';
        })""", cas)
        suite = " La copie est refaite au prochain démarrage de Prévo et chaque nuit, à la première modification après 2 h."
        self.assertEqual(textes, [
            "", "", "",
            "Copie externe des sauvegardes : aucune copie depuis 2 jours." + suite,
            "Copie externe des sauvegardes : aucune copie depuis 1 jour. " + erreur + suite,
            "Copie externe des sauvegardes : la dernière copie a échoué. " + erreur + suite,
            "Copie externe des sauvegardes : aucune copie réussie pour l'instant. " + erreur + suite,
        ])


if __name__ == "__main__":
    unittest.main()
