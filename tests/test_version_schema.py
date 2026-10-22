"""Tests du passage de parametres.version_schema au format courant (tâche T37, ARCHITECTURE.md §14.1 ;
format 3 depuis le lot 6, §20.2).

Décision de Nicolas (2026-10-20) : JUSTE AVANT que version_schema passe au format courant sur une base
existante, Prévo fait une sauvegarde automatique « AAAA-MM-JJ_HHMMSS_avant-format-vN » (N = format
visé, 3 depuis le lot 6 ; une base au format 1 passe directement au format 3, une seule sauvegarde),
restaurable depuis Paramètres comme les autres (Donnees.mettreAJourVersionSchema()).

    serveur  : sauvegarde d'abord (elle garde version_schema = 1), puis version 3 sur le disque et
               ligne de journal ; second appel sans effet ; un autre poste passé au format 3
               entre-temps : rien n'est réécrit ; écran Paramètres « Avant format 3 » puis
               restauration de toutes les tables ; API brute (motif inconnu, « ../x », corps vide) ;
    format 2 : la démo remise au format 2 (sans wiki_pages.csv ni wiki_journal.csv, ordres_travail.csv
               sans la colonne astuce) passe au format 3 à l'ouverture : une sauvegarde
               « avant-format-v3 », aucun autre fichier changé à l'octet que parametres.csv et
               journal.csv, les deux tables du wiki toujours absentes (vides), la colonne astuce
               signalée en simple information et lue vide ;
    echec    : sauvegarde impossible → version inchangée sur le disque, ErreurStockage claire ;
    dossier  : même passage avec StockageDossier (dossier simulé dans l'OPFS), restauration ;
               règles de noms identiques à celles du serveur ;
    démo     : aucune sauvegarde, aucune erreur ; passage en mémoire seulement.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_version_schema.py" -v
"""
import csv
import io
import http.client
import json
import re
import shutil
import unittest

from commun import (CasNavigateur, RACINE, ServeurPrevo, ServeurStatique, attendre_pret,
                    charger_scripts, installer_dossier_simule, preregler_profil, url_fichier)

PARAMETRES_V1 = RACINE / "tests" / "fixtures" / "v1" / "parametres.csv"
TABLES_V1 = ("demandes", "equipements", "ordres_travail", "parametres")   # fichiers de tests/fixtures/v1
MOTIF_NOM_AVANT_FORMAT_2 = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-format-v2$")
FORMAT_COURANT = "3"                                   # Schema.version (js/schema.js), lot 6
MOTIF_NOM_AVANT_FORMAT_COURANT = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-format-v3$")
MOTIF_NOM_MANUEL = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
DEBUT_ERREUR_SAUVEGARDE = "Sauvegarde avant le passage au format 3 impossible : "
FIN_ERREUR_SAUVEGARDE = " ; la mise à jour sera retentée à la prochaine ouverture."
CONFLIT_PARAMETRES = re.compile(r"status of 409.*/api/csv/parametres")

# Appel de Donnees.mettreAJourVersionSchema() dans la page : { ok, valeur } ou { ok: false, nom, message }.
APPELER_MISE_A_JOUR = """async () => {
  try {
    return { ok: true, valeur: await Donnees.mettreAJourVersionSchema() };
  } catch (erreur) {
    return { ok: false, nom: erreur.name, message: erreur.message };
  }
}"""


# ---------------------------------------------------------------------------
# Lecture des CSV (comme un autre poste ou Excel)
# ---------------------------------------------------------------------------

def lignes_csv(octets):
    """Lignes (dictionnaires) d'un CSV Prévo donné en octets ; valeurs telles que dans le fichier."""
    texte = octets.decode("utf-8-sig")
    lecteur = csv.reader(texte.splitlines(), delimiter=";")
    entete = next(lecteur)
    return [dict(zip(entete, cellules)) for cellules in lecteur if any(cellules)]


def version_schema(octets):
    """Valeur de version_schema dans un parametres.csv (sans l'apostrophe de protection), ou None."""
    for ligne in lignes_csv(octets):
        if ligne["cle"] == "version_schema":
            valeur = ligne["valeur"]
            return valeur[1:] if valeur.startswith("'") else valeur
    return None


def actions_journal_version(octets_journal):
    """Actions du journal qui concernent la ligne version_schema de parametres.csv."""
    if octets_journal is None:
        return []
    return [ligne["action"] for ligne in lignes_csv(octets_journal)
            if ligne["table"] == "parametres" and ligne["id_ligne"] == "version_schema"]


# ---------------------------------------------------------------------------
# Mode serveur
# ---------------------------------------------------------------------------

