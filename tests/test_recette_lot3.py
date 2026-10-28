"""Recette du lot 3 de bout en bout (tâche T52 ; CS37, CS46, CS47 ; brief §14).

On rejoue les scénarios du lot 3 comme un utilisateur, par l'interface, sans refaire les tests des
modules (règles, écritures : test_regles_indicateurs, test_regles_lot3, test_planning, test_controles,
test_equipe, test_etiquettes, test_indicateurs, test_rapport, test_accueil_lot3). Modes :
    serveur : serveur.py (ServeurPrevo, copie du jeu de démo, dates non décalées), un serveur par test ;
    demo    : index.html en file:// → « Essayer avec les données de démo » (dates décalées par semaines
              entières depuis la date de référence du générateur).
Scénarios (le nom de chaque test contient le mot-clé) :
    calcul_main   scénario du brief « indicateurs identiques à un calcul à la main » : pour les 3
                  équipements du rôle `equipements_calcul_main`, valeurs AFFICHÉES par l'écran
                  Indicateurs (tableau par équipement, 12 mois) = calcul Python indépendant
                  (tests/test_regles_indicateurs.CalculPython), à l'arrondi d'affichage ;
    planning      un OT à planifier glissé sur un technicien sans BR valide : planifié, avertissement
                  d'habilitation affiché ;
    controle      contrôle réalisé avec un rapport joint → le compteur « Contrôles sous 30 j » baisse ;
    habilitation  habilitation renouvelée → le compteur « Habilitations à renouveler » baisse ;
    etiquettes    planche d'un atelier : une étiquette par équipement suivi, repères en clair ;
    rapport       rapport du mois écoulé figé depuis l'accueil, puis rouvert depuis l'onglet ;
    profils       matrice du §15.2 : chaque route nouvelle pour les trois profils ;
    design        captures 1440 et 375 px des nouveaux écrans (tests/resultats/recette-lot3/) : pas de
                  défilement horizontal de la page, zones tactiles ≥ 48 px à 375 px, aucune erreur.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_recette_lot3.py" -v
"""
import csv
import datetime
import io
import math
import time
import unittest
from pathlib import Path

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo, url_fichier
from test_regles_indicateurs import CalculPython, date_reference

DOSSIER_CAPTURES = RACINE / "tests" / "resultats" / "recette-lot3"

DEBORDEMENT_JS = """() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]"""
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

# Matrice du §15.2 : route → profils autorisés.
MATRICE = {
    "#/planning": ("technicien", "responsable"),
    "#/controles": ("technicien", "responsable"),
    "#/controles/nouveau": ("responsable",),
    "#/indicateurs": ("responsable",),
    "#/indicateurs?onglet=rapports": ("responsable",),
    "#/equipe": ("technicien", "responsable"),
    "#/equipe/nouveau": ("responsable",),
    "#/parc/etiquettes": ("responsable",),
    "#/parametres": ("responsable",),
}


def lire_csv(dossier, nom):
    return list(csv.DictReader(io.StringIO((Path(dossier) / nom).read_text(encoding="utf-8-sig")), delimiter=";"))


def espaces(texte):
    return " ".join(texte.replace(" ", " ").replace(" ", " ").split())


def arrondi(valeur, decimales):
    facteur = 10 ** decimales
    return math.floor(valeur * facteur + 0.5) / facteur


def nombre_fr(valeur, decimales):
    """Comme UI.nombreFr(v, d) : milliers séparés par une espace, virgule décimale."""
    texte = "{:,.{}f}".format(arrondi(valeur, decimales), decimales)
    return texte.replace(",", " ").replace(".", ",")


