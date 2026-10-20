"""Tests du lot 2 du module Ordres de travail (ARCHITECTURE.md §14.3 à §14.6) : pièces sorties et
retours (RG6, coût RG7), anomalie d'un OT préventif et demandes liées, clôture d'un préventif
(mise à jour de la gamme, RG5) et encart des causes fréquentes.

Familles (le nom du test le dit) :
    pieces     : sortie et retour d'un kit garniture sur un OT ouvert de PO-02 (CSV sur le disque),
                 refus RG6 affiché tel quel, coût RG7 = calcul Python depuis les CSV, OT fermé sans bouton ;
    anomalie   : OT préventif généré → « Signaler une anomalie (DI liée) » → DI liée, OT marqué,
                 liens dans les deux sens, mention dans la liste, OT verrouillé en lecture seule ;
    gamme      : OT préventif mené jusqu'à la clôture technique par l'interface → gammes.csv
                 (échec de la mise à jour : clôture gardée, avertissement ; réouverture, reclôture) ;
    encart     : causes fréquentes de la fuite de PO-02 dans Préparation et Compte rendu ;
    technicien : sortie sur son OT ; telephone : 375 px sans défilement horizontal, zones ≥ 48 px.

Aucun numéro d'OT, de DI ou de mouvement du jeu de démo n'est écrit ici : ils viennent de
tests/fixtures/demo-scenarios.json (commun.scenarios_demo) ou des CSV relus.

Lancer depuis la racine du projet (un fichier à la fois) :
    py -m unittest discover -s tests -p "test_ordres_lot2.py" -v
"""
import csv
import datetime
import io
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

SCENARIOS = scenarios_demo()
EQUIPEMENT_PO02 = SCENARIOS["causes_equipement"]            # PO-02, fuites répétées
SYMPTOME_FUITE = SCENARIOS["causes_equipement_symptome"]    # code symptôme des fuites de PO-02
KIT = SCENARIOS["kit_garniture"]                            # kit garniture mécanique PO-02
OT_FUITE = SCENARIOS["ot_fuite_garniture_po02"]             # correctif clôturé de PO-02, 1 kit sorti
GAMME_MENSUELLE = SCENARIOS["gamme_mensuelle_echue"]        # gamme « date » de 30 jours, échue
OT_P1 = SCENARIOS["ot_p1_ouvert"]                           # correctif En cours
OT_CLOTURE = SCENARIOS["ot_statut_cloture_technique"]
OT_ANNULE = SCENARIOS["ot_statut_annule"]
PREVENTIF_VERROUILLE = SCENARIOS["preventif_anomalie"]      # préventif clôturé administrativement, DI liée
TECHNICIEN_BR = SCENARIOS["technicien_br_valide"]

STATUTS_FERMES = ("Clôturé techniquement", "Clôturé administrativement", "Annulé")
STATUTS_VERROUILLES = ("Clôturé administrativement", "Annulé")

# Zones tactiles de #contenu de moins de 48 px de haut (même contrôle que tests/test_recette_lot1.py).
PETITES_ZONES_JS = """() => {
  const petites = [];
  for (const el of document.querySelectorAll('#contenu a, #contenu button, #contenu input, #contenu select, #contenu textarea, #contenu summary')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || el.closest('[hidden]') || el.type === 'hidden') continue;
    const cible = (el.type === 'checkbox' || el.type === 'radio') ? (el.closest('label') || el) : el;
    const hauteur = cible.getBoundingClientRect().height;
    if (hauteur < 47.5) petites.push(el.tagName + ' « ' + (el.textContent || el.value || '').trim().slice(0, 30) + ' » ' + Math.round(hauteur) + ' px');
  }
  return petites;
}"""

# Un toast disparaît au bout de 4 s (son texte devient vide) : chaque toast affiché est noté au
# moment où il s'affiche (même principe que tests/test_preventif.py).
NOTER_TOASTS_JS = """(() => {
  window.__toasts = [];
  let dernier = '';
  new MutationObserver(() => {
    const zone = document.getElementById('toast');
    const texte = zone && zone.classList.contains('visible') ? zone.textContent.trim() : '';
    if (texte && texte !== dernier) window.__toasts.push(texte);
    dernier = texte;
  }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class'] });
})();"""


def lire_csv(dossier, nom):
    """Lignes (dictionnaires) d'un CSV de Prévo sur le disque (UTF-8 avec BOM, « ; »)."""
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def ligne_par_id(dossier, nom, identifiant):
    return next((ligne for ligne in lire_csv(dossier, nom) if ligne["id"] == identifiant), None)


def nombre(valeur):
    try:
        return float(str(valeur).replace(",", "."))
    except ValueError:
        return 0.0


