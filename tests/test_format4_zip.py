"""Import ZIP d'une base 2.1 dans la 2.2 (chantier 2.2, lot L1, T393 ; D183 ; CS169, CS170) : un export de la 2.1
(format 3) est migré en mémoire par ZipTables.lire (js/modules/zip-tables.js, appelé par ZipLecture.lire) ; l'étape
3→4 y reprend les observations des contrôles en réserves (Formats.reservesReprises).

Les ZIP sont fabriqués ici, dans un dossier temporaire, comme un export de la 2.1 : les 24 CSV d'une copie du jeu
(f3-v2.1.0 ou reserves-a-reprendre, tests/fixtures/formats/LISEZMOI.md), un document, et un manifeste exact
(version_appli 2.1.0, format 3, champs de Formats.manifeste de l'étiquette v2.1.0). Jamais de données réelles.

    lecture   (page vide, ZipLecture.lire, rien d'écrit) : avec et sans manifeste, les réserves du LISEZMOI (lignes
              entières : gravité, échéance, date de levée et OT vides ; commentaire fixe si levée), octets du CSV des
              réserves égaux à ceux qu'écrirait serveur.py (ecrire_tableau_csv, ecrire_valeur_texte) ; contrôles
              gardés ; reserves_controle annoncée comme table nouvelle (problème « info » : « n'existait pas au
              format 3 ; la table aura N lignes après l'import… ») et absente de `absentes` (l'import ne la vide
              pas) ; garanties et contrats_prestataires vides, dans `absentes` (« la table sera vide après
              l'import ») ; ZIP au format 5 (jeu plus-recent, avec et sans manifeste) : refusé ;
    dossier   OPFS (installer_dossier_simule) : base cible = la démo (format courant) plus une garantie et un contrat
              fabriqués ; confirmation : format 3 mis au format courant, réserves comptées (actuel → importé), sans
              badge « vidée », garanties et contrats seuls dans « tables absentes du ZIP seront vidées » ; après
              l'import : reserves_controle.csv égal à l'octet aux réserves du LISEZMOI, garanties et contrats en
              en-tête seul, cellules des contrôles inchangées (colonnes du format 4 à leur défaut), version_schema
              4, une ligne de journal, sauvegarde « avant-import-zip » qui garde l'ancienne base (réserve, garantie
              et contrat compris) ; ZIP au format 5 : refusé, aucun octet écrit ;
    serveur   ServeurPrevo, mêmes contrôles sur le disque ; le document est rangé sous le nom horodaté du serveur
              (« AAAAMMJJ-HHMMSS-notice-compresseur.pdf »). Joué sans saut depuis le format 4 côté serveur (T385,
              T399).

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_format4_zip.py" -v
"""
import base64
import hashlib
import json
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from commun import (FORMAT_COURANT, FORMAT_PLUS_RECENT, NB_TABLES, RACINE, CasNavigateur, ServeurPrevo,
                    ServeurStatique, attendre_pret, charger_scripts, format_du_jeu, installer_dossier_simule,
                    preregler_profil)
from test_formats_js import (COLONNES_AJOUTEES, COLONNES_RESERVES, DEFAUTS_AJOUTES, RESERVES_DU_LISEZMOI,
                             reserve_complete)
from test_zip_import import (BOUTON_REMPLACER, ECRIRE_OPFS_JS, ERREUR_PING_ABSENT, INSTANTANE_OPFS_JS,
                             MOTIF_AVANT_IMPORT_ZIP, TABLES, CasImport, contenu_sauvegarde, en_base64, fichiers_demo,
                             fichiers_du_jeu, instantane, lire_csv, octets_pdf, sans_prefixe, sauvegardes_de)
from test_zip_lecture import AIDE_JS, SCRIPTS, serveur

