"""Recette du L2 de la 2.2 « réserves des contrôles et catalogue » (T429 ; CDC CS170, CS171, CS175 côté Contrôles ;
décisions D182, D183, D187, D192, D193 ; D194 pour C18). De bout en bout, à
l'écran, comme un responsable ; les tests de chaque partie (test_reserves*, test_catalogue_*, test_principe_suivi,
test_accueil_lot3, test_bento, test_rapport, test_recette_format4) ne sont pas recopiés ici.

1. Le parcours (CasRecette.parcours), le même dans trois modes, profil Responsable :
     TestParcoursServeur        serveur.py sur une COPIE du jeu de démo, sans comptes (portée « ce PC ») ; données
                                relues dans les CSV du disque ;
     TestParcoursServeurComptes la même chose avec les trois comptes de test (session du responsable), puis la fiche
                                lue par la session du technicien : réserves et nature de la source, aucun bouton ;
     TestParcoursDemo           index.html en file://, « Essayer avec les données de démo » ; données lues en mémoire.
   Étapes :
     - accueil : nombre de réserves en retard relevé avant tout (égal au calcul Python indépendant) ;
     - liste #/controles : phrase D182, jamais « conforme » ;
     - « Nouveau contrôle » : catalogue « réglementation française », saisie libre en premier ; C04 (6 mois) et C13
       (sans périodicité, son aide) : « à confirmer avec votre organisme de contrôle » ; C18 : jamais « conforme » ;
       C14 : 48 mois, sa référence, « obligation réglementaire », relu le 08/11/2026 ; enregistré : provenance
       catalogue, C14, 2026-11-08, obligation ; la fiche le dit (provenance, nature de la source, phrase D182) ;
     - un contrôle créé depuis C04 : sa fiche porte la mention ; la périodicité modifiée (12 mois) le marque
       « saisie », C04 et sa relecture gardés, la mention reste ;
     - réalisation avec trois réserves (il y a 60 jours, sans échéance) : trois lignes, en retard à l'échéance par
       défaut (30 jours, D187), « réserves à lever (3) » ; une seule levée (date, commentaire) : les deux autres
       ouvertes, telles quelles ; nouvelle réalisation (aujourd'hui, une réserve) : rappel des deux ouvertes, aucune
       effacée ; « Créer un OT » depuis une réserve : formulaire pré-rempli, OT créé et relié, « Voir l'OT » ;
     - accueil : réserves en retard = relevé du départ + 2, égal au calcul Python ; le lien mène à la liste filtrée,
       qui montre le contrôle ; rapport mensuel figé depuis la tuile : fait marquant et décision « Lever les n
       réserves en retard : … » (calcul Python : nombre, échéances par défaut, trois plus anciennes citées) ;
     - catalogue relu (une version où C14 passe à 60 mois, relu le 01/03/2027) : la fiche le propose, aucun contrôle
       n'est changé.
2. La reprise D183 d'une base 2.1 vue à l'écran : jeu reserves-a-reprendre (tests/fixtures/formats, variante de
   f3-v2.1.0 : une base de la 2.1, format 3), en mode serveur sans comptes, avec comptes, et en mode dossier
   (navigateur, dossier simulé dans l'OPFS : le passage fait par le navigateur ; la démo n'ouvre pas de base 2.1).
   CTR-0001 (trois lignes d'observations non levées) : trois réserves ouvertes, en retard à l'échéance par défaut ;
   CTR-0002 (observations levées) : deux réserves levées sans date inventée, « levée, date inconnue », commentaire
   « levée avant la 2.2, date inconnue », échéance vide ; l'accueil compte les reprises en retard : les neuf de
   CTR-0005 à CTR-0007, à l'échéance par défaut (calcul Python ; CTR-0001 cite un équipement absent du jeu, CTR-0008
   n'a pas de date de contrôle).
En démo, avant le parcours : le contrôle du réservoir d'air comprimé de la démo (D193 : 48 mois, ligne C14) dit sa
provenance et la date de relecture du catalogue (08/11/2026, non décalée avec les dates de la démo).

Chaque cas travaille sur une copie (jeu de démo, tests/fixtures/formats via tests/jeux_formats.py) dans un dossier
temporaire, ou en mémoire, ou dans l'OPFS du navigateur de test : jamais de données réelles. Aucun identifiant du jeu
de démo écrit en dur ; les dates se calculent depuis Donnees.aujourdhui().

Bibliothèque standard + Playwright. Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_recette_22_l2.py" -v
"""
import csv
import datetime
import html
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from commun import CasNavigateur, RACINE, ServeurPrevo, ServeurStatique, attendre_pret, preregler_profil, url_fichier
from jeux_formats import copier_jeu
import test_formats_navigateur as navigateur
from test_catalogue_controles import (AIDE_SANS_PERIODICITE, C18_AFFICHE, FICHE_JS, FORMULAIRE_JS, MENTION,
                                      MISE_A_JOUR_C14, PHRASE_D182, catalogue_modifie, lignes_par_id)
from test_rapport import fait_reserves_attendu, lire_csv, texte_court
from test_reserves import RESERVES_DE_LA_CARTE_JS

# ---------------------------------------------------------------------------
# Ce que la recette attend
# ---------------------------------------------------------------------------

