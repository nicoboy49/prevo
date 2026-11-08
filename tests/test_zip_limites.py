"""T208 — tout ce que Prévo exporte, Prévo peut le réimporter (règle de Nicolas, 04/11/2026) : les limites de l'import
ZIP sont écrites à un seul endroit (LIMITES de js/modules/zip-lecture.js), serveur.py suit celles qui le concernent, et
l'export (js/modules/zip-donnees.js) les contrôle AVANT de produire le ZIP.

    un seul endroit  serveur.py : TAILLE_MAX_CORPS_CSV et TAILLE_MAX_CELLULE_CSV = LIMITES.racine (50 Mo),
                     TAILLE_MAX_CORPS = LIMITES.document (10 Mo) ; zip-donnees.js ne recopie aucune limite et les
                     messages de zip-lecture.js les tirent de LIMITES ; T229 (décisions de Nicolas du 05/11) :
                     LIMITES.zip = ZipFlux.LIMITES.octets (4 Go sans ZIP64), 4 Go décompressés, 10 000 entrées ;
    serveur          envoi d'une table (PUT csv/<table>, POST csv/<table>/ajout) : 11 Mo (ordres_travail.csv de
                     20 000 OT) et 12 Mo d'ajout au journal acceptés, 50 Mo annoncés lus (corps incomplet : 400, pas
                     413), 50 Mo et un octet refusés (413) ; documents et autres routes : toujours 10 Mo (audit F2) ;
    calcul           ZipDonnees.depassements : rien aux limites exactes ; un octet de trop (CSV, document, total),
                     une entrée de trop, des photos qui feraient un ZIP trop gros (depuis T229, toujours avec le total
                     décompressé) : la phrase qui dit quoi (fichier, taille, limite) ;
    aller-retour     grosse base proche des limites : jeu de charge (outils/generer_demo.py --volume 500,20000 :
                     ordres_travail.csv de 11 Mo), journal grossi à 45 Mo (5 ans), 49 Mo de documents fictifs
                     incompressibles (30 photos, 7 PDF dont un de 10 Mo pile) ; serveur : export (vrai bouton) puis
                     import dans une autre base, CSV et documents comparés à l'octet (noms rendus par le serveur remis,
                     journal : la ligne de l'import en plus) ; dossier : import du même ZIP, export, puis réimport de
                     cet export, comparés de même (empreintes SHA-256 de l'OPFS) ;
    refus            document de 10 Mo et un octet : fenêtre « Export ZIP impossible » qui le nomme, aucun ZIP construit
                     ni téléchargé ; ZIP trop gros (limite abaissée dans la page) : refusé avant d'être construit quand
                     les photos suffisent à le dire, sinon après, toujours sans téléchargement.

Règle numéro un : jamais de données réelles (jeu de charge et documents fictifs, dossiers temporaires, OPFS du
navigateur de test).

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_zip_limites.py" -v
"""
import codecs
import hashlib
import http.client
import importlib.util
import random
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from commun import (RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret, charger_scripts,
                    installer_dossier_simule, preregler_profil)
import test_zip_import as tzi

MIO = 1024 * 1024
BOM = codecs.BOM_UTF8
TABLES = tzi.TABLES                                             # les 24 tables du format 3
ZIP_LECTURE = RACINE / "js" / "modules" / "zip-lecture.js"
ZIP_FLUX = RACINE / "js" / "modules" / "zip-flux.js"
ZIP_DONNEES = RACINE / "js" / "modules" / "zip-donnees.js"
GENERATEUR = RACINE / "outils" / "generer_demo.py"
NOM_DOSSIER = "donnees-zip-limites"
LONG_MS = 300000                                                # gros volumes : 5 minutes au plus par étape


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_t208", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


SERVEUR = charger_serveur()


def octets_max_zip_flux():
    """ZipFlux.LIMITES.octets (js/modules/zip-flux.js), lue dans le fichier : « octets: MAX_32 - N »."""
    texte = ZIP_FLUX.read_text(encoding="utf-8")
    max_32 = re.search(r"const MAX_32 = (0x[0-9A-Fa-f]+);", texte)
    moins = re.search(r"const LIMITES = Object\.freeze\(\{ octets: MAX_32 - (\d+),", texte)
    if max_32 is None or moins is None:
        raise AssertionError("LIMITES.octets introuvable dans zip-flux.js")
    return int(max_32.group(1), 16) - int(moins.group(1))


def limites_js():
    """{nom: valeur} de LIMITES (js/modules/zip-lecture.js), lues dans le fichier : « nom: N * MO, », « nom: N, » ou
    « nom: ZipFlux.LIMITES.octets, » (T229 : la taille du ZIP)."""
    texte = ZIP_LECTURE.read_text(encoding="utf-8")
    bloc = re.search(r"const LIMITES = Object\.freeze\(\{(.*?)\}\);", texte, re.S)
    if bloc is None:
        raise AssertionError("LIMITES introuvable dans zip-lecture.js")
    limites = {nom: int(nombre) * (MIO if fois_mo else 1)
               for nom, nombre, fois_mo in re.findall(r"^\s*(\w+): (\d+)( \* MO)?,", bloc.group(1), re.M)}
    limites.update({nom: octets_max_zip_flux()
                    for nom in re.findall(r"^\s*(\w+): ZipFlux\.LIMITES\.octets,", bloc.group(1), re.M)})
    return limites


