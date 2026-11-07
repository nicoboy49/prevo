"""Lot 7 — écran de connexion et profil déduit du compte (ARCHITECTURE.md §8, §22.4 ; CDC D124, D125, D126 ; CS124 ;
tâche T155) : js/modules/connexion-ecrans.js (objet Connexion) et js/app.js en mode serveur avec les comptes exigés.

Ce qui est vérifié :
    connexion      : à 1280 px, l'écran de connexion remplace l'écran de profil de 1.2 (jamais traversé) ; champs
                     vides et mauvais mot de passe → message, aucune session ; « rester connecté » → cookie avec
                     Max-Age ; App.profil et App.session déduits du compte, profil jamais mémorisé (prevo.poste gardé),
                     « Prénom Nom · Rôle » dans le menu, « se déconnecter » à la place de « changer » ; À propos sans
                     « ce n'est pas une sécurité » ; rechargement sans nouvel écran de connexion ;
    téléphone      : 375 px sans défilement horizontal, zones tactiles de 48 px ; technicien → profil technicien lié
                     (TEC-0001), sans le bouton ni l'écran Équipe › Accès ;
    provisoire     : compte créé par l'API avec un mot de passe provisoire → changement obligatoire (règles du
                     serveur affichées, confirmation, actuel faux refusé 403), puis l'application s'ouvre ;
    appareil       : page ouverte sur #/enroler/<jeton> (invitation de l'API) → « Entrez votre nom » → demandeur sans
                     mot de passe, route #/accueil, pas de bouton « se déconnecter », reconnu au rechargement ;
                     révoqué → écran de connexion avec le bandeau « n'est plus autorisé » ; enrôlement désactivé
                     (demandeurs_avec_compte) → message et champs classiques ;
    déconnexion    : bouton du menu → écran de connexion, session fermée sur le serveur, route gardée ; session
                     fermée ailleurs → 401 relu par App (événement prevo:session-absente) → écran de connexion, puis
                     la coque se rouvre sur la même route ;
    sans comptes   : ServeurPrevo() (portée « ce PC ») : l'écran de profil de 1.2 comme avant, texte d'À propos inchangé ;
    langue (T297)  : en haut de l'écran, visible sans menu, le globe et les langues écrites dans leur langue (aucun autre
                     mot) ; English → écran en anglais, le choix tient au rechargement ; Français (sans choix) → clé
                     retirée ; installation en anglais (langue_defaut = en) : appareil neuf en français → écran en
                     anglais d'emblée (data-langue-installation de index.html), Français choisi gardé ; valeurs abîmées
                     gardées par l'appareil : français, sans erreur.

Serveur réel (ServeurPrevo(comptes=True) de tests/commun.py) sur une copie de la démo avec trois comptes ; aucune
commande d'administrateur, aucune sortie réseau, jamais le dossier donnees/ réel.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_acces_ecrans.py" -v
"""
import http.client
import json
import re
import unittest

from atelier import motif_refus_du_demandeur
from commun import COMPTES_DE_TEST, RACINE, CasNavigateur, ServeurPrevo, attendre_pret

