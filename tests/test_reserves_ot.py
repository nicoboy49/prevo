"""Tests de « Créer un OT » depuis une réserve, 2.2 (T420 ; CS170, CS176, D156, RG8 ; CONCEPTION-L2-L3 §3.4).

La carte « Réserves » de la fiche d'un contrôle propose au responsable, par réserve ouverte, « Créer un OT » (lien vers
#/ot/nouveau pré-rempli par Controles.adresseOtReserve : type réglementaire, équipement du contrôle, titre « Levée de la
réserve — <texte, 80 caractères> », travail à faire = le texte entier et « Contrôle du JJ/MM/AAAA : <nature> », écrits
dans la langue de l'installation ; ?reserve=RES-…), ou « Voir l'OT » quand la réserve en a un. Rien n'est créé sans
« Créer » ; ordres-fiche.js relie alors l'OT créé à la réserve (Controles.lierOtAReserve). Lien impossible (réserve
levée ou reliée ailleurs entre-temps) : l'OT reste créé, un toast le dit.

    serveur  : serveur.py sur une copie du jeu de démo, CSV relus sur le disque ; aucun identifiant du jeu écrit en dur
               (rôles de scenarios_demo() ; contrôle et réserves créés par le test) ;
               - responsable : « Créer un OT » sur chaque réserve ouverte, « Lever » et « Modifier » inchangés ; adresse
                 et formulaire pré-remplis ; ordres_travail.csv identique à l'octet tant que « Créer » n'est pas cliqué ;
                 RG8 suivie (pas d'exigence propre à l'OT, celle de l'équipement compte) : technicien à la BR échue
                 refusé, rien d'écrit, réserve sans OT ; technicien habilité : OT créé, réserve reliée (CSV, journal
                 « reliée à OT-… »), toast ; la carte montre l'OT lié et « Voir l'OT » ; l'autre réserve garde « Créer
                 un OT » ; l'historique dit « Reliée à OT-… » ;
               - lien impossible : réserve reliée ailleurs, puis réserve levée entre l'ouverture du formulaire et
                 « Créer » : chaque OT est créé, la réserve garde son état, toast « OT … créé, mais la réserve n'a pas pu
                 lui être reliée : … » ;
    demo     : index.html en file:// ;
               - écran en anglais, installation (démo) en français : libellés anglais, titre et travail en français
                 (D156) ; « View the WO » vers l'OT lié ; OT créé et relié, toast anglais ;
               - technicien : ni « Créer un OT » ni « Voir l'OT ».

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_reserves_ot.py" -v
"""
import csv
import datetime
import io
import json
import unittest
from pathlib import Path
from urllib.parse import parse_qs

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

SCENARIOS = scenarios_demo()
EQ_BR = SCENARIOS["equipement_br"]                     # exige la BR
TEC_ECHUE = SCENARIOS["technicien_br_echue"]           # BR échue
TEC_VALIDE = SCENARIOS["technicien_br_valide"]
SANS_RESERVE = SCENARIOS["controle_a_jour"]
TECHNICIEN = TEC_VALIDE
NATURE = "Installations électriques (T420)"
# Plus de 80 caractères : le titre de l'OT n'en reprend que 80 (Controles.interne.texteCourtReserve).
LONGUE = "Différentiel 30 mA du tableau divisionnaire TD-3 à remplacer : déclenchement mesuré trop lent (45 ms)"
COURTE = "Schéma unifilaire à mettre à jour"

APPEL_JS = """async ([module, fonction, arguments_]) => {
  const cible = { Controles, Ordres }[module];
  try { return 'accepté:' + JSON.stringify(await cible[fonction](...arguments_)); }
  catch (erreur) { return (erreur instanceof Donnees.ErreurValidation ? 'refus:' : 'erreur:') + erreur.message; }
}"""

FORMULAIRE = "#form-nouvel-ot "
CREER_OT = ".controles-reserve[data-reserve='%s'] .controles-reserve-creer-ot"
VOIR_OT = ".controles-reserve[data-reserve='%s'] .controles-reserve-voir-ot"


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def propre(ligne):
    return {cle: brut(valeur) for cle, valeur in ligne.items()}


