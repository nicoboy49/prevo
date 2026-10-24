"""Faux modèle de l'ingestion du wiki (lot 6, ARCHITECTURE.md §20.5 ; refonte 2, §20.12) : une réponse `ingestionWiki`
construite UNIQUEMENT à partir du message envoyé par Prévo (même message → même réponse). Sert au faux fournisseur
(tests/faux_fournisseur_ia.py) et au faux `claude` de la fabrication de la démo (tests/fixtures/wiki/faux_claude.py).

Il tient les longueurs lues dans l'en-tête de chaque texte reçu (« En bref : 2 phrases sur 3, 34 mots sur 60, à réécrire
en entier » ; un savoir-faire entier : « 3 phrases sur 30, 40 mots sur 600 ») : une phrase qui ne tient plus dans sa
rubrique ajoute seulement l'OT aux citations de la dernière phrase de la rubrique (il la confirme), sauf dans « En bref »,
réécrit en entier (D117, T142) : ses phrases (une phrase de même texte que celle de l'OT reçoit seulement l'OT), puis
celle de l'OT, les plus anciennes retirées au-delà des limites de l'en-tête (une phrase par panne, 3 au plus). Dans les
textes reçus, un lien vers un titre absent du catalogue et des pages reçues perd ses crochets (les mots restent), comme le
demande la consigne. Un texte qu'il modifie et qui est reçu dans d'anciennes rubriques (base de développement) est réécrit
dans les siennes : chaque ancienne rubrique devient une phrase « <rubrique> : <ses phrases> » de la première rubrique du
type, qui cite tous ses OT (chacune y est reprise ; ses liens vers des titres connus restent des liens).

Savoir-faire commun (D116, T141) : un seul par geste, titré par le premier geste de l'astuce (jusqu'à « puis », « : »,
« ; » ou la fin de sa première phrase), sans repère ; créé, il porte l'astuce dans ses « Étapes », chaque article reçu
(« Pièce : [[<article>]] ») dans « Pièces et outillage » et la phrase de sa machine (« [[<machine>]] : <titre de l'OT,
sans le repère> ») dans « Particularités par machine » ; reçu (même titre, ou ses « Étapes » portent déjà l'astuce), il
est complété au lieu d'être recréé (l'OT s'ajoute aux phrases de même texte ; la phrase de cette machine reçoit l'OT, ou
s'ajoute) ; au catalogue mais non reçu, il n'est ni créé ni modifié (seul le lien des « Astuces » le nomme).

    faux               « En bref » de la machine reçoit la phrase « <titre de l'OT, sans le repère> » (la panne, sans
                       fréquence ni comptage : T140) qui cite l'OT (ou, si une phrase de même texte existe déjà, l'OT
                       s'ajoute à ses citations), réécrit en entier ; si l'OT a une astuce, son savoir-faire commun est
                       créé ou complété, rattaché à la machine ;
    faux-textes        comme « faux », avec tous les textes de la refonte 2, chaque astuce à un seul endroit : la phrase
                       d'« En bref » lie la panne de l'OT (« <titre> ([[<libellé du symptôme>]]) », si elle est au
                       catalogue) ; une astuce courte (sans « puis ») va dans les « Astuces » de la machine, sans
                       savoir-faire ; une méthode (« … puis … ») crée ou complète son savoir-faire commun, et les
                       « Astuces » n'en reçoivent que le lien (« Méthode : voir [[<savoir-faire>]] ») ; « À quoi il sert » de chaque article reçu ne dit
                       que ce que l'OT observe de lui — « Défaut constaté : <libellé de la cause> » —, jamais où ni quand il
                       a été changé ni la panne qu'il a réglée (T140) ; sa page n'est pas renvoyée si l'OT n'en dit rien de
                       plus (sans panne au catalogue — préventif, OT sans symptôme — ou sans cause) : deux OT d'un même
                       article partis ensemble seraient rejoués (D112) ;
    faux-rien          « rien à ajouter » ;
    faux-contradiction en plus, une contradiction sur la première phrase de la machine ;
    faux-recent        la nouvelle phrase commence par « Désormais » (refusée pour un OT antérieur) ;
    faux-invente       la nouvelle phrase cite aussi OT-1999-9999 ;
    faux-retire        la première phrase de la machine hors d'« En bref » (réécrit en entier) disparaît ;
    faux-consigne      la nouvelle phrase est une consigne de sécurité ;
    faux-sans-ot       la nouvelle phrase ne cite aucun OT ;
    faux-cree-commun   en plus, un savoir-faire « Usure commune », rattaché à la machine, est créé s'il n'est pas déjà au
                       catalogue : deux OT de machines différentes partis ensemble le créeraient tous deux (collision,
                       D112 : le second est rejoué, puis le trouve au catalogue) ;
    faux-corrige       refusée puis corrigée : la nouvelle phrase ne cite aucun OT (refusée par les contrôles), sauf
                       dans une relance, qui reçoit la réponse de « faux » ;
    faux-refuse-deux   refusée deux fois : la nouvelle phrase ne cite aucun OT, puis, dans la relance, cite OT-1999-9999 ;
    faux-decoupe       comme « faux », puis un savoir-faire envoyé est découpé (§20.4 ; seules sous-pages, §20.12) — celui
                       dont la sous-page est déjà envoyée, sinon le premier dont la rubrique « Étapes » a des phrases :
                       ses « Étapes » partent dans une sous-page « <titre du savoir-faire> — étapes détaillées »
                       (savoir-faire rattaché à lui), et la mère garde à leur place une phrase de renvoi [[<sous-page>]]
                       qui cite tous les OT des phrases déplacées ; si cette sous-page est déjà envoyée, la nouvelle
                       phrase va dans ses « Étapes » (ni la machine ni la mère ne sont modifiées).

Relance avec la raison (§20.5) : le message est celui d'origine, suivi de « Ta réponse précédente : », de la réponse
refusée et de ses raisons ; la réponse est tirée du seul message d'origine (les variantes ci-dessus s'appliquent).
"""
import re

