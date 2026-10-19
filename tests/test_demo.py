"""Tests du jeu de démo : outils/generer_demo.py, donnees/demo/*.csv et js/demo-donnees.js.

Ce qui est vérifié (docs/ARCHITECTURE.md §3, §4, §11 ; brief §13) :
  - 22 fichiers CSV : BOM, séparateur « ; », fins de ligne CRLF, en-têtes identiques à js/schema.js ;
  - références (clés étrangères) valides, valeurs des listes valides ;
  - volumes du brief §13 et présence des objets des scénarios de recette (PO-02, AE-03, TEC-0001...) ;
  - champs protégés par une apostrophe (§3.2) ;
  - js/demo-donnees.js chargé dans Chromium : 22 tables, texte identique aux CSV ;
  - reproductibilité (deux exécutions = fichiers identiques, et fichiers livrés à jour) ;
  - options --volume 500,5000 (moins de 60 s) et --mois 13.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_demo.py" -v
"""
import csv
import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date, timedelta
from pathlib import Path

from commun import RACINE, CasNavigateur, charger_scripts

SCRIPT_GENERATEUR = RACINE / 'outils' / 'generer_demo.py'
DOSSIER_DEMO = RACINE / 'donnees' / 'demo'
FICHIER_JS = RACINE / 'js' / 'demo-donnees.js'
DATE_REFERENCE = '2026-10-19'
JOUR_REFERENCE = date(2026, 10, 19)

TABLES = [
    'localisations', 'equipements', 'demandes', 'ordres_travail', 'ot_operations', 'ot_pieces',
    'ot_temps', 'gammes', 'gamme_operations', 'articles', 'article_equipement', 'mouvements_stock',
    'techniciens', 'habilitations', 'compteurs', 'releves', 'controles_reglementaires',
    'codes_defaillance', 'fournisseurs', 'achats', 'parametres', 'journal']


# ---------------------------------------------------------------------------
# Outils de lecture
# ---------------------------------------------------------------------------

def charger_generateur():
    """Importe outils/generer_demo.py comme un module (sans l'exécuter)."""
    specification = importlib.util.spec_from_file_location('generer_demo_test', SCRIPT_GENERATEUR)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def lire_csv_octets(octets):
    """(en-têtes, lignes sous forme de dictionnaires) d'un fichier CSV ; les apostrophes de protection sont retirées."""
    texte = octets.decode('utf-8-sig')
    lecteur = csv.reader(io.StringIO(texte, newline=''), delimiter=';')
    lignes = list(lecteur)
    en_tetes = lignes[0]
    return en_tetes, [dict(zip(en_tetes, ligne)) for ligne in lignes[1:]]


def lire_table(dossier, table):
    return lire_csv_octets((dossier / (table + '.csv')).read_bytes())


def retirer_apostrophe(valeur):
    return valeur[1:] if valeur.startswith("'") else valeur


def lignes_propres(dossier, table):
    """Lignes d'une table, valeurs débarrassées de l'apostrophe de protection."""
    _, lignes = lire_table(dossier, table)
    return [{nom: retirer_apostrophe(valeur) for nom, valeur in ligne.items()} for ligne in lignes]


def executer_generateur(*arguments, delai=120):
    """Lance outils/generer_demo.py dans un processus séparé ; retourne (processus, durée en secondes)."""
    debut = time.monotonic()
    processus = subprocess.run([sys.executable, str(SCRIPT_GENERATEUR)] + [str(a) for a in arguments],
                               cwd=str(RACINE), capture_output=True, timeout=delai)
    return processus, time.monotonic() - debut


def jour(texte):
    return date.fromisoformat(texte[:10])


# ---------------------------------------------------------------------------
# Tests sans navigateur : format, contenu, scénarios, reproductibilité
# ---------------------------------------------------------------------------

class TestFichiersCsv(unittest.TestCase):
    """Format des 22 fichiers (§3.1)."""

    def test_22_fichiers_presents(self):
        presents = sorted(p.name for p in DOSSIER_DEMO.glob('*.csv'))
        self.assertEqual(presents, sorted(t + '.csv' for t in TABLES))

    def test_bom_separateur_et_fins_de_ligne_crlf(self):
        for table in TABLES:
            octets = (DOSSIER_DEMO / (table + '.csv')).read_bytes()
            self.assertTrue(octets.startswith(b'\xef\xbb\xbf'), table + ' : BOM absent')
            self.assertFalse(octets.startswith(b'\xef\xbb\xbf\xef\xbb\xbf'), table + ' : double BOM')
            texte = octets.decode('utf-8')[1:]
            self.assertTrue(texte.endswith('\r\n'), table + ' : le fichier doit finir par CRLF')
            entre_guillemets = False
            for position, caractere in enumerate(texte):
                if caractere == '"':
                    entre_guillemets = not entre_guillemets
                elif not entre_guillemets and caractere == '\n':
                    self.assertEqual(texte[position - 1], '\r', '%s : LF sans CR à la position %d' % (table, position))
                elif not entre_guillemets and caractere == '\r':
                    self.assertEqual(texte[position + 1], '\n', '%s : CR isolé à la position %d' % (table, position))
            self.assertFalse(entre_guillemets, table + ' : guillemet jamais refermé')

    def test_journal_en_tete_seul(self):
        _, lignes = lire_table(DOSSIER_DEMO, 'journal')
        self.assertEqual(lignes, [])

    def test_en_tetes_egaux_au_schema_python(self):
        generateur = charger_generateur()
        for table in TABLES:
            en_tetes, _ = lire_table(DOSSIER_DEMO, table)
            self.assertEqual(en_tetes, [c['nom'] for c in generateur.CHAMPS[table]], table)

    def test_nombre_de_colonnes_constant(self):
        for table in TABLES:
            texte = (DOSSIER_DEMO / (table + '.csv')).read_bytes().decode('utf-8-sig')
            lignes = list(csv.reader(io.StringIO(texte, newline=''), delimiter=';'))
            for numero, ligne in enumerate(lignes, 1):
                self.assertEqual(len(ligne), len(lignes[0]), '%s ligne %d' % (table, numero))

    def test_texte_multiligne_correctement_entre_guillemets(self):
        """Les consignations (plusieurs lignes) sont entre guillemets et se relisent sur une seule cellule."""
        _, equipements = lire_table(DOSSIER_DEMO, 'equipements')
        compresseur = [e for e in equipements if retirer_apostrophe(e['repere']) == 'CP-01'][0]
        self.assertIn('\n', compresseur['consignation'])
        self.assertTrue(compresseur['consignation'].startswith('1. '))


