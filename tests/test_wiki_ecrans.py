"""Écrans de lecture du wiki de maintenance (tâche T100 ; lot 6 refondu, T110, T119 ; refonte 2, l'encyclopédie, T136 et
T137 — ARCHITECTURE.md §20.9, §20.12 ; CS98, CS103, CS106, CS114, CS115).

Toujours la démo (index.html en file://, « Essayer avec les données de démo »), horloge du navigateur fixée à la
date de référence de la démo (2026-10-19 : dates non décalées). Profils : responsable, technicien (TEC-0001), demandeur
(Lucie Martin). Une base d'essai (BASE_JS) pose sur la démo quatorze lignes de wiki_pages de la refonte 2 (texte de PO-02
— un OT cité deux fois dans une phrase — et de CP-01, texte d'un article, savoir-faire rattachés à une machine, à un
article, à la page d'une machine, libre, sous-page, archivé, titre piégé ; une ancienne page de mode, une ancienne
sous-page de machine et un ancien composant libre, types retirés), quatorze entrées de wiki_journal (contradictions
ouvertes sur PO-02 et sur un savoir-faire — antérieure —, une fermée ; à valider ; en file ; refusées ; à refaire ;
rejetée) et une intervention piégée (OT_PIEGE : tous ses textes, en attente, sans technicien sur l'OT, deux techniciens
y ont pointé du temps). Les valeurs attendues sont écrites à la main ou recalculées ici,
et les faits des pages comparés au calcul Python indépendant de tests/calcul_wiki.py (CalculWiki, sur les CSV de la
démo et la base). Ce qui est vérifié :
    accueil     #/wiki (T136) : « Ce que l'atelier sait », phrase-résumé dont chaque nombre mène à sa liste, « Tiré de
                N interventions clôturées », recherche ; briques (icône du type, nombre, ligne utile — Articles et
                Techniciens contre le calcul Python —, lien) ; dernières interventions, six pannes les plus fréquentes ;
                « Suivi du wiki » au responsable seulement ; titres piégés : du texte ;
    listes      les six listes pour les trois profils (« réservé » au demandeur pour les techniciens et les
                interventions), éléments et ordre des interventions contre le calcul Python, état du stock aussi ;
                interventions : 100 lignes sur PC, 40 cartes au téléphone, les autres créées au clic (D101) ; sur PC, le
                tri ordonne toute la liste avant d'en créer les 100 premières lignes ;
    recherche   de l'accueil : entités groupées par type (les 6 premières créées, les autres au clic), un seul titre
                quand rien n'est trouvé ;
    pages       #/wiki/<id> des six types (T137) pour les trois profils : fil d'Ariane, type, titre, consignation et
                « À trancher » en tête, sections dans leur ordre, textes rédigés et bandeau d'origine, fiche des faits
                (égale à Wiki.entite ET au calcul Python, un cas par type au moins, et toutes les machines, pannes et
                techniciens de la démo), à droite à 1440 px et au-dessus à 375 px ; petits numéros (ordre
                d'apparition, un seul pour un OT cité deux fois dans une phrase, bulle, nom accessible, lien ; pour le
                demandeur, un bouton sans lien dont la bulle s'ouvre au toucher, dans l'écran), « Références », jamais
                [OT-…] à l'écran, le balisage stocké intact ; petits numéros des articles consommés (page Machine) et
                changés (page Panne) — D118, T143 : les 10 OT les plus récents de chaque article, puis « … et n autres »,
                égaux au calcul Python indépendant (CalculWiki.ot_des_articles), quantité gardée —, un seul jeu de numéros
                par page dans l'ordre d'apparition, sans trou ni doublon, tous dans « Références » ; interventions dans
                l'ordre du calcul Python avec leur statut ; page Intervention en lecture seule (motifs d'attente et
                d'annulation, tous ses techniciens,
                textes piégés restés du texte), « Ouvrir la fiche OT » ; visibilité
                (D114 : prix, taux horaire, pages Technicien et Intervention) ; tout lien d'une page mène à une page
                qui s'affiche ; « Modifier » ; pièges ;
    trancher    « À trancher » : décisions du responsable (D107), boutons absents pour les autres ;
    consignation  à l'octet, document, absence ; lien depuis la fiche équipement ;
    sous-pages  d'un savoir-faire seulement (refonte 2) : mère, consignation reprise, liste, mère archivée ; les
                anciennes sous-pages et pages de mode ne s'affichent plus ;
    recherche   depuis la page d'une machine, l'onglet Préparation d'un OT et la saisie d'une DI ;
    affichage   1440 et 375 px sans défilement horizontal, zones tactiles ≥ 48 px au téléphone, contrastes AA en thème
                clair et sombre, focus visible ; aucune requête réseau pour afficher ; aucune requête /api/ en mode
                serveur (les six types) ; jeu de charge (500 machines, 5 000 OT, mode serveur) : accueil, chaque liste
                et la page la plus lourde de chaque type affichés en moins de 500 ms, mise en page et peinture
                comprises, sous 5 000 éléments ; tri des 5 000 interventions en moins de 500 ms (D101).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_ecrans.py" -v
"""
import csv
import io
import json
import re
import statistics
import subprocess
import sys
import tempfile
import unicodedata
import unittest
import urllib.parse
from pathlib import Path

from calcul_wiki import TABLES as CALCUL_TABLES, CalculWiki
from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier
from test_poste import AUDIT_TEXTES_JS

HEURE_FIXE = "2026-10-19T09:00:00"
MAINTENANT = "2026-10-19 09:00"
PROFILS = {"demandeur": ("Lucie Martin", ""), "technicien": ("", "TEC-0001"), "responsable": ("", "")}
MENTION = "Statistique de l'historique, pas un diagnostic"
SANS_CONSIGNATION = "Aucune consignation saisie pour cet équipement"
SANS_TEXTE = "Aucun texte validé pour l'instant."
PHRASE_SAVOIR_FAIRE = "Ce savoir-faire ne remplace pas la consignation de l'équipement"
PIEGE = '<img src=x onerror="window.__piege = 1"><script>window.__piege = 2</script><b>gras</b>'
CONSIGNATION_PIEGEE = ("  1. Couper le sectionneur " + PIEGE + "\r\n2. Purger & vérifier « 0 bar »\n\n"
                       "   3. Cadenas personnel\t(clé sur soi)\n")
NOUVEL_ONGLET = "s'ouvre dans un nouvel onglet"
BUDGET_MS = 500                                    # D101 : un écran du wiki en moins de 500 ms

# ---------------------------------------------------------------------------------------------------
# Base d'essai de la refonte 2 posée sur la démo : textes des machines et des articles, savoir-faire, journal
# ---------------------------------------------------------------------------------------------------

MODELE = "claude-sonnet-5-5"
VALIDEUR = "Paul Martin"
TITRE_PO02 = "PO-02 — Pompe centrifuge eau de refroidissement"
TITRE_CP01 = "CP-01 — Compresseur à vis 30 kW"
TITRE_KIT = "Kit garniture mécanique PO-02"
TITRE_SF = "Changer la garniture de PO-02"
TITRE_ALIGNER = "Aligner l'accouplement de PO-02"
TITRE_SP_ALIGNER = TITRE_ALIGNER + " — comparateur"
TITRE_PIEGE = '<img src=x onerror="window.__piege = 3">Régler <b>gras</b>'
COLONNES_PAGES = ("id;type;titre;cle;equipement_id;article_id;cause_code;rattache_a;texte;ot_cites;liens;version;origine;"
                  "modele;derniere_entree;valide_par;valide_le;cree_le;modifie_le;statut").split(";")
COLONNES_JOURNAL = ("id;nature;ot_id;date_intervention;statut;anterieure;ordre;pages;changements;contradictions;raisons;"
                    "modele;essais;cree_le;traite_le;decide_par;decide_le;motif").split(";")
MOTIF_CITATION = re.compile(r"\[(OT-\d{4}-\d{4,})\]")
MOTIF_LIEN = re.compile(r"\[\[([^\[\]]+)\]\]")

TEXTE_PO02 = "\n".join([
    "## En bref",
    "- La garniture mécanique fuit côté accouplement [OT-2025-0010] [OT-2025-0044]",
    "- Le remplacement du [[" + TITRE_KIT + "]] arrête la fuite, voir [[" + TITRE_SF + "]] [OT-2026-0026]",
    "- Le raccord de refoulement se desserre [OT-2025-0030]",
    "## Astuces",
    # Le même OT cité deux fois dans la phrase : un seul petit numéro (relecture de T137, m1)
    "- Repérer l'accouplement [OT-2026-0098] avant le démontage, voir [[Fuite]] et [[Page disparue]] [OT-2026-0098] [OT-2025-0010]",
])
TEXTE_CP01 = ("## Ce qui revient\n- Le filtre à air se colmate vite [OT-2026-0171]\n"
              "## En bref\n- Purger le sécheur chaque semaine [OT-2026-0161]")
TEXTE_KIT = ("## À quoi il sert\n- Il assure l'étanchéité de l'arbre de la [[" + TITRE_PO02 + "]] [OT-2026-0214]\n"
             "- Il s'use vite quand l'accouplement est désaligné, voir [[" + TITRE_PIEGE + "]] [OT-2026-0098]")
TEXTE_SF = ("## Étapes\n- Repérer la position de l'accouplement avant le démontage, voir [[Fuite de garniture]] [OT-2026-0098]\n"
            "## Pièges\n- Ne jamais monter la garniture à sec [OT-2026-0133] [OT-2026-0058]\n"
            "## Quand le faire\n- Dès la première goutte sous la garniture [OT-2026-0133]")
TEXTE_PIEGE = "## Étapes\n- Régler <script>window.__piege = 4</script> la <b>vitesse</b> & « bien » [OT-2026-0098]"


def citations(texte):
    vus = []
    for ot in MOTIF_CITATION.findall(texte or ""):
        if ot not in vus:
            vus.append(ot)
    return vus


def page_wiki(identifiant, type_, titre, texte, origine, liens="", valide_le="2026-10-15 10:00", **autres):
    ligne = dict.fromkeys(COLONNES_PAGES, "")
    ligne.update(id=identifiant, type=type_, titre=titre, texte=texte, origine=origine, liens=liens, version="1",
                 modele="" if origine == "manuel" else MODELE, valide_par=VALIDEUR, valide_le=valide_le,
                 ot_cites=";".join(citations(texte)), cree_le="2026-10-10 08:00", modifie_le=valide_le,
                 derniere_entree="WJ-00001", statut="active")
    ligne.update(autres)
    return ligne


PAGES = [
    page_wiki("WP-0001", "équipement", TITRE_PO02, TEXTE_PO02, "IA", "ART-0016;WP-0003;PANNE-S01", "2026-10-14 08:00",
              equipement_id="EQ-0005"),
    page_wiki("WP-0002", "composant", TITRE_KIT, TEXTE_KIT, "IA", "EQ-0005;WP-0006", article_id="ART-0016"),
    page_wiki("WP-0003", "savoir-faire", TITRE_SF, TEXTE_SF, "IA et manuel", "WP-0010", "2026-10-17 11:15", equipement_id="EQ-0005"),
    page_wiki("WP-0004", "savoir-faire", "Remonter le kit de garniture",
              "## Étapes\n- Graisser légèrement les joints, comme dans [[" + TITRE_SF + "]] [OT-2026-0058]", "manuel", "WP-0003",
              article_id="ART-0016"),
    page_wiki("WP-0005", "savoir-faire", "Purger le pressostat", "## Étapes\n- Purger avant de relever la mesure [OT-2026-0098]",
              "manuel", equipement_id="EQ-0031"),
    page_wiki("WP-0006", "savoir-faire", TITRE_PIEGE, TEXTE_PIEGE, "IA", equipement_id="EQ-0005"),
    page_wiki("WP-0007", "savoir-faire", TITRE_ALIGNER, "## Étapes\n- Poser le comparateur sur le moyeu, voir [[Fuite]] [OT-2026-0214]",
              "IA", "PANNE-S01", rattache_a="WP-0001"),
    page_wiki("WP-0008", "savoir-faire", TITRE_SP_ALIGNER, "## Pièces et outillage\n- Comparateur à cadran [OT-2026-0214]", "IA",
              valide_le="2026-10-18 10:00", rattache_a="WP-0007"),
    page_wiki("WP-0009", "savoir-faire", "Ancien geste", "## Étapes\n- Vieux geste sur la [[" + TITRE_PO02 + "]] et son [[" + TITRE_KIT
              + "]] [OT-2025-0010]", "IA", "EQ-0005;ART-0016;PANNE-S01", equipement_id="EQ-0005", statut="archivée"),
    page_wiki("WP-0010", "mode", "Fuite de garniture", "## Causes\n- Garniture usée de la [[" + TITRE_PO02 + "]] [OT-2025-0010]",
              "manuel", "EQ-0005", cause_code="C01"),
    page_wiki("WP-0011", "équipement", "PO-02 — garniture", "## Astuces\n- Garder un kit d'avance [OT-2025-0044]", "IA",
              rattache_a="WP-0001"),
    page_wiki("WP-0012", "savoir-faire", "Règles de l'atelier", "## Étapes\n- Ranger l'outillage après chaque intervention [OT-2026-0001]",
              "manuel"),
    page_wiki("WP-0013", "équipement", TITRE_CP01, TEXTE_CP01, "manuel", "", "2026-10-16 09:00", equipement_id="EQ-0001"),
    # Ancienne page « composant libre » (composant sans article) : plus de page (relecture de T137, m4)
    page_wiki("WP-0014", "composant", "Joint torique libre", "## À quoi il sert\n- Il étanche le bouchon de vidange [OT-2026-0001]",
              "manuel"),
]
SAVOIR_FAIRE_ACTIFS = ["WP-0003", "WP-0004", "WP-0005", "WP-0006", "WP-0007", "WP-0008", "WP-0012"]

# Intervention piégée (relecture de T137, m4) : chaque texte de la page Intervention porte des balises ; ouverte (en
# attente), sans technicien sur l'OT, deux techniciens y ont pointé du temps (m7).
OT_PIEGE = "OT-2026-9001"
TEXTES_OT_PIEGE = {
    "travail_a_faire": "Démonter <script>window.__piege = 11</script> le <b>carter</b> & « vérifier »\n  puis remonter",
    "compte_rendu": '<img src=x onerror="window.__piege = 12">Joint <i>changé</i>\n\tRelevé : 3 bar',
    "astuce": "<b>Graisser</b> le joint <script>window.__piege = 13</script>",
    "motif_attente": 'Pièce <img src=x onerror="window.__piege = 14"> en commande',
    "motif_annulation": '<a href="#/wiki">lien</a> <b>annulé</b> <svg onload="window.__piege = 15"></svg>',
}
SECTIONS_OT_PIEGE = {"wiki-travail": "travail_a_faire", "wiki-compte-rendu": "compte_rendu", "wiki-astuce": "astuce",
                     "wiki-motif-attente": "motif_attente", "wiki-motif-annulation": "motif_annulation"}
ORDRE_PIEGE = dict(TEXTES_OT_PIEGE, id=OT_PIEGE, origine="manuel", equipement_id="EQ-0031", type="correctif différé", priorite="P3",
                   statut="En attente", titre='PE-01 — <img src=x onerror="window.__piege = 10">Fuite <b>vive</b>',
                   date_creation="2026-10-18 08:00", date_prevue="2026-10-21", technicien_id="", arret_production="0")
TEMPS_PIEGE = [{"id": "OTT-099001", "ot_id": OT_PIEGE, "technicien_id": "TEC-0003", "date": "2026-10-18", "heures": "1.5"},
               {"id": "OTT-099002", "ot_id": OT_PIEGE, "technicien_id": "TEC-0001", "date": "2026-10-18", "heures": "0.5"}]

OBSERVATION_PIEGEE = "Le raccord était serré <img src=x onerror=\"window.__piege = 5\"> : c'est le joint qui était cuit."
CONTRADICTIONS_PO02 = [
    {"page": TITRE_PO02, "pageCle": "EQ:EQ-0005", "phrase": "La garniture mécanique fuit côté accouplement",
     "observation": "La fuite vient du désalignement de l'accouplement, pas de l'usure de la garniture.",
     "ot": ["OT-2026-0214"], "statut": "ouverte"},
    {"page": TITRE_PO02, "pageCle": "EQ:EQ-0005", "phrase": "Le raccord de refoulement se desserre [OT-2025-0030]",
     "observation": OBSERVATION_PIEGEE, "ot": ["OT-2026-0214"], "statut": "ouverte"},
]
CONTRADICTIONS_SF = [
    {"page": TITRE_SF, "pageCle": "WP:WP-0003", "phrase": "Ne jamais monter la garniture à sec",
     "observation": "La garniture avait été montée graissée et elle a fui quand même.", "ot": ["OT-2025-0030"],
     "statut": "ouverte"},
]
CONTRADICTION_FERMEE = [
    {"page": TITRE_PO02, "pageCle": "EQ:EQ-0005", "phrase": "Le raccord de refoulement se desserre",
     "observation": "Déjà tranché", "ot": ["OT-2025-0044"], "statut": "fermée", "decision": "ancien",
     "decide_par": VALIDEUR, "decide_le": "2026-10-12 10:00"},
]


def entree(identifiant, statut, ot="", nature="ingestion", ordre="", anterieure="0", changements=None,
           contradictions=None, decide_le="", raisons=""):
    ligne = dict.fromkeys(COLONNES_JOURNAL, "")
    ligne.update(id=identifiant, nature=nature, ot_id=ot, statut=statut, anterieure=anterieure, ordre=ordre,
                 changements=json.dumps(changements or [], ensure_ascii=False),
                 contradictions=json.dumps(contradictions or [], ensure_ascii=False), raisons=raisons, essais="1",
                 modele=MODELE if nature == "ingestion" else "", cree_le="2026-10-09 08:00", traite_le="2026-10-09 08:05",
                 decide_par=VALIDEUR if decide_le else "", decide_le=decide_le)
    return ligne


JOURNAL = [
    entree("WJ-00001", "validée", "OT-2025-0010", ordre="1", decide_le="2026-10-10 08:00"),
    entree("WJ-00002", "validée", "OT-2026-0214", ordre="2", contradictions=CONTRADICTIONS_PO02, decide_le="2026-10-14 08:00"),
    entree("WJ-00003", "validée", "OT-2025-0030", ordre="3", anterieure="1", contradictions=CONTRADICTIONS_SF,
           decide_le="2026-10-16 09:00"),
    entree("WJ-00004", "à valider", "OT-2026-0082", ordre="4", changements=[{
        "page": "WP-0001", "cle": "EQ:EQ-0005", "type": "équipement", "titre": TITRE_PO02, "creation": False, "version_avant": 1,
        "avant": TEXTE_PO02, "apres": TEXTE_PO02 + "\n- Le raccord tient avec un joint neuf, voir [[Règles de l'atelier]] [OT-2026-0082]"}]),
    entree("WJ-00005", "à valider", "OT-2026-0058", ordre="5", changements=[{
        "cle": "TITRE:graisser la garniture", "type": "savoir-faire", "titre": "Graisser la garniture", "creation": True,
        "version_avant": 0, "avant": "", "apres": "## Étapes\n- Graisser la garniture du [[" + TITRE_KIT + "]] [OT-2026-0058]"}]),
    entree("WJ-00006", "en file", "OT-2026-0072"),
    entree("WJ-00007", "refusée", "OT-2026-0017", raisons="Page « PO-02 » : phrase sans OT."),
    entree("WJ-00008", "refusée", "OT-2026-0026", raisons="Page « PO-02 » : comptage interdit."),
    entree("WJ-00009", "en file", "OT-2026-0026"),
    entree("WJ-00010", "à refaire", "OT-2026-0126"),
    entree("WJ-00011", "rejetée", "OT-2026-0133", decide_le="2026-10-13 10:00"),
    entree("WJ-00012", "validée", "OT-2025-0044", ordre="6", contradictions=CONTRADICTION_FERMEE, decide_le="2026-10-12 10:00"),
    entree("WJ-00013", "refusée", "OT-2026-0072", raisons="Page « PO-02 » : date interdite."),
    entree("WJ-00014", "refusée", nature="manuel", raisons="La page a été modifiée entre-temps."),
]

# [[titre]] → page qui s'affiche (identifiant) ; « Page disparue », l'ancienne page de mode et l'ancienne sous-page de
# machine (types retirés) restent du texte.
RESOLUTIONS = {TITRE_PO02: "EQ-0005", TITRE_KIT: "ART-0016", TITRE_SF: "WP-0003", "Fuite": "PANNE-S01", TITRE_PIEGE: "WP-0006"}
ORIGINE_IA = "IA Rédigé avec l'IA (claude-sonnet-5-5) à partir des OT cités — validé par Paul Martin le %s"
ORIGINE_MANUEL = "Écrit par Paul Martin le %s"
ORIGINE_MIXTE = "IA Rédigé avec l'IA (claude-sonnet-5-5) à partir des OT cités, puis modifié à la main — validé par Paul Martin le %s"

# La base remplace le wiki (vide) de la démo et ajoute l'intervention piégée et ses temps pointés.
BASE_JS = """async ([pages, journal, ordre, temps]) => {
  await Donnees.modifier('wiki_pages', (lignes) => { lignes.splice(0, lignes.length, ...pages); }, { journal: false });
  await Donnees.modifier('wiki_journal', (lignes) => { lignes.splice(0, lignes.length, ...journal); }, { journal: false });
  await Donnees.modifier('ordres_travail', (lignes) => { lignes.push(ordre); }, { journal: false });
  await Donnees.modifier('ot_temps', (lignes) => { lignes.push(...temps); }, { journal: false });
}"""


def table_csv(colonnes, lignes):
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(colonnes)
    for ligne in lignes:
        ecrivain.writerow([ligne.get(c, "") for c in colonnes])
    return sortie.getvalue()


# Tables lues par le calcul Python, relues dans le navigateur (la démo telle qu'affichée : à l'ouverture, Prévo peut y
# ajouter un OT préventif échu, RG5), puis réécrites en CSV.
TABLES_JS = """(noms) => Object.fromEntries(noms.map((nom) => [nom, Donnees.lignes(nom)]))"""


# --- lectures du DOM ---------------------------------------------------------------------------------

ACCUEIL_JS = """() => {
  const t = (e) => (e ? e.textContent.replace(/\\s+/g, ' ').trim() : null);
  const lien = (a) => [t(a), a.getAttribute('href')];
  const tete = (li) => li.querySelector('.wiki-ligne-corps > :first-child');
  return {
    pastille: t(document.querySelector('.wiki-synthese-pastille')),
    h1: t(document.querySelector('#contenu h1')),
    phrase: Array.from(document.querySelectorAll('#wiki-phrase-resume a')).map(lien),
    tireDe: t(document.querySelector('#wiki-tire-de')),
    champ: document.querySelectorAll('.wiki-synthese #wiki-champ-accueil.wiki-recherche-champ').length,
    exemple: document.querySelector('#wiki-champ-accueil').getAttribute('placeholder'),
    suivi: document.querySelectorAll('#wiki-suivi').length,
    minis: Array.from(document.querySelectorAll('#wiki-suivi .wiki-mini')).map((a) => ({ vue: a.dataset.suivi, href: a.getAttribute('href'),
      nombre: t(a.querySelector('.wiki-mini-nombre')), libelle: t(a.querySelector('span')), classe: a.className })),
    actions: Array.from(document.querySelectorAll('#wiki-suivi .wiki-suivi-actions a')).map(lien),
    briques: Array.from(document.querySelectorAll('.wiki-brique')).map((a) => ({ type: a.dataset.type, href: a.getAttribute('href'),
      titre: t(a.querySelector('h2')), nombre: t(a.querySelector('.wiki-brique-nombre')), ligne: t(a.querySelector('.wiki-brique-ligne')),
      brut: a.querySelector('.wiki-brique-ligne').textContent, pastille: a.querySelector('.bento-pastille-icone').className })),
    dernieres: Array.from(document.querySelectorAll('#wiki-dernieres li')).map((li) => ({ id: li.dataset.id,
      titre: [tete(li).textContent, tete(li).getAttribute('href'), tete(li).tagName], sous: t(li.querySelector('.wiki-ligne-sous')),
      liens: Array.from(li.querySelectorAll('.wiki-ligne-sous a')).map(lien) })),
    toutes: Array.from(document.querySelectorAll('#wiki-accueil .bento-tout-voir')).map(lien),
    pannes: Array.from(document.querySelectorAll('#wiki-pannes-frequentes li')).map((li) => ({ id: li.dataset.id,
      lien: [li.querySelector('a').textContent, li.querySelector('a').getAttribute('href')], cas: t(li.querySelector('.wiki-barre-cas')),
      largeur: li.querySelector('.wiki-jauge i').style.width })),
  };
}"""

LISTE_JS = """() => {
  const t = (e) => (e ? e.textContent.replace(/\\s+/g, ' ').trim() : null);
  const racine = document.querySelector('.wiki-liste-entites');
  const h1 = racine.querySelector('h1');
  return { titre: h1.firstChild.textContent.trim(), nombre: t(h1.querySelector('.wiki-nombre')), reserve: t(racine.querySelector('.vide b')),
    fil: Array.from(racine.querySelectorAll('.fil a, .fil > span:not([aria-hidden])')).map((e) => [t(e), e.getAttribute('href')]),
    lignes: Array.from(racine.querySelectorAll('li[data-id], tbody tr')).filter((e) => e.querySelector('a')).map((e) => {
      const a = e.querySelector('a');
      const href = a.getAttribute('href');
      return [e.dataset.id || decodeURIComponent(href.slice('#/wiki/'.length)), href, a.textContent]; }),
    liens: Array.from(racine.querySelectorAll('a[href^="#/wiki/"]')).map((a) => a.getAttribute('href')),
    bouton: t(racine.querySelector('.wiki-voir-autres')) };
}"""

