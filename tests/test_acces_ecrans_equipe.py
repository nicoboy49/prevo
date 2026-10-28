"""Lot 7 — écran Équipe › Accès (ARCHITECTURE.md §22.3, §22.4, §22.5 ; CDC D124, D125 ; CS124 ; tâche T156) :
js/modules/equipe-acces.js, réservé au responsable, en mode serveur avec les comptes exigés.

Ce qui est vérifié :
    comptes      : créer un compte (identifiant donné par Prévo, mot de passe provisoire montré une seule fois et
                   jamais laissé dans la page ; il ouvre bien une session « à changer »), modifier (rôle, technicien
                   lié), réinitialiser (nouveau provisoire), désactiver puis activer ; le serveur relu par l'API ;
    appareils    : invitation créée avec sa durée (QR SVG, lien = adresse des QR + /#/enroler/<jeton>, montré une
                   fois), un téléphone enrôlé par l'API avec ce lien apparaît dans la liste, révocation d'un appareil
                   (401 aussitôt), d'une invitation (plus personne ne s'enrôle), de tous les appareils ;
    journal      : lignes du journal des connexions affichées (connexion, création, invitation, révocation), export
                   CSV téléchargé tel que le serveur le sert ;
    profils      : le technicien n'a ni le bouton « Accès » ni l'écran (renvoyé à l'accueil) ; sans comptes (portée
                   « ce PC »), l'écran explique qu'il n'y a rien à gérer ;
    téléphone    : 375 px sans défilement horizontal, onglets compris.

Serveur réel (ServeurPrevo de tests/commun.py) sur une copie de la démo avec trois comptes et --config à « comptes » ;
la session du responsable est posée en cookie dans le contexte Playwright (l'écran de connexion vient avec T155).
Aucune commande d'administrateur, aucune sortie réseau.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_acces_ecrans_equipe.py" -v
"""
import http.client
import importlib.util
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import commun
from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

SCRIPT = RACINE / "serveur.py"


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_ecrans_equipe", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()

MOTS_DE_PASSE = {
    "nicolas.briand": "phrase du responsable 2026",
    "julien.moreau": "cle a molette et graisse",
    "lea.martin": "une demande de lea 2026",
}
AGENT = "Navigateur-de-test/1.0"
LARGEURS_JS = "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
MOTIF_LIEN = re.compile(r"^https?://[^/]+/#/enroler/([A-Za-z0-9_-]{43})$")
COMPTES_JSON = b""


def setUpModule():
    """Trois comptes créés une fois (scrypt coûte) : nicolas.briand (responsable), julien.moreau (technicien lié à
    TEC-0001), lea.martin (demandeur)."""
    global COMPTES_JSON
    dossier = Path(tempfile.mkdtemp(prefix="prevo-ecrans-equipe-modele-"))
    try:
        config = serveur.Configuration(str(dossier / "donnees"), [])
        serveur.creer_dossiers(config)
        serveur.creer_compte(config, "Nicolas", "Briand", "responsable", MOTS_DE_PASSE["nicolas.briand"])
        serveur.creer_compte(config, "Julien", "Moreau", "technicien", MOTS_DE_PASSE["julien.moreau"], technicien_id="TEC-0001")
        serveur.creer_compte(config, "Léa", "Martin", "demandeur", MOTS_DE_PASSE["lea.martin"])
        COMPTES_JSON = (dossier / "donnees" / "acces" / "comptes.json").read_bytes()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))

    @property
    def cookie(self):
        valeur = self.entetes.get("set-cookie")
        return valeur.split(";")[0] if valeur else None


