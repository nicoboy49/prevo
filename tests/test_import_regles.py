"""Règles d'import des référentiels (lot 5, ARCHITECTURE.md §18.2, §18.4, §18.5 ; tâche T80).

Les données sont des GRILLES construites dans ce fichier (listes de listes de textes, sans fichier : la
lecture des fichiers est une autre tâche). Chaque aperçu rendu par Import.preparer, sur une copie du jeu
de démo (donnees/demo chargé dans StockageDemo, page file://), est comparé à un CALCUL PYTHON
INDÉPENDANT écrit ici (CalculPython) : actions, raisons (par mots-clés), valeurs converties,
changements avant → après, lignes à créer complètes (défauts du schéma), modifications, références
créées et identifiants.

Couvert : Import.TYPES (dix référentiels + historique déclaré, exemples), Import.comparable,
Import.correspondance (synonymes, accents, casse, colonne ambiguë « à confirmer », inconnue « non
utilisée », échantillon, mémoire du poste et sa lecture protégée), Import.preparer (dates JJ/MM/AAAA et
ISO, décimaux à virgule, booléens, listes fermées D86, repères « 007 », D84 a, « identique », doublons
dans le fichier, références créées D88 a, introuvables refusées, stock initial, gammes et opérations,
habilitations « Prénom Nom » / « Nom Prénom », codes par famille tolérante, mise à jour non demandée),
Import.rapportRefus (format §3.1), délégation de l'historique, et la base IDENTIQUE À L'OCTET après
l'aperçu : les 23 CSV sur le disque (mode serveur) et Donnees.instantane().

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_import_regles.py" -v
"""
import csv as module_csv
import decimal
import datetime
import hashlib
import io
import json
import re
import unicodedata
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, charger_scripts, preregler_profil

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DEMO = RACINE / "donnees" / "demo"
SCRIPTS = [
    "js/lib/papaparse.min.js",
    "js/schema.js",
    "js/donnees.js",
    "js/stockage-demo.js",
    "js/modules/import-regles.js",
]
MAINTENANT = "2026-10-21 09:30"
TYPES_ATTENDUS = ["localisations", "equipements", "articles", "fournisseurs", "techniciens", "habilitations",
                  "codes", "compteurs", "controles", "gammes", "historique"]


# ---------------------------------------------------------------------------
# Textes (règles écrites ici, sans lire le JavaScript)
# ---------------------------------------------------------------------------

def sans_accents(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte) if not unicodedata.combining(c))


def comparable(texte):
    """§18.4 : minuscules, sans accents, ponctuation et espaces réduits."""
    t = sans_accents((texte or "").strip()).lower().replace("œ", "oe").replace("æ", "ae")
    return " ".join(re.findall(r"[a-z0-9]+", t))


def cle(texte):
    """Clé naturelle : casse, accents et espaces ignorés (ponctuation gardée)."""
    return " ".join(sans_accents((texte or "").strip()).lower().split())


MOTIFS_PROTECTION = [r"[0-9]+([.,][0-9]+)?", r"[0-9]+([.,][0-9]+)?[eE][+-]?[0-9]+",
                     r"[0-9]{1,4}[/.\-][0-9]{1,2}([/.\-][0-9]{1,4})?", r"[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?",
                     r"[0-9]+([.,][0-9]+)?\s?%"]


def a_proteger(valeur, protege):
    """§3.2, pour un champ texte."""
    return valeur != "" and bool(protege or re.match(r"[=+\-@\t\r]", valeur) or valeur.startswith("'")
                                 or any(re.fullmatch(m, valeur.strip(" \t\r\n")) for m in MOTIFS_PROTECTION))


def relire(valeur, protege):
    return valeur[1:] if valeur.startswith("'") and a_proteger(valeur[1:], protege) else valeur


def ecrire_cellule(valeur):
    """Cellule CSV de Prévo (§3.1 et §3.2) pour un texte."""
    v = "'" + valeur if a_proteger(valeur, False) else valeur
    return '"' + v.replace('"', '""') + '"' if re.search(r'[;"\r\n]|^[ \t]|[ \t]$', v) else v


def canon(nombre):
    texte = format(decimal.Decimal(nombre).normalize(), "f")
    return "0" if texte == "-0" else texte


def lire_date(valeur):
    heure = r"(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?"
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})" + heure, valeur)
    if m:
        annee, mois, jour = m.groups()
    else:
        m = re.fullmatch(r"(\d{1,2})([/.\-])(\d{1,2})\2(\d{4})" + heure, valeur)
        if not m:
            return None
        jour, _, mois, annee = m.groups()
    try:
        return datetime.date(int(annee), int(mois), int(jour)).isoformat()
    except ValueError:
        return None


def lire_decimal(valeur):
    t = re.sub(r"\s", "", valeur).replace(",", ".", 1)
    return canon(t) if re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)", t) else None


def lire_entier(valeur):
    t = re.sub(r"\s", "", valeur).replace(",", ".", 1)
    return canon(t.split(".")[0]) if re.fullmatch(r"[+-]?\d+(\.0*)?", t) else None


BOOLEENS = {"1": "1", "0": "0", "vrai": "1", "faux": "0", "oui": "1", "non": "0", "true": "1", "false": "0", "x": "1"}
EQUIVALENCES = {("statut", "a l arret"): "arrêt"}   # seules équivalences de table utilisées par ces grilles


# ---------------------------------------------------------------------------
# Champs des types (ceux des grilles de ce fichier ; libellés du schéma, §4)
# ---------------------------------------------------------------------------

class Champ:
    def __init__(self, cle_champ, libelle, genre, colonne=None, obligatoire=False, cle_naturelle=False,
                 valeurs=None, defaut=None, protege=False):
        self.cle, self.libelle, self.genre, self.colonne = cle_champ, libelle, genre, colonne
        self.obligatoire, self.cle_naturelle, self.valeurs = obligatoire, cle_naturelle, valeurs
        self.defaut, self.protege = defaut, protege


def C(*arguments, **options):
    return Champ(*arguments, **options)


EQUIPEMENT = C("equipement", "Équipement", "texte", obligatoire=True, cle_naturelle=True, protege=True)
TYPES_PY = {
    "localisations": [C("chemin", "Chemin", "texte", obligatoire=True, cle_naturelle=True),
                      C("type", "Type", "choix", "type", valeurs=["site", "atelier", "ligne"])],
    "equipements": [
        C("repere", "Repère", "texte", "repere", True, True, protege=True),
        C("designation", "Désignation", "texte", "designation", True),
        C("chemin_localisation", "Localisation", "texte"),
        C("site", "Site", "texte"), C("atelier", "Atelier", "texte"), C("ligne", "Ligne", "texte"),
        C("parent", "Équipement parent", "texte", protege=True),
        C("marque", "Marque", "texte", "marque"),
        C("num_serie", "Numéro de série", "texte", "num_serie", protege=True),
        C("date_mes", "Date de mise en service", "date", "date_mes"),
        C("criticite", "Criticité", "choix", "criticite", valeurs=["A", "B", "C"], defaut="B"),
        C("statut", "Statut", "choix", "statut", valeurs=["en service", "arrêt", "rebut"], defaut="en service"),
        C("heures_fonct_jour", "Heures", "decimal", "heures_fonct_jour"),
        C("valeur_remplacement", "Valeur de remplacement", "decimal", "valeur_remplacement")],
    "articles": [
        C("reference", "Référence", "texte", "reference", True, True, protege=True),
        C("designation", "Désignation", "texte", "designation", True),
        C("stock_initial", "Stock initial", "decimal"),
        C("stock_securite", "Stock de sécurité", "decimal", "stock_securite"),
        C("delai_jours", "Délai", "entier", "delai_jours"),
        C("prix_unitaire", "Prix unitaire", "decimal", "prix_unitaire"),
        C("fournisseur", "Fournisseur", "texte"),
        C("critique", "Article critique", "booleen", "critique", defaut="0")],
    "fournisseurs": [C("nom", "Nom", "texte", "nom", True, True), C("contact", "Contact", "texte", "contact"),
                     C("telephone", "Téléphone", "texte", "telephone", protege=True),
                     C("email", "E-mail", "texte", "email")],
    "techniciens": [C("nom", "Nom", "texte", "nom", True, True), C("prenom", "Prénom", "texte", "prenom", cle_naturelle=True),
                    C("metier", "Métier", "texte", "metier"), C("taux_horaire", "Taux horaire", "decimal", "taux_horaire"),
                    C("capacite_h_semaine", "Capacité", "decimal", "capacite_h_semaine")],
    "habilitations": [C("technicien", "Technicien", "texte", obligatoire=True, cle_naturelle=True),
                      C("intitule", "Intitulé", "texte", "intitule", True, True),
                      C("date_obtention", "Date d'obtention", "date", "date_obtention"),
                      C("date_echeance", "Date d'échéance", "date", "date_echeance")],
    "codes": [C("famille", "Famille", "choix", "famille", True, True, valeurs=["symptôme", "cause", "remède"]),
              C("code", "Code", "texte", "code", True, True), C("libelle", "Libellé", "texte", "libelle", True)],
    "compteurs": [EQUIPEMENT, C("libelle", "Libellé", "texte", "libelle", True, True), C("unite", "Unité", "texte", "unite")],
    "controles": [EQUIPEMENT, C("nature", "Nature du contrôle", "texte", "nature", True, True),
                  C("periodicite_mois", "Périodicité", "entier", "periodicite_mois"),
                  C("organisme", "Organisme", "texte", "organisme"),
                  C("derniere_date", "Date du dernier contrôle", "date", "derniere_date")],
    "gammes": [EQUIPEMENT, C("libelle", "Libellé", "texte", "libelle", True, True),
               C("periodicite_jours", "Périodicité", "entier", "periodicite_jours"),
               C("operations", "Opérations", "texte"), C("valeur_attendue", "Valeur attendue", "texte")],
}
TABLE = {"localisations": "localisations", "equipements": "equipements", "articles": "articles",
         "fournisseurs": "fournisseurs", "techniciens": "techniciens", "habilitations": "habilitations",
         "codes": "codes_defaillance", "compteurs": "compteurs", "controles": "controles_reglementaires",
         "gammes": "gammes"}
