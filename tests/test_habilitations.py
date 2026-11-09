"""Tests des habilitations à l'écran, 2.2 (equipe-habilitations.js, T432 ; CS172, CS176, CS179 ; CONCEPTION-L2-L3
§6.3, réponses provisoires n° 2 et 3 de QUESTIONS-L2-L6).

Serveur Prévo (serveur.py) sur une copie temporaire du jeu de démo ; CSV et documents relus sur le disque. Les
techniciens viennent des rôles de scenarios_demo() ou sont créés par le test ; dates fixes.

    type_h02          CS172 : liste du type (« Autre (saisie libre) » d'abord et par défaut ; groupes Électricité,
                      CACES, Autorisation de conduite) ; choisir H02 pré-remplit le recyclage (36), laisse l'intitulé
                      vide avec l'aide « Le symbole du titre : … » et ouvre l'encart du type (recommandation, relu le
                      08/11/2026, réglementation française, durée en clair, délivré par ; contenu en lang="fr") ;
                      obtenue le 15/01/2024 → échéance 15/01/2027, modifiable : tapée à la main, elle n'est plus
                      recalculée ; vidée, elle suit de nouveau ; ligne écrite (type, nature, recyclage, justificatif
                      dans documents/) ; carte : « Recyclage : 36 mois » et « recommandation » (NF C 18-510), type du
                      catalogue, lien du justificatif (nouvel onglet) qui sert le document ; correction (type
                      présélectionné, échéance qui suit l'obtention), renouvellement (recyclage repris, échéance depuis
                      aujourd'hui) ; recyclage changé : « recyclage saisi ; le catalogue propose 36 mois » ;
    autorisation      CS179 : rappel sur le CACES sans autorisation de conduite ; l'autorisation de conduite (H14) est
                      un type distinct (son texte, pas de recyclage) ; « Reprendre le justificatif de : CACES R489
                      (obtenu le …) » ; la ligne écrite porte le document du CACES ; rappel parti ;
    justificatif      lien pour le responsable et pour le technicien sur SA fiche seulement (sur une autre fiche :
                      « justificatif joint, visible par le responsable », nom du document absent de la page) ;
    comptes           mode serveur avec comptes (T445) : le serveur refuse le document au technicien (403), sa
                      fiche ne montre donc aucun lien, seulement « justificatif joint, visible par le responsable ».

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_habilitations.py" -v
"""
import csv
import datetime
import io
import json
import re
import unittest
from pathlib import Path

from commun import COMPTES_DE_TEST, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

SCENARIOS = scenarios_demo()
TEC_BR_VALIDE = SCENARIOS["technicien_br_valide"]
TEC_BR_ECHUE = SCENARIOS["technicien_br_echue"]
TEC_CACES_SANS_AUTORISATION = SCENARIOS["technicien_caces_sans_autorisation"]

PDF = b"%PDF-1.4\n% justificatif de test (T432)\n%%EOF\n"
FENETRE = "dialog[open] "
RAPPEL_CACES = ("Le CACES justifie l'autorisation de conduite, il ne la remplace pas : enregistrez aussi "
                "l'autorisation de conduite de l'employeur.")
TEXTE_AUTORISATION = ("L'autorisation de conduite est délivrée par l'employeur : c'est elle qui est obligatoire. "
                      "Le CACES en est un justificatif : joignez-le.")
JUSTIFICATIF_FERME = "justificatif joint, visible par le responsable"
PHRASE = "Prévo est une aide au suivi ; la responsabilité reste celle de l'employeur."

