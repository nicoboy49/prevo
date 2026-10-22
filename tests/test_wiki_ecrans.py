"""Écrans du wiki de maintenance (tâche T100, ARCHITECTURE.md §20.7).

Toujours la démo (index.html en file://, « Essayer avec les données de démo »), horloge du navigateur fixée à la
date de référence de la démo (2026-10-19 : dates non décalées, pannes des 12 derniers mois stables). Profils :
responsable, technicien (TEC-0001), demandeur (Lucie Martin). Ce qui est vérifié :
    liste       #/wiki : une carte par élément de Wiki.listePages(), dans le même ordre (repère, désignation,
                pannes sur 12 mois, badge d'état texte + couleur, lien vers la page) ; une synthèse « à valider »
                n'est montrée qu'au responsable (§20.5 : « Aucune synthèse » pour les autres) ; filtre « À valider
                ou à revoir » avec son compte pour le responsable seulement (#/wiki?filtre=a-relire le coche) ;
    page        #/wiki/<id> : pour les 28 pages de la démo, contenu égal à Wiki.page (pannes habituelles : cas,
                période, causes, remèdes et récidives, fourchettes du détail repliable, « peu de cas », message
                « Pas encore assez de cas… (n sur 5) », mention ; pièces ; dernières interventions et « Voir les
                autres » ; même marque et modèle), sections dans l'ordre du contrat, #wiki-synthese en dernier ;
    consignation texte de la fiche identique au caractère près (retours à la ligne, CRLF, espaces), document en
                lien, message d'absence et lien de modification pour le responsable seul, aucun texte d'IA ;
    piège       <img onerror>, <script>, <b> dans une consignation, un titre et un compte rendu : du texte, rien
                n'est exécuté, aussi dans les résultats de recherche ; identifiant piégé dans l'adresse ;
    liens       numéros d'OT et références d'articles en lien pour le technicien et le responsable, en texte
                pour le demandeur (aucun lien vers un OT ni le magasin) ; lien « Wiki de cet équipement » de la
                fiche équipement ;
    recherche   depuis la liste (parc), la page (portées équipement, modèle, parc), l'onglet Préparation d'un OT
                (pré-rempli avec le titre) et la saisie d'une DI (« Déjà vu sur cette machine ? », une fois
                l'équipement choisi, pré-rempli avec le symptôme et qui le suit) : résultats = Wiki.rechercher,
                300 ms après la frappe, 5 montrés par portée puis « Voir les n autres résultats », mots surlignés,
                Entrée n'envoie pas la DI ; hors du wiki, seuls les ajouts prévus ;
    affichage   1440 et 375 px sans défilement horizontal, zones tactiles ≥ 48 px au téléphone, contrastes AA en
                thème clair (audit de test_poste) ; aucune requête réseau pour afficher une page ou chercher.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_ecrans.py" -v
"""
import json
import math
import re
import unittest

from commun import RACINE, CasNavigateur, attendre_pret, preregler_profil, url_fichier
from test_poste import AUDIT_TEXTES_JS

HEURE_FIXE = "2026-10-19T09:00:00"
PROFILS = {"demandeur": ("Lucie Martin", ""), "technicien": ("", "TEC-0001"), "responsable": ("", "")}
ETATS = {"aucune": ("Aucune synthèse", "neutre"), "a_valider": ("Synthèse à valider", "attention"),
         "validee": ("Synthèse validée", "ok"), "a_revoir": ("Synthèse à revoir", "violet")}
MENTION = "Statistique de l'historique, pas un diagnostic"
MENTION_PISTE = "Peu de cas : à prendre comme une piste."
SANS_CONSIGNATION = "Aucune consignation saisie pour cet équipement"
PIEGE = '<img src=x onerror="window.__piege = 1"><script>window.__piege = 2</script><b>gras</b>'
CONSIGNATION_PIEGEE = ("  1. Couper le sectionneur " + PIEGE + "\r\n2. Purger & vérifier « 0 bar »\n\n"
                       "   3. Cadenas personnel\t(clé sur soi)\n")
