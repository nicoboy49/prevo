"""Photographie des écrans de Prévo : textes visibles et attributs lus, relevés écran par écran (chantier i18n,
Lot 2, T235 ; critère CS148 : « l'écran ne change en rien » quand les textes passent dans js/i18n/fr.js).

CE QUI EST RELEVÉ
    Deux modes, un fichier JSON par mode (tests/fixtures/ecrans-reference/demo.json et serveur.json) :
      - demo    : index.html ouvert en file://, « Essayer avec les données de démo » (la démo vit en mémoire) ;
      - serveur : serveur.py sur une COPIE du jeu de démo (tests/commun.py ServeurPrevo), avec les trois comptes de
                  test (comptes=True : écran de connexion, rôles, Équipe › Accès), plus un second serveur sur un dossier
                  vide (base vide, assistant d'installation) et la porte des téléphones (acces/porte.html).
    Pour chaque profil (Demandeur, Technicien, Responsable, dans cet ordre), chaque écran de la liste ECRANS (routes
    du routeur de js/app.js, avec des objets du jeu de démo désignés par tests/fixtures/demo-scenarios.json) :
      - l'écran lui-même (#contenu, les alertes de la coque) ;
      - chacun de ses onglets ([role=tab], parcourus un par un, onglets imbriqués compris) : le panneau ouvert ;
      - ses fenêtres les plus courantes (décisions, motifs, confirmations) : la fenêtre <dialog> ouverte, refermée
        ensuite par Échap (rien n'est enregistré) ; et des formulaires envoyés vides (messages d'erreur) ;
      - la coque une fois par profil : menu latéral (bureau), puis en-tête et barre du bas (téléphone, 375 × 812).
    Hors profil : l'écran de démarrage et le choix du profil (démo) ; l'écran de connexion, une connexion refusée, la
    porte (Android, iPhone, autre appareil), la base vide et l'assistant d'installation (serveur).
    Pour chaque zone relevée : le texte visible (innerText, coupé aux fins de ligne et aux tabulations des tableaux,
    bords nettoyés, chaque morceau compté) et les attributs lus par l'utilisateur sur les éléments rendus (title,
    placeholder, aria-label, alt, value des boutons input, <title> des dessins SVG), plus le titre de l'onglet du
    navigateur. Les entrées sont triées (avec leur nombre) ; les écrans sont dans l'ordre fixe de ECRANS. Les
    espaces insécables restent tels quels (écrits \\u00a0, \\u202f dans le JSON : une espace ordinaire à leur place
    est un écart).

DÉTERMINISME
    Horloges figées à la date de référence du jeu de démo (dateReference de js/demo-donnees.js), 9 h 30 :
      - navigateur : Playwright clock.set_fixed_time (heure de Paris) ; la démo ne décale donc pas ses dates ;
      - serveur de test : un sitecustomize.py (trouvé par PYTHONPATH au démarrage du processus de serveur.py, qui
        n'est pas modifié) fige time.time() à la même heure locale : sauvegarde « avant mise à jour », journal des
        connexions, sessions. Les comptes de test sont écrits avec leurs dates à cette heure (sinon le mot de passe,
        « changé » à l'heure réelle, refuserait les sessions ouvertes à l'heure figée).
    Fuseau Europe/Paris, langue fr-FR, fenêtre 1280 × 800, échelle 1, thème clair, animations réduites
    (prefers-reduced-motion : les graphiques ne s'animent pas), agent du navigateur fixe (AGENT : le journal des
    connexions l'affiche). Aide à l'écran ACTIVE (comme chez l'utilisateur à la première visite : l'encart de chaque
    écran est relevé). Un écran est relevé quand il est « calme » : écran attendu affiché (App.ecranCourant), aucune
    requête fetch ni script en cours de chargement, aucun [aria-busy=true], aucun changement du DOM pendant 400 ms.
    Ce qui varie encore est MASQUÉ (remplacé par un repère entre chevrons, dans le texte, les attributs, le titre, et
    sur les captures d'image) — voir masques() et MASQUES_ELEMENTS :
      ‹version›          numéro de version de Prévo (VERSION de js/app.js) : change à chaque version ;
      ‹date-version›     date de cette version (DATE_VERSION de js/app.js) dans « À propos », masquée par sa place
                         (une date du jeu de démo peut lui ressembler : aucune date n'est masquée sur sa forme) ;
      ‹port›             port du serveur de test (choisi libre à chaque lancement) ;
      ‹dossier-prevo›, ‹dossier-temporaire›   dossier du dépôt et dossiers temporaires du serveur de test ;
      ‹nom-du-pc›        nom réseau de ce PC ; ‹adresse-reseau› ses adresses IPv4 hors 127.x (étiquettes, porte).
    Sur une capture, un élément dont un attribut lu porte un masque (QR code qui contient l'adresse et le port) est
    couvert d'un aplat gris.
    Non relevé : les notifications passagères (toasts, leur durée dépend du hasard des délais), la zone d'impression,
    les textes dessinés dans une image (illustrations de la porte) ; un seul format d'écran (bureau), plus la coque
    au téléphone.

LANCER (depuis la racine du projet ; Playwright et Chromium, comme les tests)
    py -X utf8 outils/photographier_ecrans.py                    relevé des deux modes, comparé à la référence
    py -X utf8 outils/photographier_ecrans.py --mode demo        un seul mode
    py -X utf8 outils/photographier_ecrans.py --sortie DOSSIER   écrit aussi les relevés (demo.json, serveur.json)
    py -X utf8 outils/photographier_ecrans.py --captures DOSSIER     captures PNG des écrans principaux (profil
                                                                 Responsable, bureau, les deux modes) dans DOSSIER
    py -X utf8 outils/photographier_ecrans.py --captures NOUVELLES --comparer-captures REFERENCES
                                                                 compare chaque capture à sa référence (au pixel)
    py -X utf8 outils/photographier_ecrans.py --reference        REPREND la référence des textes (chef de chantier
                                                                 seulement, jamais un test) : réécrit
                                                                 tests/fixtures/ecrans-reference/<mode>.json
    Le test tests/test_ecrans_identiques.py refait le relevé et le compare à la référence (même code que ci-dessus).
    Code de sortie : 0 identique, 1 écart (ou capture différente), 2 erreur (écran introuvable, erreur JavaScript).

LIRE UN ÉCART
    Chaque écart nomme le mode, le profil et l'écran (« fiche-ot:en-cours › onglet execution »), puis les entrées
    disparues (« - avant ») et apparues (« + après »), avec leur nombre si elles sont répétées et la sorte d'entrée
    (texte, attribut, titre). Un mot changé dans un module donne une ligne « - avant » et une ligne « + après » ; un
    écran absent de l'un des deux relevés est dit tel quel. Exemple (« Demandes à traiter » changé dans
    js/modules/accueil-bento.js) :
        [demo] responsable / accueil
            - avant, texte : « Demandes à traiter »
            + après, texte : « Demandes en attente »
    Les captures d'image : « identique » ou le nombre de pixels qui diffèrent et le rectangle qui les contient.

AJOUTER UN ÉCRAN
    Une ligne E(...) dans ECRANS (route, profils, fenêtres), puis reprise de la référence (--reference) par le chef de
    chantier, sur un code dont les écrans sont tenus pour bons.

Bibliothèque standard + Playwright (Python). Aucune écriture dans donnees/ : démo en mémoire, serveurs de test sur
des copies temporaires (tests/commun.py).
"""
import argparse
import base64
import datetime
import json
import os
import re
import socket
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE / "tests") not in sys.path:
    sys.path.insert(0, str(RACINE / "tests"))
import commun  # noqa: E402  (aides des tests : ServeurPrevo, comptes de test, scénarios du jeu de démo)

