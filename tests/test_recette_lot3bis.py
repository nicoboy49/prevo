"""Recette du lot 3 bis : préventif suggéré, de bout en bout (tâche T61, ARCHITECTURE.md §16 ;
CS53, CS55, CS57, CS59, CS60).

Familles (le nom du test le dit) :
    serveur : serveur.py sur une copie de la démo, horloge du navigateur à la date de référence de la
              démo (comme tests/test_suggestions.py) :
              - parcours du responsable : accueil → compteur → onglet → S1 « Créer la gamme » (gamme
                créée, suggestion traitée, compteur − 1) → S2 « Ignorer… » avec motif (compteur − 1) →
                « Décisions » → fiche de l'équipement sans la carte ignorée ;
              - matrice des profils : onglets, encarts des fiches, compteur d'accueil ;
              - design à 1440 et 375 px : onglets, fiche gamme et fiche équipement avec encart, fiche
                OT avec l'encart des causes fréquentes (détail déplié) ; captures dans
                tests/resultats/recette-lot3bis/ ;
    demo    : index.html en file:// → « Essayer avec les données de démo » (dates décalées à aujourd'hui) :
              compteur = calcul, une suggestion ignorée → compteur − 1 et « Décisions ».

Aucun identifiant du jeu de démo écrit en dur. Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_recette_lot3bis.py" -v
"""
import re
import unittest

from commun import RACINE, attendre_pret, preregler_profil, url_fichier
from test_suggestions import (CARTE, CasEcrans, LIGNE_DECISION, MOTS_INTERDITS, PANNEAU, SCENARIOS, attendre,
                              decisions_au_journal, espaces, lire_csv, minuscule_initiale)

DOSSIER_CAPTURES = RACINE / "tests" / "resultats" / "recette-lot3bis"
LIEN_ACCUEIL = "#/preventif?onglet=suggestions"
INSTRUMENT = "#contenu .accueil-instruments a[href='%s']" % LIEN_ACCUEIL
DEBORDEMENT_JS = "() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]"
# Zones cliquables de moins de 48 px dans #contenu (même contrôle que tests/test_recette_lot3.py).
PETITES_ZONES_JS = """() => {
  const petites = [];
  for (const el of document.querySelectorAll('#contenu a, #contenu button, #contenu input, #contenu select, #contenu textarea, #contenu summary')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || el.closest('[hidden]') || el.type === 'hidden' || el.closest('.visuellement-cache')) continue;
    const cible = (el.type === 'checkbox' || el.type === 'radio') ? (el.closest('label') || el) : el;
    if (cible.getBoundingClientRect().height < 47.5) petites.push(el.tagName + ' « ' + (el.textContent || el.value || '').trim().slice(0, 30) + ' » ' + Math.round(cible.getBoundingClientRect().height) + ' px');
  }
  return petites;
}"""


class CasRecette(CasEcrans):

    def compteur(self, page):
        page.wait_for_selector(INSTRUMENT)
        return int(page.locator(INSTRUMENT + " .chiffre").inner_text())

    def accueil(self, page):
        self.aller(page, "#/accueil")
        page.wait_for_selector(INSTRUMENT)

    def ignorer(self, page, cle, motif):
        page.click(CARTE % cle + " button[data-action='ignorer']")
        page.wait_for_selector("dialog[open] textarea[name=motif]")
        page.fill("dialog[open] textarea[name=motif]", motif)
        page.click("dialog[open] .fenetre-actions .btn-primaire")
        page.wait_for_selector("dialog[open]", state="detached")
        self.attendre_toast_note(page, "^Suggestion ignorée")