MARQUE_RELANCE = "\n\nTa réponse précédente :\n"
MOTIF_OT_INGERE = re.compile(r"^OT à intégrer : (OT-\d{4}-\d{4,})", re.M)
MOTIF_TITRE = re.compile(r"^Titre : (.*)$", re.M)
MOTIF_ASTUCE = re.compile(r"^Astuce pour la prochaine fois : (.*)$", re.M)
MOTIF_CODES = re.compile(r"^Codes : (.*)$", re.M)
MOTIF_EQUIPEMENT = re.compile(r"^Équipement : (.*)$", re.M)
# En-tête d'un texte envoyé (§20.12) : titre, type (l'un des trois), la mère d'une sous-page (« · sous-page de « … » »,
# titre qui peut contenir des parenthèses), puis ses longueurs (« · En bref : 2 phrases sur 5, 34 mots sur 120 · Astuces :
# 0 phrase sur 10 » ; un savoir-faire entier : « · 3 phrases sur 30, 40 mots sur 600 »).
MOTIF_ENTETE_PAGE = re.compile(r"^=== Page « (.+?) » \((équipement|composant|savoir-faire)"
                               r"(?: · sous-page de « (.+?) »)?((?: · [^·\n]+?)*)\) ===$", re.M)
MOTIF_LONGUEUR = re.compile(r"^(?:(.+?) : )?(\d+) phrases? sur (\d+)(?:, (\d+) mots? sur (\d+))?(, à réécrire en entier)?$")
RUBRIQUES = {"équipement": ["En bref", "Astuces"], "composant": ["À quoi il sert"],
             "savoir-faire": ["Quand le faire", "Étapes", "Pièces et outillage", "Pièges",
                              "Particularités par machine"]}     # = Wiki.RUBRIQUES
