"""Tests du jeu de démo : outils/generer_demo.py, donnees/demo/*.csv, js/demo-donnees.js et
tests/fixtures/demo-scenarios.json.

Ce qui est vérifié (docs/ARCHITECTURE.md §3, §4, §11, §14.1, §14.8 ; brief §13) :
  - 24 fichiers CSV : BOM, séparateur « ; », fins de ligne CRLF, en-têtes identiques à js/schema.js ;
  - références (clés étrangères) valides, valeurs des listes valides ;
  - volumes du brief §13, historique de 13 mois et présence des objets des scénarios de recette ;
  - champs du format v2 renseignés (valeur de remplacement, code symptôme, anomalies de préventif) ;
  - causes fréquentes (§14.5) : équipements à 5 cas et plus, portée « modèle », cas insuffisants ;
  - identifiants de scénario : fichier identique à celui du générateur, chaque clé a sa propriété ;
  - lot 3 (§15.12, D49) : contrôles réglementaires dans les 4 statuts (§15.7), planning des 4 semaines
    avec une surcharge, OT « Préparé » à planifier, panne clôturée sans durée d'arrêt, historique des
    statuts des pannes récentes au journal (dont une attente de pièce, §15.3), journal décalé par
    StockageDemo comme les autres dates ;
  - lot 3 bis (§16.8, D62) : rôles des suggestions de préventif, prouvés par un calcul Python des règles du
    §16.3 écrit ici (réglages par défaut, décisions du journal comprises) : S1, S2, S3 (case cochée et DI
    liée), S4, refus pour la seule criticité A, cas sous le seuil, suggestion ignorée puis revenue ;
  - lot 6 (§20.10, D109, D110) : astuces sur des OT correctifs clôturés, tirées de leur scénario, sans vocabulaire
    de la sécurité ; deux OT de scénario contradictoires (CP-01, PO-02), clôturés administrativement, numérotés en dernier ;
  - champs protégés par une apostrophe (§3.2) ;
  - js/demo-donnees.js chargé dans Chromium : 24 tables, texte identique aux CSV ; démo en file://
    chargée vite et sans erreur au « Contrôle de la base » ;
  - reproductibilité (deux exécutions = fichiers identiques, et fichiers livrés à jour) ;
  - options --volume 500,5000 (moins de 60 s, gammes, compteurs, mouvements, achats) et --mois 6.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_demo.py" -v
"""
import calendar
import csv
import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from commun import (FICHIER_SCENARIOS, RACINE, CasNavigateur, attendre_pret, charger_scripts, scenarios_demo,
                    url_fichier)

SCRIPT_GENERATEUR = RACINE / 'outils' / 'generer_demo.py'
DOSSIER_DEMO = RACINE / 'donnees' / 'demo'
FICHIER_JS = RACINE / 'js' / 'demo-donnees.js'
DATE_REFERENCE = '2026-10-19'
JOUR_REFERENCE = date(2026, 10, 19)
# L'historique commence entre 13,5 et 12,5 mois avant la date de référence (ARCHITECTURE.md §14.8).
DEBUT_AU_PLUS_TOT = date(2025, 9, 19) - timedelta(days=15)     # référence - 13 mois - 15 jours
DEBUT_AU_PLUS_TARD = date(2025, 10, 19) - timedelta(days=15)   # référence - 12 mois - 15 jours
STATUTS_FERMES = ('Clôturé techniquement', 'Clôturé administrativement', 'Annulé')
MINIMUM_CAUSES = 5                                             # ARCHITECTURE.md §14.5
MAINTENANT = DATE_REFERENCE + ' 09:00'                         # il est 9 h à la date de référence
# Lot 3 (ARCHITECTURE.md §15.12) : rôles de scénario ajoutés, fenêtres de temps des indicateurs.
ROLES_LOT3 = ('controle_en_retard', 'controle_a_planifier', 'controle_observations', 'controle_a_jour',
              'technicien_surcharge', 'semaine_surcharge', 'ot_a_planifier', 'ot_a_planifier_br',
              'ot_a_planifier_piece_manquante', 'panne_attente_pieces', 'panne_sans_duree',
              'equipements_calcul_main')
LUNDIS_PLANNING = [JOUR_REFERENCE + timedelta(weeks=rang) for rang in range(4)]   # 4 semaines du planning
DEBUT_3_MOIS = date(2026, 7, 19)          # pannes dont l'historique des statuts est au journal
DEBUT_12_MOIS = date(2025, 10, 20)        # période « 12-mois » (§15.3) : même jour 12 mois plus tôt + 1 jour
TYPES_CORRECTIFS = ('correctif immédiat', 'correctif différé')
MOTIF_STATUT = re.compile(r'statut (.+?) → (.+?)(?: : (.+))?')
# Lot 3 bis (ARCHITECTURE.md §16.8) : rôles de scénario ajoutés, réglages par défaut des suggestions (§16.1).
ROLES_LOT3BIS = ('suggestion_creer', 'suggestion_revoir', 'suggestion_anomalies', 'suggestion_allonger',
                 'suggestion_refus_criticite_a', 'suggestion_sous_seuil', 'suggestion_ignoree_revenue')
SEUIL_PANNES, VISITES_SANS_CONSTAT, FENETRE_MOIS = 3, 5, 12
STATUTS_CLOTURES = ('Clôturé techniquement', 'Clôturé administrativement')
MOTIF_DECISION = re.compile(r'suggestion (S[1-4]-\S+) (ignorée|traitée) : (.*)')     # action entière (§16.4)

TABLES = [
    'localisations', 'equipements', 'demandes', 'ordres_travail', 'ot_operations', 'ot_pieces',
    'ot_temps', 'gammes', 'gamme_operations', 'articles', 'article_equipement', 'mouvements_stock',
    'techniciens', 'habilitations', 'compteurs', 'releves', 'controles_reglementaires',
    'codes_defaillance', 'fournisseurs', 'achats', 'parametres', 'journal',
    'wiki_pages', 'wiki_journal']                           # format 3 (lot 6, ARCHITECTURE.md §20.2)


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


def est_ouvert(ot):
    return ot['statut'] not in STATUTS_FERMES


def cas_causes_frequentes(t, equipements, symptome):
    """OT comptés par l'encart des causes fréquentes (§14.5) : correctifs clôturés de ce symptôme,
    cause renseignée, sur les équipements donnés."""
    return [o for o in t['ordres_travail']
            if o['equipement_id'] in equipements and o['type'].startswith('correctif')
            and o['statut'].startswith('Clôturé') and o['symptome_code'] == symptome and o['cause_code']]


def equipements_du_modele(t, equipement_id):
    """Équipements de même marque et même modèle (casse ignorée), lui compris (portée « modèle »)."""
    equipement = [e for e in t['equipements'] if e['id'] == equipement_id][0]
    cle = (equipement['marque'].strip().lower(), equipement['modele'].strip().lower())
    return {e['id'] for e in t['equipements'] if (e['marque'].strip().lower(), e['modele'].strip().lower()) == cle}


# ---------------------------------------------------------------------------
# Règles du lot 3 recalculées en Python (ARCHITECTURE.md §15.3, §15.5, §15.7), indépendamment du générateur
# ---------------------------------------------------------------------------

def ajouter_mois(jour_, nombre):
    """§15.7 : même jour, `nombre` mois plus tard, ramené au dernier jour du mois (31/01 + 1 → 28 ou 29/02)."""
    annee, mois = divmod(jour_.year * 12 + jour_.month - 1 + nombre, 12)
    return date(annee, mois + 1, min(jour_.day, calendar.monthrange(annee, mois + 1)[1]))


def statut_controle(controle, aujourdhui):
    """Statut d'un contrôle réglementaire à une date (§15.7) : le premier vrai parmi « en retard »,
    « observations à lever », « à planifier » (30 jours ou moins, ou date inconnue) et « à jour »."""
    if controle['prochaine_date']:
        prochaine = jour(controle['prochaine_date'])
    elif controle['derniere_date'] and controle['periodicite_mois']:
        prochaine = ajouter_mois(jour(controle['derniere_date']), int(controle['periodicite_mois']))
    else:
        prochaine = None
    if prochaine is not None and prochaine < aujourdhui:
        return 'en retard'
    if controle['observations'].strip() and controle['observations_levees'] != '1':
        return 'observations à lever'
    if prochaine is None or prochaine <= aujourdhui + timedelta(days=30):
        return 'à planifier'
    return 'à jour'


def lundi_du_planning(date_prevue):
    """Lundi de la semaine du planning (les 4 semaines qui commencent à la date de référence) qui
    contient cette date prévue, ou None."""
    if not date_prevue:
        return None
    for lundi in LUNDIS_PLANNING:
        if lundi <= jour(date_prevue) < lundi + timedelta(days=7):
            return lundi
    return None


def charges_du_planning(t):
    """Charge de chaque technicien par semaine du planning : {(technicien, lundi ISO): heures}. Même règle
    que Planning.chargeSemaine (§15.5) : somme des temps prévus (vide = 0) des OT ni clôturés ni annulés
    qui ont un technicien et une date prévue dans la semaine."""
    charges = {}
    for ot in t['ordres_travail']:
        lundi = lundi_du_planning(ot['date_prevue'])
        if est_ouvert(ot) and ot['technicien_id'] and lundi:
            cle = (ot['technicien_id'], lundi.isoformat())
            charges[cle] = charges.get(cle, 0.0) + float(ot['temps_prevu_h'] or 0)
    return charges


def est_panne(ot):
    """§15.3 : OT correctif, arrêt de production, non annulé."""
    return ot['type'] in TYPES_CORRECTIFS and ot['arret_production'] == '1' and ot['statut'] != 'Annulé'


def date_de_panne(t, ot):
    """§15.3 : date_heure de la DI de l'OT (di_id, sinon une DI dont ot_id est cet OT), sinon date_creation."""
    for demande in t['demandes']:
        if demande['id'] == ot['di_id']:
            return jour(demande['date_heure'])
    liees = sorted(d['date_heure'] for d in t['demandes'] if d['ot_id'] == ot['id'])
    return jour(liees[0] if liees else ot['date_creation'])


def action_metier(action):
    """Ce qui suit « — » dans une action du journal (« création — acceptation de DI-… » → « acceptation de DI-… »)."""
    return action.split(' — ', 1)[1] if ' — ' in action else action


def sans_accents(texte):
    return unicodedata.normalize('NFD', texte).encode('ascii', 'ignore').decode('ascii').lower()


def instant_texte(texte):
    return datetime.strptime(texte, '%Y-%m-%d %H:%M')


def historique_ot(t, ot_id):
    """Entrées du journal d'un OT (table ordres_travail), triées par date_heure puis identifiant (§15.3)."""
    return sorted((l for l in t['journal'] if l['table'] == 'ordres_travail' and l['id_ligne'] == ot_id),
                  key=lambda l: (l['date_heure'], l['id']))


def attente_pieces_brute(t, ot):
    """Heures d'attente de pièces d'un OT lues au journal (§15.3), SANS le plafond duree_arret_h : somme des
    intervalles entre « statut X → En attente : m » (m commence par « pièce », casse et accents ignorés)
    et l'action « statut En attente → Y » suivante ; sans sortie, jusqu'à date_fin."""
    total, debut = 0.0, None
    for entree in historique_ot(t, ot['id']):
        correspondance = MOTIF_STATUT.fullmatch(action_metier(entree['action']))
        if not correspondance:
            continue
        depart, arrivee, motif = correspondance.groups()
        if arrivee == 'En attente' and sans_accents(motif or '').startswith('piece'):
            debut = instant_texte(entree['date_heure'])
        elif depart == 'En attente' and debut is not None:
            total += (instant_texte(entree['date_heure']) - debut).total_seconds() / 3600.0
            debut = None
    if debut is not None and ot['date_fin']:
        total += (instant_texte(ot['date_fin']) - debut).total_seconds() / 3600.0
    return total


