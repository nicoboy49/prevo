"""Faux modèle de l'ingestion du wiki (lot 6, ARCHITECTURE.md §20.5) : une réponse `ingestionWiki` construite
UNIQUEMENT à partir du message envoyé par Prévo (même message → même réponse). Sert au faux fournisseur
(tests/faux_fournisseur_ia.py) et au faux `claude` de la fabrication de la démo.

    faux               la page de l'équipement reçoit la phrase « <titre de l'OT> : fréquent ici » qui cite l'OT (ou,
                       si une phrase de même texte existe déjà, l'OT s'ajoute à ses citations) ; toutes ses phrases et
                       tous ses OT sont gardés ; si l'OT a une astuce, un savoir-faire « Astuce de l'<OT> » est créé,
                       rattaché à la page de l'équipement ;
    faux-rien          « rien à ajouter » ;
    faux-contradiction en plus, une contradiction sur la première phrase de la page de l'équipement ;
    faux-recent        la nouvelle phrase commence par « Désormais » (refusée pour un OT antérieur) ;
    faux-invente       la nouvelle phrase cite aussi OT-1999-9999 ;
    faux-retire        la première phrase de la page de l'équipement disparaît ;
    faux-consigne      la nouvelle phrase est une consigne de sécurité ;
    faux-sans-ot       la nouvelle phrase ne cite aucun OT ;
    faux-cree-mode     en plus, un mode « Usure commune » est créé s'il n'est pas déjà au catalogue ;
    faux-mode-cause    en plus, un mode « Mode : <codes de l'OT> » est créé s'il n'est pas déjà au catalogue : deux OT de
                       mêmes codes (donc de même cause) qui partiraient ensemble le créeraient tous deux (D112).
"""
import re

MOTIF_OT_INGERE = re.compile(r"^OT à intégrer : (OT-\d{4}-\d{4,})", re.M)
MOTIF_TITRE = re.compile(r"^Titre : (.*)$", re.M)
MOTIF_ASTUCE = re.compile(r"^Astuce pour la prochaine fois : (.*)$", re.M)
MOTIF_CODES = re.compile(r"^Codes : (.*)$", re.M)
MOTIF_ENTETE_PAGE = re.compile(r"^=== Page « (.+) » \((.+)\) ===$", re.M)
MOTIF_CITATION = re.compile(r"\[(OT-\d{4}-\d{4,})\]")
FIN_DES_PAGES = re.compile(r"\n\n(?:Date d'intervention des OT déjà cités|Catalogue des pages)")


def lire_page(texte):
    """Balisage d'une page → [{rubrique, phrases: [{texte, ot}]}] (texte sans citations)."""
    rubriques = []
    for ligne in texte.splitlines():
        ligne = ligne.strip()
        if ligne.startswith("## "):
            rubriques.append({"rubrique": ligne[3:].strip(), "phrases": []})
        elif ligne.startswith("- ") and rubriques:
            corps = ligne[2:]
            rubriques[-1]["phrases"].append({"texte": " ".join(MOTIF_CITATION.sub(" ", corps).split()),
                                             "ot": MOTIF_CITATION.findall(corps)})
    return rubriques


def lire_message(message):
    """Ce que le faux modèle retient du message de Prévo : OT, titre, astuce, pages envoyées, catalogue."""
    pages = []
    if "Pages concernées (texte actuel) :\n" in message:
        section = FIN_DES_PAGES.split(message.split("Pages concernées (texte actuel) :\n", 1)[1], 1)[0]
        entetes = list(MOTIF_ENTETE_PAGE.finditer(section))
        for rang, entete in enumerate(entetes):
            fin = entetes[rang + 1].start() if rang + 1 < len(entetes) else len(section)
            corps = section[entete.end():fin].strip("\n")
            pages.append({"titre": entete.group(1), "type": entete.group(2),
                          "rubriques": [] if corps.strip() == "(page vide)" else lire_page(corps)})
    catalogue = []
    if "Catalogue des pages :\n" in message:
        for ligne in message.split("Catalogue des pages :\n", 1)[1].splitlines():
            trouve = re.match(r"^- (.+) \((.+)\)$", ligne)
            if trouve:
                catalogue.append(trouve.group(1))
    titre = MOTIF_TITRE.search(message)
    astuce = MOTIF_ASTUCE.search(message)
    codes = MOTIF_CODES.search(message)
    return {"ot": MOTIF_OT_INGERE.search(message).group(1), "titre": titre.group(1).strip() if titre else "",
            "astuce": astuce.group(1).strip() if astuce else "", "codes": codes.group(1).strip() if codes else "",
            "pages": pages, "catalogue": catalogue}


