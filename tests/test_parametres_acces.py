"""Lot 7 — Paramètres › Accès et installation (ARCHITECTURE.md §22.10 ; CDC D130, D131 dernier point ; CS129, CS130 ;
tâche T170) : js/modules/parametres-acces.js, le relais de parametres.js et les routes de serveur.py qui vont avec
(GET journal, POST reprendre, reglages, ia, annuler ; « retirer » du démarrage ; actif_depuis de /api/info).

Ce qui est vérifié, dans un navigateur, sur un serveur du processus (serveur.py importé comme module, configuration
présente et comptes exigés, session du responsable posée ; l'élévation et la relance sont remplacées, jamais lancées ;
faux tailscale par PREVO_TAILSCALE, jamais le vrai mkcert) :
    carte          présente pour le responsable sur le PC serveur, avec l'état du serveur : actif depuis (/api/info),
                   installation terminée, portée, adresses, Tailscale (non détecté), copie externe, les 20 dernières
                   lignes du journal sans celle qui contient « cle » ; « Actualiser » relit ; lien vers la fiche d'accès ;
                   les sept sous-sections ; aucune modification en attente ;
    absente        pour un technicien ; en mode démo (file://) ; pour un client du réseau (App.pcServeur() faux) alors
                   que l'écran Paramètres s'affiche ;
    refaire        un réglage de chaque sous-section modifié (port https, certificat « mandataire » avec ses noms,
                   Tailscale appliqué d'un clic, démarrage « à la main » avec le retrait, dossier de copie, durées de
                   session et comptes des demandeurs, IA) puis « Appliquer et relancer » : prevo.config.json relu avec
                   chaque nouvelle valeur, relance notée, Retirer_demarrage.ps1 écrit et l'élévation notée, brouillon
                   supprimé, attente puis rechargement quand actif_depuis change (le serveur relancé) ;
    annuler        à 375 px sans défilement horizontal : bornes refusées avec le message du serveur (le brouillon repris
                   pour rien est jeté), modification en attente puis « Annuler » : fichier inchangé, brouillon supprimé,
                   ni relance ni élévation.
Aucune commande d'administrateur, aucune sortie réseau, jamais donnees/ réel.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_parametres_acces.py" -v
"""
import datetime
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import commun
from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier
from test_installation_api import FAUX_TAILSCALE, NOM_TAILSCALE, Client, Enregistreur, ServeurDuProcessus, configuration, serveur

MOT_DE_PASSE = "phrase de passe du responsable"
MOT_DE_PASSE_TECHNICIEN = "cle a molette et graisse"
NOM_INTRANET = "gmao.entreprise.lan"
# Configuration d'une installation faite (Solo « dehors » par le réseau privé Tailscale) : comptes exigés, Prévo
# derrière le mandataire Tailscale, démarre avec le PC, veille empêchée, aucune copie des sauvegardes.
CONFIGURATION = {"portee": "dehors", "ecoute": "127.0.0.1", "comptes": True, "mandataire": True, "certificat_auto": False,
                 "noms": [NOM_TAILSCALE], "demarrage": "systeme", "veille_desactivee": True, "copie_sauvegardes": "",
                 "session_heures": 12, "demandeurs_avec_compte": False}
LARGEURS_JS = "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
# Chromium note en console.error toute réponse ≥ 400 : seuls les refus attendus sont permis.
ERREUR_400_INSTALLATION = re.compile(r"status of 400 .*/api/installation/")
COMPTES_JSON = b""


