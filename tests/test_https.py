"""https en option pour serveur.py (lot 4, ARCHITECTURE.md §17.2 ; CDC D74 ; CS73).

Un certificat de test auto-signé (localhost, 127.0.0.1) est fabriqué à chaque exécution avec openssl
(livré avec Git pour Windows) dans un dossier temporaire : aucune clé privée n'est versionnée. Sans
openssl, ces tests sont sautés en le disant.
    - avec --certificat et --cle : le serveur répond en https (certificat vérifié contre lui-même),
      /api/info donne des adresses en https://, l'application démarre et ses adresses (QR) sont en
      https ;
    - sans ces options : http, comme avant ;
    - une seule des deux options, ou un fichier illisible : arrêt avec un message clair.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_https.py" -v
"""
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, port_libre, preregler_profil

CHEMINS_OPENSSL = [r"C:\Program Files\Git\usr\bin\openssl.exe", r"C:\Program Files\Git\mingw64\bin\openssl.exe"]


def trouver_openssl():
    trouve = shutil.which("openssl")
    if trouve:
        return trouve
    return next((chemin for chemin in CHEMINS_OPENSSL if os.path.isfile(chemin)), None)


def fabriquer_certificat(dossier):
    """Certificat et clé de test (PEM) pour localhost et 127.0.0.1, valables 2 jours."""
    openssl = trouver_openssl()
    if not openssl:
        raise unittest.SkipTest("openssl introuvable : test du https sauté")
    certificat, cle = Path(dossier) / "certificat.pem", Path(dossier) / "cle.pem"
    environnement = dict(os.environ, MSYS_NO_PATHCONV="1", MSYS2_ARG_CONV_EXCL="*")
    subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(cle), "-out", str(certificat),
                    "-days", "2", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
                   check=True, capture_output=True, env=environnement, timeout=60)
    return certificat, cle


class TestHttps(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dossier = Path(tempfile.mkdtemp(prefix="prevo-https-"))
        cls.addClassCleanup(shutil.rmtree, cls.dossier, True)
        cls.certificat, cls.cle = fabriquer_certificat(cls.dossier)

    def test_serveur_en_https_et_adresses_en_https(self):
        with ServeurPrevo(arguments=["--certificat", str(self.certificat), "--cle", str(self.cle)]) as serveur:
            self.assertTrue(serveur.url.startswith("https://"))
            contexte = ssl.create_default_context(cafile=str(self.certificat))
            with urllib.request.urlopen(serveur.url.replace("127.0.0.1", "localhost") + "/api/info", context=contexte, timeout=10) as reponse:
                info = json.loads(reponse.read().decode("utf-8"))
            self.assertTrue(info["adresse_locale"].startswith("https://localhost:"))
            self.assertTrue(all(adresse.startswith("https://") for adresse in info["adresses_reseau"]))
            self.assertIn("https://localhost:", serveur.sortie_console())
            # En http simple, le serveur https ne répond pas comme un serveur http
            with self.assertRaises(Exception):
                urllib.request.urlopen(serveur.url.replace("https://", "http://") + "/api/ping", timeout=5).read()

    def test_sans_certificat_http_comme_avant(self):
        with ServeurPrevo() as serveur:
            self.assertTrue(serveur.url.startswith("http://"))
            with urllib.request.urlopen(serveur.url + "/api/info", timeout=10) as reponse:
                info = json.loads(reponse.read().decode("utf-8"))
            self.assertTrue(info["adresse_locale"].startswith("http://localhost:"))

    def test_options_incompletes_ou_fichier_illisible_arretent_le_serveur(self):
        illisible = self.dossier / "illisible.pem"
        illisible.write_text("pas un certificat", encoding="utf-8")
        cas = (["--certificat", str(self.certificat)], ["--cle", str(self.cle)],
               ["--certificat", str(illisible), "--cle", str(self.cle)],
               ["--certificat", str(self.dossier / "absent.pem"), "--cle", str(self.cle)])
        for arguments in cas:
            with self.subTest(arguments=[Path(a).name for a in arguments]):
                resultat = subprocess.run(
                    [sys.executable, str(RACINE / "serveur.py"), "--sans-navigateur", "--port", str(port_libre()),
                     "--donnees", str(self.dossier / "donnees")] + arguments,
                    capture_output=True, timeout=30, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
                self.assertNotEqual(resultat.returncode, 0)
                sortie = (resultat.stdout + resultat.stderr).decode("utf-8", "replace")
                self.assertIn("certificat", sortie.lower())


class TestHttpsNavigateur(CasNavigateur):

    def test_application_et_qr_en_https(self):
        dossier = Path(tempfile.mkdtemp(prefix="prevo-https-nav-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        certificat, cle = fabriquer_certificat(dossier)
        with ServeurPrevo(arguments=["--certificat", str(certificat), "--cle", str(cle)]) as serveur:
            contexte = self.navigateur.new_context(locale="fr-FR", ignore_https_errors=True)
            self.addCleanup(contexte.close)
            preregler_profil(contexte, "responsable")
            page = contexte.new_page()
            self.surveiller(page)
            page.goto(serveur.url + "/")
            attendre_pret(page)
            self.assertTrue(page.evaluate("window.isSecureContext"))
            adresses = page.evaluate("App.adressesReseau()")
            self.assertTrue(all(adresse.startswith("https://") for adresse in adresses))
            equipement = page.evaluate("Donnees.lignes('equipements')[0].id")
            url_qr = page.evaluate("(id) => App.urlFicheEquipement(id)", equipement)
            self.assertTrue(url_qr.startswith("https://"), url_qr)


if __name__ == "__main__":
    unittest.main()
