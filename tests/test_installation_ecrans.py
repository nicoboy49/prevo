"""Lot 7 — écrans de l'assistant d'installation (ARCHITECTURE.md §22.10 ; CDC D131, D132 ; CS130 ; tâche T168) :
js/modules/installation-ecrans.js, installation-etapes.js, installation-fiche.js, css/modules/installation.css et
l'ouverture par js/app.js.

Ce qui est vérifié, dans un navigateur, sur un serveur du processus (serveur.py importé comme module : l'élévation
et la relance sont remplacées, jamais lancées ; faux mkcert et faux tailscale par PREVO_MKCERT et PREVO_TAILSCALE) :
    Solo « ce PC » à 1280 px : la page ouverte sur #/installation montre l'assistant (première ligne « Tant que
                  l'installation… »), la progression à huit étapes, les quatre textes de chaque étape comparés à
                  AccesTextes (les trois conseils avant le choix, celui de la situation après) et « Régler autrement »
                  qui déplie ; étapes 1, 2, 3 (prénom et nom seuls), 4 et 5 sans objet (ligne qui le dit), 6, 7
                  (« Plus tard »), 8 ; le brouillon replace l'assistant après un rechargement ; la fiche d'accès
                  (QR « Ouvrir Prévo ») ; « Garder ce dossier » ; « Terminer » : prevo.config.json écrit, relance
                  notée, attente puis rechargement sur #/accueil quand le serveur dit l'installation faite ;
    Atelier à 375 px : sans défilement horizontal, zones tactiles de 48 px ; mot de passe trop court refusé avant
                  l'envoi, erreur du serveur affichée telle quelle sous le bouton (dossier de copie introuvable) ;
                  certificat automatique avec le faux mkcert ; démarrage « avec le PC » : l'élévation notée, jamais
                  lancée ; fiche avec les deux QR ; impression (média print) : fonds blancs ou transparents, aucun
                  bouton, deux QR lisibles, le reste de la page caché ;
    Solo « dehors » : Tailscale (faux) détecté et appliqué d'un clic, adresse et rappels, « unattended » ;
    informaticien : toutes les étapes sur une page, chacune avec ses textes, « Régler autrement » et son bouton ;
                  noms acceptés par « Régler autrement », certificat « mandataire » ;
    réseau       : un client qui ouvre l'adresse réseau du PC sur #/installation ne voit pas l'assistant ni le lien ;
                  la page « / » sans configuration montre l'écran de profil comme avant, avec le lien discret
                  « Installer Prévo (assistant) » qui ouvre l'assistant.
Aucune commande d'administrateur, aucune sortie réseau, jamais le vrai mkcert ni le vrai tailscale, jamais donnees/ réel.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_installation_ecrans.py" -v
"""
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import commun
from commun import CasNavigateur
from test_https import trouver_openssl
from test_installation_api import FAUX_MKCERT, FAUX_TAILSCALE, NOM_TAILSCALE, Enregistreur, ServeurDuProcessus, configuration, serveur

MOT_DE_PASSE = "phrase de passe du responsable"
LARGEURS_JS = "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
ZONES_TACTILES_JS = """
Math.min(...[...document.querySelectorAll('#installation-contenu input:not([type=radio]):not([type=checkbox]), '
  + '#installation-contenu .installation-choix, #installation-contenu .btn, #installation-contenu summary')]
  .filter((e) => e.offsetParent !== null).map((e) => e.getBoundingClientRect().height))
"""
TEXTES_JS = """([cle, situation]) => {
  const bloc = document.querySelector('#installation-contenu section:not([hidden]) .installation-textes[data-choix="' + cle + '"]');
  if (!bloc) return null;
  const lu = (nom) => bloc.querySelector('[data-texte="' + nom + '"]').textContent.trim();
  const choix = AccesTextes.choix[cle];
  return { qui: lu('qui') === choix.qui, change: lu('change') === choix.change, pourquoi: lu('pourquoi') === choix.pourquoi,
    conseil: situation ? lu('conseil') === choix.conseil[situation]
      : Object.values(choix.conseil).every((texte) => lu('conseil').includes(texte)),
    titre: bloc.querySelector('h3').textContent.trim() === choix.titre };
}"""
# Chromium note en console.error toute réponse ≥ 400 : seuls les refus attendus sont permis.
ERREUR_400_INSTALLATION = re.compile(r"status of 400 .*/api/installation/")
ERREUR_404_TABLES = re.compile(r"status of 404 .*/api/csv/")