CATALOGUE = lignes_par_id()
C04, C13, C14 = CATALOGUE["C04"], CATALOGUE["C13"], CATALOGUE["C14"]
RELU_LE = "2026-11-08"                         # D192 : relecture du catalogue validé au L0
PROVENANCE = "Catalogue Prévo (%s), relu le 08/11/2026 — réglementation française"
PROVENANCE_SAISIE = "Saisie (nature choisie au catalogue : %s)"
SOURCE_C14 = "obligation réglementaire · relu le 08/11/2026 · réglementation française"
MOT_CONFORME = re.compile(r"(?<![\w-])conformes?(?![\w-])", re.IGNORECASE)      # CS175 (test_principe_suivi)
DELAI_LEVEE_PAR_DEFAUT = datetime.timedelta(days=30)                           # D187

# Trois réserves saisies à la réalisation, une par ligne (puces et lignes blanches comprises).
SAISIE_TROIS = "- Différentiel 30 mA à remplacer\n\n• Schéma unifilaire à mettre à jour\n1. Prise de terre à reprendre  "
TEXTES_TROIS = ["Différentiel 30 mA à remplacer", "Schéma unifilaire à mettre à jour", "Prise de terre à reprendre"]
NOUVELLE = "Éclairage de secours absent"
COMMENTAIRE_LEVEE = "Schéma mis à jour et affiché (recette L2)"
ORGANISME = "Organisme de la recette L2"

LIEN_RESERVES = "#/controles?filtre=reserves-en-retard"
COMPTEUR_RESERVES = "#bento .bento-conformite a.bento-sous-lien[href='%s'] .chiffre" % LIEN_RESERVES
FICHE = ".controles-fiche .controles-reserves[data-controle='%s']"
CREER_OT = ".controles-reserve[data-reserve='%s'] .controles-reserve-creer-ot"
VOIR_OT = ".controles-reserve[data-reserve='%s'] .controles-reserve-voir-ot"
FORMULAIRE_OT = "#form-nouvel-ot "

# La reprise D183 (tests/fixtures/formats/LISEZMOI.md, jeu reserves-a-reprendre).
JEU_REPRISE = "reserves-a-reprendre"
COMMENTAIRE_REPRISE = "levée avant la 2.2, date inconnue"
REPRISE_OUVERTE = ("CTR-0001", "2026-02-10", ["Garde-corps de la passerelle desserré", "Fin de course haut à régler",
                                              "Câble de levage : un toron cassé"])
REPRISE_LEVEE = ("CTR-0002", "2026-03-18", ["Klaxon de recul inaudible", "Ceinture du siège conducteur usée"])
# Reprises ouvertes d'un contrôle dont l'équipement est suivi et la date connue : CTR-0005, CTR-0006, CTR-0007.
REPRISES_EN_RETARD = ["RES-%05d" % numero for numero in range(6, 15)]
# Mode serveur : une table du format 4 que la reprise ne crée pas (garanties, contrats) est un fichier absent, lu
# comme une table vide après un 404 (stockage-serveur.js) que la console de Chromium note.
TABLE_ABSENTE = re.compile(r"status of 404.*/api/csv/(garanties|contrats_prestataires)\b")

# Si location.hash est déjà la route, l'écran est redessiné (App.reafficher), sinon on y va.
ALLER_JS = "(route) => { if (location.hash === route) return App.reafficher(); location.hash = route; return null; }"
# Un équipement suivi, avec un repère, qui n'exige aucune habilitation (aucun blocage RG8 à la création de l'OT).
EQUIPEMENT_JS = """() => { const e = Donnees.lignes('equipements').find((e) => String(e.actif) !== '0'
  && e.statut !== 'rebut' && !String(e.habilitation_requise || '').trim() && String(e.repere || '').trim());
  return { id: e.id, repere: e.repere }; }"""
LIGNES_JS = "(table) => Donnees.lignes(table).map((ligne) => Object.assign({}, ligne))"
# Le texte du dernier rapport figé (paramètre rapports_mensuels), lu par le stockage du mode.
DERNIER_RAPPORT_JS = """async () => { const noms = Rapport.rapportsFiges();
  return (await App.adaptateur.lireDocument(noms[noms.length - 1])).text(); }"""


def brut(valeur):
    """Valeur d'une cellule (CSV ou mémoire), sans l'apostrophe de protection contre Excel."""
    valeur = "" if valeur is None else str(valeur).strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def propre(ligne):
    return {cle: brut(valeur) for cle, valeur in ligne.items() if cle is not None}


def jour(valeur):
    texte = brut(valeur)[:10]
    return datetime.date.fromisoformat(texte) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texte) else None


def fr(date):
    return date.strftime("%d/%m/%Y")


def lignes_du_csv(octets):
    """Lignes (dict, cellules propres) d'un CSV donné en octets (BOM, « ; »)."""
    return [propre(ligne) for ligne in csv.DictReader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";")]


