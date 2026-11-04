"""Tests du format CSV v2 (ARCHITECTURE.md §14.1, avec les règles des §3 et §5.2).

Un fichier écrit par le lot 1 (format v1) doit se lire sans aucun problème « attention » ni
« erreur » : chaque colonne ajoutée par la version 2 (champ `depuisVersion: 2` du schéma) absente
du fichier donne un simple problème « info » et sa valeur par défaut. Au prochain enregistrement,
la colonne est écrite en dernière position et toutes les autres cellules restent identiques.

Fichiers de référence : tests/fixtures/v1/*.csv, copies OCTET POUR OCTET des fichiers de démo du
tag git `lot-1` (`git show lot-1:donnees/demo/<fichier>` ; `.gitattributes` empêche toute
conversion des fins de ligne des *.csv).

Couvre :
    - les fichiers de référence sont bien ceux du lot 1 (BOM, CRLF, sans colonne v2) ;
    - lecture (Donnees.csv.analyser) : aucun « attention »/« erreur », une « info » par colonne v2
      absente, valeurs par défaut ; une colonne du brief absente reste « attention » ;
    - réécriture en mémoire (Donnees.csv.serialiser) : colonnes v2 en fin, cellules v1 identiques ;
    - mode serveur (serveur.py sur une copie de la démo où les fichiers v1 remplacent ceux de la
      démo) : Donnees.modifier sur un équipement → sur le disque, valeur_remplacement en dernière
      colonne, toutes les autres cellules identiques au fichier v1 ;
    - écriture puis relecture d'une valeur de chaque nouveau champ (booléen 0/1, décimal écrit avec
      un point et relu avec une virgule française, références contrôlées).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_format_v2.py" -v
"""
import csv
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from commun import DOSSIER_DEMO, RACINE, CasNavigateur, ServeurPrevo, charger_scripts

DOSSIER_V1 = RACINE / "tests" / "fixtures" / "v1"
BOM = b"\xef\xbb\xbf"

# Les quatre fichiers de référence et les colonnes que les versions 2 et 3 ajoutent à chacun (§14.1 ; lot 6 :
# la colonne astuce des OT, §20.10), toujours en fin de ligne, dans l'ordre du schéma.
COLONNES_V2 = {
    "equipements": ["valeur_remplacement"],
    "demandes": ["symptome_code", "ot_origine_id"],
    "ordres_travail": ["anomalie_constatee", "astuce"],
    "parametres": [],
}
# Valeur par défaut de chaque nouveau champ (js/schema.js) : anomalie_constatee est un booléen faux.
DEFAUTS_V2 = {"valeur_remplacement": "", "symptome_code": "", "ot_origine_id": "", "anomalie_constatee": "0", "astuce": ""}
LIBELLES_TABLES = {"equipements": "Équipements", "demandes": "Demandes d'intervention",
                   "ordres_travail": "Ordres de travail"}
MESSAGE_INFO = "ajoutée par la version %d du format, écrite au prochain enregistrement"
VERSION_COLONNE = {"astuce": 3}   # depuisVersion du schéma (js/schema.js) ; les autres colonnes : version 2

SCRIPTS = ["js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js"]
SCRIPTS_SERVEUR = SCRIPTS + ["js/stockage-serveur.js"]

# Page vide servie (par interception Playwright) à l'adresse du serveur de test : les appels
# /api/… de StockageServeur partent ainsi de la même origine, sans dépendre d'index.html ni des
# modules de l'application (ni d'une option du serveur pour servir tests/fixtures).
PAGE_VIDE_HTML = ("<!DOCTYPE html><html lang=\"fr\"><head><meta charset=\"UTF-8\">"
                  "<title>Test du format v2</title></head><body></body></html>")


# ---------------------------------------------------------------------------
# Outils (propres à ce fichier)
# ---------------------------------------------------------------------------

def octets_v1(table):
    return (DOSSIER_V1 / (table + ".csv")).read_bytes()


def lire_lignes_csv(octets):
    """Octets d'un CSV → liste de lignes (listes de cellules brutes, apostrophes de protection comprises)."""
    return list(csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";"))