def reserves_de(dossier, controle_id):
    return [propre(r) for r in lire_csv(dossier, "reserves_controle.csv") if brut(r["controle_id"]) == controle_id]


def fr(date):
    return date.strftime("%d/%m/%Y")


def titre_attendu(texte):
    return "Levée de la réserve — " + texte[:80].rstrip()


def travail_attendu(texte, date, nature):
    return "%s\n\nContrôle du %s : %s" % (texte, fr(date), nature)


def parametres(adresse):
    """{ nom: valeur } de la partie après « ? » d'une adresse #/ot/nouveau?… (chaque nom une fois)."""
    chemin, _, requete = adresse.partition("?")
    lus = parse_qs(requete, keep_blank_values=True)
    return chemin, {nom: valeurs[0] for nom, valeurs in lus.items()}


class CasReservesOt(CasNavigateur):

    def appeler(self, module, fonction, *arguments):
        resultat = self.page.evaluate(APPEL_JS, [module, fonction, list(arguments)])
        self.assertTrue(resultat.startswith("accepté:"), resultat)
        return json.loads(resultat[len("accepté:"):])

    def aujourdhui(self):
        return datetime.date.fromisoformat(self.page.evaluate("Donnees.aujourdhui()"))

    def aller(self, route):
        self.page.evaluate("(route) => { location.hash = route; }", route)

    def attendre_fiche(self, controle_id):
        self.page.wait_for_selector(".controles-fiche .controles-reserves[data-controle='%s']" % controle_id)

    def attendre_toast(self, texte):
        self.page.wait_for_function("(t) => document.getElementById('toast').textContent.includes(t)", arg=texte)

    def toast(self):
        return self.page.evaluate("() => { const t = document.getElementById('toast'); "
                                  "return [t.textContent.trim(), t.className]; }")

    def boutons(self, reserve):
        return self.page.eval_on_selector_all(".controles-reserve[data-reserve='%s'] button" % reserve,
                                              "l => l.map((b) => b.dataset.action + ':' + b.textContent.trim())")

    def ouvrir_formulaire(self, reserve):
        """Clic sur « Créer un OT » de la réserve : le formulaire de l'OT, pré-rempli."""
        self.page.click(CREER_OT % reserve)
        self.page.wait_for_selector(FORMULAIRE + "[name=titre]")

    def formulaire(self):
        return {nom: self.page.input_value(FORMULAIRE + "[name=%s]" % nom)
                for nom in ("equipement_id", "titre", "type", "travail_a_faire", "technicien_id")}

    def creer(self):
        """« Créer » du formulaire, puis l'identifiant de l'OT ouvert ensuite."""
        self.page.click(FORMULAIRE + "button[type=submit]")
        self.page.wait_for_function("() => /^#\\/ot\\/OT-/.test(location.hash)")
        return self.page.evaluate("decodeURIComponent(location.hash.slice('#/ot/'.length))")


# ---------------------------------------------------------------------------
# Serveur : CSV relus sur le disque
# ---------------------------------------------------------------------------

