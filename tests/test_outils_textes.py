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

    def test_commun_existant_reprend_sans_creer(self):
        """T257 : --commun-existant reprend une clé commun.* déjà écrite, n'en crée aucune, même pour un texte
        répété dans deux domaines (les domaines extraits en parallèle ne touchent pas la section commun)."""
        ecrire(self.racine, 'js/i18n/fr.js', "// ==== section commun ====\n"
                                              "I18n.ajouter('fr', {\n"
                                              "  'commun.titre.liste': 'Liste des interventions',\n});\n"
                                              "// ==== fin commun ====\n\n// ==== section planning ====\n"
                                              "I18n.ajouter('fr', {\n});\n// ==== fin planning ====\n")
        ecrire(self.racine, 'js/modules/causes-essai.js', "'use strict';\nconst C = (() => {\n"
                                                           "  function f() { return 'Fiche de l\\'équipement'; }\n"
                                                           "  return { f };\n})();\n")
        avant_commun = self.lire('js/i18n/fr.js').split('// ==== fin commun ====')[0]
        res = extraire(self.racine, fichiers=('js/modules/planning-essai.js',), commun_existant=True)
        self.assertNotIn('commun', res.nouvelles)
        self.assertEqual(self.lire('js/i18n/fr.js').split('// ==== fin commun ====')[0], avant_commun)
        module = self.lire('js/modules/planning-essai.js')
        self.assertIn("I18n.t('commun.titre.liste')", module)
        self.assertNotIn("'Liste des interventions'", module)
        self.assertEqual([u.cle for u in res.unites if u.commun], ['commun.titre.liste'])
        texte = ext.rapport(res)
        self.assertIn('== Clés commun.* employées (1)', texte)
        self.assertIn('commun.titre.liste = ', texte)
        # répété dans deux domaines mais absent de la section commun : clé du domaine, jamais commun.*
        fiche = [u for u in res.unites if 'Fiche de l' in str(u.valeur)]
        self.assertEqual(len(fiche), 1)
        self.assertFalse(fiche[0].commun)
        self.assertTrue(fiche[0].cle.startswith('planning.'), fiche[0].cle)


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

    def test_cle_calculee_ne_couvre_plus_tout_le_dictionnaire(self):
        """T262 : un I18n.t(cle) entièrement calculé faisait passer toutes les clés pour employées ; seules comptent
        désormais les clés écrites en chaîne dans le code (passées ensuite par une variable) et les préfixes littéraux."""
        ext.Extracteur(self.racine).extraire('causes', ['js/modules/causes-essai.js'])
        ext.Extracteur(self.racine).extraire('socle', ['index.html'])
        module = (self.racine / 'js/modules/causes-essai.js').read_text(encoding='utf-8')
        module = module.replace("return { titre, bloc };",
                                "function dates() { return ['causes.essai.debut'].map((cle) => I18n.t(cle)); }\n"
                                "  return { titre, bloc, dates };")
        ecrire(self.racine, 'js/modules/causes-essai.js', module)
        dico = (self.racine / 'js/i18n/fr.js').read_text(encoding='utf-8')
        ecrire(self.racine, 'js/i18n/fr.js', dico.replace(
            "I18n.ajouter('fr', {\n", "I18n.ajouter('fr', {\n  'causes.essai.debut': 'Début',\n"
                                      "  'causes.essai.inutile': 'X',\n", 1))
        controle = controler(self.racine)
        orphelines = [s.message for s in controle.signalements if s.genre == 'orpheline']
        self.assertEqual(orphelines, ['clé jamais employée : causes.essai.inutile'])

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


