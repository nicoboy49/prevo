"""Tests de outils/lancer_tests.py (T203) : chaque fichier de test dans son propre processus, avec un délai maximal.

Couvre, sur un faux dépôt créé dans un dossier temporaire (aucun navigateur, aucune donnée réelle) :
    lancement   chaque fichier tests/test_*.py est lancé à part, dans l'ordre de unittest discover, depuis la
                racine donnée par --racine (une autre copie que ce dépôt) ; les autres fichiers de tests/ ne sont
                pas lancés ; la sortie complète (sortie standard et erreurs, dans l'ordre) va dans le journal ;
    délai       un fichier bloqué (boucle à 100 % d'un cœur, avec un processus enfant) est arrêté vers le délai,
                pas avant ni bien après, avec son enfant ; il compte en dépassement et la suite continue ;
    bilan       une ligne de résumé par fichier, totaux relus des lignes « Ran N tests » et « OK (…) » /
                « FAILED (…) », liste des fichiers en échec ; code de sortie 0 seulement si tout est OK.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_lanceur_tests.py" -v
"""
import importlib.util
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
LANCEUR = RACINE / "outils" / "lancer_tests.py"
DELAI_MINUTES = "0.05"       # 3 secondes
DELAI_SECONDES = 3.0
MARGE_SECONDES = 6.0         # arrêt de l'arbre et démarrage de Python sur un poste chargé


def charger_lanceur():
    """outils/lancer_tests.py lu comme module (rien n'est lancé)."""
    specification = importlib.util.spec_from_file_location("lancer_tests_prevo", LANCEUR)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


lanceur = charger_lanceur()

# Le faux dépôt : un fichier qui passe (avec un échec attendu et une écriture sur la sortie standard), un qui échoue,
# un qui se bloque après avoir lancé un processus enfant, un sauté, et deux fichiers que le motif ne retient pas.
FAUX_TESTS = {
    "aide_commune.py": "VALEUR = 42\n",
    "notest_jamais_lance.py": 'raise SystemExit("FICHIER-HORS-MOTIF-LANCE")\n',
    "test_a_passe.py": '''import unittest

from aide_commune import VALEUR


class Passe(unittest.TestCase):
    def test_1_lit_le_module_voisin(self):
        self.assertEqual(VALEUR, 42)

    def test_2_ecrit_sur_la_sortie_standard(self):
        print("MARQUEUR-SORTIE-STANDARD", flush=True)

    def test_3_passe(self):
        pass

    @unittest.expectedFailure
    def test_4_echec_attendu(self):
        self.assertEqual(1, 2)
''',
    "test_b_echoue.py": '''import unittest


class Echoue(unittest.TestCase):
    def test_1_passe(self):
        pass

    def test_2_echoue(self):
        self.assertEqual(1, 2)

    def test_3_erreur(self):
        raise RuntimeError("erreur voulue")
''',
    "test_c_bloque.py": '''import subprocess
import sys
import time
import unittest
from pathlib import Path


class Bloque(unittest.TestCase):
    def test_1_avant(self):
        print("AVANT-LE-BLOCAGE", flush=True)

    def test_2_bloque(self):
        enfant = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        Path(__file__).with_name("enfant.pid").write_text(str(enfant.pid))
        fin = time.monotonic() + 120
        while time.monotonic() < fin:       # bloqué à 100 % d'un cœur, comme le 04/11
            pass

    def test_3_jamais_lance(self):
        pass
''',
    "test_d_saute.py": '''import unittest


@unittest.skip("sauté exprès")
class Saute(unittest.TestCase):
    def test_1(self):
        pass

    def test_2(self):
        pass
''',
}


def creer_faux_depot(dossier):
    (dossier / "tests").mkdir(parents=True)
    for nom, texte in FAUX_TESTS.items():
        (dossier / "tests" / nom).write_text(texte, encoding="utf-8")


