"""Tests des contrôles réglementaires : écrans, écritures, fiche équipement, OT pré-rempli
(ARCHITECTURE.md §15.7 et §15.2 ; brief RG9, E10 ; tâche T47).

Serveur Prévo sur une copie du jeu de démo (ServeurPrevo), profil préréglé ; les CSV sont relus sur
le disque. Aucun identifiant du jeu de démo n'est écrit en dur : les contrôles viennent des rôles de
scenarios_demo() (controle_en_retard, controle_a_planifier, controle_observations, controle_a_jour),
les autres lignes sont cherchées par leurs propriétés. Les statuts attendus sont recalculés en Python
à la date du jour de l'application (Donnees.aujourdhui()).

Familles (le nom du test le dit) :
    statuts      : rôles de la démo affichés avec leur statut ; statut secondaire en second badge ;
    filtre       : #/controles?filtre=30j = calcul Python (même définition que l'accueil) ; ?statut= ;
    creation     : création et modification par le formulaire ; refus (périodicité ≤ 0, équipement
                   absent ou introuvable, prochaine date avant la dernière) sans rien écrire ;
    realisation  : contrôle réalisé avec rapport joint (document écrit, dates recalculées, fin de
                   mois) ; date future refusée sans document écrit ;
    observations : levée des observations (statut, journal) ; refus sans observation à lever ;
    ot           : « Créer un OT » ouvre un OT réglementaire pré-rempli (type, titre, équipement),
                   créé puis listé sur la fiche ; aucun OT généré par le module sans clic ;
    parc         : carte « Contrôles réglementaires » de la fiche équipement (selon le profil) ;
    profils      : technicien en lecture (aucun bouton d'écriture), demandeur renvoyé à l'accueil ;
    demo         : parcours en file:// (statuts des rôles, contrôle réalisé avec une photo) ;
    telephone    : 375 px sans défilement horizontal, zones tactiles de 48 px.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_controles.py" -v
"""
import calendar
import csv
import datetime
import io
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo, url_fichier

SCENARIOS = scenarios_demo()
EN_RETARD = SCENARIOS["controle_en_retard"]
A_PLANIFIER = SCENARIOS["controle_a_planifier"]
OBSERVATIONS = SCENARIOS["controle_observations"]
A_JOUR = SCENARIOS["controle_a_jour"]
TECHNICIEN = SCENARIOS["technicien_br_valide"]
ROLES = ((EN_RETARD, "en retard"), (A_PLANIFIER, "à planifier"), (OBSERVATIONS, "observations à lever"),
         (A_JOUR, "à jour"))

# Appel d'une écriture du module dans la page : 'accepté:<valeur JSON>' ou 'refus:<message>'.
APPEL_JS = """async ([fonction, arguments_]) => {
  try { return 'accepté:' + JSON.stringify(await Controles[fonction](...arguments_)); }
  catch (erreur) { return (erreur instanceof Donnees.ErreurValidation ? 'refus:' : 'erreur:') + erreur.message; }
}"""
PDF = {"name": "rapport-vgp.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4\n% rapport de test Prévo\n"}
# Image PNG 1 × 1 (rouge), lisible par le navigateur.
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
                    "53de0000000c4944415408d763f8cfc000000301010018dd8db00000000049454e44ae426082")


# ---------------------------------------------------------------------------
# Lecture des CSV et calculs de référence en Python
# ---------------------------------------------------------------------------

def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def jour(valeur):
    texte = brut(valeur)[:10]
    return datetime.date.fromisoformat(texte) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texte) else None


def ajouter_mois(date, mois):
    total = date.year * 12 + date.month - 1 + mois
    annee, mois0 = divmod(total, 12)
    return datetime.date(annee, mois0 + 1, min(date.day, calendar.monthrange(annee, mois0 + 1)[1]))


def periodicite(controle):
    try:
        valeur = int(brut(controle["periodicite_mois"]))
    except ValueError:
        return None
    return valeur if valeur > 0 else None


def prochaine_date(controle):
    prochaine = jour(controle["prochaine_date"])
    if prochaine:
        return prochaine
    derniere, mois = jour(controle["derniere_date"]), periodicite(controle)
    return ajouter_mois(derniere, mois) if derniere and mois else None


