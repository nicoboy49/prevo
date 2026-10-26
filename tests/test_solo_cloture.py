"""Tests de la clôture en une étape (tâche T174, ARCHITECTURE.md §22.11, CDC D132, CS132).

Réglage cloture_une_etape (0/1) de parametres.csv, posé à 1 par « Passer en mode Solo », réglable par le
responsable dans Paramètres (section « Ordres de travail »). Mode démo (file://), profil Responsable :
    - avec le réglage, « Clore » sur un OT « En cours » ouvre UNE fenêtre (champs de la clôture
      technique) et fait la clôture technique puis administrative : deux dates égales, deux lignes
      de journal (technique puis administrative), OT dans la file du wiki ;
    - les indicateurs de l'OT (MTTR, disponibilité, durée d'arrêt, coût : fonctions pures
      d'Indicateurs et Ordres.cout) sont ÉGAUX à ceux d'une clôture en deux étapes du même OT, faite
      avec les mêmes saisies sur une seconde copie de la même démo ;
    - les règles de la clôture technique s'appliquent (compte rendu « RAS » refusé, rien d'écrit) ;
    - sans le réglage, « Clore » n'apparaît pas ; le réglage se coupe dans Paramètres ;
    - « Passer en mode Solo » pose cloture_une_etape = 1.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_solo_cloture.py" -v
"""
import json
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, scenarios_demo, url_fichier

OT = scenarios_demo()["ot_statut_en_cours"]          # correctif « En cours »

COMPTE_RENDU = "Roulement du moteur grippé, remplacé puis essai à vide concluant."
ASTUCE = "Prévoir l'extracteur de roulement dans la caisse."

# Indicateurs de l'OT et de son équipement, calculés par les fonctions pures (Indicateurs, Ordres.cout).
SCRIPT_INDICATEURS = """(otId) => {
  const ot = Donnees.trouver('ordres_travail', otId);
  const periode = Indicateurs.periode('12-mois');
  const ind = Indicateurs.parEquipement(ot.equipement_id, periode);
  const garder = (r) => ({ valeur: r.valeur, raison: r.raison, effectif: r.effectif, ots: r.ots.slice().sort() });
  const cout = Ordres.cout(ot);
  return {
    mttr: garder(ind.mttr), disponibilite: garder(ind.disponibilite), mtbf: garder(ind.mtbf),
    dureeArret: garder(ind.dureeArret), pannes: garder(ind.pannes), cout: garder(ind.cout),
    coutOt: { heures: cout.heures, pieces: cout.pieces, soustraitance: cout.soustraitance, total: cout.total },
    statut: ot.statut, date_fin: ot.date_fin, duree_arret_h: ot.duree_arret_h,
  };
}"""