class CasServeurV1(CasNavigateur):
    """Serveur de test sur le jeu de démo, dont parametres.csv est celui du lot 1 (version_schema = 1)."""

    def ouvrir_application_v1(self, serveur, route="#/accueil"):
        # Depuis T28, le DÉMARRAGE de l'application fait lui-même le passage au format courant (js/app.js ;
        # testé dans tests/test_preventif.py, famille « demarrage »). Pour tester ici l'appel
        # explicite sur une base au format 1, l'application est ouverte (jeu de démo, déjà au format
        # courant : rien n'est fait), puis le parametres.csv du lot 1 est installé et relu par la page.
        preregler_profil(self.contexte, "responsable")
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        self.assertEqual(self.sauvegardes(serveur, "*_avant-format-v*"), [])
        shutil.copyfile(str(PARAMETRES_V1), str(serveur.dossier / "parametres.csv"))
        self.page.evaluate("Donnees.rechargerTable('parametres')")
        self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "1")
        return self.page

    def mettre_a_jour(self):
        return self.page.evaluate(APPELER_MISE_A_JOUR)

    @staticmethod
    def sauvegardes(serveur, motif="*"):
        dossier = serveur.dossier / "sauvegardes"
        return sorted(p.name for p in dossier.glob(motif) if p.is_dir()) if dossier.is_dir() else []

    @staticmethod
    def octets(serveur, *chemin):
        fichier = serveur.dossier.joinpath(*chemin)
        return fichier.read_bytes() if fichier.is_file() else None


