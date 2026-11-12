"""Colonnes en double côté serveur (T500, lot L7 ; relecture du 12/11 : R4 E1 et E2, R1 M4 ; ARCHITECTURE.md §22.5).

Règles vérifiées :
    première colonne   pour deux colonnes de même clé (cle_entete : « Prix Unitaire » = prix_unitaire), le serveur
                       lit la PREMIÈRE partout (dictionnaires_csv, remise des colonnes cachées, contrôle des
                       demandes), comme le navigateur (associerColonnes de js/donnees.js) ;
    technicien         il ne change plus prix_unitaire (articles, achats) ni equipements.cout_arret_h par une colonne
                       en double : son PUT (et son ajout) est refusé (400), deux fois de suite, fichier inchangé ; et
                       si le fichier porte déjà une telle colonne, c'est la vraie colonne qui est remise ;
    demandeur          il ne crée plus une demande déjà décidée par des colonnes en double : PUT et ajout refusés
                       (400) ; le contrôle lit la première colonne (403) et la ligne nouvelle est écrite depuis les
                       valeurs contrôlées ;
    témoins            le PUT normal du technicien passe toujours (colonne inconnue comprise), la demande normale du
                       demandeur aussi ; le responsable n'est pas bloqué par une colonne en double ;
    passage 3→4        une base 3 dont controles_reglementaires.csv a deux colonnes hors schéma du même nom n'est plus
                       « laissée » : ses réserves sont reprises (les mêmes que sans ces colonnes), la seconde colonne
                       devient « nom (2) » comme dans le navigateur ; une colonne du schéma en double reste laissée.

Aucune donnée réelle : copies temporaires des jeux f4-v2.2.0 et reserves-a-reprendre (tests/jeux_formats.py). Serveur
réel (ServeurPrevo) avec les trois comptes ; sans navigateur.
Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_colonnes_en_double.py" -v
"""
import csv
import http.client
import importlib.util
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import commun
from commun import RACINE
from jeux_formats import copier_jeu

JEU = "f4-v2.2.0"
JEU_A_REPRENDRE = "reserves-a-reprendre"
AGENT = "tests-prevo/1.0"
BOM = bytes((0xEF, 0xBB, 0xBF))
FORGE = "9999"
# (table, colonne cachée au technicien, nom de la colonne en double : même clé, autre écriture)
COLONNES_DU_TECHNICIEN = (("articles", "prix_unitaire", "Prix Unitaire"),
                          ("achats", "prix_unitaire", "Prix Unitaire"),
                          ("equipements", "cout_arret_h", "Cout Arret H"))
CHAMPS_DE_DECISION = ("statut", "motif_decision", "date_decision", "ot_id")
DECISION_FORGEE = {"statut": "Acceptée", "motif_decision": "accord du responsable", "date_decision": "2026-11-12",
                   "ot_id": "OT-0001"}
DECISION_VIDE = {"statut": "Nouvelle", "motif_decision": "", "date_decision": "", "ot_id": ""}


def charger_serveur():
    """serveur.py importé comme module (le serveur lancé par ServeurPrevo est un autre processus)."""
    specification = importlib.util.spec_from_file_location("serveur_prevo_t500", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


SERVEUR = charger_serveur()


def lire_tableau(octets):
    """(en-tête, lignes) d'un CSV de Prévo (BOM, « ; »), valeurs telles qu'écrites ; lignes à la largeur de l'en-tête."""
    lignes = [ligne for ligne in csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";") if ligne]
    return lignes[0], [ligne + [""] * (len(lignes[0]) - len(ligne)) for ligne in lignes[1:]]


def cellule(texte):
    """Comme celluleCsv de js/donnees.js (§3.1)."""
    return '"' + texte.replace('"', '""') + '"' if re.search(r'[;"\r\n]|\A[ \t]|[ \t]\Z', texte) else texte


def ecrire_tableau(entete, lignes, bom=True):
    texte = "".join(";".join(cellule(valeur) for valeur in ligne) + "\r\n" for ligne in [entete] + list(lignes))
    return (BOM if bom else b"") + texte.encode("utf-8")


def colonne(octets, nom):
    """{id : valeur} de la PREMIÈRE colonne de ce nom exact."""
    entete, lignes = lire_tableau(octets)
    position = entete.index(nom)
    return {ligne[0]: ligne[position] for ligne in lignes}


