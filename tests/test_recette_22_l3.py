"""Recette du L3 de la 2.2 « habilitations, blocage RG8 » (T449 ; CDC CS172, CS175 côté Habilitations, CS178, CS179,
CS180 ; décisions D182, D185, D186, D191 ; QUESTIONS-L2-L6 : motif obligatoire (Q7), réponses PROVISOIRES n° 2 et 3,
à confirmer par Nicolas). De bout en bout, à l'écran, comme un responsable puis comme un technicien ; les tests de
chaque partie (test_habilitations*, test_rg8_*, test_droits_format4, test_principe_suivi, test_planning) ne sont pas
recopiés ici.

Le parcours (CasRecette.parcours), le même dans trois modes :
    TestParcoursServeur        serveur.py sur une COPIE du jeu de démo, sans comptes (portée « ce PC ») ; données et
                               documents relus sur le disque ; le technicien : un autre contexte, son profil ;
    TestParcoursServeurComptes la même chose avec les trois comptes de test (session du responsable), puis la session
                               du technicien : refus 403 du serveur à l'écriture des habilitations et aux justificatifs
                               (réponses provisoires n° 2 et 3, T445) ;
    TestParcoursDemo           index.html en file://, « Essayer avec les données de démo » ; données en mémoire ; le
                               technicien : changement de profil dans la même page (recharger perdrait la démo).
Étapes, profil Responsable (J = Donnees.aujourdhui(), D = premier jour ouvré à J + 14) :
    - CS172, CS175 : technicien A créé par « Nouveau technicien » ; « Ajouter une habilitation » : phrase D182, jamais
      « conforme » ; type H02 du catalogue : recyclage 36 mois, « recommandation » (NF C 18-510) ; obtenue le
      15/01/2024 → échéance 15/01/2027, modifiable (tapée, elle n'est plus recalculée ; vidée, elle suit de nouveau) ;
      justificatif PDF joint ; la carte le dit et le lien du justificatif sert le document ;
    - CS179 : CACES R489 (H12) avec son justificatif : rappel « le CACES justifie l'autorisation de conduite… » ;
      l'autorisation de conduite (H14) est un autre type (groupe à part, obligation, sans recyclage), son justificatif
      repris du CACES ; le rappel s'en va ;
    - CS172 : « Corriger » : l'échéance de la BR tapée à la main (J + 7), écrite telle quelle ; vue « à renouveler » :
      la ligne, la phrase D182, jamais « conforme » ;
    - technicien B : BR obtenue après D (pas encore obtenue à D) ; technicien C : aucune habilitation ;
    - CS178 (équipement, échue) : nouvel OT sur l'équipement qui exige la BR, A à J + 5 : rien ; à D : refus en
      direct ; la fenêtre ; Annuler n'écrit rien ; passer outre avec motif (bouton inactif sans la case et le motif) :
      l'OT est créé, le journal garde qui (profil, poste), quand, quel OT, quelle habilitation ; la fiche le dit ;
    - CS180 (OT, absente) : un OT sur un équipement sans exigence, préparé ; « Habilitation exigée par l'OT » H0V et A
      à D : refus, fenêtre « Cet OT l'exige (OT) », passer outre, journal ; « Planifier » ne redemande pas ;
    - CS178 au planning (équipement, pas encore obtenue) : « Planifier… » l'OT à BR de la démo sur B à D : la fenêtre ;
      Annuler n'écrit rien ; passer outre : planifié, journal ;
    - CS180 : C, sans aucune habilitation : nouvel OT sur un équipement sans exigence et « Planifier… » de l'OT sans
      exigence de la démo : ni bandeau, ni fenêtre, ni dérogation au journal ; aucun OT sans exigence n'est bloqué,
      quel que soit le technicien (règle Ordres.controleHabilitation sur toute la base).
Puis, profil Technicien (CS178 : aucun moyen de passer outre) : la fiche de l'OT dérogé (bandeau de la dérogation,
ni case ni bouton) ; l'OT de la démo qui exige H0V : ni « Planifier », ni enregistrement de la préparation ; planning
en lecture ; par l'application elle-même : la dérogation est refusée, aucune fenêtre, rien d'écrit ; écran
Habilitations : phrase D182, aucun bouton, écriture refusée par l'application. Avec comptes, en plus : le serveur
refuse au technicien l'écriture de la table habilitations (PUT, ajout : 403, fichier inchangé) et les justificatifs
écrits pendant le parcours (403), qu'il sert au responsable ; la fiche n'a pas de lien. Sans comptes et en démo, le
technicien A ouvre son propre justificatif (QUESTIONS-L2-L6 Q5).

Chaque cas travaille sur une copie du jeu de démo dans un dossier temporaire (serveur), ou en mémoire (démo) : jamais
de données réelles. Identifiants du jeu de démo : rôles de tests/fixtures/demo-scenarios.json ; dates calculées depuis
Donnees.aujourdhui().

Bibliothèque standard + Playwright. Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_recette_22_l3.py" -v
"""
import datetime
import unittest
from pathlib import Path

from commun import COMPTES_DE_TEST, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo, url_fichier
from test_droits_format4 import BOM, REFUS_DOCUMENT, REFUS_TABLE, premiere_ligne, requete
from test_principe_suivi import MOT_CONFORME, PHRASE
from test_rapport import lire_csv

# ---------------------------------------------------------------------------
# Ce que la recette attend
# ---------------------------------------------------------------------------

SCENARIOS = scenarios_demo()
EQ_BR = SCENARIOS["equipement_br"]                     # exige la BR (AE-03)
OT_BR_A_PLANIFIER = SCENARIOS["ot_a_planifier_br"]     # « Préparé », sur l'équipement à BR, sans technicien
OT_SANS_EXIGENCE = SCENARIOS["ot_a_planifier"]         # « Préparé », aucune exigence
OT_EXIGE_H0V = SCENARIOS["ot_habilitation_exigee"]     # « Préparé », H0V exigée par l'OT, sans technicien

PDF_BR = b"%PDF-1.4\n% titre d'habilitation BR (recette T449)\n%%EOF\n"
PDF_CACES = b"%PDF-1.4\n% CACES R489 (recette T449)\n%%EOF\n"
OBTENTION_BR, ECHEANCE_BR = "2024-01-15", "2027-01-15"         # CS172 : 15/01/2024 + 36 mois → 15/01/2027
OBTENTION_CACES, OBTENTION_AUTORISATION = "2023-06-01", "2023-06-15"
MOTIF_NOUVEL_OT = "Électricien habilité du site présent ; consignation faite par lui (recette L3)"
MOTIF_PREPARATION = "Intervention hors tension vérifiée par le chef d'équipe (recette L3)"
MOTIF_PLANNING = "Titre signé le jour même, en attente de la copie (recette L3)"

RAPPEL_CACES = ("Le CACES justifie l'autorisation de conduite, il ne la remplace pas : enregistrez aussi "
                "l'autorisation de conduite de l'employeur.")
