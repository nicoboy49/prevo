"""Recette du lot 7 en mode serveur : accès et installation de bout en bout (tâche T180, ARCHITECTURE.md §22 ; CDC
D121 à D140 ; CS130 assistant et Paramètres, CS132 Solo ; CS119 : la suite des lots 1 à 6 est rejouée à part).

Chaque classe est un parcours d'utilisateur réel, en navigateur, avec son serveur ; chaque parcours vérifie l'écran
(textes, boutons présents ou absents), le disque (CSV relus en Python, JSON d'accès, configuration) et la console du
navigateur (CasNavigateur : seuls les refus attendus — 401 de la sonde, 403 des tables du demandeur — sont permis).

    Solo        serveur du processus sans configuration, dossier de données vide (élévation et relance injectées) ;
                l'assistant en navigateur : « Moi seul », « Seulement sur ce PC », prénom et nom (aucun mot de passe),
                démarrage « à la main », copie « plus tard », « Par quoi commencer ? » → la démo, « Rester ici »,
                « Terminer » ; prevo.config.json comparé clé à clé à la configuration Solo « ce PC » de
                test_installation_api ; la relance est simulée par un serveur.py réel (ServeurPrevo) sur le même dossier
                de données avec le fichier écrit (--config) ; puis à 375 px : profil Responsable (Demandeur et Technicien
                toujours proposés), accueil avec « Nouvel OT » en premier, menu allégé (Équipe et Planning sous « Plus »),
                étiquette QR de PO-02 relue par jsQR (sa route ouverte sur ce PC : voir TestEtiquetteCePc) → fiche →
                « Créer un OT » (technicien « moi » pré-rempli) → « Démarrer » → « Clore » (une seule fenêtre) ;
                Paramètres : mode Solo, clôture en une étape et l'état du serveur ; sur le disque : l'OT clos avec ses
                deux dates égales, deux lignes de journal, l'entrée de la file du wiki, le temps passé, parametres.csv
                (mode_solo, cloture_une_etape, solo_technicien_id), techniciens.csv (« moi », TEC-0005), aucun compte.
    Atelier     ServeurAtelier (tests/atelier.py : 0.0.0.0, comptes, porte http et application https, faux mkcert ;
                SkipTest sans adresse réseau ou sans openssl) : le responsable se connecte sur le PC (127.0.0.1) ; une
                étiquette relue par jsQR porte l'adresse de la porte ; Équipe › Accès : compte technicien (mot de passe
                provisoire lu une fois) et invitation (QR relu = lien) ; technicien (second contexte, sur le réseau, par
                la porte) : provisoire → changement obligatoire → ses écrans sans taux horaire ni prix (DOM, données en
                mémoire et CSV reçus ; le responsable, lui, les voit) ; un iPhone qui ne fait pas confiance voit la page
                « Faites confiance au PC atelier » (étapes iPhone, /acces/ca.crt) ; téléphone (profil Pixel 7 qui fait
                confiance au PC atelier) : étiquette → porte → https, route gardée → lien d'invitation → nom → demandeur
                → fiche → « Signaler » avec photo, sans « Proposer avec l'IA » (arbitrage du 2026-10-28) alors que l'IA
                est activée sur le poste, aucune requête /api/ia → la demande et sa photo AAAAMMJJ-HHMMSS-… sur le
                disque ; le responsable révoque l'appareil → 401 et bandeau « n'est plus autorisé » à la requête
                suivante du téléphone ; « Sauvegarder maintenant » puis
                « Tester » (vert) ; acces/ dans la sauvegarde sans sessions.json ; journal-acces.csv avec creation,
                invitation, appareil, connexion, modification, revocation, sans mot de passe ni jeton ; appareils.json
                avec des empreintes seulement (SHA-256 recalculés ici).
    Intranet    ServeurPrevo(comptes=True, mandataire, noms « gmao.entreprise.lan », demandeurs avec compte) derrière
                deux MandataireTest (https, X-Forwarded-For de deux postes) : le demandeur se connecte (cookie Secure,
                adresses de /api/info sur l'hôte d'origine), signale une demande, ne lit que ses tables (403 sur les
                autres, versions limitées, rien en mémoire) ; l'enrôlement d'un appareil est refusé (403, message) ; le
                responsable voit l'adresse d'origine dans Équipe › Accès › Journal (et sur le disque) et l'enrôlement
                désactivé ; un client direct qui forge X-Forwarded-* n'obtient rien (réseau : aucune écoute ; ce PC avec
                un hôte d'origine étranger : 403 ; sans session : 401).
    Tailscale   assistant « Moi seul » / « Aussi hors de l'atelier » avec le faux tailscale (PREVO_TAILSCALE) : compte
                responsable, réseau privé, Tailscale appliqué d'un clic (« serve » lancée et vérifiée, jamais « up »),
                démarrage avec le PC (élévation notée, jamais lancée), copie des sauvegardes vers un dossier temporaire,
                la démo ; configuration comparée clé à clé ; relance simulée par serveur.py réel : copie externe faite au
                démarrage (acces/ copié, jamais sessions.json) ; un MandataireTest joue « tailscale serve » : connexion par
                l'écran, cookie Secure, adresses en https sur le nom Tailscale, journal avec l'adresse et l'utilisateur
                Tailscale ; nouvelle relance avec le faux « Stopped » : la session tient, l'accueil du responsable signale
                Tailscale déconnecté et Paramètres › Accès et installation montre l'état du serveur.
Défauts trouvés (tests expectedFailure, docstring de chacun) :
    TestEtiquetteCePc         en portée « ce PC », les adresses réseau annoncées (QR des étiquettes) ne répondent pas ;
    TestConnexionsInactives   32 connexions keep-alive inactives bloquent toute nouvelle requête jusqu'à 60 s.
Aucune commande d'administrateur, aucune sortie réseau, jamais le vrai mkcert ni le vrai tailscale, jamais le dossier
donnees/ réel ni C:\\Prevo (« Rester ici ») ; aucune relance réelle (config.relancer injecté ; « Appliquer et relancer »
n'est jamais cliqué sur un serveur.py réel). Captures facultatives dans tests/resultats/recette-lot7/ (hors dépôt).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_recette_lot7.py" -v
"""
import csv
import datetime
import hashlib
import http.client
import json
import re
import socket
import time
import unittest
from pathlib import Path

import commun
from atelier import ServeurAtelier, adresse_reseau, motif_refus_du_demandeur, requete
from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret
from mandataire_test import MandataireTest
from test_demandes import dimensions_jpeg, fichier_png
from test_installation_api import ATTENDU_SOLO_CE_PC, ATTENDU_SOLO_DEHORS, FAUX_TAILSCALE, NOM_TAILSCALE, serveur
from test_installation_ecrans import CasInstallation
from test_recette_lot1 import MOTIF_PHOTO
from test_wiki_ingestion import regler_ia

CAPTURES = RACINE / "tests" / "resultats" / "recette-lot7"
EQUIPEMENT = "EQ-0005"                       # PO-02, pompe centrifuge (aucune habilitation exigée)
REPERE = "PO-02"
MOT_DE_PASSE_ASSISTANT = "phrase de passe du responsable"
MOTS_DE_PASSE = {identifiant: mot_de_passe for identifiant, _, _, mot_de_passe, _ in commun.COMPTES_DE_TEST.values()}
NOUVEAU_MOT_DE_PASSE_TECHNICIEN = "une phrase de passe pour sophie"
NOM_TELEPHONE = "Camille Roux"
NOM_INTRANET = "gmao.entreprise.lan"
ADRESSE_LEA, ADRESSE_RESPONSABLE = "10.20.30.40", "10.20.30.50"
ADRESSE_TAILNET, UTILISATEUR_TAILSCALE = "100.64.0.7", "nicolas@github"
TABLES_DU_DEMANDEUR = set(serveur.TABLES_DU_DEMANDEUR)
COMMANDES_TAILSCALE_INTERDITES = ("up", "down", "login", "logout", "install", "update")

# Chromium note en console.error toute réponse ≥ 400 : seuls les refus attendus sont permis, précisément.
ERREUR_401_SONDE = re.compile(r"status of 401 .*/api/versions")          # sans session : la sonde d'App
ERREUR_403_ENROLER = re.compile(r"status of 403 .*/api/enroler")
ERREUR_PING_SANS_CONFIANCE = re.compile(r"net::ERR_CERT|/api/ping")    # la porte essaie l'https sans confiance
MESSAGE_APPAREIL_REFUSE = "n'est plus autorisé"
MESSAGE_DECONNECTE = "Tailscale est déconnecté : les téléphones hors de l'atelier ne joignent plus Prévo."

