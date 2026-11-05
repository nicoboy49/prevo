"""T215 — recette du « ZIP par morceaux » (zip-flux.js T226, import T227, export T228, limites T229) : sur de vrais gros
fichiers, l'aller-retour tient dans les deux modes, la mémoire est mesurée, et le ZIP de plus de 2 Go s'ouvre avec les
outils des gens.

SAUTÉE PAR DÉFAUT (plusieurs Go écrits sur le disque, de l'ordre d'une heure). La lancer seule sur le PC, à travers le
verrou du navigateur, depuis la racine du projet :
    PREVO_RECETTE_LOURDE=1 py -X utf8 -m unittest discover -s tests -p "test_zip_morceaux.py" -v
Variables facultatives : PREVO_RECETTE_SORTIE (fichier JSON des mesures ; défaut : prevo-recette-t215.json dans le
dossier temporaire du système), PREVO_RECETTE_GARDE_MO (garde mémoire, défaut 1536 : 1,5 Go), PREVO_RECETTE_ESSAI=1
(essai rapide du déroulé : petits volumes, quelques minutes ; ni ses tailles ni ses mesures ne valent recette) ;
PREVO_RECETTE_BESOIN_MO (mémoire libre exigée au-dessus de la garde avant un export de 2 Go, défaut 1800).

Navigateur : Chromium sans tête avec un profil PERSISTANT (sur le disque), comme le Chrome d'un utilisateur. Un
contexte incognito (new_context, celui des autres tests) garde tous les Blob et l'OPFS en mémoire : il mesurerait autre
chose (et ne tiendrait pas 2 Go). Le mode dossier écrit dans l'OPFS de ce profil (installer_dossier_simule), servi par
un seul ServeurStatique pour toute la classe (même origine, donc même OPFS, d'un lancement du navigateur à l'autre).

Garde mémoire : toutes les 100 ms, la mémoire libre du système (psutil.virtual_memory().available). Sous la garde, le
navigateur de test (et lui seul : les processus chrome lancés par ce test, jamais ceux de l'utilisateur) ou
l'extraction en cours sont tués, l'étape est notée « garde » dans les mesures et sautée.

Mesure (Echantillonneur, toutes les 100 ms, pendant chaque export et chaque import, du clic au fichier téléchargé ou à
la fenêtre « import terminé ») : octets privés des processus du navigateur de test, par genre (processus principal,
onglet = plus gros processus « renderer », GPU, utilitaires), somme (Chromium entier), mémoire libre du système (plus
bas relevé), place des Blob sur le disque du profil (blob_storage) ; à la fin, le pic que Windows a noté (peak_wset).

Étapes (méthodes dans l'ordre ; chacune réutilise le ZIP de la précédente) :
  01-03  comparaison avec T212 (mêmes documents, même mesure, docs/FORMAT.md §13), sur le jeu de charge
         (generer_demo.py --volume 300,2000) : 330 photos de 1 Mo (ZIP de 335 Mo) exportées par le serveur, en profil
         persistant puis en incognito (le contexte de T212) ; ce ZIP importé en mode dossier, puis réexporté ; 9 888
         photos de 34 Kio (9 913 entrées) exportées par le serveur, sur le jeu de charge de 20 000 OT (16 992
         demandes : assez pour les citer) ;
  04     la grosse base de T212 (test_zip_limites : 20 000 OT, journal de 45 Mo), export « données seules » : ce que
         coûtent les tables, sans aucun document (avec ses documents, elle dépasserait la garde sur ce PC) ;
  05     export, mode serveur, plus de 2 Go : jeu de charge dont les données citent 220 documents fictifs
         incompressibles de 9,5 Mo (110 photos .jpg, stockées ; 110 notices .pdf, compressées) ; ZIP contrôlé : plus
         de 2 Go (2^31 octets), sans ZIP64, testzip() à None, chaque document identique à la source (SHA-256), chaque
         CSV identique au disque du serveur. Tenté seulement si la mémoire libre couvre la garde plus 1,8 Go (Chromium
         monte à 1,5 Go) ; sinon, ou si la garde l'arrête, l'étape est sautée et les étapes 06 à 09 reçoivent un ZIP
         RECOMPOSÉ : un vrai export du même serveur aux documents réduits à 1 Ko, refait par Python avec les documents
         de 9,5 Mo (zip_comme_zipflux : disposition de ZipFlux ; notices compressées par zlib) et le manifeste mis à
         jour ;
  06     ce ZIP importé en mode dossier (base f3, OPFS) : documents et tables identiques (le journal a en plus la
         ligne de l'import) ;
  07     export du mode dossier (navigateur relancé, même OPFS) : ZIP contrôlé de même ; tenté seulement si la
         mémoire libre le permet (comme 05) ;
  08     ce ZIP-là (sinon celui de l'étape 05) importé en mode serveur (copie du jeu f3) : avec quota_documents_mo à
         2 048, l'ancien défaut (et les comptes, que demande un fichier de réglages), refus propre (« Dossier des
         documents plein », tables inchangées) ; avec les réglages par défaut (4 096 depuis T250, comme l'import ZIP),
         documents (renommés par le serveur) et tables identiques ;
  09     le ZIP de plus de 2 Go de l'étape 05 ouvert par Python (zipfile.testzip), tar (bsdtar de Windows : -tf, puis
         -xf de la première entrée et de la plus lointaine) et « Extraire tout » (moteur ZIP du Shell de Windows, le
         même que l'Explorateur : Shell.Application, CopyHere 4 + 16) : nombre, tailles et SHA-256 de tous les
         fichiers ;
  10     près de 4 Go, écrit DANS LA PAGE par ZipFlux.ecrivain : 40 entrées stockées de 97,5 Mo (3 900 Mo) ; ouvert
         par Python, tar et Extraire tout. Entrées de plus de 10 Mo : Chromium garde en mémoire les 5 premiers Mo de
         chaque Blob écrit en flux (le reste va sur le disque) ; 400 entrées de 10 Mo y tiendraient 2 Go ;
  11     près de 4 Go, 400 entrées stockées de 9,75 Mo (la forme d'un vrai export), écrites par zip_comme_zipflux, la
         copie Python de l'écrivain pour les entrées stockées, vérifiée d'abord à l'octet contre ZipFlux.ecrivain sur
         un petit ZIP ; ouvert par Python, tar et Extraire tout.

Règle numéro un : jamais de données réelles (jeux de test et documents fictifs, dossiers temporaires, OPFS et profil
du navigateur de test, supprimés à la fin).
"""
import hashlib
import json
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
import zlib
from datetime import datetime
from pathlib import Path

from commun import (RACINE, SCRIPT_SANS_AIDE, ServeurPrevo, ServeurStatique, attendre_pret, installer_dossier_simule,
                    preregler_profil)

RECETTE = os.environ.get("PREVO_RECETTE_LOURDE") == "1"
ESSAI = os.environ.get("PREVO_RECETTE_ESSAI") == "1"            # petits volumes : vérifie le déroulé, rien de plus
if RECETTE:                                    # rien de lourd à l'import quand la recette est sautée
    import psutil
    from playwright.sync_api import sync_playwright
    import test_zip_import as tzi
    import test_zip_limites as tzl
    from jeux_formats import copier_jeu

MIO = 1024 * 1024
DEUX_GO = 1 << 31                              # au-delà, une position ou une taille lue comme signée devient négative
GARDE = int(os.environ.get("PREVO_RECETTE_GARDE_MO", "1536")) * MIO
DELAI_MS = 30 * 60 * 1000                      # une étape : 30 minutes au plus
SORTIE = Path(os.environ.get("PREVO_RECETTE_SORTIE") or Path(tempfile.gettempdir()) / "prevo-recette-t215.json")
NOM_DOSSIER = "donnees-recette-t215"
TAR = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tar.exe"
DOCUMENTS_2GO = 20 if ESSAI else 220         # 220 × 9,5 Mo = 2 090 Mo : le ZIP dépasse 2^31 octets
TAILLE_2GO = 19 * MIO // 2
PLUS_DE_2GO = not ESSAI
PHOTOS_T212 = (30, 300) if ESSAI else (330, 9950 - 37 - 25)  # cas A et B de T212 (B : 9 913 entrées)
ENTREES_4GO = (4, 10) if ESSAI else (40, 400)                # étapes 10 et 11
BESOINS_MO = {}                                                    # attente avant une étape (setUp)
# Export de 2 Go : Chromium à 1,54 Go au pic (première recette, garde à 68,7 s), plus une marge pour ce que fait
# l'utilisateur du PC pendant ce temps : l'export réel n'est tenté que si la mémoire libre couvre la garde et ce besoin.
BESOIN_EXPORT_2GO_MO = int(os.environ.get("PREVO_RECETTE_BESOIN_MO") or (0 if ESSAI else 1800))
DATE_ZIP = (2026, 11, 5, 12, 0, 0)             # date des ZIP écrits par l'écrivain (étapes 10 et 11)
MESURES = {}
ETAT = {}                                      # ZIP et sommes passés d'une étape à la suivante


