"""Recette du L5 de la 2.2 « coût de l'arrêt » (T476 ; CDC §3.5, CS174, CS177 côté réseau ; D188, D126 prolongé ;
QUESTIONS-L2-L6 : L4-L6 Q4, Q5, Q6 ; conception L4-L5-L6 §3). De bout en bout, à l'écran, comme un responsable puis
comme un technicien, horloge du navigateur figée (jamais la date réelle). Les tests de chaque partie
(test_cout_arret_regles, test_parc_cout_arret, test_cout_arret_serveur, test_rapport_cout_arret,
test_indicateurs_cout_arret) ne sont pas recopiés ici : la recette les enchaîne sur des données à elle et refait chaque
montant par un calcul Python `decimal` indépendant du code de Prévo (cout_de_reference : durées au dix-millième
d'heure, coût horaire au centime, arrondi au centime ROUND_HALF_UP une fois par équipement).

Le parcours du serveur (CasParcoursServeur.parcours), le même sans comptes (portée « ce PC ») et avec les trois comptes
de test, sur une COPIE du jeu de démo complétée d'un jeu d'essai de novembre 2026 (après la fin de l'historique de la
démo, le 19/10/2026 : aucun autre arrêt ce mois-là), horloge au 07/12/2026 ; A, B, C : trois équipements de la démo
sans coût horaire, trouvés par les données (aucun identifiant écrit en dur) :
    A  pannes de 1,15 h et 0,2 h : 1,35 h × 1 250,50 €/h = 1 688,175 € → 1 688,18 € (le demi-centime, que le calcul
       en flottants arrondit à 1 688,17 €) ; une panne « En cours » sans durée (listée) ; un OT annulé de 10 h (ignoré) ;
    B  panne de 0,3333 h × 87,35 €/h = 29,11 € ; un préventif avec arrêt de 5 h, un correctif sans arrêt de 7 h
       (ignorés) ;
    C  panne de 4 h, sans coût horaire : « non chiffré », jamais estimé.
    Total attendu : 1 717,29 € (171 729 centimes), partiel : 1 équipement non chiffré, 1 OT sans durée.
Étapes, profil Responsable :
    fiches   C « non chiffré » ; coûts de A (« 1 250,50 ») et de B (« 87,35 ») saisis par le formulaire de la fiche
             (aucune valeur proposée), écrits sur le disque (1250.50, 87.35), fiche « 1 250,50 €/h » ;
    règle    Indicateurs.coutArret et Rapport.donnees du mois = le calcul Python fait sur les fichiers du disque ;
    rapport  figé depuis la tuile de l'accueil, relu sur le disque : tuile au centime, « Partiel : … », comparaison
             « non comparable : coût incomplet », Pareto par coût (A et B avec leurs montants, jamais C), C dans le
             Pareto des heures, « Comprendre », « Non calculable » (C et l'OT sans durée), courriel ; aucun autre
             montant ; une page A4 (PDF) ;
    écran    Indicateurs du mois : Pareto du coût (tableau au centime, cumul, graphique), notes, carte « Non chiffré »
             (C avec ses heures et « Saisir le coût horaire », l'OT sans durée avec son lien) ;
    C        coût saisi depuis la carte (« 412,30 ») : C entre au Pareto (4 h × 412,30 = 1 649,20 €), total
             3 366,49 €, reste l'OT sans durée ; le rapport figé garde ses chiffres (document inchangé).
Puis, profil Technicien : ni menu ni adresse Indicateurs, aucune tuile de rapport ; fiches de A, B, C sans la ligne du
coût ni « non chiffré » ; aucun montant du parcours dans la page. Avec comptes, en plus : equipements reçu avec
cout_arret_h vide sur chaque ligne (T473 : valeurs vidées, en-tête gardé), dans la page comme dans la réponse du
serveur ; de même pour le demandeur, à qui le rapport figé est refusé (403). Sans comptes, le serveur ne connaît pas
les rôles : la page du technicien porte les coûts, l'écran seul les tait (comme en démo, test_parc_cout_arret).

Démo (TestParcoursDemo) : index.html en file://, horloge à la date de référence de la démo (19/10/2026, dates non
décalées) ; Indicateurs.coutArret de septembre 2026, dernier mois de l'historique, = le calcul Python fait sur
donnees/demo ; l'équipement du rôle equipement_non_chiffre listé avec ses heures ; rapport figé (en mémoire) au centime,
une page A4 ; écran Indicateurs ; coût de cet équipement saisi depuis la carte ; vue du technicien (changement de
profil dans la même page : recharger perdrait la démo).

Écart trouvé (TestRapportFigeAuTechnicien, sans navigateur) : avec comptes, le technicien lit le rapport mensuel figé
(GET /api/documents/<nom>, nom lu dans parametres.rapports_mensuels, qu'il reçoit) : coût de l'arrêt par équipement
et heures d'arrêt, d'où le coût horaire que T473 lui cache (et le coût de maintenance, D126). Le refus attendu est un
test expectedFailure, cerné par un test qui passe (l'écart exact, rien d'autre) ; à trancher par l'orchestrateur
(serveur.py : documents réservés au responsable).

Aucune requête vers une autre adresse que l'application, sauf la lecture de version existante de T305 (CS177).
Jamais de données réelles : copie temporaire de donnees/demo (serveur) ou démo en mémoire.

Bibliothèque standard + Playwright. Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_recette_cout_arret.py" -v
"""
import calendar
import csv
import datetime
import io
import math
import re
import shutil
import tempfile
import unittest
import urllib.parse
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from commun import (ADRESSE_VERSION_JSON, COMPTES_DE_TEST, DOSSIER_DEMO, CasNavigateur, ServeurPrevo, attendre_pret,
                    preregler_profil, scenarios_demo, url_fichier)
from test_droits_format4 import BOM, REFUS_DOCUMENT, requete
from test_indicateurs_cout_arret import (ATTENDRE_GRAPHIQUES_JS, LIRE_CARTE_JS, LIRE_PARETO_JS, NOMBRE_GRAPHIQUES,
                                         blancs, decimal_fr)
from test_parc_cout_arret import CHAMP, LIBELLE_FICHE, LIGNE_FICHE
from test_rapport import lire_csv

# ---------------------------------------------------------------------------
# Ce que la recette attend
# ---------------------------------------------------------------------------

