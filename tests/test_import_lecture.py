"""Lecture des fichiers et du collage de l'assistant d'import (tâche T81, ARCHITECTURE.md §18.3 ;
CS81, CS86, CS89, CS93).

Familles (le nom du test le dit) :
    construits : données fabriquées dans la page — collage tabulé, CSV Windows-1252 « ; » et UTF-8 « , »
                 avec guillemets, classeur .xlsx écrit par SheetJS (dates 1900 et 1904, « 007 », nombres,
                 cases) ; SheetJS jamais chargé pour un CSV ;
    plafonds   : trop grand, trop long, trop de colonnes, vide, chiffré → Import.ErreurImport, message clair ;
    entete     : ligne d'en-tête trouvée sous un titre, en-tête sur deux lignes ;
    fichiers   : les fichiers d'essai de tests/fixtures/import/ (T79) lus comme la lecture Python
                 indépendante (zipfile + XML pour .xlsx et .ods, csv pour les textes).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_import_lecture.py" -v
"""
import base64
import time
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier
from test_fixtures_import import DOSSIER, ENTETES_PARC, lire_csv, lire_ods, lire_xlsx

# Fichiers d'essai texte : (nom, encodage Python, séparateur, encodage annoncé par Import.lire).
TEXTES = (
    ("articles.csv", "cp1252", ";", "windows-1252"),
    ("fournisseurs.tsv", "utf-8", "\t", "utf-8"),
    ("techniciens.tsv", "utf-8", "\t", "utf-8"),
    ("habilitations.csv", "utf-8", ";", "utf-8"),
    ("codes.csv", "utf-8", ";", "utf-8"),
    ("compteurs.csv", "cp1252", ";", "windows-1252"),
    ("controles.csv", "utf-8", ";", "utf-8"),
    ("historique.csv", "utf-8", ",", "utf-8"),
    ("sans_entete.csv", "utf-8", ";", "utf-8"),
)

# Lit des fichiers d'essai (nom, base64) dans la page ; compte les appels à XLSX.read (SheetJS).
FICHIERS_JS = """async (fichiers) => {
  const X = await App.chargerSheetJS();
  const lireOrigine = X.read;
  const resultats = {};
  for (const [nom, contenu] of fichiers) {
    let appels = 0;
    X.read = (...parametres) => { appels += 1; return lireOrigine(...parametres); };
    const debut = performance.now();
    try {
      const octets = Uint8Array.from(atob(contenu), (c) => c.charCodeAt(0));
      const lu = await Import.lire(new File([octets], nom));
      resultats[nom] = { ok: true, format: lu.format, encodage: lu.encodage, feuilles: lu.feuilles, appels };
    } catch (erreur) {
      resultats[nom] = { ok: false, nom: erreur.name, message: erreur.message, appels };
    }
    resultats[nom].duree = performance.now() - debut;
    X.read = lireOrigine;
  }
  return resultats;
}"""


def normaliser(grille):
    """Grille comparable : cellules blanches en fin de ligne et lignes vides en fin de feuille retirées."""
    lignes = []
    for ligne in grille:
        ligne = list(ligne)
        while ligne and ligne[-1].strip() == "":
            ligne.pop()
        lignes.append(ligne)
    while lignes and not lignes[-1]:
        lignes.pop()
    return lignes

# Lit une source fabriquée dans la page ; rend le résultat ou l'erreur nommée.
LIRE_JS = """async (source) => {
  try {
    let entree = source;
    if (source.octets) entree = new File([Uint8Array.from(source.octets)], source.nom);
    if (source.base64) entree = new File([Uint8Array.from(atob(source.base64), (c) => c.charCodeAt(0))], source.nom);
    const lu = await Import.lire(entree);
    return { ok: true, nom: lu.nom, format: lu.format, encodage: lu.encodage, feuilles: lu.feuilles };
  } catch (erreur) {
    return { ok: false, nom: erreur.name, message: erreur.message };
  }
}"""