LARGEURS_JS = "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
# Lecture d'un QR (SVG de Prévo) par jsQR, dans la page, comme l'appareil photo d'un téléphone.
LIRE_QR_JS = """async (selecteur) => {
    const svg = document.querySelector(selecteur);
    if (!svg) return null;
    const image = new Image();
    image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(svg));
    await image.decode();
    const toile = document.createElement('canvas');
    toile.width = 400; toile.height = 400;
    const contexte = toile.getContext('2d');
    contexte.fillStyle = '#fff';
    contexte.fillRect(0, 0, 400, 400);
    contexte.drawImage(image, 0, 0, 400, 400);
    const code = jsQR(contexte.getImageData(0, 0, 400, 400).data, 400, 400);
    return code ? code.data : null;
}"""
TEXTE_CSV_JS = "async (table) => { const r = await fetch('/api/csv/' + table, { cache: 'no-store' }); return [r.status, await r.text()]; }"
JSON_JS = "async (chemin) => { const r = await fetch(chemin, { cache: 'no-store' }); return [r.status, await r.json()]; }"


# ---------------------------------------------------------------------------
# Disque
# ---------------------------------------------------------------------------

def brut(valeur):
    """Valeur sans l'apostrophe de protection des CSV (ARCHITECTURE.md §3.2)."""
    return valeur[1:] if valeur.startswith("'") else valeur


def lire_csv(chemin):
    """Lignes d'un CSV de Prévo relu par le module csv (BOM retiré, « ; »), valeurs sans apostrophe de protection."""
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        return [{cle: brut(valeur or "") for cle, valeur in ligne.items()}
                for ligne in csv.DictReader(fichier, delimiter=";") if any((v or "").strip() for v in ligne.values())]


def table(dossier, nom):
    return lire_csv(Path(dossier) / (nom + ".csv"))


def ligne(dossier, nom, identifiant):
    return next((l for l in table(dossier, nom) if l["id"] == identifiant), None)


def parametres(dossier):
    return {l["cle"]: l["valeur"] for l in table(dossier, "parametres")}


def journal_acces(dossier):
    return lire_csv(Path(dossier) / "acces" / "journal-acces.csv")


def sha256(texte):
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def textes_du_dossier(dossier):
    """{chemin relatif: texte} des fichiers texte d'un dossier (CSV, JSON, log), pour y chercher un secret."""
    dossier = Path(dossier)
    return {chemin.relative_to(dossier).as_posix(): chemin.read_text(encoding="utf-8", errors="replace")
            for chemin in dossier.rglob("*") if chemin.is_file() and chemin.suffix in (".csv", ".json", ".log", ".txt")}


def attendre_que(condition, delai_s=15, message="condition jamais remplie"):
    fin = time.monotonic() + delai_s
    while time.monotonic() < fin:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError(message)


def capturer(page, nom):
    """Capture facultative pour la recette réelle (tests/resultats/, hors dépôt)."""
    try:
        CAPTURES.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(CAPTURES / (nom + ".png")), full_page=True)
    except Exception as erreur:  # une capture ratée ne fait jamais échouer la recette
        print("  [capture] %s impossible : %s" % (nom, erreur))


def serveur_relance(fichier_configuration, dossier_donnees, environnement=None):
    """« Le serveur relancé » : serveur.py réel (ServeurPrevo) sur LE MÊME dossier de données (pas une copie) avec le
    prevo.config.json écrit par l'assistant ; --config et --donnees donnés après ceux de ServeurPrevo l'emportent."""
    reel = ServeurPrevo(source=None, environnement=environnement,
                        arguments=["--config", str(fichier_configuration), "--donnees", str(dossier_donnees)])
    reel.demarrer()
    return reel


# ---------------------------------------------------------------------------
# Gestes communs
# ---------------------------------------------------------------------------

class GestesRecette:
    """Gestes d'utilisateur communs aux parcours (mélangés à CasNavigateur ou CasInstallation)."""

    def attendre_etat(self, etat, page=None):
        (page or self.page).wait_for_function("(e) => document.documentElement.dataset.etat === e", arg=etat)

    def se_connecter(self, page, identifiant, mot_de_passe):
        """Écran de connexion (T155) : identifiant, mot de passe, « Se connecter »."""
        page.wait_for_selector("#connexion-formulaire", state="visible")
        page.fill("#connexion-identifiant", identifiant)
        page.fill("#connexion-mot-de-passe", mot_de_passe)
        page.click("#connexion-valider")

    def nouvelle_page(self, **options):
        """Contexte et page de plus (un autre appareil) : surveillés, fermés à la fin du test (ou avant, par
        ranger_l_appareil)."""
        options.setdefault("locale", "fr-FR")
        contexte = self.navigateur.new_context(**options)
        self.addCleanup(self.ranger_l_appareil, contexte)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        page = contexte.new_page()
        self.surveiller(page)
        return contexte, page

    @staticmethod
    def ranger_l_appareil(contexte):
        """Ferme le contexte d'un appareil dont le rôle est fini : ses connexions keep-alive inactives sont rendues au
        serveur (sinon chacune tient une des 32 places du serveur jusqu'à 60 s : voir TestConnexionsInactives)."""
        try:
            contexte.close()
        except Exception:  # déjà fermé
            pass

    def telephone(self, nom="Pixel 7", **options):
        """Profil Playwright d'un téléphone joué dans Chromium (le type de navigateur du profil est ignoré)."""
        profil = dict(self._playwright.devices[nom])
        profil.pop("default_browser_type", None)
        profil.update(options)
        return self.nouvelle_page(**profil)

    def aller(self, page, route, attendre):
        page.evaluate("(route) => { location.hash = route; }", route)
        page.wait_for_selector(attendre)

    def lire_qr(self, page, selecteur):
        page.wait_for_selector(selecteur)
        return page.evaluate(LIRE_QR_JS, selecteur)

    def dialogue(self, page):
        return page.locator("dialog[open]").last

    def fermer_dialogue(self, page):
        self.dialogue(page).locator(".fenetre-actions button").last.click()
        page.wait_for_selector("dialog[open]", state="detached")

    def sans_defilement_horizontal(self, contexte, page=None):
        largeurs = (page or self.page).evaluate(LARGEURS_JS)
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))

    def quitter(self, *pages):
        """Les pages quittent le serveur avant son arrêt (sinon le rafraîchissement noterait une erreur réseau)."""
        for page in pages:
            page.goto("about:blank")

    def signaler_avec_photo(self, page, symptome, photo=True):
        """Fiche de l'équipement ouverte : « Signaler un problème », symptôme, impact, photo ; rend le numéro de la DI.
        L'IA est réservée aux techniciens et au responsable (arbitrage du 2026-10-28) : ni bouton ni zone d'IA."""
        page.click("a.parc-signaler")
        page.wait_for_selector(".di-formulaire")
        self.assertIn(REPERE, page.inner_text(".selecteur-choisi"))
        self.assertTrue(page.is_hidden(".di-ia"))
        self.assertEqual(page.locator(".di-ia button").count(), 0)
        self.assertNotIn("Proposer avec l'IA", page.inner_text("#contenu"))
        page.fill("input[name=symptome]", symptome)
        page.click("label.tuile:has(input[value='dégradé'])")
        if photo:
            page.locator(".di-fichier-photo").set_input_files(fichier_png(3000, 2000))
            page.wait_for_selector(".di-apercu:not([hidden]) img")
        page.click(".di-envoyer")
        page.wait_for_selector(".di-numero")
        return page.inner_text(".di-numero").strip()

    def verifier_demande_sur_le_disque(self, dossier, numero, demandeur, photo=True):
        demande = ligne(dossier, "demandes", numero)
        self.assertIsNotNone(demande, "la demande %s est dans demandes.csv" % numero)
        self.assertEqual((demande["demandeur"], demande["equipement_id"], demande["statut"]), (demandeur, EQUIPEMENT, "Nouvelle"))
        if photo:
            self.assertRegex(demande["photo"], MOTIF_PHOTO)                   # préfixe AAAAMMJJ-HHMMSS- imposé (F4)
            chemin = Path(dossier) / "documents" / demande["photo"]
            self.assertTrue(chemin.is_file(), chemin)
            self.assertLessEqual(max(dimensions_jpeg(chemin.read_bytes())), 1280)
        return demande


class CasRecetteLot7(GestesRecette, CasNavigateur):
    """Parcours sur un serveur.py réel (ServeurPrevo, ServeurAtelier)."""