HORLOGE, JOUR = "2026-12-07T09:00:00", "2026-12-07"                 # serveur : un lundi après le jeu d'essai
MOIS, LIBELLE_MOIS, LIBELLE_PRECEDENT = "2026-11", "novembre 2026", "octobre 2026"
HORLOGE_DEMO, JOUR_DEMO = "2026-10-19T09:00:00", "2026-10-19"       # date de référence de la démo : dates non décalées
MOIS_DEMO, LIBELLE_DEMO, PRECEDENT_DEMO = "2026-09", "septembre 2026", "août 2026"

TYPES_PANNE = ("correctif immédiat", "correctif différé")
STATUTS_CLOS = ("Clôturé techniquement", "Clôturé administrativement")
DIX_MILLIEME, CENTIME = Decimal("0.0001"), Decimal("0.01")
CLOS_ADM, CLOS_TECH = "Clôturé administrativement", "Clôturé techniquement"

# Jeu d'essai de novembre 2026 : (OT, équipement du jeu, type, statut, création, arrêt de production, durée d'arrêt).
OT_DU_JEU = [
    ("OT-2026-0901", "A", "correctif immédiat", CLOS_ADM, "2026-11-03 08:00", "1", "1.15"),
    ("OT-2026-0902", "A", "correctif différé", CLOS_TECH, "2026-11-12 14:00", "1", "0.2"),
    ("OT-2026-0903", "B", "correctif immédiat", CLOS_ADM, "2026-11-05 09:30", "1", "0.3333"),
    ("OT-2026-0904", "A", "correctif immédiat", "En cours", "2026-11-24 10:00", "1", ""),      # sans durée : listé
    ("OT-2026-0905", "C", "correctif différé", CLOS_ADM, "2026-11-09 07:45", "1", "4"),         # non chiffré : listé
    ("OT-2026-0906", "A", "correctif immédiat", "Annulé", "2026-11-16 08:00", "1", "10"),       # ignorés
    ("OT-2026-0907", "B", "préventif systématique", CLOS_ADM, "2026-11-18 06:00", "1", "5"),
    ("OT-2026-0908", "B", "correctif différé", CLOS_ADM, "2026-11-19 13:00", "0", "7"),
]
SANS_DUREE = "OT-2026-0904"
# Saisie au formulaire, valeur écrite dans equipements.csv, ligne de la fiche du responsable.
SAISIES = {"A": ("1 250,50", "1250.50", "1 250,50 €/h"), "B": ("87,35", "87.35", "87,35 €/h"),
           "C": ("412,30", "412.30", "412,30 €/h")}
SAISIE_DEMO = ("1 250,50", "1250.50", "1 250,50 €/h")
# Ce que le technicien ne voit jamais, sous aucune forme (D126 prolongé, T473) : coûts saisis, montants du parcours.
MONTANTS = ("€/h", "1 250,50", "1250,50", "1250.5", "87,35", "87.35", "412,30", "412.30", "1 688,18", "29,11",
            "1 717,29", "1 649,20", "3 366,49")

MONTANT = re.compile(r"\d{1,3}(?: \d{3})*,\d\d €")
ALLER_JS = "(route) => { if (location.hash === route) return App.reafficher(); location.hash = route; return null; }"
LIGNES_JS = "(table) => Donnees.lignes(table).map((ligne) => Object.assign({}, ligne))"
LIRE_DOCUMENT_JS = """async (nom) => { const blob = await App.adaptateur.lireDocument(nom);
  return blob ? await blob.text() : null; }"""
# Indicateurs.coutArret du mois, Rapport.donnees(mois).coutArret (sans la tendance) et la 4ᵉ tuile.
LIRE_REGLE_JS = """(mois) => { const calcul = Indicateurs.coutArret(Indicateurs.periodeDuMois(mois));
  const rapport = Rapport.donnees(mois); const tuile = rapport.tuiles.find((t) => t.cle === 'coutArret');
  const donnees = Object.assign({}, rapport.coutArret); delete donnees.tendance;
  return { calcul, donnees, tuile: { valeur: tuile.valeur, texteValeur: tuile.texteValeur, precision: tuile.precision } }; }"""


# ---------------------------------------------------------------------------
# Données : lecture, jeu d'essai, calcul de référence
# ---------------------------------------------------------------------------

def brut(valeur):
    """Valeur d'une cellule (CSV ou mémoire), sans l'apostrophe de protection contre Excel."""
    valeur = "" if valeur is None else str(valeur).strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def propres(lignes):
    return [{cle: brut(valeur) for cle, valeur in ligne.items() if cle is not None} for ligne in lignes]


def lire_tables(dossier, noms=("equipements", "ordres_travail", "demandes")):
    return {nom: propres(lire_csv(dossier, nom + ".csv")) for nom in noms}


def cellule(texte):
    """Comme celluleCsv de js/donnees.js (§3.1)."""
    return '"' + texte.replace('"', '""') + '"' if re.search(r'[;"\r\n]|\A[ \t]|[ \t]\Z', texte) else texte


def lire_tableau(octets):
    """(en-tête, lignes) d'un CSV de Prévo (BOM, « ; »), valeurs telles qu'écrites."""
    lignes = [l for l in csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";") if l]
    return lignes[0], lignes[1:]


def ecrire_tableau(entete, lignes):
    return BOM + "".join(";".join(cellule(v) for v in ligne) + "\r\n" for ligne in [entete] + list(lignes)).encode("utf-8")


