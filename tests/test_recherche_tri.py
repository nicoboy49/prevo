"""Tests de la recherche tolérante et du tri selon la langue (chantier multilingue, Lot 4, T300 ; D154, CS155).

Sans navigateur :
    - le wiki (js/modules/wiki-recherche.js) et le magasin (js/modules/magasin-regles.js) plient leurs recherches par
      UI.normaliserRecherche, sans pliage à eux ;
    - aucune liste ne se trie plus par localeCompare(…, 'fr') sans réglages hors du wiki (qui garde son ordre, D154) :
      les libellés passent par UI.comparerTextes ; les codes gardent leur ordre fixe (localeCompare 'fr' numérique).
Dans Chromium (page vide en file://, moteur de traduction, js/interface.js, et le wiki pour sa recherche) :
    - pliage UI.normaliserRecherche, le même quelle que soit la langue active : « istanbul » = « İSTANBUL »,
      « ırmak » = « IRMAK », « Işık » = « IŞIK », « Çağrı » = « CAGRI », « Élodie » = « elodie », « straße » = « strasse » ;
    - recherches réelles : le sélecteur d'équipement (UI.selecteurEquipement) trouve « İSTANBUL » en tapant
      « istanbul » et « IRMAK » en tapant « ırmak » ; la recherche du wiki (Wiki.rechercher) trouve de même l'OT
      clôturé « … İSTANBUL » et l'OT « … IRMAK » ;
    - tri des listes : en français, UI.comparerTextes et UI.tableau rangent comme Intl.Collator('fr-FR') et
      localeCompare(…, 'fr') ; langue d'essai « xx » déclarée en page à la locale « tr-TR » : « Çelik » après « Cem » et
      avant « Dede », « Işık » avant « İnce » (UI.comparerTextes et colonne de UI.tableau) ;
    - codes : le sélecteur d'équipement range les repères (« EQ-2 » avant « EQ-10 », « ia-02 » avant « Id-01 ») dans
      le même ordre en français, en anglais et dans la langue d'essai.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_recherche_tri.py" -v
"""
import csv
import io
import re
import unittest

from commun import RACINE, CasNavigateur, charger_scripts

SCRIPTS_INTERFACE = ["js/interface.js"]   # précédé du moteur, des langues et du français (charger_scripts)
SCRIPTS_WIKI = [
    "js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/stockage-demo.js", "js/interface.js",
    "js/modules/causes-frequentes.js", "js/modules/indicateurs-regles.js", "js/modules/wiki-regles.js",
    "js/modules/wiki-calculs.js", "js/modules/wiki-entites.js", "js/modules/wiki-recherche.js",
]

# CS155 : paires qui doivent se plier de même (saisie, texte des données), et le pli attendu.
PAIRES = [("istanbul", "İSTANBUL", "istanbul"), ("ırmak", "IRMAK", "irmak"), ("Işık", "IŞIK", "isik"),
          ("Çağrı", "CAGRI", "cagri"), ("Élodie", "elodie", "elodie"), ("straße", "strasse", "strasse")]
ESSAI_TURC = "I18n.declarer({ code: 'xx', nom: 'Essai', locale: 'tr-TR', statut: 'automatique' })"
NOMS_TURCS = ["Dede", "İnce", "Çelik", "Işık", "Cem"]
ORDRE_TURC = ["Cem", "Çelik", "Dede", "Işık", "İnce"]
# Libellés français : accents, casse, ligature, nombres ; l'ordre doit rester celui de localeCompare 'fr'.
LIBELLES_FRANCAIS = ["été", "Ete", "etre", "Évier", "œuf", "oeuf", "Zèbre", "abc", "Abc", "côte", "cote", "coté",
                     "côté", "Ça", "ca", "Pompe 10", "pompe 9", "Pompe 9", "Élodie", "elodie", "Œillet", "Ordre"]
# Repères (codes) : rangés pareil dans toutes les langues ; en turc, « I » et « i » seraient deux lettres.
REPERES = {"EQ-0001": "Id-01", "EQ-0002": "EQ-10", "EQ-0003": "ia-02", "EQ-0004": "EQ-2", "EQ-0005": "IA-03"}
ORDRE_DES_REPERES = ["EQ-0004", "EQ-0002", "EQ-0003", "EQ-0005", "EQ-0001"]   # EQ-2, EQ-10, ia-02, IA-03, Id-01

MOTIF_TRI_FRANCAIS_NU = re.compile(r"localeCompare\([^;]*?,\s*'fr'\s*\)")
FICHIERS_DU_WIKI = re.compile(r"^wiki-.*\.js$")