# Corrections apprises sur le domaine pilote (T237). Module du domaine « mise » : fragment optionnel « (…) »,
# sauts de ligne de mise en page d'un gabarit UI.html (et un <pre>), variables sans nom, accesseurs d'App.ecran.
MODULE_PILOTE = r"""'use strict';
const EssaiMise = (() => {
  function bandeau(f) {
    return UI.html`<p>Prévo ${f.version} est disponible${f.date ? ' (' + UI.dateFr(f.date) + ')' : ''}.</p>`;
  }
  function message(t) {
    return 'Tailscale absent' + (t.raison ? ' (' + t.raison + ')' : '') + '.';
  }
  function explication() {
    return UI.html`<p class="note">Une fourchette contient la vraie part
        95 fois sur 100 ; elle se resserre.</p>`;
  }
  function preformate() {
    return UI.html`<pre>Ligne gardée
  telle quelle</pre>`;
  }
  function semaine(g) {
    return UI.html`<p>Semaine du ${UI.dateFr(g.jours[0])} au ${UI.dateFr(g.jours[6])}.</p>`;
  }
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'essai', route: /^#\/essai$/,
      get titre() { return 'Essai'; },
      menu: { get libelle() { return 'Essai court'; }, icone: 'essai', ordre: 1 },
      afficher() {},
    });
    App.ecran({ id: 'fige', route: /^#\/fige$/, titre: 'Écran figé', afficher() {} });
  });
  return { bandeau, message, explication, preformate, semaine };
})();
"""