# Appel d'une fonction d'Equipe ; `fichier` (facultatif) : { nom, octets } devient un File PDF ajouté en dernier.
APPEL_JS = """async ([fonction, arguments_, fichier]) => {
  const args = arguments_.slice();
  if (fichier) args.push(new File([new Uint8Array(fichier.octets)], fichier.nom, { type: 'application/pdf' }));
  try { return 'accepté:' + JSON.stringify(await Equipe[fonction](...args)); }
  catch (erreur) { return (erreur instanceof Donnees.ErreurValidation ? 'refus:' : 'erreur:') + erreur.message; }
}"""
# Document ouvert par un lien de la page : { statut, octets }.
LIRE_LIEN_JS = """async (selecteur) => {
  const reponse = await fetch(document.querySelector(selecteur).href);
  return { statut: reponse.status, octets: Array.from(new Uint8Array(await reponse.arrayBuffer())) };
}"""
# Document demandé par son nom à l'adresse du stockage : statut HTTP.
STATUT_DOCUMENT_JS = """async (nom) => (await fetch(await App.adaptateur.urlDocument(nom))).status"""


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def valeurs(ligne, *champs):
    return tuple(brut(ligne[champ]) for champ in champs)


def date_fr(iso):
    return datetime.date.fromisoformat(iso).strftime("%d/%m/%Y")


def ligne_du(dossier, technicien_id, **criteres):
    """Ligne d'habilitation du technicien dont les colonnes valent `criteres`."""
    return next(h for h in lire_csv(dossier, "habilitations.csv") if h["technicien_id"] == technicien_id
                and all(brut(h[c]) == v for c, v in criteres.items()))


def carte_ligne(habilitation_id):
    return ".equipe-carte-habilitations li[data-habilitation='%s']" % habilitation_id


class CasHabilitations(CasNavigateur):

    def ouvrir(self, serveur, route, profil="responsable", technicien_id="", page=None):
        page = page or self.page
        page.set_viewport_size({"width": 1280, "height": 900})
        preregler_profil(page.context, profil, technicien_id=technicien_id)
        page.goto(serveur.url + "/" + route)
        attendre_pret(page)
        page.wait_for_load_state("networkidle")

    def autre_page(self):
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 900})
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        page = contexte.new_page()
        self.surveiller(page)
        return page

    def aller(self, route, page=None):
        (page or self.page).evaluate("(route) => { location.hash = route; }", route)

    def attendre_fiche(self, technicien_id, page=None):
        (page or self.page).wait_for_selector(".equipe-fiche[data-technicien='%s'] .equipe-carte-habilitations" % technicien_id)

    def reafficher(self, technicien_id, page=None):
        page = page or self.page
        page.evaluate("document.getElementById('contenu').textContent = ''")
        page.evaluate("App.reafficher()")
        self.attendre_fiche(technicien_id, page)

    def accepte(self, fonction, *arguments, fichier=None, page=None):
        resultat = (page or self.page).evaluate(APPEL_JS, [fonction, list(arguments), fichier])
        self.assertTrue(resultat.startswith("accepté:"), resultat)
        return json.loads(resultat[len("accepté:"):])

    def joindre(self, technicien_id, habilitation, nom_fichier="titre.pdf", page=None):
        """Justificatif écrit par l'API (responsable) et posé sur la ligne ; rend le nom enregistré."""
        nom = self.accepte("ecrireJustificatif", technicien_id, brut(habilitation["intitule"]),
                           brut(habilitation["date_obtention"]), fichier={"nom": nom_fichier, "octets": list(PDF)}, page=page)
        self.accepte("modifierHabilitation", habilitation["id"], {"justificatif": nom}, page=page)
        return nom

    def attendre_toast(self, morceau):
        self.page.wait_for_function("(texte) => document.getElementById('toast').textContent.includes(texte)", arg=morceau)

    def valider(self):
        self.page.click(FENETRE + ".fenetre-actions .btn-primaire")

    def annuler(self):
        self.page.click(FENETRE + ".fenetre-actions .btn-fantome")
        self.page.wait_for_selector("dialog[open]", state="detached")

    def echeance_affichee(self):
        return self.page.evaluate("UI.dateFr(document.querySelector('dialog[open] [name=date_echeance]').value)")


# ---------------------------------------------------------------------------
# CS172 : type du catalogue, échéance calculée et modifiable, recommandation, justificatif
# ---------------------------------------------------------------------------