def setUpModule():
    """Deux comptes créés une fois (scrypt coûte) : nicolas.briand (responsable) et julien.moreau (technicien)."""
    global COMPTES_JSON
    dossier = Path(tempfile.mkdtemp(prefix="prevo-acces-modele-"))
    try:
        config = serveur.Configuration(str(dossier / "donnees"), [])
        serveur.creer_dossiers(config)
        serveur.creer_compte(config, "Nicolas", "Briand", "responsable", MOT_DE_PASSE)
        serveur.creer_compte(config, "Julien", "Moreau", "technicien", MOT_DE_PASSE_TECHNICIEN, technicien_id="TEC-0001")
        COMPTES_JSON = (dossier / "donnees" / "acces" / "comptes.json").read_bytes()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def heure_fr(iso):
    """« AAAA-MM-JJTHH:MM:SS » → « JJ/MM/AAAA HH:MM » (UI.dateHeureFr)."""
    return datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y %H:%M")


class CasAcces(CasNavigateur):
    """Un dossier temporaire et un serveur du processus par test : copie de la démo, comptes, configuration présente."""

    def setUp(self):
        super().setUp()
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-parametres-acces-"))
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

    def lancer(self, hote="127.0.0.1", reglages=None):
        """Serveur du processus sur une copie de la démo avec comptes.json et prevo.config.json (CONFIGURATION, complétée
        par « reglages »), système simulé Windows : l'élévation et la relance vont à l'enregistreur."""
        shutil.copytree(commun.DOSSIER_DEMO, self.dossier / "donnees")
        (self.dossier / "donnees" / "acces").mkdir()
        (self.dossier / "donnees" / "acces" / "comptes.json").write_bytes(COMPTES_JSON)
        self.fichier = self.dossier / "prevo.config.json"
        self.fichier.write_text(json.dumps(dict(CONFIGURATION, **(reglages or {}))), encoding="utf-8")
        config = configuration(self.dossier, None, "win32")
        self.enregistreur = Enregistreur()
        config.lancer_eleve = self.enregistreur.lancer_eleve
        config.relancer = self.enregistreur.relancer
        instance = ServeurDuProcessus(config, hote)
        self.serveurs.append(instance)
        return instance

    def session(self, instance, role="responsable", url=None):
        """Session ouverte par POST /api/connexion, cookie posé dans le contexte (avant tout chargement de page)."""
        identifiant, mot_de_passe = ("nicolas.briand", MOT_DE_PASSE) if role == "responsable" else ("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        cookie = Client(instance.url).connecter(identifiant, mot_de_passe)
        self.contexte.add_cookies([{"name": "id", "value": cookie.split("=", 1)[1], "url": url or instance.url,
                                    "httpOnly": True, "sameSite": "Lax"}])

    def ouvrir_parametres(self, url):
        self.page.goto(url + "/#/parametres")
        attendre_pret(self.page)
        self.page.wait_for_selector("#carte-sauvegardes")

    def attendre_carte(self):
        self.page.wait_for_selector("#carte-acces #acces-contenu[data-lu]")

    def section(self, cle):
        zone = self.page.locator('#carte-acces details[data-section="%s"]' % cle)
        if not zone.evaluate("d => d.open"):
            zone.locator("summary").first.click()
        return zone

    def enregistrer(self, cle, resume_attendu, section_resume=None):
        """Clique « Enregistrer ce réglage » de la sous-section et attend que le résumé (de cette section, ou de
        « section_resume ») dise la nouvelle valeur : la carte est rendue à nouveau après la réponse du serveur."""
        self.section(cle).locator('[data-enregistrer="%s"]' % cle).click()
        self.page.wait_for_function(
            "([cle, texte]) => document.querySelector('#carte-acces details[data-section=\"' + cle + '\"] .acces-resume').textContent.includes(texte)",
            arg=[section_resume or cle, resume_attendu])

    def brouillon(self):
        chemin = self.dossier / "donnees" / "installation.json"
        return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else None

    def configuration_relue(self):
        return json.loads(self.fichier.read_text(encoding="utf-8"))

    def sans_defilement_horizontal(self, contexte):
        largeurs = self.page.evaluate(LARGEURS_JS)
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))