class TestProtectionApostrophe(unittest.TestCase):
    """Protection des valeurs que le tableur abîmerait (§3.2)."""

    @classmethod
    def setUpClass(cls):
        cls.generateur = charger_generateur()

    def test_champs_proteges_non_vides_commencent_par_apostrophe(self):
        proteges = 0
        for table in TABLES:
            noms = [c['nom'] for c in self.generateur.CHAMPS[table] if c['protege']]
            _, lignes = lire_table(DOSSIER_DEMO, table)
            for ligne in lignes:
                for nom in noms:
                    if ligne[nom] != '':
                        proteges += 1
                        self.assertTrue(ligne[nom].startswith("'"), '%s.%s = %r' % (table, nom, ligne[nom]))
        self.assertGreater(proteges, 100)

    def test_toute_valeur_a_risque_est_protegee_et_aucune_autre(self):
        generateur = self.generateur
        for table in TABLES:
            champs = generateur.CHAMPS[table]
            _, lignes = lire_table(DOSSIER_DEMO, table)
            for ligne in lignes:
                for champ in champs:
                    brut = ligne[champ['nom']]
                    if champ['type'] not in ('texte', 'texte_long'):
                        self.assertFalse(brut.startswith("'"), '%s.%s' % (table, champ['nom']))
                        continue
                    relu = retirer_apostrophe(brut) if brut.startswith("'") else brut
                    attendu = generateur.a_proteger(champ['type'], champ['protege'], relu)
                    self.assertEqual(brut.startswith("'"), attendu, '%s.%s = %r' % (table, champ['nom'], brut))

    def test_ecrire_puis_relire_redonne_la_valeur(self):
        generateur = self.generateur
        champ = {'type': 'texte', 'protege': False}
        for valeur in ['- remplacer joint', '00123', '123456789012345', '1/2', '2026-10', "'déjà", '12:30', '50 %',
                       '1,5E+3', '=SOMME(A1)', 'texte normal', 'Joint à lèvres 35x52x7', '3.5', '@nom']:
            ecrite = generateur.ecrire_valeur(champ, valeur)
            relue = ecrite[1:] if ecrite.startswith("'") and generateur.a_proteger('texte', False, ecrite[1:]) else ecrite
            self.assertEqual(relue, valeur)

    def test_valeurs_numeriques_en_tete_de_cles(self):
        """Quelques cas typiques de la démo : zéros en tête, 15 chiffres, téléphones."""
        equipements = {retirer_apostrophe(e['repere']): e for e in lire_table(DOSSIER_DEMO, 'equipements')[1]}
        self.assertEqual(equipements['RA-01']['num_serie'], "'00481723")
        self.assertEqual(equipements['RB-01']['num_serie'], "'202409871234567")
        for fournisseur in lire_table(DOSSIER_DEMO, 'fournisseurs')[1]:
            self.assertRegex(fournisseur['telephone'], r"^'0\d{9}$")


