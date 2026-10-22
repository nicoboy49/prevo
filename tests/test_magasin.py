"""Tests du module Magasin (js/modules/magasin-*.js) : écran E9 et règle RG6 (ARCHITECTURE.md §14.4,
tâche T27). Serveur Prévo sur une copie du jeu de démo, profil préréglé ; les fichiers CSV sont
relus sur le disque. Aucun numéro d'OT, de mouvement ou d'achat n'est écrit en dur : les OT viennent
de scenarios_demo(), les articles et les achats sont cherchés par leurs propriétés.

Familles (le nom du test le dit) :
    negatif        : Magasin.sortir refusé (stock insuffisant : message exact et rien d'écrit sur le
                     disque ; sans OT ; OT clôturé ou annulé) ;
    point_commande : une sortie amène un article à son point de commande → onglet « À commander » ;
    achat          : demander l'achat → « Commander » → « Réceptionner » 5, par l'interface (D24) ;
    colonne_stock  : après sortie, retour, entrée et inventaire, articles.stock = stock recalculé en Python ;
                     aussi quand un autre poste sort pendant la copie du stock (conflit, copie rejouée) ;
    inventaire     : stock compté 7 dans l'onglet Inventaire → mouvement « inventaire », stock 7 ;
    suggestion     : fiche d'un article → valeur suggérée = calcul Python (D23), « Reprendre la
                     suggestion » puis Enregistrer → point_commande écrit ;
    concurrence    : deux postes sortent la dernière unité en même temps → une seule sortie ;
    profils        : technicien sans bouton d'écriture, demandeur sans menu Magasin ;
    demo           : parcours court en file:// ; telephone : 375 px sans défilement horizontal.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_magasin.py" -v
"""
import csv
import datetime
import io
import math
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo, url_fichier

SCENARIOS = scenarios_demo()
OT_OUVERT = SCENARIOS["ot_statut_en_cours"]               # OT « En cours » : sorties possibles
OT_CLOTURE = SCENARIOS["ot_statut_cloture_technique"]
OT_ANNULE = SCENARIOS["ot_statut_annule"]
KIT_GARNITURE = SCENARIOS["kit_garniture"]                # article de la démo avec des sorties
TECHNICIEN = SCENARIOS["technicien_br_valide"]

# Appel d'une écriture du magasin dans la page : 'accepté:<valeur>' ou 'refus:<message>'.
APPEL_JS = """async ([fonction, arguments_]) => {
  try { return 'accepté:' + JSON.stringify(await Magasin[fonction](...arguments_)); }
  catch (erreur) { return (erreur instanceof Donnees.ErreurValidation ? 'refus:' : 'erreur:') + erreur.message; }
}"""


# ---------------------------------------------------------------------------
# Lecture des CSV et calculs de référence en Python
# ---------------------------------------------------------------------------

def lire_csv(dossier, nom):
    """Lignes (dictionnaires) d'un CSV de Prévo sur le disque (UTF-8 avec BOM, « ; »)."""
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def reference(article):
    """Référence telle qu'affichée : sans l'apostrophe qui la protège dans le CSV (ARCHITECTURE.md §3.2)."""
    return article["reference"][1:] if article["reference"].startswith("'") else article["reference"]


def nombre(valeur):
    try:
        return float(str(valeur).replace(",", "."))
    except ValueError:
        return None


def texte_nombre(valeur):
    """Nombre tel que l'écrit un message de Prévo : '3', '2,5'."""
    return str(int(valeur)) if float(valeur).is_integer() else str(valeur).replace(".", ",")


def stock_python(mouvements, article_id):
    """Stock recalculé (date puis identifiant) : un inventaire fixe la valeur, entrée et retour
    ajoutent, une sortie retire."""
    stock = 0.0
    for mouvement in sorted((m for m in mouvements if m["article_id"] == article_id), key=lambda m: (m["date"], m["id"])):
        quantite = nombre(mouvement["quantite"]) or 0.0
        if mouvement["type"] == "inventaire":
            stock = quantite
        elif mouvement["type"] in ("entrée", "retour"):
            stock += quantite
        elif mouvement["type"] == "sortie":
            stock -= quantite
    return round(stock, 6)


