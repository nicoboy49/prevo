"""Passage au format courant par le navigateur et lecture seule des données plus récentes (chantier « socle de
données », T186 ; décisions D167 à D169 ; js/donnees.js §4.11 et js/app.js, passerAuFormatCourant ; format 4 et
reprise des observations des contrôles en réserves, T391, D183, CS169, CS170).

Chaque cas ouvre l'APPLICATION ENTIÈRE (index.html) sur une copie d'un jeu de tests/fixtures/formats/ (jeux_formats,
toujours dans un dossier temporaire, puis dans l'OPFS du navigateur : jamais de données réelles) :

    dossier  : pour f1, f2-v1.1.0, f3-v1.2.0, f3-v2.0.0, f3-v2.1.0, reserves-a-reprendre, melange, colonnes-en-trop,
               table-absente, sans-bom et entete-tronque (profil demandeur : pas d'OT préventifs générés) :
                 - la sauvegarde « avant-format-v4 » (et la quotidienne) garde les fichiers d'origine à l'octet : elle
                   a été faite avant toute écriture ; aucune sauvegarde quand il n'y a rien à faire ;
                 - seuls les fichiers attendus changent (les tables sans colonne nouvelle restent identiques à
                   l'octet) ; aucune cellule d'origine perdue (comparaison champ à champ avec le fichier d'origine) ;
                   les colonnes ajoutées portent leur valeur par défaut ;
                 - reserves_controle.csv créé avec les réserves de D183 (LISEZMOI des jeux) quand un contrôle a des
                   observations, jamais créé sinon ; garanties et contrats_prestataires jamais créés ;
                 - les lignes de journal attendues, une par étape (« passage au format N du fichier ; sauvegarde …
                   faite juste avant », ou « fichiers complétés au format 3 : ordres_travail ; … » pour melange) ;
                 - une seconde ouverture n'écrit rien ;
               contrôle déjà doté d'une réserve : rien de plus pour lui, la réserve existante gardée à l'octet, les
               autres numérotées à sa suite ; passage interrompu (fichier tenu, simulé) après les tables complétées
               ou après les réserves, puis repris : aucun doublon ;
               entete-tronque dans une base au format 2, ordres_travail.csv au format 2 avec une valeur au-delà
               de l'en-tête (CS140 : la réécriture la perdrait), controles_reglementaires.csv abîmé de même : le
               fichier abîmé n'est jamais réécrit, il est signalé (problème « erreur » et bandeau), le reste passe au
               format 4 (contrôles abîmés : aucune réserve reprise) ; bandeau selon le profil (règle de T201, T408) :
               demandeur et technicien « Fichier abîmé : prévenez le responsable », sans jargon ; le responsable garde
               le sien (« laissé tel quel »), et a celui des fichiers abîmés à l'ouverture suivante ;
               sauvegarde impossible : rien n'est écrit, bandeau, pas d'OT préventifs ; l'ouverture suivante passe ;
    format 4  : f4-v2.2.0 (T394, base au format 4) en dossier → rien à migrer ni à reprendre : aucune sauvegarde
               avant-format-v4, aucune ligne de journal, aucun fichier changé, réserves, garanties et contrats lus ;
               en serveur → le démarrage ne réécrit aucune donnée, le navigateur non plus, pas de bandeau ;
    lecture seule (plus-recent, version_schema 5) : dossier → aucun octet modifié dans le dossier (pas même
               verrou.txt), bandeau sur tous les écrans, demande envoyée par l'interface refusée, écritures directes
               (Donnees, adaptateur) refusées par ErreurLectureSeule ; démo chargée depuis les CSV déposés et
               serveur → lecture seule et bandeau aussi ;
    démo     : f1 déposé → passage en mémoire, trois lignes « … ; sans sauvegarde (démo) » ;
    serveur  : copie de f2-v1.1.0 → le navigateur n'écrit rien (aucun octet modifié), bandeau au responsable.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_formats_navigateur.py" -v
"""
import base64
import csv
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from commun import (RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret, installer_dossier_simule,
                    preregler_profil, url_fichier)
from jeux_formats import copier_jeu

