"""Recette du lot 2 de bout en bout (brief §14, tâche T33).

On rejoue les scénarios de recette du lot 2 comme un utilisateur, par l'interface, sans refaire les
tests des modules (règles, écritures, écrans : voir test_preventif, test_magasin, test_ordres_lot2,
test_demandes_lot2, test_parc_lot2, test_accueil_lot2). Chaque scénario applicable est joué :
    serveur : serveur.py (ServeurPrevo, copie du jeu de démo), vérifications sur le disque ;
    demo    : index.html en file:// → « Essayer avec les données de démo » ; rien ne survit à un
              rechargement : le profil est changé par l'interface (bouton du poste), sans recharger.

Scénarios (le nom de chaque test contient le mot-clé) :
    pompe         scénario « panne sur pompe » du lot 1 complet (tests/test_recette_lot1.py, même
                  parcours), avec la sortie du kit garniture depuis l'OT : stock du kit −1 (serveur :
                  articles.csv et mouvement « sortie » sur le disque ; démo : fiche de l'article) ;
    gamme         gamme mensuelle échue : un seul OT préventif après trois rechargements (serveur) ou
                  trois « Générer les OT échus » (démo) ; deux postes ouverts ensemble : un seul OT ;
                  exécution et clôture de l'OT par l'interface → échéance affichée dans Préventif au
                  mois suivant ; relevés saisis depuis la fiche de CP-01 → OT de la gamme compteur et
                  de la gamme seuil (serveur) ;
    stock         sortie qui rendrait le stock négatif refusée (message, stock inchangé) ; sortie qui
                  amène un article à son point de commande → « À commander », compteur de l'accueil +1 ;
    achat         demande d'achat → commandée → réceptionnée → stock ; inventaire (serveur) ;
    causes        encart « Causes fréquentes ici » des fuites de PO-02 sur la fiche DI et la fiche OT,
                  vu par les trois profils (« n cas sur N ») ; sous 5 cas : message d'attente seul ;
    anomalie      OT préventif → « Signaler une anomalie (DI liée) » → DI liée, OT marqué, liens dans
                  les deux sens ;
    liste_blanche brief, tests, outils, reference-design, docs, serveur.py → 404 ; l'application marche ;
    design        360 px : aucun défilement horizontal, zones tactiles ≥ 48 px (Préventif, Magasin,
                  fiche OT avec pièces sorties), pas de carte QR ; 1440 px : nom de l'entreprise sur
                  deux lignes ; aucune erreur console sur tout le parcours (CasNavigateur).

Aucun identifiant du jeu de démo n'est écrit en dur : scenarios_demo() (tests/fixtures/
demo-scenarios.json) ou recherche par propriétés dans les CSV (copie du serveur, ou donnees/demo pour
le mode démo, dont js/demo-donnees.js est la copie exacte).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_recette_lot2.py" -v
"""
import collections
import csv
import datetime
import http.client
import io
import re
import unittest
from pathlib import Path

import test_recette_lot1 as lot1      # import du module (pas de ses classes) : ses tests ne sont pas relancés ici
from commun import DOSSIER_DEMO, RACINE, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

SCENARIOS = scenarios_demo()
GAMME_MENSUELLE = SCENARIOS["gamme_mensuelle_echue"]       # date, 30 jours, échue sans OT ouvert (CV-01)
GAMME_COMPTEUR = SCENARIOS["gamme_compteur_sans_ot"]       # compteur horaire de CP-01, pas encore échue
GAMME_SEUIL = SCENARIOS["gamme_seuil"]                     # seuil de perte de charge de CP-01
COMPTEUR_SEUIL = SCENARIOS["compteur_seuil"]
KIT = SCENARIOS["kit_garniture"]
OT_EN_COURS = SCENARIOS["ot_statut_en_cours"]              # OT ouvert : on peut lui imputer des sorties
TECHNICIEN = SCENARIOS["technicien_br_valide"]
EQ_CAUSES = SCENARIOS["causes_equipement"]                 # PO-02 : au moins 5 fuites
SYMPTOME_CAUSES = SCENARIOS["causes_equipement_symptome"]
EQ_INSUFFISANT = SCENARIOS["causes_insuffisantes"]         # PO-03 : de 1 à 4 cas
SYMPTOME_INSUFFISANT = SCENARIOS["causes_insuffisantes_symptome"]
DI_CAUSES = SCENARIOS["di_causes_equipement"]
DI_INSUFFISANTE = SCENARIOS["di_causes_insuffisantes"]
OT_FUITE = SCENARIOS["ot_fuite_garniture_po02"]

STATUTS_FERMES = ("Clôturé techniquement", "Clôturé administrativement", "Annulé")
STATUTS_CLOTURES = ("Clôturé techniquement", "Clôturé administrativement")
MINIMUM_CAUSES = 5
LIEN_A_COMMANDER = "#/magasin?onglet=a-commander"
TOAST_GENERATION = r"^\d+ OT préventifs? générés?\.$"
# Deux postes qui génèrent en même temps : le second voit sa première écriture refusée (409), relit la
# table et n'écrit plus rien. Ce conflit est voulu ; toute autre erreur fait échouer le test.
CONFLIT_GENERATION = re.compile(r"status of 409.*/api/csv/(ordres_travail|ot_operations)")

# Chaque toast affiché est noté au moment où il s'affiche (il est masqué au bout de 4 s : le lire
# après coup échouerait au hasard). Un même texte affiché deux fois de suite (trois « Générer les OT
# échus » d'affilée) est noté deux fois : chaque affichage remplit de nouveau la zone (childList).
NOTER_TOASTS_JS = """(() => {
  window.__toasts = [];
  new MutationObserver((mutations) => {
    const zone = document.getElementById('toast');
    if (!zone || !zone.classList.contains('visible')) return;
    if (mutations.some((m) => m.type === 'childList' && (m.target === zone || zone.contains(m.target)))) {
      window.__toasts.push(zone.textContent.trim());
    }
  }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class'] });
})();"""

# Ligne d'une gamme dans la liste du Préventif (colonnes repérées par la clé de tri de leur en-tête).
LIGNE_GAMME_JS = """(gamme) => {
  const table = document.querySelector('.pv-liste-tableau table');
  if (!table || !table.tHead) return null;
  const entetes = Array.from(table.tHead.rows[0].cells);
  const colonne = (cle) => entetes.findIndex((th) => th.querySelector("button.tri[data-cle='" + cle + "']"));
  const ligne = Array.from(table.tBodies[0].rows).find((r) => r.querySelector('a[href="#/preventif/gamme/' + gamme + '"]'));
  if (!ligne) return null;
  const badge = ligne.cells[colonne('statut')].querySelector('.badge.statut');
  return {
    echeance: ligne.cells[colonne('echeance')].textContent.replace(/\\s+/g, ' ').trim(),
    derniere: ligne.cells[colonne('derniere')].textContent.trim(),
    statut: badge ? badge.textContent.trim() : null,
    ots: Array.from(ligne.querySelectorAll('a[href^="#/ot/"]')).map((a) => decodeURIComponent(a.getAttribute('href').slice(5))),
  };
}"""

