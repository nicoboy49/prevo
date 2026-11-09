"""Recette du lot 1 de bout en bout (brief §14, tâche T16).

On rejoue les scénarios de recette du brief comme un utilisateur, par l'interface, sans refaire
les tests unitaires des modules (règles, filtres, formulaires : voir test_parc, test_demandes,
test_ordres, test_parametres). Chaque scénario applicable est joué :
    serveur : serveur.py (ServeurPrevo, copie du jeu de démo), vérifications sur le disque ;
    demo    : index.html en file:// → « Essayer avec les données de démo » ; rien ne survit à un
              rechargement : le profil est changé par l'interface (bouton du poste), sans recharger.

Scénarios :
    pompe         DI sur PO-02 → acceptée P2 → OT préparé (kit garniture) → planifié → exécuté, le kit
                  sorti du magasin depuis l'OT (stock du kit −1) → clôturé techniquement puis
                  administrativement → visible dans l'historique de PO-02 ;
    ras           clôture refusée avec « RAS » et sans code cause, message clair, statut inchangé ;
    conflit       deux navigateurs valident une DI au même instant → deux DI distinctes, aucune perte ;
    telephone     (lot 7, T161 : serveur en portée « atelier », tests/atelier.py) QR de la fiche relu par
                  jsQR = adresse de la porte → téléphone 375 px qui fait confiance au PC atelier → porte →
                  application en https, route gardée → appareil enrôlé (profil déduit, T155) → DI avec photo →
                  visible sur le PC (client 127.0.0.1, responsable), sans rechargement, en moins de 30 s ;
    habilitation  OT sur AE-03 (BR) affecté au technicien dont la BR est échue → refus affiché, rien d'écrit (T437) ;
    sauvegarde    sauvegarde, ligne supprimée sur le disque, restauration par les Paramètres ;
    traversee     PUT /api/documents/../serveur.py refusé ;
    design        360 px sans défilement horizontal, zones tactiles >= 48 px, barre du bas ;
                  1440 px menu latéral ; badges de priorité avec leur texte.

Aucun identifiant du jeu de démo n'est écrit en dur : ils viennent de scenarios_demo()
(tests/fixtures/demo-scenarios.json) ou sont cherchés par leurs propriétés dans donnees/demo
(repère d'un équipement, technicien mécanicien, codes cause et remède par leur libellé).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_recette_lot1.py" -v
"""
import csv
import datetime
import hashlib
import http.client
import io
import re
import time
import unittest
from pathlib import Path

from atelier import ServeurAtelier, connecter, enroler_appareil, motif_refus_du_demandeur
from commun import (CasNavigateur, DOSSIER_DEMO, RACINE, ServeurPrevo, attendre_pret, preregler_profil,
                    scenarios_demo, url_fichier)
from test_demandes import dimensions_jpeg, fichier_png

# Identifiants des objets de scénario du jeu de démo (outils/generer_demo.py, ARCHITECTURE.md §14.8).
SCENARIOS = scenarios_demo()


def brut(valeur):
    """Valeur sans l'apostrophe de protection des CSV (ARCHITECTURE.md §3.2)."""
    return valeur[1:] if valeur.startswith("'") else valeur


def lignes_demo(table):
    """Lignes d'une table du jeu de démo (donnees/demo), valeurs sans apostrophe de protection."""
    with open(DOSSIER_DEMO / (table + ".csv"), encoding="utf-8-sig", newline="") as fichier:
        return [{cle: brut(valeur) for cle, valeur in ligne.items()} for ligne in csv.DictReader(fichier, delimiter=";")]


def ligne_demo(table, identifiant):
    return next(ligne for ligne in lignes_demo(table) if ligne["id"] == identifiant)


def repere_demo(equipement_id):
    return ligne_demo("equipements", equipement_id)["repere"]


def code_demo(famille, libelle):
    """Code de défaillance du jeu de démo d'après sa famille et son libellé."""
    return next(c["code"] for c in lignes_demo("codes_defaillance") if c["famille"] == famille and c["libelle"] == libelle)


# Objets du scénario « pompe » : la pompe aux fuites de garniture (PO-02), son kit, un mécanicien,
# les codes symptôme (fuite), cause (garniture usée) et remède (remplacement de pièce).
POMPE = SCENARIOS["causes_equipement"]
REPERE_POMPE = repere_demo(POMPE)
KIT = SCENARIOS["kit_garniture"]
DESIGNATION_KIT = ligne_demo("articles", KIT)["designation"]
MECANICIEN = next(t["id"] for t in lignes_demo("techniciens") if t["metier"] == "Mécanicien" and t["actif"] != "0")
SYMPTOME_FUITE = SCENARIOS["causes_equipement_symptome"]
CAUSE_GARNITURE = code_demo("cause", "Garniture usée")
REMEDE_REMPLACEMENT = code_demo("remède", "Remplacement de pièce")
# Scénario « habilitation » : équipement qui exige la BR (AE-03), technicien dont la BR est échue.
EQUIPEMENT_BR = SCENARIOS["equipement_br"]
REPERE_BR = repere_demo(EQUIPEMENT_BR)
TECHNICIEN_BR_ECHUE = SCENARIOS["technicien_br_echue"]
# Scénario « conflit » : un second équipement (le convoyeur de la gamme mensuelle, CV-01).
REPERE_CONVOYEUR = repere_demo(ligne_demo("gammes", SCENARIOS["gamme_mensuelle_echue"])["equipement_id"])

