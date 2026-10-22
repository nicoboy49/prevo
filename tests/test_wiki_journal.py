"""Journal du wiki : validation, rejet, à refaire, rattrapage, relance, écriture à la main, contradictions,
visibilité, intégrité, problèmes de données (lot 6 refondu, tâche T117 ; ARCHITECTURE.md §20.2, §20.7 ; D105, D107 ;
CS101, CS102).

    profil        : seul le responsable valide, rejette, relance, écrit et tranche ; un autre profil ne change rien ;
    validation    : enchaînée dans l'ordre, d'un bloc (une entrée qui crée une page et en modifie une autre : tout ou
                    rien), version vérifiée (une page changée fait passer l'entrée « à refaire », et ses suivantes) ;
                    refus d'une entrée dont une plus ancienne en attente touche une même page ; « valider la
                    sélection » refuse une contradiction ; texte, OT cités, liens, version, origine, modèle, dernière
                    entrée et validateur posés ;
    rattrapage    : page écrite mais statut non écrit → « validée » au prochain affichage ;
    rejet         : motif obligatoire ; les suivantes qui touchent une même page passent « à refaire » (en cascade),
                    les autres non ; relance d'un OT rejeté ;
    à la main     : contrôles du §20.6 (retrait permis ; OT permis, nombres, sécurité refusés), entrée « manuel »
                    avec avant et après, propositions en attente sur la page « à refaire », création (mode, savoir-
                    faire rattaché à un article), archivage, conflit de version, échec de l'écriture de la page ;
    contradictions: vues sur la page par tous les profils une fois la proposition validée, « observation antérieure »
                    pour un OT antérieur, fermées seulement par le responsable, décision au journal ;
    visibilité    : « à valider » invisible aux autres profils, en modes démo, dossier et serveur ;
    intégrité     : chaîne des entrées appliquées, ordre des dates, envois simultanés ;
    données       : problèmes du wiki dans Donnees.problemes().

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_journal.py" -v
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import test_wiki_ingestion as ingestion
from commun import (CasNavigateur, RACINE, ServeurPrevo, ServeurStatique, attendre_pret, charger_scripts,
                    installer_dossier_simule, preregler_profil, url_fichier)
from faux_fournisseur_ia import FauxFournisseur

SCRIPTS = ingestion.SCRIPTS + ["js/modules/wiki-journal.js"]
EN_FILE = ingestion.EN_FILE
NOM = "Nicolas"
PROFIL_JS = """(responsable) => { window.App = { estResponsable: () => responsable, libelleProfil: () => 'Responsable',
  profil: responsable ? { type: 'responsable', nom: 'Nicolas' } : { type: 'technicien', nom: 'Tech' } }; }"""
APPEL_JS = """async ([fonction, args]) => { try { return { ok: true, valeur: await Wiki[fonction](...args) }; }
  catch (e) { return { ok: false, nom: e.name, message: e.message }; } }"""
ETAT_JS = """() => ({ pages: Donnees.lignes('wiki_pages').map((l) => Object.assign({}, l)),
  journal: Donnees.lignes('wiki_journal').map((l) => Object.assign({}, l)) })"""
# La base d'essai de test_wiki_ingestion a des pages avec un texte : l'entrée validée de OT-2026-0007 reçoit les
# changements qui les ont écrites, pour que le wiki de départ soit intègre.
COHERENT_JS = """() => Donnees.modifier('wiki_journal', (lignes) => {
  lignes.find((e) => e.id === 'WJ-00001').changements = JSON.stringify(Donnees.lignes('wiki_pages').filter((l) => l.texte)
    .map((l) => ({ page: l.id, cle: 'WP:' + l.id, titre: l.titre, type: l.type, creation: true, version_avant: 0, avant: '',
      apres: l.texte })));
}, { journal: false })"""


class CasJournal(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur(lenteur_s=1)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)

    def setUp(self):
        super().setUp()
        ingestion.regler_ia(self.contexte, url=self.faux.url)
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate(ingestion.CHARGER_JS, ingestion.BASE)
        self.page.evaluate(COHERENT_JS)
        self.profil(True)
        self.assertEqual(self.integrite(), {"ok": True, "ecarts": []})

    def profil(self, responsable):
        self.page.evaluate(PROFIL_JS, responsable)

    def traiter(self, ids, modele="faux"):
        self.page.evaluate("(modele) => Ia.enregistrerReglages({ modele })", modele)
        bilan = self.page.evaluate(ingestion.TRAITER_JS, [ids, {}])
        self.assertIsNone(bilan["erreur"], bilan)
        return bilan

    def appel(self, fonction, *args):
        return self.page.evaluate(APPEL_JS, [fonction, list(args)])

    def ok(self, fonction, *args):
        resultat = self.appel(fonction, *args)
        self.assertTrue(resultat["ok"], resultat)
        return resultat["valeur"]

    def refus(self, attendu, fonction, *args):
        resultat = self.appel(fonction, *args)
        self.assertFalse(resultat["ok"], resultat)
        self.assertIn(attendu, resultat["message"])
        return resultat["message"]

    def entrees(self):
        """OT → entrée d'ingestion la plus récente (hors OT-2026-0007, déjà intégré dans la base)."""
        par_ot = {}
        for entree in self.page.evaluate("Donnees.lignes('wiki_journal')"):
            if entree["nature"] == "ingestion" and entree["ot_id"] != "OT-2026-0007":
                par_ot[entree["ot_id"]] = entree
        return par_ot

    def id_de(self, ot):
        return self.entrees()[ot]["id"]

    def ligne(self, page_id):
        return self.page.evaluate("(id) => Donnees.trouver('wiki_pages', id)", page_id)

    def etat(self):
        return self.page.evaluate(ETAT_JS)

    def integrite(self, envois=None):
        return self.page.evaluate("(envois) => Wiki.verifierIntegrite({ envois })", envois or [])


