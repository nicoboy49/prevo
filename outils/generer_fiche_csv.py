"""Écrit FICHE_TECHNIQUE_CSV.md, la fiche technique des fichiers CSV de Prévo (23 depuis le format 3), d'après le schéma.

Le schéma est la seule source : js/schema.js (objet Schema) est lu dans Chromium (Playwright, outil de
développement, déjà utilisé par les tests) ; la fiche est donc toujours fidèle aux fichiers réels.
La section 4 (import depuis un tableur, lot 5) reprend Import.TYPES, relu en Python dans
js/modules/import-regles.js (types, clés naturelles, colonnes reconnues et leurs autres titres).
tests/test_fiche_csv.py vérifie qu'elle est à jour (ARCHITECTURE.md §17.8).

Lancer depuis la racine du projet, après toute modification de js/schema.js ou des types de
js/modules/import-regles.js :
    py outils/generer_fiche_csv.py
"""
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER_FICHE = RACINE / "FICHE_TECHNIQUE_CSV.md"

# Rôle de chaque fichier, en une phrase (dans l'ordre du schéma).
ROLES = {
    "localisations": "Arborescence des lieux : site, ateliers, lignes.",
    "equipements": "Le parc : chaque machine ou sous-ensemble, sa criticité, sa consignation.",
    "demandes": "Demandes d'intervention (DI) signalées par les demandeurs.",
    "ordres_travail": "Ordres de travail (OT) : correctifs, préventifs, réglementaires, améliorations.",
    "ot_operations": "Check-list d'un OT (copie de la gamme, cochée pendant l'intervention).",
    "ot_pieces": "Pièces prévues pour un OT.",
    "ot_temps": "Temps passés par technicien sur un OT.",
    "gammes": "Gammes de maintenance préventive (par date, compteur ou seuil).",
    "gamme_operations": "Opérations (check-list) de chaque gamme.",
    "articles": "Articles du magasin (pièces de rechange, consommables).",
    "article_equipement": "Lien entre articles et équipements (pièces d'une machine).",
    "mouvements_stock": "Mouvements du magasin : entrées, sorties, retours, inventaires.",
    "techniciens": "Techniciens : capacité hebdomadaire, taux horaire.",
    "habilitations": "Habilitations des techniciens et leurs échéances.",
    "compteurs": "Compteurs (heures, cycles) et points de mesure des équipements.",
    "releves": "Relevés des compteurs et des mesures.",
    "controles_reglementaires": "Contrôles réglementaires périodiques (VGP, électricité…).",
    "codes_defaillance": "Codes de défaillance : symptômes, causes, remèdes.",
    "fournisseurs": "Fournisseurs du magasin.",
    "achats": "Demandes d'achat et commandes.",
    "parametres": "Réglages partagés de l'atelier (une ligne par clé).",
    "journal": "Journal des modifications (qui, quand, quoi) ; on n'y fait qu'ajouter.",
    "wiki_syntheses": ("Synthèses [IA] du wiki de maintenance (format 3) : au plus une en cours par équipement "
                       "(« à valider » ou « validée ») ; les précédentes restent, « remplacées »."),
}

TYPES = [
    ("id", "identifiant de la ligne (voir le format de chaque fichier)"),
    ("texte", "texte sur une ligne"),
    ("texte_long", "texte sur plusieurs lignes (entre guillemets dans le fichier)"),
    ("entier", "nombre entier (`12`)"),
    ("decimal", "nombre à virgule, écrit avec un point (`7.5`) ; la virgule est acceptée à la lecture"),
    ("date", "date `AAAA-MM-JJ`"),
    ("date_heure", "date et heure `AAAA-MM-JJ HH:MM`"),
    ("booleen", "`1` (oui) ou `0` (non)"),
    ("choix", "une des valeurs de la liste fermée"),
    ("ref", "identifiant d'une ligne d'un autre fichier"),
    ("document", "nom d'un fichier du dossier `documents/` (photo, PDF…)"),
]


