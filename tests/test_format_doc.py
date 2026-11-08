"""docs/FORMAT.md : le plan des versions à venir ne contient rien d'existant, et la doc cite ce qu'elle doit citer.

Sans navigateur : js/schema.js et serveur.py sont lus comme du texte."""
import os
import re
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(RACINE, 'docs', 'FORMAT.md')


def lire(*chemin):
    with open(os.path.join(RACINE, *chemin), encoding='utf-8') as fichier:
        return fichier.read()


def bloc_plan(texte):
    morceaux = re.search(r'<!-- plan:debut -->(.*?)<!-- plan:fin -->', texte, re.DOTALL)
    return morceaux.group(1) if morceaux else ''


def noms_du_plan(texte):
    """[(table, colonne ou None)] des lignes « - `table.colonne` (version) : rôle » du bloc."""
    noms = []
    for ligne in bloc_plan(texte).splitlines():
        trouve = re.match(r'^- `([a-z_]+)(?:\.([a-z_]+))?` \(\d\.\d\) : \S', ligne)
        if ligne.strip().startswith('-'):
            if not trouve:
                raise AssertionError('Ligne du plan mal formée : %r' % ligne)
            noms.append((trouve.group(1), trouve.group(2)))
    return noms


def champs_du_schema(source):
    """{table: {champs}} d'après js/schema.js (lu comme du texte)."""
    debut = source.index('const tables = {')
    fin = source.index('// Fonctions pures d\'accès')
    corps = source[debut:fin]
    resultat = {}
    for correspondance in re.finditer(r'^    ([a-z_]+): \{\n      fichier:', corps, re.MULTILINE):
        resultat.setdefault(correspondance.group(1), set())
    positions = sorted((c.start(), c.group(1)) for c in re.finditer(r'^    ([a-z_]+): \{\n      fichier:', corps, re.MULTILINE))
    for index, (position, nom) in enumerate(positions):
        limite = positions[index + 1][0] if index + 1 < len(positions) else len(corps)
        morceau = corps[position:limite]
        resultat[nom] = set(re.findall(r"(?:champ|choix|reference|codeDefaillance|booleen)\('([a-z_]+)'", morceau))
        resultat[nom].add('id')
    return resultat


def colonnes_du_serveur(source):
    debut = source.index('COLONNES_PAR_TABLE = {')
    fin = source.index('\n}\n', debut)
    corps = source[debut:fin]
    resultat = {}
    morceaux = re.split(r"^    '([a-z_]+)': ", corps, flags=re.MULTILINE)
    for index in range(1, len(morceaux), 2):
        resultat[morceaux[index]] = set(re.findall(r"'([a-z_]+)'", morceaux[index + 1]))
    return resultat


class TestFormatDoc(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.doc = lire('docs', 'FORMAT.md')
        cls.plan = noms_du_plan(cls.doc)
        cls.schema = champs_du_schema(lire('js', 'schema.js'))
        cls.serveur = colonnes_du_serveur(lire('serveur.py'))

    def test_les_lectures_trouvent_des_tables(self):
        self.assertGreaterEqual(len(self.schema), 24)
        self.assertEqual(set(self.schema), set(self.serveur))
        self.assertIn('astuce', self.schema['ordres_travail'])
        self.assertIn('astuce', self.serveur['ordres_travail'])

    def test_le_bloc_plan_n_est_pas_vide(self):
        self.assertTrue(bloc_plan(self.doc).strip())
        self.assertGreaterEqual(len(self.plan), 5)

    def test_rien_du_plan_n_existe_deja(self):
        for table, colonne in self.plan:
            for nom, existant in (('js/schema.js', self.schema), ('serveur.py', self.serveur)):
                if colonne is None:
                    self.assertNotIn(table, existant, 'table « %s » du plan déjà dans %s' % (table, nom))
                else:
                    self.assertNotIn(colonne, existant.get(table, set()),
                                     'colonne « %s.%s » du plan déjà dans %s' % (table, colonne, nom))

    def test_le_plan_ne_repete_aucun_nom(self):
        self.assertEqual(len(self.plan), len(set(self.plan)))

    def test_la_doc_cite_les_notions_obligatoires(self):
        for mot in ('version_schema', 'manifeste.json', 'avant-format-v', 'avant-import-zip', 'avant-mise-a-jour',
                    '30 jours', 'format_plus_recent'):
            self.assertIn(mot, self.doc, 'FORMAT.md ne cite pas « %s »' % mot)

    def test_les_liens_relatifs_existent(self):
        dossier = os.path.dirname(DOC)
        liens = re.findall(r'\]\(([^)\s]+)\)', self.doc)
        self.assertTrue(liens)
        for lien in liens:
            if re.match(r'^[a-z]+:', lien) or lien.startswith('#'):
                continue
            chemin = os.path.normpath(os.path.join(dossier, lien.split('#')[0]))
            self.assertTrue(os.path.exists(chemin), 'lien mort dans FORMAT.md : %s' % lien)


if __name__ == '__main__':
    unittest.main()