SECTIONS = ["entete-page", "wiki-consignation", "wiki-recherche", "wiki-pannes", "wiki-pieces", "wiki-dernieres"]

# --- lectures du DOM ---------------------------------------------------------------------------------

LISTE_JS = """() => Array.from(document.querySelectorAll('.wiki-pages > li[data-equipement]')).map((li) => {
  const badge = li.querySelector('.wiki-etat');
  return { equipementId: li.dataset.equipement, etat: li.dataset.etat, pannes: Number(li.dataset.pannes),
    repere: li.querySelector('.carte-tete b').textContent.trim(), designation: li.querySelector('.carte-titre').textContent.trim(),
    texte: li.querySelector('.wiki-pannes').textContent.trim(), badge: badge.textContent.trim(),
    classes: Array.from(badge.classList), href: li.querySelector('a').getAttribute('href') };
})"""

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
  const synthese = document.querySelector('#wiki-synthese');
  const consignation = document.querySelector('#wiki-consignation');
  return {
    h1: t(document.querySelector('#contenu h1')),
    fiche: document.querySelector('#wiki-lien-fiche').getAttribute('href'),
    sections: Array.from(racine.children).map((e) => e.id
      || Array.from(e.classList).filter((c) => c === 'entete-page' || c === 'wiki-recherche').join('.')),
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
    synthese: { derniere: racine.lastElementChild === synthese, vide: synthese.innerHTML === '',
      carte: typeof Wiki.afficherSynthese === 'function' },
  };
}"""

RESULTATS_JS = """(racine) => Array.from(document.querySelectorAll(racine + ' .wiki-portee')).map((bloc) => ({
  portee: bloc.dataset.portee, libelle: bloc.querySelector('h3').firstChild.textContent.trim(),
  ids: Array.from(bloc.querySelectorAll('.wiki-trouve')).map((li) => li.dataset.id),
  caches: Array.from(bloc.querySelectorAll('.wiki-trouve')).map((li) => li.hidden),
  liensOt: bloc.querySelectorAll('a[href^="#/ot"]').length,
  numeros: Array.from(bloc.querySelectorAll('.wiki-trouve')).map((li) => li.querySelector('.wiki-ligne-tete > :first-child').tagName),
  marques: bloc.querySelectorAll('.wiki-extrait mark').length,
  bouton: bloc.querySelector('.wiki-voir-plus') ? bloc.querySelector('.wiki-voir-plus').textContent.trim() : null }))"""

ATTENDU_RECHERCHE_JS = """([texte, equipementId]) => Wiki.rechercher(texte, { equipementId }).portees
  .filter((p) => p.resultats.length)
  .map((p) => ({ portee: p.portee, libelle: p.libelle, ids: p.resultats.map((r) => (r.type === 'ot' ? r.otId : r.syntheseId)) }))"""

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

LARGEUR_JS = "() => [document.documentElement.scrollWidth, window.innerWidth]"
ZONES_JS = """(racine) => Array.from(document.querySelectorAll(['a', 'button', 'summary', 'label.case', 'select', 'textarea',
    'input:not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=file])'].map((s) => racine + ' ' + s).join(', ')))
  .filter((e) => e.getClientRects().length > 0 && !e.closest('[hidden], .visuellement-cache'))
  .map((e) => [e.id || e.className || e.tagName, (e.textContent || e.value || '').trim().slice(0, 30),
               Math.round(e.getBoundingClientRect().height * 10) / 10])"""

ECRIRE_JS = """async ([table, id, valeurs]) => {
  await Donnees.modifier(table, (lignes) => { Object.assign(lignes.find((l) => l.id === id), valeurs); return true; },
    { action: 'test des écrans du wiki' });
}"""

AJOUTER_SYNTHESES_JS = """async (lignes) => {
  await Donnees.modifier('wiki_syntheses', (table) => { lignes.forEach((l) => table.push(l)); return true; },
    { action: 'test des écrans du wiki' });
}"""


# --- valeurs attendues, calculées ici à partir de Wiki.page -------------------------------------------

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


def textes_pannes(nombre):
    return pluriel(nombre, "panne", "pannes") + " sur 12 mois" if nombre else "Aucune panne sur 12 mois"


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


class CasWiki(CasNavigateur):
    """Outils communs : ouvrir la démo dans un contexte neuf (profil, taille, thème), aller à une route."""

    def ouvrir(self, profil="responsable", largeur=1280, hauteur=800, theme=None, telephone=False):
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
        return self.page

    def aller(self, route, attendre):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(attendre, state="attached")

    def aller_page(self, equipement):
        self.aller("#/wiki/" + equipement, '.wiki-page[data-equipement="%s"] #wiki-synthese' % equipement)

    def wiki_page(self, equipement):
        return self.page.evaluate("(id) => Wiki.page(id)", equipement)

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
        self.assertEqual([(l["portee"], l["libelle"], l["ids"]) for l in lus],
                         [(a["portee"], a["libelle"], a["ids"]) for a in attendus])
        for bloc in lus:
            self.assertEqual(bloc["caches"], [rang >= montres for rang in range(len(bloc["ids"]))])
            reste = len(bloc["ids"]) - montres
            self.assertEqual(bloc["bouton"], None if reste <= 0 else (
                "Voir les %d autres résultats" % reste if reste > 1 else "Voir l'autre résultat"))
            if demandeur:
                self.assertEqual(bloc["liensOt"], 0)
        return lus


# ---------------------------------------------------------------------------
# #/wiki : liste des pages, états, filtre du responsable
# ---------------------------------------------------------------------------

class TestListe(CasWiki):

    def verifier_liste(self, profil):
        page = self.page
        self.aller("#/wiki", ".wiki-pages > li[data-equipement]")
        self.assertEqual(page.inner_text("#contenu h1").strip(), "Wiki de maintenance")
        attendue = page.evaluate("() => Wiki.listePages()")
        lue = page.evaluate(LISTE_JS)
        self.assertEqual(len(lue), len(attendue))
        self.assertEqual(page.inner_text("#wiki-nombre-pages").strip(), str(len(attendue)))
        for entree, element in zip(attendue, lue):
            etat = entree["etat"]
            if etat == "a_valider" and profil != "responsable":
                etat = "aucune"          # §20.5 : la synthèse à valider n'est vue que du responsable
            libelle, ton = ETATS[etat]
            self.assertEqual(element, {
                "equipementId": entree["equipementId"], "etat": etat, "pannes": entree["pannes12Mois"],
                "repere": entree["repere"], "designation": entree["designation"], "texte": textes_pannes(entree["pannes12Mois"]),
                "badge": libelle, "classes": ["badge", ton, "wiki-etat"], "href": "#/wiki/" + entree["equipementId"]})
        return attendue, lue

    def test_liste_conforme_a_listePages_pour_les_trois_profils(self):
        for profil in ("demandeur", "technicien", "responsable"):
            with self.subTest(profil=profil):
                self.ouvrir(profil)
                attendue, lue = self.verifier_liste(profil)
                self.assertEqual(len(lue), 28)
                pannes = [e["pannes12Mois"] for e in attendue]
                self.assertEqual(pannes, sorted(pannes, reverse=True))
                self.assertEqual(self.page.locator("#wiki-filtre-relecture").count(), 1 if profil == "responsable" else 0)
                self.assertEqual(self.page.locator(".wiki-filtre").count(), 1 if profil == "responsable" else 0)
                etats = {e["etat"] for e in lue}
                self.assertEqual(etats, {"a_valider", "aucune"} if profil == "responsable" else {"aucune"})

    def test_etats_a_revoir_et_validee_vus_de_tous(self):
        """Une synthèse validée suivie d'interventions → « à revoir » ; validée à jour → « validée » : les deux
        sont vues du technicien et du demandeur, la synthèse « à valider » ne l'est pas."""
        for profil in ("technicien", "demandeur", "responsable"):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil)
                sources = page.evaluate("""() => Donnees.lignes('ordres_travail')
                    .filter((o) => o.equipement_id === 'EQ-0022' && /^Clôturé/.test(o.statut)).map((o) => o.id).join(';')""")
                page.evaluate(AJOUTER_SYNTHESES_JS, [
                    {"id": "WIKI-9001", "equipement_id": "EQ-0007", "texte": "", "ot_cites": "", "ot_sources": "",
                     "statut": "validée", "modele": "essai", "date_proposition": "2025-01-01 09:00", "corrigee_par": "",
                     "date_modification": "", "valide_par": "Responsable", "date_validation": "2025-01-02 09:00"},
                    {"id": "WIKI-9002", "equipement_id": "EQ-0022", "texte": "", "ot_cites": "", "ot_sources": sources,
                     "statut": "validée", "modele": "essai", "date_proposition": "2026-10-19 08:00", "corrigee_par": "",
                     "date_modification": "", "valide_par": "Responsable", "date_validation": "2026-10-19 08:30"}])
                _, lue = self.verifier_liste(profil)
                par_id = {e["equipementId"]: e for e in lue}
                self.assertEqual(par_id["EQ-0007"]["badge"], "Synthèse à revoir")
                self.assertEqual(par_id["EQ-0022"]["badge"], "Synthèse validée")
                self.assertEqual(par_id["EQ-0001"]["badge"],
                                 "Synthèse à valider" if profil == "responsable" else "Aucune synthèse")

    def test_filtre_a_valider_ou_a_revoir_du_responsable(self):
        page = self.ouvrir("responsable")
        page.evaluate(AJOUTER_SYNTHESES_JS, [
            {"id": "WIKI-9001", "equipement_id": "EQ-0007", "texte": "", "ot_cites": "", "ot_sources": "",
             "statut": "validée", "modele": "essai", "date_proposition": "2025-01-01 09:00", "corrigee_par": "",
             "date_modification": "", "valide_par": "Responsable", "date_validation": "2025-01-02 09:00"}])
        attendue, toutes = self.verifier_liste("responsable")
        a_relire = [e["equipementId"] for e in attendue if e["etat"] in ("a_valider", "a_revoir")]
        self.assertEqual(len(a_relire), 13)                     # 12 synthèses de la démo à valider + 1 à revoir
        self.assertEqual(page.inner_text("#wiki-compte-relecture").strip(), "13")
        self.assertIn("À valider ou à revoir", page.inner_text(".wiki-filtre"))
        self.assertFalse(page.is_checked("#wiki-filtre-relecture"))
        page.check("#wiki-filtre-relecture")
        lue = page.evaluate(LISTE_JS)
        self.assertEqual([e["equipementId"] for e in lue], a_relire)             # triée par pannes, comme la liste
        self.assertEqual({e["etat"] for e in lue}, {"a_valider", "a_revoir"})
        page.uncheck("#wiki-filtre-relecture")
        self.assertEqual(page.evaluate(LISTE_JS), toutes)
        # Adresse : #/wiki?filtre=a-relire coche le filtre
        self.aller("#/accueil", "#bento")
        self.aller("#/wiki?filtre=a-relire", ".wiki-pages > li[data-equipement]")
        self.assertTrue(page.is_checked("#wiki-filtre-relecture"))
        self.assertEqual([e["equipementId"] for e in page.evaluate(LISTE_JS)], a_relire)
        # Plus rien à relire : message
        page.evaluate("""async () => { await Donnees.modifier('wiki_syntheses', (table) => {
            table.forEach((l) => { l.statut = 'remplacée'; }); return true; }, { action: 'test' }); }""")
        self.aller("#/accueil", "#bento")
        self.aller("#/wiki?filtre=a-relire", ".wiki-pages > li")
        self.assertEqual(page.inner_text("#wiki-compte-relecture").strip(), "0")
        self.assertIn("Rien à relire", page.inner_text(".wiki-pages"))

    def test_liens_vers_les_pages_et_recherche_sur_le_parc(self):
        page = self.ouvrir("technicien")
        self.aller("#/wiki", ".wiki-pages > li[data-equipement]")
        section = page.locator("#contenu .wiki-recherche")
        self.assertEqual(section.count(), 1)
        self.assertIn("Chercher dans l'historique du parc", section.inner_text())
        self.assertEqual(section.get_attribute("data-equipement"), "")
        self.chercher("#contenu .wiki-recherche", "garniture")
        lus = self.verifier_resultats("#contenu .wiki-recherche", "garniture", "")
        self.assertEqual([b["portee"] for b in lus], ["parc"])
        page.click('.wiki-pages a[href="#/wiki/EQ-0005"]')
        page.wait_for_selector('.wiki-page[data-equipement="EQ-0005"]')
        self.assertEqual(page.inner_text("#contenu h1").strip(), "PO-02 — Pompe centrifuge eau de refroidissement")


