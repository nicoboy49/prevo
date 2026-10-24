"""Calcul Python indépendant des couches calculées du wiki (ARCHITECTURE.md §20.3, tâches T96 et T112).

Refait, à partir des seuls CSV (bibliothèque standard), ce que rend Wiki.pageEquipement(equipementId,
{ maintenant }) et Wiki.listePages({ maintenant }) : consignation, pannes habituelles (symptômes, causes,
fourchettes, remèdes et récidives), pièces consommées, dernières interventions, même marque et modèle,
pannes des 12 derniers mois ; puis (T112) la couche d'un composant ancré (Wiki.pageComposant : article,
montage, consommations, remplacements) et celle d'un mode ancré sur une cause (Wiki.pageMode : cas,
équipements, remèdes). Écrit à partir du contrat, pas du code JavaScript.

    calcul = CalculWiki.depuis_dossier(Path("donnees/demo"))
    calcul.page("EQ-0001", "2026-10-19")      # même forme que Wiki.pageEquipement
    calcul.liste_pages("2026-10-19")          # même forme que Wiki.listePages
    calcul.composant("ART-0001")              # même forme que Wiki.pageComposant
    calcul.mode("C01")                        # même forme que Wiki.pageMode

Définitions retenues (rapport .chantier/rapports/T96.md) :
    cas        OT dont le type commence par « correctif », clôturé techniquement ou administrativement,
               avec un code symptôme ;
    panne      date de la DI d'origine (celle que l'OT désigne, sinon la plus ancienne DI acceptée qui
               pointe vers lui), sinon création de l'OT ;
    clôture    date de clôture technique, sinon date de fin ;
    récidive   autre OT correctif non annulé du même équipement, même cause, panne strictement après la
               clôture du cas et au plus tard le 30e jour de calendrier après elle ;
    jumeaux    autres équipements actifs de même marque et modèle (sans espaces ni casse).

Définitions de T112 (rapport .chantier/rapports/T112.md) :
    consommation  d'un article : OT clôturé (techniquement ou administrativement, tout type) dont la
                  quantité nette sortie de l'article (sorties − retours liés à cet OT) est positive ; date =
                  jour de la date de fin de l'OT ;
    montage       équipements de article_equipement (quantité de la première ligne, en texte) et équipements
                  des consommations ; source « liste », « consommation » ou « les deux » ; par repère ;
    remplacements par équipement des consommations : nombre d'OT, médiane des écarts en jours entre jours
                  d'intervention successifs (None sous 2) ; par repère ;
    cas d'un mode OT correctif clôturé de la cause (sans exiger de symptôme) ;
    un équipement inconnu n'entre dans aucune liste d'équipements.

Encyclopédie (T135, ARCHITECTURE.md §20.12, D113, D114) : refait ce que rendent Wiki.entite(id, { profil, maintenant }),
Wiki.listeEntites(type, { profil }), Wiki.accueilEncyclopedie({ profil, maintenant }), Wiki.ordreInterventions(ids)
et Wiki.references(textes, aTrancher) :

    calcul.entite("PANNE-S01", "technicien", "2026-10-19")
    calcul.liste_entites("machine", "responsable")
    calcul.accueil("demandeur", "2026-10-19")

    OT ouvert      Créé, Préparé, Planifié, En cours, En attente ; date d'un OT : fin, sinon début, sinon date
                   prévue, sinon création ;
    ordre          les ouverts d'abord (« En cours », puis date prévue croissante, sans date prévue en dernier, puis
                   identifiant), puis les autres de la date la plus récente à la plus ancienne (puis identifiant
                   décroissant) ;
    panne          code symptôme qui a un cas (OT correctif clôturé) ; identifiant « PANNE- » + code encodé comme
                   encodeURIComponent ; ses interventions : tous les OT du code ;
    pièces nettes  sorties − retours d'un article liés à un OT (positives) ; consommé : OT clôturé ;
    stock          mouvements par date puis identifiant : inventaire = quantité fixée, entrée et retour ajoutent,
                   sortie retire ; rupture : du mouvement qui laisse 0 ou moins à celui qui remonte au-dessus ;
    habilitation   celles qui comptent : une par intitulé (casse et espaces ignorés), l'échéance la plus lointaine (vide :
                   sans limite ; illisible : la plus faible), puis l'obtention la plus récente, puis l'identifiant ;
                   état : pas encore valable (obtention future), échue (échéance passée ou illisible), à renouveler
                   (dans les 60 jours, le jour même compris : RG8), valide ; l'accueil compte les techniciens actifs ;
    visibilité     demandeur : ni page technicien ni page intervention (null), pas de prix, références sans lien ;
                   technicien : tout sauf le taux horaire ; responsable : tout ;
    références     ordre d'apparition sur la page (T137) : « À trancher » (en tête), puis les textes ; sans numéro (la page
                   numérote, avec les OT de ses sections : D118, T143) ;
    petits numéros des articles (D118, T143 : CalculWiki.ot_des_articles) : par article consommé (machine) ou changé
                   (panne), les OT clôturés de la page où ses pièces nettes sont positives, du plus récent au plus ancien
                   (date de l'OT, puis identifiant), les 10 premiers et le nombre des autres ;
    intervention   (T137) motifAttente et motifAnnulation de l'OT, '' sans motif ;
    retours        (T137, « Pages qui renvoient ici ») d'une machine, d'un article, d'un savoir-faire ou d'une panne :
                   pages actives dont le champ liens (« ; ») désigne l'entité ou la ligne de son texte, rendues sous leur
                   page (texte d'une machine ou d'un article qui existe : la machine, l'article ; savoir-faire : lui-même ;
                   les autres n'ont plus de page), sans la page elle-même ni doublon, par titre puis identifiant ;
    savoir-faire   d'une machine ou d'un article (D116, T141) : rattachés à elle, ou dont le champ liens (le leur ou celui
                   d'une de leurs sous-pages) désigne l'entité ou la ligne de son texte ; sans les sous-pages, une fois
                   chacun, par titre puis identifiant.
Les en-têtes, mères et sous-pages d'un savoir-faire sont ceux de Wiki.page (testés par test_wiki_calculs.py) : le
calcul ne les refait pas.
"""
import csv
import datetime
import functools
import io
import json
import math
import re
import urllib.parse
from pathlib import Path

CLOTURES = ("Clôturé techniquement", "Clôturé administrativement")
OT_MINIMUM = 5
RECIDIVE_JOURS = 30
NOMBRE_DERNIERES = 10
SYMPTOMES_MAX = 5
CAUSES_MAX = 3
LONGUEUR_EXTRAIT = 160
Z_95 = 1.96

# Champs texte des tables lues (§3.2 : apostrophe de protection), avec leur drapeau « protégé ».
CHAMPS_TEXTE = {
    "equipements": {"repere": True, "designation": False, "marque": False, "modele": False,
                    "num_serie": True, "habilitation_requise": False, "consignation": False},
    "ordres_travail": {"motif_attente": False, "titre": False, "travail_a_faire": False, "consignes": False,
                       "compte_rendu": False, "motif_annulation": False, "astuce": False},
    "articles": {"reference": True, "designation": False, "fabricant": False, "ref_fabricant": True,
                 "emplacement": False, "unite": False},
    "codes_defaillance": {"code": False, "libelle": False},
    "demandes": {"demandeur": False, "symptome": False, "description": False, "motif_decision": False},
    "mouvements_stock": {"utilisateur": False, "commentaire": False},
    "localisations": {"libelle": False},
    "fournisseurs": {"nom": False, "contact": False, "telephone": True, "email": False},
    "techniciens": {"nom": False, "prenom": False, "metier": False},
    "habilitations": {"intitule": False},
    "ot_operations": {"operation": False, "valeur_attendue": False, "valeur_mesuree": False},
    "gammes": {"libelle": False, "consignes": False},
    "controles_reglementaires": {"nature": False, "texte_reference": False, "organisme": False, "observations": False},
    "wiki_pages": {"titre": False, "cle": False, "texte": False, "ot_cites": False, "liens": False, "modele": False,
                   "valide_par": False},
    "wiki_journal": {"pages": False, "changements": False, "contradictions": False, "raisons": False, "modele": False,
                     "decide_par": False, "motif": False},
}
TABLES = ("equipements", "ordres_travail", "articles", "codes_defaillance", "demandes", "mouvements_stock",
          "article_equipement", "localisations", "fournisseurs", "techniciens", "habilitations", "ot_temps",
          "ot_operations", "achats", "gammes", "controles_reglementaires", "wiki_pages", "wiki_journal")

# Encyclopédie (T135)
OUVERTS = ("Créé", "Préparé", "Planifié", "En cours", "En attente")
HORIZON_HABILITATION_JOURS = 60            # « à renouveler » : brief RG8 (module Équipe)
MACHINES_ACCUEIL = 3
PANNES_ACCUEIL = 6                         # pannes les plus fréquentes de l'accueil (maquette)
RUBRIQUES = {"équipement": ["En bref", "Astuces"], "composant": ["À quoi il sert"],
             "savoir-faire": ["Quand le faire", "Étapes", "Pièces et outillage", "Pièges", "Particularités par machine"]}
MOTIF_CITATION = re.compile(r"\[(OT-\d{4}-\d{4,})\]")

