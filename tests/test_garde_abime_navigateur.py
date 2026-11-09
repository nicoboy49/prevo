"""Garde « fichier abîmé » au niveau des adaptateurs de stockage du NAVIGATEUR (chantier i18n-socle, tâche T200a ;
suite de T197). T197 refusait de réécrire une table abîmée dans Donnees.enregistrerLignes ; la garde est désormais
aussi dans la fonction d'écriture commune de chaque adaptateur (js/stockage-dossier.js, js/stockage-serveur.js et, pour
le serveur, serveur.py : tâche T200b), par laquelle passent toutes les écritures, y compris celles qui contournent
Donnees (ajout au journal, écritures directes de l'adaptateur).

    a. TestJournalCoupeDossier, TestJournalCoupeServeur (mixin ParcoursJournalCoupe) : journal.csv qui finit par un
       guillemet ouvert (texte entre guillemets jamais fermé : une ligne ajoutée après serait avalée par cette cellule,
       donc perdue), dès l'ouverture ou pendant l'usage. Le responsable modifie un équipement par le formulaire :
       « Équipement enregistré », equipements.csv changé, journal.csv IDENTIQUE à l'octet, un seul bandeau
       « Fichier abîmé » qui cite journal.csv. Mode dossier : OPFS simulé ; mode serveur : ServeurPrevo (la variante
       serveur attend la garde de serveur.py, T200b).
    b. TestEcrituresDirectesDossier : App.adaptateur.enregistrer sur ordres_travail.csv abîmé (jeu entete-tronque) →
       ErreurFichierAbime, fichier identique ; avec { remplacerFichierAbime: true } → écrit. App.adaptateur.ajouter
       sur un journal à guillemet ouvert → ErreurFichierAbime, fichier identique.
    c. TestImportZipDossier, TestImportZipServeur (mixin ParcoursImportZip) : l'import ZIP (une des deux dérogations)
       remplace la base f4-entete-tronque par un ZIP sain (f4-v2.2.0 : bases au format 4, sans passage ni à
       l'ouverture ni à l'import) ; en mode serveur, chaque PUT de l'import porte l'en-tête X-Prevo-Remplacer-Abime: 1.
    d. TestTraductionServeur : réponses simulées (page.route) ; 409 { code: "fichier_abime", table } →
       Donnees.ErreurFichierAbime (jamais ErreurConflit), en-tête seulement pour remplacerFichierAbime === true ;
       Donnees.ajouter ne se replie pas sur modifier, et l'événement « fichierAbime » n'est émis qu'une fois par table.
    e. TestFinDansUnGuillemetOuvert : Donnees.csv.finitDansUnGuillemetOuvert sur les exemples partagés avec la fonction
       finit_dans_un_guillemet_ouvert de serveur.py (mêmes octets, même réponse).

Règle numéro un : jamais de données réelles (copies des jeux de tests/fixtures/formats/ dans des dossiers temporaires,
ou dans l'OPFS du navigateur de test).

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_garde_abime_navigateur.py" -v
"""
import base64
import json
import re
import unittest

from commun import RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, charger_scripts
from test_recette_socle import (DESIGNATION, ECRIRE_OPFS_JS, EQUIPEMENT, ERREUR_TABLE_DU_FORMAT_4_ABSENTE, NOM_DOSSIER,
                                CasRecetteSocle, fichiers_de, fichiers_du_jeu, lignes_en_dictionnaires)
from test_zip_import import (BOUTON_REMPLACER, MOTIF_AVANT_IMPORT_ZIP, contenu_sauvegarde, ecrire_zip, lire_csv,
                             sans_apostrophe, sauvegardes_de)

# Ligne coupée dans une cellule entre guillemets, sans fin de ligne (exemple de la consigne de T200).
LIGNE_COUPEE = 'J-20261104120000-ABCD;2026-11-04 12:00;"Poste coupé'.encode("utf-8")
ENTETE_REMPLACER = "x-prevo-remplacer-abime"
CHEMIN_PAGE_SERVEUR = "/tests/fixtures/page-stockage-serveur.html"
JEU_ZIP_SAIN = "f4-v2.2.0"                   # import ZIP (c) : base au format 4, rien à passer au format courant
JEU_ZIP_ABIME = "f4-entete-tronque"          # la même, ordres_travail.csv à l'en-tête coupé (T404)

