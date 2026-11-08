"""Écran « Importer des données » : les cinq étapes de l'assistant (tâche T85, ARCHITECTURE.md §18.9).

Ce qui est vérifié, dans l'application complète, avec les vrais fichiers d'essai (tests/fixtures/import/,
déposés par set_input_files) et un collage :
  - mode serveur : les cinq étapes sur equipements.xlsx (feuille, ligne d'en-tête proposée, correspondance,
    aperçu, bilan) ; tous les CSV restent identiques à l'octet et aucune requête d'écriture ne part tant que
    « Importer » n'est pas cliqué ; import (sauvegarde « …_avant-import », progression, résultat) puis
    « Annuler cet import » avec confirmation : seules les lignes du journal restent ;
  - démo : un collage (fournisseurs.tsv) de bout en bout puis annulation (tables rendues à l'octet) ;
    historique.csv : doublons sûrs et supposés, « Importer quand même » ; articles.csv : case « Compléter et
    mettre à jour les fiches existantes » (cochée par défaut, décochée : rien n'est mis à jour), lignes
    refusées téléchargées (contenu du fichier), correspondance corrigée à la main puis retrouvée au second
    passage ; modèles .xlsx et .csv ; erreurs de lecture claires ; feuille, ligne d'en-tête, « Retour » ;
  - IA : bouton absent sans IA ; avec le faux fournisseur, il n'envoie que les titres des colonnes non
    reconnues (aucune valeur de cellule), la proposition reste « à confirmer », et l'import la trace au
    journal (« proposition IA utilisée ») ;
  - profils : technicien et demandeur n'ont pas l'écran ; lien depuis Paramètres pour le responsable ;
  - 1440 et 375 px : aucune page plus large que l'écran, zones cliquables d'au moins 48 px au téléphone ;
    thème clair : contraste AA de chaque texte affiché, à chaque étape.

Horloge du navigateur fixée (tests déterministes à toute heure).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_import_ecrans.py" -v
"""
import csv
import hashlib
import io
import json
import re
import unittest
from pathlib import Path

from commun import NB_TABLES, RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier
from faux_fournisseur_ia import FauxFournisseur
from test_app import ERREUR_CSV_ABSENT
from test_ia_regles import regler_ia, taire_coupures
from test_poste import AUDIT_TEXTES_JS

FIXTURES = RACINE / "tests" / "fixtures" / "import"
HEURE_FIXE = "2026-10-21T09:30:00"
MOTIF_AVANT_IMPORT = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-import$")
CONFIRMATION = "les modifications faites depuis l'import, sur ces tables, seront perdues"

NOTER_TOASTS_JS = """(() => {
  window.__toasts = [];
  let dernier = '';
  new MutationObserver(() => {
    const zone = document.getElementById('toast');
    const texte = zone && zone.classList.contains('visible') ? zone.textContent.trim() : '';
    if (texte && texte !== dernier) window.__toasts.push(texte);
    dernier = texte;
  }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class'] });
})();"""

# Étape 3 : une entrée par colonne du fichier.
COLONNES_JS = """() => [...document.querySelectorAll('table.import-colonnes tbody tr[data-colonne]')].map((tr) => ({
  entete: tr.querySelector('.import-entete').textContent.trim(),
  champ: tr.querySelector('select.import-champ').value,
  statut: tr.querySelector('.import-statut').textContent.trim(),
  classe: tr.querySelector('.import-statut').className,
  raison: (tr.querySelector('.import-raison') || { textContent: '' }).textContent.trim(),
  exemples: [...tr.querySelectorAll('.import-exemples li')].map((li) => li.textContent.trim()),
}))"""
# Étape 4 : totaux par action et lignes affichées.
TOTAUX_JS = """() => Object.fromEntries([...document.querySelectorAll('#contenu [data-total]')]
  .map((e) => [e.dataset.total, Number(e.textContent.trim())]))"""
LIGNES_JS = """() => [...document.querySelectorAll('table.import-lignes tbody tr[data-numero]')].map((tr) => {
  const caseQuandMeme = tr.querySelector('input.import-quand-meme');
  return { numero: Number(tr.dataset.numero), action: tr.dataset.action, texte: tr.innerText.replace(/\\s+/g, ' '),
           changements: [...tr.querySelectorAll('.import-changements li')].map((li) => li.textContent.replace(/\\s+/g, ' ').trim()),
           quandMeme: caseQuandMeme ? caseQuandMeme.checked : null };
})"""
# Contenu des tables en mémoire (octets sérialisés par Donnees), journal à part.
INSTANTANE_JS = """() => Object.fromEntries(Object.entries(Donnees.instantane())
  .map(([nom, octets]) => [nom, new TextDecoder().decode(octets)]))"""
JOURNAL_JS = "async () => { await Donnees.rafraichir(); return Donnees.lignes('journal').map((l) => [l.table, l.id_ligne, l.action]); }"
# Pages plus larges que l'écran ; zones cliquables visibles et leur hauteur.
LARGEUR_JS = "() => [document.documentElement.scrollWidth, window.innerWidth]"
ZONES_JS = """() => [...document.querySelectorAll('#contenu .btn, #contenu button, #contenu a, #contenu label.case, '
    + '#contenu .import-type, #contenu select, #contenu textarea, '
    + '#contenu input:not([type=checkbox]):not([type=radio]):not([type=file])')]
  .filter((e) => e.getClientRects().length > 0 && !e.closest('.visuellement-cache, [hidden]'))
  .map((e) => [e.id || e.className || e.tagName, (e.textContent || e.value || '').trim().slice(0, 30),
               Math.round(e.getBoundingClientRect().height * 10) / 10])"""

