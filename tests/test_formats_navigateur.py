"""Passage au format courant par le navigateur et lecture seule des données plus récentes (chantier « socle de
données », T186 ; décisions D167 à D169 ; js/donnees.js §4.11 et js/app.js, passerAuFormatCourant).

Chaque cas ouvre l'APPLICATION ENTIÈRE (index.html) sur une copie d'un jeu de tests/fixtures/formats/ (jeux_formats,
toujours dans un dossier temporaire, puis dans l'OPFS du navigateur : jamais de données réelles) :

    dossier  : pour f1, f2-v1.1.0, f3-v1.2.0, f3-v2.0.0, melange, colonnes-en-trop, table-absente, sans-bom et
               entete-tronque (profil demandeur : pas d'OT préventifs générés) :
                 - la sauvegarde « avant-format-v3 » (et la quotidienne) garde les fichiers d'origine à l'octet : elle
                   a été faite avant toute écriture ; aucune sauvegarde quand il n'y a rien à faire ;
                 - seuls les fichiers attendus changent ; aucune cellule d'origine perdue (comparaison champ à champ
                   avec le fichier d'origine) ; les colonnes ajoutées portent leur valeur par défaut ;
                 - les lignes de journal attendues (« passage au format N du fichier ; sauvegarde … faite juste
                   avant », ou « fichiers complétés au format 3 : ordres_travail ; … » pour melange) ;
                 - une seconde ouverture n'écrit rien ;
               entete-tronque dans une base au format 2, et ordres_travail.csv au format 2 avec une valeur au-delà
               de l'en-tête (CS140 : la réécriture la perdrait) : le fichier abîmé n'est jamais réécrit, il est
               signalé (problème « erreur » et bandeau), le reste passe au format 3 ;
               sauvegarde impossible : rien n'est écrit, bandeau, pas d'OT préventifs ; l'ouverture suivante passe ;
    lecture seule (plus-recent, version_schema 4) : dossier → aucun octet modifié dans le dossier (pas même
               verrou.txt), bandeau sur tous les écrans, demande envoyée par l'interface refusée, écritures directes
               (Donnees, adaptateur) refusées par ErreurLectureSeule ; démo chargée depuis les CSV déposés et
               serveur → lecture seule et bandeau aussi ;
    démo     : f1 déposé → passage en mémoire, deux lignes « … ; sans sauvegarde (démo) » ;
    serveur  : copie de f2-v1.1.0 → le navigateur n'écrit rien (aucun octet modifié), bandeau au responsable.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_formats_navigateur.py" -v
"""
import base64
import csv
import io
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
FORMAT_COURANT = 3
VERROU = "verrou.txt"
MOTIF_AVANT_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-format-v3$")
MOTIF_QUOTIDIENNE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Valeur par défaut des colonnes que les formats 2 et 3 ajoutent (js/schema.js) : anomalie_constatee est un booléen.
DEFAUTS = {"valeur_remplacement": "", "symptome_code": "", "ot_origine_id": "", "anomalie_constatee": "0", "astuce": ""}