def mo(octets):
    return round(octets / MIO, 1)


def sha256(octets):
    return hashlib.sha256(octets).hexdigest()


def sha256_fichier(chemin):
    empreinte = hashlib.sha256()
    with open(chemin, "rb") as fichier:
        for morceau in iter(lambda: fichier.read(4 * MIO), b""):
            empreinte.update(morceau)
    return empreinte.hexdigest()


def noter(cle, valeur):
    MESURES[cle] = valeur
    SORTIE.write_text(json.dumps(MESURES, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[T215] %s %s" % (cle, json.dumps(valeur, ensure_ascii=False)), flush=True)


def disponible():
    return psutil.virtual_memory().available


# ---------------------------------------------------------------------------
# Processus du navigateur de test, garde mémoire, échantillonneur
# ---------------------------------------------------------------------------

_GENRES = {}


def processus_chromium():
    """Processus chrome lancés par CE test (descendants de ce processus Python) : jamais ceux de l'utilisateur."""
    resultat = []
    for processus in psutil.Process().children(recursive=True):
        try:
            nom = processus.name().lower()
        except psutil.Error:
            continue
        if "chrom" in nom or "headless" in nom:
            resultat.append(processus)
    return resultat


def genre(processus):
    """'principal', 'onglet' (renderer), 'gpu', 'utilitaire' ou 'autre', d'après la ligne de commande (par pid)."""
    if processus.pid not in _GENRES:
        try:
            ligne = " ".join(processus.cmdline())
        except psutil.Error:
            return "autre"
        if "--type=" not in ligne:
            _GENRES[processus.pid] = "principal"
        else:
            _GENRES[processus.pid] = next((nom for cle, nom in (("renderer", "onglet"), ("gpu-process", "gpu"),
                                                                ("utility", "utilitaire")) if "--type=" + cle in ligne),
                                          "autre")
    return _GENRES[processus.pid]


def releve_chromium():
    """{genre: octets privés (somme)}, plus 'onglet_max' (le plus gros onglet) et 'total'."""
    par = {"principal": 0, "onglet": 0, "gpu": 0, "utilitaire": 0, "autre": 0, "onglet_max": 0}
    for processus in processus_chromium():
        try:
            prive = processus.memory_info().private
        except psutil.Error:
            continue
        cle = genre(processus)
        par[cle] += prive
        if cle == "onglet":
            par["onglet_max"] = max(par["onglet_max"], prive)
    par["total"] = par["principal"] + par["onglet"] + par["gpu"] + par["utilitaire"] + par["autre"]
    return par


def taille_dossier(dossier):
    total = 0
    if dossier is not None and dossier.exists():
        for racine, _, fichiers in os.walk(dossier):
            for nom in fichiers:
                try:
                    total += os.path.getsize(os.path.join(racine, nom))
                except OSError:
                    pass
    return total


class Garde(threading.Thread):
    """Toutes les 100 ms : sous GARDE octets libres, tue le navigateur de test (et les processus de `autres`)."""

    def __init__(self):
        super().__init__(daemon=True)
        self.arret = threading.Event()
        self.declenchee = None
        self.autres = []
        self.etape = ""

    def run(self):
        while not self.arret.is_set():
            libre = disponible()
            if libre < GARDE and self.declenchee is None:
                victimes = processus_chromium() + [p for p in self.autres if p.is_running()]
                self.declenchee = {"etape": self.etape, "libre_mo": mo(libre), "heure": datetime.now().isoformat(
                    timespec="seconds"), "processus_tues": len(victimes)}
                for processus in victimes:
                    try:
                        processus.kill()
                    except psutil.Error:
                        pass
            time.sleep(0.1)


GARDIEN = None


class Echantillonneur(threading.Thread):
    """Pics pendant une opération (voir le docstring du module)."""

    def __init__(self, blob_storage=None):
        super().__init__(daemon=True)
        self.arret = threading.Event()
        self.blob_storage = blob_storage
        self.pics = {"total": 0, "principal": 0, "onglet_max": 0, "gpu": 0, "utilitaire": 0}
        self.libre_min = disponible()
        self.disque_max = 0
        self.echantillons = 0

    def run(self):
        while not self.arret.is_set():
            par = releve_chromium()
            for cle in self.pics:
                self.pics[cle] = max(self.pics[cle], par[cle])
            self.libre_min = min(self.libre_min, disponible())
            if self.echantillons % 10 == 0:
                self.disque_max = max(self.disque_max, taille_dossier(self.blob_storage))
            self.echantillons += 1
            time.sleep(0.1)

    def arreter(self):
        self.arret.set()
        self.join()
        return {"chromium_pic_mo": mo(self.pics["total"]), "onglet_pic_mo": mo(self.pics["onglet_max"]),
                "principal_pic_mo": mo(self.pics["principal"]), "gpu_pic_mo": mo(self.pics["gpu"]),
                "libre_min_mo": mo(self.libre_min), "blob_disque_pic_mo": mo(self.disque_max),
                "echantillons": self.echantillons}


def pics_windows():
    """Pics de pages en mémoire notés par Windows depuis le lancement du navigateur (peak_wset)."""
    pics = {"onglet": 0, "principal": 0, "somme": 0}
    for processus in processus_chromium():
        try:
            pic = processus.memory_info().peak_wset
        except psutil.Error:
            continue
        cle = genre(processus)
        if cle in ("onglet", "principal"):
            pics[cle] = max(pics[cle], pic)
        pics["somme"] += pic
    return {cle: mo(valeur) for cle, valeur in pics.items()}


class GardeDeclenchee(Exception):
    pass


# ---------------------------------------------------------------------------
# Navigateur à profil persistant
# ---------------------------------------------------------------------------

class Navigateur:
    """Chromium sans tête, profil persistant `profil` (sur le disque), téléchargements dans `telechargements`."""

    def __init__(self, cas, profil, telechargements, dossier_simule=False, incognito=False):
        self.cas = cas
        self.incognito = incognito
        self.profil = Path(profil)
        self.telechargements = Path(telechargements)
        self.dossier_simule = dossier_simule
        self.erreurs = []

    def __enter__(self):
        self.telechargements.mkdir(parents=True, exist_ok=True)
        self.playwright = sync_playwright().start()
        reglages = {"locale": "fr-FR", "viewport": {"width": 1280, "height": 800}, "bypass_csp": True,
                    "accept_downloads": True}
        try:
            if self.incognito:                 # comme CasNavigateur et T212 : tout en mémoire
                self.navigateur = self.playwright.chromium.launch(headless=True,
                                                                  downloads_path=str(self.telechargements))
                self.contexte = self.navigateur.new_context(**reglages)
            else:
                self.contexte = self.playwright.chromium.launch_persistent_context(
                    str(self.profil), headless=True, downloads_path=str(self.telechargements), **reglages)
        except BaseException:
            self.playwright.stop()
            raise
        self.contexte.set_default_timeout(DELAI_MS)
        self.contexte.add_init_script(SCRIPT_SANS_AIDE)
        preregler_profil(self.contexte, "responsable")
        if self.dossier_simule:
            installer_dossier_simule(self.contexte, NOM_DOSSIER)
        self.page = self.contexte.pages[0] if self.contexte.pages else self.contexte.new_page()
        self.page.on("console", lambda m: m.type == "error" and self.erreurs.append(
            "%s (%s)" % (m.text, (m.location or {}).get("url", ""))))
        self.page.on("pageerror", lambda e: self.erreurs.append(str(e)))
        return self

    def __exit__(self, *exception):
        for fermer in ([self.contexte.close] + ([self.navigateur.close] if self.incognito else [])
                       + [self.playwright.stop]):
            try:
                fermer()
            except Exception:                  # navigateur tué par la garde
                pass
        return False

    @property
    def blob_storage(self):
        return self.profil / "Default" / "blob_storage"

    def erreurs_inattendues(self, autorisees=()):
        return [e for e in self.erreurs if not any(re.search(motif, e) for motif in autorisees)]


# ---------------------------------------------------------------------------
# ZIP : lecture par Python, écriture comme ZipFlux
# ---------------------------------------------------------------------------

def decrire_zip(chemin):
    """Tout ce que la recette contrôle d'un ZIP, lu par Python une entrée à la fois : csv {nom: octets} (entrées de la
    racine, manifeste compris), documents {nom: sha256}, et la structure (ZIP64, positions au-delà de 2^31)."""
    taille = chemin.stat().st_size
    with open(chemin, "rb") as fichier:
        fichier.seek(max(0, taille - 22 - 20))
        queue = fichier.read()
    zip64 = b"PK\x06\x07" in queue or b"PK\x06\x06" in queue
    debut = time.monotonic()
    csv, documents, methodes, extras = {}, {}, {}, 0
    with zipfile.ZipFile(chemin) as archive:
        infos = archive.infolist()
        for info in infos:
            methodes[info.compress_type] = methodes.get(info.compress_type, 0) + 1
            extras += 1 if info.extra else 0
            if info.filename.startswith("documents/"):
                empreinte = hashlib.sha256()
                with archive.open(info) as entree:
                    for morceau in iter(lambda: entree.read(4 * MIO), b""):
                        empreinte.update(morceau)
                documents[info.filename[len("documents/"):]] = empreinte.hexdigest()
            else:
                csv[info.filename] = archive.read(info)
        lecture = round(time.monotonic() - debut, 1)
        debut = time.monotonic()
        mauvaise = archive.testzip()
        duree_testzip = round(time.monotonic() - debut, 1)
    return {
        "octets": taille, "zip_mo": mo(taille), "entrees": len(infos), "documents": documents, "csv": csv,
        "zip64": zip64, "extras": extras, "stockees": methodes.get(0, 0), "compressees": methodes.get(8, 0),
        "position_max": max(i.header_offset for i in infos),
        "plus_loin": max(infos, key=lambda i: i.header_offset).filename, "au_dela_de_2go": sum(1 for i in infos
                                                                                    if i.header_offset >= DEUX_GO),
        "testzip": mauvaise, "testzip_s": duree_testzip, "lecture_s": lecture,
    }


def resume_zip(decrit):
    return {cle: decrit[cle] for cle in ("zip_mo", "octets", "entrees", "stockees", "compressees", "zip64",
                                        "au_dela_de_2go", "testzip", "testzip_s")} | {
        "documents": len(decrit["documents"])}


def heure_et_jour_dos(annee, mois, jour, heure, minute, seconde):
    return (heure << 11) | (minute << 5) | (seconde >> 1), ((annee - 1980) << 9) | (mois << 5) | jour


def zip_comme_zipflux(chemin, entrees, date=DATE_ZIP):
    """Écrit `entrees` ([(nom, octets)] : stockées ; ou [(nom, octets, stocker)]) avec la disposition de
    ZipFlux.ecrivain({ date }) (js/modules/zip-flux.js) : en-tête local de 30 octets sans extra ni descripteur,
    version 2.0, drapeau UTF-8, répertoire central sans extra ni commentaire, fin de 22 octets, jamais de ZIP64.
    Entrées stockées : octet pour octet ce qu'écrit ZipFlux (vérifié à l'étape 11) ; entrées compressées : deflate de
    zlib (Python), dont les octets peuvent différer de ceux de CompressionStream. Rend la taille écrite."""
    heure, jour = heure_et_jour_dos(*date)
    centrales = []
    position = 0
    with open(chemin, "wb") as fichier:
        for nom, octets, *choix in entrees:
            stocker = choix[0] if choix else True
            octets_nom = nom.encode("utf-8")
            crc = zlib.crc32(octets)
            taille = len(octets)
            if not stocker:
                compresseur = zlib.compressobj(6, zlib.DEFLATED, -15)
                octets = compresseur.compress(octets) + compresseur.flush()
            methode, compresse = (0, taille) if stocker else (8, len(octets))
            locale = struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0x0800, methode, heure, jour, crc, compresse, taille,
                                 len(octets_nom), 0) + octets_nom
            centrales.append(struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0x0800, methode, heure, jour, crc,
                                         compresse, taille, len(octets_nom), 0, 0, 0, 0, 0, position) + octets_nom)
            fichier.write(locale)
            fichier.write(octets)
            position += len(locale) + compresse
        repertoire = b"".join(centrales)
        fichier.write(repertoire)
        fichier.write(struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(centrales), len(centrales), len(repertoire),
                                  position, 0))
    return position + len(repertoire) + 22


