"""Garde « fichier abîmé » côté serveur (version corrective 1.2.1 ; même principe que T197 et T200 de la 2.0).

Défaut de la 1.2.0 : un CSV abîmé (en-tête coupé, guillemet non fermé, valeur tapée à droite du tableau) était réécrit
par la première écriture venue (génération des OT préventifs à l'ouverture, formulaire, journal) : les valeurs que la
lecture n'avait pas comprises étaient perdues sans avertissement. Correction côté serveur : toutes les écritures de
donnees/<table>.csv passent par UNE fonction, ecrire_fichier_de_donnees, qui regarde le fichier en place avant
d'écrire :
  - réécriture (PUT /api/csv/<table>) : refusée si le fichier en place est abîmé (raisons_fichier_abime, même critère
    que entree.abime du navigateur : structure abîmée, ou valeurs au-delà de l'en-tête) ;
  - ajout en fin de fichier (POST /api/csv/<table>/ajout, le journal) : refusé si le fichier se termine au milieu d'un
    texte entre guillemets (finit_dans_un_guillemet_ouvert : les lignes ajoutées y seraient avalées) ;
  - restauration d'une sauvegarde : seule dérogation (c'est le remède) ;
  - refus : 409 {"erreur", "code": "fichier_abime", "table"} ; rien n'est écrit (ni la table, ni la sauvegarde du jour).

Sans navigateur. Jeux : copies de donnees/demo abîmées par programme (tests/jeux_abimes.py), dans un dossier
temporaire ; jamais de données réelles.

1. TestFonctions — finit_dans_un_guillemet_ouvert (les 14 exemples, partagés avec le navigateur, et l'automate octet
   par octet sur des suites tirées au hasard) ; raisons_fichier_abime (jeu de démo sain, cas abîmés, fichiers vides).
2. TestEcrituresInternes — serveur.py importé comme module, sur une copie : enregistrer_csv et ajouter_au_csv refusés
   sans rien écrire ; ajout permis à un fichier abîmé ailleurs mais à la fin propre ; restauration par-dessus un
   fichier abîmé.
3. TestRoutes — serveur réel (ServeurPrevo), requêtes HTTP directes : PUT et ajout refusés en 409 fichier_abime,
   fichier identique ; un conflit de version reste un conflit ; fichier sain : 200 comme avant ; restauration.
4. TestStructure — module ast sur serveur.py : aucune écriture d'un chemin venu de chemin_table(...) hors de la
   fonction commune ; le contrôle voit bien un contournement fabriqué.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_garde_abime_serveur.py" -v
"""
import ast
import hashlib
import importlib.util
import json
import random
import re
import shutil
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from commun import RACINE, ServeurPrevo
from jeux_abimes import (avec_guillemet_ouvert, avec_note_en_trop, copier_demo, entete_tronque, fichiers_de)


