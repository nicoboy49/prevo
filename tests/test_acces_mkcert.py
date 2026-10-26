"""Lot 7 — certificat local par mkcert, piloté par Prévo (ARCHITECTURE.md §22.6 ; D127 ; CS126 ; tâche T162).

Ce qui est vérifié, avec un faux mkcert (tests/faux_mkcert.py, certificats fabriqués par openssl) :
    empreinte     un binaire dont le SHA-256 n'est pas celui de outils/empreintes-tiers.json n'est jamais exécuté
                  (refus, message, aucun lancement) ; le bon l'est ;
    certificat    le certificat couvre les adresses IP du PC, <nom>.local, <nom>, localhost, 127.0.0.1 et les noms
                  acceptés ; il n'est pas refait tant que les noms ne changent pas ; il est refait quand l'adresse
                  change ;
    autorité      seul rootCA.pem (public) est rendu pour les téléphones ; rootCA-key.pem n'est jamais copié hors du
                  dossier de l'autorité ;
    secours       téléchargement : fichier gardé si l'empreinte est juste, jamais sinon ;
    fichier       outils/empreintes-tiers.json donne mkcert 1.4.4 pour Windows, Linux (dont Raspberry Pi) et macOS ;
                  nom_binaire_mkcert choisit le bon fichier.
Le vrai mkcert (autorité installée dans Windows, téléphones) est vérifié en recette réelle (CS136).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_acces_mkcert.py" -v
"""
import hashlib
import http.server
import importlib.util
import json
import shutil
import ssl
import tempfile
import threading
import unittest
from pathlib import Path

from commun import RACINE
from test_https import trouver_openssl

FAUX = RACINE / "tests" / "faux_mkcert.py"


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_mkcert", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


def sha256(chemin):
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()


def noms_du_certificat_pem(chemin):
    decode = ssl._ssl._test_decode_cert(str(chemin))
    return sorted(valeur for _, valeur in decode.get("subjectAltName", ()))


class CasMkcert(unittest.TestCase):

    def setUp(self):
        if not trouver_openssl():
            self.skipTest("openssl introuvable : faux mkcert impossible")
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-mkcert-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        self.outils = self.dossier / "outils-tiers"
        self.outils.mkdir()
        shutil.copy(FAUX, self.outils / "faux_mkcert.py")
        self.config = serveur.Configuration(str(self.dossier / "donnees"), ["prevo.tailnet.ts.net"])
        self.config.reglages["noms"] = ["prevo.tailnet.ts.net"]
        serveur.creer_dossiers(self.config)

    def empreintes(self, sha=None):
        return {"mkcert": {"version": "1.4.4", "source": "http://invalide.example/",
                           "fichiers": {"faux_mkcert.py": {"sha256": sha or sha256(self.outils / "faux_mkcert.py")}}}}

    def lancements(self):
        journal = Path(serveur.dossier_autorite(self.config)) / "lancements.txt"
        return journal.read_text(encoding="utf-8").splitlines() if journal.is_file() else []


class TestEmpreinte(CasMkcert):

    def test_empreinte_fausse_jamais_executee(self):
        with self.assertRaises(serveur.ErreurConfiguration) as refus:
            serveur.trouver_mkcert(self.empreintes("0" * 64), str(self.outils), "faux_mkcert.py")
        self.assertIn("n'a pas été exécuté", str(refus.exception))
        self.assertEqual(self.lancements(), [])

    def test_empreinte_juste_puis_certificat(self):
        executable = serveur.trouver_mkcert(self.empreintes(), str(self.outils), "faux_mkcert.py")
        certificat, cle, noms = serveur.preparer_certificat_local(self.config, executable, adresses=["192.168.1.20"])
        attendus = sorted(["192.168.1.20", self.config.nom_pc + ".local", self.config.nom_pc, "localhost",
                           "127.0.0.1", "prevo.tailnet.ts.net"])
        self.assertEqual(sorted(noms), attendus)
        self.assertEqual(noms_du_certificat_pem(certificat), attendus)
        self.assertTrue(Path(cle).is_file())
        self.assertEqual(len(self.lancements()), 1)