class TestServeur(CasReservesOt):

    def ouvrir(self, serveur, route):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    def controle_avec_reserves(self, equipement, textes, date):
        """Contrôle créé par le test sur `equipement`, réserves relevées le `date` → (contrôle, [identifiants])."""
        controle = self.appeler("Controles", "creerControle", {"equipement_id": equipement, "nature": NATURE,
                                                               "periodicite_mois": "12"})
        ids = self.appeler("Controles", "ajouterReserves", controle, {"date_controle": date.isoformat(),
                                                                      "texte": "\n".join(textes)})
        self.assertEqual(len(ids), len(textes))
        return controle, ids

    def test_creer_un_ot_depuis_une_reserve_le_relie_et_la_carte_le_montre(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/controles")
            d1 = self.aujourdhui() - datetime.timedelta(days=10)
            controle, (longue, courte) = self.controle_avec_reserves(EQ_BR, [LONGUE, COURTE], d1)
            ordres_avant = (dossier / "ordres_travail.csv").read_bytes()
            nombre_avant = len(lire_csv(dossier, "ordres_travail.csv"))
            self.aller("#/controles/" + controle)
            self.attendre_fiche(controle)

            # Chaque réserve ouverte : « Lever », « Modifier » (boutons inchangés), puis le lien « Créer un OT »
            for reserve in (longue, courte):
                self.assertEqual(self.boutons(reserve), ["lever:Lever", "modifier:Modifier"])
                self.assertEqual(page.inner_text(CREER_OT % reserve).strip(), "Créer un OT")
                self.assertEqual(page.locator(VOIR_OT % reserve).count(), 0)
            chemin, lus = parametres(page.get_attribute(CREER_OT % longue, "href"))
            self.assertEqual(chemin, "#/ot/nouveau")
            self.assertEqual(lus, {"equipement": EQ_BR, "type": "réglementaire", "titre": titre_attendu(LONGUE),
                                   "travail": travail_attendu(LONGUE, d1, NATURE), "reserve": longue})
            self.assertLessEqual(len(lus["titre"]), len("Levée de la réserve — ") + 80)

            # Le formulaire pré-rempli ; rien n'est créé sans « Créer »
            self.ouvrir_formulaire(longue)
            self.assertEqual(self.formulaire(), {"equipement_id": EQ_BR, "titre": titre_attendu(LONGUE),
                                                 "type": "réglementaire", "travail_a_faire": travail_attendu(LONGUE, d1, NATURE),
                                                 "technicien_id": ""})
            self.assertEqual((dossier / "ordres_travail.csv").read_bytes(), ordres_avant)

            # RG8 suivie : l'équipement exige la BR, le technicien à la BR échue est refusé, rien n'est écrit
            page.select_option(FORMULAIRE + "[name=technicien_id]", TEC_ECHUE)
            page.click(FORMULAIRE + "button[type=submit]")
            self.attendre_toast("Affectation refusée")
            self.assertEqual(page.evaluate("location.hash.split('?')[0]"), "#/ot/nouveau")
            self.assertEqual((dossier / "ordres_travail.csv").read_bytes(), ordres_avant)
            self.assertEqual([r["ot_id"] for r in reserves_de(dossier, controle)], ["", ""])

            # Technicien habilité : l'OT est créé, puis relié à la réserve
            page.select_option(FORMULAIRE + "[name=technicien_id]", TEC_VALIDE)
            ot_id = self.creer()
            self.attendre_toast("Ordre de travail %s créé et relié à la réserve." % ot_id)
            self.assertIn("succes", self.toast()[1].split())
            ordres = [propre(o) for o in lire_csv(dossier, "ordres_travail.csv")]
            self.assertEqual(len(ordres), nombre_avant + 1)                    # un seul OT, celui du clic
            ot = next(o for o in ordres if o["id"] == ot_id)
            self.assertEqual((ot["equipement_id"], ot["type"], ot["origine"], ot["statut"], ot["technicien_id"]),
                             (EQ_BR, "réglementaire", "manuel", "Créé", TEC_VALIDE))
            self.assertEqual((ot["titre"], ot["travail_a_faire"]), (titre_attendu(LONGUE), travail_attendu(LONGUE, d1, NATURE)))
            self.assertEqual(ot.get("habilitation_requise", ""), "")          # aucune exigence propre à l'OT
            self.assertEqual({r["id"]: r["ot_id"] for r in reserves_de(dossier, controle)}, {longue: ot_id, courte: ""})
            reliees = [j["action"] for j in lire_csv(dossier, "journal.csv")
                       if j["table"] == "reserves_controle" and brut(j["id_ligne"]) == longue]
            self.assertTrue(reliees[-1].endswith("reliée à " + ot_id), reliees)

            # La carte montre l'OT lié et « Voir l'OT » ; l'autre réserve garde « Créer un OT »
            self.aller("#/controles/" + controle)
            self.attendre_fiche(controle)
            meta = page.eval_on_selector(".controles-reserve[data-reserve='%s'] .controles-reserve-meta" % longue,
                                         "p => p.textContent.replace(/\\s+/g, ' ').trim()")
            self.assertIn("OT lié : %s Créé" % ot_id, meta)
            self.assertEqual(page.inner_text(VOIR_OT % longue).strip(), "Voir l'OT")
            self.assertEqual(page.get_attribute(VOIR_OT % longue, "href"), "#/ot/" + ot_id)
            self.assertEqual(page.locator(CREER_OT % longue).count(), 0)
            self.assertEqual(page.locator(CREER_OT % courte).count(), 1)
            self.assertEqual(self.boutons(longue), ["lever:Lever", "modifier:Modifier"])
            actions = page.eval_on_selector_all(".controles-historique .controles-action",
                                                "l => l.map((e) => e.textContent.trim())")
            self.assertIn("Reliée à %s" % ot_id, actions)
            page.click(VOIR_OT % longue)
            page.wait_for_function("(id) => location.hash === '#/ot/' + id", arg=ot_id)

    def test_lien_impossible_l_ot_reste_cree_et_le_toast_le_dit(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/controles")
            d1 = self.aujourdhui() - datetime.timedelta(days=10)
            controle, (premiere, deuxieme) = self.controle_avec_reserves(EQ_BR, [COURTE, LONGUE], d1)
            ailleurs = self.appeler("Ordres", "creer", {"equipement_id": EQ_BR, "titre": "OT déjà prévu (T420)",
                                                        "type": "réglementaire", "priorite": "P3"})
            self.aller("#/controles/" + controle)
            self.attendre_fiche(controle)
            adresse_deuxieme = page.get_attribute(CREER_OT % deuxieme, "href")

            # Réserve reliée ailleurs entre l'ouverture du formulaire et « Créer »
            self.ouvrir_formulaire(premiere)
            self.appeler("Controles", "lierOtAReserve", premiere, ailleurs)
            nombre = len(lire_csv(dossier, "ordres_travail.csv"))
            ot_id = self.creer()
            self.attendre_toast("OT %s créé, mais la réserve n'a pas pu lui être reliée : Cette réserve est déjà reliée à %s."
                                % (ot_id, ailleurs))
            self.assertIn("attention", self.toast()[1].split())
            self.assertEqual(len(lire_csv(dossier, "ordres_travail.csv")), nombre + 1)
            self.assertTrue(any(brut(o["id"]) == ot_id for o in lire_csv(dossier, "ordres_travail.csv")))
            self.assertEqual({r["id"]: r["ot_id"] for r in reserves_de(dossier, controle)}, {premiere: ailleurs, deuxieme: ""})

            # Réserve levée entre-temps : l'OT est créé, la réserve reste levée sans OT
            self.appeler("Controles", "leverReserve", deuxieme, {"date": d1.isoformat(), "commentaire": "Refait (T420)"})
            self.aller(adresse_deuxieme)
            self.page.wait_for_function("(t) => { const c = document.querySelector('#form-nouvel-ot [name=titre]'); "
                                        "return c && c.value === t; }", arg=titre_attendu(LONGUE))
            second = self.creer()
            self.attendre_toast("OT %s créé, mais la réserve n'a pas pu lui être reliée : Cette réserve est levée : aucun OT "
                                "ne peut plus lui être relié." % second)
            self.assertEqual(len(lire_csv(dossier, "ordres_travail.csv")), nombre + 2)
            reserve = next(r for r in reserves_de(dossier, controle) if r["id"] == deuxieme)
            self.assertEqual((reserve["levee"], reserve["ot_id"]), ("1", ""))


# ---------------------------------------------------------------------------
# Démo (file://)
# ---------------------------------------------------------------------------

class TestDemo(CasReservesOt):

    def ouvrir_demo(self, profil, technicien_id=""):
        preregler_profil(self.contexte, profil, technicien_id=technicien_id)
        self.page.goto((RACINE / "index.html").resolve().as_uri())
        self.page.click("#btn-demo")
        attendre_pret(self.page)

    def reserves_ouvertes(self, textes):
        """Deux réserves relevées au dernier contrôle de SANS_RESERVE, la seconde reliée à un OT créé pour elle →
        (date du contrôle, nature, réserve sans OT, réserve avec OT, OT)."""
        controle = self.page.evaluate("(id) => Donnees.trouver('controles_reglementaires', id)", SANS_RESERVE)
        date = datetime.date.fromisoformat(controle["derniere_date"][:10])
        sans, avec = self.appeler("Controles", "ajouterReserves", SANS_RESERVE,
                                  {"date_controle": date.isoformat(), "texte": "\n".join(textes)})
        ot = self.appeler("Ordres", "creer", {"equipement_id": controle["equipement_id"], "titre": "OT de la réserve (T420)",
                                              "type": "réglementaire", "priorite": "P3"})
        self.appeler("Controles", "lierOtAReserve", avec, ot)
        return date, controle["nature"], sans, avec, ot

    def test_ecran_en_anglais_titre_et_travail_dans_la_langue_de_l_installation(self):
        page = self.page
        self.contexte.add_init_script("try { localStorage.setItem('prevo.langue', 'en'); } catch (erreur) {}")
        self.ouvrir_demo("responsable")
        self.assertEqual((page.evaluate("I18n.langue"), page.evaluate("App.profil.type")), ("en", "responsable"))
        date, nature, sans, avec, ot = self.reserves_ouvertes([COURTE, "Extincteur à recharger"])
        self.aller("#/controles/" + SANS_RESERVE)
        self.attendre_fiche(SANS_RESERVE)
        self.assertEqual(page.inner_text(CREER_OT % sans).strip(), "Create a WO")
        self.assertEqual(page.locator(CREER_OT % avec).count(), 0)
        self.assertEqual(page.inner_text(VOIR_OT % avec).strip(), "View the WO")
        self.assertEqual(page.get_attribute(VOIR_OT % avec, "href"), "#/ot/" + ot)

        # Titre et travail écrits en français, la langue de la démo (D156), l'écran restant en anglais
        nombre = page.evaluate("Donnees.lignes('ordres_travail').length")
        self.ouvrir_formulaire(sans)
        valeurs = self.formulaire()
        self.assertEqual((valeurs["titre"], valeurs["travail_a_faire"], valeurs["type"]),
                         (titre_attendu(COURTE), travail_attendu(COURTE, date, nature), "réglementaire"))
        self.assertEqual(page.inner_text(FORMULAIRE + "button[type=submit]").strip(), "Create the WO")
        self.assertEqual(page.evaluate("Donnees.lignes('ordres_travail').length"), nombre)       # rien sans « Créer »
        nouvel = self.creer()
        self.attendre_toast("Work order %s created and linked to the finding." % nouvel)
        self.assertEqual(page.evaluate("Donnees.lignes('ordres_travail').length"), nombre + 1)
        ligne = page.evaluate("(id) => Donnees.trouver('reserves_controle', id)", sans)
        self.assertEqual(ligne["ot_id"], nouvel)
        self.assertEqual(page.evaluate("(id) => Donnees.trouver('ordres_travail', id).titre", nouvel), titre_attendu(COURTE))

    def test_technicien_ni_creer_ni_voir_l_ot(self):
        page = self.page
        self.ouvrir_demo("technicien", TECHNICIEN)
        self.assertEqual(page.evaluate("App.profil.type"), "technicien")
        _, _, sans, avec, _ = self.reserves_ouvertes([COURTE, "Extincteur à recharger"])
        self.aller("#/controles/" + SANS_RESERVE)
        self.attendre_fiche(SANS_RESERVE)
        for reserve in (sans, avec):
            self.assertEqual(page.locator(".controles-reserve[data-reserve='%s']" % reserve).count(), 1)
            self.assertEqual(page.locator(CREER_OT % reserve).count(), 0)
            self.assertEqual(page.locator(VOIR_OT % reserve).count(), 0)
        self.assertEqual(page.locator(".controles-reserves a.btn").count(), 0)


if __name__ == "__main__":
    unittest.main()
