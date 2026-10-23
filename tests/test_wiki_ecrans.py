"""Écrans de lecture du wiki de maintenance (tâche T100 ; socle du lot 6 refondu, T110 ; réécrits en T119 —
ARCHITECTURE.md §20.9 ; CS98, CS103, CS106).

Toujours la démo (index.html en file://, « Essayer avec les données de démo »), horloge du navigateur fixée à la
date de référence de la démo (2026-10-19 : dates non décalées, pannes des 12 derniers mois stables). Profils :
responsable, technicien (TEC-0001), demandeur (Lucie Martin). Une base d'essai (BASE_JS) pose sur la démo onze
lignes de wiki_pages (les quatre types, ancrées ou libres, une archivée, un titre piégé) et quatorze entrées de
wiki_journal (validées avec contradictions ouvertes, l'une venue d'un OT antérieur, une fermée ; à valider ; en
file ; refusées suivies ou non d'une relance ; à refaire ; rejetée ; manuelle refusée). Ce qui est vérifié :
    accueil     #/wiki, l'encyclopédie (refonte 2, §20.12, T136) : « Ce que l'atelier sait », phrase-résumé dont chaque
                nombre mène à sa liste (sans les techniciens pour le demandeur), « Tiré de N interventions clôturées »,
                champ de recherche ; briques (icône du type, nombre, ligne utile, lien) ; dernières interventions et
                pannes les plus fréquentes (liens encodés, PANNE-… compris) — nombres égaux à
                Wiki.accueilEncyclopedie ET à un calcul fait ici sur les tables ; « Suivi du wiki » au responsable
                seulement (à valider, à trancher, en échec : nombres recalculés ici, discrets à zéro, liens vers
                #/wiki-journal?vue=…, « Traiter la file » et le journal) ; titres piégés : du texte ;
    listes      #/wiki/<liste> des six types pour les trois profils (techniciens et interventions : « réservé » au
                demandeur) : fil d'Ariane, nombre, chaque élément en lien vers sa page (identifiant encodé), égaux au
                calcul fait ici ou à Wiki.listeEntites ; machines par lieu (racine commune retirée), sous-ensembles
                sous leur machine ; pannes par nombre de cas ; articles en tableau filtrable (texte, état du stock),
                en cartes au téléphone ; interventions ouvertes en tête, statut sur chaque ligne ; pages Panne,
                Technicien, Intervention (rendu minimal en attendant T137 : titre, faits, « Ouvrir la fiche OT ») ;
    recherche   de l'accueil : entités groupées par type (Wiki.chercherEntites, machines recalculées ici), selon le
                profil (jamais un technicien ni une intervention pour le demandeur), puis les résultats plein texte
                (Wiki.rechercher) ; « Voir les n autres », « Rien trouvé », Entrée ;
    pages       #/wiki/<id> des quatre types : en-tête (type, titre, lien vers la fiche selon le profil), en-tête
                des savoir-faire (consignation de la fiche à l'octet, phrase de Prévo), couche calculée séparée
                du texte (égale à Wiki.page), texte par rubrique, bandeau d'origine (IA, manuel, IA et manuel),
                « Aucun texte validé pour l'instant. », OT cités en liens (en texte pour le demandeur), liens
                vers les pages (titre inconnu : texte), « Pages qui renvoient ici » exact, « Modifier » et
                propositions en attente au responsable seulement ; page d'équipement : contenu égal à
                Wiki.pageEquipement pour les 28 pages de la démo (pannes, pièces, dernières interventions, même
                marque et modèle), consignation à l'octet ; page archivée ou inconnue : « Page introuvable » ;
    trancher    « À trancher » vu par les trois profils (ce que dit la page avec ses OT, ce que dit le nouvel OT,
                « Observation antérieure aux faits de la page »), note et boutons au responsable seulement ;
                « L'ancien reste », « Les deux sont vrais » : la contradiction disparaît, une entrée « décision »
                est écrite ; « Le nouveau remplace » mène à #/wiki-ecrire/<page> ;
    sous-pages  (T131, base à part) « Sous-page de <mère> » en lien sous le titre, consignation de l'équipement de la
                mère en tête (à l'octet, phrase de Prévo), aucune couche calculée, fiche de la mère ; sous-pages de
                composant et de savoir-faire (en-tête de la mère, même rattachée par la page de l'équipement) ; mère
                archivée nommée sans lien ; la mère liste ses sous-pages après le texte (liens, ordre alphabétique
                français, archivée exclue) ; liste des savoir-faire (sous-pages et leur mère) ; trois profils ;
                titres piégés ;
                « Modifier » ; 1440 et 375 px, zones de 48 px, contrastes AA en thème clair et sombre ;
    piège       HTML dans un titre, une phrase, une observation, une consignation, un compte rendu, l'adresse :
                du texte, rien n'est exécuté ;
    recherche   depuis la page (portées équipement, modèle, parc),
                l'onglet Préparation d'un OT et la saisie d'une DI (« Déjà vu sur cette machine ? » : liens dans un
                nouvel onglet, la DI tapée reste) ; résultats = Wiki.rechercher ; hors du wiki, seuls les ajouts ;
    affichage   1440 et 375 px sans défilement horizontal, zones tactiles ≥ 48 px au téléphone, contrastes AA en
                thème clair (audit de test_poste) ; aucune requête réseau pour afficher ou chercher ; encyclopédie
                (accueil, recherche, listes, pages) : trois profils, contrastes AA en clair et en sombre, focus
                visible, aucune requête /api/ en mode serveur.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_ecrans.py" -v
"""
import json
import math
import re
import unicodedata
import unittest
import urllib.parse

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier
from test_poste import AUDIT_TEXTES_JS

HEURE_FIXE = "2026-10-19T09:00:00"
PROFILS = {"demandeur": ("Lucie Martin", ""), "technicien": ("", "TEC-0001"), "responsable": ("", "")}
MENTION = "Statistique de l'historique, pas un diagnostic"
MENTION_PISTE = "Peu de cas : à prendre comme une piste."
SANS_CONSIGNATION = "Aucune consignation saisie pour cet équipement"
SANS_TEXTE = "Aucun texte validé pour l'instant."
PHRASE_SAVOIR_FAIRE = "Ce savoir-faire ne remplace pas la consignation de l'équipement"
PIEGE = '<img src=x onerror="window.__piege = 1"><script>window.__piege = 2</script><b>gras</b>'
CONSIGNATION_PIEGEE = ("  1. Couper le sectionneur " + PIEGE + "\r\n2. Purger & vérifier « 0 bar »\n\n"
                       "   3. Cadenas personnel\t(clé sur soi)\n")
COUCHE_EQUIPEMENT = ["wiki-couche-titre", "wiki-consignation", "wiki-recherche", "wiki-pannes", "wiki-pieces", "wiki-dernieres"]
TYPES = {"équipement": "Équipement", "composant": "Composant", "mode": "Mode de défaillance", "savoir-faire": "Savoir-faire"}
NOUVEL_ONGLET = "s'ouvre dans un nouvel onglet"

# ---------------------------------------------------------------------------------------------------
# Base d'essai posée sur la démo : pages des quatre types et entrées du journal
# ---------------------------------------------------------------------------------------------------

MODELE = "claude-sonnet-5-5"
VALIDEUR = "Paul Martin"
TITRE_PO02 = "PO-02 — Pompe centrifuge eau de refroidissement"
TITRE_KIT = "Kit garniture mécanique PO-02"
TITRE_PIEGE = '<img src=x onerror="window.__piege = 3">Régler <b>gras</b>'
COLONNES_PAGES = ("id;type;titre;cle;equipement_id;article_id;cause_code;rattache_a;texte;ot_cites;liens;version;origine;"
                  "modele;derniere_entree;valide_par;valide_le;cree_le;modifie_le;statut").split(";")
COLONNES_JOURNAL = ("id;nature;ot_id;date_intervention;statut;anterieure;ordre;pages;changements;contradictions;raisons;"
                    "modele;essais;cree_le;traite_le;decide_par;decide_le;motif").split(";")
MOTIF_CITATION = re.compile(r"\[(OT-\d{4}-\d{4,})\]")
MOTIF_LIEN = re.compile(r"\[\[([^\[\]]+)\]\]")

TEXTE_PO02 = "\n".join([
    "## Ce qui revient",
    "- La garniture mécanique fuit côté accouplement [OT-2025-0010] [OT-2025-0044]",
    "- Le raccord de refoulement se desserre [OT-2025-0030]",
    "## Ce qui a réglé le problème",
    "- Le remplacement du [[Kit garniture mécanique PO-02]] a arrêté la fuite [OT-2026-0026]",
    "## À surveiller",
    "- L'alignement de l'accouplement, voir [[Changer la garniture de PO-02]] et [[Fuite de garniture]] [OT-2026-0214]",
    "## Astuces",
    "- Une ancienne fiche citait [[Page disparue]] [OT-2026-0098]",
])
TEXTE_MODE = ("## Symptômes\n- Goutte à goutte sous la garniture [OT-2025-0010]\n"
              "## Équipements concernés\n- Surtout la [[" + TITRE_PO02 + "]] [OT-2026-0133]")
TEXTE_SF = ("## Étapes\n- Repérer la position de l'accouplement avant le démontage [OT-2026-0098]\n"
            "## Pièges\n- Ne jamais monter la garniture à sec [OT-2026-0133] [OT-2026-0058]")
TEXTE_KIT = ("## Défaillances\n- La garniture fuit quand l'accouplement est désaligné [OT-2026-0214]\n"
             "## Montage et remplacement\n- Suivre [[Changer la garniture de PO-02]] [OT-2026-0098]\n"
             "- Régler au besoin : voir [[" + TITRE_PIEGE + "]] [OT-2026-0098]")
TEXTE_JOINT = "## Signes d'usure\n- Le joint durcit et se fissure [OT-2025-0030]"
TEXTE_DESSERRAGE = ("## Causes\n- Les vibrations desserrent le raccord de la [[" + TITRE_PO02 + "]] [OT-2025-0030] [OT-2026-0082]\n"
                    "## Remèdes\n- Changer le [[Joint torique de bride]] [OT-2026-0082]")
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
    page_wiki("WP-0001", "équipement", TITRE_PO02, TEXTE_PO02, "IA", "ART-0016;WP-0003;WP-0002", "2026-10-14 08:00",
              equipement_id="EQ-0005"),
    page_wiki("WP-0002", "mode", "Fuite de garniture", TEXTE_MODE, "manuel", "EQ-0005", "2026-10-16 09:00", cause_code="C01"),
    page_wiki("WP-0003", "savoir-faire", "Changer la garniture de PO-02", TEXTE_SF, "IA et manuel", "", "2026-10-17 11:15",
              equipement_id="EQ-0005"),
    page_wiki("WP-0004", "composant", TITRE_KIT, TEXTE_KIT, "IA", "WP-0003;WP-0011", article_id="ART-0016"),
    page_wiki("WP-0005", "composant", "Joint torique de bride", TEXTE_JOINT, "IA"),
    page_wiki("WP-0006", "mode", "Desserrage des raccords", TEXTE_DESSERRAGE, "IA", "EQ-0005;WP-0005"),
    page_wiki("WP-0007", "savoir-faire", "Remonter le kit de garniture", "## Étapes\n- Graisser légèrement les joints [OT-2026-0058]",
              "manuel", article_id="ART-0016"),
    page_wiki("WP-0008", "savoir-faire", "Purger le pressostat", "## Étapes\n- Purger avant de relever la mesure [OT-2026-0098]",
              "manuel", equipement_id="EQ-0031"),
    page_wiki("WP-0009", "mode", "Ancienne page", "## Causes\n- Ancienne page sur la [[" + TITRE_PO02 + "]] [OT-2025-0010]",
              "IA", "EQ-0005", statut="archivée"),
    page_wiki("WP-0010", "savoir-faire", "Changer le joint torique", "## Étapes\n- Nettoyer la portée du joint [OT-2025-0030]",
              "IA", rattache_a="WP-0005"),
    page_wiki("WP-0011", "savoir-faire", TITRE_PIEGE, TEXTE_PIEGE, "IA", equipement_id="EQ-0005"),
]