SUJET_DECOUPE = "étapes détaillées"
RUBRIQUE_EQUIPEMENT = "En bref"           # §20.12 : ce qu'il faut savoir d'abord de la machine, réécrit en entier (D117)
LIMITE_EN_BREF = {"phrases_max": 3, "mots_max": 60}     # si l'en-tête ne la donne pas (= Wiki.LIMITES)
RUBRIQUE_ASTUCES = "Astuces"
RUBRIQUE_ARTICLE = "À quoi il sert"
RUBRIQUE_SAVOIR_FAIRE = "Étapes"
RUBRIQUE_PIECES = "Pièces et outillage"
RUBRIQUE_PARTICULARITES = "Particularités par machine"    # D116 : une phrase par machine, avec son lien
MOTIF_CITATION = re.compile(r"\[(OT-\d{4}-\d{4,})\]")
MOTIF_LIEN = re.compile(r"\[\[([^\[\]]+)\]\]")
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


def lire_longueurs(texte):
    """Longueurs de l'en-tête → {rubrique ('' pour un savoir-faire entier): {"phrases", "mots", "phrases_max", "mots_max",
    "reecrite"}} (reecrite : « à réécrire en entier », D117)."""
    longueurs = {}
    for morceau in texte.split(" · ")[1:]:
        trouve = MOTIF_LONGUEUR.match(morceau.strip())
        if trouve:
            longueurs[trouve.group(1) or ""] = {
                "phrases": int(trouve.group(2)), "phrases_max": int(trouve.group(3)),
                "mots": int(trouve.group(4)) if trouve.group(4) else None,
                "mots_max": int(trouve.group(5)) if trouve.group(5) else None, "reecrite": bool(trouve.group(6))}
    return longueurs


def lire_message(message):
    """Ce que le faux modèle retient du message de Prévo : OT, titre, astuce, codes, machine, pages envoyées (avec leurs
    longueurs), catalogue (titres, et type de chaque titre)."""
    pages = []
    if "Pages concernées (texte actuel) :\n" in message:
        section = FIN_DES_PAGES.split(message.split("Pages concernées (texte actuel) :\n", 1)[1], 1)[0]
        entetes = list(MOTIF_ENTETE_PAGE.finditer(section))
        for rang, entete in enumerate(entetes):
            fin = entetes[rang + 1].start() if rang + 1 < len(entetes) else len(section)
            corps = section[entete.end():fin].strip("\n")
            pages.append({"titre": entete.group(1), "type": entete.group(2), "mere": entete.group(3) or "",
                          "longueurs": lire_longueurs(entete.group(4)),
                          "rubriques": [] if corps.strip() == "(page vide)" else lire_page(corps)})
    catalogue, types = [], {}
    if "Catalogue des pages :\n" in message:
        for ligne in message.split("Catalogue des pages :\n", 1)[1].splitlines():
            trouve = re.match(r"^- (.+) \((.+)\)$", ligne)
            if trouve:
                catalogue.append(trouve.group(1))
                types[trouve.group(1)] = trouve.group(2)
    titre = MOTIF_TITRE.search(message)
    astuce = MOTIF_ASTUCE.search(message)
    codes = MOTIF_CODES.search(message)
    equipement = MOTIF_EQUIPEMENT.search(message)
    return {"ot": MOTIF_OT_INGERE.search(message).group(1), "titre": titre.group(1).strip() if titre else "",
            "astuce": astuce.group(1).strip() if astuce else "", "codes": codes.group(1).strip() if codes else "",
            "repere": equipement.group(1).split(" — ", 1)[0].strip() if equipement else "",
            "pages": pages, "catalogue": catalogue, "types": types}


def est_relance(message):
    return MARQUE_RELANCE in message


def mots(texte):
    """Mots d'une phrase comme Prévo les compte (Wiki.nombreDeMots) : citations exclues, un lien compte son titre."""
    return len([mot for mot in texte.split() if any(caractere.isalnum() for caractere in mot)])


