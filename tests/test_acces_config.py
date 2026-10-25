"""Lot 7 — configuration et portées du serveur (ARCHITECTURE.md §22.1, §22.2 ; D122, D123 ; CS120 ; tâche T149).

Ce qui est vérifié :
    défaut         sans configuration, le serveur n'écoute que sur 127.0.0.1 (une connexion par une autre adresse de
                   ce PC est refusée) ;
    refus          écoute réseau sans comptes, écoute réseau sans https ni mandataire, mandataire sans comptes,
                   certificat sans clé, valeur invalide, fichier illisible : arrêt avec un message qui dit quoi faire
                   et le code de sortie 2, jamais une exception ;
    repli          comptes exigés sans aucun compte responsable : écoute ramenée à 127.0.0.1, avec l'avertissement ;
    priorité       la ligne de commande passe avant le fichier, le fichier avant les défauts ; clé inconnue signalée ;
    --aide         chaque clé de CLES_CONFIGURATION avec son type, son défaut et son aide ;
    écriture       ecrire_configuration puis lire_configuration rend les mêmes réglages ;
    journal        --journal écrit donnees/journal-serveur.log ; rotation à 1 Mo, 5 fichiers au plus.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_acces_config.py" -v
"""
import importlib.util
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

from commun import RACINE, port_libre

SCRIPT = RACINE / "serveur.py"
CODE_REFUS = 2


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_config", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


def adresse_non_bouclage():
    """Une adresse IPv4 de ce PC qui n'est pas 127.x (None si le PC n'a pas de réseau)."""
    adresses = [a for a in serveur.adresses_ip_reseau() if not a.startswith("127.")]
    return adresses[0] if adresses else None


