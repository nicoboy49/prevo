"""Correctif 2.1.1 — rapports mensuels figés servis au seul responsable en mode serveur avec comptes (D126 : ni prix
ni coût pour le technicien ; ARCHITECTURE.md §22.5).

Défaut de la 2.1.0 (et de la 2.0.0) : le technicien lit parametres.csv, donc la ligne rapports_mensuels qui nomme les
rapports figés, et GET /api/documents/<nom> lui rendait le rapport (200) : coût de maintenance du mois et, au-delà
d'un seuil, coût sur 12 mois et valeur de remplacement. Le demandeur était déjà refusé (403).

Ce qui est vérifié (vraies sessions des trois comptes de tests/commun.py, serveur.py démarré sur une copie temporaire
de donnees/demo complétée de quatre documents et de la ligne rapports_mensuels) :
    avec comptes   un document cité par rapports_mensuels (noms séparés par des virgules, apostrophe de protection et
                   espaces de bord tolérés) : 200 au responsable, octet pour octet ; 403 au technicien (qui en lit
                   pourtant le nom) et au demandeur, même code et même corps que les refus existants
                   (« acces.document_ferme ») ; casse du nom ignorée ; liste relue à chaque requête ;
    appareil       verifier_role refuse le rapport à un téléphone enrôlé (droits du demandeur), le sert au
                   responsable ; rapports_figes lit la valeur comme Rapport.rapportsFiges ;
    autres         les autres documents restent servis au technicien (document cité nulle part, document qu'il
                   envoie puis relit) ; le demandeur reste refusé comme avant ;
    sans comptes   rien ne change : le rapport et les autres documents sont servis.

Sans navigateur, aucune sortie réseau.
Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_rapports_figes_serveur.py" -v
"""
import csv
import http.client
import importlib.util
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import commun
from commun import RACINE


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_rapports_figes", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()

BOM = b"\xef\xbb\xbf"
RAPPORT = "20261001-080000-rapport-mensuel-2026-09.html"           # 1er de rapports_mensuels (apostrophe devant)
REVISION = "20261002-090000-rapport-mensuel-2026-09-r2.html"       # 2e, après « , » (espace gardée par un tableur)
PAS_ENCORE = "20261101-080000-rapport-mensuel-2026-10.html"        # sur le disque, cité ensuite par le responsable
AUTRE = "20261020-101500-notice-libre.pdf"                         # cité nulle part : lisible du technicien
VALEUR = "'%s, %s" % (RAPPORT, REVISION)     # rapports_mensuels au départ (lecture tolérante : apostrophe, espace)
MONTANT = "98 765 €"


def refus(role):
    """Corps du 403 d'un document fermé à ce rôle : celui des refus de la 2.1.0 (message_refus)."""
    return {"erreur": "Accès refusé : ce document n'est pas ouvert au %s." % role,
            "erreur_code": "acces.document_ferme", "erreur_valeurs": {"role": role}}


def contenu(nom):
    return ("<!doctype html><title>Rapport mensuel (essai 2.1.1)</title><div class=\"tuile\" data-cle=\"cout\">"
            "<div class=\"lib\">Coût de maintenance du mois</div><div class=\"val\">" + MONTANT + "</div></div>"
            "<p>" + nom + "</p>\n").encode("utf-8")


def lire_tableau(octets):
    lignes = [ligne for ligne in csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";")
              if ligne]
    return lignes[0], lignes[1:]


def cellule(texte):
    return '"' + texte.replace('"', '""') + '"' if re.search(r'[;"\r\n]|\A[ \t]|[ \t]\Z', texte) else texte


def ecrire_tableau(entete, lignes):
    return BOM + "".join(";".join(cellule(valeur) for valeur in ligne) + "\r\n"
                         for ligne in [entete] + list(lignes)).encode("utf-8")