ERREUR_PING_ABSENT = re.compile(r"status of 404.*/api/ping")      # serveur statique : pas de /api/ping
ERREUR_CSV_ABSENT = re.compile(r"status of 404.*/api/csv/")       # mode serveur : table absente = table vide
NOM_DOSSIER = "donnees-formats"
FORMAT_COURANT = 4
VERROU = "verrou.txt"
# T188 (D170) : au premier démarrage d'une version, sauvegarde « avant-mise-a-jour » (avant le passage), puis
# derniere-version.json ; chaque sauvegarde a son manifeste.json (vérifiés par tests/test_sauvegardes_dossier.py).
DERNIERE_VERSION = "derniere-version.json"
MANIFESTE = "manifeste.json"
MOTIF_AVANT_MISE_A_JOUR = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-mise-a-jour$")
MOTIF_AVANT_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-format-v%d$" % FORMAT_COURANT)
MOTIF_QUOTIDIENNE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Valeur par défaut des colonnes que les formats 2, 3 et 4 ajoutent (js/schema.js ; note de conception du format 4,
# §2.1) : anomalie_constatee est un booléen, source_periodicite une liste (défaut « saisie »).
DEFAUTS = {"valeur_remplacement": "", "symptome_code": "", "ot_origine_id": "", "anomalie_constatee": "0", "astuce": "",
           "cout_arret_h": "", "habilitation_requise": "", "recyclage_mois": "", "justificatif": "", "catalogue_id": "",
           "nature_source": "", "source_periodicite": "saisie", "catalogue_relu_le": ""}

# Reprise des observations en réserves (D183, CS170) : reserves_controle.csv, ses colonnes (note de conception du
# format 4, §2.2), le commentaire fixe des réserves reprises levées, et les réserves attendues des jeux, recopiées de
# tests/fixtures/formats/LISEZMOI.md : (id, controle_id, date_controle, texte, levee). Les autres jeux tirés des démos
# (f2-v1.1.0, f3-v1.2.0 et leurs variantes) ont le même seul contrôle à observations que f3-v2.1.0 (CTR-0004).
RESERVES = "reserves_controle.csv"
BOM = b"\xef\xbb\xbf"
COLONNES_RESERVES = ["id", "controle_id", "date_controle", "texte", "gravite", "echeance_levee", "levee", "date_levee",
                     "commentaire_levee", "ot_id"]
COMMENTAIRE_LEVEE_REPRISE = "levée avant la 2.2, date inconnue"
RESERVES_DU_LISEZMOI = {
    "reserves-a-reprendre": [
        ("RES-00001", "CTR-0001", "2026-02-10", "Garde-corps de la passerelle desserré", "0"),
        ("RES-00002", "CTR-0001", "2026-02-10", "Fin de course haut à régler", "0"),
        ("RES-00003", "CTR-0001", "2026-02-10", "Câble de levage : un toron cassé", "0"),
        ("RES-00004", "CTR-0002", "2026-03-18", "Klaxon de recul inaudible", "1"),
        ("RES-00005", "CTR-0002", "2026-03-18", "Ceinture du siège conducteur usée", "1"),
        ("RES-00006", "CTR-0005", "2026-03-24", "- Raccord de la vanne 3 suintant", "0"),
        ("RES-00007", "CTR-0005", "2026-03-24", "= Pression basse à surveiller", "0"),
        ("RES-00008", "CTR-0005", "2026-03-24", "- Étiquette du fluide illisible", "0"),
        ("RES-00009", "CTR-0006", "2026-06-02", 'Gaine "B" percée ; débit insuffisant', "0"),
        ("RES-00010", "CTR-0006", "2026-06-02", 'Filtre du caisson "F7" colmaté', "0"),
        ("RES-00011", "CTR-0007", "2026-01-15", "Cellule de sécurité inopérante", "0"),
        ("RES-00012", "CTR-0007", "2026-01-15", "Bord sensible fendu", "0"),
        ("RES-00013", "CTR-0007", "2026-01-15", "Signalisation au sol effacée", "0"),
        ("RES-00014", "CTR-0007", "2026-01-15", "Notice absente du local", "0"),
        ("RES-00015", "CTR-0008", "", "Rapport du contrôle initial non retrouvé", "0"),
    ],
    "f3-v2.1.0": [
        ("RES-00001", "CTR-0004", "2025-04-03", "Purgeur automatique du réservoir défectueux : à remplacer avant la "
                                                "prochaine inspection.", "0"),
    ],
}
MOTIF_DEBUT_DANGEREUX = re.compile(r"^[=+\-@\t\r]")       # js/donnees.js : cellule texte écrite après une apostrophe


def ligne_reprise(id, controle_id, date_controle, texte, levee):
    """Cellules (telles que dans le fichier) d'une réserve reprise : texte écrit comme un champ texte (« - … »
    devient « '- … ») ; gravité, échéance, date de levée et OT vides ; commentaire fixe seulement si levée."""
    cellule_texte = "'" + texte if MOTIF_DEBUT_DANGEREUX.match(texte) else texte
    return [id, controle_id, date_controle, cellule_texte, "", "", levee, "",
            COMMENTAIRE_LEVEE_REPRISE if levee == "1" else "", ""]


UNE_RESERVE = [ligne_reprise(*r) for r in RESERVES_DU_LISEZMOI["f3-v2.1.0"]]
QUINZE_RESERVES = [ligne_reprise(*r) for r in RESERVES_DU_LISEZMOI["reserves-a-reprendre"]]

# Ce que le passage doit écrire, par jeu : fichiers de données changés (hors journal), lignes de journal (table
# parametres, ligne version_schema), sans la suite « ; sauvegarde … faite juste avant », et lignes attendues de
# reserves_controle.csv (cellules ; [] : fichier jamais créé).
TABLES_DU_FORMAT_4 = {"equipements.csv", "ordres_travail.csv", "habilitations.csv", "controles_reglementaires.csv",
                      "parametres.csv"}
PASSAGE_3 = "passage au format 3 du fichier"
PASSAGE_4 = "passage au format 4 du fichier"
ATTENDUS = {
    "f1": ({"demandes.csv", "equipements.csv", "ordres_travail.csv", "parametres.csv"},
           ["passage au format 2 du fichier", PASSAGE_3, PASSAGE_4], []),
    "f2-v1.1.0": (TABLES_DU_FORMAT_4, [PASSAGE_3, PASSAGE_4], UNE_RESERVE),
    "melange": (TABLES_DU_FORMAT_4, ["fichiers complétés au format 3 : ordres_travail", PASSAGE_4], UNE_RESERVE),
    "f3-v1.2.0": (TABLES_DU_FORMAT_4, [PASSAGE_4], UNE_RESERVE),
    "f3-v2.0.0": (TABLES_DU_FORMAT_4, [PASSAGE_4], UNE_RESERVE),
    "f3-v2.1.0": (TABLES_DU_FORMAT_4, [PASSAGE_4], UNE_RESERVE),
    "reserves-a-reprendre": (TABLES_DU_FORMAT_4, [PASSAGE_4], QUINZE_RESERVES),
    "colonnes-en-trop": (TABLES_DU_FORMAT_4, [PASSAGE_4], UNE_RESERVE),
    "table-absente": (TABLES_DU_FORMAT_4, [PASSAGE_4], UNE_RESERVE),
    "sans-bom": (TABLES_DU_FORMAT_4, [PASSAGE_4], UNE_RESERVE),
    "entete-tronque": (TABLES_DU_FORMAT_4 - {"ordres_travail.csv"}, [PASSAGE_4], UNE_RESERVE),   # OT abîmé, laissé
}
# T206a : un jeu abîmé fait noter, à la sauvegarde du jour, la date « abîmé depuis » de ses tables dans
# fichiers-abimes.json ({"depuis": {"<table>": "AAAA-MM-JJTHH:MM:SS"}}, racine du dossier).
FICHIERS_ABIMES = "fichiers-abimes.json"
JEUX_ABIMES = {"entete-tronque"}
MOTIF_DEPUIS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
# Règle de T201 (décision du 04/11), appliquée au bandeau du passage par T408 : un fichier laissé tel quel est dit au
# responsable avec son bandeau (fichier cité, « tel quel ») ; au technicien et au demandeur, sans jargon.
BANDEAU_NON_RESPONSABLE = ("Fichier abîmé : prévenez le responsable. Tant qu'il n'est pas réparé, Prévo refuse les "
                           "enregistrements qui le touchent, sans rien perdre.")
JARGON = ("tel quel", "en-tête", "format", ".csv")
TECHNICIEN = "TEC-0001"
BANDEAUX_JS = """() => Array.from(document.querySelectorAll('#alertes-app > *'))
  .map((e) => e.textContent.replace(/\\s+/g, ' ').trim())"""

# ---------------------------------------------------------------------------
# Dossier simulé (OPFS) : écriture des fichiers d'un jeu, instantané de tout le dossier
# ---------------------------------------------------------------------------

ECRIRE_OPFS_JS = """async ([nom, fichiers]) => {
  let racine = await (await navigator.storage.getDirectory()).getDirectoryHandle(nom, { create: true });
  for (const [chemin, enBase64] of Object.entries(fichiers)) {
    const morceaux = chemin.split('/');
    let dossier = racine;
    for (const sous of morceaux.slice(0, -1)) { dossier = await dossier.getDirectoryHandle(sous, { create: true }); }
    const binaire = atob(enBase64);
    const octets = new Uint8Array(binaire.length);
    for (let i = 0; i < binaire.length; i += 1) { octets[i] = binaire.charCodeAt(i); }
    const flux = await (await dossier.getFileHandle(morceaux[morceaux.length - 1], { create: true })).createWritable();
    await flux.write(octets);
    await flux.close();
  }
}"""

INSTANTANE_OPFS_JS = """async (nom) => {
  const resultat = {};
  async function parcourir(dossier, prefixe) {
    for await (const entree of dossier.values()) {
      if (entree.kind === 'directory') { await parcourir(entree, prefixe + entree.name + '/'); continue; }
      const octets = new Uint8Array(await (await entree.getFile()).arrayBuffer());
      let binaire = '';
      for (let i = 0; i < octets.length; i += 0x8000) {
        binaire += String.fromCharCode.apply(null, octets.subarray(i, i + 0x8000));
      }
      resultat[prefixe + entree.name] = btoa(binaire);
    }
  }
  await parcourir(await (await navigator.storage.getDirectory()).getDirectoryHandle(nom, { create: true }), '');
  return resultat;
}"""

# Une sauvegarde impossible (disque plein simulé) tant que localStorage['test.sauvegardeEnPanne'] vaut '1' :
# StockageDossier.creer est enveloppé avant le démarrage de l'application (son écouteur passe après celui-ci).
SAUVEGARDE_EN_PANNE_JS = """
document.addEventListener('DOMContentLoaded', () => {
  const creer = StockageDossier.creer;
  StockageDossier.creer = async function () {
    const adaptateur = await creer.apply(this, arguments);
    if (localStorage.getItem('test.sauvegardeEnPanne') === '1') {
      adaptateur.sauvegarder = async () => { throw new Donnees.ErreurStockage('Disque plein (simulé).'); };
      adaptateur.sauvegarderAvantMiseAJour = adaptateur.sauvegarder;        // T188 : la sauvegarde « avant-mise-a-jour » aussi
    }
    return adaptateur;
  };
});
"""

# Un fichier qu'on ne peut pas enregistrer (tenu ouvert par Excel, simulé) tant que
# localStorage['test.enregistrementEnPanne'] vaut le nom de sa table : passage interrompu à cette table.
ENREGISTREMENT_EN_PANNE_JS = """
document.addEventListener('DOMContentLoaded', () => {
  const creer = StockageDossier.creer;
  StockageDossier.creer = async function () {
    const adaptateur = await creer.apply(this, arguments);
    const enregistrer = adaptateur.enregistrer;
    adaptateur.enregistrer = async function (nomTable) {
      if (localStorage.getItem('test.enregistrementEnPanne') === nomTable) {
        throw new Donnees.ErreurStockage('Fichier tenu par Excel (simulé).');
      }
      return enregistrer.apply(this, arguments);
    };
    return adaptateur;
  };
});
"""


def fichiers_du_jeu(nom):
    """{chemin relatif (« / ») : octets} d'une copie du jeu, faite dans un dossier temporaire."""
    with tempfile.TemporaryDirectory(prefix="prevo-formats-") as temporaire:
        dossier = copier_jeu(nom, Path(temporaire) / "donnees")
        return {p.relative_to(dossier).as_posix(): p.read_bytes() for p in sorted(dossier.rglob("*")) if p.is_file()}


def lire_table(octets):
    """(en-tête, lignes) d'un CSV, cellules brutes (apostrophes de protection comprises), lignes vides sautées."""
    try:
        texte = octets.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = octets.decode("cp1252")
    lignes = [l for l in csv.reader(io.StringIO(texte, newline=""), delimiter=";") if any(c.strip() for c in l)]
    return (lignes[0], lignes[1:]) if lignes else ([], [])


def cellule(ligne, position):
    return ligne[position] if position < len(ligne) else ""


def version_schema(octets):
    entete, lignes = lire_table(octets)
    for ligne in lignes:
        if cellule(ligne, entete.index("cle")) == "version_schema":
            valeur = cellule(ligne, entete.index("valeur"))
            return valeur[1:] if valeur.startswith("'") else valeur
    return None


def journal_de_version(octets, deja=0):
    """Actions du journal (à partir de la ligne de données n° deja) qui concernent parametres.version_schema."""
    if octets is None:
        return []
    entete, lignes = lire_table(octets)
    t, i, a = entete.index("table"), entete.index("id_ligne"), entete.index("action")
    return [cellule(l, a) for l in lignes[deja:] if cellule(l, t) == "parametres" and cellule(l, i) == "version_schema"]


class CasFormats(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(ERREUR_PING_ABSENT)

    # -- dossier simulé ----------------------------------------------------------------------

    def instantane(self, page=None):
        brut = (page or self.page).evaluate(INSTANTANE_OPFS_JS, NOM_DOSSIER)
        return {chemin: base64.b64decode(valeur) for chemin, valeur in brut.items()}

    def ouvrir_dossier(self, statique, fichiers, profil="demandeur"):
        """Application ouverte (état « prêt ») sur un dossier simulé qui contient `fichiers` (technicien : TEC-0001)."""
        installer_dossier_simule(self.contexte, NOM_DOSSIER)
        preregler_profil(self.contexte, profil, nom="Lucie Essai",
                         technicien_id=TECHNICIEN if profil == "technicien" else "")
        self.page.goto(statique.url + "/index.html")
        self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        envoyes = {chemin: base64.b64encode(octets).decode("ascii") for chemin, octets in fichiers.items()}
        self.page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, envoyes])
        self.assertEqual(self.instantane(), fichiers)
        self.page.click("#btn-dossier")
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("App.mode"), "dossier")

    def rouvrir_dossier(self):
        self.page.reload()
        self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        self.page.click("#btn-reprendre")
        attendre_pret(self.page)

    # -- vérifications -----------------------------------------------------------------------

    def verifier_cellules_gardees(self, nom_fichier, avant, apres):
        """Toute cellule du fichier d'origine se retrouve, sous le même nom de colonne et à la même ligne ; les
        colonnes ajoutées portent leur valeur par défaut ; seule la valeur de version_schema peut changer."""
        entete_avant, lignes_avant = lire_table(avant)
        entete_apres, lignes_apres = lire_table(apres)
        ajoutees = [nom for nom in entete_apres if nom not in entete_avant]
        self.assertTrue(set(ajoutees) <= set(DEFAUTS), "%s : colonnes ajoutées %r" % (nom_fichier, ajoutees))
        if nom_fichier == "parametres.csv":
            cles_avant = [cellule(l, entete_avant.index("cle")) for l in lignes_avant]
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

    def verifier_sauvegardes(self, origine, apres, attendue):
        """Chaque sauvegarde garde les fichiers d'origine à l'octet (faite avant toute écriture : sans
        reserves_controle.csv s'il n'était pas là) ; une seule « avant-format-v4 » si un passage était à faire, aucune
        sinon ; une seule « avant-mise-a-jour » (T188, premier démarrage de cette version). Rend le nom de la
        sauvegarde avant format."""
        dossiers = sorted({chemin.split("/")[1] for chemin in apres if chemin.startswith("sauvegardes/")})
        avant_format = [nom for nom in dossiers if MOTIF_AVANT_FORMAT.match(nom)]
        self.assertEqual(len(avant_format), 1 if attendue else 0, dossiers)
        self.assertEqual(len([nom for nom in dossiers if MOTIF_AVANT_MISE_A_JOUR.match(nom)]), 1, dossiers)
        self.assertTrue(all(MOTIF_AVANT_FORMAT.match(nom) or MOTIF_QUOTIDIENNE.match(nom)
                            or MOTIF_AVANT_MISE_A_JOUR.match(nom) for nom in dossiers), dossiers)
        csv_origine = {chemin: octets for chemin, octets in origine.items() if "/" not in chemin and chemin.endswith(".csv")}
        for nom in dossiers:
            copie = {chemin.split("/", 2)[2]: octets for chemin, octets in apres.items()
                     if chemin.startswith("sauvegardes/%s/" % nom) and not chemin.endswith("/" + MANIFESTE)}
            self.assertTrue(copie, nom)
            for fichier, octets in copie.items():
                self.assertEqual(octets, csv_origine.get(fichier), "sauvegarde %s : %s" % (nom, fichier))
        return avant_format[0] if avant_format else None

    def verifier_reserves(self, octets, attendues, avant=None):
        """reserves_controle.csv tel que Prévo l'écrit (BOM, en-tête du schéma, CRLF) : exactement les lignes
        attendues (cellules), dans l'ordre ; un fichier qui existait avant le passage garde ses octets en tête."""
        self.assertTrue(octets.startswith(BOM + ";".join(COLONNES_RESERVES).encode("ascii") + b"\r\n"))
        self.assertTrue(octets.endswith(b"\r\n"))
        entete, lignes = lire_table(octets)
        self.assertEqual(entete, COLONNES_RESERVES)
        self.assertEqual(lignes, attendues)
        if avant is not None:
            self.assertTrue(octets.startswith(avant), "réserves existantes réécrites autrement")
        # En mémoire : les mêmes réserves, apostrophe de protection relue.
        en_memoire = self.page.evaluate("Donnees.lignes('reserves_controle').map((l) => [l.id, l.controle_id, l.texte])")
        relire = lambda c: c[1:] if c.startswith("'") and MOTIF_DEBUT_DANGEREUX.match(c[1:]) else c
        self.assertEqual(en_memoire, [[l[0], l[1], relire(l[3])] for l in attendues])

    def verifier_passage(self, nom_jeu, profil="demandeur", origine=None, attendus=None):
        """Ouverture d'un jeu (ou des fichiers `origine`), puis seconde ouverture ; `attendus` : (fichiers changés,
        lignes de journal, lignes de reserves_controle.csv), ATTENDUS[nom_jeu] par défaut."""
        changes_attendus, journal_attendu, reserves_attendues = attendus or ATTENDUS[nom_jeu]
        origine = origine if origine is not None else fichiers_du_jeu(nom_jeu)
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier(statique, origine, profil)
            apres = self.instantane()

            # Rien n'a disparu ; en plus : verrou.txt, derniere-version.json (T188), journal.csv (s'il y a un passage),
            # reserves_controle.csv (s'il y a des réserves à reprendre), fichiers-abimes.json pour un jeu abîmé (T206a)
            # et les sauvegardes. Jamais garanties.csv ni contrats_prestataires.csv (tables vides non créées).
            self.assertTrue(set(origine) <= set(apres), sorted(set(origine) - set(apres)))
            nouveaux = {chemin for chemin in set(apres) - set(origine) if not chemin.startswith("sauvegardes/")}
            attendus = {VERROU, DERNIERE_VERSION} | ({FICHIERS_ABIMES} if nom_jeu in JEUX_ABIMES else set())
            if reserves_attendues and RESERVES not in origine:
                attendus.add(RESERVES)
            self.assertTrue(attendus <= nouveaux <= attendus | {"journal.csv"}, nouveaux)
            if nom_jeu in JEUX_ABIMES:
                depuis = json.loads(apres[FICHIERS_ABIMES].decode("utf-8"))["depuis"]
                self.assertTrue(depuis and all(MOTIF_DEPUIS.match(date) for date in depuis.values()), depuis)
            nom_sauvegarde = self.verifier_sauvegardes(origine, apres, bool(changes_attendus))

            # Seuls les fichiers attendus ont changé (les autres sont identiques à l'octet), sans perdre une cellule.
            changes = {chemin for chemin in origine if apres[chemin] != origine[chemin]} - {"journal.csv"}
            self.assertEqual(changes, changes_attendus)
            for chemin in sorted(changes - {RESERVES}):
                self.verifier_cellules_gardees(chemin, origine[chemin], apres[chemin])

            # Les réserves reprises (D183), écrites comme Prévo les écrit.
            if reserves_attendues:
                self.verifier_reserves(apres[RESERVES], reserves_attendues, origine.get(RESERVES))
            else:
                self.assertEqual(apres.get(RESERVES), origine.get(RESERVES))
            if "journal.csv" in origine:
                # Le journal ne fait que grandir : ses lignes d'origine restent, cellule pour cellule.
                entete_avant, lignes_avant = lire_table(origine["journal.csv"])
                entete_apres, lignes_apres = lire_table(apres["journal.csv"])
                self.assertEqual(entete_apres, entete_avant)
                self.assertEqual(lignes_apres[:len(lignes_avant)], lignes_avant)
            if changes_attendus:
                self.assertEqual(version_schema(apres["parametres.csv"]), str(FORMAT_COURANT))

            # Le journal : une ligne par étape, et rien d'autre (profil demandeur : pas d'OT préventifs).
            deja = len(lire_table(origine["journal.csv"])[1]) if "journal.csv" in origine else 0
            if journal_attendu:
                actions = journal_de_version(apres.get("journal.csv"), deja)
                suite = " ; sauvegarde %s faite juste avant" % nom_sauvegarde
                self.assertEqual(actions, [ligne + suite for ligne in journal_attendu])
                self.assertEqual(len(lire_table(apres["journal.csv"])[1]), deja + len(journal_attendu))
            else:
                self.assertEqual(apres.get("journal.csv"), origine.get("journal.csv"))

            # En mémoire : plus rien à compléter.
            etat = self.page.evaluate("Donnees.etatDuFormat()")
            self.assertEqual((etat["depart"], etat["aCompleter"]), (FORMAT_COURANT, []), etat)
            self.assertFalse(self.page.evaluate("Donnees.lectureSeule()"))
            self.assertEqual(self.page.locator("#bandeau-lecture-seule").count(), 0)

            # Seconde ouverture : rien n'est écrit (verrou.txt mis à part).
            self.rouvrir_dossier()
            seconde = self.instantane()
            sans_verrou = lambda instantane: {c: o for c, o in instantane.items() if c != VERROU}
            self.assertEqual(sans_verrou(seconde), sans_verrou(apres))
        return origine, apres


