"""ZipFlux (js/modules/zip-flux.js, T226, morceau 1 de T215 « ZIP par morceaux ») : lecture d'un ZIP par tranches
(Blob.slice) et décompression en flux contrôlée, écriture en Blob composé sans ZIP64. Module bas niveau, sans écran
ni stockage : l'import (T227) et l'export (T228) s'en serviront.

Les ZIP sont fabriqués ici (zipfile, ou JSZip et ZipFlux dans la page) à partir d'octets fictifs, dans un dossier
temporaire : jamais de données réelles. La page est tests/fixtures/page-vide.html en file:// (charger_scripts) ; un
ZIP y arrive par un <input type="file"> (un vrai File), ou y est produit ; les octets passent en base64.

    1. crc32 : « 123456789 » → 0xCBF43926 ; par morceaux = d'un seul tenant (= zlib.crc32) ;
    2. écriture → relue par zipfile (testzip, noms dont non ASCII, contenus, stocké et deflate, fichier vide, aucune
       entrée de dossier, pas de bit 3, drapeau UTF-8, date DOS), par JSZip et par ZipFlux ; sortie déterministe
       (deux écritures, et des ajouts lancés sans attendre, identiques à l'octet) ;
    3. ZIP de zipfile (deflate, stocké, ZIP64 local par force_zip64, ZIP64 complet) et de JSZip (avec et sans
       descripteurs de données) → lireRepertoire et contenu rendent les noms, tailles, CRC, positions et octets de
       zipfile ; nom qui n'est pas de l'UTF-8 → nom null, octets bruts gardés ;
    4. entrées hostiles : bombe (taille déclarée plus petite que la réelle : 'bombe', décompression arrêtée avant la
       fin des données compressées), CRC faux, taille déclarée trop grande, deflate corrompu ('abime'), données hors
       du fichier, méthode 12, entrée chiffrée, pas un ZIP, ZIP en plusieurs parties ('format') ;
    5. garde des 4 Go ('trop-gros') : verifierLimites, et l'écrivain aux limites réduites (rien n'est ajouté, le ZIP
       reste bon) ;
    6. navigateur sans « deflate-raw » (flux retirés, ou anciens flux qui le refusent, avant le chargement) :
       disponible() faux, ErreurZip 'navigateur' au message exact, lireRepertoire fonctionne encore ;
    7. lireRepertoire ne lit pas tout le fichier (Blob.prototype.slice et les lectures épiés) ; contenu ne lit que
       son entrée.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_zip_flux.py" -v
"""
import base64
import io
import random
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from commun import CasNavigateur, charger_scripts  # noqa: E402

