"""Recette du lot 4 : assistant IA, dictée, « Ce poste », thème, https, de bout en bout (tâche T74,
ARCHITECTURE.md §17 ; CS65 à CS77). Faux fournisseur seulement (FauxFournisseur de
tests/faux_fournisseur_ia.py, partagé par la classe CasIaFonctions), jamais un vrai modèle ; reconnaissance vocale simulée (tests/test_dictee.py).

Familles (le nom du test le dit) :
    technicien : serveur.py, relais /api/ia — notes DICTÉES dans le compte rendu d'un OT en cours,
                 « Rédiger le compte rendu » puis « Proposer les codes » (Utiliser), rien d'écrit avant
                 « Enregistrer le compte rendu » ; ensuite ordres_travail.csv porte le texte et les codes,
                 le statut n'a pas bougé, le journal trace les quatre champs venus de l'IA ;
    responsable : deux postes sur le même serveur — le technicien ne peut pas activer un fournisseur en
                 ligne ; le responsable l'autorise dans Paramètres → le technicien l'active après
                 l'avertissement (mention « données envoyées à … ») ; le responsable retire
                 l'autorisation → l'IA du technicien s'arrête (plus de bouton ni de mention). Le relais
                 du serveur est intercepté par le test : rien ne quitte le poste ;
    poste      : « Ce poste » ouvert aux trois profils par le menu ; thème clair choisi sur un poste,
                 gardé au rechargement, sans effet sur un autre navigateur ;
    https      : serveur.py --certificat --cle (certificat de test fabriqué à l'exécution) : Signaler
                 avec l'IA par le relais en https, puis Envoyer → la DI est sur le disque ;
    demo       : index.html en file:// → démo : description dictée, « Proposer avec l'IA » (appel
                 direct au faux fournisseur), Utiliser, Envoyer → DI en mémoire et trace au journal ;
    design     : 1440 et 375 px — « Ce poste », Signaler et compte rendu avec l'encadré ouvert : aucun
                 défilement horizontal, mention « Proposition de l'IA » visible, zones ≥ 48 px sur
                 téléphone ; captures dans tests/resultats/recette-lot4/.

Aucun identifiant du jeu de démo écrit en dur. Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_recette_lot4.py" -v
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from commun import RACINE, ServeurPrevo, attendre_pret, preregler_profil
from faux_fournisseur_ia import REPONSES
from test_dictee import NOTER_TOASTS_JS, RECONNAISSANCE_SIMULEE_JS
from test_https import fabriquer_certificat
from test_ia_fonctions import (CHAMP_CR, LIBELLE_CODES, LIBELLE_CR, LIBELLE_DI, MENTION, NOTES, SCENARIOS,
                               VALEURS_DI_JS, CasIaFonctions, ligne_demo, lire_csv, premiers_codes, traces)
from test_ia_regles import regler_ia
from test_poste import AVERTISSEMENT, HOTE_EN_LIGNE, REFUS_DISTANT, URL_EN_LIGNE
from test_recette_lot3bis import DEBORDEMENT_JS, PETITES_ZONES_JS

DOSSIER_CAPTURES = RACINE / "tests" / "resultats" / "recette-lot4"
BOUTON_MICRO_CR = CHAMP_CR + " + .dictee-bouton"
CHAMP_DESCRIPTION = ".di-formulaire textarea[name=description]"
DICTE_DI = "de l'huile coule sous la pompe depuis ce matin"


class CasRecette(CasIaFonctions):

    def serveur_neuf(self, arguments=None):
        serveur = ServeurPrevo(arguments=arguments)
        serveur.demarrer()
        self.addCleanup(serveur.arreter)
        return serveur

    def dicter(self, bouton, texte, page=None):
        """Premier usage de la dictée sur ce poste : avertissement « Continuer », puis texte dit (définitif)
        et arrêt par un second clic."""
        page = page or self.page
        page.click(bouton)
        page.wait_for_selector("dialog[open] .dictee-avertissement")
        page.click("dialog[open] .fenetre-actions .btn-primaire")
        page.wait_for_function("() => window.__dictee.instances.length && window.__dictee.instances.at(-1).demarree")
        page.evaluate("(texte) => window.__dictee.dire(texte)", texte)
        page.click(bouton)
        page.wait_for_function("(s) => document.querySelector(s).getAttribute('aria-pressed') === 'false'", arg=bouton)

    def ot_sur_disque(self, serveur, ot_id):
        return next(l for l in lire_csv(serveur.dossier, "ordres_travail") if l["id"] == ot_id)

    def capturer(self, page, nom):
        DOSSIER_CAPTURES.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(DOSSIER_CAPTURES / (nom + ".png")), full_page=True)


# ---------------------------------------------------------------------------
# technicien : dicter, rédiger, proposer les codes, enregistrer (serveur, relais)
# ---------------------------------------------------------------------------

class TestRecetteTechnicien(CasRecette):

    def test_technicien_serveur_dicter_rediger_codes_puis_enregistrer(self):
        serveur = self.serveur_neuf()
        self.contexte.add_init_script(RECONNAISSANCE_SIMULEE_JS)
        regler_ia(self.contexte, url=self.faux.url)
        ot_id = SCENARIOS["ot_statut_en_cours"]
        ot = ligne_demo("ordres_travail", ot_id)
        technicien = ligne_demo("techniciens", ot["technicien_id"])
        page = self.ouvrir_compte_rendu(ot_id, profil="technicien", nom=technicien["prenom"] + " " + technicien["nom"],
                                        technicien_id=ot["technicien_id"], serveur=serveur)
        page.wait_for_selector('.ia-bouton:has-text("%s")' % LIBELLE_CR)
        avant = self.instantane()

        # Notes dictées : ajoutées au champ, rien d'enregistré
        page.fill(CHAMP_CR, "")
        self.dicter(BOUTON_MICRO_CR, NOTES)
        self.assertEqual(page.input_value(CHAMP_CR), NOTES)

        # L'IA met en forme, puis propose les codes : repris dans le formulaire, toujours rien d'écrit
        self.proposer_et_choisir(LIBELLE_CR, "Utiliser")
        self.assertEqual(page.input_value(CHAMP_CR), REPONSES["compteRendu"]["texte"])
        self.proposer_et_choisir(LIBELLE_CODES, "Utiliser")
        self.verifier_donnees_envoyees("compteRendu", [NOTES, ot["titre"]])
        page.wait_for_load_state("networkidle")
        self.assertEqual(self.instantane(), avant, "rien n'est écrit avant « Enregistrer le compte rendu »")

        # Enregistrement habituel : le texte et les codes sur le disque, statut inchangé, traces au journal
        page.click("#form-compte-rendu button[type=submit]")
        self.attendre_toast("Compte rendu enregistré.")
        sur_disque = self.ot_sur_disque(serveur, ot_id)
        self.assertEqual(sur_disque["compte_rendu"].replace("\r\n", "\n"), REPONSES["compteRendu"]["texte"])
        self.assertEqual({champ: sur_disque[champ] for champ in premiers_codes()}, premiers_codes())
        self.assertEqual(sur_disque["statut"], ot["statut"])
        self.assertEqual(sorted(traces(self.journal(), "ordres_travail", ot_id)),
                         ["cause_code", "compte_rendu", "remede_code", "symptome_code"])
        self.verifier_par_le_relais()


# ---------------------------------------------------------------------------
# responsable : autoriser puis retirer un fournisseur en ligne (deux postes, serveur)
# ---------------------------------------------------------------------------

class TestRecetteResponsable(CasRecette):

    def intercepter_relais(self, contexte, serveur):
        """Relais /api/ia du poste du technicien remplacé par une réponse « fournisseur en ligne » : le
        serveur ne contacte jamais l'adresse en ligne. Rend la liste des demandes reçues."""
        demandes = []

        def repondre(route):
            corps = route.request.post_data or ""
            demandes.append(corps)
            # Réponse du relais (§17.2) : { statut, corps } du fournisseur, ici sa liste des modèles.
            route.fulfill(status=200, headers={"Content-Type": "application/json"},
                          body=json.dumps({"statut": 200, "corps": {"data": [{"id": "modele-en-ligne"}]}}))
        contexte.route(serveur.url + "/api/ia", repondre)
        return demandes

    def regler_autorisation(self, page, autorise):
        self.aller("#/parametres", "#form-parametres")
        case = "#form-parametres [name=ia_distant_autorise]"
        if autorise:
            page.check(case)
        else:
            page.uncheck(case)
        page.click("#form-parametres button[type=submit]")
        page.wait_for_function("(v) => Donnees.parametre('ia_distant_autorise', '0') === v", arg="1" if autorise else "0")

    def relire(self, page):
        """Surveillance du poste : le retour sur l'onglet lance le rafraîchissement des 20 s."""
        page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")

    def test_responsable_autorise_puis_retire_un_fournisseur_en_ligne(self):
        serveur = self.serveur_neuf()
        parametres = serveur.dossier / "parametres.csv"
        # Poste du responsable (ce test) et poste du technicien (autre navigateur)
        page = self.ouvrir("#/parametres", "#form-parametres", serveur=serveur, attendre_ia=False)
        contexte, autre = self.nouveau_contexte_technicien()
        demandes = self.intercepter_relais(contexte, serveur)
        autre.goto(serveur.url + "/#/poste")
        attendre_pret(autre)
        autre.wait_for_selector("#carte-ia")

        # 1. Sans autorisation : activation refusée, rien n'est gardé, aucune demande
        self.remplir_en_ligne(autre)
        autre.check("#poste-ia-actif")
        autre.click("#btn-enregistrer-ia")
        autre.wait_for_function("(t) => (window.__toasts || []).some((x) => x.includes(t))", arg=REFUS_DISTANT)
        self.assertFalse(autre.evaluate("Ia.active()"))
        self.assertEqual(demandes, [])

        # 2. Le responsable autorise (parametres.csv) ; le poste du technicien l'apprend à sa relecture
        self.regler_autorisation(page, True)
        self.assertIn("ia_distant_autorise;'1", parametres.read_text(encoding="utf-8-sig"))
        self.relire(autre)
        autre.wait_for_function("() => document.querySelector('#poste-ia-portee').innerText.includes('autorisé par le responsable')")
        autre.click("#btn-enregistrer-ia")
        autre.wait_for_selector("dialog[open] .poste-avertissement-distant")
        self.assertIn(AVERTISSEMENT, " ".join(autre.inner_text("dialog[open]").split()))
        autre.click("dialog[open] .fenetre-actions .btn-primaire")
        autre.wait_for_function("Ia.active() && Ia.etat() === 'ok'")
        autre.wait_for_selector("#ia-mention.distant", state="visible")
        self.assertEqual(autre.inner_text("#ia-mention").strip(), "IA : données envoyées à " + HOTE_EN_LIGNE)
        self.assertTrue(demandes, "le test de connexion passe par le relais du serveur")
        # Le bouton IA apparaît dans Signaler
        autre.evaluate("() => { location.hash = '#/di/nouvelle'; }")
        autre.wait_for_selector('.di-ia .ia-bouton:has-text("%s")' % LIBELLE_DI)

        # 3. Le responsable retire l'autorisation : l'IA du technicien s'arrête, sans recharger
        self.regler_autorisation(page, False)
        self.relire(autre)
        autre.wait_for_function("() => !Ia.active()")
        autre.wait_for_selector("#ia-mention", state="hidden")
        autre.wait_for_selector(".di-ia .ia-bouton", state="detached")
        self.assertEqual(autre.locator(".ia-bouton").count(), 0)

    def nouveau_contexte_technicien(self):
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        contexte.add_init_script(RECONNAISSANCE_SIMULEE_JS)
        contexte.add_init_script(NOTER_TOASTS_JS)
        technicien_id = ligne_demo("ordres_travail", SCENARIOS["ot_statut_en_cours"])["technicien_id"]
        preregler_profil(contexte, "technicien", "Technicien essai", technicien_id=technicien_id)
        page = contexte.new_page()
        self.surveiller(page)
        return contexte, page

    def remplir_en_ligne(self, page):
        page.select_option("#poste-ia-fournisseur", "openai")
        page.fill("#poste-ia-url", URL_EN_LIGNE)
        page.fill("#poste-ia-modele", "modele-en-ligne")
        page.wait_for_selector("#poste-ia-cle", state="visible")
        page.fill("#poste-ia-cle", "cle-en-ligne")


