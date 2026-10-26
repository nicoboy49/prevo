"""Lot 7 — démarrer avec la machine (ARCHITECTURE.md §22.9 ; D130 ; CS129 ; tâche T166).

Les scripts sont produits et vérifiés ligne à ligne, jamais exécutés : ils demandent des droits d'administrateur et
changent le système (tâche planifiée, pare-feu, veille). Leur exécution réelle est vérifiée en recette (CS136).

Ce qui est vérifié :
    Windows       Installer_demarrage.ps1 : tâche « Prevo » au démarrage, compte Système, délai 30 s, pythonw.exe et
                  --sans-navigateur ; règle de pare-feu entrante limitée au réseau privé et au sous-réseau local, sur
                  les deux ports ; autorité mkcert avec CAROOT ; veille sur secteur coupée avec les valeurs d'avant
                  gardées ; BOM (PowerShell 5.1) ; syntaxe acceptée par l'analyseur de PowerShell ;
                  Retirer_demarrage.ps1 : tâche et règle retirées, veille remise aux valeurs gardées ;
                  Demarrage_session.ps1 : tâche à l'ouverture de session sans droits, sinon lanceur dans Démarrage ;
    sans veille   pas de powercfg ; sans mkcert : pas d'autorité ;
    Linux         prevo.service : utilisateur dédié, Restart=on-failure, ProtectSystem, ReadWritePaths ;
    macOS         la plist se lit (plistlib) : RunAtLoad, KeepAlive, journal dans donnees/.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_acces_demarrage.py" -v
"""
import importlib.util
import plistlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from commun import RACINE

DOSSIER_PREVO = r"C:\Prevo"
PYTHONW = r"C:\Prevo\python\pythonw.exe"
MKCERT = r"C:\Prevo\outils-tiers\mkcert-v1.4.4-windows-amd64.exe"


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_demarrage", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


def syntaxe_powershell(chemin):
    """Erreurs de syntaxe d'un .ps1 selon l'analyseur de PowerShell (analyse seule, rien n'est lancé) ; None si
    PowerShell est absent."""
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return None
    commande = ("$e = $null; $t = $null; [System.Management.Automation.Language.Parser]::ParseFile('%s', [ref]$t, [ref]$e) "
                "| Out-Null; $e | ForEach-Object { $_.Message }" % str(chemin).replace("'", "''"))
    resultat = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-Command", commande],
                              capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    return resultat.stdout.strip()


class CasDemarrage(unittest.TestCase):

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-demarrage-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        self.config = serveur.Configuration(str(self.dossier / "donnees"), [])

    def produire(self, **options):
        valeurs = dict(dossier_sortie=str(self.dossier), dossier_prevo=DOSSIER_PREVO, python=PYTHONW, veille=True,
                       mkcert=MKCERT, ports=(8080, 8443), systeme="win32")
        valeurs.update(options)
        return serveur.produire_scripts_demarrage(self.config, **valeurs)