DOSSIER_REFERENCE = RACINE / "tests" / "fixtures" / "ecrans-reference"
MODES = ("demo", "serveur")
PROFILS = ("demandeur", "technicien", "responsable")
TOUS = PROFILS
INTERVENANTS = ("technicien", "responsable")
RESPONSABLE = ("responsable",)

FENETRE = {"width": 1280, "height": 800}
TELEPHONE = {"width": 375, "height": 812}
LANGUE = "fr-FR"
FUSEAU = "Europe/Paris"
HEURE_FIGEE = "09:30"
DELAI_MS = 20000
CALME_MS = 400                 # aucun changement du DOM pendant ce temps : l'écran est fini
SONDE_MS = 100
DELAI_CALME_S = 20
POSTE = "PC atelier"
# Agent du navigateur au bureau : fixe (le journal des connexions du mode serveur l'affiche ; celui de Chromium change
# à chaque version de Playwright). Les téléphones de la porte gardent celui de leur profil Playwright (non affiché).
AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 "
         "Safari/537.36")
# Identités des trois profils : celles des comptes de test du mode serveur (tests/commun.py COMPTES_DE_TEST), reprises
# telles quelles dans la démo pour que les deux modes se lisent pareil.
IDENTITES = {role: ((valeurs[1] + " " + valeurs[2]).strip(), valeurs[4]) for role, valeurs in commun.COMPTES_DE_TEST.items()}
MAUVAIS_MOT_DE_PASSE = "ce n'est pas le bon mot de passe"


def scenario(role):
    """Identifiant d'un objet de scénario du jeu de démo (tests/fixtures/demo-scenarios.json)."""
    return commun.scenarios_demo()[role]


# ---------------------------------------------------------------------------
# Écrans relevés, dans l'ordre (le même pour chaque profil)
# ---------------------------------------------------------------------------
# nom       : nom de l'écran dans le relevé (« id App » ou « id App:variante ») ;
# route     : hash de la route (une fonction pour les identifiants du jeu de démo) ;
# id        : App.ecranCourant.id attendu (défaut : le nom avant « : ») — un autre écran affiché est une erreur ;
# profils   : profils qui voient l'écran (comme profils de App.ecran) ; modes : défaut les deux ;
# onglets   : parcourir les onglets (défaut oui) ; capture : capture d'image (profil Responsable, bureau) ;
# fenetres  : [(nom, sélecteur du bouton qui ouvre la fenêtre)], profil Responsable seulement (celui qui décide) ;
# erreurs   : sélecteur du bouton d'envoi d'un formulaire laissé vide (les messages d'erreur sont relevés).

def E(nom, route, profils=TOUS, **options):
    ecran = {"nom": nom, "route": route, "profils": tuple(profils), "id": nom.split(":")[0], "onglets": True,
             "capture": False, "fenetres": (), "erreurs": None, "modes": MODES}
    ecran.update(options)
    return ecran


ECRANS = [
    E("accueil", "#/accueil", capture=True),
    E("liste-di", "#/di", capture=True),
    E("nouvelle-di", "#/di/nouvelle", capture=True, erreurs="#contenu .di-envoyer"),
    E("fiche-di:nouvelle", lambda: "#/di/" + scenario("di_statut_nouvelle"), capture=True,
      fenetres=(("accepter", '#contenu [data-decision="accepter"]'), ("differer", '#contenu [data-decision="differer"]'),
                ("refuser", '#contenu [data-decision="refuser"]'))),
    E("fiche-di:acceptee", lambda: "#/di/" + scenario("di_statut_acceptee")),
    E("fiche-di:refusee", lambda: "#/di/" + scenario("di_statut_refusee")),
    E("liste-ot", "#/ot", INTERVENANTS, capture=True),
    E("nouvel-ot", "#/ot/nouveau", RESPONSABLE, capture=True, erreurs='#contenu form button[type="submit"]'),
    E("fiche-ot:en-cours", lambda: "#/ot/" + scenario("ot_statut_en_cours"), INTERVENANTS, capture=True,
      fenetres=(("mettre-en-attente", '#contenu button[data-action="transition"][data-cible="En attente"]'),)),
    E("fiche-ot:planifie", lambda: "#/ot/" + scenario("ot_statut_planifie"), INTERVENANTS,
      fenetres=(("annuler", '#contenu button[data-action="transition"][data-cible="Annulé"]'),)),
    E("fiche-ot:preventif", lambda: "#/ot/" + scenario("ot_preventif_ouvert"), INTERVENANTS),
    E("fiche-ot:cloture-technique", lambda: "#/ot/" + scenario("ot_statut_cloture_technique"), INTERVENANTS,
      fenetres=(("cloturer", '#contenu button[data-action="transition"][data-cible="Clôturé administrativement"]'),)),
    E("fiche-ot:verrouille", lambda: "#/ot/" + scenario("ot_statut_cloture_administratif"), INTERVENANTS),
    E("parc", "#/parc", capture=True),
    E("parc-etiquettes", "#/parc/etiquettes", RESPONSABLE),
    E("equipement", lambda: "#/equipement/" + scenario("causes_equipement_2"), capture=True,
      fenetres=(("desactiver", "#contenu #parc-activite"),)),
    E("equipement:habilitation", lambda: "#/equipement/" + scenario("equipement_br")),
    E("equipement-nouveau", "#/equipement/nouveau", RESPONSABLE, erreurs='#contenu form button[type="submit"]'),
    E("equipement-modifier", lambda: "#/equipement/" + scenario("causes_equipement_2") + "/modifier", RESPONSABLE,
      capture=True),
    E("preventif", "#/preventif", INTERVENANTS, capture=True),
    E("preventif-gamme", lambda: "#/preventif/gamme/" + scenario("gamme_mensuelle_echue"), INTERVENANTS),
    E("preventif-gamme-nouvelle", "#/preventif/gamme/nouvelle", RESPONSABLE),
    E("planning", "#/planning", INTERVENANTS, capture=True),
    E("magasin", "#/magasin", INTERVENANTS, capture=True),
    E("magasin-article", lambda: "#/magasin/article/" + scenario("kit_garniture"), INTERVENANTS),
    E("magasin-article-nouveau", "#/magasin/article/nouveau", RESPONSABLE),
    E("controles", "#/controles", INTERVENANTS, capture=True),
    E("controles-fiche", lambda: "#/controles/" + scenario("controle_en_retard"), INTERVENANTS),
    E("controles-nouveau", "#/controles/nouveau", RESPONSABLE),
    E("indicateurs", "#/indicateurs", RESPONSABLE, capture=True),
    E("wiki", "#/wiki", capture=True),
    E("wiki-liste:machines", "#/wiki/machines"),
    E("wiki-liste:pannes", "#/wiki/pannes"),
    E("wiki-liste:articles", "#/wiki/articles"),
    E("wiki-liste:techniciens", "#/wiki/techniciens"),
    E("wiki-liste:savoir-faire", "#/wiki/savoir-faire"),
    E("wiki-liste:interventions", "#/wiki/interventions"),
    E("wiki-page:machine", lambda: "#/wiki/" + scenario("causes_equipement_2"), capture=True),
    E("wiki-page:article", lambda: "#/wiki/" + scenario("kit_garniture")),
    E("wiki-page:technicien", lambda: "#/wiki/" + scenario("technicien_br_valide")),
    E("wiki-journal", "#/wiki-journal", RESPONSABLE),
    E("wiki-ecrire", lambda: "#/wiki-ecrire/" + scenario("causes_equipement_2"), RESPONSABLE),
    E("import", "#/import", RESPONSABLE, capture=True),
    E("equipe", "#/equipe", INTERVENANTS, capture=True),
    E("equipe-fiche", lambda: "#/equipe/" + scenario("technicien_br_valide"), INTERVENANTS,
      fenetres=(("ajouter-habilitation", "#contenu #equipe-ajouter-habilitation"),
                ("renouveler", '#contenu button[data-action="renouveler"]'))),
    E("equipe-fiche:habilitation-echue", lambda: "#/equipe/" + scenario("technicien_br_echue"), INTERVENANTS),
    E("equipe-nouveau", "#/equipe/nouveau", RESPONSABLE),
    E("equipe-acces", "#/equipe/acces", RESPONSABLE, modes=("serveur",), capture=True,
      fenetres=(("modifier", '#contenu button[data-action="modifier"]'),
                ("reinitialiser", '#contenu button[data-action="reinitialiser"]'))),
    E("parametres", "#/parametres", RESPONSABLE, capture=True),
    E("controle", "#/controle", RESPONSABLE),
    E("installation-fiche", "#/installation/fiche", RESPONSABLE, modes=("serveur",)),
    E("poste", "#/poste", capture=True),
    E("apropos", "#/apropos", capture=True),
]