# Correspondance attendue de equipements.xlsx (LISEZMOI des fichiers d'essai).
COLONNES_EQUIPEMENTS = [
    ("Désignation", "designation", "Sûre"), ("Code machine", "repere", "Sûre"), ("Fabricant", "marque", "Sûre"),
    ("Mise en service", "date_mes", "Sûre"), ("Emplacement", "chemin_localisation", "Sûre"),
    ("N° de série", "num_serie", "Sûre"), ("Criticité", "criticite", "Sûre"), ("Machine mère", "parent", "Sûre"),
    ("Commentaire", "", "Non utilisée"),
]
CLASSES_STATUT = {"Sûre": "ok", "À confirmer": "attention", "Non utilisée": "neutre"}

# Collage pour l'IA : la 4e colonne n'a aucun titre reconnu ; ses cellules ne doivent jamais partir.
COLLAGE_IA = ("Raison sociale\tInterlocuteur\tTél\tPour commander\r\n"
              "Hydraulique Durance\tNina Roux\t0465710009\tcommandes@hydraulique-durance.example\r\n"
              "Fluidalpes Services\tBruno Faure\t0465710002\tcommandes@fluidalpes-demo.example\r\n")


def empreintes(dossier):
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(dossier.glob("*.csv"))}


def lire_articles():
    """articles.csv (Windows-1252, « ; ») : en-tête et lignes de données, comme un tableur les lit."""
    texte = (FIXTURES / "articles.csv").read_bytes().decode("cp1252")
    lignes = list(csv.reader(io.StringIO(texte, newline=""), delimiter=";"))
    return lignes[0], lignes[1:]


