"""« Suggérer une amélioration » (T306 ; D177, CS158).

Un lien dans « À propos » et au pied du menu, pour les trois profils, ouvre dans un nouvel onglet le formulaire
d'issue GitHub, pré-rempli avec la seule version de Prévo, la langue active et le navigateur réduit à
« nom version, système ». Repli : mailto:contact@prevo.pro au même contenu. Ce qui est vérifié (sans jamais naviguer
vers GitHub : on lit l'attribut href) :
    lien         présent dans À propos et dans le menu, target _blank, rel noopener noreferrer, pour le responsable,
                 le technicien et le demandeur ;
    adresse      dépôt, modèle d'issue (français ; anglais si Prévo est en anglais), titre, version, langue, navigateur
                 réduit ; rien d'autre (aucun nom de la démo, ni de l'entreprise ni des techniciens) ;
    courriel     le lien « par e-mail » porte le même contenu ;
    silence      aucune requête vers github.com au chargement ni à l'affichage de À propos ;
    navigateur   la réduction sur des chaînes User-Agent connues ;
    modèles      les deux formulaires d'issue portent le champ « contexte ».

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_suggestion.py" -v
"""
import json
import unittest
from urllib.parse import parse_qs, unquote, urlsplit

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil
from test_version_web import version_et_date

TECHNICIEN = "TEC-0001"
MODELES = RACINE / ".github" / "ISSUE_TEMPLATE"
DEPOT = "https://github.com/nicoboy49/prevo"


class CasSuggestion(CasNavigateur):

    def ouvrir(self, serveur, profil="responsable", langue=None, **options):
        self.contexte.close()
        self.contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1440, "height": 900})
        if langue:
            self.contexte.add_init_script("try { localStorage.setItem('prevo.langue', %s); } catch (e) {}" % json.dumps(langue))
        preregler_profil(self.contexte, profil, **options)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)
        self.requetes = []
        self.page.on("request", lambda requete: self.requetes.append(requete.url))
        self.page.goto(serveur.url + "/")
        attendre_pret(self.page, 30000)
        return self.page

    def a_propos(self):
        self.page.evaluate("location.hash = '#/apropos'")
        self.page.wait_for_selector("#apropos-suggestion-lien")

    def parametres_de(self, adresse):
        morceaux = urlsplit(adresse)
        return morceaux, {cle: valeurs[0] for cle, valeurs in parse_qs(morceaux.query, keep_blank_values=True).items()}

    def noms_de_la_demo(self):
        """Tout nom que l'adresse ne doit jamais contenir : entreprise, techniciens (noms, prénoms, identifiants)."""
        noms = self.page.evaluate("""() => {
            const sortie = [String(Donnees.parametre('entreprise_nom', '')).trim()];
            for (const t of Donnees.lignes('techniciens')) {
                for (const champ of ['nom', 'prenom', 'id']) if (t[champ]) sortie.push(String(t[champ]).trim()); }
            return sortie; }""")
        noms = [n for n in noms if len(n) >= 3]
        self.assertTrue(noms, "la démo doit fournir des noms à ne pas retrouver dans l'adresse")
        return noms