def ecrire_lignes_csv(chemin, lignes):
    """Réécrit un CSV comme le ferait un tableur : BOM, « ; », CRLF, guillemets seulement si besoin."""
    tampon = io.StringIO(newline="")
    csv.writer(tampon, delimiter=";", lineterminator="\r\n").writerows(lignes)
    Path(chemin).write_bytes(BOM + tampon.getvalue().encode("utf-8"))


def verifier_format_ecriture(cas, octets, nom):
    """BOM UTF-8, fins de ligne CRLF (aucun LF isolé hors guillemets), fichier terminé par CRLF (§3.1)."""
    cas.assertTrue(octets.startswith(BOM), nom + " : BOM absent")
    texte = octets[len(BOM):].decode("utf-8")
    cas.assertTrue(texte.endswith("\r\n"), nom + " : doit finir par CRLF")
    entre_guillemets = False
    for position, caractere in enumerate(texte):
        if caractere == '"':
            entre_guillemets = not entre_guillemets
        elif caractere == "\n" and not entre_guillemets:
            cas.assertEqual(texte[position - 1], "\r", "%s : LF sans CR à la position %d" % (nom, position))


def verifier_v1_plus_colonnes(cas, lignes_v1, lignes_ecrites, table, cellules_changees=None):
    """Le fichier écrit = le fichier v1 avec les colonnes v2 ajoutées en dernière position.

    cellules_changees : {(numéro de ligne de données, nom de colonne): valeur attendue} pour les
    cellules modifiées volontairement ; toutes les autres cellules doivent être identiques au v1.
    """
    attendues = cellules_changees or {}
    nouvelles = COLONNES_V2[table]
    entete_v1 = lignes_v1[0]
    cas.assertEqual(lignes_ecrites[0], entete_v1 + nouvelles, table + " : en-tête")
    cas.assertEqual(len(lignes_ecrites), len(lignes_v1), table + " : nombre de lignes")
    largeur = len(entete_v1)
    for numero, (ancienne, ecrite) in enumerate(zip(lignes_v1[1:], lignes_ecrites[1:]), 1):
        cas.assertEqual(len(ecrite), largeur + len(nouvelles), "%s ligne %d" % (table, numero))
        for position, nom in enumerate(entete_v1):
            attendu = attendues.get((numero, nom), ancienne[position])
            cas.assertEqual(ecrite[position], attendu, "%s ligne %d, colonne %s" % (table, numero, nom))
        for decalage, nom in enumerate(nouvelles):
            attendu = attendues.get((numero, nom), DEFAUTS_V2[nom])
            cas.assertEqual(ecrite[largeur + decalage], attendu, "%s ligne %d, colonne %s" % (table, numero, nom))


# ---------------------------------------------------------------------------
# 1. Les fichiers de référence sont ceux du lot 1
# ---------------------------------------------------------------------------

class TestFichiersDeReferenceV1(unittest.TestCase):

    def test_copies_octet_pour_octet_du_tag_lot_1(self):
        for table in COLONNES_V2:
            with self.subTest(table=table):
                try:
                    sortie = subprocess.run(["git", "cat-file", "blob", "lot-1:donnees/demo/%s.csv" % table],
                                            cwd=str(RACINE), capture_output=True, timeout=30)
                except (OSError, subprocess.SubprocessError) as erreur:
                    self.skipTest("git indisponible : %s" % erreur)
                if sortie.returncode != 0:
                    self.skipTest("tag lot-1 introuvable : " + sortie.stderr.decode("utf-8", "replace"))
                self.assertEqual(octets_v1(table), sortie.stdout)

    def test_format_v1_bom_crlf_et_sans_colonne_v2(self):
        for table, nouvelles in COLONNES_V2.items():
            with self.subTest(table=table):
                octets = octets_v1(table)
                verifier_format_ecriture(self, octets, table)
                entete = lire_lignes_csv(octets)[0]
                for nom in nouvelles:
                    self.assertNotIn(nom, entete)
        parametres = dict(ligne for ligne in lire_lignes_csv(octets_v1("parametres"))[1:])
        self.assertEqual(parametres["version_schema"], "'1")