def suggestion_python(article, mouvements, aujourdhui):
    """D23 : (sorties − retours des 365 derniers jours) / 365 × délai + sécurité, à l'unité
    supérieure ; None sans sortie sur la période."""
    fin = datetime.date.fromisoformat(aujourdhui)
    debut = (fin - datetime.timedelta(days=364)).isoformat()
    sorties = retours = 0.0
    for mouvement in mouvements:
        jour = mouvement["date"][:10]
        if mouvement["article_id"] != article["id"] or not debut <= jour <= aujourdhui:
            continue
        if mouvement["type"] == "sortie":
            sorties += nombre(mouvement["quantite"]) or 0
        elif mouvement["type"] == "retour":
            retours += nombre(mouvement["quantite"]) or 0
    if sorties <= 0:
        return None
    delai = nombre(article["delai_jours"]) or 0
    securite = nombre(article["stock_securite"]) or 0
    return math.ceil(round(max(0.0, sorties - retours) * delai / 365 + securite, 6))


def achats_ouverts(dossier):
    return {a["article_id"] for a in lire_csv(dossier, "achats.csv") if a["statut"] in ("demandée", "commandée")}


def article_au_dessus_du_point(dossier):
    """Article actif, sans achat en cours, dont le stock dépasse le point de commande du plus petit
    écart : (article, stock, écart)."""
    mouvements = lire_csv(dossier, "mouvements_stock.csv")
    ouverts = achats_ouverts(dossier)
    candidats = []
    for article in lire_csv(dossier, "articles.csv"):
        point = nombre(article["point_commande"])
        if article["actif"] == "0" or point is None or article["id"] in ouverts:
            continue
        stock = stock_python(mouvements, article["id"])
        if stock > point:
            candidats.append((stock - point, article["id"], article, stock))
    candidats.sort(key=lambda c: (c[0], c[1]))
    ecart, _, article, stock = candidats[0]
    return article, stock, ecart


class CasMagasin(CasNavigateur):
    """Outils communs : ouvrir une route avec un profil, appeler Magasin.*, attendre un message."""

    def ouvrir(self, serveur, route, profil="responsable", technicien_id="", largeur=1280, page=None):
        page = page or self.page
        page.set_viewport_size({"width": largeur, "height": 900})
        preregler_profil(page.context, profil, nom="Lucie Martin" if profil == "demandeur" else "",
                         technicien_id=technicien_id)
        page.goto(serveur.url + "/" + route)
        attendre_pret(page)
        # Les écritures du démarrage (format, OT préventifs échus) sont finies avant le test.
        page.wait_for_load_state("networkidle")

    def aller(self, route, page=None):
        (page or self.page).evaluate("location.hash = %r" % route)

    def appeler(self, fonction, *arguments, page=None):
        return (page or self.page).evaluate(APPEL_JS, [fonction, list(arguments)])

    def attendre_toast(self, morceau, page=None):
        (page or self.page).wait_for_function(
            "(texte) => document.getElementById('toast').textContent.includes(texte)", arg=morceau)

    def ouvrir_onglet(self, onglet):
        self.aller("#/magasin?onglet=" + onglet)
        self.page.wait_for_selector(".magasin-onglets .onglet[data-onglet='%s'][aria-selected='true']" % onglet)

    def panneau(self, onglet):
        return ".magasin-onglets .panneau-onglet[data-onglet='%s']" % onglet

    def valider_fenetre(self):
        self.page.click("dialog .fenetre-actions .btn-primaire")

    def sans_defilement(self, contexte):
        largeurs = self.page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))


# ---------------------------------------------------------------------------
# RG6 : sorties refusées
# ---------------------------------------------------------------------------