# Encart « Causes fréquentes » sous un sélecteur : titre, lignes, liens vers les OT, mention.
LIRE_ENCART_JS = """(selecteur) => {
  const encart = document.querySelector(selecteur);
  if (!encart) return null;
  return {
    titre: encart.querySelector('h3') ? encart.querySelector('h3').textContent.trim() : null,
    texte: encart.textContent.replace(/\\s+/g, ' ').trim(),
    lignes: Array.from(encart.querySelectorAll('li')).map((li) => li.textContent.replace(/\\s+/g, ' ').trim()),
    liens_ot: Array.from(encart.querySelectorAll('a[href^="#/ot"]')).map((a) => a.getAttribute('href')),
    mention: encart.querySelector('.note') ? encart.querySelector('.note').textContent.trim() : null,
  };
}"""


# ---------------------------------------------------------------------------
# CSV (copie du serveur ou donnees/demo) et calculs de référence en Python
# ---------------------------------------------------------------------------

def lire(dossier, nom):
    """Lignes d'un CSV de Prévo (BOM, « ; ») en dictionnaires, apostrophe de protection retirée."""
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return [{cle: lot1.brut(valeur) for cle, valeur in ligne.items()}
            for ligne in csv.DictReader(io.StringIO(texte), delimiter=";")]


def par_id(dossier, nom):
    return {ligne["id"]: ligne for ligne in lire(dossier, nom)}


def nombre(valeur):
    try:
        return float(re.sub(r"[\s  ]", "", str(valeur)).replace(",", "."))
    except ValueError:
        return None


def texte_nombre(valeur):
    """Nombre tel que l'écrit un message de Prévo : '3', '2,5'."""
    return str(int(valeur)) if float(valeur).is_integer() else str(valeur).replace(".", ",")


def date_fr(jour):
    return jour.strftime("%d/%m/%Y")


def stock_python(mouvements, article_id):
    """Stock recalculé (date puis identifiant) : un inventaire fixe la valeur, entrée et retour
    ajoutent, une sortie retire (comme Donnees.stockArticle)."""
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


def article_au_dessus_du_point(dossier):
    """Article actif sans achat en cours dont le stock dépasse son point de commande du plus petit
    écart : (article, stock, écart). Le sortir de `écart` l'amène à son point de commande."""
    mouvements = lire(dossier, "mouvements_stock.csv")
    achats_en_cours = {a["article_id"] for a in lire(dossier, "achats.csv") if a["statut"] in ("demandée", "commandée")}
    candidats = []
    for article in lire(dossier, "articles.csv"):
        point = nombre(article["point_commande"]) if article["point_commande"] else None
        if article["actif"] == "0" or point is None or article["id"] in achats_en_cours:
            continue
        stock = stock_python(mouvements, article["id"])
        if stock > point and float(stock - point).is_integer():
            candidats.append((stock - point, article["id"], article, stock))
    candidats.sort(key=lambda c: (c[0], c[1]))
    ecart, _, article, stock = candidats[0]
    return article, stock, ecart


def ots_ouverts_de(dossier, gamme_id):
    return [ot for ot in lire(dossier, "ordres_travail.csv")
            if ot["gamme_id"] == gamme_id and ot["statut"] not in STATUTS_FERMES]


def cas_causes(dossier, equipement_id, symptome):
    """(portée, cas) selon la règle D25 (ARCHITECTURE.md §14.5), recalculée depuis les CSV : OT
    correctifs clôturés de ce symptôme avec une cause ; cet équipement s'il a au moins 5 cas, sinon
    les équipements de même marque et modèle (casse et espaces ignorés) ; sinon portée None."""
    def cle(valeur):
        return re.sub(r"\s+", "", valeur or "").lower()

    cas = [ot for ot in lire(dossier, "ordres_travail.csv")
           if ot["type"].startswith("correctif") and ot["statut"] in STATUTS_CLOTURES
           and ot["symptome_code"] == symptome and ot["cause_code"].strip()]
    propres = [ot for ot in cas if ot["equipement_id"] == equipement_id]
    if len(propres) >= MINIMUM_CAUSES:
        return "equipement", propres
    equipements = lire(dossier, "equipements.csv")
    equipement = next(e for e in equipements if e["id"] == equipement_id)
    if not equipement["marque"].strip() or not equipement["modele"].strip():
        return None, propres
    memes = {e["id"] for e in equipements
             if cle(e["marque"]) == cle(equipement["marque"]) and cle(e["modele"]) == cle(equipement["modele"])}
    du_modele = [ot for ot in cas if ot["equipement_id"] in memes]
    return ("modele" if len(du_modele) >= MINIMUM_CAUSES else None), du_modele


def ecart_en_mois(debut, fin):
    return (fin.year * 12 + fin.month) - (debut.year * 12 + debut.month)


# ---------------------------------------------------------------------------
# Gestes communs du lot 2 (s'ajoutent à ceux du lot 1 : profil, menu, onglets, statut d'un OT)
# ---------------------------------------------------------------------------

