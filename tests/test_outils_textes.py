"""Tests des outils de textes du chantier i18n (T236) : outils/extraire_textes.py et outils/controler_textes.py.

Sans navigateur, bibliothèque standard seulement. Petits fichiers d'essai écrits dans un dossier temporaire ;
sur le vrai dépôt, seulement des essais (--essai : rien n'est écrit). Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_outils_textes.py" -v
"""
import hashlib
import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outils'))
import controler_textes as ctl  # noqa: E402
import extraire_textes as ext  # noqa: E402
import jslex  # noqa: E402

# Module d'essai (domaine planning : le nom de fichier commence par « planning- »).
MODULE = r"""'use strict';
const EssaiPlanning = (() => {

  const LIBELLES = ['Bonjour le monde'];
  const CLASSES = { P1: 'accent-p1' };

  function pluriel(nombre, mot) {
    return nombre + ' ' + mot + (nombre > 1 ? 's' : '');
  }

  function titre() {
    return 'Liste des interventions';
  }

  function resume(n, nom) {
    return `${n} intervention${n > 1 ? 's' : ''} pour ${nom}`;
  }

  function carte(ot) {
    return UI.html`<div class="carte ${CLASSES[ot.priorite] || ''}" title="Ouvrir ${ot.id}">
      <h2>Fiche de l'équipement</h2>
      <p>Cliquez sur <b>Enregistrer</b> pour valider ${ot.id}.</p>
      <p>Prix&nbsp;: ${ot.prix}</p>
      <label>Technicien <span class="requis">*</span></label>
    </div>`;
  }

  function message(ot, date) {
    return 'L\'OT ' + ot.id + ' est prévu le ' + date + '.';
  }

  function compte(liste) {
    return pluriel(liste.length, 'pièce') + ' en stock';
  }

  function lignes(n) {
    return n + ' ligne(s) importée(s)';
  }

  function erreurs() {
    UI.toast('Erreur de saisie');
    UI.toast('Erreur : saisie !');
  }

  function journal(ot) {
    console.warn('Texte de console ' + ot.id);
    const motif = 'Pièce : ' + ot.id;
    return ot.statut === 'En attente' ? 'Attente longue' : 'Libre';
  }

  function brut() {
    return '<span title="Info bulle">Texte en HTML</span>';
  }

  function choix(ok) {
    return 'Le contrôle ' + (ok ? 'est conforme' : 'a échoué') + ' aujourd\'hui.';
  }

  return { titre, resume, carte, message, compte, lignes, erreurs, journal, brut, choix, LIBELLES };
})();
"""

PAGE = """<!doctype html>
<html lang="fr">
<head>
  <title>Essai de page</title>
</head>
<body>
  <div id="ecran-essai">
    <h1>Bienvenue</h1>
    <input id="recherche" placeholder="Rechercher un équipement">
    <p>Texte <b>mêlé</b> de balises</p>
  </div>
</body>
</html>
"""

SCHEMA = """const Schema = (() => {
  function choix(nom, libelle, valeurs) { return { nom, libelle, valeurs }; }
  const CRITICITES = ['A', 'B', 'C'];
  const PRIORITES = ['P1', 'P2', 'P3', 'P4'];
  const TABLES = [choix('statut', 'Statut', ['Créé', 'En attente', 'Clôturé'])];
  return { TABLES };
})();
"""

# Jeu « propre » : rien à relire, pour vérifier le code retour du contrôle avant et après extraction.
MODULE_PROPRE = r"""'use strict';
const EssaiCauses = (() => {
  function titre(nom) {
    return 'Bonjour ' + nom + ' !';
  }
  function bloc(n) {
    return UI.html`<p>Texte du bloc</p><p>${n} cause${n > 1 ? 's' : ''} trouvée${n > 1 ? 's' : ''}</p>`;
  }
  return { titre, bloc };
})();
"""

PAGE_PROPRE = """<!doctype html>
<html lang="fr">
<head><title>Essai</title></head>
<body><h1>Bienvenue</h1><input placeholder="Rechercher"></body>
</html>
"""


def ligne_de(texte, motif):
    return texte[:texte.index(motif)].count('\n') + 1


def ecrire(racine, rel, texte):
    chemin = Path(racine) / rel
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding='utf-8', newline='\n')


def ecrire_jeu(racine):
    ecrire(racine, 'js/modules/planning-essai.js', MODULE)
    ecrire(racine, 'index.html', PAGE)
    ecrire(racine, 'js/schema.js', SCHEMA)