class TestCorrectionsDuPilote(unittest.TestCase):
    MODULE = 'js/modules/mise-essai.js'

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self.dossier.name)
        ecrire(self.racine, self.MODULE, MODULE_PILOTE)

    def tearDown(self):
        self.dossier.cleanup()

    def extraire(self):
        return ext.Extracteur(self.racine).extraire('mise', [self.MODULE])

    def lire(self, rel):
        return (self.racine / rel).read_text(encoding='utf-8')

    def valeurs(self):
        return ext.lire_dictionnaire(self.racine / 'js/i18n/fr.js')['mise'][1]

    def test_fragment_optionnel_au_rapport(self):
        # « est disponible${date ? ' (' + date + ')' : ''}. » serait devenu {v1} : la parenthèse cachée au traducteur.
        res = self.extraire()
        fragments = [r for r in res.relectures if r[3].startswith('fragment optionnel')]
        self.assertEqual([r[1] for r in fragments], [ligne_de(MODULE_PILOTE, 'Prévo ${'),
                                                     ligne_de(MODULE_PILOTE, 'Tailscale absent')])
        source = self.lire(self.MODULE)
        self.assertIn("est disponible${f.date ? ' (' + UI.dateFr(f.date) + ')' : ''}.</p>", source)
        self.assertIn("return 'Tailscale absent' + (t.raison ? ' (' + t.raison + ')' : '') + '.';", source)

    def test_saut_de_ligne_de_mise_en_page_ramene_a_une_espace(self):
        res = self.extraire()
        valeurs = self.valeurs()
        # gabarit UI.html : le saut de ligne et l'indentation du code s'affichent comme une espace
        self.assertEqual(valeurs['mise.explication.fourchette_contient_vraie_part'],
                         'Une fourchette contient la vraie part 95 fois sur 100 ; elle se resserre.')
        self.assertIn("<p class=\"note\">${I18n.t('mise.explication.fourchette_contient_vraie_part')}</p>",
                      self.lire(self.MODULE))
        # <pre> : gardé tel quel
        self.assertEqual(valeurs['mise.preformate.ligne_gardee_telle_quelle'], 'Ligne gardée\\n  telle quelle')
        for unite in res.unites:
            self.assertTrue(ext.verifier_unite(unite), (unite.valeur, unite.original))
        avant = empreintes(self.racine)
        self.assertEqual(self.extraire().unites, [])
        self.assertEqual(empreintes(self.racine), avant)

    def test_accesseurs_d_app_ecran_lus_a_l_affichage(self):
        # get titre() / get libelle() : lus à chaque affichage, donc extraits ; titre: '…' reste figé (au rapport).
        res = self.extraire()
        source = self.lire(self.MODULE)
        self.assertIn("get titre() { return I18n.t('mise.titre.essai'); },", source)
        self.assertIn("menu: { get libelle() { return I18n.t('mise.libelle.essai_court'); }, icone: 'essai'", source)
        figes = [r[2] for r in res.relectures if r[3].startswith('texte figé')]
        self.assertEqual(figes, ['Écran figé'])

    def test_variables_a_nommer(self):
        res = self.extraire()
        texte = ext.rapport(res)
        self.assertIn('textes aux variables à nommer : 1', texte)
        self.assertIn("mise.semaine.semaine_v1_v2 : {v1}, {v2} = 'Semaine du {v1} au {v2}.'", texte)
        self.assertEqual(ext.variables_a_nommer(res.unites[0]), [])
        for nom, attendu in (('v1', True), ('pourcent2', True), ('MINIMUM_PAR_DEFAUT', True), ('debut', False),
                             ('otId', False), ('n', False)):
            self.assertEqual(bool(ext.RE_NOM_GENERIQUE.match(nom)) and nom != 'n', attendu, nom)
        controle = controler(self.racine, ['mise'])
        self.assertEqual([s.message for s in controle.signalements if s.genre == 'nommer'],
                         ['mise.semaine.semaine_v1_v2 : {v1}, {v2}'])
        # renommées à la main (clé, valeur et appel) : plus rien à signaler de ce genre
        for rel, avant, apres in (
                ('js/i18n/fr.js', "'mise.semaine.semaine_v1_v2': 'Semaine du {v1} au {v2}.'",
                 "'mise.semaine.semaine_du_au': 'Semaine du {debut} au {fin}.'"),
                (self.MODULE, "I18n.t('mise.semaine.semaine_v1_v2', { v1: UI.dateFr(g.jours[0]), v2: "
                              "UI.dateFr(g.jours[6]) })",
                 "I18n.t('mise.semaine.semaine_du_au', { debut: UI.dateFr(g.jours[0]), fin: UI.dateFr(g.jours[6]) })")):
            contenu = self.lire(rel)
            self.assertIn(avant, contenu)
            ecrire(self.racine, rel, contenu.replace(avant, apres))
        controle = controler(self.racine, ['mise'])
        self.assertEqual([s for s in controle.signalements if s.genre in ('nommer', 'variables', 'manquante',
                                                                          'orpheline')], [])

    def test_contexte_de_signaler_erreur_jamais_extrait(self):
        # App.signalerErreur(erreur, contexte) : le contexte ne va qu'à la console (D157) ; le toast, lui, est extrait.
        ecrire(self.racine, 'js/modules/planning-essai.js',
               "'use strict';\nconst EssaiErreur = (() => {\n  function echec(erreur, otId) {\n"
               "    App.signalerErreur(erreur, 'planification de ' + otId);\n"
               "    UI.toast('Planification refusée pour ' + otId + '.', 'erreur');\n  }\n  return { echec };\n})();\n")
        res = ext.Extracteur(self.racine).extraire('planning', ['js/modules/planning-essai.js'])
        source = self.lire('js/modules/planning-essai.js')
        self.assertIn("App.signalerErreur(erreur, 'planification de ' + otId);", source)
        self.assertIn("UI.toast(I18n.t('planning.echec.planification_refusee', { otId }), 'erreur');", source)
        self.assertEqual((len(res.unites), res.relectures, res.exclus), (1, [], 1))

    def test_domaine_a_part_pour_l_aide_longue(self):
        ecrire(self.racine, 'js/modules/aide-ecrans.js',
               "'use strict';\nconst AideEssai = (() => {\n  function bouton() { return 'Compris'; }\n"
               "  return { bouton };\n})();\n")
        ecrire(self.racine, 'js/modules/aide-ecrans-textes.js',
               "'use strict';\nconst AideEssaiTextes = { accueil: { titre: 'Accueil du responsable' } };\n")
        self.assertEqual(ext.domaine_du_fichier('js/modules/aide-ecrans-textes.js'), 'aide-longue')
        self.assertEqual(ext.domaine_du_fichier('js/modules/aide-ecrans.js'), 'aide')
        self.assertEqual(ext.fichiers_du_domaine(self.racine, 'aide'), ['js/modules/aide-ecrans.js'])
        self.assertEqual(ext.fichiers_du_domaine(self.racine, 'aide-longue'), ['js/modules/aide-ecrans-textes.js'])
        self.assertEqual((ext.section_du_domaine('aide-longue'), ext.dictionnaire_du_domaine('aide-longue')),
                         ('aide', 'js/i18n/aide/fr.js'))
        self.assertEqual((ext.section_du_domaine('planning'), ext.dictionnaire_du_domaine('planning')),
                         ('planning', 'js/i18n/fr.js'))
        self.assertIn('aide-longue', ext.tous_les_fichiers(self.racine))
        # le contrôle du domaine « aide » ne compte plus l'aide longue ; elle a son domaine
        aide = controler(self.racine, ['aide'])
        self.assertEqual(aide.fichiers, ['js/modules/aide-ecrans.js'])
        self.assertEqual([s.message for s in aide.signalements if s.genre == 'dur'], ['« Compris »'])
        longue = controler(self.racine, ['aide-longue'])
        self.assertEqual(longue.fichiers, ['js/modules/aide-ecrans-textes.js'])
        self.assertEqual(len([s for s in longue.signalements if s.genre == 'dur']), 1)
        # en ligne de commande : domaine reconnu, extraction vers js/i18n/aide/fr.js (essai)
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            code = ext.main(['--racine', str(self.racine), '--domaine', 'aide-longue', '--essai'])
        self.assertEqual(code, 0)
        self.assertIn('section aide → js/i18n/aide/fr.js (essai', sortie.getvalue())


