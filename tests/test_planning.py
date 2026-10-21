"""Tests de l'écran Planning (tâche T48, ARCHITECTURE.md §15.5 ; brief §9 E6, §7 RG3 et RG8).

Mode serveur : un serveur.py neuf (copie du jeu de démo, dates non décalées) PAR TEST, car les
tests planifient ; vérifications sur le disque (ordres_travail.csv, journal.csv). Mode démo :
index.html en file:// (dates décalées par semaines entières), glisser-déposer seulement.
Familles (le nom du test le dit) :
    glisser     un OT « Préparé » glissé sur un technicien et un jour → « Planifié », technicien et
                date enregistrés, journal « planification : … » ;
    bouton      même résultat par « Planifier… » (sans glisser : WCAG 2.2, critère 2.5.7) ;
    replanifier un OT « Planifié » déplacé change de date sans changer de statut ; « En cours » ne
                se déplace pas ;
    piece       pièce manquante (RG3) : refus expliqué, puis « Mettre en attente (motif : pièce) » ;
    habilitation scénario Habilitation du brief rejoué depuis le planning : avertissement affiché et
                ligne « avertissement habilitation : … » au journal (RG8) ;
    charge      charge et capacité de la semaine = calcul Python, surcharge dite en texte ;
    conflit     statut changé sur un autre poste (fichier modifié) → refus clair ;
    profils     technicien : lecture seule, sa ligne en tête ; demandeur renvoyé à l'accueil ;
    telephone   375 px : liste par jour, aucun défilement horizontal, zones tactiles ≥ 48 px.

Aucun identifiant du jeu de démo écrit en dur (rôles de tests/fixtures/demo-scenarios.json).
Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_planning.py" -v
"""
import csv
import datetime
import io
import time
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo, url_fichier

FERMES = ("Clôturé techniquement", "Clôturé administrativement", "Annulé")

DEBORDEMENT_JS = """(selecteur) => { const e = document.querySelector(selecteur);
    return e ? [e.scrollWidth, e.clientWidth] : null; }"""

PETITES_ZONES_JS = """() => {
  const petites = [];
  for (const el of document.querySelectorAll('#contenu a, #contenu button, #contenu input, #contenu select, #contenu textarea, #contenu summary')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || el.closest('[hidden]') || el.type === 'hidden') continue;
    if (r.height < 47.5) petites.push(el.tagName + ' « ' + (el.textContent || el.value || '').trim().slice(0, 30) + ' » ' + Math.round(r.height) + ' px');
  }
  return petites;
}"""


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def ecrire_csv(dossier, nom, lignes):
    """Réécrit un CSV au format de Prévo (BOM, « ; », CRLF), comme un autre poste ou Excel."""
    tampon = io.StringIO(newline="")
    ecrivain = csv.DictWriter(tampon, fieldnames=list(lignes[0].keys()), delimiter=";", lineterminator="\r\n")
    ecrivain.writeheader()
    ecrivain.writerows(lignes)
    (Path(dossier) / nom).write_bytes(b"\xef\xbb\xbf" + tampon.getvalue().encode("utf-8"))


def ot_sur_disque(dossier, ot_id):
    return next(ot for ot in lire_csv(dossier, "ordres_travail.csv") if ot["id"] == ot_id)


def nombre(valeur):
    texte = (valeur or "").strip().lstrip("'").replace(",", ".")
    try:
        return float(texte) if texte else 0.0
    except ValueError:
        return 0.0


def nombre_fr(valeur):
    """Comme UI.nombreFr sans décimales imposées : jusqu'à 2 décimales, virgule (« 38,5 », « 35 »)."""
    return ("%.2f" % valeur).rstrip("0").rstrip(".").replace(".", ",")


def lundi_de(jour):
    date = datetime.date.fromisoformat(jour[:10])
    return (date - datetime.timedelta(days=date.weekday())).isoformat()


