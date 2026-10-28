"""Tests de l'application : index.html, js/app.js, À propos, modules d'attente (ARCHITECTURE.md §8).

Trois familles (le nom du test le dit) :
    fichier  : index.html ouvert en file:// (écran de démarrage, démo, CSV déposés, export ZIP) ;
    serveur  : serveur.py (ServeurPrevo) : détection, base vide, profils, menus, routes,
               changements faits sur un autre poste ;
    dossier  : dossier simulé (ServeurStatique + OPFS) : choix, base vide, reprise, verrou.
Plus la mise en page : 360 px (téléphone) et 1440 px (menu latéral repliable).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_app.py" -v
"""
import csv
import io
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from commun import (CasNavigateur, RACINE, ServeurPrevo, ServeurStatique, attendre_pret,
                    installer_dossier_simule, preregler_profil, url_fichier)

DOSSIER_DEMO = RACINE / "donnees" / "demo"
CREDIT = "Développé par Claude (Anthropic) à la demande de Nicolas Briand — SELECTIS"
BOM = b"\xef\xbb\xbf"
NOM_DOSSIER_SIMULE = "donnees-test"

# Chromium inscrit « Failed to load resource » en console.error pour toute réponse HTTP >= 400.
# On n'autorise que les 404 attendus, précisément :
ERREUR_PING_ABSENT = re.compile(r"status of 404.*/api/ping")      # serveur statique : pas de /api/ping
ERREUR_CSV_ABSENT = re.compile(r"status of 404.*/api/csv/")       # base vide : les 24 CSV manquent

# Une ligne ajoutée « par un autre poste » dans equipements.csv (16 colonnes, format du fichier).
LIGNE_AJOUTEE = "EQ-0999;'ZZ-99;Machine ajoutée par le test;LOC-0002;;;;;;B;en service;;;;;1\r\n"

# Enregistre chaque valeur prise par <html data-etat> (pour vérifier les écrans traversés).
SUIVI_ETATS_JS = """
window.__etats = [];
new MutationObserver(() => {
  const etat = document.documentElement && document.documentElement.dataset.etat;
  if (etat && window.__etats[window.__etats.length - 1] !== etat) window.__etats.push(etat);
}).observe(document, { subtree: true, attributes: true, attributeFilter: ['data-etat'] });
"""


def noms_tables_demo():
    """Noms des 24 fichiers CSV du jeu de démo (equipements.csv…)."""
    return sorted(chemin.name for chemin in DOSSIER_DEMO.glob("*.csv"))


def compter_lignes_csv(chemin):
    """Nombre de lignes de données d'un CSV (champs multilignes entre guillemets compris)."""
    texte = Path(chemin).read_text(encoding="utf-8-sig")
    return len([ligne for ligne in csv.reader(io.StringIO(texte), delimiter=";") if any(ligne)]) - 1


def ajouter_ligne_equipement(dossier):
    """Ajoute LIGNE_AJOUTEE à la fin de equipements.csv sur le disque (comme un autre poste)."""
    chemin = Path(dossier) / "equipements.csv"
    octets = chemin.read_bytes()
    if not octets.endswith(b"\n"):
        octets += b"\r\n"
    chemin.write_bytes(octets + LIGNE_AJOUTEE.encode("utf-8"))


class CasApp(CasNavigateur):
    """Outils communs : attendre un état, choisir un profil, lire le menu."""

    def attendre_etat(self, etat, page=None, delai_ms=15000):
        page = page or self.page
        page.wait_for_function("document.documentElement.dataset.etat === %r" % etat, timeout=delai_ms)

    def choisir_responsable(self, page=None):
        page = page or self.page
        self.attendre_etat("profil", page)
        page.click("#profil-responsable")
        attendre_pret(page)

    def texte(self, selecteur, page=None):
        return (page or self.page).inner_text(selecteur)

    def texte_menu(self, page=None):
        return self.texte("#menu", page)

    def sans_defilement_horizontal(self, page=None):
        page = page or self.page
        largeurs = page.evaluate(
            "[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal : %r" % (largeurs,))


# ---------------------------------------------------------------------------
# file:// : écran de démarrage, démo, CSV déposés
# ---------------------------------------------------------------------------

