"""Lot 7 — distribution : Python embarqué et mkcert dans le zip, lanceurs, réinitialisation (ARCHITECTURE.md §22.14 ;
D131 ; CS131 ; tâche T172).

Ce qui est vérifié :
    tiers         le zip contient python/ (paquet embarqué déplié, LICENSE.txt compris) et outils-tiers/ (mkcert pour
                  Windows et sa licence), avec outils/empreintes-tiers.json ; les octets sont ceux des fichiers obtenus ;
                  deux constructions donnent le même zip ; une empreinte fausse arrête tout sans rien écrire ; un
                  fichier intact du cache sert sans téléchargement (téléchargements simulés : rien ne sort sur Internet) ;
    empreintes    outils/empreintes-tiers.json : Python 3.14.9 pour Windows 64 bits, mkcert 1.4.4 et sa licence ;
    lanceurs      Lancer_GMAO.bat prend d'abord python\\python.exe, puis un Python installé ≥ 3.11 ; lancer.sh refuse
                  un Python 3.10 avec son message et accepte un 3.11 (faux python3) ;
    réinitialiser Reinitialiser_mot_de_passe.bat (Windows) demande l'identifiant et affiche le mot de passe provisoire ;
    dépôt         aucun binaire tiers suivi par git ; .gitignore les écarte.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_release_lot7.py" -v
"""
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from commun import RACINE

SCRIPT_RELEASE = RACINE / "outils" / "construire_release.py"
BASH_GIT = Path(r"C:\Program Files\Git\bin\bash.exe")


def charger(chemin, nom):
    specification = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


release = charger(SCRIPT_RELEASE, "construire_release_lot7")


def bash_utilisable():
    """Git Bash sous Windows, comme tests/test_lanceurs.py (le « bash » de System32 est celui de WSL, souvent sans
    distribution : il échoue quand la suite est lancée hors de Git Bash) ; bash ailleurs ; None s'il manque."""
    if os.name == "nt":
        return str(BASH_GIT) if BASH_GIT.exists() else None
    return shutil.which("bash")


def faux_paquet_python():
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as paquet:
        for nom, contenu in (("python.exe", b"MZ faux python"), ("pythonw.exe", b"MZ faux pythonw"),
                             ("LICENSE.txt", b"PSF LICENSE AGREEMENT (faux)"), ("python314._pth", b"python314.zip\n.\n")):
            paquet.writestr(nom, contenu)
    return tampon.getvalue()


class CasRelease(unittest.TestCase):

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-release7-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        # Copie de la source avec une liste d'empreintes qui décrit les faux binaires (mêmes noms que les vrais).
        self.source = self.dossier / "source"
        for nom in release.FICHIERS:
            cible = self.source / nom
            cible.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(RACINE / nom, cible)
        for nom in release.DOSSIERS:
            shutil.copytree(RACINE / nom, self.source / nom, ignore=shutil.ignore_patterns("__pycache__"))
        self.vrai = json.loads((RACINE / "outils" / "empreintes-tiers.json").read_text(encoding="utf-8"))
        self.faux = {
            "python-%s-embed-amd64.zip" % self.vrai["python"]["version"]: faux_paquet_python(),
            "mkcert-v%s-windows-amd64.exe" % self.vrai["mkcert"]["version"]: b"MZ faux mkcert",
            "LICENSE": b"Copyright (c) 2018 The mkcert Authors (faux)",
        }
        empreintes = json.loads(json.dumps(self.vrai))
        nom_python = "python-%s-embed-amd64.zip" % empreintes["python"]["version"]
        empreintes["python"]["fichiers"][nom_python]["sha256"] = hashlib.sha256(self.faux[nom_python]).hexdigest()
        nom_mkcert = "mkcert-v%s-windows-amd64.exe" % empreintes["mkcert"]["version"]
        empreintes["mkcert"]["fichiers"][nom_mkcert]["sha256"] = hashlib.sha256(self.faux[nom_mkcert]).hexdigest()
        empreintes["mkcert"]["texte_licence"]["sha256"] = hashlib.sha256(self.faux["LICENSE"]).hexdigest()
        (self.source / "outils" / "empreintes-tiers.json").write_text(json.dumps(empreintes, ensure_ascii=False),
                                                                      encoding="utf-8")
        self.demandes = []

    def telecharger(self, adresse):
        self.demandes.append(adresse)
        nom = adresse.rsplit("/", 1)[1]
        return self.faux[nom]

    def construire(self, sortie, cache=None, telecharger=None):
        return release.construire(self.source, self.dossier / sortie, tiers=True,
                                  cache=cache or (self.dossier / "cache"), telecharger=telecharger or self.telecharger)