SCRIPTS = ["js/lib/jszip.min.js", "js/modules/zip-flux.js"]
MIO = 1024 * 1024
DATE = (2026, 11, 5, 14, 30, 42)
MESSAGE_NAVIGATEUR = ("Ce navigateur est trop ancien pour lire ou écrire un ZIP de Prévo. Mettez-le à jour (Chrome, "
                      "Edge, Firefox ou Safari récents), ou copiez simplement votre dossier de données pour le "
                      "sauvegarder ou le transporter.")

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
window.fichierZip = function () { return document.getElementById('zip').files[0]; };
window.decrire = function (entree) {
  const copie = Object.assign({}, entree);
  copie.octetsNom = enBase64(entree.octetsNom);
  return copie;
};
// Répertoire et contenu de chaque entrée, lus par ZipFlux.
window.lireTout = async function (blob) {
  const repertoire = await ZipFlux.lireRepertoire(blob);
  const entrees = [];
  for (const entree of repertoire.entrees) {
    const description = decrire(entree);
    const octets = await ZipFlux.contenu(blob, entree);
    description.contenu = enBase64(octets);
    description.uint8 = octets instanceof Uint8Array;
    entrees.push(description);
  }
  return { cles: Object.keys(repertoire).sort(), debut: repertoire.debut, taille: repertoire.taille,
    nombre: repertoire.nombre, entrees: entrees };
};
// null si l'action réussit ; sinon ce qu'il faut savoir de l'erreur (levée ou promesse rejetée).
window.erreurDe = async function (action) {
  try {
    await action();
    return null;
  } catch (erreur) {
    return { classe: erreur instanceof ZipFlux.ErreurZip, nomClasse: erreur.name,
      code: erreur.code === undefined ? null : erreur.code, message: String(erreur.message),
      nom: erreur.nom === undefined ? null : erreur.nom };
  }
};
// Écrit un ZIP : entrées [nom, base64, { stocker, blob }], date [a, m, j, h, mi, s] (heure locale).
window.ecrire = async function (entrees, date, sansAttendre) {
  const ecrivain = ZipFlux.ecrivain({ date: new Date(date[0], date[1] - 1, date[2], date[3], date[4], date[5]) });
  const tailles = [];
  const ajouts = [];
  for (const [nom, texte, choix] of entrees) {
    const octets = depuisBase64(texte);
    const ajout = ecrivain.ajouter(nom, choix.blob ? new Blob([octets]) : octets, { stocker: Boolean(choix.stocker) });
    if (sansAttendre) { ajouts.push(ajout); } else { await ajout; tailles.push(ecrivain.taille); }
  }
  await Promise.all(ajouts);
  const avant = ecrivain.taille;
  const zip = ecrivain.terminer();
  window.dernierZip = zip;
  return { zip: enBase64(new Uint8Array(await zip.arrayBuffer())), tailles: tailles, avant: avant,
    apres: ecrivain.taille, type: zip.type, memeBlob: ecrivain.terminer() === zip };
};
const champ = document.createElement('input');
champ.type = 'file';
champ.id = 'zip';
document.body.appendChild(champ);
"""

# Navigateurs sans « deflate-raw » : flux absents, ou anciens flux (gzip et deflate seulement, Chrome 80 à 102).
SANS_FLUX = "delete window.CompressionStream; delete window.DecompressionStream;"
ANCIENS_FLUX = """
(function () {
  function ancien(Origine) {
    return function (format) {
      if (format === 'deflate-raw') { throw new TypeError('Unsupported compression format: deflate-raw'); }
      return new Origine(format);
    };
  }
  window.CompressionStream = ancien(window.CompressionStream);
  window.DecompressionStream = ancien(window.DecompressionStream);
})();
"""

# Compte les octets compressés donnés au décompresseur (installé après le chargement : ZipFlux lit le constructeur
# à l'appel).
COMPTER_ENTREE_DECOMPRESSEUR = """() => {
  const Origine = window.DecompressionStream;
  window.entreeDecompresseur = 0;
  window.DecompressionStream = function (format) {
    const decompresseur = new Origine(format);
    const compteur = new TransformStream({
      transform(morceau, controleur) { window.entreeDecompresseur += morceau.length; controleur.enqueue(morceau); },
    });
    compteur.readable.pipeTo(decompresseur.writable).catch(function () {});
    return { writable: compteur.writable, readable: decompresseur.readable };
  };
}"""

# Journal des tranches et des lectures de Blob (et donc de File).
EPIER_LECTURES = """() => {
  window.journalLectures = [];
  const tranche = Blob.prototype.slice;
  Blob.prototype.slice = function () {
    const morceau = tranche.apply(this, arguments);
    window.journalLectures.push(['slice', this.size, morceau.size]);
    return morceau;
  };
  for (const methode of ['arrayBuffer', 'stream', 'text']) {
    const origine = Blob.prototype[methode];
    Blob.prototype[methode] = function () {
      window.journalLectures.push([methode, this.size, this.size]);
      return origine.apply(this, arguments);
    };
  }
}"""


# ---------------------------------------------------------------------------
# Fabrication des ZIP (octets fictifs)
# ---------------------------------------------------------------------------

def octets_pseudo_aleatoires(taille, graine):
    """Contenu incompressible, reproductible (aucune donnée réelle)."""
    return random.Random(graine).randbytes(taille)


def b64(octets):
    return base64.b64encode(octets).decode("ascii")


def csv_fictif(lignes):
    return ("cle;valeur\r\n" + "".join("seuil_%d;'%d\r\n" % (i, i * 7) for i in range(lignes))).encode("utf-8")


# Entrées des ZIP à lire : CSV compressible, dossier, nom non ASCII, fichier vide, contenu incompressible.
ENTREES_LECTURE = [
    ("parametres.csv", csv_fictif(3000)),
    ("documents/", b""),
    ("documents/relevé n°3 été.txt", "Relevé : 12,5 bar, pompe P-01\n".encode("utf-8") * 50),
    ("vide.csv", b""),
    ("documents/photo-pompe.jpg", octets_pseudo_aleatoires(300_000, 7)),
]


def zip_python(entrees, compression=zipfile.ZIP_DEFLATED, zip64=False):
    """Octets d'un ZIP écrit par zipfile ; zip64 : en-têtes locaux en ZIP64 (force_zip64)."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", compression) as archive:
        for nom, octets in entrees:
            info = zipfile.ZipInfo(nom, date_time=DATE)
            info.compress_type = compression
            if zip64 and not nom.endswith("/"):
                with archive.open(info, "w", force_zip64=True) as flux:
                    flux.write(octets)
            else:
                archive.writestr(info, octets)
    return tampon.getvalue()


def fin_repertoire(octets):
    """(nombre, taille, début) du répertoire central, fin ZIP64 comprise."""
    fin = octets.rfind(b"PK\x05\x06")
    nombre, taille, debut = struct.unpack_from("<HII", octets, fin + 10)
    if nombre == 0xFFFF or taille == 0xFFFFFFFF or debut == 0xFFFFFFFF:
        fin64 = struct.unpack_from("<Q", octets, fin - 20 + 8)[0]
        nombre, taille, debut = struct.unpack_from("<QQQ", octets, fin64 + 32)
    return nombre, taille, debut


def positions_centrales(octets):
    """Position de chaque entrée du répertoire central, dans l'ordre."""
    nombre, _, position = fin_repertoire(octets)
    positions = []
    for _ in range(nombre):
        positions.append(position)
        position += 46 + sum(struct.unpack_from("<HHH", octets, position + 28))
    return positions


def modifier(octets, position, format_struct, valeur):
    tampon = bytearray(octets)
    struct.pack_into(format_struct, tampon, position, valeur)
    return bytes(tampon)