class TestDepotReel(unittest.TestCase):
    """Sur le vrai dépôt, seulement en essai : rien n'est écrit."""

    def test_domaines_des_modules(self):
        for chemin in sorted((RACINE / 'js' / 'modules').glob('*.js')):
            with self.subTest(module=chemin.name):
                self.assertIn(ext.domaine_du_fichier('js/modules/' + chemin.name), ext.DOMAINES)
        self.assertEqual(ext.fichiers_du_domaine(RACINE, 'planning'),
                         ['js/modules/planning-ecrans.js', 'js/modules/planning-ecritures.js',
                          'js/modules/planning-regles.js'])
        self.assertEqual(ext.domaine_du_fichier('js/modules/parametres-zip.js'), 'zip')
        self.assertEqual(ext.domaine_du_fichier('index.html'), 'socle')
        # l'aide longue générée a son domaine (T237) : le domaine « aide » n'est que l'aide courte
        self.assertEqual(ext.fichiers_du_domaine(RACINE, 'aide'), ['js/modules/aide-ecrans.js'])
        self.assertEqual(ext.fichiers_du_domaine(RACINE, 'aide-longue'), ['js/modules/aide-ecrans-textes.js'])

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
        # le pilote est extrait (T237) : plus rien à extraire ni à relire, et il le reste
        self.assertEqual((total_extraits, total_relire), (0, 0), '\n'.join(lignes))


# Import (T242) : les valeurs d'exemple des modèles à remplir (données de démo, D146) et les synonymes de titres
# reconnus à l'import ne sont jamais extraits (exceptions propres à js/modules/import-regles.js : S(…) 2e argument,
# V(…) 4e argument, SITE, CHEMIN) ; le libellé, lu par une fonction, l'est.
MODULE_IMPORT = r"""'use strict';
const EssaiImport = (() => {
  const SITE = 'Site des Trois Vallées';
  const CHEMIN = 'chemin|chemin de localisation|emplacement';
  const S = (table, exemples) => exemples;
  const V = (cle, libelle, type, exemple, liste) => ({ cle, get libelle() { return libelle(); }, type, exemple, liste });
  const TYPES = {
    equipements: [V('chemin', () => 'Localisation', 'texte', SITE + ' > Atelier Usinage', CHEMIN),
      S('equipements', { designation: "Machine d'exemple", criticite: ['B', 'classe de criticité'] })],
  };
  return { TYPES };
})();
"""


class TestExceptionsDeLImport(unittest.TestCase):
    MODULE = 'js/modules/import-regles.js'

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self.dossier.name)
        ecrire(self.racine, self.MODULE, MODULE_IMPORT)

    def tearDown(self):
        self.dossier.cleanup()

    def test_exemples_et_synonymes_jamais_extraits(self):
        res = ext.Extracteur(self.racine).extraire('import', [self.MODULE])
        source = (self.racine / self.MODULE).read_text(encoding='utf-8')
        self.assertEqual(([u.texte for u in res.unites], res.relectures), (['Localisation'], []))
        for garde in ("'Site des Trois Vallées'", "'chemin|chemin de localisation|emplacement'", "' > Atelier Usinage'",
                      "\"Machine d'exemple\"", "'classe de criticité'"):
            self.assertIn(garde, source)

    def test_domaine_import_extrait_sur_le_depot(self):
        res = ext.Extracteur(RACINE).extraire('import', ext.fichiers_du_domaine(RACINE, 'import'), essai=True)
        self.assertEqual((res.erreurs, len(res.unites), len(res.relectures)), ([], 0, 0))