# ---------------------------------------------------------------------------
# Mode dossier : passage au format courant par le navigateur
# ---------------------------------------------------------------------------

class TestDossierPassage(CasFormats):

    def test_f1_format_1_vers_4_trois_etapes_sauvegarde_d_abord(self):
        origine, apres = self.verifier_passage("f1")
        # Les tables absentes ne sont pas créées (lues vides, écrites à leur première écriture) ; sans contrôle, pas
        # de reserves_controle.csv.
        self.assertEqual(sorted(c for c in apres if c.endswith(".csv") and "/" not in c),
                         sorted(list(origine) + ["journal.csv"]))

    def test_f2_v1_1_0_format_2_vers_4(self):
        _, apres = self.verifier_passage("f2-v1.1.0")
        self.assertNotIn("wiki_pages.csv", apres)
        self.assertNotIn("wiki_journal.csv", apres)
        self.assertEqual(lire_table(apres["ordres_travail.csv"])[0][-2:], ["astuce", "habilitation_requise"])

    def test_melange_fichier_au_format_2_complete_puis_format_4(self):
        _, apres = self.verifier_passage("melange")
        self.assertEqual(version_schema(apres["parametres.csv"]), "4")

    def test_f3_v1_2_0_format_3_vers_4_une_reserve(self):
        self.verifier_passage("f3-v1.2.0")

    def test_f3_v2_0_0_format_3_vers_4_acces_intact(self):
        origine, apres = self.verifier_passage("f3-v2.0.0")
        self.assertEqual(apres["acces/comptes.json"], origine["acces/comptes.json"])

    def test_f3_v2_1_0_base_2_1_passe_au_format_4_observations_en_reserve(self):
        """CS169, CS170 : une base de la 2.1 passe au format 4 après sa sauvegarde ; l'observation de CTR-0004 devient
        une réserve ; une seconde ouverture n'écrit rien (verifier_passage)."""
        self.verifier_passage("f3-v2.1.0")

    def test_reserves_a_reprendre_quinze_reserves_de_d183(self):
        _, apres = self.verifier_passage("reserves-a-reprendre")
        self.assertEqual(self.page.evaluate("Donnees.lignes('controles_reglementaires').length"), 9)
        # Les contrôles gardent leurs observations (CS169 ; cellule pour cellule : verifier_passage), et leur colonne
        # inconnue ; six ont des observations non blanches (CTR-0009 n'a que des lignes blanches).
        entete, lignes = lire_table(apres["controles_reglementaires.csv"])
        self.assertIn("remarque_maison", entete)
        self.assertEqual(sum(1 for l in lignes if cellule(l, entete.index("observations")).strip()), 6)

    def test_colonnes_en_trop_format_3_vers_4(self):
        self.verifier_passage("colonnes-en-trop")

    def test_table_absente_format_3_vers_4_tables_non_creees(self):
        _, apres = self.verifier_passage("table-absente")
        self.assertNotIn("wiki_pages.csv", apres)
        self.assertNotIn("articles.csv", apres)

    def test_sans_bom_format_3_vers_4(self):
        self.verifier_passage("sans-bom")

    def test_entete_tronque_format_3_vers_4_problemes_de_lecture_toujours_signales(self):
        self.verifier_passage("entete-tronque")
        # Le fichier abîmé reste signalé par la lecture (colonnes absentes, valeurs au-delà de l'en-tête).
        signales = self.page.evaluate("""Donnees.problemes().filter((p) => p.table === 'ordres_travail'
            && p.type === 'colonne' && p.gravite === 'attention').length""")
        self.assertGreater(signales, 0)

    def test_controle_deja_dote_d_une_reserve_rien_de_plus(self):
        """D183, règle par contrôle : CTR-0002 a déjà une réserve (RES-00040, saisie dans la 2.2 avant la reprise) :
        il ne reçoit rien de plus, sa réserve reste à l'octet en tête du fichier ; les autres contrôles à observations
        reçoivent les leurs, numérotées à la suite (RES-00041…)."""
        origine = fichiers_du_jeu("reserves-a-reprendre")
        existante = ["RES-00040", "CTR-0002", "2026-03-18", "Klaxon de recul à remplacer", "majeure", "2026-04-17", "0",
                     "", "", ""]
        origine[RESERVES] = BOM + (";".join(COLONNES_RESERVES) + "\r\n" + ";".join(existante) + "\r\n").encode("utf-8")
        autres = [r for r in RESERVES_DU_LISEZMOI["reserves-a-reprendre"] if r[1] != "CTR-0002"]
        attendues = [existante] + [ligne_reprise("RES-%05d" % (41 + n), *r[1:]) for n, r in enumerate(autres)]
        self.assertEqual(len(attendues), 14)
        self.verifier_passage("reserves-a-reprendre", origine=origine,
                              attendus=(TABLES_DU_FORMAT_4 | {RESERVES}, [PASSAGE_4], attendues))

    def verifier_bandeau_laissee(self, profil, fichier):
        """Bandeau « Fichier abîmé » de l'ouverture, selon le profil (règle de T201, T408) : un seul ; au responsable le
        sien (fichier cité, « tel quel ») ; au technicien et au demandeur « prévenez le responsable », sans jargon."""
        bandeaux = [b for b in self.page.evaluate(BANDEAUX_JS) if "abîmé" in b]
        self.assertEqual(len(bandeaux), 1, bandeaux)
        if profil == "responsable":
            self.assertIn("Fichier abîmé laissé tel quel : %s." % fichier, bandeaux[0])
            self.assertNotIn("prévenez le responsable", bandeaux[0])
            return
        self.assertIn(BANDEAU_NON_RESPONSABLE, bandeaux[0])
        for mot in JARGON:
            self.assertNotIn(mot, bandeaux[0].lower())

    def verifier_table_laissee(self, origine, nom_table, changes_attendus, journal_attendu, reserves_attendues):
        """Ouverture par le demandeur d'une base dont `nom_table` est abîmée : elle n'est jamais réécrite, elle est
        signalée (problème « erreur » ; bandeau sans jargon, T408), le reste passe au format 4 (`changes_attendus`
        réécrits, `reserves_attendues` reprises : [] → pas de reserves_controle.csv) ; une seconde ouverture n'écrit
        rien."""
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier(statique, origine)
            apres = self.instantane()
            nom = self.verifier_sauvegardes(origine, apres, True)
            fichier = nom_table + ".csv"
            self.assertEqual(apres[fichier], origine[fichier])                              # jamais réécrit
            changes = {c for c in origine if apres[c] != origine[c]}
            self.assertEqual(changes, changes_attendus | {"parametres.csv", "journal.csv"})
            crees = {c for c in apres if c not in origine and "/" not in c and c.endswith(".csv")}
            self.assertEqual(crees, {RESERVES} if reserves_attendues else set())
            if reserves_attendues:
                self.verifier_reserves(apres[RESERVES], reserves_attendues)
            self.assertEqual(version_schema(apres["parametres.csv"]), str(FORMAT_COURANT))
            deja = len(lire_table(origine["journal.csv"])[1])
            self.assertEqual(journal_de_version(apres["journal.csv"], deja),
                             ["%s ; sauvegarde %s faite juste avant" % (ligne, nom) for ligne in journal_attendu])
            # Signalé : un problème « erreur » et un bandeau dans la coque.
            signale = self.page.evaluate("""(t) => Donnees.problemes().filter((p) => p.table === t
                && p.gravite === 'erreur' && p.message.includes('le laisse tel quel')).length""", nom_table)
            self.assertEqual(signale, 1)
            self.verifier_bandeau_laissee("demandeur", fichier)
            # Seconde ouverture : rien n'est écrit.
            self.rouvrir_dossier()
            self.assertEqual({c: o for c, o in self.instantane().items() if c != VERROU},
                             {c: o for c, o in apres.items() if c != VERROU})

    def test_entete_tronque_dans_une_base_au_format_2_jamais_reecrit_et_signale(self):
        origine = fichiers_du_jeu("entete-tronque")
        self.assertIn(b"version_schema;'3", origine["parametres.csv"])
        origine["parametres.csv"] = origine["parametres.csv"].replace(b"version_schema;'3", b"version_schema;'2")
        self.verifier_table_laissee(origine, "ordres_travail",
                                    {"equipements.csv", "habilitations.csv", "controles_reglementaires.csv"},
                                    [PASSAGE_3, PASSAGE_4], UNE_RESERVE)

    def test_fichier_au_format_2_avec_une_valeur_au_dela_de_l_en_tete_jamais_reecrit_et_signale(self):
        """CS140 : ordres_travail.csv au format 2 dont la dernière ligne porte une valeur au-delà de l'en-tête. Le
        réécrire au format 4 perdrait cette valeur : le passage le laisse tel quel et le signale."""
        origine = fichiers_du_jeu("f2-v1.1.0")
        self.assertTrue(origine["ordres_travail.csv"].endswith(b"\r\n"))
        origine["ordres_travail.csv"] = origine["ordres_travail.csv"][:-2] + b";valeur en trop\r\n"
        self.verifier_table_laissee(origine, "ordres_travail",
                                    {"equipements.csv", "habilitations.csv", "controles_reglementaires.csv"},
                                    [PASSAGE_3, PASSAGE_4], UNE_RESERVE)

    def test_controles_abimes_aucune_reserve_reprise_et_signale(self):
        """Note de conception du format 4, §5.1 : controles_reglementaires.csv abîmé (valeur au-delà de l'en-tête)
        n'est jamais réécrit et aucune réserve n'en est reprise (pas de reserves_controle.csv) ; il est signalé ; le
        reste passe au format 4."""
        origine = fichiers_du_jeu("reserves-a-reprendre")
        self.assertTrue(origine["controles_reglementaires.csv"].endswith(b"\r\n"))
        origine["controles_reglementaires.csv"] = origine["controles_reglementaires.csv"][:-2] + b";valeur en trop\r\n"
        self.verifier_table_laissee(origine, "controles_reglementaires",
                                    {"equipements.csv", "ordres_travail.csv", "habilitations.csv"}, [PASSAGE_4], [])
        self.assertEqual(self.page.evaluate("Donnees.lignes('reserves_controle').length"), 0)

    def test_entete_tronque_technicien_sans_jargon_puis_bandeau_du_responsable_a_sa_connexion(self):
        """Règle de T201 (T408) : le technicien ouvre la base au format 3 dont le passage laisse ordres_travail.csv tel
        quel : « Fichier abîmé : prévenez le responsable », sans jargon. À l'ouverture suivante, le responsable a le
        bandeau « Fichier abîmé » du responsable (fichier cité, Contrôle de la base). Le fichier n'est jamais réécrit."""
        origine = fichiers_du_jeu("entete-tronque")
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier(statique, origine, profil="technicien")
            self.assertEqual(self.page.evaluate("App.profil.type"), "technicien")
            self.assertEqual(version_schema(self.instantane()["parametres.csv"]), str(FORMAT_COURANT))
            self.verifier_bandeau_laissee("technicien", "ordres_travail.csv")
            self.page.evaluate("localStorage.setItem('prevo.profil', JSON.stringify({type: 'responsable', nom: '', "
                               "technicienId: ''}))")
            self.rouvrir_dossier()
            self.assertEqual(self.page.evaluate("App.profil.type"), "responsable")
            bandeaux = [b for b in self.page.evaluate(BANDEAUX_JS) if "abîmé" in b]
            self.assertEqual(len(bandeaux), 1, bandeaux)
            self.assertIn("Fichier abîmé : ordres_travail.csv, repéré aujourd'hui.", bandeaux[0])
            self.assertIn("Paramètres › Contrôle de la base", bandeaux[0])
            self.assertEqual(self.instantane()["ordres_travail.csv"], origine["ordres_travail.csv"])

    def test_entete_tronque_le_responsable_garde_son_bandeau_au_passage(self):
        """T408 : le responsable qui ouvre la même base garde le bandeau du passage (fichier cité, « tel quel »)."""
        origine = fichiers_du_jeu("entete-tronque")
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier(statique, origine, profil="responsable")
            self.assertEqual(version_schema(self.instantane()["parametres.csv"]), str(FORMAT_COURANT))
            self.verifier_bandeau_laissee("responsable", "ordres_travail.csv")
            self.assertEqual(self.instantane()["ordres_travail.csv"], origine["ordres_travail.csv"])

    def test_sauvegarde_impossible_rien_n_est_ecrit_puis_passage_a_l_ouverture_suivante(self):
        origine = fichiers_du_jeu("f2-v1.1.0")
        self.contexte.add_init_script("try { localStorage.setItem('test.sauvegardeEnPanne', '1'); } catch (e) {}")
        self.contexte.add_init_script(SAUVEGARDE_EN_PANNE_JS)
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier(statique, origine, profil="responsable")
            self.page.wait_for_load_state("networkidle")
            apres = self.instantane()
            # Rien n'est écrit (ni réserve, ni OT préventif) : seul verrou.txt est apparu.
            self.assertEqual({c: o for c, o in apres.items() if c != VERROU}, origine)
            alertes = self.page.inner_text("#alertes-app")
            self.assertIn("Disque plein (simulé)", alertes)
            self.assertIn("les OT préventifs échus ne sont pas générés automatiquement", alertes)
            self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "2")
            self.assertEqual(self.page.evaluate("Donnees.lignes('reserves_controle').length"), 0)
            self.assertEqual(self.page.evaluate("performance.getEntriesByName('prevo:preventif').length"), 1)

            # Ouverture suivante, sauvegarde rétablie : le passage se fait, réserve comprise.
            self.contexte.add_init_script("try { localStorage.removeItem('test.sauvegardeEnPanne'); } catch (e) {}")
            self.rouvrir_dossier()
            suivant = self.instantane()
            nom = self.verifier_sauvegardes(origine, suivant, True)
            self.assertEqual(version_schema(suivant["parametres.csv"]), str(FORMAT_COURANT))
            self.verifier_reserves(suivant[RESERVES], UNE_RESERVE)
            deja = len(lire_table(origine["journal.csv"])[1])
            actions = journal_de_version(suivant["journal.csv"], deja)
            for ligne in (PASSAGE_3, PASSAGE_4):
                self.assertIn("%s ; sauvegarde %s faite juste avant" % (ligne, nom), actions)

    def verifier_passage_interrompu(self, table_en_panne):
        """Passage interrompu à `table_en_panne` (fichier tenu par Excel, simulé), puis repris à l'ouverture suivante :
        aucune réserve en double, une seule ligne de journal (celle de l'ouverture qui finit le passage), version_schema
        au format 4 seulement à la fin ; une troisième ouverture n'écrit rien."""
        origine = fichiers_du_jeu("reserves-a-reprendre")
        self.contexte.add_init_script("try { localStorage.setItem('test.enregistrementEnPanne', '%s'); } catch (e) {}"
                                      % table_en_panne)
        self.contexte.add_init_script(ENREGISTREMENT_EN_PANNE_JS)
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier(statique, origine)
            interrompu = self.instantane()
            self.verifier_sauvegardes(origine, interrompu, True)
            self.assertIn("Fichier tenu par Excel (simulé)", self.page.inner_text("#alertes-app"))
            # Les tables du format 4 sont complétées ; version_schema n'a pas bougé ; rien au journal.
            self.assertEqual(version_schema(interrompu["parametres.csv"]), "3")
            self.assertEqual(interrompu["parametres.csv"], origine["parametres.csv"])
            self.assertEqual(interrompu["journal.csv"], origine["journal.csv"])
            for fichier in TABLES_DU_FORMAT_4 - {"parametres.csv"}:
                self.assertNotEqual(interrompu[fichier], origine[fichier], fichier)
            if table_en_panne == "reserves_controle":
                self.assertNotIn(RESERVES, interrompu)
            else:
                self.verifier_reserves(interrompu[RESERVES], QUINZE_RESERVES)

            # Ouverture suivante, fichier libéré : le passage reprend à l'étape 3→4, sans doublon.
            self.contexte.add_init_script("try { localStorage.removeItem('test.enregistrementEnPanne'); } catch (e) {}")
            self.rouvrir_dossier()
            repris = self.instantane()
            self.verifier_reserves(repris[RESERVES], QUINZE_RESERVES)
            if table_en_panne != "reserves_controle":
                self.assertEqual(repris[RESERVES], interrompu[RESERVES])
            for fichier in TABLES_DU_FORMAT_4 - {"parametres.csv"}:
                self.assertEqual(repris[fichier], interrompu[fichier], fichier + " réécrit à la reprise")
            self.assertEqual(version_schema(repris["parametres.csv"]), str(FORMAT_COURANT))
            sauvegardes = sorted({c.split("/")[1] for c in repris if c.startswith("sauvegardes/")
                                  and MOTIF_AVANT_FORMAT.match(c.split("/")[1])})
            self.assertEqual(len(sauvegardes), 2, sauvegardes)          # une par ouverture qui a tenté le passage
            deja = len(lire_table(origine["journal.csv"])[1])
            self.assertEqual(journal_de_version(repris["journal.csv"], deja),
                             ["%s ; sauvegarde %s faite juste avant" % (PASSAGE_4, sauvegardes[-1])])
            self.assertEqual(self.page.evaluate("Donnees.etatDuFormat().depart"), FORMAT_COURANT)

            # Troisième ouverture : rien n'est écrit.
            self.rouvrir_dossier()
            self.assertEqual({c: o for c, o in self.instantane().items() if c != VERROU},
                             {c: o for c, o in repris.items() if c != VERROU})

    def test_passage_interrompu_apres_les_reserves_repris_sans_doublon(self):
        # parametres.csv tenu : réserves écrites, version_schema pas encore ; la reprise ne recrée rien.
        self.verifier_passage_interrompu("parametres")

    def test_passage_interrompu_avant_les_reserves_repris_sans_doublon(self):
        # reserves_controle.csv tenu : tables complétées, pas de réserves ; la reprise les écrit une fois.
        self.verifier_passage_interrompu("reserves_controle")