def ecrire_jeu_propre(racine):
    ecrire(racine, 'js/modules/causes-essai.js', MODULE_PROPRE)
    ecrire(racine, 'index.html', PAGE_PROPRE)


def empreintes(racine):
    return {p.relative_to(racine).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(racine).rglob('*')) if p.is_file()}


def extraire(racine, section='planning', fichiers=('js/modules/planning-essai.js', 'index.html'), **options):
    return ext.Extracteur(racine).extraire(section, list(fichiers), **options)


def controler(racine, domaines=None):
    controle = ctl.Controle(racine)
    controle.lancer(domaines)
    return controle


class TestAnalyseLexicale(unittest.TestCase):

    def test_chaines_gabarits_et_expressions_regulieres(self):
        source = "const a = x / 2 / y; const r = /[/']/g; const t = `a${b + `c${d}`}e`; // 'pas ici'\n"
        jetons = jslex.lexer(source)
        genres = [(j.genre, j.valeur) for j in jetons if j.genre in ('chaine', 'gabarit', 'regex')]
        self.assertEqual(genres[0], ('regex', "/[/']/g"))
        self.assertEqual(genres[1][0], 'gabarit')
        self.assertEqual(len(genres), 2)                       # le commentaire n'est pas lu

    def test_nom_appele(self):
        arbre = jslex.construire_arbre("UI.vide('a'); x.map(f).join(', '); if (y) z();")
        groupes = [(i, n) for i, n in enumerate(arbre) if isinstance(n, jslex.Groupe)]
        noms = [jslex.nom_appele(arbre, i) for i, _ in groupes]
        self.assertEqual(noms, ['UI.vide', 'x.map', '….join', None, 'z'])

    def test_decoder(self):
        self.assertEqual(jslex.decoder(r"l\'atelier : \n"), "l'atelier : \n")