# Zones relevées : l'écran (contenu et alertes de la coque), la coque, une fenêtre ouverte, un écran plein.
ZONES_ECRAN = ["#alertes-app", "#bandeau-changement", "#contenu"]
ZONES_COQUE = [".menu-lateral", ".entete-mobile", "#bandeau-demo", "#barre-bas"]
ZONES_FENETRE = ["dialog[open]"]
ZONES_PLEIN = [".ecran-plein:not([hidden])", "dialog[open]"]
ZONES_PAGE = ["body"]

# ---------------------------------------------------------------------------
# Scripts de page
# ---------------------------------------------------------------------------

# Avant tout script de la page : compteurs pour savoir quand l'écran est fini (changements du DOM, requêtes fetch,
# scripts en cours de chargement). Rien d'autre n'est changé dans la page.
SCRIPT_SURVEILLANCE = r"""
(() => {
  if (window.__photo) return;
  const etat = window.__photo = { mutations: 0, requetes: 0, scripts: 0 };
  const suivreScript = (noeud) => {
    if (noeud.nodeName !== 'SCRIPT' || !noeud.src || noeud.__photoSuivi) return;
    noeud.__photoSuivi = true;
    etat.scripts += 1;
    const fin = () => { etat.scripts -= 1; noeud.removeEventListener('load', fin); noeud.removeEventListener('error', fin); };
    noeud.addEventListener('load', fin);
    noeud.addEventListener('error', fin);
  };
  new MutationObserver((liste) => {
    etat.mutations += liste.length;
    for (const changement of liste) for (const noeud of changement.addedNodes) suivreScript(noeud);
  }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true,
    attributeFilter: ['hidden', 'open', 'title', 'placeholder', 'aria-label', 'alt', 'value', 'aria-busy', 'class'] });
  const fetchOrigine = window.fetch;
  if (typeof fetchOrigine === 'function') {
    window.fetch = function (...arguments_) {
      etat.requetes += 1;
      let promesse;
      try { promesse = fetchOrigine.apply(this, arguments_); } catch (erreur) { etat.requetes -= 1; throw erreur; }
      return promesse.finally(() => { etat.requetes -= 1; });
    };
  }
})();
"""

SCRIPT_ETAT = """() => {
  const e = window.__photo || { mutations: -1, requetes: 0, scripts: 0 };
  return [e.mutations, e.requetes, e.scripts, Boolean(document.querySelector('[aria-busy="true"]'))];
}"""

# Relevé d'une ou plusieurs zones : texte visible et attributs lus, masqués ; titre de l'onglet.
SCRIPT_RELEVE = r"""
([zones, masques, elementsMasques]) => {
  const regles = masques.map(([motif, remplacement]) => [new RegExp(motif, 'g'), remplacement]);
  const masquer = (texte) => regles.reduce((valeur, [motif, remplacement]) => valeur.replace(motif, remplacement), texte);
  // Masques par élément : contenu remplacé le temps du relevé, puis remis (mêmes nœuds, rien n'est recréé).
  const remis = [];
  for (const [selecteur, repere] of elementsMasques) {
    for (const element of document.querySelectorAll(selecteur)) {
      remis.push([element, [...element.childNodes]]);
      element.textContent = repere;
    }
  }
  const nettoyer = (texte) => String(texte).replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, '');
  const rendu = (element) => element.getClientRects().length > 0
    && (typeof element.checkVisibility !== 'function' || element.checkVisibility({ visibilityProperty: true }));
  const racines = [];
  for (const selecteur of zones) {
    for (const element of document.querySelectorAll(selecteur)) {
      if (!rendu(element) || racines.some((racine) => racine.contains(element))) continue;
      for (let i = racines.length - 1; i >= 0; i -= 1) if (element.contains(racines[i])) racines.splice(i, 1);
      racines.push(element);
    }
  }
  const SVG = 'http://www.w3.org/2000/svg';
  const ATTRIBUTS = ['title', 'placeholder', 'aria-label', 'alt'];
  const texte = [];
  const attributs = [];
  for (const racine of racines) {
    for (const morceau of String(racine.innerText || '').split(/[\n\t]/)) {
      const propre = nettoyer(morceau);
      if (propre) texte.push(masquer(propre));
    }
    for (const element of [racine, ...racine.querySelectorAll('*')]) {
      if (element.namespaceURI === SVG && element.localName === 'title') {
        const parent = element.parentElement;
        const valeur = nettoyer(element.textContent || '');
        if (valeur && parent && rendu(parent)) attributs.push('svg-title=' + masquer(valeur));
        continue;
      }
      if (!rendu(element)) continue;
      for (const nom of ATTRIBUTS) {
        const valeur = element.getAttribute(nom);
        if (valeur !== null && nettoyer(valeur)) attributs.push(nom + '=' + masquer(nettoyer(valeur)));
      }
      if (element.localName === 'input' && ['button', 'submit', 'reset'].includes(element.type) && nettoyer(element.value)) {
        attributs.push('value=' + masquer(nettoyer(element.value)));
      }
    }
  }
  for (const [element, enfants] of remis.reverse()) element.replaceChildren(...enfants);
  return { zones: racines.length, titre: masquer(document.title || ''), texte, attributs };
}
"""

# Même masquage, appliqué à la page avant une capture d'image : nœuds de texte et masques par élément réécrits ; un
# élément dont un attribut lu porte un masque (un QR code qui contient l'adresse et le port) est marqué
# data-photo-masque, et couvert d'un aplat sur la capture.
SCRIPT_MASQUER_PAGE = r"""
([masques, elementsMasques]) => {
  const regles = masques.map(([motif, remplacement]) => [new RegExp(motif, 'g'), remplacement]);
  const masquer = (texte) => regles.reduce((valeur, [motif, remplacement]) => valeur.replace(motif, remplacement), texte);
  for (const [selecteur, repere] of elementsMasques) {
    for (const element of document.querySelectorAll(selecteur)) element.textContent = repere;
  }
  const parcours = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let noeud = parcours.nextNode(); noeud; noeud = parcours.nextNode()) {
    const apres = masquer(noeud.nodeValue);
    if (apres !== noeud.nodeValue) noeud.nodeValue = apres;
  }
  for (const element of document.body.querySelectorAll('*')) {
    for (const nom of ['title', 'placeholder', 'aria-label', 'alt', 'src', 'href', 'data-url']) {
      const valeur = element.getAttribute(nom);
      if (valeur !== null && masquer(valeur) !== valeur) element.setAttribute('data-photo-masque', '1');
    }
  }
  document.querySelectorAll('.toast.visible').forEach((toast) => toast.classList.remove('visible'));
}
"""

