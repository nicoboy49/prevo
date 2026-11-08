"""Corrections diverses de l'audit (lot 7, ARCHITECTURE.md §22.12 ; tâche T160) : I3, I4, G3, G5.

Couvre :
    I3 — une colonne inconnue (hors schéma) dont la valeur commence par « = » est écrite avec l'apostrophe de
         protection et relue à l'identique (relireValeur(ecrireValeur(v)) === v, §3.2) ;
    I4 — Ia.masquer remplace les numéros de téléphone et les adresses de courriel par « [téléphone] » et
         « [courriel] », et laisse intacts les identifiants d'OT, les dates et les nombres techniques ; les messages
         envoyés à l'IA (compte rendu, ingestion du wiki) sont masqués ;
    G3 — aucun numéro de téléphone français hors de la plage fictive de l'ARCEP dans tests/ et outils/ (tolérées :
         04 65 71 00 00 à 99 et 06 39 98 00 00 à 99, qui contiennent celle de la démo 04 65 71 00 01 à 05) ;
    G5 — aucun exemple « fournisseur.fr » (domaine réel) dans js/.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_audit_divers.py" -v
"""
import base64
import io
import re
import unittest
import zipfile

from commun import RACINE, CasNavigateur, charger_scripts

SCRIPTS = ["js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/interface.js",
           "js/modules/ia.js", "js/modules/ia-prompts.js"]

# Numéro de téléphone français : 0X XX XX XX XX ou +33 / 0033, groupes collés ou séparés par un même caractère.
# Pas précédé d'un chiffre, d'une lettre, d'un point ou d'une virgule (décimales « 0.0514459929 ») ; sauf une
# séquence d'échappement écrite dans une chaîne (« \t0490… », « \n0490… ») : constat B8 du Lot 0, que ce motif ne
# voyait pas (le « t » de « \t » est une lettre).
MOTIF_TELEPHONE = re.compile(r"(?:(?<![\w.,])|(?<=\\[tnr]))(?:(?:\+|00)33[ .-]?(?:\(0\)[ .-]?)?|0)([1-9])([ .-]?)(\d{2})\2(\d{2})\2(\d{2})\2(\d{2})(?!\w)")
PLAGES_FICTIVES = ("04657100", "06399800")       # ARCEP, œuvres de fiction : 04 65 71 00 xx, 06 39 98 00 xx
PAS_UN_NUMERO = {"0123456789"}                    # suite des chiffres (alphabet d'un test de tirage)
EXTENSIONS_TEXTE = {".py", ".js", ".csv", ".tsv", ".md", ".html", ".json", ".txt"}
EXTENSIONS_ZIP = {".xlsx", ".ods"}


def textes_du_fichier(chemin):
    """Textes lisibles d'un fichier : le fichier lui-même (UTF-8, sinon Windows-1252) ou les XML d'un classeur."""
    octets = chemin.read_bytes()
    if chemin.suffix.lower() in EXTENSIONS_ZIP and zipfile.is_zipfile(io.BytesIO(octets)):
        with zipfile.ZipFile(io.BytesIO(octets)) as archive:
            return [archive.read(nom).decode("utf-8", "replace") for nom in archive.namelist() if nom.endswith(".xml")]
    if chemin.suffix.lower() in EXTENSIONS_TEXTE | EXTENSIONS_ZIP:     # un faux classeur d'essai est lu en texte
        try:
            return [octets.decode("utf-8")]
        except UnicodeDecodeError:
            return [octets.decode("cp1252", "replace")]
    return []


def numeros_hors_plage(texte):
    """Numéros de téléphone du texte qui ne sont pas dans la plage fictive."""
    trouves = []
    for m in MOTIF_TELEPHONE.finditer(texte):
        national = "0" + "".join(m.group(i) for i in (1, 3, 4, 5, 6))
        if m.group(0) in PAS_UN_NUMERO or national.startswith(PLAGES_FICTIVES):
            continue
        trouves.append(m.group(0))
    return trouves