JEUX_2_1 = ("reserves-a-reprendre", "f3-v2.1.0")
FORMAT_2_1 = 3
TABLES_NOUVELLES = ("reserves_controle", "garanties", "contrats_prestataires")       # format 4 (CONCEPTION-L1 §2)
VIDEES = ["contrats_prestataires", "garanties"]                                       # triées
CHAMPS_TEXTE_RESERVES = ("texte", "commentaire_levee")    # écrits comme un champ texte (apostrophe de protection)
DOCUMENT_2_1 = ("notice-compresseur.pdf", octets_pdf("notice du compresseur, export 2.1"))
NOM_DOSSIER = "donnees-format4-zip"
# Base cible : une garantie et un contrat fabriqués (EQ-0001 et FOU-0001 existent dans la démo), que l'import vide.
LIGNE_GARANTIE = "GAR-0001;EQ-0001;FOU-0001;2025-01-15;2027-01-15;Pièces et main-d'œuvre, retour atelier;;1\r\n"
LIGNE_CONTRAT = ("CTP-0001;FOU-0001;Entretien des compresseurs;EQ-0001;Visites trimestrielles;2026-01-01;2026-12-31;"
                 "3;1;12;4800;;1\r\n")


# ---------------------------------------------------------------------------
# Fichiers et ZIP
# ---------------------------------------------------------------------------

def csv_du_jeu(nom):
    """{nom de fichier : octets} des CSV (à la racine) d'une copie du jeu."""
    return {chemin: octets for chemin, octets in fichiers_du_jeu(nom).items()
            if chemin.endswith(".csv") and "/" not in chemin}


def format_des_fichiers(fichiers):
    """version_schema du parametres.csv de ces fichiers, en entier (une variante n'a pas son propre parametres.csv :
    format_du_jeu ne la lit pas)."""
    return int(re.search(rb"version_schema;'?(\d+)", fichiers["parametres.csv"]).group(1))


def manifeste_2_1(entrees, format=FORMAT_2_1, version="2.1.0"):
    """Octets d'un manifeste exact comme l'écrit l'export de la 2.1 (Formats.manifeste : application, version_appli,
    format, date, motif, mode, puis les fichiers triés par nom, chacun avec sa taille et son SHA-256)."""
    contenu = {"application": "Prévo", "version_appli": version, "format": format, "date": "2026-11-02T10:00:00",
               "motif": "export", "mode": "serveur",
               "fichiers": [{"nom": nom, "octets": len(octets), "sha256": hashlib.sha256(octets).hexdigest()}
                            for nom, octets in sorted(entrees.items())]}
    return json.dumps(contenu, ensure_ascii=False, indent=2).encode("utf-8")


def ecrire_zip(chemin, fichiers, avec_manifeste=True, **manifeste):
    """Écrit un ZIP d'export ({nom : octets}) : les fichiers, un document, puis manifeste.json (exact) au besoin."""
    entrees = dict(fichiers, **{"documents/" + DOCUMENT_2_1[0]: DOCUMENT_2_1[1]})
    if avec_manifeste:
        entrees["manifeste.json"] = manifeste_2_1(entrees, **manifeste)
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as archive:
        for nom, octets in entrees.items():
            archive.writestr(zipfile.ZipInfo(nom, date_time=(2026, 11, 2, 10, 0, 0)), octets,
                             compress_type=zipfile.ZIP_DEFLATED)
    return chemin


def zip_2_1(dossier, jeu, avec_manifeste=True):
    """Export de la 2.1 fabriqué depuis le jeu (24 CSV au format 3, un document, manifeste) → chemin du ZIP."""
    fichiers = csv_du_jeu(jeu)
    assert len(fichiers) == 24 and format_des_fichiers(fichiers) == FORMAT_2_1, (jeu, len(fichiers))
    assert not set(TABLES_NOUVELLES) & {nom[:-4] for nom in fichiers}, jeu
    return ecrire_zip(Path(dossier) / ("prevo-export-2026-11-02-%s%s.zip" % (jeu, "" if avec_manifeste else "-nu")),
                      fichiers, avec_manifeste)


def zip_format_5(dossier, avec_manifeste=True):
    """ZIP d'une version plus récente (jeu plus-recent : version_schema 5, table inconnue pieces_v5)."""
    fichiers = csv_du_jeu("plus-recent")
    assert format_des_fichiers(fichiers) == format_du_jeu("plus-recent") == FORMAT_PLUS_RECENT
    return ecrire_zip(Path(dossier) / ("prevo-export-format-5%s.zip" % ("" if avec_manifeste else "-nu")), fichiers,
                      avec_manifeste, format=FORMAT_PLUS_RECENT, version="2.3.0")


