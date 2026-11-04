"""Lance la suite de tests fichier par fichier, chacun dans son propre processus, avec un délai maximal (T203).

Chaque fichier tests/test_*.py, dans l'ordre de « unittest discover », est lancé à part, depuis la racine du dépôt :
    <python courant> -X utf8 -m unittest discover -s tests -p <fichier> -v
Un fichier qui dépasse le délai maximal (15 minutes par défaut) est arrêté avec tout son arbre de processus
(navigateur, pilote Playwright, serveur…), compté en échec « délai maximal dépassé (N min) », et la suite continue
avec le fichier suivant : un blocage fait échouer un fichier au lieu de figer la suite (le 04/11, une suite complète
s'était figée sans aucun échec entre deux classes à navigateur de tests/test_recette_lot1.py).

Sortie (le journal, sinon la sortie standard) : la sortie complète de chaque fichier (sortie standard et erreurs
mêlées dans l'ordre, avec les lignes « ... ok », « ... FAIL », « ... ERROR » de unittest), encadrée par une ligne
« ===== [i/n] fichier : lancement » et une ligne de résumé (nom, durée, OK, FAILED ou DÉLAI, nombres) ; à la fin,
les totaux (relus des lignes « Ran N tests » et « OK (…) » / « FAILED (…) » de chaque fichier) et la liste des
fichiers en échec. Avec --journal, les lignes de résumé et les totaux s'affichent aussi à l'écran.
Code de sortie : 0 seulement si tous les fichiers sont OK ; 1 sinon ; 2 si les options sont fausses.

Bibliothèque standard seulement (Python 3.11+, Windows et Linux). Depuis la racine du projet :
    py outils/lancer_tests.py --journal tests/resultats/suite.txt
    py outils/lancer_tests.py [--racine COPIE_DU_DEPOT] [--motif "test_*.py"] [--delai-max MINUTES] [--journal CHEMIN]
--racine : le dépôt dont on lance les tests (défaut : celui qui contient ce fichier ; une autre copie convient, par
exemple une version 1.2.x). Ce lanceur est vérifié par tests/test_lanceur_tests.py.
"""
import argparse
import fnmatch
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
MOTIF_PAR_DEFAUT = "test_*.py"
DELAI_PAR_DEFAUT = 15        # minutes, par fichier de test
INTERVALLE = 0.25            # secondes entre deux relevés de la sortie du fichier en cours
PREFIXE = "====="            # début des lignes écrites par le lanceur (les autres viennent des tests)

OK, ECHEC, DELAI = "OK", "FAILED", "DÉLAI"

# Fichiers retenus par unittest discover : nom de module valide (unittest.loader.VALID_MODULE_NAME) et motif.
NOM_DE_MODULE = re.compile(r"[_a-z]\w*\.py$", re.IGNORECASE)
# Bilan imprimé par unittest à la fin d'un fichier : « Ran N tests in 1.234s », une ligne vide, puis
# « OK », « OK (skipped=2) », « FAILED (failures=1, errors=2) » ou, depuis Python 3.12, « NO TESTS RAN ».
LIGNE_RAN = re.compile(r"^Ran (\d+) tests? in \S+$")
LIGNE_BILAN = re.compile(r"^(OK|FAILED|NO TESTS RAN)(?: \((.*)\))?$")
COMPTES_UNITTEST = {"failures": "echecs", "errors": "erreurs", "skipped": "sautes",
                    "expected failures": "echecs_attendus", "unexpected successes": "succes_inattendus"}
LIBELLES = [("tests", "tests"), ("echecs", "échecs"), ("erreurs", "erreurs"), ("sautes", "sautés"),
            ("echecs_attendus", "échecs attendus"), ("succes_inattendus", "succès inattendus")]


def fichiers_de_test(dossier_tests, motif=MOTIF_PAR_DEFAUT):
    """Noms des fichiers de dossier_tests que « unittest discover -p motif » retient, dans son ordre (trié)."""
    return [nom for nom in sorted(os.listdir(dossier_tests))
            if os.path.isfile(os.path.join(dossier_tests, nom)) and NOM_DE_MODULE.match(nom)
            and fnmatch.fnmatch(nom, motif)]