class CasRecetteAssistant(GestesRecette, CasInstallation):
    """Parcours qui commencent par l'assistant (serveur du processus de test_installation_ecrans : dossier temporaire,
    élévation et relance injectées, faux mkcert et faux tailscale absents par défaut)."""

    def choisir_moi_seul(self):
        """Étape 1 : « Moi seul », puis l'étape de la portée."""
        page = self.page
        self.assertIn("Moi seul", page.inner_text('#installation-contenu label:has(input[name="situation"][value="seul"])'))
        self.cocher("situation", "seul")
        self.continuer()
        self.attendre_etape("portee")
        return page

    def terminer_avec_la_demo(self):
        """Étape 8 sur une base absente : « Par quoi commencer ? » → la démo ; « Rester ici » (jamais C:\\Prevo) ;
        « Terminer » → configuration écrite, relance notée ; rend le fichier de configuration relu."""
        page = self.page
        page.wait_for_selector("#inst-base", state="visible")
        self.assertIn("Par quoi commencer", page.inner_text("#inst-base"))
        self.cocher("base", "demo")
        page.wait_for_selector("#inst-dossier", state="visible")
        page.click("#inst-dossier-garder")
        page.wait_for_selector("#inst-dossier", state="hidden")
        page.wait_for_selector("#fiche-qr-ouvrir svg")
        page.click("#inst-terminer")
        page.wait_for_selector("#inst-attente", state="visible")
        self.assertIn("Prévo se relance", page.inner_text("#inst-attente"))
        page.wait_for_function("document.getElementById('inst-terminer').disabled")
        self.assertEqual(self.enregistreur.relances, [None])                 # relance demandée, jamais lancée
        donnees = self.dossier / "donnees"
        self.assertFalse((donnees / "installation.json").exists())           # brouillon supprimé
        self.assertEqual(sorted(p.stem for p in donnees.glob("*.csv")), sorted(serveur.TABLES))   # la démo
        fichier = self.dossier / "prevo.config.json"
        self.assertTrue(fichier.is_file())
        return fichier

    def comparer_cle_a_cle(self, fichier, attendu):
        ecrit = json.loads(fichier.read_text(encoding="utf-8"))
        self.assertEqual(sorted(cle for cle in ecrit if not cle.startswith("_")), sorted(attendu))
        self.assertIn("_aide", ecrit)
        for cle, valeur in attendu.items():
            with self.subTest(cle=cle):
                self.assertEqual(ecrit[cle], valeur)
        return ecrit

    def arreter_l_assistant(self, instance):
        """La page quitte le serveur de l'assistant, qui s'arrête (relance simulée : un autre serveur prend la suite)."""
        self.quitter(self.page)
        instance.arreter()
        self.serveurs.remove(instance)


# ---------------------------------------------------------------------------
# 1. Solo : l'assistant, la relance, puis un OT clos en une étape à 375 px
# ---------------------------------------------------------------------------

class TestParcoursSolo(CasRecetteAssistant):

    def test_moi_seul_sur_ce_pc_avec_la_demo_puis_ot_clos_en_une_etape_a_375_px(self):
        page = self.page
        instance = self.lancer()                                     # premier lancement, dossier de données vide
        self.ouvrir_assistant(instance)
        self.assertIn("Tant que l'installation n'est pas terminée, Prévo n'est joignable que sur ce PC.",
                      page.inner_text("#installation-premiere-ligne"))
        self.assertEqual(page.locator("#inst-migration").count(), 0)          # aucune base de 1.2
        self.choisir_moi_seul()
        self.assertTrue(page.is_checked('#installation-contenu input[name="portee"][value="ce-pc"]'))   # défaut Solo
        self.assertIn("Seulement sur ce PC", page.inner_text('#installation-contenu label:has(input[name="portee"][value="ce-pc"])'))
        self.continuer()
        self.attendre_etape("compte")
        self.assertEqual(page.locator("#installation-contenu input[type=password]").count(), 0)   # sur ce PC : le nom seul
        page.fill("#inst-prenom", "Nicolas")
        page.fill("#inst-nom", "Briand")
        self.continuer()
        self.attendre_etape("demarrage")                             # certificat et Tailscale sans objet : sautés
        self.assertEqual(len(self.lignes_sautees()), 2)
        self.cocher("demarrage", "aucun")
        self.continuer()
        self.attendre_etape("sauvegardes")
        page.click("#inst-sauvegardes-plus-tard")
        self.attendre_etape("recapitulatif")
        self.assertIn("Moi seul", page.inner_text("#installation-contenu .installation-recap"))
        fichier = self.terminer_avec_la_demo()
        self.assertEqual(self.enregistreur.eleves, [])                # aucune élévation demandée
        # La configuration écrite est celle du parcours Solo « ce PC » de l'API (étude §6.1), clé à clé.
        self.comparer_cle_a_cle(fichier, ATTENDU_SOLO_CE_PC)
        donnees = self.dossier / "donnees"
        self.assertFalse((donnees / "acces" / "comptes.json").exists())      # Solo sur ce PC : aucun compte
        reglages = parametres(donnees)
        self.assertEqual((reglages["mode_solo"], reglages["cloture_une_etape"], reglages["solo_technicien_id"]),
                         ("1", "1", "TEC-0005"))
        techniciens = table(donnees, "techniciens")
        self.assertEqual(len(techniciens), 5)                                # les quatre de la démo et « moi »
        moi = techniciens[-1]
        self.assertEqual((moi["id"], moi["prenom"], moi["nom"], moi["actif"]), ("TEC-0005", "Nicolas", "Briand", "1"))

        # Relance simulée : serveur.py réel sur le même dossier de données, avec le fichier écrit.
        self.arreter_l_assistant(instance)
        reel = serveur_relance(fichier, donnees)
        self.addCleanup(reel.arreter)
        console = reel.sortie_console()
        self.assertIn("ce PC seulement (127.0.0.1)", console)
        self.assertNotIn("pas encore faite", console)

        # À 375 px : profil Responsable (portée « ce PC », sans compte), mode Solo.
        contexte, tel = self.nouvelle_page(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True)
        tel.goto(reel.url + "/")
        self.attendre_etat("profil", tel)
        self.assertTrue(tel.is_hidden("#ecran-installation"))
        self.assertTrue(tel.is_hidden("#ecran-profil .lien-installation"))  # installation faite : plus de lien
        for choix in ("#profil-demandeur", "#profil-technicien", "#profil-responsable"):   # rôles toujours proposés
            self.assertTrue(tel.is_visible(choix), choix)
        tel.click("#profil-responsable")
        attendre_pret(tel)
        self.assertEqual(tel.evaluate("App.mode"), "serveur")
        self.assertFalse(tel.evaluate("App.comptesExiges()"))
        self.assertTrue(tel.evaluate("App.modeSolo()"))
        self.assertEqual(tel.evaluate("App.technicienSolo()"), "TEC-0005")
        self.aller(tel, "#/accueil", "#accueil-solo")
        self.assertEqual(tel.evaluate("[...document.querySelectorAll('#accueil-solo .btn')].map((b) => b.id)"),
                         ["accueil-nouvel-ot", "accueil-signaler"])            # « Nouvel OT » en premier
        self.assertIn("Nouvel OT", tel.inner_text("#accueil-nouvel-ot"))
        self.sans_defilement_horizontal("accueil Solo", tel)
        # Menu allégé : Équipe et Planning ne sont pas dans la barre du bas, mais sous « Plus ».
        en_bas = tel.evaluate("[...document.querySelectorAll('#barre-bas a')].map((a) => a.dataset.ecran)")
        self.assertNotIn("equipe", en_bas)
        self.assertNotIn("planning", en_bas)
        tel.click("#btn-plus")
        tel.wait_for_selector("dialog .liste-plus", state="visible")
        self.assertEqual(tel.locator("dialog .liste-plus a[href='#/equipe']").count(), 1)
        self.assertEqual(tel.locator("dialog .liste-plus a[href='#/planning']").count(), 1)
        self.fermer_dialogue(tel)
        capturer(tel, "solo-accueil-375")

        # L'étiquette de PO-02 (QR relu par jsQR) ouvre la fiche, « Créer un OT » en premier.
        self.aller(tel, "#/parc/etiquettes?ids=" + EQUIPEMENT,
                   "#etiquettes-apercu .etiquette[data-equipement='%s'] .etiquette-qr svg" % EQUIPEMENT)
        adresse = self.lire_qr(tel, "#etiquettes-apercu .etiquette[data-equipement='%s'] .etiquette-qr svg" % EQUIPEMENT)
        self.assertEqual(adresse, tel.evaluate("(id) => App.urlFicheEquipement(id)", EQUIPEMENT))
        self.assertTrue(adresse.endswith(":%d/#/equipement/%s" % (reel.port, EQUIPEMENT)), adresse)
        print("\n  [solo] étiquette de %s relue : %s" % (REPERE, adresse))
        # En portée « ce PC », l'adresse réseau du QR ne répond pas (défaut montré par
        # TestEtiquetteCePc) : la route de l'étiquette est ouverte sur ce PC.
        tel.goto(reel.url + "/#" + adresse.split("#", 1)[1])
        tel.wait_for_selector("#parc-creer-ot")
        self.assertIn("Créer un OT", tel.inner_text("#parc-creer-ot"))
        self.assertEqual(tel.evaluate("[...document.querySelectorAll('.parc-actions a')].map((a) => a.getAttribute('href'))")[:2],
                         ["#/ot/nouveau?equipement=" + EQUIPEMENT, "#/di/nouvelle?equipement=" + EQUIPEMENT])
        self.sans_defilement_horizontal("fiche " + REPERE, tel)
        tel.click("#parc-creer-ot")
        tel.wait_for_selector("#form-nouvel-ot")
        self.assertEqual(tel.input_value("#form-nouvel-ot [name='technicien_id']"), "TEC-0005")   # « moi » pré-rempli
        tel.fill("#form-nouvel-ot [name='titre']", REPERE + " — bruit de roulement côté moteur")
        tel.select_option("#form-nouvel-ot [name='type']", "correctif immédiat")
        tel.click("#form-nouvel-ot button[type=submit]")
        tel.wait_for_selector(".ot-fiche .ot-numero")
        ot_id = tel.inner_text(".ot-fiche .ot-numero").strip()
        self.assertEqual(tel.evaluate("location.hash"), "#/ot/" + ot_id)
        # Exécution : « Démarrer », puis « Clore » (une seule fenêtre : clôture technique et administrative).
        tel.click("button[data-action='transition'][data-cible='En cours']")
        tel.wait_for_function("() => { const b = document.querySelector('.ot-badges .badge.statut'); return b && b.textContent === 'En cours'; }")
        codes = tel.evaluate("""() => { const code = (famille) => Donnees.lignes('codes_defaillance')
            .find((c) => c.famille === famille && c.code).code; return [code('cause'), code('remède')]; }""")
        tel.click("#ot-clore")
        tel.wait_for_selector("dialog [name='compte_rendu']", state="visible")
        self.assertEqual(tel.locator("dialog").count(), 1)
        self.assertEqual(tel.input_value("dialog [name='technicien_id']"), "TEC-0005")
        tel.fill("dialog [name='heures']", "1,5")
        tel.select_option("dialog [name='cause_code']", codes[0])
        tel.select_option("dialog [name='remede_code']", codes[1])
        tel.fill("dialog [name='compte_rendu']", "Roulement côté moteur bruyant : graissé puis essai de 10 min sans bruit.")
        tel.check("dialog [name='remise_service']")
        capturer(tel, "solo-clore-375")
        tel.click("dialog .fenetre-actions .btn-primaire")
        tel.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé administrativement'", arg=ot_id)
        tel.wait_for_selector("dialog", state="detached")
        self.assertEqual(tel.locator("#ot-clore").count(), 0)                # OT verrouillé
        # Paramètres : mode Solo et clôture en une étape posés par l'assistant ; l'état du serveur (CS130).
        self.aller(tel, "#/parametres", "#carte-acces #acces-contenu[data-lu]")
        self.assertEqual(tel.locator("#btn-quitter-solo").count(), 1)
        self.assertTrue(tel.is_checked("#form-parametres [name='cloture_une_etape']"))
        self.assertIn("Terminée", tel.inner_text("#acces-installation"))
        self.assertIn("Seulement sur ce PC", tel.inner_text("#acces-portee"))
        self.assertIn("Aucune copie réglée", tel.inner_text("#acces-copie"))
        self.sans_defilement_horizontal("Paramètres", tel)
        self.quitter(tel)
        self.assertEqual(self.enregistreur.relances, [None])                 # la seule relance : celle de « Terminer »

        # Le disque : l'OT clos (deux dates égales), deux lignes de journal, la file du wiki.
        ot = ligne(donnees, "ordres_travail", ot_id)
        self.assertEqual((ot["statut"], ot["equipement_id"], ot["technicien_id"], ot["type"]),
                         ("Clôturé administrativement", EQUIPEMENT, "TEC-0005", "correctif immédiat"))
        self.assertTrue(ot["date_cloture_tech"])
        self.assertEqual(ot["date_cloture_tech"], ot["date_cloture_admin"])
        self.assertEqual((ot["cause_code"], ot["remede_code"], ot["remise_service"]), (codes[0], codes[1], "1"))
        clotures = [l["action"] for l in table(donnees, "journal")
                    if l["table"] == "ordres_travail" and l["id_ligne"] == ot_id and "→ Clôturé" in l["action"]]
        self.assertEqual(len(clotures), 2, clotures)
        self.assertTrue(clotures[0].endswith("statut En cours → Clôturé techniquement"), clotures)
        self.assertTrue(clotures[1].endswith("statut Clôturé techniquement → Clôturé administrativement"), clotures)
        file_du_wiki = [l for l in table(donnees, "wiki_journal") if l["nature"] == "ingestion" and l["ot_id"] == ot_id]
        self.assertEqual([l["statut"] for l in file_du_wiki], ["en file"])
        temps = [l for l in table(donnees, "ot_temps") if l["ot_id"] == ot_id]
        self.assertEqual([(l["technicien_id"], l["heures"]) for l in temps], [("TEC-0005", "1.5")])
        self.assertEqual(parametres(donnees)["mode_solo"], "1")
        print("  [solo] %s créé depuis l'étiquette, clos en une étape le %s" % (ot_id, ot["date_cloture_tech"]))