class TestValidation(CasJournal):

    def setUp(self):
        super().setUp()
        self.bilan = self.traiter(EN_FILE)

    def test_seul_le_responsable_ecrit(self):
        self.profil(False)
        avant = self.etat()
        id_0003 = self.id_de("OT-2026-0003")
        for fonction, args in (("valider", [[id_0003]]), ("rejeter", [id_0003, "non"]), ("remettreEnFile", [id_0003]),
                               ("ecrire", [{"pageId": "EQ-0001"}, "## Ce qui revient\n- Fuite [OT-2026-0003]"]),
                               ("trancher", [id_0003, 0, "ancien", ""])):
            with self.subTest(fonction=fonction):
                self.refus("Réservé au responsable", fonction, *args)
        self.assertEqual(self.etat(), avant)

    def test_validation_enchainee_et_d_un_bloc(self):
        entrees = self.entrees()
        self.assertEqual({ot: e["statut"] for ot, e in entrees.items()}, {ot: "à valider" for ot in EN_FILE})
        # 0008 ne passe pas avant 0003 et 0001, plus anciennes et sur la même page : rien n'est fait.
        avant = self.etat()
        message = self.refus("Validez d'abord", "valider", [entrees["OT-2026-0008"]["id"]])
        self.assertIn(entrees["OT-2026-0003"]["id"], message)
        self.assertEqual(self.etat(), avant)
        # 0003 seule, puis 0001 et 0008 ensemble (sélection) : dans l'ordre, chacune d'un bloc.
        self.assertEqual(self.ok("valider", [entrees["OT-2026-0003"]["id"]]),
                         {"validees": [entrees["OT-2026-0003"]["id"]], "aRefaire": []})
        po01 = self.ligne("WP-0001")
        apres_0003 = [c for c in json.loads(entrees["OT-2026-0003"]["changements"]) if c["cle"] == "EQ:EQ-0001"][0]["apres"]
        self.assertEqual((po01["texte"], po01["version"], po01["origine"], po01["modele"], po01["valide_par"]),
                         (apres_0003, "2", "IA", "faux", NOM))
        self.assertEqual(po01["derniere_entree"], entrees["OT-2026-0003"]["id"])
        self.assertEqual(po01["ot_cites"], "OT-2026-0007;OT-2026-0003")
        self.assertEqual(po01["liens"], "WP-0006")                                   # [[Cavitation]]
        entree = self.page.evaluate("(id) => Donnees.trouver('wiki_journal', id)", entrees["OT-2026-0003"]["id"])
        self.assertEqual((entree["statut"], entree["decide_par"]), ("validée", NOM))
        self.assertTrue(entree["decide_le"])
        self.assertEqual([c["page"] for c in json.loads(entree["changements"])], ["WP-0001"])
        selection = [entrees["OT-2026-0008"]["id"], entrees["OT-2026-0001"]["id"]]
        self.assertEqual(self.ok("valider", selection)["validees"], [entrees["OT-2026-0001"]["id"], entrees["OT-2026-0008"]["id"]])
        po01 = self.ligne("WP-0001")
        self.assertEqual(po01["version"], "4")
        self.assertEqual(po01["derniere_entree"], entrees["OT-2026-0008"]["id"])
        astuce = self.page.evaluate("Donnees.lignes('wiki_pages').find((l) => l.titre === \"Astuce de l'OT-2026-0001\")")
        # La validation inscrit la page de chaque changement, y compris celle qu'elle a créée.
        self.assertEqual([c["page"] for c in json.loads(self.entrees()["OT-2026-0001"]["changements"])], ["WP-0001", astuce["id"]])
        self.assertEqual((astuce["type"], astuce["equipement_id"], astuce["version"], astuce["origine"], astuce["cle"]),
                         ("savoir-faire", "EQ-0001", "1", "IA", "astuce de l ot 2026 0001"))
        self.assertEqual(astuce["ot_cites"], "OT-2026-0001")
        # L'état proposé de PO-01 est maintenant l'état validé ; le wiki est intègre.
        self.assertEqual(self.page.evaluate("Wiki.etatPropose().get('EQ:EQ-0001').texte"), po01["texte"])
        self.assertEqual(self.integrite(self.bilan["envois"]), {"ok": True, "ecarts": []})

    def test_page_changee_entree_a_refaire_et_rien_d_ecrit(self):
        entrees = self.entrees()
        self.ok("valider", [entrees["OT-2026-0003"]["id"]])
        # Un autre poste réécrit la page de PO-01 : la proposition de 0001 (deux pages) n'est pas appliquée du tout.
        self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => {
          const l = lignes.find((x) => x.id === 'WP-0001'); l.version = String(Number(l.version) + 1); })""")
        nombre = self.page.evaluate("Donnees.lignes('wiki_pages').length")
        bilan = self.ok("valider", [entrees["OT-2026-0001"]["id"]])
        self.assertEqual(bilan["validees"], [])
        self.assertEqual(bilan["aRefaire"], [entrees["OT-2026-0001"]["id"], entrees["OT-2026-0008"]["id"]])
        self.assertEqual(self.page.evaluate("Donnees.lignes('wiki_pages').length"), nombre)     # astuce non créée
        apres = self.entrees()
        for ot in ("OT-2026-0001", "OT-2026-0008"):
            self.assertEqual((apres[ot]["statut"], apres[ot]["changements"], apres[ot]["ordre"]), ("à refaire", "", ""))
        self.assertIn("OT-2026-0001", self.page.evaluate("Wiki.file().map((e) => e.ot_id)"))
        self.assertEqual(apres["OT-2026-0002"]["statut"], "à valider")

    def test_rejet_motif_cascade_et_relance(self):
        entrees = self.entrees()
        self.refus("motif du rejet est obligatoire", "rejeter", entrees["OT-2026-0003"]["id"], "  ")
        # Une proposition construite seulement sur la page créée par 0001 (lien vers elle) : elle suit 0001 en cascade.
        self.page.evaluate("""() => Donnees.modifier('wiki_journal', (lignes) => { lignes.push({ id: 'WJ-00099', nature: 'ingestion',
          ot_id: 'OT-2026-0002', statut: 'à valider', ordre: '99', pages: 'WP:WP-0006', contradictions: '[]',
          changements: JSON.stringify([{ page: 'WP-0006', cle: 'WP:WP-0006', version_avant: 1, avant: '', creation: false,
            apres: "## Symptômes\\n- Voir [[Astuce de l'OT-2026-0001]] [OT-2026-0007]" }]) }); }, { journal: false })""")
        resultat = self.ok("rejeter", entrees["OT-2026-0003"]["id"], "Phrase mal tournée")
        self.assertEqual(resultat, {"rejetee": entrees["OT-2026-0003"]["id"],
                                    "aRefaire": [entrees["OT-2026-0001"]["id"], entrees["OT-2026-0008"]["id"], "WJ-00099"]})
        self.page.evaluate("""() => Donnees.modifier('wiki_journal', (lignes) => {
          lignes.splice(lignes.findIndex((e) => e.id === 'WJ-00099'), 1); }, { journal: false })""")
        apres = self.entrees()
        self.assertEqual((apres["OT-2026-0003"]["statut"], apres["OT-2026-0003"]["motif"], apres["OT-2026-0003"]["decide_par"]),
                         ("rejetée", "Phrase mal tournée", NOM))
        self.assertEqual({ot: apres[ot]["statut"] for ot in EN_FILE}, {
            "OT-2026-0004": "à valider", "OT-2026-0003": "rejetée", "OT-2026-0001": "à refaire", "OT-2026-0002": "à valider",
            "OT-2026-0006": "à valider", "OT-2026-0008": "à refaire"})
        self.assertEqual(apres["OT-2026-0001"]["motif"], "à refaire : " + entrees["OT-2026-0003"]["id"] + " rejetée")
        self.assertEqual(self.ligne("WP-0001")["version"], "1")                     # rien n'a été appliqué
        # Rejet de 0004 : 0006 (même équipement CV-01) passe « à refaire ».
        self.assertEqual(self.ok("rejeter", entrees["OT-2026-0004"]["id"], "Hors sujet")["aRefaire"],
                         [entrees["OT-2026-0006"]["id"]])
        # Relance de 0003 : une nouvelle entrée en file ; pas deux fois.
        nouvelle = self.ok("remettreEnFile", entrees["OT-2026-0003"]["id"])
        self.assertEqual(self.entrees()["OT-2026-0003"]["id"], nouvelle)
        self.assertEqual(self.entrees()["OT-2026-0003"]["statut"], "en file")
        self.refus("déjà une entrée", "remettreEnFile", entrees["OT-2026-0003"]["id"])
        self.refus("rejetée ou refusée", "remettreEnFile", entrees["OT-2026-0002"]["id"])
        # Les OT « à refaire » sont retraités sur le nouvel état.
        bilan = self.traiter([])
        self.assertEqual(bilan["acceptees"], 4)
        self.assertEqual({ot: e["statut"] for ot, e in self.entrees().items()}, {
            "OT-2026-0004": "rejetée", "OT-2026-0003": "à valider", "OT-2026-0001": "à valider", "OT-2026-0002": "à valider",
            "OT-2026-0006": "à valider", "OT-2026-0008": "à valider"})

    def test_rattrapage_d_une_validation_interrompue(self):
        id_0003 = self.id_de("OT-2026-0003")
        self.page.evaluate("""() => { const modifier = Donnees.modifier; window.restaurer = () => { Donnees.modifier = modifier; };
          Donnees.modifier = function (table) { if (table === 'wiki_journal') return Promise.reject(new Error('disque plein'));
            return modifier.apply(this, arguments); }; }""")
        self.refus("disque plein", "valider", [id_0003])
        self.page.evaluate("window.restaurer()")
        self.assertEqual(self.ligne("WP-0001")["derniere_entree"], id_0003)
        self.assertEqual(self.entrees()["OT-2026-0003"]["statut"], "à valider")
        self.assertEqual(self.ok("rattraper"), 1)
        entree = self.entrees()["OT-2026-0003"]
        self.assertEqual((entree["statut"], entree["decide_par"]), ("validée", NOM))
        self.assertEqual([c["page"] for c in json.loads(entree["changements"])], ["WP-0001"])
        self.assertEqual(self.ok("rattraper"), 0)
        self.assertEqual(self.integrite(), {"ok": True, "ecarts": []})


class TestContradictions(CasJournal):

    def test_selection_refusee_puis_tranchee_par_le_responsable(self):
        self.traiter(["OT-2026-0008"], "faux-contradiction")
        self.traiter(["OT-2026-0002"])
        entrees = self.entrees()
        id_0008, id_0002 = entrees["OT-2026-0008"]["id"], entrees["OT-2026-0002"]["id"]
        self.refus("à valider une à une", "valider", [id_0008, id_0002])
        # Avant validation : rien sur la page.
        self.assertEqual(self.page.evaluate("Wiki.page('EQ-0001').contradictions"), [])
        self.ok("valider", [id_0008])
        for responsable in (False, True):
            self.profil(responsable)
            contradictions = self.page.evaluate("Wiki.page('EQ-0001').contradictions")
            self.assertEqual(len(contradictions), 1)
            self.assertEqual({k: contradictions[0][k] for k in ("entreeId", "rang", "otSource", "phrase", "anterieure", "libelle")},
                             {"entreeId": id_0008, "rang": 0, "otSource": "OT-2026-0008",
                              "phrase": "Fuite de garniture au démarrage, fréquent ici", "anterieure": False,
                              "libelle": "Ce que dit le nouvel OT"})
        # La phrase contredite n'a pas été écrasée.
        self.assertIn("- Fuite de garniture au démarrage, fréquent ici [OT-2026-0007]", self.ligne("WP-0001")["texte"])
        self.profil(False)
        self.refus("Réservé au responsable", "trancher", id_0008, 0, "ancien", "")
        self.profil(True)
        self.refus("Décision inconnue", "trancher", id_0008, 0, "peut-être", "")
        resultat = self.ok("trancher", id_0008, 0, "nouveau", "Cause confirmée par le comparateur")
        self.assertEqual(resultat["pageId"], "EQ-0001")
        contradiction = json.loads(self.entrees()["OT-2026-0008"]["contradictions"])[0]
        self.assertEqual({k: contradiction[k] for k in ("statut", "decision", "decide_par", "note")},
                         {"statut": "fermée", "decision": "nouveau", "decide_par": NOM, "note": "Cause confirmée par le comparateur"})
        decision = self.page.evaluate("(id) => Donnees.trouver('wiki_journal', id)", resultat["decisionId"])
        self.assertEqual((decision["nature"], decision["statut"], decision["ot_id"], decision["motif"], decision["pages"]),
                         ("décision", "appliquée", "OT-2026-0008", "Cause confirmée par le comparateur", "EQ:EQ-0001"))
        self.assertEqual(json.loads(decision["contradictions"])[0]["entree"], id_0008)
        self.assertEqual(self.page.evaluate("Wiki.page('EQ-0001').contradictions"), [])
        self.refus("pas ouverte", "trancher", id_0008, 0, "ancien", "")

    def test_observation_anterieure(self):
        self.traiter(["OT-2026-0003"], "faux-contradiction")              # février, la page cite avril
        entree = self.entrees()["OT-2026-0003"]
        self.assertEqual(entree["anterieure"], "1")
        self.ok("valider", [entree["id"]])
        contradiction = self.page.evaluate("Wiki.page('EQ-0001').contradictions")[0]
        self.assertEqual((contradiction["anterieure"], contradiction["libelle"]),
                         (True, "Observation antérieure aux faits de la page"))


class TestEcritureALaMain(CasJournal):

    TEXTE = ("## Ce qui revient\n- Fuite de garniture au démarrage, fréquent ici [OT-2026-0007]\n"
             "## Ce qui a réglé le problème\n- Garniture usée remplacée [OT-2026-0001]")

    def test_ecriture_controles_journal_et_propositions_a_refaire(self):
        self.traiter(["OT-2026-0003"])
        id_0003 = self.id_de("OT-2026-0003")
        # Retrait de la phrase du lien : permis à la main.
        resultat = self.ok("ecrire", {"pageId": "EQ-0001"}, self.TEXTE, {"version": 1, "motif": "Remise en ordre"})
        self.assertEqual((resultat["pageId"], resultat["ligneId"]), ("EQ-0001", "WP-0001"))
        po01 = self.ligne("WP-0001")
        self.assertEqual((po01["texte"], po01["version"], po01["origine"], po01["valide_par"], po01["derniere_entree"]),
                         (self.TEXTE, "2", "IA et manuel", NOM, resultat["entreeId"]))
        self.assertEqual((po01["ot_cites"], po01["liens"]), ("OT-2026-0007;OT-2026-0001", ""))
        entree = self.page.evaluate("(id) => Donnees.trouver('wiki_journal', id)", resultat["entreeId"])
        self.assertEqual((entree["nature"], entree["statut"], entree["decide_par"], entree["motif"], entree["pages"]),
                         ("manuel", "appliquée", NOM, "Remise en ordre", "EQ:EQ-0001"))
        changement = json.loads(entree["changements"])[0]
        self.assertEqual((changement["page"], changement["version_avant"], changement["apres"]), ("WP-0001", 1, self.TEXTE))
        self.assertEqual(changement["avant"], ingestion.TEXTE_PO01)
        # La proposition en attente sur PO-01 repart dans la file.
        self.assertEqual(self.page.evaluate("(id) => Donnees.trouver('wiki_journal', id).statut", id_0003), "à refaire")
        self.assertEqual(self.integrite(), {"ok": True, "ecarts": []})

    def test_refus_des_controles_et_du_conflit_de_version(self):
        avant = self.etat()
        cas = [
            ("Le wiki ne contient pas de consigne de sécurité", self.TEXTE + "\n- Porter des gants [OT-2026-0001]", None),
            ("OT cité hors des OT permis : OT-2026-0999", self.TEXTE + "\n- Bruit [OT-2026-0999]", None),
            ("OT cité hors des OT permis : OT-2026-0005", self.TEXTE + "\n- Bruit [OT-2026-0005]", None),  # pas clôturé administrativement
            ("nombre « 7 » absent des OT cités", self.TEXTE + "\n- Pression à 7 bar [OT-2026-0001]", None),
            ("phrase sans OT cité", self.TEXTE + "\n- Bruit au démarrage", None),
            ("La page a été modifiée entre-temps", self.TEXTE, {"version": 0}),
        ]
        for attendu, texte, options in cas:
            with self.subTest(attendu=attendu):
                self.refus(attendu, "ecrire", {"pageId": "EQ-0001"}, texte, options or {})
        self.assertEqual(self.etat(), avant)
        # Le nombre d'un OT cité est permis (2.5 h d'arrêt de OT-2026-0001).
        self.ok("ecrire", {"pageId": "EQ-0001"}, self.TEXTE + "\n- Arrêt de 2.5 h [OT-2026-0001]")

    def test_creation_archivage_et_echec_de_l_ecriture(self):
        mode = self.ok("ecrire", {"nouvelle": {"type": "mode", "titre": "Corrosion des brides"}},
                       "## Causes\n- Eau dans le circuit, voir [[Filtre à huile]] [OT-2026-0002]")
        ligne = self.ligne(mode["ligneId"])
        self.assertEqual((mode["pageId"], ligne["type"], ligne["origine"], ligne["version"], ligne["liens"], ligne["cle"]),
                         (mode["ligneId"], "mode", "manuel", "1", "ART-0003", "corrosion des brides"))
        self.assertEqual(self.page.evaluate("(id) => Wiki.page(id).titre", mode["pageId"]), "Corrosion des brides")
        self.refus("une page de ce titre existe déjà", "ecrire", {"nouvelle": {"type": "mode", "titre": "Corrosion des brides"}},
                   "## Causes\n- Eau [OT-2026-0002]")
        geste = self.ok("ecrire", {"nouvelle": {"type": "savoir-faire", "titre": "Poser le kit HC 50", "rattacheA": "ART-0001"}},
                        "## Étapes\n- Marquer la position de l'accouplement [OT-2026-0001]")
        self.assertEqual(self.ligne(geste["ligneId"])["article_id"], "ART-0001")
        self.refus("un savoir-faire se rattache", "ecrire",
                   {"nouvelle": {"type": "savoir-faire", "titre": "Geste libre", "rattacheA": mode["pageId"]}},
                   "## Étapes\n- Rincer [OT-2026-0002]")
        self.refus("Une page d'équipement ne se crée pas", "ecrire", {"nouvelle": {"type": "équipement", "titre": "ZZ"}}, "")
        # Archivage : le texte reste, la page sort du wiki ; on ne l'écrit plus.
        archive = self.ok("ecrire", {"pageId": "WP-0006"}, None, {"archiver": True})
        self.assertEqual(self.ligne("WP-0006")["statut"], "archivée")
        entree = self.page.evaluate("(id) => Donnees.trouver('wiki_journal', id)", archive["entreeId"])
        self.assertTrue(json.loads(entree["changements"])[0]["archivage"])
        self.refus("est archivée", "ecrire", {"pageId": "WP-0006"}, "## Symptômes\n- Bruit [OT-2026-0001]")
        # L'écriture de la page échoue : l'entrée « manuel » passe « refusée » avec la raison.
        self.page.evaluate("""() => { const modifier = Donnees.modifier;
          Donnees.modifier = function (table) { if (table === 'wiki_pages') return Promise.reject(new Error('disque plein'));
            return modifier.apply(this, arguments); }; }""")
        self.refus("disque plein", "ecrire", {"pageId": "EQ-0001"}, self.TEXTE)
        derniere = self.page.evaluate("Donnees.lignes('wiki_journal').filter((e) => e.nature === 'manuel').pop()")
        self.assertEqual((derniere["statut"], derniere["raisons"]), ("refusée", "disque plein"))


class TestIntegriteEtDonnees(CasJournal):

    def test_integrite_chaine_dates_et_envois(self):
        bilan = self.traiter(EN_FILE)
        ids = [self.id_de(ot) for ot in ("OT-2026-0004", "OT-2026-0003", "OT-2026-0001", "OT-2026-0002", "OT-2026-0006", "OT-2026-0008")]
        self.ok("valider", ids[:1])
        self.ok("valider", ids[1:4])
        self.ok("valider", ids[4:])
        self.assertEqual(self.integrite(bilan["envois"]), {"ok": True, "ecarts": []})
        # Deux envois en même temps sur une même page : écart.
        faux_envois = [{"ot": "A", "cles": ["EQ:EQ-0001"], "debut": 1, "fin": 4}, {"ot": "B", "cles": ["EQ:EQ-0001"], "debut": 2, "fin": 3}]
        self.assertIn("envois simultanés de A et B", [e["message"] for e in self.integrite(faux_envois)["ecarts"]])
        # Texte changé hors du journal : écart sur la page.
        self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => {
          lignes.find((l) => l.id === 'WP-0001').texte += '\\n- Ajout sans journal [OT-2026-0001]'; })""")
        ecarts = self.integrite()["ecarts"]
        self.assertEqual([(e["page"], e["message"]) for e in ecarts],
                         [("PO-01 — Pompe de process A", "le texte de la page n'est pas l'« après » de sa dernière entrée")])
        # Un « avant » qui n'est pas l'« après » de l'entrée précédente : chaîne rompue.
        self.page.evaluate("""(id) => Donnees.modifier('wiki_journal', (lignes) => { const e = lignes.find((x) => x.id === id);
          const changements = JSON.parse(e.changements); changements[0].avant += ' (falsifié)';
          e.changements = JSON.stringify(changements); })""", ids[2])
        self.assertIn((ids[2], "son « avant » n'est pas le texte laissé par l'entrée précédente"),
                      [(e["entree"], e["message"]) for e in self.integrite()["ecarts"]])
        # 0001 (mars) est intégrée après OT-2026-0007 (avril) : permis parce qu'elle est notée antérieure, écart sinon.
        self.assertEqual(self.entrees()["OT-2026-0001"]["anterieure"], "1")
        self.page.evaluate("""(id) => Donnees.modifier('wiki_journal', (lignes) => {
          lignes.find((e) => e.id === id).anterieure = '0'; })""", ids[2])
        self.assertIn("OT OT-2026-0001 intégré après un OT plus récent", [e["message"] for e in self.integrite()["ecarts"]])

    def test_problemes_du_wiki_dans_donnees(self):
        problemes = """() => Donnees.problemes().filter((p) => p.type === 'wiki')
          .map((p) => [p.gravite, p.table, p.id, p.champ, p.valeur])"""
        self.page.evaluate("""async () => {
          await Donnees.modifier('wiki_pages', (lignes) => {
            lignes.forEach((l) => { l.ot_cites = (l.texte.match(/OT-\\d{4}-\\d{4}/g) || []).join(';');
              l.cle = Wiki.comparable(l.titre); });
            Object.assign(lignes.find((l) => l.id === 'WP-0002'), { liens: 'WP-0009;WP-0099;EQ-0001' });
            Object.assign(lignes.find((l) => l.id === 'WP-0005'), { ot_cites: 'OT-2026-0999' });
            Object.assign(lignes.find((l) => l.id === 'WP-0006'), { ot_cites: '' });
            Object.assign(lignes.find((l) => l.id === 'WP-0008'), { cle: 'changer la garniture de po 01' });
          });
          await Donnees.modifier('wiki_journal', (lignes) => {
            lignes.push({ id: 'WJ-00050', nature: 'ingestion', ot_id: 'OT-2026-0002', statut: 'validée', ordre: '50',
              changements: JSON.stringify([{ page: 'WP-0001', cle: 'EQ:EQ-0001', version_avant: 5, avant: '', apres: '' }]),
              contradictions: JSON.stringify([{ page: 'Cavitation', pageCle: 'WP:WP-0006', phrase: 'x', statut: 'ouverte' }]),
              decide_le: '2026-01-02 10:00' });
            lignes.push({ id: 'WJ-00051', nature: 'ingestion', ot_id: 'OT-2026-0004', statut: 'validée', ordre: '51',
              changements: '[]', decide_le: Donnees.maintenant(),
              contradictions: JSON.stringify([{ page: 'Desserrage', pageCle: 'WP:WP-0007', phrase: 'y', statut: 'ouverte' }]) });
          });
        }""")
        self.assertEqual(sorted(map(tuple, self.page.evaluate(problemes))), sorted([
            ("attention", "wiki_pages", "WP-0002", "liens", "WP-0009"),          # page archivée
            ("attention", "wiki_pages", "WP-0002", "liens", "WP-0099"),          # page inexistante
            ("attention", "wiki_pages", "WP-0005", "ot_cites", "OT-2026-0999"),
            ("info", "wiki_pages", "WP-0006", "ot_cites", ""),
            ("attention", "wiki_pages", "WP-0008", "cle", "changer la garniture de po 01"),
            ("attention", "wiki_journal", "WJ-00050", "changements", "WP-0001"),
            ("info", "wiki_journal", "WJ-00050", "contradictions", "Cavitation"),
        ]))


