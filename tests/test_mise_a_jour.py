"""Mise à jour signalée (ARCHITECTURE.md §21 ; D120, CS118 ; tâche T147 ; T305 : D174-D176, Nicolas 06 et 07/11).

Prévo lit https://prevo.pro/version.json (ici un faux serveur local, adresse forcée par window.PREVO_ADRESSE_VERSION)
au plus une fois par jour et par poste, active par défaut, coupée par maj_signalee = 0 (Paramètres), et signale une
version plus récente sur l'accueil du responsable et dans « À propos ». Ce qui est vérifié :
    défaut       (T305) maj_signalee absente : lecture faite, bandeau d'information unique #maj-information
                 (« Compris » le retire pour ce poste, au rechargement aussi) ; réglée à 1 : pas de bandeau
                 d'information ; la case de Paramètres est cochée par défaut, son texte dit ce qui part ;
    requête      (T305) rien que la requête : aucun paramètre, ni Cookie ni Referer, l'en-tête Origin ajouté par le
                 navigateur (dit dans la doc) ; une redirection n'est jamais suivie ;
    liste blanche (T305, D176) adresse de téléchargement : https://prevo.pro/… ou https://github.com/nicoboy49/prevo/…
                 seulement (hôte exact, sans nom, sans port) ; sinon aucun bandeau ;
    anglais      (T305) nouveautes_en montré dans Prévo en anglais, nouveautes sinon (et en anglais sans
                 nouveautes_en) ; texte toujours échappé ;
    accord       version plus récente : bandeau #maj-bandeau (version, date, nouveautés, « Télécharger » vers l'adresse
                 de la release, « Ignorer cette version ») et ligne « Mise à jour » de À propos avec le lien ;
    une par jour deux rechargements : une seule requête ; « Ignorer » tient au rechargement, sans nouvelle requête ;
    rien         coupée (maj_signalee = 0), technicien, version web : aucune requête ; version égale, fichier mal formé, absent
                 (404), serveur injoignable : pas de bandeau, aucune erreur JavaScript, ligne de À propos adaptée ;
    fichier      vérification du contenu (numéro, adresse https, nouveautés bornées), comparaison des versions ;
    semver       (T216) pré-versions : 2.0.0-beta.2 < 2.0.0-beta.10 < 2.0.0 ; une bêta est prévenue de la finale,
                 une installation stable jamais d'une bêta ;
    release      outils/construire_release.py écrit dist/version.json (numéro, date, adresse de la release,
                 nouveautés tirées du CHANGELOG sans Markdown).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_mise_a_jour.py" -v
"""
import http.server
import importlib.util
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier
from test_version_web import lancer, version_et_date

SCRIPT_RELEASE = RACINE / "outils" / "construire_release.py"
TECHNICIEN = "TEC-0001"
PANNE_RESEAU = r"ERR_CONNECTION_REFUSED|Failed to fetch|net::ERR"
LECTURE_VIDE_AU_PREMIER_AFFICHAGE_JS = """if (!sessionStorage.getItem('test-maj-ouvert')) {
  sessionStorage.setItem('test-maj-ouvert', '1');
  const d = new Date();
  const jour = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  localStorage.setItem('prevo.majLecture', JSON.stringify({ date: jour, fichier: null }));
}"""


def version_suivante(version):
    """Une version plus récente que celle de l'application, à signaler : x.y.z → x.y.(z+1) ; pré-version
    x.y.z-beta.N → x.y.z (la finale, que la bêta doit voir, T216)."""
    base, _, pre = version.partition("-")
    if pre:
        return base
    nombres = [int(n) for n in base.split(".")]
    nombres[2] += 1
    return ".".join(str(n) for n in nombres)


def fichier_version(version, **champs):
    contenu = {"version": version, "date": "2026-11-02", "adresse": "https://github.com/nicoboy49/prevo/releases/tag/v" + version,
               "nouveautes": ["Mise à jour signalée sur l'accueil.", "Wiki de maintenance : pages de machines."]}
    contenu.update(champs)
    return json.dumps(contenu, ensure_ascii=False).encode("utf-8")