class TestRegeneration(CasMkcert):

    def test_pas_refait_si_rien_ne_change_refait_si_l_adresse_change(self):
        executable = serveur.trouver_mkcert(self.empreintes(), str(self.outils), "faux_mkcert.py")
        certificat, _, _ = serveur.preparer_certificat_local(self.config, executable, adresses=["192.168.1.20"])
        premier = Path(certificat).read_bytes()
        serveur.preparer_certificat_local(self.config, executable, adresses=["192.168.1.20"])
        self.assertEqual(len(self.lancements()), 1)
        self.assertEqual(Path(certificat).read_bytes(), premier)
        serveur.preparer_certificat_local(self.config, executable, adresses=["192.168.1.30"])
        self.assertEqual(len(self.lancements()), 2)
        self.assertIn("192.168.1.30", noms_du_certificat_pem(certificat))
        self.assertNotIn("192.168.1.20", noms_du_certificat_pem(certificat))
        fiche = json.loads((Path(serveur.dossier_acces(self.config)) / "certificat.json").read_text(encoding="utf-8"))
        self.assertEqual(fiche["noms"][0], "192.168.1.30")


class TestAutorite(CasMkcert):

    def test_seule_la_partie_publique_est_rendue(self):
        executable = serveur.trouver_mkcert(self.empreintes(), str(self.outils), "faux_mkcert.py")
        serveur.preparer_certificat_local(self.config, executable, adresses=["192.168.1.20"])
        publique = serveur.certificat_de_l_autorite(self.config)
        self.assertIn(b"BEGIN CERTIFICATE", publique)
        self.assertNotIn(b"PRIVATE KEY", publique)
        autorite = Path(serveur.dossier_autorite(self.config)).resolve()
        cles = [p for p in (self.dossier / "donnees").rglob("rootCA-key.pem")]
        self.assertEqual([p.resolve().parent for p in cles], [autorite])


class TestTelechargement(CasMkcert):

    def servir(self, octets):
        class Gestionnaire(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(octets)))
                self.end_headers()
                self.wfile.write(octets)

            def log_message(self, *arguments):
                pass
        site = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
        threading.Thread(target=site.serve_forever, daemon=True).start()
        self.addCleanup(site.server_close)
        self.addCleanup(site.shutdown)
        return "http://127.0.0.1:%d/faux_mkcert.py" % site.server_address[1]

    def test_garde_le_fichier_seulement_si_l_empreinte_est_juste(self):
        octets = FAUX.read_bytes()
        bon = {"mkcert": {"version": "1.4.4", "source": "",
                          "fichiers": {"faux_mkcert.py": {"sha256": hashlib.sha256(octets).hexdigest()}}}}
        mauvais = {"mkcert": {"version": "1.4.4", "source": "", "fichiers": {"faux_mkcert.py": {"sha256": "1" * 64}}}}
        cible = self.dossier / "telecharge"
        adresse = self.servir(octets)
        with self.assertRaises(serveur.ErreurConfiguration):
            serveur.telecharger_mkcert(mauvais, str(cible), "faux_mkcert.py", adresse)
        self.assertEqual(list(cible.iterdir()) if cible.exists() else [], [])
        chemin = serveur.telecharger_mkcert(bon, str(cible), "faux_mkcert.py", adresse)
        self.assertEqual(Path(chemin).read_bytes(), octets)


class TestFichierEmpreintes(unittest.TestCase):

    def test_empreintes_et_noms(self):
        empreintes = serveur.lire_empreintes_tiers()
        fichiers = empreintes["mkcert"]["fichiers"]
        self.assertEqual(empreintes["mkcert"]["version"], "1.4.4")
        for nom in ("mkcert-v1.4.4-windows-amd64.exe", "mkcert-v1.4.4-linux-arm64", "mkcert-v1.4.4-linux-arm",
                    "mkcert-v1.4.4-darwin-arm64"):
            with self.subTest(nom=nom):
                self.assertRegex(fichiers[nom]["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(serveur.nom_binaire_mkcert("1.4.4", "win32", "AMD64"), "mkcert-v1.4.4-windows-amd64.exe")
        self.assertEqual(serveur.nom_binaire_mkcert("1.4.4", "linux", "aarch64"), "mkcert-v1.4.4-linux-arm64")
        self.assertEqual(serveur.nom_binaire_mkcert("1.4.4", "linux", "armv7l"), "mkcert-v1.4.4-linux-arm")
        self.assertEqual(serveur.nom_binaire_mkcert("1.4.4", "darwin", "arm64"), "mkcert-v1.4.4-darwin-arm64")


if __name__ == "__main__":
    unittest.main()