# ---------------------------------------------------------------------------
# #/wiki/<équipement> : contenu égal à Wiki.page, consignation, pièges, liens
# ---------------------------------------------------------------------------

class TestPage(CasWiki):

    def verifier_page(self, equipement, profil):
        attendu = self.wiki_page(equipement)
        self.aller_page(equipement)
        lu = self.page.evaluate(PAGE_JS)
        eq = attendu["equipement"]
        liens = profil != "demandeur"
        self.assertEqual(lu["h1"], plat("%s — %s" % (eq["repere"], eq["designation"])))
        self.assertEqual(lu["fiche"], "#/equipement/" + equipement)
        self.assertEqual(lu["sections"], SECTIONS + (["wiki-meme-modele"] if attendu["memeModele"] else []) + ["wiki-synthese"])
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
        # Synthèse [IA] : place réservée, en dernier (vide tant que wiki-synthese.js n'y pose pas sa carte)
        self.assertTrue(lu["synthese"]["derniere"])
        if not lu["synthese"]["carte"]:
            self.assertTrue(lu["synthese"]["vide"])
        return attendu, lu

    def test_les_28_pages_de_la_demo_conformes_a_Wiki_page(self):
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
                # aucune phrase de la synthèse de l'équipement dans ce bloc
                synthese = page.evaluate("(id) => Donnees.lignes('wiki_syntheses').filter((s) => s.equipement_id === id)"
                                         ".map((s) => s.texte).join('\\n')", equipement)
                for ligne in [l for l in synthese.split("\n") if len(l) > 20]:
                    self.assertNotIn(ligne.strip("- "), page.inner_text("#wiki-consignation"))

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
        self.aller("#/wiki", ".wiki-pages")
        self.aller_page("EQ-0001")
        page.wait_for_selector("#wiki-consignation .wiki-document .badge")
        self.assertEqual(plat(page.inner_text("#wiki-consignation .wiki-consignation-document")),
                         "Document : plan-absent.pdf fichier introuvable")
        # Ni texte ni document : message d'absence et, au responsable, le lien de modification de la fiche
        page.evaluate(ECRIRE_JS, ["equipements", "EQ-0001", {"consignation": "  \n ", "document": ""}])
        self.aller("#/wiki", ".wiki-pages")
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
        ot = page.evaluate("(id) => Wiki.page(id).dernieres[0].id", "EQ-0001")
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
        self.assertEqual(page.locator("#contenu img, #contenu script").count(), 0)
        self.assertIsNone(page.evaluate("window.__piege === undefined ? null : window.__piege"))

    def test_equipement_inconnu_et_identifiant_piege(self):
        page = self.ouvrir("technicien")
        self.aller("#/wiki/EQ-9999", ".wiki-introuvable")
        self.assertEqual(page.inner_text("#contenu h1").strip(), "Équipement introuvable")
        self.assertIn("EQ-9999", page.inner_text("#contenu .vide"))
        self.assertEqual(page.get_attribute('#contenu a.btn[href="#/wiki"]', "href"), "#/wiki")
        self.aller("#/wiki/%3Cimg%20src%3Dx%20onerror%3D%22window.__piege%3D1%22%3E", ".wiki-introuvable")
        self.assertIn('<img src=x onerror="window.__piege=1">', page.inner_text("#contenu .vide"))
        self.assertEqual(page.locator("#contenu img").count(), 0)
        self.assertIsNone(page.evaluate("window.__piege === undefined ? null : window.__piege"))

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
                    page.wait_for_function("location.hash === '#/ot?equipement=EQ-0001&etat=clotures'")
                    page.wait_for_function("() => (document.querySelector('#contenu h1') || {}).textContent === 'Ordres de travail'")
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
        self.assertEqual({n for b in lus for n in b["numeros"]}, {"B"})            # numéros en texte, sans lien
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
# Affichage : 1440 et 375 px, zones tactiles, contrastes, réseau
# ---------------------------------------------------------------------------