class TestFichier(CasApp):

    def test_fichier_demarrage_demo_profil_export_zip_et_changement_de_profil(self):
        page = self.page
        page.goto(url_fichier("index.html"))
        self.attendre_etat("demarrage")
        # Les trois options : dossier, démo, dépôt de CSV (pas de dossier précédent mémorisé)
        self.assertTrue(page.is_visible("#btn-dossier"))
        self.assertTrue(page.is_visible("#btn-demo"))
        self.assertTrue(page.is_visible("#zone-depot"))
        self.assertFalse(page.is_visible("#btn-reprendre"))
        self.assertIn("Choisir le dossier de données", self.texte("#btn-dossier"))
        self.assertIn("Essayer avec les données de démo", self.texte("#btn-demo"))

        page.click("#btn-demo")
        self.choisir_responsable()
        self.assertEqual(page.evaluate("App.mode"), "demo")
        self.assertEqual(page.evaluate("location.hash"), "#/accueil")
        # Accueil du responsable (T90) : la mention démo et « Exporter en ZIP » sont dans son en-tête ;
        # le bandeau démo de la coque reprend sa place sur les autres écrans.
        self.assertTrue(page.is_visible("#accueil-demo"))
        self.assertIn("Démo — rien n'est enregistré", self.texte("#accueil-demo"))
        self.assertTrue(page.is_visible("#ecran-chargement") is False)
        self.assertEqual(page.evaluate("App.urlFicheEquipement('EQ-0001')"), "GMAO:EQ-0001")
        self.assertEqual(page.evaluate("performance.getEntriesByName('prevo:pret').length"), 1)

        # Export ZIP : les 24 CSV (BOM UTF-8) dans un fichier nommé prevo-export-AAAA-MM-JJ.zip
        for bouton in ("#btn-export-accueil", "#btn-export-demo"):
            if bouton == "#btn-export-demo":
                page.evaluate("location.hash = '#/apropos'")
                page.wait_for_selector("#bandeau-demo", state="visible")
                self.assertIn("Démo — rien n'est enregistré", self.texte("#bandeau-demo"))
            with page.expect_download() as attente:
                page.click(bouton)
            telechargement = attente.value
            self.assertRegex(telechargement.suggested_filename, r"^prevo-export-\d{4}-\d{2}-\d{2}\.zip$")
            with zipfile.ZipFile(telechargement.path()) as archive:
                noms_csv = sorted(n for n in archive.namelist() if n.endswith(".csv"))
                self.assertEqual(noms_csv, noms_tables_demo())
                self.assertTrue(archive.read("equipements.csv").startswith(BOM))

        # Changement de profil sans rechargement (en démo, recharger ferait tout perdre)
        page.evaluate("window.__memePage = true")
        page.click("#etat-poste")
        self.attendre_etat("profil")
        self.assertTrue(page.is_visible("#profil-annuler"))
        page.click("#profil-demandeur")
        page.fill("#profil-nom", "Lucie Martin")
        page.click("#profil-panneau-demandeur button[type=submit]")
        attendre_pret(page)
        self.assertTrue(page.evaluate("window.__memePage === true"))
        self.assertEqual(page.evaluate("App.profil"), {"type": "demandeur", "nom": "Lucie Martin", "technicienId": ""})
        self.assertNotIn("Ordres de travail", self.texte_menu())
        self.assertEqual(page.evaluate("App.mode"), "demo")
        self.assertIn("Lucie Martin", self.texte("#libelle-profil"))

    def test_fichier_import_de_csv_deposes(self):
        page = self.page
        page.goto(url_fichier("index.html"))
        self.attendre_etat("demarrage")
        with tempfile.TemporaryDirectory() as dossier:
            intrus = Path(dossier) / "notes.txt"
            intrus.write_text("pas un CSV de Prévo", encoding="utf-8")
            fichiers = [str(DOSSIER_DEMO / nom) for nom in ("equipements.csv", "localisations.csv", "techniciens.csv")]
            page.set_input_files("#fichiers-csv", fichiers + [str(intrus)])
            # Profil technicien : la liste vient de techniciens.csv déposé
            self.attendre_etat("profil")
        page.click("#profil-technicien")
        page.click("#profil-techniciens [data-technicien='TEC-0001']")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.mode"), "demo")
        self.assertEqual(page.evaluate("App.profil.technicienId"), "TEC-0001")
        self.assertEqual(page.evaluate("Donnees.lignes('equipements').length"),
                         compter_lignes_csv(DOSSIER_DEMO / "equipements.csv"))
        self.assertEqual(page.evaluate("Donnees.lignes('demandes').length"), 0)
        self.assertTrue(page.is_visible("#bandeau-demo"))
        page.wait_for_function("document.getElementById('toast').textContent.includes('notes.txt')")
        # Technicien : « Ordres de travail » oui, « Paramètres » non
        self.assertIn("Ordres de travail", self.texte_menu())
        self.assertNotIn("Paramètres", self.texte_menu())