def commande_du_fichier(nom):
    """Commande qui lance un seul fichier de test, depuis la racine du dépôt."""
    return [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests", "-p", nom, "-v"]


def comptes_vides():
    return dict.fromkeys((cle for cle, _ in LIBELLES), 0)


def lire_bilan(texte):
    """Bilan unittest d'une sortie : {"bilan": "OK" | "FAILED" | "NO TESTS RAN", "comptes": {...}}, ou None.

    Le dernier « Ran N tests » fait foi (un test peut imprimer un bilan d'essai avant) ; le bilan est la première
    ligne non vide qui le suit."""
    lignes = [ligne.strip() for ligne in texte.splitlines()]
    dernier = None
    for index, ligne in enumerate(lignes):
        trouve = LIGNE_RAN.match(ligne)
        if trouve:
            dernier = (index, int(trouve.group(1)))
    if dernier is None:
        return None
    index, nombre = dernier
    bilan = LIGNE_BILAN.match(next((ligne for ligne in lignes[index + 1:] if ligne), ""))
    if not bilan:
        return None
    comptes = comptes_vides()
    comptes["tests"] = nombre
    for morceau in (bilan.group(2) or "").split(","):
        cle, _, valeur = morceau.strip().partition("=")
        if cle in COMPTES_UNITTEST and valeur.isdigit():
            comptes[COMPTES_UNITTEST[cle]] = int(valeur)
    return {"bilan": bilan.group(1), "comptes": comptes}


def texte_comptes(comptes):
    """« tests 34, échecs 0, erreurs 0, sautés 2, échecs attendus 0 » (succès inattendus seulement s'il y en a)."""
    return ", ".join("%s %d" % (libelle, comptes[cle]) for cle, libelle in LIBELLES
                     if cle != "succes_inattendus" or comptes[cle])


def texte_duree(secondes):
    if secondes < 60:
        return ("%.1f s" % secondes).replace(".", ",")
    minutes, secondes = divmod(int(round(secondes)), 60)
    if minutes < 60:
        return "%d min %02d s" % (minutes, secondes)
    heures, minutes = divmod(minutes, 60)
    return "%d h %02d min %02d s" % (heures, minutes, secondes)


def texte_minutes(minutes):
    return ("%g" % minutes).replace(".", ",")


def arreter_arbre(processus):
    """Arrête le processus et tous ses descendants (Windows : taskkill /T /F ; ailleurs : son groupe de processus)."""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(processus.pid)], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(processus.pid, signal.SIGKILL)   # lancé avec start_new_session : groupe = son PID
        except (ProcessLookupError, PermissionError):
            pass
    try:
        processus.wait(timeout=30)
    except subprocess.TimeoutExpired:
        processus.kill()
        try:
            processus.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass


class Sortie:
    """Le journal (fichier) ou, sans journal, la sortie standard ; tout est écrit en UTF-8 et vidé aussitôt."""

    def __init__(self, journal=None):
        self.ecran = sys.stdout.buffer
        self.fichier = None
        if journal:
            Path(journal).parent.mkdir(parents=True, exist_ok=True)
            self.fichier = open(journal, "wb")

    def octets(self, donnees):
        flux = self.fichier or self.ecran
        flux.write(donnees)
        flux.flush()

    def ligne(self, texte, ecran_aussi=False):
        donnees = (texte + os.linesep).encode("utf-8")
        self.octets(donnees)
        if ecran_aussi and self.fichier:
            self.ecran.write(donnees)
            self.ecran.flush()

    def fermer(self):
        if self.fichier:
            self.fichier.close()


class Releve:
    """Recopie dans la sortie, ligne à ligne, ce qu'un fichier de test écrit dans son fichier temporaire, et le garde."""

    def __init__(self, lecture, sortie):
        self.lecture, self.sortie = lecture, sortie
        self.tout = bytearray()
        self.reste = b""

    def relever(self):
        nouveau = self.lecture.read()
        if not nouveau:
            return
        self.tout += nouveau
        donnees = self.reste + nouveau
        coupure = donnees.rfind(b"\n") + 1
        if coupure:
            self.sortie.octets(donnees[:coupure])
        self.reste = donnees[coupure:]

    def terminer(self):
        """Dernier relevé ; la ligne inachevée éventuelle (test en cours à l'arrêt) est fermée. Rend tout le texte."""
        self.relever()
        if self.reste:
            self.sortie.octets(self.reste + os.linesep.encode("ascii"))
            self.reste = b""
        return self.tout.decode("utf-8", errors="replace")


class ResultatFichier:
    def __init__(self, nom, statut, duree, comptes=None, detail=""):
        self.nom, self.statut, self.duree, self.comptes, self.detail = nom, statut, duree, comptes, detail

    def resume(self):
        """« OK en 12,3 s — tests 34, échecs 0, … », « DÉLAI en 900,4 s — délai maximal dépassé (15 min), … »."""
        morceaux = ([texte_comptes(self.comptes)] if self.comptes else []) + ([self.detail] if self.detail else [])
        return "%s en %s" % (self.statut, texte_duree(self.duree)) + (" — " + " ; ".join(morceaux) if morceaux else "")