LIMITES = limites_js()


def sha256(octets):
    return hashlib.sha256(octets).hexdigest()


def octets_fictifs(taille, graine, signature=b""):
    """Contenu incompressible et reproductible (aucune donnée réelle), précédé d'une signature de format."""
    return signature + random.Random(graine).randbytes(taille - len(signature))


# ---------------------------------------------------------------------------
# Grosse base proche des limites
# ---------------------------------------------------------------------------

JOURNAL_VISE = LIMITES["racine"] - 5 * MIO                    # 45 Mo : sous la limite d'un CSV, bien au-delà de 10 Mo
ACTIONS = ("modification : statut — statut En cours → Clôturé technique",
           "modification : statut, date_debut — statut Planifié → En cours",
           "création — acceptation de la demande signalée par l'atelier",
           "modification : compte_rendu — intervention terminée, pièce changée, essai concluant",
           "modification : statut, date_cloture_admin — statut Clôturé technique → Clôturé")


def lignes_de_journal(debut, nombre):
    """Lignes du journal au format de Prévo (identifiant J-AAAAMMJJHHMMSS-XXXX unique), sur cinq ans environ."""
    instant0 = datetime(2021, 1, 4, 7, 0, 0)
    for rang in range(debut, debut + nombre):
        instant = instant0 + timedelta(seconds=rang * 557)
        yield ("J-%s-%04X;%s;Poste atelier %d;Technicien %d;ordres_travail;OT-%d-%04d;%s" % (
            instant.strftime("%Y%m%d%H%M%S"), rang % 65536, instant.strftime("%Y-%m-%d %H:%M"), rang % 4 + 1,
            rang % 12 + 1, instant.year, rang % 9999 + 1, ACTIONS[rang % len(ACTIONS)])).encode("utf-8")


def grossir_journal(octets, taille_visee):
    if not octets.endswith(b"\r\n"):
        octets += b"\r\n"
    morceaux, taille, rang = [octets], len(octets), 0
    while taille < taille_visee:
        for ligne in lignes_de_journal(rang, 1000):
            morceaux.append(ligne + b"\r\n")
            taille += len(ligne) + 2
        rang += 1000
    return b"".join(morceaux)


def cellules_brutes(ligne):
    """Cellules d'une ligne CSV telles qu'écrites (guillemets compris), ou None si un guillemet reste ouvert."""
    cellules, debut, entre_guillemets = [], 0, False
    for position, caractere in enumerate(ligne):
        if caractere == '"':
            entre_guillemets = not entre_guillemets
        elif caractere == ";" and not entre_guillemets:
            cellules.append(ligne[debut:position])
            debut = position + 1
    return None if entre_guillemets else cellules + [ligne[debut:]]


def poser_documents(octets, colonne, noms):
    """Cite les noms dans `colonne`, une par ligne, sur les premières lignes complètes dont la cellule est vide : les
    autres cellules gardent leurs octets (le CSV reste celui que Prévo écrirait)."""
    lignes = octets[len(BOM):].decode("utf-8").split("\r\n")
    entete = lignes[0].split(";")
    position = entete.index(colonne)
    restants = list(noms)
    for rang in range(1, len(lignes)):
        if not restants:
            break
        cellules = cellules_brutes(lignes[rang])
        if cellules is None or len(cellules) != len(entete) or cellules[position]:
            continue
        cellules[position] = restants.pop(0)
        lignes[rang] = ";".join(cellules)
    if restants:
        raise AssertionError("pas assez de lignes pour citer les documents dans %s" % colonne)
    return BOM + "\r\n".join(lignes).encode("utf-8")


def documents_de_la_grosse_base():
    """49 Mo de documents fictifs : 30 photos de 1 Mo (JPEG), 4 notices (dont une de 10 Mo pile, la limite d'un
    document), 3 rapports de contrôle."""
    photos = {"photo-di-%05d.jpg" % n: octets_fictifs(MIO, "photo-%d" % n, b"\xff\xd8\xff\xe0") for n in range(30)}
    notices = {"notice-eq-%04d.pdf" % n: octets_fictifs(LIMITES["document"] if n == 0 else 2 * MIO, "notice-%d" % n,
                                                       b"%PDF-1.4\n") for n in range(4)}
    rapports = {"rapport-ctrl-%03d.pdf" % n: octets_fictifs(MIO, "rapport-%d" % n, b"%PDF-1.4\n") for n in range(3)}
    return photos, notices, rapports


def ecrire_dossier(dossier, fichiers):
    for chemin, octets in fichiers.items():
        (dossier / chemin).parent.mkdir(parents=True, exist_ok=True)
        (dossier / chemin).write_bytes(octets)
    return dossier