# Onglets de l'écran : barres [role=tablist] rendues (signature = identifiants de leurs onglets), onglet choisi.
SCRIPT_ONGLETS = r"""
(selecteurRacine) => {
  const racine = document.querySelector(selecteurRacine);
  if (!racine) return [];
  const rendu = (element) => element.getClientRects().length > 0;
  return [...racine.querySelectorAll('[role="tablist"]')].filter(rendu).map((barre) => {
    const onglets = [...barre.querySelectorAll('[role="tab"]')];
    const ids = onglets.map((onglet, rang) => onglet.dataset.onglet || ('n' + (rang + 1)));
    return { signature: ids.join('|'), ids, choisi: ids[onglets.findIndex((o) => o.getAttribute('aria-selected') === 'true')] || null };
  });
}
"""

# Clique un onglet d'une barre (par signature) et marque son panneau (data-photo-zone) ; rend false s'il manque.
SCRIPT_CLIC_ONGLET = r"""
([selecteurRacine, signature, id]) => {
  const racine = document.querySelector(selecteurRacine);
  document.querySelectorAll('[data-photo-zone]').forEach((element) => element.removeAttribute('data-photo-zone'));
  for (const barre of racine ? racine.querySelectorAll('[role="tablist"]') : []) {
    const onglets = [...barre.querySelectorAll('[role="tab"]')];
    const ids = onglets.map((onglet, rang) => onglet.dataset.onglet || ('n' + (rang + 1)));
    if (ids.join('|') !== signature) continue;
    const onglet = onglets[ids.indexOf(id)];
    if (!onglet) return false;
    onglet.click();
    const panneau = document.getElementById(onglet.getAttribute('aria-controls') || '');
    if (panneau) panneau.setAttribute('data-photo-zone', '1');
    return true;
  }
  return false;
}
"""


# ---------------------------------------------------------------------------
# Horloge, masques
# ---------------------------------------------------------------------------

def date_reference():
    """Date de référence du jeu de démo (dateReference de js/demo-donnees.js), AAAA-MM-JJ."""
    texte = (RACINE / "js" / "demo-donnees.js").read_text(encoding="utf-8")
    return re.search(r"""dateReference:\s*["'](\d{4}-\d{2}-\d{2})["']""", texte).group(1)


def _dernier_dimanche(annee, mois):
    jour = datetime.date(annee, mois + 1, 1) - datetime.timedelta(days=1)
    return jour - datetime.timedelta(days=(jour.weekday() + 1) % 7)


def instant_fige():
    """Instant (millisecondes depuis 1970) de la date de référence à HEURE_FIGEE, heure de Paris, indépendant du
    fuseau du PC qui lance l'outil. Règle européenne : heure d'été (UTC+2) du dernier dimanche de mars au dernier
    dimanche d'octobre (à 9 h 30, le changement de la nuit est déjà fait)."""
    jour = datetime.date.fromisoformat(date_reference())
    heures, minutes = (int(x) for x in HEURE_FIGEE.split(":"))
    ete = _dernier_dimanche(jour.year, 3) <= jour < _dernier_dimanche(jour.year, 10)
    decalage = 2 if ete else 1
    utc = datetime.datetime(jour.year, jour.month, jour.day, heures, minutes, tzinfo=datetime.timezone.utc)
    return int((utc - datetime.timedelta(hours=decalage)).timestamp() * 1000)


def heure_affichee():
    return "%sT%s:00 (%s)" % (date_reference(), HEURE_FIGEE, FUSEAU)


def _litteral(texte):
    """Texte littéral écrit en expression régulière JavaScript (sans drapeau u)."""
    return re.sub(r"[.*+?^${}()|\[\]\\/]", lambda m: "\\" + m.group(0), texte)


def _version():
    """VERSION de js/app.js (« 2.0.0-beta.2 »)."""
    return re.search(r"const VERSION = '([^']+)'", (RACINE / "js" / "app.js").read_text(encoding="utf-8")).group(1)


def adresses_reseau():
    """Adresses IPv4 de ce PC hors 127.x (celles que serveur.py donne pour la porte et les étiquettes)."""
    adresses = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            adresses.add(info[4][0])
    except OSError:
        pass
    return sorted(a for a in adresses if not a.startswith("127."))


# Repères des masques (la liste, fixe, est écrite dans chaque relevé ; voir la docstring).
REPERES = ("‹adresse-reseau›", "‹date-version›", "‹dossier-prevo›", "‹dossier-temporaire›", "‹nom-du-pc›", "‹port›",
           "‹version›")

# Masques par élément : (sélecteur CSS, repère, raison) — le contenu de l'élément est remplacé par le repère. Pour ce
# qui ne se reconnaît pas à son texte : la date de la version (DATE_VERSION de js/app.js) dans « À propos » ressemble à
# n'importe quelle date du jeu de démo ; c'est la case qui précède celle de la mise à jour (#apropos-maj).
MASQUES_ELEMENTS = [
    ("dl.valeurs > dd:has(+ dt + dd#apropos-maj)", "‹date-version›", "date de la version (js/app.js DATE_VERSION)"),
]


def masques(mode, dossiers=(), ports=()):
    """[(motif JavaScript, remplacement, raison)] appliqués dans l'ordre à chaque texte relevé.

    dossiers, ports : dossiers temporaires et port du serveur de test de ce lancement (masqués en premier, et le port
    partout où il est écrit seul : « 127.0.0.1:54321 », « http 54321, https 8443 »).
    Rien n'est masqué sur la forme d'une date : les horloges sont figées (navigateur : Playwright ; serveur de test :
    horloge_figee_du_serveur), une date qui change est un écart."""
    liste = []
    chemins = [(Path(d), "‹dossier-temporaire›") for d in dossiers] + [(RACINE, "‹dossier-prevo›")]
    for chemin, repere in chemins:
        for forme in sorted({str(chemin), chemin.as_posix(), chemin.as_uri()}, key=len, reverse=True):
            liste.append((_litteral(forme), repere, "chemin propre à ce PC ou à ce lancement"))
    liste.append((r"prevo-(?:test|comptes|photo)-[A-Za-z0-9_]+", "‹dossier-temporaire›", "dossier temporaire des tests"))
    liste.append((_litteral(_version()), "‹version›", "numéro de version de Prévo (js/app.js VERSION)"))
    nom_pc = socket.gethostname()
    if nom_pc:
        liste.append((r"\b" + _litteral(nom_pc) + r"\b", "‹nom-du-pc›", "nom réseau de ce PC"))
    for adresse in adresses_reseau():
        liste.append((r"\b" + _litteral(adresse) + r"\b", "‹adresse-reseau›", "adresse réseau de ce PC"))
    for port in ports:
        liste.append((r"\b%d\b" % port, "‹port›", "port du serveur de test, libre à chaque lancement"))
    return liste


# Horloge figée du serveur de test : serveur.py lit l'heure par time.time() (maintenant_s, noms des sauvegardes,
# journal des connexions, sessions). Un sitecustomize.py, trouvé par PYTHONPATH au démarrage de son processus, la
# fige à la même date et heure que le navigateur (heure locale du PC) ; rien d'autre n'est changé dans serveur.py.
SITECUSTOMIZE = """# Écrit par outils/photographier_ecrans.py : horloge du serveur de test figée (photographie des écrans).
import time as _time
_FIGE = _time.mktime((%d, %d, %d, %d, %d, 0, 0, 0, -1))
_time.time = lambda: _FIGE
_time.time_ns = lambda: int(_FIGE) * 1000000000
"""