# Chromium note en console.error toute réponse HTTP >= 400 : seules celles-ci sont attendues.
ERREUR_REFUS_JOURNAL = re.compile(r"status of 409.*/api/csv/journal/ajout")    # serveur : ajout refusé (T200b)
ERREUR_RESSOURCE = "Failed to load resource"                                    # réponses simulées (d)

# Exemples partagés avec serveur.py (finit_dans_un_guillemet_ouvert, T200b) : octets → finit dans un guillemet ouvert.
EXEMPLES_GUILLEMET = [
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

# Bandeaux de la coque qui citent journal.csv (texte, blancs réduits).
BANDEAUX_JOURNAL_JS = """() => Array.from(document.querySelectorAll('#alertes-app > *'))
  .map((e) => e.textContent.replace(/\\s+/g, ' ').trim()).filter((t) => t.includes('journal.csv'))"""

# Résultat d'un appel qui peut échouer : { ok, octets (base64) } ou la description de l'erreur.
ESSAI_JS = """
  const enBase64 = (octets) => {
    let binaire = '';
    for (let i = 0; i < octets.length; i += 0x8000) binaire += String.fromCharCode.apply(null, octets.subarray(i, i + 0x8000));
    return btoa(binaire);
  };
  const essai = async (action) => {
    try { await action(); return { ok: true }; } catch (erreur) {
      return { ok: false, nom: erreur.name, message: erreur.message,
        abime: erreur instanceof Donnees.ErreurFichierAbime, conflit: erreur instanceof Donnees.ErreurConflit,
        stockage: erreur instanceof Donnees.ErreurStockage, table: erreur.table === undefined ? null : erreur.table };
    }
  };
"""

# Écriture directe d'une table entière par l'adaptateur de l'application (comme parametres-zip.js, import-ecritures.js).
ENREGISTRER_DIRECT_JS = """async ([table, options]) => {""" + ESSAI_JS + """
  const octets = Donnees.instantane()[table];
  const resultat = await essai(() => (options === null
    ? App.adaptateur.enregistrer(table, octets, Donnees.version(table))
    : App.adaptateur.enregistrer(table, octets, Donnees.version(table), options)));
  return Object.assign(resultat, { octets: enBase64(octets) });
}"""

# Ajout direct au journal par l'adaptateur de l'application (en-tête + une ligne, sans BOM : comme Donnees.ajouter).
AJOUTER_DIRECT_JS = """async () => {""" + ESSAI_JS + """
  const ligne = { id: 'J-20261104130000-WXYZ', date_heure: '2026-11-04 13:00', poste: 'Poste test',
    profil: 'Demandeur', table: 'equipements', id_ligne: 'EQ-0005', action: 'essai T200a' };
  const octets = Donnees.csv.serialiser('journal', [ligne], [], { bom: false });
  return essai(() => App.adaptateur.ajouter('journal', octets));
}"""


def avec_ligne_coupee(journal):
    """journal.csv (fini par CRLF) + une ligne coupée dans une cellule entre guillemets, sans fin de ligne."""
    if not journal.endswith(b"\r\n"):
        raise AssertionError("journal.csv devrait finir par CRLF : %r" % journal[-20:])
    return journal + LIGNE_COUPEE


def en_base64(octets):
    return base64.b64encode(octets).decode("ascii")


# ---------------------------------------------------------------------------
# a. Journal qui finit par un guillemet ouvert (les deux modes)
# ---------------------------------------------------------------------------

class ParcoursJournalCoupe:
    """La classe fille donne ouvrir(fichiers, profil), apres() → {chemin : octets}, ecrire_journal(octets) et
    entetes_remplacer() → valeurs de l'en-tête X-Prevo-Remplacer-Abime vues sur les écritures."""

    def bandeaux_du_journal(self):
        return self.page.evaluate(BANDEAUX_JOURNAL_JS)

    def modifier_et_verifier(self, journal_attendu):
        """Le responsable modifie EQ-0005 : l'action réussit, equipements.csv change, journal.csv reste identique à
        l'octet, un seul bandeau « Fichier abîmé » cite journal.csv ; aucune écriture n'a demandé la dérogation."""
        self.modifier_equipement(DESIGNATION)
        self.page.wait_for_function("() => (%s)().length > 0" % BANDEAUX_JOURNAL_JS, timeout=5000)
        apres = self.apres()
        self.assertEqual(apres["journal.csv"], journal_attendu,
                         "journal.csv complété malgré son guillemet ouvert : les lignes ajoutées seraient avalées")
        equipement = next(l for l in lignes_en_dictionnaires(apres["equipements.csv"]) if l["id"] == EQUIPEMENT)
        self.assertEqual(equipement["designation"], DESIGNATION)
        bandeaux = self.bandeaux_du_journal()
        self.assertEqual(len(bandeaux), 1, bandeaux)
        self.assertIn("Fichier abîmé : journal.csv, repéré aujourd'hui.", bandeaux[0])
        self.assertEqual(self.entetes_remplacer(), [])

    def test_journal_a_guillemet_ouvert_des_l_ouverture_jamais_complete(self):
        fichiers = fichiers_du_jeu("f3-v1.2.0")
        fichiers["journal.csv"] = avec_ligne_coupee(fichiers["journal.csv"])
        self.ouvrir(fichiers, "responsable")
        # Les OT préventifs générés à l'ouverture n'ont rien ajouté au journal.
        self.assertEqual(self.apres()["journal.csv"], fichiers["journal.csv"])
        self.modifier_et_verifier(fichiers["journal.csv"])

    def test_journal_a_guillemet_ouvert_pendant_l_usage_bandeau_et_jamais_complete(self):
        self.ouvrir(fichiers_du_jeu("f3-v1.2.0"), "responsable")
        self.assertEqual(self.bandeaux_du_journal(), [])
        coupe = avec_ligne_coupee(self.apres()["journal.csv"])         # coupé par un autre programme, après l'ouverture
        self.ecrire_journal(coupe)
        self.modifier_et_verifier(coupe)


class TestJournalCoupeDossier(ParcoursJournalCoupe, CasRecetteSocle):

    def setUp(self):
        super().setUp()
        self.demarrer_statique()

    def ouvrir(self, fichiers, profil):
        self.ouvrir_dossier(fichiers, profil)

    def apres(self):
        self.page.wait_for_load_state("networkidle")
        return self.instantane()

    def ecrire_journal(self, octets):
        self.page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, {"journal.csv": en_base64(octets)}])
        self.assertEqual(self.instantane()["journal.csv"], octets)

    def entetes_remplacer(self):
        return []                                                         # mode dossier : aucune requête


