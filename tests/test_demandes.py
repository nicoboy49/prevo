"""Tests du module Demandes d'intervention (js/modules/demandes.js, tâche T13).

Couvre (ARCHITECTURE.md §10 RG1 et RG2 ; brief §9 E2 et E3) :
    - la matrice de priorité RG2 (12 cas + sécurité + criticité absente), fonction pure ;
    - « Signaler » en mode serveur : photo 3000×2000 → JPEG ≤ 1280 px sur le disque, DI dans
      demandes.csv ; bandeau sécurité et P1 ;
    - liste : « à traiter » par défaut pour le responsable, « mes demandes » pour le demandeur ;
    - décisions du responsable : accepter (OT créé et lié, priorité modifiée avec motif
      journalisé), refuser (motif obligatoire, visible du demandeur), regrouper, différer ;
    - deux pages qui acceptent la même DI → un seul OT, message clair sur la seconde
      (y compris la course exacte qui passe par les conflits d'écriture, 409 autorisés
      précisément sur ces deux fichiers) ;
    - création en mode démo (file://) ; téléphone 375 px sans défilement horizontal.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_demandes.py" -v
"""
import csv
import datetime
import io
import re
import struct
import unittest
import zlib
from pathlib import Path

from commun import (CasNavigateur, ServeurPrevo, attendre_pret, charger_scripts, preregler_profil,
                    url_fichier)

# Chromium écrit « Failed to load resource » (console.error) pour toute réponse HTTP >= 400.
# Seul le test de la course exacte provoque des 409, sur ces deux fichiers uniquement :
CONFLIT_ORDRES = re.compile(r"status of 409.*/api/csv/ordres_travail")
CONFLIT_DEMANDES = re.compile(r"status of 409.*/api/csv/demandes")

MESSAGE_DEJA_TRAITEE = "Cette demande a déjà été traitée sur un autre poste"
MOTIF_PHOTO = re.compile(r"^photo-\d{8}-\d{6}-[A-Z0-9]{4}\.jpg$")


# ---------------------------------------------------------------------------
# Outils : CSV du serveur de test, image PNG, dimensions d'un JPEG
# ---------------------------------------------------------------------------

def lire_csv(chemin):
    """Lignes d'un CSV de Prévo (BOM, `;`) en dictionnaires ; apostrophe de protection retirée."""
    texte = Path(chemin).read_text(encoding="utf-8-sig")
    lignes = []
    for ligne in csv.DictReader(io.StringIO(texte), delimiter=";"):
        lignes.append({cle: (valeur[1:] if valeur.startswith("'") else valeur) for cle, valeur in ligne.items()})
    return lignes


def ligne_par_id(chemin, identifiant):
    for ligne in lire_csv(chemin):
        if ligne["id"] == identifiant:
            return ligne
    return None