AGENT = "Navigateur-de-test/1.0"
LARGEURS_JS = "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
# Enregistre chaque valeur prise par <html data-etat> (écrans traversés).
SUIVI_ETATS_JS = """
window.__etats = [];
new MutationObserver(() => {
  const etat = document.documentElement && document.documentElement.dataset.etat;
  if (etat && window.__etats[window.__etats.length - 1] !== etat) window.__etats.push(etat);
}).observe(document, { subtree: true, attributes: true, attributeFilter: ['data-etat'] });
"""
HAUTEUR_MIN_JS = ("Math.min(...[...document.querySelectorAll(%s)].map((e) => e.getBoundingClientRect().height))")
ZONES_TACTILES = ("'#connexion-identifiant, #connexion-mot-de-passe, #connexion-formulaire label.case, #connexion-valider'")
# Chromium note en console.error toute réponse ≥ 400 : seuls les refus attendus sont permis, précisément.
ERREUR_401_SONDE = re.compile(r"status of 401 .*/api/versions")          # sans session : la sonde d'App (appareil refusé ?)
ERREUR_401_CONNEXION = re.compile(r"status of 401 .*/api/connexion")
ERREUR_401_TABLES = re.compile(r"status of 401 .*/api/(?:versions|csv/)")
ERREUR_403_MOT_DE_PASSE = re.compile(r"status of 403 .*/api/mot-de-passe")
ERREUR_403_ENROLER = re.compile(r"status of 403 .*/api/enroler")
MOTS_DE_PASSE = {valeurs[0]: valeurs[3] for valeurs in COMPTES_DE_TEST.values()}
# Sélecteur de langue de l'écran de connexion (T297) : options, valeur, texte de la zone hors de la liste, étiquette.
SELECTEUR_LANGUE_JS = """() => {
  const zone = document.getElementById('connexion-langue');
  const liste = document.getElementById('connexion-langue-liste');
  const autour = [...zone.childNodes].filter((n) => n !== liste).map((n) => n.textContent).join('').trim();
  const haut = (selecteur) => document.querySelector(selecteur).getBoundingClientRect().top;
  return { options: [...liste.options].map((o) => [o.value, o.textContent, o.lang]), valeur: liste.value, autour,
    etiquette: liste.getAttribute('aria-label'), lang: document.documentElement.lang,
    globe: Boolean(zone.querySelector('svg.icone[aria-hidden="true"]')),
    enHaut: haut('#connexion-langue') < haut('#ecran-connexion .marque'), hauteur: liste.getBoundingClientRect().height };
}"""


def texte_du_dictionnaire(code, cle):
    """Valeur de `cle` dans js/i18n/<code>.js, lue dans le fichier (échappements « \\' » retirés)."""
    source = (RACINE / "js" / "i18n" / (code + ".js")).read_text(encoding="utf-8")
    trouve = re.search(r"^  '%s': '((?:[^'\\]|\\.)*)',$" % re.escape(cle), source, re.MULTILINE)
    if not trouve:
        raise AssertionError("clé %s absente de js/i18n/%s.js" % (cle, code))
    return re.sub(r"\\(.)", r"\1", trouve.group(1))


def langues_declarees():
    """[(code, nom)] de js/i18n/langues.js, dans l'ordre."""
    source = (RACINE / "js" / "i18n" / "langues.js").read_text(encoding="utf-8")
    return re.findall(r"^I18n\.declarer\(\{ code: '([^']+)', nom: '([^']+)'", source, re.MULTILINE)
NOUVEAU_MOT_DE_PASSE = "une phrase de passe pour zoe"


def requete(url, methode, chemin, corps=None, cookie=None):
    """Une requête directe vers le serveur (préparer, relire) → (statut, en-têtes, octets)."""
    port = int(url.rsplit(":", 1)[1])
    entetes = {"User-Agent": AGENT}
    if cookie:
        entetes["Cookie"] = cookie
    if methode in ("PUT", "POST"):
        entetes["X-Prevo"] = "1"
    if isinstance(corps, (dict, list)):
        corps = json.dumps(corps).encode("utf-8")
        entetes["Content-Type"] = "application/json; charset=utf-8"
    connexion = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        connexion.request(methode, chemin, body=corps, headers=entetes)
        reponse = connexion.getresponse()
        return reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read()
    finally:
        connexion.close()


