"""Chantier multilingue, Lot 3 — tous les écrans s'ouvrent en anglais, proprement (critères CS149 et CS150 ; T279).

Refait le parcours de la photographie des écrans (outils/photographier_ecrans.py, importé tel quel : mêmes écrans de
ECRANS, onglets, fenêtres, formulaires envoyés vides, coque, démarrage, choix du profil, connexion, porte, assistant
d'installation ; démo en file:// et serveur.py ; trois profils ; horloges figées), avec English choisi : la langue est
posée dans localStorage « prevo.langue » avant chaque chargement (Releveur, paramètre langue), comme le fait le
sélecteur de langue. Pour chaque écran relevé :
    - aucune erreur JavaScript (pageerror) ni message d'erreur dans la console ;
    - aucun avertissement du moteur pour une clé absente (js/i18n.js : « Prévo (traduction) : clé « … » … ») ;
    - document.documentElement.lang vaut « en » ;
    - aucun texte français resté à l'écran (texte visible, attributs lus, titre de l'onglet ; voir Examen) :
        * texte identique à une valeur française de js/i18n/fr.js (ou js/i18n/aide/fr.js) qui n'est la valeur
          anglaise d'aucune clé (« Total », « MTBF » s'écrivent pareil : ce n'est pas un écart) ;
        * texte qui épouse un gabarit français à variables ({n} ordres en retard…) et pas son gabarit anglais ;
        * mot français fréquent en mot entier (MOTS_FRANCAIS), mot que seul le français des dictionnaires emploie
          (« nouvelle », « derniers »), date ou montant au format français ;
      en excluant les DONNÉES de la démo (noms d'équipements, de personnes, textes saisis : elles restent dans la
      langue où elles ont été écrites, D146) : une entrée présente à l'identique dans le relevé français du même écran
      (la référence de la photographie, tests/fixtures/ecrans-reference/<mode>.json, que test_ecrans_identiques.py
      tient égale à l'écran français) est une donnée si elle figure dans les données de la démo, un oubli sinon
      (texte de fr.js, ou texte resté en dur dans un module) ; les morceaux de données d'un texte composé (cellules
      des CSV du jeu de démo et leurs phrases, comptes et poste de test, noms des langues) sont retirés avant de
      chercher les mots français ; les valeurs stockées des listes (D155) ne sont jamais des données : elles se
      traduisent à l'affichage ; le contenu du catalogue Prévo (2.2, T416 : blocs [data-catalogue], en français
      dans toutes les langues, CDC §3.2) est une donnée lui aussi, relevé écran par écran (TestDonneesCatalogue) ;
    - même liste d'écrans que le relevé français (aucun écran perdu en anglais) ;
    - formats en-GB : la date en lettres de l'accueil (« Monday 19 October 2026 ») et un montant des indicateurs
      (« €1,760.00 ») au format britannique.
Le rapport donne, pour chaque problème : l'écran, la sorte, le détail, et les modes et profils où il se voit ; il est
aussi écrit en entier dans le dossier temporaire (prevo-ecrans-anglais/rapport-<mode>.txt, avec le relevé anglais).
Un problème qui relève d'un autre lot ou d'une décision, ou une réponse refusée voulue par le serveur (401, 403, 404 :
les mêmes en français, déjà permises par les tests du lot 7 et de l'installation), est rangé dans EXCEPTIONS (une
ligne, sa raison) : il est cité dans la sortie du test sans le faire échouer.

Repli (TestRepli) : une clé retirée de l'anglais servi à la page (js/i18n/en.js intercepté, sans sa ligne) donne le
texte français à l'écran et UN avertissement console pour cette clé, même quand l'écran l'emploie plusieurs fois.

Lancer depuis la racine du projet (au travers du verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_ecrans_anglais.py" -v
Durée : environ cinq minutes (deux modes, Chromium headless).
"""
import collections
import csv
import html
import importlib.util
import json
import re
import sys
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path

import commun
from atelier import tables_refusees_au_demandeur
from commun import (COMPTES_DE_TEST, DOSSIER_DEMO, RACINE, CasNavigateur, ServeurPrevo, attendre_pret,
                    preregler_profil, sync_playwright)

_specification = importlib.util.spec_from_file_location("photographier_ecrans", RACINE / "outils" / "photographier_ecrans.py")
photo = importlib.util.module_from_spec(_specification)
sys.modules.setdefault("photographier_ecrans", photo)
_specification.loader.exec_module(photo)

if str(RACINE / "outils") not in sys.path:
    sys.path.insert(0, str(RACINE / "outils"))
import textes_langues  # noqa: E402  (lecture des dictionnaires, celle de outils/controler_textes.py)
from jslex import decoder  # noqa: E402

