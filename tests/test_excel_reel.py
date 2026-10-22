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

Format v2 (lot 2, tâche T34 ; ARCHITECTURE.md §14.1) :
    v2   le vrai Excel ouvre equipements.csv (nouvel équipement, valeur_remplacement saisie
         « 12500,5 »), demandes.csv (description d'une DI) et ordres_travail.csv (titre d'un OT),
         chacun enregistré en « CSV UTF-8 » ; l'application relit sans erreur : 12 500,50 € HT
         affichés, symptome_code, ot_origine_id et anomalie_constatee de toutes les lignes identiques
         à l'avant-Excel ; une DI acceptée et un équipement modifié dans l'application réécrivent les
         trois fichiers au format D5 en conservant toutes les lignes ;
    lot1 base complète du lot 1 (tag git lot-1, dont les quatre fichiers de tests/fixtures/v1/) ; ces
         quatre fichiers passent par Excel (ouvrir, enregistrer) ; ouverture (demandeur) : sauvegarde
         « avant format 2 » puis version_schema = 2, aucun problème « attention » ni « erreur », les
         colonnes v2 absentes en « info », données identiques au fichier d'origine ; une DI créée, un
         équipement modifié, la DI acceptée ajoutent chacune des colonnes v2 en fin de table, toutes
         les autres cellules restant celles du lot 1.

Import (lot 5, tâche T86 ; ARCHITECTURE.md §18.3, §18.10) :
    xls  la liste du parc des fichiers d'essai (tests/fixtures/import/equipements.xlsx) ouverte par le vrai Excel
         et enregistrée en « Classeur Excel 97-2003 » (.xls) : Import.lire (démo, file://) lit ce .xls comme le
         .xlsx (mêmes feuilles, mêmes cellules en texte : dates AAAA-MM-JJ, « 007 », « 1E5 », « 00481723 ») et
         l'aperçu donne les mêmes actions, ligne par ligne (LISEZMOI : 5 créer, 1 mettre à jour, 14 identique,
         3 refusée).

Seuls les Excel lancés par tests/excel.py sont pilotés (et arrêtés en cas de blocage) : un Excel
déjà ouvert par l'utilisateur n'est jamais touché (vérifié ici : ses processus sont toujours là).

Lancer depuis la racine du projet (Git Bash) :
    PREVO_TEST_EXCEL=1 py -m unittest discover -s tests -p "test_excel_reel.py" -v