# ---------------------------------------------------------------------------
# 2. Atelier : comptes, invitation, téléphone, technicien, révocation, sauvegarde
# ---------------------------------------------------------------------------

class TestParcoursAtelier(CasRecetteLot7):

    def test_compte_invitation_telephone_technicien_revocation_et_sauvegarde(self):
        pc = self.page
        self.autoriser_erreur(ERREUR_401_SONDE)
        self.autoriser_erreur(motif_refus_du_demandeur())
        with ServeurAtelier() as atelier:
            donnees = atelier.dossier
            # PC serveur (127.0.0.1) : le responsable se connecte par l'écran.
            pc.goto(atelier.url_pc + "/#/accueil")
            self.attendre_etat("connexion")
            self.se_connecter(pc, "nicolas.briand", MOTS_DE_PASSE["nicolas.briand"])
            attendre_pret(pc)
            self.assertEqual(pc.evaluate("App.profil"), {"type": "responsable", "nom": "Nicolas Briand", "technicienId": ""})
            # L'étiquette de PO-02 porte l'adresse de la porte (http), jamais l'adresse https.
            selecteur_qr = "#etiquettes-apercu .etiquette[data-equipement='%s'] .etiquette-qr svg" % EQUIPEMENT
            self.aller(pc, "#/parc/etiquettes?ids=" + EQUIPEMENT, selecteur_qr)
            url_etiquette = self.lire_qr(pc, selecteur_qr)
            self.assertEqual(url_etiquette, atelier.url_porte + "/#/equipement/" + EQUIPEMENT)
            print("\n  [atelier] étiquette de %s relue : %s" % (REPERE, url_etiquette))

            # Équipe › Accès : un compte technicien, mot de passe provisoire lu une seule fois.
            self.aller(pc, "#/equipe", "#equipe-acces")
            pc.click("#equipe-acces")
            pc.wait_for_selector("#acces-comptes tbody tr")
            pc.click("#acces-creer-compte")
            dialogue = self.dialogue(pc)
            dialogue.locator("input[name=prenom]").fill("Sophie")
            dialogue.locator("input[name=nom]").fill("Lambert")
            dialogue.locator("select[name=role]").select_option("technicien")
            dialogue.locator("select[name=technicien_id]").select_option("TEC-0003")
            dialogue.locator("button:has-text('Créer le compte')").click()
            pc.wait_for_selector("#acces-mot-de-passe-provisoire")
            provisoire = pc.input_value("#acces-mot-de-passe-provisoire")
            self.assertEqual(len(provisoire), 16)
            self.assertIn("sophie.lambert", self.dialogue(pc).inner_text())
            self.fermer_dialogue(pc)
            self.assertNotIn(provisoire, pc.content())                       # montré une seule fois
            pc.wait_for_selector("#acces-comptes tbody tr:has(td b:text-is('sophie.lambert')):has-text('Mot de passe provisoire')")
            # Une invitation : le QR relu par jsQR est le lien montré, sur l'adresse de la porte.
            pc.click(".barre-onglets [role=tab]:has-text('Appareils')")
            pc.wait_for_selector("#acces-inviter")
            pc.click("#acces-creer-invitation")
            pc.wait_for_selector("#acces-invitation-qr svg")
            lien = pc.input_value("#acces-invitation-lien")
            self.assertEqual(self.lire_qr(pc, "#acces-invitation-qr svg"), lien)
            self.assertTrue(lien.startswith(atelier.url_porte + "/#/enroler/"), lien)
            jeton_invitation = lien.rsplit("/", 1)[1]
            capturer(pc, "atelier-invitation")
            self.fermer_dialogue(pc)
            self.assertNotIn(jeton_invitation, pc.content())

            # Le responsable, lui, voit les prix et les taux horaires (le contraste rend la vérification suivante probante).
            self.aller(pc, "#/magasin", "#contenu table tbody tr")
            self.assertIn("€", pc.inner_text("#contenu"))
            self.aller(pc, "#/equipe", "#contenu h1:has-text('Équipe')")
            pc.wait_for_selector("#contenu table")
            self.assertIn("Taux horaire", pc.inner_text("#contenu"))

            # Technicien (second contexte, sur le réseau, par la porte) : provisoire → changement obligatoire → ses
            # écrans. Chaque appareil est rangé quand son rôle est fini (voir TestConnexionsInactives).
            contexte_tech, tech = self.nouvelle_page(viewport={"width": 1280, "height": 800}, ignore_https_errors=True)
            tech.goto(atelier.url_porte + "/#/accueil")
            tech.wait_for_url(atelier.url_https + "/#/accueil")
            self.attendre_etat("connexion", tech)
            self.se_connecter(tech, "sophie.lambert", provisoire)
            tech.wait_for_selector("#connexion-mot-de-passe-panneau", state="visible")
            self.assertIn("Choisissez votre mot de passe", tech.inner_text("#connexion-titre"))
            self.assertTrue(tech.evaluate(JSON_JS, "/api/session")[1]["session"]["a_changer"])
            tech.fill("#connexion-actuel", provisoire)
            tech.fill("#connexion-nouveau", NOUVEAU_MOT_DE_PASSE_TECHNICIEN)
            tech.fill("#connexion-confirmation", NOUVEAU_MOT_DE_PASSE_TECHNICIEN)
            tech.click("#connexion-changer")
            attendre_pret(tech)
            self.assertEqual(tech.evaluate("App.profil"), {"type": "technicien", "nom": "Sophie Lambert", "technicienId": "TEC-0003"})
            self.verifier_ni_taux_horaire_ni_prix(tech)
            self.assertNotIn("Paramètres", tech.inner_text("#menu"))
            jetons_de_session = [c["value"] for c in contexte_tech.cookies() if c["name"] == "id"]
            self.ranger_l_appareil(contexte_tech)

            # Un iPhone qui ne fait pas encore confiance au PC atelier : la page de la porte le guide (CS137), jamais une
            # erreur du navigateur ; la route de l'étiquette reste dans l'adresse.
            self.autoriser_erreur(ERREUR_PING_SANS_CONFIANCE)
            contexte_iphone, iphone = self.telephone("iPhone 14")
            iphone.goto(url_etiquette)
            iphone.wait_for_function("!document.getElementById('confiance').hidden")
            self.assertIn("Faites confiance au PC atelier", iphone.inner_text("#confiance"))
            self.assertTrue(iphone.is_visible("#etapes-iphone"))
            self.assertFalse(iphone.is_visible("#etapes-android"))
            self.assertEqual(iphone.get_attribute("#etapes-iphone a.btn-telecharger", "href"), "/acces/ca.crt")
            self.assertEqual(iphone.evaluate("location.href"), url_etiquette)
            self.sans_defilement_horizontal("porte sur iPhone", iphone)
            capturer(iphone, "atelier-porte-iphone-sans-confiance")
            self.ranger_l_appareil(contexte_iphone)

            # Téléphone qui fait confiance au PC atelier, l'IA activée sur ce poste (elle ne doit pas lui servir).
            contexte_tel, tel = self.telephone("Pixel 7", ignore_https_errors=True)
            regler_ia(contexte_tel)
            requetes_tel = []
            tel.on("request", lambda r: requetes_tel.append(r.url))
            # Étiquette → porte (http) → application en https, route gardée ; pas encore enrôlé : écran de connexion.
            tel.goto(url_etiquette)
            tel.wait_for_url(atelier.url_https + "/#/equipement/" + EQUIPEMENT)
            self.attendre_etat("connexion", tel)
            self.assertTrue(tel.evaluate("window.isSecureContext"))
            self.assertEqual(tel.evaluate("location.hash"), "#/equipement/" + EQUIPEMENT)
            # Le lien d'invitation (QR montré par le responsable) → « Entrez votre nom » → demandeur sans mot de passe.
            tel.goto(lien)
            tel.wait_for_url(atelier.url_https + "/#/enroler/" + jeton_invitation)
            tel.wait_for_selector("#connexion-enrolement", state="visible")
            self.assertIn("Entrez votre nom", tel.inner_text("#connexion-enrolement"))
            tel.fill("#connexion-nom", NOM_TELEPHONE)
            tel.click("#connexion-enroler")
            attendre_pret(tel)
            self.assertEqual(tel.evaluate("location.hash"), "#/accueil")
            self.assertEqual(tel.evaluate("App.profil"), {"type": "demandeur", "nom": NOM_TELEPHONE, "technicienId": ""})
            self.assertTrue(tel.evaluate("App.session.appareil"))
            jeton_appareil = next(c["value"] for c in contexte_tel.cookies() if c["name"] == "appareil")
            # L'étiquette à nouveau : la fiche, « Signaler » avec photo, sans IA.
            tel.goto(url_etiquette)
            tel.wait_for_url(atelier.url_https + "/#/equipement/" + EQUIPEMENT)
            attendre_pret(tel)
            tel.wait_for_function("(r) => document.querySelector('#contenu h1') && document.querySelector('#contenu h1').textContent.includes(r)",
                                  arg=REPERE)
            self.assertFalse(tel.evaluate("Ia.active()"))
            self.assertTrue(tel.evaluate("JSON.parse(localStorage.getItem('prevo.ia')).actif"))   # l'IA du poste est activée
            numero = self.signaler_avec_photo(tel, "Vibrations anormales du moteur")
            capturer(tel, "atelier-telephone-confirmation")
            self.sans_defilement_horizontal("confirmation", tel)
            self.assertEqual([u for u in requetes_tel if "/api/ia" in u], [])  # ni réglages ni relais de l'IA
            self.verifier_demande_sur_le_disque(donnees, numero, NOM_TELEPHONE)
            print("  [atelier] DI %s du téléphone enrôlé, photo sur le disque" % numero)

            # Le responsable révoque l'appareil : le téléphone reçoit 401 à sa requête suivante et voit le bandeau.
            self.aller(pc, "#/equipe/acces?onglet=appareils", "#acces-inviter")   # l'onglet relit le serveur
            ligne_appareil = "#acces-liste-appareils tbody tr:has-text('%s')" % NOM_TELEPHONE
            pc.wait_for_selector(ligne_appareil)
            pc.locator(ligne_appareil + " button[data-revoquer=appareil]").click()
            self.dialogue(pc).locator("button:has-text('Révoquer')").click()
            pc.wait_for_selector(ligne_appareil + ":has-text('Révoqué')")
            refus_recus = []
            tel.on("response", lambda r: refus_recus.append(r.url) if r.status == 401 and "/api/" in r.url else None)
            tel.evaluate("document.dispatchEvent(new Event('visibilitychange'))")   # retour sur l'onglet : rafraîchissement
            # (au plus tard, le rafraîchissement périodique de 20 s fait la même requête)
            tel.wait_for_function("document.documentElement.dataset.etat === 'connexion'", timeout=30000)
            tel.wait_for_selector("#connexion-appareil-refuse", state="visible")
            self.assertTrue(refus_recus, "le téléphone a reçu un 401")
            self.assertTrue(all(u.startswith(atelier.url_https + "/api/") for u in refus_recus), refus_recus)
            self.assertIn(MESSAGE_APPAREIL_REFUSE, tel.inner_text("#connexion-appareil-refuse"))
            self.assertTrue(tel.is_visible("#connexion-formulaire"))
            capturer(tel, "atelier-telephone-revoque")
            refus = requete(atelier.url_https, "/api/csv/equipements", contexte=atelier.contexte_confiance,
                            cookie="appareil=" + jeton_appareil)
            self.assertEqual(refus.statut, 401)
            self.assertTrue(refus.json().get("appareil_refuse"))
            self.ranger_l_appareil(contexte_tel)

            # Sauvegarde manuelle depuis Paramètres, puis « Tester » : verte.
            self.aller(pc, "#/parametres", "#btn-sauvegarder")
            pc.click("#btn-sauvegarder")
            pc.wait_for_selector("#nom-sauvegarde-creee")
            nom = pc.inner_text("#nom-sauvegarde-creee").strip()
            pc.wait_for_selector('button[data-tester="%s"]' % nom)
            pc.click('button[data-tester="%s"]' % nom)
            pc.wait_for_selector("#resultat-test-sauvegarde")
            self.assertEqual(pc.get_attribute("#resultat-test-sauvegarde", "data-ok"), "1")
            self.assertIn("Sauvegarde lisible : 24 tables relues", " ".join(pc.inner_text("#resultat-test-sauvegarde").split()))
            capturer(pc, "atelier-tester-sauvegarde")
            pc.click("dialog .fenetre-actions .btn-primaire")
            pc.wait_for_selector("dialog", state="detached")
            sauvegarde = donnees / "sauvegardes" / nom
            self.assertEqual(len(list(sauvegarde.glob("*.csv"))), 24)
            for fichier in ("comptes.json", "appareils.json", "journal-acces.csv"):
                self.assertTrue((sauvegarde / "acces" / fichier).is_file(), fichier)
            self.assertTrue((donnees / "acces" / "sessions.json").is_file())      # des sessions existent…
            self.assertFalse((sauvegarde / "acces" / "sessions.json").exists())   # … jamais sauvegardées
            self.quitter(pc)

            # Journal des connexions, appareils, sessions : des événements et des empreintes, jamais un secret.
            evenements = journal_acces(donnees)
            resultats = {l["resultat"] for l in evenements}
            self.assertLessEqual({"creation", "invitation", "appareil", "connexion", "modification", "revocation"}, resultats)
            par_resultat = lambda r: [l for l in evenements if l["resultat"] == r]
            self.assertIn("sophie.lambert", [l["qui"] for l in par_resultat("creation")])
            self.assertIn("sophie.lambert", [l["qui"] for l in par_resultat("modification")])
            self.assertIn(("nicolas.briand", "127.0.0.1"), [(l["qui"], l["adresse"]) for l in par_resultat("connexion")])
            self.assertIn(("sophie.lambert", atelier.adresse_reseau), [(l["qui"], l["adresse"]) for l in par_resultat("connexion")])
            appareils = json.loads((donnees / "acces" / "appareils.json").read_text(encoding="utf-8"))
            appareil = next(a for a in appareils["appareils"] if a["nom_demandeur"] == NOM_TELEPHONE)
            self.assertEqual([l["qui"] for l in par_resultat("appareil")], ["appareil:" + appareil["id"]])
            self.assertIn("appareil:" + appareil["id"], [l["qui"] for l in par_resultat("revocation")])
            self.assertTrue(appareil["revoque"])
            invitation = next(i for i in appareils["invitations"] if i["id"] == appareil["invitation"])
            self.assertEqual(invitation["empreinte"], sha256(jeton_invitation))  # empreintes recalculées ici
            self.assertEqual(appareil["empreinte"], sha256(jeton_appareil))
            for entree in appareils["invitations"] + appareils["appareils"]:
                self.assertRegex(entree["empreinte"], r"^[0-9a-f]{64}$")
                self.assertLessEqual(set(entree), {"id", "empreinte", "cree_le", "expire_le", "revoquee", "libelle",
                                                   "nom_demandeur", "vu_le", "revoque", "invitation"})
            sessions = json.loads((donnees / "acces" / "sessions.json").read_text(encoding="utf-8"))
            jetons_de_session += [c["value"] for c in self.contexte.cookies() if c["name"] == "id"]   # technicien et PC
            self.assertEqual(len(jetons_de_session), 2)
            for jeton in jetons_de_session:
                self.assertIn(sha256(jeton), sessions)                         # seule l'empreinte est gardée
            secrets = [MOTS_DE_PASSE["nicolas.briand"], provisoire, NOUVEAU_MOT_DE_PASSE_TECHNICIEN, jeton_invitation,
                       jeton_appareil] + jetons_de_session
            fichiers = textes_du_dossier(donnees / "acces")
            fichiers.update({"sauvegarde/" + n: t for n, t in textes_du_dossier(sauvegarde / "acces").items()})
            fichiers["console"] = atelier.console()
            for nom_fichier, texte in fichiers.items():
                for secret in secrets:
                    self.assertNotIn(secret, texte, "un secret dans %s" % nom_fichier)
            print("  [atelier] journal des connexions : %s" % ", ".join(sorted(resultats)))

    def verifier_ni_taux_horaire_ni_prix(self, tech):
        """D126, CS122 : le technicien ne reçoit ni taux horaire ni prix — CSV reçus, données en mémoire, écrans."""
        for nom_table, cachee, gardee in (("techniciens", "taux_horaire", "metier"), ("articles", "prix_unitaire", "stock_securite"),
                                          ("achats", "prix_unitaire", "quantite")):
            statut, texte = tech.evaluate(TEXTE_CSV_JS, nom_table)
            entete = texte.lstrip("\ufeff").splitlines()[0].split(";")
            self.assertEqual(statut, 200)
            self.assertNotIn(cachee, entete, nom_table)
            self.assertIn(gardee, entete, nom_table)
            self.assertEqual(tech.evaluate("([t, c]) => Donnees.lignes(t).filter((l) => String(l[c] || '') !== '').length",
                                           [nom_table, cachee]), 0, nom_table)
        self.assertGreater(tech.evaluate("Donnees.lignes('articles').length"), 10)
        self.aller(tech, "#/equipe", "#contenu h1:has-text('Équipe')")
        tech.wait_for_selector("#contenu table, #contenu .carte")
        self.assertNotIn("Taux horaire", tech.inner_text("#contenu"))
        self.aller(tech, "#/equipe/TEC-0003", "#contenu h1")
        self.assertNotIn("Taux horaire", tech.inner_text("#contenu"))
        self.aller(tech, "#/magasin", "#contenu table tbody tr")
        self.assertNotIn("€", tech.inner_text("#contenu"))
        capturer(tech, "atelier-technicien-magasin")