def zip64_complet(octets):
    """Le même ZIP, répertoire central et fin en ZIP64 : tailles et position à 0xFFFFFFFF dans chaque entrée centrale,
    champ extra 0x0001 (taille, taille compressée, position), puis fin ZIP64, localisateur et fin saturée."""
    nombre, _, debut = fin_repertoire(octets)
    nouvelles = []
    for position in positions_centrales(octets):
        longueur_nom, longueur_extra, longueur_commentaire = struct.unpack_from("<HHH", octets, position + 28)
        entete = bytearray(octets[position:position + 46])
        compresse, decompresse = struct.unpack_from("<II", entete, 20)
        local = struct.unpack_from("<I", entete, 42)[0]
        champ = struct.pack("<HHQQQ", 1, 24, decompresse, compresse, local)
        struct.pack_into("<II", entete, 20, 0xFFFFFFFF, 0xFFFFFFFF)
        struct.pack_into("<I", entete, 42, 0xFFFFFFFF)
        struct.pack_into("<H", entete, 30, longueur_extra + len(champ))
        reste = position + 46
        nom = octets[reste:reste + longueur_nom]
        extra = octets[reste + longueur_nom:reste + longueur_nom + longueur_extra]
        commentaire = octets[reste + longueur_nom + longueur_extra:
                             reste + longueur_nom + longueur_extra + longueur_commentaire]
        nouvelles.append(bytes(entete) + nom + champ + extra + commentaire)
    repertoire = b"".join(nouvelles)
    position_fin64 = debut + len(repertoire)
    fin64 = struct.pack("<IQHHIIQQQQ", 0x06064b50, 44, 45, 45, 0, 0, nombre, nombre, len(repertoire), debut)
    localisateur = struct.pack("<IIQI", 0x07064b50, 0, position_fin64, 1)
    fin = struct.pack("<IHHHHIIH", 0x06054b50, 0, 0, 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0)
    return octets[:debut] + repertoire + fin64 + localisateur + fin