class TestJournalCoupeServeur(ParcoursJournalCoupe, CasRecetteSocle):
    """Attend la garde de serveur.py (T200b) : sans elle, le serveur complète journal.csv et ces tests échouent."""

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(ERREUR_REFUS_JOURNAL)
        # Jeu au format 3 : le passage au format 4 ne crée ni garanties ni contrats_prestataires (CONCEPTION-L1 §3.3).
        self.autoriser_erreur(ERREUR_TABLE_DU_FORMAT_4_ABSENTE)
        self.ecritures = []
        self.page.on("request", self.noter_ecriture)

    def noter_ecriture(self, requete):
        if requete.method in ("PUT", "POST") and "/api/csv/" in requete.url:
            self.ecritures.append((requete.method, requete.url, requete.headers.get(ENTETE_REMPLACER)))

    def ouvrir(self, fichiers, profil):
        source = self.temporaire / "jeu" / "donnees"
        for chemin, octets in fichiers.items():
            (source / chemin).parent.mkdir(parents=True, exist_ok=True)
            (source / chemin).write_bytes(octets)
        self.serveur = ServeurPrevo(source=source)
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)
        self.ouvrir_serveur(self.serveur.url, profil)

    def apres(self):
        self.page.wait_for_load_state("networkidle")
        return fichiers_de(self.serveur.dossier)

    def ecrire_journal(self, octets):
        (self.serveur.dossier / "journal.csv").write_bytes(octets)

    def entetes_remplacer(self):
        return [ecriture for ecriture in self.ecritures if ecriture[2] is not None]


# ---------------------------------------------------------------------------
# b. Écritures qui contournent Donnees, mode dossier
# ---------------------------------------------------------------------------