class CasInstallation(CasNavigateur):
    """Un dossier temporaire et un serveur du processus par test ; faux binaires absents par défaut."""

    def setUp(self):
        super().setUp()
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-installation-ecrans-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        self.faux = self.dossier / "faux-tailscale"
        patch = mock.patch.dict(os.environ, {
            "PREVO_MKCERT": str(self.dossier / "nulle-part" / "mkcert.exe"),
            "PREVO_TAILSCALE": str(self.dossier / "nulle-part" / "tailscale.exe"),
            "FAUX_TAILSCALE_DOSSIER": str(self.faux), "FAUX_TAILSCALE_ETAT": "Running",
            "FAUX_TAILSCALE_NOM": NOM_TAILSCALE + ".", "FAUX_TAILSCALE_EXPIRATION": ""})
        patch.start()
        self.addCleanup(patch.stop)
        silence = mock.patch.object(serveur, "afficher")
        silence.start()
        self.addCleanup(silence.stop)
        self.serveurs = []

    def tearDown(self):
        for instance in self.serveurs:
            instance.arreter()
        super().tearDown()

    def lancer(self, source=None, hote="127.0.0.1"):
        """Serveur du processus (l'application servie depuis le dépôt, les données dans le dossier temporaire),
        système simulé Windows : l'élévation va à l'enregistreur. Rend l'instance (url, config)."""
        if source is not None:
            shutil.copytree(source, self.dossier / "donnees")
        config = configuration(self.dossier, None, "win32")
        self.enregistreur = Enregistreur()
        config.lancer_eleve = self.enregistreur.lancer_eleve
        config.relancer = self.enregistreur.relancer
        instance = ServeurDuProcessus(config, hote)
        self.serveurs.append(instance)
        return instance

    def faux_mkcert(self):
        if not trouver_openssl():
            self.skipTest("openssl introuvable : faux mkcert impossible")
        os.environ["PREVO_MKCERT"] = str(FAUX_MKCERT)

    def faux_tailscale(self):
        os.environ["PREVO_TAILSCALE"] = str(FAUX_TAILSCALE)

    # -- l'assistant dans la page ------------------------------------------------------------

    def ouvrir_assistant(self, instance, page=None):
        page = page or self.page
        page.goto(instance.url + "/#/installation")
        page.wait_for_function("document.documentElement.dataset.etat === 'installation'")
        page.wait_for_selector("#installation-contenu section.installation-etape")

    def etape_courante(self, page=None):
        return (page or self.page).get_attribute("#installation-contenu section.installation-etape", "data-etape")

    def attendre_etape(self, cle, page=None):
        (page or self.page).wait_for_selector('#installation-contenu[data-formulaire="%s"] section[data-etape="%s"]' % (cle, cle))

    def verifier_textes(self, cle_choix, situation):
        """Les quatre textes du choix affiché sont ceux d'AccesTextes (conseil de la situation, ou les trois)."""
        resultat = self.page.evaluate(TEXTES_JS, [cle_choix, situation])
        self.assertIsNotNone(resultat, "textes de « %s » absents de l'étape %s" % (cle_choix, self.etape_courante()))
        self.assertEqual(resultat, {"qui": True, "change": True, "pourquoi": True, "conseil": True, "titre": True}, cle_choix)

    def verifier_autrement(self, section="#installation-contenu section.installation-etape"):
        details = self.page.locator(section + " details.installation-autrement").first
        self.assertEqual(details.locator("summary").inner_text().strip(), "Régler autrement")
        self.assertFalse(details.evaluate("d => d.open"))
        details.locator("summary").click()
        self.assertTrue(details.evaluate("d => d.open"))
        self.assertTrue(details.locator(".installation-autrement-corps").is_visible())
        details.locator("summary").click()

    def cocher(self, nom, valeur):
        self.page.check('#installation-contenu input[name="%s"][value="%s"]' % (nom, valeur))

    def continuer(self):
        self.page.click("#inst-continuer")

    def lignes_sautees(self):
        return [t.strip() for t in self.page.locator("#installation-contenu .installation-sautee").all_inner_texts()]

    def sans_defilement_horizontal(self, contexte):
        largeurs = self.page.evaluate(LARGEURS_JS)
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))