# ---------------------------------------------------------------------------------------------------
# Visibilité dans l'application : « à valider » invisible aux autres profils, dans les trois modes
# ---------------------------------------------------------------------------------------------------

AJOUT_JS = """async () => {
  if (Donnees.trouver('wiki_pages', 'WP-0001')) return;
  const equipement = Donnees.lignes('equipements')[0];
  const titre = equipement.repere + ' — ' + equipement.designation;
  const ot = Donnees.lignes('ordres_travail').filter((o) => o.statut === 'Clôturé administrativement').map((o) => o.id).sort()[0];
  const valide = '## Ce qui revient\\n- Texte validé [' + ot + ']';
  await Donnees.modifier('wiki_pages', (lignes) => { lignes.push({ id: 'WP-0001', type: 'équipement', titre,
    equipement_id: equipement.id, texte: valide, version: '1', statut: 'active', origine: 'IA', derniere_entree: 'WJ-00001' }); });
  await Donnees.modifier('wiki_journal', (lignes) => {
    lignes.push({ id: 'WJ-00001', nature: 'ingestion', ot_id: ot, statut: 'validée', ordre: '1', pages: 'EQ:' + equipement.id,
      changements: JSON.stringify([{ page: 'WP-0001', cle: 'EQ:' + equipement.id, version_avant: 0, avant: '', apres: valide }]),
      contradictions: '[]' });
    lignes.push({ id: 'WJ-00002', nature: 'ingestion', ot_id: ot, statut: 'à valider', ordre: '2', pages: 'EQ:' + equipement.id,
      changements: JSON.stringify([{ page: 'WP-0001', cle: 'EQ:' + equipement.id, version_avant: 1, avant: valide,
        apres: valide + '\\n- Texte proposé [' + ot + ']' }]), contradictions: '[]' });
  });
}"""
VU_JS = """() => { const page = Wiki.page(Donnees.lignes('equipements')[0].id);
  return { texte: page.texte, enAttente: page.enAttente.map((e) => e.entreeId), integre: Wiki.verifierIntegrite().ok }; }"""


