"""Tests de l'accueil, des Paramètres et du Contrôle de la base (tâche T15, ARCHITECTURE.md §8 à §10).

    accueil     : compteurs du responsable = calcul Python sur les CSV du serveur de test ;
                  QR de connexion relu par jsQR ; accueils du technicien et du demandeur ;
    paramètres  : écriture de entreprise_nom et des délais dans parametres.csv, export ZIP ;
    sauvegarde  : « Sauvegarder maintenant », restauration d'une table puis de toutes les tables ;
    contrôle    : références cassées, identifiants manquants, incohérence DI/OT injectés sur le disque ;
    démo        : sauvegardes indisponibles ;
    profils     : demandeur et technicien n'ont pas accès aux Paramètres ;
    lot 3 (T46) : réglages tolérance, seuil, priorité, horizon, heures par défaut (bornes, écrits et
                  relus) ; codes de défaillance (code proposé, ajout visible dans la fiche OT, libellé
                  modifié, doublons refusés).

Les tests ne dépendent que des écrans de ce lot : les données sont lues sur le disque du serveur de
test ou par `Donnees`, jamais en naviguant dans les écrans Parc, Demandes ou Ordres.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_parametres.py" -v
"""
import csv
import datetime
import io
import json
import re
import unittest
import urllib.request
import zipfile
from pathlib import Path

from commun import (CasNavigateur, RACINE, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo,
                    url_fichier)

DOSSIER_DEMO = RACINE / "donnees" / "demo"
# Une DI « Nouvelle » du jeu de démo (outils/generer_demo.py, tests/fixtures/demo-scenarios.json).
DI_NOUVELLE = scenarios_demo()["di_statut_nouvelle"]
BOM = "﻿"
STATUTS_OT_FERMES = ("Clôturé techniquement", "Clôturé administrativement", "Annulé")
# Compteur de l'accueil du responsable (tuile-lien de la grille « bento », T90)
COMPTEUR = "#contenu #bento a.bento-compteur[href='%s']"

# Lecture du QR de l'accueil par jsQR : le SVG est dessiné dans un canvas puis décodé.
LIRE_QR_JS = """async () => {
  const svg = document.querySelector('#qr-connexion svg');
  if (!svg) return null;
  const image = new Image();
  image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg.outerHTML);
  await image.decode();
  const toile = document.createElement('canvas');
  toile.width = 300; toile.height = 300;
  const contexte = toile.getContext('2d');
  contexte.drawImage(image, 0, 0, 300, 300);
  const code = jsQR(contexte.getImageData(0, 0, 300, 300).data, 300, 300);
  return code ? code.data : null;
}"""


# ---------------------------------------------------------------------------
# Lecture et écriture des CSV du serveur de test (comme un autre poste ou Excel)
# ---------------------------------------------------------------------------

def lire_csv(chemin):
    """(en-tête, lignes) d'un CSV Prévo : lignes = liste de dictionnaires, valeurs telles que dans le fichier."""
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        lecteur = csv.reader(fichier, delimiter=";")
        entete = next(lecteur)
        lignes = [dict(zip(entete, cellules)) for cellules in lecteur if any(cellules)]
    return entete, lignes


def ecrire_csv(chemin, entete, lignes):
    """Réécrit un CSV au format Prévo (BOM, « ; », CRLF)."""
    tampon = io.StringIO(newline="")
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(entete)
    for ligne in lignes:
        ecrivain.writerow([ligne.get(nom, "") for nom in entete])
    Path(chemin).write_bytes((BOM + tampon.getvalue()).encode("utf-8"))


def sans_apostrophe(valeur):
    """Valeur d'un CSV sans l'apostrophe de protection d'Excel (« '24 » → « 24 »)."""
    return valeur[1:] if valeur.startswith("'") else valeur


def ajouter_texte_csv(chemin, texte):
    """Ajoute des lignes brutes à la fin d'un CSV (comme un autre poste qui écrit sur le disque)."""
    octets = Path(chemin).read_bytes()
    if not octets.endswith(b"\n"):
        octets += b"\r\n"
    Path(chemin).write_bytes(octets + texte.encode("utf-8"))


def numero_ligne_physique(chemin, debut_de_ligne):
    """Numéro (en-tête = 1) de la ligne du fichier qui commence par `debut_de_ligne`."""
    lignes = Path(chemin).read_bytes().decode("utf-8").split("\n")
    for position, ligne in enumerate(lignes):
        if ligne.lstrip(BOM).startswith(debut_de_ligne):
            return position + 1
    raise AssertionError("ligne introuvable dans %s : %s" % (chemin, debut_de_ligne))


# Lignes d'équipements injectées sur le disque (16 colonnes, format du fichier).
LIGNE_REFERENCE_CASSEE = "EQ-0998;'ZZ-98;Machine à référence cassée;LOC-9999;;;;;;B;en service;;;;;1\r\n"
LIGNE_SANS_IDENTIFIANT = ";'ZZ-97;Machine sans identifiant;LOC-0002;;;;;;B;en service;;;;;1\r\n"


class CasParametres(CasNavigateur):
    """Outils communs : serveur de test, profil, attente de l'application."""

    def ouvrir(self, serveur, route="#/accueil", profil="responsable", **options):
        """Ouvre l'application en mode serveur avec un profil préréglé."""
        preregler_profil(self.contexte, profil, **options)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        return self.page

    def aller_a(self, route):
        self.page.evaluate("hash => { location.hash = hash; }", route)
        self.page.wait_for_function("hash => location.hash === hash", arg=route)

    def attendre_ecran(self, titre):
        self.page.wait_for_function(
            "titre => document.querySelector('#contenu h1') && document.querySelector('#contenu h1').textContent.trim() === titre",
            arg=titre)

    def texte(self, selecteur):
        return self.page.inner_text(selecteur)

    def texte_toast(self):
        return self.page.evaluate("document.getElementById('toast').textContent")

    def attendre_toast(self, extrait):
        self.page.wait_for_function(
            "extrait => document.getElementById('toast').textContent.includes(extrait)", arg=extrait)

    def rafraichir_donnees(self):
        """Fait relire à l'application les fichiers modifiés sur le disque (sans attendre les 20 s)."""
        self.page.evaluate("Donnees.rafraichir()")


# ---------------------------------------------------------------------------
# Accueil
# ---------------------------------------------------------------------------