def lancer(racine, *options, garde=120):
    """Lance le lanceur sur racine ; rend (code de sortie, sortie standard, erreurs, durée en secondes)."""
    debut = time.monotonic()
    processus = subprocess.Popen([sys.executable, "-X", "utf8", str(LANCEUR), "--racine", str(racine), *options],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        sortie, erreurs = processus.communicate(timeout=garde)
    except subprocess.TimeoutExpired:
        lanceur.arreter_arbre(processus)
        processus.communicate()
        raise AssertionError("le lanceur ne s'est pas arrêté en %d s" % garde)
    return (processus.returncode, normaliser(sortie), normaliser(erreurs), time.monotonic() - debut)


def normaliser(octets):
    return octets.decode("utf-8", errors="replace").replace("\r\n", "\n")


def processus_existe(pid):
    if os.name == "nt":
        liste = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"],
                               capture_output=True).stdout.decode("ascii", errors="replace")
        return '"%d"' % pid in liste
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:                                    # Linux : un processus zombie (pas encore retiré) est déjà arrêté
        return Path("/proc/%d/stat" % pid).read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def processus_disparu(pid, attente=5.0):
    """Vrai si le processus n'existe plus (ou plus après une courte attente : il peut finir d'être retiré)."""
    fin = time.monotonic() + attente
    while processus_existe(pid):
        if time.monotonic() > fin:
            return False
        time.sleep(0.1)
    return True


def tuer(pid):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def ligne_de(texte, debut):
    """La ligne du texte qui commence par debut (une seule attendue ; les lignes « … : lancement » sont écartées)."""
    lignes = [ligne for ligne in texte.splitlines() if ligne.startswith(debut) and not ligne.endswith(" : lancement")]
    if len(lignes) != 1:
        raise AssertionError("%d lignes commencent par « %s »" % (len(lignes), debut))
    return lignes[0]