TABLES_TYPE = {"localisations": ["localisations"], "equipements": ["localisations", "equipements"],
               "articles": ["fournisseurs", "articles", "mouvements_stock"], "fournisseurs": ["fournisseurs"],
               "techniciens": ["techniciens"], "habilitations": ["habilitations"], "codes": ["codes_defaillance"],
               "compteurs": ["compteurs"], "controles": ["controles_reglementaires"], "gammes": ["gammes", "gamme_operations"]}
CLES = {
    "equipements": lambda b: cle(b.get("repere", "")),
    "articles": lambda b: cle(b.get("reference", "")),
    "fournisseurs": lambda b: cle(b.get("nom", "")),
    "techniciens": lambda b: cle(b.get("nom", "")) + "|" + cle(b.get("prenom", "")),
    "habilitations": lambda b: b.get("technicien_id", "") + "|" + cle(b.get("intitule", "")),
    "codes": lambda b: b.get("famille", "") + "|" + cle(b.get("code", "")),
    "compteurs": lambda b: b.get("equipement_id", "") + "|" + cle(b.get("libelle", "")),
    "controles": lambda b: b.get("equipement_id", "") + "|" + cle(b.get("nature", "")),
    "gammes": lambda b: b.get("equipement_id", "") + "|" + cle(b.get("libelle", "")),
}
# Défauts du schéma (§4) des tables écrites par ces grilles
DEFAUTS = {"equipements": {"criticite": "B", "statut": "en service", "actif": "1"},
           "articles": {"critique": "0", "actif": "1"}, "techniciens": {"actif": "1"},
           "gammes": {"declencheur": "date", "actif": "1"}, "controles_reglementaires": {"observations_levees": "0"}}
FORMATS_ID = {"localisations": ("LOC-", 4), "equipements": ("EQ-", 4), "articles": ("ART-", 4),
              "mouvements_stock": ("MVT-", 6), "fournisseurs": ("FOU-", 4), "techniciens": ("TEC-", 4),
              "habilitations": ("HAB-", 4), "codes_defaillance": ("CD-", 4), "compteurs": ("CPT-", 4),
              "controles_reglementaires": ("CTR-", 4), "gammes": ("GAM-", 4), "gamme_operations": ("GOP-", 6)}
PROTEGES = {"repere", "num_serie", "reference", "ref_fabricant", "telephone"}


def convertir(champ, brut):
    """→ (valeur, erreur, note) ; erreur et note sont des tuples de mots-clés de la raison attendue."""
    v = (brut or "").strip()
    if v == "":
        return "", None, None
    if champ.genre == "texte":
        return relire(v, champ.protege), None, None
    if v.startswith("'"):
        v = v[1:].strip()
    lu = None
    if champ.genre == "date":
        lu = lire_date(v)
    elif champ.genre == "decimal":
        lu = lire_decimal(v)
    elif champ.genre == "entier":
        lu = lire_entier(v)
    elif champ.genre == "booleen":
        lu = BOOLEENS.get(v.lower())
    elif champ.genre == "choix":
        cherche = comparable(v)
        lu = EQUIVALENCES.get((champ.cle, cherche))
        if lu is None:
            lu = next((p for p in champ.valeurs if comparable(p) in (cherche, cherche[:-1] if cherche.endswith("s") else None)), None)
        if lu is None:
            return v, (champ.libelle, v, "valeurs permises"), None
        return lu, None, (None if comparable(lu) == cherche else (champ.libelle, "lu comme", lu))
    return (lu, None, None) if lu is not None else (v, (champ.libelle, v), None)


# ---------------------------------------------------------------------------
# Calcul Python indépendant de l'aperçu (§18.5)
# ---------------------------------------------------------------------------

def lire_demo():
    base, colonnes = {}, {}
    for fichier in sorted(DOSSIER_DEMO.glob("*.csv")):
        lecteur = module_csv.DictReader(io.StringIO(fichier.read_text(encoding="utf-8-sig")), delimiter=";")
        base[fichier.stem] = [{k: relire(v or "", k in PROTEGES) for k, v in ligne.items()} for ligne in lecteur]
        colonnes[fichier.stem] = lecteur.fieldnames
    return base, colonnes


class Prevu:
    """Ligne à créer ; son identifiant est donné à la fin, dans l'ordre du fichier."""
    def __init__(self, table, valeurs, ligne):
        self.table, self.valeurs, self.ligne, self.id = table, valeurs, ligne, None


class Noeud:
    """Localisation de l'arbre : existante (id connu, ligne de la base) ou prévue (id à la fin)."""
    def __init__(self, libelle, genre, parent, id_noeud=None, ligne_base=None):
        self.libelle, self.type, self.parent, self.id, self.base = libelle, genre, parent, id_noeud, ligne_base
        self.table, self.ligne = "localisations", None


def ident(valeur):
    return valeur.id if isinstance(valeur, (Prevu, Noeud)) else valeur