def stock_csv(dossier, article_id):
    return nombre(ligne_par_id(dossier, "articles.csv", article_id)["stock"])


def mouvements_de(dossier, ot_id):
    return [m for m in lire_csv(dossier, "mouvements_stock.csv") if m["ot_id"] == ot_id]


def cout_python(dossier, ot_id):
    """RG7 recalculé depuis les CSV : heures × taux + (sorties − retours) × prix + sous-traitance."""
    taux = {t["id"]: nombre(t["taux_horaire"]) for t in lire_csv(dossier, "techniciens.csv")}
    prix = {a["id"]: nombre(a["prix_unitaire"]) for a in lire_csv(dossier, "articles.csv")}
    heures = sum(nombre(t["heures"]) * taux.get(t["technicien_id"], 0)
                 for t in lire_csv(dossier, "ot_temps.csv") if t["ot_id"] == ot_id)
    pieces = 0.0
    for mouvement in mouvements_de(dossier, ot_id):
        signe = {"sortie": 1, "retour": -1}.get(mouvement["type"], 0)
        pieces += signe * nombre(mouvement["quantite"]) * prix.get(mouvement["article_id"], 0)
    ot = ligne_par_id(dossier, "ordres_travail.csv", ot_id)
    soustraitance = nombre(ot["cout_soustraitance"]) if ot["cout_soustraitance"] else 0.0
    return round(pieces, 2), round(heures + pieces + soustraitance, 2)


def euros_fr(montant):
    """1234.5 → '1 234,50' (comme UI.euro, sans le symbole)."""
    return "{:,.2f}".format(montant).replace(",", " ").replace(".", ",")


def espaces_simples(texte):
    return re.sub(r"[ \xa0]", " ", texte)


def ot_genere_de_la_gamme(dossier, gamme_id):
    """Identifiant de l'OT ouvert de la gamme (créé par la génération à l'ouverture, RG5)."""
    ouverts = [o["id"] for o in lire_csv(dossier, "ordres_travail.csv")
               if o["gamme_id"] == gamme_id and o["statut"] not in STATUTS_FERMES]
    if len(ouverts) != 1:
        raise AssertionError("un seul OT ouvert attendu pour %s : %r" % (gamme_id, ouverts))
    return ouverts[0]


class CasOrdresLot2(CasNavigateur):
    """Outils communs : ouvrir une route avec un profil, piloter la fiche OT."""

    def ouvrir(self, serveur, route, profil="responsable", technicien_id="", largeur=1280):
        self.page.set_viewport_size({"width": largeur, "height": 900})
        preregler_profil(self.contexte, profil, technicien_id=technicien_id)
        self.contexte.add_init_script(NOTER_TOASTS_JS)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        # Les écritures du démarrage (OT préventifs échus générés) sont finies avant d'agir.
        self.page.wait_for_load_state("networkidle")

    def aller(self, route):
        self.page.evaluate("(route) => { location.hash = route; }", route)

    def ouvrir_fiche(self, ot_id):
        self.aller("#/ot/" + ot_id)
        self.page.wait_for_function(
            "(id) => { const n = document.querySelector('.ot-fiche .ot-numero'); return n && n.textContent === id; }", arg=ot_id)

    def onglet(self, identifiant):
        self.page.click(".onglet[data-onglet='%s']" % identifiant)

    def attendre_statut(self, statut):
        self.page.wait_for_function(
            "(s) => { const b = document.querySelector('.ot-badges .badge.statut'); return b && b.textContent === s; }", arg=statut)

    def transition(self, cible, zone=".ot-actions"):
        self.page.click("%s button[data-action='transition'][data-cible='%s']" % (zone, cible))

    def attendre_toast_note(self, motif):
        """Texte du premier toast affiché depuis le chargement qui correspond à `motif` (regex)."""
        return self.page.wait_for_function(
            "motif => (window.__toasts || []).find((texte) => new RegExp(motif).test(texte)) || null",
            arg=motif).json_value()

    def attendre_js(self, expression, argument=None):
        self.page.wait_for_function(expression, arg=argument)

    def message_sorties(self, extrait):
        """Message du bloc « Pièces sorties » une fois qu'il contient `extrait` (le message d'un refus
        précédent peut être encore affiché au moment du clic)."""
        return self.page.wait_for_function(
            """(extrait) => { const zone = document.querySelector('#ot-bloc-sorties .ot-sorties-message');
                const texte = zone ? zone.innerText.trim() : '';
                return texte.includes(extrait) ? texte : null; }""", arg=extrait).json_value()

    def sortir(self, article_id, quantite):
        page = self.page
        page.select_option("#ot-sortie-article", article_id)
        page.fill("#ot-sortie-quantite", quantite)
        page.click("#form-sortie button[type=submit]")

    def retourner(self, article_id, quantite):
        page = self.page
        page.click("#ot-bloc-sorties button.ot-retourner[data-article='%s']" % article_id)
        page.wait_for_selector("dialog .ot-fenetre-retour")
        page.fill("dialog .ot-fenetre-retour [name=quantite]", quantite)
        page.click("dialog .fenetre-actions .btn-primaire")

    def creer_ot_par_l_interface(self, equipement_id, titre, technicien_id=""):
        """Formulaire « Nouvel OT » (responsable) ; renvoie l'identifiant de l'OT créé."""
        page = self.page
        self.aller("#/ot/nouveau?equipement=" + equipement_id)
        page.wait_for_selector("#form-nouvel-ot")
        page.fill("#form-nouvel-ot [name=titre]", titre)
        if technicien_id:
            page.select_option("#form-nouvel-ot [name=technicien_id]", technicien_id)
        page.click("#form-nouvel-ot button[type=submit]")
        page.wait_for_function("location.hash.startsWith('#/ot/OT-')")
        ot_id = page.evaluate("decodeURIComponent(location.hash.slice(5))")
        self.ouvrir_fiche(ot_id)
        return ot_id