class TestLien(CasSuggestion):

    def verifier_lien(self, selecteur):
        lien = self.page.locator(selecteur)
        self.assertTrue(lien.is_visible(), selecteur)
        self.assertEqual(lien.get_attribute("target"), "_blank")
        self.assertEqual(lien.get_attribute("rel"), "noopener noreferrer")
        self.assertEqual(lien.inner_text().strip(), "Suggérer une amélioration")
        return lien.get_attribute("href")

    def test_present_dans_a_propos_et_le_menu_pour_les_trois_profils(self):
        with ServeurPrevo() as serveur:
            for profil, options in (("responsable", {"nom": "Test Responsable"}), ("technicien", {"nom": "Test Technicien", "technicien_id": TECHNICIEN}),
                                   ("demandeur", {"nom": "Karim Benali"})):
                with self.subTest(profil=profil):
                    self.ouvrir(serveur, profil, **options)
                    dans_menu = self.verifier_lien("#menu-suggestion-lien")
                    self.a_propos()
                    dans_apropos = self.verifier_lien("#apropos-suggestion-lien")
                    self.assertEqual(dans_menu, dans_apropos)

    def test_adresse_ouverte_version_langue_navigateur_et_rien_d_autre(self):
        version = version_et_date()[0]
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur)
            self.a_propos()
            adresse = self.page.locator("#apropos-suggestion-lien").get_attribute("href")
            morceaux, parametres = self.parametres_de(adresse)
            self.assertEqual(morceaux.scheme + "://" + morceaux.netloc + morceaux.path, DEPOT + "/issues/new")
            self.assertEqual(sorted(parametres), ["contexte", "template", "title"])
            self.assertEqual(parametres["template"], "2-proposer-une-amelioration.yml")
            self.assertEqual(parametres["title"], "[Amélioration] ")
            lignes = parametres["contexte"].split("\n")
            self.assertEqual(len(lignes), 3, parametres["contexte"])
            self.assertEqual(lignes[0], "Version de Prévo : " + version)
            self.assertEqual(lignes[1], "Langue : fr")
            attendu = self.page.evaluate("Apropos.navigateurReduit(navigator.userAgent, navigator.userAgentData)")
            self.assertEqual(lignes[2], "Navigateur : " + attendu)
            self.assertRegex(attendu, r"^(Chrome|Edge) \d+, (Windows|macOS|Linux)$")
            texte = unquote(adresse)
            for nom in self.noms_de_la_demo():
                self.assertNotIn(nom.lower(), texte.lower(), nom)

    def test_prevo_en_anglais_ouvre_le_modele_anglais(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, langue="en")
            self.a_propos()
            _, parametres = self.parametres_de(self.page.locator("#apropos-suggestion-lien").get_attribute("href"))
            self.assertEqual(parametres["template"], "3-suggest-an-improvement.yml")
            self.assertEqual(parametres["title"], "[Improvement] ")
            self.assertIn("Language: en", parametres["contexte"])
            self.assertEqual(self.page.locator("#apropos-suggestion-lien").inner_text().strip(), "Suggest an improvement")
            self.assertEqual(self.page.locator("#menu-suggestion-lien").inner_text().strip(), "Suggest an improvement")

    def test_mention_traduction_automatique_seulement_pour_une_langue_automatique(self):
        """T343 (CS161) : français et anglais, aucune mention ; une langue déclarée « automatique » (ici tr, déclarée par
        la copie servie de langues.js : la déclaration réelle vient à la fin du Lot 5) : « Traduction automatique —
        corrections bienvenues » au pied du menu, dans « Ce poste » et dans « À propos », lien vers le formulaire
        « Corriger une traduction » avec la langue et le contexte, nouvel onglet."""
        version = version_et_date()[0]
        with ServeurPrevo() as serveur:
            for langue in (None, "en"):
                with self.subTest(langue=langue):
                    self.ouvrir(serveur, langue=langue)
                    self.a_propos()
                    self.assertEqual(self.page.locator("#menu-traduction-lien, #apropos-traduction-lien").count(), 0)
                    self.assertEqual(self.page.locator("#menu-traduction").inner_html().strip(), "")
            declaration = ("\nI18n.declarer({ code: 'tr', nom: 'Türkçe', locale: 'tr-TR', statut: 'automatique', "
                           "aide: 'en' });\n")
            langues = (RACINE / "js" / "i18n" / "langues.js").read_text(encoding="utf-8") + declaration
            self.ouvrir_avec(serveur, "tr", lambda contexte: contexte.route("**/js/i18n/langues.js", lambda route: route.fulfill(
                status=200, content_type="text/javascript; charset=utf-8", body=langues)))
            self.assertEqual(self.page.evaluate("I18n.langue"), "tr")
            adresses = []
            for selecteur, ecran in (("#menu-traduction-lien", None), ("#apropos-traduction-lien", "#/apropos"),
                                     ("#poste-traduction-lien", "#/poste")):
                with self.subTest(selecteur=selecteur):
                    if ecran:
                        self.page.evaluate("(route) => { location.hash = route; }", ecran)
                        self.page.wait_for_selector(selecteur)
                    lien = self.page.locator(selecteur)
                    self.assertTrue(lien.is_visible(), selecteur)
                    self.assertEqual(lien.get_attribute("target"), "_blank")
                    self.assertEqual(lien.get_attribute("rel"), "noopener noreferrer")
                    adresses.append(lien.get_attribute("href"))
            self.assertEqual(len(set(adresses)), 1, adresses)
            morceaux, parametres = self.parametres_de(adresses[0])
            self.assertEqual(morceaux.scheme + "://" + morceaux.netloc + morceaux.path, DEPOT + "/issues/new")
            self.assertEqual(sorted(parametres), ["contexte", "langue", "template", "title"])
            self.assertEqual(parametres["template"], "4-corriger-une-traduction.yml")
            self.assertEqual(parametres["langue"], "tr")
            self.assertIn(version, parametres["contexte"])
            self.assertTrue((MODELES / parametres["template"]).is_file())

    def ouvrir_avec(self, serveur, langue, preparer):
        """Comme ouvrir(), avec une préparation du contexte (routes) avant le premier chargement."""
        self.contexte.close()
        self.contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1440, "height": 900})
        self.contexte.add_init_script("try { localStorage.setItem('prevo.langue', %s); } catch (e) {}" % json.dumps(langue))
        preparer(self.contexte)
        preregler_profil(self.contexte, "responsable")
        self.page = self.contexte.new_page()
        self.surveiller(self.page)
        self.page.goto(serveur.url + "/")
        attendre_pret(self.page, 30000)
        return self.page

    def test_repli_par_courriel_meme_contenu(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur)
            self.a_propos()
            _, github = self.parametres_de(self.page.locator("#apropos-suggestion-lien").get_attribute("href"))
            courriel = self.page.locator("#apropos-suggestion-courriel").get_attribute("href")
            self.assertTrue(courriel.startswith("mailto:contact@prevo.pro?"), courriel)
            _, parametres = self.parametres_de(courriel)
            self.assertEqual(sorted(parametres), ["body", "subject"])
            self.assertEqual(parametres["body"], github["contexte"])

    def test_aucune_requete_vers_github_sans_clic(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur)
            self.a_propos()
            self.page.wait_for_timeout(500)
            # prevo.pro/version.json (T305, vérification de version, servie par le contexte des tests) n'est pas le lien.
            self.assertEqual([u for u in self.requetes if "github" in u], [])