class TestVisibiliteTroisModes(CasNavigateur):

    def verifier(self, page, responsable):
        page.evaluate(AJOUT_JS)
        vu = page.evaluate(VU_JS)
        self.assertEqual(vu["texte"].count("Texte validé"), 1)
        self.assertNotIn("Texte proposé", vu["texte"])
        self.assertEqual(vu["enAttente"], ["WJ-00002"] if responsable else [])
        self.assertTrue(vu["integre"])

    def nouvelle_page(self, profil, dossier=None):
        contexte = self.navigateur.new_context(locale="fr-FR")
        self.addCleanup(contexte.close)
        preregler_profil(contexte, profil, nom="Tech" if profil == "technicien" else "", technicien_id="TEC-0001"
                         if profil == "technicien" else "")
        if dossier:
            installer_dossier_simule(contexte, dossier)
        page = contexte.new_page()
        self.surveiller(page)
        return page

    def test_a_valider_invisible_aux_autres_profils(self):
        for motif in ingestion.ERREURS_SERVEUR_STATIQUE:
            self.autoriser_erreur(motif)
        for profil in ("technicien", "responsable"):
            with self.subTest(mode="démo", profil=profil):
                page = self.nouvelle_page(profil)
                page.goto(url_fichier("index.html"))
                page.click("#btn-demo")
                attendre_pret(page)
                self.verifier(page, profil == "responsable")
            with self.subTest(mode="dossier", profil=profil), ServeurStatique(RACINE) as statique:
                page = self.nouvelle_page(profil, "donnees-journal-" + profil)
                page.goto(statique.url + "/index.html")
                page.click("#btn-dossier")
                page.wait_for_selector("#btn-base-demo", state="visible")
                page.click("#btn-base-demo")
                attendre_pret(page, 30000)
                self.assertEqual(page.evaluate("App.mode"), "dossier")
                self.verifier(page, profil == "responsable")
        with ServeurPrevo() as serveur:
            for profil in ("responsable", "technicien"):           # le responsable écrit d'abord, le technicien relit
                with self.subTest(mode="serveur", profil=profil):
                    page = self.nouvelle_page(profil)
                    page.goto(serveur.url + "/")
                    attendre_pret(page, 30000)
                    self.assertEqual(page.evaluate("App.mode"), "serveur")
                    self.verifier(page, profil == "responsable")


if __name__ == "__main__":
    unittest.main()
