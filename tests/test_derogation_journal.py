"""Dérogation d'habilitation RG8 et journal (T504 ; D186, D191, CS178 ; relecture R5 du 12/11). Sans navigateur.

    py -X utf8 -m unittest discover -s tests -p "test_derogation_journal.py" -v

Les scripts classiques de Prévo sont chargés sous Node (contexte vm), sur des tables d'essai en mémoire
(StockageDemo) : aucune donnée réelle. Deux défauts fermés :
  1. le marqueur « dérogation habilitation : … » n'est reconnu que dans une ligne de journal écrite par une écriture
     qui affecte (création, préparation, passage à « Planifié », planification), jamais dans un motif libre ;
  2. une dérogation dont la ligne de journal n'a pas pu être écrite n'est pas annoncée comme enregistrée.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

HARNAIS = r"""
const vm = require('vm'), fs = require('fs'), path = require('path');
const RACINE = process.argv[2];
const SCRIPTS = ['js/i18n.js', 'js/i18n/langues.js', 'js/i18n/fr.js', 'js/lib/papaparse.min.js', 'js/schema.js',
  'js/donnees.js', 'js/stockage-demo.js', 'js/interface.js', null, 'js/modules/ordres-regles.js',
  'js/modules/ordres-ecritures.js', 'js/modules/equipe-regles.js', 'js/modules/planning-regles.js',
  'js/modules/planning-ecritures.js'];
const APP = `var profil = 'responsable'; var comptes = false;
  var App = { estResponsable: () => profil === 'responsable', estTechnicien: () => profil === 'technicien',
    comptesExiges: () => comptes, session: { identifiant: 'nicolas.briand' }, raisonErreur: (e) => e.message };`;
const csv = (entete, lignes) => [entete].concat(lignes).join('\r\n') + '\r\n';
const MARQUEUR = 'dérogation habilitation : TEC-0004 le 2099-01-15 sans BR (échue) ; motif : urgence, accompagné';
const SANS_RAISON = 'dérogation habilitation : TEC-0004 le 2099-01-15 sans BR ; motif : vu avec le chef';

// Contexte neuf : un équipement qui exige BR, TEC-0004 dont la BR est échue, des OT, un journal donné.
async function contexte(ots, journal) {
  const stock = new Map();
  const c = { console: { log() {}, warn() {}, error() {}, info() {} }, setTimeout, clearTimeout, TextEncoder, TextDecoder,
    Blob, EventTarget, CustomEvent, Event, URL, URLSearchParams, Intl, structuredClone, queueMicrotask,
    crypto: require('crypto').webcrypto,
    localStorage: { getItem: (k) => (stock.has(k) ? stock.get(k) : null), setItem: (k, v) => stock.set(k, String(v)), removeItem: (k) => stock.delete(k) },
    navigator: { language: 'fr-FR', languages: ['fr-FR'], userAgent: 'node' },
    location: { protocol: 'file:', hash: '', search: '', href: 'file:///x' } };
  const el = () => new Proxy(function () {}, { get: (t, p) => (p === Symbol.toPrimitive ? () => '' : p === 'length' ? 0 : el()), apply: () => el(), set: () => true });
  c.document = { documentElement: { lang: 'fr', setAttribute() {}, getAttribute() { return 'fr'; }, dataset: {}, style: {} },
    addEventListener() {}, querySelector: () => null, querySelectorAll: () => [], createElement: () => el(), body: el(), head: el(), currentScript: null };
  c.window = c; c.self = c; c.globalThis = c; c.addEventListener = () => {}; c.matchMedia = () => ({ matches: false, addEventListener() {} });
  vm.createContext(c);
  for (const s of SCRIPTS) {
    if (s === null) vm.runInContext(APP, c, { filename: 'app-essai' });
    else vm.runInContext(fs.readFileSync(path.join(RACINE, s), 'utf8'), c, { filename: s });
  }
  c.run = (code) => vm.runInContext(code, c);
  c.tables = {
    equipements: csv('id;repere;designation;statut;actif;habilitation_requise', ['EQ-0002;AE-03;Armoire;en service;1;BR']),
    techniciens: csv('id;nom;prenom;actif', ['TEC-0004;Garnier;Thomas;1']),
    habilitations: csv('id;technicien_id;intitule;date_obtention;date_echeance', ['HAB-0004;TEC-0004;BR;2023-06-01;2026-05-31']),
    ordres_travail: csv('id;statut;type;priorite;origine;equipement_id;technicien_id;date_prevue;date_creation;titre;date_debut', ots),
    journal: csv('id;date_heure;poste;profil;table;id_ligne;action', journal || []),
  };
  c.adaptateur = c.run('StockageDemo.creer(tables)');
  const ajouter = c.adaptateur.ajouter.bind(c.adaptateur);
  c.panneJournal = false;
  c.adaptateur.ajouter = async (table, octets) => {
    if (table === 'journal' && c.panneJournal) throw new Error('journal.csv verrouillé (ouvert dans Excel)');
    return ajouter(table, octets);
  };
  await c.run(`Donnees.initialiser(adaptateur, { poste: 'P', profil: 'Responsable' }); Donnees.chargerTout()`);
  // essai(code) → { rendu } ou { refus: message, habilitation: vrai si l'erreur porte un refus RG8, classe }.
  c.essai = async (code) => {
    try { return { rendu: await c.run(code) }; }
    catch (e) { return { refus: e.message, habilitation: Boolean(e.habilitation), classe: e.name }; }
  };
  c.actions = async () => { await c.run(`Donnees.rechargerTable('journal')`); return c.run(`Donnees.lignes('journal').map((l) => l.action)`); };
  return c;
}
const OT = (id, statut, technicien, date) => id + ';' + statut + ';correctif différé;P3;manuel;EQ-0002;' + (technicien || '') + ';' + (date || '')
  + ';2026-11-01 08:00;Essai;' + (statut === 'En cours' ? '2026-11-02 08:00' : '');
