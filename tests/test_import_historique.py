"""Historique des interventions (lot 5, ARCHITECTURE.md §18.6, D92 et ses trois ajustements ; tâche T82).

Le fichier d'essai tests/fixtures/import/historique.csv est lu ICI en Python (module csv) et passé, comme
grille de lignes, à Import.preparer('historique', …) dans une page file:// chargée avec le jeu de démo.
L'aperçu rendu est comparé :
    - à un CALCUL PYTHON INDÉPENDANT écrit dans ce fichier (CalculHistorique : conversion, refus,
      ancien numéro, doublons sûrs et supposés, défauts signalés, codes par famille, technicien,
      ligne de temps, identifiants OT-AAAA-NNNN de l'année de création) ;
    - aux chiffres du LISEZMOI des fichiers d'essai (tableau recopié ici, ligne par ligne).
Puis : « Importer quand même » (options.importerQuandMeme), réimport après écriture des créations par
Donnees.modifier (rien n'est recréé), indicateurs de la base importée (MTBF, MTTR, disponibilité, avec
l'ajustement 3) égaux au CalculPython de test_regles_indicateurs.py, et l'aperçu n'écrit rien.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_import_historique.py" -v
"""
import csv as module_csv
import datetime
import decimal
import math
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, charger_scripts
from test_import_regles import BOOLEENS, cle, comparable, lire_date, lire_decimal, lire_demo, relire, sans_accents
from test_regles_indicateurs import CalculPython as CalculIndicateurs

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "tests" / "fixtures" / "import" / "historique.csv"
SCRIPTS = [
    "js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/stockage-demo.js", "js/interface.js",
    "js/modules/accueil.js", "js/modules/ordres-regles.js", "js/modules/planning-regles.js",
    "js/modules/indicateurs-regles.js", "js/modules/indicateurs-series.js",
    "js/modules/import-regles.js", "js/modules/import-historique.js",
]
HEURE_FIXE = "2026-10-21T09:30:00"
MAINTENANT = "2026-10-21 09:30"
FIN_FENETRE = "2025-10-31"          # 12 mois glissants : 2024-11-01 → 2025-10-31 (historique importé + début de la démo)


# ---------------------------------------------------------------------------
# Lecture du fichier d'essai (comme Import.lire : cellules en texte, une ligne par enregistrement)
# ---------------------------------------------------------------------------

def lire_historique():
    with open(FICHIER, encoding="utf-8", newline="") as flux:
        lignes = list(module_csv.reader(flux))
    return lignes[0], lignes[1:]


# Correspondance attendue des 15 colonnes du fichier (toutes « sûres »)
CHOIX_FICHIER = {0: "ancien_numero", 1: "equipement", 2: "date_creation", 3: "date_debut", 4: "date_fin", 5: "type",
                 6: "titre", 7: "compte_rendu", 8: "duree_arret_h", 9: "arret_production", 10: "symptome_code",
                 11: "cause_code", 12: "remede_code", 13: "technicien", 14: "temps_passe_h"}


def correspondance(entetes, choix):
    return [{"colonne": i, "entete": e, "champ": choix.get(i, ""), "statut": "sure" if i in choix else "non_utilisee",
             "raison": ""} for i, e in enumerate(entetes)]


# ---------------------------------------------------------------------------
# Règles écrites ici, sans lire le JavaScript (§18.5, §18.6, LISEZMOI « Choix retenus »)
# ---------------------------------------------------------------------------

TYPES_OT = ["correctif immédiat", "correctif différé", "préventif systématique", "préventif conditionnel",
            "amélioration", "réglementaire"]
PRIORITES = ["P1", "P2", "P3", "P4"]
# Équivalences de type affichées (D86) : texte comparable → type de Prévo
TYPES_LUS = {"depannage": "correctif immédiat", "curatif": "correctif immédiat", "preventif": "préventif systématique",
             "entretien preventif": "préventif systématique", "maintenance preventive": "préventif systématique",
             "conditionnel": "préventif conditionnel", "amelioratif": "amélioration"}
# Champs du type « historique », dans l'ordre de Import.TYPES : (libellé, genre, protégé)
CHAMPS = [
    ("ancien_numero", "Ancien n° d'OT", "texte", True), ("equipement", "Équipement", "texte", True),
    ("type", "Type", "choix", False), ("priorite", "Priorité", "choix", False), ("titre", "Titre", "texte", False),
    ("compte_rendu", "Compte rendu", "texte_long", False), ("date_creation", "Date de création", "date_heure", False),
    ("date_debut", "Date de début", "date_heure", False), ("date_fin", "Date de fin", "date_heure", False),
    ("arret_production", "Arrêt de production", "booleen", False), ("duree_arret_h", "Durée d'arrêt (heures)", "decimal", False),
    ("symptome_code", "Code symptôme", "texte", False), ("cause_code", "Code cause", "texte", False),
    ("remede_code", "Code remède", "texte", False), ("technicien", "Technicien", "texte", False),
    ("temps_passe_h", "Temps passé (heures)", "decimal", False), ("cout_soustraitance", "Coût de sous-traitance", "decimal", False),
]
LIBELLES = {c[0]: c[1] for c in CHAMPS}
FAMILLES = [("symptome_code", "symptôme"), ("cause_code", "cause"), ("remede_code", "remède")]
DEFAUTS_OT = {"statut": "Créé", "arret_production": "0", "remise_service": "0", "anomalie_constatee": "0"}


def lire_date_heure(valeur):
    m = re.fullmatch(r"([0-9/.\-]+)(?:(?:\s+|T)(\d{1,2}):(\d{2})(?::(\d{2}))?)?", valeur)
    jour = lire_date(m.group(1)) if m else None
    if not jour:
        return None
    if m.group(2) is None:
        return jour + " 00:00"
    heures, minutes, secondes = int(m.group(2)), int(m.group(3)), int(m.group(4) or 0)
    if heures > 23 or minutes > 59 or secondes > 59:
        return None
    return "%s %02d:%02d" % (jour, heures, minutes)


def lire_choix(valeur, permises, equivalences):
    k = " ".join(sans_accents(valeur).lower().split())
    lu = next((p for p in permises if sans_accents(p).lower() == k), None)
    if lu is None:
        lu = equivalences.get(comparable(valeur))
    if lu is None:
        lu = next((p for p in permises if comparable(p) in (comparable(valeur), comparable(valeur)[:-1] if comparable(valeur).endswith("s") else None)), None)
    return lu


