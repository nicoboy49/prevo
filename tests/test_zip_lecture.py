"""Lecture et contrôle d'un ZIP de données (chantier « socle de données », T190 ; décision D172) : ZipLecture.lire de
js/modules/zip-lecture.js, qui ne doit RIEN écrire (ni stockage, ni réseau).

Les ZIP sont fabriqués ici (zipfile, ou ZipFlux et Formats.manifeste dans la page, comme l'export) dans un dossier
temporaire, à partir des jeux de tests/fixtures/formats/ (jeux_formats.copier_jeu) : jamais de données réelles. Les
ZIP de JSZip 3.10.2 (exports publiés 1.2 à 2.0 bêta 2 ; JSZip retiré du dépôt en T229) sont des octets figés :
tests/fixtures/zip-jszip/export-1.2.zip et export-beta2.zip, produits une fois (T229) par le JSZip et le formats.js de
l'étiquette v2.0.0-beta.2, avec les options de chaque version. La page est tests/fixtures/page-vide.html en file://
(charger_scripts) ; le ZIP y arrive par un <input type="file"> (un vrai File), sauf les cas ArrayBuffer et Blob.

    acceptés : export complet avec manifeste exact ; exports 1.2 et 2.0 bêta sans manifeste ; ZIP fait par ZipFlux et
               Formats.manifeste comme l'export (deflate et stocké, ArrayBuffer et Blob) ; ZIP de JSZip figés :
               export 1.2 et bêta 1 (entrée « documents/ », sans manifeste), bêta 2 (sans entrée de dossier, avec
               manifeste), en File, ArrayBuffer et Blob ; variantes (stocké, ZIP64 local, dossier documents/) ; format 2
               et format 1 migrés en mémoire, lignes intactes champ à champ ; fichier au format 2 dans une base au
               format 3 ; tables absentes ; 10 000 entrées ; aucune écriture ni requête pendant la lecture ;
    refusés  : chemins hostiles (../x.csv, /x.csv, C:/x.csv, documents/../../x.csv, a\\b.csv, segment vide, caractère
               de contrôle…) ; noms non admis (acces/comptes.json, virus.exe…) ; doublons ; bombe (60 Mo de zéros) ;
               taille réelle plus grande que la taille annoncée ; contenu abîmé (CRC) ; 10 001 entrées ; CSV de 51 Mo ;
               document de 10 Mo et un octet (10 Mo pile accepté) ;
               plus de 4 Go décompressés (tailles annoncées ; 4 Go pile passent ce contrôle) ; fichier de plus de 4 Go
               moins 2 octets (taille annoncée d'un Blob, rien n'est lu ; la limite pile passe ce contrôle) ; empreinte fausse, fichier ajouté ou manquant ; manifeste
               illisible ; format plus récent ; ZIP sans CSV ; fichier non ZIP ; CSV illisible (format 0) ; entrée
               chiffrée ou méthode inconnue ;
    deux passes (T205) : le résultat ne garde aucun octet de document (nom, taille, empreinte), un seul document
               décompressé à la fois (ZipLecture.memoire), relecture exacte par ZipLecture.lireDocument ; ZIP modifié
               entre les deux passes (même CRC-32 : empreinte ; CRC-32 faux : abîmé), avec et sans manifeste ;
    par morceaux (T227) : ZIP de 30 Mo lu par ZipFlux sans jamais être chargé en entier (Blob.prototype épié :
               aucune lecture de plus de 4 Mo ; memoire().zip = 0) ; navigateur sans « deflate-raw » : refus
               MESSAGE_NAVIGATEUR avant toute lecture, pas de JSZip en secours (retiré du dépôt en T229) ; fichier remplacé ou retiré sur le
               disque entre les deux passes (refus clair), ou avant la lecture (« Lecture du fichier impossible ») ;
    règle des noms de documents : copie conforme à serveur.py (listes et décisions sur une batterie de noms).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_zip_lecture.py" -v
"""
import base64
import csv
import functools
import hashlib
import importlib.util
import io
import json
import random
import shutil
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from commun import RACINE, CasNavigateur, charger_scripts  # noqa: E402
from jeux_formats import copier_jeu  # noqa: E402

SCRIPTS = ["js/lib/papaparse.min.js", "js/schema.js", "js/formats.js", "js/donnees.js",
           "js/modules/zip-tables.js", "js/modules/zip-flux.js", "js/modules/zip-lecture.js"]
ZIP_JSZIP = RACINE / "tests" / "fixtures" / "zip-jszip"
FORMAT_COURANT = 3
MIO = 1024 * 1024
DATE = (2026, 11, 4, 12, 0, 0)
CLES_ACCEPTE = ["abimes", "absentes", "documents", "format", "formatOrigine", "manifeste", "migre", "ok", "problemes",
                "refus", "tables"]
# Documents fictifs, avec la signature de leur format : photo, notice au nom horodaté par le serveur, rapport figé.
DOCUMENTS = {
    "documents/photo-pompe.jpg": b"\xff\xd8\xff\xe0" + b"photo fictive " * 40,
    "documents/20260101-120000-notice.pdf": b"%PDF-1.4\n% notice fictive\n" * 10,
    "documents/rapport-mensuel-2026-10.html": "<!DOCTYPE html><title>Rapport</title><p>Octobre</p>".encode("utf-8"),
}
# Valeur par défaut des colonnes que les formats 2 et 3 ajoutent (js/schema.js) : anomalie_constatee est un booléen.
DEFAUTS = {"valeur_remplacement": "", "symptome_code": "", "ot_origine_id": "", "anomalie_constatee": "0", "astuce": ""}


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_zip_lecture", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()

# Aides installées dans la page : résumé d'un résultat (le résultat complet reste dans window.dernier), base64.
AIDE_JS = """
window.enBase64 = function (octets) {
  let binaire = '';
  for (let i = 0; i < octets.length; i += 0x8000) { binaire += String.fromCharCode.apply(null, octets.subarray(i, i + 0x8000)); }
  return btoa(binaire);
};
window.depuisBase64 = function (texte) {
  const binaire = atob(texte);
  const octets = new Uint8Array(binaire.length);
  for (let i = 0; i < binaire.length; i += 1) { octets[i] = binaire.charCodeAt(i); }
  return octets;
};
// Documents : relus un par un depuis le ZIP (ZipLecture.lireDocument, seconde passe), r.documents n'en gardant
// aucun octet (nom, taille, empreinte).
window.resumer = async function (r) {
  const resume = { ok: r.ok, refus: r.refus, cles: Object.keys(r).sort() };
  if (!r.ok) { return resume; }
  const tables = {};
  for (const [nom, t] of Object.entries(r.tables)) {
    tables[nom] = { entete: t.entete, lignes: t.lignes.length, inconnues: t.colonnesInconnues };
  }
  const documents = [];
  for (const d of r.documents) {
    const octets = await ZipLecture.lireDocument(r, d.nom);
    documents.push({ nom: d.nom, base64: enBase64(octets), uint8: octets instanceof Uint8Array,
      cles: Object.keys(d).sort(), taille: d.taille, empreinte: d.empreinte,
      sansOctets: Object.values(d).every((v) => v === null || typeof v !== 'object') });
  }
  return Object.assign(resume, { format: r.format, formatOrigine: r.formatOrigine, migre: r.migre,
    manifeste: r.manifeste, absentes: r.absentes, tables: tables, documents: documents,
    problemes: r.problemes.map((p) => ({ gravite: p.gravite, type: p.type, table: p.table, message: p.message })) });
};
window.serialiserTables = function () {
  const sortie = {};
  for (const [nom, t] of Object.entries(window.dernier.tables)) {
    sortie[Schema.table(nom).fichier] = enBase64(Donnees.csv.serialiser(nom, t.lignes, t.colonnesInconnues));
  }
  return sortie;
};
const champ = document.createElement('input');
champ.type = 'file';
champ.id = 'zip';
document.body.appendChild(champ);
"""