# Classeur .xlsx (ou .xls) écrit par SheetJS dans la page, en base64.
CLASSEUR_JS = """async ([bookType, date1904]) => {
  const X = await App.chargerSheetJS();
  const feuille = X.utils.aoa_to_sheet([
    ['Liste du parc — atelier'],
    [],
    ['Code machine', 'Désignation', 'Mise en service', 'Heures', 'Actif', 'Remarque'],
    ['007', 'Pompe de relevage', 0, 12.5, true, 'à voir'],
    ['PO-99', 'Compresseur', 0, 8, false, ''],
  ]);
  // Dates : numéros de série et format date (système 1900 ou 1904)
  const serie = date1904 ? 45000 - 1462 : 45000;                  // 15/03/2023 dans les deux systèmes
  feuille['C4'] = { t: 'n', v: serie, z: 'dd/mm/yyyy' };
  feuille['C5'] = { t: 'n', v: serie + 0.5, z: 'dd/mm/yyyy hh:mm' };
  const classeur = X.utils.book_new();
  X.utils.book_append_sheet(classeur, feuille, 'Parc');
  X.utils.book_append_sheet(classeur, X.utils.aoa_to_sheet([['vide']]), 'Notes');
  if (date1904) classeur.Workbook = { WBProps: { date1904: true } };
  return X.write(classeur, { bookType, type: 'base64' });
}"""


class CasLecture(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.adresses = []
        self.page.on("request", lambda requete: self.adresses.append(requete.url))
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)

    def lire(self, source):
        return self.page.evaluate(LIRE_JS, source)

    def lignes(self, source, feuille=0):
        resultat = self.lire(source)
        self.assertTrue(resultat["ok"], resultat)
        return resultat["feuilles"][feuille]["lignes"]


class TestConstruits(CasLecture):

    def test_collage_tabule(self):
        resultat = self.lire({"texte": "Repère\tDésignation\r\nPO-01\tPompe « A »\r\n\r\n", "nom": "Collage"})
        self.assertTrue(resultat["ok"], resultat)
        self.assertEqual(resultat["format"], "collage")
        self.assertEqual(resultat["feuilles"][0]["lignes"], [["Repère", "Désignation"], ["PO-01", "Pompe « A »"]])

    def test_csv_windows_1252_point_virgule_et_utf8_virgule_avec_guillemets(self):
        texte = "Référence;Désignation;Prix\r\nR-1;Roulement à billes;12,50\r\n"
        resultat = self.lire({"octets": list(texte.encode("cp1252")), "nom": "articles.csv"})
        self.assertTrue(resultat["ok"], resultat)
        self.assertEqual(resultat["encodage"], "windows-1252")
        self.assertEqual(resultat["feuilles"][0]["lignes"], [["Référence", "Désignation", "Prix"], ["R-1", "Roulement à billes", "12,50"]])
        texte = '\ufeffN° OT,Compte rendu\r\n1234,"Fuite, garniture ""neuve"" posée"\r\n'
        lignes = self.lignes({"octets": list(texte.encode("utf-8")), "nom": "historique.csv"})
        self.assertEqual(lignes, [["N° OT", "Compte rendu"], ["1234", 'Fuite, garniture "neuve" posée']])
        # Un CSV ne charge jamais SheetJS
        self.assertTrue(self.page.evaluate("typeof XLSX === 'undefined'"))
        self.assertEqual([a for a in self.adresses if "xlsx.full" in a], [])

    def test_xlsx_dates_1900_et_1904_zeros_en_tete_nombres_cases_et_feuilles(self):
        for date1904 in (False, True):
            with self.subTest(date1904=date1904):
                base64 = self.page.evaluate(CLASSEUR_JS, ["xlsx", date1904])
                resultat = self.lire({"base64": base64, "nom": "parc.xlsx"})
                self.assertTrue(resultat["ok"], resultat)
                self.assertEqual([f["nom"] for f in resultat["feuilles"]], ["Parc", "Notes"])
                lignes = resultat["feuilles"][0]["lignes"]
                self.assertEqual(lignes[0][0], "Liste du parc — atelier")
                self.assertEqual(lignes[2], ["Code machine", "Désignation", "Mise en service", "Heures", "Actif", "Remarque"])
                self.assertEqual(lignes[3], ["007", "Pompe de relevage", "2023-03-15", "12.5", "1", "à voir"])
                self.assertEqual(lignes[4], ["PO-99", "Compresseur", "2023-03-15 12:00", "8", "0", ""])

    def test_xls_ancien_format_lu_comme_le_xlsx(self):
        base64 = self.page.evaluate(CLASSEUR_JS, ["biff8", False])
        lignes = self.lignes({"base64": base64, "nom": "parc.xls"})
        self.assertEqual(lignes[3], ["007", "Pompe de relevage", "2023-03-15", "12.5", "1", "à voir"])