def grosse_base(dossier):
    """{chemin: octets} de la grosse base (24 CSV et documents/), écrite aussi dans `dossier`."""
    charge = Path(tempfile.mkdtemp(prefix="prevo-charge-"))
    try:
        subprocess.run([sys.executable, "-X", "utf8", str(GENERATEUR), "--volume", "500,20000", "--sortie", str(charge)],
                       check=True, capture_output=True, cwd=str(RACINE), timeout=600)
        fichiers = {table + ".csv": (charge / (table + ".csv")).read_bytes() for table in TABLES}
    finally:
        shutil.rmtree(charge, ignore_errors=True)
    photos, notices, rapports = documents_de_la_grosse_base()
    fichiers["journal.csv"] = grossir_journal(fichiers["journal.csv"], JOURNAL_VISE)
    fichiers["demandes.csv"] = poser_documents(fichiers["demandes.csv"], "photo", sorted(photos))
    fichiers["equipements.csv"] = poser_documents(fichiers["equipements.csv"], "document", sorted(notices))
    fichiers["controles_reglementaires.csv"] = poser_documents(fichiers["controles_reglementaires.csv"], "rapport",
                                                               sorted(rapports))
    for documents in (photos, notices, rapports):
        fichiers.update({"documents/" + nom: octets for nom, octets in documents.items()})
    ecrire_dossier(dossier, fichiers)
    return fichiers


def entrees_zip(chemin):
    with zipfile.ZipFile(chemin) as archive:
        return {nom: archive.read(nom) for nom in archive.namelist()}


def documents_de(entrees):
    return {nom[len("documents/"):]: octets for nom, octets in entrees.items() if nom.startswith("documents/")}


def premier_ecart(a, b):
    for position, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return "premier écart à l'octet %d : %r / %r" % (position, a[position:position + 60], b[position:position + 60])
    return "longueurs %d et %d" % (len(a), len(b))


def remettre_noms(octets, rendus):
    """Octets d'un CSV où chaque nom de document du ZIP est remplacé par le nom rendu à l'import ({zip: rendu})."""
    changes = {nom: rendu for nom, rendu in rendus.items() if nom != rendu}
    if not changes:
        return octets
    motif = re.compile(b"|".join(re.escape(nom.encode()) for nom in sorted(changes, key=len, reverse=True)))
    return motif.sub(lambda trouve: changes[trouve.group(0).decode()].encode(), octets)


TABLES_A_DOCUMENTS = ("equipements", "demandes", "controles_reglementaires", "parametres")

EMPREINTES_OPFS_JS = """async ([nom, debuts]) => {
  // {chemin: {taille, sha256}} du dossier de l'OPFS (sans sauvegardes/) ; pour un chemin de `debuts` ({chemin: n}),
  // aussi l'empreinte de ses n premiers octets et la suite en texte (la ligne de journal de l'import).
  const hex = (tampon) => Array.from(new Uint8Array(tampon), (o) => o.toString(16).padStart(2, '0')).join('');
  const resultat = {};
  async function parcourir(dossier, prefixe) {
    for await (const entree of dossier.values()) {
      const chemin = prefixe + entree.name;
      if (entree.kind === 'directory') { if (chemin !== 'sauvegardes') await parcourir(entree, chemin + '/'); continue; }
      const octets = new Uint8Array(await (await entree.getFile()).arrayBuffer());
      const decrit = { taille: octets.length, sha256: hex(await crypto.subtle.digest('SHA-256', octets)) };
      if (chemin in debuts) {
        decrit.debut = hex(await crypto.subtle.digest('SHA-256', octets.subarray(0, debuts[chemin])));
        decrit.suite = new TextDecoder().decode(octets.subarray(debuts[chemin]));
      }
      resultat[chemin] = decrit;
    }
  }
  await parcourir(await (await navigator.storage.getDirectory()).getDirectoryHandle(nom), '');
  return resultat;
}"""

ESPION_ZIP_JS = """() => {
  window.__telechargements = 0;
  window.__generations = 0;                                    // ZIP écrits (T228 : ZipFlux, terminer)
  const creer = ZipFlux.ecrivain;
  ZipFlux.ecrivain = function () {
    const ecrivain = creer.apply(this, arguments);
    const terminer = ecrivain.terminer;
    ecrivain.terminer = function () { window.__generations += 1; return terminer.apply(this, arguments); };
    return ecrivain;
  };
  const cliquer = HTMLAnchorElement.prototype.click;           // UI est gelé : le lien de UI.telecharger est compté
  HTMLAnchorElement.prototype.click = function () {
    if (this.download) window.__telechargements += 1;
    return cliquer.apply(this, arguments);
  };
}"""


# ---------------------------------------------------------------------------
# 1. Un seul endroit (sans navigateur)
# ---------------------------------------------------------------------------