class TestAccueil(CasParametres):

    def test_accueil_responsable_compteurs_egaux_au_calcul_python_sur_les_csv(self):
        aujourdhui = datetime.date.today().isoformat()
        with ServeurPrevo() as serveur:
            _, demandes = lire_csv(serveur.dossier / "demandes.csv")
            _, ordres = lire_csv(serveur.dossier / "ordres_travail.csv")
            a_traiter = [d for d in demandes if d["statut"] == "Nouvelle"]
            ouverts = [o for o in ordres if o["statut"] not in STATUTS_OT_FERMES]
            en_retard = [o for o in ouverts if o["date_prevue"] and o["date_prevue"] < aujourdhui]
            p1_ouverts = [o for o in ouverts if o["priorite"] == "P1"]
            securite = [d for d in a_traiter if d["impact"] == "sécurité"]

            page = self.ouvrir(serveur)
            self.assertEqual(self.texte("#contenu h1"), "Bonjour")               # accueil « bento » (T90)
            chiffre = lambda lien: int(page.inner_text(COMPTEUR % lien + " .chiffre"))
            self.assertEqual(chiffre("#/di?statut=Nouvelle"), len(a_traiter))
            self.assertEqual(chiffre("#/ot?filtre=retard"), len(en_retard))
            self.assertEqual(chiffre("#/ot?filtre=p1"), len(p1_ouverts))
            # Le jeu de démo a bien de quoi remplir les trois indicateurs (sinon ce test ne prouverait rien).
            self.assertGreater(len(a_traiter), 0)
            self.assertGreater(len(en_retard), 0)
            self.assertGreater(len(p1_ouverts), 0)
            self.assertIn("dont %d sécurité" % len(securite), self.texte(COMPTEUR % "#/di?statut=Nouvelle"))

            # Les trois indicateurs sont des liens (liste filtrée) ; les fonctions du module donnent les mêmes nombres.
            self.assertEqual(page.evaluate(
                "(() => { const c = Accueil.calculerCompteurs(); return [c.diATraiter.length, c.otEnRetard.length, c.p1Ouverts.length]; })()"),
                [len(a_traiter), len(en_retard), len(p1_ouverts)])

            # Listes : 5 DI à traiter au plus (la demande de sécurité d'abord), 5 OT en retard au plus (les plus anciens d'abord).
            cartes_di = page.locator('#bento-demandes:has(h2:text("Demandes à traiter")) li')
            self.assertEqual(cartes_di.count(), min(5, len(a_traiter)))
            premiere_di = cartes_di.first.locator(".bento-id").inner_text()
            self.assertEqual(premiere_di, securite[0]["id"])
            self.assertEqual(cartes_di.first.locator("a").get_attribute("href"), "#/di/" + securite[0]["id"])
            cartes_ot = page.locator('#bento-retards:has(h2:text("OT en retard")) li')
            self.assertEqual(cartes_ot.count(), min(5, len(en_retard)))
            plus_ancien = sorted(en_retard, key=lambda o: o["date_prevue"])[0]["id"]
            self.assertEqual(cartes_ot.first.locator(".bento-id").inner_text(), plus_ancien)
            self.assertIn("en retard de", cartes_ot.first.inner_text())

            # Pas d'alerte de contrôle : le jeu de démo est sain.
            self.assertEqual(page.locator("#contenu .alerte.important").count(), 0)

    def test_accueil_alerte_quand_le_controle_de_la_base_a_des_erreurs(self):
        with ServeurPrevo() as serveur:
            ajouter_texte_csv(serveur.dossier / "equipements.csv", LIGNE_REFERENCE_CASSEE)
            page = self.ouvrir(serveur)
            alerte = page.locator("#contenu .alerte.important")
            self.assertEqual(alerte.count(), 1)
            self.assertIn("Contrôle de la base", alerte.inner_text())
            alerte.locator("a").click()
            page.wait_for_function("location.hash === '#/controle'")
            self.attendre_ecran("Contrôle de la base")

    def test_accueil_qr_de_connexion_relu_par_jsqr_egal_a_l_adresse_reseau(self):
        with ServeurPrevo() as serveur:
            with urllib.request.urlopen(serveur.url + "/api/info", timeout=5) as reponse:
                adresses = json.loads(reponse.read().decode("utf-8"))["adresses_reseau"]
            page = self.ouvrir(serveur)
            self.assertTrue(page.is_visible("#carte-connexion"))
            texte = self.texte("#carte-connexion")
            self.assertIn("Connecter un téléphone", texte)
            self.assertIn("même réseau Wi-Fi", texte)
            self.assertIn("réseau privé", texte)
            if adresses:
                # Vrai réseau de la machine de test : le QR contient la première adresse réseau.
                self.assertEqual(page.evaluate(LIRE_QR_JS), adresses[0])
                self.assertEqual(self.texte("#adresse-reseau"), adresses[0])
            else:
                self.assertIn("Aucune adresse réseau", texte)
                self.assertEqual(page.locator("#qr-connexion").count(), 0)

    def test_accueil_qr_avec_adresse_reseau_imposee_puis_sans_adresse(self):
        adresse = "http://192.168.7.20:8080/"
        with ServeurPrevo() as serveur:
            # Réponse de /api/info imposée : le test ne dépend pas du réseau de la machine.
            self.page.route("**/api/info", lambda route: route.fulfill(
                status=200, content_type="application/json",
                body=json.dumps({"port": 8080, "adresse_locale": "http://localhost:8080/", "adresses_reseau": [adresse]})))
            page = self.ouvrir(serveur)
            self.assertEqual(page.evaluate(LIRE_QR_JS), adresse)
            self.assertEqual(self.texte("#adresse-reseau"), adresse)

            # Sans adresse réseau : explication à la place du QR.
            page.unroute("**/api/info")
            page.route("**/api/info", lambda route: route.fulfill(
                status=200, content_type="application/json",
                body=json.dumps({"port": 8080, "adresse_locale": "http://localhost:8080/", "adresses_reseau": []})))
            # L'adresse est gardée en mémoire par le module : on recharge la page pour une lecture neuve.
            page.reload()
            attendre_pret(page)
            self.assertEqual(page.locator("#qr-connexion").count(), 0)
            self.assertIn("Aucune adresse réseau détectée", self.texte("#carte-connexion"))

    def test_accueil_technicien_ses_ot_ouverts_et_signaler(self):
        with ServeurPrevo() as serveur:
            _, ordres = lire_csv(serveur.dossier / "ordres_travail.csv")
            siens = [o for o in ordres if o["technicien_id"] == "TEC-0002" and o["statut"] not in STATUTS_OT_FERMES]
            self.assertGreater(len(siens), 0)
            page = self.ouvrir(serveur, profil="technicien", technicien_id="TEC-0002")
            cartes = page.locator("#contenu .liste-cartes > li")
            self.assertEqual(cartes.count(), len(siens))
            identifiants = [cartes.nth(i).locator("b").first.inner_text() for i in range(cartes.count())]
            self.assertEqual(sorted(identifiants), sorted(o["id"] for o in siens))
            # Aucun compteur du responsable ; depuis le lot 3 (§15.9), seulement les deux indicateurs
            # de conformité (contrôles sous 30 j, habilitations à renouveler).
            liens = page.eval_on_selector_all("#contenu .instruments a", "l => l.map(a => a.getAttribute('href'))")
            self.assertEqual(sorted(liens), ["#/controles?filtre=30j", "#/equipe?filtre=a-renouveler"])
            self.assertEqual(page.locator("#contenu .instruments:not(.accueil-instruments-technicien)").count(), 0)
            signaler = page.locator("#contenu a.btn-gros")
            self.assertIn("Signaler un problème", signaler.inner_text())
            self.assertEqual(signaler.get_attribute("href"), "#/di/nouvelle")
            # Le QR de connexion est aussi proposé (mode serveur).
            self.assertTrue(page.is_visible("#carte-connexion"))

    def test_accueil_demandeur_gros_bouton_et_ses_cinq_dernieres_demandes_avec_motif(self):
        with ServeurPrevo() as serveur:
            _, demandes = lire_csv(serveur.dossier / "demandes.csv")
            page = self.ouvrir(serveur, profil="demandeur", nom="Lucas Perrot")
            signaler = page.locator("#contenu a.btn-gros")
            self.assertIn("Signaler un problème", signaler.inner_text())
            self.assertEqual(signaler.get_attribute("href"), "#/di/nouvelle")
            self.assertEqual(page.locator("#contenu .instruments").count(), 0)

            def verifier(nom):
                siennes = sorted((d for d in demandes if d["demandeur"] == nom),
                                 key=lambda d: d["date_heure"], reverse=True)
                cartes = page.locator("#contenu .liste-cartes > li")
                self.assertEqual(cartes.count(), min(5, len(siennes)))
                for position, demande in enumerate(siennes[:5]):
                    carte = cartes.nth(position)
                    self.assertEqual(carte.locator("b").first.inner_text(), demande["id"])
                    self.assertIn(demande["statut"], carte.inner_text())
                    if demande["statut"] in ("Refusée", "Différée") and demande["motif_decision"]:
                        self.assertIn(demande["motif_decision"], carte.inner_text())
                return siennes

            siennes = verifier("Lucas Perrot")
            self.assertTrue(any(d["statut"] == "Différée" for d in siennes[:5]))
            self.assertIn("Motif du report", self.texte("#contenu"))

            # Un demandeur dont une demande a été refusée voit le motif du refus.
            page.evaluate("localStorage.setItem('prevo.profil', JSON.stringify({type: 'demandeur', nom: 'Hugo Lefèvre', technicienId: ''}))")
            page.reload()
            attendre_pret(page)
            siennes = verifier("Hugo Lefèvre")
            refusee = [d for d in siennes if d["statut"] == "Refusée"][0]
            self.assertIn("Motif du refus", self.texte("#contenu"))
            self.assertIn(refusee["motif_decision"], self.texte("#contenu"))

    def test_demo_pas_de_carte_de_connexion_sur_l_accueil(self):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("App.mode"), "demo")
        self.assertEqual(self.texte("#contenu h1"), "Bonjour")                   # accueil « bento » (T90)
        self.assertEqual(self.page.locator("#carte-connexion").count(), 0)
        self.assertGreater(int(self.page.inner_text(COMPTEUR % "#/di?statut=Nouvelle" + " .chiffre")), 0)


