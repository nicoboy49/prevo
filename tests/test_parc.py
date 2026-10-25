"""Tests du module Parc : js/modules/parc-*.js (objet Parc) et css/modules/parc.css (tâche T12).

Deux familles (le nom du test le dit) :
    demo    : index.html ouvert en file:// avec les données de démo (rien n'est écrit) ;
    serveur : serveur.py sur une copie du jeu de démo (ServeurPrevo) : on relit les CSV sur le disque.

Ce qui est vérifié : arborescence (ateliers, PO-02, sous-équipements), recherche, inactifs,
fiche PO-02 (consignation, historique avec ses OT et ses DI, articles liés), QR code relu par jsQR
(= App.urlFicheEquipement : « GMAO:… » en démo, URL en serveur), création / modification /
désactivation d'un équipement (ligne dans equipements.csv : BOM, repère protégé par une apostrophe),
repère en double refusé, boucle de parenté refusée, localisations, profil demandeur sans « Modifier »,
téléphone 375 px sans défilement horizontal.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_parc.py" -v
"""
import csv
import io
import re
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from commun import (CasNavigateur, RACINE, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo,
                    url_fichier)

DOSSIER_DEMO = RACINE / "donnees" / "demo"
# Identifiants des objets de scénario du jeu de démo (outils/generer_demo.py, ARCHITECTURE.md §14.8).
SCENARIOS = scenarios_demo()
# La démo décale ses dates du nombre de semaines entières écoulées depuis sa date de référence (§11).
JOUR_REFERENCE_DEMO = date(2026, 10, 19)