def sans_doublon(identifiants):
    vus = []
    for identifiant in identifiants:
        if identifiant not in vus:
            vus.append(identifiant)
    return vus


def tient(page, rubrique, texte):
    """La phrase tient dans la limite de l'en-tête : celle de sa rubrique, ou celle d'un savoir-faire entier (noms des
    rubriques compris) ; vrai sans limite connue. Les nombres sont recomptés sur le texte en cours de la réponse."""
    longueurs = page["longueurs"]
    limite = longueurs.get(rubrique) or longueurs.get("")
    if not limite:
        return True
    entiere = rubrique not in longueurs
    remplies = [r for r in page["rubriques"] if r["phrases"] and (entiere or r["rubrique"] == rubrique)]
    phrases = sum(len(r["phrases"]) for r in remplies) + 1
    total = sum(mots(p["texte"]) for r in remplies for p in r["phrases"]) + mots(texte)
    if entiere:
        total += sum(mots(r["rubrique"]) for r in remplies) + (0 if any(r["rubrique"] == rubrique for r in remplies)
                                                              else mots(rubrique))
    return phrases <= limite["phrases_max"] and (limite["mots_max"] is None or total <= limite["mots_max"])


def rubrique_de(page, nom):
    """La rubrique `nom` de la page (créée vide, en tête, si elle n'y est pas)."""
    trouvee = next((r for r in page["rubriques"] if r["rubrique"] == nom), None)
    if trouvee is None:
        trouvee = {"rubrique": nom, "phrases": []}
        page["rubriques"].insert(0, trouvee)
    return trouvee


def ajouter_phrase(page, nom, texte, citees):
    """Une phrase de plus dans une rubrique : même texte → les OT s'ajoutent à ses citations ; rubrique pleine (en-tête)
    → les OT s'ajoutent aux citations de sa dernière phrase (ils la confirment) ; sinon, la phrase nouvelle."""
    recoit = rubrique_de(page, nom)
    meme = next((phrase for phrase in recoit["phrases"] if phrase["texte"] == texte), None)
    if meme is None and not tient(page, nom, texte) and recoit["phrases"] and citees:
        meme = recoit["phrases"][-1]
    if meme is not None and citees:
        meme["ot"] = sans_doublon(meme["ot"] + citees)
    else:
        recoit["phrases"].append({"texte": texte, "ot": citees})


def reecrire_en_bref(page, texte, citees):
    """« En bref » réécrit en entier (D117) : ses phrases (une phrase de même texte reçoit seulement les OT), puis celle de
    l'OT ; au-delà des limites de l'en-tête, les plus anciennes partent (une synthèse, pas un historique)."""
    phrases = rubrique_de(page, RUBRIQUE_EQUIPEMENT)["phrases"]
    meme = next((phrase for phrase in phrases if phrase["texte"] == texte), None)
    if meme is not None:
        meme["ot"] = sans_doublon(meme["ot"] + citees)
    else:
        phrases.append({"texte": texte, "ot": citees})
    limite = page["longueurs"].get(RUBRIQUE_EQUIPEMENT) or LIMITE_EN_BREF
    while len(phrases) > 1 and (len(phrases) > limite["phrases_max"] or (
            limite["mots_max"] is not None and sum(mots(phrase["texte"]) for phrase in phrases) > limite["mots_max"])):
        phrases.pop(0)


def geste_de(astuce):
    """Titre du savoir-faire commun d'une astuce (D116) : son premier geste, sans repère — l'astuce jusqu'à « puis »,
    « : », « ; » ou la fin de sa première phrase."""
    geste = re.split(r",? puis | : |; |\. ", astuce.strip(), maxsplit=1)[0].strip(" .,;:")
    return geste[:1].upper() + geste[1:]