class TestColonnesInconnues(CasNavigateur):
    """I3 : colonnes hors schéma protégées par apostrophe comme un champ texte."""

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)

    def aller_retour(self, valeurs):
        return self.page.evaluate("""(valeurs) => {
            const lignes = valeurs.map((v, i) => ({ id: 'FOU-000' + (i + 1), nom: 'Fournisseur ' + i, colonne_maison: v }));
            const octets = Donnees.csv.serialiser('fournisseurs', lignes, ['colonne_maison']);
            const texte = new TextDecoder('utf-8').decode(octets);
            const relu = Donnees.csv.analyser('fournisseurs', octets);
            const reecrit = new TextDecoder('utf-8').decode(Donnees.csv.serialiser('fournisseurs', relu.lignes, relu.colonnesInconnues));
            return { texte, inconnues: relu.colonnesInconnues, relues: relu.lignes.map((l) => l.colonne_maison), reecrit };
        }""", valeurs)

    def test_formule_ecrite_avec_apostrophe_et_relue_a_l_identique(self):
        resultat = self.aller_retour(["=SOMME(A1:A3)"])
        self.assertIn(";'=SOMME(A1:A3)\r\n", resultat["texte"])
        self.assertEqual(resultat["inconnues"], ["colonne_maison"])
        self.assertEqual(resultat["relues"], ["=SOMME(A1:A3)"])
        self.assertEqual(resultat["reecrit"], resultat["texte"])            # stable : pas d'apostrophe en plus

    def test_valeurs_piegees_relues_a_l_identique(self):
        valeurs = ["=1+1", "+33 6 39 98 00 12", "-3", "@lien", "'deja", "''double", "0465710001", "7,5", "1/2",
                   "texte simple", "", "a;b", 'guillemet "x"']
        resultat = self.aller_retour(valeurs)
        self.assertEqual(resultat["relues"], valeurs)
        self.assertEqual(resultat["reecrit"], resultat["texte"])
        for dangereuse in ("=1+1", "-3", "@lien"):
            self.assertIn(";'" + dangereuse + "\r\n", resultat["texte"])


