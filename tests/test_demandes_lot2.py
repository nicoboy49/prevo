"""Tests du lot 2 du module Demandes d'intervention (tâche T29 ; ARCHITECTURE.md §14.5 et §14.6).

Couvre, en mode serveur sur une copie du jeu de démo (identifiants lus dans scenarios_demo()) :
    - symptome : la suggestion « Fuite » donne le code symptôme, écrit dans demandes.csv ; texte
      retouché → plus de code ; casse et espaces ignorés ; texte libre → code vide ; acceptation →
      OT avec le même code (y compris un OT déjà créé pour la DI, dont le code était vide) ;
    - encart : causes fréquentes sur la fiche d'une DI (≥ 5 cas : « n cas sur N », liens vers des OT
      existants) vues par le demandeur, le technicien et le responsable (le demandeur, sans accès
      aux OT, voit les mêmes identifiants en texte simple, sans aucun lien #/ot) ; sous 5 cas :
      seulement « Pas encore assez de cas pour ce symptôme (n sur 5) » ; DI sans code : pas d'encart ;
    - anomalie : #/di/nouvelle?equipement=…&ot=<préventif ouvert> → bandeau, DI liée
      (ot_origine_id), OT d'origine « anomalie constatée » = 1 sur le disque (idempotent), lien sur
      la fiche, mention dans la liste ; seconde écriture en échec → DI créée et avertissement ;
    - verrou : OT préventif d'origine verrouillé (RG3 : Clôturé administrativement, Annulé) → la DI
      garde son lien, l'OT n'est jamais modifié (octets de sa ligne, journal), bandeau et
      confirmation le disent ; OT annulé sur un autre poste après l'ouverture du formulaire → pas
      marqué non plus (contrôle sur la ligne fraîche, après le conflit d'écriture) ;
    - suivi : bloc « Suivi » d'une DI acceptée : l'OT est un lien pour le technicien et le
      responsable, son identifiant en texte simple pour le demandeur (aucun lien #/ot) ;
    - téléphone 375 px sans défilement horizontal.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_demandes_lot2.py" -v
"""
import collections
import csv
import io
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

# Identifiants des objets de scénario du jeu de démo (outils/generer_demo.py, ARCHITECTURE.md §14.8).
SCENARIOS = scenarios_demo()
EQ_CAUSES = SCENARIOS["causes_equipement"]                       # PO-02 : fuites, ≥ 5 cas sur l'équipement
SYMPTOME_CAUSES = SCENARIOS["causes_equipement_symptome"]
EQ_INSUFFISANT = SCENARIOS["causes_insuffisantes"]               # PO-03 : moins de 5 cas
SYMPTOME_INSUFFISANT = SCENARIOS["causes_insuffisantes_symptome"]
DI_CAUSES = SCENARIOS["di_causes_equipement"]
DI_INSUFFISANTE = SCENARIOS["di_causes_insuffisantes"]
DI_SANS_CODE = SCENARIOS["di_sans_symptome_code"]
OT_PREVENTIF_OUVERT = SCENARIOS["ot_preventif_ouvert"]
OT_PREVENTIF_VERROUILLE = SCENARIOS["ot_preventif_cloture"]      # préventif « Clôturé administrativement »
DI_ACCEPTEE = SCENARIOS["di_statut_acceptee"]                   # DI « Acceptée », avec son OT
OT_DE_DI_ACCEPTEE = SCENARIOS["ot_de_di_acceptee"]

STATUTS_CLOTURES = ("Clôturé techniquement", "Clôturé administrativement")
STATUTS_VERROUILLES = ("Clôturé administrativement", "Annulé")    # RG3 : OT jamais modifié
# Identifiant d'OT (ARCHITECTURE.md §4 : OT-AAAA-NNNN), pour le relever dans un texte.
MOTIF_ID_OT = re.compile(r"OT-\d{4}-\d{4,}")

# Zones tactiles de #contenu de moins de 48 px de haut (même règle que tests/test_recette_lot1.py :
# case à cocher ou bouton radio : son libellé compte).
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
MINIMUM = 5
TECHNICIEN = "TEC-0001"


# ---------------------------------------------------------------------------
# Outils : CSV du serveur de test, règle des causes fréquentes recalculée en Python
# ---------------------------------------------------------------------------

def lire_csv(chemin):
    """Lignes d'un CSV de Prévo (BOM, `;`) en dictionnaires ; apostrophe de protection retirée."""
    texte = Path(chemin).read_text(encoding="utf-8-sig")
    return [{cle: (valeur[1:] if valeur.startswith("'") else valeur) for cle, valeur in ligne.items()}
            for ligne in csv.DictReader(io.StringIO(texte), delimiter=";")]


def ligne_par_id(chemin, identifiant):
    return next((ligne for ligne in lire_csv(chemin) if ligne["id"] == identifiant), None)


def code_symptome(dossier, libelle):
    """Code de la famille « symptôme » dont le libellé est `libelle` (lu dans codes_defaillance.csv)."""
    for ligne in lire_csv(dossier / "codes_defaillance.csv"):
        if ligne["famille"] == "symptôme" and ligne["libelle"] == libelle:
            return ligne["code"]
    raise AssertionError("aucun code symptôme « %s » dans le jeu de démo" % libelle)