class FauxSite:
    """Faux prevo.pro : sert /version.json (corps et statut donnés), compte les requêtes, en-tête CORS comme le vrai."""

    def __init__(self, corps=b"", statut=200, entetes=None):
        self.corps, self.statut, self.requetes, self.entetes_recus = corps, statut, [], []
        self.entetes_envoyes = dict(entetes or {})

    def __enter__(self):
        site = self

        class Gestionnaire(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                site.requetes.append(self.path)
                site.entetes_recus.append({nom.lower(): valeur for nom, valeur in self.headers.items()})
                self.send_response(site.statut)
                for nom, valeur in site.entetes_envoyes.items():
                    self.send_header(nom, valeur)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(site.corps)))
                self.end_headers()
                self.wfile.write(site.corps)

            def log_message(self, *arguments):
                pass

        self.serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        return self

    def __exit__(self, *exception):
        self.serveur.shutdown()
        self.serveur.server_close()

    @property
    def url(self):
        return "http://127.0.0.1:%d/version.json" % self.serveur.server_address[1]


class CasMiseAJour(CasNavigateur):

    VERIFICATION_DE_VERSION = True                  # faux site local (commun.servir_version_des_tests ne joue pas)

    def setUp(self):
        super().setUp()
        self.version = version_et_date()[0]
        self.nouvelle = version_suivante(self.version)

    def ouvrir(self, serveur, adresse, profil="responsable", accord=True, langue=None, cookies=None, **options):
        """Page du responsable (ou d'un autre profil) en mode serveur, adresse du faux site forcée ; accord : True écrit
        maj_signalee = 1, False maj_signalee = 0 (coupée), None n'écrit rien (jamais réglée : active par défaut, T305),
        dans parametres.csv (serveur) avant le rechargement qui déclenche la lecture ; langue : choix de ce poste."""
        self.contexte.close()
        self.contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1440, "height": 900})
        self.contexte.add_init_script("window.PREVO_ADRESSE_VERSION = %s;" % json.dumps(adresse))
        if langue:
            self.contexte.add_init_script("localStorage.setItem('prevo.langue', %s);" % json.dumps(langue))
        if cookies:
            self.contexte.add_cookies(cookies)
        if accord is not None:
            # T305 (active par défaut) : le premier affichage lirait avant que le réglage soit écrit ; une lecture du
            # jour « vide » posée d'avance l'en empêche, une seule fois par onglet (la seule lecture suit le réglage).
            self.contexte.add_init_script(LECTURE_VIDE_AU_PREMIER_AFFICHAGE_JS)
        preregler_profil(self.contexte, profil, **options)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)
        self.page.goto(serveur.url + "/")
        attendre_pret(self.page, 30000)
        if accord is not None:
            self.page.evaluate("""(valeur) => Donnees.modifier('parametres', (lignes) => {
                const ligne = lignes.find((l) => l.cle === 'maj_signalee');
                if (ligne) ligne.valeur = valeur; else lignes.push({ cle: 'maj_signalee', valeur: valeur });
                return true; }, { action: 'test de la mise à jour signalée' })""", "1" if accord else "0")
            self.page.evaluate("localStorage.removeItem('prevo.majLecture')")
            self.page.reload()
            attendre_pret(self.page, 30000)
        return self.page

    def attendre_lecture(self):
        self.page.wait_for_function("localStorage.getItem('prevo.majLecture') !== null", timeout=10000)
        return json.loads(self.page.evaluate("localStorage.getItem('prevo.majLecture')"))

    def ligne_apropos(self):
        self.page.evaluate("location.hash = '#/apropos'")
        self.page.wait_for_selector("#apropos-maj")
        return self.page.evaluate("document.querySelector('#apropos-maj').textContent.replace(/\\s+/g, ' ').trim()")