# ---------------------------------------------------------------------------
# Règles du lot 3 bis recalculées en Python (ARCHITECTURE.md §16.2 à §16.4), indépendamment du générateur
# ---------------------------------------------------------------------------

def moment(ot):
    """§16.2 : date_fin, sinon date_cloture_tech, sinon date_creation, ramené à « AAAA-MM-JJ HH:MM »."""
    return (ot['date_fin'] or ot['date_cloture_tech'] or ot['date_creation']).replace('T', ' ')[:16]


def decisions_par_cle(t, avant=None):
    """§16.4 : dernière décision de chaque clé {clé: (ligne du journal, décision, texte)} ; la plus récente
    par date_heure puis identifiant. avant : seules les décisions antérieures à ce moment comptent."""
    resultat = {}
    for ligne in sorted(t['journal'], key=lambda l: (l['date_heure'], l['id'])):
        forme = MOTIF_DECISION.fullmatch(ligne['action'])
        if forme and (avant is None or ligne['date_heure'] < avant):
            resultat[forme.group(1)] = (ligne, forme.group(2), forme.group(3))
    return resultat


def avec_anomalie(t, visite, jusqu_a=None):
    """§16.2 : case « anomalie constatée » cochée OU au moins une DI dont ot_origine_id est la visite."""
    return visite['anomalie_constatee'] == '1' or any(
        d['ot_origine_id'] == visite['id'] and (jusqu_a is None or d['date_heure'] <= jusqu_a) for d in t['demandes'])


def suggestions_ouvertes(t, aujourdhui=JOUR_REFERENCE, seuil=SEUIL_PANNES, jusqu_a=None, criticites=None):
    """Suggestions ouvertes selon le §16.3 : {clé: {regle, equipement, cause, faits: [OT], sur, depuis}}.
    jusqu_a : moment ; seuls les OT, DI et décisions antérieurs comptent (état de la base à ce moment).
    criticites : {équipement: criticité} qui remplace celle du fichier."""
    debut = ajouter_mois(aujourdhui, -FENETRE_MOIS) + timedelta(days=1)
    decisions = decisions_par_cle(t, jusqu_a)
    criticite = dict({e['id']: e['criticite'] for e in t['equipements']}, **(criticites or {}))
    suivis = [e['id'] for e in t['equipements'] if e['actif'] != '0' and e['statut'] != 'rebut']
    ordres = [o for o in t['ordres_travail'] if jusqu_a is None or moment(o) <= jusqu_a]
    actives = [g for g in t['gammes'] if g['actif'] != '0']
    suivies = [g for g in actives if g['declencheur'] in ('date', 'compteur') and g['equipement_id'] in suivis]

    def visites(gamme):
        return sorted((o for o in ordres if o['gamme_id'] == gamme['id'] and o['statut'] in STATUTS_CLOTURES
                       and jour(moment(o)) <= aujourdhui), key=lambda o: (moment(o), o['id']))

    def apres_decision(cle, ot):
        return cle not in decisions or moment(ot) > decisions[cle][0]['date_heure']

    ouvertes = {}

    def ouvrir(cle, faits, equipement, cause='', sur=None):
        ouvertes[cle] = {'regle': cle[:2], 'equipement': equipement, 'cause': cause, 'faits': [o['id'] for o in faits],
                         'sur': sur, 'depuis': decisions[cle][0]['date_heure'] if cle in decisions else None}

    for equipement in suivis:
        siennes = [g for g in suivies if g['equipement_id'] == equipement and visites(g)]
        if not any(g['equipement_id'] == equipement for g in actives):
            regle, depuis = 'S1', ''
        elif siennes:
            regle, depuis = 'S2', min(moment(visites(g)[0]) for g in siennes)
        else:
            continue
        for cause in sorted({o['cause_code'] for o in ordres if o['cause_code']}):
            cle = '%s-%s-%s' % (regle, equipement, cause)
            faits = [o for o in ordres if o['equipement_id'] == equipement and o['type'] in TYPES_CORRECTIFS
                     and o['statut'] in STATUTS_CLOTURES and o['cause_code'] == cause
                     and debut <= jour(moment(o)) <= aujourdhui and moment(o) > depuis and apres_decision(cle, o)]
            if len(faits) >= seuil:
                ouvrir(cle, faits, equipement, cause)
    for gamme in suivies:
        cle = 'S3-' + gamme['id']
        regardees = [o for o in visites(gamme) if apres_decision(cle, o)][-4:]
        anomalies = [o for o in regardees if avec_anomalie(t, o, jusqu_a)]
        if len(anomalies) >= 2:
            ouvrir(cle, anomalies, gamme['equipement_id'], sur=len(regardees))
        cle = 'S4-' + gamme['id']
        serie = []
        for visite in reversed([o for o in visites(gamme) if apres_decision(cle, o)]):    # pas de passage au format 2
            if avec_anomalie(t, visite, jusqu_a):
                break
            serie.insert(0, visite)
        pannes = [o for o in ordres if serie and o['equipement_id'] == gamme['equipement_id']
                  and o['type'] in TYPES_CORRECTIFS and o['statut'] != 'Annulé'
                  and jour(o['date_creation']) >= jour(moment(serie[0]))]
        if criticite[gamme['equipement_id']] in ('B', 'C') and len(serie) >= VISITES_SANS_CONSTAT and not pannes:
            ouvrir(cle, serie, gamme['equipement_id'])
    return ouvertes


# ---------------------------------------------------------------------------
# Tests sans navigateur : format, contenu, scénarios, reproductibilité
# ---------------------------------------------------------------------------