class CasPlanning(CasNavigateur):
    """Un serveur neuf par test (les tests planifient) ; profil responsable par défaut."""

    def setUp(self):
        super().setUp()
        self.scenarios = scenarios_demo()
        self.serveur = ServeurPrevo()
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)

    def ouvrir(self, route, profil="responsable", nom="Responsable", technicien_id="", page=None, contexte=None):
        preregler_profil(contexte or self.contexte, profil, nom, technicien_id)
        if page is None:
            # Fenêtre haute : la grille entière est visible, la carte et la case de dépôt aussi
            # (le glisser-déposer simulé ne fait pas défiler la page pendant le geste).
            page = self.page
            page.set_viewport_size({"width": 1440, "height": 1600})
        page.goto(self.serveur.url + "/" + route)
        attendre_pret(page)
        return page

    def semaine_de(self, ot_id):
        return lundi_de(ot_sur_disque(self.serveur.dossier, ot_id)["date_prevue"])

    def case(self, technicien_id, jour):
        return '.pl-case[data-technicien="%s"][data-date="%s"]' % (technicien_id, jour)

    def carte(self, ot_id):
        return '.pl-ot[data-ot="%s"]' % ot_id

    def attendre_disque(self, condition, delai_s=10):
        """Attend qu'une condition sur le disque devienne vraie (écriture et journal sont asynchrones)."""
        fin = time.time() + delai_s
        while time.time() < fin:
            if condition():
                return True
            time.sleep(0.2)
        return condition()

    def journal_de(self, ot_id):
        return [entree["action"] for entree in lire_csv(self.serveur.dossier, "journal.csv") if entree["id_ligne"] == ot_id]


