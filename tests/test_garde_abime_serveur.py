"""Garde « fichier abîmé » au niveau du stockage, côté serveur (T200b, chantier i18n-socle ; suite de T197, qui
protège le navigateur : Donnees.enregistrerLignes et ErreurFichierAbime de js/donnees.js).

Toutes les écritures de donnees/<table>.csv du serveur passent par UNE fonction commune (ecrire_fichier_de_donnees),
qui regarde le fichier en place avant d'écrire :
  - ajout en fin de fichier (POST /api/csv/<table>/ajout) : refusé si le fichier se termine au milieu d'un texte entre
    guillemets (finit_dans_un_guillemet_ouvert) : à la relecture, les lignes ajoutées seraient avalées dans cette
    cellule, donc perdues ; un fichier abîmé ailleurs mais à la fin propre reçoit l'ajout (rien n'est réécrit) ;
  - réécriture (PUT /api/csv/<table>, ecrire_table de l'assistant et du Solo, jeu de démo, passage au format) :
    refusée si le fichier en place est abîmé (raisons_fichier_abime, même critère que entree.abime du navigateur),
    sauf dérogation : PUT avec l'en-tête X-Prevo-Remplacer-Abime: 1 (import ZIP), et restauration d'une sauvegarde
    (le remède) ;
  - refus : 409 {"erreur", "code": "fichier_abime", "table"} ; la table reste identique à l'octet. T206 (inversé) : la
    sauvegarde du jour passe AVANT la garde, un refus la fait donc si elle manque (son manifeste marque le fichier
    abîmé ; tests/test_sauvegardes_abimes_serveur.py pour le reste).

Sans navigateur. Les jeux de tests/fixtures/formats (tests/jeux_formats.py) sont copiés dans un dossier temporaire
(jamais lus ni écrits en place, jamais de données réelles).

1. TestFonctions — finit_dans_un_guillemet_ouvert : exemples de la consigne (les mêmes que la version JS du
   navigateur), même résultat que l'automate appliqué octet par octet sur des suites tirées au hasard ;
   raisons_fichier_abime : jeux entete-tronque et f3-v1.2.0, cas fabriqués (colonnes en double non comptées : le
   navigateur garde la seconde colonne, associerColonnes).
2. TestEcrituresInternes — serveur.py importé comme module, sur une copie : ecrire_table (technicien_moi,
   poser_mode_solo) sur techniciens.csv ou parametres.csv abîmé, jeu de démo sur une base dont un fichier en place
   est abîmé, enregistrer_csv et ajouter_au_csv (tables identiques à l'octet ; T206 : la sauvegarde du jour faite
   avant le refus, verifier_sauvegarde_du_jour_puis_rien) ; restauration
   par-dessus un fichier abîmé ; passage au format au démarrage : un refus ne le fait pas planter ; journal à
   guillemet ouvert laissé tel quel par le passage.
3. TestRoutes — serveur réel (ServeurPrevo) : POST /api/csv/journal/ajout sur un journal à guillemet ouvert ; PUT
   sur entete-tronque, sans puis avec X-Prevo-Remplacer-Abime ; demandeur avec comptes sur demandes.csv abîmé.
4. TestStructure — module ast sur serveur.py : tout ecrire_atomique d'un chemin venu de chemin_table(...) est dans la
   fonction commune et nulle part ailleurs, aucune autre écriture brute d'un tel chemin ; et le contrôle voit bien un
   contournement fabriqué.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_garde_abime_serveur.py" -v
"""
import ast
import csv
import hashlib
import importlib.util
import io
import json
import random
import re
import shutil
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from commun import RACINE, ServeurPrevo
from jeux_formats import copier_jeu