def zip_bombe(taille):
    """ZIP d'une entrée de `taille` octets nuls, écrite en flux (rien de gros en mémoire), puis taille décompressée
    déclarée à 1 000 octets dans le répertoire central. Rend (octets, taille compressée)."""
    tampon = io.BytesIO()
    info = zipfile.ZipInfo("zeros.bin", date_time=DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        with archive.open(info, "w") as flux:
            zeros = bytes(MIO)
            for _ in range(taille // MIO):
                flux.write(zeros)
    octets = tampon.getvalue()
    position = positions_centrales(octets)[0]
    methode, = struct.unpack_from("<H", octets, position + 10)
    compresse, = struct.unpack_from("<I", octets, position + 20)
    assert methode == 8 and compresse * 500 < taille, "bombe : deflate attendu, très compressé"
    return modifier(octets, position + 24, "<I", 1000), compresse


def nom_brut(info):
    return info.filename.encode("utf-8" if info.flag_bits & 0x800 else "cp437")


# ---------------------------------------------------------------------------
# Cas de base
# ---------------------------------------------------------------------------

class CasZipFlux(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-zip-flux-"))
        self.addCleanup(shutil.rmtree, self.temporaire, True)
        self.numero = 0
        self.charger()

    def charger(self):
        charger_scripts(self.page, SCRIPTS)
        self.page.add_script_tag(content=AIDE_JS)

    def poser(self, octets):
        """Le ZIP devient le File de l'<input type="file"> (écrit dans le dossier temporaire)."""
        self.numero += 1
        chemin = self.temporaire / ("essai-%d.zip" % self.numero)
        chemin.write_bytes(octets)
        self.page.set_input_files("#zip", str(chemin))

    def lire_tout(self, octets):
        self.poser(octets)
        return self.page.evaluate("async () => lireTout(fichierZip())")

    def comparer(self, octets, lu):
        """lireRepertoire et contenu (lu) rendent ce que zipfile lit des mêmes octets."""
        self.assertEqual(lu["cles"], ["debut", "entrees", "nombre", "taille"])
        nombre, taille, debut = fin_repertoire(octets)
        self.assertEqual((lu["nombre"], lu["taille"], lu["debut"]), (nombre, taille, debut))
        with zipfile.ZipFile(io.BytesIO(octets)) as archive:
            infos = archive.infolist()
            self.assertEqual(len(lu["entrees"]), len(infos))
            for info, entree in zip(infos, lu["entrees"]):
                with self.subTest(nom=info.filename):
                    attendu = {"nom": info.filename, "octetsNom": b64(nom_brut(info)), "dossier": info.is_dir(),
                               "drapeaux": info.flag_bits, "methode": info.compress_type, "crc": info.CRC,
                               "compresse": info.compress_size, "decompresse": info.file_size,
                               "local": info.header_offset}
                    self.assertEqual(sorted(entree), sorted(list(attendu) + ["contenu", "uint8"]))
                    self.assertEqual({cle: entree[cle] for cle in attendu}, attendu)
                    self.assertTrue(entree["uint8"])
                    self.assertEqual(base64.b64decode(entree["contenu"]), b"" if info.is_dir() else archive.read(info))

    def erreur(self, expression):
        """Erreur de l'action JavaScript `expression` (corps d'une fonction asynchrone), ou None."""
        return self.page.evaluate("async () => erreurDe(async () => { %s })" % expression)

    def verifier_erreur(self, erreur, code, *textes):
        self.assertIsNotNone(erreur, "une ErreurZip '%s' était attendue" % code)
        self.assertTrue(erreur["classe"], erreur)
        self.assertEqual(erreur["nomClasse"], "ErreurZip")
        self.assertEqual(erreur["code"], code, erreur["message"])
        for texte in textes:
            self.assertIn(texte, erreur["message"])


# ---------------------------------------------------------------------------
# 1. CRC-32
# ---------------------------------------------------------------------------

class TestCrc32(CasZipFlux):

    def test_valeur_de_controle_et_morceaux(self):
        donnees = octets_pseudo_aleatoires(100_000, 1)
        resultat = self.page.evaluate("""([texte]) => {
          const neuf = new TextEncoder().encode('123456789');
          const o = depuisBase64(texte);
          return {
            controle: ZipFlux.crc32(neuf),
            vide: ZipFlux.crc32(new Uint8Array(0)),
            deuxMorceaux: ZipFlux.crc32(neuf.subarray(4), ZipFlux.crc32(neuf.subarray(0, 4))),
            entier: ZipFlux.crc32(o),
            troisMorceaux: ZipFlux.crc32(o.subarray(70000),
              ZipFlux.crc32(o.subarray(33333, 70000), ZipFlux.crc32(o.subarray(0, 33333)))),
          };
        }""", [b64(donnees)])
        self.assertEqual(resultat["controle"], 0xCBF43926)
        self.assertEqual(resultat["vide"], 0)
        self.assertEqual(resultat["deuxMorceaux"], 0xCBF43926)
        self.assertEqual(resultat["entier"], zlib.crc32(donnees))
        self.assertEqual(resultat["troisMorceaux"], zlib.crc32(donnees))


# ---------------------------------------------------------------------------
# 2. Écriture
# ---------------------------------------------------------------------------

ENTREES_ECRITURE = [
    ("parametres.csv", csv_fictif(5000), {}),
    ("documents/relevé n°3 été.txt", "Relevé : 12,5 bar, pompe P-01\n".encode("utf-8") * 40, {"stocker": True}),
    ("documents/photo-pompe.jpg", octets_pseudo_aleatoires(1_500_000, 3), {"stocker": True, "blob": True}),
    ("vide.csv", b"", {}),
    ("documents/vide.txt", b"", {"stocker": True}),
    ("manifeste.json", b'{"application": "Pr\xc3\xa9vo", "format": 3}', {"blob": True}),
]


class TestEcriture(CasZipFlux):

    def ecrire(self, entrees=ENTREES_ECRITURE, sans_attendre=False):
        return self.page.evaluate("([entrees, date, sansAttendre]) => ecrire(entrees, date, sansAttendre)",
                                  [[[nom, b64(octets), choix] for nom, octets, choix in entrees], list(DATE),
                                   sans_attendre])

    def test_relu_par_zipfile(self):
        ecrit = self.ecrire()
        octets = base64.b64decode(ecrit["zip"])
        self.assertEqual(ecrit["type"], "application/zip")
        self.assertTrue(ecrit["memeBlob"])
        with zipfile.ZipFile(io.BytesIO(octets)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.namelist(), [nom for nom, _, _ in ENTREES_ECRITURE])
            for info, (nom, contenu, choix) in zip(archive.infolist(), ENTREES_ECRITURE):
                with self.subTest(nom=nom):
                    self.assertEqual(archive.read(info), contenu)
                    self.assertEqual(info.compress_type,
                                     zipfile.ZIP_STORED if choix.get("stocker") else zipfile.ZIP_DEFLATED)
                    self.assertFalse(info.is_dir())
                    self.assertEqual(info.flag_bits & 0x0800, 0x0800, "drapeau UTF-8 (bit 11)")
                    self.assertEqual(info.flag_bits & 0x0008, 0, "pas de descripteur de données (bit 3)")
                    self.assertEqual(info.flag_bits & 0x0001, 0)
                    self.assertEqual(info.date_time, DATE)
                    self.assertEqual((info.create_version, info.extract_version), (20, 20))
                    self.assertEqual(info.extra, b"")
                    # En-tête local : mêmes CRC-32 et tailles que le répertoire central (rien à 0, rien après).
                    local = struct.unpack_from("<IHHHHHIIIHH", octets, info.header_offset)
                    self.assertEqual(local[0], 0x04034b50)
                    self.assertEqual(local[2], info.flag_bits)
                    self.assertEqual(local[6:9], (info.CRC, info.compress_size, info.file_size))
                    self.assertEqual(local[10], 0, "aucun champ extra local")
            self.assertFalse([nom for nom in archive.namelist() if nom.endswith("/")], "aucune entrée de dossier")
        # Taille : en-têtes locaux et données avant terminer() (= début du répertoire central), tout le ZIP après.
        nombre, taille, debut = fin_repertoire(octets)
        self.assertEqual(nombre, len(ENTREES_ECRITURE))
        self.assertEqual(ecrit["avant"], debut)
        self.assertEqual(ecrit["apres"], len(octets))
        self.assertEqual(debut + taille + 22, len(octets))
        self.assertEqual(ecrit["tailles"], sorted(ecrit["tailles"]))
        # La photo, incompressible, est bien stockée telle quelle ; le CSV est bien compressé.
        with zipfile.ZipFile(io.BytesIO(octets)) as archive:
            self.assertLess(archive.getinfo("parametres.csv").compress_size, len(ENTREES_ECRITURE[0][1]) // 3)
            self.assertEqual(archive.getinfo("documents/photo-pompe.jpg").compress_size, 1_500_000)

    def test_sortie_deterministe(self):
        premier = self.ecrire()["zip"]
        second = self.ecrire()["zip"]
        sans_attendre = self.ecrire(sans_attendre=True)["zip"]
        self.assertEqual(premier, second, "même entrées, même date : mêmes octets")
        self.assertEqual(premier, sans_attendre, "ajouts lancés sans attendre : même ordre, mêmes octets")

    def test_relu_par_jszip_et_par_zipflux(self):
        ecrit = self.ecrire()
        octets = base64.b64decode(ecrit["zip"])
        jszip = self.page.evaluate("""async () => {
          const archive = await JSZip.loadAsync(window.dernierZip, { checkCRC32: true });
          const sortie = {};
          for (const nom of Object.keys(archive.files)) {
            sortie[nom] = { dossier: archive.files[nom].dir, base64: enBase64(await archive.files[nom].async('uint8array')) };
          }
          return sortie;
        }""")
        self.assertEqual(list(jszip), [nom for nom, _, _ in ENTREES_ECRITURE])
        for nom, contenu, _ in ENTREES_ECRITURE:
            self.assertFalse(jszip[nom]["dossier"])
            self.assertEqual(base64.b64decode(jszip[nom]["base64"]), contenu, nom)
        lu = self.page.evaluate("async () => lireTout(window.dernierZip)")
        self.comparer(octets, lu)

    def test_date_bornee_et_par_defaut(self):
        resultat = self.page.evaluate("""async () => {
          const zip = async (options) => {
            const ecrivain = ZipFlux.ecrivain(options);
            await ecrivain.ajouter('a.txt', new Uint8Array([1, 2, 3]));
            return enBase64(new Uint8Array(await ecrivain.terminer().arrayBuffer()));
          };
          return { ancienne: await zip({ date: new Date(1970, 0, 1) }), defaut: await zip(),
            invalide: await erreurDe(() => ZipFlux.ecrivain({ date: new Date('n importe quoi') })) };
        }""")
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(resultat["ancienne"]))) as archive:
            self.assertEqual(archive.infolist()[0].date_time, (1980, 1, 1, 0, 0, 0))
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(resultat["defaut"]))) as archive:
            self.assertIsNone(archive.testzip())
            self.assertGreaterEqual(archive.infolist()[0].date_time[0], 2026)
        self.assertEqual(resultat["invalide"]["nomClasse"], "TypeError")