class TestParcours(CasInstallation):

    def test_solo_ce_pc_a_1280_px_jusqu_a_terminer(self):
        page = self.page
        # Après « Terminer » en Solo : parametres.csv et techniciens.csv existent, les 21 autres tables manquent (404 à
        # la lecture, tables vides : point ouvert T167/T171, pas de choix « démo ou vide » à cette première ouverture).
        self.autoriser_erreur(ERREUR_404_TABLES)
        instance = self.lancer()                                 # dossier de données vide : premier lancement
        self.ouvrir_assistant(instance)
        self.assertIn("Tant que l'installation n'est pas terminée, Prévo n'est joignable que sur ce PC.",
                      page.inner_text("#installation-premiere-ligne"))
        self.assertEqual(page.locator("#installation-contenu .installation-progression li").count(), 8)
        self.assertEqual(self.etape_courante(), "situation")
        self.assertIn("Étape 1 sur 8", page.text_content("#installation-contenu h2"))
        self.verifier_textes("installation", None)                # avant le choix : les trois conseils
        self.verifier_autrement()
        # Rien de coché : message, aucune étape écrite.
        self.continuer()
        page.wait_for_selector("#inst-erreur-situation", state="visible")
        self.assertFalse((self.dossier / "donnees" / "installation.json").exists())
        self.cocher("situation", "seul")
        self.continuer()
        self.attendre_etape("portee")
        self.assertIn("Étape 2 sur 8", page.text_content("#installation-contenu h2"))
        self.verifier_textes("exterieur", "seul")
        self.verifier_textes("mot_de_passe", "seul")
        self.verifier_autrement()
        self.assertEqual(page.input_value("#inst-port_http"), "8080")
        self.assertTrue(page.is_checked('#installation-contenu input[name="portee"][value="ce-pc"]'))   # défaut Solo
        self.continuer()
        self.attendre_etape("compte")
        self.verifier_textes("mot_de_passe", "seul")
        self.verifier_autrement()
        self.assertEqual(page.locator("#installation-contenu input[type=password]").count(), 0)   # Solo sur ce PC : le nom seul
        page.fill("#inst-prenom", "Nicolas")
        page.fill("#inst-nom", "Briand")
        self.continuer()
        # Certificat et Tailscale sans objet : sautés avec la ligne qui le dit.
        self.attendre_etape("demarrage")
        self.assertIn("Étape 6 sur 8", page.text_content("#installation-contenu h2"))
        sautees = self.lignes_sautees()
        self.assertEqual(len(sautees), 2, sautees)
        self.assertTrue(sautees[0].startswith("Étape « Certificat » sautée"), sautees)
        self.assertTrue(sautees[1].startswith("Étape « Hors de l'atelier » sautée"), sautees)
        self.assertEqual(page.locator("#installation-contenu .installation-progression li.sans-objet").count(), 2)
        self.verifier_textes("demarrage", "seul")
        self.verifier_textes("veille", "seul")
        self.verifier_autrement()
        # Le brouillon fait foi : rechargé, l'assistant revient à la première étape à faire.
        page.reload()
        page.wait_for_function("document.documentElement.dataset.etat === 'installation'")
        self.attendre_etape("demarrage")
        self.assertEqual(self.lignes_sautees(), [])
        # Précédent : l'étape du compte (les deux sans objet sont passées).
        page.click("#inst-precedent")
        self.attendre_etape("compte")
        self.assertIn("existe déjà", page.inner_text("#installation-contenu"))   # technicien « moi » créé : étape faite
        self.assertEqual(page.locator("#installation-contenu h2 .installation-fait").count(), 1)
        self.continuer()
        self.attendre_etape("demarrage")
        self.cocher("demarrage", "aucun")
        self.continuer()
        self.attendre_etape("sauvegardes")
        self.verifier_textes("sauvegardes", "seul")
        self.verifier_autrement()
        page.click("#inst-sauvegardes-plus-tard")
        self.attendre_etape("recapitulatif")
        self.assertIn("Étape 8 sur 8", page.text_content("#installation-contenu h2"))
        self.verifier_textes("etiquettes", "seul")
        page.wait_for_selector("#fiche-qr-ouvrir svg")
        self.assertEqual(page.locator("#fiche-qr-confiance").count(), 0)         # pas d'autorité sur « ce PC »
        self.assertIn("http://127.0.0.1:8080/", page.inner_text("#inst-fiche"))
        self.assertIn("Aucun mot de passe", page.inner_text("#inst-fiche"))
        self.assertIn("Moi seul", page.inner_text("#installation-contenu .installation-recap"))
        # « Régler autrement » du récapitulatif : les quatre textes de l'IA, réglée plus tard.
        page.click("#installation-contenu details.installation-autrement summary")
        self.verifier_textes("ia", "seul")
        self.assertIn("Paramètres", page.inner_text("#installation-contenu .installation-autrement-corps"))
        # Dossier conseillé (système simulé Windows, dossier temporaire) : proposé, refus possible.
        page.wait_for_selector("#inst-dossier", state="visible")
        self.assertIn("C:\\Prevo", page.inner_text("#inst-dossier"))
        page.click("#inst-dossier-garder")                     # « Rester ici » (T171) : mémorisé par le serveur, puis caché
        page.wait_for_selector("#inst-dossier", state="hidden")
        self.assertEqual(self.enregistreur.relances, [])
        # Terminer : configuration écrite, relance notée, attente ; le serveur relancé dit l'installation faite → #/accueil.
        page.click("#inst-terminer")
        page.wait_for_selector("#inst-attente", state="visible")
        self.assertIn("Prévo se relance", page.inner_text("#inst-attente"))
        page.wait_for_function("document.getElementById('inst-terminer').disabled")
        fichier = Path(instance.config.reglages["_fichier"])
        self.assertTrue(fichier.is_file())
        ecrit = json.loads(fichier.read_text(encoding="utf-8"))
        self.assertEqual((ecrit["portee"], ecrit["ecoute"], ecrit["comptes"], ecrit["demarrage"]), ("ce-pc", "127.0.0.1", False, "aucun"))
        self.assertEqual(self.enregistreur.relances, [None])
        self.assertFalse((self.dossier / "donnees" / "installation.json").exists())
        instance.config.reglages["_present"] = True                     # « le serveur relancé » : installation faite
        page.wait_for_function("location.hash === '#/accueil' && document.documentElement.dataset.etat === 'profil'")
        self.assertTrue(page.is_hidden("#ecran-installation"))
        self.assertFalse(page.evaluate("App.installationAFaire()"))
        self.assertTrue(page.is_hidden("#ecran-profil .lien-installation"))

    def test_atelier_a_375_px_mkcert_elevation_et_impression(self):
        page = self.page
        page.set_viewport_size({"width": 375, "height": 812})
        self.autoriser_erreur(ERREUR_400_INSTALLATION)
        self.faux_mkcert()
        instance = self.lancer(source=commun.DOSSIER_DEMO)
        self.ouvrir_assistant(instance)
        self.sans_defilement_horizontal("étape 1")
        self.assertGreaterEqual(page.evaluate(ZONES_TACTILES_JS), 48)
        self.cocher("situation", "equipe")
        self.continuer()
        self.attendre_etape("portee")
        self.sans_defilement_horizontal("étape 2")
        self.assertGreaterEqual(page.evaluate(ZONES_TACTILES_JS), 48)
        self.verifier_textes("exterieur", "equipe")
        self.assertTrue(page.is_checked('#installation-contenu input[name="portee"][value="atelier"]'))   # défaut Atelier
        self.continuer()
        self.attendre_etape("compte")
        self.sans_defilement_horizontal("étape 3")
        self.assertGreaterEqual(page.evaluate(ZONES_TACTILES_JS), 48)
        self.assertEqual(page.locator("#installation-contenu input[type=password]").count(), 2)
        page.fill("#inst-prenom", "Nicolas")
        page.fill("#inst-nom", "Briand")
        page.fill("#inst-mot-de-passe", "court123")
        self.assertIn("trop court", page.inner_text("#inst-force"))
        page.fill("#inst-confirmation", "court123")
        self.continuer()
        page.wait_for_selector("#inst-erreur-compte", state="visible")
        self.assertIn("12 caractères", page.inner_text("#inst-erreur-compte"))
        self.assertFalse((self.dossier / "donnees" / "acces" / "comptes.json").exists())   # refusé avant l'envoi
        page.fill("#inst-mot-de-passe", MOT_DE_PASSE)
        self.assertIn("solide", page.inner_text("#inst-force"))
        page.fill("#inst-confirmation", MOT_DE_PASSE)
        self.continuer()
        self.attendre_etape("certificat")
        self.assertTrue((self.dossier / "donnees" / "acces" / "comptes.json").is_file())
        self.assertNotIn(MOT_DE_PASSE, page.content())
        self.sans_defilement_horizontal("étape 4")
        self.assertGreaterEqual(page.evaluate(ZONES_TACTILES_JS), 48)
        self.verifier_textes("certificat", "equipe")
        self.verifier_autrement()
        self.assertTrue(page.is_checked('#installation-contenu input[name="mode"][value="automatique"]'))
        self.assertEqual(page.locator('#installation-contenu input[name="mode"][value="reseau_prive"]').count(), 0)   # pas « dehors »
        self.continuer()
        # Tailscale sans objet sur le Wi-Fi : sauté.
        self.attendre_etape("demarrage")
        self.assertEqual(len(self.lignes_sautees()), 1)
        self.assertTrue((self.dossier / "donnees" / "acces" / "certificat.pem").is_file())        # faux mkcert
        self.sans_defilement_horizontal("étape 6")
        self.assertGreaterEqual(page.evaluate(ZONES_TACTILES_JS), 48)
        self.assertIn("Une seule invite d'administrateur", page.inner_text("#inst-demarrage-uac"))
        self.assertTrue(page.is_checked('#installation-contenu input[name="demarrage"][value="systeme"]'))   # défaut Atelier
        self.assertTrue(page.is_checked("#inst-veille"))
        self.continuer()
        self.attendre_etape("sauvegardes")
        self.assertEqual(self.enregistreur.eleves, [(str(self.dossier / "Installer_demarrage.ps1"), True)])   # notée, jamais lancée
        # Erreur du serveur telle quelle sous le bouton : l'étape reste ouverte.
        page.fill("#inst-copie_sauvegardes", str(self.dossier / "absent"))
        self.continuer()
        page.wait_for_selector("#inst-erreur-sauvegardes", state="visible")
        self.assertIn("introuvable", page.inner_text("#inst-erreur-sauvegardes"))
        self.assertEqual(self.etape_courante(), "sauvegardes")
        nas = self.dossier / "nas"
        nas.mkdir()
        page.fill("#inst-copie_sauvegardes", str(nas))
        self.continuer()
        self.attendre_etape("recapitulatif")
        self.sans_defilement_horizontal("étape 8")
        page.wait_for_selector("#fiche-qr-ouvrir svg")
        page.wait_for_selector("#fiche-qr-confiance svg")                            # autorité locale présente
        self.assertIn(str(nas), page.inner_text("#inst-fiche"))
        self.assertIn("nicolas.briand", page.inner_text("#inst-fiche"))
        self.assertGreaterEqual(page.evaluate(ZONES_TACTILES_JS), 48)
        self.sans_defilement_horizontal("fiche")
        # Impression : la fiche copiée dans #impression, en média print : fond blanc ou transparent, aucun bouton, deux QR.
        page.evaluate("InstallationFiche.preparerImpression(document.querySelector('#inst-fiche .fiche-acces'))")
        page.emulate_media(media="print")
        fonds = page.evaluate("""() => [...document.querySelectorAll('#impression .fiche-acces, #impression .fiche-acces *')]
            .map((e) => getComputedStyle(e).backgroundColor).filter((c) => c !== 'rgba(0, 0, 0, 0)' && c !== 'rgb(255, 255, 255)')""")
        self.assertEqual(fonds, [])
        self.assertEqual(page.evaluate("[...document.querySelectorAll('#impression button, #impression .btn')].map((b) => getComputedStyle(b).display)"),
                         ["none"])
        self.assertEqual(page.evaluate("[...document.querySelectorAll('#impression .fiche-qr svg')].map((s) => s.getBoundingClientRect().width > 100)"),
                         [True, True])
        self.assertEqual(page.evaluate("getComputedStyle(document.getElementById('ecran-installation')).display"), "none")
        self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('#impression .fiche-acces h2')).color"), "rgb(0, 0, 0)")
        page.emulate_media(media="screen")
        page.evaluate("InstallationFiche.terminerImpression()")
        self.assertEqual(page.evaluate("document.getElementById('impression').childElementCount"), 0)
        self.assertEqual(self.enregistreur.relances, [])

    def test_solo_dehors_tailscale_applique_d_un_clic(self):
        page = self.page
        self.faux_tailscale()
        instance = self.lancer(source=commun.DOSSIER_DEMO)
        self.ouvrir_assistant(instance)
        self.cocher("situation", "seul")
        self.continuer()
        self.attendre_etape("portee")
        self.cocher("portee", "dehors")
        self.continuer()
        self.attendre_etape("compte")
        page.fill("#inst-prenom", "Nicolas")
        page.fill("#inst-nom", "Briand")
        page.fill("#inst-mot-de-passe", MOT_DE_PASSE)
        page.fill("#inst-confirmation", MOT_DE_PASSE)
        self.continuer()
        self.attendre_etape("certificat")
        self.assertTrue(page.is_checked('#installation-contenu input[name="mode"][value="reseau_prive"]'))   # Solo dehors, Tailscale présent
        self.continuer()
        self.attendre_etape("tailscale")
        self.verifier_textes("exterieur", "seul")
        self.verifier_autrement()
        self.assertIn("installé et connecté", page.inner_text("#inst-tailscale-etat"))
        self.assertEqual(page.locator("#inst-tailscale-telecharger").count(), 0)
        self.assertEqual(page.locator("#inst-continuer").count(), 0)                 # ses propres boutons
        page.click("#inst-tailscale-appliquer")
        page.wait_for_selector("#inst-tailscale-resultat", state="visible")
        self.assertIn("https://" + NOM_TAILSCALE + "/", page.inner_text("#inst-tailscale-resultat"))
        self.assertIn("expiration de clé", page.inner_text("#inst-tailscale-resultat"))
        lancements = (self.faux / "lancements.txt").read_text(encoding="utf-8").splitlines()
        self.assertIn("serve --bg --https=443 http://127.0.0.1:8080", lancements)
        page.click("#inst-tailscale-unattended")
        page.wait_for_selector("#inst-tailscale-unattended", state="hidden")
        self.assertIn("set --unattended=true", (self.faux / "lancements.txt").read_text(encoding="utf-8"))
        self.assertEqual([l for l in (self.faux / "lancements.txt").read_text(encoding="utf-8").splitlines()
                          if l.split()[0] in ("up", "down", "login", "install")], [])
        page.click("#inst-tailscale-continuer")
        self.attendre_etape("demarrage")
        self.assertEqual(page.locator("#installation-contenu .installation-progression li.faite").count(), 5)
        brouillon = json.loads((self.dossier / "donnees" / "installation.json").read_text(encoding="utf-8"))
        self.assertEqual((brouillon["noms"], brouillon["mandataire"], brouillon["etapes"]["tailscale"]), ([NOM_TAILSCALE], True, "fait"))
        self.assertNotIn(MOT_DE_PASSE, (self.dossier / "donnees" / "installation.json").read_text(encoding="utf-8"))

    def test_informaticien_toutes_les_etapes_sur_une_page(self):
        page = self.page
        instance = self.lancer(source=commun.DOSSIER_DEMO)
        self.ouvrir_assistant(instance)
        self.cocher("situation", "informaticien")
        self.continuer()
        page.wait_for_selector('#installation-contenu[data-formulaire="une-page"]')
        sections = page.locator("#installation-contenu section.installation-etape")
        self.assertEqual(sections.count(), 7)
        self.assertEqual([s.get_attribute("data-etape") for s in sections.all()],
                         ["portee", "compte", "certificat", "tailscale", "demarrage", "sauvegardes", "recapitulatif"])
        self.assertEqual(page.locator("#installation-contenu .installation-progression").count(), 0)
        for cle_etape, choix in (("portee", "exterieur"), ("compte", "mot_de_passe"), ("certificat", "certificat"),
                                 ("demarrage", "demarrage"), ("sauvegardes", "sauvegardes"), ("recapitulatif", "etiquettes")):
            with self.subTest(etape=cle_etape):
                self.assertEqual(page.evaluate(TEXTES_JS.replace("section:not([hidden])", 'section[data-etape="%s"]' % cle_etape), [choix, "informaticien"]),
                                 {"qui": True, "change": True, "pourquoi": True, "conseil": True, "titre": True})
                self.verifier_autrement('#installation-contenu section[data-etape="%s"]' % cle_etape)
        self.assertIn("Sans objet", page.inner_text('#installation-contenu section[data-etape="tailscale"]'))   # portée atelier
        self.assertEqual(page.locator("#installation-contenu [data-enregistrer]").count(), 5)
        self.assertEqual(page.locator("#inst-continuer").count(), 0)
        # Portée : nom DNS interne par « Régler autrement », mis en minuscules par le serveur.
        portee = page.locator('#installation-contenu section[data-etape="portee"]')
        portee.locator("summary").click()
        portee.locator("#inst-noms").fill("GMAO.Entreprise.lan")
        portee.locator('[data-enregistrer="portee"]').click()
        page.wait_for_selector('#installation-contenu section[data-etape="portee"] .installation-fait')
        self.assertEqual(page.input_value('#installation-contenu section[data-etape="portee"] #inst-noms'), "gmao.entreprise.lan")
        # Certificat : « mandataire » dans la liste principale pour l'informaticien ; mode enregistré.
        certificat = page.locator('#installation-contenu section[data-etape="certificat"]')
        self.assertTrue(certificat.locator('input[name="mode"][value="mandataire"]').is_visible())
        self.assertTrue(certificat.locator('input[name="mode"][value="mandataire"]').is_checked())
        certificat.locator('[data-enregistrer="certificat"]').click()
        page.wait_for_selector('#installation-contenu section[data-etape="certificat"] .installation-fait')
        brouillon = json.loads((self.dossier / "donnees" / "installation.json").read_text(encoding="utf-8"))
        self.assertEqual((brouillon["noms"], brouillon["mandataire"], brouillon["certificat_auto"], brouillon["etapes"]["certificat"]),
                         (["gmao.entreprise.lan"], True, False, "fait"))
        self.assertEqual(self.enregistreur.eleves, [])                                  # rien d'automatique sans clic
        self.assertEqual(page.locator("#inst-terminer").count(), 1)