TRIER_JS = """([valeurs, options]) => valeurs.slice().sort((a, b) => UI.comparerTextes(a, b, options || undefined))"""
TABLEAU_JS = """(noms) => {
  const tableau = UI.tableau({ colonnes: [{ cle: 'nom', libelle: 'Nom' }], lignes: noms.map((nom) => ({ nom })),
                               triInitial: { cle: 'nom', sens: 'asc' }, libelle: 'Essai' });
  document.body.appendChild(tableau);
  const ordre = Array.from(tableau.querySelectorAll('tbody tr td:first-child')).map((cellule) => cellule.textContent.trim());
  tableau.remove();
  return ordre;
}"""
SELECTEUR_JS = """(equipements) => {
  const zone = document.createElement('div');
  document.body.appendChild(zone);
  UI.selecteurEquipement(zone, { equipements, localisations: [] });
  return zone.querySelector('input[type="search"]').id;
}"""
OPTIONS_JS = "() => Array.from(document.querySelectorAll('.selecteur-option')).map((option) => option.dataset.id)"


def texte_csv(lignes):
    """Lignes (dictionnaires) → CSV « ; », CRLF (§3.1)."""
    colonnes = []
    for ligne in lignes:
        colonnes.extend(cle for cle in ligne if cle not in colonnes)
    sortie = io.StringIO()
    ecrivain = csv.DictWriter(sortie, fieldnames=colonnes, delimiter=";", lineterminator="\r\n", restval="")
    ecrivain.writeheader()
    ecrivain.writerows(lignes)
    return sortie.getvalue()


def ot_clos(identifiant, titre):
    """Un OT correctif clôturé techniquement (champs utiles à la recherche du wiki seulement)."""
    return {"id": identifiant, "origine": "manuel", "di_id": "", "equipement_id": "EQ-0001",
            "type": "correctif immédiat", "priorite": "P2", "statut": "Clôturé techniquement", "titre": titre,
            "travail_a_faire": "", "date_creation": "2026-10-01 08:00", "date_fin": "2026-10-01 10:00",
            "date_cloture_tech": "2026-10-01 10:00", "symptome_code": "", "cause_code": "", "remede_code": "",
            "compte_rendu": ""}


# ---------------------------------------------------------------------------
# Sans navigateur : une seule façon de plier, une seule façon de trier les libellés
# ---------------------------------------------------------------------------

class TestSources(unittest.TestCase):

    def lire(self, chemin):
        return (RACINE / chemin).read_text(encoding="utf-8")

    def test_wiki_et_magasin_plient_par_ui_normaliser_recherche(self):
        for chemin in ("js/modules/wiki-recherche.js", "js/modules/magasin-regles.js"):
            with self.subTest(fichier=chemin):
                source = self.lire(chemin)
                self.assertIn("UI.normaliserRecherche(valeur)", source)
                self.assertNotIn(".normalize(", source)

    def test_aucun_tri_francais_nu_hors_du_wiki(self):
        fichiers = [RACINE / "js" / "app.js", RACINE / "js" / "interface.js"]
        fichiers += [f for f in sorted((RACINE / "js" / "modules").glob("*.js")) if not FICHIERS_DU_WIKI.match(f.name)]
        for fichier in fichiers:
            with self.subTest(fichier=fichier.name):
                self.assertEqual(MOTIF_TRI_FRANCAIS_NU.findall(fichier.read_text(encoding="utf-8")), [])


# ---------------------------------------------------------------------------
# Navigateur : pliage et tri (page vide, moteur de traduction et js/interface.js)
# ---------------------------------------------------------------------------