# Socle et schéma (T238) : les libellés de js/schema.js sont lus dans fr.js (choix(nom, [valeurs]) n'a plus de libellé) ;
# les valeurs stockées des listes restent reconnues (D155). Le moteur js/i18n.js n'est jamais extrait (D157).
SCHEMA_SANS_LIBELLES = """const Schema = (() => {
  function choix(nom, valeurs) { return { nom, valeurs }; }
  const CRITICITES = ['A', 'B', 'C'];
  const TABLES = [choix('statut', ['Créé', 'En attente']), choix('criticite', CRITICITES),
    choix('impact', 'Impact', ['gêne'])];
  return { TABLES };
})();
"""


class TestSocleEtSchema(unittest.TestCase):

    def test_valeurs_des_listes_lues_sans_libelle(self):
        with tempfile.TemporaryDirectory() as dossier:
            ecrire(dossier, 'js/schema.js', SCHEMA_SANS_LIBELLES)
            _, valeurs, _ = ext.lire_schema(dossier)
        self.assertEqual(valeurs, {'Créé', 'En attente', 'A', 'B', 'C', 'gêne'})

    def test_valeurs_du_vrai_schema(self):
        _, valeurs, _ = ext.lire_schema(RACINE)
        self.assertEqual(len(valeurs), 69)
        self.assertLessEqual({'Clôturé techniquement', 'en service', 'P1', 'B', 'à valider'}, valeurs)

    def test_moteur_de_traduction_jamais_extrait(self):
        self.assertEqual(ext.Classement(RACINE).exception_fichier('js/i18n.js')['classe'], 'D157')

    def test_domaines_socle_et_schema_extraits_sur_le_depot(self):
        extracteur = ext.Extracteur(RACINE)
        for domaine in ('socle', 'schema'):
            with self.subTest(domaine=domaine):
                res = extracteur.extraire(domaine, ext.fichiers_du_domaine(RACINE, domaine), essai=True)
                self.assertEqual((res.erreurs, len(res.unites), len(res.relectures)), ([], 0, 0))


MODULE_PENDANT = '''\
const ParametresEssai = (() => {
  function brancher(bouton, pendant) {
    bouton.addEventListener('click', () => pendant(bouton, 'import ZIP', () => 1));
  }
  return { brancher };
})();
'''


class TestExceptionPendantDesParametres(unittest.TestCase):
    """T245 : le contexte de pendant(bouton, contexte, action) des cartes de Paramètres ne va que dans la console."""

    def test_contexte_jamais_extrait_dans_les_cartes_de_parametres(self):
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            ecrire(racine, 'js/modules/parametres-zip.js', MODULE_PENDANT)
            res = ext.Extracteur(racine).extraire('zip', ['js/modules/parametres-zip.js'])
            self.assertEqual(([u.texte for u in res.unites], res.relectures), ([], []))

    def test_domaines_parametres_sauvegardes_zip_sans_texte_en_dur_sur_le_depot(self):
        for domaine in ('parametres', 'sauvegardes', 'zip'):
            res = ext.Extracteur(RACINE).extraire(domaine, ext.fichiers_du_domaine(RACINE, domaine), essai=True)
            self.assertEqual((res.erreurs, len(res.unites), len(res.relectures)), ([], 0, 0), domaine)


# Aide longue (T247) : js/i18n/aide/fr.js a un bloc de section par outil (« acces » : outils/generer_acces_textes.py,
# « aide » : outils/generer_aide_ecrans.py) ; les outils le lisent et le complètent comme js/i18n/fr.js : le contrôle des
# domaines aide-longue et acces voit ses clés (manquantes, orphelines), l'extraction écrit dans son bloc.
AIDE_FR = """'use strict';
// Aide longue d'essai.

// ==== section aide ====
I18n.ajouter('fr', {
  'aide.ecran.accueil.titre': 'Accueil',
});
// ==== fin aide ====
"""
MODULE_AIDE_LONGUE = """'use strict';
const EssaiAideTextes = {
  accueil: {
    get titre() { return I18n.t('aide.ecran.accueil.titre'); },
    ancre: 'accueil',
  },
};
"""