def cas_causes(dossier, equipement_id, symptome):
    """(portée, cas) selon la règle D25 (ARCHITECTURE.md §14.5), recalculée depuis les CSV :
    OT correctifs clôturés de ce symptôme avec une cause ; cet équipement s'il a au moins 5 cas,
    sinon les équipements de même marque et modèle (casse et espaces ignorés)."""
    def cle(valeur):
        return re.sub(r"\s+", "", valeur or "").lower()

    cas = [ot for ot in lire_csv(dossier / "ordres_travail.csv")
           if ot["type"].startswith("correctif") and ot["statut"] in STATUTS_CLOTURES
           and ot["symptome_code"] == symptome and ot["cause_code"].strip()]
    propres = [ot for ot in cas if ot["equipement_id"] == equipement_id]
    if len(propres) >= MINIMUM:
        return "equipement", propres
    equipements = lire_csv(dossier / "equipements.csv")
    equipement = next(e for e in equipements if e["id"] == equipement_id)
    if not equipement["marque"].strip() or not equipement["modele"].strip():
        return None, propres
    memes = {e["id"] for e in equipements
             if cle(e["marque"]) == cle(equipement["marque"]) and cle(e["modele"]) == cle(equipement["modele"])}
    du_modele = [ot for ot in cas if ot["equipement_id"] in memes]
    return ("modele" if len(du_modele) >= MINIMUM else None), du_modele


def lignes_journal(dossier, morceau, identifiant):
    texte = (dossier / "journal.csv").read_text(encoding="utf-8-sig")
    return [ligne for ligne in texte.splitlines() if identifiant in ligne and morceau in ligne]


def journal_de_la_ligne(dossier, table, identifiant):
    """Entrées du journal qui portent sur une ligne d'une table (colonnes table et id_ligne)."""
    return [ligne for ligne in lire_csv(dossier / "journal.csv")
            if ligne["table"] == table and ligne["id_ligne"] == identifiant]


def octets_de_la_ligne(chemin, identifiant):
    """Octets exacts de la ligne d'un CSV dont le premier champ est `identifiant` (apostrophe ou
    guillemets de protection ignorés)."""
    for ligne in Path(chemin).read_bytes().split(b"\n"):
        premier = ligne.split(b";", 1)[0].lstrip(b"\xef\xbb\xbf").strip(b"'\"")
        if premier.decode("utf-8", "replace") == identifiant:
            return ligne
    raise AssertionError("aucune ligne %s dans %s" % (identifiant, chemin))


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class CasDemandesLot2(CasNavigateur):

    def ouvrir(self, serveur, route):
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        # Les écritures du démarrage (OT préventifs échus d'un technicien ou d'un responsable) sont
        # finies avant d'agir.
        self.page.wait_for_load_state("networkidle")

    def changer_profil(self, type_profil, nom="", technicien_id=""):
        self.page.evaluate("([t, n, tec]) => localStorage.setItem('prevo.profil', JSON.stringify({type: t, nom: n, technicienId: tec}))",
                           [type_profil, nom, technicien_id])
        self.page.reload()
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    def aller(self, route, selecteur):
        """Change de route dans la page (sans rechargement) et attend un élément de l'écran."""
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(selecteur)

    def ouvrir_fiche(self, di):
        """Fiche d'une DI, attendue sur son propre numéro (pas sur la fiche affichée avant)."""
        self.page.evaluate("(route) => { location.hash = route; }", "#/di/" + di)
        self.page.wait_for_function("""(id) => { const b = document.querySelector('.di-entete-badges b');
            return b !== null && b.textContent === id; }""", arg=di)

    def attendre_toast(self, texte):
        self.page.wait_for_function("(t) => document.getElementById('toast').textContent.includes(t)", arg=texte)

    def envoyer(self):
        """Envoie le formulaire « Signaler » et rend le numéro de la DI créée."""
        self.page.click(".di-envoyer")
        self.page.wait_for_selector(".di-numero")
        return self.page.inner_text(".di-numero")

    def puces_appuyees(self):
        return self.page.eval_on_selector_all(".di-puce[aria-pressed='true']", "(puces) => puces.map((p) => p.dataset.symptome)")

    def sans_defilement_horizontal(self):
        largeurs = self.page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal : %r" % (largeurs,))

    def erreur_de(self, expression, argument=None):
        """Évalue une expression JavaScript (promesse) qui doit échouer → « NomDeLErreur : message ».
        L'expression peut utiliser la variable `argument`."""
        return self.page.evaluate("""async (argument) => {
            try { await %s; return 'aucune erreur'; }
            catch (e) { return e.constructor.name + ' : ' + e.message; } }""" % expression, argument)


# ---------------------------------------------------------------------------
# symptome : code symptôme à la saisie et à l'acceptation
# ---------------------------------------------------------------------------