# ---------------------------------------------------------------------------
# Pièces sorties et retours (RG6), coût RG7
# ---------------------------------------------------------------------------

class TestPieces(CasOrdresLot2):

    def test_pieces_sortie_retour_refus_rg6_et_cout_rg7(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/ot")
            ot_id = self.creer_ot_par_l_interface(EQUIPEMENT_PO02, "PO-02 — fuite à la garniture (lot 2)")
            stock_avant = stock_csv(dossier, KIT)
            self.assertGreaterEqual(stock_avant, 1)
            self.assertEqual(page.evaluate("(a) => Donnees.stockArticle(a)", KIT), stock_avant)
            prix_kit = nombre(ligne_par_id(dossier, "articles.csv", KIT)["prix_unitaire"])

            # Bloc vide, formulaire de sortie : le kit est proposé avec son stock
            self.onglet("execution")
            page.wait_for_selector("#ot-bloc-sorties #form-sortie")
            self.assertIn("Aucune pièce sortie", page.inner_text("#ot-bloc-sorties"))
            option = page.inner_text("#ot-sortie-article option[value='%s']" % KIT)
            self.assertIn("Kit garniture", option)
            self.assertIn("stock %d" % stock_avant, option)

            # Sortie de 1 kit : mouvement « sortie » imputé à l'OT, colonne stock − 1
            self.sortir(KIT, "1")
            page.wait_for_selector("#ot-bloc-sorties tr[data-article='%s'] button.ot-retourner" % KIT)
            self.assertRegex(self.attendre_toast_note("^Sortie enregistrée"), "1 × .*Kit garniture.*" + ot_id)
            mouvements = mouvements_de(dossier, ot_id)
            self.assertEqual([(m["type"], m["article_id"], m["quantite"]) for m in mouvements], [("sortie", KIT, "1")])
            self.assertEqual(mouvements[0]["utilisateur"], "Responsable")
            self.assertEqual(stock_csv(dossier, KIT), stock_avant - 1)
            ligne = page.inner_text("#ot-bloc-sorties tr[data-article='%s']" % KIT)
            self.assertIn(euros_fr(prix_kit), espaces_simples(ligne))

            # Coût RG7 (onglet Compte rendu) = calcul Python depuis les CSV
            pieces, total = cout_python(dossier, ot_id)
            self.assertAlmostEqual(pieces, prix_kit, places=2)
            self.onglet("compte-rendu")
            self.assertIn(euros_fr(total), espaces_simples(page.inner_text("#ot-cout-total")))

            # Sortie au-delà du stock : message RG6 tel quel, rien d'écrit
            self.onglet("execution")
            demande = int(stock_avant - 1) + 3
            self.sortir(KIT, str(demande))
            self.assertEqual(self.message_sorties("Stock insuffisant"),
                             "Stock insuffisant : %d en stock, %d demandé" % (stock_avant - 1, demande))
            self.assertEqual(len(mouvements_de(dossier, ot_id)), 1)
            self.assertEqual(stock_csv(dossier, KIT), stock_avant - 1)

            # Retour au-delà du net sorti : refus, rien d'écrit
            self.retourner(KIT, "3")
            message = self.message_sorties("Retour refusé")
            self.assertIn("1 sorti pour l'OT " + ot_id, message)
            self.assertNotIn("Stock insuffisant", message)
            self.assertEqual(len(mouvements_de(dossier, ot_id)), 1)

            # Retour de 1 : stock rétabli, plus de bouton « Retourner » (net 0), coût des pièces nul
            self.retourner(KIT, "1")
            page.wait_for_function("(a) => { const l = document.querySelector(\"#ot-bloc-sorties tr[data-article='\" + a + \"']\");"
                                   " return l && !l.querySelector('button.ot-retourner'); }", arg=KIT)
            self.attendre_toast_note("^Retour enregistré")
            mouvements = mouvements_de(dossier, ot_id)
            self.assertEqual([(m["type"], m["quantite"]) for m in mouvements], [("sortie", "1"), ("retour", "1")])
            self.assertEqual(stock_csv(dossier, KIT), stock_avant)
            self.assertEqual(cout_python(dossier, ot_id)[0], 0)
            self.onglet("compte-rendu")
            self.assertIn(euros_fr(cout_python(dossier, ot_id)[1]), espaces_simples(page.inner_text("#ot-cout-total")))

    def test_pieces_ot_cloture_ou_annule_sans_bouton(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/ot")
            # OT clôturé avec une sortie (kit de la fuite de PO-02) : ligne affichée, aucun bouton
            self.assertTrue(any(m["type"] == "sortie" and m["article_id"] == KIT for m in mouvements_de(dossier, OT_FUITE)))
            for ot_id in (OT_FUITE, OT_CLOTURE, OT_ANNULE):
                with self.subTest(ot=ot_id):
                    statut = ligne_par_id(dossier, "ordres_travail.csv", ot_id)["statut"]
                    self.assertIn(statut, STATUTS_FERMES)
                    self.ouvrir_fiche(ot_id)
                    self.onglet("execution")
                    page.wait_for_selector("#ot-bloc-sorties .ot-sorties-lecture")
                    self.assertEqual(page.locator("#ot-bloc-sorties #form-sortie, #ot-bloc-sorties button").count(), 0)
                    self.assertIn("plus aucune sortie", page.inner_text("#ot-bloc-sorties"))
            self.ouvrir_fiche(OT_FUITE)
            self.onglet("execution")
            self.assertIn("Kit garniture", page.inner_text("#ot-bloc-sorties tr[data-article='%s']" % KIT))
            # L'API refuse aussi (RG6 : OT clôturé)
            refus = page.evaluate("""([ot, a]) => Magasin.sortir(ot, a, 1, '').then(() => 'accepté', (e) => e.message)""", [OT_FUITE, KIT])
            self.assertIn("on ne peut plus lui imputer de sortie", refus)


# ---------------------------------------------------------------------------
# RG3 : « Planifié » refusé si une pièce prévue MANQUE — besoin restant = prévu − net déjà sorti
# pour cet OT ; la pièce manque si le stock est inférieur à ce besoin restant.
# ---------------------------------------------------------------------------

class TestRg3(CasOrdresLot2):

    def preparer_ot_avec_kit(self, quantite_prevue):
        """OT de PO-02 créé par l'interface (technicien, date prévue par défaut), kit garniture prévu
        en `quantite_prevue`, passé « Préparé » ; renvoie son identifiant."""
        page = self.page
        ot_id = self.creer_ot_par_l_interface(EQUIPEMENT_PO02, "PO-02 — garniture (RG3)", TECHNICIEN_BR)
        self.onglet("preparation")
        page.select_option("#ot-nouvel-article", KIT)
        page.fill("#ot-nouvelle-quantite", str(quantite_prevue))
        page.click("#form-pieces button[type=submit]")
        self.attendre_js("([id, q]) => Donnees.lignes('ot_pieces').some(p => p.ot_id === id && p.quantite_prevue === q)",
                         [ot_id, str(quantite_prevue)])
        self.transition("Préparé", ".ot-actions-preparation")
        self.attendre_statut("Préparé")
        return ot_id

    def test_rg3_planifier_accepte_quand_la_piece_prevue_est_deja_sortie_pour_l_ot(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/ot")
            stock = int(stock_csv(dossier, KIT))
            self.assertGreaterEqual(stock, 1)
            ot_id = self.preparer_ot_avec_kit(stock)            # prévu = tout le stock
            # Le kit est sorti pour CET OT avant « Planifier » : le stock tombe à 0, besoin restant 0
            self.onglet("execution")
            self.sortir(KIT, str(stock))
            page.wait_for_selector("#ot-bloc-sorties tr[data-article='%s'] button.ot-retourner" % KIT)
            self.assertEqual(stock_csv(dossier, KIT), 0)
            self.onglet("preparation")
            self.transition("Planifié", ".ot-actions-preparation")
            page.wait_for_function("""() => document.querySelector('#ot-message .alerte')
                || document.querySelector('.ot-badges .badge.statut').textContent === 'Planifié'""")
            self.assertEqual(page.locator("#ot-message .alerte.important").count(), 0, page.inner_text("#ot-message"))
            self.attendre_statut("Planifié")
            self.assertEqual(ligne_par_id(dossier, "ordres_travail.csv", ot_id)["statut"], "Planifié")
            # Onglet Préparation : plus d'alerte « stock insuffisant » pour la pièce déjà sortie
            self.onglet("preparation")
            page.wait_for_selector("#ot-bloc-pieces tr[data-piece] .badge.ok")
            self.assertEqual(page.locator("#ot-bloc-pieces .badge.ko, #ot-bloc-pieces .alerte").count(), 0)
            self.assertEqual(page.evaluate("(id) => Ordres.piecesManquantes(id)", ot_id), [])

    def test_rg3_planifier_refuse_si_le_besoin_restant_depasse_le_stock(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/ot")
            stock = int(stock_csv(dossier, KIT))
            self.assertGreaterEqual(stock, 2)
            prevu = stock + 1
            ot_id = self.preparer_ot_avec_kit(prevu)             # prévu = stock + 1
            # 1 kit sorti pour l'OT : besoin restant = stock, stock restant = stock − 1 → manque
            self.onglet("execution")
            self.sortir(KIT, "1")
            page.wait_for_selector("#ot-bloc-sorties tr[data-article='%s']" % KIT)
            libelle = page.evaluate("(a) => { const x = Donnees.trouver('articles', a); return x.reference + ' — ' + x.designation; }", KIT)
            self.onglet("preparation")
            page.wait_for_selector("#ot-bloc-pieces .badge.ko")
            self.transition("Planifié", ".ot-actions-preparation")
            page.wait_for_selector("#ot-message .alerte")
            message = page.inner_text("#ot-message")
            # Message inchangé : quantité prévue cumulée et stock actuel
            self.assertIn("Stock insuffisant pour « %s » : %d prévu(s), %d en stock." % (libelle, prevu, stock - 1), message)
            self.assertEqual(page.locator("#ot-message button[data-action='attente-piece']").count(), 1)
            self.assertEqual(self.page.inner_text(".ot-badges .badge.statut"), "Préparé")
            self.assertEqual(ligne_par_id(dossier, "ordres_travail.csv", ot_id)["statut"], "Préparé")


# ---------------------------------------------------------------------------
# OT préventif : anomalie constatée, DI liée
# ---------------------------------------------------------------------------

class TestAnomalie(CasOrdresLot2):

    def test_anomalie_signalee_depuis_un_ot_preventif_genere(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/ot")
            ot_id = ot_genere_de_la_gamme(dossier, GAMME_MENSUELLE)
            ot = ligne_par_id(dossier, "ordres_travail.csv", ot_id)
            self.assertEqual((ot["origine"], ot["statut"], ot["anomalie_constatee"]), ("préventif", "Créé", "0"))
            equipement = ot["equipement_id"]
            repere = ligne_par_id(dossier, "equipements.csv", equipement)["repere"].lstrip("'")

            # Fiche : case décochée, bouton vers le formulaire prérempli, aucune DI liée
            self.ouvrir_fiche(ot_id)
            self.assertFalse(page.is_checked("#ot-anomalie-constatee"))
            self.assertFalse(page.is_disabled("#ot-anomalie-constatee"))
            self.assertIn("Aucune demande liée", page.inner_text(".ot-anomalie"))
            self.assertEqual(page.get_attribute("#ot-signaler-anomalie", "href"),
                             "#/di/nouvelle?equipement=%s&ot=%s" % (equipement, ot_id))
            self.assertIn("Signaler une anomalie (DI liée)", page.inner_text("#ot-signaler-anomalie"))
            self.assertEqual(page.locator(".ot-badges .ot-badge-anomalie").count(), 0)

            # « Signaler une anomalie » → formulaire prérempli (équipement, OT d'origine) → DI créée
            page.click("#ot-signaler-anomalie")
            page.wait_for_selector(".di-formulaire")
            self.assertIn(ot_id, page.inner_text(".di-origine"))
            self.assertIn(repere, page.inner_text(".selecteur-choisi"))
            page.fill("input[name=symptome]", "Bande qui frotte sur le châssis")
            page.click("label.tuile:has(input[value='gêne'])")
            page.click(".di-envoyer")
            page.wait_for_selector(".di-numero")
            di = page.inner_text(".di-numero")
            demande = ligne_par_id(dossier, "demandes.csv", di)
            self.assertEqual((demande["ot_origine_id"], demande["equipement_id"], demande["statut"]), (ot_id, equipement, "Nouvelle"))
            self.assertEqual(ligne_par_id(dossier, "ordres_travail.csv", ot_id)["anomalie_constatee"], "1")

            # Retour à l'OT : case cochée, mention dans l'en-tête, DI liée listée avec son lien
            page.click(".di-confirmation-origine a")
            self.ouvrir_fiche(ot_id)
            page.wait_for_selector(".ot-di-liees a[href='#/di/%s']" % di)
            self.assertTrue(page.is_checked("#ot-anomalie-constatee"))
            self.assertIn("anomalie constatée", page.inner_text(".ot-badges"))
            self.assertEqual(page.text_content(".ot-anomalie h3").strip(), "Demandes liées (1)")   # texte du DOM (CSS en capitales)
            self.assertIn("Bande qui frotte", page.inner_text(".ot-di-liees"))

            # Lien retour sur la fiche DI
            page.click(".ot-di-liees a[href='#/di/%s']" % di)
            page.wait_for_selector(".di-lien-origine")
            self.assertEqual(page.get_attribute(".di-lien-origine", "href"), "#/ot/" + ot_id)

            # Liste des OT : mention « anomalie constatée » sur la ligne de l'OT
            self.aller("#/ot")
            page.wait_for_selector(".ot-liste-tableau tbody tr")
            ligne = page.locator(".ot-liste-tableau tbody tr").filter(has_text=ot_id)
            self.assertEqual(ligne.locator(".ot-badge-anomalie").count(), 1)

            # La case s'enregistre aussitôt (décochée puis cochée de nouveau)
            self.ouvrir_fiche(ot_id)
            page.uncheck("#ot-anomalie-constatee")
            self.attendre_toast_note("mention « anomalie constatée » retirée")
            self.assertEqual(ligne_par_id(dossier, "ordres_travail.csv", ot_id)["anomalie_constatee"], "0")
            page.wait_for_function("() => document.querySelector('.ot-badges') && !document.querySelector('.ot-badges .ot-badge-anomalie')")
            page.check("#ot-anomalie-constatee")
            page.wait_for_selector(".ot-badges .ot-badge-anomalie")
            self.assertEqual(ligne_par_id(dossier, "ordres_travail.csv", ot_id)["anomalie_constatee"], "1")
            journal = [j["action"] for j in lire_csv(dossier, "journal.csv") if j["id_ligne"] == ot_id]
            self.assertTrue(any("anomalie constatée retirée" in action for action in journal), journal)

    def test_anomalie_ot_preventif_verrouille_en_lecture_seule(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/ot")
            ot = ligne_par_id(dossier, "ordres_travail.csv", PREVENTIF_VERROUILLE)
            self.assertEqual(ot["origine"], "préventif")
            self.assertIn(ot["statut"], STATUTS_VERROUILLES)
            liees = sorted(d["id"] for d in lire_csv(dossier, "demandes.csv") if d["ot_origine_id"] == PREVENTIF_VERROUILLE)
            self.assertTrue(liees)
            self.ouvrir_fiche(PREVENTIF_VERROUILLE)
            self.assertTrue(page.is_disabled("#ot-anomalie-constatee"))
            self.assertEqual(page.locator("#ot-signaler-anomalie").count(), 0)
            self.assertEqual(sorted(page.eval_on_selector_all(".ot-di-liees a", "liens => liens.map(a => a.textContent)")), liees)
            self.assertEqual(page.is_checked("#ot-anomalie-constatee"), ot["anomalie_constatee"] == "1")
            # Un OT correctif n'a pas de carte d'anomalie
            self.ouvrir_fiche(OT_P1)
            self.assertEqual(page.locator(".ot-anomalie").count(), 0)


# ---------------------------------------------------------------------------
# Clôture technique d'un préventif : gamme mise à jour (RG5)
# ---------------------------------------------------------------------------

class TestGamme(CasOrdresLot2):

    def premier_code(self, dossier, famille):
        return sorted(c["code"] for c in lire_csv(dossier, "codes_defaillance.csv") if c["famille"] == famille)[0]

    def test_gamme_mise_a_jour_a_la_cloture_technique_par_l_interface(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/ot")
            gamme_avant = ligne_par_id(dossier, "gammes.csv", GAMME_MENSUELLE)
            self.assertEqual((gamme_avant["declencheur"], gamme_avant["periodicite_jours"]), ("date", "30"))   # mensuelle
            ot_id = ot_genere_de_la_gamme(dossier, GAMME_MENSUELLE)
            self.ouvrir_fiche(ot_id)

            # Préparation (technicien habilité, date prévue gardée) → Préparé → Planifié → Démarrer
            self.onglet("preparation")
            page.select_option("#form-preparation [name=technicien_id]", TECHNICIEN_BR)
            self.transition("Préparé", ".ot-actions-preparation")
            self.attendre_statut("Préparé")
            self.transition("Planifié", ".ot-actions-preparation")
            self.attendre_statut("Planifié")
            self.onglet("execution")
            self.transition("En cours", ".ot-demarrer")
            self.attendre_statut("En cours")

            # Exécution : temps passé, date de fin ; compte rendu complet
            self.onglet("execution")
            page.fill("#ot-temps-heures", "1")
            page.click("#form-temps button[type=submit]")
            self.attendre_js("(id) => Donnees.lignes('ot_temps').some(t => t.ot_id === id)", ot_id)
            self.onglet("execution")
            page.click("#form-execution .ot-maintenant")
            page.click("#form-execution button[type=submit]")
            self.attendre_js("(id) => Donnees.trouver('ordres_travail', id).date_fin !== ''", ot_id)
            self.onglet("compte-rendu")
            page.select_option("#form-compte-rendu [name=cause_code]", self.premier_code(dossier, "cause"))
            page.select_option("#form-compte-rendu [name=remede_code]", self.premier_code(dossier, "remède"))
            page.fill("#form-compte-rendu [name=compte_rendu]", "Contrôle mensuel réalisé, tension de bande réglée.")
            page.check("#form-compte-rendu [name=remise_service]")

            # 1) Mise à jour de la gamme en échec : la clôture reste, avertissement affiché
            page.evaluate("""() => { window.__apresCloture = Preventif.apresCloture;
                Preventif.apresCloture = async () => { throw new Donnees.ErreurValidation('panne simulée'); }; }""")
            self.transition("Clôturé techniquement", "#form-compte-rendu")
            self.attendre_statut("Clôturé techniquement")
            self.assertEqual(ligne_par_id(dossier, "ordres_travail.csv", ot_id)["statut"], "Clôturé techniquement")
            self.assertEqual(ligne_par_id(dossier, "gammes.csv", GAMME_MENSUELLE), gamme_avant)
            page.wait_for_selector("#ot-message .alerte")
            self.assertIn("la gamme %s n'a pas été mise à jour (panne simulée)" % GAMME_MENSUELLE, page.inner_text("#ot-message"))
            self.assertIn("panne simulée", self.attendre_toast_note("n'a pas été mise à jour"))

            # 2) Réouverture (responsable) puis nouvelle clôture : la gamme prend la date de fin
            page.evaluate("() => { Preventif.apresCloture = window.__apresCloture; }")
            self.transition("En cours")
            self.attendre_statut("En cours")
            self.onglet("compte-rendu")
            self.transition("Clôturé techniquement", "#form-compte-rendu")
            self.attendre_statut("Clôturé techniquement")
            self.attendre_toast_note("^%s : Clôturé techniquement\\.$" % ot_id)
            self.assertEqual(page.locator("#ot-message .alerte").count(), 0)

            ot = ligne_par_id(dossier, "ordres_travail.csv", ot_id)
            self.assertEqual(ot["statut"], "Clôturé techniquement")
            fin = datetime.date.fromisoformat(ot["date_fin"][:10])
            gamme = ligne_par_id(dossier, "gammes.csv", GAMME_MENSUELLE)
            self.assertEqual(gamme["derniere_realisation"], fin.isoformat())
            self.assertEqual(gamme["prochaine_echeance"], (fin + datetime.timedelta(days=30)).isoformat())
            self.assertGreater(gamme["prochaine_echeance"], gamme_avant["prochaine_echeance"])
            journal = [j["action"] for j in lire_csv(dossier, "journal.csv") if j["id_ligne"] == GAMME_MENSUELLE]
            self.assertTrue(any("réalisation de la gamme par l'OT " + ot_id in action for action in journal), journal)


# ---------------------------------------------------------------------------
# Encart « Causes fréquentes ici »
# ---------------------------------------------------------------------------

class TestEncart(CasOrdresLot2):

    def test_encart_causes_frequentes_fuite_po02_preparation_et_compte_rendu(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/ot")
            ot = ligne_par_id(dossier, "ordres_travail.csv", OT_FUITE)
            self.assertEqual((ot["equipement_id"], ot["symptome_code"]), (EQUIPEMENT_PO02, SYMPTOME_FUITE))
            cas = [o for o in lire_csv(dossier, "ordres_travail.csv")
                   if o["equipement_id"] == EQUIPEMENT_PO02 and o["type"].startswith("correctif")
                   and o["statut"] in ("Clôturé techniquement", "Clôturé administrativement")
                   and o["symptome_code"] == SYMPTOME_FUITE and o["cause_code"]]
            self.assertGreaterEqual(len(cas), 5)
            self.ouvrir_fiche(OT_FUITE)
            for onglet in ("compte-rendu", "preparation"):
                with self.subTest(onglet=onglet):
                    self.onglet(onglet)
                    encart = ".panneau-onglet[data-onglet='%s'] .ot-causes .causes-frequentes" % onglet
                    page.wait_for_selector(encart)
                    texte = page.inner_text(encart)
                    self.assertIn("Causes fréquentes ici — %d cas" % len(cas), texte)
                    self.assertIn("Statistique de l'historique, pas un diagnostic", texte)
                    self.assertGreaterEqual(page.locator(encart + " a[href^='#/ot/']").count(), 1)
            # Sans code symptôme (OT préventif) : pas d'encart
            sans_code = next(o["id"] for o in lire_csv(dossier, "ordres_travail.csv")
                             if o["origine"] == "préventif" and not o["symptome_code"] and o["statut"] not in STATUTS_FERMES)
            self.ouvrir_fiche(sans_code)
            self.onglet("preparation")
            page.wait_for_selector("#form-preparation")
            self.assertEqual(page.locator(".ot-causes").count(), 0)


# ---------------------------------------------------------------------------
# Technicien et téléphone
# ---------------------------------------------------------------------------

def article_disponible(page, ot_id):
    """Un article à sortir pour l'OT : une pièce prévue en stock, sinon un article actif en stock."""
    return page.evaluate("""(ot) => {
        const prevues = Donnees.lignes('ot_pieces').filter(p => p.ot_id === ot && Number(p.quantite_prevue) > 0).map(p => p.article_id);
        const enStock = (id) => Donnees.stockArticle(id) >= 1;
        return prevues.find(enStock)
          || Donnees.lignes('articles').filter(a => a.actif !== '0').map(a => a.id).find(enStock); }""", ot_id)


class TestTechnicienEtTelephone(CasOrdresLot2):

    def test_technicien_sortie_possible_sur_son_ot(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            technicien = ligne_par_id(dossier, "ordres_travail.csv", OT_P1)["technicien_id"]
            self.assertTrue(technicien)
            self.ouvrir(serveur, "#/ot/" + OT_P1, profil="technicien", technicien_id=technicien)
            page.wait_for_selector(".ot-fiche .ot-numero")
            self.onglet("execution")
            page.wait_for_selector("#form-sortie")
            article = article_disponible(page, OT_P1)
            self.assertTrue(article)
            avant = len(mouvements_de(dossier, OT_P1))
            self.sortir(article, "1")
            page.wait_for_selector("#ot-bloc-sorties tr[data-article='%s'] button.ot-retourner" % article)
            mouvements = mouvements_de(dossier, OT_P1)
            self.assertEqual(len(mouvements), avant + 1)
            dernier = mouvements[-1]
            self.assertEqual((dernier["type"], dernier["article_id"], dernier["quantite"]), ("sortie", article, "1"))
            self.assertNotIn(dernier["utilisateur"], ("", "Responsable"))

    def test_telephone_375px_sans_defilement_horizontal_et_zones_48px(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/ot", largeur=375)
            page.set_viewport_size({"width": 375, "height": 812})

            def controler(contexte):
                largeurs = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
                self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))
                self.assertEqual(page.evaluate(PETITES_ZONES_JS), [], "zones tactiles < 48 px (%s)" % contexte)

            # OT en cours avec une pièce sortie : tableau empilé, bouton « Retourner », formulaire
            article = article_disponible(page, OT_P1)
            page.evaluate("([ot, a]) => Magasin.sortir(ot, a, 1, 'test téléphone')", [OT_P1, article])
            self.ouvrir_fiche(OT_P1)
            self.onglet("execution")
            page.wait_for_selector("#ot-bloc-sorties button.ot-retourner")
            controler(OT_P1 + " exécution")
            # Préventif généré (carte d'anomalie), préventif verrouillé (demandes liées)
            for ot_id in (ot_genere_de_la_gamme(dossier, GAMME_MENSUELLE), PREVENTIF_VERROUILLE):
                self.ouvrir_fiche(ot_id)
                page.wait_for_selector(".ot-anomalie")
                controler(ot_id + " anomalie")
            # Encart des causes fréquentes (Préparation, Compte rendu) et OT clôturé avec sortie
            self.ouvrir_fiche(OT_FUITE)
            for onglet in ("preparation", "execution", "compte-rendu"):
                self.onglet(onglet)
                controler(OT_FUITE + " " + onglet)
            self.aller("#/ot")
            page.wait_for_selector(".ot-liste-cartes .liste-cartes")
            controler("liste des OT")


if __name__ == "__main__":
    unittest.main()