# ---------------------------------------------------------------------------
# Mode serveur
# ---------------------------------------------------------------------------

class TestServeur(CasApp):

    def test_serveur_detecte_sans_ecran_de_demarrage_puis_profil_memorise(self):
        page = self.page
        page.add_init_script(SUIVI_ETATS_JS)
        with ServeurPrevo() as serveur:
            page.goto(serveur.url + "/")
            self.choisir_responsable()
            self.assertNotIn("demarrage", page.evaluate("window.__etats"))
            self.assertTrue(page.is_hidden("#ecran-demarrage"))
            self.assertEqual(page.evaluate("App.mode"), "serveur")
            self.assertTrue(page.is_hidden("#bandeau-demo"))
            self.assertRegex(page.evaluate("App.urlFicheEquipement('EQ-0001')"),
                             r"^http://[^/]+/#/equipement/EQ-0001$")
            self.assertEqual(page.evaluate("JSON.parse(localStorage.getItem('prevo.profil')).type"), "responsable")
            poste = page.evaluate("localStorage.getItem('prevo.poste')")
            self.assertRegex(poste, r"^Poste-[A-Z0-9]{4}$")

            # Rechargement : profil mémorisé, aucun écran de profil
            page.reload()
            attendre_pret(page)
            self.assertNotIn("profil", page.evaluate("window.__etats"))
            self.assertEqual(page.evaluate("App.poste"), poste)
            self.assertIn("Responsable", self.texte("#libelle-profil"))

    def test_serveur_base_vide_partir_des_donnees_de_demo(self):
        self.autoriser_erreur(ERREUR_CSV_ABSENT)
        page = self.page
        with ServeurPrevo(source=None) as serveur:
            page.goto(serveur.url + "/")
            self.attendre_etat("demarrage")
            self.assertTrue(page.is_visible("#ecran-base-vide"))
            self.assertTrue(page.is_visible("#btn-base-vide"))
            page.click("#btn-base-demo")
            self.choisir_responsable()
            sur_disque = sorted(chemin.name for chemin in serveur.dossier.glob("*.csv"))
            self.assertEqual(sur_disque, noms_tables_demo())
            for nom in sur_disque:
                self.assertTrue((serveur.dossier / nom).read_bytes().startswith(BOM), nom)
            self.assertEqual(page.evaluate("Donnees.lignes('equipements').length"),
                             compter_lignes_csv(serveur.dossier / "equipements.csv"))
            self.assertGreater(page.evaluate("Donnees.lignes('equipements').length"), 0)

    def test_serveur_base_vide_creer_une_base_vide(self):
        self.autoriser_erreur(ERREUR_CSV_ABSENT)
        page = self.page
        with ServeurPrevo(source=None) as serveur:
            page.goto(serveur.url + "/")
            self.attendre_etat("demarrage")
            page.click("#btn-base-vide")
            self.choisir_responsable()
            sur_disque = sorted(chemin.name for chemin in serveur.dossier.glob("*.csv"))
            self.assertEqual(sur_disque, noms_tables_demo())
            entete = (serveur.dossier / "equipements.csv").read_bytes()
            self.assertTrue(entete.startswith(BOM + b"id;repere;designation;"))
            self.assertEqual(compter_lignes_csv(serveur.dossier / "equipements.csv"), 0)

    def test_serveur_menus_et_ecrans_selon_le_profil(self):
        page = self.page
        preregler_profil(self.contexte, "demandeur", nom="Lucie Martin")
        with ServeurPrevo() as serveur:
            page.goto(serveur.url + "/")
            attendre_pret(page)
            menu = self.texte_menu()
            for entree in ("Accueil", "Signaler", "Demandes", "Parc", "À propos"):
                self.assertIn(entree, menu)
            self.assertNotIn("Ordres de travail", menu)
            self.assertNotIn("Paramètres", menu)

            # Écran interdit au profil → accueil + message
            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_function("location.hash === '#/accueil'")
            page.wait_for_function("document.getElementById('toast').textContent.includes('pas disponible')")
            # Route inconnue → accueil
            page.evaluate("location.hash = '#/route-inconnue'")
            page.wait_for_function("location.hash === '#/accueil'")
            # Entrée active du menu
            page.evaluate("location.hash = '#/parc'")
            page.wait_for_function("document.querySelector('#menu a.actif') && document.querySelector('#menu a.actif').dataset.ecran === 'parc'")
            page.evaluate("location.hash = '#/equipement/EQ-0001'")
            page.wait_for_function("document.querySelector('#contenu h1') && document.querySelector('#contenu h1').textContent.includes('—')")
            self.assertEqual(page.evaluate("document.querySelector('#menu a.actif').dataset.ecran"), "parc")

            # Responsable : tout le menu
            page.evaluate("localStorage.setItem('prevo.profil', JSON.stringify({type: 'responsable', nom: '', technicienId: ''}))")
            # (goto vers la même page avec un autre hash ne recharge pas : on recharge vraiment)
            page.evaluate("history.replaceState(null, '', '#/parametres')")
            page.reload()
            attendre_pret(page)
            menu = self.texte_menu()
            self.assertIn("Ordres de travail", menu)
            self.assertIn("Paramètres", menu)
            # Le responsable arrive bien sur l'écran Paramètres (contenu livré par le module, T15).
            self.assertEqual(page.evaluate("document.querySelector('#menu a.actif').dataset.ecran"), "parametres")
            self.assertIn("Paramètres", self.texte("#contenu h1"))

            # Technicien : OT oui, Paramètres non
            page.evaluate("localStorage.setItem('prevo.profil', JSON.stringify({type: 'technicien', nom: '', technicienId: 'TEC-0002'}))")
            page.evaluate("history.replaceState(null, '', '#/accueil')")
            page.reload()
            attendre_pret(page)
            menu = self.texte_menu()
            self.assertIn("Ordres de travail", menu)
            self.assertNotIn("Paramètres", menu)
            self.assertTrue(page.evaluate("App.estTechnicien() && !App.estResponsable()"))

    def test_serveur_route_demandee_avant_le_profil_retablie(self):
        page = self.page
        with ServeurPrevo() as serveur:
            page.goto(serveur.url + "/#/equipement/EQ-0003")
            self.attendre_etat("profil")
            page.click("#profil-demandeur")
            # Nom obligatoire
            page.click("#profil-panneau-demandeur button[type=submit]")
            self.assertTrue(page.is_visible("#profil-nom-erreur"))
            self.assertEqual(page.evaluate("document.documentElement.dataset.etat"), "profil")
            page.fill("#profil-nom", "Lucie Martin")
            page.click("#profil-panneau-demandeur button[type=submit]")
            attendre_pret(page)
            self.assertEqual(page.evaluate("location.hash"), "#/equipement/EQ-0003")
            self.assertIn("EQ-0003", self.texte("#contenu"))
            self.assertEqual(page.evaluate("App.profil.type"), "demandeur")

    def test_serveur_changement_distant_l_ecran_se_met_a_jour_seul(self):
        page = self.page
        preregler_profil(self.contexte, "responsable")
        with ServeurPrevo() as serveur:
            page.goto(serveur.url + "/#/parc")
            attendre_pret(page)
            page.evaluate("window.__memePage = true")
            self.assertNotIn("ZZ-99", self.texte("#contenu"))
            ajouter_ligne_equipement(serveur.dossier)
            # Rafraîchissement par défaut toutes les 20 s : la mise à jour arrive en 25 s au plus.
            page.wait_for_function("document.getElementById('contenu').innerText.includes('ZZ-99')", timeout=25000)
            self.assertTrue(page.evaluate("window.__memePage === true"))
            self.assertTrue(page.is_hidden("#bandeau-changement"))

    def test_serveur_saisie_en_cours_bandeau_au_lieu_du_reaffichage(self):
        page = self.page
        preregler_profil(self.contexte, "responsable")
        with ServeurPrevo() as serveur:
            # Rafraîchissement toutes les 2 s pour ce test (paramètre rafraichissement_s)
            chemin = serveur.dossier / "parametres.csv"
            texte = chemin.read_bytes().decode("utf-8")
            self.assertIn("rafraichissement_s;'20", texte)
            chemin.write_bytes(texte.replace("rafraichissement_s;'20", "rafraichissement_s;'2").encode("utf-8"))

            page.goto(serveur.url + "/#/parc")
            attendre_pret(page)
            # Une saisie dans l'écran (un champ quelconque de #contenu)
            page.evaluate("""() => {
              const champ = document.createElement('input');
              champ.id = 'saisie-test';
              document.getElementById('contenu').appendChild(champ);
            }""")
            page.fill("#saisie-test", "texte en cours")
            ajouter_ligne_equipement(serveur.dossier)
            page.wait_for_selector("#bandeau-changement", state="visible", timeout=15000)
            self.assertIn("Des données ont changé sur un autre poste", self.texte("#bandeau-changement"))
            self.assertEqual(page.input_value("#saisie-test"), "texte en cours")
            self.assertNotIn("ZZ-99", self.texte("#contenu"))
            # « Actualiser » réaffiche l'écran avec les nouvelles données
            page.click("#btn-actualiser")
            page.wait_for_function("document.getElementById('contenu').innerText.includes('ZZ-99')")
            self.assertTrue(page.is_hidden("#bandeau-changement"))
            self.assertEqual(page.locator("#saisie-test").count(), 0)

    def test_serveur_a_propos_contient_le_credit_exact(self):
        page = self.page
        preregler_profil(self.contexte, "technicien", technicien_id="TEC-0001")
        with ServeurPrevo() as serveur:
            page.goto(serveur.url + "/#/apropos")
            attendre_pret(page)
            contenu = self.texte("#contenu")
            self.assertIn(CREDIT, contenu)
            self.assertIn("2.0.0", contenu)
            self.assertIn("Les profils adaptent les écrans, ce n'est pas une sécurité", contenu)
            self.assertIn("Usage sur réseau local uniquement, sans authentification", contenu)
            # Lot 4 : assistant IA et dictée décrits, lien vers le guide (servi par serveur.py)
            self.assertIn("l'IA propose, vous validez", contenu)
            self.assertIn("Google ou de Microsoft", contenu)
            self.assertNotIn("pas encore disponibles", contenu)
            self.assertEqual(page.get_attribute("#contenu a[href='GUIDE.html']", "href"), "GUIDE.html")
            for bibliotheque in ("PapaParse 5.7.0", "qrcode-generator 2.0.4", "jsQR 1.4.0", "JSZip 3.10.2",
                                 "ECharts 5.5.1", "SheetJS CE 0.20.3", "Sora", "MIT", "Apache-2.0", "OFL"):
                self.assertIn(bibliotheque, contenu)
            self.assertEqual(page.get_attribute("#contenu a[href='js/lib/LICENCES.txt']", "href"), "js/lib/LICENCES.txt")
            self.assertIn("Serveur", contenu)
            # Badge de signature du menu → À propos
            signature = page.evaluate("document.querySelector('.signature').textContent.replace(/\\s+/g, ' ').trim()")
            self.assertEqual(signature, CREDIT)
            self.assertEqual(page.get_attribute(".signature", "href"), "#/apropos")