def etat_python(controle, aujourdhui):
    """(statut, secondaires) — RG9 : le premier vrai de en retard, observations, à planifier, à jour."""
    prochaine = prochaine_date(controle)
    vrais = []
    if prochaine is not None and prochaine < aujourdhui:
        vrais.append("en retard")
    if brut(controle["observations"]) and brut(controle["observations_levees"]) != "1":
        vrais.append("observations à lever")
    if prochaine is None or aujourdhui <= prochaine <= aujourdhui + datetime.timedelta(days=30):
        vrais.append("à planifier")
    if not vrais:
        vrais.append("à jour")
    return vrais[0], vrais[1:]


def sous_30_jours(dossier, aujourdhui):
    """Identifiants des contrôles « sous 30 jours » (même définition que Controles.sous30Jours)."""
    equipements = {e["id"]: e for e in lire_csv(dossier, "equipements.csv")}
    resultat = []
    for controle in lire_csv(dossier, "controles_reglementaires.csv"):
        equipement = equipements.get(controle["equipement_id"])
        if not equipement or brut(equipement["actif"]) == "0" or equipement["statut"] == "rebut":
            continue
        prochaine = prochaine_date(controle)
        if prochaine is None or prochaine <= aujourdhui + datetime.timedelta(days=30):
            resultat.append(controle["id"])
    return resultat


def date_reference():
    """Date de référence du générateur du jeu de démo (js/demo-donnees.js)."""
    texte = (Path(__file__).resolve().parent.parent / "js" / "demo-donnees.js").read_text(encoding="utf-8")
    return datetime.date.fromisoformat(re.search(r"""dateReference:\s*["'](\d{4}-\d{2}-\d{2})["']""", texte).group(1))


def suivis(dossier):
    """Contrôles d'équipements suivis (actifs, hors rebut) : ceux de la liste par défaut."""
    equipements = {e["id"]: e for e in lire_csv(dossier, "equipements.csv")}
    return [c for c in lire_csv(dossier, "controles_reglementaires.csv")
            if c["equipement_id"] in equipements and brut(equipements[c["equipement_id"]]["actif"]) != "0"
            and equipements[c["equipement_id"]]["statut"] != "rebut"]


def controle(dossier, controle_id):
    return next(c for c in lire_csv(dossier, "controles_reglementaires.csv") if c["id"] == controle_id)


def journal_de(dossier, controle_id):
    return [e for e in lire_csv(dossier, "journal.csv")
            if e["table"] == "controles_reglementaires" and e["id_ligne"] == controle_id]


def date_fin_de_mois(derniere, mois, aujourdhui):
    """Date passée D (le 31 d'un mois, ≥ derniere) telle que D + mois tombe à une fin de mois plus courte."""
    annee, numero = aujourdhui.year, aujourdhui.month
    for _ in range(36):
        if calendar.monthrange(annee, numero)[1] == 31:
            candidate = datetime.date(annee, numero, 31)
            if candidate <= aujourdhui and (derniere is None or candidate >= derniere) \
                    and ajouter_mois(candidate, mois).day < 31:
                return candidate
        numero -= 1
        if numero == 0:
            annee, numero = annee - 1, 12
    raise AssertionError("aucune date de fin de mois utilisable")


# ---------------------------------------------------------------------------
# Outils communs
# ---------------------------------------------------------------------------

class CasControles(CasNavigateur):

    def ouvrir(self, serveur, route, profil="responsable", technicien_id="", largeur=1280, nom=""):
        self.page.set_viewport_size({"width": largeur, "height": 900})
        preregler_profil(self.contexte, profil, nom=nom, technicien_id=technicien_id)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        # Les écritures du démarrage (OT préventifs échus) sont finies avant le test.
        self.page.wait_for_load_state("networkidle")

    def aller(self, route):
        self.page.evaluate("(route) => { location.hash = route; }", route)

    def appeler(self, fonction, *arguments):
        return self.page.evaluate(APPEL_JS, [fonction, list(arguments)])

    def aujourdhui(self):
        return datetime.date.fromisoformat(self.page.evaluate("Donnees.aujourdhui()"))

    def attendre_toast(self, morceau):
        self.page.wait_for_function(
            "(texte) => document.getElementById('toast').textContent.includes(texte)", arg=morceau)

    def attendre_liste(self):
        self.page.wait_for_selector(".controles-liste a.controles-lien")

    def ids_affiches(self):
        return self.page.eval_on_selector_all(
            ".controles-liste a.controles-lien",
            "liens => Array.from(new Set(liens.map(a => decodeURIComponent(a.getAttribute('href').split('/').pop()))))")

    def badges(self, controle_id, racine="#contenu"):
        return self.page.eval_on_selector_all(
            "%s .controles-statuts[data-controle='%s'] .badge" % (racine, controle_id),
            "badges => badges.map(b => b.textContent.trim())")

    def attendre_fiche(self, controle_id):
        self.page.wait_for_selector(".controles-fiche .controles-statuts[data-controle='%s']" % controle_id)

    def valider_fenetre(self):
        self.page.click("dialog .fenetre-actions .btn-primaire")