def reponse_ingestion(message, modele="faux"):
    """Réponse JSON (objet Python) du faux modèle à un message `ingestionWiki`."""
    lu = lire_message(message)
    ot = lu["ot"]
    if modele == "faux-rien":
        return {"rien_a_ajouter": True, "pages": [], "contradictions": []}
    equipement = next((page for page in lu["pages"] if page["type"] == "équipement"), None)
    if equipement is None:
        return {"rien_a_ajouter": True, "pages": [], "contradictions": []}
    rubriques = equipement["rubriques"]
    contradictions = []
    premiere = next((phrase for rubrique in rubriques for phrase in rubrique["phrases"]), None)
    if modele == "faux-contradiction" and premiere:
        contradictions.append({"page": equipement["titre"], "phrase": premiere["texte"],
                               "observation": "Cet OT trouve une autre cause.", "ot": [ot]})
    if modele == "faux-retire" and premiere:
        for rubrique in rubriques:
            if premiere in rubrique["phrases"]:
                rubrique["phrases"].remove(premiere)
    texte = (lu["titre"].split(" — ", 1)[-1] or "Intervention") + " : fréquent ici"
    citees = [ot]
    if modele == "faux-recent":
        texte = "Désormais, " + texte[0].lower() + texte[1:]
    elif modele == "faux-consigne":
        texte = "Consigner la machine avant de démonter"
    elif modele == "faux-invente":
        citees = [ot, "OT-1999-9999"]
    elif modele == "faux-sans-ot":
        citees = []
    revient = next((rubrique for rubrique in rubriques if rubrique["rubrique"] == "Ce qui revient"), None)
    if revient is None:
        revient = {"rubrique": "Ce qui revient", "phrases": []}
        rubriques.insert(0, revient)
    meme = next((phrase for phrase in revient["phrases"] if phrase["texte"] == texte), None)
    if meme is not None and citees:
        meme["ot"] = meme["ot"] + [identifiant for identifiant in citees if identifiant not in meme["ot"]]
    else:
        revient["phrases"].append({"texte": texte, "ot": citees})
    pages = [{"action": "modifier", "titre": equipement["titre"], "type": "équipement", "rattache_a": "",
              "rubriques": [r for r in rubriques if r["phrases"]]}]
    if lu["astuce"]:
        pages.append({"action": "creer", "titre": "Astuce de l'" + ot, "type": "savoir-faire",
                      "rattache_a": equipement["titre"],
                      "rubriques": [{"rubrique": "Étapes", "phrases": [{"texte": lu["astuce"], "ot": [ot]}]}]})
    if modele == "faux-mode-cause" and lu["codes"] and "Mode : " + lu["codes"] not in lu["catalogue"]:
        pages.append({"action": "creer", "titre": "Mode : " + lu["codes"], "type": "mode", "rattache_a": "",
                      "rubriques": [{"rubrique": "Causes", "phrases": [{"texte": "Constaté sur cet équipement", "ot": [ot]}]}]})
    if modele == "faux-cree-mode" and "Usure commune" not in lu["catalogue"]:
        pages.append({"action": "creer", "titre": "Usure commune", "type": "mode", "rattache_a": "",
                      "rubriques": [{"rubrique": "Causes", "phrases": [{"texte": "Usure normale des pièces", "ot": [ot]}]}]})
    return {"rien_a_ajouter": False, "pages": pages, "contradictions": contradictions}