# ---------------------------------------------------------------------------
# Mode dossier (simulé : OPFS servi en http://127.0.0.1)
# ---------------------------------------------------------------------------

LISTER_OPFS_JS = """async (nom) => {
  const dossier = await (await navigator.storage.getDirectory()).getDirectoryHandle(nom);
  const noms = [];
  for await (const entree of dossier.values()) noms.push(entree.name);
  return noms.sort();
}"""


class TestDossier(CasApp):

    def test_dossier_choisir_base_vide_demo_reprendre_et_verrou(self):
        self.autoriser_erreur(ERREUR_PING_ABSENT)
        installer_dossier_simule(self.contexte, NOM_DOSSIER_SIMULE)
        page = self.page
        with ServeurStatique(RACINE) as statique:
            adresse = statique.url + "/index.html"
            page.goto(adresse)
            self.attendre_etat("demarrage")
            self.assertTrue(page.is_hidden("#btn-reprendre"))
            page.click("#btn-dossier")
            page.wait_for_selector("#ecran-base-vide", state="visible")
            page.click("#btn-base-demo")
            self.choisir_responsable()
            self.assertEqual(page.evaluate("App.mode"), "dossier")
            self.assertTrue(page.is_hidden("#bandeau-demo"))
            self.assertGreater(page.evaluate("Donnees.lignes('equipements').length"), 0)
            noms = page.evaluate(LISTER_OPFS_JS, NOM_DOSSIER_SIMULE)
            self.assertEqual(sorted(n for n in noms if n.endswith(".csv")), noms_tables_demo())
            self.assertIn("verrou.txt", noms)
            self.assertTrue(page.is_hidden("#alertes-app"))

            # Rechargement : « Reprendre le dossier précédent (donnees-test) » ; même onglet → pas d'alerte
            page.reload()
            self.attendre_etat("demarrage")
            self.assertTrue(page.is_visible("#btn-reprendre"))
            self.assertIn(NOM_DOSSIER_SIMULE, self.texte("#btn-reprendre"))
            page.click("#btn-reprendre")
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.mode"), "dossier")
            self.assertTrue(page.is_hidden("#alertes-app"))

            # Seconde page sur le même dossier : avertissement de verrou (non bloquant)
            seconde = self.contexte.new_page()
            self.surveiller(seconde)
            seconde.goto(adresse)
            self.attendre_etat("demarrage", seconde)
            seconde.click("#btn-reprendre")
            attendre_pret(seconde)
            seconde.wait_for_selector("#alertes-app .alerte.attention", state="visible")
            self.assertIn("semble déjà ouvert", self.texte("#alertes-app", seconde))
            seconde.click("#alertes-app .alerte button")
            self.assertTrue(seconde.is_hidden("#alertes-app"))


