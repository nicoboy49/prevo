"""Sauvegardes du serveur (chantier « socle de données », T187 ; décision D170 ; docs/FORMAT.md §8 et §9 ; serveur.py :
preparer_donnees_au_demarrage, sauvegarder_avant_mise_a_jour, faire_sauvegarde_du_jour,
purger_sauvegardes_quotidiennes, ecrire_manifeste, copier_documents_dans_sauvegarde).

Ce qui est vérifié, sans navigateur :
    rotation           à chaque nouvelle sauvegarde quotidienne, celles de plus de 30 jours (jour de l'horloge du
                       serveur) sont supprimées : 10, 29 et 30 jours gardées, 31 et 45 supprimées ; « avant-… »
                       anciennes, manuelles et noms étrangers (date impossible, fichier, autre nom) jamais touchés ;
                       aucune rotation sans nouvelle quotidienne ; au démarrage du serveur réel (date du jour) aussi ;
    avant-mise-a-jour  premier démarrage sur une copie de f2-v1.1.0 et de f3-v1.2.0 sans derniere-version.json :
                       sauvegarde aux octets d'ORIGINE (avant le passage au format 3), manifeste « de » = « inconnue »,
                       « vers » = version courante, derniere-version.json écrit, sauvegarde du jour faite APRÈS le
                       passage ; second démarrage : aucun octet changé ; autre version notée : nouvelle sauvegarde ;
                       même version : aucune ; base vide : rien ; fichier illisible : « inconnue » ; sauvegarde
                       impossible : un message, derniere-version.json pas écrit ; lecture seule : faite quand même ;
    manifeste          dans chaque sauvegarde (quotidienne, manuelle, à motif, avant-restauration) : champs de
                       Formats.manifeste (js/formats.js) dans le même ordre, fichiers triés, tailles et SHA-256
                       recalculés par hashlib, format des données copiées, date de l'horloge du serveur ; ignoré par la
                       restauration et par « Tester » ;
    avant-import-zip   documents/ copié (fichiers seulement : ni caché, ni sous-dossier) et compté dans le manifeste ;
                       quotidienne, manuelle et autres motifs sans documents ;
    motifs             liste fermée : motif inconnu 400, rien de créé ; noms admis par MOTIF_NOM_SAUVEGARDE ; mêmes
                       motifs et même motif de nom dans js/stockage-dossier.js.

Deux façons de lancer : serveur.py importé et servi dans ce processus, horloge simulée (config.horloge) ; serveur réel
(ServeurPrevo de tests/commun.py, date du jour) pour ce que fait main au démarrage. Jeux de tests/fixtures/formats
copiés dans un dossier temporaire (règle du chantier : jamais de données réelles).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_sauvegardes_socle.py" -v
"""
import datetime
import hashlib
import http.client
import importlib.util
import json
import re
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import commun
from commun import RACINE
from jeux_formats import copier_jeu