# ---------------------------------------------------------------------------
# Lecture seule : données d'une version plus récente (plus-recent, version_schema 5)
# ---------------------------------------------------------------------------

TENTER_ECRITURES_JS = """async () => {
  const essais = {
    modifier: () => Donnees.modifier('parametres', (lignes) => { lignes.push({ cle: 'essai', valeur: '1' }); }),
    ajouter: () => Donnees.ajouter('journal', [{ table: 'parametres', id_ligne: 'essai', action: 'essai' }]),
    enregistrer: () => App.adaptateur.enregistrer('parametres', new Uint8Array([1]), null),
    ecrireDocument: () => App.adaptateur.ecrireDocument('essai.txt', new Blob(['essai'])),
    sauvegarder: () => App.adaptateur.sauvegarder(),
    restaurer: () => App.adaptateur.restaurer('2000-01-01'),
    migrer: () => Donnees.migrerAuFormatCourant(),
  };
  const resultats = {};
  for (const [nom, essai] of Object.entries(essais)) {
    try {
      resultats[nom] = { ok: true, valeur: await essai() };
    } catch (erreur) {
      resultats[nom] = { ok: false, nom: erreur.name, lectureSeule: erreur instanceof Donnees.ErreurLectureSeule,
        stockage: erreur instanceof Donnees.ErreurStockage, message: erreur.message };
    }
  }
  return resultats;
}"""