def avec_colonne_en_plus(octets, nom, valeur):
    entete, lignes = lire_tableau(octets)
    return ecrire_tableau(entete + [nom], [ligne + [valeur] for ligne in lignes])


def demande_nouvelle(entete, identifiant, decision):
    """Ligne d'une demande neuve, sur les colonnes du schéma (entete)."""
    valeurs = {"id": identifiant, "date_heure": "2026-11-12 09:00", "demandeur": "Léa Martin", "symptome": "fuite",
               "impact": "gêne", "description": "essai T500"}
    valeurs.update(decision)
    return [valeurs.get(nom, "") for nom in entete]


def demandes_avec_doubles(actuel, identifiant, vraies, doubles):
    """demandes.csv reçu : l'en-tête du schéma suivi des quatre colonnes de décision en double ; les lignes actuelles
    y portent deux fois leurs valeurs, la ligne nouvelle « vraies » dans les colonnes du schéma et « doubles » après."""
    entete, lignes = lire_tableau(actuel)
    positions = [entete.index(champ) for champ in CHAMPS_DE_DECISION]
    anciennes = [ligne + [ligne[position] for position in positions] for ligne in lignes]
    nouvelle = demande_nouvelle(entete, identifiant, vraies) + [doubles[champ] for champ in CHAMPS_DE_DECISION]
    return ecrire_tableau(entete + list(CHAMPS_DE_DECISION), anciennes + [nouvelle])


class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets


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
    """Serveur réel sur une copie du jeu f4-v2.2.0, sessions des trois rôles ; chaque test remet les fichiers qu'il
    change (remettre)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.racine = Path(tempfile.mkdtemp(prefix="prevo-colonnes-double-"))
        cls.addClassCleanup(shutil.rmtree, cls.racine, True)
        cls.serveur = commun.ServeurPrevo(source=copier_jeu(JEU, cls.racine / "source"), comptes=True)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.cookies = {role: cls.serveur.session(role) for role in ("demandeur", "technicien", "responsable")}

    def requete(self, role, methode, chemin, corps=None, entetes=None):
        return requete(self.serveur, methode, chemin, corps, self.cookies[role], entetes)

    def chemin(self, table):
        return self.serveur.dossier / (table + ".csv")

    def fichier(self, table):
        return self.chemin(table).read_bytes()

    def remettre(self, table):
        """Le fichier de cette table retrouve ses octets d'avant le test ; rend ces octets."""
        avant = self.fichier(table)
        self.addCleanup(self.chemin(table).write_bytes, avant)
        return avant

    def ecrire(self, role, table, octets):
        """PUT de la table entière, avec la version lue par ce rôle."""
        lue = self.requete(role, "GET", "/api/csv/" + table)
        self.assertEqual(lue.statut, 200, lue.octets[:300])
        return self.requete(role, "PUT", "/api/csv/" + table, octets, {"X-Version-Attendue": lue.entetes["x-version"]})

    def ajouter(self, role, table, entete, lignes):
        return self.requete(role, "POST", "/api/csv/%s/ajout" % table, ecrire_tableau(entete, lignes, bom=False))