class TestContenuDemo(unittest.TestCase):
    """Volumes du brief §13 et objets des scénarios de recette."""

    @classmethod
    def setUpClass(cls):
        cls.t = {table: lignes_propres(DOSSIER_DEMO, table) for table in TABLES}
        cls.equipement = {e['repere']: e for e in cls.t['equipements']}
        cls.equipement_par_id = {e['id']: e for e in cls.t['equipements']}
        cls.ot_par_id = {o['id']: o for o in cls.t['ordres_travail']}
        cls.di_par_id = {d['id']: d for d in cls.t['demandes']}

    def ot_de(self, repere):
        identifiant = self.equipement[repere]['id']
        return [o for o in self.t['ordres_travail'] if o['equipement_id'] == identifiant]

    @staticmethod
    def est_ouvert(ot):
        return ot['statut'] not in ('Clôturé techniquement', 'Clôturé administrativement', 'Annulé')

    # -- volumes (§13)

    def test_volumes_du_brief(self):
        t = self.t
        types = [l['type'] for l in t['localisations']]
        self.assertEqual(types.count('site'), 1)
        self.assertEqual(types.count('atelier'), 3)
        self.assertIn(types.count('ligne'), (2, 3))
        self.assertTrue(28 <= len(t['equipements']) <= 34, len(t['equipements']))
        self.assertEqual(len(t['techniciens']), 4)
        self.assertTrue(45 <= len(t['articles']) <= 55, len(t['articles']))
        self.assertEqual(len(t['gammes']), 10)
        self.assertTrue(4 <= len(t['fournisseurs']) <= 5)
        self.assertGreaterEqual(len(t['controles_reglementaires']), 5)
        self.assertEqual(len(t['compteurs']), 3)
        self.assertGreaterEqual(len(t['releves']), 3 * 6)
        self.assertGreaterEqual(len(t['ordres_travail']), 80)
        self.assertGreaterEqual(len(t['demandes']), 50)
        for gamme in t['gammes']:
            operations = [o for o in t['gamme_operations'] if o['gamme_id'] == gamme['id']]
            self.assertTrue(3 <= len(operations) <= 8, '%s : %d opérations' % (gamme['id'], len(operations)))

    def test_entreprise_et_parametres(self):
        parametres = {p['cle']: p['valeur'] for p in self.t['parametres']}
        self.assertEqual(parametres['entreprise_nom'], 'Atelier des Trois Vallées (démo)')
        for cle, valeur in [('delai_p1_h', '0'), ('delai_p2_h', '24'), ('delai_p3_h', '168'),
                            ('delai_p4', 'prochain arrêt'), ('rafraichissement_s', '20'), ('version_schema', '1')]:
            self.assertEqual(parametres[cle], valeur, cle)
        for cle in ('heures_fonct_defaut', 'tolerance_preventif_pct'):
            self.assertIn(cle, parametres)

    def test_historique_de_6_mois_se_terminant_a_la_date_de_reference(self):
        dates = sorted(o['date_creation'][:10] for o in self.t['ordres_travail'])
        self.assertGreaterEqual(jour(dates[0]), date(2026, 4, 19))
        self.assertLessEqual(jour(dates[0]), date(2026, 5, 3))
        self.assertEqual(dates[-1], DATE_REFERENCE)
        for table, champ in (('ordres_travail', 'date_debut'), ('ordres_travail', 'date_fin'),
                             ('ordres_travail', 'date_cloture_tech'), ('ot_temps', 'date'),
                             ('mouvements_stock', 'date')):
            for ligne in self.t[table]:
                if ligne[champ]:
                    self.assertLessEqual(ligne[champ][:10], DATE_REFERENCE, '%s.%s' % (table, champ))

    # -- équipements

    def test_equipements_cles(self):
        pompe = self.equipement['PO-02']
        self.assertEqual(pompe['designation'], 'Pompe centrifuge eau de refroidissement')
        self.assertEqual(pompe['criticite'], 'B')
        self.assertEqual(self.equipement['CP-01']['criticite'], 'A')
        self.assertEqual(self.equipement['AE-03']['habilitation_requise'], 'BR')
        for repere in ('CV-01', 'CV-02', 'PR-01', 'CN-01', 'CU-01', 'PT-01', 'CH-01', 'GF-01', 'VE-01',
                       'AE-01', 'AE-02', 'AE-03', 'AE-04', 'RA-01'):
            self.assertIn(repere, self.equipement)

    def test_equipements_detail(self):
        sans_heures = [e['repere'] for e in self.t['equipements'] if e['heures_fonct_jour'] == '']
        self.assertEqual(len(sans_heures), 2, sans_heures)
        series = [e['num_serie'] for e in self.t['equipements']]
        self.assertTrue(any(s.startswith('0') and s.isdigit() for s in series), 'un numéro de série à zéros en tête')
        self.assertTrue(any(len(s) == 15 and s.isdigit() for s in series), 'un numéro de série à 15 chiffres')
        self.assertGreaterEqual(len([e for e in self.t['equipements'] if e['parent_id']]), 3)
        for repere in ('CP-01', 'PR-01', 'AE-01', 'PT-01', 'CH-01'):
            self.assertTrue(self.equipement[repere]['consignation'], 'consignation de ' + repere)
        self.assertEqual(len(set(e['repere'] for e in self.t['equipements'])), len(self.t['equipements']))

    # -- techniciens

    def test_techniciens_et_habilitations(self):
        techniciens = {t['id']: t for t in self.t['techniciens']}
        self.assertEqual(sorted(techniciens), ['TEC-0001', 'TEC-0002', 'TEC-0003', 'TEC-0004'])
        for technicien in techniciens.values():
            self.assertTrue(38 <= float(technicien['taux_horaire']) <= 48)
            self.assertEqual(float(technicien['capacite_h_semaine']), 35)
        self.assertEqual(sorted(t['metier'] for t in techniciens.values()),
                         ['Automaticien', 'Mécanicien', 'Polyvalent', 'Électricien'])
        self.assertEqual(techniciens['TEC-0001']['metier'], 'Électricien')

        def habilitations(technicien, intitule):
            return [h for h in self.t['habilitations'] if h['technicien_id'] == technicien and h['intitule'] == intitule]

        br1 = habilitations('TEC-0001', 'BR')
        self.assertEqual(len(br1), 1)
        self.assertLessEqual(br1[0]['date_obtention'], DATE_REFERENCE)
        self.assertGreater(br1[0]['date_echeance'], DATE_REFERENCE)
        br4 = habilitations('TEC-0004', 'BR')
        self.assertEqual(len(br4), 1)
        self.assertLess(br4[0]['date_echeance'], DATE_REFERENCE)
        bientot = [h for h in self.t['habilitations']
                   if h['technicien_id'] != 'TEC-0004'
                   and 0 <= (jour(h['date_echeance']) - JOUR_REFERENCE).days < 60]
        self.assertEqual(len(bientot), 1, bientot)

    # -- articles et stock

    def test_articles_sous_le_point_de_commande(self):
        sous_le_seuil = [a for a in self.t['articles'] if float(a['stock']) <= float(a['point_commande'])]
        self.assertEqual(len(sous_le_seuil), 3, [a['designation'] for a in sous_le_seuil])
        strictement = [a for a in self.t['articles'] if float(a['stock']) < float(a['point_commande'])]
        self.assertEqual(len(strictement), 3)

    def test_kit_garniture_po02(self):
        kits = [a for a in self.t['articles'] if a['designation'] == 'Kit garniture mécanique PO-02']
        self.assertEqual(len(kits), 1)
        self.assertGreaterEqual(float(kits[0]['stock']), 2)
        liens = [l for l in self.t['article_equipement']
                 if l['article_id'] == kits[0]['id'] and l['equipement_id'] == self.equipement['PO-02']['id']]
        self.assertEqual(len(liens), 1)

    def test_colonne_stock_egale_au_stock_recalcule(self):
        stock = {}
        for mouvement in self.t['mouvements_stock']:
            quantite = float(mouvement['quantite'])
            article = mouvement['article_id']
            if mouvement['type'] == 'inventaire':
                stock[article] = quantite
            elif mouvement['type'] in ('entrée', 'retour'):
                stock[article] = stock.get(article, 0) + quantite
            else:
                stock[article] = stock.get(article, 0) - quantite
                self.assertTrue(mouvement['ot_id'], 'sortie non imputée à un OT : ' + mouvement['id'])
            self.assertGreaterEqual(stock[article], 0, 'stock négatif : ' + mouvement['id'])
        for article in self.t['articles']:
            self.assertEqual(float(article['stock']), stock.get(article['id'], 0), article['id'])

    def test_achats_coherents_avec_les_entrees(self):
        statuts = [a['statut'] for a in self.t['achats']]
        self.assertGreaterEqual(statuts.count('reçue'), 3)
        self.assertTrue(1 <= statuts.count('demandée') <= 2)
        self.assertGreaterEqual(statuts.count('commandée'), 1)
        recu, entre = {}, {}
        for achat in self.t['achats']:
            if achat['statut'] == 'reçue':
                recu[achat['article_id']] = recu.get(achat['article_id'], 0) + float(achat['quantite'])
                self.assertTrue(achat['date_reception'])
            else:
                self.assertEqual(achat['date_reception'], '')
        for mouvement in self.t['mouvements_stock']:
            if mouvement['type'] == 'entrée':
                entre[mouvement['article_id']] = entre.get(mouvement['article_id'], 0) + float(mouvement['quantite'])
        self.assertEqual(recu, entre)

    # -- codes de défaillance

    def test_codes_de_defaillance(self):
        par_famille = {}
        for code in self.t['codes_defaillance']:
            par_famille.setdefault(code['famille'], []).append(code['code'])
        self.assertEqual(par_famille['symptôme'], ['S%02d' % n for n in range(1, 11)] + ['S99'])
        self.assertEqual(par_famille['cause'], ['C%02d' % n for n in range(1, 15)] + ['C99'])
        self.assertEqual(par_famille['remède'], ['R%02d' % n for n in range(1, 11)])

    # -- historique : cas démontrables

    def test_po02_trois_fuites_de_garniture_a_58_jours(self):
        fuites = [o for o in self.ot_de('PO-02') if o['type'].startswith('correctif') and o['cause_code'] == 'C01']
        self.assertEqual(len(fuites), 3)
        dates = sorted(jour(self.di_par_id[o['di_id']]['date_heure']) for o in fuites)
        for avant, apres in zip(dates, dates[1:]):
            self.assertTrue(55 <= (apres - avant).days <= 61, (avant, apres))
        kit = [a for a in self.t['articles'] if a['designation'] == 'Kit garniture mécanique PO-02'][0]
        for fuite in fuites:
            sorties = [m for m in self.t['mouvements_stock']
                       if m['ot_id'] == fuite['id'] and m['article_id'] == kit['id'] and m['type'] == 'sortie']
            self.assertEqual(len(sorties), 1, fuite['id'])

    def test_cv02_arrets_intempestifs_repetes(self):
        arrets = [o for o in self.ot_de('CV-02') if o['symptome_code'] == 'S05' and o['cause_code'] == 'C04']
        self.assertGreaterEqual(len(arrets), 5)

    def test_cp01_echauffements_recurrents(self):
        echauffements = [o for o in self.ot_de('CP-01') if o['symptome_code'] == 'S04']
        self.assertGreaterEqual(len(echauffements), 4)

    def test_un_equipement_a_panne_unique(self):
        correctifs = {repere: [o for o in self.ot_de(repere) if o['type'].startswith('correctif')]
                      for repere in self.equipement}
        uniques = [repere for repere, liste in correctifs.items() if len(liste) == 1]
        self.assertIn('BA-01', uniques)

    def test_ve01_cinq_preventifs_consecutifs_sans_constat(self):
        ot = sorted(self.ot_de('VE-01'), key=lambda o: o['date_creation'])
        self.assertGreaterEqual(len(ot), 5)
        self.assertTrue(all(o['type'].startswith('préventif') for o in ot), 'aucun correctif sur VE-01')
        for o in ot:
            if o['statut'].startswith('Clôturé'):
                self.assertRegex(o['compte_rendu'], r'(?i)ras|rien à signaler')

    def test_une_panne_entre_deux_visites_preventives(self):
        trouve = False
        for repere in self.equipement:
            ot = self.ot_de(repere)
            preventifs = sorted((o for o in ot if o['type'].startswith('préventif') and o['date_fin']),
                                key=lambda o: o['date_fin'])
            for avant, apres in zip(preventifs, preventifs[1:]):
                for o in ot:
                    if o['type'].startswith('correctif') and o['date_debut'] and avant['date_fin'] < o['date_debut'] < apres['date_debut']:
                        trouve = True
        self.assertTrue(trouve)

    def test_chaines_symptome_cause_remede_coherentes(self):
        """Une même cause mène toujours aux mêmes familles de remèdes plausibles (pas de fuite -> réarmement)."""
        plausibles = {
            'C01': {'R01'}, 'C02': {'R01', 'R10'}, 'C03': {'R02'}, 'C04': {'R03'}, 'C05': {'R01', 'R03'},
            'C06': {'R04'}, 'C07': {'R05'}, 'C08': {'R08'}, 'C09': {'R07'}, 'C10': {'R01'}, 'C11': {'R02'},
            'C12': {'R08'}, 'C13': {'R10'}, 'C14': {'R01'}, 'C99': {'R06', 'R09', 'R10', 'R01', 'R02', 'R03', 'R04', 'R05'}}
        for o in self.t['ordres_travail']:
            if o['type'].startswith('correctif') and o['statut'].startswith('Clôturé'):
                self.assertIn(o['remede_code'], plausibles[o['cause_code']], '%s %s %s' % (o['id'], o['cause_code'], o['remede_code']))
        symptomes_par_cause = {}
        for o in self.t['ordres_travail']:
            if o['type'].startswith('correctif') and o['cause_code'] == 'C01':
                symptomes_par_cause.setdefault('C01', set()).add(o['symptome_code'])
        self.assertEqual(symptomes_par_cause['C01'], {'S01'})

    def test_comptes_rendus_varies_et_pauvres_seulement_sur_les_preventifs(self):
        correctifs = [o for o in self.t['ordres_travail'] if o['type'].startswith('correctif') and o['compte_rendu']]
        self.assertGreaterEqual(len({o['compte_rendu'] for o in correctifs}), 30)
        pauvre = re.compile(r'(?i)^(ras|fait|rien à signaler|contrôle fait|tout est conforme)')
        for o in correctifs:
            self.assertIsNone(pauvre.match(o['compte_rendu']), '%s : %r' % (o['id'], o['compte_rendu']))
        preventifs_pauvres = [o for o in self.t['ordres_travail']
                              if o['type'].startswith('préventif') and pauvre.match(o['compte_rendu'])]
        self.assertGreaterEqual(len(preventifs_pauvres), 3)

    def test_temps_passes_arrets_et_sorties_de_stock(self):
        arrets = [o for o in self.t['ordres_travail'] if o['arret_production'] == '1' and o['duree_arret_h']]
        self.assertGreaterEqual(len(arrets), 10)
        self.assertGreaterEqual(len([m for m in self.t['mouvements_stock'] if m['type'] == 'sortie']), 40)
        temps = {}
        for ligne in self.t['ot_temps']:
            temps[ligne['ot_id']] = temps.get(ligne['ot_id'], 0) + float(ligne['heures'])
        for o in self.t['ordres_travail']:
            if o['statut'].startswith('Clôturé'):
                self.assertGreater(temps.get(o['id'], 0), 0, o['id'])

    def test_les_ot_clotures_respectent_rg4(self):
        for o in self.t['ordres_travail']:
            if not o['statut'].startswith('Clôturé'):
                continue
            self.assertTrue(o['date_fin'], o['id'])
            self.assertTrue(o['cause_code'] and o['remede_code'], o['id'])
            self.assertGreaterEqual(len(o['compte_rendu']), 10, o['id'])
            self.assertEqual(o['remise_service'], '1', o['id'])
            self.assertTrue(o['date_cloture_tech'], o['id'])
            self.assertEqual(o['statut'] == 'Clôturé administrativement', bool(o['date_cloture_admin']), o['id'])

    def test_la_plupart_des_ot_anciens_sont_clotures_administrativement(self):
        statuts = [o['statut'] for o in self.t['ordres_travail']]
        administratifs = statuts.count('Clôturé administrativement')
        techniques = statuts.count('Clôturé techniquement')
        self.assertGreater(administratifs, 0.7 * len(statuts))
        self.assertTrue(1 <= techniques <= 15, techniques)

    def test_les_preventifs_copient_les_operations_de_leur_gamme(self):
        operations_par_ot = {}
        for operation in self.t['ot_operations']:
            operations_par_ot.setdefault(operation['ot_id'], []).append(operation)
        operations_par_gamme = {}
        for operation in self.t['gamme_operations']:
            operations_par_gamme.setdefault(operation['gamme_id'], []).append(operation)
        preventifs = [o for o in self.t['ordres_travail'] if o['origine'] == 'préventif']
        self.assertGreaterEqual(len(preventifs), 25)
        for o in preventifs:
            copiees = sorted(operations_par_ot[o['id']], key=lambda x: int(x['ordre']))
            modele = sorted(operations_par_gamme[o['gamme_id']], key=lambda x: int(x['ordre']))
            self.assertEqual([c['operation'] for c in copiees], [m['operation'] for m in modele], o['id'])
            if o['statut'].startswith('Clôturé'):
                self.assertTrue(all(c['fait'] == '1' for c in copiees), o['id'])

    # -- état à la date de référence

    def test_demandes_a_la_date_de_reference(self):
        statuts = [d['statut'] for d in self.t['demandes']]
        self.assertTrue(3 <= statuts.count('Nouvelle') <= 4, statuts.count('Nouvelle'))
        self.assertEqual(statuts.count('Différée'), 1)
        self.assertEqual(statuts.count('Refusée'), 1)
        for demande in self.t['demandes']:
            if demande['statut'] == 'Refusée':
                self.assertGreaterEqual(len(demande['motif_decision']), 10)
            if demande['statut'] in ('Acceptée', 'Regroupée'):
                self.assertIn(demande['ot_id'], self.ot_par_id)
            if demande['statut'] in ('Nouvelle', 'Différée', 'Refusée'):
                self.assertEqual(demande['ot_id'], '')
        self.assertGreaterEqual(statuts.count('Regroupée'), 1)
        self.assertTrue(any(d['statut'] == 'Nouvelle' and d['impact'] == 'sécurité' for d in self.t['demandes']))

    def test_ot_ouverts_dans_tous_les_statuts(self):
        ouverts = [o for o in self.t['ordres_travail'] if self.est_ouvert(o)]
        self.assertEqual({o['statut'] for o in ouverts}, {'Créé', 'Préparé', 'Planifié', 'En cours', 'En attente'})
        attente = [o for o in ouverts if o['statut'] == 'En attente']
        self.assertEqual(len(attente), 1)
        self.assertRegex(attente[0]['motif_attente'], r'(?i)pièce')
        p1 = [o for o in ouverts if o['priorite'] == 'P1']
        self.assertEqual(len(p1), 1, [o['id'] for o in p1])
        retard = [o for o in ouverts if o['date_prevue'] < DATE_REFERENCE]
        self.assertTrue(2 <= len(retard) <= 3, [o['id'] for o in retard])

    def test_gamme_mensuelle_echue_sans_ot_ouvert(self):
        ouvertes = {o['gamme_id'] for o in self.t['ordres_travail'] if self.est_ouvert(o) and o['gamme_id']}
        echues_sans_ot = []
        for gamme in self.t['gammes']:
            if gamme['declencheur'] != 'date':
                continue
            echeance = jour(gamme['prochaine_echeance']) - timedelta(days=int(gamme['avance_jours']))
            if echeance <= JOUR_REFERENCE and gamme['id'] not in ouvertes:
                echues_sans_ot.append(gamme)
        self.assertEqual(len(echues_sans_ot), 1)
        self.assertEqual(echues_sans_ot[0]['periodicite_jours'], '30')
        self.assertGreater(len([o for o in self.t['ordres_travail'] if o['gamme_id'] == echues_sans_ot[0]['id']]), 3)

    def test_gammes_echues_ont_un_seul_ot_ouvert(self):
        ouverts = {}
        for o in self.t['ordres_travail']:
            if self.est_ouvert(o) and o['gamme_id']:
                ouverts[o['gamme_id']] = ouverts.get(o['gamme_id'], 0) + 1
        self.assertTrue(ouverts)
        self.assertTrue(all(n == 1 for n in ouverts.values()))

    def test_controles_reglementaires(self):
        controles = self.t['controles_reglementaires']
        en_retard = [c for c in controles if c['prochaine_date'] < DATE_REFERENCE]
        self.assertEqual(len(en_retard), 1)
        a_lever = [c for c in controles if c['observations'] and c['observations_levees'] == '0']
        self.assertEqual(len(a_lever), 1)
        a_planifier = [c for c in controles if 0 <= (jour(c['prochaine_date']) - JOUR_REFERENCE).days <= 30]
        self.assertGreaterEqual(len(a_planifier), 1)
        natures = ' '.join(c['nature'].lower() for c in controles)
        for mot in ('pont roulant', 'chariot', 'électrique', 'réservoir'):
            self.assertIn(mot, natures)

    def test_habilitation_exigee_respectee_dans_l_historique(self):
        """Les OT de l'historique sur AE-03 (BR) sont faits par un technicien qui avait un BR valide ce jour-là."""
        ot = [o for o in self.ot_de('AE-03') if o['technicien_id'] and o['date_debut']]
        self.assertGreaterEqual(len(ot), 1)
        for o in ot:
            valides = [h for h in self.t['habilitations']
                       if h['technicien_id'] == o['technicien_id'] and h['intitule'] == 'BR'
                       and h['date_obtention'] <= o['date_debut'][:10] <= h['date_echeance']]
            self.assertTrue(valides, o['id'])