def preparer_source(racine):
    """Copie de donnees/demo complétée des OT de novembre 2026 (OT_DU_JEU) → (dossier, jeu) ; jeu : {A, B, C} =
    {id, repere} de trois équipements suivis, sans coût horaire, sans parent ni habilitation exigée (premiers par id)."""
    source = Path(racine) / "source"
    shutil.copytree(DOSSIER_DEMO, source)
    tables = lire_tables(source, ("equipements", "ordres_travail", "techniciens"))
    candidats = sorted((e for e in tables["equipements"] if e["actif"] != "0" and e["statut"] != "rebut" and e["repere"]
                        and not e["cout_arret_h"] and not e["parent_id"] and not e["habilitation_requise"]),
                       key=lambda e: e["id"])
    if len(candidats) < 3:
        raise AssertionError("la démo n'a plus trois équipements sans coût horaire")
    jeu = {cle: {"id": e["id"], "repere": e["repere"]} for cle, e in zip("ABC", candidats)}
    technicien = next(t["id"] for t in tables["techniciens"] if t.get("actif") != "0")
    existants = {ot["id"] for ot in tables["ordres_travail"]}
    if any(ot["date_creation"][:7] >= MOIS for ot in tables["ordres_travail"]):
        raise AssertionError("la démo a déjà des OT en novembre 2026 : le jeu d'essai ne serait plus seul")
    chemin = source / "ordres_travail.csv"
    octets = chemin.read_bytes()
    if not (octets.startswith(BOM) and octets.endswith(b"\r\n")):
        raise AssertionError("ordres_travail.csv de la démo : BOM ou fin de ligne inattendus")
    entete = octets[len(BOM):].split(b"\r\n", 1)[0].decode("utf-8").split(";")
    lignes = []
    for ot_id, cle, type_ot, statut, creation, arret, duree in OT_DU_JEU:
        if ot_id in existants:
            raise AssertionError(ot_id + " existe déjà dans la démo")
        valeurs = {"id": ot_id, "origine": "manuel", "equipement_id": jeu[cle]["id"], "type": type_ot, "priorite": "P2",
                   "statut": statut, "titre": "%s — arrêt du jeu d'essai (recette T476)" % jeu[cle]["repere"],
                   "date_creation": creation, "technicien_id": technicien, "arret_production": arret,
                   "duree_arret_h": duree, "anomalie_constatee": "0"}
        if statut != "Annulé":
            valeurs["date_debut"] = creation
        if statut in STATUTS_CLOS:
            valeurs.update(date_fin=creation[:11] + "16:00", date_cloture_tech=creation[:11] + "16:30", remise_service="1",
                           compte_rendu="Remis en service (recette T476).")
        if statut == CLOS_ADM:
            valeurs["date_cloture_admin"] = creation[:11] + "17:00"
        if statut == "Annulé":
            valeurs["motif_annulation"] = "Doublon (recette T476)."
        lignes.append(";".join(cellule(valeurs.get(nom, "")) for nom in entete))
    chemin.write_bytes(octets + ("\r\n".join(lignes) + "\r\n").encode("utf-8"))
    return source, jeu


def decimal_lu(valeur, pas):
    """Décimal positif ou nul d'une cellule (« 1 250,50 », « 1250.50 »), arrondi au pas (moitié vers le haut) ; None
    si vide, illisible ou négatif."""
    texte = re.sub(r"[\s  ]", "", brut(valeur)).replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d*)?", texte):
        return None
    return Decimal(texte).quantize(pas, ROUND_HALF_UP)


def dernier_jour(mois):
    return "%s-%02d" % (mois, calendar.monthrange(int(mois[:4]), int(mois[5:7]))[1])


def cout_de_reference(tables, mois, couts=None):
    """Coût de l'arrêt du mois calculé à part (conception L4-L5-L6 §3.1), sans le code de Prévo : pannes = OT
    correctif immédiat ou différé, avec arrêt de production, non annulé, daté par sa DI d'origine (celle qu'il désigne,
    sinon la plus ancienne DI acceptée qui le désigne), sinon par sa création. Par équipement : Σ durées (au
    dix-millième d'heure) × coût horaire actuel (au centime), arrondi au centime ROUND_HALF_UP ; sans coût horaire
    lisible : non chiffré (avec ses heures) ; panne sans durée lisible : listée. `couts` : {équipement : coût} saisis.
    → { lignes: [(équipement, heures, coût horaire, centimes)], non_chiffres: [(équipement, heures)],
        sans_duree: [(OT, équipement, raison)], total (centimes), complet }."""
    debut, fin = mois + "-01", dernier_jour(mois)
    equipements = {e["id"]: dict(e) for e in tables["equipements"]}
    for identifiant, cout in (couts or {}).items():
        equipements[identifiant]["cout_arret_h"] = cout
    demandes = {di["id"]: di for di in tables["demandes"]}
    acceptees = {}
    for di in sorted(tables["demandes"], key=lambda d: d["date_heure"]):
        if di["ot_id"] and di["statut"] == "Acceptée":
            acceptees.setdefault(di["ot_id"], di)
    pannes = []
    for ot in tables["ordres_travail"]:
        if ot["type"] not in TYPES_PANNE or ot["arret_production"] != "1" or ot["statut"] == "Annulé":
            continue
        di = demandes.get(ot["di_id"]) or acceptees.get(ot["id"])
        date = (di["date_heure"] if di and di["date_heure"] else "") or ot["date_creation"]
        if debut <= date[:10] <= fin:
            pannes.append((date, ot["id"], ot))
    heures, avec_duree, sans_duree = {}, set(), []
    for _, _, ot in sorted(pannes, key=lambda panne: panne[:2]):
        equipement = ot["equipement_id"]
        heures.setdefault(equipement, Decimal(0))
        duree = decimal_lu(ot["duree_arret_h"], DIX_MILLIEME)
        if duree is None:
            sans_duree.append((ot["id"], equipement, "sans durée d'arrêt" if ot["statut"] in STATUTS_CLOS else "non clôturé"))
        else:
            heures[equipement] += duree
            avec_duree.add(equipement)
    lignes, non_chiffres = [], []
    for equipement, total_heures in heures.items():
        cout = decimal_lu(equipements[equipement]["cout_arret_h"], CENTIME) if equipement in equipements else None
        if cout is None:
            non_chiffres.append((equipement, total_heures))
        elif equipement in avec_duree:
            lignes.append((equipement, total_heures, cout,
                           int((total_heures * cout * 100).quantize(Decimal(1), ROUND_HALF_UP))))
    lignes.sort(key=lambda l: (-l[3], -l[1], l[0]))
    non_chiffres.sort(key=lambda l: (-l[1], l[0]))
    return {"lignes": lignes, "non_chiffres": non_chiffres, "sans_duree": sans_duree,
            "total": sum(l[3] for l in lignes), "complet": not non_chiffres and not sans_duree}


def forme(calcul):
    """Résultat d'Indicateurs.coutArret (page) sous la forme de cout_de_reference."""
    def heures(valeur):
        return Decimal(repr(valeur)).quantize(DIX_MILLIEME)
    return {"lignes": [(l["equipementId"], heures(l["heures"]), Decimal(l["coutHoraireCentimes"]) / 100, l["centimes"])
                       for l in calcul["parEquipement"]],
            "non_chiffres": [(l["equipementId"], heures(l["heures"])) for l in calcul["nonChiffres"]],
            "sans_duree": [(l["otId"], l["equipementId"], l["raison"]) for l in calcul["sansDuree"]],
            "total": calcul["totalCentimes"], "complet": calcul["complet"]}