# ---------------------------------------------------------------------------
# poste : « Ce poste » pour les trois profils, thème clair propre au navigateur
# ---------------------------------------------------------------------------

class TestRecettePoste(CasRecette):

    def test_ce_poste_trois_profils_par_le_menu_et_theme_clair_propre_au_navigateur(self):
        serveur = self.serveur_neuf()
        technicien_id = ligne_demo("ordres_travail", SCENARIOS["ot_statut_en_cours"])["technicien_id"]
        profils = [("responsable", "Responsable", ""), ("technicien", "Technicien essai", technicien_id),
                   ("demandeur", "Paul Essai", "")]
        for profil, nom, identifiant in profils:
            with self.subTest(profil=profil):
                contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
                try:
                    contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
                    preregler_profil(contexte, profil, nom, technicien_id=identifiant)
                    page = contexte.new_page()
                    self.surveiller(page)
                    page.goto(serveur.url + "/#/accueil")
                    attendre_pret(page)
                    page.locator("a[href='#/poste']:visible").first.click()
                    page.wait_for_function("location.hash === '#/poste'")
                    page.wait_for_selector("#carte-affichage")
                    self.assertEqual(page.inner_text("#contenu h1").strip(), "Ce poste")
                    self.assertIsNone(page.get_attribute("html", "data-theme"))
                    if profil == "technicien":
                        page.check("#poste-theme-clair")
                        page.wait_for_function("document.documentElement.dataset.theme === 'clair'")
                        page.reload()
                        # Posé avant le premier écran : dès que la coque est prête, le thème est déjà là
                        attendre_pret(page)
                        self.assertEqual(page.get_attribute("html", "data-theme"), "clair")
                finally:
                    contexte.close()


