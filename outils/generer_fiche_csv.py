"""Écrit FICHE_TECHNIQUE_CSV.md, la fiche technique des 22 fichiers CSV de Prévo, d'après le schéma.

Le schéma est la seule source : js/schema.js (objet Schema) est lu dans Chromium (Playwright, outil de
développement, déjà utilisé par les tests) ; la fiche est donc toujours fidèle aux fichiers réels.
tests/test_fiche_csv.py vérifie qu'elle est à jour (ARCHITECTURE.md §17.8).

Lancer depuis la racine du projet, après toute modification de js/schema.js :
    py outils/generer_fiche_csv.py
"""
import json
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


def rediger_fiche(schema):
    """Texte Markdown complet de la fiche (fonction pure : même schéma → même texte)."""
    tables = schema["tables"]
    lignes = [
        "# Fiche technique des fichiers CSV de Prévo",
        "",
        "Document généré par `outils/generer_fiche_csv.py` d'après `js/schema.js` : ne pas le modifier à la main.",
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
    lignes.append("")
    return "\n".join(lignes)


def main():
    texte = rediger_fiche(lire_schema())
    FICHIER_FICHE.write_text(texte, encoding="utf-8", newline="\n")
    print("Écrit : %s (%d lignes)" % (FICHIER_FICHE.name, texte.count("\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