def reserves_attendues(jeu):
    """Lignes entières de reserves_controle que la reprise doit donner pour le jeu (LISEZMOI, CONCEPTION-L1 §3.2)."""
    return [reserve_complete(*reserve) for reserve in RESERVES_DU_LISEZMOI[jeu]]


def octets_reserves_attendus(jeu):
    """Octets de reserves_controle.csv que serveur.py écrirait pour ces réserves (BOM, « ; », CRLF ; texte et
    commentaire écrits comme un champ texte, les autres tels quels) : le navigateur doit écrire les mêmes."""
    lignes = [[serveur.ecrire_valeur_texte(reserve[colonne]) if colonne in CHAMPS_TEXTE_RESERVES else reserve[colonne]
               for colonne in COLONNES_RESERVES] for reserve in reserves_attendues(jeu)]
    return serveur.ecrire_tableau_csv(COLONNES_RESERVES, lignes)


def base_cible():
    """{chemin : octets} de la base qui reçoit l'import : la démo (format courant, ses réserves), dont les garanties et
    les contrats sont remplacés par une garantie et un contrat fabriqués (la démo en a plusieurs depuis le L4)."""
    fichiers = fichiers_demo()
    for nom, ligne in (("garanties.csv", LIGNE_GARANTIE), ("contrats_prestataires.csv", LIGNE_CONTRAT)):
        entete = fichiers[nom].split(b"\r\n", 1)[0]
        fichiers[nom] = entete + b"\r\n" + ligne.encode("utf-8")
    assert reserves_de_la_demo() >= 1, "la démo a des réserves"
    for table in VIDEES:
        assert len(lire_csv(fichiers[table + ".csv"])[1]) == 1, table
    return fichiers


def reserves_de_la_demo():
    """Nombre de réserves de la démo (plus d'une depuis T417 : réserves de RA-01 et d'AE-01), que l'import remplace."""
    return len(lire_csv(fichiers_demo()["reserves_controle.csv"])[1])


# ---------------------------------------------------------------------------
# Lecture (ZipLecture.lire → ZipTables.lire), sans rien écrire
# ---------------------------------------------------------------------------

LIRE_JS = """async () => {
  const r = await ZipLecture.lire(document.getElementById('zip').files[0]);
  if (!r.ok) { return { ok: false, refus: r.refus }; }
  const tables = r.tables;
  return {
    ok: true, formatOrigine: r.formatOrigine, migre: r.migre, absentes: r.absentes,
    problemesTables: r.problemes.filter((p) => p.type === 'table')
      .map((p) => ({ gravite: p.gravite, table: p.table, message: p.message })),
    reserves: tables.reserves_controle.lignes,
    enteteReserves: tables.reserves_controle.entete,
    csvReserves: enBase64(Donnees.csv.serialiser('reserves_controle', tables.reserves_controle.lignes,
      tables.reserves_controle.colonnesInconnues)),
    nombres: Object.fromEntries(Object.keys(tables).map((nom) => [nom, tables[nom].lignes.length])),
    controles: tables.controles_reglementaires.lignes.map((l) => ({ id: l.id, observations: l.observations,
      observations_levees: l.observations_levees })),
    libelles: Object.fromEntries(Schema.nomsTables().map((nom) => [nom, Schema.table(nom).libelle])),
    courant: Formats.courant,
  };
}"""