class TestCarte(CasAcces):

    def test_responsable_sur_le_pc_serveur_etat_du_serveur_et_sections(self):
        page = self.page
        instance = self.lancer()
        journal = self.dossier / "donnees" / "journal-serveur.log"
        journal.write_text("\n".join(["ligne %d" % i for i in range(25)] + ["PREVO_IA_CLE=secret-a-ne-pas-montrer", "fin"]) + "\n", encoding="utf-8")
        self.session(instance)
        self.ouvrir_parametres(instance.url)
        self.attendre_carte()
        self.assertTrue(page.evaluate("App.pcServeur()"))
        carte = page.inner_text("#carte-acces")
        self.assertIn("Accès et installation", carte)
        self.assertEqual(page.get_attribute("#acces-fiche", "href"), "#/installation/fiche")
        # État du serveur : actif depuis (/api/info), installation terminée, portée, adresses, Tailscale, copie, journal.
        self.assertEqual(page.inner_text("#acces-actif-depuis"), heure_fr(instance.config.actif_depuis))
        self.assertIn("Terminée", page.inner_text("#acces-installation"))
        self.assertIn("Aussi hors de l'atelier", page.inner_text("#acces-portee"))
        self.assertIn(":%d/" % instance.port, page.inner_text("#acces-adresses"))
        self.assertIn("Non détecté", page.inner_text("#acces-tailscale"))
        self.assertIn("Aucune copie réglée", page.inner_text("#acces-copie"))
        lignes = page.inner_text("#acces-journal pre").splitlines()
        self.assertEqual(lignes, ["ligne %d" % i for i in range(7, 25)] + ["fin"])       # les 20 dernières, sans « cle »
        self.assertNotIn("secret-a-ne-pas-montrer", page.content())
        self.assertNotIn("PREVO_IA_CLE=", page.inner_text("#acces-journal"))
        # Les sept sous-sections, repliées, avec le résumé des valeurs en cours ; aucune modification en attente.
        sections = page.locator("#carte-acces details.acces-section")
        self.assertEqual([s.get_attribute("data-section") for s in sections.all()],
                         ["portee", "certificat", "tailscale", "demarrage", "sauvegardes", "reglages", "ia"])
        self.assertEqual(page.locator("#carte-acces details.acces-section[open]").count(), 0)
        self.assertEqual(page.locator("#carte-acces details.acces-section.sans-objet").count(), 0)   # « dehors » : tout a un objet
        self.assertIn("Avec le PC, sans fenêtre", page.inner_text('#carte-acces details[data-section="demarrage"] summary'))
        self.assertIn(NOM_TAILSCALE, page.inner_text('#carte-acces details[data-section="portee"] summary'))
        self.assertEqual(page.locator("#acces-attente").count(), 0)
        self.assertIsNone(self.brouillon())
        # L'aide d'un réglage est celle d'AccesTextes.options (une seule source).
        self.section("reglages")
        self.assertIn(page.evaluate("AccesTextes.options.session_heures.aide"),
                      page.inner_text('#carte-acces details[data-section="reglages"]'))
        # « Actualiser » relit le journal.
        with journal.open("a", encoding="utf-8") as fichier:
            fichier.write("nouvelle ligne\n")
        page.click("#acces-actualiser")
        page.wait_for_function("document.querySelector('#acces-journal').textContent.includes('nouvelle ligne')")
        self.assertEqual(self.enregistreur.relances, [])
        self.assertEqual(self.enregistreur.eleves, [])

    def test_absente_pour_un_technicien(self):
        instance = self.lancer()
        self.session(instance, "technicien")
        self.page.goto(instance.url + "/#/parametres")
        attendre_pret(self.page)
        self.page.wait_for_selector("#contenu h1")
        self.assertEqual(self.page.locator("#carte-acces").count(), 0)
        self.assertEqual(self.page.evaluate("App.profil && App.profil.type"), "technicien")

    def test_absente_en_mode_demo(self):
        page = self.page
        preregler_profil(self.contexte, "responsable")
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        page.evaluate("() => { location.hash = '#/parametres'; }")
        page.wait_for_selector("#carte-sauvegardes")
        self.assertEqual(page.evaluate("App.mode"), "demo")
        self.assertEqual(page.locator("#carte-acces, #acces-contenu").count(), 0)

    def test_absente_pour_un_client_du_reseau(self):
        adresses = [a for a in serveur.adresses_ip_reseau() if not a.startswith("127.")]
        if not adresses:
            self.skipTest("ce PC n'a pas d'adresse réseau")
        instance = self.lancer(hote="0.0.0.0")
        url = "http://%s:%d" % (adresses[0], instance.port)
        self.session(instance, url=url)
        self.ouvrir_parametres(url)
        self.assertFalse(self.page.evaluate("App.pcServeur()"))
        self.assertEqual(self.page.evaluate("App.profil && App.profil.type"), "responsable")
        self.assertEqual(self.page.locator("#carte-acces, #acces-contenu").count(), 0)