def convertir(cle_champ, genre, protege, brut):
    """→ (valeur, erreur, note) ; erreur et note : tuples de mots-clés de la raison attendue."""
    libelle = LIBELLES[cle_champ]
    v = (brut or "").strip()
    if v == "":
        return "", None, None
    if genre in ("texte", "texte_long"):
        return relire(v, protege), None, None
    if v.startswith("'"):
        v = v[1:].strip()
    if genre == "choix":
        lu = lire_choix(v, TYPES_OT if cle_champ == "type" else PRIORITES, TYPES_LUS if cle_champ == "type" else {})
        if lu is None:
            return v, (libelle, v, "valeurs permises"), None
        return lu, None, (None if comparable(lu) == comparable(v) else (libelle, v, "lu comme", lu))
    lu = {"date_heure": lire_date_heure, "decimal": lire_decimal, "booleen": lambda t: BOOLEENS.get(t.lower())}[genre](v)
    return (lu, None, None) if lu is not None else (v, (libelle, v), None)


def anciens_numeros(compte_rendu):
    numeros = []
    for ligne in re.split(r"\r?\n", compte_rendu or ""):
        m = re.match(r"^\s*ancien\s+n(?:°|º|o)\.?\s*:\s*(.*?)\s*$", ligne, re.I)
        if m and m.group(1):
            numeros.append(m.group(1))
    return numeros


def titre_du_compte_rendu(compte_rendu):
    """80 caractères au plus, coupés en fin de mot (LISEZMOI, choix 6)."""
    t = " ".join(compte_rendu.split())
    if len(t) <= 80:
        return t
    coupe = t[:80]
    if t[80] != " " and " " in coupe:
        coupe = coupe[:coupe.rfind(" ")]
    return coupe.rstrip(" ,;:")


def negatif(valeur):
    return decimal.Decimal(valeur) < 0


# ---------------------------------------------------------------------------
# Calcul Python indépendant de l'aperçu de l'historique
# ---------------------------------------------------------------------------