class TestLecture(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-format4-zip-"))
        self.addCleanup(shutil.rmtree, self.temporaire, True)
        charger_scripts(self.page, SCRIPTS)
        self.page.add_script_tag(content=AIDE_JS)

    def lire(self, chemin):
        self.page.set_input_files("#zip", str(chemin))
        return self.page.evaluate(LIRE_JS)

    def test_zip_de_la_2_1_reserves_reprises_annoncees_comme_table_nouvelle(self):
        for jeu in JEUX_2_1:
            for avec_manifeste in (True, False):
                with self.subTest(jeu=jeu, manifeste=avec_manifeste):
                    lu = self.lire(zip_2_1(self.temporaire, jeu, avec_manifeste))
                    self.assertTrue(lu["ok"], lu.get("refus"))
                    self.assertEqual(lu["courant"], FORMAT_COURANT)
                    self.assertEqual((lu["formatOrigine"], lu["migre"]), (FORMAT_2_1, True))
                    # CS170 : les réserves de D183, lignes entières, dans l'ordre, et les octets de serveur.py.
                    attendues = reserves_attendues(jeu)
                    self.assertEqual(lu["enteteReserves"], COLONNES_RESERVES)
                    self.assertEqual(lu["reserves"], attendues)
                    self.assertEqual(base64.b64decode(lu["csvReserves"]), octets_reserves_attendus(jeu))
                    # CS169 : les contrôles gardent leurs observations (elles restent lisibles par une 2.1).
                    _, controles_zip = lire_csv(csv_du_jeu(jeu)["controles_reglementaires.csv"])
                    self.assertEqual([c["id"] for c in lu["controles"]], [c["id"] for c in controles_zip])
                    for controle in lu["controles"]:
                        if any(r["controle_id"] == controle["id"] for r in attendues):
                            self.assertTrue(controle["observations"].strip(), controle["id"])
                    # Table nouvelle remplie : annoncée (info), jamais « vidée » ; garanties et contrats : vides.
                    self.assertEqual(lu["absentes"], ["garanties", "contrats_prestataires"])
                    self.assertEqual(lu["nombres"]["garanties"], 0)
                    self.assertEqual(lu["nombres"]["contrats_prestataires"], 0)
                    problemes = {p["table"]: p for p in lu["problemesTables"]}
                    self.assertEqual(sorted(problemes), sorted(TABLES_NOUVELLES))
                    self.assertTrue(all(p["gravite"] == "info" for p in problemes.values()), problemes)
                    n = len(attendues)
                    self.assertEqual(problemes["reserves_controle"]["message"],
                                     "%s : reserves_controle.csv n'existait pas au format 3 ; la table aura %d %s après "
                                     "l'import, %s des données du ZIP au passage au format %d."
                                     % (lu["libelles"]["reserves_controle"], n, "ligne" if n == 1 else "lignes",
                                        "reprise" if n == 1 else "reprises", FORMAT_COURANT))
                    for table in VIDEES:
                        self.assertEqual(problemes[table]["message"], "%s : %s.csv n'existait pas au format 3 ; la "
                                         "table sera vide après l'import." % (lu["libelles"][table], table))

    def test_zip_au_format_5_refuse(self):
        for avec_manifeste in (True, False):
            with self.subTest(manifeste=avec_manifeste):
                lu = self.lire(zip_format_5(self.temporaire, avec_manifeste))
                self.assertFalse(lu["ok"], lu)
                for attendu in ("version plus récente de Prévo", "format %d" % FORMAT_PLUS_RECENT,
                                "jusqu'au format %d" % FORMAT_COURANT):
                    self.assertIn(attendu, lu["refus"])


# ---------------------------------------------------------------------------
# Import par l'application : contrôles communs aux deux modes
# ---------------------------------------------------------------------------

class CasFormat4(CasImport):

    # Mode serveur : serveur.py range un document sous un nom horodaté (« AAAAMMJJ-HHMMSS-<nom> », test_zip_import).
    NOM_HORODATE = False

    def verifier_confirmation(self, info, jeu):
        self.assertEqual((info["format"], info["migre"], info["documents"]), (str(FORMAT_2_1), "1", 1))
        self.assertIn("Prévo 2.1.0", info["origine"])
        self.assertEqual(info["formatTexte"], "Format des données : 3 ; elles seront mises au format %d (format de "
                                              "cette version) à l'import." % FORMAT_COURANT)
        # Les réserves reprises sont comptées et ne sont pas annoncées « vidées » ; garanties et contrats le sont.
        self.assertEqual(info["actuel"]["reserves_controle"], reserves_de_la_demo())
        self.assertEqual(info["importe"]["reserves_controle"], len(RESERVES_DU_LISEZMOI[jeu]))
        self.assertEqual(sorted(info["videes"]), VIDEES)
        self.assertIn("2 tables absentes du ZIP seront vidées", info["tablesVidees"])
        for table in VIDEES:
            self.assertIn(table + ".csv", info["tablesVidees"])
            self.assertEqual((info["actuel"][table], info["importe"][table]), (1, 0), table)
        self.assertNotIn("reserves_controle.csv", info["tablesVidees"])
        self.assertNotIn("sera vide", info["problemes"] or "")

    def verifier_apres_import(self, jeu, fichiers, avant, nom_zip):
        """fichiers, avant : {chemin : octets} du dossier de données après et avant l'import."""
        zip_csv = csv_du_jeu(jeu)
        # Réserves écrites par l'import, à l'octet ; garanties et contrats vidés (en-tête du format courant seul).
        self.assertEqual(fichiers["reserves_controle.csv"], octets_reserves_attendus(jeu))
        for table in VIDEES:
            entete, lignes = lire_csv(fichiers[table + ".csv"])
            self.assertEqual((entete, lignes), (lire_csv(fichiers_demo()[table + ".csv"])[0], []), table)
        # Contrôles : chaque cellule du ZIP gardée sous son nom de colonne ; colonnes du format 4 à leur défaut.
        entete_zip, controles_zip = lire_csv(zip_csv["controles_reglementaires.csv"])
        entete, controles = lire_csv(fichiers["controles_reglementaires.csv"])
        self.assertEqual(len(controles), len(controles_zip))
        for ligne, ligne_zip in zip(controles, controles_zip):
            self.assertEqual({c: ligne[c] for c in entete_zip}, ligne_zip)
            for colonne in COLONNES_AJOUTEES[4]["controles_reglementaires"]:
                self.assertEqual(ligne[colonne], DEFAUTS_AJOUTES[colonne], (ligne["id"], colonne))
        self.assertEqual(set(entete), set(entete_zip) | set(COLONNES_AJOUTEES[4]["controles_reglementaires"]))
        self.assertIn(("version_schema;'%d" % FORMAT_COURANT).encode(), fichiers["parametres.csv"])
        self.assertRegex(lire_csv(fichiers["journal.csv"])[1][-1]["action"],
                         r"^import ZIP : %s, %d tables, 1 document ; sauvegarde \d{4}-\d{2}-\d{2}_\d{6}_avant-import-zip "
                         r"faite juste avant$" % (re.escape(nom_zip), NB_TABLES))
        # Le document du ZIP : seul nouveau document, à l'octet, sous son nom (horodaté en mode serveur).
        nouveaux = {chemin[len("documents/"):]: octets for chemin, octets in fichiers.items()
                    if chemin.startswith("documents/") and chemin not in avant}
        self.assertEqual(list(nouveaux.values()), [DOCUMENT_2_1[1]])
        nom = next(iter(nouveaux))
        self.assertEqual(sans_prefixe(nom) if self.NOM_HORODATE else nom, DOCUMENT_2_1[0])
        if self.NOM_HORODATE:
            self.assertNotEqual(nom, DOCUMENT_2_1[0])
        # La sauvegarde faite juste avant garde l'ancienne base, tables nouvelles comprises (rien de perdu).
        noms = sauvegardes_de(fichiers, MOTIF_AVANT_IMPORT_ZIP)
        self.assertEqual(len(noms), 1, noms)
        sauvegarde = contenu_sauvegarde(fichiers, noms[0])
        for table in TABLES:
            self.assertEqual(sauvegarde[table + ".csv"], avant[table + ".csv"], table)


# ---------------------------------------------------------------------------
# Mode dossier (OPFS)
# ---------------------------------------------------------------------------

class TestDossier(CasFormat4):

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(ERREUR_PING_ABSENT)

    def ouvrir_dossier(self, statique, fichiers):
        installer_dossier_simule(self.contexte, NOM_DOSSIER)
        preregler_profil(self.contexte, "responsable")
        page = self.page
        page.goto(statique.url + "/index.html")
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, {chemin: en_base64(o) for chemin, o in fichiers.items()}])
        page.click("#btn-dossier")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.mode"), "dossier")
        page.evaluate("location.hash = '#/parametres'")
        page.wait_for_selector("#btn-import-zip")
        return page

    def opfs(self, page):
        return {chemin: base64.b64decode(valeur)
                for chemin, valeur in page.evaluate(INSTANTANE_OPFS_JS, NOM_DOSSIER).items()}

    def importer(self, jeu):
        chemin_zip = zip_2_1(self.temporaire, jeu)
        with ServeurStatique(RACINE) as statique:
            page = self.ouvrir_dossier(statique, base_cible())
            avant = self.opfs(page)
            self.assertEqual(len([c for c in avant if c.endswith(".csv") and "/" not in c]), NB_TABLES)
            self.choisir_zip(page, chemin_zip)
            self.verifier_confirmation(self.confirmation(page), jeu)
            page.click(BOUTON_REMPLACER)
            self.texte_fenetre(page, "import-zip-termine")
            self.verifier_apres_import(jeu, self.opfs(page), avant, chemin_zip.name)

    def test_dossier_zip_de_la_2_1_avec_reserves_a_reprendre(self):
        self.importer("reserves-a-reprendre")

    def test_dossier_zip_de_la_2_1_jeu_f3_v2_1_0(self):
        self.importer("f3-v2.1.0")

    def test_dossier_zip_au_format_5_refuse_rien_ecrit(self):
        chemin_zip = zip_format_5(self.temporaire)
        with ServeurStatique(RACINE) as statique:
            page = self.ouvrir_dossier(statique, base_cible())
            avant = self.opfs(page)
            self.choisir_zip(page, chemin_zip)
            texte = self.texte_fenetre(page, "import-zip-refus")
            for attendu in ("version plus récente de Prévo", "format %d" % FORMAT_PLUS_RECENT, "Rien n'a été écrit."):
                self.assertIn(attendu, texte)
            self.assertEqual(page.locator("#confirmation-import-zip").count(), 0)
            self.assertEqual(self.opfs(page), avant)