class TestFichiersCsv(unittest.TestCase):
    """Format des 24 fichiers (§3.1)."""

    def test_23_fichiers_presents(self):
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

    def test_journal_bien_forme_et_trie(self):
        """Lot 3 (D49) : le journal n'est plus vide, il porte l'historique des pannes récentes. Chaque
        entrée a le format de l'application (§4, §5.3) : identifiant J-AAAAMMJJHHMMSS-XXXX qui reprend
        la minute de date_heure, poste « Poste démo », profil d'un vrai profil ; fichier trié par
        date_heure puis identifiant, rien après « maintenant » (date de référence, 9 h).
        Lot 3 bis (§16.4) : une décision sur une suggestion est l'action brute écrite par
        Donnees.journaliser (« suggestion <clé> ignorée : <motif> »), sur la table equipements (S1, S2) ou
        gammes (S3, S4), par le responsable ; les autres entrées restent l'historique des OT et des DI."""
        _, lignes = lire_table(DOSSIER_DEMO, 'journal')
        self.assertGreater(len(lignes), 20)
        identifiants = [l['id'] for l in lignes]
        self.assertEqual(len(set(identifiants)), len(identifiants), 'identifiants en double')
        self.assertEqual([(l['date_heure'], l['id']) for l in lignes], sorted((l['date_heure'], l['id']) for l in lignes))
        techniciens = {l['id'] for l in lire_table(DOSSIER_DEMO, 'techniciens')[1]}
        for ligne in lignes:
            morceaux = re.fullmatch(r'J-(\d{12})(\d{2})-[A-Z0-9]{4}', ligne['id'])
            self.assertIsNotNone(morceaux, ligne['id'])
            self.assertEqual(morceaux.group(1), re.sub(r'\D', '', ligne['date_heure']), ligne['id'])
            self.assertLessEqual(ligne['date_heure'], DATE_REFERENCE + ' 09:00', ligne['id'])
            self.assertEqual(ligne['poste'], 'Poste démo', ligne['id'])
            profil = ligne['profil']
            self.assertTrue(profil == 'Responsable' or profil.startswith('Demandeur ')
                            or (profil.startswith('Technicien ') and profil[len('Technicien '):] in techniciens),
                            '%s : profil %r' % (ligne['id'], profil))
            decision = MOTIF_DECISION.fullmatch(ligne['action'])
            if decision:
                regle = decision.group(1)[:2]
                self.assertEqual(ligne['table'], 'equipements' if regle in ('S1', 'S2') else 'gammes', ligne['id'])
                self.assertEqual(profil, 'Responsable', ligne['id'])
                self.assertIn(ligne['id_ligne'], decision.group(1), ligne['id'])
            else:
                self.assertIn(ligne['table'], ('ordres_travail', 'demandes'), ligne['id'])
                self.assertIn(' — ', ligne['action'], ligne['id'])

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
        self.assertEqual(len(t['gammes']), 12)      # 10 des lots 1 à 3 + 2 gammes récentes du lot 3 bis (§16.8)
        self.assertTrue(4 <= len(t['fournisseurs']) <= 5)
        self.assertGreaterEqual(len(t['controles_reglementaires']), 5)
        # 3 compteurs (heures, cycles) + 1 point de mesure pour la gamme seuil, un relevé par mois
        self.assertEqual(len(t['compteurs']), 4)
        self.assertGreaterEqual(len(t['releves']), 4 * 13)
        self.assertGreaterEqual(len(t['ordres_travail']), 200)
        self.assertGreaterEqual(len(t['demandes']), 120)
        self.assertEqual(sorted({g['declencheur'] for g in t['gammes']}), ['compteur', 'date', 'seuil'])
        for gamme in t['gammes']:
            operations = [o for o in t['gamme_operations'] if o['gamme_id'] == gamme['id']]
            self.assertTrue(3 <= len(operations) <= 8, '%s : %d opérations' % (gamme['id'], len(operations)))

    def test_entreprise_et_parametres(self):
        parametres = {p['cle']: p['valeur'] for p in self.t['parametres']}
        self.assertEqual(parametres['entreprise_nom'], 'Atelier des Trois Vallées (démo)')
        for cle, valeur in [('delai_p1_h', '0'), ('delai_p2_h', '24'), ('delai_p3_h', '168'),
                            ('delai_p4', 'prochain arrêt'), ('rafraichissement_s', '20'), ('version_schema', '3'),
                            # clés ajoutées par le lot 2 (ARCHITECTURE.md §14.1)
                            ('priorite_preventif', 'P3'), ('horizon_calendrier_semaines', '12')]:
            self.assertEqual(parametres[cle], valeur, cle)
        for cle in ('heures_fonct_defaut', 'tolerance_preventif_pct'):
            self.assertIn(cle, parametres)

    def test_historique_de_13_mois_se_terminant_a_la_date_de_reference(self):
        dates = sorted(o['date_creation'][:10] for o in self.t['ordres_travail'])
        self.assertEqual(dates[-1], DATE_REFERENCE)
        # Chaque partie de l'historique commence entre 13,5 et 12,5 mois avant la date de référence.
        preventifs = [o for o in self.t['ordres_travail'] if o['origine'] == 'préventif']
        for nom, lignes, champ in (('OT', self.t['ordres_travail'], 'date_creation'),
                                   ('DI', self.t['demandes'], 'date_heure'),
                                   ('préventifs', preventifs, 'date_creation'),
                                   ('relevés', self.t['releves'], 'date'),
                                   ('mouvements', self.t['mouvements_stock'], 'date'),
                                   ('achats', self.t['achats'], 'date')):
            premiere = jour(min(ligne[champ] for ligne in lignes))
            self.assertTrue(DEBUT_AU_PLUS_TOT <= premiere <= DEBUT_AU_PLUS_TARD, '%s : %s' % (nom, premiere))
        # Les identifiants gardent leur année : des OT et des DI de 2025 et de 2026.
        for table, prefixe in (('ordres_travail', 'OT-'), ('demandes', 'DI-')):
            for ligne in self.t[table]:
                champ = 'date_creation' if table == 'ordres_travail' else 'date_heure'
                self.assertTrue(ligne['id'].startswith(prefixe + ligne[champ][:4] + '-'), ligne['id'])
            self.assertEqual({ligne['id'][len(prefixe):len(prefixe) + 4] for ligne in self.t[table]}, {'2025', '2026'})
        for table, champ in (('ordres_travail', 'date_debut'), ('ordres_travail', 'date_fin'),
                             ('ordres_travail', 'date_cloture_tech'), ('ot_temps', 'date'),
                             ('mouvements_stock', 'date'), ('releves', 'date'), ('achats', 'date')):
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

    def test_valeur_de_remplacement_realiste_sur_chaque_equipement(self):
        """§14.1 : décimal en € HT, renseigné partout, dans les ordres de grandeur de chaque famille."""
        for equipement in self.t['equipements']:
            self.assertRegex(equipement['valeur_remplacement'], r'^\d+(\.\d+)?$', equipement['repere'])
            self.assertGreater(float(equipement['valeur_remplacement']), 0, equipement['repere'])
        fourchettes = {'CP-01': (25000, 40000), 'PO-01': (3000, 9000), 'PO-02': (3000, 9000), 'PO-03': (3000, 9000),
                       'CV-01': (8000, 20000), 'CV-02': (8000, 20000), 'CV-03': (8000, 20000),
                       'PR-01': (60000, 120000), 'CN-01': (80000, 150000), 'AE-01': (5000, 15000),
                       'AE-02': (5000, 15000), 'AE-03': (5000, 15000), 'AE-04': (5000, 15000),
                       'CH-01': (20000, 35000), 'GF-01': (15000, 30000)}
        for repere, (minimum, maximum) in fourchettes.items():
            valeur = float(self.equipement[repere]['valeur_remplacement'])
            self.assertTrue(minimum <= valeur <= maximum, '%s : %s €' % (repere, valeur))

    def test_codes_symptome_des_di_coherents_avec_leur_ot(self):
        """§14.6 : environ 80 % des DI ont un code symptôme, toujours celui de l'OT qu'elles ont produit
        (ou rejoint) ; les codes sont de la famille « symptôme »."""
        symptomes = {c['code'] for c in self.t['codes_defaillance'] if c['famille'] == 'symptôme'}
        avec_code = [d for d in self.t['demandes'] if d['symptome_code']]
        self.assertTrue(0.7 <= len(avec_code) / len(self.t['demandes']) <= 0.9,
                        '%d DI sur %d avec un code' % (len(avec_code), len(self.t['demandes'])))
        compares = 0
        for demande in avec_code:
            self.assertIn(demande['symptome_code'], symptomes, demande['id'])
            if demande['ot_id']:
                self.assertEqual(demande['symptome_code'], self.ot_par_id[demande['ot_id']]['symptome_code'], demande['id'])
                compares += 1
        self.assertGreater(compares, 80)

    def test_anomalies_de_preventif_avec_leur_di_liee(self):
        """§14.6 : deux OT préventifs avec anomalie constatée ; chacun a sa DI liée (ot_origine_id),
        l'une acceptée (correctif clôturé), l'autre « Nouvelle ».
        Lot 3 bis (§16.2, §16.8) : la gamme de la suggestion S3 ajoute les deux autres formes possibles
        dans l'application : une visite à case cochée sans DI (anomalie réglée sur place) et une DI liée à
        une visite déjà verrouillée (Clôturé administrativement avant la DI), que l'application ne marque
        donc pas (§14.6, écart retenu)."""
        gamme_s3 = scenarios_demo()['suggestion_anomalies'][len('S3-'):]
        anomalies = [o for o in self.t['ordres_travail'] if o['anomalie_constatee'] == '1' and o['gamme_id'] != gamme_s3]
        self.assertTrue(2 <= len(anomalies) <= 3, [o['id'] for o in anomalies])
        statuts = []
        for ot in anomalies:
            self.assertEqual(ot['origine'], 'préventif', ot['id'])
            liees = [d for d in self.t['demandes'] if d['ot_origine_id'] == ot['id']]
            self.assertEqual(len(liees), 1, ot['id'])
            statuts.append(liees[0]['statut'])
            if liees[0]['statut'] == 'Acceptée':
                correctif = self.ot_par_id[liees[0]['ot_id']]
                self.assertTrue(correctif['type'].startswith('correctif'))
                self.assertTrue(correctif['statut'].startswith('Clôturé'))
        self.assertIn('Acceptée', statuts)
        self.assertIn('Nouvelle', statuts)
        for demande in self.t['demandes']:
            if demande['ot_origine_id']:
                origine = self.ot_par_id[demande['ot_origine_id']]
                if origine['anomalie_constatee'] != '1':          # seulement la DI liée « après le verrou » du lot 3 bis
                    self.assertEqual(origine['gamme_id'], gamme_s3, demande['id'])
                    self.assertEqual(origine['statut'], 'Clôturé administrativement', demande['id'])
                    self.assertLessEqual(origine['date_cloture_admin'], demande['date_heure'], demande['id'])
        origines = {d['ot_origine_id'] for d in self.t['demandes']}
        sans_di = [o for o in self.t['ordres_travail'] if o['anomalie_constatee'] == '1' and o['id'] not in origines]
        self.assertEqual([(o['origine'], o['gamme_id']) for o in sans_di], [('préventif', gamme_s3)])

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
        for article in self.t['articles']:          # point de commande SAISI sur les articles gérés (D23)
            self.assertRegex(article['point_commande'], r'^\d+(\.\d+)?$', article['id'])
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

    def test_mouvements_de_tous_les_types_sur_13_mois(self):
        mouvements = self.t['mouvements_stock']
        self.assertEqual({m['type'] for m in mouvements}, {'entrée', 'sortie', 'retour', 'inventaire'})
        ecarts = [m for m in mouvements if m['type'] == 'inventaire' and m['commentaire'].startswith('Inventaire annuel')]
        self.assertGreaterEqual(len(ecarts), len(self.t['articles']))
        for genre in ('sortie', 'entrée'):
            dates = sorted(jour(m['date']) for m in mouvements if m['type'] == genre)
            self.assertGreaterEqual((dates[-1] - dates[0]).days, 330, genre)
        recues = sorted(jour(a['date_reception']) for a in self.t['achats'] if a['statut'] == 'reçue')
        self.assertGreaterEqual((recues[-1] - recues[0]).days, 300)

    def test_achats_coherents_avec_les_entrees(self):
        statuts = [a['statut'] for a in self.t['achats']]
        self.assertGreaterEqual(statuts.count('reçue'), 10)
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

    def test_po02_sept_fuites_de_garniture_a_58_jours(self):
        # 13 mois d'historique : fuites il y a 19, 77, 135, 193, 251, 309 et 367 jours.
        fuites = [o for o in self.ot_de('PO-02') if o['type'].startswith('correctif') and o['cause_code'] == 'C01']
        self.assertEqual(len(fuites), 7)
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

    def test_causes_frequentes_equipements_a_5_cas_et_plus(self):
        """§14.5 : PO-02 a au moins 5 fuites (S01) clôturées avec cause, au moins deux causes, la garniture
        usée (C01) en tête ; un autre équipement (CP-01, échauffements S04) atteint aussi 5 cas."""
        fuites = cas_causes_frequentes(self.t, {self.equipement['PO-02']['id']}, 'S01')
        self.assertGreaterEqual(len(fuites), MINIMUM_CAUSES)
        causes = {}
        for ot in fuites:
            causes[ot['cause_code']] = causes.get(ot['cause_code'], 0) + 1
        self.assertGreaterEqual(len(causes), 2, causes)
        self.assertEqual(max(causes, key=causes.get), 'C01', causes)
        self.assertGreater(causes['C01'], max(n for code, n in causes.items() if code != 'C01'))
        libelles = {c['code']: c['libelle'] for c in self.t['codes_defaillance']}
        self.assertEqual(libelles['C01'], 'Garniture usée')
        echauffements = cas_causes_frequentes(self.t, {self.equipement['CP-01']['id']}, 'S04')
        self.assertGreaterEqual(len(echauffements), MINIMUM_CAUSES)
        a_5_cas = set()
        for equipement in self.t['equipements']:
            for symptome in {o['symptome_code'] for o in self.ot_de(equipement['repere']) if o['symptome_code']}:
                if len(cas_causes_frequentes(self.t, {equipement['id']}, symptome)) >= MINIMUM_CAUSES:
                    a_5_cas.add(equipement['repere'])
        self.assertGreaterEqual(len(a_5_cas), 2, a_5_cas)

    def test_causes_frequentes_portee_modele_et_cas_insuffisants(self):
        """§14.5 : CV-03 a moins de 5 arrêts intempestifs (S05) à lui seul, mais au moins 5 avec CV-02,
        même marque et même modèle ; PO-03 (modèle unique) a de 1 à 4 cas de bruit (S02)."""
        cv03 = self.equipement['CV-03']
        self.assertEqual((cv03['marque'], cv03['modele']), (self.equipement['CV-02']['marque'], self.equipement['CV-02']['modele']))
        propres = cas_causes_frequentes(self.t, {cv03['id']}, 'S05')
        self.assertTrue(1 <= len(propres) < MINIMUM_CAUSES, len(propres))
        modele = cas_causes_frequentes(self.t, equipements_du_modele(self.t, cv03['id']), 'S05')
        self.assertGreaterEqual(len(modele), MINIMUM_CAUSES)
        po03 = self.equipement['PO-03']
        self.assertEqual(equipements_du_modele(self.t, po03['id']), {po03['id']})
        bruits = cas_causes_frequentes(self.t, {po03['id']}, 'S02')
        self.assertTrue(1 <= len(bruits) < MINIMUM_CAUSES, len(bruits))

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
        self.assertGreaterEqual(len(preventifs), 60)
        # Type selon le déclencheur (§14.3) : conditionnel pour une gamme seuil, systématique sinon.
        declencheurs = {g['id']: g['declencheur'] for g in self.t['gammes']}
        for o in preventifs:
            attendu = 'préventif conditionnel' if declencheurs[o['gamme_id']] == 'seuil' else 'préventif systématique'
            self.assertEqual(o['type'], attendu, o['id'])
        for o in preventifs:
            copiees = sorted(operations_par_ot[o['id']], key=lambda x: int(x['ordre']))
            modele = sorted(operations_par_gamme[o['gamme_id']], key=lambda x: int(x['ordre']))
            self.assertEqual([c['operation'] for c in copiees], [m['operation'] for m in modele], o['id'])
            if o['statut'].startswith('Clôturé'):
                self.assertTrue(all(c['fait'] == '1' for c in copiees), o['id'])

    # -- état à la date de référence

    def test_demandes_a_la_date_de_reference(self):
        statuts = [d['statut'] for d in self.t['demandes']]
        # 4 DI d'opérateurs + la DI liée à l'anomalie d'un préventif récent
        self.assertTrue(4 <= statuts.count('Nouvelle') <= 5, statuts.count('Nouvelle'))
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

    def test_gammes_coherentes_avec_les_preventifs_realises(self):
        """Dernière réalisation = date de fin du dernier préventif clôturé de la gamme ; échéance d'une
        gamme date = dernière réalisation + périodicité ; préventifs réalisés sur les 13 mois, sauf pour les
        deux gammes RÉCENTES du lot 3 bis (§16.8, mises en place cet été), qui ont au moins 5 visites."""
        scenarios = scenarios_demo()
        recentes = {scenarios['suggestion_anomalies'][len('S3-'):], scenarios['suggestion_refus_criticite_a']}
        for gamme in self.t['gammes']:
            clotures = sorted((o for o in self.t['ordres_travail']
                               if o['gamme_id'] == gamme['id'] and o['statut'].startswith('Clôturé')),
                              key=lambda o: o['date_fin'])
            self.assertTrue(clotures, gamme['id'])
            self.assertEqual(clotures[-1]['date_fin'][:10], gamme['derniere_realisation'], gamme['id'])
            if gamme['declencheur'] == 'date':
                attendue = jour(gamme['derniere_realisation']) + timedelta(days=int(gamme['periodicite_jours']))
                self.assertEqual(gamme['prochaine_echeance'], attendue.isoformat(), gamme['id'])
                if gamme['id'] in recentes:
                    self.assertGreaterEqual(len(clotures), 5, gamme['id'])
                elif int(gamme['periodicite_jours']) <= 90:
                    self.assertGreaterEqual((jour(clotures[-1]['date_fin']) - jour(clotures[0]['date_fin'])).days, 270,
                                            gamme['id'])

    def test_gamme_seuil_sur_un_point_de_mesure_sous_le_seuil(self):
        """§14.3 : gamme seuil avec son compteur de mesure ; dernier relevé SOUS le seuil (pas échue) ;
        réalisée dans l'historique après un relevé au-dessus du seuil (OT préventif conditionnel)."""
        seuils = [g for g in self.t['gammes'] if g['declencheur'] == 'seuil']
        self.assertEqual(len(seuils), 1)
        gamme = seuils[0]
        compteur = [c for c in self.t['compteurs'] if c['id'] == gamme['compteur_id']][0]
        self.assertEqual(compteur['equipement_id'], gamme['equipement_id'])
        self.assertNotIn(compteur['id'], {g['compteur_id'] for g in self.t['gammes'] if g is not gamme})
        releves = sorted((r for r in self.t['releves'] if r['compteur_id'] == compteur['id']), key=lambda r: (r['date'], r['id']))
        self.assertGreaterEqual(len(releves), 13)
        self.assertLess(float(releves[-1]['valeur']), float(gamme['seuil']))
        declencheurs = [r for r in releves if float(r['valeur']) >= float(gamme['seuil'])]
        self.assertTrue(declencheurs)
        self.assertLess(declencheurs[-1]['date'], gamme['derniere_realisation'])
        self.assertEqual(gamme['releve_derniere_realisation'], declencheurs[-1]['valeur'])
        ordres = [o for o in self.t['ordres_travail'] if o['gamme_id'] == gamme['id']]
        self.assertTrue(ordres)
        for o in ordres:
            self.assertEqual(o['type'], 'préventif conditionnel')
            self.assertTrue(o['statut'].startswith('Clôturé'))

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
# Identifiants de scénario (tests/fixtures/demo-scenarios.json, §14.8)
# ---------------------------------------------------------------------------