def euro_fr(centimes):
    entier, reste = divmod(int(centimes), 100)
    return "{:,}".format(entier).replace(",", " ") + ",%02d €" % reste


def heures_fr(heures):
    texte = format(Decimal(heures).quantize(CENTIME, ROUND_HALF_UP), "f").rstrip("0").rstrip(".")
    return texte.replace(".", ",") + " h"


def manque_fr(reference):
    morceaux = []
    n = len(reference["non_chiffres"])
    if n:
        morceaux.append("1 équipement non chiffré" if n == 1 else "%d équipements non chiffrés" % n)
    if reference["sans_duree"]:
        morceaux.append("%d OT sans durée" % len(reference["sans_duree"]))
    return ", ".join(morceaux)


def non_calculable_fr(reference, reperes):
    """Entrée « Non calculable » du rapport (conception §3.2), pour 8 repères au plus (les jeux de la recette en ont
    moins) : (libellé, raison)."""
    assert len(reference["non_chiffres"]) + len(reference["sans_duree"]) <= 8
    equipements = [("%s (%s d'arrêt)" if rang == 0 else "%s (%s)") % (reperes[e], heures_fr(h))
                   for rang, (e, h) in enumerate(reference["non_chiffres"])]
    ots = ["%s (%s, %s)" % (ot, reperes[e], raison) for ot, e, raison in reference["sans_duree"]]
    raison = ("%s ; OT sans durée : %s" % (", ".join(equipements), ", ".join(ots)) if equipements and ots
              else ", ".join(equipements + ots))
    return ("Coût de l'arrêt — non chiffré" if equipements else "Coût de l'arrêt — OT sans durée"), raison


def present(repere, texte):
    """Le repère figure dans le texte comme un mot entier (« CV-02 » n'est pas trouvé dans « CV-02.M »)."""
    return re.search(r"(?<![\w.-])%s(?![\w.-])" % re.escape(repere), texte) is not None


# ---------------------------------------------------------------------------
# Le parcours, à l'écran
# ---------------------------------------------------------------------------