class CalculPython:

    def __init__(self, base, colonnes):
        self.b, self.colonnes = base, colonnes

    # -- outils --------------------------------------------------------------
    def nouvelle_ligne(self, table, valeurs):
        ligne = {nom: DEFAUTS.get(table, {}).get(nom, "") for nom in self.colonnes[table]}
        ligne.update(valeurs)
        return ligne

    def index(self, table, fonction):
        index = {}
        for ligne in self.b[table]:
            k = fonction(ligne)
            if k not in index or (index[k].get("actif") == "0" and ligne.get("actif") != "0"):
                index[k] = ligne
        return index

    def equipement(self, repere):
        return self.index("equipements", lambda l: cle(l["repere"])).get(cle(repere))

    def technicien(self, nom):
        k, tous = cle(nom), self.b["techniciens"]
        trouves = [t for t in tous if k in (cle(t["prenom"] + " " + t["nom"]), cle(t["nom"] + " " + t["prenom"]))]
        trouves = trouves or [t for t in tous if cle(t["nom"]) == k]
        return trouves[0] if len(trouves) == 1 else None

    def stock(self, article_id):
        s = decimal.Decimal(0)
        for m in sorted((m for m in self.b["mouvements_stock"] if m["article_id"] == article_id), key=lambda m: (m["date"], m["id"])):
            q = decimal.Decimal(m["quantite"] or "0")
            s = q if m["type"] == "inventaire" else s + q if m["type"] in ("entrée", "retour") else s - q if m["type"] == "sortie" else s
        return canon(s)

    def refuser(self, ligne, raisons):
        ligne.update(action="refusee", changements=[], cible="")
        ligne["raisons"] += raisons

    def chemin(self, noeud):
        morceaux = []
        while noeud is not None:
            morceaux.insert(0, noeud.libelle)
            noeud = noeud.parent
        return " > ".join(morceaux)

    def afficher(self, colonne, valeur):
        if isinstance(valeur, Noeud):
            return self.chemin(valeur)
        if colonne == "localisation_id":
            return self.chemin(next(n for n in self.arbre if n.id == valeur)) if valeur else ""
        if isinstance(valeur, Prevu):
            return valeur.valeurs.get("repere") or valeur.valeurs.get("nom")
        if colonne == "parent_id" and valeur:
            return next(e["repere"] for e in self.b["equipements"] if e["id"] == valeur)
        if colonne == "fournisseur_id" and valeur:
            return next(f["nom"] for f in self.b["fournisseurs"] if f["id"] == valeur)
        return valeur

    def poser(self, ligne, colonne, valeur):
        if "_objet" in ligne:
            ligne["_objet"].valeurs[colonne] = valeur
        else:
            ligne["_cibles"].append((None, colonne, valeur, None))

    def prevoir(self, objet):
        self.crees.append(objet)
        return objet

    # -- arbre des localisations ----------------------------------------------
    def construire_arbre(self):
        par_id = {l["id"]: Noeud(l["libelle"], l["type"], None, l["id"], l) for l in self.b["localisations"]}
        for l in self.b["localisations"]:
            par_id[l["id"]].parent = par_id.get(l["parent_id"])
        return list(par_id.values())

    def enfant(self, parent, libelle):
        return next((n for n in self.arbre if n.parent is parent and cle(n.libelle) == cle(libelle)), None)

    def resoudre(self, elements):
        parent, debut = self.enfant(None, elements[0][0]), 1
        if parent is None:
            ancres = [n for n in self.arbre if cle(n.libelle) == cle(elements[0][0])]
            if len(ancres) > 1:
                return None, ("plusieurs localisations", elements[0][0])
            parent = ancres[0] if ancres else None
            debut = 1 if parent else 0
        for libelle, genre in elements[debut:]:
            noeud = self.enfant(parent, libelle)
            if noeud is None:
                genre = genre or {None: "site", "site": "atelier", "atelier": "ligne"}.get(parent.type if parent else None)
                if genre is None:
                    return None, ("trois niveaux",)
                noeud = self.prevoir(Noeud(libelle, genre, parent))
                self.arbre.append(noeud)
            parent = noeud
        return parent, None

    @staticmethod
    def decouper(chemin):
        morceaux = [m.strip() for m in (chemin.split(">") if ">" in chemin else re.split(r"[\\/]", chemin))]
        if "" in morceaux:
            return None, ("incomplet",)
        if len(morceaux) > 3:
            return None, ("trois niveaux",)
        return morceaux, None

    # -- les deux passes -------------------------------------------------------
    def preparer(self, type_, grille, choix, mettre_a_jour=True, premier=2, maintenant=MAINTENANT):
        self.type, self.maj, self.maintenant = type_, mettre_a_jour, maintenant
        self.table, self.lignes, self.crees, self.cles, self.vus = TABLE[type_], [], [], {}, {}
        self.arbre, self.fournisseurs, self.etats = self.construire_arbre(), {}, {}
        colonnes = {champ: colonne for colonne, champ in choix.items()}
        for rang, cellules in enumerate(grille):
            if any((c or "").strip() for c in cellules):
                self.passe1(rang, premier + rang, cellules, colonnes)
        for ligne in self.lignes:
            if ligne["action"] != "refusee":
                getattr(self, "passe2_" + type_, self.decider)(ligne)
        if type_ == "equipements":
            self.cascade()
        return self.terminer()

    def passe1(self, rang, numero, cellules, colonnes):
        ligne = {"numero": numero, "rang": rang, "action": "creer", "raisons": [], "valeurs": {}, "changements": [],
                 "cible": "", "_brouillon": {}, "_cibles": [], "_manquants": [], "_vides": []}
        self.lignes.append(ligne)
        erreurs, v, brouillon = [], ligne["valeurs"], ligne["_brouillon"]
        for champ in TYPES_PY[self.type]:
            if champ.cle not in colonnes:
                if champ.obligatoire:
                    (erreurs if champ.cle_naturelle else ligne["_manquants"]).append((champ.libelle, "obligatoire"))
                continue
            colonne = colonnes[champ.cle]
            valeur, erreur, note = convertir(champ, cellules[colonne] if colonne < len(cellules) else "")
            if note:
                ligne["raisons"].append(note)
            if erreur:
                v[champ.cle] = valeur
                erreurs.append(erreur)
                continue
            if valeur == "":
                if champ.obligatoire:
                    (erreurs if champ.cle_naturelle else ligne["_manquants"]).append((champ.libelle, "obligatoire"))
                else:
                    ligne["_vides"].append(champ)
                continue
            v[champ.cle] = valeur
            if champ.colonne:
                brouillon[champ.colonne] = valeur
                if not champ.cle_naturelle:
                    ligne["_cibles"].append((champ, champ.colonne, valeur, None))
        if not erreurs and v.get("equipement"):
            trouve = self.equipement(v["equipement"])
            if trouve is None:
                erreurs.append((v["equipement"], "introuvable"))
            else:
                brouillon["equipement_id"] = trouve["id"]
        if not erreurs and v.get("technicien"):
            trouve = self.technicien(v["technicien"])
            if trouve is None:
                erreurs.append((v["technicien"], "introuvable"))
            else:
                brouillon["technicien_id"] = trouve["id"]
        for champ_chemin in ("chemin", "chemin_localisation"):
            if not erreurs and v.get(champ_chemin):
                elements, erreur = self.decouper(v[champ_chemin])
                if erreur:
                    erreurs.append(erreur)
        if erreurs:
            return self.refuser(ligne, erreurs)
        if self.type == "localisations":
            return
        k = CLES[self.type](brouillon)
        if k in self.cles:
            tete = self.cles[k]
            if self.type == "gammes" and v.get("operations"):
                ligne["_tete"] = tete
                return
            return self.refuser(ligne, [("doublon", "ligne %d" % tete["numero"])])
        existante = self.index(self.table, CLES[self.type]).get(k)
        if existante is None and ligne["_manquants"]:
            return self.refuser(ligne, ligne["_manquants"])
        self.cles[k] = ligne
        if existante is not None:
            ligne["_existante"] = existante
            return
        valeurs = dict(brouillon)
        if self.type == "articles":
            valeurs["stock"] = "0"
        ligne["_objet"] = self.prevoir(Prevu(self.table, self.nouvelle_ligne(self.table, valeurs), ligne))
        for champ in ligne["_vides"]:
            if champ.defaut is not None and champ.colonne:
                affiche = {"0": "non", "1": "oui"}[champ.defaut] if champ.genre == "booleen" else champ.defaut
                ligne["raisons"].append((champ.libelle, "par défaut", affiche))

    def decider(self, ligne, ajouts=False):
        existante = ligne.get("_existante")
        if existante is None:
            ligne["action"] = "creer"
            return
        ligne["cible"] = existante["id"]
        changes = {}
        for champ, colonne, valeur, avant in ligne["_cibles"]:
            ancien = existante.get(colonne, "") if avant is None else avant
            genre = champ.genre if champ else "ref"
            if isinstance(valeur, (Prevu, Noeud)):
                pareil = False
            elif genre in ("decimal", "entier") and lire_decimal(ancien) is not None:
                pareil = lire_decimal(ancien) == valeur
            else:
                pareil = ancien.strip() == valeur
            if pareil:
                continue
            changes[colonne] = valeur
            ligne["changements"].append((colonne, self.afficher(colonne, ancien), self.afficher(colonne, valeur)))
        if not changes and not ajouts:
            ligne["action"] = "identique"
            return
        if not self.maj:
            ligne.update(action="identique", changements=[])
            ligne["raisons"].append(("mise à jour non demandée",))
            return
        ligne["action"] = "mettre_a_jour"
        ligne.setdefault("_modifier", [])
        if changes:
            ligne["_modifier"].insert(0, (self.table, existante["id"], changes))

    # -- règles propres à chaque type -----------------------------------------
    def passe2_localisations(self, ligne):
        v = ligne["valeurs"]
        morceaux, _ = self.decouper(v["chemin"])
        elements = [(m, None) for m in morceaux]
        elements[-1] = (elements[-1][0], v.get("type"))
        noeud, erreur = self.resoudre(elements)
        if erreur:
            return self.refuser(ligne, [erreur])
        if noeud.id is None and noeud.base is None:
            if noeud.ligne is not None:
                return self.refuser(ligne, [("doublon", "ligne %d" % noeud.ligne["numero"])])
            noeud.ligne, ligne["_objet"], ligne["action"] = ligne, noeud, "creer"
            if v.get("type"):
                noeud.type = v["type"]
            return
        if id(noeud) in self.vus:
            return self.refuser(ligne, [("doublon", "ligne %d" % self.vus[id(noeud)]["numero"])])
        self.vus[id(noeud)] = ligne
        ligne["_existante"] = noeud.base
        self.decider(ligne)

    def passe2_equipements(self, ligne):
        v = ligne["valeurs"]
        if v.get("parent"):
            k = cle(v["parent"])
            if k == cle(v["repere"]):
                return self.refuser(ligne, [("propre parent",)])
            existant = self.equipement(v["parent"])
            if existant is not None:
                ligne["_parent"] = (existant["id"], None)
            elif k in self.cles:
                ligne["_parent"] = (self.cles[k]["_objet"], self.cles[k])
            else:
                return self.refuser(ligne, [("parent", v["parent"], "introuvable")])
            self.poser(ligne, "parent_id", ligne["_parent"][0])
        if v.get("chemin_localisation"):
            elements = [(m, None) for m in self.decouper(v["chemin_localisation"])[0]]
        else:
            elements = [(v[n], n) for n in ("site", "atelier", "ligne") if v.get(n)]
        if elements:
            noeud, erreur = self.resoudre(elements)
            if erreur:
                return self.refuser(ligne, [erreur])
            self.poser(ligne, "localisation_id", noeud if noeud.id is None else noeud.id)
        self.decider(ligne)

    def cascade(self):
        """Un équipement dont le parent (ligne du fichier) est refusé est refusé à son tour."""
        change = True
        while change:
            change = False
            for ligne in [l for l in self.lignes if l["action"] in ("creer", "mettre_a_jour") and "_parent" in l]:
                ligne_parent = ligne["_parent"][1]
                if ligne_parent is not None and ligne_parent["action"] == "refusee":
                    self.refuser(ligne, [("parent", "refusé", "ligne %d" % ligne_parent["numero"])])
                    change = True

    def passe2_articles(self, ligne):
        v = ligne["valeurs"]
        if v.get("fournisseur"):
            k = cle(v["fournisseur"])
            existant = self.index("fournisseurs", lambda f: cle(f["nom"])).get(k)
            if existant is not None:
                valeur = existant["id"]
            else:
                if k not in self.fournisseurs:
                    self.fournisseurs[k] = self.prevoir(Prevu("fournisseurs", self.nouvelle_ligne("fournisseurs", {"nom": v["fournisseur"]}), None))
                valeur = self.fournisseurs[k]
            self.poser(ligne, "fournisseur_id", valeur)
        quantite = v.get("stock_initial")
        if quantite is not None and "_objet" in ligne:
            ligne["_objet"].valeurs["stock"] = quantite
        elif quantite is not None:
            ligne["_cibles"].append((Champ("stock", "Stock", "decimal"), "stock", quantite, self.stock(ligne["_existante"]["id"])))
        self.decider(ligne)
        nouveau = quantite is not None and (ligne["action"] == "creer" or (
            ligne["action"] == "mettre_a_jour" and any("stock" in c for _, _, c in ligne.get("_modifier", []))))
        if nouveau:
            article = ligne.get("_objet") or ligne["_existante"]["id"]
            self.prevoir(Prevu("mouvements_stock", self.nouvelle_ligne("mouvements_stock", {
                "date": self.maintenant, "article_id": article, "type": "inventaire", "quantite": quantite,
                "utilisateur": "Responsable", "commentaire": "import"}), ligne))

    def passe2_gammes(self, ligne):
        v, tete = ligne["valeurs"], ligne.get("_tete")
        source = tete if tete is not None else ligne
        if id(source) not in self.etats:
            if "_existante" in source:
                ops = [o for o in self.b["gamme_operations"] if o["gamme_id"] == source["_existante"]["id"]]
                self.etats[id(source)] = {"ordre": max([int(o["ordre"]) for o in ops] or [0]), "connues": {cle(o["operation"]): o for o in ops}}
            else:
                self.etats[id(source)] = {"ordre": 0, "connues": {}}
        etat = self.etats[id(source)]
        gamme = source["_objet"] if "_objet" in source else source["_existante"]["id"]
        liste = [o.strip() for o in v.get("operations", "").split(";")] if v.get("operations") else []
        attendues = [a.strip() for a in v.get("valeur_attendue", "").split(";")] if len(liste) > 1 else [v.get("valeur_attendue", "")]
        ajouts, modifications = [], []
        for i, operation in enumerate(liste):
            if not operation:
                continue
            attendue = attendues[i] if i < len(attendues) else ""
            connue = etat["connues"].get(cle(operation))
            if connue is None:
                etat["ordre"] += 1
                etat["connues"][cle(operation)] = self.prevoir(Prevu("gamme_operations", self.nouvelle_ligne("gamme_operations", {
                    "gamme_id": gamme, "ordre": str(etat["ordre"]), "operation": operation, "valeur_attendue": attendue}), ligne))
                ajouts.append(operation)
            elif isinstance(connue, dict) and attendue and attendue != connue["valeur_attendue"]:
                modifications.append((connue, attendue))
        if tete is not None:
            ligne["_cibles"] = []
            if "_objet" in tete:
                ligne["cible"] = ""
                ligne["action"] = "creer" if ajouts else "identique"
            ligne["raisons"].append(("opération", "ligne %d" % tete["numero"]) if ajouts else ("opération", "déjà"))
            if "_objet" in tete:
                return
            ligne["_existante"] = tete["_existante"]
        existante = "_existante" in ligne
        if existante:
            for operation in ajouts:
                ligne["changements"].append(("operation", "", operation))
            for connue, attendue in modifications:
                ligne["changements"].append(("valeur_attendue", connue["valeur_attendue"], attendue))
        self.decider(ligne, ajouts=bool(ajouts or modifications))
        if ligne["action"] == "mettre_a_jour":
            for connue, attendue in modifications:
                ligne["_modifier"].append(("gamme_operations", connue["id"], {"valeur_attendue": attendue}))

    # -- fin : identifiants, références, écritures ------------------------------
    def terminer(self):
        gardee = lambda l: l is not None and l["action"] in ("creer", "mettre_a_jour")
        utilises = set()

        def marquer(valeur):
            while isinstance(valeur, (Prevu, Noeud)) and id(valeur) not in utilises:
                utilises.add(id(valeur))
                valeur = valeur.parent if isinstance(valeur, Noeud) else None

        for objet in self.crees:
            if gardee(objet.ligne):
                if isinstance(objet, Noeud):
                    marquer(objet.parent)
                else:
                    for valeur in objet.valeurs.values():
                        marquer(valeur)
        for ligne in self.lignes:
            if gardee(ligne):
                for _, _, changes in ligne.get("_modifier", []):
                    for valeur in changes.values():
                        marquer(valeur)
        gardes = [o for o in self.crees if gardee(o.ligne) or (o.ligne is None and id(o) in utilises)]
        compteurs = {}
        for objet in gardes:
            prefixe, chiffres = FORMATS_ID[objet.table]
            if objet.table not in compteurs:
                compteurs[objet.table] = max([int(l["id"][len(prefixe):]) for l in self.b[objet.table]
                                              if l["id"].startswith(prefixe) and l["id"][len(prefixe):].isdigit()] or [0])
            compteurs[objet.table] += 1
            objet.id = prefixe + str(compteurs[objet.table]).zfill(chiffres)
        ecritures = {t: {"creer": [], "modifier": []} for t in TABLES_TYPE[self.type]}
        references = []
        for objet in gardes:
            if isinstance(objet, Noeud):
                ligne = {"id": objet.id, "libelle": objet.libelle, "parent_id": ident(objet.parent) or "", "type": objet.type}
            else:
                ligne = {k: ident(v) for k, v in objet.valeurs.items()}
                ligne["id"] = objet.id
            ecritures[objet.table]["creer"].append({k: ligne[k] for k in self.colonnes[objet.table]})
            if objet.ligne is None:
                references.append((objet.table, self.chemin(objet) if isinstance(objet, Noeud) else objet.valeurs["nom"], objet.id))
        for ligne in self.lignes:
            if gardee(ligne):
                for table, identifiant, changes in ligne.get("_modifier", []):
                    ecritures[table]["modifier"].append({"id": identifiant, "changes": {k: ident(v) for k, v in changes.items()}})
            if ligne["action"] == "creer":
                ligne["cible"] = (ligne.get("_objet") or ligne["_tete"]["_objet"]).id
            elif ligne["action"] != "refusee" and "_tete" in ligne and "_objet" in ligne["_tete"]:
                ligne["cible"] = ligne["_tete"]["_objet"].id
        totaux = {a: sum(1 for l in self.lignes if l["action"] == a) for a in ("creer", "mettre_a_jour", "identique", "refusee")}
        totaux.update(lignes=len(self.lignes), references=len(references))
        lignes = [{k: v for k, v in l.items() if not k.startswith("_")} for l in self.lignes]
        return {"lignes": lignes, "ecritures": ecritures, "references": references, "totaux": totaux}


