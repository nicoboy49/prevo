"""Recette « bêta 1 → bêta 2 » (chantier i18n-socle, tâche T219) : une installation Prévo 2.0.0 bêta 1 passe en
2.0.0-beta.2 SANS RIEN PERDRE. Parcours de bout en bout, comme un utilisateur, sur une COPIE du jeu f3-v2.0.0
(tests/fixtures/formats/ ; format 3 comme la bêta 2, sans derniere-version.json comme les vraies installations 2.0.0,
avec acces/comptes.json) dans un dossier temporaire ou dans l'OPFS du navigateur de test. Modèle : test_recette_socle.py
(dont les aides sont importées).

    TestBeta2Serveur   serveur avec comptes : premier démarrage de la bêta 2 → sauvegarde « avant-mise-a-jour » aux
                       octets d'origine (acces/ compris, FORMAT.md §8), aucune « avant-format-* » (format 3 des deux
                       côtés), version notée ; connexion du responsable, aucun bandeau, un équipement modifié par le
                       formulaire ; aucune perte ; second démarrage : aucune nouvelle « avant-mise-a-jour » ;
                       passage suivant (appli simulée en 2.0.0) : nouvelle sauvegarde, version 2.0.0 notée ;
                       export ZIP (vrai bouton) puis import dans une base neuve : mêmes CSV, journal + 1 ligne.
    TestBeta2Dossier   mode dossier (OPFS simulé) : mêmes contrôles, puis rechargement : rien de neuf.

CS167 : setUpModule et tearDownModule vérifient que donnees/ du dépôt n'a pas changé. Jamais de données réelles.

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_recette_beta2.py" -v
"""
import datetime
import json
import re
import shutil
import unittest
from pathlib import Path
from unittest import mock

import commun
from commun import RACINE, ServeurPrevo, comptes_json
from test_recette_socle import (DERNIERE_VERSION, DONNEES_DU_DEPOT, ERREUR_CSV_ABSENT,
                                ERREUR_SANS_SESSION, FORMAT_COURANT, MOTIF_AVANT_FORMAT, MOTIF_AVANT_MISE_A_JOUR,
                                MOTIF_QUOTIDIENNE, PREFIXE_CONSOLE_FORMAT, SERVEUR, TABLES, VERROU, VERSION_APPLI,
                                CasRecetteSocle, csv_de_la_racine, empreintes, fichiers_de, fichiers_du_jeu,
                                lignes_en_dictionnaires, lire_table, sans_manifeste, sauvegardes, une_seule,
                                valeur_comparable)

JEU = "f3-v2.0.0"
VERSION_FINALE = "2.0.0"
DESIGNATION = "Pompe de refroidissement (recette bêta 2)"
CHANGEES = {"equipements.csv": {("EQ-0005", "designation")}}
# Fichiers de données qu'une session du responsable peut réécrire (OT préventifs générés à l'ouverture, journal).
ECRITS_PAR_UNE_SESSION = {"equipements.csv", "journal.csv", "ordres_travail.csv", "ot_operations.csv"}


def setUpModule():
    DONNEES_DU_DEPOT.clear()
    DONNEES_DU_DEPOT.update(empreintes(RACINE / "donnees"))


def tearDownModule():
    if empreintes(RACINE / "donnees") != DONNEES_DU_DEPOT:
        raise AssertionError("CS167 : le dossier donnees/ du dépôt a changé pendant la recette.")


def version_notee(fichiers):
    return json.loads(fichiers[DERNIERE_VERSION].decode("utf-8"))["version"]


class CasBeta2(CasRecetteSocle):

    def verifier_passage(self, origine, copies, vers, de):
        """Une seule « avant-mise-a-jour » (aux octets d'origine, acces/ compris), aucune « avant-format-* »."""
        maj = une_seule(copies, MOTIF_AVANT_MISE_A_JOUR)
        self.assertEqual([n for n in copies if MOTIF_AVANT_FORMAT.match(n) or "avant-format" in n], [])
        self.assertEqual(sorted(copies), sorted([maj, datetime.date.today().isoformat()]))
        self.assertEqual(sans_manifeste(copies[maj]), origine)
        self.verifier_manifeste(copies[maj], "avant-mise-a-jour", FORMAT_COURANT, "serveur" if self.mode == "serveur"
                                else "dossier", {"de": de, "vers": vers})
        return maj

    mode = "serveur"