class TestServeur(CasServeurV1):

    def test_sauvegarde_d_abord_puis_version_courante_sur_le_disque_et_journal_second_appel_sans_effet(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_application_v1(serveur)
            self.assertEqual(self.sauvegardes(serveur, "*_avant-format-v*"), [])

            resultat = self.mettre_a_jour()
            self.assertTrue(resultat["ok"], resultat)
            nom = resultat["valeur"]["sauvegarde"]
            self.assertTrue(resultat["valeur"]["misAJour"])
            self.assertRegex(nom, MOTIF_NOM_AVANT_FORMAT_COURANT)

            # La sauvegarde existe sur le disque et garde l'état D'AVANT (version_schema = 1) :
            # elle a donc bien été faite avant le passage de version (une seule : 1 → 3 directement).
            self.assertEqual(self.sauvegardes(serveur, "*_avant-format-v*"), [nom])
            copie = self.octets(serveur, "sauvegardes", nom, "parametres.csv")
            self.assertEqual(copie, PARAMETRES_V1.read_bytes())
            self.assertEqual(version_schema(copie), "1")
            self.assertIsNotNone(self.octets(serveur, "sauvegardes", nom, "equipements.csv"))

            # parametres.csv vaut 3 sur le disque (les autres réglages sont gardés), une ligne de journal.
            apres = self.octets(serveur, "parametres.csv")
            self.assertEqual(version_schema(apres), FORMAT_COURANT)
            self.assertEqual({l["cle"] for l in lignes_csv(apres)}, {l["cle"] for l in lignes_csv(copie)})
            self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), FORMAT_COURANT)
            actions = actions_journal_version(self.octets(serveur, "journal.csv"))
            self.assertEqual(len(actions), 1, actions)
            self.assertIn("passage au format 3 du fichier ; sauvegarde %s faite juste avant" % nom, actions[0])

            # Second appel : rien (ni sauvegarde, ni écriture).
            toutes_avant = self.sauvegardes(serveur)
            second = self.mettre_a_jour()
            self.assertEqual(second, {"ok": True, "valeur": {"misAJour": False, "sauvegarde": None}})
            self.assertEqual(self.sauvegardes(serveur), toutes_avant)
            self.assertEqual(self.octets(serveur, "parametres.csv"), apres)
            self.assertEqual(len(actions_journal_version(self.octets(serveur, "journal.csv"))), 1)

    def test_autre_poste_deja_passe_au_format_courant_rien_n_est_reecrit(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_application_v1(serveur)
            # Pas de relecture automatique pendant le test : le cache doit rester périmé.
            self.page.evaluate("Donnees.arreterSurveillance()")
            # Un autre poste a fait le passage juste après notre lecture (notre cache dit encore 1).
            ecrit_par_l_autre_poste = PARAMETRES_V1.read_bytes().replace(b"version_schema;'1", b"version_schema;'3")
            (serveur.dossier / "parametres.csv").write_bytes(ecrit_par_l_autre_poste)
            self.autoriser_erreur(CONFLIT_PARAMETRES)     # écriture refusée (version périmée), puis relecture

            resultat = self.mettre_a_jour()
            self.assertTrue(resultat["ok"], resultat)
            # Notre sauvegarde est faite (sans gravité : deux copies), mais la version n'est pas réécrite.
            self.assertFalse(resultat["valeur"]["misAJour"])
            self.assertRegex(resultat["valeur"]["sauvegarde"], MOTIF_NOM_AVANT_FORMAT_COURANT)
            self.assertEqual(self.octets(serveur, "parametres.csv"), ecrit_par_l_autre_poste)
            self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), FORMAT_COURANT)
            self.assertEqual(actions_journal_version(self.octets(serveur, "journal.csv")), [])

    def test_ecran_parametres_avant_format_courant_puis_restauration_de_toutes_les_tables(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir_application_v1(serveur)
            nom = self.mettre_a_jour()["valeur"]["sauvegarde"]
            self.assertEqual(version_schema(self.octets(serveur, "parametres.csv")), FORMAT_COURANT)

            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_selector('#carte-sauvegardes button[data-restaurer="%s"]' % nom)
            ligne = page.locator('#carte-sauvegardes tr:has(button[data-restaurer="%s"])' % nom)
            self.assertEqual(ligne.locator(".badge").inner_text().strip(), "Avant format 3")
            self.assertIn("info", ligne.locator(".badge").get_attribute("class").split())
            heure = "%s:%s:%s" % (nom[11:13], nom[13:15], nom[15:17])
            self.assertIn(" à " + heure, ligne.inner_text())
            self.assertEqual(page.evaluate("n => Parametres.decrireSauvegarde(n).type", nom), "Avant format 3")

            # « Restaurer… » → toutes les tables (choix par défaut).
            page.click('button[data-restaurer="%s"]' % nom)
            page.wait_for_selector("#fenetre-restauration")
            self.assertIn("avant format 3", page.inner_text("#fenetre-restauration"))
            page.click("dialog .fenetre-actions .btn-danger")
            page.wait_for_selector("#nom-copie-securite")
            self.assertIn("parametres", page.inner_text("#message-action"))
            self.assertEqual(self.octets(serveur, "parametres.csv"), PARAMETRES_V1.read_bytes())
            self.assertEqual(version_schema(self.octets(serveur, "parametres.csv")), "1")
            self.assertEqual(page.evaluate("Donnees.parametre('version_schema')"), "1")

    def test_echec_de_la_sauvegarde_version_inchangee_et_erreur_claire(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_application_v1(serveur)
            journal_avant = self.octets(serveur, "journal.csv")
            # La sauvegarde échoue (méthode remplacée dans la page : disque plein, Excel…).
            self.page.evaluate("""() => { window.vraieSauvegarde = App.adaptateur.sauvegarder;
                App.adaptateur.sauvegarder = async () => {
                  throw new Donnees.ErreurStockage('Le disque est plein (simulé).'); }; }""")
            resultat = self.mettre_a_jour()
            self.assertFalse(resultat["ok"], resultat)
            self.assertEqual(resultat["nom"], "ErreurStockage")
            self.assertEqual(resultat["message"],
                             DEBUT_ERREUR_SAUVEGARDE + "Le disque est plein (simulé)" + FIN_ERREUR_SAUVEGARDE)
            # Rien n'a bougé : version 1 sur le disque et en mémoire, pas de journal, pas de sauvegarde.
            self.assertEqual(self.octets(serveur, "parametres.csv"), PARAMETRES_V1.read_bytes())
            self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "1")
            self.assertEqual(self.octets(serveur, "journal.csv"), journal_avant)
            self.assertEqual(self.sauvegardes(serveur, "*_avant-format-v*"), [])

            # Une erreur qui n'est pas une ErreurStockage (bogue, réseau) donne le même message clair.
            self.page.evaluate("() => { App.adaptateur.sauvegarder = async () => { throw new TypeError('panne'); }; }")
            resultat = self.mettre_a_jour()
            self.assertEqual((resultat["ok"], resultat["nom"]), (False, "ErreurStockage"))
            self.assertEqual(resultat["message"], DEBUT_ERREUR_SAUVEGARDE + "panne" + FIN_ERREUR_SAUVEGARDE)
            self.assertEqual(version_schema(self.octets(serveur, "parametres.csv")), "1")

            # Relecture de la vague 2 : un stockage (hors démo) qui ne sait pas sauvegarder, ou qui ne
            # renvoie aucun nom, n'est pas dispensé de la sauvegarde → refus, version inchangée.
            for remplacement, cause in (
                    ("undefined", "ce mode de stockage ne sait pas faire de sauvegarde"),
                    ("async () => undefined", "le stockage n'a pas confirmé la sauvegarde (aucun nom renvoyé)")):
                self.page.evaluate("() => { App.adaptateur.sauvegarder = %s; }" % remplacement)
                resultat = self.mettre_a_jour()
                self.assertEqual((resultat["ok"], resultat["nom"]), (False, "ErreurStockage"), remplacement)
                self.assertEqual(resultat["message"], DEBUT_ERREUR_SAUVEGARDE + cause + FIN_ERREUR_SAUVEGARDE)
                self.assertEqual(version_schema(self.octets(serveur, "parametres.csv")), "1")
                self.assertEqual(self.octets(serveur, "journal.csv"), journal_avant)

            # La fois suivante (sauvegarde rétablie), le passage se fait.
            self.page.evaluate("() => { App.adaptateur.sauvegarder = window.vraieSauvegarde; }")
            resultat = self.mettre_a_jour()
            self.assertTrue(resultat["ok"] and resultat["valeur"]["misAJour"], resultat)
            self.assertEqual(version_schema(self.octets(serveur, "parametres.csv")), FORMAT_COURANT)

    def test_passage_1_vers_3_tables_du_wiki_vides_colonne_astuce_vide_aucun_autre_fichier_change(self):
        """Lot 6 (§20.2) : une base au format 1, sans fichiers du wiki ni colonne astuce, passe directement au format
        3 ; les deux tables du wiki restent absentes (vides), la colonne astuce est lue vide (simple information),
        et seuls parametres.csv et journal.csv changent sur le disque."""
        with ServeurPrevo() as serveur:
            for nom in ("wiki_pages.csv", "wiki_journal.csv"):
                (serveur.dossier / nom).unlink()
            retirer_derniere_colonne(serveur.dossier / "ordres_travail.csv", "astuce")
            self.autoriser_erreur(re.compile(r"status of 404.*/api/csv/wiki_(pages|journal)"))   # fichier absent = table vide
            self.ouvrir_application_v1(serveur)
            avant = {p.name: p.read_bytes() for p in serveur.dossier.glob("*.csv")}
            resultat = self.mettre_a_jour()
            self.assertTrue(resultat["ok"] and resultat["valeur"]["misAJour"], resultat)
            self.assertRegex(resultat["valeur"]["sauvegarde"], MOTIF_NOM_AVANT_FORMAT_COURANT)
            apres = {p.name: p.read_bytes() for p in serveur.dossier.glob("*.csv")}
            self.assertEqual(set(apres), set(avant))                  # aucun fichier du wiki créé
            self.assertEqual(sorted(nom for nom in avant if apres[nom] != avant[nom]), ["journal.csv", "parametres.csv"])
            self.assertEqual(self.page.evaluate("[Donnees.lignes('wiki_pages').length, Donnees.lignes('wiki_journal').length]"),
                             [0, 0])
            self.assertEqual(self.page.evaluate(
                "Donnees.lignes('ordres_travail').filter((ot) => ot.astuce !== '').length"), 0)
            # (Le problème « info » de la colonne absente est prouvé par TestFormat2VersFormat3 : ici, la base a été
            # lue d'abord avec les paramètres de la démo, au format 3, avant l'installation de ceux du format 1.)


def retirer_derniere_colonne(chemin, nom):
    """Réécrit un CSV de Prévo (BOM, « ; », CRLF) sans sa dernière colonne, qui doit s'appeler `nom` : le
    fichier tel qu'une base au format 2 l'avait (lot 6 : ordres_travail.csv sans la colonne astuce)."""
    texte = chemin.read_bytes().decode("utf-8-sig")
    lignes = list(csv.reader(io.StringIO(texte, newline=""), delimiter=";"))
    assert lignes[0][-1] == nom, lignes[0][-3:]
    sortie = io.StringIO(newline="")
    csv.writer(sortie, delimiter=";", lineterminator="\r\n").writerows(ligne[:-1] for ligne in lignes)
    chemin.write_bytes(b"\xef\xbb\xbf" + sortie.getvalue().encode("utf-8"))


class TestFormat2VersFormat3(CasServeurV1):
    """Lot 6 (§20.2) : une base au format 2 (la démo sans wiki_pages.csv, wiki_journal.csv ni colonne astuce)
    passe au format 3 à l'ouverture de l'application ; seuls parametres.csv et journal.csv changent."""

    def test_ouverture_d_une_base_au_format_2_sauvegarde_puis_format_3_sans_toucher_aux_donnees(self):
        with ServeurPrevo() as serveur:
            parametres = serveur.dossier / "parametres.csv"
            octets_v3 = parametres.read_bytes()
            self.assertIn(b"version_schema;'3", octets_v3)
            parametres.write_bytes(octets_v3.replace(b"version_schema;'3", b"version_schema;'2"))
            for nom in ("wiki_pages.csv", "wiki_journal.csv"):
                (serveur.dossier / nom).unlink()
            retirer_derniere_colonne(serveur.dossier / "ordres_travail.csv", "astuce")
            avant = {p.name: p.read_bytes() for p in serveur.dossier.glob("*.csv")}
            self.assertNotIn("wiki_pages.csv", avant)
            self.assertNotIn(b";astuce", avant["ordres_travail.csv"].split(b"\r\n", 1)[0])

            # Demandeur : il ne génère pas les OT préventifs échus (RG5), qui changeraient ordres_travail.csv.
            preregler_profil(self.contexte, "demandeur", nom="Lucie Martin")
            self.autoriser_erreur(re.compile(r"status of 404.*/api/csv/wiki_(pages|journal)"))   # fichier absent = table vide
            self.page.goto(serveur.url + "/#/accueil")
            attendre_pret(self.page)

            # Une seule sauvegarde, « avant-format-v3 », qui garde l'état d'avant (format 2).
            sauvegardes = self.sauvegardes(serveur, "*_avant-format-v*")
            self.assertEqual(len(sauvegardes), 1, sauvegardes)
            self.assertRegex(sauvegardes[0], MOTIF_NOM_AVANT_FORMAT_COURANT)
            self.assertEqual(version_schema(self.octets(serveur, "sauvegardes", sauvegardes[0], "parametres.csv")), "2")
            self.assertEqual(version_schema(parametres.read_bytes()), FORMAT_COURANT)

            # Aucun autre fichier n'a changé à l'octet ; les nouvelles tables ne sont pas créées (vides).
            apres = {p.name: p.read_bytes() for p in serveur.dossier.glob("*.csv")}
            self.assertEqual(set(apres), set(avant))
            changes = sorted(nom for nom in avant if apres[nom] != avant[nom])
            self.assertEqual(changes, ["journal.csv", "parametres.csv"])
            self.assertEqual(self.page.evaluate("Donnees.lignes('wiki_pages').length"), 0)
            self.assertEqual(self.page.evaluate("Donnees.lignes('wiki_journal').length"), 0)
            # La colonne astuce absente : lue vide, simple information (écrite au prochain enregistrement).
            self.assertEqual(self.page.evaluate(
                "Donnees.lignes('ordres_travail').filter((ot) => ot.astuce !== '').length"), 0)
            self.assertEqual(self.page.evaluate(
                "Donnees.problemes().filter((p) => p.table === 'ordres_travail' && p.champ === 'astuce')"
                ".map((p) => p.gravite)"), ["info"])
            actions = actions_journal_version(self.octets(serveur, "journal.csv"))
            self.assertEqual(len(actions), 1, actions)
            self.assertIn("passage au format 3 du fichier ; sauvegarde %s faite juste avant" % sauvegardes[0], actions[0])
            # La base reste propre : aucun problème « erreur » ni « attention » nouveau.
            self.assertEqual(self.page.evaluate(
                "Donnees.problemes().filter((p) => p.gravite !== 'info' && p.table.startsWith('wiki_')).length"), 0)


# ---------------------------------------------------------------------------
# API brute du serveur (http.client) : motif de sauvegarde
# ---------------------------------------------------------------------------

def requete(serveur, methode, chemin, corps=b"", entetes=None):
    """(statut, objet JSON) d'une requête envoyée telle quelle au serveur de test."""
    connexion = http.client.HTTPConnection("127.0.0.1", serveur.port, timeout=15)
    try:
        envoyees = {"X-Prevo": "1", "Content-Length": str(len(corps))}
        envoyees.update(entetes or {})
        connexion.request(methode, chemin, body=corps, headers=envoyees)
        reponse = connexion.getresponse()
        return reponse.status, json.loads(reponse.read().decode("utf-8"))
    finally:
        connexion.close()


def demander_sauvegarde(serveur, corps):
    if not isinstance(corps, bytes):
        corps = json.dumps(corps).encode("utf-8")
    return requete(serveur, "POST", "/api/sauvegarde", corps, {"Content-Type": "application/json"})


def demander_restauration(serveur, nom, tables=None):
    demande = {"sauvegarde": nom}
    if tables is not None:
        demande["tables"] = tables
    return requete(serveur, "POST", "/api/restauration", json.dumps(demande).encode("utf-8"),
                   {"Content-Type": "application/json"})


# Noms de sauvegarde : (nom, valide). Un nom valide mais absent → 404 (serveur) / « introuvable »
# (dossier) ; un nom invalide → 400 / « Nom de sauvegarde invalide ». Mêmes réponses des deux côtés.
NOMS_A_CONTROLER = (
    ("1999-01-01", True),
    ("1999-01-01_120000", True),
    ("1999-01-01_120000_avant-restauration", True),
    ("1999-01-01_120000_avant-format-v2", True),
    ("1999-01-01_120000_avant-format-v12", True),
    ("1999-01-01_avant-format-v2", False),           # sans heure
    ("1999-01-01_120000_avant-format-v", False),
    ("1999-01-01_120000_avant-format-vx", False),
    ("1999-01-01_120000_avant-format-v2x", False),
    ("1999-01-01_120000_avant-format-v2/../..", False),
    ("1999-01-01_120000_avant-format-v２", False),  # chiffre « pleine largeur »
    ("1999-01-01_120000_inconnu", False),
    ("../x", False),
)


class TestApiMotif(unittest.TestCase):

    def test_motif_inconnu_ou_traversee_400_corps_vide_nom_manuel_et_motif_accepte(self):
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier / "sauvegardes"
            avant = sorted(p.name for p in dossier.iterdir())
            for corps in ({"motif": "inconnu"}, {"motif": "../x"}, {"motif": "avant-format-v4"},
                          {"motif": "avant-format-v2/../.."}, {"motif": 2}, {"motif": ["avant-format-v2"]},
                          ["avant-format-v2"], b"pas du json", b"\xff\xfe"):
                with self.subTest(corps=corps):
                    statut, reponse = demander_sauvegarde(serveur, corps)
                    self.assertEqual(statut, 400, reponse)
                    self.assertIn("erreur", reponse)
            self.assertEqual(sorted(p.name for p in dossier.iterdir()), avant)    # rien n'a été créé
            statut, reponse = demander_sauvegarde(serveur, {"motif": "inconnu"})
            self.assertIn("Motif de sauvegarde refusé", reponse["erreur"])

            # Corps vide : comme avant, sauvegarde manuelle « AAAA-MM-JJ_HHMMSS ».
            statut, reponse = requete(serveur, "POST", "/api/sauvegarde", b"")
            self.assertEqual(statut, 200, reponse)
            self.assertRegex(reponse["sauvegarde"], MOTIF_NOM_MANUEL)
            # Objet sans motif (ou motif null) : sauvegarde manuelle aussi.
            statut, reponse = demander_sauvegarde(serveur, {"motif": None})
            self.assertEqual(statut, 200, reponse)
            self.assertRegex(reponse["sauvegarde"], MOTIF_NOM_MANUEL)

            # Motifs de la liste fermée : « …_avant-format-v2 » (lot 2) et « …_avant-format-v3 » (lot 6),
            # listés et restaurables.
            statut, reponse = demander_sauvegarde(serveur, {"motif": "avant-format-v3"})
            self.assertEqual(statut, 200, reponse)
            self.assertRegex(reponse["sauvegarde"], MOTIF_NOM_AVANT_FORMAT_COURANT)
            statut, reponse = demander_sauvegarde(serveur, {"motif": "avant-format-v2"})
            self.assertEqual(statut, 200, reponse)
            nom = reponse["sauvegarde"]
            self.assertRegex(nom, MOTIF_NOM_AVANT_FORMAT_2)
            self.assertTrue((dossier / nom / "parametres.csv").is_file())
            statut, liste = requete(serveur, "GET", "/api/sauvegardes")
            self.assertIn(nom, [s["nom"] for s in liste["sauvegardes"]])
            statut, reponse = demander_restauration(serveur, nom, ["parametres"])
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(reponse["restaurees"], ["parametres"])

    def test_json_trop_imbrique_400_et_non_500(self):
        # Relecture de la vague 2 : « [[[[… » faisait lever RecursionError à json.loads → 500.
        imbrique = b"[" * 200000 + b"]" * 200000
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier / "sauvegardes"
            avant = sorted(p.name for p in dossier.iterdir())
            for chemin in ("/api/sauvegarde", "/api/restauration"):
                with self.subTest(chemin=chemin):
                    statut, reponse = requete(serveur, "POST", chemin, imbrique,
                                              {"Content-Type": "application/json"})
                    self.assertEqual(statut, 400, reponse)
                    self.assertEqual(reponse["erreur"], "Corps JSON invalide.")
            self.assertEqual(sorted(p.name for p in dossier.iterdir()), avant)    # rien n'a été créé
            self.assertNotIn("RecursionError", serveur.sortie_console())
            statut, _ = requete(serveur, "GET", "/api/ping")
            self.assertEqual(statut, 200)                                        # toujours en service

    def test_regles_de_noms_pour_la_restauration(self):
        with ServeurPrevo() as serveur:
            for nom, valide in NOMS_A_CONTROLER:
                with self.subTest(nom=nom):
                    statut, reponse = demander_restauration(serveur, nom)
                    self.assertEqual(statut, 404 if valide else 400, reponse)


# ---------------------------------------------------------------------------
# Mode dossier (dossier simulé dans l'OPFS du navigateur)
# ---------------------------------------------------------------------------

NOM_DOSSIER_SIMULE = "donnees-version-schema"
PAGE_DOSSIER = "/tests/fixtures/page-stockage-dossier.html"

# Outils ajoutés à la page de test : copie des fichiers de tests/fixtures/v1 dans le dossier simulé,
# lecture et liste de l'OPFS, ouverture de l'adaptateur et de Donnees.
AIDE_DOSSIER_JS = """
window.aideVersion = (() => {
  const nomDossier = %s;
  async function dossier(chemin) {
    let courant = await (await navigator.storage.getDirectory()).getDirectoryHandle(nomDossier, { create: true });
    for (const morceau of chemin.split('/').filter(Boolean)) { courant = await courant.getDirectoryHandle(morceau); }
    return courant;
  }
  async function lire(chemin) {
    const morceaux = chemin.split('/');
    try {
      const poignee = await (await dossier(morceaux.slice(0, -1).join('/'))).getFileHandle(morceaux[morceaux.length - 1]);
      return Array.from(new Uint8Array(await (await poignee.getFile()).arrayBuffer()));
    } catch (erreur) {
      if (erreur.name === 'NotFoundError') { return null; }
      throw erreur;
    }
  }
  async function lister(chemin) {
    const noms = [];
    try {
      for await (const entree of (await dossier(chemin)).values()) { noms.push(entree.name); }
    } catch (erreur) {
      if (erreur.name === 'NotFoundError') { return []; }
      throw erreur;
    }
    return noms.sort();
  }
  async function installerFichiersV1(tables) {
    const racine = await dossier('');
    for (const table of tables) {
      const reponse = await fetch('/tests/fixtures/v1/' + table + '.csv', { cache: 'no-store' });
      const octets = new Uint8Array(await reponse.arrayBuffer());
      const flux = await (await racine.getFileHandle(table + '.csv', { create: true })).createWritable();
      await flux.write(octets);
      await flux.close();
    }
  }
  async function ouvrir() {
    window.dos = await StockageDossier.creer(await window.showDirectoryPicker(), { poste: 'Poste test' });
    Donnees.initialiser(window.dos, { poste: 'Poste test', profil: 'Responsable' });
    await Donnees.chargerTout();
  }
  async function appeler(methode, args) {
    try {
      return { ok: true, valeur: await window.dos[methode](...(args || [])) };
    } catch (erreur) {
      return { ok: false, nom: erreur.name, message: erreur.message };
    }
  }
  return { lire, lister, installerFichiersV1, ouvrir, appeler };
})();
""" % json.dumps(NOM_DOSSIER_SIMULE)


class TestDossier(CasNavigateur):

    def ouvrir_dossier_v1(self, url_base):
        installer_dossier_simule(self.contexte, NOM_DOSSIER_SIMULE)
        self.page.goto(url_base + PAGE_DOSSIER)
        self.page.add_script_tag(content=AIDE_DOSSIER_JS)
        self.page.evaluate("tables => aideVersion.installerFichiersV1(tables)", list(TABLES_V1))
        self.page.evaluate("aideVersion.ouvrir()")
        self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "1")

    def lire(self, chemin):
        octets = self.page.evaluate("chemin => aideVersion.lire(chemin)", chemin)
        return None if octets is None else bytes(octets)

    def lister(self, chemin):
        return self.page.evaluate("chemin => aideVersion.lister(chemin)", chemin)

    def appeler(self, methode, *args):
        return self.page.evaluate("([m, a]) => aideVersion.appeler(m, a)", [methode, list(args)])

    def test_dossier_passage_au_format_courant_puis_restauration(self):
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier_v1(statique.url)
            resultat = self.page.evaluate(APPELER_MISE_A_JOUR)
            self.assertTrue(resultat["ok"], resultat)
            self.assertTrue(resultat["valeur"]["misAJour"])
            nom = resultat["valeur"]["sauvegarde"]
            self.assertRegex(nom, MOTIF_NOM_AVANT_FORMAT_COURANT)

            # Sauvegarde complète (sans marqueur « .en-cours »), avec l'état d'avant.
            self.assertEqual(self.lister("sauvegardes/" + nom), sorted(t + ".csv" for t in TABLES_V1))
            self.assertEqual(self.lire("sauvegardes/%s/parametres.csv" % nom), PARAMETRES_V1.read_bytes())
            self.assertEqual(version_schema(self.lire("parametres.csv")), FORMAT_COURANT)
            actions = actions_journal_version(self.lire("journal.csv"))
            self.assertEqual(len(actions), 1, actions)
            self.assertIn("passage au format 3 du fichier ; sauvegarde %s faite juste avant" % nom, actions[0])

            # Second appel : rien.
            sauvegardes_avant = self.lister("sauvegardes")
            parametres_avant = self.lire("parametres.csv")
            self.assertEqual(self.page.evaluate(APPELER_MISE_A_JOUR),
                             {"ok": True, "valeur": {"misAJour": False, "sauvegarde": None}})
            self.assertEqual(self.lister("sauvegardes"), sauvegardes_avant)
            self.assertEqual(self.lire("parametres.csv"), parametres_avant)

            # Le nom est accepté par StockageDossier : listé, puis restauré (toutes les tables).
            liste = self.appeler("listerSauvegardes")
            self.assertTrue(liste["ok"], liste)
            self.assertIn(nom, [s["nom"] for s in liste["valeur"]])
            restauration = self.appeler("restaurer", nom)
            self.assertTrue(restauration["ok"], restauration)
            self.assertEqual(sorted(restauration["valeur"]["restaurees"]), sorted(TABLES_V1))
            self.assertEqual(self.lire("parametres.csv"), PARAMETRES_V1.read_bytes())

    def test_dossier_motif_refuse_et_regles_de_noms_identiques_au_serveur(self):
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier_v1(statique.url)
            avant = self.lister("sauvegardes")
            for motif in ("inconnu", "../x", "avant-format-v4", "avant-format-v2/../..", 2):
                with self.subTest(motif=motif):
                    resultat = self.appeler("sauvegarder", motif)
                    self.assertEqual((resultat["ok"], resultat["nom"]), (False, "ErreurStockage"), resultat)
                    self.assertIn("Motif de sauvegarde refusé", resultat["message"])
            self.assertEqual(self.lister("sauvegardes"), avant)          # rien n'a été créé

            # Sans motif : sauvegarde manuelle, comme avant ; avec un motif de la liste : « …_avant-format-vN ».
            manuelle = self.appeler("sauvegarder")
            self.assertRegex(manuelle["valeur"], MOTIF_NOM_MANUEL)
            avec_motif = self.appeler("sauvegarder", "avant-format-v2")
            self.assertRegex(avec_motif["valeur"], MOTIF_NOM_AVANT_FORMAT_2)
            avec_motif = self.appeler("sauvegarder", "avant-format-v3")
            self.assertRegex(avec_motif["valeur"], MOTIF_NOM_AVANT_FORMAT_COURANT)

            # Mêmes règles de noms que le serveur (TestApiMotif.test_regles_de_noms_pour_la_restauration).
            for nom, valide in NOMS_A_CONTROLER:
                with self.subTest(nom=nom):
                    resultat = self.appeler("restaurer", nom)
                    self.assertFalse(resultat["ok"])
                    attendu = "Sauvegarde introuvable" if valide else "Nom de sauvegarde invalide"
                    self.assertIn(attendu, resultat["message"])