def particularite(equipement, lu):
    """Phrase de la machine dans « Particularités par machine » (D116) : son lien, puis le titre de l'OT sans le repère."""
    return "[[" + equipement["titre"] + "]] : " + (lu["titre"].split(" — ", 1)[-1] or "intervention")


def completer_savoir_faire(savoir, equipement, articles, lu, ot):
    """Savoir-faire commun reçu, complété (D116) : l'astuce dans ses « Étapes », les articles reçus dans « Pièces et
    outillage » (même texte : l'OT s'ajoute) ; la phrase de cette machine reçoit l'OT, ou s'ajoute."""
    ajouter_phrase(savoir, RUBRIQUE_SAVOIR_FAIRE, lu["astuce"], [ot])
    for article in articles:
        ajouter_phrase(savoir, RUBRIQUE_PIECES, "Pièce : [[" + article["titre"] + "]]", [ot])
    lien = "[[" + equipement["titre"] + "]]"
    machine = next((phrase for phrase in rubrique_de(savoir, RUBRIQUE_PARTICULARITES)["phrases"]
                    if phrase["texte"].startswith(lien)), None)
    if machine is not None:
        machine["ot"] = sans_doublon(machine["ot"] + [ot])
    else:
        ajouter_phrase(savoir, RUBRIQUE_PARTICULARITES, particularite(equipement, lu), [ot])


def retirer_liens_inconnus(pages, catalogue):
    """Dans les textes reçus, un lien vers un titre absent du catalogue et des pages reçues (ancienne page de mode, base
    de développement) perd ses crochets : les mots restent (sinon : « lien vers une page inconnue »)."""
    connus = set(catalogue) | {page["titre"] for page in pages}
    for page in pages:
        for rubrique in page["rubriques"]:
            for phrase in rubrique["phrases"]:
                phrase["texte"] = MOTIF_LIEN.sub(lambda lien: lien.group(0) if lien.group(1).strip() in connus
                                                 else lien.group(1), phrase["texte"])


def reprendre_anciennes(page):
    """Texte reçu dans d'anciennes rubriques (avant la refonte 2) : chacune devient une phrase « <rubrique> : <ses
    phrases> » (liens connus gardés, voir retirer_liens_inconnus) de la première rubrique du type, qui cite tous ses OT :
    chaque ancienne phrase est reprise."""
    permises = RUBRIQUES[page["type"]]
    anciennes = [r for r in page["rubriques"] if r["rubrique"] not in permises and r["phrases"]]
    page["rubriques"] = [r for r in page["rubriques"] if r["rubrique"] in permises]
    for ancienne in anciennes:
        texte = ancienne["rubrique"] + " : " + " ; ".join(p["texte"] for p in ancienne["phrases"])
        rubrique_de(page, permises[0])["phrases"].append(
            {"texte": texte, "ot": sans_doublon(ot for p in ancienne["phrases"] for ot in p["ot"])})


def modifiee(page):
    return {"action": "modifier", "titre": page["titre"], "type": page["type"], "rattache_a": "",
            "rubriques": [r for r in page["rubriques"] if r["phrases"]]}


def titre_de_sous_page(savoir):
    return savoir["titre"] + " — " + SUJET_DECOUPE


def a_decouper(pages):
    """faux-decoupe : le savoir-faire envoyé (pas une sous-page) dont la sous-page est déjà envoyée, sinon le premier dont
    la rubrique « Étapes » a des phrases ; None s'il n'y en a pas."""
    savoirs = [page for page in pages if page["type"] == "savoir-faire" and not page["mere"]]
    for savoir in savoirs:
        if any(page["mere"] == savoir["titre"] and page["titre"] == titre_de_sous_page(savoir) for page in pages):
            return savoir
    return next((savoir for savoir in savoirs if any(rubrique["rubrique"] == RUBRIQUE_SAVOIR_FAIRE and rubrique["phrases"]
                                                     for rubrique in savoir["rubriques"])), None)