TROUVES_JS = """() => Array.from(document.querySelectorAll('#wiki-trouves .wiki-groupe:not(.wiki-plein-texte)')).map((g) => ({
  type: g.dataset.type, titre: g.querySelector('.wiki-groupe-titre').textContent.replace(/\\s+/g, ' ').trim(),
  ids: Array.from(g.querySelectorAll('li')).map((li) => li.dataset.id),
  liens: Array.from(g.querySelectorAll('li')).map((li) => { const a = li.querySelector('.wiki-ligne-corps > a'); return a ? a.getAttribute('href') : null; }),
  textes: Array.from(g.querySelectorAll('li')).map((li) => li.querySelector('.wiki-ligne-corps > :first-child').textContent),
  caches: g.querySelectorAll('li[hidden]').length,
  bouton: g.querySelector('.wiki-voir-autres') ? g.querySelector('.wiki-voir-autres').textContent.trim() : null }))"""

ARTICLES_JS = """() => Array.from(document.querySelectorAll('#wiki-articles tbody tr')).filter((tr) => tr.querySelector('a')).map((tr) => {
  const a = tr.querySelector('a');
  const etat = tr.querySelector('.wiki-etat-stock');
  return [decodeURIComponent(a.getAttribute('href').slice('#/wiki/'.length)), a.getAttribute('href'), etat.textContent, etat.className,
    tr.lastElementChild.textContent.trim()];
})"""

INTERVENTIONS_JS = """() => Array.from(document.querySelectorAll('#wiki-interventions tbody tr')).map((tr) => {
  const c = tr.cells;
  const href = (td) => { const a = td.querySelector('a'); return a ? a.getAttribute('href') : null; };
  return { id: c[1].textContent.trim(), lien: href(c[1]), statut: c[3].textContent.trim(), machine: href(c[4]), panne: href(c[5]) };
})"""

FAITS_JS = """() => Array.from(document.querySelectorAll('#wiki-faits dt')).map((dt) => {
  const dd = dt.nextElementSibling;
  const a = dd.querySelector('a');
  return [dt.textContent.trim(), dd.textContent.replace(/\\s+/g, ' ').trim(), a ? a.getAttribute('href') : null];
})"""

FIL_JS = "() => Array.from(document.querySelectorAll('#contenu .fil a')).map((a) => [a.textContent.trim(), a.getAttribute('href')])"

# La panne la plus fréquente change de code : un code qui change à l'encodage, un libellé piégé (CODE_PIEGE, LIBELLE_PIEGE).
PANNE_PIEGEE_JS = """async ([code, libelle]) => {
  const premiere = Wiki.listeEntites('panne')[0];
  await Donnees.modifier('codes_defaillance', (lignes) => {
    lignes.push({ id: 'CD-9001', famille: 'symptôme', code, libelle }); return true; }, { action: 'test des écrans du wiki' });
  await Donnees.modifier('ordres_travail', (lignes) => {
    lignes.filter((ot) => ot.symptome_code === premiere.code).forEach((ot) => { ot.symptome_code = code; }); return true; },
    { action: 'test des écrans du wiki' });
  return { ancien: premiere.code, cas: premiere.cas };
}"""

# Page d'une entité (T137) : tout ce que montre la page, pour la comparer à Wiki.entite et au calcul Python.
ENTITE_JS = """() => {
  const t = (e) => (e ? e.textContent.replace(/\\s+/g, ' ').trim() : null);
  const href = (a) => (a ? a.getAttribute('href') : null);
  const racine = document.querySelector('#contenu .wiki-page');
  if (!racine || racine.classList.contains('wiki-introuvable')) return { introuvable: true, h1: t(document.querySelector('#contenu h1')) };
  const sansRefs = (e) => { const copie = e.cloneNode(true); copie.querySelectorAll('sup.wiki-ref').forEach((s) => s.remove()); return t(copie); };
  const refs = (e) => Array.from(e.querySelectorAll('sup.wiki-ref')).map((s) => {
    const cible = s.firstElementChild;
    return [cible.textContent, s.dataset.ot, cible.tagName, href(cible), cible.getAttribute('title')]; });
  const phrase = (p) => ({ texte: sansRefs(p), refs: refs(p), liens: Array.from(p.querySelectorAll('a.wiki-lien-page')).map((a) => [t(a), href(a)]),
    absents: Array.from(p.querySelectorAll('.wiki-lien-absent')).map(t) });
  const rect = (e) => { const r = e.getBoundingClientRect(); return { gauche: r.left, haut: r.top, droite: r.right, bas: r.bottom }; };
  const grille = racine.querySelector('.wiki-page-grille');
  const lecture = racine.querySelector('.wiki-lecture');
  const fiche = racine.querySelector('#wiki-faits');
  const alertes = racine.querySelector('.wiki-alertes');
  const consignation = racine.querySelector('#wiki-consignation, #wiki-entete');
  const mere = racine.querySelector('#wiki-mere');
  return {
    id: racine.dataset.page, type: racine.dataset.type, equipement: racine.dataset.equipement, dataMere: racine.dataset.mere,
    h1: t(racine.querySelector('h1')), h1Brut: racine.querySelector('h1').textContent,
    fil: Array.from(racine.querySelectorAll('.fil a, .fil .wiki-fil-nom')).map((e) => [t(e), href(e)]),
    puce: racine.querySelector('.wiki-entete-entite .wiki-puce').className, sousTitre: t(racine.querySelector('.wiki-sous-titre')),
    mere: mere ? { texte: t(mere), lien: mere.querySelector('a') ? [mere.querySelector('a').textContent, href(mere.querySelector('a'))] : null,
      archivee: t(mere.querySelector('.wiki-mere-archivee')) } : null,
    actions: Array.from(racine.querySelectorAll('.wiki-actions a')).map((a) => [a.id, t(a), href(a)]),
    blocs: Array.from(racine.children).map((e) => e.id || e.className),
    alertes: alertes ? Array.from(alertes.children).map((e) => e.id) : [],
    enTete: alertes ? Boolean(alertes.compareDocumentPosition(grille) & Node.DOCUMENT_POSITION_FOLLOWING) : null,
    sections: Array.from(lecture.children).flatMap((e) => (e.classList.contains('wiki-textes')
      ? Array.from(e.children).map((s) => 'texte:' + s.dataset.rubrique) : [e.id || e.className])),
    faits: Array.from(fiche.querySelectorAll('dt')).map((dt) => [dt.textContent.trim(), t(dt.nextElementSibling),
      href(dt.nextElementSibling.querySelector('a'))]),
    ficheRect: rect(fiche), lectureRect: rect(lecture), alertesRect: alertes ? rect(alertes) : null,
    textes: Array.from(racine.querySelectorAll('.wiki-texte')).map((s) => ({ rubrique: s.dataset.rubrique,
      forme: s.querySelector('.wiki-prose') ? 'prose' : (s.querySelector('.wiki-phrases') ? 'liste' : null),
      phrases: Array.from(s.querySelectorAll('.wiki-phrase')).map(phrase),
      origine: t(s.querySelector('.wiki-origine')), sansTexte: t(s.querySelector('.wiki-sans-texte')) })),
    contradictions: Array.from(racine.querySelectorAll('.wiki-contradiction')).map((c) => ({ entree: c.dataset.entree, rang: c.dataset.rang,
      anterieure: c.dataset.anterieure, page: phrase(c.querySelector('.wiki-cote-page .wiki-phrase')), titreOt: t(c.querySelector('.wiki-cote-ot h3')),
      observation: c.querySelector('.wiki-observation-texte').textContent, refs: refs(c.querySelector('.wiki-observation')),
      boutons: Array.from(c.querySelectorAll('button[data-decision]')).map((b) => [b.dataset.decision, t(b)]),
      notes: c.querySelectorAll('textarea').length })),
    sups: Array.from(racine.querySelectorAll('sup.wiki-ref')).map((s) => [Number(s.textContent.trim()), s.dataset.ot]),
    references: Array.from(racine.querySelectorAll('#wiki-references li')).map((li) => [li.id, li.dataset.ot, t(li),
      Array.from(li.querySelectorAll('a')).map(href)]),
    crochets: (racine.innerText.match(/\\[OT-/g) || []).length,
    interventions: Array.from(racine.querySelectorAll('#wiki-interventions .wiki-intervention')).map((e) => [e.dataset.id,
      t(e.querySelector('.badge.statut')), href(e.querySelector(':scope > a, td:nth-child(2) a'))]),
    voirAutres: t(racine.querySelector('#wiki-interventions .wiki-voir-autres')),
    attente: Array.from(racine.querySelectorAll('#wiki-en-attente li')).map((li) => [li.dataset.entree, t(li)]),
    consignation: consignation ? { id: consignation.id, titre: t(consignation.querySelector('h2')),
      phrase: t(consignation.querySelector('.wiki-entete-phrase')),
      texte: consignation.querySelector('.wiki-consignation-texte') ? consignation.querySelector('.wiki-consignation-texte').textContent : null,
      absence: t(consignation.querySelector('.wiki-sans-consignation')),
      equipements: Array.from(consignation.querySelectorAll('.wiki-entete-equipements a')).map((a) => [t(a), href(a)]),
      aide: t(consignation.querySelector('p.aide')), modifier: href(consignation.querySelector('#wiki-modifier-consignation')) } : null,
    sousPages: Array.from(racine.querySelectorAll('#wiki-sous-pages li')).map((li) => [li.dataset.id, t(li.querySelector('a')),
      href(li.querySelector('a'))]),
    savoirFaire: Array.from(racine.querySelectorAll('#wiki-savoir-faire li')).map((li) => li.dataset.id),
    retours: Array.from(racine.querySelectorAll('#wiki-retours li')).map((li) => [li.dataset.id,
      t(li.querySelector('.wiki-ligne-corps > :first-child')), href(li.querySelector('.wiki-ligne-corps > a'))]),
    blocsOt: Object.fromEntries(Array.from(lecture.querySelectorAll(':scope > .wiki-section')).map((s) => [s.id,
      t(s.querySelector('.wiki-texte-ot, .wiki-lignes-page, .wiki-vide'))])),
    liens: Array.from(new Set(Array.from(racine.querySelectorAll('a[href]')).map(href))),
    controles: racine.querySelectorAll('input:not([type=search]), select, textarea, form').length,
  };
}"""

# Articles consommés (page Machine : la liste sous « Consommés ») ou changés (page Panne) : chaque ligne et ses petits
# numéros (D118, T143).
LIGNES_ARTICLES_JS = """(type) => {
  const section = document.querySelector(type === 'panne' ? '#wiki-articles-changes' : '#wiki-articles');
  const titre = Array.from(section.querySelectorAll('h3')).find((h) => h.textContent.trim().startsWith('Consommés'));
  const bloc = type === 'panne' ? section : titre.nextElementSibling;
  return Array.from(bloc.querySelectorAll('li.wiki-ligne')).map((li) => {
    const sous = li.querySelector('.wiki-ligne-sous');
    const sups = Array.from(sous.querySelectorAll('sup.wiki-ref'));
    const copie = sous.cloneNode(true);
    copie.querySelectorAll('sup, .wiki-ref-autres').forEach((e) => e.remove());
    const autres = sous.querySelector('.wiki-ref-autres');
    return { id: li.dataset.id, ot: sups.map((s) => s.dataset.ot), numeros: sups.map((s) => Number(s.firstElementChild.textContent)),
      balises: sups.map((s) => s.firstElementChild.tagName), liens: sups.map((s) => s.firstElementChild.getAttribute('href')),
      bulles: sups.map((s) => s.firstElementChild.getAttribute('title')), noms: sups.map((s) => s.firstElementChild.getAttribute('aria-label')),
      autres: autres ? autres.textContent.trim() : null, texte: copie.textContent.replace(/\\s+/g, ' ').trim(),
      droite: li.querySelector('.wiki-ligne-droite').textContent.trim() };
  });
}"""

RESULTATS_JS = """(racine) => Array.from(document.querySelectorAll(racine + ' .wiki-portee')).map((bloc) => ({
  portee: bloc.dataset.portee, libelle: bloc.querySelector('h3').firstChild.textContent.trim(),
  ids: Array.from(bloc.querySelectorAll('.wiki-trouve')).map((li) => li.dataset.id),
  types: Array.from(bloc.querySelectorAll('.wiki-trouve')).map((li) => li.dataset.type),
  caches: Array.from(bloc.querySelectorAll('.wiki-trouve')).map((li) => li.hidden),
  liensOt: bloc.querySelectorAll('a[href^="#/ot"]').length,
  numeros: Array.from(bloc.querySelectorAll('.wiki-trouve')).map((li) => li.querySelector('.wiki-ligne-tete > :first-child').tagName),
  marques: bloc.querySelectorAll('.wiki-extrait mark').length,
  bouton: bloc.querySelector('.wiki-voir-plus') ? bloc.querySelector('.wiki-voir-plus').textContent.trim() : null }))"""

ATTENDU_RECHERCHE_JS = """([texte, equipementId]) => Wiki.rechercher(texte, { equipementId }).portees
  .filter((p) => p.resultats.length)
  .map((p) => ({ portee: p.portee, libelle: p.libelle, ids: p.resultats.map((r) => (r.type === 'ot' ? r.otId : r.pageId)),
    types: p.resultats.map((r) => r.type) }))"""

# Mesure du délai de la recherche : de la frappe (événement input) à l'apparition des résultats.
DELAI_JS = """([selecteur, texte]) => new Promise((resoudre) => {
  const champ = document.querySelector(selecteur);
  const zone = champ.closest('.wiki-recherche, .wiki-recherche-demande').querySelector('.wiki-resultats');
  let t0 = 0;
  const observateur = new MutationObserver(() => {
    if (zone.querySelector('.wiki-portee, .wiki-rien')) { observateur.disconnect(); resoudre(performance.now() - t0); }
  });
  observateur.observe(zone, { childList: true, subtree: true });
  zone.textContent = '';
  champ.value = texte;
  t0 = performance.now();
  champ.dispatchEvent(new Event('input', { bubbles: true }));
})"""

# Durée d'affichage d'un écran : du changement d'adresse à l'apparition de `selecteur`, mise en page forcée, puis
# l'image suivante peinte (la tâche qui suit requestAnimationFrame) — relecture de T137 (critique) : arrêtée dans
# requestAnimationFrame, la mesure ne comptait ni la mise en page ni la peinture.
MESURE_JS = """([route, selecteur]) => new Promise((resoudre) => {
  const t0 = performance.now();
  const fin = () => {
    document.body.getBoundingClientRect();
    requestAnimationFrame(() => setTimeout(() => resoudre({ duree: performance.now() - t0,
      elements: document.querySelectorAll('#contenu *').length }), 0));
  };
  const observateur = new MutationObserver(() => {
    if (document.querySelector(selecteur)) { observateur.disconnect(); fin(); }
  });
  observateur.observe(document.getElementById('contenu'), { childList: true, subtree: true });
  location.hash = route;
})"""

# Entité la plus lourde de chaque type : [identifiant, nombre] — machine et panne (code symptôme) qui ont le plus d'OT,
# article qui a le plus de mouvements de stock, technicien qui a le plus d'interventions (son OT ou du temps pointé),
# intervention qui a le plus de temps pointés, de mouvements et d'opérations (à égalité, le plus petit identifiant).
LOURDES_JS = """() => {
  const compter = (lignes, champ) => { const n = new Map();
    lignes.forEach((l) => { const c = String(l[champ] || '').trim(); if (c) n.set(c, (n.get(c) || 0) + 1); }); return n; };
  const plus = (n) => Array.from(n).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))[0];
  const ordres = Donnees.lignes('ordres_travail');
  const parTechnicien = new Map();
  const poser = (technicien, ot) => { const t = String(technicien || '').trim(); if (!t) return;
    if (!parTechnicien.has(t)) parTechnicien.set(t, new Set()); parTechnicien.get(t).add(ot); };
  ordres.forEach((ot) => poser(ot.technicien_id, ot.id));
  Donnees.lignes('ot_temps').forEach((t) => poser(t.technicien_id, t.ot_id));
  const panne = plus(compter(ordres, 'symptome_code'));
  return { machine: plus(compter(ordres, 'equipement_id')), panne: [Wiki.idPanne(panne[0]), panne[1]],
    article: plus(compter(Donnees.lignes('mouvements_stock'), 'article_id')),
    technicien: plus(new Map(Array.from(parTechnicien, ([t, ots]) => [t, ots.size]))),
    intervention: plus(compter([].concat(Donnees.lignes('ot_temps'), Donnees.lignes('mouvements_stock'), Donnees.lignes('ot_operations')), 'ot_id')) };
}"""

# Largeur de la page et largeur visible : clientWidth, pas innerWidth — en émulation mobile, un débordement agrandit
# la fenêtre de mise en page (innerWidth 451 pour 375 px d'écran) et la comparaison avec innerWidth ne voyait rien.
LARGEUR_JS = "() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]"
ZONES_JS = """(racine) => Array.from(document.querySelectorAll(['a', 'button', 'summary', 'label.case', 'select', 'textarea',
    'input:not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=file])'].map((s) => racine + ' ' + s).join(', ')))
  .filter((e) => e.getClientRects().length > 0 && !e.closest('[hidden], .visuellement-cache'))
  .map((e) => [e.id || e.className || e.tagName, (e.textContent || e.value || '').trim().slice(0, 30),
               Math.round(e.getBoundingClientRect().height * 10) / 10])"""

ECRIRE_JS = """async ([table, id, valeurs]) => {
  await Donnees.modifier(table, (lignes) => { Object.assign(lignes.find((l) => l.id === id), valeurs); return true; },
    { action: 'test des écrans du wiki' });
}"""

TRIER_TITRES_JS = """(pages) => { const fr = new Intl.Collator('fr', { numeric: true, sensitivity: 'base' });
  return pages.slice().sort((a, b) => fr.compare(a[1], b[1]) || (a[0] < b[0] ? -1 : 1)).map((p) => p[0]); }"""


# --- valeurs attendues, calculées ici ----------------------------------------------------------------

def date_fr(iso):
    return "%s/%s/%s" % (iso[8:10], iso[5:7], iso[0:4]) if iso else ""


def date_heure_fr(valeur):
    return date_fr(valeur) + (" " + valeur[11:16] if len(valeur) >= 16 else "")


def plat(texte):
    return re.sub(r"\s+", " ", texte or "").strip()


def nombre_fr(valeur, decimales=None):
    """Nombre à la française comme UI.nombreFr (jusqu'à 2 décimales, milliers séparés)."""
    arrondi = round(float(valeur), 2)
    entier, _, fraction = ("%.2f" % abs(arrondi)).partition(".")
    fraction = fraction if decimales == 2 else fraction.rstrip("0")
    groupes = []
    while len(entier) > 3:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    groupes.insert(0, entier)
    return ("-" if arrondi < 0 else "") + " ".join(groupes) + ("," + fraction if fraction else "")


def euro(valeur):
    return nombre_fr(valeur, 2) + " €"


def pluriel(nombre, singulier, forme_plurielle):
    return "%d %s" % (nombre, forme_plurielle if nombre > 1 else singulier)


def valeur_fait(fait):
    """Valeur d'un fait à l'écran (précisions de wiki-page-ecrans.js), None si vide."""
    valeur = fait["valeur"]
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, (int, float)):
        if fait["libelle"] == "Prix unitaire":
            return euro(valeur)
        if fait["libelle"] == "Taux horaire":
            return euro(valeur) + " / h"
        return nombre_fr(valeur)
    texte = str(valeur)
    if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}", texte):
        return date_heure_fr(texte)
    return date_fr(texte) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texte) else texte


def faits_attendus(faits):
    """Fiche attendue : [libellé, valeur, lien] des faits non vides, dans l'ordre."""
    return [[f["libelle"], plat(valeur_fait(f)), "#/wiki/" + encoder(f["lien"]) if f["lien"] else None]
            for f in faits if valeur_fait(f) is not None]


def fiche_attendue(entite):
    """Fiche attendue d'une page : ses faits (faits_attendus) ; pour une intervention, à la place du fait « Technicien »,
    tous ses techniciens (sections.techniciens : « Techniciens » s'ils sont plusieurs, lien du premier) — relecture de
    T137, m7."""
    techniciens = (entite["sections"].get("techniciens") or []) if entite["type"] == "intervention" else []
    lignes = []
    for fait in entite["faits"]:
        if techniciens and fait["libelle"] == "Technicien":
            lignes.append(["Techniciens" if len(techniciens) > 1 else "Technicien", ", ".join(t["nom"] for t in techniciens),
                           "#/wiki/" + encoder(techniciens[0]["lien"]) if techniciens[0]["lien"] else None])
        elif valeur_fait(fait) is not None:
            lignes.extend(faits_attendus([fait]))
    return lignes


def titre_equipement(ligne):
    return " — ".join(v for v in ((ligne.get("repere") or "").strip(), (ligne.get("designation") or "").strip()) if v)


def titre_article(ligne):
    return (ligne.get("designation") or "").strip() or (ligne.get("reference") or "").strip() or ligne["id"]


LISTES = {"machines": "Machines", "pannes": "Pannes", "articles": "Articles", "techniciens": "Techniciens",
          "savoir-faire": "Savoir-faire", "interventions": "Interventions"}
LISTE_DU_TYPE = {"machine": "machines", "panne": "pannes", "article": "articles", "technicien": "techniciens",
                 "savoir-faire": "savoir-faire", "intervention": "interventions"}
CLES_NOMBRES = {"machines": "machines", "pannes": "pannes", "articles": "articles", "techniciens": "techniciens",
                "savoir-faire": "savoirFaire"}
CLOTURES = ("Clôturé techniquement", "Clôturé administrativement")
OUVERTS = ("Créé", "Préparé", "Planifié", "En cours", "En attente")
CODE_PIEGE = "S/1 é&"                              # « / », espace, accent, « & » : changent à l'encodage
LIBELLE_PIEGE = '<img src=x onerror="window.__piege = 7">Fuite <b>vive</b>'
PIEGE_MACHINE = 'Compresseur <img src=x onerror="window.__piege = 8"><b>vis</b>'
PIEGE_NOM = 'Moreau <img src=x onerror="window.__piege = 9"><b>gras</b>'
ERREURS_SERVEUR = [re.compile(r"status of 404.*/api/ping"), re.compile(r"status of 404.*/api/csv/")]
# Une page de chaque type (base d'essai) ; la page Intervention et la page Technicien ne s'ouvrent pas au demandeur.
SIX = {"machine": "EQ-0005", "panne": "PANNE-S01", "article": "ART-0016", "technicien": "TEC-0002",
       "intervention": "OT-2026-0214", "savoir-faire": "WP-0003"}


def encoder(valeur):
    """encodeURIComponent, refait ici : lettres, chiffres et - _ . ! ~ * ' ( ) restent tels quels."""
    return urllib.parse.quote(valeur, safe="-_.!~*'()")


def lien_panne(code):
    """Lien vers la page d'une panne : #/wiki/ + encodeURIComponent(« PANNE- » + encodeURIComponent(code))."""
    return "#/wiki/" + encoder("PANNE-" + encoder(code))


def sans_accents(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte) if not unicodedata.combining(c)).lower()


def mots_comparables(texte):
    return re.sub(r"[^a-z0-9]+", " ", sans_accents(texte).replace("œ", "oe").replace("æ", "ae")).split()


def est_un_cas(ot):
    """Cas d'une panne : OT correctif clôturé qui porte un code symptôme."""
    return ot["type"].strip().startswith("correctif") and ot["statut"].strip() in CLOTURES and ot["symptome_code"].strip() != ""


def compter_cas(ordres):
    cas = {}
    for ot in ordres:
        if est_un_cas(ot):
            cas[ot["symptome_code"].strip()] = cas.get(ot["symptome_code"].strip(), 0) + 1
    return cas


def libelle_symptome(tables, code):
    for ligne in tables["codes_defaillance"]:
        if ligne["famille"].strip() == "symptôme" and ligne["code"].strip() == code:
            return ligne["libelle"].strip()
    return code


def pannes_attendues(tables):
    """Pannes, calculées ici : [(identifiant, lien, libellé, cas)], par nombre de cas décroissant, puis code."""
    return [("PANNE-" + encoder(code), lien_panne(code), libelle_symptome(tables, code), cas)
            for code, cas in sorted(compter_cas(tables["ordres_travail"]).items(), key=lambda e: (-e[1], e[0]))]


def date_de_l_ot(ot):
    for champ in ("date_fin", "date_debut", "date_prevue", "date_creation"):
        if (ot.get(champ) or "").strip():
            return ot[champ].strip()
    return ""