# ---------------------------------------------------------------------------
# 3. Lecture de ZIP écrits par zipfile et par JSZip
# ---------------------------------------------------------------------------

class TestLecture(CasZipFlux):

    def test_zip_python_deflate(self):
        octets = zip_python(ENTREES_LECTURE)
        self.comparer(octets, self.lire_tout(octets))

    def test_zip_python_stocke(self):
        octets = zip_python(ENTREES_LECTURE, zipfile.ZIP_STORED)
        self.comparer(octets, self.lire_tout(octets))

    def test_zip_python_zip64_local(self):
        octets = zip_python(ENTREES_LECTURE, zip64=True)
        self.assertIn(b"\x01\x00\x10\x00", octets, "champ extra ZIP64 des en-têtes locaux")
        self.comparer(octets, self.lire_tout(octets))

    def test_zip64_complet(self):
        octets = zip64_complet(zip_python(ENTREES_LECTURE))
        with zipfile.ZipFile(io.BytesIO(octets)) as archive:
            self.assertIsNone(archive.testzip())             # le ZIP fabriqué est bon pour zipfile
        self.assertIn(b"PK\x06\x06", octets)
        self.assertIn(b"PK\x06\x07", octets)
        self.comparer(octets, self.lire_tout(octets))

    def test_nom_qui_n_est_pas_de_l_utf8(self):
        octets = zip_python([("x-nom.csv", b"a;b\r\n"), ("y.csv", b"c\r\n")])
        position = positions_centrales(octets)[0]
        octets = modifier(octets, position + 46, "<B", 0xFF)
        lu = self.lire_tout(octets)
        self.assertIsNone(lu["entrees"][0]["nom"])
        self.assertFalse(lu["entrees"][0]["dossier"])
        self.assertEqual(base64.b64decode(lu["entrees"][0]["octetsNom"]), b"\xff-nom.csv")
        self.assertEqual(base64.b64decode(lu["entrees"][0]["contenu"]), b"a;b\r\n")
        self.assertEqual(lu["entrees"][1]["nom"], "y.csv")

    def zip_jszip(self, descripteurs):
        fichiers = [[nom, b64(octets), nom.endswith(".jpg")] for nom, octets in ENTREES_LECTURE
                    if not nom.endswith("/")]
        return self.page.evaluate("""async ([fichiers, streamFiles]) => {
          const zip = new JSZip();
          for (const [nom, texte, stocker] of fichiers) {
            zip.file(nom, depuisBase64(texte), stocker ? { compression: 'STORE' } : {});
          }
          const blob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE', streamFiles: streamFiles });
          return { zip: enBase64(new Uint8Array(await blob.arrayBuffer())), lu: await lireTout(blob) };
        }""", [fichiers, descripteurs])

    def test_zip_jszip(self):
        for descripteurs in (False, True):
            with self.subTest(descripteurs=descripteurs):
                resultat = self.zip_jszip(descripteurs)
                octets = base64.b64decode(resultat["zip"])
                self.comparer(octets, resultat["lu"])
                drapeaux = [entree["drapeaux"] & 0x08 for entree in resultat["lu"]["entrees"]]
                self.assertEqual(any(drapeaux), descripteurs, "descripteurs de données (bit 3) de JSZip")
                self.assertIn("documents/", [entree["nom"] for entree in resultat["lu"]["entrees"]])
                lus = {entree["nom"]: base64.b64decode(entree["contenu"]) for entree in resultat["lu"]["entrees"]}
                for nom, contenu in ENTREES_LECTURE:
                    self.assertEqual(lus[nom], contenu, nom)