class TestScenariosDemo(unittest.TestCase):
    """Le fichier écrit est celui du générateur, et chaque clé désigne une ligne qui a la propriété
    annoncée par la docstring de outils/generer_demo.py."""

    @classmethod
    def setUpClass(cls):
        cls.s = scenarios_demo()
        cls.t = {table: lignes_propres(DOSSIER_DEMO, table) for table in TABLES}
        cls.par_id = {table: {ligne['cle' if table == 'parametres' else 'id']: ligne for ligne in cls.t[table]}
                      for table in TABLES}
        cls.repere = {e['id']: e['repere'] for e in cls.t['equipements']}

    def ligne(self, table, cle):
        self.assertIn(cle, self.s)
        self.assertIn(self.s[cle], self.par_id[table], cle)
        return self.par_id[table][self.s[cle]]

    def ot(self, cle):
        return self.ligne('ordres_travail', cle)

    def di(self, cle):
        return self.ligne('demandes', cle)

    def gamme(self, cle):
        return self.ligne('gammes', cle)

    def ot_ouverts(self, equipement_id=None):
        return [o for o in self.t['ordres_travail'] if est_ouvert(o)
                and (equipement_id is None or o['equipement_id'] == equipement_id)]

    def releves(self, compteur_id):
        return sorted((r for r in self.t['releves'] if r['compteur_id'] == compteur_id), key=lambda r: (r['date'], r['id']))

    # -- le fichier

    def test_fichier_identique_a_celui_du_generateur(self):
        generateur = charger_generateur()
        ctx = generateur.construire_jeu()
        scenarios = generateur.scenarios_du_jeu(ctx)
        generateur.verifier_scenarios(ctx, scenarios)            # lève ErreurCoherence en cas de défaut
        self.assertEqual(FICHIER_SCENARIOS.read_bytes(), generateur.texte_scenarios(scenarios).encode('utf-8'),
                         'tests/fixtures/demo-scenarios.json : relancer py outils/generer_demo.py')
        texte = FICHIER_SCENARIOS.read_bytes().decode('utf-8')
        self.assertFalse(texte.startswith('﻿'))
        self.assertTrue(texte.startswith('{\n  "'), 'JSON indenté')
        self.assertEqual(list(json.loads(texte)), sorted(json.loads(texte)), 'clés triées')
        # Chaque clé est documentée dans la docstring du générateur, et réciproquement.
        self.assertEqual(sorted(generateur.cles_documentees()), sorted(self.s))
        for cle, valeur in self.s.items():          # texte, liste triée, ou (lot 3 bis, ce seul rôle) petit objet de textes
            self.assertTrue(isinstance(valeur, str) or (isinstance(valeur, list) and valeur == sorted(valeur))
                            or (cle == 'suggestion_sous_seuil' and isinstance(valeur, dict)
                                and all(isinstance(v, str) for v in valeur.values())), cle)

    def test_cles_minimales_demandees(self):
        for cle in ('gamme_mensuelle_echue', 'gamme_compteur_echue', 'gamme_seuil', 'kit_garniture',
                    'articles_sous_point_commande', 'preventif_anomalie', 'di_anomalie_nouvelle', 'causes_equipement',
                    'causes_equipement_symptome', 'causes_modele', 'causes_modele_symptome', 'causes_insuffisantes',
                    'causes_insuffisantes_symptome', 'ot_p1_ouvert', 'ot_en_retard', 'technicien_br_valide',
                    'technicien_br_echue', 'equipement_br'):
            self.assertIn(cle, self.s)
        for statut in ('cree', 'prepare', 'planifie', 'en_cours', 'en_attente', 'cloture_technique',
                       'cloture_administratif', 'annule'):
            self.assertIn('ot_statut_' + statut, self.s)
        for statut in ('nouvelle', 'acceptee', 'regroupee', 'differee', 'refusee'):
            self.assertIn('di_statut_' + statut, self.s)
        # Rôles ajoutés par le lot 3 (ARCHITECTURE.md §15.12) et le lot 3 bis (§16.8)
        for cle in ROLES_LOT3 + ROLES_LOT3BIS:
            self.assertIn(cle, self.s)

    # -- OT

    def test_ot_par_statut(self):
        attendus = {'ot_statut_cree': 'Créé', 'ot_statut_prepare': 'Préparé', 'ot_statut_planifie': 'Planifié',
                    'ot_statut_en_cours': 'En cours', 'ot_statut_en_attente': 'En attente',
                    'ot_statut_cloture_technique': 'Clôturé techniquement',
                    'ot_statut_cloture_administratif': 'Clôturé administrativement', 'ot_statut_annule': 'Annulé'}
        for cle, statut in attendus.items():
            self.assertEqual(self.ot(cle)['statut'], statut, cle)
        self.assertEqual(self.ot('ot_statut_cree')['gamme_id'], self.s['gamme_compteur_echue'])
        prepare = self.ot('ot_statut_prepare')
        self.assertTrue(prepare['type'].startswith('correctif'))
        self.assertLess(prepare['date_prevue'], DATE_REFERENCE)
        planifie = self.ot('ot_statut_planifie')
        self.assertTrue(planifie['type'].startswith('correctif') and planifie['technicien_id'])
        self.assertGreaterEqual(planifie['date_prevue'], DATE_REFERENCE)
        en_cours = self.ot('ot_statut_en_cours')
        self.assertEqual((en_cours['priorite'], en_cours['origine']), ('P2', 'DI'))
        attente = self.ot('ot_statut_en_attente')
        self.assertRegex(attente['motif_attente'], r'(?i)pièce')
        self.assertLess(attente['date_prevue'], DATE_REFERENCE)
        self.assertGreaterEqual(len(self.ot('ot_statut_annule')['motif_annulation']), 10)
        techniques = [o for o in self.t['ordres_travail'] if o['statut'] == 'Clôturé techniquement']
        self.assertEqual(self.s['ot_statut_cloture_technique'],
                         max(techniques, key=lambda o: (o['date_cloture_tech'], o['id']))['id'])
        administratifs = [o for o in self.t['ordres_travail'] if o['statut'] == 'Clôturé administrativement']
        self.assertEqual(self.s['ot_statut_cloture_administratif'],
                         max(administratifs, key=lambda o: (o['date_cloture_admin'], o['id']))['id'])

    def test_ot_p1_ouvert_et_ot_en_retard(self):
        p1 = self.ot('ot_p1_ouvert')
        self.assertEqual((p1['priorite'], p1['statut'], self.repere[p1['equipement_id']]), ('P1', 'En cours', 'CP-01'))
        self.assertEqual([o['id'] for o in self.ot_ouverts() if o['priorite'] == 'P1'], [p1['id']])
        retard = sorted(o['id'] for o in self.ot_ouverts() if o['date_prevue'] and o['date_prevue'] < DATE_REFERENCE)
        self.assertEqual(self.s['ot_en_retard'], retard)
        self.assertTrue({self.s['ot_statut_prepare'], self.s['ot_statut_en_attente'], self.s['ot_preventif_ouvert']}
                        <= set(retard))
        for identifiant in retard:
            self.assertNotEqual(self.par_id['ordres_travail'][identifiant]['statut'], 'Annulé')

    def test_ot_remarquables(self):
        regroupe = self.ot('ot_en_cours_regroupe')
        self.assertEqual(regroupe['statut'], 'En cours')
        self.assertEqual([o['id'] for o in self.ot_ouverts(regroupe['equipement_id'])], [regroupe['id']])
        regroupee = self.di('di_statut_regroupee')
        self.assertEqual((regroupee['ot_id'], regroupee['equipement_id']), (regroupe['id'], regroupe['equipement_id']))
        ouvert = self.ot('ot_preventif_ouvert')
        self.assertEqual((ouvert['origine'], ouvert['statut'], ouvert['technicien_id']), ('préventif', 'Planifié', 'TEC-0004'))
        self.assertLess(ouvert['date_prevue'], DATE_REFERENCE)
        preventifs = [o for o in self.t['ordres_travail'] if o['origine'] == 'préventif' and o['statut'].startswith('Clôturé')]
        self.assertEqual(self.s['ot_preventif_cloture'], min(preventifs, key=lambda o: (o['date_creation'], o['id']))['id'])
        fuite = self.ot('ot_fuite_garniture_po02')
        self.assertEqual((self.repere[fuite['equipement_id']], fuite['symptome_code'], fuite['cause_code']),
                         ('PO-02', 'S01', 'C01'))
        self.assertTrue(fuite['type'].startswith('correctif') and fuite['statut'].startswith('Clôturé'))
        pieces = [(p['article_id'], p['quantite_prevue']) for p in self.t['ot_pieces'] if p['ot_id'] == fuite['id']]
        self.assertEqual(pieces, [(self.s['kit_garniture'], '1')])
        # La dernière fuite de garniture USÉE (C01) de PO-02 ; l'OT de scénario du lot 6 (désalignement, C11) est
        # plus récent, voulu ainsi (TestDemoLot6).
        po02 = [o for o in self.t['ordres_travail'] if o['equipement_id'] == fuite['equipement_id'] and o['cause_code'] == 'C01']
        self.assertEqual(max(po02, key=lambda o: (o['date_creation'], o['id']))['id'], fuite['id'])
        acceptee = self.di('di_statut_acceptee')
        self.assertEqual(self.s['ot_de_di_acceptee'], acceptee['ot_id'])
        self.assertEqual(self.ot('ot_de_di_acceptee')['di_id'], acceptee['id'])

    def test_preventifs_avec_anomalie_et_leur_di(self):
        preventif = self.ot('preventif_anomalie')
        demande = self.di('di_anomalie_acceptee')
        correctif = self.ot('ot_correctif_anomalie')
        self.assertEqual((preventif['origine'], preventif['anomalie_constatee']), ('préventif', '1'))
        self.assertTrue(preventif['statut'].startswith('Clôturé'))
        self.assertEqual((demande['ot_origine_id'], demande['statut'], demande['ot_id']),
                         (preventif['id'], 'Acceptée', correctif['id']))
        self.assertTrue(correctif['type'].startswith('correctif') and correctif['statut'].startswith('Clôturé'))
        self.assertEqual(correctif['symptome_code'], demande['symptome_code'])
        nouvelle = self.ot('preventif_anomalie_nouvelle')
        demande = self.di('di_anomalie_nouvelle')
        self.assertEqual((nouvelle['origine'], nouvelle['anomalie_constatee']), ('préventif', '1'))
        self.assertEqual((demande['ot_origine_id'], demande['statut'], demande['ot_id']), (nouvelle['id'], 'Nouvelle', ''))
        # Hors la gamme de la suggestion S3 du lot 3 bis (case cochée sans DI, voir TestDemoLot3bis).
        gamme_s3 = self.s['suggestion_anomalies'][len('S3-'):]
        self.assertEqual(sorted(o['id'] for o in self.t['ordres_travail']
                                if o['anomalie_constatee'] == '1' and o['gamme_id'] != gamme_s3),
                         sorted([preventif['id'], nouvelle['id']]))

    # -- DI

    def test_di_par_statut_et_remarquables(self):
        for cle, statut in (('di_statut_nouvelle', 'Nouvelle'), ('di_statut_acceptee', 'Acceptée'),
                            ('di_statut_regroupee', 'Regroupée'), ('di_statut_differee', 'Différée'),
                            ('di_statut_refusee', 'Refusée')):
            self.assertEqual(self.di(cle)['statut'], statut, cle)
        self.assertGreaterEqual(len(self.di('di_statut_differee')['motif_decision']), 10)
        self.assertGreaterEqual(len(self.di('di_statut_refusee')['motif_decision']), 10)
        self.assertEqual([d['id'] for d in self.t['demandes'] if d['statut'] == 'Refusée'], [self.s['di_statut_refusee']])
        self.assertEqual(self.s['di_nouvelles'], sorted(d['id'] for d in self.t['demandes'] if d['statut'] == 'Nouvelle'))
        criticite = {e['id']: e['criticite'] for e in self.t['equipements']}
        securite = self.di('di_securite')
        self.assertEqual((securite['statut'], securite['impact']), ('Nouvelle', 'sécurité'))
        p4 = self.di('di_nouvelle_p4')
        self.assertEqual((p4['statut'], criticite[p4['equipement_id']], p4['impact']), ('Nouvelle', 'C', 'gêne'))
        sans_ot = self.di('di_nouvelle_sans_ot_ouvert')
        self.assertEqual((sans_ot['statut'], criticite[sans_ot['equipement_id']], sans_ot['impact']), ('Nouvelle', 'C', 'gêne'))
        self.assertEqual(self.ot_ouverts(sans_ot['equipement_id']), [])
        degradee = self.di('di_nouvelle_degradee')
        self.assertEqual((degradee['statut'], degradee['impact'], degradee['demandeur']), ('Nouvelle', 'dégradé', 'Sarah Colin'))
        for cle in ('di_securite', 'di_nouvelle_p4', 'di_nouvelle_sans_ot_ouvert', 'di_nouvelle_degradee',
                    'di_anomalie_nouvelle'):
            self.assertIn(self.s[cle], self.s['di_nouvelles'], cle)

    def test_di_historiques(self):
        premiere = self.di('di_plus_ancienne')
        self.assertEqual(premiere['id'], min(d['id'] for d in self.t['demandes']))
        self.assertEqual(premiere['id'], self.t['demandes'][0]['id'])
        self.assertEqual(premiere['statut'], 'Acceptée')
        self.assertTrue(premiere['date_decision'])
        acceptees = [d for d in self.t['demandes'] if d['statut'] == 'Acceptée' and d['ot_id']]
        self.assertEqual([self.s['di_statut_acceptee'], self.s['di_acceptee_autre']], [d['id'] for d in acceptees[:2]])
        causes = self.di('di_causes_equipement')
        self.assertEqual((causes['equipement_id'], causes['symptome_code']),
                         (self.s['causes_equipement'], self.s['causes_equipement_symptome']))
        self.assertTrue(self.par_id['ordres_travail'][causes['ot_id']]['statut'].startswith('Clôturé'))
        insuffisantes = self.di('di_causes_insuffisantes')
        self.assertEqual((insuffisantes['equipement_id'], insuffisantes['symptome_code']),
                         (self.s['causes_insuffisantes'], self.s['causes_insuffisantes_symptome']))
        self.assertEqual(self.di('di_sans_symptome_code')['symptome_code'], '')

    # -- préventif, compteurs

    def test_gammes_et_compteurs(self):
        mensuelle = self.gamme('gamme_mensuelle_echue')
        self.assertEqual((mensuelle['declencheur'], mensuelle['periodicite_jours']), ('date', '30'))
        self.assertLessEqual(jour(mensuelle['prochaine_echeance']) - timedelta(days=int(mensuelle['avance_jours'])),
                             JOUR_REFERENCE)
        ouvertes = {o['gamme_id'] for o in self.ot_ouverts() if o['gamme_id']}
        self.assertNotIn(mensuelle['id'], ouvertes)
        for cle, echue in (('gamme_compteur_echue', True), ('gamme_compteur_sans_ot', False)):
            gamme = self.gamme(cle)
            self.assertEqual(gamme['declencheur'], 'compteur')
            dernier = float(self.releves(gamme['compteur_id'])[-1]['valeur'])
            ecart = dernier - float(gamme['releve_derniere_realisation'] or 0)
            self.assertEqual(ecart >= float(gamme['periodicite_unites']), echue, cle)
            self.assertEqual(gamme['id'] in ouvertes, echue, cle)
        seuil = self.gamme('gamme_seuil')
        self.assertEqual((seuil['declencheur'], seuil['compteur_id']), ('seuil', self.s['compteur_seuil']))
        self.assertLess(float(self.releves(seuil['compteur_id'])[-1]['valeur']), float(seuil['seuil']))
        self.assertNotIn(seuil['id'], ouvertes)
        sans_constat = self.gamme('gamme_sans_constat')
        self.assertEqual(self.repere[sans_constat['equipement_id']], 'VE-01')
        clotures = [o for o in self.t['ordres_travail'] if o['gamme_id'] == sans_constat['id'] and o['statut'].startswith('Clôturé')]
        self.assertGreaterEqual(len(clotures), 5)
        for o in clotures:
            self.assertRegex(o['compte_rendu'], r'(?i)ras|rien à signaler')
        horaire = self.ligne('compteurs', 'compteur_horaire')
        self.assertEqual((horaire['unite'], self.repere[horaire['equipement_id']]), ('h', 'CP-01'))
        self.assertEqual(self.ligne('compteurs', 'compteur_seuil')['equipement_id'], seuil['equipement_id'])

    # -- magasin

    def test_articles_et_achats(self):
        kit = self.ligne('articles', 'kit_garniture')
        self.assertEqual(kit['designation'], 'Kit garniture mécanique PO-02')
        self.assertGreaterEqual(float(kit['stock']), 2)
        sous = sorted(a['id'] for a in self.t['articles'] if float(a['stock']) <= float(a['point_commande']))
        self.assertEqual(self.s['articles_sous_point_commande'], sous)
        self.assertEqual(len(sous), 3)
        for cle, statut in (('achat_statut_demandee', 'demandée'), ('achat_statut_commandee', 'commandée'),
                            ('achat_statut_recue', 'reçue')):
            self.assertEqual(self.ligne('achats', cle)['statut'], statut, cle)
        recu = self.ligne('achats', 'achat_statut_recue')
        entrees = [m for m in self.t['mouvements_stock']
                   if m['type'] == 'entrée' and m['commentaire'] == 'Réception de la commande ' + recu['id']]
        self.assertEqual(len(entrees), 1)
        self.assertEqual((entrees[0]['article_id'], entrees[0]['quantite']), (recu['article_id'], recu['quantite']))

    # -- parc, techniciens

    def test_parc_et_habilitations(self):
        self.assertEqual(self.ligne('equipements', 'equipement_br')['habilitation_requise'], 'BR')
        unique = self.ligne('equipements', 'equipement_panne_unique')
        correctifs = [o for o in self.t['ordres_travail'] if o['equipement_id'] == unique['id'] and o['type'].startswith('correctif')]
        self.assertEqual(len(correctifs), 1)

        def br(technicien):
            return [h for h in self.t['habilitations'] if h['technicien_id'] == technicien and h['intitule'] == 'BR']

        valide = br(self.ligne('techniciens', 'technicien_br_valide')['id'])
        self.assertTrue(any(h['date_obtention'] <= DATE_REFERENCE <= h['date_echeance'] for h in valide))
        echue = br(self.ligne('techniciens', 'technicien_br_echue')['id'])
        self.assertTrue(echue)
        self.assertTrue(all(h['date_echeance'] < DATE_REFERENCE for h in echue))

    # -- causes fréquentes

    def test_causes_frequentes(self):
        t = self.t
        for cle in ('causes_equipement', 'causes_equipement_2'):
            cas = cas_causes_frequentes(t, {self.s[cle]}, self.s[cle + '_symptome'])
            self.assertGreaterEqual(len(cas), MINIMUM_CAUSES, cle)
        self.assertEqual(self.repere[self.s['causes_equipement']], 'PO-02')
        self.assertEqual(self.s['causes_equipement_symptome'], 'S01')
        modele = self.s['causes_modele']
        propres = cas_causes_frequentes(t, {modele}, self.s['causes_modele_symptome'])
        tous = cas_causes_frequentes(t, equipements_du_modele(t, modele), self.s['causes_modele_symptome'])
        self.assertTrue(len(propres) < MINIMUM_CAUSES <= len(tous), (len(propres), len(tous)))
        insuffisant = self.s['causes_insuffisantes']
        tous = cas_causes_frequentes(t, equipements_du_modele(t, insuffisant), self.s['causes_insuffisantes_symptome'])
        self.assertTrue(1 <= len(tous) < MINIMUM_CAUSES, len(tous))
        symptomes = {c['code'] for c in t['codes_defaillance'] if c['famille'] == 'symptôme'}
        for cle in ('causes_equipement', 'causes_equipement_2', 'causes_modele', 'causes_insuffisantes'):
            self.assertIn(self.s[cle], self.par_id['equipements'], cle)
            self.assertIn(self.s[cle + '_symptome'], symptomes, cle)


