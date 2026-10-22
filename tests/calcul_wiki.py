"""Calcul Python indépendant de la couche calculée du wiki (ARCHITECTURE.md §20.3, tâche T96).

Refait, à partir des seuls CSV (bibliothèque standard), ce que rend Wiki.page(equipementId, { maintenant })
et Wiki.listePages({ maintenant }) : consignation, pannes habituelles (symptômes, causes, fourchettes,
remèdes et récidives), pièces consommées, dernières interventions, même marque et modèle, état de la
synthèse, pannes des 12 derniers mois. Écrit à partir du contrat, pas du code JavaScript.

    calcul = CalculWiki.depuis_dossier(Path("donnees/demo"))
    calcul.page("EQ-0001", "2026-10-19")      # même forme que Wiki.page
    calcul.liste_pages("2026-10-19")          # même forme que Wiki.listePages

Définitions retenues (rapport .chantier/rapports/T96.md) :
    cas        OT dont le type commence par « correctif », clôturé techniquement ou administrativement,
               avec un code symptôme ;
    panne      date de la DI d'origine (celle que l'OT désigne, sinon la plus ancienne DI acceptée qui
               pointe vers lui), sinon création de l'OT ;
    clôture    date de clôture technique, sinon date de fin ;
    récidive   autre OT correctif non annulé du même équipement, même cause, panne strictement après la
               clôture du cas et au plus tard le 30e jour de calendrier après elle ;
    jumeaux    autres équipements actifs de même marque et modèle (sans espaces ni casse).
"""
import csv
import datetime
import functools
import io
import math
import re
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
                       "compte_rendu": False, "motif_annulation": False},
    "articles": {"reference": True, "designation": False, "fabricant": False, "ref_fabricant": True,
                 "emplacement": False, "unite": False},
    "codes_defaillance": {"code": False, "libelle": False},
    "demandes": {"demandeur": False, "symptome": False, "description": False, "motif_decision": False},
    "mouvements_stock": {"utilisateur": False, "commentaire": False},
    "wiki_syntheses": {"texte": False, "ot_cites": False, "ot_sources": False, "modele": False,
                       "corrigee_par": False, "valide_par": False},
}
TABLES = ("equipements", "ordres_travail", "articles", "codes_defaillance", "demandes", "mouvements_stock",
          "wiki_syntheses")

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
        self.syntheses = lu["wiki_syntheses"]
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

    def synthese(self, equipement_id, clotures):
        """→ (synthèse courante ou None, état, remplacées) ; la synthèse porte « etat » et « depuis »."""
        siennes = [s for s in self.syntheses if propre(s["equipement_id"]) == equipement_id]
        ordre = lambda s: (propre(s["date_proposition"]), s["id"])
        remplacees = sorted((s for s in siennes if propre(s["statut"]) == "remplacée"), key=ordre, reverse=True)
        courantes = sorted((s for s in siennes if propre(s["statut"]) != "remplacée"), key=ordre, reverse=True)
        if not courantes:
            return None, "aucune", remplacees
        courante = dict(courantes[0])
        sources = {propre(x) for x in courante["ot_sources"].split(";") if propre(x)}
        depuis = sum(1 for ot in clotures
                     if ot["id"] not in sources and self.cloture(ot) > propre(courante["date_proposition"]))
        if propre(courante["statut"]) == "validée":
            etat = "a_revoir" if depuis > 0 else "validee"
        else:
            etat = "a_valider"
        courante.update({"etat": etat, "depuis": depuis})
        return courante, etat, remplacees

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
        synthese, etat, remplacees = self.synthese(equipement_id, clotures)
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
            "synthese": synthese,
            "etat": etat,
            "remplacees": remplacees,
            "peutProposer": len(clotures) >= OT_MINIMUM,
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
                          "pannes12Mois": self.pannes_12_mois(ordres, maintenant),
                          "etat": self.synthese(equipement["id"], clotures)[1]})
        pages.sort(key=selon((lambda p: p["pannes12Mois"], True), (lambda p: p["repere"], False),
                             (lambda p: p["equipementId"], False)))
        return pages