TEXTE_AUTORISATION = ("L'autorisation de conduite est délivrée par l'employeur : c'est elle qui est obligatoire. "
                      "Le CACES en est un justificatif : joignez-le.")
JUSTIFICATIF_FERME = "justificatif joint, visible par le responsable"
REFUS_APPLICATION = "Seul le responsable enregistre les habilitations."

FENETRE = "dialog[open] "
DEROGATION = "dialog.ot-fenetre-derogation"
CASE = DEROGATION + " [name=passer_outre]"
CHAMP_MOTIF = DEROGATION + " [name=motif]"
PASSER_OUTRE = DEROGATION + " .ot-passer-outre"
ANNULER = DEROGATION + " .fenetre-actions .btn-fantome"
ZONE = "%s .ot-zone-habilitation"
BANDEAU_DEROGATION = ".ot-bandeau-etat .alerte.attention .alerte-texte"
PLANIFIER_FICHE = ".ot-actions button[data-action='transition'][data-cible='%s']"

# Si location.hash est déjà la route, l'écran est redessiné (App.reafficher), sinon on y va.
ALLER_JS = "(route) => { if (location.hash === route) return App.reafficher(); location.hash = route; return null; }"
LIGNES_JS = "(table) => Donnees.lignes(table).map((ligne) => Object.assign({}, ligne))"
# Un équipement suivi, avec un repère, qui n'exige aucune habilitation.
EQUIPEMENT_SANS_EXIGENCE_JS = """() => Donnees.lignes('equipements').find((e) => String(e.actif) !== '0'
  && e.statut !== 'rebut' && !String(e.habilitation_requise || '').trim() && String(e.repere || '').trim()).id"""
# Appel d'une fonction de l'application (« Equipe.creerTechnicien ») : { accepte } ou { refus, validation, habilitation }.
APPEL_JS = """async ([chemin, arguments_]) => {
  const [objet, fonction] = chemin.split('.');
  try { return { accepte: await eval(objet)[fonction](...arguments_) }; }
  catch (erreur) { return { refus: erreur.message, validation: erreur instanceof Donnees.ErreurValidation,
                            habilitation: Boolean(erreur.habilitation) }; } }"""
# Document ouvert par un lien de la page : { statut, octets }.
LIRE_LIEN_JS = """async (selecteur) => {
  const reponse = await fetch(document.querySelector(selecteur).href);
  return { statut: reponse.status, octets: Array.from(new Uint8Array(await reponse.arrayBuffer())) }; }"""
# CS180 sur toute la base : aucun OT sans exigence n'est bloqué, quel que soit le technicien, à la date donnée.
JAMAIS_BLOQUE_JS = """(date) => {
  const techniciens = Donnees.lignes('techniciens');
  const ordres = Donnees.lignes('ordres_travail');
  const sans = ordres.filter((ot) => !Ordres.habilitationsExigees(ot).length);
  const bloques = [];
  sans.forEach((ot) => techniciens.forEach((t) => { if (Ordres.controleHabilitation(ot, t.id, date).bloque) bloques.push(ot.id + ' / ' + t.id); }));
  return { sans: sans.length, avec: ordres.length - sans.length, techniciens: techniciens.length, bloques }; }"""


def brut(valeur):
    """Valeur d'une cellule (CSV ou mémoire), sans l'apostrophe de protection contre Excel."""
    valeur = "" if valeur is None else str(valeur).strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def propre(ligne):
    return {cle: brut(valeur) for cle, valeur in ligne.items() if cle is not None}


def fr(date):
    return (date if isinstance(date, datetime.date) else datetime.date.fromisoformat(date)).strftime("%d/%m/%Y")


def jour_ouvre(date):
    """Le jour même s'il est ouvré, sinon le lundi suivant (la grille du planning grise le week-end)."""
    return date + datetime.timedelta(days=(7 - date.weekday()) % 7 if date.weekday() >= 5 else 0)


def lundi(date):
    return date - datetime.timedelta(days=date.weekday())


def marqueur(technicien, date, liste, motif, compte=""):
    qui = " ; compte : " + compte if compte else ""          # T448 : le compte connecté, avec les comptes seulement
    return "dérogation habilitation : %s le %s sans %s%s ; motif : %s" % (technicien, date.isoformat(), liste, qui, motif)


def carte_ligne(habilitation_id):
    return ".equipe-carte-habilitations li[data-habilitation='%s']" % habilitation_id


# ---------------------------------------------------------------------------
# Aides d'écran communes
# ---------------------------------------------------------------------------