# Chromium écrit « Failed to load resource » (console.error) pour toute réponse HTTP >= 400.
# Seul le scénario « conflit » provoque un 409, et seulement sur demandes.csv :
CONFLIT_DEMANDES = re.compile(r"status of 409.*/api/csv/demandes")

SYMPTOME_POMPE = "Fuite au niveau de la garniture"
DESCRIPTION_POMPE = "Goutte à goutte continu sous la garniture côté moteur, flaque d'environ 30 cm."
COMPTE_RENDU_POMPE = ("Garniture mécanique usée (faces rayées) : kit garniture remplacé, "
                      "remise en eau et essai 15 min sans fuite.")
# Nom enregistré par le serveur : « AAAAMMJJ-HHMMSS-photo-… » (préfixe imposé, audit F4, T159)
MOTIF_PHOTO = re.compile(r"^\d{8}-\d{6}-photo-\d{8}-\d{6}-[A-Z0-9]{4}\.jpg$")

# Lecture d'un QR (SVG de la fiche équipement) par jsQR, dans la page.
LIRE_QR_FICHE_JS = """async () => {
    const svg = document.querySelector('.parc-qr-carte svg.qr-svg');
    if (!svg) return null;
    const image = new Image();
    image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(svg));
    await image.decode();
    const toile = document.createElement('canvas');
    toile.width = 300; toile.height = 300;
    const contexte = toile.getContext('2d');
    contexte.drawImage(image, 0, 0, 300, 300);
    const code = jsQR(contexte.getImageData(0, 0, 300, 300).data, 300, 300);
    return code ? code.data : null;
}"""

LARGEURS_JS = "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"

# Zones tactiles de #contenu de moins de 48 px de haut (case à cocher : son libellé compte).
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


def lire_csv(chemin):
    """(en-tête, lignes) d'un CSV de Prévo ; valeurs telles que dans le fichier (apostrophes comprises)."""
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        lecteur = csv.reader(fichier, delimiter=";")
        entete = next(lecteur)
        lignes = [dict(zip(entete, cellules)) for cellules in lecteur if any(cellules)]
    return entete, lignes


def ligne_par_id(chemin, identifiant):
    return next((l for l in lire_csv(chemin)[1] if l["id"] == identifiant), None)


def ecrire_csv(chemin, entete, lignes):
    """Réécrit un CSV au format Prévo (BOM, « ; », CRLF), comme un utilisateur qui l'aurait édité."""
    tampon = io.StringIO(newline="")
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(entete)
    for ligne in lignes:
        ecrivain.writerow([ligne.get(nom, "") for nom in entete])
    Path(chemin).write_bytes(("﻿" + tampon.getvalue()).encode("utf-8"))


def dans_deux_jours():
    return (datetime.date.today() + datetime.timedelta(days=2)).isoformat()


class CasRecette(CasNavigateur):
    """Gestes d'utilisateur communs aux scénarios (profil, menu, onglets, statut d'un OT)."""

    # -- démarrage ------------------------------------------------------------

    def attendre_etat(self, etat, page=None):
        (page or self.page).wait_for_function(
            "(etat) => document.documentElement.dataset.etat === etat", arg=etat)

    def demarrer_serveur_sans_profil(self, serveur, route="", page=None):
        page = page or self.page
        page.goto(serveur.url + "/" + route)
        self.attendre_etat("profil", page)

    def demarrer_demo_sans_profil(self, page=None):
        page = page or self.page
        page.goto(url_fichier("index.html"))
        self.attendre_etat("demarrage", page)
        page.click("#btn-demo")
        self.attendre_etat("profil", page)

    def choisir_profil(self, type_profil, nom="", technicien_id="", page=None):
        """Sur l'écran de profil : choisit le profil comme un utilisateur."""
        page = page or self.page
        if type_profil == "responsable":
            page.click("#profil-responsable")
        elif type_profil == "demandeur":
            page.click("#profil-demandeur")
            page.fill("#profil-nom", nom)
            page.click("#profil-panneau-demandeur button[type=submit]")
        else:
            page.click("#profil-technicien")
            page.click("#profil-techniciens [data-technicien='%s']" % technicien_id)
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.profil.type"), type_profil)

    def changer_profil(self, type_profil, nom="", technicien_id="", page=None):
        """Change de profil par le bouton du poste, sans recharger la page."""
        page = page or self.page
        page.evaluate("window.__memePage = true")
        page.click("#etat-poste")
        self.attendre_etat("profil", page)
        self.choisir_profil(type_profil, nom, technicien_id, page=page)
        self.assertTrue(page.evaluate("window.__memePage === true"), "la page a été rechargée")

    # -- navigation -------------------------------------------------------------

    def menu(self, ecran, page=None):
        page = page or self.page
        page.click("#menu a[data-ecran='%s']" % ecran)

    def attendre_toast(self, extrait, page=None):
        (page or self.page).wait_for_function(
            "(t) => document.getElementById('toast').textContent.includes(t)", arg=extrait)

    def sans_defilement_horizontal(self, contexte, page=None):
        largeurs = (page or self.page).evaluate(LARGEURS_JS)
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))

    # -- fiche OT -------------------------------------------------------------------

    def attendre_fiche_ot(self, ot_id):
        self.page.wait_for_function(
            "(id) => { const n = document.querySelector('.ot-fiche .ot-numero'); return n && n.textContent === id; }",
            arg=ot_id)

    def statut_ot(self):
        return self.page.inner_text(".ot-badges .badge.statut")

    def attendre_statut(self, statut):
        self.page.wait_for_function(
            "(s) => { const b = document.querySelector('.ot-badges .badge.statut'); return b && b.textContent === s; }",
            arg=statut)

    def onglet(self, identifiant):
        self.page.click(".onglet[data-onglet='%s']" % identifiant)

    def ouvrir_ot_depuis_la_liste(self, ot_id):
        self.menu("liste-ot")
        lien = self.page.locator(".ot-liste-tableau a", has_text=ot_id)
        lien.first.click()
        self.attendre_fiche_ot(ot_id)


