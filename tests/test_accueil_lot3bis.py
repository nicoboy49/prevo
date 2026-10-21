"""Accueil, lot 3 bis : instrument « Suggestions de préventif » (tâche T60, ARCHITECTURE.md §16.6 ;
CDC D58, D60).

Toujours serveur.py sur une copie du jeu de démo (ServeurPrevo), date du jour réelle :
    compteur  : nombre = suggestions ouvertes d'après un calcul Python indépendant sur les CSV du
                serveur (tests/test_regles_suggestions.calcul_python) et d'après Suggestions.ouvertes ;
                complément « dont n sur criticité A » ou « à examiner » ; lien vers l'onglet ;
    profils   : le responsable seul le voit (technicien et demandeur : rien) ;
    telephone : 375 px, aucun défilement horizontal de la page avec huit indicateurs.

Aucun identifiant du jeu de démo écrit en dur. Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_accueil_lot3bis.py" -v
"""
import csv
import datetime
import io
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil
from test_regles_suggestions import calcul_python

LIEN = "#/preventif?onglet=suggestions"
DEBORDEMENT_JS = """(selecteur) => { const e = document.querySelector(selecteur);
    return e ? [e.scrollWidth, e.clientWidth] : null; }"""


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return [{k: (v or "").strip().lstrip("'") for k, v in ligne.items()}
            for ligne in csv.DictReader(io.StringIO(texte), delimiter=";")]


class TestAccueilLot3bis(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def ouvrir(self, page, contexte, profil="responsable", nom="Responsable", technicien_id=""):
        preregler_profil(contexte, profil, nom, technicien_id)
        page.goto(self.serveur.url + "/#/accueil")
        attendre_pret(page)

    def test_compteur_egal_au_calcul_python_et_lien(self):
        self.ouvrir(self.page, self.contexte)
        aujourdhui = self.page.evaluate("Donnees.aujourdhui()")
        self.assertEqual(aujourdhui, datetime.date.today().isoformat())
        attendues = calcul_python(aujourdhui, dossier=self.serveur.dossier)
        self.assertGreater(len(attendues), 0, "la démo doit avoir des suggestions ouvertes")
        criticites = {e["id"]: e["criticite"] for e in lire_csv(self.serveur.dossier, "equipements.csv")}
        sur_a = sum(1 for s in attendues.values() if criticites.get(s["equipementId"]) == "A")

        lien = self.page.locator("#contenu .accueil-instruments a[href='%s']" % LIEN)
        self.assertEqual(lien.count(), 1)
        self.assertIn("Suggestions de préventif", lien.inner_text())
        self.assertEqual(int(lien.locator(".chiffre").inner_text()), len(attendues))
        self.assertEqual(self.page.evaluate("Suggestions.ouvertes(Donnees.aujourdhui()).length"), len(attendues))
        complement = lien.locator(".comp").inner_text()
        self.assertEqual(complement, "dont %d sur criticité A" % sur_a if sur_a else "à examiner")
        # Les sept indicateurs des lots 2 et 3 restent là, le nouveau s'y ajoute (accueil « bento », T90 :
        # 4 compteurs, 2 tuiles « à surveiller », les 2 liens de « Contrôles et habilitations »)
        self.assertEqual(self.page.locator(
            "#contenu #bento :is(a.bento-compteur, a.bento-surveiller, a.bento-sous-lien)").count(), 8)
        self.assertIn("bento-surveiller", lien.get_attribute("class"))

    def test_sans_suggestion_sur_criticite_a_le_complement_dit_a_examiner(self):
        # Serveur à part : ses équipements de criticité A passent en B (écriture dans sa copie seulement).
        with ServeurPrevo() as serveur:
            preregler_profil(self.contexte, "responsable", "Responsable")      # sans passer par le serveur partagé
            self.page.goto(serveur.url + "/#/accueil")
            attendre_pret(self.page)
            self.page.wait_for_load_state("networkidle")
            self.page.evaluate("""() => Donnees.modifier('equipements', (lignes) => {
              lignes.forEach((ligne) => { if (ligne.criticite === 'A') ligne.criticite = 'B'; });
            })""")
            self.page.evaluate("() => App.reafficher()")
            lien = self.page.locator("#contenu .accueil-instruments a[href='%s']" % LIEN)
            self.page.wait_for_function("(lien) => { const a = document.querySelector(`#contenu a[href='${lien}'] .comp`);"
                                        " return a && a.textContent === 'à examiner'; }", arg=LIEN)
            attendues = calcul_python(self.page.evaluate("Donnees.aujourdhui()"), dossier=serveur.dossier)
            self.assertEqual(int(lien.locator(".chiffre").inner_text()), len(attendues))

    def test_profils_technicien_et_demandeur_ne_le_voient_pas(self):
        technicien = next(t for t in lire_csv(self.serveur.dossier, "techniciens.csv") if t["actif"] != "0")
        for profil, nom, technicien_id in (("technicien", technicien["prenom"] + " " + technicien["nom"], technicien["id"]),
                                           ("demandeur", "Paul Martin", "")):
            with self.subTest(profil=profil):
                contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
                try:
                    page = contexte.new_page()
                    self.surveiller(page)
                    self.ouvrir(page, contexte, profil, nom, technicien_id)
                    page.wait_for_selector("#contenu h1")
                    self.assertEqual(page.locator("#contenu a[href='%s']" % LIEN).count(), 0)
                    self.assertNotIn("Suggestions de préventif", page.inner_text("#contenu"))
                finally:
                    contexte.close()

    def test_telephone_375_px_sans_defilement_horizontal(self):
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 375, "height": 812},
                                               is_mobile=True, has_touch=True)
        try:
            page = contexte.new_page()
            self.surveiller(page)
            self.ouvrir(page, contexte)
            self.assertEqual(page.locator("#contenu a[href='%s']" % LIEN).count(), 1)
            largeur, visible = page.evaluate(DEBORDEMENT_JS, "html")
            self.assertLessEqual(largeur, visible + 1)
            hauteur = page.locator("#contenu a[href='%s']" % LIEN).bounding_box()["height"]
            self.assertGreaterEqual(hauteur, 47.5)
        finally:
            contexte.close()


if __name__ == "__main__":
    unittest.main()