def avec_rapports(octets, valeur):
    """parametres.csv où rapports_mensuels vaut « valeur » (ligne ajoutée ou remplacée)."""
    entete, lignes = lire_tableau(octets)
    return ecrire_tableau(entete, [ligne for ligne in lignes if ligne[0] != "rapports_mensuels"]
                          + [["rapports_mensuels", valeur]])


class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))


def requete(serveur_prevo, methode, chemin, corps=None, cookie=None, entetes=None):
    entetes = dict(entetes or {})
    entetes.setdefault("User-Agent", "tests-prevo/1.0")
    if cookie:
        entetes["Cookie"] = cookie
    if methode in ("PUT", "POST"):
        entetes.setdefault("X-Prevo", "1")
        corps = b"" if corps is None else corps
    connexion = http.client.HTTPConnection("127.0.0.1", serveur_prevo.port, timeout=60)
    try:
        connexion.request(methode, chemin, body=corps, headers=entetes)
        reponse = connexion.getresponse()
        return Reponse(reponse.status, {cle.lower(): valeur for cle, valeur in reponse.getheaders()}, reponse.read())
    finally:
        connexion.close()


class CasRapportsFiges(unittest.TestCase):
    """Un serveur pour la classe, sur la démo plus quatre documents et rapports_mensuels = VALEUR."""

    COMPTES = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        racine = Path(tempfile.mkdtemp(prefix="prevo-rapports-figes-"))
        cls.addClassCleanup(shutil.rmtree, racine, True)
        source = racine / "donnees"
        shutil.copytree(commun.DOSSIER_DEMO, source)
        documents = source / "documents"
        documents.mkdir(exist_ok=True)
        for nom in (RAPPORT, REVISION, PAS_ENCORE, AUTRE):
            (documents / nom).write_bytes(contenu(nom))
        parametres = source / "parametres.csv"
        parametres.write_bytes(avec_rapports(parametres.read_bytes(), VALEUR))
        cls.serveur = commun.ServeurPrevo(source=source, comptes=cls.COMPTES)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.cookies = ({role: cls.serveur.session(role) for role in ("demandeur", "technicien", "responsable")}
                       if cls.COMPTES else {})

    def requete(self, role, methode, chemin, corps=None, entetes=None):
        return requete(self.serveur, methode, chemin, corps, self.cookies.get(role), entetes)

    def document(self, role, nom):
        return self.requete(role, "GET", "/api/documents/" + nom)

    def assertServi(self, reponse, nom):
        self.assertEqual((reponse.statut, reponse.octets), (200, contenu(nom)), reponse.octets[:300])

    def assertRefus(self, reponse, role):
        self.assertEqual(reponse.statut, 403, reponse.octets[:300])
        self.assertEqual(reponse.json(), refus(role))
        self.assertNotIn(MONTANT.encode("utf-8"), reponse.octets)