def accueil_attendu(tables, profil, calcul):
    """Accueil de l'encyclopédie, calculé ici à partir des tables (définitions du contrat §20.12) pour un profil."""
    ordres = tables["ordres_travail"]
    nombres = {"machines": len(tables["equipements"]), "pannes": len(compter_cas(ordres)), "articles": len(tables["articles"]),
               "techniciens": None if profil == "demandeur" else len(tables["techniciens"]),
               "savoir-faire": sum(1 for p in tables["wiki_pages"] if p["type"] == "savoir-faire" and p["statut"] != "archivée")}
    noms = [("machines", "machine", "machines"), ("pannes", "panne", "pannes"), ("articles", "article", "articles"),
            ("techniciens", "technicien", "techniciens"), ("savoir-faire", "savoir-faire", "savoir-faire")]
    liens = [[pluriel(nombres[cle], un, plusieurs), "#/wiki/" + cle] for cle, un, plusieurs in noms if nombres[cle] is not None]
    par_machine = {}
    for ot in ordres:
        par_machine[ot["equipement_id"]] = par_machine.get(ot["equipement_id"], 0) + 1
    machines = sorted(tables["equipements"], key=lambda e: (-par_machine.get(e["id"], 0), titre_equipement(e), e["id"]))
    pannes = pannes_attendues(tables)
    clotures = sorted((o for o in ordres if o["statut"].strip() in CLOTURES), key=lambda o: (date_de_l_ot(o), o["id"]), reverse=True)
    # Lignes des briques Articles et Techniciens : comptes du calcul Python indépendant (tests/calcul_wiki.py).
    calcule = calcul.accueil(profil, MAINTENANT)
    articles = calcule["articles"]
    ligne_articles = " · ".join(p for p in (
        "%d sous le seuil" % articles["sousLeSeuil"] if articles["sousLeSeuil"] else "",
        "%d en rupture" % articles["enRupture"] if articles["enRupture"] else "") if p) or "Tous en stock, au-dessus du seuil"
    habilitations = calcule["habilitations"]
    ligne_techniciens = None if habilitations is None else " · ".join(p for p in (
        pluriel(habilitations["suivies"], "habilitation suivie", "habilitations suivies"),
        "%d à renouveler" % habilitations["aRenouveler"] if habilitations["aRenouveler"] else "",
        pluriel(habilitations["echues"], "échue", "échues") if habilitations["echues"] else "") if p)
    return {"nombres": nombres, "liens": liens, "phrase": ", ".join(l[0] for l in liens[:-1]) + " et " + liens[-1][0],
            "cloturees": len(clotures), "reperes": [e["repere"] for e in machines[:3] if par_machine.get(e["id"], 0) > 0],
            "premiere_panne": (pannes[0][2], pluriel(pannes[0][3], "cas", "cas")), "dernieres": [o["id"] for o in clotures[:6]],
            "pannes": [(p[0], [p[2], p[1]], pluriel(p[3], "cas", "cas")) for p in pannes[:6]],
            "ligne_articles": ligne_articles, "ligne_techniciens": ligne_techniciens}


def compteurs_attendus(journal, ordres):
    """Compteurs du suivi du wiki, recalculés ici à partir des lignes (définitions des vues du journal)."""
    numero = lambda e: int(re.sub(r"\D", "", e["id"]) or 0)  # noqa: E731
    ingestions = [e for e in journal if e["nature"] == "ingestion" and e["ot_id"]]
    # « En échec » : OT sans autre entrée que rejetée ou refusée, dont la dernière est « refusée » (vue du journal).
    vivants = {e["ot_id"] for e in ingestions if e["statut"] not in ("rejetée", "refusée")}
    dernieres = {}
    for e in ingestions:
        if e["statut"] in ("rejetée", "refusée") and e["ot_id"] not in vivants:
            if e["ot_id"] not in dernieres or numero(e) > numero(dernieres[e["ot_id"]]):
                dernieres[e["ot_id"]] = e
    echecs = [ot for ot, e in dernieres.items() if e["statut"] == "refusée"]
    return {
        "a-valider": sum(1 for e in journal if e["statut"] == "à valider"),
        "contradictions": sum(1 for e in journal if e["statut"] == "validée"
                              for c in json.loads(e["contradictions"] or "[]") if c.get("statut") == "ouverte"),
        "file": sum(1 for e in ingestions if e["statut"] in ("en file", "à refaire")),
        "echecs": len(echecs),
    }


def phrase_attendue(contenu):
    """Phrase du balisage → ce que l'écran montre : texte sans citations, liens vers les pages qui s'affichent, titres
    inconnus en texte, OT cités (petits numéros dans l'ordre de la phrase, sans doublon)."""
    titres = [titre.strip() for titre in MOTIF_LIEN.findall(contenu)]
    texte = plat(MOTIF_LIEN.sub(lambda m: m.group(1).strip(), MOTIF_CITATION.sub(" ", contenu)))
    return {"texte": texte, "ot": citations(contenu),
            "liens": [[plat(titre), "#/wiki/" + encoder(RESOLUTIONS[titre])] for titre in titres if titre in RESOLUTIONS],
            "absents": [plat(titre) for titre in titres if titre not in RESOLUTIONS]}


def ordre_des_numeros(entite, articles):
    """OT dans l'ordre attendu de leurs petits numéros sur la page (D113, D118 : un seul jeu, l'ordre d'apparition, un OT
    à sa première place), recalculé ici : « À trancher » (la phrase, puis les OT qui l'observent, sinon l'OT de l'entrée),
    les textes d'avant les articles (« En bref » d'une machine ; tous ceux d'une page sans articles), les OT montrés des
    articles consommés ou changés (`articles` : CalculWiki.ot_des_articles, dans l'ordre de la page), puis les autres
    textes. `entite` : Wiki.entite (ses contradictions)."""
    vus = []

    def voir(ots):
        for ot in ots:
            if ot not in vus:
                vus.append(ot)

    for contradiction in entite["aTrancher"]:
        voir(citations(contradiction.get("phrase")))
        observes = [ot for ot in (contradiction.get("ot") or []) if ot]
        voir(observes or [o for o in [contradiction.get("otSource")] if o])
    rubriques = (entite.get("textes") or {}).get("rubriques") or []
    avant = [r for r in rubriques if r["nom"] == "En bref" or entite["type"] != "machine"]
    for rubrique in avant:
        for phrase in rubrique["phrases"]:
            voir(citations(phrase))
    for article in articles:
        voir(article["ot"])
    for rubrique in rubriques:
        if rubrique not in avant:
            for phrase in rubrique["phrases"]:
                voir(citations(phrase))
    return vus


def rubriques_du_texte(texte):
    """[(rubrique, [phrases])] du balisage stocké, dans l'ordre du texte."""
    rubriques = []
    for ligne in texte.splitlines():
        if ligne.startswith("## "):
            rubriques.append((ligne[3:].strip(), []))
        elif ligne.startswith("- "):
            rubriques[-1][1].append(ligne[2:].strip())
    return rubriques


class CasWiki(CasNavigateur):
    """Outils communs : ouvrir la démo dans un contexte neuf (profil, taille, thème), poser la base d'essai, aller à
    une route, lire une page."""

    def ouvrir(self, profil="responsable", largeur=1280, hauteur=800, theme=None, telephone=False, base=False):
        self.contexte.close()
        options = {"locale": "fr-FR", "viewport": {"width": largeur, "height": hauteur}}
        if telephone:
            options.update(is_mobile=True, has_touch=True)
        self.contexte = self.navigateur.new_context(**options)
        self.contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        self.contexte.clock.set_fixed_time(HEURE_FIXE)
        if theme:
            self.contexte.add_init_script("try { localStorage.setItem('prevo.theme', %s); } catch (e) { /* vide */ }"
                                          % json.dumps(theme))
        nom, technicien = PROFILS[profil]
        preregler_profil(self.contexte, profil, nom, technicien)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        if base:
            self.poser_base()
        return self.page

    def poser_base(self):
        self.page.evaluate(BASE_JS, [PAGES, JOURNAL, ORDRE_PIEGE, TEMPS_PIEGE])

    def aller(self, route, attendre):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(attendre, state="attached")

    def aller_page(self, equipement):
        self.aller("#/wiki/" + equipement, '.wiki-page[data-equipement="%s"] #wiki-interventions' % equipement)

    def aller_entite(self, identifiant):
        """Va à la page d'une entité et attend qu'elle s'affiche, ou « Page introuvable » pour cet identifiant."""
        self.page.evaluate("(route) => { location.hash = route; }", "#/wiki/" + encoder(identifiant))
        self.page.wait_for_function("""(id) => document.querySelector('.wiki-page[data-page="' + CSS.escape(id) + '"] .wiki-page-grille')
          || Array.from(document.querySelectorAll('.wiki-introuvable .vide')).some((e) => e.textContent.includes('« ' + id + ' »'))""",
                                    arg=identifiant)

    def lire(self, identifiant):
        self.aller_entite(identifiant)
        return self.page.evaluate(ENTITE_JS)

    def entite(self, identifiant, profil):
        return self.page.evaluate("([id, p]) => Wiki.entite(id, { profil: p })", [identifiant, profil])

    def aller_accueil(self):
        self.aller("#/wiki", "#wiki-accueil")

    def chercher_accueil(self, texte):
        """Tape `texte` dans la recherche de l'accueil (résultats vidés d'abord) et attend les résultats."""
        self.page.evaluate("() => { const z = document.querySelector('#wiki-trouves'); z.textContent = ''; z.hidden = true; }")
        self.page.fill("#wiki-champ-accueil", texte)
        self.page.wait_for_selector("#wiki-trouves:not([hidden]) .wiki-trouves-titre")

    def attendre_resultats(self, racine):
        self.page.wait_for_selector("%s .wiki-portee, %s .wiki-rien" % (racine, racine))

    def chercher(self, racine, texte):
        """Tape `texte` dans le champ de recherche sous `racine` (zone des résultats vidée d'abord) et attend les résultats."""
        self.page.evaluate("(r) => { document.querySelector(r + ' .wiki-resultats').textContent = ''; }", racine)
        self.page.fill(racine + " .wiki-recherche-champ", texte)
        self.attendre_resultats(racine)

    def verifier_resultats(self, racine, texte, equipement, demandeur=False, montres=5):
        """Résultats affichés sous `racine` = Wiki.rechercher(texte, { equipementId }) : portées non vides dans
        l'ordre, tous les résultats, `montres` montrés (5 ; 3 dans une DI) puis cachés, liens selon le profil."""
        attendus = self.page.evaluate(ATTENDU_RECHERCHE_JS, [texte, equipement])
        lus = self.page.evaluate(RESULTATS_JS, racine)
        self.assertTrue(attendus, "la recherche « %s » devrait trouver quelque chose" % texte)
        self.assertEqual([(l["portee"], l["libelle"], l["ids"], l["types"]) for l in lus],
                         [(a["portee"], a["libelle"], a["ids"], a["types"]) for a in attendus])
        for bloc in lus:
            self.assertEqual(bloc["caches"], [rang >= montres for rang in range(len(bloc["ids"]))])
            reste = len(bloc["ids"]) - montres
            self.assertEqual(bloc["bouton"], None if reste <= 0 else (
                "Voir les %d autres résultats" % reste if reste > 1 else "Voir l'autre résultat"))
            if demandeur:
                self.assertEqual(bloc["liensOt"], 0)
        return lus

    def verifier_sans_piege(self):
        self.assertEqual(self.page.locator("#contenu img, #contenu script").count(), 0)
        self.assertIsNone(self.page.evaluate("window.__piege === undefined ? null : window.__piege"))

    def tables(self):
        return self.page.evaluate("""() => Object.fromEntries(['equipements', 'articles', 'techniciens', 'ordres_travail',
          'codes_defaillance', 'wiki_pages', 'wiki_journal', 'localisations'].map((t) => [t, Donnees.lignes(t)]))""")

    def calcul(self):
        """Calcul Python indépendant (tests/calcul_wiki.py) sur les tables affichées, réécrites en CSV."""
        tables = self.page.evaluate(TABLES_JS, list(CALCUL_TABLES))
        return CalculWiki({nom: table_csv(sorted({c for ligne in lignes for c in ligne}), lignes) if lignes else ""
                           for nom, lignes in tables.items()})


# ---------------------------------------------------------------------------
# #/wiki : accueil de l'encyclopédie (refonte 2, §20.12, T136)
# ---------------------------------------------------------------------------

class TestAccueil(CasWiki):

    def test_accueil_pour_les_trois_profils(self):
        for profil in ("demandeur", "technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                self.aller_accueil()
                lu = page.evaluate(ACCUEIL_JS)
                tables = self.tables()
                attendu = accueil_attendu(tables, profil, self.calcul())
                donnees = page.evaluate("(p) => Wiki.accueilEncyclopedie({ profil: p })", profil)
                # Grande tuile : pastille, phrase-résumé (le titre de l'écran), chaque nombre en lien vers sa liste
                self.assertEqual(lu["pastille"], "Ce que l'atelier sait")
                self.assertEqual(lu["h1"], attendu["phrase"])
                self.assertEqual(lu["phrase"], attendu["liens"])
                self.assertEqual(attendu["phrase"].startswith("31 machines, "), True)
                self.assertEqual("technicien" in attendu["phrase"], profil != "demandeur")
                # Les nombres sont ceux de Wiki.accueilEncyclopedie (et du calcul fait ici)
                self.assertEqual({cle: donnees["nombres"][CLES_NOMBRES[cle]] for cle in attendu["nombres"]}, attendu["nombres"])
                self.assertEqual(donnees["nombres"]["cloturees"], attendu["cloturees"])
                self.assertEqual(lu["tireDe"], "Tiré de %s. Tout est relié : chaque nom mène à sa page."
                                 % pluriel(attendu["cloturees"], "intervention clôturée", "interventions clôturées"))
                self.assertEqual(lu["champ"], 1)
                # Briques : icône et couleur du type, nombre, ligne utile, lien vers la liste ; pas de techniciens au demandeur
                types = [t for t in ("machine", "panne", "article", "technicien", "savoir-faire") if profil != "demandeur" or t != "technicien"]
                self.assertEqual([b["type"] for b in lu["briques"]], types)
                self.assertEqual([b["href"] for b in lu["briques"]], ["#/wiki/" + LISTE_DU_TYPE[t] for t in types])
                self.assertEqual([b["nombre"] for b in lu["briques"]], [str(attendu["nombres"][LISTE_DU_TYPE[t]]) for t in types])
                self.assertTrue(all("wiki-t-" + b["type"] in b["pastille"] for b in lu["briques"]))
                lignes = {b["type"]: b["ligne"] for b in lu["briques"]}
                self.assertEqual(lignes["machine"], "Le plus d'interventions : " + ", ".join(attendu["reperes"]))
                self.assertEqual(lignes["panne"], "La plus fréquente : %s (%s)" % attendu["premiere_panne"])
                # Articles et Techniciens : comptes du calcul Python (relecture de T136, m5)
                self.assertEqual(lignes["article"], attendu["ligne_articles"])
                self.assertEqual(lignes.get("technicien"), attendu["ligne_techniciens"])
                # « : » et « · » collés au mot d'avant par une espace insécable (relecture de T136, m1 et m2)
                bruts = {b["type"]: b["brut"] for b in lu["briques"]}
                self.assertIn("interventions\u00a0: ", bruts["machine"])
                self.assertIn("fréquente\u00a0: ", bruts["panne"])
                if profil != "demandeur":
                    self.assertNotIn(" ·", bruts["technicien"])
                    self.assertIn("\u00a0·", bruts["technicien"])
                # Suivi du wiki : responsable seulement
                self.assertEqual(lu["suivi"], 1 if profil == "responsable" else 0)
                self.assertEqual(page.locator('#contenu a[href^="#/wiki-journal"]').count(), 5 if profil == "responsable" else 0)
                # Dernières interventions : les six plus récentes clôturées ; titre en lien, sauf pour le demandeur
                self.assertEqual([d["id"] for d in lu["dernieres"]], attendu["dernieres"])
                self.assertEqual([d["id"] for d in donnees["dernieres"][:6]], attendu["dernieres"])
                ordres = {o["id"]: o for o in tables["ordres_travail"]}
                for ligne in lu["dernieres"]:
                    ot = ordres[ligne["id"]]
                    self.assertEqual(ligne["titre"], [ot["titre"], None, "SPAN"] if profil == "demandeur"
                                     else [ot["titre"], "#/wiki/" + encoder(ot["id"]), "A"])
                    self.assertEqual(ligne["liens"][0][1], "#/wiki/" + encoder(ot["equipement_id"]))
                self.assertEqual(lu["toutes"], ([] if profil == "demandeur" else [["Toutes", "#/wiki/interventions"]])
                                 + [["Toutes", "#/wiki/pannes"]])
                # Pannes les plus fréquentes : six (maquette, relecture de T136), par nombre de cas, liens encodés
                self.assertEqual(len(lu["pannes"]), 6)
                self.assertEqual([(p["id"], p["lien"], p["cas"]) for p in lu["pannes"]], attendu["pannes"])
                self.assertEqual(lu["pannes"][0]["largeur"], "100%")
                self.verifier_sans_piege()

    def test_texte_d_exemple_court_au_telephone(self):
        """Relecture de T136 (m9) : à 375 px, le texte d'exemple tient dans son champ (accueil, filtre des articles)."""
        for profil, attendu in (("demandeur", "Machine, panne, article…"), ("technicien", "Machine, panne, OT…")):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, largeur=375, hauteur=812, telephone=True)
                for selecteur in ("#wiki-champ-accueil", "#wiki-filtre-texte"):
                    if selecteur == "#wiki-champ-accueil":
                        self.aller_accueil()
                        self.assertEqual(page.evaluate(ACCUEIL_JS)["exemple"], attendu)
                    else:
                        self.aller("#/wiki/articles", "#wiki-filtre-texte")
                        self.assertEqual(page.get_attribute("#wiki-filtre-texte", "placeholder"), "Désignation, référence…")
                    tient = page.evaluate("""(s) => { const champ = document.querySelector(s);
                      const mesure = document.createElement('span'); const style = getComputedStyle(champ);
                      mesure.style.font = style.font; mesure.style.whiteSpace = 'pre'; mesure.textContent = champ.placeholder;
                      document.body.appendChild(mesure); const largeur = mesure.getBoundingClientRect().width; mesure.remove();
                      return largeur <= champ.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight); }""", selecteur)
                    self.assertTrue(tient, selecteur)
        page = self.ouvrir("technicien", largeur=1440, hauteur=900)
        self.aller_accueil()
        self.assertEqual(page.evaluate(ACCUEIL_JS)["exemple"], "Chercher une machine, une panne, un article, une intervention…")

    def test_suivi_du_wiki_au_responsable(self):
        page = self.ouvrir("responsable", base=True)
        self.aller_accueil()
        lu = page.evaluate(ACCUEIL_JS)
        attendus = compteurs_attendus(page.evaluate("Donnees.lignes('wiki_journal')"), page.evaluate("Donnees.lignes('ordres_travail')"))
        # « En échec » : 1 — OT-2026-0072 a aussi une entrée « en file » (relancé) : il n'est plus en échec, comme dans la
        # vue « En échec » du journal où mène la tuile.
        self.assertEqual((attendus["a-valider"], attendus["contradictions"], attendus["echecs"]), (2, 3, 1))
        self.assertEqual([(m["vue"], m["libelle"], m["href"], m["nombre"]) for m in lu["minis"]], [
            ("a-valider", "à valider", "#/wiki-journal?vue=a-valider", "2"),
            ("contradictions", "à trancher", "#/wiki-journal?vue=contradictions", "3"),
            ("echecs", "en échec", "#/wiki-journal?vue=echecs", "1")])
        self.assertEqual(page.evaluate("Wiki.accueilEncyclopedie({ profil: 'responsable' }).suivi"),
                         {"aValider": 2, "aTrancher": 3, "enEchec": 1})
        self.assertEqual(self.calcul().suivi(), {"aValider": 2, "aTrancher": 3, "enEchec": 1})
        # Seules les actions en attente ressortent : à valider en ambre, à trancher et en échec en rouge
        self.assertEqual([m["classe"] for m in lu["minis"]], ["wiki-mini attente", "wiki-mini urgent", "wiki-mini urgent"])
        # « Traiter la file » et le journal restent au responsable, depuis le suivi
        self.assertEqual(page.evaluate("Wiki.file().length"), attendus["file"])
        self.assertEqual(lu["actions"], [["Traiter la file (%d)" % attendus["file"], "#/wiki-journal?vue=file"],
                                         ["Journal du wiki", "#/wiki-journal"]])
        page.click('.wiki-mini[data-suivi="a-valider"]')
        page.wait_for_function("location.hash === '#/wiki-journal?vue=a-valider'")
        page.wait_for_selector(".wiki-journal", state="attached")
        self.aller_accueil()
        page.click("#wiki-traiter-file")
        page.wait_for_function("location.hash === '#/wiki-journal?vue=file'")
        page.wait_for_selector(".wiki-journal", state="attached")

    def test_suivi_discret_a_zero_sur_la_demo(self):
        page = self.ouvrir("responsable")
        self.assertEqual(page.evaluate("Donnees.lignes('wiki_journal').length"), 0)
        self.aller_accueil()
        lu = page.evaluate(ACCUEIL_JS)
        self.assertEqual([(m["vue"], m["nombre"], m["classe"]) for m in lu["minis"]],
                         [("a-valider", "0", "wiki-mini"), ("contradictions", "0", "wiki-mini"), ("echecs", "0", "wiki-mini")])
        couleurs = page.evaluate("""() => ['.wiki-mini-nombre', '.wiki-brique-nombre'].map((s) => getComputedStyle(document.querySelector(s)).color)""")
        self.assertNotEqual(couleurs[0], couleurs[1])         # à zéro, le nombre est discret (pas la couleur forte)

    def test_chaque_nombre_et_chaque_brique_mene_a_sa_liste(self):
        for profil in ("demandeur", "responsable"):
            page = self.ouvrir(profil, base=True)
            listes = [l for l in ("machines", "pannes", "articles", "techniciens", "savoir-faire") if profil != "demandeur" or l != "techniciens"]
            for liste in listes:
                for selecteur in ('#wiki-phrase-resume a[data-liste="%s"]' % liste, '.wiki-brique[href="#/wiki/%s"]' % liste):
                    with self.subTest(profil=profil, selecteur=selecteur):
                        self.aller_accueil()
                        page.click(selecteur)
                        page.wait_for_selector('.wiki-liste-entites[data-liste="%s"]' % liste)
                        self.assertEqual(page.evaluate("location.hash"), "#/wiki/" + liste)
                        self.assertEqual(page.evaluate("document.querySelector('#contenu h1').firstChild.textContent.trim()"), LISTES[liste])

    def test_lien_d_une_panne_encode_jusqu_a_sa_page(self):
        """Code symptôme qui change à l'encodage (« / », espace, accent, « & ») et libellé piégé : la panne la plus fréquente
        mène à sa page depuis la brique, les barres, la liste et une ligne des dernières interventions."""
        page = self.ouvrir("technicien")
        code = page.evaluate(PANNE_PIEGEE_JS, [CODE_PIEGE, LIBELLE_PIEGE])
        identifiant = "PANNE-" + encoder(CODE_PIEGE)
        self.assertEqual(identifiant, "PANNE-S%2F1%20%C3%A9%26")
        self.assertEqual(page.evaluate("Wiki.listeEntites('panne')[0].id"), identifiant)
        self.aller_accueil()
        lu = page.evaluate(ACCUEIL_JS)
        self.assertEqual(lu["pannes"][0]["lien"], [LIBELLE_PIEGE, lien_panne(CODE_PIEGE)])
        self.assertIn("La plus fréquente : " + LIBELLE_PIEGE, [b["ligne"] for b in lu["briques"] if b["type"] == "panne"][0])
        derniere = [d for d in lu["dernieres"] if d["sous"].endswith(LIBELLE_PIEGE)]
        if derniere:
            self.assertEqual(derniere[0]["liens"][-1], [LIBELLE_PIEGE, lien_panne(CODE_PIEGE)])
        self.verifier_sans_piege()
        page.click("#wiki-pannes-frequentes li:first-child a")
        page.wait_for_selector('.wiki-entite[data-page="%s"]' % identifiant)
        self.assertEqual(page.evaluate("document.querySelector('#contenu h1').textContent"), LIBELLE_PIEGE)
        faits = page.evaluate(FAITS_JS)
        self.assertEqual(faits[0], ["Code", CODE_PIEGE, None])
        self.assertEqual(faits[1][:2], ["Cas", str(code["cas"])])
        # Les interventions de la page mènent à la même panne (identifiant encodé, jamais le code brut)
        self.assertIn(lien_panne(CODE_PIEGE), page.evaluate("Array.from(document.querySelectorAll('#wiki-interventions a')).map((a) => a.getAttribute('href'))"))
        self.verifier_sans_piege()
        self.aller("#/wiki/pannes", ".wiki-liste-entites[data-liste=pannes]")
        self.assertEqual(page.evaluate("""() => { const a = document.querySelector('.wiki-ligne .wiki-ligne-corps > a');
          return [a.textContent, a.getAttribute('href')]; }"""), [LIBELLE_PIEGE, lien_panne(CODE_PIEGE)])
        page.click(".wiki-ligne .wiki-ligne-corps > a")
        page.wait_for_selector('.wiki-entite[data-page="%s"]' % identifiant)
        self.verifier_sans_piege()

    def test_titres_pieges_restent_du_texte(self):
        page = self.ouvrir("responsable", base=True)
        page.evaluate(ECRIRE_JS, ["equipements", "EQ-0001", {"designation": PIEGE_MACHINE}])
        page.evaluate(ECRIRE_JS, ["techniciens", "TEC-0001", {"nom": PIEGE_NOM}])
        code = page.evaluate("Wiki.listeEntites('panne')[0].code")
        page.evaluate("""([code, libelle]) => Donnees.modifier('codes_defaillance', (lignes) => {
          lignes.filter((l) => l.famille === 'symptôme' && l.code === code).forEach((l) => { l.libelle = libelle; }); return true; },
          { action: 'test des écrans du wiki' })""", [code, LIBELLE_PIEGE])
        self.aller_accueil()
        lu = page.evaluate(ACCUEIL_JS)
        self.assertEqual(lu["pannes"][0]["lien"][0], LIBELLE_PIEGE)
        self.assertEqual([b["ligne"] for b in lu["briques"] if b["type"] == "panne"][0].split(" (")[0], "La plus fréquente : " + LIBELLE_PIEGE)
        self.verifier_sans_piege()
        for requete, type_, ident, titre in (("CP-01", "machine", "EQ-0001", "CP-01 — " + PIEGE_MACHINE),
                                             ("Moreau", "technicien", "TEC-0001", None), ("garniture", "savoir-faire", "WP-0003", None)):
            self.chercher_accueil(requete)
            groupes = {g["type"]: g for g in page.evaluate(TROUVES_JS)}
            self.assertIn(ident, groupes[type_]["ids"], requete)
            if titre:
                self.assertEqual(groupes[type_]["textes"][groupes[type_]["ids"].index(ident)], titre)
            self.verifier_sans_piege()
        nom = page.evaluate("Wiki.entite('TEC-0001').titre")
        self.assertTrue(nom.endswith(PIEGE_NOM))
        for route, selecteur, attendu in (("#/wiki/machines", 'li[data-id="EQ-0001"] .wiki-ligne-corps > a', "CP-01 — " + PIEGE_MACHINE),
                                          ("#/wiki/techniciens", 'li[data-id="TEC-0001"] h2', nom),
                                          ("#/wiki/savoir-faire", 'li[data-id="WP-0006"] .wiki-ligne-corps > a', TITRE_PIEGE),
                                          ("#/wiki/pannes", ".wiki-ligne .wiki-ligne-corps > a", LIBELLE_PIEGE),
                                          ("#/wiki/TEC-0001", "#contenu h1", nom), ("#/wiki/EQ-0001", "#contenu h1", "CP-01 — " + PIEGE_MACHINE)):
            with self.subTest(route=route):
                self.aller(route, selecteur)
                self.assertEqual(page.evaluate("(s) => document.querySelector(s).textContent", selecteur), attendu)
                self.verifier_sans_piege()