# ---------------------------------------------------------------------------
# https : Signaler avec l'IA par le relais, en https
# ---------------------------------------------------------------------------

class TestRecetteHttps(CasRecette):

    def test_https_signaler_avec_l_ia_par_le_relais_puis_envoyer(self):
        dossier = Path(tempfile.mkdtemp(prefix="prevo-recette-https-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        certificat, cle = fabriquer_certificat(dossier)
        serveur = self.serveur_neuf(["--certificat", str(certificat), "--cle", str(cle)])
        self.assertTrue(serveur.url.startswith("https://"))
        # Contexte qui accepte le certificat de test (auto-signé)
        self.contexte.close()
        self.contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800},
                                                    ignore_https_errors=True)
        self.contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)
        self.preparer_page()
        regler_ia(self.contexte, url=self.faux.url)
        demandeur = ligne_demo("demandes", SCENARIOS["di_statut_nouvelle"])["demandeur"]
        page = self.ouvrir_signaler(serveur=serveur, profil="demandeur", nom=demandeur)
        self.assertTrue(page.evaluate("location.protocol") == "https:")
        page.wait_for_selector('.di-ia .ia-bouton:has-text("%s")' % LIBELLE_DI)
        page.fill("input[name=symptome]", "ça fuit")
        page.fill("textarea[name=description]", "flaque sous la machine depuis ce matin")
        self.proposer_et_choisir(LIBELLE_DI, "Utiliser")
        page.click(".di-envoyer")
        page.wait_for_selector(".di-numero")
        di_id = page.get_attribute(".di-numero", "data-numero")
        di = next(l for l in lire_csv(serveur.dossier, "demandes") if l["id"] == di_id)
        self.assertEqual(di["symptome"], REPONSES["reformulerDI"]["symptome"])
        self.assertEqual(traces(self.journal(), "demandes", di_id), ["symptome", "impact"])
        self.verifier_par_le_relais()


