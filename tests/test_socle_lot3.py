"""Tests du socle du lot 3 (tâche T41, ARCHITECTURE.md §15.1).

Familles (le nom du test le dit) :
    echarts   : ECharts absent à l'état « prêt » (index.html ne le référence pas), puis chargé à la
                demande par App.chargerEcharts() (une seule balise <script>), utilisable, y compris le
                rendu SVG hors écran (renderToSVGString) qui servira au rapport mensuel ; un échec de
                chargement rejette la promesse avec un message clair et permet un nouvel essai ; même
                chose en file:// (mode démo) ;
    document  : un document « .html » est accepté par serveur.py (201), relu avec le type
                text/html et la politique « sandbox » (aucun script ne s'y exécute) ;
    adresse   : App.urlFicheEquipement prend le paramètre adresse_qr quand c'est une adresse http(s),
                sinon la première adresse détectée ; App.adressesReseau() rend une copie (démo : []) ;
    objets    : objets globaux du lot 3 créés par les fichiers d'attente, icônes du lot 3 présentes.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_socle_lot3.py" -v
"""
import csv
import http.client
import io
import re
import unittest
from pathlib import Path

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier

# Rendu SVG hors écran, comme le fera le rapport mensuel (§15.10).
RENDU_SVG_JS = """async () => {
  const lib = await App.chargerEcharts();
  const graphique = lib.init(null, null, { renderer: 'svg', ssr: true, width: 300, height: 160 });
  graphique.setOption({ animation: false, xAxis: { type: 'category', data: ['a', 'b'] },
                        yAxis: { type: 'value' }, series: [{ type: 'bar', data: [3, 5] }] });
  const svg = graphique.renderToSVGString();
  graphique.dispose();
  return svg;
}"""


def ecrire_parametre(dossier, cle, valeur):
    """Remplace (ou ajoute) une clé de parametres.csv, au format de Prévo (BOM, « ; », CRLF)."""
    chemin = Path(dossier) / "parametres.csv"
    lignes = list(csv.DictReader(io.StringIO(chemin.read_text(encoding="utf-8-sig")), delimiter=";"))
    for ligne in lignes:
        if ligne["cle"] == cle:
            ligne["valeur"] = valeur
            break
    else:
        lignes.append({"cle": cle, "valeur": valeur})
    tampon = io.StringIO(newline="")
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(["cle", "valeur"])
    for ligne in lignes:
        ecrivain.writerow([ligne["cle"], ligne["valeur"]])
    chemin.write_bytes(b"\xef\xbb\xbf" + tampon.getvalue().encode("utf-8"))