LANGUE = "en"
# Avertissement du moteur pour une clé absente (js/i18n.js, avertir) : début commun aux deux raisons.
AVERTISSEMENT_CLE = "Prévo (traduction) : clé « "
MOTS_FRANCAIS = ("le", "la", "les", "des", "du", "une", "est", "pas", "vous", "aucun", "pour", "avec")
MOIS_FRANCAIS = "janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre"
JOURS_FRANCAIS = "lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche"
RE_MOTS_FRANCAIS = re.compile(r"(?<![\w'’-])(%s)(?![\w'’-])" % "|".join(MOTS_FRANCAIS), re.IGNORECASE)
FORMATS_FRANCAIS = [
    (re.compile(r"\d,\d+[\u00a0\u202f ]?€"), "montant au format français"),
    (re.compile(r"\b\d{1,2}(?:er)? (?:%s)\b" % MOIS_FRANCAIS, re.IGNORECASE), "date au format français"),
    (re.compile(r"\b(?:%s)\b" % JOURS_FRANCAIS, re.IGNORECASE), "jour en français"),
    (re.compile(r"\d[\u00a0\u202f]\d{3}\b"), "nombre au format français (milliers séparés par une espace)"),
]
MOIS_ANGLAIS = "January|February|March|April|May|June|July|August|September|October|November|December"
# Formats en-GB attendus (Intl, locale en-GB) : jour avant le mois en lettres ; euro devant, virgule des milliers.
DATE_EN_GB = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),? \d{1,2} (?:%s) \d{4}\b"
                        % MOIS_ANGLAIS)
MONTANT_EN_GB = re.compile(r"€\d{1,3}(?:,\d{3})+\.\d{2}\b")
FORMATS_EN_GB = [("responsable", "accueil", DATE_EN_GB, "date en lettres en-GB (« Monday 19 October 2026 »)"),
                 ("responsable", "indicateurs", MONTANT_EN_GB, "montant en-GB (« €1,760.00 »)")]

# Problèmes connus laissés à un autre lot ou à une décision : (écran, sorte, détail : trois expressions régulières ;
# raison). Une ligne par exception ; chacune est citée dans la sortie du test.
EXCEPTIONS = [
    (r"connexion", r"^erreur console$", r"status of 401 .*\(/api/(?:versions|connexion)\)",
     "sans session, le serveur refuse la sonde /api/versions et le mauvais mot de passe (401) : voulu, pareil en français"),
    (r".", r"^erreur console$", r"status of 403 .*\(/api/csv/(?:%s)\)" % "|".join(tables_refusees_au_demandeur()),
     "profil Demandeur : les tables qui ne sont pas les siennes sont refusées (403, lot 7) : voulu, pareil en français"),
    (r"installation", r"^erreur console$", r"status of 404 .*\(/api/csv/\w+\)",
     "dossier vide de l'assistant d'installation : les CSV manquent (404, table vide) : voulu, pareil en français"),
    (r"porte › ", r"^erreur console$", r"status of 404 .*\(/acces/ca\.crt\)",
     "porte servie sans autorité locale : /acces/ca.crt répond 404 avec l'explication, voulu (pareil en français)"),
]

Probleme = collections.namedtuple("Probleme", "mode profil ecran sorte detail")


# ---------------------------------------------------------------------------
# Dictionnaires et données de la démo (sans navigateur)
# ---------------------------------------------------------------------------

def _formes(valeur):
    """Textes affichables d'une entrée de dictionnaire (brute, entre apostrophes ; ou pluriel) : échappements
    décodés, balisage retiré, entités HTML décodées, une ligne par morceau, bords nettoyés."""
    brutes = list(valeur.values()) if isinstance(valeur, dict) else [valeur]
    formes = []
    for brute in brutes:
        texte = html.unescape(re.sub(r"<[^>]*>", "", decoder(brute)))
        for ligne in texte.split("\n"):
            ligne = ligne.strip(" \t\r")
            if ligne:
                formes.append(ligne)
    return formes


def _gabarit(forme):
    """Expression régulière d'une forme à variables (« {n} ordres » → « (.+?) ordres »)."""
    morceaux = re.split(r"\{\w+\}", forme)
    return re.compile("(?:.+?)".join(re.escape(m) for m in morceaux), re.DOTALL)


RE_MOT = re.compile(r"[^\W\d_]{3,}")
# Noms anglais des mois et des jours écrits par Intl (dates en-GB), absents de en.js : des mots anglais.
NOMS_INTL_ANGLAIS = set((MOIS_ANGLAIS + "|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Monday|Tuesday|Wednesday|"
                         "Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun").lower().split("|"))


def _mots(texte):
    return set(RE_MOT.findall(texte.lower()))