# ---------------------------------------------------------------------------
# Lot 3 : contrôles, planning, pannes et journal (ARCHITECTURE.md §15.12, D49)
# ---------------------------------------------------------------------------

# Champs modifiés que Donnees.modifier inscrit avant « — » pour chaque statut atteint (ordre du schéma,
# ordres-ecritures.js : date_debut posée au premier démarrage, motif d'attente, dates de clôture).
CHAMPS_DU_PASSAGE = {'Préparé': 'statut', 'Planifié': 'statut', 'En attente': 'statut, motif_attente',
                     'Clôturé techniquement': 'statut, date_cloture_tech',
                     'Clôturé administrativement': 'statut, date_cloture_admin'}


class TestDemoLot3(unittest.TestCase):
    """Le jeu de démo complété pour le lot 3 : chaque rôle a la propriété annoncée, recalculée ici en
    Python avec les règles du contrat (§15.3, §15.5, §15.7), sans passer par le générateur."""

    @classmethod
    def setUpClass(cls):
        cls.s = scenarios_demo()
        cls.t = {table: lignes_propres(DOSSIER_DEMO, table) for table in TABLES}
        cls.ot_par_id = {o['id']: o for o in cls.t['ordres_travail']}
        cls.di_par_id = {d['id']: d for d in cls.t['demandes']}
        cls.equipement_par_id = {e['id']: e for e in cls.t['equipements']}
        cls.stock = {a['id']: float(a['stock']) for a in cls.t['articles']}

    def ot(self, role):
        self.assertIn(self.s[role], self.ot_par_id, role)
        return self.ot_par_id[self.s[role]]

    def pieces_manquantes(self, ot):
        """Pièces prévues dont le stock ne suffit pas (RG3 ; aucune sortie n'a encore eu lieu pour l'OT)."""
        return [p for p in self.t['ot_pieces']
                if p['ot_id'] == ot['id'] and float(p['quantite_prevue']) > self.stock[p['article_id']]]

    def pannes_recentes(self):
        return [o for o in self.t['ordres_travail'] if est_panne(o) and date_de_panne(self.t, o) >= DEBUT_3_MOIS]

    # -- contrôles réglementaires (§15.7)

    def test_controles_dans_les_quatre_statuts_a_la_date_de_reference(self):
        controles = {c['id']: c for c in self.t['controles_reglementaires']}
        statuts = {identifiant: statut_controle(c, JOUR_REFERENCE) for identifiant, c in controles.items()}
        attendus = {'controle_en_retard': 'en retard', 'controle_observations': 'observations à lever',
                    'controle_a_planifier': 'à planifier', 'controle_a_jour': 'à jour'}
        for role, statut in attendus.items():
            self.assertIn(self.s[role], controles, role)
            self.assertEqual(statuts[self.s[role]], statut, role)
        self.assertEqual(set(statuts.values()), set(attendus.values()))
        # « à planifier » par sa date (connue, dans les 30 jours), pas faute de date
        prochaine = jour(controles[self.s['controle_a_planifier']]['prochaine_date'])
        self.assertTrue(0 <= (prochaine - JOUR_REFERENCE).days <= 30, prochaine)
        for controle in controles.values():          # prochaine date = dernière + périodicité (mois)
            attendue = ajouter_mois(jour(controle['derniere_date']), int(controle['periodicite_mois']))
            self.assertEqual(controle['prochaine_date'], attendue.isoformat(), controle['id'])

    def test_controles_textes_et_periodicites_reglementaires(self):
        controles = self.t['controles_reglementaires']

        def seul(mot):
            trouves = [c for c in controles if mot in c['nature'].lower()]
            self.assertEqual(len(trouves), 1, mot)
            return trouves[0]

        chariot = seul('chariot')                    # VGP des chariots élévateurs : 6 mois (art. 23 a)
        self.assertEqual((chariot['periodicite_mois'], chariot['texte_reference']),
                         ('6', 'Arrêté du 1er mars 2004 (VGP), art. 23'))
        self.assertEqual(chariot['id'], self.s['controle_en_retard'])
        self.assertEqual(seul('électrique')['texte_reference'],
                         'Code du travail, art. R4226-16 ; arrêté du 26 décembre 2011')
        self.assertEqual(seul('pont roulant')['periodicite_mois'], '12')
        self.assertEqual(seul('réservoir')['periodicite_mois'], '36')

    # -- planning des 4 semaines (§15.5)

    def test_planning_des_quatre_semaines_avec_une_surcharge(self):
        grille = [o for o in self.t['ordres_travail']
                  if est_ouvert(o) and o['technicien_id'] and lundi_du_planning(o['date_prevue'])]
        planifies = [o for o in grille if o['statut'] == 'Planifié']
        self.assertEqual({o['technicien_id'] for o in planifies}, {t['id'] for t in self.t['techniciens']})
        self.assertEqual({lundi_du_planning(o['date_prevue']) for o in planifies}, set(LUNDIS_PLANNING))
        self.assertTrue(1 <= len([o for o in grille if o['statut'] == 'En cours']) <= 2)
        for ot in grille:
            self.assertGreater(float(ot['temps_prevu_h'] or 0), 0, ot['id'])
        for ot in planifies:                          # RG3 : un OT planifié a ses pièces en stock
            self.assertEqual(self.pieces_manquantes(ot), [], ot['id'])
        capacites = {t['id']: float(t['capacite_h_semaine']) for t in self.t['techniciens']}
        surcharges = sorted(cle for cle, heures in charges_du_planning(self.t).items() if heures > capacites[cle[0]])
        self.assertEqual(surcharges, [(self.s['technicien_surcharge'], self.s['semaine_surcharge'])])
        self.assertIn(self.s['semaine_surcharge'], [lundi.isoformat() for lundi in LUNDIS_PLANNING])

    def test_ot_prepares_a_planifier(self):
        a_planifier = [o['id'] for o in self.t['ordres_travail']
                       if o['statut'] == 'Préparé' and not (o['technicien_id'] and lundi_du_planning(o['date_prevue']))]
        self.assertTrue(3 <= len(a_planifier) <= 5, a_planifier)
        roles = ('ot_a_planifier', 'ot_a_planifier_br', 'ot_a_planifier_piece_manquante')
        self.assertEqual(len({self.s[role] for role in roles}), 3)
        for role in roles:
            ot = self.ot(role)
            self.assertIn(ot['id'], a_planifier, role)
            self.assertEqual(ot['technicien_id'], '', role)
            self.assertGreaterEqual(ot['date_prevue'], DATE_REFERENCE, role)      # pas en retard
            self.assertGreater(float(ot['temps_prevu_h'] or 0), 0, role)
        simple = self.ot('ot_a_planifier')          # se planifie sans refus ni avertissement
        self.assertEqual(self.equipement_par_id[simple['equipement_id']]['habilitation_requise'], '')
        self.assertEqual(self.pieces_manquantes(simple), [])
        br = self.ot('ot_a_planifier_br')            # scénario habilitation (RG8) : pièces en stock
        self.assertEqual(br['equipement_id'], self.s['equipement_br'])
        self.assertEqual(self.pieces_manquantes(br), [])
        manque = self.ot('ot_a_planifier_piece_manquante')     # refus RG3 au planning
        self.assertTrue(self.pieces_manquantes(manque))
        self.assertEqual(self.equipement_par_id[manque['equipement_id']]['habilitation_requise'], '')

    # -- pannes et historique des statuts (§15.3)

    def test_panne_cloturee_sans_duree_d_arret(self):
        ot = self.ot('panne_sans_duree')
        self.assertTrue(est_panne(ot), ot['id'])
        self.assertTrue(ot['statut'].startswith('Clôturé'), ot['statut'])
        self.assertEqual(ot['duree_arret_h'], '')

    def test_panne_qui_a_attendu_une_piece(self):
        ot = self.ot('panne_attente_pieces')
        self.assertTrue(est_panne(ot) and ot['statut'].startswith('Clôturé') and ot['duree_arret_h'], ot['id'])
        self.assertGreaterEqual(date_de_panne(self.t, ot), DEBUT_3_MOIS)
        self.assertTrue(sans_accents(ot['motif_attente']).startswith('piece'), ot['motif_attente'])
        actions = [action_metier(e['action']) for e in historique_ot(self.t, ot['id'])]
        self.assertIn('statut En cours → En attente : ' + ot['motif_attente'], actions)
        self.assertIn('statut En attente → En cours', actions)
        attente = attente_pieces_brute(self.t, ot)            # de quelques heures à quelques jours
        self.assertTrue(2 <= attente <= 7 * 24, attente)
        self.assertLess(attente, float(ot['duree_arret_h']))

    def test_historique_des_statuts_des_pannes_des_trois_derniers_mois(self):
        pannes = self.pannes_recentes()
        self.assertGreaterEqual(len(pannes), 6)
        identifiants = {o['id'] for o in pannes}
        for role in ('panne_attente_pieces', 'panne_sans_duree', 'ot_p1_ouvert'):
            self.assertIn(self.s[role], identifiants, role)
        for ot in pannes:
            with self.subTest(ot=ot['id']):
                self.verifier_historique(ot)

    def verifier_historique(self, ot):
        """Création (acceptation de la DI ou création de l'OT d'urgence) puis passages de statut, chacun
        depuis le statut précédent, horodatés comme les dates de l'OT ; fin sur le statut de l'OT."""
        entrees = historique_ot(self.t, ot['id'])
        self.assertTrue(entrees)
        creation = entrees[0]
        if ot['origine'] == 'DI':
            self.assertEqual((creation['action'], creation['profil']), ('création — acceptation de ' + ot['di_id'], 'Responsable'))
        else:
            self.assertEqual(creation['action'], "création — création de l'OT (%s)" % ot['origine'])
        self.assertEqual(creation['date_heure'], ot['date_creation'])
        statut, precedent, demarre = 'Créé', creation['date_heure'], False
        for entree in entrees[1:]:
            champs, _, metier = entree['action'].partition(' — ')
            correspondance = MOTIF_STATUT.fullmatch(metier)
            self.assertIsNotNone(correspondance, entree['action'])
            depart, arrivee, motif = correspondance.groups()
            self.assertEqual(depart, statut, entree['action'])
            self.assertGreater(entree['date_heure'], precedent, entree['id'])
            if arrivee == 'En cours':
                attendus = 'statut' if demarre else 'statut, date_debut'
            else:
                attendus = CHAMPS_DU_PASSAGE[arrivee]
            self.assertEqual(champs, 'modification : ' + attendus, entree['action'])
            technicien = arrivee in ('En cours', 'En attente', 'Clôturé techniquement')
            self.assertEqual(entree['profil'], 'Technicien ' + ot['technicien_id'] if technicien else 'Responsable',
                             entree['action'])
            if arrivee == 'En cours' and not demarre:
                self.assertEqual(entree['date_heure'], ot['date_debut'])
                demarre = True
            elif arrivee == 'En attente':
                self.assertEqual(motif, ot['motif_attente'])
            elif arrivee == 'Clôturé techniquement':
                self.assertEqual(entree['date_heure'], ot['date_cloture_tech'])
            elif arrivee == 'Clôturé administrativement':
                self.assertEqual(entree['date_heure'], ot['date_cloture_admin'])
            if arrivee not in ('Clôturé techniquement', 'Clôturé administrativement') and ot['date_fin']:
                self.assertLessEqual(entree['date_heure'], ot['date_fin'], entree['action'])
            statut, precedent = arrivee, entree['date_heure']
        self.assertEqual(statut, ot['statut'])
        self.assertLessEqual(precedent, MAINTENANT)
        # Côté DI : signalement à sa date, puis décision (acceptée ou regroupée) à sa date de décision.
        for demande in self.t['demandes']:
            if demande['ot_id'] != ot['id']:
                continue
            propres = sorted((l for l in self.t['journal'] if l['table'] == 'demandes' and l['id_ligne'] == demande['id']),
                             key=lambda l: (l['date_heure'], l['id']))
            signalee = 'création — demande signalée' + (' pendant ' + demande['ot_origine_id'] if demande['ot_origine_id'] else '')
            if demande['statut'] == 'Acceptée':
                decision = 'modification : statut, date_decision, ot_id — acceptée → ' + ot['id']
            else:
                decision = 'modification : statut, motif_decision, date_decision, ot_id — regroupée avec ' + ot['id']
            self.assertEqual([(l['date_heure'], l['action']) for l in propres],
                             [(demande['date_heure'], signalee), (demande['date_decision'], decision)], demande['id'])
            self.assertEqual(propres[1]['profil'], 'Responsable', demande['id'])

    def test_equipements_pour_le_calcul_a_la_main(self):
        identifiants = self.s['equipements_calcul_main']
        self.assertEqual(len(identifiants), 3)
        equipements = [self.equipement_par_id[identifiant] for identifiant in identifiants]
        self.assertIn('A', [e['criticite'] for e in equipements])
        pannes_vues = set()
        for equipement in equipements:
            self.assertGreater(float(equipement['heures_fonct_jour'] or 0), 0, equipement['repere'])
            self.assertEqual((equipement['statut'] != 'rebut', equipement['actif']), (True, '1'), equipement['repere'])
            pannes = [o['id'] for o in self.t['ordres_travail'] if o['equipement_id'] == equipement['id']
                      and est_panne(o) and DEBUT_12_MOIS <= date_de_panne(self.t, o) <= JOUR_REFERENCE]
            self.assertGreaterEqual(len(pannes), 2, equipement['repere'])
            pannes_vues.update(pannes)
        # Ensemble, ils couvrent les cas limites des indicateurs : panne non clôturée, sans durée, attente de pièce.
        for role in ('ot_p1_ouvert', 'panne_sans_duree', 'panne_attente_pieces'):
            self.assertIn(self.s[role], pannes_vues, role)


