"""Synthèses du wiki livrées avec la démo (tâche T101, ARCHITECTURE.md §20.8, décision D98 de Nicolas).

    fichier figé : outils/demo_wiki_syntheses.csv — en-tête exact, une synthèse par équipement à au moins 5 OT
                   correctifs clôturés (12), statut « à valider » ou « validée », modèle réellement utilisé
                   (Claude), aucune date dans le texte (la démo décale ses dates) ; chaque OT cité est parmi les
                   OT envoyés, et chaque OT envoyé est un OT clôturé de l'équipement ;
    générateur   : outils/generer_demo.py le reprend tel quel (donnees/demo identique à l'octet), deux
                   générations donnent le même fichier ;
    dans la page : les 12 synthèses passent les contrôles du §20.4 (Wiki.controlerSynthese) ; ce sont exactement
                   les équipements des requêtes de la démo (Wiki.requetesDemo) ; « À propos » porte la mention
                   « Synthèses de démo rédigées par Claude avec le prompt de Prévo ».

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_demo.py" -v
"""
import csv
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from commun import RACINE, CasNavigateur, attendre_pret, preregler_profil, url_fichier

FIGE = RACINE / "outils" / "demo_wiki_syntheses.csv"
DEMO = RACINE / "donnees" / "demo"
CHAMPS = ["id", "equipement_id", "texte", "ot_cites", "ot_sources", "statut", "modele", "date_proposition",
          "corrigee_par", "date_modification", "valide_par", "date_validation"]
MENTION = "Synthèses de démo rédigées par Claude avec le prompt de Prévo"
MOTIF_CITATION = re.compile(r"\[OT-\d{4}-\d{4,}\]")
MOTIF_DATE = re.compile(r"\b20[1-3]\d\b|\b\d{1,2}/\d{1,2}\b|\b(?:janvier|février|mars|avril|mai|juin|juillet|août|"
                        r"septembre|octobre|novembre|décembre)\b", re.IGNORECASE)
STATUTS_CLOTURES = ("Clôturé techniquement", "Clôturé administrativement")


def lire(chemin):
    texte = Path(chemin).read_text(encoding="utf-8-sig")
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=";")
    return lecteur.fieldnames, list(lecteur)


def ids(valeur):
    return [morceau.strip() for morceau in valeur.split(";") if morceau.strip()]


class TestFichierFige(unittest.TestCase):

    def setUp(self):
        self.entete, self.lignes = lire(FIGE)
        _, ordres = lire(DEMO / "ordres_travail.csv")
        self.ordres = {o["id"]: o for o in ordres}

    def test_forme_du_fichier(self):
        self.assertEqual(self.entete, CHAMPS)
        self.assertEqual(len(self.lignes), 12)
        self.assertEqual([l["id"] for l in self.lignes], ["WIKI-%04d" % n for n in range(1, 13)])
        self.assertEqual(len({l["equipement_id"] for l in self.lignes}), 12)
        for ligne in self.lignes:
            with self.subTest(synthese=ligne["id"]):
                self.assertIn(ligne["statut"], ("à valider", "validée"))
                self.assertIn("claude", ligne["modele"].lower())
                self.assertRegex(ligne["date_proposition"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
                self.assertEqual(ligne["corrigee_par"] == "", ligne["date_modification"] == "")
                if ligne["statut"] == "validée":
                    self.assertTrue(ligne["valide_par"] and ligne["date_validation"])
                else:
                    self.assertEqual((ligne["valide_par"], ligne["date_validation"]), ("", ""))
                self.assertEqual(MOTIF_DATE.findall(MOTIF_CITATION.sub(" ", ligne["texte"])), [])

    def test_ot_cites_parmi_les_envoyes_et_envoyes_clotures_de_l_equipement(self):
        for ligne in self.lignes:
            with self.subTest(synthese=ligne["id"]):
                sources, cites = ids(ligne["ot_sources"]), ids(ligne["ot_cites"])
                self.assertTrue(cites)
                self.assertTrue(set(cites) <= set(sources))
                self.assertEqual(sorted(set(MOTIF_CITATION.findall(ligne["texte"]))), sorted("[%s]" % c for c in cites))
                for identifiant in sources:
                    ot = self.ordres[identifiant]
                    self.assertEqual(ot["equipement_id"], ligne["equipement_id"])
                    self.assertIn(ot["statut"], STATUTS_CLOTURES)

    def test_un_equipement_par_seuil_de_5_correctifs_clotures(self):
        compte = {}
        for ot in self.ordres.values():
            if ot["type"].startswith("correctif") and ot["statut"] in STATUTS_CLOTURES:
                compte[ot["equipement_id"]] = compte.get(ot["equipement_id"], 0) + 1
        attendus = {e for e, n in compte.items() if n >= 5}
        self.assertEqual({l["equipement_id"] for l in self.lignes}, attendus)


class TestGenerateur(unittest.TestCase):

    def test_repris_tel_quel_et_deterministe(self):
        self.assertEqual((DEMO / "wiki_syntheses.csv").read_bytes(), FIGE.read_bytes())
        sorties = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as dossier:
                subprocess.run([sys.executable, str(RACINE / "outils" / "generer_demo.py"), "--sortie", dossier, "--sans-js"],
                               check=True, capture_output=True)
                sorties.append((Path(dossier) / "wiki_syntheses.csv").read_bytes())
        self.assertEqual(sorties[0], sorties[1])
        self.assertEqual(sorties[0], FIGE.read_bytes())


class TestDansLaPage(CasNavigateur):

    def setUp(self):
        super().setUp()
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)

    def test_controles_du_contrat_et_equipements_des_requetes(self):
        resultat = self.page.evaluate("""() => {
          const syntheses = Donnees.lignes('wiki_syntheses');
          return {
            controles: syntheses.map((s) => [s.id, Wiki.controlerSynthese(s.texte, s.ot_sources.split(';')).raisons]),
            equipements: syntheses.map((s) => s.equipement_id).sort(),
            requetes: Wiki.requetesDemo().map((r) => r.equipementId).sort(),
          };
        }""")
        for identifiant, raisons in resultat["controles"]:
            with self.subTest(synthese=identifiant):
                self.assertEqual(raisons, [])
        self.assertEqual(resultat["equipements"], resultat["requetes"])

    def test_mention_dans_a_propos(self):
        self.page.evaluate("location.hash = '#/apropos'")
        self.page.wait_for_selector("#apropos-syntheses-demo")
        texte = " ".join(self.page.inner_text("#apropos-syntheses-demo").split())
        self.assertIn(MENTION, texte)


if __name__ == "__main__":
    unittest.main()