class OutilsLot2:
    """Mélangé à une classe de test de la recette du lot 1 (lot1.CasRecette ou une de ses filles)."""

    def setUp(self):
        super().setUp()
        self.contexte.add_init_script(NOTER_TOASTS_JS)

    # -- navigation, toasts -------------------------------------------------------------------

    def aller(self, route, page=None):
        """Change de route dans la page, comme un lien (sans rechargement)."""
        (page or self.page).evaluate("(route) => { location.hash = route; }", route)

    def nombre_toasts(self, page=None):
        return (page or self.page).evaluate("(window.__toasts || []).length")

    def attendre_toast_note(self, motif, depuis=0, page=None):
        """Texte du premier toast affiché (depuis le n-ième) qui correspond à `motif` (expression régulière)."""
        return (page or self.page).wait_for_function(
            "([motif, n]) => (window.__toasts || []).slice(n).find((t) => new RegExp(motif).test(t)) || null",
            arg=[motif, depuis]).json_value()

    def avec_toast(self, motif, action):
        """Lance action() puis attend un NOUVEAU toast qui correspond à `motif` ; renvoie son texte."""
        avant = self.nombre_toasts()
        action()
        return self.attendre_toast_note(motif, avant)

    # -- fiche OT -----------------------------------------------------------------------------

    def ouvrir_ot(self, ot_id):
        self.aller("#/ot/" + ot_id)
        self.attendre_fiche_ot(ot_id)

    def transition(self, cible, zone=".ot-actions"):
        self.page.click("%s button[data-action='transition'][data-cible='%s']" % (zone, cible))

    def sortir_depuis_l_ot(self, article_id, quantite):
        """Bloc « Pièces sorties » (onglet Exécution) : sortie de `quantite` × article, réussie."""
        page = self.page
        self.onglet("execution")
        page.wait_for_selector("#ot-bloc-sorties #form-sortie")
        page.select_option("#ot-sortie-article", article_id)
        page.fill("#ot-sortie-quantite", texte_nombre(quantite))
        texte = self.avec_toast("^Sortie enregistrée", lambda: page.click("#form-sortie button[type=submit]"))
        page.wait_for_selector("#ot-bloc-sorties tr[data-article='%s'] button.ot-retourner" % article_id)
        return texte

    def message_sorties(self, extrait):
        """Message du bloc « Pièces sorties » une fois qu'il contient `extrait`."""
        return self.page.wait_for_function(
            """(extrait) => { const zone = document.querySelector('#ot-bloc-sorties .ot-sorties-message');
                const texte = zone ? zone.innerText.trim() : '';
                return texte.includes(extrait) ? texte : null; }""", arg=extrait).json_value()

    def executer_et_cloturer(self, ot_id, cause, remede):
        """OT préventif ouvert (fiche affichée) mené par l'interface jusqu'à la clôture technique :
        technicien habilité, Préparé, Planifié, Démarrer, temps passé, date de fin « Maintenant »,
        compte rendu complet, « Clôturer techniquement ». Renvoie la date de fin (date)."""
        page = self.page
        self.onglet("preparation")
        page.select_option("#form-preparation [name=technicien_id]", TECHNICIEN)
        self.transition("Préparé", ".ot-actions-preparation")
        self.attendre_statut("Préparé")
        self.transition("Planifié", ".ot-actions-preparation")
        self.attendre_statut("Planifié")
        self.onglet("execution")
        self.avec_toast("^" + re.escape(ot_id + " : En cours."), lambda: self.transition("En cours", ".ot-demarrer"))
        self.onglet("execution")
        page.fill("#ot-temps-heures", "1")
        self.avec_toast("^Temps ajouté", lambda: page.click("#form-temps button[type=submit]"))
        self.onglet("execution")
        page.click("#form-execution .ot-maintenant")
        fin = datetime.date.fromisoformat(page.input_value("#form-execution [name=date_fin]")[:10])
        self.avec_toast("^Exécution enregistrée", lambda: page.click("#form-execution button[type=submit]"))
        self.onglet("compte-rendu")
        page.select_option("#form-compte-rendu [name=cause_code]", cause)
        page.select_option("#form-compte-rendu [name=remede_code]", remede)
        page.fill("#form-compte-rendu [name=compte_rendu]", "Contrôle mensuel réalisé : tension de bande réglée, rouleaux graissés.")
        page.check("#form-compte-rendu [name=remise_service]")
        self.avec_toast("^" + re.escape(ot_id + " : Clôturé techniquement."),
                        lambda: self.transition("Clôturé techniquement", "#form-compte-rendu"))
        self.attendre_statut("Clôturé techniquement")
        self.assertEqual(page.locator("#ot-message .alerte").count(), 0)
        return fin

    # -- Préventif, Magasin, Accueil ---------------------------------------------------------------

    def liste_des_gammes(self):
        """Ouvre la liste des gammes par le menu (depuis un autre écran)."""
        self.menu("preventif")
        self.page.wait_for_selector(".pv-liste-tableau tbody tr a[href^='#/preventif/gamme/']")

    def ligne_gamme(self, gamme_id, page=None):
        return (page or self.page).evaluate(LIGNE_GAMME_JS, gamme_id)

    def fiche_article(self, article_id, reference):
        """Ouvre la fiche d'un article et renvoie le stock affiché (nombre)."""
        page = self.page
        self.aller("#/magasin/article/" + article_id)
        page.wait_for_function("""(ref) => { const t = document.querySelector('.magasin-fiche h1');
            return t && t.textContent.includes(ref) && document.getElementById('magasin-stock'); }""", arg=reference)
        texte = page.inner_text("#magasin-stock")
        trouve = re.match(r"\s*(-?[\d\s  ]+(?:,\d+)?)", texte)
        self.assertIsNotNone(trouve, texte)
        return nombre(trouve.group(1))

    def panneau_a_commander(self):
        """Texte de l'onglet « À commander » du magasin (ouvert depuis un autre écran)."""
        page = self.page
        self.aller(LIEN_A_COMMANDER)
        panneau = ".magasin-onglets .panneau-onglet[data-onglet='a-commander']"
        page.wait_for_selector(".magasin-onglets .onglet[data-onglet='a-commander'][aria-selected='true']")
        page.wait_for_selector(panneau + " .magasin-liste")
        return page.inner_text(panneau)

    def compteur_accueil(self, lien):
        """Chiffre d'un indicateur de l'accueil (ouvert depuis un autre écran)."""
        self.aller("#/accueil")
        selecteur = '#contenu .instruments a[href="%s"] .chiffre' % lien
        self.page.wait_for_selector(selecteur)
        return int(self.page.inner_text(selecteur))

    def verifier_ecran(self, contexte, page=None):
        """360 px : aucun défilement horizontal, toutes les zones tactiles de #contenu ≥ 48 px."""
        page = page or self.page
        self.sans_defilement_horizontal(contexte, page)
        self.assertEqual(page.evaluate(lot1.PETITES_ZONES_JS), [], "zones tactiles < 48 px : " + contexte)


class CasRecette2(OutilsLot2, lot1.CasRecette):
    """Base des scénarios du lot 2."""


# ---------------------------------------------------------------------------
# 1. Panne sur pompe avec la sortie du kit depuis l'OT (serveur, démo)
# ---------------------------------------------------------------------------

class TestRecette2Pompe(OutilsLot2, lot1.TestRecettePompe):
    """Le parcours du lot 1 (lot1.TestRecettePompe.jouer : DI, acceptation P2, préparation avec le kit,
    planification, démarrage, SORTIE DU KIT depuis l'onglet Exécution, temps, clôtures, historique de
    PO-02), vérifié ici du côté du magasin."""

    def verifier_fiche_du_kit(self, ot_id, stock_attendu):
        """Fiche de l'article : stock −1 et la sortie de l'OT parmi ses mouvements."""
        reference = par_id(DOSSIER_DEMO, "articles.csv")[KIT]["reference"]
        self.assertEqual(self.fiche_article(KIT, reference), stock_attendu)
        mouvements = ".magasin-mouvements-article"
        self.page.wait_for_selector(mouvements)
        self.assertGreaterEqual(self.page.locator(mouvements + " a[href='#/ot/%s']" % ot_id).count(), 1)

    def test_pompe_serveur(self):
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            stock_avant = nombre(par_id(dossier, "articles.csv")[KIT]["stock"])
            self.assertEqual(stock_avant, stock_python(lire(dossier, "mouvements_stock.csv"), KIT))
            self.assertGreaterEqual(stock_avant, 1)
            mouvements_avant = set(par_id(dossier, "mouvements_stock.csv"))

            numero, ot_id = self.jouer(serveur)

            # Disque : un seul nouveau mouvement, la sortie du kit imputée à l'OT ; colonne stock −1
            nouveaux = [m for m in lire(dossier, "mouvements_stock.csv") if m["id"] not in mouvements_avant]
            self.assertEqual([(m["type"], m["article_id"], m["quantite"], m["ot_id"], m["utilisateur"]) for m in nouveaux],
                             [("sortie", KIT, "1", ot_id, "Responsable")])
            self.assertEqual(nombre(par_id(dossier, "articles.csv")[KIT]["stock"]), stock_avant - 1)
            self.assertEqual(stock_python(lire(dossier, "mouvements_stock.csv"), KIT), stock_avant - 1)
            # L'OT de la pompe, clôturé, est dans son historique (vérifié à l'écran par jouer())
            ot = par_id(dossier, "ordres_travail.csv")[ot_id]
            self.assertEqual((ot["equipement_id"], ot["di_id"], ot["statut"]), (lot1.POMPE, numero, "Clôturé administrativement"))
            self.verifier_fiche_du_kit(ot_id, stock_avant - 1)

    def test_pompe_demo(self):
        stock_avant = stock_python(lire(DOSSIER_DEMO, "mouvements_stock.csv"), KIT)
        numero, ot_id = self.jouer()
        self.assertEqual(self.page.evaluate("App.mode"), "demo")
        self.assertEqual(self.stock_kit, (stock_avant, stock_avant - 1))
        self.verifier_fiche_du_kit(ot_id, stock_avant - 1)


# ---------------------------------------------------------------------------
# 2. Gamme mensuelle échue, gammes compteur et seuil (serveur, démo)
# ---------------------------------------------------------------------------