OBSERVATION_PIEGEE = "Le raccord était serré <img src=x onerror=\"window.__piege = 5\"> : c'est le joint qui était cuit."
CONTRADICTIONS_PO02 = [
    {"page": TITRE_PO02, "pageCle": "EQ:EQ-0005", "phrase": "La garniture mécanique fuit côté accouplement",
     "observation": "La fuite vient du désalignement de l'accouplement, pas de l'usure de la garniture.",
     "ot": ["OT-2026-0214"], "statut": "ouverte"},
    {"page": TITRE_PO02, "pageCle": "EQ:EQ-0005", "phrase": "Le raccord de refoulement se desserre [OT-2025-0030]",
     "observation": OBSERVATION_PIEGEE, "ot": ["OT-2026-0214"], "statut": "ouverte"},
]
CONTRADICTIONS_MODE = [
    {"page": "Fuite de garniture", "pageCle": "WP:WP-0002", "phrase": "Goutte à goutte sous la garniture",
     "observation": "La goutte venait du raccord de refoulement, pas de la garniture.", "ot": ["OT-2025-0030"],
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
    entree("WJ-00003", "validée", "OT-2025-0030", ordre="3", anterieure="1", contradictions=CONTRADICTIONS_MODE,
           decide_le="2026-10-16 09:00"),
    entree("WJ-00004", "à valider", "OT-2026-0082", ordre="4", changements=[{
        "page": "WP-0001", "cle": "EQ:EQ-0005", "type": "équipement", "titre": TITRE_PO02, "creation": False, "version_avant": 1,
        "avant": TEXTE_PO02, "apres": TEXTE_PO02 + "\n- Le raccord tient avec un joint neuf [OT-2026-0082]"}]),
    entree("WJ-00005", "à valider", "OT-2026-0058", ordre="5", changements=[{
        "cle": "TITRE:graisser la garniture", "type": "savoir-faire", "titre": "Graisser la garniture", "creation": True,
        "version_avant": 0, "avant": "", "apres": "## Étapes\n- Graisser la garniture [OT-2026-0058]"}]),
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

# Titre → identifiant canonique (liens [[titre]] de la base d'essai) ; « Page disparue » n'existe pas.
RESOLUTIONS = {TITRE_PO02: "EQ-0005", TITRE_KIT: "ART-0016", "Changer la garniture de PO-02": "WP-0003",
               "Fuite de garniture": "WP-0002", "Joint torique de bride": "WP-0005", TITRE_PIEGE: "WP-0011"}
ORIGINE_IA = "Rédigé avec l'IA (claude-sonnet-5-5) à partir des OT cités — validé par Paul Martin le %s"
ORIGINE_MANUEL = "Écrit par Paul Martin le %s"
ORIGINE_MIXTE = "Rédigé avec l'IA (claude-sonnet-5-5) à partir des OT cités, puis modifié à la main — validé par Paul Martin le %s"

# La base remplace le wiki figé de la démo (T122).
BASE_JS = """async ([pages, journal]) => {
  await Donnees.modifier('wiki_pages', (lignes) => { lignes.splice(0, lignes.length, ...pages); }, { journal: false });
  await Donnees.modifier('wiki_journal', (lignes) => { lignes.splice(0, lignes.length, ...journal); }, { journal: false });
}"""

# --- lectures du DOM ---------------------------------------------------------------------------------

# Encyclopédie (refonte 2, §20.12, T136) : accueil, listes, recherche de l'accueil, pages Panne, Technicien, Intervention
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
    suivi: document.querySelectorAll('#wiki-suivi').length,
    minis: Array.from(document.querySelectorAll('#wiki-suivi .wiki-mini')).map((a) => ({ vue: a.dataset.suivi, href: a.getAttribute('href'),
      nombre: t(a.querySelector('.wiki-mini-nombre')), libelle: t(a.querySelector('span')), classe: a.className })),
    actions: Array.from(document.querySelectorAll('#wiki-suivi .wiki-suivi-actions a')).map(lien),
    briques: Array.from(document.querySelectorAll('.wiki-brique')).map((a) => ({ type: a.dataset.type, href: a.getAttribute('href'),
      titre: t(a.querySelector('h2')), nombre: t(a.querySelector('.wiki-brique-nombre')), ligne: t(a.querySelector('.wiki-brique-ligne')),
      pastille: a.querySelector('.bento-pastille-icone').className })),
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
    liens: Array.from(racine.querySelectorAll('a[href^="#/wiki/"]')).map((a) => a.getAttribute('href')) };
}"""

TROUVES_JS = """() => Array.from(document.querySelectorAll('#wiki-trouves .wiki-groupe:not(.wiki-plein-texte)')).map((g) => ({
  type: g.dataset.type, titre: g.querySelector('.wiki-groupe-titre').textContent.replace(/\\s+/g, ' ').trim(),
  ids: Array.from(g.querySelectorAll('li')).map((li) => li.dataset.id),
  liens: Array.from(g.querySelectorAll('li')).map((li) => { const a = li.querySelector('.wiki-ligne-corps > a'); return a ? a.getAttribute('href') : null; }),
  textes: Array.from(g.querySelectorAll('li')).map((li) => li.querySelector('.wiki-ligne-corps > :first-child').textContent),
  caches: Array.from(g.querySelectorAll('li')).map((li) => li.hidden),
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
  return [dt.textContent.trim(), dd.textContent.trim(), a ? a.getAttribute('href') : null];
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

PAGE_WIKI_JS = """() => {
  const t = (e) => (e ? e.textContent.replace(/\\s+/g, ' ').trim() : null);
  const lien = (a) => [t(a), a.getAttribute('href')];
  const ots = (racine) => Array.from(racine.querySelectorAll('.wiki-citations > *')).map((e) => [e.tagName, t(e), e.getAttribute('href')]);
  const phrase = (p) => ({ texte: t(p.querySelector('.wiki-phrase-texte')), ot: ots(p),
    liens: Array.from(p.querySelectorAll('.wiki-phrase-texte > a')).map(lien),
    absents: Array.from(p.querySelectorAll('.wiki-phrase-texte > .wiki-lien-absent')).map(t) });
  const racine = document.querySelector('.wiki-page');
  const entete = document.querySelector('#wiki-entete');
  const attente = document.querySelector('#wiki-en-attente');
  const fiche = document.querySelector('#wiki-lien-fiche');
  const modifier = document.querySelector('#wiki-modifier');
  return {
    id: racine.dataset.page, type: racine.dataset.type, h1: t(document.querySelector('#contenu h1')),
    typeBadge: t(racine.querySelector('.wiki-type')), fiche: fiche ? lien(fiche) : null,
    blocs: Array.from(racine.children).map((e) => e.id || e.className),
    couche: Array.from(document.querySelectorAll('#wiki-couche > *')).map((e) => e.id
      || Array.from(e.classList).filter((c) => c === 'wiki-recherche' || c === 'wiki-couche-titre').join('.')),
    origine: t(document.querySelector('#wiki-texte .wiki-origine')),
    sansTexte: t(document.querySelector('#wiki-texte .wiki-sans-texte')),
    modifier: modifier ? lien(modifier) : null,
    rubriques: Array.from(document.querySelectorAll('#wiki-texte .wiki-rubrique')).map((r) => [t(r.querySelector('h3')),
      Array.from(r.querySelectorAll('.wiki-phrase')).map(phrase)]),
    retours: Array.from(document.querySelectorAll('#wiki-retours li')).map((li) => [li.dataset.id,
      ...lien(li.querySelector('a')), t(li.querySelector('.badge'))]),
    nombreRetours: t(document.querySelector('#wiki-retours h2 .badge')),
    sansRetour: t(document.querySelector('#wiki-retours .wiki-sans-retour')),
    contradictions: Array.from(document.querySelectorAll('.wiki-contradiction')).map((c) => ({
      entree: c.dataset.entree, rang: c.dataset.rang, anterieure: c.dataset.anterieure,
      page: phrase(c.querySelector('.wiki-cote-page .wiki-phrase')), titreOt: t(c.querySelector('.wiki-cote-ot h3')),
      observation: c.querySelector('.wiki-observation').textContent, ot: ots(c.querySelector('.wiki-cote-ot')),
      boutons: Array.from(c.querySelectorAll('button[data-decision]')).map((b) => [b.dataset.decision, t(b)]),
      notes: c.querySelectorAll('textarea').length })),
    attente: attente ? { lignes: Array.from(attente.querySelectorAll('.wiki-attente > li')).map((li) => [li.dataset.entree,
      ...lien(li.querySelector('.wiki-lien-proposition')), t(li.querySelector('.wiki-ligne-tete > :nth-child(2)'))]),
      vide: t(attente.querySelector('.wiki-sans-attente')) } : null,
    entete: entete ? { titre: t(entete.querySelector('h2')), phrase: t(entete.querySelector('.wiki-entete-phrase')),
      consignation: entete.querySelector('.wiki-consignation-texte') ? entete.querySelector('.wiki-consignation-texte').textContent : null,
      absence: t(entete.querySelector('.wiki-sans-consignation')),
      equipements: Array.from(entete.querySelectorAll('.wiki-entete-equipements a')).map(lien),
      aide: t(entete.querySelector('p.aide')) } : null,
  };
}"""

PAGE_JS = """() => {
  const t = (e) => (e ? e.textContent.replace(/\\s+/g, ' ').trim() : null);
  const spans = (e) => (e ? Array.from(e.querySelectorAll(':scope > span')).map(t) : []);
  const symptomes = (racine) => Array.from(racine.querySelectorAll('.wiki-symptomes > li')).map((li) => ({
    code: li.dataset.code, suffisant: li.dataset.suffisant, libelle: t(li.querySelector('h3')),
    cas: t(li.querySelector('.wiki-cas')), periode: t(li.querySelector('.wiki-periode')),
    insuffisant: t(li.querySelector('.wiki-insuffisant')), piste: t(li.querySelector('.wiki-piste')),
    sansCause: t(li.querySelector('.wiki-sans-cause')),
    causes: Array.from(li.querySelectorAll('.wiki-causes > li')).map((c) => ({ code: c.dataset.code,
      texte: t(c.querySelector('.wiki-cause')),
      remedes: Array.from(c.querySelectorAll('.wiki-remedes > li')).map((r) => ({ code: r.dataset.code, texte: t(r) })) })),
    fourchettes: Array.from(li.querySelectorAll('details.causes-precision .causes-fourchettes > div')).map(t),
    detailFerme: Array.from(li.querySelectorAll('details.causes-precision')).every((d) => !d.open) }));
  const racine = document.querySelector('.wiki-page');
  const memeModele = document.querySelector('#wiki-meme-modele');
  const consignation = document.querySelector('#wiki-consignation');
  return {
    h1: t(document.querySelector('#contenu h1')),
    fiche: document.querySelector('#wiki-lien-fiche').getAttribute('href'),
    blocs: Array.from(racine.children).map((e) => e.id || e.className),
    sections: Array.from(document.querySelector('#wiki-couche').children).map((e) => e.id
      || Array.from(e.classList).filter((c) => c === 'wiki-couche-titre' || c === 'wiki-recherche').join('.')),
    pannes: symptomes(document.querySelector('#wiki-pannes')),
    sansPanne: t(document.querySelector('#wiki-pannes .wiki-sans-panne')),
    mention: t(document.querySelector('#wiki-pannes .wiki-mention')),
    pieces: Array.from(document.querySelectorAll('#wiki-pieces .wiki-pieces > li')).map((li) => ({
      article: li.dataset.article, reference: t(li.querySelector('.wiki-ligne-tete > :first-child')),
      designation: t(li.querySelector('.wiki-designation')), meta: spans(li.querySelector('.carte-meta')) })),
    dernieres: Array.from(document.querySelectorAll('#wiki-dernieres .wiki-interventions > li')).map((li) => ({
      id: li.dataset.ot, numero: t(li.querySelector('.wiki-ligne-tete > :first-child')), date: t(li.querySelector('.wiki-date')),
      titre: t(li.querySelector('.carte-titre')), meta: spans(li.querySelector('.carte-meta')),
      extrait: li.querySelector('.wiki-extrait') ? li.querySelector('.wiki-extrait').textContent : '' })),
    voirAutres: document.querySelector('#wiki-voir-autres')
      ? [document.querySelector('#wiki-voir-autres').getAttribute('href'), t(document.querySelector('#wiki-voir-autres'))] : null,
    autres: t(document.querySelector('#wiki-autres')),
    memeModele: memeModele ? { jumeaux: Array.from(memeModele.querySelectorAll('.wiki-jumeaux a')).map((a) => [a.getAttribute('href'), t(a)]),
      aide: t(memeModele.querySelector('.aide')), pannes: symptomes(memeModele), mention: t(memeModele.querySelector('.wiki-mention')) } : null,
    consignation: { texte: consignation.querySelector('.wiki-consignation-texte')
      ? consignation.querySelector('.wiki-consignation-texte').textContent : null,
      absence: t(consignation.querySelector('.wiki-sans-consignation')),
      modifier: consignation.querySelector('#wiki-modifier-consignation')
        ? consignation.querySelector('#wiki-modifier-consignation').getAttribute('href') : null },
  };
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


# --- valeurs attendues, calculées ici ----------------------------------------------------------------

def date_fr(iso):
    return "%s/%s/%s" % (iso[8:10], iso[5:7], iso[0:4]) if iso else ""


def periode(debut, fin):
    if not debut and not fin:
        return ""
    if not debut or not fin or debut == fin:
        return "le " + date_fr(fin or debut)
    return "du %s au %s" % (date_fr(debut), date_fr(fin))


def pourcent(part):
    return "%d %%" % math.floor(part * 100 + 0.5)


def nombre_fr(valeur):
    texte = ("%.2f" % float(valeur)).rstrip("0").rstrip(".")
    return texte.replace(".", ",")


def pluriel(nombre, singulier, forme_plurielle):
    return "%d %s" % (nombre, forme_plurielle if nombre > 1 else singulier)


def symptomes_attendus(pannes):
    attendus = []
    for symptome in pannes:
        attendu = {"code": symptome["code"], "suffisant": "oui" if symptome["suffisant"] else "non",
                   "libelle": symptome["libelle"], "cas": "%d cas" % symptome["cas"],
                   "periode": periode(symptome["debut"], symptome["fin"]), "insuffisant": None, "piste": None,
                   "sansCause": None, "causes": [], "fourchettes": [], "detailFerme": True}
        if not symptome["suffisant"]:
            attendu["insuffisant"] = "Pas encore assez de cas pour ce symptôme (%d sur 5)" % symptome["cas"]
        elif not symptome["causes"]:
            attendu["sansCause"] = "Aucune cause n'est renseignée sur ces cas."
        else:
            attendu["piste"] = MENTION_PISTE if symptome["peuDeCas"] else None
            for cause in symptome["causes"]:
                dernier = " · dernier cas le " + date_fr(cause["dernierCas"]) if cause["dernierCas"] else ""
                attendu["causes"].append({
                    "code": cause["code"],
                    "texte": "%s — %d cas sur %d%s" % (cause["libelle"], cause["nombre"], symptome["casAvecCause"], dernier),
                    "remedes": [{"code": remede["code"], "texte": "%s : %d fois, %s dans les 30 jours" % (
                        remede["libelle"], remede["fois"],
                        pluriel(remede["recidives"], "récidive", "récidives") if remede["recidives"] else "aucune récidive")}
                        for remede in cause["remedes"]]})
                attendu["fourchettes"].append("%s : entre %s et %s des cas" % (
                    cause["libelle"], pourcent(cause["fourchette"]["bas"]), pourcent(cause["fourchette"]["haut"])))
        attendus.append(attendu)
    return attendus


def plat(texte):
    return re.sub(r"\s+", " ", texte or "").strip()


def ots_attendus(ots, liens):
    return [["A", ot, "#/ot/" + ot] if liens else ["B", ot, None] for ot in ots]


def phrase_attendue(contenu, liens):
    """Phrase du balisage → ce que l'écran doit montrer : texte sans citations (liens gardés comme texte), OT cités
    (liens selon le profil), liens vers les pages connues, titres inconnus en texte."""
    titres = [titre.strip() for titre in MOTIF_LIEN.findall(contenu)]
    texte = plat(MOTIF_LIEN.sub(lambda m: m.group(1).strip(), MOTIF_CITATION.sub(" ", contenu)))
    return {"texte": texte, "ot": ots_attendus(citations(contenu), liens),
            "liens": [[plat(titre), "#/wiki/" + RESOLUTIONS[titre]] for titre in titres if titre in RESOLUTIONS],
            "absents": [plat(titre) for titre in titres if titre not in RESOLUTIONS]}


def rubriques_attendues(texte, liens):
    rubriques = []
    for ligne in texte.splitlines():
        if ligne.startswith("## "):
            rubriques.append([ligne[3:].strip(), []])
        elif ligne.startswith("- "):
            rubriques[-1][1].append(phrase_attendue(ligne[2:].strip(), liens))
    return rubriques


def titre_equipement(ligne):
    return " — ".join(v for v in ((ligne.get("repere") or "").strip(), (ligne.get("designation") or "").strip()) if v)


def titre_article(ligne):
    return (ligne.get("designation") or "").strip() or (ligne.get("reference") or "").strip() or ligne["id"]


LISTES = {"machines": "Machines", "pannes": "Pannes", "articles": "Articles", "techniciens": "Techniciens",
          "savoir-faire": "Savoir-faire", "interventions": "Interventions"}
LISTE_DU_TYPE = {"machine": "machines", "panne": "pannes", "article": "articles", "technicien": "techniciens",
                 "savoir-faire": "savoir-faire"}
CLES_NOMBRES = {"machines": "machines", "pannes": "pannes", "articles": "articles", "techniciens": "techniciens",
                "savoir-faire": "savoirFaire"}
CLOTURES = ("Clôturé techniquement", "Clôturé administrativement")
OUVERTS = ("Créé", "Préparé", "Planifié", "En cours", "En attente")
CODE_PIEGE = "S/1 é&"                              # « / », espace, accent, « & » : changent à l'encodage
LIBELLE_PIEGE = '<img src=x onerror="window.__piege = 7">Fuite <b>vive</b>'
PIEGE_MACHINE = 'Compresseur <img src=x onerror="window.__piege = 8"><b>vis</b>'
PIEGE_NOM = 'Moreau <img src=x onerror="window.__piege = 9"><b>gras</b>'
ERREURS_SERVEUR = [re.compile(r"status of 404.*/api/ping"), re.compile(r"status of 404.*/api/csv/")]


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


def accueil_attendu(tables, profil):
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
    return {"nombres": nombres, "liens": liens, "phrase": ", ".join(l[0] for l in liens[:-1]) + " et " + liens[-1][0],
            "cloturees": len(clotures), "reperes": [e["repere"] for e in machines[:3] if par_machine.get(e["id"], 0) > 0],
            "premiere_panne": (pannes[0][2], pluriel(pannes[0][3], "cas", "cas")), "dernieres": [o["id"] for o in clotures[:6]],
            "pannes": [(p[0], [p[2], p[1]], pluriel(p[3], "cas", "cas")) for p in pannes[:5]]}


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
    vus = {e["ot_id"] for e in journal if e["nature"] == "ingestion"}
    return {
        "a-valider": sum(1 for e in journal if e["statut"] == "à valider"),
        "contradictions": sum(1 for e in journal if e["statut"] == "validée"
                              for c in json.loads(e["contradictions"] or "[]") if c.get("statut") == "ouverte"),
        "file": sum(1 for e in ingestions if e["statut"] in ("en file", "à refaire")),
        "echecs": len(echecs),
        "hors": sum(1 for o in ordres if o["statut"] == "Clôturé administrativement" and o["id"] not in vus),
    }


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
        self.page.evaluate(BASE_JS, [PAGES, JOURNAL])

    def aller(self, route, attendre):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(attendre, state="attached")

    def aller_page(self, equipement):
        self.aller("#/wiki/" + equipement, '.wiki-page[data-equipement="%s"] #wiki-dernieres' % equipement)

    def aller_wiki(self, identifiant):
        self.aller("#/wiki/" + identifiant, '.wiki-page[data-page="%s"] #wiki-retours' % identifiant)

    def aller_accueil(self):
        self.aller("#/wiki", "#wiki-accueil")

    def chercher_accueil(self, texte):
        """Tape `texte` dans la recherche de l'accueil (résultats vidés d'abord) et attend les résultats."""
        self.page.evaluate("() => { const z = document.querySelector('#wiki-trouves'); z.textContent = ''; z.hidden = true; }")
        self.page.fill("#wiki-champ-accueil", texte)
        self.page.wait_for_selector("#wiki-trouves:not([hidden]) .wiki-trouves-titre")

    def lire_page(self, identifiant):
        self.aller_wiki(identifiant)
        return self.page.evaluate(PAGE_WIKI_JS)

    def wiki_page(self, equipement):
        return self.page.evaluate("(id) => Wiki.pageEquipement(id)", equipement)

    def wiki(self, identifiant):
        return self.page.evaluate("(id) => Wiki.page(id, { responsable: App.estResponsable() })", identifiant)

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
                attendu = accueil_attendu(tables, profil)
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
                # Pannes les plus fréquentes : cinq, par nombre de cas, liens encodés
                self.assertEqual([(p["id"], p["lien"], p["cas"]) for p in lu["pannes"]], attendu["pannes"])
                self.assertEqual(lu["pannes"][0]["largeur"], "100%")
                self.verifier_sans_piege()

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
                                          ("#/wiki/savoir-faire", 'li[data-id="WP-0011"] .wiki-ligne-corps > a', TITRE_PIEGE),
                                          ("#/wiki/pannes", ".wiki-ligne .wiki-ligne-corps > a", LIBELLE_PIEGE),
                                          ("#/wiki/TEC-0001", "#contenu h1", nom)):
            with self.subTest(route=route):
                self.aller(route, selecteur)
                self.assertEqual(page.evaluate("(s) => document.querySelector(s).textContent", selecteur), attendu)
                self.verifier_sans_piege()

    def tables(self):
        return self.page.evaluate("""() => Object.fromEntries(['equipements', 'articles', 'techniciens', 'ordres_travail',
          'codes_defaillance', 'wiki_pages', 'wiki_journal', 'localisations'].map((t) => [t, Donnees.lignes(t)]))""")


# ---------------------------------------------------------------------------
# #/wiki/<liste> : les six listes
# ---------------------------------------------------------------------------

class TestListes(CasWiki):

    tables = TestAccueil.tables

    def lire(self, liste):
        self.aller("#/wiki/" + liste, '.wiki-liste-entites[data-liste="%s"]' % liste)
        return self.page.evaluate(LISTE_JS)

    def test_six_listes_pour_les_trois_profils(self):
        for profil in ("demandeur", "technicien", "responsable"):
            page = self.ouvrir(profil, base=True)
            tables = self.tables()
            francais = lambda paires: page.evaluate(TRIER_TITRES_JS, paires)  # noqa: E731
            attendus = {
                "machines": sorted(e["id"] for e in tables["equipements"]),
                "pannes": [p[0] for p in pannes_attendues(tables)],
                "articles": francais([[a["id"], titre_article(a)] for a in tables["articles"]]),
                "techniciens": francais([[t["id"], (t["prenom"] + " " + t["nom"]).strip()] for t in tables["techniciens"]]),
                "savoir-faire": francais([[p["id"], p["titre"]] for p in tables["wiki_pages"]
                                          if p["type"] == "savoir-faire" and p["statut"] != "archivée"]),
                "interventions": page.evaluate("Wiki.listeEntites('intervention', { profil: 'responsable' }).map((o) => o.id)"),
            }
            self.assertEqual(len(attendus["savoir-faire"]), 5)
            for liste, ids in attendus.items():
                with self.subTest(profil=profil, liste=liste):
                    lu = self.lire(liste)
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
        lu = self.lire("machines")
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
        lu = self.lire("pannes")
        attendues = pannes_attendues(self.tables())
        self.assertEqual([l[:3] for l in lu["lignes"]], [[i, lien, libelle] for i, lien, libelle, _ in attendues])
        self.assertEqual(page.evaluate("Array.from(document.querySelectorAll('.wiki-ligne-droite')).map((e) => e.textContent)"),
                         [pluriel(cas, "cas", "cas") for *_, cas in attendues])

    def test_articles_filtrables_avec_l_etat_du_stock(self):
        page = self.ouvrir("technicien")
        self.lire("articles")
        articles = {a["articleId"]: a for a in page.evaluate("Wiki.listeEntites('article', { profil: 'technicien' })")}
        lignes = page.evaluate(ARTICLES_JS)
        self.assertEqual(len(lignes), 52)
        classes = {"en stock": "ok", "sous le seuil": "attention", "rupture": "ko"}
        for ident, _, etat, classe, nombre in lignes:
            article = articles[ident]
            self.assertEqual(etat, page.evaluate("(a) => UI.nombreFr(a.stock) + ' ' + a.unite + ' · ' + a.etat", article))
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
        page = self.ouvrir("technicien", largeur=375, hauteur=812, telephone=True)
        self.lire("articles")
        self.assertEqual(page.locator("#wiki-articles .liste-cartes > li > a").count(), 52)
        page.fill("#wiki-filtre-texte", "courroie")
        page.wait_for_function("document.querySelectorAll('#wiki-articles .liste-cartes > li').length < 52")
        self.assertTrue(all("ourroie" in t for t in page.eval_on_selector_all("#wiki-articles .carte-titre", "e => e.map((x) => x.textContent)")))
        self.lire("interventions")
        total = page.evaluate("Wiki.listeEntites('intervention').length")
        caches = page.eval_on_selector_all(".wiki-carte-intervention", "e => e.map((x) => x.hidden)")
        self.assertEqual(caches, [rang >= 40 for rang in range(total)])
        bouton = page.locator(".wiki-voir-autres")
        self.assertEqual(bouton.inner_text().strip(), "Voir les %d autres interventions" % (total - 40))
        bouton.click()
        self.assertEqual(page.eval_on_selector_all(".wiki-carte-intervention[hidden]", "e => e.length"), 0)

    def test_interventions_ouvertes_en_tete_avec_leur_statut(self):
        page = self.ouvrir("responsable")
        self.lire("interventions")
        lignes = page.evaluate(INTERVENTIONS_JS)
        tables = self.tables()
        ordres = {o["id"]: o for o in tables["ordres_travail"]}
        self.assertEqual(len(lignes), len(ordres))
        self.assertEqual([l["id"] for l in lignes], page.evaluate("Wiki.listeEntites('intervention').map((o) => o.id)"))
        statuts = [l["statut"] for l in lignes]
        self.assertEqual(statuts, [ordres[l["id"]]["statut"] for l in lignes])          # le statut sur chaque ligne
        ouverts = [s in OUVERTS for s in statuts]
        self.assertTrue(any(ouverts) and not all(ouverts))
        self.assertEqual(ouverts, sorted(ouverts, reverse=True))                         # les ouverts en tête
        self.assertEqual(statuts[0], "En cours")
        fermes = [l["id"] for l in lignes if l["statut"] not in OUVERTS]
        self.assertEqual(fermes, sorted(fermes, key=lambda i: (date_de_l_ot(ordres[i]), i), reverse=True))
        cas = {code for code, _ in compter_cas(tables["ordres_travail"]).items()}
        for ligne in lignes:
            ot = ordres[ligne["id"]]
            self.assertEqual(ligne["lien"], "#/wiki/" + encoder(ot["id"]))
            self.assertEqual(ligne["machine"], "#/wiki/" + encoder(ot["equipement_id"]))
            code = ot["symptome_code"].strip()
            self.assertEqual(ligne["panne"], lien_panne(code) if code in cas else None, ot["id"])

    def test_pages_panne_technicien_intervention(self):
        """Rendu minimal (T136, en attendant T137) : titre, fiche des faits, liens ; rien pour le demandeur qui ne les voit pas."""
        for profil in ("demandeur", "technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil)
                tables = self.tables()
                code, libelle, cas = sorted(((c, l, n) for c, n in compter_cas(tables["ordres_travail"]).items()
                                             for l in [libelle_symptome(tables, c)]), key=lambda x: (-x[2], x[0]))[0]
                self.lire("pannes")
                page.click(".wiki-ligne .wiki-ligne-corps > a")
                page.wait_for_selector('.wiki-entite[data-type="panne"]')
                self.assertEqual(page.inner_text("#contenu h1").strip(), libelle)
                self.assertEqual(page.evaluate(FIL_JS), [["Wiki", "#/wiki"], ["Pannes", "#/wiki/pannes"]])
                faits = page.evaluate(FAITS_JS)
                self.assertEqual([f[:2] for f in faits[:3]], [["Code", code], ["Cas", str(cas)],
                                                               ["Machines touchées", str(len({o["equipement_id"] for o in tables["ordres_travail"] if est_un_cas(o) and o["symptome_code"].strip() == code}))]])
                ot = [o for o in tables["ordres_travail"] if est_un_cas(o)][0]
                if profil == "demandeur":
                    for ident in ("TEC-0001", ot["id"]):
                        self.aller("#/wiki/" + ident, ".wiki-introuvable")
                    continue
                self.aller("#/wiki/TEC-0001", '.wiki-entite[data-page="TEC-0001"]')
                technicien = [t for t in tables["techniciens"] if t["id"] == "TEC-0001"][0]
                self.assertEqual(page.inner_text("#contenu h1").strip(), (technicien["prenom"] + " " + technicien["nom"]).strip())
                libelles = [f[0] for f in page.evaluate(FAITS_JS)]
                self.assertEqual("Taux horaire" in libelles, profil == "responsable")
                self.aller("#/wiki/" + ot["id"], '.wiki-entite[data-page="%s"]' % ot["id"])
                self.assertEqual(page.inner_text("#contenu h1").strip(), ot["id"] + " — " + ot["titre"])
                self.assertEqual(page.get_attribute("#wiki-fiche-ot", "href"), "#/ot/" + ot["id"])
                faits = {f[0]: f for f in page.evaluate(FAITS_JS)}
                self.assertEqual(faits["Machine"][2], "#/wiki/" + ot["equipement_id"])
                self.assertEqual(faits["Panne"][2], lien_panne(ot["symptome_code"].strip()))
                self.assertEqual(faits["Statut"][1], ot["statut"])
                page.click("#wiki-fiche-ot")
                page.wait_for_function("(id) => location.hash === '#/ot/' + id", arg=ot["id"])


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
                self.assertEqual([(l["type"], l["ids"]) for l in lus], [(a["type"], a["ids"]) for a in attendus])
                self.assertEqual([l["type"] for l in lus], ["machine"] + ([] if profil == "demandeur" else ["intervention"]))
                # Machines : calcul fait ici (un mot du nom commence par « pompe »), par titre
                equipements = page.evaluate("Donnees.lignes('equipements')")
                machines = sorted((titre_equipement(e), e["id"]) for e in equipements
                                  if any(m.startswith("pompe") for m in mots_comparables(titre_equipement(e))))
                self.assertEqual(lus[0]["ids"], [i for _, i in machines])
                self.assertEqual(lus[0]["titre"], "Machines · %d" % len(machines))
                for groupe in lus:
                    self.assertEqual(groupe["liens"], ["#/wiki/" + encoder(i) for i in groupe["ids"]])
                    self.assertEqual(groupe["caches"], [rang >= 6 for rang in range(len(groupe["ids"]))])
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
        self.assertEqual(len(groupe["ids"]), total)
        self.assertEqual(groupe["bouton"], "Voir les %d autres interventions" % (total - 6))
        page.click('#wiki-trouves .wiki-groupe[data-type="intervention"] .wiki-voir-autres')
        self.assertEqual(page.eval_on_selector_all('#wiki-trouves .wiki-groupe[data-type="intervention"] li[hidden]', "e => e.length"), 0)
        self.chercher_accueil("zzqxw")
        self.assertEqual(page.inner_text("#wiki-trouves .wiki-rien").strip(), "Rien trouvé pour « zzqxw ».")
        # Effacer le champ cache les résultats ; Entrée cherche tout de suite (sans attendre 300 ms)
        page.fill("#wiki-champ-accueil", "")
        page.wait_for_selector("#wiki-trouves", state="hidden")
        page.evaluate("() => { const c = document.querySelector('#wiki-champ-accueil'); c.value = 'compresseur'; }")
        page.press("#wiki-champ-accueil", "Enter")
        self.assertEqual(page.evaluate("document.querySelector('#wiki-trouves').hidden"), False)
        self.assertIn("EQ-0001", [i for g in page.evaluate(TROUVES_JS) for i in g["ids"]])


# ---------------------------------------------------------------------------
# Encyclopédie : 1440 et 375 px, zones tactiles, contrastes, réseau
# ---------------------------------------------------------------------------

class TestAffichageEncyclopedie(CasWiki):

    def parcourir(self, verifier, profil):
        """Accueil, recherche (tout ouvert), six listes, pages Panne, Technicien et Intervention."""
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
        idents = [page.evaluate("Wiki.listeEntites('panne')[0].id")]
        if profil != "demandeur":
            idents += ["TEC-0001", page.evaluate("Wiki.listeEntites('intervention')[0].id")]
        for ident in idents:
            self.aller("#/wiki/" + encoder(ident), '.wiki-entite[data-page="%s"]' % ident)
            verifier("#contenu", "page " + ident)

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
        """Mode serveur : afficher l'accueil, les listes, les pages et chercher ne fait aucune requête /api/ (la surveillance
        des autres postes, /api/versions toutes les 20 s, n'est pas un affichage)."""
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
            requetes = []
            self.page.on("request", lambda requete: requetes.append(requete.url))
            self.parcourir(lambda racine, ou: self.assertEqual(
                [u for u in requetes if "/api/" in u and "/api/versions" not in u], [], ou), "responsable")


# ---------------------------------------------------------------------------
# #/wiki/<id> : les quatre types (base d'essai)
# ---------------------------------------------------------------------------

class TestPagesDuWiki(CasWiki):

    def verifier_texte(self, lu, texte, liens, origine):
        self.assertEqual(lu["origine"], origine)
        self.assertIsNone(lu["sansTexte"])
        self.assertEqual(lu["rubriques"], rubriques_attendues(texte, liens))

    def verifier_retours(self, lu, identifiant, attendus):
        self.assertEqual([r[0] for r in lu["retours"]], [r[0] for r in attendus])
        self.assertEqual(lu["retours"], [[i, plat(titre), "#/wiki/" + i, TYPES[type_]] for i, titre, type_ in attendus])
        self.assertEqual(lu["nombreRetours"], str(len(attendus)))
        self.assertEqual(lu["sansRetour"], None if attendus else "Aucune page ne renvoie ici pour l'instant.")
        calcules = self.wiki(identifiant)["retours"]
        self.assertEqual([[r["id"], r["titre"], r["type"]] for r in calcules], [list(r) for r in attendus])

    def test_page_d_equipement_pour_les_trois_profils(self):
        for profil in ("demandeur", "technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                liens = profil != "demandeur"
                responsable = profil == "responsable"
                lu = self.lire_page("EQ-0005")
                calcul = self.wiki_page("EQ-0005")
                self.assertEqual((lu["id"], lu["type"], lu["h1"], lu["typeBadge"]), ("EQ-0005", "équipement", TITRE_PO02, "Équipement"))
                self.assertEqual(lu["fiche"], ["Fiche de l'équipement", "#/equipement/EQ-0005"])
                # De haut en bas : en-tête, couche calculée, texte, « À trancher », renvois, propositions (responsable)
                self.assertEqual(lu["blocs"], ["entete-page", "wiki-couche", "wiki-texte", "wiki-a-trancher", "wiki-retours"]
                                 + (["wiki-en-attente"] if responsable else []))
                self.assertEqual(lu["couche"], COUCHE_EQUIPEMENT + (["wiki-meme-modele"] if calcul["memeModele"] else []))
                self.verifier_texte(lu, TEXTE_PO02, liens, ORIGINE_IA % "14/10/2026")
                self.assertEqual(lu["rubriques"][3][1][0]["absents"], ["Page disparue"])
                self.verifier_retours(lu, "EQ-0005", [("WP-0006", "Desserrage des raccords", "mode"),
                                                     ("WP-0002", "Fuite de garniture", "mode")])
                # « À trancher » : vu par tous ; note et boutons au responsable
                self.assertEqual([(c["entree"], c["rang"], c["anterieure"]) for c in lu["contradictions"]],
                                 [("WJ-00002", "0", "non"), ("WJ-00002", "1", "non")])
                premiere, seconde = lu["contradictions"]
                self.assertEqual(premiere["page"], phrase_attendue(TEXTE_PO02.splitlines()[1][2:], liens))
                self.assertEqual(seconde["page"], phrase_attendue(TEXTE_PO02.splitlines()[2][2:], liens))
                self.assertEqual((premiere["titreOt"], premiere["observation"]), ("Ce que dit le nouvel OT", CONTRADICTIONS_PO02[0]["observation"]))
                self.assertEqual(seconde["observation"], OBSERVATION_PIEGEE)
                self.assertEqual(premiere["ot"], ots_attendus(["OT-2026-0214"], liens))
                for contradiction in lu["contradictions"]:
                    self.assertEqual(contradiction["boutons"], [["ancien", "L'ancien reste"], ["nouveau", "Le nouveau remplace"],
                                                                ["les deux", "Les deux sont vrais"]] if responsable else [])
                    self.assertEqual(contradiction["notes"], 1 if responsable else 0)
                # Au responsable : « Modifier » et les propositions en attente sur la page
                self.assertEqual(lu["modifier"], ["Modifier", "#/wiki-ecrire/EQ-0005"] if responsable else None)
                if responsable:
                    self.assertEqual(lu["attente"], {"lignes": [["WJ-00004", "Proposition WJ-00004", "#/wiki-journal?entree=WJ-00004",
                                                                 "OT-2026-0082"]], "vide": None})
                else:
                    self.assertIsNone(lu["attente"])
                    self.assertNotIn("WJ-00004", page.inner_text("#contenu"))
                if not liens:
                    self.assertEqual(page.locator('#contenu a[href^="#/ot"], #contenu a[href^="#/magasin"]').count(), 0)
                self.verifier_sans_piege()

    def test_pages_de_composant_ancre_libre_et_sans_texte(self):
        for profil in ("technicien", "demandeur"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                liens = profil == "technicien"
                lu = self.lire_page("ART-0016")
                calcul = self.wiki("ART-0016")["calcul"]
                self.assertEqual((lu["h1"], lu["typeBadge"]), (TITRE_KIT, "Composant"))
                self.assertEqual(lu["fiche"], ["Fiche de l'article", "#/magasin/article/ART-0016"] if liens else None)
                self.assertEqual(lu["blocs"], ["entete-page", "wiki-couche", "wiki-texte", "wiki-retours"])
                self.assertEqual(lu["couche"], ["wiki-couche-titre", "wiki-article", "wiki-montage", "wiki-remplacements",
                                                "wiki-consommations"])
                article = page.evaluate("""() => Array.from(document.querySelectorAll('#wiki-article dd')).map((d) =>
                    [d.textContent.trim(), d.querySelector('a') ? d.querySelector('a').getAttribute('href') : null])""")
                a = calcul["article"]
                self.assertEqual([d[0] for d in article[:5]], [a["reference"], a["designation"], a["fabricant"] or "–",
                                                               a["refFabricant"] or "–", a["emplacement"] or "–"])
                self.assertTrue(article[5][0].startswith(nombre_fr(a["stock"])), article[5])
                self.assertEqual(article[0][1], "#/magasin/article/ART-0016" if liens else None)
                montage = page.evaluate("""() => Array.from(document.querySelectorAll('#wiki-montage .wiki-montage > li')).map((li) =>
                    [li.dataset.equipement, li.querySelector('a').getAttribute('href'), li.querySelector('.carte-meta').textContent.replace(/\\s+/g, ' ').trim()])""")
                sources = {"liste": "dans la liste des pièces", "consommation": "consommé en intervention",
                           "les deux": "dans la liste des pièces et consommé en intervention"}
                self.assertEqual(montage, [[m["equipementId"], "#/wiki/" + m["equipementId"], plat(sources[m["source"]] + (
                    " Quantité montée : " + nombre_fr(m["quantite"]) if m["quantite"] else ""))] for m in calcul["montage"]])
                remplacements = page.evaluate("""() => Array.from(document.querySelectorAll('#wiki-remplacements li')).map((li) =>
                    [li.dataset.equipement, Array.from(li.querySelectorAll('.carte-meta span')).map((s) => s.textContent)])""")

                def intervalle(r):
                    if r["intervalleMedianJours"] is None:
                        return "un seul : pas d'intervalle" if r["nombre"] < 2 else "intervalle inconnu"
                    return "intervalle médian : %s %s" % (nombre_fr(r["intervalleMedianJours"]),
                                                          "jours" if r["intervalleMedianJours"] >= 2 else "jour")
                self.assertEqual(remplacements, [[r["equipementId"], [pluriel(r["nombre"], "remplacement", "remplacements"),
                                                                     intervalle(r)]] for r in calcul["remplacements"]])
                consommations = page.evaluate("""() => Array.from(document.querySelectorAll('#wiki-consommations .wiki-consommations > li'))
                    .map((li) => [li.dataset.ot, li.querySelector('.wiki-ligne-tete > :first-child').tagName])""")
                self.assertEqual(consommations, [[c["otId"], "A" if liens else "B"] for c in calcul["consommations"][:10]])
                self.assertGreater(len(consommations), 0)
                self.verifier_texte(lu, TEXTE_KIT, liens, ORIGINE_IA % "15/10/2026")
                self.verifier_retours(lu, "ART-0016", [("EQ-0005", TITRE_PO02, "équipement")])
                self.assertIsNone(lu["modifier"])
                # Composant libre : « Pas d'article au magasin »
                lu = self.lire_page("WP-0005")
                self.assertEqual((lu["h1"], lu["typeBadge"], lu["fiche"]), ("Joint torique de bride", "Composant", None))
                self.assertEqual(lu["couche"], ["wiki-couche-titre", "wiki-sans-article"])
                self.assertEqual(page.inner_text("#wiki-sans-article .wiki-pas-d-article").strip(), "Pas d'article au magasin")
                self.verifier_texte(lu, TEXTE_JOINT, liens, ORIGINE_IA % "15/10/2026")
                self.verifier_retours(lu, "WP-0005", [("WP-0006", "Desserrage des raccords", "mode")])
                # Article sans texte validé : un message clair, pas d'origine
                lu = self.lire_page("ART-0001")
                self.assertEqual((lu["sansTexte"], lu["origine"], lu["rubriques"]), (SANS_TEXTE, None, []))
                self.assertEqual(lu["retours"], [])

    def test_pages_de_mode_ancre_et_libre(self):
        page = self.ouvrir("technicien", base=True)
        lu = self.lire_page("WP-0002")
        calcul = self.wiki("WP-0002")["calcul"]
        self.assertEqual((lu["h1"], lu["typeBadge"], lu["fiche"]), ("Fuite de garniture", "Mode de défaillance", None))
        self.assertEqual(lu["blocs"], ["entete-page", "wiki-couche", "wiki-texte", "wiki-a-trancher", "wiki-retours"])
        self.assertEqual(lu["couche"], ["wiki-couche-titre", "wiki-cause"])
        cause = page.evaluate("""() => ({ code: document.querySelector('#wiki-cause h2 .badge').textContent,
            libelle: document.querySelector('#wiki-cause .wiki-cause-libelle').textContent.trim(),
            cas: document.querySelector('#wiki-cause .wiki-cas-mode').textContent.trim(),
            equipements: Array.from(document.querySelectorAll('#wiki-cause .wiki-equipements-touches > li')).map((li) =>
              [li.dataset.equipement, li.querySelector('a').getAttribute('href'), li.querySelector('.wiki-designation').textContent]),
            remedes: Array.from(document.querySelectorAll('#wiki-cause .wiki-remedes-mode > li')).map((li) =>
              [li.dataset.code, li.textContent.replace(/\\s+/g, ' ').trim()]),
            mention: document.querySelector('#wiki-cause .wiki-mention').textContent })""")
        self.assertEqual((cause["code"], cause["libelle"]), ("C01", calcul["cause"]["libelle"]))
        self.assertEqual(cause["libelle"], "Garniture usée")
        self.assertEqual(cause["cas"], "%s de cette cause" % pluriel(calcul["cas"], "intervention corrective clôturée",
                                                                      "interventions correctives clôturées"))
        self.assertEqual(cause["equipements"], [[e["equipementId"], "#/wiki/" + e["equipementId"], "%d cas" % e["cas"]]
                                                for e in calcul["equipements"]])
        self.assertEqual(cause["remedes"], [[r["code"], "%s : %d fois" % (r["libelle"], r["fois"])] for r in calcul["remedes"]])
        self.assertEqual(cause["mention"], MENTION)
        self.verifier_texte(lu, TEXTE_MODE, True, ORIGINE_MANUEL % "16/10/2026")
        self.verifier_retours(lu, "WP-0002", [("EQ-0005", TITRE_PO02, "équipement")])
        # Contradiction venue d'un OT antérieur aux faits de la page
        self.assertEqual(len(lu["contradictions"]), 1)
        contradiction = lu["contradictions"][0]
        self.assertEqual((contradiction["entree"], contradiction["anterieure"], contradiction["titreOt"]),
                         ("WJ-00003", "oui", "Observation antérieure aux faits de la page"))
        self.assertEqual(contradiction["page"], phrase_attendue("Goutte à goutte sous la garniture [OT-2025-0010]", True))
        self.assertEqual(contradiction["ot"], ots_attendus(["OT-2025-0030"], True))
        self.assertEqual(contradiction["boutons"], [])
        # Mode libre : rien de calculé
        lu = self.lire_page("WP-0006")
        self.assertEqual(lu["couche"], ["wiki-couche-titre", "wiki-sans-cause"])
        self.assertEqual(page.inner_text("#wiki-sans-cause .wiki-pas-de-cause").strip(), "Pas de code cause associé")
        self.verifier_texte(lu, TEXTE_DESSERRAGE, True, ORIGINE_IA % "15/10/2026")
        self.assertEqual([lien for _, phrases in lu["rubriques"] for p in phrases for lien in p["liens"]],
                         [[TITRE_PO02, "#/wiki/EQ-0005"], ["Joint torique de bride", "#/wiki/WP-0005"]])
        self.verifier_retours(lu, "WP-0006", [])
        self.assertNotIn("wiki-a-trancher", lu["blocs"])

    def test_pages_de_savoir_faire_et_leur_en_tete(self):
        for profil in ("technicien", "demandeur"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                liens = profil == "technicien"
                # Rattaché à un équipement : sa consignation telle quelle, puis la phrase de Prévo
                lu = self.lire_page("WP-0003")
                consignation = page.evaluate("Donnees.trouver('equipements', 'EQ-0005').consignation")
                self.assertGreater(consignation.count("\n"), 2)
                self.assertEqual((lu["h1"], lu["typeBadge"]), ("Changer la garniture de PO-02", "Savoir-faire"))
                self.assertEqual(lu["fiche"], ["Fiche de l'équipement", "#/equipement/EQ-0005"])
                self.assertEqual(lu["blocs"], ["entete-page", "wiki-entete", "wiki-texte", "wiki-retours"])
                self.assertEqual(lu["entete"]["titre"], "Consignation de PO-02")
                self.assertEqual(lu["entete"]["phrase"], PHRASE_SAVOIR_FAIRE)
                self.assertEqual(lu["entete"]["phrase"], page.evaluate("Wiki.PHRASE_SAVOIR_FAIRE"))
                self.assertEqual(lu["entete"]["consignation"], consignation)
                self.assertEqual(lu["entete"]["consignation"], self.wiki("WP-0003")["entete"]["consignation"]["texte"])
                self.assertEqual(page.locator("#wiki-entete .wiki-consignation-texte *").count(), 0)
                self.verifier_texte(lu, TEXTE_SF, liens, ORIGINE_MIXTE % "17/10/2026")
                self.verifier_retours(lu, "WP-0003", [("ART-0016", TITRE_KIT, "composant"), ("EQ-0005", TITRE_PO02, "équipement")])
                # Rattaché à un article : les équipements où il est monté, en liens vers leur page
                lu = self.lire_page("WP-0007")
                self.assertEqual(lu["fiche"], ["Fiche de l'article", "#/magasin/article/ART-0016"] if liens else None)
                self.assertEqual(lu["entete"]["phrase"], PHRASE_SAVOIR_FAIRE)
                self.assertIsNone(lu["entete"]["consignation"])
                self.assertEqual(lu["entete"]["equipements"], [[e["repere"], "#/wiki/" + e["equipementId"]]
                                                               for e in self.wiki("WP-0007")["entete"]["equipements"]])
                self.assertIn(["PO-02", "#/wiki/EQ-0005"], lu["entete"]["equipements"])
                self.verifier_texte(lu, "## Étapes\n- Graisser légèrement les joints [OT-2026-0058]", liens, ORIGINE_MANUEL % "15/10/2026")
                # Équipement sans consignation : le message de la page d'équipement
                lu = self.lire_page("WP-0008")
                self.assertEqual((lu["entete"]["titre"], lu["entete"]["absence"], lu["entete"]["consignation"]),
                                 ("Consignation de PE-01", SANS_CONSIGNATION, None))
                self.assertEqual(lu["entete"]["phrase"], PHRASE_SAVOIR_FAIRE)
                # Rattaché à une page de composant libre : lien vers elle, aucun équipement connu
                lu = self.lire_page("WP-0010")
                self.assertEqual(lu["fiche"], ["Page du composant", "#/wiki/WP-0005"])
                self.assertEqual((lu["entete"]["equipements"], lu["entete"]["phrase"]), ([], PHRASE_SAVOIR_FAIRE))
                self.assertIn("Aucun équipement connu", lu["entete"]["aide"])

    def test_page_archivee_inconnue_et_identifiant_piege(self):
        page = self.ouvrir("technicien", base=True)
        for identifiant in ("WP-0009", "EQ-9999"):
            with self.subTest(identifiant=identifiant):
                self.aller("#/wiki/" + identifiant, ".wiki-introuvable")
                self.assertEqual(page.inner_text("#contenu h1").strip(), "Page introuvable")
                self.assertIn(identifiant, page.inner_text("#contenu .vide"))
                self.assertEqual(page.get_attribute('#contenu a.btn[href="#/wiki"]', "href"), "#/wiki")
                self.aller_accueil()
        self.aller("#/wiki/%3Cimg%20src%3Dx%20onerror%3D%22window.__piege%3D1%22%3E", ".wiki-introuvable")
        self.assertIn('<img src=x onerror="window.__piege=1">', page.inner_text("#contenu .vide"))
        self.verifier_sans_piege()

    def test_page_d_un_equipement_disparu(self):
        """Relecture de T119 : une page d'équipement dont l'équipement n'existe plus s'affiche (sans couche calculée)."""
        page = self.ouvrir("responsable", base=True)
        page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => { lignes.push({ id: 'WP-0090', type: 'équipement',
          titre: 'XX-99 — Machine retirée', equipement_id: 'EQ-0999', texte: '## Ce qui revient\\n- Fuite [OT-2026-0001]',
          version: '1', statut: 'active', origine: 'manuel', valide_par: 'Responsable', valide_le: '2026-10-01 10:00' }); })""")
        self.aller("#/wiki/WP-0090", ".wiki-page #wiki-sans-equipement")
        self.assertIn("Équipement introuvable", page.inner_text("#wiki-sans-equipement"))
        self.assertIn("Fuite", page.inner_text("#contenu"))

    def test_titre_phrase_observation_et_consignation_piegees_restent_du_texte(self):
        page = self.ouvrir("responsable", base=True)
        page.evaluate(ECRIRE_JS, ["equipements", "EQ-0005", {"consignation": CONSIGNATION_PIEGEE}])
        lu = self.lire_page("WP-0003")
        self.assertEqual(lu["entete"]["consignation"], CONSIGNATION_PIEGEE)       # au caractère près
        self.assertEqual(page.locator("#wiki-entete img, #wiki-entete script, #wiki-entete .wiki-consignation-texte *").count(), 0)
        self.verifier_sans_piege()
        # Titre et phrase piégés
        lu = self.lire_page("WP-0011")
        self.assertEqual(lu["h1"], plat(TITRE_PIEGE))
        self.assertEqual(page.evaluate("document.querySelector('#contenu h1').textContent"), TITRE_PIEGE)
        self.assertEqual(lu["rubriques"], rubriques_attendues(TEXTE_PIEGE, True))
        self.assertIn("<script>window.__piege = 4</script>", lu["rubriques"][0][1][0]["texte"])
        self.assertEqual(page.locator("#wiki-texte .wiki-phrase-texte *").count(), 0)
        self.verifier_retours(lu, "WP-0011", [("ART-0016", TITRE_KIT, "composant")])
        self.verifier_sans_piege()
        # Lien vers la page au titre piégé, depuis une autre page et depuis la liste des savoir-faire
        lu = self.lire_page("ART-0016")
        self.assertIn([plat(TITRE_PIEGE), "#/wiki/WP-0011"], [l for _, phrases in lu["rubriques"] for p in phrases for l in p["liens"]])
        self.aller("#/wiki/savoir-faire", '.wiki-liste-entites li[data-id="WP-0011"]')
        self.assertEqual(page.evaluate("document.querySelector('li[data-id=\"WP-0011\"] .wiki-ligne-corps > a').textContent"), TITRE_PIEGE)
        # Observation piégée dans « À trancher »
        lu = self.lire_page("EQ-0005")
        self.assertEqual(lu["contradictions"][1]["observation"], OBSERVATION_PIEGEE)
        self.verifier_sans_piege()


# ---------------------------------------------------------------------------
# « À trancher » : décisions du responsable (D107)
# ---------------------------------------------------------------------------

class TestTrancher(CasWiki):

    def decisions(self):
        return [e for e in self.page.evaluate("Donnees.lignes('wiki_journal')") if e["nature"] == "décision"]

    def test_l_ancien_reste_puis_les_deux_sont_vrais_puis_le_nouveau_remplace(self):
        page = self.ouvrir("responsable", base=True)
        self.lire_page("EQ-0005")
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
        # « Les deux sont vrais », sans note : l'encadré disparaît (après le repos qui suit une décision)
        page.wait_for_selector(".wiki-page:not([data-occupe])")
        page.click('.wiki-contradiction[data-rang="1"] button[data-decision="les deux"]')
        page.wait_for_function("!document.querySelector('#wiki-a-trancher')")
        self.assertEqual([json.loads(d["contradictions"])[0]["decision"] for d in self.decisions()], ["ancien", "les deux"])
        self.assertEqual(page.evaluate("Wiki.page('EQ-0005').contradictions"), [])
        # Le texte de la page n'a pas changé (une contradiction n'écrase rien)
        self.assertEqual(page.evaluate("Donnees.trouver('wiki_pages', 'WP-0001').texte"), TEXTE_PO02)
        # « Le nouveau remplace » : décision écrite, puis l'écriture à la main de la page
        self.lire_page("WP-0002")
        page.evaluate("""() => { window.__routes = [];
            window.addEventListener('hashchange', (e) => window.__routes.push(new URL(e.newURL).hash)); }""")
        page.click('.wiki-contradiction button[data-decision="nouveau"]')
        page.wait_for_function("window.__routes.includes('#/wiki-ecrire/WP-0002')")
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
        self.lire_page("EQ-0005")
        self.assertEqual(page.locator(".wiki-contradiction").count(), 2)
        page.locator('.wiki-contradiction[data-rang="0"] button[data-decision="ancien"]').click()
        page.locator('.wiki-contradiction button[data-decision="ancien"]').last.click()
        page.wait_for_selector(".wiki-page:not([data-occupe])")
        self.assertEqual(len(self.decisions()), 1)
        self.assertEqual(len(page.evaluate("Wiki.page('EQ-0005').contradictions")), 1)

    def test_propositions_en_attente_et_boutons_absents_hors_responsable(self):
        page = self.ouvrir("responsable", base=True)
        lu = self.lire_page("WP-0003")
        self.assertEqual(lu["attente"], {"lignes": [], "vide": "Aucune proposition en attente sur cette page."})
        self.assertEqual(lu["modifier"], ["Modifier", "#/wiki-ecrire/WP-0003"])
        for profil in ("technicien", "demandeur"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                for identifiant in ("EQ-0005", "WP-0002"):
                    lu = self.lire_page(identifiant)
                    self.assertGreater(len(lu["contradictions"]), 0)
                    self.assertEqual(page.locator("#contenu .wiki-trancher, #contenu button[data-decision], #contenu textarea").count(), 0)
                    self.assertIsNone(lu["attente"])
                    self.assertIsNone(lu["modifier"])


# ---------------------------------------------------------------------------
# #/wiki/<équipement> : couche calculée égale à Wiki.pageEquipement, consignation, pièges, liens
# ---------------------------------------------------------------------------

class TestPageEquipement(CasWiki):

    def verifier_page(self, equipement, profil):
        attendu = self.wiki_page(equipement)
        self.aller_page(equipement)
        lu = self.page.evaluate(PAGE_JS)
        eq = attendu["equipement"]
        liens = profil != "demandeur"
        self.assertEqual(lu["h1"], plat("%s — %s" % (eq["repere"], eq["designation"])))
        self.assertEqual(lu["fiche"], "#/equipement/" + equipement)
        self.assertEqual(lu["blocs"], ["entete-page", "wiki-couche", "wiki-texte", "wiki-retours"]
                         + (["wiki-en-attente"] if profil == "responsable" else []))
        self.assertEqual(lu["sections"], COUCHE_EQUIPEMENT + (["wiki-meme-modele"] if attendu["memeModele"] else []))
        # Pannes habituelles
        self.assertEqual(lu["pannes"], symptomes_attendus(attendu["pannes"]))
        self.assertEqual(lu["mention"], MENTION if attendu["pannes"] else None)
        self.assertEqual(lu["sansPanne"] is None, bool(attendu["pannes"]))
        # Pièces consommées
        self.assertEqual([(p["article"], p["reference"], p["designation"]) for p in lu["pieces"]],
                         [(p["articleId"], p["reference"], p["designation"]) for p in attendu["pieces"]])
        for piece, element in zip(attendu["pieces"], lu["pieces"]):
            self.assertTrue(element["meta"][0].startswith("Quantité : %s" % nombre_fr(piece["quantite"])), element)
            self.assertEqual(element["meta"][1], pluriel(piece["nombreOt"], "intervention", "interventions"))
            self.assertEqual(element["meta"][2:], ["dernière sortie le " + date_fr(piece["derniereDate"])] if piece["derniereDate"] else [])
        # Dernières interventions
        self.assertEqual([d["id"] for d in lu["dernieres"]], [d["id"] for d in attendu["dernieres"]])
        for ot, element in zip(attendu["dernieres"], lu["dernieres"]):
            self.assertEqual(element["numero"], ot["id"])
            self.assertEqual(element["titre"], plat(ot["titre"]))
            self.assertEqual(element["date"], date_fr(ot["date"]) or None)
            self.assertEqual(element["extrait"], ot["extrait"])
            meta = ["%s : %s" % (nom, ot["codes"][cle]) for nom, cle in (("Symptôme", "symptome"), ("Cause", "cause"),
                                                                       ("Remède", "remede")) if ot["codes"][cle]]
            if ot["dureeArret"] is not None:
                meta.append("Arrêt : %s h" % nombre_fr(ot["dureeArret"]))
            self.assertEqual(element["meta"], [plat(m) for m in meta])
        reste = attendu["total"] - len(attendu["dernieres"])
        if reste > 0 and liens:
            self.assertEqual(lu["voirAutres"], ["#/ot?equipement=%s&etat=clotures" % equipement,
                                                "Voir les %d autres interventions" % reste if reste > 1 else "Voir l'autre intervention"])
        else:
            self.assertIsNone(lu["voirAutres"])
        self.assertEqual(lu["autres"], ("Et %s." % pluriel(reste, "intervention plus ancienne", "interventions plus anciennes"))
                         if reste > 0 and not liens else None)
        # Même marque et modèle
        if attendu["memeModele"]:
            self.assertEqual(lu["memeModele"]["jumeaux"],
                             [["#/wiki/" + j["id"], j["repere"]] for j in attendu["memeModele"]["equipements"]])
            self.assertIn("%s %s" % (eq["marque"], eq["modele"]), lu["memeModele"]["aide"])
            self.assertEqual(lu["memeModele"]["pannes"], symptomes_attendus(attendu["memeModele"]["pannes"]))
            self.assertEqual(lu["memeModele"]["mention"], MENTION if attendu["memeModele"]["pannes"] else None)
        else:
            self.assertIsNone(lu["memeModele"])
        # Consignation
        consignation = attendu["consignation"]
        if consignation and consignation["texte"].strip():
            self.assertEqual(lu["consignation"]["texte"], consignation["texte"])
            self.assertIsNone(lu["consignation"]["absence"])
        else:
            self.assertIsNone(lu["consignation"]["texte"])
            self.assertEqual(lu["consignation"]["absence"], SANS_CONSIGNATION)
        # Sans ligne au wiki : pas de texte, un message clair
        self.assertEqual(self.page.inner_text("#wiki-texte .wiki-sans-texte").strip(), SANS_TEXTE)
        return attendu, lu

    def test_les_28_pages_de_la_demo_conformes_a_Wiki_pageEquipement(self):
        page = self.ouvrir("technicien")
        ids = page.evaluate("() => Wiki.listePages().map((p) => p.equipementId)")
        self.assertEqual(len(ids), 28)
        vus = {"suffisant": 0, "insuffisant": 0, "piste": 0, "recidive": 0, "memeModele": 0, "voirAutres": 0, "sansPiece": 0}
        for equipement in ids:
            with self.subTest(equipement=equipement):
                attendu, lu = self.verifier_page(equipement, "technicien")
                vus["suffisant"] += sum(1 for s in attendu["pannes"] if s["suffisant"])
                vus["insuffisant"] += sum(1 for s in attendu["pannes"] if not s["suffisant"])
                vus["piste"] += sum(1 for s in attendu["pannes"] if s["peuDeCas"])
                vus["recidive"] += sum(1 for s in attendu["pannes"] for c in s["causes"] for r in c["remedes"] if r["recidives"])
                vus["memeModele"] += 1 if attendu["memeModele"] else 0
                vus["voirAutres"] += 1 if lu["voirAutres"] else 0
                vus["sansPiece"] += 0 if attendu["pieces"] else 1
        # La démo couvre bien chaque cas d'affichage
        self.assertTrue(all(vus.values()), vus)

    def test_pages_du_demandeur_et_du_responsable(self):
        for profil in ("demandeur", "responsable"):
            with self.subTest(profil=profil):
                self.ouvrir(profil)
                for equipement in ("EQ-0001", "EQ-0023", "EQ-0018", "EQ-0031"):
                    self.verifier_page(equipement, profil)

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

    def test_absence_de_consignation_sans_lien_pour_technicien_et_demandeur(self):
        for profil in ("technicien", "demandeur"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil)
                self.aller_page("EQ-0031")                          # PE-01 : aucune consignation dans la démo
                self.assertEqual(page.inner_text("#wiki-consignation .wiki-sans-consignation").strip(), SANS_CONSIGNATION)
                self.assertEqual(page.locator("#wiki-modifier-consignation").count(), 0)
                self.assertEqual(page.locator('#contenu a[href$="/modifier"]').count(), 0)

    def test_texte_piege_dans_un_compte_rendu_et_un_titre_reste_du_texte(self):
        page = self.ouvrir("technicien")
        ot = page.evaluate("(id) => Wiki.pageEquipement(id).dernieres[0].id", "EQ-0001")
        compte_rendu = "Fuite au palier " + PIEGE + " & « guillemets » \"doubles\" 'simples'"
        page.evaluate(ECRIRE_JS, ["ordres_travail", ot, {"compte_rendu": compte_rendu, "titre": "<b>Titre</b> piégé " + PIEGE}])
        self.aller_page("EQ-0001")
        ligne = page.locator('#wiki-dernieres li[data-ot="%s"]' % ot)
        self.assertEqual(ligne.locator(".wiki-extrait").text_content(), self.wiki_page("EQ-0001")["dernieres"][0]["extrait"])
        self.assertIn("<img src=x", ligne.locator(".wiki-extrait").text_content())
        self.assertEqual(plat(ligne.locator(".carte-titre").text_content()), plat("<b>Titre</b> piégé " + PIEGE))
        self.assertEqual(ligne.locator("img, script, b:not(.wiki-numero-ot)").count(), 0)
        # Dans les résultats de la recherche (extrait surligné par Wiki.surligner)
        self.chercher(".wiki-page .wiki-recherche", "palier")
        trouve = page.locator('.wiki-page .wiki-trouve[data-id="%s"]' % ot)
        self.assertEqual(trouve.count(), 1)
        self.assertIn("<img src=x", trouve.locator(".wiki-extrait").text_content())
        self.assertGreater(trouve.locator(".wiki-extrait mark").count(), 0)
        self.assertEqual(trouve.locator("img, script, .carte-titre b").count(), 0)
        self.verifier_sans_piege()

    def test_liens_selon_le_profil(self):
        for profil in ("demandeur", "technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil)
                attendu = self.wiki_page("EQ-0001")
                self.aller_page("EQ-0001")
                self.chercher(".wiki-page .wiki-recherche", "filtre colmaté")
                liens_ot = page.eval_on_selector_all('#contenu a[href^="#/ot"]', "(l) => l.map((a) => a.getAttribute('href'))")
                liens_magasin = page.locator('#contenu a[href^="#/magasin"]').count()
                numeros = page.eval_on_selector_all("#wiki-dernieres .wiki-ligne-tete > :first-child",
                                                    "(l) => l.map((e) => [e.tagName, e.textContent])")
                self.assertEqual([n[1] for n in numeros], [d["id"] for d in attendu["dernieres"]])
                if profil == "demandeur":
                    self.assertEqual(liens_ot, [])
                    self.assertEqual(liens_magasin, 0)
                    self.assertEqual({n[0] for n in numeros}, {"B"})
                    self.assertGreater(page.locator(".wiki-trouve .wiki-numero-ot").count(), 0)
                    self.assertEqual(page.locator("#wiki-pieces .wiki-pieces b").count(), len(attendu["pieces"]))
                else:
                    self.assertEqual({n[0] for n in numeros}, {"A"})
                    for ot in attendu["dernieres"]:
                        self.assertIn("#/ot/" + ot["id"], liens_ot)
                    self.assertIn("#/ot?equipement=EQ-0001&etat=clotures", liens_ot)
                    self.assertEqual(page.eval_on_selector_all("#wiki-pieces .wiki-lien-article", "(l) => l.map((a) => a.getAttribute('href'))"),
                                     ["#/magasin/article/" + p["articleId"] for p in attendu["pieces"]])
                    self.assertGreater(page.locator('.wiki-trouve a.wiki-lien-ot[href^="#/ot/OT-"]').count(), 0)
                    # Les liens mènent aux écrans
                    page.click('#wiki-dernieres a[href="#/ot/%s"]' % attendu["dernieres"][0]["id"])
                    page.wait_for_selector(".ot-onglets")
                    self.aller_page("EQ-0001")
                    page.click("#wiki-voir-autres")
                    # La liste reprend les filtres de l'adresse puis la réécrit en « #/ot » (ordres-liste.js) : on attend
                    # la liste et son filtre « Clôturés », jamais l'adresse passagère (course sous charge).
                    page.wait_for_function("() => (document.querySelector('#contenu h1') || {}).textContent === 'Ordres de travail'"
                                           " && (document.querySelector('#ot-filtre-etat') || {}).value === 'clotures'")
                # Même marque et modèle : lien vers la page du jumeau, pour tous
                self.aller_page("EQ-0023")
                page.click('#wiki-meme-modele a[href="#/wiki/EQ-0025"]')
                page.wait_for_selector('.wiki-page[data-equipement="EQ-0025"]')
                self.aller_page("EQ-0001")
                page.click("#wiki-lien-fiche")
                page.wait_for_function("location.hash === '#/equipement/EQ-0001'")
                page.wait_for_selector("#lien-wiki-equipement")

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
# Sous-pages (§20.4, §20.9 ; T131) : base d'essai = PAGES, la page de PO-02 avec ses renvois, et des sous-pages
# ---------------------------------------------------------------------------

PHRASE_SOUS_PAGE = "Cette page ne remplace pas la consignation de l'équipement"
TITRE_SP_GARNITURE = "PO-02 — garniture"
TITRE_SP_ETANCHEITE = "PO-02 — Étanchéité"
TITRE_SP_PIEGE = 'PO-02 — <img src=x onerror="window.__piege = 6">Régler <b>gras</b>'
TITRE_SP_KIT = TITRE_KIT + " — usure"
TITRE_SP_REGLAGE = TITRE_PIEGE + " — réglage fin"
TITRE_SF_ALIGNER = "Aligner l'accouplement de PO-02"
TITRE_SP_ALIGNER = TITRE_SF_ALIGNER + " — comparateur"
TEXTE_SP_GARNITURE = ("## Ce qui revient\n- La garniture fuit au démarrage [OT-2025-0010]\n"
                      "## Astuces\n- Garder un kit d'avance au magasin [OT-2025-0044]")
TEXTE_SP_KIT = "## Signes d'usure\n- La face se raye [OT-2026-0214]"
RENVOI_PO02 = "- Le détail est dans [[%s]], [[%s]] et [[%s]] [OT-2025-0010] [OT-2026-0214]" % (
    TITRE_SP_GARNITURE, TITRE_SP_ETANCHEITE, TITRE_SP_PIEGE)
SOUS_PAGES = [
    page_wiki("WP-0012", "équipement", TITRE_SP_GARNITURE, TEXTE_SP_GARNITURE, "IA", "", "2026-10-18 10:00", rattache_a="WP-0001"),
    page_wiki("WP-0013", "équipement", TITRE_SP_ETANCHEITE, "## À surveiller\n- Le joint de corps suinte [OT-2026-0214]",
              "manuel", rattache_a="WP-0001"),
    page_wiki("WP-0014", "équipement", TITRE_SP_PIEGE, "## Astuces\n- Régler sans forcer [OT-2026-0098]", "IA", rattache_a="WP-0001"),
    page_wiki("WP-0015", "équipement", "PO-02 — accouplement", "## Astuces\n- Aligner à froid [OT-2026-0214]", "IA",
              rattache_a="WP-0001", statut="archivée"),
    page_wiki("WP-0016", "composant", TITRE_SP_KIT, TEXTE_SP_KIT, "IA", rattache_a="WP-0004"),
    page_wiki("WP-0017", "savoir-faire", TITRE_SP_REGLAGE, "## Étapes\n- Reprendre le réglage à froid [OT-2026-0098]", "IA",
              rattache_a="WP-0011"),
    # Savoir-faire rattaché à la page de PO-02 par rattache_a (pas une sous-page : autre type), et sa sous-page
    # (relecture de T130, CS98 : la consignation remonte deux rattachements).
    page_wiki("WP-0018", "savoir-faire", TITRE_SF_ALIGNER, "## Étapes\n- Poser le comparateur sur le moyeu [OT-2026-0214]", "IA",
              rattache_a="WP-0001"),
    page_wiki("WP-0019", "savoir-faire", TITRE_SP_ALIGNER, "## Pièces et outillage\n- Comparateur à cadran [OT-2026-0214]", "IA",
              rattache_a="WP-0018"),
]
PAGES_SOUS_PAGES = [dict(p, texte=p["texte"] + "\n" + RENVOI_PO02, liens=p["liens"] + ";WP-0012;WP-0013;WP-0014")
                    if p["id"] == "WP-0001" else p for p in PAGES] + SOUS_PAGES

SOUS_PAGE_JS = """() => {
  const t = (e) => (e ? e.textContent.replace(/\\s+/g, ' ').trim() : null);
  const racine = document.querySelector('.wiki-page');
  const mere = document.querySelector('#wiki-mere');
  const lien = mere ? mere.querySelector('a') : null;
  const liste = document.querySelector('#wiki-sous-pages');
  return { dataMere: racine.dataset.mere, dataEquipement: racine.dataset.equipement, mere: t(mere),
    mereLien: lien ? [lien.textContent, lien.getAttribute('href')] : null,
    mereArchivee: mere ? t(mere.querySelector('.wiki-mere-archivee')) : null,
    sousPages: liste ? Array.from(liste.querySelectorAll('li')).map((li) => [li.dataset.id, li.querySelector('a').textContent,
      li.querySelector('a').getAttribute('href')]) : null,
    nombre: liste ? t(liste.querySelector('h2 .badge')) : null,
    recherche: document.querySelectorAll('.wiki-page .wiki-recherche').length,
    calcule: document.querySelectorAll('#wiki-couche, #wiki-sans-equipement, #wiki-sans-article, #wiki-sans-cause').length };
}"""
TRIER_TITRES_JS = """(pages) => { const fr = new Intl.Collator('fr', { numeric: true, sensitivity: 'base' });
  return pages.slice().sort((a, b) => fr.compare(a[1], b[1]) || (a[0] < b[0] ? -1 : 1)).map((p) => p[0]); }"""
SOUS_PAGES_PARCOURUES = ("EQ-0005", "WP-0012", "WP-0014", "ART-0016", "WP-0016", "WP-0011", "WP-0017", "WP-0019")


class TestSousPages(CasWiki):
    """Sous-pages : « Sous-page de <mère> » (lien), consignation de l'équipement de la mère en tête, aucune couche
    calculée ; la mère liste ses sous-pages après le texte ; la liste des savoir-faire montre ceux des sous-pages (les
    sous-pages de machine et d'article, retirées par la refonte 2, n'y sont pas) ; trois profils ; titres piégés ;
    « Modifier » ; 1440 et 375 px, zones de 48 px, contrastes AA en thème clair et sombre."""

    verifier_texte = TestPagesDuWiki.verifier_texte
    verifier_retours = TestPagesDuWiki.verifier_retours

    def poser_base(self):
        self.page.evaluate(BASE_JS, [PAGES_SOUS_PAGES, JOURNAL])

    def lire(self, identifiant):
        lu = self.lire_page(identifiant)
        lu.update(self.page.evaluate(SOUS_PAGE_JS))
        return lu

    def consignation_po02(self):
        """Consignation de la fiche de PO-02, telle quelle, et celle de sa page d'équipement (Wiki.pageEquipement)."""
        fiche = self.page.evaluate("Donnees.trouver('equipements', 'EQ-0005').consignation")
        self.assertGreater(fiche.count("\n"), 2)
        self.assertEqual(self.wiki_page("EQ-0005")["consignation"]["texte"], fiche)
        return fiche

    def test_sous_page_d_equipement_pour_les_trois_profils(self):
        for profil in ("demandeur", "technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                liens = profil != "demandeur"
                responsable = profil == "responsable"
                lu = self.lire("WP-0012")
                self.assertEqual((lu["id"], lu["type"], lu["h1"], lu["typeBadge"]),
                                 ("WP-0012", "équipement", TITRE_SP_GARNITURE, "Équipement"))
                # Sous le titre, « Sous-page de <mère> » en lien vers la mère ; la fiche est celle de l'équipement de la mère.
                self.assertEqual(lu["mere"], "Sous-page de " + TITRE_PO02)
                self.assertEqual(lu["mereLien"], [TITRE_PO02, "#/wiki/EQ-0005"])
                self.assertEqual(page.evaluate("document.querySelector('#wiki-mere').previousElementSibling.tagName"), "H1")
                self.assertEqual((lu["dataMere"], lu["dataEquipement"]), ("EQ-0005", ""))
                self.assertEqual(lu["fiche"], ["Fiche de l'équipement", "#/equipement/EQ-0005"])
                # En tête, la consignation de l'équipement de sa mère, à l'octet ; aucune couche calculée.
                self.assertEqual(lu["blocs"], ["entete-page", "wiki-entete", "wiki-texte", "wiki-retours"]
                                 + (["wiki-en-attente"] if responsable else []))
                self.assertEqual((lu["couche"], lu["calcule"], lu["recherche"]), ([], 0, 0))
                self.assertEqual(lu["entete"]["titre"], "Consignation de PO-02")
                self.assertEqual(lu["entete"]["phrase"], PHRASE_SOUS_PAGE)
                self.assertEqual(lu["entete"]["phrase"], page.evaluate("Wiki.PHRASE_SOUS_PAGE"))
                self.assertEqual(lu["entete"]["consignation"], self.consignation_po02())
                self.assertEqual(page.locator("#wiki-entete .wiki-consignation-texte *, #wiki-modifier-consignation").count(), 0)
                self.assertIsNone(self.wiki("WP-0012")["calcul"])
                # Le texte, son origine, les OT cités (sans lien pour le demandeur), la mère dans « Pages qui renvoient ici ».
                self.verifier_texte(lu, TEXTE_SP_GARNITURE, liens, ORIGINE_IA % "18/10/2026")
                self.verifier_retours(lu, "WP-0012", [("EQ-0005", TITRE_PO02, "équipement")])
                self.assertIsNone(lu["sousPages"])
                self.assertEqual(lu["modifier"], ["Modifier", "#/wiki-ecrire/WP-0012"] if responsable else None)
                if not liens:
                    self.assertEqual(page.locator('#contenu a[href^="#/ot"], #contenu a[href^="#/magasin"]').count(), 0)
                self.verifier_sans_piege()

    def test_la_mere_liste_ses_sous_pages_apres_le_texte(self):
        for profil in ("demandeur", "technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                responsable = profil == "responsable"
                lu = self.lire("EQ-0005")
                # Par titre, dans l'ordre alphabétique français (« Étanchéité » avant « garniture ») ; l'archivée n'y est pas.
                titres = {"WP-0012": TITRE_SP_GARNITURE, "WP-0013": TITRE_SP_ETANCHEITE, "WP-0014": TITRE_SP_PIEGE}
                ordre = page.evaluate(TRIER_TITRES_JS, list(titres.items()))
                self.assertLess(ordre.index("WP-0013"), ordre.index("WP-0012"))
                self.assertEqual(lu["sousPages"], [[i, titres[i], "#/wiki/" + i] for i in ordre])
                self.assertEqual([[s["id"], s["titre"]] for s in self.wiki("EQ-0005")["sousPages"]], [[i, titres[i]] for i in ordre])
                self.assertEqual(lu["nombre"], "3")
                self.assertEqual(lu["blocs"], ["entete-page", "wiki-couche", "wiki-texte", "wiki-sous-pages", "wiki-a-trancher",
                                               "wiki-retours"] + (["wiki-en-attente"] if responsable else []))
                self.assertIsNone(lu["mere"])
                self.assertEqual(lu["dataMere"], "")
                # La phrase de renvoi de la mère mène à ses sous-pages.
                self.assertEqual(lu["rubriques"][3][1][-1]["liens"], [[TITRE_SP_GARNITURE, "#/wiki/WP-0012"],
                                                                      [TITRE_SP_ETANCHEITE, "#/wiki/WP-0013"],
                                                                      [plat(TITRE_SP_PIEGE), "#/wiki/WP-0014"]])
                # Mère d'un autre type : composant, savoir-faire ; une page sans sous-page n'a pas la section.
                self.assertEqual(self.lire("ART-0016")["sousPages"], [["WP-0016", TITRE_SP_KIT, "#/wiki/WP-0016"]])
                self.assertEqual(self.lire("WP-0011")["sousPages"], [["WP-0017", TITRE_SP_REGLAGE, "#/wiki/WP-0017"]])
                self.assertEqual(self.lire("WP-0018")["sousPages"], [["WP-0019", TITRE_SP_ALIGNER, "#/wiki/WP-0019"]])
                for identifiant in ("WP-0002", "WP-0003", "WP-0012"):
                    self.assertIsNone(self.lire(identifiant)["sousPages"], identifiant)
                self.verifier_sans_piege()
        # On va de la mère à la sous-page, puis de la sous-page à la mère.
        self.aller_wiki("EQ-0005")
        page.click('#wiki-sous-pages a[href="#/wiki/WP-0013"]')
        page.wait_for_selector('.wiki-page[data-page="WP-0013"] #wiki-mere')
        page.click("#wiki-mere a")
        page.wait_for_selector('.wiki-page[data-page="EQ-0005"] #wiki-sous-pages')

    def test_sous_pages_de_composant_et_de_savoir_faire_et_mere_archivee(self):
        for profil in ("technicien", "demandeur"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                liens = profil == "technicien"
                # Composant : la mère, la fiche de l'article de la mère (pas de magasin pour le demandeur), rien de calculé.
                lu = self.lire("WP-0016")
                self.assertEqual((lu["h1"], lu["typeBadge"], lu["mere"], lu["mereLien"]),
                                 (TITRE_SP_KIT, "Composant", "Sous-page de " + TITRE_KIT, [TITRE_KIT, "#/wiki/ART-0016"]))
                self.assertEqual(lu["fiche"], ["Fiche de l'article", "#/magasin/article/ART-0016"] if liens else None)
                self.assertEqual(lu["blocs"], ["entete-page", "wiki-texte", "wiki-retours"])
                self.assertEqual((lu["entete"], lu["calcule"]), (None, 0))
                self.assertNotIn("Pas d'article au magasin", page.inner_text("#contenu"))
                self.verifier_texte(lu, TEXTE_SP_KIT, liens, ORIGINE_IA % "15/10/2026")
                # Savoir-faire : l'en-tête de sa mère — consignation de la fiche, telle quelle, et la phrase des savoir-faire —,
                # que la mère soit rattachée à l'équipement (WP-0011) ou à la page de l'équipement (WP-0018).
                consignation = self.consignation_po02()
                for identifiant, mere, titre_mere in (("WP-0017", "WP-0011", TITRE_PIEGE), ("WP-0019", "WP-0018", TITRE_SF_ALIGNER)):
                    lu = self.lire(identifiant)
                    self.assertEqual(lu["mereLien"], [titre_mere, "#/wiki/" + mere], identifiant)
                    self.assertEqual(lu["blocs"], ["entete-page", "wiki-entete", "wiki-texte", "wiki-retours"], identifiant)
                    self.assertEqual((lu["entete"]["titre"], lu["entete"]["phrase"], lu["entete"]["consignation"]),
                                     ("Consignation de PO-02", PHRASE_SAVOIR_FAIRE, consignation), identifiant)
                    self.assertEqual(lu["fiche"], ["Fiche de l'équipement", "#/equipement/EQ-0005"], identifiant)
                    self.assertEqual(self.lire(mere)["entete"]["consignation"], consignation, mere)
                self.assertIsNone(self.lire("WP-0018")["mere"])               # rattaché à une page d'un autre type
                self.verifier_sans_piege()
        # Mère archivée : nommée sans lien, « page archivée » ; la sous-page garde sa consignation.
        page.evaluate(ECRIRE_JS, ["wiki_pages", "WP-0018", {"statut": "archivée"}])
        lu = self.lire("WP-0019")
        self.assertEqual((lu["mere"], lu["mereLien"], lu["mereArchivee"]),
                         ("Sous-page de " + TITRE_SF_ALIGNER + " page archivée", None, TITRE_SF_ALIGNER))
        self.assertEqual(lu["entete"]["consignation"], consignation)

    def test_liste_des_savoir_faire_et_leurs_sous_pages(self):
        for profil in ("demandeur", "technicien", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil, base=True)
                self.aller("#/wiki/savoir-faire", ".wiki-liste-entites[data-liste=savoir-faire] li")
                lignes = page.evaluate("""() => Array.from(document.querySelectorAll('.wiki-liste-entites li')).map((li) => [li.dataset.id,
                  li.querySelector('.wiki-ligne-corps > a').textContent, Array.from(li.querySelectorAll('.wiki-ligne-sous a'))
                  .map((a) => [a.textContent, a.getAttribute('href')])])""")
                savoir = [[p["id"], p["titre"]] for p in PAGES_SOUS_PAGES if p["type"] == "savoir-faire" and p["statut"] != "archivée"]
                # Base de TestPagesDuWiki (5 savoir-faire) : deux sous-pages de savoir-faire (WP-0017, WP-0019) et WP-0018
                self.assertEqual(len(savoir), 8)
                self.assertEqual([l[0] for l in lignes], page.evaluate(TRIER_TITRES_JS, savoir))
                sous = {l[0]: l for l in lignes}
                self.assertEqual(sous["WP-0017"][1], TITRE_SP_REGLAGE)
                self.assertEqual(sous["WP-0017"][2][-1], [TITRE_PIEGE, "#/wiki/WP-0011"])          # « sous-page de » sa mère
                self.assertEqual(sous["WP-0019"][2][-1], [TITRE_SF_ALIGNER, "#/wiki/WP-0018"])
                self.assertEqual(sous["WP-0018"][2], [[TITRE_PO02, "#/wiki/EQ-0005"]])            # rattaché à la machine
                # Les sous-pages de machine et d'article (types retirés) ne sont dans aucune liste ; l'archivée nulle part
                for liste in ("machines", "articles", "savoir-faire"):
                    self.aller("#/wiki/" + liste, '.wiki-liste-entites[data-liste="%s"]' % liste)
                    for ident in ("WP-0012", "WP-0013", "WP-0014", "WP-0015", "WP-0016"):
                        self.assertEqual(page.locator('#contenu [data-id="%s"], #contenu a[href="#/wiki/%s"]' % (ident, ident)).count(), 0)
                self.verifier_sans_piege()

    def test_titres_pieges_de_sous_page_restent_du_texte(self):
        page = self.ouvrir("responsable", base=True)
        lu = self.lire("WP-0014")
        self.assertEqual(page.evaluate("document.querySelector('#contenu h1').textContent"), TITRE_SP_PIEGE)
        self.assertEqual(lu["mereLien"], [TITRE_PO02, "#/wiki/EQ-0005"])
        self.verifier_sans_piege()
        # Sous-page d'une mère au titre piégé : « Sous-page de » reste du texte.
        lu = self.lire("WP-0017")
        self.assertEqual(lu["mereLien"], [TITRE_PIEGE, "#/wiki/WP-0011"])
        self.assertEqual(page.evaluate("document.querySelector('#contenu h1').textContent"), TITRE_SP_REGLAGE)
        self.verifier_sans_piege()
        # Liste des sous-pages de la mère et index.
        self.assertIn(["WP-0014", TITRE_SP_PIEGE, "#/wiki/WP-0014"], self.lire("EQ-0005")["sousPages"])
        self.assertEqual(page.locator("#wiki-sous-pages *:not(h2):not(.badge):not(ul):not(li):not(a):not(p)").count(), 0)
        self.verifier_sans_piege()
        # Sous-page de savoir-faire au titre piégé, dans la liste des savoir-faire
        self.aller("#/wiki/savoir-faire", '.wiki-liste-entites li[data-id="WP-0017"]')
        self.assertEqual(page.evaluate("document.querySelector('li[data-id=\"WP-0017\"] .wiki-ligne-corps > a').textContent"), TITRE_SP_REGLAGE)
        self.verifier_sans_piege()

    def test_modifier_une_sous_page(self):
        """Refonte 2 (T138) : une sous-page de machine (type retiré) ne s'écrit plus, elle s'archive ; une sous-page de
        savoir-faire se modifie et garde sa mère et la consignation de PO-02 (deux rattachements)."""
        page = self.ouvrir("responsable", base=True)
        self.lire("WP-0012")
        page.click("#wiki-modifier")
        page.wait_for_selector('.wj-ecrire[data-page="WP-0012"] .wj-type-retire')
        page.fill("#wj-texte", TEXTE_SP_GARNITURE + "\n- La garniture tient après le rodage [OT-2025-0010]")
        page.click(".wj-enregistrer")
        page.wait_for_function("document.querySelector('.wj-annonce').textContent.includes('type de page retiré')")
        self.assertEqual(page.evaluate("location.hash"), "#/wiki-ecrire/WP-0012")
        ligne = page.evaluate("Donnees.trouver('wiki_pages', 'WP-0012')")
        self.assertEqual((ligne["texte"], ligne["version"]), (TEXTE_SP_GARNITURE, "1"))

        self.lire("WP-0019")
        page.click("#wiki-modifier")
        page.wait_for_selector('.wj-ecrire[data-page="WP-0019"]')
        self.assertEqual(page.query_selector_all(".wj-type-retire"), [])
        avant = page.input_value("#wj-texte")
        apres = avant + "\n- Serrer le comparateur sans forcer [OT-2026-0214]"
        page.fill("#wj-texte", apres)
        page.click(".wj-enregistrer")
        page.wait_for_function("location.hash === '#/wiki/WP-0019'")
        ligne = page.evaluate("Donnees.trouver('wiki_pages', 'WP-0019')")
        self.assertEqual((ligne["texte"], ligne["version"], ligne["rattache_a"], ligne["equipement_id"], ligne["statut"]),
                         (apres, "2", "WP-0018", "", "active"))
        lu = self.lire("WP-0019")
        self.assertEqual(lu["mereLien"], [TITRE_SF_ALIGNER, "#/wiki/WP-0018"])
        self.assertIn("Serrer le comparateur sans forcer", page.inner_text("#wiki-texte"))
        self.assertIn(", puis modifié à la main — validé par", lu["origine"])
        self.assertEqual((lu["entete"]["titre"], lu["entete"]["consignation"]), ("Consignation de PO-02", self.consignation_po02()))

    def parcourir(self, verifier):
        """Accueil, liste des savoir-faire, mères et sous-pages des trois types."""
        self.aller_accueil()
        verifier("#contenu", "accueil")
        self.aller("#/wiki/savoir-faire", ".wiki-liste-entites[data-liste=savoir-faire] li")
        verifier("#contenu", "liste des savoir-faire")
        for identifiant in SOUS_PAGES_PARCOURUES:
            self.aller_wiki(identifiant)
            verifier("#contenu", "page " + identifiant)

    def test_1440_et_375_px_sans_defilement_horizontal_et_zones_de_48_px(self):
        for largeur, hauteur, telephone in ((1440, 900, False), (375, 812, True)):
            for profil in ("responsable", "demandeur"):
                with self.subTest(largeur=largeur, profil=profil):
                    self.ouvrir(profil, largeur=largeur, hauteur=hauteur, telephone=telephone, base=True)

                    def verifier(racine, ou):
                        largeur_page, ecran = self.page.evaluate(LARGEUR_JS)
                        self.assertLessEqual(largeur_page, ecran, "%s : page plus large que l'écran (%s > %s)" % (ou, largeur_page, ecran))
                        if telephone:
                            zones = self.page.evaluate(ZONES_JS, racine)
                            self.assertEqual([z for z in zones if z[2] < 47.5], [], "%s : zones de moins de 48 px" % ou)
                    self.parcourir(verifier)

    def test_contrastes_aa_en_theme_clair_et_sombre(self):
        for theme in ("clair", None):
            with self.subTest(theme=theme or "sombre"):
                page = self.ouvrir("technicien", largeur=1440, hauteur=900, theme=theme, base=True)
                self.assertEqual(page.evaluate("document.documentElement.dataset.theme || null"), theme)

                def verifier(racine, ou):
                    page.wait_for_timeout(100)
                    self.assertEqual(page.evaluate(AUDIT_TEXTES_JS, racine), [], ou)
                self.parcourir(verifier)


# ---------------------------------------------------------------------------
# Affichage : 1440 et 375 px, zones tactiles, contrastes, réseau
# ---------------------------------------------------------------------------

PAGES_PARCOURUES = ("EQ-0005", "ART-0016", "WP-0002", "WP-0003", "WP-0005", "WP-0006", "WP-0007", "WP-0010", "WP-0011")


class TestAffichage(CasWiki):

    def parcourir(self, verifier, profil):
        """Accueil (suivi, recherche, résultats ouverts), pages des quatre types (base d'essai), pages d'équipement de la
        démo (résultats et détails ouverts), fiche équipement ; puis DI et OT (blocs wiki)."""
        page = self.page
        self.poser_base()
        self.aller_accueil()
        self.chercher_accueil("fuite garniture")
        for bouton in page.locator("#wiki-trouves .wiki-voir-plus, #wiki-trouves .wiki-voir-autres").all():
            bouton.click()
        verifier("#contenu", "accueil")
        for identifiant in PAGES_PARCOURUES:
            self.aller_wiki(identifiant)
            verifier("#contenu", "page " + identifiant)
        for equipement in ("EQ-0001", "EQ-0023", "EQ-0031"):
            self.aller_page(equipement)
            self.chercher(".wiki-page .wiki-recherche", "capteur filtre")
            page.evaluate("() => document.querySelectorAll('.wiki-page details').forEach((d) => { d.open = true; })")
            verifier("#contenu", "page " + equipement)
        self.aller("#/equipement/EQ-0001", "#lien-wiki-equipement")
        verifier("p:has(> #lien-wiki-equipement)", "fiche équipement")
        self.aller("#/di/nouvelle?equipement=EQ-0005", ".wiki-recherche-demande")
        page.fill("input[name=symptome]", "garniture")
        self.attendre_resultats(".wiki-recherche-demande")
        verifier(".wiki-recherche-demande", "saisie d'une DI")
        if profil != "demandeur":
            ot = page.evaluate("() => Wiki.pageEquipement('EQ-0001').dernieres[1].id")
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


if __name__ == "__main__":
    unittest.main()