def comptes_a_l_heure_figee():
    """Octets de comptes.json (tests/commun.py comptes_json) avec leurs dates à l'heure figée du serveur."""
    contenu = json.loads(commun.comptes_json().decode("utf-8"))
    fige = "%sT%s:00" % (date_reference(), HEURE_FIGEE)
    for compte in contenu.get("comptes", []):
        for cle, valeur in list(compte.items()):
            if isinstance(valeur, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", valeur):
                compte[cle] = fige
    return json.dumps(contenu, ensure_ascii=False, indent=1).encode("utf-8")


def horloge_figee_du_serveur(dossier):
    """Écrit sitecustomize.py dans dossier ; rend l'environnement à donner à ServeurPrevo."""
    jour = datetime.date.fromisoformat(date_reference())
    heures, minutes = (int(x) for x in HEURE_FIGEE.split(":"))
    Path(dossier, "sitecustomize.py").write_text(SITECUSTOMIZE % (jour.year, jour.month, jour.day, heures, minutes),
                                                 encoding="utf-8")
    chemins = [str(dossier)] + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])
    return {"PYTHONPATH": os.pathsep.join(chemins)}


# ---------------------------------------------------------------------------
# Relevé
# ---------------------------------------------------------------------------

class ErreurReleve(RuntimeError):
    """Un écran n'a pas pu être relevé (écran introuvable, erreur JavaScript, écran jamais calme)."""