class CasRecette(CasNavigateur):
    """Le mode fournit lignes(table) (disque ou mémoire) et document(nom) (texte du rapport figé)."""

    def lignes(self, table):  # pragma: no cover - fourni par le mode
        raise NotImplementedError

    def document(self, nom):  # pragma: no cover - fourni par le mode
        raise NotImplementedError

    def js(self, script, argument=None, page=None):
        return (page or self.page).evaluate(script, argument)

    def aller(self, route, selecteur, page=None):
        page = page or self.page
        page.evaluate(ALLER_JS, route)
        page.wait_for_selector(selecteur)

    def attendre(self, condition, message="", delai_s=10):
        """Attend qu'une condition sur les données devienne vraie (le serveur écrit après la réponse de l'écran)."""
        fin = datetime.datetime.now() + datetime.timedelta(seconds=delai_s)
        while datetime.datetime.now() < fin:
            if condition():
                return
            self.page.wait_for_timeout(200)
        self.assertTrue(condition(), message)

    def noter_requetes(self, page):
        page.on("request", lambda requete_: self.requetes.append(requete_.url))

    def verifier_reseau(self, origine):
        """CS177 : aucune requête hors de l'application ; seule la lecture de version de T305 (existante) sort."""
        locales = (origine, "file:", "blob:", "data:", "about:")
        externes = [u for u in self.requetes if not u.startswith(locales) and u != ADRESSE_VERSION_JSON]
        self.assertGreater(len(self.requetes), 10)
        self.assertEqual(externes, [], "requêtes vers une autre adresse que l'application")

    def cout_lu(self, equipement):
        return next(e for e in self.lignes("equipements") if e["id"] == equipement)["cout_arret_h"]

    def rapports_figes(self):
        valeur = next((p["valeur"] for p in self.lignes("parametres") if p["cle"] == "rapports_mensuels"), "")
        return [nom.strip() for nom in valeur.split(",") if nom.strip()]

    # -- fiche et formulaire de l'équipement --------------------------------------------------------

    def fiche(self, equipement, page=None):
        """Ouvre la fiche de CET équipement (l'identifiant est la première valeur de la fiche technique)."""
        page = page or self.page
        page.evaluate("(r) => { location.hash = r; }", "#/equipement/" + equipement)
        page.wait_for_function("""(id) => { const dd = document.querySelector('#contenu .parc .valeurs dd');
            return location.hash === '#/equipement/' + id && dd !== null && dd.textContent.trim() === id; }""",
                               arg=equipement)

    def texte_fiche(self):
        return blancs(self.page.inner_text(LIGNE_FICHE)).strip()

    def enregistrer_cout(self, equipement, saisie, ecrit, affiche):
        """Formulaire ouvert : aucune valeur proposée (D188) ; saisie, enregistrement, valeur écrite, fiche."""
        page = self.page
        self.assertEqual(page.input_value(CHAMP + " input"), "", "aucun coût horaire par défaut")
        page.fill(CHAMP + " input", saisie)
        page.click("#parc-formulaire button[type=submit]")
        page.wait_for_function("""(id) => { const dd = document.querySelector('#contenu .parc .valeurs dd');
            return location.hash === '#/equipement/' + id && dd !== null && dd.textContent.trim() === id; }""",
                               arg=equipement)
        self.attendre(lambda: self.cout_lu(equipement) == ecrit, "coût horaire de %s non écrit" % equipement)
        self.assertEqual(self.texte_fiche(), affiche)

    def saisir_cout(self, equipement, saisie, ecrit, affiche):
        self.aller("#/equipement/%s/modifier" % equipement, CHAMP + " input")
        self.enregistrer_cout(equipement, saisie, ecrit, affiche)

    def saisir_depuis_la_carte(self, equipement, saisie, ecrit, affiche):
        """« Saisir le coût horaire » de la carte « Non chiffré » (écran Indicateurs affiché) : la modification de la
        fiche, puis l'enregistrement."""
        lien = '#contenu .indicateurs-non-chiffre tr[data-equipement="%s"] a.indicateurs-saisir-cout' % equipement
        self.page.click(lien)
        self.page.wait_for_function("(h) => location.hash === h", arg="#/equipement/%s/modifier" % equipement)
        self.page.wait_for_selector(CHAMP + " input")
        self.enregistrer_cout(equipement, saisie, ecrit, affiche)

    # -- la règle, le rapport, l'écran Indicateurs --------------------------------------------------

    def verifier_regle(self, mois, reference):
        """Indicateurs.coutArret du mois = le calcul Python ; Rapport.donnees et sa 4ᵉ tuile le reprennent au centime."""
        lu = self.js(LIRE_REGLE_JS, mois)
        self.assertEqual(forme(lu["calcul"]), reference)
        self.assertEqual(lu["donnees"], lu["calcul"])
        self.assertEqual(lu["calcul"]["total"], reference["total"] / 100)
        self.assertEqual(blancs(lu["tuile"]["texteValeur"]), euro_fr(reference["total"]))
        self.assertEqual(lu["tuile"]["precision"], "Partiel : " + manque_fr(reference))

    def figer_le_mois(self, mois, libelle):
        """« Figer » sur la tuile de l'accueil du responsable → (nom enregistré, texte du document)."""
        page = self.page
        self.aller("#/accueil", "#bandeau-rapport")
        self.assertIn(libelle, page.inner_text("#bandeau-rapport"))
        self.assertEqual(self.rapports_figes(), [])
        page.click('#bandeau-rapport [data-action="figer-rapport"]')
        self.attendre(lambda: len(self.rapports_figes()) == 1, "rapport non figé")
        nom = self.rapports_figes()[0]
        self.assertRegex(nom, r"(^|-)rapport-mensuel-%s\.html$" % mois)
        page.wait_for_function("!document.querySelector('#bandeau-rapport')")
        return nom, self.document(nom)

    def verifier_rapport(self, document, reference, precedent):
        """Le rapport figé : tuile au centime et ce qui lui manque, Pareto par coût, Comprendre, Non calculable,
        courriel ; rien d'estimé (aucun autre montant que ceux du calcul)."""
        texte = blancs(document)
        total, manque = euro_fr(reference["total"]), manque_fr(reference)
        self.assertEqual(re.findall(r'<div class="tuile" data-cle="([^"]+)">', texte),
                         ["disponibilite", "cout", "partPreventif", "coutArret"])
        tuile = re.search(r'<div class="tuile" data-cle="coutArret">(.*?)</section>', texte, re.S).group(1)
        self.assertIn('<div class="lib">Coût de l\'arrêt</div><div class="val">%s</div>' % total, tuile)
        self.assertIn('<div class="raison">Partiel : %s</div>' % manque, tuile)
        self.assertIn("○ non comparable avec %s : coût incomplet" % precedent, tuile)
        self.assertEqual(MONTANT.findall(tuile), [total])
        figures = dict(re.findall(r"<figcaption>(.*?)</figcaption>(.*?)</figure>", texte, re.S))
        cout, heures = figures["Coût de l'arrêt du mois par équipement (€)"], figures["Durée d'arrêt du mois par équipement (heures)"]
        premiers = [l for l in reference["lignes"] if l[3] > 0][:5]
        self.assertEqual(sorted(MONTANT.findall(cout)), sorted(euro_fr(l[3]) for l in premiers))
        for equipement, *_ in premiers:
            self.assertTrue(present(self.reperes[equipement], cout), equipement)
        # Un non chiffré n'est jamais dans le Pareto par coût ; ses heures connues restent dans celui des heures (en
        # démo, CV-02 n'a qu'une panne sans durée : non chiffré à 0 h, et son OT listé sans durée).
        for equipement, nombre in reference["non_chiffres"]:
            with self.subTest(non_chiffre=equipement):
                self.assertFalse(present(self.reperes[equipement], cout), "non chiffré dans le Pareto par coût")
                if nombre > 0:
                    self.assertTrue(present(self.reperes[equipement], heures), "absent du Pareto des heures")
        self.assertIn("<dt>Coût de l'arrêt :</dt>", texte)
        definition = texte.split("<dt>Coût de l'arrêt :</dt>")[1].split("</dd>")[0]
        self.assertIn("durée d'arrêt × coût d'une heure d'arrêt", definition)
        self.assertIn("Rien n'est estimé", definition)
        self.assertIn("<li><b>%s</b> : %s</li>" % non_calculable_fr(reference, self.reperes), texte)
        lien = re.search(r'href="(mailto:[^"]*)"', document).group(1)
        corps = blancs(urllib.parse.unquote(lien.replace("&amp;", "&")))
        self.assertIn("• Coût de l'arrêt : %s — Partiel : %s (non comparable avec %s : coût incomplet)"
                      % (total, manque, precedent), corps)
        for interdit in ("NaN", "Infinity", "undefined"):
            self.assertNotIn(interdit, texte)

    def verifier_une_page(self, document):
        """Le document figé, ouvert seul en file:// et imprimé : une page A4."""
        dossier = Path(tempfile.mkdtemp(prefix="recette-cout-arret-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        fichier = dossier / "rapport-mensuel.html"
        fichier.write_text(document, encoding="utf-8")
        page = self.page.context.new_page()
        self.surveiller(page)
        self.noter_requetes(page)
        page.goto(fichier.resolve().as_uri())
        pdf = page.pdf(prefer_css_page_size=True)
        page.close()
        self.assertEqual(len(re.findall(rb"/Type\s*/Page[^s]", pdf)), 1, "le rapport doit tenir sur une page A4")

    def aller_indicateurs(self, mois):
        debut, fin = mois + "-01", dernier_jour(mois)
        self.page.evaluate("""(h) => { document.querySelectorAll('#contenu .indicateurs-resultats')
            .forEach((z) => { z.dataset.ancienne = '1'; }); App.naviguer(h); }""",
                           "#/indicateurs?periode=du-au&du=%s&au=%s" % (debut, fin))
        self.page.wait_for_function(ATTENDRE_GRAPHIQUES_JS, arg=NOMBRE_GRAPHIQUES, timeout=20000)
        self.page.wait_for_function("(d) => document.querySelector('#contenu .indicateurs-resultats').dataset.du === d",
                                    arg=debut)

    def verifier_indicateurs(self, reference):
        """Écran Indicateurs (période du mois) : Pareto du coût au centime, notes, carte « Non chiffré »."""
        pareto = self.js(LIRE_PARETO_JS)
        self.assertEqual(pareto["etat"], "pret")
        attendus = [l for l in reference["lignes"] if l[3] > 0][:10]
        self.assertEqual([l[0] for l in pareto["lignes"]], [self.reperes[l[0]] for l in attendus])
        self.assertEqual(sorted(pareto["categories"]), sorted(self.reperes[l[0]] for l in attendus))
        cumul = 0
        for lu, (equipement, heures, cout, centimes) in zip(pareto["lignes"], attendus):
            with self.subTest(pareto=equipement):
                cumul += centimes
                self.assertEqual(decimal_fr(lu[1]), heures.quantize(CENTIME, ROUND_HALF_UP), lu)
                self.assertEqual(decimal_fr(lu[2]), cout, lu)
                self.assertEqual(decimal_fr(lu[3]), Decimal(centimes) / 100, lu)            # au centime
                self.assertLessEqual(abs(decimal_fr(lu[4]) - Decimal(cumul * 100) / reference["total"]), Decimal("0.05"), lu)
        notes = [blancs(note) for note in pareto["notes"]]
        self.assertEqual(notes, ["Coût de l'arrêt de la période : %s." % euro_fr(reference["total"]),
                                 "Partiel : %s (liste : carte « Non chiffré »)." % manque_fr(reference)])
        carte = self.js(LIRE_CARTE_JS)
        self.assertEqual((carte["titre"], carte["complet"]), ("Non chiffré", "0"))
        self.assertEqual([(l["id"], l["cellules"][0], decimal_fr(blancs(l["cellules"][1]))) for l in carte["equipements"]],
                         [(e, self.reperes[e], h.quantize(CENTIME, ROUND_HALF_UP)) for e, h in reference["non_chiffres"]])
        for ligne in carte["equipements"]:
            self.assertEqual(ligne["saisir"], "Saisir le coût horaire")
            self.assertIn("#/equipement/%s/modifier" % ligne["id"], ligne["liens"])
        self.assertEqual([(l["id"], l["cellules"][1], l["raison"], l["liens"][0]) for l in carte["ots"]],
                         [(ot, self.reperes[e], raison, "#/ot/" + ot) for ot, e, raison in reference["sans_duree"]])
        self.assertNotRegex(self.page.inner_text("#contenu"), r"NaN|Infinity|undefined")

    # -- profil Technicien ----------------------------------------------------------------------------

    def vue_du_technicien(self, page, equipements, interdits):
        """Ni menu, ni adresse, ni tuile du rapport ; fiches sans la ligne du coût ; aucun montant dans la page."""
        self.assertEqual((page.evaluate("App.profil.type"), page.evaluate("App.estResponsable()")), ("technicien", False))
        self.assertEqual(page.locator("#menu a[data-ecran='indicateurs']").count(), 0)
        self.assertEqual(page.locator("#bandeau-rapport").count(), 0)
        for route in ("#/indicateurs", "#/indicateurs?periode=du-au&du=%s-01&au=%s" % (MOIS, dernier_jour(MOIS))):
            with self.subTest(route=route):
                page.evaluate("() => { location.hash = '#/parc'; }")
                page.wait_for_function("location.hash === '#/parc'")
                page.evaluate("(r) => { location.hash = r; }", route)
                page.wait_for_function("location.hash === '#/accueil'")
                self.assertEqual(page.locator(".indicateurs-resultats, .indicateurs-non-chiffre, .rapports").count(), 0)
        for equipement in equipements:
            with self.subTest(fiche=equipement):
                self.fiche(equipement, page)
                self.assertEqual(page.locator(LIGNE_FICHE).count(), 0)
                contenu = blancs(page.inner_text("#contenu"))
                self.assertNotIn(LIBELLE_FICHE, contenu)
                self.assertNotIn("non chiffré", contenu)
                self.assertNotIn("/h", blancs(page.inner_text("#contenu .valeurs")))
        tout = blancs(page.evaluate("() => document.body.innerText + ' ' + document.body.innerHTML"))
        for montant in interdits:
            self.assertNotIn(montant, tout)


# ---------------------------------------------------------------------------
# Mode serveur : sans comptes, puis avec comptes
# ---------------------------------------------------------------------------

class CasParcoursServeur(CasRecette):
    """serveur.py sur la copie préparée du jeu de démo ; données et documents relus sur le disque."""

    COMPTES = False

    def lignes(self, table):
        if not (self.dossier / (table + ".csv")).exists():
            return []
        return propres(lire_csv(self.dossier, table + ".csv"))

    def document(self, nom):
        return (self.dossier / "documents" / nom).read_text(encoding="utf-8")

    def lancer(self):
        self.requetes = []
        racine = Path(tempfile.mkdtemp(prefix="prevo-recette-cout-arret-"))
        self.addCleanup(shutil.rmtree, racine, True)
        source, self.jeu = preparer_source(racine)
        with ServeurPrevo(source=source, comptes=self.COMPTES) as serveur:
            self.serveur, self.dossier = serveur, Path(serveur.dossier)
            if self.COMPTES:
                serveur.poser_session(self.contexte, "responsable")
            else:
                preregler_profil(self.contexte, "responsable", "Nicolas Briand")
            self.contexte.clock.set_fixed_time(HORLOGE)
            self.noter_requetes(self.page)
            self.page.set_viewport_size({"width": 1440, "height": 1200})
            self.page.goto(serveur.url + "/#/accueil")
            attendre_pret(self.page)
            self.page.wait_for_load_state("networkidle")       # écritures du démarrage (OT préventifs échus) finies
            self.assertEqual((self.js("App.profil.type"), self.js("Donnees.aujourdhui()")), ("responsable", JOUR))
            self.parcours()
            self.page.close()
            self.technicien(serveur)
            self.verifier_reseau(serveur.url + "/")

    def parcours(self):
        a, b, c = (self.jeu[cle]["id"] for cle in "ABC")
        self.reperes = {e["id"]: e["repere"] for e in self.lignes("equipements")}
        self.assertEqual(self.page.locator("#menu a[data-ecran='indicateurs']").count(), 1)

        # Fiches : C sans coût horaire (« non chiffré ») ; coûts de A et de B saisis par le formulaire.
        self.fiche(c)
        self.assertEqual(self.texte_fiche(), "non chiffré")
        self.saisir_cout(a, *SAISIES["A"])
        self.saisir_cout(b, *SAISIES["B"])
        self.assertEqual(self.cout_lu(c), "")

        # Le calcul Python sur les fichiers du disque : le jeu d'essai, au centime ; le piège des flottants évité.
        reference = cout_de_reference(lire_tables(self.dossier), MOIS)
        self.assertEqual(reference, {
            "lignes": [(a, Decimal("1.35"), Decimal("1250.50"), 168818), (b, Decimal("0.3333"), Decimal("87.35"), 2911)],
            "non_chiffres": [(c, Decimal(4))], "sans_duree": [(SANS_DUREE, a, "non clôturé")],
            "total": 171729, "complet": False})
        self.assertEqual(math.floor((1.15 + 0.2) * 1250.5 * 100 + 0.5), 168817)    # en flottants : 1 688,17 €
        self.verifier_regle(MOIS, reference)

        # Le rapport figé depuis l'accueil, relu sur le disque ; une page A4.
        nom, document = self.figer_le_mois(MOIS, LIBELLE_MOIS)
        self.assertIn('<div class="val">1 717,29 €</div>', blancs(document))
        self.verifier_rapport(document, reference, LIBELLE_PRECEDENT)
        self.verifier_une_page(document)

        # L'écran Indicateurs du mois ; puis le coût de C saisi depuis la carte « Non chiffré ».
        self.aller_indicateurs(MOIS)
        self.verifier_indicateurs(reference)
        self.saisir_depuis_la_carte(c, *SAISIES["C"])
        apres = cout_de_reference(lire_tables(self.dossier), MOIS)
        self.assertEqual((apres["total"], [l[0] for l in apres["lignes"]], apres["non_chiffres"], apres["sans_duree"]),
                         (336649, [a, c, b], [], reference["sans_duree"]))
        self.verifier_regle(MOIS, apres)
        self.aller_indicateurs(MOIS)
        self.verifier_indicateurs(apres)
        self.assertEqual(self.document(nom), document)                        # le rapport figé garde ses chiffres
        self.nom_du_rapport = nom

    def page_technicien(self, serveur, technicien):
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1440, "height": 1200})
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        contexte.clock.set_fixed_time(HORLOGE)
        if self.COMPTES:
            serveur.poser_session(contexte, "technicien")
        else:
            preregler_profil(contexte, "technicien", technicien_id=technicien)
        page = contexte.new_page()
        self.surveiller(page)
        self.noter_requetes(page)
        page.goto(serveur.url + "/#/accueil")
        attendre_pret(page)
        page.wait_for_load_state("networkidle")
        self.page = page                                        # attendre() lit self.page
        return page

    def technicien(self, serveur):
        """Sans comptes : un technicien de la démo (son profil sur ce poste)."""
        technicien = next(t["id"] for t in self.lignes("techniciens") if t.get("actif") != "0")
        page = self.page_technicien(serveur, technicien)
        self.vue_du_technicien(page, [self.jeu[cle]["id"] for cle in "ABC"], MONTANTS)