def en_retard(reserves, controles, equipements, aujourdhui):
    """Réserves en retard, calcul indépendant de l'application (CS170, D187) : [(échéance, id, échéance par défaut ?)]
    des réserves ouvertes d'un contrôle dont l'équipement est suivi (actif, pas au rebut), à l'échéance saisie, sinon
    30 jours après le contrôle, passée ; l'échéance la plus ancienne d'abord, puis par identifiant (ordre de
    l'accueil et du rapport)."""
    equipements = {e["id"]: e for e in equipements}
    controles = {c["id"]: c for c in controles}
    retards = []
    for reserve in reserves:
        controle = controles.get(reserve["controle_id"])
        equipement = equipements.get(controle["equipement_id"]) if controle else None
        if reserve["levee"] == "1" or not equipement or equipement["actif"] == "0" or equipement["statut"] == "rebut":
            continue
        saisie, releve = jour(reserve["echeance_levee"]), jour(reserve["date_controle"])
        echeance = saisie or (releve + DELAI_LEVEE_PAR_DEFAUT if releve else None)
        if echeance is not None and echeance < aujourdhui:
            retards.append((echeance, reserve["id"], saisie is None))
    return sorted(retards)


# ---------------------------------------------------------------------------
# Aides d'écran communes
# ---------------------------------------------------------------------------

class Ecran:
    """À mêler à un CasNavigateur : lecture des écrans Contrôles, accueil. Le mode fournit lignes(table)."""

    def lignes(self, table):  # pragma: no cover - fourni par le mode
        raise NotImplementedError

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)

    def aujourdhui(self):
        return datetime.date.fromisoformat(self.js("Donnees.aujourdhui()"))

    def aller(self, route, selecteur, page=None):
        page = page or self.page
        page.evaluate(ALLER_JS, route)
        page.wait_for_selector(selecteur)

    def attendre_toast(self, texte):
        self.page.wait_for_function("(t) => document.getElementById('toast').textContent.includes(t)", arg=texte)

    def attendre_titre(self, titre, page=None):
        (page or self.page).wait_for_function(
            "(t) => { const h = document.querySelector('.controles-fiche .controles-reserves > .entete-carte h2'); "
            "return h && h.textContent.trim() === t; }", arg=titre)

    def carte(self, page=None):
        return (page or self.page).evaluate(RESERVES_DE_LA_CARTE_JS)

    def groupes(self):
        return self.page.eval_on_selector_all(".controles-fiche .controles-reserves-groupe h3",
                                              "hs => hs.map((h) => h.textContent.trim())")

    def badges(self, controle):
        return self.page.eval_on_selector_all(".controles-fiche .controles-statuts[data-controle='%s'] .badge" % controle,
                                              "l => l.map((b) => b.textContent.trim())")

    def dernier_controle_reserves(self):
        return self.page.inner_text(".controles-fiche .controles-dernier .controles-dernier-reserves").strip()

    def phrases(self, page=None):
        return (page or self.page).eval_on_selector_all(
            "#contenu .controles-principe", "l => l.filter((e) => e.getClientRects().length).map((e) => e.textContent.trim())")

    def verifier_principe(self, ecran, page=None):
        """CS175 : la phrase D182, une fois, et aucun « conforme » sur l'écran."""
        with self.subTest(ecran=ecran):
            self.assertEqual(self.phrases(page), [PHRASE_D182])
            texte = (page or self.page).evaluate("() => document.querySelector('#contenu').innerText")
            self.assertIsNone(MOT_CONFORME.search(texte), "« conforme » sur l'écran %s" % ecran)

    def reserves(self, controle):
        return [r for r in self.lignes("reserves_controle") if r["controle_id"] == controle]

    def controle(self, identifiant):
        return next(c for c in self.lignes("controles_reglementaires") if c["id"] == identifiant)

    def retards(self):
        return en_retard(self.lignes("reserves_controle"), self.lignes("controles_reglementaires"),
                         self.lignes("equipements"), self.aujourdhui())

    def compteur_accueil(self):
        """Nombre de réserves en retard affiché à l'accueil du responsable (tuile « Contrôles et habilitations »)."""
        self.aller("#/accueil", COMPTEUR_RESERVES)
        return int(self.page.inner_text(COMPTEUR_RESERVES).strip())


# ---------------------------------------------------------------------------
# 1. Le parcours
# ---------------------------------------------------------------------------