FORMES_A_PROTEGER = [re.compile(motif) for motif in (
    r"[0-9]+([.,][0-9]+)?", r"[0-9]+([.,][0-9]+)?[eE][+-]?[0-9]+",
    r"[0-9]{1,4}[/.\-][0-9]{1,2}([/.\-][0-9]{1,4})?", r"[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?",
    r"[0-9]+([.,][0-9]+)?\s?%")]


def protegee(valeur, protege):
    """Vrai si Prévo écrit cette valeur précédée d'une apostrophe (§3.2)."""
    if valeur == "":
        return False
    return bool(protege or re.match(r"[=+\-@\t\r]", valeur) or valeur.startswith("'")
                or any(forme.fullmatch(valeur.strip(" \t\r\n")) for forme in FORMES_A_PROTEGER))


def cellule(table, champ, brute):
    """Valeur en mémoire d'une cellule : apostrophe de protection retirée (champs texte), fin parasite ôtée."""
    brute = brute or ""
    textes = CHAMPS_TEXTE.get(table, {})
    if champ in textes:
        if brute.startswith("'") and protegee(brute[1:], textes[champ]):
            brute = brute[1:]
        return brute.rstrip(" \t\r")
    return brute.rstrip(" \t\r").strip()


def lire_table(table, contenu):
    if not contenu:
        return []
    if contenu.startswith("\ufeff"):
        contenu = contenu[1:]
    lecteur = csv.DictReader(io.StringIO(contenu, newline=""), delimiter=";")
    return [{champ: cellule(table, champ, valeur) for champ, valeur in ligne.items() if champ is not None}
            for ligne in lecteur]


def propre(valeur):
    return (valeur or "").strip()


def nombre(valeur):
    texte = propre(valeur).replace(",", ".").replace(" ", "").replace("\u00a0", "")
    if not texte:
        return None
    try:
        resultat = float(texte)
    except ValueError:
        return None
    return resultat if math.isfinite(resultat) else None