# ---------------------------------------------------------------------------
# Démo
# ---------------------------------------------------------------------------

class TestDemo(CasNavigateur):

    def test_demo_aucune_sauvegarde_aucune_erreur(self):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.page.evaluate("""() => { window.appelsSauvegarde = 0;
            const original = App.adaptateur.sauvegarder;
            App.adaptateur.sauvegarder = function () { window.appelsSauvegarde += 1; return original.apply(this, arguments); }; }""")
        # Le jeu de démo est déjà au format courant : rien à faire.
        self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), FORMAT_COURANT)
        self.assertEqual(self.page.evaluate(APPELER_MISE_A_JOUR),
                         {"ok": True, "valeur": {"misAJour": False, "sauvegarde": None}})
        self.assertEqual(self.page.evaluate("window.appelsSauvegarde"), 0)

    def test_demo_fichiers_au_format_1_passage_en_memoire_seulement(self):
        charger_scripts(self.page, ["js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js",
                                    "js/stockage-demo.js"])
        resultat = self.page.evaluate("""async (texteParametres) => {
            const demo = StockageDemo.creer({ parametres: texteParametres });
            let appelsSauvegarde = 0;
            const original = demo.sauvegarder;
            demo.sauvegarder = function () { appelsSauvegarde += 1; return original.apply(this, arguments); };
            Donnees.initialiser(demo, { poste: 'Poste test', profil: 'Responsable' });
            await Donnees.chargerTout();
            const premier = await Donnees.mettreAJourVersionSchema();
            const second = await Donnees.mettreAJourVersionSchema();
            return {
              premier, second, appelsSauvegarde,
              version: Donnees.parametre('version_schema'),
              fichier: Donnees.csv.decoder((await demo.charger('parametres')).octets).texte,
              journal: Donnees.lignes('journal').map((ligne) => ligne.action),
            };
        }""", PARAMETRES_V1.read_bytes().decode("utf-8-sig"))
        self.assertEqual(resultat["premier"], {"misAJour": True, "sauvegarde": None})
        self.assertEqual(resultat["second"], {"misAJour": False, "sauvegarde": None})
        self.assertEqual(resultat["appelsSauvegarde"], 0)
        self.assertEqual(resultat["version"], FORMAT_COURANT)
        self.assertIn("version_schema;'3", resultat["fichier"])
        self.assertEqual(len(resultat["journal"]), 1, resultat["journal"])
        self.assertIn("passage au format 3 du fichier ; sans sauvegarde (démo)", resultat["journal"][0])


if __name__ == "__main__":
    unittest.main()