class CasRecette(Ecran, CasNavigateur):
    """Le parcours CS170, CS171, CS175 ; le mode ouvre l'application (profil Responsable) puis appelle parcours()."""

    def formulaire(self):
        return self.js(FORMULAIRE_JS)

    def choisir(self, ligne):
        self.page.select_option("#form-controle [name=catalogue_id]", ligne)
        return self.formulaire()

    def enregistrer_nouveau(self):
        """« Enregistrer » du formulaire de création ; rend l'identifiant du contrôle, sa fiche affichée."""
        self.page.click("#form-controle button[type=submit]")
        self.page.wait_for_function("() => /^#\\/controles\\/CTR-/.test(location.hash)")
        identifiant = self.js("decodeURIComponent(location.hash.split('/').pop())")
        self.page.wait_for_selector(FICHE % identifiant)
        self.page.wait_for_selector("#contenu .controles-source")
        return identifiant

    def parcours(self):
        """Le parcours complet ; rend ce qu'il a créé (contrôles C14 et C04, réserves, OT)."""
        avant = self.compteur_accueil()
        self.assertEqual(avant, len(self.retards()), "accueil ≠ calcul Python avant le parcours")
        equipement = self.js(EQUIPEMENT_JS)
        self.aller("#/controles", ".controles-liste a.controles-lien")
        self.verifier_principe("liste")
        c14 = self.creer_depuis_le_catalogue(equipement)
        c04 = self.creer_depuis_c04_puis_modifier(equipement)
        reserves = self.realiser_lever_realiser(c14)
        ot = self.creer_un_ot_depuis_une_reserve(c14, reserves, equipement)
        self.accueil_et_rapport(avant, c14, reserves)
        self.catalogue_relu(c14)
        return {"c14": c14, "c04": c04, "reserves": reserves, "ot": ot, "equipement": equipement}

    # -- CS171 : le catalogue à la création ----------------------------------------------------------

    def creer_depuis_le_catalogue(self, equipement):
        page = self.page
        self.aller("#/controles/nouveau?equipement=" + equipement["id"], "#form-controle [name=catalogue_id]")
        releve = self.formulaire()
        self.assertEqual(releve["libelle"], "Choisir dans le catalogue Prévo — réglementation française")
        self.assertEqual((releve["premiere"], releve["choisie"], releve["encart"]),
                         (["", "Saisie libre (hors catalogue)"], "", False))
        self.verifier_principe("formulaire, saisie libre")
        aide_initiale = releve["aidePeriodicite"]

        # C04 et C13 : « à confirmer avec votre organisme de contrôle » (D192) ; C13 sans périodicité, son aide.
        releve = self.choisir("C04")
        self.assertEqual((releve["nature"], releve["periodicite"], releve["natureSource"], releve["mentions"]),
                         (C04["nature"], "6", "obligation", [MENTION]))
        self.assertIn("relu le 08/11/2026", releve["texteEncart"])
        self.assertEqual(releve["provenance"], PROVENANCE % "C04")
        self.verifier_principe("formulaire, C04")
        releve = self.choisir("C13")
        self.assertEqual((releve["nature"], releve["periodicite"], releve["natureSource"], releve["mentions"]),
                         (C13["nature"], "", "recommandation", [MENTION]))
        self.assertEqual(releve["aidePeriodicite"], AIDE_SANS_PERIODICITE)
        self.verifier_principe("formulaire, C13")
        # C18 : son résumé validé dit « conforme » ; l'écran jamais (D194).
        releve = self.choisir("C18")
        self.assertIn(C18_AFFICHE, releve["texteEncart"])
        self.verifier_principe("formulaire, C18")

        # C14 : périodicité, référence et nature de la source pré-remplies, affichées avec la date de relecture.
        releve = self.choisir("C14")
        self.assertEqual((releve["nature"], releve["periodicite"], releve["reference"], releve["natureSource"]),
                         (C14["nature"], "48", C14["reference"], "obligation"))
        self.assertEqual(releve["natureSourceAffichee"], "obligation réglementaire")
        self.assertIn(SOURCE_C14, releve["texteEncart"])
        self.assertEqual((releve["provenance"], releve["badge"], releve["mentions"]), (PROVENANCE % "C14", "", []))
        self.assertEqual(releve["aidePeriodicite"], aide_initiale)
        self.verifier_principe("formulaire, C14")
        page.fill("#form-controle [name=organisme]", ORGANISME)
        c14 = self.enregistrer_nouveau()

        ligne = self.controle(c14)
        self.assertEqual({cle: ligne[cle] for cle in ("equipement_id", "nature", "periodicite_mois", "texte_reference",
                                                       "source_periodicite", "catalogue_id", "catalogue_relu_le",
                                                       "nature_source", "organisme")},
                         {"equipement_id": equipement["id"], "nature": C14["nature"], "periodicite_mois": "48",
                          "texte_reference": C14["reference"], "source_periodicite": "catalogue", "catalogue_id": "C14",
                          "catalogue_relu_le": RELU_LE, "nature_source": "obligation", "organisme": ORGANISME})
        fiche = self.js(FICHE_JS)
        self.assertEqual((fiche["provenance"], fiche["natureSource"], fiche["miseAJour"], fiche["bouton"]),
                         (PROVENANCE % "C14", "obligation", None, False))
        self.assertEqual(page.locator("#contenu .controles-source .controles-catalogue-mention").count(), 0)
        self.verifier_principe("fiche du contrôle créé depuis C14")
        return c14

    def creer_depuis_c04_puis_modifier(self, equipement):
        """C04 enregistré : la fiche porte la mention ; la périodicité changée le marque « saisie » (CS171)."""
        page = self.page
        self.aller("#/controles/nouveau?equipement=" + equipement["id"], "#form-controle [name=catalogue_id]")
        self.choisir("C04")
        c04 = self.enregistrer_nouveau()
        mention = "#contenu .controles-source .controles-catalogue-mention"
        self.assertEqual(self.js(FICHE_JS)["provenance"], PROVENANCE % "C04")
        self.assertEqual(page.inner_text(mention).strip(), MENTION)
        self.assertEqual({cle: self.controle(c04)[cle] for cle in ("periodicite_mois", "source_periodicite", "catalogue_id",
                                                                   "catalogue_relu_le", "nature_source")},
                         {"periodicite_mois": "6", "source_periodicite": "catalogue", "catalogue_id": "C04",
                          "catalogue_relu_le": RELU_LE, "nature_source": "obligation"})
        page.fill("#form-controle [name=periodicite_mois]", "12")
        page.click("#form-controle button[type=submit]")
        self.attendre_toast("Contrôle enregistré.")
        page.wait_for_function("(t) => { const p = document.querySelector('#contenu .controles-source .controles-provenance');"
                               " return p && p.textContent.trim() === t; }", arg=PROVENANCE_SAISIE % "C04")
        self.assertEqual({cle: self.controle(c04)[cle] for cle in ("periodicite_mois", "source_periodicite", "catalogue_id",
                                                                   "catalogue_relu_le", "nature_source")},
                         {"periodicite_mois": "12", "source_periodicite": "saisie", "catalogue_id": "C04",
                          "catalogue_relu_le": RELU_LE, "nature_source": "obligation"})
        self.assertEqual(page.inner_text(mention).strip(), MENTION)
        self.verifier_principe("fiche du contrôle C04 modifié")
        return c04

    # -- CS170 : réserves ----------------------------------------------------------------------------

    def ouvrir_realisation(self):
        self.page.click("#controle-realise")
        self.page.wait_for_selector("dialog [name=reserves]")

    def valider_fenetre(self):
        self.page.click("dialog .fenetre-actions .btn-primaire")

    def realiser_lever_realiser(self, controle):
        """Trois réserves ; en lever une ; une nouvelle réalisation n'en efface aucune. Rend les quatre identifiants."""
        page = self.page
        aujourdhui = self.aujourdhui()
        d1 = aujourdhui - datetime.timedelta(days=60)
        self.aller("#/controles/" + controle, FICHE % controle)
        self.assertEqual(page.inner_text(".controles-reserves .controles-reserves-vide"), "Aucune réserve relevée.")

        # Réalisation il y a 60 jours, trois lignes, sans échéance : trois réserves, en retard à l'échéance par défaut.
        self.ouvrir_realisation()
        page.fill("dialog [name=date]", d1.isoformat())
        page.fill("dialog [name=organisme]", ORGANISME)
        page.fill("dialog [name=reserves]", SAISIE_TROIS)
        self.assertEqual(page.text_content("dialog .controles-apercu-reserves").strip(), "3 réserves seront enregistrées.")
        self.valider_fenetre()
        self.attendre_toast("Contrôle réalisé enregistré, 3 réserves relevées.")
        self.attendre_titre("Réserves (3, dont 3 à lever)")
        trois = self.reserves(controle)
        self.assertEqual([r["texte"] for r in trois], TEXTES_TROIS)
        for reserve in trois:
            self.assertEqual((reserve["date_controle"], reserve["echeance_levee"], reserve["levee"], reserve["date_levee"],
                              reserve["ot_id"]), (d1.isoformat(), "", "0", "", ""), reserve)
        ids = [r["id"] for r in trois]
        carte = self.carte()
        self.assertEqual([(r["id"], r["statut"], r["badge"]) for r in carte], [(i, "en retard", "en retard") for i in ids])
        for reserve in carte:
            self.assertIn("échéance le %s (30 jours après le contrôle)" % fr(d1 + DELAI_LEVEE_PAR_DEFAUT), reserve["meta"])
        self.assertIn("réserves à lever (3)", self.badges(controle))
        self.assertEqual(self.dernier_controle_reserves(), "3")

        # En lever une : les deux autres restent ouvertes, telles quelles.
        levee_le = d1 + datetime.timedelta(days=5)
        page.click(".controles-reserve[data-reserve='%s'] [data-action=lever]" % ids[1])
        page.wait_for_selector("dialog [name=commentaire]")
        page.fill("dialog [name=date]", levee_le.isoformat())
        page.fill("dialog [name=commentaire]", COMMENTAIRE_LEVEE)
        self.valider_fenetre()
        self.attendre_toast("Réserve levée.")
        self.attendre_titre("Réserves (3, dont 2 à lever)")
        apres_levee = self.reserves(controle)
        self.assertEqual((apres_levee[0], apres_levee[2]), (trois[0], trois[2]))
        self.assertEqual((apres_levee[1]["levee"], apres_levee[1]["date_levee"], apres_levee[1]["commentaire_levee"]),
                         ("1", levee_le.isoformat(), COMMENTAIRE_LEVEE))
        self.assertIn("réserves à lever (2)", self.badges(controle))
        carte = {r["id"]: r for r in self.carte()}
        self.assertEqual((carte[ids[1]]["statut"], carte[ids[1]]["badge"], carte[ids[1]]["repliee"]),
                         ("levée", "levée le %s" % fr(levee_le), True))
        self.assertEqual([carte[i]["statut"] for i in (ids[0], ids[2])], ["en retard", "en retard"])

        # Nouvelle réalisation aujourd'hui, une réserve : rappel des deux ouvertes ; aucune réserve effacée.
        self.ouvrir_realisation()
        self.assertEqual(page.inner_text("dialog .controles-reserves-precedentes"),
                         "2 réserves des contrôles précédents restent à lever.")
        page.fill("dialog [name=reserves]", NOUVELLE)
        self.valider_fenetre()
        self.attendre_toast("Contrôle réalisé enregistré, 1 réserve relevée.")
        self.attendre_titre("Réserves (4, dont 3 à lever)")
        quatre = self.reserves(controle)
        self.assertEqual(quatre[:3], apres_levee)
        self.assertEqual((quatre[3]["texte"], quatre[3]["date_controle"], quatre[3]["levee"]),
                         (NOUVELLE, aujourdhui.isoformat(), "0"))
        self.assertEqual(self.controle(controle)["derniere_date"], aujourdhui.isoformat())
        self.assertEqual(self.groupes(), ["Contrôle du %s — 1 réserve" % fr(aujourdhui),
                                          "Contrôle du %s — 3 réserves" % fr(d1)])
        self.assertIn("réserves à lever (3)", self.badges(controle))
        self.assertEqual(self.dernier_controle_reserves(), "1")
        self.verifier_principe("fiche après les réalisations")
        return ids + [quatre[3]["id"]]

    def creer_un_ot_depuis_une_reserve(self, controle, reserves, equipement):
        """« Créer un OT » depuis la première réserve : pré-rempli, rien sans « Créer », puis créé et relié."""
        page = self.page
        premiere, troisieme = reserves[0], reserves[2]
        nombre = len(self.lignes("ordres_travail"))
        page.click(CREER_OT % premiere)
        page.wait_for_selector(FORMULAIRE_OT + "[name=titre]")
        valeurs = {nom: page.input_value(FORMULAIRE_OT + "[name=%s]" % nom) for nom in ("equipement_id", "titre", "type")}
        self.assertEqual(valeurs, {"equipement_id": equipement["id"], "type": "réglementaire",
                                   "titre": "Levée de la réserve — " + TEXTES_TROIS[0]})
        self.assertEqual(len(self.lignes("ordres_travail")), nombre)
        page.click(FORMULAIRE_OT + "button[type=submit]")
        page.wait_for_function("() => /^#\\/ot\\/OT-/.test(location.hash)")
        ot = self.js("decodeURIComponent(location.hash.slice('#/ot/'.length))")
        self.attendre_toast("Ordre de travail %s créé et relié à la réserve." % ot)
        ordres = self.lignes("ordres_travail")
        self.assertEqual(len(ordres), nombre + 1)
        ligne = next(o for o in ordres if o["id"] == ot)
        self.assertEqual((ligne["equipement_id"], ligne["type"], ligne["titre"]),
                         (equipement["id"], "réglementaire", "Levée de la réserve — " + TEXTES_TROIS[0]))
        self.assertEqual([r["ot_id"] for r in self.reserves(controle)], [ot, "", "", ""])
        self.aller("#/controles/" + controle, FICHE % controle)
        self.assertEqual(page.get_attribute(VOIR_OT % premiere, "href"), "#/ot/" + ot)
        self.assertEqual((page.locator(CREER_OT % premiere).count(), page.locator(CREER_OT % troisieme).count()), (0, 1))
        return ot

    # -- CS170 : accueil et rapport ------------------------------------------------------------------

    def accueil_et_rapport(self, avant, controle, reserves):
        page = self.page
        retards = self.retards()
        identifiants = [identifiant for _, identifiant, _ in retards]
        # Les deux réserves encore ouvertes du contrôle d'il y a 60 jours sont en retard ; ni la levée ni celle du jour.
        self.assertTrue({reserves[0], reserves[2]} <= set(identifiants), identifiants)
        self.assertFalse({reserves[1], reserves[3]} & set(identifiants), identifiants)
        self.assertEqual(self.compteur_accueil(), avant + 2)
        self.assertEqual(self.compteur_accueil(), len(retards))
        # Le lien mène à la liste filtrée, qui montre le contrôle.
        page.click("#bento .bento-conformite a[href='%s']" % LIEN_RESERVES)
        page.wait_for_function("() => document.querySelector('#controles-statut') && "
                               "document.querySelector('#controles-statut').value === 'reserves-en-retard'")
        self.assertGreaterEqual(page.locator("#contenu .controles-liste a.controles-lien[href='#/controles/%s']"
                                             % controle).count(), 1)

        # Rapport mensuel figé depuis la tuile de l'accueil : fait marquant et décision (D187 : échéance par défaut).
        self.aller("#/accueil", '#bandeau-rapport [data-action="figer-rapport"]')
        figes = self.js("Rapport.rapportsFiges().length")
        page.click('#bandeau-rapport [data-action="figer-rapport"]')
        page.wait_for_function("(n) => Rapport.rapportsFiges().length > n", arg=figes)
        contenu = html.unescape(self.js(DERNIER_RAPPORT_JS))
        aujourdhui = self.aujourdhui()
        nombre, par_defaut = len(retards), sum(1 for _, _, defaut in retards if defaut)
        self.assertIn("<li>%s</li>" % fait_reserves_attendu(nombre, par_defaut, fr(aujourdhui)), contenu)
        lignes = {r["id"]: r for r in self.lignes("reserves_controle")}
        controles = {c["id"]: c for c in self.lignes("controles_reglementaires")}
        reperes = {e["id"]: e["repere"] for e in self.lignes("equipements")}
        citees = " ; ".join("%s (%s)" % (texte_court(lignes[i]["texte"]), reperes[controles[lignes[i]["controle_id"]]["equipement_id"]])
                            for i in identifiants[:3])
        debut = "Lever la réserve en retard : " if nombre == 1 else "Lever les %d réserves en retard : " % nombre
        self.assertIn("<li>%s%s.</li>" % (debut, citees), contenu)

    # -- CS171 : un catalogue relu ne change aucun contrôle ------------------------------------------

    def catalogue_relu(self, controle):
        avant = self.lignes("controles_reglementaires")
        dossier = tempfile.mkdtemp(prefix="prevo-t429-")
        self.addCleanup(shutil.rmtree, dossier, True)
        self.page.add_script_tag(content=catalogue_modifie(dossier))
        self.assertEqual(self.js("() => Controles.ligneCatalogue('C14').periodicite_mois"), 60)
        self.aller("#/controles/" + controle, "#contenu .controles-mise-a-jour")
        fiche = self.js(FICHE_JS)
        self.assertEqual((fiche["miseAJour"], fiche["bouton"], fiche["provenance"]),
                         (MISE_A_JOUR_C14, True, PROVENANCE % "C14"))
        self.assertEqual(self.lignes("controles_reglementaires"), avant, "le catalogue relu a changé un contrôle")
        self.verifier_principe("fiche, catalogue relu")