class TestAffichage(CasWiki):

    def parcourir(self, verifier, profil):
        """Liste avec résultats, pages (résultats et détails ouverts), fiche équipement ; puis OT et DI (blocs wiki)."""
        page = self.page
        self.aller("#/wiki", ".wiki-pages > li[data-equipement]")
        self.chercher("#contenu .wiki-recherche", "fuite garniture")
        page.click("#contenu .wiki-voir-plus")
        verifier("#contenu", "liste")
        if profil == "responsable":
            page.check("#wiki-filtre-relecture")
            verifier("#contenu", "liste filtrée")
        for equipement in ("EQ-0001", "EQ-0023", "EQ-0031"):
            self.aller_page(equipement)
            self.chercher(".wiki-page .wiki-recherche", "capteur filtre")
            page.evaluate("() => document.querySelectorAll('.wiki-page details').forEach((d) => { d.open = true; })")
            verifier("#contenu", "page " + equipement)
        self.aller("#/equipement/EQ-0001", "#lien-wiki-equipement")
        verifier("p:has(> #lien-wiki-equipement)", "fiche équipement")
        self.aller("#/di/nouvelle?equipement=EQ-0001", ".wiki-recherche-demande")
        page.fill("input[name=symptome]", "échauffement")
        self.attendre_resultats(".wiki-recherche-demande")
        verifier(".wiki-recherche-demande", "saisie d'une DI")
        if profil != "demandeur":
            ot = page.evaluate("() => Wiki.page('EQ-0001').dernieres[1].id")
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
        page = self.ouvrir("technicien")
        requetes = []
        page.on("request", lambda requete: requetes.append(requete.url))
        page.evaluate("""() => { window.__appels = [];
            const noter = (nom) => function () { window.__appels.push(nom); throw new Error('appel réseau interdit : ' + nom); };
            window.fetch = noter('fetch'); XMLHttpRequest.prototype.open = noter('xhr');
            navigator.sendBeacon = noter('beacon'); window.WebSocket = noter('websocket'); window.EventSource = noter('eventsource'); }""")
        self.parcourir(lambda racine, ou: None, "technicien")
        for texte in ("bruit", "ne démarre pas", "fuite", "température"):
            page.evaluate("(t) => Wiki.rechercher(t, {})", texte)
        self.assertEqual(page.evaluate("window.__appels"), [])
        self.assertEqual([u for u in requetes if not u.startswith(("blob:", "data:"))], [])


if __name__ == "__main__":
    unittest.main()
