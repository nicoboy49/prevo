"""Tests du moteur de traduction js/i18n.js (objet I18n) et de son chargement (chantier multilingue, Lot 2, T234 ;
contrat du Lot 2 ; ARCHITECTURE.md §1 ; D147).

Sans navigateur :
    - fichiers : js/i18n/fr.js a un bloc par section du contrat, dans l'ordre et bien formé ; js/i18n/aide/fr.js ;
      js/i18n/langues.js déclare le français puis l'anglais (en-GB, T278) ;
    - chargement : index.html charge js/i18n.js, langues.js, fr.js, aide/fr.js et js/i18n-chargeur.js juste avant
      js/schema.js ; acces/porte.html charge le moteur, les langues, fr.js et le chargeur (T297) avant porte.js ;
    - serveur.py : js/i18n/… et js/i18n/aide/… dans la liste blanche ; la porte sert js/i18n.js, js/i18n/ et
      js/i18n-chargeur.js (T297), rien d'autre de js/ ;
    - release (fichiers_a_inclure) et démo web (construire) : js/i18n.js, js/i18n-chargeur.js et js/i18n/ embarqués.
Dans Chromium :
    - interpolation {nom} ; pluriels Intl.PluralRules (français : 0 et 1 au singulier, 2 au pluriel ; langue d'essai en
      locale « pl » : one, few, many, other ; catégorie absente : other ; n absent : other) ;
    - repli : langue active, puis français, puis la clé, console.warn une seule fois par clé ; clés aide.* : français
      sans avertissement ;
    - I18n.html : balisage du dictionnaire gardé, valeur « <script> » échappée, accepté par UI.html et UI.remplir
      sans double échappement ; sans UI (porte) : fragment qui se convertit en chaîne ;
    - data-i18n et data-i18n-attr (I18n.appliquer) ;
    - chargeur : langue d'essai « xx » (js/i18n/xx.js et js/i18n/aide/xx.js écrits dans une COPIE servie de
      l'application, jamais dans le dépôt) choisie avant le chargement par localStorage « prevo.langue » : ses textes
      sont pris AVANT js/schema.js (sonde placée juste avant js/schema.js dans la copie : elle lit une clé pendant le
      chargement), en http, en file:// et sous la vraie politique de sécurité du contenu (script-src 'self') ; langue
      non déclarée ou mal formée : français, sans erreur ni requête ; chargeur ajouté après l'analyse : page intacte ;
      I18n.appliquer(document) au démarrage de l'application ;
    - index.html en file:// et avec serveur.py (ServeurPrevo), acces/porte.html servie : sans erreur console ;
    - sélecteur de langue (T278, D147, D148) : au pied du menu et à l'écran « Ce poste », les langues déclarées sous
      leur nom dans leur langue ; English choisi → page rechargée en anglais (lang="en", menu, nombres en-GB), sans
      erreur ni clé absente ; Français → page française (lang="fr", clé retirée) ; stockage refusé : message, la page
      reste dans sa langue, sans erreur.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_i18n.py" -v
"""
import importlib.util
import re
import shutil
import tempfile
import unittest
import urllib.request
from pathlib import Path

from commun import (RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret, charger_scripts,
                    preregler_profil, url_fichier)

# Sections de js/i18n/fr.js : recopie du contrat du Lot 2, dans l'ordre.
SECTIONS = ("commun schema valeurs socle planning causes dictee mise aide ordres demandes parc preventif controles "
            "garanties wiki suggestions import magasin indicateurs rapport accueil equipe acces connexion poste apropos "
            "installation porte parametres sauvegardes zip serveur ia").split()
SCRIPTS_I18N = ["js/i18n.js", "js/i18n/langues.js", "js/i18n/fr.js", "js/i18n/aide/fr.js", "js/i18n-chargeur.js"]
SCRIPTS_PORTE = ["/js/i18n.js", "/js/i18n/langues.js", "/js/i18n/fr.js", "/js/i18n-chargeur.js", "/acces/porte.js"]
FICHIERS_I18N = ["js/i18n.js", "js/i18n-chargeur.js", "js/i18n/langues.js", "js/i18n/fr.js", "js/i18n/aide/fr.js",
                 "js/i18n/en.js", "js/i18n/aide/en.js"]
# Langues déclarées par js/i18n/langues.js (T278), dans l'ordre du sélecteur : code, nom dans sa langue, locale, statut.
LANGUES = [{"code": "fr", "nom": "Français", "locale": "fr-FR", "statut": "reference"},
           {"code": "en", "nom": "English", "locale": "en-GB", "statut": "complete"},
           # Lot 5 (T375) : traductions automatiques, aide longue en anglais (D158)
           {"code": "tr", "nom": "Türkçe", "locale": "tr-TR", "statut": "automatique", "aide": "en"},
           {"code": "it", "nom": "Italiano", "locale": "it-IT", "statut": "automatique", "aide": "en"},
           {"code": "pt-PT", "nom": "Português", "locale": "pt-PT", "statut": "automatique", "aide": "en"}]
CODES = [langue["code"] for langue in LANGUES]
ERREUR_PING_ABSENT = re.compile(r"status of 404.*/api/ping")      # serveur statique : pas de /api/ping
ERREUR_SANS_AUTORITE = re.compile(r"status of 404.*/acces/ca\.crt")   # porte sans autorité locale (MESSAGE_SANS_AUTORITE)