class Client:
    """Requêtes directes vers le serveur, pour préparer ou relire ce que l'écran a fait."""

    def __init__(self, url):
        self.port = int(url.rsplit(":", 1)[1])

    def requete(self, methode, chemin, corps=None, cookie=None):
        entetes = {"User-Agent": AGENT}
        if cookie:
            entetes["Cookie"] = cookie
        if methode in ("PUT", "POST"):
            entetes["X-Prevo"] = "1"
        if isinstance(corps, (dict, list)):
            corps = json.dumps(corps).encode("utf-8")
            entetes["Content-Type"] = "application/json; charset=utf-8"
        connexion = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            connexion.request(methode, chemin, body=corps, headers=entetes)
            reponse = connexion.getresponse()
            return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
        finally:
            connexion.close()

    def connecter(self, identifiant, mot_de_passe=None):
        reponse = self.requete("POST", "/api/connexion", {"identifiant": identifiant,
                                                          "mot_de_passe": mot_de_passe or MOTS_DE_PASSE[identifiant],
                                                          "rester": False})
        return reponse

    def session(self, identifiant):
        reponse = self.connecter(identifiant)
        assert reponse.statut == 200, reponse.octets
        return reponse.cookie


def preparer_source(racine):
    """Copie de la démo avec les comptes ; configuration à « comptes ». Rend (dossier source, fichier de configuration)."""
    source = racine / "source"
    shutil.copytree(commun.DOSSIER_DEMO, source)
    (source / "acces").mkdir()
    (source / "acces" / "comptes.json").write_bytes(COMPTES_JSON)
    configuration = racine / "prevo.config.json"
    configuration.write_text(json.dumps({"comptes": True}), encoding="utf-8")
    return source, configuration