def png(largeur, hauteur):
    """Image PNG RVB (bandes de couleur) écrite sans bibliothèque : zlib + struct."""
    bandes = [b"\xd0\x40\x30", b"\x30\x80\xd0", b"\xe0\xc0\x40", b"\x40\xb0\x60"]
    lignes_brutes = []
    for y in range(hauteur):
        couleur = bandes[(y * len(bandes)) // hauteur]
        lignes_brutes.append(b"\x00" + couleur * (largeur // 2) + b"\xf0\xf0\xf0" * (largeur - largeur // 2))
    donnees = zlib.compress(b"".join(lignes_brutes), 6)

    def bloc(type_bloc, contenu):
        return (struct.pack(">I", len(contenu)) + type_bloc + contenu
                + struct.pack(">I", zlib.crc32(type_bloc + contenu) & 0xFFFFFFFF))

    entete = struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", entete) + bloc(b"IDAT", donnees) + bloc(b"IEND", b"")


def dimensions_jpeg(octets):
    """(largeur, hauteur) lues dans le segment SOF d'un JPEG."""
    if octets[:2] != b"\xff\xd8":
        raise AssertionError("ce n'est pas un JPEG (début %r)" % octets[:4])
    position = 2
    while position < len(octets):
        if octets[position] != 0xFF:
            position += 1
            continue
        marqueur = octets[position + 1]
        if marqueur in (0xD8, 0x01) or 0xD0 <= marqueur <= 0xD7:
            position += 2
            continue
        longueur = struct.unpack(">H", octets[position + 2:position + 4])[0]
        if 0xC0 <= marqueur <= 0xCF and marqueur not in (0xC4, 0xC8, 0xCC):
            hauteur, largeur = struct.unpack(">HH", octets[position + 5:position + 9])
            return largeur, hauteur
        position += 2 + longueur
    raise AssertionError("segment SOF introuvable dans le JPEG")


def fichier_png(largeur, hauteur, nom="photo.png"):
    return {"name": nom, "mimeType": "image/png", "buffer": png(largeur, hauteur)}


# ---------------------------------------------------------------------------
# Règle pure RG2
# ---------------------------------------------------------------------------

class TestPrioriteCalculee(CasNavigateur):

    MATRICE = {
        ("A", "gêne"): "P2", ("A", "dégradé"): "P1", ("A", "arrêt"): "P1", ("A", "sécurité"): "P1",
        ("B", "gêne"): "P3", ("B", "dégradé"): "P2", ("B", "arrêt"): "P1", ("B", "sécurité"): "P1",
        ("C", "gêne"): "P4", ("C", "dégradé"): "P3", ("C", "arrêt"): "P2", ("C", "sécurité"): "P1",
    }

    def test_matrice_complete_securite_et_criticite_absente(self):
        charger_scripts(self.page, ["js/schema.js", "js/donnees.js", "js/interface.js", "js/modules/demandes.js"])
        calcul = "([c, i]) => Demandes.prioriteCalculee(c, i)"
        # 12 cas : 3 criticités × 4 impacts (sécurité → toujours P1)
        for (criticite, impact), attendu in self.MATRICE.items():
            with self.subTest(criticite=criticite, impact=impact):
                self.assertEqual(self.page.evaluate(calcul, [criticite, impact]), attendu)
        # Criticité absente ou inconnue → B
        for criticite in ("", None, "Z"):
            with self.subTest(criticite=criticite):
                self.assertEqual(self.page.evaluate(calcul, [criticite, "gêne"]), "P3")
                self.assertEqual(self.page.evaluate(calcul, [criticite, "dégradé"]), "P2")
                self.assertEqual(self.page.evaluate(calcul, [criticite, "sécurité"]), "P1")
        # Écritures approximatives acceptées ; impact inconnu → pas de priorité
        self.assertEqual(self.page.evaluate(calcul, ["c", "Securite"]), "P1")
        self.assertEqual(self.page.evaluate(calcul, [" a ", "ARRET"]), "P1")
        self.assertEqual(self.page.evaluate(calcul, ["C", "gene"]), "P4")
        self.assertEqual(self.page.evaluate(calcul, ["A", ""]), "")
        self.assertEqual(self.page.evaluate(calcul, ["A", "panne"]), "")
        # Type d'OT proposé à l'acceptation
        self.assertEqual(self.page.evaluate("Demandes.typePropose('P1')"), "correctif immédiat")
        self.assertEqual(self.page.evaluate("Demandes.typePropose('P2')"), "correctif différé")


# ---------------------------------------------------------------------------
# Mode serveur
# ---------------------------------------------------------------------------

class CasDemandes(CasNavigateur):

    def ouvrir(self, serveur, route, page=None):
        page = page or self.page
        page.goto(serveur.url + "/" + route)
        attendre_pret(page)
        return page

    def aller(self, route, selecteur, page=None):
        """Change de route dans la page (sans rechargement) et attend un élément de l'écran."""
        page = page or self.page
        page.evaluate("(route) => { location.hash = route; }", route)
        page.wait_for_selector(selecteur)

    def changer_profil(self, type_profil, nom="", page=None):
        page = page or self.page
        page.evaluate("([t, n]) => localStorage.setItem('prevo.profil', JSON.stringify({type: t, nom: n, technicienId: ''}))",
                      [type_profil, nom])
        page.reload()
        attendre_pret(page)

    def attendre_toast(self, texte, page=None):
        (page or self.page).wait_for_function(
            "(t) => document.getElementById('toast').textContent.includes(t)", arg=texte)

    def lignes_tableau(self, page=None):
        return (page or self.page).locator(".di-zone-tableau tbody tr.cliquable")

    def sans_defilement_horizontal(self, page=None):
        largeurs = (page or self.page).evaluate(
            "[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal : %r" % (largeurs,))


class TestServeurSignaler(CasDemandes):

    def test_serveur_creation_avec_photo_3000x2000_jpeg_reduit_et_di_dans_le_csv(self):
        preregler_profil(self.contexte, "demandeur", "Lucie Martin")
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/di/nouvelle?equipement=EQ-0005")
            # Équipement prérempli par ?equipement=
            self.assertTrue(page.is_visible(".selecteur-choisi"))
            self.assertIn("PO-02", page.inner_text(".selecteur-choisi"))
            # Symptôme par une suggestion (libellé des codes symptôme)
            page.click(".di-puce[data-symptome='Fuite']")
            self.assertEqual(page.input_value("input[name=symptome]"), "Fuite")
            page.click("label.tuile:has(input[value='dégradé'])")
            self.assertEqual(page.inner_text(".di-priorite .badge"), "P2")      # B × dégradé
            self.assertEqual(page.locator(".bandeau-securite").count(), 0)
            page.fill("textarea[name=description]", "Goutte à goutte sous la garniture côté moteur.")
            self.assertIsNotNone(page.get_attribute("textarea[name=description]", "data-dictee"))
            # Photo 3000 × 2000 : aperçu réduit avant l'envoi
            champ = page.locator(".di-fichier-photo")
            self.assertEqual(champ.get_attribute("accept"), "image/*")
            self.assertEqual(champ.get_attribute("capture"), "environment")
            champ.set_input_files(fichier_png(3000, 2000))
            page.wait_for_selector(".di-apercu:not([hidden]) img")
            page.wait_for_function("document.querySelector('.di-apercu-image').naturalWidth > 0")
            self.assertEqual(page.evaluate("document.querySelector('.di-apercu-image').naturalWidth"), 1280)

            page.click(".di-envoyer")
            page.wait_for_selector(".di-numero")
            numero = page.inner_text(".di-numero")
            self.assertEqual(numero, "DI-%d-0076" % 2026)   # identifiant annuel : 75 DI 2026 dans la démo
            self.assertIn("Demande envoyée", page.inner_text("#contenu"))

            # Sur le disque : la DI et la photo (JPEG, plus grand côté = 1280 px)
            ligne = ligne_par_id(serveur.dossier / "demandes.csv", numero)
            self.assertIsNotNone(ligne)
            self.assertEqual(ligne["demandeur"], "Lucie Martin")
            self.assertEqual(ligne["equipement_id"], "EQ-0005")
            self.assertEqual(ligne["symptome"], "Fuite")
            self.assertEqual(ligne["impact"], "dégradé")
            self.assertEqual(ligne["statut"], "Nouvelle")
            self.assertEqual(ligne["description"], "Goutte à goutte sous la garniture côté moteur.")
            self.assertRegex(ligne["date_heure"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
            self.assertRegex(ligne["photo"], MOTIF_PHOTO)
            octets = (serveur.dossier / "documents" / ligne["photo"]).read_bytes()
            largeur, hauteur = dimensions_jpeg(octets)
            self.assertEqual(max(largeur, hauteur), 1280)
            self.assertEqual((largeur, hauteur), (1280, 853))

            # La fiche affiche la photo (urlDocument) et le lien vers l'équipement
            page.click("a:has-text('Voir ma demande')")
            page.wait_for_selector(".di-details")
            page.wait_for_function("document.querySelector('.di-photo-image').naturalWidth > 0")
            self.assertEqual(page.get_attribute(".di-details a[href^='#/equipement/']", "href"), "#/equipement/EQ-0005")

    def test_serveur_bandeau_securite_et_priorite_p1(self):
        preregler_profil(self.contexte, "demandeur", "Paul Dubois")
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/di/nouvelle?equipement=EQ-0006")     # PO-03, criticité C
            page.click("label.tuile:has(input[value='gêne'])")
            self.assertEqual(page.inner_text(".di-priorite .badge"), "P4")
            self.assertEqual(page.locator(".bandeau-securite").count(), 0)
            page.click("label.tuile:has(input[value='sécurité'])")
            self.assertTrue(page.is_visible(".bandeau-securite"))
            self.assertIn("Danger : mettez la zone en sécurité et prévenez votre responsable",
                          page.inner_text(".bandeau-securite"))
            self.assertEqual(page.get_attribute(".bandeau-securite", "role"), "alert")
            self.assertEqual(page.inner_text(".di-priorite .badge"), "P1")
            # Un autre impact retire le bandeau
            page.click("label.tuile:has(input[value='arrêt'])")
            self.assertEqual(page.locator(".bandeau-securite").count(), 0)
            self.assertEqual(page.inner_text(".di-priorite .badge"), "P2")
            # Champs obligatoires : messages sous les champs, rien d'écrit
            page.click("label.tuile:has(input[value='sécurité'])")
            page.click(".di-envoyer")
            self.assertIn("Décrivez", page.inner_text("[data-champ=symptome] .erreur-champ"))
            self.assertEqual(len(lire_csv(serveur.dossier / "demandes.csv")), 75)
            page.fill("input[name=symptome]", "Fumée qui sort du coffret moteur")
            page.click(".di-envoyer")
            page.wait_for_selector(".di-numero")
            numero = page.inner_text(".di-numero")
            # Rappel du danger sur la confirmation, DI « sécurité » écrite
            self.assertTrue(page.is_visible(".bandeau-securite"))
            self.assertEqual(ligne_par_id(serveur.dossier / "demandes.csv", numero)["impact"], "sécurité")
            self.assertEqual(page.evaluate("(id) => Demandes.prioriteCalculee('C', Donnees.trouver('demandes', id).impact)", numero), "P1")


class TestServeurListe(CasDemandes):

    def test_serveur_mes_demandes_du_demandeur(self):
        preregler_profil(self.contexte, "demandeur", "Lucas Perrot")
        page = self.page
        with ServeurPrevo() as serveur:
            toutes = lire_csv(serveur.dossier / "demandes.csv")
            les_siennes = [l for l in toutes if l["demandeur"] == "Lucas Perrot"]
            self.assertGreater(len(les_siennes), 2)
            self.ouvrir(serveur, "#/di")
            self.assertEqual(page.input_value("select[name=portee]"), "mes")
            self.assertEqual(page.input_value("select[name=statut]"), "tous")
            self.assertEqual(self.lignes_tableau().count(), len(les_siennes))
            texte_tableau = page.inner_text(".di-zone-tableau")
            for ligne in les_siennes:
                self.assertIn(ligne["id"], texte_tableau)
            # Sa demande différée montre le motif du report
            self.assertIn("arrêt programmé de fin octobre", texte_tableau)
            # Toutes les demandes
            page.select_option("select[name=portee]", "toutes")
            self.assertEqual(self.lignes_tableau().count(), len(toutes))
            # Recherche
            page.fill("input[name=recherche]", "fardeleuse")
            attendues = [l for l in toutes if "fardeleuse" in (l["symptome"] + l["description"]
                                                               + l["motif_decision"]).lower()
                         or l["equipement_id"] == "EQ-0026"]
            self.assertEqual(self.lignes_tableau().count(), len(attendues))
            # Tri par clic sur l'en-tête (n° croissant)
            page.fill("input[name=recherche]", "")
            page.click(".di-zone-tableau th .tri[data-cle='id']")
            self.assertEqual(self.lignes_tableau().first.locator("td").first.inner_text(), "DI-2026-0001")

    def test_serveur_responsable_voit_les_demandes_a_traiter_par_defaut(self):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurPrevo() as serveur:
            nouvelles = [l["id"] for l in lire_csv(serveur.dossier / "demandes.csv") if l["statut"] == "Nouvelle"]
            self.assertEqual(sorted(nouvelles), ["DI-2026-0069", "DI-2026-0071", "DI-2026-0072", "DI-2026-0073"])
            self.ouvrir(serveur, "#/di")
            self.assertEqual(page.input_value("select[name=statut]"), "Nouvelle")
            self.assertEqual(page.locator("select[name=portee]").count(), 0)      # le responsable n'a pas de nom
            self.assertEqual(self.lignes_tableau().count(), 4)
            # La DI sécurité (AE-04, criticité C) est en P1
            ligne_securite = self.lignes_tableau().filter(has_text="DI-2026-0073")
            self.assertEqual(ligne_securite.locator(".badge.prio-p1").inner_text(), "P1")
            # Lien de l'accueil vers une liste filtrée : ?statut=
            self.aller("#/di?statut=Refusée", ".di-zone-tableau")
            page.wait_for_function("document.querySelector('select[name=statut]').value === 'Refusée'")
            self.assertEqual(self.lignes_tableau().count(), 1)
            self.assertIn("hors périmètre de la maintenance", page.inner_text(".di-zone-tableau"))
            # Clic sur une ligne → fiche
            self.lignes_tableau().first.locator("td").nth(3).click()
            page.wait_for_selector(".di-details")
            self.assertEqual(page.evaluate("location.hash"), "#/di/DI-2026-0065")
            self.assertEqual(page.locator(".di-panneau-decision").count(), 0)   # déjà décidée


    def test_serveur_lien_de_l_accueil_statut_nouvelle_preselectionne(self):
        # Technicien : sans paramètre, la liste montre tous les statuts ; ?statut=Nouvelle doit filtrer.
        preregler_profil(self.contexte, "technicien", "", "TEC-0001")
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/di")
            self.assertEqual(page.input_value("select[name=statut]"), "tous")
            self.assertGreater(self.lignes_tableau().count(), 4)
            self.ouvrir(serveur, "#/di?statut=Nouvelle")
            self.assertEqual(page.input_value("select[name=statut]"), "Nouvelle")
            numeros = sorted(page.eval_on_selector_all(
                ".di-zone-tableau tbody tr.cliquable td:first-child", "(cellules) => cellules.map((c) => c.textContent.trim())"))
            self.assertEqual(numeros, ["DI-2026-0069", "DI-2026-0071", "DI-2026-0072", "DI-2026-0073"])


class TestServeurDecisions(CasDemandes):

    def test_serveur_acceptation_po02_degrade_cree_un_ot_p2_lie(self):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/accueil")
            di = page.evaluate("""Demandes.creer({ equipement_id: 'EQ-0005', symptome: 'Fuite à la garniture',
                impact: 'dégradé', description: 'Flaque sous la pompe.', demandeur: 'Lucie Martin' })""")
            self.aller("#/di/" + di, ".di-panneau-decision")
            page.click("[data-decision=accepter]")
            page.wait_for_selector("dialog .di-fenetre-accepter")
            self.assertEqual(page.input_value("dialog select[name=priorite]"), "P2")
            self.assertEqual(page.input_value("dialog select[name=type]"), "correctif différé")
            self.assertTrue(page.is_hidden("dialog .di-champ-motif"))
            demain = (datetime.date.today() + datetime.timedelta(days=1))
            self.assertIn(demain.strftime("%d/%m/%Y"), page.inner_text("dialog .di-date-prevue"))
            page.click("dialog button:has-text(\"Créer l'ordre de travail\")")
            page.wait_for_function("location.hash.startsWith('#/ot/')")
            ot_id = page.evaluate("decodeURIComponent(location.hash.slice(5))")
            self.assertEqual(ot_id, "OT-2026-0109")

            ot = ligne_par_id(serveur.dossier / "ordres_travail.csv", ot_id)
            self.assertEqual(ot["origine"], "DI")
            self.assertEqual(ot["di_id"], di)
            self.assertEqual(ot["equipement_id"], "EQ-0005")
            self.assertEqual(ot["priorite"], "P2")
            self.assertEqual(ot["type"], "correctif différé")
            self.assertEqual(ot["statut"], "Créé")
            self.assertEqual(ot["titre"], "Fuite à la garniture")
            self.assertEqual(ot["travail_a_faire"], "Flaque sous la pompe.")
            self.assertRegex(ot["date_creation"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
            self.assertEqual(ot["date_prevue"], demain.isoformat())
            demande = ligne_par_id(serveur.dossier / "demandes.csv", di)
            self.assertEqual(demande["statut"], "Acceptée")
            self.assertEqual(demande["ot_id"], ot_id)
            self.assertRegex(demande["date_decision"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

            # La fiche de la DI montre le lien vers l'OT, plus de panneau de décision
            self.aller("#/di/" + di, ".di-suivi")
            self.assertEqual(page.get_attribute(".di-suivi a[href^='#/ot/']", "href"), "#/ot/" + ot_id)
            self.assertEqual(page.locator(".di-panneau-decision").count(), 0)

    def test_serveur_acceptation_avec_priorite_modifiee_motif_obligatoire_et_journal(self):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurPrevo() as serveur:
            # DI-2026-0072 : PO-03 (criticité C) × gêne → P4
            self.ouvrir(serveur, "#/di/DI-2026-0072")
            page.click("[data-decision=accepter]")
            page.wait_for_selector("dialog .di-fenetre-accepter")
            self.assertEqual(page.input_value("dialog select[name=priorite]"), "P4")
            self.assertIn("prochain arrêt", page.inner_text("dialog .di-date-prevue"))
            page.select_option("dialog select[name=priorite]", "P1")
            self.assertEqual(page.input_value("dialog select[name=type]"), "correctif immédiat")
            page.select_option("dialog select[name=priorite]", "P3")
            self.assertEqual(page.input_value("dialog select[name=type]"), "correctif différé")
            self.assertTrue(page.is_visible("dialog .di-champ-motif"))
            # Sans motif : refusé, la fenêtre reste ouverte
            page.click("dialog button:has-text(\"Créer l'ordre de travail\")")
            self.assertTrue(page.is_visible("dialog .di-champ-motif .erreur-champ"))
            self.assertEqual(ligne_par_id(serveur.dossier / "demandes.csv", "DI-2026-0072")["statut"], "Nouvelle")
            page.fill("dialog textarea[name=motif]", "pompe de secours en panne")
            page.click("dialog button:has-text(\"Créer l'ordre de travail\")")
            page.wait_for_function("location.hash.startsWith('#/ot/')")
            ot_id = page.evaluate("decodeURIComponent(location.hash.slice(5))")
            ot = ligne_par_id(serveur.dossier / "ordres_travail.csv", ot_id)
            self.assertEqual(ot["priorite"], "P3")
            self.assertEqual(ot["date_prevue"], (datetime.date.today() + datetime.timedelta(days=7)).isoformat())
            # Journal (écrit par ajout, relu sur le disque)
            page.wait_for_function("""async () => { await Donnees.rafraichir();
                return Donnees.lignes('journal').some((l) => l.action.includes('priorité P4 → P3 : pompe de secours en panne')); }""")
            journal = (serveur.dossier / "journal.csv").read_text(encoding="utf-8-sig")
            self.assertIn("priorité P4 → P3 : pompe de secours en panne", journal)
            # API : un changement de priorité sans motif est refusé
            message = page.evaluate("""async () => {
                try { await Demandes.accepter('DI-2026-0069', { priorite: 'P1' }); return 'accepté'; }
                catch (e) { return e.constructor.name + ' : ' + e.message; } }""")
            self.assertIn("ErreurValidation", message)
            self.assertIn("motif", message)
            # API : P4 → pas de date prévue
            ot_p4 = page.evaluate("Demandes.accepter('DI-2026-0069')")     # ET-01 (C) × gêne → P4
            self.assertEqual(ligne_par_id(serveur.dossier / "ordres_travail.csv", ot_p4)["priorite"], "P4")
            self.assertEqual(ligne_par_id(serveur.dossier / "ordres_travail.csv", ot_p4)["date_prevue"], "")

    def test_serveur_refus_sans_motif_impossible_et_motif_visible_du_demandeur(self):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/di/DI-2026-0071")          # demandeur : Sarah Colin
            page.click("[data-decision=refuser]")
            page.wait_for_selector("dialog textarea[name=motif]")
            page.click("dialog button:has-text('Refuser la demande')")
            self.assertTrue(page.is_visible("dialog .erreur-champ"))
            self.assertIn("obligatoire", page.inner_text("dialog .erreur-champ"))
            self.assertEqual(ligne_par_id(serveur.dossier / "demandes.csv", "DI-2026-0071")["statut"], "Nouvelle")
            # API : motif vide refusé aussi
            message = page.evaluate("""async () => {
                try { await Demandes.refuser('DI-2026-0071', '   '); return 'refusée'; }
                catch (e) { return e.constructor.name + ' : ' + e.message; } }""")
            self.assertIn("ErreurValidation", message)
            page.fill("dialog textarea[name=motif]", "Fuite déjà connue : la presse est remplacée en novembre.")
            page.click("dialog button:has-text('Refuser la demande')")
            self.attendre_toast("refusée")
            page.wait_for_selector(".di-suivi:has-text('Refusée par le responsable')")
            ligne = ligne_par_id(serveur.dossier / "demandes.csv", "DI-2026-0071")
            self.assertEqual(ligne["statut"], "Refusée")
            self.assertEqual(ligne["motif_decision"], "Fuite déjà connue : la presse est remplacée en novembre.")

            # Le demandeur voit le motif dans sa liste
            self.changer_profil("demandeur", "Sarah Colin")
            self.aller("#/di", ".di-zone-tableau")
            ligne_tableau = self.lignes_tableau().filter(has_text="DI-2026-0071")
            self.assertIn("la presse est remplacée en novembre", ligne_tableau.inner_text())
            self.assertIn("Refusée", ligne_tableau.inner_text())

    def test_serveur_regroupement_avec_un_ot_ouvert_du_meme_equipement(self):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/accueil")
            # EM-01 (EQ-0026) a un OT ouvert : OT-2026-0107 (En cours)
            di = page.evaluate("""Demandes.creer({ equipement_id: 'EQ-0026', symptome: 'Films encore mal soudés',
                impact: 'dégradé', demandeur: 'Manon Duval' })""")
            self.aller("#/di/" + di, ".di-panneau-decision")
            self.assertTrue(page.is_enabled("[data-decision=regrouper]"))
            page.click("[data-decision=regrouper]")
            page.wait_for_selector("dialog .di-choix-ot")
            options = page.locator("dialog .di-choix-ot input[type=radio]")
            self.assertEqual(options.count(), 1)
            self.assertEqual(options.first.get_attribute("value"), "OT-2026-0107")
            page.click("dialog button:has-text('Regrouper')")
            page.wait_for_selector(".di-suivi a[href='#/ot/OT-2026-0107']")
            ligne = ligne_par_id(serveur.dossier / "demandes.csv", di)
            self.assertEqual(ligne["statut"], "Regroupée")
            self.assertEqual(ligne["ot_id"], "OT-2026-0107")
            # Aucun OT créé
            self.assertFalse(any(o["di_id"] == di for o in lire_csv(serveur.dossier / "ordres_travail.csv")))
            # Sans OT ouvert sur l'équipement (ET-01), « Regrouper » est grisé
            self.aller("#/di/DI-2026-0069", ".di-panneau-decision")
            self.assertTrue(page.is_disabled("[data-decision=regrouper]"))

    def test_serveur_report_puis_decision_toujours_possible(self):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/di/DI-2026-0072")
            page.click("[data-decision=differer]")
            page.wait_for_selector("dialog textarea[name=motif]")
            page.fill("dialog textarea[name=motif]", "À voir au prochain arrêt de la station")
            page.click("dialog button:has-text('Différer')")
            self.attendre_toast("différée")
            page.wait_for_selector(".di-suivi:has-text('Différée')")
            ligne = ligne_par_id(serveur.dossier / "demandes.csv", "DI-2026-0072")
            self.assertEqual(ligne["statut"], "Différée")
            self.assertEqual(ligne["motif_decision"], "À voir au prochain arrêt de la station")
            self.assertRegex(ligne["date_decision"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
            # Une DI différée peut encore être acceptée, regroupée ou refusée, plus différée
            self.assertTrue(page.is_visible("[data-decision=accepter]"))
            self.assertTrue(page.is_visible("[data-decision=refuser]"))
            self.assertEqual(page.locator("[data-decision=differer]").count(), 0)
            ot_id = page.evaluate("Demandes.accepter('DI-2026-0072')")
            self.assertEqual(ligne_par_id(serveur.dossier / "demandes.csv", "DI-2026-0072")["ot_id"], ot_id)


class TestServeurDeuxPostes(CasDemandes):

    def test_serveur_deux_pages_acceptent_la_meme_di_un_seul_ot(self):
        preregler_profil(self.contexte, "responsable")
        page_a = self.page
        page_b = self.contexte.new_page()
        self.surveiller(page_b)
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/di/DI-2026-0069", page_a)
            self.ouvrir(serveur, "#/di/DI-2026-0069", page_b)
            page_b.wait_for_selector(".di-panneau-decision")
            # Poste A accepte
            page_a.click("[data-decision=accepter]")
            page_a.click("dialog button:has-text(\"Créer l'ordre de travail\")")
            page_a.wait_for_function("location.hash.startsWith('#/ot/')")
            # Poste B (écran encore ouvert sur la DI « Nouvelle ») accepte à son tour
            page_b.click("[data-decision=accepter]")
            page_b.click("dialog button:has-text(\"Créer l'ordre de travail\")")
            self.attendre_toast(MESSAGE_DEJA_TRAITEE, page_b)
            # B montre l'état réel : acceptée, plus de décision possible
            page_b.wait_for_selector(".di-suivi:has-text('Acceptée')")
            self.assertEqual(page_b.locator(".di-panneau-decision").count(), 0)
            self.assertEqual(page_b.evaluate("location.hash"), "#/di/DI-2026-0069")
            ordres = [o for o in lire_csv(serveur.dossier / "ordres_travail.csv") if o["di_id"] == "DI-2026-0069"]
            self.assertEqual(len(ordres), 1)
            self.assertEqual(ligne_par_id(serveur.dossier / "demandes.csv", "DI-2026-0069")["ot_id"], ordres[0]["id"])

    def test_serveur_course_exacte_deux_acceptations_simultanees_un_seul_ot(self):
        """Les deux postes lisent la DI « Nouvelle » au même instant : la vérification préalable
        passe des deux côtés ; c'est l'enchaînement idempotent (D18) qui doit protéger."""
        self.autoriser_erreur(CONFLIT_ORDRES)
        self.autoriser_erreur(CONFLIT_DEMANDES)
        preregler_profil(self.contexte, "responsable")
        page_a = self.page
        page_b = self.contexte.new_page()
        self.surveiller(page_b)
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/di/DI-2026-0071", page_a)
            self.ouvrir(serveur, "#/di/DI-2026-0071", page_b)
            # Poste B : sa relecture préalable rend la copie qu'il avait (lecture « au même instant »)
            page_b.evaluate("() => { Donnees.rechargerTable = async (table) => Donnees.lignes(table); }")
            ot_a = page_a.evaluate("Demandes.accepter('DI-2026-0071')")
            resultat_b = page_b.evaluate("""async () => {
                try { return 'accepté : ' + await Demandes.accepter('DI-2026-0071'); }
                catch (e) { return e.constructor.name + ' : ' + e.message; } }""")
            self.assertIn("ErreurValidation", resultat_b)
            self.assertIn(MESSAGE_DEJA_TRAITEE, resultat_b)
            self.assertGreaterEqual(page_b.evaluate("Donnees.statistiques.conflits"), 2)
            ordres = [o for o in lire_csv(serveur.dossier / "ordres_travail.csv") if o["di_id"] == "DI-2026-0071"]
            self.assertEqual([o["id"] for o in ordres], [ot_a])
            self.assertEqual(ligne_par_id(serveur.dossier / "demandes.csv", "DI-2026-0071")["ot_id"], ot_a)


# ---------------------------------------------------------------------------
# Mode démo (file://)
# ---------------------------------------------------------------------------

class TestDemo(CasDemandes):

    def test_demo_creation_avec_photo_en_memoire(self):
        preregler_profil(self.contexte, "demandeur", "Lucie Martin")
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_selector("#btn-demo")
        page.click("#btn-demo")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.mode"), "demo")
        self.aller("#/di/nouvelle", ".di-formulaire")
        # Équipement choisi par la recherche
        page.fill(".selecteur-recherche input[type=search]", "PO-02")
        page.click(".selecteur-option[data-id='EQ-0005']")
        page.fill("input[name=symptome]", "Bruit de roulement")
        page.click("label.tuile:has(input[value='arrêt'])")
        self.assertEqual(page.inner_text(".di-priorite .badge"), "P1")          # B × arrêt
        page.locator(".di-fichier-photo").set_input_files(fichier_png(800, 600))
        page.wait_for_selector(".di-apercu:not([hidden])")
        page.click(".di-envoyer")
        page.wait_for_selector(".di-numero")
        numero = page.inner_text(".di-numero")
        self.assertRegex(numero, r"^DI-\d{4}-\d{4}$")
        demande = page.evaluate("(id) => Donnees.trouver('demandes', id)", numero)
        self.assertEqual(demande["statut"], "Nouvelle")
        self.assertEqual(demande["demandeur"], "Lucie Martin")
        self.assertRegex(demande["photo"], MOTIF_PHOTO)
        self.assertEqual(page.evaluate("App.adaptateur.documentsEnMemoire().map((d) => d.nom)"), [demande["photo"]])
        # Visible dans « mes demandes »
        self.aller("#/di", ".di-zone-tableau")
        self.assertIn(numero, page.inner_text(".di-zone-tableau"))
        self.assertEqual(self.lignes_tableau().count(), 1)


# ---------------------------------------------------------------------------
# Téléphone 375 px
# ---------------------------------------------------------------------------

class TestTelephone(CasDemandes):

    def setUp(self):
        super().setUp()
        # Contexte « téléphone » à la place du contexte de bureau
        self.contexte.close()
        self.contexte = self.navigateur.new_context(
            locale="fr-FR", viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True)
        self.contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)

    def hauteurs_trop_petites(self, selecteur):
        return self.page.evaluate("""(s) => Array.from(document.querySelectorAll(s))
            .filter((e) => e.offsetParent !== null && e.getBoundingClientRect().height < 48)
            .map((e) => e.outerHTML.slice(0, 80))""", selecteur)

    def test_telephone_375_signaler_liste_fiche_sans_defilement_horizontal(self):
        preregler_profil(self.contexte, "demandeur", "Paul Dubois")
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/di/nouvelle?equipement=EQ-0013")
            page.click("label.tuile:has(input[value='sécurité'])")
            self.assertTrue(page.is_visible(".bandeau-securite"))
            self.sans_defilement_horizontal()
            # Une seule colonne : les étapes ont toutes la même largeur
            largeurs = page.evaluate("Array.from(document.querySelectorAll('.di-etape')).map((e) => Math.round(e.getBoundingClientRect().width))")
            self.assertEqual(len(set(largeurs)), 1)
            # Gros boutons (gants) : ≥ 48 px
            for selecteur in (".tuile > span", ".di-puce", ".di-bouton-photo", ".di-envoyer",
                              ".selecteur-changer", "input[name=symptome]"):
                with self.subTest(selecteur=selecteur):
                    self.assertEqual(self.hauteurs_trop_petites(selecteur), [])
            # Liste : cartes, pas de tableau
            self.aller("#/di", ".di-cartes")
            self.assertTrue(page.is_visible(".di-cartes"))
            self.assertTrue(page.is_hidden(".di-zone-tableau"))
            self.assertIn("DI-2026-0073", page.inner_text(".di-cartes"))
            self.sans_defilement_horizontal()
            # Fiche avec le panneau de décision (responsable)
            self.changer_profil("responsable")
            self.aller("#/di/DI-2026-0073", ".di-panneau-decision")
            self.assertTrue(page.is_visible(".bandeau-securite"))
            self.assertEqual(self.hauteurs_trop_petites(".di-panneau-decision .btn"), [])
            self.sans_defilement_horizontal()


if __name__ == "__main__":
    unittest.main()
