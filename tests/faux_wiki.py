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
                       mêmes codes (donc de même cause) qui partiraient ensemble le créeraient tous deux (D112) ;
    faux-corrige       refusée puis corrigée : la nouvelle phrase ne cite aucun OT (refusée par les contrôles), sauf
                       dans une relance, qui reçoit la réponse de « faux » ;
    faux-refuse-deux   refusée deux fois : la nouvelle phrase ne cite aucun OT, puis, dans la relance, cite OT-1999-9999 ;
    faux-decoupe       comme « faux », puis la page de l'équipement est découpée (§20.4) : sa rubrique « Ce qui revient »
                       part dans une sous-page « <repère> — pannes qui reviennent » (type équipement, rattachée à la page
                       de l'équipement), et la mère garde à sa place une phrase de renvoi [[<sous-page>]] qui cite tous
                       les OT des phrases déplacées ; si cette sous-page est déjà envoyée, la nouvelle phrase y va (la
                       mère n'est pas modifiée).

Relance avec la raison (§20.5) : le message est celui d'origine, suivi de « Ta réponse précédente : », de la réponse
refusée et de ses raisons ; la réponse est tirée du seul message d'origine (les variantes ci-dessus s'appliquent).
"""
import re

MARQUE_RELANCE = "\n\nTa réponse précédente :\n"
MOTIF_OT_INGERE = re.compile(r"^OT à intégrer : (OT-\d{4}-\d{4,})", re.M)
MOTIF_TITRE = re.compile(r"^Titre : (.*)$", re.M)
MOTIF_ASTUCE = re.compile(r"^Astuce pour la prochaine fois : (.*)$", re.M)
MOTIF_CODES = re.compile(r"^Codes : (.*)$", re.M)
# En-tête d'une page envoyée : titre, type (l'un des quatre), la mère d'une sous-page (« · sous-page de « … » », titre
# qui peut contenir des parenthèses), puis sa taille (« · 2 phrases sur 30, 14 mots sur 600 »).
MOTIF_ENTETE_PAGE = re.compile(r"^=== Page « (.+?) » \((équipement|composant|mode|savoir-faire)"
                               r"(?: · sous-page de « (.+) »)?(?: · \d+ phrases sur \d+, \d+ mots sur \d+)?\) ===$", re.M)
SUJET_DECOUPE = "pannes qui reviennent"
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
            pages.append({"titre": entete.group(1), "type": entete.group(2), "mere": entete.group(3) or "",
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


def est_relance(message):
    return MARQUE_RELANCE in message


def decouper(pages, titre):
    """faux-decoupe (§20.4) : la rubrique « Ce qui revient » de la page de l'équipement (pages[0], modifiée) part dans
    une sous-page `titre` rattachée à elle ; la mère garde à sa place une phrase de renvoi [[titre]] qui cite tous les
    OT des phrases déplacées (chacune y est « reprise »)."""
    mere = pages[0]
    revient = next(rubrique for rubrique in mere["rubriques"] if rubrique["rubrique"] == "Ce qui revient")
    citees = []
    for phrase in revient["phrases"]:
        citees += [identifiant for identifiant in phrase["ot"] if identifiant not in citees]
    pages.append({"action": "creer", "titre": titre, "type": "équipement", "rattache_a": mere["titre"],
                  "rubriques": [{"rubrique": "Ce qui revient", "phrases": revient["phrases"]}]})
    revient["phrases"] = [{"texte": "Détail des pannes qui reviennent : voir [[" + titre + "]]", "ot": citees}]


def reponse_ingestion(message, modele="faux"):
    """Réponse JSON (objet Python) du faux modèle à un message `ingestionWiki` (d'origine ou de relance)."""
    relance = est_relance(message)
    if modele == "faux-corrige":
        modele = "faux" if relance else "faux-sans-ot"
    elif modele == "faux-refuse-deux":
        modele = "faux-invente" if relance else "faux-sans-ot"
    lu = lire_message(message.split(MARQUE_RELANCE, 1)[0])
    ot = lu["ot"]
    if modele == "faux-rien":
        return {"rien_a_ajouter": True, "pages": [], "contradictions": []}
    equipement = next((page for page in lu["pages"] if page["type"] == "équipement" and not page["mere"]), None)
    if equipement is None:
        return {"rien_a_ajouter": True, "pages": [], "contradictions": []}
    sous_page = None
    if modele == "faux-decoupe":
        titre_sous_page = equipement["titre"].split(" — ", 1)[0] + " — " + SUJET_DECOUPE
        sous_page = next((page for page in lu["pages"] if page["mere"] == equipement["titre"]
                          and page["titre"] == titre_sous_page), None)
    cible = sous_page or equipement               # la page qui reçoit la nouvelle phrase
    rubriques = cible["rubriques"]
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
    pages = [{"action": "modifier", "titre": cible["titre"], "type": "équipement", "rattache_a": "",
              "rubriques": [r for r in rubriques if r["phrases"]]}]
    if modele == "faux-decoupe" and sous_page is None:
        decouper(pages, titre_sous_page)
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