# ---------------------------------------------------------------------------
# Grilles (en-têtes, lignes, correspondance colonne → champ)
# ---------------------------------------------------------------------------

E_EQUIPEMENTS = ["Code machine", "Désignation", "Localisation", "Équipement parent", "Constructeur", "N° de série",
                 "Mise en service", "Criticité", "État", "Heures par jour", "Valeur à neuf", "Commentaire"]
C_EQUIPEMENTS = {0: "repere", 1: "designation", 2: "chemin_localisation", 3: "parent", 4: "marque", 5: "num_serie",
                 6: "date_mes", 7: "criticite", 8: "statut", 9: "heures_fonct_jour", 10: "valeur_remplacement"}
SITE = "Site des Trois Vallées"


def ligne_eq(repere, designation="", chemin="", parent="", marque="", serie="", mes="", criticite="", etat="",
             heures="", valeur="", commentaire=""):
    return [repere, designation, chemin, parent, marque, serie, mes, criticite, etat, heures, valeur, commentaire]


G_EQUIPEMENTS = [
    ligne_eq("007", "Tour à commande numérique", SITE + " > Atelier Usinage > Cellule d'usinage CN", "", "Tornos",
             "0012345", "15/03/2021", "a", "En service", "7,5", "45 000,50", "neuf"),             # 2 créer, zéros gardés
    ligne_eq("CP-01", "Compresseur à vis 30 kW", criticite="B"),                                  # 3 mettre à jour A → B
    ligne_eq("cp-01.sec", "Sécheur d'air par réfrigération", "Atelier Utilités", "CP-01"),        # 4 identique (ancrage)
    ligne_eq("PN-01", "Cabine de peinture", SITE + " > Atelier Peinture > Cabine 1", "PN-00", mes="2022-06-01",
             etat="à l'arrêt"),                                                                    # 5 parent plus bas, réf. créées
    ligne_eq("007", "Tour bis"),                                                                   # 6 doublon de la ligne 2
    ligne_eq("PN-00", "Ligne de peinture", SITE + " > Atelier Peinture", criticite="C"),          # 7 créer
    ligne_eq("XX-01", "", mes="31/02/2020"),                                                        # 8 obligatoire + date illisible
    ligne_eq("XX-02", "Machine X; prototype", parent="ZZ-99"),                                     # 9 parent introuvable
    ligne_eq("XX-03", "Machine Y", criticite="Z"),                                                 # 10 hors liste
    ligne_eq("RA-01", "", SITE + " > Atelier Utilités > Local compresseurs", heures="20"),        # 11 mise à jour + réf.
    ligne_eq(""),                                                                                  # 12 vide : ignorée
    ligne_eq("XX-04", "Machine Z", SITE + " > Atelier Usinage > Cabine 1"),                       # 13 créer (2e « Cabine 1 »)
    ligne_eq("XX-06", "Machine enfant", parent="XX-07"),                                           # 14 parent refusé ensuite
    ligne_eq("XX-07", "Machine parente", "Cabine 1"),                                              # 15 localisation ambiguë
    ligne_eq("XX-08", "Machine W", parent="xx-08"),                                                # 16 son propre parent
]