class TestSocleServeur(CasNavigateur):
    """Mode serveur : un serveur.py (copie du jeu de démo) pour la classe, profil responsable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def ouvrir(self):
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(self.serveur.url + "/")
        attendre_pret(self.page)

    def requete(self, methode, chemin, corps=None):
        connexion = http.client.HTTPConnection("127.0.0.1", self.serveur.port, timeout=20)
        try:
            connexion.putrequest(methode, chemin, skip_host=True, skip_accept_encoding=True)
            connexion.putheader("Host", "127.0.0.1:%d" % self.serveur.port)
            if methode == "PUT":
                connexion.putheader("X-Prevo", "1")
            if corps is not None:
                connexion.putheader("Content-Length", str(len(corps)))
            connexion.endheaders()
            if corps:
                connexion.send(corps)
            reponse = connexion.getresponse()
            return reponse.status, {n.lower(): v for n, v in reponse.getheaders()}, reponse.read()
        finally:
            connexion.close()

    # -- echarts ---------------------------------------------------------------------------------

    def test_echarts_absent_a_l_etat_pret_puis_charge_a_la_demande_et_rend_du_svg(self):
        self.ouvrir()
        self.assertEqual(self.page.evaluate("typeof echarts"), "undefined")
        self.assertEqual(self.page.locator("script[src*='echarts']").count(), 0)
        self.assertNotIn("echarts", (RACINE / "index.html").read_text(encoding="utf-8"))

        # La bibliothèque embarquée est ECharts 5.5.1 (avec zrender 5.6.0 : js/lib/LICENCES.txt).
        version = self.page.evaluate("async () => (await App.chargerEcharts()).version")
        self.assertEqual(version, "5.5.1")
        # Un second appel réutilise la bibliothèque : une seule balise <script>
        self.assertTrue(self.page.evaluate("async () => (await App.chargerEcharts()) === echarts"))
        self.assertEqual(self.page.locator("script[src*='echarts']").count(), 1)

        svg = self.page.evaluate(RENDU_SVG_JS)
        self.assertTrue(svg.startswith("<svg"), svg[:80])
        self.assertIn("</svg>", svg)
        self.assertNotIn("<script", svg)

    def test_echarts_un_echec_rejette_la_promesse_puis_un_nouvel_essai_reussit(self):
        self.autoriser_erreur("Failed to load resource")
        self.autoriser_erreur("ERR_FAILED")
        echecs = {"restant": 1}

        def intercepter(route):
            if echecs["restant"]:
                echecs["restant"] -= 1
                route.abort()
            else:
                route.continue_()

        self.page.route(re.compile(r".*/js/lib/echarts\.min\.js$"), intercepter)
        self.ouvrir()
        message = self.page.evaluate(
            "async () => { try { await App.chargerEcharts(); return 'chargé'; } catch (e) { return e.message; } }")
        self.assertIn("echarts.min.js", message)
        self.assertIn("pas pu être chargée", message)
        self.assertEqual(self.page.evaluate("typeof echarts"), "undefined")
        self.assertEqual(self.page.evaluate("async () => typeof (await App.chargerEcharts()).init"), "function")

    # -- document --------------------------------------------------------------------------------

    def test_document_html_accepte_et_servi_en_bac_a_sable(self):
        contenu = "<!doctype html><title>Rapport</title><p>Données au 01/10</p>".encode("utf-8")
        statut, _, corps = self.requete("PUT", "/api/documents/rapport-mensuel-test-socle.html", contenu)
        self.assertEqual(statut, 201, corps)
        statut, entetes, corps = self.requete("GET", "/api/documents/rapport-mensuel-test-socle.html")
        self.assertEqual(statut, 200)
        self.assertEqual(corps, contenu)
        self.assertEqual(entetes["content-type"], "text/html; charset=utf-8")
        self.assertEqual(entetes["content-security-policy"], "sandbox")
        self.assertEqual(entetes["x-content-type-options"], "nosniff")
        # Jamais d'écrasement : le même nom est refusé (409)
        statut, _, _ = self.requete("PUT", "/api/documents/rapport-mensuel-test-socle.html", b"v2")
        self.assertEqual(statut, 409)
        # « .htm » reste refusé
        statut, _, _ = self.requete("PUT", "/api/documents/page.htm", b"<p>x</p>")
        self.assertEqual(statut, 400)

    def test_document_html_ecrit_par_l_application(self):
        self.ouvrir()
        nom = self.page.evaluate("""async () => App.adaptateur.ecrireDocument('rapport-socle-app.html',
            new Blob(['<!doctype html><title>R</title>'], { type: 'text/html' }))""")
        self.assertEqual(nom, "rapport-socle-app.html")
        self.assertTrue((Path(self.serveur.dossier) / "documents" / "rapport-socle-app.html").is_file())

    # -- adresse ---------------------------------------------------------------------------------

    def test_adresse_qr_prise_quand_c_est_une_adresse_sinon_la_premiere_detectee(self):
        ecrire_parametre(self.serveur.dossier, "adresse_qr", "http://atelier-pc.local:8080/")
        try:
            self.ouvrir()
            self.assertEqual(self.page.evaluate("App.urlFicheEquipement('EQ-0005')"),
                             "http://atelier-pc.local:8080/#/equipement/EQ-0005")
            adresses = self.page.evaluate("App.adressesReseau()")
            self.assertIsInstance(adresses, list)
            # Une copie : la modifier ne change pas la liste de l'application
            self.assertEqual(self.page.evaluate(
                "(() => { const a = App.adressesReseau(); a.push('x'); return App.adressesReseau().length; })()"),
                len(adresses))
        finally:
            ecrire_parametre(self.serveur.dossier, "adresse_qr", "pas une adresse")
        self.page.goto(self.serveur.url + "/")
        attendre_pret(self.page)
        url = self.page.evaluate("App.urlFicheEquipement('EQ-0005')")
        attendue = (self.page.evaluate("App.adressesReseau()") or [self.serveur.url + "/"])[0]
        self.assertEqual(url, attendue.rstrip("/") + "/#/equipement/EQ-0005")
        ecrire_parametre(self.serveur.dossier, "adresse_qr", "")

    # -- objets ----------------------------------------------------------------------------------

    def test_objets_du_lot3_et_icones(self):
        self.ouvrir()
        types = self.page.evaluate("""() => ({
            Equipe: typeof Equipe, Controles: typeof Controles, Planning: typeof Planning,
            Indicateurs: typeof Indicateurs, Rapport: typeof Rapport,
            parc: typeof Parc.libelleEquipement, parametres: typeof Parametres.decrireSauvegarde })""")
        self.assertEqual(types, {"Equipe": "object", "Controles": "object", "Planning": "object",
                                 "Indicateurs": "object", "Rapport": "object",
                                 "parc": "function", "parametres": "function"})
        icones = self.page.evaluate("UI.nomsIcones()")
        for nom in ("planning", "controles", "indicateurs", "equipe"):
            with self.subTest(icone=nom):
                self.assertIn(nom, icones)
                self.assertIn("<svg", self.page.evaluate("(n) => String(UI.icone(n))", nom))


class TestSocleDemo(CasNavigateur):
    """Mode démo en file:// : ECharts se charge aussi à la demande ; aucune adresse réseau."""

    def test_echarts_en_file_mode_demo_et_adresses_vides(self):
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("typeof echarts"), "undefined")
        svg = self.page.evaluate(RENDU_SVG_JS)
        self.assertTrue(svg.startswith("<svg"), svg[:80])
        self.assertEqual(self.page.evaluate("App.adressesReseau()"), [])
        self.assertEqual(self.page.evaluate("App.urlFicheEquipement('EQ-0005')"), "GMAO:EQ-0005")

    def test_document_html_isole_en_demo_aucun_script_execute(self):
        # Correction de relecture : hors serveur, un document .html ouvert par Prévo ne doit
        # exécuter aucun script (page enveloppe + cadre isolé sans scripts).
        # Le navigateur dit qu'il a bloqué le script du cadre isolé : c'est la preuve attendue.
        self.autoriser_erreur("Blocked script execution")
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        resultat = self.page.evaluate("""async () => {
            const piege = '<p id="texte">Rapport</p><script>window.top.__piege = 1; document.title = "PIEGE";</' + 'script>';
            await App.adaptateur.ecrireDocument('rapport-piege.html', new Blob([piege], { type: 'text/html' }));
            const adresse = await App.adaptateur.urlDocument('rapport-piege.html');
            const page = new DOMParser().parseFromString(await (await fetch(adresse)).text(), 'text/html');
            const cadre = document.createElement('iframe');
            cadre.src = adresse;
            await new Promise((resoudre) => { cadre.onload = resoudre; document.body.appendChild(cadre); });
            await new Promise((resoudre) => setTimeout(resoudre, 300));
            return { scripts: page.scripts.length, sandbox: page.querySelector('iframe').getAttribute('sandbox'),
                     piege: window.__piege === undefined ? null : window.__piege,
                     titre: page.title, srcdoc: page.querySelector('iframe').getAttribute('srcdoc').includes('Rapport') };
        }""")
        self.assertEqual(resultat, {"scripts": 0, "sandbox": "allow-modals", "piege": None,
                                    "titre": "rapport-piege.html", "srcdoc": True})
        self.assertTrue(any("Blocked script execution" in erreur for erreur in self.erreurs_console), self.erreurs_console)


if __name__ == "__main__":
    unittest.main()
