"""Tests du cœur de js/donnees.js (section 4) et de js/stockage-demo.js (tâche T08).

Couvre (ARCHITECTURE.md §5 et §6) :
    - chargement du jeu de démo sans aucun problème de gravité « erreur » ;
    - décalage des dates de la démo (semaines entières) ;
    - formats de nouvelId (séquentiel, annuel, horodaté) ;
    - modifier : conflit simulé (rechargement + réapplication), 3 conflits de suite,
      ErreurValidation jamais réessayée, journal (création, modification, action) ;
    - ajouter (journal) et repli sur modifier ;
    - problemes() : référence cassée, code de la mauvaise famille ou inconnu, doublon,
      identifiant manquant, notation scientifique d'Excel, incohérences DI/OT ;
    - stockArticle (inventaire) ; rafraichir et surveillance ; instantane ;
    - contrat de l'adaptateur StockageDemo (versions, conflits, ajout, documents) ;
    - performance : 500 équipements et 5 000 OT chargés en moins de 1 s, modifier en moins de 300 ms.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_donnees.py" -v
"""
import base64
import csv
import io
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from commun import DOSSIER_DEMO, RACINE, CasNavigateur, charger_scripts, scenarios_demo

# Identifiants des objets de scénario du jeu de démo (outils/generer_demo.py, ARCHITECTURE.md §14.8).
SCENARIOS = scenarios_demo()


def lignes_demo(table):
    """Lignes d'un CSV du jeu de démo (donnees/demo), apostrophe de protection retirée."""
    texte = (DOSSIER_DEMO / (table + ".csv")).read_bytes().decode("utf-8-sig")
    return [{cle: (valeur[1:] if valeur.startswith("'") else valeur) for cle, valeur in ligne.items()}
            for ligne in csv.DictReader(io.StringIO(texte, newline=""), delimiter=";")]


def ligne_demo(table, identifiant):
    return next(ligne for ligne in lignes_demo(table) if ligne["id"] == identifiant)


# Identifiants du journal livré avec la démo (lot 3, ARCHITECTURE.md §15.12 : historique des statuts des
# pannes récentes). Les tests du journal vérifient que leurs entrées s'ajoutent APRÈS celles-ci, sans en
# perdre aucune.
JOURNAL_DEMO = [ligne["id"] for ligne in lignes_demo("journal")]


def numero_annuel_suivant(table, prefixe, annee, rang=1):
    """Identifiant annuel de la rang-ième ligne créée dans le jeu de démo pour cette année."""
    debut = "%s-%d-" % (prefixe, annee)
    numeros = [int(ligne["id"][len(debut):]) for ligne in lignes_demo(table) if ligne["id"].startswith(debut)]
    return "%s%04d" % (debut, max(numeros, default=0) + rang)


def plus_14_jours(date_heure):
    """Date-heure « AAAA-MM-JJ HH:MM » décalée de deux semaines (décalage de la démo)."""
    return (datetime.strptime(date_heure, "%Y-%m-%d %H:%M") + timedelta(days=14)).strftime("%Y-%m-%d %H:%M")

SCRIPTS = [
    "js/lib/papaparse.min.js",
    "js/schema.js",
    "js/donnees.js",
    "js/stockage-demo.js",
    "js/demo-donnees.js",
]

# Petites fonctions installées dans la page pour les tests.
AIDE_JS = """
window.versOctets = (texteBase64) => Uint8Array.from(atob(texteBase64), (c) => c.charCodeAt(0));
window.texteDe = (octets) => new TextDecoder('utf-8', { ignoreBOM: true }).decode(octets);   // garde le BOM
// Démarre Donnees sur un adaptateur ; mémorise les événements « changement » reçus.
window.demarrer = async (adaptateur) => {
  window.evenementsRecus = [];
  Donnees.initialiser(adaptateur, { poste: 'Poste test', profil: 'Responsable test' });
  Donnees.evenements.addEventListener('changement', (e) => window.evenementsRecus.push(e.detail));
  return Donnees.chargerTout();
};
// Réécrit une table « depuis un autre poste » directement sur l'adaptateur.
window.ecrireAilleurs = async (adaptateur, table, transformer) => {
  const actuel = await adaptateur.charger(table);
  const lu = Donnees.csv.analyser(table, actuel.octets);
  transformer(lu.lignes);
  return adaptateur.enregistrer(table, Donnees.csv.serialiser(table, lu.lignes, lu.colonnesInconnues), actuel.version);
};
'aides installées';
"""

MESSAGE_CONFLIT_DEMANDES = ("Le fichier demandes est modifié en même temps sur un autre poste. "
                            "Réessayez dans un instant.")


class CasDonnees(CasNavigateur):
    """Page vide (file://) avec papaparse, schema, donnees, stockage-demo et le jeu de démo."""

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate(AIDE_JS)

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)


# ---------------------------------------------------------------------------
# Chargement et décalage du jeu de démo
# ---------------------------------------------------------------------------