# ---------------------------------------------------------------------------
# Profils : pas d'accès aux Paramètres
# ---------------------------------------------------------------------------

class TestAccesParProfil(CasParametres):

    def verifier_refus(self, serveur, profil, **options):
        page = self.ouvrir(serveur, profil=profil, **options)
        self.assertNotIn("Paramètres", self.texte("#menu"))
        for route in ("#/parametres", "#/controle"):
            page.evaluate("hash => { history.replaceState(null, '', '#/apropos'); location.hash = hash; }", route)
            page.wait_for_function("location.hash === '#/accueil'")
            self.attendre_toast("pas disponible")
            self.assertEqual(self.texte("#contenu h1"), "Accueil")
            self.assertEqual(page.locator("#form-parametres").count(), 0)

    def test_demandeur_et_technicien_n_ont_pas_acces_aux_parametres(self):
        with ServeurPrevo() as serveur:
            self.verifier_refus(serveur, "demandeur", nom="Lucie Martin")
            self.page.evaluate("localStorage.setItem('prevo.profil', JSON.stringify({type: 'technicien', nom: '', technicienId: 'TEC-0001'}))")
            self.page.reload()
            attendre_pret(self.page)
            self.assertNotIn("Paramètres", self.texte("#menu"))
            self.page.evaluate("location.hash = '#/parametres'")
            self.page.wait_for_function("location.hash === '#/accueil'")
            self.attendre_toast("pas disponible")
            self.assertEqual(self.page.locator("#form-parametres").count(), 0)


# ---------------------------------------------------------------------------
# Paramètres : réglages et export
# ---------------------------------------------------------------------------