# ---------------------------------------------------------------------------
# Mode serveur
# ---------------------------------------------------------------------------

class TestServeur(CasFormat4):

    NOM_HORODATE = True

    def demarrer(self):
        source = self.temporaire / "base"
        for nom, octets in base_cible().items():
            (source / nom).parent.mkdir(parents=True, exist_ok=True)
            (source / nom).write_bytes(octets)
        return ServeurPrevo(source=source)

    def ouvrir_parametres(self, serveur_prevo):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(serveur_prevo.url + "/#/parametres")
        attendre_pret(self.page)
        self.page.wait_for_selector("#btn-import-zip")
        return self.page

    def importer(self, jeu):
        chemin_zip = zip_2_1(self.temporaire, jeu)
        with self.demarrer() as serveur_prevo:
            page = self.ouvrir_parametres(serveur_prevo)
            avant = instantane(serveur_prevo.dossier)
            self.choisir_zip(page, chemin_zip)
            self.verifier_confirmation(self.confirmation(page), jeu)
            page.click(BOUTON_REMPLACER)
            self.texte_fenetre(page, "import-zip-termine")
            self.verifier_apres_import(jeu, instantane(serveur_prevo.dossier), avant, chemin_zip.name)

    def test_serveur_zip_de_la_2_1_avec_reserves_a_reprendre(self):
        self.importer("reserves-a-reprendre")

    def test_serveur_zip_de_la_2_1_jeu_f3_v2_1_0(self):
        self.importer("f3-v2.1.0")

    def test_serveur_zip_au_format_5_refuse_rien_ecrit(self):
        chemin_zip = zip_format_5(self.temporaire)
        with self.demarrer() as serveur_prevo:
            page = self.ouvrir_parametres(serveur_prevo)
            avant = instantane(serveur_prevo.dossier)
            self.choisir_zip(page, chemin_zip)
            texte = self.texte_fenetre(page, "import-zip-refus")
            for attendu in ("version plus récente de Prévo", "format %d" % FORMAT_PLUS_RECENT, "Rien n'a été écrit."):
                self.assertIn(attendu, texte)
            self.assertEqual(page.locator("#confirmation-import-zip").count(), 0)
            self.assertEqual(instantane(serveur_prevo.dossier), avant)


if __name__ == "__main__":
    unittest.main()
