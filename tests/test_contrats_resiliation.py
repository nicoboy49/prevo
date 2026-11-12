"""Tests de la résiliation des contrats tacites aux dates périmées et du compteur des garanties « bientôt » (T503).

Relecture R5 du 12/11/2026 (lot L7), D198 : « un contrat tacite aux dates périmées doit être reconduit avant de noter
sa résiliation ». Avant la correction, « Noter la résiliation » n'était refusée qu'au statut « dates à mettre à
jour » : un contrat « à décider » sur une période CALCULÉE, dont la fin ENREGISTRÉE est
passée, devenait « terminé » à son ancienne fin (plus d'alerte, sorti du total des montants) et « Reconduire » était
ensuite refusé. Second défaut : l'accueil (Garanties.aEcheance) et l'écran Garanties ne comptaient pas les mêmes
garanties « bientôt » (équipements au rebut ou désactivés).

Sans navigateur : les scripts du dépôt sont chargés tels quels dans un contexte `vm` de Node, horloge figée au
12/11/2026, données passées à StockageDemo.creer (jeu écrit à la main dans ce fichier, aucune donnée réelle).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_contrats_resiliation.py" -v
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HARNAIS = r"""
const vm = require('vm'), fs = require('fs'), path = require('path');
const RACINE = process.argv[2];
const SCRIPTS = ['js/i18n.js', 'js/i18n/langues.js', 'js/i18n/fr.js', 'js/lib/papaparse.min.js', 'js/schema.js',
  'js/donnees.js', 'js/stockage-demo.js', 'js/interface.js',
  { code: "var App = { mode: 'demo', estResponsable: () => true, estTechnicien: () => false, comptesExiges: () => false, raisonErreur: (e) => e.message, definirTitre() {} };" },
  'js/modules/controles-regles.js', 'js/modules/garanties-regles.js', 'js/modules/garanties-ecritures.js',
  'js/modules/garanties-ecrans.js'];
// Horloge figée : le 12/11/2026 à 10 h (heure locale).
const HORLOGE = "(() => { const Vraie = Date; const fige = new Vraie(2026, 10, 12, 10, 0, 0).getTime();"
  + " Date = class extends Vraie { constructor(...a) { if (a.length) super(...a); else super(fige); } static now() { return fige; } }; })();";
const csv = (entete, lignes) => [entete].concat(lignes).join('\r\n') + '\r\n';

async function contexte(tables) {
  const stock = new Map();
  const ctx = { console, setTimeout, clearTimeout, TextEncoder, TextDecoder, Blob, EventTarget, CustomEvent, Event, URL,
    URLSearchParams, Intl, structuredClone, queueMicrotask, crypto: require('crypto').webcrypto,
    localStorage: { getItem: (k) => (stock.has(k) ? stock.get(k) : null), setItem: (k, v) => stock.set(k, String(v)), removeItem: (k) => stock.delete(k) },
    navigator: { language: 'fr-FR', languages: ['fr-FR'], userAgent: 'node' },
    location: { protocol: 'file:', hash: '', search: '', href: 'file:///x' } };
  const el = () => new Proxy(function () {}, { get: (t, p) => (p === Symbol.toPrimitive ? () => '' : p === 'length' ? 0 : el()), apply: () => el(), set: () => true });
  ctx.document = { documentElement: { lang: 'fr', setAttribute() {}, getAttribute() { return 'fr'; }, dataset: {}, style: {} },
    addEventListener() {}, querySelector: () => null, querySelectorAll: () => [], createElement: () => el(), body: el(), head: el(), currentScript: null };
  ctx.window = ctx; ctx.self = ctx; ctx.globalThis = ctx; ctx.addEventListener = () => {};
  ctx.matchMedia = () => ({ matches: false, addEventListener() {} });
  vm.createContext(ctx);
  vm.runInContext(HORLOGE, ctx);
  for (const s of SCRIPTS) {
    if (typeof s === 'object') vm.runInContext(s.code, ctx, { filename: 'app-factice' });
    else vm.runInContext(fs.readFileSync(path.join(RACINE, s), 'utf8'), ctx, { filename: s });
  }
  ctx.tables = tables;
  const run = (code) => vm.runInContext(code, ctx);
  await run("Donnees.initialiser(StockageDemo.creer(tables), { poste: 'P', profil: 'R' }); Donnees.chargerTout()");
  return run;
}

