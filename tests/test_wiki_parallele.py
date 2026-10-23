"""Parallélisme de l'ingestion du wiki (lot 6 refondu, tâche T118 ; ARCHITECTURE.md §20.5, §20.7 ; D112 ; CS111).

Tous les OT clôturés administrativement de la démo sont ingérés avec le faux fournisseur (réponse tirée du seul
message), une fois avec 1 agent, une fois avec Wiki.SEUILS.agentsSimultanes agents et des délais de réponse variés
(l'ordre d'arrivée des réponses change), puis toutes les propositions sont validées. On vérifie :
    - le wiki obtenu est le même (texte de chaque page, propositions de chaque OT) ;
    - Wiki.verifierIntegrite est ok (chaîne de chaque page, ordre des dates, aucun envoi simultané sur une page) ;
    - jamais plus de agentsSimultanes envois en cours, et le parallélisme a bien eu lieu (le plafond est atteint) ;
    - jamais deux envois en cours qui partagent une clé (page : machine, article, savoir-faire ; plus de cause, refonte 2)
      ; le faux modèle écrit tous les textes de la refonte 2 (faux-textes) : « En bref » et « Astuces » de la machine,
      « À quoi il sert » de chaque article consommé, savoir-faire de l'astuce ; deux OT d'une même machine ou d'un même
      article partis ensemble seraient rejoués (pages changées pendant l'envoi) : aucun rejeu attendu.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_parallele.py" -v
"""
import json
import unittest

import test_wiki_ingestion as ingestion
from commun import CasNavigateur, charger_scripts
from faux_fournisseur_ia import FauxFournisseur

SCRIPTS = ["js/demo-donnees.js"] + ingestion.SCRIPTS + ["js/modules/wiki-journal.js"]
PROFIL_JS = """() => { window.App = { estResponsable: () => true, libelleProfil: () => 'Responsable',
  profil: { type: 'responsable', nom: 'Nicolas' } }; }"""
CHARGER_DEMO_JS = """async () => {
  // La démo porte son wiki figé (T122) : le test le reconstruit à partir d'un wiki vide.
  const tables = Object.assign({}, DEMO_DONNEES.tables);
  ['wiki_pages', 'wiki_journal'].forEach((nom) => { tables[nom] = tables[nom].split('\\r\\n')[0] + '\\r\\n'; });
  Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
  await Donnees.chargerTout();
}"""
# Ingestion de toute la démo puis validation de toutes les propositions, dans l'ordre de leur rang.
INGERER_JS = """async (agents) => {
  const ids = Donnees.lignes('ordres_travail').filter((o) => o.statut === 'Clôturé administrativement').map((o) => o.id);
  await Wiki.mettreEnFile(ids);
  let n = 0;
  let enVol = 0;
  let enVolMax = 0;
  const messages = {};
  // agents absent : le plafond par défaut de Prévo (Wiki.SEUILS.agentsSimultanes), comme l'écran.
  const bilan = await Wiki.traiterFile({ agents: agents || undefined, appeler: async (requete, donnees, annuler) => {
    n += 1;
    enVol += 1;                                   // appels en cours, comptés ici, hors de la comptabilité de Prévo
    enVolMax = Math.max(enVolMax, enVol);
    messages[donnees.ot.id] = requete.messages[1].content.split('\\nCatalogue des pages :')[0];
    try {
      if (agents !== 1) await new Promise((r) => setTimeout(r, (n * 37) % 23));      // réponses dans le désordre
      return await Ia.envoyerRequete(requete, annuler);
    } finally {
      enVol -= 1;
    }
  } });
  const aValider = Donnees.lignes('wiki_journal').filter((e) => e.statut === 'à valider').map((e) => e.id);
  const validation = await Wiki.valider(aValider);
  return {
    ot: ids.length, acceptees: bilan.acceptees, rien: bilan.rien, refusees: bilan.refusees, rejouees: bilan.rejouees,
    erreur: bilan.erreur && bilan.erreur.message, envois: bilan.envois, validees: validation.validees.length,
    aRefaire: validation.aRefaire.length,
    integrite: Wiki.verifierIntegrite({ envois: bilan.envois }),
    pages: Object.fromEntries(Donnees.lignes('wiki_pages').filter((l) => l.statut !== 'archivée')
      .map((l) => [l.titre, { texte: l.texte, type: l.type, ot: l.ot_cites, liens: l.liens, version: l.version }])),
    propositions: Object.fromEntries(Donnees.lignes('wiki_journal').filter((e) => e.nature === 'ingestion')
      .map((e) => [e.ot_id, { statut: e.statut, anterieure: e.anterieure,
        apres: JSON.parse(e.changements || '[]').map((c) => [c.titre, c.apres]) }])),
    agentsMax: Wiki.SEUILS.agentsSimultanes, enVolMax, messages,
    dates: Object.fromEntries(Donnees.lignes('ordres_travail').map((o) => [o.id, o.date_fin])),
  };
}"""


