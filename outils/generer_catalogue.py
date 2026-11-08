#!/usr/bin/env python3
"""Génère js/catalogue/fr.js depuis docs/catalogue/*.json (T400). Stdlib seule, déterministe.

    py -X utf8 outils/generer_catalogue.py [dossier_de_sortie]
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SOURCES = RACINE / "docs" / "catalogue"
MENTIONS = {
    "controles": "à confirmer avec votre organisme de contrôle",
    "habilitations": "à confirmer avec votre organisme de formation",
}
FICHIERS = {"controles": "controles-fr.json", "habilitations": "habilitations-fr.json"}


def charger(nom, dossier=SOURCES):
    with open(Path(dossier) / FICHIERS[nom], encoding="utf-8") as f:
        return json.load(f)


def lignes_avec_mention(nom, dossier=SOURCES):
    lignes = []
    for ligne in charger(nom, dossier)["lignes"]:
        ligne = dict(ligne)
        ligne["mention"] = MENTIONS[nom] if ligne.get("a_confirmer") else ""
        lignes.append(ligne)
    return lignes


def contenu(dossier=SOURCES):
    entete = charger("controles", dossier)["entete"]
    donnees = {nom: lignes_avec_mention(nom, dossier) for nom in FICHIERS}
    corps = json.dumps(donnees, ensure_ascii=False, indent=2)
    return (
        "// Généré par outils/generer_catalogue.py à partir de docs/catalogue/*.json : ne pas éditer.\n"
        "// Catalogue des contrôles réglementaires et des habilitations (France), validé le %s.\n"
        "// %s\n"
        "(function () {\n"
        "  \"use strict\";\n"
        "  function geler(valeur) {\n"
        "    if (valeur && typeof valeur === \"object\") {\n"
        "      Object.keys(valeur).forEach(function (cle) { geler(valeur[cle]); });\n"
        "      Object.freeze(valeur);\n"
        "    }\n"
        "    return valeur;\n"
        "  }\n"
        "  window.CatalogueFR = geler(%s);\n"
        "})();\n"
    ) % (entete["valide_le"], entete["avertissement"], corps.replace("\n", "\n  "))


def ecrire(sortie=None, dossier=SOURCES):
    cible = Path(sortie) if sortie else RACINE / "js" / "catalogue"
    cible.mkdir(parents=True, exist_ok=True)
    chemin = cible / "fr.js"
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        f.write(contenu(dossier))
    return chemin


if __name__ == "__main__":
    print(ecrire(sys.argv[1] if len(sys.argv) > 1 else None))