class TestSymptome(CasDemandesLot2):

    def test_symptome_suggestion_texte_libre_et_acceptation(self):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurPrevo() as serveur:
            demandes_csv = serveur.dossier / "demandes.csv"
            ordres_csv = serveur.dossier / "ordres_travail.csv"
            code_fuite = code_symptome(serveur.dossier, "Fuite")
            self.ouvrir(serveur, "#/di/nouvelle?equipement=" + EQ_CAUSES)
            puce = ".di-puce[data-symptome='Fuite']"

            # Choisir la suggestion : le code est retenu (puce marquée)
            page.click(puce)
            self.assertEqual(page.input_value("input[name=symptome]"), "Fuite")
            self.assertEqual(self.puces_appuyees(), ["Fuite"])
            self.assertEqual(page.evaluate("Demandes.codeSymptome(document.querySelector('input[name=symptome]').value)"), code_fuite)
            # Retoucher le texte : il ne correspond plus à un libellé, le code s'efface
            page.fill("input[name=symptome]", "Fuite d'huile au joint")
            self.assertEqual(self.puces_appuyees(), [])
            # Correspondance exacte, casse et espaces ignorés
            page.fill("input[name=symptome]", "  fU ITE ")
            self.assertEqual(self.puces_appuyees(), ["Fuite"])
            self.assertEqual(page.evaluate("Demandes.codeSymptome('Fuite d\\'eau')"), "")

            # DI créée avec la suggestion « Fuite » : code écrit sur le disque
            page.click(puce)
            page.click("label.tuile:has(input[value='dégradé'])")
            di_code = self.envoyer()
            ligne = ligne_par_id(demandes_csv, di_code)
            self.assertEqual((ligne["symptome"], ligne["symptome_code"], ligne["ot_origine_id"]), ("Fuite", code_fuite, ""))

            # Texte libre : code vide
            page.click(".di-autre")
            page.wait_for_selector(".di-formulaire")
            page.fill(".selecteur-recherche input[type=search]", "PO-02")
            page.click(".selecteur-option[data-id='%s']" % EQ_CAUSES)
            page.fill("input[name=symptome]", "Fuite d'eau sous la pompe")
            self.assertEqual(self.puces_appuyees(), [])
            page.click("label.tuile:has(input[value='gêne'])")
            di_libre = self.envoyer()
            ligne = ligne_par_id(demandes_csv, di_libre)
            self.assertEqual((ligne["symptome"], ligne["symptome_code"]), ("Fuite d'eau sous la pompe", ""))

            # Acceptation par l'interface : l'OT créé porte le même code symptôme
            self.ouvrir_fiche(di_code)
            page.click("[data-decision=accepter]")
            page.wait_for_selector("dialog .di-fenetre-accepter")
            page.click("dialog button:has-text(\"Créer l'ordre de travail\")")
            page.wait_for_function("location.hash.startsWith('#/ot/')")
            ot_id = page.evaluate("decodeURIComponent(location.hash.slice(5))")
            ot = ligne_par_id(ordres_csv, ot_id)
            self.assertEqual((ot["di_id"], ot["symptome_code"]), (di_code, code_fuite))
            # Texte libre accepté : OT sans code
            ot_libre = page.evaluate("(di) => Demandes.accepter(di)", di_libre)
            self.assertEqual(ligne_par_id(ordres_csv, ot_libre)["symptome_code"], "")

            # OT déjà créé pour la DI (essai interrompu), sans code : réutilisé et complété
            di_api = page.evaluate("""(code) => Demandes.creer({ equipement_id: %r, symptome: 'Fuite',
                symptome_code: code, impact: 'gêne', demandeur: 'Lucie Martin' })""" % EQ_CAUSES, code_fuite)
            ot_existant = page.evaluate("""([di, equipement]) => Donnees.modifier('ordres_travail', (lignes, outils) => {
                const id = outils.nouvelId(lignes, outils.maintenant());
                lignes.push({ id, origine: 'DI', di_id: di, equipement_id: equipement, type: 'correctif différé',
                  priorite: 'P3', statut: 'Créé', titre: 'Fuite', date_creation: outils.maintenant() });
                return id; })""", [di_api, EQ_CAUSES])
            self.assertEqual(ligne_par_id(ordres_csv, ot_existant)["symptome_code"], "")
            self.assertEqual(page.evaluate("(di) => Demandes.accepter(di)", di_api), ot_existant)
            self.assertEqual(ligne_par_id(ordres_csv, ot_existant)["symptome_code"], code_fuite)
            self.assertEqual(len([o for o in lire_csv(ordres_csv) if o["di_id"] == di_api]), 1)

            # API : un code symptôme inconnu est refusé, rien n'est écrit
            nombre = len(lire_csv(demandes_csv))
            message = self.erreur_de("Demandes.creer({ equipement_id: argument, symptome: 'Fuite', impact: 'gêne', symptome_code: 'ZZ9' })", EQ_CAUSES)
            self.assertIn("ErreurValidation", message)
            self.assertIn("ZZ9", message)
            self.assertEqual(len(lire_csv(demandes_csv)), nombre)


# ---------------------------------------------------------------------------
# encart : causes fréquentes sur la fiche DI, pour les trois profils
# ---------------------------------------------------------------------------