class CasImport(CasNavigateur):
    """Outils communs : ouvrir l'écran, passer d'une étape à l'autre, lire ce qui est affiché."""

    def setUp(self):
        super().setUp()
        self.contexte.clock.set_fixed_time(HEURE_FIXE)

    # -- ouverture -------------------------------------------------------------------------

    def ouvrir_demo(self, profil="responsable", theme=None):
        if theme:
            self.contexte.add_init_script("try { localStorage.setItem('prevo.theme', %s); } catch (e) { /* vide */ }"
                                          % json.dumps(theme))
        preregler_profil(self.contexte, profil)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.aller("#/import")
        self.attendre_etape(1)
        return self.page

    def ouvrir_serveur(self, serveur, route="#/import"):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")
        if route == "#/import":
            self.attendre_etape(1)
        return self.page

    def aller(self, route):
        self.page.evaluate("hash => { location.hash = hash; }", route)
        self.page.wait_for_function("hash => location.hash === hash", arg=route)

    # -- étapes ----------------------------------------------------------------------------

    def attendre_etape(self, numero):
        self.page.wait_for_selector('.import-etape[data-etape="%d"]' % numero, state="visible")

    def etape(self):
        return int(self.page.get_attribute(".import-etape", "data-etape"))

    def continuer(self, numero):
        self.page.click("#import-continuer")
        self.attendre_etape(numero)

    def retour(self, numero):
        self.page.click("#import-retour")
        self.attendre_etape(numero)

    def choisir_type(self, type_):
        self.page.check('input[name="import-type"][value="%s"]' % type_)
        self.continuer(2)

    def attendre_lecture(self, nom):
        """Fichier lu : son nom en titre de la zone « lu » et les titres des colonnes affichés."""
        self.page.wait_for_function("(nom) => { const t = document.querySelector('#import-lu:not([hidden]) > h3');"
                                    " return t && t.textContent.includes(nom) && document.querySelector('#import-titres'); }", arg=nom)

    def deposer(self, nom):
        self.page.set_input_files("#import-fichier", str(FIXTURES / nom))
        self.attendre_lecture(nom)

    def coller(self, texte):
        self.page.fill("#import-collage", texte)
        self.page.click("#import-lire-collage")
        self.attendre_lecture("Collage")

    def jusqu_a_l_apercu(self, type_, fichier=None, collage=None):
        self.choisir_type(type_)
        if fichier:
            self.deposer(fichier)
        else:
            self.coller(collage)
        self.continuer(3)
        self.continuer(4)

    def colonnes(self):
        return self.page.evaluate(COLONNES_JS)

    def totaux(self):
        return self.page.evaluate(TOTAUX_JS)

    def lignes(self):
        return {ligne["numero"]: ligne for ligne in self.page.evaluate(LIGNES_JS)}

    def attendre_total(self, action, valeur):
        self.page.wait_for_function("([a, v]) => { const e = document.querySelector('#contenu [data-total=\"' + a + '\"]');"
                                    " return e && Number(e.textContent.trim()) === v; }", arg=[action, valeur])

    def importer(self):
        self.page.click("#import-importer")
        self.page.wait_for_selector("#import-resultat .alerte.succes")

    def annuler_l_import(self):
        self.page.click("#import-annuler")
        self.page.wait_for_selector("dialog[open]")
        self.assertIn(CONFIRMATION, self.page.inner_text("dialog[open]"))
        self.page.click("dialog[open] .btn-danger")
        self.page.wait_for_function("() => (document.querySelector('#import-resultat') || {}).textContent"
                                    " && document.querySelector('#import-resultat').textContent.includes('Import annulé')")

    def resultat_par_table(self):
        return self.page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('#import-resultat tr[data-table]')]
          .map((tr) => [tr.dataset.table, [Number(tr.querySelector('.import-crees').textContent),
                                            Number(tr.querySelector('.import-mis-a-jour').textContent)]]))""")

    def verifier_largeur(self, ou):
        largeur, ecran = self.page.evaluate(LARGEUR_JS)
        self.assertLessEqual(largeur, ecran, "%s : page plus large que l'écran (%s > %s)" % (ou, largeur, ecran))

    def verifier_zones(self, ou):
        zones = self.page.evaluate(ZONES_JS)
        self.assertGreater(len(zones), 0, ou)
        self.assertEqual([z for z in zones if z[2] < 47.5], [], "%s : zones de moins de 48 px" % ou)


# ---------------------------------------------------------------------------
# Mode serveur : rien n'est écrit avant « Importer », import puis annulation
# ---------------------------------------------------------------------------

class TestServeur(CasImport):

    def test_cinq_etapes_xlsx_rien_ecrit_avant_importer_puis_annulation(self):
        with ServeurPrevo() as serveur:
            ecritures = []
            self.page.on("request", lambda r: ecritures.append(r.method + " " + r.url) if r.method != "GET" else None)
            page = self.ouvrir_serveur(serveur)
            avant = empreintes(serveur.dossier)
            self.assertEqual(len(avant), NB_TABLES)
            ecritures.clear()

            # 1. Quoi : les types et leur aide
            types = page.eval_on_selector_all('input[name="import-type"]', "es => es.map((e) => e.value)")
            self.assertEqual(types, list(page.evaluate("Object.keys(Import.TYPES)")))
            self.assertIn("Le parc : un équipement par ligne", page.inner_text(".import-etape"))
            self.assertTrue(page.is_disabled("#import-continuer"))
            self.choisir_type("equipements")

            # 2. D'où : fichier déposé, feuilles, ligne d'en-tête proposée
            self.deposer("equipements.xlsx")
            self.assertEqual(page.eval_on_selector_all("#import-feuille option", "os => os.map((o) => o.textContent.trim())"),
                             ["Parc", "Notes"])
            self.assertEqual(page.input_value("#import-ligne-entete"), "2")
            self.assertIn("Code machine", page.inner_text("#import-titres"))
            self.assertIn("23 lignes de données", page.inner_text("#import-lu"))

            # 3. Colonnes : champ et statut en texte et en couleur, trois exemples
            self.continuer(3)
            colonnes = self.colonnes()
            self.assertEqual([(c["entete"], c["champ"], c["statut"]) for c in colonnes], COLONNES_EQUIPEMENTS)
            for colonne in colonnes:
                with self.subTest(colonne=colonne["entete"]):
                    self.assertIn(CLASSES_STATUT[colonne["statut"]], colonne["classe"].split())
            self.assertEqual(colonnes[1]["exemples"], ["CP-01", "CP-01.PUR", "CP-02"])
            self.assertEqual(page.locator("#import-zone-ia .ia-bouton").count(), 0, "pas d'IA réglée : pas de bouton")

            # 4. Aperçu : totaux, changement avant → après, références créées, refus
            self.continuer(4)
            self.assertTrue(page.is_checked("#import-mettre-a-jour"))
            totaux = self.totaux()
            self.assertEqual({a: totaux[a] for a in ("creer", "mettre_a_jour", "identique", "refusee")},
                             {"creer": 5, "mettre_a_jour": 1, "identique": 14, "refusee": 3})
            lignes = self.lignes()
            self.assertEqual(len(lignes), 23)
            self.assertEqual(lignes[8]["action"], "mettre_a_jour")
            self.assertEqual(len(lignes[8]["changements"]), 1)
            self.assertRegex(lignes[8]["changements"][0], r"Criticité.*B.*→.*A")
            self.assertEqual(sorted(n for n, l in lignes.items() if l["action"] == "refusee"), [16, 17, 24])
            self.assertIn("XX-99", lignes[17]["texte"])
            self.assertIn("Ligne de rectification", page.inner_text("#import-references"))
            self.assertTrue(page.is_visible("#import-refus"))

            # 5. Importer : bilan, rien n'est encore écrit
            self.continuer(5)
            bilan = page.inner_text("#import-bilan")
            self.assertIn("Équipements", bilan)
            self.assertIn("Localisations", bilan)
            self.assertTrue(page.is_enabled("#import-importer"))
            page.wait_for_timeout(400)
            self.assertEqual(empreintes(serveur.dossier), avant, "aucun CSV modifié avant « Importer »")
            self.assertEqual(ecritures, [], "aucune requête d'écriture avant « Importer »")

            self.importer()
            self.assertRegex(page.inner_text("#import-sauvegarde").strip(), MOTIF_AVANT_IMPORT)
            self.assertEqual(self.resultat_par_table(), {"localisations": [1, 0], "equipements": [5, 1]})
            progression = page.evaluate("() => { const p = document.querySelector('#import-progression progress');"
                                        " return p ? [p.value, p.max] : null; }")
            self.assertEqual(progression, [2, 2])
            apres = empreintes(serveur.dossier)
            self.assertNotEqual(apres["equipements.csv"], avant["equipements.csv"])
            self.assertNotEqual(apres["localisations.csv"], avant["localisations.csv"])
            self.assertTrue(page.is_hidden("#import-retour"), "plus de retour en arrière après l'import")
            self.assertTrue(page.is_hidden("#import-importer"))

            self.annuler_l_import()
            final = empreintes(serveur.dossier)
            self.assertEqual([nom for nom in avant if final[nom] != avant[nom]], ["journal.csv"])

    def test_apercu_perime_un_autre_poste_a_ecrit_nouvel_apercu_montre(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir_serveur(serveur)
            self.jusqu_a_l_apercu("fournisseurs", collage=(FIXTURES / "fournisseurs.tsv").read_bytes().decode("utf-8"))
            self.assertEqual(self.totaux()["creer"], 3)
            self.continuer(5)
            # Un autre poste crée « Roulements du Vercors » entre l'aperçu et l'import
            contexte = self.navigateur.new_context(locale="fr-FR")
            try:
                preregler_profil(contexte, "responsable")
                autre = contexte.new_page()
                self.surveiller(autre)
                autre.goto(serveur.url + "/#/accueil")
                attendre_pret(autre)
                autre.evaluate("""async () => { await Donnees.modifier('fournisseurs', (lignes, outils) => {
                  lignes.push({ id: outils.nouvelId(), nom: 'Roulements du Vercors' }); }); }""")
            finally:
                contexte.close()
            avant = empreintes(serveur.dossier)
            page.click("#import-importer")
            self.attendre_etape(4)
            self.assertIn("ont changé sur un autre poste", page.inner_text("#import-message-apercu"))
            self.assertEqual(self.totaux()["creer"], 2, "le nouvel aperçu reconnaît la fiche de l'autre poste")
            self.assertEqual({n: h for n, h in empreintes(serveur.dossier).items() if n != "journal.csv"},
                             {n: h for n, h in avant.items() if n != "journal.csv"}, "rien n'est écrit")
            self.continuer(5)
            self.importer()
            self.assertEqual(self.resultat_par_table()["fournisseurs"][0], 2)

    def test_profils_technicien_et_demandeur_sans_ecran_et_lien_depuis_parametres(self):
        with ServeurPrevo() as serveur:
            for profil, options in (("technicien", {"nom": "Technicien essai", "technicien_id": "TEC-0001"}),
                                    ("demandeur", {"nom": "Paul Essai"})):
                with self.subTest(profil=profil):
                    contexte = self.navigateur.new_context(locale="fr-FR")
                    try:
                        contexte.add_init_script(NOTER_TOASTS_JS)
                        preregler_profil(contexte, profil, **options)
                        page = contexte.new_page()
                        self.surveiller(page)
                        page.goto(serveur.url + "/#/import")
                        attendre_pret(page)
                        page.wait_for_function("location.hash === '#/accueil'")
                        page.wait_for_function("(window.__toasts || []).some((t) => t.includes('Importer des données')"
                                               " && t.includes(\"n'est pas disponible pour le profil\"))")
                        self.assertEqual(page.locator(".import-etape").count(), 0)
                    finally:
                        contexte.close()
            # Responsable : lien « Importer des données » dans Paramètres
            page = self.ouvrir_serveur(serveur, "#/parametres")
            page.wait_for_selector("#lien-import")
            self.assertEqual(page.get_attribute("#lien-import", "href"), "#/import")
            self.assertIn("Importer des données", page.inner_text("#lien-import"))
            page.click("#lien-import")
            self.attendre_etape(1)


# ---------------------------------------------------------------------------
# Démo : collage, historique, case « Compléter », refus, mémoire, modèles, erreurs
# ---------------------------------------------------------------------------

class TestDemo(CasImport):

    def test_collage_de_bout_en_bout_puis_annulation_a_l_octet(self):
        page = self.ouvrir_demo()
        avant = page.evaluate(INSTANTANE_JS)
        texte = (FIXTURES / "fournisseurs.tsv").read_bytes().decode("utf-8")
        self.choisir_type("fournisseurs")
        self.coller(texte)
        self.assertEqual(page.input_value("#import-ligne-entete"), "1")
        self.assertEqual(page.locator("#import-feuille").count(), 0, "un collage n'a qu'une feuille")
        self.continuer(3)
        self.assertEqual([(c["entete"], c["champ"], c["statut"]) for c in self.colonnes()],
                         [("Raison sociale", "nom", "Sûre"), ("Interlocuteur", "contact", "Sûre"),
                          ("Tél", "telephone", "Sûre"), ("Courriel", "email", "Sûre")])
        self.continuer(4)
        totaux = self.totaux()
        self.assertEqual({a: totaux[a] for a in ("creer", "mettre_a_jour", "identique", "refusee")},
                         {"creer": 3, "mettre_a_jour": 1, "identique": 1, "refusee": 1})
        lignes = self.lignes()
        self.assertRegex(lignes[2]["changements"][0], r"ventes@fluidalpes-demo\.example.*→.*commandes@fluidalpes-demo\.example")
        self.continuer(5)
        self.assertEqual(page.evaluate(INSTANTANE_JS), avant, "rien n'est écrit avant « Importer »")
        self.importer()
        self.assertEqual(page.locator("#import-sauvegarde").count(), 0, "démo : pas de sauvegarde sur un disque")
        self.assertEqual(self.resultat_par_table(), {"fournisseurs": [3, 1]})
        telephones = page.evaluate("() => Object.fromEntries(Donnees.lignes('fournisseurs').map((f) => [f.nom, f.telephone]))")
        self.assertEqual(telephones["Roulements du Vercors"], "0465710023")
        self.assertEqual(telephones["Pneumatique Savoie Services"], "04 65 71 00 30")
        # Confirmation refusée (« Garder l'import ») : rien n'est annulé
        importe = page.evaluate(INSTANTANE_JS)["fournisseurs"]
        page.click("#import-annuler")
        page.wait_for_selector("dialog[open]")
        page.click("dialog[open] .fenetre-actions .btn-fantome")
        page.wait_for_selector("dialog[open]", state="detached")
        page.wait_for_timeout(400)
        self.assertIn("Import terminé", page.inner_text("#import-resultat"))
        self.assertEqual(page.evaluate(INSTANTANE_JS)["fournisseurs"], importe)
        self.annuler_l_import()
        final = page.evaluate(INSTANTANE_JS)
        self.assertEqual({t: v for t, v in final.items() if t != "journal"}, {t: v for t, v in avant.items() if t != "journal"})
        # Recommencer : retour à l'étape 1
        page.click("#import-recommencer")
        self.attendre_etape(1)

    def test_echec_en_cours_d_ecriture_annuler_cet_import_propose(self):
        page = self.ouvrir_demo()
        avant = page.evaluate(INSTANTANE_JS)
        self.jusqu_a_l_apercu("equipements", fichier="equipements.xlsx")
        self.continuer(5)
        # La 2e table (équipements) ne s'écrit pas : les localisations sont déjà écrites
        page.evaluate("""() => { const modifier = Donnees.modifier;
          Donnees.modifier = function (table, ...reste) {
            if (table === 'equipements') return Promise.reject(new Error('disque plein (essai)'));
            return modifier.call(this, table, ...reste); }; }""")
        page.click("#import-importer")
        page.wait_for_selector("#import-resultat .alerte.important")
        texte = page.inner_text("#import-resultat")
        self.assertIn("arrêté en cours de route", texte)
        self.assertIn("disque plein (essai)", texte)
        self.assertEqual(page.locator("#import-recommencer").count(), 0)
        self.assertNotEqual(page.evaluate(INSTANTANE_JS)["localisations"], avant["localisations"])
        self.annuler_l_import()
        final = page.evaluate(INSTANTANE_JS)
        self.assertEqual({t: v for t, v in final.items() if t != "journal"}, {t: v for t, v in avant.items() if t != "journal"})

    def test_historique_doublons_et_importer_quand_meme(self):
        page = self.ouvrir_demo()
        self.jusqu_a_l_apercu("historique", fichier="historique.csv")
        totaux = self.totaux()
        self.assertEqual({a: totaux[a] for a in ("creer", "refusee", "doublon_sur", "doublon_suppose")},
                         {"creer": 13, "refusee": 2, "doublon_sur": 1, "doublon_suppose": 2})
        lignes = self.lignes()
        self.assertEqual(lignes[19]["action"], "doublon_sur")
        for numero in (12, 18):
            with self.subTest(ligne=numero):
                self.assertEqual(lignes[numero]["action"], "doublon_suppose")
                self.assertIs(lignes[numero]["quandMeme"], False, "case « Importer quand même » non cochée")
        self.assertIn("OT-2025-0002", lignes[18]["texte"])
        self.assertIn("ligne 4", lignes[12]["texte"])
        self.assertEqual(page.locator("#import-mettre-a-jour").count() and page.is_visible("#import-mettre-a-jour"), False,
                         "historique : un OT existant n'est jamais mis à jour")
        # Filtre : les doublons supposés seulement
        page.click('button.import-filtre[data-filtre="doublon_suppose"]')
        page.wait_for_function("() => document.querySelectorAll('table.import-lignes tbody tr[data-numero]').length === 2")
        self.assertEqual(page.get_attribute('button.import-filtre[data-filtre="doublon_suppose"]', "aria-pressed"), "true")
        # Ligne 18 importée quand même : une création de plus
        page.click('input.import-quand-meme[data-numero="18"]')
        self.attendre_total("creer", 14)
        self.assertEqual(self.totaux()["doublon_suppose"], 1)
        page.click('button.import-filtre[data-filtre="tout"]')
        page.wait_for_function("() => document.querySelectorAll('table.import-lignes tbody tr[data-numero]').length === 18")
        lignes = self.lignes()
        self.assertEqual(lignes[18]["action"], "creer")
        self.assertIs(lignes[18]["quandMeme"], True)
        self.assertIs(lignes[12]["quandMeme"], False)
        self.continuer(5)
        self.importer()
        self.assertEqual(self.resultat_par_table()["ordres_travail"][0], 14)
        anciens = page.evaluate("() => Donnees.lignes('ordres_travail').filter((o) => (o.compte_rendu || '').startsWith('Ancien n° : '))"
                                ".map((o) => o.compte_rendu.split('\\n')[0])")
        self.assertIn("Ancien n° : 4601", anciens)
        self.assertNotIn("Ancien n° : 4520", anciens)
        self.assertEqual(len(anciens), 14)

    def test_case_completer_cochee_par_defaut_et_decochee(self):
        page = self.ouvrir_demo()
        self.jusqu_a_l_apercu("articles", fichier="articles.csv")
        self.assertTrue(page.is_checked("#import-mettre-a-jour"))
        totaux = self.totaux()
        self.assertEqual({a: totaux[a] for a in ("creer", "mettre_a_jour", "identique", "refusee")},
                         {"creer": 7, "mettre_a_jour": 1, "identique": 1, "refusee": 3})
        self.assertRegex(self.lignes()[2]["changements"][0], r"Prix unitaire.*4[.,]8.*→.*5[.,]15")
        self.assertIn("Boulonnerie des Cimes", page.inner_text("#import-references"))
        page.uncheck("#import-mettre-a-jour")
        self.attendre_total("mettre_a_jour", 0)
        self.assertEqual(self.totaux()["identique"], 2)
        ligne = self.lignes()[2]
        self.assertEqual(ligne["action"], "identique")
        self.assertIn("mise à jour non demandée", ligne["texte"])
        self.continuer(5)
        self.importer()
        self.assertEqual(self.resultat_par_table()["articles"], [7, 0])
        self.assertEqual(page.evaluate("Donnees.trouver('articles', 'ART-0001').prix_unitaire"), "4.8")
        # « Importer d'autres données » : l'assistant repart de l'étape 1, case de nouveau cochée
        page.click("#import-recommencer")
        self.attendre_etape(1)
        self.jusqu_a_l_apercu("articles", fichier="articles.csv")
        self.assertTrue(page.is_checked("#import-mettre-a-jour"))
        self.assertEqual(self.lignes()[2]["action"], "mettre_a_jour")

    def test_lignes_refusees_telechargees(self):
        page = self.ouvrir_demo()
        self.jusqu_a_l_apercu("articles", fichier="articles.csv")
        self.assertIn("3", page.inner_text("#import-refus"))
        with page.expect_download() as attente:
            page.click("#import-refus")
        telechargement = attente.value
        self.assertTrue(telechargement.suggested_filename.endswith(".csv"), telechargement.suggested_filename)
        octets = Path(telechargement.path()).read_bytes()
        self.assertTrue(octets.startswith(b"\xef\xbb\xbf"), "BOM UTF-8 (format de Prévo)")
        lues = list(csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";"))
        entete, donnees = lire_articles()
        self.assertEqual(lues[0], ["Raison"] + entete)
        self.assertEqual(len(lues), 4)
        sans_apostrophe = lambda v: v[1:] if v.startswith("'") else v
        attendues = {6: "doublon", 10: "Désignation", 11: "Délai"}       # rang dans les données (ligne - 2) → mot de la raison
        for (rang, mot), ligne in zip(sorted(attendues.items()), lues[1:]):
            with self.subTest(ligne=rang + 2):
                self.assertIn(mot.lower(), ligne[0].lower())
                self.assertEqual([sans_apostrophe(v) for v in ligne[1:]], donnees[rang])

    def test_correspondance_corrigee_a_la_main_puis_retrouvee_au_second_passage(self):
        page = self.ouvrir_demo()
        self.choisir_type("articles")
        self.deposer("articles.csv")
        self.continuer(3)
        colonnes = self.colonnes()
        rang = [c["entete"] for c in colonnes].index("Stock mini")
        self.assertEqual(colonnes[rang]["champ"], "stock_securite")
        page.select_option('select.import-champ[data-colonne="%d"]' % rang, "point_commande")
        colonne = self.colonnes()[rang]
        self.assertEqual((colonne["champ"], colonne["statut"]), ("point_commande", "Sûre"))
        self.continuer(4)                                     # correspondance validée : retenue sur le poste
        # Second passage, après rechargement
        page.reload()
        page.click("#btn-demo")
        attendre_pret(page)
        self.aller("#/import")
        self.attendre_etape(1)
        self.choisir_type("articles")
        self.deposer("articles.csv")
        self.continuer(3)
        colonnes = {c["entete"]: c for c in self.colonnes()}
        self.assertEqual(colonnes["Stock mini"]["champ"], "point_commande")
        self.assertEqual(colonnes["Stock mini"]["statut"], "Sûre")
        self.assertIn("import précédent", colonnes["Stock mini"]["raison"])
        self.assertEqual(colonnes["Famille"]["champ"], "")
        self.assertEqual(colonnes["Code article"]["champ"], "reference")

    def test_champ_repris_par_une_autre_colonne_et_retour_garde_les_choix(self):
        page = self.ouvrir_demo()
        self.choisir_type("articles")
        self.deposer("articles.csv")
        self.continuer(3)
        entetes = [c["entete"] for c in self.colonnes()]
        famille, libelle = entetes.index("Famille"), entetes.index("Libellé")
        page.select_option('select.import-champ[data-colonne="%d"]' % famille, "designation")
        colonnes = self.colonnes()
        self.assertEqual((colonnes[famille]["champ"], colonnes[famille]["statut"]), ("designation", "Sûre"))
        self.assertEqual((colonnes[libelle]["champ"], colonnes[libelle]["statut"]), ("", "Non utilisée"))
        # Retour puis Continuer : les choix restent
        self.retour(2)
        self.assertIn("articles.csv", page.inner_text("#import-lu"))
        self.retour(1)
        self.assertTrue(page.is_checked('input[name="import-type"][value="articles"]'))
        self.continuer(2)
        self.continuer(3)
        colonnes = self.colonnes()
        self.assertEqual(colonnes[famille]["champ"], "designation")
        self.assertEqual(colonnes[libelle]["champ"], "")
        # Aucune colonne utilisée : impossible de continuer
        for rang in range(len(entetes)):
            page.select_option('select.import-champ[data-colonne="%d"]' % rang, "")
        page.click("#import-continuer")
        page.wait_for_timeout(200)
        self.assertEqual(self.etape(), 3)
        self.assertIn("aucune colonne", page.inner_text("#import-alertes-colonnes").lower())

    def test_modeles_a_remplir(self):
        page = self.ouvrir_demo()
        self.assertTrue(page.is_disabled("#import-modele-csv"))
        page.check('input[name="import-type"][value="equipements"]')
        with page.expect_download() as attente:
            page.click("#import-modele-csv")
        self.assertEqual(attente.value.suggested_filename, "prevo-modele-equipements.csv")
        texte = Path(attente.value.path()).read_bytes().decode("utf-8")
        libelles = page.evaluate("Import.TYPES.equipements.champs.map((c) => c.libelle)")
        self.assertTrue(texte.startswith(chr(0xFEFF)))
        self.assertEqual(next(csv.reader(io.StringIO(texte[1:], newline=""), delimiter=";")), libelles)
        with page.expect_download() as attente:
            page.click("#import-modele-xlsx")
        self.assertEqual(attente.value.suggested_filename, "prevo-modele-equipements.xlsx")
        self.assertTrue(Path(attente.value.path()).read_bytes().startswith(b"PK"))

    def test_erreurs_de_lecture_feuille_et_ligne_d_entete(self):
        page = self.ouvrir_demo()
        self.choisir_type("equipements")
        for nom, message in (("vide.csv", "vide"), ("chiffre.xlsx", "mot de passe"), ("lignes_vides.csv", "aucune"),
                             ("cellules_repetees.ods", "200")):
            with self.subTest(fichier=nom):
                page.set_input_files("#import-fichier", str(FIXTURES / nom))
                page.wait_for_function("(m) => { const z = document.querySelector('#import-erreur');"
                                       " return z && !z.hidden && z.textContent.toLowerCase().includes(m); }", arg=message)
                self.assertTrue(page.is_disabled("#import-continuer"))
        # Sans ligne d'en-tête : message clair, impossible de continuer
        page.set_input_files("#import-fichier", str(FIXTURES / "sans_entete.csv"))
        page.wait_for_function("() => { const z = document.querySelector('#import-erreur');"
                               " return z && !z.hidden && z.textContent.includes('en-tête'); }")
        self.assertTrue(page.is_disabled("#import-continuer"))
        # Un bon fichier efface l'erreur
        self.deposer("equipements.xlsx")
        self.assertTrue(page.is_hidden("#import-erreur"))
        self.assertTrue(page.is_enabled("#import-continuer"))
        # Feuille « Notes » puis « Parc »
        page.select_option("#import-feuille", "1")
        page.wait_for_function("() => !document.querySelector('#import-titres') || !document.querySelector('#import-titres').textContent.includes('Code machine')")
        page.select_option("#import-feuille", "0")
        page.wait_for_function("() => document.querySelector('#import-titres').textContent.includes('Code machine')")
        # Ligne d'en-tête changée à la main, puis en-tête sur deux lignes
        page.fill("#import-ligne-entete", "1")
        page.dispatch_event("#import-ligne-entete", "change")
        page.wait_for_function("() => document.querySelector('#import-titres').textContent.includes('Liste du parc')")
        page.fill("#import-ligne-entete", "2")
        page.dispatch_event("#import-ligne-entete", "change")
        page.wait_for_function("() => document.querySelector('#import-titres').textContent.includes('Code machine')")
        page.check("#import-deux-lignes")
        page.wait_for_function("() => document.querySelector('#import-titres').textContent.includes('Code machine CP-01')")
        page.uncheck("#import-deux-lignes")
        self.continuer(3)
        self.assertEqual([(c["entete"], c["champ"]) for c in self.colonnes()], [(e, c) for e, c, _ in COLONNES_EQUIPEMENTS])


# ---------------------------------------------------------------------------
# IA : bouton absent sans IA ; titres seulement ; proposition « à confirmer » ; trace au journal
# ---------------------------------------------------------------------------

class TestIa(CasImport):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur(lenteur_s=3)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)
        taire_coupures(cls.faux)

    def setUp(self):
        super().setUp()
        self.faux.requetes.clear()

    def test_sans_ia_pas_de_bouton(self):
        page = self.ouvrir_demo()
        self.choisir_type("fournisseurs")
        self.coller(COLLAGE_IA)
        self.continuer(3)
        page.wait_for_timeout(300)
        self.assertEqual(page.locator("#import-zone-ia .ia-bouton").count(), 0)
        self.assertEqual(self.faux.requetes, [])

    def test_proposition_du_faux_fournisseur_titres_seulement_a_confirmer_et_journal(self):
        regler_ia(self.contexte, url=self.faux.url)
        page = self.ouvrir_demo()
        page.wait_for_function("Ia.etat() === 'ok'")
        self.choisir_type("fournisseurs")
        self.coller(COLLAGE_IA)
        self.continuer(3)
        self.assertEqual([c["statut"] for c in self.colonnes()], ["Sûre", "Sûre", "Sûre", "Non utilisée"])
        page.click("#import-zone-ia .ia-bouton")
        page.wait_for_selector(".ia-encadre .ia-proposition")
        self.assertIn("Pour commander", page.inner_text(".ia-encadre"))
        page.click(".ia-encadre .ia-actions .btn-primaire")
        page.wait_for_selector(".ia-encadre", state="detached")
        # Ce qui est parti : les titres non reconnus et les champs libres, aucune valeur de cellule
        chats = self.faux.requetes_vers("/api/chat")
        self.assertEqual(len(chats), 1)
        corps = chats[0]["corps"]
        proprietes = corps["format"]["properties"]["colonnes"]["items"]["properties"]
        self.assertEqual(proprietes["entete"]["enum"], ["Pour commander"])
        champs_envoyes = [c for c in proprietes["champ"]["enum"] if c]
        self.assertNotIn("nom", champs_envoyes, "un champ déjà pris par une colonne sûre n'est pas proposé")
        envoye = json.dumps(corps, ensure_ascii=False)
        for ligne in COLLAGE_IA.strip().split("\r\n")[1:]:
            for cellule in ligne.split("\t"):
                with self.subTest(cellule=cellule):
                    self.assertNotIn(cellule, envoye)
        # La proposition reste « à confirmer »
        colonne = self.colonnes()[3]
        self.assertEqual(colonne["champ"], champs_envoyes[0])
        self.assertEqual(colonne["champ"], "email")
        self.assertEqual(colonne["statut"], "À confirmer")
        self.assertIn("attention", colonne["classe"].split())
        self.assertIn("IA", colonne["raison"])
        # Import : la proposition gardée est tracée au journal
        self.continuer(4)
        totaux = self.totaux()
        self.assertEqual((totaux["creer"], totaux["mettre_a_jour"]), (1, 1))
        self.continuer(5)
        journal_avant = len(page.evaluate(JOURNAL_JS))
        self.importer()
        page.wait_for_function("async () => { await Donnees.rafraichir();"
                               " return Donnees.lignes('journal').some((l) => l.action.startsWith('proposition IA utilisée')); }")
        nouvelles = page.evaluate(JOURNAL_JS)[journal_avant:]
        traces = [l for l in nouvelles if l[2].startswith("proposition IA utilisée")]
        self.assertEqual(len(traces), 1)
        self.assertIn("faux", traces[0][2])
        self.assertIn("Pour commander", traces[0][2])

    def test_proposition_remplacee_a_la_main_pas_de_trace(self):
        regler_ia(self.contexte, url=self.faux.url)
        page = self.ouvrir_demo()
        page.wait_for_function("Ia.etat() === 'ok'")
        self.choisir_type("fournisseurs")
        self.coller(COLLAGE_IA)
        self.continuer(3)
        page.click("#import-zone-ia .ia-bouton")
        page.wait_for_selector(".ia-encadre .ia-proposition")
        page.click(".ia-encadre .ia-actions .btn-primaire")
        page.wait_for_selector(".ia-encadre", state="detached")
        page.select_option('select.import-champ[data-colonne="3"]', "")
        self.assertEqual(self.colonnes()[3]["statut"], "Non utilisée")
        self.continuer(4)
        self.continuer(5)
        self.importer()
        page.wait_for_timeout(300)
        self.assertFalse(any(l[2].startswith("proposition IA utilisée") for l in page.evaluate(JOURNAL_JS)))


# ---------------------------------------------------------------------------
# Affichage : 1440 et 375 px, thème clair
# ---------------------------------------------------------------------------

class TestAffichage(CasImport):

    def parcourir(self, verifier):
        """Les cinq étapes sur equipements.xlsx (tableau large), import puis annulation ; verifier(ou) à chaque vue."""
        page = self.page
        verifier("étape 1")
        page.check('input[name="import-type"][value="equipements"]')
        verifier("étape 1, type choisi")
        self.continuer(2)
        verifier("étape 2")
        self.deposer("equipements.xlsx")
        verifier("étape 2, fichier lu")
        self.continuer(3)
        verifier("étape 3")
        self.continuer(4)
        verifier("étape 4")
        page.click('button.import-filtre[data-filtre="refusee"]')
        page.wait_for_function("() => document.querySelectorAll('table.import-lignes tbody tr[data-numero]').length === 3")
        verifier("étape 4, refusées")
        page.click('button.import-filtre[data-filtre="tout"]')
        self.continuer(5)
        verifier("étape 5")
        self.importer()
        verifier("étape 5, importé")
        self.annuler_l_import()
        verifier("étape 5, annulé")

    def test_1440_px_aucune_page_plus_large_que_l_ecran(self):
        self.page.set_viewport_size({"width": 1440, "height": 900})
        self.ouvrir_demo()
        self.parcourir(self.verifier_largeur)

    def test_375_px_aucune_page_plus_large_et_zones_de_48_px(self):
        self.page.set_viewport_size({"width": 375, "height": 812})
        page = self.ouvrir_demo()

        def verifier(ou):
            self.verifier_largeur(ou)
            self.verifier_zones(ou)
        self.parcourir(verifier)
        # Le tableau de l'aperçu défile dans son cadre, jamais la page
        self.page.click("#import-recommencer")
        self.attendre_etape(1)
        self.jusqu_a_l_apercu("equipements", fichier="equipements.xlsx")
        cadre = page.evaluate("() => { const c = document.querySelector('.import-cadre');"
                              " return [c.scrollWidth, c.clientWidth, getComputedStyle(c).overflowX]; }")
        self.assertGreater(cadre[0], cadre[1], "le tableau est plus large que son cadre au téléphone")
        self.assertIn(cadre[2], ("auto", "scroll"))
        self.verifier_largeur("étape 4, de nouveau")

    def test_theme_clair_contraste_des_textes_a_chaque_etape(self):
        self.page.set_viewport_size({"width": 1440, "height": 900})
        page = self.ouvrir_demo(theme="clair")
        self.assertEqual(page.evaluate("document.documentElement.dataset.theme"), "clair")

        def verifier(ou):
            page.wait_for_timeout(150)
            self.assertEqual(page.evaluate(AUDIT_TEXTES_JS, "#app"), [], ou)
        self.parcourir(verifier)
        # Historique : doublons, cases « Importer quand même »
        page.click("#import-recommencer")
        self.attendre_etape(1)
        self.jusqu_a_l_apercu("historique", fichier="historique.csv")
        verifier("étape 4, historique")


class TestAccueilBaseVide(CasImport):
    """Accueil d'une base sans équipement : le responsable est invité à importer ; ni le demandeur (une base vide
    n'a pas de technicien) ni la démo."""

    def test_lien_import_seulement_pour_le_responsable_d_une_base_vide(self):
        self.autoriser_erreur(ERREUR_CSV_ABSENT)
        with ServeurPrevo(source=None) as serveur:
            preregler_profil(self.contexte, "responsable")
            page = self.page
            page.goto(serveur.url + "/")
            page.wait_for_selector("#btn-base-vide", state="visible")
            page.click("#btn-base-vide")
            attendre_pret(page)
            page.wait_for_selector("#lien-import-accueil", state="visible")
            self.assertEqual(page.get_attribute("#lien-import-accueil", "href"), "#/import")
            self.assertIn("Votre parc est vide", page.inner_text("#carte-import-accueil"))
            page.click("#lien-import-accueil")
            self.attendre_etape(1)
            # Demandeur sur la même base : pas d'invitation
            contexte = self.navigateur.new_context(locale="fr-FR")
            try:
                preregler_profil(contexte, "demandeur", "Paul")
                autre = contexte.new_page()
                autre.goto(serveur.url + "/")
                attendre_pret(autre)
                autre.wait_for_load_state("networkidle")
                self.assertEqual(autre.locator("#lien-import-accueil").count(), 0)
            finally:
                contexte.close()
        # Démo (parc rempli) : pas d'invitation
        self.ouvrir_demo()
        self.aller("#/accueil")
        self.page.wait_for_selector(".accueil-instruments")
        self.assertEqual(self.page.locator("#carte-import-accueil").count(), 0)


if __name__ == "__main__":
    unittest.main()