class CasRecette(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.scenarios = scenarios_demo()

    def serveur(self):
        serveur = ServeurPrevo()
        serveur.demarrer()
        self.addCleanup(serveur.arreter)
        return serveur

    def ouvrir_serveur(self, serveur, route="#/accueil", profil="responsable", nom="Responsable", technicien_id="", page=None, contexte=None):
        preregler_profil(contexte or self.contexte, profil, nom, technicien_id)
        page = page or self.page
        page.goto(serveur.url + "/" + route)
        attendre_pret(page)
        return page

    def ouvrir_demo(self, profil="responsable", nom="Responsable", technicien_id=""):
        preregler_profil(self.contexte, profil, nom, technicien_id)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        return self.page

    def aller(self, route, page=None):
        (page or self.page).evaluate("(route) => { location.hash = route; }", route)

    def attendre(self, condition, delai_s=15):
        fin = time.time() + delai_s
        while time.time() < fin:
            if condition():
                return True
            time.sleep(0.2)
        return condition()

    def cellules_equipement(self, page, equipement_id):
        """Textes des cellules de la ligne d'un équipement dans le tableau de l'écran Indicateurs,
        par libellé de colonne."""
        return page.evaluate("""(id) => {
            const lien = document.querySelector('#contenu table a[href="#/equipement/' + id + '"]');
            if (!lien) return null;
            const table = lien.closest('table');
            const entetes = Array.from(table.querySelectorAll('thead th')).map((th) => th.textContent.trim());
            const cellules = Array.from(lien.closest('tr').cells).map((td) => td.textContent.trim());
            return Object.fromEntries(entetes.map((libelle, rang) => [libelle, cellules[rang]])); }""", equipement_id)

    def verifier_calcul_main(self, page, aujourdhui_donnees):
        """Valeurs affichées (tableau par équipement, 12 mois) = calcul Python indépendant."""
        calcul = CalculPython(aujourdhui_donnees)
        self.aller("#/indicateurs?periode=12-mois", page)
        page.wait_for_selector("#contenu table a[href^='#/equipement/']")
        for equipement_id in self.scenarios["equipements_calcul_main"]:
            attendu = calcul.equipement(equipement_id)
            cellules = self.cellules_equipement(page, equipement_id)
            self.assertIsNotNone(cellules, equipement_id)
            with self.subTest(equipement=equipement_id):
                self.assertEqual(cellules["Pannes"], str(attendu["pannes"]))
                self.assertEqual(espaces(cellules["Arrêt (h)"]), nombre_fr(attendu["dureeArret"], 1))
                self.assertEqual(espaces(cellules["MTBF (h)"]), nombre_fr(attendu["mtbf"], 1))
                self.assertEqual(espaces(cellules["MTTR (h)"]), nombre_fr(attendu["mttr"], 1))
                self.assertEqual(espaces(cellules["Disponibilité"]), nombre_fr(attendu["disponibilite"] * 100, 1) + " %")
                self.assertEqual(espaces(cellules["Coût"]), nombre_fr(attendu["cout"], 2) + " €")


class TestRecetteServeur(CasRecette):

    def test_calcul_main_serveur(self):
        serveur = self.serveur()
        page = self.ouvrir_serveur(serveur)
        aujourdhui = datetime.date.fromisoformat(page.evaluate("Donnees.aujourdhui()"))
        self.verifier_calcul_main(page, aujourdhui)

    def test_planning_serveur_habilitation_avertie(self):
        serveur = self.serveur()
        ot_id = self.scenarios["ot_a_planifier_br"]
        ot = next(o for o in lire_csv(serveur.dossier, "ordres_travail.csv") if o["id"] == ot_id)
        date = datetime.date.fromisoformat(ot["date_prevue"][:10])
        lundi = (date - datetime.timedelta(days=date.weekday())).isoformat()
        page = self.ouvrir_serveur(serveur, "#/planning?semaine=" + lundi)
        page.set_viewport_size({"width": 1440, "height": 1600})
        technicien = self.scenarios["technicien_br_echue"]
        page.drag_and_drop(".pl-a-planifier .pl-ot[data-ot='%s']" % ot_id,
                           '.pl-case[data-technicien="%s"][data-date="%s"]' % (technicien, lundi))
        message = page.wait_for_selector("#pl-message .alerte.attention")
        self.assertIn("Avertissement habilitation", message.inner_text())
        self.assertTrue(self.attendre(lambda: next(o for o in lire_csv(serveur.dossier, "ordres_travail.csv")
                                                   if o["id"] == ot_id)["statut"] == "Planifié"))

    def compteur(self, page, lien):
        self.aller("#/accueil", page)
        page.wait_for_selector("#contenu a[href='%s'] .chiffre" % lien)
        return int(page.inner_text("#contenu a[href='%s'] .chiffre" % lien))

    def test_controle_serveur_realise_avec_rapport_puis_compteur_d_accueil(self):
        serveur = self.serveur()
        page = self.ouvrir_serveur(serveur)
        avant = self.compteur(page, "#/controles?filtre=30j")
        controle = self.scenarios["controle_en_retard"]
        self.aller("#/controles/" + controle, page)
        page.wait_for_selector(".controles-fiche .controles-statuts[data-controle='%s']" % controle)
        page.click("#controle-realise")
        page.wait_for_selector("dialog [name=date]")
        page.set_input_files("dialog input[type=file]", files=[{"name": "rapport-vgp.pdf", "mimeType": "application/pdf",
                                                                 "buffer": b"%PDF-1.4\n% rapport de recette\n"}])
        page.click("dialog .fenetre-actions .btn-primaire")
        self.assertTrue(self.attendre(lambda: next(c for c in lire_csv(serveur.dossier, "controles_reglementaires.csv")
                                                   if c["id"] == controle)["rapport"] != ""))
        ligne = next(c for c in lire_csv(serveur.dossier, "controles_reglementaires.csv") if c["id"] == controle)
        self.assertTrue((Path(serveur.dossier) / "documents" / ligne["rapport"]).is_file())
        self.assertEqual(ligne["derniere_date"], page.evaluate("Donnees.aujourdhui()"))
        self.assertEqual(self.compteur(page, "#/controles?filtre=30j"), avant - 1)

    def test_habilitation_serveur_renouvelee_puis_compteur_d_accueil(self):
        serveur = self.serveur()
        page = self.ouvrir_serveur(serveur)
        avant = self.compteur(page, "#/equipe?filtre=a-renouveler")
        technicien = self.scenarios["technicien_br_echue"]
        habilitation = page.evaluate("""(t) => Equipe.habilitationsQuiComptent(t)
            .find((h) => h.intitule.trim().toUpperCase() === 'BR').id""", technicien)
        self.aller("#/equipe/" + technicien, page)
        page.wait_for_selector(".equipe-fiche[data-technicien='%s']" % technicien)
        page.click("button[data-action='renouveler'][data-habilitation='%s']" % habilitation)
        page.wait_for_selector("dialog [name=date_echeance]")
        aujourdhui = datetime.date.fromisoformat(page.evaluate("Donnees.aujourdhui()"))
        page.fill("dialog [name=date_echeance]", (aujourdhui + datetime.timedelta(days=3 * 365)).isoformat())
        page.click("dialog .fenetre-actions .btn-primaire")
        self.assertTrue(self.attendre(lambda: sum(1 for h in lire_csv(serveur.dossier, "habilitations.csv")
                                                  if h["technicien_id"] == technicien and h["intitule"] == "BR") == 2))
        self.assertEqual(self.compteur(page, "#/equipe?filtre=a-renouveler"), avant - 1)

    def test_etiquettes_serveur_planche_d_un_atelier(self):
        serveur = self.serveur()
        localisations = lire_csv(serveur.dossier, "localisations.csv")
        atelier = next(l for l in localisations if l["type"] == "atelier")
        descendants = {atelier["id"]}
        change = True
        while change:
            change = False
            for l in localisations:
                if l["parent_id"] in descendants and l["id"] not in descendants:
                    descendants.add(l["id"])
                    change = True
        attendus = sorted(e["repere"].lstrip("'") for e in lire_csv(serveur.dossier, "equipements.csv")
                          if e["localisation_id"] in descendants and e["actif"].strip() != "0" and e["statut"] != "rebut")
        page = self.ouvrir_serveur(serveur, "#/parc/etiquettes?localisation=" + atelier["id"])
        page.wait_for_selector(".etiquette, [class*='etiquette']")
        reperes = page.evaluate("""() => Array.from(document.querySelectorAll('#etiquettes-apercu .etiquette-repere, #etiquettes-apercu [class*="repere"]'))
            .map((e) => e.textContent.trim())""")
        self.assertEqual(sorted(reperes), attendus)

    def test_rapport_serveur_fige_puis_rouvert(self):
        serveur = self.serveur()
        page = self.ouvrir_serveur(serveur)
        page.click('#bandeau-rapport [data-action="figer-rapport"]')
        documents = Path(serveur.dossier) / "documents"
        # Nom imposé par le serveur : « AAAAMMJJ-HHMMSS-rapport-mensuel-… » (audit F4, T159)
        self.assertTrue(self.attendre(lambda: documents.is_dir() and any(documents.glob("*-rapport-mensuel-*.html"))))
        nom = next(documents.glob("*-rapport-mensuel-*.html")).name
        self.aller("#/indicateurs?onglet=rapports")
        page.wait_for_selector('.rapports-liste tr[data-nom="%s"]' % nom)
        with self.contexte.expect_page() as attente:
            page.click('.rapports-liste [data-action="ouvrir"][data-nom="%s"]' % nom)
        rapport = attente.value
        self.surveiller(rapport)
        rapport.wait_for_load_state()
        self.assertIn("Rapport mensuel de maintenance", rapport.inner_text("body"))

    def test_profils_matrice_des_routes_serveur(self):
        serveur = self.serveur()
        technicien = next(t for t in lire_csv(serveur.dossier, "techniciens.csv") if t["actif"].strip() != "0")
        identites = {"demandeur": ("Paul Martin", ""), "technicien": (technicien["prenom"] + " " + technicien["nom"], technicien["id"]),
                     "responsable": ("Responsable", "")}
        for profil, (nom, technicien_id) in identites.items():
            contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
            try:
                page = contexte.new_page()
                self.surveiller(page)
                self.ouvrir_serveur(serveur, "#/accueil", profil, nom, technicien_id, page=page, contexte=contexte)
                for route, autorises in MATRICE.items():
                    with self.subTest(profil=profil, route=route):
                        page.evaluate("(r) => { location.hash = r; }", route)
                        base = route.split("?")[0]
                        if profil in autorises:
                            # L'écran peut compléter l'adresse (ex. période des Indicateurs) : on compare le chemin.
                            page.wait_for_function("(b) => location.hash.split('?')[0] === b && document.documentElement.dataset.etat === 'pret'", arg=base)
                            page.wait_for_timeout(150)
                            self.assertEqual(page.evaluate("location.hash.split('?')[0]"), base)
                        else:
                            page.wait_for_function("location.hash === '#/accueil'")
            finally:
                contexte.close()

    def test_design_serveur_1440_et_375_px(self):
        serveur = self.serveur()
        DOSSIER_CAPTURES.mkdir(parents=True, exist_ok=True)
        ecrans = {"planning": "#/planning?semaine=" + self.scenarios["semaine_surcharge"], "controles": "#/controles",
                  "equipe": "#/equipe", "indicateurs": "#/indicateurs", "rapports": "#/indicateurs?onglet=rapports",
                  "etiquettes": "#/parc/etiquettes", "accueil": "#/accueil"}
        for largeur, hauteur, mobile in ((1440, 900, False), (375, 812, True)):
            contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": largeur, "height": hauteur},
                                                   is_mobile=mobile, has_touch=mobile)
            try:
                page = contexte.new_page()
                self.surveiller(page)
                self.ouvrir_serveur(serveur, "#/accueil", page=page, contexte=contexte)
                for nom, route in ecrans.items():
                    with self.subTest(largeur=largeur, ecran=nom):
                        page.evaluate("(r) => { location.hash = r; }", route)
                        page.wait_for_function("(b) => location.hash.split('?')[0] === b && document.documentElement.dataset.etat === 'pret'",
                                               arg=route.split("?")[0])
                        page.wait_for_timeout(600)
                        page.screenshot(path=str(DOSSIER_CAPTURES / ("%s-%d.png" % (nom, largeur))), full_page=True)
                        largeur_page, visible = page.evaluate(DEBORDEMENT_JS)
                        self.assertLessEqual(largeur_page, visible + 1, "défilement horizontal : %s à %d px" % (nom, largeur))
                        if mobile:
                            self.assertEqual(page.evaluate(PETITES_ZONES_JS), [], "%s à 375 px" % nom)
            finally:
                contexte.close()


