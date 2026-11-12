"""Version d'une table servie à un rôle qui n'en reçoit pas toutes les colonnes (T506 ; relecture R4, D126 ;
ARCHITECTURE.md §22.5).

Le défaut : X-Version était l'empreinte SHA-256 (16 caractères) du fichier ENTIER, colonnes cachées comprises. Le
technicien, qui reçoit toutes les autres cellules et connaît le format d'écriture (§3.1), recomposait le fichier avec
un prix ou un taux candidat et comparait son empreinte à la version reçue : la bonne valeur se reconnaissait hors
ligne. La même empreinte envoyée dans X-Version-Attendue faisait aussi passer un PUT (200 pour la bonne, 409 sinon).

Ce qui est vérifié, en mode serveur avec comptes (vraies sessions, copie du jeu f3-v2.0.0, articles réduit à une
ligne dont le technicien ne reçoit pas prix_unitaire) :
    essai du relecteur  aucune version vue du technicien (GET, /api/versions, réponse d'un PUT, d'un ajout, d'un 409)
                        n'est l'empreinte du fichier recomposé, ni avec le bon prix ni avec un mauvais ;
    essai en ligne      X-Version-Attendue = empreinte du fichier recomposé : 409 au même corps pour tous les
                        candidats ; un prix candidat envoyé dans la colonne cachée : même réponse pour tous, fichier
                        inchangé ;
    témoins du 409      technicien et responsable se voient toujours en conflit, dans les deux sens ; la version
                        rendue par un 409 ou un 200 est celle que le rôle lira ensuite ;
    le reste inchangé   responsable, tables sans colonne cachée, serveur sans comptes : la version reste l'empreinte
                        du fichier ; la clé du serveur (donnees/acces/.cle-versions) est gardée d'une requête à l'autre.

Aucune donnée réelle : copie temporaire du jeu f3-v2.0.0 (tests/jeux_formats.py). Sans navigateur.
Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_version_colonnes_cachees.py" -v
"""
import csv
import hashlib
import http.client
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import commun
from jeux_formats import copier_jeu

JEU = "f3-v2.0.0"
AGENT = "tests-prevo/1.0"
BOM = bytes((0xEF, 0xBB, 0xBF))
ENTETE = ["id", "reference", "designation", "fabricant", "ref_fabricant", "emplacement", "unite", "stock",
          "stock_securite", "point_commande", "qte_commande", "delai_jours", "prix_unitaire", "fournisseur_id",
          "critique", "actif"]
PRIX = "4.8"                                                # la valeur cachée au technicien
ARTICLE = ["ART-0001", "ROU-001", "Roulement 6204", "Rouloran", "6204-2RS", "A1-01", "u", "9", "4", "8", "20", "3",
           PRIX, "", "0", "1"]
CANDIDATS = ("4.5", PRIX, "5", "12.25")                     # le bon prix parmi de mauvais
POSITION_PRIX = ENTETE.index("prix_unitaire")
MOTIF_VERSION = re.compile(r"[0-9a-f]{16}")


def empreinte(octets):
    """La version d'un fichier telle que tout le monde sait la calculer (SHA-256, 16 caractères)."""
    return hashlib.sha256(octets).hexdigest()[:16]


def lire_tableau(octets):
    lignes = [ligne for ligne in csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";") if ligne]
    return lignes[0], lignes[1:]


def ecrire_tableau(entete, lignes):
    """Format d'écriture de Prévo (§3.1) pour des valeurs sans « ; », guillemet ni espace de bord."""
    return BOM + "".join(";".join(ligne) + "\r\n" for ligne in [entete] + list(lignes)).encode("utf-8")


def recomposer(octets_recus, prix):
    """Ce que fait l'attaquant : le fichier entier d'après ce que le technicien a reçu, avec un prix candidat."""
    entete, lignes = lire_tableau(octets_recus)
    if "prix_unitaire" in entete:
        raise AssertionError("le technicien a reçu prix_unitaire : l'essai n'a plus de sens")
    return ecrire_tableau(ENTETE, [ligne[:POSITION_PRIX] + [prix] + ligne[POSITION_PRIX:] for ligne in lignes])


def avec_prix(lignes, prix):
    """PUT du technicien qui tente un prix : en-tête entier, prix candidat sur chaque ligne."""
    return ecrire_tableau(ENTETE, [ligne[:POSITION_PRIX] + [prix] + ligne[POSITION_PRIX + 1:] for ligne in lignes])


def preparer_source(racine):
    source = copier_jeu(JEU, racine / "source")
    (source / "articles.csv").write_bytes(ecrire_tableau(ENTETE, [ARTICLE]))
    return source


class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))