# ---------------------------------------------------------------------------
# Tests avec Chromium : schéma JS, références, js/demo-donnees.js
# ---------------------------------------------------------------------------

JS_DECRIRE_SCHEMA = """
JSON.stringify(Schema.nomsTables().map(nom => {
  const table = Schema.table(nom);
  return { nom: nom, identifiant: table.identifiant || null, champs: table.champs.map(c => ({
    nom: c.nom, type: c.type, protege: c.protege === true, table: c.table || '',
    champCible: c.champCible || '', famille: c.filtre ? c.filtre.famille : '', valeurs: c.valeurs || null })) };
}))
"""


class TestAvecNavigateur(CasNavigateur):
    """Comparaisons avec js/schema.js et chargement de js/demo-donnees.js dans Chromium."""

    def schema_js(self):
        charger_scripts(self.page, ['js/schema.js'])
        return {t['nom']: t for t in json.loads(self.page.evaluate(JS_DECRIRE_SCHEMA))}

    def test_schema_python_identique_au_schema_js(self):
        generateur = charger_generateur()
        schema_js = self.schema_js()
        self.assertEqual(list(schema_js), TABLES)
        decrit = generateur.decrire_schema()
        for table in TABLES:
            champs_python = decrit[table]['champs']
            champs_js = schema_js[table]['champs']
            self.assertEqual([c['nom'] for c in champs_python], [c['nom'] for c in champs_js], table)
            for python, js in zip(champs_python, champs_js):
                self.assertEqual(python['type'], js['type'], '%s.%s' % (table, js['nom']))
                self.assertEqual(python['protege'], js['protege'], '%s.%s' % (table, js['nom']))
                self.assertEqual(python.get('table', ''), js['table'], '%s.%s' % (table, js['nom']))
                self.assertEqual(python.get('champCible', ''), js['champCible'], '%s.%s' % (table, js['nom']))
                self.assertEqual(python.get('famille', ''), js['famille'], '%s.%s' % (table, js['nom']))
                self.assertEqual(python.get('valeurs'), js['valeurs'], '%s.%s' % (table, js['nom']))
            if schema_js[table]['identifiant']:
                identifiant = schema_js[table]['identifiant']
                self.assertEqual(decrit[table]['identifiant'],
                                 [identifiant['prefixe'], identifiant['chiffres'], bool(identifiant['annuel'])], table)

    def test_en_tetes_csv_identiques_au_schema_js(self):
        schema_js = self.schema_js()
        for table in TABLES:
            en_tetes, _ = lire_table(DOSSIER_DEMO, table)
            self.assertEqual(en_tetes, [c['nom'] for c in schema_js[table]['champs']], table)

    def test_references_valides_selon_le_schema_js(self):
        schema_js = self.schema_js()
        tables = {table: lire_table(DOSSIER_DEMO, table)[1] for table in TABLES}
        cle = {table: ('cle' if table == 'parametres' else 'id') for table in TABLES}
        valeurs_cles = {table: {retirer_apostrophe(l[cle[table]]) for l in tables[table]} for table in TABLES}
        codes = {}
        for ligne in tables['codes_defaillance']:
            codes.setdefault(ligne['famille'], set()).add(ligne['code'])
        verifiees = 0
        for table in TABLES:
            for champ in schema_js[table]['champs']:
                for ligne in tables[table]:
                    valeur = ligne[champ['nom']]
                    if champ['type'] == 'choix':
                        self.assertIn(valeur, champ['valeurs'], '%s.%s = %r' % (table, champ['nom'], valeur))
                    elif champ['type'] == 'ref' and valeur != '':
                        valides = codes[champ['famille']] if champ['champCible'] else valeurs_cles[champ['table']]
                        self.assertIn(valeur, valides, '%s %s.%s = %r' % (ligne.get('id'), table, champ['nom'], valeur))
                        verifiees += 1
        self.assertGreater(verifiees, 1000)

    def test_champs_proteges_selon_le_schema_js(self):
        schema_js = self.schema_js()
        for table in TABLES:
            for champ in schema_js[table]['champs']:
                if not champ['protege']:
                    continue
                for ligne in lire_table(DOSSIER_DEMO, table)[1]:
                    if ligne[champ['nom']] != '':
                        self.assertTrue(ligne[champ['nom']].startswith("'"), '%s.%s' % (table, champ['nom']))

    def test_demo_donnees_js_contient_les_22_tables_identiques_aux_csv(self):
        charger_scripts(self.page, ['js/demo-donnees.js'])
        self.assertEqual(self.page.evaluate('DEMO_DONNEES.dateReference'), DATE_REFERENCE)
        noms = self.page.evaluate('Object.keys(DEMO_DONNEES.tables)')
        self.assertEqual(noms, TABLES)
        for table in TABLES:
            texte = self.page.evaluate('(nom) => DEMO_DONNEES.tables[nom]', table)
            octets = (DOSSIER_DEMO / (table + '.csv')).read_bytes()
            self.assertTrue(octets.startswith(b'\xef\xbb\xbf'))
            self.assertEqual(texte, octets[3:].decode('utf-8'), table)
            self.assertNotIn('﻿', texte)

    def test_aller_retour_par_donnees_csv_sans_probleme(self):
        """Chaque CSV lu puis réécrit par Donnees.csv (js/donnees.js) est identique octet pour octet, sans problème signalé
        (ignoré tant que js/donnees.js n'existe pas)."""
        if not (RACINE / 'js' / 'donnees.js').is_file():
            self.skipTest('js/donnees.js absent')
        charger_scripts(self.page, ['js/lib/papaparse.min.js', 'js/schema.js', 'js/donnees.js'])
        if not self.page.evaluate("typeof Donnees === 'object' && Donnees.csv && typeof Donnees.csv.analyser === 'function'"
                                  " && typeof Donnees.csv.serialiser === 'function'"):
            self.skipTest('Donnees.csv.analyser / serialiser absents')
        for table in TABLES:
            octets = list((DOSSIER_DEMO / (table + '.csv')).read_bytes())
            resultat = self.page.evaluate("""([table, octets]) => {
                const analyse = Donnees.csv.analyser(table, new Uint8Array(octets));
                const sortie = Donnees.csv.serialiser(table, analyse.lignes, analyse.colonnesInconnues);
                return { sortie: Array.from(sortie), problemes: analyse.problemes.map(p => p.type + ' : ' + p.message),
                         colonnesInconnues: analyse.colonnesInconnues.length };
            }""", [table, octets])
            self.assertEqual(resultat['problemes'], [], table)
            self.assertEqual(resultat['colonnesInconnues'], 0, table)
            self.assertEqual(resultat['sortie'], octets, table + ' : la réécriture diffère du fichier généré')

    def test_regle_de_protection_identique_a_donnees_js(self):
        """Python et JavaScript appliquent la même règle d'apostrophe (ignoré tant que js/donnees.js n'existe pas)."""
        if not (RACINE / 'js' / 'donnees.js').is_file():
            self.skipTest('js/donnees.js absent')
        charger_scripts(self.page, ['js/schema.js', 'js/donnees.js'])
        if not self.page.evaluate("typeof Donnees === 'object' && Donnees.csv && typeof Donnees.csv.ecrireValeur === 'function'"):
            self.skipTest('Donnees.csv.ecrireValeur absent')
        generateur = charger_generateur()
        echantillon = ['- remplacer joint', '00123', '123456789012345', '1/2', '2026-10', "'déjà", '12:30', '50 %',
                       '1,5E+3', '=SOMME(A1)', 'texte normal', 'Joint à lèvres 35x52x7', '3.5', '@nom', '+33 1', ' 12 ',
                       '12 mm', '6 à 7,5 bar', '1.2.3', '1-12', '2026-10-19', '', 'A', '0']
        for type_champ in ('texte', 'texte_long'):
            for protege in (False, True):
                champ = {'nom': 'x', 'type': type_champ}
                if protege:
                    champ['protege'] = True
                for valeur in echantillon:
                    attendu = generateur.ecrire_valeur({'type': type_champ, 'protege': protege}, valeur)
                    obtenu = self.page.evaluate('([c, v]) => Donnees.csv.ecrireValeur(c, v)', [champ, valeur])
                    self.assertEqual(obtenu, attendu, '%s protege=%s %r' % (type_champ, protege, valeur))