class TestAideLongueParLangue(unittest.TestCase):

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self.dossier.name)
        ecrire(self.racine, 'js/i18n/aide/fr.js', AIDE_FR)
        ecrire(self.racine, 'js/modules/aide-ecrans-textes.js', MODULE_AIDE_LONGUE)

    def tearDown(self):
        self.dossier.cleanup()

    def test_le_depot_a_un_bloc_par_outil(self):
        blocs = ext.lire_dictionnaire(RACINE / 'js/i18n/aide/fr.js')
        self.assertEqual(sorted(blocs), ['acces', 'aide'])
        for section, prefixe in (('acces', 'aide.acces.'), ('aide', 'aide.ecran.')):
            langue, entrees = blocs[section]
            self.assertEqual(langue, 'fr')
            self.assertGreater(len(entrees), 80, section)
            self.assertEqual([cle for cle in entrees if not cle.startswith(prefixe)], [], section)
        # l'aide courte (aide.encart.*) reste dans js/i18n/fr.js, jamais dans le fichier de l'aide longue
        courte = ext.lire_dictionnaire(RACINE / 'js/i18n/fr.js')['aide'][1]
        self.assertTrue(courte and all(cle.startswith('aide.encart.') for cle in courte))

    def test_controle_lit_le_dictionnaire_de_l_aide(self):
        self.assertEqual(controler(self.racine, ['aide-longue']).signalements, [])
        ecrire(self.racine, 'js/modules/aide-ecrans-textes.js', MODULE_AIDE_LONGUE.replace(
            "    ancre: 'accueil',\n", "    ancre: 'accueil',\n    get texte() { return I18n.t('aide.ecran.accueil.texte'); },\n"
            "    essayez: 'Cliquez sur le compteur des demandes.',\n"))
        ecrire(self.racine, 'js/i18n/aide/fr.js', AIDE_FR.replace(
            "  'aide.ecran.accueil.titre'", "  'aide.ecran.oublie.titre': 'Oublié',\n  'aide.ecran.accueil.titre'"))
        signalements = sorted((s.genre, s.message) for s in controler(self.racine, ['aide-longue']).signalements)
        self.assertEqual([genre for genre, _ in signalements], ['dur', 'manquante', 'orpheline'])
        self.assertTrue(signalements[0][1].startswith('« Cliquez sur le compteur des demandes. »'))
        self.assertEqual(signalements[1][1], 'clé absente du dictionnaire : aide.ecran.accueil.texte')
        self.assertEqual(signalements[2][1], 'clé jamais employée : aide.ecran.oublie.titre')

    def test_extraction_complete_le_bloc_de_l_aide(self):
        ecrire(self.racine, 'js/modules/aide-ecrans-textes.js', MODULE_AIDE_LONGUE.replace(
            "const EssaiAideTextes", "function phraseDemo() {\n  return 'Vous êtes dans la démo.';\n}\nconst EssaiAideTextes"))
        res = ext.Extracteur(self.racine).extraire(ext.section_du_domaine('aide-longue'), ['js/modules/aide-ecrans-textes.js'],
                                                   dictionnaire=ext.dictionnaire_du_domaine('aide-longue'))
        self.assertEqual(len(res.unites), 1)
        texte = (self.racine / 'js/i18n/aide/fr.js').read_text(encoding='utf-8')
        self.assertEqual(texte.count("I18n.ajouter('fr', {"), 1)
        langue, entrees = ext.lire_dictionnaire(self.racine / 'js/i18n/aide/fr.js')['aide']
        self.assertEqual(entrees[res.unites[0].cle], 'Vous êtes dans la démo.')
        self.assertIn('aide.ecran.accueil.titre', entrees)
        self.assertEqual(controler(self.racine, ['aide-longue']).signalements, [])


if __name__ == '__main__':
    unittest.main()