class TestEcrituresDirectesDossier(CasRecetteSocle):

    def setUp(self):
        super().setUp()
        self.demarrer_statique()

    def test_enregistrer_direct_refuse_sur_fichier_abime_sauf_derogation(self):
        origine = fichiers_du_jeu("entete-tronque")
        self.ouvrir_dossier(origine, "demandeur")
        self.assertIn("ordres_travail", self.page.evaluate("Donnees.tablesAbimees()"))
        for options in (None, {}, {"remplacerFichierAbime": "oui"}, {"remplacerFichierAbime": 1}):
            with self.subTest(options=options):
                resultat = self.page.evaluate(ENREGISTRER_DIRECT_JS, ["ordres_travail", options])
                self.assertFalse(resultat["ok"], "ordres_travail.csv abîmé réécrit par l'adaptateur")
                self.assertTrue(resultat["abime"], resultat)
                self.assertFalse(resultat["conflit"], resultat)
                self.assertEqual(resultat["table"], "ordres_travail")
                self.assertIn("ordres_travail.csv est abîmé", resultat["message"])
                self.assertEqual(self.instantane()["ordres_travail.csv"], origine["ordres_travail.csv"])
        # Dérogation (import ZIP) : le fichier est remplacé par les octets donnés.
        resultat = self.page.evaluate(ENREGISTRER_DIRECT_JS, ["ordres_travail", {"remplacerFichierAbime": True}])
        self.assertTrue(resultat["ok"], resultat)
        self.assertEqual(self.instantane()["ordres_travail.csv"], base64.b64decode(resultat["octets"]))
        self.assertNotEqual(self.instantane()["ordres_travail.csv"], origine["ordres_travail.csv"])

    def test_ajouter_direct_refuse_sur_journal_a_guillemet_ouvert(self):
        fichiers = fichiers_du_jeu("f3-v1.2.0")
        fichiers["journal.csv"] = avec_ligne_coupee(fichiers["journal.csv"])
        self.ouvrir_dossier(fichiers, "demandeur")
        resultat = self.page.evaluate(AJOUTER_DIRECT_JS)
        self.assertFalse(resultat["ok"], "ligne ajoutée à un journal qui finit par un guillemet ouvert")
        self.assertTrue(resultat["abime"], resultat)
        self.assertEqual(resultat["table"], "journal")
        self.assertIn("journal.csv est abîmé", resultat["message"])
        self.assertEqual(self.instantane()["journal.csv"], fichiers["journal.csv"])


# ---------------------------------------------------------------------------
# c. Import ZIP qui remplace un fichier abîmé (les deux modes)
# ---------------------------------------------------------------------------

class ParcoursImportZip:
    """La classe fille donne ouvrir_parametres(fichiers), apres() et verifier_entetes(ecritures de l'import)."""

    def test_import_zip_sain_remplace_le_fichier_abime(self):
        zip_csv = {c: o for c, o in fichiers_du_jeu(JEU_ZIP_SAIN).items() if c.endswith(".csv")}
        chemin_zip = ecrire_zip(self.temporaire / "sain.zip", zip_csv)
        origine = fichiers_du_jeu(JEU_ZIP_ABIME)
        self.ouvrir_parametres(origine)
        self.assertIn("ordres_travail", self.page.evaluate("Donnees.tablesAbimees()"))
        self.page.set_input_files("#fichier-import-zip", str(chemin_zip))
        self.page.wait_for_selector("#confirmation-import-zip")
        debut = len(self.ecritures)
        self.page.click(BOUTON_REMPLACER)
        self.page.wait_for_selector("#import-zip-termine")
        apres = self.apres()
        # ordres_travail.csv remplacé par celui du ZIP, champ à champ ; l'original abîmé est dans la sauvegarde.
        self.assertNotEqual(apres["ordres_travail.csv"], origine["ordres_travail.csv"])
        entete, lignes = lire_csv(apres["ordres_travail.csv"])
        entete_zip, lignes_zip = lire_csv(zip_csv["ordres_travail.csv"])
        self.assertEqual(entete, entete_zip)
        self.assertEqual([{c: sans_apostrophe(v) for c, v in ligne.items()} for ligne in lignes],
                         [{c: sans_apostrophe(v) for c, v in ligne.items()} for ligne in lignes_zip])
        noms = sauvegardes_de(apres, MOTIF_AVANT_IMPORT_ZIP)
        self.assertEqual(len(noms), 1, noms)
        self.assertEqual(contenu_sauvegarde(apres, noms[0])["ordres_travail.csv"], origine["ordres_travail.csv"])
        self.verifier_entetes(self.ecritures[debut:])