class TestSorties(CasMagasin):

    def test_negatif_stock_insuffisant_sans_ot_ot_cloture_rien_sur_le_disque(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/magasin")
            fichier = serveur.dossier / "mouvements_stock.csv"
            avant = fichier.read_bytes()
            stock = stock_python(lire_csv(serveur.dossier, "mouvements_stock.csv"), KIT_GARNITURE)
            self.assertEqual(self.page.evaluate("(id) => Donnees.stockArticle(id)", KIT_GARNITURE), stock)
            demande = stock + 1
            self.assertEqual(self.appeler("sortir", OT_OUVERT, KIT_GARNITURE, demande, "essai"),
                             "refus:Stock insuffisant : %s en stock, %s demandé" % (texte_nombre(stock), texte_nombre(demande)))
            resultat = self.appeler("sortir", "", KIT_GARNITURE, 1, "")
            self.assertTrue(resultat.startswith("refus:") and "imputée à un ordre de travail" in resultat, resultat)
            resultat = self.appeler("sortir", OT_CLOTURE, KIT_GARNITURE, 1, "")
            self.assertTrue(resultat.startswith("refus:") and "Clôturé techniquement" in resultat, resultat)
            resultat = self.appeler("sortir", OT_ANNULE, KIT_GARNITURE, 1, "")
            self.assertTrue(resultat.startswith("refus:") and "Annulé" in resultat, resultat)
            resultat = self.appeler("sortir", OT_OUVERT, KIT_GARNITURE, 0, "")
            self.assertTrue(resultat.startswith("refus:") and "supérieure à 0" in resultat, resultat)
            resultat = self.appeler("retourner", OT_OUVERT, KIT_GARNITURE, 1, "")
            self.assertTrue(resultat.startswith("refus:") and "Retour refusé" in resultat, resultat)
            self.assertEqual(fichier.read_bytes(), avant, "mouvements_stock.csv ne doit pas changer")
            self.assertEqual(self.page.evaluate("(id) => Donnees.stockArticle(id)", KIT_GARNITURE), stock)

    def test_point_commande_une_sortie_fait_apparaitre_l_article_a_commander(self):
        with ServeurPrevo() as serveur:
            article, stock, ecart = article_au_dessus_du_point(serveur.dossier)
            self.ouvrir(serveur, "#/magasin?onglet=a-commander")
            panneau = self.panneau("a-commander")
            self.page.wait_for_selector(panneau + " .magasin-liste")
            self.assertNotIn(reference(article), self.page.inner_text(panneau))
            self.assertTrue(self.appeler("sortir", OT_OUVERT, article["id"], ecart, "test point de commande").startswith("accepté:"))
            self.page.evaluate("App.reafficher()")
            self.page.wait_for_selector(panneau + " .magasin-liste")
            texte = self.page.inner_text(panneau)
            self.assertIn(reference(article), texte)
            self.assertIn("Demander l'achat", texte)
            # Badge « À commander » dans l'onglet Articles, et colonne stock au niveau du point
            self.ouvrir_onglet("articles")
            self.page.fill("#magasin-recherche-article", reference(article))
            self.page.wait_for_selector(self.panneau("articles") + " .magasin-badge-commander")
            ligne = next(a for a in lire_csv(serveur.dossier, "articles.csv") if a["id"] == article["id"])
            self.assertEqual(nombre(ligne["stock"]), nombre(article["point_commande"]))


# ---------------------------------------------------------------------------
# Achats : demandée → commandée → reçue (D24)
# ---------------------------------------------------------------------------

class TestAchats(CasMagasin):

    def test_achat_demande_commande_reception_par_l_interface(self):
        page = self.page
        with ServeurPrevo() as serveur:
            article, stock, ecart = article_au_dessus_du_point(serveur.dossier)
            self.ouvrir(serveur, "#/magasin")
            self.assertTrue(self.appeler("sortir", OT_OUVERT, article["id"], ecart, "").startswith("accepté:"))
            self.ouvrir_onglet("a-commander")
            proposee = page.evaluate("(id) => Magasin.aCommander().find((e) => e.article.id === id).quantiteProposee", article["id"])
            page.click("button[data-action='demander-achat'][data-article='%s']" % article["id"])
            page.wait_for_selector("dialog [name=quantite]")
            self.valider_fenetre()
            self.attendre_toast("Demande d'achat")
            achats = [a for a in lire_csv(serveur.dossier, "achats.csv") if a["article_id"] == article["id"] and a["statut"] == "demandée"]
            self.assertEqual(len(achats), 1, achats)
            achat = achats[0]
            prix_avant = article["prix_unitaire"]
            self.assertEqual(nombre(achat["quantite"]), proposee)
            self.assertEqual(achat["prix_unitaire"], prix_avant)
            self.assertEqual(achat["fournisseur_id"], article["fournisseur_id"])
            self.assertEqual(achat["date"], page.evaluate("Donnees.aujourdhui()"))
            # Une seconde demande du même article est refusée tant que la première n'est pas commandée
            self.assertIn("attend déjà", self.appeler("demanderAchat", article["id"], 3))
            # Onglet Achats : « Commander »
            self.ouvrir_onglet("achats")
            page.click("button[data-action='commander'][data-achat='%s']" % achat["id"])
            self.attendre_toast("commandé")
            ligne = next(a for a in lire_csv(serveur.dossier, "achats.csv") if a["id"] == achat["id"])
            self.assertEqual(ligne["statut"], "commandée")
            # « Réceptionner » 5
            stock_avant = stock_python(lire_csv(serveur.dossier, "mouvements_stock.csv"), article["id"])
            page.click("button[data-action='receptionner'][data-achat='%s']" % achat["id"])
            page.wait_for_selector("dialog [name=quantite_recue]")
            page.fill("dialog [name=quantite_recue]", "5")
            self.valider_fenetre()
            self.attendre_toast("réceptionné")
            ligne = next(a for a in lire_csv(serveur.dossier, "achats.csv") if a["id"] == achat["id"])
            self.assertEqual((ligne["statut"], ligne["date_reception"]), ("reçue", page.evaluate("Donnees.aujourdhui()")))
            mouvements = lire_csv(serveur.dossier, "mouvements_stock.csv")
            entrees = [m for m in mouvements if m["article_id"] == article["id"] and m["type"] == "entrée"
                       and m["commentaire"].startswith("Réception " + achat["id"])]
            self.assertEqual(len(entrees), 1, entrees)
            self.assertEqual(nombre(entrees[0]["quantite"]), 5)
            self.assertEqual(entrees[0]["utilisateur"], "Responsable")
            self.assertEqual(stock_python(mouvements, article["id"]), stock_avant + 5)
            ligne_article = next(a for a in lire_csv(serveur.dossier, "articles.csv") if a["id"] == article["id"])
            self.assertEqual(nombre(ligne_article["stock"]), stock_avant + 5)
            self.assertEqual(ligne_article["prix_unitaire"], prix_avant, "D24 : une réception ne change pas le prix")
            # Une seconde réception est refusée (rien n'entre en double)
            self.assertIn("déjà réceptionné", self.appeler("recevoir", achat["id"], 5))


# ---------------------------------------------------------------------------
# Colonne stock, inventaire, point de commande suggéré
# ---------------------------------------------------------------------------

class TestStock(CasMagasin):

    def test_colonne_stock_egale_au_stock_recalcule_apres_chaque_type_de_mouvement(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/magasin")
            articles = [a for a in lire_csv(serveur.dossier, "articles.csv") if a["actif"] != "0"]
            mouvements = lire_csv(serveur.dossier, "mouvements_stock.csv")
            avec_stock = [a["id"] for a in articles if stock_python(mouvements, a["id"]) >= 3]
            sortie, entree, inventaire = avec_stock[0], avec_stock[1], avec_stock[2]
            for appel in (("sortir", OT_OUVERT, sortie, 2, "sortie de test"),
                          ("retourner", OT_OUVERT, sortie, 1, "retour de test"),
                          ("entrer", entree, 3, "entrée de test"),
                          ("inventorier", [{"articleId": inventaire, "quantite": 4}], "inventaire de test")):
                resultat = self.appeler(*appel)
                self.assertTrue(resultat.startswith("accepté:"), (appel, resultat))
                mouvements = lire_csv(serveur.dossier, "mouvements_stock.csv")
                for ligne in lire_csv(serveur.dossier, "articles.csv"):
                    with self.subTest(apres=appel[0], article=ligne["id"]):
                        self.assertEqual(nombre(ligne["stock"]), stock_python(mouvements, ligne["id"]))
            # Les mouvements portent le type, l'OT et l'utilisateur attendus
            derniers = {m["commentaire"]: m for m in mouvements}
            self.assertEqual((derniers["sortie de test"]["type"], derniers["sortie de test"]["ot_id"]), ("sortie", OT_OUVERT))
            self.assertEqual((derniers["retour de test"]["type"], derniers["retour de test"]["ot_id"]), ("retour", OT_OUVERT))
            self.assertEqual((derniers["entrée de test"]["type"], derniers["entrée de test"]["ot_id"]), ("entrée", ""))
            self.assertEqual(derniers["inventaire de test"]["type"], "inventaire")
            self.assertEqual({m["utilisateur"] for m in derniers.values() if "de test" in m["commentaire"]}, {"Responsable"})

    def test_inventaire_stock_compte_7_par_l_onglet(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/magasin?onglet=inventaire")
            mouvements = lire_csv(serveur.dossier, "mouvements_stock.csv")
            article = next(a for a in lire_csv(serveur.dossier, "articles.csv")
                           if a["actif"] != "0" and stock_python(mouvements, a["id"]) != 7)
            stock = stock_python(mouvements, article["id"])
            champ = "input[data-inventaire='%s']" % article["id"]
            page.wait_for_selector(champ)
            page.fill(champ, "7")
            ecart = 7 - stock
            attendu = ("+" if ecart > 0 else "−") + texte_nombre(abs(ecart))
            self.assertEqual(page.inner_text("[data-ecart='%s']" % article["id"]).strip(), attendu)
            page.click("#magasin-valider-inventaire")
            page.wait_for_selector("dialog .fenetre-actions .btn-primaire")
            self.valider_fenetre()
            self.attendre_toast("Inventaire enregistré")
            mouvements = lire_csv(serveur.dossier, "mouvements_stock.csv")
            dernier = [m for m in mouvements if m["article_id"] == article["id"]][-1]
            self.assertEqual((dernier["type"], nombre(dernier["quantite"]), dernier["ot_id"]), ("inventaire", 7, ""))
            self.assertEqual(stock_python(mouvements, article["id"]), 7)
            ligne = next(a for a in lire_csv(serveur.dossier, "articles.csv") if a["id"] == article["id"])
            self.assertEqual(nombre(ligne["stock"]), 7)
            self.assertEqual(page.evaluate("(id) => Donnees.stockArticle(id)", article["id"]), 7)

    def test_suggestion_valeur_calculee_reprise_puis_enregistree(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/magasin")
            aujourdhui = page.evaluate("Donnees.aujourdhui()")
            mouvements = lire_csv(serveur.dossier, "mouvements_stock.csv")
            candidats = []
            for article in lire_csv(serveur.dossier, "articles.csv"):
                valeur = suggestion_python(article, mouvements, aujourdhui)
                if valeur is not None and valeur != nombre(article["point_commande"]):
                    candidats.append((article, valeur))
            self.assertTrue(candidats, "aucun article de la démo dont la suggestion diffère du point de commande")
            article, valeur = candidats[0]
            self.aller("#/magasin/article/" + article["id"])
            page.wait_for_selector("#form-article #magasin-suggestion")
            self.assertEqual(page.get_attribute("#magasin-suggestion", "data-valeur"), str(valeur))
            self.assertIn("Point de commande suggéré : %d" % valeur, page.inner_text("#magasin-suggestion"))
            champ = "#form-article [name=point_commande]"
            self.assertEqual(nombre(page.input_value(champ)), nombre(article["point_commande"]))
            page.click("#magasin-reprendre-suggestion")
            self.assertEqual(page.input_value(champ), str(valeur))
            # Reprendre la suggestion n'enregistre rien tout seul
            ligne = next(a for a in lire_csv(serveur.dossier, "articles.csv") if a["id"] == article["id"])
            self.assertEqual(ligne["point_commande"], article["point_commande"])
            page.click("#form-article button[type=submit]")
            self.attendre_toast("Article enregistré")
            ligne = next(a for a in lire_csv(serveur.dossier, "articles.csv") if a["id"] == article["id"])
            self.assertEqual(nombre(ligne["point_commande"]), valeur)
            self.assertEqual(ligne["prix_unitaire"], article["prix_unitaire"])
            # Un article sans aucune sortie : « non calculable », pas de bouton
            sans_sortie = next((a for a in lire_csv(serveur.dossier, "articles.csv")
                                if suggestion_python(a, mouvements, aujourdhui) is None), None)
            if sans_sortie is not None:
                self.aller("#/magasin/article/" + sans_sortie["id"])
                page.wait_for_function("(id) => document.querySelector('.magasin-fiche h1') && "
                                       "document.querySelector('.magasin-fiche h1').textContent.includes(id)",
                                       arg=reference(sans_sortie))
                self.assertIn("non calculable", page.inner_text("#magasin-suggestion"))
                self.assertEqual(page.locator("#magasin-reprendre-suggestion").count(), 0)


# ---------------------------------------------------------------------------
# Deux postes : la dernière unité
# ---------------------------------------------------------------------------

LANCER_SORTIE_JS = """([otId, articleId]) => {
  window.__sortie = null;
  Magasin.sortir(otId, articleId, 1, 'dernière unité').then(
    () => { window.__sortie = 'accepté'; },
    (erreur) => { window.__sortie = 'refus:' + erreur.message; });
}"""


class TestConcurrence(CasMagasin):

    def test_concurrence_deux_postes_sortent_la_derniere_unite(self):
        # Le poste qui écrit le second a une version périmée de mouvements_stock.csv : 409, relecture, refus.
        self.autoriser_erreur(re.compile(r"status of 409.*/api/csv/mouvements_stock"))
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/magasin")
            contexte_b = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 900})
            self.addCleanup(contexte_b.close)
            contexte_b.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
            preregler_profil(contexte_b, "responsable", poste="Poste B")
            poste_b = contexte_b.new_page()
            self.surveiller(poste_b)
            poste_b.goto(serveur.url + "/#/magasin")
            attendre_pret(poste_b)
            poste_b.wait_for_load_state("networkidle")
            # Plus qu'une unité en stock, vue par les deux postes
            self.assertTrue(self.appeler("inventorier", [{"articleId": KIT_GARNITURE, "quantite": 1}], "reste une").startswith("accepté:"))
            poste_b.evaluate("Donnees.rafraichir()")
            self.assertEqual(poste_b.evaluate("(id) => Donnees.stockArticle(id)", KIT_GARNITURE), 1)
            sorties_avant = [m for m in lire_csv(serveur.dossier, "mouvements_stock.csv") if m["type"] == "sortie"]
            for page in (self.page, poste_b):
                page.evaluate(LANCER_SORTIE_JS, [OT_OUVERT, KIT_GARNITURE])
            resultats = []
            for page in (self.page, poste_b):
                page.wait_for_function("window.__sortie !== null")
                resultats.append(page.evaluate("window.__sortie"))
            self.assertEqual(sorted(resultats), ["accepté", "refus:Stock insuffisant : 0 en stock, 1 demandé"], resultats)
            # Le refus vient bien des lignes relues après le conflit (le cache disait « 1 en stock »)
            conflits = sum(page.evaluate("Donnees.statistiques.conflits") for page in (self.page, poste_b))
            self.assertGreaterEqual(conflits, 1)
            mouvements = lire_csv(serveur.dossier, "mouvements_stock.csv")
            nouvelles = [m for m in mouvements if m["type"] == "sortie"][len(sorties_avant):]
            self.assertEqual([(m["article_id"], m["ot_id"], nombre(m["quantite"])) for m in nouvelles], [(KIT_GARNITURE, OT_OUVERT, 1)])
            self.assertEqual(stock_python(mouvements, KIT_GARNITURE), 0)
            ligne = next(a for a in lire_csv(serveur.dossier, "articles.csv") if a["id"] == KIT_GARNITURE)
            self.assertEqual(nombre(ligne["stock"]), 0)

    def test_colonne_stock_juste_quand_un_autre_poste_sort_pendant_la_copie_du_stock(self):
        """Le poste A a écrit sa sortie ; sa copie du stock dans articles.csv est retenue pendant que
        le poste B fait toute sa sortie ; la copie de A arrive ensuite (409, articles relu, copie
        rejouée) : la colonne doit valoir le stock recalculé depuis mouvements_stock.csv, pas le
        stock du cache de A (qui ignore la sortie de B)."""
        self.autoriser_erreur(re.compile(r"status of 409.*/api/csv/(articles|mouvements_stock)"))
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/magasin")
            contexte_b = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 900})
            self.addCleanup(contexte_b.close)
            contexte_b.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
            preregler_profil(contexte_b, "responsable", poste="Poste B")
            poste_b = contexte_b.new_page()
            self.surveiller(poste_b)
            poste_b.goto(serveur.url + "/#/magasin")
            attendre_pret(poste_b)
            poste_b.wait_for_load_state("networkidle")
            # Pas de relecture automatique : seul le code de l'écriture peut voir la sortie de B
            for page in (self.page, poste_b):
                page.evaluate("Donnees.arreterSurveillance()")
            self.assertTrue(self.appeler("inventorier", [{"articleId": KIT_GARNITURE, "quantite": 5}], "cinq").startswith("accepté:"))
            poste_b.evaluate("Donnees.rafraichir()")

            # A : sortie de 1 ; sa première écriture de articles.csv (la copie du stock) est retenue
            retenues = []

            def retenir(route):
                if route.request.method == "PUT" and not retenues:
                    retenues.append(route)
                else:
                    route.continue_()
            self.page.route("**/api/csv/articles", retenir)
            conflits_avant = self.page.evaluate("Donnees.statistiques.conflits")
            self.page.evaluate("""([ot, article]) => { window.__a = null; Magasin.sortir(ot, article, 1, 'poste A').then(
                (id) => { window.__a = 'accepté'; }, (erreur) => { window.__a = 'refus:' + erreur.message; }); }""",
                               [OT_OUVERT, KIT_GARNITURE])
            for _ in range(200):
                if retenues:
                    break
                self.page.wait_for_timeout(50)
            self.assertTrue(retenues, "la copie du stock du poste A n'a pas été écrite")

            # B : sortie de 1, complète (mouvement puis colonne)
            self.assertTrue(self.appeler("sortir", OT_OUVERT, KIT_GARNITURE, 1, "poste B", page=poste_b).startswith("accepté:"))
            mouvements = lire_csv(serveur.dossier, "mouvements_stock.csv")
            self.assertEqual(stock_python(mouvements, KIT_GARNITURE), 3)

            # La copie de A part maintenant : conflit, articles relu, copie rejouée
            retenues[0].continue_()
            self.page.wait_for_function("window.__a !== null")
            self.assertEqual(self.page.evaluate("window.__a"), "accepté")
            self.page.unroute("**/api/csv/articles")
            self.assertGreater(self.page.evaluate("Donnees.statistiques.conflits"), conflits_avant)
            mouvements = lire_csv(serveur.dossier, "mouvements_stock.csv")
            ligne = next(a for a in lire_csv(serveur.dossier, "articles.csv") if a["id"] == KIT_GARNITURE)
            self.assertEqual(nombre(ligne["stock"]), stock_python(mouvements, KIT_GARNITURE))
            self.assertEqual(nombre(ligne["stock"]), 3)


