"""Lot 7 — derrière un mandataire (ARCHITECTURE.md §22.7 ; CDC D129 ; CS128 ; tâche T164).

Ce qui est vérifié :
    origine        origine_mandatee : attestée seulement si « mandataire » est vrai, connexion venue de 127.0.0.1 ou ::1,
                   X-Forwarded-Proto (http|https) et X-Forwarded-Host présents ; dernière adresse de X-Forwarded-For
                   si lisible ; sinon None (en-têtes ignorés) ;
    https          derrière le mandataire de test en https : cookie Secure, /api/info sur l'hôte d'origine (jamais la
                   porte), l'application servie en http sur 127.0.0.1, HSTS pour le nom d'origine, journal avec
                   l'adresse d'origine et la colonne Tailscale ;
    http           mandataire en http : cookie sans Secure, adresses en http ;
    hôte           hôte d'origine hors des noms acceptés : 403 sur toute route ;
    ignorés        « mandataire » faux : les mêmes en-têtes, venus d'un relais ou d'un client direct, ne changent rien ;
                   un relais sans X-Forwarded-* : client direct (adresses du serveur), colonne Tailscale gardée (T151).

Serveur réel (ServeurPrevo de tests/commun.py, comptes=True, « mandataire » et « noms » par reglages) derrière
tests/mandataire_test.py ; aucune commande d'administrateur, aucune sortie réseau.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_acces_mandataire.py" -v
"""
import csv
import http.client
import importlib.util
import json
import unittest
from pathlib import Path

from commun import RACINE, ServeurPrevo, COMPTES_DE_TEST
from mandataire_test import MandataireTest

SCRIPT = RACINE / "serveur.py"


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_mandataire", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()

NOM_ORIGINE = "prevo.tail1234.ts.net"
CLIENT_ORIGINE = "100.64.0.7"
UTILISATEUR_TAILSCALE = "nicolas@github"
AGENT = "Navigateur-de-test/1.0"


class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))

    @property
    def set_cookie(self):
        return self.entetes.get("set-cookie", "")

    @property
    def cookie(self):
        return self.set_cookie.split(";")[0] if self.set_cookie else None


def requete(url, methode, chemin, corps=None, cookie=None, entetes=None):
    """Une requête http vers « url » (le serveur ou le mandataire), une connexion par requête."""
    hote, port = url.split("//", 1)[1].split(":")
    en_tetes = dict(entetes or {})
    en_tetes.setdefault("User-Agent", AGENT)
    if cookie:
        en_tetes["Cookie"] = cookie
    if methode in ("POST", "PUT"):
        en_tetes["X-Prevo"] = "1"
    if isinstance(corps, dict):
        corps = json.dumps(corps).encode("utf-8")
        en_tetes["Content-Type"] = "application/json; charset=utf-8"
    connexion = http.client.HTTPConnection(hote, int(port), timeout=30)
    try:
        connexion.request(methode, chemin, body=corps, headers=en_tetes)
        reponse = connexion.getresponse()
        return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
    finally:
        connexion.close()


def connecter(url, role="responsable"):
    identifiant, _, _, mot_de_passe, _ = COMPTES_DE_TEST[role]
    return requete(url, "POST", "/api/connexion", {"identifiant": identifiant, "mot_de_passe": mot_de_passe,
                                                   "rester": False})


def lignes_du_journal(dossier):
    chemin = Path(dossier) / "acces" / "journal-acces.csv"
    if not chemin.is_file():
        return []
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        return list(csv.DictReader(fichier, delimiter=";"))


class FauxGestionnaire:
    def __init__(self, mandataire, adresse, entetes):
        self.config = serveur.Configuration(str(RACINE / "donnees"), [])
        self.config.reglages["mandataire"] = mandataire
        self.client_address = (adresse, 12345)
        self.headers = entetes