# ---------------------------------------------------------------------------
# 2. Lecture et réécriture en mémoire (Donnees.csv)
# ---------------------------------------------------------------------------

class TestLectureFichiersV1(CasNavigateur):

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)

    def analyser(self, table, octets):
        return self.page.evaluate(
            "([table, octets]) => Donnees.csv.analyser(table, new Uint8Array(octets))", [table, list(octets)])

    def analyser_et_reecrire(self, table, octets):
        """Lit le fichier puis le réécrit tel quel (aucune modification) : octets du fichier réécrit."""
        return bytes(self.page.evaluate("""([table, octets]) => {
            const lu = Donnees.csv.analyser(table, new Uint8Array(octets));
            return Array.from(Donnees.csv.serialiser(table, lu.lignes, lu.colonnesInconnues));
        }""", [table, list(octets)]))

    def test_aucun_probleme_attention_ni_erreur_et_une_info_par_colonne_v2(self):
        for table, nouvelles in COLONNES_V2.items():
            with self.subTest(table=table):
                resultat = self.analyser(table, octets_v1(table))
                graves = [(p["gravite"], p["type"], p["message"]) for p in resultat["problemes"]
                          if p["gravite"] in ("attention", "erreur")]
                self.assertEqual(graves, [])
                infos = [p for p in resultat["problemes"] if p["gravite"] == "info"]
                self.assertEqual([(p["type"], p["champ"], p["ligne"]) for p in infos],
                                 [("colonne", nom, 1) for nom in nouvelles])
                for probleme, nom in zip(infos, nouvelles):
                    self.assertEqual(probleme["table"], table)
                    self.assertEqual(probleme["message"], "%s : colonne « %s » %s."
                                     % (LIBELLES_TABLES[table], nom, MESSAGE_INFO % VERSION_COLONNE.get(nom, 2)))
                self.assertEqual(resultat["colonnesInconnues"], [])
                self.assertEqual(resultat["encodage"], "utf-8")

    def test_les_lignes_lues_portent_la_valeur_par_defaut(self):
        for table, nouvelles in COLONNES_V2.items():
            with self.subTest(table=table):
                resultat = self.analyser(table, octets_v1(table))
                lignes_v1 = lire_lignes_csv(octets_v1(table))
                self.assertEqual(len(resultat["lignes"]), len(lignes_v1) - 1)
                self.assertGreater(len(resultat["lignes"]), 5)
                for ligne in resultat["lignes"]:
                    for nom in nouvelles:
                        self.assertEqual(ligne[nom], DEFAUTS_V2[nom], "%s %s.%s" % (ligne.get("id"), table, nom))
        ordres = self.analyser("ordres_travail", octets_v1("ordres_travail"))["lignes"]
        self.assertTrue(all(o["anomalie_constatee"] == "0" for o in ordres))

    def test_une_colonne_du_brief_absente_reste_en_attention(self):
        """§3.3 inchangé : seule la colonne du brief retirée est « attention » ; la colonne v2 reste « info »."""
        lignes = lire_lignes_csv(octets_v1("equipements"))
        position = lignes[0].index("marque")
        tampon = io.StringIO(newline="")
        csv.writer(tampon, delimiter=";", lineterminator="\r\n").writerows(
            [ligne[:position] + ligne[position + 1:] for ligne in lignes])
        resultat = self.analyser("equipements", BOM + tampon.getvalue().encode("utf-8"))
        colonnes = sorted((p["gravite"], p["champ"]) for p in resultat["problemes"] if p["type"] == "colonne")
        self.assertEqual(colonnes, [("attention", "marque"), ("info", "valeur_remplacement")])
        self.assertEqual([p["gravite"] for p in resultat["problemes"] if p["type"] != "colonne"], [])

    def test_reecriture_ajoute_les_colonnes_v2_en_fin_et_garde_toutes_les_cellules(self):
        for table in COLONNES_V2:
            with self.subTest(table=table):
                reecrit = self.analyser_et_reecrire(table, octets_v1(table))
                verifier_format_ecriture(self, reecrit, table)
                verifier_v1_plus_colonnes(self, lire_lignes_csv(octets_v1(table)), lire_lignes_csv(reecrit), table)
        # parametres n'a pas de nouvelle colonne : la réécriture est identique octet pour octet
        self.assertEqual(self.analyser_et_reecrire("parametres", octets_v1("parametres")), octets_v1("parametres"))

    def test_lecture_tolerante_des_nouveaux_champs(self):
        """Valeurs saisies dans un tableur : virgule française, espaces, oui/non/x… (§3.3)."""
        cas = {
            "equipements": ("valeur_remplacement",
                            [("1 234,50", "1234.50"), ("7,5", "7.5"), ("12500", "12500"), ("", ""),
                             (" 980,25", "980.25"), (" 15 000 ", "15000")]),
            "ordres_travail": ("anomalie_constatee",
                               [("oui", "1"), ("non", "0"), ("x", "1"), ("VRAI", "1"), ("faux", "0"),
                                ("1", "1"), ("0", "0")]),
            "demandes": ("symptome_code", [(" S01 ", "S01"), ("S04", "S04"), ("", "")]),
        }
        for table, (nom, valeurs) in cas.items():
            with self.subTest(table=table, champ=nom):
                lignes = lire_lignes_csv(octets_v1(table))
                entete = lignes[0] + [nom]
                donnees = [ligne + [valeurs[i % len(valeurs)][0]] for i, ligne in enumerate(lignes[1:])]
                tampon = io.StringIO(newline="")
                csv.writer(tampon, delimiter=";", lineterminator="\r\n").writerows([entete] + donnees)
                resultat = self.analyser(table, BOM + tampon.getvalue().encode("utf-8"))
                self.assertEqual([p for p in resultat["problemes"] if p["type"] == "valeur"], [])
                self.assertNotIn(nom, [p["champ"] for p in resultat["problemes"]])
                for i, ligne in enumerate(resultat["lignes"]):
                    self.assertEqual(ligne[nom], valeurs[i % len(valeurs)][1], "%s ligne %d" % (table, i + 1))

    def test_valeur_illisible_d_un_nouveau_champ_est_une_erreur_de_valeur(self):
        lignes = lire_lignes_csv(octets_v1("ordres_travail"))
        donnees = [lignes[0] + ["anomalie_constatee"], lignes[1] + ["peut-être"]]
        tampon = io.StringIO(newline="")
        csv.writer(tampon, delimiter=";", lineterminator="\r\n").writerows(donnees)
        resultat = self.analyser("ordres_travail", BOM + tampon.getvalue().encode("utf-8"))
        valeurs = [(p["gravite"], p["champ"], p["valeur"]) for p in resultat["problemes"] if p["type"] == "valeur"]
        self.assertEqual(valeurs, [("erreur", "anomalie_constatee", "peut-être")])