def charger_serveur():
    """serveur.py importé comme module (le serveur lancé par ServeurPrevo est un autre processus)."""
    specification = importlib.util.spec_from_file_location("serveur_prevo_garde_abime", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


SERVEUR = charger_serveur()

BOM = b"\xef\xbb\xbf"
CODE = "fichier_abime"
FONCTION_COMMUNE = "ecrire_fichier_de_donnees"

# Les 14 exemples (octets → finit dans un guillemet ouvert), partagés avec Donnees.csv.finitDansUnGuillemetOuvert
# (tests/test_garde_abime_navigateur.py) et identiques à ceux de T200 sur la 2.0.
EXEMPLES_GUILLEMET_OUVERT = [
    (b'', False),
    (b'id;action\r\n', False),
    (b'id;action\r\nJ-1;"ok"\r\n', False),
    (b'id;action\r\nJ-1;"coup', True),
    (b'id;action\r\nJ-1;"a""b', True),
    (b'id;action\r\nJ-1;"a""b"\r\n', False),
    (b'id;action\r\nJ-1;5" tuyau\r\n', False),
    (b'id;action\r\nJ-1;"multi\r\nligne', True),
    (b'id;action\r\nJ-1;"multi\r\nligne"\r\n', False),
    (b'\xef\xbb\xbf"id";"action"\r\n"J-1";"x', True),
    (b'id,action\r\nJ-1,"coup', True),
    (b'id;action\r\nJ-1;"fin"', False),
    (b'id;action\r\nJ-1;"a"b;"c', True),
    (b'id;action\r\nJ-1;a,"b\r\n', False),
]

DEBUT, DANS_LE_CHAMP, ENTRE_GUILLEMETS, GUILLEMET_VU = range(4)


def guillemet_ouvert_octet_par_octet(octets):
    """L'automate appliqué octet par octet : référence écrite ici, indépendante de serveur.py."""
    if octets.startswith(BOM):
        octets = octets[len(BOM):]
    separateur = b";"
    for ligne in re.split(rb"\r\n|\r|\n", octets):
        if ligne.strip():
            if b";" not in ligne and b"," in ligne:
                separateur = b","
            break
    fins = (separateur[0], 0x0D, 0x0A)
    etat = DEBUT
    for octet in octets:
        if etat == ENTRE_GUILLEMETS:
            etat = GUILLEMET_VU if octet == 0x22 else ENTRE_GUILLEMETS
        elif etat == DANS_LE_CHAMP:
            etat = DEBUT if octet in fins else DANS_LE_CHAMP
        else:                                                           # début de champ, ou guillemet vu
            etat = ENTRE_GUILLEMETS if octet == 0x22 else DEBUT if octet in fins else DANS_LE_CHAMP
    return etat == ENTRE_GUILLEMETS


def version_de(octets):
    return hashlib.sha256(octets).hexdigest()[:16]


def sans_bom(octets):
    return octets[len(BOM):] if octets.startswith(BOM) else octets


def requete(serveur, methode, chemin, corps=b"", entetes=None):
    """(statut, objet JSON ou octets) d'une requête au serveur de test ; X-Prevo pour PUT et POST."""
    entetes = dict(entetes or {})
    if methode in ("PUT", "POST"):
        entetes.setdefault("X-Prevo", "1")
    demande = urllib.request.Request(serveur.url + chemin, data=corps if methode in ("PUT", "POST") else None,
                                     method=methode, headers=entetes)
    try:
        with urllib.request.urlopen(demande, timeout=30) as reponse:
            statut, octets, type_contenu = reponse.status, reponse.read(), reponse.headers.get("Content-Type", "")
    except urllib.error.HTTPError as erreur:
        statut, octets, type_contenu = erreur.code, erreur.read(), erreur.headers.get("Content-Type", "")
    return statut, json.loads(octets.decode("utf-8")) if "json" in type_contenu else octets


class CasCopies(unittest.TestCase):

    def setUp(self):
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-garde-abime-"))
        self.addCleanup(shutil.rmtree, str(self.temporaire), True)
        self.numero = 0

    def demo(self):
        """Copie neuve du jeu de démo ; rend son dossier."""
        self.numero += 1
        return copier_demo(self.temporaire / ("copie-%d" % self.numero) / "donnees")

    def config(self, dossier):
        config = SERVEUR.Configuration(str(dossier), [])
        SERVEUR.creer_dossiers(config)
        return config

    def verifier_refus(self, erreur, table):
        """Le 409 de la garde : code fichier_abime, table, message clair (quoi, pourquoi, quoi faire)."""
        self.assertEqual(erreur.statut, 409, erreur.message)
        self.assertEqual(erreur.champs_supplementaires, {"code": CODE, "table": table})
        self.verifier_message(erreur.message, table)

    def verifier_reponse_de_refus(self, statut, reponse, table):
        self.assertEqual(statut, 409, reponse)
        self.assertEqual((reponse.get("code"), reponse.get("table")), (CODE, table), reponse)
        self.verifier_message(reponse["erreur"], table)

    def verifier_message(self, message, table):
        self.assertIn("Fichier abîmé", message)
        self.assertIn(table + ".csv", message)
        self.assertIn("pour ne rien perdre", message)
        self.assertIn("Restaurez la sauvegarde du jour (Paramètres › Sauvegardes", message)
        self.assertIn("https://github.com/nicoboy49/prevo/issues", message)


# ---------------------------------------------------------------------------
# 1. Fonctions
# ---------------------------------------------------------------------------

class TestFonctions(CasCopies):

    def test_finit_dans_un_guillemet_ouvert_les_14_exemples(self):
        self.assertEqual(len(EXEMPLES_GUILLEMET_OUVERT), 14)
        for octets, attendu in EXEMPLES_GUILLEMET_OUVERT:
            with self.subTest(octets=octets):
                self.assertIs(SERVEUR.finit_dans_un_guillemet_ouvert(octets), attendu)
                self.assertIs(guillemet_ouvert_octet_par_octet(octets), attendu)       # la référence aussi

    def test_finit_dans_un_guillemet_ouvert_comme_l_automate_octet_par_octet(self):
        tirage = random.Random(121)
        alphabet = [b'"', b';', b',', b'\r', b'\n', b'a', b' ']
        for _ in range(4000):
            octets = b"".join(tirage.choice(alphabet) for _ in range(tirage.randrange(0, 14)))
            if tirage.random() < 0.2:
                octets = BOM + octets
            with self.subTest(octets=octets):
                self.assertIs(SERVEUR.finit_dans_un_guillemet_ouvert(octets), guillemet_ouvert_octet_par_octet(octets))

    def test_finit_dans_un_guillemet_ouvert_sur_la_demo_et_un_journal_coupe(self):
        dossier = self.demo()
        for chemin in sorted(dossier.glob("*.csv")):
            with self.subTest(fichier=chemin.name):
                self.assertFalse(SERVEUR.finit_dans_un_guillemet_ouvert(chemin.read_bytes()))
        self.assertTrue(SERVEUR.finit_dans_un_guillemet_ouvert(avec_guillemet_ouvert((dossier / "journal.csv").read_bytes())))

    def test_raisons_fichier_abime(self):
        dossier = self.demo()
        for chemin in sorted(dossier.glob("*.csv")):
            with self.subTest(fichier=chemin.name):
                self.assertEqual(SERVEUR.raisons_fichier_abime(chemin.read_bytes()), [])
        ordres = (dossier / "ordres_travail.csv").read_bytes()
        abimes = {
            "en-tête coupé": entete_tronque(ordres),
            "valeur tapée à droite du tableau": avec_note_en_trop(ordres),
            "guillemet non fermé": ordres + 'OT-9999;"jamais fermé\r\n'.encode(),
            "texte collé à un guillemet fermant": ordres + b'OT-9998;"ferm\xc3\xa9"colle;x\r\n',
            "fin dans un guillemet ouvert": avec_guillemet_ouvert(ordres),
            "Windows-1252, valeur en trop": avec_note_en_trop(ordres).decode("utf-8").encode("cp1252", "replace"),
        }
        for nom, octets in abimes.items():
            with self.subTest(cas=nom):
                self.assertTrue(SERVEUR.raisons_fichier_abime(octets))
        self.assertIn("valeurs au-delà de l'en-tête", SERVEUR.raisons_fichier_abime(abimes["en-tête coupé"]))
        # Sans contenu, ou lignes courtes (valeurs manquantes à droite) : rien ne se perd à la réécriture.
        sains = {"absent": None, "vide": b"", "BOM seul": BOM, "blancs": BOM + b"  \r\n\r\n",
                 "lignes courtes": BOM + b"id;designation;repere\r\nEQ-1\r\nEQ-2;Tour\r\n",
                 "cellule vide en trop": BOM + b"id;designation\r\nEQ-1;Tour; \r\n"}
        for nom, octets in sains.items():
            with self.subTest(cas=nom):
                self.assertEqual(SERVEUR.raisons_fichier_abime(octets), [])


# ---------------------------------------------------------------------------
# 2. Écritures internes (module, sur une copie)
# ---------------------------------------------------------------------------

class TestEcrituresInternes(CasCopies):

    def test_enregistrer_csv_refuse_sans_rien_ecrire_sauvegarde_du_jour_comprise(self):
        dossier = self.demo()
        sain = (dossier / "ordres_travail.csv").read_bytes()
        abime = entete_tronque(sain)
        (dossier / "ordres_travail.csv").write_bytes(abime)
        config = self.config(dossier)
        avant = fichiers_de(dossier)
        with SERVEUR.VERROU_ECRITURE, self.assertRaises(SERVEUR.ErreurHttp) as refus:
            SERVEUR.enregistrer_csv(config, "ordres_travail", sain, version_de(abime))
        self.verifier_refus(refus.exception, "ordres_travail")
        self.assertEqual(fichiers_de(dossier), avant)

    def test_ajouter_au_csv_refuse_sur_un_journal_a_guillemet_ouvert(self):
        dossier = self.demo()
        journal = (dossier / "journal.csv").read_bytes()
        coupe = avec_guillemet_ouvert(journal)
        (dossier / "journal.csv").write_bytes(coupe)
        config = self.config(dossier)
        avant = fichiers_de(dossier)
        corps = sans_bom(journal).split(b"\r\n", 1)[0] + b"\r\nJ-10;2026-11-04 10:01;Poste test;;t;i;essai\r\n"
        with SERVEUR.VERROU_ECRITURE, self.assertRaises(SERVEUR.ErreurHttp) as refus:
            SERVEUR.ajouter_au_csv(config, "journal", corps)
        self.verifier_refus(refus.exception, "journal")
        self.assertIn("se termine au milieu d'un texte entre guillemets", refus.exception.message)
        self.assertEqual(fichiers_de(dossier), avant)

    def test_ajout_permis_a_un_fichier_abime_ailleurs_mais_a_la_fin_propre(self):
        """L'ajout ne réécrit rien de ce qui est en place : une valeur en trop sur une ligne n'est pas perdue."""
        dossier = self.demo()
        journal = (dossier / "journal.csv").read_bytes()
        abime = avec_note_en_trop(journal)
        (dossier / "journal.csv").write_bytes(abime)
        config = self.config(dossier)
        ligne = b"J-10;2026-11-04 10:01;Poste test;;t;i;essai\r\n"
        with SERVEUR.VERROU_ECRITURE:
            SERVEUR.ajouter_au_csv(config, "journal", sans_bom(journal).split(b"\r\n", 1)[0] + b"\r\n" + ligne)
        self.assertEqual((dossier / "journal.csv").read_bytes(), abime + ligne)

    def test_restaurer_par_dessus_un_fichier_abime(self):
        dossier = self.demo()
        config = self.config(dossier)
        sain = (dossier / "ordres_travail.csv").read_bytes()
        nom = SERVEUR.nouveau_nom_horodate(config)
        SERVEUR.copier_tables_dans_sauvegarde(config, nom)
        abime = entete_tronque(sain)
        (dossier / "ordres_travail.csv").write_bytes(abime)
        with SERVEUR.VERROU_ECRITURE:
            resultat = SERVEUR.restaurer(config, nom, ["ordres_travail"])
        self.assertEqual(resultat["restaurees"], ["ordres_travail"])
        self.assertEqual((dossier / "ordres_travail.csv").read_bytes(), sain)
        securite = dossier / "sauvegardes" / resultat["copie_securite"] / "ordres_travail.csv"
        self.assertEqual(securite.read_bytes(), abime)                # le fichier abîmé reste dans la copie de sécurité


# ---------------------------------------------------------------------------
# 3. Routes (serveur réel, requêtes HTTP directes)
# ---------------------------------------------------------------------------

class TestRoutes(CasCopies):

    def test_put_sur_un_fichier_abime_refuse_en_409_fichier_identique(self):
        source = self.demo()
        sain = (source / "ordres_travail.csv").read_bytes()
        abime = entete_tronque(sain)
        (source / "ordres_travail.csv").write_bytes(abime)
        with ServeurPrevo(source=source) as serveur:
            chemin = serveur.dossier / "ordres_travail.csv"
            avant = fichiers_de(serveur.dossier)
            statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", sain,
                                      {"X-Version-Attendue": version_de(abime)})
            self.verifier_reponse_de_refus(statut, reponse, "ordres_travail")
            self.assertEqual(fichiers_de(serveur.dossier), avant)  # ni la table, ni la sauvegarde du jour
            # Le contrôle de version passe d'abord : un conflit reste un conflit (le navigateur le réessaie).
            statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", sain,
                                      {"X-Version-Attendue": "0123456789abcdef"})
            self.assertEqual(statut, 409, reponse)
            self.assertEqual(reponse.get("version_actuelle"), version_de(abime))
            self.assertNotIn("code", reponse)
            self.assertEqual(chemin.read_bytes(), abime)
            # Une valeur tapée à droite du tableau : refusé de même.
            note = avec_note_en_trop(sain)
            chemin.write_bytes(note)
            statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", sain,
                                      {"X-Version-Attendue": version_de(note)})
            self.verifier_reponse_de_refus(statut, reponse, "ordres_travail")
            self.assertEqual(chemin.read_bytes(), note)
            # Fichier sain : 200 comme avant.
            chemin.write_bytes(sain)
            modifie = sain.replace(b"Entretien mensuel du compresseur CP-01", b"Entretien mensuel du compresseur CP-1")
            self.assertNotEqual(modifie, sain)
            statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", modifie,
                                      {"X-Version-Attendue": version_de(sain)})
            self.assertEqual(statut, 200, reponse)
            self.assertEqual((chemin.read_bytes(), reponse["version"]), (modifie, version_de(modifie)))

    def test_ajout_au_journal_a_guillemet_ouvert_refuse_en_409_journal_identique(self):
        source = self.demo()
        sain = (source / "journal.csv").read_bytes()
        coupe = avec_guillemet_ouvert(sain)
        (source / "journal.csv").write_bytes(coupe)
        entete = sans_bom(sain).split(b"\r\n", 1)[0]
        ligne = "J-20261104100100-EFGH;2026-11-04 10:01;Poste test;;ordres_travail;OT-2025-0001;essai\r\n".encode()
        with ServeurPrevo(source=source) as serveur:
            chemin = serveur.dossier / "journal.csv"
            avant = fichiers_de(serveur.dossier)
            statut, reponse = requete(serveur, "POST", "/api/csv/journal/ajout", entete + b"\r\n" + ligne)
            self.verifier_reponse_de_refus(statut, reponse, "journal")
            self.assertEqual(fichiers_de(serveur.dossier), avant)
            # Journal sain : 200 comme avant.
            chemin.write_bytes(sain)
            statut, reponse = requete(serveur, "POST", "/api/csv/journal/ajout", entete + b"\r\n" + ligne)
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(chemin.read_bytes(), sain + ligne)
            self.assertEqual(reponse["version"], version_de(sain + ligne))

    def test_restauration_d_une_sauvegarde_par_dessus_un_fichier_abime(self):
        source = self.demo()
        with ServeurPrevo(source=source) as serveur:
            chemin = serveur.dossier / "demandes.csv"
            sain = chemin.read_bytes()
            statut, reponse = requete(serveur, "POST", "/api/sauvegarde", b"")
            self.assertEqual(statut, 200, reponse)
            nom = reponse["sauvegarde"]
            abime = avec_note_en_trop(sain)
            chemin.write_bytes(abime)
            corps = json.dumps({"sauvegarde": nom, "tables": ["demandes"]}).encode("utf-8")
            statut, reponse = requete(serveur, "POST", "/api/restauration", corps,
                                      {"Content-Type": "application/json; charset=utf-8"})
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(reponse["restaurees"], ["demandes"])
            self.assertEqual(chemin.read_bytes(), sain)
            securite = serveur.dossier / "sauvegardes" / reponse["copie_securite"] / "demandes.csv"
            self.assertEqual(securite.read_bytes(), abime)


