"""Tests des écritures de RG8 bloquante (T437 ; D186, D191 ; CS178, CS180 ; conception L2-L3 §7.3 à §7.5).

Par l'API, dans l'application ouverte en mode serveur (serveur.py sur une copie temporaire du jeu de démo, dates non
décalées), CSV relus sur le disque. Ordres.creer, Ordres.interne.modifierOt (préparation), Ordres.changerStatut vers
« Planifié » et Planning.planifier (planification et replanification) refusent d'affecter un technicien sans
l'habilitation exigée valide à la date, sans rien écrire (Donnees.ErreurValidation, erreur.habilitation = { otId,
technicienId, date, manquantes }). Avec { passerOutreHabilitation: true, motifDerogation }, le responsable passe et
l'action du journal de l'écriture elle-même finit par le marqueur « dérogation habilitation : … ; motif : … » : qui
(profil, poste), quand (date_heure), quel OT (id_ligne), quelle habilitation (le marqueur). Sans motif : refus
(QUESTIONS-L2-L6 Q7). Une dérogation déjà notée vaut pour l'acte suivant (même OT, technicien, date et habilitations) ;
changer de date redemande. Sous un profil technicien, l'option ne change rien. Un OT sans exigence passe toujours.
Les fenêtres « passer outre » sont T438 (fiche de l'OT) et T439 (planning).

Aucun identifiant du jeu de démo écrit en dur (rôles de tests/fixtures/demo-scenarios.json) ; date fixe 20/11/2026 ;
un serveur pour la classe, chaque test sur ses propres OT et techniciens.

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_rg8_ecritures.py" -v
"""
import csv
import io
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

SCENARIOS = scenarios_demo()
EQ_BR = SCENARIOS["equipement_br"]                     # AE-03, exige la BR
TEC_ECHUE = SCENARIOS["technicien_br_echue"]           # BR échue
TEC_VALIDE = SCENARIOS["technicien_br_valide"]
OT_A_PLANIFIER = SCENARIOS["ot_a_planifier"]           # « Préparé », équipement sans exigence
OT_A_PLANIFIER_BR = SCENARIOS["ot_a_planifier_br"]     # « Préparé », sur AE-03, pièces en stock
OT_EXIGEE = SCENARIOS["ot_habilitation_exigee"]        # « Préparé », H0V exigée par l'OT seul

DATE = "2026-11-20"
MOTIF = "Électricien du site présent ; consignation faite par lui"
DEROGER = {"passerOutreHabilitation": True, "motifDerogation": MOTIF}
SEUL_LE_RESPONSABLE = "Seul le responsable peut passer outre."
MOTIF_OBLIGATOIRE = "Pour passer outre, le motif de la dérogation est obligatoire."

# Appel d'une écriture → { accepte } ou { refus, habilitation, pieces } (Donnees.ErreurValidation) ou { erreur }.
APPEL_JS = """async ([module, fonction, args]) => {
  const cible = { Ordres, Planning, Equipe, interne: Ordres.interne }[module];
  try {
    const valeur = await cible[fonction](...args);
    return { accepte: valeur === undefined ? null : valeur };
  } catch (erreur) {
    if (!(erreur instanceof Donnees.ErreurValidation)) return { erreur: String((erreur && erreur.stack) || erreur) };
    return { refus: erreur.message, habilitation: erreur.habilitation || null, pieces: erreur.piecesManquantes || null };
  }
}"""


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def marqueur(technicien, date, liste, motif=MOTIF):
    return "dérogation habilitation : %s le %s sans %s ; motif : %s" % (technicien, date, liste, motif)


def date_fr(iso):
    return "%s/%s/%s" % (iso[8:10], iso[5:7], iso[0:4])