const ENTETE_CONTRATS = 'id;fournisseur_id;objet;equipement_ids;perimetre;date_debut;date_fin;preavis_mois;reconduction_tacite;reconduction_mois;montant_annuel;document;actif';
const CONTRATS = {
  // tacite, fin enregistrée passée, période calculée jusqu'au 31/12/2026, date limite 30/11/2026 : « à décider »
  a_decider_perime: 'CTP-0001;FOU-0001;Maintenance compresseurs;;;2025-01-01;2025-12-31;1;1;12;4800;;1',
  // tacite, fin enregistrée passée, période calculée, date limite 30/09/2026 passée : « dates à mettre à jour »
  limite_passee_perime: 'CTP-0001;FOU-0001;Presses;;;2025-01-01;2025-12-31;3;1;12;4800;;1',
  // tacite, fin enregistrée passée, durée de reconduction inconnue : « dates à mettre à jour »
  a_mettre_a_jour: 'CTP-0001;FOU-0001;Ponts;;;2025-01-01;2025-12-31;1;1;;4800;;1',
  // tacite, dates à jour, date limite 30/11/2026 : « à décider », résiliation permise
  a_decider_a_jour: 'CTP-0001;FOU-0001;Portes;;;2026-01-01;2026-12-31;1;1;12;4800;;1',
};
const ETAT = "(e => ({ statut: e.statut, fin: e.fin, finPeriode: e.finPeriode, periodeCalculee: e.periodeCalculee, dateLimite: e.dateLimite, alerte: e.alerte }))"
  + "(Garanties.etatContrat(Donnees.trouver('contrats_prestataires', 'CTP-0001')))";
const RESILIER = "Garanties.noterResiliation('CTP-0001', { date: Donnees.aujourdhui(), commentaire: 'LRAR' })";

async function contrat(nom, etapes) {
  const run = await contexte({
    fournisseurs: csv('id;nom', ['FOU-0001;Presta']),
    contrats_prestataires: csv(ENTETE_CONTRATS, [CONTRATS[nom]]),
    journal: csv('id;date_heure;poste;utilisateur;table;id_ligne;action', []),
  });
  const photo = async () => ({
    etat: await run(ETAT), tacite: await run("Donnees.trouver('contrats_prestataires', 'CTP-0001').reconduction_tacite"),
    total: await run('Garanties.totalMontants().centimes'), journal: await run("Donnees.lignes('journal').map((l) => l.action)"),
    enAlerte: await run('Garanties.aEcheance().contrats.length'),
  });
  const sortie = { aujourdhui: await run('Donnees.aujourdhui()'), avant: await photo(), etapes: [],
    messageAttendu: await run("I18n.t('garanties.noter_resiliation.reconduire_d_abord', { fin: '31/12/2025' })") };
  for (const etape of etapes) {
    const resultat = { etape };
    try { resultat.rendu = await run(etape === 'resilier' ? RESILIER : "Garanties.reconduireContrat('CTP-0001', {})"); }
    catch (erreur) { resultat.refus = String(erreur && erreur.message); }
    Object.assign(resultat, await photo());
    sortie.etapes.push(resultat);
  }
  return sortie;
}

