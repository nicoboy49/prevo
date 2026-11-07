"""Lot 7 — porte d'entrée et https sur deux écouteurs (ARCHITECTURE.md §22.1, §22.6, §22.13 ; D127 ; CS125, CS137 ;
tâche T161).

Ce qui est vérifié, avec un serveur réel en portée « atelier » (tests/atelier.py : écoute sur 0.0.0.0, comptes,
certificat de test du faux mkcert ; le téléphone simulé se connecte à l'adresse réseau du PC, le PC à 127.0.0.1) :
    porte          sur port_http, un client du réseau reçoit la page de porte (200, sans donnée) pour toute adresse,
                   /api/csv/…, index.html, js/, GUIDE.html et /api/ping compris ; un PUT ou un POST n'est jamais lu ;
                   la page porte le port https de ce serveur (data-port-https) et sa propre politique (connect-src vers
                   l'origine https du même hôte, rien d'autre au dehors) ; elle ne sert que ses fichiers (acces/,
                   favicon, polices) ;
    ca.crt         /acces/ca.crt sert le certificat public de l'autorité (type x-x509-ca-cert, téléchargement), par la
                   porte comme par l'application ; rootCA-key.pem n'est servi par aucune adresse ; 404 clair sans
                   autorité locale ;
    PC             le PC serveur (127.0.0.1) reçoit l'application en http sur port_http ; /api/info donne l'adresse de
                   la porte (http://<ip>:<port_http>/) ; l'application en https porte les en-têtes de §22.13, les
                   documents gardent « sandbox » ; la console donne la porte, jamais l'adresse https ;
    mkcert         câblage de main : certificat_du_serveur prend le certificat donné, sinon celui que mkcert fabrique
                   (drapeau _https_auto pour les règles de portée) ; mkcert absent ⇒ démarrage refusé, code 2, aucun
                   écouteur ; avec le faux mkcert, main ouvre la porte et l'application et le dit ;
    navigateur     (Playwright) un navigateur qui fait confiance à l'autorité est redirigé vers
                   https://…:<port_https>/#/<route> en gardant la route (fiche d'une étiquette, lien d'invitation), et
                   un appareil enrôlé y ouvre l'application en contexte sécurisé ; un navigateur qui ne fait pas
                   confiance voit « Faites confiance au PC atelier » : profil Android (Pixel 7) → étapes Android
                   numérotées avec leurs illustrations, profil iPhone (iPhone 14) → étapes iPhone, autre → choix ;
                   « Réessayer » relance l'essai ; lisible à 390 px sans défilement horizontal ;
    adresses       QR de l'accueil et étiquettes sur l'adresse de la porte ; aucune adresse https:<port> ni https://<ip>
                   dans les textes servis (index.html, js/, css/, acces/) ni dans GUIDE.html ;
    langue         (T297) fichiers servis sans session : ceux d'avant et UN de plus, js/i18n-chargeur.js (rien d'autre de
                   js/) ; data-langue-installation posé dans la porte (langue_defaut déclarée, sinon « fr ») et dans
                   index.html (langue_defaut déclarée seulement) ; une valeur non déclarée, mal formée ou piégée : « fr »
                   à la porte, rien dans index.html ; navigateur : porte en français (installation fr) et en anglais
                   (installation en) ; sélecteur en haut, visible sans menu (globe, langues écrites dans leur langue,
                   aucun autre mot), il change la langue et le choix tient au rechargement ; la langue de
                   l'installation choisie retire le choix ; valeur abîmée gardée par le téléphone : français, sans erreur.
Aucune commande d'administrateur, aucune sortie du PC (le faux mkcert ne touche pas au magasin de certificats).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_acces_porte.py" -v
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, port_libre, preregler_profil
from atelier import (FAUX_MKCERT, ServeurAtelier, adresse_reseau, charger_serveur, comptes_json, connecter,
                     enroler_appareil, motif_refus_du_demandeur, openssl_present, requete)

serveur = charger_serveur("serveur_prevo_porte")

PAGE_PORTE = RACINE / "acces" / "porte.html"
TITRE_PORTE = "Faites confiance au PC atelier"
CLE_TITRE_PORTE = "porte.confiance.faites_confiance_pc_atelier"
MOTIF_LANGUE_DE_LA_PAGE = re.compile(r'data-langue-installation="([^"]*)"')
# Sélecteur de langue de la porte (T297) : options, valeur, texte de la zone hors de la liste, étiquette accessible.
SELECTEUR_PORTE_JS = """() => {
  const zone = document.getElementById('choix-langue');
  const liste = document.getElementById('langue-liste');
  const autour = [...zone.childNodes].filter((n) => n !== liste).map((n) => n.textContent).join('').trim();
  return { visible: !zone.hidden, options: [...liste.options].map((o) => [o.value, o.textContent, o.lang]),
    valeur: liste.value, autour, etiquette: liste.getAttribute('aria-label'), lang: document.documentElement.lang,
    globe: Boolean(zone.querySelector('svg[aria-hidden="true"]')) };
}"""
MOTIF_ADRESSE_HTTPS_IP = re.compile(r"https://(?:\d{1,3}\.){3}\d{1,3}")
MOTIF_ADRESSE_HTTPS_PORT = re.compile(r"https://[^\s\"'<>()]*:8443")


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


def poser_langue_defaut(cas, dossier, valeur):
    """langue_defaut = valeur ajoutée à parametres.csv du serveur (lu à chaque page servie) ; remis comme avant à la
    fin du test."""
    chemin = Path(dossier) / "parametres.csv"
    avant = chemin.read_bytes()
    cas.addCleanup(chemin.write_bytes, avant)
    base = avant if avant.endswith(b"\n") else avant + b"\r\n"
    chemin.write_bytes(base + ("langue_defaut;%s\r\n" % valeur).encode("utf-8"))


def captures_de_la_page():
    """Chemins des illustrations référencées par acces/porte.html, dans l'ordre."""
    return re.findall(r'src="(/acces/captures/[^"]+)"', PAGE_PORTE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Serveur réel en portée « atelier » : porte, ca.crt, PC, application en https
# ---------------------------------------------------------------------------

class CasAtelier(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.atelier = ServeurAtelier()
        cls.atelier.demarrer()
        cls.addClassCleanup(cls.atelier.arreter)

    def reseau(self, chemin, **options):
        return requete(self.atelier.url_porte, chemin, **options)

    def pc(self, chemin, **options):
        return requete(self.atelier.url_pc, chemin, **options)

    def https(self, chemin, **options):
        return requete(self.atelier.url_https, chemin, contexte=self.atelier.contexte_confiance, **options)

    def verifier_page_de_porte(self, reponse, chemin):
        self.assertEqual(reponse.statut, 200, chemin)
        self.assertTrue(reponse.entetes["content-type"].startswith("text/html"), chemin)
        self.assertIn(TITRE_PORTE, reponse.texte, chemin)
        self.assertIn('data-port-https="%d"' % self.atelier.port_https, reponse.texte, chemin)
        self.assertNotIn("Prévo — GMAO", reponse.texte, chemin)              # jamais index.html
        self.assertNotIn("id;", reponse.texte, chemin)                       # jamais un CSV
        self.assertNotIn("sauvegardes", reponse.texte, chemin)
        politique = reponse.entetes["content-security-policy"]
        self.assertEqual(politique, serveur.POLITIQUE_PORTE % self.atelier.url_https)
        self.assertEqual(reponse.entetes["x-frame-options"], "DENY")
        self.assertEqual(reponse.entetes["referrer-policy"], "no-referrer")
        self.assertIn("camera=(self)", reponse.entetes["permissions-policy"])
        self.assertNotIn("strict-transport-security", reponse.entetes)


class TestPorte(CasAtelier):

    def test_un_client_du_reseau_recoit_la_page_de_porte_pour_toute_adresse(self):
        for chemin in ("/", "/index.html", "/api/csv/equipements", "/api/ping", "/api/info", "/api/versions",
                       "/js/app.js", "/css/style.css", "/GUIDE.html", "/api/documents/photo.jpg",
                       "/api/sauvegardes", "/inexistant", "/acces/porte.html"):
            with self.subTest(chemin=chemin):
                self.verifier_page_de_porte(self.reseau(chemin), chemin)

    def test_un_envoi_depuis_le_reseau_n_est_jamais_lu(self):
        chemin = self.atelier.dossier / "equipements.csv"
        avant = chemin.read_bytes()
        # T187 : le démarrage a déjà fait ses sauvegardes (du jour, « avant-mise-a-jour ») ; aucune de plus ensuite.
        sauvegardes_avant = sorted(p.name for p in (self.atelier.dossier / "sauvegardes").iterdir())
        for methode, adresse in (("POST", "/api/connexion"), ("PUT", "/api/csv/equipements"), ("POST", "/api/sauvegarde"),
                                 ("PUT", "/api/documents/essai.txt")):
            with self.subTest(methode=methode, adresse=adresse):
                reponse = self.reseau(adresse, methode=methode, corps=b"id;repere\r\nEQ-9999;Pirate\r\n",
                                      entetes={"X-Prevo": "1", "Content-Type": "text/csv"})
                self.verifier_page_de_porte(reponse, adresse)
                self.assertEqual(reponse.entetes.get("connection"), "close")
        self.assertEqual(chemin.read_bytes(), avant)
        self.assertFalse((self.atelier.dossier / "documents" / "essai.txt").exists())
        self.assertEqual(sorted(p.name for p in (self.atelier.dossier / "sauvegardes").iterdir()), sauvegardes_avant)

    def test_la_porte_sert_ses_fichiers_et_rien_de_l_application(self):
        attendus = {"/acces/porte.js": ("text/javascript", b"Porte"), "/acces/porte.css": ("text/css", b"Sora"),
                    "/favicon.svg": ("image/svg+xml", b"<svg"),
                    "/css/polices/sora-latin-wght-normal.woff2": ("font/woff2", b"wOF2")}
        captures = captures_de_la_page()
        self.assertGreaterEqual(len(captures), 10)
        for capture in captures:
            attendus[capture] = ("image/svg+xml", b"<svg")
        for chemin, (type_attendu, debut) in attendus.items():
            with self.subTest(chemin=chemin):
                reponse = self.reseau(chemin)
                self.assertEqual(reponse.statut, 200)
                self.assertTrue(reponse.entetes["content-type"].startswith(type_attendu), reponse.entetes["content-type"])
                self.assertTrue(reponse.octets.startswith(debut) or debut in reponse.octets[:200])
                self.assertEqual(reponse.entetes["content-security-policy"], serveur.POLITIQUE_PORTE % self.atelier.url_https)
        # Sur le disque, la page attend son port : l'attribut vide, une seule fois.
        self.assertEqual(PAGE_PORTE.read_text(encoding="utf-8").count(serveur.ATTRIBUT_PORT_HTTPS), 1)

    def test_ca_crt_sert_le_certificat_de_l_autorite_et_jamais_sa_cle(self):
        attendu = self.atelier.rootca.read_bytes()
        self.assertIn(b"BEGIN CERTIFICATE", attendu)
        for nom, lire in (("réseau", self.reseau), ("PC", self.pc), ("https", self.https)):
            with self.subTest(client=nom):
                reponse = lire("/acces/ca.crt")
                self.assertEqual(reponse.statut, 200)
                self.assertEqual(reponse.entetes["content-type"], "application/x-x509-ca-cert")
                self.assertEqual(reponse.entetes["content-disposition"], 'attachment; filename="prevo-ca.crt"')
                self.assertEqual(reponse.octets, attendu)
                self.assertNotIn(b"PRIVATE KEY", reponse.octets)
        cle = (self.atelier.dossier / "acces" / "autorite" / "rootCA-key.pem").read_bytes()
        self.assertIn(b"PRIVATE KEY", cle)
        for chemin in ("/acces/rootCA-key.pem", "/acces/autorite/rootCA-key.pem", "/donnees/acces/autorite/rootCA-key.pem",
                       "/acces/ca.key", "/acces/cle.pem", "/acces/certificat.pem"):
            for nom, lire in (("réseau", self.reseau), ("PC", self.pc), ("https", self.https)):
                with self.subTest(chemin=chemin, client=nom):
                    reponse = lire(chemin)
                    self.assertNotIn(b"PRIVATE KEY", reponse.octets)
                    self.assertNotEqual(reponse.octets, cle)
                    if nom == "réseau":
                        self.verifier_page_de_porte(reponse, chemin)
                    else:
                        self.assertIn(reponse.statut, (403, 404))

    def test_la_porte_sert_le_chargeur_de_langue_et_rien_d_autre_de_js(self):
        """T297 : un seul fichier de plus sans session, le chargeur de la langue (texte public, aucune donnée)."""
        reponse = self.reseau("/js/i18n-chargeur.js")
        self.assertEqual(reponse.statut, 200)
        self.assertTrue(reponse.entetes["content-type"].startswith("text/javascript"))
        self.assertEqual(reponse.octets, (RACINE / "js" / "i18n-chargeur.js").read_bytes())
        self.assertEqual(reponse.entetes["content-security-policy"], serveur.POLITIQUE_PORTE % self.atelier.url_https)
        for chemin in ("/js/app.js", "/js/interface.js", "/js/schema.js", "/js/stockage-serveur.js",
                       "/js/i18n-chargeur.js.bak", "/js/modules/connexion-ecrans.js", "/css/style.css"):
            with self.subTest(chemin=chemin):
                self.verifier_page_de_porte(self.reseau(chemin), chemin)

    def test_langue_de_l_installation_posee_dans_la_porte_et_dans_index(self):
        """T297 : data-langue-installation, toujours une langue déclarée et bien formée (rien d'autre n'entre)."""
        self.assertEqual(MOTIF_LANGUE_DE_LA_PAGE.findall(self.reseau("/").texte), ["fr"])       # sans réglage : fr
        self.assertEqual(MOTIF_LANGUE_DE_LA_PAGE.findall(self.pc("/").texte), [""])             # index : rien
        self.assertEqual(MOTIF_LANGUE_DE_LA_PAGE.findall(self.https("/").texte), [""])
        cas = (("en", "en", "en"), ("fr", "fr", "fr"), ("de", "fr", ""), ("EN", "fr", ""),
               ('x"><script>alert(1)</script>', "fr", ""), ("en-GB", "fr", ""))
        parametres = self.atelier.dossier / "parametres.csv"
        avant = parametres.read_bytes()
        self.addCleanup(parametres.write_bytes, avant)
        for valeur, porte, index in cas:
            with self.subTest(langue_defaut=valeur):
                parametres.write_bytes(avant + ("langue_defaut;%s\r\n" % valeur).encode("utf-8"))
                page = self.reseau("/inexistant").texte
                self.assertEqual(MOTIF_LANGUE_DE_LA_PAGE.findall(page), [porte])
                self.assertNotIn("<script>alert", page)
                self.assertEqual(MOTIF_LANGUE_DE_LA_PAGE.findall(self.pc("/").texte), [index])
                self.assertEqual(MOTIF_LANGUE_DE_LA_PAGE.findall(self.pc("/index.html").texte), [index])
        # parametres.csv illisible (un dossier à sa place) : la porte est servie quand même, en français.
        parametres.unlink()
        parametres.mkdir()
        self.addCleanup(parametres.rmdir)
        self.assertEqual(MOTIF_LANGUE_DE_LA_PAGE.findall(self.reseau("/").texte), ["fr"])
        self.assertEqual(self.pc("/").statut, 200)

    def test_sans_autorite_locale_ca_crt_repond_404_clair(self):
        with ServeurPrevo() as ce_pc:
            reponse = requete(ce_pc.url, "/acces/ca.crt")
            self.assertEqual(reponse.statut, 404)
            self.assertEqual(reponse.json()["erreur"], serveur.MESSAGE_SANS_AUTORITE)
            self.assertIn("informaticien", reponse.json()["erreur"])
            # Et la porte reste servie à ce PC comme un fichier public (rien de privé dedans).
            self.assertEqual(requete(ce_pc.url, "/acces/porte.js").statut, 200)


class TestPcEtApplication(CasAtelier):

    def test_le_pc_sur_la_porte_recoit_l_application_en_http(self):
        accueil = self.pc("/")
        self.assertEqual(accueil.statut, 200)
        self.assertIn("Prévo — GMAO", accueil.texte)
        self.assertNotIn(TITRE_PORTE, accueil.texte)
        self.assertIn("connect-src 'self' https://prevo.pro", accueil.entetes["content-security-policy"])
        self.assertEqual(accueil.entetes["x-frame-options"], "DENY")
        self.assertNotIn("strict-transport-security", accueil.entetes)
        self.assertEqual(self.pc("/api/ping").json()["application"], "Prévo")
        session = connecter(self.atelier.url_pc, "nicolas.briand")
        self.assertNotIn("Secure", session.entetes["set-cookie"])              # http sur ce PC : contexte sécurisé
        info = self.pc("/api/info", cookie=session.cookie).json()
        self.assertEqual(info["port"], self.atelier.port_http)
        self.assertEqual(info["adresse_locale"], "http://localhost:%d/" % self.atelier.port_http)
        self.assertIn(self.atelier.url_porte + "/", info["adresses_reseau"])
        for adresse in info["adresses_reseau"]:
            self.assertRegex(adresse, r"^http://[0-9.]+:%d/$" % self.atelier.port_http)
            self.assertNotIn(":%d" % self.atelier.port_https, adresse)
        # Les données, elles, ne sortent que par l'application : la porte (réseau) ne les sert pas.
        self.assertEqual(self.pc("/api/csv/equipements", cookie=session.cookie).statut, 200)
        self.verifier_page_de_porte(self.reseau("/api/csv/equipements", cookie=session.cookie), "réseau avec cookie")

    def test_l_application_en_https_entetes_documents_et_adresses(self):
        self.assertEqual(self.https("/api/ping").json()["application"], "Prévo")
        index = self.https("/")
        self.assertEqual(index.statut, 200)
        self.assertIn("Prévo — GMAO", index.texte)
        self.assertIn("script-src 'self';", index.entetes["content-security-policy"])
        self.assertEqual(index.entetes["x-frame-options"], "DENY")
        self.assertEqual(index.entetes["referrer-policy"], "no-referrer")
        self.assertEqual(index.entetes["permissions-policy"], "camera=(self), microphone=(self), geolocation=()")
        self.assertNotIn("strict-transport-security", index.entetes)        # adresse IP : jamais de HSTS
        session = connecter(self.atelier.url_https, "nicolas.briand", self.atelier.contexte_confiance)
        self.assertIn("Secure", session.entetes["set-cookie"])
        info = self.https("/api/info", cookie=session.cookie).json()
        self.assertEqual(info["adresses_reseau"], self.pc("/api/info", cookie=connecter(self.atelier.url_pc, "nicolas.briand").cookie).json()["adresses_reseau"])
        self.assertTrue(all(a.startswith("http://") for a in info["adresses_reseau"]))
        (self.atelier.dossier / "documents" / "essai-porte.pdf").write_bytes(b"%PDF-1.4\n%essai\n")
        document = self.https("/api/documents/essai-porte.pdf", cookie=session.cookie)
        self.assertEqual(document.statut, 200)
        self.assertEqual(document.entetes["content-security-policy"], "sandbox")
        self.assertNotIn("x-frame-options", document.entetes)
        # Sans session, l'API de l'application refuse (401) : les comptes sont exigés hors de « ce PC ».
        self.assertEqual(self.https("/api/csv/equipements").statut, 401)

    def test_la_console_donne_la_porte_jamais_l_adresse_https(self):
        console = self.atelier.console()
        self.assertIn("Sur le réseau    : %s/" % self.atelier.url_porte, console)
        self.assertIn("Sur ce PC        : http://localhost:%d/" % self.atelier.port_http, console)
        self.assertIn("Application      : en https sur le port %d" % self.atelier.port_https, console)
        self.assertNotIn("https://", console)


# ---------------------------------------------------------------------------
# Câblage de mkcert dans main (serveur importé dans ce processus, faux mkcert)
# ---------------------------------------------------------------------------

class TestCablageMkcert(unittest.TestCase):

    def setUp(self):
        if not openssl_present():
            self.skipTest("openssl introuvable : faux mkcert impossible")
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-porte-main-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        self.donnees = self.dossier / "donnees"
        (self.donnees / "acces").mkdir(parents=True)
        (self.donnees / "acces" / "comptes.json").write_bytes(comptes_json())
        self.faux = self.dossier / "faux_mkcert.py"
        shutil.copy(FAUX_MKCERT, self.faux)
        self.console = []
        espion = mock.patch.object(serveur, "afficher", side_effect=self.console.append)
        espion.start()
        self.addCleanup(espion.stop)

    def configuration(self, **reglages):
        chemin = self.dossier / "prevo.config.json"
        chemin.write_text(json.dumps(reglages), encoding="utf-8")
        return chemin

    def arguments(self, configuration, port=None, *supplement):
        return ["--sans-navigateur", "--donnees", str(self.donnees), "--config", str(configuration),
                "--port", str(port or port_libre())] + list(supplement)

    def lancements(self):
        journal = Path(serveur.dossier_autorite(self.config)) / "lancements.txt"
        return journal.read_text(encoding="utf-8").splitlines() if journal.is_file() else []

    def test_certificat_du_serveur_et_drapeau_https_auto(self):
        configuration = self.configuration(ecoute="0.0.0.0", comptes=True)
        reglages = serveur.reglages_du_lancement(serveur.lire_arguments(self.arguments(configuration)))
        self.assertTrue(reglages["_https_auto"])
        self.assertEqual(serveur.verifier_regles_portee(reglages, True), [])
        self.config = serveur.Configuration(str(self.donnees), [])
        self.config.reglages = reglages
        certificat, cle = serveur.certificat_du_serveur(self.config, reglages, mkcert=str(self.faux))
        self.assertEqual(Path(certificat), self.donnees / "acces" / "certificat.pem")
        self.assertTrue(Path(cle).is_file())
        self.assertEqual(len(self.lancements()), 1)
        # Certificat donné : pris tel quel, mkcert jamais lancé, drapeau faux.
        donne = serveur.reglages_du_lancement(serveur.lire_arguments(
            self.arguments(configuration, None, "--certificat", certificat, "--cle", cle)))
        self.assertFalse(donne["_https_auto"])
        self.assertEqual(serveur.certificat_du_serveur(self.config, donne, mkcert=str(self.faux)), (certificat, cle))
        self.assertEqual(len(self.lancements()), 1)
        # Ce PC : rien ; réseau sans certificat_auto : refus qui parle de https.
        ce_pc = serveur.reglages_du_lancement(serveur.lire_arguments(self.arguments(self.configuration())))
        self.assertEqual(serveur.certificat_du_serveur(self.config, ce_pc, mkcert=str(self.faux)), (None, None))
        sans = dict(reglages, certificat_auto=False, _https_auto=False)
        with self.assertRaises(serveur.ErreurConfiguration) as refus:
            serveur.certificat_du_serveur(self.config, sans, mkcert=str(self.faux))
        self.assertIn("https", str(refus.exception))

    def test_main_refuse_de_demarrer_sans_mkcert_code_2_et_aucun_ecouteur(self):
        configuration = self.configuration(ecoute="0.0.0.0", comptes=True)
        with mock.patch.object(serveur, "trouver_mkcert", side_effect=serveur.ErreurConfiguration("Outil introuvable : mkcert.")), \
                mock.patch.object(serveur, "ServeurPrevo") as ecouteur:
            with self.assertRaises(SystemExit) as fin:
                serveur.main(self.arguments(configuration))
        self.assertEqual(fin.exception.code, serveur.CODE_SORTIE_REGLES)
        texte = "\n".join(self.console)
        self.assertIn("Démarrage refusé", texte)
        self.assertIn("mkcert", texte)
        self.assertIn("https", texte)
        self.assertIn("Outil introuvable", texte)
        ecouteur.assert_not_called()

    def test_main_ouvre_la_porte_et_l_application_avec_le_certificat_de_mkcert(self):
        port_http, port_https = port_libre(), port_libre()
        configuration = self.configuration(ecoute="0.0.0.0", comptes=True, port_https=port_https)
        with mock.patch.object(serveur, "trouver_mkcert", return_value=str(self.faux)), \
                mock.patch.object(serveur.ServeurPrevo, "serve_forever", return_value=None), \
                mock.patch.object(serveur, "lancer_copie_externe"):
            serveur.main(self.arguments(configuration, port_http))
        texte = "\n".join(self.console)
        ip = adresse_reseau()
        if ip:
            self.assertIn("Sur le réseau    : http://%s:%d/" % (ip, port_http), texte)
        self.assertIn("Sur ce PC        : http://localhost:%d/" % port_http, texte)
        self.assertIn("Application      : en https sur le port %d" % port_https, texte)
        self.assertIn("certificat fabriqué par Prévo", texte)
        self.assertIn("comptes exigés", texte)
        self.assertNotIn("https://", texte)
        self.assertTrue((self.donnees / "acces" / "certificat.pem").is_file())
        self.assertTrue((self.donnees / "acces" / "cle.pem").is_file())
        self.assertTrue((self.donnees / "acces" / "autorite" / "rootCA.pem").is_file())
        self.config = serveur.Configuration(str(self.donnees), [])
        self.assertEqual(len(self.lancements()), 1)


# ---------------------------------------------------------------------------
# Fichiers que la porte sert sans session (T297 : un seul de plus, js/i18n-chargeur.js)
# ---------------------------------------------------------------------------

class TestFichiersSansSession(unittest.TestCase):

    def test_un_seul_fichier_de_plus_que_la_porte_d_avant(self):
        fichiers = [f.relative_to(RACINE).as_posix() for f in RACINE.rglob("*")
                    if f.is_file() and ".git" not in f.relative_to(RACINE).parts]
        self.assertGreater(len(fichiers), 300)
        servis = {chemin for chemin in fichiers if serveur.fichier_de_la_porte(chemin.lower().split("/"))}
        # La liste d'avant T297 (§22.6, T234) : le favicon, le moteur et les textes, les polices, la porte elle-même.
        avant = {chemin for chemin in fichiers
                 if chemin in ("favicon.svg", "js/i18n.js") or chemin.startswith(("js/i18n/", "css/polices/"))
                 or (chemin.startswith("acces/") and chemin != "acces/porte.html")}
        self.assertEqual(servis - avant, {"js/i18n-chargeur.js"})
        self.assertEqual(avant - servis, set())
        self.assertFalse(any(chemin.startswith(("js/modules/", "donnees/")) for chemin in servis))


# ---------------------------------------------------------------------------
# Aucune adresse https donnée par l'application ni le guide (CS137)
# ---------------------------------------------------------------------------

class TestAucuneAdresseHttps(unittest.TestCase):

    def fichiers_servis(self):
        fichiers = [RACINE / "index.html", RACINE / "GUIDE.html"]
        fichiers += [f for f in sorted((RACINE / "js").rglob("*.js")) if "lib" not in f.relative_to(RACINE).parts]
        fichiers += sorted((RACINE / "css").rglob("*.css"))
        fichiers += sorted((RACINE / "acces").rglob("*.*"))
        return fichiers

    def test_textes_servis_et_guide_sans_adresse_https(self):
        fichiers = self.fichiers_servis()
        self.assertGreater(len(fichiers), 60)
        for fichier in fichiers:
            with self.subTest(fichier=fichier.relative_to(RACINE).as_posix()):
                texte = fichier.read_text(encoding="utf-8")
                self.assertEqual(MOTIF_ADRESSE_HTTPS_IP.findall(texte), [])
                self.assertEqual(MOTIF_ADRESSE_HTTPS_PORT.findall(texte), [])
        guide = (RACINE / "GUIDE.html").read_text(encoding="utf-8")
        self.assertEqual(guide.count("https://192.168"), 0)
        self.assertIn("http://192.168.1.20:8080", guide)                      # la porte, elle, est donnée

    def test_la_page_de_porte_et_le_serveur(self):
        page = PAGE_PORTE.read_text(encoding="utf-8")
        self.assertIn(TITRE_PORTE, page)
        self.assertIn('href="/acces/ca.crt"', page)
        self.assertIn("Réessayer", page)
        self.assertIn("Firefox", page)
        self.assertIn("Réglages de confiance des certificats", page)
        self.assertIn("Certificat CA", page)
        self.assertEqual(MOTIF_ADRESSE_HTTPS_IP.findall(page), [])
        self.assertNotIn("8443", page)
        self.assertNotIn("https://", re.sub(r"<!--.*?-->", "", page, flags=re.S))      # aucune adresse hors commentaire
        self.assertNotIn("8443", (RACINE / "acces" / "porte.js").read_text(encoding="utf-8"))
        code = (RACINE / "serveur.py").read_text(encoding="utf-8")
        self.assertIn("PORT_HTTPS_PAR_DEFAUT", code)
        self.assertIn("acces/porte.html", code)
        for capture in captures_de_la_page():
            self.assertTrue((RACINE / capture.lstrip("/")).is_file(), capture)


# ---------------------------------------------------------------------------
# Navigateur : redirection en gardant la route, « Faites confiance au PC atelier », adresses de la porte
# ---------------------------------------------------------------------------

def profil_appareil(playwright, nom):
    """Profil Playwright d'un téléphone, joué dans Chromium (le type de navigateur du profil est ignoré)."""
    profil = dict(playwright.devices[nom])
    profil.pop("default_browser_type", None)
    return profil


def attendre(page, expression, delai_s=15):
    """Attente sans eval (la page de porte garde sa vraie politique : script-src 'self')."""
    import time
    limite = time.time() + delai_s
    while time.time() < limite:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(100)
    raise AssertionError("attente dépassée : " + expression)


class CasPorteNavigateur(CasNavigateur):
    CSP_REELLE = True
    MOTIF_PING_REFUSE = re.compile(r"net::ERR_CERT|/api/ping")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.atelier = ServeurAtelier()
        cls.atelier.demarrer()
        cls.addClassCleanup(cls.atelier.arreter)

    def telephone(self, nom, confiance=False):
        contexte = self.navigateur.new_context(locale="fr-FR", ignore_https_errors=confiance,
                                               **profil_appareil(self._playwright, nom))
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        page = contexte.new_page()
        self.surveiller(page)
        return contexte, page

    def attendre_confiance(self, page):
        attendre(page, "() => !document.getElementById('confiance').hidden")

    def verifier_etapes(self, page, systeme, texte_attendu, autre):
        self.assertEqual(page.evaluate("document.documentElement.dataset.systeme"), systeme)
        self.assertTrue(page.is_visible("#etapes-" + systeme))
        self.assertFalse(page.is_visible("#etapes-" + autre))
        self.assertFalse(page.is_visible("#choix-systeme"))
        etapes = page.locator("#etapes-%s > li" % systeme)
        self.assertGreaterEqual(etapes.count(), 6)
        self.assertIn(texte_attendu, page.inner_text("#etapes-" + systeme))
        for indice in range(etapes.count()):
            etape = etapes.nth(indice)
            self.assertEqual(etape.locator("h3").count(), 1)
            numero = etape.evaluate("(li) => getComputedStyle(li, '::before').content")
            self.assertNotIn(numero, ("none", "normal", '""'), "étape %d sans numéro" % (indice + 1))
        images = page.locator("#etapes-%s img" % systeme)
        self.assertGreaterEqual(images.count(), etapes.count() - 2)
        for indice in range(images.count()):
            image = images.nth(indice)
            self.assertTrue(image.get_attribute("src").startswith("/acces/captures/"))
            self.assertGreater(image.evaluate("(img) => img.naturalWidth"), 0, image.get_attribute("src"))
            self.assertTrue(image.get_attribute("alt"))
        lien = page.locator("#etapes-%s a.btn-telecharger" % systeme)
        self.assertEqual(lien.get_attribute("href"), "/acces/ca.crt")
        self.assertTrue(lien.is_visible())
        self.assertGreaterEqual(lien.bounding_box()["height"], 44)
        bouton = page.locator("#etapes-%s .btn-reessayer" % systeme)
        self.assertTrue(bouton.is_visible())
        self.assertGreaterEqual(bouton.bounding_box()["height"], 44)
        largeurs = page.evaluate("[document.scrollingElement.scrollWidth, document.scrollingElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal : %r" % largeurs)
        return bouton


class TestPorteNavigateur(CasPorteNavigateur):

    def changer_de_langue(self, page, code):
        """Le sélecteur de la porte : choix retenu, page rechargée, « Faites confiance au PC atelier » de nouveau."""
        with page.expect_navigation():
            page.select_option("#langue-liste", code)
        self.attendre_confiance(page)

    def test_porte_en_francais_selecteur_sans_menu_et_choix_garde(self):
        """T297 : installation en français ; le sélecteur change la langue sans menu ni mot à lire en français."""
        self.autoriser_erreur(self.MOTIF_PING_REFUSE)
        contexte, page = self.telephone("Pixel 7")
        page.goto(self.atelier.url_porte + "/#/equipement/EQ-0005")
        self.attendre_confiance(page)
        selecteur = page.evaluate(SELECTEUR_PORTE_JS)
        self.assertEqual(selecteur["options"], [[code, nom, code] for code, nom in langues_declarees()])
        self.assertEqual((selecteur["visible"], selecteur["valeur"], selecteur["lang"]), (True, "fr", "fr"))
        self.assertEqual(selecteur["autour"], "")                         # le globe et la liste, aucun mot
        self.assertTrue(selecteur["globe"])
        self.assertEqual(selecteur["etiquette"], texte_du_dictionnaire("fr", "porte.langue.etiquette"))
        # Visible sans menu : en haut de la page, au-dessus du titre, zone tactile de 44 px au moins.
        self.assertTrue(page.is_visible("#langue-liste"))
        boite = page.locator("#langue-liste").bounding_box()
        self.assertLess(boite["y"], page.locator(".marque").bounding_box()["y"])
        self.assertGreaterEqual(boite["height"], 44)
        self.assertIn(TITRE_PORTE, page.inner_text("#confiance"))
        # English : la page se recharge en anglais, la route est gardée, le choix tient au rechargement.
        self.changer_de_langue(page, "en")
        anglais = texte_du_dictionnaire("en", CLE_TITRE_PORTE)
        self.assertIn(anglais, page.inner_text("#confiance"))
        self.assertNotIn(TITRE_PORTE, page.inner_text("body"))
        self.assertEqual(page.evaluate("[document.documentElement.lang, document.title, localStorage.getItem('prevo.langue')]"),
                         ["en", texte_du_dictionnaire("en", "porte.page.prevo_bienvenue"), "en"])
        self.assertEqual(page.evaluate("location.hash"), "#/equipement/EQ-0005")
        self.assertEqual(page.evaluate(SELECTEUR_PORTE_JS)["etiquette"], texte_du_dictionnaire("en", "porte.langue.etiquette"))
        page.reload()
        self.attendre_confiance(page)
        self.assertIn(anglais, page.inner_text("#confiance"))
        # Français, la langue de l'installation : le choix est retiré, le téléphone suit l'installation.
        self.changer_de_langue(page, "fr")
        self.assertIn(TITRE_PORTE, page.inner_text("#confiance"))
        self.assertEqual(page.evaluate("[document.documentElement.lang, localStorage.getItem('prevo.langue')]"), ["fr", None])
        largeurs = page.evaluate("[document.scrollingElement.scrollWidth, document.scrollingElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal : %r" % largeurs)

    def test_porte_d_une_installation_en_anglais(self):
        """T297 : langue_defaut = en, téléphone en français sans choix : la porte en anglais ; Français choisi : gardé."""
        self.autoriser_erreur(self.MOTIF_PING_REFUSE)
        poser_langue_defaut(self, self.atelier.dossier, "en")
        contexte, page = self.telephone("iPhone 14")
        page.goto(self.atelier.url_porte + "/")
        self.attendre_confiance(page)
        self.assertEqual(page.evaluate("document.documentElement.dataset.langueInstallation"), "en")
        self.assertIn(texte_du_dictionnaire("en", CLE_TITRE_PORTE), page.inner_text("#confiance"))
        self.assertIn(texte_du_dictionnaire("en", "porte.etapes.telecharger_certificat"), page.inner_text("#etapes-iphone"))
        selecteur = page.evaluate(SELECTEUR_PORTE_JS)
        self.assertEqual((selecteur["valeur"], selecteur["lang"], selecteur["autour"]), ("en", "en", ""))
        # Message renvoyé par le serveur (sans autorité locale) : par son code, dans la langue de la page.
        self.assertEqual(page.evaluate("Porte.messageDuServeur({ erreur: 'Français reçu.', erreur_code: 'porte.sans_autorite' })"),
                         texte_du_dictionnaire("en", "serveur.porte.sans_autorite"))
        self.assertEqual(page.evaluate("Porte.messageDuServeur({ erreur: 'Français reçu.', erreur_code: 'code.inconnu' })"),
                         "Français reçu.")
        self.changer_de_langue(page, "fr")
        self.assertIn(TITRE_PORTE, page.inner_text("#confiance"))
        self.assertEqual(page.evaluate("localStorage.getItem('prevo.langue')"), "fr")

    def test_valeur_abimee_gardee_par_le_telephone_francais_sans_erreur(self):
        self.autoriser_erreur(self.MOTIF_PING_REFUSE)
        contexte, page = self.telephone("Pixel 7")
        contexte.add_init_script("localStorage.setItem('prevo.langue', 'zz\"><img src=x onerror=alert(1)>');")
        requetes = []
        page.on("request", lambda requete: requetes.append(requete.url))
        page.goto(self.atelier.url_porte + "/")
        self.attendre_confiance(page)
        selecteur = page.evaluate(SELECTEUR_PORTE_JS)
        self.assertEqual((selecteur["valeur"], selecteur["lang"]), ("fr", "fr"))
        self.assertIn(TITRE_PORTE, page.inner_text("#confiance"))
        self.assertEqual([url for url in requetes if "/js/i18n/" in url and not url.endswith(("/langues.js", "/fr.js"))], [])

    def test_navigateur_qui_fait_confiance_redirige_en_gardant_la_route(self):
        contexte, page = self.telephone("Pixel 7", confiance=True)
        enroler_appareil(self.atelier, contexte)            # invitation du responsable, appareil enrôlé (T153 ; écran à T156)
        preregler_profil(contexte, "demandeur", "Karim Benali")
        self.autoriser_erreur(motif_refus_du_demandeur())
        page.goto(self.atelier.url_porte + "/#/equipement/EQ-0005")
        page.wait_for_url(self.atelier.url_https + "/#/equipement/EQ-0005")
        attendre(page, "() => document.documentElement.dataset.etat === 'pret'")
        self.assertTrue(page.evaluate("window.isSecureContext"))
        self.assertEqual(page.evaluate("location.hash"), "#/equipement/EQ-0005")
        self.assertIn("PO-02", page.inner_text("#contenu h1"))
        self.assertEqual(page.evaluate("App.urlFicheEquipement('EQ-0005')"),
                         self.atelier.url_porte + "/#/equipement/EQ-0005")       # le QR de la fiche : la porte
        # Un lien d'invitation (T153) garde aussi son fragment : seule la route change de port.
        contexte.route(self.atelier.url_https + "/", lambda route: route.fulfill(
            status=200, content_type="text/html", body="<!doctype html><title>Application</title>"))
        page.goto(self.atelier.url_porte + "/#/enroler/jeton-de-test_0123456789")
        page.wait_for_url(self.atelier.url_https + "/#/enroler/jeton-de-test_0123456789")

    def test_sans_confiance_android_etapes_numerotees_et_reessayer(self):
        self.autoriser_erreur(self.MOTIF_PING_REFUSE)
        contexte, page = self.telephone("Pixel 7")
        page.goto(self.atelier.url_porte + "/#/equipement/EQ-0005")
        self.attendre_confiance(page)
        self.assertEqual(page.evaluate("location.href"), self.atelier.url_porte + "/#/equipement/EQ-0005")
        self.assertIn(TITRE_PORTE, page.inner_text("#confiance"))
        self.assertTrue(page.is_visible("#note-firefox"))
        bouton = self.verifier_etapes(page, "android", "Certificat CA", "iphone")
        self.assertIn("Installer quand même", page.inner_text("#etapes-android"))
        bouton.click()
        attendre(page, "() => { const m = document.getElementById('message-essai'); "
                       "return !m.hidden && m.textContent.includes('ne fait pas encore confiance'); }")
        self.assertEqual(page.evaluate("location.href"), self.atelier.url_porte + "/#/equipement/EQ-0005")
        self.assertTrue(page.is_visible("#etapes-android"))
        self.assertEqual(page.evaluate("Porte.adresseCible()"), self.atelier.url_https + "/#/equipement/EQ-0005")

    def test_sans_confiance_iphone_etapes_du_bon_systeme(self):
        self.autoriser_erreur(self.MOTIF_PING_REFUSE)
        contexte, page = self.telephone("iPhone 14")
        page.goto(self.atelier.url_porte + "/")
        self.attendre_confiance(page)
        self.verifier_etapes(page, "iphone", "Réglages de confiance des certificats", "android")
        self.assertIn("Profil téléchargé", page.inner_text("#etapes-iphone"))
        self.assertFalse(page.is_visible("#note-firefox"))

    def test_systeme_inconnu_choix_entre_les_deux(self):
        self.autoriser_erreur(self.MOTIF_PING_REFUSE)
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        page = contexte.new_page()
        self.surveiller(page)
        page.goto(self.atelier.url_porte + "/")
        self.attendre_confiance(page)
        self.assertTrue(page.is_visible("#choix-systeme"))
        self.assertFalse(page.is_visible("#etapes-android"))
        self.assertFalse(page.is_visible("#etapes-iphone"))
        page.click("#choix-systeme [data-systeme='iphone']")
        self.assertTrue(page.is_visible("#etapes-iphone"))
        self.assertFalse(page.is_visible("#etapes-android"))
        page.click("#choix-systeme [data-systeme='android']")
        self.assertTrue(page.is_visible("#etapes-android"))
        agents = page.evaluate("""() => [
          Porte.systemeDuTelephone('Mozilla/5.0 (Linux; Android 14; Pixel 7) Chrome/130 Mobile Safari/537.36', true),
          Porte.systemeDuTelephone('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) Safari/604.1', true),
          Porte.systemeDuTelephone('Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) Safari/604.1', true),
          Porte.systemeDuTelephone('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15', true),
          Porte.systemeDuTelephone('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15', false),
          Porte.systemeDuTelephone('Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130', false)]""")
        self.assertEqual(agents, ["android", "iphone", "iphone", "iphone", "", ""])

    def test_qr_de_l_accueil_et_etiquettes_sur_l_adresse_de_la_porte(self):
        cookie = connecter(self.atelier.url_pc, "nicolas.briand").cookie
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800}, bypass_csp=True)
        self.addCleanup(contexte.close)
        contexte.add_cookies([{"name": "id", "value": cookie.split("=", 1)[1], "url": self.atelier.url_pc,
                               "httpOnly": True, "sameSite": "Lax"}])
        preregler_profil(contexte, "responsable", "Responsable")
        page = contexte.new_page()
        self.surveiller(page)
        page.goto(self.atelier.url_pc + "/#/accueil")
        attendre_pret(page)
        porte = self.atelier.url_porte + "/"
        self.assertIn(porte, page.evaluate("App.adressesReseau()"))
        self.assertEqual(page.evaluate("App.urlFicheEquipement('EQ-0005')"), self.atelier.url_porte + "/#/equipement/EQ-0005")
        page.wait_for_selector("#carte-connexion")
        self.assertEqual(page.inner_text("#adresse-reseau"), porte)
        self.assertNotIn(":%d" % self.atelier.port_https, page.inner_text("#carte-connexion"))
        self.assertIn(TITRE_PORTE, page.inner_text("#carte-connexion"))     # le rappel, puisque la porte est ouverte
        page.goto(self.atelier.url_pc + "/#/parc/etiquettes")
        page.wait_for_selector("#etiquettes-adresse-encodee")
        self.assertIn(self.atelier.url_porte, page.inner_text("#etiquettes-adresse-encodee"))
        self.assertNotIn(":%d" % self.atelier.port_https, page.inner_text("#contenu"))


if __name__ == "__main__":
    unittest.main()