class TestParametres(CasParametres):

    def test_modification_de_entreprise_nom_et_des_delais_ecrite_dans_parametres_csv(self):
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "parametres.csv"
            page = self.ouvrir(serveur, route="#/parametres")
            self.attendre_ecran("Paramètres")
            self.assertEqual(page.input_value("#form-parametres [name=entreprise_nom]"), "Atelier des Trois Vallées (démo)")
            self.assertEqual(page.input_value("#form-parametres [name=delai_p2_h]"), "24")
            self.assertEqual(page.input_value("#form-parametres [name=rafraichissement_s]"), "20")

            # Une valeur invalide est refusée : message sous le champ, fichier inchangé.
            avant = chemin.read_bytes()
            page.fill("#form-parametres [name=delai_p2_h]", "abc")
            page.click("#form-parametres button[type=submit]")
            page.wait_for_selector("#form-parametres .en-erreur .erreur-champ", state="visible")
            self.assertEqual(chemin.read_bytes(), avant)

            # Valeurs correctes : écrites dans parametres.csv, nom visible dans le menu.
            page.fill("#form-parametres [name=entreprise_nom]", "Atelier Test T15")
            page.fill("#form-parametres [name=delai_p2_h]", "48")
            page.fill("#form-parametres [name=delai_p4]", "prochain arrêt programmé")
            page.click("#form-parametres button[type=submit]")
            self.attendre_toast("Paramètres enregistrés")
            _, lignes = lire_csv(chemin)
            valeurs = {ligne["cle"]: sans_apostrophe(ligne["valeur"]) for ligne in lignes}
            self.assertEqual(valeurs["entreprise_nom"], "Atelier Test T15")
            self.assertEqual(valeurs["delai_p2_h"], "48")
            self.assertEqual(valeurs["delai_p4"], "prochain arrêt programmé")
            self.assertEqual(valeurs["delai_p1_h"], "0")            # les autres clés n'ont pas bougé
            self.assertEqual(valeurs["delai_p3_h"], "168")
            self.assertEqual(valeurs["version_schema"], "3")         # format 3 (ARCHITECTURE.md §20.2)
            # (le menu écrit le nom en capitales par la feuille de style : on lit le texte brut)
            self.assertIn("Atelier Test T15", page.evaluate("document.getElementById('nom-entreprise').textContent"))
            self.assertIn("parametres;entreprise_nom;modification : valeur",
                          (serveur.dossier / "journal.csv").read_text(encoding="utf-8"))

            # Après rechargement de la page, le formulaire montre les valeurs enregistrées.
            page.reload()
            attendre_pret(page)
            self.attendre_ecran("Paramètres")
            self.assertEqual(page.input_value("#form-parametres [name=entreprise_nom]"), "Atelier Test T15")
            self.assertEqual(page.input_value("#form-parametres [name=delai_p2_h]"), "48")

    def test_ce_poste_et_changement_de_profil(self):
        # Lot 4 (§17.1, §17.7) : la carte « Ce poste » de Paramètres renvoie à l'écran « Ce poste »
        # (#/poste), qui porte désormais le bouton « Changer de profil ou de nom de poste… ».
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur, route="#/parametres")
            self.attendre_ecran("Paramètres")
            self.assertEqual(self.texte("#poste-nom"), "Poste test")
            self.assertEqual(self.texte("#poste-profil"), "Responsable")
            self.assertEqual(page.get_attribute("#lien-ce-poste", "href"), "#/poste")
            self.assertIn("Ouvrir « Ce poste »", self.texte("#lien-ce-poste"))
            page.click("#lien-ce-poste")
            page.wait_for_function("location.hash === '#/poste'")
            self.attendre_ecran("Ce poste")
            page.click("#btn-changer-profil")
            page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
            page.click("#profil-annuler")
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.profil.type"), "responsable")

    def test_export_zip_contient_les_22_csv(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur, route="#/parametres")
            self.attendre_ecran("Paramètres")
            with page.expect_download() as attente:
                page.click("#btn-export-zip")
            telechargement = attente.value
            self.assertRegex(telechargement.suggested_filename, r"^prevo-export-\d{4}-\d{2}-\d{2}\.zip$")
            with zipfile.ZipFile(telechargement.path()) as archive:
                noms_csv = sorted(n for n in archive.namelist() if n.endswith(".csv"))
                self.assertEqual(len(noms_csv), 24)
                self.assertEqual(noms_csv, sorted(c.name for c in DOSSIER_DEMO.glob("*.csv")))
                self.assertTrue(archive.read("equipements.csv").startswith(BOM.encode("utf-8")))

    def test_lien_vers_le_controle_de_la_base(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur, route="#/parametres")
            self.attendre_ecran("Paramètres")
            self.assertIn("Aucun problème", self.texte("#contenu"))
            page.click("#lien-controle")
            page.wait_for_function("location.hash === '#/controle'")
            self.attendre_ecran("Contrôle de la base")
            # Le menu garde « Paramètres » allumé sur l'écran de contrôle.
            self.assertEqual(page.evaluate("document.querySelector('#menu a.actif').dataset.ecran"), "parametres")


# ---------------------------------------------------------------------------
# Sauvegarde et restauration
# ---------------------------------------------------------------------------