class TestExtraction(unittest.TestCase):

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self.dossier.name)
        ecrire_jeu(self.racine)

    def tearDown(self):
        self.dossier.cleanup()

    def lire(self, rel):
        return (self.racine / rel).read_text(encoding='utf-8')

    def test_extraction_complete(self):
        res = extraire(self.racine)
        self.assertEqual(res.erreurs, [])
        source = self.lire('js/modules/planning-essai.js')
        valeurs = ext.lire_dictionnaire(self.racine / 'js/i18n/fr.js')['planning'][1]
        attendu = {
            # littéral simple
            'planning.titre.liste_interventions': "'Liste des interventions'",
            # concaténation regroupée en une clé avec des variables
            'planning.message.ot_prevu': "'L\\'OT {otId} est prévu le {date}.'",
            # gabarit + pluriel local « > 1 ? 's' : '' »
            'planning.resume.n_interventions_nom': "{ one: '{n} intervention pour {nom}', other: '{n} interventions "
                                                  "pour {nom}' }",
            # petite fonction pluriel(n, mot)
            'planning.compte.pieces_stock': "{ one: '{n} pièce en stock', other: '{n} pièces en stock' }",
            # « (s) » après un nombre sûr : les deux formes gardent le texte d'avant
            'planning.lignes.ligne_importee': "{ one: '{n} ligne(s) importée(s)', other: '{n} ligne(s) "
                                              "importée(s)' }",
            # UI.html : texte entre balises, phrase balisée (I18n.html), entité, attribut
            'planning.carte.fiche_equipement': "'Fiche de l\\'équipement'",
            'planning.carte.cliquez_enregistrer_valider': "'Cliquez sur <b>Enregistrer</b> pour valider {otId}.'",
            'planning.carte.prix_prix': "'Prix&nbsp;: {prix}'",
            'planning.carte.ouvrir_ot_id': "'Ouvrir {otId}'",
            'planning.carte.technicien': "'Technicien'",
            # collision : même résumé, deux textes → _2
            'planning.erreurs.erreur_saisie': "'Erreur de saisie'",
            'planning.erreurs.erreur_saisie_2': "'Erreur : saisie !'",
            # caractère invisible : écrit par son échappement
            'planning.journal.attente_longue': "'Attente\\u00a0longue'",
            'planning.journal.libre': "'Libre'",
            # index.html
            'planning.page.essai_page': "'Essai de page'",
            'planning.ecran_essai.bienvenue': "'Bienvenue'",
            'planning.recherche.rechercher_equipement': "'Rechercher un équipement'",
        }
        self.assertEqual({k: ext.affichage(v) for k, v in valeurs.items()}, attendu)
        self.assertIn("return I18n.t('planning.titre.liste_interventions');", source)
        self.assertIn("return I18n.t('planning.message.ot_prevu', { otId: ot.id, date });", source)
        self.assertIn("return I18n.t('planning.resume.n_interventions_nom', { n, nom });", source)
        self.assertIn("return I18n.t('planning.compte.pieces_stock', { n: liste.length });", source)
        self.assertIn("return I18n.t('planning.lignes.ligne_importee', { n });", source)
        self.assertIn("<p>${I18n.html('planning.carte.cliquez_enregistrer_valider', { otId: ot.id })}</p>", source)
        self.assertIn("<p>${I18n.html('planning.carte.prix_prix', { prix: ot.prix })}</p>", source)
        self.assertIn('title="${I18n.t(\'planning.carte.ouvrir_ot_id\', { otId: ot.id })}"', source)
        self.assertIn("<label>${I18n.t('planning.carte.technicien')} <span class=\"requis\">*</span></label>",
                      source)
        page = self.lire('index.html')
        self.assertIn('<title data-i18n="planning.page.essai_page">Essai de page</title>', page)
        self.assertIn('placeholder="Rechercher un équipement" data-i18n-attr="placeholder:planning.recherche.'
                      'rechercher_equipement">', page)
        self.assertEqual([c[:2] for c in res.collisions], [('planning.erreurs.erreur_saisie',
                                                            'planning.erreurs.erreur_saisie_2')])

    def test_exceptions_et_cas_au_rapport(self):
        res = extraire(self.racine)
        source = self.lire('js/modules/planning-essai.js')
        # exceptions : console (D157), marqueur « Pièce : » (D156), valeur stockée « En attente » (D155)
        self.assertIn("console.warn('Texte de console ' + ot.id);", source)
        self.assertIn("const motif = 'Pièce : ' + ot.id;", source)
        self.assertIn("ot.statut === 'En attente'", source)
        self.assertGreaterEqual(res.exclus, 2)
        js = 'js/modules/planning-essai.js'
        self.assertEqual({(r[0], r[1], r[3].split(' (')[0]) for r in res.relectures}, {
            (js, ligne_de(MODULE, 'Bonjour le monde'), 'texte figé au chargement du module'),   # constante figée
            (js, ligne_de(MODULE, 'Info bulle'), 'HTML dans une chaîne'),        # attribut HTML dans une chaîne
            (js, ligne_de(MODULE, 'Le contrôle'), "choix de texte ou fragment HTML au milieu d'une phrase"),
            ('index.html', ligne_de(PAGE, 'mêlé'), 'texte mêlé à des balises'),
        })
        # rien n'est réécrit pour ces cas
        self.assertIn("const LIBELLES = ['Bonjour le monde'];", source)
        self.assertIn("return '<span title=\"Info bulle\">Texte en HTML</span>';", source)
        self.assertIn("return 'Le contrôle ' + (ok ? 'est conforme' : 'a échoué') + ' aujourd\\'hui.';", source)
        self.assertIn('<p>Texte <b>mêlé</b> de balises</p>', self.lire('index.html'))

    def test_texte_affiche_identique(self):
        res = extraire(self.racine)
        self.assertGreater(len(res.unites), 15)
        valeurs = {}
        for section, (langue, entrees) in ext.lire_dictionnaire(self.racine / 'js/i18n/fr.js').items():
            valeurs.update(entrees)
        for unite in res.unites:
            with self.subTest(cle=unite.cle):
                self.assertEqual(valeurs[unite.cle], unite.valeur)          # relu tel qu'écrit
                self.assertTrue(ext.verifier_unite(unite), (unite.valeur, unite.original, unite.vars))
        # aucun caractère invisible en clair dans le dictionnaire (test_depot les refuse)
        texte = self.lire('js/i18n/fr.js')
        for invisible in ext.INVISIBLES:
            self.assertNotIn(invisible, texte)

    def test_second_passage_sans_changement(self):
        extraire(self.racine)
        avant = empreintes(self.racine)
        res = extraire(self.racine)
        self.assertEqual(res.unites, [])
        self.assertEqual(res.fichiers_modifies, [])
        self.assertEqual(empreintes(self.racine), avant)

    def test_deterministe(self):
        autre = tempfile.TemporaryDirectory()
        self.addCleanup(autre.cleanup)
        ecrire_jeu(autre.name)
        extraire(self.racine)
        extraire(autre.name, fichiers=('index.html', 'js/modules/planning-essai.js'))
        self.assertEqual(empreintes(self.racine), empreintes(autre.name))

    def test_essai_n_ecrit_rien(self):
        avant = empreintes(self.racine)
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            code = ext.main(['--racine', str(self.racine), '--section', 'planning', '--essai',
                             'js/modules/planning-essai.js', 'index.html'])
        self.assertEqual(code, 0)
        self.assertEqual(empreintes(self.racine), avant)
        self.assertFalse((self.racine / 'js/i18n/fr.js').exists())
        texte = sortie.getvalue()
        self.assertIn("(essai : rien n'est écrit)", texte)
        self.assertIn('Fichiers seraient modifiés : index.html, js/modules/planning-essai.js, js/i18n/fr.js', texte)
        self.assertIn('== À relire', texte)

    def test_bloc_existant_complete_et_trie(self):
        ecrire(self.racine, 'js/i18n/fr.js', "// en-tête gardé\n\n// ==== section commun ====\n"
                                              "I18n.ajouter('fr', {\n  'commun.ok': 'OK',\n});\n"
                                              "// ==== fin commun ====\n\n// ==== section planning ====\n"
                                              "I18n.ajouter('fr', {\n  'planning.zzz.dernier': \"Dernier\",\n});\n"
                                              "// ==== fin planning ====\n")
        extraire(self.racine)
        texte = self.lire('js/i18n/fr.js')
        self.assertTrue(texte.startswith("// en-tête gardé\n\n// ==== section commun ====\n"
                                         "I18n.ajouter('fr', {\n  'commun.ok': 'OK',\n});\n"))
        bloc = texte.split('// ==== section planning ====\n')[1].split('// ==== fin planning ====')[0]
        cles = [ligne.split("'")[1] for ligne in bloc.splitlines() if ligne.startswith("  '")]
        self.assertEqual(cles, sorted(cles))
        self.assertIn("  'planning.zzz.dernier': 'Dernier',", bloc)

    def test_commun_seulement_sur_demande(self):
        ecrire(self.racine, 'js/modules/causes-essai.js', "'use strict';\nconst C = (() => {\n"
                                                           "  function f() { return 'Liste des interventions'; }\n"
                                                           "  return { f };\n})();\n")
        res = extraire(self.racine, fichiers=('js/modules/planning-essai.js',))
        self.assertNotIn('commun', res.nouvelles)
        self.dossier.cleanup()
        self.dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self.dossier.name)
        ecrire_jeu(self.racine)
        ecrire(self.racine, 'js/modules/causes-essai.js', "'use strict';\nconst C = (() => {\n"
                                                           "  function f() { return 'Liste des interventions'; }\n"
                                                           "  return { f };\n})();\n")
        res = extraire(self.racine, fichiers=('js/modules/planning-essai.js',), commun=True)
        self.assertEqual(res.nouvelles['commun'], {'commun.liste_interventions': 'Liste des interventions'})
        self.assertIn("I18n.t('commun.liste_interventions')", self.lire('js/modules/planning-essai.js'))