class TestReduction(CasSuggestion):

    def test_navigateur_reduit_sur_des_chaines_connues(self):
        cas = [
            ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
             None, "Chrome 130, Windows"),
            ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.2903.51",
             None, "Edge 131, Windows"),
            ("Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0", None, "Firefox 132, Linux"),
            ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
             None, "Safari 17, iOS"),
            ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
             None, "Safari 17, macOS"),
            ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
             None, "Chrome 130, Android"),
            ("Mozilla/5.0 (Windows NT 10.0) Chrome/130.0.0.0", {"brands": [{"brand": "Not;A=Brand", "version": "24"},
             {"brand": "Chromium", "version": "130"}, {"brand": "Microsoft Edge", "version": "130"}], "platform": "Windows"},
             "Edge 130, Windows"),
            ("Mozilla/5.0 (X11; Linux x86_64) Chrome/129.0.0.0", {"brands": [{"brand": "Google Chrome", "version": "129"}],
             "platform": "macOS"}, "Chrome 129, macOS"),
            ("curl/8.4.0", None, "navigateur inconnu"),
            ("", None, "navigateur inconnu"),
        ]
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur)
            for ua, donnees, attendu in cas:
                with self.subTest(ua=ua[:60]):
                    obtenu = self.page.evaluate("([ua, donnees]) => Apropos.navigateurReduit(ua, donnees)", [ua, donnees])
                    self.assertEqual(obtenu, attendu)


class TestModeles(unittest.TestCase):

    def test_les_deux_formulaires_portent_le_champ_contexte(self):
        for nom in ("2-proposer-une-amelioration.yml", "3-suggest-an-improvement.yml", "4-corriger-une-traduction.yml"):
            with self.subTest(modele=nom):
                texte = (MODELES / nom).read_text(encoding="utf-8")
                self.assertIn("    id: contexte\n", texte)
                self.assertNotIn("\r", texte)
        self.assertIn("blank_issues_enabled: false", (MODELES / "config.yml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