class TestTypeEtEcheance(CasHabilitations):

    def test_type_h02_obtenue_15_01_2024_echeance_15_01_2027_modifiable_carte_et_justificatif(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/equipe")
            tec = self.accepte("creerTechnicien", {"nom": "Écran", "prenom": "Essai"})
            self.aller("#/equipe/" + tec)
            self.attendre_fiche(tec)
            page.click("#equipe-ajouter-habilitation")
            liste = FENETRE + "[name=catalogue_id]"
            page.wait_for_selector(liste)

            # Liste du type : « Autre (saisie libre) » d'abord et par défaut, puis une famille par groupe
            premier = page.eval_on_selector(liste, "s => [s.options[0].value, s.options[0].textContent.trim(), s.value]")
            self.assertEqual(premier, ["", "Autre (saisie libre)", ""])
            groupes = dict(page.eval_on_selector_all(liste + " optgroup",
                                                     "gs => gs.map(g => [g.label, Array.from(g.children).map(o => o.value)])"))
            self.assertEqual(list(groupes), ["Électricité", "CACES", "Autorisation de conduite"])
            self.assertIn("H14", groupes["Autorisation de conduite"])
            self.assertNotIn("H14", groupes["CACES"])
            self.assertEqual(page.inner_text(liste + " option[value=H02]").strip(),
                             "H02 · Habilitation électrique – électricien — recyclage 36 mois (recommandation)")
            self.assertTrue(page.is_hidden(FENETRE + ".equipe-type-encart"))
            self.assertEqual(page.inner_text(FENETRE + ".equipe-principe").strip(), PHRASE)

            # H02 : recyclage pré-rempli, intitulé laissé au symbole du titre, encart du type
            page.select_option(liste, "H02")
            self.assertEqual(page.input_value(FENETRE + "[name=recyclage_mois]"), "36")
            self.assertEqual(page.input_value(FENETRE + "[name=intitule]"), "")
            aide = page.inner_text(FENETRE + ".equipe-aide-symbole")
            self.assertTrue(aide.startswith("Le symbole du titre : ") and "BR" in aide, aide)
            encart = page.inner_text(FENETRE + ".equipe-type-encart")
            for morceau in ("recommandation · relu le 08/11/2026 · réglementation française", "NF C 18-510",
                            "3 ans (périodicité de recyclage recommandée", "Employeur (titre d'habilitation)"):
                with self.subTest(encart=morceau):
                    self.assertIn(morceau, encart)
            self.assertTrue(page.eval_on_selector_all(FENETRE + ".equipe-type-encart [data-catalogue]",
                                                      "es => es.length > 0 && es.every(e => e.closest('[lang=fr]'))"))
            liens = page.eval_on_selector_all(FENETRE + ".equipe-type-liens a", "as => as.map(a => [a.target, a.rel])")
            self.assertTrue(liens and all(lien == ["_blank", "noopener noreferrer"] for lien in liens), liens)

            # CS172 : obtenue le 15/01/2024 → échéance 15/01/2027 ; modifiable, puis plus recalculée ; vidée, elle suit
            page.fill(FENETRE + "[name=intitule]", "BR")
            page.fill(FENETRE + "[name=date_obtention]", "2024-01-15")
            self.assertEqual(self.echeance_affichee(), "15/01/2027")
            page.fill(FENETRE + "[name=date_echeance]", "2027-01-10")
            page.fill(FENETRE + "[name=date_obtention]", "2024-02-01")
            self.assertEqual(self.echeance_affichee(), "10/01/2027")
            page.fill(FENETRE + "[name=recyclage_mois]", "24")
            self.assertEqual(self.echeance_affichee(), "10/01/2027")
            page.fill(FENETRE + "[name=date_echeance]", "")
            page.fill(FENETRE + "[name=recyclage_mois]", "36")
            page.fill(FENETRE + "[name=date_obtention]", "2024-01-15")
            self.assertEqual(self.echeance_affichee(), "15/01/2027")
            page.set_input_files(FENETRE + "input[type=file]",
                                 files=[{"name": "titre.pdf", "mimeType": "application/pdf", "buffer": PDF}])
            self.valider()
            self.attendre_toast("Habilitation ajoutée")

            ligne = ligne_du(serveur.dossier, tec, intitule="BR")
            self.assertEqual(valeurs(ligne, "date_obtention", "date_echeance", "recyclage_mois", "catalogue_id", "nature_source"),
                             ("2024-01-15", "2027-01-15", "36", "H02", "recommandation"))
            nom = brut(ligne["justificatif"])
            self.assertRegex(nom, r"-habilitation-%s-BR-2024-01-15\.pdf$" % tec)
            self.assertEqual((serveur.dossier / "documents" / nom).read_bytes(), PDF)

            # Carte : recyclage et « recommandation » (NF C 18-510), type du catalogue, justificatif qui s'ouvre
            element = carte_ligne(ligne["id"])
            page.wait_for_selector(element + " a.equipe-justificatif-lien")
            texte = page.inner_text(element)
            self.assertIn("Recyclage : 36 mois", texte)
            self.assertEqual(page.inner_text(element + " .equipe-recyclage .badge").strip(), "recommandation")
            self.assertIn("Type : Habilitation électrique – électricien (catalogue Prévo)", texte)
            self.assertNotIn("le catalogue propose", texte)
            self.assertEqual(page.eval_on_selector(element + " a.equipe-justificatif-lien", "a => [a.target, a.textContent.trim()]"),
                             ["_blank", nom])
            lu = page.evaluate(LIRE_LIEN_JS, element + " a.equipe-justificatif-lien")
            self.assertEqual((lu["statut"], bytes(lu["octets"])), (200, PDF))
            self.assertIn(PHRASE, page.inner_text(".equipe-carte-habilitations .equipe-principe"))

            # Correction : type présélectionné, justificatif actuel nommé ; l'échéance (égale au calcul) suit l'obtention
            page.click("button[data-action='corriger'][data-habilitation='%s']" % ligne["id"])
            page.wait_for_selector(liste)
            self.assertEqual((page.input_value(liste), page.input_value(FENETRE + "[name=recyclage_mois]"),
                              page.input_value(FENETRE + "[name=date_echeance]")), ("H02", "36", "2027-01-15"))
            self.assertIn("Justificatif actuel : " + nom, page.inner_text(FENETRE + ".champ[data-champ=justificatif]"))
            page.fill(FENETRE + "[name=date_obtention]", "2024-03-01")
            self.assertEqual(self.echeance_affichee(), "01/03/2027")
            self.annuler()

            # Renouvellement : ni type ni intitulé à choisir, recyclage repris, échéance = aujourd'hui + 36 mois
            page.click("button[data-action='renouveler'][data-habilitation='%s']" % ligne["id"])
            page.wait_for_selector(FENETRE + "[name=date_echeance]")
            self.assertEqual(page.locator(FENETRE + "[name=catalogue_id], " + FENETRE + "[name=intitule]").count(), 0)
            self.assertEqual(page.input_value(FENETRE + "[name=recyclage_mois]"), "36")
            self.assertEqual(page.input_value(FENETRE + "[name=date_echeance]"),
                             page.evaluate("Equipe.echeanceProposee(Donnees.aujourdhui(), 36)"))
            self.assertIn("recommandation", page.inner_text(FENETRE + ".equipe-type-encart"))
            self.annuler()

            # Recyclage saisi différent de la durée du type
            self.accepte("modifierHabilitation", ligne["id"], {"recyclage_mois": "24"})
            self.reafficher(tec)
            texte = page.inner_text(carte_ligne(ligne["id"]))
            self.assertIn("Recyclage : 24 mois", texte)
            self.assertIn("recyclage saisi ; le catalogue propose 36 mois", texte)

    def test_demo_br_du_technicien_recyclage_nf_c_18_510_recommandation(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/equipe/" + TEC_BR_VALIDE, profil="technicien", technicien_id=TEC_BR_VALIDE)
            self.attendre_fiche(TEC_BR_VALIDE)
            br = ligne_du(serveur.dossier, TEC_BR_VALIDE, intitule="BR")
            self.assertEqual(valeurs(br, "catalogue_id", "nature_source"), ("H02", "recommandation"))
            element = carte_ligne(br["id"])
            self.assertIn("Recyclage : 36 mois", self.page.inner_text(element + " .equipe-recyclage"))
            self.assertEqual(self.page.inner_text(element + " .equipe-recyclage .badge").strip(), "recommandation")
            self.assertIn("aucun justificatif", self.page.inner_text(element))
            self.assertEqual(self.page.locator(".equipe-fiche [name], .equipe-fiche button[data-action]").count(), 0)


# ---------------------------------------------------------------------------
# CS179 : autorisation de conduite distincte du CACES, qui en est un justificatif
# ---------------------------------------------------------------------------

class TestAutorisationDeConduite(CasHabilitations):

    def test_autorisation_type_distinct_justificatif_du_caces_repris_rappel_parti(self):
        page = self.page
        tec = TEC_CACES_SANS_AUTORISATION
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/equipe/" + tec)
            self.attendre_fiche(tec)
            caces = ligne_du(serveur.dossier, tec, catalogue_id="H12")
            self.assertIn(RAPPEL_CACES, page.inner_text(carte_ligne(caces["id"]) + " .equipe-rappel-caces"))
            self.assertEqual(page.locator(".equipe-rappel-caces").count(), 1)
            nom = self.joindre(tec, caces, "caces.pdf")
            self.reafficher(tec)
            page.wait_for_selector(carte_ligne(caces["id"]) + " a.equipe-justificatif-lien")

            page.click("#equipe-ajouter-habilitation")
            liste = FENETRE + "[name=catalogue_id]"
            reprise = FENETRE + ".champ[data-champ=justificatif_repris]"
            page.wait_for_selector(liste)
            self.assertTrue(page.is_hidden(reprise))
            # H14 : son intitulé, aucun recyclage, son texte ; « Reprendre le justificatif de : CACES R489 (obtenu le …) »
            page.select_option(liste, "H14")
            self.assertEqual(page.input_value(FENETRE + "[name=intitule]"), "Autorisation de conduite (employeur)")
            self.assertEqual(page.input_value(FENETRE + "[name=recyclage_mois]"), "")
            self.assertIn(TEXTE_AUTORISATION, page.inner_text(FENETRE + ".equipe-type-encart"))
            self.assertIn("obligation réglementaire", page.inner_text(FENETRE + ".equipe-type-encart .equipe-type-source"))
            self.assertTrue(page.is_visible(reprise))
            self.assertIn("Reprendre le justificatif de :", page.inner_text(reprise))
            options = page.eval_on_selector_all(reprise + " option", "os => os.map(o => [o.value, o.textContent.trim()])")
            self.assertEqual(options, [["", "— aucun —"],
                                       [nom, "%s (obtenu le %s)" % (brut(caces["intitule"]), date_fr(brut(caces["date_obtention"])))]])
            # Un CACES : le rappel, pas de reprise ; intitulé proposé remplacé (il n'avait pas été retouché)
            page.select_option(liste, "H12")
            self.assertIn(RAPPEL_CACES, page.inner_text(FENETRE + ".equipe-type-encart"))
            self.assertTrue(page.is_hidden(reprise))
            self.assertEqual(page.input_value(FENETRE + "[name=intitule]"), "CACES R489")
            self.assertEqual(page.input_value(FENETRE + "[name=recyclage_mois]"), "60")

            page.select_option(liste, "H14")
            self.assertEqual(page.input_value(FENETRE + "[name=recyclage_mois]"), "")
            page.select_option(reprise + " select", nom)
            page.fill(FENETRE + "[name=date_obtention]", "2024-03-01")
            self.assertEqual(page.input_value(FENETRE + "[name=date_echeance]"), "")
            self.valider()
            self.attendre_toast("Habilitation ajoutée")

            autorisation = ligne_du(serveur.dossier, tec, catalogue_id="H14")
            self.assertEqual(valeurs(autorisation, "intitule", "date_obtention", "date_echeance", "recyclage_mois", "justificatif",
                                     "nature_source"),
                             ("Autorisation de conduite (employeur)", "2024-03-01", "", "", nom, "obligation"))
            self.assertEqual(valeurs(ligne_du(serveur.dossier, tec, catalogue_id="H12"), "justificatif"), (nom,))
            page.wait_for_selector(carte_ligne(autorisation["id"]) + " a.equipe-justificatif-lien")
            self.assertEqual(page.locator(".equipe-rappel-caces").count(), 0)
            lu = page.evaluate(LIRE_LIEN_JS, carte_ligne(autorisation["id"]) + " a.equipe-justificatif-lien")
            self.assertEqual((lu["statut"], bytes(lu["octets"])), (200, PDF))


# ---------------------------------------------------------------------------
# Lien du justificatif : responsable, technicien sur sa propre fiche ; comptes (T445)
# ---------------------------------------------------------------------------

class TestJustificatifSelonLeProfil(CasHabilitations):

    def test_justificatif_lien_du_technicien_sur_sa_fiche_seulement(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/equipe")
            sien = ligne_du(serveur.dossier, TEC_BR_VALIDE, intitule="BR")
            autre = ligne_du(serveur.dossier, TEC_BR_ECHUE, intitule="BR")
            nom_sien = self.joindre(TEC_BR_VALIDE, sien)
            nom_autre = self.joindre(TEC_BR_ECHUE, autre)

            page = self.autre_page()
            self.ouvrir(serveur, "#/equipe/" + TEC_BR_VALIDE, profil="technicien", technicien_id=TEC_BR_VALIDE, page=page)
            self.attendre_fiche(TEC_BR_VALIDE, page)
            page.wait_for_selector(carte_ligne(sien["id"]) + " a.equipe-justificatif-lien")
            lu = page.evaluate(LIRE_LIEN_JS, carte_ligne(sien["id"]) + " a.equipe-justificatif-lien")
            self.assertEqual((lu["statut"], bytes(lu["octets"])), (200, PDF))
            self.assertIn(nom_sien, page.inner_text(carte_ligne(sien["id"])))

            self.aller("#/equipe/" + TEC_BR_ECHUE, page)
            self.attendre_fiche(TEC_BR_ECHUE, page)
            element = carte_ligne(autre["id"])
            self.assertIn("Justificatif : " + JUSTIFICATIF_FERME, page.inner_text(element))
            self.assertEqual(page.locator(".equipe-carte-habilitations a.equipe-justificatif-lien").count(), 0)
            self.assertNotIn(nom_autre, page.evaluate("document.getElementById('contenu').innerHTML"))

    def test_comptes_le_technicien_recoit_403_et_ne_voit_aucun_lien(self):
        self.autoriser_erreur(re.compile(r"status of 403"))
        technicien = COMPTES_DE_TEST["technicien"][4]
        with ServeurPrevo(comptes=True) as serveur:
            serveur.poser_session(self.contexte, "responsable")
            self.page.goto(serveur.url + "/#/equipe/" + technicien)
            attendre_pret(self.page)
            self.attendre_fiche(technicien)
            br = ligne_du(serveur.dossier, technicien, intitule="BR")
            nom = self.joindre(technicien, br)
            self.reafficher(technicien)
            self.page.wait_for_selector(carte_ligne(br["id"]) + " a.equipe-justificatif-lien")

            page = self.autre_page()
            serveur.poser_session(page.context, "technicien")
            page.goto(serveur.url + "/#/equipe/" + technicien)
            attendre_pret(page)
            self.attendre_fiche(technicien, page)
            self.assertEqual(page.evaluate("App.profil.technicienId"), technicien)
            self.assertEqual(page.evaluate(STATUT_DOCUMENT_JS, nom), 403)
            self.assertIn("Justificatif : " + JUSTIFICATIF_FERME, page.inner_text(carte_ligne(br["id"])))
            self.assertEqual(page.locator(".equipe-carte-habilitations a.equipe-justificatif-lien").count(), 0)


if __name__ == "__main__":
    unittest.main()