class Releveur:
    """Relevé d'un mode : un navigateur, un contexte par profil, les écrans dans l'ordre de ECRANS.

    captures : dossier où écrire les captures PNG des écrans principaux (profil Responsable), ou None.
    filtre : expression régulière sur les noms d'écran (mise au point ; jamais pour la référence)."""

    def __init__(self, playwright, navigateur, mode, captures=None, filtre=None, journal=None):
        self.playwright = playwright
        self.navigateur = navigateur
        self.mode = mode
        self.captures = Path(captures) if captures else None
        self.filtre = re.compile(filtre) if filtre else None
        self.journal = journal or (lambda texte: None)
        self.ecrans = []
        self.erreurs_js = []
        self.dossiers = []
        self.ports = []
        self.regles = [(motif, remplacement) for motif, remplacement, _ in masques(mode)]
        self.elements_masques = [(selecteur, repere) for selecteur, repere, _ in MASQUES_ELEMENTS]
        self.temporaire = None
        self.dernier = "début du relevé"

    def mettre_a_jour_masques(self):
        self.regles = [(motif, remplacement) for motif, remplacement, _ in masques(self.mode, self.dossiers, self.ports)]

    # -- contexte et page -----------------------------------------------------

    def nouveau_contexte(self, appareil=None, **options):
        reglages = dict(locale=LANGUE, timezone_id=FUSEAU, color_scheme="light", reduced_motion="reduce",
                        bypass_csp=True)
        if appareil:
            profil = dict(self.playwright.devices[appareil])
            profil.pop("default_browser_type", None)
            reglages.update(profil)
        else:
            reglages.update(viewport=dict(FENETRE), device_scale_factor=1, user_agent=AGENT)
        reglages.update(options)
        contexte = self.navigateur.new_context(**reglages)
        contexte.set_default_timeout(DELAI_MS)
        contexte.clock.set_fixed_time(instant_fige() / 1000)
        contexte.add_init_script(SCRIPT_SURVEILLANCE)
        return contexte

    def nouvelle_page(self, contexte, nom):
        page = contexte.new_page()
        page.on("pageerror", lambda erreur: self.erreurs_js.append("%s : %s" % (nom, erreur)))
        return page

    def verifier_erreurs(self):
        if self.erreurs_js:
            raise ErreurReleve("erreur JavaScript pendant le relevé (%s) :\n  %s" % (self.mode, "\n  ".join(self.erreurs_js)))

    def attendre_calme(self, page, quoi):
        """Attend que la page ne bouge plus (voir DÉTERMINISME dans la docstring)."""
        fin = time.monotonic() + DELAI_CALME_S
        precedent, stables = None, 0
        while True:
            etat = page.evaluate(SCRIPT_ETAT)
            if etat == precedent and etat[1] <= 0 and etat[2] <= 0 and not etat[3]:
                stables += 1
                if stables * SONDE_MS >= CALME_MS:
                    return
            else:
                stables = 0
            precedent = etat
            if time.monotonic() > fin:
                raise ErreurReleve("%s : l'écran ne se stabilise pas en %d s (mutations, requêtes, scripts, occupé : %r)"
                                   % (quoi, DELAI_CALME_S, etat))
            page.wait_for_timeout(SONDE_MS)

    # -- relevé d'une zone ----------------------------------------------------

    def noter(self, page, profil, nom, zones, vide_permis=False):
        self.dernier = "%s / %s" % (profil, nom)
        if self.filtre and not self.filtre.search(nom):
            return None
        brut = page.evaluate(SCRIPT_RELEVE, [zones, self.regles, self.elements_masques])
        if not brut["zones"] and not vide_permis:
            raise ErreurReleve("%s / %s / %s : aucune zone visible parmi %s" % (self.mode, profil, nom, zones))
        entree = {"profil": profil, "ecran": nom, "titre": brut["titre"],
                  "texte": compter(brut["texte"]), "attributs": compter(brut["attributs"])}
        self.ecrans.append(entree)
        self.journal("  %-11s %-55s %4d textes, %3d attributs" % (profil, nom, len(entree["texte"]), len(entree["attributs"])))
        return entree

    def capturer(self, page, nom):
        if not self.captures:
            return
        page.evaluate(SCRIPT_MASQUER_PAGE, [self.regles, self.elements_masques])
        page.evaluate("() => { document.activeElement && document.activeElement.blur && document.activeElement.blur(); window.scrollTo(0, 0); }")
        self.attendre_calme(page, nom)
        chemin = self.captures / ("%s-%s.png" % (self.mode, nom_de_fichier(nom)))
        chemin.write_bytes(page.screenshot(full_page=True, animations="disabled", caret="hide",
                                           mask=[page.locator("[data-photo-masque]")], mask_color="#808080"))
        self.journal("  capture    %s" % chemin.name)

    # -- navigation dans l'application ----------------------------------------

    def aller(self, page, ecran, profil):
        route = ecran["route"]() if callable(ecran["route"]) else ecran["route"]
        quoi = "%s / %s / %s (%s)" % (self.mode, profil, ecran["nom"], route)
        page.evaluate("route => { if (location.hash === route) App.naviguer(route); else location.hash = route; }", route)
        try:
            page.wait_for_function("id => typeof App !== 'undefined' && App.ecranCourant && App.ecranCourant.id === id",
                                   arg=ecran["id"], timeout=DELAI_MS)
        except Exception as erreur:
            courant = page.evaluate("() => (typeof App !== 'undefined' && App.ecranCourant && App.ecranCourant.id) || null")
            raise ErreurReleve("%s : écran « %s » attendu, « %s » affiché" % (quoi, ecran["id"], courant)) from erreur
        self.attendre_calme(page, quoi)
        self.verifier_erreurs()

    def onglets(self, page, profil, prefixe, racine="#contenu", deja=None):
        """Parcourt chaque onglet de chaque barre (onglets imbriqués compris) et relève son panneau."""
        deja = set() if deja is None else deja
        for barre in page.evaluate(SCRIPT_ONGLETS, racine):
            if barre["signature"] in deja:
                continue
            deja.add(barre["signature"])
            for identifiant in barre["ids"]:
                if identifiant == barre["choisi"]:
                    continue            # son panneau est déjà dans le relevé de l'écran (ou du panneau parent)
                nom = "%s › onglet %s" % (prefixe, identifiant)
                if not page.evaluate(SCRIPT_CLIC_ONGLET, [racine, barre["signature"], identifiant]):
                    raise ErreurReleve("%s / %s / %s : onglet introuvable" % (self.mode, profil, nom))
                self.attendre_calme(page, nom)
                self.noter(page, profil, nom, ["[data-photo-zone]"])
                self.onglets(page, profil, nom, "[data-photo-zone]", deja)
                page.evaluate("() => document.querySelectorAll('[data-photo-zone]').forEach((e) => e.removeAttribute('data-photo-zone'))")

    def cliquer(self, page, selecteur, quoi):
        element = page.query_selector(selecteur)
        if element is None:
            raise ErreurReleve("%s : bouton introuvable (%s)" % (quoi, selecteur))
        element.scroll_into_view_if_needed()
        element.click()

    def ecran(self, page, profil, ecran):
        if self.mode not in ecran["modes"] or profil not in ecran["profils"]:
            return
        nom = ecran["nom"]
        parties = [nom] + ["%s › onglet" % nom] + ["%s › fenêtre %s" % (nom, f) for f, _ in ecran["fenetres"]] + \
                  (["%s › erreurs" % nom] if ecran["erreurs"] else [])
        if self.filtre and not any(self.filtre.search(partie) for partie in parties):
            return
        self.aller(page, ecran, profil)
        self.noter(page, profil, nom, ZONES_ECRAN)
        if profil == "responsable" and ecran["capture"]:
            self.capturer(page, nom)
        if ecran["onglets"]:
            self.onglets(page, profil, nom)
        for nom_fenetre, selecteur in (ecran["fenetres"] if profil == "responsable" else ()):
            quoi = "%s › fenêtre %s" % (nom, nom_fenetre)
            self.aller(page, ecran, profil)
            self.cliquer(page, selecteur, "%s / %s / %s" % (self.mode, profil, quoi))
            page.wait_for_selector("dialog[open]", timeout=DELAI_MS)
            self.attendre_calme(page, quoi)
            self.noter(page, profil, quoi, ZONES_FENETRE)
            page.keyboard.press("Escape")
            page.wait_for_function("() => !document.querySelector('dialog[open]')", timeout=DELAI_MS)
            self.attendre_calme(page, quoi)
        if ecran["erreurs"]:
            quoi = "%s › erreurs" % nom
            self.aller(page, ecran, profil)
            self.cliquer(page, ecran["erreurs"], "%s / %s / %s" % (self.mode, profil, quoi))
            self.attendre_calme(page, quoi)
            if page.query_selector("dialog[open]"):
                raise ErreurReleve("%s / %s / %s : une fenêtre s'est ouverte à l'envoi du formulaire vide" % (self.mode, profil, quoi))
            self.noter(page, profil, quoi, ZONES_ECRAN)
        self.verifier_erreurs()

    def coque(self, page, profil):
        """La coque du profil : au bureau (menu latéral), puis au téléphone (en-tête, barre du bas)."""
        self.noter(page, profil, "coque (bureau)", ZONES_COQUE)
        page.set_viewport_size(dict(TELEPHONE))
        self.attendre_calme(page, "coque (téléphone)")
        self.noter(page, profil, "coque (téléphone)", ZONES_COQUE)
        page.set_viewport_size(dict(FENETRE))
        self.attendre_calme(page, "coque (bureau)")

    def profil(self, page, profil):
        for ecran in ECRANS:
            self.ecran(page, profil, ecran)
        self.aller(page, ECRANS[0], profil)
        self.coque(page, profil)
        self.verifier_erreurs()

    def attendre_plein(self, page, selecteur, quoi):
        page.wait_for_selector(selecteur, state="visible", timeout=DELAI_MS)
        self.attendre_calme(page, quoi)

    # -- démo ---------------------------------------------------------------------

    def demo(self):
        index = (RACINE / "index.html").resolve().as_uri()
        # Démarrage et choix du profil (poste neuf).
        contexte = self.nouveau_contexte()
        try:
            page = self.nouvelle_page(contexte, "démarrage")
            page.goto(index)
            self.attendre_plein(page, "#ecran-demarrage", "démarrage")
            self.noter(page, "aucun", "demarrage", ZONES_PLEIN)
            page.click("#btn-demo")
            self.attendre_plein(page, "#ecran-profil", "choix du profil")
            self.noter(page, "aucun", "profil", ZONES_PLEIN)
            page.click("#profil-demandeur")
            self.attendre_plein(page, "#profil-panneau-demandeur", "profil demandeur")
            self.noter(page, "aucun", "profil › demandeur", ZONES_PLEIN)
            page.click("#profil-panneau-demandeur [data-retour]")
            page.click("#profil-technicien")
            self.attendre_plein(page, "#profil-panneau-technicien", "profil technicien")
            self.noter(page, "aucun", "profil › technicien", ZONES_PLEIN)
            self.verifier_erreurs()
        finally:
            contexte.close()
        for profil in PROFILS:
            nom, technicien = IDENTITES[profil]
            contexte = self.nouveau_contexte()
            try:
                commun.preregler_profil(contexte, profil, nom, technicien, poste=POSTE)
                page = self.nouvelle_page(contexte, profil)
                page.goto(index)
                page.click("#btn-demo")
                commun.attendre_pret(page, DELAI_MS)
                self.attendre_calme(page, "démo " + profil)
                self.profil(page, profil)
            finally:
                contexte.close()

    # -- serveur ------------------------------------------------------------------

    def serveur_de_test(self, **options):
        """ServeurPrevo (tests/commun.py) à l'horloge figée ; ses dossiers temporaires sont masqués."""
        if self.temporaire is None:
            self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-photo-"))
        environnement = horloge_figee_du_serveur(self.temporaire)
        serveur = commun.ServeurPrevo(environnement=environnement, **options)
        # Les comptes de test (tests/commun.py comptes_json) portent l'heure réelle de leur création : un mot de passe
        # « changé » après l'heure figée refuserait toute session (verifier_session). Le temps du démarrage, leurs
        # dates sont ramenées à l'heure figée.
        origine, octets = commun.comptes_json, comptes_a_l_heure_figee()
        commun.comptes_json = lambda: octets
        try:
            serveur.demarrer()
        finally:
            commun.comptes_json = origine
        self.dossiers, self.ports = [serveur.dossier.parent], [serveur.port]
        self.mettre_a_jour_masques()
        return serveur

    def serveur(self):
        try:
            serveur = self.serveur_de_test(comptes=True)
            try:
                self.connexion(serveur)
                self.porte(serveur)
                for profil in PROFILS:
                    contexte = self.nouveau_contexte()
                    try:
                        serveur.poser_session(contexte, profil)
                        page = self.nouvelle_page(contexte, profil)
                        page.goto(serveur.url + "/#/accueil")
                        commun.attendre_pret(page, DELAI_MS)
                        self.attendre_calme(page, "serveur " + profil)
                        self.profil(page, profil)
                    finally:
                        contexte.close()
            finally:
                serveur.arreter()
            self.installation()
        finally:
            if self.temporaire is not None:
                commun._supprimer_dossier(self.temporaire)
                self.temporaire = None

    def connexion(self, serveur):
        contexte = self.nouveau_contexte()
        try:
            page = self.nouvelle_page(contexte, "connexion")
            page.goto(serveur.url + "/")
            self.attendre_plein(page, "#connexion-formulaire", "connexion")
            self.noter(page, "aucun", "connexion", ZONES_PLEIN)
            page.fill("#connexion-identifiant", commun.COMPTES_DE_TEST["demandeur"][0])
            page.fill("#connexion-mot-de-passe", MAUVAIS_MOT_DE_PASSE)
            page.click("#connexion-valider")
            self.attendre_plein(page, "#connexion-erreur", "connexion refusée")
            self.noter(page, "aucun", "connexion › refusée", ZONES_PLEIN)
            self.verifier_erreurs()
        finally:
            contexte.close()

    def porte(self, serveur):
        """La porte des téléphones (acces/porte.html) : servie ici sans port https, l'essai échoue et la page dit
        comment faire confiance au PC, selon le système reconnu."""
        for nom, appareil, attendu in (("porte › android", "Pixel 7", "#etapes-android"),
                                       ("porte › iphone", "iPhone 14", "#etapes-iphone"),
                                       ("porte › autre", None, "#choix-systeme")):
            contexte = self.nouveau_contexte(appareil)
            try:
                page = self.nouvelle_page(contexte, nom)
                page.goto(serveur.url + "/acces/porte.html")
                self.attendre_plein(page, attendu, nom)
                self.noter(page, "aucun", nom, ZONES_PAGE)
                self.verifier_erreurs()
            finally:
                contexte.close()

    def etape_installation(self, page, prefixe):
        """Relève l'étape de l'assistant affichée (nommée par son data-etape)."""
        self.attendre_plein(page, "#installation-contenu .installation-etape", prefixe)
        etapes = page.evaluate("""() => [...document.querySelectorAll('#installation-contenu .installation-etape')]
            .filter((section) => section.getClientRects().length > 0).map((section) => section.dataset.etape || '?')""")
        self.noter(page, "aucun", "%s › %s" % (prefixe, "+".join(etapes) if len(etapes) < 3 else "toutes"), ZONES_PLEIN)

    def installation(self):
        """Base vide et assistant d'installation : serveurs sur un dossier vide, sans configuration. L'assistant
        avance par l'API (POST /api/installation/<étape>, comme lui), jamais jusqu'à l'étape « démarrage » (qui
        écrit des scripts à côté de serveur.py)."""
        for situation, etapes in (("seul", (("portee", {"portee": "ce-pc"}), ("compte", {"prenom": "Claire", "nom": "Fontaine"}))),
                                  ("informaticien", ())):
            serveur = self.serveur_de_test(source=None)
            contexte = self.nouveau_contexte()
            try:
                page = self.nouvelle_page(contexte, "installation")
                if situation == "seul":
                    page.goto(serveur.url + "/")
                    self.attendre_plein(page, ".ecran-plein:not([hidden]):not(#ecran-chargement)", "dossier vide")
                    self.noter(page, "aucun", "dossier vide", ZONES_PLEIN)
                    page.goto(serveur.url + "/#/installation")
                    page.reload()
                    self.etape_installation(page, "installation")
                else:
                    page.goto(serveur.url + "/#/installation")
                    self.attendre_plein(page, "#installation-contenu .installation-etape", "installation")
                poster_installation(serveur.url, "situation", {"situation": situation})
                page.reload()
                self.etape_installation(page, "installation (%s)" % situation)
                for etape, corps in etapes:
                    poster_installation(serveur.url, etape, corps)
                    page.reload()
                    self.etape_installation(page, "installation (%s)" % situation)
                self.verifier_erreurs()
            finally:
                contexte.close()
                serveur.arreter()

    def relever(self):
        try:
            getattr(self, self.mode)()
        except ErreurReleve:
            raise
        except Exception as erreur:       # attente dépassée, page fermée… : dire où, sans la pile de Playwright
            premiere = (str(erreur).strip().splitlines() or [repr(erreur)])[0]
            raise ErreurReleve("%s, après « %s » : %s : %s" % (self.mode, self.dernier, type(erreur).__name__, premiere)) from erreur
        self.verifier_erreurs()
        return document(self.mode, self.ecrans)