class TestEncart(CasDemandesLot2):

    def lire_encart(self):
        return self.page.evaluate("""() => {
            const encart = document.querySelector('.di-details .causes-frequentes');
            if (!encart) return null;
            return {
              titre: encart.querySelector('h3') ? encart.querySelector('h3').textContent : null,
              texte: encart.textContent.replace(/\\s+/g, ' ').trim(),
              lignes: Array.from(encart.querySelectorAll('li')).map((li) => ({
                texte: li.textContent,
                ot: Array.from(li.querySelectorAll('a[href^="#/ot/"]')).map((a) => a.getAttribute('href').slice(5)),
              })),
              // Tout lien vers les écrans des OT (fiche #/ot/… ou liste #/ot?…, « et n autres »)
              liens_ot: Array.from(encart.querySelectorAll('a[href^="#/ot"]')).map((a) => a.getAttribute('href')),
              mention: encart.querySelector('.note') ? encart.querySelector('.note').textContent : null,
            };
        }""")

    def test_encart_vu_par_le_demandeur_le_technicien_et_le_responsable(self):
        preregler_profil(self.contexte, "demandeur", "Lucie Martin")
        with ServeurPrevo() as serveur:
            # Attendus recalculés depuis les CSV
            self.assertEqual(ligne_par_id(serveur.dossier / "demandes.csv", DI_CAUSES)["symptome_code"], SYMPTOME_CAUSES)
            self.assertEqual(ligne_par_id(serveur.dossier / "demandes.csv", DI_INSUFFISANTE)["symptome_code"], SYMPTOME_INSUFFISANT)
            self.assertEqual(ligne_par_id(serveur.dossier / "demandes.csv", DI_SANS_CODE)["symptome_code"], "")
            portee, cas = cas_causes(serveur.dossier, EQ_CAUSES, SYMPTOME_CAUSES)
            self.assertEqual(portee, "equipement")
            par_cause = collections.Counter(ot["cause_code"] for ot in cas).most_common()
            portee_insuffisante, cas_insuffisants = cas_causes(serveur.dossier, EQ_INSUFFISANT, SYMPTOME_INSUFFISANT)
            self.assertIsNone(portee_insuffisante)
            self.assertLess(len(cas_insuffisants), MINIMUM)
            ot_existants = {ot["id"] for ot in lire_csv(serveur.dossier / "ordres_travail.csv")}
            ot_des_cas = {ot["id"] for ot in cas}
            cause_de_l_ot = {ot["id"]: ot["cause_code"] for ot in cas}
            cas_par_cause = collections.Counter(cause_de_l_ot.values())

            self.ouvrir(serveur, "#/accueil")
            for type_profil, nom, technicien in (("demandeur", "Lucie Martin", ""), ("technicien", "", TECHNICIEN),
                                                 ("responsable", "", "")):
                with self.subTest(profil=type_profil):
                    if type_profil != "demandeur":
                        self.changer_profil(type_profil, nom, technicien)
                    self.assertEqual(self.page.evaluate("App.profil.type"), type_profil)

                    # ≥ 5 cas : titre, « n cas sur N », liens vers des OT existants, mention
                    self.ouvrir_fiche(DI_CAUSES)
                    encart = self.lire_encart()
                    self.assertIsNotNone(encart)
                    self.assertEqual(encart["titre"], "Causes fréquentes ici — %d cas" % len(cas))
                    self.assertEqual(len(encart["lignes"]), min(3, len(par_cause)))
                    for rang, ligne in enumerate(encart["lignes"]):
                        trouve = re.search(r" — (\d+) cas sur (\d+) ", ligne["texte"])
                        self.assertIsNotNone(trouve, ligne["texte"])
                        self.assertEqual(int(trouve.group(2)), len(cas))
                        self.assertEqual(int(trouve.group(1)), par_cause[rang][1])
                        # Identifiants montrés (les mêmes pour tous les profils) : au plus 5, de cette cause
                        ids_texte = MOTIF_ID_OT.findall(ligne["texte"])
                        self.assertTrue(ids_texte, "aucun identifiant d'OT : %r" % ligne["texte"])
                        self.assertEqual(len(ids_texte), min(5, par_cause[rang][1]), ligne["texte"])
                        self.assertTrue(set(ids_texte) <= ot_existants, ids_texte)
                        self.assertTrue(set(ids_texte) <= ot_des_cas, ids_texte)
                        causes = {cause_de_l_ot[i] for i in ids_texte}       # une seule cause par ligne
                        self.assertEqual(len(causes), 1, ids_texte)
                        self.assertEqual(cas_par_cause[causes.pop()], int(trouve.group(1)), ligne["texte"])
                        if type_profil == "demandeur":
                            # Pas d'accès aux OT : identifiants en texte simple, aucun lien
                            self.assertEqual(ligne["ot"], [], "lien vers un OT pour le demandeur : %r" % ligne["texte"])
                        else:
                            self.assertEqual(ligne["ot"], ids_texte, "chaque identifiant est un lien : %r" % ligne["texte"])
                    if type_profil == "demandeur":
                        self.assertEqual(encart["liens_ot"], [], "liens vers les OT montrés au demandeur")
                    else:
                        self.assertTrue(encart["liens_ot"])
                    self.assertEqual(encart["mention"], "Statistique de l'historique, pas un diagnostic")
                    self.assertIn("(%s)" % SYMPTOME_CAUSES, self.page.inner_text(".di-code-symptome"))

                    # Moins de 5 cas : seulement le message, ni cause ni « cas sur »
                    self.ouvrir_fiche(DI_INSUFFISANTE)
                    encart = self.lire_encart()
                    self.assertIsNotNone(encart)
                    self.assertEqual(encart["texte"], "Pas encore assez de cas pour ce symptôme (%d sur 5)" % len(cas_insuffisants))
                    self.assertEqual(encart["lignes"], [])
                    self.assertIsNone(encart["titre"])
                    self.assertNotIn("cas sur", encart["texte"])

                    # Sans code symptôme : pas d'encart
                    self.ouvrir_fiche(DI_SANS_CODE)
                    self.assertIsNone(self.lire_encart())
                    self.assertEqual(self.page.locator(".causes-frequentes").count(), 0)
                    self.assertEqual(self.page.locator(".di-code-symptome").count(), 0)