class TestLectureSeule(CasFormats):

    def verifier_refus(self, resultats, sans_adaptateur=()):
        migrer = resultats.pop("migrer")
        self.assertEqual((migrer["ok"], migrer["valeur"]["misAJour"]), (True, False), migrer)
        for nom, resultat in resultats.items():
            if nom in sans_adaptateur:
                continue
            with self.subTest(ecriture=nom):
                self.assertFalse(resultat["ok"], resultat)
                self.assertEqual(resultat["nom"], "ErreurLectureSeule")
                self.assertTrue(resultat["lectureSeule"] and resultat["stockage"])
                self.assertIn("version plus récente de Prévo", resultat["message"])
                self.assertIn("format 5", resultat["message"])
                self.assertIn("dernière version de Prévo", resultat["message"])

    def verifier_bandeau(self):
        bandeau = self.page.locator("#alertes-app #bandeau-lecture-seule")
        self.assertTrue(bandeau.is_visible())
        texte = bandeau.inner_text()
        self.assertIn("Lecture seule", texte)
        self.assertIn("format 5", texte)
        self.assertEqual(bandeau.locator("button").count(), 0)          # pas de « Fermer »

    def test_dossier_aucun_octet_modifie_bandeau_partout_et_ecritures_refusees(self):
        origine = fichiers_du_jeu("plus-recent")
        entete, lignes = lire_table(origine["equipements.csv"])
        equipement = lignes[0][entete.index("id")]
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier(statique, origine)
            self.page.wait_for_load_state("networkidle")
            self.assertTrue(self.page.evaluate("Donnees.lectureSeule()"))
            self.verifier_bandeau()
            # L'application reste consultable : la table inconnue est ignorée, les connues sont lues.
            self.assertGreater(self.page.evaluate("Donnees.lignes('equipements').length"), 0)

            # Une demande envoyée par l'interface est refusée, avec le message clair.
            self.page.evaluate("id => { location.hash = '#/di/nouvelle?equipement=' + id; }", equipement)
            self.page.wait_for_selector(".di-envoyer")
            self.verifier_bandeau()                                      # sur cet écran aussi
            self.page.fill("input[name=symptome]", "Fuite d'huile")
            self.page.click("label.tuile:has(input[value='dégradé'])")
            self.page.fill("textarea[name=description]", "Essai en lecture seule.")
            self.page.click(".di-envoyer")
            self.page.wait_for_function("document.getElementById('toast').innerText.includes('lecture seule')")
            self.assertEqual(self.page.locator(".di-numero").count(), 0)

            # Les écritures directes sont refusées (Donnees et adaptateur), le passage ne fait rien.
            self.verifier_refus(self.page.evaluate(TENTER_ECRITURES_JS))

            self.page.evaluate("location.hash = '#/accueil'")
            self.page.wait_for_function("document.documentElement.dataset.etat === 'pret'")
            self.verifier_bandeau()
            # Aucun octet modifié dans le dossier : ni passage, ni journal, ni sauvegarde, ni verrou.txt.
            self.assertEqual(self.instantane(), origine)

            # Seconde ouverture : toujours rien.
            self.rouvrir_dossier()
            self.verifier_bandeau()
            self.assertEqual(self.instantane(), origine)

    def test_demo_depuis_les_csv_deposes_lecture_seule_et_bandeau(self):
        with tempfile.TemporaryDirectory(prefix="prevo-formats-") as temporaire:
            dossier = copier_jeu("plus-recent", Path(temporaire) / "donnees")
            fichiers = [str(p) for p in sorted(dossier.glob("*.csv"))]
            preregler_profil(self.contexte, "responsable", nom="Claire Essai")
            self.page.goto(url_fichier("index.html"))
            self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            self.page.set_input_files("#fichiers-csv", fichiers)
            attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("App.mode"), "demo")
        self.assertTrue(self.page.evaluate("Donnees.lectureSeule()"))
        self.verifier_bandeau()
        self.assertFalse(self.page.evaluate("document.getElementById('bandeau-demo').hidden"))
        # Responsable : aucun OT préventif généré à l'ouverture, rien au journal ; écritures refusées.
        origine = fichiers_du_jeu("plus-recent")
        for table in ("ordres_travail", "journal"):
            self.assertEqual(self.page.evaluate("t => Donnees.lignes(t).length", table),
                             len(lire_table(origine[table + ".csv"])[1]), table)
        self.verifier_refus(self.page.evaluate(TENTER_ECRITURES_JS))

    def test_serveur_lecture_seule_aucun_octet_modifie_par_le_navigateur(self):
        with tempfile.TemporaryDirectory(prefix="prevo-formats-") as temporaire:
            source = copier_jeu("plus-recent", Path(temporaire) / "donnees")
            self.autoriser_erreur(ERREUR_CSV_ABSENT)
            with ServeurPrevo(source=source) as serveur:
                copier_jeu("plus-recent", serveur.dossier)
                avant = {p.relative_to(serveur.dossier).as_posix(): p.read_bytes()
                         for p in serveur.dossier.rglob("*") if p.is_file()}
                preregler_profil(self.contexte, "responsable", nom="Claire Essai")
                self.page.goto(serveur.url + "/#/accueil")
                attendre_pret(self.page)
                self.page.wait_for_load_state("networkidle")
                self.assertTrue(self.page.evaluate("Donnees.lectureSeule()"))
                self.verifier_bandeau()
                self.verifier_refus(self.page.evaluate(TENTER_ECRITURES_JS))
                apres = {p.relative_to(serveur.dossier).as_posix(): p.read_bytes()
                         for p in serveur.dossier.rglob("*") if p.is_file()}
                self.assertEqual(apres, avant)