class TestRecette2Gamme(CasRecette2):

    def codes_cloture(self, dossier):
        """Premiers codes cause et remède du jeu (un préventif n'a pas de cause « usure » particulière)."""
        codes = lire(dossier, "codes_defaillance.csv")
        return (sorted(c["code"] for c in codes if c["famille"] == "cause")[0],
                sorted(c["code"] for c in codes if c["famille"] == "remède")[0])

    def verifier_un_seul_ot(self, ot_id):
        """Liste du Préventif : la gamme a un OT ouvert, et un seul : celui-ci."""
        ligne = self.ligne_gamme(GAMME_MENSUELLE)
        self.assertIsNotNone(ligne)
        self.assertEqual((ligne["statut"], ligne["ots"]), ("OT ouvert", [ot_id]))

    def cloturer_et_verifier_l_echeance(self, ot_id, dossier):
        """Depuis la liste du Préventif : lien de l'OT → exécution et clôture technique par l'interface
        → la liste montre l'échéance au mois suivant. Renvoie (date de fin, échéance)."""
        page = self.page
        ligne = page.locator(".pv-liste-tableau tbody tr:has(a[href='#/preventif/gamme/%s'])" % GAMME_MENSUELLE)
        ligne.locator("a[href='#/ot/%s']" % ot_id).click()
        self.attendre_fiche_ot(ot_id)
        self.assertEqual(self.statut_ot(), "Créé")
        fin = self.executer_et_cloturer(ot_id, *self.codes_cloture(dossier))
        periodicite = int(par_id(dossier, "gammes.csv")[GAMME_MENSUELLE]["periodicite_jours"])
        self.assertTrue(28 <= periodicite <= 31, periodicite)               # gamme mensuelle
        echeance = fin + datetime.timedelta(days=periodicite)

        self.liste_des_gammes()
        ligne = self.ligne_gamme(GAMME_MENSUELLE)
        self.assertNotEqual(ligne["statut"], "OT ouvert")
        self.assertIn(ligne["statut"], ("À jour", "Bientôt"))
        self.assertEqual(ligne["ots"], [])
        self.assertEqual(ligne["derniere"], date_fr(fin))
        self.assertEqual(ligne["echeance"], date_fr(echeance))
        # « Le mois suivant » : 30 jours après la fin (sauf fin un 30 ou 31 janvier, qui saute février).
        if not (fin.month == 1 and fin.day >= 30):
            self.assertEqual(ecart_en_mois(fin, echeance), 1, (fin, echeance))
        print("\n  [gamme] %s réalisé le %s -> échéance affichée %s" % (ot_id, date_fr(fin), ligne["echeance"]))
        return fin, echeance

    def test_gamme_serveur_un_seul_ot_apres_trois_rechargements_puis_cloture_echeance_au_mois_suivant(self):
        page = self.page
        preregler_profil(self.contexte, "responsable")
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.assertEqual(ots_ouverts_de(dossier, GAMME_MENSUELLE), [])      # échue, aucun OT avant l'ouverture
            page.goto(serveur.url + "/#/preventif")
            attendre_pret(page)
            self.attendre_toast_note(TOAST_GENERATION)
            page.wait_for_selector(".pv-liste-tableau tbody tr")
            ouverts = ots_ouverts_de(dossier, GAMME_MENSUELLE)
            self.assertEqual(len(ouverts), 1, ouverts)
            ot_id = ouverts[0]["id"]
            self.assertEqual((ouverts[0]["origine"], ouverts[0]["statut"]), ("préventif", "Créé"))
            self.verifier_un_seul_ot(ot_id)

            for rechargement in range(1, 4):
                with self.subTest(rechargement=rechargement):
                    page.reload()
                    attendre_pret(page)
                    page.wait_for_selector(".pv-liste-tableau tbody tr")
                    self.assertEqual([o["id"] for o in ots_ouverts_de(dossier, GAMME_MENSUELLE)], [ot_id])
                    self.verifier_un_seul_ot(ot_id)

            fin, echeance = self.cloturer_et_verifier_l_echeance(ot_id, dossier)
            gamme = par_id(dossier, "gammes.csv")[GAMME_MENSUELLE]
            self.assertEqual((gamme["derniere_realisation"], gamme["prochaine_echeance"]), (fin.isoformat(), echeance.isoformat()))
            self.assertEqual(par_id(dossier, "ordres_travail.csv")[ot_id]["statut"], "Clôturé techniquement")
            self.assertEqual(ots_ouverts_de(dossier, GAMME_MENSUELLE), [])

    def test_gamme_serveur_deux_postes_ouverts_ensemble_un_seul_ot(self):
        self.autoriser_erreur(CONFLIT_GENERATION)
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.assertEqual(ots_ouverts_de(dossier, GAMME_MENSUELLE), [])
            pages = []
            for profil, technicien in (("technicien", TECHNICIEN), ("responsable", "")):
                contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
                self.addCleanup(contexte.close)
                contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
                preregler_profil(contexte, profil, technicien_id=technicien, poste="Poste " + profil)
                page = contexte.new_page()
                self.surveiller(page)
                pages.append(page)
            for page in pages:                                   # les deux postes s'ouvrent ensemble
                page.goto(serveur.url + "/#/preventif", wait_until="commit")
            for page in pages:
                attendre_pret(page)
                page.wait_for_load_state("networkidle")
            ouverts = ots_ouverts_de(dossier, GAMME_MENSUELLE)
            self.assertEqual(len(ouverts), 1, ouverts)
            for page in pages:                                   # chaque poste voit le même et seul OT
                page.reload()
                attendre_pret(page)
                page.wait_for_selector(".pv-liste-tableau tbody tr")
                ligne = self.ligne_gamme(GAMME_MENSUELLE, page)
                self.assertEqual((ligne["statut"], ligne["ots"]), ("OT ouvert", [ouverts[0]["id"]]))
            self.assertEqual(len(ots_ouverts_de(dossier, GAMME_MENSUELLE)), 1)
            operations = [o for o in lire(dossier, "ot_operations.csv") if o["ot_id"] == ouverts[0]["id"]]
            self.assertEqual(len(operations), len([o for o in lire(dossier, "gamme_operations.csv") if o["gamme_id"] == GAMME_MENSUELLE]))

    def test_gamme_demo_un_seul_ot_apres_trois_generer_puis_cloture_echeance_au_mois_suivant(self):
        page = self.page
        self.demarrer_demo_sans_profil()
        self.choisir_profil("responsable")
        self.attendre_toast_note(TOAST_GENERATION)                       # génération à l'ouverture
        self.liste_des_gammes()
        ligne = self.ligne_gamme(GAMME_MENSUELLE)
        self.assertEqual(ligne["statut"], "OT ouvert")
        self.assertEqual(len(ligne["ots"]), 1, ligne)
        ot_id = ligne["ots"][0]
        ouverts = "(g) => Donnees.lignes('ordres_travail').filter((o) => o.gamme_id === g && !%r.includes(o.statut)).map((o) => o.id)" % list(STATUTS_FERMES)
        for essai in range(1, 4):
            with self.subTest(generer=essai):
                page.evaluate("document.getElementById('pv-generer').dataset.avant = '1'")
                texte = self.avec_toast(".", lambda: page.click("#pv-generer"))
                self.assertEqual(texte, "Aucune gamme échue.")
                page.wait_for_selector("#pv-generer:not([data-avant])")          # liste réaffichée
                self.verifier_un_seul_ot(ot_id)
                self.assertEqual(page.evaluate(ouverts, GAMME_MENSUELLE), [ot_id])
        fin, echeance = self.cloturer_et_verifier_l_echeance(ot_id, DOSSIER_DEMO)
        gamme = page.evaluate("(g) => Donnees.trouver('gammes', g)", GAMME_MENSUELLE)
        self.assertEqual((gamme["derniere_realisation"], gamme["prochaine_echeance"]), (fin.isoformat(), echeance.isoformat()))
        self.assertEqual(page.evaluate(ouverts, GAMME_MENSUELLE), [])

    def test_gamme_serveur_compteur_seuil_releves_saisis_depuis_la_fiche_equipement(self):
        page = self.page
        preregler_profil(self.contexte, "responsable")
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            gammes = par_id(dossier, "gammes.csv")
            compteur, seuil = gammes[GAMME_COMPTEUR], gammes[GAMME_SEUIL]
            self.assertEqual((compteur["declencheur"], seuil["declencheur"], seuil["compteur_id"]), ("compteur", "seuil", COMPTEUR_SEUIL))
            self.assertEqual(compteur["equipement_id"], seuil["equipement_id"])            # CP-01
            equipement = compteur["equipement_id"]
            self.assertEqual((ots_ouverts_de(dossier, GAMME_COMPTEUR), ots_ouverts_de(dossier, GAMME_SEUIL)), ([], []))
            releves = lire(dossier, "releves.csv")
            dernier = max((r for r in releves if r["compteur_id"] == compteur["compteur_id"]), key=lambda r: (r["date"], r["id"]))
            atteint = nombre(compteur["releve_derniere_realisation"]) + nombre(compteur["periodicite_unites"])
            self.assertGreater(atteint, nombre(dernier["valeur"]))          # pas une baisse : aucun avertissement

            page.goto(serveur.url + "/#/equipement/" + equipement)
            attendre_pret(page)
            page.wait_for_selector("#contenu .parc-preventif li[data-gamme='%s']" % GAMME_SEUIL)
            for gamme_id, compteur_id, valeur, type_ot in (
                    (GAMME_COMPTEUR, compteur["compteur_id"], texte_nombre(atteint), "préventif systématique"),
                    (GAMME_SEUIL, COMPTEUR_SEUIL, texte_nombre(round(nombre(seuil["seuil"]) + 0.05, 2)), "préventif conditionnel")):
                with self.subTest(gamme=gamme_id):
                    self.assertNotEqual(page.get_attribute(".parc-preventif li[data-gamme='%s']" % gamme_id, "data-statut"), "ot_ouvert")
                    page.click(".parc-saisir-releve[data-compteur='%s']" % compteur_id)
                    page.wait_for_selector("dialog.dialogue .parc-formulaire-releve")
                    page.fill("dialog.dialogue [name=valeur]", valeur)
                    texte = self.avec_toast("^Relevé enregistré",
                                            lambda: page.click("dialog.dialogue button:has-text('Enregistrer le relevé')"))
                    page.wait_for_selector("dialog.dialogue", state="detached")
                    self.assertRegex(texte, r"^Relevé enregistré\. \d+ OT préventifs? générés?\.$")
                    ouverts = ots_ouverts_de(dossier, gamme_id)
                    self.assertEqual(len(ouverts), 1, ouverts)
                    self.assertEqual((ouverts[0]["origine"], ouverts[0]["type"], ouverts[0]["statut"], ouverts[0]["equipement_id"]),
                                     ("préventif", type_ot, "Créé", equipement))
                    # La carte Préventif de la fiche montre l'OT ouvert, avec son lien
                    page.wait_for_selector(".parc-preventif li[data-gamme='%s'][data-statut='ot_ouvert'] a.parc-lien-ot[href='#/ot/%s']"
                                           % (gamme_id, ouverts[0]["id"]))
            self.assertEqual(len(ots_ouverts_de(dossier, GAMME_COMPTEUR)), 1)
            page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# 3. Stock : sortie refusée, point de commande, achat, inventaire (serveur, démo)
