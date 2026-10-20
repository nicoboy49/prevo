"""Tests de l'écran Équipe : techniciens et habilitations (ARCHITECTURE.md §15.8 et §15.2 ; brief
§6 « techniciens » et « habilitations », RG8 ; tâche T46).

Serveur Prévo sur une copie du jeu de démo (ServeurPrevo), profil préréglé ; les CSV sont relus sur
le disque. Aucun identifiant du jeu de démo n'est écrit en dur : les techniciens viennent des rôles
de scenarios_demo() (technicien_br_valide, technicien_br_echue) ou sont cherchés par leurs propriétés ;
les statuts attendus sont recalculés en Python à la date du jour de l'application.

Familles (le nom du test le dit) :
    creation     : créer un technicien, lui ajouter une habilitation, la renouveler → 2 lignes,
                   l'ancienne intacte ; refus (nom vide, échéance avant l'obtention, capacité,
                   taux, intitulé déjà présent) sans rien écrire ;
    statuts      : statuts des habilitations qui comptent sur la démo = calcul Python ;
                   ?filtre=a-renouveler = Equipe.aRenouveler = calcul Python ;
    desactivation: un technicien désactivé quitte la liste des actifs (confirmation demandée) ;
    profils      : technicien en lecture sans aucun taux horaire dans le DOM ; demandeur renvoyé ;
    conflit      : deux postes ajoutent chacun une habilitation en même temps : aucune perte ;
    telephone    : 375 px sans défilement horizontal.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_equipe.py" -v
"""
import csv
import datetime
import io
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

SCENARIOS = scenarios_demo()
TEC_BR_VALIDE = SCENARIOS["technicien_br_valide"]
TEC_BR_ECHUE = SCENARIOS["technicien_br_echue"]

APPEL_JS = """async ([fonction, arguments_]) => {
  try { return 'accepté:' + JSON.stringify(await Equipe[fonction](...arguments_)); }
  catch (erreur) { return (erreur instanceof Donnees.ErreurValidation ? 'refus:' : 'erreur:') + erreur.message; }
}"""
LIGNES_CONTENU_JS = """() => (document.getElementById('contenu').innerHTML + (document.getElementById('impression') || {innerHTML: ''}).innerHTML)"""


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


def nombre(valeur):
    try:
        return float(brut(valeur).replace(",", "."))
    except ValueError:
        return None


def qui_comptent(dossier, technicien_id):
    """Habilitations qui comptent : par intitulé (casse, espaces ignorés), l'échéance la plus lointaine
    (vide = sans limite), puis l'obtention la plus récente, puis l'identifiant le plus grand."""
    meilleures = {}
    for habilitation in lire_csv(dossier, "habilitations.csv"):
        if habilitation["technicien_id"] != technicien_id or not brut(habilitation["intitule"]):
            continue
        cle = re.sub(r"\s+", "", brut(habilitation["intitule"]).lower())
        rang = (jour(habilitation["date_echeance"]) or datetime.date.max, jour(habilitation["date_obtention"]) or datetime.date.min,
                int(re.sub(r"\D", "", habilitation["id"]) or 0))
        if cle not in meilleures or rang > meilleures[cle][0]:
            meilleures[cle] = (rang, habilitation)
    return [h for _, h in meilleures.values()]


def statut_python(habilitation, aujourdhui):
    obtention, echeance = jour(habilitation["date_obtention"]), jour(habilitation["date_echeance"])
    if obtention and obtention > aujourdhui:
        return "pas encore valable"
    if echeance and echeance < aujourdhui:
        return "échue"
    if echeance and (echeance - aujourdhui).days <= 60:
        return "à renouveler"
    return "valide"


def techniciens_actifs(dossier):
    return [t for t in lire_csv(dossier, "techniciens.csv") if brut(t["actif"]) != "0"]


def a_renouveler(dossier, aujourdhui):
    return sorted(h["id"] for t in techniciens_actifs(dossier) for h in qui_comptent(dossier, t["id"])
                  if statut_python(h, aujourdhui) in ("échue", "à renouveler"))


# ---------------------------------------------------------------------------
# Outils communs
# ---------------------------------------------------------------------------