# ---------------------------------------------------------------------------
# demo : dicter puis reformuler, appel direct au faux fournisseur
# ---------------------------------------------------------------------------

class TestRecetteDemo(CasRecette):

    def test_demo_dicter_reformuler_utiliser_puis_envoyer(self):
        self.contexte.add_init_script(RECONNAISSANCE_SIMULEE_JS)
        regler_ia(self.contexte, url=self.faux.url)
        demandeur = ligne_demo("demandes", SCENARIOS["di_statut_nouvelle"])["demandeur"]
        page = self.ouvrir_signaler(profil="demandeur", nom=demandeur)
        page.wait_for_selector('.di-ia .ia-bouton:has-text("%s")' % LIBELLE_DI)
        page.fill("input[name=symptome]", "fuite")
        self.dicter(CHAMP_DESCRIPTION + " + .dictee-bouton", DICTE_DI)
        self.assertEqual(page.input_value(CHAMP_DESCRIPTION), DICTE_DI)
        avant = self.instantane()
        self.proposer_et_choisir(LIBELLE_DI, "Utiliser")
        self.verifier_donnees_envoyees("reformulerDI", ["fuite", DICTE_DI])
        valeurs = page.evaluate(VALEURS_DI_JS)
        self.assertEqual((valeurs["symptome"], valeurs["description"]), (REPONSES["reformulerDI"]["symptome"], DICTE_DI))
        self.assertEqual(self.instantane(), avant, "rien n'est écrit avant « Envoyer »")
        page.click(".di-envoyer")
        page.wait_for_selector(".di-numero")
        di_id = page.get_attribute(".di-numero", "data-numero")
        di = page.evaluate("(id) => Donnees.trouver('demandes', id)", di_id)
        self.assertEqual((di["symptome"], di["description"], di["demandeur"]),
                         (REPONSES["reformulerDI"]["symptome"], DICTE_DI, demandeur))
        self.assertEqual(traces(self.journal(), "demandes", di_id), ["symptome", "impact"])
        # Appel direct : rien par /api/ia en démo
        self.assertFalse([a for a in self.adresses if "/api/ia" in a])