class TestControle(unittest.TestCase):

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self.dossier.name)
        ecrire_jeu_propre(self.racine)

    def tearDown(self):
        self.dossier.cleanup()

    def code(self, *args):
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            code = ctl.main(['--racine', str(self.racine)] + list(args))
        return code, sortie.getvalue()

    def test_controle_a_1_avant_extraction_et_a_0_apres(self):
        code, texte = self.code()
        self.assertEqual(code, 1, texte)
        self.assertIn('Textes visibles restés en dur : 6', texte)
        ext.Extracteur(self.racine).extraire('causes', ['js/modules/causes-essai.js'])
        ext.Extracteur(self.racine).extraire('socle', ['index.html'])
        code, texte = self.code()
        self.assertEqual(code, 0, texte)
        self.assertIn('Résultat : rien à signaler.', texte)
        code, texte = self.code('--domaine', 'causes')
        self.assertEqual(code, 0, texte)
        self.assertIn('domaines : causes (1 fichiers)', texte)

    def test_cles_manquantes_orphelines_et_variables(self):
        ext.Extracteur(self.racine).extraire('causes', ['js/modules/causes-essai.js'])
        ext.Extracteur(self.racine).extraire('socle', ['index.html'])
        module = (self.racine / 'js/modules/causes-essai.js').read_text(encoding='utf-8')
        module = module.replace("{ nom }", "{ autre: nom }").replace(
            "return { titre, bloc };", "I18n.t('causes.essai.absente');\n  return { titre, bloc };")
        ecrire(self.racine, 'js/modules/causes-essai.js', module)
        dico = (self.racine / 'js/i18n/fr.js').read_text(encoding='utf-8')
        ecrire(self.racine, 'js/i18n/fr.js', dico.replace("I18n.ajouter('fr', {\n",
                                                          "I18n.ajouter('fr', {\n  'causes.essai.inutile': 'X',\n", 1))
        controle = controler(self.racine)
        genres = sorted((s.genre, s.message.split(' : ')[0]) for s in controle.signalements)
        self.assertEqual(genres, [('manquante', 'clé absente du dictionnaire'),
                                  ('orpheline', 'clé jamais employée'),
                                  ('variables', 'causes.titre.bonjour_nom')])
        self.assertIn('appel { autre }, valeur { nom }', [s.message.split(' : ', 1)[1] for s in
                                                          controle.signalements if s.genre == 'variables'][0])

    def test_page_differente_du_dictionnaire(self):
        ext.Extracteur(self.racine).extraire('socle', ['index.html'])
        page = (self.racine / 'index.html').read_text(encoding='utf-8')
        ecrire(self.racine, 'index.html', page.replace('>Bienvenue<', '>Bonjour<'))
        controle = controler(self.racine, ['socle'])
        self.assertEqual([s.genre for s in controle.signalements if s.genre == 'page'], ['page'])

    def test_lot3_prevu_mais_pas_fait(self):
        # La comparaison des langues (Lot 3) n'existe pas encore : aucune fonction factice ne fait semblant.
        self.assertFalse(hasattr(ctl, 'comparer_langue'))
        self.assertTrue(hasattr(ctl, 'Langue'))