class CalculHistorique:

    def __init__(self, base, colonnes):
        self.b, self.colonnes = base, colonnes

    def equipement(self, repere):
        trouves = [e for e in self.b["equipements"] if cle(e["repere"]) == cle(repere)]
        actifs = [e for e in trouves if e.get("actif") != "0"]
        return (actifs or trouves or [None])[0]

    def technicien(self, nom):
        k, tous = cle(nom), self.b["techniciens"]
        trouves = [t for t in tous if k in (cle(t["prenom"] + " " + t["nom"]), cle(t["nom"] + " " + t["prenom"]))]
        trouves = trouves or [t for t in tous if cle(t["nom"]) == k]
        return trouves[0]["id"] if len(trouves) == 1 else None

    def code(self, famille, valeur):
        codes = [c for c in self.b["codes_defaillance"] if c["famille"] == famille]
        par_code = [c for c in codes if comparable(c["code"]) == comparable(valeur)]
        if par_code:
            return par_code[0]["code"]
        par_libelle = [c for c in codes if comparable(c["libelle"]) == comparable(valeur)]
        return par_libelle[0]["code"] if len(par_libelle) == 1 else None

    def preparer(self, grille, choix, premier=2, forcees=()):
        colonnes = {champ: colonne for colonne, champ in choix.items()}
        numeros_base, cles_base = {}, {}
        for ot in self.b["ordres_travail"]:
            for numero in anciens_numeros(ot["compte_rendu"]):
                numeros_base.setdefault(cle(numero), {"ot": ot["id"]})
            cles_base.setdefault((ot["equipement_id"], ot["date_creation"][:16], comparable(ot["titre"])), {"ot": ot["id"]})
        numeros_fichier, cles_fichier, lignes, creations = {}, {}, [], []
        for rang, cellules in enumerate(grille):
            if not any((c or "").strip() for c in cellules):
                continue
            ligne = {"numero": premier + rang, "rang": rang, "action": "creer", "raisons": [], "valeurs": {},
                     "changements": [], "cible": "", "_doublon": None}
            lignes.append(ligne)
            self.ligne(ligne, cellules, colonnes, numeros_base, cles_base, numeros_fichier, cles_fichier, creations, forcees)
        # Identifiants : plus grand numéro existant + 1, dans l'ordre du fichier ; OT de l'année de création
        compteurs = {}

        def suivant(table, prefixe, chiffres):
            if prefixe not in compteurs:
                compteurs[prefixe] = max([int(l["id"][len(prefixe):]) for l in self.b[table]
                                          if l["id"].startswith(prefixe) and l["id"][len(prefixe):].isdigit()] or [0])
            compteurs[prefixe] += 1
            return prefixe + str(compteurs[prefixe]).zfill(chiffres)

        ecritures = {"ordres_travail": {"creer": [], "modifier": []}, "ot_temps": {"creer": [], "modifier": []}}
        for ligne, ot, temps in creations:
            ot["id"] = suivant("ordres_travail", "OT-" + ot["date_creation"][:4] + "-", 4)
            ligne["cible"] = ot["id"]
            ecritures["ordres_travail"]["creer"].append(ot)
            if temps is not None:
                temps["id"] = suivant("ot_temps", "OTT-", 6)
                temps["ot_id"] = ot["id"]
                ecritures["ot_temps"]["creer"].append(temps)
        for ligne in lignes:
            doublon = ligne.pop("_doublon")
            ligne["doublon"] = None
            if doublon is not None:
                cible = doublon.get("ot") or (doublon["ligne"]["cible"] if doublon["ligne"]["action"] == "creer" else "")
                ligne["doublon"] = {"ot": cible, "ligne": doublon["ligne"]["numero"] if "ligne" in doublon else None}
                if ligne["action"] != "creer":
                    ligne["cible"] = cible
        totaux = {a: sum(1 for l in lignes if l["action"] == a)
                  for a in ("creer", "mettre_a_jour", "identique", "refusee", "doublon_sur", "doublon_suppose")}
        totaux.update(lignes=len(lignes), references=0)
        return {"lignes": lignes, "ecritures": ecritures, "totaux": totaux}

    def ligne(self, ligne, cellules, colonnes, numeros_base, cles_base, numeros_fichier, cles_fichier, creations, forcees):
        v, erreurs, manquants = ligne["valeurs"], [], []
        for cle_champ, libelle, genre, protege in CHAMPS:
            if cle_champ not in colonnes:
                if cle_champ == "equipement":
                    manquants.append((libelle, "obligatoire"))
                continue
            colonne = colonnes[cle_champ]
            valeur, erreur, note = convertir(cle_champ, genre, protege, cellules[colonne] if colonne < len(cellules) else "")
            if note:
                ligne["raisons"].append(note)
            if erreur:
                v[cle_champ] = valeur
                erreurs.append(erreur)
            elif valeur != "":
                v[cle_champ] = valeur
            elif cle_champ == "equipement":
                manquants.append((libelle, "obligatoire"))
        numero = v.get("ancien_numero", "")
        # 1. Doublon sûr : même ancien numéro dans Prévo, sinon plus haut dans le fichier (ligne non refusée)
        if numero:
            deja = numeros_base.get(cle(numero)) or numeros_fichier.get(cle(numero))
            if deja:
                ligne.update(action="doublon_sur", _doublon=deja)
                ligne["raisons"].insert(0, ("Doublon sûr", numero, deja["ot"] if "ot" in deja else "ligne %d" % deja["ligne"]["numero"]))
                return
        # 2. Refus
        if erreurs or manquants:
            return self.refuser(ligne, erreurs + manquants)
        equipement = self.equipement(v["equipement"])
        if equipement is None:
            erreurs.append((v["equipement"], "introuvable"))
        if not v.get("date_creation") and not v.get("date_debut"):
            erreurs.append(("ni date de création", "début"))
        for cle_champ in ("duree_arret_h", "temps_passe_h", "cout_soustraitance"):
            if cle_champ in v and negatif(v[cle_champ]):
                erreurs.append((LIBELLES[cle_champ], "négatif"))
        if not v.get("titre") and not v.get("compte_rendu"):
            erreurs.append(("Titre", "ni titre ni compte rendu"))
        if erreurs:
            return self.refuser(ligne, erreurs)
        # 3. L'OT clôturé (§18.6)
        raisons = ligne["raisons"]
        type_ot = v.get("type") or "correctif différé"
        if "type" not in v:
            raisons.append(("Type", "correctif différé", "par défaut"))
        priorite = v.get("priorite") or "P3"
        if "priorite" not in v:
            raisons.append(("Priorité", "P3", "par défaut"))
        titre = v.get("titre") or titre_du_compte_rendu(v["compte_rendu"])
        if "titre" not in v:
            raisons.append(("Titre", "compte rendu"))
        date_creation = v.get("date_creation") or v["date_debut"]
        if "date_creation" not in v:
            raisons.append(("Date de création", "date de début"))
        date_debut = v.get("date_debut", "")
        date_fin = v.get("date_fin") or date_debut or date_creation
        if "date_fin" not in v:
            raisons.append(("Date de fin", "date de début" if date_debut else "date de création"))
        duree = v.get("duree_arret_h", "")
        if "arret_production" in v:
            arret = v["arret_production"]
            if arret == "0" and duree and decimal.Decimal(duree) > 0:
                raisons.append(("non", "durée d'arrêt"))
        else:
            arret = "1" if duree and decimal.Decimal(duree) > 0 else "0"
            if arret == "1":
                raisons.append(("Arrêt de production", "oui", "durée"))
        if arret == "1" and not duree:
            raisons.append(("sans durée", "vide"))
        codes = {}
        for cle_champ, famille in FAMILLES:
            codes[cle_champ] = ""
            if cle_champ in v:
                trouve = self.code(famille, v[cle_champ])
                if trouve:
                    codes[cle_champ] = trouve
                else:
                    raisons.append((LIBELLES[cle_champ], v[cle_champ], "introuvable", "vide"))
        technicien_id = ""
        if "technicien" in v:
            technicien_id = self.technicien(v["technicien"]) or ""
            if not technicien_id:
                raisons.append((v["technicien"], "introuvable", "vide"))
        temps = v.get("temps_passe_h")
        avec_temps = temps is not None and decimal.Decimal(temps) > 0
        if avec_temps and not technicien_id:
            raisons.append(("Temps passé", "sans technicien"))
        compte_rendu = ("Ancien n° : " + numero + ("\n" + v["compte_rendu"] if v.get("compte_rendu") else "")) if numero \
            else v.get("compte_rendu", "")
        ot = {nom: DEFAUTS_OT.get(nom, "") for nom in self.colonnes["ordres_travail"]}
        ot.update({"origine": "préventif" if type_ot.startswith("préventif") else "manuel", "equipement_id": equipement["id"],
                   "type": type_ot, "priorite": priorite, "statut": "Clôturé administrativement", "titre": titre,
                   "date_creation": date_creation, "technicien_id": technicien_id, "date_debut": date_debut,
                   "date_fin": date_fin, "arret_production": arret, "duree_arret_h": duree, "compte_rendu": compte_rendu,
                   "remise_service": "1", "cout_soustraitance": v.get("cout_soustraitance", ""),
                   "date_cloture_tech": date_fin, "date_cloture_admin": date_fin}, **codes)
        # 4. Doublon supposé : même équipement, même date de création à la minute, même titre comparable
        k = (equipement["id"], date_creation, comparable(titre))
        suppose = cles_base.get(k) or cles_fichier.get(k)
        if suppose:
            ligne["_doublon"] = suppose
            ou = suppose["ot"] if "ot" in suppose else "ligne %d" % suppose["ligne"]["numero"]
            if ligne["numero"] not in forcees:
                ligne["action"] = "doublon_suppose"
                raisons.insert(0, ("Doublon supposé", ou, "Importer quand même"))
                if numero:
                    numeros_fichier.setdefault(cle(numero), {"ligne": ligne})
                return
            raisons.insert(0, ("Doublon supposé", ou, "importée quand même"))
        temps_ligne = {"id": "", "ot_id": "", "technicien_id": technicien_id, "date": date_fin[:10], "heures": temps} if avec_temps else None
        creations.append((ligne, ot, temps_ligne))
        if numero:
            numeros_fichier.setdefault(cle(numero), {"ligne": ligne})
        cles_fichier.setdefault(k, {"ligne": ligne})

    @staticmethod
    def refuser(ligne, raisons):
        ligne.update(action="refusee", changements=[], cible="")
        ligne["raisons"] += raisons