def decouper(pages, savoir):
    """faux-decoupe (§20.4) : les « Étapes » du savoir-faire `savoir` partent dans une sous-page créée, rattachée à lui ;
    la mère, modifiée, garde à leur place une phrase de renvoi [[titre]] qui cite tous les OT des phrases déplacées
    (chacune y est « reprise »). La sous-page est mise avant sa mère : l'ordre ne compte pas."""
    titre = titre_de_sous_page(savoir)
    etapes = next(rubrique for rubrique in savoir["rubriques"] if rubrique["rubrique"] == RUBRIQUE_SAVOIR_FAIRE)
    citees = sans_doublon(identifiant for phrase in etapes["phrases"] for identifiant in phrase["ot"])
    pages.append({"action": "creer", "titre": titre, "type": "savoir-faire", "rattache_a": savoir["titre"],
                  "rubriques": [{"rubrique": RUBRIQUE_SAVOIR_FAIRE, "phrases": etapes["phrases"]}]})
    etapes["phrases"] = [{"texte": "Détail des étapes : voir [[" + titre + "]]", "ot": citees}]
    pages.append(modifiee(savoir))


def reponse_ingestion(message, modele="faux"):
    """Réponse JSON (objet Python) du faux modèle à un message `ingestionWiki` (d'origine ou de relance)."""
    relance = est_relance(message)
    if modele == "faux-corrige":
        modele = "faux" if relance else "faux-sans-ot"
    elif modele == "faux-refuse-deux":
        modele = "faux-invente" if relance else "faux-sans-ot"
    lu = lire_message(message.split(MARQUE_RELANCE, 1)[0])
    ot = lu["ot"]
    retirer_liens_inconnus(lu["pages"], lu["catalogue"])
    if modele == "faux-rien":
        return {"rien_a_ajouter": True, "pages": [], "contradictions": []}
    equipement = next((page for page in lu["pages"] if page["type"] == "équipement" and not page["mere"]), None)
    if equipement is None:
        return {"rien_a_ajouter": True, "pages": [], "contradictions": []}
    savoir = a_decouper(lu["pages"]) if modele == "faux-decoupe" else None
    sous_page = next((page for page in lu["pages"] if page["mere"] == savoir["titre"]
                      and page["titre"] == titre_de_sous_page(savoir)), None) if savoir else None
    cible = sous_page or equipement               # la page qui reçoit la nouvelle phrase, dans cette rubrique :
    rubrique_cible = RUBRIQUE_SAVOIR_FAIRE if sous_page else RUBRIQUE_EQUIPEMENT
    contradictions = []
    premiere = next((phrase for rubrique in cible["rubriques"] for phrase in rubrique["phrases"]), None)
    if modele == "faux-contradiction" and premiere:
        contradictions.append({"page": equipement["titre"], "phrase": premiere["texte"],
                               "observation": "Cet OT trouve une autre cause.", "ot": [ot]})
    # faux-retire : la première phrase hors d'« En bref » (réécrit en entier, D117 : le retrait y est permis).
    gardee = next((rubrique for rubrique in cible["rubriques"] if rubrique["rubrique"] != RUBRIQUE_EQUIPEMENT
                   and rubrique["phrases"]), None)
    if modele == "faux-retire" and gardee:
        gardee["phrases"].pop(0)
    if cible is equipement:
        reprendre_anciennes(equipement)
    texte = lu["titre"].split(" — ", 1)[-1] or "Intervention"      # la panne de l'OT, jamais sa fréquence (T140)
    panne = lu["codes"].split(" / ", 1)[0]
    panne = panne if panne and lu["types"].get(panne) == "panne" else ""      # libellé du symptôme, s'il est une panne
    textes = modele == "faux-textes"
    if textes and panne:
        texte += " ([[" + panne + "]])"
    citees = [ot]
    if modele == "faux-recent":
        texte = "Désormais, " + texte[0].lower() + texte[1:]
    elif modele == "faux-consigne":
        texte = "Consigner la machine avant de démonter"
    elif modele == "faux-invente":
        citees = [ot, "OT-1999-9999"]
    elif modele == "faux-sans-ot":
        citees = []
    if cible is equipement:
        reecrire_en_bref(equipement, texte, citees)
    else:
        ajouter_phrase(cible, rubrique_cible, texte, citees)
    # faux-textes : une astuce courte va dans « Astuces » ; une méthode (« … puis … ») dans son savoir-faire commun — reçu
    # (même titre, ou ses « Étapes » la portent déjà) : complété ; au catalogue seulement : ni créé ni modifié ; sinon créé —
    # et « Astuces » n'en reçoit que le lien : jamais aux deux endroits. faux : toute astuce a son savoir-faire commun.
    methode = textes and " puis " in lu["astuce"]
    commun = bool(lu["astuce"]) and (methode or not textes)
    geste = geste_de(lu["astuce"]) if commun else ""
    complete = next((page for page in lu["pages"] if page["type"] == "savoir-faire" and not page["mere"]
                     and (page["titre"] == geste or any(phrase["texte"] == lu["astuce"] for rubrique in page["rubriques"]
                                                        if rubrique["rubrique"] == RUBRIQUE_SAVOIR_FAIRE
                                                        for phrase in rubrique["phrases"]))), None) if commun else None
    titre_astuce = complete["titre"] if complete else geste
    articles = [page for page in lu["pages"] if page["type"] == "composant" and not page["mere"]]
    if textes and lu["astuce"]:
        astuce = "Méthode : voir [[" + titre_astuce + "]]" if methode else lu["astuce"]
        ajouter_phrase(equipement, RUBRIQUE_ASTUCES, astuce, [ot])
    pages = [modifiee(cible)]
    codes = lu["codes"].split(" / ")
    defaut = codes[1] if panne and len(codes) == 3 else ""         # la cause (symptôme / cause / remède) : ce que l'OT a vu
    if textes and defaut:
        # « À quoi il sert » : ce que l'OT observe de l'article (le défaut constaté), jamais où ni quand il a été changé ni
        # la panne qu'il a réglée ; s'il n'en dit rien de plus, sa page n'est pas renvoyée (T140).
        for article in articles:
            reprendre_anciennes(article)
            ajouter_phrase(article, RUBRIQUE_ARTICLE, "Défaut constaté : " + defaut, [ot])
            pages.append(modifiee(article))
    if complete is not None and complete is not savoir:
        completer_savoir_faire(complete, equipement, articles, lu, ot)
        pages.append(modifiee(complete))
    if savoir is not None and sous_page is None:
        decouper(pages, savoir)
    if commun and complete is None and geste not in lu["catalogue"]:
        rubriques = [{"rubrique": RUBRIQUE_SAVOIR_FAIRE, "phrases": [{"texte": lu["astuce"], "ot": [ot]}]}]
        if articles:
            rubriques.append({"rubrique": RUBRIQUE_PIECES, "phrases": [{"texte": "Pièce : [[" + article["titre"] + "]]",
                                                                        "ot": [ot]} for article in articles]})
        rubriques.append({"rubrique": RUBRIQUE_PARTICULARITES, "phrases": [{"texte": particularite(equipement, lu), "ot": [ot]}]})
        pages.append({"action": "creer", "titre": geste, "type": "savoir-faire", "rattache_a": equipement["titre"],
                      "rubriques": rubriques})
    if modele == "faux-cree-commun" and "Usure commune" not in lu["catalogue"]:
        pages.append({"action": "creer", "titre": "Usure commune", "type": "savoir-faire", "rattache_a": equipement["titre"],
                      "rubriques": [{"rubrique": "Quand le faire", "phrases": [{"texte": "Usure normale des pièces",
                                                                                "ot": [ot]}]}]})
    return {"rien_a_ajouter": False, "pages": pages, "contradictions": contradictions}