# ---------------------------------------------------------------------------
# design : 1440 et 375 px
# ---------------------------------------------------------------------------

class TestRecetteDesign(CasRecette):

    def verifier_ecran(self, page, nom, telephone):
        largeur, visible = page.evaluate(DEBORDEMENT_JS)
        self.assertLessEqual(largeur, visible, "%s : défilement horizontal (%d > %d)" % (nom, largeur, visible))
        if telephone:
            self.assertEqual(page.evaluate(PETITES_ZONES_JS), [], nom)
        self.capturer(page, nom)

    def parcourir(self, telephone):
        serveur = self.serveur_neuf()
        suffixe = "375" if telephone else "1440"
        if telephone:
            self.passer_au_telephone()
        else:
            self.page.set_viewport_size({"width": 1440, "height": 900})
        regler_ia(self.contexte, url=self.faux.url)
        ot_id = SCENARIOS["ot_statut_en_cours"]
        technicien_id = ligne_demo("ordres_travail", ot_id)["technicien_id"]
        page = self.ouvrir("#/poste", "#carte-affichage", serveur=serveur, profil="technicien", nom="Technicien essai",
                           technicien_id=technicien_id)
        self.verifier_ecran(page, "ce-poste-" + suffixe, telephone)

        self.aller("#/di/nouvelle?equipement=" + SCENARIOS["causes_equipement"], ".di-formulaire")
        page.wait_for_selector(".di-ia .ia-bouton")
        page.fill("input[name=symptome]", "ça fuit")
        self.cliquer_ia(LIBELLE_DI)
        self.assertIn(MENTION, self.attendre_proposition())
        self.verifier_ecran(page, "signaler-ia-" + suffixe, telephone)
        self.choisir("Ignorer")

        self.aller("#/ot/" + ot_id, ".ot-fiche")
        self.onglet_compte_rendu(ot_id)
        page.fill(CHAMP_CR, NOTES)
        self.cliquer_ia(LIBELLE_CODES)
        self.assertIn(MENTION, self.attendre_proposition())
        self.verifier_ecran(page, "compte-rendu-ia-" + suffixe, telephone)
        self.choisir("Ignorer")

    def test_design_1440(self):
        self.parcourir(telephone=False)

    def test_design_375_zones_de_48_px(self):
        self.parcourir(telephone=True)


if __name__ == "__main__":
    unittest.main()