# ---------------------------------------------------------------------------
# 3. Mode serveur : réécriture sur le disque par Donnees.modifier
# ---------------------------------------------------------------------------

class TestFormatV2ModeServeur(CasNavigateur):

    def setUp(self):
        super().setUp()
        # Copie du jeu de démo ; ServeurPrevo en refait une copie temporaire (jamais donnees/ réel), où ouvrir()
        # pose les fichiers v1 APRÈS le démarrage : le serveur passe au format courant à son démarrage (T185) ;
        # c'est le cas « le serveur n'a pas pu » (Excel ouvert) qui reste à lire et à réécrire par le navigateur.
        temporaire = tempfile.TemporaryDirectory(prefix="prevo-test-v2-")
        self.addCleanup(temporaire.cleanup)
        self.source = Path(temporaire.name) / "donnees"
        shutil.copytree(str(DOSSIER_DEMO), str(self.source))

    def ouvrir(self, serveur):
        """Les fichiers v1 à la place de ceux de la démo, puis page vide à l'adresse du serveur, scripts de Donnees
        et StockageServeur, 22 tables chargées."""
        for table in COLONNES_V2:
            (serveur.dossier / (table + ".csv")).write_bytes(octets_v1(table))
        adresse = serveur.url + "/test-format-v2.html"
        self.page.route(adresse, lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8", body=PAGE_VIDE_HTML))
        self.page.goto(adresse)
        for chemin in SCRIPTS_SERVEUR:
            self.page.add_script_tag(url=serveur.url + "/" + chemin)
        absentes = self.page.evaluate("""async () => {
            Donnees.initialiser(StockageServeur.creer(), { poste: 'Poste test', profil: 'Test format v2' });
            return (await Donnees.chargerTout()).tablesAbsentes;
        }""")
        self.assertEqual(absentes, [])

    def colonnes_signalees(self):
        return self.page.evaluate("""() => Donnees.problemes().filter((p) => p.type === 'colonne')
            .map((p) => [p.gravite, p.table, p.champ])""")

    def test_modifier_un_equipement_ecrit_la_colonne_v2_en_derniere_position(self):
        lignes_v1 = lire_lignes_csv(octets_v1("equipements"))
        identifiant = lignes_v1[1][0]
        nouvelle_designation = "Désignation modifiée ; format v2"
        with ServeurPrevo(source=self.source) as serveur:
            self.ouvrir(serveur)
            avant = self.colonnes_signalees()
            self.page.evaluate("""async ([id, designation]) => {
                await Donnees.modifier('equipements', (lignes) => {
                  lignes.find((ligne) => ligne.id === id).designation = designation;
                });
            }""", [identifiant, nouvelle_designation])
            apres = self.colonnes_signalees()
            octets = (serveur.dossier / "equipements.csv").read_bytes()
            journal = (serveur.dossier / "journal.csv").read_bytes().decode("utf-8-sig")
            demandes = (serveur.dossier / "demandes.csv").read_bytes()
            ordres = (serveur.dossier / "ordres_travail.csv").read_bytes()

        # Avant : une information par colonne v2 absente, rien d'autre ; après : la table réécrite
        # n'est plus signalée, les deux autres le restent (elles n'ont pas encore été enregistrées).
        self.assertEqual(sorted(avant), sorted([["info", "equipements", "valeur_remplacement"],
                                                ["info", "demandes", "symptome_code"],
                                                ["info", "demandes", "ot_origine_id"],
                                                ["info", "ordres_travail", "anomalie_constatee"],
                                                ["info", "ordres_travail", "astuce"]]))
        self.assertEqual(sorted(apres), sorted([["info", "demandes", "symptome_code"],
                                                ["info", "demandes", "ot_origine_id"],
                                                ["info", "ordres_travail", "anomalie_constatee"],
                                                ["info", "ordres_travail", "astuce"]]))
        # Sur le disque : format §3.1, valeur_remplacement en dernière colonne, le reste identique au v1.
        verifier_format_ecriture(self, octets, "equipements.csv")
        lignes_ecrites = lire_lignes_csv(octets)
        self.assertEqual(lignes_ecrites[0][-1], "valeur_remplacement")
        verifier_v1_plus_colonnes(self, lignes_v1, lignes_ecrites, "equipements",
                                  {(1, "designation"): nouvelle_designation})
        # Les tables non modifiées ne sont pas réécrites ; le journal ne note que le champ modifié.
        self.assertEqual(demandes, octets_v1("demandes"))
        self.assertEqual(ordres, octets_v1("ordres_travail"))
        self.assertIn("equipements;%s;modification : designation\r\n" % identifiant, journal)
        self.assertNotIn("valeur_remplacement", journal)

    def test_ecriture_et_relecture_de_chaque_nouveau_champ(self):
        equipement_id = lire_lignes_csv(octets_v1("equipements"))[1][0]
        ordres_v1 = lire_lignes_csv(octets_v1("ordres_travail"))
        ot_id, autre_ot_id = ordres_v1[1][0], ordres_v1[2][0]
        di_id = lire_lignes_csv(octets_v1("demandes"))[1][0]
        with ServeurPrevo(source=self.source) as serveur:
            self.ouvrir(serveur)
            # 1. Écriture par Donnees.modifier : formats du §3.1 (point décimal, 0/1, références brutes).
            self.page.evaluate("""async ([eq, ot, di]) => {
                await Donnees.modifier('equipements', (l) => { l.find((x) => x.id === eq).valeur_remplacement = '12500.5'; });
                await Donnees.modifier('ordres_travail', (l) => { l.find((x) => x.id === ot).anomalie_constatee = '1'; });
                await Donnees.modifier('demandes', (l) => {
                  const demande = l.find((x) => x.id === di);
                  demande.symptome_code = 'S01';
                  demande.ot_origine_id = ot;
                });
            }""", [equipement_id, ot_id, di_id])
            dossier = serveur.dossier
            equipements = lire_lignes_csv((dossier / "equipements.csv").read_bytes())
            ordres = lire_lignes_csv((dossier / "ordres_travail.csv").read_bytes())
            demandes = lire_lignes_csv((dossier / "demandes.csv").read_bytes())
            verifier_v1_plus_colonnes(self, lire_lignes_csv(octets_v1("equipements")), equipements, "equipements",
                                      {(1, "valeur_remplacement"): "12500.5"})
            verifier_v1_plus_colonnes(self, ordres_v1, ordres, "ordres_travail", {(1, "anomalie_constatee"): "1"})
            verifier_v1_plus_colonnes(self, lire_lignes_csv(octets_v1("demandes")), demandes, "demandes",
                                      {(1, "symptome_code"): "S01", (1, "ot_origine_id"): ot_id})

            # 2. Retouche « dans un tableur » : virgule française et espace, oui/x, espaces autour d'un code.
            equipements[1][-1] = "12 500,75"
            ordres[1][-2] = "non"      # anomalie_constatee, avant la colonne astuce (lot 6)
            ordres[2][-2] = "x"
            demandes[1][-2] = " S02 "
            ecrire_lignes_csv(dossier / "equipements.csv", equipements)
            ecrire_lignes_csv(dossier / "ordres_travail.csv", ordres)
            ecrire_lignes_csv(dossier / "demandes.csv", demandes)
            relu = self.relire(equipement_id, ot_id, autre_ot_id, di_id)
            self.assertEqual(relu["valeurs"], ["12500.75", "0", "1", "S02", ot_id])
            self.assertEqual(relu["problemes"], [])

            # 3. Références contrôlées : un code de cause n'est pas un symptôme, un OT inexistant est signalé.
            demandes[1][-2] = "C01"
            demandes[1][-1] = "OT-1999-0001"
            ecrire_lignes_csv(dossier / "demandes.csv", demandes)
            relu = self.relire(equipement_id, ot_id, autre_ot_id, di_id)
            self.assertEqual(relu["valeurs"][3:], ["C01", "OT-1999-0001"])
            self.assertEqual(sorted((p[0], p[1], p[2]) for p in relu["problemes"]),
                             [("erreur", "reference", "ot_origine_id"), ("erreur", "reference", "symptome_code")])
            message_symptome = [p[3] for p in relu["problemes"] if p[2] == "symptome_code"][0]
            self.assertIn("famille « symptôme »", message_symptome)

    def relire(self, equipement_id, ot_id, autre_ot_id, di_id):
        """Relit les trois tables depuis le serveur ; valeurs des nouveaux champs et problèmes qui les concernent."""
        return self.page.evaluate("""async ([eq, ot, autreOt, di]) => {
            for (const table of ['equipements', 'ordres_travail', 'demandes']) { await Donnees.rechargerTable(table); }
            const demande = Donnees.trouver('demandes', di);
            const nouveaux = ['valeur_remplacement', 'anomalie_constatee', 'symptome_code', 'ot_origine_id'];
            return {
              valeurs: [Donnees.trouver('equipements', eq).valeur_remplacement,
                        Donnees.trouver('ordres_travail', ot).anomalie_constatee,
                        Donnees.trouver('ordres_travail', autreOt).anomalie_constatee,
                        demande.symptome_code, demande.ot_origine_id],
              problemes: Donnees.problemes().filter((p) => nouveaux.includes(p.champ))
                .map((p) => [p.gravite, p.type, p.champ, p.message]),
            };
        }""", [equipement_id, ot_id, autre_ot_id, di_id])


if __name__ == "__main__":
    unittest.main()