class TestTechnicien(CasServeur):

    def test_colonne_en_double_refusee_deux_put_de_suite(self):
        """Le scénario du relecteur : l'en-tête du schéma plus « Prix Unitaire » à 9999, envoyé deux fois."""
        for table, cachee, double in COLONNES_DU_TECHNICIEN:
            with self.subTest(table=table):
                avant = self.remettre(table)
                corps = avec_colonne_en_plus(avant, double, FORGE)
                for essai in (1, 2):
                    reponse = self.ecrire("technicien", table, corps)
                    self.assertEqual(reponse.statut, 400, "PUT %d : %r" % (essai, reponse.octets[:300]))
                    self.assertEqual(self.fichier(table), avant)
                self.assertNotIn(FORGE, colonne(self.fichier(table), cachee).values())

    def test_fichier_qui_porte_deja_le_double_la_vraie_colonne_est_remise(self):
        """Une base réelle peut porter la colonne en double : la valeur remise est celle de la PREMIÈRE colonne."""
        for table, cachee, double in COLONNES_DU_TECHNICIEN:
            with self.subTest(table=table):
                avant = self.remettre(table)
                self.chemin(table).write_bytes(avec_colonne_en_plus(avant, double, FORGE))
                entete, lignes = lire_tableau(avant)
                position = entete.index(cachee)
                forgees = [ligne[:position] + ["1"] + ligne[position + 1:] for ligne in lignes]
                reponse = self.ecrire("technicien", table, ecrire_tableau(entete, forgees))
                self.assertEqual(reponse.statut, 200, reponse.octets[:300])
                self.assertEqual(colonne(self.fichier(table), cachee), colonne(avant, cachee))

    def test_ajout_avec_colonne_en_double_refuse(self):
        avant = self.remettre("articles")
        entete, lignes = lire_tableau(avant)
        nouvelle = ["ART-9001"] + [""] * (len(entete) - 1) + [FORGE]
        reponse = self.ajouter("technicien", "articles", entete + ["Prix Unitaire"], [nouvelle])
        self.assertEqual(reponse.statut, 400, reponse.octets[:300])
        self.assertEqual(self.fichier("articles"), avant)

    def test_temoin_le_put_normal_passe_toujours(self):
        avant = self.remettre("articles")
        entete, lignes = lire_tableau(avant)
        stock = entete.index("stock")
        lignes[0][stock] = str(int(lignes[0][stock]) + 1)
        reponse = self.ecrire("technicien", "articles", ecrire_tableau(entete, lignes))
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        self.assertEqual(lire_tableau(self.fichier("articles")), (entete, lignes))
        # Une colonne inconnue (hors schéma, clé nouvelle) n'est pas un double : toujours acceptée.
        reponse = self.ecrire("technicien", "articles", avec_colonne_en_plus(self.fichier("articles"), "remarque", "vu"))
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        self.assertEqual(colonne(self.fichier("articles"), "prix_unitaire"), colonne(avant, "prix_unitaire"))
        self.assertEqual(set(colonne(self.fichier("articles"), "remarque").values()), {"vu"})


class TestDemandeur(CasServeur):

    def test_demande_deja_decidee_par_colonnes_en_double_refusee(self):
        avant = self.remettre("demandes")
        corps = demandes_avec_doubles(avant, "DI-9001", DECISION_FORGEE, DECISION_VIDE)
        reponse = self.ecrire("demandeur", "demandes", corps)
        self.assertEqual(reponse.statut, 400, reponse.octets[:300])
        self.assertEqual(self.fichier("demandes"), avant)
        entete, lignes = lire_tableau(corps)
        ajout = self.ajouter("demandeur", "demandes", entete, lignes[-1:])
        self.assertEqual(ajout.statut, 400, ajout.octets[:300])
        self.assertEqual(self.fichier("demandes"), avant)

    def test_le_controle_lit_la_premiere_colonne_et_ecrit_les_valeurs_controlees(self):
        """Les fonctions du contrôle, sans le refus de l'en-tête : la décision forgée dans les vraies colonnes est vue
        (403) ; forgée dans les doubles, elle n'est jamais écrite."""
        avant = self.fichier("demandes")
        with self.assertRaises(SERVEUR.ErreurHttp) as refus:
            SERVEUR.garder_les_demandes_actuelles(demandes_avec_doubles(avant, "DI-9001", DECISION_FORGEE, DECISION_VIDE),
                                                  avant)
        self.assertEqual(refus.exception.statut, 403)
        ecrit = SERVEUR.garder_les_demandes_actuelles(
            demandes_avec_doubles(avant, "DI-9001", DECISION_VIDE, DECISION_FORGEE), avant)
        derniere = lire_tableau(ecrit)[1][-1]
        self.assertEqual(derniere[0], "DI-9001")
        for valeur in DECISION_FORGEE.values():
            self.assertNotIn(valeur, derniere)
        lignes = SERVEUR.dictionnaires_csv(BOM + b"id;statut;Statut\r\nDI-1;Nouvelle;Accept\xc3\xa9e\r\n", "demandes")
        self.assertEqual(lignes, [{"id": "DI-1", "statut": "Nouvelle"}])

    def test_temoin_la_demande_normale_passe_toujours(self):
        avant = self.remettre("demandes")
        entete, lignes = lire_tableau(avant)
        nouvelle = demande_nouvelle(entete, "DI-9002", DECISION_VIDE)
        reponse = self.ecrire("demandeur", "demandes", ecrire_tableau(entete, lignes + [nouvelle]))
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        self.assertEqual(lire_tableau(self.fichier("demandes")), (entete, lignes + [nouvelle]))
        forgee = demande_nouvelle(entete, "DI-9003", DECISION_FORGEE)
        refus = self.ecrire("demandeur", "demandes", ecrire_tableau(entete, lignes + [nouvelle, forgee]))
        self.assertEqual(refus.statut, 403, refus.octets[:300])