# ---------------------------------------------------------------------------
# Bases fabriquées
# ---------------------------------------------------------------------------

def ecrire_documents(dossier, documents):
    """Écrit les documents fictifs un à un ({nom: (taille, graine, signature)}) → {nom: sha256}."""
    dossier.mkdir(parents=True, exist_ok=True)
    empreintes = {}
    for nom, (taille, graine, signature) in documents.items():
        octets = tzl.octets_fictifs(taille, graine, signature)
        (dossier / nom).write_bytes(octets)
        empreintes[nom] = sha256(octets)
    return empreintes


def jeu_de_charge(dossier, volume="300,2000"):
    """CSV d'un jeu de charge écrits dans `dossier` → {nom: octets}. generer_demo.py --volume 300,2000 : 300
    équipements, 609 demandes, 2,5 Mo de CSV ; 300,20000 : 16 992 demandes, 18 Mo de CSV (journal court)."""
    charge = Path(tempfile.mkdtemp(prefix="prevo-recette-charge-"))
    try:
        subprocess.run([sys.executable, "-X", "utf8", str(tzl.GENERATEUR), "--volume", volume, "--sortie",
                        str(charge)], check=True, capture_output=True, cwd=str(RACINE), timeout=600)
        fichiers = {table + ".csv": (charge / (table + ".csv")).read_bytes() for table in tzl.TABLES}
    finally:
        shutil.rmtree(charge, ignore_errors=True)
    tzl.ecrire_dossier(dossier, fichiers)
    return fichiers