class Textes:
    """Ce qui distingue un texte français oublié d'un texte traduit, lu dans les dictionnaires (fr.js et en.js, aide
    longue comprise).

    francais : {texte français sans variable: clé}, seulement ceux qui ne sont la valeur anglaise d'aucune clé ;
    gabarits : {mot: [(clé, expression française, [expressions anglaises de la clé])]}, rangés par le plus long mot
    de leur partie fixe (un texte n'est essayé que contre les gabarits d'un de ses mots) ;
    vocabulaire : mots (3 lettres et plus) des textes français qu'aucun texte anglais n'emploie (« nouvelle »,
    « derniers ») ;
    valeurs : valeurs stockées des listes (D155, clés valeurs.<table>.<champ>.<valeur>) et leur texte français :
    affichées, elles se traduisent ; ce ne sont jamais des données gardées en français."""

    def __init__(self, racine=RACINE):
        fr = textes_langues.Langue("fr", racine, textes_langues.fichiers_de("fr")).entrees
        en = textes_langues.Langue(LANGUE, racine, textes_langues.fichiers_de(LANGUE)).entrees
        formes_en = {cle: _formes(valeur) for cle, (_, valeur, _) in en.items()}
        anglais = {forme for formes in formes_en.values() for forme in formes}
        mots_anglais = set().union(NOMS_INTL_ANGLAIS, *(_mots(re.sub(r"\{\w+\}", " ", forme)) for forme in anglais))
        self.francais = {}
        self.gabarits = collections.defaultdict(list)
        self.vocabulaire = set()
        self.valeurs = set()
        for cle, (_, valeur, _) in sorted(fr.items()):
            formes = _formes(valeur)
            if cle.startswith("valeurs.") and cle.count(".") >= 3:
                self.valeurs.add(cle.split(".", 3)[3])
                self.valeurs.update(formes)
            for forme in formes:
                self.vocabulaire.update(_mots(re.sub(r"\{\w+\}", " ", forme)) - mots_anglais)
                if forme in anglais:
                    continue
                if "{" not in forme:
                    self.francais.setdefault(forme, cle)
                    continue
                mots = RE_MOT.findall(re.sub(r"\{\w+\}", " ", forme).lower())
                if sum(len(mot) for mot in mots) < 4:
                    continue                 # « {n} h », « {a} · {b} » : rien de français à reconnaître
                anglaises = [_gabarit(f) for f in formes_en.get(cle, ()) if "{" in f]
                self.gabarits[max(mots, key=len)].append((cle, _gabarit(forme), anglaises))

    def cle_francaise(self, texte):
        """(clé de fr.js dont le texte français est `texte`, mot fixe du gabarit ou None), ou (None, None)."""
        if texte in self.francais:
            return self.francais[texte], None
        for mot in _mots(texte):
            for cle, francais, anglaises in self.gabarits.get(mot, ()):
                if francais.fullmatch(texte) and not any(anglaise.fullmatch(texte) for anglaise in anglaises):
                    return cle + " (gabarit)", mot
        return None, None


RE_LIEN_WIKI = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")         # [[Cartouche filtre]] → Cartouche filtre
RE_CITATION = re.compile(r"\s*\[(?:OT|DI)-[^\]]*\]")                  # [OT-2026-0012] : rendu en appel de note
RE_MARQUE_LIGNE = re.compile(r"^\s*(?:#+|[-*>]|\d+[.)])\s+")
RE_PHRASE = re.compile(r"(?<=[.;!?])\s+|\s+:\s+")


def _ajouter_segment(segments, texte):
    texte = texte.strip().lstrip("'").strip()
    for forme in (texte, texte.rstrip(".;:!? ")):
        if len(forme) >= 3 and not re.fullmatch(r"[\d\W_]+", forme):
            segments.add(forme)