# ---------------------------------------------------------------------------
# 4. Entrées hostiles
# ---------------------------------------------------------------------------

class TestHostiles(CasZipFlux):

    def contenu_premiere(self, octets, avant=""):
        """Erreur de ZipFlux.contenu sur la première entrée (lue par lireRepertoire), ou None."""
        self.poser(octets)
        return self.erreur("%s const r = await ZipFlux.lireRepertoire(fichierZip()); "
                           "await ZipFlux.contenu(fichierZip(), r.entrees[0]);" % avant)

    def repertoire(self, octets):
        self.poser(octets)
        return self.erreur("await ZipFlux.lireRepertoire(fichierZip());")

    def base(self):
        return zip_python([("parametres.csv", csv_fictif(2000)), ("autre.csv", b"x;y\r\n")])

    def test_bombe_arretee_avant_la_fin(self):
        octets, compresse = zip_bombe(256 * MIO)
        self.page.evaluate(COMPTER_ENTREE_DECOMPRESSEUR)
        erreur = self.contenu_premiere(octets)
        self.verifier_erreur(erreur, "bombe", "zeros.bin", "bombe de décompression")
        self.assertEqual(erreur["nom"], "zeros.bin")
        donne = self.page.evaluate("window.entreeDecompresseur")
        self.assertGreater(donne, 0)
        self.assertLess(donne, compresse // 4, "décompression arrêtée bien avant la fin des %d octets compressés"
                        % compresse)

    def test_bombe_entree_stockee(self):
        octets = zip_python([("a.csv", b"0123456789" * 100)], zipfile.ZIP_STORED)
        position = positions_centrales(octets)[0]
        self.verifier_erreur(self.contenu_premiere(modifier(octets, position + 24, "<I", 999)), "bombe")

    def test_crc_faux(self):
        octets = self.base()
        position = positions_centrales(octets)[0]
        crc = struct.unpack_from("<I", octets, position + 16)[0]
        erreur = self.contenu_premiere(modifier(octets, position + 16, "<I", crc ^ 1))
        self.verifier_erreur(erreur, "abime", "parametres.csv", "abîmé")

    def test_taille_declaree_trop_grande(self):
        octets = self.base()
        position = positions_centrales(octets)[0]
        taille = struct.unpack_from("<I", octets, position + 24)[0]
        self.verifier_erreur(self.contenu_premiere(modifier(octets, position + 24, "<I", taille + 1)), "abime")

    def test_deflate_corrompu(self):
        octets = self.base()
        with zipfile.ZipFile(io.BytesIO(octets)) as archive:
            info = archive.infolist()[0]
        longueurs = struct.unpack_from("<HH", octets, info.header_offset + 26)
        donnees = info.header_offset + 30 + sum(longueurs)
        tampon = bytearray(octets)
        tampon[donnees:donnees + 64] = b"\xff" * 64        # bloc de type 3 (réservé) : flux deflate invalide
        self.verifier_erreur(self.contenu_premiere(bytes(tampon)), "abime", "parametres.csv")

    def test_donnees_hors_du_fichier(self):
        octets = self.base()
        position = positions_centrales(octets)[0]
        self.verifier_erreur(self.contenu_premiere(modifier(octets, position + 42, "<I", len(octets) + 1000)),
                             "format", "abîmé")
        # En-tête local introuvable à la position annoncée.
        self.verifier_erreur(self.contenu_premiere(modifier(octets, position + 42, "<I", 5)), "format")
        # Données qui débordent sur le répertoire central : refusées avec la limite du contrôle 2 de zip-lecture.js.
        taille = struct.unpack_from("<I", octets, position + 20)[0]
        _, _, debut = fin_repertoire(octets)
        deborde = modifier(octets, position + 20, "<I", taille + 100)
        self.poser(deborde)
        erreur = self.erreur("const r = await ZipFlux.lireRepertoire(fichierZip()); "
                             "await ZipFlux.positionDonnees(fichierZip(), r.entrees[0], r.debut);")
        self.verifier_erreur(erreur, "format")
        self.assertIsNone(self.erreur("const r = await ZipFlux.lireRepertoire(fichierZip()); "
                                      "if (await ZipFlux.positionDonnees(fichierZip(), r.entrees[1], r.debut) >= %d) "
                                      "{ throw new Error('position'); }" % debut))

    def test_methode_12_et_entree_chiffree(self):
        octets = self.base()
        position = positions_centrales(octets)[0]
        self.verifier_erreur(self.contenu_premiere(modifier(octets, position + 10, "<H", 12)), "format",
                             "méthode 12")
        drapeaux = struct.unpack_from("<H", octets, position + 8)[0]
        self.verifier_erreur(self.contenu_premiere(modifier(octets, position + 8, "<H", drapeaux | 1)), "format",
                             "chiffré")

    def test_pas_un_zip_et_plusieurs_parties(self):
        self.verifier_erreur(self.repertoire(octets_pseudo_aleatoires(5000, 4)), "format", "pas un ZIP lisible")
        self.verifier_erreur(self.repertoire(b"PK\x05\x06"), "format", "pas un ZIP lisible")
        octets = self.base()
        fin = octets.rfind(b"PK\x05\x06")
        self.verifier_erreur(self.repertoire(modifier(octets, fin + 4, "<H", 1)), "format", "plusieurs parties")
        # Répertoire central annoncé hors du fichier.
        self.verifier_erreur(self.repertoire(modifier(octets, fin + 16, "<I", len(octets))), "format", "abîmé")
        # Nombre d'entrées plus grand que le répertoire.
        self.verifier_erreur(self.repertoire(modifier(octets, fin + 10, "<H", 3)), "format")
        # Le ZIP intact passe.
        self.assertIsNone(self.repertoire(octets))