E_ARTICLES = ["Réf.", "Désignation", "Fournisseur", "Qté stock", "Prix d'achat", "Stock mini", "Critique", "Délai"]
C_ARTICLES = {0: "reference", 1: "designation", 2: "fournisseur", 3: "stock_initial", 4: "prix_unitaire",
              5: "stock_securite", 6: "critique", 7: "delai_jours"}

E_FOURNISSEURS = ["Société", "Interlocuteur", "Tél", "Courriel"]
C_FOURNISSEURS = {0: "nom", 1: "contact", 2: "telephone", 3: "email"}
G_FOURNISSEURS = [
    ["Mécaroule Distribution", "", "0465710001", ""],
    ["Hydrau Pro", "Luc Martin", "0612345678", "contact@hydrau.example"],
    ["MECAROULE distribution", "Claire Rousseau", "", ""],
    ["", "Sans nom", "", ""],
    ["Fluidalpes Services", "Bruno Faure", "'0465710099", ""],
]

E_TECHNICIENS = ["Nom", "Prénom", "Métier", "Coût horaire", "Capacité"]
C_TECHNICIENS = {0: "nom", 1: "prenom", 2: "metier", 3: "taux_horaire", 4: "capacite_h_semaine"}
G_TECHNICIENS = [
    ["Moreau", "Julien", "Électricien", "45", ""],
    ["Durand", "Paul", "Mécanicien", "40,5", "35"],
    ["MOREAU", "julien", "", "", ""],
    ["Lambert", "Sophie", "", "", "35"],
]

E_HABILITATIONS = ["Technicien", "Habilitation", "Obtenue le", "Échéance"]
C_HABILITATIONS = {0: "technicien", 1: "intitule", 2: "date_obtention", 3: "date_echeance"}
G_HABILITATIONS = [
    ["Julien Moreau", "BR", "10/03/2025", "10/03/2028"],
    ["Benali Karim", "H0V", "", "14/05/2028"],
    ["Karim Benali", "B1V", "01/02/2026", ""],
    ["Jean Inconnu", "BR", "", ""],
    ["Moreau Julien", "br", "", ""],
    ["Garnier", "H0V", "", ""],
]

E_CODES = ["Famille", "Code", "Libellé"]
C_CODES = {0: "famille", 1: "code", 2: "libelle"}
G_CODES = [
    ["Symptomes", "S01", "Fuite"],
    ["cause", "C99", "Corrosion"],
    ["Remède", "R01", "Remplacement complet de la pièce"],
    ["Défaut", "D01", "Divers"],
    ["CAUSE", "c99", "Corrosion bis"],
]

E_COMPTEURS = ["Repère", "Libellé", "Unité"]
C_COMPTEURS = {0: "equipement", 1: "libelle", 2: "unite"}
G_COMPTEURS = [
    ["CP-01", "Compteur horaire de marche", "heures"],
    ["CP-01", "Compteur de démarrages", "démarrages"],
    ["ZZ-99", "Compteur", "h"],
]

E_CONTROLES = ["Équipement", "Nature du contrôle", "Périodicité (mois)", "Dernier contrôle", "Organisme"]
C_CONTROLES = {0: "equipement", 1: "nature", 2: "periodicite_mois", 3: "derniere_date", 4: "organisme"}
G_CONTROLES = [
    ["PT-01", "Vérification générale périodique du pont roulant", "12", "10/02/2026", "Bureau Alpin de Contrôle (démo)"],
    ["CP-01", "Contrôle des soupapes", "24", "2026-01-15", "Bureau X"],
    ["CP-01", "Contrôle des soupapes bis", "douze", "", ""],
]