class TestRecetteDemo(CasRecette):

    def test_calcul_main_demo(self):
        page = self.ouvrir_demo()
        aujourdhui = datetime.date.fromisoformat(page.evaluate("Donnees.aujourdhui()"))
        reference = datetime.date.fromisoformat(date_reference())
        # La démo décale les dates d'un nombre de semaines entières : le calcul Python, qui lit les
        # CSV non décalés, prend la date du jour reculée d'autant.
        semaines = (aujourdhui - reference).days // 7
        self.verifier_calcul_main(page, aujourdhui - datetime.timedelta(days=7 * semaines))

    def test_rapport_demo_fige_et_telechargeable(self):
        page = self.ouvrir_demo()
        page.click('#bandeau-rapport [data-action="figer-rapport"]')
        page.wait_for_function("App.adaptateur.documentsEnMemoire().some((d) => /^rapport-mensuel-/.test(d.nom))")
        self.aller("#/indicateurs?onglet=rapports")
        page.wait_for_selector('.rapports-liste [data-action="telecharger"]')
        with page.expect_download() as attente:
            page.click('.rapports-liste [data-action="telecharger"]')
        self.assertTrue(attente.value.suggested_filename.startswith("rapport-mensuel-"))


if __name__ == "__main__":
    unittest.main()