class TestRecetteServeur(CasRecette):

    def test_parcours_du_responsable_serveur(self):
        serveur = self.serveur()
        page = self.ouvrir(serveur, "#/accueil")
        ouvertes = page.evaluate("() => Suggestions.ouvertes(Donnees.aujourdhui()).map((s) => s.cle)")
        depart = self.compteur(page)
        self.assertEqual(depart, len(ouvertes))
        self.assertIn(SCENARIOS["suggestion_creer"], ouvertes)
        self.assertIn(SCENARIOS["suggestion_revoir"], ouvertes)

        # Le compteur mène à l'onglet
        page.click(INSTRUMENT)
        page.wait_for_function("location.hash === '%s'" % LIEN_ACCUEIL)
        page.wait_for_selector(PANNEAU + " .sg-carte")
        self.assertEqual(page.eval_on_selector_all(PANNEAU + " .sg-carte", "c => c.map((e) => e.dataset.cle)"), ouvertes)
        self.assertNotRegex(page.inner_text("#contenu"), MOTS_INTERDITS)

        # S1 « Créer la gamme » : formulaire pré-rempli, rien d'écrit avant le clic, puis traitée
        cle = SCENARIOS["suggestion_creer"]
        s = page.evaluate("(cle) => Suggestions.trouver(cle, Donnees.aujourdhui())", cle)
        gammes_avant = (serveur.dossier / "gammes.csv").read_bytes()
        page.click(CARTE % cle + " .sg-actions a")
        page.wait_for_selector("#pv-formulaire-gamme")
        self.assertEqual(page.input_value("#pv-formulaire-gamme [name=libelle]"), "Prévenir : " + minuscule_initiale(s["causeLibelle"]))
        page.wait_for_load_state("networkidle")
        self.assertEqual((serveur.dossier / "gammes.csv").read_bytes(), gammes_avant)
        page.fill("#pv-formulaire-gamme [name=periodicite_jours]", "28")
        page.click("#pv-formulaire-gamme button[type=submit]")
        page.wait_for_function("/^#\\/preventif\\/gamme\\/GAM-\\d+/.test(location.hash)")
        gamme_id = re.search(r"GAM-\d+", page.evaluate("location.hash")).group(0)
        self.assertTrue(attendre(lambda: decisions_au_journal(serveur.dossier, cle)))
        self.assertEqual(decisions_au_journal(serveur.dossier, cle)[-1]["action"],
                         "suggestion %s traitée : gamme %s créée" % (cle, gamme_id))
        self.accueil(page)
        self.assertEqual(self.compteur(page), depart - 1)

        # S2 « Ignorer… » avec motif : journal, carte retirée, compteur − 1
        cle_s2 = SCENARIOS["suggestion_revoir"]
        equipement_s2 = page.evaluate("(cle) => Suggestions.trouver(cle, Donnees.aujourdhui()).equipementId", cle_s2)
        self.onglet_suggestions(page)
        self.ignorer(page, cle_s2, "Garniture changée à chaque visite depuis septembre ; on surveille.")
        self.assertTrue(attendre(lambda: decisions_au_journal(serveur.dossier, cle_s2)))
        ligne = decisions_au_journal(serveur.dossier, cle_s2)[-1]
        self.assertEqual((ligne["table"], ligne["id_ligne"]), ("equipements", equipement_s2))
        self.assertTrue(ligne["action"].startswith("suggestion %s ignorée : Garniture changée" % cle_s2))
        page.wait_for_selector(CARTE % cle_s2, state="detached")
        self.onglet_decisions(page)
        for decidee in (cle, cle_s2):
            self.assertEqual(page.locator(LIGNE_DECISION % decidee).count(), 1, decidee)
        self.accueil(page)
        self.assertEqual(self.compteur(page), depart - 2)

        # Fiche de l'équipement : la suggestion ignorée n'y est plus
        self.aller(page, "#/equipement/" + equipement_s2)
        page.wait_for_selector(".parc-preventif")
        self.assertEqual(page.locator(".sg-encart .sg-carte[data-cle='%s']" % cle_s2).count(), 0)
        # gammes.csv : seule la gamme créée s'est ajoutée (rien d'autre n'a été modifié sans action)
        avant = [l for l in gammes_avant.decode("utf-8-sig").splitlines() if l]
        apres = [l for l in (serveur.dossier / "gammes.csv").read_bytes().decode("utf-8-sig").splitlines() if l]
        self.assertEqual(apres[:len(avant)], avant)
        self.assertEqual([l.split(";")[0].lstrip("'") for l in apres[len(avant):]], [gamme_id])

    def test_profils_onglets_encarts_et_compteur_serveur(self):
        serveur = self.serveur()
        technicien = next(t for t in lire_csv(serveur.dossier, "techniciens.csv") if t["actif"] != "0")
        gamme_s3 = SCENARIOS["suggestion_anomalies"][3:]                      # clé « S3-<gamme> »
        identites = {"demandeur": ("Paul Martin", ""), "technicien": (technicien["prenom"] + " " + technicien["nom"], technicien["id"]),
                     "responsable": ("Responsable", "")}
        for profil, (nom, technicien_id) in identites.items():
            with self.subTest(profil=profil):
                contexte, page = self.nouveau_contexte()
                self.ouvrir(serveur, "#/accueil", profil, nom, technicien_id, contexte=contexte, page=page)
                responsable = profil == "responsable"
                self.assertEqual(page.locator(INSTRUMENT).count(), 1 if responsable else 0)
                for onglet in ("suggestions", "decisions"):
                    self.aller(page, "#/preventif?onglet=" + onglet)
                    if responsable:
                        page.wait_for_selector(".onglet[data-onglet='%s'][aria-selected='true']" % onglet)
                    else:
                        page.wait_for_function("location.hash === '#/accueil'")
                        if profil == "technicien":
                            self.attendre_toast_note(page, "Suggestions de préventif.*n'est pas disponible pour le profil Technicien")
                if profil != "demandeur":
                    # Liste du Préventif : les onglets Suggestions et Décisions n'existent que pour le responsable
                    self.aller(page, "#/preventif")
                    page.wait_for_selector(".pv-onglets .onglet[data-onglet='gammes']")
                    for onglet in ("suggestions", "decisions"):
                        self.assertEqual(page.locator(".pv-onglets .onglet[data-onglet='%s']" % onglet).count(),
                                         1 if responsable else 0)
                    # Fiche gamme : la carte (la check-list est la dernière partie dessinée) puis l'encart
                    self.aller(page, "#/preventif/gamme/" + gamme_s3)
                    page.wait_for_selector(".pv-fiche[data-gamme='%s'] .pv-check-liste h2" % gamme_s3)
                    if responsable:
                        page.wait_for_selector(".sg-encart")
                    self.assertEqual(page.locator(".sg-encart").count(), 1 if responsable else 0)
                equipement = page.evaluate("(g) => { const ligne = Donnees.trouver('gammes', g); return ligne ? ligne.equipement_id : ''; }", gamme_s3)
                if equipement:
                    self.aller(page, "#/equipement/" + equipement)
                    page.wait_for_selector(".parc-complements")         # fiche dessinée (l'encart est posé avant), tous profils
                    if responsable:
                        page.wait_for_selector(".sg-encart")
                    self.assertEqual(page.locator(".sg-encart").count(), 1 if responsable else 0)

    def test_design_serveur_1440_et_375_px(self):
        serveur = self.serveur()
        DOSSIER_CAPTURES.mkdir(parents=True, exist_ok=True)
        gamme_s3 = SCENARIOS["suggestion_anomalies"][3:]
        cle_s1 = SCENARIOS["suggestion_creer"]
        ot_causes = SCENARIOS["ot_fuite_garniture_po02"]
        for largeur, telephone in ((1440, False), (375, True)):
            contexte, page = self.nouveau_contexte(largeur, telephone)
            self.ouvrir(serveur, "#/accueil", contexte=contexte, page=page)
            equipement_s1 = page.evaluate("(cle) => Suggestions.trouver(cle, Donnees.aujourdhui()).equipementId", cle_s1)
            ecrans = {
                "suggestions": ("#/preventif?onglet=suggestions", PANNEAU + " .sg-carte"),
                "decisions": ("#/preventif?onglet=decisions", ".panneau-onglet[data-onglet='decisions'] .suggestions"),
                "fiche-gamme": ("#/preventif/gamme/%s?suggestion=%s" % (gamme_s3, SCENARIOS["suggestion_anomalies"]), ".sg-rappel"),
                "fiche-equipement": ("#/equipement/" + equipement_s1, ".sg-encart .sg-carte"),
                "ot-causes": ("#/ot/" + ot_causes, ".ot-fiche"),
            }
            for nom, (route, attendu) in ecrans.items():
                with self.subTest(largeur=largeur, ecran=nom):
                    self.aller(page, route)
                    page.wait_for_selector(attendu)
                    if nom == "ot-causes":
                        page.click(".onglet[data-onglet='compte-rendu']")
                        details = ".panneau-onglet[data-onglet='compte-rendu'] details.causes-precision"
                        page.wait_for_selector(details)
                        page.click(details + " summary")
                        self.assertTrue(page.evaluate("(s) => document.querySelector(s).open", details))
                    page.wait_for_timeout(500)
                    page.screenshot(path=str(DOSSIER_CAPTURES / ("%s-%d.png" % (nom, largeur))), full_page=True)
                    largeur_page, visible = page.evaluate(DEBORDEMENT_JS)
                    self.assertLessEqual(largeur_page, visible + 1, "défilement horizontal : %s à %d px" % (nom, largeur))
                    self.assertNotRegex(page.inner_text("#contenu"), MOTS_INTERDITS)
                    if telephone:
                        self.assertEqual(page.evaluate(PETITES_ZONES_JS), [], "%s à 375 px" % nom)
            # Le type d'une suggestion n'est jamais dit par la seule couleur : chaque carte porte son badge en texte
            self.aller(page, "#/preventif?onglet=suggestions")
            page.wait_for_selector(PANNEAU + " .sg-carte")
            badges = page.eval_on_selector_all(PANNEAU + " .sg-carte", "c => c.map((e) => [e.dataset.regle, e.querySelector('.sg-type').textContent.trim()])")
            titres = page.evaluate("() => Suggestions.TITRES")
            for regle, badge in badges:
                self.assertEqual(espaces(badge), "%s · %s" % (regle, titres[regle]))


class TestRecetteDemo(CasRecette):

    def test_parcours_demo_compteur_ignorer_et_decisions(self):
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        page = self.page
        depart = self.compteur(page)
        self.assertEqual(depart, page.evaluate("() => Suggestions.ouvertes(Donnees.aujourdhui()).length"))
        self.assertGreater(depart, 0)
        self.onglet_suggestions(page)
        premiere = page.eval_on_selector(PANNEAU + " .sg-carte", "c => c.dataset.cle")
        self.ignorer(page, premiere, "Essai de la recette en mode démo.")
        page.wait_for_selector(CARTE % premiere, state="detached")
        self.onglet_decisions(page)
        self.assertEqual(page.locator(LIGNE_DECISION % premiere).count(), 1)
        self.accueil(page)
        self.assertEqual(self.compteur(page), depart - 1)
        self.assertNotRegex(page.inner_text("#contenu"), MOTS_INTERDITS)


if __name__ == "__main__":
    unittest.main()