# ---------------------------------------------------------------------------
# Profils (D27)
# ---------------------------------------------------------------------------

class TestProfils(CasMagasin):

    def test_profils_technicien_en_consultation_sans_bouton_d_ecriture(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/magasin", profil="technicien", technicien_id=TECHNICIEN)
            page.wait_for_selector(".magasin-onglets .barre-onglets")
            onglets = page.eval_on_selector_all(".magasin-onglets .onglet", "o => o.map(b => b.dataset.onglet)")
            self.assertEqual(onglets, ["articles", "mouvements", "a-commander", "achats", "fournisseurs"])
            self.assertEqual(page.locator("#magasin-nouvel-article").count(), 0)
            for onglet in onglets:
                self.ouvrir_onglet(onglet)
                panneau = self.panneau(onglet)
                page.wait_for_selector(panneau + " > *")
                # (« Voir les achats reçus » ne fait qu'afficher : seul bouton permis)
                ecriture = panneau + " button[data-action]:not([data-action='voir-recues']), " + panneau + " .btn-primaire"
                self.assertEqual(page.locator(ecriture).count(), 0, onglet)
            # Inventaire demandé dans l'adresse : pas d'onglet Inventaire, un autre onglet s'ouvre
            self.aller("#/magasin?onglet=inventaire")
            page.wait_for_function("location.hash.startsWith('#/magasin?onglet=') && !location.hash.includes('inventaire')")
            self.assertEqual(page.locator(".onglet[data-onglet='inventaire'], input[data-inventaire]").count(), 0)
            # Fiche : valeurs et suggestion en lecture, aucun bouton d'écriture
            self.aller("#/magasin/article/" + KIT_GARNITURE)
            page.wait_for_selector(".magasin-fiche #magasin-suggestion")
            for selecteur in ("#form-article", "#magasin-entree", "#magasin-demander-achat", "#magasin-reprendre-suggestion"):
                self.assertEqual(page.locator(selecteur).count(), 0, selecteur)
            self.assertIn("Point de commande", page.inner_text(".magasin-fiche"))
            # Lot 6 (§20.1) : lien vers le wiki de l'article, même forme que celui de la fiche équipement
            lien = page.locator("#lien-wiki-article")
            self.assertEqual(lien.get_attribute("href"), "#/wiki/" + KIT_GARNITURE)
            self.assertEqual(lien.inner_text().strip(), "Wiki de cet article")
            self.assertEqual(lien.locator("svg.icone").count(), 1)
            # Création d'article : réservée au responsable (retour à l'accueil)
            self.aller("#/magasin/article/nouveau")
            page.wait_for_function("location.hash === '#/accueil'")

    def test_profils_demandeur_sans_menu_magasin(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/accueil", profil="demandeur")
            self.assertEqual(page.locator("#menu a[data-ecran='magasin'], #barre-bas a[data-ecran='magasin']").count(), 0)
            self.aller("#/magasin")
            page.wait_for_function("location.hash === '#/accueil'")
            self.assertEqual(page.locator(".magasin-onglets").count(), 0)


# ---------------------------------------------------------------------------
# Démo et téléphone
# ---------------------------------------------------------------------------

class TestDemoEtTelephone(CasMagasin):

    def test_demo_parcours_court_entree_en_stock(self):
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-responsable")
        attendre_pret(page)
        page.click("#menu a[data-ecran='magasin']")
        page.wait_for_selector(self.panneau("articles") + " .table tbody tr")
        self.assertIn(page.evaluate("(id) => Donnees.trouver('articles', id).reference", KIT_GARNITURE),
                      page.inner_text(self.panneau("articles")))
        avant = page.evaluate("(id) => Donnees.stockArticle(id)", KIT_GARNITURE)
        self.aller("#/magasin/article/" + KIT_GARNITURE)
        page.click("#magasin-entree")
        page.wait_for_selector("dialog [name=quantite]")
        page.fill("dialog [name=quantite]", "2")
        page.fill("dialog [name=commentaire]", "pièce retrouvée")
        self.valider_fenetre()
        self.attendre_toast("Entrée en stock enregistrée")
        self.assertEqual(page.evaluate("(id) => Donnees.stockArticle(id)", KIT_GARNITURE), avant + 2)
        self.assertEqual(nombre(page.evaluate("(id) => Donnees.trouver('articles', id).stock", KIT_GARNITURE)), avant + 2)
        page.wait_for_function("(texte) => document.getElementById('magasin-stock').textContent.startsWith(texte)",
                               arg=texte_nombre(avant + 2))

    def test_telephone_375px_sans_defilement_horizontal(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/magasin", largeur=375)
            page.set_viewport_size({"width": 375, "height": 812})
            for onglet in ("articles", "mouvements", "inventaire", "a-commander", "achats", "fournisseurs"):
                self.ouvrir_onglet(onglet)
                page.wait_for_selector(self.panneau(onglet) + " > *")
                self.sans_defilement("onglet " + onglet)
            self.ouvrir_onglet("articles")
            self.assertTrue(page.is_visible(self.panneau("articles") + " .liste-cartes"))
            self.aller("#/magasin/article/" + KIT_GARNITURE)
            page.wait_for_selector("#form-article")
            self.sans_defilement("fiche article")
            for selecteur in ("#magasin-entree", "#magasin-demander-achat", "#form-article button[type=submit]"):
                hauteur = page.eval_on_selector(selecteur, "e => e.getBoundingClientRect().height")
                self.assertGreaterEqual(hauteur, 48, selecteur)
            self.aller("#/magasin/article/nouveau")
            page.wait_for_selector("#form-article [name=reference]")
            self.sans_defilement("nouvel article")


if __name__ == "__main__":
    unittest.main()