def charger_serveur():
    """serveur.py importé comme module (le serveur lancé par ServeurPrevo est un autre processus)."""
    specification = importlib.util.spec_from_file_location("serveur_prevo_t200b", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


SERVEUR = charger_serveur()

BOM = b"\xef\xbb\xbf"
CODE = "fichier_abime"
ENTETE_DEROGATION = "X-Prevo-Remplacer-Abime"
FONCTION_COMMUNE = "ecrire_fichier_de_donnees"

# Exemples de la consigne T200 (octets → attendu), partagés avec la version JS du navigateur (t200a).
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
    """L'automate de la consigne appliqué octet par octet : référence écrite ici, indépendante de serveur.py."""
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
        elif etat == DEBUT:
            etat = ENTRE_GUILLEMETS if octet == 0x22 else DEBUT if octet in fins else DANS_LE_CHAMP
        else:                                                           # guillemet vu
            etat = ENTRE_GUILLEMETS if octet == 0x22 else DEBUT if octet in fins else DANS_LE_CHAMP
    return etat == ENTRE_GUILLEMETS


def version_de(octets):
    return hashlib.sha256(octets).hexdigest()[:16]


def fichiers_de(dossier):
    """{chemin relatif: octets} de tous les fichiers du dossier (sauvegardes comprises)."""
    dossier = Path(dossier)
    return {p.relative_to(dossier).as_posix(): p.read_bytes() for p in sorted(dossier.rglob("*")) if p.is_file()}


def lire_tableau(octets):
    """(en-tête, lignes) d'un CSV de Prévo (BOM, « ; »), cellules telles qu'écrites, lignes vides ignorées."""
    lignes = [ligne for ligne in csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";")
              if ligne]
    return lignes[0], lignes[1:]


def cellule(texte):
    """Comme celluleCsv de js/donnees.js (§3.1)."""
    return '"' + texte.replace('"', '""') + '"' if re.search(r'[;"\r\n]|\A[ \t]|[ \t]\Z', texte) else texte


def ecrire_tableau(entete, lignes):
    texte = "".join(";".join(cellule(valeur) for valeur in ligne) + "\r\n" for ligne in [entete] + list(lignes))
    return BOM + texte.encode("utf-8")


def sans_bom(octets):
    return octets[len(BOM):] if octets.startswith(BOM) else octets


def avec_une_valeur_en_trop(octets, cellules):
    """Le fichier plus une ligne qui a une valeur au-delà de l'en-tête (« en trop ») : fichier abîmé."""
    largeur = sans_bom(octets).split(b"\r\n", 1)[0].count(b";") + 1
    ligne = (list(cellules) + [""] * largeur)[:largeur] + ["en trop"]
    return octets + ";".join(ligne).encode("utf-8") + b"\r\n"


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
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-t200b-"))
        self.addCleanup(shutil.rmtree, self.temporaire, True)
        self.numero = 0

    def jeu(self, nom):
        """Copie neuve du jeu dans le dossier temporaire ; rend son dossier."""
        self.numero += 1
        return copier_jeu(nom, self.temporaire / ("copie-%d" % self.numero) / "donnees")

    def octets_du_jeu(self, nom, fichier):
        return (self.jeu(nom) / fichier).read_bytes()

    def config(self, dossier):
        config = SERVEUR.Configuration(str(dossier), [])
        SERVEUR.creer_dossiers(config)
        return config

    def verifier_refus(self, erreur, table, extrait="est abîmé"):
        """Le 409 de la garde : code fichier_abime, table, message clair (quoi, pourquoi, quoi faire)."""
        self.assertEqual(erreur.statut, 409, erreur.message)
        self.assertEqual(erreur.champs_supplementaires, {"code": CODE, "table": table})
        self.assertIn(table + ".csv", erreur.message)
        self.assertIn(extrait, erreur.message)
        self.assertIn("pour ne rien perdre", erreur.message)
        self.assertIn("restaurez une sauvegarde ou importez un ZIP", erreur.message)
        self.assertIn("Paramètres › Contrôle de la base", erreur.message)

    def verifier_sauvegarde_du_jour_puis_rien(self, dossier, avant, table):
        """T206 (contrat, point 1 ; inverse de T200, « rien d'écrit, sauvegarde du jour comprise ») : la sauvegarde du
        jour passe avant la garde. Le refus a fait UNE quotidienne, dont le manifeste marque le fichier abîmé ; à part
        elle et fichiers-abimes.json, rien n'a changé à l'octet."""
        apres = fichiers_de(dossier)
        nouvelles = sorted({chemin.split("/")[1] for chemin in apres
                            if chemin.startswith("sauvegardes/") and chemin not in avant})
        self.assertEqual(len(nouvelles), 1, nouvelles)
        self.assertRegex(nouvelles[0], r"^\d{4}-\d{2}-\d{2}$")
        manifeste = json.loads(apres["sauvegardes/%s/manifeste.json" % nouvelles[0]].decode("utf-8"))
        self.assertIn(table + ".csv", [decrit["nom"] for decrit in manifeste["fichiers"] if decrit.get("abime") is True])
        self.assertEqual({chemin: octets for chemin, octets in apres.items()
                          if not chemin.startswith("sauvegardes/%s/" % nouvelles[0])
                          and chemin != "fichiers-abimes.json"}, avant)

    def verifier_reponse_de_refus(self, statut, reponse, table, extrait="est abîmé"):
        self.assertEqual(statut, 409, reponse)
        self.assertEqual((reponse.get("code"), reponse.get("table")), (CODE, table), reponse)
        self.assertIn(table + ".csv", reponse["erreur"])
        self.assertIn(extrait, reponse["erreur"])