# ---------------------------------------------------------------------------
# #/wiki/<liste> : les six listes
# ---------------------------------------------------------------------------

class TestListes(CasWiki):

    def lire_liste(self, liste, tout=False):
        self.aller("#/wiki/" + liste, '.wiki-liste-entites[data-liste="%s"]' % liste)
        if tout and self.page.locator(".wiki-liste-entites .wiki-voir-autres").count():
            self.page.click(".wiki-liste-entites .wiki-voir-autres")
            self.page.wait_for_selector(".wiki-liste-entites .wiki-voir-autres", state="detached")
        return self.page.evaluate(LISTE_JS)

    def test_six_listes_pour_les_trois_profils(self):
        for profil in ("demandeur", "technicien", "responsable"):
            page = self.ouvrir(profil, base=True)
            calcul = self.calcul()
            tables = self.tables()
            francais = lambda paires: page.evaluate(TRIER_TITRES_JS, paires)  # noqa: E731
            attendus = {
                "machines": sorted(e["id"] for e in tables["equipements"]),
                "pannes": [p[0] for p in pannes_attendues(tables)],
                "articles": francais([[a["id"], titre_article(a)] for a in tables["articles"]]),
                "techniciens": francais([[t["id"], (t["prenom"] + " " + t["nom"]).strip()] for t in tables["techniciens"]]),
                "savoir-faire": francais([[p["id"], p["titre"]] for p in tables["wiki_pages"]
                                          if p["type"] == "savoir-faire" and p["statut"] != "archivée"]),
                # Ordre des interventions : celui du calcul Python indépendant (relecture de T136, m5)
                "interventions": [e["id"] for e in calcul.liste_entites("intervention", "responsable", MAINTENANT)],
            }
            self.assertEqual(sorted(attendus["savoir-faire"]), SAVOIR_FAIRE_ACTIFS)
            for liste, ids in attendus.items():
                with self.subTest(profil=profil, liste=liste):
                    lu = self.lire_liste(liste, tout=True)
                    self.assertEqual(lu["titre"], LISTES[liste])
                    self.assertEqual(lu["fil"], [["Wiki", "#/wiki"], [LISTES[liste], None]])
                    if profil == "demandeur" and liste in ("techniciens", "interventions"):
                        self.assertEqual(lu["reserve"], "Réservé aux techniciens et au responsable")
                        self.assertEqual((lu["nombre"], lu["lignes"]), (None, []))
                        continue
                    self.assertIsNone(lu["reserve"])
                    self.assertEqual(lu["nombre"], str(len(ids)))
                    lus = [l[0] for l in lu["lignes"]]
                    if liste == "machines":
                        self.assertEqual(sorted(lus), ids)                  # ordre : test des lieux ci-dessous
                    else:
                        self.assertEqual(lus, ids)
                    # Chaque élément mène à sa page (identifiant encodé), et rien d'autre que ce que le profil voit
                    self.assertEqual([l[1] for l in lu["lignes"]], ["#/wiki/" + encoder(i) for i in lus])
                    if profil == "demandeur":
                        self.assertEqual([h for h in lu["liens"] if h.startswith(("#/wiki/TEC-", "#/wiki/OT-"))], [])
                    self.verifier_sans_piege()

    def test_machines_par_lieu_et_sous_ensembles(self):
        page = self.ouvrir("demandeur")
        lu = self.lire_liste("machines")
        tables = self.tables()
        equipements = {e["id"]: e for e in tables["equipements"]}
        lieux = {l["id"]: l for l in tables["localisations"]}

        def chemin(lieu_id):
            noms = []
            while lieu_id in lieux:
                noms.insert(0, lieux[lieu_id]["libelle"])
                lieu_id = lieux[lieu_id]["parent_id"]
            return noms
        groupes = page.evaluate("""() => Array.from(document.querySelectorAll('.wiki-groupe-lieu')).map((g) => ({ lieu: g.dataset.lieu,
          titre: g.querySelector('h2').textContent, lignes: Array.from(g.querySelectorAll('li')).map((li) => [li.dataset.id,
          Number(li.style.getPropertyValue('--profondeur')), li.classList.contains('enfant')]) }))""")
        self.assertGreater(len(groupes), 3)
        racines = {tuple(chemin(e["localisation_id"]))[:1] for e in tables["equipements"]}
        self.assertEqual(len(racines), 1)                                  # un seul site : sa racine n'est pas répétée
        for groupe in groupes:
            self.assertEqual(groupe["titre"], " › ".join(groupe["lieu"].split(" › ")[1:]))
            for rang, (ident, profondeur, enfant) in enumerate(groupe["lignes"]):
                parent = equipements[ident]["parent_id"]
                self.assertEqual(enfant, profondeur > 0)
                if profondeur == 0:
                    self.assertEqual(" › ".join(chemin(equipements[ident]["localisation_id"])), groupe["lieu"], ident)
                    self.assertTrue(not parent or parent not in equipements, ident)
                else:
                    # Sous-ensemble : juste sous sa machine (la ligne la plus proche au-dessus, d'une profondeur de moins)
                    avant = [l for l in groupe["lignes"][:rang] if l[1] == profondeur - 1][-1]
                    self.assertEqual(avant[0], parent, ident)
        sous = [i for g in groupes for i, p, _ in g["lignes"] if p > 0]
        self.assertEqual(sorted(sous), sorted(e["id"] for e in tables["equipements"] if e["parent_id"] in equipements))
        self.assertGreater(len(sous), 3)
        self.assertEqual(lu["nombre"], str(len(equipements)))

    def test_pannes_par_nombre_de_cas(self):
        page = self.ouvrir("technicien")
        lu = self.lire_liste("pannes")
        attendues = pannes_attendues(self.tables())
        self.assertEqual([l[:3] for l in lu["lignes"]], [[i, lien, libelle] for i, lien, libelle, _ in attendues])
        self.assertEqual(page.evaluate("Array.from(document.querySelectorAll('.wiki-ligne-droite')).map((e) => e.textContent)"),
                         [pluriel(cas, "cas", "cas") for *_, cas in attendues])

    def test_articles_filtrables_avec_l_etat_du_stock(self):
        page = self.ouvrir("technicien")
        self.lire_liste("articles")
        # État et stock : ceux du calcul Python indépendant, qui rejoue les mouvements (relecture de T136, m5)
        articles = {a["articleId"]: a for a in self.calcul().liste_entites("article", "technicien", MAINTENANT)}
        lignes = page.evaluate(ARTICLES_JS)
        self.assertEqual(len(lignes), 52)
        classes = {"en stock": "ok", "sous le seuil": "attention", "rupture": "ko"}
        for ident, _, etat, classe, nombre in lignes:
            article = articles[ident]
            self.assertEqual(plat(etat), plat("%s%s · %s" % (nombre_fr(article["stock"]), " " + article["unite"] if article["unite"] else "",
                                                              article["etat"])), ident)
            self.assertIn(classes[article["etat"]], classe.split())
            self.assertEqual(nombre, str(article["interventions"]))
        self.assertGreater(sum(1 for a in articles.values() if a["etat"] != "en stock"), 0)
        self.assertNotIn("Prix", page.inner_text("#wiki-articles thead"))      # le prix est sur la page d'un article
        # Filtre : texte (désignation, référence, emplacement), puis état
        page.fill("#wiki-filtre-texte", "roulement")
        attendus = sorted(i for i, a in articles.items() if "roulement" in sans_accents(" ".join([a["titre"], a["reference"], a["emplacement"]])))
        page.wait_for_function("(n) => document.querySelectorAll('#wiki-articles tbody tr').length === n", arg=len(attendus))
        self.assertEqual(sorted(l[0] for l in page.evaluate(ARTICLES_JS)), attendus)
        self.assertEqual(page.inner_text(".wiki-filtre-compte"), "%d articles sur 52" % len(attendus))
        page.fill("#wiki-filtre-texte", "")
        page.select_option("#wiki-filtre-etat", "sous le seuil")
        attendus = sorted(i for i, a in articles.items() if a["etat"] == "sous le seuil")
        page.wait_for_function("(n) => document.querySelectorAll('#wiki-articles tbody tr').length === n", arg=len(attendus))
        self.assertEqual(sorted(l[0] for l in page.evaluate(ARTICLES_JS)), attendus)

    def test_articles_et_interventions_en_cartes_au_telephone(self):
        """Au téléphone : articles en cartes ; interventions, seules les 40 premières cartes créées, les autres au clic."""
        page = self.ouvrir("technicien", largeur=375, hauteur=812, telephone=True)
        self.lire_liste("articles")
        self.assertEqual(page.locator("#wiki-articles .liste-cartes > li > a").count(), 52)
        page.fill("#wiki-filtre-texte", "courroie")
        page.wait_for_function("document.querySelectorAll('#wiki-articles .liste-cartes > li').length < 52")
        self.assertTrue(all("ourroie" in t for t in page.eval_on_selector_all("#wiki-articles .carte-titre", "e => e.map((x) => x.textContent)")))
        self.lire_liste("interventions")
        ordre = [e["id"] for e in self.calcul().liste_entites("intervention", "technicien", MAINTENANT)]
        total = len(ordre)
        self.assertGreater(total, 40)
        cartes = lambda: page.eval_on_selector_all(".wiki-carte-intervention", "e => e.map((x) => x.dataset.id)")  # noqa: E731
        self.assertEqual(cartes(), ordre[:40])                               # créées : les 40 premières seulement
        self.assertEqual(page.locator(".wiki-carte-intervention[hidden]").count(), 0)
        bouton = page.locator(".wiki-voir-autres")
        self.assertEqual(bouton.inner_text().strip(), "Voir les %d autres interventions" % (total - 40))
        bouton.click()
        self.assertEqual(cartes(), ordre)
        self.assertEqual(page.locator(".wiki-voir-autres").count(), 0)

    def test_interventions_ouvertes_en_tete_avec_leur_statut(self):
        """PC : les 100 premières lignes, « Voir les n autres » ajoute les autres ; ordre et statut du calcul Python."""
        page = self.ouvrir("responsable")
        lu = self.lire_liste("interventions")
        attendues = self.calcul().liste_entites("intervention", "responsable", MAINTENANT)
        total = len(attendues)
        self.assertGreater(total, 100)
        lignes = page.evaluate(INTERVENTIONS_JS)
        self.assertEqual([l["id"] for l in lignes], [e["id"] for e in attendues[:100]])
        self.assertEqual(lu["nombre"], str(total))
        self.assertEqual(lu["bouton"], "Voir les %d autres interventions" % (total - 100))
        page.click(".wiki-liste-entites .wiki-voir-autres")
        page.wait_for_function("(n) => document.querySelectorAll('#wiki-interventions tbody tr').length === n", arg=total)
        lignes = page.evaluate(INTERVENTIONS_JS)
        self.assertEqual([l["id"] for l in lignes], [e["id"] for e in attendues])
        self.assertEqual(page.locator(".wiki-liste-entites .wiki-voir-autres").count(), 0)
        statuts = [l["statut"] for l in lignes]
        self.assertEqual(statuts, [e["statut"] for e in attendues])                     # le statut sur chaque ligne
        ouverts = [s in OUVERTS for s in statuts]
        self.assertTrue(any(ouverts) and not all(ouverts))
        self.assertEqual(ouverts, sorted(ouverts, reverse=True))                         # les ouverts en tête
        self.assertEqual(statuts[0], "En cours")
        tables = self.tables()
        ordres = {o["id"]: o for o in tables["ordres_travail"]}
        fermes = [l["id"] for l in lignes if l["statut"] not in OUVERTS]
        self.assertEqual(fermes, sorted(fermes, key=lambda i: (date_de_l_ot(ordres[i]), i), reverse=True))
        cas = set(compter_cas(tables["ordres_travail"]))
        for ligne in lignes:
            ot = ordres[ligne["id"]]
            self.assertEqual(ligne["lien"], "#/wiki/" + encoder(ot["id"]))
            self.assertEqual(ligne["machine"], "#/wiki/" + encoder(ot["equipement_id"]))
            code = ot["symptome_code"].strip()
            self.assertEqual(ligne["panne"], lien_panne(code) if code in cas else None, ot["id"])

    def test_tri_des_interventions_sur_toute_la_liste(self):
        """Relecture de T137 (m5) : sur PC, trier le tableau des interventions ordonne TOUTE la liste (plus de 100 OT dans la
        démo), puis n'en crée que les 100 premières lignes ; « Voir les n autres » ajoute la suite dans le même ordre ; un
        tri après l'ouverture garde toutes les lignes. Tri stable (à égalité, l'ordre d'avant), comme UI.tableau."""
        page = self.ouvrir("responsable", largeur=1440, hauteur=900)
        self.lire_liste("interventions")
        attendues = self.calcul().liste_entites("intervention", "responsable", MAINTENANT)
        total = len(attendues)
        self.assertGreater(total, 100)
        dates = {e["id"]: e["date"] for e in attendues}
        self.assertTrue(all(dates.values()))
        courant = [e["id"] for e in attendues]
        numero = lambda i: tuple(int(n) for n in re.findall(r"\d+", i))  # noqa: E731

        def trier(cle):
            page.click('#wiki-interventions th .tri[data-cle="%s"]' % cle)
            return ([l["id"] for l in page.evaluate(INTERVENTIONS_JS)],
                    page.evaluate("() => Array.from(document.querySelectorAll('#wiki-interventions th[aria-sort]')).map((th) => [th.textContent.trim(), th.getAttribute('aria-sort')])"))
        # N° croissant, puis décroissant : les 100 premiers de toute la liste (pas les 100 lignes déjà créées, triées)
        courant = sorted(courant, key=numero)
        self.assertNotEqual(courant[:100], sorted(([e["id"] for e in attendues])[:100], key=numero))
        self.assertEqual(trier("id"), (courant[:100], [["N°", "ascending"]]))
        courant = sorted(courant, key=numero, reverse=True)
        self.assertEqual(trier("id"), (courant[:100], [["N°", "descending"]]))
        # Date croissante (à date égale, l'ordre d'avant : N° décroissant), puis toute la liste au clic
        courant = sorted(courant, key=lambda i: dates[i])
        self.assertEqual(trier("date"), (courant[:100], [["Date", "ascending"]]))
        self.assertEqual(page.inner_text(".wiki-liste-entites .wiki-voir-autres").strip(), "Voir les %d autres interventions" % (total - 100))
        page.click(".wiki-liste-entites .wiki-voir-autres")
        self.assertEqual([l["id"] for l in page.evaluate(INTERVENTIONS_JS)], courant)
        self.assertEqual(page.locator(".wiki-liste-entites .wiki-voir-autres").count(), 0)
        # Après l'ouverture, un nouveau tri garde toutes les lignes
        courant = sorted(courant, key=numero)
        self.assertEqual(trier("id"), (courant, [["N°", "ascending"]]))
        self.verifier_sans_piege()


# ---------------------------------------------------------------------------
# Recherche de l'accueil : entités par type, puis plein texte (D99, D114)
# ---------------------------------------------------------------------------