class CasEcranAcces(CasNavigateur):
    """Serveur réel en mode comptes pour toute la classe ; la session est posée en cookie avant le chargement."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.racine = Path(tempfile.mkdtemp(prefix="prevo-ecrans-equipe-"))
        cls.addClassCleanup(shutil.rmtree, cls.racine, True)
        source, configuration = preparer_source(cls.racine)
        cls.serveur = ServeurPrevo(source=source, arguments=["--config", str(configuration)])
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.client = Client(cls.serveur.url)

    def poser_session(self, identifiant, profil, nom, technicien_id=""):
        cookie = self.client.session(identifiant)
        self.contexte.add_cookies([{"name": "id", "value": cookie.split("=", 1)[1], "url": self.serveur.url,
                                    "httpOnly": True, "sameSite": "Lax"}])
        preregler_profil(self.contexte, profil, nom, technicien_id)
        return cookie

    def ouvrir_acces(self, onglet=None):
        self.page.goto(self.serveur.url + "/#/equipe/acces" + ("?onglet=" + onglet if onglet else ""))
        attendre_pret(self.page)
        self.page.wait_for_selector("#acces-contenu .barre-onglets")

    def activer_onglet(self, libelle, selecteur_attendu):
        self.page.click(".barre-onglets [role=tab]:has-text('%s')" % libelle)
        self.page.wait_for_selector(selecteur_attendu)

    def dialogue(self):
        return self.page.locator("dialog[open]").last

    def fermer_dialogue(self):
        self.dialogue().locator(".fenetre-actions button").last.click()
        self.page.wait_for_selector("dialog[open]", state="detached")

    def sans_defilement_horizontal(self, contexte):
        largeurs = self.page.evaluate(LARGEURS_JS)
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))


class TestComptes(CasEcranAcces):

    def setUp(self):
        super().setUp()
        self.responsable = self.poser_session("nicolas.briand", "responsable", "Nicolas Briand")

    def comptes_du_serveur(self):
        return {c["identifiant"]: c for c in self.client.requete("GET", "/api/acces/comptes", cookie=self.responsable).json()["comptes"]}

    def ligne(self, identifiant):
        return self.page.locator("#acces-comptes tbody tr:has(td b:text-is('%s'))" % identifiant)

    def test_creer_modifier_reinitialiser_desactiver_activer(self):
        page = self.page
        self.ouvrir_acces()
        page.wait_for_selector("#acces-comptes tbody tr")
        self.assertEqual(page.locator("#acces-comptes tbody tr").count(), 3)
        self.assertIn("Responsable", self.ligne("nicolas.briand").inner_text())
        self.assertIn("Julien Moreau", self.ligne("julien.moreau").inner_text())       # technicien lié (TEC-0001)
        # Créer : prénom obligatoire, rôle demandeur ; le mot de passe provisoire s'affiche une seule fois.
        page.click("#acces-creer-compte")
        dialogue = self.dialogue()
        dialogue.locator("button:has-text('Créer le compte')").click()
        page.wait_for_selector("dialog[open] [aria-invalid='true']")
        self.assertEqual(len(self.comptes_du_serveur()), 3)                                 # rien écrit
        dialogue.locator("input[name=prenom]").fill("Zoé")
        dialogue.locator("input[name=nom]").fill("Durand")
        dialogue.locator("select[name=role]").select_option("demandeur")
        dialogue.locator("button:has-text('Créer le compte')").click()
        page.wait_for_selector("#acces-mot-de-passe-provisoire")
        provisoire = page.input_value("#acces-mot-de-passe-provisoire")
        self.assertEqual(len(provisoire), 16)
        self.assertIn("zoe.durand", self.dialogue().inner_text())
        self.fermer_dialogue()
        self.assertNotIn(provisoire, page.content())                                       # montré une seule fois
        page.wait_for_selector("#acces-comptes tbody tr:has(td b:text-is('zoe.durand'))")
        self.assertIn("Mot de passe provisoire", self.ligne("zoe.durand").inner_text())
        compte = self.comptes_du_serveur()["zoe.durand"]
        self.assertEqual((compte["role"], compte["a_changer"], compte["actif"]), ("demandeur", True, True))
        entree = self.client.connecter("zoe.durand", provisoire)
        self.assertEqual((entree.statut, entree.json()["session"]["a_changer"]), (200, True))     # le provisoire ouvre
        # Modifier : rôle technicien avec une fiche liée ; un technicien sans fiche est refusé dans la fenêtre.
        self.ligne("zoe.durand").locator("button[data-action=modifier]").click()
        dialogue = self.dialogue()
        dialogue.locator("select[name=role]").select_option("technicien")
        dialogue.locator("button:has-text('Enregistrer')").click()
        page.wait_for_selector("dialog[open] [aria-invalid='true']")
        self.assertEqual(self.comptes_du_serveur()["zoe.durand"]["role"], "demandeur")
        dialogue.locator("select[name=technicien_id]").select_option("TEC-0001")
        dialogue.locator("button:has-text('Enregistrer')").click()
        page.wait_for_selector("dialog[open]", state="detached")
        page.wait_for_selector("#acces-comptes tbody tr:has(td b:text-is('zoe.durand')):has-text('Technicien')")
        compte = self.comptes_du_serveur()["zoe.durand"]
        self.assertEqual((compte["role"], compte["technicien_id"]), ("technicien", "TEC-0001"))
        # Réinitialiser : un nouveau provisoire, différent, montré une fois.
        self.ligne("zoe.durand").locator("button[data-action=reinitialiser]").click()
        self.dialogue().locator("button:has-text('Réinitialiser')").click()
        page.wait_for_selector("#acces-mot-de-passe-provisoire")
        nouveau = page.input_value("#acces-mot-de-passe-provisoire")
        self.assertEqual(len(nouveau), 16)
        self.assertNotEqual(nouveau, provisoire)
        self.fermer_dialogue()
        self.assertNotIn(nouveau, page.content())
        self.assertEqual(self.client.connecter("zoe.durand", provisoire).statut, 401)
        self.assertEqual(self.client.connecter("zoe.durand", nouveau).statut, 200)
        # Désactiver (confirmation) puis activer ; jamais de bouton pour son propre compte.
        self.assertEqual(self.ligne("nicolas.briand").locator("button[data-action=desactiver]").count(), 0)
        page.wait_for_selector("#acces-comptes tbody tr:has(td b:text-is('zoe.durand')) button[data-action=desactiver]")
        self.ligne("zoe.durand").locator("button[data-action=desactiver]").click()
        self.dialogue().locator("button:has-text('Désactiver')").click()
        page.wait_for_selector("#acces-comptes tbody tr:has(td b:text-is('zoe.durand')):has-text('Désactivé')")
        self.assertFalse(self.comptes_du_serveur()["zoe.durand"]["actif"])
        self.assertEqual(self.client.connecter("zoe.durand", nouveau).statut, 401)
        self.ligne("zoe.durand").locator("button[data-action=activer]").click()
        page.wait_for_selector("#acces-comptes tbody tr:has(td b:text-is('zoe.durand')) button[data-action=desactiver]")
        self.assertTrue(self.comptes_du_serveur()["zoe.durand"]["actif"])
        # Aucun secret dans la page ni dans le journal des connexions.
        contenu = page.content()
        for secret in (provisoire, nouveau, MOTS_DE_PASSE["nicolas.briand"]):
            self.assertNotIn(secret, contenu)
        journal = self.client.requete("GET", "/api/acces/journal", cookie=self.responsable).octets.decode("utf-8-sig")
        self.assertNotIn(provisoire, journal)
        self.assertNotIn(nouveau, journal)
        self.assertIn("zoe.durand;", journal)
        self.assertIn(";creation;", journal)


class TestAppareils(CasEcranAcces):

    def setUp(self):
        super().setUp()
        self.responsable = self.poser_session("nicolas.briand", "responsable", "Nicolas Briand")

    def enroler(self, lien, nom):
        jeton = MOTIF_LIEN.match(lien).group(1)
        reponse = self.client.requete("POST", "/api/enroler", {"invitation": jeton, "nom": nom})
        return reponse

    def test_invitation_qr_enrolement_et_revocations(self):
        page = self.page
        self.ouvrir_acces("appareils")
        page.wait_for_selector("#acces-inviter")
        page.select_option("#acces-duree-invitation", "72")
        page.click("#acces-creer-invitation")
        page.wait_for_selector("#acces-invitation-qr svg")
        lien = page.input_value("#acces-invitation-lien")
        self.assertRegex(lien, MOTIF_LIEN)
        self.assertTrue(lien.startswith("http://"))
        self.assertIn("Demandeur", self.dialogue().inner_text())
        self.fermer_dialogue()
        self.assertNotIn(MOTIF_LIEN.match(lien).group(1), page.content())                  # le jeton n'est montré qu'une fois
        page.wait_for_selector("#acces-invitations tbody tr")
        ligne = page.locator("#acces-invitations tbody tr").first
        self.assertIn("Valide", ligne.inner_text())
        invitation = self.client.requete("GET", "/api/acces/invitations", cookie=self.responsable).json()["invitations"][0]
        self.assertEqual(invitation["expire_le"][:10] >= invitation["cree_le"][:10], True)
        # Un téléphone ouvre le lien et s'enrôle (l'écran d'enrôlement vient avec T156 bis / T155 : ici par l'API).
        reponse = self.enroler(lien, "Karim Benali")
        self.assertEqual(reponse.statut, 200, reponse.octets)
        cookie_appareil = reponse.cookie
        self.assertEqual(self.enroler(lien, "Paul Essai").statut, 200)
        self.activer_onglet("Comptes", "#acces-comptes")
        self.activer_onglet("Appareils", "#acces-liste-appareils tbody tr:has-text('Karim Benali')")
        self.assertEqual(page.locator("#acces-liste-appareils tbody tr").count(), 2)
        self.assertIn("Karim Benali", page.locator("#acces-liste-appareils").inner_text())
        # Révoquer l'appareil de Karim : 401 aussitôt pour lui, l'autre continue.
        page.locator("#acces-liste-appareils tbody tr:has-text('Karim Benali') button[data-revoquer=appareil]").click()
        self.dialogue().locator("button:has-text('Révoquer')").click()
        page.wait_for_selector("#acces-liste-appareils tbody tr:has-text('Karim Benali'):has-text('Révoqué')")
        self.assertEqual(self.client.requete("GET", "/api/csv/equipements", cookie=cookie_appareil).statut, 401)
        # Révoquer l'invitation : plus personne ne s'enrôle avec.
        page.locator("#acces-invitations tbody tr").first.locator("button[data-revoquer=invitation]").click()
        self.dialogue().locator("button:has-text('Révoquer')").click()
        page.wait_for_selector("#acces-invitations tbody tr:has-text('Révoquée')")
        self.assertEqual(self.enroler(lien, "Encore Un").statut, 401)
        # Révoquer tous : l'appareil restant tombe aussi.
        page.click("#acces-revoquer-tous")
        self.dialogue().locator("button:has-text('Tout révoquer')").click()
        page.wait_for_selector("#acces-liste-appareils tbody tr:has-text('Paul Essai'):has-text('Révoqué')")
        self.assertEqual(page.locator("#acces-revoquer-tous").count(), 0)
        appareils = self.client.requete("GET", "/api/acces/invitations", cookie=self.responsable).json()["appareils"]
        self.assertEqual([a["revoque"] for a in appareils], [True, True])
        # Journal : invitation, appareils, révocations.
        self.activer_onglet("Journal des connexions", "#acces-journal tbody tr")
        texte = page.locator("#acces-journal").inner_text()
        for attendu in ("Invitation", "Appareil enrôlé", "Révocation", "Connexion", "nicolas.briand", "appareil:AP-"):
            self.assertIn(attendu, texte)

    def test_export_du_journal(self):
        page = self.page
        self.ouvrir_acces("journal")
        page.wait_for_selector("#acces-journal tbody tr")
        with page.expect_download() as telechargement:
            page.click("#acces-exporter-journal")
        fichier = telechargement.value
        self.assertEqual(fichier.suggested_filename, "journal-acces.csv")
        contenu = Path(fichier.path()).read_text(encoding="utf-8-sig")
        attendu = self.client.requete("GET", "/api/acces/journal", cookie=self.responsable).octets.decode("utf-8-sig")
        self.assertTrue(contenu.startswith("date;qui;adresse;agent;resultat;tailscale"))
        self.assertEqual(contenu.splitlines()[:3], attendu.splitlines()[:3])

    def test_telephone_sans_defilement_horizontal(self):
        page = self.page
        page.set_viewport_size({"width": 375, "height": 812})
        self.ouvrir_acces()
        page.wait_for_selector("#acces-comptes tbody tr")
        self.sans_defilement_horizontal("comptes")
        self.activer_onglet("Appareils", "#acces-inviter")
        self.sans_defilement_horizontal("appareils")
        self.activer_onglet("Journal des connexions", "#acces-journal")
        self.sans_defilement_horizontal("journal")


class TestProfils(CasEcranAcces):

    def test_technicien_sans_bouton_ni_ecran(self):
        page = self.page
        self.poser_session("julien.moreau", "technicien", "Julien Moreau", "TEC-0001")
        page.goto(self.serveur.url + "/#/equipe")
        attendre_pret(page)
        page.wait_for_selector("#contenu h1:has-text('Équipe')")
        self.assertEqual(page.locator("#equipe-acces").count(), 0)
        page.goto(self.serveur.url + "/#/equipe/acces")
        page.wait_for_function("() => location.hash === '#/accueil'")
        self.assertEqual(page.locator("#acces-contenu").count(), 0)

    def test_responsable_a_le_bouton(self):
        page = self.page
        self.poser_session("nicolas.briand", "responsable", "Nicolas Briand")
        page.goto(self.serveur.url + "/#/equipe")
        attendre_pret(page)
        page.wait_for_selector("#equipe-acces")
        page.click("#equipe-acces")
        page.wait_for_selector("#acces-contenu .barre-onglets")
        self.assertEqual(page.evaluate("location.hash"), "#/equipe/acces")


class TestSansComptes(CasNavigateur):

    def test_ecran_explique_qu_il_n_y_a_rien_a_gerer(self):
        preregler_profil(self.contexte, "responsable", "Nicolas Briand")
        with ServeurPrevo() as serveur_:
            self.page.goto(serveur_.url + "/#/equipe/acces")
            attendre_pret(self.page)
            self.page.wait_for_selector("#acces-contenu .alerte")
            self.assertIn("ne sont pas activés", self.page.locator("#acces-contenu").inner_text())
            self.assertEqual(self.page.locator(".barre-onglets").count(), 0)


if __name__ == "__main__":
    unittest.main()