def requete(serveur, methode, chemin, corps=None, cookie=None, entetes=None):
    entetes = dict(entetes or {})
    entetes.setdefault("User-Agent", AGENT)
    if cookie:
        entetes["Cookie"] = cookie
    if methode in ("PUT", "POST"):
        entetes.setdefault("X-Prevo", "1")
        corps = b"" if corps is None else corps
    connexion = http.client.HTTPConnection("127.0.0.1", serveur.port, timeout=60)
    try:
        connexion.request(methode, chemin, body=corps, headers=entetes)
        reponse = connexion.getresponse()
        return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
    finally:
        connexion.close()


class CasServeur(unittest.TestCase):
    """Un serveur réel par test (les tests écrivent articles.csv) ; sessions des trois rôles si COMPTES."""

    COMPTES = True

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp(prefix="prevo-version-cachee-"))
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.serveur = commun.ServeurPrevo(source=preparer_source(self.racine), comptes=self.COMPTES)
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)
        self.cookies = ({role: self.serveur.session(role) for role in ("demandeur", "technicien", "responsable")}
                        if self.COMPTES else {})

    def requete(self, role, methode, chemin, corps=None, entetes=None):
        return requete(self.serveur, methode, chemin, corps, self.cookies.get(role), entetes)

    def fichier(self, table="articles"):
        return (self.serveur.dossier / (table + ".csv")).read_bytes()

    def lire(self, role, table="articles"):
        reponse = self.requete(role, "GET", "/api/csv/" + table)
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        return reponse

    def version(self, role, table="articles"):
        return self.lire(role, table).entetes["x-version"]

    def version_listee(self, role, table="articles"):
        reponse = self.requete(role, "GET", "/api/versions")
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        return reponse.json()["tables"][table]["version"]

    def put(self, role, octets, attendue, table="articles"):
        return self.requete(role, "PUT", "/api/csv/" + table, octets, {"X-Version-Attendue": attendue})


class TestEssaiDuRelecteur(CasServeur):
    """Le technicien ne distingue plus le bon prix d'un mauvais, ni hors ligne ni par ses écritures."""

    def empreintes_candidates(self):
        """{prix candidat : empreinte du fichier recomposé} ; celle du bon prix est bien celle du fichier."""
        recu = self.lire("technicien").octets
        candidates = {prix: empreinte(recomposer(recu, prix)) for prix in CANDIDATS}
        self.assertEqual(candidates[PRIX], empreinte(self.fichier()), "l'essai ne recompose plus le fichier")
        return candidates

    def test_aucune_version_lue_n_est_l_empreinte_d_un_fichier_recompose(self):
        candidates = self.empreintes_candidates()
        vues = {"GET": self.version("technicien"), "versions": self.version_listee("technicien")}
        for origine, version in vues.items():
            self.assertRegex(version, MOTIF_VERSION, origine)
            for prix, calculee in candidates.items():
                self.assertNotEqual(version, calculee, "%s : la version confirme le prix %s" % (origine, prix))
        self.assertEqual(vues["GET"], vues["versions"])

    def test_empreinte_candidate_en_version_attendue_409_identique(self):
        candidates = self.empreintes_candidates()
        avant = self.fichier()
        _, lignes = lire_tableau(avant)
        reponses = {}
        for prix, calculee in candidates.items():
            reponse = self.put("technicien", avec_prix(lignes, ""), calculee)
            reponses[prix] = (reponse.statut, reponse.octets)
        self.assertEqual({statut for statut, _ in reponses.values()}, {409}, reponses)
        self.assertEqual(len({corps for _, corps in reponses.values()}), 1, reponses)
        rendue = json.loads(reponses[PRIX][1].decode("utf-8"))["version_actuelle"]
        self.assertNotIn(rendue, candidates.values())
        self.assertEqual(rendue, self.version("technicien"))
        self.assertEqual(self.fichier(), avant)

    def test_prix_candidat_dans_la_colonne_cachee_meme_reponse(self):
        candidates = self.empreintes_candidates()
        avant = self.fichier()
        _, lignes = lire_tableau(avant)
        reponses = {}
        for prix in CANDIDATS:
            reponse = self.put("technicien", avec_prix(lignes, prix), self.version("technicien"))
            reponses[prix] = (reponse.statut, reponse.octets)
            self.assertEqual(self.fichier(), avant, "prix %s : le fichier a changé" % prix)
        self.assertEqual({statut for statut, _ in reponses.values()}, {200}, reponses)
        self.assertEqual(len({corps for _, corps in reponses.values()}), 1, reponses)
        rendue = json.loads(reponses[PRIX][1].decode("utf-8"))["version"]
        self.assertNotIn(rendue, candidates.values())
        self.assertEqual(rendue, self.version("technicien"))

    def test_ajout_du_technicien_rend_sa_version(self):
        ligne = ["ART-0002", "ROU-002", "Roulement 6205", "Rouloran", "6205-2RS", "A1-02", "u", "1", "1", "1", "1", "3",
                 "99", "", "0", "1"]
        corps = (";".join(ENTETE) + "\r\n" + ";".join(ligne) + "\r\n").encode("utf-8")
        reponse = self.requete("technicien", "POST", "/api/csv/articles/ajout", corps)
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        self.assertNotEqual(reponse.json()["version"], empreinte(self.fichier()))
        self.assertEqual(reponse.json()["version"], self.version("technicien"))
        self.assertEqual(lire_tableau(self.fichier())[1][1][POSITION_PRIX], "", "prix d'une ligne ajoutée : vide")