class CasEquipe(CasNavigateur):

    def ouvrir(self, serveur, route, profil="responsable", technicien_id="", largeur=1280, page=None):
        page = page or self.page
        page.set_viewport_size({"width": largeur, "height": 900})
        preregler_profil(page.context, profil, nom="Lucie Martin" if profil == "demandeur" else "", technicien_id=technicien_id)
        page.goto(serveur.url + "/" + route)
        attendre_pret(page)
        page.wait_for_load_state("networkidle")

    def aller(self, route, page=None):
        (page or self.page).evaluate("(route) => { location.hash = route; }", route)

    def appeler(self, fonction, *arguments, page=None):
        return (page or self.page).evaluate(APPEL_JS, [fonction, list(arguments)])

    def aujourdhui(self):
        return datetime.date.fromisoformat(self.page.evaluate("Donnees.aujourdhui()"))

    def attendre_toast(self, morceau):
        self.page.wait_for_function(
            "(texte) => document.getElementById('toast').textContent.includes(texte)", arg=morceau)

    def attendre_fiche(self, technicien_id):
        self.page.wait_for_selector(".equipe-fiche[data-technicien='%s']" % technicien_id)

    def valider_fenetre(self):
        self.page.click("dialog .fenetre-actions .btn-primaire")


# ---------------------------------------------------------------------------
# Création, habilitation, renouvellement, refus
# ---------------------------------------------------------------------------

