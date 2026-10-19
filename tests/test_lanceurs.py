"""Tests des lanceurs Lancer_GMAO.bat (Windows) et lancer.sh (Mac/Linux).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_lanceurs.py" -v
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BASH_GIT = Path(r"C:\Program Files\Git\bin\bash.exe")


def bash_disponible():
    """Chemin d'un bash utilisable (Git Bash sous Windows, bash sinon), ou None."""
    if os.name == "nt":
        return str(BASH_GIT) if BASH_GIT.exists() else None
    return shutil.which("bash")


def port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def arreter(proc):
    """Arrête le processus et tous ses enfants."""
    if proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                           capture_output=True)
        else:
            proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


class LancementMixin:
    def verifier_lancement(self, commande):
        tmp = tempfile.mkdtemp(prefix="prevo_lanceur_")
        proc = None
        try:
            port = port_libre()
            proc = subprocess.Popen(
                commande + ["--sans-navigateur", "--port", str(port), "--donnees", tmp],
                cwd=str(RACINE), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            fin = time.time() + 20
            reponse = None
            while time.time() < fin and reponse is None:
                if proc.poll() is not None:
                    self.fail("le lanceur s'est arrêté (code %s)" % proc.returncode)
                try:
                    with urllib.request.urlopen(
                            "http://127.0.0.1:%d/api/ping" % port, timeout=2) as r:
                        reponse = json.loads(r.read().decode("utf-8"))
                except OSError:
                    time.sleep(0.3)
            self.assertIsNotNone(reponse, "/api/ping n'a pas répondu en 20 s")
            self.assertEqual(reponse.get("application"), "Prévo")
        finally:
            if proc is not None:
                arreter(proc)
            shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(os.name == "nt", "Lancer_GMAO.bat ne tourne que sous Windows")
class TestBat(LancementMixin, unittest.TestCase):
    def setUp(self):
        self.octets = (RACINE / "Lancer_GMAO.bat").read_bytes()
        self.texte = self.octets.decode("utf-8")

    def test_fins_de_ligne_crlf(self):
        self.assertIn(b"\r\n", self.octets)
        self.assertNotIn(b"\n", self.octets.replace(b"\r\n", b""))

    def test_contenu(self):
        t = self.texte
        self.assertIn("winget install -e --id Python.Python.3.12 "
                      "--accept-package-agreements --accept-source-agreements", t)
        self.assertIn("choice /C ON", t)
        self.assertIn("https://www.python.org/downloads/", t)
        self.assertIn("réseau privé", t)
        self.assertIn("pare-feu", t)
        self.assertIn("chcp 65001", t)
        self.assertIn("%*", t)

    def test_python_absent_ou_alias_store_refuse_sans_installer(self):
        """Faux py/python (code 9009, comme l'alias du Store) : aucun serveur, lien python.org.

        Un faux winget (en tête du PATH du sous-processus seulement) note tout appel
        d'installation dans un journal : la réponse « N » doit mener à l'aide manuelle.
        """
        dossier = Path(tempfile.mkdtemp(prefix="prevo_faux_python_"))
        try:
            for nom in ("py.cmd", "python.cmd"):
                (dossier / nom).write_text("@echo off\r\nexit /b 9009\r\n", encoding="ascii")
            (dossier / "winget.cmd").write_text(
                "@echo off\r\n"
                'if "%1"=="--version" exit /b 0\r\n'
                'echo installation >> "%~dp0winget-appel.log"\r\n'
                "exit /b 1\r\n", encoding="ascii")
            env = dict(os.environ)
            env["PATH"] = str(dossier) + os.pathsep + env.get("PATH", "")
            r = subprocess.run(["cmd", "/c", ".\\Lancer_GMAO.bat"], cwd=str(RACINE), env=env,
                               input=b"N\r\n\r\n\r\n", stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=60)
            sortie = r.stdout.decode("utf-8", errors="replace")
            self.assertFalse((dossier / "winget-appel.log").exists(), "winget install a été lancé")
            self.assertIn("Installer Python maintenant", sortie)   # la question a bien été posée
            self.assertIn("https://www.python.org/downloads/", sortie)
            self.assertNotIn("pare-feu", sortie)                   # le serveur n'a pas été préparé
            self.assertNotIn("Le serveur s'est arrêté", sortie)
            self.assertEqual(r.returncode, 1, sortie)
        finally:
            shutil.rmtree(dossier, ignore_errors=True)

    def test_version_minimale_verifiee(self):
        self.assertIn("sys.version_info < (3, 8)", self.texte)

    def test_lancement(self):
        self.verifier_lancement(["cmd", "/c", ".\\Lancer_GMAO.bat"])


class TestSh(LancementMixin, unittest.TestCase):
    def setUp(self):
        self.octets = (RACINE / "lancer.sh").read_bytes()
        self.texte = self.octets.decode("utf-8")

    def test_fins_de_ligne_lf(self):
        self.assertNotIn(b"\r", self.octets)
        self.assertTrue(self.texte.startswith("#!/bin/sh\n"))

    def test_aucune_installation_executee(self):
        for ligne in self.texte.splitlines():
            s = ligne.strip()
            if s.startswith("#"):
                continue
            if "winget" in s or "apt install" in s or "brew install" in s:
                # seulement permis dans un message d'aide (echo)
                self.assertTrue(s.startswith("echo "), "commande d'installation : " + s)
        self.assertIn('exec "$PYTHON" serveur.py "$@"', self.texte)

    def test_syntaxe_sh(self):
        bash = bash_disponible()
        if not bash:
            self.skipTest("bash introuvable")
        r = subprocess.run([bash, "-c", "sh -n lancer.sh"], cwd=str(RACINE),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_lancement(self):
        bash = bash_disponible()
        if not bash:
            self.skipTest("bash introuvable")
        self.verifier_lancement([bash, "lancer.sh"])


if __name__ == "__main__":
    unittest.main()