# ---------------------------------------------------------------------------
# Base déjà au format 4 (f4-v2.2.0, T394) : rien à faire, des deux côtés
# ---------------------------------------------------------------------------

class TestFormat4SansPassage(CasFormats):

    def verifier_tables_du_format_4(self):
        """Les tables du format 4 du jeu, lues en mémoire ; plus rien à compléter, pas de lecture seule."""
        lues = self.page.evaluate("""() => ({
          reserves: Donnees.lignes('reserves_controle').map((l) => [l.id, l.controle_id, l.levee, l.date_levee]),
          garanties: Donnees.lignes('garanties').map((l) => l.id),
          contrats: Donnees.lignes('contrats_prestataires').map((l) => [l.id, l.reconduction_tacite]),
          etat: Donnees.etatDuFormat(), lectureSeule: Donnees.lectureSeule(),
          version: Donnees.parametre('version_schema') })""")
        self.assertEqual(lues["reserves"], [["RES-00001", "CTR-0004", "0", ""], ["RES-00002", "CTR-0001", "0", ""],
                                            ["RES-00003", "CTR-0002", "1", "2026-04-02"]])
        self.assertEqual(lues["garanties"], ["GAR-0001", "GAR-0002"])
        self.assertEqual(lues["contrats"], [["CTP-0001", "1"], ["CTP-0002", "0"]])
        self.assertEqual((lues["etat"]["depart"], lues["etat"]["aCompleter"]), (FORMAT_COURANT, []), lues["etat"])
        self.assertFalse(lues["lectureSeule"])
        self.assertEqual(lues["version"], str(FORMAT_COURANT))
        self.assertEqual(self.page.locator("#bandeau-lecture-seule").count(), 0)

    def test_dossier_f4_rien_a_migrer_aucun_fichier_change(self):
        """Mode dossier : ni sauvegarde avant-format-v4, ni journal, ni fichier changé (verrou.txt et
        derniere-version.json mis à part), réserves gardées à l'octet ; seconde ouverture : rien (verifier_passage)."""
        origine, apres = self.verifier_passage("f4-v2.2.0", attendus=(set(), [], []))
        self.assertIn(RESERVES, origine)
        self.assertEqual({c: o for c, o in apres.items() if c in origine}, origine)
        self.verifier_tables_du_format_4()

    def test_serveur_f4_demarrage_et_navigateur_n_ecrivent_rien(self):
        """Mode serveur : le démarrage ne réécrit aucune donnée (ni passage, ni sauvegarde avant-format-v4) ; le
        navigateur lit la base au format 4 sans rien écrire ni signaler."""
        origine = fichiers_du_jeu("f4-v2.2.0")
        with tempfile.TemporaryDirectory(prefix="prevo-formats-") as temporaire:
            source = copier_jeu("f4-v2.2.0", Path(temporaire) / "donnees")
            self.autoriser_erreur(ERREUR_CSV_ABSENT)
            with ServeurPrevo(source=source) as serveur:
                avant = {p.relative_to(serveur.dossier).as_posix(): p.read_bytes()
                         for p in serveur.dossier.rglob("*") if p.is_file()}
                self.assertEqual({c: o for c, o in avant.items() if "/" not in c and c.endswith(".csv")}, origine)
                self.assertFalse([c for c in avant if "_avant-format-v" in c])
                self.assertNotIn("passage au format", serveur.sortie_console())
                preregler_profil(self.contexte, "demandeur", nom="Lucie Essai")
                self.page.goto(serveur.url + "/#/accueil")
                attendre_pret(self.page)
                self.page.wait_for_load_state("networkidle")
                self.verifier_tables_du_format_4()
                self.assertNotIn("pas encore au format", self.page.inner_text("#alertes-app"))
                resultat = self.page.evaluate("Donnees.migrerAuFormatCourant()")
                self.assertFalse(resultat["misAJour"], resultat)
                apres = {p.relative_to(serveur.dossier).as_posix(): p.read_bytes()
                         for p in serveur.dossier.rglob("*") if p.is_file()}
                self.assertEqual(apres, avant)