class TestUnSeulEndroit(unittest.TestCase):

    def test_limites_du_serveur_egales_a_celles_de_l_import(self):
        self.assertEqual(LIMITES["racine"], 50 * MIO)                  # décision de Nicolas (04/11)
        self.assertEqual(SERVEUR.TAILLE_MAX_CORPS_CSV, LIMITES["racine"])
        self.assertEqual(SERVEUR.TAILLE_MAX_CELLULE_CSV, LIMITES["racine"])
        self.assertEqual(SERVEUR.csv.field_size_limit(), LIMITES["racine"])
        self.assertEqual(SERVEUR.TAILLE_MAX_CORPS, LIMITES["document"])
        self.assertEqual(LIMITES["document"], 10 * MIO)                # inchangée : documents et JSON (audit F2)
        self.assertEqual(set(SERVEUR.ROUTES_CORPS_CSV), {("PUT", "csv/<table>"), ("POST", "csv/<table>/ajout")})
        for route in SERVEUR.ROUTES_CORPS_CSV:
            self.assertIn(route, SERVEUR.ROUTES_API)

    def test_limites_decidees_par_nicolas(self):
        # T229 (05/11) : ZIP de 4 Go au plus sans ZIP64 (la limite de l'écrivain de zip-flux.js, lue, pas recopiée),
        # 4 Go décompressés, 10 000 entrées (T212) ; racine et document inchangées (T208).
        self.assertIn("zip: ZipFlux.LIMITES.octets,", ZIP_LECTURE.read_text(encoding="utf-8"))
        self.assertEqual(sorted(LIMITES), ["document", "entrees", "racine", "taux", "total", "zip"])
        self.assertEqual((LIMITES["zip"], LIMITES["total"], LIMITES["entrees"]), (0xFFFFFFFE, 4096 * MIO, 10000))
        self.assertEqual((LIMITES["racine"], LIMITES["document"]), (50 * MIO, 10 * MIO))

    def test_l_export_lit_les_limites_sans_les_recopier(self):
        code = ZIP_DONNEES.read_text(encoding="utf-8")
        self.assertIn("ZipLecture.LIMITES", code)
        self.assertIsNone(re.search(r"\d+\s*\*\s*(1024|MO)\b|\b(400|200|50|10)\s*Mo\b|\b(10 ?000|2 ?000)\b|\b1 ?Go\b"
                                    r"|0x[0-9A-Fa-f]{6,}|\b4096\b|\b4 ?294 ?967", code))

    def test_les_messages_de_l_import_tirent_leurs_nombres_de_limites(self):
        code = ZIP_LECTURE.read_text(encoding="utf-8")
        for fige in ("dépasser 400 Mo", "dépasser 4 Go", "10 Mo au plus", "50 Mo au plus", "1 Go au plus",
                     "4 Go au plus", "10 000 au plus"):
            self.assertFalse(fige in code, fige)


# ---------------------------------------------------------------------------
# 2. Envoi d'une table au serveur (sans navigateur)
# ---------------------------------------------------------------------------

def requete(port, methode, chemin, corps=None, entetes=None, annonce=None, fermer_apres=None):
    """(statut, corps de la réponse). annonce : Content-Length annoncé sans envoyer le corps ; fermer_apres : octets
    envoyés avant de fermer l'envoi (corps incomplet)."""
    if annonce is None:
        connexion = http.client.HTTPConnection("127.0.0.1", port, timeout=120)
        try:
            connexion.request(methode, chemin, body=corps, headers=dict({"X-Prevo": "1"}, **(entetes or {})))
            reponse = connexion.getresponse()
            return reponse.status, reponse.read()
        finally:
            connexion.close()
    lignes = ["%s %s HTTP/1.1" % (methode, chemin), "Host: 127.0.0.1:%d" % port, "X-Prevo: 1",
              "Content-Length: %d" % annonce] + ["%s: %s" % paire for paire in (entetes or {}).items()]
    with socket.create_connection(("127.0.0.1", port), timeout=60) as prise:
        prise.sendall(("\r\n".join(lignes) + "\r\n\r\n").encode("ascii") + (fermer_apres or b""))
        if fermer_apres is not None:
            prise.shutdown(socket.SHUT_WR)
        recu = b""
        while True:                                             # le serveur ferme après ces réponses
            morceau = prise.recv(65536)
            if not morceau:
                break
            recu += morceau
    return int(recu.split(b" ", 2)[1]), recu.split(b"\r\n\r\n", 1)[-1]