def charger_serveur():
    """serveur.py importé comme module (le serveur lancé par commun.ServeurPrevo est un autre processus)."""
    specification = importlib.util.spec_from_file_location("serveur_prevo_t187", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


SERVEUR = charger_serveur()

BOM = bytes((0xEF, 0xBB, 0xBF))
CRLF = bytes((13, 10))
MOTIF_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
MOTIF_DATE_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
COMPTES_JSON = json.dumps({"version": 1, "comptes": [{"identifiant": "nicolas.briand", "role": "responsable",
                                                      "actif": True}]}, indent=2).encode("utf-8")
SESSIONS_JSON = json.dumps({"0" * 64: {"identifiant": "nicolas.briand"}}).encode("utf-8")
PHOTO = bytes(range(256)) * 40                  # 10 Ko : un document « binaire »
RAPPORT = b"%PDF-1.4\n% rapport de controle\n"


def champs_de_formats_js():
    """Champs du contexte de Formats.manifeste (CHAMPS_CONTEXTE de js/formats.js), dans leur ordre."""
    texte = (RACINE / "js" / "formats.js").read_text(encoding="utf-8")
    trouve = re.search(r"const CHAMPS_CONTEXTE = \[([^\]]*)\]", texte)
    if not trouve:
        raise AssertionError("CHAMPS_CONTEXTE introuvable dans js/formats.js")
    return re.findall(r"'([^']*)'", trouve.group(1))


CHAMPS_DU_MANIFESTE = ["application"] + champs_de_formats_js() + ["fichiers"]


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------

def instant(annee, mois, jour, heure=0, minute=0, seconde=0):
    """Secondes d'une heure locale (les noms des sauvegardes sont en heure locale)."""
    return datetime.datetime(annee, mois, jour, heure, minute, seconde).timestamp()


def csv_de(table, *lignes):
    """CSV au format Prévo (BOM, « ; », CRLF) : en-tête du schéma, puis les lignes données (texte)."""
    entete = ";".join(SERVEUR.COLONNES_PAR_TABLE[table]).encode("utf-8")
    return BOM + CRLF.join([entete] + [ligne.encode("utf-8") for ligne in lignes]) + CRLF


def fichiers_de(dossier):
    """{chemin relatif « / »: octets} de tous les fichiers d'un dossier."""
    dossier = Path(dossier)
    return {p.relative_to(dossier).as_posix(): p.read_bytes() for p in sorted(dossier.rglob("*")) if p.is_file()}


def csv_a_la_racine(fichiers):
    return {chemin: octets for chemin, octets in fichiers.items() if "/" not in chemin and chemin.endswith(".csv")}


def noms_des_sauvegardes(dossier_donnees):
    dossier = Path(dossier_donnees) / "sauvegardes"
    return sorted(p.name for p in dossier.iterdir()) if dossier.is_dir() else []


def une_seule(noms, suffixe):
    trouves = [nom for nom in noms if nom.endswith(suffixe)]
    if len(trouves) != 1:
        raise AssertionError("une sauvegarde « …%s » attendue : %r" % (suffixe, noms))
    return trouves[0]


def lire_manifeste(dossier_sauvegarde):
    return json.loads((Path(dossier_sauvegarde) / "manifeste.json").read_text(encoding="utf-8"))


def fichiers_attendus(dossier_sauvegarde):
    """Calcul indépendant de « fichiers » : chaque fichier de la sauvegarde sauf manifeste.json, chemin relatif en « / »,
    trié par nom, taille et SHA-256 complet (hashlib)."""
    return [{"nom": chemin, "octets": len(octets), "sha256": hashlib.sha256(octets).hexdigest()}
            for chemin, octets in sorted(fichiers_de(dossier_sauvegarde).items()) if chemin != "manifeste.json"]


def requete(port, methode, chemin, corps=None, entetes=None):
    """(statut, objet JSON) d'une requête vers un serveur Prévo de 127.0.0.1 ; X-Prevo sur les écritures."""
    entetes = dict(entetes or {})
    if isinstance(corps, (dict, list)):
        corps = json.dumps(corps).encode("utf-8")
    if methode in ("PUT", "POST"):
        corps = corps if corps is not None else b""
        entetes.setdefault("X-Prevo", "1")
        entetes["Content-Length"] = str(len(corps))
    connexion = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        connexion.request(methode, chemin, body=corps, headers=entetes)
        reponse = connexion.getresponse()
        octets = reponse.read()
        type_contenu = reponse.getheader("Content-Type", "")
        return reponse.status, json.loads(octets.decode("utf-8")) if "json" in type_contenu else octets
    finally:
        connexion.close()


class ServeurDansLeProcessus:
    """serveur.py importé et servi dans un fil de ce processus ; config.horloge rend self.instant."""

    def __init__(self, dossier_donnees, depart):
        self.instant = depart
        self.config = SERVEUR.Configuration(str(dossier_donnees), [])
        self.config.horloge = lambda: self.instant
        SERVEUR.creer_dossiers(self.config)
        self.http = SERVEUR.ServeurPrevo(("127.0.0.1", 0), self.config)
        self.config.port = self.http.server_address[1]
        self.fil = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.fil.start()

    def requete(self, methode, chemin, corps=None, entetes=None):
        return requete(self.config.port, methode, chemin, corps, entetes)

    def ecrire_parametres(self, nom_entreprise):
        """PUT /api/csv/parametres (version lue sur le disque), comme un poste qui enregistre."""
        chemin = Path(self.config.dossier_donnees) / "parametres.csv"
        attendue = hashlib.sha256(chemin.read_bytes()).hexdigest()[:16] if chemin.is_file() else "aucune"
        statut, reponse = self.requete("PUT", "/api/csv/parametres",
                                       csv_de("parametres", "version_schema;'3", "entreprise_nom;" + nom_entreprise),
                                       {"X-Version-Attendue": attendue})
        if statut != 200:
            raise AssertionError("écriture refusée : %d %r" % (statut, reponse))

    def arreter(self):
        if self.http is not None:
            self.http.shutdown()
            self.http.server_close()
            self.fil.join(timeout=5)
            self.http = None


class CasDossier(unittest.TestCase):
    """Dossier temporaire ; console de serveur.py relevée (self.console)."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp(prefix="prevo-t187-"))
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.console = []
        espion = mock.patch.object(SERVEUR, "afficher", side_effect=self.console.append)
        espion.start()
        self.addCleanup(espion.stop)

    def donnees_d_atelier(self, nom="donnees"):
        """Base au format 3 : parametres, equipements, acces/ (comptes, sessions, clé privée), deux documents, un
        fichier temporaire caché et un sous-dossier dans documents/."""
        donnees = self.racine / nom
        (donnees / "acces").mkdir(parents=True)
        (donnees / "documents" / "sous-dossier").mkdir(parents=True)
        (donnees / "parametres.csv").write_bytes(csv_de("parametres", "version_schema;'3", "entreprise_nom;Atelier"))
        (donnees / "equipements.csv").write_bytes(csv_de("equipements", "EQ-0001;'PO-01;Pompe"))
        (donnees / "acces" / "comptes.json").write_bytes(COMPTES_JSON)
        (donnees / "acces" / "sessions.json").write_bytes(SESSIONS_JSON)
        (donnees / "acces" / "cle.pem").write_bytes(b"-----BEGIN PRIVATE KEY-----\nessai\n")
        (donnees / "documents" / "20260601-080000-pompe.jpg").write_bytes(PHOTO)
        (donnees / "documents" / "rapport.pdf").write_bytes(RAPPORT)
        (donnees / "documents" / ".rapport.pdf.x1.tmp").write_bytes(b"ecriture en cours")
        (donnees / "documents" / "sous-dossier" / "cache.txt").write_bytes(b"jamais copie")
        return donnees

    def verifier_manifeste(self, dossier_sauvegarde, motif, format_, date=None, complement=None):
        """Manifeste exact : champs et ordre de Formats.manifeste, valeurs, fichiers recalculés par hashlib."""
        manifeste = lire_manifeste(dossier_sauvegarde)
        champs = list(CHAMPS_DU_MANIFESTE)
        if complement:
            champs[-1:-1] = list(complement)
        self.assertEqual(list(manifeste), champs, dossier_sauvegarde.name)
        self.assertEqual(manifeste["application"], "Prévo")
        self.assertEqual(manifeste["version_appli"], SERVEUR.VERSION_APPLICATION)
        self.assertEqual((manifeste["format"], manifeste["motif"], manifeste["mode"]), (format_, motif, "serveur"))
        self.assertRegex(manifeste["date"], MOTIF_DATE_ISO)
        if date is not None:
            self.assertEqual(manifeste["date"], date)
        for cle, valeur in (complement or {}).items():
            self.assertEqual(manifeste[cle], valeur, cle)
        self.assertEqual(manifeste["fichiers"], fichiers_attendus(dossier_sauvegarde))
        self.assertEqual([f["nom"] for f in manifeste["fichiers"]], sorted(f["nom"] for f in manifeste["fichiers"]))
        self.assertNotIn("manifeste.json", [f["nom"] for f in manifeste["fichiers"]])
        return manifeste


# ---------------------------------------------------------------------------
# Rotation des quotidiennes (30 jours)
# ---------------------------------------------------------------------------

class TestRotation(CasDossier):

    AUJOURD_HUI = datetime.date(2026, 6, 15)
    # « avant-… » et manuelles très anciennes, noms étrangers : jamais touchés par la rotation.
    AUTRES = ["2025-01-02_101010_avant-format-v3", "2025-01-02_101011_avant-import",
              "2025-01-02_101012_avant-restauration", "2025-01-02_101013_avant-import-zip",
              "2025-01-02_101014_avant-mise-a-jour", "2025-01-03_080000", "2026-13-45", "2025-02-30",
              "2025-01-04-copie", "Mes sauvegardes"]

    def preparer(self):
        donnees = self.donnees_d_atelier()
        sauvegardes = donnees / "sauvegardes"
        sauvegardes.mkdir()
        for nom in self.AUTRES:
            (sauvegardes / nom).mkdir()
            (sauvegardes / nom / "parametres.csv").write_bytes(csv_de("parametres", "entreprise_nom;" + nom))
        (sauvegardes / "2025-01-05").write_bytes(b"un fichier au nom de date")
        return donnees

    def quotidienne(self, donnees, jours, aujourd_hui=None):
        """Fausse sauvegarde quotidienne vieille de « jours » jours ; rend son nom."""
        nom = ((aujourd_hui or self.AUJOURD_HUI) - datetime.timedelta(days=jours)).isoformat()
        dossier = donnees / "sauvegardes" / nom
        dossier.mkdir(parents=True)
        (dossier / "parametres.csv").write_bytes(csv_de("parametres", "entreprise_nom;Jour " + nom))
        return nom

    def test_a_la_premiere_ecriture_du_jour_plus_de_30_jours_supprimees_rien_d_autre(self):
        donnees = self.preparer()
        gardees = [self.quotidienne(donnees, jours) for jours in (10, 29, 30)]
        supprimees = [self.quotidienne(donnees, jours) for jours in (31, 45)]
        serveur = ServeurDansLeProcessus(donnees, instant(2026, 6, 15, 9, 0))
        self.addCleanup(serveur.arreter)
        serveur.ecrire_parametres("Matin")
        attendus = sorted(gardees + self.AUTRES + ["2025-01-05", "2026-06-15"])
        self.assertEqual(noms_des_sauvegardes(donnees), attendus)
        for nom in self.AUTRES:                                  # intactes, contenu compris
            self.assertIn(nom.encode("utf-8"), (donnees / "sauvegardes" / nom / "parametres.csv").read_bytes(), nom)
        self.assertEqual((donnees / "sauvegardes" / "2025-01-05").read_bytes(), b"un fichier au nom de date")
        self.assertTrue(all(nom not in noms_des_sauvegardes(donnees) for nom in supprimees))

        # Deuxième écriture du jour : pas de nouvelle quotidienne, donc aucune rotation.
        remise = self.quotidienne(donnees, 31)
        serveur.instant = instant(2026, 6, 15, 17, 0)
        serveur.ecrire_parametres("Soir")
        self.assertIn(remise, noms_des_sauvegardes(donnees))

        # Le lendemain : nouvelle quotidienne ; 30 jours la veille = 31 jours ce jour-là : supprimée.
        serveur.instant = instant(2026, 6, 16, 8, 0)
        serveur.ecrire_parametres("Lendemain")
        self.assertEqual(noms_des_sauvegardes(donnees),
                         sorted(gardees[:2] + self.AUTRES + ["2025-01-05", "2026-06-15", "2026-06-16"]))

    def test_au_demarrage_horloge_simulee(self):
        donnees = self.preparer()
        gardees = [self.quotidienne(donnees, jours) for jours in (10, 29)]
        for jours in (31, 45):
            self.quotidienne(donnees, jours)
        (donnees / "derniere-version.json").write_text(json.dumps({"version": SERVEUR.VERSION_APPLICATION}),
                                                       encoding="utf-8")
        config = SERVEUR.Configuration(str(donnees), [])
        config.horloge = lambda: instant(2026, 6, 15, 7, 30)
        SERVEUR.creer_dossiers(config)
        SERVEUR.preparer_donnees_au_demarrage(config)
        self.assertEqual(noms_des_sauvegardes(donnees), sorted(gardees + self.AUTRES + ["2025-01-05", "2026-06-15"]))
        # Celle du jour existe déjà : un autre démarrage le même jour ne supprime rien (pas de nouvelle quotidienne).
        vieille = self.quotidienne(donnees, 60)
        SERVEUR.preparer_donnees_au_demarrage(config)
        self.assertIn(vieille, noms_des_sauvegardes(donnees))

    def test_au_demarrage_du_serveur_reel(self):
        source = self.preparer()
        aujourd_hui = datetime.date.today()
        gardees = [self.quotidienne(source, jours, aujourd_hui) for jours in (10, 29)]
        supprimees = [self.quotidienne(source, jours, aujourd_hui) for jours in (31, 45)]
        with commun.ServeurPrevo(source=source) as serveur:
            noms = noms_des_sauvegardes(serveur.dossier)
        # Pas de derniere-version.json : une sauvegarde « avant-mise-a-jour » de plus, faite à ce démarrage.
        mise_a_jour = une_seule([nom for nom in noms if nom not in self.AUTRES], "_avant-mise-a-jour")
        self.assertEqual(noms, sorted(gardees + self.AUTRES + ["2025-01-05", aujourd_hui.isoformat(), mise_a_jour]))
        self.assertFalse(set(supprimees) & set(noms))


# ---------------------------------------------------------------------------
# Sauvegarde « avant-mise-a-jour » au démarrage
# ---------------------------------------------------------------------------

class TestAvantMiseAJour(CasDossier):

    def premier_demarrage(self, nom_jeu, ajouts_au_format_3):
        """Premier démarrage du serveur réel sur une copie du jeu, sans derniere-version.json ; contrôles communs.
        Rend la copie du dossier de données après ce démarrage."""
        source = copier_jeu(nom_jeu, self.racine / nom_jeu / "donnees")
        origine = fichiers_de(source)
        self.assertNotIn("derniere-version.json", origine)
        with commun.ServeurPrevo(source=source) as serveur:
            copie = self.racine / nom_jeu / "apres"
            shutil.copytree(serveur.dossier, copie)
            console = serveur.sortie_console()
        apres = fichiers_de(copie)
        noms = noms_des_sauvegardes(copie)
        aujourd_hui = datetime.date.today().isoformat()
        # 1. La sauvegarde « avant-mise-a-jour », aux octets d'ORIGINE (avant tout passage de format).
        mise_a_jour = une_seule(noms, "_avant-mise-a-jour")
        contenu = fichiers_de(copie / "sauvegardes" / mise_a_jour)
        del contenu["manifeste.json"]
        self.assertEqual(contenu, origine)
        format_d_origine = 2 if ajouts_au_format_3 else 3
        self.verifier_manifeste(copie / "sauvegardes" / mise_a_jour, "avant-mise-a-jour", format_d_origine,
                                complement={"de": None, "vers": SERVEUR.VERSION_APPLICATION})
        self.assertIn("sauvegarde %s faite avant la mise à jour" % mise_a_jour, console)
        # derniere-version.json : la version courante, depuis maintenant.
        notee = json.loads((copie / "derniere-version.json").read_text(encoding="utf-8"))
        self.assertEqual(list(notee), ["version", "depuis"])
        self.assertEqual(notee["version"], SERVEUR.VERSION_APPLICATION)
        self.assertRegex(notee["depuis"], MOTIF_DATE_ISO)
        self.assertEqual(notee["depuis"][:10], aujourd_hui)
        # 2. Le passage au format 3 (T185), ou rien pour un jeu déjà au format 3.
        format_v3 = [nom for nom in noms if nom.endswith("_avant-format-v3")]
        self.assertEqual(len(format_v3), 1 if ajouts_au_format_3 else 0, noms)
        if ajouts_au_format_3:
            self.assertLess(console.index(mise_a_jour), console.index("Format des données"))
            self.assertNotEqual(apres["ordres_travail.csv"], origine["ordres_travail.csv"])
        else:
            self.assertEqual(csv_a_la_racine(apres), origine)
        # 3. La sauvegarde du jour, faite APRÈS le passage : les CSV tels qu'ils sont maintenant.
        self.assertIn(aujourd_hui, noms)
        quotidienne = fichiers_de(copie / "sauvegardes" / aujourd_hui)
        del quotidienne["manifeste.json"]
        self.assertEqual(quotidienne, csv_a_la_racine(apres))
        self.verifier_manifeste(copie / "sauvegardes" / aujourd_hui, "quotidienne", 3)
        self.assertEqual(sorted(noms), sorted([aujourd_hui, mise_a_jour] + format_v3))
        return copie

    def test_f2_premier_demarrage_puis_second_sans_effet(self):
        copie = self.premier_demarrage("f2-v1.1.0", ajouts_au_format_3=True)
        avant_second = fichiers_de(copie)
        with commun.ServeurPrevo(source=copie) as second:
            self.assertEqual(fichiers_de(second.dossier), avant_second)       # ni sauvegarde, ni fichier réécrit

    def test_f3_premier_demarrage_sans_passage_de_format(self):
        self.premier_demarrage("f3-v1.2.0", ajouts_au_format_3=False)

    def test_autre_version_notee_nouvelle_sauvegarde_meme_version_aucune(self):
        source = copier_jeu("f3-v1.2.0", self.racine / "autre" / "donnees")
        (source / "derniere-version.json").write_text(
            json.dumps({"version": "1.2.0", "depuis": "2025-03-01T08:00:00"}), encoding="utf-8")
        with commun.ServeurPrevo(source=source) as serveur:
            noms = noms_des_sauvegardes(serveur.dossier)
            mise_a_jour = une_seule(noms, "_avant-mise-a-jour")
            self.verifier_manifeste(serveur.dossier / "sauvegardes" / mise_a_jour, "avant-mise-a-jour", 3,
                                    complement={"de": "1.2.0", "vers": SERVEUR.VERSION_APPLICATION})
            notee = json.loads((serveur.dossier / "derniere-version.json").read_text(encoding="utf-8"))
            self.assertEqual(notee["version"], SERVEUR.VERSION_APPLICATION)
        # La version courante déjà notée : aucune sauvegarde « avant-mise-a-jour » (la quotidienne, oui).
        source = copier_jeu("f3-v1.2.0", self.racine / "meme" / "donnees")
        meme = json.dumps({"version": SERVEUR.VERSION_APPLICATION, "depuis": "2026-01-01T08:00:00"}).encode("utf-8")
        (source / "derniere-version.json").write_bytes(meme)
        with commun.ServeurPrevo(source=source) as serveur:
            self.assertEqual(noms_des_sauvegardes(serveur.dossier), [datetime.date.today().isoformat()])
            self.assertEqual((serveur.dossier / "derniere-version.json").read_bytes(), meme)

    def test_base_vide_rien(self):
        with commun.ServeurPrevo(source=None) as serveur:
            self.assertEqual(noms_des_sauvegardes(serveur.dossier), [])
            self.assertFalse((serveur.dossier / "derniere-version.json").exists())

    def test_lecture_seule_sauvegardes_faites_donnees_intactes(self):
        source = copier_jeu("plus-recent", self.racine / "plus-recent" / "donnees")
        origine = fichiers_de(source)
        with commun.ServeurPrevo(source=source) as serveur:
            noms = noms_des_sauvegardes(serveur.dossier)
            mise_a_jour = une_seule(noms, "_avant-mise-a-jour")
            self.assertIn(datetime.date.today().isoformat(), noms)
            contenu = fichiers_de(serveur.dossier / "sauvegardes" / mise_a_jour)
            del contenu["manifeste.json"]
            # Les tables du schéma, octet pour octet (pieces_v4.csv, table inconnue, n'est pas une table à sauvegarder).
            self.assertEqual(contenu, {chemin: octets for chemin, octets in origine.items()
                                       if chemin[:-len(".csv")] in SERVEUR.TABLES})
            self.assertIn("pieces_v4.csv", origine)
            self.verifier_manifeste(serveur.dossier / "sauvegardes" / mise_a_jour, "avant-mise-a-jour", 4,
                                    complement={"de": None, "vers": SERVEUR.VERSION_APPLICATION})
            self.assertEqual(csv_a_la_racine(fichiers_de(serveur.dossier)), origine)     # aucune table écrite
            statut, reponse = requete(serveur.port, "PUT", "/api/csv/equipements", origine["equipements.csv"],
                                      {"X-Version-Attendue": "aucune"})
            self.assertEqual((statut, reponse["code"]), (409, "format_plus_recent"))

    def test_fichier_illisible_version_inconnue(self):
        donnees = self.donnees_d_atelier()
        (donnees / "derniere-version.json").write_bytes(b"{pas du json")
        config = SERVEUR.Configuration(str(donnees), [])
        config.horloge = lambda: instant(2026, 6, 15, 7, 30, 5)
        SERVEUR.creer_dossiers(config)
        nom = SERVEUR.sauvegarder_avant_mise_a_jour(config)
        self.assertEqual(nom, "2026-06-15_073005_avant-mise-a-jour")
        self.verifier_manifeste(donnees / "sauvegardes" / nom, "avant-mise-a-jour", 3, date="2026-06-15T07:30:05",
                                complement={"de": None, "vers": SERVEUR.VERSION_APPLICATION})
        self.assertEqual(json.loads((donnees / "derniere-version.json").read_text(encoding="utf-8")),
                         {"version": SERVEUR.VERSION_APPLICATION, "depuis": "2026-06-15T07:30:05"})
        self.assertIsNone(SERVEUR.sauvegarder_avant_mise_a_jour(config))             # notée : rien de plus
        self.assertEqual(noms_des_sauvegardes(donnees), [nom])

    def test_sauvegarde_impossible_message_et_rien_d_autre(self):
        donnees = self.donnees_d_atelier()
        (donnees / "sauvegardes").write_bytes(b"un fichier a la place du dossier des sauvegardes")
        origine = fichiers_de(donnees)
        config = SERVEUR.Configuration(str(donnees), [])
        self.assertIsNone(SERVEUR.sauvegarder_avant_mise_a_jour(config))
        self.assertEqual(fichiers_de(donnees), origine)                              # derniere-version.json absent
        self.assertTrue(any("sauvegarde « avant-mise-a-jour » impossible" in ligne and "prochain démarrage" in ligne
                            for ligne in self.console), self.console)
        # Au démarrage complet, l'échec de la sauvegarde du jour est dit aussi, sans arrêter le serveur.
        SERVEUR.preparer_donnees_au_demarrage(config)
        self.assertEqual(fichiers_de(donnees), origine)
        self.assertTrue(any("sauvegarde du jour impossible au démarrage" in ligne for ligne in self.console),
                        self.console)


# ---------------------------------------------------------------------------
# Manifeste, documents de « avant-import-zip », motifs
# ---------------------------------------------------------------------------

class TestManifesteEtDocuments(CasDossier):

    def setUp(self):
        super().setUp()
        self.donnees = self.donnees_d_atelier()
        self.serveur = ServeurDansLeProcessus(self.donnees, instant(2026, 6, 15, 10, 0, 0))
        self.addCleanup(self.serveur.arreter)

    def sauvegarder(self, motif=None):
        corps = {"motif": motif} if motif else None
        statut, reponse = self.serveur.requete("POST", "/api/sauvegarde", corps)
        self.assertEqual(statut, 200, reponse)
        return reponse["sauvegarde"]

    def test_manifeste_exact_dans_chaque_sauvegarde(self):
        s = self.serveur
        s.ecrire_parametres("Atelier modifié")                  # la quotidienne d'abord, à l'état d'avant
        quotidienne = self.donnees / "sauvegardes" / "2026-06-15"
        self.verifier_manifeste(quotidienne, "quotidienne", 3, date="2026-06-15T10:00:00")
        self.assertIn(b"entreprise_nom;Atelier\r\n", (quotidienne / "parametres.csv").read_bytes())
        s.instant += 1
        manuelle = self.sauvegarder()
        self.assertEqual(manuelle, "2026-06-15_100001")
        manifeste = self.verifier_manifeste(self.donnees / "sauvegardes" / manuelle, "manuelle", 3,
                                            date="2026-06-15T10:00:01")
        self.assertEqual([f["nom"] for f in manifeste["fichiers"]],
                         ["acces/comptes.json", "equipements.csv", "parametres.csv"])     # ni sessions, ni clé
        for motif in ("avant-format-v3", "avant-import", "avant-mise-a-jour"):
            s.instant += 1
            nom = self.sauvegarder(motif)
            self.verifier_manifeste(self.donnees / "sauvegardes" / nom, motif, 3)
            self.assertFalse((self.donnees / "sauvegardes" / nom / "documents").exists(), motif)
        self.assertFalse((quotidienne / "documents").exists())
        self.assertFalse((self.donnees / "sauvegardes" / manuelle / "documents").exists())
        # Copie de sécurité d'une restauration : son manifeste aussi.
        s.instant += 60
        statut, reponse = s.requete("POST", "/api/restauration", {"sauvegarde": manuelle})
        self.assertEqual(statut, 200, reponse)
        self.verifier_manifeste(self.donnees / "sauvegardes" / reponse["copie_securite"], "avant-restauration", 3)
        # Aucun dossier temporaire laissé.
        self.assertEqual([nom for nom in noms_des_sauvegardes(self.donnees) if nom.startswith(".")], [])

    def test_avant_import_zip_copie_les_documents_et_les_compte(self):
        nom = self.sauvegarder("avant-import-zip")
        self.assertEqual(nom, "2026-06-15_100000_avant-import-zip")
        sauvegarde = self.donnees / "sauvegardes" / nom
        self.assertEqual(sorted(p.name for p in (sauvegarde / "documents").iterdir()),
                         ["20260601-080000-pompe.jpg", "rapport.pdf"])             # ni caché, ni sous-dossier
        self.assertEqual((sauvegarde / "documents" / "20260601-080000-pompe.jpg").read_bytes(), PHOTO)
        self.assertEqual((sauvegarde / "documents" / "rapport.pdf").read_bytes(), RAPPORT)
        manifeste = self.verifier_manifeste(sauvegarde, "avant-import-zip", 3, date="2026-06-15T10:00:00")
        self.assertEqual([f["nom"] for f in manifeste["fichiers"]],
                         ["acces/comptes.json", "documents/20260601-080000-pompe.jpg", "documents/rapport.pdf",
                          "equipements.csv", "parametres.csv"])
        photo = next(f for f in manifeste["fichiers"] if f["nom"].endswith("pompe.jpg"))
        self.assertEqual((photo["octets"], photo["sha256"]), (len(PHOTO), hashlib.sha256(PHOTO).hexdigest()))
        # Les documents du dossier de données sont restés en place.
        self.assertEqual((self.donnees / "documents" / "rapport.pdf").read_bytes(), RAPPORT)

    def test_restauration_et_tester_ignorent_le_manifeste(self):
        nom = self.sauvegarder("avant-import-zip")
        sauvegarde = self.donnees / "sauvegardes" / nom
        self.assertTrue((sauvegarde / "manifeste.json").is_file())
        statut, liste = self.serveur.requete("GET", "/api/sauvegardes")
        self.assertEqual(statut, 200, liste)
        self.assertIn({"nom": nom, "tables": ["equipements", "parametres"]}, liste["sauvegardes"])
        statut, test = self.serveur.requete("POST", "/api/sauvegarde/tester", {"nom": nom})
        self.assertEqual(statut, 200, test)
        self.assertEqual(test, {"nom": nom, "ok": True, "tables": [
            {"table": "equipements", "lignes": 1, "erreur": None},
            {"table": "parametres", "lignes": 2, "erreur": None}]})
        (self.donnees / "equipements.csv").write_bytes(csv_de("equipements", "EQ-0002;'PO-02;Compresseur"))
        self.serveur.instant += 60
        statut, reponse = self.serveur.requete("POST", "/api/restauration", {"sauvegarde": nom})
        self.assertEqual(statut, 200, reponse)
        self.assertEqual(reponse["restaurees"], ["equipements", "parametres"])
        self.assertEqual((self.donnees / "equipements.csv").read_bytes(), csv_de("equipements", "EQ-0001;'PO-01;Pompe"))
        self.assertFalse((self.donnees / "manifeste.json").exists())
        self.assertFalse((self.donnees / "documents" / "documents").exists())

    def test_motif_inconnu_toujours_refuse_rien_de_cree(self):
        avant = noms_des_sauvegardes(self.donnees)
        for motif in ("avant-tout", "quotidienne", "manuelle", "avant-restauration", "avant-import-zip/../x",
                      "AVANT-IMPORT-ZIP", "avant-mise-a-jour ", "avant-format-v9", 5, ["avant-import-zip"]):
            with self.subTest(motif=motif):
                statut, reponse = self.serveur.requete("POST", "/api/sauvegarde", {"motif": motif})
                self.assertEqual(statut, 400, reponse)
                self.assertIn("Motif de sauvegarde refusé", reponse["erreur"])
        self.assertEqual(noms_des_sauvegardes(self.donnees), avant)


class TestMotifs(unittest.TestCase):

    MOTIFS = ("avant-format-v2", "avant-format-v3", "avant-import", "avant-import-zip", "avant-mise-a-jour")

    def test_liste_fermee_et_noms(self):
        self.assertEqual(SERVEUR.MOTIFS_SAUVEGARDE, self.MOTIFS)
        for nom in ("2026-11-04", "2026-11-04_093000", "2026-11-04_093000_avant-restauration",
                    "2026-11-04_093000_avant-format-v3", "2026-11-04_093000_avant-import",
                    "2026-11-04_093000_avant-import-zip", "2026-11-04_093000_avant-mise-a-jour"):
            with self.subTest(nom=nom):
                self.assertTrue(SERVEUR.MOTIF_NOM_SAUVEGARDE.fullmatch(nom))
        for nom in ("2026-11-04_avant-import-zip", "2026-11-04_093000_avant-import-zip2",
                    "2026-11-04_093000_avant-mise-a-jour/..", "2026-11-04_093000_avant-mise", "2026-11-04_093000_",
                    "../2026-11-04", "2026-11-04_093000_avant-import-zip_avant-import"):
            with self.subTest(nom=nom):
                self.assertIsNone(SERVEUR.MOTIF_NOM_SAUVEGARDE.fullmatch(nom))

    def test_memes_motifs_dans_le_mode_dossier(self):
        lignes = (RACINE / "js" / "stockage-dossier.js").read_text(encoding="utf-8").splitlines()

        def ligne(debut):
            trouvees = [texte for texte in lignes if texte.startswith(debut)]
            self.assertEqual(len(trouvees), 1, debut)
            return trouvees[0]

        nom_js = ligne("  const MOTIF_NOM_SAUVEGARDE = ")
        self.assertEqual(nom_js, "  const MOTIF_NOM_SAUVEGARDE = /^\\d{4}-\\d{2}-\\d{2}(_\\d{6}(_avant-restauration"
                                 "|_avant-format-v\\d+|_avant-import-zip|_avant-import|_avant-mise-a-jour)?)?$/;")
        self.assertEqual(ligne("  const MOTIFS_SAUVEGARDE = "),
                         "  const MOTIFS_SAUVEGARDE = [%s];" % ", ".join("'%s'" % m for m in self.MOTIFS))
        # Même motif de nom des deux côtés (\d du JavaScript = [0-9] du serveur).
        motif_js = re.search(r"/\^(.*)\$/;", nom_js).group(1).replace("\\d", "[0-9]")
        self.assertEqual(motif_js, SERVEUR.MOTIF_NOM_SAUVEGARDE.pattern)


if __name__ == "__main__":
    unittest.main()