const AFFECTER = `Ordres.interne.modifierOt('OT-2026-0001', { technicien_id: 'TEC-0004', date_prevue: '2099-01-15' }, 'préparation')`;
const AFFECTER_OUTRE = `Ordres.interne.modifierOt('OT-2026-0001', { technicien_id: 'TEC-0004', date_prevue: '2099-01-15' }, 'préparation',
  { passerOutreHabilitation: true, motifDerogation: 'urgence, accompagné' })`;
const ACCORDEE = (id) => `Boolean(Ordres.derogationAccordee('${id}', 'TEC-0004', '2099-01-15', ['BR']))`;

(async () => {
  const r = {};

  // 1. Marqueur forgé par un technicien dans un motif de mise en attente (scénario du relecteur).
  let c = await contexte([OT('OT-2026-0001', 'En cours')]);
  c.run(`profil = 'technicien'`);
  r.forge_attente = await c.essai(`Ordres.changerStatut('OT-2026-0001', 'En cours', 'En attente', { motif_attente: 'pièce ; ${SANS_RAISON}' })`);
  await c.essai(`Ordres.changerStatut('OT-2026-0001', 'En attente', 'En cours', {})`);
  c.run(`profil = 'responsable'`);
  r.forge_journal = await c.actions();
  r.forge_accordee = c.run(ACCORDEE('OT-2026-0001'));
  r.forge_affectation = await c.essai(AFFECTER);
  r.forge_ot = c.run(`Donnees.trouver('ordres_travail', 'OT-2026-0001').technicien_id`);

  // 2. Lignes de journal : formes écrites par la 2.2.0-beta.1 (reconnues) et textes libres (jamais reconnus).
  const lignes = {
    preparation: 'modification : technicien_id, date_prevue — préparation ; ' + MARQUEUR,
    preparation_compte: 'modification : date_prevue, technicien_id — préparation ; dérogation habilitation : TEC-0004 le 2099-01-15 sans BR (échue) ; compte : nicolas.briand ; motif : urgence',
    preparation_autre_langue: 'modification : technicien_id — preparation ; ' + MARQUEUR,
    sans_action: 'modification : habilitation_requise — ' + MARQUEUR,
    creation: "création — création de l'OT (manuel) ; " + MARQUEUR,
    statut_planifie: 'modification : statut — statut Préparé → Planifié ; ' + MARQUEUR,
    planification: 'modification : statut, technicien_id, date_prevue — planification : TEC-0004 le 2099-01-15 (Préparé → Planifié) ; ' + MARQUEUR,
    replanification: 'modification : date_prevue — replanification : TEC-0004 le 2099-01-15 ; ' + MARQUEUR,
    forge_attente: 'modification : motif_attente, statut — statut En cours → En attente : pièce ; ' + SANS_RAISON,
    forge_annulation: 'modification : motif_annulation, statut — statut Créé → Annulé : doublon ; ' + MARQUEUR,
    forge_priorite: 'modification : priorite — priorité P3 → P1 : client ; ' + MARQUEUR,
    forge_planifie_motif: 'modification : statut — statut Préparé → Planifié : x ; ' + MARQUEUR,
    forge_acceptation: 'création — acceptation de DI-2026-0001 ; priorité P3 → P1 : x ; ' + MARQUEUR,
    forge_champ_affecte: 'modification : technicien_id, statut — statut En cours → En attente : pièce ; ' + MARQUEUR,
    forge_nu: MARQUEUR,
  };
  const noms = Object.keys(lignes);
  const journal = noms.map((nom, i) => 'J-2026111208000' + (i % 10) + '-A' + String(100 + i) + ';2026-11-12 08:00:0' + (i % 10)
    + ';P;Responsable;ordres_travail;OT-2026-' + String(1001 + i) + ';"' + lignes[nom].replace(/"/g, '""') + '"');
  c = await contexte([OT('OT-2026-0001', 'Préparé')], journal);
  r.lignes = {};
  noms.forEach((nom, i) => { r.lignes[nom] = c.run(ACCORDEE('OT-2026-' + String(1001 + i))); });

  // 3. Mode serveur avec comptes : une ligne dont le profil n'est pas le responsable ne vaut pas dérogation.
  const profils = { responsable: 'Responsable', technicien: 'Technicien TEC-0004', demandeur: 'Demandeur Paul', vide: '' };
  const cles = Object.keys(profils);
  c = await contexte([OT('OT-2026-0001', 'Préparé')], cles.map((cle, i) => 'J-2026111208000' + i + '-B10' + i + ';2026-11-12 08:00:0' + i
    + ';P;' + profils[cle] + ';ordres_travail;OT-2026-' + String(2001 + i) + ';"' + lignes.preparation + '"'));
  r.profils_hors_comptes = {}; r.profils_comptes = {};
  cles.forEach((cle, i) => { r.profils_hors_comptes[cle] = c.run(ACCORDEE('OT-2026-' + String(2001 + i))); });
  c.run('comptes = true');
  cles.forEach((cle, i) => { r.profils_comptes[cle] = c.run(ACCORDEE('OT-2026-' + String(2001 + i))); });

  // 4. Chemin normal : dérogation accordée à la préparation, puis « Planifier » ne redemande pas.
  c = await contexte([OT('OT-2026-0001', 'Préparé')]);
  r.normal_refus = await c.essai(AFFECTER);
  r.normal_affectation = await c.essai(AFFECTER_OUTRE);
  r.normal_accordee = c.run(ACCORDEE('OT-2026-0001'));
  r.normal_planifier = await c.essai(`Ordres.changerStatut('OT-2026-0001', 'Préparé', 'Planifié', {})`);
  r.normal_journal = await c.actions();

  // 5. Journal en panne pendant la dérogation : pas de succès annoncé, OT écrit, dérogation redemandée ensuite.
  c = await contexte([OT('OT-2026-0001', 'Préparé')]);
  c.panneJournal = true;
  r.panne_affectation = await c.essai(AFFECTER_OUTRE);
  r.panne_attendu = c.run(`I18n.t('ordres.derogation.non_tracee', { otId: 'OT-2026-0001' })`);
  r.panne_sans_derogation = await c.essai(`Ordres.interne.modifierOt('OT-2026-0001', { titre: 'Autre titre' }, 'préparation')`);
  c.panneJournal = false;
  r.panne_journal = await c.actions();
  r.panne_ot = c.run(`(o => o.technicien_id + ' ' + o.date_prevue + ' ' + o.titre)(Donnees.trouver('ordres_travail', 'OT-2026-0001'))`);
  r.panne_accordee = c.run(ACCORDEE('OT-2026-0001'));
  r.panne_planifier = await c.essai(`Ordres.changerStatut('OT-2026-0001', 'Préparé', 'Planifié', {})`);
  r.panne_planifier_outre = await c.essai(`Ordres.changerStatut('OT-2026-0001', 'Préparé', 'Planifié', {}, { passerOutreHabilitation: true, motifDerogation: 'urgence' })`);
  r.panne_journal_apres = await c.actions();

  // 6. Mêmes pannes par les autres écritures qui accordent une dérogation : création, « Planifier », planning.
  const OUTRE = `{ passerOutreHabilitation: true, motifDerogation: 'urgence' }`;
  c = await contexte([OT('OT-2026-0001', 'Préparé', 'TEC-0004', '2099-01-15'), OT('OT-2026-0002', 'Préparé')]);
  c.panneJournal = true;
  r.panne_statut = await c.essai(`Ordres.changerStatut('OT-2026-0001', 'Préparé', 'Planifié', {}, ${OUTRE})`);
  r.panne_planning = await c.essai(`Planning.planifier('OT-2026-0002', 'Préparé', 'TEC-0004', '2099-01-15', ${OUTRE})`);
  r.panne_creation = await c.essai(`Ordres.creer({ equipement_id: 'EQ-0002', titre: 'Neuf', type: 'correctif différé', priorite: 'P3',
    technicien_id: 'TEC-0004', date_prevue: '2099-01-15' }, ${OUTRE})`);
  r.panne_statuts = c.run(`Donnees.lignes('ordres_travail').map((o) => o.id + ' ' + o.statut + ' ' + o.technicien_id)`);
  // Un motif libre qui contient le marqueur, journal en panne : ce n'est pas une dérogation, l'action réussit.
  c = await contexte([OT('OT-2026-0001', 'En cours')]);
  c.panneJournal = true;
  r.panne_motif_libre = await c.essai(`Ordres.changerStatut('OT-2026-0001', 'En cours', 'En attente', { motif_attente: 'pièce ; ${SANS_RAISON}' })`);
  // Planning, chemin normal : la dérogation notée par la planification est relue.
  c = await contexte([OT('OT-2026-0002', 'Préparé')]);
  r.planning_normal = await c.essai(`Planning.planifier('OT-2026-0002', 'Préparé', 'TEC-0004', '2099-01-15', ${OUTRE})`);
  r.planning_accordee = c.run(ACCORDEE('OT-2026-0002'));
  r.planning_journal = await c.actions();

  process.stdout.write('RESULTAT ' + JSON.stringify(r) + '\n');
})().catch((e) => { process.stderr.write('ECHEC ' + (e && e.stack || e) + '\n'); process.exit(1); });
"""

NON_TRACEE = "la dérogation n'a pas pu être notée au journal"


@unittest.skipUnless(shutil.which("node"), "Node absent : modules non chargés")
class DerogationJournal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "harnais.js"
            script.write_text(HARNAIS, encoding="utf-8")
            fini = subprocess.run(["node", str(script), str(RACINE)], capture_output=True, encoding="utf-8", timeout=120)
        if fini.returncode != 0:
            raise AssertionError("harnais Node : " + fini.stderr[-1500:])
        ligne = [l for l in fini.stdout.splitlines() if l.startswith("RESULTAT ")][-1]
        cls.r = json.loads(ligne[len("RESULTAT "):])

    # --- Vérité 1 : un motif d'attente qui contient le texte d'une dérogation ne vaut pas dérogation ---
    def test_motif_d_attente_forge_le_responsable_est_interroge(self):
        r = self.r
        self.assertEqual(r["forge_attente"].get("rendu"), "En attente")
        self.assertTrue(any("En attente : pièce ; dérogation habilitation : TEC-0004" in a for a in r["forge_journal"]))
        self.assertFalse(r["forge_accordee"])
        self.assertTrue(r["forge_affectation"].get("habilitation"), r["forge_affectation"])
        self.assertIn("Affectation refusée", r["forge_affectation"]["refus"])
        self.assertEqual(r["forge_ot"], "")

    def test_textes_libres_jamais_lus_comme_derogation(self):
        for nom in ("forge_attente", "forge_annulation", "forge_priorite", "forge_planifie_motif", "forge_acceptation",
                    "forge_champ_affecte", "forge_nu"):
            self.assertFalse(self.r["lignes"][nom], nom)

    def test_derogations_au_format_actuel_toujours_reconnues(self):
        for nom in ("preparation", "preparation_compte", "preparation_autre_langue", "sans_action", "creation",
                    "statut_planifie", "planification", "replanification"):
            self.assertTrue(self.r["lignes"][nom], nom)

    def test_mode_comptes_seul_le_profil_responsable(self):
        self.assertEqual(self.r["profils_hors_comptes"],
                         {"responsable": True, "technicien": True, "demandeur": True, "vide": True})
        self.assertEqual(self.r["profils_comptes"],
                         {"responsable": True, "technicien": False, "demandeur": False, "vide": True})

    # --- Chemin normal : dérogation accordée, puis « Planifier » ne redemande pas ---
    def test_chemin_normal_planifier_ne_redemande_pas(self):
        r = self.r
        self.assertTrue(r["normal_refus"].get("habilitation"))
        self.assertEqual(sorted(r["normal_affectation"]["rendu"]), ["date_prevue", "technicien_id"])
        self.assertTrue(r["normal_accordee"])
        self.assertEqual(r["normal_planifier"].get("rendu"), "Planifié", r["normal_planifier"])
        marquees = [a for a in r["normal_journal"] if "dérogation habilitation : " in a]
        self.assertEqual(len(marquees), 1, r["normal_journal"])
        self.assertTrue(marquees[0].endswith(
            "— préparation ; dérogation habilitation : TEC-0004 le 2099-01-15 sans BR (échue) ; motif : urgence, accompagné"))

    def test_planning_derogation_notee_et_relue(self):
        r = self.r
        self.assertEqual(r["planning_normal"].get("rendu", {}).get("statut"), "Planifié", r["planning_normal"])
        self.assertTrue(r["planning_accordee"])
        self.assertTrue(any("planification : TEC-0004 le 2099-01-15 (Préparé → Planifié) ; dérogation habilitation : " in a
                            for a in r["planning_journal"]))

    # --- Vérité 2 : si l'écriture du journal échoue, le responsable est prévenu que la dérogation n'est pas tracée ---
    def test_journal_en_panne_le_responsable_est_prevenu(self):
        r = self.r
        self.assertNotIn("rendu", r["panne_affectation"])
        self.assertEqual(r["panne_affectation"]["refus"], r["panne_attendu"])
        self.assertIn(NON_TRACEE, r["panne_attendu"])
        self.assertIn("OT-2026-0001", r["panne_attendu"])
        self.assertFalse(r["panne_affectation"]["habilitation"])

    def test_journal_en_panne_ot_ecrit_et_derogation_redemandee(self):
        r = self.r
        self.assertEqual(r["panne_journal"], [])
        self.assertEqual(r["panne_ot"], "TEC-0004 2099-01-15 Autre titre")      # pas de retour arrière
        self.assertFalse(r["panne_accordee"])
        self.assertTrue(r["panne_planifier"].get("habilitation"), r["panne_planifier"])     # « Planifier » redemande
        self.assertEqual(r["panne_planifier_outre"].get("rendu"), "Planifié")
        self.assertEqual(len([a for a in r["panne_journal_apres"] if "dérogation habilitation : " in a]), 1)

    def test_journal_en_panne_regle_generale_inchangee(self):
        # Une écriture sans dérogation n'échoue pas quand le journal ne s'écrit pas (règle du socle).
        self.assertEqual(self.r["panne_sans_derogation"].get("rendu"), ["titre"])
        self.assertEqual(self.r["panne_motif_libre"].get("rendu"), "En attente")

    def test_journal_en_panne_autres_ecritures(self):
        r = self.r
        for nom in ("panne_statut", "panne_planning", "panne_creation"):
            self.assertIn(NON_TRACEE, r[nom].get("refus", ""), (nom, r[nom]))
        self.assertIn("OT-2026-0001 Planifié TEC-0004", r["panne_statuts"])
        self.assertIn("OT-2026-0002 Planifié TEC-0004", r["panne_statuts"])
        self.assertEqual(len(r["panne_statuts"]), 3)                           # l'OT créé existe
        self.assertIn(r["panne_statuts"][2].split(" ")[0], r["panne_creation"]["refus"])


if __name__ == "__main__":
    unittest.main()