def documents_2go():
    """220 documents de 9,5 Mo : 110 photos (JPEG, stockées dans le ZIP), 110 notices (PDF, compressées)."""
    photos = {"photo-recette-%03d.jpg" % n: (TAILLE_2GO, "recette-photo-%d" % n, b"\xff\xd8\xff\xe0")
              for n in range(DOCUMENTS_2GO // 2)}
    notices = {"notice-recette-%03d.pdf" % n: (TAILLE_2GO, "recette-notice-%d" % n, b"%PDF-1.4\n")
               for n in range(DOCUMENTS_2GO // 2)}
    return photos, notices


# ---------------------------------------------------------------------------
# « Extraire tout » : moteur ZIP du Shell de Windows
# ---------------------------------------------------------------------------

EXTRAIRE_TOUT_PS1 = r"""param([string]$Zip, [string]$Cible, [int]$Attendus, [long]$Octets, [int]$Delai)
$ErrorActionPreference = 'Stop'
$debut = Get-Date
try {
  $sh = New-Object -ComObject Shell.Application
  $source = $sh.NameSpace($Zip)
  if ($null -eq $source) { Write-Output 'ERREUR NameSpace(zip) rend null'; exit 2 }
  $elements = $source.Items()
  Write-Output ('ELEMENTS ' + $elements.Count)
  $sh.NameSpace($Cible).CopyHere($elements, 4 + 16)
} catch { Write-Output ('ERREUR ' + $_.Exception.Message); exit 3 }
$avant = -1; $immobile = 0
while ($true) {
  Start-Sleep -Milliseconds 1000
  $fichiers = @(Get-ChildItem -LiteralPath $Cible -Recurse -File -ErrorAction SilentlyContinue)
  $total = [long]0; foreach ($f in $fichiers) { $total += $f.Length }
  $secondes = [int]((Get-Date) - $debut).TotalSeconds
  if ($fichiers.Count -ge $Attendus -and $total -ge $Octets) {
    Write-Output "FINI $($fichiers.Count) $total $secondes"; exit 0
  }
  if ($total -eq $avant) { $immobile++ } else { $immobile = 0 }
  $avant = $total
  if ($immobile -ge 180 -or $secondes -gt $Delai) { Write-Output "ARRET $($fichiers.Count) $total $secondes"; exit 1 }
}
"""


# ---------------------------------------------------------------------------
# La recette
# ---------------------------------------------------------------------------

@unittest.skipUnless(RECETTE, "recette lourde du ZIP par morceaux (T215) : PREVO_RECETTE_LOURDE=1, voir le docstring")
class TestZipParMorceaux(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global GARDIEN
        super().setUpClass()
        cls.temporaire = Path(tempfile.mkdtemp(prefix="prevo-recette-t215-"))
        cls.addClassCleanup(shutil.rmtree, cls.temporaire, True)
        GARDIEN = Garde()
        GARDIEN.start()
        cls.addClassCleanup(GARDIEN.arret.set)
        cls.statique = ServeurStatique(RACINE)
        cls.statique.demarrer()
        cls.addClassCleanup(cls.statique.arreter)
        noter("depart", {"libre_mo": mo(disponible()), "garde_mo": mo(GARDE), "temporaire": str(cls.temporaire),
                         "disque_libre_go": round(shutil.disk_usage(cls.temporaire).free / (1024 * MIO), 1),
                         "heure": datetime.now().isoformat(timespec="seconds")})

    def setUp(self):
        GARDIEN.etape = self._testMethodName
        GARDIEN.declenchee = None
        GARDIEN.autres = []
        # Avant une étape gourmande, attendre (10 min au plus) que la mémoire libre couvre la garde et le besoin
        # estimé ; sinon la lancer quand même, sous la garde. Après une garde : laisser Windows rendre la mémoire.
        besoin = BESOINS_MO.get(self._testMethodName[:7], 0) * MIO
        fin = time.monotonic() + (600 if besoin else 120)
        while disponible() < GARDE + max(besoin, 300 * MIO) and time.monotonic() < fin:
            time.sleep(1)
        if disponible() < GARDE + 300 * MIO:
            noter(self._testMethodName, {"saute": "mémoire libre au départ", "libre_mo": mo(disponible())})
            self.skipTest("mémoire libre insuffisante au départ : %s Mo" % mo(disponible()))

    # -- mesure ----------------------------------------------------------------------------------------------------

    def mesurer(self, navigateur, action):
        """(mesure, résultat de l'action) ; GardeDeclenchee si la garde a tué le navigateur pendant l'action."""
        navigateur.page.wait_for_timeout(3000)
        avant = releve_chromium()
        libre_avant = disponible()
        echantillonneur = Echantillonneur(navigateur.blob_storage)
        echantillonneur.start()
        debut = time.monotonic()
        try:
            resultat = action()
        except Exception as erreur:
            pics = echantillonneur.arreter()
            if GARDIEN.declenchee:
                raise GardeDeclenchee(dict(GARDIEN.declenchee, duree_s=round(time.monotonic() - debut, 1),
                                           **pics)) from erreur
            raise
        duree = round(time.monotonic() - debut, 1)
        pics = echantillonneur.arreter()
        navigateur.page.wait_for_timeout(2000)
        apres = releve_chromium()
        return dict(duree_s=duree, chromium_avant_mo=mo(avant["total"]), onglet_avant_mo=mo(avant["onglet_max"]),
                    principal_avant_mo=mo(avant["principal"]), libre_avant_mo=mo(libre_avant), **pics,
                    chromium_apres_mo=mo(apres["total"]), pics_windows=pics_windows()), resultat

    def etape(self, cle, fonction):
        """Lance une étape ; garde déclenchée → notée et sautée."""
        try:
            return fonction()
        except GardeDeclenchee as garde:
            noter(cle, {"garde": garde.args[0]})
            self.skipTest("garde mémoire déclenchée : %s" % json.dumps(garde.args[0], ensure_ascii=False))

    # -- actions dans Prévo ----------------------------------------------------------------------------------------

    def exporter(self, page, destination, bouton="#btn-export-zip"):
        """Clic sur « Exporter en ZIP » (`bouton`) (et « Continuer l'export complet » si l'avertissement T222
        s'ouvre), fichier téléchargé déplacé en `destination` → {avertissement, telechargement_s}."""
        telechargements = []

        def noter_telechargement(telechargement):
            telechargements.append(telechargement)

        page.on("download", noter_telechargement)
        avertissement = False
        try:
            page.click(bouton)
            fin = time.monotonic() + DELAI_MS / 1000
            while not telechargements:
                self.assertLess(time.monotonic(), fin, "export : rien de téléchargé")
                if page.locator("#export-zip-refus").count():
                    self.fail("export refusé : " + page.inner_text("#export-zip-refus"))
                if not avertissement and page.locator("#export-zip-avertissement").count():
                    avertissement = True
                    page.locator("dialog .fenetre-actions button").filter(has_text="Continuer l'export complet").click()
                page.wait_for_timeout(250)
            debut = time.monotonic()
            telecharge = Path(telechargements[0].path())         # attend la fin de l'écriture du fichier
            duree = round(time.monotonic() - debut, 1)
        finally:
            page.remove_listener("download", noter_telechargement)
        self.assertRegex(telechargements[0].suggested_filename,
                         r"^prevo-export-\d{4}-\d{2}-\d{2}(-sans-documents)?\.zip$")
        if destination.exists():
            destination.unlink()
        shutil.move(str(telecharge), str(destination))
        return {"avertissement": avertissement, "telechargement_s": duree}

    def importer(self, page, chemin, documents):
        page.set_input_files("#fichier-import-zip", str(chemin))
        page.wait_for_selector("#confirmation-import-zip", timeout=DELAI_MS)
        self.assertEqual(page.evaluate(
            "Number(document.getElementById('confirmation-import-zip').dataset.documents)"), documents)
        page.click(tzi.BOUTON_REMPLACER)
        page.wait_for_selector("#import-zip-termine, #import-zip-echec, #import-zip-refus", timeout=DELAI_MS)
        self.assertEqual(page.locator("#import-zip-echec, #import-zip-refus").count(), 0,
                         page.inner_text("dialog") if page.locator("dialog").count() else "")
        termine = re.sub(r"\s+", " ", page.inner_text("#import-zip-termine"))
        self.assertIn("24 tables remplacées, %d documents" % documents, termine)
        return termine

    def ouvrir_serveur(self, navigateur, serveur):
        page = navigateur.page
        page.goto(serveur.url + "/#/parametres")
        attendre_pret(page, DELAI_MS)
        page.wait_for_selector("#btn-export-zip")
        page.wait_for_load_state("networkidle")
        return page

    def ouvrir_dossier(self, navigateur, ecrire_jeu):
        """Mode dossier sur l'OPFS du profil : jeu f3 écrit d'abord (ecrire_jeu), sinon « Reprendre »."""
        page = navigateur.page
        page.goto(self.statique.url + "/index.html")
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        if ecrire_jeu:
            page.evaluate(tzi.ECRIRE_OPFS_JS, [NOM_DOSSIER, {c: tzi.en_base64(o) for c, o in
                                                             tzi.fichiers_du_jeu("f3-v1.2.0").items()}])
            page.click("#btn-dossier")
        else:
            page.click("#btn-reprendre")
        attendre_pret(page, DELAI_MS)
        self.assertEqual(page.evaluate("App.mode"), "dossier")
        page.evaluate("location.hash = '#/parametres'")
        page.wait_for_selector("#btn-import-zip")
        return page

    def opfs(self, page, debuts=None):
        return page.evaluate(tzl.EMPREINTES_OPFS_JS, [NOM_DOSSIER, debuts or {}])

    def sans_erreur(self, navigateur, autorisees=()):
        self.assertEqual(navigateur.erreurs_inattendues(autorisees), [])

    # -- contrôles ---------------------------------------------------------------------------------------------------

    def controler_zip(self, decrit, sources, plus_de_2go=True):
        """ZIP écrit par Prévo : sans ZIP64 ni extra, CRC justes (testzip), chaque document de `sources` ({nom:
        sha256}) présent et identique."""
        self.assertIsNone(decrit["testzip"])
        self.assertFalse(decrit["zip64"], "ZIP64 trouvé : Prévo n'en écrit jamais")
        self.assertEqual(decrit["extras"], 0)
        if plus_de_2go:
            self.assertGreater(decrit["octets"], DEUX_GO)
            self.assertGreater(decrit["au_dela_de_2go"], 0)
        self.assertEqual(sorted(decrit["documents"]), sorted(sources))
        for nom, empreinte in sources.items():
            self.assertEqual(decrit["documents"][nom], empreinte, nom)
        self.assertIn("manifeste.json", decrit["csv"])
        manifeste = json.loads(decrit["csv"]["manifeste.json"].decode("utf-8"))
        decrits = {f["nom"]: f["sha256"] for f in manifeste["fichiers"]}
        for nom, empreinte in sources.items():
            self.assertEqual(decrits["documents/" + nom], empreinte, nom)
        self.assertNotIn("manquants", manifeste)

    def controler_import(self, decrit, csv_ecrits, documents_ecrits, nom_zip, prefixe):
        """Rien de perdu à l'import de `decrit` : chaque document écrit à l'octet (nom rendu : `prefixe` puis le nom du
        ZIP), chaque table identique (noms rendus remis), le journal avec en plus la seule ligne de l'import.
        csv_ecrits {table: octets}, documents_ecrits {nom: sha256}."""
        par_empreinte = {}
        for nom, empreinte in documents_ecrits.items():
            par_empreinte.setdefault(empreinte, []).append(nom)
        rendus = {}
        for nom, empreinte in decrit["documents"].items():
            candidats = [rendu for rendu in par_empreinte.get(empreinte, []) if re.fullmatch(prefixe + re.escape(nom),
                                                                                             rendu)]
            self.assertEqual(len(candidats), 1, "document perdu ou changé : " + nom)
            rendus[nom] = candidats[0]
        for table in tzl.TABLES:
            attendu = decrit["csv"][table + ".csv"]
            if table in tzl.TABLES_A_DOCUMENTS:
                attendu = tzl.remettre_noms(attendu, rendus)
            obtenu = csv_ecrits[table]
            if table == "journal":
                self.assertTrue(obtenu.startswith(attendu), tzl.premier_ecart(obtenu, attendu))
                self.assertRegex(obtenu[len(attendu):].decode("utf-8"),
                                 r"^[^\r\n]*;parametres;[^\r\n]*import ZIP : %s, 24 tables[^\r\n]*\r\n$"
                                 % re.escape(nom_zip))
            else:
                self.assertTrue(obtenu == attendu, table + " : " + tzl.premier_ecart(obtenu, attendu))
        return rendus

    def controler_opfs(self, page, decrit, nom_zip):
        journal = len(decrit["csv"]["journal.csv"])
        contenu = self.opfs(page, {"journal.csv": journal})
        self.assertEqual(contenu["journal.csv"]["debut"], sha256(decrit["csv"]["journal.csv"]))
        self.assertRegex(contenu["journal.csv"]["suite"], r"^[^\r\n]*;parametres;[^\r\n]*import ZIP : %s, 24 tables"
                                                          r"[^\r\n]*\r\n$" % re.escape(nom_zip))
        for table in tzl.TABLES:
            if table != "journal":
                self.assertEqual(contenu[table + ".csv"]["sha256"], sha256(decrit["csv"][table + ".csv"]), table)
        documents = {chemin[len("documents/"):]: d["sha256"] for chemin, d in contenu.items()
                     if chemin.startswith("documents/")}
        for nom, empreinte in decrit["documents"].items():
            self.assertEqual(documents.get(nom), empreinte, "document perdu ou changé : " + nom)
        return contenu

    # -- outils d'ouverture ------------------------------------------------------------------------------------------

    def ouvrir_par_tar(self, chemin, decrit):
        debut = time.monotonic()
        liste = subprocess.run([str(TAR), "-tf", str(chemin)], capture_output=True, timeout=1800)
        noms = [n for n in liste.stdout.decode("utf-8", "replace").splitlines() if n and not n.endswith("/")]
        resultat = {"liste_code": liste.returncode, "liste_noms": len(noms),
                    "liste_s": round(time.monotonic() - debut, 1),
                    "liste_erreur": liste.stderr.decode("utf-8", "replace")[-300:]}
        extraits = ["documents/" + next(iter(decrit["documents"])), decrit["plus_loin"]]
        cible = self.temporaire / "tar"
        shutil.rmtree(cible, ignore_errors=True)
        cible.mkdir()
        debut = time.monotonic()
        sortie = subprocess.run([str(TAR), "-xf", str(chemin), "-C", str(cible)] + extraits, capture_output=True,
                                timeout=1800)
        resultat.update({"extraction_code": sortie.returncode, "extraction_s": round(time.monotonic() - debut, 1),
                         "extraction_erreur": sortie.stderr.decode("utf-8", "replace")[-300:],
                         "extraits": extraits, "extraits_justes": sum(1 for nom in extraits if self.juste(
                             cible / nom, nom, decrit))})
        shutil.rmtree(cible, ignore_errors=True)
        return resultat

    @staticmethod
    def juste(fichier, nom, decrit):
        """Vrai si `fichier` (extrait) a l'empreinte de l'entrée `nom` du ZIP décrit."""
        if not fichier.is_file():
            return False
        if nom.startswith("documents/"):
            attendu = decrit["documents"].get(nom[len("documents/"):])
        else:
            attendu = sha256(decrit["csv"][nom]) if nom in decrit["csv"] else None
        return attendu is not None and sha256_fichier(fichier) == attendu

    def extraire_tout(self, chemin, decrit):
        """« Extraire tout » par le Shell de Windows → résultat (nombre, octets, SHA-256 justes, durée, message)."""
        cible = self.temporaire / "extraire-tout"
        shutil.rmtree(cible, ignore_errors=True)
        cible.mkdir()
        script = self.temporaire / "extraire_tout.ps1"
        script.write_text(EXTRAIRE_TOUT_PS1, encoding="utf-8-sig")
        attendus = decrit["entrees"]
        with zipfile.ZipFile(chemin) as archive:
            octets = sum(info.file_size for info in archive.infolist())
        debut = time.monotonic()
        processus = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                      "-File", str(script), str(chemin), str(cible), str(attendus), str(octets),
                                      "3600"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        GARDIEN.autres = [psutil.Process(processus.pid)]
        libre_min = disponible()
        while processus.poll() is None:
            libre_min = min(libre_min, disponible())
            time.sleep(0.5)
        GARDIEN.autres = []
        sortie = processus.communicate()[0].decode("utf-8", "replace").strip()
        duree = round(time.monotonic() - debut, 1)
        fichiers = [p for p in cible.rglob("*") if p.is_file()]
        resultat = {"code": processus.returncode, "sortie": sortie[-400:], "duree_s": duree, "fichiers": len(fichiers),
                    "attendus": attendus, "octets": sum(p.stat().st_size for p in fichiers), "octets_attendus": octets,
                    "libre_min_mo": mo(libre_min), "garde": GARDIEN.declenchee}
        justes = 0
        faux = []
        for p in fichiers:
            nom = p.relative_to(cible).as_posix()
            if self.juste(p, nom, decrit):
                justes += 1
            else:
                faux.append(nom)
        resultat.update({"sha256_justes": justes, "faux": faux[:10]})
        shutil.rmtree(cible, ignore_errors=True)
        return resultat

    def ouvrir_par_les_outils(self, cle, chemin, decrit):
        """Python (déjà fait par decrire_zip), tar, Extraire tout ; résultats notés sous `cle` ; s'arrête en échec
        précis si Extraire tout échoue (décision de Nicolas)."""
        resultat = {"zip_mo": decrit["zip_mo"], "entrees": decrit["entrees"],
                    "python": {"testzip": decrit["testzip"], "testzip_s": decrit["testzip_s"],
                               "lecture_s": decrit["lecture_s"], "documents_lus": len(decrit["documents"])}}
        resultat["tar"] = self.ouvrir_par_tar(chemin, decrit)
        resultat["extraire_tout"] = self.extraire_tout(chemin, decrit)
        noter(cle, resultat)
        if resultat["extraire_tout"]["garde"]:
            self.skipTest("garde mémoire pendant Extraire tout : %s" % resultat["extraire_tout"]["garde"])
        self.assertIsNone(decrit["testzip"])
        self.assertEqual(resultat["tar"]["liste_code"], 0, resultat["tar"])
        self.assertEqual(resultat["tar"]["liste_noms"], decrit["entrees"], resultat["tar"])
        self.assertEqual(resultat["tar"]["extraits_justes"], 2, resultat["tar"])
        extraction = resultat["extraire_tout"]
        self.assertEqual((extraction["code"], extraction["fichiers"], extraction["sha256_justes"]),
                         (0, decrit["entrees"], decrit["entrees"]), "Extraire tout a échoué : %s" % extraction)

    # -- 01-04 : comparaison avec T212 -------------------------------------------------------------------------------

    def charge(self, volume="300,2000"):
        if volume not in ETAT:
            ETAT[volume] = jeu_de_charge(self.temporaire / ("charge-" + volume.replace(",", "-")), volume)
        return ETAT[volume]

    def export_serveur_t212(self, cle, photos, taille, prefixe, incognito=False, volume="300,2000"):
        """Documents des cas de T212 (`photos` photos fictives de `taille` octets citées dans demandes.csv), sur un jeu
        de charge (`volume`) : la grosse base de T212 (onglet à 0,6 Go avant l'export) ajoutée à ces documents
        dépasserait la garde sur ce PC ; son coût propre est mesuré à part (étape 04)."""
        fichiers = self.charge(volume)
        source = self.temporaire / (cle + "-source")
        shutil.rmtree(source, ignore_errors=True)
        noms = ["%s-%05d.jpg" % (prefixe, n) for n in range(photos)]
        tzl.ecrire_dossier(source, fichiers | {"demandes.csv": tzl.poser_documents(fichiers["demandes.csv"], "photo",
                                                                                   noms)})
        sources = {nom[len("documents/"):]: sha256(octets) for nom, octets in fichiers.items()
                   if nom.startswith("documents/")}
        chemin = self.temporaire / (cle + ".zip")
        with ServeurPrevo(source=source) as serveur:
            sources.update(ecrire_documents(serveur.dossier / "documents", {
                nom: (taille, "%s-%d" % (prefixe, n), b"\xff\xd8\xff\xe0") for n, nom in enumerate(noms)}))
            with Navigateur(self, self.temporaire / ("profil-" + cle), self.temporaire / "telechargements",
                            incognito=incognito) as nav:
                page = self.ouvrir_serveur(nav, serveur)
                mesure, export = self.mesurer(nav, lambda: self.exporter(page, chemin))
                page.goto("about:blank")
                self.sans_erreur(nav)
        shutil.rmtree(source, ignore_errors=True)
        shutil.rmtree(self.temporaire / ("profil-" + cle), ignore_errors=True)
        decrit = decrire_zip(chemin)
        noter(cle, {"zip": resume_zip(decrit), "export": dict(mesure, **export)})
        self.controler_zip(decrit, sources, plus_de_2go=False)
        return chemin, decrit

    def test_01_t212_cas_a_export_serveur_385_mo(self):
        chemin, decrit = self.etape("01_t212_a_serveur",
                                    lambda: self.export_serveur_t212("01_t212_a_serveur", PHOTOS_T212[0], MIO,
                                                                     "photo-a"))
        self.assertEqual(decrit["entrees"], 25 + PHOTOS_T212[0])
        ETAT["zip_t212_a"] = (chemin, decrit)
        # Le même export dans un contexte incognito, comme T212 (CasNavigateur) : tout y reste en mémoire.
        chemin_i, _ = self.etape("01_t212_a_serveur_incognito", lambda: self.export_serveur_t212(
            "01_t212_a_serveur_incognito", PHOTOS_T212[0], MIO, "photo-a", incognito=True))
        chemin_i.unlink()

    def test_02_t212_cas_a_import_puis_export_dossier(self):
        if "zip_t212_a" not in ETAT:
            self.skipTest("l'étape 01 n'a pas produit son ZIP")
        chemin, decrit = ETAT["zip_t212_a"]
        profil = self.temporaire / "profil-02"
        chemin_2 = self.temporaire / "02_t212_a_dossier.zip"

        def deroule():
            with Navigateur(self, profil, self.temporaire / "telechargements", dossier_simule=True) as nav:
                page = self.ouvrir_dossier(nav, ecrire_jeu=True)
                mesure_import, termine = self.mesurer(nav, lambda: self.importer(page, chemin,
                                                                                 len(decrit["documents"])))
                self.sans_erreur(nav, [tzi.ERREUR_PING_ABSENT.pattern])
            with Navigateur(self, profil, self.temporaire / "telechargements", dossier_simule=True) as nav:
                page = self.ouvrir_dossier(nav, ecrire_jeu=False)
                mesure_export, export = self.mesurer(nav, lambda: self.exporter(page, chemin_2))
                self.sans_erreur(nav, [tzi.ERREUR_PING_ABSENT.pattern])
            return mesure_import, termine, mesure_export, export

        mesure_import, termine, mesure_export, export = self.etape("02_t212_a_dossier", deroule)
        shutil.rmtree(profil, ignore_errors=True)
        decrit_2 = decrire_zip(chemin_2)
        noter("02_t212_a_dossier", {"import": dict(mesure_import, termine=termine[:120]), "zip": resume_zip(decrit_2),
                                    "export": dict(mesure_export, **export)})
        self.controler_zip(decrit_2, decrit["documents"], plus_de_2go=False)
        chemin.unlink()
        chemin_2.unlink()

    def test_03_t212_cas_b_export_serveur_9950_entrees(self):
        # 24 CSV + manifeste : photos jusqu'à 9 913 entrées (T212 : 9 950 avec les 37 documents de la grosse base), sur
        # le jeu de charge de 20 000 OT (assez de demandes pour les citer).
        chemin, decrit = self.etape("03_t212_b_serveur", lambda: self.export_serveur_t212(
            "03_t212_b_serveur", PHOTOS_T212[1], 34 * 1024 + 512, "photo-b", volume="300,20000"))
        self.assertEqual(decrit["entrees"], 25 + PHOTOS_T212[1])
        chemin.unlink()

    def test_04_grosse_base_de_t212_donnees_seules(self):
        """Coût des TABLES seules : la grosse base de T212 (20 000 OT, journal de 45 Mo), export « données seules »."""
        source = self.temporaire / "grosse-base"
        tzl.grosse_base(source)
        chemin = self.temporaire / "04_grosse_base.zip"

        def deroule():
            with ServeurPrevo(source=source) as serveur:
                with Navigateur(self, self.temporaire / "profil-04", self.temporaire / "telechargements") as nav:
                    page = self.ouvrir_serveur(nav, serveur)
                    mesure, export = self.mesurer(nav, lambda: self.exporter(page, chemin,
                                                                             "#btn-export-donnees-seules"))
                    page.goto("about:blank")
                    self.sans_erreur(nav)
            return mesure, export

        mesure, export = self.etape("04_grosse_base_donnees_seules", deroule)
        shutil.rmtree(source, ignore_errors=True)
        shutil.rmtree(self.temporaire / "profil-04", ignore_errors=True)
        decrit = decrire_zip(chemin)
        noter("04_grosse_base_donnees_seules", {"zip": resume_zip(decrit), "export": dict(mesure, **export)})
        self.assertEqual((decrit["entrees"], len(decrit["documents"])), (25, 0))
        self.assertGreater(len(decrit["csv"]["journal.csv"]), 40 * MIO)
        chemin.unlink()

    # -- 05-08 : aller-retour de plus de 2 Go dans les deux modes ------------------------------------------------------

    def memoire_pour(self, cle, besoin_mo, delai_s=5 if ESSAI else 900):
        """Attend (delai_s au plus) que la mémoire libre couvre la garde plus `besoin_mo` → vrai si c'est le cas (sinon
        noté sous `cle`_non_tente)."""
        fin = time.monotonic() + delai_s
        while disponible() < GARDE + besoin_mo * MIO and time.monotonic() < fin:
            time.sleep(2)
        if disponible() >= GARDE + besoin_mo * MIO:
            return True
        noter(cle + "_non_tente", {"libre_mo": mo(disponible()), "besoin_mo": besoin_mo, "garde_mo": mo(GARDE),
                                   "attente_s": delai_s})
        return False

    def source_2go(self):
        """Jeu de charge dont demandes.csv et equipements.csv citent les 220 documents → (dossier, documents)."""
        source = self.temporaire / "source-2go"
        fichiers = jeu_de_charge(source)
        photos, notices = documents_2go()
        tzl.ecrire_dossier(source, {
            "demandes.csv": tzl.poser_documents(fichiers["demandes.csv"], "photo", sorted(photos)),
            "equipements.csv": tzl.poser_documents(fichiers["equipements.csv"], "document", sorted(notices))})
        return source, dict(photos, **notices)

    def export_reel_2go(self, source, documents, chemin):
        with ServeurPrevo(source=source) as serveur:
            debut = time.monotonic()
            sources = ecrire_documents(serveur.dossier / "documents", documents)
            fabrication = round(time.monotonic() - debut, 1)
            with Navigateur(self, self.temporaire / "profil-05", self.temporaire / "telechargements") as nav:
                page = self.ouvrir_serveur(nav, serveur)
                mesure, export = self.mesurer(nav, lambda: self.exporter(page, chemin))
                disque = {table: (serveur.dossier / (table + ".csv")).read_bytes() for table in tzl.TABLES}
                page.goto("about:blank")
                self.sans_erreur(nav)
        shutil.rmtree(self.temporaire / "profil-05", ignore_errors=True)
        return sources, dict(mesure, **export, fabrication_s=fabrication), disque

    def zip_recompose(self, source, documents):
        """Repli quand l'export réel de 2 Go ne tient pas sous la garde : un VRAI export du même serveur, documents
        réduits à 1 Ko (mêmes noms), puis recomposé par Python avec les documents de 9,5 Mo (photos stockées, notices
        compressées par zlib), le manifeste mis à jour (tailles, SHA-256) et la disposition de ZipFlux → (chemin,
        décrit, {nom: sha256})."""
        petit = self.temporaire / "05_petits_documents.zip"
        chemin = self.temporaire / "05_recompose.zip"
        with ServeurPrevo(source=source) as serveur:
            ecrire_documents(serveur.dossier / "documents", {nom: (1024, graine, signature)
                                                             for nom, (_, graine, signature) in documents.items()})
            with Navigateur(self, self.temporaire / "profil-05r", self.temporaire / "telechargements") as nav:
                page = self.ouvrir_serveur(nav, serveur)
                self.exporter(page, petit)
                disque = {table: (serveur.dossier / (table + ".csv")).read_bytes() for table in tzl.TABLES}
                page.goto("about:blank")
                self.sans_erreur(nav)
        shutil.rmtree(self.temporaire / "profil-05r", ignore_errors=True)
        with zipfile.ZipFile(petit) as archive:
            contenu = [(info.filename, archive.read(info)) for info in archive.infolist()]
        petit.unlink()
        manifeste_petit = dict(contenu)["manifeste.json"]
        manifeste = json.loads(manifeste_petit.decode("utf-8"))
        self.assertEqual((json.dumps(manifeste, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), manifeste_petit,
                         "manifeste.json : Python ne le réécrit pas comme JSON.stringify(…, null, 2)")
        sources = {}

        def entrees():
            for nom, octets in contenu:
                if nom.startswith("documents/"):
                    taille, graine, signature = documents[nom[len("documents/"):]]
                    octets = tzl.octets_fictifs(taille, graine, signature)
                    sources[nom[len("documents/"):]] = sha256(octets)
                    yield nom, octets, nom.endswith(".jpg")
                elif nom != "manifeste.json":
                    yield nom, octets, False
            for fichier in manifeste["fichiers"]:
                if fichier["nom"].startswith("documents/"):
                    nom = fichier["nom"][len("documents/"):]
                    fichier["octets"], fichier["sha256"] = documents[nom][0], sources[nom]
            yield "manifeste.json", (json.dumps(manifeste, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), False

        debut = time.monotonic()
        zip_comme_zipflux(chemin, entrees())
        recomposition = round(time.monotonic() - debut, 1)
        decrit = decrire_zip(chemin)
        noter("05_zip_recompose", {"zip": resume_zip(decrit), "recomposition_s": recomposition})
        self.controler_zip(decrit, sources, PLUS_DE_2GO)
        for table, octets in disque.items():
            self.assertTrue(decrit["csv"][table + ".csv"] == octets, table)
        return chemin, decrit, sources

    def test_05_export_serveur_plus_de_2_go(self):
        source, documents = self.source_2go()
        chemin = self.temporaire / "05_serveur.zip"
        raison = "mémoire libre insuffisante au départ (besoin : %d Mo au-dessus de la garde)" % BESOIN_EXPORT_2GO_MO
        if self.memoire_pour("05_serveur_2go", BESOIN_EXPORT_2GO_MO):
            try:
                sources, mesure, disque = self.export_reel_2go(source, documents, chemin)
            except GardeDeclenchee as garde:
                noter("05_serveur_2go", {"garde": garde.args[0]})
                raison = "garde mémoire déclenchée : %s" % json.dumps(garde.args[0], ensure_ascii=False)
            else:
                shutil.rmtree(source, ignore_errors=True)
                decrit = decrire_zip(chemin)
                noter("05_serveur_2go", {"zip": resume_zip(decrit), "export": mesure})
                self.controler_zip(decrit, sources, PLUS_DE_2GO)
                self.assertEqual(decrit["stockees"], DOCUMENTS_2GO // 2)
                for table, octets in disque.items():
                    self.assertTrue(decrit["csv"][table + ".csv"] == octets, table)
                ETAT["sources_2go"] = sources
                ETAT["zip_serveur"] = (chemin, decrit)
                return
        shutil.rmtree(self.temporaire / "profil-05", ignore_errors=True)
        chemin, decrit, sources = self.zip_recompose(source, documents)
        shutil.rmtree(source, ignore_errors=True)
        ETAT["sources_2go"] = sources
        ETAT["zip_serveur"] = (chemin, decrit)
        ETAT["zip_recompose"] = True
        self.skipTest("export réel de 2 Go non fait (%s) : ZIP recomposé pour les étapes 06 à 09" % raison)

    def test_06_import_dossier_du_zip_serveur(self):
        if "zip_serveur" not in ETAT:
            self.skipTest("l'étape 05 n'a pas produit son ZIP")
        chemin, decrit = ETAT["zip_serveur"]

        def deroule():
            with Navigateur(self, self.temporaire / "profil-dossier", self.temporaire / "telechargements",
                            dossier_simule=True) as nav:
                page = self.ouvrir_dossier(nav, ecrire_jeu=True)
                mesure, termine = self.mesurer(nav, lambda: self.importer(page, chemin, DOCUMENTS_2GO))
                debut = time.monotonic()
                self.controler_opfs(page, decrit, chemin.name)
                controle = round(time.monotonic() - debut, 1)
                self.sans_erreur(nav, [tzi.ERREUR_PING_ABSENT.pattern])
            return mesure, termine, controle

        mesure, termine, controle = self.etape("06_dossier_import_2go", deroule)
        noter("06_dossier_import_2go", {"import": dict(mesure, termine=termine[:120]), "controle_opfs_s": controle,
                                        "zip_importe": "recomposé" if ETAT.get("zip_recompose") else "export serveur"})
        ETAT["opfs_2go"] = True

    def test_07_export_dossier_plus_de_2_go(self):
        if "opfs_2go" not in ETAT:
            self.skipTest("l'étape 06 n'a pas rempli l'OPFS")
        if not self.memoire_pour("07_dossier_export_2go", BESOIN_EXPORT_2GO_MO):
            self.skipTest("export de 2 Go non tenté : mémoire libre insuffisante (besoin : %d Mo au-dessus de la garde)"
                          % BESOIN_EXPORT_2GO_MO)
        chemin = self.temporaire / "07_dossier.zip"

        def deroule():
            with Navigateur(self, self.temporaire / "profil-dossier", self.temporaire / "telechargements",
                            dossier_simule=True) as nav:
                page = self.ouvrir_dossier(nav, ecrire_jeu=False)
                mesure, export = self.mesurer(nav, lambda: self.exporter(page, chemin))
                contenu = self.opfs(page)
                self.sans_erreur(nav, [tzi.ERREUR_PING_ABSENT.pattern])
            return mesure, export, contenu

        mesure, export, contenu = self.etape("07_dossier_export_2go", deroule)
        shutil.rmtree(self.temporaire / "profil-dossier", ignore_errors=True)
        decrit = decrire_zip(chemin)
        noter("07_dossier_export_2go", {"zip": resume_zip(decrit), "export": dict(mesure, **export)})
        self.controler_zip(decrit, ETAT["sources_2go"], PLUS_DE_2GO)
        for nom, octets in decrit["csv"].items():
            if nom != "manifeste.json":
                self.assertEqual(sha256(octets), contenu[nom]["sha256"], nom)
        ETAT["zip_dossier"] = (chemin, decrit)

    def test_08_import_serveur_du_zip_dossier(self):
        origine = "export dossier" if "zip_dossier" in ETAT else ("recomposé" if ETAT.get("zip_recompose")
                                                                    else "export serveur")
        if "zip_dossier" not in ETAT and "zip_serveur" not in ETAT:
            self.skipTest("ni l'étape 07 ni l'étape 05 n'ont produit de ZIP")
        chemin, decrit = ETAT.get("zip_dossier") or ETAT["zip_serveur"]
        source = self.temporaire / "source-f3"
        copier_jeu("f3-v1.2.0", source)

        # a. Dossier des documents plafonné à 2 Go (quota_documents_mo à 2 048, l'ancien défaut, audit F2 ; fichier de
        #    configuration : avec les comptes, le responsable importe) : 2 090 Mo de documents n'y entrent pas :
        #    l'import s'arrête proprement, sans toucher aux tables.
        def refuse():
            with ServeurPrevo(source=source, comptes=True, reglages={"quota_documents_mo": 2048}) as serveur:
                with Navigateur(self, self.temporaire / "profil-08", self.temporaire / "telechargements") as nav:
                    serveur.poser_session(nav.contexte, "responsable")
                    page = self.ouvrir_serveur(nav, serveur)
                    avant = {table: (serveur.dossier / (table + ".csv")).read_bytes() for table in tzl.TABLES}
                    debut = time.monotonic()
                    page.set_input_files("#fichier-import-zip", str(chemin))
                    page.wait_for_selector("#confirmation-import-zip", timeout=DELAI_MS)
                    page.click(tzi.BOUTON_REMPLACER)
                    page.wait_for_selector("#import-zip-echec, #import-zip-termine", timeout=DELAI_MS)
                    duree = round(time.monotonic() - debut, 1)
                    texte = re.sub(r"\s+", " ", page.inner_text("dialog"))
                    page.goto("about:blank")
                    self.sans_erreur(nav, [r"status of 413"])
                apres = {table: (serveur.dossier / (table + ".csv")).read_bytes() for table in tzl.TABLES}
                copies = sum(1 for p in (serveur.dossier / "documents").iterdir() if p.is_file())
            shutil.rmtree(self.temporaire / "profil-08", ignore_errors=True)
            return {"duree_s": duree, "message": texte[:400], "documents_copies": copies,
                    "tables_inchangees": avant == apres}

        refus = self.etape("08_serveur_import_2go_quota_2048", refuse)
        noter("08_serveur_import_2go_quota_2048", refus)
        self.assertIn("Dossier des documents plein", refus["message"])
        self.assertIn("aucune donnée n'a changé", refus["message"])
        self.assertTrue(refus["tables_inchangees"])

        # b. Réglages par défaut (T250 : quota_documents_mo à 4 096, comme l'import ZIP) : tout entre.
        def deroule():
            with ServeurPrevo(source=source) as serveur:
                with Navigateur(self, self.temporaire / "profil-08", self.temporaire / "telechargements") as nav:
                    page = self.ouvrir_serveur(nav, serveur)
                    mesure, termine = self.mesurer(nav, lambda: self.importer(page, chemin, DOCUMENTS_2GO))
                    page.goto("about:blank")
                    self.sans_erreur(nav)
                dossier = serveur.dossier
                csv_ecrits = {table: (dossier / (table + ".csv")).read_bytes() for table in tzl.TABLES}
                debut = time.monotonic()
                documents = {p.name: sha256_fichier(p) for p in (dossier / "documents").iterdir() if p.is_file()}
                controle = round(time.monotonic() - debut, 1)
            return mesure, termine, csv_ecrits, documents, controle

        mesure, termine, csv_ecrits, documents, controle = self.etape("08_serveur_import_2go", deroule)
        shutil.rmtree(source, ignore_errors=True)
        shutil.rmtree(self.temporaire / "profil-08", ignore_errors=True)
        noter("08_serveur_import_2go", {"import": dict(mesure, termine=termine[:120]), "controle_disque_s": controle,
                                        "zip_importe": origine})
        rendus = self.controler_import(decrit, csv_ecrits, documents, chemin.name, r"\d{8}-\d{6}-")
        self.assertEqual(len(rendus), DOCUMENTS_2GO)
        if origine == "export dossier":
            chemin.unlink()

    # -- 09-11 : ouverture par d'autres outils -------------------------------------------------------------------------

    def test_09_zip_de_plus_de_2_go_ouvert_par_python_tar_et_extraire_tout(self):
        if "zip_serveur" not in ETAT:
            self.skipTest("l'étape 05 n'a pas produit son ZIP")
        chemin, decrit = ETAT["zip_serveur"]
        self.ouvrir_par_les_outils("09_outils_2go", chemin, decrit)
        chemin.unlink()
        ETAT.pop("zip_serveur")

    def test_10_pres_de_4_go_ecrit_dans_la_page_par_zipflux(self):
        taille, nombre = 195 * MIO // 2, ENTREES_4GO[0]             # 40 × 97,5 Mo = 3 900 Mo
        base = random.Random("recette-4go").randbytes(taille)
        source = self.temporaire / "source-4go.bin"
        source.write_bytes(base)
        chemin = self.temporaire / "10_page_4go.zip"
        attendus = {"gros-%02d.jpg" % n: sha256(struct.pack(">Q", n) + base[8:]) for n in range(nombre)}
        del base
        ecrire = """async ([nombre, date]) => {
          const fichier = document.getElementById('source').files[0];
          const ecrivain = ZipFlux.ecrivain({ date: new Date(...date) });
          for (let n = 0; n < nombre; n += 1) {
            const entete = new Uint8Array(8);
            new DataView(entete.buffer).setUint32(4, n);
            const nom = 'documents/gros-' + String(n).padStart(2, '0') + '.jpg';
            await ecrivain.ajouter(nom, new Blob([entete, fichier.slice(8)]), { stocker: true });
          }
          const zip = ecrivain.terminer();
          const lien = document.createElement('a');
          lien.href = URL.createObjectURL(zip);
          lien.download = 'recette-4go.zip';
          document.body.appendChild(lien);
          lien.click();
          return zip.size;
        }"""

        def deroule():
            with Navigateur(self, self.temporaire / "profil-10", self.temporaire / "telechargements") as nav:
                page = nav.page
                page.goto(self.statique.url + "/tests/fixtures/page-vide.html")
                page.add_script_tag(url=self.statique.url + "/js/modules/zip-flux.js")
                page.evaluate("() => { const c = document.createElement('input'); c.type = 'file'; c.id = 'source'; "
                              "document.body.appendChild(c); }")
                page.set_input_files("#source", str(source))

                def produire():
                    with page.expect_download(timeout=DELAI_MS) as attente:
                        octets = page.evaluate(ecrire, [nombre, [DATE_ZIP[0], DATE_ZIP[1] - 1] + list(DATE_ZIP[2:])])
                    debut = time.monotonic()
                    telecharge = Path(attente.value.path())
                    duree = round(time.monotonic() - debut, 1)
                    shutil.move(str(telecharge), str(chemin))
                    return {"octets_page": octets, "telechargement_s": duree}

                mesure, production = self.mesurer(nav, produire)
                self.sans_erreur(nav)
            return mesure, production

        mesure, production = self.etape("10_page_4go", deroule)
        shutil.rmtree(self.temporaire / "profil-10", ignore_errors=True)
        source.unlink()
        decrit = decrire_zip(chemin)
        noter("10_page_4go", {"zip": resume_zip(decrit), "ecriture": dict(mesure, **production)})
        self.assertEqual(production["octets_page"], decrit["octets"])
        self.assertLess(decrit["octets"], 0xFFFFFFFF)
        self.assertGreater(decrit["octets"], (3800 if not ESSAI else 380) * MIO)
        self.assertEqual(decrit["documents"], attendus)
        self.assertIsNone(decrit["testzip"])
        self.assertFalse(decrit["zip64"])
        self.ouvrir_par_les_outils("10_outils_page_4go", chemin, decrit)
        chemin.unlink()

    def test_11_pres_de_4_go_400_entrees_de_10_mo(self):
        # 1. La copie Python de l'écrivain donne, octet pour octet, ce que donne ZipFlux.ecrivain (entrées stockées).
        petites = [("documents/a.jpg", random.Random("a").randbytes(70000)), ("documents/vide.pdf", b""),
                   ("documents/é-ü.jpg", random.Random("b").randbytes(1000)), ("manifeste.json", b"{}\n")]
        with Navigateur(self, self.temporaire / "profil-11", self.temporaire / "telechargements") as nav:
            page = nav.page
            page.goto(self.statique.url + "/tests/fixtures/page-vide.html")
            page.add_script_tag(url=self.statique.url + "/js/modules/zip-flux.js")
            octets_page = bytes(page.evaluate("""async ([entrees, date]) => {
              const ecrivain = ZipFlux.ecrivain({ date: new Date(...date) });
              for (const [nom, octets] of entrees) {
                await ecrivain.ajouter(nom, new Uint8Array(octets), { stocker: true });
              }
              return Array.from(new Uint8Array(await ecrivain.terminer().arrayBuffer()));
            }""", [[[nom, list(octets)] for nom, octets in petites],
                   [DATE_ZIP[0], DATE_ZIP[1] - 1] + list(DATE_ZIP[2:])]))
            self.sans_erreur(nav)
        shutil.rmtree(self.temporaire / "profil-11", ignore_errors=True)
        petit = self.temporaire / "petit.zip"
        zip_comme_zipflux(petit, petites)
        self.assertEqual(petit.read_bytes(), octets_page, "la copie Python n'écrit pas comme ZipFlux.ecrivain")
        petit.unlink()
        # 2. 400 entrées de 9,75 Mo, comme un vrai export près de 4 Go.
        taille, nombre = 39 * MIO // 4, ENTREES_4GO[1]               # 400 × 9,75 Mo = 3 900 Mo
        base = random.Random("recette-400").randbytes(taille)
        chemin = self.temporaire / "11_400_entrees.zip"
        attendus = {"photo-%03d.jpg" % n: sha256(struct.pack(">Q", n) + base[8:]) for n in range(nombre)}
        debut = time.monotonic()
        octets = zip_comme_zipflux(chemin, (("documents/photo-%03d.jpg" % n, struct.pack(">Q", n) + base[8:])
                                            for n in range(nombre)))
        ecriture = round(time.monotonic() - debut, 1)
        del base
        decrit = decrire_zip(chemin)
        noter("11_copie_python_4go", {"zip": resume_zip(decrit), "ecriture_s": ecriture})
        self.assertEqual(octets, decrit["octets"])
        self.assertEqual(decrit["documents"], attendus)
        self.assertIsNone(decrit["testzip"])
        self.ouvrir_par_les_outils("11_outils_400_entrees_4go", chemin, decrit)
        chemin.unlink()


if __name__ == "__main__":
    unittest.main()