class TestPlafonds(CasLecture):

    def erreur(self, source, extrait):
        resultat = self.lire(source)
        self.assertFalse(resultat["ok"], resultat)
        self.assertEqual(resultat["nom"], "ErreurImport")
        self.assertIn(extrait, resultat["message"])

    def test_trop_grand_trop_long_trop_de_colonnes_vide_et_chiffre(self):
        trop_grand = self.page.evaluate("""async () => {
          const octets = new Uint8Array(10 * 1024 * 1024 + 1).fill(65);
          try { await Import.lire(new File([octets], 'gros.csv')); return null; } catch (e) { return [e.name, e.message]; }
        }""")
        self.assertEqual(trop_grand[0], "ErreurImport")
        self.assertIn("trop grand", trop_grand[1])
        lignes = "a;b\r\n" + "".join("%d;x\r\n" % n for n in range(20001))
        self.erreur({"texte": lignes, "nom": "long.csv"}, "trop long")
        juste = "a;b\r\n" + "".join("%d;x\r\n" % n for n in range(20000))
        self.assertEqual(len(self.lignes({"texte": juste, "nom": "juste.csv"})), 20001)
        self.erreur({"texte": ";".join("c%d" % n for n in range(201)) + "\r\n", "nom": "large.csv"}, "Trop de colonnes")
        self.erreur({"texte": "  \r\n", "nom": "vide.csv"}, "vide")
        self.erreur({"octets": [], "nom": "vide.csv"}, "vide")
        self.erreur({"texte": ";;\r\n;;\r\n", "nom": "rien.csv"}, "aucune donnée")
        ole = [0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1] + [0] * 504
        ole += [b for c in "EncryptionInfo" for b in (ord(c), 0)] + [0] * 64
        self.erreur({"octets": ole, "nom": "chiffre.xlsx"}, "mot de passe")
        self.erreur({"octets": [1, 2, 3], "nom": "image.png"}, "Format non reconnu")


class TestEntete(CasLecture):

    def test_titre_au_dessus_et_en_tete_sur_deux_lignes(self):
        lignes = [["Liste du parc — atelier", "", ""], ["", "", ""], ["Repère", "Désignation", "Mise en service"],
                  ["PO-01", "Pompe", "15/03/2023"]]
        self.assertEqual(self.page.evaluate("(l) => Import.ligneEntete(l)", lignes), 2)
        double = [["Équipement", "", "Dates"], ["Repère", "Désignation", "Mise en service"], ["PO-01", "Pompe", "15/03/2023"]]
        self.assertEqual(self.page.evaluate("(l) => Import.entetes(l, 0, true)", double),
                         ["Équipement Repère", "Équipement Désignation", "Dates Mise en service"])
        self.assertEqual(self.page.evaluate("(l) => Import.entetes(l, 1, false)", double), ["Repère", "Désignation", "Mise en service"])