class TestRechercheAccueil(CasWiki):

    def test_recherche_groupee_par_type_selon_le_profil(self):
        for profil in ("demandeur", "technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                self.aller_accueil()
                self.chercher_accueil("pompe")
                lus = page.evaluate(TROUVES_JS)
                attendus = page.evaluate("""([t, p]) => Wiki.chercherEntites(t, { profil: p }).groupes.map((g) => ({ type: g.type,
                  ids: g.entites.map((e) => e.lien) }))""", ["pompe", profil])
                # Seules les 6 premières entités d'un groupe sont créées (D101)
                self.assertEqual([(l["type"], l["ids"]) for l in lus], [(a["type"], a["ids"][:6]) for a in attendus])
                self.assertEqual([l["type"] for l in lus], ["machine"] + ([] if profil == "demandeur" else ["intervention"]))
                # Machines : calcul fait ici (un mot du nom commence par « pompe »), par titre
                equipements = page.evaluate("Donnees.lignes('equipements')")
                machines = sorted((titre_equipement(e), e["id"]) for e in equipements
                                  if any(m.startswith("pompe") for m in mots_comparables(titre_equipement(e))))
                self.assertEqual(lus[0]["ids"], [i for _, i in machines][:6])
                self.assertEqual(lus[0]["titre"], "Machines · %d" % len(machines))
                for groupe in lus:
                    self.assertEqual(groupe["liens"], ["#/wiki/" + encoder(i) for i in groupe["ids"]])
                    self.assertEqual(groupe["caches"], 0)
                # Puis les interventions clôturées et les textes du wiki : Wiki.rechercher, numéros d'OT sans lien au demandeur
                plein = page.evaluate(RESULTATS_JS, "#wiki-trouves")
                attendu = page.evaluate(ATTENDU_RECHERCHE_JS, ["pompe", ""])
                self.assertEqual([(b["portee"], b["ids"], b["types"]) for b in plein], [(a["portee"], a["ids"], a["types"]) for a in attendu])
                if profil == "demandeur":
                    self.assertEqual(sum(b["liensOt"] for b in plein), 0)
                # Un technicien par son nom, une intervention par son numéro : jamais pour le demandeur
                nom = page.evaluate("Donnees.trouver('techniciens', 'TEC-0001').nom")
                self.chercher_accueil(nom)
                groupes = {g["type"]: g["ids"] for g in page.evaluate(TROUVES_JS)}
                self.assertEqual(groupes.get("technicien"), None if profil == "demandeur" else ["TEC-0001"])
                ot = page.evaluate("Donnees.lignes('ordres_travail')[3].id")
                self.chercher_accueil(ot)
                groupes = {g["type"]: g["ids"] for g in page.evaluate(TROUVES_JS)}
                self.assertEqual(groupes.get("intervention"), None if profil == "demandeur" else [ot])
                if profil == "demandeur":
                    self.assertEqual(page.locator('#wiki-trouves a[href^="#/wiki/TEC-"], #wiki-trouves a[href^="#/wiki/OT-"], '
                                                  '#wiki-trouves a[href^="#/ot/"]').count(), 0)
                # Une page du wiki par son titre (savoir-faire de la base), puis le lien mène à sa page
                self.chercher_accueil("garniture")
                groupes = {g["type"]: g["ids"] for g in page.evaluate(TROUVES_JS)}
                self.assertIn("WP-0003", groupes["savoir-faire"])
                page.click('#wiki-trouves li[data-id="WP-0003"] a')
                page.wait_for_selector('.wiki-page[data-page="WP-0003"]')
                self.verifier_sans_piege()

    def test_voir_les_autres_rien_trouve_et_entree(self):
        page = self.ouvrir("technicien")
        self.aller_accueil()
        self.chercher_accueil("ot")
        groupe = [g for g in page.evaluate(TROUVES_JS) if g["type"] == "intervention"][0]
        total = page.evaluate("Donnees.lignes('ordres_travail').length")
        attendus = page.evaluate("() => Wiki.chercherEntites('ot', { profil: 'technicien' }).groupes.find((g) => g.type === 'intervention').entites.map((e) => e.lien)")
        self.assertEqual(len(attendus), total)
        self.assertEqual(groupe["ids"], attendus[:6])                      # les 6 premières créées, rien de caché
        self.assertEqual(groupe["bouton"], "Voir les %d autres interventions" % (total - 6))
        page.click('#wiki-trouves .wiki-groupe[data-type="intervention"] .wiki-voir-autres')
        groupe = [g for g in page.evaluate(TROUVES_JS) if g["type"] == "intervention"][0]
        self.assertEqual((groupe["ids"], groupe["bouton"]), (attendus, None))
        # Rien trouvé : un seul titre (relecture de T136, m8)
        self.chercher_accueil("zzqxw")
        self.assertEqual(page.eval_on_selector_all("#wiki-trouves h2", "e => e.map((x) => x.textContent.trim())"), ["Rien trouvé pour « zzqxw »."])
        self.assertEqual(page.inner_text("#wiki-trouves .wiki-rien").strip(), "Rien trouvé pour « zzqxw ».")
        # Effacer le champ cache les résultats ; Entrée cherche tout de suite (sans attendre 300 ms)
        page.fill("#wiki-champ-accueil", "")
        page.wait_for_selector("#wiki-trouves", state="hidden")
        page.evaluate("() => { const c = document.querySelector('#wiki-champ-accueil'); c.value = 'compresseur'; }")
        page.press("#wiki-champ-accueil", "Enter")
        self.assertEqual(page.evaluate("document.querySelector('#wiki-trouves').hidden"), False)
        self.assertIn("EQ-0001", [i for g in page.evaluate(TROUVES_JS) for i in g["ids"]])


# ---------------------------------------------------------------------------
# #/wiki/<id> : la page d'une entité, six types, trois profils (refonte 2, §20.12, T137)
# ---------------------------------------------------------------------------

# OT cités par « À trancher » et les textes (Wiki.entite().references, sans numéro), dans leur ordre
REFERENCES_PO02 = ["OT-2026-0214", "OT-2025-0030", "OT-2025-0010", "OT-2025-0044", "OT-2026-0026", "OT-2026-0098"]
REFERENCES_SF = ["OT-2025-0030", "OT-2026-0133", "OT-2026-0098", "OT-2026-0058"]
REFERENCES_CP01 = ["OT-2026-0161", "OT-2026-0171"]
# Petits numéros de la page, un seul jeu dans l'ordre d'apparition (D118, T143), écrits à la main : « À trancher », « En
# bref », les articles consommés — un OT déjà numéroté garde son numéro, les autres prennent les suivants —, puis
# « Astuces » (PO-02 : déjà numérotés) ou l'ancienne rubrique « Ce qui revient » (CP-01 : le dernier numéro).
NUMEROS_PO02 = ["OT-2026-0214", "OT-2025-0030", "OT-2025-0010", "OT-2025-0044", "OT-2026-0026",
                "OT-2026-0175", "OT-2026-0133", "OT-2026-0098", "OT-2026-0058",           # kit garniture PO-02
                "OT-2026-0126", "OT-2026-0072", "OT-2026-0017", "OT-2025-0017",           # graisse EP2
                "OT-2026-0082"]                                                           # joints toriques
NUMEROS_CP01 = ["OT-2026-0161", "OT-2026-0117", "OT-2026-0118", "OT-2026-0094", "OT-2026-0048", "OT-2026-0030",
                "OT-2026-0013", "OT-2025-0043", "OT-2025-0023", "OT-2026-0138", "OT-2026-0076", "OT-2026-0012",
                "OT-2025-0004", "OT-2026-0061", "OT-2026-0171"]
SECTIONS = {
    "machine": ["texte:En bref", "wiki-pannes", "wiki-interventions", "carte wiki-recherche", "wiki-articles", "wiki-savoir-faire",
                "texte:Astuces", "wiki-preventif"],
    "panne": ["wiki-calcule", "wiki-panne-machines", "wiki-causes", "wiki-remedes", "wiki-articles-changes", "wiki-interventions"],
    "article": ["texte:À quoi il sert", "wiki-stock", "wiki-montee", "wiki-consomme-sur", "wiki-interventions", "wiki-savoir-faire"],
    "technicien": ["wiki-calcule", "wiki-habilitations", "wiki-interventions"],
    "intervention": ["wiki-demande", "wiki-travail", "wiki-compte-rendu", "wiki-astuce", "wiki-pieces", "wiki-temps", "wiki-cite-dans"],
    "savoir-faire": ["texte:Quand le faire", "texte:Étapes", "texte:Pièges"],
}
TYPES_ENTITES = {"machine": ("Machine", "Machines"), "panne": ("Panne", "Pannes"), "article": ("Article", "Articles"),
                 "technicien": ("Technicien", "Techniciens"), "intervention": ("Intervention", "Interventions"),
                 "savoir-faire": ("Savoir-faire", "Savoir-faire")}
LIENS_HORS_WIKI = re.compile(r"^#/(wiki|wiki-journal\?entree=WJ-\d+|wiki-ecrire/.+|equipement/[^/]+(/modifier)?|magasin/article/[^/]+|ot/[^/]+)$")


class TestPagesEntites(CasWiki):
    """Page d'une entité : en-tête, en tête de page, sections, fiche des faits, textes, références, visibilité, liens."""

    def verifier_entete(self, lu, type_, entite):
        libelle, liste = TYPES_ENTITES[type_]
        self.assertEqual((lu["id"], lu["type"]), (entite["id"], type_))
        self.assertEqual(lu["fil"][:2], [["Wiki", "#/wiki"], [liste, "#/wiki/" + LISTE_DU_TYPE[type_]]])
        self.assertIn("wiki-t-" + type_, lu["puce"])
        titre = entite["id"] + " — " + entite["titre"] if type_ == "intervention" else entite["titre"]
        self.assertEqual(lu["h1Brut"], titre)

    def test_six_types_pour_les_trois_profils(self):
        for profil in ("demandeur", "technicien", "responsable"):
            page = self.ouvrir(profil, base=True)
            calcul = self.calcul()
            for type_, identifiant in SIX.items():
                with self.subTest(profil=profil, type=type_):
                    lu = self.lire(identifiant)
                    if profil == "demandeur" and type_ in ("technicien", "intervention"):      # D114 : pas de page pour lui
                        self.assertEqual((lu.get("introuvable"), lu["h1"]), (True, "Page introuvable"))
                        self.assertIsNone(self.entite(identifiant, profil))
                        continue
                    entite = self.entite(identifiant, profil)
                    self.verifier_entete(lu, type_, entite)
                    # Fiche des faits : Wiki.entite ET le calcul Python indépendant (faits vides omis, valeurs à la française ;
                    # pour l'intervention, tous ses techniciens)
                    self.assertEqual(lu["faits"][:len(fiche_attendue(entite))] if type_ != "machine"
                                     else [f for f in lu["faits"] if f[0] != "Sous-ensembles"], fiche_attendue(entite))
                    self.assertEqual(faits_attendus(entite["faits"]), faits_attendus(calcul.entite(identifiant, profil, MAINTENANT)["faits"]))
                    self.assertEqual(fiche_attendue(entite), fiche_attendue(calcul.entite(identifiant, profil, MAINTENANT)))
                    # Sections dans l'ordre du type ; consignation et « À trancher » en tête de page
                    self.assertEqual([s for s in lu["sections"] if s not in ("wiki-en-attente", "wiki-retours", "wiki-references")],
                                     SECTIONS[type_])
                    self.assertEqual(lu["blocs"][0], "entete-page wiki-entete-entite")
                    self.assertEqual(lu["blocs"][-1], "wiki-page-grille")
                    if lu["alertes"]:
                        self.assertEqual((lu["blocs"][1], lu["enTete"]), ("wiki-alertes", True))
                    attendues = {"machine": ["wiki-consignation", "wiki-a-trancher"], "savoir-faire": ["wiki-entete", "wiki-a-trancher"]}
                    self.assertEqual(lu["alertes"], attendues.get(type_, []))
                    # Références à la fin, jamais [OT-…] à l'écran
                    self.assertEqual(lu["crochets"], 0)
                    if lu["references"]:
                        self.assertEqual(lu["sections"][-1], "wiki-references")
                    # Interventions de la page : dans l'ordre de Wiki.entite (= calcul Python), avec leur statut
                    if "wiki-interventions" in SECTIONS[type_]:
                        ordre = calcul.entite(identifiant, profil, MAINTENANT)["sections"]["interventions"]
                        self.assertEqual([i[0] for i in lu["interventions"]], [o["id"] for o in ordre][:10])
                        self.assertEqual([i[1] for i in lu["interventions"]], [o["statut"] for o in ordre][:10])
                        self.assertEqual([i[2] for i in lu["interventions"]],
                                         [None if profil == "demandeur" else "#/wiki/" + o["id"] for o in ordre][:10])
                    # Visibilité (D114) : prix au technicien et au responsable, taux horaire au responsable seul
                    libelles = [f[0] for f in lu["faits"]]
                    if type_ == "article":
                        self.assertEqual("Prix unitaire" in libelles, profil != "demandeur")
                        self.assertEqual("€" in page.inner_text("#contenu"), profil != "demandeur")
                    if type_ == "technicien":
                        self.assertEqual("Taux horaire" in libelles, profil == "responsable")
                    if profil == "demandeur":
                        self.assertEqual([h for h in lu["liens"] if h.startswith(("#/wiki/TEC-", "#/wiki/OT-", "#/ot", "#/magasin"))], [])
                        self.assertEqual(page.locator("#contenu sup.wiki-ref a").count(), 0)
                    # Actions : fiche de l'équipement, de l'article (pas au demandeur), de l'OT ; « Modifier » au responsable
                    actions = {a[0]: a[2] for a in lu["actions"]}
                    if type_ == "machine":
                        self.assertEqual(actions.get("wiki-lien-fiche"), "#/equipement/EQ-0005")
                    if type_ == "article":
                        self.assertEqual(actions.get("wiki-lien-fiche"), None if profil == "demandeur" else "#/magasin/article/ART-0016")
                    if type_ == "intervention":
                        self.assertEqual(actions.get("wiki-fiche-ot"), "#/ot/OT-2026-0214")
                    self.assertEqual(actions.get("wiki-modifier"), "#/wiki-ecrire/" + identifiant
                                     if profil == "responsable" and type_ in ("machine", "article", "savoir-faire") else None)
                    self.verifier_sans_piege()

    def test_petits_numeros_et_references(self):
        for profil in ("technicien", "demandeur"):
            page = self.ouvrir(profil, base=True)
            calcul = self.calcul()
            for identifiant, cites, attendus in (("EQ-0005", REFERENCES_PO02, NUMEROS_PO02), ("WP-0003", REFERENCES_SF, REFERENCES_SF),
                                                 ("EQ-0001", REFERENCES_CP01, NUMEROS_CP01)):
                with self.subTest(profil=profil, page=identifiant):
                    lu = self.lire(identifiant)
                    entite = self.entite(identifiant, profil)
                    # Un seul jeu de numéros, dans l'ordre d'apparition sur la page (« À trancher » en tête, puis les textes
                    # et les articles consommés à leur place : D118) ; un OT garde son numéro ; Wiki.entite().references
                    # donne les OT cités par les textes, sans numéro (la page numérote seule)
                    premiers = []
                    for numero, ot in lu["sups"]:
                        if ot not in premiers:
                            premiers.append(ot)
                    self.assertEqual(premiers, attendus)
                    articles = calcul.ot_des_articles(identifiant) if entite["type"] == "machine" else []
                    self.assertEqual(premiers, ordre_des_numeros(entite, articles))
                    self.assertEqual([r["id"] for r in entite["references"]], cites)
                    self.assertEqual({tuple(sorted(r)) for r in entite["references"]}, {("date", "id", "lien", "machine", "titre")})
                    self.assertEqual({ot: numero for numero, ot in lu["sups"]}, {ot: rang + 1 for rang, ot in enumerate(attendus)})
                    ordres = {o["id"]: o for o in page.evaluate("Donnees.lignes('ordres_travail')")}
                    for ref in entite["references"]:
                        ot = ordres[ref["id"]]
                        self.assertEqual(ref["date"], date_de_l_ot(ot)[:10])
                    # Bulle « <OT> · <date> · <titre> » et nom « Référence n : <bulle> » ; lien vers la page de l'OT ; pour le
                    # demandeur, un bouton sans lien (relecture de T137, m6 : la bulle s'ouvre au toucher)
                    sups = page.evaluate("""() => Array.from(document.querySelectorAll('#contenu sup.wiki-ref')).map((s) => [s.dataset.ot,
                      s.firstElementChild.tagName, s.firstElementChild.getAttribute('href'), s.firstElementChild.getAttribute('title'),
                      s.firstElementChild.getAttribute('aria-label'), s.firstElementChild.textContent, s.querySelectorAll('a').length])""")
                    for ot, balise, lien, bulle, nom, numero, liens in sups:
                        self.assertEqual(bulle, "%s · %s · %s" % (ot, date_fr(date_de_l_ot(ordres[ot])[:10]), ordres[ot]["titre"]))
                        self.assertEqual(nom, "Référence %s : %s" % (numero, bulle))
                        self.assertEqual((balise, lien, liens), ("BUTTON", None, 0) if profil == "demandeur" else ("A", "#/wiki/" + ot, 1))
                    # « Références » : numéro, OT, date, machine, titre — dans l'ordre des numéros
                    self.assertEqual([r[:2] for r in lu["references"]], [["wiki-ref-%d" % (rang + 1), ot] for rang, ot in enumerate(attendus)])
                    for (_, ot, texte, liens) in lu["references"]:
                        o = ordres[ot]
                        repere = page.evaluate("(id) => Donnees.trouver('equipements', id).repere", o["equipement_id"])
                        self.assertEqual(texte, plat("%s · %s · %s · %s" % (ot, date_fr(date_de_l_ot(o)[:10]), repere, o["titre"])))
                        self.assertEqual(liens, (["#/wiki/" + o["equipement_id"]] if profil == "demandeur"
                                                 else ["#/wiki/" + ot, "#/wiki/" + o["equipement_id"]]))
                    # Jamais [OT-…] à l'écran ; le balisage stocké ne change pas
                    self.assertEqual(lu["crochets"], 0)
                    self.assertNotIn("[OT-", page.inner_text("#contenu"))
            stockes = {p["id"]: p["texte"] for p in page.evaluate("Donnees.lignes('wiki_pages')")}
            self.assertEqual(stockes, {p["id"]: p["texte"] for p in PAGES})
        # Le petit numéro mène à la page de l'intervention
        page = self.ouvrir("technicien", base=True)
        self.lire("EQ-0005")
        page.click('#wiki-texte sup.wiki-ref[data-ot="OT-2025-0044"] a')
        page.wait_for_selector('.wiki-page[data-page="OT-2025-0044"] .wiki-page-grille')

    def test_petits_numeros_des_articles_consommes_et_changes(self):
        """D118 (T143) : sur la page d'une machine (articles consommés) et d'une panne (articles changés), chaque article
        montre, après son nombre d'interventions, les OT où il a servi en petits numéros — les 10 plus récents, puis « … et
        n autres » —, égaux au calcul Python indépendant (CalculWiki.ot_des_articles), et garde sa quantité ; un seul jeu
        de numéros par page, dans l'ordre d'apparition, sans trou ni doublon (un OT déjà numéroté par un texte garde son
        numéro) ; « Références » les contient tous ; bulle « OT · date · titre » ; pour le demandeur, un bouton sans lien
        qui l'ouvre ; jamais [OT-…] à l'écran."""
        for profil in ("technicien", "demandeur"):
            page = self.ouvrir(profil, base=True)
            calcul = self.calcul()
            ordres = {o["id"]: o for o in page.evaluate("Donnees.lignes('ordres_travail')")}
            bulle = lambda ot: "%s · %s · %s" % (ot, date_fr(date_de_l_ot(ordres[ot])[:10]), ordres[ot]["titre"])  # noqa: E731
            plus_de_dix = 0
            for identifiant in ("EQ-0005", "EQ-0001", "EQ-0022", "PANNE-S01", "PANNE-S05"):
                with self.subTest(profil=profil, page=identifiant):
                    lu = self.lire(identifiant)
                    calcule = calcul.entite(identifiant, profil, MAINTENANT)
                    panne = calcule["type"] == "panne"
                    articles = calcul.ot_des_articles(identifiant)
                    self.assertTrue(articles)
                    plus_de_dix += sum(1 for a in articles if a["autres"])
                    lignes = page.evaluate(LIGNES_ARTICLES_JS, calcule["type"])
                    # Chaque article : ses OT (les 10 plus récents) en petits numéros, « … et n autres », sa quantité
                    self.assertEqual([(l["id"], l["ot"]) for l in lignes], [(a["articleId"], a["ot"]) for a in articles])
                    noms = ("intervention", "interventions") if panne else ("intervention clôturée", "interventions clôturées")
                    quantites = calcule["sections"]["articles" if panne else "articlesConsommes"]
                    self.assertEqual([(l["texte"], l["autres"], l["droite"]) for l in lignes], [
                        (pluriel(len(a["ot"]) + a["autres"], *noms),
                         ("… et %d autres" % a["autres"] if a["autres"] > 1 else "… et 1 autre") if a["autres"] else None,
                         "quantité " + nombre_fr(q["quantite"])) for a, q in zip(articles, quantites)])
                    self.assertEqual([q["articleId"] for q in quantites], [a["articleId"] for a in articles])
                    # Un seul jeu de numéros, dans l'ordre d'apparition sur la page, sans trou ni doublon
                    premiers = []
                    for _, ot in lu["sups"]:
                        if ot not in premiers:
                            premiers.append(ot)
                    self.assertEqual(premiers, ordre_des_numeros(self.entite(identifiant, profil), articles))
                    self.assertEqual([numero for numero, _ in lu["sups"]], [premiers.index(ot) + 1 for _, ot in lu["sups"]])
                    self.assertEqual(sorted({numero for numero, _ in lu["sups"]}), list(range(1, len(premiers) + 1)))
                    self.assertEqual([n for l in lignes for n in l["numeros"]], [premiers.index(ot) + 1 for l in lignes for ot in l["ot"]])
                    # « Références » : tous les OT numérotés, dans l'ordre des numéros, avec leur date et leur titre
                    self.assertEqual([r[:2] for r in lu["references"]], [["wiki-ref-%d" % (rang + 1), ot] for rang, ot in enumerate(premiers)])
                    self.assertTrue({ot for l in lignes for ot in l["ot"]} <= {r[1] for r in lu["references"]})
                    for (_, ot, texte, _) in lu["references"]:
                        self.assertTrue(texte.startswith(ot + " · " + date_fr(date_de_l_ot(ordres[ot])[:10]) + " · "), texte)
                        self.assertTrue(texte.endswith(plat(ordres[ot]["titre"])), texte)
                    # Bulle et nom ; lien vers la page de l'OT, ou bouton sans lien pour le demandeur
                    for l in lignes:
                        self.assertEqual(l["bulles"], [bulle(ot) for ot in l["ot"]])
                        self.assertEqual(l["noms"], ["Référence %d : %s" % (n, bulle(ot)) for n, ot in zip(l["numeros"], l["ot"])])
                        self.assertEqual((l["balises"], l["liens"]), (["BUTTON"] * len(l["ot"]), [None] * len(l["ot"])) if profil == "demandeur"
                                         else (["A"] * len(l["ot"]), ["#/wiki/" + ot for ot in l["ot"]]))
                    self.assertEqual(lu["crochets"], 0)
                    self.assertNotIn("[OT-", page.inner_text("#contenu"))
            self.assertGreaterEqual(plus_de_dix, 2)                  # des articles à plus de 10 OT : « … et n autres »
            # Pour le demandeur, le numéro d'un article ouvre sa bulle ; pour le technicien, il mène à la page de l'OT
            self.lire("PANNE-S05")
            numero = page.locator("#wiki-articles-changes sup.wiki-ref").first
            ot = numero.get_attribute("data-ot")
            numero.locator(":scope > *").click()
            if profil == "demandeur":
                self.assertEqual(page.locator("#contenu .wiki-ref-bulle").all_inner_texts(), [bulle(ot)])
            else:
                page.wait_for_selector('.wiki-page[data-page="%s"] .wiki-page-grille' % ot)
            self.verifier_sans_piege()

    def test_textes_rubriques_liens_et_origine(self):
        page = self.ouvrir("technicien", base=True)
        # Machine : « En bref » en paragraphe, « Astuces » en liste, plus loin ; liens [[titre]] vers les pages qui s'affichent
        lu = self.lire("EQ-0005")
        textes = {t["rubrique"]: t for t in lu["textes"]}
        self.assertEqual([t["rubrique"] for t in lu["textes"]], ["En bref", "Astuces"])
        self.assertEqual((textes["En bref"]["forme"], textes["Astuces"]["forme"]), ("prose", "liste"))
        self.assertEqual(textes["En bref"]["origine"], ORIGINE_IA % "14/10/2026")
        self.assertEqual(textes["Astuces"]["origine"], ORIGINE_IA % "14/10/2026")     # un bandeau par groupe de textes
        for rubrique, phrases in rubriques_du_texte(TEXTE_PO02):
            self.assertEqual([{"texte": p["texte"], "ot": [r[1] for r in p["refs"]], "liens": p["liens"], "absents": p["absents"]}
                              for p in textes[rubrique]["phrases"]], [phrase_attendue(p) for p in phrases], rubrique)
        self.assertIn(["Fuite", "#/wiki/PANNE-S01"], textes["Astuces"]["phrases"][0]["liens"])    # [[Fuite]] → sa page de panne
        self.assertEqual(textes["Astuces"]["phrases"][0]["absents"], ["Page disparue"])
        # Un OT cité deux fois dans la même phrase n'a qu'un petit numéro, à sa première place (relecture de T137, m1)
        self.assertEqual(rubriques_du_texte(TEXTE_PO02)[1][1][0].count("[OT-2026-0098]"), 2)
        self.assertEqual([r[1] for r in textes["Astuces"]["phrases"][0]["refs"]], ["OT-2026-0098", "OT-2025-0010"])
        self.assertEqual(textes["Astuces"]["phrases"][0]["texte"], "Repérer l'accouplement avant le démontage, voir Fuite et Page disparue")
        self.assertEqual(page.evaluate("""() => { const phrase = document.querySelector('.wiki-texte[data-rubrique="Astuces"] .wiki-phrase');
          return [phrase.querySelectorAll('sup.wiki-ref[data-ot="OT-2026-0098"]').length,
            phrase.firstElementChild.matches('sup.wiki-ref[data-ot="OT-2026-0098"]'), phrase.firstChild.textContent]; }"""),
            [1, True, "Repérer l'accouplement"])
        # Une ancienne rubrique (avant la refonte 2) vient après celles du type ; une rubrique vide n'est pas montrée
        lu = self.lire("EQ-0001")
        self.assertEqual([t["rubrique"] for t in lu["textes"]], ["En bref", "Ce qui revient"])
        self.assertEqual(lu["sections"].index("texte:Ce qui revient") - lu["sections"].index("wiki-savoir-faire"), 1)
        self.assertEqual(lu["textes"][0]["origine"], ORIGINE_MANUEL % "16/10/2026")
        # Article : « À quoi il sert » ; un lien vers un savoir-faire au titre piégé
        lu = self.lire("ART-0016")
        self.assertEqual([(t["rubrique"], t["forme"], t["origine"]) for t in lu["textes"]], [("À quoi il sert", "prose", ORIGINE_IA % "15/10/2026")])
        self.assertEqual([p["liens"] for p in lu["textes"][0]["phrases"]], [[[TITRE_PO02, "#/wiki/EQ-0005"]], [[plat(TITRE_PIEGE), "#/wiki/WP-0006"]]])
        # Savoir-faire : rubriques dans l'ordre du type ; un lien vers une ancienne page de mode reste du texte
        lu = self.lire("WP-0003")
        self.assertEqual([(t["rubrique"], t["forme"]) for t in lu["textes"]], [("Quand le faire", "liste"), ("Étapes", "liste"), ("Pièges", "liste")])
        self.assertEqual(lu["textes"][0]["origine"], ORIGINE_MIXTE % "17/10/2026")
        self.assertEqual(lu["textes"][1]["phrases"][0]["absents"], ["Fuite de garniture"])
        self.assertEqual(self.lire("WP-0004")["textes"][0]["origine"], ORIGINE_MANUEL % "15/10/2026")
        # Sans texte : « Aucun texte validé pour l'instant. », pas de bandeau ; « Astuces » absente
        for identifiant, rubrique in (("ART-0001", "À quoi il sert"), ("EQ-0031", "En bref")):
            lu = self.lire(identifiant)
            self.assertEqual([(t["rubrique"], t["sansTexte"], t["origine"]) for t in lu["textes"]], [(rubrique, SANS_TEXTE, None)])
            self.assertEqual(lu["references"], [])
            self.assertNotIn("wiki-references", lu["sections"])

    def test_pages_qui_renvoient_ici(self):
        """CS103 : « Pages qui renvoient ici » exact — la règle de Wiki.page (champ liens des pages actives) — sur une machine,
        un article, deux savoir-faire et une panne, contre le calcul Python indépendant et des valeurs écrites à la main ;
        ni la page archivée, ni l'ancienne page de mode (type retiré, sans page), ni les propositions à valider ; section
        absente sans retour et sur une intervention ; chaque lien mène à une page qui s'affiche, aussi pour le demandeur."""
        attendus = {
            "EQ-0005": [("ART-0016", "article", TITRE_KIT)],                        # texte de l'article ; ni WP-0009 ni WP-0010
            "ART-0016": [("EQ-0005", "machine", TITRE_PO02)],                       # texte de PO-02 ; ni WP-0009 ni WJ-00005
            "WP-0003": [("EQ-0005", "machine", TITRE_PO02), ("WP-0004", "savoir-faire", "Remonter le kit de garniture")],
            "WP-0006": [("ART-0016", "article", TITRE_KIT)],
            "PANNE-S01": [("WP-0007", "savoir-faire", TITRE_ALIGNER), ("EQ-0005", "machine", TITRE_PO02)],   # par titre
            "WP-0012": [],                                                          # seul WJ-00004, à valider, y renvoie
            "EQ-0001": [],
        }
        for profil in ("demandeur", "technicien", "responsable"):
            page = self.ouvrir(profil, base=True)
            calcul = self.calcul()
            # Les liens qui ne comptent pas existent bien : page archivée, ancienne page de mode, propositions à valider
            self.assertIn("[[Règles de l'atelier]]", page.evaluate("Donnees.trouver('wiki_journal', 'WJ-00004').changements"))
            self.assertIn("[[" + TITRE_KIT + "]]", page.evaluate("Donnees.trouver('wiki_journal', 'WJ-00005').changements"))
            for identifiant, retours in attendus.items():
                with self.subTest(profil=profil, page=identifiant):
                    lu = self.lire(identifiant)
                    calcules = calcul.entite(identifiant, profil, MAINTENANT)["retours"]
                    self.assertEqual([(r["id"], r["type"], r["titre"]) for r in calcules], retours)
                    self.assertEqual(self.entite(identifiant, profil)["retours"], calcules)
                    self.assertEqual(lu["retours"], [[i, plat(t), "#/wiki/" + i] for i, _, t in retours])
                    self.assertEqual("wiki-retours" in lu["sections"], bool(retours))
                    if retours:                          # en fin de page, avant « Références »
                        self.assertEqual([s for s in lu["sections"] if s not in ("wiki-en-attente", "wiki-references")][-1], "wiki-retours")
            if profil != "demandeur":
                self.assertNotIn("wiki-retours", self.lire("OT-2026-0214")["sections"])         # « Cité dans le wiki » le fait
            # Chaque lien mène à la page de celle qui renvoie
            self.lire("PANNE-S01")
            page.click('#wiki-retours a[href="#/wiki/WP-0007"]')
            page.wait_for_selector('.wiki-page[data-page="WP-0007"] .wiki-page-grille')
            self.lire("ART-0016")
            page.click('#wiki-retours a[href="#/wiki/EQ-0005"]')
            page.wait_for_selector('.wiki-page[data-page="EQ-0005"] .wiki-page-grille')
            self.verifier_sans_piege()

    def test_consignation_et_a_trancher_en_tete(self):
        for profil in ("demandeur", "technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                responsable = profil == "responsable"
                consignation = page.evaluate("Donnees.trouver('equipements', 'EQ-0005').consignation")
                self.assertGreater(consignation.count("\n"), 2)
                lu = self.lire("EQ-0005")
                self.assertEqual(lu["alertes"], ["wiki-consignation", "wiki-a-trancher"])
                self.assertEqual((lu["consignation"]["titre"], lu["consignation"]["texte"]), ("Consignation de PO-02", consignation))
                self.assertEqual(lu["consignation"]["texte"], self.entite("EQ-0005", profil)["sections"]["consignation"]["texte"])
                self.assertEqual(page.locator("#wiki-consignation .wiki-consignation-texte *").count(), 0)
                # « À trancher » : vu par tous ; note et boutons au responsable
                self.assertEqual([(c["entree"], c["rang"], c["anterieure"]) for c in lu["contradictions"]],
                                 [("WJ-00002", "0", "non"), ("WJ-00002", "1", "non")])
                premiere, seconde = lu["contradictions"]
                self.assertEqual((premiere["page"]["texte"], premiere["titreOt"], premiere["observation"]),
                                 (CONTRADICTIONS_PO02[0]["phrase"], "Ce que dit le nouvel OT", CONTRADICTIONS_PO02[0]["observation"]))
                self.assertEqual(seconde["page"]["texte"], "Le raccord de refoulement se desserre")
                self.assertEqual([r[1] for r in seconde["page"]["refs"]], ["OT-2025-0030"])
                self.assertEqual(seconde["observation"], OBSERVATION_PIEGEE)
                self.assertEqual([r[:2] for r in premiere["refs"]], [["1", "OT-2026-0214"]])
                for contradiction in lu["contradictions"]:
                    self.assertEqual(contradiction["boutons"], [["ancien", "L'ancien reste"], ["nouveau", "Le nouveau remplace"],
                                                                ["les deux", "Les deux sont vrais"]] if responsable else [])
                    self.assertEqual(contradiction["notes"], 1 if responsable else 0)
                # Propositions en attente : au responsable seulement
                self.assertEqual(lu["attente"], [["WJ-00004", "Proposition WJ-00004 OT-2026-0082"]] if responsable else [])
                if not responsable:
                    self.assertNotIn("WJ-00004", page.inner_text("#contenu"))
                # Savoir-faire rattaché à la machine : sa consignation telle quelle, la phrase de Prévo ; contradiction antérieure
                lu = self.lire("WP-0003")
                self.assertEqual(lu["alertes"], ["wiki-entete", "wiki-a-trancher"])
                self.assertEqual((lu["consignation"]["titre"], lu["consignation"]["phrase"], lu["consignation"]["texte"]),
                                 ("Consignation de PO-02", PHRASE_SAVOIR_FAIRE, consignation))
                self.assertEqual(lu["consignation"]["phrase"], page.evaluate("Wiki.PHRASE_SAVOIR_FAIRE"))
                self.assertEqual([(c["entree"], c["anterieure"], c["titreOt"]) for c in lu["contradictions"]],
                                 [("WJ-00003", "oui", "Observation antérieure aux faits de la page")])
                # Rattaché à un article : les machines où il est monté, en liens ; machine sans consignation ; libre
                lu = self.lire("WP-0004")
                self.assertEqual((lu["alertes"], lu["consignation"]["phrase"], lu["consignation"]["texte"]), (["wiki-entete"], PHRASE_SAVOIR_FAIRE, None))
                self.assertEqual(lu["consignation"]["equipements"], [[e["repere"], "#/wiki/" + e["equipementId"]]
                                                                     for e in self.entite("WP-0004", profil)["sections"]["entete"]["equipements"]])
                self.assertIn(["PO-02", "#/wiki/EQ-0005"], lu["consignation"]["equipements"])
                lu = self.lire("WP-0005")
                self.assertEqual((lu["consignation"]["titre"], lu["consignation"]["absence"], lu["consignation"]["modifier"]),
                                 ("Consignation de PE-01", SANS_CONSIGNATION, None))
                lu = self.lire("WP-0012")
                self.assertEqual((lu["sousTitre"], lu["consignation"]["equipements"]), ("Sans rattachement", []))
                self.assertIn("Aucune machine connue", lu["consignation"]["aide"])
                # Les autres types n'ont rien en tête
                for identifiant in ("PANNE-S01", "ART-0001"):
                    self.assertEqual(self.lire(identifiant)["alertes"], [])
                self.verifier_sans_piege()

    def test_page_intervention_en_lecture_seule(self):
        for profil in ("technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                lu = self.lire("OT-2026-0214")
                entite = self.entite("OT-2026-0214", profil)
                ot = page.evaluate("Donnees.trouver('ordres_travail', 'OT-2026-0214')")
                self.assertEqual(lu["h1Brut"], "OT-2026-0214 — " + ot["titre"])
                self.assertEqual(lu["sousTitre"], date_fr(ot["date_fin"]) + " · " + TITRE_PO02)
                blocs = lu["blocsOt"]
                self.assertEqual(blocs["wiki-travail"], plat(ot["travail_a_faire"]))
                self.assertEqual(blocs["wiki-compte-rendu"], plat(ot["compte_rendu"]))
                self.assertEqual(blocs["wiki-astuce"], plat(ot["astuce"]))
                self.assertIn(plat(entite["sections"]["demande"]["symptome"]), page.inner_text("#wiki-demande"))
                self.assertNotIn("wiki-motif-attente", lu["sections"])
                self.assertNotIn("wiki-motif-annulation", lu["sections"])
                # « Cité dans le wiki » : les pages dont un texte cite l'OT (Wiki.entite)
                cites = page.evaluate("Array.from(document.querySelectorAll('#wiki-cite-dans li')).map((li) => li.dataset.id)")
                self.assertEqual(cites, [p["id"] for p in entite["sections"]["citeDans"]])
                self.assertEqual(sorted(cites), ["ART-0016", "WP-0007", "WP-0008"])      # le texte de PO-02 ne la cite pas
                self.assertEqual(page.evaluate("Array.from(document.querySelectorAll('#wiki-temps li')).map((li) => li.dataset.id)"),
                                 [t["id"] for t in entite["sections"]["temps"]])
                # Lecture seule : aucun champ ni bouton d'écriture, « Modifier » absent ; « Ouvrir la fiche OT » mène à la fiche
                self.assertEqual(lu["controles"], 0)
                self.assertEqual(page.locator("#contenu .wiki-page button").count(), 0)
                self.assertEqual([a[0] for a in lu["actions"]], ["wiki-fiche-ot"])
                self.assertEqual(lu["actions"][0][1:], ["Ouvrir la fiche OT", "#/ot/OT-2026-0214"])
                page.click("#wiki-fiche-ot")
                page.wait_for_function("location.hash === '#/ot/OT-2026-0214'")
                page.wait_for_selector(".ot-onglets")
        # Motifs d'attente et d'annulation de l'OT, quand ils sont renseignés (relecture de T135)
        for identifiant, section, champ in (("OT-2026-0192", "wiki-motif-attente", "motif_attente"),
                                            ("OT-2026-0167", "wiki-motif-annulation", "motif_annulation")):
            lu = self.lire(identifiant)
            ot = page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", identifiant)
            self.assertTrue(ot[champ].strip())
            self.assertEqual(lu["blocsOt"][section], plat(ot[champ]))
            self.assertEqual(self.entite(identifiant, "responsable")["sections"]["motifAttente" if champ == "motif_attente" else "motifAnnulation"],
                             ot[champ].strip())

    def test_page_intervention_piegee_reste_du_texte(self):
        """Relecture de T137 (m4) : titre, travail demandé, compte rendu, astuce, motifs d'attente et d'annulation d'une
        intervention piégée (base d'essai) : du texte au caractère près, aucune balise interprétée — sur sa page, dans la
        liste des interventions, sur la page de sa machine et de ses techniciens."""
        for profil in ("technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                ot = page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", OT_PIEGE)
                self.assertEqual({champ: ot[champ] for champ in TEXTES_OT_PIEGE}, TEXTES_OT_PIEGE)      # stockés tels quels
                lu = self.lire(OT_PIEGE)
                self.assertEqual(lu["h1Brut"], OT_PIEGE + " — " + ORDRE_PIEGE["titre"])
                self.assertEqual([s for s in lu["sections"] if s in SECTIONS_OT_PIEGE], list(SECTIONS_OT_PIEGE))
                textes = page.evaluate("""(ids) => ids.map((id) => document.querySelector('#' + id + ' .wiki-texte-ot').textContent)""",
                                       list(SECTIONS_OT_PIEGE))
                self.assertEqual(textes, [TEXTES_OT_PIEGE[champ].strip() for champ in SECTIONS_OT_PIEGE.values()])
                self.assertEqual(page.locator("#contenu .wiki-texte-ot *, #contenu h1 *").count(), 0)
                self.verifier_sans_piege()
                # Ailleurs : la liste des interventions, la page de sa machine, celle d'un technicien qui y a pointé du temps
                for route, selecteur in (("#/wiki/interventions", "#wiki-interventions tbody tr"),
                                         ("#/wiki/EQ-0031", '.wiki-page[data-page="EQ-0031"] .wiki-intervention[data-id="%s"]' % OT_PIEGE),
                                         ("#/wiki/TEC-0003", '.wiki-page[data-page="TEC-0003"] .wiki-intervention[data-id="%s"]' % OT_PIEGE)):
                    with self.subTest(profil=profil, route=route):
                        self.aller(route, selecteur)
                        self.assertIn(ORDRE_PIEGE["titre"], page.inner_text("#contenu"))
                        self.verifier_sans_piege()

    def test_techniciens_d_une_intervention(self):
        """Relecture de T137 (m7) : la fiche d'une intervention nomme tous ses techniciens — celui de l'OT, puis ceux qui y ont
        pointé du temps ; « Techniciens » s'ils sont plusieurs —, chacun en lien vers sa page, à la place du fait
        « Technicien », comme Wiki.entite et le calcul Python indépendant ; aussi quand l'OT n'a pas de technicien."""
        lire = """() => { const dt = document.querySelector('#wiki-faits dt[data-section="techniciens"]');
          if (!dt) return null;
          const dd = dt.nextElementSibling;
          return { libelle: dt.textContent.trim(), noms: Array.from(dd.querySelectorAll('a, .wiki-nom-entite')).map((e) => [e.textContent,
              e.getAttribute('href')]),
            avant: dt.previousElementSibling.previousElementSibling.textContent.trim(),
            apres: dd.nextElementSibling ? dd.nextElementSibling.textContent.trim() : null,
            lignes: document.querySelectorAll('#wiki-faits dt[data-fait="Technicien"]').length }; }"""
        for profil in ("technicien", "responsable"):
            page = self.ouvrir(profil, base=True)
            calcul = self.calcul()
            for identifiant, attendus in (("OT-2026-0214", ["TEC-0002", "TEC-0004"]), (OT_PIEGE, ["TEC-0003", "TEC-0001"]),
                                          ("OT-2025-0012", ["TEC-0002", "TEC-0001"]), ("OT-2025-0001", ["TEC-0002"])):
                with self.subTest(profil=profil, intervention=identifiant):
                    techniciens = calcul.entite(identifiant, profil, MAINTENANT)["sections"]["techniciens"]
                    self.assertEqual([t["technicienId"] for t in techniciens], attendus)
                    self.assertEqual(self.entite(identifiant, profil)["sections"]["techniciens"], techniciens)
                    self.lire(identifiant)
                    lu = page.evaluate(lire)
                    self.assertEqual(lu["libelle"], "Techniciens" if len(attendus) > 1 else "Technicien")
                    self.assertEqual(lu["noms"], [[t["nom"], "#/wiki/" + t["technicienId"]] for t in techniciens])
                    self.assertEqual((lu["avant"], lu["apres"], lu["lignes"]), ("Statut", "Créé le", 1))      # à la place du fait
            # Le lien d'un technicien mène à sa page
            self.lire(OT_PIEGE)
            page.click('#wiki-faits a[href="#/wiki/TEC-0003"]')
            page.wait_for_selector('.wiki-page[data-page="TEC-0003"] .wiki-page-grille')
        # Le demandeur n'ouvre pas la page d'une intervention, ni aucune page de technicien (D114)
        page = self.ouvrir("demandeur", base=True)
        self.assertEqual(self.lire("OT-2026-0214").get("introuvable"), True)
        self.assertIsNone(self.calcul().entite("OT-2026-0214", "demandeur", MAINTENANT))

    def test_bulle_d_un_petit_numero_au_toucher_pour_le_demandeur(self):
        """Relecture de T137 (m6) : pour le demandeur, un petit numéro est un bouton sans lien, nommé « Référence n : <OT> ·
        <date> · <titre> », qui montre sa bulle au toucher (au clic, au clavier), une seule à la fois, lisible et dans
        l'écran ; un second toucher, un toucher ailleurs ou Échap la referment."""
        bulle_js = """() => Array.from(document.querySelectorAll('#contenu .wiki-ref-bulle')).map((b) => {
          b.scrollIntoView({ block: 'center' });
          const r = b.getBoundingClientRect();
          const dessus = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
          return { texte: b.textContent, ot: b.closest('sup').dataset.ot, cache: b.getAttribute('aria-hidden'), gauche: r.left,
            droite: r.right, largeur: r.width, hauteur: r.height, dessus: Boolean(dessus && dessus.closest('.wiki-ref-bulle') === b),
            ecran: document.documentElement.clientWidth }; })"""
        for largeur, hauteur, telephone, theme in ((375, 812, True, "clair"), (1440, 900, False, None)):
            with self.subTest(largeur=largeur):
                page = self.ouvrir("demandeur", largeur=largeur, hauteur=hauteur, telephone=telephone, theme=theme, base=True)
                self.lire("EQ-0005")
                ordres = {o["id"]: o for o in page.evaluate("Donnees.lignes('ordres_travail')")}
                boutons = page.locator("#contenu sup.wiki-ref > button.wiki-ref-numero")
                self.assertGreater(boutons.count(), 5)
                self.assertEqual(page.locator("#contenu sup.wiki-ref a").count(), 0)
                self.assertEqual(page.locator("#contenu .wiki-ref-bulle").count(), 0)
                toucher = (lambda e: e.tap()) if telephone else (lambda e: e.click())
                titre = page.locator("#contenu h1")
                for rang in range(boutons.count()):
                    bouton = boutons.nth(rang)
                    ot = bouton.evaluate("(b) => b.closest('sup').dataset.ot")
                    attendu = "%s · %s · %s" % (ot, date_fr(date_de_l_ot(ordres[ot])[:10]), ordres[ot]["titre"])
                    self.assertEqual(bouton.get_attribute("aria-label"), "Référence %s : %s" % (bouton.inner_text().strip(), attendu))
                    toucher(titre)                       # un toucher ailleurs ferme la bulle d'avant (elle peut couvrir ce numéro)
                    self.assertEqual(page.locator("#contenu .wiki-ref-bulle").count(), 0)
                    toucher(bouton)
                    bulles = page.evaluate(bulle_js)
                    self.assertEqual([(b["texte"], b["ot"], b["cache"], b["dessus"]) for b in bulles], [(attendu, ot, "true", True)], ot)
                    self.assertGreaterEqual(bulles[0]["gauche"], 0)
                    self.assertLessEqual(bulles[0]["droite"], bulles[0]["ecran"])
                    self.assertGreater(bulles[0]["hauteur"], 10)
                    largeur_page, ecran = page.evaluate(LARGEUR_JS)
                    self.assertLessEqual(largeur_page, ecran, "bulle de %s : page plus large que l'écran" % ot)
                    self.assertEqual(page.evaluate(AUDIT_TEXTES_JS, "#contenu sup.wiki-ref"), [], ot)
                # Un second toucher sur le même numéro la referme ; une seule bulle à la fois ; toucher la bulle la referme
                dernier = boutons.nth(boutons.count() - 1)
                toucher(dernier)
                self.assertEqual(page.locator("#contenu .wiki-ref-bulle").count(), 0)
                toucher(boutons.first)
                toucher(dernier)
                self.assertEqual([b["ot"] for b in page.evaluate(bulle_js)], [dernier.evaluate("(b) => b.closest('sup').dataset.ot")])
                toucher(page.locator("#contenu .wiki-ref-bulle"))
                self.assertEqual(page.locator("#contenu .wiki-ref-bulle").count(), 0)
                # Au clavier : Entrée l'ouvre, Échap la referme
                boutons.first.focus()
                page.keyboard.press("Enter")
                self.assertEqual(page.locator("#contenu .wiki-ref-bulle").count(), 1)
                page.keyboard.press("Escape")
                self.assertEqual(page.locator("#contenu .wiki-ref-bulle").count(), 0)
                self.verifier_sans_piege()

    def test_listes_d_interventions_dans_l_ordre_avec_leur_statut(self):
        """Une page ne crée que ses 10 premières interventions (D101) ; « Voir les n autres interventions » crée les autres ;
        ordre et statuts du calcul Python, les ouvertes en tête (D113)."""
        for largeur, telephone in ((1440, False), (375, True)):
            with self.subTest(largeur=largeur):
                page = self.ouvrir("technicien", largeur=largeur, hauteur=900, telephone=telephone, base=True)
                calcul = self.calcul()
                for identifiant in ("TEC-0002", "EQ-0001", "PANNE-S01"):
                    attendues = calcul.entite(identifiant, "technicien", MAINTENANT)["sections"]["interventions"]
                    lu = self.lire(identifiant)
                    self.assertEqual([i[:2] for i in lu["interventions"]], [[o["id"], o["statut"]] for o in attendues[:10]], identifiant)
                    self.assertEqual(page.locator("#wiki-interventions .wiki-intervention[hidden]").count(), 0)
                    self.assertEqual(lu["voirAutres"], "Voir les %d autres interventions" % (len(attendues) - 10))
                    page.click("#wiki-interventions .wiki-voir-autres")
                    lu = page.evaluate(ENTITE_JS)
                    self.assertEqual([i[:2] for i in lu["interventions"]], [[o["id"], o["statut"]] for o in attendues], identifiant)
                    self.assertIsNone(lu["voirAutres"])
                ouverts = [o["statut"] in OUVERTS for o in calcul.entite("EQ-0001", "technicien", MAINTENANT)["sections"]["interventions"]]
                self.assertEqual(ouverts[0], True)
                self.assertEqual(ouverts, sorted(ouverts, reverse=True))

    def test_tous_les_liens_menent_a_une_page_qui_s_affiche(self):
        """Chaque lien #/wiki/<id> d'une page de chaque type mène à une page que le profil voit (aucune « Page
        introuvable ») ; les autres liens vont vers des écrans connus ; quelques-uns sont suivis pour de bon."""
        for profil in ("demandeur", "technicien", "responsable"):
            page = self.ouvrir(profil, base=True)
            pages = [i for t, i in SIX.items() if profil != "demandeur" or t not in ("technicien", "intervention")]
            for identifiant in pages + ["WP-0008", "EQ-0001"]:
                with self.subTest(profil=profil, page=identifiant):
                    self.lire(identifiant)
                    for bouton in page.locator("#contenu .wiki-voir-autres").all():
                        bouton.click()
                    liens = page.evaluate("Array.from(new Set(Array.from(document.querySelectorAll('#contenu .wiki-page a[href]')).map((a) => a.getAttribute('href'))))")
                    vers_wiki = [l for l in liens if l.startswith("#/wiki/") and l[7:] not in LISTES]
                    self.assertTrue(vers_wiki)
                    introuvables = page.evaluate("""([liens, profil]) => liens.filter((lien) =>
                      !Wiki.entite(decodeURIComponent(lien.slice('#/wiki/'.length)), { profil }))""", [vers_wiki, profil])
                    self.assertEqual(introuvables, [])
                    autres = [l for l in liens if l not in vers_wiki and not (l.startswith("#/wiki/") and l[7:] in LISTES)]
                    self.assertEqual([l for l in autres if not LIENS_HORS_WIKI.match(l)], [])
                    if profil == "demandeur":
                        self.assertEqual([l for l in autres if l.startswith(("#/ot/", "#/magasin/"))], [])
            # Suivis pour de bon : un lien de chaque type de cible depuis la page de PO-02
            self.lire("EQ-0005")
            cibles = page.evaluate("""() => { const vus = new Map();
              Array.from(document.querySelectorAll('#contenu .wiki-lecture a[href^="#/wiki/"]')).forEach((a) => {
                const id = decodeURIComponent(a.getAttribute('href').slice('#/wiki/'.length)); const type = id.replace(/-.*/, '');
                if (!vus.has(type)) vus.set(type, id); });
              return Array.from(vus.values()); }""")
            self.assertGreaterEqual(len(cibles), 4 if profil == "demandeur" else 5)
            for identifiant in cibles:
                with self.subTest(profil=profil, suivi=identifiant):
                    self.aller_entite(identifiant)
                    self.assertEqual(page.locator("#contenu .wiki-introuvable").count(), 0, identifiant)

    def test_fiche_a_droite_sur_pc_et_au_dessus_sur_telephone(self):
        for largeur, hauteur, telephone in ((1440, 900, False), (375, 812, True)):
            with self.subTest(largeur=largeur):
                self.ouvrir("responsable", largeur=largeur, hauteur=hauteur, telephone=telephone, base=True)
                for identifiant in ("EQ-0005", "OT-2026-0214"):
                    lu = self.lire(identifiant)
                    fiche, lecture = lu["ficheRect"], lu["lectureRect"]
                    if telephone:
                        self.assertLessEqual(fiche["bas"], lecture["haut"] + 1, identifiant)          # au-dessus
                        if lu["alertesRect"]:
                            self.assertLessEqual(lu["alertesRect"]["bas"], fiche["haut"] + 1)         # sous la consignation
                    else:
                        self.assertGreaterEqual(fiche["gauche"], lecture["droite"], identifiant)      # à droite
                        self.assertLess(fiche["haut"], lecture["bas"])

    def test_machines_pannes_et_techniciens_de_la_demo_comme_le_calcul_python(self):
        """Toutes les machines, pannes et techniciens de la démo et dix articles : fiche et interventions de la page égales au
        calcul Python indépendant ; aucune erreur à l'affichage."""
        page = self.ouvrir("responsable")
        calcul = self.calcul()
        identifiants = (sorted(calcul.par_id) + [p["id"] for p in calcul.liste_pannes()] + sorted(calcul.articles)[:10]
                        + sorted(t["id"] for t in calcul.tables["techniciens"]))
        self.assertGreater(len(identifiants), 50)
        for identifiant in identifiants:
            with self.subTest(entite=identifiant):
                lu = self.lire(identifiant)
                attendue = calcul.entite(identifiant, "responsable", MAINTENANT)
                self.assertEqual([f for f in lu["faits"] if f[0] != "Sous-ensembles"], faits_attendus(attendue["faits"]))
                if "interventions" in attendue["sections"]:
                    self.assertEqual([i[0] for i in lu["interventions"]], [o["id"] for o in attendue["sections"]["interventions"]][:10])
                if attendue["type"] == "machine" and attendue["sections"]["sousEnsembles"]:
                    sous = [f for f in lu["faits"] if f[0] == "Sous-ensembles"][0]
                    self.assertEqual(sous[1], ", ".join(page.evaluate("(id) => Donnees.trouver('equipements', id).repere", m["equipementId"])
                                                        for m in attendue["sections"]["sousEnsembles"]))
                self.assertEqual(lu["crochets"], 0)

    def test_pieges_restent_du_texte(self):
        page = self.ouvrir("responsable", base=True)
        page.evaluate(ECRIRE_JS, ["equipements", "EQ-0005", {"consignation": CONSIGNATION_PIEGEE}])
        page.evaluate(ECRIRE_JS, ["ordres_travail", "OT-2026-0098", {"titre": "<b>Titre</b> piégé " + PIEGE}])
        lu = self.lire("WP-0003")
        self.assertEqual(lu["consignation"]["texte"], CONSIGNATION_PIEGEE)       # au caractère près
        self.assertEqual(page.locator("#wiki-entete img, #wiki-entete script, #wiki-entete .wiki-consignation-texte *").count(), 0)
        # Le titre piégé d'un OT cité : dans la bulle du petit numéro et dans « Références », du texte
        bulle = page.get_attribute('#contenu sup.wiki-ref[data-ot="OT-2026-0098"] a', "title")
        self.assertIn("<b>Titre</b> piégé " + PIEGE, bulle)
        self.assertIn("<b>Titre</b> piégé", page.inner_text("#wiki-references"))
        self.verifier_sans_piege()
        # Titre et phrase piégés d'un savoir-faire
        lu = self.lire("WP-0006")
        self.assertEqual(lu["h1Brut"], TITRE_PIEGE)
        self.assertIn("<script>window.__piege = 4</script>", lu["textes"][0]["phrases"][0]["texte"])
        self.assertEqual(page.locator("#contenu .wiki-phrase *:not(sup):not(sup *)").count(), 0)
        self.verifier_sans_piege()
        # Observation piégée dans « À trancher », titre piégé dans un lien
        lu = self.lire("EQ-0005")
        self.assertEqual(lu["contradictions"][1]["observation"], OBSERVATION_PIEGEE)
        self.assertIn([plat(TITRE_PIEGE), "#/wiki/WP-0006"], [l for t in self.lire("ART-0016")["textes"] for p in t["phrases"] for l in p["liens"]])
        self.verifier_sans_piege()
        # Identifiant piégé dans l'adresse ; page archivée, inconnue, d'un type retiré (page de mode, sous-page de machine,
        # composant libre — relecture de T137, m4) : « Page introuvable »
        self.aller("#/wiki/%3Cimg%20src%3Dx%20onerror%3D%22window.__piege%3D1%22%3E", ".wiki-introuvable")
        self.assertIn('<img src=x onerror="window.__piege=1">', page.inner_text("#contenu .vide"))
        libre = page.evaluate("Donnees.trouver('wiki_pages', 'WP-0014')")
        self.assertEqual((libre["type"], libre["article_id"], libre["statut"]), ("composant", "", "active"))
        calcul = self.calcul()
        for identifiant in ("WP-0009", "WP-0010", "WP-0011", "WP-0014", "EQ-9999", "PANNE-S00"):
            with self.subTest(identifiant=identifiant):
                lu = self.lire(identifiant)
                self.assertEqual((lu.get("introuvable"), lu["h1"]), (True, "Page introuvable"))
                self.assertEqual(page.get_attribute('#contenu a.btn[href="#/wiki"]', "href"), "#/wiki")
                self.assertIsNone(self.entite(identifiant, "responsable"))
                self.assertIsNone(calcul.entite(identifiant, "responsable", MAINTENANT))
        self.verifier_sans_piege()


# ---------------------------------------------------------------------------
# « À trancher » : décisions du responsable (D107)
# ---------------------------------------------------------------------------

class TestTrancher(CasWiki):

    def decisions(self):
        return [e for e in self.page.evaluate("Donnees.lignes('wiki_journal')") if e["nature"] == "décision"]

    def test_l_ancien_reste_puis_les_deux_sont_vrais_puis_le_nouveau_remplace(self):
        page = self.ouvrir("responsable", base=True)
        self.lire("EQ-0005")
        # « L'ancien reste », avec une note
        premiere = page.locator('.wiki-contradiction[data-rang="0"]')
        premiere.locator("textarea").fill("Vu avec le fournisseur")
        premiere.locator('button[data-decision="ancien"]').click()
        page.wait_for_function("document.querySelectorAll('.wiki-contradiction').length === 1")
        self.assertEqual(page.get_attribute(".wiki-contradiction", "data-rang"), "1")
        entree = page.evaluate("Donnees.trouver('wiki_journal', 'WJ-00002')")
        fermee = json.loads(entree["contradictions"])[0]
        self.assertEqual((fermee["statut"], fermee["decision"], fermee["note"]), ("fermée", "ancien", "Vu avec le fournisseur"))
        decisions = self.decisions()
        self.assertEqual(len(decisions), 1)
        self.assertEqual((decisions[0]["statut"], decisions[0]["ot_id"], decisions[0]["motif"]),
                         ("appliquée", "OT-2026-0214", "Vu avec le fournisseur"))
        trace = json.loads(decisions[0]["contradictions"])[0]
        self.assertEqual((trace["entree"], trace["rang"], trace["decision"]), ("WJ-00002", 0, "ancien"))
        # Les petits numéros suivent : la contradiction restante cite OT-2025-0030 en premier
        self.assertEqual(page.evaluate(ENTITE_JS)["sups"][0], [1, "OT-2025-0030"])
        # « Les deux sont vrais », sans note : l'encadré disparaît (après le repos qui suit une décision)
        page.wait_for_selector(".wiki-page:not([data-occupe])")
        page.click('.wiki-contradiction[data-rang="1"] button[data-decision="les deux"]')
        page.wait_for_function("!document.querySelector('#wiki-a-trancher')")
        self.assertEqual([json.loads(d["contradictions"])[0]["decision"] for d in self.decisions()], ["ancien", "les deux"])
        self.assertEqual(self.entite("EQ-0005", "responsable")["aTrancher"], [])
        self.assertEqual(page.evaluate(ENTITE_JS)["alertes"], ["wiki-consignation"])
        # Le texte de la page n'a pas changé (une contradiction n'écrase rien)
        self.assertEqual(page.evaluate("Donnees.trouver('wiki_pages', 'WP-0001').texte"), TEXTE_PO02)
        # « Le nouveau remplace » : décision écrite, puis l'écriture à la main de la page
        self.lire("WP-0003")
        page.evaluate("""() => { window.__routes = [];
            window.addEventListener('hashchange', (e) => window.__routes.push(new URL(e.newURL).hash)); }""")
        page.click('.wiki-contradiction button[data-decision="nouveau"]')
        page.wait_for_function("window.__routes.includes('#/wiki-ecrire/WP-0003')")
        self.assertEqual(json.loads(page.evaluate("Donnees.trouver('wiki_journal', 'WJ-00003')")["contradictions"])[0]["decision"],
                         "nouveau")
        self.assertEqual(len(self.decisions()), 3)
        # Le suivi du wiki (accueil) suit
        self.aller_accueil()
        self.assertEqual(page.inner_text('.wiki-mini[data-suivi="contradictions"] .wiki-mini-nombre').strip(), "0")

    def test_deux_clics_rapides_ne_tranchent_qu_une_contradiction(self):
        """Relecture de T119 : un clic sur une décision, puis aussitôt un autre (double clic, ou carte arrivée sous le
        pointeur après le réaffichage) : une seule contradiction est tranchée."""
        page = self.ouvrir("responsable", base=True)
        self.lire("EQ-0005")
        self.assertEqual(page.locator(".wiki-contradiction").count(), 2)
        page.locator('.wiki-contradiction[data-rang="0"] button[data-decision="ancien"]').click()
        page.locator('.wiki-contradiction button[data-decision="ancien"]').last.click()
        page.wait_for_selector(".wiki-page:not([data-occupe])")
        self.assertEqual(len(self.decisions()), 1)
        self.assertEqual(len(self.entite("EQ-0005", "responsable")["aTrancher"]), 1)

    def test_boutons_absents_hors_responsable(self):
        for profil in ("technicien", "demandeur"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                for identifiant in ("EQ-0005", "WP-0003"):
                    lu = self.lire(identifiant)
                    self.assertGreater(len(lu["contradictions"]), 0)
                    self.assertEqual(page.locator("#contenu .wiki-trancher, #contenu button[data-decision], #contenu textarea").count(), 0)
                    self.assertEqual(lu["attente"], [])
                    self.assertNotIn("wiki-modifier", [a[0] for a in lu["actions"]])
                    self.assertEqual(page.locator("#wiki-ecrire-savoir-faire").count(), 0)


# ---------------------------------------------------------------------------
# Consignation de la page d'une machine (CS98) ; lien depuis la fiche équipement
# ---------------------------------------------------------------------------

class TestConsignation(CasWiki):

    def test_consignation_identique_au_champ_de_la_fiche(self):
        page = self.ouvrir("technicien")
        for equipement in ("EQ-0001", "EQ-0026", "EQ-0028"):
            with self.subTest(equipement=equipement):
                champ = page.evaluate("(id) => Donnees.trouver('equipements', id).consignation", equipement)
                self.aller_page(equipement)
                bloc = page.evaluate("""() => { const e = document.querySelector('#wiki-consignation .wiki-consignation-texte');
                    return { texte: e.textContent, lignes: e.innerText.split('\\n').length, espaces: getComputedStyle(e).whiteSpace,
                             enfants: e.children.length }; }""")
                self.assertGreater(champ.count("\n"), 2)
                self.assertEqual(bloc["texte"], champ)
                self.assertEqual(bloc["lignes"], champ.count("\n") + 1)       # retours à la ligne gardés à l'écran
                self.assertEqual(bloc["espaces"], "pre-wrap")
                self.assertEqual(bloc["enfants"], 0)
                self.assertNotIn("[IA]", page.inner_text("#wiki-consignation"))

    def test_consignation_piegee_document_et_absence(self):
        page = self.ouvrir("responsable")
        nom = page.evaluate("() => App.adaptateur.ecrireDocument('consignation-cp01.pdf', new Blob(['%PDF-1.4'], { type: 'application/pdf' }))")
        page.evaluate(ECRIRE_JS, ["equipements", "EQ-0001", {"consignation": CONSIGNATION_PIEGEE, "document": nom}])
        self.aller_page("EQ-0001")
        page.wait_for_selector("#wiki-consignation .wiki-lien-document")
        texte = page.evaluate("() => document.querySelector('#wiki-consignation .wiki-consignation-texte').textContent")
        self.assertEqual(texte, CONSIGNATION_PIEGEE)                     # au caractère près : CRLF, tabulation, espaces
        self.assertEqual(page.locator("#wiki-consignation img, #wiki-consignation script").count(), 0)
        self.assertEqual(page.locator("#wiki-consignation .wiki-consignation-texte *").count(), 0)
        self.assertIsNone(page.evaluate("window.__piege === undefined ? null : window.__piege"))
        lien = page.locator("#wiki-consignation .wiki-lien-document")
        self.assertTrue(lien.get_attribute("href").startswith("blob:"))
        self.assertEqual(lien.get_attribute("target"), "_blank")
        self.assertIn("consignation-cp01.pdf", lien.inner_text())
        self.assertEqual(page.locator("#wiki-modifier-consignation").count(), 0)
        # Document introuvable : son nom et la mention, pas de lien
        page.evaluate(ECRIRE_JS, ["equipements", "EQ-0001", {"document": "plan-absent.pdf"}])
        self.aller_accueil()
        self.aller_page("EQ-0001")
        page.wait_for_selector("#wiki-consignation .wiki-document .badge")
        self.assertEqual(plat(page.inner_text("#wiki-consignation .wiki-consignation-document")),
                         "Document : plan-absent.pdf fichier introuvable")
        # Ni texte ni document : message d'absence et, au responsable, le lien de modification de la fiche
        page.evaluate(ECRIRE_JS, ["equipements", "EQ-0001", {"consignation": "  \n ", "document": ""}])
        self.aller_accueil()
        self.aller_page("EQ-0001")
        self.assertEqual(page.inner_text("#wiki-consignation .wiki-sans-consignation").strip(), SANS_CONSIGNATION)
        self.assertEqual(page.get_attribute("#wiki-modifier-consignation", "href"), "#/equipement/EQ-0001/modifier")
        self.assertEqual(page.locator("#wiki-consignation .wiki-consignation-texte").count(), 0)
        page.click("#wiki-modifier-consignation")
        page.wait_for_selector("#contenu form")
        self.assertEqual(page.evaluate("location.hash"), "#/equipement/EQ-0001/modifier")
        # Document seul (texte vide) : message d'absence ET le document
        page.evaluate(ECRIRE_JS, ["equipements", "EQ-0001", {"document": nom}])
        self.aller_page("EQ-0001")
        page.wait_for_selector("#wiki-consignation .wiki-lien-document")
        self.assertEqual(page.inner_text("#wiki-consignation .wiki-sans-consignation").strip(), SANS_CONSIGNATION)

    def test_en_tete_d_un_savoir_faire_commun_a_plusieurs_machines(self):
        """D116 (T141, point 6) : un savoir-faire rattaché à une machine et lié dans son texte à une autre montre en tête la
        liste de ces machines, chacune avec un lien vers sa page (où est sa consignation), sans consignation recopiée ;
        rattaché à sa seule machine (même liée dans son texte), sa consignation comme avant."""
        page = self.ouvrir("technicien")
        page.evaluate("""async () => { const NL = String.fromCharCode(10);
          const titre = (id) => { const e = Donnees.trouver('equipements', id); return e.repere + ' — ' + e.designation; };
          await Donnees.modifier('wiki_pages', (lignes) => {
            lignes.push({ id: 'WP-0901', type: 'savoir-faire', titre: 'Remplacer une garniture mécanique', equipement_id: 'EQ-0001',
              texte: '## Particularités par machine' + NL + '- [[' + titre('EQ-0001') + ']] : accès direct [OT-2025-0001]' + NL
                + '- [[' + titre('EQ-0026') + ']] : accès par le dessus [OT-2025-0006]', liens: 'EQ-0001;EQ-0026', version: '1',
              statut: 'active', origine: 'IA' });
            lignes.push({ id: 'WP-0902', type: 'savoir-faire', titre: 'Purger la machine', equipement_id: 'EQ-0001',
              texte: '## Étapes' + NL + '- Purger [OT-2025-0001]', liens: 'EQ-0001', version: '1', statut: 'active', origine: 'IA' });
          }); }""")
        reperes = page.evaluate("() => ['EQ-0001', 'EQ-0026'].map((id) => Donnees.trouver('equipements', id).repere)")
        lu = self.lire("WP-0901")
        self.assertEqual(lu["alertes"][0], "wiki-entete")
        self.assertEqual((lu["consignation"]["titre"], lu["consignation"]["phrase"], lu["consignation"]["texte"]),
                         ("Consignation des équipements", PHRASE_SAVOIR_FAIRE, None))
        self.assertEqual(lu["consignation"]["equipements"], [[reperes[0], "#/wiki/EQ-0001"], [reperes[1], "#/wiki/EQ-0026"]])
        self.assertIn("Ce savoir-faire sert sur ces machines ; la consignation de chacune est en tête de sa page :",
                      page.inner_text("#wiki-entete"))
        seul = self.lire("WP-0902")
        self.assertEqual((seul["consignation"]["titre"], seul["consignation"]["texte"]),
                         ("Consignation de " + reperes[0], page.evaluate("Donnees.trouver('equipements', 'EQ-0001').consignation")))

    def test_absence_de_consignation_sans_lien_pour_technicien_et_demandeur(self):
        for profil in ("technicien", "demandeur"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil)
                self.aller_page("EQ-0031")                          # PE-01 : aucune consignation dans la démo
                self.assertEqual(page.inner_text("#wiki-consignation .wiki-sans-consignation").strip(), SANS_CONSIGNATION)
                self.assertEqual(page.locator("#wiki-modifier-consignation").count(), 0)
                self.assertEqual(page.locator('#contenu a[href$="/modifier"]').count(), 0)

    def test_lien_wiki_de_la_fiche_equipement(self):
        for profil in ("demandeur", "technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil)
                self.aller("#/equipement/EQ-0005", "#lien-wiki-equipement")
                lien = page.locator("#lien-wiki-equipement")
                self.assertEqual(lien.count(), 1)
                self.assertEqual(lien.get_attribute("href"), "#/wiki/EQ-0005")
                self.assertEqual(lien.inner_text().strip(), "Wiki de cet équipement")
                self.assertTrue(page.evaluate("""() => { const lien = document.querySelector('#lien-wiki-equipement');
                    return lien.closest('.entete-page') !== null && lien.compareDocumentPosition(document.querySelector('.parc-consignation'))
                      === Node.DOCUMENT_POSITION_FOLLOWING; }"""))
                # Hors du wiki, seul ce lien porte une classe ou un identifiant wiki sur la fiche
                self.assertEqual(page.evaluate("""() => Array.from(document.querySelectorAll('#contenu *'))
                    .filter((e) => /wiki/.test(e.id + ' ' + (typeof e.className === 'string' ? e.className : ''))).map((e) => e.id)"""),
                    ["lien-wiki-equipement"])
                lien.click()
                page.wait_for_selector('.wiki-page[data-equipement="EQ-0005"]')
                page.click("#wiki-lien-fiche")
                page.wait_for_function("location.hash === '#/equipement/EQ-0005'")
                page.wait_for_selector("#lien-wiki-equipement")


# ---------------------------------------------------------------------------
# Recherche : depuis la page, l'onglet Préparation d'un OT, la saisie d'une DI
# ---------------------------------------------------------------------------

class TestRecherche(CasWiki):

    def test_recherche_depuis_la_page_portees_delai_et_surlignage(self):
        page = self.ouvrir("technicien")
        self.aller_page("EQ-0023")                                  # CV-02 : jumeau CV-03
        section = page.locator(".wiki-page .wiki-recherche")
        self.assertEqual(section.get_attribute("data-equipement"), "EQ-0023")
        self.assertEqual(section.get_attribute("role"), "search")
        self.assertIsNotNone(section.get_attribute("data-hors-saisie"))
        self.assertEqual(section.locator(".wiki-recherche-aide").inner_text().strip(),
                         "Dans les interventions clôturées et les pages du wiki : cet équipement d'abord, puis ceux de même "
                         "marque et modèle, puis le reste du parc.")
        champ = section.locator("input")
        self.assertEqual(champ.get_attribute("type"), "search")
        self.assertIsNotNone(champ.get_attribute("data-hors-saisie"))
        self.assertEqual(champ.input_value(), "")
        self.assertEqual(page.inner_text(".wiki-page .wiki-resultats").strip(), "")
        delai = page.evaluate(DELAI_JS, [".wiki-page .wiki-recherche-champ", "capteur encrassé"])
        self.assertGreaterEqual(delai, 290)
        self.assertLess(delai, 2000)
        lus = self.verifier_resultats(".wiki-page .wiki-recherche", "capteur encrassé", "EQ-0023")
        self.assertEqual(lus[0]["portee"], "equipement")
        self.assertIn("modele", [b["portee"] for b in lus])
        self.assertGreater(lus[0]["marques"], 0)
        # Frappes rapprochées : une seule recherche, 300 ms après la dernière
        page.evaluate("""() => { window.__recherches = 0; const origine = Wiki.rechercher;
            Wiki.rechercher = function () { window.__recherches += 1; return origine.apply(this, arguments); }; }""")
        page.locator(".wiki-page .wiki-recherche-champ").fill("")
        page.locator(".wiki-page .wiki-recherche-champ").press_sequentially("bruit", delay=40)
        page.wait_for_function("window.__recherches >= 1")
        page.wait_for_timeout(400)
        self.assertEqual(page.evaluate("window.__recherches"), 1)
        # « Voir les n autres résultats »
        self.chercher(".wiki-page .wiki-recherche", "arrêt capteur nettoyage")
        bloc = page.locator(".wiki-page .wiki-portee").first
        bouton = bloc.locator(".wiki-voir-plus")
        if bouton.count():
            bouton.click()
            self.assertEqual(bloc.locator(".wiki-trouve[hidden]").count(), 0)
            self.assertEqual(bouton.get_attribute("aria-expanded"), "true")
            bouton.click()
            self.assertGreater(bloc.locator(".wiki-trouve[hidden]").count(), 0)
        else:
            self.fail("la recherche devrait rendre plus de 5 résultats sur CV-02")
        # Rien trouvé ; Entrée cherche tout de suite
        champ = page.locator(".wiki-page .wiki-recherche-champ")
        champ.fill("zzqxw")
        champ.press("Enter")
        self.assertEqual(plat(page.inner_text(".wiki-page .wiki-rien")), "Rien trouvé pour « zzqxw ».")
        champ.fill("")
        page.wait_for_timeout(400)
        self.assertEqual(page.inner_text(".wiki-page .wiki-resultats").strip(), "")

    def test_recherche_depuis_l_onglet_preparation_d_un_ot(self):
        page = self.ouvrir("responsable")
        ot = page.evaluate("""() => Donnees.lignes('ordres_travail').filter((o) => !/^Clôturé|Annulé/.test(o.statut))
            .find((o) => Wiki.rechercher(o.titre, { equipementId: o.equipement_id }).portees.some((p) => p.resultats.length))""")
        self.assertIsNotNone(ot, "aucun OT ouvert de la démo dont le titre trouve un résultat")
        self.aller("#/ot/" + ot["id"], ".ot-onglets")
        page.click(".onglet[data-onglet='preparation']")
        page.wait_for_selector("#form-preparation")
        section = page.locator("#contenu .wiki-recherche")
        self.assertEqual(section.count(), 1)
        self.assertEqual(section.locator(".wiki-recherche-titre").inner_text().strip(), "Chercher dans l'historique")
        # Pré-rempli avec le titre, sans le repère de l'équipement (« PO-02 — Fuite… » → « Fuite… ») : sinon « po »
        # et « 02 » seraient cherchés partout (relecture de l'orchestrateur).
        repere = page.evaluate("(id) => Donnees.trouver('equipements', id).repere", ot["equipement_id"])
        attendu = " ".join(ot["titre"].replace(repere, " ").split()).lstrip(" —–:-").strip()
        self.assertIn(repere, ot["titre"], "le jeu de démo met le repère en tête des titres d'OT")
        self.assertEqual(section.locator("input").input_value(), attendu)
        self.assertNotIn(repere, section.locator("input").input_value())
        self.assertEqual(section.get_attribute("data-equipement"), ot["equipement_id"])
        self.assertTrue(page.evaluate("""() => { const s = document.querySelector('#contenu .wiki-recherche');
            const f = document.querySelector('#form-preparation');
            return !f.contains(s) && s.compareDocumentPosition(f) === Node.DOCUMENT_POSITION_FOLLOWING
              && s.closest('[data-hors-saisie]') === s && s.closest('.panneau-onglet, [role=tabpanel]') !== null; }"""))
        self.attendre_resultats("#contenu .wiki-recherche")
        self.verifier_resultats("#contenu .wiki-recherche", attendu, ot["equipement_id"], montres=3)
        # Hors du wiki : dans la fiche de l'OT, seul ce bloc porte une classe wiki
        self.assertEqual(page.evaluate("""() => Array.from(document.querySelectorAll('#contenu [class*="wiki"], #contenu [id*="wiki"]'))
            .filter((e) => !e.closest('.wiki-recherche')).length"""), 0)
        # Une recherche tapée n'est pas une saisie du formulaire de préparation
        section.locator("input").fill("fuite")
        page.wait_for_timeout(350)
        self.assertNotEqual(page.get_attribute("#form-preparation", "data-modifie"), "1")
        # Le technicien a le même champ (onglet en lecture)
        page = self.ouvrir("technicien")
        self.aller("#/ot/" + ot["id"], ".ot-onglets")
        page.click(".onglet[data-onglet='preparation']")
        page.wait_for_selector("#contenu .wiki-recherche")
        self.attendre_resultats("#contenu .wiki-recherche")
        self.verifier_resultats("#contenu .wiki-recherche", attendu, ot["equipement_id"], montres=3)

    def test_recherche_dans_la_saisie_d_une_di(self):
        page = self.ouvrir("demandeur")
        self.aller("#/di/nouvelle", ".di-formulaire")
        self.assertEqual(page.locator(".wiki-recherche, .wiki-recherche-demande").count(), 0)   # pas d'équipement : rien
        page.fill(".selecteur-recherche input[type=search]", "PO-02")
        page.click(".selecteur-option[data-id='EQ-0005']")
        bloc = page.locator(".di-formulaire .wiki-recherche-demande")
        self.assertEqual(bloc.count(), 1)
        self.assertEqual(bloc.locator(".wiki-recherche-titre").inner_text().strip(), "Déjà vu sur cette machine ?")
        self.assertEqual(bloc.get_attribute("data-equipement"), "EQ-0005")
        self.assertEqual(bloc.locator("input").input_value(), "")
        self.assertTrue(page.evaluate("""() => { const b = document.querySelector('.wiki-recherche-demande');
            return b.closest('.di-etape') === document.querySelector('input[name=symptome]').closest('.di-etape'); }"""))
        # Le symptôme saisi pré-remplit la recherche (frappe, puis une suggestion)
        page.fill("input[name=symptome]", "fuite garniture")
        self.assertEqual(bloc.locator("input").input_value(), "fuite garniture")
        self.attendre_resultats(".wiki-recherche-demande")
        lus = self.verifier_resultats(".wiki-recherche-demande", "fuite garniture", "EQ-0005", demandeur=True, montres=3)
        self.assertEqual(lus[0]["portee"], "equipement")
        # Numéros d'OT en texte, sans lien (les pages du wiki, elles, sont des liens pour tous)
        self.assertEqual({n for b in lus for n, t in zip(b["numeros"], b["types"]) if t == "ot"}, {"B"})
        page.click(".di-puce[data-symptome='Fuite']")
        self.assertEqual(bloc.locator("input").input_value(), "Fuite")
        # Entrée dans le champ de recherche n'envoie pas la demande
        bloc.locator("input").press("Enter")
        self.attendre_resultats(".wiki-recherche-demande")
        self.assertEqual(page.locator(".di-numero").count(), 0)
        self.assertEqual(page.locator(".di-formulaire .champ.en-erreur").count(), 0)
        # Tapé à la main : la recherche ne suit plus le symptôme
        bloc.locator("input").fill("bruit")
        page.fill("input[name=symptome]", "Fuite d'eau au joint")
        self.assertEqual(bloc.locator("input").input_value(), "bruit")
        # Changer d'équipement : le champ part, puis revient pour le nouvel équipement, pré-rempli
        page.click(".selecteur-changer")
        self.assertEqual(page.locator(".wiki-recherche-demande").count(), 0)
        page.fill(".selecteur-recherche input[type=search]", "CP-01")
        page.click(".selecteur-option[data-id='EQ-0001']")
        self.assertEqual(page.get_attribute(".wiki-recherche-demande", "data-equipement"), "EQ-0001")
        self.assertEqual(page.input_value(".wiki-recherche-demande input"), "Fuite d'eau au joint")
        # La demande part normalement, sans rien de la recherche
        page.click("label.tuile:has(input[value='gêne'])")
        page.click(".di-envoyer")
        page.wait_for_selector(".di-numero")
        demande = page.evaluate("(id) => Donnees.trouver('demandes', id)", page.inner_text(".di-numero"))
        self.assertEqual((demande["equipement_id"], demande["symptome"]), ("EQ-0001", "Fuite d'eau au joint"))

    def test_di_les_liens_s_ouvrent_dans_un_nouvel_onglet(self):
        """Un clic sur un résultat de « Déjà vu sur cette machine ? » ne fait jamais perdre la DI tapée."""
        for profil in ("technicien", "demandeur"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                self.aller("#/di/nouvelle?equipement=EQ-0005", ".di-formulaire .wiki-recherche-demande")
                page.fill("input[name=symptome]", "garniture accouplement")
                self.attendre_resultats(".wiki-recherche-demande")
                liens = page.evaluate("""() => Array.from(document.querySelectorAll('.wiki-recherche-demande .wiki-resultats a')).map((a) =>
                    ({ href: a.getAttribute('href'), cible: a.getAttribute('target'), rel: a.getAttribute('rel'),
                       titre: a.getAttribute('title'), texte: a.textContent }))""")
                self.assertTrue(any(l["href"].startswith("#/wiki/") for l in liens), liens)
                self.assertEqual(any(l["href"].startswith("#/ot/") for l in liens), profil == "technicien")
                for lien in liens:
                    self.assertEqual((lien["cible"], lien["rel"]), ("_blank", "noopener"), lien)
                    self.assertEqual(lien["titre"], "%s (%s)" % (lien["texte"], NOUVEL_ONGLET))
                # Le clic ouvre un autre onglet ; la saisie reste là
                with self.contexte.expect_page() as attente:
                    page.locator('.wiki-recherche-demande .wiki-resultats a[href^="#/wiki/"]').first.click()
                attente.value.close()
                self.assertEqual(page.input_value("input[name=symptome]"), "garniture accouplement")
                self.assertTrue(page.evaluate("location.hash").startswith("#/di/nouvelle"))
                self.assertEqual(page.locator(".di-formulaire").count(), 1)

    def test_di_avec_equipement_dans_l_adresse_et_liens_du_technicien(self):
        page = self.ouvrir("technicien")
        self.aller("#/di/nouvelle?equipement=EQ-0001", ".di-formulaire .wiki-recherche-demande")
        bloc = page.locator(".wiki-recherche-demande")
        self.assertEqual(bloc.get_attribute("data-equipement"), "EQ-0001")
        page.fill("input[name=symptome]", "échauffement filtre")
        self.attendre_resultats(".wiki-recherche-demande")
        lus = self.verifier_resultats(".wiki-recherche-demande", "échauffement filtre", "EQ-0001", montres=3)
        self.assertGreater(sum(b["liensOt"] for b in lus), 0)
        # Hors du wiki : dans le formulaire, seul ce bloc porte une classe wiki
        self.assertEqual(page.evaluate("""() => Array.from(document.querySelectorAll('#contenu [class*="wiki"], #contenu [id*="wiki"]'))
            .filter((e) => !e.closest('.wiki-recherche-demande')).length"""), 0)

    def test_hors_du_wiki_seules_les_lignes_d_appel_prevues(self):
        """Ajouts hors du wiki (interface gelée) : une ligne dans l'onglet Préparation, deux dans la saisie d'une DI,
        une dans la fiche équipement."""
        attendus = {
            "ordres-onglets.js": ["Wiki.champRecherche({ equipementId: ot.equipement_id, texteInitial: ot.titre, titre: 'Chercher dans l\\'historique', montres: 3 })"],
            "demandes-signaler.js": ["Wiki.poserRechercheDemande(champSymptome, selecteur.valeur());"] * 2,
            "parc-fiche.js": ['<a id="lien-wiki-equipement" href="#/wiki/${idUrl}">${UI.icone(\'wiki\')}Wiki de cet équipement</a>'],
        }
        for fichier, morceaux in attendus.items():
            with self.subTest(fichier=fichier):
                lignes = [l for l in (RACINE / "js" / "modules" / fichier).read_text(encoding="utf-8").splitlines()
                          if re.search("wiki", l, re.IGNORECASE)]
                self.assertEqual(len(lignes), len(morceaux), lignes)
                for ligne, morceau in zip(lignes, morceaux):
                    self.assertIn(morceau, ligne)


# ---------------------------------------------------------------------------
# Sous-pages (§20.4 ; refonte 2 : celles d'un savoir-faire seulement)
# ---------------------------------------------------------------------------

class TestSousPages(CasWiki):
    """Sous-page d'un savoir-faire : « Sous-page de <mère> » (lien), consignation reprise de sa mère (deux rattachements :
    sous-page → savoir-faire → texte de PO-02), la mère liste ses sous-pages ; mère archivée nommée sans lien ; les
    anciennes sous-pages de machine et pages de mode (types retirés) ne s'affichent plus et s'archivent."""

    def test_sous_page_d_un_savoir_faire_pour_les_trois_profils(self):
        for profil in ("demandeur", "technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                consignation = page.evaluate("Donnees.trouver('equipements', 'EQ-0005').consignation")
                lu = self.lire("WP-0008")
                self.assertEqual((lu["type"], lu["h1Brut"], lu["dataMere"]), ("savoir-faire", TITRE_SP_ALIGNER, "WP-0007"))
                self.assertEqual(lu["mere"], {"texte": "Sous-page de " + TITRE_ALIGNER, "lien": [TITRE_ALIGNER, "#/wiki/WP-0007"],
                                              "archivee": None})
                self.assertEqual(page.evaluate("document.querySelector('#wiki-mere').previousElementSibling.tagName"), "H1")
                self.assertEqual(lu["alertes"], ["wiki-entete"])
                self.assertEqual((lu["consignation"]["titre"], lu["consignation"]["phrase"], lu["consignation"]["texte"]),
                                 ("Consignation de PO-02", PHRASE_SAVOIR_FAIRE, consignation))
                self.assertEqual(lu["faits"], [["Rattaché à", TITRE_PO02, "#/wiki/EQ-0005"],
                                               ["Sous-page de", TITRE_ALIGNER, "#/wiki/WP-0007"]])
                self.assertEqual(faits_attendus(self.entite("WP-0008", profil)["faits"]),
                                 faits_attendus(self.calcul().entite("WP-0008", profil, MAINTENANT)["faits"]))
                self.assertEqual([(t["rubrique"], t["origine"]) for t in lu["textes"]], [("Pièces et outillage", ORIGINE_IA % "18/10/2026")])
                self.assertEqual(lu["sousPages"], [])
                self.assertEqual([a[0] for a in lu["actions"]], ["wiki-modifier"] if profil == "responsable" else [])
                # La mère liste ses sous-pages ; un savoir-faire sans sous-page n'a pas la section
                lu = self.lire("WP-0007")
                self.assertIsNone(lu["mere"])
                self.assertEqual(lu["sousPages"], [["WP-0008", TITRE_SP_ALIGNER, "#/wiki/WP-0008"]])
                self.assertEqual(self.lire("WP-0003")["sousPages"], [])
                # Rattaché à la page de PO-02 : dans les savoir-faire de la machine, pas sa sous-page
                self.assertEqual(sorted(self.lire("EQ-0005")["savoirFaire"]), ["WP-0003", "WP-0006", "WP-0007"])
                self.verifier_sans_piege()
        # De la mère à la sous-page, puis de la sous-page à la mère
        self.lire("WP-0007")
        page.click('#wiki-sous-pages a[href="#/wiki/WP-0008"]')
        page.wait_for_selector('.wiki-page[data-page="WP-0008"] #wiki-mere')
        page.click("#wiki-mere a")
        page.wait_for_selector('.wiki-page[data-page="WP-0007"] #wiki-sous-pages')

    def test_mere_archivee_et_types_retires(self):
        page = self.ouvrir("responsable", base=True)
        consignation = page.evaluate("Donnees.trouver('equipements', 'EQ-0005').consignation")
        # Liste des savoir-faire : la sous-page et sa mère ; les types retirés et l'archivée n'y sont pas
        self.aller("#/wiki/savoir-faire", ".wiki-liste-entites[data-liste=savoir-faire] li")
        lignes = page.evaluate("""() => Array.from(document.querySelectorAll('.wiki-liste-entites li')).map((li) => [li.dataset.id,
          Array.from(li.querySelectorAll('.wiki-ligne-sous a')).map((a) => [a.textContent, a.getAttribute('href')])])""")
        self.assertEqual(sorted(l[0] for l in lignes), SAVOIR_FAIRE_ACTIFS)
        self.assertEqual(dict(lignes)["WP-0008"][-1], [TITRE_ALIGNER, "#/wiki/WP-0007"])
        # Anciennes sous-page de machine et page de mode : plus de page ; leur écriture dit « type de page retiré »
        for identifiant in ("WP-0010", "WP-0011"):
            with self.subTest(identifiant=identifiant):
                self.assertEqual(self.lire(identifiant).get("introuvable"), True)
                self.aller("#/wiki-ecrire/" + identifiant, '.wj-ecrire[data-page="%s"] .wj-type-retire' % identifiant)
        # Mère archivée : nommée sans lien, « page archivée » ; la sous-page garde sa consignation
        page.evaluate(ECRIRE_JS, ["wiki_pages", "WP-0007", {"statut": "archivée"}])
        lu = self.lire("WP-0008")
        self.assertEqual(lu["mere"], {"texte": "Sous-page de " + TITRE_ALIGNER + " page archivée", "lien": None, "archivee": TITRE_ALIGNER})
        self.assertEqual(lu["consignation"]["texte"], consignation)
        self.assertEqual(self.lire("WP-0007").get("introuvable"), True)

    def test_modifier_une_sous_page(self):
        page = self.ouvrir("responsable", base=True)
        self.lire("WP-0008")
        page.click("#wiki-modifier")
        page.wait_for_selector('.wj-ecrire[data-page="WP-0008"]')
        self.assertEqual(page.query_selector_all(".wj-type-retire"), [])
        avant = page.input_value("#wj-texte")
        apres = avant + "\n- Serrer le comparateur sans forcer [OT-2026-0214]"
        page.fill("#wj-texte", apres)
        page.click(".wj-enregistrer")
        page.wait_for_function("location.hash === '#/wiki/WP-0008'")
        page.wait_for_selector('.wiki-page[data-page="WP-0008"] .wiki-page-grille')
        ligne = page.evaluate("Donnees.trouver('wiki_pages', 'WP-0008')")
        self.assertEqual((ligne["texte"], ligne["version"], ligne["rattache_a"], ligne["equipement_id"], ligne["statut"]),
                         (apres, "2", "WP-0007", "", "active"))
        lu = page.evaluate(ENTITE_JS)
        self.assertEqual(lu["mere"]["lien"], [TITRE_ALIGNER, "#/wiki/WP-0007"])
        self.assertIn("Serrer le comparateur sans forcer", page.inner_text("#wiki-texte"))
        self.assertIn(", puis modifié à la main — validé par", lu["textes"][0]["origine"])
        self.assertEqual(lu["consignation"]["titre"], "Consignation de PO-02")


# ---------------------------------------------------------------------------
# Encyclopédie : 1440 et 375 px, zones tactiles, contrastes, réseau
# ---------------------------------------------------------------------------

class TestAffichageEncyclopedie(CasWiki):

    def pages_parcourues(self, profil):
        """Une page de chaque type (celles du profil), plus une sous-page et une page sans contradiction si la base est posée."""
        ids = self.page.evaluate("""(profil) => {
          const premier = (type) => { const liste = Wiki.listeEntites(type, { profil: 'responsable' }) || [];
            return liste.length ? (liste[0].lien || liste[0].id) : null; };
          return [premier('panne'), 'EQ-0005', 'ART-0016', premier('savoir-faire')].concat(profil === 'demandeur' ? []
            : ['TEC-0001', Wiki.listeEntites('intervention', { profil: 'responsable' })[0].id, 'OT-2026-0214']); }""", profil)
        if self.page.evaluate("Boolean(Donnees.trouver('wiki_pages', 'WP-0008'))"):
            ids += ["WP-0008", "EQ-0001", "WP-0003"]
        return [i for i in ids if i]

    def parcourir(self, verifier, profil):
        """Accueil, recherche (tout ouvert), six listes, pages des six types (« Voir les n autres » ouverts)."""
        page = self.page
        self.aller_accueil()
        verifier("#contenu", "accueil")
        self.chercher_accueil("pompe")
        for bouton in page.locator("#wiki-trouves .wiki-voir-autres, #wiki-trouves .wiki-voir-plus").all():
            bouton.click()
        verifier("#contenu", "accueil, recherche")
        for liste in LISTES:
            self.aller("#/wiki/" + liste, '.wiki-liste-entites[data-liste="%s"]' % liste)
            verifier("#contenu", "liste " + liste)
        for ident in self.pages_parcourues(profil):
            self.aller_entite(ident)
            verifier("#contenu", "page " + ident)
            boutons = page.locator("#contenu .wiki-page .wiki-voir-autres").all()
            for bouton in boutons:
                bouton.click()
            if boutons:
                verifier("#contenu", "page " + ident + ", listes ouvertes")

    def verifier_largeur(self, ou):
        largeur, ecran = self.page.evaluate(LARGEUR_JS)
        self.assertLessEqual(largeur, ecran, "%s : page plus large que l'écran (%s > %s)" % (ou, largeur, ecran))

    def test_1440_et_375_px_sans_defilement_horizontal_et_zones_de_48_px(self):
        for largeur, hauteur, telephone in ((1440, 900, False), (375, 812, True)):
            for profil in ("responsable", "technicien", "demandeur"):
                with self.subTest(largeur=largeur, profil=profil):
                    self.ouvrir(profil, largeur=largeur, hauteur=hauteur, telephone=telephone, base=True)

                    def verifier(racine, ou):
                        self.verifier_largeur(ou)
                        if telephone:
                            zones = self.page.evaluate(ZONES_JS, racine)
                            self.assertGreater(len(zones), 0, ou)
                            self.assertEqual([z for z in zones if z[2] < 47.5], [], "%s : zones de moins de 48 px" % ou)
                    self.parcourir(verifier, profil)

    def test_contrastes_aa_en_theme_clair_et_sombre(self):
        for theme in ("clair", None):
            for profil, largeur, hauteur, telephone in (("responsable", 1440, 900, False), ("demandeur", 375, 812, True)):
                with self.subTest(theme=theme or "sombre", profil=profil):
                    page = self.ouvrir(profil, largeur=largeur, hauteur=hauteur, theme=theme, telephone=telephone, base=True)
                    self.assertEqual(page.evaluate("document.documentElement.dataset.theme || null"), theme)

                    def verifier(racine, ou):
                        page.wait_for_timeout(100)
                        self.assertEqual(page.evaluate(AUDIT_TEXTES_JS, racine), [], ou)
                    self.parcourir(verifier, profil)

    def test_focus_visible_sur_la_recherche_et_les_briques(self):
        page = self.ouvrir("responsable", largeur=1440, hauteur=900)
        self.aller_accueil()
        for selecteur in ("#wiki-champ-accueil", '#wiki-phrase-resume a[data-liste="machines"]', ".wiki-brique", ".wiki-mini"):
            with self.subTest(selecteur=selecteur):
                page.focus(selecteur)
                page.keyboard.press("Shift+Tab")
                page.keyboard.press("Tab")
                style = page.evaluate("""(s) => { const e = document.activeElement; const c = getComputedStyle(e);
                  return [e.matches(s), e.matches(':focus-visible'), c.outlineStyle, parseFloat(c.outlineWidth)]; }""", selecteur)
                self.assertEqual(style[:3], [True, True, "solid"])
                self.assertGreaterEqual(style[3], 2)

    def test_aucun_appel_reseau_pour_afficher_ou_chercher(self):
        page = self.ouvrir("responsable", base=True)
        requetes = []
        page.on("request", lambda requete: requetes.append(requete.url))
        page.evaluate("""() => { window.__appels = [];
            const noter = (nom) => function () { window.__appels.push(nom); throw new Error('appel réseau interdit : ' + nom); };
            window.fetch = noter('fetch'); XMLHttpRequest.prototype.open = noter('xhr');
            navigator.sendBeacon = noter('beacon'); window.WebSocket = noter('websocket'); window.EventSource = noter('eventsource'); }""")
        self.parcourir(lambda racine, ou: None, "responsable")
        self.assertEqual(page.evaluate("window.__appels"), [])
        self.assertEqual([u for u in requetes if not u.startswith(("blob:", "data:"))], [])

    def test_aucune_requete_api_en_mode_serveur(self):
        """Mode serveur : afficher l'accueil, les listes et les pages des six types et chercher ne fait aucune requête /api/
        (la surveillance des autres postes, /api/versions toutes les 20 s, n'est pas un affichage)."""
        for motif in ERREURS_SERVEUR:
            self.autoriser_erreur(motif)
        with ServeurPrevo() as serveur:
            self.contexte.close()
            self.contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1440, "height": 900})
            preregler_profil(self.contexte, "responsable")
            self.page = self.contexte.new_page()
            self.surveiller(self.page)
            self.page.goto(serveur.url + "/")
            attendre_pret(self.page, 30000)
            self.assertEqual(self.page.evaluate("App.mode"), "serveur")
            # Un savoir-faire, écrit avant de compter (le wiki de la démo est vide) : la sixième page
            self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => { lignes.push({ id: 'WP-0001', type: 'savoir-faire',
              titre: 'Changer la garniture de PO-02', equipement_id: 'EQ-0005', texte: '## Étapes\\n- Repérer l\\'accouplement [OT-2026-0098]',
              version: '1', origine: 'manuel', valide_par: 'Paul Martin', valide_le: '2026-10-15 10:00', statut: 'active' }); return true; },
              { action: 'test des écrans du wiki' })""")
            self.assertEqual(self.page.evaluate("Wiki.entite('WP-0001', { profil: 'responsable' }).type"), "savoir-faire")
            requetes = []
            self.page.on("request", lambda requete: requetes.append(requete.url))
            self.parcourir(lambda racine, ou: self.assertEqual(
                [u for u in requetes if "/api/" in u and "/api/versions" not in u], [], ou), "responsable")
            self.assertIn("WP-0001", self.pages_parcourues("responsable"))


# ---------------------------------------------------------------------------
# Affichage des champs de recherche : page d'une machine, fiche équipement, DI, OT
# ---------------------------------------------------------------------------

class TestAffichage(CasWiki):

    def parcourir(self, verifier, profil):
        """Pages de machines de la démo (résultats de recherche ouverts), fiche équipement ; puis DI et OT (blocs wiki)."""
        page = self.page
        self.poser_base()
        for equipement in ("EQ-0001", "EQ-0023", "EQ-0031"):
            self.aller_page(equipement)
            self.chercher(".wiki-page .wiki-recherche", "capteur filtre")
            for bouton in page.locator(".wiki-page .wiki-voir-plus").all():
                bouton.click()
            verifier("#contenu", "page " + equipement)
        self.aller("#/equipement/EQ-0001", "#lien-wiki-equipement")
        verifier("p:has(> #lien-wiki-equipement)", "fiche équipement")
        self.aller("#/di/nouvelle?equipement=EQ-0005", ".wiki-recherche-demande")
        page.fill("input[name=symptome]", "garniture")
        self.attendre_resultats(".wiki-recherche-demande")
        verifier(".wiki-recherche-demande", "saisie d'une DI")
        if profil != "demandeur":
            ot = page.evaluate("() => Wiki.entite('EQ-0001', { profil: 'technicien' }).sections.interventions[2].id")
            self.aller("#/ot/" + ot, ".ot-onglets")
            page.click(".onglet[data-onglet='preparation']")
            self.attendre_resultats("#contenu .wiki-recherche")
            verifier("#contenu .wiki-recherche", "onglet Préparation")

    def verifier_largeur(self, ou):
        largeur, ecran = self.page.evaluate(LARGEUR_JS)
        self.assertLessEqual(largeur, ecran, "%s : page plus large que l'écran (%s > %s)" % (ou, largeur, ecran))

    def test_1440_px_sans_defilement_horizontal(self):
        for profil in ("responsable", "demandeur"):
            with self.subTest(profil=profil):
                self.ouvrir(profil, largeur=1440, hauteur=900)
                self.parcourir(lambda racine, ou: self.verifier_largeur(ou), profil)

    def test_375_px_sans_defilement_horizontal_et_zones_de_48_px(self):
        for profil in ("responsable", "demandeur"):
            with self.subTest(profil=profil):
                self.ouvrir(profil, largeur=375, hauteur=812, telephone=True)

                def verifier(racine, ou):
                    self.verifier_largeur(ou)
                    zones = self.page.evaluate(ZONES_JS, racine)
                    self.assertGreater(len(zones), 0, ou)
                    self.assertEqual([z for z in zones if z[2] < 47.5], [], "%s : zones de moins de 48 px" % ou)
                self.parcourir(verifier, profil)

    def test_theme_clair_contraste_aa_des_textes(self):
        for profil in ("responsable", "demandeur"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, largeur=1440, hauteur=900, theme="clair")
                self.assertEqual(page.evaluate("document.documentElement.dataset.theme"), "clair")

                def verifier(racine, ou):
                    page.wait_for_timeout(100)
                    self.assertEqual(page.evaluate(AUDIT_TEXTES_JS, racine), [], ou)
                self.parcourir(verifier, profil)

    def test_theme_clair_contraste_aa_au_telephone(self):
        page = self.ouvrir("technicien", largeur=375, hauteur=812, theme="clair", telephone=True)

        def verifier(racine, ou):
            page.wait_for_timeout(100)
            self.assertEqual(page.evaluate(AUDIT_TEXTES_JS, racine), [], ou)
        self.parcourir(verifier, "technicien")

    def test_aucune_requete_reseau_pour_afficher_ou_chercher(self):
        page = self.ouvrir("responsable")
        requetes = []
        page.on("request", lambda requete: requetes.append(requete.url))
        page.evaluate("""() => { window.__appels = [];
            const noter = (nom) => function () { window.__appels.push(nom); throw new Error('appel réseau interdit : ' + nom); };
            window.fetch = noter('fetch'); XMLHttpRequest.prototype.open = noter('xhr');
            navigator.sendBeacon = noter('beacon'); window.WebSocket = noter('websocket'); window.EventSource = noter('eventsource'); }""")
        self.parcourir(lambda racine, ou: None, "responsable")
        for texte in ("bruit", "ne démarre pas", "fuite", "température", "garniture"):
            page.evaluate("(t) => Wiki.rechercher(t, {})", texte)
        self.assertEqual(page.evaluate("window.__appels"), [])
        self.assertEqual([u for u in requetes if not u.startswith(("blob:", "data:"))], [])


# ---------------------------------------------------------------------------
# Jeu de charge (D101 ; relecture de T136, C1) : afficher, pas seulement calculer
# ---------------------------------------------------------------------------

class TestJeuDeCharge(CasWiki):
    """Jeu de charge (outils/generer_demo.py --volume 500,5000 : 500 machines, 5 000 OT), mode serveur, responsable, PC et
    téléphone : l'accueil, chaque liste et la page la plus lourde de chaque type s'affichent en moins de 500 ms (médiane
    de trois affichages, de l'adresse à l'image peinte, mise en page comprise), sans créer des dizaines de milliers
    d'éléments (avant : 63 065 pour la liste des interventions, 5 s ; relecture de T137 : 14 443 pour la chronologie du
    stock créée en entier d'un coup). Pages mesurées (relecture de T137, critique) : la machine et la panne qui ont le
    plus d'OT, l'article qui a le plus de mouvements de stock, le technicien qui a le plus d'interventions (les siennes
    et celles où il a pointé du temps), l'intervention qui a le plus de temps pointés, de mouvements et d'opérations."""

    ELEMENTS_MAX = 5000

    def test_accueil_listes_et_pages_en_moins_de_500_ms(self):
        for motif in ERREURS_SERVEUR:
            self.autoriser_erreur(motif)
        with tempfile.TemporaryDirectory() as dossier:
            resultat = subprocess.run([sys.executable, str(RACINE / "outils" / "generer_demo.py"), "--volume", "500,5000",
                                       "--sortie", dossier, "--sans-js"], capture_output=True, cwd=RACINE)
            self.assertEqual(resultat.returncode, 0, resultat.stdout.decode("utf-8", "replace"))
            with ServeurPrevo(source=dossier) as serveur:
                for largeur, hauteur, telephone in ((1440, 900, False), (375, 812, True)):
                    with self.subTest(largeur=largeur):
                        self.mesurer(serveur, largeur, hauteur, telephone)

    def mesurer(self, serveur, largeur, hauteur, telephone):
        self.contexte.close()
        options = {"locale": "fr-FR", "viewport": {"width": largeur, "height": hauteur}}
        if telephone:
            options.update(is_mobile=True, has_touch=True)
        self.contexte = self.navigateur.new_context(**options)
        preregler_profil(self.contexte, "responsable")
        page = self.page = self.contexte.new_page()
        self.surveiller(page)
        page.goto(serveur.url + "/")
        attendre_pret(page, 60000)
        self.assertEqual(page.evaluate("App.mode"), "serveur")
        total = page.evaluate("Donnees.lignes('ordres_travail').length")       # 5 000, plus les préventifs échus créés à l'ouverture
        self.assertGreaterEqual(total, 5000)
        if not page.evaluate("Boolean(Donnees.trouver('wiki_pages', 'WP-9001'))"):
            page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => { lignes.push({ id: 'WP-9001', type: 'savoir-faire',
              titre: 'Geste de charge', equipement_id: Donnees.lignes('equipements')[0].id, texte: '## Étapes\\n- Un geste [' +
              Donnees.lignes('ordres_travail')[0].id + ']', version: '1', origine: 'manuel', valide_par: 'Responsable',
              valide_le: '2026-10-15 10:00', statut: 'active' }); return true; }, { action: 'test de charge du wiki' })""")
        lourdes = page.evaluate(LOURDES_JS)
        ids = [lourdes[t][0] for t in ("machine", "panne", "article", "technicien", "intervention")] + ["WP-9001"]
        sys.stderr.write("\n  [charge %d px] pages les plus lourdes : %s\n" % (largeur, lourdes))
        # Bien les plus lourdes du jeu de charge : des milliers de mouvements, des centaines d'OT
        self.assertGreater(lourdes["article"][1], 1000)
        self.assertGreater(lourdes["panne"][1], 100)
        self.assertGreater(lourdes["technicien"][1], 100)
        self.assertTrue(all(page.evaluate("(id) => Boolean(Wiki.entite(id, { profil: 'responsable' }))", i) for i in ids))
        routes = [("#/wiki", "#wiki-accueil")]
        routes += [("#/wiki/" + liste, '.wiki-liste-entites[data-liste="%s"]' % liste) for liste in LISTES]
        routes += [("#/wiki/" + encoder(i), '.wiki-page[data-page="%s"] .wiki-page-grille' % i) for i in ids]
        bilan = []
        for route, selecteur in routes:
            durees = []
            for _ in range(3):
                page.evaluate("location.hash = '#/apropos'")
                page.wait_for_function("() => !document.querySelector('#contenu .wiki')")
                page.wait_for_timeout(100)
                mesure = page.evaluate(MESURE_JS, [route, selecteur])
                durees.append(mesure["duree"])
            bilan.append("%s %.0f" % (route, statistics.median(durees)))
            with self.subTest(largeur=largeur, route=route):
                self.assertLess(statistics.median(durees), BUDGET_MS, durees)
                self.assertLess(mesure["elements"], self.ELEMENTS_MAX, route)
        sys.stderr.write("\n  [charge %d px] %s\n" % (largeur, ", ".join(bilan)))
        # « Voir les n autres » de la liste des interventions crée les autres au clic
        page.evaluate("location.hash = '#/wiki/interventions'")
        page.wait_for_selector(".wiki-liste-entites[data-liste=interventions] .wiki-voir-autres")
        selecteur = ".wiki-carte-intervention" if telephone else "#wiki-interventions tbody tr"
        self.assertEqual(page.locator(selecteur).count(), 40 if telephone else 100)
        if not telephone:
            # Trier par N° ordonne les 5 000 OT, puis ne crée que les 100 premières lignes, en moins de 500 ms (m5)
            tri = page.evaluate("""() => new Promise((resoudre) => { const t0 = performance.now();
              document.querySelector('#wiki-interventions th .tri[data-cle="id"]').click();
              document.body.getBoundingClientRect();
              requestAnimationFrame(() => setTimeout(() => resoudre({ duree: performance.now() - t0,
                ids: Array.from(document.querySelectorAll('#wiki-interventions tbody tr')).map((tr) => tr.cells[1].textContent.trim()) }), 0)); })""")
            tous = page.evaluate("Donnees.lignes('ordres_travail').map((ot) => ot.id)")
            self.assertEqual(tri["ids"], sorted(tous, key=lambda i: tuple(int(n) for n in re.findall(r"\d+", i)))[:100])
            self.assertLess(tri["duree"], BUDGET_MS)
            sys.stderr.write("  [charge 1440 px] tri des %d interventions par N° : %.0f ms\n" % (len(tous), tri["duree"]))
        page.click(".wiki-liste-entites .wiki-voir-autres")
        page.wait_for_function("([s, n]) => document.querySelectorAll(s).length === n", arg=[selecteur, total])


if __name__ == "__main__":
    unittest.main()