E_GAMMES = ["Équipement", "Gamme", "Périodicité", "Opération", "Valeur attendue"]
C_GAMMES = {0: "equipement", 1: "libelle", 2: "periodicite_jours", 3: "operations", 4: "valeur_attendue"}
G_GAMMES = [
    ["CP-01", "Graissage annuel", "365", "Graisser les paliers", "Graisse visible"],
    ["CP-01", "Graissage annuel", "", "Contrôler le moteur", ""],
    ["CP-01", "graissage annuel", "", "", ""],
    ["CP-01", "Entretien mensuel du compresseur CP-01", "30", "Contrôler le niveau d'huile ; Vérifier la courroie",
     "Entre mini et maxi (jauge) ; Tension correcte"],
    ["ZZ-99", "Gamme X", "", "", ""],
    ["PT-01", "Visite du pont", "90", "Contrôler les freins;Contrôler le câble ;  ", "Freinage OK;"],
    ["CP-01", "Graissage annuel", "", "graisser les paliers", "Autre"],
]

E_LOCALISATIONS = ["Chemin", "Type"]
C_LOCALISATIONS = {0: "chemin", 1: "type"}
G_LOCALISATIONS = [
    [SITE, ""],
    [SITE + " > Atelier Logistique > Quai 1", ""],
    [SITE + " / Atelier Logistique", ""],
    ["Atelier Usinage", ""],
    ["Nouveau site", "Site"],
    [SITE + " > Atelier Usinage", "ligne"],
    ["A > B > C > D", ""],
    [SITE + " >  > X", ""],
    [SITE + " > Atelier Assemblage-conditionnement > Ligne d'assemblage", "atelier"],
    ["Cellule d'usinage CN > Poste 1", ""],
]


def grille_articles(stock_rou_001):
    return [
        ["ROU-900", "Roulement 6310", "Nouveau Fournisseur SA", "12", "4,50", "2", "x", "5"],
        ["ROU-001", "", "Mécaroule Distribution", stock_rou_001, "4,80", "", "", ""],
        ["rou-002", "", "nouveau fournisseur sa", "", "6", "", "", ""],
        ["ROU-900", "Doublon", "", "", "", "", "", ""],
        ["ROU-902", "Joint torique", "", "abc", "", "", "", ""],
        ["ROU-903", "Courroie", "", "", "", "", "", ""],
        ["007", "Joint plat", "Autre Fournisseur", "0", "", "", "non", ""],
        ["ROU-904", "Bague", "Fournisseur Fantôme", "", "", "", "", "3,5"],
    ]