# ---------------------------------------------------------------------------
# 4. Structure de serveur.py (module ast)
# ---------------------------------------------------------------------------

# Écritures brutes d'un fichier (nom de la fonction appelée, quel que soit le module) ; open n'y compte qu'en écriture.
ECRITURES_BRUTES = {"remplacer_avec_essais", "replace", "rename", "copy", "copy2", "copyfile", "move", "write_bytes",
                    "write_text"}
FONCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


def nom_appele(appel):
    fonction = appel.func
    return fonction.id if isinstance(fonction, ast.Name) else fonction.attr if isinstance(fonction, ast.Attribute) \
        else None


def est_appel_de_chemin_table(noeud):
    return isinstance(noeud, ast.Call) and nom_appele(noeud) == "chemin_table"


def noeuds_propres(racines):
    """Les nœuds sous « racines », sans entrer dans les fonctions et classes imbriquées (comptées à part)."""
    a_voir = list(racines)
    while a_voir:
        noeud = a_voir.pop()
        if isinstance(noeud, FONCTIONS + (ast.ClassDef,)):
            continue
        yield noeud
        a_voir.extend(ast.iter_child_nodes(noeud))


def portees(arbre):
    """(nom, nœuds propres) du module (hors fonctions et classes) puis de chaque fonction ou méthode."""
    yield "<module>", list(noeuds_propres(arbre.body))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, FONCTIONS):
            yield noeud.name, list(noeuds_propres(ast.iter_child_nodes(noeud)))