# ---------------------------------------------------------------------------
# 5. Garde des 4 Go
# ---------------------------------------------------------------------------

class TestQuatreGo(CasZipFlux):

    def test_verifier_limites(self):
        resultat = self.page.evaluate("""() => {
          const essai = (mesures, limites) => {
            try { ZipFlux.verifierLimites(mesures, limites); return null; } catch (e) { return [e.code, e.message]; }
          };
          return {
            limites: ZipFlux.LIMITES,
            rien: essai({}),
            entreesMax: essai({ entrees: 65534 }), entreesTrop: essai({ entrees: 65535 }),
            totalMax: essai({ total: 0xFFFFFFFE }), totalTrop: essai({ total: 0xFFFFFFFF }),
            totalBienTrop: essai({ total: 5 * 1024 * 1024 * 1024 }),
            decompresseTrop: essai({ decompresse: 0xFFFFFFFF }), compresseTrop: essai({ compresse: 0xFFFFFFFF }),
            limitesReduites: essai({ total: 1001 }, { octets: 1000 }),
          };
        }""")
        self.assertEqual(resultat["limites"], {"octets": 0xFFFFFFFE, "entrees": 65534})
        for cle in ("rien", "entreesMax", "totalMax"):
            self.assertIsNone(resultat[cle], cle)
        for cle in ("totalTrop", "totalBienTrop", "decompresseTrop", "compresseTrop"):
            self.assertEqual(resultat[cle][0], "trop-gros", cle)
            self.assertIn("4 Go", resultat[cle][1])
        self.assertEqual(resultat["entreesTrop"][0], "trop-gros")
        self.assertIn("65 534", resultat["entreesTrop"][1])
        self.assertEqual(resultat["limitesReduites"][0], "trop-gros")

    def test_ecrivain_aux_limites_reduites(self):
        # Limite de 900 octets : a.txt (100 o) puis b.txt (600 o), stockés, font un ZIP de 894 octets ; c.txt (1 o)
        # le porterait à 981 (répertoire central et fin compris) ; d.txt (2 000 o) dépasse d'emblée.
        resultat = self.page.evaluate("""async () => {
          const ecrivain = ZipFlux.ecrivain({ date: new Date(2026, 10, 5), limites: { octets: 900 } });
          const stocke = { stocker: true };
          await ecrivain.ajouter('a.txt', new Uint8Array(100).fill(97), stocke);
          await ecrivain.ajouter('b.txt', new Uint8Array(600).fill(98), stocke);
          const avant = ecrivain.taille;
          const c = await erreurDe(() => ecrivain.ajouter('c.txt', new Uint8Array(1), stocke));
          const d = await erreurDe(() => ecrivain.ajouter('d.txt', new Uint8Array(2000), stocke));
          const apres = ecrivain.taille;
          const zip = ecrivain.terminer();
          const parEntrees = ZipFlux.ecrivain({ date: new Date(2026, 10, 5), limites: { entrees: 2 } });
          await parEntrees.ajouter('1.txt', new Uint8Array(1));
          await parEntrees.ajouter('2.txt', new Uint8Array(1));
          const troisieme = await erreurDe(() => parEntrees.ajouter('3.txt', new Uint8Array(1)));
          return { c: c, d: d, avant: avant, apres: apres, zip: enBase64(new Uint8Array(await zip.arrayBuffer())),
            troisieme: troisieme, deux: (await ZipFlux.lireRepertoire(parEntrees.terminer())).nombre };
        }""")
        self.verifier_erreur(resultat["c"], "trop-gros", "4 Go")
        self.verifier_erreur(resultat["d"], "trop-gros", "4 Go")
        self.verifier_erreur(resultat["troisieme"], "trop-gros", "65 534")
        self.assertEqual(resultat["deux"], 2)
        self.assertEqual(resultat["avant"], resultat["apres"], "rien n'est écrit pour une entrée refusée")
        octets = base64.b64decode(resultat["zip"])
        self.assertEqual(len(octets), 894)
        with zipfile.ZipFile(io.BytesIO(octets)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.namelist(), ["a.txt", "b.txt"])
            self.assertEqual(archive.read("b.txt"), b"b" * 600)