# ---------------------------------------------------------------------------
# Reproductibilité et options de la ligne de commande
# ---------------------------------------------------------------------------

class TestGenerateur(unittest.TestCase):

    def test_deux_executions_donnent_des_fichiers_identiques(self):
        with tempfile.TemporaryDirectory() as temporaire:
            racine = Path(temporaire)
            for numero in (1, 2):
                processus, _ = executer_generateur('--sortie', racine / ('csv%d' % numero),
                                                   '--fichier-js', racine / ('demo%d.js' % numero))
                self.assertEqual(processus.returncode, 0, processus.stderr.decode('utf-8', 'replace'))
            for table in TABLES:
                self.assertEqual((racine / 'csv1' / (table + '.csv')).read_bytes(),
                                 (racine / 'csv2' / (table + '.csv')).read_bytes(), table)
            self.assertEqual((racine / 'demo1.js').read_bytes(), (racine / 'demo2.js').read_bytes())
            # Les fichiers livrés sont ceux que produit le générateur (aucun oubli de régénération).
            for table in TABLES:
                self.assertEqual((racine / 'csv1' / (table + '.csv')).read_bytes(),
                                 (DOSSIER_DEMO / (table + '.csv')).read_bytes(),
                                 table + ' : relancer py outils/generer_demo.py')
            self.assertEqual((racine / 'demo1.js').read_bytes(), FICHIER_JS.read_bytes(),
                             'js/demo-donnees.js : relancer py outils/generer_demo.py')

    def test_le_fichier_js_est_bien_forme(self):
        texte = FICHIER_JS.read_text(encoding='utf-8')
        self.assertTrue(texte.startswith("'use strict';"))
        self.assertIn('ne pas modifier', texte)
        self.assertIn("dateReference: \"2026-10-19\"", texte)
        self.assertIn('const DEMO_DONNEES = {', texte)
        self.assertNotIn('﻿', texte)

    def test_jeu_de_charge_500_equipements_5000_ot(self):
        with tempfile.TemporaryDirectory() as temporaire:
            sortie = Path(temporaire) / 'charge'
            processus, duree = executer_generateur('--volume', '500,5000', '--sortie', sortie)
            self.assertEqual(processus.returncode, 0, processus.stderr.decode('utf-8', 'replace'))
            self.assertLess(duree, 60)
            self.assertEqual(len(lire_table(sortie, 'equipements')[1]), 500)
            self.assertEqual(len(lire_table(sortie, 'ordres_travail')[1]), 5000)
            demandes = len(lire_table(sortie, 'demandes')[1])
            self.assertTrue(2500 <= demandes <= 3500, demandes)
            self.assertEqual(sorted(p.name for p in sortie.glob('*.csv')), sorted(t + '.csv' for t in TABLES))
            self.assertGreater(len(lire_table(sortie, 'ot_operations')[1]), 5000)
            self.assertGreater(len(lire_table(sortie, 'ot_temps')[1]), 5000)

    def test_option_mois_etend_l_historique(self):
        with tempfile.TemporaryDirectory() as temporaire:
            sortie = Path(temporaire) / 'long'
            processus, _ = executer_generateur('--mois', '13', '--sortie', sortie)
            self.assertEqual(processus.returncode, 0, processus.stderr.decode('utf-8', 'replace'))
            ot_long = lire_table(sortie, 'ordres_travail')[1]
            ot_court = lire_table(DOSSIER_DEMO, 'ordres_travail')[1]
            self.assertGreater(len(ot_long), 1.5 * len(ot_court))
            premiere = min(o['date_creation'][:10] for o in ot_long)
            self.assertLessEqual(premiere, '2025-10-31')
            self.assertTrue(any(o['id'].startswith('OT-2025-') for o in ot_long))
            self.assertEqual(len(lire_table(sortie, 'equipements')[1]), 31)

    def test_volume_sans_sortie_est_refuse(self):
        processus, _ = executer_generateur('--volume', '500,5000')
        self.assertNotEqual(processus.returncode, 0)


if __name__ == '__main__':
    unittest.main()