class TestTiers(CasRelease):

    def test_zip_contient_python_et_mkcert(self):
        chemin, _ = self.construire("a")
        version = chemin.stem.split("prevo-", 1)[1]
        prefixe = "prevo-%s/" % version
        with zipfile.ZipFile(chemin) as archive:
            noms = set(archive.namelist())
            for attendu in ("python/python.exe", "python/pythonw.exe", "python/LICENSE.txt", "python/python314._pth",
                            "outils-tiers/mkcert-v1.4.4-windows-amd64.exe", "outils-tiers/LICENCE-mkcert.txt",
                            "outils/empreintes-tiers.json", "Reinitialiser_mot_de_passe.bat", "serveur.py"):
                with self.subTest(fichier=attendu):
                    self.assertIn(prefixe + attendu, noms)
            self.assertEqual(archive.read(prefixe + "outils-tiers/mkcert-v1.4.4-windows-amd64.exe"), b"MZ faux mkcert")
            self.assertEqual(archive.read(prefixe + "python/pythonw.exe"), b"MZ faux pythonw")
            self.assertEqual([n for n in archive.namelist()], sorted(archive.namelist()))
        self.assertEqual(len(self.demandes), 3)
        self.assertTrue(any("python.org/ftp/python/3.14.9/" in d for d in self.demandes), self.demandes)
        self.assertTrue(any("FiloSottile/mkcert/releases/download/v1.4.4/" in d for d in self.demandes), self.demandes)

    def test_deterministe_et_cache(self):
        premier, _ = self.construire("a")

        def interdit(adresse):
            raise AssertionError("téléchargement inattendu : " + adresse)
        second, _ = self.construire("b", telecharger=interdit)            # tout vient du cache, intact
        self.assertEqual(premier.read_bytes(), second.read_bytes())

    def test_empreinte_fausse_rien_n_est_ecrit(self):
        nom_mkcert = "mkcert-v1.4.4-windows-amd64.exe"
        self.faux[nom_mkcert] = b"MZ binaire pas celui attendu"
        with self.assertRaises(release.ErreurConstruction) as refus:
            self.construire("c")
        self.assertIn("empreinte inattendue", str(refus.exception))
        self.assertFalse((self.dossier / "c").exists() and any((self.dossier / "c").iterdir()))
        self.assertFalse((self.dossier / "cache" / nom_mkcert).exists(), "un fichier faux n'entre pas dans le cache")

    def test_sans_tiers(self):
        chemin, _ = release.construire(self.source, self.dossier / "d", tiers=False)
        with zipfile.ZipFile(chemin) as archive:
            self.assertFalse([n for n in archive.namelist() if "/python/" in n or "/outils-tiers/" in n])

    def test_version_beta_zip_version_json_et_changelog(self):
        """2.0.0-beta.2 : nom du zip, dossier interne, version.json et section « ## [2.0.0-beta.2] » du CHANGELOG."""
        app = self.source / "js" / "app.js"
        texte = app.read_text(encoding="utf-8")
        app.write_text(re.sub(r"const VERSION = '[^']*';", "const VERSION = '2.0.0-beta.2';", texte), encoding="utf-8")
        (self.source / "CHANGELOG.md").write_text(
            "# Journal\n\n## [2.0.0-beta.2] - 2026-11-04\n\n- Une nouveauté.\n\n## [2.0.0] - 2026-10-28\n\n- Autre.\n",
            encoding="utf-8")
        chemin, _ = release.construire(self.source, self.dossier / "d", tiers=False)
        self.assertEqual(chemin.name, "prevo-2.0.0-beta.2.zip")
        with zipfile.ZipFile(chemin) as archive:
            self.assertTrue(all(n.startswith("prevo-2.0.0-beta.2/") for n in archive.namelist()))
        donnees = json.loads((self.dossier / "d" / "version.json").read_text(encoding="utf-8"))
        self.assertEqual(donnees["version"], "2.0.0-beta.2")
        self.assertEqual(donnees["adresse"], release.ADRESSE_TELECHARGEMENT)
        self.assertEqual(donnees["nouveautes"], ["Une nouveauté."])


class TestEmpreintesReelles(unittest.TestCase):

    def test_python_3_14_9_et_mkcert_1_4_4(self):
        empreintes = json.loads((RACINE / "outils" / "empreintes-tiers.json").read_text(encoding="utf-8"))
        self.assertEqual(empreintes["python"]["version"], "3.14.9")
        self.assertEqual(empreintes["python"]["fichiers"]["python-3.14.9-embed-amd64.zip"]["sha256"],
                         "3c01d7cfc666f746a6f064f60fb2156ab0ec464d3d738ab796371a46a9bb24a2")
        self.assertEqual(empreintes["mkcert"]["fichiers"]["mkcert-v1.4.4-windows-amd64.exe"]["sha256"],
                         "d2660b50a9ed59eada480750561c96abc2ed4c9a38c6a24d93e30e0977631398")
        self.assertRegex(empreintes["mkcert"]["texte_licence"]["sha256"], r"^[0-9a-f]{64}$")


