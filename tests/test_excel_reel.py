"""Aller-retour par le vrai Microsoft Excel (tâche T17, brief §14 « Aller-retour Excel »).

Lancé seulement si PREVO_TEST_EXCEL=1 et si Excel peut être piloté (tests/excel.py, VBScript) ;
sinon les tests sont ignorés (skipTest) sans démarrer Excel.

Scénario (serveur.py sur une copie du jeu de démo) :
    1. le vrai Excel ouvre equipements.csv du dossier du serveur (comme un double-clic), on y saisit
       une ligne (identifiant suivant, repère TR-09, « Tour à commande numérique « Ébène » »,
       localisation existante, mise en service 15/03/2024, criticité « b ») et on enregistre en
       « CSV UTF-8 » ;
    2. l'application relit le fichier : le nouvel équipement est dans le Parc avec ses accents, le
       Contrôle de la base n'a aucune erreur, les valeurs protégées (n° de série à zéros en tête et à
       15 chiffres, repères) et les dates des autres lignes (réécrites JJ/MM/AAAA par Excel) sont
       relues à l'identique ;
    3. une modification dans l'application réécrit le fichier au format D5 (BOM, dates ISO,
       apostrophes) en gardant la ligne ajoutée.
Variante : enregistrement en « CSV » simple (Windows-1252) → relu sans perte d'accents, problème
« encodage » d'information seulement.

Seuls les Excel lancés par tests/excel.py sont pilotés (et arrêtés en cas de blocage) : un Excel
déjà ouvert par l'utilisateur n'est jamais touché (vérifié ici : ses processus sont toujours là).

Lancer depuis la racine du projet (Git Bash) :
    PREVO_TEST_EXCEL=1 py -m unittest discover -s tests -p "test_excel_reel.py" -v
"""
import csv
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import excel
from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

BOM = b"\xef\xbb\xbf"
DESIGNATION = "Tour à commande numérique « Ébène »"
REPERE = "TR-09"
LOCALISATION = "LOC-0002"
CHAMPS_DATE = ("date_mes", "date_fin_garantie")


def lire_csv_brut(octets, encodage="utf-8-sig"):
    """(en-tête, lignes en dictionnaires) ; valeurs brutes du fichier."""
    texte = octets.decode(encodage)
    lecteur = csv.reader(io.StringIO(texte, newline=""), delimiter=";")
    entete = next(lecteur)
    return entete, [dict(zip(entete, cellules)) for cellules in lecteur if any(cellules)]