class TestImportZipDossier(ParcoursImportZip, CasRecetteSocle):

    def setUp(self):
        super().setUp()
        self.demarrer_statique()
        self.ecritures = []

    def ouvrir_parametres(self, fichiers):
        self.ouvrir_dossier(fichiers, "responsable")
        self.aller("#/parametres", "#btn-import-zip")

    def apres(self):
        self.page.wait_for_load_state("networkidle")
        return self.instantane()

    def verifier_entetes(self, ecritures):
        self.assertEqual(ecritures, [])                                    # mode dossier : aucune requête


class TestImportZipServeur(ParcoursImportZip, CasRecetteSocle):

    def setUp(self):
        super().setUp()
        self.ecritures = []
        self.page.on("request", self.noter_ecriture)

    def noter_ecriture(self, requete):
        if requete.method in ("PUT", "POST") and "/api/csv/" in requete.url:
            self.ecritures.append((requete.method, requete.url.rsplit("/api/csv/", 1)[1],
                                   requete.headers.get(ENTETE_REMPLACER)))

    def ouvrir_parametres(self, fichiers):
        source = self.temporaire / "jeu" / "donnees"
        for chemin, octets in fichiers.items():
            (source / chemin).parent.mkdir(parents=True, exist_ok=True)
            (source / chemin).write_bytes(octets)
        self.serveur = ServeurPrevo(source=source)
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)
        self.ouvrir_serveur(self.serveur.url, "responsable", route="#/parametres")
        self.page.wait_for_selector("#btn-import-zip")

    def apres(self):
        self.page.wait_for_load_state("networkidle")
        return fichiers_de(self.serveur.dossier)

    def verifier_entetes(self, ecritures):
        """Chaque table remplacée par l'import (PUT) porte l'en-tête de la dérogation ; l'ajout au journal non."""
        remplacees = [e for e in ecritures if e[0] == "PUT"]
        self.assertEqual(sorted(e[1] for e in remplacees), sorted(c[:-4] for c in fichiers_du_jeu(JEU_ZIP_SAIN)
                                                                   if c.endswith(".csv")))
        self.assertEqual([e for e in remplacees if e[2] != "1"], [])
        self.assertEqual([e for e in ecritures if e[0] == "POST" and e[2] is not None], [])


# ---------------------------------------------------------------------------
# d. Traduction du 409 « fichier_abime » par js/stockage-serveur.js (réponses simulées)
# ---------------------------------------------------------------------------

REFUS_ABIME = {"erreur": "Le fichier journal.csv est abîmé : Prévo ne l'enregistre plus.", "code": "fichier_abime",
               "table": "journal"}
CONFLIT_GENERIQUE = {"erreur": "Le fichier equipements.csv a été modifié par un autre poste.",
                     "version_actuelle": "0123456789abcdef"}

TRADUCTION_JS = """async () => {""" + ESSAI_JS + """
  const stockage = StockageServeur.creer();
  const octets = new TextEncoder().encode('id;date_heure;poste;profil;table;id_ligne;action\\r\\n');
  return {
    ajout: await essai(() => stockage.ajouter('journal', octets)),
    enregistrement: await essai(() => stockage.enregistrer('journal', octets, 'v1')),
    optionNonVraie: await essai(() => stockage.enregistrer('journal', octets, 'v1', { remplacerFichierAbime: 'oui' })),
    avecOption: await essai(() => stockage.enregistrer('journal', octets, 'v1', { remplacerFichierAbime: true })),
    conflit: await essai(() => stockage.enregistrer('equipements', octets, 'v1')),
  };
}"""

DONNEES_JS = """async () => {""" + ESSAI_JS + """
  Donnees.initialiser(StockageServeur.creer(), { poste: 'Poste test', profil: 'Responsable' });
  const evenements = [];
  Donnees.evenements.addEventListener('fichierAbime', (evenement) => evenements.push(evenement.detail));
  const ajout = await essai(() => Donnees.ajouter('journal', [{ id: 'J-20261104140000-AAAA', action: 'essai' }]));
  const premier = await Donnees.journaliser('equipements', 'EQ-0005', 'essai 1');
  const second = await Donnees.journaliser('equipements', 'EQ-0005', 'essai 2');
  return { ajout: ajout, premier: premier, second: second, evenements: evenements };
}"""