class TestPliageEtTri(CasNavigateur):

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS_INTERFACE)

    def choisir_essai_turc(self):
        self.assertTrue(self.page.evaluate("() => { %s; return I18n.choisir('xx'); }" % ESSAI_TURC))
        self.assertEqual(self.page.evaluate("I18n.locale"), "tr-TR")

    def plis(self):
        return self.page.evaluate("(paires) => paires.map(([a, b]) => [UI.normaliserRecherche(a), UI.normaliserRecherche(b)])",
                                  [[a, b] for a, b, _ in PAIRES])

    def test_pliage_des_paires_quelle_que_soit_la_langue(self):
        attendus = [[pli, pli] for _, _, pli in PAIRES]
        self.assertEqual(self.plis(), attendus)
        self.choisir_essai_turc()
        self.assertEqual(self.plis(), attendus)
        self.assertEqual(self.page.evaluate("UI.normaliserRecherche('  Pompe   İSTANBUL\\u00a0Nord ')"), "pompe istanbul nord")

    def test_selecteur_d_equipement_trouve_istanbul_et_irmak(self):
        equipements = [{"id": "EQ-0001", "repere": "P-01", "designation": "Pompe İSTANBUL", "actif": "1"},
                       {"id": "EQ-0002", "repere": "V-02", "designation": "Vanne IRMAK", "actif": "1"},
                       {"id": "EQ-0003", "repere": "C-03", "designation": "Compresseur Ankara", "actif": "1"}]
        champ = self.page.evaluate(SELECTEUR_JS, equipements)
        for saisie, attendus in (("istanbul", ["EQ-0001"]), ("ırmak", ["EQ-0002"]), ("IRMAK", ["EQ-0002"]),
                                 ("vanne ırmak", ["EQ-0002"]), ("İstanbul", ["EQ-0001"])):
            with self.subTest(saisie=saisie):
                self.page.fill("#" + champ, saisie)
                self.assertEqual(self.page.evaluate(OPTIONS_JS), attendus)

    def test_francais_identique_a_locale_compare_fr(self):
        for options in (None, {"sensitivity": "base"}, {"numeric": True, "sensitivity": "base"}):
            with self.subTest(options=options):
                attendu = self.page.evaluate(
                    "([valeurs, options]) => valeurs.slice().sort((a, b) => a.localeCompare(b, 'fr', options || undefined))",
                    [LIBELLES_FRANCAIS, options])
                self.assertEqual(self.page.evaluate(TRIER_JS, [LIBELLES_FRANCAIS, options]), attendu)
                collateur = self.page.evaluate(
                    "([valeurs, options]) => valeurs.slice().sort(new Intl.Collator('fr-FR', options || undefined).compare)",
                    [LIBELLES_FRANCAIS, options])
                self.assertEqual(collateur, attendu)
        tableau = self.page.evaluate(
            "(valeurs) => valeurs.slice().sort((a, b) => a.localeCompare(b, 'fr', { numeric: true, sensitivity: 'base' }))",
            LIBELLES_FRANCAIS)
        self.assertEqual(self.page.evaluate(TABLEAU_JS, LIBELLES_FRANCAIS), tableau)

    def test_tri_dans_la_langue_d_essai_turque(self):
        self.assertNotEqual(self.page.evaluate(TRIER_JS, [NOMS_TURCS, None]), ORDRE_TURC)   # français : Çelik avant Cem
        self.choisir_essai_turc()
        self.assertEqual(self.page.evaluate(TRIER_JS, [NOMS_TURCS, None]), ORDRE_TURC)
        self.assertEqual(self.page.evaluate(TRIER_JS, [NOMS_TURCS, {"numeric": True, "sensitivity": "base"}]), ORDRE_TURC)
        self.assertEqual(self.page.evaluate(TABLEAU_JS, NOMS_TURCS), ORDRE_TURC)
        self.assertTrue(self.page.evaluate("I18n.choisir('fr')"))
        self.assertEqual(self.page.evaluate(TRIER_JS, [NOMS_TURCS, None]),
                         self.page.evaluate("(noms) => noms.slice().sort((a, b) => a.localeCompare(b, 'fr'))", NOMS_TURCS))

    def test_codes_ranges_pareil_dans_toutes_les_langues(self):
        equipements = [{"id": i, "repere": r, "designation": "Pompe", "actif": "1"} for i, r in REPERES.items()]
        ordres = {}
        for langue in ("fr", "en", "xx"):
            if langue == "xx":
                self.page.evaluate("() => { %s; }" % ESSAI_TURC)
            self.assertTrue(self.page.evaluate("(code) => I18n.choisir(code)", langue))
            champ = self.page.evaluate(SELECTEUR_JS, equipements)
            self.page.fill("#" + champ, "pompe")
            ordres[langue] = self.page.evaluate(OPTIONS_JS)
            self.page.evaluate("() => document.querySelectorAll('.selecteur-equipement').forEach((bloc) => bloc.parentNode.remove())")
        self.assertEqual(ordres, {langue: ORDRE_DES_REPERES for langue in ("fr", "en", "xx")})


# ---------------------------------------------------------------------------
# Navigateur : la recherche du wiki plie de même
# ---------------------------------------------------------------------------

class TestRechercheDuWiki(CasNavigateur):

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS_WIKI)
        tables = {"equipements": texte_csv([{"id": "EQ-0001", "repere": "PR-01", "designation": "Presse hydraulique",
                                             "marque": "Schuler", "modele": "HP 250", "statut": "en service",
                                             "actif": "1"}]),
                  "ordres_travail": texte_csv([ot_clos("OT-2026-0001", "Fuite vanne İSTANBUL"),
                                               ot_clos("OT-2026-0002", "Bruit pompe IRMAK"),
                                               ot_clos("OT-2026-0003", "Courroie détendue")])}
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", tables)

    def trouves(self, requete):
        reponse = self.page.evaluate("(texte) => Wiki.rechercher(texte, {})", requete)
        return [r["otId"] for portee in reponse["portees"] for r in portee["resultats"]]

    def test_istanbul_et_irmak_trouves(self):
        for requete, attendus in (("istanbul", ["OT-2026-0001"]), ("İSTANBUL", ["OT-2026-0001"]),
                                  ("ırmak", ["OT-2026-0002"]), ("irmak", ["OT-2026-0002"]),
                                  ("courroie detendue", ["OT-2026-0003"])):
            with self.subTest(requete=requete):
                self.assertEqual(self.trouves(requete), attendus)

    def test_mots_de_recherche_du_wiki(self):
        mots = self.page.evaluate("(valeurs) => valeurs.map((v) => Wiki.motsRecherche(v))",
                                  ["İSTANBUL", "istanbul", "ırmak", "IRMAK", "Straße", "Œillet ÉCROU"])
        self.assertEqual(mots, [["istanbul"], ["istanbul"], ["irmak"], ["irmak"], ["strasse"], ["oeillet", "ecrou"]])


if __name__ == "__main__":
    unittest.main()