def simultanes(envois):
    """Plus grand nombre d'envois en cours en même temps (rangs debut/fin des événements)."""
    evenements = sorted([(e["debut"], 1) for e in envois] + [(e["fin"], -1) for e in envois])
    en_cours, maximum = 0, 0
    for _rang, pas in evenements:
        en_cours += pas
        maximum = max(maximum, en_cours)
    return maximum


class TestParallele(CasNavigateur):

    DELAI_PAR_DEFAUT_MS = 120000

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur(lenteur_s=1)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)

    def ingerer(self, agents):
        contexte = self.navigateur.new_context(locale="fr-FR")
        self.addCleanup(contexte.close)
        ingestion.regler_ia(contexte, url=self.faux.url, modele="faux-textes")
        page = contexte.new_page()
        page.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        self.surveiller(page)
        charger_scripts(page, SCRIPTS)
        page.evaluate(PROFIL_JS)
        page.evaluate(CHARGER_DEMO_JS)
        return page.evaluate(INGERER_JS, agents)

    def test_meme_wiki_avec_1_et_5_agents(self):
        seul = self.ingerer(1)
        agents = seul["agentsMax"]
        self.assertEqual(agents, 5)
        plusieurs = self.ingerer(None)                    # plafond par défaut de Prévo
        for nom, resultat in (("1 agent", seul), ("%d agents" % agents, plusieurs)):
            with self.subTest(nom):
                self.assertIsNone(resultat["erreur"])
                self.assertGreater(resultat["ot"], 200)
                self.assertEqual(resultat["acceptees"] + resultat["rien"] + resultat["refusees"], resultat["ot"])
                self.assertEqual((resultat["refusees"], resultat["rejouees"]), (0, 0))
                self.assertEqual((resultat["validees"], resultat["aRefaire"]), (resultat["acceptees"], 0))
                self.assertEqual(resultat["integrite"], {"ok": True, "ecarts": []})
                # Pour deux envois qui partagent une clé (machine, article ou savoir-faire) : le plus ancien (date
                # d'intervention, puis numéro d'OT) a fini avant que le plus récent parte — jamais ensemble, jamais
                # dans le désordre.
                envois = resultat["envois"]
                rang = lambda e: (resultat["dates"][e["ot"]], e["ot"])  # noqa: E731
                for n, a in enumerate(envois):
                    for b in envois[n + 1:]:
                        if set(a["cles"]) & set(b["cles"]):
                            ancien, recent = (a, b) if rang(a) < rang(b) else (b, a)
                            self.assertLess(ancien["fin"], recent["debut"], (ancien, recent))
        self.assertEqual(simultanes(seul["envois"]), 1)
        self.assertLessEqual(simultanes(plusieurs["envois"]), agents)
        self.assertEqual(simultanes(plusieurs["envois"]), agents)             # le parallélisme a eu lieu
        # Mesuré aussi dans `appeler`, hors de la comptabilité de Prévo.
        self.assertEqual((seul["enVolMax"], plusieurs["enVolMax"]), (1, agents))
        # Mêmes requêtes, catalogue mis à part : le catalogue d'un envoi dépend des OT déjà finis sur d'autres pages
        # (pages créées par eux), et c'est la seule différence permise (précision de D112).
        self.assertEqual(sorted(plusieurs["messages"]), sorted(seul["messages"]))
        differents = [ot for ot in seul["messages"] if plusieurs["messages"][ot] != seul["messages"][ot]]
        self.assertEqual(differents, [])
        # Même wiki : chaque page, chaque proposition.
        self.assertEqual(sorted(plusieurs["pages"]), sorted(seul["pages"]))
        for titre, page in seul["pages"].items():
            with self.subTest(page=titre):
                self.assertEqual(plusieurs["pages"][titre], page)
        self.assertEqual(plusieurs["propositions"], seul["propositions"])
        self.assertGreater(len(seul["pages"]), 30)
        # Les textes de la refonte 2 seulement : machines, articles consommés (« À quoi il sert »), savoir-faire.
        types = [p["type"] for p in seul["pages"].values()]
        self.assertEqual(set(types), {"équipement", "composant", "savoir-faire"})
        self.assertGreater(types.count("composant"), 10)
        self.assertTrue(any("## Astuces" in p["texte"] for p in seul["pages"].values() if p["type"] == "équipement"))
        self.assertFalse(any(cle.startswith("CAUSE:") for e in seul["envois"] for cle in e["cles"]))
        # Toute la démo, dans l'ordre des dates : aucun OT n'arrive après des faits plus récents de ses pages.
        self.assertTrue(all(p["anterieure"] == "0" for p in seul["propositions"].values()))


if __name__ == "__main__":
    unittest.main()