# ---------------------------------------------------------------------------
# anomalie : DI liée à un OT préventif
# ---------------------------------------------------------------------------

class TestAnomalie(CasDemandesLot2):

    def test_anomalie_di_liee_a_un_ot_preventif_ouvert(self):
        preregler_profil(self.contexte, "technicien", "", TECHNICIEN)
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            demandes_csv = dossier / "demandes.csv"
            ordres_csv = dossier / "ordres_travail.csv"
            ot_origine = ligne_par_id(ordres_csv, OT_PREVENTIF_OUVERT)
            self.assertEqual(ot_origine["origine"], "préventif")
            self.assertEqual(ot_origine["anomalie_constatee"], "0")
            equipement = ot_origine["equipement_id"]
            code_bruit = code_symptome(dossier, "Bruit anormal")
            journal_avant = len(lignes_journal(dossier, "anomalie_constatee", OT_PREVENTIF_OUVERT))

            self.ouvrir(serveur, "#/di/nouvelle?equipement=%s&ot=%s" % (equipement, OT_PREVENTIF_OUVERT))
            self.assertIn("Anomalie constatée pendant l'OT préventif " + OT_PREVENTIF_OUVERT, page.inner_text(".di-origine"))
            self.assertEqual(page.get_attribute(".di-origine a", "href"), "#/ot/" + OT_PREVENTIF_OUVERT)
            self.assertTrue(page.is_visible(".selecteur-choisi"))
            page.click(".di-puce[data-symptome='Bruit anormal']")
            page.click("label.tuile:has(input[value='gêne'])")
            page.fill("textarea[name=description]", "Bruit de roulement côté accouplement, vu pendant le graissage.")
            di = self.envoyer()
            self.assertIn("pendant l'OT préventif " + OT_PREVENTIF_OUVERT, page.inner_text(".di-confirmation"))

            # Sur le disque : DI liée, OT d'origine « anomalie constatée », une entrée au journal
            ligne = ligne_par_id(demandes_csv, di)
            self.assertEqual((ligne["equipement_id"], ligne["ot_origine_id"], ligne["symptome_code"], ligne["statut"]),
                             (equipement, OT_PREVENTIF_OUVERT, code_bruit, "Nouvelle"))
            self.assertEqual(ligne_par_id(ordres_csv, OT_PREVENTIF_OUVERT)["anomalie_constatee"], "1")
            self.assertEqual(len(lignes_journal(dossier, "anomalie_constatee", OT_PREVENTIF_OUVERT)), journal_avant + 1)

            # Idempotent : une seconde DI liée au même OT ne le réécrit pas
            di_bis = page.evaluate("""([equipement, ot]) => Demandes.creer({ equipement_id: equipement,
                symptome: 'Graisseur bouché', impact: 'gêne', ot_origine_id: ot })""", [equipement, OT_PREVENTIF_OUVERT])
            self.assertEqual(ligne_par_id(demandes_csv, di_bis)["ot_origine_id"], OT_PREVENTIF_OUVERT)
            self.assertEqual(ligne_par_id(ordres_csv, OT_PREVENTIF_OUVERT)["anomalie_constatee"], "1")
            self.assertEqual(len(lignes_journal(dossier, "anomalie_constatee", OT_PREVENTIF_OUVERT)), journal_avant + 1)

            # Fiche DI : lien vers l'OT préventif ; liste : mention discrète
            self.ouvrir_fiche(di)
            self.assertEqual(page.inner_text(".di-origine-fiche a"), "Signalée pendant l'OT préventif " + OT_PREVENTIF_OUVERT)
            self.assertEqual(page.get_attribute(".di-origine-fiche a", "href"), "#/ot/" + OT_PREVENTIF_OUVERT)
            self.aller("#/di?statut=tous", ".di-zone-tableau tbody tr")
            ligne_tableau = page.locator(".di-zone-tableau tbody tr.cliquable").filter(has_text=di)
            self.assertIn("pendant l'OT préventif " + OT_PREVENTIF_OUVERT, ligne_tableau.inner_text())

            # API : OT d'origine inconnu ou non préventif → refus, rien d'écrit
            ordres = lire_csv(ordres_csv)
            correctif = next(o["id"] for o in ordres if o["origine"] == "DI")
            nombre = len(lire_csv(demandes_csv))
            script = "Demandes.creer({ equipement_id: %r, symptome: 'Fuite', impact: 'gêne', ot_origine_id: argument })" % equipement
            message = self.erreur_de(script, correctif)
            self.assertIn("ErreurValidation", message)
            self.assertIn("n'est pas un OT préventif", message)
            message = self.erreur_de(script, "OT-1999-9999")
            self.assertIn("ErreurValidation", message)
            self.assertIn("introuvable", message)
            self.assertEqual(len(lire_csv(demandes_csv)), nombre)
            # Écran : ?ot= d'un OT non préventif → avertissement, pas de bandeau d'anomalie
            self.aller("#/di/nouvelle?equipement=%s&ot=%s" % (equipement, correctif), ".di-origine .alerte.attention")
            self.assertIn("n'est pas", page.inner_text(".di-origine"))
            self.assertNotIn("Anomalie constatée", page.inner_text(".di-origine"))

            # Seconde écriture en échec : la DI reste créée, un avertissement le dit
            autre = next(o for o in ordres if o["origine"] == "préventif" and o["anomalie_constatee"] == "0"
                         and o["id"] != OT_PREVENTIF_OUVERT)
            page.evaluate("""() => { const origine = Donnees.modifier;
                Donnees.modifier = async function (table, ...reste) {
                  if (table === 'ordres_travail') throw new Donnees.ErreurStockage('écriture impossible (simulée)');
                  return origine.call(this, table, ...reste);
                }; }""")
            di_sans_marque = page.evaluate("""([equipement, ot]) => Demandes.creer({ equipement_id: equipement,
                symptome: 'Fuite', impact: 'gêne', ot_origine_id: ot })""", [autre["equipement_id"], autre["id"]])
            self.assertEqual(ligne_par_id(demandes_csv, di_sans_marque)["ot_origine_id"], autre["id"])
            self.assertEqual(ligne_par_id(ordres_csv, autre["id"])["anomalie_constatee"], "0")
            self.attendre_toast("n'a pas pu être marqué « anomalie constatée »")
            self.assertIn(di_sans_marque + " est bien créée", page.inner_text("#toast"))