class CasParcoursServeur(CasRecette):
    """serveur.py sur une copie du jeu de démo ; données relues dans les CSV du disque."""

    COMPTES = False

    def lignes(self, table):
        if not (self.dossier / (table + ".csv")).exists():
            return []
        return [propre(ligne) for ligne in lire_csv(self.dossier, table + ".csv")]

    def lancer(self):
        with ServeurPrevo(comptes=self.COMPTES) as serveur:
            self.serveur, self.dossier = serveur, Path(serveur.dossier)
            if self.COMPTES:
                serveur.poser_session(self.contexte, "responsable")
            else:
                preregler_profil(self.contexte, "responsable", "Nicolas Briand")
            self.page.goto(serveur.url + "/#/accueil")
            attendre_pret(self.page)
            self.page.wait_for_load_state("networkidle")       # écritures du démarrage (OT préventifs échus) finies
            self.assertEqual(self.js("App.profil.type"), "responsable")
            cree = self.parcours()
            self.apres_le_parcours(serveur, cree)

    def apres_le_parcours(self, serveur, cree):
        pass


class TestParcoursServeur(CasParcoursServeur):

    def test_parcours_catalogue_reserves_ot_accueil_rapport(self):
        self.lancer()


class TestParcoursServeurComptes(CasParcoursServeur):

    COMPTES = True

    def test_parcours_avec_comptes_puis_la_fiche_lue_par_le_technicien(self):
        self.lancer()

    def apres_le_parcours(self, serveur, cree):
        """La session du technicien lit la fiche : réserves, nature de la source, provenance, phrase ; aucun bouton."""
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        serveur.poser_session(contexte, "technicien")
        page = contexte.new_page()
        self.surveiller(page)
        page.goto(serveur.url + "/#/controles/" + cree["c14"])
        attendre_pret(page)
        page.wait_for_selector(FICHE % cree["c14"])
        self.assertEqual(page.evaluate("App.profil.type"), "technicien")
        self.attendre_titre("Réserves (4, dont 3 à lever)", page)
        self.assertEqual(sorted(r["id"] for r in self.carte(page)), sorted(cree["reserves"]))
        for selecteur in (".controles-reserves button", ".controles-reserve-creer-ot", ".controles-reserve-voir-ot",
                          "#controle-realise", "#controle-creer-ot", ".controles-fiche [name]"):
            self.assertEqual(page.locator(selecteur).count(), 0, selecteur)
        description = page.inner_text("#contenu .controles-zone-controle")
        self.assertIn("obligation réglementaire", description)
        self.assertIn(PROVENANCE % "C14", description)
        self.verifier_principe("fiche lue par le technicien", page)


