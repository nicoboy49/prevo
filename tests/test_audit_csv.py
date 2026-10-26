# -*- coding: utf-8 -*-
"""Audit E2 : le serveur refuse un CSV piégé (ARCHITECTURE.md §22.12).

Rejoue le scénario de l'annexe A du rapport d'audit (étapes 2 et 3) : un autre client que Prévo écrit
par l'API une cellule qu'Excel exécuterait à l'ouverture (=, +, @, tabulation, retour chariot, tiret
qui n'introduit pas un nombre), des octets qui ne sont pas de l'UTF-8 ou un en-tête qui n'est pas celui
du schéma. serveur.py répond 400 et ne touche pas au fichier ; la même valeur protégée par
l'apostrophe (ce que fait Prévo, §3.2) passe.

Vérifie aussi que COLONNES_PAR_TABLE de serveur.py est la recopie exacte de js/schema.js, et que
chaque fichier du jeu de démo passe la vérification (Prévo ne se refuse jamais lui-même).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_audit_csv.py" -v
"""
import hashlib
import http.client
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from commun import CasNavigateur, ServeurPrevo, RACINE, DOSSIER_DEMO, url_fichier  # noqa: E402

BOM = b"\xef\xbb\xbf"
LIGNE_PIEGE = "entreprise_nom;=cmd|' /C calc'!A0"
# Morceaux des messages de verifier_contenu_csv : le 400 vient bien de la vérification du contenu.
UTF8 = "doit être encodé en UTF-8"
ENTETE = "En-tête de"
FORMULE = "caractère de formule"
CELLULE_LIEN ='+HYPERLINK("http://exemple.invalid/";"Cliquer")'


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_audit_csv", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


def entete(table, *en_plus):
    """Ligne d'en-tête du schéma de la table, suivie des colonnes en plus (texte, sans fin de ligne)."""
    return ";".join(list(serveur.COLONNES_PAR_TABLE[table]) + list(en_plus))


def empreinte(octets):
    return hashlib.sha256(octets).hexdigest()[:16]