# ---------------------------------------------------------------------------
# verrou : un OT verrouillé (RG3) n'est jamais modifié par une DI liée
# ---------------------------------------------------------------------------

class TestVerrou(CasDemandesLot2):

    def texte(self, selecteur):
        return re.sub(r"\s+", " ", self.page.inner_text(selecteur)).strip()

    def test_verrou_ot_preventif_cloture_administrativement_la_di_est_liee_l_ot_reste_intact(self):
        preregler_profil(self.contexte, "demandeur", "Lucie Martin")
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            ordres_csv = dossier / "ordres_travail.csv"
            ot = ligne_par_id(ordres_csv, OT_PREVENTIF_VERROUILLE)
            self.assertEqual((ot["origine"], ot["statut"], ot["anomalie_constatee"]),
                             ("préventif", "Clôturé administrativement", "0"))
            self.assertIn(ot["statut"], STATUTS_VERROUILLES)
            octets_avant = octets_de_la_ligne(ordres_csv, OT_PREVENTIF_VERROUILLE)
            journal_avant = journal_de_la_ligne(dossier, "ordres_travail", OT_PREVENTIF_VERROUILLE)
            self.ouvrir(serveur, "#/accueil")

            # API : la DI est créée et liée ; l'OT verrouillé n'est pas touché
            di_api = page.evaluate("""([equipement, ot]) => Demandes.creer({ equipement_id: equipement,
                symptome: 'Bruit', impact: 'gêne', ot_origine_id: ot })""", [ot["equipement_id"], OT_PREVENTIF_VERROUILLE])
            self.assertEqual(ligne_par_id(dossier / "demandes.csv", di_api)["ot_origine_id"], OT_PREVENTIF_VERROUILLE)
            self.assertEqual(octets_de_la_ligne(ordres_csv, OT_PREVENTIF_VERROUILLE), octets_avant)
            self.assertEqual(journal_de_la_ligne(dossier, "ordres_travail", OT_PREVENTIF_VERROUILLE), journal_avant)

            # Écran : le bandeau prévient avant l'envoi, la confirmation le redit
            self.aller("#/di/nouvelle?equipement=%s&ot=%s" % (ot["equipement_id"], OT_PREVENTIF_VERROUILLE), ".di-origine .alerte")
            bandeau = self.texte(".di-origine")
            self.assertIn("Anomalie constatée pendant l'OT préventif " + OT_PREVENTIF_VERROUILLE, bandeau)
            self.assertIn("l'OT %s est verrouillé : il ne sera pas marqué « anomalie constatée »" % OT_PREVENTIF_VERROUILLE, bandeau)
            self.assertNotIn("qui sera marqué", bandeau)
            page.click(".di-puce[data-symptome='Fuite']")
            page.click("label.tuile:has(input[value='gêne'])")
            di = self.envoyer()
            confirmation = self.texte(".di-confirmation")
            self.assertIn("pendant l'OT préventif " + OT_PREVENTIF_VERROUILLE, confirmation)
            self.assertIn("L'OT %s est verrouillé : il n'a pas été marqué « anomalie constatée »" % OT_PREVENTIF_VERROUILLE, confirmation)

            # Disque : DI liée ; OT inchangé à l'octet près ; aucune entrée de journal sur l'OT
            self.assertEqual(ligne_par_id(dossier / "demandes.csv", di)["ot_origine_id"], OT_PREVENTIF_VERROUILLE)
            self.assertEqual(octets_de_la_ligne(ordres_csv, OT_PREVENTIF_VERROUILLE), octets_avant)
            self.assertEqual(journal_de_la_ligne(dossier, "ordres_travail", OT_PREVENTIF_VERROUILLE), journal_avant)

    def test_verrou_ot_annule_sur_un_autre_poste_apres_l_ouverture_du_formulaire_pas_marque(self):
        # Le poste A a une version périmée de ordres_travail.csv : 409, relecture, OT vu « Annulé ».
        self.autoriser_erreur(re.compile(r"status of 409.*/api/csv/ordres_travail"))
        preregler_profil(self.contexte, "technicien", "", TECHNICIEN)
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            ordres_csv = dossier / "ordres_travail.csv"
            ot = ligne_par_id(ordres_csv, OT_PREVENTIF_OUVERT)
            self.assertNotIn(ot["statut"], STATUTS_VERROUILLES)
            self.assertEqual(ot["anomalie_constatee"], "0")

            # Poste A : formulaire ouvert sur l'OT encore ouvert (pas de relecture automatique)
            self.ouvrir(serveur, "#/di/nouvelle?equipement=%s&ot=%s" % (ot["equipement_id"], OT_PREVENTIF_OUVERT))
            page.evaluate("Donnees.arreterSurveillance()")
            self.assertIn("qui sera marqué « anomalie constatée »", self.texte(".di-origine"))
            page.click(".di-puce[data-symptome='Fuite']")
            page.click("label.tuile:has(input[value='gêne'])")

            # Poste B : le responsable annule l'OT pendant ce temps
            contexte_b = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
            self.addCleanup(contexte_b.close)
            contexte_b.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
            preregler_profil(contexte_b, "responsable", poste="Poste B")
            poste_b = contexte_b.new_page()
            self.surveiller(poste_b)
            poste_b.goto(serveur.url + "/#/accueil")
            attendre_pret(poste_b)
            poste_b.wait_for_load_state("networkidle")
            statut = ligne_par_id(ordres_csv, OT_PREVENTIF_OUVERT)["statut"]
            poste_b.evaluate("""([ot, statut]) => Ordres.changerStatut(ot, statut, 'Annulé',
                { motif_annulation: 'Équipement déposé (essai)' })""", [OT_PREVENTIF_OUVERT, statut])
            self.assertEqual(ligne_par_id(ordres_csv, OT_PREVENTIF_OUVERT)["statut"], "Annulé")
            octets_annule = octets_de_la_ligne(ordres_csv, OT_PREVENTIF_OUVERT)
            journal_annule = journal_de_la_ligne(dossier, "ordres_travail", OT_PREVENTIF_OUVERT)
            # Le poste A ne le sait pas encore
            self.assertEqual(page.evaluate("(id) => Donnees.trouver('ordres_travail', id).statut", OT_PREVENTIF_OUVERT), statut)
            conflits_avant = page.evaluate("Donnees.statistiques.conflits")

            # Poste A envoie : DI liée, OT annulé laissé tel quel (décision prise sur la ligne fraîche)
            di = self.envoyer()
            self.assertGreater(page.evaluate("Donnees.statistiques.conflits"), conflits_avant)
            self.assertEqual(ligne_par_id(dossier / "demandes.csv", di)["ot_origine_id"], OT_PREVENTIF_OUVERT)
            self.assertEqual(octets_de_la_ligne(ordres_csv, OT_PREVENTIF_OUVERT), octets_annule)
            self.assertEqual(ligne_par_id(ordres_csv, OT_PREVENTIF_OUVERT)["anomalie_constatee"], "0")
            self.assertEqual(journal_de_la_ligne(dossier, "ordres_travail", OT_PREVENTIF_OUVERT), journal_annule)
            self.assertIn("L'OT %s est verrouillé : il n'a pas été marqué « anomalie constatée »" % OT_PREVENTIF_OUVERT,
                          self.texte(".di-confirmation"))