# ---------------------------------------------------------------------------
# 3. Intranet : demandeur avec compte derrière le mandataire de l'entreprise
# ---------------------------------------------------------------------------

class TestParcoursIntranet(CasRecetteLot7):

    REGLAGES = {"mandataire": True, "noms": [NOM_INTRANET], "demandeurs_avec_compte": True}

    def test_intranet_demandeur_avec_compte_derriere_le_mandataire(self):
        self.autoriser_erreur(ERREUR_401_SONDE)
        self.autoriser_erreur(motif_refus_du_demandeur())
        self.autoriser_erreur(ERREUR_403_ENROLER)
        with ServeurPrevo(comptes=True, reglages=self.REGLAGES) as reel, \
                MandataireTest(reel.url, hote=NOM_INTRANET, protocole="https", client=ADRESSE_LEA) as poste_lea, \
                MandataireTest(reel.url, hote=NOM_INTRANET, protocole="https", client=ADRESSE_RESPONSABLE) as poste_responsable:
            # Le demandeur (Léa, compte) se connecte par le mandataire.
            page = self.page
            lectures = {}
            page.on("response", lambda r: lectures.__setitem__(r.url.rsplit("/", 1)[1].split("?")[0], r.status)
                    if "/api/csv/" in r.url and r.request.method == "GET" else None)
            page.goto(poste_lea.url + "/")
            self.attendre_etat("connexion")
            self.se_connecter(page, "lea.martin", MOTS_DE_PASSE["lea.martin"])
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.profil"), {"type": "demandeur", "nom": "Léa Martin", "technicienId": ""})
            cookie = next(c for c in self.contexte.cookies() if c["name"] == "id")
            self.assertTrue(cookie["secure"] and cookie["httpOnly"])          # https d'origine : cookie Secure
            statut, info = page.evaluate(JSON_JS, "/api/info")
            self.assertEqual((statut, info["adresse_locale"], info["adresses_reseau"], info["porte"]),
                             (200, "https://%s/" % NOM_INTRANET, ["https://%s/" % NOM_INTRANET], False))
            self.assertEqual(page.evaluate("App.adressesReseau()"), ["https://%s/" % NOM_INTRANET])
            # Ses tables seulement : 200 pour les siennes, 403 pour les autres, rien d'autre en mémoire.
            lues = {t for t, s in lectures.items() if s == 200}
            refusees = {t for t, s in lectures.items() if s == 403}
            self.assertEqual(lues, TABLES_DU_DEMANDEUR)
            self.assertEqual(refusees, set(lectures) - TABLES_DU_DEMANDEUR)
            self.assertEqual(lues | refusees, set(lectures))
            self.assertIn("techniciens", refusees)
            self.assertIn("ordres_travail", refusees)
            for nom_table in ("techniciens", "ordres_travail", "articles", "ot_temps"):
                self.assertEqual(page.evaluate("(t) => Donnees.lignes(t).length", nom_table), 0, nom_table)
            statut, versions = page.evaluate(JSON_JS, "/api/versions")
            self.assertEqual(statut, 200)
            noms_versions = set(versions["tables"])
            self.assertIn("demandes", noms_versions)
            self.assertLessEqual(noms_versions, TABLES_DU_DEMANDEUR)
            # Elle signale une demande depuis la fiche (sans IA : demandeur).
            self.aller(page, "#/equipement/" + EQUIPEMENT, "a.parc-signaler")
            numero = self.signaler_avec_photo(page, "Fuite d'eau sous la pompe", photo=False)
            self.verifier_demande_sur_le_disque(reel.dossier, numero, "Léa Martin", photo=False)
            capturer(page, "intranet-demandeur-confirmation")
            self.quitter(page)
            print("\n  [intranet] DI %s de Léa Martin par %s" % (numero, NOM_INTRANET))

            # Enrôlement d'un appareil : refusé (403), l'écran le dit et propose la connexion classique.
            _, visiteur = self.nouvelle_page(viewport={"width": 1280, "height": 800})
            visiteur.goto(poste_lea.url + "/#/enroler/" + "x" * 43)
            self.attendre_etat("connexion", visiteur)
            visiteur.wait_for_selector("#connexion-enrolement", state="visible")
            visiteur.fill("#connexion-nom", "Karim Benali")
            visiteur.click("#connexion-enroler")
            visiteur.wait_for_selector("#connexion-formulaire", state="visible")
            self.assertIn("désactivé", visiteur.inner_text("#connexion-erreur"))
            self.quitter(visiteur)
            refus = requete(poste_lea.url, "/api/enroler", "POST", {"invitation": "y" * 43, "nom": "Karim Benali"}, {"X-Prevo": "1"})
            self.assertEqual(refus.statut, 403, refus.octets)
            self.assertFalse((reel.dossier / "acces" / "appareils.json").exists()
                             and json.loads((reel.dossier / "acces" / "appareils.json").read_text(encoding="utf-8"))["appareils"])

            # Le responsable (autre poste) voit l'adresse d'origine de Léa dans le journal des connexions.
            _, responsable = self.nouvelle_page(viewport={"width": 1280, "height": 800})
            responsable.goto(poste_responsable.url + "/#/equipe/acces?onglet=journal")
            self.attendre_etat("connexion", responsable)
            self.se_connecter(responsable, "nicolas.briand", MOTS_DE_PASSE["nicolas.briand"])
            attendre_pret(responsable)
            ligne_lea = "#acces-journal tbody tr:has-text('lea.martin'):has-text('%s')" % ADRESSE_LEA
            responsable.wait_for_selector(ligne_lea)
            self.assertIn("Connexion", responsable.inner_text(ligne_lea))
            capturer(responsable, "intranet-journal")
            responsable.click(".barre-onglets [role=tab]:has-text('Appareils')")
            responsable.wait_for_selector("#acces-inviter")
            self.assertIn("Enrôlement désactivé", responsable.inner_text("#acces-contenu"))
            self.assertTrue(responsable.is_disabled("#acces-creer-invitation"))
            self.quitter(responsable)
            connexions = [(l["qui"], l["adresse"], l["tailscale"]) for l in journal_acces(reel.dossier) if l["resultat"] == "connexion"]
            self.assertIn(("lea.martin", ADRESSE_LEA, ""), connexions)
            self.assertIn(("nicolas.briand", ADRESSE_RESPONSABLE, ""), connexions)

            # Un client direct qui forge X-Forwarded-* n'obtient rien.
            forges = {"X-Forwarded-Proto": "https", "X-Forwarded-For": "203.0.113.9"}
            reseau = adresse_reseau()
            if reseau:                                    # vu du réseau : Prévo n'écoute que sur 127.0.0.1
                with self.assertRaises(OSError):
                    socket.create_connection((reseau, reel.port), timeout=3).close()
            for chemin in ("/api/ping", "/api/csv/demandes", "/"):
                with self.subTest(chemin=chemin):
                    etranger = requete(reel.url, chemin, entetes=dict(forges, **{"X-Forwarded-Host": "pirate.example"}))
                    self.assertEqual(etranger.statut, 403)
                    self.assertEqual(etranger.json(), {"erreur": serveur.MESSAGE_HOTE_ORIGINE_REFUSE})
            sans_session = requete(reel.url, "/api/csv/demandes", entetes=dict(forges, **{"X-Forwarded-Host": NOM_INTRANET}))
            self.assertEqual(sans_session.statut, 401)
            self.assertNotIn(numero.encode("utf-8"), sans_session.octets)
            self.assertEqual([l for l in journal_acces(reel.dossier) if l["adresse"] == "203.0.113.9"], [])