def poster_installation(url, etape, corps):
    """POST /api/installation/<étape> du serveur de test (comme l'assistant : JSON, en-tête X-Prevo)."""
    requete = urllib.request.Request(url + "/api/installation/" + etape, data=json.dumps(corps).encode("utf-8"),
                                     method="POST", headers={"Content-Type": "application/json; charset=utf-8",
                                                             "X-Prevo": "1", "User-Agent": "photographie-prevo/1.0"})
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        if reponse.status != 200:
            raise ErreurReleve("installation, étape %s : réponse %s" % (etape, reponse.status))


def compter(entrees):
    """{entrée: nombre}, trié (l'ordre d'affichage n'est pas gardé : seul ce qui est affiché compte)."""
    nombres = {}
    for entree in entrees:
        nombres[entree] = nombres.get(entree, 0) + 1
    return dict(sorted(nombres.items()))


def nom_de_fichier(nom):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", nom.replace(" › ", "--")).strip("_")


def document(mode, ecrans):
    """Le relevé d'un mode tel qu'il est écrit (JSON)."""
    return {
        "outil": "outils/photographier_ecrans.py",
        "mode": mode,
        "conditions": {"horloge": heure_affichee(), "fuseau": FUSEAU, "langue": LANGUE,
                       "fenetre": "%dx%d" % (FENETRE["width"], FENETRE["height"])},
        "masques": list(REPERES),
        "ecrans": ecrans,
    }


# Caractères invisibles écrits par leur échappement dans le JSON (visibles à la relecture, comme dans les sources).
INVISIBLES = re.compile("[ ­ -‏    ⁠﻿]")


def en_json(releve):
    texte = json.dumps(releve, ensure_ascii=False, indent=0)
    return INVISIBLES.sub(lambda m: "\\u%04x" % ord(m.group(0)), texte) + "\n"


def lire_reference(mode, dossier=DOSSIER_REFERENCE):
    return json.loads((Path(dossier) / ("%s.json" % mode)).read_text(encoding="utf-8"))


def ecrire(releve, dossier):
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / ("%s.json" % releve["mode"])
    with open(chemin, "w", encoding="utf-8", newline="\n") as fichier:
        fichier.write(en_json(releve))
    return chemin


def relever(modes=MODES, captures=None, filtre=None, journal=None):
    """{mode: relevé} des modes demandés (un seul navigateur Chromium, fermé à la fin)."""
    if commun.sync_playwright is None:
        raise RuntimeError("Playwright pour Python n'est pas installé")
    if captures:
        Path(captures).mkdir(parents=True, exist_ok=True)
    resultats = {}
    with commun.sync_playwright() as playwright:
        navigateur = playwright.chromium.launch(headless=True)
        try:
            for mode in modes:
                if journal:
                    journal("Relevé du mode %s" % mode)
                resultats[mode] = Releveur(playwright, navigateur, mode, captures, filtre, journal).relever()
        finally:
            navigateur.close()
    return resultats


# ---------------------------------------------------------------------------
# Comparaison
# ---------------------------------------------------------------------------

def lisible(texte):
    """Texte cité dans un écart : caractères invisibles écrits par leur échappement."""
    return "« %s »" % INVISIBLES.sub(lambda m: "\\u%04x" % ord(m.group(0)), texte)


def _difference(sorte, avant, apres):
    """Lignes « - avant » (entrées disparues ou moins nombreuses), puis « + après » (apparues ou plus nombreuses)."""
    disparues, apparues = [], []
    for cle in sorted(set(avant) | set(apres)):
        n_avant, n_apres = avant.get(cle, 0), apres.get(cle, 0)
        if n_avant == n_apres:
            continue
        compte = "" if max(n_avant, n_apres) == 1 else " (%d fois avant, %d après)" % (n_avant, n_apres)
        if n_avant > n_apres:
            disparues.append("    - avant, %s : %s%s" % (sorte, lisible(cle), compte))
        else:
            apparues.append("    + après, %s : %s%s" % (sorte, lisible(cle), compte))
    return disparues + apparues