# ---------------------------------------------------------------------------
# 1. Fonctions
# ---------------------------------------------------------------------------

class TestFonctions(CasCopies):

    def test_finit_dans_un_guillemet_ouvert_exemples_de_la_consigne(self):
        for octets, attendu in EXEMPLES_GUILLEMET_OUVERT:
            with self.subTest(octets=octets):
                self.assertIs(SERVEUR.finit_dans_un_guillemet_ouvert(octets), attendu)
                self.assertIs(guillemet_ouvert_octet_par_octet(octets), attendu)       # la référence aussi

    def test_finit_dans_un_guillemet_ouvert_comme_l_automate_octet_par_octet(self):
        tirage = random.Random(200)
        alphabet = [b'"', b';', b',', b'\r', b'\n', b'a', b' ']
        for _ in range(4000):
            octets = b"".join(tirage.choice(alphabet) for _ in range(tirage.randrange(0, 14)))
            if tirage.random() < 0.2:
                octets = BOM + octets
            with self.subTest(octets=octets):
                self.assertIs(SERVEUR.finit_dans_un_guillemet_ouvert(octets), guillemet_ouvert_octet_par_octet(octets))

    def test_finit_dans_un_guillemet_ouvert_sur_les_jeux_et_un_journal_coupe(self):
        dossier = self.jeu("f3-v1.2.0")
        for chemin in sorted(dossier.glob("*.csv")):
            with self.subTest(fichier=chemin.name):
                self.assertFalse(SERVEUR.finit_dans_un_guillemet_ouvert(chemin.read_bytes()))
        journal = (dossier / "journal.csv").read_bytes()
        self.assertTrue(SERVEUR.finit_dans_un_guillemet_ouvert(journal + 'J-9;2026-04-01 10:00;"Poste coupé'.encode()))

    def test_raisons_fichier_abime_sur_les_jeux(self):
        tronque = self.jeu("entete-tronque")
        raisons = SERVEUR.raisons_fichier_abime((tronque / "ordres_travail.csv").read_bytes())
        self.assertTrue(raisons)
        self.assertIn("valeurs au-delà de l'en-tête", raisons)
        sain = self.jeu("f3-v1.2.0")
        for chemin in sorted(sain.glob("*.csv")):
            with self.subTest(fichier=chemin.name):
                self.assertEqual(SERVEUR.raisons_fichier_abime(chemin.read_bytes()), [])

    def test_raisons_fichier_abime_cas_fabriques(self):
        ordres = self.octets_du_jeu("f3-v1.2.0", "ordres_travail.csv")
        entete, reste = ordres.split(b"\r\n", 1)
        abimes = {
            "guillemet non fermé": ordres + 'OT-9999;"jamais fermé\r\n'.encode(),
            "texte collé à un guillemet fermant": ordres + b'OT-9998;"ferm\xc3\xa9"colle;x\r\n',
            "valeurs au-delà de l'en-tête": avec_une_valeur_en_trop(ordres, ["OT-9997"]),
        }
        for nom, octets in abimes.items():
            with self.subTest(cas=nom):
                self.assertTrue(SERVEUR.raisons_fichier_abime(octets))
        # Colonne en double : le navigateur garde la seconde (colonne inconnue « titre (2) », réécrite en fin de
        # fichier, associerColonnes) : rien ne se perd, le fichier n'est pas abîmé pour la garde.
        sains = {"colonne en double": entete + b";titre\r\n" + reste, "vide": b"", "BOM seul": BOM,
                 "blancs": BOM + b"  \r\n\r\n"}
        for nom, octets in sains.items():
            with self.subTest(cas=nom):
                self.assertEqual(SERVEUR.raisons_fichier_abime(octets), [])
        self.assertTrue(SERVEUR.lire_fichier_de_donnees(sains["colonne en double"])["pertes"])   # le passage, lui