# ---------------------------------------------------------------------------
# Chiffres du LISEZMOI (tests/fixtures/import/LISEZMOI.md, historique.csv), recopiés ici
# ---------------------------------------------------------------------------
# numéro de ligne, N° OT, repère, action, OT, type, origine, création, début, fin, arrêt, durée,
# codes S / C / R, technicien, (ligne ot_temps : id, heures, technicien, date) ou None
L = "creer"
LISEZMOI = [
    (2, "3987", "PO-01", L, "OT-2024-0001", "correctif immédiat", "manuel", "2024-11-18 15:45", "2024-11-18 16:00", "2024-11-18 17:30", "1", "1.5", "S06", "C09", "R07", "TEC-0004", ("OTT-000276", "1.5", "TEC-0004", "2024-11-18")),
    (3, "3990", "SC-01", L, "OT-2024-0002", "préventif systématique", "préventif", "2024-12-09 08:00", "2024-12-09 08:30", "2024-12-09 09:30", "0", "", "", "", "", "TEC-0002", ("OTT-000277", "1", "TEC-0002", "2024-12-09")),
    (4, "4512", "CP-01", L, "OT-2025-0057", "correctif immédiat", "manuel", "2025-01-14 07:40", "2025-01-14 08:05", "2025-01-14 10:30", "1", "2.5", "S01", "C01", "R01", "TEC-0002", ("OTT-000278", "2.5", "TEC-0002", "2025-01-14")),
    (5, "4513", "PO-02", L, "OT-2025-0058", "correctif immédiat", "manuel", "2025-02-03 10:15", "2025-02-03 10:40", "2025-02-03 12:10", "1", "1.5", "S02", "C02", "R01", "TEC-0002", ("OTT-000279", "1.75", "TEC-0002", "2025-02-03")),
    (6, "4514", "CV-02", L, "OT-2025-0059", "correctif immédiat", "manuel", "2025-02-11 06:50", "2025-02-11 07:05", "2025-02-11 07:50", "1", "0.75", "S05", "C04", "R03", "TEC-0001", ("OTT-000280", "0.75", "TEC-0001", "2025-02-11")),
    (7, "4515", "PR-01", L, "OT-2025-0060", "correctif immédiat", "manuel", "2025-02-24 13:20", "2025-02-24 13:30", "2025-02-24 16:00", "1", "", "S01", "C10", "R01", "TEC-0004", ("OTT-000281", "2.5", "TEC-0004", "2025-02-24")),
    (8, "4516", "GF-01", L, "OT-2025-0061", "préventif systématique", "préventif", "2025-03-10 09:00", "2025-03-10 09:15", "2025-03-10 12:15", "0", "", "", "", "", "TEC-0001", ("OTT-000282", "3", "TEC-0001", "2025-03-10")),
    (9, "4517", "CU-01", L, "OT-2025-0062", "correctif différé", "manuel", "2025-03-19 14:10", "2025-03-20 08:00", "2025-03-20 11:30", "1", "1.5", "S05", "C06", "R04", "TEC-0003", ("OTT-000283", "3.5", "TEC-0003", "2025-03-20")),
    (10, "4518", "EM-01", L, "OT-2025-0063", "amélioration", "manuel", "2025-04-02 10:00", "2025-04-07 13:00", "2025-04-07 17:00", "0", "", "", "", "R09", "TEC-0003", ("OTT-000284", "4", "TEC-0003", "2025-04-07")),
    (11, "4519", "PT-01", L, "OT-2025-0064", "réglementaire", "manuel", "2025-04-15 08:00", "2025-04-16 08:00", "2025-04-16 10:00", "0", "", "", "", "", "", None),
    (12, "4520", "CP-01", "doublon_suppose"),
    (13, "4521", "CV-03", "refusee"),
    (14, "4522", "ET-01", L, "OT-2025-0065", "correctif immédiat", "manuel", "2025-05-12 09:30", "2025-05-12 09:30", "2025-05-12 10:15", "1", "0.5", "S07", "C11", "R02", "TEC-0004", ("OTT-000285", "0.75", "TEC-0004", "2025-05-12")),
    (15, "4523", "XX-99", "refusee"),
    (16, "4524", "CH-01", L, "OT-2025-0066", "correctif immédiat", "manuel", "2025-05-20 14:00", "2025-05-20 14:20", "2025-05-20 16:20", "1", "2", "", "", "R06", "TEC-0002", ("OTT-000286", "2", "TEC-0002", "2025-05-20")),
    (17, "4525", "VE-01", L, "OT-2025-0067", "correctif différé", "manuel", "2025-06-03 07:30", "2025-06-03 08:00", "2025-06-03 09:10", "0", "", "S03", "C03", "R02", "TEC-0001", ("OTT-000287", "1", "TEC-0001", "2025-06-03")),
    (18, "4601", "CV-02", "doublon_suppose"),
    (19, "4514", "CV-02", "doublon_sur"),
]


# ---------------------------------------------------------------------------
# Grille construite : cas que le fichier d'essai ne couvre pas
# ---------------------------------------------------------------------------

E_GRILLE = ["N° d'OT", "Repère", "Date", "Début", "Fin", "Nature", "Objet", "Commentaire", "Durée d'arrêt", "Arrêt",
            "Symptôme", "Cause", "Remède", "Réalisé par", "Temps passé", "Priorité", "Sous-traitance"]
C_GRILLE = {0: "ancien_numero", 1: "equipement", 2: "date_creation", 3: "date_debut", 4: "date_fin", 5: "type", 6: "titre",
            7: "compte_rendu", 8: "duree_arret_h", 9: "arret_production", 10: "symptome_code", 11: "cause_code",
            12: "remede_code", 13: "technicien", 14: "temps_passe_h", 15: "priorite", 16: "cout_soustraitance"}


def g(numero, repere, creation="", debut="", fin="", type_ot="", titre="", compte_rendu="", duree="", arret="", s="", c="", r="",
      technicien="", temps="", priorite="", soustraitance=""):
    return [numero, repere, creation, debut, fin, type_ot, titre, compte_rendu, duree, arret, s, c, r, technicien, temps,
            priorite, soustraitance]