# ---------------------------------------------------------------------------
# suivi : bloc « Suivi » de la fiche, OT de la demande (T38)
# ---------------------------------------------------------------------------

class TestSuivi(CasDemandesLot2):

    def lire_suivi(self):
        return self.page.evaluate("""() => {
            const bloc = document.querySelector('.di-suivi');
            return {
              texte: bloc ? bloc.textContent.replace(/\\s+/g, ' ').trim() : null,
              liens_suivi: bloc ? Array.from(bloc.querySelectorAll('a')).map((a) => a.getAttribute('href')) : [],
              // Tout lien vers les écrans des OT, n'importe où dans la page (fiche, encart, origine)
              liens_ot: Array.from(document.querySelectorAll('#contenu a[href^="#/ot"]')).map((a) => a.getAttribute('href')),
            };
        }""")

    def test_suivi_ot_de_la_di_acceptee_en_texte_pour_le_demandeur_lien_pour_les_autres(self):
        """Le demandeur n'a pas accès aux OT : l'identifiant de l'OT de sa demande est affiché en
        texte simple (un lien le renverrait à l'accueil) ; technicien et responsable gardent le lien."""
        preregler_profil(self.contexte, "demandeur", "Lucie Martin")
        with ServeurPrevo() as serveur:
            demande = ligne_par_id(serveur.dossier / "demandes.csv", DI_ACCEPTEE)
            self.assertEqual((demande["statut"], demande["ot_id"]), ("Acceptée", OT_DE_DI_ACCEPTEE))
            self.assertIsNotNone(ligne_par_id(serveur.dossier / "ordres_travail.csv", OT_DE_DI_ACCEPTEE))

            self.ouvrir(serveur, "#/accueil")
            for type_profil, nom, technicien in (("demandeur", "Lucie Martin", ""), ("technicien", "", TECHNICIEN),
                                                 ("responsable", "", "")):
                with self.subTest(profil=type_profil):
                    if type_profil != "demandeur":
                        self.changer_profil(type_profil, nom, technicien)
                    self.assertEqual(self.page.evaluate("App.profil.type"), type_profil)
                    self.ouvrir_fiche(DI_ACCEPTEE)
                    suivi = self.lire_suivi()
                    self.assertIsNotNone(suivi["texte"])
                    # Même contenu pour tous : la rubrique et l'identifiant de l'OT
                    self.assertIn("Ordre de travail", suivi["texte"])
                    self.assertIn(OT_DE_DI_ACCEPTEE, suivi["texte"])
                    if type_profil == "demandeur":
                        self.assertEqual(suivi["liens_ot"], [], "lien vers un OT montré au demandeur")
                        self.assertEqual(suivi["liens_suivi"], [], "lien dans le bloc « Suivi » du demandeur")
                    else:
                        self.assertIn("#/ot/" + OT_DE_DI_ACCEPTEE, suivi["liens_suivi"])