LIRE_JS = "async () => resumer(window.dernier = await ZipLecture.lire(document.getElementById('zip').files[0]))"


# ---------------------------------------------------------------------------
# Fabrication des fichiers et des ZIP
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _jeu(nom):
    with tempfile.TemporaryDirectory(prefix="prevo-zip-lecture-") as temporaire:
        dossier = copier_jeu(nom, Path(temporaire) / "donnees")
        return tuple((p.relative_to(dossier).as_posix(), p.read_bytes()) for p in sorted(dossier.rglob("*"))
                     if p.is_file())


def fichiers_du_jeu(nom, avec_acces=False):
    """{chemin : octets} d'une copie du jeu (dossier temporaire) ; sans acces/, que l'export n'emporte jamais."""
    return {chemin: octets for chemin, octets in _jeu(nom) if avec_acces or not chemin.startswith("acces/")}


def manifeste(fichiers, format=FORMAT_COURANT, **autres):
    """Octets d'un manifeste exact (comme Formats.manifeste) des fichiers donnés."""
    contenu = {"application": "Prévo", "version_appli": "2.0.0", "format": format, "date": "2026-11-04",
               "motif": "export", "mode": "dossier",
               "fichiers": [{"nom": nom, "octets": len(octets), "sha256": hashlib.sha256(octets).hexdigest()}
                            for nom, octets in sorted(fichiers.items())]}
    contenu.update(autres)
    return json.dumps(contenu, ensure_ascii=False).encode("utf-8")


def octets_zip(entrees, compression=zipfile.ZIP_DEFLATED, zip64=False):
    """Octets d'un ZIP ; entrees : dict ou liste de (nom, octets). Les noms sont écrits TELS QUELS (zipfile ne les
    corrige pas quand on les pose après coup), doublons compris ; un nom en « / » est un dossier."""
    tampon = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")                       # « Duplicate name » : voulu
        with zipfile.ZipFile(tampon, "w", compression) as archive:
            for nom, octets in (entrees.items() if isinstance(entrees, dict) else entrees):
                info = zipfile.ZipInfo("provisoire", date_time=DATE)
                info.filename = nom
                info.compress_type = compression
                if zip64:
                    with archive.open(info, "w", force_zip64=True) as flux:
                        flux.write(octets)
                else:
                    archive.writestr(info, octets)
    return tampon.getvalue()


def entrees_centrales(octets):
    """{nom : position dans le répertoire central} d'un ZIP (lu depuis la fin du répertoire central)."""
    fin = octets.rfind(b"PK\x05\x06")
    nombre = int.from_bytes(octets[fin + 10:fin + 12], "little")
    position = int.from_bytes(octets[fin + 16:fin + 20], "little")
    resultat = {}
    for _ in range(nombre):
        longueurs = [int.from_bytes(octets[position + d:position + d + 2], "little") for d in (28, 30, 32)]
        resultat[octets[position + 46:position + 46 + longueurs[0]].decode("utf-8")] = position
        position += 46 + sum(longueurs)
    return resultat


def modifier_entier(octets, position, taille, valeur):
    tampon = bytearray(octets)
    tampon[position:position + taille] = valeur.to_bytes(taille, "little")
    return bytes(tampon)


def annoncer_tailles(octets, tailles):
    """Le même ZIP où la taille décompressée ANNONCÉE au répertoire central change ({nom : taille}) : les tailles
    annoncées sont contrôlées avant toute décompression (contrôle 3), sans produire de gros fichier."""
    positions = entrees_centrales(octets)
    tampon = bytearray(octets)
    for nom, taille in tailles.items():
        struct.pack_into("<I", tampon, positions[nom] + 24, taille)
    return bytes(tampon)