# ---------------------------------------------------------------------------
# 4. Hors de l'atelier : Tailscale simulé, mandataire, copie externe, déconnexion
# ---------------------------------------------------------------------------

class TestParcoursTailscale(CasRecetteAssistant):

    def environnement_tailscale(self, etat):
        return {"PREVO_TAILSCALE": str(FAUX_TAILSCALE), "FAUX_TAILSCALE_DOSSIER": str(self.faux),
                "FAUX_TAILSCALE_ETAT": etat, "FAUX_TAILSCALE_NOM": NOM_TAILSCALE + ".", "FAUX_TAILSCALE_EXPIRATION": ""}

    def lancements(self):
        journal = self.faux / "lancements.txt"
        return journal.read_text(encoding="utf-8").splitlines() if journal.is_file() else []

    def test_aussi_hors_de_l_atelier_tailscale_mandataire_copie_externe_puis_deconnecte(self):
        page = self.page
        self.autoriser_erreur(ERREUR_401_SONDE)
        self.faux_tailscale()
        copie = self.dossier / "Cle USB" / "Sauvegardes Prevo"
        copie.mkdir(parents=True)
        instance = self.lancer()
        self.ouvrir_assistant(instance)
        self.choisir_moi_seul()
        self.assertIn("Aussi hors de l'atelier", page.inner_text('#installation-contenu label:has(input[name="portee"][value="dehors"])'))
        self.cocher("portee", "dehors")
        self.continuer()
        self.attendre_etape("compte")
        page.fill("#inst-prenom", "Nicolas")
        page.fill("#inst-nom", "Briand")
        page.fill("#inst-mot-de-passe", MOT_DE_PASSE_ASSISTANT)
        page.fill("#inst-confirmation", MOT_DE_PASSE_ASSISTANT)
        self.continuer()
        self.attendre_etape("certificat")
        self.assertTrue(page.is_checked('#installation-contenu input[name="mode"][value="reseau_prive"]'))
        self.continuer()
        self.attendre_etape("tailscale")
        self.assertIn("installé et connecté", page.inner_text("#inst-tailscale-etat"))
        page.click("#inst-tailscale-appliquer")
        page.wait_for_selector("#inst-tailscale-resultat", state="visible")
        self.assertIn("https://%s/" % NOM_TAILSCALE, page.inner_text("#inst-tailscale-resultat"))
        page.click("#inst-tailscale-continuer")
        self.attendre_etape("demarrage")
        self.cocher("demarrage", "systeme")
        page.check("#inst-veille")
        self.continuer()
        self.attendre_etape("sauvegardes")
        self.assertEqual(self.enregistreur.eleves, [(str(self.dossier / "Installer_demarrage.ps1"), True)])   # notée
        page.fill("#inst-copie_sauvegardes", str(copie))
        self.continuer()
        self.attendre_etape("recapitulatif")
        fichier = self.terminer_avec_la_demo()
        self.comparer_cle_a_cle(fichier, dict(ATTENDU_SOLO_DEHORS, copie_sauvegardes=str(copie)))
        # « serve » lancée et vérifiée par le faux tailscale, vers la porte du PC ; jamais up, login, install.
        lancements = self.lancements()
        self.assertIn("serve --bg --https=443 http://127.0.0.1:8080", lancements)
        self.assertLess(lancements.index("serve --bg --https=443 http://127.0.0.1:8080"),
                        len(lancements) - 1 - lancements[::-1].index("serve status --json"))
        self.assertEqual([l for l in lancements if l.split()[0] in COMMANDES_TAILSCALE_INTERDITES], [])
        serve = json.loads((self.faux / "serve.json").read_text(encoding="utf-8"))
        self.assertEqual(serve["Web"][NOM_TAILSCALE + ":443"]["Handlers"]["/"]["Proxy"], "http://127.0.0.1:8080")
        donnees = self.dossier / "donnees"
        comptes = json.loads((donnees / "acces" / "comptes.json").read_text(encoding="utf-8"))
        self.assertEqual([(c["identifiant"], c["role"], c["technicien_id"]) for c in comptes["comptes"]],
                         [("nicolas.briand", "responsable", "TEC-0005")])
        self.assertEqual(parametres(donnees)["solo_technicien_id"], "TEC-0005")

        # Relance simulée (Tailscale connecté) : la copie externe est faite au démarrage.
        self.arreter_l_assistant(instance)
        reel = serveur_relance(fichier, donnees, self.environnement_tailscale("Running"))
        self.addCleanup(reel.arreter)
        attendre_que(lambda: (donnees / "copie-externe.json").is_file(), message=reel.sortie_console())
        jours = {(datetime.date.today() - datetime.timedelta(days=n)).isoformat() for n in (0, 1)}   # à toute heure
        etat_copie = json.loads((donnees / "copie-externe.json").read_text(encoding="utf-8"))
        self.assertIn(etat_copie["derniere_reussie"], jours)
        self.assertIsNone(etat_copie["erreur"])
        # La sauvegarde quotidienne faite par « Terminer » (avant d'écrire la démo), copiée telle quelle.
        self.assertIn(etat_copie["sauvegarde_copiee"], jours)
        self.assertTrue((donnees / "sauvegardes" / etat_copie["sauvegarde_copiee"]).is_dir())
        self.assertEqual([p.name for p in copie.iterdir()], [etat_copie["sauvegarde_copiee"]])   # aucun dossier temporaire
        copiee = copie / etat_copie["sauvegarde_copiee"]
        self.assertTrue((copiee / "acces" / "comptes.json").is_file())
        self.assertIn("nicolas.briand", (copiee / "acces" / "comptes.json").read_text(encoding="utf-8"))
        self.assertEqual([p for p in copie.rglob("sessions.json")], [])
        console = reel.sortie_console()
        self.assertIn("Tailscale        : %s, connecté" % NOM_TAILSCALE, console)
        self.assertIn("Copie externe des sauvegardes : sauvegarde du %s à jour" % etat_copie["sauvegarde_copiee"], console)

        # « tailscale serve » joué par MandataireTest : connexion par l'écran, cookie Secure, adresses en https.
        with MandataireTest(reel.url, hote=NOM_TAILSCALE, protocole="https", client=ADRESSE_TAILNET,
                            tailscale=UTILISATEUR_TAILSCALE) as tailnet:
            page.goto(tailnet.url + "/#/accueil")
            self.attendre_etat("connexion")
            self.se_connecter(page, "nicolas.briand", MOT_DE_PASSE_ASSISTANT)
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.profil"), {"type": "responsable", "nom": "Nicolas Briand", "technicienId": "TEC-0005"})
            self.assertTrue(page.evaluate("App.modeSolo()"))
            cookie = next(c for c in self.contexte.cookies() if c["name"] == "id")
            self.assertTrue(cookie["secure"] and cookie["httpOnly"])
            self.assertEqual(page.evaluate("App.adressesReseau()"), ["https://%s/" % NOM_TAILSCALE])
            page.wait_for_selector("#tailscale-zone[data-lu='1']", state="attached")
            self.assertEqual(page.locator("#alerte-tailscale").count(), 0)          # connecté : rien à signaler
            page.wait_for_selector("#copie-externe-zone[data-lu='1']", state="attached")
            self.assertEqual(page.locator("#alerte-copie-externe").count(), 0)      # copie à jour
            self.quitter(page)
        derniere = [l for l in journal_acces(donnees) if l["resultat"] == "connexion"][-1]
        self.assertEqual((derniere["qui"], derniere["adresse"], derniere["tailscale"]),
                         ("nicolas.briand", ADRESSE_TAILNET, UTILISATEUR_TAILSCALE))
        reel.arreter()

        # Tailscale déconnecté (le faux passe « Stopped ») : nouvelle relance ; le responsable, sur le PC serveur, garde
        # sa session ; l'accueil le signale ; Paramètres › Accès et installation montre l'état du serveur.
        reel = serveur_relance(fichier, donnees, self.environnement_tailscale("Stopped"))
        self.addCleanup(reel.arreter)
        self.assertIn("Tailscale        : %s, déconnecté" % NOM_TAILSCALE, reel.sortie_console())
        page.goto(reel.url + "/#/accueil")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.session.identifiant"), "nicolas.briand")
        page.wait_for_selector("#alerte-tailscale")
        self.assertIn(MESSAGE_DECONNECTE, " ".join(page.inner_text("#alerte-tailscale").split()))
        self.assertIn("attention", page.get_attribute("#alerte-tailscale", "class"))
        capturer(page, "tailscale-deconnecte-accueil")
        self.aller(page, "#/parametres", "#carte-acces #acces-contenu[data-lu]")
        self.assertIn("Terminée", page.inner_text("#acces-installation"))
        self.assertIn("Aussi hors de l'atelier", page.inner_text("#acces-portee"))
        self.assertIn("Installé mais pas connecté", page.inner_text("#acces-tailscale"))
        reussie = datetime.date.fromisoformat(etat_copie["derniere_reussie"]).strftime("%d/%m/%Y")
        self.assertIn("%s — Dernière copie réussie le %s" % (copie, reussie), page.inner_text("#acces-copie"))
        self.assertIn("https://%s/" % NOM_TAILSCALE, page.inner_text("#acces-adresses"))
        capturer(page, "tailscale-parametres")
        self.quitter(page)
        self.assertEqual([l for l in self.lancements() if l.split()[0] in COMMANDES_TAILSCALE_INTERDITES], [])