class TestChargementDemo(CasDonnees):

    def test_chargement_demo_sans_erreur(self):
        resultat = self.js("""async (ids) => {
          const adaptateur = StockageDemo.creer(DEMO_DONNEES.tables,
            { dateReference: DEMO_DONNEES.dateReference, aujourdhui: DEMO_DONNEES.dateReference });
          const charge = await demarrer(adaptateur);
          const problemes = Donnees.problemes();
          return {
            tablesAbsentes: charge.tablesAbsentes,
            baseVide: Donnees.baseVide(),
            erreurs: problemes.filter((p) => p.gravite === 'erreur').map((p) => p.message),
            attentions: problemes.filter((p) => p.gravite === 'attention').map((p) => p.message),
            nombreEquipements: Donnees.lignes('equipements').length,
            po02: Donnees.trouver('equipements', 'EQ-0005').repere,
            ae03: Donnees.trouver('equipements', 'EQ-0012').habilitation_requise,
            stockKit: Donnees.stockArticle(ids.kit),
            diNouvelles: Donnees.lignes('demandes').filter((d) => d.statut === 'Nouvelle').map((d) => d.id),
            otSuivant: Donnees.nouvelId('ordres_travail', undefined, '2026-10-19'),
            rafraichissement: Donnees.parametre('rafraichissement_s', 'aucun'),
            parametreAbsent: Donnees.parametre('cle_qui_n_existe_pas', 'défaut'),
            versionEquipements: Donnees.version('equipements'),
            inconnu: Donnees.trouver('equipements', 'EQ-9999') === undefined,
          };
        }""", {"kit": SCENARIOS["kit_garniture"]})
        for message in resultat["attentions"]:
            print("  [attention] " + message)
        self.assertEqual(resultat["erreurs"], [], "le jeu de démo ne doit contenir aucune erreur")
        self.assertEqual(resultat["tablesAbsentes"], [])
        self.assertFalse(resultat["baseVide"])
        self.assertGreater(resultat["nombreEquipements"], 30)
        self.assertEqual(resultat["po02"], "PO-02")
        self.assertIn("BR", resultat["ae03"])
        self.assertEqual(resultat["stockKit"], float(ligne_demo("articles", SCENARIOS["kit_garniture"])["stock"]))
        self.assertGreaterEqual(resultat["stockKit"], 2)
        self.assertEqual(resultat["diNouvelles"], SCENARIOS["di_nouvelles"])
        self.assertEqual(resultat["otSuivant"], numero_annuel_suivant("ordres_travail", "OT", 2026))
        self.assertEqual(resultat["rafraichissement"], "20")
        self.assertEqual(resultat["parametreAbsent"], "défaut")
        self.assertEqual(resultat["versionEquipements"], "v1")
        self.assertTrue(resultat["inconnu"])

    def test_base_vide(self):
        resultat = self.js("""async () => {
          const charge = await demarrer(StockageDemo.creer({}));
          return { absentes: charge.tablesAbsentes.length, baseVide: Donnees.baseVide(),
                   lignes: Donnees.lignes('equipements').length, problemes: Donnees.problemes().length };
        }""")
        self.assertEqual(resultat, {"absentes": 22, "baseVide": True, "lignes": 0, "problemes": 0})

    def test_decalage_des_dates(self):
        di = ligne_demo("demandes", SCENARIOS["di_plus_ancienne"])       # première ligne du fichier
        resultat = self.js("""async (diId) => {
          const reference = DEMO_DONNEES.dateReference;           // 2026-10-19
          const decalees = StockageDemo.decalerDates(DEMO_DONNEES.tables, reference, '2026-11-03');
          const lire = (table) => Donnees.csv.analyser(table, decalees[table]).lignes;
          const sixJours = StockageDemo.decalerDates({ demandes: DEMO_DONNEES.tables.demandes }, reference, '2026-10-25');
          await demarrer(StockageDemo.creer(DEMO_DONNEES.tables, { dateReference: reference, aujourdhui: '2026-11-03' }));
          return {
            di: lire('demandes').find((d) => d.id === diId),
            eq: lire('equipements').find((e) => e.id === 'EQ-0001').date_mes,
            hab: lire('habilitations').find((h) => h.id === 'HAB-0001'),
            sixJours: Donnees.csv.analyser('demandes', sixJours.demandes).lignes[0].date_heure,
            parCreer: Donnees.trouver('demandes', diId).date_heure,
            erreurs: Donnees.problemes().filter((p) => p.gravite === 'erreur').length,
          };
        }""", di["id"])
        self.assertTrue(di["date_decision"])
        self.assertEqual(resultat["di"]["date_heure"], plus_14_jours(di["date_heure"]))
        self.assertEqual(resultat["di"]["date_decision"], plus_14_jours(di["date_decision"]))
        self.assertEqual(resultat["di"]["id"], di["id"])                       # l'identifiant garde son année
        self.assertEqual(resultat["eq"], "2019-03-26")                         # 2019-03-12 + 14 j
        self.assertEqual(resultat["hab"]["date_obtention"], "2025-03-24")
        self.assertEqual(resultat["hab"]["date_echeance"], "2028-03-24")
        self.assertEqual(resultat["sixJours"], di["date_heure"])                # moins d'une semaine : rien
        self.assertEqual(resultat["parCreer"], plus_14_jours(di["date_heure"]))
        self.assertEqual(resultat["erreurs"], 0)


# ---------------------------------------------------------------------------
# Identifiants
# ---------------------------------------------------------------------------

class TestIdentifiants(CasDonnees):

    def test_formats_nouvel_id(self):
        resultat = self.js("""() => {
          const ids = (liste) => liste.map((id) => ({ id: id }));
          let tableSansIdentifiant = '';
          try { Donnees.nouvelId('parametres', []); } catch (e) { tableSansIdentifiant = e.message; }
          const annee = String(new Date().getFullYear());
          return {
            sequentiel: Donnees.nouvelId('equipements', ids(['EQ-0009', 'EQ-0010', 'autre', 'EQ-12a'])),
            premier: Donnees.nouvelId('equipements', []),
            sixChiffres: Donnees.nouvelId('mouvements_stock', ids(['MVT-000041'])),
            cinqChiffres: Donnees.nouvelId('article_equipement', []),
            annuel: Donnees.nouvelId('demandes', ids(['DI-2026-0073', 'DI-2025-0100']), '2026-10-19'),
            annuelHeure: Donnees.nouvelId('demandes', ids(['DI-2026-0073']), '2026-10-19 08:30'),
            nouvelleAnnee: Donnees.nouvelId('demandes', ids(['DI-2026-0073']), '2027-01-02'),
            sansDate: Donnees.nouvelId('ordres_travail', []),
            anneeCourante: annee,
            journal: Donnees.nouvelId('journal', []),
            tableSansIdentifiant: tableSansIdentifiant,
          };
        }""")
        self.assertEqual(resultat["sequentiel"], "EQ-0011")
        self.assertEqual(resultat["premier"], "EQ-0001")
        self.assertEqual(resultat["sixChiffres"], "MVT-000042")
        self.assertEqual(resultat["cinqChiffres"], "AEQ-00001")
        self.assertEqual(resultat["annuel"], "DI-2026-0074")
        self.assertEqual(resultat["annuelHeure"], "DI-2026-0074")
        self.assertEqual(resultat["nouvelleAnnee"], "DI-2027-0001")
        self.assertEqual(resultat["sansDate"], "OT-" + resultat["anneeCourante"] + "-0001")
        self.assertRegex(resultat["journal"], r"^J-\d{14}-[A-Z0-9]{4}$")
        self.assertIn("parametres", resultat["tableSansIdentifiant"])


# ---------------------------------------------------------------------------
# modifier : conflits, validation, journal
# ---------------------------------------------------------------------------