class TestAvecComptes(CasRapportsFiges):

    def test_rapport_servi_au_seul_responsable(self):
        for nom in (RAPPORT, REVISION):
            with self.subTest(nom=nom):
                self.assertServi(self.document("responsable", nom), nom)
                self.assertRefus(self.document("technicien", nom), "technicien")
                self.assertRefus(self.document("demandeur", nom), "demandeur")

    def test_refus_du_technicien_comme_les_refus_existants(self):
        """Même code et même corps que le refus d'un document au demandeur, déjà en place dans la 2.1.0."""
        existant = self.document("demandeur", AUTRE)
        nouveau = self.document("technicien", RAPPORT)
        self.assertEqual((existant.statut, nouveau.statut), (403, 403))
        self.assertEqual(existant.json(), refus("demandeur"))
        self.assertEqual(nouveau.json(), refus("technicien"))
        self.assertEqual(existant.entetes.get("content-type"), nouveau.entetes.get("content-type"))

    def test_le_technicien_lit_le_nom_pas_le_document(self):
        """Le nom reste dans parametres (table qu'il lit) ; le document lui est refusé."""
        lue = self.requete("technicien", "GET", "/api/csv/parametres")
        self.assertEqual(lue.statut, 200, lue.octets[:300])
        self.assertIn(REVISION.encode("ascii"), lue.octets)
        self.assertRefus(self.document("technicien", REVISION), "technicien")

    def test_casse_du_nom_ignoree(self):
        """Windows et macOS ne distinguent pas la casse : un autre nom ne doit pas ouvrir le même fichier."""
        for nom in (RAPPORT.upper(), REVISION.replace("rapport", "Rapport")):
            with self.subTest(nom=nom):
                self.assertRefus(self.document("technicien", nom), "technicien")

    def test_liste_relue_a_chaque_requete(self):
        self.assertServi(self.document("technicien", PAS_ENCORE), PAS_ENCORE)        # pas encore un rapport figé
        lue = self.requete("responsable", "GET", "/api/csv/parametres")
        valeur = ",".join((RAPPORT, REVISION, PAS_ENCORE))                           # comme Rapport.figer
        ecrit = self.requete("responsable", "PUT", "/api/csv/parametres", avec_rapports(lue.octets, valeur),
                             {"X-Version-Attendue": lue.entetes["x-version"]})
        self.assertEqual(ecrit.statut, 200, ecrit.octets[:300])
        self.assertRefus(self.document("technicien", PAS_ENCORE), "technicien")
        self.assertServi(self.document("responsable", PAS_ENCORE), PAS_ENCORE)

    def test_autres_documents_du_technicien_toujours_servis(self):
        self.assertServi(self.document("technicien", AUTRE), AUTRE)
        self.assertServi(self.document("responsable", AUTRE), AUTRE)
        self.assertRefus(self.document("demandeur", AUTRE), "demandeur")     # ni photo ni document d'équipement
        corps = b"%PDF-1.4 essai 2.1.1\n"
        envoi = self.requete("technicien", "PUT", "/api/documents/notice-essai-211.pdf", corps)
        self.assertEqual(envoi.statut, 201, envoi.octets[:300])
        relu = self.document("technicien", envoi.json()["nom"])
        self.assertEqual((relu.statut, relu.octets), (200, corps))

    def test_appareil_refuse_et_regle_lue_dans_parametres(self):
        """Un téléphone enrôlé a les droits du demandeur (D125) : refusé ; le responsable passe. La valeur est lue
        comme Rapport.rapportsFiges (apostrophe de protection, virgules, espaces de bord)."""
        config = serveur.Configuration(str(self.serveur.dossier), [])
        self.assertTrue({RAPPORT, REVISION} <= serveur.rapports_figes(config))
        route = ("GET", "documents/<nom>")
        appareil = {"identifiant": "appareil:ap-0001", "role": "demandeur", "appareil": True}
        with self.assertRaises(serveur.ErreurHttp) as refuse:
            serveur.verifier_role(config, appareil, route, RAPPORT)
        self.assertEqual(refuse.exception.statut, 403)
        responsable = {"identifiant": "nicolas.briand", "role": "responsable", "appareil": False}
        self.assertIsNone(serveur.verifier_role(config, responsable, route, RAPPORT))

    def test_sans_ligne_ni_fichier_aucun_rapport(self):
        dossier = Path(tempfile.mkdtemp(prefix="prevo-rapports-figes-vide-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        config = serveur.Configuration(str(dossier), [])
        self.assertEqual(serveur.rapports_figes(config), set())
        (dossier / "parametres.csv").write_bytes(BOM + b"cle;valeur\r\nentreprise_nom;Essai\r\n")
        self.assertEqual(serveur.rapports_figes(config), set())


class TestSansComptes(CasRapportsFiges):
    """Portée « ce PC », aucun compte : rien ne change."""

    COMPTES = False

    def test_rapport_et_autres_documents_servis(self):
        for nom in (RAPPORT, REVISION, AUTRE):
            with self.subTest(nom=nom):
                self.assertServi(self.document(None, nom), nom)


if __name__ == "__main__":
    unittest.main()