def lancer_fichier(racine, nom, minutes, sortie, dossier_temporaire):
    """Lance un fichier de test dans son propre processus ; à l'expiration du délai, arrête tout son arbre.

    La sortie du processus va dans un fichier temporaire relu toutes les INTERVALLE secondes, pas dans un tube :
    un processus petit-enfant resté vivant qui garderait le tube ouvert ne peut pas figer le lanceur."""
    chemin = Path(dossier_temporaire) / (nom + ".sortie")
    with open(chemin, "wb") as ecriture:
        debut = time.monotonic()
        processus = subprocess.Popen(commande_du_fichier(nom), cwd=str(racine), stdin=subprocess.DEVNULL,
                                     stdout=ecriture, stderr=subprocess.STDOUT, start_new_session=(os.name != "nt"))
    limite = debut + minutes * 60
    depasse = False
    try:
        with open(chemin, "rb") as lecture:
            releve = Releve(lecture, sortie)
            while True:
                releve.relever()
                reste = limite - time.monotonic()
                if reste <= 0:
                    if processus.poll() is None:
                        depasse = True
                        arreter_arbre(processus)
                    break
                try:
                    processus.wait(timeout=min(INTERVALLE, reste))
                    break
                except subprocess.TimeoutExpired:
                    pass
            texte = releve.terminer()
    finally:
        if processus.poll() is None:    # interruption (Ctrl+C) ou erreur du lanceur : rien ne reste derrière
            arreter_arbre(processus)
    try:
        chemin.unlink()
    except OSError:
        pass                            # encore ouvert par un processus resté vivant : le dossier temporaire suffira
    duree = time.monotonic() - debut
    if depasse:
        return ResultatFichier(nom, DELAI, duree,
                               detail="délai maximal dépassé (%s min), arbre de processus arrêté" % texte_minutes(minutes))
    bilan, code = lire_bilan(texte), processus.returncode
    if bilan is None:
        return ResultatFichier(nom, ECHEC, duree, detail="bilan de unittest introuvable (code de sortie %s)" % code)
    if bilan["bilan"] == "OK" and code == 0:
        return ResultatFichier(nom, OK, duree, bilan["comptes"])
    detail = {"NO TESTS RAN": "aucun test lancé"}.get(bilan["bilan"], "")
    if bilan["bilan"] == "OK":
        detail = "code de sortie %s" % code
    return ResultatFichier(nom, ECHEC, duree, bilan["comptes"], detail)


def ecrire_totaux(sortie, resultats, duree):
    totaux = comptes_vides()
    for resultat in resultats:
        for cle, valeur in (resultat.comptes or {}).items():
            totaux[cle] += valeur
    depassements = sum(resultat.statut == DELAI for resultat in resultats)
    sortie.ligne("%s Totaux : %d fichiers en %s — %s, fichiers en dépassement %d"
                 % (PREFIXE, len(resultats), texte_duree(duree), texte_comptes(totaux), depassements), True)
    en_echec = [resultat for resultat in resultats if resultat.statut != OK]
    if en_echec:
        sortie.ligne("%s Fichiers en échec (%d) : %s" % (PREFIXE, len(en_echec), ", ".join(
            "%s (%s)" % (resultat.nom, resultat.statut) for resultat in en_echec)), True)
    else:
        sortie.ligne("%s Fichiers en échec : aucun" % PREFIXE, True)
    return not en_echec


def main(arguments=None):
    parseur = argparse.ArgumentParser(
        description="Lance chaque fichier de test dans son propre processus, avec un délai maximal par fichier.")
    parseur.add_argument("--racine", default=str(RACINE),
                         help="dépôt dont on lance les tests (défaut : celui qui contient ce lanceur)")
    parseur.add_argument("--motif", default=MOTIF_PAR_DEFAUT,
                         help="motif des fichiers de tests/ à lancer (défaut : test_*.py)")
    parseur.add_argument("--delai-max", type=float, default=DELAI_PAR_DEFAUT, metavar="MINUTES",
                         help="délai maximal par fichier, en minutes (défaut : %d)" % DELAI_PAR_DEFAUT)
    parseur.add_argument("--journal", metavar="CHEMIN", help="fichier où écrire toute la sortie (défaut : l'écran)")
    options = parseur.parse_args(arguments)
    if not options.delai_max > 0:
        parseur.error("--delai-max : un nombre de minutes plus grand que zéro")
    racine = Path(options.racine).resolve()
    if not (racine / "tests").is_dir():
        parseur.error("--racine : aucun dossier tests/ dans %s" % racine)
    noms = fichiers_de_test(racine / "tests", options.motif)
    sortie = Sortie(options.journal)
    resultats = []
    debut = time.monotonic()
    try:
        sortie.ligne("%s lancer_tests : %d fichiers tests/%s de %s, délai maximal %s min par fichier"
                     % (PREFIXE, len(noms), options.motif, racine, texte_minutes(options.delai_max)), True)
        if not noms:
            sortie.ligne("%s Aucun fichier à lancer" % PREFIXE, True)
            return 1
        with tempfile.TemporaryDirectory(prefix="prevo_lancer_tests_", ignore_cleanup_errors=True) as temporaire:
            for numero, nom in enumerate(noms, 1):
                repere = "%s [%d/%d] %s" % (PREFIXE, numero, len(noms), nom)
                sortie.ligne(repere + " : lancement")
                resultat = lancer_fichier(racine, nom, options.delai_max, sortie, temporaire)
                resultats.append(resultat)
                sortie.ligne(repere + " : " + resultat.resume(), True)
        return 0 if ecrire_totaux(sortie, resultats, time.monotonic() - debut) else 1
    except KeyboardInterrupt:
        sortie.ligne("%s Interrompu (Ctrl+C) après %d fichiers : le fichier en cours et ses processus sont arrêtés"
                     % (PREFIXE, len(resultats)), True)
        return 130
    finally:
        sortie.fermer()


if __name__ == "__main__":
    sys.exit(main())