class TestOrigineMandatee(unittest.TestCase):

    def test_attestee_seulement_depuis_ce_pc_avec_les_deux_en_tetes(self):
        complets = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": NOM_ORIGINE, "X-Forwarded-For": CLIENT_ORIGINE}
        self.assertIsNone(serveur.origine_mandatee(FauxGestionnaire(False, "127.0.0.1", complets)))
        self.assertIsNone(serveur.origine_mandatee(FauxGestionnaire(True, "192.168.1.5", complets)))
        self.assertIsNone(serveur.origine_mandatee(FauxGestionnaire(True, "127.0.0.1", {})))
        self.assertIsNone(serveur.origine_mandatee(FauxGestionnaire(True, "127.0.0.1", {"X-Forwarded-Proto": "https"})))
        self.assertIsNone(serveur.origine_mandatee(FauxGestionnaire(True, "127.0.0.1", {"X-Forwarded-Host": NOM_ORIGINE})))
        self.assertIsNone(serveur.origine_mandatee(FauxGestionnaire(True, "127.0.0.1",
                                                                     dict(complets, **{"X-Forwarded-Proto": "ftp"}))))
        self.assertIsNone(serveur.origine_mandatee(FauxGestionnaire(True, "127.0.0.1",
                                                                     dict(complets, **{"X-Forwarded-Host": "a/b"}))))
        self.assertEqual(serveur.origine_mandatee(FauxGestionnaire(True, "127.0.0.1", complets)),
                         {"protocole": "https", "hote": NOM_ORIGINE, "adresse": CLIENT_ORIGINE})
        self.assertEqual(serveur.origine_mandatee(FauxGestionnaire(True, "::1", complets))["adresse"], CLIENT_ORIGINE)
        # Chaîne de mandataires : la dernière adresse (celle que le mandataire de ce PC a vue) ; port de l'hôte gardé.
        chaine = {"X-Forwarded-Proto": "HTTPS, http", "X-Forwarded-Host": "Prevo.Exemple:8443, autre",
                  "X-Forwarded-For": "1.2.3.4, 100.64.0.9"}
        self.assertEqual(serveur.origine_mandatee(FauxGestionnaire(True, "127.0.0.1", chaine)),
                         {"protocole": "https", "hote": "prevo.exemple:8443", "adresse": "100.64.0.9"})
        # X-Forwarded-For illisible ou absent : l'adresse de la connexion.
        sans_for = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": NOM_ORIGINE}
        self.assertEqual(serveur.origine_mandatee(FauxGestionnaire(True, "127.0.0.1", sans_for))["adresse"], "127.0.0.1")
        illisible = dict(sans_for, **{"X-Forwarded-For": "pas une adresse"})
        self.assertEqual(serveur.origine_mandatee(FauxGestionnaire(True, "127.0.0.1", illisible))["adresse"], "127.0.0.1")