def wilson(k, n):
    """Intervalle de Wilson à 95 % de la part k / n (D59) ; None si n = 0."""
    if n <= 0:
        return None
    p = k / n
    z2 = Z_95 * Z_95
    denominateur = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denominateur
    marge = (Z_95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denominateur
    return {"bas": 0 if k == 0 else max(0.0, centre - marge), "haut": 1 if k == n else min(1.0, centre + marge)}


def jour_suivant(jour_iso, jours):
    try:
        return (datetime.date.fromisoformat(jour_iso) + datetime.timedelta(days=jours)).isoformat()
    except ValueError:
        return ""


def cle_modele(valeur):
    return re.sub(r"\s+", "", propre(valeur)).lower()


def extrait(compte_rendu):
    une_ligne = re.sub(r"\s+", " ", propre(compte_rendu))
    if len(une_ligne) <= LONGUEUR_EXTRAIT:
        return une_ligne
    return une_ligne[:LONGUEUR_EXTRAIT - 1].rstrip() + "…"


def selon(*criteres):
    """Tri par critères successifs : chaque critère est (fonction clé, décroissant ?)."""
    def comparer(a, b):
        for cle, decroissant in criteres:
            x, y = cle(a), cle(b)
            if x != y:
                return (1 if x < y else -1) if decroissant else (-1 if x < y else 1)
        return 0
    return functools.cmp_to_key(comparer)


class CalculWiki:

    def __init__(self, tables):
        """tables : { nom de table : texte du CSV } (table absente = vide)."""
        lu = {nom: lire_table(nom, tables.get(nom, "")) for nom in TABLES}
        self.equipements = lu["equipements"]
        self.par_id = {e["id"]: e for e in self.equipements}
        self.ordres = lu["ordres_travail"]
        self.articles = {a["id"]: a for a in lu["articles"]}
        self.mouvements = lu["mouvements_stock"]
        self.article_equipement = lu["article_equipement"]
        self.tables = lu                                   # encyclopédie (T135) : toutes les tables lues
        self.ordre_par_id = {ot["id"]: ot for ot in self.ordres}
        self.libelles = {}
        for code in lu["codes_defaillance"]:
            self.libelles.setdefault((propre(code["famille"]), propre(code["code"])), propre(code["libelle"]))
        self.date_panne = {}
        demandes = lu["demandes"]
        demandes_par_id = {d["id"]: d for d in demandes}
        for ot in self.ordres:
            origine = demandes_par_id.get(propre(ot.get("di_id")))
            if origine is None:
                vers_lui = sorted((d for d in demandes if propre(d.get("ot_id")) == ot["id"]),
                                  key=lambda d: propre(d["date_heure"]))
                origine = next((d for d in vers_lui if propre(d["statut"]) == "Acceptée"), None)
            quand = propre(origine["date_heure"]) if origine is not None else ""
            self.date_panne[ot["id"]] = quand or propre(ot["date_creation"])

    @classmethod
    def depuis_dossier(cls, dossier):
        dossier = Path(dossier)
        return cls({nom: (dossier / (nom + ".csv")).read_text(encoding="utf-8-sig")
                    for nom in TABLES if (dossier / (nom + ".csv")).is_file()})

    # -- outils -----------------------------------------------------------------------------------

    def libelle(self, famille, code):
        code = propre(code)
        if not code:
            return ""
        return self.libelles.get((famille, code)) or code

    def ordres_de(self, equipement_id):
        return [ot for ot in self.ordres if propre(ot["equipement_id"]) == equipement_id]

    @staticmethod
    def est_cloture(ot):
        return propre(ot["statut"]) in CLOTURES

    def est_un_cas(self, ot):
        return propre(ot["type"]).startswith("correctif") and self.est_cloture(ot) and propre(ot["symptome_code"]) != ""

    @staticmethod
    def cloture(ot):
        return propre(ot["date_cloture_tech"]) or propre(ot["date_fin"])

    def jour_panne(self, ot):
        return self.date_panne[ot["id"]][:10]

    def recidive(self, cas):
        """Vrai si un autre OT correctif non annulé du même équipement, même cause, tombe en panne dans
        ]clôture, jour de clôture + 30 jours]."""
        fin = self.cloture(cas)
        limite = jour_suivant(fin[:10], RECIDIVE_JOURS)
        cause = propre(cas["cause_code"])
        if not limite or not cause:
            return False
        for autre in self.ordres:
            if autre["id"] == cas["id"] or propre(autre["equipement_id"]) != propre(cas["equipement_id"]):
                continue
            if not propre(autre["type"]).startswith("correctif") or propre(autre["statut"]) == "Annulé":
                continue
            if propre(autre["cause_code"]) != cause:
                continue
            panne = self.date_panne[autre["id"]]
            if panne > fin and panne[:10] <= limite:
                return True
        return False

    # -- pannes habituelles -----------------------------------------------------------------------

    def pannes(self, equipement_ids):
        cas = [ot for ot in self.ordres if propre(ot["equipement_id"]) in equipement_ids and self.est_un_cas(ot)]
        par_symptome = {}
        for ot in cas:
            par_symptome.setdefault(propre(ot["symptome_code"]), []).append(ot)
        symptomes = []
        for code, liste in par_symptome.items():
            jours = sorted(j for j in (self.jour_panne(ot) for ot in liste) if j)
            symptomes.append({"code": code, "libelle": self.libelle("symptôme", code), "cas": len(liste),
                              "debut": jours[0] if jours else "", "fin": jours[-1] if jours else "", "_cas": liste})
        symptomes.sort(key=selon((lambda s: s["cas"], True), (lambda s: s["fin"], True), (lambda s: s["code"], False)))
        return [self.detail(s) for s in symptomes[:SYMPTOMES_MAX]]

    def detail(self, symptome):
        liste = symptome.pop("_cas")
        avec_cause = [ot for ot in liste if propre(ot["cause_code"])]
        symptome.update({"casAvecCause": len(avec_cause), "suffisant": symptome["cas"] >= OT_MINIMUM,
                         "peuDeCas": False, "causes": []})
        if not symptome["suffisant"]:
            return symptome
        par_cause = {}
        for ot in avec_cause:
            par_cause.setdefault(propre(ot["cause_code"]), []).append(ot)
        causes = []
        for code, cas_de_la_cause in par_cause.items():
            jours = sorted(j for j in (self.jour_panne(ot) for ot in cas_de_la_cause) if j)
            causes.append({"code": code, "libelle": self.libelle("cause", code), "nombre": len(cas_de_la_cause),
                           "dernierCas": jours[-1] if jours else "",
                           "fourchette": wilson(len(cas_de_la_cause), len(avec_cause)),
                           "remedes": self.remedes(cas_de_la_cause)})
        causes.sort(key=selon((lambda c: c["nombre"], True), (lambda c: c["dernierCas"], True),
                              (lambda c: c["code"], False)))
        symptome["causes"] = causes[:CAUSES_MAX]
        symptome["peuDeCas"] = any(c["fourchette"] is not None
                                   and (c["fourchette"]["haut"] - c["fourchette"]["bas"]) / 2 > 0.20
                                   for c in symptome["causes"])
        return symptome

    def remedes(self, cas_de_la_cause):
        par_remede = {}
        for ot in cas_de_la_cause:
            if propre(ot["remede_code"]):
                par_remede.setdefault(propre(ot["remede_code"]), []).append(ot)
        remedes = [{"code": code, "libelle": self.libelle("remède", code), "fois": len(liste),
                    "recidives": sum(1 for ot in liste if self.recidive(ot))} for code, liste in par_remede.items()]
        remedes.sort(key=selon((lambda r: r["fois"], True), (lambda r: r["recidives"], False),
                               (lambda r: r["code"], False)))
        return remedes

    # -- pièces, dernières interventions, synthèse ------------------------------------------------

    def pieces(self, ordres):
        ids = [ot["id"] for ot in ordres]
        nets = {}          # article -> { OT -> [quantité nette, dernière sortie] }
        for ot_id in ids:
            for mouvement in self.mouvements:
                if propre(mouvement["ot_id"]) != ot_id or propre(mouvement["type"]) not in ("sortie", "retour"):
                    continue
                net = nets.setdefault(propre(mouvement["article_id"]), {}).setdefault(ot_id, [0, ""])
                quantite = nombre(mouvement["quantite"]) or 0
                if propre(mouvement["type"]) == "sortie":
                    net[0] += quantite
                    net[1] = max(net[1], propre(mouvement["date"])[:10])
                else:
                    net[0] -= quantite
        pieces = []
        for article_id, par_ot in nets.items():
            total = sum(q for q, _ in par_ot.values())
            if total <= 0:
                continue
            positifs = [(q, d) for q, d in par_ot.values() if q > 0]
            article = self.articles.get(article_id, {})
            pieces.append({"articleId": article_id, "reference": propre(article.get("reference")) or article_id,
                           "designation": propre(article.get("designation")), "quantite": total,
                           "nombreOt": len(positifs), "derniereDate": max([d for _, d in positifs] + [""])})
        pieces.sort(key=selon((lambda p: p["nombreOt"], True), (lambda p: p["quantite"], True),
                              (lambda p: p["articleId"], False)))
        return pieces

    def dernieres(self, clotures):
        recentes = sorted(clotures, key=lambda ot: (propre(ot["date_fin"]), ot["id"]), reverse=True)
        return [{"id": ot["id"], "date": propre(ot["date_fin"]), "type": propre(ot["type"]), "titre": propre(ot["titre"]),
                 "codes": {"symptome": self.libelle("symptôme", ot["symptome_code"]),
                           "cause": self.libelle("cause", ot["cause_code"]),
                           "remede": self.libelle("remède", ot["remede_code"])},
                 "extrait": extrait(ot["compte_rendu"]), "dureeArret": nombre(ot["duree_arret_h"])}
                for ot in recentes[:NOMBRE_DERNIERES]]

    def pannes_12_mois(self, ordres, maintenant):
        fin = maintenant[:10]
        debut = jour_suivant(fin, -364)
        return sum(1 for ot in ordres if self.est_un_cas(ot) and debut <= self.jour_panne(ot) <= fin)

    # -- résultats --------------------------------------------------------------------------------

    def page(self, equipement_id, maintenant):
        equipement = self.par_id.get(equipement_id)
        if equipement is None:
            return None
        ordres = self.ordres_de(equipement_id)
        clotures = [ot for ot in ordres if self.est_cloture(ot)]
        marque, modele = cle_modele(equipement["marque"]), cle_modele(equipement["modele"])
        jumeaux = []
        if marque and modele:
            jumeaux = sorted((e for e in self.equipements if e["id"] != equipement_id and propre(e["actif"]) != "0"
                              and cle_modele(e["marque"]) == marque and cle_modele(e["modele"]) == modele),
                             key=lambda e: (propre(e["repere"]), e["id"]))
        consignation, document = equipement.get("consignation", ""), equipement.get("document", "")
        return {
            "equipement": {"id": equipement_id, "repere": propre(equipement["repere"]),
                           "designation": propre(equipement["designation"]), "marque": propre(equipement["marque"]),
                           "modele": propre(equipement["modele"])},
            "consignation": {"texte": consignation, "document": document}
            if propre(consignation) or propre(document) else None,
            "pannes": self.pannes({equipement_id}),
            "pannes12Mois": self.pannes_12_mois(ordres, maintenant),
            "pieces": self.pieces(ordres),
            "dernieres": self.dernieres(clotures),
            "total": len(clotures),
            "memeModele": {"equipements": [{"id": e["id"], "repere": propre(e["repere"])} for e in jumeaux],
                           "pannes": self.pannes({equipement_id} | {e["id"] for e in jumeaux})} if jumeaux else None,
        }

    def liste_pages(self, maintenant):
        pages = []
        for equipement in self.equipements:
            ordres = self.ordres_de(equipement["id"])
            clotures = [ot for ot in ordres if self.est_cloture(ot)]
            if not clotures:
                continue
            pages.append({"equipementId": equipement["id"], "repere": propre(equipement["repere"]),
                          "designation": propre(equipement["designation"]),
                          "pannes12Mois": self.pannes_12_mois(ordres, maintenant)})
        pages.sort(key=selon((lambda p: p["pannes12Mois"], True), (lambda p: p["repere"], False),
                             (lambda p: p["equipementId"], False)))
        return pages

    # -- composant ancré (T112) --------------------------------------------------------------------

    def repere(self, equipement_id):
        return propre(self.par_id[equipement_id]["repere"])

    def stock(self, article_id):
        """Stock d'après les mouvements, par date puis identifiant : un inventaire fixe la valeur, une
        entrée ou un retour ajoute, une sortie retire ; arrondi au millionième."""
        stock = 0
        mouvements = sorted((m for m in self.mouvements if m["article_id"] == article_id),
                            key=lambda m: (m["date"], m["id"]))
        for mouvement in mouvements:
            quantite = nombre(mouvement["quantite"]) or 0
            if mouvement["type"] == "inventaire":
                stock = quantite
            elif mouvement["type"] in ("entrée", "retour"):
                stock += quantite
            elif mouvement["type"] == "sortie":
                stock -= quantite
        return math.floor(stock * 1e6 + 0.5) / 1e6

    def consommations(self, article_id):
        nets = {}
        for mouvement in self.mouvements:
            ot_id, sens = propre(mouvement["ot_id"]), propre(mouvement["type"])
            if propre(mouvement["article_id"]) != article_id or not ot_id or sens not in ("sortie", "retour"):
                continue
            quantite = nombre(mouvement["quantite"]) or 0
            nets[ot_id] = nets.get(ot_id, 0) + (quantite if sens == "sortie" else -quantite)
        resultat = []
        for ot_id, quantite in nets.items():
            ot = self.ordre_par_id.get(ot_id)
            if quantite > 0 and ot is not None and self.est_cloture(ot):
                resultat.append({"otId": ot_id, "date": propre(ot["date_fin"])[:10],
                                 "equipementId": propre(ot["equipement_id"]), "quantite": quantite})
        resultat.sort(key=selon((lambda c: c["date"], True), (lambda c: c["otId"], False)))
        return resultat

    def montage(self, article_id):
        listes = {}
        for ligne in self.article_equipement:
            equipement_id = propre(ligne["equipement_id"])
            if propre(ligne["article_id"]) == article_id and equipement_id and equipement_id not in listes:
                listes[equipement_id] = propre(ligne["quantite"]).replace(" ", "").replace(",", ".")
        consommes = {c["equipementId"] for c in self.consommations(article_id)}
        resultat = []
        for equipement_id in set(listes) | consommes:
            if equipement_id not in self.par_id:
                continue
            dans_liste, consomme = equipement_id in listes, equipement_id in consommes
            resultat.append({"equipementId": equipement_id, "repere": self.repere(equipement_id),
                             "quantite": listes.get(equipement_id, ""),
                             "source": "les deux" if dans_liste and consomme else ("liste" if dans_liste else "consommation")})
        resultat.sort(key=lambda m: (m["repere"], m["equipementId"]))
        return resultat

    @staticmethod
    def jour_lisible(jour_iso):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", jour_iso):
            return None
        try:
            return datetime.date.fromisoformat(jour_iso)
        except ValueError:
            return None

    @staticmethod
    def mediane(valeurs):
        triees = sorted(valeurs)
        n = len(triees)
        if n == 0:
            return None
        return triees[n // 2] if n % 2 else (triees[n // 2 - 1] + triees[n // 2]) / 2

    def remplacements(self, article_id):
        par_equipement = {}
        for consommation in self.consommations(article_id):
            par_equipement.setdefault(consommation["equipementId"], []).append(consommation)
        resultat = []
        for equipement_id, liste in par_equipement.items():
            if equipement_id not in self.par_id:
                continue
            jours = sorted(j for j in (self.jour_lisible(c["date"]) for c in liste) if j is not None)
            ecarts = [(apres - avant).days for avant, apres in zip(jours, jours[1:])]
            resultat.append({"equipementId": equipement_id, "repere": self.repere(equipement_id),
                             "nombre": len({c["otId"] for c in liste}),
                             "intervalleMedianJours": self.mediane(ecarts) if len(jours) >= 2 else None})
        resultat.sort(key=lambda r: (r["repere"], r["equipementId"]))
        return resultat

    def composant(self, article_id):
        article = self.articles.get(article_id)
        if article is None:
            return None
        return {
            "article": {"id": article_id, "reference": propre(article.get("reference")),
                        "designation": propre(article.get("designation")), "fabricant": propre(article.get("fabricant")),
                        "refFabricant": propre(article.get("ref_fabricant")),
                        "emplacement": propre(article.get("emplacement")), "stock": self.stock(article_id)},
            "montage": self.montage(article_id),
            "consommations": self.consommations(article_id),
            "remplacements": self.remplacements(article_id),
        }

    # -- mode ancré sur une cause (T112) -----------------------------------------------------------

    def mode(self, cause):
        cas = [ot for ot in self.ordres if propre(ot["type"]).startswith("correctif") and self.est_cloture(ot)
               and propre(ot["cause_code"]) == cause]
        par_equipement, par_remede = {}, {}
        for ot in cas:
            par_equipement[propre(ot["equipement_id"])] = par_equipement.get(propre(ot["equipement_id"]), 0) + 1
            if propre(ot["remede_code"]):
                par_remede[propre(ot["remede_code"])] = par_remede.get(propre(ot["remede_code"]), 0) + 1
        equipements = [{"equipementId": e, "repere": self.repere(e), "cas": n}
                       for e, n in par_equipement.items() if e in self.par_id]
        equipements.sort(key=selon((lambda e: e["cas"], True), (lambda e: e["repere"], False),
                                   (lambda e: e["equipementId"], False)))
        remedes = [{"code": code, "libelle": self.libelle("remède", code), "fois": n} for code, n in par_remede.items()]
        remedes.sort(key=selon((lambda r: r["fois"], True), (lambda r: r["code"], False)))
        return {"cause": {"code": cause, "libelle": self.libelle("cause", cause)}, "cas": len(cas),
                "equipements": equipements, "remedes": remedes}

    # -- encyclopédie (T135, §20.12) : index ----------------------------------------------------------

    def index(self):
        """Index de l'encyclopédie, calculés une fois (les tables ne changent pas)."""
        if getattr(self, "_index", None) is not None:
            return self._index
        t = self.tables
        nets = {}                                    # OT -> {article: quantité nette}, dans l'ordre des mouvements
        for m in sorted(self.mouvements, key=lambda m: (val(m, "date"), val(m, "id"))):
            if not val(m, "ot_id") or val(m, "type") not in ("sortie", "retour"):
                continue
            q = nombre(m.get("quantite")) or 0
            par_article = nets.setdefault(val(m, "ot_id"), {})
            par_article[val(m, "article_id")] = par_article.get(val(m, "article_id"), 0) + (q if val(m, "type") == "sortie" else -q)
        self._index = {
            "nets": nets,
            "cas": [ot for ot in self.ordres if self.est_un_cas(ot)],
            "localisations": {l["id"]: l for l in t["localisations"]},
            "fournisseurs": {f["id"]: f for f in t["fournisseurs"]},
            "techniciens": {x["id"]: x for x in t["techniciens"]},
            "demandes": {d["id"]: d for d in t["demandes"]},
            "pages": {p["id"]: p for p in t["wiki_pages"]},
            "actives": [p for p in t["wiki_pages"] if val(p, "statut") != "archivée"],
        }
        self._index["codes_avec_cas"] = {val(ot, "symptome_code") for ot in self._index["cas"]}
        return self._index

    # -- encyclopédie : ordre, références aux entités --------------------------------------------------

    @staticmethod
    def date_ot(ot):
        return val(ot, "date_fin") or val(ot, "date_debut") or val(ot, "date_prevue") or val(ot, "date_creation")

    def avant(self, a, b):
        """Ordre des interventions (D113) : -1 si a vient avant b."""
        ouvert_a, ouvert_b = val(a, "statut") in OUVERTS, val(b, "statut") in OUVERTS
        if ouvert_a != ouvert_b:
            return -1 if ouvert_a else 1
        if ouvert_a:
            cle_a = (val(a, "statut") != "En cours", jour(a.get("date_prevue")) == "", jour(a.get("date_prevue")), val(a, "id"))
            cle_b = (val(b, "statut") != "En cours", jour(b.get("date_prevue")) == "", jour(b.get("date_prevue")), val(b, "id"))
            return -1 if cle_a < cle_b else (1 if cle_a > cle_b else 0)
        cle_a, cle_b = (self.date_ot(a), val(a, "id")), (self.date_ot(b), val(b, "id"))
        return -1 if cle_a > cle_b else (1 if cle_a < cle_b else 0)

    def ordonner(self, ordres):
        return sorted(ordres, key=functools.cmp_to_key(self.avant))

    def ordre_interventions(self, ids):
        connus = []
        for ot_id in ids:
            ot = self.ordre_par_id.get(propre(ot_id))
            if ot is not None and ot not in connus:
                connus.append(ot)
        return [ot["id"] for ot in self.ordonner(connus)]

    def machine(self, equipement_id):
        e = self.par_id.get(equipement_id) if equipement_id else None
        if e is None:
            return None
        return {"equipementId": equipement_id, "titre": " — ".join(x for x in (val(e, "repere"), val(e, "designation")) if x),
                "lien": equipement_id}

    def article(self, article_id):
        a = self.articles.get(article_id) if article_id else None
        if a is None:
            return None
        return {"articleId": article_id, "titre": val(a, "designation") or val(a, "reference") or article_id, "lien": article_id}

    def technicien(self, technicien_id, profil):
        x = self.index()["techniciens"].get(technicien_id) if technicien_id else None
        if x is None:
            return None
        nom = " ".join(v for v in (val(x, "prenom"), val(x, "nom")) if v) or technicien_id
        return {"technicienId": technicien_id, "nom": nom, "lien": technicien_id if profil != "demandeur" else None}

    def panne(self, code):
        code = propre(code)
        if not code:
            return None
        return {"code": code, "libelle": self.libelle("symptôme", code),
                "lien": id_panne(code) if code in self.index()["codes_avec_cas"] else None}

    def lieu(self, localisation_id):
        localisations, noms, vus = self.index()["localisations"], [], set()
        courant = localisations.get(propre(localisation_id))
        while courant is not None and courant["id"] not in vus:
            vus.add(courant["id"])
            noms.insert(0, val(courant, "libelle"))
            courant = localisations.get(val(courant, "parent_id"))
        return " › ".join(n for n in noms if n)

    def element(self, ot, profil):
        """Ligne d'une liste d'interventions."""
        ids = [val(ot, "technicien_id")] + [val(x, "technicien_id") for x in self.tables["ot_temps"] if val(x, "ot_id") == ot["id"]]
        techniciens = []
        for technicien_id in dict.fromkeys(i for i in ids if i):
            if self.technicien(technicien_id, profil) is not None:
                techniciens.append(self.technicien(technicien_id, profil))
        return {"id": ot["id"], "titre": val(ot, "titre"), "statut": val(ot, "statut"), "type": val(ot, "type"),
                "date": self.date_ot(ot)[:10], "datePrevue": jour(ot.get("date_prevue")),
                "machine": self.machine(val(ot, "equipement_id")), "panne": self.panne(ot.get("symptome_code")),
                "techniciens": techniciens, "lien": ot["id"] if profil != "demandeur" else None}

    def elements(self, ordres, profil):
        return [self.element(ot, profil) for ot in self.ordonner(ordres)]

    # -- encyclopédie : pièces, pannes, codes ----------------------------------------------------------

    def pieces_nettes(self, ordres, clotures_seulement):
        totaux, ots = {}, {}
        for ot in ordres:
            if clotures_seulement and not self.est_cloture(ot):
                continue
            for article_id, net in self.index()["nets"].get(ot["id"], {}).items():
                if net > 0 and article_id in self.articles:
                    totaux[article_id] = totaux.get(article_id, 0) + net
                    ots.setdefault(article_id, []).append(ot)
        resultat = [dict(self.article(a), quantite=arrondi(q), ot=[o["id"] for o in self.ordonner(ots[a])])
                    for a, q in totaux.items()]
        resultat.sort(key=selon((lambda p: p["quantite"], True), (lambda p: p["articleId"], False)))
        return resultat

    def ot_des_articles(self, identifiant, montres=10):
        """Petits numéros des articles d'une page (D118, T143), recalculés ici sans pieces_nettes : [{ articleId, ot,
        autres }] des articles consommés d'une machine ou changés d'une panne, dans l'ordre de la page (quantité nette
        décroissante, puis article) ; ot : les `montres` plus récents (date de l'OT, puis identifiant, décroissants) des OT
        clôturés de la machine, ou des cas de la panne, où les pièces nettes de l'article (sorties − retours liés à l'OT)
        sont positives ; autres : le nombre des suivants."""
        if identifiant.startswith("PANNE-"):
            code = urllib.parse.unquote(identifiant[len("PANNE-"):])
            ordres = [ot for ot in self.ordres if self.est_un_cas(ot) and val(ot, "symptome_code") == code]
        else:
            ordres = [ot for ot in self.ordres if val(ot, "equipement_id") == identifiant and self.est_cloture(ot)]
        nets = {}                                    # OT -> {article: sorties - retours}
        for m in self.mouvements:
            if val(m, "ot_id") and val(m, "type") in ("sortie", "retour"):
                signe = 1 if val(m, "type") == "sortie" else -1
                par_article = nets.setdefault(val(m, "ot_id"), {})
                par_article[val(m, "article_id")] = par_article.get(val(m, "article_id"), 0) + signe * (nombre(m.get("quantite")) or 0)
        quantites, ots = {}, {}
        for ot in ordres:
            for article_id, net in nets.get(ot["id"], {}).items():
                if net > 0 and article_id in self.articles:
                    quantites[article_id] = quantites.get(article_id, 0) + net
                    ots.setdefault(article_id, []).append(ot)
        resultat = []
        for article_id in sorted(quantites, key=lambda a: (-round(quantites[a], 6), a)):
            recents = sorted(ots[article_id], key=lambda o: (self.date_ot(o), o["id"]), reverse=True)
            resultat.append({"articleId": article_id, "ot": [o["id"] for o in recents[:montres]],
                             "autres": max(0, len(recents) - montres)})
        return resultat

    def pannes_frequentes(self, ordres):
        par_code = {}
        for ot in ordres:
            if self.est_un_cas(ot):
                code = val(ot, "symptome_code")
                cas, derniere = par_code.get(code, (0, ""))
                par_code[code] = (cas + 1, max(derniere, self.date_ot(ot)[:10]))
        pannes = [{"code": code, "libelle": self.libelle("symptôme", code), "cas": cas, "derniere": derniere,
                   "lien": id_panne(code)} for code, (cas, derniere) in par_code.items()]
        pannes.sort(key=selon((lambda p: p["cas"], True), (lambda p: p["derniere"], True), (lambda p: p["code"], False)))
        return pannes

    def compter(self, cas, champ, famille):
        nombres = {}
        for ot in cas:
            if val(ot, champ):
                nombres[val(ot, champ)] = nombres.get(val(ot, champ), 0) + 1
        resultat = [{"code": c, "libelle": self.libelle(famille, c), "cas": n} for c, n in nombres.items()]
        resultat.sort(key=selon((lambda c: c["cas"], True), (lambda c: c["code"], False)))
        return resultat

    # -- encyclopédie : textes, références, savoir-faire ------------------------------------------------

    @staticmethod
    def textes(ligne, type_):
        if ligne is None:
            return {"pageId": "", "origine": "", "modele": "", "validePar": "", "valideLe": "", "rubriques": []}
        return {"pageId": ligne["id"], "origine": val(ligne, "origine"), "modele": val(ligne, "modele"),
                "validePar": val(ligne, "valide_par"), "valideLe": val(ligne, "valide_le"),
                "rubriques": rubriques(ligne.get("texte"), type_)}

    def references_detaillees(self, textes, a_trancher, profil):
        resultat = []
        for ot_id in references(textes, a_trancher):
            ot = self.ordre_par_id.get(ot_id)
            resultat.append({"id": ot_id, "date": self.date_ot(ot)[:10] if ot else "",
                             "titre": val(ot, "titre") if ot else "", "machine": self.machine(val(ot, "equipement_id")) if ot else None,
                             "lien": ot_id if ot is not None and profil != "demandeur" else None})
        return resultat

    def mere(self, ligne):
        mere = self.index()["pages"].get(val(ligne, "rattache_a")) if val(ligne, "rattache_a") else None
        return mere if mere is not None and val(mere, "type") == val(ligne, "type") else None

    def rattachement(self, ligne):
        source = self.mere(ligne) or ligne
        cible = source
        if not val(source, "equipement_id") and not val(source, "article_id") and val(source, "rattache_a"):
            cible = self.index()["pages"].get(val(source, "rattache_a"), {})
        machine = self.machine(val(cible, "equipement_id"))
        if machine is not None:
            return {"type": "machine", "id": machine["equipementId"], "titre": machine["titre"], "lien": machine["lien"]}
        article = self.article(val(cible, "article_id"))
        if article is not None:
            return {"type": "article", "id": article["articleId"], "titre": article["titre"], "lien": article["lien"]}
        return None

    def savoir_faire_de(self, type_, entite_id):
        """Savoir-faire (sans les sous-pages) rattachés à l'entité, ou dont le champ liens — le leur ou celui de l'une de
        leurs sous-pages — désigne l'entité ou la ligne de son texte (D116, T141), une fois chacun, par titre."""
        ancre = (self.texte_ancre("équipement", "equipement_id", entite_id) if type_ == "machine"
                 else self.texte_ancre("composant", "article_id", entite_id))
        cibles = {entite_id} | ({ancre["id"]} if ancre is not None else set())
        lies = set()
        for ligne in self.index()["actives"]:
            liens = {x.strip() for x in (ligne.get("liens") or "").split(";") if x.strip()}
            if val(ligne, "type") == "savoir-faire" and cibles & liens:
                lies.add((self.mere(ligne) or ligne)["id"])
        trouves = []
        for ligne in self.index()["actives"]:
            if val(ligne, "type") != "savoir-faire" or self.mere(ligne) is not None:
                continue
            r = self.rattachement(ligne)
            if (r is not None and r["type"] == type_ and r["id"] == entite_id) or ligne["id"] in lies:
                trouves.append({"id": ligne["id"], "titre": val(ligne, "titre"), "lien": ligne["id"]})
        return sorted(trouves, key=lambda s: (s["titre"], s["id"]))

    def texte_ancre(self, type_, champ, entite_id):
        return next((p for p in self.index()["actives"] if val(p, "type") == type_ and val(p, champ) == entite_id), None)

    def finir(self, base, textes, a_trancher, en_attente, profil):
        a_trancher = list(a_trancher or [])
        base.update({"textes": textes, "aTrancher": a_trancher, "enAttente": list(en_attente or []),
                     "references": self.references_detaillees(textes, a_trancher, profil), "retours": [],
                     "liens": {"machine": True, "panne": True, "article": True, "savoir-faire": True,
                               "technicien": profil != "demandeur", "intervention": profil != "demandeur"}})
        return base

    # -- encyclopédie : machine ------------------------------------------------------------------------

    def page_machine(self, e, profil, a_trancher, en_attente):
        equipement_id = e["id"]
        ordres = self.ordres_de(equipement_id)
        faits = [fait("Repère", val(e, "repere")), fait("Lieu", self.lieu(e.get("localisation_id"))),
                 fait("Marque et modèle", " ".join(x for x in (val(e, "marque"), val(e, "modele")) if x)),
                 fait("N° de série", val(e, "num_serie")), fait("Mise en service", jour(e.get("date_mes"))),
                 fait("Criticité", val(e, "criticite")), fait("État", val(e, "statut")),
                 fait("Habilitation requise", val(e, "habilitation_requise"))]
        if val(e, "parent_id"):
            parent = self.machine(val(e, "parent_id"))
            faits.append(fait("Fait partie de", parent["titre"] if parent else val(e, "parent_id"), parent["lien"] if parent else None))
        faits.append(fait("Interventions", len(ordres)))
        montes = {}
        for ligne in self.article_equipement:
            a = val(ligne, "article_id")
            if val(ligne, "equipement_id") == equipement_id and a and a not in montes and a in self.articles:
                montes[a] = nombre(ligne.get("quantite"))
        gammes = [{"id": g["id"], "libelle": val(g, "libelle"), "declencheur": val(g, "declencheur"),
                   "periodiciteJours": nombre(g.get("periodicite_jours")), "prochaine": jour(g.get("prochaine_echeance"))}
                  for g in self.tables["gammes"] if val(g, "equipement_id") == equipement_id and val(g, "actif") != "0"]
        controles = [{"id": c["id"], "nature": val(c, "nature"), "organisme": val(c, "organisme"),
                      "derniere": jour(c.get("derniere_date")), "prochaine": jour(c.get("prochaine_date"))}
                     for c in self.tables["controles_reglementaires"] if val(c, "equipement_id") == equipement_id]
        consignation, document = e.get("consignation") or "", e.get("document") or ""
        titre = self.machine(equipement_id)["titre"]
        sections = {
            "consignation": {"texte": consignation, "document": document} if propre(consignation) or propre(document) else None,
            "sousEnsembles": sorted((self.machine(x["id"]) for x in self.equipements
                                     if val(x, "parent_id") == equipement_id and x["id"] != equipement_id),
                                    key=lambda m: (m["titre"], m["equipementId"])),
            "pannes": self.pannes_frequentes(ordres),
            "interventions": self.elements(ordres, profil),
            "articlesMontes": sorted((dict(self.article(a), quantite=q) for a, q in montes.items()),
                                     key=lambda a: (a["titre"], a["articleId"])),
            "articlesConsommes": self.pieces_nettes(ordres, True),
            "savoirFaire": self.savoir_faire_de("machine", equipement_id),
            "gammes": sorted(gammes, key=lambda g: (g["prochaine"] == "", g["prochaine"], g["id"])),
            "controles": sorted(controles, key=lambda c: (c["prochaine"] == "", c["prochaine"], c["id"])),
        }
        ligne = self.texte_ancre("équipement", "equipement_id", equipement_id)
        base = {"id": equipement_id, "type": "machine", "titre": titre, "faits": faits, "sections": sections}
        return self.finir(base, self.textes(ligne, "équipement"), a_trancher, en_attente, profil)

    # -- encyclopédie : article ------------------------------------------------------------------------

    def stock_dans_le_temps(self, article_id, profil):
        """Stock rejoué mouvement par mouvement : (stock final, sorties imputées à un OT, ruptures)."""
        stock, debut, sorties, ruptures = 0, None, [], []
        for m in sorted((m for m in self.mouvements if val(m, "article_id") == article_id), key=lambda m: (val(m, "date"), val(m, "id"))):
            q = nombre(m.get("quantite")) or 0
            sens = val(m, "type")
            if sens == "inventaire":
                stock = q
            elif sens in ("entrée", "retour"):
                stock += q
            elif sens == "sortie":
                stock -= q
            reste = arrondi(stock)
            if val(m, "ot_id") and sens in ("sortie", "retour"):
                ot = self.ordre_par_id.get(val(m, "ot_id"))
                sorties.append({"id": m["id"], "date": jour(m.get("date")), "type": sens, "quantite": q, "ot": val(m, "ot_id"),
                                "machine": self.machine(val(ot, "equipement_id")) if ot else None, "stock": reste,
                                "lien": val(m, "ot_id") if ot is not None and profil != "demandeur" else None})
            if reste <= 0 and debut is None:
                debut = jour(m.get("date"))
            elif reste > 0 and debut is not None:
                ruptures.append({"debut": debut, "fin": jour(m.get("date"))})
                debut = None
        if debut is not None:
            ruptures.append({"debut": debut, "fin": ""})
        return arrondi(stock), sorties, ruptures

    @staticmethod
    def etat_stock(a, stock):
        point = nombre(a.get("point_commande"))
        if stock <= 0:
            return "rupture"
        return "sous le seuil" if point is not None and stock <= point else "en stock"

    def ordres_servis(self, article_id):
        """OT où les pièces nettes de l'article sont positives, dans l'ordre de leurs premiers mouvements."""
        return [ot_id for ot_id, par_article in self.index()["nets"].items() if par_article.get(article_id, 0) > 0]

    def nom_fournisseur(self, fournisseur_id):
        f = self.index()["fournisseurs"].get(propre(fournisseur_id))
        return (val(f, "nom") or f["id"]) if f is not None else propre(fournisseur_id)

    def page_article(self, a, profil, a_trancher, en_attente):
        article_id = a["id"]
        stock, sorties, ruptures = self.stock_dans_le_temps(article_id, profil)
        faits = [fait("Référence", val(a, "reference")), fait("Fabricant", val(a, "fabricant")),
                 fait("Référence du fabricant", val(a, "ref_fabricant")), fait("Emplacement", val(a, "emplacement")),
                 fait("Stock", stock), fait("Unité", val(a, "unite")), fait("État du stock", self.etat_stock(a, stock)),
                 fait("Stock de sécurité", nombre(a.get("stock_securite"))), fait("Point de commande", nombre(a.get("point_commande"))),
                 fait("Quantité de commande", nombre(a.get("qte_commande"))), fait("Délai (jours)", nombre(a.get("delai_jours"))),
                 fait("Fournisseur", self.nom_fournisseur(a.get("fournisseur_id")))]
        if profil != "demandeur":
            faits.append(fait("Prix unitaire", nombre(a.get("prix_unitaire"))))
        faits.append(fait("Critique", val(a, "critique") == "1"))
        commandes = []
        for achat in sorted((x for x in self.tables["achats"] if val(x, "article_id") == article_id), key=lambda x: (val(x, "date"), val(x, "id"))):
            commande = {"id": achat["id"], "date": jour(achat.get("date")), "quantite": nombre(achat.get("quantite")),
                        "fournisseur": self.nom_fournisseur(achat.get("fournisseur_id")), "statut": val(achat, "statut"),
                        "reception": jour(achat.get("date_reception"))}
            if profil != "demandeur":
                commande["prixUnitaire"] = nombre(achat.get("prix_unitaire"))
            commandes.append(commande)
        montee = {}
        for ligne in self.article_equipement:
            e = val(ligne, "equipement_id")
            if val(ligne, "article_id") == article_id and e and e not in montee and e in self.par_id:
                montee[e] = nombre(ligne.get("quantite"))
        consomme = {}
        for ot_id in self.ordres_servis(article_id):
            ot = self.ordre_par_id.get(ot_id)
            if ot is None or not self.est_cloture(ot) or self.machine(val(ot, "equipement_id")) is None:
                continue
            e = val(ot, "equipement_id")
            n, q = consomme.get(e, (0, 0))
            consomme[e] = (n + 1, arrondi(q + self.index()["nets"][ot_id][article_id]))
        sections = {
            "commandes": commandes, "sorties": sorties, "ruptures": ruptures,
            "montee": sorted((dict(self.machine(e), quantite=q) for e, q in montee.items()), key=lambda m: (m["titre"], m["equipementId"])),
            "consommeSur": sorted((dict(self.machine(e), nombreOt=n, quantite=q) for e, (n, q) in consomme.items()),
                                  key=selon((lambda m: m["nombreOt"], True), (lambda m: m["titre"], False),
                                            (lambda m: m["equipementId"], False))),
            "interventions": self.elements([self.ordre_par_id[i] for i in self.ordres_servis(article_id) if i in self.ordre_par_id], profil),
            "savoirFaire": self.savoir_faire_de("article", article_id),
        }
        ligne = self.texte_ancre("composant", "article_id", article_id)
        base = {"id": article_id, "type": "article", "titre": self.article(article_id)["titre"], "faits": faits, "sections": sections}
        return self.finir(base, self.textes(ligne, "composant"), a_trancher, en_attente, profil)

    # -- encyclopédie : panne, technicien, intervention, savoir-faire -----------------------------------

    def page_panne(self, identifiant, profil):
        try:
            code = urllib.parse.unquote(identifiant[len("PANNE-"):], errors="strict")
        except UnicodeDecodeError:
            return None
        cas = [ot for ot in self.index()["cas"] if val(ot, "symptome_code") == code]
        if not code or id_panne(code) != identifiant or not cas:
            return None
        jours = sorted(j for j in (self.date_ot(ot)[:10] for ot in cas) if j)
        par_machine = {}
        for ot in cas:
            if self.machine(val(ot, "equipement_id")) is not None:
                par_machine[val(ot, "equipement_id")] = par_machine.get(val(ot, "equipement_id"), 0) + 1
        machines = [dict(self.machine(e), cas=n) for e, n in par_machine.items()]
        machines.sort(key=selon((lambda m: m["cas"], True), (lambda m: m["titre"], False), (lambda m: m["equipementId"], False)))
        tous = [ot for ot in self.ordres if val(ot, "symptome_code") == code]
        base = {"id": identifiant, "type": "panne", "titre": self.libelle("symptôme", code),
                "faits": [fait("Code", code), fait("Cas", len(cas)), fait("Machines touchées", len(machines)),
                          fait("Premier cas", jours[0] if jours else ""), fait("Dernier cas", jours[-1] if jours else "")],
                "sections": {"machines": machines, "causes": self.compter(cas, "cause_code", "cause"),
                             "remedes": self.compter(cas, "remede_code", "remède"),
                             "articles": self.pieces_nettes(cas, True), "interventions": self.elements(tous, profil)}}
        return self.finir(base, None, [], [], profil)

    def habilitations(self, technicien_id, maintenant):
        aujourdhui = maintenant[:10]
        limite = jour_suivant(aujourdhui, HORIZON_HABILITATION_JOURS)

        def rang_echeance(h):
            echeance = jour(h.get("date_echeance"))
            if not echeance:
                return "9999-12-31"                                  # sans limite : la plus lointaine
            return echeance if self.jour_lisible(echeance) else "0000-00-00"   # illisible : la plus faible

        retenues = {}
        for h in self.tables["habilitations"]:
            cle = re.sub(r"\s+", "", val(h, "intitule").lower())
            if val(h, "technicien_id") != technicien_id or not cle:
                continue
            obtention = jour(h.get("date_obtention"))
            rang = (rang_echeance(h), obtention if self.jour_lisible(obtention) else "", h["id"])
            if cle not in retenues or rang > retenues[cle][0]:
                retenues[cle] = (rang, h)
        resultat = []
        for _, h in retenues.values():
            echeance, obtention = jour(h.get("date_echeance")), jour(h.get("date_obtention"))
            if echeance and self.jour_lisible(echeance) is None:
                etat = "échue"
            elif self.jour_lisible(obtention) and obtention > aujourdhui:
                etat = "pas encore valable"
            elif echeance and echeance < aujourdhui:
                etat = "échue"
            elif echeance and echeance <= limite:
                etat = "à renouveler"
            else:
                etat = "valide"
            resultat.append({"id": h["id"], "intitule": val(h, "intitule"), "obtention": obtention, "echeance": echeance, "etat": etat})
        resultat.sort(key=lambda h: (h["intitule"].casefold(), h["id"]))
        return resultat

    def ordres_du_technicien(self, technicien_id):
        ids = {ot["id"] for ot in self.ordres if val(ot, "technicien_id") == technicien_id}
        ids |= {val(x, "ot_id") for x in self.tables["ot_temps"] if val(x, "technicien_id") == technicien_id}
        return [self.ordre_par_id[i] for i in ids if i in self.ordre_par_id]

    def heures(self, technicien_id):
        return arrondi(sum(nombre(x.get("heures")) or 0 for x in self.tables["ot_temps"] if val(x, "technicien_id") == technicien_id))

    def page_technicien(self, x, profil, maintenant):
        ordres = self.ordres_du_technicien(x["id"])
        faits = [fait("Métier", val(x, "metier")), fait("Capacité (h par semaine)", nombre(x.get("capacite_h_semaine"))),
                 fait("Heures pointées", self.heures(x["id"])), fait("Interventions", len(ordres)),
                 fait("Actif", val(x, "actif") != "0")]
        if profil == "responsable":
            faits.append(fait("Taux horaire", nombre(x.get("taux_horaire"))))
        base = {"id": x["id"], "type": "technicien", "titre": self.technicien(x["id"], profil)["nom"], "faits": faits,
                "sections": {"habilitations": self.habilitations(x["id"], maintenant), "interventions": self.elements(ordres, profil)}}
        return self.finir(base, None, [], [], profil)

    def demande_origine(self, ot):
        demande = self.index()["demandes"].get(val(ot, "di_id")) if val(ot, "di_id") else None
        if demande is None:
            acceptees = sorted((d for d in self.tables["demandes"] if val(d, "ot_id") == ot["id"] and val(d, "statut") == "Acceptée"),
                               key=lambda d: val(d, "date_heure"))
            demande = acceptees[0] if acceptees else None
        if demande is None:
            return None
        return {"id": demande["id"], "date": val(demande, "date_heure"), "demandeur": val(demande, "demandeur"),
                "symptome": val(demande, "symptome"), "description": val(demande, "description"), "statut": val(demande, "statut")}

    def cite_dans(self, ot_id):
        pages = {}
        for ligne in self.index()["actives"]:
            if ot_id not in citations(ligne.get("texte")):
                continue
            type_ = val(ligne, "type")
            entree = None
            if type_ == "équipement" and self.machine(val(ligne, "equipement_id")):
                m = self.machine(val(ligne, "equipement_id"))
                entree = {"id": m["equipementId"], "type": "machine", "titre": m["titre"], "lien": m["lien"]}
            elif type_ == "composant" and self.article(val(ligne, "article_id")):
                a = self.article(val(ligne, "article_id"))
                entree = {"id": a["articleId"], "type": "article", "titre": a["titre"], "lien": a["lien"]}
            elif type_ == "savoir-faire":
                entree = {"id": ligne["id"], "type": "savoir-faire", "titre": val(ligne, "titre"), "lien": ligne["id"]}
            if entree is not None and entree["id"] not in pages:
                pages[entree["id"]] = entree
        return sorted(pages.values(), key=lambda p: (p["titre"], p["id"]))

    def page_intervention(self, ot, profil):
        ot_id = ot["id"]
        machine = self.machine(val(ot, "equipement_id"))
        technicien = self.technicien(val(ot, "technicien_id"), profil)
        panne = self.panne(ot.get("symptome_code"))
        demande = self.demande_origine(ot)
        faits = [fait("Machine", machine["titre"] if machine else val(ot, "equipement_id"), machine["lien"] if machine else None),
                 fait("Type", val(ot, "type")), fait("Priorité", val(ot, "priorite")), fait("Statut", val(ot, "statut")),
                 fait("Technicien", technicien["nom"] if technicien else "", technicien["lien"] if technicien else None),
                 fait("Créé le", val(ot, "date_creation")), fait("Prévu le", val(ot, "date_prevue")),
                 fait("Début", val(ot, "date_debut")), fait("Fin", val(ot, "date_fin")),
                 fait("Arrêt de production", val(ot, "arret_production") == "1"), fait("Durée d'arrêt (h)", nombre(ot.get("duree_arret_h"))),
                 fait("Panne", panne["libelle"] if panne else "", panne["lien"] if panne else None),
                 fait("Cause", self.libelle("cause", ot.get("cause_code"))), fait("Remède", self.libelle("remède", ot.get("remede_code"))),
                 fait("Demande d'origine", demande["id"] if demande else ""),
                 fait("Clôture technique", val(ot, "date_cloture_tech")), fait("Clôture administrative", val(ot, "date_cloture_admin"))]
        temps = []
        for x in sorted((x for x in self.tables["ot_temps"] if val(x, "ot_id") == ot_id), key=lambda x: (val(x, "date"), val(x, "id"))):
            qui = self.technicien(val(x, "technicien_id"), profil)
            temps.append({"id": x["id"], "date": jour(x.get("date")), "technicienId": val(x, "technicien_id"),
                          "nom": qui["nom"] if qui else "", "lien": qui["lien"] if qui else None, "heures": nombre(x.get("heures"))})
        operations = sorted((o for o in self.tables["ot_operations"] if val(o, "ot_id") == ot_id),
                            key=lambda o: (nombre(o.get("ordre")) or 0, val(o, "id")))
        sections = {
            "demande": demande, "travail": val(ot, "travail_a_faire"), "compteRendu": val(ot, "compte_rendu"),
            "astuce": val(ot, "astuce"), "motifAttente": val(ot, "motif_attente"), "motifAnnulation": val(ot, "motif_annulation"),
            "techniciens": self.element(ot, profil)["techniciens"],
            "pieces": [dict(self.article(a), quantite=arrondi(q)) for a, q in self.index()["nets"].get(ot_id, {}).items()
                       if q > 0 and a in self.articles],
            "operations": [{"ordre": nombre(o.get("ordre")), "operation": val(o, "operation"), "valeurAttendue": val(o, "valeur_attendue"),
                            "fait": val(o, "fait") == "1", "valeurMesuree": val(o, "valeur_mesuree")} for o in operations],
            "temps": temps, "citeDans": self.cite_dans(ot_id),
            "ficheOT": "#/ot/" + urllib.parse.quote(ot_id, safe="!*'()"),
        }
        base = {"id": ot_id, "type": "intervention", "titre": val(ot, "titre") or ot_id, "faits": faits, "sections": sections}
        return self.finir(base, None, [], [], profil)

    def page_savoir_faire(self, ligne, profil, a_trancher, en_attente):
        """Sans l'en-tête, la mère ni les sous-pages (ceux de Wiki.page, que le test compare à part)."""
        r = self.rattachement(ligne)
        faits = [fait("Rattaché à", r["titre"] if r else "", r["lien"] if r else None)]
        mere = self.mere(ligne)
        if mere is not None:
            faits.append(fait("Sous-page de", val(mere, "titre"), mere["id"]))
        base = {"id": ligne["id"], "type": "savoir-faire", "titre": val(ligne, "titre"), "faits": faits,
                "sections": {"rattachement": r}}
        return self.finir(base, self.textes(ligne, "savoir-faire"), a_trancher, en_attente, profil)

    def retours(self, entite):
        """« Pages qui renvoient ici » d'une entité (définition en tête)."""
        cibles = {entite["id"], (entite.get("textes") or {}).get("pageId") or ""} - {""}
        trouves = {}
        for ligne in self.index()["actives"]:
            liens = [x.strip() for x in (ligne.get("liens") or "").split(";") if x.strip()]
            if not cibles.intersection(liens):
                continue
            type_, retour = val(ligne, "type"), None
            if type_ == "équipement" and self.machine(val(ligne, "equipement_id")):
                m = self.machine(val(ligne, "equipement_id"))
                retour = {"id": m["equipementId"], "type": "machine", "titre": m["titre"], "lien": m["lien"]}
            elif type_ == "composant" and self.article(val(ligne, "article_id")):
                a = self.article(val(ligne, "article_id"))
                retour = {"id": a["articleId"], "type": "article", "titre": a["titre"], "lien": a["lien"]}
            elif type_ == "savoir-faire":
                retour = {"id": ligne["id"], "type": "savoir-faire", "titre": val(ligne, "titre"), "lien": ligne["id"]}
            if retour is not None and retour["id"] != entite["id"] and retour["id"] not in trouves:
                trouves[retour["id"]] = retour
        return sorted(trouves.values(), key=lambda r: (r["titre"], r["id"]))

    def entite(self, identifiant, profil, maintenant, a_trancher=None, en_attente=None):
        """Même forme que Wiki.entite(identifiant, { profil, maintenant }) ; a_trancher, en_attente : ce que rendent
        les crochets de wiki-journal.js (vides sans eux)."""
        resultat = self.entite_sans_retours(identifiant, profil, maintenant, a_trancher, en_attente)
        if resultat is not None and resultat["type"] in ("machine", "article", "savoir-faire", "panne"):
            resultat["retours"] = self.retours(resultat)
        return resultat

    def entite_sans_retours(self, identifiant, profil, maintenant, a_trancher=None, en_attente=None):
        identifiant = propre(identifiant)
        if not identifiant:
            return None
        if identifiant.startswith("PANNE-"):
            return self.page_panne(identifiant, profil)
        if identifiant in self.par_id:
            return self.page_machine(self.par_id[identifiant], profil, a_trancher, en_attente)
        if identifiant in self.articles:
            return self.page_article(self.articles[identifiant], profil, a_trancher, en_attente)
        if identifiant in self.index()["techniciens"]:
            return None if profil == "demandeur" else self.page_technicien(self.index()["techniciens"][identifiant], profil, maintenant)
        if identifiant in self.ordre_par_id:
            return None if profil == "demandeur" else self.page_intervention(self.ordre_par_id[identifiant], profil)
        ligne = self.index()["pages"].get(identifiant)
        if ligne is None or val(ligne, "statut") == "archivée":
            return None
        if val(ligne, "type") == "équipement" and val(ligne, "equipement_id") in self.par_id:
            return self.page_machine(self.par_id[val(ligne, "equipement_id")], profil, a_trancher, en_attente)
        if val(ligne, "type") == "composant" and val(ligne, "article_id") in self.articles:
            return self.page_article(self.articles[val(ligne, "article_id")], profil, a_trancher, en_attente)
        if val(ligne, "type") == "savoir-faire":
            return self.page_savoir_faire(ligne, profil, a_trancher, en_attente)
        return None

    # -- encyclopédie : listes et accueil ----------------------------------------------------------------

    def liste_machines(self, profil):
        def dans_un_cycle(e):
            courant, vus = e, set()
            while courant is not None and val(courant, "parent_id") and courant["id"] not in vus:
                vus.add(courant["id"])
                if val(courant, "parent_id") == e["id"]:
                    return True
                courant = self.par_id.get(val(courant, "parent_id"))
            return False

        enfants, racines = {}, []
        for e in self.equipements:
            parent = val(e, "parent_id")
            if parent and parent in self.par_id and not dans_un_cycle(e):
                enfants.setdefault(parent, []).append(e)
            else:
                racines.append(e)

        def noeud(e):
            ordres = self.ordres_de(e["id"])
            return dict(self.machine(e["id"]), lieu=self.lieu(e.get("localisation_id")),
                        marqueModele=" ".join(x for x in (val(e, "marque"), val(e, "modele")) if x),
                        interventions=len(ordres), pannes=self.pannes_frequentes(ordres),
                        sousEnsembles=sorted((noeud(x) for x in enfants.get(e["id"], [])), key=lambda m: (m["titre"], m["equipementId"])))

        groupes = {}
        for m in sorted((noeud(e) for e in racines), key=lambda m: (m["titre"], m["equipementId"])):
            groupes.setdefault(m["lieu"], []).append(m)
        return [{"lieu": lieu, "machines": groupes[lieu]} for lieu in sorted(groupes, key=lambda l: (l == "", l))]

    def liste_pannes(self):
        codes = []
        for ot in self.index()["cas"]:
            if val(ot, "symptome_code") not in codes:
                codes.append(val(ot, "symptome_code"))
        pannes = []
        for code in codes:
            cas = [ot for ot in self.index()["cas"] if val(ot, "symptome_code") == code]
            causes = self.compter(cas, "cause_code", "cause")
            pannes.append({"id": id_panne(code), "code": code, "titre": self.libelle("symptôme", code), "cas": len(cas),
                           "machines": len({val(ot, "equipement_id") for ot in cas if val(ot, "equipement_id") in self.par_id}),
                           "cause": {"code": causes[0]["code"], "libelle": causes[0]["libelle"]} if causes else None,
                           "derniere": max(self.date_ot(ot)[:10] for ot in cas), "lien": id_panne(code)})
        pannes.sort(key=selon((lambda p: p["cas"], True), (lambda p: p["code"], False)))
        return pannes

    def liste_articles(self):
        resultat = []
        for a in self.articles.values():
            stock = self.stock_dans_le_temps(a["id"], "responsable")[0]
            resultat.append(dict(self.article(a["id"]), reference=val(a, "reference"), emplacement=val(a, "emplacement"),
                                 stock=stock, unite=val(a, "unite"), etat=self.etat_stock(a, stock), critique=val(a, "critique") == "1",
                                 interventions=len([i for i in self.ordres_servis(a["id"]) if i in self.ordre_par_id])))
        return sorted(resultat, key=lambda a: (a["titre"], a["articleId"]))

    def liste_techniciens(self, profil, maintenant):
        resultat = [dict(self.technicien(x["id"], profil), metier=val(x, "metier"), actif=val(x, "actif") != "0",
                         interventions=len(self.ordres_du_technicien(x["id"])),
                         habilitations=len(self.habilitations(x["id"], maintenant)), heures=self.heures(x["id"]))
                    for x in self.tables["techniciens"]]
        return sorted(resultat, key=lambda x: (x["nom"], x["technicienId"]))

    def liste_savoir_faire(self):
        resultat = []
        for ligne in self.index()["actives"]:
            if val(ligne, "type") != "savoir-faire":
                continue
            mere = self.mere(ligne)
            resultat.append({"id": ligne["id"], "titre": val(ligne, "titre"), "rattachement": self.rattachement(ligne),
                             "mere": {"id": mere["id"], "titre": val(mere, "titre")} if mere is not None else None,
                             "lien": ligne["id"]})
        return sorted(resultat, key=lambda s: (s["titre"], s["id"]))

    def liste_entites(self, type_, profil, maintenant="2026-10-19"):
        if type_ == "machine":
            return self.liste_machines(profil)
        if type_ == "panne":
            return self.liste_pannes()
        if type_ == "article":
            return self.liste_articles()
        if type_ == "savoir-faire":
            return self.liste_savoir_faire()
        if type_ == "technicien":
            return None if profil == "demandeur" else self.liste_techniciens(profil, maintenant)
        if type_ == "intervention":
            return None if profil == "demandeur" else self.elements(self.ordres, profil)
        return None

    def suivi(self):
        """Suivi du wiki, définitions des compteurs du journal (wiki-ecrans.js, §20.9)."""
        journal = self.tables["wiki_journal"]

        def lire(valeur):
            try:
                lu = json.loads(valeur)
            except ValueError:
                return []
            return lu if isinstance(lu, list) else []

        a_trancher = sum(1 for e in journal if val(e, "statut") == "validée" for c in lire(e.get("contradictions"))
                         if isinstance(c, dict) and propre(c.get("statut")) == "ouverte")
        par_ot = {}
        for e in journal:
            if val(e, "nature") == "ingestion" and val(e, "ot_id"):
                par_ot.setdefault(val(e, "ot_id"), []).append(e)
        en_echec = 0
        for entrees in par_ot.values():
            if all(val(e, "statut") in ("rejetée", "refusée") for e in entrees):
                derniere = max(entrees, key=lambda e: int(re.sub(r"\D", "", e["id"]) or 0))
                en_echec += val(derniere, "statut") == "refusée"
        return {"aValider": sum(1 for e in journal if val(e, "statut") == "à valider"), "aTrancher": a_trancher,
                "enEchec": en_echec}

    def accueil(self, profil, maintenant):
        pannes = self.liste_pannes()
        articles = self.liste_articles()
        clotures = self.ordonner([ot for ot in self.ordres if self.est_cloture(ot)])
        machines = sorted((dict(self.machine(e["id"]), interventions=len(self.ordres_de(e["id"]))) for e in self.equipements),
                          key=selon((lambda m: m["interventions"], True), (lambda m: m["titre"], False), (lambda m: m["equipementId"], False)))
        habilitations = None
        if profil != "demandeur":
            liste = [h for x in self.tables["techniciens"] if val(x, "actif") != "0" for h in self.habilitations(x["id"], maintenant)]
            habilitations = {"suivies": len(liste), "aRenouveler": sum(1 for h in liste if h["etat"] == "à renouveler"),
                             "echues": sum(1 for h in liste if h["etat"] == "échue")}
        return {
            "nombres": {"machines": len(self.equipements), "pannes": len(pannes), "articles": len(articles),
                        "techniciens": None if profil == "demandeur" else len(self.tables["techniciens"]),
                        "savoirFaire": len(self.liste_savoir_faire()),
                        "interventions": None if profil == "demandeur" else len(self.ordres), "cloturees": len(clotures)},
            "machinesPlusDInterventions": machines[:MACHINES_ACCUEIL],
            "pannePlusFrequente": pannes[0] if pannes else None,
            "articles": {"sousLeSeuil": sum(1 for a in articles if a["etat"] == "sous le seuil"),
                         "enRupture": sum(1 for a in articles if a["etat"] == "rupture")},
            "habilitations": habilitations,
            "dernieres": [self.element(ot, profil) for ot in clotures[:NOMBRE_DERNIERES]],
            "pannesFrequentes": pannes[:PANNES_ACCUEIL],
            "suivi": self.suivi() if profil == "responsable" else None,
        }


# -- encyclopédie : outils sans état ------------------------------------------------------------------

def val(ligne, champ):
    return propre((ligne or {}).get(champ))


def jour(valeur):
    return propre(valeur)[:10]


def arrondi(valeur):
    """Au millionième, demi vers le haut (Math.round de JavaScript)."""
    return math.floor(valeur * 1e6 + 0.5) / 1e6


def fait(libelle, valeur, lien=None):
    return {"libelle": libelle, "valeur": valeur, "lien": lien or None}


def id_panne(code):
    """« PANNE- » et le code encodé comme le ferait encodeURIComponent."""
    return "PANNE-" + urllib.parse.quote(propre(code), safe="!*'()")


def citations(texte):
    return list(dict.fromkeys(MOTIF_CITATION.findall(texte or "")))


def rubriques(texte, type_):
    """Rubriques d'un texte stocké (« ## Rubrique », « - phrase »), dans l'ordre des rubriques du type."""
    lues = []
    for ligne in (texte or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        nette = ligne.strip()
        titre = re.fullmatch(r"##\s+(.+?)\s*", nette)
        phrase = re.fullmatch(r"-\s+(.*)", nette)
        if titre:
            lues.append({"nom": titre.group(1), "phrases": []})
        elif phrase and lues:
            lues[-1]["phrases"].append(phrase.group(1).strip())
    ordre = RUBRIQUES.get(type_, [])
    return sorted(lues, key=lambda r: ordre.index(r["nom"]) if r["nom"] in ordre else len(ordre))


def references(textes, a_trancher):
    """OT cités par « À trancher », en tête de la page (phrase, puis OT observés, sinon l'OT de l'entrée), puis par les
    textes (rubriques dans l'ordre), sans doublon, dans l'ordre de première apparition sur la page (T137)."""
    ids = []
    for contradiction in a_trancher or []:
        ids += citations(contradiction.get("phrase"))
        observes = [propre(o) for o in contradiction.get("ot") or [] if propre(o)]
        ids += observes or ([propre(contradiction.get("otSource"))] if propre(contradiction.get("otSource")) else [])
    for rubrique in (textes or {}).get("rubriques", []):
        for phrase in rubrique["phrases"]:
            ids += citations(phrase)
    return list(dict.fromkeys(ids))