def comparer(reference, releve):
    """Liste des écarts lisibles entre deux relevés d'un même mode (vide si identiques)."""
    mode = releve.get("mode")
    ecarts = []
    index_avant = {(e["profil"], e["ecran"]): e for e in reference.get("ecrans", [])}
    index_apres = {(e["profil"], e["ecran"]): e for e in releve.get("ecrans", [])}
    for cle in list(index_avant) + [c for c in index_apres if c not in index_avant]:
        profil, nom = cle
        entete = "[%s] %s / %s" % (mode, profil, nom)
        if cle not in index_apres:
            ecarts.append("%s : écran absent du nouveau relevé" % entete)
            continue
        if cle not in index_avant:
            ecarts.append("%s : écran nouveau (absent de la référence)" % entete)
            continue
        avant, apres = index_avant[cle], index_apres[cle]
        lignes = []
        if avant["titre"] != apres["titre"]:
            lignes.append("    - avant, titre : %s" % lisible(avant["titre"]))
            lignes.append("    + après, titre : %s" % lisible(apres["titre"]))
        lignes += _difference("texte", avant["texte"], apres["texte"])
        lignes += _difference("attribut", avant["attributs"], apres["attributs"])
        if lignes:
            ecarts.append(entete + "\n" + "\n".join(lignes))
    ordre_avant = [c for c in index_avant if c in index_apres]
    ordre_apres = [c for c in index_apres if c in index_avant]
    if ordre_avant != ordre_apres:
        ecarts.append("[%s] ordre des écrans changé" % mode)
    for cle in ("conditions", "masques"):
        if reference.get(cle) != releve.get(cle):
            ecarts.append("[%s] %s différents : %r → %r" % (mode, cle, reference.get(cle), releve.get(cle)))
    return ecarts


# ---------------------------------------------------------------------------
# Captures d'image : comparaison au pixel (dans Chromium, par un canvas)
# ---------------------------------------------------------------------------

SCRIPT_PIXELS = r"""
async ([a, b]) => {
  const charger = async (donnees) => { const image = new Image(); image.src = 'data:image/png;base64,' + donnees; await image.decode(); return image; };
  const [ia, ib] = [await charger(a), await charger(b)];
  if (ia.naturalWidth !== ib.naturalWidth || ia.naturalHeight !== ib.naturalHeight) {
    return { taille: [ia.naturalWidth, ia.naturalHeight, ib.naturalWidth, ib.naturalHeight] };
  }
  const lire = (image) => { const toile = document.createElement('canvas'); toile.width = image.naturalWidth; toile.height = image.naturalHeight;
    const dessin = toile.getContext('2d'); dessin.drawImage(image, 0, 0); return dessin.getImageData(0, 0, toile.width, toile.height).data; };
  const [pa, pb] = [lire(ia), lire(ib)];
  const largeur = ia.naturalWidth;
  let nombre = 0, x0 = Infinity, y0 = Infinity, x1 = -1, y1 = -1;
  for (let i = 0; i < pa.length; i += 4) {
    if (pa[i] !== pb[i] || pa[i + 1] !== pb[i + 1] || pa[i + 2] !== pb[i + 2] || pa[i + 3] !== pb[i + 3]) {
      nombre += 1; const p = i / 4, x = p % largeur, y = Math.floor(p / largeur);
      if (x < x0) x0 = x; if (y < y0) y0 = y; if (x > x1) x1 = x; if (y > y1) y1 = y;
    }
  }
  return { nombre, rectangle: nombre ? [x0, y0, x1, y1] : null };
}
"""


def comparer_captures(dossier_nouvelles, dossier_references, journal=print):
    """Compare chaque capture de dossier_references à celle du même nom dans dossier_nouvelles ; rend les écarts."""
    nouvelles, references = Path(dossier_nouvelles), Path(dossier_references)
    noms = sorted({p.name for p in references.glob("*.png")} | {p.name for p in nouvelles.glob("*.png")})
    ecarts = []
    with commun.sync_playwright() as playwright:
        navigateur = playwright.chromium.launch(headless=True)
        try:
            page = navigateur.new_page()
            page.set_content("<!doctype html><title>comparaison</title>")
            for nom in noms:
                a, b = references / nom, nouvelles / nom
                if not a.is_file() or not b.is_file():
                    ecarts.append("%s : capture %s" % (nom, "nouvelle (sans référence)" if not a.is_file() else "absente"))
                    continue
                octets_a, octets_b = a.read_bytes(), b.read_bytes()
                if octets_a == octets_b:
                    journal("  identique  %s" % nom)
                    continue
                resultat = page.evaluate(SCRIPT_PIXELS, [base64.b64encode(octets_a).decode("ascii"),
                                                         base64.b64encode(octets_b).decode("ascii")])
                if resultat.get("taille"):
                    ecarts.append("%s : taille différente (%d × %d avant, %d × %d après)" % ((nom,) + tuple(resultat["taille"])))
                elif resultat["nombre"]:
                    ecarts.append("%s : %d pixels différents, dans le rectangle x %d à %d, y %d à %d"
                                  % ((nom, resultat["nombre"]) + tuple(resultat["rectangle"][i] for i in (0, 2, 1, 3))))
                else:
                    journal("  identique  %s (pixels identiques, fichiers différents)" % nom)
        finally:
            navigateur.close()
    return ecarts


# ---------------------------------------------------------------------------
# Programme
# ---------------------------------------------------------------------------

def main(arguments=None):
    analyseur = argparse.ArgumentParser(description="Photographie des écrans de Prévo (textes visibles, attributs, "
                                                    "captures) et comparaison à la référence.")
    analyseur.add_argument("--mode", choices=MODES, action="append", help="mode à relever (défaut : les deux)")
    analyseur.add_argument("--reference", action="store_true",
                           help="reprendre la référence des textes (chef de chantier seulement, jamais un test)")
    analyseur.add_argument("--sortie", help="dossier où écrire aussi les relevés (demo.json, serveur.json)")
    analyseur.add_argument("--captures", help="dossier où écrire les captures PNG (profil Responsable, bureau)")
    analyseur.add_argument("--comparer-captures", metavar="REFERENCES",
                           help="dossier des captures de référence, comparées aux nouvelles (avec --captures)")
    analyseur.add_argument("--ecrans", help="expression régulière : seulement ces écrans (mise au point)")
    options = analyseur.parse_args(arguments)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if options.reference and options.ecrans:
        analyseur.error("--reference relève tous les écrans : pas de --ecrans")
    if options.comparer_captures and not options.captures:
        options.captures = tempfile.mkdtemp(prefix="prevo-photo-captures-")
    modes = tuple(m for m in MODES if m in (options.mode or MODES))
    debut = time.monotonic()
    try:
        releves = relever(modes, options.captures, options.ecrans, journal=print)
    except ErreurReleve as erreur:
        print("ERREUR : %s" % erreur)
        return 2
    print("Relevé fait en %.0f s." % (time.monotonic() - debut))
    code = 0
    for mode, releve in releves.items():
        if options.sortie:
            print("Écrit %s" % ecrire(releve, options.sortie))
        if options.reference:
            print("Référence reprise : %s" % ecrire(releve, DOSSIER_REFERENCE))
            continue
        if not (DOSSIER_REFERENCE / ("%s.json" % mode)).is_file():
            print("Mode %s : aucune référence (%s)." % (mode, DOSSIER_REFERENCE / ("%s.json" % mode)))
            code = 1
            continue
        reference = lire_reference(mode)
        if options.ecrans:                  # seulement les écrans relevés : ceux dont le nom répond au filtre
            filtre = re.compile(options.ecrans)
            reference = dict(reference, ecrans=[e for e in reference["ecrans"] if filtre.search(e["ecran"])])
        ecarts = comparer(reference, releve)
        if ecarts:
            code = 1
            print("\n%d écart(s) dans le mode %s :\n%s" % (len(ecarts), mode, "\n".join(ecarts)))
        else:
            print("Mode %s : %d écrans identiques à la référence." % (mode, len(releve["ecrans"])))
    if options.comparer_captures:
        ecarts = comparer_captures(options.captures, options.comparer_captures)
        if ecarts:
            code = 1
            print("\nCaptures différentes :\n  " + "\n  ".join(ecarts))
        else:
            print("Captures identiques à la référence.")
    return code


if __name__ == "__main__":
    sys.exit(main())