# ---------------------------------------------------------------------------
# 2. Écritures internes (module, sur une copie)
# ---------------------------------------------------------------------------

class TestEcrituresInternes(CasCopies):

    def test_ecrire_table_par_technicien_moi_refuse_sur_techniciens_abime(self):
        dossier = self.jeu("f3-v1.2.0")
        abime = avec_une_valeur_en_trop((dossier / "techniciens.csv").read_bytes(), ["TEC-0999", "Essai", "Zoé"])
        (dossier / "techniciens.csv").write_bytes(abime)
        config = self.config(dossier)
        avant = fichiers_de(dossier)
        with SERVEUR.VERROU_ECRITURE, self.assertRaises(SERVEUR.ErreurHttp) as refus:
            SERVEUR.technicien_moi(config, "Camille", "Nouvelle")
        self.verifier_refus(refus.exception, "techniciens")
        self.verifier_sauvegarde_du_jour_puis_rien(dossier, avant, "techniciens")     # T206 : la quotidienne, seule

    def test_ecrire_table_par_poser_mode_solo_refuse_sur_parametres_abime(self):
        dossier = self.jeu("f3-v1.2.0")
        abime = avec_une_valeur_en_trop((dossier / "parametres.csv").read_bytes(), ["cle_maison", "valeur"])
        (dossier / "parametres.csv").write_bytes(abime)
        config = self.config(dossier)
        avant = fichiers_de(dossier)
        with SERVEUR.VERROU_ECRITURE, self.assertRaises(SERVEUR.ErreurHttp) as refus:
            SERVEUR.poser_mode_solo(config, "TEC-0001")
        self.verifier_refus(refus.exception, "parametres")
        self.verifier_sauvegarde_du_jour_puis_rien(dossier, avant, "parametres")

    def test_ecrire_table_sur_un_fichier_sain_ecrit_comme_avant(self):
        dossier = self.jeu("f3-v1.2.0")
        config = self.config(dossier)
        with SERVEUR.VERROU_ECRITURE:
            identifiant = SERVEUR.technicien_moi(config, "Camille", "Nouvelle")
            SERVEUR.poser_mode_solo(config, identifiant)
        entete, lignes = lire_tableau((dossier / "techniciens.csv").read_bytes())
        self.assertEqual(lignes[-1][:3], [identifiant, "Nouvelle", "Camille"])
        self.assertIn(b"mode_solo;1", (dossier / "parametres.csv").read_bytes())
        self.assertTrue(any(re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name) for p in (dossier / "sauvegardes").iterdir()))

    def test_jeu_de_demo_refuse_sans_toucher_aux_tables_si_un_fichier_en_place_est_abime(self):
        sain = self.octets_du_jeu("f3-v1.2.0", "techniciens.csv")
        dossier = self.temporaire / "demo" / "donnees"
        dossier.mkdir(parents=True)
        (dossier / "techniciens.csv").write_bytes(avec_une_valeur_en_trop(sain, ["TEC-0999", "Essai", "Zoé"]))
        config = self.config(dossier)
        avant = fichiers_de(dossier)
        with SERVEUR.VERROU_ECRITURE, self.assertRaises(SERVEUR.ErreurHttp) as refus:
            SERVEUR.installer_jeu_de_demo(config, {})
        self.verifier_refus(refus.exception, "techniciens")
        self.verifier_sauvegarde_du_jour_puis_rien(dossier, avant, "techniciens")     # aucune table de la démo

    def test_enregistrer_csv_refuse_apres_la_sauvegarde_du_jour(self):
        dossier = self.jeu("entete-tronque")
        sain = self.octets_du_jeu("f3-v1.2.0", "ordres_travail.csv")
        config = self.config(dossier)
        avant = fichiers_de(dossier)
        with SERVEUR.VERROU_ECRITURE, self.assertRaises(SERVEUR.ErreurHttp) as refus:
            SERVEUR.enregistrer_csv(config, "ordres_travail", sain, version_de(avant["ordres_travail.csv"]))
        self.verifier_refus(refus.exception, "ordres_travail")
        self.verifier_sauvegarde_du_jour_puis_rien(dossier, avant, "ordres_travail")
        with SERVEUR.VERROU_ECRITURE:                                  # dérogation (import ZIP) : écrit
            version = SERVEUR.enregistrer_csv(config, "ordres_travail", sain, version_de(avant["ordres_travail.csv"]),
                                              remplacer_abime=True)
        self.assertEqual(((dossier / "ordres_travail.csv").read_bytes(), version), (sain, version_de(sain)))

    def test_ajouter_au_csv_refuse_apres_la_sauvegarde_du_jour(self):
        dossier = self.jeu("f3-v1.2.0")
        journal = (dossier / "journal.csv").read_bytes()
        coupe = journal + 'J-9;2026-04-01 10:00;"Poste coupé'.encode()
        (dossier / "journal.csv").write_bytes(coupe)
        config = self.config(dossier)
        avant = fichiers_de(dossier)
        corps = sans_bom(journal).split(b"\r\n", 1)[0] + b"\r\nJ-10;2026-04-01 10:01;Poste test;;t;i;essai\r\n"
        with SERVEUR.VERROU_ECRITURE, self.assertRaises(SERVEUR.ErreurHttp) as refus:
            SERVEUR.ajouter_au_csv(config, "journal", corps)
        self.verifier_refus(refus.exception, "journal", "se termine au milieu d'un texte entre guillemets")
        self.verifier_sauvegarde_du_jour_puis_rien(dossier, avant, "journal")

    def test_restaurer_par_dessus_un_fichier_abime(self):
        dossier = self.jeu("f3-v1.2.0")
        config = self.config(dossier)
        sain = (dossier / "ordres_travail.csv").read_bytes()
        nom = SERVEUR.nouveau_nom_horodate(config)
        SERVEUR.copier_tables_dans_sauvegarde(config, nom)
        abime = self.octets_du_jeu("entete-tronque", "ordres_travail.csv")
        (dossier / "ordres_travail.csv").write_bytes(abime)
        with SERVEUR.VERROU_ECRITURE:
            resultat = SERVEUR.restaurer(config, nom, ["ordres_travail"])
        self.assertEqual(resultat["restaurees"], ["ordres_travail"])
        self.assertEqual((dossier / "ordres_travail.csv").read_bytes(), sain)
        securite = dossier / "sauvegardes" / resultat["copie_securite"] / "ordres_travail.csv"
        self.assertEqual(securite.read_bytes(), abime)                # le fichier abîmé reste dans la copie de sécurité

    def migrer(self, dossier):
        config = self.config(dossier)
        messages = []
        with mock.patch.object(SERVEUR, "afficher", side_effect=messages.append):
            etat = SERVEUR.migrer_donnees_au_demarrage(config)
        return etat, messages

    def test_passage_au_format_un_refus_de_la_garde_ne_le_fait_pas_planter(self):
        dossier = self.jeu("f2-v1.1.0")
        avant = fichiers_de(dossier)
        with mock.patch.object(SERVEUR, "raisons_fichier_abime", return_value=["raison de test"]):
            etat, messages = self.migrer(dossier)
        self.assertEqual((etat["migration"], etat["table_bloquee"], etat["base"]),
                         ("incomplete", "ordres_travail", 2))
        self.assertTrue(any("ordres_travail.csv ne peut pas être écrit" in m and "abîmé" in m for m in messages),
                        messages)
        apres = fichiers_de(dossier)
        for chemin in ("ordres_travail.csv", "parametres.csv"):
            self.assertEqual(apres[chemin], avant[chemin], chemin)

    def test_passage_au_format_laisse_un_journal_a_guillemet_ouvert(self):
        dossier = self.jeu("f2-v1.1.0")
        coupe = (dossier / "journal.csv").read_bytes() + 'J-9;2026-04-01 10:00;"Poste coupé'.encode()
        (dossier / "journal.csv").write_bytes(coupe)
        etat, messages = self.migrer(dossier)
        self.assertEqual((etat["migration"], etat["base"]), ("faite", 3))
        self.assertEqual((dossier / "journal.csv").read_bytes(), coupe)
        self.assertTrue(any("lignes du journal du passage non écrites" in m for m in messages), messages)