def correspondance(entetes, choix):
    return [{"colonne": i, "entete": e, "champ": choix.get(i, ""), "statut": "sure" if i in choix else "non_utilisee",
             "raison": ""} for i, e in enumerate(entetes)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class CasImport(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tables = {f.stem: f.read_bytes().decode("utf-8-sig") for f in DOSSIER_DEMO.glob("*.csv")}
        cls.base, cls.colonnes = lire_demo()

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable' });
          await Donnees.chargerTout();
        }""", self.tables)

    def preparer(self, type_, entetes, grille, choix, options=None):
        options = dict({"maintenant": MAINTENANT}, **(options or {}))
        return self.page.evaluate("([t, l, c, o]) => Import.preparer(t, l, c, o)",
                                  [type_, grille, correspondance(entetes, choix), options])

    def attendu(self, type_, grille, choix, **options):
        return CalculPython(self.base, self.colonnes).preparer(type_, grille, choix, **options)

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
                self.assertEqual(sorted((c["champ"], c["avant"], c["apres"]) for c in lo["changements"]),
                                 sorted(la["changements"]))
                self.verifier_raisons(lo["raisons"], la["raisons"])
        self.assertEqual(obtenu["ecritures"], attendu["ecritures"])
        self.assertEqual([(r["table"], r["libelle"], r["id"]) for r in obtenu["referencesCreees"]], attendu["references"])
        self.assertEqual(obtenu["totaux"], attendu["totaux"])


class TestTypesEtComparable(CasImport):

    def test_types_declares_et_champs_complets(self):
        types = self.page.evaluate("() => JSON.parse(JSON.stringify(Import.TYPES))")
        self.assertEqual(sorted(types), sorted(TYPES_ATTENDUS))
        noms_schema = self.page.evaluate("() => Object.fromEntries(Schema.nomsTables().map((t) => [t, Schema.table(t).champs.map((c) => c.nom)]))")
        for cle_type, description in types.items():
            with self.subTest(type=cle_type):
                self.assertEqual(description["cle"], cle_type)
                self.assertTrue(description["libelle"] and description["aide"])
                self.assertEqual(description["tables"], TABLES_TYPE.get(cle_type, ["ordres_travail", "ot_temps"]))
                self.assertTrue(any(c["cleNaturelle"] for c in description["champs"]))
                self.assertIsInstance(description["refs"], list)
                for champ in description["champs"]:
                    for propriete in ("cle", "libelle", "table", "champ", "type", "obligatoire", "synonymes", "cleNaturelle", "exemple"):
                        self.assertIn(propriete, champ, (cle_type, champ.get("cle"), propriete))
                    self.assertNotEqual(champ["champ"], "id", "identifiant Prévo jamais pris dans le fichier (D85)")
                    if champ["champ"]:
                        self.assertIn(champ["champ"], noms_schema[champ["table"]], (cle_type, champ["cle"]))
                self.assertEqual(len({c["cle"] for c in description["champs"]}), len(description["champs"]))
        repere = next(c for c in types["equipements"]["champs"] if c["cle"] == "repere")
        self.assertIn("code machine", repere["synonymes"])
        self.assertTrue(repere["cleNaturelle"] and repere["obligatoire"])
        historique = {c["cle"]: c for c in types["historique"]["champs"]}
        for virtuel in ("ancien_numero", "temps_passe_h", "technicien", "equipement"):
            self.assertIn(virtuel, historique)
            self.assertIsNone(historique[virtuel]["champ"])
        self.assertEqual(historique["temps_passe_h"]["type"], "decimal")

    def test_exemples_des_champs_valables(self):
        # Chaque exemple (pour les modèles de T84) se convertit sans erreur.
        erreurs = self.page.evaluate("""() => {
          const erreurs = [];
          for (const type of Object.values(Import.TYPES)) {
            for (const champ of type.champs) {
              const lu = Import.interne.convertir(champ, champ.exemple);
              if (lu.erreur || String(champ.exemple).trim() === '') erreurs.push(type.cle + '.' + champ.cle + ' : ' + champ.exemple);
            }
          }
          return erreurs;
        }""")
        self.assertEqual(erreurs, [])

    def test_comparable(self):
        cas = {"N° de série": "n de serie", "  Prix  d’achat (€) ": "prix d achat", "ŒUVRE": "oeuvre",
               "Qté_stock": "qte stock", "Équipement parent": "equipement parent", "": ""}
        obtenu = self.page.evaluate("(cas) => cas.map((t) => Import.comparable(t))", list(cas))
        self.assertEqual(obtenu, list(cas.values()))
        self.assertEqual(obtenu, [comparable(t) for t in cas])

    def test_historique_delegue_ou_erreur_claire(self):
        message = self.page.evaluate("""() => { try { Import.preparer('historique', [['x']], [], {}); return 'pas d\\'erreur'; }
          catch (e) { return e.name + ' : ' + e.message; } }""")
        self.assertTrue(message.startswith("ErreurImport : "), message)
        self.assertIn("historique", message)
        rendu = self.page.evaluate("""() => {
          Import.preparerHistorique = (lignes, correspondance, options, outils) =>
            ({ appel: [lignes.length, correspondance.length, options.mettreAJour, typeof outils.comparable, typeof outils.convertir] });
          try { return Import.preparer('historique', [['a'], ['b']], [{ colonne: 0, champ: 'titre', statut: 'sure' }], { mettreAJour: false }); }
          finally { delete Import.preparerHistorique; }
        }""")
        self.assertEqual(rendu, {"appel": [2, 1, False, "function", "function"]})

    def test_erreurs_d_appel(self):
        messages = self.page.evaluate("""() => [
          () => Import.preparer('inconnu', [], [], {}),
          () => Import.preparer('fournisseurs', [], [{ colonne: 0, champ: 'nom', statut: 'sure' }, { colonne: 1, champ: 'nom', statut: 'a_confirmer' }], {}),
          () => Import.correspondance('inconnu', ['a'], [], null),
        ].map((f) => { try { f(); return 'aucune'; } catch (e) { return e.name; } })""")
        self.assertEqual(messages, ["ErreurImport"] * 3)


class TestCorrespondance(CasImport):

    def correspondance_js(self, type_, entetes, echantillon, memoire=None):
        return self.page.evaluate("([t, e, ech, m]) => Import.correspondance(t, e, ech, m)", [type_, entetes, echantillon, memoire])

    def test_synonymes_accents_casse_et_colonne_inconnue(self):
        resultat = self.correspondance_js("equipements", E_EQUIPEMENTS, G_EQUIPEMENTS)
        self.assertEqual([r["colonne"] for r in resultat], list(range(len(E_EQUIPEMENTS))))
        self.assertEqual({r["colonne"]: r["champ"] for r in resultat if r["champ"]}, C_EQUIPEMENTS)
        self.assertEqual([r["statut"] for r in resultat], ["sure"] * 11 + ["non_utilisee"])
        self.assertTrue(all(r["raison"] for r in resultat))
        for type_, entetes, choix in (("articles", E_ARTICLES, C_ARTICLES), ("fournisseurs", E_FOURNISSEURS, C_FOURNISSEURS),
                                      ("techniciens", E_TECHNICIENS, C_TECHNICIENS), ("habilitations", E_HABILITATIONS, C_HABILITATIONS),
                                      ("codes", E_CODES, C_CODES), ("compteurs", E_COMPTEURS, C_COMPTEURS),
                                      ("controles", E_CONTROLES, C_CONTROLES), ("gammes", E_GAMMES, C_GAMMES),
                                      ("localisations", E_LOCALISATIONS, C_LOCALISATIONS)):
            with self.subTest(type=type_):
                resultat = self.correspondance_js(type_, entetes, [])
                self.assertEqual({r["colonne"]: r["champ"] for r in resultat}, choix)
                self.assertEqual({r["statut"] for r in resultat}, {"sure"})
        # En-têtes en capitales, sans accents, avec ponctuation
        resultat = self.correspondance_js("equipements", ["CODE-MACHINE", "designation", "N DE SERIE", "etat"], [])
        self.assertEqual([(r["champ"], r["statut"]) for r in resultat],
                         [("repere", "sure"), ("designation", "sure"), ("num_serie", "sure"), ("statut", "sure")])

    def test_ambigue_proche_et_echantillon(self):
        entetes = ["Code machine", "DESIGNATION", "Désignation", "n° de série", "Date MES", "Truc", "Marque du moteur", "", "Repère"]
        dates = [["A1", "x", "y", "123", "15/03/2021", "t", "m", "", "R1"], ["A2", "x", "y", "124", "2021-03-16", "t", "m", "", "R2"]]
        resultat = self.correspondance_js("equipements", entetes, dates)
        self.assertEqual([(r["champ"], r["statut"]) for r in resultat], [
            ("", "a_confirmer"),               # même champ que « Repère » (titre exact, mieux placé)
            ("designation", "a_confirmer"),    # deux colonnes de même niveau pour la désignation
            ("", "a_confirmer"),
            ("num_serie", "sure"),
            ("date_mes", "sure"),              # synonyme, échantillon de dates
            ("", "non_utilisee"),
            ("marque", "a_confirmer"),         # titre proche (préfixe)
            ("", "non_utilisee"),              # colonne sans titre
            ("repere", "sure"),
        ])
        self.assertIn("Repère", resultat[0]["raison"])
        mots = [["A1", "x", "y", "123", "bientôt", "t", "m", "", "R1"], ["A2", "x", "y", "124", "jamais", "t", "m", "", "R2"]]
        resultat = self.correspondance_js("equipements", entetes, mots)
        self.assertEqual((resultat[4]["champ"], resultat[4]["statut"]), ("date_mes", "a_confirmer"))

    def test_memoire_du_poste(self):
        retenue = self.page.evaluate("""() => {
          Import.memoriserCorrespondance('fournisseurs', ['Société', 'Tél', 'Divers'], [
            { colonne: 0, champ: 'nom', statut: 'sure' }, { colonne: 1, champ: 'telephone', statut: 'a_confirmer' },
            { colonne: 2, champ: '', statut: 'non_utilisee' }]);
          return { brut: JSON.parse(localStorage.getItem('prevo.import')),
                   retenue: Import.correspondanceRetenue('fournisseurs', ['SOCIÉTÉ ', 'tél', 'divers']),
                   autre: Import.correspondanceRetenue('fournisseurs', ['Société', 'Tél']) };
        }""")
        self.assertEqual(retenue["retenue"], ["nom", "telephone", ""])
        self.assertIsNone(retenue["autre"])
        self.assertTrue(retenue["brut"])
        resultat = self.correspondance_js("fournisseurs", ["SOCIÉTÉ ", "tél", "divers"], [], "auto")
        self.assertEqual([(r["champ"], r["statut"]) for r in resultat], [("nom", "sure"), ("telephone", "sure"), ("", "non_utilisee")])
        self.assertIn("retenue lors d'un import précédent", resultat[0]["raison"])
        # Mémoire ignorée sur demande (null), et autre jeu d'en-têtes : correspondance automatique
        resultat = self.correspondance_js("fournisseurs", ["Société", "Tél", "Divers"], [], None)
        self.assertNotIn("retenue", resultat[0]["raison"])
        # Retenue aussi d'une page à l'autre du même poste (localStorage)
        self.page.reload()
        charger_scripts(self.page, SCRIPTS)
        self.assertEqual(self.page.evaluate("() => Import.correspondanceRetenue('fournisseurs', ['Société', 'Tél', 'Divers'])"),
                         ["nom", "telephone", ""])

    def test_memoire_illisible_ou_refusee(self):
        resultat = self.page.evaluate("""() => {
          localStorage.setItem('prevo.import', '{ pas du json');
          const illisible = Import.correspondanceRetenue('fournisseurs', ['Société']);
          const lire = Storage.prototype.getItem, ecrire = Storage.prototype.setItem;
          Storage.prototype.getItem = () => { throw new Error('refusé'); };
          Storage.prototype.setItem = () => { throw new Error('refusé'); };
          try {
            Import.memoriserCorrespondance('fournisseurs', ['Société'], [{ colonne: 0, champ: 'nom', statut: 'sure' }]);
            return [illisible, Import.correspondanceRetenue('fournisseurs', ['Société']),
                    Import.correspondance('fournisseurs', ['Société'], [], 'auto')[0].champ];
          } finally { Storage.prototype.getItem = lire; Storage.prototype.setItem = ecrire; }
        }""")
        self.assertEqual(resultat, [None, None, "nom"])


class TestApercu(CasImport):

    def test_equipements(self):
        self.comparer(self.preparer("equipements", E_EQUIPEMENTS, G_EQUIPEMENTS, C_EQUIPEMENTS),
                      self.attendu("equipements", G_EQUIPEMENTS, C_EQUIPEMENTS))

    def test_equipements_valeurs_converties_lisibles(self):
        apercu = self.preparer("equipements", E_EQUIPEMENTS, G_EQUIPEMENTS, C_EQUIPEMENTS)
        premiere = apercu["lignes"][0]
        self.assertEqual((premiere["valeurs"]["repere"], premiere["valeurs"]["num_serie"]), ("007", "0012345"))
        self.assertEqual(premiere["valeurs"]["date_mes"], "2021-03-15")
        self.assertEqual(premiere["valeurs"]["valeur_remplacement"], "45000.5")
        self.assertEqual(premiere["valeurs"]["criticite"], "A")
        self.assertEqual(apercu["totaux"]["refusee"], 7)
        self.assertNotIn(12, [l["numero"] for l in apercu["lignes"]], "ligne vide ignorée")

    def test_equipements_sans_mise_a_jour(self):
        self.comparer(self.preparer("equipements", E_EQUIPEMENTS, G_EQUIPEMENTS, C_EQUIPEMENTS, {"mettreAJour": False}),
                      self.attendu("equipements", G_EQUIPEMENTS, C_EQUIPEMENTS, mettre_a_jour=False))

    def test_equipements_une_colonne_par_niveau(self):
        entetes = ["Repère", "Désignation", "Atelier", "Ligne"]
        grille = [["XY-01", "Machine", "Atelier Usinage", "Ligne 9"], ["XY-02", "Machine 2", "Atelier Neuf", ""],
                  ["XY-03", "Machine 3", "", "Ligne 9"]]
        choix = {0: "repere", 1: "designation", 2: "atelier", 3: "ligne"}
        self.comparer(self.preparer("equipements", entetes, grille, choix), self.attendu("equipements", grille, choix))

    def test_articles_et_stock_initial(self):
        stock = decimal.Decimal(CalculPython(self.base, self.colonnes).stock("ART-0001")) + 5
        grille = grille_articles(str(stock).replace(".", ","))
        self.comparer(self.preparer("articles", E_ARTICLES, grille, C_ARTICLES),
                      self.attendu("articles", grille, C_ARTICLES))
        apercu = self.preparer("articles", E_ARTICLES, grille, C_ARTICLES)
        inventaires = apercu["ecritures"]["mouvements_stock"]["creer"]
        self.assertEqual([m["type"] for m in inventaires], ["inventaire"] * 3)
        self.assertEqual([m["commentaire"] for m in inventaires], ["import"] * 3)

    def test_fournisseurs_et_numero_de_premiere_ligne(self):
        self.comparer(self.preparer("fournisseurs", E_FOURNISSEURS, G_FOURNISSEURS, C_FOURNISSEURS),
                      self.attendu("fournisseurs", G_FOURNISSEURS, C_FOURNISSEURS))
        self.comparer(self.preparer("fournisseurs", E_FOURNISSEURS, G_FOURNISSEURS, C_FOURNISSEURS, {"numeroPremiereLigne": 5}),
                      self.attendu("fournisseurs", G_FOURNISSEURS, C_FOURNISSEURS, premier=5))

    def test_techniciens(self):
        self.comparer(self.preparer("techniciens", E_TECHNICIENS, G_TECHNICIENS, C_TECHNICIENS),
                      self.attendu("techniciens", G_TECHNICIENS, C_TECHNICIENS))

    def test_habilitations_prenom_nom_et_nom_prenom(self):
        self.comparer(self.preparer("habilitations", E_HABILITATIONS, G_HABILITATIONS, C_HABILITATIONS),
                      self.attendu("habilitations", G_HABILITATIONS, C_HABILITATIONS))

    def test_codes_famille_tolerante(self):
        self.comparer(self.preparer("codes", E_CODES, G_CODES, C_CODES), self.attendu("codes", G_CODES, C_CODES))

    def test_compteurs(self):
        self.comparer(self.preparer("compteurs", E_COMPTEURS, G_COMPTEURS, C_COMPTEURS),
                      self.attendu("compteurs", G_COMPTEURS, C_COMPTEURS))

    def test_controles(self):
        self.comparer(self.preparer("controles", E_CONTROLES, G_CONTROLES, C_CONTROLES),
                      self.attendu("controles", G_CONTROLES, C_CONTROLES))

    def test_gammes_et_operations(self):
        self.comparer(self.preparer("gammes", E_GAMMES, G_GAMMES, C_GAMMES), self.attendu("gammes", G_GAMMES, C_GAMMES))
        sans = self.preparer("gammes", E_GAMMES, G_GAMMES, C_GAMMES, {"mettreAJour": False})
        self.comparer(sans, self.attendu("gammes", G_GAMMES, C_GAMMES, mettre_a_jour=False))

    def test_localisations(self):
        self.comparer(self.preparer("localisations", E_LOCALISATIONS, G_LOCALISATIONS, C_LOCALISATIONS),
                      self.attendu("localisations", G_LOCALISATIONS, C_LOCALISATIONS))

    def test_reimport_des_creations_tout_identique(self):
        # Les lignes à créer, écrites dans la base, puis le même fichier réimporté : rien à créer (CS85).
        apercu = self.preparer("fournisseurs", E_FOURNISSEURS, G_FOURNISSEURS[:2], C_FOURNISSEURS)
        self.page.evaluate("""async (lignes) => { await Donnees.modifier('fournisseurs', (l) => { l.push(...lignes); }); }""",
                           apercu["ecritures"]["fournisseurs"]["creer"])
        second = self.preparer("fournisseurs", E_FOURNISSEURS, G_FOURNISSEURS[:2], C_FOURNISSEURS)
        self.assertEqual([l["action"] for l in second["lignes"]], ["identique", "identique"])

    def test_une_cellule_vide_n_efface_jamais(self):
        grille = [["CP-01", "", "", "", "", "", "", "", "", "", "", ""]]
        apercu = self.preparer("equipements", E_EQUIPEMENTS, grille, C_EQUIPEMENTS)
        self.assertEqual(apercu["lignes"][0]["action"], "identique")
        self.assertEqual(apercu["ecritures"]["equipements"], {"creer": [], "modifier": []})


class TestRapportRefus(CasImport):

    def test_rapport_au_format_de_prevo(self):
        apercu = self.preparer("equipements", E_EQUIPEMENTS, G_EQUIPEMENTS, C_EQUIPEMENTS)
        texte = self.page.evaluate("([a, l, e]) => Import.rapportRefus(a, l, e)", [apercu, G_EQUIPEMENTS, E_EQUIPEMENTS])
        refusees = [l for l in apercu["lignes"] if l["action"] == "refusee"]
        lignes = [["Raison"] + E_EQUIPEMENTS] + [[" ; ".join(l["raisons"])] + G_EQUIPEMENTS[l["rang"]] for l in refusees]
        attendu = "\ufeff" + "".join(";".join(ecrire_cellule(c) for c in ligne) + "\r\n" for ligne in lignes)
        self.assertEqual(texte, attendu)
        self.assertIn(";'007;", texte)                       # zéros protégés pour Excel
        self.assertIn('"Machine X; prototype"', texte)       # « ; » entre guillemets
        self.assertIn("'31/02/2020", texte)
        relu = list(module_csv.reader(io.StringIO(texte[1:], newline=""), delimiter=";"))
        self.assertEqual(len(relu), 1 + len(refusees))


class TestBaseInchangee(CasNavigateur):
    """Mode serveur, application complète : l'aperçu n'écrit rien (23 CSV identiques à l'octet)."""

    def test_aucune_ecriture_ni_sur_le_disque_ni_en_memoire(self):
        with ServeurPrevo() as serveur:
            empreintes = lambda: {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(serveur.dossier.glob("*.csv"))}
            ecritures = []
            self.page.on("request", lambda r: ecritures.append(r.method + " " + r.url) if r.method != "GET" else None)
            preregler_profil(self.contexte, "responsable")
            self.page.goto(serveur.url + "/#/import")
            attendre_pret(self.page)
            self.page.wait_for_load_state("networkidle")
            # Les écritures du démarrage de l'application (s'il y en a) sont faites : l'aperçu part de là.
            avant = empreintes()
            self.assertEqual(len(avant), 23)
            ecritures.clear()
            instantane ="() => Object.entries(Donnees.instantane()).map(([t, o]) => t + ':' + Array.from(o).join(','))"
            memoire_avant = self.page.evaluate(instantane)
            appels = [("equipements", E_EQUIPEMENTS, G_EQUIPEMENTS, C_EQUIPEMENTS), ("articles", E_ARTICLES, grille_articles("14"), C_ARTICLES),
                      ("fournisseurs", E_FOURNISSEURS, G_FOURNISSEURS, C_FOURNISSEURS), ("techniciens", E_TECHNICIENS, G_TECHNICIENS, C_TECHNICIENS),
                      ("habilitations", E_HABILITATIONS, G_HABILITATIONS, C_HABILITATIONS), ("codes", E_CODES, G_CODES, C_CODES),
                      ("compteurs", E_COMPTEURS, G_COMPTEURS, C_COMPTEURS), ("controles", E_CONTROLES, G_CONTROLES, C_CONTROLES),
                      ("gammes", E_GAMMES, G_GAMMES, C_GAMMES), ("localisations", E_LOCALISATIONS, G_LOCALISATIONS, C_LOCALISATIONS)]
            totaux = self.page.evaluate("""(appels) => appels.map(([type, entetes, grille, correspondance]) => {
              Import.correspondance(type, entetes, grille);
              const apercu = Import.preparer(type, grille, correspondance, { mettreAJour: true });
              Import.rapportRefus(apercu, grille, entetes);
              return apercu.totaux.creer + apercu.totaux.mettre_a_jour;
            })""", [[t, e, g, correspondance(e, c)] for t, e, g, c in appels])
            self.assertTrue(all(n > 0 for n in totaux), totaux)
            self.assertEqual(self.page.evaluate(instantane), memoire_avant)
            self.page.wait_for_timeout(300)
            apres = empreintes()
            self.assertEqual([nom for nom in avant if apres[nom] != avant[nom]], [])
            self.assertEqual(ecritures, [])


if __name__ == "__main__":
    unittest.main()