class TestRefaireChaqueReglage(CasAcces):

    def test_un_reglage_par_section_puis_appliquer_et_relancer(self):
        page = self.page
        os.environ["PREVO_TAILSCALE"] = str(FAUX_TAILSCALE)
        instance = self.lancer()
        self.session(instance)
        self.ouvrir_parametres(instance.url)
        self.attendre_carte()
        self.assertIn("Connecté : " + NOM_TAILSCALE, page.inner_text("#acces-tailscale"))
        self.assertIn("https://%s/" % NOM_TAILSCALE, page.inner_text("#acces-adresses"))
        # Portée : port https par « Régler autrement » ; le brouillon est repris de la configuration (pas des défauts).
        portee = self.section("portee")
        self.assertTrue(portee.locator('input[name="portee"][value="dehors"]').is_checked())
        portee.locator("details.installation-autrement summary").click()
        self.assertEqual(portee.locator("#inst-noms").input_value(), NOM_TAILSCALE)
        portee.locator("#inst-port_https").fill("8444")
        self.enregistrer("portee", "https 8444")
        page.wait_for_selector("#acces-attente")
        brouillon = self.brouillon()
        self.assertEqual((brouillon["port_https"], brouillon["portee"], brouillon["comptes"], brouillon["situation"], brouillon["mode_solo"]),
                         (8444, "dehors", True, "equipe", False))
        self.assertEqual(brouillon["demarrage"], "systeme")                       # repris de la configuration, pas « aucun »
        self.assertIn("Prévo redémarre", page.inner_text("#acces-attente"))
        # Certificat : derrière le mandataire de l'entreprise, avec ses noms (sous « Régler autrement »).
        certificat = self.section("certificat")
        self.assertTrue(certificat.locator('input[name="mode"][value="reseau_prive"]').is_checked())
        certificat.locator("details.installation-autrement summary").click()
        certificat.locator('input[name="mode"][value="mandataire"]').check()
        certificat.locator("#inst-noms").fill(NOM_INTRANET + ", " + NOM_TAILSCALE)
        self.enregistrer("certificat", "noms : " + NOM_INTRANET, section_resume="portee")   # les noms, visibles dans « Portée »
        self.assertEqual(self.brouillon()["noms"], [NOM_INTRANET, NOM_TAILSCALE])
        # Tailscale : appliqué d'un clic (faux tailscale : serve lancée, jamais « up »).
        tailscale = self.section("tailscale")
        self.assertTrue(tailscale.locator("#inst-tailscale-plus-tard").is_hidden())
        tailscale.locator("#inst-tailscale-appliquer").click()
        page.wait_for_selector("#inst-tailscale-resultat", state="visible")
        self.assertIn("https://%s/" % NOM_TAILSCALE, page.inner_text("#inst-tailscale-resultat"))
        lancements = (self.faux / "lancements.txt").read_text(encoding="utf-8").splitlines()
        self.assertIn("serve --bg --https=443 http://127.0.0.1:8080", lancements)
        self.assertEqual([l for l in lancements if l.split()[0] in ("up", "down", "login", "install")], [])
        self.assertTrue(self.brouillon()["mandataire"])
        # Démarrage : « à la main » alors que Prévo démarrait avec le PC → retrait (script écrit, élévation notée).
        demarrage = self.section("demarrage")
        self.assertTrue(demarrage.locator('input[name="demarrage"][value="systeme"]').is_checked())
        self.assertIn("Retirer_demarrage.ps1", demarrage.inner_text())
        demarrage.locator('input[name="demarrage"][value="aucun"]').check()
        demarrage.locator("#inst-veille").uncheck()
        self.enregistrer("demarrage", "À la main")
        self.assertEqual(self.enregistreur.eleves, [(str(self.dossier / "Retirer_demarrage.ps1"), True)])
        self.assertTrue((self.dossier / "Retirer_demarrage.ps1").is_file())
        self.assertIn("schtasks.exe --% /delete /tn \"Prevo\" /f", (self.dossier / "Retirer_demarrage.ps1").read_text(encoding="utf-8-sig"))
        self.assertEqual((self.brouillon()["demarrage"], self.brouillon()["veille_desactivee"]), ("aucun", False))
        # Copie des sauvegardes : un dossier qui existe.
        nas = self.dossier / "nas"
        nas.mkdir()
        sauvegardes = self.section("sauvegardes")
        sauvegardes.locator("#inst-copie_sauvegardes").fill(str(nas))
        self.enregistrer("sauvegardes", str(nas))
        self.assertEqual(self.brouillon()["copie_sauvegardes"], str(nas))
        # Comptes des demandeurs et durées de session.
        reglages = self.section("reglages")
        reglages.locator('input[name="demandeurs_avec_compte"]').check()
        reglages.locator('input[name="session_heures"]').fill("24")
        reglages.locator('input[name="invitation_heures"]').fill("48")
        self.enregistrer("reglages", "session 24 h")
        brouillon = self.brouillon()
        self.assertEqual((brouillon["demandeurs_avec_compte"], brouillon["session_heures"], brouillon["invitation_heures"]), (True, 24, 48))
        # IA : fournisseur, adresse, en ligne ; la clé reste hors de l'API.
        ia = self.section("ia")
        self.assertIn("Clé du service : aucune", ia.inner_text())
        self.assertIn("PREVO_IA_CLE", ia.inner_text())
        ia.locator('select[name="ia_fournisseur"]').select_option("openai")
        ia.locator('input[name="ia_url"]').fill("http://127.0.0.1:1234/v1")
        ia.locator('input[name="ia_en_ligne"]').check()
        self.enregistrer("ia", "127.0.0.1:1234")
        brouillon = self.brouillon()
        self.assertEqual((brouillon["ia_fournisseur"], brouillon["ia_url"], brouillon["ia_en_ligne"]), ("openai", "http://127.0.0.1:1234/v1", True))
        self.assertNotIn("ia_cle", brouillon)
        self.assertEqual(self.configuration_relue()["session_heures"], 12)             # rien d'écrit avant « Appliquer »
        self.assertEqual(self.enregistreur.relances, [])
        # Appliquer et relancer : configuration écrite, relance notée, attente du serveur relancé (actif_depuis change).
        avant = instance.config.actif_depuis
        page.click("#acces-appliquer")
        page.wait_for_selector("#acces-relance", state="visible")
        self.assertIn("Prévo se relance", page.inner_text("#acces-relance"))
        page.wait_for_function("document.getElementById('acces-appliquer').disabled")
        ecrit = self.configuration_relue()
        attendu = {"portee": "dehors", "ecoute": "127.0.0.1", "comptes": True, "mandataire": True, "certificat_auto": False,
                   "port_http": 8080, "port_https": 8444, "noms": [NOM_INTRANET, NOM_TAILSCALE], "demarrage": "aucun",
                   "veille_desactivee": False, "copie_sauvegardes": str(nas), "demandeurs_avec_compte": True,
                   "session_heures": 24, "session_longue_jours": 30, "invitation_heures": 48, "quota_documents_mo": 2048,
                   "ia_fournisseur": "openai", "ia_url": "http://127.0.0.1:1234/v1", "ia_en_ligne": True}
        for cle, valeur in attendu.items():
            with self.subTest(cle=cle):
                self.assertEqual(ecrit[cle], valeur)
        self.assertNotIn("ia_cle", ecrit)                                               # jamais écrite par Paramètres
        self.assertEqual(self.enregistreur.relances, [None])
        self.assertIsNone(self.brouillon())
        self.assertEqual(len(self.enregistreur.eleves), 1)                              # le retrait, une seule élévation
        # « Le serveur relancé » : il relit le fichier écrit et repart (autre instant de démarrage).
        instance.config.reglages.update(serveur.lire_configuration(str(self.fichier)))
        instance.config.actif_depuis = "2030-01-01T00:00:00"
        page.wait_for_function("document.documentElement.dataset.etat === 'pret' && location.hash === '#/parametres'"
                               " && (document.querySelector('#acces-actif-depuis') || {}).textContent === '01/01/2030 00:00'")
        self.assertEqual(page.locator("#acces-attente").count(), 0)
        self.assertIn("À la main", page.inner_text('#carte-acces details[data-section="demarrage"] summary'))