class TestOuverture(CasInstallation):

    def test_client_du_reseau_sans_assistant_ni_lien(self):
        adresses = [a for a in serveur.adresses_ip_reseau() if not a.startswith("127.")]
        if not adresses:
            self.skipTest("ce PC n'a pas d'adresse réseau")
        page = self.page
        instance = self.lancer(source=commun.DOSSIER_DEMO, hote="0.0.0.0")
        page.goto("http://%s:%d/#/installation" % (adresses[0], instance.port))
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        self.assertTrue(page.is_hidden("#ecran-installation"))
        self.assertFalse(page.evaluate("App.pcServeur()"))
        self.assertTrue(page.evaluate("App.installationAFaire()"))              # /api/info le dit, mais pas d'assistant ici
        self.assertTrue(page.is_hidden("#ecran-profil .lien-installation"))
        self.assertEqual(page.evaluate("location.hash"), "#/installation")

    def test_adresse_vide_ecran_de_profil_et_lien_discret(self):
        page = self.page
        instance = self.lancer(source=commun.DOSSIER_DEMO)
        page.goto(instance.url + "/")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")       # comme avant le lot 7
        self.assertTrue(page.is_hidden("#ecran-installation"))
        self.assertTrue(page.is_visible("#ecran-profil .lien-installation"))
        self.assertIn("Installer Prévo (assistant)", page.inner_text("#ecran-profil .lien-installation"))
        page.click("#ecran-profil .lien-installation a")
        page.wait_for_function("document.documentElement.dataset.etat === 'installation'")
        page.wait_for_selector('#installation-contenu section[data-etape="situation"]')
        self.assertEqual(page.evaluate("location.hash"), "#/installation")
        # Quitter sans terminer : Prévo s'ouvre normalement sur l'accueil (écran de profil, aucune configuration écrite).
        page.click("#installation-quitter")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        self.assertEqual(page.evaluate("location.hash"), "#/accueil")
        self.assertFalse(Path(instance.config.reglages["_fichier"]).exists())
        # La fiche seule, sur #/installation/fiche, tant que l'installation n'est pas faite (page rechargée : un simple
        # changement de hash ne redémarre pas App).
        page.goto(instance.url + "/#/installation/fiche")
        page.reload()
        page.wait_for_function("document.documentElement.dataset.etat === 'installation'")
        page.wait_for_selector("#fiche-qr-ouvrir svg")
        self.assertTrue(page.is_visible("#inst-retour-assistant"))

    def test_comptes_sans_responsable_le_pc_serveur_ouvre_l_assistant(self):
        """Configuration écrite à la main avec « comptes », sans aucun compte (§22.10, correction du 28/10) : sur le
        PC serveur, l'assistant s'ouvre à la place d'un écran de connexion sans issue, quelle que soit l'adresse."""
        racine = Path(tempfile.mkdtemp(prefix="prevo-sans-responsable-"))
        self.addCleanup(shutil.rmtree, racine, True)
        fichier = racine / "prevo.config.json"
        fichier.write_text(json.dumps({"comptes": True}), encoding="utf-8")
        self.autoriser_erreur(re.compile(r"status of 401 .*/api/"))     # la sonde d'App avant l'assistant
        with commun.ServeurPrevo(arguments=["--config", str(fichier)]) as reel:
            page = self.page
            page.goto(reel.url + "/")
            page.wait_for_function("document.documentElement.dataset.etat === 'installation'")
            page.wait_for_selector('#installation-contenu section[data-etape="situation"]')
            self.assertTrue(page.is_hidden("#ecran-connexion"))


if __name__ == "__main__":
    unittest.main()