# ---------------------------------------------------------------------------

class TestRecette2Stock(CasRecette2):

    def jouer_stock(self, reference, serveur=None):
        """reference : dossier dont les CSV décrivent l'état de départ (copie du serveur ou donnees/demo)."""
        page = self.page
        articles = par_id(reference, "articles.csv")
        stock_kit = stock_python(lire(reference, "mouvements_stock.csv"), KIT)
        self.assertEqual(self.fiche_article(KIT, articles[KIT]["reference"]), stock_kit)

        # --- Sortie qui rendrait le stock négatif : refusée, message RG6, stock inchangé ---
        octets = {}
        if serveur:
            octets = {nom: (serveur.dossier / nom).read_bytes() for nom in ("mouvements_stock.csv", "articles.csv")}
        self.ouvrir_ot(OT_EN_COURS)
        self.onglet("execution")
        page.wait_for_selector("#ot-bloc-sorties #form-sortie")
        self.assertIn("stock %s" % texte_nombre(stock_kit), page.inner_text("#ot-sortie-article option[value='%s']" % KIT))
        lignes_avant = page.inner_text("#ot-bloc-sorties table")
        page.select_option("#ot-sortie-article", KIT)
        page.fill("#ot-sortie-quantite", texte_nombre(stock_kit + 1))
        page.click("#form-sortie button[type=submit]")
        self.assertEqual(self.message_sorties("Stock insuffisant"),
                         "Stock insuffisant : %s en stock, %s demandé" % (texte_nombre(stock_kit), texte_nombre(stock_kit + 1)))
        self.assertEqual(page.inner_text("#ot-bloc-sorties table"), lignes_avant)
        self.assertEqual(self.fiche_article(KIT, articles[KIT]["reference"]), stock_kit)
        for nom, contenu in octets.items():
            self.assertEqual((serveur.dossier / nom).read_bytes(), contenu, nom + " ne doit pas changer")

        # --- Sortie qui amène un article à son point de commande : « À commander », accueil +1 ---
        article, stock, ecart = article_au_dessus_du_point(reference)
        point = nombre(article["point_commande"])
        self.assertEqual(self.fiche_article(article["id"], article["reference"]), stock)
        a_commander_avant = self.compteur_accueil(LIEN_A_COMMANDER)
        self.assertNotIn(article["reference"], self.panneau_a_commander())
        self.ouvrir_ot(OT_EN_COURS)
        texte = self.sortir_depuis_l_ot(article["id"], ecart)
        self.assertIn(OT_EN_COURS, texte)
        a_commander = self.panneau_a_commander()
        self.assertIn(article["reference"], a_commander)
        self.assertIn("Demander l'achat", a_commander)
        self.assertEqual(self.fiche_article(article["id"], article["reference"]), point)
        self.assertEqual(self.compteur_accueil(LIEN_A_COMMANDER), a_commander_avant + 1)
        print("\n  [stock] %s : %s -> %s (point de commande), « À commander » à l'accueil : %d -> %d"
              % (article["reference"], texte_nombre(stock), texte_nombre(point), a_commander_avant, a_commander_avant + 1))
        return article, point

    def test_stock_serveur_sortie_negative_refusee_puis_point_de_commande(self):
        preregler_profil(self.contexte, "responsable")
        with ServeurPrevo() as serveur:
            self.page.goto(serveur.url + "/#/accueil")
            attendre_pret(self.page)
            self.page.wait_for_load_state("networkidle")
            mouvements_avant = set(par_id(serveur.dossier, "mouvements_stock.csv"))
            article, point = self.jouer_stock(serveur.dossier, serveur)
            nouveaux = [m for m in lire(serveur.dossier, "mouvements_stock.csv") if m["id"] not in mouvements_avant]
            self.assertEqual([(m["type"], m["article_id"], m["ot_id"]) for m in nouveaux], [("sortie", article["id"], OT_EN_COURS)])
            self.assertEqual(nombre(par_id(serveur.dossier, "articles.csv")[article["id"]]["stock"]), point)

    def test_stock_demo_sortie_negative_refusee_puis_point_de_commande(self):
        self.demarrer_demo_sans_profil()
        self.choisir_profil("responsable")
        article, point = self.jouer_stock(DOSSIER_DEMO)
        self.assertEqual(self.page.evaluate("(a) => Donnees.stockArticle(a)", article["id"]), point)

    def test_achat_serveur_demande_commande_reception_puis_inventaire(self):
        page = self.page
        preregler_profil(self.contexte, "responsable")
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            page.goto(serveur.url + "/#/accueil")
            attendre_pret(page)
            page.wait_for_load_state("networkidle")
            article, stock, ecart = article_au_dessus_du_point(dossier)
            point = nombre(article["point_commande"])
            self.ouvrir_ot(OT_EN_COURS)
            self.sortir_depuis_l_ot(article["id"], ecart)                 # l'article tombe à son point de commande
            a_commander = self.compteur_accueil(LIEN_A_COMMANDER)
            self.assertIn(article["reference"], self.panneau_a_commander())

            # « Demander l'achat » (quantité proposée), dans l'onglet « À commander »
            page.click("button[data-action='demander-achat'][data-article='%s']" % article["id"])
            page.wait_for_selector("dialog [name=quantite]")
            proposee = nombre(page.input_value("dialog [name=quantite]"))
            self.assertGreater(proposee, 0)
            self.avec_toast("Demande d'achat", lambda: page.click("dialog .fenetre-actions .btn-primaire"))
            achats = [a for a in lire(dossier, "achats.csv") if a["article_id"] == article["id"] and a["statut"] == "demandée"]
            self.assertEqual(len(achats), 1, achats)
            achat = achats[0]
            self.assertEqual((nombre(achat["quantite"]), achat["fournisseur_id"], achat["date"]),
                             (proposee, article["fournisseur_id"], page.evaluate("Donnees.aujourdhui()")))

            # Onglet Achats : « Commander », puis « Réceptionner » la quantité reçue
            self.aller("#/magasin?onglet=achats")
            page.wait_for_selector("button[data-action='commander'][data-achat='%s']" % achat["id"])
            self.avec_toast("commandé", lambda: page.click("button[data-action='commander'][data-achat='%s']" % achat["id"]))
            self.assertEqual(par_id(dossier, "achats.csv")[achat["id"]]["statut"], "commandée")
            recue = 5
            page.click("button[data-action='receptionner'][data-achat='%s']" % achat["id"])
            page.wait_for_selector("dialog [name=quantite_recue]")
            page.fill("dialog [name=quantite_recue]", str(recue))
            self.avec_toast("réceptionné", lambda: page.click("dialog .fenetre-actions .btn-primaire"))
            ligne = par_id(dossier, "achats.csv")[achat["id"]]
            self.assertEqual((ligne["statut"], ligne["date_reception"]), ("reçue", page.evaluate("Donnees.aujourdhui()")))
            entrees = [m for m in lire(dossier, "mouvements_stock.csv") if m["article_id"] == article["id"]
                       and m["type"] == "entrée" and m["commentaire"].startswith("Réception " + achat["id"])]
            self.assertEqual([nombre(m["quantite"]) for m in entrees], [recue])
            self.assertEqual(nombre(par_id(dossier, "articles.csv")[article["id"]]["stock"]), point + recue)
            self.assertEqual(self.fiche_article(article["id"], article["reference"]), point + recue)
            # Réapprovisionné : l'article quitte « À commander », le compteur de l'accueil baisse de 1
            self.assertNotIn(article["reference"], self.panneau_a_commander())
            self.assertEqual(self.compteur_accueil(LIEN_A_COMMANDER), a_commander - 1)

            # Inventaire : stock compté, mouvement « inventaire » en valeur absolue
            compte = point + recue + 2
            self.aller("#/magasin?onglet=inventaire")
            champ = "input[data-inventaire='%s']" % article["id"]
            page.wait_for_selector(champ)
            page.fill(champ, texte_nombre(compte))
            self.assertEqual(page.inner_text("[data-ecart='%s']" % article["id"]).strip(), "+2")
            page.click("#magasin-valider-inventaire")
            page.wait_for_selector("dialog .fenetre-actions .btn-primaire")
            self.avec_toast("Inventaire enregistré", lambda: page.click("dialog .fenetre-actions .btn-primaire"))
            dernier = [m for m in lire(dossier, "mouvements_stock.csv") if m["article_id"] == article["id"]][-1]
            self.assertEqual((dernier["type"], nombre(dernier["quantite"]), dernier["ot_id"]), ("inventaire", compte, ""))
            self.assertEqual(nombre(par_id(dossier, "articles.csv")[article["id"]]["stock"]), compte)
            self.assertEqual(self.fiche_article(article["id"], article["reference"]), compte)