class TestTraductionServeur(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(ERREUR_RESSOURCE)
        self.statique = ServeurStatique(RACINE)
        self.statique.demarrer()
        self.addCleanup(self.statique.arreter)
        self.requetes = []
        self.page.route("**/api/**", self.repondre)
        self.page.goto(self.statique.url + CHEMIN_PAGE_SERVEUR)
        self.page.wait_for_function("typeof StockageServeur === 'object' && typeof Donnees === 'object'")

    def repondre(self, route):
        requete = route.request
        chemin = requete.url.split("/api/", 1)[1]
        self.requetes.append((requete.method, chemin, requete.headers.get(ENTETE_REMPLACER)))
        if requete.method == "GET":
            route.fulfill(status=404, content_type="application/json", body=json.dumps({"erreur": "absent"}))
        elif chemin.startswith("csv/journal"):
            route.fulfill(status=409, content_type="application/json; charset=utf-8",
                          body=json.dumps(REFUS_ABIME, ensure_ascii=False))
        else:
            route.fulfill(status=409, content_type="application/json; charset=utf-8",
                          body=json.dumps(CONFLIT_GENERIQUE, ensure_ascii=False))

    def test_409_fichier_abime_traduit_et_entete_seulement_sur_demande(self):
        resultats = self.page.evaluate(TRADUCTION_JS)
        for cle in ("ajout", "enregistrement", "optionNonVraie", "avecOption"):
            with self.subTest(appel=cle):
                resultat = resultats[cle]
                self.assertFalse(resultat["ok"])
                self.assertEqual((resultat["nom"], resultat["abime"], resultat["conflit"], resultat["stockage"],
                                  resultat["table"]), ("ErreurFichierAbime", True, False, True, "journal"), resultat)
                self.assertIn("journal.csv est abîmé", resultat["message"])
        # Le 409 sans code reste un conflit (réessayé par Donnees.modifier).
        conflit = resultats["conflit"]
        self.assertEqual((conflit["nom"], conflit["conflit"], conflit["abime"]), ("ErreurConflit", True, False))
        # L'en-tête de la dérogation ne part que pour remplacerFichierAbime === true.
        self.assertEqual(self.requetes, [
            ("POST", "csv/journal/ajout", None),
            ("PUT", "csv/journal", None),
            ("PUT", "csv/journal", None),
            ("PUT", "csv/journal", "1"),
            ("PUT", "csv/equipements", None),
        ])

    def test_donnees_ajouter_sans_repli_et_un_seul_evenement_par_table(self):
        resultat = self.page.evaluate(DONNEES_JS)
        self.assertEqual((resultat["ajout"]["nom"], resultat["ajout"]["abime"]), ("ErreurFichierAbime", True),
                         resultat["ajout"])
        # journaliser n'échoue jamais pour une ligne de journal manquée : null, l'action de l'utilisateur continue.
        self.assertEqual((resultat["premier"], resultat["second"]), (None, None))
        self.assertEqual(resultat["evenements"], [{"table": "journal"}])
        # Aucun repli sur modifier (ni relecture, ni réécriture du journal) : trois ajouts, rien d'autre.
        self.assertEqual(self.requetes, [("POST", "csv/journal/ajout", None)] * 3)


# ---------------------------------------------------------------------------
# e. Donnees.csv.finitDansUnGuillemetOuvert
# ---------------------------------------------------------------------------

class TestFinDansUnGuillemetOuvert(CasNavigateur):

    def test_exemples_partages_avec_le_serveur(self):
        charger_scripts(self.page, ["js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js"])
        exemples = [list(octets) for octets, _ in EXEMPLES_GUILLEMET]
        obtenus = self.page.evaluate("""(exemples) => exemples.map((liste) => {
          const octets = Uint8Array.from(liste);
          return [Donnees.csv.finitDansUnGuillemetOuvert(octets), Donnees.csv.finitDansUnGuillemetOuvert(octets.buffer)];
        })""", exemples)
        for (octets, attendu), (sur_vue, sur_tampon) in zip(EXEMPLES_GUILLEMET, obtenus):
            with self.subTest(octets=octets):
                self.assertIs(sur_vue, attendu)
                self.assertIs(sur_tampon, attendu)


if __name__ == "__main__":
    unittest.main()