class TestWindows(CasDemarrage):

    def test_installer(self):
        ecrits = self.produire()
        self.assertEqual(sorted(ecrits), ["Demarrage_session.ps1", "Installer_demarrage.ps1", "Retirer_demarrage.ps1"])
        octets = Path(ecrits["Installer_demarrage.ps1"]).read_bytes()
        self.assertTrue(octets.startswith(b"\xef\xbb\xbf"), "BOM attendu : PowerShell 5.1")
        lignes = octets.decode("utf-8-sig").split("\r\n")
        self.assertIn('schtasks.exe --% /create /tn "Prevo" /sc onstart /delay 0000:30 /ru System /rl HIGHEST /f '
                      '/tr "\\"C:\\Prevo\\python\\pythonw.exe\\" \\"C:\\Prevo\\serveur.py\\" --sans-navigateur"', lignes)
        self.assertIn('netsh.exe --% advfirewall firewall delete rule name="Prevo"', lignes)
        self.assertIn('netsh.exe --% advfirewall firewall add rule name="Prevo" dir=in action=allow protocol=TCP '
                      'localport=8080,8443 profile=private remoteip=localsubnet program="C:\\Prevo\\python\\pythonw.exe"',
                      lignes)
        self.assertIn("$env:CAROOT = '%s'" % serveur.dossier_autorite(self.config), lignes)
        self.assertIn("& '%s' -install" % MKCERT, lignes)
        for attendue in ("powercfg.exe /change standby-timeout-ac 0", "powercfg.exe /change hibernate-timeout-ac 0",
                         "powercfg.exe /change monitor-timeout-ac 15"):
            self.assertIn(attendue, lignes)
        self.assertTrue(any("veille-avant.json" in ligne and "Set-Content" in ligne for ligne in lignes))
        self.assertFalse(any("profile=public" in ligne or "profile=any" in ligne for ligne in lignes))
        erreurs = syntaxe_powershell(ecrits["Installer_demarrage.ps1"])
        if erreurs is not None:
            self.assertEqual(erreurs, "", "syntaxe PowerShell")

    def test_retirer_et_session(self):
        ecrits = self.produire()
        retirer = Path(ecrits["Retirer_demarrage.ps1"]).read_bytes().decode("utf-8-sig").split("\r\n")
        self.assertIn('schtasks.exe --% /delete /tn "Prevo" /f', retirer)
        self.assertIn('netsh.exe --% advfirewall firewall delete rule name="Prevo"', retirer)
        self.assertIn("  powercfg.exe /change standby-timeout-ac $avant.veille", retirer)
        session = Path(ecrits["Demarrage_session.ps1"]).read_bytes().decode("utf-8-sig").split("\r\n")
        self.assertIn('schtasks.exe --% /create /tn "Prevo" /sc onlogon /rl LIMITED /f '
                      '/tr "\\"C:\\Prevo\\python\\pythonw.exe\\" \\"C:\\Prevo\\serveur.py\\" --sans-navigateur"', session)
        self.assertFalse(any("/ru System" in ligne for ligne in session))
        self.assertTrue(any("GetFolderPath('Startup')" in ligne for ligne in session))
        for nom in ("Retirer_demarrage.ps1", "Demarrage_session.ps1"):
            erreurs = syntaxe_powershell(ecrits[nom])
            if erreurs is not None:
                self.assertEqual(erreurs, "", nom)

    def test_sans_veille_ni_mkcert(self):
        ecrits = self.produire(veille=False, mkcert=None)
        texte = Path(ecrits["Installer_demarrage.ps1"]).read_bytes().decode("utf-8-sig")
        self.assertNotIn("powercfg", texte)
        self.assertNotIn("-install", texte)
        self.assertIn("schtasks.exe --% /create", texte)


class TestLinuxEtMac(CasDemarrage):

    def test_unite_systemd(self):
        ecrits = self.produire(systeme="linux", dossier_prevo="/opt/prevo", python="/usr/bin/python3")
        texte = Path(ecrits["prevo.service"]).read_text(encoding="utf-8")
        for attendue in ("User=prevo", "Group=prevo", "WorkingDirectory=/opt/prevo",
                         "ExecStart=/usr/bin/python3 /opt/prevo/serveur.py --sans-navigateur", "Restart=on-failure",
                         "ProtectSystem=full", "ProtectHome=yes", "ReadWritePaths=%s" % self.config.dossier_donnees,
                         "WantedBy=multi-user.target", "After=network-online.target"):
            self.assertIn(attendue + "\n", texte)
        commandes = serveur.commandes_systemd("/opt/prevo")
        self.assertIn("sudo systemctl enable --now prevo", commandes)

    def test_plist_launchd(self):
        ecrits = self.produire(systeme="darwin", dossier_prevo="/Users/atelier/Prevo", python="/usr/bin/python3")
        contenu = plistlib.loads(Path(ecrits["pro.prevo.serveur.plist"]).read_bytes())
        self.assertEqual(contenu["Label"], "pro.prevo.serveur")
        self.assertEqual(contenu["ProgramArguments"], ["/usr/bin/python3", "/Users/atelier/Prevo/serveur.py",
                                                       "--sans-navigateur"])
        self.assertTrue(contenu["RunAtLoad"])
        self.assertEqual(contenu["KeepAlive"], {"SuccessfulExit": False})
        self.assertEqual(contenu["StandardOutPath"], "/Users/atelier/Prevo/donnees/journal-serveur.log")


if __name__ == "__main__":
    unittest.main()