class TestEnvoiAuServeur(unittest.TestCase):

    def setUp(self):
        self.serveur = ServeurPrevo(source=None)
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)

    def test_une_table_jusqu_a_50_mo_les_autres_routes_a_10_mo(self):
        port, limite_csv, limite = self.serveur.port, SERVEUR.TAILLE_MAX_CORPS_CSV, SERVEUR.TAILLE_MAX_CORPS
        # ordres_travail.csv de 20 000 OT : 11 Mo environ (lignes de la démo répétées), refusé avant T208.
        demo = (tzi.DOSSIER_DEMO / "ordres_travail.csv").read_bytes()
        entete, _, lignes = demo.partition(b"\r\n")
        corps = entete + b"\r\n" + lignes * (11 * MIO // len(lignes) + 1)
        self.assertGreater(len(corps), 11 * MIO)
        statut, reponse = requete(port, "PUT", "/api/csv/ordres_travail", corps, {"X-Version-Attendue": "aucune"})
        self.assertEqual(statut, 200, reponse[:200])
        self.assertEqual((self.serveur.dossier / "ordres_travail.csv").read_bytes(), corps)
        # Ajout au journal de 12 Mo (POST csv/<table>/ajout) : accepté.
        journal = (tzi.DOSSIER_DEMO / "journal.csv").read_bytes()[len(BOM):].split(b"\r\n")[0] + b"\r\n" \
            + b"".join(ligne + b"\r\n" for ligne in lignes_de_journal(0, 12 * MIO // 120))
        self.assertGreater(len(journal), 12 * MIO)
        statut, reponse = requete(port, "POST", "/api/csv/journal/ajout", journal)
        self.assertEqual(statut, 200, reponse[:200])
        # 50 Mo annoncés : lus (corps incomplet, 400), pas refusés d'avance ; un octet de plus : 413, rien de lu.
        for methode, chemin in (("PUT", "/api/csv/achats"), ("POST", "/api/csv/journal/ajout")):
            with self.subTest(route=chemin):
                statut, reponse = requete(port, methode, chemin, entetes={"X-Version-Attendue": "aucune"},
                                          annonce=limite_csv, fermer_apres=b"x")
                self.assertEqual(statut, 400, reponse)
                statut, reponse = requete(port, methode, chemin, entetes={"X-Version-Attendue": "aucune"},
                                          annonce=limite_csv + 1)
                self.assertEqual(statut, 413, reponse)
                self.assertIn("50 Mo au maximum", reponse.decode("utf-8"))
        self.assertFalse((self.serveur.dossier / "achats.csv").exists())
        # Documents, sauvegarde : toujours 10 Mo (audit F2).
        for methode, chemin in (("PUT", "/api/documents/gros.pdf"), ("POST", "/api/sauvegarde")):
            with self.subTest(route=chemin):
                statut, reponse = requete(port, methode, chemin, annonce=limite + 1)
                self.assertEqual(statut, 413, reponse)
                self.assertIn("10 Mo au maximum", reponse.decode("utf-8"))
        self.assertFalse((self.serveur.dossier / "documents" / "gros.pdf").exists())


# ---------------------------------------------------------------------------
# 3. Calcul des dépassements (page sans application)
# ---------------------------------------------------------------------------

class TestDepassements(CasNavigateur):

    def depassements(self, entrees, incomplet=False):
        return self.page.evaluate("([e, i]) => ZipDonnees.depassements(e, i)", [entrees, incomplet])

    def test_rien_aux_limites_exactes_une_phrase_par_depassement(self):
        charger_scripts(self.page, ["js/modules/zip-flux.js", "js/modules/zip-lecture.js", "js/modules/zip-donnees.js"])
        self.assertEqual(self.page.evaluate("Object.assign({}, ZipLecture.LIMITES)"),
                         dict(LIMITES, seuilTaux=MIO))
        self.assertEqual(self.page.evaluate("[ZipLecture.LIMITES.zip === ZipFlux.LIMITES.octets, "
                                            "ZipLecture.enMo(ZipLecture.LIMITES.zip), ZipLecture.enMo(ZipLecture.LIMITES.total)]"),
                         [True, "4 Go", "4 Go"])
        csv = [{"nom": "journal.csv", "taille": LIMITES["racine"]}]
        document = [{"nom": "documents/notice.pdf", "taille": LIMITES["document"]}]
        manifeste = [{"nom": "manifeste.json", "taille": 0}]
        self.assertEqual(self.depassements(csv + document + manifeste), [])
        # Un octet de trop : le fichier, sa taille (« plus de » quand l'arrondi égalerait la limite), la limite.
        self.assertEqual(self.depassements([{"nom": "journal.csv", "taille": LIMITES["racine"] + 1}]),
                         ["« journal.csv » fait plus de 50 Mo (50 Mo au plus par fichier de données)"])
        self.assertEqual(self.depassements([{"nom": "ordres_travail.csv", "taille": 52 * MIO + MIO // 3}]),
                         ["« ordres_travail.csv » fait 52,3 Mo (50 Mo au plus par fichier de données)"])
        self.assertEqual(self.depassements([{"nom": "documents/notice.pdf", "taille": LIMITES["document"] + 1}]),
                         ["« documents/notice.pdf » fait plus de 10 Mo (10 Mo au plus par document)"])
        # Nombre d'entrées : 10 000 pile passe, 10 001 non (T212).
        petits = [{"nom": "documents/d%05d.txt" % n, "taille": 1} for n in range(LIMITES["entrees"])]
        self.assertEqual(self.depassements(petits), [])
        self.assertEqual(self.depassements(petits + manifeste), ["le ZIP compterait 10 001 fichiers (10 000 au plus)"])
        self.assertEqual(self.depassements(petits + manifeste, True),
                         ["le ZIP compterait au moins 10 001 fichiers (10 000 au plus)"])
        # Total décompressé (T229 : 4 Go) : 4 Go pile passe ; un octet de plus, « plus de 4 Go » ; 4,1 Go non
        # (documents de 10 Mo, sous leur limite ; des tailles seulement, aucun contenu).
        dix = [{"nom": "documents/n%03d.pdf" % n, "taille": LIMITES["document"]} for n in range(420)]
        pile = dix[:409] + [{"nom": "documents/reste.pdf", "taille": 6 * MIO}]
        self.assertEqual(sum(e["taille"] for e in pile), LIMITES["total"])
        self.assertEqual(self.depassements(pile), [])
        self.assertEqual(self.depassements(pile + [{"nom": "documents/octet.txt", "taille": 1}]),
                         ["le contenu ferait plus de 4 Go une fois décompressé (4 Go au plus)"])
        self.assertEqual(self.depassements(dix),
                         ["le contenu ferait 4,1 Go une fois décompressé (4 Go au plus)"])
        # Taille du ZIP : depuis T229 (ZIP de 4 Go, 4 Go décompressés), des photos ne font un ZIP trop gros qu'au-delà
        # du total décompressé (90 % de leur taille au moins) : les deux phrases. 500 photos de 10 Mo (JPEG, déjà
        # compressées) : 4,9 Go décompressés, un ZIP d'au moins 4,4 Go ; 500 PDF : le total seul, rien d'avance.
        photos = [{"nom": "documents/p%03d.jpg" % n, "taille": 10 * MIO} for n in range(500)]
        self.assertEqual(self.depassements(photos),
                         ["le contenu ferait 4,9 Go une fois décompressé (4 Go au plus)",
                          "le ZIP ferait au moins 4,4 Go, photos et documents déjà compressés (4 Go au plus)"])
        self.assertEqual(self.depassements([{"nom": e["nom"].replace(".jpg", ".pdf"), "taille": 10 * MIO}
                                            for e in photos]),
                         ["le contenu ferait 4,9 Go une fois décompressé (4 Go au plus)"])


# ---------------------------------------------------------------------------
# 4. Aller-retour d'une grosse base, dans les deux modes
# ---------------------------------------------------------------------------

class TestAllerRetour(CasNavigateur):
    """La grosse base (fabriquée une fois pour la classe) et son export par le serveur (une fois aussi)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temporaire = Path(tempfile.mkdtemp(prefix="prevo-zip-limites-"))
        cls.addClassCleanup(shutil.rmtree, cls.temporaire, True)
        cls.base = grosse_base(cls.temporaire / "grosse-base")
        cls.zip_serveur = None

    def setUp(self):
        super().setUp()
        self.contexte.set_default_timeout(LONG_MS)
        preregler_profil(self.contexte, "responsable")

    def exporter(self, page, chemin):
        with page.expect_download(timeout=LONG_MS) as attente:
            page.click("#btn-export-zip")
        attente.value.save_as(str(chemin))
        return entrees_zip(chemin)

    def importer(self, page, chemin, documents):
        page.set_input_files("#fichier-import-zip", str(chemin))
        page.wait_for_selector("#confirmation-import-zip", timeout=LONG_MS)
        self.assertEqual(page.evaluate("Number(document.getElementById('confirmation-import-zip').dataset.documents)"),
                         documents)
        page.click(tzi.BOUTON_REMPLACER)
        page.wait_for_selector("#import-zip-termine", timeout=LONG_MS)
        termine = re.sub(r"\s+", " ", page.inner_text("#import-zip-termine"))
        self.assertIn("24 tables remplacées, %d documents" % documents, termine)
        return termine

    def export_du_serveur(self):
        """Entrées du ZIP exporté (vrai bouton) par un serveur sur la grosse base, contrôlé à l'octet contre le disque
        du serveur au moment de l'export (à l'ouverture, Prévo génère les OT préventifs échus du jeu de charge : le
        journal et les OT ont alors quelques lignes de plus que la base fabriquée)."""
        if type(self).zip_serveur is None:
            chemin = self.temporaire / "prevo-export-serveur.zip"
            with ServeurPrevo(source=self.temporaire / "grosse-base") as serveur:
                page = self.page
                page.goto(serveur.url + "/#/parametres")
                attendre_pret(page, LONG_MS)
                entrees = self.exporter(page, chemin)
                disque = {nom: (serveur.dossier / nom).read_bytes() for nom in self.base}
                page.goto("about:blank")        # plus aucune requête de fond (/api/versions) vers le serveur arrêté
            self.assertEqual(sorted(entrees), sorted(list(self.base) + ["manifeste.json"]))
            for nom, octets in disque.items():
                self.assertTrue(entrees[nom] == octets, nom + " : " + premier_ecart(entrees[nom], octets))
            for nom, octets in self.base.items():
                if nom.startswith("documents/"):
                    self.assertEqual(sha256(entrees[nom]), sha256(octets), nom)
            self.assertGreater(len(entrees["journal.csv"]), 40 * MIO)
            self.assertGreater(len(entrees["ordres_travail.csv"]), 10 * MIO)
            type(self).zip_serveur = (chemin, entrees)
        return type(self).zip_serveur

    def verifier_import(self, entrees, csv_ecrits, documents_ecrits, nom_zip, prefixe):
        """Rien de perdu : chaque document du ZIP est écrit à l'octet (nom rendu : `prefixe` puis le nom du ZIP) ; chaque
        CSV écrit est celui du ZIP à l'octet, noms rendus remis ; le journal a en plus la seule ligne de l'import.
        csv_ecrits {table: octets}, documents_ecrits {nom: sha256}."""
        rendus = {}
        par_empreinte = {}
        for nom, empreinte in documents_ecrits.items():
            par_empreinte.setdefault(empreinte, []).append(nom)
        for nom, octets in documents_de(entrees).items():
            candidats = [rendu for rendu in par_empreinte.get(sha256(octets), [])
                         if re.fullmatch(prefixe + re.escape(nom), rendu)]
            self.assertEqual(len(candidats), 1, "document perdu ou changé : " + nom)
            rendus[nom] = candidats[0]
        for table in TABLES:
            attendu = entrees[table + ".csv"]
            if table in TABLES_A_DOCUMENTS:
                attendu = remettre_noms(attendu, rendus)
            obtenu = csv_ecrits[table]
            if table == "journal":
                self.assertTrue(obtenu.startswith(attendu), premier_ecart(obtenu, attendu))
                suite = obtenu[len(attendu):].decode("utf-8")
                self.assertRegex(suite, r"^[^\r\n]*;parametres;[^\r\n]*import ZIP : %s, 24 tables[^\r\n]*\r\n$"
                                 % re.escape(nom_zip))
            else:
                self.assertTrue(obtenu == attendu, table + " : " + premier_ecart(obtenu, attendu))
        return rendus

    def empreintes(self, page, debuts=None):
        return page.evaluate(EMPREINTES_OPFS_JS, [NOM_DOSSIER, debuts or {}])

    def test_serveur_export_puis_import_dans_une_autre_base_sans_perte(self):
        chemin, entrees = self.export_du_serveur()
        source_b = ecrire_dossier(self.temporaire / "base-b", tzi.fichiers_du_jeu("f3-v1.2.0"))
        with ServeurPrevo(source=source_b) as serveur:
            page = self.page
            page.goto(serveur.url + "/#/parametres")
            attendre_pret(page, LONG_MS)
            self.importer(page, chemin, len(documents_de(entrees)))
            dossier = serveur.dossier
            csv_ecrits = {table: (dossier / (table + ".csv")).read_bytes() for table in TABLES}
            documents = {p.name: sha256(p.read_bytes()) for p in (dossier / "documents").iterdir() if p.is_file()}
        rendus = self.verifier_import(entrees, csv_ecrits, documents, chemin.name, r"\d{8}-\d{6}-")
        self.assertEqual(len(rendus), 37)


    def verifier_opfs(self, page, entrees, nom_zip):
        journal = len(entrees["journal.csv"])
        opfs = self.empreintes(page, {"journal.csv": journal})
        self.assertEqual(opfs["journal.csv"]["debut"], sha256(entrees["journal.csv"]))
        self.assertRegex(opfs["journal.csv"]["suite"], r"^[^\r\n]*;parametres;[^\r\n]*import ZIP : %s, 24 tables"
                                                       r"[^\r\n]*\r\n$" % re.escape(nom_zip))
        for table in TABLES:
            if table != "journal":
                self.assertEqual(opfs[table + ".csv"]["sha256"], sha256(entrees[table + ".csv"]), table)
        documents = {chemin[len("documents/"):]: decrit["sha256"] for chemin, decrit in opfs.items()
                     if chemin.startswith("documents/")}
        for nom, octets in documents_de(entrees).items():
            self.assertEqual(documents.get(nom), sha256(octets), "document perdu ou changé : " + nom)
        return opfs

    def test_dossier_import_export_puis_reimport_sans_perte(self):
        self.autoriser_erreur(tzi.ERREUR_PING_ABSENT)
        chemin, entrees = self.export_du_serveur()
        nombre = len(documents_de(entrees))
        installer_dossier_simule(self.contexte, NOM_DOSSIER)
        with ServeurStatique(RACINE) as statique:
            page = self.page
            page.goto(statique.url + "/index.html")
            page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            page.evaluate(tzi.ECRIRE_OPFS_JS, [NOM_DOSSIER, {c: tzi.en_base64(o)
                                                              for c, o in tzi.fichiers_du_jeu("f3-v1.2.0").items()}])
            page.click("#btn-dossier")
            attendre_pret(page, LONG_MS)
            self.assertEqual(page.evaluate("App.mode"), "dossier")
            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_selector("#btn-import-zip")
            # 1. Import du ZIP du serveur : tout écrit à l'octet (mêmes noms de documents en mode dossier).
            self.importer(page, chemin, nombre)
            self.verifier_opfs(page, entrees, chemin.name)
            # 2. Rechargement, puis export du mode dossier : les fichiers de l'OPFS, à l'octet.
            with page.expect_navigation():
                page.click("dialog button:has-text('Recharger Prévo')")
            page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            page.click("#btn-reprendre")
            attendre_pret(page, LONG_MS)
            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_selector("#btn-export-zip")
            chemin_2 = self.temporaire / "prevo-export-dossier.zip"
            entrees_2 = self.exporter(page, chemin_2)
            self.assertEqual(sorted(entrees_2), sorted(entrees))
            opfs = self.empreintes(page)                        # l'OPFS au moment de l'export
            for nom, octets in entrees_2.items():
                if nom != "manifeste.json":
                    self.assertEqual(sha256(octets), opfs[nom]["sha256"], nom)
            for nom, octets in documents_de(entrees).items():
                self.assertEqual(sha256(entrees_2["documents/" + nom]), sha256(octets), nom)
            # 3. Réimport de cet export : documents identiques repris, CSV à l'octet, journal : une ligne de plus.
            termine = self.importer(page, chemin_2, nombre)
            self.assertIn("%d déjà présent(s), repris" % nombre, termine)
            self.verifier_opfs(page, entrees_2, chemin_2.name)


# ---------------------------------------------------------------------------
# 5. Export refusé : rien n'est produit
# ---------------------------------------------------------------------------

class TestExportRefuse(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-zip-limites-refus-"))
        self.addCleanup(shutil.rmtree, self.temporaire, True)
        preregler_profil(self.contexte, "responsable")

    def ouvrir(self, serveur):
        page = self.page
        page.goto(serveur.url + "/#/parametres")
        attendre_pret(page)
        page.wait_for_selector("#btn-export-zip")
        page.evaluate(ESPION_ZIP_JS)
        return page

    def refus(self, page):
        page.click("#btn-export-zip")
        page.wait_for_selector("#export-zip-refus")
        texte = re.sub(r"\s+", " ", page.inner_text("#export-zip-refus")).strip()
        self.assertTrue(texte.startswith("Export impossible : l'import de Prévo refuserait ce ZIP. "), texte)
        self.assertTrue(texte.endswith(" Aucun ZIP n'a été produit."), texte)
        page.click("dialog .fenetre-actions button:has-text('Fermer')")
        page.wait_for_selector("#export-zip-refus", state="detached")
        return texte

    def compteurs(self, page):
        return page.evaluate("[window.__generations, window.__telechargements]")

    def test_document_trop_gros_nomme_aucun_zip_construit_ni_telecharge(self):
        demo = tzi.fichiers_demo()
        demo["equipements.csv"] = poser_documents(demo["equipements.csv"], "document", ["trop-gros.pdf"])
        source = ecrire_dossier(self.temporaire / "source", dict(demo, **{
            "documents/trop-gros.pdf": octets_fictifs(LIMITES["document"] + 1, "trop", b"%PDF-1.4\n")}))
        with ServeurPrevo(source=source) as serveur:
            page = self.ouvrir(serveur)
            texte = self.refus(page)
            self.assertIn("« documents/trop-gros.pdf » fait plus de 10 Mo (10 Mo au plus par document)", texte)
            self.assertEqual(self.compteurs(page), [0, 0])

    def test_zip_trop_gros_refuse_avant_ou_apres_sa_construction_jamais_telecharge(self):
        demo = tzi.fichiers_demo()
        demo["equipements.csv"] = poser_documents(demo["equipements.csv"], "document", ["notice.pdf"])
        demo["demandes.csv"] = poser_documents(demo["demandes.csv"], "photo", ["photo.jpg"])
        source = ecrire_dossier(self.temporaire / "source", dict(demo, **{
            "documents/notice.pdf": octets_fictifs(MIO, "notice", b"%PDF-1.4\n"),
            "documents/photo.jpg": octets_fictifs(MIO, "photo", b"\xff\xd8\xff\xe0")}))
        with ServeurPrevo(source=source) as serveur:
            page = self.ouvrir(serveur)
            # Limite du ZIP abaissée dans la page (ZipDonnees lit ZipLecture.LIMITES à l'appel) : 1,5 Mo. La photo
            # n'en fait au moins que 0,9 : le ZIP est construit (2,1 Mo environ), puis refusé sur sa taille réelle.
            abaisser = "(zip) => { ZipLecture.LIMITES = Object.freeze(Object.assign({}, ZipLecture.LIMITES, { zip })); }"
            page.evaluate(abaisser, MIO * 3 // 2)
            texte = self.refus(page)
            self.assertRegex(texte, r"Le ZIP ferait 2(,\d)? Mo \(1,5 Mo au plus\)\.")
            self.assertEqual(self.compteurs(page), [1, 0])
            # 0,5 Mo : la photo suffit à le dire, le ZIP n'est pas construit.
            page.evaluate(abaisser, MIO // 2)
            texte = self.refus(page)
            self.assertIn("Le ZIP ferait au moins 0,9 Mo, photos et documents déjà compressés (0,5 Mo au plus).", texte)
            self.assertEqual(self.compteurs(page), [1, 0])


if __name__ == "__main__":
    unittest.main()