class CasConnexion(CasNavigateur):
    """Serveur réel en mode comptes pour toute la classe ; chaque test part d'un contexte neuf, sans cookie."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo(comptes=True)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def setUp(self):
        super().setUp()
        self.page.add_init_script(SUIVI_ETATS_JS)
        self.autoriser_erreur(ERREUR_401_SONDE)

    def attendre_etat(self, etat, page=None):
        (page or self.page).wait_for_function("document.documentElement.dataset.etat === %r" % etat)

    def etats(self, page=None):
        return (page or self.page).evaluate("window.__etats")

    def session_du_navigateur(self):
        """GET /api/session avec les cookies du contexte Playwright (la requête API partage son stockage)."""
        return self.contexte.request.get(self.serveur.url + "/api/session").json()

    def connecter(self, identifiant, mot_de_passe=None, rester=False, page=None):
        page = page or self.page
        page.fill("#connexion-identifiant", identifiant)
        page.fill("#connexion-mot-de-passe", mot_de_passe if mot_de_passe is not None else MOTS_DE_PASSE[identifiant])
        page.set_checked("#connexion-rester", rester)
        page.click("#connexion-valider")

    def sans_defilement_horizontal(self, contexte, page=None):
        largeurs = (page or self.page).evaluate(LARGEURS_JS)
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))

    def api(self, methode, chemin, corps=None, role="responsable"):
        statut, entetes, octets = requete(self.serveur.url, methode, chemin, corps, self.serveur.session(role))
        return statut, (json.loads(octets.decode("utf-8")) if octets else None)


class TestConnexion(CasConnexion):

    def test_refus_de_connexion_affiche_dans_la_langue_de_l_ecran(self):
        """T285 (D157) : l'écran lit le message du serveur par son code (StockageServeur.texte) ; en français, inchangé."""
        page = self.page
        self.autoriser_erreur(ERREUR_401_CONNEXION)
        page.goto(self.serveur.url + "/")
        self.attendre_etat("connexion")
        page.evaluate("""() => {
          I18n.declarer({ code: 'xx', nom: 'Essai', locale: 'en-GB', statut: 'automatique' });
          I18n.ajouter('xx', { 'serveur.sessions.connexion_refusee': 'Refus (essai xx)' });
          I18n.choisir('xx');
        }""")
        self.connecter("nicolas.briand", "pas le bon mot de passe")
        page.wait_for_function("document.getElementById('connexion-erreur').textContent.includes('Refus (essai xx)')")
        self.assertNotIn("Identifiant ou mot de passe", page.inner_text("#connexion-erreur"))
        page.evaluate("I18n.choisir('fr')")
        self.connecter("nicolas.briand", "pas le bon mot de passe")
        page.wait_for_function("document.getElementById('connexion-erreur').textContent.includes('Identifiant ou mot de passe incorrect.')")

    def choisir_langue(self, code):
        with self.page.expect_navigation():
            self.page.select_option("#connexion-langue-liste", code)
        self.attendre_etat("connexion")

    def bouton_connexion(self):
        return self.page.inner_text("#connexion-valider").strip()

    def test_selecteur_de_langue_sans_menu_et_choix_garde(self):
        """T297 : installation sans réglage, appareil en français ; le sélecteur change la langue sans menu."""
        page = self.page
        page.goto(self.serveur.url + "/")
        self.attendre_etat("connexion")
        selecteur = page.evaluate(SELECTEUR_LANGUE_JS)
        self.assertEqual(selecteur["options"], [[code, nom, code] for code, nom in langues_declarees()])
        self.assertEqual((selecteur["valeur"], selecteur["lang"], selecteur["autour"]), ("fr", "fr", ""))
        self.assertTrue(selecteur["globe"])
        self.assertTrue(selecteur["enHaut"])
        self.assertGreaterEqual(selecteur["hauteur"], 44)
        self.assertEqual(selecteur["etiquette"], texte_du_dictionnaire("fr", "connexion.choix_langue.etiquette"))
        self.assertTrue(page.is_visible("#connexion-langue-liste"))
        self.assertEqual(self.bouton_connexion(), texte_du_dictionnaire("fr", "socle.connexion_valider.connecter"))
        # English : l'écran se recharge en anglais ; le choix tient au rechargement.
        self.choisir_langue("en")
        self.assertEqual(self.bouton_connexion(), texte_du_dictionnaire("en", "socle.connexion_valider.connecter"))
        self.assertEqual(page.evaluate("[document.documentElement.lang, localStorage.getItem('prevo.langue')]"), ["en", "en"])
        self.assertEqual(page.evaluate(SELECTEUR_LANGUE_JS)["etiquette"],
                         texte_du_dictionnaire("en", "connexion.choix_langue.etiquette"))
        page.reload()
        self.attendre_etat("connexion")
        self.assertEqual(page.evaluate("I18n.langue"), "en")
        # Français, la langue qu'aurait l'appareil sans choix : la clé est retirée.
        self.choisir_langue("fr")
        self.assertEqual(self.bouton_connexion(), texte_du_dictionnaire("fr", "socle.connexion_valider.connecter"))
        self.assertEqual(page.evaluate("[document.documentElement.lang, localStorage.getItem('prevo.langue')]"), ["fr", None])
        # Une seule liste, même après un retour à l'écran de connexion.
        self.assertEqual(page.locator("#connexion-langue select").count(), 1)

    def test_valeurs_abimees_gardees_par_l_appareil_francais_sans_erreur(self):
        self.contexte.add_init_script("localStorage.setItem('prevo.langue', 'zz\\\"><b>x</b>'); "
                                      "localStorage.setItem('prevo.langue.installation', '<img src=x onerror=alert(1)>');")
        page = self.page
        page.goto(self.serveur.url + "/")
        self.attendre_etat("connexion")
        selecteur = page.evaluate(SELECTEUR_LANGUE_JS)
        self.assertEqual((selecteur["valeur"], selecteur["lang"]), ("fr", "fr"))
        self.assertEqual(self.bouton_connexion(), texte_du_dictionnaire("fr", "socle.connexion_valider.connecter"))

    def test_responsable_a_1280_px_rester_connecte_profil_deduit_et_a_propos(self):
        page = self.page
        self.autoriser_erreur(ERREUR_401_CONNEXION)
        cookies = []
        page.on("response", lambda r: cookies.append(r.header_value("set-cookie")) if r.url.endswith("/api/connexion") else None)
        page.goto(self.serveur.url + "/")
        self.attendre_etat("connexion")
        self.assertTrue(page.is_visible("#connexion-formulaire"))
        self.assertTrue(page.is_hidden("#ecran-profil"))
        self.assertTrue(page.is_hidden("#connexion-enrolement"))
        self.assertTrue(page.is_hidden("#connexion-mot-de-passe-panneau"))
        self.assertIn("Rester connecté sur cet appareil", page.inner_text("#connexion-formulaire"))
        self.assertTrue(page.inner_text("#connexion-rester-aide").strip())               # aide de T169 (acces-textes.js)
        self.assertGreaterEqual(page.evaluate(HAUTEUR_MIN_JS % ZONES_TACTILES), 48)
        # Champs vides : message, aucune requête.
        page.click("#connexion-valider")
        page.wait_for_selector("#connexion-erreur", state="visible")
        self.assertIn("Indiquez", page.inner_text("#connexion-erreur"))
        self.assertEqual(cookies, [])
        # Mauvais mot de passe : le message du serveur tel quel, pas de session, le champ vidé.
        self.connecter("nicolas.briand", "pas le bon mot de passe")
        page.wait_for_function("document.getElementById('connexion-erreur').textContent.includes('Identifiant ou mot de passe incorrect.')")
        self.assertEqual(page.evaluate("document.documentElement.dataset.etat"), "connexion")
        self.assertIsNone(self.session_du_navigateur()["session"])
        self.assertEqual(page.input_value("#connexion-mot-de-passe"), "")
        self.assertFalse(page.is_disabled("#connexion-valider"))
        # Bon mot de passe avec « rester » : cookie avec Max-Age, application ouverte, profil déduit du compte.
        self.connecter("nicolas.briand", rester=True)
        attendre_pret(page)
        self.assertEqual(len(cookies), 2)
        self.assertIn("Max-Age=", cookies[-1])
        self.assertIn("HttpOnly", cookies[-1])
        self.assertEqual(page.evaluate("App.mode"), "serveur")
        self.assertTrue(page.evaluate("App.comptesExiges()"))
        self.assertEqual(page.evaluate("App.profil"), {"type": "responsable", "nom": "Nicolas Briand", "technicienId": ""})
        self.assertEqual(page.evaluate("App.session.identifiant"), "nicolas.briand")
        self.assertFalse(page.evaluate("App.session.appareil"))
        self.assertEqual(page.inner_text("#libelle-profil").strip(), "Nicolas Briand · Responsable")
        self.assertEqual(page.inner_text("#etat-poste .changer").strip(), "se déconnecter")
        self.assertIsNone(page.evaluate("localStorage.getItem('prevo.profil')"))          # jamais mémorisé en mode comptes
        self.assertRegex(page.evaluate("localStorage.getItem('prevo.poste')"), r"^Poste-[A-Z0-9]{4}$")
        self.assertNotIn("profil", self.etats())
        self.assertIn("connexion", self.etats())
        self.assertEqual(self.etats()[-1], "pret")
        self.assertIn("Équipe", page.inner_text("#menu"))
        self.assertEqual(self.session_du_navigateur()["session"]["identifiant"], "nicolas.briand")
        # Le responsable a bien le bouton Équipe › Accès.
        page.evaluate("location.hash = '#/equipe'")
        page.wait_for_selector("#equipe-acces")
        # À propos (D126) : plus « ce n'est pas une sécurité ».
        page.evaluate("location.hash = '#/apropos'")
        page.wait_for_function("document.querySelector('#contenu h1') && document.querySelector('#contenu h1').textContent.includes('À propos')")
        contenu = page.inner_text("#contenu")
        self.assertIn("le serveur vérifie les droits", contenu)
        self.assertNotIn("ce n'est pas une sécurité", contenu)
        self.assertNotIn("sans authentification", contenu)
        # Rechargement : la session vaut, aucun écran de connexion ni de profil.
        page.reload()
        attendre_pret(page)
        self.assertNotIn("connexion", self.etats())
        self.assertNotIn("profil", self.etats())
        self.assertEqual(page.evaluate("App.profil.type"), "responsable")
        self.assertEqual(page.evaluate("location.hash"), "#/apropos")

    def test_telephone_375_px_technicien_sans_equipe_acces(self):
        page = self.page
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(self.serveur.url + "/#/accueil")
        self.attendre_etat("connexion")
        self.sans_defilement_horizontal("écran de connexion")
        self.assertGreaterEqual(page.evaluate(HAUTEUR_MIN_JS % ZONES_TACTILES), 48)
        self.connecter("julien.moreau")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.profil"), {"type": "technicien", "nom": "Julien Moreau", "technicienId": "TEC-0001"})
        self.assertTrue(page.evaluate("App.estTechnicien() && !App.estResponsable()"))
        self.assertEqual(page.inner_text("#libelle-profil").strip(), "Julien Moreau · Technicien")
        self.sans_defilement_horizontal("accueil")
        self.assertEqual(page.get_attribute("#btn-profil-mobile", "aria-label"), "Se déconnecter")
        # Ni le bouton « Accès » de l'écran Équipe, ni l'écran (renvoyé à l'accueil).
        page.evaluate("location.hash = '#/equipe'")
        page.wait_for_selector("#contenu h1:has-text('Équipe')")
        self.assertEqual(page.locator("#equipe-acces").count(), 0)
        page.evaluate("location.hash = '#/equipe/acces'")
        page.wait_for_function("location.hash === '#/accueil'")
        self.assertEqual(page.locator("#acces-contenu").count(), 0)
        self.assertNotIn("Paramètres", page.evaluate("document.getElementById('menu').innerText"))

    def test_mot_de_passe_provisoire_change_avant_tout(self):
        page = self.page
        self.autoriser_erreur(ERREUR_403_MOT_DE_PASSE)
        self.autoriser_erreur(motif_refus_du_demandeur())
        statut, cree = self.api("POST", "/api/acces/comptes", {"prenom": "Zoé", "nom": "Durand", "role": "demandeur"})
        self.assertEqual(statut, 200, cree)
        provisoire = cree["mot_de_passe_provisoire"]
        self.assertEqual(cree["compte"]["identifiant"], "zoe.durand")
        page.goto(self.serveur.url + "/")
        self.attendre_etat("connexion")
        self.connecter("zoe.durand", provisoire)
        page.wait_for_selector("#connexion-mot-de-passe-panneau", state="visible")
        self.assertEqual(page.evaluate("document.documentElement.dataset.etat"), "connexion")
        self.assertTrue(page.is_hidden("#connexion-formulaire"))
        self.assertIn("Choisissez votre mot de passe", page.inner_text("#connexion-titre"))
        self.assertIn("12 caractères au moins", page.inner_text("#connexion-mot-de-passe-panneau"))
        self.assertEqual(page.input_value("#connexion-mot-de-passe"), "")
        # Trop court (règle du serveur, vérifiée avant l'envoi).
        page.fill("#connexion-actuel", provisoire)
        page.fill("#connexion-nouveau", "court123")
        page.fill("#connexion-confirmation", "court123")
        page.click("#connexion-changer")
        page.wait_for_selector("#connexion-mdp-erreur", state="visible")
        self.assertIn("12 caractères", page.inner_text("#connexion-mdp-erreur"))
        self.assertIn("trop court", page.inner_text("#connexion-force"))
        # Confirmation différente.
        page.fill("#connexion-nouveau", NOUVEAU_MOT_DE_PASSE)
        page.fill("#connexion-confirmation", "une autre phrase de passe")
        page.click("#connexion-changer")
        page.wait_for_function("document.getElementById('connexion-mdp-erreur').textContent.includes('confirmation')")
        # Mot de passe actuel faux : le message du serveur (403).
        page.fill("#connexion-actuel", "pas le provisoire du tout")
        page.fill("#connexion-confirmation", NOUVEAU_MOT_DE_PASSE)
        page.click("#connexion-changer")
        page.wait_for_function("document.getElementById('connexion-mdp-erreur').textContent.includes('Mot de passe actuel incorrect.')")
        self.assertEqual(page.input_value("#connexion-actuel"), "")                          # champs vidés à chaque réponse
        self.assertTrue(self.session_du_navigateur()["session"]["a_changer"])
        # Le bon : session neuve, application ouverte en demandeur « Zoé Durand ».
        page.fill("#connexion-actuel", provisoire)
        page.fill("#connexion-nouveau", NOUVEAU_MOT_DE_PASSE)
        page.fill("#connexion-confirmation", NOUVEAU_MOT_DE_PASSE)
        page.click("#connexion-changer")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.profil"), {"type": "demandeur", "nom": "Zoé Durand", "technicienId": ""})
        self.assertFalse(page.evaluate("App.session.aChanger"))
        self.assertFalse(self.session_du_navigateur()["session"]["a_changer"])
        self.assertNotIn("Ordres de travail", page.inner_text("#menu"))
        contenu = page.content()
        self.assertNotIn(provisoire, contenu)
        self.assertNotIn(NOUVEAU_MOT_DE_PASSE, contenu)
        # Le provisoire ne vaut plus, le nouveau ouvre une session.
        self.assertEqual(self.connexion_api("zoe.durand", provisoire), 401)
        self.assertEqual(self.connexion_api("zoe.durand", NOUVEAU_MOT_DE_PASSE), 200)

    def connexion_api(self, identifiant, mot_de_passe):
        return requete(self.serveur.url, "POST", "/api/connexion",
                       {"identifiant": identifiant, "mot_de_passe": mot_de_passe, "rester": False})[0]

    def test_appareil_enrole_par_le_lien_puis_revoque(self):
        page = self.page
        self.autoriser_erreur(motif_refus_du_demandeur())
        self.autoriser_erreur(ERREUR_401_TABLES)
        statut, invitation = self.api("POST", "/api/acces/invitations", {})
        self.assertEqual(statut, 200, invitation)
        self.assertRegex(invitation["chemin"], r"^/#/enroler/[A-Za-z0-9_-]{43}$")
        page.goto(self.serveur.url + invitation["chemin"])
        self.attendre_etat("connexion")
        self.assertTrue(page.is_visible("#connexion-enrolement"))
        self.assertTrue(page.is_hidden("#connexion-formulaire"))
        self.assertIn("Entrez votre nom", page.inner_text("#connexion-enrolement"))
        page.click("#connexion-enroler")
        page.wait_for_selector("#connexion-enrolement-erreur", state="visible")
        self.assertIn("Indiquez votre nom", page.inner_text("#connexion-enrolement-erreur"))
        page.fill("#connexion-nom", "  Karim   Benali ")
        page.click("#connexion-enroler")
        attendre_pret(page)
        self.assertEqual(page.evaluate("location.hash"), "#/accueil")
        self.assertEqual(page.evaluate("App.profil"), {"type": "demandeur", "nom": "Karim Benali", "technicienId": ""})
        self.assertTrue(page.evaluate("App.session.appareil"))
        self.assertEqual(page.inner_text("#libelle-profil").strip(), "Karim Benali · Demandeur")
        self.assertTrue(page.is_hidden("#etat-poste .changer"))                 # pas de « se déconnecter » pour un appareil
        self.assertTrue(page.is_disabled("#etat-poste"))
        self.assertTrue(page.is_hidden("#btn-profil-mobile"))
        session = self.session_du_navigateur()["session"]
        self.assertEqual((session["appareil"], session["nom"], session["role"]), (True, "Karim Benali", "demandeur"))
        self.assertNotIn("profil", self.etats())
        # Rechargement : l'appareil est reconnu par son cookie, aucun écran de connexion.
        page.reload()
        attendre_pret(page)
        self.assertNotIn("connexion", self.etats())
        self.assertEqual(page.evaluate("App.profil.nom"), "Karim Benali")
        # Révoqué par le responsable : la requête suivante (401 appareil_refuse) ramène l'écran de connexion avec le bandeau.
        statut, liste = self.api("GET", "/api/acces/invitations")
        appareils = [a for a in liste["appareils"] if a["nom_demandeur"] == "Karim Benali"]
        self.assertEqual(len(appareils), 1)
        statut, _ = self.api("POST", "/api/acces/appareils/%s/revoquer" % appareils[0]["id"], {})
        self.assertEqual(statut, 200)
        page.evaluate("App.adaptateur.listerVersions().catch(() => null)")
        self.attendre_etat("connexion")
        page.wait_for_selector("#connexion-appareil-refuse", state="visible")
        self.assertIn("n'est plus autorisé", page.inner_text("#connexion-appareil-refuse"))
        self.assertTrue(page.is_visible("#connexion-formulaire"))
        self.assertIsNone(self.session_du_navigateur()["session"])
        # Le cookie d'appareil a été effacé par le serveur : un compte peut se connecter depuis ce navigateur.
        self.connecter("nicolas.briand")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.profil.type"), "responsable")
        self.assertFalse(page.evaluate("App.session.appareil"))
        self.assertTrue(page.is_visible("#etat-poste .changer"))

    def test_deconnexion_puis_session_fermee_ailleurs_route_gardee(self):
        page = self.page
        self.autoriser_erreur(ERREUR_401_TABLES)
        page.goto(self.serveur.url + "/#/parc")
        self.attendre_etat("connexion")
        self.connecter("nicolas.briand")
        attendre_pret(page)
        self.assertEqual(page.evaluate("location.hash"), "#/parc")
        page.wait_for_selector("#contenu h1:has-text('Parc')")
        # Déconnexion par le bouton du menu : session fermée sur le serveur, écran de connexion, route gardée.
        page.click("#etat-poste")
        self.attendre_etat("connexion")
        self.assertIsNone(self.session_du_navigateur()["session"])
        self.assertEqual(page.evaluate("location.hash"), "#/parc")
        self.assertTrue(page.is_hidden("#app"))
        self.connecter("nicolas.briand")
        attendre_pret(page)
        self.assertEqual(page.evaluate("location.hash"), "#/parc")
        page.wait_for_selector("#contenu h1:has-text('Parc')")
        # Session fermée ailleurs (« déconnecter partout ») : le 401 de la requête suivante est relu par App
        # (événement prevo:session-absente) → écran de connexion par-dessus, sans perdre la route.
        statut, resultat = self.api("POST", "/api/acces/deconnecter-partout", {"identifiant": "nicolas.briand"})
        self.assertEqual(statut, 200, resultat)
        self.assertGreaterEqual(resultat["sessions_fermees"], 2)
        page.evaluate("App.adaptateur.listerVersions().catch(() => null)")
        self.attendre_etat("connexion")
        page.wait_for_selector("#connexion-motif", state="visible")
        self.assertIn("Connexion nécessaire", page.inner_text("#connexion-motif"))
        self.assertEqual(page.evaluate("location.hash"), "#/parc")
        self.connecter("julien.moreau")                                           # une autre personne, même route
        attendre_pret(page)
        self.assertEqual(page.evaluate("location.hash"), "#/parc")
        page.wait_for_selector("#contenu h1:has-text('Parc')")
        self.assertEqual(page.evaluate("App.profil.technicienId"), "TEC-0001")
        self.assertEqual(page.inner_text("#libelle-profil").strip(), "Julien Moreau · Technicien")
        self.assertEqual(self.session_du_navigateur()["session"]["identifiant"], "julien.moreau")