class TestClotureUneEtape(CasNavigateur):

    def ouvrir_demo(self, page=None, contexte=None):
        preregler_profil(contexte or self.contexte, "responsable")
        page = page or self.page
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        return page

    def aller(self, page, route, selecteur):
        page.evaluate("location.hash = %r" % route)
        page.wait_for_selector(selecteur)

    def regler_dans_parametres(self, page, actif):
        """Coche ou décoche « Clôture en une étape » dans Paramètres et enregistre."""
        self.aller(page, "#/parametres", "#form-parametres [name='cloture_une_etape']")
        case = page.locator("#form-parametres [name='cloture_une_etape']")
        if case.is_checked() != actif:
            case.click()
        page.click("#form-parametres button[type=submit]")
        attendu = "1" if actif else "0"
        page.wait_for_function("(v) => Donnees.parametre('cloture_une_etape', '') === v", arg=attendu)

    def saisies(self, page):
        """Mêmes saisies pour les deux copies : date de fin passée, codes, article en stock."""
        return page.evaluate("""(otId) => {
          const ot = Donnees.trouver('ordres_travail', otId);
          const code = (famille) => Donnees.lignes('codes_defaillance').find((c) => c.famille === famille && c.code).code;
          const article = Donnees.lignes('articles').find((a) => a.actif !== '0' && Donnees.stockArticle(a.id) >= 2);
          const technicien = ot.technicien_id || Donnees.lignes('techniciens').find((t) => t.actif !== '0').id;
          // Le jeu de démo date le début de l'OT du jour (heure fixe) : début et fin passés, quelle que soit l'heure.
          const heure = (decalage) => { const d = new Date(Date.now() - decalage * 3600000);
            const deux = (n) => String(n).padStart(2, '0');
            return d.getFullYear() + '-' + deux(d.getMonth() + 1) + '-' + deux(d.getDate()) + ' ' + deux(d.getHours()) + ':' + deux(d.getMinutes()); };
          return { date_debut: heure(5), date_fin: heure(1), symptome_code: code('symptôme'),
            cause_code: code('cause'), remede_code: code('remède'), article_id: article.id, technicien_id: technicien };
        }""", OT)

    def poser_debut(self, page, s):
        """Même date de début sur chaque copie (écriture habituelle d'un champ de l'OT)."""
        page.evaluate("([otId, debut]) => Ordres.interne.modifierOt(otId, { date_debut: debut }, 'début')", [OT, s["date_debut"]])

    def remplir_fenetre_clore(self, page, s, compte_rendu=COMPTE_RENDU):
        page.click("#ot-clore")
        page.wait_for_selector("dialog [name='compte_rendu']", state="visible")
        self.assertEqual(page.locator("dialog").count(), 1)
        page.fill("dialog [name='date_fin']", s["date_fin"].replace(" ", "T"))
        page.check("dialog [name='arret_production']")
        page.fill("dialog [name='duree_arret_h']", "1,5")
        page.fill("dialog [name='heures']", "2,5")
        page.select_option("dialog [name='technicien_id']", s["technicien_id"])
        page.select_option("dialog [name='article_id']", s["article_id"])
        page.fill("dialog [name='quantite']", "2")
        page.select_option("dialog [name='symptome_code']", s["symptome_code"])
        page.select_option("dialog [name='cause_code']", s["cause_code"])
        page.select_option("dialog [name='remede_code']", s["remede_code"])
        page.fill("dialog [name='compte_rendu']", compte_rendu)
        page.fill("dialog [name='astuce']", ASTUCE)
        page.check("dialog [name='remise_service']")
        page.click("dialog .fenetre-actions .btn-primaire")

    def cloturer_en_deux_etapes(self, page, s):
        """Même OT, mêmes saisies, par les écritures habituelles : saisies, temps, pièce, puis deux changerStatut."""
        page.evaluate("""async ([otId, s, compteRendu, astuce]) => {
          await Ordres.interne.modifierOt(otId, { date_fin: s.date_fin, arret_production: '1', duree_arret_h: '1.5',
            symptome_code: s.symptome_code, cause_code: s.cause_code, remede_code: s.remede_code,
            compte_rendu: compteRendu, astuce: astuce, remise_service: '1' }, 'compte rendu');
          await Ordres.interne.modifierLieeAOt(otId, 'ot_temps', (lignes, outils) => {
            lignes.push({ id: outils.nouvelId(lignes), ot_id: otId, technicien_id: s.technicien_id,
              date: s.date_fin.slice(0, 10), heures: '2.5' });
          }, { action: 'temps passé sur ' + otId });
          await Magasin.sortir(otId, s.article_id, 2, '');
          await Ordres.changerStatut(otId, 'En cours', 'Clôturé techniquement');
          await Ordres.changerStatut(otId, 'Clôturé techniquement', 'Clôturé administrativement');
        }""", [OT, s, COMPTE_RENDU, ASTUCE])

    def lignes_journal(self, page):
        return page.evaluate("""async (otId) => {
          await Donnees.rechargerTable('journal');
          return Donnees.lignes('journal').filter((l) => l.table === 'ordres_travail' && l.id_ligne === otId
            && /→ Clôturé/.test(l.action)).map((l) => l.action);
        }""", OT)

    def file_wiki(self, page):
        return page.evaluate("""async (otId) => {
          await Donnees.rechargerTable('wiki_journal');
          return Donnees.lignes('wiki_journal').filter((l) => l.nature === 'ingestion' && l.ot_id === otId)
            .map((l) => l.statut);
        }""", OT)

    # ------------------------------------------------------------------------------------------------

    def test_sans_reglage_pas_de_bouton_clore(self):
        page = self.ouvrir_demo()
        self.assertEqual(page.evaluate("Donnees.parametre('cloture_une_etape', '0')"), "0")
        self.assertFalse(page.evaluate("Ordres.clotureUneEtape()"))
        self.aller(page, "#/ot/" + OT, ".ot-actions")
        self.assertEqual(page.locator("#ot-clore").count(), 0)
        self.assertEqual(page.locator(".ot-actions [data-cible='Clôturé techniquement']").count(), 1)

    def test_clore_deux_dates_deux_lignes_file_du_wiki_et_indicateurs_egaux(self):
        page = self.ouvrir_demo()
        self.regler_dans_parametres(page, True)
        s = self.saisies(page)
        self.poser_debut(page, s)
        self.aller(page, "#/ot/" + OT, "#ot-clore")
        self.remplir_fenetre_clore(page, s)
        page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé administrativement'", arg=OT)
        page.wait_for_selector("dialog", state="detached")
        ot = page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", OT)
        self.assertTrue(ot["date_cloture_tech"])
        self.assertEqual(ot["date_cloture_tech"], ot["date_cloture_admin"])
        self.assertEqual(ot["compte_rendu"], COMPTE_RENDU)
        self.assertEqual(ot["astuce"], ASTUCE)
        actions = self.lignes_journal(page)
        self.assertEqual(len(actions), 2, actions)
        self.assertTrue(actions[0].endswith("statut En cours → Clôturé techniquement"), actions)
        self.assertTrue(actions[1].endswith("statut Clôturé techniquement → Clôturé administrativement"), actions)
        self.assertEqual(self.file_wiki(page), ["en file"])
        self.assertEqual(page.locator("#ot-clore").count(), 0)          # OT verrouillé : plus de « Clore »
        en_une = page.evaluate(SCRIPT_INDICATEURS, OT)

        # Seconde copie de la même démo : clôture en deux étapes, mêmes saisies.
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        try:
            autre = contexte.new_page()
            self.surveiller(autre)
            self.ouvrir_demo(autre, contexte)
            self.poser_debut(autre, s)
            self.cloturer_en_deux_etapes(autre, s)
            en_deux = autre.evaluate(SCRIPT_INDICATEURS, OT)
            self.assertEqual(self.file_wiki(autre), ["en file"])
        finally:
            contexte.close()
        self.assertEqual(en_une["statut"], "Clôturé administrativement")
        self.assertIn(OT, en_une["cout"]["ots"])
        self.assertIn(OT, en_une["pannes"]["ots"])                     # l'OT compte dans MTTR et disponibilité
        self.assertIsNotNone(en_une["mttr"]["valeur"])
        self.assertGreater(en_une["coutOt"]["pieces"], 0)
        self.assertEqual(json.dumps(en_une, sort_keys=True), json.dumps(en_deux, sort_keys=True))

    def test_regles_de_la_cloture_technique_appliquees(self):
        page = self.ouvrir_demo()
        self.regler_dans_parametres(page, True)
        s = self.saisies(page)
        self.poser_debut(page, s)
        avant = page.evaluate("(id) => JSON.stringify(Donnees.trouver('ordres_travail', id))", OT)
        temps_avant = page.evaluate("(id) => Donnees.lignes('ot_temps').filter((l) => l.ot_id === id).length", OT)
        self.aller(page, "#/ot/" + OT, "#ot-clore")
        self.remplir_fenetre_clore(page, s, compte_rendu="RAS")
        page.wait_for_selector("dialog .erreur-champ[role=alert]:not([hidden])")
        self.assertIn("RAS", page.text_content("dialog .erreur-champ[role=alert]"))
        self.assertEqual(page.evaluate("(id) => JSON.stringify(Donnees.trouver('ordres_travail', id))", OT), avant)
        self.assertEqual(page.evaluate("(id) => Donnees.lignes('ot_temps').filter((l) => l.ot_id === id).length", OT), temps_avant)
        page.click("dialog .fenetre-actions .btn-fantome")
        page.wait_for_selector("dialog", state="detached")
        self.assertEqual(self.file_wiki(page), [])

    def test_desactivable_dans_parametres(self):
        page = self.ouvrir_demo()
        self.regler_dans_parametres(page, True)
        self.aller(page, "#/ot/" + OT, "#ot-clore")
        self.regler_dans_parametres(page, False)
        self.aller(page, "#/ot/" + OT, ".ot-actions")
        self.assertEqual(page.locator("#ot-clore").count(), 0)

    def test_passer_en_solo_pose_le_reglage(self):
        page = self.ouvrir_demo()
        self.aller(page, "#/parametres", "#btn-passer-solo")
        page.click("#btn-passer-solo")
        page.wait_for_selector("dialog [name='prenom']", state="visible")
        page.fill("dialog [name='prenom']", "Camille")
        page.fill("dialog [name='nom']", "Soliste")
        page.click("dialog .fenetre-actions .btn-primaire")
        page.wait_for_selector("#btn-quitter-solo")
        self.assertEqual(page.evaluate("Donnees.parametre('cloture_une_etape', '0')"), "1")
        page.click("#btn-quitter-solo")
        page.wait_for_selector("#btn-passer-solo")
        self.assertEqual(page.evaluate("Donnees.parametre('cloture_une_etape', '0')"), "1")   # laissé tel quel


if __name__ == "__main__":
    unittest.main()