class TestDerriereLeMandataire(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.serveur = ServeurPrevo(comptes=True, reglages={"mandataire": True, "noms": [NOM_ORIGINE]})
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def test_https_cookie_secure_adresses_d_origine_journal_et_hsts(self):
        with MandataireTest(self.serveur.url, hote=NOM_ORIGINE, protocole="https", client=CLIENT_ORIGINE,
                            tailscale=UTILISATEUR_TAILSCALE) as mandataire:
            entree = connecter(mandataire.url)
            self.assertEqual(entree.statut, 200, entree.octets)
            self.assertIn("; Secure", entree.set_cookie)
            self.assertIn("HttpOnly", entree.set_cookie)
            cookie = entree.cookie
            info = requete(mandataire.url, "GET", "/api/info", cookie=cookie).json()
            self.assertEqual(info["adresse_locale"], "https://%s/" % NOM_ORIGINE)
            self.assertEqual(info["adresses_reseau"], ["https://%s/" % NOM_ORIGINE])
            self.assertFalse(info["porte"])
            # L'application elle-même, en http sur 127.0.0.1 derrière le mandataire : pas une page de porte.
            page = requete(mandataire.url, "GET", "/")
            self.assertEqual(page.statut, 200)
            self.assertIn(b"<title>", page.octets)
            self.assertNotIn(b"Faites confiance au PC atelier", page.octets)
            self.assertEqual(page.entetes.get("strict-transport-security"), "max-age=%d" % serveur.DUREE_HSTS_S)
            self.assertEqual(requete(mandataire.url, "GET", "/api/csv/equipements", cookie=cookie).statut, 200)
            # Journal : adresse d'origine et colonne Tailscale.
            derniere = [l for l in lignes_du_journal(self.serveur.dossier) if l["resultat"] == "connexion"][-1]
            self.assertEqual((derniere["qui"], derniere["adresse"], derniere["tailscale"]),
                             (COMPTES_DE_TEST["responsable"][0], CLIENT_ORIGINE, UTILISATEUR_TAILSCALE))
        # Sans mandataire (client direct sur 127.0.0.1) : adresses du serveur, pas de HSTS, pas de Secure.
        direct = connecter(self.serveur.url)
        self.assertEqual(direct.statut, 200)
        self.assertNotIn("Secure", direct.set_cookie)
        info = requete(self.serveur.url, "GET", "/api/info", cookie=direct.cookie).json()
        self.assertTrue(info["adresse_locale"].startswith("http://localhost:"))
        self.assertNotIn("strict-transport-security", requete(self.serveur.url, "GET", "/").entetes)

    def test_mandataire_en_http_et_hote_hors_des_noms(self):
        with MandataireTest(self.serveur.url, hote=NOM_ORIGINE, protocole="http", client=CLIENT_ORIGINE) as mandataire:
            entree = connecter(mandataire.url)
            self.assertEqual(entree.statut, 200, entree.octets)
            self.assertNotIn("Secure", entree.set_cookie)
            info = requete(mandataire.url, "GET", "/api/info", cookie=entree.cookie).json()
            self.assertEqual(info["adresses_reseau"], ["http://%s/" % NOM_ORIGINE])
            self.assertNotIn("strict-transport-security", requete(mandataire.url, "GET", "/").entetes)
        with MandataireTest(self.serveur.url, hote="pirate.example", protocole="https", client=CLIENT_ORIGINE) as mandataire:
            for methode, chemin in (("GET", "/api/ping"), ("GET", "/"), ("POST", "/api/connexion")):
                with self.subTest(chemin=chemin):
                    refus = requete(mandataire.url, methode, chemin, {} if methode == "POST" else None)
                    self.assertEqual((refus.statut, refus.json()), (403, {"erreur": serveur.MESSAGE_HOTE_ORIGINE_REFUSE,
                                                                         "erreur_code": "requete.hote_origine_refuse"}))
        # Un nom accepté avec son port, et l'adresse IP du PC, passent comme pour Host.
        with MandataireTest(self.serveur.url, hote=NOM_ORIGINE + ":8443", protocole="https") as mandataire:
            cookie = connecter(mandataire.url).cookie
            self.assertEqual(requete(mandataire.url, "GET", "/api/info", cookie=cookie).json()["adresses_reseau"],
                             ["https://%s:8443/" % NOM_ORIGINE])
        with MandataireTest(self.serveur.url, hote="127.0.0.1:9000", protocole="https") as mandataire:
            self.assertEqual(requete(mandataire.url, "GET", "/api/ping").statut, 200)

    def test_relais_sans_en_tetes_forwarded_est_un_client_direct(self):
        with MandataireTest(self.serveur.url, tailscale=UTILISATEUR_TAILSCALE, forwarded=False) as relais:
            entree = connecter(relais.url)
            self.assertEqual(entree.statut, 200, entree.octets)
            self.assertNotIn("Secure", entree.set_cookie)
            info = requete(relais.url, "GET", "/api/info", cookie=entree.cookie).json()
            self.assertTrue(info["adresse_locale"].startswith("http://localhost:"))
            derniere = [l for l in lignes_du_journal(self.serveur.dossier) if l["resultat"] == "connexion"][-1]
            self.assertEqual((derniere["adresse"], derniere["tailscale"]), ("127.0.0.1", UTILISATEUR_TAILSCALE))


class TestMandataireFaux(unittest.TestCase):

    def test_en_tetes_forwarded_ignores_quand_mandataire_est_faux(self):
        with ServeurPrevo(comptes=True) as serveur_:
            forges = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": NOM_ORIGINE, "X-Forwarded-For": CLIENT_ORIGINE,
                      "Tailscale-User-Login": UTILISATEUR_TAILSCALE}
            identifiant, _, _, mot_de_passe, _ = COMPTES_DE_TEST["responsable"]
            entree = requete(serveur_.url, "POST", "/api/connexion",
                             {"identifiant": identifiant, "mot_de_passe": mot_de_passe, "rester": False}, entetes=forges)
            self.assertEqual(entree.statut, 200, entree.octets)
            self.assertNotIn("Secure", entree.set_cookie)
            info = requete(serveur_.url, "GET", "/api/info", cookie=entree.cookie, entetes=forges).json()
            self.assertTrue(info["adresse_locale"].startswith("http://localhost:"))
            self.assertNotIn("strict-transport-security", requete(serveur_.url, "GET", "/", entetes=forges).entetes)
            derniere = lignes_du_journal(serveur_.dossier)[-1]
            self.assertEqual((derniere["adresse"], derniere["tailscale"]), ("127.0.0.1", ""))
            with MandataireTest(serveur_.url, hote=NOM_ORIGINE, protocole="https", client=CLIENT_ORIGINE) as mandataire:
                info = requete(mandataire.url, "GET", "/api/info", cookie=entree.cookie).json()
                self.assertTrue(info["adresse_locale"].startswith("http://localhost:"))


if __name__ == "__main__":
    unittest.main()