class TestLanceurs(unittest.TestCase):

    def test_lancer_gmao_prefere_le_python_embarque_puis_3_11(self):
        texte = (RACINE / "Lancer_GMAO.bat").read_text(encoding="utf-8")
        embarque = texte.index('if exist "%~dp0python\\python.exe" (')
        installe = texte.index("call py -3 -c")
        self.assertLess(embarque, installe, "le Python embarqué passe avant un Python installé")
        self.assertEqual(texte.count("sys.version_info < (3, 11)"), 2)
        self.assertNotIn("(3, 8)", texte)
        self.assertIn("3.11 ou plus récent", texte)
        self.assertIn("Python.Python.3.14", texte)
        self.assertEqual((RACINE / "Lancer_GMAO.bat").read_bytes().count(b"\n"),
                         (RACINE / "Lancer_GMAO.bat").read_bytes().count(b"\r\n"), "fins de ligne CRLF")

    def test_lancer_sh_refuse_3_10_accepte_3_11(self):
        bash = bash_utilisable()
        if not bash:
            self.skipTest("bash introuvable (Git Bash sous Windows)")
        for version, attendu_code, attendu_texte in (("3.10", 1, "Python 3.11 ou plus récent est nécessaire"),
                                                     ("3.11", 0, "LANCE serveur.py --sans-navigateur")):
            with self.subTest(version=version), tempfile.TemporaryDirectory(prefix="prevo-lancer-") as dossier:
                faux = Path(dossier) / "python3"
                accepte = "0" if version == "3.11" else "1"
                faux.write_bytes(("#!/bin/sh\n"
                                  "case \"$1\" in -c) exit %s ;; esac\n"
                                  "echo \"LANCE $*\"\n" % accepte).encode("ascii"))
                faux.chmod(0o755)
                shutil.copy2(RACINE / "lancer.sh", Path(dossier) / "lancer.sh")
                chemin_bash = subprocess.run([bash, "-c", "cd \"$1\" && pwd", "_", dossier], capture_output=True,
                                             encoding="utf-8").stdout.strip()
                resultat = subprocess.run([bash, "-c", 'PATH="%s:/usr/bin:/bin" sh ./lancer.sh --sans-navigateur'
                                           % chemin_bash], cwd=dossier, capture_output=True, encoding="utf-8",
                                          errors="replace", timeout=30)
                self.assertEqual(resultat.returncode, attendu_code, resultat.stdout + resultat.stderr)
                self.assertIn(attendu_texte, resultat.stdout + resultat.stderr)

    @unittest.skipUnless(os.name == "nt", "lanceur Windows")
    def test_reinitialiser_mot_de_passe_bat(self):
        serveur = charger(RACINE / "serveur.py", "serveur_prevo_release7")
        with tempfile.TemporaryDirectory(prefix="prevo-reinit-") as dossier:
            for nom in ("serveur.py", "Reinitialiser_mot_de_passe.bat"):
                shutil.copy2(RACINE / nom, Path(dossier) / nom)
            config = serveur.Configuration(str(Path(dossier) / "donnees"), [])
            serveur.creer_compte(config, "Nicolas", "Briand", "responsable", "ancien mot de passe long")
            resultat = subprocess.run(["cmd", "/c", str(Path(dossier) / "Reinitialiser_mot_de_passe.bat")], cwd=dossier,
                                      input="nicolas.briand\r\n\r\n", capture_output=True, encoding="utf-8",
                                      errors="replace", timeout=60, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            sortie = resultat.stdout + resultat.stderr
            self.assertEqual(resultat.returncode, 0, sortie)
            self.assertIn("Mot de passe provisoire de « nicolas.briand »", sortie)
            compte = json.loads((Path(dossier) / "donnees" / "acces" / "comptes.json").read_text(encoding="utf-8"))["comptes"][0]
            self.assertTrue(compte["a_changer"])


class TestDepot(unittest.TestCase):

    def test_aucun_binaire_tiers_dans_le_depot(self):
        suivis = subprocess.run(["git", "ls-files"], cwd=str(RACINE), capture_output=True, encoding="utf-8").stdout.splitlines()
        self.assertEqual([f for f in suivis if f.startswith(("python/", "outils-tiers/")) or f.endswith(".exe")], [])
        ignore = (RACINE / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("outils-tiers/", ignore)
        self.assertIn("/python/", ignore)


if __name__ == "__main__":
    unittest.main()