# ---------------------------------------------------------------------------
# 1. Panne sur pompe (serveur, démo)
# ---------------------------------------------------------------------------

class TestRecettePompe(CasRecette):

    def jouer(self, serveur=None):
        """Le parcours complet ; renvoie (numéro de DI, identifiant d'OT)."""
        page = self.page
        if serveur:
            self.demarrer_serveur_sans_profil(serveur)
        else:
            self.demarrer_demo_sans_profil()

        # --- Le demandeur signale la fuite sur PO-02 ---
        self.choisir_profil("demandeur", "Lucie Martin")
        self.menu("nouvelle-di")
        page.wait_for_selector(".di-formulaire")
        page.fill(".selecteur-recherche input[type=search]", REPERE_POMPE)
        page.click(".selecteur-option[data-id='%s']" % POMPE)
        self.assertIn(REPERE_POMPE, page.inner_text(".selecteur-choisi"))
        page.fill("input[name=symptome]", SYMPTOME_POMPE)
        page.click("label.tuile:has(input[value='dégradé'])")
        self.assertEqual(page.inner_text(".di-priorite .badge"), "P2")        # B × dégradé
        page.fill("textarea[name=description]", DESCRIPTION_POMPE)
        if serveur:
            page.locator(".di-fichier-photo").set_input_files(fichier_png(1600, 1200))
            page.wait_for_selector(".di-apercu:not([hidden]) img")
        page.click(".di-envoyer")
        page.wait_for_selector(".di-numero")
        numero = page.inner_text(".di-numero")
        self.assertRegex(numero, r"^DI-\d{4}-\d{4}$")
        self.assertIn("Demande envoyée", page.inner_text("#contenu"))

        # --- Le responsable l'ouvre depuis la liste des demandes : P2 ---
        self.changer_profil("responsable")
        self.menu("liste-di")
        page.wait_for_selector(".di-zone-tableau tbody tr.cliquable")
        ligne = page.locator(".di-zone-tableau tbody tr.cliquable", has_text=numero)
        self.assertEqual(ligne.count(), 1)
        ligne.locator("td").nth(3).click()
        page.wait_for_selector(".di-details")
        self.assertEqual(page.evaluate("location.hash"), "#/di/" + numero)
        self.assertEqual(page.inner_text(".di-details .badge.prio-p2"), "P2")
        self.assertIn(SYMPTOME_POMPE, page.inner_text("#contenu"))

        # --- Accepter : OT P2 lié ---
        page.click("[data-decision=accepter]")
        page.wait_for_selector("dialog .di-fenetre-accepter")
        self.assertEqual(page.input_value("dialog select[name=priorite]"), "P2")
        page.click("dialog button:has-text(\"Créer l'ordre de travail\")")
        page.wait_for_function("location.hash.startsWith('#/ot/')")
        ot_id = page.evaluate("decodeURIComponent(location.hash.slice(5))")
        self.attendre_fiche_ot(ot_id)
        self.assertEqual(self.statut_ot(), "Créé")
        self.assertEqual(page.inner_text(".ot-badges .badge.prio-p2"), "P2")
        self.assertEqual(page.locator(".ot-fiche a[href='#/di/%s']" % numero).count() >= 1, True)

        # --- Préparation : technicien mécanicien, date prévue, kit garniture × 1 ---
        self.onglet("preparation")
        page.select_option("#form-preparation [name=technicien_id]", MECANICIEN)
        page.fill("#form-preparation [name=date_prevue]", dans_deux_jours())
        page.click("#form-preparation button[type=submit]")
        self.attendre_toast("Préparation enregistrée")
        self.onglet("preparation")
        option_kit = page.locator("#ot-nouvel-article option[value='%s']" % KIT).inner_text()
        self.assertIn(DESIGNATION_KIT, option_kit)
        page.select_option("#ot-nouvel-article", KIT)
        page.fill("#ot-nouvelle-quantite", "1")
        page.click("#form-pieces button[type=submit]")
        page.wait_for_selector("#ot-bloc-pieces tr[data-piece]:has-text(%r)" % DESIGNATION_KIT)
        page.click(".ot-actions-preparation button:has-text('Marquer préparé')")
        self.attendre_statut("Préparé")

        # --- Planifier : accepté (stock suffisant) ---
        page.click(".ot-actions-preparation button:has-text('Planifier')")
        self.attendre_statut("Planifié")
        self.assertEqual(page.locator("#ot-message .alerte").count(), 0)

        # --- Démarrer, temps passé, date de fin ---
        self.onglet("execution")
        page.click(".ot-demarrer button:has-text('Démarrer')")
        self.attendre_statut("En cours")
        # --- Sortie du kit depuis l'OT (bloc « Pièces sorties ») : stock du kit −1 ---
        self.onglet("execution")
        page.wait_for_selector("#ot-bloc-sorties #form-sortie")
        self.assertIn("Aucune pièce sortie", page.inner_text("#ot-bloc-sorties"))
        self.assertEqual(page.input_value("#ot-sortie-article"), KIT)          # pièce prévue proposée en tête
        stock_kit_avant = page.evaluate("(a) => Donnees.stockArticle(a)", KIT)
        self.assertIn("stock %d" % stock_kit_avant, page.inner_text("#ot-sortie-article option[value='%s']" % KIT))
        page.fill("#ot-sortie-quantite", "1")
        page.click("#form-sortie button[type=submit]")
        page.wait_for_selector("#ot-bloc-sorties tr[data-article='%s'] button.ot-retourner" % KIT)
        self.attendre_toast("Sortie enregistrée")
        self.assertEqual(page.evaluate("(a) => Donnees.stockArticle(a)", KIT), stock_kit_avant - 1)
        self.stock_kit = (stock_kit_avant, stock_kit_avant - 1)
        self.onglet("execution")
        self.assertEqual(page.input_value("#ot-temps-technicien"), MECANICIEN)
        page.fill("#ot-temps-heures", "1,5")
        page.click("#form-temps button[type=submit]")
        page.wait_for_function("document.querySelector('#ot-bloc-temps tbody') && !document.querySelector('#ot-bloc-temps .vide-table')")
        self.attendre_toast("Temps ajouté")
        self.onglet("execution")
        page.click("#form-execution .ot-maintenant")
        page.click("#form-execution button[type=submit]")
        self.attendre_toast("Exécution enregistrée")

        # --- Compte rendu : codes, texte, remise en service → clôture technique ---
        self.onglet("compte-rendu")
        for champ, code, libelle in (("symptome_code", SYMPTOME_FUITE, "fuite"), ("cause_code", CAUSE_GARNITURE, "garniture usée"),
                                     ("remede_code", REMEDE_REMPLACEMENT, "remplacement")):
            option = page.locator("#form-compte-rendu [name=%s] option[value='%s']" % (champ, code)).inner_text()
            self.assertIn(libelle, option.lower())
            page.select_option("#form-compte-rendu [name=%s]" % champ, code)
        page.fill("#form-compte-rendu [name=compte_rendu]", COMPTE_RENDU_POMPE)
        page.check("#form-compte-rendu [name=remise_service]")
        page.click("#form-compte-rendu button:has-text('Clôturer techniquement')")
        self.attendre_statut("Clôturé techniquement")

        # --- Clôture administrative : OT verrouillé ---
        page.click(".ot-actions button:has-text('Clôturer administrativement')")
        page.click("dialog .fenetre-actions .btn-primaire")
        self.attendre_statut("Clôturé administrativement")
        self.assertEqual(page.locator(".ot-fiche button[data-action='transition']").count(), 0)
        self.assertIn("lecture seule", page.inner_text(".ot-bandeau-etat"))

        # --- La fiche de PO-02 montre l'OT dans son historique ---
        page.locator(".ot-fiche a[href='#/equipement/%s']" % POMPE).first.click()
        page.wait_for_function("(r) => document.querySelector('#contenu h1') && document.querySelector('#contenu h1').textContent.includes(r)",
                               arg=REPERE_POMPE)
        page.wait_for_selector("#contenu a[href='#/ot/%s']" % ot_id)
        ligne_historique = page.locator("#contenu tr", has_text=ot_id).first.inner_text()
        self.assertIn("Clôturé administrativement", ligne_historique)
        self.assertIn("P2", ligne_historique)
        return numero, ot_id

    def test_pompe_serveur(self):
        with ServeurPrevo() as serveur:
            stock_kit_disque = float(ligne_par_id(serveur.dossier / "articles.csv", KIT)["stock"])
            numero, ot_id = self.jouer(serveur)
            dossier = serveur.dossier
            # Stock du kit −1 : colonne stock de articles.csv et mouvement « sortie » imputé à l'OT
            self.assertEqual(self.stock_kit[0], stock_kit_disque)
            self.assertEqual(float(ligne_par_id(dossier / "articles.csv", KIT)["stock"]), stock_kit_disque - 1)
            sorties = [(m["type"], m["article_id"], m["quantite"]) for m in lire_csv(dossier / "mouvements_stock.csv")[1]
                       if m["ot_id"] == ot_id]
            self.assertEqual(sorties, [("sortie", KIT, "1")])
            demande = ligne_par_id(dossier / "demandes.csv", numero)
            self.assertEqual((demande["statut"], demande["ot_id"], demande["impact"], demande["demandeur"]),
                             ("Acceptée", ot_id, "dégradé", "Lucie Martin"))
            self.assertRegex(demande["photo"], MOTIF_PHOTO)
            self.assertTrue((dossier / "documents" / demande["photo"]).is_file())
            ot = ligne_par_id(dossier / "ordres_travail.csv", ot_id)
            self.assertEqual((ot["statut"], ot["priorite"], ot["origine"], ot["di_id"], ot["equipement_id"]),
                             ("Clôturé administrativement", "P2", "DI", numero, POMPE))
            self.assertEqual((ot["technicien_id"], ot["date_prevue"], ot["symptome_code"], ot["cause_code"],
                              ot["remede_code"], ot["remise_service"]),
                             (MECANICIEN, dans_deux_jours(), SYMPTOME_FUITE, CAUSE_GARNITURE, REMEDE_REMPLACEMENT, "1"))
            self.assertEqual(ot["compte_rendu"], COMPTE_RENDU_POMPE)
            for champ in ("date_debut", "date_fin", "date_cloture_tech", "date_cloture_admin"):
                self.assertRegex(ot[champ], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", champ)
            pieces = [(p["article_id"], p["quantite_prevue"]) for p in lire_csv(dossier / "ot_pieces.csv")[1] if p["ot_id"] == ot_id]
            self.assertEqual(pieces, [(KIT, "1")])
            temps = [(t["technicien_id"], t["heures"]) for t in lire_csv(dossier / "ot_temps.csv")[1] if t["ot_id"] == ot_id]
            self.assertEqual(temps, [(MECANICIEN, "1.5")])

    def test_pompe_demo(self):
        numero, ot_id = self.jouer()
        self.assertEqual(self.page.evaluate("App.mode"), "demo")
        ot = self.page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", ot_id)
        self.assertEqual((ot["statut"], ot["priorite"], ot["di_id"], ot["cause_code"]),
                         ("Clôturé administrativement", "P2", numero, CAUSE_GARNITURE))
        self.assertEqual(self.page.evaluate("(id) => Donnees.trouver('demandes', id).statut", numero), "Acceptée")
        # Stock du kit −1 (stock recalculé et colonne stock de la ligne de l'article)
        self.assertEqual(self.page.evaluate("(a) => Donnees.stockArticle(a)", KIT), self.stock_kit[1])
        self.assertEqual(float(self.page.evaluate("(a) => Donnees.trouver('articles', a).stock", KIT)), self.stock_kit[1])


# ---------------------------------------------------------------------------
# 2. Clôture refusée avec « RAS » et sans code cause (serveur, démo)
# ---------------------------------------------------------------------------

class TestRecetteRas(CasRecette):

    OT = SCENARIOS["ot_p1_ouvert"]      # En cours, P1, CP-01

    def jouer(self):
        page = self.page
        self.choisir_profil("responsable")
        self.ouvrir_ot_depuis_la_liste(self.OT)
        self.assertEqual(self.statut_ot(), "En cours")
        self.onglet("compte-rendu")
        page.select_option("#form-compte-rendu [name=cause_code]", "")
        page.fill("#form-compte-rendu [name=compte_rendu]", "RAS")
        page.click("#form-compte-rendu button:has-text('Clôturer techniquement')")
        page.wait_for_selector("#ot-message .alerte")
        message = page.inner_text("#ot-message")
        self.assertIn("Clôture technique impossible", message)
        self.assertIn("code cause", message)
        self.assertIn("RAS", message)
        self.assertEqual(self.statut_ot(), "En cours")
        return message

    def test_ras_serveur(self):
        with ServeurPrevo() as serveur:
            self.demarrer_serveur_sans_profil(serveur)
            self.jouer()
            ot = ligne_par_id(serveur.dossier / "ordres_travail.csv", self.OT)
            self.assertEqual(ot["statut"], "En cours")
            self.assertEqual(ot["date_cloture_tech"], "")

    def test_ras_demo(self):
        self.demarrer_demo_sans_profil()
        self.jouer()
        self.assertEqual(self.page.evaluate("(id) => Donnees.trouver('ordres_travail', id).statut", self.OT), "En cours")


# ---------------------------------------------------------------------------
# 3. Conflit : deux navigateurs valident une DI au même instant (serveur)
# ---------------------------------------------------------------------------

class TestRecetteConflit(CasRecette):

    def nouveau_poste(self, nom, poste):
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        preregler_profil(contexte, "demandeur", nom=nom, poste=poste)
        page = contexte.new_page()
        self.surveiller(page)
        return contexte, page

    def remplir(self, page, serveur, equipement, symptome):
        page.goto(serveur.url + "/")
        attendre_pret(page)
        self.menu("nouvelle-di", page)
        page.wait_for_selector(".di-formulaire")
        page.fill(".selecteur-recherche input[type=search]", equipement)
        page.click(".selecteur-option:has-text('%s')" % equipement)
        page.fill("input[name=symptome]", symptome)
        page.click("label.tuile:has(input[value='gêne'])")

    def test_conflit_serveur_deux_validations_simultanees(self):
        self.autoriser_erreur(CONFLIT_DEMANDES)
        with ServeurPrevo() as serveur:
            avant = len(lire_csv(serveur.dossier / "demandes.csv")[1])
            contexte_a, page_a = self.nouveau_poste("Lucie Martin", "Poste A")
            contexte_b, page_b = self.nouveau_poste("Paul Dubois", "Poste B")
            self.remplir(page_a, serveur, REPERE_POMPE, "Bruit de roulement côté accouplement")
            self.remplir(page_b, serveur, REPERE_CONVOYEUR, "Bande qui patine au démarrage")

            # Barrière : les écritures de demandes.csv sont retenues jusqu'à ce que les DEUX postes
            # aient envoyé la leur (les deux clics ont eu lieu avant toute réponse du serveur).
            retenues = []
            barriere = {"active": True}

            def retenir(route):
                if barriere["active"] and route.request.method == "PUT":
                    retenues.append(route)
                else:
                    route.continue_()

            for contexte in (contexte_a, contexte_b):
                contexte.route(re.compile(r"/api/csv/demandes$"), retenir)
            page_a.click(".di-envoyer")
            page_b.click(".di-envoyer")
            fin = time.monotonic() + 10
            while len(retenues) < 2:
                self.assertLess(time.monotonic(), fin, "les deux envois n'ont pas eu lieu (%d)" % len(retenues))
                page_a.wait_for_timeout(20)
            barriere["active"] = False
            for route in retenues:
                route.continue_()

            page_a.wait_for_selector(".di-numero")
            page_b.wait_for_selector(".di-numero")
            numero_a = page_a.inner_text(".di-numero")
            numero_b = page_b.inner_text(".di-numero")
            self.assertNotEqual(numero_a, numero_b)
            demandes = {l["id"]: l for l in lire_csv(serveur.dossier / "demandes.csv")[1]}
            self.assertEqual(len(demandes), avant + 2)
            self.assertEqual(demandes[numero_a]["demandeur"], "Lucie Martin")
            self.assertEqual(demandes[numero_a]["equipement_id"], POMPE)
            self.assertEqual(demandes[numero_b]["demandeur"], "Paul Dubois")
            self.assertEqual(demandes[numero_b]["symptome"], "Bande qui patine au démarrage")
            # Le conflit a réellement eu lieu (409 puis rejeu) dans au moins un des deux postes.
            conflits = [page_a.evaluate("Donnees.statistiques.conflits"), page_b.evaluate("Donnees.statistiques.conflits")]
            self.assertGreaterEqual(max(conflits), 1, conflits)


# ---------------------------------------------------------------------------
# 4. Téléphone : QR → fiche → DI avec photo → visible sur le PC en moins de 30 s (serveur)
# ---------------------------------------------------------------------------

class TestRecetteTelephone(CasRecette):

    def test_telephone_serveur_qr_fiche_di_photo_visible_sur_le_pc(self):
        """Lot 7 (T161) : le chemin réel d'un téléphone — l'étiquette porte l'adresse de la porte (http), la porte
        conduit un téléphone qui fait confiance au PC atelier à l'application en https sur la même fiche, l'appareil
        enrôlé (invitation du responsable, POST /api/enroler ; l'écran vient à T156) signale avec photo, le PC
        (client 127.0.0.1, responsable connecté) voit la demande sans recharger."""
        pc = self.page
        pc.set_viewport_size({"width": 1440, "height": 900})
        preregler_profil(self.contexte, "responsable")
        with ServeurAtelier() as serveur:
            # PC : le responsable est connecté (cookie de session posé d'avance ; l'écran de connexion est testé par
            # tests/test_acces_ecrans.py, T155)
            cookie = connecter(serveur.url_pc, "nicolas.briand").cookie
            self.contexte.add_cookies([{"name": "id", "value": cookie.split("=", 1)[1], "url": serveur.url_pc,
                                        "httpOnly": True, "sameSite": "Lax"}])
            # PC : lit le QR de la fiche de PO-02 (comme l'appareil photo le ferait) : l'adresse de la porte
            pc.goto(serveur.url_pc + "/#/equipement/" + POMPE)
            attendre_pret(pc)
            pc.wait_for_selector(".parc-qr-carte svg.qr-svg")
            url_qr = pc.evaluate(LIRE_QR_FICHE_JS)
            self.assertEqual(url_qr, serveur.url_porte + "/#/equipement/" + POMPE)
            print("\n  [telephone] QR de %s relu par jsQR : %s" % (REPERE_POMPE, url_qr))
            # PC : la liste des demandes reste affichée, sans rechargement
            self.menu("liste-di", pc)
            pc.wait_for_selector(".di-zone-tableau tbody tr.cliquable")
            pc.evaluate("window.__memePage = true")

            # Téléphone : fait confiance au PC atelier (certificat installé : ignore_https_errors), appareil enrôlé
            # sans profil mémorisé ; les tables qui ne sont pas au demandeur répondent 403 (vues comme absentes).
            telephone = self.navigateur.new_context(locale="fr-FR", viewport={"width": 375, "height": 812},
                                                    is_mobile=True, has_touch=True, ignore_https_errors=True)
            self.addCleanup(telephone.close)
            telephone.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
            enroler_appareil(serveur, telephone, "Karim Benali")
            self.autoriser_erreur(motif_refus_du_demandeur())
            tel = telephone.new_page()
            self.surveiller(tel)
            tel.goto(url_qr)                                      # la porte, en http…
            tel.wait_for_url(serveur.url_https + "/#/equipement/" + POMPE)   # … puis l'application en https, même fiche
            self.assertTrue(tel.evaluate("window.isSecureContext"))
            # Appareil enrôlé (T155) : le profil vient de la session, jamais l'écran de profil ; la route est gardée.
            attendre_pret(tel)
            self.assertEqual(tel.evaluate("App.profil"), {"type": "demandeur", "nom": "Karim Benali", "technicienId": ""})
            self.assertTrue(tel.evaluate("App.session.appareil"))
            self.assertEqual(tel.evaluate("location.hash"), "#/equipement/" + POMPE)
            tel.wait_for_function("(r) => document.querySelector('#contenu h1') && document.querySelector('#contenu h1').textContent.includes(r)",
                                  arg=REPERE_POMPE)
            self.sans_defilement_horizontal("fiche " + REPERE_POMPE, tel)
            tel.click("a.parc-signaler")
            tel.wait_for_selector(".di-formulaire")
            self.assertIn(REPERE_POMPE, tel.inner_text(".selecteur-choisi"))
            tel.fill("input[name=symptome]", "Vibrations anormales du moteur")
            tel.click("label.tuile:has(input[value='dégradé'])")
            tel.locator(".di-fichier-photo").set_input_files(fichier_png(3000, 2000))
            tel.wait_for_selector(".di-apercu:not([hidden]) img")
            self.sans_defilement_horizontal("nouvelle DI", tel)
            tel.click(".di-envoyer")
            tel.wait_for_selector(".di-numero")
            confirmation = time.monotonic()
            numero = tel.inner_text(".di-numero")
            self.sans_defilement_horizontal("confirmation", tel)

            # PC : la DI apparaît d'elle-même (rafraichissement_s = 20 du jeu de démo)
            pc.wait_for_function(
                "(n) => document.querySelector('.di-zone-tableau') && document.querySelector('.di-zone-tableau').innerText.includes(n)",
                arg=numero, timeout=30000)
            delai = time.monotonic() - confirmation
            print("\n  [telephone] DI %s visible sur le PC %.1f s après la confirmation" % (numero, delai))
            self.assertLess(delai, 30)
            self.assertTrue(pc.evaluate("window.__memePage === true"), "le PC a rechargé la page")

            # Disque : la DI et sa photo JPEG réduite à 1280 px
            demande = ligne_par_id(serveur.dossier / "demandes.csv", numero)
            self.assertEqual((demande["demandeur"], demande["equipement_id"]), ("Karim Benali", POMPE))
            self.assertRegex(demande["photo"], MOTIF_PHOTO)
            largeur, hauteur = dimensions_jpeg((serveur.dossier / "documents" / demande["photo"]).read_bytes())
            self.assertLessEqual(max(largeur, hauteur), 1280)


# ---------------------------------------------------------------------------
# 5. Habilitation : OT sur AE-03 (BR) affecté au technicien dont la BR est échue (serveur, démo)
# ---------------------------------------------------------------------------

class TestRecetteHabilitation(CasRecette):

    def jouer(self):
        page = self.page
        self.choisir_profil("responsable")
        self.menu("liste-ot")
        page.click("#ot-nouveau")
        page.wait_for_selector("#form-nouvel-ot")
        page.fill("#ot-nouveau-equipement input[type=search]", REPERE_BR)
        page.click("#ot-nouveau-equipement .selecteur-option[data-id='%s']" % EQUIPEMENT_BR)
        page.fill("#form-nouvel-ot [name=titre]", REPERE_BR + " — resserrage des borniers")
        page.click("#form-nouvel-ot button[type=submit]")
        page.wait_for_selector(".ot-fiche .ot-numero")
        ot_id = page.inner_text(".ot-fiche .ot-numero")
        date_prevue = dans_deux_jours()
        self.onglet("preparation")
        page.select_option("#form-preparation [name=technicien_id]", TECHNICIEN_BR_ECHUE)
        page.fill("#form-preparation [name=date_prevue]", date_prevue)
        page.dispatch_event("#form-preparation [name=date_prevue]", "change")
        page.wait_for_selector("#form-preparation .ot-zone-habilitation .alerte")
        self.assertIn("BR", page.inner_text("#form-preparation .ot-zone-habilitation"))
        page.click("#form-preparation button[type=submit]")
        # RG8 bloquante (T437, D186) : l'affectation est refusée ; la fenêtre « passer outre » du responsable (T438)
        # est annulée : rien n'est écrit, le refus est redit.
        page.click("dialog.ot-fenetre-derogation .fenetre-actions .btn-fantome")
        self.attendre_toast("Affectation refusée")
        self.assertIn("(%s) n'a pas d'habilitation valide au %s : BR (échue le " % (
            TECHNICIEN_BR_ECHUE, "/".join(reversed(date_prevue.split("-")))), page.inner_text("#toast"))
        return ot_id

    def test_habilitation_serveur(self):
        with ServeurPrevo() as serveur:
            self.demarrer_serveur_sans_profil(serveur)
            ot_id = self.jouer()
            _, journal = lire_csv(serveur.dossier / "journal.csv")
            self.assertEqual([j["action"] for j in journal if j["id_ligne"] == ot_id and "habilitation" in j["action"]], [])
            self.assertEqual(ligne_par_id(serveur.dossier / "ordres_travail.csv", ot_id)["technicien_id"], "")

    def test_habilitation_demo(self):
        self.demarrer_demo_sans_profil()
        ot_id = self.jouer()
        etat = self.page.evaluate("""async (id) => { await Donnees.rechargerTable('journal');
            await Donnees.rechargerTable('ordres_travail');
            return { entrees: Donnees.lignes('journal').filter((j) => j.id_ligne === id && j.action.includes('habilitation'))
              .map((j) => j.action), technicien: Donnees.trouver('ordres_travail', id).technicien_id }; }""", ot_id)
        self.assertEqual(etat, {"entrees": [], "technicien": ""})


# ---------------------------------------------------------------------------
# 6. Sauvegarde : ligne supprimée par erreur, restaurée par les Paramètres (serveur)
# ---------------------------------------------------------------------------

class TestRecetteSauvegarde(CasRecette):

    PERDU = SCENARIOS["equipement_panne_unique"]      # BA-01

    def test_sauvegarde_serveur_ligne_supprimee_puis_restauree(self):
        page = self.page
        with ServeurPrevo() as serveur:
            # Rafraîchissement toutes les 2 s (paramètre de l'atelier) pour ne pas attendre 20 s.
            parametres = serveur.dossier / "parametres.csv"
            texte = parametres.read_bytes().decode("utf-8")
            self.assertIn("rafraichissement_s;'20", texte)
            parametres.write_bytes(texte.replace("rafraichissement_s;'20", "rafraichissement_s;'2").encode("utf-8"))
            chemin = serveur.dossier / "equipements.csv"
            original = chemin.read_bytes()
            entete, lignes = lire_csv(chemin)
            self.assertIn(self.PERDU, [l["id"] for l in lignes])

            self.demarrer_serveur_sans_profil(serveur)
            self.choisir_profil("responsable")
            self.menu("parametres")
            page.wait_for_selector("#btn-sauvegarder")
            page.click("#btn-sauvegarder")
            page.wait_for_selector("#nom-sauvegarde-creee")
            nom = page.inner_text("#nom-sauvegarde-creee")

            # La ligne de BA-01 est supprimée par erreur dans equipements.csv
            self.menu("parc")
            lien = "#parc-arbre a[href='#/equipement/%s']" % self.PERDU
            page.wait_for_selector(lien)
            ecrire_csv(chemin, entete, [l for l in lignes if l["id"] != self.PERDU])
            page.wait_for_selector(lien, state="detached", timeout=15000)

            # Restauration depuis les Paramètres (toutes les tables, choix par défaut)
            self.menu("parametres")
            page.click('button[data-restaurer="%s"]' % nom)
            page.wait_for_selector("#fenetre-restauration")
            page.click("dialog .fenetre-actions .btn-danger")
            page.wait_for_selector("#nom-copie-securite")
            self.menu("parc")
            page.wait_for_selector(lien)
            self.assertIn(self.PERDU, [l["id"] for l in lire_csv(chemin)[1]])
            self.assertEqual(chemin.read_bytes(), original)


# ---------------------------------------------------------------------------
# 7. Traversée de dossier refusée (serveur)
# ---------------------------------------------------------------------------

class TestRecetteTraversee(unittest.TestCase):

    def test_traversee_put_documents_refuse_et_serveur_intact(self):
        script = RACINE / "serveur.py"
        empreinte = hashlib.sha256(script.read_bytes()).hexdigest()
        with ServeurPrevo() as serveur:
            for chemin in ("/api/documents/../serveur.py", "/api/documents/..%2Fserveur.py",
                           "/api/documents/..%5Cserveur.py", "/api/documents/%2E%2E/serveur.py"):
                with self.subTest(chemin=chemin):
                    connexion = http.client.HTTPConnection("127.0.0.1", serveur.port, timeout=10)
                    try:
                        corps = b"print('pirate')\n"
                        connexion.putrequest("PUT", chemin)
                        connexion.putheader("X-Prevo", "1")
                        connexion.putheader("Content-Type", "application/octet-stream")
                        connexion.putheader("Content-Length", str(len(corps)))
                        connexion.endheaders(corps)
                        reponse = connexion.getresponse()
                        reponse.read()
                        self.assertGreaterEqual(reponse.status, 400, "%s accepté (%d)" % (chemin, reponse.status))
                        print("\n  [traversee] PUT %s -> %d" % (chemin, reponse.status))
                    finally:
                        connexion.close()
            self.assertFalse((serveur.dossier / "serveur.py").exists())
            self.assertFalse((serveur.dossier.parent / "serveur.py").exists())
        self.assertEqual(hashlib.sha256(script.read_bytes()).hexdigest(), empreinte)


# ---------------------------------------------------------------------------
# 8. Design : téléphone 360 px, grand écran 1440 px, badges, aucune erreur console (serveur)
# ---------------------------------------------------------------------------

class TestRecetteDesign(CasRecette):

    ECRANS = (
        ("#/accueil", "#contenu #bento"),                 # accueil « bento » du responsable (T90)
        ("#/di/nouvelle", ".di-formulaire"),
        ("#/equipement/" + POMPE, ".parc-qr-carte"),
        ("#/ot/" + SCENARIOS["ot_p1_ouvert"], ".ot-fiche .ot-numero"),
        ("#/ot/" + SCENARIOS["ot_statut_prepare"], ".ot-fiche .ot-numero"),
        ("#/di/" + SCENARIOS["di_nouvelle_degradee"], ".di-details"),
        ("#/ot", ".ot-liste-cartes .liste-cartes"),
    )

    def verifier_badges_priorite(self, contexte):
        badges = self.page.eval_on_selector_all(
            "#contenu .badge[class*='prio-p']",
            "els => els.filter(e => e.offsetParent !== null).map(e => [e.className, e.textContent.trim()])")
        self.assertTrue(badges, "aucun badge de priorité visible (%s)" % contexte)
        for classe, texte in badges:
            niveau = re.search(r"prio-p([1-4])", classe).group(1)
            self.assertEqual(texte, "P" + niveau, "%s : %s" % (contexte, classe))

    def test_design_serveur_360_et_1440(self):
        page = self.page
        page.set_viewport_size({"width": 360, "height": 740})
        preregler_profil(self.contexte, "responsable")
        with ServeurPrevo() as serveur:
            page.goto(serveur.url + "/")
            attendre_pret(page)
            for route, selecteur in self.ECRANS:
                with self.subTest(largeur=360, route=route):
                    page.evaluate("(r) => { location.hash = r; }", route)
                    page.wait_for_selector(selecteur)
                    self.sans_defilement_horizontal("360 px " + route)
                    self.assertEqual(page.evaluate(PETITES_ZONES_JS), [], "zones tactiles < 48 px sur " + route)
                    self.assertTrue(page.is_visible(".barre-bas"))
                    self.assertTrue(page.is_hidden(".menu-lateral"))
            self.verifier_badges_priorite("liste des OT, 360 px")

            page.set_viewport_size({"width": 1440, "height": 900})
            page.evaluate("location.hash = '#/ot'")
            page.wait_for_selector(".ot-liste-tableau tbody tr")
            self.assertTrue(page.is_visible(".menu-lateral"))
            self.assertTrue(page.is_hidden(".barre-bas"))
            self.sans_defilement_horizontal("1440 px #/ot")
            self.verifier_badges_priorite("liste des OT, 1440 px")
            page.evaluate("location.hash = '#/di'")
            page.wait_for_selector(".di-zone-tableau tbody tr.cliquable")
            self.verifier_badges_priorite("liste des DI, 1440 px")
        # Aucune erreur console sur tout le parcours : vérifié par CasNavigateur.tearDown.


if __name__ == "__main__":
    unittest.main()