def date_demo_decalee(texte):
    """Date d'un fichier de la démo telle que l'écran la montre : la démo décale ses dates d'un nombre entier de
    semaines depuis JOUR_REFERENCE_DEMO, pour rester actuelle (un test qui attend la date brute ne passe que la
    semaine de référence)."""
    return date.fromisoformat(texte[:10]) + timedelta(weeks=(date.today() - JOUR_REFERENCE_DEMO).days // 7)
BOM = b"\xef\xbb\xbf"
LIBELLE_PO02 = "PO-02 — Pompe centrifuge eau de refroidissement"
RAPPEL_CONSIGNATION = "Cocher une case ne consigne rien : appliquez la procédure."
ESPACES = re.compile("[  ]")

LIRE_QR_JS = """async () => {
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


def lire_csv(dossier, nom):
    """Lit un CSV du disque : vérifie le BOM UTF-8 et renvoie (lignes en dict, texte brut)."""
    octets = (Path(dossier) / nom).read_bytes()
    assert octets.startswith(BOM), "BOM UTF-8 absent de " + nom
    texte = octets.decode("utf-8")[1:]
    return list(csv.DictReader(io.StringIO(texte, newline=""), delimiter=";")), texte


def ligne_par_id(lignes, identifiant):
    for ligne in lignes:
        if ligne["id"] == identifiant:
            return ligne
    return None


def espaces_simples(texte):
    return ESPACES.sub(" ", texte)


class CasParc(CasNavigateur):
    """Outils communs : ouvrir la démo ou un serveur, aller sur un écran, relire le QR."""

    def ouvrir_demo(self, route="#/parc"):
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-responsable")
        attendre_pret(page)
        self.aller(route)

    def ouvrir_serveur(self, serveur, profil="responsable", route="#/parc", **profil_extra):
        preregler_profil(self.contexte, profil, **profil_extra)
        self.page.goto(serveur.url + "/")
        attendre_pret(self.page)
        self.aller(route)

    def aller(self, route):
        self.page.evaluate("(r) => { location.hash = r; }", route)
        if route == "#/parc":
            self.page.wait_for_selector("#parc-arbre")
        else:
            self.page.wait_for_selector("#contenu .parc h1")
        # laisse l'affichage asynchrone (fiche) se terminer
        self.page.wait_for_function("document.querySelector('#contenu .parc') !== null")

    def reperes_visibles(self):
        """Repères des équipements affichés dans l'arborescence."""
        return self.page.locator("#parc-arbre a.feuille b").all_inner_texts()

    def sans_defilement_horizontal(self):
        largeurs = self.page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal : %r" % (largeurs,))

    def texte(self, selecteur):
        return espaces_simples(self.page.inner_text(selecteur))

    def remplir_equipement(self, repere, designation, **autres):
        page = self.page
        page.fill("#parc-formulaire [name=repere]", repere)
        page.fill("#parc-formulaire [name=designation]", designation)
        for nom, valeur in autres.items():
            champ = "#parc-formulaire [name=%s]" % nom
            if nom in ("localisation_id", "parent_id", "criticite", "statut"):
                page.select_option(champ, valeur)
            else:
                page.fill(champ, valeur)

    def enregistrer_formulaire(self):
        self.page.click("#parc-formulaire button[type=submit]")


# ---------------------------------------------------------------------------
# Démo (file://) : lecture seule en pratique
# ---------------------------------------------------------------------------

class TestParcDemo(CasParc):

    def test_demo_arborescence_ateliers_sous_equipements_et_api_exposee(self):
        self.ouvrir_demo()
        page = self.page
        libelles = page.locator("#parc-arbre summary b").all_inner_texts()
        for atelier in ("Atelier Usinage", "Atelier Assemblage-conditionnement", "Atelier Utilités"):
            self.assertIn(atelier, libelles)
        self.assertIn("Site des Trois Vallées", libelles)
        self.assertIn("PO-02", self.reperes_visibles())
        # PO-02 est un lien vers sa fiche
        self.assertEqual(page.locator("#parc-arbre a[href='#/equipement/EQ-0005']").count(), 1)
        # Un sous-équipement est rangé sous son parent : CP-01.SEC sous CP-01
        self.assertEqual(page.locator("#parc-arbre li:has(> a[href='#/equipement/EQ-0001']) > ul a[href='#/equipement/EQ-0002']").count(), 1)
        # Badges criticité et statut (CP-01 est à l'arrêt)
        ligne_cp01 = page.locator("#parc-arbre a[href='#/equipement/EQ-0001']")
        self.assertIn("Crit. A", ligne_cp01.inner_text())
        self.assertIn("arrêt", ligne_cp01.inner_text())
        # Boutons du responsable
        self.assertTrue(page.is_visible("text=Nouvel équipement"))
        self.assertTrue(page.is_visible("#parc-nouvelle-localisation"))
        # API pour les autres modules
        self.assertEqual(page.evaluate("Parc.libelleEquipement('EQ-0005')"), LIBELLE_PO02)
        self.assertEqual(page.evaluate("Parc.libelleEquipement('EQ-9999')"), "EQ-9999")
        self.assertEqual(page.evaluate("Parc.cheminLocalisation('LOC-0005')"),
                         "Site des Trois Vallées › Atelier Assemblage-conditionnement › Ligne de conditionnement")
        self.assertEqual(page.evaluate("Parc.cheminLocalisation('')"), "")

    def test_demo_recherche_par_repere_designation_marque_et_inactifs(self):
        self.ouvrir_demo()
        page = self.page
        self.assertNotIn("PE-01", self.reperes_visibles())          # PE-01 est inactif (rebut)

        page.fill("#parc-recherche", "pompe")
        self.assertEqual(sorted(self.reperes_visibles()), ["PO-01", "PO-02", "PO-03"])
        self.assertIn("3 équipements trouvés", self.texte(".parc-resultat"))
        # Les localisations sans résultat disparaissent
        self.assertNotIn("Atelier Usinage", page.locator("#parc-arbre summary b").all_inner_texts())

        page.fill("#parc-recherche", "HYDRONEL")                     # marque, sans tenir compte de la casse
        self.assertEqual(sorted(self.reperes_visibles()), ["PO-01", "PO-02"])

        page.fill("#parc-recherche", "cn-01")                        # repère : l'équipement et son sous-équipement
        self.assertEqual(sorted(self.reperes_visibles()), ["CN-01", "CN-01.BR"])

        page.fill("#parc-recherche", "zzzzzz")
        self.assertIn("Aucun équipement trouvé", self.texte("#parc-arbre"))

        # Inactifs
        page.fill("#parc-recherche", "perceuse")
        self.assertIn("Aucun équipement trouvé", self.texte("#parc-arbre"))
        page.check("#parc-inactifs")
        self.assertEqual(self.reperes_visibles(), ["PE-01"])
        self.assertIn("Inactif", page.inner_text("#parc-arbre a[href='#/equipement/EQ-0031']"))
        page.uncheck("#parc-inactifs")
        page.fill("#parc-recherche", "")
        self.assertNotIn("PE-01", self.reperes_visibles())

        # Replier / déplier
        page.click("#parc-replier")
        self.assertEqual(page.locator("#parc-arbre details[open]").count(), 0)
        page.click("#parc-replier")
        self.assertGreater(page.locator("#parc-arbre details[open]").count(), 0)

    def test_demo_fiche_po02_consignation_historique_articles_et_qr(self):
        self.ouvrir_demo("#/equipement/EQ-0005")
        page = self.page
        self.assertEqual(self.texte("#contenu h1"), LIBELLE_PO02)
        # Bloc consignation : rappel exact + procédure
        consignation = self.texte(".parc-consignation")
        self.assertIn(RAPPEL_CONSIGNATION, consignation)
        self.assertIn("Isoler la partie concernée du circuit d'eau et la vidanger.", consignation)
        # Fiche : libellés, dates en français, chemin de localisation
        fiche = self.texte(".valeurs")
        for attendu in ("Identifiant", "EQ-0005", "Hydronel", "HC 50-160", "HY-50-17-2987",
                        date_demo_decalee("2017-09-18").strftime("%d/%m/%Y"),
                        "Site des Trois Vallées › Atelier Utilités"):
            self.assertIn(attendu, fiche)
        # Historique : tous les OT et toutes les DI de PO-02 (moins de 20 chacun : tout est affiché), avec des liens
        ordres_po02 = [o for o in lire_csv(DOSSIER_DEMO, "ordres_travail.csv")[0] if o["equipement_id"] == "EQ-0005"]
        demandes_po02 = [d for d in lire_csv(DOSSIER_DEMO, "demandes.csv")[0] if d["equipement_id"] == "EQ-0005"]
        self.assertTrue(5 <= len(ordres_po02) <= 20, len(ordres_po02))
        self.assertTrue(3 <= len(demandes_po02) <= 20, len(demandes_po02))
        liens_ot = page.locator("#contenu a[href^='#/ot/OT-']").all_inner_texts()
        self.assertEqual(sorted(set(liens_ot)), sorted(o["id"] for o in ordres_po02))
        liens_di = page.locator("#contenu a[href^='#/di/DI-']").all_inner_texts()
        self.assertEqual(sorted(set(liens_di)), sorted(d["id"] for d in demandes_po02))
        # La dernière fuite de garniture : date de création (décalée comme la démo), type, priorité, statut
        fuite = ligne_par_id(ordres_po02, SCENARIOS["ot_fuite_garniture_po02"])
        self.assertEqual((fuite["type"], fuite["priorite"]), ("correctif différé", "P2"))
        decalage = timedelta(weeks=(date.today() - JOUR_REFERENCE_DEMO).days // 7)
        creation = date.fromisoformat(fuite["date_creation"][:10]) + decalage
        ordres = page.locator("#contenu table tr", has_text=fuite["id"]).first.inner_text()
        for attendu in (creation.strftime("%d/%m/%Y"), "correctif différé", "P2", fuite["statut"], "Fuite à la garniture"):
            self.assertIn(attendu, ordres)
        # Le plus récent d'abord
        self.assertEqual(liens_ot[0], fuite["id"])
        # Articles liés : le kit garniture et son stock (colonne stock de articles.csv)
        stock_kit = ligne_par_id(lire_csv(DOSSIER_DEMO, "articles.csv")[0], SCENARIOS["kit_garniture"])["stock"]
        ligne_kit = espaces_simples(page.locator("#contenu table tr", has_text="Kit garniture mécanique PO-02").first.inner_text())
        self.assertRegex(ligne_kit, r"\b%s kit" % re.escape(stock_kit))
        # Gros bouton « Signaler un problème » vers la demande préremplie
        signaler = page.locator("a.parc-signaler")
        self.assertEqual(signaler.get_attribute("href"), "#/di/nouvelle?equipement=EQ-0005")
        self.assertIn("Signaler un problème", signaler.inner_text())
        # Actions du responsable
        self.assertEqual(page.locator("a[href='#/ot/nouveau?equipement=EQ-0005']").count(), 1)
        self.assertEqual(page.locator("a[href='#/equipement/EQ-0005/modifier']").count(), 1)
        self.assertEqual(self.texte("#parc-activite"), "Désactiver")
        # QR : relu par jsQR = App.urlFicheEquipement ; repère en clair dessous ; consigne
        self.assertEqual(page.evaluate(LIRE_QR_JS), "GMAO:EQ-0005")
        self.assertEqual(page.evaluate("App.urlFicheEquipement('EQ-0005')"), "GMAO:EQ-0005")
        self.assertEqual(self.texte(".qr .repere"), "PO-02")
        self.assertIn("Code GMAO:EQ-0005, lisible par la caméra du poste.", self.texte(".parc-qr-carte"))

    def test_demo_fiche_habilitation_compteur_et_sous_equipements(self):
        self.ouvrir_demo("#/equipement/EQ-0012")
        self.assertIn("BR", self.texte(".parc-habilitation"))
        self.assertIn("Habilitation requise", self.texte(".parc-habilitation"))
        # Compteur de CP-01 : dernier relevé
        self.aller("#/equipement/EQ-0001")
        lignes, _ = lire_csv(DOSSIER_DEMO, "releves.csv")
        releves = sorted((r for r in lignes if r["compteur_id"] == "CPT-0001"), key=lambda r: (r["date"], r["id"]))
        dernier = releves[-1]
        jour = date_demo_decalee(dernier["date"]).strftime("%d/%m/%Y")
        compteurs = self.texte(".parc-compteurs")
        self.assertIn("Compteur horaire de marche", compteurs)
        self.assertIn(jour, compteurs)
        self.assertIn(re.sub(r"(\d)(?=(\d{3})+$)", r"\1 ", dernier["valeur"]), compteurs)
        # Sous-équipement listé sur la fiche du parent, avec lien
        self.assertEqual(self.page.locator("#contenu a[href='#/equipement/EQ-0002']").count(), 1)
        # Fiche d'un sous-équipement : parent cliquable
        self.aller("#/equipement/EQ-0002")
        self.assertEqual(self.page.locator(".valeurs a[href='#/equipement/EQ-0001']").count(), 1)
        # Équipement inconnu : message clair
        self.aller("#/equipement/EQ-9999")
        self.assertIn("Équipement introuvable", self.texte("#contenu"))

    def test_demo_controles_de_saisie_repere_unique_et_boucles(self):
        self.ouvrir_demo()
        page = self.page
        verifier = """([valeurs, id]) => Parc.verifierEquipement(valeurs, Donnees.lignes('equipements'), Donnees.lignes('localisations'), id)"""

        def messages(valeurs, identifiant=""):
            return [(e["nom"], e["message"]) for e in page.evaluate(verifier, [valeurs, identifiant])]

        base = {"repere": "ZZ-01", "designation": "Machine", "localisation_id": "LOC-0002", "parent_id": ""}
        self.assertEqual(messages(base), [])
        # Repère obligatoire, désignation obligatoire
        self.assertEqual([n for n, _ in messages(dict(base, repere="", designation=""))], ["repere", "designation"])
        # Repère en double parmi les actifs (casse ignorée), message qui nomme l'équipement
        double = messages(dict(base, repere="po-02"))
        self.assertEqual(double[0][0], "repere")
        self.assertIn("déjà utilisé", double[0][1])
        self.assertIn("Pompe centrifuge", double[0][1])
        # Un équipement garde son propre repère ; un repère d'équipement inactif est réutilisable
        self.assertEqual(messages(dict(base, repere="PO-02"), "EQ-0005"), [])
        self.assertEqual(messages(dict(base, repere="PE-01")), [])
        # Localisation inexistante
        self.assertEqual(messages(dict(base, localisation_id="LOC-9999"))[0][0], "localisation_id")
        # Parent : soi-même, inexistant, boucle (EQ-0002 est un sous-équipement de EQ-0001)
        self.assertIn("propre parent", messages(dict(base, parent_id="EQ-0001"), "EQ-0001")[0][1])
        self.assertEqual(messages(dict(base, parent_id="EQ-9999"))[0][0], "parent_id")
        boucle = messages(dict(base, repere="CP-01", parent_id="EQ-0002"), "EQ-0001")
        self.assertEqual(boucle[0][0], "parent_id")
        self.assertIn("Boucle", boucle[0][1])
        self.assertEqual(messages(dict(base, parent_id="EQ-0001")), [])            # parent valide
        # Heures hors limites
        self.assertEqual(messages(dict(base, heures_fonct_jour="30"))[0][0], "heures_fonct_jour")
        # Localisations : boucle et doublon au même endroit
        loc = """([valeurs, id]) => Parc.verifierLocalisation(valeurs, Donnees.lignes('localisations'), id)"""
        boucle_loc = page.evaluate(loc, [{"libelle": "Site", "type": "site", "parent_id": "LOC-0002"}, "LOC-0001"])
        self.assertIn("Boucle", boucle_loc[0]["message"])
        double_loc = page.evaluate(loc, [{"libelle": "atelier usinage", "type": "atelier", "parent_id": "LOC-0001"}, ""])
        self.assertIn("existe déjà", double_loc[0]["message"])
        self.assertEqual(page.evaluate(loc, [{"libelle": "Atelier Usinage", "type": "atelier", "parent_id": "LOC-0001"}, "LOC-0002"]), [])

    def test_demo_formulaire_de_modification_prerempli(self):
        self.ouvrir_demo("#/equipement/EQ-0005/modifier")
        page = self.page
        self.assertEqual(page.input_value("#parc-formulaire [name=repere]"), "PO-02")
        self.assertEqual(page.input_value("#parc-formulaire [name=localisation_id]"), "LOC-0004")
        self.assertEqual(page.input_value("#parc-formulaire [name=date_mes]"), date_demo_decalee("2017-09-18").isoformat())
        self.assertEqual(page.input_value("#parc-formulaire [name=criticite]"), "B")
        self.assertEqual(page.input_value("#parc-formulaire [name=heures_fonct_jour]"), "16")
        # L'équipement ne se propose pas comme son propre parent
        options = page.eval_on_selector_all("#parc-formulaire [name=parent_id] option", "els => els.map(e => e.value)")
        self.assertNotIn("EQ-0005", options)
        self.assertIn("EQ-0001", options)
        # Champs obligatoires vides : messages sous les champs, on reste sur le formulaire
        page.fill("#parc-formulaire [name=repere]", "")
        page.fill("#parc-formulaire [name=designation]", "")
        self.enregistrer_formulaire()
        self.assertEqual(page.locator("#parc-formulaire .erreur-champ:not([hidden])").count(), 2)
        self.assertEqual(page.evaluate("location.hash"), "#/equipement/EQ-0005/modifier")
        # En démo, la modification est gardée en mémoire (et rien n'est écrit)
        page.fill("#parc-formulaire [name=repere]", "PO-02")
        page.fill("#parc-formulaire [name=designation]", "Pompe de test")
        self.enregistrer_formulaire()
        page.wait_for_function("location.hash === '#/equipement/EQ-0005'")
        page.wait_for_function("document.querySelector('#contenu h1').textContent.includes('Pompe de test')")


# ---------------------------------------------------------------------------
# Serveur : écriture sur le disque
# ---------------------------------------------------------------------------

class TestParcServeur(CasParc):

    def test_serveur_fiche_qr_relu_est_l_url_de_la_fiche(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur, route="#/equipement/EQ-0005")
            page = self.page
            attendu = page.evaluate("App.urlFicheEquipement('EQ-0005')")
            self.assertRegex(attendu, r"^http://[^/]+/#/equipement/EQ-0005$")
            self.assertEqual(page.evaluate(LIRE_QR_JS), attendu)
            self.assertEqual(self.texte(".qr .repere"), "PO-02")
            self.assertIn("Scannez avec l'appareil photo du téléphone", self.texte(".parc-qr-carte"))
            self.assertNotIn("lisible par la caméra du poste", self.texte(".parc-qr-carte"))
            # Un QR scanné : l'URL ouvre la fiche (ici avec le chemin local du serveur de test)
            page.goto(serveur.url + "/#/equipement/EQ-0012")
            page.wait_for_function("document.querySelector('#contenu h1') && document.querySelector('#contenu h1').textContent.includes('AE-03')")

    def test_serveur_creation_modification_desactivation_et_reactivation(self):
        with ServeurPrevo() as serveur, tempfile.TemporaryDirectory() as temporaire:
            self.ouvrir_serveur(serveur)
            page = self.page
            avant, _ = lire_csv(serveur.dossier, "equipements.csv")

            # --- Création (avec un document) ---
            pdf = Path(temporaire) / "notice.pdf"
            pdf.write_bytes(b"%PDF-1.4\n% notice de test\n")
            page.click("text=Nouvel équipement")
            page.wait_for_selector("#parc-formulaire")
            self.assertEqual(page.evaluate("location.hash"), "#/equipement/nouveau")
            self.remplir_equipement("ZZ-77", "Machine de test", localisation_id="LOC-0002", parent_id="EQ-0019",
                                    marque="Marque Z", modele="M-1", num_serie="00123", criticite="A",
                                    heures_fonct_jour="7,5", habilitation_requise="BR",
                                    consignation="1. Couper le courant.\n2. Cadenasser.")
            page.set_input_files("#parc-formulaire input[type=file]", str(pdf))
            self.enregistrer_formulaire()
            page.wait_for_function("location.hash === '#/equipement/EQ-0032'")
            page.wait_for_function("document.querySelector('#contenu h1') && document.querySelector('#contenu h1').textContent.includes('ZZ-77')")

            apres, texte = lire_csv(serveur.dossier, "equipements.csv")
            self.assertEqual(len(apres), len(avant) + 1)
            ligne = ligne_par_id(apres, "EQ-0032")
            self.assertIsNotNone(ligne)
            self.assertEqual(ligne["repere"], "'ZZ-77")                    # repère protégé par une apostrophe
            self.assertEqual(ligne["num_serie"], "'00123")                  # zéros de tête protégés
            self.assertEqual(ligne["designation"], "Machine de test")
            self.assertEqual(ligne["localisation_id"], "LOC-0002")
            self.assertEqual(ligne["parent_id"], "EQ-0019")
            self.assertEqual(ligne["criticite"], "A")
            self.assertEqual(ligne["statut"], "en service")
            self.assertEqual(ligne["heures_fonct_jour"], "7.5")
            self.assertEqual(ligne["habilitation_requise"], "BR")
            self.assertEqual(ligne["consignation"], "1. Couper le courant.\n2. Cadenasser.")
            self.assertEqual(ligne["actif"], "1")
            self.assertRegex(ligne["document"], r"^ZZ-77_\d{8}-\d{6}_[a-z0-9]{4}\.pdf$")
            self.assertTrue((serveur.dossier / "documents" / ligne["document"]).is_file())
            self.assertIn("\r\n", texte)
            # Les autres lignes n'ont pas bougé
            self.assertEqual(ligne_par_id(apres, "EQ-0005"), ligne_par_id(avant, "EQ-0005"))
            # Journal
            journal, _ = lire_csv(serveur.dossier, "journal.csv")
            self.assertTrue(any(j["table"] == "equipements" and j["id_ligne"] == "EQ-0032" and "création" in j["action"] for j in journal))

            # La fiche montre tout : parent, document en lien, consignation, habilitation
            fiche = self.texte("#contenu")
            self.assertIn("ZZ-77", fiche)
            self.assertIn("Couper le courant.", fiche)
            self.assertIn("Habilitation requise : BR", fiche)
            self.assertIn("Scie à ruban", fiche)
            lien_document = page.locator(".valeurs a[href*='/api/documents/']")
            self.assertEqual(lien_document.count(), 1)
            statut = page.evaluate("(href) => fetch(href).then((r) => r.status)", lien_document.get_attribute("href"))
            self.assertEqual(statut, 200)

            # Le nouvel équipement apparaît dans le parc, sous son parent
            self.aller("#/parc")
            self.assertEqual(page.locator("#parc-arbre li:has(> a[href='#/equipement/EQ-0019']) > ul a[href='#/equipement/EQ-0032']").count(), 1)

            # --- Modification ---
            self.aller("#/equipement/EQ-0005")
            page.click("a[href='#/equipement/EQ-0005/modifier']")
            page.wait_for_selector("#parc-formulaire")
            page.fill("#parc-formulaire [name=designation]", "Pompe centrifuge modifiée")
            page.fill("#parc-formulaire [name=marque]", "Hydronel SA")
            page.select_option("#parc-formulaire [name=statut]", "arrêt")
            self.enregistrer_formulaire()
            page.wait_for_function("location.hash === '#/equipement/EQ-0005'")
            page.wait_for_function("document.querySelector('#contenu h1').textContent.includes('Pompe centrifuge modifiée')")
            lignes, _ = lire_csv(serveur.dossier, "equipements.csv")
            modifiee = ligne_par_id(lignes, "EQ-0005")
            self.assertEqual(modifiee["designation"], "Pompe centrifuge modifiée")
            self.assertEqual(modifiee["marque"], "Hydronel SA")
            self.assertEqual(modifiee["statut"], "arrêt")
            self.assertEqual(modifiee["repere"], "'PO-02")
            self.assertEqual(modifiee["modele"], ligne_par_id(avant, "EQ-0005")["modele"])
            self.assertEqual(modifiee["consignation"], ligne_par_id(avant, "EQ-0005")["consignation"])

            # --- Désactivation (confirmation, jamais de suppression) ---
            self.aller("#/equipement/EQ-0006")
            page.click("#parc-activite")
            page.wait_for_selector("dialog.dialogue")
            self.assertIn("Son historique est conservé", page.inner_text("dialog.dialogue"))
            page.click("dialog .fenetre-actions button:has-text('Annuler')")
            lignes, _ = lire_csv(serveur.dossier, "equipements.csv")
            self.assertEqual(ligne_par_id(lignes, "EQ-0006")["actif"], "1")      # annulé : rien ne change
            page.click("#parc-activite")
            page.wait_for_selector("dialog.dialogue")
            page.click("dialog .fenetre-actions button:has-text('Désactiver')")
            page.wait_for_function("document.querySelector('#parc-activite') && document.querySelector('#parc-activite').textContent.trim() === 'Réactiver'")
            lignes, _ = lire_csv(serveur.dossier, "equipements.csv")
            self.assertEqual(ligne_par_id(lignes, "EQ-0006")["actif"], "0")
            self.assertEqual(len(lignes), len(avant) + 1)                          # aucune ligne supprimée
            self.assertIn("Cet équipement est désactivé", self.texte("#contenu"))
            self.aller("#/parc")
            self.assertNotIn("PO-03", self.reperes_visibles())
            page.check("#parc-inactifs")
            self.assertIn("PO-03", self.reperes_visibles())

            # --- Réactivation ---
            self.aller("#/equipement/EQ-0006")
            page.click("#parc-activite")
            page.wait_for_selector("dialog.dialogue")
            page.click("dialog .fenetre-actions button:has-text('Réactiver')")
            page.wait_for_function("document.querySelector('#parc-activite').textContent.trim() === 'Désactiver'")
            lignes, _ = lire_csv(serveur.dossier, "equipements.csv")
            self.assertEqual(ligne_par_id(lignes, "EQ-0006")["actif"], "1")

    def test_serveur_repere_en_double_refuse_avec_message(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur, route="#/equipement/nouveau")
            page = self.page
            page.wait_for_selector("#parc-formulaire")
            avant = (serveur.dossier / "equipements.csv").read_bytes()
            self.remplir_equipement("po-02", "Une autre pompe")
            self.enregistrer_formulaire()
            page.wait_for_selector("#parc-formulaire [data-champ=repere] .erreur-champ:not([hidden])")
            message = self.texte("#parc-formulaire [data-champ=repere] .erreur-champ")
            self.assertIn("déjà utilisé", message)
            self.assertIn("PO-02 — Pompe centrifuge eau de refroidissement", message)
            self.assertEqual(page.evaluate("location.hash"), "#/equipement/nouveau")
            self.assertEqual((serveur.dossier / "equipements.csv").read_bytes(), avant)   # rien n'a été écrit
            # Un repère libre passe
            page.fill("#parc-formulaire [name=repere]", "PO-02B")
            self.enregistrer_formulaire()
            page.wait_for_function("location.hash === '#/equipement/EQ-0032'")

    def test_serveur_repere_double_detecte_aussi_si_un_autre_poste_vient_de_le_prendre(self):
        """Le contrôle est rejoué dans Donnees.modifier sur les lignes fraîches du fichier."""
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur, route="#/equipement/nouveau")
            page = self.page
            page.wait_for_selector("#parc-formulaire")
            self.remplir_equipement("ZZ-55", "Machine concurrente")
            # Un autre poste crée ZZ-55 entre-temps : la table est modifiée sous les pieds de l'écran
            erreur = page.evaluate("""async () => {
                await Donnees.modifier('equipements', (lignes, outils) => {
                    lignes.push({ id: outils.nouvelId(lignes), repere: 'ZZ-55', designation: 'Déjà là', actif: '1' });
                });
                return null;
            }""")
            self.assertIsNone(erreur)
            self.enregistrer_formulaire()
            page.wait_for_selector("#parc-formulaire [data-champ=repere] .erreur-champ:not([hidden])")
            self.assertIn("déjà utilisé", self.texte("#parc-formulaire [data-champ=repere] .erreur-champ"))
            lignes, _ = lire_csv(serveur.dossier, "equipements.csv")
            self.assertEqual(len([l for l in lignes if l["repere"] == "'ZZ-55"]), 1)

    def test_serveur_localisation_creation_modification_et_doublon(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur)
            page = self.page
            page.click("#parc-nouvelle-localisation")
            page.wait_for_selector("dialog .parc-formulaire-localisation")
            # Libellé obligatoire
            page.click("dialog .fenetre-actions button:has-text('Enregistrer')")
            page.wait_for_selector("dialog [data-champ=libelle] .erreur-champ:not([hidden])")
            page.fill("dialog [name=libelle]", "Zone de test")
            page.select_option("dialog [name=parent_id]", "LOC-0001")
            self.assertEqual(page.input_value("dialog [name=type]"), "atelier")       # suit le parent
            page.click("dialog .fenetre-actions button:has-text('Enregistrer')")
            page.wait_for_selector("dialog", state="detached")
            lignes, _ = lire_csv(serveur.dossier, "localisations.csv")
            nouvelle = ligne_par_id(lignes, "LOC-0008")
            self.assertEqual((nouvelle["libelle"], nouvelle["parent_id"], nouvelle["type"]), ("Zone de test", "LOC-0001", "atelier"))
            self.assertIn("Zone de test", page.locator("#parc-arbre summary b").all_inner_texts())
            self.assertIn("Aucun équipement ici", self.texte("#parc-arbre"))

            # Même libellé au même endroit : refusé, la fenêtre reste ouverte
            page.click("#parc-nouvelle-localisation")
            page.wait_for_selector("dialog .parc-formulaire-localisation")
            page.fill("dialog [name=libelle]", "zone de TEST")
            page.select_option("dialog [name=parent_id]", "LOC-0001")
            page.click("dialog .fenetre-actions button:has-text('Enregistrer')")
            page.wait_for_selector("dialog [data-champ=libelle] .erreur-champ:not([hidden])")
            self.assertIn("existe déjà", self.texte("dialog [data-champ=libelle] .erreur-champ"))
            page.click("dialog .fenetre-actions button:has-text('Annuler')")
            page.wait_for_selector("dialog", state="detached")
            self.assertEqual(len(lire_csv(serveur.dossier, "localisations.csv")[0]), 8)

            # Modification : on ne peut pas choisir une de ses sous-localisations comme parent
            page.click("button[data-localisation='LOC-0003']")
            page.wait_for_selector("dialog .parc-formulaire-localisation")
            options = page.eval_on_selector_all("dialog [name=parent_id] option", "els => els.map(e => e.value)")
            self.assertNotIn("LOC-0003", options)
            self.assertNotIn("LOC-0005", options)                                      # sa ligne
            self.assertIn("LOC-0001", options)
            page.fill("dialog [name=libelle]", "Atelier Assemblage")
            page.click("dialog .fenetre-actions button:has-text('Enregistrer')")
            page.wait_for_selector("dialog", state="detached")
            lignes, _ = lire_csv(serveur.dossier, "localisations.csv")
            self.assertEqual(ligne_par_id(lignes, "LOC-0003")["libelle"], "Atelier Assemblage")
            self.assertEqual(ligne_par_id(lignes, "LOC-0003")["type"], "atelier")
            self.assertIn("Atelier Assemblage", page.locator("#parc-arbre summary b").all_inner_texts())

    def test_serveur_demandeur_et_technicien_sans_modification(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur, profil="demandeur", nom="Lucie Martin", route="#/parc")
            page = self.page
            self.assertEqual(page.locator("text=Nouvel équipement").count(), 0)
            self.assertEqual(page.locator("#parc-nouvelle-localisation").count(), 0)
            self.assertEqual(page.locator(".parc-modifier-localisation").count(), 0)
            self.assertIn("PO-02", self.reperes_visibles())
            self.aller("#/equipement/EQ-0005")
            self.assertTrue(page.is_visible("a.parc-signaler"))
            self.assertEqual(page.get_attribute("a.parc-signaler", "href"), "#/di/nouvelle?equipement=EQ-0005")
            self.assertEqual(page.locator("a[href='#/equipement/EQ-0005/modifier']").count(), 0)
            self.assertEqual(page.locator("a[href^='#/ot/nouveau']").count(), 0)
            self.assertEqual(page.locator("#parc-activite").count(), 0)
            self.assertNotIn("Modifier", self.texte("#contenu .parc-actions"))
            self.assertIn(RAPPEL_CONSIGNATION, self.texte(".parc-consignation"))
            # Les écrans de saisie sont refusés : retour à l'accueil avec un message
            page.evaluate("location.hash = '#/equipement/nouveau'")
            page.wait_for_function("location.hash === '#/accueil'")
            page.evaluate("location.hash = '#/equipement/EQ-0005/modifier'")
            page.wait_for_function("location.hash === '#/accueil'")

    def test_serveur_technicien_sans_modification(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur, profil="technicien", technicien_id="TEC-0002", route="#/equipement/EQ-0005")
            page = self.page
            self.assertTrue(page.is_visible("a.parc-signaler"))
            self.assertEqual(page.locator("a[href='#/equipement/EQ-0005/modifier']").count(), 0)
            self.assertEqual(page.locator("#parc-activite").count(), 0)
            self.assertEqual(page.locator("a[href^='#/ot/nouveau']").count(), 0)

    def test_serveur_telephone_375px_sans_defilement_horizontal(self):
        page = self.page
        page.set_viewport_size({"width": 375, "height": 800})
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur, profil="technicien", technicien_id="TEC-0002", route="#/parc")
            self.assertTrue(page.evaluate("UI.estTelephone()"))
            self.sans_defilement_horizontal()
            page.fill("#parc-recherche", "convoyeur")
            self.assertEqual(sorted(self.reperes_visibles()), ["CV-01", "CV-02", "CV-02.M", "CV-03"])
            self.sans_defilement_horizontal()
            page.fill("#parc-recherche", "")
            # Fiche de PO-02 : « Signaler un problème » en tête, avant la consignation ; zone tactile >= 48 px
            for route in ("#/equipement/EQ-0005", "#/equipement/EQ-0012", "#/equipement/EQ-0001"):
                self.aller(route)
                page.wait_for_selector("a.parc-signaler")
                self.sans_defilement_horizontal()
            self.aller("#/equipement/EQ-0005")
            haut_signaler = page.evaluate("document.querySelector('a.parc-signaler').getBoundingClientRect().top")
            haut_consignation = page.evaluate("document.querySelector('.parc-consignation').getBoundingClientRect().top")
            self.assertLess(haut_signaler, haut_consignation)
            self.assertLess(haut_signaler, 400)                                      # visible sans défiler
            self.assertGreaterEqual(page.evaluate("document.querySelector('a.parc-signaler').getBoundingClientRect().height"), 48)
            # Les historiques passent en cartes (pas de tableau qui déborde)
            self.assertEqual(page.locator("#contenu table").count(), 0)
            self.assertGreaterEqual(page.locator("#contenu a[href^='#/ot/OT-']").count(), 5)
            # Le QR tient dans l'écran
            largeur_qr = page.evaluate("document.querySelector('.parc-qr-carte svg.qr-svg').getBoundingClientRect().width")
            self.assertLessEqual(largeur_qr, 375)
            # Formulaire en une colonne, sans débordement (responsable)
            page.evaluate("localStorage.setItem('prevo.profil', JSON.stringify({type: 'responsable', nom: '', technicienId: ''}))")
            page.reload()
            attendre_pret(page)
            self.aller("#/equipement/EQ-0005/modifier")
            page.wait_for_selector("#parc-formulaire")
            self.sans_defilement_horizontal()
            self.aller("#/parc")
            page.click("#parc-nouvelle-localisation")
            page.wait_for_selector("dialog .parc-formulaire-localisation")
            self.sans_defilement_horizontal()


if __name__ == "__main__":
    unittest.main()