# ---------------------------------------------------------------------------
# Statuts, filtres
# ---------------------------------------------------------------------------

class TestListe(CasControles):

    def test_statuts_des_roles_de_la_demo_et_badge_secondaire(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/controles")
            self.attendre_liste()
            aujourdhui = self.aujourdhui()
            self.assertEqual(self.page.inner_text("#contenu h1"), "Contrôles réglementaires")
            for controle_id, role in ROLES:
                with self.subTest(controle=controle_id):
                    statut, secondaires = etat_python(controle(serveur.dossier, controle_id), aujourdhui)
                    self.assertEqual(self.badges(controle_id), [statut] + secondaires)
                    if 0 <= (aujourdhui - date_reference()).days < 7:
                        self.assertEqual(statut, role)       # rôle du générateur, vrai à sa date de référence
            # Menu « Contrôles » allumé
            self.assertEqual(self.page.evaluate("document.querySelector('#menu a.actif').dataset.ecran"), "controles")

            # Un contrôle en retard ET avec des observations : le second statut s'affiche en second badge
            veille = (aujourdhui - datetime.timedelta(days=1)).isoformat()
            self.assertTrue(self.appeler("modifierControle", OBSERVATIONS, {"prochaine_date": veille}).startswith("accepté:"))
            self.page.evaluate("App.reafficher()")
            self.page.wait_for_function("(id) => document.querySelectorAll(`.controles-statuts[data-controle='${id}'] .badge`).length === 2",
                                        arg=OBSERVATIONS)
            self.assertEqual(self.badges(OBSERVATIONS), ["en retard", "observations à lever"])
            self.aller("#/controles/" + OBSERVATIONS)
            self.attendre_fiche(OBSERVATIONS)
            self.assertEqual(self.badges(OBSERVATIONS, ".controles-fiche"), ["en retard", "observations à lever"])
            self.assertIn("en retard de 1 jour", self.page.inner_text(".controles-fiche .controles-raison"))

    def test_filtre_30j_egal_au_calcul_python_et_filtre_par_statut(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/controles?filtre=30j")
            self.attendre_liste()
            aujourdhui = self.aujourdhui()
            attendus = sous_30_jours(serveur.dossier, aujourdhui)
            self.assertTrue(attendus, "la démo doit avoir des contrôles sous 30 jours")
            self.assertEqual(sorted(self.ids_affiches()), sorted(attendus))
            self.assertEqual(self.page.evaluate("Controles.sous30Jours().length"), len(attendus))
            self.assertIn("30 jours", self.page.inner_text("#contenu"))
            # Tous les contrôles, puis un statut donné par l'adresse
            self.aller("#/controles")
            self.page.wait_for_function("(n) => document.querySelectorAll('.controles-liste a.controles-lien').length > 0", arg=0)
            tous = [c["id"] for c in suivis(serveur.dossier)]
            self.page.wait_for_function("(n) => new Set(Array.from(document.querySelectorAll('.controles-liste a.controles-lien')).map(a => a.getAttribute('href'))).size === n",
                                        arg=len(tous))
            self.assertEqual(sorted(self.ids_affiches()), sorted(tous))
            self.aller("#/controles?statut=" + "en%20retard")
            self.page.wait_for_function("(n) => new Set(Array.from(document.querySelectorAll('.controles-liste a.controles-lien')).map(a => a.getAttribute('href'))).size < n",
                                        arg=len(tous))
            en_retard = [c["id"] for c in suivis(serveur.dossier)
                         if "en retard" in [etat_python(c, aujourdhui)[0]] + etat_python(c, aujourdhui)[1]]
            self.assertEqual(sorted(self.ids_affiches()), sorted(en_retard))
            # ?equipement= : seulement les contrôles de cet équipement
            equipement = controle(serveur.dossier, A_JOUR)["equipement_id"]
            self.aller("#/controles?equipement=" + equipement)
            self.page.wait_for_function("(id) => document.querySelector('.controles-liste') && "
                                        "Array.from(document.querySelectorAll('.controles-liste a.controles-lien')).every(a => a.getAttribute('href').endsWith(id))",
                                        arg=A_JOUR)
            attendus = [c["id"] for c in lire_csv(serveur.dossier, "controles_reglementaires.csv") if c["equipement_id"] == equipement]
            self.assertEqual(sorted(self.ids_affiches()), sorted(attendus))


# ---------------------------------------------------------------------------
# Création et modification
# ---------------------------------------------------------------------------

class TestCreation(CasControles):

    def test_creation_et_modification_par_le_formulaire_avec_refus(self):
        page = self.page
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "controles_reglementaires.csv"
            avec_controle = {c["equipement_id"] for c in lire_csv(serveur.dossier, "controles_reglementaires.csv")}
            equipement = next(e for e in lire_csv(serveur.dossier, "equipements.csv")
                              if brut(e["actif"]) != "0" and e["statut"] != "rebut" and e["id"] not in avec_controle)
            self.ouvrir(serveur, "#/controles/nouveau?equipement=" + equipement["id"])
            page.wait_for_selector("#form-controle")
            self.assertEqual(page.input_value("#form-controle [name=equipement_id]"), equipement["id"])
            aujourdhui = self.aujourdhui()

            # Refus : périodicité 0, rien d'écrit
            avant = chemin.read_bytes()
            page.fill("#form-controle [name=nature]", "Contrôle des appareils à pression (test)")
            page.fill("#form-controle [name=texte_reference]", "Arrêté du 20 novembre 2017")
            page.fill("#form-controle [name=periodicite_mois]", "0")
            page.fill("#form-controle [name=organisme]", "Organisme de test")
            derniere = (aujourdhui - datetime.timedelta(days=40)).isoformat()
            page.fill("#form-controle [name=derniere_date]", derniere)
            page.click("#form-controle button[type=submit]")
            page.wait_for_selector("#form-controle .champ[data-champ='periodicite_mois'] .erreur-champ:not([hidden])")
            self.assertIn("supérieur à 0", page.inner_text("#form-controle .champ[data-champ='periodicite_mois'] .erreur-champ"))
            self.assertEqual(chemin.read_bytes(), avant)

            # Valeurs correctes : création, fiche affichée
            page.fill("#form-controle [name=periodicite_mois]", "12")
            page.click("#form-controle button[type=submit]")
            self.attendre_toast("Contrôle créé")
            page.wait_for_function("location.hash.startsWith('#/controles/CTR-')")
            nouveau = page.evaluate("decodeURIComponent(location.hash.split('/').pop())")
            ligne = controle(serveur.dossier, nouveau)
            self.assertEqual((ligne["equipement_id"], ligne["nature"], brut(ligne["periodicite_mois"]), ligne["organisme"], ligne["derniere_date"]),
                             (equipement["id"], "Contrôle des appareils à pression (test)", "12", "Organisme de test", derniere))
            self.assertEqual(ligne["observations"], "")
            self.attendre_fiche(nouveau)
            statut, _ = etat_python(ligne, aujourdhui)
            self.assertEqual(self.badges(nouveau, ".controles-fiche")[0], statut)
            self.assertTrue(any(e["action"].startswith("création") for e in journal_de(serveur.dossier, nouveau)))

            # Modification par le formulaire de la fiche
            page.fill("#form-controle [name=organisme]", "Autre organisme (test)")
            page.click("#form-controle button[type=submit]")
            self.attendre_toast("Contrôle enregistré")
            self.assertEqual(controle(serveur.dossier, nouveau)["organisme"], "Autre organisme (test)")

            # Refus par l'API, sur les lignes fraîches : rien d'écrit
            avant = chemin.read_bytes()
            base = {"equipement_id": equipement["id"], "nature": "Essai", "periodicite_mois": "12"}
            for valeurs, attendu in (
                    (dict(base, equipement_id=""), "équipement"),
                    (dict(base, equipement_id="EQ-9999"), "introuvable"),
                    (dict(base, periodicite_mois="-3"), "supérieur à 0"),
                    (dict(base, periodicite_mois="2.5"), "supérieur à 0"),
                    (dict(base, nature=""), "nature"),
                    (dict(base, derniere_date=(aujourdhui + datetime.timedelta(days=3)).isoformat()), "futur"),
                    (dict(base, derniere_date="2026-05-10", prochaine_date="2026-05-01"), "suivre")):
                with self.subTest(valeurs=valeurs):
                    resultat = self.appeler("creerControle", valeurs)
                    self.assertTrue(resultat.startswith("refus:") and attendu in resultat, resultat)
            resultat = self.appeler("modifierControle", nouveau, {"periodicite_mois": "0"})
            self.assertTrue(resultat.startswith("refus:") and "supérieur à 0" in resultat, resultat)
            resultat = self.appeler("modifierControle", nouveau, {"equipement_id": "EQ-9999"})
            self.assertTrue(resultat.startswith("refus:") and "introuvable" in resultat, resultat)
            self.assertEqual(chemin.read_bytes(), avant)


# ---------------------------------------------------------------------------
# Contrôle réalisé, observations
# ---------------------------------------------------------------------------

class TestRealisation(CasControles):

    def test_controle_realise_avec_rapport_dates_recalculees_fin_de_mois_et_date_future_refusee(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/controles/" + EN_RETARD)
            self.attendre_fiche(EN_RETARD)
            aujourdhui = self.aujourdhui()
            ligne = controle(serveur.dossier, EN_RETARD)
            mois = periodicite(ligne)
            date = date_fin_de_mois(jour(ligne["derniere_date"]), mois, aujourdhui)
            attendue = ajouter_mois(date, mois)
            self.assertLess(attendue.day, 31)                       # fin de mois ramenée (ex. 31/08 + 6 → 28/02)
            documents = serveur.dossier / "documents"
            avant_documents = sorted(p.name for p in documents.iterdir()) if documents.is_dir() else []
            chemin = serveur.dossier / "controles_reglementaires.csv"

            # Date future : refus dans la fenêtre, ni document ni ligne écrits
            page.click("#controle-realise")
            page.wait_for_selector("dialog [name=date]")
            self.assertEqual(page.input_value("dialog [name=date]"), aujourdhui.isoformat())
            avant = chemin.read_bytes()
            page.fill("dialog [name=date]", (aujourdhui + datetime.timedelta(days=1)).isoformat())
            page.set_input_files("dialog input[type=file]", files=[PDF])
            self.valider_fenetre()
            page.wait_for_selector("dialog .erreur-champ:not([hidden])")
            self.assertIn("futur", page.inner_text("dialog"))
            self.assertEqual(chemin.read_bytes(), avant)
            apres_documents = sorted(p.name for p in documents.iterdir()) if documents.is_dir() else []
            self.assertEqual(apres_documents, avant_documents)

            # Date passée au 31 du mois, rapport PDF joint
            page.fill("dialog [name=date]", date.isoformat())
            page.fill("dialog [name=organisme]", "Organisme du test")
            self.valider_fenetre()
            self.attendre_toast("Contrôle réalisé enregistré")
            page.wait_for_selector("dialog", state="detached")
            ligne = controle(serveur.dossier, EN_RETARD)
            self.assertEqual(ligne["derniere_date"], date.isoformat())
            self.assertEqual(ligne["prochaine_date"], attendue.isoformat())
            self.assertEqual(ligne["organisme"], "Organisme du test")
            self.assertEqual((ligne["observations"], ligne["observations_levees"]), ("", "1"))
            self.assertRegex(ligne["rapport"], r"^controle-%s-%s(-\d+)?\.pdf$" % (EN_RETARD, date.isoformat()))
            self.assertEqual((documents / ligne["rapport"]).read_bytes(), PDF["buffer"])
            actions = [e["action"] for e in journal_de(serveur.dossier, EN_RETARD)]
            self.assertTrue(any("contrôle réalisé le %s" % date.strftime("%d/%m/%Y") in a for a in actions), actions)
            # L'écran suit : statut recalculé, rapport en lien, historique
            statut, secondaires = etat_python(ligne, aujourdhui)
            page.wait_for_function("([id, statut]) => { const b = document.querySelector(`.controles-fiche .controles-statuts[data-controle='${id}'] .badge`); return b && b.textContent.trim() === statut; }",
                                   arg=[EN_RETARD, statut])
            self.assertTrue(page.get_attribute("#controle-rapport", "href").endswith("/api/documents/" + ligne["rapport"]))
            self.assertIn("contrôle réalisé le", page.inner_text(".controles-historique"))
            # L'API refuse aussi une date future et une date antérieure au dernier contrôle
            for date_refusee, attendu in (((aujourdhui + datetime.timedelta(days=2)).isoformat(), "futur"),
                                         ((date - datetime.timedelta(days=1)).isoformat(), "antérieure")):
                resultat = self.appeler("enregistrerRealisation", EN_RETARD, {"date": date_refusee})
                self.assertTrue(resultat.startswith("refus:") and attendu in resultat, resultat)

    def test_observations_levees_statut_et_journal(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/controles/" + OBSERVATIONS)
            self.attendre_fiche(OBSERVATIONS)
            aujourdhui = self.aujourdhui()
            self.assertIn("observations à lever", self.badges(OBSERVATIONS, ".controles-fiche"))
            # Refus : rien à lever sur un contrôle à jour ; commentaire obligatoire
            resultat = self.appeler("leverObservations", A_JOUR, {"date": aujourdhui.isoformat(), "commentaire": "rien"})
            self.assertTrue(resultat.startswith("refus:") and "observation" in resultat, resultat)
            resultat = self.appeler("leverObservations", OBSERVATIONS, {"date": aujourdhui.isoformat(), "commentaire": ""})
            self.assertTrue(resultat.startswith("refus:"), resultat)
            self.assertEqual(controle(serveur.dossier, OBSERVATIONS)["observations_levees"], "0")

            page.click("#controle-lever")
            page.wait_for_selector("dialog [name=commentaire]")
            page.fill("dialog [name=commentaire]", "Purgeur automatique remplacé")
            self.valider_fenetre()
            self.attendre_toast("Observations levées")
            ligne = controle(serveur.dossier, OBSERVATIONS)
            self.assertEqual(ligne["observations_levees"], "1")
            self.assertTrue(ligne["observations"])                   # le texte des observations est gardé
            actions = [e["action"] for e in journal_de(serveur.dossier, OBSERVATIONS)]
            self.assertTrue(any("observations levées le %s : Purgeur automatique remplacé" % aujourdhui.strftime("%d/%m/%Y") in a
                                for a in actions), actions)
            statut, secondaires = etat_python(ligne, aujourdhui)
            self.assertNotEqual(statut, "observations à lever")
            page.wait_for_function("(id) => !document.querySelector('#controle-lever') && document.querySelector(`.controles-fiche .controles-statuts[data-controle='${id}']`)",
                                   arg=OBSERVATIONS)
            self.assertEqual(self.badges(OBSERVATIONS, ".controles-fiche"), [statut] + secondaires)
            self.assertIn("observations levées", page.inner_text(".controles-historique"))


# ---------------------------------------------------------------------------
# OT pré-rempli ; aucun OT généré par le module
# ---------------------------------------------------------------------------

class TestOrdres(CasControles):

    def test_creer_un_ot_reglementaire_pre_rempli_puis_cree_et_liste(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/controles/" + EN_RETARD)
            self.attendre_fiche(EN_RETARD)
            ligne = controle(serveur.dossier, EN_RETARD)
            ordres_avant = len(lire_csv(serveur.dossier, "ordres_travail.csv"))
            page.click("#controle-creer-ot")
            page.wait_for_selector("#form-nouvel-ot")
            self.assertTrue(page.evaluate("location.hash.startsWith('#/ot/nouveau?')"))
            self.assertEqual(page.input_value("#form-nouvel-ot [name=type]"), "réglementaire")
            titre = page.input_value("#form-nouvel-ot [name=titre]")
            self.assertIn(ligne["nature"], titre)
            self.assertEqual(page.input_value("#form-nouvel-ot [name=equipement_id]"), ligne["equipement_id"])
            self.assertEqual(len(lire_csv(serveur.dossier, "ordres_travail.csv")), ordres_avant)   # rien sans clic
            page.fill("#form-nouvel-ot [name=titre]", titre + " (organisme prévenu)")      # modifiable
            page.click("#form-nouvel-ot button[type=submit]")
            page.wait_for_selector(".ot-fiche .ot-numero")
            ot_id = page.inner_text(".ot-fiche .ot-numero")
            ot = next(o for o in lire_csv(serveur.dossier, "ordres_travail.csv") if o["id"] == ot_id)
            self.assertEqual((ot["type"], ot["equipement_id"], ot["titre"], ot["origine"]),
                             ("réglementaire", ligne["equipement_id"], titre + " (organisme prévenu)", "manuel"))
            self.assertEqual(len(lire_csv(serveur.dossier, "ordres_travail.csv")), ordres_avant + 1)
            # L'OT apparaît dans la carte « OT réglementaires » de la fiche du contrôle
            self.aller("#/controles/" + EN_RETARD)
            self.attendre_fiche(EN_RETARD)
            self.assertEqual(page.locator(".controles-ot a[href='#/ot/%s']" % ot_id).count(), 1)
            # Un type inconnu dans l'adresse est ignoré ; un titre seul pré-remplit
            self.aller("#/ot/nouveau?type=inconnu&titre=Essai%20de%20titre")
            page.wait_for_function("document.querySelector('#form-nouvel-ot [name=titre]') && document.querySelector('#form-nouvel-ot [name=titre]').value === 'Essai de titre'")
            self.assertEqual(page.input_value("#form-nouvel-ot [name=type]"), "correctif différé")

    def test_aucun_ot_genere_par_le_module_sans_clic(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/accueil")
            ordres = (serveur.dossier / "ordres_travail.csv").read_bytes()
            nombre = page.evaluate("Donnees.lignes('ordres_travail').length")
            routes = ["#/controles", "#/controles?filtre=30j"]
            routes += ["#/controles/" + c["id"] for c in lire_csv(serveur.dossier, "controles_reglementaires.csv")]
            routes += ["#/equipement/" + controle(serveur.dossier, EN_RETARD)["equipement_id"]]
            for route in routes:
                self.aller(route)
                page.wait_for_selector(".controles-fiche, .controles-liste, .parc-controles")
                page.wait_for_load_state("networkidle")
            self.assertEqual((serveur.dossier / "ordres_travail.csv").read_bytes(), ordres)
            self.assertEqual(page.evaluate("Donnees.lignes('ordres_travail').length"), nombre)


# ---------------------------------------------------------------------------
# Fiche équipement, profils
# ---------------------------------------------------------------------------

class TestProfils(CasControles):

    def test_parc_carte_controles_de_la_fiche_equipement_selon_le_profil(self):
        page = self.page
        with ServeurPrevo() as serveur:
            equipement = controle(serveur.dossier, EN_RETARD)["equipement_id"]
            controles = [c["id"] for c in lire_csv(serveur.dossier, "controles_reglementaires.csv") if c["equipement_id"] == equipement]
            self.ouvrir(serveur, "#/equipement/" + equipement)
            page.wait_for_selector(".parc-controles")
            liens = page.eval_on_selector_all(".parc-controles li a[href^='#/controles/']", "l => l.map(a => a.getAttribute('href'))")
            self.assertEqual(sorted(liens), sorted("#/controles/" + c for c in controles))
            statut, _ = etat_python(controle(serveur.dossier, EN_RETARD), self.aujourdhui())
            self.assertEqual(self.badges(EN_RETARD, ".parc-controles")[0], statut)
            page.click("#parc-ajouter-controle")
            page.wait_for_selector("#form-controle")
            self.assertEqual(page.input_value("#form-controle [name=equipement_id]"), equipement)

            # Technicien : carte en lecture
            page.evaluate("(id) => localStorage.setItem('prevo.profil', JSON.stringify({type: 'technicien', nom: '', technicienId: id}))", TECHNICIEN)
            page.goto(serveur.url + "/#/equipement/" + equipement)
            page.reload()                                   # même document : on recharge pour lire le profil
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.profil.type"), "technicien")
            page.wait_for_selector(".parc-controles a[href='#/controles/%s']" % EN_RETARD)
            self.assertEqual(page.locator("#parc-ajouter-controle").count(), 0)
            # Demandeur : pas de carte (l'écran Contrôles lui est fermé)
            page.evaluate("localStorage.setItem('prevo.profil', JSON.stringify({type: 'demandeur', nom: 'Lucie Martin', technicienId: ''}))")
            page.reload()
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.profil.type"), "demandeur")
            page.wait_for_selector(".parc .parc-consignation")
            self.assertEqual(page.locator(".parc-controles").count(), 0)

    def test_profils_technicien_en_lecture_demandeur_renvoye(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/controles", profil="technicien", technicien_id=TECHNICIEN)
            self.attendre_liste()
            self.assertEqual(page.locator("#menu a[data-ecran='controles']").count(), 1)
            self.assertEqual(page.locator("#controles-nouveau").count(), 0)
            for controle_id in (EN_RETARD, OBSERVATIONS):
                self.aller("#/controles/" + controle_id)
                self.attendre_fiche(controle_id)
                for selecteur in ("#controle-realise", "#controle-lever", "#controle-creer-ot", "#form-controle",
                                  ".controles-fiche button.btn-primaire", ".controles-fiche [name]"):
                    self.assertEqual(page.locator(selecteur).count(), 0, selecteur)
                self.assertIn("Organisme", page.inner_text(".controles-fiche"))
            self.aller("#/controles/nouveau")
            page.wait_for_function("location.hash === '#/accueil'")

        with ServeurPrevo() as serveur:
            contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
            self.addCleanup(contexte.close)
            autre = contexte.new_page()
            self.surveiller(autre)
            preregler_profil(contexte, "demandeur", "Lucie Martin")
            autre.goto(serveur.url + "/#/accueil")
            attendre_pret(autre)
            self.assertEqual(autre.locator("#menu a[data-ecran='controles']").count(), 0)
            autre.evaluate("location.hash = '#/controles'")
            autre.wait_for_function("document.getElementById('toast').textContent.includes('pas disponible')")
            autre.wait_for_function("location.hash === '#/accueil'")
            self.assertEqual(autre.locator(".controles-liste").count(), 0)


# ---------------------------------------------------------------------------
# Démo (file://) et téléphone
# ---------------------------------------------------------------------------

class TestDemoEtTelephone(CasControles):

    def test_demo_statuts_des_roles_et_controle_realise_avec_une_photo(self):
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-responsable")
        attendre_pret(page)
        page.click("#menu a[data-ecran='controles']")
        self.attendre_liste()
        for controle_id, role in ROLES:                 # dates décalées par semaines entières : rôles gardés
            with self.subTest(controle=controle_id):
                self.assertEqual(self.badges(controle_id)[0], role)
        self.aller("#/controles/" + A_PLANIFIER)
        self.attendre_fiche(A_PLANIFIER)
        page.click("#controle-realise")
        page.wait_for_selector("dialog [name=date]")
        page.set_input_files("dialog input[type=file]", files=[{"name": "rapport.png", "mimeType": "image/png", "buffer": PNG}])
        page.fill("dialog [name=observations]", "Prise de terre à reprendre")
        self.valider_fenetre()
        self.attendre_toast("Contrôle réalisé enregistré")
        ligne = page.evaluate("(id) => Object.assign({}, Donnees.trouver('controles_reglementaires', id))", A_PLANIFIER)
        self.assertEqual(ligne["derniere_date"], page.evaluate("Donnees.aujourdhui()"))
        self.assertEqual((ligne["observations"], ligne["observations_levees"]), ("Prise de terre à reprendre", "0"))
        self.assertTrue(ligne["rapport"].startswith("controle-" + A_PLANIFIER))
        page.wait_for_selector("#controle-rapport")
        self.assertTrue(page.get_attribute("#controle-rapport", "href").startswith("blob:"))
        self.assertEqual(self.badges(A_PLANIFIER, ".controles-fiche")[0], "observations à lever")

    def test_telephone_375px_sans_defilement_horizontal(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/controles", largeur=375)
            page.set_viewport_size({"width": 375, "height": 812})

            def sans_defilement(contexte):
                largeurs = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
                self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))

            page.wait_for_selector(".controles-liste .liste-cartes a.controles-lien")
            sans_defilement("liste")
            self.aller("#/controles/" + OBSERVATIONS)
            self.attendre_fiche(OBSERVATIONS)
            sans_defilement("fiche")
            for selecteur in ("#controle-realise", "#controle-lever", "#controle-creer-ot", "#form-controle button[type=submit]"):
                hauteur = page.eval_on_selector(selecteur, "e => e.getBoundingClientRect().height")
                self.assertGreaterEqual(hauteur, 48, selecteur)
            page.click("#controle-realise")
            page.wait_for_selector("dialog [name=date]")
            sans_defilement("fenêtre contrôle réalisé")
            page.click("dialog .fenetre-fermer")
            self.aller("#/controles/nouveau")
            page.wait_for_selector("#form-controle")
            sans_defilement("nouveau contrôle")


if __name__ == "__main__":
    unittest.main()
