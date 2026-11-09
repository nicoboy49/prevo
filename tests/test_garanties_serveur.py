"""L4 — droits du serveur sur les garanties, les contrats de prestataires et les réserves des contrôles (T453 ; CS173 ;
D126 prolongé ; QUESTIONS-L2-L6.md, L4-L6 Q6 ; ARCHITECTURE.md §22.5).

Décidé (pas une réponse provisoire, contrairement à habilitations, T445) : reserves_controle, garanties et
contrats_prestataires s'écrivent par le responsable seul ; montant_annuel est caché au technicien.

Ce qui est vérifié, en mode serveur avec comptes (vraies sessions sur une copie du jeu f4-v2.2.0, montants changés) :
    technicien     lit garanties et reserves_controle telles qu'elles sont ; reçoit contrats_prestataires sans
                   montant_annuel (en-tête compris, aucun montant dans les octets, autres colonnes intactes), X-Version
                   du fichier entier ; PUT (même forgé) et ajout refusés sur les trois tables (403, même corps que son
                   refus sur parametres), fichiers inchangés ;
    responsable    lit contrats_prestataires avec montant_annuel ; écrit les trois tables (PUT, ajout) ;
    demandeur      ne lit ni n'écrit aucune des trois (403), /api/versions ne les cite pas ; l'appareil enrôlé non
                   plus (identité simulée, verifier_role) ;
    colonne gardée si le PUT du technicien passait un jour, montant_annuel serait remis depuis le fichier
                   (controle_d_ecriture) et vidé dans un ajout (controle_d_ajout) ; rien pour le responsable ;
    sans comptes   rien ne change (montant lu, trois tables écrites).

Aucune donnée réelle : copie temporaire du jeu f4-v2.2.0 (tests/jeux_formats.py). Sans navigateur.
Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_garanties_serveur.py" -v
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
from jeux_formats import copier_jeu

SCRIPT = RACINE / "serveur.py"
JEU = "f4-v2.2.0"
AGENT = "tests-prevo/1.0"
BOM = bytes((0xEF, 0xBB, 0xBF))
TABLES = ("reserves_controle", "garanties", "contrats_prestataires")
# Montants posés dans la copie du jeu : chiffres qui n'apparaissent nulle part ailleurs dans le jeu.
MONTANTS = {"CTP-0001": "48123", "CTP-0002": "13579"}
# Ligne nouvelle de chaque table, pour les ajouts (colonnes du jeu, dans l'ordre de son en-tête).
LIGNES_NOUVELLES = {
    "reserves_controle": b"RES-00901;CTR-0001;2026-11-02;Garde-corps desserre;mineure;2026-12-02;0;;;\r\n",
    "garanties": b"GAR-0901;EQ-0001;FOU-0002;2026-11-01;2028-10-31;Pieces seules;;1\r\n",
    "contrats_prestataires": b"CTP-0901;FOU-0002;Essai T453;;;2026-11-01;2027-10-31;2;0;;24680;;1\r\n",
}
REFUS_TABLE = "Accès refusé : la table « {table} » ne se modifie que par le responsable."
REFUS_LECTURE = "Accès refusé : la table « {table} » n'est pas ouverte au {role}."


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_t453", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


# ---------------------------------------------------------------------------
# Données d'essai : CSV au format de Prévo
# ---------------------------------------------------------------------------

def lire_tableau(octets):
    """(en-tête, lignes) d'un CSV de Prévo (BOM, « ; »), valeurs telles qu'écrites."""
    lignes = [ligne for ligne in csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";") if ligne]
    return lignes[0], lignes[1:]


def cellule(texte):
    """Comme celluleCsv de js/donnees.js (§3.1)."""
    return '"' + texte.replace('"', '""') + '"' if re.search(r'[;"\r\n]|\A[ \t]|[ \t]\Z', texte) else texte


def ecrire_tableau(entete, lignes):
    texte = "".join(";".join(cellule(valeur) for valeur in ligne) + "\r\n" for ligne in [entete] + list(lignes))
    return BOM + texte.encode("utf-8")


def avec_cellule(octets, identifiant, colonne, valeur):
    """Octets du CSV où la ligne « identifiant » a « valeur » dans « colonne » (une seule ligne de cet id)."""
    entete, lignes = lire_tableau(octets)
    position = entete.index(colonne)
    trouvees = [ligne for ligne in lignes if ligne[0] == identifiant]
    if len(trouvees) != 1:
        raise AssertionError("%s : %d ligne(s) dans le jeu" % (identifiant, len(trouvees)))
    trouvees[0].extend([""] * (position + 1 - len(trouvees[0])))
    trouvees[0][position] = valeur
    return ecrire_tableau(entete, lignes)


def sans_colonne(octets, colonne):
    """(en-tête, lignes) du CSV sans cette colonne : ce que le technicien doit recevoir."""
    entete, lignes = lire_tableau(octets)
    position = entete.index(colonne)
    return ([nom for rang, nom in enumerate(entete) if rang != position],
            [[valeur for rang, valeur in enumerate(ligne) if rang != position] for ligne in lignes])


def premiere_ligne(octets):
    """Ligne d'en-tête d'un fichier (sans BOM ni fin de ligne) : début d'un corps d'ajout."""
    return octets[len(BOM):].split(b"\r\n", 1)[0] if octets.startswith(BOM) else octets.split(b"\r\n", 1)[0]


def preparer_source(racine):
    """Copie du jeu f4-v2.2.0, montants annuels des deux contrats remplacés par MONTANTS. Rend le dossier."""
    source = copier_jeu(JEU, racine / "source")
    chemin = source / "contrats_prestataires.csv"
    octets = chemin.read_bytes()
    for identifiant, montant in MONTANTS.items():
        octets = avec_cellule(octets, identifiant, "montant_annuel", montant)
    chemin.write_bytes(octets)
    for table in TABLES:
        if not (source / (table + ".csv")).is_file():
            raise AssertionError("le jeu %s n'a plus %s.csv" % (JEU, table))
    return source


# ---------------------------------------------------------------------------
# Requêtes sur un serveur réel
# ---------------------------------------------------------------------------

class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))


def requete(serveur_prevo, methode, chemin, corps=None, cookie=None, entetes=None):
    entetes = dict(entetes or {})
    entetes.setdefault("User-Agent", AGENT)
    if cookie:
        entetes["Cookie"] = cookie
    if methode in ("PUT", "POST"):
        entetes.setdefault("X-Prevo", "1")
        corps = b"" if corps is None else corps
    connexion = http.client.HTTPConnection("127.0.0.1", serveur_prevo.port, timeout=60)
    try:
        connexion.request(methode, chemin, body=corps, headers=entetes)
        reponse = connexion.getresponse()
        return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
    finally:
        connexion.close()


class CasServeur(unittest.TestCase):
    """Serveur réel (ServeurPrevo) sur une copie préparée du jeu ; sessions des trois rôles si COMPTES."""

    COMPTES = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.racine = Path(tempfile.mkdtemp(prefix="prevo-garanties-serveur-"))
        cls.addClassCleanup(shutil.rmtree, cls.racine, True)
        cls.serveur = commun.ServeurPrevo(source=preparer_source(cls.racine), comptes=cls.COMPTES)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.cookies = ({role: cls.serveur.session(role) for role in ("demandeur", "technicien", "responsable")}
                       if cls.COMPTES else {})

    def requete(self, role, methode, chemin, corps=None, entetes=None):
        return requete(self.serveur, methode, chemin, corps, self.cookies.get(role), entetes)

    def fichier(self, table):
        return (self.serveur.dossier / (table + ".csv")).read_bytes()

    def lire(self, role, table):
        lue = self.requete(role, "GET", "/api/csv/" + table)
        self.assertEqual(lue.statut, 200, lue.octets[:300])
        return lue

    def ecrire(self, role, table, octets, version=None):
        """PUT de la table entière, avec la version lue par ce rôle (ou celle donnée)."""
        version = version or self.lire(role, table).entetes["x-version"]
        return self.requete(role, "PUT", "/api/csv/" + table, octets, {"X-Version-Attendue": version})

    def ajouter(self, role, table):
        return self.requete(role, "POST", "/api/csv/%s/ajout" % table,
                            premiere_ligne(self.fichier(table)) + b"\r\n" + LIGNES_NOUVELLES[table])

    def assertRefus(self, reponse, message):
        self.assertEqual(reponse.statut, 403, reponse.octets[:300])
        self.assertEqual(reponse.json()["erreur"], message)


# ---------------------------------------------------------------------------
# Technicien : lit les trois tables (sans montant annuel), n'en écrit aucune ; demandeur : rien
# ---------------------------------------------------------------------------

class TestTechnicienEtDemandeur(CasServeur):

    def test_technicien_lit_garanties_et_reserves_telles_quelles(self):
        for table in ("garanties", "reserves_controle"):
            with self.subTest(table=table):
                self.assertEqual(self.lire("technicien", table).octets, self.fichier(table))

    def test_technicien_recoit_les_contrats_sans_montant_annuel(self):
        disque = self.fichier("contrats_prestataires")
        for montant in MONTANTS.values():
            self.assertIn(montant.encode("ascii"), disque)
        lue = self.lire("technicien", "contrats_prestataires")
        entete, lignes = lire_tableau(lue.octets)
        self.assertNotIn("montant_annuel", entete)
        for montant in MONTANTS.values():
            self.assertNotIn(montant.encode("ascii"), lue.octets)
        self.assertEqual((entete, lignes), sans_colonne(disque, "montant_annuel"))   # le reste intact, objet compris
        # X-Version du fichier entier (celle du responsable), pour qu'une écriture reste possible ailleurs.
        self.assertEqual(lue.entetes["x-version"], self.lire("responsable", "contrats_prestataires").entetes["x-version"])

    def test_technicien_refuse_a_l_ecriture_des_trois_tables_fichiers_inchanges(self):
        for table in TABLES:
            with self.subTest(table=table):
                avant = self.fichier(table)
                self.assertRefus(self.ecrire("technicien", table, avant), REFUS_TABLE.format(table=table))
                self.assertRefus(self.ajouter("technicien", table), REFUS_TABLE.format(table=table))
                self.assertEqual(self.fichier(table), avant)

    def test_technicien_un_montant_forge_ne_passe_pas(self):
        avant = self.fichier("contrats_prestataires")
        forge = avec_cellule(avant, "CTP-0001", "montant_annuel", "1")
        self.assertRefus(self.ecrire("technicien", "contrats_prestataires", forge),
                         REFUS_TABLE.format(table="contrats_prestataires"))
        self.assertEqual(self.fichier("contrats_prestataires"), avant)

    def test_meme_refus_que_sur_parametres(self):
        """Mêmes codes et corps que le refus existant (acces.table_du_responsable), au nom de table près."""
        attendu = self.ecrire("technicien", "parametres", self.fichier("parametres"))
        self.assertEqual(attendu.statut, 403, attendu.octets[:300])
        for table in TABLES:
            with self.subTest(table=table):
                corps = self.ecrire("technicien", table, self.fichier(table)).json()
                self.assertEqual(corps, json.loads(json.dumps(attendu.json(), ensure_ascii=False)
                                                   .replace("parametres", table)))

    def test_demandeur_ne_lit_ni_n_ecrit_aucune_des_trois(self):
        for table in TABLES:
            with self.subTest(table=table):
                avant = self.fichier(table)
                self.assertRefus(self.requete("demandeur", "GET", "/api/csv/" + table),
                                 REFUS_LECTURE.format(table=table, role="demandeur"))
                self.assertEqual(self.ecrire("demandeur", table, avant, version="0" * 16).statut, 403)
                self.assertEqual(self.ajouter("demandeur", table).statut, 403)
                self.assertEqual(self.fichier(table), avant)
        versions = self.requete("demandeur", "GET", "/api/versions")
        self.assertEqual(versions.statut, 200, versions.octets[:300])
        self.assertFalse(set(versions.json()["tables"]) & set(TABLES))


# ---------------------------------------------------------------------------
# Responsable : lit tout, écrit les trois tables
# ---------------------------------------------------------------------------

class TestResponsable(CasServeur):

    def test_lit_les_contrats_avec_montant_annuel(self):
        lue = self.lire("responsable", "contrats_prestataires")
        self.assertEqual(lue.octets, self.fichier("contrats_prestataires"))
        self.assertIn("montant_annuel", lire_tableau(lue.octets)[0])

    def test_ecrit_les_trois_tables(self):
        changements = {"reserves_controle": ("RES-00002", "gravite", "critique"),
                       "garanties": ("GAR-0002", "date_fin", "2026-10-14"),
                       "contrats_prestataires": ("CTP-0002", "montant_annuel", "14200")}
        for table, (identifiant, colonne, valeur) in changements.items():
            with self.subTest(table=table):
                modifie = avec_cellule(self.fichier(table), identifiant, colonne, valeur)
                reponse = self.ecrire("responsable", table, modifie)
                self.assertEqual(reponse.statut, 200, reponse.octets[:300])
                self.assertEqual(self.fichier(table), modifie)
                ajout = self.ajouter("responsable", table)
                self.assertEqual(ajout.statut, 200, ajout.octets[:300])
                self.assertTrue(self.fichier(table).endswith(LIGNES_NOUVELLES[table]))


# ---------------------------------------------------------------------------
# Appareil enrôlé (droits du demandeur) : identité simulée, règle du serveur appliquée directement
# ---------------------------------------------------------------------------

class TestAppareil(unittest.TestCase):

    APPAREIL = {"identifiant": "appareil:ap-0001", "role": "demandeur", "appareil": True}

    def test_aucune_des_trois_tables(self):
        config = serveur.Configuration(tempfile.mkdtemp(prefix="prevo-garanties-appareil-"), [])
        self.addCleanup(shutil.rmtree, config.dossier_donnees, True)
        for route in (("GET", "csv/<table>"), ("PUT", "csv/<table>"), ("POST", "csv/<table>/ajout")):
            for table in TABLES:
                with self.subTest(route=route, table=table):
                    with self.assertRaises(serveur.ErreurHttp) as refus:
                        serveur.verifier_role(config, self.APPAREIL, route, table)
                    self.assertEqual(refus.exception.statut, 403)


# ---------------------------------------------------------------------------
# Colonne gardée : si le refus d'écriture était levé, le montant resterait intouchable par le technicien
# ---------------------------------------------------------------------------

class TestMontantGardeALEcriture(unittest.TestCase):

    TECHNICIEN = {"identifiant": "julien.moreau", "role": "technicien", "appareil": False}
    RESPONSABLE = {"identifiant": "nicolas.briand", "role": "responsable", "appareil": False}

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp(prefix="prevo-garanties-colonne-"))
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.actuels = (preparer_source(self.racine) / "contrats_prestataires.csv").read_bytes()

    def test_put_montant_remis_depuis_le_fichier_ligne_nouvelle_sans_montant(self):
        controle = serveur.controle_d_ecriture(self.TECHNICIEN, "contrats_prestataires")
        self.assertIsNotNone(controle)
        entete, lignes = lire_tableau(avec_cellule(self.actuels, "CTP-0001", "montant_annuel", "1"))
        nouvelle = [""] * len(entete)
        nouvelle[0], nouvelle[entete.index("montant_annuel")] = "CTP-0902", "999"
        ecrits = lire_tableau(controle(ecrire_tableau(entete, lignes + [nouvelle]), self.actuels))
        position = ecrits[0].index("montant_annuel")
        self.assertEqual({ligne[0]: ligne[position] for ligne in ecrits[1]},
                         dict(MONTANTS, **{"CTP-0902": ""}))

    def test_ajout_montant_vide(self):
        controle = serveur.controle_d_ajout(self.TECHNICIEN, "contrats_prestataires")
        self.assertIsNotNone(controle)
        entete = premiere_ligne(self.actuels)
        ajoutees = controle(entete, LIGNES_NOUVELLES["contrats_prestataires"], self.actuels)
        cles = entete.decode("utf-8").split(";")
        rangee = ajoutees.decode("utf-8").rstrip("\r\n").split(";")
        self.assertEqual((rangee[0], rangee[cles.index("montant_annuel")]), ("CTP-0901", ""))

    def test_rien_pour_le_responsable(self):
        self.assertIsNone(serveur.controle_d_ecriture(self.RESPONSABLE, "contrats_prestataires"))
        self.assertIsNone(serveur.controle_d_ajout(self.RESPONSABLE, "contrats_prestataires"))


# ---------------------------------------------------------------------------
# Sans comptes : rien ne change
# ---------------------------------------------------------------------------

class TestSansComptes(CasServeur):

    COMPTES = False

    def test_rien_ne_change(self):
        self.assertEqual(self.lire(None, "contrats_prestataires").octets, self.fichier("contrats_prestataires"))
        for table in TABLES:
            with self.subTest(table=table):
                reponse = self.ecrire(None, table, self.fichier(table))
                self.assertEqual(reponse.statut, 200, reponse.octets[:300])


if __name__ == "__main__":
    unittest.main()