class TestExcelReel(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        if not excel.excel_reel_demande():
            raise unittest.SkipTest("Excel réel non demandé : définir PREVO_TEST_EXCEL=1")
        # Instantané AVANT la sonde : l'Excel lancé par excel_disponible() met un moment à se fermer.
        cls.excel_utilisateur = set(excel._processus_excel())
        if not excel.excel_disponible():
            raise unittest.SkipTest("Microsoft Excel n'est pas disponible sur ce poste")
        print("\n  [excel] version %s ; Excel déjà ouverts (jamais touchés) : %s"
              % (excel.version_excel(), sorted(cls.excel_utilisateur)))
        super().setUpClass()

    def tearDown(self):
        super().tearDown()
        # Les Excel de l'utilisateur (ouverts avant le test) sont toujours là.
        restants = set(excel._processus_excel())
        self.assertTrue(self.excel_utilisateur <= restants,
                        "Excel de l'utilisateur disparu : %r" % (self.excel_utilisateur - restants))

    # -- outils -------------------------------------------------------------------

    def ouvrir(self, serveur):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(serveur.url + "/#/parc")
        attendre_pret(self.page)
        self.page.wait_for_selector("#parc-arbre")

    def saisir_dans_excel(self, chemin, format_csv):
        """Ajoute la ligne TR-09 dans Excel et enregistre `chemin` au format demandé.

        Renvoie (identifiant attribué, octets écrits par Excel)."""
        entete, lignes = lire_csv_brut(chemin.read_bytes())
        numeros = [int(l["id"][3:]) for l in lignes if re.fullmatch(r"EQ-\d{4}", l["id"])]
        identifiant = "EQ-%04d" % (max(numeros) + 1)
        ligne_excel = len(lignes) + 2                      # en-tête + lignes (une ligne Excel par enregistrement)
        colonne = {nom: position + 1 for position, nom in enumerate(entete)}
        saisies = [
            (ligne_excel, colonne["id"], identifiant),
            (ligne_excel, colonne["repere"], REPERE),
            (ligne_excel, colonne["designation"], DESIGNATION),
            (ligne_excel, colonne["localisation_id"], LOCALISATION),
            (ligne_excel, colonne["date_mes"], "15/03/2024"),
            (ligne_excel, colonne["criticite"], "b"),
        ]
        dossier = Path(tempfile.mkdtemp(prefix="prevo-excel-reel-"))
        try:
            sortie = dossier / "equipements.csv"
            excel.aller_retour_excel(chemin, sortie, format=format_csv, modifications=saisies)
            octets = sortie.read_bytes()
        finally:
            shutil.rmtree(dossier, ignore_errors=True)
        chemin.write_bytes(octets)                         # « Enregistrer » à la place du fichier
        return identifiant, octets

    def relire_dans_l_application(self, identifiant):
        page = self.page
        page.reload()
        attendre_pret(page)
        page.wait_for_selector("#parc-arbre a[href='#/equipement/%s']" % identifiant)
        self.assertIn(REPERE, page.inner_text("#parc-arbre a[href='#/equipement/%s']" % identifiant))
        page.click("#parc-arbre a[href='#/equipement/%s']" % identifiant)
        page.wait_for_function("(d) => document.querySelector('#contenu h1') && document.querySelector('#contenu h1').textContent.includes(d)",
                               arg=DESIGNATION)
        ligne = page.evaluate("(id) => Donnees.trouver('equipements', id)", identifiant)
        self.assertEqual((ligne["repere"], ligne["designation"], ligne["localisation_id"], ligne["date_mes"], ligne["criticite"]),
                         (REPERE, DESIGNATION, LOCALISATION, "2024-03-15", "B"))
        return ligne

    def problemes(self):
        return self.page.evaluate("Donnees.problemes().map((p) => [p.gravite, p.type, p.table, p.champ, p.valeur, p.message])")

    def verifier_controle_sans_erreur(self):
        page = self.page
        page.evaluate("location.hash = '#/controle'")
        page.wait_for_function("document.querySelector('#contenu h1') && document.querySelector('#contenu h1').textContent.trim() === 'Contrôle de la base'")
        erreurs = [p for p in self.problemes() if p[0] == "erreur"]
        self.assertEqual(erreurs, [])
        compteur = page.locator('[data-compteur="erreur"] .chiffre')
        if compteur.count():
            self.assertEqual(compteur.inner_text(), "0")

    def verifier_autres_lignes_identiques(self, avant, identifiant):
        apres = {l["id"]: l for l in self.page.evaluate("Donnees.lignes('equipements')")}
        self.assertEqual(set(apres) - set(avant), {identifiant})
        for ident, ligne in avant.items():
            with self.subTest(equipement=ident):
                self.assertEqual(apres[ident], ligne)

    # -- tests --------------------------------------------------------------------

    def test_excel_utf8_ajout_relu_controle_sans_erreur_puis_reecriture_d5(self):
        page = self.page
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "equipements.csv"
            original = chemin.read_bytes()
            self.ouvrir(serveur)
            avant = {l["id"]: l for l in page.evaluate("Donnees.lignes('equipements')")}
            # Le jeu de démo contient bien les valeurs pièges (sinon le test ne prouverait rien).
            series = [l["num_serie"] for l in avant.values()]
            self.assertTrue(any(re.fullmatch(r"0\d+", s) for s in series), series)
            self.assertTrue(any(re.fullmatch(r"\d{15}", s) for s in series), series)
            self.assertTrue(any(l["date_mes"] for l in avant.values()))

            identifiant, octets_excel = self.saisir_dans_excel(chemin, "utf8")
            # Excel a bien réécrit le fichier à sa façon : dates JJ/MM/AAAA
            _, lignes_excel = lire_csv_brut(octets_excel)
            dates_excel = [l["date_mes"] for l in lignes_excel if l["date_mes"]]
            self.assertTrue(dates_excel and all(re.fullmatch(r"\d{2}/\d{2}/\d{4}", d) for d in dates_excel), dates_excel[:5])
            print("\n  [excel utf8] %d octets, BOM %s, ligne ajoutée : %s"
                  % (len(octets_excel), octets_excel.startswith(BOM),
                     next(l for l in lignes_excel if l["id"] == identifiant)))

            self.relire_dans_l_application(identifiant)
            self.verifier_autres_lignes_identiques(avant, identifiant)
            self.verifier_controle_sans_erreur()
            print("  [excel utf8] problèmes signalés : %r" % (self.problemes(),))

            # Modification dans l'application → réécriture au format D5, ligne ajoutée conservée
            page.evaluate("(id) => { location.hash = '#/equipement/' + id + '/modifier'; }", identifiant)
            page.wait_for_selector("#parc-formulaire")
            page.fill("#parc-formulaire [name=marque]", "Haas")
            page.click("#parc-formulaire button[type=submit]")
            page.wait_for_function("(id) => location.hash === '#/equipement/' + id", arg=identifiant)
            page.wait_for_function("(id) => Donnees.trouver('equipements', id).marque === 'Haas'", arg=identifiant)
            octets = chemin.read_bytes()
            self.assertTrue(octets.startswith(BOM))
            # Les lignes d'origine sont réécrites octet pour octet comme avant Excel (BOM, « ; »,
            # apostrophes, dates ISO, CRLF entre les lignes), la ligne ajoutée vient à la fin.
            self.assertTrue(original.endswith(b"\r\n"))
            self.assertTrue(octets.startswith(original), "le début du fichier diffère de l'original")
            self.assertTrue(octets[len(original):].startswith(identifiant.encode("ascii") + b";"))
            self.assertTrue(octets.endswith(b"\r\n"))
            self.assertNotIn(b"\n", octets[len(original):-2])
            entete, lignes = lire_csv_brut(octets)
            entete_origine, lignes_origine = lire_csv_brut(original)
            self.assertEqual(entete, entete_origine)
            ajoutee = next(l for l in lignes if l["id"] == identifiant)
            self.assertEqual((ajoutee["repere"], ajoutee["designation"], ajoutee["date_mes"], ajoutee["criticite"], ajoutee["marque"]),
                             ("'" + REPERE, DESIGNATION, "2024-03-15", "B", "Haas"))
            # Toutes les autres lignes retrouvent exactement leur écriture d'origine (apostrophes, dates ISO)
            self.assertEqual([l for l in lignes if l["id"] != identifiant], lignes_origine)
            for ligne in lignes:
                for champ in CHAMPS_DATE:
                    if champ in ligne and ligne[champ]:
                        self.assertRegex(ligne[champ], r"^\d{4}-\d{2}-\d{2}$")

    def test_excel_csv_windows_1252_relu_sans_perte_d_accents(self):
        page = self.page
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "equipements.csv"
            self.ouvrir(serveur)
            avant = {l["id"]: l for l in page.evaluate("Donnees.lignes('equipements')")}
            identifiant, octets_excel = self.saisir_dans_excel(chemin, "ansi")
            self.assertFalse(octets_excel.startswith(BOM))
            with self.assertRaises(UnicodeDecodeError):
                octets_excel.decode("utf-8")
            self.assertIn(DESIGNATION.encode("cp1252"), octets_excel)

            self.relire_dans_l_application(identifiant)
            self.verifier_autres_lignes_identiques(avant, identifiant)
            self.verifier_controle_sans_erreur()
            encodage = [p for p in self.problemes() if p[1] == "encodage"]
            self.assertEqual([(p[0], p[2]) for p in encodage], [("info", "equipements")])
            print("\n  [excel ansi] problèmes signalés : %r" % (self.problemes(),))


if __name__ == "__main__":
    unittest.main()