class TestMasquage(CasNavigateur):
    """I4 : numéros de téléphone et adresses de courriel masqués avant l'envoi à l'IA."""

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)

    def masquer(self, texte):
        return self.page.evaluate("(texte) => Ia.masquer(texte)", texte)

    def test_masque_telephones_et_courriels(self):
        cas = {
            "Rappeler M. Untel au 06 39 98 00 12.": "Rappeler M. Untel au [téléphone].",
            "fixe 04.65.71.00.07 ou 04-65-71-00-08": "fixe [téléphone] ou [téléphone]",
            "tél 0639980012": "tél [téléphone]",
            "+33 6 39 98 00 12 / +33 (0)4 65 71 00 07 / 0033639980012": "[téléphone] / [téléphone] / [téléphone]",
            "écrire à m.untel@atelier-demo.example avant": "écrire à [courriel] avant",
            "voir contact@fournisseur.example.": "voir [courriel].",
        }
        for source, attendu in cas.items():
            with self.subTest(source=source):
                self.assertEqual(self.masquer(source), attendu)

    def test_laisse_intacts_ot_dates_et_nombres_techniques(self):
        for texte in ("OT-2026-0107", "[OT-2026-0107]", "15 855 h", "0,58 bar", "19/10/2026", "2026-10-19 08:30",
                      "05.10.2026 08:30", "1 200 tr/min", "réf. 6205-2RS", "jeu 0,05 mm", "SN-000777", "12 345 678"):
            with self.subTest(texte=texte):
                self.assertEqual(self.masquer(texte), texte)
        self.assertEqual(self.masquer("OT-2026-0107 le 19/10/2026 : 0,58 bar à 15 855 h, appeler 06 39 98 00 12"),
                         "OT-2026-0107 le 19/10/2026 : 0,58 bar à 15 855 h, appeler [téléphone]")

    def test_messages_envoyes_a_l_ia_masques(self):
        messages = self.page.evaluate("""() => {
            const notes = 'Fuite au raccord, vu avec le fournisseur au 06 39 98 00 12 (m.untel@atelier-demo.example). 0,58 bar.';
            return {
              compteRendu: Ia.PROMPTS.compteRendu.utilisateur({ notes, titre: 'Fuite', repere: 'CMP-03' }),
              reformulerDI: Ia.PROMPTS.reformulerDI.utilisateur({ symptome: 'bruit', description: notes }),
              ingestion: Ia.PROMPTS.ingestionWiki.utilisateur({
                ot: { id: 'OT-2026-0107', dateIntervention: '2026-10-19', type: 'correctif', titre: 'Fuite',
                      compteRendu: notes, astuce: 'Appeler le 04 65 71 00 07 avant.' },
                pages: [{ titre: 'CMP-03', type: 'équipement', texte: 'Contact : 06.39.98.00.13 [OT-2026-0100].' }],
                catalogue: [] }),
              systeme: Ia.PROMPTS.compteRendu.systeme,
            };
        }""")
        for nom in ("compteRendu", "reformulerDI", "ingestion"):
            with self.subTest(fonction=nom):
                message = messages[nom]
                self.assertIn("[téléphone]", message)
                self.assertNotRegex(message, r"06[ .]39[ .]98|04 65 71 00 07|@atelier-demo")
                self.assertIn("0,58 bar", message)
        self.assertIn("[courriel]", messages["compteRendu"])
        self.assertIn("OT-2026-0107", messages["ingestion"])
        self.assertIn("[OT-2026-0100]", messages["ingestion"])
        self.assertNotIn("[téléphone]", messages["systeme"])               # la consigne ne change pas


class TestDepotSansDonneeReelle(unittest.TestCase):
    """G3 et G5 : numéros fictifs seulement, aucun domaine réel en exemple."""

    def test_le_motif_reconnait_les_numeros(self):
        # Sondes hors de la plage tolérée mais dans les blocs fictifs de l'ARCEP (04 65 71 xx xx, 06 39 98 xx xx) :
        # ce fichier ne cite aucun numéro attribuable (il est exclu du balayage ci-dessous pour ces seules sondes).
        self.assertEqual(numeros_hors_plage("tél 04 65 71 01 30, port. +33 6 39 98 12 34, 0639981234, 04.65.71.99.99"),
                         ["04 65 71 01 30", "+33 6 39 98 12 34", "0639981234", "04.65.71.99.99"])
        self.assertEqual(numeros_hors_plage("04 65 71 00 01 ; 0465710099 ; +33 6 39 98 00 78 ; 0639980012"), [])
        self.assertEqual(numeros_hors_plage("0.0514459929 * b ; OT-2026-0107 ; 15 855 h ; '0123456789'"), [])

    def test_aucun_numero_hors_plage_fictive_dans_tests_et_outils(self):
        trouves = []
        for dossier in ("tests", "outils"):
            for chemin in sorted((RACINE / dossier).rglob("*")):
                if not chemin.is_file() or "__pycache__" in chemin.parts:
                    continue
                for texte in textes_du_fichier(chemin):
                    trouves += ["%s : %s" % (chemin.relative_to(RACINE).as_posix(), n) for n in numeros_hors_plage(texte)
                                if chemin.name != "test_audit_divers.py"]
        self.assertEqual(trouves, [])

    def test_aucun_fournisseur_fr_dans_js(self):
        trouves = [chemin.relative_to(RACINE).as_posix() for chemin in sorted((RACINE / "js").rglob("*.js"))
                   if "fournisseur.fr" in chemin.read_text(encoding="utf-8", errors="replace")]
        self.assertEqual(trouves, [])


if __name__ == "__main__":
    unittest.main()