async function garanties() {
  const run = await contexte({
    equipements: csv('id;repere;designation;statut;actif', ['EQ-0001;CP-01;Compresseur;en service;1',
      'EQ-0002;TO-02;Tour ancien;rebut;1', 'EQ-0003;PE-03;Perceuse retirée;en service;0']),
    garanties: csv('id;equipement_id;fournisseur_id;date_debut;date_fin;conditions;document;actif', [
      'GAR-0001;EQ-0001;;2024-12-01;2026-12-01;;;1', 'GAR-0002;EQ-0002;;2024-12-01;2026-12-01;;;1',
      'GAR-0003;EQ-0003;;2024-12-01;2026-12-01;;;1', 'GAR-0004;EQ-0001;;2025-01-01;2028-01-01;;;1']),
    journal: csv('id;date_heure;poste;utilisateur;table;id_ligne;action', []),
  });
  return run(`(() => {
    const jour = Donnees.aujourdhui(), delai = Garanties.delaiAlerte();
    const lignes = Garanties.interne.lignesDe('garanties', jour, delai);
    const filtre = (valeur) => lignes.filter(Garanties.interne.filtresDe('garanties').find((f) => f.valeur === valeur).garder).map((l) => l.ligne.id).sort();
    return { accueil: Garanties.aEcheance().garanties.map((l) => l.id).sort(), ecranBientot: filtre('bientot'),
      ecranSousGarantie: filtre('sous-garantie'), liste: lignes.map((l) => l.ligne.id).sort(),
      statuts: Object.fromEntries(lignes.map((l) => [l.ligne.id, l.etat.statut])) };
  })()`);
}