def copie_du_dossier(dossier, destination):
    shutil.copytree(dossier, destination)
    return Path(destination)


class ServeurVersion(ServeurPrevo):
    """Le même serveur.py, mais d'une autre version (VERSION_APPLICATION réécrite dans une copie du fichier)."""

    def __init__(self, version, racine_temporaire, **options):
        super().__init__(**options)
        self.version = version
        self.racine_version = Path(racine_temporaire)

    def demarrer(self):
        self.racine_version.mkdir(parents=True, exist_ok=True)
        texte = (RACINE / "serveur.py").read_text(encoding="utf-8")
        modifie = re.sub(r"^VERSION_APPLICATION = '[^']+'", "VERSION_APPLICATION = '%s'" % self.version, texte,
                         count=1, flags=re.M)
        assert modifie != texte
        (self.racine_version / "serveur.py").write_text(modifie, encoding="utf-8", newline="\n")
        with mock.patch.object(commun, "RACINE", self.racine_version):
            super().demarrer()


# ---------------------------------------------------------------------------
# 1. Mode serveur, avec comptes
# ---------------------------------------------------------------------------

class TestBeta2Serveur(CasBeta2):

    def preparer(self):
        self.autoriser_erreur(ERREUR_CSV_ABSENT)
        self.autoriser_erreur(ERREUR_SANS_SESSION)
        source = self.jeu(JEU)
        (source / "acces").mkdir(exist_ok=True)
        (source / "acces" / "comptes.json").write_bytes(comptes_json())      # comptes de test (mots de passe connus)
        origine = fichiers_de(source)
        self.assertNotIn(DERNIERE_VERSION, origine)                          # une installation 2.0.0 bêta 1
        return source, origine

    def test_beta1_vers_beta2_sauvegarde_connexion_modification_sans_perte_puis_passage_suivant(self):
        source, origine = self.preparer()
        suite = self.temporaire / "suite"
        with ServeurPrevo(source=source, comptes=True) as serveur:
            demarre = fichiers_de(serveur.dossier)
            console = serveur.sortie_console()
            copies = sauvegardes(demarre)
            maj = self.verifier_passage(origine, copies, VERSION_APPLI, None)
            self.assertIn("sauvegarde %s faite avant la mise à jour" % maj, console)
            self.assertNotIn(PREFIXE_CONSOLE_FORMAT, console)
            self.assertEqual(VERSION_APPLI, "2.0.0-beta.2")
            self.assertEqual(version_notee(demarre), "2.0.0-beta.2")
            self.assertEqual(csv_de_la_racine(demarre), csv_de_la_racine(origine))     # aucune migration
            self.assertEqual(demarre["acces/comptes.json"], origine["acces/comptes.json"])

            # Le responsable se connecte par l'écran de connexion : aucun bandeau d'erreur, ni lecture seule.
            self.page.goto(serveur.url + "/#/accueil")
            self.se_connecter(self.page, "responsable")
            self.assertEqual(self.page.evaluate("App.profil.type"), "responsable")
            self.page.wait_for_load_state("networkidle")
            self.aucun_bandeau()
            self.assertEqual(self.page.evaluate("Donnees.etatDuFormat().depart"), FORMAT_COURANT)
            self.modifier_equipement(DESIGNATION)
            apres = fichiers_de(serveur.dossier)
            self.page.goto("about:blank")

            equipement = next(l for l in lignes_en_dictionnaires(apres["equipements.csv"]) if l["id"] == "EQ-0005")
            self.assertEqual(equipement["designation"], DESIGNATION)
            changes = self.verifier_aucune_perte(origine, apres, CHANGEES)
            self.assertIn("equipements.csv", changes)
            self.assertLessEqual(set(changes), ECRITS_PAR_UNE_SESSION, changes)
            for chemin, octets in csv_de_la_racine(origine).items():          # tous les autres CSV : à l'octet
                if chemin not in changes:
                    self.assertEqual(apres[chemin], octets, chemin)
            self.verifier_rien_sans_sauvegarde(origine, apres)
            self.assertEqual(apres["acces/comptes.json"], origine["acces/comptes.json"])
            self.assertEqual(version_notee(apres), "2.0.0-beta.2")
            self.assertEqual(sorted(sauvegardes(apres)), sorted(copies))     # toujours une seule « avant-mise-a-jour »
            copie_du_dossier(serveur.dossier, suite)
            copie_du_dossier(serveur.dossier, self.temporaire / "pour-export")

        # Second démarrage, même version : aucune nouvelle « avant-mise-a-jour ».
        avant_second = fichiers_de(suite)
        with ServeurPrevo(source=suite, comptes=True) as second:
            noms = sauvegardes(fichiers_de(second.dossier))
            self.assertEqual(sorted(noms), sorted(sauvegardes(avant_second)))
            self.assertEqual(sum(1 for n in noms if MOTIF_AVANT_MISE_A_JOUR.match(n)), 1)
            self.assertEqual(version_notee(fichiers_de(second.dossier)), "2.0.0-beta.2")

        # Passage suivant : l'appli est la 2.0.0 (finale) → nouvelle sauvegarde, version 2.0.0 notée, aucune perte.
        with ServeurVersion(VERSION_FINALE, self.temporaire / "appli-finale", source=suite, comptes=True) as finale:
            apres_finale = fichiers_de(finale.dossier)
            console = finale.sortie_console()
            copies = sauvegardes(apres_finale)
            mises_a_jour = sorted(n for n in copies if MOTIF_AVANT_MISE_A_JOUR.match(n))
            self.assertEqual(len(mises_a_jour), 2, sorted(copies))
            nouvelle = next(n for n in mises_a_jour if n not in sauvegardes(avant_second))
            contenu = sans_manifeste(copies[nouvelle])
            for chemin, octets in csv_de_la_racine(avant_second).items():       # l'état d'avant, à l'octet
                self.assertEqual(contenu[chemin], octets, chemin)
            self.assertEqual(contenu["acces/comptes.json"], origine["acces/comptes.json"])
            self.verifier_manifeste(copies[nouvelle], "avant-mise-a-jour", FORMAT_COURANT, "serveur",
                                    {"de": "2.0.0-beta.2", "vers": VERSION_FINALE})
            self.assertIn("sauvegarde %s faite avant la mise à jour" % nouvelle, console)
            self.assertEqual(version_notee(apres_finale), VERSION_FINALE)
            for chemin, octets in csv_de_la_racine(avant_second).items():
                self.assertEqual(apres_finale[chemin], octets, chemin)
            self.assertEqual(apres_finale["acces/comptes.json"], origine["acces/comptes.json"])

    def test_export_zip_puis_import_dans_une_base_neuve_memes_csv_journal_plus_une_ligne(self):
        source, origine = self.preparer()
        chemin_zip = None
        with ServeurPrevo(source=source, comptes=True) as serveur:
            self.page.goto(serveur.url + "/#/accueil")
            self.se_connecter(self.page, "responsable")
            self.page.wait_for_load_state("networkidle")
            self.aucun_bandeau()
            self.modifier_equipement(DESIGNATION)
            self.aller("#/parametres", "#btn-export-zip")
            nom_zip, noms, entrees, chemin_zip = self.exporter()
            base_a = fichiers_de(serveur.dossier)
            self.page.goto("about:blank")
        manifeste = self.verifier_zip_export(nom_zip, noms, entrees, {}, "serveur", FORMAT_COURANT)
        self.assertEqual(manifeste["version_appli"], "2.0.0-beta.2")
        for table in TABLES:                       # l'export est la base A, table par table (cellules)
            self.assertEqual(lire_table(entrees[table + ".csv"]), lire_table(base_a.get(table + ".csv", b"")), table)

        # Base neuve (f3-v1.2.0 : même format, autres données), comptes exigés : import par le responsable.
        cible = self.jeu("f3-v1.2.0", "neuve")
        with ServeurPrevo(source=cible, comptes=True) as neuve:
            self.page.goto(neuve.url + "/#/parametres")
            self.se_connecter(self.page, "responsable")
            self.page.wait_for_selector("#btn-import-zip")
            self.page.set_input_files("#fichier-import-zip", str(chemin_zip))
            self.page.wait_for_selector("#confirmation-import-zip")
            self.page.click("dialog button:has-text('Remplacer')")
            self.page.wait_for_selector("#import-zip-termine")
            importee = fichiers_de(neuve.dossier)
            self.page.goto("about:blank")
        for table in TABLES:
            nom = table + ".csv"
            if table == "journal":
                continue
            entete, lignes = lire_table(entrees[nom])
            entete_i, lignes_i = lire_table(importee.get(nom, b""))
            self.assertEqual((entete_i, [[valeur_comparable(c) for c in l] for l in lignes_i]),
                             (entete, [[valeur_comparable(c) for c in l] for l in lignes]), table)
        entete, lignes = lire_table(entrees["journal.csv"])
        entete_i, lignes_i = lire_table(importee["journal.csv"])
        self.assertEqual(entete_i, entete)
        self.assertEqual(lignes_i[:len(lignes)], lignes)
        self.assertEqual(len(lignes_i), len(lignes) + 1)
        self.assertIn("import", " ".join(lignes_i[-1]).lower())