MOTIF_COMMENTAIRE_HTML = re.compile(r"<!--.*?-->", re.DOTALL)
MOTIF_SCRIPT_SRC = re.compile(r"""<script\b[^>]*?\ssrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)

# Espion de console.warn : chaque avertissement est noté dans window.avertissements (et n'est plus écrit).
ESPION_AVERTISSEMENTS_JS = "() => { window.avertissements = []; console.warn = (...morceaux) => " \
                           "{ window.avertissements.push(morceaux.join(' ')); }; }"

# Langue d'essai écrite dans la copie servie (jamais dans le dépôt) ; locale « pl » : catégories one, few, many, other.
DECLARATION_ESSAI = ("I18n.declarer({ code: 'xx', nom: 'Essai', locale: 'pl', statut: 'automatique' });\n"
                     # T343 (D158) : langue d'essai sans aide longue, qui la prend en anglais (comme tr, it, pt-PT).
                     "I18n.declarer({ code: 'yy', nom: 'Essai Y', locale: 'tr', statut: 'automatique', aide: 'en' });\n")
FICHIER_ESSAI_Y = ("'use strict';\n// Langue d'essai « yy » de tests/test_i18n.py (copie servie seulement), aide longue en anglais.\n"
                   "I18n.ajouter('yy', {\n  'essai.chargement': 'Texte de la langue d\\'essai Y',\n});\n")
FICHIER_ESSAI = ("'use strict';\n// Langue d'essai de tests/test_i18n.py (copie servie seulement).\n"
                 "I18n.ajouter('xx', {\n  'essai.appliquer': 'Appliqué en xx',\n"
                 "  'essai.chargement': 'Texte de la langue d\\'essai',\n});\n")
AIDE_ESSAI = "'use strict';\nI18n.ajouter('xx', {\n  'aide.essai.xx': 'Aide de la langue d\\'essai',\n});\n"
AJOUT_FR = ("I18n.ajouter('fr', {\n  'aide.essai.fr': 'Aide française',\n  'essai.appliquer': 'Appliqué en français',\n"
            "  'essai.chargement': 'Texte français',\n});\n")
# Sonde placée juste avant js/schema.js dans la copie : ce qu'elle lit l'est PENDANT le chargement, avant le schéma.
SONDE = ("'use strict';\nwindow.sondeI18n = { langue: I18n.langue, texte: I18n.t('essai.chargement'),\n"
         "  aideXx: I18n.t('aide.essai.xx'), aideFr: I18n.t('aide.essai.fr'), schemaCharge: typeof Schema !== 'undefined' };\n")
PIED = '<p class="demarrage-pied">'
PIED_TRADUIT = '<p class="demarrage-pied" data-i18n="essai.appliquer">'
TEXTE_XX = "Texte de la langue d'essai"


def scripts_de_la_page(texte):
    return MOTIF_SCRIPT_SRC.findall(MOTIF_COMMENTAIRE_HTML.sub("", texte))


def charger_module(chemin, nom):
    """Importe un fichier Python du projet comme module (sans le lancer)."""
    specification = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_module(RACINE / "serveur.py", "serveur_prevo_i18n")


def preparer_copie(racine):
    """Copie de l'application (index.html, favicon, css/, js/) dans `racine`, avec la langue d'essai « xx » déclarée, ses
    deux fichiers, des clés françaises de comparaison, la sonde avant js/schema.js et un data-i18n dans index.html."""
    for nom in ("index.html", "favicon.svg"):
        shutil.copyfile(RACINE / nom, racine / nom)
    for nom in ("css", "js"):
        shutil.copytree(RACINE / nom, racine / nom)
    i18n = racine / "js" / "i18n"
    with open(i18n / "langues.js", "a", encoding="utf-8", newline="\n") as fichier:
        fichier.write(DECLARATION_ESSAI)
    with open(i18n / "fr.js", "a", encoding="utf-8", newline="\n") as fichier:
        fichier.write(AJOUT_FR)
    (i18n / "xx.js").write_text(FICHIER_ESSAI, encoding="utf-8", newline="\n")
    (i18n / "aide" / "xx.js").write_text(AIDE_ESSAI, encoding="utf-8", newline="\n")
    (i18n / "yy.js").write_text(FICHIER_ESSAI_Y, encoding="utf-8", newline="\n")     # sans aide/yy.js (D158)
    (racine / "js" / "sonde-i18n.js").write_text(SONDE, encoding="utf-8", newline="\n")
    page = (racine / "index.html").read_text(encoding="utf-8")
    schema = '<script src="js/schema.js"></script>'
    assert page.count(schema) == 1 and PIED in page
    # Le premier pied de page est celui de l'écran de démarrage (celui que lit querySelector).
    page = page.replace(schema, '<script src="js/sonde-i18n.js"></script>\n' + schema).replace(PIED, PIED_TRADUIT, 1)
    (racine / "index.html").write_text(page, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Sans navigateur : fichiers, chargement, serveur, release
# ---------------------------------------------------------------------------

class TestFichiers(unittest.TestCase):

    def test_fr_un_bloc_par_section_dans_l_ordre(self):
        texte = (RACINE / "js" / "i18n" / "fr.js").read_text(encoding="utf-8")
        self.assertTrue(texte.startswith("'use strict';\n"))
        self.assertEqual(re.findall(r"^// ==== section (\S+) ====$", texte, re.MULTILINE), SECTIONS)
        self.assertEqual(re.findall(r"^// ==== fin (\S+) ====$", texte, re.MULTILINE), SECTIONS)
        for section in SECTIONS:
            with self.subTest(section=section):
                motif = (r"^// ==== section %s ====\nI18n\.ajouter\('fr', \{\n(?:  '[^\n]*\n)*\}\);\n// ==== fin %s ====$"
                         % (re.escape(section), re.escape(section)))
                self.assertRegex(texte, re.compile(motif, re.MULTILINE))

    def test_aide_et_langues(self):
        aide = (RACINE / "js" / "i18n" / "aide" / "fr.js").read_text(encoding="utf-8")
        self.assertTrue(aide.startswith("'use strict';\n"))
        self.assertIn("I18n.ajouter('fr', {\n", aide)
        langues = (RACINE / "js" / "i18n" / "langues.js").read_text(encoding="utf-8")
        declarations = re.findall(r"^I18n\.declarer\(\{ code: '([^']*)', nom: '([^']*)', locale: '([^']*)', "
                                  r"statut: '([^']*)'(?:, aide: '([^']*)')? \}\);$", langues, re.MULTILINE)
        self.assertEqual(declarations, [tuple(langue.values()) + ("",) * (5 - len(langue)) for langue in LANGUES])
        self.assertEqual(langues.count("I18n.declarer("), len(LANGUES))

    def test_index_charge_la_traduction_juste_avant_le_schema(self):
        scripts = scripts_de_la_page((RACINE / "index.html").read_text(encoding="utf-8"))
        debut = scripts.index("js/schema.js") - len(SCRIPTS_I18N)
        self.assertEqual(scripts[debut:debut + len(SCRIPTS_I18N) + 1], SCRIPTS_I18N + ["js/schema.js"])

    def test_porte_charge_le_moteur_et_le_francais(self):
        scripts = scripts_de_la_page((RACINE / "acces" / "porte.html").read_text(encoding="utf-8"))
        self.assertEqual(scripts, SCRIPTS_PORTE)


class TestServeurEtRelease(unittest.TestCase):

    def test_le_serveur_sert_les_textes_de_toutes_les_langues(self):
        for chemin in (["js", "i18n.js"], ["js", "i18n-chargeur.js"], ["js", "i18n", "fr.js"],
                       ["js", "i18n", "langues.js"], ["js", "i18n", "aide", "fr.js"], ["js", "i18n", "pt-PT.js"]):
            with self.subTest(chemin="/".join(chemin)):
                self.assertTrue(serveur.chemin_public(chemin, False))

    def test_la_porte_sert_les_textes_et_rien_d_autre_de_js(self):
        for chemin in (["js", "i18n.js"], ["js", "i18n", "fr.js"], ["js", "i18n", "langues.js"],
                       ["js", "i18n", "aide", "fr.js"], ["js", "i18n-chargeur.js"]):
            with self.subTest(chemin="/".join(chemin)):
                self.assertTrue(serveur.fichier_de_la_porte(chemin))
        for chemin in (["js", "app.js"], ["js", "interface.js"], ["js", "schema.js"], ["js", "i18n-chargeur.js.bak"],
                       ["js", "i18n"], ["js", "i18n.js.bak"], ["js", "lib", "qrcode.js"], ["index.html"],
                       ["acces", "porte.html"], ["donnees", "equipements.csv"]):
            with self.subTest(chemin="/".join(chemin)):
                self.assertFalse(serveur.fichier_de_la_porte(chemin))

    def test_la_release_embarque_la_traduction(self):
        release = charger_module(RACINE / "outils" / "construire_release.py", "construire_release_i18n")
        fichiers = release.fichiers_a_inclure(RACINE)
        for chemin in FICHIERS_I18N:
            with self.subTest(chemin=chemin):
                self.assertIn(chemin, fichiers)

    def test_la_demo_web_embarque_la_traduction(self):
        demo = charger_module(RACINE / "outils" / "construire_demo_web.py", "construire_demo_web_i18n")
        dossier = Path(tempfile.mkdtemp(prefix="prevo-i18n-demo-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        sortie = demo.construire(dossier / "demo-web")
        for chemin in FICHIERS_I18N:
            with self.subTest(chemin=chemin):
                self.assertEqual((sortie / chemin).read_bytes(), (RACINE / chemin).read_bytes())


# ---------------------------------------------------------------------------
# Navigateur : le moteur seul (page vide en file://)
# ---------------------------------------------------------------------------

class TestMoteur(CasNavigateur):

    def ouvrir(self, *autres):
        charger_scripts(self.page, ["js/i18n.js"] + list(autres))
        self.page.evaluate(ESPION_AVERTISSEMENTS_JS)

    def avertissements(self):
        return self.page.evaluate("window.avertissements")

    def test_interpolation_et_langues_declarees(self):
        self.ouvrir("js/i18n/langues.js")
        resultat = self.page.evaluate("""() => {
          I18n.ajouter('fr', { 'essai.semaine': 'Semaine du {date}', 'essai.deux': '{a} et {b}, encore {a}' });
          I18n.ajouter('fr', { 'essai.sans': 'Rien à remplacer', 'essai.deux': '{a} puis {b}, encore {a}' });
          return {
            textes: [I18n.t('essai.semaine', { date: '3 nov.' }), I18n.t('essai.deux', { a: 1, b: 'deux' }),
                     I18n.t('essai.semaine'), I18n.t('essai.semaine', { autre: 'x' }),
                     I18n.t('essai.semaine', { date: null }), I18n.t('essai.semaine', { date: 0 }),
                     I18n.t('essai.sans', { date: 'x' }), I18n.t('essai.semaine', { date: '<b>&' })],
            langue: I18n.langue, langues: I18n.langues,
          };
        }""")
        self.assertEqual(resultat["textes"], ["Semaine du 3 nov.", "1 puis deux, encore 1", "Semaine du {date}",
                                              "Semaine du {date}", "Semaine du ", "Semaine du 0", "Rien à remplacer",
                                              "Semaine du <b>&"])
        self.assertEqual(resultat["langue"], "fr")
        self.assertEqual(resultat["langues"], LANGUES)
        self.assertEqual(self.avertissements(), [])

    def test_pluriels_francais_et_langue_d_essai(self):
        self.ouvrir()
        resultat = self.page.evaluate("""() => {
          I18n.ajouter('fr', { 'essai.ot': { one: '{n} intervention', other: '{n} interventions' } });
          const francais = [0, 1, 2, 3, 1000000, '1'].map((n) => I18n.t('essai.ot', { n }));
          const sansNombre = I18n.t('essai.ot');
          I18n.declarer({ code: 'xx', nom: 'Essai', locale: 'pl', statut: 'automatique' });
          I18n.ajouter('xx', {
            'essai.plik': { one: '{n} plik', few: '{n} pliki', many: '{n} plików', other: '{n} pliku' },
            'essai.incomplet': { one: '{n} un', other: '{n} autre' },
          });
          const choisie = I18n.choisir('xx');
          return {
            francais, sansNombre, choisie, langue: I18n.langue,
            essai: [1, 2, 5, 22, 0, 1.5].map((n) => I18n.t('essai.plik', { n })),
            incomplet: [1, 2, 5].map((n) => I18n.t('essai.incomplet', { n })),
            categories: [1, 2, 5, 1.5].map((n) => new Intl.PluralRules('pl').select(n)),
          };
        }""")
        # 1 000 000 est « many » en français (CLDR) : la catégorie absente donne « other ».
        self.assertEqual(resultat["francais"], ["0 intervention", "1 intervention", "2 interventions",
                                                "3 interventions", "1000000 interventions", "1 intervention"])
        self.assertEqual(resultat["sansNombre"], "{n} interventions")
        self.assertTrue(resultat["choisie"])
        self.assertEqual(resultat["langue"], "xx")
        self.assertEqual(resultat["categories"], ["one", "few", "many", "other"])
        self.assertEqual(resultat["essai"], ["1 plik", "2 pliki", "5 plików", "22 pliki", "0 plików", "1.5 pliku"])
        self.assertEqual(resultat["incomplet"], ["1 un", "2 autre", "5 autre"])
        self.assertEqual(self.avertissements(), [])

    def test_repli_francais_puis_la_cle_avertissement_une_fois_par_cle(self):
        self.ouvrir()
        resultat = self.page.evaluate("""() => {
          I18n.ajouter('fr', { 'essai.fr': 'Texte français', 'essai.commun': 'Commun fr',
                               'essai.ot': { one: '{n} intervention', other: '{n} interventions' } });
          const r = {};
          r.absenteEnFrancais = [I18n.t('essai.absente'), I18n.t('essai.absente')];
          r.avertissementsEnFrancais = window.avertissements.length;
          r.inconnue = I18n.choisir('zz');
          r.langueApresInconnue = I18n.langue;
          I18n.declarer({ code: 'xx', nom: 'Essai', locale: 'pl', statut: 'automatique' });
          I18n.ajouter('xx', { 'essai.commun': 'Commun xx' });
          I18n.choisir('xx');
          r.traduite = I18n.t('essai.commun');
          r.repli = [I18n.t('essai.fr'), I18n.t('essai.fr'), String(I18n.html('essai.fr'))];
          r.absente = [I18n.t('essai.absente2'), I18n.t('essai.absente2'), String(I18n.html('essai.absente2'))];
          r.dejaSignalee = I18n.t('essai.absente');
          // Texte pris en français : règles de pluriel du français (0 au singulier ; « pl » aurait dit many).
          r.plurielDuRepli = I18n.t('essai.ot', { n: 0 });
          r.retourFrancais = I18n.choisir('fr') && I18n.langue;
          return r;
        }""")
        self.assertEqual(resultat["absenteEnFrancais"], ["essai.absente", "essai.absente"])
        self.assertEqual(resultat["avertissementsEnFrancais"], 1)
        self.assertFalse(resultat["inconnue"])
        self.assertEqual(resultat["langueApresInconnue"], "fr")
        self.assertEqual(resultat["traduite"], "Commun xx")
        self.assertEqual(resultat["repli"], ["Texte français"] * 3)
        self.assertEqual(resultat["absente"], ["essai.absente2"] * 3)
        self.assertEqual(resultat["dejaSignalee"], "essai.absente")
        self.assertEqual(resultat["plurielDuRepli"], "0 intervention")
        self.assertEqual(resultat["retourFrancais"], "fr")
        avertissements = self.avertissements()
        self.assertEqual(len(avertissements), 4, avertissements)
        for cle, avertissement in zip(("essai.absente", "essai.fr", "essai.absente2", "essai.ot"), avertissements):
            with self.subTest(cle=cle):
                self.assertIn("« %s »" % cle, avertissement)
        self.assertIn("absente en « xx »", avertissements[1])

    def test_reference_rend_le_francais_quelle_que_soit_la_langue_active(self):
        self.ouvrir()
        resultat = self.page.evaluate("""() => {
          I18n.ajouter('fr', { 'essai.ref': 'Bonjour {nom}', 'essai.refpl': { one: '{n} chose', other: '{n} choses' } });
          I18n.declarer({ code: 'xx', nom: 'Essai', locale: 'pl', statut: 'automatique' });
          I18n.ajouter('xx', { 'essai.ref': 'Hello {nom}' });
          I18n.choisir('xx');
          const avant = window.avertissements.length;
          const r = { active: I18n.t('essai.ref', { nom: 'A' }), ref: I18n.reference('essai.ref', { nom: 'A' }),
                      pluriel: I18n.reference('essai.refpl', { n: 0 }), absente: I18n.reference('essai.nulle_part'),
                      avertissements: window.avertissements.length - avant };
          I18n.choisir('fr');
          return r;
        }""")
        self.assertEqual(resultat, {"active": "Hello A", "ref": "Bonjour A", "pluriel": "0 chose",
                                    "absente": "essai.nulle_part", "avertissements": 0})

    def test_aide_manquante_dans_une_langue_francais_sans_avertissement(self):
        self.ouvrir()
        resultat = self.page.evaluate("""() => {
          I18n.ajouter('fr', { 'aide.essai.texte': 'Aide française', 'aide.essai.autre': 'Autre aide française' });
          I18n.declarer({ code: 'xx', nom: 'Essai', locale: 'pl', statut: 'automatique' });
          I18n.ajouter('xx', { 'aide.essai.autre': 'Autre aide xx' });
          I18n.choisir('xx');
          const textes = [I18n.t('aide.essai.texte'), I18n.t('aide.essai.autre'), String(I18n.html('aide.essai.texte'))];
          const avant = window.avertissements.length;
          // Absente partout, même en français : c'est une erreur du dictionnaire, signalée comme les autres clés.
          const absente = I18n.t('aide.essai.absente');
          return { textes, avant, absente };
        }""")
        self.assertEqual(resultat["textes"], ["Aide française", "Autre aide xx", "Aide française"])
        self.assertEqual(resultat["avant"], 0)
        self.assertEqual(resultat["absente"], "aide.essai.absente")
        self.assertEqual(len(self.avertissements()), 1)

    def test_aide_prise_dans_la_langue_que_la_declaration_designe(self):
        """T343 (D158) : « aide: 'en' » → clés aide.* prises en anglais, sans avertissement, avant le français ; une clé
        aide.* traduite dans la langue active passe avant ; « aide » invalide (français, non déclarée, elle-même) →
        repli habituel sur le français ; les autres clés ne passent jamais par l'anglais."""
        self.ouvrir()
        resultat = self.page.evaluate("""() => {
          I18n.ajouter('fr', { 'aide.essai.texte': 'Aide française', 'aide.essai.propre': 'Propre en français',
                               'aide.essai.seulement_fr': 'Seulement en français', 'essai.ecran': 'Écran français' });
          I18n.declarer({ code: 'en', nom: 'English', locale: 'en-GB', statut: 'complete' });
          I18n.ajouter('en', { 'aide.essai.texte': 'English help', 'aide.essai.propre': 'Own in English',
                               'essai.ecran': 'English screen' });
          I18n.declarer({ code: 'yy', nom: 'Y', locale: 'tr', statut: 'automatique', aide: 'en' });
          I18n.ajouter('yy', { 'aide.essai.propre': 'Kendi yardımı' });
          const repli = [];
          for (const aide of ['fr', 'zz', 'yy', false]) {
            I18n.declarer({ code: 'ww', nom: 'W', locale: 'tr', statut: 'automatique', aide });
            repli.push(I18n.langueDeLAide('ww'));
          }
          I18n.choisir('yy');
          const avant = window.avertissements.length;
          const textes = [I18n.t('aide.essai.texte'), I18n.t('aide.essai.propre'), I18n.t('aide.essai.seulement_fr')];
          const apresAide = window.avertissements.length;
          const ecran = I18n.t('essai.ecran');
          return { langue: I18n.langueDeLAide('yy'), repli, textes, avant, apresAide, ecran };
        }""")
        self.assertEqual(resultat["langue"], "en")
        self.assertEqual(resultat["repli"], [None, None, "yy", None])
        self.assertEqual(resultat["textes"], ["English help", "Kendi yardımı", "Seulement en français"])
        self.assertEqual(resultat["apresAide"], resultat["avant"])              # aide.* : aucun avertissement
        self.assertEqual(resultat["ecran"], "Écran français")                   # hors aide.* : jamais l'anglais
        self.assertEqual(len(self.avertissements()), 1)                         # la clé d'écran absente en « yy »

    def test_html_balisage_garde_valeurs_echappees_pour_ui(self):
        self.ouvrir("js/interface.js")
        resultat = self.page.evaluate("""() => {
          I18n.ajouter('fr', { 'essai.html': 'Bonjour <b>{nom}</b>, voir <a href="#/aide">l\\'aide</a>.',
                               'essai.lien': 'Ouvrir {lien} {liste}',
                               'essai.ot': { one: '<b>{n}</b> intervention', other: '<b>{n}</b> interventions' } });
          const fragment = I18n.html('essai.html', { nom: '<script>alert(1)</script>' });
          const zone = document.createElement('div');
          document.body.appendChild(zone);
          UI.remplir(zone, fragment);
          return {
            sur: UI.estSur(fragment), texte: String(fragment),
            scripts: zone.querySelectorAll('script').length, gras: zone.querySelector('b').textContent,
            liens: zone.querySelectorAll('a').length, gabarit: String(UI.html`<p>${fragment}</p>`),
            imbrique: String(I18n.html('essai.lien', { lien: UI.html`<a href="#/x">${'a&b'}</a>`,
                                                       liste: ['<i>', UI.html`<i>ok</i>`, null, false] })),
            pluriel: String(I18n.html('essai.ot', { n: 2 })),
            brut: I18n.t('essai.html', { nom: '<i>' }),
            absente: String(I18n.html('<essai>')), absenteSure: UI.estSur(I18n.html('<essai>')),
          };
        }""")
        attendu = 'Bonjour <b>&lt;script&gt;alert(1)&lt;/script&gt;</b>, voir <a href="#/aide">l\'aide</a>.'
        self.assertTrue(resultat["sur"])
        self.assertEqual(resultat["texte"], attendu)
        self.assertEqual(resultat["scripts"], 0)
        self.assertEqual(resultat["gras"], "<script>alert(1)</script>")
        self.assertEqual(resultat["liens"], 1)
        self.assertEqual(resultat["gabarit"], "<p>" + attendu + "</p>")          # aucun double échappement
        self.assertEqual(resultat["imbrique"], 'Ouvrir <a href="#/x">a&amp;b</a> &lt;i&gt;<i>ok</i>')
        self.assertEqual(resultat["pluriel"], "<b>2</b> interventions")
        self.assertEqual(resultat["brut"], 'Bonjour <b><i></b>, voir <a href="#/aide">l\'aide</a>.')
        self.assertEqual(resultat["absente"], "&lt;essai&gt;")
        self.assertTrue(resultat["absenteSure"])

    def test_html_sans_ui_fragment_en_chaine(self):
        self.ouvrir()
        resultat = self.page.evaluate("""() => {
          I18n.ajouter('fr', { 'essai.html': 'Bonjour <b>{nom}</b>' });
          const fragment = I18n.html('essai.html', { nom: '<script>x</script>' });
          const zone = document.createElement('div');
          zone.innerHTML = fragment;
          const imbrique = String(I18n.html('essai.html', { nom: fragment }));
          return { type: typeof fragment, texte: String(fragment), gras: zone.querySelector('b').textContent,
                   scripts: zone.querySelectorAll('script').length, imbrique };
        }""")
        self.assertEqual(resultat["type"], "object")
        self.assertEqual(resultat["texte"], "Bonjour <b>&lt;script&gt;x&lt;/script&gt;</b>")
        self.assertEqual(resultat["gras"], "<script>x</script>")
        self.assertEqual(resultat["scripts"], 0)
        self.assertEqual(resultat["imbrique"], "Bonjour <b>Bonjour <b>&lt;script&gt;x&lt;/script&gt;</b></b>")

    def test_formats_de_nombres_suivent_la_locale_de_la_langue_active(self):
        self.ouvrir("js/i18n/langues.js", "js/interface.js")
        resultat = self.page.evaluate("""() => {
          const lire = () => [UI.nombreFr(1234567.5), UI.nombreFr(1234.5, 2), UI.euro(1234.5)];
          const francais = lire();
          I18n.declarer({ code: 'xx', nom: 'Essai', locale: 'en-GB', statut: 'automatique' });
          I18n.choisir('xx');
          const anglais = lire();
          const locale = I18n.locale;
          I18n.choisir('fr');
          return { francais, anglais, locale, retour: lire() };
        }""")
        self.assertEqual(resultat["francais"], ["1 234 567,5", "1 234,50", "1 234,50 €"])
        self.assertEqual(resultat["locale"], "en-GB")
        self.assertEqual(resultat["anglais"], ["1,234,567.5", "1,234.50", "€1,234.50"])
        self.assertEqual(resultat["retour"], resultat["francais"])

    def test_data_i18n_et_data_i18n_attr(self):
        self.ouvrir()
        resultat = self.page.evaluate("""() => {
          I18n.ajouter('fr', { 'essai.titre': 'Titre traduit', 'essai.bulle': 'Bulle traduite',
                               'essai.indice': 'Indice traduit', 'essai.zone': 'Zone traduite' });
          document.body.innerHTML = '<section id="zone" data-i18n-attr="aria-label:essai.zone">'
            + '<h1 id="titre" data-i18n="essai.titre">Ancien titre</h1>'
            + '<input id="champ" data-i18n-attr="title:essai.bulle; placeholder:essai.indice">'
            + '<button id="mixte" data-i18n="essai.titre" data-i18n-attr="title:essai.bulle">Ancien</button></section>'
            + '<p id="dehors" data-i18n="essai.titre">Dehors</p>';
          const lire = () => ({
            titre: document.getElementById('titre').textContent,
            bulle: document.getElementById('champ').getAttribute('title'),
            indice: document.getElementById('champ').getAttribute('placeholder'),
            mixte: [document.getElementById('mixte').textContent, document.getElementById('mixte').title],
            zone: document.getElementById('zone').getAttribute('aria-label'),
            dehors: document.getElementById('dehors').textContent,
          });
          const nombre = I18n.appliquer(document.getElementById('zone'));
          const dansLaZone = lire();
          const toutLeDocument = I18n.appliquer(document);
          return { nombre, dansLaZone, toutLeDocument, apres: lire() };
        }""")
        self.assertEqual(resultat["nombre"], 4)
        self.assertEqual(resultat["dansLaZone"], {
            "titre": "Titre traduit", "bulle": "Bulle traduite", "indice": "Indice traduit",
            "mixte": ["Titre traduit", "Bulle traduite"], "zone": "Zone traduite", "dehors": "Dehors"})
        self.assertEqual(resultat["toutLeDocument"], 5)
        self.assertEqual(resultat["apres"]["dehors"], "Titre traduit")
        self.assertEqual(self.avertissements(), [])

    def test_chargeur_ajoute_apres_l_analyse_laisse_la_page_intacte(self):
        self.ouvrir()
        self.page.evaluate("""() => {
          document.body.innerHTML = '<p id="temoin">Témoin</p>';
          I18n.declarer({ code: 'xx', nom: 'Essai', locale: 'pl', statut: 'automatique' });
          localStorage.setItem('prevo.langue', 'xx');
        }""")
        self.page.add_script_tag(url=url_fichier("js/i18n-chargeur.js"))
        self.assertEqual(self.page.evaluate("document.getElementById('temoin').textContent"), "Témoin")
        self.assertEqual(self.page.evaluate("I18n.langue"), "fr")


# ---------------------------------------------------------------------------
# Navigateur : chargement dans l'application (copie servie avec la langue d'essai, puis le dépôt tel quel)
# ---------------------------------------------------------------------------

class TestChargement(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dossier = Path(tempfile.mkdtemp(prefix="prevo-i18n-copie-"))
        cls.addClassCleanup(shutil.rmtree, cls.dossier, True)
        preparer_copie(cls.dossier)

    def attendre_etat(self, page, etat):
        page.wait_for_function("document.documentElement.dataset.etat === %r" % etat)

    def lire(self, page):
        return page.evaluate("""() => ({ sonde: window.sondeI18n, langue: I18n.langue,
          pied: document.querySelector('.demarrage-pied').textContent, schema: typeof Schema })""")

    def verifier_langue_d_essai(self, etat):
        self.assertEqual(etat["sonde"], {"langue": "xx", "texte": TEXTE_XX, "aideXx": "Aide de la langue d'essai",
                                         "aideFr": "Aide française", "schemaCharge": False})
        self.assertEqual(etat["langue"], "xx")
        self.assertEqual(etat["pied"], "Appliqué en xx")              # I18n.appliquer(document) au démarrage
        self.assertEqual(etat["schema"], "object")

    def test_langue_d_essai_prise_avant_le_schema_en_http(self):
        self.autoriser_erreur(ERREUR_PING_ABSENT)
        page = self.page
        requetes = []
        page.on("request", lambda requete: requetes.append(requete.url))
        with ServeurStatique(self.dossier) as statique:
            page.goto(statique.url + "/index.html")
            self.attendre_etat(page, "demarrage")
            etat = self.lire(page)
            self.assertEqual(etat["sonde"]["langue"], "fr")
            self.assertEqual(etat["sonde"]["texte"], "Texte français")
            self.assertEqual(etat["pied"], "Appliqué en français")
            # Langue non déclarée, mal formée ou française : français, sans erreur ni requête de plus.
            for valeur in ("zz", "XX", "xx\"><img src=x onerror=alert(1)>", "../xx", "fr", ""):
                with self.subTest(valeur=valeur):
                    page.evaluate("(valeur) => localStorage.setItem('prevo.langue', valeur)", valeur)
                    page.reload()
                    self.attendre_etat(page, "demarrage")
                    etat = self.lire(page)
                    self.assertEqual((etat["langue"], etat["sonde"]["texte"]), ("fr", "Texte français"))
            self.assertEqual([url for url in requetes if "/js/i18n/" in url and "/fr.js" not in url
                              and "/langues.js" not in url], [])
            # Langue d'essai déclarée : ses deux fichiers chargés avant js/schema.js.
            page.evaluate("localStorage.setItem('prevo.langue', 'xx')")
            page.reload()
            self.attendre_etat(page, "demarrage")
            self.verifier_langue_d_essai(self.lire(page))
            # L'ordre d'exécution est prouvé par la sonde ; celui des requêtes ne dit rien (le navigateur lit en avance).
            charges = {url.split("/js/", 1)[1] for url in requetes if "/js/" in url}
            self.assertTrue({"i18n/xx.js", "i18n/aide/xx.js"} <= charges, charges)

    def test_langue_sans_aide_longue_charge_l_anglais_et_l_affiche(self):
        """T343 (D158) : langue « yy » déclarée avec aide: 'en' (comme tr, it, pt-PT) : yy.js, en.js et aide/en.js chargés,
        jamais aide/yy.js ; une clé de l'aide longue s'affiche en anglais ; une ligne d'information dans la console."""
        self.autoriser_erreur(ERREUR_PING_ABSENT)
        page = self.page
        requetes, infos = [], []
        page.on("request", lambda requete: requetes.append(requete.url))
        page.on("console", lambda message: infos.append(message.text) if message.type == "info" else None)
        with ServeurStatique(self.dossier) as statique:
            page.goto(statique.url + "/index.html")
            self.attendre_etat(page, "demarrage")
            page.evaluate("localStorage.setItem('prevo.langue', 'yy')")
            requetes.clear()
            page.reload()
            self.attendre_etat(page, "demarrage")
            etat = page.evaluate("""() => {
              const cle = 'aide.ecran.accueil.titre';
              return { langue: I18n.langue, texte: I18n.t('essai.chargement'), aide: I18n.t(cle),
                       anglais: I18n.enLangue('en', () => I18n.t(cle)), francais: I18n.reference(cle) };
            }""")
            page.evaluate("localStorage.removeItem('prevo.langue')")
        charges = {url.split("/js/", 1)[1] for url in requetes if "/js/i18n/" in url}
        self.assertEqual(etat["langue"], "yy")
        self.assertEqual(etat["texte"], "Texte de la langue d'essai Y")
        self.assertTrue({"i18n/yy.js", "i18n/en.js", "i18n/aide/en.js"} <= charges, charges)
        self.assertNotIn("i18n/aide/yy.js", charges)
        self.assertEqual(etat["aide"], etat["anglais"])
        self.assertNotEqual(etat["aide"], etat["francais"])
        self.assertIn("Prévo : pas d'aide longue en « yy » ; elle s'affiche en « en ».", infos)

    def test_police_sora_dessine_les_lettres_turques(self):
        """CS163 (T343, D162) : ğ, Ğ, İ, ş, Ş (absentes du sous-ensemble latin) sont prises dans Sora latin-ext, chargée à
        la demande depuis css/polices/ ; ı reste dans latin. index.html réel en file://."""
        self.page.goto(url_fichier(RACINE / "index.html"))
        self.attendre_etat(self.page, "demarrage")
        resultat = self.page.evaluate("""async () => {
          const essai = document.createElement('p');
          essai.style.fontFamily = 'Sora'; essai.textContent = 'Iğdır, İstanbul, Şişli, ışık';
          document.body.appendChild(essai);
          await document.fonts.load('16px Sora', 'ğĞİşŞ');
          const faces = [...document.fonts].filter((face) => face.family.replace(/["']/g, '') === 'Sora')
            .map((face) => ({ etat: face.status, plage: face.unicodeRange.toUpperCase() }));
          return { faces, pret: document.fonts.check('16px Sora', 'ğĞİşŞı') };
        }""")
        etendue = [face for face in resultat["faces"] if "U+100-2BA" in face["plage"] or "U+0100-02BA" in face["plage"]]
        latin = [face for face in resultat["faces"] if face not in etendue]
        self.assertEqual(len(etendue), 1, resultat["faces"])
        self.assertEqual(etendue[0]["etat"], "loaded")
        self.assertEqual(len(latin), 1, resultat["faces"])
        self.assertIn("131", latin[0]["plage"])                               # ı : sous-ensemble latin
        self.assertTrue(resultat["pret"])

    def test_langue_d_essai_prise_avant_le_schema_en_file(self):
        self.contexte.add_init_script("try { localStorage.setItem('prevo.langue', 'xx'); } catch (erreur) {}")
        self.page.goto(url_fichier(self.dossier / "index.html"))
        self.attendre_etat(self.page, "demarrage")
        self.verifier_langue_d_essai(self.lire(self.page))

    def test_langue_d_essai_sous_la_vraie_politique_de_securite(self):
        # Contexte sans contournement de la politique (bypass_csp faux) : celle de serveur.py, posée sur index.html.
        politique = serveur.POLITIQUE_CONTENU % serveur.ADRESSE_VERSION_PUBLIEE
        contexte = self.navigateur.new_context(bypass_csp=False, locale="fr-FR")
        self.addCleanup(contexte.close)
        contexte.add_init_script("try { localStorage.setItem('prevo.langue', 'xx'); } catch (erreur) {}")
        page = contexte.new_page()
        self.surveiller(page)
        self.autoriser_erreur(ERREUR_PING_ABSENT)

        # La page elle-même, lue sur le disque de la copie, servie avec la politique ; le reste vient du serveur statique.
        page.route("**/index.html", lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8", headers={"Content-Security-Policy": politique},
            body=(self.dossier / "index.html").read_bytes()))
        with ServeurStatique(self.dossier) as statique:
            page.goto(statique.url + "/index.html")
            sonde = page.evaluate("window.sondeI18n")
            # La politique s'applique bien à cette page : un script en ligne y est refusé (script-src 'self').
            self.autoriser_erreur("Executing inline script violates the following Content Security Policy")
            self.assertFalse(page.evaluate("""() => { const script = document.createElement('script');
              script.textContent = 'window.scriptEnLigne = true;'; document.head.appendChild(script);
              return window.scriptEnLigne === true; }"""))
        self.assertEqual(sonde["langue"], "xx")
        self.assertEqual(sonde["texte"], TEXTE_XX)
        self.assertFalse(sonde["schemaCharge"])

    def test_index_en_file_sans_erreur(self):
        self.page.goto(url_fichier("index.html"))
        self.attendre_etat(self.page, "demarrage")
        etat = self.page.evaluate("() => ({ langue: I18n.langue, langues: I18n.langues.map((l) => l.code), "
                                  "t: typeof I18n.t, lang: document.documentElement.lang })")
        self.assertEqual(etat, {"langue": "fr", "langues": CODES, "t": "function", "lang": "fr"})

    def test_mode_serveur_application_et_porte_sans_erreur(self):
        page = self.page
        preregler_profil(self.contexte, "responsable", "Nicolas Briand")
        with ServeurPrevo() as serveur:
            for chemin in ("/js/i18n.js", "/js/i18n-chargeur.js", "/js/i18n/langues.js", "/js/i18n/fr.js",
                           "/js/i18n/aide/fr.js"):
                with self.subTest(chemin=chemin), urllib.request.urlopen(serveur.url + chemin, timeout=10) as reponse:
                    self.assertEqual(reponse.status, 200)
                    self.assertTrue(reponse.headers["Content-Type"].startswith("text/javascript"))
                    self.assertEqual(reponse.read(), (RACINE / chemin.lstrip("/")).read_bytes())
            page.goto(serveur.url + "/")
            attendre_pret(page)
            self.assertEqual(page.evaluate("[App.mode, I18n.langue]"), ["serveur", "fr"])
            # Portée « ce PC », sans autorité locale : porte.js lit /acces/ca.crt, qui répond 404 avec l'explication.
            self.autoriser_erreur(ERREUR_SANS_AUTORITE)
            page.goto(serveur.url + "/acces/porte.html")
            page.wait_for_load_state("load")
            etat = page.evaluate("() => ({ langue: I18n.langue, langues: I18n.langues.map((l) => l.code), "
                                 "titre: document.title })")
            self.assertEqual(etat, {"langue": "fr", "langues": CODES, "titre": "Prévo — Bienvenue"})


# ---------------------------------------------------------------------------
# Navigateur : le sélecteur de langue (T278 ; D147, D148)
# ---------------------------------------------------------------------------

MENU_LANGUE = "#menu-langue-liste"
POSTE_LANGUE = "#poste-langue-liste"
# Les deux listes et la page : options (valeur, nom, lang), choix, nom accessible ; lang de <html>, langue active, clé
# retenue ; entrée « Ce poste » du menu et titre de l'écran (affiché, texte de la langue active, texte français) ;
# un nombre formaté.
ETAT_LANGUE_JS = """() => {
  const options = (liste) => [...liste.options].map((o) => [o.value, o.textContent, o.lang]);
  const menu = document.querySelector('#menu-langue-liste');
  const poste = document.querySelector('#poste-langue-liste');
  const lien = document.querySelector('#menu a[data-ecran="poste"] .libelle');
  let retenue;
  try { retenue = localStorage.getItem('prevo.langue'); } catch (erreur) { retenue = 'illisible'; }
  return {
    lang: document.documentElement.lang, langue: I18n.langue, locale: I18n.locale, retenue,
    menu: options(menu), poste: options(poste), choix: [menu.value, poste.value],
    menuVisible: menu.getClientRects().length > 0,
    nomMenu: [menu.getAttribute('aria-label'), I18n.t('socle.selecteur_langue.langue_ecran'),
              I18n.reference('socle.selecteur_langue.langue_ecran')],
    nomPoste: [...poste.labels].map((l) => [l.textContent.trim(), I18n.t('poste.carte_affichage.langue_ecran')]),
    entree: [lien.textContent.trim(), I18n.t('poste.menu.libelle'), I18n.reference('poste.menu.libelle')],
    titre: [document.querySelector('#contenu h1').textContent.trim(), I18n.t('poste.ecran.poste'),
            I18n.reference('poste.ecran.poste')],
    nombre: UI.nombreFr(1234567.5),
  };
}"""
# Stockage refusé pour la langue seule (navigation privée stricte, réglage du navigateur) : le reste de Prévo garde le
# sien, pour que seul le sélecteur soit éprouvé.
REFUS_LANGUE_JS = """(() => {
  for (const methode of ['setItem', 'removeItem']) {
    const avant = Storage.prototype[methode];
    Storage.prototype[methode] = function (cle, ...reste) {
      if (cle === 'prevo.langue') throw new DOMException('Stockage refusé (test)', 'SecurityError');
      return avant.call(this, cle, ...reste);
    };
  }
})();"""


class TestSelecteurDeLangue(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.cles_absentes = []          # console.warn du moteur : « Prévo (traduction) : clé … »
        self.page.on("console", lambda message: self.cles_absentes.append(message.text)
                     if message.type == "warning" and "(traduction)" in message.text else None)

    def changer_de_langue(self, selecteur, code):
        """Choisit `code` dans la liste : la page se recharge ; état relu sur l'écran « Ce poste » rouvert."""
        with self.page.expect_navigation():
            self.page.select_option(selecteur, code)
        attendre_pret(self.page)
        self.page.wait_for_selector(POSTE_LANGUE)
        return self.page.evaluate(ETAT_LANGUE_JS)

    def verifier_dans_sa_langue(self, etat, code):
        options = [[langue["code"], langue["nom"], langue["code"]] for langue in LANGUES]
        self.assertEqual((etat["menu"], etat["poste"]), (options, options))      # noms jamais traduits
        self.assertEqual(etat["choix"], [code, code])
        self.assertTrue(etat["menuVisible"])
        self.assertEqual(etat["nomMenu"][0], etat["nomMenu"][1])
        self.assertEqual(len(etat["nomPoste"]), 1)                              # un seul <label for>
        self.assertEqual(etat["nomPoste"][0][0], etat["nomPoste"][0][1])
        for zone in ("entree", "titre"):
            self.assertEqual(etat[zone][0], etat[zone][1], zone)

    def test_au_menu_et_a_ce_poste_anglais_puis_francais(self):
        page = self.page
        preregler_profil(self.contexte, "responsable", "Nicolas Briand")
        with ServeurPrevo() as serveur:
            page.goto(serveur.url + "/#/poste")
            attendre_pret(page)
            page.wait_for_selector(POSTE_LANGUE)
            francais = page.evaluate(ETAT_LANGUE_JS)
            self.verifier_dans_sa_langue(francais, "fr")
            self.assertEqual((francais["lang"], francais["langue"], francais["retenue"]), ("fr", "fr", None))

            # English, choisi au pied du menu : page rechargée en anglais.
            anglais = self.changer_de_langue(MENU_LANGUE, "en")
            self.verifier_dans_sa_langue(anglais, "en")
            self.assertEqual((anglais["lang"], anglais["langue"], anglais["locale"], anglais["retenue"]),
                             ("en", "en", "en-GB", "en"))
            for zone in ("entree", "titre", "nomMenu"):
                self.assertNotEqual(anglais[zone][0], anglais[zone][2], zone)      # pas le texte français
            self.assertEqual(anglais["nombre"], "1,234,567.5")
            # Un autre écran en anglais (accueil), puis retour à « Ce poste ».
            page.evaluate("location.hash = '#/accueil'")
            page.wait_for_function("App.ecranCourant && App.ecranCourant.id === 'accueil'")
            self.assertEqual(page.evaluate("document.documentElement.lang"), "en")
            page.evaluate("location.hash = '#/poste'")
            page.wait_for_selector(POSTE_LANGUE)

            # Français, choisi à l'écran « Ce poste » : page française, clé retirée.
            retour = self.changer_de_langue(POSTE_LANGUE, "fr")
            self.verifier_dans_sa_langue(retour, "fr")
            self.assertEqual((retour["lang"], retour["langue"], retour["locale"], retour["retenue"]),
                             ("fr", "fr", "fr-FR", None))
            for zone in ("entree", "titre", "nomMenu", "nombre"):
                self.assertEqual(retour[zone], francais[zone], zone)
        self.assertEqual(self.cles_absentes, [])

    def test_stockage_refuse_message_et_page_dans_sa_langue(self):
        page = self.page
        self.contexte.add_init_script(REFUS_LANGUE_JS)
        preregler_profil(self.contexte, "responsable", "Nicolas Briand")
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        page.evaluate("window.memePage = true")
        page.select_option(MENU_LANGUE, "en")
        # Démo : l'avertissement (T299) passe avant ; confirmé, le stockage refusé donne le message.
        page.locator("dialog[open]").get_by_role("button", name="Changer").click()
        page.wait_for_selector("#toast.visible")
        etat = page.evaluate("""() => ({ memePage: window.memePage === true, langue: I18n.langue,
          lang: document.documentElement.lang, choix: document.querySelector('#menu-langue-liste').value,
          message: document.querySelector('#toast').textContent.trim(),
          attendu: I18n.t('socle.selecteur_langue.choix_non_retenu') })""")
        self.assertEqual({cle: etat[cle] for cle in ("memePage", "langue", "lang", "choix")},
                         {"memePage": True, "langue": "fr", "lang": "fr", "choix": "fr"})
        self.assertEqual(etat["message"], etat["attendu"])
        # La liste du menu tient dans le menu ; menu en icônes seules (tablette) ou caché (téléphone) : liste cachée,
        # rien ne déborde.
        dans_le_menu = page.evaluate("""() => {
          const liste = document.querySelector('#menu-langue-liste').getBoundingClientRect();
          const menu = document.querySelector('.menu-lateral').getBoundingClientRect();
          return liste.width > 0 && liste.left >= menu.left && liste.right <= menu.right; }""")
        self.assertTrue(dans_le_menu)
        for largeur in (900, 375):
            with self.subTest(largeur=largeur):
                page.set_viewport_size({"width": largeur, "height": 800})
                etat = page.evaluate("""() => ({
                  visible: document.querySelector('#menu-langue-liste').getClientRects().length > 0,
                  deborde: document.documentElement.scrollWidth > document.documentElement.clientWidth })""")
                self.assertEqual(etat, {"visible": False, "deborde": False})
        self.assertEqual(self.cles_absentes, [])


if __name__ == "__main__":
    unittest.main()