(async () => {
  const sortie = {
    a_decider_perime: await contrat('a_decider_perime', ['resilier', 'reconduire', 'resilier']),
    limite_passee_perime: await contrat('limite_passee_perime', ['resilier']),
    a_mettre_a_jour: await contrat('a_mettre_a_jour', ['resilier']),
    a_decider_a_jour: await contrat('a_decider_a_jour', ['resilier']),
    garanties: await garanties(),
  };
  console.log('<<<JSON' + JSON.stringify(sortie) + 'JSON>>>');
})().catch((erreur) => { console.error('ECHEC', erreur); process.exit(1); });
"""


class ContratsResiliation(unittest.TestCase):
    """Un seul lancement de Node pour tous les scénarios (setUpClass), puis des constats sur son résultat."""

    @classmethod
    def setUpClass(cls):
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node introuvable sur ce poste")
        dossier = tempfile.mkdtemp(prefix="prevo-t503-")
        try:
            script = os.path.join(dossier, "harnais.js")
            with open(script, "w", encoding="utf-8", newline="\n") as fichier:
                fichier.write(HARNAIS)
            lance = subprocess.run([node, script, RACINE], capture_output=True, text=True, encoding="utf-8",
                                   timeout=120)
        finally:
            shutil.rmtree(dossier, ignore_errors=True)
        if lance.returncode != 0 or "<<<JSON" not in lance.stdout:
            raise AssertionError("harnais Node en échec :\n" + lance.stdout[-2000:] + "\n" + lance.stderr[-3000:])
        cls.r = json.loads(lance.stdout.split("<<<JSON", 1)[1].split("JSON>>>", 1)[0])

    def test_horloge_figee(self):
        self.assertEqual(self.r["a_decider_perime"]["aujourdhui"], "2026-11-12")

    # --- D198 : contrat tacite « à décider » dont la fin enregistrée est passée -----------------------------------

    def test_situation_de_depart_a_decider_sur_periode_calculee(self):
        avant = self.r["a_decider_perime"]["avant"]
        self.assertEqual(avant["etat"], {"statut": "a_decider", "fin": "2025-12-31", "finPeriode": "2026-12-31",
                                         "periodeCalculee": True, "dateLimite": "2026-11-30", "alerte": True})
        self.assertEqual(avant["total"], 480000)

    def test_resiliation_refusee_reconduire_d_abord(self):
        cas = self.r["a_decider_perime"]
        etape = cas["etapes"][0]
        self.assertNotIn("rendu", etape, "la résiliation d'un contrat tacite aux dates périmées doit être refusée")
        self.assertEqual(etape["refus"], cas["messageAttendu"])
        self.assertIn("31/12/2025", etape["refus"])
        # rien n'est écrit : le contrat reste tacite, « à décider », en alerte, dans le total ; journal vide
        self.assertEqual(etape["tacite"], "1")
        self.assertEqual(etape["etat"], cas["avant"]["etat"])
        self.assertEqual(etape["total"], 480000)
        self.assertEqual(etape["enAlerte"], 1)
        self.assertEqual(etape["journal"], [])

    def test_reconduire_puis_resilier_donne_la_bonne_fin(self):
        _, reconduit, resilie = self.r["a_decider_perime"]["etapes"]
        self.assertNotIn("refus", reconduit)
        self.assertEqual(reconduit["etat"], {"statut": "a_decider", "fin": "2026-12-31", "finPeriode": "2026-12-31",
                                             "periodeCalculee": False, "dateLimite": "2026-11-30", "alerte": True})
        self.assertNotIn("refus", resilie)
        self.assertEqual(resilie["rendu"], ["reconduction_tacite"])
        self.assertEqual(resilie["tacite"], "0")
        # la prestation court jusqu'au 31/12/2026 : « se termine bientôt », toujours en alerte et dans le total
        self.assertEqual(resilie["etat"]["statut"], "bientot")
        self.assertEqual(resilie["etat"]["fin"], "2026-12-31")
        self.assertEqual(resilie["etat"]["finPeriode"], "2026-12-31")
        self.assertEqual(resilie["total"], 480000)
        self.assertEqual(resilie["enAlerte"], 1)
        self.assertTrue(any("résiliation notée : lettre du 12/11/2026 ; LRAR" in action for action in resilie["journal"]),
                        resilie["journal"])

    def test_limite_passee_sur_periode_calculee_toujours_refuse(self):
        cas = self.r["limite_passee_perime"]
        self.assertEqual(cas["avant"]["etat"]["statut"], "a_mettre_a_jour")
        self.assertTrue(cas["avant"]["etat"]["periodeCalculee"])
        self.assertEqual(cas["etapes"][0].get("refus"), cas["messageAttendu"])
        self.assertEqual(cas["etapes"][0]["tacite"], "1")
        self.assertEqual(cas["etapes"][0]["total"], 480000)

    def test_dates_a_mettre_a_jour_toujours_refuse(self):
        cas = self.r["a_mettre_a_jour"]
        self.assertEqual(cas["avant"]["etat"]["statut"], "a_mettre_a_jour")
        self.assertEqual(cas["etapes"][0].get("refus"), cas["messageAttendu"])
        self.assertEqual(cas["etapes"][0]["tacite"], "1")

    def test_contrat_aux_dates_a_jour_toujours_resiliable(self):
        cas = self.r["a_decider_a_jour"]
        self.assertEqual(cas["avant"]["etat"]["statut"], "a_decider")
        self.assertFalse(cas["avant"]["etat"]["periodeCalculee"])
        etape = cas["etapes"][0]
        self.assertEqual(etape.get("rendu"), ["reconduction_tacite"])
        self.assertEqual(etape["etat"]["statut"], "bientot")
        self.assertEqual(etape["etat"]["fin"], "2026-12-31")
        self.assertEqual(etape["total"], 480000)

    # --- Garanties « bientôt » : une seule règle pour l'accueil et pour l'écran -----------------------------------

    def test_garanties_bientot_meme_nombre_a_l_accueil_et_a_l_ecran(self):
        g = self.r["garanties"]
        self.assertEqual(g["accueil"], ["GAR-0001"])
        self.assertEqual(g["ecranBientot"], g["accueil"])

    def test_garanties_hors_suivi_restent_dans_la_liste(self):
        g = self.r["garanties"]
        self.assertEqual(g["liste"], ["GAR-0001", "GAR-0002", "GAR-0003", "GAR-0004"])
        self.assertEqual(g["ecranSousGarantie"], ["GAR-0001", "GAR-0002", "GAR-0003", "GAR-0004"])
        # le statut affiché ne change pas : seuls le filtre et le compteur « bientôt » suivent la règle de l'accueil
        self.assertEqual(g["statuts"], {"GAR-0001": "bientot", "GAR-0002": "bientot", "GAR-0003": "bientot",
                                        "GAR-0004": "en_cours"})


if __name__ == "__main__":
    unittest.main()