# ---------------------------------------------------------------------------
# 2. Mode dossier (OPFS simulé)
# ---------------------------------------------------------------------------

class TestBeta2Dossier(CasBeta2):
    mode = "dossier"

    def setUp(self):
        super().setUp()
        self.demarrer_statique()

    def test_beta1_vers_beta2_en_mode_dossier_sauvegarde_modification_sans_perte_puis_rechargement(self):
        origine = fichiers_du_jeu(JEU)
        self.assertNotIn(DERNIERE_VERSION, origine)
        # Mode dossier : les sauvegardes gardent les tables, pas acces/ (qui n'est jamais touché, FORMAT.md §8).
        sans_acces = {c: o for c, o in origine.items() if not c.startswith("acces/")}
        self.ouvrir_dossier(origine, "responsable")
        demarre = self.instantane()
        copies = sauvegardes(demarre)
        maj = une_seule(copies, MOTIF_AVANT_MISE_A_JOUR)
        for nom, contenu in copies.items():
            self.assertTrue(nom == maj or MOTIF_QUOTIDIENNE.match(nom), sorted(copies))      # aucune « avant-format »
            self.assertEqual(sans_manifeste(contenu), sans_acces, nom)
        self.verifier_manifeste(copies[maj], "avant-mise-a-jour", FORMAT_COURANT, "dossier",
                                {"de": None, "vers": VERSION_APPLI})
        self.assertEqual(version_notee(demarre), "2.0.0-beta.2")
        self.verifier_aucune_perte(origine, demarre)       # l'ouverture crée les tables absentes, génère les OT
        self.aucun_bandeau()
        self.assertEqual(self.page.evaluate("Donnees.etatDuFormat().depart"), FORMAT_COURANT)

        self.modifier_equipement(DESIGNATION)
        apres = self.instantane()
        equipement = next(l for l in lignes_en_dictionnaires(apres["equipements.csv"]) if l["id"] == "EQ-0005")
        self.assertEqual(equipement["designation"], DESIGNATION)
        changes = self.verifier_aucune_perte(origine, apres, CHANGEES)
        self.assertIn("equipements.csv", changes)
        self.assertLessEqual(set(changes), ECRITS_PAR_UNE_SESSION, changes)
        for chemin, octets in csv_de_la_racine(origine).items():
            if chemin not in changes:
                self.assertEqual(apres[chemin], octets, chemin)
        self.verifier_rien_sans_sauvegarde(origine, apres)
        self.assertEqual(apres["acces/comptes.json"], origine["acces/comptes.json"])
        self.assertEqual(sorted(sauvegardes(apres)), sorted(copies))

        # Rechargement : rien de neuf (verrou.txt mis à part).
        self.rouvrir_dossier()
        sans_verrou = lambda instantane: {c: o for c, o in instantane.items() if c != VERROU}  # noqa: E731
        self.assertEqual(sans_verrou(self.instantane()), sans_verrou(apres))


if __name__ == "__main__":
    unittest.main()