class TestAutresServeurs(CasNavigateur):

    def test_enrolement_desactive_message_et_champs_classiques(self):
        page = self.page
        self.autoriser_erreur(ERREUR_401_SONDE)
        self.autoriser_erreur(ERREUR_403_ENROLER)
        with ServeurPrevo(comptes=True, reglages={"demandeurs_avec_compte": True}) as serveur:
            page.goto(serveur.url + "/#/enroler/" + "x" * 43)
            page.wait_for_function("document.documentElement.dataset.etat === 'connexion'")
            page.wait_for_selector("#connexion-enrolement", state="visible")
            page.fill("#connexion-nom", "Karim Benali")
            page.click("#connexion-enroler")
            page.wait_for_selector("#connexion-formulaire", state="visible")
            self.assertTrue(page.is_hidden("#connexion-enrolement"))
            self.assertIn("désactivé", page.inner_text("#connexion-erreur"))
            self.connecter_depuis(page, serveur, "lea.martin")
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.profil"), {"type": "demandeur", "nom": "Léa Martin", "technicienId": ""})
            self.assertEqual(page.evaluate("location.hash"), "#/accueil")

    def connecter_depuis(self, page, serveur, identifiant):
        self.autoriser_erreur(motif_refus_du_demandeur())
        page.fill("#connexion-identifiant", identifiant)
        page.fill("#connexion-mot-de-passe", MOTS_DE_PASSE[identifiant])
        page.click("#connexion-valider")

    def test_connexion_dans_la_langue_d_une_installation_en_anglais(self):
        """T297 : langue_defaut = en ; appareil neuf (navigateur fr-FR, rien de retenu) : écran en anglais d'emblée."""
        page = self.page
        self.autoriser_erreur(ERREUR_401_SONDE)
        page.add_init_script(SUIVI_ETATS_JS)
        with ServeurPrevo(comptes=True) as serveur:
            with open(serveur.dossier / "parametres.csv", "ab") as fichier:
                fichier.write(b"langue_defaut;en\r\n")
            page.goto(serveur.url + "/")
            page.wait_for_function("document.documentElement.dataset.etat === 'connexion'")
            self.assertEqual(page.evaluate("[document.documentElement.dataset.langueInstallation, I18n.langue, "
                                           "document.documentElement.lang]"), ["en", "en", "en"])
            self.assertEqual(page.inner_text("#connexion-valider").strip(),
                             texte_du_dictionnaire("en", "socle.connexion_valider.connecter"))
            self.assertEqual(page.evaluate("document.getElementById('connexion-langue-liste').value"), "en")
            self.assertEqual(page.evaluate("window.__etats.filter((etat) => etat === 'connexion').length"), 1)
            # Français choisi : retenu (il diffère de l'installation), gardé au rechargement.
            with page.expect_navigation():
                page.select_option("#connexion-langue-liste", "fr")
            page.wait_for_function("document.documentElement.dataset.etat === 'connexion'")
            self.assertEqual(page.inner_text("#connexion-valider").strip(),
                             texte_du_dictionnaire("fr", "socle.connexion_valider.connecter"))
            self.assertEqual(page.evaluate("localStorage.getItem('prevo.langue')"), "fr")
            page.reload()
            page.wait_for_function("document.documentElement.dataset.etat === 'connexion'")
            self.assertEqual(page.evaluate("I18n.langue"), "fr")

    def test_sans_comptes_ecran_de_profil_comme_avant(self):
        page = self.page
        page.add_init_script(SUIVI_ETATS_JS)
        with ServeurPrevo() as serveur:
            page.goto(serveur.url + "/")
            page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
            self.assertTrue(page.is_hidden("#ecran-connexion"))
            self.assertFalse(page.evaluate("App.comptesExiges()"))
            page.click("#profil-responsable")
            attendre_pret(page)
            self.assertNotIn("connexion", page.evaluate("window.__etats"))
            self.assertIsNone(page.evaluate("App.session"))
            self.assertEqual(page.evaluate("JSON.parse(localStorage.getItem('prevo.profil')).type"), "responsable")
            self.assertIn("Responsable ·", page.inner_text("#libelle-profil"))
            self.assertEqual(page.inner_text("#etat-poste .changer").strip(), "changer")
            page.evaluate("location.hash = '#/apropos'")
            page.wait_for_function("document.querySelector('#contenu h1') && document.querySelector('#contenu h1').textContent.includes('À propos')")
            self.assertIn("ce n'est pas une sécurité", page.inner_text("#contenu"))


if __name__ == "__main__":
    unittest.main()