class Ecran:
    """À mêler à un CasNavigateur ; le mode fournit lignes(table) (disque ou mémoire)."""

    def lignes(self, table):  # pragma: no cover - fourni par le mode
        raise NotImplementedError

    def js(self, script, argument=None, page=None):
        return (page or self.page).evaluate(script, argument)

    def appeler(self, chemin, *arguments, page=None):
        return self.js(APPEL_JS, [chemin, list(arguments)], page)

    def accepte(self, chemin, *arguments, page=None):
        resultat = self.appeler(chemin, *arguments, page=page)
        self.assertIn("accepte", resultat, resultat)
        return resultat["accepte"]

    def aujourdhui(self):
        return datetime.date.fromisoformat(self.js("Donnees.aujourdhui()"))

    def aller(self, route, selecteur, page=None):
        page = page or self.page
        page.evaluate(ALLER_JS, route)
        page.wait_for_selector(selecteur)

    def attendre(self, condition, message="", delai_s=10):
        """Attend qu'une condition sur les données devienne vraie (le serveur écrit après la réponse de l'écran)."""
        fin = datetime.datetime.now() + datetime.timedelta(seconds=delai_s)
        while datetime.datetime.now() < fin:
            if condition():
                return
            self.page.wait_for_timeout(200)
        self.assertTrue(condition(), message)

    def attendre_toast(self, texte, page=None):
        # text_content : le toast entre par une transition de visibility (inner_text rendrait '' au premier instant).
        (page or self.page).wait_for_function(
            "(t) => document.getElementById('toast').textContent.includes(t)", arg=texte)
        return (page or self.page).text_content("#toast")

    def ligne(self, table, identifiant):
        return next(ligne for ligne in self.lignes(table) if ligne["id"] == identifiant)

    def journal_de(self, ot_id):
        return [j for j in self.lignes("journal") if j["table"] == "ordres_travail" and j["id_ligne"] == ot_id]

    def nom(self, technicien_id):
        technicien = self.ligne("techniciens", technicien_id)
        return ("%s %s" % (technicien["prenom"], technicien["nom"])).strip()

    def verifier_principe(self, ecran, zone, page=None):
        """CS175 côté Habilitations : la phrase D182 dans la zone ; aucun « conforme » à l'écran (ni dans la fenêtre)."""
        page = page or self.page
        with self.subTest(ecran=ecran):
            phrases = page.eval_on_selector_all(zone + " .equipe-principe",
                                                "l => l.filter((e) => e.getClientRects().length).map((e) => e.textContent.trim())")
            self.assertEqual(phrases, [PHRASE])
            texte = page.evaluate("() => document.querySelector('#contenu').innerText + ' ' + "
                                  "Array.from(document.querySelectorAll('dialog[open]')).map((d) => d.innerText).join(' ')")
            self.assertIsNone(MOT_CONFORME.search(texte), "« conforme » sur l'écran %s" % ecran)

    # -- fiche d'un technicien, fenêtre d'une habilitation ------------------------------------------

    def fiche_technicien(self, technicien_id, page=None):
        self.aller("#/equipe/" + technicien_id,
                   ".equipe-fiche[data-technicien='%s'] .equipe-carte-habilitations" % technicien_id, page)

    def valider_fenetre(self):
        self.page.click(FENETRE + ".fenetre-actions .btn-primaire")

    def echeance_affichee(self):
        return self.js("UI.dateFr(document.querySelector('dialog[open] [name=date_echeance]').value)")

    def ouvrir_ajout(self, technicien_id):
        self.fiche_technicien(technicien_id)
        self.page.click("#equipe-ajouter-habilitation")
        self.page.wait_for_selector(FENETRE + "[name=catalogue_id]")

    def habilitation_du(self, technicien_id, **criteres):
        return next(h for h in self.lignes("habilitations") if h["technicien_id"] == technicien_id
                    and all(h[c] == v for c, v in criteres.items()))

    # -- OT -------------------------------------------------------------------------------------------

    def attendre_fiche_ot(self, ot_id=None):
        if ot_id:
            self.page.wait_for_function("(id) => { const n = document.querySelector('.ot-fiche .ot-numero');"
                                        " return n && n.textContent === id; }", arg=ot_id)
        else:
            self.page.wait_for_function("() => /^#\\/ot\\/OT-/.test(location.hash)"
                                        " && document.querySelector('.ot-fiche .ot-numero')")
        return self.page.inner_text(".ot-fiche .ot-numero")

    def fiche_ot(self, ot_id, onglet=None, page=None):
        page = page or self.page
        page.evaluate(ALLER_JS, "#/ot/" + ot_id)
        page.wait_for_function("(id) => { const n = document.querySelector('.ot-fiche .ot-numero');"
                               " return n && n.textContent === id; }", arg=ot_id)
        if onglet:
            page.click(".onglet[data-onglet='%s']" % onglet)
            page.wait_for_selector("#form-%s" % onglet)

    def attendre_statut(self, statut):
        self.page.wait_for_function("(s) => { const b = document.querySelector('.ot-badges .badge.statut');"
                                    " return b && b.textContent === s; }", arg=statut)

    def choisir_affectation(self, formulaire, technicien, date):
        self.page.select_option(formulaire + " [name=technicien_id]", technicien)
        self.page.fill(formulaire + " [name=date_prevue]", date.isoformat())
        self.page.dispatch_event(formulaire + " [name=date_prevue]", "change")

    def refus_en_direct(self, formulaire):
        return self.page.wait_for_selector(ZONE % formulaire + " .alerte.important").inner_text()

    def constat(self, technicien, date, liste):
        return "%s (%s) n'a pas d'habilitation valide au %s pour : %s." % (self.nom(technicien), technicien, fr(date), liste)

    def attendre_derogation(self, constat, exigence):
        """La fenêtre du responsable : titre, constat, exigence ; « Passer outre » inactif à l'ouverture."""
        fenetre = self.page.wait_for_selector(DEROGATION)
        self.assertEqual(fenetre.query_selector("h2").inner_text(), "Habilitation exigée non valide")
        texte = fenetre.inner_text()
        self.assertIn(constat, texte)
        self.assertIn(exigence, texte)
        self.assertIn("Je passe outre, sous ma responsabilité. Le journal notera qui, quand, cet OT et ces habilitations.",
                      texte)
        self.assertTrue(self.page.is_disabled(PASSER_OUTRE))
        self.assertFalse(self.page.is_checked(CASE))

    def annuler_derogation(self):
        self.page.click(ANNULER)
        self.page.wait_for_selector(DEROGATION, state="detached")

    def passer_outre(self, motif):
        """Motif seul, case seule : bouton inactif ; les deux : il s'active (QUESTIONS-L2-L6 Q7)."""
        self.page.fill(CHAMP_MOTIF, motif)
        self.assertTrue(self.page.is_disabled(PASSER_OUTRE))
        self.page.check(CASE)
        self.page.fill(CHAMP_MOTIF, "  ")
        self.assertTrue(self.page.is_disabled(PASSER_OUTRE))
        self.page.fill(CHAMP_MOTIF, motif)
        self.assertTrue(self.page.is_enabled(PASSER_OUTRE))
        self.page.click(PASSER_OUTRE)
        self.page.wait_for_selector(DEROGATION, state="detached")

    def verifier_journal(self, entree, ot_id, technicien, date, liste, motif, debut):
        """Qui (profil, poste ; avec les comptes, le compte : T448), quand (date et heure du jour), quel OT, quelle
        habilitation (le marqueur, D186)."""
        self.assertEqual((entree["table"], entree["id_ligne"], entree["profil"], entree["poste"]),
                         ("ordres_travail", ot_id, "Responsable", "Poste test"))
        self.assertRegex(entree["date_heure"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}")
        self.assertIn(entree["date_heure"][:10], (self.jour.isoformat(), (self.jour + datetime.timedelta(days=1)).isoformat()))
        compte = COMPTES_DE_TEST["responsable"][0] if getattr(self, "COMPTES", False) else ""
        self.assertEqual(entree["action"], debut + " ; " + marqueur(technicien, date, liste, motif, compte))

    def bandeau_derogation(self, entree, intitule, motif):
        return "Affecté sans habilitation %s valide : dérogation du responsable le %s à %s. Motif : %s" % (
            intitule, fr(entree["date_heure"][:10]), entree["date_heure"][11:16], motif)

    # -- planning -------------------------------------------------------------------------------------

    def planning(self, date, page=None):
        self.aller("#/planning?semaine=" + lundi(date).isoformat(), ".pl-ecran .pl-case", page)

    def planifier_par_le_bouton(self, ot_id, technicien, date):
        page = self.page
        page.click(".pl-a-planifier .pl-ot[data-ot='%s'] [data-action='planifier']" % ot_id)
        page.select_option("#pl-technicien", technicien)
        page.fill("#pl-date", date.isoformat())
        page.click("dialog .fenetre-actions button:has-text('Planifier')")

    def case_planning(self, technicien, date):
        return ".pl-case[data-technicien='%s'][data-date='%s'] .pl-ot" % (technicien, date.isoformat())


# ---------------------------------------------------------------------------
# Le parcours
# ---------------------------------------------------------------------------

class CasRecette(Ecran, CasNavigateur):
    """Le mode ouvre l'application (profil Responsable), appelle parcours(), puis ouvre la vue du technicien."""

    def parcours(self):
        self.jour = self.aujourdhui()
        self.date = jour_ouvre(self.jour + datetime.timedelta(days=14))         # D : date prévue des affectations
        a = self.creer_technicien_a()
        br = self.habilitation_h02(a)
        caces, autorisation = self.autorisation_de_conduite(a)
        echeance = self.corriger_l_echeance(a, br)
        b = self.technicien_pas_encore_obtenue()
        c = self.accepte("Equipe.creerTechnicien", {"nom": "Recette L3", "prenom": "Sans habilitation"})
        ot_equipement = self.nouvel_ot_equipement_echue(a, echeance)
        ot_exigence = self.preparation_exigence_de_l_ot(a)
        self.planning_pas_encore_obtenue(b)
        ot_libre = self.sans_exigence_jamais_bloque(c)
        return {"a": a, "b": b, "c": c, "br": br, "caces": caces, "autorisation": autorisation,
                "ot_equipement": ot_equipement, "ot_exigence": ot_exigence, "ot_libre": ot_libre}

    # -- CS172, CS175 : habilitation du catalogue -----------------------------------------------------

    def creer_technicien_a(self):
        page = self.page
        self.aller("#/equipe/nouveau", "#form-technicien [name=nom]")
        page.fill("#form-technicien [name=nom]", "Recette L3")
        page.fill("#form-technicien [name=prenom]", "Électricien")
        page.click("#form-technicien button[type=submit]")
        self.attendre_toast("Technicien créé.")
        page.wait_for_function("() => /^#\\/equipe\\/TEC-/.test(location.hash)")
        a = self.js("decodeURIComponent(location.hash.split('/').pop())")
        self.fiche_technicien(a)
        self.verifier_principe("fiche d'un technicien sans habilitation", ".equipe-carte-habilitations")
        return a

    def habilitation_h02(self, a):
        page = self.page
        self.ouvrir_ajout(a)
        liste = FENETRE + "[name=catalogue_id]"
        self.verifier_principe("fenêtre « Ajouter une habilitation », saisie libre", FENETRE)
        page.select_option(liste, "H02")
        self.assertEqual(page.input_value(FENETRE + "[name=recyclage_mois]"), "36")
        encart = page.inner_text(FENETRE + ".equipe-type-encart")
        for morceau in ("recommandation · relu le 08/11/2026 · réglementation française", "NF C 18-510"):
            self.assertIn(morceau, encart)
        source = page.inner_text(FENETRE + ".equipe-type-encart .equipe-type-source")
        self.assertIn("recommandation", source)
        self.assertNotIn("obligation", source)
        self.verifier_principe("fenêtre « Ajouter une habilitation », H02", FENETRE)

        # CS172 : 15/01/2024 + 36 mois → 15/01/2027 ; tapée à la main, elle n'est plus recalculée ; vidée, elle suit.
        page.fill(FENETRE + "[name=intitule]", "BR")
        page.fill(FENETRE + "[name=date_obtention]", OBTENTION_BR)
        self.assertEqual(self.echeance_affichee(), "15/01/2027")
        page.fill(FENETRE + "[name=date_echeance]", "2027-01-08")
        page.fill(FENETRE + "[name=date_obtention]", "2024-01-20")
        self.assertEqual(self.echeance_affichee(), "08/01/2027")
        page.fill(FENETRE + "[name=date_echeance]", "")
        page.fill(FENETRE + "[name=date_obtention]", OBTENTION_BR)
        self.assertEqual(self.echeance_affichee(), "15/01/2027")
        page.set_input_files(FENETRE + "input[type=file]",
                             files=[{"name": "titre-br.pdf", "mimeType": "application/pdf", "buffer": PDF_BR}])
        self.valider_fenetre()
        self.attendre_toast("Habilitation ajoutée")
        self.attendre(lambda: any(h["technicien_id"] == a for h in self.lignes("habilitations")), "BR non écrite")

        br = self.habilitation_du(a, intitule="BR")
        self.assertEqual({c: br[c] for c in ("date_obtention", "date_echeance", "recyclage_mois", "catalogue_id",
                                             "nature_source")},
                         {"date_obtention": OBTENTION_BR, "date_echeance": ECHEANCE_BR, "recyclage_mois": "36",
                          "catalogue_id": "H02", "nature_source": "recommandation"})
        self.assertRegex(br["justificatif"], r"(^|-)habilitation-%s-BR-2024-01-15\.pdf$" % a)
        self.verifier_document(br["justificatif"], PDF_BR)

        # La carte : recyclage, « recommandation », type du catalogue ; le justificatif s'ouvre depuis la fiche.
        element = carte_ligne(br["id"])
        page.wait_for_selector(element + " a.equipe-justificatif-lien")
        texte = page.inner_text(element)
        self.assertIn("Obtenue le 15/01/2024 · échéance le 15/01/2027", texte)
        self.assertIn("Recyclage : 36 mois", texte)
        self.assertEqual(page.inner_text(element + " .equipe-recyclage .badge").strip(), "recommandation")
        self.assertIn("Type : Habilitation électrique – électricien (catalogue Prévo)", texte)
        self.verifier_lien(element, br["justificatif"], PDF_BR)
        self.verifier_principe("fiche du technicien, BR", ".equipe-carte-habilitations")
        return br["id"]

    def verifier_lien(self, element, nom, octets, page=None):
        page = page or self.page
        lien = element + " a.equipe-justificatif-lien"
        self.assertEqual(page.eval_on_selector(lien, "a => [a.target, a.textContent.trim()]"), ["_blank", nom])
        lu = page.evaluate(LIRE_LIEN_JS, lien)
        self.assertEqual((lu["statut"], bytes(lu["octets"])), (200, octets))

    def verifier_document(self, nom, octets):  # pragma: no cover - selon le mode
        pass

    # -- CS179 : autorisation de conduite, type distinct du CACES qui la justifie ---------------------

    def autorisation_de_conduite(self, a):
        page = self.page
        self.ouvrir_ajout(a)
        liste = FENETRE + "[name=catalogue_id]"
        groupes = dict(page.eval_on_selector_all(liste + " optgroup",
                                                 "gs => gs.map(g => [g.label, Array.from(g.children).map(o => o.value)])"))
        self.assertEqual(list(groupes), ["Électricité", "CACES", "Autorisation de conduite"])
        self.assertIn("H14", groupes["Autorisation de conduite"])
        self.assertIn("H12", groupes["CACES"])
        self.assertNotIn("H14", groupes["CACES"])
        page.select_option(liste, "H12")
        self.assertEqual((page.input_value(FENETRE + "[name=intitule]"), page.input_value(FENETRE + "[name=recyclage_mois]")),
                         ("CACES R489", "60"))
        self.assertIn(RAPPEL_CACES, page.inner_text(FENETRE + ".equipe-type-encart"))
        page.fill(FENETRE + "[name=date_obtention]", OBTENTION_CACES)
        page.set_input_files(FENETRE + "input[type=file]",
                             files=[{"name": "caces.pdf", "mimeType": "application/pdf", "buffer": PDF_CACES}])
        self.valider_fenetre()
        self.attendre_toast("Habilitation ajoutée")
        self.attendre(lambda: any(h["catalogue_id"] == "H12" for h in self.lignes("habilitations") if h["technicien_id"] == a))
        caces = self.habilitation_du(a, catalogue_id="H12")
        self.assertEqual((caces["intitule"], caces["recyclage_mois"]), ("CACES R489", "60"))
        page.wait_for_selector(carte_ligne(caces["id"]) + " .equipe-rappel-caces")
        self.assertIn(RAPPEL_CACES, page.inner_text(carte_ligne(caces["id"]) + " .equipe-rappel-caces"))

        # H14 : son intitulé, aucun recyclage, l'obligation ; le justificatif repris du CACES.
        page.click("#equipe-ajouter-habilitation")
        page.wait_for_selector(liste)
        page.select_option(liste, "H14")
        self.assertEqual((page.input_value(FENETRE + "[name=intitule]"), page.input_value(FENETRE + "[name=recyclage_mois]")),
                         ("Autorisation de conduite (employeur)", ""))
        encart = page.inner_text(FENETRE + ".equipe-type-encart")
        self.assertIn(TEXTE_AUTORISATION, encart)
        self.assertIn("obligation réglementaire", page.inner_text(FENETRE + ".equipe-type-encart .equipe-type-source"))
        reprise = FENETRE + ".champ[data-champ=justificatif_repris]"
        self.assertTrue(page.is_visible(reprise))
        options = page.eval_on_selector_all(reprise + " option", "os => os.map(o => [o.value, o.textContent.trim()])")
        self.assertEqual(options, [["", "— aucun —"], [caces["justificatif"], "CACES R489 (obtenu le %s)" % fr(OBTENTION_CACES)]])
        page.select_option(reprise + " select", caces["justificatif"])
        page.fill(FENETRE + "[name=date_obtention]", OBTENTION_AUTORISATION)
        self.assertEqual(page.input_value(FENETRE + "[name=date_echeance]"), "")
        self.verifier_principe("fenêtre « Ajouter une habilitation », H14", FENETRE)
        self.valider_fenetre()
        self.attendre_toast("Habilitation ajoutée")
        self.attendre(lambda: any(h["catalogue_id"] == "H14" for h in self.lignes("habilitations") if h["technicien_id"] == a))
        autorisation = self.habilitation_du(a, catalogue_id="H14")
        self.assertNotEqual(autorisation["id"], caces["id"])
        self.assertEqual({c: autorisation[c] for c in ("intitule", "date_obtention", "date_echeance", "recyclage_mois",
                                                       "justificatif", "nature_source")},
                         {"intitule": "Autorisation de conduite (employeur)", "date_obtention": OBTENTION_AUTORISATION,
                          "date_echeance": "", "recyclage_mois": "", "justificatif": caces["justificatif"],
                          "nature_source": "obligation"})
        page.wait_for_selector(carte_ligne(autorisation["id"]) + " a.equipe-justificatif-lien")
        self.assertEqual(page.locator(".equipe-rappel-caces").count(), 0)
        self.verifier_lien(carte_ligne(autorisation["id"]), caces["justificatif"], PDF_CACES)
        return caces["id"], autorisation["id"]

    # -- CS172 : l'échéance corrigée à la main ; vue « à renouveler » ---------------------------------

    def corriger_l_echeance(self, a, br):
        page = self.page
        echeance = self.jour + datetime.timedelta(days=7)
        self.fiche_technicien(a)
        page.click("button[data-action='corriger'][data-habilitation='%s']" % br)
        page.wait_for_selector(FENETRE + "[name=date_echeance]")
        self.assertEqual(page.input_value(FENETRE + "[name=date_echeance]"), ECHEANCE_BR)
        page.fill(FENETRE + "[name=date_echeance]", echeance.isoformat())
        self.valider_fenetre()
        self.attendre_toast("Habilitation corrigée.")
        self.attendre(lambda: self.ligne("habilitations", br)["date_echeance"] == echeance.isoformat(), "échéance non écrite")
        ligne = self.ligne("habilitations", br)
        self.assertEqual((ligne["date_obtention"], ligne["recyclage_mois"], ligne["catalogue_id"]), (OBTENTION_BR, "36", "H02"))
        page.wait_for_function("([s, t]) => { const e = document.querySelector(s); return e && e.innerText.includes(t); }",
                               arg=[carte_ligne(br), "échéance le " + fr(echeance)])

        self.aller("#/equipe?filtre=a-renouveler", ".equipe-a-renouveler")
        lignes = page.eval_on_selector_all(".equipe-a-renouveler li", "l => l.map((e) => e.innerText)")
        self.assertTrue(any(self.nom(a) in texte and "BR" in texte for texte in lignes), lignes)
        self.verifier_principe("vue « à renouveler »", ".equipe-a-renouveler")
        return echeance

    def technicien_pas_encore_obtenue(self):
        """B : BR obtenue après D (par la fenêtre, type H02) : pas encore obtenue à la date prévue."""
        page = self.page
        b = self.accepte("Equipe.creerTechnicien", {"nom": "Recette L3", "prenom": "Futur électricien"})
        self.obtention_b = self.date + datetime.timedelta(days=16)
        self.ouvrir_ajout(b)
        page.select_option(FENETRE + "[name=catalogue_id]", "H02")
        page.fill(FENETRE + "[name=intitule]", "BR")
        page.fill(FENETRE + "[name=date_obtention]", self.obtention_b.isoformat())
        self.valider_fenetre()
        self.attendre_toast("Habilitation ajoutée")
        self.attendre(lambda: any(h["technicien_id"] == b for h in self.lignes("habilitations")), "BR de B non écrite")
        self.assertEqual(self.habilitation_du(b, intitule="BR")["date_obtention"], self.obtention_b.isoformat())
        return b

    # -- CS178 : nouvel OT, exigence de l'équipement, habilitation échue -----------------------------

    def nouvel_ot_equipement_echue(self, a, echeance):
        page = self.page
        formulaire = "#form-nouvel-ot"
        repere = self.ligne("equipements", EQ_BR)["repere"]
        self.aller("#/ot/nouveau?equipement=" + EQ_BR, formulaire + " [name=titre]")
        page.fill(formulaire + " [name=titre]", "Recette L3 — armoire, BR échue à la date prévue")
        # Avant l'échéance corrigée (J + 5 < J + 7) : rien ; à D : le refus en direct, à la date prévue.
        self.choisir_affectation(formulaire, a, self.jour + datetime.timedelta(days=5))
        self.assertEqual(page.locator(ZONE % formulaire + " .alerte").count(), 0)
        self.choisir_affectation(formulaire, a, self.date)
        liste = "BR (échue le %s)" % fr(echeance)
        bandeau = self.refus_en_direct(formulaire)
        self.assertIn("Habilitation exigée non valide : " + self.constat(a, self.date, liste), bandeau)
        self.assertIn("vous pourrez passer outre, sous votre responsabilité, avec un motif.", bandeau)

        # Annuler : rien n'est écrit, le refus est redit.
        avant_ot, avant_journal = len(self.lignes("ordres_travail")), len(self.lignes("journal"))
        page.click(formulaire + " button[type=submit]")
        self.attendre_derogation(self.constat(a, self.date, liste), "Cet OT l'exige (équipement %s). L'affectation est refusée." % repere)
        self.annuler_derogation()
        self.assertIn("Seul le responsable peut passer outre.", self.attendre_toast("Affectation refusée"))
        self.assertEqual((len(self.lignes("ordres_travail")), len(self.lignes("journal"))), (avant_ot, avant_journal))

        # Passer outre : l'OT est créé avec l'affectation ; la dérogation dans l'action du journal de la création.
        page.click(formulaire + " button[type=submit]")
        self.attendre_derogation(self.constat(a, self.date, liste), "(équipement %s)" % repere)
        self.passer_outre(MOTIF_NOUVEL_OT)
        ot_id = self.attendre_fiche_ot()
        self.attendre(lambda: len(self.journal_de(ot_id)) == 1, "journal de la création absent")
        ligne = self.ligne("ordres_travail", ot_id)
        self.assertEqual((ligne["equipement_id"], ligne["technicien_id"], ligne["date_prevue"], ligne["statut"]),
                         (EQ_BR, a, self.date.isoformat(), "Créé"))
        entree = self.journal_de(ot_id)[0]
        self.verifier_journal(entree, ot_id, a, self.date, "BR (échue)", MOTIF_NOUVEL_OT,
                              "création — création de l'OT (manuel)")
        page.wait_for_selector(BANDEAU_DEROGATION)
        self.assertEqual(page.inner_text(BANDEAU_DEROGATION), self.bandeau_derogation(entree, "BR", MOTIF_NOUVEL_OT))
        self.assertEqual(page.inner_text(".ot-entete .ot-habilitation-exigee"), "Habilitation exigée : BR (équipement)")
        return ot_id

    # -- CS180 : exigence posée sur l'OT (D191), absente ; « Planifier » ne redemande pas -------------

    def preparation_exigence_de_l_ot(self, a):
        page = self.page
        equipement = self.js(EQUIPEMENT_SANS_EXIGENCE_JS)
        self.aller("#/ot/nouveau?equipement=" + equipement, "#form-nouvel-ot [name=titre]")
        page.fill("#form-nouvel-ot [name=titre]", "Recette L3 — exigence de l'OT")
        page.click("#form-nouvel-ot button[type=submit]")
        ot_id = self.attendre_fiche_ot()
        self.assertEqual(page.locator("dialog").count(), 0)
        page.click(PLANIFIER_FICHE % "Préparé")
        self.attendre_statut("Préparé")
        self.fiche_ot(ot_id, "preparation")
        formulaire = "#form-preparation"
        page.wait_for_selector(formulaire + " [name=habilitation_requise]")
        self.choisir_affectation(formulaire, a, self.date)
        self.assertEqual(page.locator(ZONE % formulaire + " .alerte").count(), 0)      # l'équipement n'exige rien
        page.fill(formulaire + " [name=habilitation_requise]", "H0V")
        page.dispatch_event(formulaire + " [name=habilitation_requise]", "change")
        self.assertIn(self.constat(a, self.date, "H0V (absente)"), self.refus_en_direct(formulaire))
        page.click(formulaire + " button[type=submit]")
        self.attendre_derogation(self.constat(a, self.date, "H0V (absente)"), "Cet OT l'exige (OT). L'affectation est refusée.")
        self.passer_outre(MOTIF_PREPARATION)
        self.attendre_toast("Préparation enregistrée.")
        self.attendre(lambda: self.ligne("ordres_travail", ot_id)["habilitation_requise"] == "H0V", "exigence non écrite")
        ligne = self.ligne("ordres_travail", ot_id)
        self.assertEqual((ligne["technicien_id"], ligne["date_prevue"], ligne["statut"]), (a, self.date.isoformat(), "Préparé"))
        derniere = self.journal_de(ot_id)[-1]
        self.assertTrue(derniere["action"].startswith("modification : "), derniere["action"])
        self.assertIn(" — préparation ; ", derniere["action"])
        self.verifier_journal(derniere, ot_id, a, self.date, "H0V (absente)", MOTIF_PREPARATION,
                              derniere["action"].split(" ; dérogation habilitation : ")[0])
        page.wait_for_selector(".ot-entete .ot-habilitation-exigee")
        self.assertEqual(page.inner_text(".ot-entete .ot-habilitation-exigee"), "Habilitation exigée : H0V (OT)")
        page.wait_for_selector(BANDEAU_DEROGATION)
        self.assertEqual(page.inner_text(BANDEAU_DEROGATION), self.bandeau_derogation(derniere, "H0V", MOTIF_PREPARATION))

        # « Planifier » : même OT, technicien, date et habilitation → aucune fenêtre ; une seule dérogation au journal.
        page.click(PLANIFIER_FICHE % "Planifié")
        self.attendre_statut("Planifié")
        self.assertEqual(page.locator("dialog").count(), 0)
        self.attendre(lambda: self.ligne("ordres_travail", ot_id)["statut"] == "Planifié")
        self.assertEqual(self.journal_de(ot_id)[-1]["action"], "modification : statut — statut Préparé → Planifié")
        self.assertEqual(sum("dérogation habilitation" in j["action"] for j in self.journal_de(ot_id)), 1)
        return ot_id

    # -- CS178 au planning : exigence de l'équipement, pas encore obtenue -----------------------------

    def planning_pas_encore_obtenue(self, b):
        page = self.page
        ot_id = OT_BR_A_PLANIFIER
        self.assertEqual(self.ligne("ordres_travail", ot_id)["statut"], "Préparé")
        liste = "BR (pas encore obtenue : valable à partir du %s)" % fr(self.obtention_b)
        repere = self.ligne("equipements", EQ_BR)["repere"]
        avant = self.journal_de(ot_id)
        self.planning(self.date)
        self.planifier_par_le_bouton(ot_id, b, self.date)
        self.attendre_derogation(self.constat(b, self.date, liste), "Cet OT l'exige (équipement %s)." % repere)
        self.annuler_derogation()
        self.assertIn("Affectation refusée", page.wait_for_selector("#pl-message .alerte.important").inner_text())
        ligne = self.ligne("ordres_travail", ot_id)
        self.assertEqual((ligne["statut"], ligne["technicien_id"]), ("Préparé", ""))
        self.assertEqual(self.journal_de(ot_id), avant)

        self.planifier_par_le_bouton(ot_id, b, self.date)
        self.attendre_derogation(self.constat(b, self.date, liste), "(équipement %s)" % repere)
        self.passer_outre(MOTIF_PLANNING)
        page.wait_for_selector(self.case_planning(b, self.date) + "[data-ot='%s']" % ot_id)
        self.attendre(lambda: self.ligne("ordres_travail", ot_id)["statut"] == "Planifié", "OT non planifié")
        self.attendre(lambda: len(self.journal_de(ot_id)) == len(avant) + 1, "journal de la planification absent")
        ligne = self.ligne("ordres_travail", ot_id)
        self.assertEqual((ligne["technicien_id"], ligne["date_prevue"]), (b, self.date.isoformat()))
        self.verifier_journal(self.journal_de(ot_id)[-1], ot_id, b, self.date, "BR (pas encore obtenue)", MOTIF_PLANNING,
                              "modification : statut, date_prevue, technicien_id — planification : %s le %s "
                              "(Préparé → Planifié)" % (b, self.date.isoformat()))

    # -- CS180 : un OT sans exigence n'est jamais bloqué ---------------------------------------------

    def sans_exigence_jamais_bloque(self, c):
        page = self.page
        self.assertEqual([h for h in self.lignes("habilitations") if h["technicien_id"] == c], [])
        equipement = self.js(EQUIPEMENT_SANS_EXIGENCE_JS)
        formulaire = "#form-nouvel-ot"
        self.aller("#/ot/nouveau?equipement=" + equipement, formulaire + " [name=titre]")
        page.fill(formulaire + " [name=titre]", "Recette L3 — sans exigence")
        self.choisir_affectation(formulaire, c, self.date)
        self.assertEqual(page.locator(ZONE % formulaire + " .alerte").count(), 0)
        page.click(formulaire + " button[type=submit]")
        ot_id = self.attendre_fiche_ot()
        self.assertEqual(page.locator("dialog").count(), 0)
        self.attendre(lambda: len(self.journal_de(ot_id)) == 1)
        self.assertEqual([j["action"] for j in self.journal_de(ot_id)], ["création — création de l'OT (manuel)"])
        self.assertEqual((self.ligne("ordres_travail", ot_id)["technicien_id"], page.locator(BANDEAU_DEROGATION).count()), (c, 0))
        self.assertEqual(page.locator(".ot-entete .ot-habilitation-exigee").count(), 0)

        # Au planning : l'OT sans exigence de la démo, sur C, sans fenêtre.
        self.assertEqual(self.js("(id) => Ordres.habilitationsExigees(id)", OT_SANS_EXIGENCE), [])
        self.planning(self.date)
        self.planifier_par_le_bouton(OT_SANS_EXIGENCE, c, self.date)
        page.wait_for_selector(self.case_planning(c, self.date) + "[data-ot='%s']" % OT_SANS_EXIGENCE)
        self.assertEqual(page.locator(DEROGATION).count(), 0)
        self.attendre(lambda: self.ligne("ordres_travail", OT_SANS_EXIGENCE)["statut"] == "Planifié")
        self.assertFalse(any("dérogation" in j["action"] or "habilitation" in j["action"]
                             for j in self.journal_de(OT_SANS_EXIGENCE)))

        # Toute la base : aucun OT sans exigence n'est bloqué, quel que soit le technicien ; l'exigence, elle, bloque C.
        bilan = self.js(JAMAIS_BLOQUE_JS, self.date.isoformat())
        self.assertGreater(bilan["sans"], 10, bilan)
        self.assertGreater(bilan["avec"], 0, bilan)
        self.assertEqual(bilan["bloques"], [], bilan)
        self.assertTrue(self.js("([ot, c, d]) => Ordres.controleHabilitation(ot, c, d).bloque",
                                [OT_EXIGE_H0V, c, self.date.isoformat()]))
        return ot_id

    # -- CS178 : le technicien n'a aucun moyen de passer outre ---------------------------------------

    def vue_du_technicien(self, page, cree, technicien):
        """La page est ouverte sous le profil Technicien (technicien : son identifiant)."""
        self.assertEqual((page.evaluate("App.profil.type"), page.evaluate("App.profil.technicienId"),
                          page.evaluate("App.estResponsable()")), ("technicien", technicien, False))
        a = cree["a"]

        # L'OT dérogé : le bandeau de la dérogation, lu de tous ; ni case, ni bouton.
        self.fiche_ot(cree["ot_equipement"], page=page)
        entree = self.journal_de(cree["ot_equipement"])[0]
        page.wait_for_selector(BANDEAU_DEROGATION)
        self.assertEqual(page.inner_text(BANDEAU_DEROGATION), self.bandeau_derogation(entree, "BR", MOTIF_NOUVEL_OT))
        self.assertEqual(page.locator("[name=passer_outre], .ot-passer-outre, dialog").count(), 0)

        # L'OT de la démo qui exige H0V : ni « Planifier » ni enregistrement de la préparation.
        self.fiche_ot(OT_EXIGE_H0V, "preparation", page=page)
        self.assertEqual(page.locator("#form-preparation button[type=submit]").count(), 0)
        self.assertEqual(page.locator("button[data-cible='Planifié']").count(), 0)
        self.assertEqual(page.inner_text(".ot-entete .ot-habilitation-exigee"), "Habilitation exigée : H0V (OT)")

        # Planning : lecture seule.
        self.planning(self.date, page)
        self.assertEqual(page.locator(".pl-ot[draggable='true']").count(), 0)
        self.assertEqual(page.locator("[data-action='planifier']").count(), 0)

        # Par l'application elle-même : aucune fenêtre, la dérogation refusée, rien d'écrit (A n'a pas H0V).
        avant_ot, avant_journal = self.ligne("ordres_travail", OT_EXIGE_H0V), len(self.lignes("journal"))
        infos = {"otId": OT_EXIGE_H0V, "technicienId": a, "date": self.date.isoformat(),
                 "manquantes": [{"intitule": "H0V", "raison": "absente", "echeance": "", "obtention": "", "origines": ["ot"]}]}
        self.assertIsNone(page.evaluate("(infos) => Ordres.demanderDerogation(infos)", infos))
        for script in ("([ot, t, d]) => Planning.planifier(ot, 'Préparé', t, d, { passerOutreHabilitation: true, "
                       "motifDerogation: 'motif du technicien' })",
                       "([ot, t, d]) => Ordres.avecDerogation((options) => Planning.planifier(ot, 'Préparé', t, d, options))"):
            with self.subTest(script=script):
                resultat = page.evaluate("""async ([script, args]) => {
                    try { await eval(script)(args); return { accepte: true }; }
                    catch (erreur) { return { refus: erreur.message, habilitation: Boolean(erreur.habilitation) }; } }""",
                                         [script, [OT_EXIGE_H0V, a, self.date.isoformat()]])
                self.assertTrue(resultat.get("refus", "").startswith("Affectation refusée : "), resultat)
                self.assertTrue(resultat["habilitation"], resultat)
        self.assertEqual(page.locator("dialog, [name=passer_outre], .ot-passer-outre").count(), 0)
        self.assertEqual((self.ligne("ordres_travail", OT_EXIGE_H0V), len(self.lignes("journal"))), (avant_ot, avant_journal))

        # Écran Habilitations : phrase D182, aucun bouton ; l'application refuse l'écriture.
        self.fiche_technicien(a, page)
        self.verifier_principe("fiche d'un technicien vue par le technicien", ".equipe-carte-habilitations", page)
        self.assertEqual(page.locator("#equipe-ajouter-habilitation, .equipe-carte-habilitations button[data-action]").count(), 0)
        avant = self.lignes("habilitations")
        refus = self.appeler("Equipe.ajouterHabilitation", a, {"intitule": "H0V", "date_obtention": "2026-01-05"}, page=page)
        self.assertEqual((refus.get("refus"), refus.get("validation")), (REFUS_APPLICATION, True), refus)
        refus = self.appeler("Equipe.modifierHabilitation", cree["br"], {"date_echeance": ECHEANCE_BR}, page=page)
        self.assertEqual(refus.get("refus"), REFUS_APPLICATION, refus)
        self.assertEqual(self.lignes("habilitations"), avant)


# ---------------------------------------------------------------------------
# Les modes
# ---------------------------------------------------------------------------

class CasParcoursServeur(CasRecette):
    """serveur.py sur une copie du jeu de démo ; données et documents relus sur le disque."""

    COMPTES = False

    def lignes(self, table):
        if not (self.dossier / (table + ".csv")).exists():
            return []
        return [propre(ligne) for ligne in lire_csv(self.dossier, table + ".csv")]

    def verifier_document(self, nom, octets):
        self.assertEqual((self.dossier / "documents" / nom).read_bytes(), octets)

    def lancer(self):
        with ServeurPrevo(comptes=self.COMPTES) as serveur:
            self.serveur, self.dossier = serveur, Path(serveur.dossier)
            if self.COMPTES:
                serveur.poser_session(self.contexte, "responsable")
            else:
                preregler_profil(self.contexte, "responsable", "Nicolas Briand")
            self.page.set_viewport_size({"width": 1440, "height": 1200})
            self.page.goto(serveur.url + "/#/accueil")
            attendre_pret(self.page)
            self.page.wait_for_load_state("networkidle")       # écritures du démarrage (OT préventifs échus) finies
            self.assertEqual(self.js("App.profil.type"), "responsable")
            cree = self.parcours()
            self.page.close()
            self.technicien(serveur, cree)

    def page_technicien(self, serveur, technicien):
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1440, "height": 1200})
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        if self.COMPTES:
            serveur.poser_session(contexte, "technicien")
        else:
            preregler_profil(contexte, "technicien", technicien_id=technicien)
        page = contexte.new_page()
        self.surveiller(page)
        page.goto(serveur.url + "/#/accueil")
        attendre_pret(page)
        page.wait_for_load_state("networkidle")
        self.page = page                                        # attendre() et les aides lisent self.page
        return page

    def technicien(self, serveur, cree):
        """Sans comptes : le technicien A (son profil sur ce poste) ; il ouvre son propre justificatif (Q5)."""
        page = self.page_technicien(serveur, cree["a"])
        self.vue_du_technicien(page, cree, cree["a"])
        br = self.ligne("habilitations", cree["br"])
        self.verifier_lien(carte_ligne(cree["br"]), br["justificatif"], PDF_BR, page)