class TestModifier(CasDonnees):

    def test_conflit_simule(self):
        """Un autre poste écrit sa DI juste avant nous : rechargement, nouvel identifiant, 2 DI."""
        resultat = self.js("""async () => {
          const base = StockageDemo.creer(DEMO_DONNEES.tables);
          let premiereEcriture = true;
          const enveloppe = Object.assign({}, base, {
            enregistrer: async (table, octets, versionAttendue) => {
              if (table === 'demandes' && premiereEcriture) {
                premiereEcriture = false;
                await ecrireAilleurs(base, 'demandes', (lignes) => {
                  lignes.push({ id: Donnees.nouvelId('demandes', lignes, '2026-10-19'),
                    date_heure: '2026-10-19 10:00', demandeur: 'Autre poste', equipement_id: 'EQ-0001',
                    symptome: 'Fuite d\\'huile', impact: 'gêne', statut: 'Nouvelle' });
                });
              }
              return base.enregistrer(table, octets, versionAttendue);
            },
          });
          await demarrer(enveloppe);
          let appels = 0;
          const idCree = await Donnees.modifier('demandes', (lignes, outils) => {
            appels += 1;
            const id = outils.nouvelId(lignes, '2026-10-19');
            lignes.push({ id: id, date_heure: outils.maintenant(), demandeur: 'Ce poste',
              equipement_id: 'EQ-0002', symptome: 'Bruit', impact: 'gêne' });
            return id;
          }, { action: 'nouvelle demande' });
          const relu = Donnees.csv.analyser('demandes', (await base.charger('demandes')).octets).lignes;
          return {
            idCree: idCree, appels: appels,
            autre: relu.filter((d) => d.demandeur === 'Autre poste').map((d) => d.id),
            notre: relu.filter((d) => d.demandeur === 'Ce poste').map((d) => d.id),
            enCache: Donnees.trouver('demandes', idCree),
            statutParDefaut: Donnees.trouver('demandes', idCree).statut,
            statistiques: Object.assign({}, Donnees.statistiques),
            evenements: evenementsRecus,
          };
        }""")
        self.assertEqual(resultat["statistiques"]["conflits"], 1)
        self.assertEqual(resultat["statistiques"]["essais"], 2)
        self.assertEqual(resultat["appels"], 2)
        self.assertEqual(len(resultat["autre"]), 1)
        self.assertEqual(resultat["notre"], [resultat["idCree"]])
        self.assertNotEqual(resultat["autre"][0], resultat["idCree"])
        self.assertEqual(resultat["autre"][0], numero_annuel_suivant("demandes", "DI", 2026, 1))
        self.assertEqual(resultat["idCree"], numero_annuel_suivant("demandes", "DI", 2026, 2))
        self.assertIsNotNone(resultat["enCache"])
        self.assertEqual(resultat["statutParDefaut"], "Nouvelle")           # défaut du schéma
        self.assertEqual(resultat["evenements"], [{"tables": ["demandes"], "origine": "local"}])

    def test_trois_conflits_de_suite(self):
        resultat = self.js("""async () => {
          const base = StockageDemo.creer(DEMO_DONNEES.tables);
          let chargements = 0;
          const enveloppe = Object.assign({}, base, {
            charger: async (table) => { if (table === 'demandes') { chargements += 1; } return base.charger(table); },
            enregistrer: async (table) => { throw new Donnees.ErreurConflit('conflit simulé', 'v9'); },
          });
          await demarrer(enveloppe);
          let appels = 0;
          let erreur = null;
          try {
            await Donnees.modifier('demandes', (lignes, outils) => {
              appels += 1;
              lignes.push({ id: outils.nouvelId(lignes, '2026-10-19'), equipement_id: 'EQ-0001' });
            });
          } catch (e) { erreur = e; }
          return {
            nom: erreur && erreur.name, message: erreur && erreur.message,
            estConflit: erreur instanceof Donnees.ErreurConflit,
            appels: appels, rechargements: chargements - 1,
            statistiques: Object.assign({}, Donnees.statistiques),
            evenements: evenementsRecus.length,
          };
        }""")
        self.assertTrue(resultat["estConflit"])
        self.assertEqual(resultat["message"], MESSAGE_CONFLIT_DEMANDES)
        self.assertEqual(resultat["appels"], 3)
        self.assertEqual(resultat["rechargements"], 2)
        self.assertEqual(resultat["statistiques"], {"conflits": 3, "essais": 3})
        self.assertEqual(resultat["evenements"], 0)

    def test_erreur_validation_jamais_reessayee(self):
        resultat = self.js("""async () => {
          const adaptateur = StockageDemo.creer(DEMO_DONNEES.tables);
          await demarrer(adaptateur);
          let appels = 0;
          let erreur = null;
          try {
            await Donnees.modifier('demandes', () => {
              appels += 1;
              throw new Donnees.ErreurValidation('Demande déjà traitée sur un autre poste.');
            });
          } catch (e) { erreur = e; }
          return { nom: erreur.name, message: erreur.message, appels: appels,
                   estValidation: erreur instanceof Donnees.ErreurValidation,
                   statistiques: Object.assign({}, Donnees.statistiques),
                   version: (await adaptateur.listerVersions()).demandes };
        }""")
        self.assertTrue(resultat["estValidation"])
        self.assertEqual(resultat["message"], "Demande déjà traitée sur un autre poste.")
        self.assertEqual(resultat["appels"], 1)
        self.assertEqual(resultat["statistiques"], {"conflits": 0, "essais": 1})
        self.assertEqual(resultat["version"], "v1")

    def test_journal_apres_modifier(self):
        ot_id = SCENARIOS["ot_de_di_acceptee"]
        resultat = self.js("""async (otId) => {
          const adaptateur = StockageDemo.creer(DEMO_DONNEES.tables);
          await demarrer(adaptateur);
          const nouveau = await Donnees.modifier('equipements', (lignes, outils) => {
            const id = outils.nouvelId(lignes);
            lignes.push({ id: id, repere: 'NV-01', designation: 'Nouvelle machine' });
            const eq1 = lignes.find((l) => l.id === 'EQ-0001');
            eq1.designation = 'Compresseur renommé';
            eq1.marque = 'Autre marque';
            return id;
          }, { action: 'essai du journal' });
          const sansChangement = await Donnees.modifier('equipements', () => 'rien');
          await Donnees.modifier('equipements', (lignes) => {
            lignes.find((l) => l.id === 'EQ-0002').marque = 'Sans journal';
          }, { journal: false });
          const idAvertissement = await Donnees.journaliser('ordres_travail', otId,
            'avertissement habilitation : TEC-0004 sans BR valide au 2026-10-21');
          const avantRelecture = Donnees.lignes('journal').length;
          await Donnees.rechargerTable('journal');
          return {
            nouveau: nouveau, sansChangement: sansChangement, idAvertissement: idAvertissement,
            avantRelecture: avantRelecture,
            journal: Donnees.lignes('journal'),
            versions: await adaptateur.listerVersions(),
            evenements: evenementsRecus,
          };
        }""", ot_id)
        # Le journal livré avec la démo est conservé tel quel ; nos entrées viennent après.
        self.assertGreater(len(JOURNAL_DEMO), 0)
        self.assertEqual([e["id"] for e in resultat["journal"][:len(JOURNAL_DEMO)]], JOURNAL_DEMO)
        journal = resultat["journal"][len(JOURNAL_DEMO):]
        # Nos propres entrées sont ajoutées au cache (la table reste périmée pour modifier).
        self.assertEqual(resultat["avantRelecture"], len(JOURNAL_DEMO) + 3)
        self.assertEqual(len(journal), 3)
        # Une entrée par ligne, dans l'ordre des lignes de la table (EQ-0001 avant la ligne ajoutée).
        modification, creation, avertissement = journal
        self.assertEqual(creation["table"], "equipements")
        self.assertEqual(creation["id_ligne"], resultat["nouveau"])
        self.assertEqual(creation["action"], "création — essai du journal")
        self.assertEqual(modification["id_ligne"], "EQ-0001")
        self.assertEqual(modification["action"], "modification : designation, marque — essai du journal")
        for entree in journal:
            self.assertRegex(entree["id"], r"^J-\d{14}-[A-Z0-9]{4}$")
            self.assertRegex(entree["date_heure"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
            self.assertEqual(entree["poste"], "Poste test")
            self.assertEqual(entree["profil"], "Responsable test")
        self.assertEqual(len({e["id"] for e in journal}), 3)
        self.assertEqual(avertissement["id"], resultat["idAvertissement"])
        self.assertEqual(avertissement["table"], "ordres_travail")
        self.assertEqual(avertissement["id_ligne"], ot_id)
        self.assertIn("avertissement habilitation", avertissement["action"])
        self.assertEqual(resultat["sansChangement"], "rien")
        self.assertEqual(resultat["versions"]["equipements"], "v3")   # la modification vide n'écrit rien
        self.assertEqual(resultat["evenements"], [{"tables": ["equipements"], "origine": "local"}] * 2)

    def test_echec_du_journal_sans_echec_de_la_modification(self):
        resultat = self.js("""async () => {
          const base = StockageDemo.creer(DEMO_DONNEES.tables);
          const refus = async () => { throw new Donnees.ErreurStockage('journal.csv est ouvert dans Excel.'); };
          const enveloppe = Object.assign({}, base, {
            ajouter: refus,
            enregistrer: (table, octets, version) => table === 'journal' ? refus() : base.enregistrer(table, octets, version),
          });
          await demarrer(enveloppe);
          const avertissements = [];
          const warnOrigine = console.warn;
          console.warn = (...morceaux) => avertissements.push(morceaux.map(String).join(' '));
          let valeur;
          let idJournal;
          try {
            valeur = await Donnees.modifier('equipements', (lignes) => {
              lignes.find((l) => l.id === 'EQ-0001').designation = 'Modifiée malgré tout';
              return 'ok';
            });
            idJournal = await Donnees.journaliser('equipements', 'EQ-0001', 'essai');
          } finally {
            console.warn = warnOrigine;
          }
          return { valeur: valeur, idJournal: idJournal, avertissements: avertissements,
                   designation: Donnees.trouver('equipements', 'EQ-0001').designation };
        }""")
        self.assertEqual(resultat["valeur"], "ok")
        self.assertIsNone(resultat["idJournal"])
        self.assertEqual(resultat["designation"], "Modifiée malgré tout")
        self.assertEqual(len(resultat["avertissements"]), 2)
        self.assertIn("journal", resultat["avertissements"][0])


# ---------------------------------------------------------------------------
# ajouter (journal) et repli
# ---------------------------------------------------------------------------

class TestAjouter(CasDonnees):

    ENTREE = """(id) => ({ id: id, date_heure: '2026-10-19 10:00', poste: 'P1', profil: 'Test',
                          table: 'equipements', id_ligne: 'EQ-0001', action: 'essai' })"""

    def test_ajouter_direct(self):
        resultat = self.js("""async () => {
          const entree = (""" + self.ENTREE + """);
          const adaptateur = StockageDemo.creer(DEMO_DONNEES.tables);
          await demarrer(adaptateur);
          const reponse = await Donnees.ajouter('journal', [entree('J-20261019100000-AAAA'), entree('J-20261019100000-BBBB')]);
          const texte = texteDe((await adaptateur.charger('journal')).octets);
          const avant = Donnees.lignes('journal').length;
          const relues = await Donnees.rafraichir();
          return { reponse: reponse, texte: texte, avant: avant, relues: relues,
                   apres: Donnees.lignes('journal').map((l) => l.id), evenements: evenementsRecus.length };
        }""")
        self.assertEqual(resultat["reponse"], {"repli": False})
        self.assertTrue(resultat["texte"].startswith("﻿id;date_heure;poste;profil;table;id_ligne;action\r\n"))
        self.assertEqual(resultat["texte"].count("﻿"), 1)
        self.assertIn("J-20261019100000-AAAA;2026-10-19 10:00;P1;Test;equipements;EQ-0001;essai\r\n", resultat["texte"])
        self.assertEqual(resultat["avant"], len(JOURNAL_DEMO) + 2, "nos propres lignes sont dans le cache")
        self.assertEqual(resultat["relues"], ["journal"], "rafraichir() explicite relit la table périmée")
        self.assertEqual(resultat["apres"], JOURNAL_DEMO + ["J-20261019100000-AAAA", "J-20261019100000-BBBB"])
        self.assertEqual(resultat["evenements"], 0, "un changement du seul journal n'est pas signalé")

    def test_ajouter_avec_repli(self):
        """Le journal a été réenregistré (colonne ajoutée) : l'ajout est refusé → repli sur modifier."""
        resultat = self.js("""async () => {
          const entree = (""" + self.ENTREE + """);
          const adaptateur = StockageDemo.creer(DEMO_DONNEES.tables);
          await demarrer(adaptateur);
          const enteteExcel = 'id;date_heure;poste;profil;table;id_ligne;action;remarque\\r\\n'
            + 'J-20261001080000-XXXX;2026-10-01 08:00;P0;Test;equipements;EQ-0002;ancienne;notée à la main\\r\\n';
          await adaptateur.enregistrer('journal', new TextEncoder().encode(enteteExcel), 'v1');
          const premier = await Donnees.ajouter('journal', [entree('J-20261019100000-CCCC')]);
          const conflits = Donnees.statistiques.conflits;
          const second = await Donnees.ajouter('journal', [entree('J-20261019100001-DDDD')]);
          await Donnees.rafraichir();
          return { premier: premier, second: second, conflits: conflits,
                   ids: Donnees.lignes('journal').map((l) => l.id),
                   remarque: Donnees.trouver('journal', 'J-20261001080000-XXXX').remarque };
        }""")
        self.assertEqual(resultat["premier"], {"repli": True})
        self.assertEqual(resultat["conflits"], 1, "cache du journal périmé : un conflit puis relecture")
        self.assertEqual(resultat["second"], {"repli": False}, "en-tête relu avec la colonne inconnue")
        self.assertEqual(resultat["ids"], ["J-20261001080000-XXXX", "J-20261019100000-CCCC", "J-20261019100001-DDDD"])
        self.assertEqual(resultat["remarque"], "notée à la main")

    # Adaptateur de démo espionné : compte les lectures complètes du journal et les listerVersions.
    # window.avantAjout (facultatif) : appelé avant chaque adaptateur.ajouter (« autre poste »).
    ESPION = """(adaptateur) => {
      window.compteurs = { lecturesJournal: 0, versions: 0 };
      const vraiCharger = adaptateur.charger;
      const vraiAjouter = adaptateur.ajouter;
      const vraiListerVersions = adaptateur.listerVersions;
      adaptateur.charger = async (table) => {
        if (table === 'journal') { compteurs.lecturesJournal += 1; }
        return vraiCharger(table);
      };
      adaptateur.listerVersions = async () => { compteurs.versions += 1; return vraiListerVersions(); };
      adaptateur.ajouter = async (table, octets) => {
        if (window.avantAjout) { const f = window.avantAjout; window.avantAjout = null; await f(); }
        return vraiAjouter(table, octets);
      };
      adaptateur.ajouterAutrePoste = (identifiant) => vraiAjouter('journal', new TextEncoder().encode(
        'id;date_heure;poste;profil;table;id_ligne;action\\r\\n' + identifiant
        + ';2026-10-19 09:00;Autre poste;P;equipements;EQ-0002;ailleurs\\r\\n'));
      return adaptateur;
    }"""

    # Laisse tourner la surveillance (période 20 ms) jusqu'à `n` listerVersions de plus.
    ATTENDRE_TOURS = """async (n) => {
      const cible = compteurs.versions + n;
      const debut = Date.now();
      while (compteurs.versions < cible && Date.now() - debut < 3000) {
        await new Promise((r) => setTimeout(r, 10));
      }
      await new Promise((r) => setTimeout(r, 30));      // le dernier rafraîchissement se termine
      return compteurs.versions >= cible;
    }"""

    def demarrer_espionne(self):
        self.js("""async (espion) => {
          window.adaptateur = (eval(espion))(StockageDemo.creer(DEMO_DONNEES.tables));
          await demarrer(window.adaptateur);
        }""", self.ESPION)

    def tours_de_surveillance(self, n=3):
        self.js("() => Donnees.demarrerSurveillance(20)")
        self.assertTrue(self.js(self.ATTENDRE_TOURS, n), "la surveillance n'a pas tourné")
        self.js("() => Donnees.arreterSurveillance()")

    def ids_journal_stockage(self):
        return self.js("""async () => Donnees.csv.analyser('journal',
          (await adaptateur.charger('journal')).octets).lignes.map((l) => l.id)""")

    def test_ajout_puis_surveillance_sans_relire_le_journal(self):
        """(a) Après notre propre ajout, si rien d'autre n'a changé, le journal n'est pas relu."""
        self.demarrer_espionne()
        identifiant = self.js("() => Donnees.journaliser('equipements', 'EQ-0001', 'essai')")
        self.assertIsNotNone(identifiant)
        self.js("() => { compteurs.lecturesJournal = 0; }")
        self.tours_de_surveillance(3)
        self.assertEqual(self.js("() => compteurs.lecturesJournal"), 0,
                         "journal relu en entier alors que seul notre ajout l'a changé")
        self.assertEqual(self.js("() => evenementsRecus"), [], "notre propre ajout au journal n'est pas signalé")
        # Nos propres lignes sont visibles sans relecture (après celles du journal de la démo).
        self.assertEqual(self.js("() => Donnees.lignes('journal').map((l) => l.id)"), JOURNAL_DEMO + [identifiant])
        # Un rafraîchissement demandé explicitement (ex. avant l'export) relit tout.
        self.assertEqual(self.js("() => Donnees.rafraichir()"), ["journal"])
        self.assertEqual(self.js("() => compteurs.lecturesJournal"), 1)

    def test_ajout_puis_ajout_d_un_autre_poste_relu_par_la_surveillance(self):
        """(b) Un autre poste ajoute après nous : la version diffère, le journal est relu."""
        self.demarrer_espionne()
        identifiant = self.js("() => Donnees.journaliser('equipements', 'EQ-0001', 'essai')")
        self.js("() => adaptateur.ajouterAutrePoste('J-AUTRE')")
        self.js("() => { compteurs.lecturesJournal = 0; }")
        self.tours_de_surveillance(3)
        self.assertEqual(self.js("() => compteurs.lecturesJournal"), 1)
        self.assertEqual(self.js("() => Donnees.lignes('journal').map((l) => l.id)"),
                         JOURNAL_DEMO + [identifiant, "J-AUTRE"])
        # Lot 4 (§17.9) : le journal changé sur un autre poste est signalé (une seule fois).
        self.assertEqual(self.js("() => evenementsRecus"), [{"tables": ["journal"], "origine": "distant"}])

    def test_modifier_journal_apres_ajout_ne_perd_pas_la_ligne_d_un_autre_poste(self):
        """(c) L'autre poste ajoute juste AVANT notre ajout (même version ensuite) : la surveillance
        ne relit pas, mais modifier('journal') relit avant d'écrire et ne perd rien."""
        self.demarrer_espionne()
        self.js("() => { window.avantAjout = () => adaptateur.ajouterAutrePoste('J-AUTRE'); }")
        identifiant = self.js("() => Donnees.journaliser('equipements', 'EQ-0001', 'essai')")
        self.tours_de_surveillance(3)
        self.js("""() => Donnees.modifier('journal', (lignes) => {
          lignes.push(Object.assign({}, lignes[lignes.length - 1], { id: 'J-MANUEL' }));
        }, { journal: false })""")
        self.assertEqual(self.ids_journal_stockage(), JOURNAL_DEMO + ["J-AUTRE", identifiant, "J-MANUEL"])
        self.assertEqual(self.js("() => Donnees.lignes('journal').map((l) => l.id)"),
                         JOURNAL_DEMO + ["J-AUTRE", identifiant, "J-MANUEL"])


# ---------------------------------------------------------------------------
# problemes()
# ---------------------------------------------------------------------------

class TestProblemes(CasDonnees):

    def test_problemes_detectes(self):
        # di1 : DI acceptée dont l'OT est ot1 ; di2 : une autre DI acceptée ; ot2 : un OT préventif clôturé.
        ids = {"di1": SCENARIOS["di_statut_acceptee"], "ot1": SCENARIOS["ot_de_di_acceptee"],
               "di2": SCENARIOS["di_acceptee_autre"], "ot2": SCENARIOS["ot_preventif_cloture"]}
        resultat = self.js("""async (ids) => {
          const tables = Object.assign({}, DEMO_DONNEES.tables);
          const retoucher = (table, transformer) => {
            const lu = Donnees.csv.analyser(table, tables[table]);
            transformer(lu.lignes);
            tables[table] = texteDe(Donnees.csv.serialiser(table, lu.lignes, lu.colonnesInconnues));
          };
          let diAcceptees;
          retoucher('demandes', (lignes) => {
            const di1 = lignes.find((d) => d.id === ids.di1);
            di1.statut = 'Nouvelle'; di1.ot_id = '';                 // ot1 vient d'une DI non acceptée
            lignes.find((d) => d.id === ids.di2).ot_id = '';         // acceptée sans OT
            diAcceptees = lignes.filter((d) => d.statut === 'Acceptée' && d.ot_id !== '');
            diAcceptees[0].ot_id = 'OT-2026-9999';                   // acceptée avec un OT inconnu
          });
          retoucher('ordres_travail', (lignes) => {
            const ot1 = lignes.find((o) => o.id === ids.ot1);
            ot1.equipement_id = 'EQ-9999';                           // référence cassée
            ot1.cause_code = 'S01';                                  // code d'une autre famille
            const ot2 = lignes.find((o) => o.id === ids.ot2);
            ot2.cause_code = 'C42';                                  // code inconnu
            lignes.push(Object.assign({}, ot2));                     // doublon
            lignes.push(Object.assign({}, ot2, { id: '' }));         // identifiant manquant
          });
          // Numéro de série abîmé par Excel (notation scientifique), écrit tel quel dans le fichier.
          tables.equipements = tables.equipements.replace("'AV30-2019-04571", '1,23457E+14');

          await demarrer(StockageDemo.creer(tables));
          const premiers = Donnees.problemes();
          const memeTableau = Donnees.problemes() === premiers;
          await Donnees.modifier('ordres_travail', (lignes) => {
            lignes.find((o) => o.id === ids.ot1).equipement_id = 'EQ-0001';
          });
          const apres = Donnees.problemes();
          const resume = (p) => ({ gravite: p.gravite, type: p.type, table: p.table, id: p.id,
                                   champ: p.champ, valeur: p.valeur, message: p.message });
          return { premiers: premiers.map(resume), memeTableau: memeTableau,
                   recalcule: apres !== premiers, apres: apres.map(resume),
                   diInconnu: diAcceptees[0].id };
        }""", ids)
        problemes = resultat["premiers"]

        def trouver(type_probleme, **criteres):
            return [p for p in problemes if p["type"] == type_probleme
                    and all(p[cle] == valeur for cle, valeur in criteres.items())]

        reference = trouver("reference", table="ordres_travail", id=ids["ot1"], champ="equipement_id")
        self.assertEqual(len(reference), 1)
        self.assertEqual(reference[0]["gravite"], "erreur")
        self.assertEqual(reference[0]["valeur"], "EQ-9999")

        mauvaise_famille = trouver("reference", id=ids["ot1"], champ="cause_code")
        self.assertEqual(len(mauvaise_famille), 1)
        self.assertIn("symptôme", mauvaise_famille[0]["message"])
        self.assertIn("cause", mauvaise_famille[0]["message"])

        inconnu = trouver("reference", id=ids["ot2"], champ="cause_code", valeur="C42")
        self.assertEqual(len(inconnu), 2, "la ligne et son doublon")

        doublon = trouver("doublon", table="ordres_travail", id=ids["ot2"])
        self.assertEqual(len(doublon), 1)
        self.assertEqual(doublon[0]["gravite"], "erreur")

        sans_identifiant = trouver("identifiant", table="ordres_travail")
        self.assertEqual(len(sans_identifiant), 1)
        self.assertIsNone(sans_identifiant[0]["id"])

        excel = trouver("excel", table="equipements", id="EQ-0001", champ="num_serie")
        self.assertEqual(len(excel), 1)
        self.assertEqual(excel[0]["valeur"], "1,23457E+14")

        sans_ot = trouver("incoherence", table="demandes", id=ids["di2"])
        self.assertEqual(len(sans_ot), 1)
        self.assertEqual(sans_ot[0]["gravite"], "erreur")
        ot_inconnu = trouver("incoherence", table="demandes", id=resultat["diInconnu"])
        self.assertEqual(len(ot_inconnu), 1)
        self.assertIn("OT-2026-9999", ot_inconnu[0]["message"])
        di_non_acceptee = trouver("incoherence", table="ordres_travail", id=ids["ot1"])
        self.assertEqual(len(di_non_acceptee), 1)
        self.assertEqual(di_non_acceptee[0]["gravite"], "attention")

        # Recalcul paresseux : même tableau tant que rien ne change, nouveau calcul après modifier.
        self.assertTrue(resultat["memeTableau"])
        self.assertTrue(resultat["recalcule"])
        apres = resultat["apres"]
        self.assertFalse([p for p in apres if p["valeur"] == "EQ-9999"])
        self.assertEqual(len([p for p in apres if p["type"] == "excel"]), 1, "valeur toujours abîmée")
        self.assertEqual(len([p for p in apres if p["type"] == "doublon"]), 1)


# ---------------------------------------------------------------------------
# Stock, rafraîchissement, instantané
# ---------------------------------------------------------------------------

MOUVEMENTS = "\r\n".join([
    "id;date;article_id;type;quantite;ot_id;utilisateur;commentaire",
    "MVT-000005;2026-01-05 08:00;ART-0001;retour;0,5;;;",
    "MVT-000001;2026-01-01 08:00;ART-0001;entrée;5;;;",
    "MVT-000003;2026-01-03 08:00;ART-0001;inventaire;10;;;",
    "MVT-000002;2026-01-02 08:00;ART-0001;sortie;2;;;",
    "MVT-000004;2026-01-04 08:00;ART-0001;sortie;1;;;",
    "MVT-000007;2026-01-03 08:00;ART-0002;inventaire;4;;;",
    "MVT-000006;2026-01-03 08:00;ART-0002;entrée;3;;;",
]) + "\r\n"


class TestStockEtRafraichissement(CasDonnees):

    def test_stock_article_avec_inventaire(self):
        resultat = self.js("""async (mouvements) => {
          await demarrer(StockageDemo.creer({ mouvements_stock: mouvements }));
          const avant = { art1: Donnees.stockArticle('ART-0001'), art2: Donnees.stockArticle('ART-0002'),
                          art3: Donnees.stockArticle('ART-0003') };
          await Donnees.modifier('mouvements_stock', (lignes, outils) => {
            lignes.push({ id: outils.nouvelId(lignes), date: '2026-01-06 08:00', article_id: 'ART-0001',
                          type: 'sortie', quantite: '1.5' });
          });
          return { avant: avant, apres: Donnees.stockArticle('ART-0001') };
        }""", MOUVEMENTS)
        self.assertEqual(resultat["avant"], {"art1": 9.5, "art2": 4, "art3": 0})
        self.assertEqual(resultat["apres"], 8)

    def test_rafraichir_apres_ecriture_exterieure(self):
        resultat = self.js("""async () => {
          const adaptateur = StockageDemo.creer(DEMO_DONNEES.tables);
          await demarrer(adaptateur);
          const rien = await Donnees.rafraichir();
          await ecrireAilleurs(adaptateur, 'equipements', (lignes) => {
            lignes.find((l) => l.id === 'EQ-0001').designation = 'Changée sur un autre poste';
          });
          const relues = await Donnees.rafraichir();
          const ensuite = await Donnees.rafraichir();
          return { rien: rien, relues: relues, ensuite: ensuite, evenements: evenementsRecus,
                   designation: Donnees.trouver('equipements', 'EQ-0001').designation,
                   version: Donnees.version('equipements') };
        }""")
        self.assertEqual(resultat["rien"], [])
        self.assertEqual(resultat["relues"], ["equipements"])
        self.assertEqual(resultat["ensuite"], [])
        self.assertEqual(resultat["designation"], "Changée sur un autre poste")
        self.assertEqual(resultat["version"], "v2")
        self.assertEqual(resultat["evenements"], [{"tables": ["equipements"], "origine": "distant"}])

    def test_surveillance(self):
        resultat = self.js("""async () => {
          const adaptateur = StockageDemo.creer(DEMO_DONNEES.tables);
          await demarrer(adaptateur);
          Donnees.demarrerSurveillance(50);
          const recu = new Promise((resoudre) => {
            Donnees.evenements.addEventListener('changement', (e) => resoudre(e.detail), { once: true });
            setTimeout(() => resoudre(null), 3000);
          });
          await ecrireAilleurs(adaptateur, 'techniciens', (lignes) => { lignes[0].metier = 'Automaticien'; });
          const detail = await recu;
          Donnees.arreterSurveillance();
          return { detail: detail, metier: Donnees.lignes('techniciens')[0].metier };
        }""")
        self.assertEqual(resultat["detail"], {"tables": ["techniciens"], "origine": "distant"})
        self.assertEqual(resultat["metier"], "Automaticien")

    def test_instantane(self):
        resultat = self.js("""async () => {
          await demarrer(StockageDemo.creer(DEMO_DONNEES.tables));
          const fichiers = Donnees.instantane();
          const noms = Object.keys(fichiers);
          return {
            noms: noms, attendus: Schema.nomsTables(),
            tousOctets: noms.every((n) => fichiers[n] instanceof Uint8Array),
            avecBom: noms.every((n) => fichiers[n][0] === 0xEF && fichiers[n][1] === 0xBB && fichiers[n][2] === 0xBF),
            memesLignes: noms.every((n) => Donnees.csv.analyser(n, fichiers[n]).lignes.length === Donnees.lignes(n).length),
            identique: texteDe(fichiers.equipements) === texteDe(Donnees.csv.serialiser('equipements', Donnees.lignes('equipements'))),
          };
        }""")
        self.assertEqual(resultat["noms"], resultat["attendus"])
        self.assertEqual(len(resultat["noms"]), 22)
        self.assertTrue(resultat["tousOctets"])
        self.assertTrue(resultat["avecBom"])
        self.assertTrue(resultat["memesLignes"])
        self.assertTrue(resultat["identique"])


# ---------------------------------------------------------------------------
# Adaptateur StockageDemo (contrat §6)
# ---------------------------------------------------------------------------

class TestStockageDemo(CasDonnees):

    def test_contrat_adaptateur(self):
        resultat = self.js("""async () => {
          const a = StockageDemo.creer({ techniciens: 'id;nom\\r\\nTEC-0001;Moreau\\r\\n' });
          const capturer = async (promesse) => {
            try { await promesse; return null; } catch (e) { return { nom: e.name, message: e.message, versionActuelle: e.versionActuelle }; }
          };
          const octets = (texte) => new TextEncoder().encode(texte);
          const lu = await a.charger('techniciens');
          const absent = await a.charger('equipements');
          const ecrit = await a.enregistrer('techniciens', octets('id;nom\\r\\nTEC-0001;Moreau\\r\\nTEC-0002;Benali\\r\\n'), 'v1');
          const conflitVersion = await capturer(a.enregistrer('techniciens', octets('x'), 'v1'));
          const conflitExiste = await capturer(a.enregistrer('techniciens', octets('x'), null));
          const conflitAbsent = await capturer(a.enregistrer('equipements', octets('x'), 'v1'));
          const creation = await a.enregistrer('localisations', octets('id;libelle;parent_id;type\\r\\n'), null);
          const ajoutNouveau = await a.ajouter('journal', octets('id;action\\r\\nJ-1;un\\r\\n'));
          const ajoutSuite = await a.ajouter('journal', octets('id;action\\r\\nJ-2;deux\\r\\n'));
          const conflitEntete = await capturer(a.ajouter('journal', octets('id;autre\\r\\nJ-3;trois\\r\\n')));
          const journal = texteDe((await a.charger('journal')).octets);
          const tableInconnue = await capturer(a.charger('inconnue'));
          const versions = await a.listerVersions();
          const blob = new Blob(['photo'], { type: 'image/jpeg' });
          const nomDocument = await a.ecrireDocument('photo-1.jpg', blob);
          const ecrasement = await capturer(a.ecrireDocument('photo-1.jpg', blob));
          const nomInvalide = await capturer(a.ecrireDocument('../x.jpg', blob));
          const relu = await (await a.lireDocument('photo-1.jpg')).text();
          const url = await a.urlDocument('photo-1.jpg');
          return {
            mode: a.mode, libelle: a.libelle,
            lu: { texte: texteDe(lu.octets), bom: lu.octets[0] === 0xEF, version: lu.version },
            absent: absent, ecrit: ecrit, creation: creation,
            conflitVersion: conflitVersion, conflitExiste: conflitExiste, conflitAbsent: conflitAbsent,
            ajoutNouveau: ajoutNouveau, ajoutSuite: ajoutSuite, conflitEntete: conflitEntete, journal: journal,
            tableInconnue: tableInconnue, nombreVersions: Object.keys(versions).length,
            versionEquipements: versions.equipements, versionTechniciens: versions.techniciens,
            nomDocument: nomDocument, ecrasement: ecrasement, nomInvalide: nomInvalide, relu: relu,
            url: url, memeUrl: url === await a.urlDocument('photo-1.jpg'),
            documentAbsent: await a.lireDocument('absent.jpg'), urlAbsente: await a.urlDocument('absent.jpg'),
            documents: a.documentsEnMemoire().map((d) => d.nom),
            sauvegarder: await capturer(a.sauvegarder()),
            listerSauvegardes: await capturer(a.listerSauvegardes()),
            restaurer: await capturer(a.restaurer('2026-10-19')),
            info: await a.info(),
          };
        }""")
        indisponible = {"nom": "ErreurStockage", "message": "Indisponible en mode démo : rien n'est enregistré.",
                        "versionActuelle": None}
        self.assertEqual(resultat["mode"], "demo")
        self.assertEqual(resultat["libelle"], "Démo — rien n'est enregistré")
        self.assertEqual(resultat["lu"], {"texte": "﻿id;nom\r\nTEC-0001;Moreau\r\n", "bom": True, "version": "v1"})
        self.assertEqual(resultat["absent"], {"octets": None, "version": None})
        self.assertEqual(resultat["ecrit"], {"version": "v2"})
        self.assertEqual(resultat["creation"], {"version": "v1"})
        self.assertEqual(resultat["conflitVersion"]["nom"], "ErreurConflit")
        self.assertEqual(resultat["conflitVersion"]["versionActuelle"], "v2")
        self.assertEqual(resultat["conflitExiste"]["nom"], "ErreurConflit")
        self.assertEqual(resultat["conflitAbsent"]["nom"], "ErreurConflit")
        self.assertIsNone(resultat["conflitAbsent"]["versionActuelle"])
        self.assertEqual(resultat["ajoutNouveau"], {"version": "v1"})
        self.assertEqual(resultat["ajoutSuite"], {"version": "v2"})
        self.assertEqual(resultat["conflitEntete"]["nom"], "ErreurConflit")
        self.assertEqual(resultat["journal"], "﻿id;action\r\nJ-1;un\r\nJ-2;deux\r\n")
        self.assertEqual(resultat["tableInconnue"]["nom"], "ErreurStockage")
        self.assertEqual(resultat["nombreVersions"], 22)
        self.assertIsNone(resultat["versionEquipements"])
        self.assertEqual(resultat["versionTechniciens"], "v2")
        self.assertEqual(resultat["nomDocument"], "photo-1.jpg")
        self.assertEqual(resultat["ecrasement"]["nom"], "ErreurStockage")
        self.assertEqual(resultat["nomInvalide"]["nom"], "ErreurStockage")
        self.assertEqual(resultat["relu"], "photo")
        self.assertTrue(resultat["url"].startswith("blob:"))
        self.assertTrue(resultat["memeUrl"])
        self.assertIsNone(resultat["documentAbsent"])
        self.assertIsNone(resultat["urlAbsente"])
        self.assertEqual(resultat["documents"], ["photo-1.jpg"])
        self.assertEqual(resultat["sauvegarder"], indisponible)
        self.assertEqual(resultat["listerSauvegardes"], indisponible)
        self.assertEqual(resultat["restaurer"], indisponible)
        self.assertEqual(resultat["info"], {})

    def test_depuis_fichiers(self):
        resultat = self.js("""async () => {
          const fichiers = [
            new File([DEMO_DONNEES.tables.equipements], 'Equipements.CSV'),
            new File(['bonjour'], 'notes.txt'),
            new File(['a;b\\r\\n1;2\\r\\n'], 'inconnue.csv'),
            new File(['id;repere\\r\\nEQ-0001;X\\r\\n'], 'equipements.csv'),
          ];
          const depot = await StockageDemo.depuisFichiers(fichiers);
          const charge = await demarrer(depot.adaptateur);
          return { ignores: depot.fichiersIgnores, absentes: charge.tablesAbsentes.length,
                   equipements: Donnees.lignes('equipements').length,
                   attendus: Donnees.csv.analyser('equipements', DEMO_DONNEES.tables.equipements).lignes.length,
                   mode: depot.adaptateur.mode };
        }""")
        self.assertEqual(resultat["ignores"], ["notes.txt", "inconnue.csv", "equipements.csv"])
        self.assertEqual(resultat["absentes"], 21)
        self.assertEqual(resultat["equipements"], resultat["attendus"])
        self.assertEqual(resultat["mode"], "demo")


# ---------------------------------------------------------------------------
# Performance (CS20 : 500 équipements, 5 000 OT)
# ---------------------------------------------------------------------------

class TestPerformance(CasDonnees):

    LIMITE_CHARGEMENT_MS = 1000
    LIMITE_MODIFIER_MS = 300

    def test_performance_gros_volume(self):
        with tempfile.TemporaryDirectory(prefix="prevo-perf-") as dossier:
            processus = subprocess.run(
                [sys.executable, str(RACINE / "outils" / "generer_demo.py"),
                 "--volume", "500,5000", "--sortie", dossier, "--sans-js"],
                cwd=str(RACINE), capture_output=True, timeout=120)
            self.assertEqual(processus.returncode, 0, processus.stderr.decode("utf-8", "replace"))
            fichiers = {chemin.stem: base64.b64encode(chemin.read_bytes()).decode("ascii")
                        for chemin in sorted(Path(dossier).glob("*.csv"))}
        self.assertEqual(len(fichiers), 22)

        resultat = self.js("""async (fichiers) => {
          const tables = {};
          for (const nom of Object.keys(fichiers)) { tables[nom] = versOctets(fichiers[nom]); }
          const adaptateur = StockageDemo.creer(tables);
          Donnees.initialiser(adaptateur, { poste: 'Poste perf', profil: 'Test' });
          const debut = performance.now();
          await Donnees.chargerTout();
          const chargement = performance.now() - debut;
          const debutProblemes = performance.now();
          const problemes = Donnees.problemes();
          const controle = performance.now() - debutProblemes;
          const debutModifier = performance.now();
          const id = await Donnees.modifier('demandes', (lignes, outils) => {
            const nouvelId = outils.nouvelId(lignes, outils.aujourdhui());
            lignes.push({ id: nouvelId, date_heure: outils.maintenant(), demandeur: 'Perf',
                          equipement_id: 'EQ-0001', symptome: 'Essai de charge', impact: 'gêne' });
            return nouvelId;
          }, { action: 'test de performance' });
          const modification = performance.now() - debutModifier;
          return {
            chargement: chargement, controle: controle, modification: modification, id: id,
            equipements: Donnees.lignes('equipements').length,
            ordres: Donnees.lignes('ordres_travail').length,
            demandes: Donnees.lignes('demandes').length,
            erreurs: problemes.filter((p) => p.gravite === 'erreur').length,
          };
        }""", fichiers)
        print("\n  performance : chargerTout %.0f ms, problemes() %.0f ms, modifier('demandes') %.0f ms "
              "(%d équipements, %d OT, %d DI, %d erreurs)"
              % (resultat["chargement"], resultat["controle"], resultat["modification"],
                 resultat["equipements"], resultat["ordres"], resultat["demandes"], resultat["erreurs"]))
        self.assertGreaterEqual(resultat["equipements"], 500)
        self.assertGreaterEqual(resultat["ordres"], 5000)
        self.assertLess(resultat["chargement"], self.LIMITE_CHARGEMENT_MS)
        self.assertLess(resultat["modification"], self.LIMITE_MODIFIER_MS)


if __name__ == "__main__":
    unittest.main()