class TestFichiers(CasLecture):
    """Les fichiers d'essai de T79, lus par Import.lire, contre la lecture Python indépendante (sans SheetJS)."""

    def lire_fichiers(self, *noms):
        fichiers = [[nom, base64.b64encode((DOSSIER / nom).read_bytes()).decode("ascii")] for nom in noms]
        return self.page.evaluate(FICHIERS_JS, fichiers)

    def feuilles(self, resultat):
        self.assertTrue(resultat["ok"], resultat)
        return {feuille["nom"]: normaliser(feuille["lignes"]) for feuille in resultat["feuilles"]}

    def test_tableurs_xlsx_ods_xls_et_gammes(self):
        lus = self.lire_fichiers("equipements.xlsx", "equipements.ods", "equipements.xls", "gammes.xlsx")
        parc, _brutes, _formats = lire_xlsx(DOSSIER / "equipements.xlsx")
        attendu = {nom: normaliser(lignes) for nom, lignes in parc.items() if normaliser(lignes)}
        self.assertEqual(self.feuilles(lus["equipements.xlsx"]), attendu)
        ods = {nom: normaliser(lignes) for nom, lignes in lire_ods(DOSSIER / "equipements.ods").items() if normaliser(lignes)}
        self.assertEqual(ods, attendu, "lecture Python : le .ods a les mêmes données que le .xlsx")
        self.assertEqual(self.feuilles(lus["equipements.ods"]), attendu)
        self.assertEqual(self.feuilles(lus["equipements.xls"]), attendu)
        gammes, _brutes, _formats = lire_xlsx(DOSSIER / "gammes.xlsx")
        self.assertEqual(self.feuilles(lus["gammes.xlsx"]), {nom: normaliser(l) for nom, l in gammes.items() if normaliser(l)})
        # Ligne d'en-tête trouvée sous le titre, dans les trois formats
        grille = lus["equipements.xlsx"]["feuilles"][0]["lignes"]
        rang = [ligne[:len(ENTETES_PARC)] for ligne in grille].index(ENTETES_PARC)
        self.assertGreater(rang, 0)
        for nom in ("equipements.xlsx", "equipements.ods", "equipements.xls"):
            lignes = lus[nom]["feuilles"][0]["lignes"]
            self.assertEqual(self.page.evaluate("([l, t]) => Import.ligneEntete(l, t)", [lignes, "equipements"]), rang, nom)

    def test_dates_des_tableurs_independantes_du_fuseau_horaire(self):
        # Un fuseau très en avance et un très en retard sur l'heure universelle : mêmes dates qu'en Python.
        attendu = {nom: normaliser(l) for nom, l in lire_xlsx(DOSSIER / "equipements.xlsx")[0].items() if normaliser(l)}
        for fuseau in ("Pacific/Kiritimati", "Pacific/Pago_Pago"):
            with self.subTest(fuseau=fuseau):
                contexte = self.navigateur.new_context(locale="fr-FR", timezone_id=fuseau)
                try:
                    preregler_profil(contexte, "responsable")
                    page = contexte.new_page()
                    page.goto(url_fichier("index.html"))
                    page.click("#btn-demo")
                    attendre_pret(page)
                    fichiers = [[nom, base64.b64encode((DOSSIER / nom).read_bytes()).decode("ascii")]
                                for nom in ("equipements.ods", "equipements.xlsx", "equipements.xls")]
                    lus = page.evaluate(FICHIERS_JS, fichiers)
                    for nom, resultat in lus.items():
                        self.assertEqual(self.feuilles(resultat), attendu, nom)
                finally:
                    contexte.close()

    def test_textes_encodages_separateurs_et_guillemets(self):
        lus = self.lire_fichiers(*[nom for nom, _e, _s, _a in TEXTES])
        for nom, encodage, separateur, annonce in TEXTES:
            with self.subTest(fichier=nom):
                resultat = lus[nom]
                self.assertTrue(resultat["ok"], resultat)
                self.assertEqual(resultat["encodage"], annonce)
                self.assertEqual(resultat["appels"], 0, "un texte ne passe jamais par SheetJS")
                self.assertEqual(len(resultat["feuilles"]), 1)
                self.assertEqual(normaliser(resultat["feuilles"][0]["lignes"]), normaliser(lire_csv(nom, encodage, separateur)))
        historique = lus["historique.csv"]["feuilles"][0]["lignes"]
        self.assertEqual(self.page.evaluate("([l, t]) => Import.ligneEntete(l, t)", [historique, "historique"]), 0)

    def test_plafond_de_lignes_et_sa_limite(self):
        lus = self.lire_fichiers("trop_de_lignes.csv", "limite_de_lignes.csv")
        self.assertFalse(lus["trop_de_lignes.csv"]["ok"])
        self.assertEqual(lus["trop_de_lignes.csv"]["nom"], "ErreurImport")
        self.assertIn("trop long", lus["trop_de_lignes.csv"]["message"])
        limite = lus["limite_de_lignes.csv"]
        self.assertTrue(limite["ok"], {k: v for k, v in limite.items() if k != "feuilles"})
        self.assertEqual(len(normaliser(limite["feuilles"][0]["lignes"])), 20001)

    def test_fichiers_pieges_refuses_avec_un_message_clair(self):
        debut = time.monotonic()
        lus = self.lire_fichiers("chiffre.xlsx", "vide.csv", "lignes_vides.csv", "cellules_repetees.ods")
        attendus = {"chiffre.xlsx": "mot de passe", "vide.csv": "vide", "lignes_vides.csv": "aucune donnée",
                    "cellules_repetees.ods": "Trop de colonnes"}
        for nom, extrait in attendus.items():
            with self.subTest(fichier=nom):
                self.assertFalse(lus[nom]["ok"], lus[nom])
                self.assertEqual(lus[nom]["nom"], "ErreurImport")
                self.assertIn(extrait, lus[nom]["message"])
        # La bombe de cellules répétées est refusée AVANT SheetJS (qui déplierait le million de cellules)
        self.assertEqual(lus["cellules_repetees.ods"]["appels"], 0)
        self.assertEqual(lus["chiffre.xlsx"]["appels"], 0)
        self.assertLess(lus["cellules_repetees.ods"]["duree"], 1000)
        self.assertLess(time.monotonic() - debut, 30)


if __name__ == "__main__":
    unittest.main()