class TestFauxDepotAvecBlocage(unittest.TestCase):
    """Un passage du lanceur sur le faux dépôt complet, avec journal : un fichier échoue, un autre se bloque."""

    @classmethod
    def setUpClass(cls):
        cls.dossier = Path(tempfile.mkdtemp(prefix="prevo_test_lanceur_"))
        creer_faux_depot(cls.dossier)
        cls.chemin_journal = cls.dossier / "resultats" / "journal.txt"
        cls.code, cls.ecran, cls.erreurs, cls.duree_totale = lancer(
            cls.dossier, "--delai-max", DELAI_MINUTES, "--journal", str(cls.chemin_journal))
        cls.journal = normaliser(cls.chemin_journal.read_bytes()) if cls.chemin_journal.is_file() else ""
        fichier_pid = cls.dossier / "tests" / "enfant.pid"
        cls.pid_enfant = int(fichier_pid.read_text()) if fichier_pid.is_file() else None

    @classmethod
    def tearDownClass(cls):
        if cls.pid_enfant and processus_existe(cls.pid_enfant):
            tuer(cls.pid_enfant)
        shutil.rmtree(cls.dossier, ignore_errors=True)

    def test_code_de_sortie_non_nul(self):
        self.assertEqual(self.code, 1, self.erreurs)

    def test_un_resume_par_fichier_dans_l_ordre_de_unittest(self):
        attendus = [
            ("[1/4] test_a_passe.py", "OK", "tests 4, échecs 0, erreurs 0, sautés 0, échecs attendus 1"),
            ("[2/4] test_b_echoue.py", "FAILED", "tests 3, échecs 1, erreurs 1, sautés 0, échecs attendus 0"),
            ("[4/4] test_d_saute.py", "OK", "tests 2, échecs 0, erreurs 0, sautés 2, échecs attendus 0"),
        ]
        for repere, statut, nombres in attendus:
            with self.subTest(fichier=repere):
                ligne = ligne_de(self.journal, "===== %s : %s en " % (repere, statut))
                self.assertRegex(ligne, r" en \d+,\d s — %s$" % re.escape(nombres))
        # Lancés l'un après l'autre, dans l'ordre trié, chacun entre sa ligne de lancement et son résumé
        positions = []
        for numero, nom in enumerate(["test_a_passe.py", "test_b_echoue.py", "test_c_bloque.py", "test_d_saute.py"], 1):
            positions.append(self.journal.index("===== [%d/4] %s : lancement" % (numero, nom)))
            positions.append(self.journal.index("===== [%d/4] %s : " % (numero, nom), positions[-1] + 1))
        self.assertEqual(positions, sorted(positions))
        self.assertLess(positions[4], self.journal.index("AVANT-LE-BLOCAGE"), "sortie du fichier bloqué à sa place")
        self.assertLess(self.journal.index("AVANT-LE-BLOCAGE"), positions[5])

    def test_fichier_bloque_arrete_vers_le_delai_et_compte_en_depassement(self):
        ligne = ligne_de(self.journal, "===== [3/4] test_c_bloque.py : ")
        trouve = re.fullmatch(r"===== \[3/4\] test_c_bloque\.py : DÉLAI en (\d+,\d) s — "
                              r"délai maximal dépassé \(0,05 min\), arbre de processus arrêté", ligne)
        self.assertTrue(trouve, ligne)
        duree = float(trouve.group(1).replace(",", "."))
        self.assertGreaterEqual(duree, DELAI_SECONDES, "arrêté avant le délai")
        self.assertLess(duree, DELAI_SECONDES + MARGE_SECONDES, "arrêté bien après le délai")
        self.assertGreaterEqual(self.duree_totale, DELAI_SECONDES)
        # La sortie d'avant le blocage est gardée ; le test suivant n'a jamais commencé
        self.assertIn("AVANT-LE-BLOCAGE", self.journal)
        self.assertNotIn("test_3_jamais_lance", self.journal)

    def test_enfant_du_fichier_bloque_arrete_avec_lui(self):
        self.assertIsNotNone(self.pid_enfant, "le fichier bloqué n'a pas lancé son enfant")
        self.assertTrue(processus_disparu(self.pid_enfant), "processus enfant encore vivant : %d" % self.pid_enfant)

    def test_totaux_et_fichiers_en_echec(self):
        self.assertRegex(ligne_de(self.journal, "===== Totaux : "),
                         r"^===== Totaux : 4 fichiers en \S+ s — tests 9, échecs 1, erreurs 1, sautés 2, "
                         r"échecs attendus 1, fichiers en dépassement 1$")
        self.assertEqual(ligne_de(self.journal, "===== Fichiers en échec"),
                         "===== Fichiers en échec (2) : test_b_echoue.py (FAILED), test_c_bloque.py (DÉLAI)")
        self.assertTrue(self.journal.rstrip("\n").endswith("test_c_bloque.py (DÉLAI)"))

    def test_sortie_complete_de_chaque_fichier_dans_le_journal(self):
        for motif in (r"test_1_lit_le_module_voisin \(.*\) \.\.\. ok$", r"test_4_echec_attendu \(.*\) \.\.\. expected failure$",
                      r"test_2_echoue \(.*\) \.\.\. FAIL$", r"test_3_erreur \(.*\) \.\.\. ERROR$",
                      r"^RuntimeError: erreur voulue$", r"^FAILED \(failures=1, errors=1\)$",
                      r"test_1 \(.*\) \.\.\. skipped 'sauté exprès'$", r"^Ran 4 tests in ", r"^Ran 2 tests in "):
            with self.subTest(motif=motif):
                self.assertRegex(self.journal, re.compile(motif, re.MULTILINE))
        # Sortie standard et erreurs mêlées dans l'ordre : le texte imprimé par le test s'inscrit entre « ... » et « ok »
        self.assertRegex(self.journal, r"test_2_ecrit_sur_la_sortie_standard \(.*\) \.\.\. MARQUEUR-SORTIE-STANDARD\nok\n")

    def test_seuls_les_fichiers_du_motif_sont_lances(self):
        self.assertNotIn("FICHIER-HORS-MOTIF-LANCE", self.journal)
        self.assertNotIn("aide_commune.py", self.journal)
        self.assertIn("===== lancer_tests : 4 fichiers tests/test_*.py de ", self.journal)

    def test_ecran_resumes_et_totaux_seulement(self):
        self.assertIn("===== [3/4] test_c_bloque.py : DÉLAI en ", self.ecran)
        self.assertIn("===== Totaux : 4 fichiers en ", self.ecran)
        self.assertIn("===== Fichiers en échec (2) : ", self.ecran)
        self.assertNotIn("AVANT-LE-BLOCAGE", self.ecran)
        self.assertNotIn(" : lancement", self.ecran)