# ---------------------------------------------------------------------------
# 4. Causes fréquentes : fiche DI et fiche OT, trois profils (serveur, démo)
# ---------------------------------------------------------------------------

class TestRecette2Causes(CasRecette2):

    ENCART_DI = ".di-details .causes-frequentes"

    def ouvrir_di(self, di):
        self.aller("#/di/" + di)
        self.page.wait_for_function("""(id) => { const b = document.querySelector('.di-entete-badges b');
            return b !== null && b.textContent === id; }""", arg=di)

    def verifier_encart(self, encart, cas, sans_lien, contexte):
        """≥ 5 cas : titre « … — N cas », une ligne par cause « k cas sur N », mention, liens selon le profil."""
        par_cause = collections.Counter(ot["cause_code"] for ot in cas).most_common()
        self.assertIsNotNone(encart, contexte)
        self.assertEqual(encart["titre"], "Causes fréquentes ici — %d cas" % len(cas), contexte)
        self.assertEqual(len(encart["lignes"]), min(3, len(par_cause)), contexte)
        for rang, ligne in enumerate(encart["lignes"]):
            trouve = re.search(r" — (\d+) cas sur (\d+) ", ligne)
            self.assertIsNotNone(trouve, ligne)
            self.assertEqual((int(trouve.group(1)), int(trouve.group(2))), (par_cause[rang][1], len(cas)), contexte)
        self.assertEqual(encart["mention"], "Statistique de l'historique, pas un diagnostic", contexte)
        if sans_lien:
            self.assertEqual(encart["liens_ot"], [], "liens vers les OT montrés au demandeur")
        else:
            self.assertTrue(encart["liens_ot"], contexte)

    def verifier_encart_insuffisant(self, encart, cas, contexte):
        self.assertIsNotNone(encart, contexte)
        self.assertEqual(encart["texte"], "Pas encore assez de cas pour ce symptôme (%d sur %d)" % (len(cas), MINIMUM_CAUSES), contexte)
        self.assertEqual((encart["titre"], encart["lignes"]), (None, []), contexte)

    def jouer(self, reference):
        page = self.page
        portee, cas = cas_causes(reference, EQ_CAUSES, SYMPTOME_CAUSES)
        self.assertEqual(portee, "equipement")
        portee_insuffisante, insuffisants = cas_causes(reference, EQ_INSUFFISANT, SYMPTOME_INSUFFISANT)
        self.assertIsNone(portee_insuffisante)
        self.assertTrue(1 <= len(insuffisants) < MINIMUM_CAUSES, insuffisants)
        self.assertIn(OT_FUITE, [ot["id"] for ot in cas])
        ot_insuffisant = insuffisants[-1]["id"]
        equipements = par_id(reference, "equipements.csv")
        print("\n  [causes] %s, symptôme %s : %d cas ; %s, symptôme %s : %d cas (moins de %d)"
              % (equipements[EQ_CAUSES]["repere"], SYMPTOME_CAUSES, len(cas),
                 equipements[EQ_INSUFFISANT]["repere"], SYMPTOME_INSUFFISANT, len(insuffisants), MINIMUM_CAUSES))

        for rang, (profil, nom, technicien) in enumerate((("demandeur", "Lucie Martin", ""), ("technicien", "", TECHNICIEN),
                                                          ("responsable", "", ""))):
            with self.subTest(profil=profil):
                if rang == 0:
                    self.choisir_profil(profil, nom, technicien)
                else:
                    self.changer_profil(profil, nom, technicien)
                # Fiche DI : ≥ 5 cas, puis moins de 5 cas
                self.ouvrir_di(DI_CAUSES)
                self.verifier_encart(page.evaluate(LIRE_ENCART_JS, self.ENCART_DI), cas, profil == "demandeur", profil + " DI")
                self.ouvrir_di(DI_INSUFFISANTE)
                self.verifier_encart_insuffisant(page.evaluate(LIRE_ENCART_JS, self.ENCART_DI), insuffisants, profil + " DI")
                if profil == "demandeur":
                    continue                                       # pas d'accès aux OT
                # Fiche OT : Préparation et Compte rendu
                for ot_id, verifier in ((OT_FUITE, lambda e, c: self.verifier_encart(e, cas, False, c)),
                                        (ot_insuffisant, lambda e, c: self.verifier_encart_insuffisant(e, insuffisants, c))):
                    self.ouvrir_ot(ot_id)
                    for onglet in ("preparation", "compte-rendu"):
                        self.onglet(onglet)
                        selecteur = ".panneau-onglet[data-onglet='%s'] .ot-causes .causes-frequentes" % onglet
                        page.wait_for_selector(selecteur)
                        verifier(page.evaluate(LIRE_ENCART_JS, selecteur), "%s %s %s" % (profil, ot_id, onglet))

    def test_causes_serveur_fiche_di_et_fiche_ot_trois_profils(self):
        with ServeurPrevo() as serveur:
            self.demarrer_serveur_sans_profil(serveur)
            self.jouer(serveur.dossier)

    def test_causes_demo_fiche_di_et_fiche_ot_trois_profils(self):
        self.demarrer_demo_sans_profil()
        self.jouer(DOSSIER_DEMO)


