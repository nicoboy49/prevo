"""Lot 7 — comptes côté serveur (ARCHITECTURE.md §22.3 ; D124 ; CS121 ; tâche T150).

Ce qui est vérifié :
    hachage        l'empreinte stockée est égale au calcul indépendant de tests/calcul_acces.py (scrypt, et le repli
                   PBKDF2 avec le nom de l'algorithme stocké) ; deux comptes au même mot de passe ont des sels et des
                   empreintes différents ; comparaison juste et fausse ;
    règles         11 caractères refusés, 12 acceptés, aucune règle de composition, 257 refusés ;
    comptes        identifiants « prenom.nom » sans accents, suffixe si pris (même personne refusée sans
                   autre_personne, T301) ; technicien lié obligatoire ; au moins
                   un responsable actif ; le fichier ne contient jamais le mot de passe en clair ; compte_public sans
                   sel ni empreinte ;
    ligne de cmd   --reinitialiser donne un provisoire de 16 caractères, à changer, qui ouvre le compte ; code 1 sans
                   comptes ;
    journal        chaque création ou réinitialisation écrit une ligne dans journal-acces.csv (BOM, « ; »,
                   apostrophe devant une cellule qui commence par = + - @) ;
    sauvegardes    une sauvegarde copie acces/ sauf sessions.json ; /api/restauration ne restaure jamais comptes.json.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_acces_comptes.py" -v
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import calcul_acces
from commun import RACINE

SCRIPT = RACINE / "serveur.py"


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_comptes", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


class CasComptes(unittest.TestCase):

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-comptes-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        self.config = serveur.Configuration(str(self.dossier / "donnees"), [])
        serveur.creer_dossiers(self.config)

    def comptes_bruts(self):
        return json.loads((self.dossier / "donnees" / "acces" / "comptes.json").read_text(encoding="utf-8"))["comptes"]


class TestHachage(CasComptes):

    def test_empreinte_egale_au_calcul_independant(self):
        serveur.creer_compte(self.config, "Nicolas", "Briand", "responsable", "une phrase de passe assez longue")
        compte = self.comptes_bruts()[0]
        self.assertEqual(compte["algo"], "scrypt-n15-r8-p3")
        self.assertEqual(compte["empreinte"], calcul_acces.empreinte(compte["algo"], "une phrase de passe assez longue",
                                                                     compte["sel"]))
        self.assertTrue(serveur.mot_de_passe_juste(compte, "une phrase de passe assez longue"))
        self.assertFalse(serveur.mot_de_passe_juste(compte, "une phrase de passe assez longuE"))
        self.assertFalse(serveur.mot_de_passe_juste(compte, None))

    def test_repli_pbkdf2_avec_le_nom_stocke(self):
        algo, sel, empreinte = serveur.hacher_mot_de_passe("mot de passe de repli", algo=serveur.ALGO_PBKDF2)
        self.assertEqual(algo, "pbkdf2-sha256-600000")
        self.assertEqual(empreinte, calcul_acces.empreinte(algo, "mot de passe de repli", sel))
        compte = {"algo": algo, "sel": sel, "empreinte": empreinte}
        self.assertTrue(serveur.mot_de_passe_juste(compte, "mot de passe de repli"))

    def test_sels_differents_pour_le_meme_mot_de_passe(self):
        serveur.creer_compte(self.config, "Julien", "Moreau", "technicien", "meme mot de passe 2026", technicien_id="TEC-0001")
        serveur.creer_compte(self.config, "Karim", "Benali", "technicien", "meme mot de passe 2026", technicien_id="TEC-0002")
        premier, second = self.comptes_bruts()
        self.assertNotEqual(premier["sel"], second["sel"])
        self.assertNotEqual(premier["empreinte"], second["empreinte"])
        texte = (self.dossier / "donnees" / "acces" / "comptes.json").read_text(encoding="utf-8")
        self.assertNotIn("meme mot de passe 2026", texte)


class TestRegles(CasComptes):

    def test_longueurs(self):
        with self.assertRaises(serveur.ErreurCompte):
            serveur.creer_compte(self.config, "A", "B", "responsable", "x" * 11)
        serveur.creer_compte(self.config, "A", "B", "responsable", "x" * 12)
        serveur.creer_compte(self.config, "C", "D", "responsable", "aaaaaaaaaaaa")      # aucune règle de composition
        with self.assertRaises(serveur.ErreurCompte):
            serveur.creer_compte(self.config, "E", "F", "responsable", "x" * 257)

    def test_identifiants_technicien_lie_et_dernier_responsable(self):
        premier = serveur.creer_compte(self.config, "Élodie", "Le Gall", "responsable", "phrase de passe solide")
        # T301 : même prénom et même nom (accents et casse ignorés) : refusé, sauf « C'est une autre personne ».
        with self.assertRaises(serveur.ErreurCompte):
            serveur.creer_compte(self.config, "Elodie", "le gall", "demandeur", "phrase de passe solide")
        second = serveur.creer_compte(self.config, "Elodie", "le gall", "demandeur", "phrase de passe solide",
                                      autre_personne=True)
        self.assertEqual(premier["identifiant"], "elodie.le-gall")
        self.assertEqual(second["identifiant"], "elodie.le-gall.2")
        self.assertNotIn("empreinte", premier)
        self.assertNotIn("sel", premier)
        with self.assertRaises(serveur.ErreurCompte):
            serveur.creer_compte(self.config, "Sans", "Technicien", "technicien", "phrase de passe solide")
        with self.assertRaises(serveur.ErreurCompte):
            serveur.modifier_compte(self.config, "elodie.le-gall", actif=False)     # dernier responsable actif
        self.assertTrue(serveur.responsable_actif_existe(self.config))
        serveur.modifier_compte(self.config, "elodie.le-gall.2", role="responsable")
        serveur.modifier_compte(self.config, "elodie.le-gall", actif=False)
        self.assertTrue(serveur.responsable_actif_existe(self.config))


class TestLigneDeCommande(CasComptes):

    def lancer(self, *arguments):
        commande = [sys.executable, str(SCRIPT), "--sans-navigateur", "--donnees", str(self.dossier / "donnees"),
                    "--config", str(self.dossier / "absent.json")] + list(arguments)
        resultat = subprocess.run(commande, capture_output=True, encoding="utf-8", errors="replace", timeout=60,
                                  env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        return resultat.returncode, resultat.stdout + resultat.stderr

    def test_reinitialiser_sans_comptes_code_1(self):
        code, console = self.lancer("--reinitialiser", "personne")
        self.assertEqual(code, 1, console)
        self.assertIn("Aucun compte", console)
        self.assertNotIn("Traceback", console)

    def test_reinitialiser_donne_un_provisoire_a_changer(self):
        serveur.creer_compte(self.config, "Nicolas", "Briand", "responsable", "ancien mot de passe long")
        code, console = self.lancer("--reinitialiser", "Nicolas.Briand")
        self.assertEqual(code, 0, console)
        provisoire = console.split("« nicolas.briand » : ")[1].split()[0]
        self.assertEqual(len(provisoire), 16)
        compte = self.comptes_bruts()[0]
        self.assertTrue(compte["a_changer"])
        self.assertTrue(serveur.mot_de_passe_juste(compte, provisoire))
        self.assertFalse(serveur.mot_de_passe_juste(compte, "ancien mot de passe long"))
        code, console = self.lancer("--reinitialiser", "inconnu.personne")
        self.assertEqual(code, 1, console)
        self.assertIn("introuvable", console)


class TestJournalEtSauvegardes(CasComptes):

    def test_journal_des_acces(self):
        serveur.creer_compte(self.config, "Nicolas", "Briand", "responsable", "phrase de passe solide")
        serveur.ecrire_journal_acces(self.config, "=cmd|' /C calc'!A0", "192.168.1.20", "-Navigateur", "echec")
        octets = (self.dossier / "donnees" / "acces" / "journal-acces.csv").read_bytes()
        self.assertTrue(octets.startswith(b"\xef\xbb\xbf"))
        lignes = octets.decode("utf-8-sig").splitlines()
        self.assertEqual(lignes[0], "date;qui;adresse;agent;resultat;tailscale")
        self.assertIn(";nicolas.briand;;;creation;", lignes[1])
        self.assertEqual(len(lignes), 3)
        self.assertIn("'=cmd", lignes[2])
        self.assertIn("'-Navigateur", lignes[2])

    def test_sauvegarde_copie_acces_sans_sessions_et_restauration_ne_les_touche_pas(self):
        serveur.creer_compte(self.config, "Nicolas", "Briand", "responsable", "phrase de passe solide")
        acces = self.dossier / "donnees" / "acces"
        (acces / "sessions.json").write_text("{}", encoding="utf-8")
        (self.dossier / "donnees" / "equipements.csv").write_text("id;libelle\r\nEQ-0001;Pompe\r\n", encoding="utf-8")
        nom = serveur.nouveau_nom_horodate(self.config)
        serveur.copier_tables_dans_sauvegarde(self.config, nom)
        copie = self.dossier / "donnees" / "sauvegardes" / nom
        self.assertTrue((copie / "acces" / "comptes.json").is_file())
        self.assertTrue((copie / "acces" / "journal-acces.csv").is_file())
        self.assertFalse((copie / "acces" / "sessions.json").exists())
        # un compte créé après la sauvegarde n'est pas effacé par la restauration
        serveur.creer_compte(self.config, "Julien", "Moreau", "technicien", "phrase de passe solide", technicien_id="TEC-0001")
        serveur.restaurer(self.config, nom, None)
        self.assertEqual([c["identifiant"] for c in self.comptes_bruts()], ["nicolas.briand", "julien.moreau"])


if __name__ == "__main__":
    unittest.main()