class TestToutOk(unittest.TestCase):

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo_test_lanceur_"))
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        creer_faux_depot(self.dossier)

    def test_tout_ok_code_zero_et_sortie_sur_l_ecran_sans_journal(self):
        code, ecran, erreurs, _ = lancer(self.dossier, "--motif", "test_[ad]_*.py", "--delai-max", DELAI_MINUTES)
        self.assertEqual(code, 0, ecran + erreurs)
        self.assertRegex(ligne_de(ecran, "===== Totaux : "),
                         r"^===== Totaux : 2 fichiers en \S+ s — tests 6, échecs 0, erreurs 0, sautés 2, "
                         r"échecs attendus 1, fichiers en dépassement 0$")
        self.assertEqual(ligne_de(ecran, "===== Fichiers en échec"), "===== Fichiers en échec : aucun")
        self.assertRegex(ecran, re.compile(r"test_3_passe \(.*\) \.\.\. ok$", re.MULTILINE))
        self.assertNotIn("test_b_echoue", ecran)

    def test_options_fausses_code_deux(self):
        vide = self.dossier / "sans_tests"
        vide.mkdir()
        for options in ((), ("--delai-max", "0")):
            with self.subTest(options=options):
                racine = vide if not options else self.dossier
                code, _, erreurs, _ = lancer(racine, *options)
                self.assertEqual(code, 2)
                self.assertIn("--", erreurs)

    def test_aucun_fichier_code_un(self):
        code, ecran, _, _ = lancer(self.dossier, "--motif", "test_inexistant_*.py")
        self.assertEqual(code, 1)
        self.assertIn("===== Aucun fichier à lancer", ecran)


class TestLectureDuBilan(unittest.TestCase):

    def test_ok_avec_details(self):
        bilan = lanceur.lire_bilan("x ... ok\r\n\r\n------\r\nRan 5 tests in 1.234s\r\n\r\n"
                                   "OK (skipped=2, expected failures=1)\r\n")
        self.assertEqual(bilan, {"bilan": "OK", "comptes": {"tests": 5, "echecs": 0, "erreurs": 0, "sautes": 2,
                                                             "echecs_attendus": 1, "succes_inattendus": 0}})

    def test_echec_au_singulier_et_succes_inattendu(self):
        bilan = lanceur.lire_bilan("Ran 1 test in 0.001s\n\nFAILED (failures=1, errors=2, unexpected successes=3)\n")
        self.assertEqual(bilan["bilan"], "FAILED")
        self.assertEqual([bilan["comptes"][cle] for cle in ("tests", "echecs", "erreurs", "succes_inattendus")],
                         [1, 1, 2, 3])

    def test_le_dernier_bilan_fait_foi(self):
        texte = "Ran 99 tests in 0.1s\n\nOK\nimprimé par un test\nRan 3 tests in 0.2s\n\nFAILED (errors=1)\nfin\n"
        self.assertEqual(lanceur.lire_bilan(texte)["comptes"]["tests"], 3)
        self.assertEqual(lanceur.lire_bilan(texte)["bilan"], "FAILED")

    def test_aucun_test_ou_aucun_bilan(self):
        self.assertEqual(lanceur.lire_bilan("Ran 0 tests in 0.000s\n\nNO TESTS RAN\n")["bilan"], "NO TESTS RAN")
        self.assertIsNone(lanceur.lire_bilan("test_x (m.C.test_x) ... "))
        self.assertIsNone(lanceur.lire_bilan("Ran 2 tests in 0.1s\n\nTraceback (most recent call last):\n"))

    def test_fichiers_retenus_comme_unittest_discover(self):
        dossier = Path(tempfile.mkdtemp(prefix="prevo_test_lanceur_"))
        self.addCleanup(shutil.rmtree, dossier, ignore_errors=True)
        for nom in ("test_b.py", "test_a.py", "aide.py", "test_c.txt", "test-tiret.py", "test_1.py"):
            (dossier / nom).write_text("", encoding="utf-8")
        (dossier / "test_dossier.py").mkdir()
        self.assertEqual(lanceur.fichiers_de_test(dossier), ["test_1.py", "test_a.py", "test_b.py"])
        self.assertEqual(lanceur.fichiers_de_test(dossier, "test_b*.py"), ["test_b.py"])

    def test_commande_d_un_fichier(self):
        self.assertEqual(lanceur.commande_du_fichier("test_x.py"),
                         [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests", "-p", "test_x.py",
                          "-v"])


if __name__ == "__main__":
    unittest.main()