class TestPlanning(CasPlanning):

    def test_glisser_un_ot_prepare_le_planifie_et_le_journalise(self):
        ot_id = self.scenarios["ot_a_planifier"]
        lundi = self.semaine_de(ot_id)
        jour = (datetime.date.fromisoformat(lundi) + datetime.timedelta(days=2)).isoformat()
        technicien = self.scenarios["technicien_br_valide"]
        page = self.ouvrir("#/planning?semaine=" + lundi)
        source = ".pl-a-planifier " + self.carte(ot_id)
        self.assertEqual(page.get_attribute(source, "draggable"), "true")
        page.drag_and_drop(source, self.case(technicien, jour))
        page.wait_for_selector(self.case(technicien, jour) + " " + self.carte(ot_id))
        self.assertTrue(self.attendre_disque(lambda: ot_sur_disque(self.serveur.dossier, ot_id)["statut"] == "Planifié"))
        ligne = ot_sur_disque(self.serveur.dossier, ot_id)
        self.assertEqual((ligne["technicien_id"], ligne["date_prevue"]), (technicien, jour))
        attendu = "planification : %s le %s (Préparé → Planifié)" % (technicien, jour)
        self.assertTrue(self.attendre_disque(lambda: any(attendu in action for action in self.journal_de(ot_id))),
                        self.journal_de(ot_id))
        self.assertEqual(page.locator(".pl-a-planifier " + self.carte(ot_id)).count(), 0)

    def test_bouton_planifier_donne_le_meme_resultat_sans_glisser(self):
        ot_id = self.scenarios["ot_a_planifier"]
        lundi = self.semaine_de(ot_id)
        jour = (datetime.date.fromisoformat(lundi) + datetime.timedelta(days=3)).isoformat()
        technicien = self.scenarios["technicien_surcharge"]
        page = self.ouvrir("#/planning?semaine=" + lundi)
        page.click(".pl-a-planifier " + self.carte(ot_id) + ' [data-action="planifier"]')
        page.select_option("#pl-technicien", technicien)
        page.fill("#pl-date", jour)
        page.click("dialog .fenetre-actions button:has-text('Planifier')")
        page.wait_for_selector(self.case(technicien, jour) + " " + self.carte(ot_id))
        self.assertTrue(self.attendre_disque(lambda: ot_sur_disque(self.serveur.dossier, ot_id)["statut"] == "Planifié"))
        ligne = ot_sur_disque(self.serveur.dossier, ot_id)
        self.assertEqual((ligne["technicien_id"], ligne["date_prevue"]), (technicien, jour))

    def test_replanifier_un_ot_planifie_et_en_cours_non_deplacable(self):
        en_cours = self.scenarios["ot_statut_en_cours"]
        lundi = self.semaine_de(en_cours)
        page = self.ouvrir("#/planning?semaine=" + lundi)
        self.assertEqual(page.get_attribute(self.carte(en_cours), "draggable"), "false")
        self.assertEqual(page.locator(self.carte(en_cours) + ' [data-action="planifier"]').count(), 0)
        # Un OT « Planifié » de la grille, déplacé au lendemain (ou à la veille) chez le même technicien
        choix = page.evaluate("""() => { const carte = document.querySelector('.pl-grille .pl-ot[data-statut="Planifié"]');
            const caseActuelle = carte.closest('.pl-case');
            return [carte.dataset.ot, caseActuelle.dataset.technicien, caseActuelle.dataset.date]; }""")
        ot_id, technicien, jour = choix
        nouveau = (datetime.date.fromisoformat(jour) + datetime.timedelta(days=1 if jour < (
            datetime.date.fromisoformat(lundi) + datetime.timedelta(days=6)).isoformat() else -1)).isoformat()
        page.drag_and_drop(self.case(technicien, jour) + " " + self.carte(ot_id), self.case(technicien, nouveau))
        page.wait_for_selector(self.case(technicien, nouveau) + " " + self.carte(ot_id))
        self.assertTrue(self.attendre_disque(lambda: ot_sur_disque(self.serveur.dossier, ot_id)["date_prevue"] == nouveau))
        self.assertEqual(ot_sur_disque(self.serveur.dossier, ot_id)["statut"], "Planifié")
        self.assertTrue(self.attendre_disque(lambda: any("replanification : %s le %s" % (technicien, nouveau) in action
                                                         for action in self.journal_de(ot_id))))

    def test_piece_manquante_refusee_puis_mise_en_attente_motif_piece(self):
        ot_id = self.scenarios["ot_a_planifier_piece_manquante"]
        lundi = self.semaine_de(ot_id)
        technicien = self.scenarios["technicien_br_valide"]
        page = self.ouvrir("#/planning?semaine=" + lundi)
        page.drag_and_drop(".pl-a-planifier " + self.carte(ot_id), self.case(technicien, lundi))
        message = page.wait_for_selector("#pl-message .alerte.important")
        self.assertIn("n'a pas été planifié", message.inner_text())
        self.assertIn("Stock insuffisant", message.inner_text())
        self.assertEqual(ot_sur_disque(self.serveur.dossier, ot_id)["statut"], "Préparé")
        page.click('#pl-message [data-action="attente-piece"]')
        motif = page.wait_for_selector("dialog textarea")
        self.assertTrue(motif.input_value().startswith("Pièce : "))
        page.click("dialog .fenetre-actions button:has-text('Valider')")
        self.assertTrue(self.attendre_disque(lambda: ot_sur_disque(self.serveur.dossier, ot_id)["statut"] == "En attente"))
        self.assertTrue(ot_sur_disque(self.serveur.dossier, ot_id)["motif_attente"].startswith("Pièce : "))

    def test_habilitation_avertissement_affiche_et_trace_au_journal(self):
        ot_id = self.scenarios["ot_a_planifier_br"]
        lundi = self.semaine_de(ot_id)
        jour = (datetime.date.fromisoformat(lundi) + datetime.timedelta(days=4)).isoformat()
        technicien = self.scenarios["technicien_br_echue"]
        page = self.ouvrir("#/planning?semaine=" + lundi)
        page.drag_and_drop(".pl-a-planifier " + self.carte(ot_id), self.case(technicien, jour))
        message = page.wait_for_selector("#pl-message .alerte.attention")
        self.assertIn("Avertissement habilitation : %s sans BR valide au %s" % (technicien, jour), message.inner_text())
        self.assertTrue(self.attendre_disque(lambda: ot_sur_disque(self.serveur.dossier, ot_id)["statut"] == "Planifié"))
        attendu = "avertissement habilitation : %s sans BR valide au %s" % (technicien, jour)
        self.assertTrue(self.attendre_disque(lambda: any(attendu in action for action in self.journal_de(ot_id))),
                        self.journal_de(ot_id))

    def test_charge_et_surcharge_egales_au_calcul_python(self):
        lundi = self.scenarios["semaine_surcharge"]
        debut = datetime.date.fromisoformat(lundi)
        jours = [(debut + datetime.timedelta(days=n)).isoformat() for n in range(7)]
        page = self.ouvrir("#/planning?semaine=" + lundi)
        ordres = lire_csv(self.serveur.dossier, "ordres_travail.csv")
        for technicien in lire_csv(self.serveur.dossier, "techniciens.csv"):
            if technicien["actif"].strip() == "0":
                continue
            charge = sum(nombre(ot["temps_prevu_h"]) for ot in ordres if ot["statut"] not in FERMES
                         and ot["technicien_id"] == technicien["id"] and ot["date_prevue"][:10] in jours)
            capacite = nombre(technicien["capacite_h_semaine"])
            texte = page.inner_text('.pl-grille tr[data-technicien="%s"] th' % technicien["id"])
            with self.subTest(technicien=technicien["id"]):
                self.assertIn("%s h / %s h" % (nombre_fr(charge), nombre_fr(capacite)), texte)
                self.assertEqual("surcharge" in texte, charge > capacite)
        self.assertIn("surcharge", page.inner_text('.pl-grille tr[data-technicien="%s"] th' % self.scenarios["technicien_surcharge"]))

    def test_noms_prenom_nom_lignes_par_nom_et_fenetre_planifier(self):
        """Lot 4 (§17.9) : « Prénom Nom » comme ailleurs ; les lignes restent rangées par nom."""
        actifs = sorted((t for t in lire_csv(self.serveur.dossier, "techniciens.csv") if t["actif"].strip() != "0"),
                        key=lambda t: (t["nom"].lower(), t["prenom"].lower()))
        page = self.ouvrir("#/planning?semaine=" + self.scenarios["semaine_surcharge"])
        ids = {t["id"] for t in actifs}
        noms = page.locator(".pl-grille tbody tr[data-technicien]").evaluate_all(
            "(lignes, ids) => lignes.filter((l) => ids.includes(l.dataset.technicien)).map((l) => l.querySelector('th b').textContent)",
            sorted(ids))
        self.assertEqual(noms, ["%s %s" % (t["prenom"], t["nom"]) for t in actifs])
        page.click('[data-action="planifier"]')
        options = page.locator("dialog[open] select option").all_inner_texts()
        self.assertEqual([o.split(" — ")[0] for o in options if " — " in o],
                         ["%s %s" % (t["prenom"], t["nom"]) for t in actifs])

    def test_filtre_technicien_annonce_et_garde_d_une_semaine_a_l_autre(self):
        """?technicien= (§15.5) : une seule ligne, filtre annoncé, gardé par « Semaine suivante » (relecture)."""
        lundi = self.scenarios["semaine_surcharge"]
        technicien = self.scenarios["technicien_surcharge"]
        page = self.ouvrir("#/planning?semaine=%s&technicien=%s" % (lundi, technicien))
        lignes = ".pl-grille tr[data-technicien]"
        self.assertEqual(page.eval_on_selector_all(lignes, "l => l.map(e => e.dataset.technicien)"), [technicien])
        self.assertIn("Voir toute l'équipe", page.inner_text(".pl-filtre"))
        suivant = (datetime.date.fromisoformat(lundi) + datetime.timedelta(days=7)).isoformat()
        page.click(".pl-navigation >> text=Semaine suivante")
        page.wait_for_selector('.pl-ecran[data-lundi="%s"]' % suivant)        # l'écran est réaffiché
        self.assertIn("technicien=" + technicien, page.evaluate("location.hash"))
        self.assertEqual(page.eval_on_selector_all(lignes, "l => l.map(e => e.dataset.technicien)"), [technicien])
        page.click(".pl-filtre a")
        # Attendre le réaffichage lui-même (le hash change avant lui) : toute l'équipe revient.
        page.wait_for_function("document.querySelectorAll(%r).length > 1" % lignes)
        self.assertEqual(page.locator(".pl-filtre").count(), 0)

    def test_grille_sans_defilement_et_pas_plus_etroite_sur_grand_ecran(self):
        """Recette puis relecture : à 1 440 et 1 920 px, la grille tient dans son cadre, et la mise en
        page « À planifier » à droite ne la rend pas plus étroite qu'à 1 440 px."""
        page = self.ouvrir("#/planning?semaine=" + self.scenarios["semaine_surcharge"])
        largeurs = {}
        for largeur in (1440, 1920):
            page.set_viewport_size({"width": largeur, "height": 1200})
            page.reload()
            attendre_pret(page)
            defile, visible, grille = page.evaluate("""() => { const c = document.querySelector('.pl-cadre');
                return [c.scrollWidth, c.clientWidth, document.querySelector('.pl-grille').getBoundingClientRect().width]; }""")
            with self.subTest(largeur=largeur):
                self.assertLessEqual(defile, visible + 1)
            largeurs[largeur] = grille
        self.assertGreaterEqual(largeurs[1920], largeurs[1440] - 1, largeurs)

    def test_conflit_statut_change_sur_un_autre_poste_refus_clair(self):
        self.autoriser_erreur("409")
        ot_id = self.scenarios["ot_a_planifier"]
        lundi = self.semaine_de(ot_id)
        page = self.ouvrir("#/planning?semaine=" + lundi)
        # Un autre poste met l'OT en attente (le fichier change sur le disque).
        lignes = lire_csv(self.serveur.dossier, "ordres_travail.csv")
        for ligne in lignes:
            if ligne["id"] == ot_id:
                ligne["statut"] = "En attente"
                ligne["motif_attente"] = "Attente de l'arrêt de la ligne"
        ecrire_csv(self.serveur.dossier, "ordres_travail.csv", lignes)
        page.drag_and_drop(".pl-a-planifier " + self.carte(ot_id), self.case(self.scenarios["technicien_br_valide"], lundi))
        message = page.wait_for_selector("#pl-message .alerte.important")
        self.assertIn("sur un autre poste", message.inner_text())
        self.assertEqual(ot_sur_disque(self.serveur.dossier, ot_id)["statut"], "En attente")