GRILLE = [
    # 2 : créé le 31/12/2024, commencé en 2025 → numéro de l'année de CRÉATION (OT-2024-…) ; sous-traitance à virgule
    g("A-1", "CP-01", "31/12/2024 23:50", "02/01/2025 08:00", "02/01/2025 10:00", "Correctif différé", "Fuite au raccord",
      "Raccord changé.", arret="non", technicien="Julien Moreau", temps="2", priorite="P2", soustraitance="150,5"),
    g("A-2", "PO-01", "01/03/2025 08:00", type_ot="Inconnu", titre="Titre"),                      # 3 type hors liste
    g("A-3", "PO-02", "05/03/2025 08:00", titre="Titre", compte_rendu="CR", duree="-2"),           # 4 durée négative
    g("A-4", "PO-02", "06/03/2025 08:00"),                                                         # 5 ni titre ni compte rendu
    # 6 : date seule, sans début ni fin ; arrêt oui sans durée ; temps sans technicien ; priorité vide → P3
    g("A-5", "GF-01", "07/03/2025", type_ot="Réglementaire", titre="Contrôle annuel", compte_rendu="Contrôle fait.",
      arret="oui", temps="1,5"),
    # 7 : arrêt « non » malgré une durée ; codes par code ; technicien « Nom Prénom »
    g("A-6", "PO-01", "08/03/2025 10:00", "08/03/2025 10:30", "08/03/2025 12:00", "Dépannage", "Pompe bloquée", "Débloquée.",
      "3", "non", "S06", "C14", "R06", "Benali Karim", "1", "P1"),
    g("A-7", "ZZ-00", "09/03/2025 10:00", titre="Machine inconnue"),                              # 8 refusée (machine)
    # 9 : même ancien numéro que la ligne 8, refusée : pas un doublon sûr
    g("A-7", "CU-01", "09/03/2025 10:00", "09/03/2025 10:15", "09/03/2025 11:00", "curatif", "Broche bloquée !",
      "Broche débloquée.", "0,5", "oui", technicien="Thomas Garnier", temps="0,75"),
    # 10 : doublon supposé de la ligne 9 (titre comparable : casse, accents, ponctuation ignorés)
    g("A-8", "CU-01", "09/03/2025 10:00", type_ot="Dépannage", titre="BROCHE BLOQUEE"),
    g("A-8", "CU-01", "10/03/2025 10:00", titre="Autre"),                                          # 11 doublon sûr de la ligne 10
    # 12 : sans ancien numéro ; préventif conditionnel ; codes d'une autre famille → vides ; remède en minuscules
    g("", "CU-01", "10/03/2025 07:00", "10/03/2025 07:30", "10/03/2025 08:00", "conditionnel", "Analyse vibratoire",
      "Mesures dans les tolérances.", s="Garniture usée", c="fuite", r="r05", technicien="Sophie Lambert", temps="0,5",
      priorite="P4", soustraitance="0"),
    g("A-9", "", "11/03/2025 08:00", titre="Sans machine"),                                        # 13 équipement vide
    g("A-10", "SC-01", "32/01/2025 08:00", titre="Date impossible"),                               # 14 date illisible
    # 15 : année 2023, numéro protégé par une apostrophe (rapport des refus réimporté)
    g("'0042", "SC-01", "15/06/2023 09:00", "15/06/2023 09:30", "15/06/2023 10:00", "Amélioration", "Carter ajouté",
      "Carter de protection ajouté sur la lame.", arret="non", r="R09", technicien="Thomas Garnier", temps="1"),
    g("", ""),                                                                                      # 16 vide : ignorée
    # 17 : temps 0 → aucune ligne de temps ; durée 0 donnée → gardée (jamais vidée) ; arrêt vide → non
    g("A-11", "PT-01", "20/03/2025 08:00", fin="20/03/2025 09:00", titre="Essai", duree="0", technicien="Julien Moreau", temps="0"),
    # 18 : même machine, même jour et même titre que la ligne 9, mais une autre heure : pas un doublon supposé
    g("A-12", "CU-01", "09/03/2025 14:00", titre="Broche bloquée", compte_rendu="Nouvelle intervention l'après-midi."),
    # 19 : titre absent, compte rendu long : 80 caractères au plus, coupés en fin de mot (jamais au milieu)
    g("A-13", "PO-03", "21/03/2025 08:00",
      compte_rendu="Remplacement du capteur inductif de position sur le vérin principal du bras de levage, puis réglage."),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def ecrire_creations(page, ecritures):
    """Écrit les créations de l'aperçu par Donnees.modifier, table par table (OT puis temps), sans Import.importer."""
    page.evaluate("""async (ecritures) => {
      for (const table of ['ordres_travail', 'ot_temps']) {
        const nouvelles = ecritures[table].creer.map((ligne) => Object.assign({}, ligne));
        await Donnees.modifier(table, (lignes) => { lignes.push(...nouvelles); }, { journal: false });
      }
    }""", ecritures)


class CasHistorique(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tables = {f.stem: f.read_bytes().decode("utf-8-sig") for f in (RACINE / "donnees" / "demo").glob("*.csv")}
        cls.entetes, cls.grille = lire_historique()

    def setUp(self):
        super().setUp()
        self.contexte.clock.set_fixed_time(HEURE_FIXE)
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable' });
          await Donnees.chargerTout();
        }""", self.tables)
        self.base, self.colonnes = lire_demo()

    def preparer(self, grille=None, choix=None, entetes=None, options=None):
        options = dict({"maintenant": MAINTENANT}, **(options or {}))
        grille = self.grille if grille is None else grille
        return self.page.evaluate("([l, c, o]) => Import.preparer('historique', l, c, o)",
                                  [grille, correspondance(entetes or self.entetes, choix or CHOIX_FICHIER), options])

    def attendu(self, grille=None, choix=None, forcees=()):
        return CalculHistorique(self.base, self.colonnes).preparer(self.grille if grille is None else grille,
                                                                   choix or CHOIX_FICHIER, forcees=forcees)

    def verifier_raisons(self, obtenues, attendues):
        restantes = list(obtenues)
        for mots in attendues:
            trouvee = next((r for r in restantes if all(m in r for m in mots)), None)
            self.assertIsNotNone(trouvee, "raison attendue %r absente de %r" % (mots, obtenues))
            restantes.remove(trouvee)
        self.assertEqual(restantes, [], "raisons en trop : %r" % (restantes,))

    def comparer(self, obtenu, attendu):
        self.assertEqual([l["numero"] for l in obtenu["lignes"]], [l["numero"] for l in attendu["lignes"]])
        for lo, la in zip(obtenu["lignes"], attendu["lignes"]):
            with self.subTest(ligne=la["numero"]):
                self.assertEqual(lo["action"], la["action"], lo["raisons"])
                self.assertEqual(lo["rang"], la["rang"])
                self.assertEqual(lo["valeurs"], la["valeurs"])
                self.assertEqual(lo["cible"], la["cible"])
                self.assertEqual(lo["changements"], [])
                self.assertEqual(lo.get("doublon"), la["doublon"])
                self.verifier_raisons(lo["raisons"], la["raisons"])
        self.assertEqual(obtenu["ecritures"], attendu["ecritures"])
        self.assertEqual(obtenu["referencesCreees"], [])
        self.assertEqual(obtenu["totaux"], attendu["totaux"])

    def ajouter_a_la_base(self, ecritures):
        """Ajoute les créations attendues à la base du calcul Python (comme ecrire_creations dans la page)."""
        self.base["ordres_travail"] = self.base["ordres_travail"] + [dict(o) for o in ecritures["ordres_travail"]["creer"]]
        self.base["ot_temps"] = self.base["ot_temps"] + [dict(t) for t in ecritures["ot_temps"]["creer"]]


class TestCorrespondance(CasHistorique):

    def test_colonnes_du_fichier_toutes_reconnues(self):
        resultat = self.page.evaluate("([e, d]) => Import.correspondance('historique', e, d, null)", [self.entetes, self.grille])
        self.assertEqual({r["colonne"]: r["champ"] for r in resultat}, CHOIX_FICHIER)
        self.assertEqual([(r["entete"], r["statut"]) for r in resultat if r["statut"] != "sure"], [])

    def test_equivalences_de_type_affichees(self):
        lus = self.page.evaluate("""() => { const champ = Import.TYPES.historique.champs.find((c) => c.cle === 'type');
          return ['Dépannage', 'CURATIF', 'Préventif', 'Correctif différé', 'conditionnel', 'Autre chose']
            .map((t) => Import.interne.convertir(champ, t)); }""")
        self.assertEqual([l["valeur"] for l in lus], ["correctif immédiat", "correctif immédiat", "préventif systématique",
                                                      "correctif différé", "préventif conditionnel", "Autre chose"])
        self.assertIn("lu comme", lus[0]["note"])
        self.assertNotIn("note", lus[3])
        self.assertIn("valeurs permises", lus[5]["erreur"])


class TestApercuDuFichier(CasHistorique):

    def test_apercu_egal_au_calcul_python(self):
        self.comparer(self.preparer(), self.attendu())

    def test_apercu_conforme_au_lisezmoi(self):
        apercu = self.preparer()
        self.assertEqual(apercu["totaux"], {"lignes": 18, "references": 0, "creer": 13, "mettre_a_jour": 0, "identique": 0,
                                            "refusee": 2, "doublon_sur": 1, "doublon_suppose": 2})
        ots = {o["id"]: o for o in apercu["ecritures"]["ordres_travail"]["creer"]}
        temps = {t["ot_id"]: t for t in apercu["ecritures"]["ot_temps"]["creer"]}
        self.assertEqual(len(ots), 13)
        self.assertEqual(len(temps), 12)
        self.assertEqual(apercu["ecritures"]["ordres_travail"]["modifier"], [])
        self.assertEqual(apercu["ecritures"]["ot_temps"]["modifier"], [])
        reperes = {e["id"]: e["repere"] for e in self.base["equipements"]}
        par_numero = {l["numero"]: l for l in apercu["lignes"]}
        for attendu in LISEZMOI:
            ligne = par_numero[attendu[0]]
            with self.subTest(ligne=attendu[0]):
                self.assertEqual(ligne["action"], attendu[3], ligne["raisons"])
                self.assertEqual(ligne["valeurs"]["ancien_numero"], attendu[1])
                if attendu[3] != "creer":
                    continue
                (_, numero, repere, _, ident, type_ot, origine, creation, debut, fin, arret, duree, s, c, r, technicien, ligne_temps) = attendu
                ot = ots[ident]
                self.assertEqual(ligne["cible"], ident)
                self.assertEqual((reperes[ot["equipement_id"]], ot["type"], ot["origine"], ot["priorite"], ot["statut"]),
                                 (repere, type_ot, origine, "P3", "Clôturé administrativement"))
                self.assertEqual((ot["date_creation"], ot["date_debut"], ot["date_fin"], ot["date_cloture_tech"], ot["date_cloture_admin"]),
                                 (creation, debut, fin, fin, fin))
                self.assertEqual((ot["arret_production"], ot["duree_arret_h"], ot["remise_service"]), (arret, duree, "1"))
                self.assertEqual((ot["symptome_code"], ot["cause_code"], ot["remede_code"], ot["technicien_id"]), (s, c, r, technicien))
                self.assertTrue(ot["compte_rendu"].startswith("Ancien n° : " + numero + "\n"), ot["compte_rendu"])
                self.assertTrue(any("P3" in raison for raison in ligne["raisons"]), "priorité par défaut signalée")
                if ligne_temps is None:
                    self.assertNotIn(ident, temps)
                else:
                    t = temps[ident]
                    self.assertEqual((t["id"], t["heures"], t["technicien_id"], t["date"]), ligne_temps)
        self.assertEqual(ots["OT-2025-0067"]["titre"], "Courroie du ventilateur détendue : retendue et alignée, puis vibrations mesurées")
        self.assertEqual(par_numero[12]["cible"], "OT-2025-0057")          # doublon supposé de la ligne 4
        self.assertEqual(par_numero[18]["cible"], "OT-2025-0002")          # doublon supposé de l'OT de la démo
        self.assertEqual(par_numero[19]["cible"], "OT-2025-0059")          # doublon sûr de la ligne 6
        self.assertEqual(par_numero[12]["doublon"], {"ot": "OT-2025-0057", "ligne": 4})
        self.assertEqual(par_numero[18]["doublon"], {"ot": "OT-2025-0002", "ligne": None})
        self.assertEqual(par_numero[19]["doublon"], {"ot": "OT-2025-0059", "ligne": 6})

    def test_ancien_numero_et_compte_rendu(self):
        apercu = self.preparer()
        ot = next(o for o in apercu["ecritures"]["ordres_travail"]["creer"] if o["id"] == "OT-2025-0060")
        self.assertEqual(ot["compte_rendu"], 'Ancien n° : 4515\nFlexible HP percé, remplacé par un flexible "DN10" serti.\n'
                                             "Essai sous pression : aucune fuite.")
        self.assertIn("Ancien n°", (RACINE / "js" / "modules" / "import-historique.js").read_text(encoding="utf-8"))
        # Ligne 7 : arrêt « oui » sans durée → durée VIDE (jamais 0), signalée
        ligne = next(l for l in apercu["lignes"] if l["numero"] == 7)
        self.assertEqual((ot["arret_production"], ot["duree_arret_h"]), ("1", ""))
        self.assertTrue(any("sans durée" in r for r in ligne["raisons"]), ligne["raisons"])

    def test_signalements_du_fichier(self):
        lignes = {l["numero"]: l for l in self.preparer()["lignes"]}
        self.assertTrue(any("Pierre Martel" in r and "introuvable" in r for r in lignes[11]["raisons"]))
        self.assertTrue(any("C04" in r and "symptôme" in r for r in lignes[16]["raisons"]))
        self.assertTrue(any("Usure générale" in r for r in lignes[16]["raisons"]))
        self.assertTrue(any("correctif différé" in r and "par défaut" in r for r in lignes[17]["raisons"]))
        self.assertTrue(any("Importer quand même" in r for r in lignes[12]["raisons"]))
        self.assertTrue(any("Importer quand même" in r and "OT-2025-0002" in r for r in lignes[18]["raisons"]))
        self.assertTrue(any("XX-99" in r for r in lignes[15]["raisons"]))

    def test_doublon_sur_contre_un_ot_existant(self):
        # Un OT de la base cite l'ancien n° 4514 sur une ligne de son compte rendu (casse et espaces libres)
        self.page.evaluate("""async () => Donnees.modifier('ordres_travail', (lignes) => {
          lignes.find((o) => o.id === 'OT-2025-0003').compte_rendu = "Repris de l'ancien logiciel.\\nANCIEN N° :  4514 ";
        }, { journal: false })""")
        ot = next(o for o in self.base["ordres_travail"] if o["id"] == "OT-2025-0003")
        ot["compte_rendu"] = "Repris de l'ancien logiciel.\nANCIEN N° :  4514 "
        apercu = self.preparer()
        self.comparer(apercu, self.attendu())
        lignes = {l["numero"]: l for l in apercu["lignes"]}
        self.assertEqual((lignes[6]["action"], lignes[6]["cible"]), ("doublon_sur", "OT-2025-0003"))
        self.assertEqual((lignes[19]["action"], lignes[19]["cible"]), ("doublon_sur", "OT-2025-0003"))


class TestGrilleConstruite(CasHistorique):

    def test_cas_limites_egaux_au_calcul_python(self):
        obtenu = self.preparer(GRILLE, C_GRILLE, E_GRILLE)
        self.comparer(obtenu, self.attendu(GRILLE, C_GRILLE))
        actions = {l["numero"]: l["action"] for l in obtenu["lignes"]}
        self.assertEqual(actions, {2: "creer", 3: "refusee", 4: "refusee", 5: "refusee", 6: "creer", 7: "creer", 8: "refusee",
                                   9: "creer", 10: "doublon_suppose", 11: "doublon_sur", 12: "creer", 13: "refusee",
                                   14: "refusee", 15: "creer", 17: "creer", 18: "creer", 19: "creer"})
        ots = {o["id"]: o for o in obtenu["ecritures"]["ordres_travail"]["creer"]}
        self.assertEqual(sorted(ots), ["OT-2023-0001", "OT-2024-0001", "OT-2025-0057", "OT-2025-0058", "OT-2025-0059",
                                       "OT-2025-0060", "OT-2025-0061", "OT-2025-0062", "OT-2025-0063"])
        self.assertEqual(ots["OT-2025-0063"]["titre"], "Remplacement du capteur inductif de position sur le vérin principal du bras de")
        self.assertEqual(ots["OT-2024-0001"]["date_debut"], "2025-01-02 08:00")     # année de création, pas de début
        self.assertEqual(ots["OT-2025-0057"]["date_fin"], "2025-03-07 00:00")      # ni début ni fin : date de création
        self.assertEqual(ots["OT-2025-0061"]["duree_arret_h"], "0")               # 0 donné : gardé
        self.assertEqual(ots["OT-2023-0001"]["compte_rendu"], "Ancien n° : 0042\nCarter de protection ajouté sur la lame.")
        self.assertEqual(ots["OT-2025-0060"]["compte_rendu"], "Mesures dans les tolérances.")   # sans ancien numéro
        self.assertEqual((ots["OT-2025-0060"]["origine"], ots["OT-2025-0060"]["type"]), ("préventif", "préventif conditionnel"))
        temps = {t["ot_id"]: t for t in obtenu["ecritures"]["ot_temps"]["creer"]}
        self.assertEqual(temps["OT-2025-0057"]["technicien_id"], "")
        self.assertNotIn("OT-2025-0061", temps)                                     # temps 0 : aucune ligne

    def test_importer_quand_meme_dans_la_grille(self):
        obtenu = self.preparer(GRILLE, C_GRILLE, E_GRILLE, {"importerQuandMeme": [10]})
        self.comparer(obtenu, self.attendu(GRILLE, C_GRILLE, forcees={10}))
        lignes = {l["numero"]: l for l in obtenu["lignes"]}
        self.assertEqual(lignes[10]["action"], "creer")
        self.assertEqual(lignes[11]["cible"], lignes[10]["cible"])                   # doublon sûr de l'OT importé quand même


class TestImporterQuandMeme(CasHistorique):

    def test_un_doublon_suppose_coche_devient_une_creation(self):
        obtenu = self.preparer(options={"importerQuandMeme": [18]})
        self.comparer(obtenu, self.attendu(forcees={18}))
        ligne = next(l for l in obtenu["lignes"] if l["numero"] == 18)
        self.assertEqual(ligne["action"], "creer")
        self.assertEqual(ligne["doublon"], {"ot": "OT-2025-0002", "ligne": None})
        self.assertTrue(any("importée quand même" in r for r in ligne["raisons"]), ligne["raisons"])
        self.assertEqual(obtenu["totaux"]["creer"], 14)
        self.assertEqual(obtenu["totaux"]["doublon_suppose"], 1)
        self.assertEqual(len(obtenu["ecritures"]["ot_temps"]["creer"]), 13)
        # Un Set est accepté aussi (appel depuis l'écran) ; les deux doublons supposés cochés
        totaux = self.page.evaluate("""([l, c]) => Import.preparer('historique', l, c, { importerQuandMeme: new Set([12, 18]) }).totaux""",
                                    [self.grille, correspondance(self.entetes, CHOIX_FICHIER)])
        self.assertEqual((totaux["creer"], totaux["doublon_suppose"]), (15, 0))
        self.comparer(self.preparer(options={"importerQuandMeme": [12, 18]}), self.attendu(forcees={12, 18}))
        # Aucun : les doublons supposés restent montrés, jamais écartés en silence
        sans = self.preparer(options={"importerQuandMeme": []})
        self.assertEqual([l["numero"] for l in sans["lignes"] if l["action"] == "doublon_suppose"], [12, 18])


class TestReimport(CasHistorique):

    def test_reimport_ne_cree_rien(self):
        premier, attendu = self.preparer(), self.attendu()
        self.comparer(premier, attendu)
        ecrire_creations(self.page, premier["ecritures"])
        self.ajouter_a_la_base(attendu["ecritures"])
        avant = self.page.evaluate("() => JSON.stringify(Donnees.lignes('ordres_travail'))")
        second = self.preparer()
        self.comparer(second, self.attendu())
        self.assertEqual(second["totaux"]["creer"], 0)
        self.assertEqual(second["ecritures"], {"ordres_travail": {"creer": [], "modifier": []}, "ot_temps": {"creer": [], "modifier": []}})
        actions = {l["numero"]: l["action"] for l in second["lignes"]}
        crees = [l["numero"] for l in premier["lignes"] if l["action"] == "creer"]
        self.assertEqual({n: actions[n] for n in crees + [19]}, {n: "doublon_sur" for n in crees + [19]})
        self.assertEqual((actions[12], actions[18], actions[13], actions[15]), ("doublon_suppose", "doublon_suppose", "refusee", "refusee"))
        par_numero = {l["numero"]: l for l in second["lignes"]}
        self.assertEqual(par_numero[6]["cible"], "OT-2025-0059")
        self.assertEqual(par_numero[12]["cible"], "OT-2025-0057")
        self.assertEqual(self.page.evaluate("() => JSON.stringify(Donnees.lignes('ordres_travail'))"), avant)

    def test_reimport_apres_import_des_doublons_supposes_tout_en_doublon_sur(self):
        premier, attendu = self.preparer(options={"importerQuandMeme": [12, 18]}), self.attendu(forcees={12, 18})
        self.comparer(premier, attendu)
        ecrire_creations(self.page, premier["ecritures"])
        self.ajouter_a_la_base(attendu["ecritures"])
        second = self.preparer()
        self.comparer(second, self.attendu())
        self.assertEqual(second["totaux"], {"lignes": 18, "references": 0, "creer": 0, "mettre_a_jour": 0, "identique": 0,
                                            "refusee": 2, "doublon_sur": 16, "doublon_suppose": 0})


class TestIndicateursDeLaBaseImportee(CasHistorique):

    def test_mtbf_mttr_disponibilite_egaux_au_calcul_python(self):
        apercu = self.preparer()
        ecrire_creations(self.page, apercu["ecritures"])
        # Base du calcul indépendant : la démo (lue sur le disque) + les créations ATTENDUES (calcul Python)
        attendu = self.attendu()
        calcul = CalculIndicateurs(datetime.date.fromisoformat(FIN_FENETRE))
        calcul.ordres = calcul.ordres + [dict(o) for o in attendu["ecritures"]["ordres_travail"]["creer"]]
        for t in attendu["ecritures"]["ot_temps"]["creer"]:
            calcul.temps.setdefault(t["ot_id"], []).append(dict(t))
        equipements = sorted({o["equipement_id"] for o in attendu["ecritures"]["ordres_travail"]["creer"]})
        self.assertEqual(len(equipements), 13)
        avec_panne_importee = 0
        for equipement_id in equipements:
            valeurs = calcul.equipement(equipement_id)
            obtenu = self.page.evaluate("([id, jour]) => Indicateurs.parEquipement(id, Indicateurs.periode('12-mois', jour))",
                                        [equipement_id, FIN_FENETRE])
            if valeurs["pannes"] == 0:
                # CalculPython ne traite que les équipements en panne ; sans panne, §15.3 : disponibilité 1, avec la note
                self.assertEqual(obtenu["disponibilite"]["note"], "aucune panne sur la période")
                valeurs["disponibilite"] = 1
            for cle_indicateur, valeur in valeurs.items():
                with self.subTest(equipement=equipement_id, indicateur=cle_indicateur):
                    if valeur is None:
                        self.assertIsNone(obtenu[cle_indicateur]["valeur"])
                        self.assertTrue(obtenu[cle_indicateur]["raison"])
                    else:
                        self.assertTrue(math.isclose(obtenu[cle_indicateur]["valeur"], valeur, rel_tol=1e-9, abs_tol=1e-6),
                                        "%s : %r ≠ %r" % (cle_indicateur, obtenu[cle_indicateur]["valeur"], valeur))
            avec_panne_importee += valeurs["pannes"] > 0
        self.assertGreaterEqual(avec_panne_importee, 8)
        # Ajustement 3 : la panne importée sans durée (PR-01, ligne 7) compte dans les pannes et le MTBF,
        # mais elle est exclue du MTTR et de la disponibilité (jamais comptée 0 h)
        pr01 = self.page.evaluate("(jour) => Indicateurs.parEquipement('EQ-0020', Indicateurs.periode('12-mois', jour))", FIN_FENETRE)
        exclu = {"id": "OT-2025-0060", "raison": "sans durée d'arrêt"}
        self.assertIn(exclu, pr01["mttr"]["exclus"])
        self.assertIn(exclu, pr01["disponibilite"]["exclus"])
        self.assertEqual(pr01["pannes"]["valeur"], calcul.equipement("EQ-0020")["pannes"])
        self.assertGreaterEqual(pr01["pannes"]["valeur"], 1)


class TestApercuSansEcriture(CasHistorique):

    def test_l_apercu_n_ecrit_rien(self):
        instantane = """() => JSON.stringify({ tables: Object.fromEntries(Schema.nomsTables().map((t) => [t, Donnees.lignes(t)])),
          fichiers: Object.entries(Donnees.instantane()).map(([t, o]) => t + ':' + Array.from(o).join(',')) })"""
        avant = self.page.evaluate(instantane)
        appels = self.page.evaluate("""([l1, c1, l2, c2]) => {
          const appels = [];
          const [modifier, ajouter] = [Donnees.modifier, Donnees.ajouter];
          Donnees.modifier = (...a) => { appels.push('modifier ' + a[0]); return modifier(...a); };
          Donnees.ajouter = (...a) => { appels.push('ajouter ' + a[0]); return ajouter(...a); };
          try {
            Import.preparer('historique', l1, c1, {});
            Import.preparer('historique', l1, c1, { importerQuandMeme: [12, 18] });
            Import.preparer('historique', l2, c2, { importerQuandMeme: [10] });
          } finally { Object.assign(Donnees, { modifier, ajouter }); }
          return appels;
        }""", [self.grille, correspondance(self.entetes, CHOIX_FICHIER), GRILLE, correspondance(E_GRILLE, C_GRILLE)])
        self.assertEqual(appels, [])
        self.assertEqual(self.page.evaluate(instantane), avant)


if __name__ == "__main__":
    unittest.main()