class TestRg8Ecritures(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.dossier = cls.serveur.dossier
        technicien = next(t for t in lire_csv(cls.dossier, "techniciens.csv") if t["id"] == TEC_ECHUE)
        cls.nom_echue = "%s %s" % (brut(technicien["prenom"]), brut(technicien["nom"]))
        cls.echeance_br = max(brut(h["date_echeance"]) for h in lire_csv(cls.dossier, "habilitations.csv")
                              if h["technicien_id"] == TEC_ECHUE and brut(h["intitule"]).upper() == "BR")

    # -- outils ----------------------------------------------------------------------------------

    def ouvrir(self, profil="responsable", technicien_id=""):
        preregler_profil(self.contexte, profil, technicien_id=technicien_id)
        self.page.goto(self.serveur.url + "/#/ot")
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    def appeler(self, module, fonction, *arguments):
        return self.page.evaluate(APPEL_JS, [module, fonction, list(arguments)])

    def accepte(self, module, fonction, *arguments):
        resultat = self.appeler(module, fonction, *arguments)
        self.assertIn("accepte", resultat, resultat)
        return resultat["accepte"]

    def refuse(self, module, fonction, *arguments):
        resultat = self.appeler(module, fonction, *arguments)
        self.assertIn("refus", resultat, resultat)
        return resultat

    def ot(self, ot_id):
        return next(o for o in lire_csv(self.dossier, "ordres_travail.csv") if o["id"] == ot_id)

    def nombre_ot(self):
        return len(lire_csv(self.dossier, "ordres_travail.csv"))

    def journal(self):
        return lire_csv(self.dossier, "journal.csv")

    def actions(self, ot_id):
        return [j["action"] for j in self.journal() if j["table"] == "ordres_travail" and j["id_ligne"] == ot_id]

    def refus_attendu(self, nom, technicien, date, liste, fin=SEUL_LE_RESPONSABLE):
        return "Affectation refusée : %s (%s) n'a pas d'habilitation valide au %s : %s. %s" % (
            nom, technicien, date_fr(date), liste, fin)

    def br_echue(self):
        return "BR (échue le %s)" % date_fr(self.echeance_br)

    def manquantes(self, refus):
        return [(m["intitule"], m["raison"], m["origines"]) for m in refus["habilitation"]["manquantes"]]

    def nouvel_ot(self, titre, **valeurs):
        return self.accepte("Ordres", "creer", dict({"equipement_id": EQ_BR, "titre": titre, "type": "correctif différé",
                                                     "priorite": "P3"}, **valeurs))

    # -- création -------------------------------------------------------------------------------

    def test_creer_refuse_sans_rien_ecrire_puis_derogation_du_responsable_au_journal(self):
        self.ouvrir()
        valeurs = {"equipement_id": EQ_BR, "titre": "T437 — création", "type": "correctif différé", "priorite": "P3",
                   "technicien_id": TEC_ECHUE, "date_prevue": DATE}
        avant_ot, avant_journal = self.nombre_ot(), len(self.journal())
        refus = self.refuse("Ordres", "creer", valeurs)
        self.assertEqual(refus["refus"], self.refus_attendu(self.nom_echue, TEC_ECHUE, DATE, self.br_echue()))
        self.assertEqual(sorted(refus["habilitation"]), ["date", "manquantes", "otId", "technicienId"])
        self.assertEqual((refus["habilitation"]["technicienId"], refus["habilitation"]["date"]), (TEC_ECHUE, DATE))
        self.assertEqual(self.manquantes(refus), [("BR", "echue", ["equipement"])])
        self.assertEqual(refus["habilitation"]["manquantes"][0]["echeance"], self.echeance_br)
        # Q7 : le responsable qui passe outre sans motif est refusé aussi (motif vide ou blanc).
        for options in ({"passerOutreHabilitation": True}, {"passerOutreHabilitation": True, "motifDerogation": " \n "}):
            with self.subTest(options=options):
                refus = self.refuse("Ordres", "creer", valeurs, options)
                self.assertEqual(refus["refus"], self.refus_attendu(self.nom_echue, TEC_ECHUE, DATE, self.br_echue(),
                                                                    MOTIF_OBLIGATOIRE))
                self.assertIsNotNone(refus["habilitation"])
        # Une option mal formée (pas exactement true) ne passe pas outre.
        self.refuse("Ordres", "creer", valeurs, {"passerOutreHabilitation": "oui", "motifDerogation": MOTIF})
        self.assertEqual((self.nombre_ot(), len(self.journal())), (avant_ot, avant_journal))   # rien d'écrit

        ot_id = self.accepte("Ordres", "creer", valeurs, DEROGER)
        ligne = self.ot(ot_id)
        self.assertEqual((ligne["technicien_id"], ligne["date_prevue"], ligne["statut"]), (TEC_ECHUE, DATE, "Créé"))
        entrees = [j for j in self.journal() if j["id_ligne"] == ot_id]
        self.assertEqual([j["action"] for j in entrees],
                         ["création — création de l'OT (manuel) ; " + marqueur(TEC_ECHUE, DATE, "BR (échue)")])
        # Qui, quand, quel OT, quelle habilitation : l'entrée de l'écriture elle-même.
        entree = entrees[0]
        self.assertEqual((entree["table"], entree["profil"], entree["poste"]), ("ordres_travail", "Responsable", "Poste test"))
        self.assertRegex(entree["date_heure"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}")
        relu = self.page.evaluate("(action) => Ordres.lireDerogation(action)", entree["action"])
        self.assertEqual(relu, {"technicienId": TEC_ECHUE, "date": DATE, "motif": MOTIF,
                                "manquantes": [{"intitule": "BR", "raison": "echue"}]})

    # -- préparation, puis « Planifier », puis replanification -----------------------------------

    def test_preparer_puis_planifier_la_derogation_notee_vaut_pour_l_acte_suivant(self):
        self.ouvrir()
        ot_id = self.nouvel_ot("T437 — préparation")                        # sans technicien : rien à contrôler
        self.assertEqual(self.accepte("Ordres", "changerStatut", ot_id, "Créé", "Préparé"), "Préparé")
        affecter = {"technicien_id": TEC_ECHUE, "date_prevue": DATE}
        refus = self.refuse("interne", "modifierOt", ot_id, affecter, "préparation")
        self.assertEqual(refus["refus"], self.refus_attendu(self.nom_echue, TEC_ECHUE, DATE, self.br_echue()))
        self.assertEqual(refus["habilitation"]["otId"], ot_id)
        self.assertEqual(self.ot(ot_id)["technicien_id"], "")

        self.assertEqual(self.accepte("interne", "modifierOt", ot_id, affecter, "préparation", DEROGER),
                         ["technicien_id", "date_prevue"])
        derniere = self.actions(ot_id)[-1]
        self.assertTrue(derniere.startswith("modification : "), derniere)
        self.assertTrue(derniere.endswith(" — préparation ; " + marqueur(TEC_ECHUE, DATE, "BR (échue)")), derniere)

        # Un champ sans rapport avec l'affectation : RG8 n'est pas revue (non rétroactive), rien n'est ajouté.
        self.assertEqual(self.accepte("interne", "modifierOt", ot_id, {"consignes": "Consigner l'armoire"}, "préparation"),
                         ["consignes"])
        self.assertEqual(self.actions(ot_id)[-1], "modification : consignes — préparation")

        # « Planifier » : même OT, technicien, date et habilitations → la dérogation notée vaut, rien n'est redemandé.
        self.assertEqual(self.accepte("Ordres", "changerStatut", ot_id, "Préparé", "Planifié"), "Planifié")
        self.assertEqual(self.actions(ot_id)[-1], "modification : statut — statut Préparé → Planifié")

        # Replanifier à une autre date redemande ; un technicien habilité passe ; revenir au jour dérogé aussi.
        refus = self.refuse("Planning", "planifier", ot_id, "Planifié", TEC_ECHUE, "2026-11-23")
        self.assertEqual(refus["habilitation"]["date"], "2026-11-23")
        self.assertEqual(self.ot(ot_id)["date_prevue"], DATE)
        self.assertEqual(self.accepte("Planning", "planifier", ot_id, "Planifié", TEC_VALIDE, "2026-11-23"),
                         {"statut": "Planifié", "avertissements": []})
        self.assertEqual(self.actions(ot_id)[-1],
                         "modification : date_prevue, technicien_id — replanification : %s le 2026-11-23" % TEC_VALIDE)
        self.accepte("Planning", "planifier", ot_id, "Planifié", TEC_ECHUE, DATE)
        self.assertNotIn("dérogation", self.actions(ot_id)[-1])
        self.assertEqual(sum("dérogation habilitation" in action for action in self.actions(ot_id)), 1)

    def test_changer_statut_vers_planifie_refuse_puis_derogation(self):
        # Affectation d'avant la 2.2 (sans contrôle) : « Planifier » la revoit (RG8 dans les erreurs du passage).
        self.ouvrir()
        ot_id = self.nouvel_ot("T437 — statut")
        self.accepte("Ordres", "changerStatut", ot_id, "Créé", "Préparé")
        self.page.evaluate("""([id, technicien, date]) => Donnees.modifier('ordres_travail', (lignes) => {
            Object.assign(lignes.find((o) => o.id === id), { technicien_id: technicien, date_prevue: date }); },
            { journal: false })""", [ot_id, TEC_ECHUE, DATE])
        verification = self.page.evaluate("(id) => Ordres.verifierPassage(Donnees.trouver('ordres_travail', id), 'Planifié')", ot_id)
        self.assertFalse(verification["ok"])
        self.assertEqual(verification["erreurs"], [self.refus_attendu(self.nom_echue, TEC_ECHUE, DATE, self.br_echue())])
        refus = self.refuse("Ordres", "changerStatut", ot_id, "Préparé", "Planifié")
        self.assertEqual(refus["refus"], verification["erreurs"][0])
        self.assertEqual(refus["habilitation"]["otId"], ot_id)
        self.assertEqual(self.ot(ot_id)["statut"], "Préparé")
        self.assertEqual(self.accepte("Ordres", "changerStatut", ot_id, "Préparé", "Planifié", None, DEROGER), "Planifié")
        self.assertEqual(self.actions(ot_id)[-1], "modification : statut — statut Préparé → Planifié ; "
                         + marqueur(TEC_ECHUE, DATE, "BR (échue)"))

    # -- planning ---------------------------------------------------------------------------------

    def test_planning_refuse_puis_derogation_et_exigence_portee_par_l_ot(self):
        self.ouvrir()
        refus = self.refuse("Planning", "planifier", OT_A_PLANIFIER_BR, "Préparé", TEC_ECHUE, DATE)
        self.assertEqual(refus["refus"], self.refus_attendu(self.nom_echue, TEC_ECHUE, DATE, self.br_echue()))
        self.assertEqual((refus["habilitation"]["otId"], refus["pieces"]), (OT_A_PLANIFIER_BR, []))
        refus = self.refuse("Planning", "planifier", OT_A_PLANIFIER_BR, "Préparé", TEC_ECHUE, DATE,
                            {"passerOutreHabilitation": True, "motifDerogation": ""})
        self.assertTrue(refus["refus"].endswith(MOTIF_OBLIGATOIRE), refus["refus"])
        ligne = self.ot(OT_A_PLANIFIER_BR)
        self.assertEqual((ligne["statut"], ligne["technicien_id"]), ("Préparé", ""))

        self.assertEqual(self.accepte("Planning", "planifier", OT_A_PLANIFIER_BR, "Préparé", TEC_ECHUE, DATE, DEROGER),
                         {"statut": "Planifié", "avertissements": []})
        ligne = self.ot(OT_A_PLANIFIER_BR)
        self.assertEqual((ligne["statut"], ligne["technicien_id"], ligne["date_prevue"]), ("Planifié", TEC_ECHUE, DATE))
        derniere = self.actions(OT_A_PLANIFIER_BR)[-1]
        self.assertTrue(derniere.endswith(" — planification : %s le %s (Préparé → Planifié) ; %s"
                                          % (TEC_ECHUE, DATE, marqueur(TEC_ECHUE, DATE, "BR (échue)"))), derniere)

        # H0V exigée par l'OT seul (équipement sans exigence) : un technicien sans habilitation est refusé.
        nouveau = self.accepte("Equipe", "creerTechnicien", {"nom": "Sans habilitation", "prenom": "Planning"})
        refus = self.refuse("Planning", "planifier", OT_EXIGEE, "Préparé", nouveau, DATE)
        self.assertEqual(self.manquantes(refus), [("H0V", "absente", ["ot"])])
        self.assertEqual(refus["refus"], self.refus_attendu("Planning Sans habilitation", nouveau, DATE, "H0V (absente)"))
        self.assertEqual(self.ot(OT_EXIGEE)["statut"], "Préparé")

    # -- profil technicien : aucun moyen de passer outre (CS178) ---------------------------------

    def test_technicien_l_option_ne_change_rien(self):
        self.ouvrir(profil="technicien", technicien_id=TEC_ECHUE)
        self.assertFalse(self.page.evaluate("App.estResponsable()"))
        planifie = self.page.evaluate("""() => Donnees.lignes('ordres_travail').find((o) => o.statut === 'Planifié' && o.technicien_id !== %r
            && Ordres.habilitationsExigees(o).some((e) => e.intitule.toUpperCase() === 'BR')).id""" % TEC_ECHUE)
        avant = self.ot(planifie)
        avant_ot, avant_journal = self.nombre_ot(), len(self.journal())
        valeurs = {"equipement_id": EQ_BR, "titre": "T437 — technicien", "type": "correctif différé", "priorite": "P3",
                   "technicien_id": TEC_ECHUE, "date_prevue": DATE}
        for module, fonction, arguments in (
                ("Ordres", "creer", [valeurs, DEROGER]),
                ("interne", "modifierOt", [planifie, {"technicien_id": TEC_ECHUE, "date_prevue": DATE}, "préparation", DEROGER]),
                ("Planning", "planifier", [planifie, "Planifié", TEC_ECHUE, DATE, DEROGER])):
            with self.subTest(fonction=fonction):
                refus = self.refuse(module, fonction, *arguments)
                self.assertEqual(refus["refus"], self.refus_attendu(self.nom_echue, TEC_ECHUE, DATE, self.br_echue()))
                self.assertIsNotNone(refus["habilitation"])
        self.assertEqual((self.nombre_ot(), len(self.journal())), (avant_ot, avant_journal))
        self.assertEqual(self.ot(planifie), avant)

    # -- OT sans exigence (CS180) --------------------------------------------------------------------

    def test_ot_sans_exigence_passe_toujours(self):
        self.ouvrir()
        self.assertEqual(self.page.evaluate("(id) => Ordres.habilitationsExigees(id)", OT_A_PLANIFIER), [])
        equipement = self.ot(OT_A_PLANIFIER)["equipement_id"]
        nouveau = self.accepte("Equipe", "creerTechnicien", {"nom": "Sans habilitation", "prenom": "Libre"})
        ot_id = self.accepte("Ordres", "creer", {"equipement_id": equipement, "titre": "T437 — sans exigence",
                                                 "type": "correctif différé", "priorite": "P3", "technicien_id": nouveau,
                                                 "date_prevue": DATE}, DEROGER)
        self.assertEqual(self.actions(ot_id), ["création — création de l'OT (manuel)"])   # rien à déroger, rien noté
        self.assertEqual(self.accepte("Planning", "planifier", OT_A_PLANIFIER, "Préparé", nouveau, DATE),
                         {"statut": "Planifié", "avertissements": []})
        self.assertFalse(any("dérogation" in action or "habilitation" in action for action in self.actions(OT_A_PLANIFIER)))
        self.assertEqual(self.ot(OT_A_PLANIFIER)["technicien_id"], nouveau)

    # -- fiche de l'OT : aucune erreur JavaScript (T447, après le retrait de journaliserHabilitation) ------

    def ouvrir_fiche(self, ot_id):
        self.page.goto(self.serveur.url + "/#/ot/" + ot_id)
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")
        self.assertIn(ot_id, self.page.inner_text("body"))

    def test_fiche_d_un_ot_dont_l_habilitation_manque_sans_erreur_javascript(self):
        self.ouvrir()
        ot_id = self.nouvel_ot("T447 — fiche")
        # Affectation refusée sans dérogation : la fiche de l'OT s'ouvre.
        self.refuse("interne", "modifierOt", ot_id, {"technicien_id": TEC_ECHUE, "date_prevue": DATE}, "préparation")
        self.ouvrir_fiche(ot_id)
        # Dérogation du responsable, notée au journal par l'écriture elle-même : la fiche s'ouvre.
        self.accepte("interne", "modifierOt", ot_id, {"technicien_id": TEC_ECHUE, "date_prevue": DATE}, "préparation", DEROGER)
        self.assertIn("dérogation habilitation", self.actions(ot_id)[-1])
        self.ouvrir_fiche(ot_id)
        self.ouvrir_fiche(OT_EXIGEE)


if __name__ == "__main__":
    unittest.main()