# ---------------------------------------------------------------------------
# Mise en page : téléphone (360 px) et grand écran (1440 px)
# ---------------------------------------------------------------------------

class TestMiseEnPage(CasApp):

    def test_telephone_360px_sans_defilement_horizontal_barre_du_bas(self):
        page = self.page
        page.set_viewport_size({"width": 360, "height": 740})
        # Écran de démarrage (file://)
        page.goto(url_fichier("index.html"))
        self.attendre_etat("demarrage")
        self.sans_defilement_horizontal()
        with ServeurPrevo() as serveur:
            page.goto(serveur.url + "/")
            self.attendre_etat("profil")
            self.sans_defilement_horizontal()
            page.click("#profil-technicien")
            self.sans_defilement_horizontal()
            page.click("#profil-techniciens [data-technicien='TEC-0002']")
            attendre_pret(page)
            for route in ("#/accueil", "#/parc", "#/apropos", "#/ot"):
                page.evaluate("location.hash = %r" % route)
                page.wait_for_function("document.querySelector('#contenu h1') !== null")
                self.sans_defilement_horizontal()
            self.assertTrue(page.is_visible(".barre-bas"))
            self.assertTrue(page.is_hidden(".menu-lateral"))
            self.assertTrue(page.is_visible(".entete-mobile"))
            # Barre du bas : 4 entrées + « Plus » ; « Plus » ouvre les autres entrées
            self.assertEqual(page.locator("#barre-bas a").count(), 4)
            page.click("#btn-plus")
            page.wait_for_selector("dialog .liste-plus", state="visible")
            self.assertIn("À propos", page.inner_text("dialog .liste-plus"))
            page.click("dialog .liste-plus a[href='#/apropos']")
            page.wait_for_function("location.hash === '#/apropos'")
            self.assertEqual(page.locator("dialog").count(), 0)
            # Zones tactiles de la barre du bas : 48 px au moins
            hauteur = page.evaluate("Math.min(...[...document.querySelectorAll('#barre-bas a, #barre-bas button')].map(e => e.getBoundingClientRect().height))")
            self.assertGreaterEqual(hauteur, 48)

    def test_grand_ecran_1440px_menu_lateral_et_repli_memorise(self):
        page = self.page
        page.set_viewport_size({"width": 1440, "height": 900})
        preregler_profil(self.contexte, "responsable")
        with ServeurPrevo() as serveur:
            page.goto(serveur.url + "/")
            attendre_pret(page)
            self.assertTrue(page.is_visible(".menu-lateral"))
            self.assertTrue(page.is_hidden(".barre-bas"))
            self.assertTrue(page.is_visible("#menu a[data-ecran='accueil'] .libelle"))
            self.assertFalse(page.evaluate("document.getElementById('app').classList.contains('replie')"))
            page.click("#btn-replier")
            self.assertTrue(page.evaluate("document.getElementById('app').classList.contains('replie')"))
            self.assertEqual(page.evaluate("localStorage.getItem('prevo.menuReplie')"), "1")
            page.reload()
            attendre_pret(page)
            self.assertTrue(page.evaluate("document.getElementById('app').classList.contains('replie')"))
            self.assertEqual(page.get_attribute("#btn-replier", "aria-expanded"), "false")
            page.click("#btn-replier")
            self.assertFalse(page.evaluate("document.getElementById('app').classList.contains('replie')"))
            self.sans_defilement_horizontal()


if __name__ == "__main__":
    unittest.main()