# ---------------------------------------------------------------------------
# 5. Anomalie pendant un préventif : DI liée (serveur, démo)
# ---------------------------------------------------------------------------

class TestRecette2Anomalie(CasRecette2):

    SYMPTOME = "Bande qui frotte sur le châssis"

    def jouer(self):
        """Technicien : OT préventif généré à l'ouverture (gamme mensuelle), ouvert depuis le
        Préventif → « Signaler une anomalie (DI liée) » → DI → liens dans les deux sens."""
        page = self.page
        self.choisir_profil("technicien", technicien_id=TECHNICIEN)
        self.liste_des_gammes()
        ot_id = self.ligne_gamme(GAMME_MENSUELLE)["ots"][0]
        page.locator(".pv-liste-tableau tbody tr:has(a[href='#/preventif/gamme/%s']) a[href='#/ot/%s']"
                     % (GAMME_MENSUELLE, ot_id)).click()
        self.attendre_fiche_ot(ot_id)
        self.assertFalse(page.is_checked("#ot-anomalie-constatee"))
        self.assertIn("Aucune demande liée", page.inner_text(".ot-anomalie"))

        page.click("#ot-signaler-anomalie")
        page.wait_for_selector(".di-formulaire")
        self.assertIn(ot_id, page.inner_text(".di-origine"))
        page.fill("input[name=symptome]", self.SYMPTOME)
        page.click("label.tuile:has(input[value='gêne'])")
        page.click(".di-envoyer")
        page.wait_for_selector(".di-numero")
        di = page.inner_text(".di-numero")
        self.assertIn("pendant l'OT préventif " + ot_id, page.inner_text(".di-confirmation"))

        # DI → OT : l'OT est marqué « anomalie constatée » et liste la DI liée
        page.click(".di-confirmation-origine a")
        self.attendre_fiche_ot(ot_id)
        page.wait_for_selector(".ot-di-liees a[href='#/di/%s']" % di)
        self.assertTrue(page.is_checked("#ot-anomalie-constatee"))
        self.assertIn("anomalie constatée", page.inner_text(".ot-badges"))
        self.assertIn(self.SYMPTOME, page.inner_text(".ot-di-liees"))
        # OT → DI : la fiche de la DI renvoie à l'OT d'origine
        page.click(".ot-di-liees a[href='#/di/%s']" % di)
        page.wait_for_selector(".di-lien-origine")
        self.assertEqual(page.get_attribute(".di-lien-origine", "href"), "#/ot/" + ot_id)
        page.click(".di-lien-origine")
        self.attendre_fiche_ot(ot_id)
        return ot_id, di

    def test_anomalie_serveur_di_liee_ot_marque_liens_dans_les_deux_sens(self):
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.demarrer_serveur_sans_profil(serveur)
            ot_id, di = self.jouer()
            demande = par_id(dossier, "demandes.csv")[di]
            self.assertEqual((demande["ot_origine_id"], demande["statut"], demande["symptome"]), (ot_id, "Nouvelle", self.SYMPTOME))
            ot = par_id(dossier, "ordres_travail.csv")[ot_id]
            self.assertEqual((ot["origine"], ot["gamme_id"], ot["anomalie_constatee"]), ("préventif", GAMME_MENSUELLE, "1"))
            self.assertEqual(demande["equipement_id"], ot["equipement_id"])
            journal = [j["action"] for j in lire(dossier, "journal.csv") if j["table"] == "ordres_travail" and j["id_ligne"] == ot_id]
            self.assertTrue(any("anomalie_constatee" in action for action in journal), journal)

    def test_anomalie_demo_di_liee_ot_marque_liens_dans_les_deux_sens(self):
        self.demarrer_demo_sans_profil()
        ot_id, di = self.jouer()
        demande = self.page.evaluate("(id) => Donnees.trouver('demandes', id)", di)
        ot = self.page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", ot_id)
        self.assertEqual((demande["ot_origine_id"], demande["statut"]), (ot_id, "Nouvelle"))
        self.assertEqual((ot["origine"], ot["anomalie_constatee"], ot["equipement_id"]), ("préventif", "1", demande["equipement_id"]))


# ---------------------------------------------------------------------------
# 6. Liste blanche du serveur (serveur)
# ---------------------------------------------------------------------------