# ---------------------------------------------------------------------------
# Démo (CSV déposés) et serveur
# ---------------------------------------------------------------------------

class TestDemoEtServeur(CasFormats):

    def test_demo_f1_depose_passage_en_memoire_sans_sauvegarde(self):
        origine = fichiers_du_jeu("f1")
        with tempfile.TemporaryDirectory(prefix="prevo-formats-") as temporaire:
            dossier = copier_jeu("f1", Path(temporaire) / "donnees")
            preregler_profil(self.contexte, "demandeur", nom="Lucie Essai")
            self.page.goto(url_fichier("index.html"))
            self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            self.page.set_input_files("#fichiers-csv", [str(p) for p in sorted(dossier.glob("*.csv"))])
            attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("App.mode"), "demo")
        self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), str(FORMAT_COURANT))
        actions = self.page.evaluate("""Donnees.lignes('journal').filter((l) => l.table === 'parametres'
            && l.id_ligne === 'version_schema').map((l) => l.action)""")
        self.assertEqual(actions, [ligne + " ; sans sauvegarde (démo)"
                                   for ligne in ("passage au format 2 du fichier", PASSAGE_3, PASSAGE_4)])
        self.assertEqual(self.page.evaluate("Donnees.lignes('reserves_controle').length"), 0)   # aucun contrôle
        # Les tables réécrites (en mémoire) gardent toutes leurs cellules.
        for table in ("demandes", "equipements", "ordres_travail"):
            octets = bytes(self.page.evaluate(
                "async (t) => Array.from((await App.adaptateur.charger(t)).octets)", table))
            self.assertNotEqual(octets, origine[table + ".csv"])
            self.verifier_cellules_gardees(table + ".csv", origine[table + ".csv"], octets)

    def test_serveur_f2_le_navigateur_n_ecrit_rien_bandeau_au_responsable(self):
        with tempfile.TemporaryDirectory(prefix="prevo-formats-") as temporaire:
            source = copier_jeu("f2-v1.1.0", Path(temporaire) / "donnees")
            self.autoriser_erreur(ERREUR_CSV_ABSENT)
            with ServeurPrevo(source=source) as serveur:
                # Les fichiers du jeu, tels quels, même si le serveur avait pu les mettre à jour à son démarrage
                # (T185) : c'est le cas « le serveur n'a pas pu » (Excel ouvert) que le navigateur doit montrer.
                copier_jeu("f2-v1.1.0", serveur.dossier)
                avant = {p.relative_to(serveur.dossier).as_posix(): p.read_bytes()
                         for p in serveur.dossier.rglob("*") if p.is_file()}
                preregler_profil(self.contexte, "responsable", nom="Claire Essai")
                self.page.goto(serveur.url + "/#/accueil")
                attendre_pret(self.page)
                self.page.wait_for_timeout(500)
                # Le navigateur ne passe pas au format courant : aucune écriture, aucune sauvegarde, pas d'OT.
                resultat = self.page.evaluate("Donnees.migrerAuFormatCourant()")
                self.assertFalse(resultat["misAJour"], resultat)
                self.assertEqual(resultat["sauvegarde"], None)
                apres = {p.relative_to(serveur.dossier).as_posix(): p.read_bytes()
                         for p in serveur.dossier.rglob("*") if p.is_file()}
                self.assertEqual(apres, avant)
                self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "2")
                alertes = self.page.inner_text("#alertes-app")
                self.assertIn("pas encore au format %d" % FORMAT_COURANT, alertes)
                self.assertIn("relancez Prévo", alertes)
                self.assertIn("fermez Excel", alertes)
                self.assertFalse(self.page.evaluate("Donnees.lectureSeule()"))


if __name__ == "__main__":
    unittest.main()