# ---------------------------------------------------------------------------
# 6. Navigateur sans « deflate-raw »
# ---------------------------------------------------------------------------

class TestSansDeflateBrut(CasZipFlux):

    def verifier_sans_flux(self, script):
        self.contexte.add_init_script(script)
        self.charger()                                      # rechargée : le script passe avant les nôtres
        octets = zip_python(ENTREES_LECTURE)
        self.poser(octets)
        resultat = self.page.evaluate("""async () => {
          const r = await ZipFlux.lireRepertoire(fichierZip());
          return {
            disponible: ZipFlux.disponible(),
            message: ZipFlux.MESSAGE_NAVIGATEUR,
            contenu: await erreurDe(() => ZipFlux.contenu(fichierZip(), r.entrees[0])),
            ecrivain: await erreurDe(() => ZipFlux.ecrivain({ date: new Date() })),
            entrees: r.entrees.map(decrire),
          };
        }""")
        self.assertFalse(resultat["disponible"])
        self.assertEqual(resultat["message"], MESSAGE_NAVIGATEUR)
        for cle in ("contenu", "ecrivain"):
            self.verifier_erreur(resultat[cle], "navigateur")
            self.assertEqual(resultat[cle]["message"], MESSAGE_NAVIGATEUR)
        with zipfile.ZipFile(io.BytesIO(octets)) as archive:
            self.assertEqual([(e["nom"], e["crc"], e["decompresse"]) for e in resultat["entrees"]],
                             [(i.filename, i.CRC, i.file_size) for i in archive.infolist()])

    def test_flux_absents(self):
        self.verifier_sans_flux(SANS_FLUX)

    def test_anciens_flux_sans_deflate_brut(self):
        self.verifier_sans_flux(ANCIENS_FLUX)

    def test_ajouter_rejete_si_les_flux_disparaissent(self):
        resultat = self.page.evaluate("""async () => {
          const avant = ZipFlux.disponible();
          const ecrivain = ZipFlux.ecrivain({ date: new Date() });
          window.CompressionStream = undefined;
          return { avant: avant, apres: ZipFlux.disponible(),
            ajouter: await erreurDe(() => ecrivain.ajouter('a.txt', new Uint8Array(3))) };
        }""")
        self.assertTrue(resultat["avant"])
        self.assertFalse(resultat["apres"])
        self.verifier_erreur(resultat["ajouter"], "navigateur")
        self.assertEqual(resultat["ajouter"]["message"], MESSAGE_NAVIGATEUR)


# ---------------------------------------------------------------------------
# 7. Lecture par tranches
# ---------------------------------------------------------------------------

class TestTranches(CasZipFlux):

    def test_lire_repertoire_ne_lit_pas_tout_le_fichier(self):
        entrees = [("documents/photo-%d.jpg" % i, octets_pseudo_aleatoires(1_500_000, 10 + i)) for i in range(3)]
        entrees += [("parametres.csv", csv_fictif(500)), ("vide.csv", b"")]
        octets = zip_python(entrees)
        self.assertGreater(len(octets), 4 * MIO)
        self.poser(octets)
        self.page.evaluate(EPIER_LECTURES)
        resultat = self.page.evaluate("""async () => {
          window.journalLectures = [];
          const r = await ZipFlux.lireRepertoire(fichierZip());
          const repertoire = window.journalLectures;
          window.journalLectures = [];
          const entree = r.entrees[1];
          const octets = await ZipFlux.contenu(fichierZip(), entree);
          return { repertoire: repertoire, contenu: window.journalLectures, compresse: entree.compresse,
            taille: octets.length, nombre: r.nombre };
        }""")
        self.assertEqual(resultat["nombre"], 5)
        self.assertEqual(resultat["taille"], 1_500_000)
        lectures = [l for l in resultat["repertoire"] if l[0] != "slice"]
        self.assertTrue(lectures, "aucune lecture épiée : le test ne voit rien")
        self.assertTrue(all(l[0] == "arrayBuffer" for l in lectures), lectures)
        # Chaque lecture porte sur une tranche (jamais sur le fichier lui-même) : la fin (65 557 octets au plus),
        # puis le répertoire central.
        self.assertTrue(all(l[1] < len(octets) for l in lectures), lectures)
        self.assertLessEqual(max(l[2] for l in lectures), 65557)
        self.assertLess(sum(l[2] for l in lectures), 100_000)
        tranches = [l for l in resultat["repertoire"] if l[0] == "slice"]
        self.assertTrue(all(l[2] <= 65557 for l in tranches), tranches)
        # contenu : l'en-tête local (30 octets) puis les données de l'entrée, rien d'autre.
        lus = [l for l in resultat["contenu"] if l[0] != "slice"]
        self.assertTrue(all(l[1] < len(octets) for l in lus), lus)
        self.assertEqual(sorted(l[2] for l in lus), [30, resultat["compresse"]])


if __name__ == "__main__":
    unittest.main()