class TestParcoursDemo(CasRecette):
    """index.html en file:// (démo, données en mémoire)."""

    def lignes(self, table):
        return [propre(ligne) for ligne in self.js(LIGNES_JS, table)]

    def test_parcours_en_demo(self):
        preregler_profil(self.contexte, "responsable", "Nicolas Briand")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.assertEqual((self.js("App.mode"), self.js("App.profil.type")), ("demo", "responsable"))
        # Le réservoir d'air comprimé de la démo (D193) : 48 mois, ligne C14, relu le 08/11/2026 à l'écran.
        reservoir = next(c for c in self.lignes("controles_reglementaires") if c["catalogue_id"] == "C14")
        self.assertEqual((reservoir["periodicite_mois"], reservoir["source_periodicite"], reservoir["catalogue_relu_le"]),
                         ("48", "catalogue", RELU_LE))
        self.aller("#/controles/" + reservoir["id"], FICHE % reservoir["id"])
        self.assertEqual(self.js(FICHE_JS)["provenance"], PROVENANCE % "C14")
        self.parcours()


# ---------------------------------------------------------------------------
# 2. La reprise D183 d'une base 2.1, vue à l'écran
# ---------------------------------------------------------------------------

class VerificationsDeLaReprise(Ecran):
    """À mêler à un CasNavigateur dont l'application est ouverte sur le jeu reserves-a-reprendre, profil Responsable."""

    def verifier_reprise(self):
        page = self.page
        controle, date, textes = REPRISE_OUVERTE
        controle_leve, date_levee, textes_leves = REPRISE_LEVEE
        # Les données : une réserve par ligne non vide ; levées sans date inventée (D183).
        ouvertes = self.reserves(controle)
        self.assertEqual([(r["texte"], r["date_controle"], r["levee"]) for r in ouvertes], [(t, date, "0") for t in textes])
        for reserve in ouvertes:
            self.assertEqual((reserve["echeance_levee"], reserve["date_levee"], reserve["commentaire_levee"], reserve["ot_id"]),
                             ("", "", "", ""), reserve)
        levees = self.reserves(controle_leve)
        self.assertEqual([(r["texte"], r["date_controle"], r["levee"]) for r in levees],
                         [(t, date_levee, "1") for t in textes_leves])
        for reserve in levees:
            self.assertEqual((reserve["echeance_levee"], reserve["date_levee"], reserve["commentaire_levee"]),
                             ("", "", COMMENTAIRE_REPRISE), reserve)

        # CTR-0001 : trois réserves ouvertes, en retard à l'échéance par défaut (30 jours après le contrôle).
        self.aller("#/controles/" + controle, FICHE % controle)
        self.attendre_titre("Réserves (3, dont 3 à lever)")
        echeance = fr(datetime.date.fromisoformat(date) + DELAI_LEVEE_PAR_DEFAUT)
        self.assertEqual(self.groupes(), ["Contrôle du %s — 3 réserves" % fr(datetime.date.fromisoformat(date))])
        carte = self.carte()
        self.assertEqual([(r["texte"], r["statut"], r["badge"]) for r in carte], [(t, "en retard", "en retard") for t in textes])
        for reserve in carte:
            self.assertIn("échéance le %s (30 jours après le contrôle)" % echeance, reserve["meta"])
        self.assertIn("réserves à lever (3)", self.badges(controle))
        self.assertEqual(self.dernier_controle_reserves(), "3")

        # CTR-0002 : deux réserves levées, « levée, date inconnue », commentaire de la reprise, aucune échéance.
        self.aller("#/controles/" + controle_leve, FICHE % controle_leve)
        self.attendre_titre("Réserves (2, toutes levées)")
        carte = self.carte()
        self.assertEqual([(r["texte"], r["statut"], r["badge"], r["repliee"]) for r in carte],
                         [(t, "levée", "levée, date inconnue", True) for t in textes_leves])
        for reserve in carte:
            self.assertEqual(reserve["commentaire"], "Ce qui a été fait : " + COMMENTAIRE_REPRISE)
            self.assertNotIn("échéance", reserve["meta"])
        self.assertEqual(page.inner_text(".controles-reserves-levees summary"), "Voir les réserves levées (2)")
        self.assertFalse([b for b in self.badges(controle_leve) if b.startswith("réserves à lever")])

        # Accueil : les réserves reprises en retard comptées (presque toutes, au premier lancement : L1 R6) ; celles de
        # CTR-0001 non, son équipement n'est pas dans le jeu (référence qui pend, LISEZMOI), ni celle de CTR-0008 (date
        # du contrôle inconnue : aucune échéance).
        retards = self.retards()
        self.assertEqual(sorted(identifiant for _, identifiant, _ in retards), REPRISES_EN_RETARD)
        self.assertTrue(all(defaut for _, _, defaut in retards))
        self.assertEqual(self.compteur_accueil(), len(REPRISES_EN_RETARD))