class TestSauvegarde(CasParametres):

    def lignes_equipements_sur_disque(self, serveur):
        return lire_csv(serveur.dossier / "equipements.csv")

    def test_scenario_sauvegarde_suppression_sur_disque_et_restauration(self):
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "equipements.csv"
            entete, lignes = lire_csv(chemin)
            ligne_perdue = lignes[-1]                    # dernière ligne : une seule ligne physique
            identifiant = ligne_perdue["id"]
            page = self.ouvrir(serveur, route="#/parametres")
            self.attendre_ecran("Paramètres")
            self.assertEqual(page.locator("#carte-sauvegardes").count(), 1)

            # 1. « Sauvegarder maintenant » : une sauvegarde manuelle apparaît sur le disque et dans la liste.
            page.click("#btn-sauvegarder")
            page.wait_for_selector("#nom-sauvegarde-creee")
            nom = self.texte("#nom-sauvegarde-creee")
            self.assertRegex(nom, r"^\d{4}-\d{2}-\d{2}_\d{6}$")
            self.assertTrue((serveur.dossier / "sauvegardes" / nom / "equipements.csv").is_file())
            self.assertEqual(page.locator('button[data-restaurer="%s"]' % nom).count(), 1)
            self.assertIn("Manuelle", self.texte("#carte-sauvegardes"))

            # 2. La ligne est supprimée à la main dans equipements.csv : elle disparaît de l'application.
            ecrire_csv(chemin, entete, lignes[:-1])
            self.assertIsNotNone(page.evaluate("id => Donnees.trouver('equipements', id)", identifiant))
            page.evaluate("Donnees.rafraichir()")
            page.wait_for_function("id => Donnees.trouver('equipements', id) === undefined", arg=identifiant)
            self.assertNotIn(identifiant, [l["id"] for l in lire_csv(chemin)[1]])

            # 3. Annuler la restauration ne fait rien (pas de copie de sécurité).
            page.click('button[data-restaurer="%s"]' % nom)
            page.wait_for_selector("#fenetre-restauration")
            self.assertIn("copie de sécurité", self.texte("#fenetre-restauration"))
            page.click("dialog .fenetre-actions .btn-fantome")
            page.wait_for_selector("dialog", state="detached")
            self.assertEqual(list((serveur.dossier / "sauvegardes").glob("*_avant-restauration")), [])
            self.assertIsNone(page.evaluate("id => Donnees.trouver('equipements', id) || null", identifiant))

            # 4. Restauration de la seule table equipements : la ligne revient, dans l'appli et dans le fichier.
            page.click('button[data-restaurer="%s"]' % nom)
            page.wait_for_selector("#fenetre-restauration")
            self.assertTrue(page.is_disabled("#fenetre-restauration select[name=table]"))
            page.check("#fenetre-restauration input[value=une]")
            page.select_option("#fenetre-restauration select[name=table]", "equipements")
            page.click("dialog .fenetre-actions .btn-danger")
            page.wait_for_selector("#nom-copie-securite")
            copie = self.texte("#nom-copie-securite")
            self.assertRegex(copie, r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-restauration$")
            self.assertIn("equipements", self.texte("#message-action"))
            self.assertEqual(page.evaluate("id => Donnees.trouver('equipements', id).id", identifiant), identifiant)
            self.assertIn(identifiant, [l["id"] for l in lire_csv(chemin)[1]])
            # La copie de sécurité garde l'état d'avant (sans la ligne) et existe sur le disque.
            dossier_copie = serveur.dossier / "sauvegardes" / copie
            self.assertTrue(dossier_copie.is_dir())
            self.assertNotIn(identifiant, [l["id"] for l in lire_csv(dossier_copie / "equipements.csv")[1]])
            self.assertEqual(page.locator('button[data-restaurer="%s"]' % copie).count(), 1)
            self.assertIn("Copie de sécurité", self.texte("#carte-sauvegardes"))

    def test_restauration_de_toutes_les_tables_et_nom_de_l_entreprise_relu(self):
        with ServeurPrevo() as serveur:
            chemin_equipements = serveur.dossier / "equipements.csv"
            chemin_parametres = serveur.dossier / "parametres.csv"
            original_parametres = chemin_parametres.read_bytes()
            entete, lignes = lire_csv(chemin_equipements)
            identifiant = lignes[-1]["id"]
            page = self.ouvrir(serveur, route="#/parametres")
            self.attendre_ecran("Paramètres")
            page.click("#btn-sauvegarder")
            page.wait_for_selector("#nom-sauvegarde-creee")
            nom = self.texte("#nom-sauvegarde-creee")

            # Deux fichiers abîmés sur le disque : une ligne d'équipement perdue, le nom de l'entreprise changé.
            ecrire_csv(chemin_equipements, entete, lignes[:-1])
            chemin_parametres.write_bytes(original_parametres.replace(
                "Atelier des Trois Vallées (démo)".encode("utf-8"), "Nom modifié sur disque".encode("utf-8")))
            page.evaluate("Donnees.rafraichir()")
            page.wait_for_function("id => Donnees.trouver('equipements', id) === undefined", arg=identifiant)
            page.wait_for_function("document.getElementById('nom-entreprise').textContent.includes('Nom modifié sur disque')")

            # Restauration de toutes les tables (choix par défaut).
            page.click('button[data-restaurer="%s"]' % nom)
            page.wait_for_selector("#fenetre-restauration")
            page.click("dialog .fenetre-actions .btn-danger")
            page.wait_for_selector("#nom-copie-securite")
            self.assertEqual(page.evaluate("id => Donnees.trouver('equipements', id).id", identifiant), identifiant)
            self.assertEqual(chemin_parametres.read_bytes(), original_parametres)
            self.assertIn(identifiant, [l["id"] for l in lire_csv(chemin_equipements)[1]])
            page.wait_for_function("document.getElementById('nom-entreprise').textContent.includes('Atelier des Trois Vallées')")
            self.assertEqual(page.input_value("#form-parametres [name=entreprise_nom]"), "Atelier des Trois Vallées (démo)")
            self.assertIn("equipements", self.texte("#message-action"))
            self.assertIn("parametres", self.texte("#message-action"))

    def test_demo_sauvegardes_indisponibles(self):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        self.aller_a("#/parametres")
        self.attendre_ecran("Paramètres")
        self.assertIn("Indisponible en démo", self.texte("#carte-sauvegardes"))
        self.assertEqual(page.locator("#btn-sauvegarder").count(), 0)
        self.assertEqual(page.locator("button[data-restaurer]").count(), 0)
        # L'export ZIP, lui, marche en démo.
        with page.expect_download() as attente:
            page.click("#btn-export-zip")
        with zipfile.ZipFile(attente.value.path()) as archive:
            self.assertEqual(len([n for n in archive.namelist() if n.endswith(".csv")]), 24)


# ---------------------------------------------------------------------------
# Contrôle de la base
# ---------------------------------------------------------------------------

class TestControle(CasParametres):

    def ligne_du_tableau(self, texte_identifiant, table="equipements.csv", champ=None):
        """Ligne du tableau de contrôle qui contient l'identifiant (et la table, et le champ)."""
        lignes = self.page.locator("#contenu .carte-gravite tbody tr").filter(has_text=texte_identifiant)
        lignes = lignes.filter(has_text=table)
        if champ:
            lignes = lignes.filter(has_text=champ)
        self.assertEqual(lignes.count(), 1, "ligne de contrôle introuvable : %s %s %s" % (texte_identifiant, table, champ))
        return lignes.first

    def test_controle_reference_cassee_identifiant_manquant_et_attribution(self):
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "equipements.csv"
            page = self.ouvrir(serveur, route="#/controle")
            self.attendre_ecran("Contrôle de la base")
            self.assertIn("Aucun problème détecté", self.texte("#contenu"))
            self.assertEqual(page.locator("#btn-attribuer").count(), 0)

            # Deux défauts injectés sur le disque, puis « Relire les fichiers » (sans attendre les 20 s).
            ajouter_texte_csv(chemin, LIGNE_REFERENCE_CASSEE + LIGNE_SANS_IDENTIFIANT)
            ligne_reference = numero_ligne_physique(chemin, "EQ-0998;")
            ligne_sans_id = numero_ligne_physique(chemin, ";'ZZ-97;")
            self.assertEqual(ligne_sans_id, ligne_reference + 1)
            page.click("#btn-relire")
            page.wait_for_selector("#contenu .carte-gravite")

            # Référence cassée : table, ligne du fichier, identifiant, champ, valeur, message.
            reference = self.ligne_du_tableau("EQ-0998", champ="localisation_id")
            cellules = [c.strip() for c in reference.locator("td").all_inner_texts()]
            self.assertEqual(cellules[0], "Référence cassée")
            self.assertEqual(cellules[1], "equipements.csv")
            self.assertEqual(cellules[2], str(ligne_reference))
            self.assertEqual(cellules[3], "EQ-0998")
            self.assertEqual(cellules[4], "localisation_id")
            self.assertEqual(cellules[5], "LOC-9999")
            self.assertIn("LOC-9999", cellules[6])
            # Lien vers la fiche concernée.
            self.assertEqual(reference.locator("a").first.get_attribute("href"), "#/equipement/EQ-0998")

            # Identifiant manquant : table, ligne, champ « id ».
            manquant = self.ligne_du_tableau("Identifiant manquant")
            cellules = [c.strip() for c in manquant.locator("td").all_inner_texts()]
            self.assertEqual(cellules[1], "equipements.csv")
            self.assertEqual(cellules[2], str(ligne_sans_id))
            self.assertEqual(cellules[4], "id")
            self.assertEqual(page.inner_text('[data-compteur="erreur"] .chiffre'), "2")
            self.assertIn("Attribuer les identifiants manquants (1)", self.texte("#btn-attribuer"))

            # « Attribuer les identifiants manquants » : confirmation, puis la ligne reçoit un identifiant.
            page.click("#btn-attribuer")
            page.wait_for_selector("dialog")
            self.assertIn("equipements.csv (1)", self.texte("dialog"))
            page.click("dialog .fenetre-actions .btn-primaire")
            page.wait_for_function(
                "document.getElementById('message-action') && document.getElementById('message-action').textContent.includes('1 identifiant attribué')")
            _, lignes = lire_csv(chemin)
            self.assertEqual([l["id"] for l in lignes if not l["id"]], [])
            ligne_corrigee = [l for l in lignes if l["designation"] == "Machine sans identifiant"][0]
            numero_max = max(int(l["id"][3:]) for l in lignes if re.fullmatch(r"EQ-\d{4}", l["id"]) and l is not ligne_corrigee)
            self.assertEqual(ligne_corrigee["id"], "EQ-%04d" % (numero_max + 1))
            self.assertEqual(page.evaluate("Donnees.problemes().filter(p => p.type === 'identifiant').length"), 0)
            self.assertEqual(page.locator("#btn-attribuer").count(), 0)
            # La référence cassée, elle, reste signalée (l'attribution n'y touche pas).
            self.assertEqual(self.page.inner_text('[data-compteur="erreur"] .chiffre'), "1")
            self.ligne_du_tableau("EQ-0998", champ="localisation_id")
            self.assertIn("identifiants manquants", (serveur.dossier / "journal.csv").read_text(encoding="utf-8"))

    def test_controle_incoherence_di_ot_avec_lien_vers_la_demande(self):
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "demandes.csv"
            entete, demandes = lire_csv(chemin)
            demande = [d for d in demandes if d["id"] == DI_NOUVELLE][0]
            self.assertEqual(demande["statut"], "Nouvelle")
            demande["statut"] = "Acceptée"                       # acceptée mais sans ordre de travail
            ecrire_csv(chemin, entete, demandes)
            page = self.ouvrir(serveur, route="#/controle")
            self.attendre_ecran("Contrôle de la base")
            ligne = self.ligne_du_tableau(DI_NOUVELLE, table="demandes.csv", champ="ot_id")
            cellules = [c.strip() for c in ligne.locator("td").all_inner_texts()]
            self.assertEqual(cellules[0], "Incohérence")
            self.assertEqual(cellules[2], str(numero_ligne_physique(chemin, DI_NOUVELLE + ";")))
            self.assertIn("aucun ordre de travail", cellules[6])
            lien = ligne.locator("a").first
            self.assertEqual(lien.get_attribute("href"), "#/di/" + DI_NOUVELLE)
            # Les compteurs par gravité et par type sont affichés.
            self.assertEqual(page.inner_text('[data-compteur="erreur"] .chiffre'), "1")
            self.assertIn("Incohérence : 1", self.texte('.carte-gravite[data-gravite="erreur"]'))

    def test_controle_relire_les_fichiers_affiche_un_message(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur, route="#/controle")
            self.attendre_ecran("Contrôle de la base")
            # « Relire les fichiers » : message de confirmation, écran réaffiché.
            page.click("#btn-relire")
            self.attendre_toast("Fichiers relus")
            self.assertIn("relus", self.texte("#message-action"))


# ---------------------------------------------------------------------------
# Lot 3 (tâche T46, ARCHITECTURE.md §15.11) : réglages du préventif et des indicateurs, codes de défaillance
# ---------------------------------------------------------------------------

APPEL_PARAMETRES_JS = """async ([fonction, arguments_]) => {
  try { return 'accepté:' + JSON.stringify(await Parametres[fonction](...arguments_)); }
  catch (erreur) { return (erreur instanceof Donnees.ErreurValidation ? 'refus:' : 'erreur:') + erreur.message; }
}"""


def code_propose(lignes, famille, lettre):
    """Code proposé : lettre de la famille + numéro suivant (hors « 99 », réservé à « Autre ») sur 2 chiffres."""
    numeros = [int(m.group(1)) for l in lignes if l["famille"] == famille
               for m in [re.fullmatch(r"[A-Za-z]+(\d+)", sans_apostrophe(l["code"]))] if m]
    suivant = max([n for n in numeros if n < 99] or [0]) + 1
    return "%s%02d" % (lettre, suivant)


class TestReglagesEtCodes(CasParametres):

    def appeler(self, fonction, *arguments):
        return self.page.evaluate(APPEL_PARAMETRES_JS, [fonction, list(arguments)])

    def test_reglages_tolerance_seuil_priorite_horizon_heures_enregistres_et_relus(self):
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "parametres.csv"
            page = self.ouvrir(serveur, route="#/parametres")
            self.attendre_ecran("Paramètres")
            formulaire = "#form-parametres "
            # Valeurs du fichier, ou défaut quand la clé manque (seuil_remplacement_pct n'est pas dans la démo)
            self.assertEqual(page.input_value(formulaire + "[name=tolerance_preventif_pct]"), "10")
            self.assertEqual(page.input_value(formulaire + "[name=seuil_remplacement_pct]"), "50")
            self.assertEqual(page.input_value(formulaire + "[name=priorite_preventif]"), "P3")
            self.assertEqual(page.input_value(formulaire + "[name=horizon_calendrier_semaines]"), "12")
            self.assertEqual(page.input_value(formulaire + "[name=heures_fonct_defaut]"), "8")
            # Bornes : refus sous le champ, fichier inchangé
            avant = chemin.read_bytes()
            for nom, valeur in (("tolerance_preventif_pct", "150"), ("seuil_remplacement_pct", "0"),
                                ("horizon_calendrier_semaines", "60"), ("heures_fonct_defaut", "25"),
                                ("heures_fonct_defaut", "0")):    # 0 : le préventif le remplacerait par 8 en silence
                with self.subTest(nom=nom):
                    page.fill(formulaire + "[name=%s]" % nom, valeur)
                    page.click(formulaire + "button[type=submit]")
                    page.wait_for_selector(formulaire + ".champ[data-champ='%s'].en-erreur" % nom)
                    self.assertEqual(chemin.read_bytes(), avant)
                    page.fill(formulaire + "[name=%s]" % nom, {"tolerance_preventif_pct": "10", "seuil_remplacement_pct": "50",
                                                               "horizon_calendrier_semaines": "12", "heures_fonct_defaut": "8"}[nom])
            # Valeurs correctes : écrites, puis relues après rechargement
            page.fill(formulaire + "[name=tolerance_preventif_pct]", "15")
            page.fill(formulaire + "[name=seuil_remplacement_pct]", "80")
            page.select_option(formulaire + "[name=priorite_preventif]", "P2")
            page.fill(formulaire + "[name=horizon_calendrier_semaines]", "26")
            page.fill(formulaire + "[name=heures_fonct_defaut]", "7,5")
            page.click(formulaire + "button[type=submit]")
            self.attendre_toast("Paramètres enregistrés")
            _, lignes = lire_csv(chemin)
            valeurs = {ligne["cle"]: sans_apostrophe(ligne["valeur"]) for ligne in lignes}
            self.assertEqual([valeurs[c] for c in ("tolerance_preventif_pct", "seuil_remplacement_pct", "priorite_preventif",
                                                    "horizon_calendrier_semaines", "heures_fonct_defaut")],
                             ["15", "80", "P2", "26", "7.5"])
            self.assertEqual(valeurs["delai_p2_h"], "24")                         # le reste n'a pas bougé
            page.reload()
            attendre_pret(page)
            self.attendre_ecran("Paramètres")
            self.assertEqual(page.input_value(formulaire + "[name=tolerance_preventif_pct]"), "15")
            self.assertEqual(page.input_value(formulaire + "[name=seuil_remplacement_pct]"), "80")
            self.assertEqual(page.input_value(formulaire + "[name=priorite_preventif]"), "P2")
            self.assertEqual(page.input_value(formulaire + "[name=heures_fonct_defaut]"), "7,5")
            self.assertEqual(page.evaluate("Donnees.parametre('seuil_remplacement_pct', '')"), "80")

    def test_reglages_des_suggestions_defauts_bornes_et_enregistrement(self):
        """Lot 3 bis (ARCHITECTURE.md §16.1) : trois seuils des suggestions de préventif."""
        defauts = {"suggestion_seuil_pannes": "3", "suggestion_visites_sans_constat": "5", "suggestion_fenetre_mois": "12"}
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "parametres.csv"
            page = self.ouvrir(serveur, route="#/parametres")
            self.attendre_ecran("Paramètres")
            formulaire = "#form-parametres "
            # Clés absentes de la démo : le formulaire montre le défaut, dans une section à part
            for nom, valeur in defauts.items():
                with self.subTest(nom=nom):
                    self.assertEqual(page.input_value(formulaire + "[name=%s]" % nom), valeur)
            self.assertIn("Suggestions de préventif", page.inner_text("#form-parametres"))
            # Bornes (2–20, 3–20, 3–24) : refus sous le champ, fichier inchangé
            avant = chemin.read_bytes()
            for nom, valeur in (("suggestion_seuil_pannes", "1"), ("suggestion_seuil_pannes", "21"),
                                ("suggestion_visites_sans_constat", "2"), ("suggestion_visites_sans_constat", "21"),
                                ("suggestion_fenetre_mois", "2"), ("suggestion_fenetre_mois", "25"),
                                ("suggestion_fenetre_mois", "6,5")):
                with self.subTest(nom=nom, valeur=valeur):
                    page.fill(formulaire + "[name=%s]" % nom, valeur)
                    page.click(formulaire + "button[type=submit]")
                    page.wait_for_selector(formulaire + ".champ[data-champ='%s'].en-erreur" % nom)
                    self.assertEqual(chemin.read_bytes(), avant)
                    page.fill(formulaire + "[name=%s]" % nom, defauts[nom])
            # Valeurs correctes : écrites, puis relues après rechargement
            page.fill(formulaire + "[name=suggestion_seuil_pannes]", "4")
            page.fill(formulaire + "[name=suggestion_visites_sans_constat]", "8")
            page.fill(formulaire + "[name=suggestion_fenetre_mois]", "24")
            page.click(formulaire + "button[type=submit]")
            self.attendre_toast("Paramètres enregistrés")
            _, lignes = lire_csv(chemin)
            valeurs = {ligne["cle"]: sans_apostrophe(ligne["valeur"]) for ligne in lignes}
            self.assertEqual([valeurs[c] for c in defauts], ["4", "8", "24"])
            page.reload()
            attendre_pret(page)
            self.attendre_ecran("Paramètres")
            self.assertEqual(page.input_value(formulaire + "[name=suggestion_visites_sans_constat]"), "8")
            self.assertEqual(page.evaluate("Donnees.parametre('suggestion_fenetre_mois', '')"), "24")

    def test_reglage_fournisseurs_ia_distant_non_par_defaut_puis_enregistre(self):
        """Lot 4 (ARCHITECTURE.md §17.1, D67) : le responsable autorise ou non les IA en ligne (défaut : non). Depuis
        T158 (audit M2, §22.12), en mode serveur la décision est celle du PC serveur (--ia-en-ligne) : la case la
        montre, désactivée, avec la note, et « Enregistrer » n'y touche pas (parametres.csv) ; dans la démo (sans
        serveur, comme en mode dossier), la case s'enregistre comme avant."""
        note = "Décidé sur le PC serveur (Paramètres › Accès et installation)."
        case = "#form-parametres [name=ia_distant_autorise]"
        # Mode serveur sans --ia-en-ligne : « non », sans pouvoir la changer ; Enregistrer laisse la clé hors du fichier
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "parametres.csv"
            page = self.ouvrir(serveur, route="#/parametres")
            self.attendre_ecran("Paramètres")
            self.assertIn("Assistant IA", page.inner_text("#form-parametres"))
            self.assertFalse(page.is_checked(case))
            self.assertTrue(page.is_disabled(case))
            self.assertIn(note, page.inner_text("#form-parametres"))
            page.click("#form-parametres button[type=submit]")
            self.attendre_toast("Paramètres enregistrés")
            _, lignes = lire_csv(chemin)
            self.assertNotIn("ia_distant_autorise", {ligne["cle"] for ligne in lignes}, "clé absente de la démo : jamais écrite")
        # Mode serveur avec --ia-en-ligne : « oui », toujours sans pouvoir la changer
        with ServeurPrevo(arguments=["--ia-en-ligne"]) as serveur:
            page = self.ouvrir(serveur, route="#/parametres")
            self.attendre_ecran("Paramètres")
            page.wait_for_function("(s) => document.querySelector(s) && document.querySelector(s).checked", arg=case)
            self.assertTrue(page.is_disabled(case))
            self.assertIn(note, page.inner_text("#form-parametres"))
        # Démo (sans serveur) : la case s'enregistre, défaut « non »
        page = self.page
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        self.aller_a("#/parametres")
        self.attendre_ecran("Paramètres")
        self.assertFalse(page.is_checked(case))
        self.assertFalse(page.is_disabled(case))
        self.assertNotIn(note, page.inner_text("#form-parametres"))
        self.assertEqual(page.evaluate("Donnees.parametre('ia_distant_autorise', '0')"), "0")
        page.check(case)
        page.click("#form-parametres button[type=submit]")
        self.attendre_toast("Paramètres enregistrés")
        self.assertEqual(page.evaluate("Donnees.parametre('ia_distant_autorise', '0')"), "1")
        page.uncheck(case)
        page.click("#form-parametres button[type=submit]")
        page.wait_for_function("Donnees.parametre('ia_distant_autorise', '0') === '0'")

    def test_codes_ajout_visible_dans_la_fiche_ot_libelle_modifie_et_doublons_refuses(self):
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "codes_defaillance.csv"
            _, codes = lire_csv(chemin)
            attendu = code_propose(codes, "cause", "C")
            page = self.ouvrir(serveur, route="#/parametres")
            self.attendre_ecran("Paramètres")
            carte = "#carte-codes "
            page.select_option(carte + "[name=famille]", "cause")
            page.wait_for_function("(code) => document.querySelector('#carte-codes [name=code]').value === code", arg=attendu)
            # Doublons refusés : code existant (toutes familles), libellé existant dans la famille
            avant = chemin.read_bytes()
            existant = next(c for c in codes if c["famille"] == "cause")
            page.fill(carte + "[name=code]", sans_apostrophe(existant["code"]).lower())
            page.fill(carte + "[name=libelle]", "Libellé nouveau")
            page.click(carte + "button[type=submit]")
            page.wait_for_selector(carte + ".champ[data-champ='code'].en-erreur")
            self.assertIn("existe déjà", page.inner_text(carte + ".champ[data-champ='code'] .erreur-champ"))
            page.fill(carte + "[name=code]", attendu)
            page.fill(carte + "[name=libelle]", existant["libelle"].upper())
            page.click(carte + "button[type=submit]")
            page.wait_for_selector(carte + ".champ[data-champ='libelle'].en-erreur")
            self.assertEqual(chemin.read_bytes(), avant)
            for valeurs, morceau in (({"famille": "cause", "libelle": "", "code": "C77"}, "libellé"),
                                     ({"famille": "cause", "libelle": "Essai", "code": "C 7;7"}, "code"),
                                     ({"famille": "inconnue", "libelle": "Essai", "code": "X01"}, "famille")):
                resultat = self.appeler("ajouterCode", valeurs)
                self.assertTrue(resultat.startswith("refus:") and morceau in resultat, resultat)
            self.assertEqual(chemin.read_bytes(), avant)

            # Ajout par la carte
            page.fill(carte + "[name=libelle]", "Joint de couvercle usé")
            page.click(carte + "button[type=submit]")
            self.attendre_toast("Code ajouté")
            _, codes = lire_csv(chemin)
            nouveau = next(c for c in codes if c["libelle"] == "Joint de couvercle usé")
            self.assertEqual((nouveau["famille"], sans_apostrophe(nouveau["code"])), ("cause", attendu))
            page.wait_for_selector(carte + "[data-code='%s']" % nouveau["id"])
            # Le code suivant est proposé
            page.wait_for_function("(code) => document.querySelector('#carte-codes [name=code]').value !== code", arg=attendu)

            # Libellé modifié (fenêtre), puis affiché
            page.click(carte + "button[data-code-modifier='%s']" % nouveau["id"])
            page.wait_for_selector("dialog [name=libelle]")
            self.assertEqual(page.input_value("dialog [name=libelle]"), "Joint de couvercle usé")
            page.fill("dialog [name=libelle]", "Joint de couvercle détérioré")
            page.click("dialog .fenetre-actions .btn-primaire")
            self.attendre_toast("Libellé modifié")
            _, codes = lire_csv(chemin)
            self.assertEqual(next(c for c in codes if c["id"] == nouveau["id"])["libelle"], "Joint de couvercle détérioré")
            page.wait_for_function("(id) => document.querySelector(`#carte-codes [data-code='${id}']`).textContent.includes('détérioré')",
                                   arg=nouveau["id"])
            resultat = self.appeler("modifierLibelleCode", nouveau["id"], existant["libelle"])
            self.assertTrue(resultat.startswith("refus:") and "existe déjà" in resultat, resultat)

            # Visible dans la liste des causes de la fiche d'un OT ouvert (onglet Compte rendu)
            ot = scenarios_demo()["ot_statut_en_cours"]
            self.aller_a("#/ot/" + ot)
            page.wait_for_selector(".onglet[data-onglet='compte-rendu']")
            page.click(".onglet[data-onglet='compte-rendu']")
            page.wait_for_selector("#form-compte-rendu [name=cause_code]")
            options = page.eval_on_selector_all("#form-compte-rendu [name=cause_code] option", "o => o.map(e => [e.value, e.textContent])")
            self.assertIn([attendu, attendu + " — Joint de couvercle détérioré"], options)
            journal = (serveur.dossier / "journal.csv").read_text(encoding="utf-8")
            self.assertIn("codes_defaillance;%s;création" % nouveau["id"], journal)


if __name__ == "__main__":
    unittest.main()