def ecritures_de_chemin_table(source):
    """[(fonction, ligne, appel)] : appels qui écrivent un chemin venu de chemin_table(...) (directement, ou par une
    variable affectée depuis chemin_table dans la même fonction). ecrire_atomique : premier argument ; open : en
    écriture (« w », « a », « x » ou « + ») ; autres écritures brutes (ECRITURES_BRUTES) : n'importe quel argument."""
    trouvees = []
    for nom, noeuds in portees(ast.parse(source)):
        variables = set()
        for noeud in noeuds:
            if isinstance(noeud, ast.Assign) and est_appel_de_chemin_table(noeud.value):
                variables.update(cible.id for cible in noeud.targets if isinstance(cible, ast.Name))
            elif isinstance(noeud, (ast.AnnAssign, ast.NamedExpr)) and est_appel_de_chemin_table(noeud.value) \
                    and isinstance(noeud.target, ast.Name):
                variables.add(noeud.target.id)

        def vient_de_chemin_table(argument):
            return est_appel_de_chemin_table(argument) or (isinstance(argument, ast.Name) and argument.id in variables)

        for noeud in noeuds:
            if not isinstance(noeud, ast.Call):
                continue
            appele = nom_appele(noeud)
            arguments = list(noeud.args) + [mot.value for mot in noeud.keywords]
            if appele == "ecrire_atomique":
                visees = noeud.args[:1]
            elif appele == "open":
                mode = noeud.args[1] if len(noeud.args) > 1 else next(
                    (mot.value for mot in noeud.keywords if mot.arg == "mode"), None)
                ecrit = isinstance(mode, ast.Constant) and isinstance(mode.value, str) and set(mode.value) & set("wax+")
                visees = noeud.args[:1] if ecrit else []
            elif appele in ECRITURES_BRUTES:
                visees = arguments
            else:
                continue
            if any(vient_de_chemin_table(argument) for argument in visees):
                trouvees.append((nom, noeud.lineno, appele))
    return trouvees