class TestParcoursServeur(CasParcoursServeur):

    def test_habilitations_et_blocage_rg8_serveur_sans_comptes(self):
        self.lancer()


class TestParcoursServeurComptes(CasParcoursServeur):

    COMPTES = True

    def test_habilitations_et_blocage_rg8_avec_comptes_puis_refus_du_serveur_au_technicien(self):
        self.lancer()

    def technicien(self, serveur, cree):
        """Le compte technicien (son technicien lié) : la vue, puis les refus 403 du serveur (provisoires Q2, Q3)."""
        technicien = COMPTES_DE_TEST["technicien"][4]
        page = self.page_technicien(serveur, technicien)
        self.vue_du_technicien(page, cree, technicien)
        # La fiche de A : le justificatif est dit, sans lien ni nom de document.
        br = self.ligne("habilitations", cree["br"])
        self.assertIn("Justificatif : " + JUSTIFICATIF_FERME, page.inner_text(carte_ligne(cree["br"])))
        self.assertEqual(page.locator(".equipe-carte-habilitations a.equipe-justificatif-lien").count(), 0)
        self.assertNotIn(br["justificatif"], page.evaluate("document.getElementById('contenu').innerHTML"))

        # Le serveur : écriture de habilitations refusée au technicien (PUT, ajout), fichier inchangé.
        cookie, responsable = serveur.session("technicien"), serveur.session("responsable")
        chemin = self.dossier / "habilitations.csv"
        avant = chemin.read_bytes()
        entete = premiere_ligne(avant)
        envoi = requete(serveur, "PUT", "/api/csv/habilitations", BOM + entete + b"\r\n", cookie,
                        {"X-Version-Attendue": "0" * 16})
        ajout = requete(serveur, "POST", "/api/csv/habilitations/ajout",
                        entete + ("\r\nHAB-0901;%s;H0V;2026-11-01;2029-11-01;;;;\r\n" % technicien).encode("utf-8"), cookie)
        for reponse in (envoi, ajout):
            self.assertEqual(reponse.statut, 403, reponse.octets[:300])
            self.assertEqual(reponse.json()["erreur"], REFUS_TABLE)
        self.assertEqual(chemin.read_bytes(), avant)

        # Les justificatifs écrits pendant le parcours : refusés au technicien, servis au responsable.
        for nom, octets in ((br["justificatif"], PDF_BR), (self.ligne("habilitations", cree["caces"])["justificatif"], PDF_CACES)):
            with self.subTest(document=nom):
                refus = requete(serveur, "GET", "/api/documents/" + nom, cookie=cookie)
                self.assertEqual(refus.statut, 403, refus.octets[:300])
                self.assertEqual(refus.json()["erreur"], REFUS_DOCUMENT.format(role="technicien"))
                servi = requete(serveur, "GET", "/api/documents/" + nom, cookie=responsable)
                self.assertEqual((servi.statut, servi.octets), (200, octets))


class TestParcoursDemo(CasRecette):
    """index.html en file:// (démo, données en mémoire) ; le technicien : changement de profil dans la même page."""

    def lignes(self, table):
        return [propre(ligne) for ligne in self.js(LIGNES_JS, table)]

    def test_habilitations_et_blocage_rg8_en_demo(self):
        preregler_profil(self.contexte, "responsable", "Nicolas Briand")
        self.page.set_viewport_size({"width": 1440, "height": 1200})
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.assertEqual((self.js("App.mode"), self.js("App.profil.type")), ("demo", "responsable"))
        cree = self.parcours()

        # Profil Technicien (A), sans recharger : la démo serait perdue.
        page = self.page
        page.evaluate("window.__memePage = true")
        page.click("#etat-poste")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-technicien")
        page.click("#profil-techniciens [data-technicien='%s']" % cree["a"])
        attendre_pret(page)
        self.assertTrue(page.evaluate("window.__memePage === true"), "la page a été rechargée")
        self.vue_du_technicien(page, cree, cree["a"])
        br = self.ligne("habilitations", cree["br"])
        self.verifier_lien(carte_ligne(cree["br"]), br["justificatif"], PDF_BR, page)


if __name__ == "__main__":
    unittest.main()