class TestSignalement(CasMiseAJour):

    def test_version_plus_recente_bandeau_lien_et_ligne_de_a_propos(self):
        with ServeurPrevo() as serveur, FauxSite(fichier_version(self.nouvelle)) as site:
            page = self.ouvrir(serveur, site.url)
            page.wait_for_selector("#maj-zone #maj-bandeau", timeout=10000)
            texte = page.evaluate("document.querySelector('#maj-bandeau').textContent.replace(/\\s+/g, ' ').trim()")
            self.assertIn("Prévo %s est disponible" % self.nouvelle, texte)
            self.assertIn("(02/11/2026)", texte)
            self.assertIn("Mise à jour signalée sur l'accueil. · Wiki de maintenance : pages de machines.", texte)
            lien = page.locator("#maj-bandeau a.maj-telecharger")
            self.assertEqual(lien.get_attribute("href"), "https://github.com/nicoboy49/prevo/releases/tag/v" + self.nouvelle)
            self.assertEqual(lien.get_attribute("target"), "_blank")
            self.assertEqual(page.evaluate("document.querySelector('#maj-bandeau').getAttribute('role')"), "status")
            self.assertEqual(site.requetes, ["/version.json"])
            # Toujours à sa place après un retour sur l'accueil, sans nouvelle requête.
            page.evaluate("location.hash = '#/parc'")
            page.wait_for_selector("#contenu h1")
            page.evaluate("location.hash = '#/accueil'")
            page.wait_for_selector("#maj-zone #maj-bandeau")
            self.assertEqual(len(site.requetes), 1)
            ligne = self.ligne_apropos()
            self.assertIn("Prévo %s est disponible" % self.nouvelle, ligne)
            self.assertEqual(page.get_attribute("#apropos-maj a", "href"), "https://github.com/nicoboy49/prevo/releases/tag/v" + self.nouvelle)

    def test_une_lecture_par_jour_et_ignorer_tient_au_rechargement(self):
        with ServeurPrevo() as serveur, FauxSite(fichier_version(self.nouvelle)) as site:
            page = self.ouvrir(serveur, site.url)
            page.wait_for_selector("#maj-bandeau", timeout=10000)
            for _ in range(2):
                page.reload()
                attendre_pret(page, 30000)
                page.wait_for_selector("#maj-bandeau")
            self.assertEqual(site.requetes, ["/version.json"], "une seule lecture par jour et par poste")
            page.click("#maj-bandeau .maj-ignorer")
            page.wait_for_selector("#maj-bandeau", state="detached")
            self.assertEqual(page.evaluate("localStorage.getItem('prevo.majIgnoree')"), self.nouvelle)
            page.reload()
            attendre_pret(page, 30000)
            page.wait_for_selector("#contenu .accueil-instruments")
            self.assertIsNone(page.query_selector("#maj-bandeau"))
            self.assertEqual(len(site.requetes), 1)
            self.assertIn("Prévo est à jour", self.ligne_apropos())
            # Une version plus récente encore est signalée malgré la version ignorée.
            self.assertTrue(page.evaluate("""(v) => { localStorage.setItem('prevo.majLecture', JSON.stringify({ date: JSON.parse(localStorage.getItem('prevo.majLecture')).date,
                fichier: { version: v, date: '2026-12-01', adresse: 'https://prevo.pro/', nouveautes: [] } })); return Boolean(MiseAJour.disponible()); }""",
                                          version_suivante(self.nouvelle)))

    def test_coupee_technicien_et_version_web_aucune_requete(self):
        with ServeurPrevo() as serveur, FauxSite(fichier_version(self.nouvelle)) as site:
            page = self.ouvrir(serveur, site.url, accord=False)
            page.wait_for_selector("#contenu .accueil-instruments")
            page.wait_for_timeout(500)
            self.assertEqual(site.requetes, [])
            self.assertIsNone(page.evaluate("localStorage.getItem('prevo.majLecture')"))
            self.assertIsNone(page.query_selector("#maj-bandeau"))
            self.assertIn("Non vérifiée", self.ligne_apropos())
            self.assertIn("Paramètres", self.ligne_apropos())
            # Technicien, même avec l'accord : rien ne part, rien n'est montré.
            page = self.ouvrir(serveur, site.url, profil="technicien", technicien_id=TECHNICIEN)
            page.wait_for_selector("#contenu h1")
            page.wait_for_timeout(500)
            self.assertEqual(site.requetes, [])
            self.assertIsNone(page.evaluate("localStorage.getItem('prevo.majLecture')"))
            self.assertIsNone(page.query_selector("#maj-bandeau"))
            self.assertNotIn("disponible", self.ligne_apropos())
            # Version web (démo en ligne) : la vérification refuse avant toute requête.
            page = self.ouvrir(serveur, site.url)
            page.wait_for_selector("#maj-bandeau", timeout=10000)
            self.assertEqual(len(site.requetes), 1)
            resultat = page.evaluate("""async () => { localStorage.removeItem('prevo.majLecture'); App.versionWeb = true;
                const r = await MiseAJour.verifier(); return [r, localStorage.getItem('prevo.majLecture'), MiseAJour.disponible()]; }""")
            self.assertEqual(resultat, [None, None, None])
            self.assertEqual(len(site.requetes), 1)
            self.assertIn("Démo en ligne", self.ligne_apropos())

    def test_version_egale_fichier_mal_forme_absent_ou_injoignable_rien_et_aucune_erreur(self):
        with ServeurPrevo() as serveur:
            with FauxSite(fichier_version(self.version)) as site:          # même version : à jour
                page = self.ouvrir(serveur, site.url)
                lecture = self.attendre_lecture()
                self.assertEqual(lecture["fichier"]["version"], self.version)
                page.wait_for_selector("#contenu .accueil-instruments")
                self.assertIsNone(page.query_selector("#maj-bandeau"))
                self.assertIn("Prévo est à jour", self.ligne_apropos())
            with FauxSite(b"pas du JSON {") as site:                        # mal formé
                page = self.ouvrir(serveur, site.url)
                self.assertIsNone(self.attendre_lecture()["fichier"])
                self.assertIsNone(page.query_selector("#maj-bandeau"))
                self.assertIn("Vérification impossible aujourd'hui", self.ligne_apropos())
            with FauxSite(fichier_version(self.nouvelle, adresse="http://pas-https.exemple/")) as site:   # adresse refusée
                page = self.ouvrir(serveur, site.url)
                self.assertIsNone(self.attendre_lecture()["fichier"])
                self.assertIsNone(page.query_selector("#maj-bandeau"))
            self.autoriser_erreur(re.compile(r"status of 404.*version\.json"))
            with FauxSite(b"", statut=404) as site:                        # absent
                page = self.ouvrir(serveur, site.url)
                self.assertIsNone(self.attendre_lecture()["fichier"])
                self.assertIsNone(page.query_selector("#maj-bandeau"))
            self.autoriser_erreur(re.compile(PANNE_RESEAU))
            with FauxSite(b"") as site:                                    # injoignable : le port est fermé
                adresse = site.url
            page = self.ouvrir(serveur, adresse)
            self.assertIsNone(self.attendre_lecture()["fichier"])
            self.assertIsNone(page.query_selector("#maj-bandeau"))
            self.assertIn("Vérification impossible aujourd'hui", self.ligne_apropos())

    def test_lecture_du_fichier_et_comparaison_des_versions(self):
        with ServeurPrevo() as serveur, FauxSite(fichier_version(self.nouvelle)) as site:
            page = self.ouvrir(serveur, site.url, accord=False)
            resultat = page.evaluate("""() => ({
              nombres: [MiseAJour.nombres('1.2.0'), MiseAJour.nombres(' 10.0.3 '), MiseAJour.nombres('1.2'), MiseAJour.nombres('v1.2.0'), MiseAJour.nombres(12)],
              plusRecente: [MiseAJour.plusRecente([1, 2, 0], [1, 1, 9]), MiseAJour.plusRecente([1, 10, 0], [1, 9, 0]),
                            MiseAJour.plusRecente([1, 1, 0], [1, 1, 0]), MiseAJour.plusRecente([1, 0, 9], [1, 1, 0]), MiseAJour.plusRecente(null, [1, 0, 0])],
              fichier: MiseAJour.lireFichier({ version: '1.3.0', date: '2026-12-24', adresse: 'https://prevo.pro/x',
                nouveautes: ['  un  ', '', 'deux', 'trois', 'quatre', 7, 'x'.repeat(300)] }),
              refuses: [MiseAJour.lireFichier(null), MiseAJour.lireFichier({ version: '1.3.0' }), MiseAJour.lireFichier({ version: '1.3', adresse: 'https://a' }),
                        MiseAJour.lireFichier({ version: '1.3.0', adresse: 'ftp://a' })],
              dateIgnoree: MiseAJour.lireFichier({ version: '1.3.0', adresse: 'https://prevo.pro/a', date: 'hier' }).date,
            })""")
            self.assertEqual(resultat["nombres"], [[1, 2, 0], [10, 0, 3], None, None, None])
            self.assertEqual(resultat["plusRecente"], [True, True, False, False, False])
            fichier = resultat["fichier"]
            self.assertEqual((fichier["version"], fichier["date"], fichier["adresse"]), ("1.3.0", "2026-12-24", "https://prevo.pro/x"))
            self.assertEqual(fichier["nouveautes"][:2], ["un", "deux"])
            self.assertEqual(len(fichier["nouveautes"]), 3)
            self.assertEqual(resultat["refuses"], [None, None, None, None])
            self.assertEqual(resultat["dateIgnoree"], "")

    def test_semver_une_beta_voit_la_finale_une_stable_jamais_une_beta(self):
        # T216 : MOTIF_VERSION n'acceptait que X.Y.Z, une installation 2.0.0-beta.2 n'aurait jamais vu la 2.0.0.
        with ServeurPrevo() as serveur, FauxSite(fichier_version(self.nouvelle)) as site:
            page = self.ouvrir(serveur, site.url, accord=False)
            resultat = page.evaluate("""() => {
              const n = MiseAJour.nombres;
              const plus = (a, b) => MiseAJour.plusRecente(n(a), n(b));
              const signaler = (lue, installee) => MiseAJour.aSignaler(n(lue), n(installee));
              return {
                nombres: [n('2.0.0-beta.2'), n(' 2.0.0-rc.1 '), n('2.0.0-'), n('2.0.0-beta..1'), n('2.0.0+build.1'),
                          n('2.0.0-béta'), n('2.0.0-a.b.c.d.e'), n('2.0.0-' + 'x'.repeat(21))],
                plus: [plus('2.0.0', '2.0.0-beta.2'), plus('2.0.0-beta.2', '2.0.0'), plus('2.0.0-beta.10', '2.0.0-beta.2'),
                       plus('2.0.0-beta.2', '2.0.0-beta.10'), plus('2.0.0-beta.2', '2.0.0-beta.2'), plus('2.0.0-beta.1', '2.0.0-beta'),
                       plus('2.0.0-rc.1', '2.0.0-beta.9'), plus('2.0.0-beta', '2.0.0-1'), plus('2.0.1-beta.1', '2.0.0'),
                       plus('1.2.1', '2.0.0-beta.2'), plus('2.0.0-beta.2', '1.2.1')],
                signaler: [signaler('2.0.0', '2.0.0-beta.2'), signaler('2.0.0-beta.3', '2.0.0-beta.2'),
                           signaler('2.1.0', '2.0.0-beta.2'), signaler('2.0.0-beta.2', '1.2.1'), signaler('2.0.0-beta.2', '2.0.0'),
                           signaler('1.2.2', '1.2.1'), signaler('1.2.1', '2.0.0-beta.2'), signaler('2.0.0', null)],
                fichier: MiseAJour.lireFichier({ version: '2.0.0-beta.3', adresse: 'https://prevo.pro/x' }).version,
              };
            }""")
            self.assertEqual(resultat["nombres"], [[2, 0, 0, "beta", 2], [2, 0, 0, "rc", 1], None, None, None, None, None,
                                                   None])
            self.assertEqual(resultat["plus"], [True, False, True, False, False, True, True, True, True, False, True])
            self.assertEqual(resultat["signaler"], [True, True, True, False, False, True, False, False])
            self.assertEqual(resultat["fichier"], "2.0.0-beta.3")