class TestParcoursServeur(CasParcoursServeur):

    def test_cout_de_l_arret_serveur_sans_comptes(self):
        self.lancer()


class TestParcoursServeurComptes(CasParcoursServeur):

    COMPTES = True

    def test_cout_de_l_arret_avec_comptes_puis_rien_pour_le_technicien(self):
        self.lancer()

    def technicien(self, serveur):
        """Le compte technicien : la vue, puis ce qu'il reçoit (T473) ; le demandeur, et le rapport figé (403)."""
        page = self.page_technicien(serveur, COMPTES_DE_TEST["technicien"][4])
        equipements = [self.jeu[cle]["id"] for cle in "ABC"]
        self.vue_du_technicien(page, equipements, MONTANTS)

        # Dans la page : la colonne, vide sur chaque ligne ; les coûts sont pourtant sur le disque.
        self.assertEqual({e: self.cout_lu(e) for e in equipements}, {self.jeu[cle]["id"]: SAISIES[cle][1] for cle in "ABC"})
        recus = propres(page.evaluate(LIGNES_JS, "equipements"))
        self.assertGreater(len(recus), 3)
        self.assertTrue(all("cout_arret_h" in e for e in recus))
        self.assertEqual({e["cout_arret_h"] for e in recus}, {""})
        self.assertNotRegex(page.evaluate("JSON.stringify(Donnees.lignes('equipements'))"), r"1250\.5|87\.35|412\.3")

        # Réponse du serveur au technicien et au demandeur : en-tête du format 4 gardé, valeurs vidées.
        for role in ("technicien", "demandeur"):
            with self.subTest(role=role):
                reponse = requete(serveur, "GET", "/api/csv/equipements", cookie=serveur.session(role))
                self.assertEqual(reponse.statut, 200, reponse.octets[:300])
                entete, lignes = lire_tableau(reponse.octets)
                position = entete.index("cout_arret_h")
                self.assertEqual({ligne[position] for ligne in lignes}, {""})
                for cout in (b"1250.50", b"87.35", b"412.30", b"655.25"):
                    self.assertNotIn(cout, reponse.octets)
        refus = requete(serveur, "GET", "/api/documents/" + self.nom_du_rapport, cookie=serveur.session("demandeur"))
        self.assertEqual(refus.statut, 403, refus.octets[:300])
        self.assertEqual(refus.json()["erreur"], REFUS_DOCUMENT.format(role="demandeur"))