class TestResponsable(CasServeur):

    def test_le_responsable_n_est_pas_bloque(self):
        avant = self.remettre("articles")
        corps = avec_colonne_en_plus(avant, "Prix Unitaire", FORGE)
        reponse = self.ecrire("responsable", "articles", corps)
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        self.assertEqual(self.fichier("articles"), corps)


class TestPassageAuFormat4(unittest.TestCase):
    """migrer_donnees_au_demarrage du module, sur des copies du jeu reserves-a-reprendre (base au format 3)."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp(prefix="prevo-colonnes-double-passage-"))
        self.addCleanup(shutil.rmtree, self.racine, True)

    def migrer(self, nom, changer=None):
        dossier = copier_jeu(JEU_A_REPRENDRE, self.racine / nom / "donnees")
        if changer:
            chemin = dossier / "controles_reglementaires.csv"
            chemin.write_bytes(changer(chemin.read_bytes()))
        config = SERVEUR.Configuration(str(dossier), [])
        SERVEUR.creer_dossiers(config)
        with mock.patch.object(SERVEUR, "afficher"):
            etat = SERVEUR.migrer_donnees_au_demarrage(config)
        return dossier, etat

    @staticmethod
    def avec_deux_notes(octets):
        entete, lignes = lire_tableau(octets)
        return ecrire_tableau(entete + ["note", "note"], [ligne + ["a", "b"] for ligne in lignes])

    def test_deux_colonnes_hors_schema_du_meme_nom_les_reserves_sont_reprises(self):
        temoin, etat_temoin = self.migrer("temoin")
        reserves_temoin = (temoin / "reserves_controle.csv").read_bytes()
        self.assertGreater(len(lire_tableau(reserves_temoin)[1]), 0, "le jeu n'a plus de réserve à reprendre")
        dossier, etat = self.migrer("double", self.avec_deux_notes)
        self.assertEqual(etat["tables_abimees"], [])
        self.assertEqual((etat["migration"], etat["base"]), ("faite", etat_temoin["base"]))
        self.assertTrue((dossier / "reserves_controle.csv").is_file(), "aucune réserve reprise")
        self.assertEqual((dossier / "reserves_controle.csv").read_bytes(), reserves_temoin)
        # controles_reglementaires réécrit : ses colonnes dans leur ordre, la seconde « note » nommée comme le
        # navigateur la nomme, les cellules gardées, puis les colonnes du format 4.
        source = copier_jeu(JEU_A_REPRENDRE, self.racine / "source") / "controles_reglementaires.csv"
        avant = lire_tableau(self.avec_deux_notes(source.read_bytes()))[0]
        entete, lignes = lire_tableau((dossier / "controles_reglementaires.csv").read_bytes())
        entete_temoin = lire_tableau((temoin / "controles_reglementaires.csv").read_bytes())[0]
        self.assertEqual(entete.count("note"), 1)
        position = entete.index("note")
        self.assertEqual(entete[position:position + 2], ["note", "note (2)"])
        self.assertEqual({(ligne[position], ligne[position + 1]) for ligne in lignes}, {("a", "b")})
        self.assertEqual(entete[:position] + entete[position + 2:], entete_temoin)
        self.assertEqual(entete[:len(avant)], avant[:-1] + ["note (2)"])

    def test_colonne_du_schema_en_double_toujours_laissee(self):
        def avec_double_du_schema(octets):
            return avec_colonne_en_plus(octets, "Observations", "x")
        dossier, etat = self.migrer("schema", avec_double_du_schema)
        self.assertEqual(etat["tables_abimees"], ["controles_reglementaires"])
        self.assertFalse((dossier / "reserves_controle.csv").exists())


if __name__ == "__main__":
    unittest.main()