class TestActiveParDefaut(CasMiseAJour):

    def test_jamais_reglee_lecture_faite_et_bandeau_d_information_unique(self):
        with ServeurPrevo() as serveur, FauxSite(fichier_version(self.nouvelle)) as site:
            page = self.ouvrir(serveur, site.url, accord=None)
            page.wait_for_selector("#maj-bandeau", timeout=10000)
            self.assertEqual(len(site.requetes), 1)
            information = page.inner_text("#maj-information")
            self.assertIn("Prévo vérifie une fois par jour s'il existe une nouvelle version", information)
            self.assertIn("Paramètres › Mises à jour", information)
            page.click("#maj-information button:has-text('Compris')")
            page.wait_for_selector("#maj-information", state="detached")
            page.reload()
            attendre_pret(page, 30000)
            page.wait_for_selector("#maj-bandeau", timeout=10000)
            self.assertIsNone(page.query_selector("#maj-information"))          # une fois par poste
            self.assertEqual(len(site.requetes), 1)                              # une lecture par jour
            # La case de Paramètres est cochée par défaut et son texte dit ce qui part.
            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_selector("[data-champ=maj_signalee] input[type=checkbox]")
            self.assertTrue(page.is_checked("[data-champ=maj_signalee] input[type=checkbox]"))
            texte = page.inner_text("[data-champ=maj_signalee]")
            for morceau in ("https://prevo.pro/version.json", "ni identifiant, ni numéro d'installation, ni statistique",
                            "l'adresse par laquelle Prévo est ouvert", "la seule connexion que Prévo ouvre de lui-même"):
                self.assertIn(morceau, texte)
            # Réglée à 1 (le responsable a décidé) : plus de bandeau d'information, même sur un poste neuf.
            page = self.ouvrir(serveur, site.url, accord=True)
            page.wait_for_selector("#maj-bandeau", timeout=10000)
            self.assertIsNone(page.query_selector("#maj-information"))

    def test_demo_ouverte_depuis_index_html_aucune_requete(self):
        # T305 : la démo (atelier fictif en mémoire) ne vérifie rien, comme avant la vérification par défaut.
        with FauxSite(fichier_version(self.nouvelle)) as site:
            self.contexte.add_init_script("window.PREVO_ADRESSE_VERSION = %s;" % json.dumps(site.url))
            preregler_profil(self.contexte, "responsable")
            page = self.page
            page.goto(url_fichier("index.html"))
            page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            page.click("#btn-demo")
            attendre_pret(page)
            page.wait_for_selector("#contenu .accueil-instruments")
            page.wait_for_timeout(500)
            self.assertEqual(site.requetes, [])
            self.assertIsNone(page.query_selector("#maj-information"))
            self.assertEqual(self.ligne_apropos(), "Démo : aucune vérification (rien n'est lu sur Internet).")

    def test_rien_que_la_requete_sans_referer_ni_cookie_ni_redirection(self):
        with ServeurPrevo() as serveur, FauxSite(fichier_version(self.nouvelle)) as site:
            page = self.ouvrir(serveur, site.url, accord=None, cookies=[{"name": "temoin", "value": "ne-doit-pas-partir",
                                                                         "domain": "127.0.0.1", "path": "/"}])
            page.wait_for_selector("#maj-bandeau", timeout=10000)
            self.assertEqual(site.requetes, ["/version.json"])                 # aucun paramètre
            entetes = site.entetes_recus[0]
            self.assertNotIn("cookie", entetes)
            self.assertNotIn("referer", entetes)
            self.assertEqual(entetes.get("origin"), serveur.url)              # ajouté par le navigateur (doc, T305)
        self.autoriser_erreur(re.compile(PANNE_RESEAU + r"|Failed to load resource"))
        with ServeurPrevo() as serveur, FauxSite(b"", statut=302) as site:
            site.entetes_envoyes["Location"] = site.url + "?redirige"
            page = self.ouvrir(serveur, site.url, accord=True)
            self.assertIsNone(self.attendre_lecture()["fichier"])
            self.assertEqual(site.requetes, ["/version.json"])                 # la redirection n'est pas suivie
            self.assertIsNone(page.query_selector("#maj-bandeau"))

    def test_adresse_de_telechargement_en_liste_blanche(self):
        with ServeurPrevo() as serveur, FauxSite(fichier_version(self.nouvelle)) as site:
            page = self.ouvrir(serveur, site.url, accord=False)
            permises = page.evaluate("""() => [
              'https://prevo.pro/', 'https://prevo.pro/telecharger', 'https://github.com/nicoboy49/prevo',
              'https://github.com/nicoboy49/prevo/releases/tag/v2.0.0',
              'http://prevo.pro/', 'https://prevo.pro.exemple.com/', 'https://www.prevo.pro/', 'https://prevo.pro:8443/',
              'https://nom:secret@prevo.pro/', 'https://github.com/autre/prevo', 'https://github.com/nicoboy49/prevo-faux',
              'https://github.com/nicoboy49', 'https://exemple.org/prevo.pro', 'javascript:alert(1)', 'pas une adresse',
            ].map((a) => MiseAJour.adresseDeTelechargementPermise(a))""")
            self.assertEqual(permises, [True] * 4 + [False] * 11)
            for adresse in ("https://exemple.org/prevo-2.zip", "https://github.com/autre/prevo/releases"):
                with self.subTest(adresse=adresse):
                    self.assertIsNone(page.evaluate("(a) => MiseAJour.lireFichier({ version: '9.9.9', adresse: a })",
                                                    adresse))
        with ServeurPrevo() as serveur, FauxSite(fichier_version(self.nouvelle, adresse="https://exemple.org/x")) as site:
            page = self.ouvrir(serveur, site.url)
            self.assertIsNone(self.attendre_lecture()["fichier"])
            page.wait_for_selector("#contenu .accueil-instruments")
            self.assertIsNone(page.query_selector("#maj-bandeau"))

    def test_nouveautes_en_anglais_si_le_fichier_en_a(self):
        anglais = ["Turkish names in user names.", "<b>not bold</b>"]
        with ServeurPrevo() as serveur, FauxSite(fichier_version(self.nouvelle, nouveautes_en=anglais)) as site:
            page = self.ouvrir(serveur, site.url, langue="en")
            page.wait_for_selector("#maj-bandeau", timeout=10000)
            self.assertEqual(page.inner_text("#maj-bandeau .maj-nouveautes"), " · ".join(anglais))   # texte, pas HTML
            self.assertIsNone(page.query_selector("#maj-bandeau .maj-nouveautes b"))
            page = self.ouvrir(serveur, site.url)
            page.wait_for_selector("#maj-bandeau", timeout=10000)
            self.assertIn("Mise à jour signalée sur l'accueil.", page.inner_text("#maj-bandeau .maj-nouveautes"))
        with ServeurPrevo() as serveur, FauxSite(fichier_version(self.nouvelle)) as site:     # sans nouveautes_en
            page = self.ouvrir(serveur, site.url, langue="en")
            page.wait_for_selector("#maj-bandeau", timeout=10000)
            self.assertIn("Mise à jour signalée sur l'accueil.", page.inner_text("#maj-bandeau .maj-nouveautes"))