class TestDepotReel(unittest.TestCase):
    """Sur le vrai dépôt, seulement en essai : rien n'est écrit."""

    def test_domaines_des_modules(self):
        for chemin in sorted((RACINE / 'js' / 'modules').glob('*.js')):
            with self.subTest(module=chemin.name):
                self.assertIn(ext.domaine_du_fichier('js/modules/' + chemin.name), ext.SECTIONS)
        self.assertEqual(ext.fichiers_du_domaine(RACINE, 'planning'),
                         ['js/modules/planning-ecrans.js', 'js/modules/planning-ecritures.js',
                          'js/modules/planning-regles.js'])
        self.assertEqual(ext.domaine_du_fichier('js/modules/parametres-zip.js'), 'zip')
        self.assertEqual(ext.domaine_du_fichier('index.html'), 'socle')

    def test_essai_sur_le_domaine_pilote(self):
        avant = {f: hashlib.sha256((RACINE / f).read_bytes()).hexdigest()
                 for d in ext.DOMAINE_PILOTE for f in ext.fichiers_du_domaine(RACINE, d)}
        extracteur = ext.Extracteur(RACINE)
        lignes = []
        total_extraits = total_relire = 0
        for domaine in ext.DOMAINE_PILOTE:
            res = extracteur.extraire(domaine, ext.fichiers_du_domaine(RACINE, domaine), essai=True)
            self.assertEqual(res.erreurs, [], domaine)
            for unite in res.unites:
                self.assertTrue(ext.verifier_unite(unite), (unite.fichier, unite.ligne, unite.valeur))
            raisons = {}
            for r in res.relectures:
                raisons[r[3]] = raisons.get(r[3], 0) + 1
            total_extraits += len(res.unites)
            total_relire += len(res.relectures)
            lignes.append('  %-9s %3d extraits, %3d à relire %s' % (domaine, len(res.unites), len(res.relectures),
                                                                    dict(sorted(raisons.items()))))
        apres = {f: hashlib.sha256((RACINE / f).read_bytes()).hexdigest() for f in avant}
        self.assertEqual(apres, avant)
        self.assertGreater(total_extraits, 50)
        print('\nDomaine pilote (essai) : %d extraits, %d à relire' % (total_extraits, total_relire))
        print('\n'.join(lignes))


if __name__ == '__main__':
    unittest.main()