class TestAnnulerEtBornes(CasAcces):

    def test_bornes_refusees_puis_annuler_a_375_px(self):
        page = self.page
        page.set_viewport_size({"width": 375, "height": 812})
        self.autoriser_erreur(ERREUR_400_INSTALLATION)
        instance = self.lancer()
        self.session(instance)
        self.ouvrir_parametres(instance.url)
        self.attendre_carte()
        self.sans_defilement_horizontal("carte repliée")
        # Hors bornes : le message du serveur sous le bouton ; le brouillon repris pour rien est jeté.
        reglages = self.section("reglages")
        self.sans_defilement_horizontal("section dépliée")
        reglages.locator('input[name="session_heures"]').fill("0")
        reglages.locator('[data-enregistrer="reglages"]').click()
        page.wait_for_selector("#acces-erreur-reglages", state="visible")
        self.assertIn("Bornes : 1 à 720", page.inner_text("#acces-erreur-reglages"))
        self.assertIsNone(self.brouillon())
        self.assertEqual(page.locator("#acces-attente").count(), 0)
        # Pas un entier : refusé avant l'envoi.
        reglages.locator('input[name="session_heures"]').fill("douze")
        reglages.locator('[data-enregistrer="reglages"]').click()
        page.wait_for_selector("#acces-erreur-reglages", state="visible")
        self.assertIn("nombre entier", page.inner_text("#acces-erreur-reglages"))
        self.assertIsNone(self.brouillon())
        # Une modification en attente, puis « Annuler » : rien ne change.
        reglages.locator('input[name="session_heures"]').fill("24")
        self.enregistrer("reglages", "session 24 h")
        page.wait_for_selector("#acces-attente")
        self.sans_defilement_horizontal("modification en attente")
        self.assertEqual(self.brouillon()["session_heures"], 24)
        page.click("#acces-annuler")
        page.wait_for_function("!document.querySelector('#acces-attente') && document.querySelector('#acces-contenu[data-lu]')")
        self.assertIsNone(self.brouillon())
        self.assertEqual(self.configuration_relue()["session_heures"], 12)
        self.assertIn("session 12 h", page.inner_text('#carte-acces details[data-section="reglages"] summary'))
        self.assertEqual(self.enregistreur.relances, [])
        self.assertEqual(self.enregistreur.eleves, [])
        self.sans_defilement_horizontal("après annulation")


if __name__ == "__main__":
    unittest.main()
