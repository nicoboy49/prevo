"""Catalogue des contrôles et habilitations (France), données versionnées (T400). Sans réseau.

    py -X utf8 -m unittest discover -s tests -p "test_catalogue_donnees.py" -v
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "outils"))
import generer_catalogue  # noqa: E402

VALIDE = Path("C:/sync/nicolas/sites internet/gmao/.chantier/v2.2/L0/valide")
CHAMPS = {
    "controles": ["id", "famille", "nature", "equipements", "periodicite_mois", "periodicite_texte", "nature_source",
                  "reference", "liens", "qui_verifie", "a_confirmer", "relu_le"],
    "habilitations": ["id", "famille", "type", "titres", "duree_mois", "duree_texte", "nature_source", "reference",
                      "liens", "delivre_par", "a_confirmer", "relu_le"],
}
DUREE = {"controles": "periodicite_mois", "habilitations": "duree_mois"}


def lire(nom):
    with open(RACINE / "docs" / "catalogue" / (nom + "-fr.json"), encoding="utf-8") as f:
        return json.load(f)


class DonneesCatalogue(unittest.TestCase):
    def setUp(self):
        self.c = {l["id"]: l for l in lire("controles")["lignes"]}
        self.h = {l["id"]: l for l in lire("habilitations")["lignes"]}

    def test_effectifs_ids_ordre(self):
        for nom, prefixe, n in (("controles", "C", 31), ("habilitations", "H", 15)):
            ids = [l["id"] for l in lire(nom)["lignes"]]
            self.assertEqual(ids, ["%s%02d" % (prefixe, i) for i in range(1, n + 1)])

    def test_entete(self):
        for nom in CHAMPS:
            e = lire(nom)["entete"]
            self.assertEqual(e["catalogue"], nom + "-fr")
            self.assertEqual(e["pays"], "FR")
            self.assertEqual(e["valide_le"], "2026-11-08")

    def test_champs_et_valeurs(self):
        for nom, champs in CHAMPS.items():
            for l in lire(nom)["lignes"]:
                self.assertEqual(list(l), champs, l["id"])
                self.assertIn(l["nature_source"], {"obligation", "norme", "recommandation"}, l["id"])
                d = l[DUREE[nom]]
                self.assertTrue(d is None or (type(d) is int and d > 0), l["id"])
                self.assertIsInstance(l["a_confirmer"], bool, l["id"])
                for lien in l["liens"]:
                    self.assertTrue(lien["url"].startswith("https://"), l["id"])

    def test_cas_particuliers(self):
        self.assertEqual(self.c["C04"]["periodicite_mois"], 6)
        self.assertTrue(self.c["C04"]["a_confirmer"])
        self.assertIsNone(self.c["C13"]["periodicite_mois"])
        self.assertTrue(self.c["C13"]["a_confirmer"])
        self.assertTrue(self.h["H03"]["a_confirmer"])
        self.assertEqual(self.h["H01"]["nature_source"], "recommandation")
        self.assertEqual(self.h["H02"]["nature_source"], "recommandation")

    def test_mentions(self):
        for nom, texte in generer_catalogue.MENTIONS.items():
            for l in generer_catalogue.lignes_avec_mention(nom):
                self.assertEqual(l["mention"], texte if l["a_confirmer"] else "")


class Genere(unittest.TestCase):
    def test_generateur_reproduit_le_fichier(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = generer_catalogue.ecrire(tmp)
            self.assertEqual(chemin.read_bytes(), (RACINE / "js" / "catalogue" / "fr.js").read_bytes())
        self.assertNotIn(b"\r", (RACINE / "js" / "catalogue" / "fr.js").read_bytes())

    def test_conforme_au_fichier_valide(self):
        if not VALIDE.is_dir():
            self.skipTest("dossier .chantier absent")
        for nom, champs in CHAMPS.items():
            with open(VALIDE / ("catalogue-%s.json" % nom), encoding="utf-8") as f:
                source = json.load(f)
            lignes = lire(nom)["lignes"]
            self.assertEqual(len(lignes), len(source))
            for l, s in zip(lignes, source):
                self.assertEqual(l, {c: s[c] for c in champs}, l["id"])

    def test_evaluation_dans_node(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node absent")
        script = (
            "global.window = {}; require('fs'); "
            "eval(require('fs').readFileSync(process.argv[1], 'utf8')); "
            "const c = window.CatalogueFR; "
            "if (c.controles.length !== 31 || c.habilitations.length !== 15) process.exit(2); "
            "if (!Object.isFrozen(c) || !Object.isFrozen(c.controles[0].liens)) process.exit(3); "
            "console.log(c.controles.length);"
        )
        r = subprocess.run([node, "-e", script, str(RACINE / "js" / "catalogue" / "fr.js")],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "31")


if __name__ == "__main__":
    unittest.main()
