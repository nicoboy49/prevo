"""Tests de RG8 au planning, passer outre (T439 ; D186, D191 ; CS178, CS180 ; conception L2-L3 §7.4 et §7.6).

Mode serveur : un serveur.py neuf (copie du jeu de démo, dates non décalées) par test, CSV relus sur le disque.
Glisser-déposer et « Planifier… » passent par Ordres.avecDerogation : un OT dont l'équipement exige la BR, glissé sur
un technicien à BR échue, est refusé ; le responsable voit la fenêtre « Habilitation exigée non valide », Annuler
n'écrit rien, passer outre planifie et le journal garde le marqueur. Un OT sans exigence se planifie sans fenêtre.
Le technicien n'a que la lecture : ni carte déplaçable, ni bouton, ni dérogation même en appelant l'écriture.

Aucun identifiant du jeu de démo écrit en dur (rôles de tests/fixtures/demo-scenarios.json).
Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_rg8_planning.py" -v
"""
import datetime
import unittest

from test_planning import CasPlanning, ot_sur_disque

FENETRE = "dialog.ot-fenetre-derogation"
CASE = FENETRE + " [name=passer_outre]"
CHAMP_MOTIF = FENETRE + " [name=motif]"
PASSER_OUTRE = FENETRE + " .ot-passer-outre"
ANNULER = FENETRE + " .fenetre-actions .btn-fantome"
MOTIF = "Électricien du site présent ; consignation faite par lui"


class TestRg8Planning(CasPlanning):

    def preparer(self, ot_cle="ot_a_planifier_br", decalage=4):
        ot_id = self.scenarios[ot_cle]
        lundi = self.semaine_de(ot_id)
        jour = (datetime.date.fromisoformat(lundi) + datetime.timedelta(days=decalage)).isoformat()
        return ot_id, lundi, jour

    def verifier_fenetre(self):
        fenetre = self.page.wait_for_selector(FENETRE)
        self.assertEqual(fenetre.query_selector("h2").inner_text(), "Habilitation exigée non valide")
        self.assertIn(self.scenarios["technicien_br_echue"], fenetre.inner_text())
        self.assertTrue(self.page.is_disabled(PASSER_OUTRE))

    def passer_outre(self):
        self.page.fill(CHAMP_MOTIF, MOTIF)
        self.page.check(CASE)
        self.assertTrue(self.page.is_enabled(PASSER_OUTRE))
        self.page.click(PASSER_OUTRE)
        self.page.wait_for_selector(FENETRE, state="detached")

    def verifier_planifie_avec_derogation(self, ot_id, technicien, jour):
        self.assertTrue(self.attendre_disque(lambda: ot_sur_disque(self.serveur.dossier, ot_id)["statut"] == "Planifié"))
        ligne = ot_sur_disque(self.serveur.dossier, ot_id)
        self.assertEqual((ligne["technicien_id"], ligne["date_prevue"]), (technicien, jour))
        marqueur = "dérogation habilitation : %s le %s sans BR (échue) ; motif : %s" % (technicien, jour, MOTIF)
        self.assertTrue(self.attendre_disque(lambda: any(a.endswith(" ; " + marqueur) for a in self.journal_de(ot_id))),
                        self.journal_de(ot_id))
        entree = [e for e in self.journal_de(ot_id) if e.endswith(marqueur)][-1]
        self.assertIn("planification : %s le %s (Préparé → Planifié)" % (technicien, jour), entree)

    def test_glisser_refuse_annuler_n_ecrit_rien_puis_passer_outre_et_journal(self):
        ot_id, lundi, jour = self.preparer()
        technicien = self.scenarios["technicien_br_echue"]
        avant = self.journal_de(ot_id)
        page = self.ouvrir("#/planning?semaine=" + lundi)
        page.drag_and_drop(".pl-a-planifier " + self.carte(ot_id), self.case(technicien, jour))
        self.verifier_fenetre()
        page.click(ANNULER)
        page.wait_for_selector(FENETRE, state="detached")
        message = page.wait_for_selector("#pl-message .alerte.important").inner_text()
        self.assertIn("Affectation refusée", message)
        ligne = ot_sur_disque(self.serveur.dossier, ot_id)
        self.assertEqual((ligne["statut"], ligne["technicien_id"]), ("Préparé", ""))
        self.assertEqual(self.journal_de(ot_id), avant)

        page.drag_and_drop(".pl-a-planifier " + self.carte(ot_id), self.case(technicien, jour))
        self.verifier_fenetre()
        self.passer_outre()
        page.wait_for_selector(self.case(technicien, jour) + " " + self.carte(ot_id))
        self.verifier_planifie_avec_derogation(ot_id, technicien, jour)

    def test_bouton_planifier_meme_fenetre_et_meme_resultat(self):
        ot_id, lundi, jour = self.preparer(decalage=3)
        technicien = self.scenarios["technicien_br_echue"]
        page = self.ouvrir("#/planning?semaine=" + lundi)
        page.click(".pl-a-planifier " + self.carte(ot_id) + ' [data-action="planifier"]')
        page.select_option("#pl-technicien", technicien)
        page.fill("#pl-date", jour)
        page.click("dialog .fenetre-actions button:has-text('Planifier')")
        self.verifier_fenetre()
        self.passer_outre()
        page.wait_for_selector(self.case(technicien, jour) + " " + self.carte(ot_id))
        self.verifier_planifie_avec_derogation(ot_id, technicien, jour)

    def test_ot_sans_exigence_se_planifie_sans_fenetre(self):
        ot_id, lundi, jour = self.preparer("ot_a_planifier", 2)
        technicien = self.scenarios["technicien_br_echue"]
        page = self.ouvrir("#/planning?semaine=" + lundi)
        page.drag_and_drop(".pl-a-planifier " + self.carte(ot_id), self.case(technicien, jour))
        page.wait_for_selector(self.case(technicien, jour) + " " + self.carte(ot_id))
        self.assertEqual(page.locator(FENETRE).count(), 0)
        self.assertTrue(self.attendre_disque(lambda: ot_sur_disque(self.serveur.dossier, ot_id)["statut"] == "Planifié"))
        self.assertFalse(any("dérogation" in a for a in self.journal_de(ot_id)))

    def test_technicien_lecture_seule_et_aucune_derogation_par_l_api(self):
        ot_id, lundi, jour = self.preparer()
        technicien = self.scenarios["technicien_br_echue"]
        page = self.ouvrir("#/planning?semaine=" + lundi, "technicien", "Technicien", technicien)
        self.assertEqual(page.locator('.pl-ot[draggable="true"]').count(), 0)
        self.assertEqual(page.locator('[data-action="planifier"]').count(), 0)
        refus = page.evaluate("""async ([ot, tec, jour]) => {
            try { await Planning.planifier(ot, 'Préparé', tec, jour, { passerOutreHabilitation: true, motifDerogation: 'x' }); return ''; }
            catch (e) { return e.message; } }""", [ot_id, technicien, jour])
        self.assertIn("Affectation refusée", refus)
        self.assertEqual(ot_sur_disque(self.serveur.dossier, ot_id)["statut"], "Préparé")
        self.assertEqual(page.locator(FENETRE).count(), 0)


if __name__ == "__main__":
    unittest.main()