class TestRecette2ListeBlanche(CasRecette2):

    INTERDITS = ("/docs/brief-gmao.md", "/README.md", "/LICENSE", "/tests/commun.py", "/tests/test_recette_lot2.py",
                 "/outils/generer_demo.py", "/reference-design/index.html", "/reference-design/style.css",
                 "/docs/ARCHITECTURE.md", "/serveur.py", "/Lancer_GMAO.bat", "/lancer.sh",
                 "/DOCS/ARCHITECTURE.md", "/Serveur.py", "/donnees.csv")
    # Remontées de dossier : refusées dès l'analyse du chemin (400), avant la liste blanche.
    TRAVERSEES = ("/js/../serveur.py", "/css/%2e%2e/serveur.py", "/js/..%2F..%2Fbrief-gmao.md")
    PERMIS = ("/", "/index.html", "/favicon.svg", "/css/style.css", "/js/app.js")

    def obtenir(self, serveur, chemin):
        connexion = http.client.HTTPConnection("127.0.0.1", serveur.port, timeout=10)
        try:
            connexion.putrequest("GET", chemin, skip_accept_encoding=True)
            connexion.endheaders()
            reponse = connexion.getresponse()
            return reponse.status, reponse.read()
        finally:
            connexion.close()

    def test_liste_blanche_serveur_fichiers_du_projet_404_application_fonctionne(self):
        page = self.page
        with ServeurPrevo() as serveur:
            for chemin in self.INTERDITS:
                with self.subTest(chemin=chemin):
                    statut, corps = self.obtenir(serveur, chemin)
                    self.assertEqual(statut, 404, chemin)
                    self.assertNotIn(b"def ", corps)
                    self.assertNotIn(b"# Brief", corps)
            for chemin in self.TRAVERSEES:
                with self.subTest(chemin=chemin):
                    statut, corps = self.obtenir(serveur, chemin)
                    self.assertEqual(statut, 400, chemin)
                    self.assertNotIn(b"def ", corps)
            for chemin in self.PERMIS:
                with self.subTest(chemin=chemin):
                    self.assertEqual(self.obtenir(serveur, chemin)[0], 200, chemin)
            print("\n  [liste_blanche] %d chemins hors liste -> 404 ; %d fichiers de l'application -> 200"
                  % (len(self.INTERDITS), len(self.PERMIS)))

            # L'application fonctionne (aucun fichier hors liste demandé : aucune erreur console)
            self.demarrer_serveur_sans_profil(serveur)
            self.choisir_profil("responsable")
            for ecran, selecteur in (("preventif", ".pv-liste-tableau tbody tr"), ("magasin", ".magasin-onglets .panneau-onglet"),
                                     ("liste-ot", ".ot-liste-tableau tbody tr"), ("parc", "#parc-arbre")):
                self.menu(ecran)
                page.wait_for_selector(selecteur)
            page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# 7. Design : 360 px et 1440 px, aucune erreur console (serveur)
# ---------------------------------------------------------------------------

class TestRecette2Design(CasRecette2):

    NOM_LONG = "Société Industrielle de Maintenance des Trois Vallées et Annexes"

    MESURE_NOM_JS = """() => { const e = document.getElementById('nom-entreprise'); const s = getComputedStyle(e);
        return { hauteur: e.getBoundingClientRect().height, interligne: parseFloat(s.lineHeight),
                 texte: e.textContent, titre: e.title, visible: e.offsetParent !== null }; }"""

    def test_design_serveur_360_px_preventif_magasin_pieces_sorties_et_1440_px(self):
        page = self.page
        page.set_viewport_size({"width": 360, "height": 740})
        preregler_profil(self.contexte, "responsable")
        with ServeurPrevo() as serveur:
            page.goto(serveur.url + "/#/accueil")
            attendre_pret(page)
            page.wait_for_load_state("networkidle")
            self.assertTrue(page.evaluate("UI.estTelephone()"))
            page.wait_for_selector("#contenu .instruments")
            self.assertEqual(page.locator("#carte-connexion").count(), 0, "carte QR affichée sur un téléphone")
            self.verifier_ecran("360 px accueil")

            ecrans = [("#/preventif?onglet=gammes", ".pv-liste-cartes .carte-ligne"),
                      ("#/preventif?onglet=calendrier", ".pv-calendrier .pv-semaine"),
                      ("#/preventif/gamme/" + GAMME_MENSUELLE, ".pv-operations .pv-operation")]
            ecrans += [("#/magasin?onglet=" + onglet, ".magasin-onglets .panneau-onglet[data-onglet='%s'] > *" % onglet)
                       for onglet in ("articles", "mouvements", "inventaire", "a-commander", "achats", "fournisseurs")]
            ecrans += [("#/magasin/article/" + KIT, "#form-article")]
            for route, selecteur in ecrans:
                with self.subTest(largeur=360, route=route):
                    self.aller("#/accueil")                 # chaque écran est ouvert depuis un autre écran
                    page.wait_for_selector("#contenu .instruments")
                    self.aller(route)
                    page.wait_for_selector(selecteur)
                    self.verifier_ecran("360 px " + route)
                    self.assertTrue(page.is_visible(".barre-bas"))

            # Fiche OT, onglet Exécution, bloc « Pièces sorties » avec une sortie (bouton « Retourner »)
            article = page.evaluate("""() => Donnees.lignes('articles').filter((a) => a.actif !== '0')
                .map((a) => a.id).find((id) => Donnees.stockArticle(id) >= 1)""")
            self.ouvrir_ot(OT_EN_COURS)
            self.sortir_depuis_l_ot(article, 1)
            self.onglet("execution")
            page.wait_for_selector("#ot-bloc-sorties button.ot-retourner")
            self.verifier_ecran("360 px fiche OT, pièces sorties")
            page.click("#ot-bloc-sorties button.ot-retourner")
            page.wait_for_selector("dialog .ot-fenetre-retour")
            self.sans_defilement_horizontal("360 px fenêtre de retour")
            for bouton in page.locator("dialog .fenetre-actions button").all():
                self.assertGreaterEqual(bouton.bounding_box()["height"], 47.5)
            page.click("dialog .fenetre-actions .btn-fantome")

            # 1440 px : menu latéral, carte QR présente, nom de l'entreprise (saisi dans les
            # Paramètres) sur deux lignes, nom complet en infobulle
            page.set_viewport_size({"width": 1440, "height": 900})
            self.aller("#/accueil")
            page.wait_for_selector("#carte-connexion", state="visible")
            self.assertTrue(page.is_visible(".menu-lateral"))
            self.menu("parametres")
            page.wait_for_selector("#form-parametres [name=entreprise_nom]")
            page.fill("#form-parametres [name=entreprise_nom]", self.NOM_LONG)
            self.avec_toast("^Paramètres enregistrés", lambda: page.click("#form-parametres button[type=submit]"))
            page.wait_for_function("(n) => document.getElementById('nom-entreprise').textContent === n", arg=self.NOM_LONG)
            mesure = page.evaluate(self.MESURE_NOM_JS)
            self.assertTrue(mesure["visible"], mesure)
            self.assertEqual((mesure["texte"], mesure["titre"]), (self.NOM_LONG, self.NOM_LONG))
            self.assertGreaterEqual(mesure["hauteur"], 2 * mesure["interligne"] - 1, mesure)
            self.assertLessEqual(mesure["hauteur"], 2 * mesure["interligne"] + 1, mesure)
            largeurs = page.evaluate("(() => { const m = document.querySelector('.menu-lateral'); return [m.scrollWidth, m.clientWidth]; })()")
            self.assertLessEqual(largeurs[0], largeurs[1], "le menu déborde : %r" % (largeurs,))
            self.sans_defilement_horizontal("1440 px paramètres")
            parametres = {l["cle"]: l["valeur"] for l in lire(serveur.dossier, "parametres.csv")}
            self.assertEqual(parametres["entreprise_nom"], self.NOM_LONG)
            page.wait_for_load_state("networkidle")
        # Aucune erreur console sur tout le parcours : vérifié par CasNavigateur.tearDown.


if __name__ == "__main__":
    unittest.main()