# ---------------------------------------------------------------------------
# Mode démo
# ---------------------------------------------------------------------------

class TestParcoursDemo(CasRecette):
    """index.html en file:// (démo, données en mémoire) ; le technicien : changement de profil dans la même page."""

    def lignes(self, table):
        return propres(self.js(LIGNES_JS, table))

    def document(self, nom):
        return self.js(LIRE_DOCUMENT_JS, nom)

    def test_cout_de_l_arret_en_demo(self):
        self.requetes = []
        preregler_profil(self.contexte, "responsable", "Nicolas Briand")
        self.contexte.clock.set_fixed_time(HORLOGE_DEMO)
        self.noter_requetes(self.page)
        self.page.set_viewport_size({"width": 1440, "height": 1200})
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.assertEqual((self.js("App.mode"), self.js("App.profil.type"), self.js("Donnees.aujourdhui()")),
                         ("demo", "responsable", JOUR_DEMO))

        # Le calcul Python fait sur donnees/demo (le disque, pas la page) : septembre 2026, dernier mois de l'historique.
        tables = lire_tables(DOSSIER_DEMO)
        self.reperes = {e["id"]: e["repere"] for e in tables["equipements"]}
        role = scenarios_demo()["equipement_non_chiffre"]
        reference = cout_de_reference(tables, MOIS_DEMO)
        self.assertTrue(reference["lignes"], "la démo chiffre des équipements (T475)")
        self.assertGreater(dict(reference["non_chiffres"]).get(role, 0), 0, "rôle equipement_non_chiffre (T475)")
        self.assertNotIn(role, [l[0] for l in reference["lignes"]])
        self.assertFalse(reference["complet"])
        self.verifier_regle(MOIS_DEMO, reference)

        # Le rapport figé depuis l'accueil (en mémoire) ; une page A4 ; l'écran Indicateurs du mois.
        nom, document = self.figer_le_mois(MOIS_DEMO, LIBELLE_DEMO)
        self.verifier_rapport(document, reference, PRECEDENT_DEMO)
        self.verifier_une_page(document)
        self.aller_indicateurs(MOIS_DEMO)
        self.verifier_indicateurs(reference)

        # Le coût horaire de l'équipement du rôle, saisi depuis la carte : il est chiffré, jamais estimé avant.
        self.saisir_depuis_la_carte(role, *SAISIE_DEMO)
        apres = cout_de_reference(tables, MOIS_DEMO, {role: SAISIE_DEMO[1]})
        self.assertIn(role, [l[0] for l in apres["lignes"]])
        self.assertNotIn(role, dict(apres["non_chiffres"]))
        self.verifier_regle(MOIS_DEMO, apres)
        self.aller_indicateurs(MOIS_DEMO)
        self.verifier_indicateurs(apres)
        self.assertEqual(self.document(nom), document)                        # le rapport figé garde ses chiffres

        # Profil Technicien, sans recharger : la démo serait perdue.
        page = self.page
        technicien = next(t["id"] for t in self.lignes("techniciens") if t.get("actif") != "0")
        page.evaluate("window.__memePage = true")
        page.click("#etat-poste")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-technicien")
        page.click("#profil-techniciens [data-technicien='%s']" % technicien)
        attendre_pret(page)
        self.assertTrue(page.evaluate("window.__memePage === true"), "la page a été rechargée")
        montants = ["€/h", SAISIE_DEMO[0]] + [euro_fr(x) for x in (reference["total"], apres["total"])]
        montants += [euro_fr(l[3]) for l in apres["lignes"]]
        self.vue_du_technicien(page, [role] + [l[0] for l in apres["lignes"]], montants)
        self.verifier_reseau(url_fichier("index.html"))