class CasConfiguration(unittest.TestCase):

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-config-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        self.donnees = self.dossier / "donnees"
        self.config = self.dossier / "prevo.config.json"

    def ecrire(self, reglages):
        self.config.write_text(json.dumps(reglages, ensure_ascii=False), encoding="utf-8")

    def lancer_jusqu_au_bout(self, *arguments, delai=30):
        """Lance serveur.py qui doit s'arrêter tout seul (refus) : (code de sortie, console)."""
        commande = [sys.executable, str(SCRIPT), "--sans-navigateur", "--donnees", str(self.donnees),
                    "--config", str(self.config), "--port", str(port_libre())] + list(arguments)
        resultat = subprocess.run(commande, capture_output=True, encoding="utf-8", errors="replace", timeout=delai,
                                  env=dict(os.environ, PYTHONIOENCODING="utf-8"), cwd=str(RACINE))
        return resultat.returncode, resultat.stdout + resultat.stderr

    def demarrer(self, *arguments):
        """Lance serveur.py qui doit tourner : (processus, port, lignes de console lues jusqu'au démarrage)."""
        port = port_libre()
        commande = [sys.executable, str(SCRIPT), "--sans-navigateur", "--donnees", str(self.donnees),
                    "--config", str(self.config), "--port", str(port)] + list(arguments)
        processus = subprocess.Popen(commande, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(RACINE),
                                     env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1"))
        self.addCleanup(self.arreter, processus)
        lignes = []
        limite = time.time() + 20
        while time.time() < limite:
            ligne = processus.stdout.readline().decode("utf-8", "replace")
            if not ligne:
                break
            lignes.append(ligne.rstrip())
            if "Ctrl+C" in ligne:
                break
        return processus, port, lignes

    @staticmethod
    def arreter(processus):
        if processus.poll() is None:
            processus.kill()
        processus.wait(timeout=10)
        processus.stdout.close()

    def lire_ping(self, adresse, port):
        with urllib.request.urlopen("http://%s:%d/api/ping" % (adresse, port), timeout=5) as reponse:
            return json.loads(reponse.read().decode("utf-8"))


class TestDefautEtRefus(CasConfiguration):

    def test_sans_configuration_ecoute_sur_ce_pc_seulement(self):
        processus, port, lignes = self.demarrer()
        self.assertEqual(self.lire_ping("127.0.0.1", port)["application"], "Prévo")
        self.assertTrue(any("ce PC seulement (127.0.0.1)" in ligne for ligne in lignes), lignes)
        autre = adresse_non_bouclage()
        if autre is None:
            self.skipTest("aucune adresse réseau sur ce PC")
        with self.assertRaises(OSError):
            socket.create_connection((autre, port), timeout=3).close()

    def test_ecoute_reseau_sans_comptes_code_de_sortie_2(self):
        code, console = self.lancer_jusqu_au_bout("--ecoute", "0.0.0.0")
        self.assertEqual(code, CODE_REFUS, console)
        self.assertIn("sans mot de passe", console)
        self.assertIn("Démarrage refusé", console)
        self.assertNotIn("Traceback", console)

    def test_ecoute_reseau_sans_https_code_de_sortie_2(self):
        self.ecrire({"ecoute": "0.0.0.0", "comptes": True, "certificat_auto": False})
        code, console = self.lancer_jusqu_au_bout()
        self.assertEqual(code, CODE_REFUS, console)
        self.assertIn("sans https", console)
        self.assertNotIn("Traceback", console)

    def test_mandataire_sans_comptes_code_de_sortie_2(self):
        self.ecrire({"mandataire": True})
        code, console = self.lancer_jusqu_au_bout()
        self.assertEqual(code, CODE_REFUS, console)
        self.assertIn("mandataire", console)

    def test_certificat_sans_cle_code_de_sortie_2(self):
        self.ecrire({"certificat": str(self.dossier / "certificat.pem")})
        code, console = self.lancer_jusqu_au_bout()
        self.assertEqual(code, CODE_REFUS, console)
        self.assertIn("vont ensemble", console)

    def test_valeurs_invalides_et_fichier_illisible_code_de_sortie_2(self):
        for contenu, attendu in ((json.dumps({"port_http": "huit mille"}), "port_http"),
                                 (json.dumps({"ecoute": "192.168.1.10"}), "ecoute"),
                                 (json.dumps({"comptes": "oui"}), "comptes"),
                                 (json.dumps({"noms": "prevo.local"}), "noms"),
                                 (json.dumps(["pas un objet"]), "objet JSON"),
                                 ("{ pas du json", "illisible")):
            with self.subTest(contenu=contenu):
                self.config.write_text(contenu, encoding="utf-8")
                code, console = self.lancer_jusqu_au_bout()
                self.assertEqual(code, CODE_REFUS, console)
                self.assertIn(attendu, console)
                self.assertNotIn("Traceback", console)


class TestReglages(CasConfiguration):

    def test_comptes_sans_responsable_repli_sur_ce_pc(self):
        reglages = serveur.lire_configuration(None)
        reglages.update({"ecoute": "0.0.0.0", "comptes": True, "mandataire": True})
        avertissements = serveur.verifier_regles_portee(reglages, False)
        self.assertEqual(reglages["ecoute"], "127.0.0.1")
        self.assertTrue(any("Aucun compte responsable" in a for a in avertissements), avertissements)
        reglages.update({"ecoute": "0.0.0.0"})
        self.assertEqual(serveur.verifier_regles_portee(reglages, True), [])
        self.assertEqual(reglages["ecoute"], "0.0.0.0")

    def test_ligne_de_commande_avant_le_fichier_et_cle_inconnue(self):
        self.ecrire({"port_http": 9123, "noms": ["prevo.tailnet.ts.net"], "couleur": "bleu"})
        processus, port, lignes = self.demarrer()
        self.assertEqual(self.lire_ping("127.0.0.1", port)["application"], "Prévo")
        self.assertTrue(any("clé inconnue « couleur » ignorée" in ligne for ligne in lignes), lignes)
        reglages = serveur.lire_configuration(str(self.config))
        self.assertEqual(reglages["port_http"], 9123)
        self.assertEqual(reglages["noms"], ["prevo.tailnet.ts.net"])
        self.assertEqual(reglages["_inconnues"], ["couleur"])

    def test_aide_liste_chaque_cle(self):
        code, console = self.lancer_jusqu_au_bout("--aide")
        self.assertEqual(code, 0, console)
        for cle, _, _, aide in serveur.CLES_CONFIGURATION:
            with self.subTest(cle=cle):
                self.assertIn("  %s  (" % cle, console)
                self.assertIn(aide[:40], console)

    def test_ecriture_puis_lecture(self):
        reglages = serveur.reglages_par_defaut()
        reglages.update({"portee": "atelier", "ecoute": "0.0.0.0", "comptes": True, "noms": ["Prevo.Local"],
                         "port_https": 9443, "copie_sauvegardes": "E:\\Sauvegardes Prévo"})
        serveur.ecrire_atomique = serveur.ecrire_atomique       # fonction du module, écriture atomique
        serveur.ecrire_configuration(str(self.config), reglages)
        brut = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertIn("_aide", brut)
        relu = serveur.lire_configuration(str(self.config))
        for cle, _, _, _ in serveur.CLES_CONFIGURATION:
            attendu = ["prevo.local"] if cle == "noms" else reglages[cle]
            self.assertEqual(relu[cle], attendu, cle)


class TestJournal(CasConfiguration):

    def test_option_journal_ecrit_le_fichier(self):
        processus, port, lignes = self.demarrer("--journal")
        self.lire_ping("127.0.0.1", port)
        journal = self.donnees / "journal-serveur.log"
        self.assertTrue(journal.is_file())
        contenu = journal.read_text(encoding="utf-8")
        self.assertIn("serveur local de GMAO", contenu)
        self.assertRegex(contenu.splitlines()[0], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ")

    def test_rotation_a_un_mo_et_cinq_fichiers(self):
        chemin = self.dossier / "journal-serveur.log"
        journal = serveur.JournalServeur(str(chemin))
        ligne = "x" * 1000
        for _ in range(serveur.TAILLE_JOURNAL_SERVEUR // 1000 * 7):
            journal.ecrire(ligne)
        fichiers = sorted(p.name for p in self.dossier.iterdir() if p.name.startswith("journal-serveur.log"))
        self.assertEqual(fichiers, ["journal-serveur.log", "journal-serveur.log.1", "journal-serveur.log.2",
                                    "journal-serveur.log.3", "journal-serveur.log.4"])
        for nom in fichiers:
            self.assertLessEqual((self.dossier / nom).stat().st_size, serveur.TAILLE_JOURNAL_SERVEUR + 1100)


if __name__ == "__main__":
    unittest.main()