# Ce que le passage doit écrire, par jeu : fichiers de données changés (hors journal) et lignes de journal
# (table parametres, ligne version_schema), sans la suite « ; sauvegarde … faite juste avant ».
ATTENDUS = {
    "f1": ({"demandes.csv", "equipements.csv", "ordres_travail.csv", "parametres.csv"},
           ["passage au format 2 du fichier", "passage au format 3 du fichier"]),
    "f2-v1.1.0": ({"ordres_travail.csv", "parametres.csv"}, ["passage au format 3 du fichier"]),
    "melange": ({"ordres_travail.csv"}, ["fichiers complétés au format 3 : ordres_travail"]),
    "f3-v1.2.0": (set(), []),
    "f3-v2.0.0": (set(), []),
    "colonnes-en-trop": (set(), []),
    "table-absente": (set(), []),
    "sans-bom": (set(), []),
    "entete-tronque": (set(), []),
}

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
    }
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
        """Application ouverte (état « prêt ») sur un dossier simulé qui contient `fichiers`."""
        installer_dossier_simule(self.contexte, NOM_DOSSIER)
        preregler_profil(self.contexte, profil, nom="Lucie Essai")
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
        """Chaque sauvegarde garde les fichiers d'origine à l'octet (faite avant toute écriture) ; une seule
        « avant-format-v3 » si un passage était à faire, aucune sinon. Rend le nom de la sauvegarde avant format."""
        dossiers = sorted({chemin.split("/")[1] for chemin in apres if chemin.startswith("sauvegardes/")})
        avant_format = [nom for nom in dossiers if MOTIF_AVANT_FORMAT.match(nom)]
        self.assertEqual(len(avant_format), 1 if attendue else 0, dossiers)
        self.assertTrue(all(MOTIF_AVANT_FORMAT.match(nom) or MOTIF_QUOTIDIENNE.match(nom) for nom in dossiers), dossiers)
        csv_origine = {chemin: octets for chemin, octets in origine.items() if "/" not in chemin and chemin.endswith(".csv")}
        for nom in dossiers:
            copie = {chemin.split("/", 2)[2]: octets for chemin, octets in apres.items()
                     if chemin.startswith("sauvegardes/%s/" % nom)}
            self.assertTrue(copie, nom)
            for fichier, octets in copie.items():
                self.assertEqual(octets, csv_origine.get(fichier), "sauvegarde %s : %s" % (nom, fichier))
        return avant_format[0] if avant_format else None

    def verifier_passage(self, nom_jeu, profil="demandeur"):
        changes_attendus, journal_attendu = ATTENDUS[nom_jeu]
        origine = fichiers_du_jeu(nom_jeu)
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier(statique, origine, profil)
            apres = self.instantane()

            # Rien n'a disparu ; en plus : verrou.txt, journal.csv (s'il y a un passage) et les sauvegardes.
            self.assertTrue(set(origine) <= set(apres), sorted(set(origine) - set(apres)))
            nouveaux = {chemin for chemin in set(apres) - set(origine) if not chemin.startswith("sauvegardes/")}
            self.assertTrue(nouveaux <= {VERROU, "journal.csv"}, nouveaux)
            nom_sauvegarde = self.verifier_sauvegardes(origine, apres, bool(changes_attendus))

            # Seuls les fichiers attendus ont changé, sans perdre une cellule.
            changes = {chemin for chemin in origine if apres[chemin] != origine[chemin]} - {"journal.csv"}
            self.assertEqual(changes, changes_attendus)
            for chemin in sorted(changes):
                self.verifier_cellules_gardees(chemin, origine[chemin], apres[chemin])
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

    def test_f1_format_1_vers_3_deux_etapes_sauvegarde_d_abord(self):
        origine, apres = self.verifier_passage("f1")
        # Les tables absentes ne sont pas créées (lues vides, écrites à leur première écriture).
        self.assertEqual(sorted(c for c in apres if c.endswith(".csv") and "/" not in c),
                         sorted(list(origine) + ["journal.csv"]))

    def test_f2_v1_1_0_format_2_vers_3(self):
        _, apres = self.verifier_passage("f2-v1.1.0")
        self.assertNotIn("wiki_pages.csv", apres)
        self.assertNotIn("wiki_journal.csv", apres)
        self.assertEqual(lire_table(apres["ordres_travail.csv"])[0][-1], "astuce")

    def test_melange_fichier_au_format_2_complete_sans_changer_version_schema(self):
        _, apres = self.verifier_passage("melange")
        self.assertEqual(version_schema(apres["parametres.csv"]), "3")

    def test_f3_v1_2_0_rien_a_faire(self):
        self.verifier_passage("f3-v1.2.0")

    def test_f3_v2_0_0_rien_a_faire_acces_intact(self):
        origine, apres = self.verifier_passage("f3-v2.0.0")
        self.assertEqual(apres["acces/comptes.json"], origine["acces/comptes.json"])

    def test_colonnes_en_trop_rien_a_faire(self):
        self.verifier_passage("colonnes-en-trop")

    def test_table_absente_rien_a_faire_tables_non_creees(self):
        _, apres = self.verifier_passage("table-absente")
        self.assertNotIn("wiki_pages.csv", apres)
        self.assertNotIn("articles.csv", apres)

    def test_sans_bom_rien_a_faire(self):
        self.verifier_passage("sans-bom")

    def test_entete_tronque_rien_a_faire_problemes_de_lecture_toujours_signales(self):
        self.verifier_passage("entete-tronque")
        # Le fichier abîmé reste signalé par la lecture (colonnes absentes, valeurs au-delà de l'en-tête).
        signales = self.page.evaluate("""Donnees.problemes().filter((p) => p.table === 'ordres_travail'
            && p.type === 'colonne' && p.gravite === 'attention').length""")
        self.assertGreater(signales, 0)

    def verifier_table_laissee(self, origine, nom_table):
        """Ouverture d'une base au format 2 dont `nom_table` est abîmée : elle n'est jamais réécrite, elle est signalée
        (problème « erreur » et bandeau), le reste passe au format 3 ; une seconde ouverture n'écrit rien."""
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier(statique, origine)
            apres = self.instantane()
            nom = self.verifier_sauvegardes(origine, apres, True)
            fichier = nom_table + ".csv"
            self.assertEqual(apres[fichier], origine[fichier])                              # jamais réécrit
            changes = {c for c in origine if apres[c] != origine[c]}
            self.assertEqual(changes, {"parametres.csv", "journal.csv"})
            self.assertEqual(version_schema(apres["parametres.csv"]), "3")
            deja = len(lire_table(origine["journal.csv"])[1])
            self.assertEqual(journal_de_version(apres["journal.csv"], deja),
                             ["passage au format 3 du fichier ; sauvegarde %s faite juste avant" % nom])
            # Signalé : un problème « erreur » et un bandeau dans la coque.
            signale = self.page.evaluate("""(t) => Donnees.problemes().filter((p) => p.table === t
                && p.gravite === 'erreur' && p.message.includes('le laisse tel quel')).length""", nom_table)
            self.assertEqual(signale, 1)
            alertes = self.page.inner_text("#alertes-app")
            self.assertIn(fichier, alertes)
            self.assertIn("tel quel", alertes)
            # Seconde ouverture : rien n'est écrit.
            self.rouvrir_dossier()
            self.assertEqual({c: o for c, o in self.instantane().items() if c != VERROU},
                             {c: o for c, o in apres.items() if c != VERROU})

    def test_entete_tronque_dans_une_base_au_format_2_jamais_reecrit_et_signale(self):
        origine = fichiers_du_jeu("entete-tronque")
        self.assertIn(b"version_schema;'3", origine["parametres.csv"])
        origine["parametres.csv"] = origine["parametres.csv"].replace(b"version_schema;'3", b"version_schema;'2")
        self.verifier_table_laissee(origine, "ordres_travail")

    def test_fichier_au_format_2_avec_une_valeur_au_dela_de_l_en_tete_jamais_reecrit_et_signale(self):
        """CS140 : ordres_travail.csv au format 2 dont la dernière ligne porte une valeur au-delà de l'en-tête. Le
        réécrire au format 3 perdrait cette valeur : le passage le laisse tel quel et le signale."""
        origine = fichiers_du_jeu("f2-v1.1.0")
        self.assertTrue(origine["ordres_travail.csv"].endswith(b"\r\n"))
        origine["ordres_travail.csv"] = origine["ordres_travail.csv"][:-2] + b";valeur en trop\r\n"
        self.verifier_table_laissee(origine, "ordres_travail")

    def test_sauvegarde_impossible_rien_n_est_ecrit_puis_passage_a_l_ouverture_suivante(self):
        origine = fichiers_du_jeu("f2-v1.1.0")
        self.contexte.add_init_script("try { localStorage.setItem('test.sauvegardeEnPanne', '1'); } catch (e) {}")
        self.contexte.add_init_script(SAUVEGARDE_EN_PANNE_JS)
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier(statique, origine, profil="responsable")
            self.page.wait_for_load_state("networkidle")
            apres = self.instantane()
            # Rien n'est écrit (pas même d'OT préventif) : seul verrou.txt est apparu.
            self.assertEqual({c: o for c, o in apres.items() if c != VERROU}, origine)
            alertes = self.page.inner_text("#alertes-app")
            self.assertIn("Disque plein (simulé)", alertes)
            self.assertIn("les OT préventifs échus ne sont pas générés automatiquement", alertes)
            self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "2")
            self.assertEqual(self.page.evaluate("performance.getEntriesByName('prevo:preventif').length"), 1)

            # Ouverture suivante, sauvegarde rétablie : le passage se fait.
            self.contexte.add_init_script("try { localStorage.removeItem('test.sauvegardeEnPanne'); } catch (e) {}")
            self.rouvrir_dossier()
            suivant = self.instantane()
            nom = self.verifier_sauvegardes(origine, suivant, True)
            self.assertEqual(version_schema(suivant["parametres.csv"]), "3")
            deja = len(lire_table(origine["journal.csv"])[1])
            self.assertIn("passage au format 3 du fichier ; sauvegarde %s faite juste avant" % nom,
                          journal_de_version(suivant["journal.csv"], deja))


# ---------------------------------------------------------------------------
# Lecture seule : données d'une version plus récente (plus-recent, version_schema 4)
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
                self.assertIn("format 4", resultat["message"])
                self.assertIn("dernière version de Prévo", resultat["message"])

    def verifier_bandeau(self):
        bandeau = self.page.locator("#alertes-app #bandeau-lecture-seule")
        self.assertTrue(bandeau.is_visible())
        texte = bandeau.inner_text()
        self.assertIn("Lecture seule", texte)
        self.assertIn("format 4", texte)
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
        self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "3")
        actions = self.page.evaluate("""Donnees.lignes('journal').filter((l) => l.table === 'parametres'
            && l.id_ligne === 'version_schema').map((l) => l.action)""")
        self.assertEqual(actions, ["passage au format 2 du fichier ; sans sauvegarde (démo)",
                                   "passage au format 3 du fichier ; sans sauvegarde (démo)"])
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
                self.assertIn("pas encore au format 3", alertes)
                self.assertIn("relancez Prévo", alertes)
                self.assertIn("fermez Excel", alertes)
                self.assertFalse(self.page.evaluate("Donnees.lectureSeule()"))


if __name__ == "__main__":
    unittest.main()
