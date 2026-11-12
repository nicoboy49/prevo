"""Écrans après une dérogation d'habilitation non tracée (T510 ; suite de T504, D186 ; relecture du 12/11).

Mode serveur : un serveur.py neuf (copie du jeu de démo) par test, CSV relus sur le disque. L'ajout au journal est
mis en panne (la requête POST /api/csv/journal/ajout reçoit une réponse 500, comme un journal.csv verrouillé) : le
responsable passe outre le blocage d'habilitation, l'OT est écrit mais la dérogation n'est pas notée
(Ordres.ecrireAvecTrace lève Donnees.ErreurStockage, erreur.otEcrit). L'écran doit alors suivre l'état écrit :
  - nouvel OT : le formulaire est fermé, la fiche de l'OT créé est affichée avec le message (un second clic sur
    « Enregistrer » ne peut plus créer de doublon : la table ne compte qu'un OT de plus) ;
  - préparation et bouton « Planifier » : la fiche est réaffichée avec l'état écrit et le message ;
  - planning : la carte est dans sa case, le message est dans le bandeau de l'écran.

Aucun identifiant du jeu de démo écrit en dur (rôles de tests/fixtures/demo-scenarios.json).
Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_derogation_ecran.py" -v
"""
import datetime
import re
import unittest

from test_planning import CasPlanning, lire_csv, ot_sur_disque

FENETRE = "dialog.ot-fenetre-derogation"
MOTIF = "Électricien du site présent ; consignation faite par lui"
DATE = "2026-11-20"
MESSAGE_FICHE = ".ot-fiche .ot-bandeau-etat .alerte.important"
PLANIFIER = ".ot-actions button[data-action='transition'][data-cible='Planifié']"


def non_tracee(ot_id):
    return "%s est enregistré, mais la dérogation n'a pas pu être notée au journal : refaites l'affectation." % ot_id