class TestConflitsToujoursVus(CasServeur):
    """Témoins : le contrôle des écritures concurrentes tient pour tous les rôles et entre deux rôles."""

    def modifie(self, designation):
        _, lignes = lire_tableau(self.fichier())
        lignes[0][ENTETE.index("designation")] = designation
        return lignes

    def test_responsable_ecrit_le_technicien_est_en_conflit(self):
        lue = self.version("technicien")
        reponse = self.put("responsable", ecrire_tableau(ENTETE, self.modifie("Par le responsable")),
                           self.version("responsable"))
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        self.assertEqual(reponse.json()["version"], empreinte(self.fichier()))
        apres = self.fichier()
        refus = self.put("technicien", avec_prix(self.modifie("Par le technicien"), ""), lue)
        self.assertEqual(refus.statut, 409, refus.octets[:300])
        self.assertEqual(self.fichier(), apres)
        actuelle = refus.json()["version_actuelle"]
        self.assertNotEqual(actuelle, lue)
        self.assertEqual(actuelle, self.version("technicien"))
        accepte = self.put("technicien", avec_prix(self.modifie("Par le technicien"), ""), actuelle)
        self.assertEqual(accepte.statut, 200, accepte.octets[:300])
        self.assertEqual(accepte.json()["version"], self.version("technicien"))
        ligne = lire_tableau(self.fichier())[1][0]
        self.assertEqual((ligne[ENTETE.index("designation")], ligne[POSITION_PRIX]), ("Par le technicien", PRIX))

    def test_technicien_ecrit_le_responsable_est_en_conflit(self):
        lue = self.version("responsable")
        self.assertEqual(lue, empreinte(self.fichier()))
        reponse = self.put("technicien", avec_prix(self.modifie("Par le technicien"), ""), self.version("technicien"))
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        apres = self.fichier()
        refus = self.put("responsable", ecrire_tableau(ENTETE, self.modifie("Par le responsable")), lue)
        self.assertEqual(refus.statut, 409, refus.octets[:300])
        self.assertEqual(refus.json()["version_actuelle"], empreinte(apres))
        self.assertEqual(self.fichier(), apres)

    def test_technicien_version_perimee_ou_absente(self):
        lue = self.version("technicien")
        premier = self.put("technicien", avec_prix(self.modifie("Premier"), ""), lue)
        self.assertEqual(premier.statut, 200, premier.octets[:300])
        self.assertNotEqual(premier.json()["version"], lue)
        apres = self.fichier()
        for attendue in (lue, "aucune", "0" * 16, self.version("responsable")):
            refus = self.put("technicien", avec_prix(self.modifie("Second"), ""), attendue)
            self.assertEqual(refus.statut, 409, (attendue, refus.octets[:300]))
            self.assertEqual(refus.json()["version_actuelle"], premier.json()["version"], attendue)
        self.assertEqual(self.fichier(), apres)

    def test_tables_sans_colonne_cachee_et_responsable_inchanges(self):
        for role in ("technicien", "responsable"):
            self.assertEqual(self.version(role, "ordres_travail"), empreinte(self.fichier("ordres_travail")), role)
            self.assertEqual(self.version_listee(role, "ordres_travail"), empreinte(self.fichier("ordres_travail")), role)
        self.assertEqual(self.version("responsable"), empreinte(self.fichier()))
        self.assertEqual(self.version_listee("responsable"), empreinte(self.fichier()))

    def test_cle_du_serveur_gardee(self):
        premiere = self.version("technicien")
        cle = self.serveur.dossier / "acces" / ".cle-versions"
        self.assertTrue(cle.is_file(), "clé des versions absente de donnees/acces/")
        octets = cle.read_bytes()
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", octets.decode("ascii")), octets[:80])
        self.assertEqual(self.version("technicien"), premiere)
        self.assertEqual(self.version_listee("technicien"), premiere)
        self.assertEqual(cle.read_bytes(), octets)


class TestSansComptes(CasServeur):
    COMPTES = False

    def test_version_du_fichier_entier(self):
        self.assertEqual(self.version(None), empreinte(self.fichier()))
        self.assertEqual(self.version_listee(None), empreinte(self.fichier()))
        _, lignes = lire_tableau(self.fichier())
        reponse = self.put(None, avec_prix(lignes, "7"), empreinte(self.fichier()))
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        self.assertEqual(reponse.json()["version"], empreinte(self.fichier()))
        self.assertFalse((self.serveur.dossier / "acces" / ".cle-versions").exists())


if __name__ == "__main__":
    unittest.main()