class TestVersionJsonDeLaRelease(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        specification = importlib.util.spec_from_file_location("construire_release_test", SCRIPT_RELEASE)
        cls.module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(cls.module)
        cls.version, cls.date = version_et_date()

    def test_version_json_ecrit_avec_le_zip(self):
        with tempfile.TemporaryDirectory(prefix="prevo-maj-") as sortie:
            resultat = lancer(SCRIPT_RELEASE, "--sortie", sortie, "--sans-tiers")
            self.assertEqual(resultat.returncode, 0, resultat.stderr)
            self.assertIn("version.json", resultat.stdout)
            self.assertIn("Access-Control-Allow-Origin", resultat.stdout)
            octets = (Path(sortie) / "version.json").read_bytes()
            self.assertNotIn(b"\r\n", octets)
            self.assertTrue(octets.endswith(b"\n"))
            contenu = json.loads(octets.decode("utf-8"))
            self.assertEqual(sorted(contenu), ["adresse", "date", "nouveautes", "version"])
            self.assertEqual(contenu["version"], self.version)
            self.assertEqual(contenu["date"], "%04d-%02d-%02d" % self.date)
            self.assertEqual(contenu["adresse"], "https://github.com/nicoboy49/prevo/releases/tag/v" + self.version)
            self.assertEqual(contenu["nouveautes"], self.module.nouveautes_du_changelog(RACINE, self.version))
            self.assertLessEqual(len(contenu["nouveautes"]), 2)
            for nouveaute in contenu["nouveautes"]:
                self.assertTrue(nouveaute and len(nouveaute) <= 200, nouveaute)
                self.assertFalse(re.search(r"\*\*|`|\]\(", nouveaute), nouveaute)

    def test_nouveautes_du_changelog(self):
        with tempfile.TemporaryDirectory(prefix="prevo-maj-") as dossier:
            changelog = Path(dossier) / "CHANGELOG.md"
            changelog.write_text("# Journal\n\n## [Non publié]\n\n- pas celle-là\n\n## [2.0.0] - 2027-01-01\n\n### Ajouté\n\n"
                                 "- Première **nouveauté** avec un [lien](docs/X.md) et du `code`,\n  sur deux   lignes.\n"
                                 "- Deuxième nouveauté.\n- Troisième, ignorée.\n\n## [1.9.0] - 2026-12-01\n\n- ancienne\n",
                                 encoding="utf-8")
            self.assertEqual(self.module.nouveautes_du_changelog(dossier, "2.0.0"),
                             ["Première nouveauté avec un lien et du code, sur deux lignes.", "Deuxième nouveauté."])
            self.assertEqual(self.module.nouveautes_du_changelog(dossier, "1.9.0"), ["ancienne"])
            self.assertEqual(self.module.nouveautes_du_changelog(dossier, "3.0.0"), [])
            changelog.unlink()
            self.assertEqual(self.module.nouveautes_du_changelog(dossier, "2.0.0"), [])


if __name__ == "__main__":
    unittest.main()