EXEMPLE_DE_CONTOURNEMENTS = '''
def ecrire_fichier_de_donnees(config, table, octets):
    chemin = chemin_table(config, table)
    ecrire_atomique(chemin, octets)

def contourne(config, table, octets):
    ecrire_atomique(chemin_table(config, table), octets)

def contourne_par_variable(config, octets):
    chemin = chemin_table(config, 'journal')
    ecrire_atomique(chemin, octets)

def contourne_par_open(config, octets):
    with open(chemin_table(config, 'journal'), 'ab') as fichier:
        fichier.write(octets)

def contourne_par_replace(config, temporaire):
    cible = chemin_table(config, 'journal')
    os.replace(temporaire, cible)

def lit_seulement(config):
    with open(chemin_table(config, 'journal'), 'rb') as fichier:
        return fichier.read() + lire_octets(chemin_table(config, 'journal'))

def autre_fichier(config, octets):
    chemin = os.path.join(config.dossier_donnees, 'documents', 'photo.jpg')
    ecrire_atomique(chemin, octets)
'''


class TestStructure(unittest.TestCase):

    def test_le_controle_voit_un_contournement(self):
        trouvees = ecritures_de_chemin_table(EXEMPLE_DE_CONTOURNEMENTS)
        self.assertEqual(sorted(nom for nom, _, _ in trouvees),
                         ["contourne", "contourne_par_open", "contourne_par_replace", "contourne_par_variable",
                          FONCTION_COMMUNE])

    def test_toutes_les_ecritures_des_csv_de_donnees_passent_par_la_fonction_commune(self):
        source = (RACINE / "serveur.py").read_text(encoding="utf-8")
        trouvees = ecritures_de_chemin_table(source)
        self.assertEqual([(nom, appele) for nom, _, appele in trouvees], [(FONCTION_COMMUNE, "ecrire_atomique")],
                         "écritures de donnees/<table>.csv hors de %s (fonction, ligne, appel) : %r"
                         % (FONCTION_COMMUNE, trouvees))
        self.assertTrue(callable(getattr(SERVEUR, FONCTION_COMMUNE, None)))


if __name__ == "__main__":
    unittest.main()