# ---------------------------------------------------------------------------
# 3. Routes (serveur réel)
# ---------------------------------------------------------------------------

class TestRoutes(CasCopies):

    def test_ajout_au_journal_a_guillemet_ouvert_refuse_puis_journal_sain_accepte(self):
        source = self.jeu("f3-v1.2.0")
        sain = (source / "journal.csv").read_bytes()
        coupe = sain + 'J-20260401100000-ABCD;2026-04-01 10:00;"Poste coupé'.encode()
        abime_ailleurs = avec_une_valeur_en_trop(sain, ["J-20260401100000-WXYZ", "2026-04-01 10:00"])
        (source / "journal.csv").write_bytes(coupe)
        entete = sans_bom(sain).split(b"\r\n", 1)[0]
        ligne = "J-20260401100100-EFGH;2026-04-01 10:01;Poste test;;ordres_travail;OT-2025-0001;essai\r\n".encode()
        with ServeurPrevo(source=source) as serveur:
            chemin = serveur.dossier / "journal.csv"
            statut, reponse = requete(serveur, "POST", "/api/csv/journal/ajout", entete + b"\r\n" + ligne)
            self.verifier_reponse_de_refus(statut, reponse, "journal", "se termine au milieu d'un texte entre guillemets")
            self.assertEqual(chemin.read_bytes(), coupe)
            # Abîmé ailleurs (valeur au-delà de l'en-tête), fin propre : l'ajout ne réécrit rien, il est permis.
            chemin.write_bytes(abime_ailleurs)
            statut, reponse = requete(serveur, "POST", "/api/csv/journal/ajout", entete + b"\r\n" + ligne)
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(chemin.read_bytes(), abime_ailleurs + ligne)
            # Journal sain : 200 comme avant.
            chemin.write_bytes(sain)
            statut, reponse = requete(serveur, "POST", "/api/csv/journal/ajout", entete + b"\r\n" + ligne)
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(chemin.read_bytes(), sain + ligne)
            self.assertEqual(reponse["version"], version_de(sain + ligne))

    def test_put_sur_entete_tronque_refuse_sauf_derogation_puis_fichier_sain(self):
        source = self.jeu("entete-tronque")
        abime = (source / "ordres_travail.csv").read_bytes()
        sain = self.octets_du_jeu("f3-v1.2.0", "ordres_travail.csv")
        with ServeurPrevo(source=source) as serveur:
            chemin = serveur.dossier / "ordres_travail.csv"
            self.assertEqual(chemin.read_bytes(), abime)              # le démarrage ne l'a pas touché
            attendue = {"X-Version-Attendue": version_de(abime)}
            for entetes in (attendue, dict(attendue, **{ENTETE_DEROGATION: "0"}),
                            dict(attendue, **{ENTETE_DEROGATION: "oui"})):
                with self.subTest(entetes=entetes):
                    statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", sain, entetes)
                    self.verifier_reponse_de_refus(statut, reponse, "ordres_travail")
                    self.assertEqual(chemin.read_bytes(), abime)
            # Le contrôle de version passe d'abord : un 409 de conflit reste un 409 de conflit.
            statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", sain,
                                      {"X-Version-Attendue": "0123456789abcdef", ENTETE_DEROGATION: "1"})
            self.assertEqual(statut, 409, reponse)
            self.assertEqual(reponse.get("version_actuelle"), version_de(abime))
            self.assertNotIn("code", reponse)
            self.assertEqual(chemin.read_bytes(), abime)
            # Dérogation (import ZIP) : écrit.
            statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", sain,
                                      dict(attendue, **{ENTETE_DEROGATION: "1"}))
            self.assertEqual(statut, 200, reponse)
            self.assertEqual((chemin.read_bytes(), reponse["version"]), (sain, version_de(sain)))
            # Fichier sain : PUT sans dérogation, 200 comme avant.
            modifie = sain.replace(b"Entretien mensuel du compresseur CP-01", b"Entretien mensuel du compresseur CP-1")
            self.assertNotEqual(modifie, sain)
            statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", modifie,
                                      {"X-Version-Attendue": version_de(sain)})
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(chemin.read_bytes(), modifie)

    def test_demandeur_avec_comptes_sur_demandes_abime(self):
        source = self.jeu("f3-v1.2.0")
        octets = (source / "demandes.csv").read_bytes()
        entete, lignes = lire_tableau(octets)
        ancienne = [""] * len(entete)
        for nom, valeur in {"id": "DI-2025-0999", "date_heure": "2025-10-01 09:00", "demandeur": "Léa Fontaine",
                            "equipement_id": "EQ-0001", "symptome": "Bruit", "impact": "aucun",
                            "statut": "Acceptée"}.items():
            ancienne[entete.index(nom)] = valeur
        abime = avec_une_valeur_en_trop(octets, ancienne)
        (source / "demandes.csv").write_bytes(abime)
        nouvelle = [""] * len(entete)
        for nom, valeur in {"id": "DI-2026-9001", "date_heure": "2026-04-01 10:15", "demandeur": "Léa Martin",
                            "equipement_id": "EQ-0005", "symptome": "Fuite", "impact": "dégradé",
                            "statut": "Nouvelle"}.items():
            nouvelle[entete.index(nom)] = valeur
        # Ce que le navigateur du demandeur envoie : les demandes lues (la valeur en trop est ignorée), plus la sienne.
        corps = ecrire_tableau(entete, lignes + [ancienne, nouvelle])
        with ServeurPrevo(source=source, comptes=True) as serveur:
            chemin = serveur.dossier / "demandes.csv"
            statut, reponse = requete(serveur, "PUT", "/api/csv/demandes", corps,
                                      {"X-Version-Attendue": version_de(abime), "Cookie": serveur.session("demandeur")})
            self.verifier_reponse_de_refus(statut, reponse, "demandes")
            self.assertEqual(chemin.read_bytes(), abime)
            # Fichier sain : la même demande passe, comme avant.
            chemin.write_bytes(ecrire_tableau(entete, lignes + [ancienne]))
            statut, reponse = requete(serveur, "PUT", "/api/csv/demandes", corps,
                                      {"X-Version-Attendue": version_de(chemin.read_bytes()),
                                       "Cookie": serveur.session("demandeur")})
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(lire_tableau(chemin.read_bytes())[1], lignes + [ancienne, nouvelle])

    def test_derogation_reservee_au_responsable_avec_les_comptes(self):
        """Avec les comptes, l'import ZIP est réservé au responsable (D172) : X-Prevo-Remplacer-Abime aussi. Un
        technicien qui l'envoie reçoit 403 et rien n'est écrit ; le responsable remplace le fichier abîmé."""
        source = self.jeu("entete-tronque")
        abime = (source / "ordres_travail.csv").read_bytes()
        entete, lignes = lire_tableau(self.octets_du_jeu("f3-v1.2.0", "ordres_travail.csv"))
        corps = ecrire_tableau(entete, lignes)
        with ServeurPrevo(source=source, comptes=True) as serveur:
            chemin = serveur.dossier / "ordres_travail.csv"
            entetes = {"X-Version-Attendue": version_de(abime), "X-Prevo-Remplacer-Abime": "1"}
            statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", corps,
                                      dict(entetes, Cookie=serveur.session("technicien")))
            self.assertEqual(statut, 403, reponse)
            self.assertIn("seul le responsable", reponse["erreur"])
            self.assertEqual(chemin.read_bytes(), abime)
            statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", corps,
                                      dict(entetes, Cookie=serveur.session("responsable")))
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(lire_tableau(chemin.read_bytes())[1], lignes)


# ---------------------------------------------------------------------------
# 4. Structure de serveur.py (module ast)
# ---------------------------------------------------------------------------

# Écritures brutes d'un fichier (nom de la fonction appelée, quel que soit le module) ; open n'y compte qu'en écriture.
ECRITURES_BRUTES = {"remplacer_avec_essais", "replace", "rename", "copy", "copy2", "copyfile", "move", "write_bytes",
                    "write_text"}


def nom_appele(appel):
    fonction = appel.func
    return fonction.id if isinstance(fonction, ast.Name) else fonction.attr if isinstance(fonction, ast.Attribute) \
        else None


def est_appel_de_chemin_table(noeud):
    return isinstance(noeud, ast.Call) and nom_appele(noeud) == "chemin_table"


FONCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


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
    chemin = os.path.join(config.dossier_donnees, 'derniere-version.json')
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