class TestCreation(CasEquipe):

    def test_creation_technicien_habilitation_renouvellement_deux_lignes_ancienne_intacte(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/equipe")
            aujourdhui = self.aujourdhui()
            page.click("#equipe-nouveau")
            page.wait_for_selector("#form-technicien")
            self.assertEqual(page.input_value("#form-technicien [name=capacite_h_semaine]"), "35")
            # Refus : nom vide, rien d'écrit
            chemin = serveur.dossier / "techniciens.csv"
            avant = chemin.read_bytes()
            page.fill("#form-technicien [name=prenom]", "Alice")
            page.click("#form-technicien button[type=submit]")
            page.wait_for_selector("#form-technicien .champ[data-champ='nom'] .erreur-champ:not([hidden])")
            self.assertEqual(chemin.read_bytes(), avant)
            # Création
            page.fill("#form-technicien [name=nom]", "Durand")
            page.fill("#form-technicien [name=metier]", "Électricienne")
            page.fill("#form-technicien [name=taux_horaire]", "45,5")
            page.click("#form-technicien button[type=submit]")
            self.attendre_toast("Technicien créé")
            page.wait_for_function("location.hash.startsWith('#/equipe/TEC-')")
            tec = page.evaluate("decodeURIComponent(location.hash.split('/').pop())")
            ligne = next(t for t in lire_csv(serveur.dossier, "techniciens.csv") if t["id"] == tec)
            self.assertEqual((ligne["nom"], ligne["prenom"], ligne["metier"], nombre(ligne["taux_horaire"]),
                              nombre(ligne["capacite_h_semaine"]), ligne["actif"]),
                             ("Durand", "Alice", "Électricienne", 45.5, 35.0, "1"))
            self.attendre_fiche(tec)

            # Habilitation : échéance avant l'obtention refusée dans la fenêtre
            habilitations = serveur.dossier / "habilitations.csv"
            avant = habilitations.read_bytes()
            page.click("#equipe-ajouter-habilitation")
            page.wait_for_selector("dialog [name=intitule]")
            obtention = (aujourdhui - datetime.timedelta(days=1000)).isoformat()
            echeance = (aujourdhui + datetime.timedelta(days=20)).isoformat()
            page.fill("dialog [name=intitule]", "BR")
            page.fill("dialog [name=date_obtention]", obtention)
            page.fill("dialog [name=date_echeance]", (aujourdhui - datetime.timedelta(days=1001)).isoformat())
            self.valider_fenetre()
            page.wait_for_selector("dialog .champ[data-champ='date_echeance'] .erreur-champ:not([hidden])")
            self.assertEqual(habilitations.read_bytes(), avant)
            page.fill("dialog [name=date_echeance]", echeance)
            self.valider_fenetre()
            self.attendre_toast("Habilitation ajoutée")
            lignes = [h for h in lire_csv(serveur.dossier, "habilitations.csv") if h["technicien_id"] == tec]
            self.assertEqual([(h["intitule"], h["date_obtention"], h["date_echeance"]) for h in lignes], [("BR", obtention, echeance)])
            ancienne = lignes[0]
            page.wait_for_selector(".equipe-statut[data-habilitation='%s']" % ancienne["id"])
            self.assertEqual(page.inner_text(".equipe-statut[data-habilitation='%s'] .badge" % ancienne["id"]), "à renouveler")

            # Renouvellement : nouvelle ligne de même intitulé, l'ancienne reste telle quelle
            page.click("button[data-action='renouveler'][data-habilitation='%s']" % ancienne["id"])
            page.wait_for_selector("dialog [name=date_echeance]")
            self.assertEqual(page.input_value("dialog [name=date_obtention]"), aujourdhui.isoformat())
            nouvelle_echeance = (aujourdhui + datetime.timedelta(days=3 * 365)).isoformat()
            page.fill("dialog [name=date_echeance]", nouvelle_echeance)
            self.valider_fenetre()
            self.attendre_toast("Habilitation renouvelée")
            lignes = [h for h in lire_csv(serveur.dossier, "habilitations.csv") if h["technicien_id"] == tec]
            self.assertEqual(len(lignes), 2)
            self.assertEqual(lignes[0], ancienne)
            self.assertEqual((lignes[1]["intitule"], lignes[1]["date_obtention"], lignes[1]["date_echeance"]),
                             ("BR", aujourdhui.isoformat(), nouvelle_echeance))
            page.wait_for_selector(".equipe-statut[data-habilitation='%s']" % lignes[1]["id"])
            self.assertEqual(page.inner_text(".equipe-statut[data-habilitation='%s'] .badge" % lignes[1]["id"]), "valide")
            self.assertIn(UI_date(echeance), page.inner_text(".equipe-historique"))
            journal = [e["action"] for e in lire_csv(serveur.dossier, "journal.csv")
                       if e["table"] == "habilitations" and e["id_ligne"] == lignes[1]["id"]]
            self.assertTrue(any("renouvellement de %s" % ancienne["id"] in a for a in journal), journal)

            # Refus par l'API (lignes fraîches), rien d'écrit
            avant_t, avant_h = chemin.read_bytes(), habilitations.read_bytes()
            for fonction, arguments, attendu in (
                    ("creerTechnicien", [{"nom": "  "}], "nom"),
                    ("creerTechnicien", [{"nom": "Test", "capacite_h_semaine": "90"}], "80"),
                    ("creerTechnicien", [{"nom": "Test", "taux_horaire": "-1"}], "négatif"),
                    ("creerTechnicien", [{"nom": "Durand", "prenom": "Alice"}], "déjà"),
                    ("ajouterHabilitation", [tec, {"intitule": "br", "date_obtention": obtention}], "Renouveler"),
                    ("ajouterHabilitation", [tec, {"intitule": "H0V", "date_obtention": obtention,
                                                   "date_echeance": (aujourdhui - datetime.timedelta(days=1001)).isoformat()}], "obtention"),
                    ("ajouterHabilitation", ["TEC-9999", {"intitule": "H0V", "date_obtention": obtention}], "introuvable"),
                    ("renouvelerHabilitation", [ancienne["id"], {"date_obtention": aujourdhui.isoformat(),
                                                                 "date_echeance": (aujourdhui - datetime.timedelta(days=1)).isoformat()}], "obtention"),
                    ("modifierHabilitation", [ancienne["id"], {"intitule": ""}], "intitulé")):
                with self.subTest(fonction=fonction, arguments=arguments):
                    resultat = self.appeler(fonction, *arguments)
                    self.assertTrue(resultat.startswith("refus:") and attendu in resultat, resultat)
            self.assertEqual((chemin.read_bytes(), habilitations.read_bytes()), (avant_t, avant_h))


def UI_date(iso):
    """Date ISO → JJ/MM/AAAA (format affiché par UI.dateFr)."""
    return datetime.date.fromisoformat(iso).strftime("%d/%m/%Y")


# ---------------------------------------------------------------------------
# Statuts sur la démo, filtre « à renouveler »
# ---------------------------------------------------------------------------

class TestStatuts(CasEquipe):

    def test_statuts_de_la_demo_egaux_au_calcul_python_et_filtre_a_renouveler(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/equipe")
            page.wait_for_selector(".equipe-liste a.equipe-lien")
            aujourdhui = self.aujourdhui()
            for technicien in techniciens_actifs(serveur.dossier):
                for habilitation in qui_comptent(serveur.dossier, technicien["id"]):
                    with self.subTest(habilitation=habilitation["id"]):
                        selecteur = ".equipe-liste .equipe-habilitation[data-habilitation='%s']" % habilitation["id"]
                        self.assertEqual(page.get_attribute(selecteur, "data-statut"), statut_python(habilitation, aujourdhui))
            # Le technicien dont la BR est échue : statut affiché sur sa fiche
            self.aller("#/equipe/" + TEC_BR_ECHUE)
            self.attendre_fiche(TEC_BR_ECHUE)
            for habilitation in qui_comptent(serveur.dossier, TEC_BR_ECHUE):
                self.assertEqual(page.inner_text(".equipe-statut[data-habilitation='%s'] .badge" % habilitation["id"]),
                                 statut_python(habilitation, aujourdhui))
            br = next(h for h in qui_comptent(serveur.dossier, TEC_BR_ECHUE) if h["intitule"] == "BR")
            self.assertEqual(statut_python(br, aujourdhui), "échue")
            # ?filtre=a-renouveler : même liste qu'Equipe.aRenouveler et que le calcul Python
            self.aller("#/equipe?filtre=a-renouveler")
            page.wait_for_selector(".equipe-a-renouveler")
            attendus = a_renouveler(serveur.dossier, aujourdhui)
            self.assertTrue(attendus)
            affiches = page.eval_on_selector_all(".equipe-a-renouveler .equipe-statut[data-habilitation]",
                                                 "s => Array.from(new Set(s.map(e => e.dataset.habilitation)))")
            self.assertEqual(sorted(affiches), attendus)
            self.assertEqual(sorted(page.evaluate("Equipe.aRenouveler().map(e => e.habilitation.id)")), attendus)

    def test_desactivation_le_technicien_quitte_la_liste_des_actifs(self):
        page = self.page
        with ServeurPrevo() as serveur:
            technicien = next(t for t in techniciens_actifs(serveur.dossier) if t["id"] not in (TEC_BR_VALIDE, TEC_BR_ECHUE))
            self.ouvrir(serveur, "#/equipe/" + technicien["id"])
            self.attendre_fiche(technicien["id"])
            page.uncheck("#form-technicien [name=actif]")
            page.click("#form-technicien button[type=submit]")
            page.wait_for_selector("dialog .fenetre-actions .btn-danger")
            page.click("dialog .fenetre-actions .btn-danger")
            self.attendre_toast("Technicien enregistré")
            ligne = next(t for t in lire_csv(serveur.dossier, "techniciens.csv") if t["id"] == technicien["id"])
            self.assertEqual(ligne["actif"], "0")
            self.assertEqual(ligne["nom"], technicien["nom"])                # rien d'autre n'a changé
            page.wait_for_selector(".equipe-fiche .badge.barre")
            self.aller("#/equipe")
            page.wait_for_selector(".equipe-liste a.equipe-lien")
            self.assertEqual(page.locator(".equipe-liste a.equipe-lien[href='#/equipe/%s']" % technicien["id"]).count(), 0)
            page.select_option("#equipe-etat", "tous")
            page.wait_for_selector(".equipe-liste a.equipe-lien[href='#/equipe/%s']" % technicien["id"])
            # Plus proposé au choix du profil technicien ni compté dans « à renouveler »
            self.assertNotIn(technicien["id"], page.evaluate("Equipe.aRenouveler().map(e => e.technicien.id)"))


# ---------------------------------------------------------------------------
# Profils, conflit, téléphone
# ---------------------------------------------------------------------------

class TestProfils(CasEquipe):

    def test_technicien_en_lecture_sans_taux_horaire_dans_le_dom_demandeur_renvoye(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/equipe", profil="technicien", technicien_id=TEC_BR_VALIDE)
            page.wait_for_selector(".equipe-liste a.equipe-lien")
            self.assertEqual(page.locator("#menu a[data-ecran='equipe']").count(), 1)
            self.assertEqual(page.locator("#equipe-nouveau").count(), 0)
            taux = [brut(t["taux_horaire"]) for t in lire_csv(serveur.dossier, "techniciens.csv") if brut(t["taux_horaire"])]
            for route in ["#/equipe", "#/equipe?filtre=a-renouveler", "#/equipe?etat=tous"] + \
                    ["#/equipe/" + t["id"] for t in lire_csv(serveur.dossier, "techniciens.csv")]:
                with self.subTest(route=route):
                    page.evaluate("document.getElementById('contenu').textContent = ''")   # pas de lecture de l'écran précédent
                    page.evaluate("(route) => App.naviguer(route)", route)                  # même adresse : réaffichée aussi
                    page.wait_for_function("(route) => location.hash === route && document.querySelector('#contenu .equipe')", arg=route)
                    page.wait_for_selector(".equipe-fiche, .equipe-liste, .equipe-a-renouveler")
                    html = page.evaluate(LIGNES_CONTENU_JS)
                    self.assertNotIn("taux", html.lower())
                    self.assertNotIn("€", html)
                    for valeur in taux:
                        self.assertIsNone(re.search(r"\b%s(?:[.,]0+)?\s*€" % re.escape(valeur), html), valeur)
                    if route.startswith("#/equipe/"):
                        for selecteur in ("#form-technicien", "#equipe-ajouter-habilitation", "button[data-action]", ".equipe-fiche [name]"):
                            self.assertEqual(page.locator(selecteur).count(), 0, selecteur)
            self.aller("#/equipe/nouveau")
            page.wait_for_function("location.hash === '#/accueil'")

            contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
            self.addCleanup(contexte.close)
            autre = contexte.new_page()
            self.surveiller(autre)
            self.ouvrir(serveur, "#/accueil", profil="demandeur", page=autre)
            self.assertEqual(autre.locator("#menu a[data-ecran='equipe']").count(), 0)
            self.aller("#/equipe", page=autre)
            autre.wait_for_function("document.getElementById('toast').textContent.includes('pas disponible')")
            autre.wait_for_function("location.hash === '#/accueil'")
            self.assertEqual(autre.locator(".equipe-liste").count(), 0)

    def test_conflit_deux_postes_ajoutent_une_habilitation_sans_perte(self):
        # Le second poste écrit avec une version périmée de habilitations.csv : 409, relecture, nouvel essai.
        self.autoriser_erreur(re.compile(r"status of 409.*/api/csv/habilitations"))
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/equipe")
            contexte_b = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 900})
            self.addCleanup(contexte_b.close)
            contexte_b.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
            poste_b = contexte_b.new_page()
            self.surveiller(poste_b)
            self.ouvrir(serveur, "#/equipe", page=poste_b)
            for page in (self.page, poste_b):
                page.evaluate("Donnees.arreterSurveillance()")
            aujourdhui = self.aujourdhui()
            nombre_avant = len(lire_csv(serveur.dossier, "habilitations.csv"))
            valeurs = {"date_obtention": (aujourdhui - datetime.timedelta(days=10)).isoformat(),
                       "date_echeance": (aujourdhui + datetime.timedelta(days=700)).isoformat()}
            conflits_avant = poste_b.evaluate("Donnees.statistiques.conflits")
            resultat_a = self.appeler("ajouterHabilitation", TEC_BR_VALIDE, dict(valeurs, intitule="Habilitation du poste A"))
            resultat_b = self.appeler("ajouterHabilitation", TEC_BR_ECHUE, dict(valeurs, intitule="Habilitation du poste B"), page=poste_b)
            self.assertTrue(resultat_a.startswith("accepté:") and resultat_b.startswith("accepté:"), (resultat_a, resultat_b))
            self.assertGreater(poste_b.evaluate("Donnees.statistiques.conflits"), conflits_avant)
            lignes = lire_csv(serveur.dossier, "habilitations.csv")
            self.assertEqual(len(lignes), nombre_avant + 2)
            intitules = {(h["technicien_id"], h["intitule"]) for h in lignes}
            self.assertIn((TEC_BR_VALIDE, "Habilitation du poste A"), intitules)
            self.assertIn((TEC_BR_ECHUE, "Habilitation du poste B"), intitules)
            self.assertEqual(len({h["id"] for h in lignes}), len(lignes))     # identifiants distincts

    def test_telephone_375px_sans_defilement_horizontal(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/equipe", largeur=375)
            page.set_viewport_size({"width": 375, "height": 812})

            def sans_defilement(contexte):
                largeurs = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
                self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))

            page.wait_for_selector(".equipe-liste .liste-cartes a.equipe-lien")
            sans_defilement("liste")
            self.aller("#/equipe?filtre=a-renouveler")
            page.wait_for_selector(".equipe-a-renouveler")
            sans_defilement("à renouveler")
            self.aller("#/equipe/" + TEC_BR_ECHUE)
            self.attendre_fiche(TEC_BR_ECHUE)
            sans_defilement("fiche")
            for selecteur in ("#equipe-ajouter-habilitation", "#form-technicien button[type=submit]", "button[data-action='renouveler']"):
                hauteur = page.eval_on_selector(selecteur, "e => e.getBoundingClientRect().height")
                self.assertGreaterEqual(hauteur, 48, selecteur)
            self.aller("#/equipe/nouveau")
            page.wait_for_selector("#form-technicien")
            sans_defilement("nouveau technicien")


if __name__ == "__main__":
    unittest.main()