class TestPlanningProfils(CasPlanning):

    def test_profils_technicien_lecture_seule_sa_ligne_en_tete_demandeur_renvoye(self):
        technicien = self.scenarios["technicien_surcharge"]
        page = self.ouvrir("#/planning?semaine=" + self.scenarios["semaine_surcharge"], "technicien", "Technicien", technicien)
        self.assertEqual(page.get_attribute(".pl-grille tbody tr", "data-technicien"), technicien)
        self.assertEqual(page.locator('.pl-ot[draggable="true"]').count(), 0)
        self.assertEqual(page.locator('[data-action="planifier"]').count(), 0)
        self.assertEqual(page.locator(".pl-case[data-depot]").count(), 0)
        self.assertGreater(page.locator(".pl-grille .pl-ot").count(), 0)

        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        try:
            autre = contexte.new_page()
            self.surveiller(autre)
            self.ouvrir("#/planning", "demandeur", "Paul Martin", page=autre, contexte=contexte)
            autre.wait_for_function("location.hash === '#/accueil'")
            self.assertEqual(autre.locator(".pl-grille").count(), 0)
        finally:
            contexte.close()

    def test_telephone_375_px_liste_par_jour_sans_defilement_et_zones_de_48_px(self):
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 375, "height": 812},
                                               is_mobile=True, has_touch=True)
        try:
            page = contexte.new_page()
            self.surveiller(page)
            self.ouvrir("#/planning?semaine=" + self.scenarios["semaine_surcharge"], page=page, contexte=contexte)
            self.assertEqual(page.locator(".pl-grille").count(), 0)
            self.assertEqual(page.locator(".pl-jour").count(), 7)
            largeur, visible = page.evaluate(DEBORDEMENT_JS, "html")
            self.assertLessEqual(largeur, visible + 1)
            self.assertEqual(page.evaluate(PETITES_ZONES_JS), [])
        finally:
            contexte.close()


class TestPlanningDemo(CasNavigateur):
    """Mode démo (file://, dates décalées) : le glisser-déposer marche aussi sans serveur."""

    def test_glisser_en_mode_demo(self):
        scenarios = scenarios_demo()
        ot_id = scenarios["ot_a_planifier"]
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.set_viewport_size({"width": 1440, "height": 1600})
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        lundi = self.page.evaluate("(id) => Planning.lundiDe(Donnees.trouver('ordres_travail', id).date_prevue)", ot_id)
        self.page.evaluate("(route) => { location.hash = route; }", "#/planning?semaine=" + lundi)
        self.page.wait_for_selector(".pl-a-planifier .pl-ot[data-ot='%s']" % ot_id)
        cible = '.pl-case[data-technicien="%s"][data-date="%s"]' % (scenarios["technicien_br_valide"], lundi)
        self.page.drag_and_drop(".pl-a-planifier .pl-ot[data-ot='%s']" % ot_id, cible)
        self.page.wait_for_selector(cible + " .pl-ot[data-ot='%s']" % ot_id)
        self.assertEqual(self.page.evaluate("(id) => Donnees.trouver('ordres_travail', id).statut", ot_id), "Planifié")


if __name__ == "__main__":
    unittest.main()