# ---------------------------------------------------------------------------
# Écart trouvé : le rapport figé, servi au technicien (sans navigateur)
# ---------------------------------------------------------------------------

class TestRapportFigeAuTechnicien(unittest.TestCase):
    """Avec comptes, un rapport mensuel figé est un document comme un autre de donnees/documents : la règle des
    documents du technicien (DOCUMENTS_DU_TECHNICIEN de serveur.py : tous, sauf justificatifs d'habilitation et
    contrats signés) le lui sert, et il en reçoit le nom (parametres.rapports_mensuels, table qu'il lit). Le rapport
    porte le coût de l'arrêt par équipement à côté des heures d'arrêt (donc le coût horaire, que T473 lui cache) et le
    coût de maintenance (D126). Le demandeur, lui, est refusé. Le responsable fige ici comme Rapport.figer : le
    document (PUT /api/documents), puis son nom dans rapports_mensuels (PUT de parametres)."""

    CONTENU = ("<!doctype html><title>Rapport mensuel de maintenance — septembre 2026</title><p>Coût de l'arrêt : "
               "4 887,50 € ; CP-01 : 5,75 h d'arrêt, 4 887,50 € (recette T476)</p>").encode("utf-8")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo(comptes=True)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.cookies = {role: cls.serveur.session(role) for role in ("responsable", "technicien", "demandeur")}
        depot = requete(cls.serveur, "PUT", "/api/documents/rapport-mensuel-2026-09.html", cls.CONTENU,
                        cls.cookies["responsable"], {"Content-Type": "text/html;charset=utf-8"})
        if depot.statut not in (200, 201):
            raise AssertionError("dépôt du rapport refusé : %s %r" % (depot.statut, depot.octets[:300]))
        cls.nom = depot.json()["nom"]
        lue = requete(cls.serveur, "GET", "/api/csv/parametres", cookie=cls.cookies["responsable"])
        entete, lignes = lire_tableau(lue.octets)
        lignes = [ligne for ligne in lignes if ligne[0] != "rapports_mensuels"] + [["rapports_mensuels", cls.nom]]
        ecrit = requete(cls.serveur, "PUT", "/api/csv/parametres", ecrire_tableau(entete, lignes),
                        cls.cookies["responsable"], {"X-Version-Attendue": lue.entetes["x-version"]})
        if ecrit.statut != 200:
            raise AssertionError("rapports_mensuels non écrit : %s %r" % (ecrit.statut, ecrit.octets[:300]))

    def lire(self, role):
        return requete(self.serveur, "GET", "/api/documents/" + self.nom, cookie=self.cookies[role])

    @unittest.expectedFailure
    def test_le_technicien_ne_lit_pas_le_rapport_fige(self):
        """Attendu (D126 prolongé par T473 : aucun coût pour le technicien) : 403. Aujourd'hui : servi (200). Quand
        serveur.py réservera les rapports figés au responsable, retirer expectedFailure et retourner le test cerné."""
        reponse = self.lire("technicien")
        self.assertEqual(reponse.statut, 403, reponse.octets[:200])

    def test_ecart_cerne_rapport_servi_au_technicien_seul_hors_responsable(self):
        """L'écart exact, rien d'autre : le responsable lit le rapport, le demandeur est refusé (403) ; le technicien
        reçoit le nom du rapport (parametres) et le document entier (200), avec ses montants."""
        self.assertEqual((self.lire("responsable").statut, self.lire("responsable").octets), (200, self.CONTENU))
        refus = self.lire("demandeur")
        self.assertEqual(refus.statut, 403, refus.octets[:300])
        self.assertEqual(refus.json()["erreur"], REFUS_DOCUMENT.format(role="demandeur"))
        parametres = requete(self.serveur, "GET", "/api/csv/parametres", cookie=self.cookies["technicien"])
        self.assertEqual(parametres.statut, 200)
        self.assertIn(self.nom.encode("utf-8"), parametres.octets)
        servi = self.lire("technicien")
        self.assertEqual((servi.statut, servi.octets), (200, self.CONTENU))


if __name__ == "__main__":
    unittest.main()