def lire_schema():
    """Objet Schema (version et tables) lu dans Chromium."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        try:
            page = navigateur.new_page()
            page.set_content("<!doctype html><title>schéma</title>")
            page.add_script_tag(content=(RACINE / "js" / "schema.js").read_text(encoding="utf-8"))
            texte = page.evaluate("() => JSON.stringify({ version: Schema.version, ordre: Schema.nomsTables(), tables: Schema.tables })")
        finally:
            navigateur.close()
    return json.loads(texte)


def format_identifiant(table):
    ident = table.get("identifiant")
    if not ident:
        return "saisi (la clé elle-même)"
    if ident.get("horodate"):
        return "`%sAAAAMMJJHHMMSS-XXXX` (horodatage puis %d caractères tirés au hasard)" % (ident["prefixe"], ident["chiffres"])
    numero = "N" * ident["chiffres"]
    if ident.get("annuel"):
        return "`%sAAAA-%s` (numéro remis à 1 chaque année ; ex. `%s2026-%s`)" % (
            ident["prefixe"], numero, ident["prefixe"], "0" * (ident["chiffres"] - 2) + "42")
    return "`%s%s` (ex. `%s%s`)" % (ident["prefixe"], numero, ident["prefixe"], "0" * (ident["chiffres"] - 1) + "1")


def cellule(texte):
    """Texte sûr dans une cellule de tableau Markdown."""
    return str(texte).replace("|", "\\|").replace("\n", " ")


def valeurs_ou_reference(champ):
    if champ.get("valeurs"):
        return ", ".join("`%s`" % v for v in champ["valeurs"])
    if champ.get("table"):
        cible = "`%s.csv`" % champ["table"]
        if champ.get("champCible"):
            cible += " (colonne `%s`)" % champ["champCible"]
        if champ.get("filtre"):
            cible += ", " + ", ".join("%s = %s" % (cle, valeur) for cle, valeur in champ["filtre"].items())
        return "réf. " + cible
    return ""


def remarques(champ):
    morceaux = []
    if champ.get("protege"):
        morceaux.append("toujours protégé par une apostrophe")
    if champ.get("depuisVersion"):
        morceaux.append("depuis le format %d" % champ["depuisVersion"])
    if champ.get("synonymes"):
        morceaux.append("autres noms reconnus : " + ", ".join(champ["synonymes"]))
    return " ; ".join(morceaux)


# ---------------------------------------------------------------------------------------------------------
# Section 4 : import depuis un tableur, d'après Import.TYPES (js/modules/import-regles.js, lot 5)
# ---------------------------------------------------------------------------------------------------------
# Import.TYPES est écrit en JavaScript avec des appels S(…), V(…), type(…), reference(…), equipementDe(…). Un
# petit lecteur d'expressions le relit ici, sans navigateur, depuis le texte du fichier : littéraux (textes,
# nombres, tableaux, objets), « + », appels, Object.assign et fonctions fléchées à une expression. Les constantes
# et fonctions du fichier sont relues de la même façon ; S, V et type, qui assemblent les champs, sont reproduites
# ci-dessous (mêmes règles que dans import-regles.js : libellé, type et synonymes du schéma, synonymes ajoutés,
# options). Une construction inconnue arrête la génération avec un message clair : jamais de fiche fausse.

FICHIER_IMPORT = RACINE / "js" / "modules" / "import-regles.js"
FICHIER_LECTURE = RACINE / "js" / "modules" / "import-lecture.js"
DEBUT_TYPES = "// ===== 2."            # section de import-regles.js qui définit TYPES
FIN_TYPES = "// ===== 3."


class ErreurLectureImport(Exception):
    """import-regles.js n'a pas pu être relu (construction inconnue) : la fiche n'est pas écrite."""


MOTIF_JETON = re.compile(r"""
    (?P<espace>\s+|//[^\n]*|/\*.*?\*/)
  | (?P<chaine>'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`)
  | (?P<nombre>\d+(?:\.\d+)?)
  | (?P<nom>[A-Za-z_$][\w$]*)
  | (?P<signe>=>|\.\.\.|===|!==|==|!=|&&|\|\||[-+*/%(){}\[\],;:.=?<>!&|])
""", re.VERBOSE | re.DOTALL)
ECHAPPEMENTS = {"n": "\n", "t": "\t", "r": "\r", "'": "'", '"': '"', "`": "`", "\\": "\\"}


def jetons_js(texte):
    """Jetons (genre, valeur) d'un extrait de JavaScript ; commentaires et espaces retirés."""
    resultat, position = [], 0
    while position < len(texte):
        trouve = MOTIF_JETON.match(texte, position)
        if not trouve:
            raise ErreurLectureImport("caractère inattendu dans %s : %r" % (FICHIER_IMPORT.name, texte[position:position + 40]))
        position = trouve.end()
        genre = trouve.lastgroup
        if genre == "espace":
            continue
        valeur = trouve.group(genre)
        if genre == "chaine":
            valeur = re.sub(r"\\(.)", lambda m: ECHAPPEMENTS.get(m.group(1), m.group(1)), valeur[1:-1], flags=re.DOTALL)
        resultat.append((genre, valeur))
    return resultat


class Fleche:
    """Fonction fléchée du fichier : paramètres et jetons de son expression."""

    def __init__(self, parametres, corps, portee):
        self.parametres, self.corps, self.portee = parametres, corps, portee


class LecteurJs:
    """Évalue les jetons d'une expression ; `portee` donne la valeur d'un nom (dictionnaire, puis `chercher`)."""

    def __init__(self, jetons, portee, chercher):
        self.jetons, self.rang, self.portee, self.chercher = jetons, 0, portee, chercher

    def voir(self, decalage=0):
        rang = self.rang + decalage
        return self.jetons[rang] if rang < len(self.jetons) else (None, None)

    def prendre(self, signe=None):
        jeton = self.voir()
        if jeton[0] is None or (signe is not None and jeton[1] != signe):
            raise ErreurLectureImport("« %s » attendu, « %s » trouvé dans %s" % (signe, jeton[1], FICHIER_IMPORT.name))
        self.rang += 1
        return jeton

    def tout(self):
        valeur = self.expression()
        if self.rang != len(self.jetons):
            raise ErreurLectureImport("expression non reconnue dans %s, près de « %s »" % (FICHIER_IMPORT.name, self.voir()[1]))
        return valeur

    def expression(self):
        valeur = self.postfixe()
        while self.voir()[1] == "+" and self.voir()[0] == "signe":
            self.prendre("+")
            droite = self.postfixe()
            if not (isinstance(valeur, str) and isinstance(droite, str)):
                raise ErreurLectureImport("« + » entre autre chose que deux textes dans %s" % FICHIER_IMPORT.name)
            valeur += droite
        return valeur

    def postfixe(self):
        valeur = self.primaire()
        while True:
            genre, signe = self.voir()
            if genre == "signe" and signe == "(":
                valeur = appeler(valeur, self.liste(")"))
            elif genre == "signe" and signe == ".":
                self.prendre(".")
                nom = self.prendre()[1]
                if not isinstance(valeur, dict) or nom not in valeur:
                    raise ErreurLectureImport("membre « .%s » non reconnu dans %s" % (nom, FICHIER_IMPORT.name))
                valeur = valeur[nom]
            else:
                return valeur

    def liste(self, fermeture):
        self.prendre("(" if fermeture == ")" else "[")
        valeurs = []
        while self.voir()[1] != fermeture:
            if self.voir()[1] == "...":
                raise ErreurLectureImport("« ... » non reconnu dans %s" % FICHIER_IMPORT.name)
            valeurs.append(self.expression())
            if self.voir()[1] != fermeture:
                self.prendre(",")
        self.prendre(fermeture)
        return valeurs

    def objet(self):
        self.prendre("{")
        valeur = {}
        while self.voir()[1] != "}":
            genre, cle = self.prendre()
            if genre not in ("nom", "chaine", "nombre"):
                raise ErreurLectureImport("clé d'objet non reconnue dans %s : « %s »" % (FICHIER_IMPORT.name, cle))
            if self.voir()[1] == ":":
                self.prendre(":")
                valeur[cle] = self.expression()
            elif genre == "nom":
                valeur[cle] = self.nom(cle)          # { table, ref } : raccourci
            else:
                raise ErreurLectureImport("objet non reconnu dans %s" % FICHIER_IMPORT.name)
            if self.voir()[1] != "}":
                self.prendre(",")
        self.prendre("}")
        return valeur

    def fleche_en_vue(self):
        """( a, b ) => … : rend le nombre de jetons des paramètres (parenthèses comprises), sinon 0."""
        rang = 1
        while self.voir(rang)[0] == "nom" or self.voir(rang)[1] == ",":
            rang += 1
        return rang + 1 if self.voir(rang)[1] == ")" and self.voir(rang + 1)[1] == "=>" else 0

    def fleche(self, longueur):
        parametres = [valeur for genre, valeur in self.jetons[self.rang + 1:self.rang + longueur - 1] if genre == "nom"]
        self.rang += longueur
        self.prendre("=>")
        debut, profondeur = self.rang, 0
        while self.rang < len(self.jetons):
            signe = self.voir()[1] if self.voir()[0] == "signe" else None
            if signe in ("(", "[", "{"):
                profondeur += 1
            elif signe in (")", "]", "}", ",", ";") and profondeur == 0:
                break
            elif signe in (")", "]", "}"):
                profondeur -= 1
            self.rang += 1
        return Fleche(parametres, self.jetons[debut:self.rang], self.portee)

    def nom(self, nom):
        if nom in self.portee:
            return self.portee[nom]
        return self.chercher(nom)

    def primaire(self):
        genre, valeur = self.voir()
        if genre in ("chaine", "nombre"):
            self.prendre()
            return valeur
        if genre == "signe" and valeur == "[":
            return self.liste("]")
        if genre == "signe" and valeur == "{":
            return self.objet()
        if genre == "signe" and valeur == "(":
            longueur = self.fleche_en_vue()
            if longueur:
                return self.fleche(longueur)
            self.prendre("(")
            dedans = self.expression()
            self.prendre(")")
            return dedans
        if genre == "nom":
            self.prendre()
            if valeur in ("true", "false", "null", "undefined"):
                return {"true": True, "false": False}.get(valeur)
            return self.nom(valeur)
        raise ErreurLectureImport("expression non reconnue dans %s, près de « %s »" % (FICHIER_IMPORT.name, valeur))


def appeler(fonction, arguments):
    if callable(fonction):
        return fonction(*arguments)
    if isinstance(fonction, Fleche):
        if fonction.corps and fonction.corps[0][1] == "{":
            raise ErreurLectureImport("fonction à corps entre accolades non reconnue dans %s" % FICHIER_IMPORT.name)
        portee = dict(zip(fonction.parametres, list(arguments) + [None] * len(fonction.parametres)))
        portee.update({cle: valeur for cle, valeur in fonction.portee.items() if cle not in portee})
        lecteur = LecteurJs(fonction.corps, portee, fonction.portee["__chercher__"])
        return lecteur.tout()
    raise ErreurLectureImport("appel d'autre chose qu'une fonction dans %s" % FICHIER_IMPORT.name)


def lire_types_import(schema):
    """Import.TYPES relu dans js/modules/import-regles.js : { cle: { cle, libelle, aide, tables, champs, refs } }."""
    texte = FICHIER_IMPORT.read_text(encoding="utf-8")
    if DEBUT_TYPES not in texte or FIN_TYPES not in texte:
        raise ErreurLectureImport("sections « %s » et « %s » introuvables dans %s" % (DEBUT_TYPES, FIN_TYPES, FICHIER_IMPORT.name))
    jetons = jetons_js(texte[texte.index(DEBUT_TYPES):texte.index(FIN_TYPES)])

    # Définitions de la section : const NOM = … ; const [A, B] = [x, y] ; (les « function » sont sautées).
    definitions, rang = {}, 0

    def fin_instruction(debut):
        profondeur, position = 0, debut
        while position < len(jetons):
            genre, signe = jetons[position]
            if genre == "signe" and signe in ("(", "[", "{"):
                profondeur += 1
            elif genre == "signe" and signe in (")", "]", "}"):
                profondeur -= 1
                if profondeur == 0 and signe == "}" and jetons[debut][1] == "function":
                    return position + 1
            elif genre == "signe" and signe == ";" and profondeur == 0:
                return position
            position += 1
        return position

    def elements(debut, fin):
        """Jetons de chaque élément d'un tableau [a, b, …] (jetons[debut] = « [ », jetons[fin - 1] = « ] »)."""
        morceaux, courant, profondeur = [], [], 0
        for genre, valeur in jetons[debut + 1:fin - 1]:
            if genre == "signe" and valeur in ("(", "[", "{"):
                profondeur += 1
            elif genre == "signe" and valeur in (")", "]", "}"):
                profondeur -= 1
            if genre == "signe" and valeur == "," and profondeur == 0:
                morceaux.append(courant)
                courant = []
            else:
                courant.append((genre, valeur))
        return morceaux + ([courant] if courant else [])

    while rang < len(jetons):
        genre, valeur = jetons[rang]
        if (genre, valeur) == ("nom", "function"):
            rang = fin_instruction(rang)
        elif (genre, valeur) == ("nom", "const"):
            fin = fin_instruction(rang)
            if jetons[rang + 1][1] == "[":
                noms_fin = next(i for i in range(rang + 1, fin) if jetons[i][1] == "]")
                noms = [v for g, v in jetons[rang + 2:noms_fin] if g == "nom"]
                droite = jetons[noms_fin + 2:fin]
                if droite and droite[0][1] == "[" and droite[-1][1] == "]":
                    for nom, morceau in zip(noms, elements(noms_fin + 2, fin)):
                        definitions[nom] = morceau
            else:
                definitions[jetons[rang + 1][1]] = jetons[rang + 3:fin]
            rang = fin + 1
        else:
            rang += 1
    if "TYPES" not in definitions:
        raise ErreurLectureImport("« const TYPES = { … } » introuvable dans %s" % FICHIER_IMPORT.name)

    tables = schema["tables"]

    def champ_schema(table, nom):
        trouve = next((c for c in tables.get(table, {}).get("champs", []) if c["nom"] == nom), None)
        if trouve is None:
            raise ErreurLectureImport("champ « %s.%s » absent du schéma (cité par %s)" % (table, nom, FICHIER_IMPORT.name))
        return trouve

    def avec_synonymes(options, liste):
        options = options or {}
        resultat = dict(options)
        resultat["synonymes"] = (liste.split("|") if liste else []) + list(options.get("synonymes") or [])
        return resultat

    def champs_du_schema(table, exemples):
        resultat = []
        for nom, valeur in exemples.items():
            exemple, liste, options = ((valeur if isinstance(valeur, list) else [valeur]) + [None, None, None])[:3]
            champ = champ_schema(table, nom)
            extra = avec_synonymes(options, liste)
            fiche = {"cle": nom, "libelle": champ.get("libelle"), "table": table, "champ": nom, "type": champ["type"],
                     "valeurs": champ.get("valeurs") or None, "obligatoire": champ.get("obligatoire") is True,
                     "protege": champ.get("protege") is True, "defaut": champ.get("defaut"), "cleNaturelle": False,
                     "exemple": exemple}
            fiche.update(extra)
            fiche["synonymes"] = list(champ.get("synonymes") or []) + extra["synonymes"]
            resultat.append(fiche)
        return resultat

    def champ_virtuel(cle, libelle, genre, exemple, liste=None, options=None):
        fiche = {"cle": cle, "libelle": libelle, "table": None, "champ": None, "type": genre, "valeurs": None,
                 "obligatoire": False, "protege": False, "defaut": None, "cleNaturelle": False, "exemple": exemple}
        fiche.update(avec_synonymes(options, liste))
        return fiche

    def type_de_donnees(cle, libelle, aide, tables_ecrites, groupes):
        champs = []
        for groupe in groupes:
            champs.extend(groupe if isinstance(groupe, list) else [groupe])
        refs = [{"champ": c["cle"], "table": c["ref"], "creee": c["ref"] in ("localisations", "fournisseurs")}
                for c in champs if c.get("ref")]
        return {"cle": cle, "libelle": libelle, "aide": aide, "tables": tables_ecrites, "champs": champs, "refs": refs}

    def assigner(cible, *sources):
        for source in sources:
            cible.update(source or {})
        return cible

    globales = {"S": champs_du_schema, "V": champ_virtuel, "type": type_de_donnees, "avecSynonymes": avec_synonymes,
                "Object": {"assign": assigner}}
    valeurs = {}

    def chercher(nom):
        if nom in globales:
            return globales[nom]
        if nom not in valeurs:
            if nom not in definitions:
                raise ErreurLectureImport("nom « %s » inconnu dans la section des types de %s" % (nom, FICHIER_IMPORT.name))
            valeurs[nom] = LecteurJs(definitions[nom], {"__chercher__": chercher}, chercher).tout()
        return valeurs[nom]

    types = chercher("TYPES")
    if not isinstance(types, dict) or not types:
        raise ErreurLectureImport("TYPES n'est pas un objet de types de données dans %s" % FICHIER_IMPORT.name)
    return types


def lire_plafonds_import():
    """Plafonds de la lecture (Import.PLAFONDS de import-lecture.js) : (mégaoctets, lignes, colonnes)."""
    texte = FICHIER_LECTURE.read_text(encoding="utf-8")
    trouve = re.search(r"PLAFONDS = Object\.freeze\(\{ octets: (\d+) \* 1024 \* 1024, lignes: (\d+), colonnes: (\d+) \}\)", texte)
    if not trouve:
        raise ErreurLectureImport("Import.PLAFONDS introuvable dans %s" % FICHIER_LECTURE.name)
    return tuple(int(n) for n in trouve.groups())


# Précisions écrites à la main pour les colonnes propres à l'import ; clé = (type, champ) ou champ.
REMARQUES_IMPORT = {
    "chemin": "« Site > Atelier > Ligne » (séparateur `>`, `/` ou `\\`) ; type déduit du niveau ; niveaux manquants créés",
    "chemin_localisation": "chemin « Site > Atelier > Ligne » ; localisation créée si elle manque",
    "site": "une colonne par niveau, au lieu du chemin ; créé s'il manque",
    "atelier": "une colonne par niveau, au lieu du chemin ; créé s'il manque",
    "ligne": "une colonne par niveau, au lieu du chemin ; créée si elle manque",
    "parent": "repère d'un équipement de Prévo ou du même fichier",
    "stock_initial": "devient un mouvement « inventaire » ; le stock affiché est celui du fichier",
    "fournisseur": "nom du fournisseur ; créé s'il manque",
    ("habilitations", "technicien"): "« Prénom Nom », « Nom Prénom » ou nom seul s'il est unique ; doit exister",
    "equipement": "repère d'un équipement de Prévo",
    "compteur": "libellé d'un compteur du même équipement",
    "operations": "une ligne par opération (gamme répétée) ou opérations séparées par « ; »",
    "valeur_attendue": "dans l'ordre des opérations, séparées par « ; »",
    "ancien_numero": "écrit en tête du compte rendu (« Ancien n° : … ») ; sert à repérer les doublons",
    "symptome_code": "code ou libellé de la famille ; jamais créé (vide et signalé s'il est inconnu)",
    "cause_code": "code ou libellé de la famille ; jamais créé (vide et signalé s'il est inconnu)",
    "remede_code": "code ou libellé de la famille ; jamais créé (vide et signalé s'il est inconnu)",
    ("historique", "technicien"): "par son nom ; vide et signalé s'il est introuvable",
    "temps_passe_h": "une ligne de `ot_temps.csv` (technicien de l'OT)",
    ("historique", "type"): "absent : « correctif différé », signalé ; inconnu : ligne refusée",
    ("historique", "priorite"): "absente : « P3 », signalée",
    ("historique", "titre"): "absent : début du compte rendu",
    ("historique", "date_creation"): "absente : date de début ; ni l'une ni l'autre : ligne refusée",
    ("historique", "date_fin"): "absente : date de début",
    ("historique", "duree_arret_h"): "absente : laissée vide, jamais 0",
    ("historique", "arret_production"): "absent : « oui » si une durée d'arrêt non nulle est donnée",
}
CLE_NATURELLE_COMPLEMENT = {
    "historique": " ; sans lui, même équipement, même date de création (à la minute) et même titre : doublon"
                  " supposé, montré dans l'aperçu",
}


def rediger_import(schema):
    """Lignes Markdown de la section « Import depuis un tableur » (fonction pure : mêmes fichiers → même texte)."""
    types = lire_types_import(schema)
    mega, lignes_max, colonnes_max = lire_plafonds_import()
    fichier = lambda table: "`%s`" % schema["tables"][table]["fichier"]
    lignes = [
        "",
        "## 4. Import depuis un tableur",
        "",
        "L'écran « Importer des données » (responsable, depuis Paramètres) reprend des données existantes depuis un"
        " fichier `.csv`, `.tsv`, `.txt`, `.xlsx`, `.xlsm`, `.xls` ou `.ods`, ou depuis des cellules collées : %d Mo,"
        " %s lignes et %d colonnes au plus. Rien n'est écrit avant le bouton « Importer » ; une sauvegarde"
        " `AAAA-MM-JJ_HHMMSS_avant-import` est faite juste avant (modes serveur et dossier), et l'import peut être"
        " annulé." % (mega, "{:,}".format(lignes_max).replace(",", " "), colonnes_max),
        "",
        "- **Titres reconnus** : un titre de colonne est reconnu, sans tenir compte des majuscules, des accents ni de la"
        " ponctuation, s'il est égal au titre du modèle, au nom de la colonne CSV ou à l'un des autres titres listés"
        " ci-dessous ; un titre seulement proche est proposé « à confirmer ».",
        "- **Clé naturelle** : les identifiants de Prévo ne sont jamais pris dans le fichier ; une fiche est reconnue"
        " par sa clé (tableau ci-dessous). Une fiche déjà présente est complétée et mise à jour, pour les seules colonnes"
        " importées et non vides (au choix, à chaque import) : une cellule vide n'efface rien. L'historique ne modifie"
        " jamais un OT existant.",
        "- **Valeurs** : lues comme dans un CSV de Prévo (§1) ; une valeur illisible ou hors de la liste fermée refuse"
        " la ligne, avec sa raison. Une valeur n'est jamais inventée.",
        "- **Obligatoire** : sans cette colonne, une ligne qui crée une fiche est refusée. **Clé** : partie de la clé"
        " naturelle ; vide, elle refuse la ligne.",
        "- **Modèles** : pour chaque type, l'assistant propose un modèle `.xlsx` (avec une feuille « Aide ») et `.csv`,"
        " avec ces titres et une ligne d'exemple.",
        "",
        "| Type | Fichiers écrits | Reconnu par (clé naturelle) |",
        "| --- | --- | --- |",
    ]
    for cle, type_ in types.items():
        cles = " + ".join(c["libelle"] for c in type_["champs"] if c.get("cleNaturelle"))
        lignes.append("| %s | %s | %s |" % (cellule(type_["libelle"]), ", ".join(fichier(t) for t in type_["tables"]),
                                                  cellule(cles + CLE_NATURELLE_COMPLEMENT.get(cle, ""))))
    for numero, (cle, type_) in enumerate(types.items(), 1):
        lignes += ["", "### 4.%d %s" % (numero, type_["libelle"]), "", type_["aide"].replace("\\", "\\\\"), "",
                   "| Titre de la colonne | Écrit dans | Obligatoire | Autres titres reconnus | Remarques |",
                   "| --- | --- | --- | --- | --- |"]
        for champ in type_["champs"]:
            if champ.get("champ") and champ.get("table"):
                ecrit = "%s : `%s`" % (fichier(champ["table"]), champ["champ"])
            elif champ.get("ecrit") and champ.get("table"):
                ecrit = "%s : `%s`" % (fichier(champ["table"]), champ["ecrit"])
            elif champ.get("table"):
                ecrit = fichier(champ["table"])
            else:
                ecrit = ""
            obligatoire = ", ".join(m for m, vrai in (("oui", champ.get("obligatoire")), ("clé", champ.get("cleNaturelle"))) if vrai)
            autres = list(dict.fromkeys(s for s in champ.get("synonymes") or [] if s))
            remarque = REMARQUES_IMPORT.get((cle, champ["cle"]))
            if remarque is None:                         # remarque commune : colonnes propres à l'import seulement
                remarque = REMARQUES_IMPORT.get(champ["cle"], "") if not champ.get("champ") or champ.get("ref") else ""
            lignes.append("| %s | %s | %s | %s | %s |" % (cellule(champ["libelle"]), ecrit, obligatoire,
                                                         cellule(", ".join(autres)), cellule(remarque)))
    return lignes


def rediger_fiche(schema):
    """Texte Markdown complet de la fiche (fonction pure : même schéma → même texte)."""
    tables = schema["tables"]
    lignes = [
        "# Fiche technique des fichiers CSV de Prévo",
        "",
        "Document généré par `outils/generer_fiche_csv.py` d'après `js/schema.js` (et, pour la section 4,"
        " `js/modules/import-regles.js`) : ne pas le modifier à la main.",
        "",
        "Prévo range ses données dans **%d fichiers CSV** (format **version %d**), dans le dossier de données"
        " (`donnees/` à côté de `serveur.py`, ou le dossier choisi en mode dossier). Ils s'ouvrent et se modifient"
        " dans Excel. Le paramètre `version_schema` de `parametres.csv` indique la version du format." % (len(schema["ordre"]), schema["version"]),
        "",
        "## 1. Règles communes à tous les fichiers",
        "",
        "- **Encodage** : UTF-8 avec BOM ; à la lecture, un fichier en Windows-1252 est aussi accepté (signalé).",
        "- **Séparateur** : point-virgule `;` (une virgule est acceptée à la lecture si l'en-tête n'a aucun `;`).",
        "- **Fins de ligne** : CRLF. **Première ligne** : les noms des colonnes, dans l'ordre ci-dessous ; les colonnes"
        " ajoutées à la main sont conservées et réécrites à la fin ; une colonne manquante prend sa valeur par défaut.",
        "- **Guillemets** : une valeur est entre guillemets si elle contient `;`, `\"`, un retour à la ligne ; un `\"`"
        " s'écrit `\"\"`.",
        "- **Valeurs** : dates `AAAA-MM-JJ`, date-heure `AAAA-MM-JJ HH:MM`, nombres avec un point, booléens `1`/`0`."
        " À la lecture, Prévo accepte aussi `JJ/MM/AAAA`, la virgule décimale, `oui`/`non`, `vrai`/`faux`.",
        "- **Apostrophe de protection** : Excel abîme certaines valeurs de texte (`00123` devient `123`, `1/2` devient une"
        " date, `- joint` devient une formule). Prévo écrit ces valeurs précédées d'une apostrophe (`'00123`) et la"
        " retire à la lecture. Les colonnes marquées « toujours protégé » l'ont systématiquement.",
        "- **Jamais de suppression** : une ligne n'est jamais effacée ; elle est désactivée (`actif` = `0`) ou annulée"
        " (statut `Annulé`). Toute modification faite par Prévo est inscrite dans `journal.csv`.",
        "- **Excel et Prévo en même temps** : ne modifiez pas un fichier dans Excel pendant que quelqu'un enregistre dans"
        " Prévo ; fermez Excel avant.",
        "",
        "## 2. Les types de colonnes",
        "",
        "| Type | Contenu |",
        "| --- | --- |",
    ]
    lignes += ["| `%s` | %s |" % (nom, explication) for nom, explication in TYPES]
    lignes += ["", "## 3. Les %d fichiers" % len(schema["ordre"]), "",
               "| Fichier | Contenu | Identifiant |", "| --- | --- | --- |"]
    for nom in schema["ordre"]:
        table = tables[nom]
        lignes.append("| `%s` | %s | %s |" % (table["fichier"], ROLES.get(nom, table["libelle"]), format_identifiant(table)))
    for numero, nom in enumerate(schema["ordre"], 1):
        table = tables[nom]
        lignes += ["", "### 3.%d `%s` — %s" % (numero, table["fichier"], table["libelle"]), "",
                   ROLES.get(nom, ""), "",
                   "- Identifiant : %s." % format_identifiant(table)]
        if table.get("ajoutSeul"):
            lignes.append("- Fichier écrit par ajout seulement : les lignes existantes ne sont jamais réécrites.")
        lignes += ["", "| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |",
                   "| --- | --- | --- | --- | --- | --- | --- |"]
        for champ in table["champs"]:
            lignes.append("| `%s` | %s | `%s` | %s | %s | %s | %s |" % (
                champ["nom"], cellule(champ.get("libelle", "")), champ["type"], "oui" if champ.get("obligatoire") else "",
                cellule(valeurs_ou_reference(champ)), cellule("`%s`" % champ["defaut"] if champ.get("defaut") not in (None, "") else ""),
                cellule(remarques(champ))))
    lignes += rediger_import(schema)
    lignes.append("")
    return "\n".join(lignes)


def main():
    texte = rediger_fiche(lire_schema())
    FICHIER_FICHE.write_text(texte, encoding="utf-8", newline="\n")
    print("Écrit : %s (%d lignes)" % (FICHIER_FICHE.name, texte.count("\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