# ---------------------------------------------------------------------------
# Téléphone 375 px
# ---------------------------------------------------------------------------

class TestTelephone(CasDemandesLot2):

    def setUp(self):
        super().setUp()
        # Contexte « téléphone » à la place du contexte de bureau
        self.contexte.close()
        self.contexte = self.navigateur.new_context(
            locale="fr-FR", viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True)
        self.contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)

    def test_telephone_375_anomalie_encart_et_liste_sans_defilement_horizontal(self):
        preregler_profil(self.contexte, "technicien", "", TECHNICIEN)
        page = self.page
        with ServeurPrevo() as serveur:
            equipement = ligne_par_id(serveur.dossier / "ordres_travail.csv", OT_PREVENTIF_OUVERT)["equipement_id"]
            self.ouvrir(serveur, "#/di/nouvelle?equipement=%s&ot=%s" % (equipement, OT_PREVENTIF_OUVERT))
            self.assertTrue(page.is_visible(".di-origine .alerte"))
            page.click(".di-puce[data-symptome='Fuite']")
            self.assertEqual(self.puces_appuyees(), ["Fuite"])
            petites = page.evaluate("""() => Array.from(document.querySelectorAll('.di-puce'))
                .filter((e) => e.getBoundingClientRect().height < 48).length""")
            self.assertEqual(petites, 0)
            self.sans_defilement_horizontal()
            page.click("label.tuile:has(input[value='gêne'])")
            di = self.envoyer()
            self.sans_defilement_horizontal()
            # Fiche de la DI liée : lien vers l'OT préventif et encart
            self.ouvrir_fiche(di)
            self.assertTrue(page.is_visible(".di-origine-fiche a"))
            self.sans_defilement_horizontal()
            # Fiche d'une DI avec encart (lignes longues, liens)
            self.ouvrir_fiche(DI_CAUSES)
            self.assertTrue(page.is_visible(".di-details .causes-frequentes"))
            self.sans_defilement_horizontal()
            # Liste en cartes avec la mention de l'OT d'origine
            self.aller("#/di", ".di-cartes li")
            self.assertIn("pendant l'OT préventif " + OT_PREVENTIF_OUVERT, page.inner_text(".di-cartes"))
            self.sans_defilement_horizontal()

    def test_telephone_360_zones_tactiles_de_48_px(self):
        """Liens de l'encart (« voir les OT », « et n autres »), du bandeau d'anomalie et de la
        confirmation : zone tactile d'au moins 48 px de haut à 360 px, sans défilement horizontal."""
        page = self.page
        page.set_viewport_size({"width": 360, "height": 740})
        preregler_profil(self.contexte, "technicien", "", TECHNICIEN)
        with ServeurPrevo() as serveur:
            portee, cas = cas_causes(serveur.dossier, EQ_CAUSES, SYMPTOME_CAUSES)
            self.assertEqual(portee, "equipement")
            equipement = ligne_par_id(serveur.dossier / "ordres_travail.csv", OT_PREVENTIF_OUVERT)["equipement_id"]

            # Fiche de la DI de l'équipement « causes » : le plus de liens dans l'encart
            self.ouvrir(serveur, "#/accueil")
            self.ouvrir_fiche(DI_CAUSES)
            liens = page.eval_on_selector_all(".di-details .causes-frequentes li a", "(liens) => liens.map((a) => a.textContent)")
            self.assertGreaterEqual(len(liens), min(5, len(cas)))
            if max(collections.Counter(ot["cause_code"] for ot in cas).values()) > 5:
                self.assertTrue(any(re.match(r"^et \d+ autres?$", texte) for texte in liens), liens)
            self.assertEqual(page.evaluate(PETITES_ZONES_JS), [], "zones tactiles < 48 px sur la fiche " + DI_CAUSES)
            self.sans_defilement_horizontal()

            # Formulaire lié à un OT préventif (lien dans le bandeau), puis confirmation
            self.aller("#/di/nouvelle?equipement=%s&ot=%s" % (equipement, OT_PREVENTIF_OUVERT), ".di-origine a")
            self.assertEqual(page.evaluate(PETITES_ZONES_JS), [], "zones tactiles < 48 px sur le formulaire lié")
            self.sans_defilement_horizontal()
            page.click(".di-puce[data-symptome='Fuite']")
            page.click("label.tuile:has(input[value='gêne'])")
            di = self.envoyer()
            self.assertEqual(page.evaluate(PETITES_ZONES_JS), [], "zones tactiles < 48 px sur la confirmation")
            self.sans_defilement_horizontal()
            # Fiche de la DI liée (lien « Signalée pendant l'OT préventif … » et encart)
            self.ouvrir_fiche(di)
            self.assertEqual(page.evaluate(PETITES_ZONES_JS), [], "zones tactiles < 48 px sur la fiche " + di)
            self.sans_defilement_horizontal()


if __name__ == "__main__":
    unittest.main()