def meme_crc32_autre_contenu(octets, position=8, compensation=16):
    """Octets de même longueur et de même CRC-32, mais autre contenu (donc autre SHA-256) : l'octet `position` est
    changé, quatre octets à partir de `compensation` rétablissent le CRC (le CRC-32 est linéaire sur GF(2)). Seule
    l'empreinte SHA-256 distingue alors les deux contenus."""
    longueur = len(octets)
    zero = zlib.crc32(bytes(longueur))

    def lineaire(delta):
        return zlib.crc32(bytes(delta)) ^ zero

    delta = bytearray(longueur)
    delta[position] = 0x5A
    colonnes = []
    for bit in range(32):
        unitaire = bytearray(longueur)
        unitaire[compensation + bit // 8] = 1 << (bit % 8)
        colonnes.append(lineaire(unitaire))
    pivots = {}
    for rang, colonne in enumerate(colonnes):                 # base de Gauss sur GF(2) : bit fort → (vecteur, masque)
        vecteur, masque = colonne, 1 << rang
        for fort in range(31, -1, -1):
            if not (vecteur >> fort) & 1:
                continue
            if fort not in pivots:
                pivots[fort] = (vecteur, masque)
                break
            vecteur, masque = vecteur ^ pivots[fort][0], masque ^ pivots[fort][1]
    reste, masque = lineaire(delta), 0
    for fort in range(31, -1, -1):
        if (reste >> fort) & 1:
            reste, masque = reste ^ pivots[fort][0], masque ^ pivots[fort][1]
    assert reste == 0
    for bit in range(32):
        if (masque >> bit) & 1:
            delta[compensation + bit // 8] ^= 1 << (bit % 8)
    autre = bytes(a ^ b for a, b in zip(octets, delta))
    assert autre != octets and zlib.crc32(autre) == zlib.crc32(octets)
    assert hashlib.sha256(autre).digest() != hashlib.sha256(octets).digest()
    return autre


def octets_pseudo_aleatoires(taille, graine):
    """Contenu incompressible, reproductible (aucune donnée réelle)."""
    return random.Random(graine).randbytes(taille)


def lire_table(octets):
    """(en-tête, lignes) d'un CSV, cellules brutes (apostrophes de protection comprises), lignes vides sautées."""
    try:
        texte = octets.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = octets.decode("cp1252")
    lignes = [ligne for ligne in csv.reader(io.StringIO(texte, newline=""), delimiter=";")
              if any(cellule.strip() for cellule in ligne)]
    return (lignes[0], lignes[1:]) if lignes else ([], [])


def cellule(ligne, position):
    return ligne[position] if position < len(ligne) else ""


def csv_de_base():
    """Deux CSV valides (format 3) pour accompagner une entrée à refuser."""
    jeu = fichiers_du_jeu("f3-v1.2.0")
    return {"parametres.csv": jeu["parametres.csv"], "equipements.csv": jeu["equipements.csv"]}


# ---------------------------------------------------------------------------
# Cas de base : une page avec les scripts, un dossier temporaire
# ---------------------------------------------------------------------------

class CasZip(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-zip-lecture-"))
        self.addCleanup(shutil.rmtree, self.temporaire, True)
        charger_scripts(self.page, SCRIPTS)
        self.page.add_script_tag(content=AIDE_JS)
        self.numero = 0

    def lire(self, octets):
        """Résumé de ZipLecture.lire(File) sur ces octets (fichier écrit dans le dossier temporaire)."""
        self.numero += 1
        chemin = self.temporaire / ("essai-%d.zip" % self.numero)
        chemin.write_bytes(octets)
        self.page.set_input_files("#zip", str(chemin))
        return self.page.evaluate(LIRE_JS)

    def accepte(self, octets):
        resultat = self.lire(octets)
        self.assertTrue(resultat["ok"], resultat["refus"])
        self.assertIsNone(resultat["refus"])
        self.assertEqual(resultat["cles"], CLES_ACCEPTE)
        self.assertEqual(resultat["format"], FORMAT_COURANT)
        self.assertEqual(sorted(resultat["tables"]), sorted(self.page.evaluate("Schema.nomsTables()")))
        return resultat

    def refus(self, octets, *attendus):
        """Le message de refus ; le résultat n'a QUE ok et refus ; chaque texte attendu y figure."""
        resultat = self.lire(octets)
        self.assertFalse(resultat["ok"], resultat)
        self.assertEqual(resultat["cles"], ["ok", "refus"])
        for attendu in attendus:
            self.assertIn(attendu, resultat["refus"])
        return resultat["refus"]

    def verifier_cellules_gardees(self, nom_fichier, avant, apres):
        """Toute cellule du fichier d'origine se retrouve, sous le même nom de colonne et à la même ligne ; les
        colonnes ajoutées portent leur valeur par défaut ; seule la valeur de version_schema change (format courant)."""
        entete_avant, lignes_avant = lire_table(avant)
        entete_apres, lignes_apres = lire_table(apres)
        ajoutees = [nom for nom in entete_apres if nom not in entete_avant]
        self.assertTrue(set(ajoutees) <= set(DEFAUTS), "%s : colonnes ajoutées %r" % (nom_fichier, ajoutees))
        if nom_fichier == "parametres.csv":
            cles_avant = [cellule(ligne, entete_avant.index("cle")) for ligne in lignes_avant]
            self.assertEqual(len(lignes_apres), len(lignes_avant) + (0 if "version_schema" in cles_avant else 1))
        else:
            self.assertEqual(len(lignes_apres), len(lignes_avant), nom_fichier + " : nombre de lignes")
        for numero, ligne_avant in enumerate(lignes_avant):
            ligne_apres = lignes_apres[numero]
            for position, nom in enumerate(entete_avant):
                if not nom.strip():
                    continue
                self.assertIn(nom, entete_apres, "%s : colonne %s perdue" % (nom_fichier, nom))
                attendu = cellule(ligne_avant, position)
                if nom_fichier == "parametres.csv" and nom == "valeur" and cellule(ligne_avant, 0) == "version_schema":
                    attendu = "'%d" % FORMAT_COURANT
                self.assertEqual(cellule(ligne_apres, entete_apres.index(nom)), attendu,
                                 "%s, ligne %d, colonne %s" % (nom_fichier, numero + 2, nom))
            for nom in ajoutees:
                self.assertEqual(cellule(ligne_apres, entete_apres.index(nom)), DEFAUTS[nom],
                                 "%s, ligne %d, colonne ajoutée %s" % (nom_fichier, numero + 2, nom))

    def verifier_migration(self, nom_jeu, format_origine):
        """Le jeu, zippé sans manifeste, est lu, migré en mémoire, et chaque cellule d'origine est gardée."""
        jeu = fichiers_du_jeu(nom_jeu)
        resultat = self.accepte(octets_zip(jeu))
        self.assertEqual(resultat["formatOrigine"], format_origine)
        self.assertTrue(resultat["migre"])
        self.assertIsNone(resultat["manifeste"])
        self.assertIn("astuce", resultat["tables"]["ordres_travail"]["entete"])
        reecrits = {nom: base64.b64decode(valeur) for nom, valeur in self.page.evaluate("serialiserTables()").items()}
        for nom_fichier, avant in jeu.items():
            with self.subTest(fichier=nom_fichier):
                self.verifier_cellules_gardees(nom_fichier, avant, reecrits[nom_fichier])
        return resultat


# ---------------------------------------------------------------------------
# ZIP acceptés
# ---------------------------------------------------------------------------

class TestZipAcceptes(CasZip):

    def test_export_complet_avec_manifeste_exact(self):
        fichiers = dict(fichiers_du_jeu("f3-v2.0.0"), **DOCUMENTS)
        contenu_manifeste = manifeste(fichiers, manquants=["photo-perdue.jpg"])
        resultat = self.accepte(octets_zip(dict(fichiers, **{"documents/": b"", "manifeste.json": contenu_manifeste})))
        self.assertEqual(resultat["formatOrigine"], FORMAT_COURANT)
        self.assertFalse(resultat["migre"])
        self.assertEqual(resultat["manifeste"], json.loads(contenu_manifeste))
        self.assertEqual(resultat["absentes"], [])
        for nom_fichier, octets in fichiers.items():
            if nom_fichier.endswith(".csv") and "/" not in nom_fichier:
                self.assertEqual(resultat["tables"][nom_fichier[:-4]]["lignes"], len(lire_table(octets)[1]), nom_fichier)
        self.assertEqual({d["nom"]: base64.b64decode(d["base64"]) for d in resultat["documents"]},
                         {nom[len("documents/"):]: octets for nom, octets in DOCUMENTS.items()})
        self.assertTrue(all(d["uint8"] for d in resultat["documents"]))
        self.assertFalse([p for p in resultat["problemes"] if p["type"] == "table"])
        self.assertTrue(any("photo-perdue.jpg" in p["message"] for p in resultat["problemes"]))

    def test_exports_1_2_et_2_0_beta_sans_manifeste(self):
        for nom_jeu in ("f3-v1.2.0", "f3-v2.0.0"):
            with self.subTest(jeu=nom_jeu):
                resultat = self.accepte(octets_zip(dict(fichiers_du_jeu(nom_jeu), **DOCUMENTS)))
                self.assertIsNone(resultat["manifeste"])
                self.assertEqual(resultat["formatOrigine"], FORMAT_COURANT)
                self.assertFalse(resultat["migre"])
                self.assertEqual(resultat["absentes"], [])
                self.assertEqual(len(resultat["documents"]), len(DOCUMENTS))

    def test_zip_fait_par_zipflux_et_formats_manifeste_comme_l_export(self):
        """Comme l'export depuis T228 : ZipFlux.ecrivain et Formats.manifeste ; deflate, puis stocké ; lu en
        ArrayBuffer et en Blob."""
        fichiers = dict(fichiers_du_jeu("f3-v1.2.0"), **DOCUMENTS)
        en_base64 = {nom: base64.b64encode(octets).decode("ascii") for nom, octets in fichiers.items()}
        for stocker in (False, True):
            with self.subTest(stocker=stocker):
                resultats = self.page.evaluate("""async ([fichiers, stocker]) => {
                  const ecrivain = ZipFlux.ecrivain({ date: new Date(2026, 10, 4, 12, 0, 0) });
                  const decrits = [];
                  for (const [nom, texte] of Object.entries(fichiers)) {
                    const octets = depuisBase64(texte);
                    await ecrivain.ajouter(nom, octets, { stocker: stocker });
                    decrits.push({ nom: nom, octets: octets });
                  }
                  const manifeste = await Formats.manifeste(decrits, { version_appli: '2.0.0', format: Formats.courant,
                    date: '2026-11-04', motif: 'export', mode: 'dossier' });
                  await ecrivain.ajouter('manifeste.json', new TextEncoder().encode(JSON.stringify(manifeste, null, 2)));
                  const blob = ecrivain.terminer();
                  return [await resumer(await ZipLecture.lire(await blob.arrayBuffer())),
                          await resumer(await ZipLecture.lire(blob))];
                }""", [en_base64, stocker])
                for resultat in resultats:
                    self.assertTrue(resultat["ok"], resultat["refus"])
                    self.assertEqual(len(resultat["manifeste"]["fichiers"]), len(fichiers))
                    self.assertFalse(resultat["migre"])
                    self.assertEqual(len(resultat["documents"]), len(DOCUMENTS))

    def test_exports_de_jszip_octets_figes(self):
        """ZIP de JSZip 3.10.2 figés (voir l'en-tête) : export-1.2.zip comme les versions 1.2 et 2.0 bêta 1
        (archive.file sans option : entrée « documents/ » ; deflate ; sans manifeste ; jeu f3-v1.2.0) ; export-beta2.zip
        comme la bêta 2 (createFolders: false, deflate, mimeType, manifeste de Formats.manifeste ; jeu f3-v2.0.0). Lus
        en File, en ArrayBuffer et en Blob."""
        for fichier, nom_jeu, dossier, avec_manifeste in (("export-1.2.zip", "f3-v1.2.0", True, False),
                                                           ("export-beta2.zip", "f3-v2.0.0", False, True)):
            with self.subTest(fichier=fichier):
                octets = (ZIP_JSZIP / fichier).read_bytes()
                with zipfile.ZipFile(io.BytesIO(octets)) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertEqual("documents/" in archive.namelist(), dossier)
                    self.assertFalse([i.filename for i in archive.infolist() if i.flag_bits & 0x08], "pas de bit 3")
                    contenus = {i.filename: archive.read(i) for i in archive.infolist() if not i.is_dir()}
                manifeste_zip = contenus.pop("manifeste.json", None)
                self.assertEqual(manifeste_zip is not None, avec_manifeste)
                attendus = dict(fichiers_du_jeu(nom_jeu), **DOCUMENTS)
                self.assertEqual(contenus, attendus)                  # le jeu et les documents, à l'octet
                resultats = [self.accepte(octets)] + self.page.evaluate("""async (texte) => {
                  const octets = depuisBase64(texte);
                  return [await resumer(await ZipLecture.lire(octets.buffer)),
                          await resumer(await ZipLecture.lire(new Blob([octets], { type: 'application/zip' })))];
                }""", base64.b64encode(octets).decode("ascii"))
                for resultat in resultats:
                    self.assertTrue(resultat["ok"], resultat["refus"])
                    self.assertEqual(resultat["manifeste"], json.loads(manifeste_zip) if avec_manifeste else None)
                    self.assertEqual(resultat["formatOrigine"], FORMAT_COURANT)
                    self.assertFalse(resultat["migre"])
                    self.assertEqual(resultat["absentes"], [])
                    self.assertEqual({d["nom"]: base64.b64decode(d["base64"]) for d in resultat["documents"]},
                                     {nom[len("documents/"):]: o for nom, o in DOCUMENTS.items()})
                    for nom_fichier, contenu in attendus.items():
                        if "/" not in nom_fichier:
                            self.assertEqual(resultat["tables"][nom_fichier[:-4]]["lignes"],
                                             len(lire_table(contenu)[1]), nom_fichier)

    def test_variantes_acceptees(self):
        jeu = dict(fichiers_du_jeu("f3-v1.2.0"), **DOCUMENTS)
        variantes = {
            "stocké sans compression": octets_zip(jeu, compression=zipfile.ZIP_STORED),
            "ZIP64 dans les en-têtes locaux": octets_zip(jeu, zip64=True),
            "dossier documents/ explicite": octets_zip(dict({"documents/": b""}, **jeu)),
            "fichier à 1 Mo de zéros (sous le seuil du taux)": octets_zip(dict(csv_de_base(),
                                                                         **{"documents/zeros.txt": bytes(MIO)})),
        }
        for nom, octets in variantes.items():
            with self.subTest(variante=nom):
                self.accepte(octets)

    def test_zip_au_format_2_migre_lignes_intactes(self):
        resultat = self.verifier_migration("f2-v1.1.0", 2)
        self.assertEqual(resultat["absentes"], ["wiki_pages", "wiki_journal"])
        for nom_table in ("wiki_pages", "wiki_journal"):
            self.assertEqual(resultat["tables"][nom_table]["lignes"], 0)
            self.assertIn({"gravite": "info", "type": "table", "table": nom_table},
                          [{c: p[c] for c in ("gravite", "type", "table")} for p in resultat["problemes"]])

    def test_zip_au_format_1_migre_tables_absentes_listees(self):
        resultat = self.verifier_migration("f1", 1)
        noms = self.page.evaluate("Schema.nomsTables()")
        presentes = {"demandes", "equipements", "ordres_travail", "parametres"}
        self.assertEqual(resultat["absentes"], [nom for nom in noms if nom not in presentes])
        graves = {p["table"]: p["gravite"] for p in resultat["problemes"] if p["type"] == "table"}
        self.assertEqual(graves["localisations"], "attention")      # existait au format 1 : l'import la videra
        self.assertEqual(graves["wiki_pages"], "info")              # n'existait pas au format 1

    def test_fichier_au_format_2_dans_une_base_au_format_3(self):
        # Comme Donnees.etatDuFormat : le plus petit format des fichiers compte (jeu « melange »).
        resultat = self.accepte(octets_zip(fichiers_du_jeu("melange")))
        self.assertEqual(resultat["formatOrigine"], 2)
        self.assertTrue(resultat["migre"])
        self.assertIn("astuce", resultat["tables"]["ordres_travail"]["entete"])

    def test_tables_absentes_vides_et_signalees(self):
        resultat = self.accepte(octets_zip(fichiers_du_jeu("table-absente")))
        self.assertFalse(resultat["migre"])
        self.assertEqual(resultat["absentes"], ["articles", "wiki_pages"])
        colonnes = self.page.evaluate("Formats.colonnes('articles')")
        self.assertEqual(resultat["tables"]["articles"], {"entete": colonnes, "lignes": 0, "inconnues": []})
        attention = [p["table"] for p in resultat["problemes"] if p["type"] == "table" and p["gravite"] == "attention"]
        self.assertEqual(attention, ["articles", "wiki_pages"])

    def test_10000_entrees_acceptees(self):
        entrees = dict(csv_de_base())
        entrees.update({"documents/d%05d.txt" % numero: b"x" for numero in range(10000 - len(entrees))})
        resultat = self.accepte(octets_zip(entrees))
        self.assertEqual(len(resultat["documents"]), 10000 - 2)

    def test_aucune_ecriture_ni_requete_pendant_la_lecture(self):
        self.page.evaluate("""() => {
          window.appels = [];
          const espionner = (objet, nom, libelle) => {
            if (!objet || typeof objet[nom] !== 'function') { return; }
            const origine = objet[nom];
            objet[nom] = function () { window.appels.push(libelle); return origine.apply(this, arguments); };
          };
          espionner(window, 'fetch', 'fetch');
          espionner(XMLHttpRequest.prototype, 'open', 'XMLHttpRequest');
          espionner(Storage.prototype, 'setItem', 'setItem');
          espionner(Storage.prototype, 'removeItem', 'removeItem');
          espionner(Storage.prototype, 'clear', 'clear');
          espionner(window.indexedDB, 'open', 'indexedDB');
          espionner(navigator.storage, 'getDirectory', 'getDirectory');
          espionner(window, 'open', 'window.open');
        }""")
        fichiers = dict(fichiers_du_jeu("f2-v1.1.0"), **DOCUMENTS)
        self.accepte(octets_zip(dict(fichiers, **{"manifeste.json": manifeste(fichiers, format=2)})))
        self.assertEqual(self.page.evaluate("window.appels"), [])


# ---------------------------------------------------------------------------
# Lecture en deux passes (T205) : documents contrôlés puis oubliés, relus un par un
# ---------------------------------------------------------------------------

# Le ZIP vient d'un ArrayBuffer de la page (ZipLecture le lit sans copie) : le modifier après la première passe, c'est
# modifier le ZIP entre les deux passes.
MODIFIER_ENTRE_LES_PASSES_JS = """async ([zip64, nom, position, remplacement64]) => {
  const tampon = depuisBase64(zip64).buffer;
  const lu = await ZipLecture.lire(tampon);
  if (!lu.ok) { return { refus: lu.refus }; }
  const intact = enBase64(await ZipLecture.lireDocument(lu, nom));
  new Uint8Array(tampon).set(depuisBase64(remplacement64), position);
  let autres = 0;
  for (const d of lu.documents) { if (d.nom !== nom) { await ZipLecture.lireDocument(lu, d.nom); autres += 1; } }
  const erreurDe = async (r, n) => { try { await ZipLecture.lireDocument(r, n); return null; } catch (e) { return e.message; } };
  return { refus: null, intact: intact, autres: autres, erreur: await erreurDe(lu, nom),
    inconnus: [await erreurDe(lu, 'absent.pdf'), await erreurDe({ documents: lu.documents }, nom)] };
}"""


class TestDeuxPasses(CasZip):

    def test_documents_controles_un_par_un_sans_octets_gardes(self):
        """Première passe : chaque document décompressé, contrôlé (taille, CRC-32, empreinte du manifeste) puis oublié
        avant le suivant ; le résultat n'en garde que nom, taille et empreinte ; seconde passe : contenu exact."""
        documents = {"documents/gros-%d.pdf" % n: octets_pseudo_aleatoires(taille, n)
                     for n, taille in enumerate((2 * MIO, 3 * MIO, MIO))}
        fichiers = dict(fichiers_du_jeu("f3-v1.2.0"), **documents)
        contenu_manifeste = manifeste(fichiers)
        octets = octets_zip(dict(fichiers, **{"manifeste.json": contenu_manifeste}))
        resultat = self.accepte(octets)
        self.assertEqual(len(resultat["documents"]), 3)
        for d in resultat["documents"]:
            attendu = documents["documents/" + d["nom"]]
            self.assertEqual(d["cles"], ["empreinte", "nom", "taille"])
            self.assertTrue(d["sansOctets"], d["nom"])
            self.assertEqual(d["taille"], len(attendu))
            self.assertEqual(d["empreinte"], hashlib.sha256(attendu).hexdigest())
            self.assertEqual(base64.b64decode(d["base64"]), attendu)
            self.assertTrue(d["uint8"])
        racine = sum(len(o) for nom, o in fichiers.items() if "/" not in nom) + len(contenu_manifeste)
        self.assertEqual(self.page.evaluate("ZipLecture.memoire()"),
                         {"zip": 0, "racine": racine, "documentsGardesMax": 1, "documentMax": 3 * MIO})

    def test_document_modifie_entre_les_deux_passes_refuse_a_la_relecture(self):
        """Contenu changé, même CRC-32 : seule l'empreinte SHA-256 (du manifeste, ou calculée à la première passe
        pour un export sans manifeste) le voit ; contenu changé, CRC-32 faux : « abîmé »."""
        vise = octets_pseudo_aleatoires(4000, 7)
        meme_crc = meme_crc32_autre_contenu(vise)
        crc_faux = vise[:8] + bytes([vise[8] ^ 0x5A]) + vise[9:]
        fichiers = dict(csv_de_base(), **{"documents/autre.pdf": b"%PDF-1.4 autre", "documents/vise.pdf": vise})
        for avec_manifeste in (True, False):
            entrees = dict(fichiers, **({"manifeste.json": manifeste(fichiers)} if avec_manifeste else {}))
            octets = octets_zip(entrees, compression=zipfile.ZIP_STORED)
            self.assertEqual(octets.count(vise), 1)
            for remplacement, attendu in ((meme_crc, "a changé depuis le contrôle du ZIP (son empreinte ne "
                                                     "correspond plus)"), (crc_faux, "« documents/vise.pdf » est abîmé")):
                with self.subTest(manifeste=avec_manifeste, attendu=attendu):
                    sortie = self.page.evaluate(MODIFIER_ENTRE_LES_PASSES_JS, [
                        base64.b64encode(octets).decode("ascii"), "vise.pdf", octets.find(vise),
                        base64.b64encode(remplacement).decode("ascii")])
                    self.assertIsNone(sortie["refus"])
                    self.assertEqual(base64.b64decode(sortie["intact"]), vise)
                    self.assertEqual(sortie["autres"], 1)
                    self.assertIsNotNone(sortie["erreur"])
                    self.assertIn(attendu, sortie["erreur"])
                    self.assertTrue(all(sortie["inconnus"]), sortie["inconnus"])


# ---------------------------------------------------------------------------
# Lecture par morceaux (T227, morceau 2 de T215) : ZipFlux, jamais le fichier entier, pas de JSZip (retiré en T229)
# ---------------------------------------------------------------------------

# Lectures de Blob épiées (window.lectures : [quoi, octets]) : slice → octets de la tranche ; arrayBuffer, stream,
# text, bytes → taille du Blob lu (d'un coup, ou en flux).
ESPION_LECTURES_JS = """() => {
  window.lectures = [];
  const espionner = (objet, nom, libelle, mesure) => {
    const origine = objet[nom];
    objet[nom] = function () {
      window.lectures.push([libelle, mesure(this, arguments)]);
      return origine.apply(this, arguments);
    };
  };
  espionner(Blob.prototype, 'slice', 'slice', (blob, a) => {
    const debut = a[0] || 0;
    return Math.min(a[1] === undefined ? blob.size : a[1], blob.size) - debut;
  });
  for (const nom of ['arrayBuffer', 'stream', 'text', 'bytes']) {
    if (Blob.prototype[nom]) { espionner(Blob.prototype, nom, nom, (blob) => blob.size); }
  }
}"""

GROS_ZIP_JS = """async () => {
  const hexa = (tampon) => Array.from(new Uint8Array(tampon), (o) => o.toString(16).padStart(2, '0')).join('');
  const fichier = document.getElementById('zip').files[0];
  window.lectures = [];
  const r = await ZipLecture.lire(fichier);
  if (!r.ok) { return { refus: r.refus }; }
  const premiere = window.lectures.slice();
  const memoire = ZipLecture.memoire();
  const relus = [];
  for (const d of r.documents) {
    const octets = await ZipLecture.lireDocument(r, d.nom);
    relus.push([d.nom, d.taille, d.empreinte, octets.length, hexa(await crypto.subtle.digest('SHA-256', octets))]);
  }
  return { refus: null, taille: fichier.size, premiere: premiere, toutes: window.lectures, memoire: memoire,
    relus: relus };
}"""

# Navigateur trop ancien : DecompressionStream absent, ou sans « deflate-raw » (le constructeur lève, comme avant
# Chrome 103) ; remis ensuite.
NAVIGATEUR_ANCIEN_JS = """async (cas) => {
  const origine = window.DecompressionStream;
  window.DecompressionStream = cas === 'absent' ? undefined : class extends origine {
    constructor(format) {
      if (format === 'deflate-raw') { throw new TypeError('Unsupported compression format: deflate-raw'); }
      super(format);
    }
  };
  window.lectures = [];
  try {
    const r = await ZipLecture.lire(document.getElementById('zip').files[0]);
    return { disponible: ZipFlux.disponible(), r: r, message: ZipFlux.MESSAGE_NAVIGATEUR, lectures: window.lectures };
  } finally {
    window.DecompressionStream = origine;
  }
}"""

RELIRE_JS = """async (nom) => {
  try { await ZipLecture.lireDocument(window.dernier, nom); return null; } catch (e) { return e.message; }
}"""


class TestParMorceaux(CasZip):

    def test_gros_zip_lu_par_tranches_jamais_en_entier(self):
        """Trente Mo de documents incompressibles (dix de 3 Mo) avec manifeste, dans un vrai File : aucune tranche ni
        aucune lecture de plus de 4 Mo (Blob.prototype épié), rien sur le fichier entier, chaque octet lu à peu près
        une fois par la première passe ; memoire() : ZIP non gardé (0), un document de 3 Mo à la fois ; seconde passe
        exacte."""
        documents = {"documents/gros-%02d.pdf" % n: octets_pseudo_aleatoires(3 * MIO, "gros-%d" % n) for n in range(10)}
        fichiers = dict(csv_de_base(), **documents)
        contenu_manifeste = manifeste(fichiers)
        octets = octets_zip(dict(fichiers, **{"manifeste.json": contenu_manifeste}))
        self.assertGreater(len(octets), 30 * MIO)
        chemin = self.temporaire / "gros.zip"
        chemin.write_bytes(octets)
        del octets
        self.page.set_input_files("#zip", str(chemin))
        self.page.evaluate(ESPION_LECTURES_JS)
        sortie = self.page.evaluate(GROS_ZIP_JS)
        self.assertIsNone(sortie["refus"])
        self.assertEqual(sortie["taille"], chemin.stat().st_size)
        for quoi, taille in sortie["toutes"]:
            self.assertLess(taille, 4 * MIO, quoi)
        tranches = [taille for quoi, taille in sortie["toutes"] if quoi == "slice"]
        self.assertGreaterEqual(max(tranches), 3 * MIO)                  # les documents : une tranche chacun, en flux
        lus = sum(taille for quoi, taille in sortie["premiere"] if quoi != "slice")
        self.assertLess(lus, sortie["taille"] * 1.1)
        racine = sum(len(o) for nom, o in fichiers.items() if "/" not in nom) + len(contenu_manifeste)
        self.assertEqual(sortie["memoire"], {"zip": 0, "racine": racine, "documentsGardesMax": 1,
                                             "documentMax": 3 * MIO})
        self.assertEqual(len(sortie["relus"]), len(documents))
        for nom, taille, empreinte, longueur, relue in sortie["relus"]:
            attendue = hashlib.sha256(documents["documents/" + nom]).hexdigest()
            self.assertEqual((taille, empreinte, longueur, relue), (3 * MIO, attendue, 3 * MIO, attendue), nom)

    def test_navigateur_sans_deflate_raw_refus_avant_toute_lecture(self):
        """ZipFlux.disponible() faux : refus au message de ZipFlux, sans rien lire du fichier et sans JSZip en secours
        (décision de Nicolas) ; le même fichier est lu une fois le navigateur rétabli."""
        chemin = self.temporaire / "navigateur.zip"
        chemin.write_bytes(octets_zip(dict(csv_de_base(), **DOCUMENTS)))
        self.page.set_input_files("#zip", str(chemin))
        self.page.evaluate(ESPION_LECTURES_JS)
        for cas in ("absent", "sans deflate-raw"):
            with self.subTest(cas=cas):
                sortie = self.page.evaluate(NAVIGATEUR_ANCIEN_JS, cas)
                self.assertFalse(sortie["disponible"])
                self.assertEqual(sortie["r"], {"ok": False, "refus": sortie["message"]})
                self.assertIn("Ce navigateur est trop ancien pour lire ou écrire un ZIP de Prévo", sortie["message"])
                self.assertEqual(sortie["lectures"], [])
        self.assertTrue(self.page.evaluate("ZipFlux.disponible()"))
        resultat = self.page.evaluate(LIRE_JS)
        self.assertTrue(resultat["ok"], resultat["refus"])

    def test_fichier_change_ou_retire_sur_le_disque(self):
        """Le ZIP n'est plus gardé en mémoire : la seconde passe relit le fichier choisi. Remplacé ou retiré sur le
        disque depuis le contrôle, il ne se relit plus : refus clair, le document n'est pas importé. Retiré entre le
        choix et la lecture : « Lecture du fichier impossible »."""
        octets = octets_zip(dict(csv_de_base(), **DOCUMENTS))
        debut = "Le fichier « essai-%d.zip » a été modifié, déplacé ou supprimé depuis sa vérification : il n'est pas importé. Relancez l'import."
        self.assertTrue(self.lire(octets)["ok"])
        chemin = self.temporaire / ("essai-%d.zip" % self.numero)
        debut = debut % self.numero
        chemin.write_bytes(octets + bytes(10))                            # remplacé : autre taille, autre date
        self.assertEqual(self.page.evaluate(RELIRE_JS, "photo-pompe.jpg"), debut)
        chemin.unlink()                                                   # supprimé
        self.assertEqual(self.page.evaluate(RELIRE_JS, "20260101-120000-notice.pdf"),
                         debut + " Vérifiez qu'il est toujours à sa place.")
        retire = self.temporaire / "retire.zip"
        retire.write_bytes(octets)
        self.page.set_input_files("#zip", str(retire))
        # Taille lue avant le retrait ; sans cela, Chromium la mesure au premier accès, trouve 0 octet, et le refus est
        # alors « pas un ZIP lisible » (refus aussi, rien n'est lu).
        self.assertEqual(self.page.evaluate("document.getElementById('zip').files[0].size"), len(octets))
        retire.unlink()
        resultat = self.page.evaluate(LIRE_JS)
        self.assertEqual(resultat["cles"], ["ok", "refus"])
        self.assertTrue(resultat["refus"].startswith("Lecture du fichier impossible ("), resultat["refus"])


class TestSourceSansEcriture(unittest.TestCase):
    """Garde-fou : le module ne contient aucun appel d'écriture ni de réseau."""

    def test_aucun_appel_d_ecriture_ni_de_reseau_dans_le_module(self):
        texte = (RACINE / "js" / "modules" / "zip-lecture.js").read_text(encoding="utf-8")
        for interdit in ("fetch(", "XMLHttpRequest", "localStorage", "sessionStorage", "indexedDB", "getDirectory",
                         "ecrireDocument", "enregistrer", ".modifier(", ".ajouter(", "sauvegarder", "navigator.sendBeacon"):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, texte)
        self.assertIn("const ZipLecture = ", texte)


# ---------------------------------------------------------------------------
# ZIP refusés
# ---------------------------------------------------------------------------

class TestZipRefuses(CasZip):

    def test_chemins_hostiles(self):
        hostiles = {
            "../x.csv": "remontée de dossier",
            "/x.csv": "chemin absolu",
            "C:/x.csv": "chemin absolu",
            "c:x.csv": "chemin absolu",
            "documents/../../x.csv": "remontée de dossier",
            "./equipements.csv": "segment « . »",
            "documents/./photo.jpg": "segment « . »",
            "a\\b.csv": "barre oblique inverse",
            "documents\\photo.jpg": "barre oblique inverse",
            "a//b.csv": "segment vide",
            "documents//photo.jpg": "segment vide",
            "x\x01.csv": "caractère de contrôle",
            "documents/photo\x7f.jpg": "caractère de contrôle",
            "../": "remontée de dossier",
        }
        for nom, raison in hostiles.items():
            with self.subTest(nom=nom):
                affiche = "".join("?" if ord(c) < 0x20 or 0x7f <= ord(c) <= 0x9f else c for c in nom)
                self.refus(octets_zip(list(csv_de_base().items()) + [(nom, b"id;nom\r\n")]),
                           "chemin dangereux", "« %s »" % affiche, raison)

    def test_nom_illisible_qui_n_est_pas_de_l_utf8(self):
        octets = octets_zip(dict(csv_de_base(), **{"documents/xxxx.txt": b"x"}))
        position = octets.rfind(b"documents/xxxx.txt")                 # le nom dans le répertoire central
        octets = octets[:position + 10] + b"\xff\xfe" + octets[position + 12:]
        self.refus(octets, "chemin dangereux", "UTF-8")

    def test_noms_non_admis(self):
        for nom in ("acces/comptes.json", "acces/", "virus.exe", "documents/virus.exe", "documents/con.txt",
                    "documents/photo pompe.jpg", "documents/sous/photo.jpg", "sous/equipements.csv",
                    "Ordres_travail.csv", "pieces_v4.csv", "__MACOSX/", "lisezmoi.txt", "documents/.cache.txt"):
            with self.subTest(nom=nom):
                self.refus(octets_zip(dict(csv_de_base(), **{nom: b"" if nom.endswith("/") else b"x"})),
                           "ne vient pas d'un export de Prévo", "« %s »" % nom)

    def test_noms_en_double(self):
        base = list(csv_de_base().items())
        for doublon in (base + [("equipements.csv", b"id\r\n")],
                        base + [("documents/Photo.jpg", b"a"), ("documents/photo.jpg", b"b")]):
            with self.subTest(nom=doublon[-1][0]):
                self.refus(octets_zip(doublon), "deux fois")

    def test_bombe_de_decompression(self):
        octets = octets_zip(dict(csv_de_base(), **{"documents/zeros.txt": bytes(60 * MIO)}))
        self.assertLess(len(octets), MIO)
        self.refus(octets, "« documents/zeros.txt »", "bombe de décompression", "100 fois au plus")

    def test_taille_reelle_plus_grande_que_la_taille_annoncee(self):
        # 5 Mo de zéros annoncés 4 096 octets (sous le seuil du taux) : la décompression s'arrête et refuse.
        octets = octets_zip(dict(csv_de_base(), **{"documents/zeros.txt": bytes(5 * MIO)}))
        octets = modifier_entier(octets, entrees_centrales(octets)["documents/zeros.txt"] + 24, 4, 4096)
        self.refus(octets, "« documents/zeros.txt »", "plus gros que ce que le ZIP annonce")

    def test_contenu_abime_sans_manifeste(self):
        octets = octets_zip(dict(csv_de_base(), **{"documents/notice.txt": b"notice fictive " * 50}),
                            compression=zipfile.ZIP_STORED)
        info = zipfile.ZipFile(io.BytesIO(octets)).getinfo("documents/notice.txt")
        local = info.header_offset
        donnees = local + 30 + int.from_bytes(octets[local + 26:local + 28], "little") \
            + int.from_bytes(octets[local + 28:local + 30], "little")
        octets = octets[:donnees + 3] + b"#" + octets[donnees + 4:]       # un octet changé : CRC-32 faux
        self.refus(octets, "« documents/notice.txt » est abîmé")

    def test_10001_entrees(self):
        entrees = dict(csv_de_base())
        entrees.update({"documents/d%05d.txt" % numero: b"x" for numero in range(10001 - len(entrees))})
        self.refus(octets_zip(entrees), "10 001 entrées", "10 000 au plus")

    def test_csv_de_51_mo(self):
        # T208 : 50 Mo au plus par CSV (LIMITES.racine ; tests/test_zip_limites.py la lie à serveur.py).
        jeu = fichiers_du_jeu("f3-v1.2.0")
        lignes = [jeu["equipements.csv"].split(b"\r\n")[0]]
        taille, numero = len(lignes[0]), 0
        while taille <= 51 * MIO:
            ligne = ("EQ-%07d;Équipement %d;%s" % (numero, numero, hashlib.md5(str(numero).encode()).hexdigest())).encode()
            lignes.append(ligne)
            taille += len(ligne) + 2
            numero += 1
        gros = b"\r\n".join(lignes) + b"\r\n"
        octets = octets_zip({"parametres.csv": jeu["parametres.csv"], "equipements.csv": gros})
        self.assertLess(len(gros) / len(octets), 100)                     # pas une bombe : la taille seule refuse
        self.refus(octets, "« equipements.csv »", "51 Mo", "50 Mo au plus par fichier de données")

    def test_document_de_10_mo_et_un_octet(self):
        # T208 : 10 Mo au plus par document (LIMITES.document, ce que le serveur accepte d'un envoi) ; 10 Mo pile passe.
        pile = octets_pseudo_aleatoires(10 * MIO, "pile")
        self.accepte(octets_zip(dict(csv_de_base(), **{"documents/pile.pdf": pile})))
        trop = octets_zip(dict(csv_de_base(), **{"documents/trop.pdf": pile + b"x"}))
        self.refus(trop, "« documents/trop.pdf »", "10 Mo au plus par document")

    def test_plus_de_4_go_decompresses(self):
        # T229 : 4 Go décompressés au plus (LIMITES.total), contrôlés sur les tailles ANNONCÉES, avant toute
        # décompression : 4 200 documents d'un octet, annoncés 1 Mo au plus chacun au répertoire central (sous le seuil
        # du taux), et deux CSV. Aucun gros fichier n'est produit.
        base = csv_de_base()
        racine = sum(len(octets) for octets in base.values())
        noms = ["documents/z%04d.txt" % numero for numero in range(4200)]
        octets = octets_zip(dict(base, **{nom: b"x" for nom in noms}), compression=zipfile.ZIP_STORED)

        def annonce(total):                    # total décompressé annoncé : 1 Mo par document, puis 0
            reste, tailles = total - racine, {}
            for nom in noms:
                tailles[nom] = min(MIO, reste)
                reste -= tailles[nom]
            self.assertEqual(reste, 0)
            return annoncer_tailles(octets, tailles)

        quatre_go = 4096 * MIO
        pile = self.refus(annonce(quatre_go))  # 4 Go pile : passe ce contrôle (refusé plus loin : tailles fausses)
        self.assertNotIn("une fois décompressé", pile)
        self.assertEqual(self.refus(annonce(quatre_go + 1)),
                         "Ce ZIP fait plus de 4 Go une fois décompressé : 4 Go au plus. Il est refusé.")
        self.assertEqual(self.refus(annonce(4200 * MIO)),
                         "Ce ZIP fait 4,1 Go une fois décompressé : 4 Go au plus. Il est refusé.")

    def test_zip_de_plus_de_4_go_refuse_sans_etre_lu(self):
        """T229 : 4 Go au plus, sans ZIP64 (LIMITES.zip = ZipFlux.LIMITES.octets : 4 Go moins 2 octets). La taille du
        fichier est contrôlée avant toute lecture : Blob à la taille annoncée (aucun gros fichier produit), lectures
        épiées. La limite pile passe ce contrôle (le contenu, vide, est alors lu et refusé comme illisible)."""
        self.page.evaluate(ESPION_LECTURES_JS)
        sortie = self.page.evaluate("""async () => {
          class TailleAnnoncee extends Blob {
            constructor(taille) { super([]); this.taille = taille; }
            get size() { return this.taille; }
          }
          const essai = async (taille) => {
            window.lectures = [];
            const resume = await resumer(await ZipLecture.lire(new TailleAnnoncee(taille)));
            return { refus: resume.refus, cles: resume.cles, lectures: window.lectures.length };
          };
          return { limites: [ZipLecture.LIMITES.zip, ZipFlux.LIMITES.octets, ZipLecture.enMo(ZipLecture.LIMITES.zip)],
            pile: await essai(0xFFFFFFFE), unOctetDeTrop: await essai(0xFFFFFFFF), gros: await essai(4.5 * 1024 ** 3) };
        }""")
        self.assertEqual(sortie["limites"], [0xFFFFFFFE, 0xFFFFFFFE, "4 Go"])
        self.assertEqual(sortie["unOctetDeTrop"], {"cles": ["ok", "refus"], "lectures": 0, "refus":
                         "Ce fichier fait plus de 4 Go : un ZIP de données ne peut pas dépasser 4 Go. Il est refusé."})
        self.assertEqual(sortie["gros"], {"cles": ["ok", "refus"], "lectures": 0, "refus":
                         "Ce fichier fait 4,5 Go : un ZIP de données ne peut pas dépasser 4 Go. Il est refusé."})
        self.assertEqual(sortie["pile"]["cles"], ["ok", "refus"])
        self.assertNotIn("ne peut pas dépasser", sortie["pile"]["refus"])
        self.assertGreater(sortie["pile"]["lectures"], 0)

    def test_empreinte_fausse_fichier_ajoute_ou_manquant(self):
        fichiers = dict(fichiers_du_jeu("f3-v1.2.0"), **DOCUMENTS)
        exact = manifeste(fichiers)
        modifie = dict(fichiers, **{"equipements.csv": fichiers["equipements.csv"].replace(b"Pompe", b"Pompx", 1)})
        self.assertNotEqual(modifie["equipements.csv"], fichiers["equipements.csv"])
        fausse = json.loads(exact)
        fausse["fichiers"][0]["sha256"] = "0" * 64
        sans_un = {nom: octets for nom, octets in fichiers.items() if nom != "documents/photo-pompe.jpg"}
        cas = {
            "fichier modifié": (dict(modifie, **{"manifeste.json": exact}), "ne correspond pas à son empreinte"),
            "empreinte fausse": (dict(fichiers, **{"manifeste.json": json.dumps(fausse).encode()}),
                                 "ne correspond pas à son empreinte"),
            "fichier ajouté": (dict(fichiers, **{"documents/ajout.txt": b"x", "manifeste.json": exact}),
                               "n'est pas décrit par le manifeste"),
            "fichier manquant": (dict(sans_un, **{"manifeste.json": exact}), "manque dans le ZIP"),
        }
        for nom, (entrees, attendu) in cas.items():
            with self.subTest(cas=nom):
                self.refus(octets_zip(entrees), attendu, "refaites l'export")

    def test_manifeste_illisible(self):
        fichiers = fichiers_du_jeu("f3-v1.2.0")
        bon = json.loads(manifeste(fichiers))
        sans_fichiers = dict(bon)
        del sans_fichiers["fichiers"]
        format_texte = dict(bon, format="trois")
        empreinte_courte = json.loads(manifeste(fichiers))
        empreinte_courte["fichiers"][0]["sha256"] = "abc"
        doublon = dict(bon, fichiers=bon["fichiers"] + bon["fichiers"][:1])
        for nom, contenu in {"pas du JSON": b"{pas du json", "tableau": b"[]", "UTF-8 invalide": b'{"a": "\xff"}',
                             "sans fichiers": json.dumps(sans_fichiers).encode(),
                             "format illisible": json.dumps(format_texte).encode(),
                             "empreinte illisible": json.dumps(empreinte_courte).encode(),
                             "fichier en double": json.dumps(doublon).encode()}.items():
            with self.subTest(cas=nom):
                self.refus(octets_zip(dict(fichiers, **{"manifeste.json": contenu})), "manifeste", "illisible")

    def test_format_plus_recent(self):
        recent = fichiers_du_jeu("plus-recent")
        self.assertIn("pieces_v4.csv", recent)                  # table inconnue : le format, plus parlant, prime
        self.refus(octets_zip(recent), "version plus récente de Prévo", "format 4", "jusqu'au format 3",
                   "Mettez Prévo à jour")
        fichiers = fichiers_du_jeu("f3-v1.2.0")
        self.refus(octets_zip(dict(fichiers, **{"manifeste.json": manifeste(fichiers, format=4)})),
                   "version plus récente de Prévo", "format 4")

    def test_zip_sans_csv_de_table(self):
        for nom, entrees in {"documents seuls": dict({"documents/": b""}, **DOCUMENTS),
                             "ZIP vide": {}}.items():
            with self.subTest(cas=nom):
                self.refus(octets_zip(entrees), "aucun fichier CSV de table")

    def test_fichier_qui_n_est_pas_un_zip(self):
        jeu = fichiers_du_jeu("f3-v1.2.0")
        for nom, octets in {"CSV": jeu["equipements.csv"], "vide": b"", "texte": b"PK mais pas un ZIP",
                            "ZIP tronqué": octets_zip(csv_de_base())[:-30]}.items():
            with self.subTest(cas=nom):
                self.refus(octets, "pas un ZIP lisible")

    def test_csv_illisible_format_0(self):
        self.refus(octets_zip(fichiers_du_jeu("entete-tronque")), "« ordres_travail.csv » est illisible",
                   "format 1", "on ne remplace pas une base par un fichier illisible")

    def test_entree_chiffree_ou_methode_inconnue(self):
        octets = octets_zip(csv_de_base())
        position = entrees_centrales(octets)["equipements.csv"]
        self.refus(modifier_entier(octets, position + 8, 2, 1), "« equipements.csv » est chiffré")
        self.refus(modifier_entier(octets, position + 10, 2, 12), "méthode 12")


# ---------------------------------------------------------------------------
# Règle des noms de documents : copie de serveur.py
# ---------------------------------------------------------------------------

def decision_du_serveur(nom):
    try:
        serveur.verifier_nom_document(nom)
        return True
    except serveur.ErreurHttp:
        return False


class TestRegleDesDocuments(CasZip):

    def test_copie_conforme_aux_listes_de_serveur(self):
        regle = self.page.evaluate("JSON.parse(JSON.stringify(ZipLecture.REGLE_DOCUMENTS))")
        self.assertEqual(regle["motif"], "^" + serveur.MOTIF_NOM_DOCUMENT_ENREGISTRE.pattern + "$")
        self.assertEqual(sorted(regle["extensions"]), sorted(serveur.TYPES_DOCUMENTS))
        self.assertEqual(sorted(regle["reserves"]), sorted(serveur.NOMS_RESERVES_WINDOWS))

    def test_memes_decisions_que_serveur(self):
        noms = ["photo.jpg", "20260101-120000-photo.jpg", "PHOTO.JPEG", "rapport-mensuel-2026-10.html", "x.htm",
                "x.doc", "x.xls", "x.exe", "x.jpg.exe", "x.tar.gz", "con.txt", "CON.pdf", "com1.png", "lpt9.txt",
                "com0.txt", "nul", "aux.", "prn.txt.txt", ".cache.txt", "-x.txt", "_x.txt", "a..b.txt", "a b.txt",
                "é.txt", "a/b.txt", "a\\b.txt", "x.JPG", "x", "x.", "x.txt\n", "x\x00.txt", "",
                "a" * 124 + ".txt", "a" * 125 + ".txt", "20260101-120000-" + "a" * 124 + ".txt",
                "20260101-120000-" + "a" * 125 + ".txt", "2026-01-01.pdf", "x.webp", "x.gif", "x.png", "x.pdf",
                "x.txt", "x.csv", "x.docx", "x.xlsx", "x.odt", "x.ods"]
        decisions = self.page.evaluate("(noms) => noms.map((nom) => ZipLecture.nomDocumentAdmis(nom))", noms)
        self.assertEqual(len(decisions), len(noms))
        for nom, decision in zip(noms, decisions):
            with self.subTest(nom=nom):
                self.assertEqual(decision, decision_du_serveur(nom))
        self.assertTrue(decision_du_serveur("20260101-120000-photo.jpg"))   # la batterie a des noms admis
        self.assertFalse(decision_du_serveur("x.exe"))                      # et des noms refusés


if __name__ == "__main__":
    unittest.main()