class TestAuditCsvServeur(unittest.TestCase):
    """Un serveur sur une copie du jeu de démo pour toute la classe."""

    @classmethod
    def setUpClass(cls):
        cls.serveur = ServeurPrevo(source=DOSSIER_DEMO)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    # -- outils -------------------------------------------------------------

    def requete(self, methode, chemin, corps=None, entetes=None):
        connexion = http.client.HTTPConnection("127.0.0.1", self.serveur.port, timeout=20)
        try:
            tout = {"X-Prevo": "1"}
            tout.update(entetes or {})
            connexion.request(methode, chemin, body=corps, headers=tout)
            reponse = connexion.getresponse()
            return reponse.status, reponse.read()
        finally:
            connexion.close()

    def lire(self, table):
        return (self.serveur.dossier / (table + ".csv")).read_bytes()

    def mettre(self, table, texte_ou_octets):
        """PUT /api/csv/<table> avec la version actuelle du fichier (le refus ne peut donc pas être un 409)."""
        corps = texte_ou_octets.encode("utf-8") if isinstance(texte_ou_octets, str) else texte_ou_octets
        version = empreinte(self.lire(table))
        return self.requete("PUT", "/api/csv/" + table, corps, {"X-Version-Attendue": version})

    def ajouter(self, table, texte_ou_octets):
        corps = texte_ou_octets.encode("utf-8") if isinstance(texte_ou_octets, str) else texte_ou_octets
        return self.requete("POST", "/api/csv/%s/ajout" % table, corps)

    def corps_parametres(self, *lignes, colonnes_en_plus=()):
        return BOM + ("\r\n".join([entete("parametres", *colonnes_en_plus)] + list(lignes)) + "\r\n").encode("utf-8")

    def ligne_journal(self, action):
        return "JRN-AUDIT;2026-10-26 10:00:00;Poste audit;responsable;ordres_travail;OT-0001;" + action

    def assert_refuse_sans_toucher(self, table, statut_et_corps, avant, motif):
        """400 avec le message de la vérification du contenu (motif), fichier identique à l'octet."""
        statut, corps = statut_et_corps
        self.assertEqual(statut, 400, corps.decode("utf-8", "replace"))
        self.assertIn(motif, corps.decode("utf-8"))
        self.assertEqual(self.lire(table), avant, "le fichier %s.csv a changé malgré le refus" % table)

    # -- refus --------------------------------------------------------------

    def test_put_parametres_formule_refuse_fichier_intact(self):
        avant = self.lire("parametres")
        self.assert_refuse_sans_toucher("parametres", self.mettre("parametres", self.corps_parametres(LIGNE_PIEGE)),
                                        avant, FORMULE)

    def test_put_journal_non_utf8_refuse(self):
        avant = self.lire("journal")
        corps = (entete("journal") + "\r\nJRN-AUDIT;2026-10-26;Poste;responsable;ordres_travail;OT-1;Réparé\r\n")
        self.assert_refuse_sans_toucher("journal", self.mettre("journal", corps.encode("cp1252")), avant, UTF8)

    def test_put_entete_hors_schema_refuse(self):
        avant = self.lire("parametres")
        for premiere_ligne in ("valeur;cle", "cle", "id;libelle", "autre;cle;valeur"):
            with self.subTest(entete=premiere_ligne):
                corps = BOM + (premiere_ligne + "\r\nentreprise_nom;Atelier\r\n").encode("utf-8")
                self.assert_refuse_sans_toucher("parametres", self.mettre("parametres", corps), avant, ENTETE)

    def test_ajout_hyperlink_refuse(self):
        avant = self.lire("journal")
        corps = entete("journal") + "\r\n" + self.ligne_journal(CELLULE_LIEN) + "\r\n"
        self.assert_refuse_sans_toucher("journal", self.ajouter("journal", corps), avant, FORMULE)

    def test_ajout_entete_hors_schema_ou_non_utf8_refuse(self):
        avant = self.lire("journal")
        self.assert_refuse_sans_toucher(
            "journal", self.ajouter("journal", "id;action\r\nJRN-AUDIT;creation\r\n"), avant, ENTETE)
        corps = (entete("journal") + "\r\n" + self.ligne_journal("Réparé") + "\r\n").encode("cp1252")
        self.assert_refuse_sans_toucher("journal", self.ajouter("journal", corps), avant, UTF8)

    def test_cellules_dangereuses_refusees(self):
        avant = self.lire("parametres")
        for valeur in ("=1+1", "+33", "@SOMME(A1)", "\tcachée", "\rcachée", "-cmd", "-", "-SOMME(A1)"):
            with self.subTest(valeur=valeur):
                corps = self.corps_parametres('note;"%s"' % valeur)
                self.assert_refuse_sans_toucher("parametres", self.mettre("parametres", corps), avant, FORMULE)

    # -- acceptations -------------------------------------------------------

    def test_valeurs_protegees_par_apostrophe_acceptees(self):
        corps = self.corps_parametres("entreprise_nom;'=cmd|' /C calc'!A0")
        statut, reponse = self.mettre("parametres", corps)
        self.assertEqual(statut, 200, reponse)
        self.assertEqual(self.lire("parametres"), corps)
        ligne = self.ligne_journal("'" + CELLULE_LIEN)
        statut, reponse = self.ajouter("journal", entete("journal") + "\r\n" + ligne + "\r\n")
        self.assertEqual(statut, 200, reponse)
        self.assertTrue(self.lire("journal").rstrip(b"\r\n").endswith(ligne.encode("utf-8")))

    def test_nombres_negatifs_et_espace_acceptes(self):
        for valeur in ("-5", "-0,5", "-.5", " =1+1", "'-cmd"):
            with self.subTest(valeur=valeur):
                corps = self.corps_parametres("seuil;" + valeur)
                statut, reponse = self.mettre("parametres", corps)
                self.assertEqual(statut, 200, reponse)
                self.assertEqual(self.lire("parametres"), corps)

    def test_colonne_en_plus_apres_le_schema_acceptee(self):
        corps = self.corps_parametres("entreprise_nom;Atelier;ajoutée dans Excel", colonnes_en_plus=("note_excel",))
        statut, reponse = self.mettre("parametres", corps)
        self.assertEqual(statut, 200, reponse)
        self.assertEqual(self.lire("parametres"), corps)


class TestDemoAcceptee(unittest.TestCase):

    def test_chaque_fichier_de_la_demo_passe_la_verification(self):
        fichiers = sorted(DOSSIER_DEMO.glob("*.csv"))
        self.assertEqual(sorted(f.stem for f in fichiers), sorted(serveur.COLONNES_PAR_TABLE))
        for fichier in fichiers:
            with self.subTest(fichier=fichier.name):
                try:
                    serveur.verifier_contenu_csv(fichier.stem, fichier.read_bytes())
                except serveur.ErreurHttp as erreur:
                    self.fail("%s refusé : %s" % (fichier.name, erreur))


class TestCoherenceSchema(CasNavigateur):

    def test_colonnes_par_table_identiques_a_schema_js(self):
        self.page.goto(url_fichier("index.html"))
        self.page.wait_for_function("typeof Schema !== 'undefined'")
        colonnes_js = self.page.evaluate(
            "Object.fromEntries(Schema.nomsTables().map((n) => [n, Schema.table(n).champs.map((c) => c.nom)]))")
        self.assertEqual(list(colonnes_js), list(serveur.TABLES))
        self.assertEqual(sorted(colonnes_js), sorted(serveur.COLONNES_PAR_TABLE))
        for table, colonnes in colonnes_js.items():
            with self.subTest(table=table):
                self.assertEqual(list(serveur.COLONNES_PAR_TABLE[table]), colonnes)


if __name__ == "__main__":
    unittest.main()