class TestRepriseServeur(VerificationsDeLaReprise, CasNavigateur):
    """serveur.py démarré sur une copie du jeu : passage au format 4 au démarrage, puis l'écran."""

    def lignes(self, table):
        if not (self.dossier / (table + ".csv")).exists():
            return []
        return [propre(ligne) for ligne in lire_csv(self.dossier, table + ".csv")]

    def verifier_serveur(self, comptes):
        temporaire = Path(tempfile.mkdtemp(prefix="prevo-t429-reprise-"))
        self.addCleanup(shutil.rmtree, temporaire, True)
        source = copier_jeu(JEU_REPRISE, temporaire / "donnees")
        self.assertFalse((source / "reserves_controle.csv").exists())          # base 2.1 : aucune réserve
        self.autoriser_erreur(TABLE_ABSENTE)
        with ServeurPrevo(source=source, comptes=comptes) as serveur:
            self.dossier = Path(serveur.dossier)
            if comptes:
                serveur.poser_session(self.contexte, "responsable")
            else:
                preregler_profil(self.contexte, "responsable", "Nicolas Briand")
            self.page.goto(serveur.url + "/#/accueil")
            attendre_pret(self.page)
            self.page.wait_for_load_state("networkidle")
            self.verifier_reprise()

    def test_base_2_1_reprise_sans_comptes(self):
        self.verifier_serveur(comptes=False)

    def test_base_2_1_reprise_avec_comptes(self):
        self.verifier_serveur(comptes=True)


class TestRepriseNavigateur(VerificationsDeLaReprise, navigateur.CasFormats):
    """Mode dossier (navigateur) : le passage au format 4 fait par l'application à l'ouverture du dossier."""

    def lignes(self, table):
        octets = self.instantane().get(table + ".csv")
        return lignes_du_csv(octets) if octets is not None else []

    def test_base_2_1_reprise_en_mode_dossier(self):
        fichiers = navigateur.fichiers_du_jeu(JEU_REPRISE)
        self.assertNotIn("reserves_controle.csv", fichiers)
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier(statique, fichiers, profil="responsable")
            self.assertIn("reserves_controle.csv", self.instantane())
            self.verifier_reprise()


if __name__ == "__main__":
    unittest.main()