# ---------------------------------------------------------------------------
# Défauts trouvés par la recette (expectedFailure : l'orchestrateur corrige)
# ---------------------------------------------------------------------------

class TestEtiquetteCePc(unittest.TestCase):

    @unittest.expectedFailure
    def test_etiquette_solo_ce_pc_mene_a_une_adresse_qui_repond(self):
        """DÉFAUT (parcours Solo, D132 « étiquette QR → fiche machine », CS120, CS125) : en portée « ce PC » (écoute sur
        127.0.0.1 seulement, la portée de Solo par défaut), GET /api/info rend encore dans « adresses_reseau » les
        adresses réseau du PC (http://<IP du PC>:<port>/, Configuration.adresses_reseau, quelle que soit l'écoute) ; les
        QR des étiquettes (App.urlFicheEquipement), la carte « Connecter un téléphone » de l'accueil les reprennent et la
        console les affiche « Sur le réseau : … (téléphones, tablettes) » juste avant « Écoute : ce PC seulement ».
        Prévo n'y écoute pas : le QR d'une étiquette imprimée en Solo « ce PC » ne mène nulle part (connexion refusée,
        même depuis le PC). Attendu : n'annoncer une adresse que là où Prévo répond (comme GET installation/fiche, qui ne
        donne les adresses réseau « que quand Prévo écoute sur le réseau »), ou dire sur l'écran des étiquettes que le
        QR ne servira qu'une fois Prévo ouvert au Wi-Fi de l'atelier. À trancher avec CS119 : test_etiquettes (lot 3)
        attend aujourd'hui l'URL réseau dans le QR avec ServeurPrevo() (portée « ce PC »)."""
        reseau = adresse_reseau()
        if reseau is None:
            self.skipTest("ce PC n'a pas d'adresse réseau : rien d'annoncé, rien à montrer")
        with ServeurPrevo() as reel:                          # portée « ce PC », comme Solo après l'assistant
            info = requete(reel.url, "/api/info").json()
            injoignables = []
            for adresse in info["adresses_reseau"]:
                hote, port = adresse.split("//", 1)[1].rstrip("/").rsplit(":", 1)
                try:
                    socket.create_connection((hote, int(port)), timeout=3).close()
                except OSError as erreur:
                    injoignables.append("%s (%s)" % (adresse, erreur.__class__.__name__))
            self.assertEqual(injoignables, [], "adresses annoncées où Prévo n'écoute pas")


