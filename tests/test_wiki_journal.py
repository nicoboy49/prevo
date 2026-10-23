"""Journal du wiki : validation, rejet, à refaire, rattrapage, relance, écriture à la main, contradictions,
visibilité, intégrité, problèmes de données (lot 6 refondu, tâche T117 ; ARCHITECTURE.md §20.2, §20.7 ; D105, D107 ;
CS101, CS102).

    profil        : seul le responsable valide, rejette, relance, écrit et tranche ; un autre profil ne change rien ;
    validation    : enchaînée dans l'ordre, d'un bloc (une entrée qui crée une page et en modifie une autre : tout ou
                    rien), version vérifiée (une page changée fait passer l'entrée « à refaire », et ses suivantes) ;
                    refus d'une entrée dont une plus ancienne en attente touche une même page ; « valider la
                    sélection » refuse une contradiction ; texte, OT cités, liens, version, origine, modèle, dernière
                    entrée et validateur posés ;
    rattrapage    : page écrite mais statut non écrit → « validée » au prochain affichage, sur les tables chargées (D101 :
                    afficher l'index ou une page, en mode serveur, ne fait aucune requête /api/csv ; valider, écrire et
                    ouvrir le journal relisent les pages) ; changements appliqués dans leur ordre (tri retiré, T138) ;
    rejet         : motif obligatoire ; les suivantes qui touchent une même page passent « à refaire » (en cascade),
                    les autres non ; relance d'un OT rejeté ;
    à la main     : contrôles du §20.6 (retrait permis ; OT permis, nombres, sécurité, limite d'« En bref » refusés),
                    entrée « manuel » avec avant et après, propositions en attente sur la page « à refaire », création
                    d'un savoir-faire seulement (refonte 2, §20.12 : mode, composant libre, équipement refusés ; sous-page
                    d'un savoir-faire seulement), archivage, conflit de version, échec de l'écriture de la page ;
                    ancienne page de mode ou sous-page d'équipement ou de composant (type retiré) lue sans erreur,
                    refusée à l'écriture (« type de page retiré : archivez-la »), archivable ; lien vers une panne
                    ([[Fuite]]) accepté et gardé dans `liens` (PANNE-<code>), à la main comme par l'IA ;
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
NL = ingestion.NL
page_wiki = ingestion.page_wiki
# Base d'essai de la refonte 2 (§20.12) : celle de test_wiki_ingestion, avec les textes des nouveaux types — « En bref »
# de PO-01, « À quoi il sert » du kit, des savoir-faire à la place des pages de mode — et une ancienne page de mode
# (WP-0007, type retiré), lue sans erreur et signalée.
TEXTE_PO01 = ("## En bref" + NL + "- Fuite de garniture au démarrage, fréquent ici [OT-2026-0007]" + NL
              + "- Voir [[Éviter la cavitation]] [OT-2026-0007]")
WIKI_PAGES = ingestion.table_csv(ingestion.ENTETE_WIKI, [
    page_wiki("WP-0001", "équipement", "PO-01 — Pompe de process A", TEXTE_PO01, equipement="EQ-0001"),
    page_wiki("WP-0002", "savoir-faire", "Changer la garniture de PO-01", "## Étapes" + NL + "- Repérer l'accouplement [OT-2026-0007]",
              equipement="EQ-0001"),
    page_wiki("WP-0003", "composant", "Kit garniture HC 50", "## À quoi il sert" + NL + "- Étanchéité de l'arbre [OT-2026-0007]",
              article="ART-0001"),
    # Rattaché à la page du composant (pas d'article_id) : trouvé par son rattachement.
    page_wiki("WP-0004", "savoir-faire", "Monter le kit garniture", "## Étapes" + NL + "- Lubrifier les joints [OT-2026-0007]",
              rattache="WP-0003"),
    page_wiki("WP-0005", "savoir-faire", "Repérer l'usure de la garniture", "## Quand le faire" + NL
              + "- Garniture usée [OT-2026-0007]", equipement="EQ-0001"),
    page_wiki("WP-0006", "savoir-faire", "Éviter la cavitation", "## Pièges" + NL + "- Bruit de gravier [OT-2026-0007]",
              equipement="EQ-0001"),
    page_wiki("WP-0007", "mode", "Desserrage", "## Causes" + NL + "- Bornes desserrées [OT-2026-0007]", cause="C03"),
    page_wiki("WP-0008", "savoir-faire", "Nettoyer le filtre de CP-01", equipement="EQ-0002"),
    page_wiki("WP-0009", "savoir-faire", "Ancien geste", "## Étapes" + NL + "- Vieux [OT-2026-0007]", equipement="EQ-0001",
              statut="archivée"),
    # Rattaché à la page de l'équipement (pas d'equipement_id) : trouvé par son rattachement.
    page_wiki("WP-0010", "savoir-faire", "Graisser le palier", "## Étapes" + NL + "- Graisser [OT-2026-0007]", rattache="WP-0001"),
])
BASE = dict(ingestion.BASE, wiki_pages=WIKI_PAGES)
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
        self.page.evaluate(ingestion.CHARGER_JS, BASE)
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
                               ("ecrire", [{"pageId": "EQ-0001"}, "## En bref\n- Fuite [OT-2026-0003]"]),
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
        self.assertEqual(po01["liens"], "WP-0006")                                   # [[Éviter la cavitation]]
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

    def test_lien_vers_une_page_seulement_modifiee_ne_lie_pas(self):
        """Un lien vers une page qu'une proposition plus ancienne modifie sans la créer n'en fait pas dépendre : rejetée,
        elle laisserait la page en place (fabrication de la démo, 2026-10-23 : un lien vers la page d'un équipement liait
        toute proposition à la dernière qui changeait cet équipement, et bloquait sa validation)."""
        entrees = self.entrees()
        id_0001 = entrees["OT-2026-0001"]["id"]
        self.assertIn("EQ:EQ-0001", [c["cle"] for c in json.loads(entrees["OT-2026-0001"]["changements"])])
        titre = self.ligne("WP-0001")["titre"]
        self.page.evaluate("""(titre) => Donnees.modifier('wiki_journal', (lignes) => { lignes.push({ id: 'WJ-00098',
          nature: 'ingestion', ot_id: 'OT-2026-0002', statut: 'à valider', ordre: '98', pages: 'WP:WP-0006',
          contradictions: '[]', changements: JSON.stringify([{ page: 'WP-0006', cle: 'WP:WP-0006', version_avant: 1,
            avant: '', creation: false, apres: '## Pièges\\n- Voir [[' + titre + ']] [OT-2026-0007]' }]) }); },
          { journal: false })""", titre)
        self.assertNotIn("WJ-00098", self.ok("rejeter", id_0001, "Essai")["aRefaire"])
        self.assertEqual(self.ok("valider", ["WJ-00098"])["validees"], ["WJ-00098"])

    def test_rejet_motif_cascade_et_relance(self):
        entrees = self.entrees()
        self.refus("motif du rejet est obligatoire", "rejeter", entrees["OT-2026-0003"]["id"], "  ")
        # Une proposition construite seulement sur la page créée par 0001 (lien vers elle) : elle suit 0001 en cascade.
        self.page.evaluate("""() => Donnees.modifier('wiki_journal', (lignes) => { lignes.push({ id: 'WJ-00099', nature: 'ingestion',
          ot_id: 'OT-2026-0002', statut: 'à valider', ordre: '99', pages: 'WP:WP-0006', contradictions: '[]',
          changements: JSON.stringify([{ page: 'WP-0006', cle: 'WP:WP-0006', version_avant: 1, avant: '', creation: false,
            apres: "## Pièges\\n- Voir [[Astuce de l'OT-2026-0001]] [OT-2026-0007]" }]) }); }, { journal: false })""")
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

    def test_rattrapage_sur_les_tables_chargees_sans_relire_les_pages(self):
        """D101 : Wiki.rattraper() (affichage d'une page du wiki) travaille sur les tables chargées, sans relire
        wiki_pages ; { relire: true } (validation, écriture, ouverture du journal) les relit d'abord. Une validation
        interrompue est rattrapée sans rien relire."""
        espion = """async (options) => {
          const relues = [];
          const recharger = Donnees.rechargerTable;
          Donnees.rechargerTable = function (table) { relues.push(table); return recharger.apply(this, arguments); };
          try { return { nombre: await Wiki.rattraper(options || undefined), relues }; }
          finally { Donnees.rechargerTable = recharger; }
        }"""
        self.assertEqual(self.page.evaluate(espion, None), {"nombre": 0, "relues": []})
        self.assertEqual(self.page.evaluate(espion, {"relire": True}), {"nombre": 0, "relues": ["wiki_pages"]})
        id_0003 = self.id_de("OT-2026-0003")
        self.page.evaluate("""() => { const modifier = Donnees.modifier;
          Donnees.modifier = function (table) { if (table === 'wiki_journal') { Donnees.modifier = modifier;
            return Promise.reject(new Error('disque plein')); } return modifier.apply(this, arguments); }; }""")
        self.refus("disque plein", "valider", [id_0003])
        self.assertEqual(self.page.evaluate(espion, None), {"nombre": 1, "relues": []})
        self.assertEqual(self.entrees()["OT-2026-0003"]["statut"], "validée")

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


AUTRE_POSTE_JS = """([table, geste]) => {
  // Le geste d'un « autre poste » passe juste avant la prochaine écriture de `table` par ce poste, une seule fois.
  const original = Donnees.modifier;
  const gestes = {
    rejeter: (id) => Wiki.rejeter(id, 'rejet sur un autre poste'),
    valider: (id) => Wiki.valider([id]),
    reecrire: () => original.call(Donnees, 'wiki_pages', (lignes) => { const l = lignes.find((x) => x.id === 'WP-0001');
      l.version = String(Number(l.version) + 1); l.texte += '\\n- Ajout d\\'un autre poste [OT-2026-0007]'; }),
  };
  window.resultatAutre = null;
  Donnees.modifier = async function (nom) {
    if (nom === table) {
      Donnees.modifier = original;
      window.resultatAutre = await gestes[geste[0]](geste[1]).then(() => ({ ok: true }), (e) => ({ ok: false, message: e.message }));
    }
    return original.apply(this, arguments);
  };
}"""


class TestDeuxPostes(CasJournal):
    """Deux postes du responsable en même temps (CS101) : une entrée appliquée aux pages est validée, quoi que l'autre
    poste ait fait entre les deux écritures ; rien ne reste publié contre le journal."""

    def setUp(self):
        super().setUp()
        self.traiter(EN_FILE)
        self.id_0003 = self.id_de("OT-2026-0003")

    def autre_poste(self, table, geste, cible=""):
        self.page.evaluate(AUTRE_POSTE_JS, [table, [geste, cible]])

    def fin(self):
        entree = self.entrees()["OT-2026-0003"]
        self.assertEqual(entree["statut"], "validée")
        self.assertEqual([c["page"] for c in json.loads(entree["changements"])], ["WP-0001"])
        self.assertEqual(self.ligne("WP-0001")["derniere_entree"], self.id_0003)
        self.assertEqual(self.integrite(), {"ok": True, "ecarts": []})
        return entree

    def test_rejet_apres_l_ecriture_des_pages_refuse(self):
        self.autre_poste("wiki_journal", "rejeter", self.id_0003)
        self.assertEqual(self.ok("valider", [self.id_0003])["validees"], [self.id_0003])
        autre = self.page.evaluate("window.resultatAutre")
        self.assertFalse(autre["ok"])
        self.assertIn("vient d'être validée", autre["message"])
        self.fin()

    def test_rejet_avant_l_ecriture_des_pages_la_validation_l_emporte(self):
        self.autre_poste("wiki_pages", "rejeter", self.id_0003)
        self.assertEqual(self.ok("valider", [self.id_0003])["validees"], [self.id_0003])
        self.assertEqual(self.page.evaluate("window.resultatAutre"), {"ok": True})
        entree = self.fin()
        self.assertIn("un autre poste l'avait passée « rejetée »", entree["motif"])
        self.assertTrue(entree["ordre"])

    def test_deux_validations_de_la_meme_proposition(self):
        self.autre_poste("wiki_journal", "valider", self.id_0003)
        self.assertEqual(self.ok("valider", [self.id_0003])["validees"], [self.id_0003])
        autre = self.page.evaluate("window.resultatAutre")
        self.assertFalse(autre["ok"])
        self.assertIn("n'est pas « à valider » (validée)", autre["message"])
        self.assertEqual(self.ligne("WP-0001")["version"], "2")              # appliquée une seule fois
        self.fin()

    def test_ecriture_a_la_main_et_page_reecrite_sur_un_autre_poste(self):
        self.autre_poste("wiki_pages", "reecrire")
        texte = "## En bref\n- Fuite de garniture au démarrage, fréquent ici [OT-2026-0007]"
        self.refus("modifiée entre-temps (sans doute sur un autre poste)", "ecrire", {"pageId": "EQ-0001"}, texte, {"version": 1})
        manuelle = self.page.evaluate("Donnees.lignes('wiki_journal').filter((e) => e.nature === 'manuel').pop()")
        self.assertEqual(manuelle["statut"], "refusée")
        self.assertIn("Ajout d'un autre poste", self.ligne("WP-0001")["texte"])

    def test_rattrapage_avant_une_validation_enchainee(self):
        # La validation de 0003 est interrompue après l'écriture des pages ; valider 0001 (construite sur elle) rattrape
        # d'abord 0003 au lieu de la refuser.
        self.page.evaluate("""() => { const modifier = Donnees.modifier;
          Donnees.modifier = function (table) { if (table === 'wiki_journal') { Donnees.modifier = modifier;
            return Promise.reject(new Error('disque plein')); } return modifier.apply(this, arguments); }; }""")
        self.refus("disque plein", "valider", [self.id_0003])
        self.assertEqual(self.ok("valider", [self.id_de("OT-2026-0001")])["validees"], [self.id_de("OT-2026-0001")])
        self.assertEqual(self.entrees()["OT-2026-0003"]["statut"], "validée")
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

    TEXTE = ("## En bref\n- Fuite de garniture au démarrage, fréquent ici [OT-2026-0007]\n"
             "## Astuces\n- Garniture usée remplacée [OT-2026-0001]")

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
        self.assertEqual(changement["avant"], TEXTE_PO01)
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
            # Les limites des textes rédigés (§20.12) valent aussi à la main.
            ("Page « PO-01 — Pompe de process A » : « En bref » : 6 phrases, 5 au plus.",
             "## En bref\n" + "\n".join("- Constat %s [OT-2026-0001]" % ("x" * n) for n in range(1, 7)), None),
            ("rubrique « Ce qui revient » inconnue pour une page équipement",
             "## Ce qui revient\n- Fuite de garniture au démarrage [OT-2026-0007]", None),
            ("La page a été modifiée entre-temps", self.TEXTE, {"version": 0}),
        ]
        for attendu, texte, options in cas:
            with self.subTest(attendu=attendu):
                self.refus(attendu, "ecrire", {"pageId": "EQ-0001"}, texte, options or {})
        self.assertEqual(self.etat(), avant)
        # Le nombre d'un OT cité est permis (2.5 h d'arrêt de OT-2026-0001).
        self.ok("ecrire", {"pageId": "EQ-0001"}, self.TEXTE + "\n- Arrêt de 2.5 h [OT-2026-0001]")

    def test_seul_un_savoir_faire_se_cree_a_la_main(self):
        """Refonte 2 (§20.12) : une page de mode, un composant libre ou une page d'équipement ne se crée plus, même à la
        main ; une sous-page ne se crée que sous un savoir-faire. Rien n'est écrit."""
        avant = self.etat()
        for attendu, nouvelle, texte in (
                ("Page « Corrosion des brides » : type « mode » inconnu (équipement, composant, savoir-faire).",
                 {"type": "mode", "titre": "Corrosion des brides", "causeCode": "C02"}, "## Causes\n- Eau [OT-2026-0002]"),
                ("Page « Joint de bride » : une page de composant ne se crée pas",
                 {"type": "composant", "titre": "Joint de bride"}, "## À quoi il sert\n- Étanchéité [OT-2026-0002]"),
                ("Page « ZZ » : une page d'équipement ne se crée pas", {"type": "équipement", "titre": "ZZ"}, ""),
                ("Page « PO-01 — garniture » : une sous-page n'existe que pour un savoir-faire",
                 {"type": "équipement", "titre": "PO-01 — garniture", "rattacheA": "EQ-0001"},
                 "## En bref\n- Garniture sèche [OT-2026-0001]"),
                ("Page « Kit garniture HC 50 — faces » : une sous-page n'existe que pour un savoir-faire",
                 {"type": "composant", "titre": "Kit garniture HC 50 — faces", "rattacheA": "ART-0001"},
                 "## À quoi il sert\n- Faces rayées [OT-2026-0001]")):
            with self.subTest(nouvelle=nouvelle):
                message = self.refus(attendu, "ecrire", {"nouvelle": nouvelle}, texte)
                self.assertEqual(message.count("Page « "), 1, message)               # une seule raison
        self.assertEqual(self.etat(), avant)

    def test_creation_archivage_et_echec_de_l_ecriture(self):
        # Un savoir-faire rattaché à un équipement (au lieu de l'ancienne page de mode créée à la main).
        rincer = self.ok("ecrire", {"nouvelle": {"type": "savoir-faire", "titre": "Rincer le circuit", "rattacheA": "EQ-0002"}},
                         "## Étapes\n- Eau dans le circuit, voir [[Filtre à huile]] [OT-2026-0002]")
        ligne = self.ligne(rincer["ligneId"])
        self.assertEqual((rincer["pageId"], ligne["type"], ligne["origine"], ligne["version"], ligne["liens"], ligne["cle"],
                          ligne["equipement_id"], ligne["cause_code"]),
                         (rincer["ligneId"], "savoir-faire", "manuel", "1", "ART-0003", "rincer le circuit", "EQ-0002", ""))
        self.assertEqual(self.page.evaluate("(id) => Wiki.page(id).titre", rincer["pageId"]), "Rincer le circuit")
        self.refus("une page de ce titre existe déjà", "ecrire",
                   {"nouvelle": {"type": "savoir-faire", "titre": "Rincer le circuit", "rattacheA": "EQ-0002"}},
                   "## Étapes\n- Eau [OT-2026-0002]")
        geste = self.ok("ecrire", {"nouvelle": {"type": "savoir-faire", "titre": "Poser le kit HC 50", "rattacheA": "ART-0001"}},
                        "## Étapes\n- Marquer la position de l'accouplement [OT-2026-0001]")
        self.assertEqual(self.ligne(geste["ligneId"])["article_id"], "ART-0001")
        # Rattaché à l'ancienne page de mode (ni équipement ni composant) : refusé.
        self.refus("un savoir-faire se rattache", "ecrire",
                   {"nouvelle": {"type": "savoir-faire", "titre": "Geste libre", "rattacheA": "WP-0007"}},
                   "## Étapes\n- Rincer [OT-2026-0002]")
        # Archivage : le texte reste, la page sort du wiki ; on ne l'écrit plus.
        archive = self.ok("ecrire", {"pageId": "WP-0006"}, None, {"archiver": True})
        self.assertEqual(self.ligne("WP-0006")["statut"], "archivée")
        entree = self.page.evaluate("(id) => Donnees.trouver('wiki_journal', id)", archive["entreeId"])
        self.assertTrue(json.loads(entree["changements"])[0]["archivage"])
        self.refus("est archivée", "ecrire", {"pageId": "WP-0006"}, "## Pièges\n- Bruit [OT-2026-0001]")
        # Une page créée à la main puis archivée : l'entrée de sa création porte son WP-…, l'intégrité reste ok.
        self.ok("ecrire", {"pageId": rincer["ligneId"]}, None, {"archiver": True})
        creation = self.page.evaluate("""(id) => Donnees.lignes('wiki_journal').find((e) => e.nature === 'manuel'
          && JSON.parse(e.changements)[0].creation && JSON.parse(e.changements)[0].page === id)""", rincer["ligneId"])
        self.assertIsNotNone(creation)
        self.assertEqual(self.integrite(), {"ok": True, "ecarts": []})
        # L'écriture de la page échoue : l'entrée « manuel » passe « refusée » avec la raison.
        self.page.evaluate("""() => { const modifier = Donnees.modifier;
          Donnees.modifier = function (table) { if (table === 'wiki_pages') return Promise.reject(new Error('disque plein'));
            return modifier.apply(this, arguments); }; }""")
        self.refus("disque plein", "ecrire", {"pageId": "EQ-0001"}, self.TEXTE)
        derniere = self.page.evaluate("Donnees.lignes('wiki_journal').filter((e) => e.nature === 'manuel').pop()")
        self.assertEqual((derniere["statut"], derniere["raisons"]), ("refusée", "disque plein"))

    def test_ancienne_page_de_mode(self):
        """Une page de mode d'une base de développement (type retiré par la refonte 2) : lue sans erreur, signalée
        « type de page retiré » (attention), Wiki.page ne plante pas, refusée à l'écriture à la main (« type de page
        retiré : archivez-la »), archivable."""
        problemes = """() => Donnees.problemes().filter((p) => p.table === 'wiki_pages' && p.gravite !== 'info')
          .map((p) => [p.gravite, p.type, p.id, p.champ, p.valeur, p.message])"""
        self.assertEqual(self.page.evaluate(problemes), [["attention", "wiki", "WP-0007", "type", "mode",
            "Page du wiki WP-0007 (« Desserrage ») : type de page retiré (« mode » : une panne est une page calculée par "
            "Prévo) ; archivez-la."]])
        self.assertEqual(self.ligne("WP-0007")["type"], "mode")
        self.assertEqual(self.page.evaluate("Wiki.page('WP-0007').titre"), "Desserrage")
        self.assertEqual(self.page.evaluate("Wiki.typeRetire(Donnees.trouver('wiki_pages', 'WP-0007'))"), "mode")
        avant = self.etat()
        message = self.refus("Page « Desserrage » (mode) : type de page retiré : archivez-la.", "ecrire", {"pageId": "WP-0007"},
                             "## Causes\n- Bornes desserrées [OT-2026-0007]")
        self.assertEqual(message.count("Page « "), 1, message)
        self.assertEqual(self.etat(), avant)
        self.ok("ecrire", {"pageId": "WP-0007"}, None, {"archiver": True})
        self.assertEqual(self.ligne("WP-0007")["statut"], "archivée")
        self.assertEqual(self.page.evaluate(problemes), [])
        self.assertEqual(self.integrite(), {"ok": True, "ecarts": []})

    def test_ancienne_sous_page_d_equipement_ou_de_composant(self):
        """Une sous-page d'équipement ou de composant d'avant la refonte 2 (seuls les savoir-faire en ont, §20.12) : type
        de page retiré, refusée à l'écriture à la main, archivable ; une sous-page de savoir-faire, elle, s'écrit."""
        self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => {
          const page = (id, type, titre, texte, rattache) => ({ id, type, titre, texte, rattache_a: rattache, version: '1',
            statut: 'active', origine: 'IA' });
          lignes.push(page('WP-0020', 'équipement', 'PO-01 — garniture', '## Ce qui revient\\n- Garniture sèche [OT-2026-0007]', 'WP-0001'));
          lignes.push(page('WP-0021', 'composant', 'Kit garniture HC 50 — faces', '## Défaillances\\n- Faces rayées [OT-2026-0007]', 'WP-0003'));
          lignes.push(page('WP-0022', 'savoir-faire', 'Changer la garniture de PO-01 — dépose', '## Étapes\\n- Déposer [OT-2026-0007]', 'WP-0002'));
        })""")
        retires = self.page.evaluate("['WP-0020', 'WP-0021', 'WP-0022', 'WP-0001', 'WP-0010'].map((id) => Wiki.typeRetire(Donnees.trouver('wiki_pages', id)))")
        self.assertEqual(retires, ["sous-page d'équipement", "sous-page de composant", "", "", ""])
        avant = self.etat()
        self.refus("Page « PO-01 — garniture » (sous-page d'équipement) : type de page retiré : archivez-la.", "ecrire",
                   {"pageId": "WP-0020"}, "## En bref\n- Garniture sèche [OT-2026-0007]")
        self.refus("(sous-page de composant) : type de page retiré : archivez-la.", "ecrire", {"pageId": "WP-0021"},
                   "## À quoi il sert\n- Faces rayées [OT-2026-0007]")
        self.assertEqual(self.etat(), avant)
        self.ok("ecrire", {"pageId": "WP-0022"}, "## Étapes\n- Déposer le kit usé [OT-2026-0007]")
        for id_ in ("WP-0020", "WP-0021"):
            self.ok("ecrire", {"pageId": id_}, None, {"archiver": True})
            self.assertEqual(self.ligne(id_)["statut"], "archivée")

    def test_lien_vers_une_panne_accepte_et_garde_dans_liens(self):
        """Suite de T134 : [[Fuite]] (libellé d'un code symptôme qui a un cas : une page Panne) est accepté à l'écriture à la
        main et gardé dans `liens` sous PANNE-<code> (même définition que la page, Wiki.listeEntites) ; une proposition de
        l'IA validée aussi ; Donnees.problemes ne le signale pas ; [[Vibration]] (code sans OT) reste inconnu."""
        texte = self.TEXTE + "\n- Fuite revenue, voir [[Fuite]] et [[Bruit anormal]] [OT-2026-0001]"
        self.ok("ecrire", {"pageId": "EQ-0001"}, texte)
        self.assertEqual(self.ligne("WP-0001")["liens"], "PANNE-S01;PANNE-S02")
        self.assertEqual(self.page.evaluate("Wiki.pannesDuWiki().map((p) => [p.id, p.titre]).sort()"),
                         [["PANNE-S01", "Fuite"], ["PANNE-S02", "Bruit anormal"]])
        self.assertEqual(self.page.evaluate("""() => Donnees.problemes().filter((p) => p.table === 'wiki_pages' && p.champ === 'liens')
          .map((p) => p.valeur)"""), [])
        self.refus("lien vers une page inconnue « Vibration »", "ecrire", {"pageId": "EQ-0001"},
                   texte + "\n- Voir [[Vibration]] [OT-2026-0001]")
        # Un code symptôme qui n'existe pas : signalé par Donnees.problemes.
        self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => {
          lignes.find((l) => l.id === 'WP-0001').liens = 'PANNE-S01;PANNE-S99'; })""")
        self.assertEqual(self.page.evaluate("""() => Donnees.problemes().filter((p) => p.table === 'wiki_pages' && p.champ === 'liens')
          .map((p) => p.valeur)"""), ["PANNE-S99"])
        # Par l'IA (faux-textes : « … : fréquent ici ([[Fuite]]) ») : la validation garde aussi le lien.
        self.traiter(["OT-2026-0008"], "faux-textes")
        self.ok("valider", [self.id_de("OT-2026-0008")])
        self.assertIn("[[Fuite]]", self.ligne("WP-0001")["texte"])
        self.assertIn("PANNE-S01", self.ligne("WP-0001")["liens"].split(";"))


# Découpage d'un savoir-faire (refonte 2, §20.12 : seules sous-pages) par faux-decoupe : ses « Étapes » partent dans
# « <titre> — étapes détaillées ».
MERE_SF = "Changer la garniture de PO-01"
SOUS_PAGE_SF = MERE_SF + " — étapes détaillées"
ASTUCE_0001 = "Astuce de l'OT-2026-0001"
CLES_JS = """() => Array.from(Wiki.etatPropose().values()).filter((p) => p.titre.startsWith('Changer la garniture de PO-01'))
  .map((p) => [p.cle, p.titre, p.rattacheA, p.equipementId]).sort()"""
PROBLEMES_WIKI_JS = """(ids) => Donnees.problemes().filter((p) => p.table === 'wiki_pages' && ids.includes(p.id))
  .map((p) => [p.gravite, p.id, p.champ, p.message])"""


class TestDecoupage(CasJournal):
    """Découpage en sous-pages (§20.4, §20.7, CS113 ; savoir-faire seulement, §20.12) : validé d'un bloc, la sous-page
    reçoit rattache_a = la ligne de sa mère (créée d'abord, quel que soit l'ordre des changements), jamais l'ancrage de sa
    mère ; la mère garde sa clé ; intégrité ; la proposition suivante envoie la sous-page ; rejet, cascade et rattrapage."""

    def lignes(self):
        return {ligne["titre"]: ligne for ligne in self.page.evaluate("Donnees.lignes('wiki_pages')")}

    def test_sous_page_ecrite_a_la_main_sans_ancrage(self):
        """Une sous-page de savoir-faire écrite à la main : rattachée à la ligne de sa mère, sans ancrage propre (ni
        équipement, ni article, ni code cause : l'écriture à la main n'en reçoit plus, refonte 2) ; sous un équipement
        ou un composant, refusée."""
        self.ok("ecrire", {"nouvelle": {"type": "savoir-faire", "titre": MERE_SF + " — dépose", "rattacheA": "WP-0002"}},
                "## Étapes\n- Déposer le kit usé [OT-2026-0001]")
        ligne = self.lignes()[MERE_SF + " — dépose"]
        self.assertEqual((ligne["type"], ligne["rattache_a"], ligne["equipement_id"], ligne["article_id"], ligne["cause_code"]),
                         ("savoir-faire", "WP-0002", "", "", ""))
        self.refus("une sous-page n'existe que pour un savoir-faire", "ecrire",
                   {"nouvelle": {"type": "équipement", "titre": "PO-01 — garniture", "rattacheA": "EQ-0001"}},
                   "## En bref\n- Garniture sèche [OT-2026-0001]")

    def test_ancienne_proposition_de_sous_page_d_equipement(self):
        """Une proposition encore à valider d'avant la refonte 2 (base de développement) qui crée une sous-page
        d'équipement, une page de mode ou un composant libre : sa validation est refusée, rien n'est écrit ; elle reste
        à valider, et le message dit au responsable de la rejeter."""
        anciennes = [("WJ-00097", "TITRE:po 01 garniture", "PO-01 — garniture", "équipement", "PO-01 — Pompe de process A",
                      "## Ce qui revient\\n- Garniture sèche [OT-2026-0001]"),
                     ("WJ-00096", "TITRE:faces rayees", "Faces rayées", "mode", "", "## Causes\\n- Garniture sèche [OT-2026-0001]"),
                     ("WJ-00095", "TITRE:joint torique 20x2", "Joint torique 20x2", "composant", "",
                      "## Défaillances\\n- Joint pincé [OT-2026-0001]")]
        for entree, cle, titre, type_, mere, apres in anciennes:
            with self.subTest(type=type_):
                self.page.evaluate("""([entree, cle, titre, type, mere, apres]) => Donnees.modifier('wiki_journal', (lignes) => {
                  lignes.push({ id: entree, nature: 'ingestion', ot_id: 'OT-2026-0001', statut: 'à valider', ordre: entree.slice(-2),
                    pages: 'EQ:EQ-0001', contradictions: '[]', changements: JSON.stringify([{ cle, titre, type, creation: true,
                      rattacheA: mere, version_avant: 0, avant: '', apres: apres.split('\\\\n').join(String.fromCharCode(10)) }]) }); },
                  { journal: false })""", [entree, cle, titre, type_, mere, apres])
                avant = self.etat()["pages"]
                self.refus("« %s » : seule une page savoir-faire se crée (proposition d'avant la refonte 2) : rejetez-la." % titre,
                           "valider", [entree])
                self.assertEqual(self.etat()["pages"], avant)
                self.assertEqual(self.page.evaluate("(id) => Donnees.trouver('wiki_journal', id).statut", entree), "à valider")
                self.assertEqual(self.ok("rejeter", entree, "Proposition d'avant la refonte 2")["rejetee"], entree)

    def test_validation_d_un_decoupage_d_un_bloc(self):
        self.traiter(["OT-2026-0001"], "faux-decoupe")
        id_0001 = self.id_de("OT-2026-0001")
        nombre = len(self.lignes())
        self.assertEqual(self.ok("valider", [id_0001]), {"validees": [id_0001], "aRefaire": []})
        lignes = self.lignes()
        self.assertEqual(len(lignes), nombre + 2)                              # la sous-page et l'astuce
        sous_page, mere = lignes[SOUS_PAGE_SF], self.ligne("WP-0002")
        self.assertEqual({k: sous_page[k] for k in ("type", "rattache_a", "equipement_id", "article_id", "cause_code", "version",
                                                    "origine", "cle", "derniere_entree", "statut", "ot_cites")},
                         {"type": "savoir-faire", "rattache_a": "WP-0002", "equipement_id": "", "article_id": "",
                          "cause_code": "", "version": "1", "origine": "IA", "cle": "changer la garniture de po 01 etapes detaillees",
                          "derniere_entree": id_0001, "statut": "active", "ot_cites": "OT-2026-0007"})
        self.assertEqual((mere["equipement_id"], mere["version"], mere["derniere_entree"], mere["liens"], mere["ot_cites"]),
                         ("EQ-0001", "2", id_0001, sous_page["id"], "OT-2026-0007"))
        self.assertIn("[[" + SOUS_PAGE_SF + "]]", mere["texte"])
        actives = [l["cle"] for l in lignes.values() if l["statut"] == "active" and l["cle"]]    # posées à l'écriture
        self.assertEqual(len(actives), len(set(actives)))                     # clés uniques
        self.assertEqual(sorted(actives), ["astuce de l ot 2026 0001", "changer la garniture de po 01",
                                           "changer la garniture de po 01 etapes detaillees", "po 01 pompe de process a"])
        # La mère garde sa clé et son ancrage ; la sous-page a sa clé (WP:), rattachée à celle de sa mère, sans ancrage.
        self.assertEqual(self.page.evaluate(CLES_JS), [
            ["WP:WP-0002", MERE_SF, "", "EQ-0001"],
            ["WP:" + sous_page["id"], SOUS_PAGE_SF, "WP:WP-0002", ""]])
        self.assertEqual([c["page"] for c in json.loads(self.entrees()["OT-2026-0001"]["changements"])],
                         ["WP-0001", sous_page["id"], "WP-0002", lignes[ASTUCE_0001]["id"]])
        self.assertEqual(self.integrite(), {"ok": True, "ecarts": []})
        self.assertEqual(self.page.evaluate(PROBLEMES_WIKI_JS, ["WP-0002", sous_page["id"]]), [])
        # Modifiée à la main au-delà des limites : refusée, sans le conseil de la découper (une sous-page ne se découpe pas).
        trop = "## Étapes\n" + "\n".join("- Constat %s [OT-2026-0001]" % ("x" * n) for n in range(1, 32))
        message = self.refus("31 phrases, 30 au plus", "ecrire", {"pageId": sous_page["id"]}, trop)
        self.assertNotIn("se découpe", message)
        self.assertIn("se découpe", self.refus("31 phrases, 30 au plus", "ecrire", {"pageId": "WP-0002"}, trop))
        # La proposition suivante sur PO-01 envoie la sous-page juste après sa mère ; validée à son tour, intègre.
        cles = self.page.evaluate("(ot) => Wiki.pagesConcernees(ot).cles", "OT-2026-0008")
        self.assertEqual(cles[0], "EQ:EQ-0001")
        self.assertEqual(cles.index("WP:" + sous_page["id"]), cles.index("WP:WP-0002") + 1)
        self.traiter(["OT-2026-0008"], "faux-decoupe")
        suite = self.entrees()["OT-2026-0008"]
        self.assertEqual([(c["page"], c["version_avant"]) for c in json.loads(suite["changements"])], [(sous_page["id"], 1)])
        self.ok("valider", [suite["id"]])
        self.assertEqual((self.ligne(sous_page["id"])["version"], self.ligne(sous_page["id"])["rattache_a"]), ("2", "WP-0002"))
        self.assertEqual(self.integrite(), {"ok": True, "ecarts": []})

    def test_mere_creee_par_une_proposition_plus_ancienne(self):
        """La mère n'a pas encore de ligne : c'est le savoir-faire créé par une proposition encore à valider (l'astuce de
        OT-2026-0001), découpé par la suivante, qui crée sa sous-page avant de modifier sa mère. Validées d'une sélection,
        la ligne de la mère est créée d'abord et la sous-page lui est rattachée."""
        self.traiter(["OT-2026-0001"])
        self.traiter(["OT-2026-0008"], "faux-decoupe")
        id_0001, id_0008 = self.id_de("OT-2026-0001"), self.id_de("OT-2026-0008")
        self.assertEqual([c["titre"] for c in json.loads(self.entrees()["OT-2026-0008"]["changements"])],
                         ["PO-01 — Pompe de process A", ASTUCE_0001 + " — étapes détaillées", ASTUCE_0001])
        self.assertNotIn(ASTUCE_0001, self.lignes())
        self.refus("Validez d'abord " + id_0001, "valider", [id_0008])
        self.assertEqual(self.ok("valider", [id_0008, id_0001])["validees"], [id_0001, id_0008])
        lignes = self.lignes()
        mere, sous_page = lignes[ASTUCE_0001], lignes[ASTUCE_0001 + " — étapes détaillées"]
        self.assertEqual((mere["type"], mere["equipement_id"], mere["version"]), ("savoir-faire", "EQ-0001", "2"))
        self.assertEqual((sous_page["type"], sous_page["rattache_a"], sous_page["equipement_id"], sous_page["article_id"]),
                         ("savoir-faire", mere["id"], "", ""))
        self.assertLess(mere["id"], sous_page["id"])                          # la ligne de la mère d'abord
        self.assertEqual(self.integrite(), {"ok": True, "ecarts": []})
        self.assertEqual(self.page.evaluate(PROBLEMES_WIKI_JS, [mere["id"], sous_page["id"]]), [])

    def test_rejet_cascade_et_rattrapage_d_un_decoupage(self):
        self.traiter(["OT-2026-0001"], "faux-decoupe")
        self.traiter(["OT-2026-0008"], "faux-decoupe")                       # sur la sous-page encore à valider
        id_0001, id_0008 = self.id_de("OT-2026-0001"), self.id_de("OT-2026-0008")
        self.assertEqual([c["titre"] for c in json.loads(self.entrees()["OT-2026-0008"]["changements"])], [SOUS_PAGE_SF])
        self.refus("Validez d'abord " + id_0001, "valider", [id_0008])
        self.assertEqual(self.ok("rejeter", id_0001, "Découpage à revoir"), {"rejetee": id_0001, "aRefaire": [id_0008]})
        self.assertNotIn(SOUS_PAGE_SF, self.lignes())
        # Retraitées (0001 relancé) : le découpage revient ; sa validation est interrompue après l'écriture des pages,
        # puis rattrapée.
        self.ok("remettreEnFile", id_0001)
        self.traiter([], "faux-decoupe")
        id_0001 = self.id_de("OT-2026-0001")
        self.page.evaluate("""() => { const modifier = Donnees.modifier;
          Donnees.modifier = function (table) { if (table === 'wiki_journal') { Donnees.modifier = modifier;
            return Promise.reject(new Error('disque plein')); } return modifier.apply(this, arguments); }; }""")
        self.refus("disque plein", "valider", [id_0001])
        self.assertEqual(self.lignes()[SOUS_PAGE_SF]["derniere_entree"], id_0001)
        self.assertEqual(self.ok("rattraper"), 1)
        self.assertEqual(self.entrees()["OT-2026-0001"]["statut"], "validée")
        self.assertEqual(self.integrite(), {"ok": True, "ecarts": []})

    def test_changements_appliques_dans_leur_ordre(self):
        """Tri retiré de `appliquer` (T138, « pages modifiées avant pages créées ») : une entrée qui crée un savoir-faire
        rattaché à une machine encore sans ligne AVANT de modifier cette machine s'applique dans l'ordre de ses
        changements ; le savoir-faire prend l'ancrage de la machine (equipement_id) sans attendre sa ligne. (La mère
        d'une sous-page, elle, a toujours déjà sa ligne : un savoir-faire envoyé, ou créé par une entrée plus ancienne,
        validée d'abord — test_mere_creee_par_une_proposition_plus_ancienne.)"""
        self.page.evaluate("""() => Donnees.modifier('wiki_journal', (lignes) => { lignes.push({ id: 'WJ-00050',
          nature: 'ingestion', ot_id: 'OT-2026-0002', statut: 'à valider', ordre: '50', pages: 'EQ:EQ-0002', contradictions: '[]',
          changements: JSON.stringify([
            { cle: 'TITRE:purger le circuit de cp 01', titre: 'Purger le circuit de CP-01', type: 'savoir-faire', creation: true,
              rattacheA: 'CP-01 — Compresseur', version_avant: 0, avant: '', apres: '## Étapes\\n- Purger [OT-2026-0002]' },
            { cle: 'EQ:EQ-0002', page: '', titre: 'CP-01 — Compresseur', type: 'équipement', creation: false, version_avant: 0,
              avant: '', apres: '## En bref\\n- Filtre encrassé, voir [[Purger le circuit de CP-01]] [OT-2026-0002]' }]) }); },
          { journal: false })""")
        self.assertEqual(self.ok("valider", ["WJ-00050"]), {"validees": ["WJ-00050"], "aRefaire": []})
        lignes = self.lignes()
        savoir, machine = lignes["Purger le circuit de CP-01"], lignes["CP-01 — Compresseur"]
        self.assertEqual((savoir["equipement_id"], savoir["rattache_a"], machine["equipement_id"], machine["type"]),
                         ("EQ-0002", "", "EQ-0002", "équipement"))
        self.assertLess(savoir["id"], machine["id"])                          # créées dans l'ordre des changements
        self.assertEqual(machine["liens"], savoir["id"])
        self.assertEqual(self.integrite(), {"ok": True, "ecarts": []})

    def test_mere_archivee_signalee(self):
        self.traiter(["OT-2026-0001"], "faux-decoupe")
        self.ok("valider", [self.id_de("OT-2026-0001")])
        sous_page = self.lignes()[SOUS_PAGE_SF]
        self.ok("ecrire", {"pageId": "WP-0002"}, None, {"archiver": True})
        self.assertIn(["attention", sous_page["id"], "rattache_a",
                       "Page du wiki %s (« %s ») : sous-page de la page archivée « %s » (WP-0002)."
                       % (sous_page["id"], SOUS_PAGE_SF, MERE_SF)], self.page.evaluate(PROBLEMES_WIKI_JS, [sous_page["id"]]))


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
        # Une page qui a un texte sans aucune entrée au journal : écart.
        self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => { lignes.push({ id: 'WP-0090', type: 'savoir-faire',
          titre: 'Page écrite hors du journal', texte: '## Étapes\\n- Usure [OT-2026-0001]', version: '1', statut: 'active' }); })""")
        self.assertIn(("Page écrite hors du journal", "texte sans entrée au journal"),
                      [(e["page"], e["message"]) for e in self.integrite()["ecarts"]])
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
              contradictions: JSON.stringify([{ page: 'Éviter la cavitation', pageCle: 'WP:WP-0006', phrase: 'x', statut: 'ouverte' }]),
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
            ("info", "wiki_journal", "WJ-00050", "contradictions", "Éviter la cavitation"),
            ("attention", "wiki_pages", "WP-0007", "type", "mode"),            # ancienne page de mode (type retiré)
        ]))


# ---------------------------------------------------------------------------------------------------
# Visibilité dans l'application : « à valider » invisible aux autres profils, dans les trois modes
# ---------------------------------------------------------------------------------------------------

# Par-dessus le wiki de la démo (qui peut déjà avoir la page) : la page du premier équipement (créée si besoin, avec
# son entrée validée), puis une proposition à valider qui la change.
AJOUT_JS = """async () => {
  if (Donnees.trouver('wiki_journal', 'WJ-99002')) return;
  const equipement = Donnees.lignes('equipements')[0];
  const ot = Donnees.lignes('ordres_travail').filter((o) => o.statut === 'Clôturé administrativement').map((o) => o.id).sort()[0];
  const actuelle = () => Donnees.lignes('wiki_pages').find((l) => l.type === 'équipement' && l.equipement_id === equipement.id
    && l.statut !== 'archivée');
  if (!actuelle()) {
    const valide = '## En bref\\n- Texte validé [' + ot + ']';
    await Donnees.modifier('wiki_pages', (lignes) => { lignes.push({ id: 'WP-9001', type: 'équipement',
      titre: equipement.repere + ' — ' + equipement.designation, equipement_id: equipement.id, texte: valide, version: '1',
      statut: 'active', origine: 'IA', derniere_entree: 'WJ-99001' }); });
    await Donnees.modifier('wiki_journal', (lignes) => { lignes.push({ id: 'WJ-99001', nature: 'ingestion', ot_id: ot,
      statut: 'validée', ordre: '9998', pages: 'EQ:' + equipement.id, contradictions: '[]',
      changements: JSON.stringify([{ page: 'WP-9001', cle: 'EQ:' + equipement.id, version_avant: 0, avant: '', apres: valide }]) }); });
  }
  const ligne = actuelle();
  await Donnees.modifier('wiki_journal', (lignes) => { lignes.push({ id: 'WJ-99002', nature: 'ingestion', ot_id: ot,
    statut: 'à valider', ordre: '9999', pages: 'EQ:' + equipement.id, contradictions: '[]',
    changements: JSON.stringify([{ page: ligne.id, cle: 'EQ:' + equipement.id, version_avant: Number(ligne.version) || 0,
      avant: ligne.texte, apres: ligne.texte + '\\n- Texte proposé [' + ot + ']' }]) }); });
}"""
VU_JS = """() => { const equipement = Donnees.lignes('equipements')[0]; const page = Wiki.page(equipement.id);
  const ligne = Donnees.lignes('wiki_pages').find((l) => l.type === 'équipement' && l.equipement_id === equipement.id
    && l.statut !== 'archivée');
  return { texte: page.texte, valide: ligne.texte, enAttente: page.enAttente.map((e) => e.entreeId),
    integre: Wiki.verifierIntegrite().ok }; }"""


class TestVisibiliteTroisModes(CasNavigateur):

    def verifier(self, page, responsable):
        page.evaluate(AJOUT_JS)
        vu = page.evaluate(VU_JS)
        self.assertEqual(vu["texte"], vu["valide"])                      # le texte validé, jamais la proposition
        self.assertNotIn("Texte proposé", vu["texte"])
        if responsable:
            self.assertIn("WJ-99002", vu["enAttente"])
        else:
            self.assertEqual(vu["enAttente"], [])
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


class TestAffichageSansReseau(CasNavigateur):
    """D101 (relevé du test de performance de T124 : afficher une page relisait /api/csv/wiki_pages) : en mode serveur,
    afficher l'index du wiki puis la page d'une machine ne fait aucune requête /api/csv ; le journal, lui, relit les
    pages à son ouverture (rattrapage, §20.7)."""

    def test_index_et_page_sans_requete_csv_en_mode_serveur(self):
        for motif in ingestion.ERREURS_SERVEUR_STATIQUE:
            self.autoriser_erreur(motif)
        with ServeurPrevo() as serveur:
            contexte = self.navigateur.new_context(locale="fr-FR")
            self.addCleanup(contexte.close)
            preregler_profil(contexte, "responsable")
            page = contexte.new_page()
            self.surveiller(page)
            page.goto(serveur.url + "/")
            attendre_pret(page, 30000)
            self.assertEqual(page.evaluate("App.mode"), "serveur")
            equipement = page.evaluate("Donnees.lignes('equipements')[0].id")
            requetes = []
            page.on("request", lambda requete: requetes.append(requete.url))
            for route in ("#/wiki", "#/wiki/" + equipement):
                with self.subTest(route=route):
                    page.evaluate("location.hash = '#/accueil'")
                    page.wait_for_selector("#contenu .accueil-instruments")
                    page.evaluate("(route) => { location.hash = route; }", route)
                    page.wait_for_selector("#contenu .wiki")
                    page.wait_for_timeout(300)
                    self.assertEqual([u for u in requetes if "/api/csv" in u], [])
            page.evaluate("location.hash = '#/wiki-journal'")
            page.wait_for_selector('.wj[data-vue="journal"]')
            self.assertTrue(any("/api/csv/wiki_pages" in u for u in requetes), requetes)


if __name__ == "__main__":
    unittest.main()