"""
import base64
import csv
import io
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import excel
import test_format_v2 as format_v2      # import du module (pas de ses classes) : ses tests ne sont pas relancés ici
from commun import (CasNavigateur, DOSSIER_DEMO, RACINE, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo,
                    url_fichier)
from test_import_lecture import normaliser

FIXTURES_IMPORT = RACINE / "tests" / "fixtures" / "import"
XL_EXCEL8 = 56                                   # XlFileFormat : « Classeur Excel 97-2003 » (.xls)
SIGNATURE_OLE = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1])
# Lecture de classeurs (nom, base64) par Import.lire, puis aperçu du parc sur la démo (correspondance automatique).
LIRE_CLASSEURS_JS = """async (classeurs) => {
  const resultats = {};
  for (const [nom, contenu] of classeurs) {
    const lu = await Import.lire(new File([Uint8Array.from(atob(contenu), (c) => c.charCodeAt(0))], nom));
    const lignes = lu.feuilles[0].lignes;
    const rang = Import.ligneEntete(lignes, 'equipements');
    const donnees = lignes.slice(rang + 1);
    const correspondance = Import.correspondance('equipements', Import.entetes(lignes, rang, false), donnees, 'auto');
    const apercu = Import.preparer('equipements', donnees, correspondance, { numeroPremiereLigne: rang + 2 });
    resultats[nom] = { format: lu.format, feuilles: lu.feuilles, rang, totaux: apercu.totaux,
                       actions: apercu.lignes.map((l) => [l.numero, l.action]) };
  }
  return resultats;
}"""

BOM = b"\xef\xbb\xbf"
DESIGNATION = "Tour à commande numérique « Ébène »"
REPERE = "TR-09"
LOCALISATION = "LOC-0002"
CHAMPS_DATE = ("date_mes", "date_fin_garantie")

# Format v2 : nouvel équipement saisi dans Excel, cellules modifiées dans demandes et ordres_travail.
REPERE_V2 = "BE-02"
DESIGNATION_V2 = "Banc d'essai hydraulique « Écluse »"
VALEUR_SAISIE = "12500,5"                       # saisie au clavier dans Excel (fr-FR)
DESCRIPTION_EXCEL = "Revue dans Excel : bande à surveiller à la prochaine visite."
TITRE_EXCEL = "Remplacement du capteur (titre revu dans Excel)"
CHAMPS_V2 = {"demandes": ("symptome_code", "ot_origine_id"), "ordres_travail": ("anomalie_constatee",)}
TABLES_V1 = tuple(format_v2.COLONNES_V2)        # equipements, demandes, ordres_travail, parametres


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

    # =========================================================================================
    # Format v2 (lot 2) : aller-retour Excel des tables qui ont des colonnes v2
    # =========================================================================================

    def passer_par_excel(self, chemin, modifications=None):
        """Ouvre `chemin` dans le vrai Excel, applique les saisies (ligne, colonne, valeur), enregistre
        en « CSV UTF-8 » à sa place (comme « Enregistrer ») ; renvoie les octets écrits par Excel."""
        dossier = Path(tempfile.mkdtemp(prefix="prevo-excel-v2-"))
        try:
            sortie = dossier / chemin.name
            excel.aller_retour_excel(chemin, sortie, format="utf8", modifications=modifications)
            octets = sortie.read_bytes()
        finally:
            shutil.rmtree(dossier, ignore_errors=True)
        chemin.write_bytes(octets)
        return octets

    def valeurs_v2(self):
        """Valeurs lues par l'application : {demandes: {id: [symptome_code, ot_origine_id]}, ordres: {id: anomalie_constatee}}."""
        return self.page.evaluate("""() => ({
            demandes: Object.fromEntries(Donnees.lignes('demandes').map((d) => [d.id, [d.symptome_code, d.ot_origine_id]])),
            ordres: Object.fromEntries(Donnees.lignes('ordres_travail').map((o) => [o.id, o.anomalie_constatee])) })""")

    def colonnes_brutes(self, octets, colonnes):
        """{id: (valeurs brutes des colonnes)} d'un fichier CSV."""
        return {ligne["id"]: tuple(ligne[nom] for nom in colonnes) for ligne in lire_csv_brut(octets)[1]}

    def cellules_changees(self, octets_avant, octets_apres):
        """Cellules qui diffèrent entre deux versions d'un fichier (mêmes en-têtes) : {(id, colonne)},
        plus la liste des identifiants des lignes ajoutées, dans l'ordre."""
        entete_avant, avant = lire_csv_brut(octets_avant)
        entete_apres, apres = lire_csv_brut(octets_apres)
        self.assertEqual(entete_apres, entete_avant)
        self.assertEqual([l["id"] for l in apres[:len(avant)]], [l["id"] for l in avant], "ordre des lignes")
        changees = {(a["id"], nom) for a, b in zip(avant, apres) for nom in entete_avant if a[nom] != b[nom]}
        return changees, [l["id"] for l in apres[len(avant):]]

    def verifier_format_d5(self, octets, nom):
        """Écriture au format D5 (§3.1) : BOM, CRLF, dates ISO (aucune date JJ/MM/AAAA d'Excel)."""
        format_v2.verifier_format_ecriture(self, octets, nom)
        self.assertNotRegex(octets.decode("utf-8-sig"), r"(?m)(^|;)\d{2}/\d{2}/\d{4}", nom + " : date d'Excel restée")

    def accepter_par_l_interface(self, di):
        """Fiche de la DI → « Accepter » → « Créer l'ordre de travail » ; renvoie l'OT créé."""
        page = self.page
        page.evaluate("(id) => { location.hash = '#/di/' + id; }", di)
        page.wait_for_selector("[data-decision=accepter]")
        page.click("[data-decision=accepter]")
        page.wait_for_selector("dialog .di-fenetre-accepter")
        page.click("dialog button:has-text(\"Créer l'ordre de travail\")")
        page.wait_for_function("location.hash.startsWith('#/ot/')")
        page.wait_for_selector(".ot-fiche .ot-numero")
        return page.evaluate("decodeURIComponent(location.hash.slice(5))")

    def modifier_par_le_formulaire(self, equipement_id, champ, valeur):
        """Fiche équipement → « Modifier » : un champ changé, enregistré."""
        page = self.page
        page.evaluate("(id) => { location.hash = '#/equipement/' + id + '/modifier'; }", equipement_id)
        page.wait_for_selector("#parc-formulaire [name=%s]" % champ)
        page.fill("#parc-formulaire [name=%s]" % champ, valeur)
        page.click("#parc-formulaire button[type=submit]")
        page.wait_for_function("(id) => location.hash === '#/equipement/' + id", arg=equipement_id)
        page.wait_for_function("([id, champ, v]) => Donnees.trouver('equipements', id)[champ] === v", arg=[equipement_id, champ, valeur])

    def test_excel_v2_valeur_remplacement_et_champs_v2_intacts_puis_reecriture_d5(self):
        page = self.page
        scenarios = scenarios_demo()
        di_modifiee, di_acceptee = scenarios["di_statut_differee"], scenarios["di_statut_nouvelle"]
        ot_modifie = scenarios["ot_statut_planifie"]
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur)                                  # responsable : OT préventifs générés à l'ouverture
            page.wait_for_load_state("networkidle")
            originaux = {t: (dossier / (t + ".csv")).read_bytes() for t in ("equipements", "demandes", "ordres_travail")}
            avant = self.valeurs_v2()
            # Le jeu de démo a de quoi le prouver : codes symptôme, DI liées, OT « anomalie constatée »
            self.assertTrue(any(v[0] for v in avant["demandes"].values()))
            self.assertTrue(any(v[1] for v in avant["demandes"].values()))
            self.assertIn("1", avant["ordres"].values())
            bruts_avant = {t: self.colonnes_brutes(originaux[t], c) for t, c in CHAMPS_V2.items()}

            # 1. equipements.csv : nouvel équipement, valeur de remplacement saisie « 12500,5 »
            entete, lignes = lire_csv_brut(originaux["equipements"])
            self.assertEqual(entete[-1], "valeur_remplacement")
            numeros = [int(l["id"][3:]) for l in lignes if re.fullmatch(r"EQ-\d{4}", l["id"])]
            identifiant = "EQ-%04d" % (max(numeros) + 1)
            localisation = lire_csv_brut((dossier / "localisations.csv").read_bytes())[1][0]["id"]
            colonne = {nom: position + 1 for position, nom in enumerate(entete)}
            rang = len(lignes) + 2
            octets = self.passer_par_excel(dossier / "equipements.csv", [
                (rang, colonne["id"], identifiant), (rang, colonne["repere"], REPERE_V2),
                (rang, colonne["designation"], DESIGNATION_V2), (rang, colonne["localisation_id"], localisation),
                (rang, colonne["criticite"], "b"), (rang, colonne["valeur_remplacement"], VALEUR_SAISIE)])
            ajoutee = next(l for l in lire_csv_brut(octets)[1] if l["id"] == identifiant)
            self.assertEqual(ajoutee["valeur_remplacement"], VALEUR_SAISIE)      # virgule française d'Excel
            print("\n  [excel v2] ligne ajoutée par Excel : %s" % ";".join(ajoutee[nom] for nom in entete))

            # 2. demandes.csv et 3. ordres_travail.csv : une cellule sans rapport avec les champs v2
            for table, ident, champ, valeur in (("demandes", di_modifiee, "description", DESCRIPTION_EXCEL),
                                                ("ordres_travail", ot_modifie, "titre", TITRE_EXCEL)):
                entete_table, lignes_table = lire_csv_brut(originaux[table])
                rang_ligne = next(i for i, l in enumerate(lignes_table) if l["id"] == ident) + 2
                octets = self.passer_par_excel(dossier / (table + ".csv"), [(rang_ligne, entete_table.index(champ) + 1, valeur)])
                # Excel a réécrit le fichier à sa façon (dates JJ/MM/AAAA) sans toucher aux champs v2
                self.assertRegex(octets.decode("utf-8-sig"), r";\d{2}/\d{2}/\d{4} \d{2}:\d{2};", table)
                self.assertEqual(self.colonnes_brutes(octets, CHAMPS_V2[table]), bruts_avant[table], table)

            # Relecture par l'application : aucune erreur, champs v2 identiques, valeur affichée
            page.reload()
            attendre_pret(page)
            page.wait_for_load_state("networkidle")
            problemes = self.problemes()
            print("  [excel v2] problèmes signalés : %r" % (problemes,))
            self.assertEqual([p for p in problemes if p[0] in ("erreur", "attention")], [])
            self.assertEqual(self.valeurs_v2(), avant)
            self.assertEqual(page.evaluate("(id) => Donnees.trouver('demandes', id).description", di_modifiee), DESCRIPTION_EXCEL)
            self.assertEqual(page.evaluate("(id) => Donnees.trouver('ordres_travail', id).titre", ot_modifie), TITRE_EXCEL)
            ligne = page.evaluate("(id) => Donnees.trouver('equipements', id)", identifiant)
            self.assertEqual((ligne["repere"], ligne["designation"], ligne["criticite"], ligne["valeur_remplacement"]),
                             (REPERE_V2, DESIGNATION_V2, "B", "12500.5"))
            page.evaluate("(id) => { location.hash = '#/equipement/' + id; }", identifiant)
            page.wait_for_function("""() => { const v = document.querySelector('.parc-valeur-remplacement');
                return v && v.textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ').trim() === '12 500,50 € HT'; }""")
            self.verifier_controle_sans_erreur()

            # Modifications dans l'application : DI acceptée (demandes + ordres_travail), équipement modifié
            avant_ecriture = {t: (dossier / (t + ".csv")).read_bytes() for t in originaux}
            ot_cree = self.accepter_par_l_interface(di_acceptee)
            self.modifier_par_le_formulaire(identifiant, "marque", "Hydrauval")
            apres = {t: (dossier / (t + ".csv")).read_bytes() for t in originaux}
            for table in originaux:
                with self.subTest(table=table):
                    self.verifier_format_d5(apres[table], table)
                    self.assertNotEqual(apres[table], avant_ecriture[table], table + " n'a pas été réécrit")
            # Toutes les lignes d'avant Excel sont conservées ; seules changent les cellules voulues
            changees, ajoutees = self.cellules_changees(originaux["equipements"], apres["equipements"])
            self.assertEqual((changees, ajoutees), (set(), [identifiant]))
            self.assertTrue(apres["equipements"].startswith(originaux["equipements"]))
            nouvelle = lire_csv_brut(apres["equipements"])[1][-1]
            self.assertEqual((nouvelle["repere"], nouvelle["designation"], nouvelle["criticite"], nouvelle["marque"],
                              nouvelle["valeur_remplacement"]), ("'" + REPERE_V2, DESIGNATION_V2, "B", "Hydrauval", "12500.5"))
            changees, ajoutees = self.cellules_changees(originaux["demandes"], apres["demandes"])
            self.assertEqual(ajoutees, [])
            self.assertIn((di_modifiee, "description"), changees)
            self.assertTrue({ident for ident, _ in changees} <= {di_modifiee, di_acceptee}, changees)
            self.assertTrue({nom for ident, nom in changees if ident == di_acceptee} <= {"statut", "ot_id", "date_decision", "motif_decision"})
            changees, ajoutees = self.cellules_changees(originaux["ordres_travail"], apres["ordres_travail"])
            self.assertEqual((changees, ajoutees), ({(ot_modifie, "titre")}, [ot_cree]))
            self.assertEqual(self.colonnes_brutes(apres["demandes"], CHAMPS_V2["demandes"]),
                             dict(bruts_avant["demandes"]))
            ordres = self.colonnes_brutes(apres["ordres_travail"], CHAMPS_V2["ordres_travail"])
            self.assertEqual(ordres.pop(ot_cree), ("0",))
            self.assertEqual(ordres, bruts_avant["ordres_travail"])

    # =========================================================================================
    # Base du lot 1 (format v1) passée par Excel, puis ouverte par le lot 2
    # =========================================================================================

    def base_du_lot_1(self):
        """Dossier temporaire : les 22 tables du jeu de démo du lot 1 (tag git lot-1), dont les quatre
        fichiers de tests/fixtures/v1/ (copies octet pour octet du tag, vérifiées par test_format_v2)."""
        temporaire = tempfile.TemporaryDirectory(prefix="prevo-excel-lot1-")
        self.addCleanup(temporaire.cleanup)
        source = Path(temporaire.name) / "donnees"
        source.mkdir()
        for chemin in sorted(DOSSIER_DEMO.glob("*.csv")):
            table = chemin.stem
            if table in TABLES_V1:
                (source / chemin.name).write_bytes(format_v2.octets_v1(table))
                continue
            try:
                sortie = subprocess.run(["git", "cat-file", "blob", "lot-1:donnees/demo/%s" % chemin.name],
                                        cwd=str(RACINE), capture_output=True, timeout=30)
            except (OSError, subprocess.SubprocessError) as erreur:
                self.skipTest("git indisponible : %s" % erreur)
            if sortie.returncode != 0:
                self.skipTest("tag lot-1 introuvable : " + sortie.stderr.decode("utf-8", "replace"))
            (source / chemin.name).write_bytes(sortie.stdout)
        return source

    def changer_profil_par_l_interface(self, type_profil):
        page = self.page
        page.click("#etat-poste")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-" + type_profil)
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.profil.type"), type_profil)

    def test_excel_lot1_base_v1_passee_par_excel_colonnes_v2_en_info_puis_ajoutees_en_fin(self):
        page = self.page
        source = self.base_du_lot_1()
        # Les quatre fichiers v1 passent par Excel (ouvrir, enregistrer en « CSV UTF-8 »)
        for table in TABLES_V1:
            octets = self.passer_par_excel(source / (table + ".csv"))
            self.assertTrue(octets.startswith(BOM), table)
        self.assertRegex(lire_csv_brut((source / "demandes.csv").read_bytes())[1][0]["date_heure"], r"^\d{2}/\d{2}/\d{4} ")
        parametres_excel = (source / "parametres.csv").read_bytes()
        self.assertIn(b"version_schema;'1", parametres_excel)            # apostrophe gardée par Excel
        lignes_v1 = {table: format_v2.lire_lignes_csv(format_v2.octets_v1(table)) for table in TABLES_V1}

        preregler_profil(self.contexte, "demandeur", nom="Lucie Martin")
        with ServeurPrevo(source=source) as serveur:
            dossier = serveur.dossier
            page.goto(serveur.url + "/#/accueil")
            attendre_pret(page)
            page.wait_for_load_state("networkidle")

            # Passage au format 2 à l'ouverture : sauvegarde « avant format 2 » (fichier d'Excel), puis version 2
            sauvegardes = sorted((dossier / "sauvegardes").glob("*_avant-format-v2"))
            self.assertEqual(len(sauvegardes), 1, sauvegardes)
            self.assertEqual((sauvegardes[0] / "parametres.csv").read_bytes(), parametres_excel)
            self.assertIn(["version_schema", "'2"], format_v2.lire_lignes_csv((dossier / "parametres.csv").read_bytes()))

            # Relecture : aucun « attention » ni « erreur » ; les colonnes v2 absentes en « info »
            problemes = self.problemes()
            print("\n  [excel lot1] problèmes signalés : %r" % (problemes,))
            self.assertEqual([p for p in problemes if p[0] in ("erreur", "attention")], [])
            colonnes = sorted((p[2], p[3]) for p in problemes if p[1] == "colonne")
            self.assertEqual(colonnes, sorted((table, nom) for table, noms in format_v2.COLONNES_V2.items() for nom in noms))
            self.assertEqual({p[0] for p in problemes if p[1] == "colonne"}, {"info"})
            # Données identiques à celles des fichiers du lot 1 avant Excel (dates comprises)
            # (parametres a changé depuis : version_schema vient de passer à 2)
            for table in ("equipements", "demandes", "ordres_travail"):
                with self.subTest(lecture=table):
                    identiques = page.evaluate("""([table, octets]) => JSON.stringify(Donnees.csv.analyser(table, new Uint8Array(octets)).lignes)
                        === JSON.stringify(Donnees.lignes(table))""", [table, list(format_v2.octets_v1(table))])
                    self.assertTrue(identiques, table + " : lu après Excel, différent du fichier du lot 1")

            # Modifications dans l'application : chacune ajoute les colonnes v2 en fin de table
            equipement = lignes_v1["equipements"][1]
            page.click("#menu a[data-ecran='nouvelle-di']")
            page.wait_for_selector(".di-formulaire")
            page.fill(".selecteur-recherche input[type=search]", equipement[1].lstrip("'"))
            page.click(".selecteur-option[data-id='%s']" % equipement[0])
            page.fill("input[name=symptome]", "Fuite d'huile sous le carter")
            page.click("label.tuile:has(input[value='gêne'])")
            page.click(".di-envoyer")
            page.wait_for_selector(".di-numero")
            di = page.inner_text(".di-numero")
            self.changer_profil_par_l_interface("responsable")
            designation = "Désignation revue après Excel ; format v2"
            self.modifier_par_le_formulaire(equipement[0], "designation", designation)
            ot_cree = self.accepter_par_l_interface(di)

            ecrits = {table: format_v2.lire_lignes_csv((dossier / (table + ".csv")).read_bytes()) for table in TABLES_V1}
            for table in ("equipements", "demandes", "ordres_travail"):
                with self.subTest(ecriture=table):
                    octets = (dossier / (table + ".csv")).read_bytes()
                    self.verifier_format_d5(octets, table)
                    v1 = lignes_v1[table]
                    changees = {(1, "designation"): designation} if table == "equipements" else {}
                    format_v2.verifier_v1_plus_colonnes(self, v1, ecrits[table][:len(v1)], table, changees)
            self.assertEqual(len(ecrits["equipements"]), len(lignes_v1["equipements"]))
            nouvelle_di = dict(zip(ecrits["demandes"][0], ecrits["demandes"][-1]))
            self.assertEqual((nouvelle_di["id"], nouvelle_di["statut"], nouvelle_di["ot_id"], nouvelle_di["symptome_code"],
                              nouvelle_di["ot_origine_id"]), (di, "Acceptée", ot_cree, "", ""))
            nouvel_ot = dict(zip(ecrits["ordres_travail"][0], ecrits["ordres_travail"][-1]))
            self.assertEqual((nouvel_ot["id"], nouvel_ot["di_id"], nouvel_ot["anomalie_constatee"]), (ot_cree, di, "0"))
            self.assertEqual(len(ecrits["ordres_travail"]), len(lignes_v1["ordres_travail"]) + 1)
            self.assertEqual([p for p in self.problemes() if p[1] == "colonne"], [])     # plus rien à signaler

    def test_excel_xls_enregistre_par_excel_lu_par_import_comme_le_xlsx(self):
        # Le vrai Excel ouvre une copie de equipements.xlsx et l'enregistre en .xls (Excel 97-2003)
        dossier = Path(tempfile.mkdtemp(prefix="prevo-excel-xls-"))
        try:
            entree, sortie = dossier / "parc.xlsx", dossier / "parc.xls"
            shutil.copyfile(str(FIXTURES_IMPORT / "equipements.xlsx"), str(entree))
            code, console = excel._executer_vbs("\r\n".join([
                'etape = "ouverture du classeur"',
                "Set wb = xl.Workbooks.Open(%s, , , , , , , , , , , , , True)" % excel.chaine_vbs(str(entree)),
                "Verifier",
                'etape = "enregistrement en .xls"',
                "wb.SaveAs %s, %d" % (excel.chaine_vbs(str(sortie)), XL_EXCEL8),
                "Verifier",
            ]))
            self.assertEqual(code, 0, console)
            self.assertTrue(sortie.is_file(), console)
            octets_xls = sortie.read_bytes()
        finally:
            shutil.rmtree(dossier, ignore_errors=True)
        self.assertEqual(octets_xls[:8], SIGNATURE_OLE, "un .xls est un conteneur OLE")

        # Import.lire (démo, file://) : le .xls d'Excel donne les mêmes cellules et le même aperçu que le .xlsx
        page = self.page
        preregler_profil(self.contexte, "responsable")
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        xlsx = base64.b64encode((FIXTURES_IMPORT / "equipements.xlsx").read_bytes()).decode("ascii")
        lus = page.evaluate(LIRE_CLASSEURS_JS, [["parc.xlsx", xlsx], ["parc.xls", base64.b64encode(octets_xls).decode("ascii")]])
        reference, excel_xls = lus["parc.xlsx"], lus["parc.xls"]
        self.assertEqual((reference["format"], excel_xls["format"]), ("xlsx", "xls"))
        feuilles = lambda lu: {f["nom"]: normaliser(f["lignes"]) for f in lu["feuilles"] if normaliser(f["lignes"])}
        self.assertEqual(list(feuilles(excel_xls)), list(feuilles(reference)))
        for nom, lignes in feuilles(reference).items():
            with self.subTest(feuille=nom):
                self.assertEqual(feuilles(excel_xls)[nom], lignes)
        parc = feuilles(excel_xls)["Parc"]
        self.assertIn("007", [l[1] for l in parc if len(l) > 1])
        self.assertIn("1E5", [l[5] for l in parc if len(l) > 5])
        self.assertEqual(excel_xls["rang"], 1)
        self.assertEqual(excel_xls["actions"], reference["actions"])
        self.assertEqual({a: excel_xls["totaux"][a] for a in ("creer", "mettre_a_jour", "identique", "refusee")},
                         {"creer": 5, "mettre_a_jour": 1, "identique": 14, "refusee": 3})


if __name__ == "__main__":
    unittest.main()