# ---------------------------------------------------------------------------
# Lot 3 bis : préventif suggéré (ARCHITECTURE.md §16.8, D62)
# ---------------------------------------------------------------------------

class TestDemoLot3bis(unittest.TestCase):
    """Le jeu de démo complété pour le lot 3 bis : chaque rôle a la propriété annoncée, prouvée par le calcul
    des règles du §16.3 écrit dans ce fichier (suggestions_ouvertes), à la date de référence, réglages par
    défaut (3 pannes, 5 visites, 12 mois), décisions du journal comprises. Aucun identifiant n'est écrit en
    dur : les clés viennent de demo-scenarios.json, les équipements sont reconnus par leur repère."""

    @classmethod
    def setUpClass(cls):
        cls.s = scenarios_demo()
        cls.t = {table: lignes_propres(DOSSIER_DEMO, table) for table in TABLES}
        cls.ouvertes = suggestions_ouvertes(cls.t)
        cls.ot_par_id = {o['id']: o for o in cls.t['ordres_travail']}
        cls.equipement_par_id = {e['id']: e for e in cls.t['equipements']}
        cls.gamme_par_id = {g['id']: g for g in cls.t['gammes']}
        cls.repere = {e['id']: e['repere'] for e in cls.t['equipements']}

    def suggestion(self, role, regle):
        """La suggestion ouverte dont la clé joue ce rôle, après contrôle de sa règle."""
        cle = self.s[role]
        self.assertIn(cle, self.ouvertes, role)
        self.assertEqual(self.ouvertes[cle]['regle'], regle, role)
        return self.ouvertes[cle]

    def gammes_actives(self, equipement_id):
        return [g for g in self.t['gammes'] if g['equipement_id'] == equipement_id and g['actif'] != '0']

    def test_roles_presents_au_format_des_cles(self):
        for role in ROLES_LOT3BIS:
            self.assertIn(role, self.s)
        for role in ('suggestion_creer', 'suggestion_revoir', 'suggestion_ignoree_revenue'):
            self.assertRegex(self.s[role], r'^S[12]-EQ-\d{4}-C\d{2}$', role)
        for role in ('suggestion_anomalies', 'suggestion_allonger'):
            self.assertRegex(self.s[role], r'^S[34]-GAM-\d{4}$', role)
        self.assertIn(self.s['suggestion_refus_criticite_a'], self.gamme_par_id)
        sous = self.s['suggestion_sous_seuil']
        self.assertEqual(sorted(sous), ['cause', 'equipement'])
        self.assertIn(sous['equipement'], self.equipement_par_id)
        self.assertIn(sous['cause'], {c['code'] for c in self.t['codes_defaillance'] if c['famille'] == 'cause'})

    def test_s1_creer_une_gamme_cv02(self):
        suggestion = self.suggestion('suggestion_creer', 'S1')
        self.assertEqual((self.repere[suggestion['equipement']], suggestion['cause']), ('CV-02', 'C04'))
        self.assertGreaterEqual(len(suggestion['faits']), SEUIL_PANNES)
        self.assertEqual(self.gammes_actives(suggestion['equipement']), [])

    def test_s2_revoir_le_preventif_po02(self):
        suggestion = self.suggestion('suggestion_revoir', 'S2')
        self.assertEqual((self.repere[suggestion['equipement']], suggestion['cause']), ('PO-02', 'C01'))
        self.assertGreaterEqual(len(suggestion['faits']), SEUIL_PANNES)
        self.assertTrue(self.gammes_actives(suggestion['equipement']))

    def test_s3_anomalies_par_la_case_et_par_une_di_liee(self):
        suggestion = self.suggestion('suggestion_anomalies', 'S3')
        gamme = self.gamme_par_id[self.s['suggestion_anomalies'][len('S3-'):]]
        equipement = self.equipement_par_id[gamme['equipement_id']]
        self.assertEqual((gamme['declencheur'], gamme['actif']), ('date', '1'))
        self.assertIn(equipement['criticite'], ('B', 'C'))            # de préférence pas A (§16.8)
        self.assertEqual((suggestion['sur'], len(suggestion['faits'])), (4, 2))
        visites = [self.ot_par_id[identifiant] for identifiant in suggestion['faits']]
        liees = {v['id']: [d for d in self.t['demandes'] if d['ot_origine_id'] == v['id']] for v in visites}
        par_case = [v for v in visites if v['anomalie_constatee'] == '1' and not liees[v['id']]]
        par_di = [v for v in visites if v['anomalie_constatee'] == '0' and liees[v['id']]]
        self.assertEqual((len(par_case), len(par_di)), (1, 1))
        self.assertIn('Anomalie constatée', par_case[0]['compte_rendu'])
        visite = par_di[0]
        demande = liees[visite['id']][0]
        # DI envoyée après la clôture administrative de la visite : l'OT, verrouillé, n'a pas été marqué (§14.6).
        self.assertEqual(visite['statut'], 'Clôturé administrativement')
        self.assertLessEqual(visite['date_cloture_admin'], demande['date_heure'])
        self.assertEqual(demande['date_heure'][:10], visite['date_fin'][:10])
        self.assertEqual(demande['equipement_id'], visite['equipement_id'])
        technicien = [t for t in self.t['techniciens'] if t['id'] == visite['technicien_id']][0]
        self.assertEqual(demande['demandeur'], '%s %s' % (technicien['prenom'], technicien['nom']))
        self.assertTrue(demande['symptome'] and demande['impact'] in ('sécurité', 'arrêt', 'dégradé', 'gêne'))
        self.assertEqual(demande['statut'], 'Acceptée')
        correctif = self.ot_par_id[demande['ot_id']]
        self.assertEqual((correctif['di_id'], correctif['equipement_id'], correctif['symptome_code']),
                         (demande['id'], demande['equipement_id'], demande['symptome_code']))
        self.assertTrue(correctif['type'].startswith('correctif') and correctif['statut'] in STATUTS_CLOTURES)
        self.assertGreater(correctif['date_creation'], demande['date_heure'])
        # Aucune autre suggestion sur cet équipement ou cette gamme.
        autres = [cle for cle, s in self.ouvertes.items()
                  if cle != self.s['suggestion_anomalies'] and (s['equipement'] == equipement['id'] or gamme['id'] in cle)]
        self.assertEqual(autres, [])

    def test_s4_allonger_la_gamme_de_ve01(self):
        suggestion = self.suggestion('suggestion_allonger', 'S4')
        self.assertEqual(self.repere[suggestion['equipement']], 'VE-01')
        self.assertGreaterEqual(len(suggestion['faits']), VISITES_SANS_CONSTAT)

    def test_refus_de_s4_pour_la_seule_criticite_a(self):
        gamme = self.gamme_par_id[self.s['suggestion_refus_criticite_a']]
        equipement = self.equipement_par_id[gamme['equipement_id']]
        self.assertEqual((gamme['declencheur'], gamme['actif'], equipement['criticite']), ('date', '1', 'A'))
        self.assertTrue(equipement['actif'] != '0' and equipement['statut'] != 'rebut')
        self.assertNotIn('S4-' + gamme['id'], self.ouvertes)
        # La même base, l'équipement passé en criticité B : S4 s'ouvre, avec au moins 6 visites de suite.
        sans_a = suggestions_ouvertes(self.t, criticites={equipement['id']: 'B'})
        self.assertIn('S4-' + gamme['id'], sans_a)
        serie = [self.ot_par_id[identifiant] for identifiant in sans_a['S4-' + gamme['id']]['faits']]
        self.assertGreaterEqual(len(serie), 6)
        self.assertFalse(any(avec_anomalie(self.t, visite) for visite in serie))
        depuis = [o['id'] for o in self.t['ordres_travail'] if o['equipement_id'] == equipement['id']
                  and o['type'] in TYPES_CORRECTIFS and o['statut'] != 'Annulé'
                  and o['date_creation'][:10] >= serie[0]['date_fin'][:10]]
        self.assertEqual(depuis, [])

    def test_cas_sous_le_seuil(self):
        cas = self.s['suggestion_sous_seuil']
        cle = 'S1-%s-%s' % (cas['equipement'], cas['cause'])
        self.assertEqual(self.gammes_actives(cas['equipement']), [])
        correctifs = [o for o in self.t['ordres_travail'] if o['equipement_id'] == cas['equipement']
                      and o['type'] in TYPES_CORRECTIFS and o['statut'] in STATUTS_CLOTURES
                      and o['cause_code'] == cas['cause'] and DEBUT_12_MOIS <= jour(moment(o)) <= JOUR_REFERENCE]
        self.assertEqual(len(correctifs), SEUIL_PANNES - 1)
        self.assertFalse([c for c in self.ouvertes if c.endswith('-%s-%s' % (cas['equipement'], cas['cause']))])
        self.assertIn(cle, suggestions_ouvertes(self.t, seuil=SEUIL_PANNES - 1))     # c'est bien le seuil qui manque

    def test_suggestion_ignoree_puis_revenue(self):
        cle = self.s['suggestion_ignoree_revenue']
        suggestion = self.suggestion('suggestion_ignoree_revenue', cle[:2])
        self.assertNotIn(self.repere[suggestion['equipement']], ('CV-02', 'PO-02', 'VE-01'))
        ligne, decision, motif = decisions_par_cle(self.t)[cle]
        # Écrite comme Donnees.journaliser l'écrit (§16.4) : action brute, motif d'une ligne, 300 caractères au plus.
        self.assertEqual(decision, 'ignorée')
        self.assertTrue(motif.strip() and len(motif) <= 300 and '\n' not in motif, motif)
        self.assertEqual((ligne['table'], ligne['id_ligne'], ligne['profil'], ligne['poste']),
                         ('equipements', suggestion['equipement'], 'Responsable', 'Poste démo'))
        self.assertRegex(ligne['date_heure'], r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')
        self.assertEqual(ligne['id'][2:14], re.sub(r'\D', '', ligne['date_heure']))
        # Revenue : au moins « seuil » faits postérieurs à la décision, dans la fenêtre de 12 mois.
        self.assertEqual(suggestion['depuis'], ligne['date_heure'])
        self.assertGreaterEqual(len(suggestion['faits']), SEUIL_PANNES)
        for identifiant in suggestion['faits']:
            self.assertGreater(moment(self.ot_par_id[identifiant]), ligne['date_heure'], identifiant)
        # Et elle était ouverte quand le responsable l'a ignorée (état de la base à ce moment).
        avant = suggestions_ouvertes(self.t, jour(ligne['date_heure']), jusqu_a=ligne['date_heure'])
        self.assertIn(cle, avant)


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


class TestDemoLot6(unittest.TestCase):
    """Le jeu de démo complété pour le lot 6 (ARCHITECTURE.md §20.10, D109, D110) : des OT correctifs clôturés
    portent une astuce tirée de celles de leur scénario ; deux OT de scénario, clôturés administrativement et
    numérotés en dernier, contredisent ce que l'atelier croyait (PO-02 : désalignement, pas l'usure ; CP-01 :
    radiateur, pas le filtre)."""

    @classmethod
    def setUpClass(cls):
        cls.generateur = charger_generateur()
        cls.t = {table: lignes_propres(DOSSIER_DEMO, table) for table in TABLES}
        cls.repere = {e['id']: e['repere'] for e in cls.t['equipements']}
        cls.scenarios = [o for o in cls.t['ordres_travail'] if o['titre'].endswith('cause trouvée')]

    def test_astuces_sur_des_correctifs_clotures_tirees_de_leur_scenario(self):
        avec = [o for o in self.t['ordres_travail'] if o['astuce']]
        self.assertGreaterEqual(len(avec), 30)
        astuces = self.generateur.ASTUCES
        for ot in avec:
            with self.subTest(ot=ot['id']):
                self.assertTrue(ot['type'].startswith('correctif'))
                self.assertEqual(ot['statut'][:8], 'Clôturé ')
                self.assertLessEqual(len(ot['astuce']), 500)
                if ot not in self.scenarios:
                    self.assertIn(ot['astuce'], astuces[ot['titre'].split(' — ', 1)[1]])
        self.assertTrue(all(not o['astuce'] for o in self.t['ordres_travail'] if not o['type'].startswith('correctif')))

    def test_deux_ot_de_scenario_contradictoires(self):
        self.assertEqual([self.repere[o['equipement_id']] for o in self.scenarios], ['CP-01', 'PO-02'])
        cp01, po02 = self.scenarios
        for ot, cause, remede in ((cp01, 'C99', 'R03'), (po02, 'C11', 'R02')):
            with self.subTest(ot=ot['id']):
                self.assertEqual(ot['statut'], 'Clôturé administrativement')
                self.assertEqual((ot['cause_code'], ot['remede_code']), (cause, remede))
                self.assertTrue(ot['astuce'] and ot['compte_rendu'] and ot['di_id'])
        self.assertGreater((JOUR_REFERENCE - jour(cp01['date_fin'])).days, 14)     # validée dans le wiki de démo
        self.assertLessEqual((JOUR_REFERENCE - jour(po02['date_fin'])).days, 14)   # laissée « à valider »
        # PO-02 : après la dernière garniture changée pour usure (C01), dont elle contredit la cause.
        garnitures = [o for o in self.t['ordres_travail']
                      if o['equipement_id'] == po02['equipement_id'] and o['cause_code'] == 'C01']
        self.assertTrue(garnitures)
        self.assertGreater(po02['date_fin'], max(o['date_fin'] for o in garnitures))
        self.assertIn('désaligné', po02['compte_rendu'])
        self.assertIn('radiateur', cp01['compte_rendu'])
        # Numérotés en dernier, dans l'ordre de leurs dates : aucun autre numéro d'OT n'a bougé.
        numeros_2026 = sorted(o['id'] for o in self.t['ordres_travail'] if o['id'].startswith('OT-2026-'))
        self.assertEqual(numeros_2026[-2:], [cp01['id'], po02['id']])


class TestAvecNavigateur(CasNavigateur):
    """Comparaisons avec js/schema.js et chargement de js/demo-donnees.js dans Chromium."""

    def test_astuces_sans_vocabulaire_de_securite(self):
        """D97 : les astuces de la démo ne contiennent aucun terme du vocabulaire de la sécurité du wiki."""
        charger_scripts(self.page, ['js/lib/papaparse.min.js', 'js/schema.js', 'js/donnees.js',
                                    'js/modules/causes-frequentes.js', 'js/modules/indicateurs-regles.js',
                                    'js/modules/wiki-regles.js'])
        astuces = sorted({o['astuce'] for o in lignes_propres(DOSSIER_DEMO, 'ordres_travail') if o['astuce']}
                         | {a for liste in charger_generateur().ASTUCES.values() for a in liste})
        trouves = self.page.evaluate("(liste) => liste.map((a) => [a, Wiki.termesDeSecurite(a)])"
                                     ".filter(([, termes]) => termes.length)", astuces)
        self.assertEqual(trouves, [])

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

    def test_stockage_demo_decale_aussi_le_journal(self):
        """§11 : StockageDemo décale toutes les dates du nombre de semaines entières écoulées, celles du
        journal comprises (date_heure) ; l'identifiant J-… garde son horodatage d'origine."""
        charger_scripts(self.page, ['js/lib/papaparse.min.js', 'js/schema.js', 'js/donnees.js', 'js/stockage-demo.js',
                                    'js/demo-donnees.js'])
        decale = self.page.evaluate("""() => {
            const decalees = StockageDemo.decalerDates({ journal: DEMO_DONNEES.tables.journal },
              DEMO_DONNEES.dateReference, '2026-11-03');
            return Donnees.csv.analyser('journal', decalees.journal).lignes.map((l) => [l.id, l.date_heure, l.action]);
        }""")
        origine = lignes_propres(DOSSIER_DEMO, 'journal')
        self.assertGreater(len(origine), 0)
        self.assertEqual(len(decale), len(origine))
        for (identifiant, date_heure, action), ligne in zip(decale, origine):
            self.assertEqual((identifiant, action), (ligne['id'], ligne['action']))
            attendue = (instant_texte(ligne['date_heure']) + timedelta(days=14)).strftime('%Y-%m-%d %H:%M')
            self.assertEqual(date_heure, attendue, identifiant)

    def test_champs_proteges_selon_le_schema_js(self):
        schema_js = self.schema_js()
        for table in TABLES:
            for champ in schema_js[table]['champs']:
                if not champ['protege']:
                    continue
                for ligne in lire_table(DOSSIER_DEMO, table)[1]:
                    if ligne[champ['nom']] != '':
                        self.assertTrue(ligne[champ['nom']].startswith("'"), '%s.%s' % (table, champ['nom']))

    def test_demo_donnees_js_contient_les_23_tables_identiques_aux_csv(self):
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

    def test_demo_en_file_chargee_vite_et_controle_de_la_base_sans_probleme(self):
        """13 mois d'historique restent légers en file:// : fichier de moins de 1 Mo, démo prête en
        quelques secondes, aucun problème signalé par « Contrôle de la base »."""
        self.assertLess(FICHIER_JS.stat().st_size, 1024 * 1024)
        page = self.page
        page.goto(url_fichier('index.html'))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        debut = time.monotonic()
        page.click('#btn-demo')
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click('#profil-responsable')
        attendre_pret(page)
        duree = time.monotonic() - debut
        self.assertLess(duree, 5, 'démo prête en %.1f s' % duree)
        self.assertEqual(page.evaluate("App.mode"), 'demo')
        self.assertEqual(page.evaluate("Donnees.problemes().map((p) => p.gravite + ' : ' + p.message)"), [])
        page.evaluate("location.hash = '#/controle'")
        page.wait_for_selector('[data-compteur="erreur"] .chiffre')
        self.assertEqual(page.inner_text('[data-compteur="erreur"] .chiffre'), '0')
        self.assertIn('Aucun problème détecté', page.inner_text('#contenu'))

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
                       '12 mm', '6 à 7,5 bar', '1.2.3', '1-12', '2026-10-19', '', 'A', '0',
                       # bords : BOM, NEL (U+0085), espaces et tabulations (retrait explicite de [ \t\r\n])
                       '﻿12', '12\x85', '\t12', '\t', '  ', '12 ', '\n12 ']
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
                                                   '--fichier-js', racine / ('demo%d.js' % numero),
                                                   '--fichier-scenarios', racine / ('scenarios%d.json' % numero))
                self.assertEqual(processus.returncode, 0, processus.stderr.decode('utf-8', 'replace'))
            for table in TABLES:
                self.assertEqual((racine / 'csv1' / (table + '.csv')).read_bytes(),
                                 (racine / 'csv2' / (table + '.csv')).read_bytes(), table)
            self.assertEqual((racine / 'demo1.js').read_bytes(), (racine / 'demo2.js').read_bytes())
            self.assertEqual((racine / 'scenarios1.json').read_bytes(), (racine / 'scenarios2.json').read_bytes())
            # Les fichiers livrés sont ceux que produit le générateur (aucun oubli de régénération).
            for table in TABLES:
                self.assertEqual((racine / 'csv1' / (table + '.csv')).read_bytes(),
                                 (DOSSIER_DEMO / (table + '.csv')).read_bytes(),
                                 table + ' : relancer py outils/generer_demo.py')
            self.assertEqual((racine / 'demo1.js').read_bytes(), FICHIER_JS.read_bytes(),
                             'js/demo-donnees.js : relancer py outils/generer_demo.py')
            self.assertEqual((racine / 'scenarios1.json').read_bytes(), FICHIER_SCENARIOS.read_bytes(),
                             'tests/fixtures/demo-scenarios.json : relancer py outils/generer_demo.py')

    def test_sortie_ou_volume_n_ecrivent_pas_les_identifiants_de_scenario(self):
        """Le fichier des scénarios ne vaut que pour le jeu livré : --sortie ne le réécrit pas."""
        avant = FICHIER_SCENARIOS.stat().st_mtime_ns
        with tempfile.TemporaryDirectory() as temporaire:
            processus, _ = executer_generateur('--sortie', Path(temporaire) / 'csv', '--sans-js')
            self.assertEqual(processus.returncode, 0, processus.stderr.decode('utf-8', 'replace'))
            self.assertEqual(sorted(p.name for p in Path(temporaire).iterdir()), ['csv'])
        self.assertEqual(FICHIER_SCENARIOS.stat().st_mtime_ns, avant)

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
            # Gammes : environ une pour trois équipements, les trois déclencheurs, quelques-unes échues
            # (donc avec un OT préventif ouvert) ; compteurs, relevés, mouvements et achats en proportion
            # du jeu de démo.
            gammes = lire_table(sortie, 'gammes')[1]
            self.assertTrue(500 * 0.28 <= len(gammes) <= 500 * 0.36, len(gammes))
            self.assertEqual(sorted({g['declencheur'] for g in gammes}), ['compteur', 'date', 'seuil'])
            ordres = lire_table(sortie, 'ordres_travail')[1]
            ouvertes = {o['gamme_id'] for o in ordres if o['gamme_id'] and est_ouvert(o)}
            self.assertGreaterEqual(len(ouvertes), 10)
            compteurs = lire_table(sortie, 'compteurs')[1]
            self.assertEqual({g['compteur_id'] for g in gammes if g['declencheur'] != 'date'},
                             {c['id'] for c in compteurs})
            self.assertGreaterEqual(len(lire_table(sortie, 'releves')[1]), 20 * len(compteurs))
            demo_ot = len(lire_table(DOSSIER_DEMO, 'ordres_travail')[1])
            for table in ('mouvements_stock', 'achats'):
                proportion_demo = len(lire_table(DOSSIER_DEMO, table)[1]) / demo_ot
                proportion = len(lire_table(sortie, table)[1]) / len(ordres)
                self.assertTrue(0.3 * proportion_demo <= proportion <= 3 * proportion_demo,
                                '%s : %.3f par OT (démo : %.3f)' % (table, proportion, proportion_demo))
            self.assertTrue(all(e['valeur_remplacement'] for e in lire_table(sortie, 'equipements')[1]))

    def test_option_mois_change_la_duree_de_l_historique(self):
        with tempfile.TemporaryDirectory() as temporaire:
            sortie = Path(temporaire) / 'court'
            processus, _ = executer_generateur('--mois', '6', '--sortie', sortie)
            self.assertEqual(processus.returncode, 0, processus.stderr.decode('utf-8', 'replace'))
            ot_court = lire_table(sortie, 'ordres_travail')[1]
            ot_long = lire_table(DOSSIER_DEMO, 'ordres_travail')[1]
            self.assertGreater(len(ot_long), 1.5 * len(ot_court))
            premiere = min(o['date_creation'][:10] for o in ot_court)
            self.assertGreaterEqual(premiere, '2026-04-01')
            self.assertFalse(any(o['id'].startswith('OT-2025-') for o in ot_court))
            self.assertTrue(any(o['id'].startswith('OT-2025-') for o in ot_long))
            self.assertEqual(len(lire_table(sortie, 'equipements')[1]), 31)

    def test_volume_sans_sortie_est_refuse(self):
        processus, _ = executer_generateur('--volume', '500,5000')
        self.assertNotEqual(processus.returncode, 0)


if __name__ == '__main__':
    unittest.main()