class TestConnexionsInactives(unittest.TestCase):

    @unittest.expectedFailure
    def test_des_connexions_keep_alive_inactives_ne_bloquent_pas_une_nouvelle_requete(self):
        """DÉFAUT (audit F2, §22.12 ; révélé par le parcours Atelier : avec quatre navigateurs ouverts, une requête de plus
        est restée plus de 15 s sans réponse) : SEMAPHORE_CONNEXIONS (32 places) est pris dans
        ServeurPrevo.process_request_thread pour toute la vie d'une connexion HTTP/1.1, y compris quand elle attend,
        inactive, la requête suivante (keep-alive, coupée après 60 s de silence : GestionnaireRequetes.timeout). Le
        commentaire de CONNEXIONS_MAX parle de « requêtes servies en même temps » ; le code compte les connexions
        ouvertes. Un navigateur qui charge Prévo en ouvre jusqu'à six par adresse (la porte et l'application) : mesuré
        sur ce PC (portée « ce PC », Chromium), cinq navigateurs venus de charger Prévo, et le sixième n'ouvre pas la page
        en 30 s ; toute nouvelle requête attend jusqu'à 60 s alors qu'aucune n'est servie.
        Ici : 32 connexions ouvertes et inactives (une requête servie chacune), la 33e requête n'a pas de réponse en 5 s.
        Pistes : ne tenir la place que pendant le traitement d'une requête (handle_one_request), ou un délai
        d'inactivité court pour le keep-alive ; CS134 (« 33e connexion en attente ») reste vrai pour 33 requêtes en cours."""
        with ServeurPrevo() as reel:
            prises = []
            try:
                for _ in range(serveur.CONNEXIONS_MAX):
                    prise = socket.create_connection(("127.0.0.1", reel.port), timeout=10)
                    prises.append(prise)
                    prise.sendall(("GET /api/ping HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nConnection: keep-alive\r\n\r\n"
                                   % reel.port).encode("ascii"))
                    self.assertTrue(prise.recv(65536).startswith(b"HTTP/1.1 200"))   # servie, puis inactive
                debut = time.monotonic()
                connexion = http.client.HTTPConnection("127.0.0.1", reel.port, timeout=5)
                try:
                    connexion.request("GET", "/api/ping")
                    statut = connexion.getresponse().status
                except OSError as erreur:
                    self.fail("33e requête sans réponse au bout de %.1f s (%s) : 32 connexions inactives tiennent "
                              "toutes les places" % (time.monotonic() - debut, erreur.__class__.__name__))
                finally:
                    connexion.close()
                self.assertEqual(statut, 200)
            finally:
                for prise in prises:
                    prise.close()


if __name__ == "__main__":
    unittest.main()