def _ajouter_donnee(segments, valeur):
    """Une valeur de données et les morceaux sous lesquels l'écran peut la montrer : chaque ligne, sans sa marque
    Markdown, liens du wiki ouverts, appels d'OT retirés, puis découpée en phrases (et aux « : ») ; une cellule JSON
    (propositions du wiki, réglages) est lue valeur par valeur."""
    if isinstance(valeur, dict):
        valeur = list(valeur.values())
    if isinstance(valeur, list):
        for element in valeur:
            _ajouter_donnee(segments, element)
        return
    if not isinstance(valeur, str):
        return
    if valeur.strip()[:1] in ("[", "{"):
        try:
            _ajouter_donnee(segments, json.loads(valeur))
            return
        except ValueError:
            pass
    _ajouter_segment(segments, valeur)
    for ligne in valeur.splitlines():
        propre = RE_LIEN_WIKI.sub(r"\1", RE_MARQUE_LIGNE.sub("", ligne))
        propre = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", propre).replace("**", "").replace("`", "")
        for morceau in [ligne, propre] + RE_CITATION.split(propre):
            _ajouter_segment(segments, morceau)
            for phrase in RE_PHRASE.split(morceau):
                _ajouter_segment(segments, phrase)


def segments_de_donnees(dossier=DOSSIER_DEMO):
    """Morceaux de DONNÉES de la démo (D146) : cellules des CSV et leurs morceaux (_ajouter_donnee), comptes de test,
    poste et identités de la photographie, compte créé par l'assistant d'installation ; plus les noms des langues."""
    segments = set()
    for chemin in sorted(Path(dossier).glob("*.csv")):
        with open(chemin, encoding="utf-8-sig", newline="") as fichier:
            lignes = csv.reader(fichier, delimiter=";")
            next(lignes, None)
            for ligne in lignes:
                for cellule in ligne:
                    _ajouter_donnee(segments, cellule)
    for identifiant, prenom, nom, _, _ in COMPTES_DE_TEST.values():
        for texte in (identifiant, prenom, nom, (prenom + " " + nom).strip()):
            _ajouter_segment(segments, texte)
    for nom, _ in photo.IDENTITES.values():
        _ajouter_segment(segments, nom)
    _ajouter_segment(segments, photo.POSTE)
    _ajouter_segment(segments, commun.preregler_profil.__defaults__[-1])      # poste des comptes de test (« Poste test »)
    _ajouter_segment(segments, "Claire Fontaine")            # compte créé par l'assistant (photo.installation)
    # Noms des langues, chacun dans sa langue (js/i18n/langues.js ; D148 : jamais traduits).
    langues = (RACINE / "js" / "i18n" / "langues.js").read_text(encoding="utf-8")
    for nom in re.findall(r"\bnom:\s*'([^']+)'", langues):
        _ajouter_segment(segments, nom)
    return segments


# ---------------------------------------------------------------------------
# Examen d'un relevé anglais (sans navigateur)
# ---------------------------------------------------------------------------

class Examen:
    """Examine un relevé anglais, écran par écran, au regard du relevé français du même mode.

    Pour chaque texte (texte visible, attribut lu, titre de l'onglet) :
      - texte identique à l'écran français ET donnée de la démo : donnée, rien à dire (D146) ;
      - texte français de fr.js (exact, ou gabarit dont la partie fixe n'est pas dans une donnée) : « texte
        français » ;
      - sinon, une fois les morceaux de données retirés : mots français fréquents (MOTS_FRANCAIS), mots que seul le
        français emploie (Textes.vocabulaire), date ou montant au format français."""

    def __init__(self, textes, segments):
        self.textes = textes
        # Une valeur de liste (statut « arrêt »…) s'affiche traduite : elle n'est pas une donnée ici.
        # Comparaison sans la casse : la feuille de style met certains textes en capitales (text-transform), et
        # innerText les rend ainsi.
        self.donnees = {s.lower() for s in segments if s not in textes.valeurs}
        self.par_mot = collections.defaultdict(list)
        for segment in self.donnees:
            premier = re.search(r"\w+", segment)
            if premier:
                self.par_mot[premier.group(0)].append(segment)
        self.memoire = {}

    def sans_donnees(self, texte):
        """`texte` (en minuscules) sans ses morceaux de données, les plus longs d'abord ; un texte abrégé (« … ») qui
        commence une donnée est tout entier une donnée. Les noms techniques (« 2026-10-19_093000_avant-mise-a-jour »,
        adresses) sont retirés aussi."""
        texte = texte.lower()
        candidats = set()
        for mot in set(re.findall(r"\w+", texte)):
            candidats.update(self.par_mot.get(mot, ()))
        if texte.endswith("…") and any(segment.startswith(texte[:-1].rstrip()) for segment in candidats):
            return ""
        for segment in sorted(candidats, key=len, reverse=True):
            if segment in texte:
                texte = texte.replace(segment, " ")
        return re.sub(r"\S*_\S*|\S*://\S*", " ", texte)

    def francais(self, texte, identique):
        """Problèmes [(sorte, détail)] d'un texte relevé en anglais ; identique : vrai s'il figure tel quel dans le
        relevé français du même écran."""
        cle_memoire = (texte, identique)
        if cle_memoire not in self.memoire:
            self.memoire[cle_memoire] = self._francais(texte, identique)
        return self.memoire[cle_memoire]

    def _francais(self, texte, identique):
        if identique and texte.lower() in self.donnees:
            return []
        cle, mot_fixe = self.textes.cle_francaise(texte)
        suspects = (cle or RE_MOTS_FRANCAIS.search(texte) or _mots(texte) & self.textes.vocabulaire
                    or any(motif.search(texte) for motif, _ in FORMATS_FRANCAIS))
        reste = self.sans_donnees(texte) if suspects else texte
        if cle and (mot_fixe is None or mot_fixe in reste):
            return [("texte français", "%s (clé %s)" % (photo.lisible(texte), cle))]
        origine = "identique à l'écran français, ni clé de fr.js ni donnée" if identique else "texte traduit"
        problemes = []
        mots = {m.lower() for m in RE_MOTS_FRANCAIS.findall(reste)} | (_mots(reste) & self.textes.vocabulaire)
        if mots:
            problemes.append(("mot français", "%s : %s (%s)" % (photo.lisible(texte), ", ".join(sorted(mots)), origine)))
        for motif, nom in FORMATS_FRANCAIS:
            if motif.search(reste):
                problemes.append((nom, "%s (%s)" % (photo.lisible(texte), origine)))
        return problemes

    def releve(self, anglais, francais):
        """Problèmes d'un relevé anglais comparé au relevé français du même mode."""
        mode = anglais["mode"]
        index_fr = {(e["profil"], e["ecran"]): e for e in francais["ecrans"]}
        index_en = {(e["profil"], e["ecran"]): e for e in anglais["ecrans"]}
        problemes = []
        for profil, ecran in index_fr:
            if (profil, ecran) not in index_en:
                problemes.append(Probleme(mode, profil, ecran, "écran absent en anglais", "relevé en français, pas en anglais"))
        for (profil, ecran), entree in index_en.items():
            fr = index_fr.get((profil, ecran))
            if fr is None:
                problemes.append(Probleme(mode, profil, ecran, "écran en plus en anglais", "absent du relevé français"))
                fr = {"titre": "", "texte": {}, "attributs": {}}
            textes_fr = set(fr["texte"]) | {a.split("=", 1)[1] for a in fr["attributs"]} | {fr["titre"]}
            vus = [("texte", t) for t in entree["texte"]] + [("titre", entree["titre"])]
            vus += [("attribut " + a.split("=", 1)[0], a.split("=", 1)[1]) for a in entree["attributs"]]
            for ou, texte in vus:
                if not texte:
                    continue
                for sorte, detail in self.francais(texte, texte in textes_fr):
                    problemes.append(Probleme(mode, profil, ecran, sorte, detail if ou == "texte" else ou + ", " + detail))
        return problemes


def formats_en_gb(releve):
    """Problèmes de format : FORMATS_EN_GB absents des écrans désignés (onglets compris)."""
    problemes = []
    for profil, ecran, motif, quoi in FORMATS_EN_GB:
        textes = [t for e in releve["ecrans"] if e["profil"] == profil
                  and (e["ecran"] == ecran or e["ecran"].startswith(ecran + " › ")) for t in e["texte"]]
        if not any(motif.search(t) for t in textes):
            problemes.append(Probleme(releve["mode"], profil, ecran, "format en-GB absent", quoi))
    return problemes


def exception_de(probleme):
    for ecran, sorte, detail, raison in EXCEPTIONS:
        if re.search(ecran, probleme.ecran) and re.search(sorte, probleme.sorte) and re.search(detail, probleme.detail):
            return raison
    return None


def rapport(problemes):
    """Lignes lisibles : un problème par écran, sorte et détail, avec les modes et profils où il se voit."""
    groupes = collections.OrderedDict()
    for p in problemes:
        groupes.setdefault((p.ecran, p.sorte, p.detail), collections.OrderedDict()).setdefault(p.mode, []).append(p.profil)
    lignes = []
    for (ecran, sorte, detail), modes in groupes.items():
        ou = " ; ".join("%s : %s" % (mode, ", ".join(dict.fromkeys(profils))) for mode, profils in modes.items())
        lignes.append("%s — %s : %s  [%s]" % (ecran, sorte, detail, ou))
    return lignes


# ---------------------------------------------------------------------------
# Relevé en anglais : le parcours de la photographie, avec la console écoutée
# ---------------------------------------------------------------------------

# Contenu du catalogue Prévo affiché (2.2, T416 ; CDC §3.2 : textes juridiques français, en français dans toutes les
# langues) : les blocs [data-catalogue] (lang="fr") sont des DONNÉES. Texte d'un bloc ; pour une option de liste, où
# le texte du catalogue voisine avec un texte traduit (« C01 · <nature> — 12 months »), la valeur de data-catalogue
# (la part du catalogue) ; pour un groupe d'options, son libellé (la famille).
SCRIPT_DONNEES_CATALOGUE = r"""
() => {
  const textes = [];
  for (const element of document.querySelectorAll('[data-catalogue]')) {
    const valeur = element.getAttribute('data-catalogue')
      || (element.localName === 'optgroup' ? element.label : (element.innerText || element.textContent || ''));
    textes.push(...String(valeur).split(/[\n\t]/));
  }
  return textes;
}
"""


def donnees_du_catalogue(page):
    """Morceaux de données des blocs [data-catalogue] de la page (SCRIPT_DONNEES_CATALOGUE), comme segments_de_donnees."""
    segments = set()
    for texte in page.evaluate(SCRIPT_DONNEES_CATALOGUE):
        _ajouter_segment(segments, texte)
    return segments


class ReleveurAnglais(photo.Releveur):
    """Releveur de la photographie, English choisi ; note, écran par écran, les erreurs JavaScript (sans arrêter le
    relevé), les messages d'erreur et les avertissements de clé absente de la console, et l'attribut lang ; garde les
    textes des blocs du catalogue (donnees_catalogue), rangés parmi les données."""

    def __init__(self, playwright, navigateur, mode):
        super().__init__(playwright, navigateur, mode, langue=LANGUE)
        self.problemes = []
        self.courant = ("aucun", "début du relevé")
        self.donnees_catalogue = set()

    def signaler(self, sorte, detail):
        profil, ecran = self.courant
        self.problemes.append(Probleme(self.mode, profil, ecran, sorte, detail))

    def nouvelle_page(self, contexte, nom):
        self.courant = (nom if nom in photo.PROFILS else "aucun", "ouverture (%s)" % nom)
        page = super().nouvelle_page(contexte, nom)
        page.on("console", self.console)
        return page

    def console(self, message):
        if message.type == "error":
            adresse = (message.location or {}).get("url") or ""
            chemin = urllib.parse.urlsplit(adresse).path if adresse.startswith("http") else Path(adresse).name
            self.signaler("erreur console", "%s (%s)" % (message.text, chemin or "?"))
        elif message.type == "warning" and AVERTISSEMENT_CLE in message.text:
            self.signaler("clé absente", message.text)

    def verifier_erreurs(self):
        for erreur in self.erreurs_js:
            self.signaler("erreur JavaScript", erreur)
        del self.erreurs_js[:]

    def aller(self, page, ecran, profil):
        self.courant = (profil, ecran["nom"])
        super().aller(page, ecran, profil)

    def noter(self, page, profil, nom, zones, vide_permis=False):
        self.courant = (profil, nom)
        entree = super().noter(page, profil, nom, zones, vide_permis)
        if entree is not None:
            lang = page.evaluate("document.documentElement.lang")
            if lang != LANGUE:
                self.signaler("lang", "<html lang=%r> (attendu %r)" % (lang, LANGUE))
            self.donnees_catalogue |= donnees_du_catalogue(page)
        return entree


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

LIGNES_MONTREES = 120


class TestEcransAnglais(unittest.TestCase):
    """Un test par mode : tout le parcours de la photographie en anglais, examiné écran par écran."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if sync_playwright is None:
            raise unittest.SkipTest("Playwright pour Python n'est pas installé")
        cls.textes = Textes()
        cls.segments = segments_de_donnees()
        cls._playwright = sync_playwright().start()
        cls.addClassCleanup(cls._playwright.stop)
        cls.navigateur = cls._playwright.chromium.launch(headless=True)
        cls.addClassCleanup(cls.navigateur.close)

    def verifier_mode(self, mode):
        francais = photo.lire_reference(mode)
        debut = time.monotonic()
        releveur = ReleveurAnglais(self._playwright, self.navigateur, mode)
        try:
            anglais = releveur.relever()
        except photo.ErreurReleve as erreur:
            anglais = photo.document(mode, releveur.ecrans)
            releveur.problemes.append(Probleme(mode, "?", releveur.dernier, "relevé interrompu", str(erreur)))
        duree = time.monotonic() - debut
        # Données de la démo, plus le contenu du catalogue vu pendant le relevé (blocs [data-catalogue]).
        examen = Examen(self.textes, self.segments | releveur.donnees_catalogue)
        problemes = releveur.problemes + examen.releve(anglais, francais) + formats_en_gb(anglais)
        retenus = [p for p in problemes if exception_de(p) is None]
        excuses = [p for p in problemes if exception_de(p) is not None]
        dossier = Path(tempfile.gettempdir()) / "prevo-ecrans-anglais"
        photo.ecrire(anglais, dossier)
        lignes = rapport(retenus)
        par_raison = collections.OrderedDict()
        for probleme in excuses:
            par_raison.setdefault(exception_de(probleme), []).append(probleme)
        resume = ["%d problème(s), écrans %s ← %s" % (len(liste), ", ".join(dict.fromkeys(p.ecran for p in liste)), raison)
                  for raison, liste in par_raison.items()]
        (dossier / ("rapport-%s.txt" % mode)).write_text(
            "\n".join(lignes + ["", "Exceptions (EXCEPTIONS) :"] + rapport(excuses)) + "\n", encoding="utf-8")
        if resume:
            sys.stderr.write("\n  [%s] exceptions (EXCEPTIONS) :\n    %s" % (mode, "\n    ".join(resume)))
        if retenus:
            montrees = lignes[:LIGNES_MONTREES]
            if len(lignes) > LIGNES_MONTREES:
                montrees.append("… et %d autres" % (len(lignes) - LIGNES_MONTREES))
            self.fail("%d problème(s) en anglais, mode %s (%d écrans relevés en %.0f s) :\n  %s\n\nRapport complet : %s"
                      % (len(lignes), mode, len(anglais["ecrans"]), duree, "\n  ".join(montrees),
                         dossier / ("rapport-%s.txt" % mode)))
        sys.stderr.write("\n  [%s] %d écrans ouverts en anglais, sans problème, en %.0f s " % (mode, len(anglais["ecrans"]), duree))

    def test_demo(self):
        self.verifier_mode("demo")

    def test_serveur(self):
        self.verifier_mode("serveur")


class TestRepli(CasNavigateur):
    """Une clé retirée de l'anglais servi à la page : texte français affiché, un seul avertissement pour cette clé."""

    CLE = "accueil.entete.bonjour"
    LIGNE = "  'accueil.entete.bonjour': 'Hello',\n"

    def test_cle_absente_en_anglais_texte_francais_et_un_avertissement(self):
        source = (RACINE / "js" / "i18n" / "en.js").read_text(encoding="utf-8")
        self.assertEqual(source.count(self.LIGNE), 1, "ligne de la clé introuvable dans js/i18n/en.js")
        incomplet = source.replace(self.LIGNE, "")
        avertissements = []
        self.page.on("console", lambda message: avertissements.append(message.text)
                     if message.type == "warning" else None)
        self.contexte.add_init_script("try { localStorage.setItem('prevo.langue', 'en'); } catch (erreur) {}")
        preregler_profil(self.contexte, "responsable", "Nicolas Briand")
        servis = []

        def servir(route):
            servis.append(route.request.url)
            route.fulfill(status=200, content_type="text/javascript; charset=utf-8", body=incomplet)

        self.page.route("**/js/i18n/en.js", servir)
        lire = """(cle) => ({ lang: document.documentElement.lang, langue: I18n.langue,
          titre: document.querySelector('.bento-salut h1').textContent.trim(), francais: I18n.reference(cle),
          autre: I18n.t('accueil.moment_atelier.matin_atelier') })"""
        with ServeurPrevo() as serveur:
            self.page.goto(serveur.url + "/#/accueil")
            attendre_pret(self.page)
            self.page.wait_for_function("App.ecranCourant && App.ecranCourant.id === 'accueil'")
            premier = self.page.evaluate(lire, self.CLE)
            # L'écran est rendu une seconde fois (autre écran, puis retour) : toujours un seul avertissement.
            self.page.evaluate("location.hash = '#/di'")
            self.page.wait_for_function("App.ecranCourant && App.ecranCourant.id === 'liste-di'")
            self.page.evaluate("location.hash = '#/accueil'")
            self.page.wait_for_function("App.ecranCourant && App.ecranCourant.id === 'accueil' "
                                        "&& document.querySelector('.bento-salut h1')")
            second = self.page.evaluate(lire, self.CLE)
        self.assertEqual(len(servis), 1, servis)
        for etat in (premier, second):
            self.assertEqual(etat, {"lang": "en", "langue": "en", "titre": "Bonjour", "francais": "Bonjour",
                                    "autre": "This morning in the workshop"})
        attendu = "Prévo (traduction) : clé « %s » absente en « en » : texte français affiché." % self.CLE
        self.assertEqual([a for a in avertissements if AVERTISSEMENT_CLE in a], [attendu])


class TestDonneesCatalogue(CasNavigateur):
    """Blocs du catalogue Prévo (T416) : leur texte est une donnée, pas un oubli de traduction ; le texte traduit qui
    les entoure reste examiné."""

    PAGE = """<!doctype html><html lang="en"><body><form>
      <select><option value="">Free entry (outside the catalogue)</option>
        <optgroup label="Levage" data-catalogue><option value="C01" data-catalogue="VGP pont roulant, palan">C01 · VGP
          pont roulant, palan — 12 months</option></optgroup></select>
      <dl><dt>Reference text</dt><dd lang="fr" data-catalogue>Arrêté du 1er mars 2004, art. 23</dd>
        <dt>Who inspects</dt><dd lang="fr" data-catalogue>Personnes qualifiées de l'établissement</dd></dl>
      <div lang="fr" data-catalogue>à confirmer avec votre organisme de contrôle</div></form></body></html>"""

    def test_blocs_du_catalogue_parmi_les_donnees(self):
        self.page.set_content(self.PAGE)
        segments = donnees_du_catalogue(self.page)
        for attendu in ("Levage", "VGP pont roulant, palan", "Arrêté du 1er mars 2004, art. 23",
                        "Personnes qualifiées de l'établissement", "à confirmer avec votre organisme de contrôle"):
            with self.subTest(segment=attendu):
                self.assertIn(attendu, segments)
        self.assertNotIn("C01 · VGP pont roulant, palan — 12 months", segments, "l'option entière n'est pas une donnée")
        textes = Textes()
        examen = Examen(textes, segments)
        vus = ["C01 · VGP pont roulant, palan — 12 months", "Arrêté du 1er mars 2004, art. 23",
               "Personnes qualifiées de l'établissement", "à confirmer avec votre organisme de contrôle"]
        releve = {"mode": "demo", "ecrans": [{"profil": "responsable", "ecran": "controles-nouveau", "titre": "",
                                              "texte": photo.compter(vus), "attributs": {}}]}
        vide = {"mode": "demo", "ecrans": [{"profil": "responsable", "ecran": "controles-nouveau", "titre": "",
                                            "texte": {}, "attributs": {}}]}
        self.assertEqual(examen.releve(releve, vide), [])
        # Sans les blocs du catalogue, ces textes seraient signalés ; un suffixe resté en français l'est toujours.
        self.assertTrue(Examen(textes, set()).releve(releve, vide))
        releve["ecrans"][0]["texte"] = photo.compter(["C01 · VGP pont roulant, palan — 12 mois"])
        problemes = examen.releve(releve, vide)
        self.assertEqual(len(problemes), 1, problemes)
        self.assertIn("mois", problemes[0].detail)


class TestExamen(unittest.TestCase):
    """L'examen lui-même (sans navigateur), sur de petits relevés."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.examen = Examen(Textes(), {"Compresseur à vis 30 kW", "Fuite d'huile sous la presse PR-01"})

    def releve(self, textes, attributs=(), titre="Home — Prévo"):
        return {"mode": "demo", "ecrans": [{"profil": "responsable", "ecran": "accueil", "titre": titre,
                                            "texte": photo.compter(textes), "attributs": photo.compter(attributs)}]}

    def sortes(self, anglais, francais):
        return sorted((p.sorte, p.detail) for p in self.examen.releve(self.releve(*anglais), self.releve(*francais)))

    def test_texte_de_fr_js_reste_en_francais(self):
        problemes = self.sortes((["Bonjour", "Hello"],), (["Bonjour"],))
        self.assertEqual(problemes, [("texte français", "« Bonjour » (clé accueil.entete.bonjour)")])

    def test_donnees_gardees_en_francais(self):
        donnees = ["Compresseur à vis 30 kW", "Fuite d'huile sous la presse PR-01"]
        self.assertEqual(self.sortes((donnees + ["Hello"],), (donnees + ["Bonjour"],)), [])

    def test_donnee_dans_un_texte_traduit(self):
        self.assertEqual(self.sortes((["Leak: Fuite d'huile sous la presse PR-01"],), ([],)), [])

    def test_mot_francais_et_formats(self):
        problemes = self.sortes((["Nothing pour today", "Total 1\u00a0760,00\u00a0€"], ["title=Lundi 19 octobre"]),
                                (["Rien pour aujourd'hui"],))
        self.assertEqual([sorte for sorte, _ in problemes],
                         ["date au format français", "jour en français", "montant au format français",
                          "mot français", "nombre au format français (milliers séparés par une espace)"])

    def test_texte_identique_ni_cle_ni_donnee(self):
        problemes = self.sortes((["Rien de neuf pour la presse"],), (["Rien de neuf pour la presse"],))
        self.assertEqual(len(problemes), 1)
        self.assertIn("ni clé de fr.js ni donnée", problemes[0][1])

    def test_ecran_absent(self):
        anglais = {"mode": "demo", "ecrans": []}
        problemes = self.examen.releve(anglais, self.releve(["Bonjour"]))
        self.assertEqual([p.sorte for p in problemes], ["écran absent en anglais"])

    def test_formats_en_gb(self):
        bon = {"mode": "demo", "ecrans": [
            {"profil": "responsable", "ecran": "accueil", "texte": {"Monday 19 October 2026": 1}},
            {"profil": "responsable", "ecran": "indicateurs › onglet couts", "texte": {"€1,760.00": 1}}]}
        self.assertEqual(formats_en_gb(bon), [])
        mauvais = {"mode": "demo", "ecrans": [
            {"profil": "responsable", "ecran": "accueil", "texte": {"Lundi 19 octobre 2026": 1}},
            {"profil": "responsable", "ecran": "indicateurs", "texte": {"1\u00a0760,00\u00a0€": 1}}]}
        self.assertEqual([p.ecran for p in formats_en_gb(mauvais)], ["accueil", "indicateurs"])

    def test_rapport_groupe_modes_et_profils(self):
        problemes = [Probleme("demo", "demandeur", "accueil", "clé absente", "x"),
                     Probleme("demo", "technicien", "accueil", "clé absente", "x"),
                     Probleme("serveur", "responsable", "accueil", "clé absente", "x")]
        self.assertEqual(rapport(problemes), ["accueil — clé absente : x  [demo : demandeur, technicien ; serveur : responsable]"])


if __name__ == "__main__":
    unittest.main()