class TestDerogationEcran(CasPlanning):

    def setUp(self):
        super().setUp()
        self.equipement = self.scenarios["equipement_br"]
        self.technicien = self.scenarios["technicien_br_echue"]
        # La réponse 500 voulue est dite par le navigateur dans la console.
        self.autoriser_erreur(re.compile(r"Failed to load resource.*500"))

    # -- outils ----------------------------------------------------------------------------------

    def casser_journal(self):
        self.page.route("**/api/csv/journal/ajout", lambda route: route.fulfill(
            status=500, content_type="application/json", body='{"erreur": "journal.csv verrouillé (essai)"}'))

    def passer_outre(self):
        self.page.wait_for_selector(FENETRE)
        self.page.fill(FENETRE + " [name=motif]", MOTIF)
        self.page.check(FENETRE + " [name=passer_outre]")
        self.page.click(FENETRE + " .ot-passer-outre")
        self.page.wait_for_selector(FENETRE, state="detached")

    def ots(self):
        return lire_csv(self.serveur.dossier, "ordres_travail.csv")

    def choisir_affectation(self, formulaire):
        self.page.select_option(formulaire + " [name=technicien_id]", self.technicien)
        self.page.fill(formulaire + " [name=date_prevue]", DATE)
        self.page.dispatch_event(formulaire + " [name=date_prevue]", "change")

    def attendre_fiche(self, ot_id):
        self.page.wait_for_function(
            "(id) => { const n = document.querySelector('.ot-fiche .ot-numero'); return n && n.textContent === id; }",
            arg=ot_id)

    def ot_prepare(self, titre):
        """OT « Préparé » sur l'équipement à BR, sans technicien, par les écritures elles-mêmes."""
        ot_id = self.page.evaluate(
            "([equipement, titre]) => Ordres.creer({ equipement_id: equipement, titre, type: 'correctif différé', priorite: 'P3' })",
            [self.equipement, titre])
        self.page.evaluate("(id) => Ordres.changerStatut(id, 'Créé', 'Préparé')", ot_id)
        return ot_id

    def verifier_sans_trace(self, ot_id):
        self.assertFalse(any("dérogation" in action for action in self.journal_de(ot_id)), self.journal_de(ot_id))

    # -- nouvel OT : le formulaire ne reste pas ouvert sur un OT déjà créé ------------------------

    def test_nouvel_ot_non_trace_montre_la_fiche_et_le_message_sans_doublon(self):
        page = self.ouvrir("#/ot/nouveau?equipement=" + self.equipement)
        page.wait_for_selector("#form-nouvel-ot")
        page.fill("#form-nouvel-ot [name=titre]", "T510 — nouvel OT")
        self.choisir_affectation("#form-nouvel-ot")
        avant = {ot["id"] for ot in self.ots()}
        self.casser_journal()
        page.click("#form-nouvel-ot button[type=submit]")
        self.passer_outre()

        self.assertTrue(self.attendre_disque(lambda: len(self.ots()) == len(avant) + 1))
        ot_id = next(ot["id"] for ot in self.ots() if ot["id"] not in avant)
        # L'écran montre l'OT créé et le message ; le formulaire de création n'est plus là.
        self.attendre_fiche(ot_id)
        self.assertEqual(page.evaluate("location.hash"), "#/ot/" + ot_id)
        self.assertEqual(page.locator("#form-nouvel-ot").count(), 0)
        self.assertEqual(page.wait_for_selector(MESSAGE_FICHE).inner_text().strip(), non_tracee(ot_id))
        # Un seul OT de plus, avec l'affectation écrite ; aucune dérogation au journal.
        ligne = ot_sur_disque(self.serveur.dossier, ot_id)
        self.assertEqual((ligne["technicien_id"], ligne["date_prevue"], ligne["statut"]), (self.technicien, DATE, "Créé"))
        self.assertEqual(len(self.ots()), len(avant) + 1)
        self.verifier_sans_trace(ot_id)
        # Le message n'est dit qu'une fois : la fiche rouverte ne le montre plus.
        page.evaluate("App.reafficher()")
        self.attendre_fiche(ot_id)
        self.assertEqual(page.locator(MESSAGE_FICHE).count(), 0)

    # -- préparation : la fiche est réaffichée avec l'état écrit ----------------------------------

    def test_preparation_non_tracee_reaffiche_la_fiche_ecrite_et_le_message(self):
        page = self.ouvrir("#/ot")
        ot_id = self.ot_prepare("T510 — préparation")
        page.evaluate("(id) => { location.hash = '#/ot/' + id; }", ot_id)
        self.attendre_fiche(ot_id)
        page.click(".onglet[data-onglet='preparation']")
        page.wait_for_selector("#form-preparation")
        self.choisir_affectation("#form-preparation")
        self.casser_journal()
        page.click("#form-preparation button[type=submit]")
        self.passer_outre()

        self.assertEqual(page.wait_for_selector(MESSAGE_FICHE).inner_text().strip(), non_tracee(ot_id))
        ligne = ot_sur_disque(self.serveur.dossier, ot_id)
        self.assertEqual((ligne["technicien_id"], ligne["date_prevue"]), (self.technicien, DATE))
        # Fiche réaffichée : le formulaire porte l'état écrit et n'est plus « modifié ».
        self.assertEqual(page.input_value("#form-preparation [name=technicien_id]"), self.technicien)
        self.assertNotEqual(page.get_attribute("#form-preparation", "data-modifie"), "1")
        self.verifier_sans_trace(ot_id)

    # -- bouton « Planifier » : le statut écrit est affiché ----------------------------------------

    def test_planifier_non_trace_reaffiche_le_statut_ecrit_et_le_message(self):
        page = self.ouvrir("#/ot")
        ot_id = self.ot_prepare("T510 — planifier")
        # Affectation d'avant la 2.2 (RG8 non rétroactive) : écrite sans contrôle ni journal.
        page.evaluate("""([id, technicien, date]) => Donnees.modifier('ordres_travail', (lignes) => {
            Object.assign(lignes.find((o) => o.id === id), { technicien_id: technicien, date_prevue: date }); },
            { journal: false })""", [ot_id, self.technicien, DATE])
        page.evaluate("(id) => { location.hash = '#/ot/' + id; }", ot_id)
        self.attendre_fiche(ot_id)
        self.casser_journal()
        page.click(PLANIFIER)
        self.passer_outre()

        self.assertEqual(page.wait_for_selector(MESSAGE_FICHE).inner_text().strip(), non_tracee(ot_id))
        self.assertEqual(page.inner_text(".ot-badges .badge.statut"), "Planifié")
        self.assertEqual(page.locator(PLANIFIER).count(), 0)
        self.assertEqual(ot_sur_disque(self.serveur.dossier, ot_id)["statut"], "Planifié")
        self.verifier_sans_trace(ot_id)

    # -- planning : la carte est à sa place, le message dans le bandeau ---------------------------

    def test_planning_non_trace_reaffiche_la_grille_et_le_message(self):
        ot_id = self.scenarios["ot_a_planifier_br"]
        lundi = self.semaine_de(ot_id)
        jour = (datetime.date.fromisoformat(lundi) + datetime.timedelta(days=4)).isoformat()
        page = self.ouvrir("#/planning?semaine=" + lundi)
        self.casser_journal()
        page.drag_and_drop(".pl-a-planifier " + self.carte(ot_id), self.case(self.technicien, jour))
        self.passer_outre()

        page.wait_for_selector(self.case(self.technicien, jour) + " " + self.carte(ot_id))
        self.assertEqual(page.locator(".pl-a-planifier " + self.carte(ot_id)).count(), 0)
        self.assertIn(non_tracee(ot_id), page.wait_for_selector("#pl-message .alerte").inner_text())
        ligne = ot_sur_disque(self.serveur.dossier, ot_id)
        self.assertEqual((ligne["statut"], ligne["technicien_id"], ligne["date_prevue"]), ("Planifié", self.technicien, jour))
        self.verifier_sans_trace(ot_id)


if __name__ == "__main__":
    unittest.main()
