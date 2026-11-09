"""Accueil du responsable en « bento », menu latéral, barre du bas, notification (tâches T89 et T90 ;
BRIEF_design_accueil.md).

Toujours la démo (index.html en file://, « Essayer avec les données de démo »), profil responsable sauf
mention, horloge du navigateur fixée à la date de référence de la démo (2026-10-19 : dates non décalées),
fuseau Europe/Paris ; contexte en mouvements réduits (reduced_motion) pour lire les chiffres finaux, sauf
pour les tests des mouvements. Familles (le nom du test le dit) :
    phrase      phrase de la tuile de synthèse et ligne secondaire construites d'après les données
                (accords, segments à 0 omis, « Rien d'urgent ce matin. »), « Ce matin / Cet après-midi /
                Ce soir » à 9 h, 14 h et 19 h ;
    premier     « À traiter en premier » : DI sécurité ou P1 la plus ancienne, sinon l'OT le plus en
                retard, sinon le prochain préventif (choix recalculé en Python), libellé du bouton selon
                le type ; rien → tuile masquée, la synthèse prend toute la largeur ;
    chiffres    chaque chiffre = la liste correspondante (Accueil.calculerCompteurs, Suggestions), listes
                « Demandes à traiter » et « OT en retard », liens vers les listes filtrées ;
    reserves    2.2 (T421, CS170) : troisième lien de « Contrôles et habilitations », réserves en retard (la
                réserve de RA-01, échéance par défaut passée) vers #/controles?filtre=reserves-en-retard, détail
                selon l'échéance (saisie, par défaut, mêlées, aucune) ; indicateur du technicien ;
    rapport     tuile du rapport : « Figer », « Plus tard », absente si le mois est figé → la ligne des
                compteurs s'étend ;
    mouvements  coupés avec prefers-reduced-motion (ni animation ni transition, chiffres tout de suite) ;
                sans cette préférence, les chiffres défilent jusqu'à leur valeur et les tuiles se soulèvent ;
    jetons      jetons de couleur du brief dans les deux thèmes, et utilisés par les tuiles et la barre ;
    contrastes  textes affichés (audit de test_poste) à 1440 et 390 px, clair et sombre, plus la mesure
                réelle du blanc sur le dégradé : capture de la tuile avec le texte transparent, pire pixel
                (halos compris, sur toute leur dérive) sous chaque texte ;
    zones       zones cliquables ≥ 44 px (48 px au téléphone), pas de défilement horizontal ;
    decor       décor « lueur » en aria-hidden ; notification en role="status", bulle à droite sur PC,
                au-dessus de la barre du bas au téléphone, courte ; pas de toast à l'ouverture de la démo ;
    autres      accueils technicien et demandeur inchangés (structure relevée sur le commit eb2a5b9),
                aucune couleur en dur hors des variables (CSS des modules, JavaScript de l'accueil).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_bento.py" -v
"""
import base64
import json
import re
import sys
import unittest

from commun import RACINE, CasNavigateur, attendre_pret, preregler_profil, scenarios_demo, url_fichier
from test_poste import AUDIT_TEXTES_JS

REFERENCE = "2026-10-19"
MATIN, APRES_MIDI, SOIR = REFERENCE + "T09:00:00", REFERENCE + "T14:00:00", REFERENCE + "T19:00:00"
STATUTS_FERMES = ["Clôturé techniquement", "Clôturé administrativement", "Annulé"]
RANG_PRIORITE = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}

LIEN_DI, LIEN_RETARD, LIEN_P1 = "#/di?statut=Nouvelle", "#/ot?filtre=retard", "#/ot?filtre=p1"
LIEN_PREVENTIFS, LIEN_ARTICLES = "#/preventif?onglet=calendrier", "#/magasin?onglet=a-commander"
LIEN_CONTROLES, LIEN_HABILITATIONS = "#/controles?filtre=30j", "#/equipe?filtre=a-renouveler"
LIEN_SUGGESTIONS, LIEN_PLANNING = "#/preventif?onglet=suggestions", "#/planning"
LIEN_RESERVES = "#/controles?filtre=reserves-en-retard"

# Jetons du brief (valeurs écrites sans espaces pour la comparaison)
JETONS = {
    "clair": {
        "--fond-synthese": "linear-gradient(135deg,#2F5BEA0%,#3D6BF255%,#1FA9D6130%)",
        "--ombre-synthese": "022px50pxrgba(47,91,234,.30)",
        "--ombre-tuile": "01px2pxrgba(14,22,48,.04),010px28pxrgba(14,22,48,.06)",
        "--fond-barre-verre": "rgba(255,255,255,.72)",
        "--rayon-tuile": "24px", "--rayon-tuile-grande": "28px",
    },
    "sombre": {
        "--fond-synthese": "linear-gradient(135deg,#2F5BEA0%,#3D6BF255%,#1FA9D6130%)",
        "--ombre-synthese": "024px60pxrgba(51,102,230,.35)",
        "--ombre-tuile": "none",
        "--fond-barre-verre": "rgba(18,27,54,.72)",
        "--rayon-tuile": "24px", "--rayon-tuile-grande": "28px",
    },
}

# Accueils technicien (TEC-0002) et demandeur (Lucas Perrot) au 2026-10-19 : structure relevée sur le
# commit eb2a5b9 (avant la refonte) par .chantier/design/bento/captures_bento.py.
STRUCTURE_AVANT = {
    "technicien": {
        "h1": "Accueil",
        "blocs": ["div.entete-page", "div.pile-gros.accueil-signaler",
                  "div.instruments.accueil-instruments.accueil-instruments-technicien", "article.carte.accueil-mes-ordres"],
        "classes": ["accent-p1", "accueil-instruments", "accueil-instruments-technicien", "accueil-mes-ordres",
                    "accueil-preventifs-vide", "accueil-signaler", "accueil-sous-titre", "accueil-voir-tout", "ambre",
                    "badge", "btn", "btn-gros", "btn-primaire", "carte", "carte-meta", "carte-tete", "carte-titre",
                    "chiffre", "comp", "cyan", "entete-carte", "entete-page", "info", "instruments", "lib",
                    "liste-cartes", "muted", "neutre", "pile-gros", "prio-p1", "prio-p3", "prio-p4", "rouge",
                    "statut", "violet"],
    },
    "demandeur": {
        "h1": "Accueil",
        "blocs": ["div.entete-page", "div.pile-gros.accueil-signaler", "article.carte"],
        "classes": ["accueil-motif", "accueil-signaler", "accueil-voir-tout", "attention", "badge", "btn", "btn-gros",
                    "btn-primaire", "carte", "carte-meta", "carte-tete", "carte-titre", "entete-carte", "entete-page",
                    "info", "liste-cartes", "ok", "pile-gros", "statut", "violet"],
    },
}

NOTER_TOASTS_JS = """(() => {
  window.__toasts = [];
  let dernier = '';
  new MutationObserver(() => {
    const zone = document.getElementById('toast');
    const texte = zone && zone.classList.contains('visible') ? zone.textContent.trim() : '';
    if (texte && texte !== dernier) window.__toasts.push(texte);
    dernier = texte;
  }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class'] });
})();"""

STRUCTURE_JS = """() => {
  const classes = new Set();
  document.querySelectorAll('#contenu *').forEach((e) => {
    if (typeof e.className === 'string') e.className.split(/\\s+/).filter(Boolean).forEach((c) => classes.add(c));
  });
  return { classes: Array.from(classes).sort(), h1: (document.querySelector('#contenu h1') || {}).textContent || null,
           blocs: Array.from(document.querySelectorAll('#contenu > *')).map((e) => e.tagName.toLowerCase() + '.' + String(e.className).trim().split(/\\s+/).join('.')) };
}"""

DONNEES_JS = """() => {
  const c = Accueil.calculerCompteurs();
  const fermes = %s;
  return {
    di: c.diATraiter.map((d) => ({ id: d.id, impact: d.impact, date: d.date_heure })),
    p1: c.p1Ouverts.map((o) => ({ id: o.id, date: o.date_creation, statut: o.statut })),
    retard: c.otEnRetard.map((o) => ({ id: o.id, prevue: o.date_prevue, priorite: o.priorite })),
    preventifs: c.preventifsSemaine.map((o) => o.id),
    ouverts: Donnees.lignes('ordres_travail').filter((o) => !fermes.includes(o.statut))
      .map((o) => ({ id: o.id, origine: o.origine, prevue: o.date_prevue })),
    articles: c.articlesACommander.length, controles: c.controlesSous30j.length,
    habilitations: c.habilitationsARenouveler.length,
    reserves: c.reservesEnRetard.map((e) => ({ id: e.reserve.id, parDefaut: e.etat.parDefaut })),
    suggestions: Suggestions.ouvertes(Donnees.aujourdhui()).length,
  };
}""" % json.dumps(STATUTS_FERMES)

# Valeur affichée d'un chiffre (le chiffre défile par la propriété --compte ; le texte du DOM est la valeur)
CHIFFRES_JS = """() => Array.from(document.querySelectorAll('#bento .chiffre')).map((e) => ({
  texte: e.textContent.trim(), compte: getComputedStyle(e).getPropertyValue('--compte').trim() }))"""

ZONES_JS = """(seuil) => {
  const petites = [];
  const selecteur = '#contenu a, #contenu button, #menu a, .menu-lateral button, .menu-lateral a, #barre-bas a, #barre-bas button, .entete-mobile button';
  for (const el of document.querySelectorAll(selecteur)) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || el.closest('[hidden]') || getComputedStyle(el).visibility === 'hidden') continue;
    if (r.height < seuil - 0.5) petites.push(el.tagName + ' « ' + (el.textContent || '').trim().slice(0, 30) + ' » ' + Math.round(r.height) + ' px');
  }
  return petites;
}"""

# Contraste des chiffres (dessinés par ::after, que l'audit des textes ne voit pas)
CHIFFRES_CONTRASTE_JS = """() => {
  const lire = (c) => { const m = (c || '').match(/[0-9.]+/g); if (!m) return null;
    const v = m.map(Number); return { r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1 }; };
  const sur = (h, b) => ({ r: h.r * h.a + b.r * (1 - h.a), g: h.g * h.a + b.g * (1 - h.a), b: h.b * h.a + b.b * (1 - h.a), a: 1 });
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const fondDe = (el) => { const couches = [];
    for (let e = el; e; e = e.parentElement) { const c = lire(getComputedStyle(e).backgroundColor);
      if (c && c.a > 0) { couches.push(c); if (c.a >= 1) break; } }
    let fond = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = couches.length - 1; i >= 0; i -= 1) fond = sur(couches[i], fond);
    return fond; };
  return Array.from(document.querySelectorAll('#bento .chiffre')).filter((e) => e.getClientRects().length)
    .map((e) => { const s = getComputedStyle(e, '::after');
      return [e.textContent.trim(), parseFloat(s.fontSize), Number(s.fontWeight),
              Math.round(ratio(sur(lire(s.color), fondDe(e)), fondDe(e)) * 100) / 100]; });
}"""

# Mesure réelle du blanc sur le dégradé, 1) boîtes des textes de la tuile de synthèse (hors décor). La
# boîte d'un texte (celle de la police, plus haute que sa ligne) peut mordre sur un autre élément qui a
# son propre fond (pastille « sécurité », boutons, pastille du moment) : ces zones-là sont exclues de
# sa boîte (on y mesure les textes de ces éléments, sur leur fond).
BOITES_SYNTHESE_JS = """() => {
  const tuile = document.getElementById('bento-synthese');
  const base = tuile.getBoundingClientRect();
  const relatif = (b) => ({ x: b.left - base.left, y: b.top - base.top, l: b.width, h: b.height });
  const aFond = Array.from(tuile.querySelectorAll('.bento-moment, .bento-securite, .btn'));
  const textes = [];
  const marcheur = document.createTreeWalker(tuile, NodeFilter.SHOW_TEXT);
  for (let n = marcheur.nextNode(); n; n = marcheur.nextNode()) {
    if (!n.textContent.trim() || n.parentElement.closest('.bento-lueur')) continue;
    const s = getComputedStyle(n.parentElement);
    const r = document.createRange();
    r.selectNodeContents(n);
    // Texte posé sur un élément à fond propre : sa boîte s'arrête 2 px avant le bord de cet élément
    // (bord arrondi ; les lettres n'y vont jamais)
    const support = aFond.filter((e) => e.contains(n)).pop();
    const bord = support ? support.getBoundingClientRect() : null;
    const boites = Array.from(r.getClientRects()).filter((b) => b.width > 0 && b.height > 0)
      .map((b) => { if (!bord) return b;
        const haut = Math.max(b.top, bord.top + 2), bas = Math.min(b.bottom, bord.bottom - 2);
        return new DOMRect(b.left, haut, b.width, bas - haut); })
      .map(relatif);
    // Les autres éléments à fond propre, élargis d'1 px (bord adouci de leurs coins arrondis)
    const exclues = aFond.filter((e) => !e.contains(n)).map((e) => { const b = e.getBoundingClientRect();
      return relatif(new DOMRect(b.left - 1, b.top - 1, b.width + 2, b.height + 2)); });
    if (boites.length) textes.push({ texte: n.textContent.trim().replace(/\\s+/g, ' '), couleur: s.color,
      taille: parseFloat(s.fontSize), graisse: Number(s.fontWeight), boites, exclues });
  }
  return textes;
}"""

# 2) texte rendu transparent (le fond seul reste dans la capture), sans transition (celle de la couleur
#    des boutons laisserait le texte à moitié visible dans la première capture)
TEXTE_TRANSPARENT_JS = """(actif) => new Promise((resoudre) => {
  let style = document.getElementById('sonde-transparent');
  if (!style) { style = document.createElement('style'); style.id = 'sonde-transparent'; document.head.appendChild(style); }
  style.textContent = actif ? '#bento-synthese, #bento-synthese * { color: transparent !important; text-shadow: none !important; transition: none !important; }' : '';
  requestAnimationFrame(() => requestAnimationFrame(resoudre));
})"""

# 3) halos arrêtés à une fraction de leur dérive (sans effet si les mouvements sont réduits)
HALOS_JS = """(fraction) => {
  const animations = [];
  document.querySelectorAll('#bento-synthese .bento-halo').forEach((h) => h.getAnimations().forEach((a) => animations.push(a)));
  animations.forEach((a) => { a.pause(); a.currentTime = fraction * a.effect.getComputedTiming().duration; });
  return animations.length;
}"""

# 4) pire contraste sous chaque texte : chaque pixel de sa boîte contre la couleur du texte
PIRE_CONTRASTE_JS = """async ([png, textes, echelle]) => {
  const image = new Image();
  image.src = 'data:image/png;base64,' + png;
  await image.decode();
  const toile = document.createElement('canvas');
  toile.width = image.width; toile.height = image.height;
  const ctx = toile.getContext('2d');
  ctx.drawImage(image, 0, 0);
  const pixels = ctx.getImageData(0, 0, toile.width, toile.height).data;
  const lineaire = []; for (let v = 0; v < 256; v += 1) { const x = v / 255; lineaire.push(x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4)); }
  const lum = (r, g, b) => 0.2126 * lineaire[r] + 0.7152 * lineaire[g] + 0.0722 * lineaire[b];
  return textes.map((t) => {
    const c = t.couleur.match(/[0-9.]+/g).map(Number);
    const lt = lum(Math.round(c[0]), Math.round(c[1]), Math.round(c[2]));
    const exclu = (x, y) => t.exclues.some((e) => x >= e.x * echelle && x < (e.x + e.l) * echelle && y >= e.y * echelle && y < (e.y + e.h) * echelle);
    let pire = Infinity;
    t.boites.forEach((b) => {
      const x0 = Math.max(0, Math.floor(b.x * echelle)), y0 = Math.max(0, Math.floor(b.y * echelle));
      const x1 = Math.min(toile.width, Math.ceil((b.x + b.l) * echelle)), y1 = Math.min(toile.height, Math.ceil((b.y + b.h) * echelle));
      for (let y = y0; y < y1; y += 1) for (let x = x0; x < x1; x += 1) {
        if (exclu(x, y)) continue;
        const i = (y * toile.width + x) * 4;
        const lf = lum(pixels[i], pixels[i + 1], pixels[i + 2]);
        const r = (Math.max(lt, lf) + 0.05) / (Math.min(lt, lf) + 0.05);
        if (r < pire) pire = r;
      }
    });
    return pire;
  });
}"""

OUVRIR_ACCUEIL_JS = "() => { location.hash = '#/accueil'; }"


def espaces(texte):
    return re.sub(r"\s+", " ", texte or "").strip()


def accord(nombre, singulier, pluriel=None):
    return "%d %s" % (nombre, singulier if nombre <= 1 else (pluriel or singulier + "s"))


def phrase_attendue(di, securite, moment):
    """Phrase de la synthèse (calcul indépendant de celui de l'application)."""
    if di == 0:
        return {"matin": "Rien d'urgent ce matin.", "après-midi": "Rien d'urgent cet après-midi.",
                "soir": "Rien d'urgent ce soir."}[moment]
    texte = accord(di, "demande") + " à traiter"
    return texte + (", dont %d sécurité" % securite if securite else "")


def ligne_attendue(retard, p1, preventifs):
    segments = []
    if retard:
        segments.append("%d OT en retard" % retard)
    if p1:
        segments.append(accord(p1, "P1 ouvert", "P1 ouverts"))
    if preventifs:
        segments.append(accord(preventifs, "préventif") + " cette semaine")
    return " · ".join(segments)


def premier_attendu(donnees):
    """(type, identifiant) de « À traiter en premier », ou None (calcul indépendant)."""
    candidats = [(d["date"] or "9999", 0, d["id"], "securite") for d in donnees["di"] if d["impact"] == "sécurité"]
    candidats += [(o["date"] or "9999", 1, o["id"], "p1") for o in donnees["p1"]]
    if candidats:
        choix = min(candidats)
        return choix[3], choix[2]
    if donnees["retard"]:
        choix = min(donnees["retard"], key=lambda o: (o["prevue"], RANG_PRIORITE.get(o["priorite"], 9), o["id"]))
        return "retard", choix["id"]
    preventifs = [o for o in donnees["ouverts"] if o["origine"] == "préventif" and o["prevue"]]
    if preventifs:
        choix = min(preventifs, key=lambda o: (o["prevue"], o["id"]))
        return "preventif", choix["id"]
    return None


LIBELLES_ACTION = {"securite": "Traiter la demande", "p1": "Ouvrir l'ordre de travail",
                   "retard": "Ouvrir l'ordre de travail", "preventif": "Ouvrir le préventif"}


class CasBento(CasNavigateur):
    """Outils communs : ouvrir la démo dans un contexte réglé (taille, thème, heure, mouvements)."""

    def ouvrir(self, largeur=1440, hauteur=900, telephone=False, theme=None, heure=MATIN, mouvement="reduce",
               profil="responsable", nom="", technicien_id=""):
        options = dict(locale="fr-FR", timezone_id="Europe/Paris", reduced_motion=mouvement,
                       viewport={"width": largeur, "height": hauteur})
        if telephone:
            options.update(is_mobile=True, has_touch=True, device_scale_factor=2)
        contexte = self.navigateur.new_context(**options)
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        contexte.clock.set_fixed_time(heure)
        if theme:
            contexte.add_init_script("try { localStorage.setItem('prevo.theme', %s); } catch (e) { /* sans stockage */ }"
                                     % json.dumps(theme))
        contexte.add_init_script(NOTER_TOASTS_JS)
        preregler_profil(contexte, profil, nom, technicien_id, poste="Poste atelier")
        page = contexte.new_page()
        self.surveiller(page)
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        self.assertEqual(page.evaluate("Donnees.aujourdhui()"), REFERENCE)
        if profil == "responsable":
            page.wait_for_selector("#bento")
        return page

    def donnees(self, page):
        return page.evaluate(DONNEES_JS)

    def modifier_puis_reafficher(self, page, script):
        """Exécute `script` (fonction async de la page, qui écrit par Donnees.modifier) puis réaffiche."""
        page.evaluate("async () => { await (%s)(); await App.reafficher(); }" % script)
        page.wait_for_selector("#bento")

    def texte(self, page, selecteur):
        return espaces(page.eval_on_selector(selecteur, "e => e.textContent"))

    def sans_defilement_horizontal(self, page, contexte):
        largeurs = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))


# ---------------------------------------------------------------------------
# phrase
# ---------------------------------------------------------------------------

class TestPhrase(CasBento):

    def verifier_phrase(self, page, moment):
        d = self.donnees(page)
        securite = sum(1 for x in d["di"] if x["impact"] == "sécurité")
        self.assertEqual(self.texte(page, "#bento-phrase"), phrase_attendue(len(d["di"]), securite, moment))
        ligne = ligne_attendue(len(d["retard"]), len(d["p1"]), len(d["preventifs"]))
        if ligne:
            self.assertEqual(self.texte(page, "#bento-ligne"), ligne)
        else:
            self.assertEqual(page.locator("#bento-ligne").count(), 0)
        self.assertEqual(page.locator("#bento-phrase .bento-securite").count(), 1 if len(d["di"]) and securite else 0)
        return d

    def test_phrase_ce_matin_d_apres_les_donnees_de_la_demo(self):
        page = self.ouvrir(heure=MATIN)
        self.assertEqual(self.texte(page, "#bento-synthese .bento-moment"), "Ce matin dans l'atelier")
        d = self.verifier_phrase(page, "matin")
        # La démo du 19/10 donne du pluriel et du singulier (sinon ce test ne prouverait rien)
        self.assertEqual((len(d["di"]), sum(1 for x in d["di"] if x["impact"] == "sécurité")), (5, 1))
        self.assertEqual((len(d["retard"]), len(d["p1"]), len(d["preventifs"])), (3, 1, 3))
        self.assertEqual(self.texte(page, "#bento-phrase"), "5 demandes à traiter, dont 1 sécurité")
        self.assertEqual(self.texte(page, "#bento-ligne"), "3 OT en retard · 1 P1 ouvert · 3 préventifs cette semaine")
        # Boutons de la synthèse
        self.assertEqual(self.texte(page, "#bento-synthese a[href='%s']" % LIEN_DI), "Voir les demandes →")
        self.assertEqual(self.texte(page, "#bento-synthese a[href='%s']" % LIEN_PLANNING), "Ouvrir le planning")
        # En-tête : « Bonjour », date en toutes lettres
        self.assertEqual(self.texte(page, "#contenu .bento-entete h1"), "Bonjour")
        self.assertEqual(self.texte(page, "#contenu .bento-date"), "Lundi 19 octobre 2026")

    def test_phrase_accords_et_segments_a_zero_omis(self):
        page = self.ouvrir()
        # Une seule DI (sans sécurité), aucun OT en retard, deux P1, un seul préventif de la semaine
        self.modifier_puis_reafficher(page, """async () => {
          const auj = Donnees.aujourdhui();
          const c = Accueil.calculerCompteurs();
          const garder = c.diATraiter.find((d) => d.impact !== 'sécurité').id;
          await Donnees.modifier('demandes', (l) => l.forEach((d) => {
            if (d.statut === 'Nouvelle' && d.id !== garder) { d.statut = 'Différée'; d.motif_decision = 'essai'; } }));
          await Donnees.modifier('ordres_travail', (l) => {
            const ouverts = l.filter((o) => !%s.includes(o.statut));
            const prev = ouverts.find((o) => o.origine === 'préventif');
            ouverts.forEach((o) => { o.date_prevue = '2099-01-01'; if (o.priorite === 'P1') o.priorite = 'P2'; });
            prev.date_prevue = auj;
            ouverts.filter((o) => o !== prev).slice(0, 2).forEach((o) => { o.priorite = 'P1'; });
          });
        }""" % json.dumps(STATUTS_FERMES))
        d = self.verifier_phrase(page, "matin")
        self.assertEqual((len(d["di"]), len(d["retard"]), len(d["p1"]), len(d["preventifs"])), (1, 0, 2, 1))
        self.assertEqual(self.texte(page, "#bento-phrase"), "1 demande à traiter")
        self.assertEqual(self.texte(page, "#bento-ligne"), "2 P1 ouverts · 1 préventif cette semaine")

        # Deux DI de sécurité, un OT en retard, aucun P1, deux préventifs de la semaine
        page = self.ouvrir()
        self.modifier_puis_reafficher(page, """async () => {
          const auj = Donnees.aujourdhui();
          const [a, m, j] = auj.split('-').map(Number);
          const hier = new Date(Date.UTC(a, m - 1, j - 1)).toISOString().slice(0, 10);
          const c = Accueil.calculerCompteurs();
          const garder = c.diATraiter.slice(0, 2).map((d) => d.id);
          await Donnees.modifier('demandes', (l) => l.forEach((d) => {
            if (d.statut !== 'Nouvelle') return;
            if (garder.includes(d.id)) d.impact = 'sécurité'; else { d.statut = 'Différée'; d.motif_decision = 'essai'; } }));
          await Donnees.modifier('ordres_travail', (l) => {
            const ouverts = l.filter((o) => !%s.includes(o.statut));
            ouverts.forEach((o) => { o.date_prevue = '2099-01-01'; if (o.priorite === 'P1') o.priorite = 'P2'; });
            ouverts.filter((o) => o.origine === 'préventif').slice(0, 2).forEach((o) => { o.date_prevue = auj; });
            ouverts.find((o) => o.origine !== 'préventif').date_prevue = hier;
          });
        }""" % json.dumps(STATUTS_FERMES))
        d = self.verifier_phrase(page, "matin")
        self.assertEqual((len(d["di"]), len(d["retard"]), len(d["p1"]), len(d["preventifs"])), (2, 1, 0, 2))
        self.assertEqual(self.texte(page, "#bento-phrase"), "2 demandes à traiter, dont 2 sécurité")
        self.assertEqual(self.texte(page, "#bento-ligne"), "1 OT en retard · 2 préventifs cette semaine")

    def test_phrase_cet_apres_midi_ce_soir_et_rien_d_urgent(self):
        vider = """async () => { await Donnees.modifier('demandes', (l) => { l.splice(0, l.length); }); }"""
        for heure, moment, pastille in ((MATIN, "matin", "Ce matin dans l'atelier"),
                                        (APRES_MIDI, "après-midi", "Cet après-midi dans l'atelier"),
                                        (SOIR, "soir", "Ce soir dans l'atelier")):
            with self.subTest(heure=heure):
                page = self.ouvrir(heure=heure)
                self.assertEqual(self.texte(page, "#bento-synthese .bento-moment"), pastille)
                self.verifier_phrase(page, moment)
                self.modifier_puis_reafficher(page, vider)
                self.assertEqual(self.donnees(page)["di"], [])
                self.assertEqual(self.texte(page, "#bento-phrase"), phrase_attendue(0, 0, moment))
                self.verifier_phrase(page, moment)


# ---------------------------------------------------------------------------
# premier
# ---------------------------------------------------------------------------

class TestPremier(CasBento):

    def verifier_premier(self, page, type_attendu):
        d = self.donnees(page)
        attendu = premier_attendu(d)
        self.assertEqual(attendu[0] if attendu else None, type_attendu, attendu)
        tuile = page.locator("#bento-premier")
        if attendu is None:
            self.assertEqual(tuile.count(), 0)
            # La synthèse prend toute la largeur de la grille
            largeurs = page.evaluate("""() => [document.getElementById('bento-synthese').getBoundingClientRect().width,
                document.getElementById('bento').getBoundingClientRect().width]""")
            self.assertAlmostEqual(largeurs[0], largeurs[1], delta=1)
            return
        self.assertEqual(tuile.count(), 1)
        self.assertEqual((tuile.get_attribute("data-type"), tuile.get_attribute("data-id")), attendu)
        self.assertEqual(espaces(tuile.locator("h2").inner_text()), "À traiter en premier")
        action = tuile.locator(".bento-premier-action")
        self.assertEqual(espaces(action.inner_text()), LIBELLES_ACTION[attendu[0]])
        self.assertEqual(action.get_attribute("href"), ("#/di/" if attendu[0] == "securite" else "#/ot/") + attendu[1])
        self.assertIn(attendu[1], espaces(tuile.locator(".bento-pastilles").inner_text()))
        # « 2 colonnes × 2 rangées » : à côté de la synthèse, même hauteur
        boites = page.evaluate("""() => ['bento-synthese', 'bento-premier'].map((id) => {
            const r = document.getElementById(id).getBoundingClientRect(); return [r.top, r.height, r.width]; })""")
        self.assertAlmostEqual(boites[0][0], boites[1][0], delta=1)
        self.assertAlmostEqual(boites[0][1], boites[1][1], delta=1)
        self.assertAlmostEqual(boites[0][2], 2 * boites[1][2] + 16, delta=2)

    def test_premier_securite_ou_p1_la_plus_ancienne_puis_retard_puis_preventif_puis_rien(self):
        page = self.ouvrir()
        # Démo : DI sécurité de 07:15 et P1 créé à 07:50 → la DI
        self.verifier_premier(page, "securite")
        page.click("#bento-premier .bento-premier-action")
        page.wait_for_function("location.hash.startsWith('#/di/')")
        page.evaluate(OUVRIR_ACCUEIL_JS)
        page.wait_for_selector("#bento-premier")
        # Le P1 devient plus ancien que la DI → le P1
        self.modifier_puis_reafficher(page, """async () => {
          const p1 = Accueil.calculerCompteurs().p1Ouverts[0].id;
          await Donnees.modifier('ordres_travail', (l) => { l.find((o) => o.id === p1).date_creation = '2026-10-18 08:00'; });
        }""")
        self.verifier_premier(page, "p1")
        # Ni DI sécurité ni P1 → l'OT le plus en retard
        self.modifier_puis_reafficher(page, """async () => {
          await Donnees.modifier('demandes', (l) => l.forEach((d) => { if (d.impact === 'sécurité') d.impact = 'arrêt'; }));
          await Donnees.modifier('ordres_travail', (l) => l.forEach((o) => { if (o.priorite === 'P1') o.priorite = 'P2'; }));
        }""")
        self.verifier_premier(page, "retard")
        # Plus aucun retard → le prochain préventif
        self.modifier_puis_reafficher(page, """async () => {
          const retards = Accueil.calculerCompteurs().otEnRetard.map((o) => o.id);
          await Donnees.modifier('ordres_travail', (l) => l.forEach((o) => { if (retards.includes(o.id)) o.statut = 'Annulé'; }));
        }""")
        self.verifier_premier(page, "preventif")
        # Plus aucun préventif ouvert → tuile masquée, synthèse sur toute la largeur
        self.modifier_puis_reafficher(page, """async () => {
          await Donnees.modifier('ordres_travail', (l) => l.forEach((o) => {
            if (o.origine === 'préventif' && !%s.includes(o.statut)) o.statut = 'Annulé'; }));
        }""" % json.dumps(STATUTS_FERMES))
        self.verifier_premier(page, None)


# ---------------------------------------------------------------------------
# chiffres
# ---------------------------------------------------------------------------

class TestChiffres(CasBento):

    def tuile(self, page, lien):
        """Tuile-lien (compteur, « à surveiller ») ou lien de la tuile « Contrôles et habilitations »."""
        return page.locator("#bento :is(a.bento-compteur, a.bento-surveiller, a.bento-sous-lien)[href='%s']" % lien)

    def chiffre(self, page, lien):
        return int(self.tuile(page, lien).locator(".chiffre").first.inner_text())

    def test_chiffres_egaux_aux_listes_et_liens(self):
        page = self.ouvrir()
        d = self.donnees(page)
        compteurs = page.locator("#bento .bento-compteur")
        self.assertEqual(compteurs.evaluate_all("l => l.map((a) => a.getAttribute('href'))"),
                         [LIEN_DI, LIEN_RETARD, LIEN_P1, LIEN_PREVENTIFS])
        attendus = {LIEN_DI: len(d["di"]), LIEN_RETARD: len(d["retard"]), LIEN_P1: len(d["p1"]),
                    LIEN_PREVENTIFS: len(d["preventifs"]), LIEN_ARTICLES: d["articles"],
                    LIEN_CONTROLES: d["controles"], LIEN_HABILITATIONS: d["habilitations"],
                    LIEN_RESERVES: len(d["reserves"]), LIEN_SUGGESTIONS: d["suggestions"]}
        for lien, nombre in attendus.items():
            with self.subTest(lien=lien):
                self.assertEqual(self.tuile(page, lien).count(), 1)
                self.assertEqual(self.chiffre(page, lien), nombre)
        securite = sum(1 for x in d["di"] if x["impact"] == "sécurité")
        self.assertIn("dont %d sécurité" % securite, espaces(self.tuile(page, LIEN_DI).inner_text()))
        self.assertEqual(self.tuile(page, LIEN_DI).locator(".comp.rouge").count(), 1)
        # « Contrôles et habilitations » : une tuile, trois liens (réserves en retard depuis la 2.2), le total
        # dans la grosse pastille
        conformite = page.locator("#bento .bento-conformite")
        self.assertEqual(conformite.count(), 1)
        self.assertEqual(int(conformite.locator(".bento-carre .chiffre").inner_text()),
                         d["controles"] + d["habilitations"] + len(d["reserves"]))
        self.assertEqual(conformite.locator("a").evaluate_all("l => l.map((a) => a.getAttribute('href'))"),
                         [LIEN_CONTROLES, LIEN_HABILITATIONS, LIEN_RESERVES])
        # 4 tuiles « à surveiller » (« Garanties et contrats » depuis la 2.2, T485 : test_accueil_v22.py)
        self.assertEqual(page.locator("#bento .bento-surveiller").count(), 4)
        # Listes : 5 au plus, la DI de sécurité d'abord, les OT les plus en retard d'abord ; « Tout voir (N) »
        demandes = page.locator("#bento-demandes li a")
        self.assertEqual(demandes.count(), min(5, len(d["di"])))
        premiere = sorted(d["di"], key=lambda x: (x["impact"] != "sécurité", x["date"]))[0]["id"]
        self.assertEqual(demandes.first.get_attribute("href"), "#/di/" + premiere)
        self.assertEqual(self.texte(page, "#bento-demandes .bento-tout-voir"), "Tout voir (%d)" % len(d["di"]))
        self.assertEqual(page.get_attribute("#bento-demandes .bento-tout-voir", "href"), LIEN_DI)
        retards = page.locator("#bento-retards li a")
        self.assertEqual(retards.count(), min(5, len(d["retard"])))
        plus_ancien = sorted(d["retard"], key=lambda o: o["prevue"])[0]
        self.assertEqual(retards.first.get_attribute("href"), "#/ot/" + plus_ancien["id"])
        self.assertEqual(retards.first.locator(".badge.prio-" + plus_ancien["priorite"].lower()).count(), 1)
        self.assertIn("en retard de", espaces(retards.first.inner_text()))
        self.assertEqual(self.texte(page, "#bento-retards .bento-tout-voir"), "Tout voir (%d)" % len(d["retard"]))
        self.assertEqual(page.get_attribute("#bento-retards .bento-tout-voir", "href"), LIEN_RETARD)
        # Les tuiles mènent aux listes filtrées (adresse relevée au changement : la liste des OT la
        # ramène ensuite à « #/ot » après avoir pris le filtre)
        page.evaluate("""() => { window.__adresses = [];
            window.addEventListener('hashchange', (e) => window.__adresses.push(new URL(e.newURL).hash)); }""")
        for lien in (LIEN_RETARD, LIEN_ARTICLES, LIEN_CONTROLES, LIEN_RESERVES, LIEN_SUGGESTIONS):
            with self.subTest(clic=lien):
                self.tuile(page, lien).click()
                page.wait_for_function("lien => window.__adresses.includes(lien)", arg=lien)
                page.wait_for_function("() => !document.getElementById('bento')")
                page.evaluate(OUVRIR_ACCUEIL_JS)
                page.wait_for_selector("#bento")
        page.click("#bento-synthese a[href='%s']" % LIEN_PLANNING)
        page.wait_for_function("location.hash === '#/planning'")

    def test_chiffres_telephone_listes_et_ordre(self):
        page = self.ouvrir(390, 844, telephone=True)
        # La liste des demandes n'est pas sur l'accueil du téléphone ; l'OT en retard, si
        self.assertFalse(page.is_visible("#bento-demandes"))
        self.assertTrue(page.is_visible("#bento-retards"))
        ordre = page.evaluate("""() => ['bento-synthese', 'bento-premier', 'bento-compteurs-fin', 'bandeau-rapport', 'bento-retards', 'bento-surveiller-debut']
            .map((id) => { const e = id === 'bento-compteurs-fin' ? [...document.querySelectorAll('#bento .bento-compteur')].pop()
              : id === 'bento-surveiller-debut' ? document.querySelector('#bento .bento-surveiller') : document.getElementById(id);
              return e.getBoundingClientRect().top; })""")
        self.assertEqual(ordre, sorted(ordre))
        # 4 compteurs en 2 × 2
        boites = page.locator("#bento .bento-compteur").evaluate_all(
            "l => l.map((e) => { const r = e.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.left)]; })")
        self.assertEqual(len({b[0] for b in boites}), 2)
        self.assertEqual(len({b[1] for b in boites}), 2)
        # L'en-tête mobile dit « Bonjour » et la date ; le bouton du profil est rond
        self.assertEqual(espaces(page.inner_text("#titre-mobile")), "Bonjour Lundi 19 octobre")
        rayon = page.evaluate("getComputedStyle(document.getElementById('btn-profil-mobile')).borderRadius")
        self.assertEqual(rayon, "50%")
        self.assertTrue(page.is_visible("#accueil-demo"))
        # Un autre écran retrouve son titre habituel
        page.evaluate("location.hash = '#/ot'")
        page.wait_for_function("document.getElementById('titre-mobile').textContent === 'Ordres de travail'")


# ---------------------------------------------------------------------------
# reserves
# ---------------------------------------------------------------------------

DETAIL_PAR_DEFAUT = "échéance par défaut passée (30 jours après le contrôle)"
LEVER_TOUTES_JS = """async () => { for (const e of Controles.reservesEnRetard(Donnees.aujourdhui())) {
    await Controles.leverReserve(e.reserve.id, { date: Donnees.aujourdhui(), commentaire: 'Remplacé (test).' }); } }"""


class TestReserves(CasBento):

    def ligne(self, page):
        """Lien « réserves en retard » de la tuile « Contrôles et habilitations » : (chiffre, libellé, détail, ton)."""
        lien = page.locator("#bento .bento-conformite a.bento-sous-lien[href='%s']" % LIEN_RESERVES)
        self.assertEqual(lien.count(), 1)
        detail = lien.locator(".comp")
        return (int(lien.locator(".chiffre").inner_text()), espaces(lien.locator(".bento-sous-texte > span").first.inner_text()),
                espaces(detail.inner_text()), "rouge" if "rouge" in (detail.get_attribute("class") or "").split() else "")

    def total(self, page):
        return int(page.locator("#bento .bento-conformite .bento-carre .chiffre").inner_text())

    def test_reserves_en_retard_de_la_demo_puis_detail_selon_l_echeance(self):
        scenarios = scenarios_demo()
        page = self.ouvrir()
        d = self.donnees(page)
        # La démo : la réserve de RA-01 (relevée le 03/04/2025, ouverte, sans échéance saisie) et elle seule
        self.assertEqual(d["reserves"], [{"id": scenarios["reserve_en_retard"], "parDefaut": True}])
        self.assertEqual(page.evaluate("(id) => Donnees.trouver('equipements', Donnees.trouver('controles_reglementaires', "
                                       "Donnees.trouver('reserves_controle', id).controle_id).equipement_id).repere",
                                       scenarios["reserve_en_retard"]), "RA-01")
        self.assertEqual(self.ligne(page), (1, "réserve en retard", DETAIL_PAR_DEFAUT, "rouge"))
        avant = self.total(page)
        # Échéance saisie, passée : le détail ne parle plus de l'échéance par défaut
        self.modifier_puis_reafficher(page, "async () => Controles.modifierReserve(%s, { echeance_levee: '2026-10-01' })"
                                      % json.dumps(scenarios["reserve_en_retard"]))
        self.assertEqual(self.ligne(page), (1, "réserve en retard", "échéance de levée passée", "rouge"))
        # Une réserve de plus, sans échéance saisie, relevée il y a plus de 30 jours : les deux sortes mêlées
        self.modifier_puis_reafficher(page, """async () => Controles.ajouterReserves(
            Donnees.trouver('reserves_controle', %s).controle_id, { date_controle: '2026-01-05', texte: 'Manomètre à remplacer.' })"""
                                      % json.dumps(scenarios["reserve_en_retard"]))
        self.assertEqual(self.ligne(page),
                         (2, "réserves en retard", "dont 1 à l'échéance par défaut (30 jours après le contrôle)", "rouge"))
        self.assertEqual(self.total(page), avant + 1)
        # Toutes levées : zéro, détail neutre ; le lien reste
        self.modifier_puis_reafficher(page, LEVER_TOUTES_JS)
        self.assertEqual(self.ligne(page), (0, "réserve en retard", "aucune échéance de levée passée", ""))
        self.assertEqual(self.total(page), avant - 1)
        self.assertEqual(self.donnees(page)["reserves"], [])

    def test_reserves_lien_vers_la_liste_filtree(self):
        page = self.ouvrir()
        page.click("#bento .bento-conformite a[href='%s']" % LIEN_RESERVES)
        page.wait_for_function("() => !document.getElementById('bento')")
        page.wait_for_function("() => document.querySelector('#controles-statut') && "
                               "document.querySelector('#controles-statut').value === 'reserves-en-retard'")
        # La liste ne montre que les contrôles qui ont une réserve en retard : celui de RA-01 (pas celui de CH-01,
        # en retard lui-même mais sans réserve)
        liste = page.inner_text("#contenu .controles-liste")
        self.assertIn("RA-01", liste)
        self.assertNotIn("CH-01", liste)

    def test_reserves_indicateur_du_technicien(self):
        page = self.ouvrir(profil="technicien", technicien_id="TEC-0002")
        indicateurs = page.locator("#contenu .accueil-instruments-technicien > a")
        self.assertEqual(indicateurs.evaluate_all("l => l.map((a) => a.getAttribute('href'))"),
                         [LIEN_CONTROLES, LIEN_HABILITATIONS, LIEN_RESERVES])
        reserves = indicateurs.nth(2)
        self.assertEqual(espaces(reserves.locator(".lib").inner_text()), "Réserves en retard")
        self.assertEqual(int(reserves.locator(".chiffre").inner_text()), 1)
        self.assertEqual(espaces(reserves.locator(".comp").inner_text()), DETAIL_PAR_DEFAUT)
        self.assertIn("rouge", reserves.get_attribute("class").split())


# ---------------------------------------------------------------------------
# rapport
# ---------------------------------------------------------------------------

class TestRapport(CasBento):

    def largeurs(self, page):
        return page.evaluate("""() => ({ compteurs: [...document.querySelectorAll('#bento .bento-compteur')].map((e) => {
            const r = e.getBoundingClientRect(); return [r.top, r.width]; }),
            grille: document.getElementById('bento').getBoundingClientRect().width,
            rapport: document.getElementById('bandeau-rapport') ? document.getElementById('bandeau-rapport').getBoundingClientRect().width : 0 })""")

    def test_rapport_plus_tard_puis_figer_la_ligne_des_compteurs_s_etend(self):
        page = self.ouvrir()
        tuile = page.locator("#bento #bandeau-rapport")
        self.assertEqual(tuile.count(), 1)
        self.assertIn("Rapport de septembre", espaces(tuile.inner_text()))
        self.assertIn("septembre 2026", espaces(tuile.inner_text()))
        avant = self.largeurs(page)
        self.assertEqual(len({round(t) for t, _ in avant["compteurs"]}), 1, "4 compteurs sur une ligne")
        self.assertAlmostEqual(avant["rapport"], 2 * avant["compteurs"][0][1] + 16, delta=2)
        # « Plus tard » : la tuile part, rien n'est écrit, les compteurs prennent la ligne
        page.click('#bandeau-rapport [data-action="rapport-plus-tard"]')
        self.assertEqual(page.locator("#bandeau-rapport").count(), 0)
        apres = self.largeurs(page)
        self.assertGreater(apres["compteurs"][0][1], avant["compteurs"][0][1] + 40)
        self.assertAlmostEqual(sum(l for _, l in apres["compteurs"]) + 3 * 16, apres["grille"], delta=2)
        page.evaluate("App.reafficher()")
        page.wait_for_selector("#bento")
        self.assertEqual(page.locator("#bandeau-rapport").count(), 0)
        self.assertEqual(page.evaluate("App.adaptateur.documentsEnMemoire().length"), 0)

        # Autre ouverture : « Figer » écrit le rapport ; le mois est figé, la tuile ne revient pas
        page = self.ouvrir()
        page.click('#bandeau-rapport [data-action="figer-rapport"]')
        page.wait_for_function("App.adaptateur.documentsEnMemoire().some((d) => d.nom === 'rapport-mensuel-2026-09.html')")
        page.wait_for_function("!document.getElementById('bandeau-rapport') && document.getElementById('bento')")
        self.assertIsNone(page.evaluate("Rapport.moisAProposer(Donnees.aujourdhui())"))
        fige = self.largeurs(page)
        self.assertAlmostEqual(sum(l for _, l in fige["compteurs"]) + 3 * 16, fige["grille"], delta=2)


# ---------------------------------------------------------------------------
# mouvements
# ---------------------------------------------------------------------------

class TestMouvements(CasBento):

    def test_mouvements_coupes_avec_reduced_motion_chiffres_tout_de_suite(self):
        page = self.ouvrir(mouvement="reduce")
        actives = page.evaluate("""() => document.getAnimations().map((a) => (a.animationName || a.transitionProperty || 'animation')
            + ' sur ' + (a.effect && a.effect.target ? a.effect.target.className : '?'))""")
        self.assertEqual(actives, [])
        for chiffre in page.evaluate(CHIFFRES_JS):
            self.assertEqual(chiffre["compte"], chiffre["texte"], chiffre)
        styles = page.evaluate("""() => [...document.querySelectorAll('#bento, #bento *, .barre-bas, .menu a, #toast')].filter((e) => {
            const s = getComputedStyle(e); const b = getComputedStyle(e, '::before'); const a = getComputedStyle(e, '::after');
            return [s, b, a].some((x) => x.animationName !== 'none' || x.transitionDuration.split(',').some((d) => parseFloat(d) > 0)); })
            .map((e) => e.tagName + '.' + e.className)""")
        self.assertEqual(styles, [])
        page.hover("#bento .bento-compteur")
        page.wait_for_timeout(350)
        self.assertEqual(page.eval_on_selector("#bento .bento-compteur", "e => getComputedStyle(e).transform"), "none")

    def test_mouvements_sans_preference_chiffres_qui_arrivent_a_leur_valeur_et_tuiles_qui_se_soulevent(self):
        page = self.ouvrir(mouvement="no-preference")
        noms = page.evaluate("() => document.getAnimations().map((a) => a.animationName).filter(Boolean)")
        nombre = page.locator("#bento .chiffre").count()
        self.assertGreaterEqual(nombre, 9)
        self.assertGreaterEqual(noms.count("bento-compter"), nombre)
        self.assertGreaterEqual(len([n for n in noms if n.startswith("bento-derive")]), 2, noms)
        self.assertGreaterEqual(len([n for n in noms if n == "bento-pouls"]), 2, noms)
        page.evaluate("""() => Promise.all(document.getAnimations().filter((a) => a.animationName === 'bento-compter')
            .map((a) => a.finished))""")
        for chiffre in page.evaluate(CHIFFRES_JS):
            self.assertEqual(chiffre["compte"], chiffre["texte"], chiffre)
        page.hover("#bento .bento-compteur")
        page.wait_for_function("() => getComputedStyle(document.querySelector('#bento .bento-compteur')).transform === 'matrix(1, 0, 0, 1, 0, -4)'")
        # Un réaffichage (données changées ailleurs) ne refait pas défiler les chiffres
        page.mouse.move(5, 5)
        page.evaluate("App.reafficher()")
        page.wait_for_selector("#bento")
        self.assertEqual(page.evaluate("() => document.getAnimations().filter((a) => a.animationName === 'bento-compter').length"), 0)


# ---------------------------------------------------------------------------
# jetons
# ---------------------------------------------------------------------------

class TestJetons(CasBento):

    def test_jetons_du_brief_dans_les_deux_themes_et_utilises(self):
        page = self.ouvrir()
        for theme in ("clair", "sombre"):
            with self.subTest(theme=theme):
                page.evaluate("t => { if (t === 'clair') document.documentElement.dataset.theme = 'clair'; else delete document.documentElement.dataset.theme; }", theme)
                valeurs = page.evaluate("""(noms) => Object.fromEntries(noms.map((n) => [n,
                    getComputedStyle(document.documentElement).getPropertyValue(n).replace(/\\s+/g, '').toUpperCase()]))""",
                                        list(JETONS[theme]))
                for nom, attendu in JETONS[theme].items():
                    self.assertEqual(valeurs[nom], attendu.replace(" ", "").upper(), nom)
                styles = page.evaluate("""() => { const s = (q) => getComputedStyle(document.querySelector(q));
                    return { image: s('#bento-synthese').backgroundImage, ombre: s('#bento-synthese').boxShadow,
                             rayonSynthese: s('#bento-synthese').borderTopLeftRadius, rayonPremier: s('#bento-premier').borderTopLeftRadius,
                             rayonTuile: s('#bento .bento-compteur').borderTopLeftRadius, ombreTuile: s('#bento .bento-compteur').boxShadow,
                             couleur: s('#bento-phrase').color }; }""")
                self.assertIn("linear-gradient(135deg, rgb(47, 91, 234) 0%, rgb(61, 107, 242) 55%, rgb(31, 169, 214) 130%)", styles["image"])
                self.assertNotEqual(styles["ombre"], "none")
                self.assertEqual((styles["rayonSynthese"], styles["rayonPremier"], styles["rayonTuile"]), ("28px", "28px", "24px"))
                self.assertEqual(styles["ombreTuile"] == "none", theme == "sombre", styles["ombreTuile"])
                self.assertEqual(styles["couleur"], "rgb(255, 255, 255)")
                # Menu : élément actif en fond bleu doux, texte bleu, 700 ; éléments de 44 px
                menu = page.evaluate("""() => { const a = document.querySelector('#menu a.actif'); const s = getComputedStyle(a);
                    const sonde = document.createElement('i'); document.body.appendChild(sonde);
                    const lire = (v, p) => { sonde.style[p] = 'var(' + v + ')'; return getComputedStyle(sonde)[p]; };
                    const r = { fond: s.backgroundColor, texte: s.color, graisse: s.fontWeight,
                      fondAttendu: lire('--teinte-bleu', 'backgroundColor'), texteAttendu: lire('--texte-bleu', 'color'),
                      hauteurs: [...document.querySelectorAll('#menu a')].map((e) => e.getBoundingClientRect().height) };
                    sonde.remove(); return r; }""")
                self.assertEqual((menu["fond"], menu["texte"], menu["graisse"]), (menu["fondAttendu"], menu["texteAttendu"], "700"))
                self.assertEqual(set(round(h) for h in menu["hauteurs"]), {44})
        # Petite carte du profil en bas du menu
        carte = espaces(page.inner_text("#etat-poste"))
        self.assertIn("Responsable · Poste atelier", carte)
        self.assertIn("changer", carte.lower())

    def test_jetons_barre_du_bas_en_verre_depoli(self):
        page = self.ouvrir(390, 844, telephone=True)
        for theme in ("clair", "sombre"):
            with self.subTest(theme=theme):
                page.evaluate("t => { if (t === 'clair') document.documentElement.dataset.theme = 'clair'; else delete document.documentElement.dataset.theme; }", theme)
                barre = page.evaluate("""() => { const s = getComputedStyle(document.getElementById('barre-bas'));
                    const sonde = document.createElement('i'); document.body.appendChild(sonde); sonde.style.backgroundColor = 'var(--fond-barre-verre)';
                    const attendu = getComputedStyle(sonde).backgroundColor; sonde.remove();
                    return { filtre: s.backdropFilter, fond: s.backgroundColor, attendu, rayon: s.borderTopLeftRadius,
                             actif: getComputedStyle(document.querySelector('#barre-bas a.actif')).backgroundColor }; }""")
                self.assertEqual(barre["filtre"], "blur(18px) saturate(1.4)")
                self.assertEqual(barre["fond"], barre["attendu"])
                self.assertEqual(barre["rayon"], "26px")
                self.assertNotEqual(barre["actif"], "rgba(0, 0, 0, 0)")


# ---------------------------------------------------------------------------
# contrastes
# ---------------------------------------------------------------------------

class TestContrastes(CasBento):

    def mesurer_synthese(self, page, echelle):
        """[(texte, taille, graisse, pire ratio)] : pire pixel sous chaque texte de la tuile de synthèse."""
        textes = page.evaluate(BOITES_SYNTHESE_JS)
        page.evaluate(TEXTE_TRANSPARENT_JS, True)
        pires = [float("inf")] * len(textes)
        fractions = [i / 6 for i in range(7)]
        for fraction in fractions:
            if not page.evaluate(HALOS_JS, fraction) and fraction > 0:
                break                                    # pas de dérive (mouvements réduits) : une capture suffit
            png = page.locator("#bento-synthese").screenshot(animations="allow")
            ratios = page.evaluate(PIRE_CONTRASTE_JS, [base64.b64encode(png).decode("ascii"), textes, echelle])
            pires = [min(a, b) for a, b in zip(pires, ratios)]
        page.evaluate(TEXTE_TRANSPARENT_JS, False)
        return [(t["texte"], t["taille"], t["graisse"], round(r, 2)) for t, r in zip(textes, pires)]

    def test_contrastes_textes_affiches_et_blanc_sur_le_degrade_1440_et_390_clair_et_sombre(self):
        # 1440 et 390 px (brief), plus 1100 px : la plus étroite des grilles du PC (phrase jusqu'au bord droit)
        for largeur, hauteur, telephone in ((1440, 900, False), (1100, 800, False), (390, 844, True)):
            for theme in ("clair", "sombre"):
                with self.subTest(largeur=largeur, theme=theme):
                    page = self.ouvrir(largeur, hauteur, telephone=telephone, theme=theme, mouvement="no-preference")
                    page.evaluate("""() => Promise.all(document.getAnimations().filter((a) => a.animationName === 'bento-compter')
                        .map((a) => a.finished))""")
                    page.mouse.move(2, 2)
                    self.assertEqual(page.evaluate(AUDIT_TEXTES_JS, "#app"), [], "%d px, %s" % (largeur, theme))
                    for texte, taille, graisse, ratio in page.evaluate(CHIFFRES_CONTRASTE_JS):
                        grand = taille >= 24 or (taille >= 18.66 and graisse >= 700)
                        self.assertGreaterEqual(ratio, 3.0 if grand else 4.5, "chiffre %s (%.1f px) : %s:1" % (texte, taille, ratio))
                    mesures = self.mesurer_synthese(page, 2 if telephone else 1)
                    self.assertGreaterEqual(len(mesures), 6)
                    echecs = []
                    for texte, taille, graisse, ratio in mesures:
                        grand = taille >= 24 or (taille >= 18.66 and graisse >= 700)
                        sys.stderr.write("\n  [contraste] %d px %s : « %s » %.1f px %d -> %.2f:1 (seuil %s)"
                                         % (largeur, theme, texte[:40], taille, graisse, ratio, "3" if grand else "4,5"))
                        if ratio < (3.0 if grand else 4.5):
                            echecs.append("« %s » (%.1f px, %d) : %.2f:1" % (texte, taille, graisse, ratio))
                    self.assertEqual(echecs, [], "%d px %s" % (largeur, theme))


# ---------------------------------------------------------------------------
# zones
# ---------------------------------------------------------------------------

class TestZones(CasBento):

    def test_zones_cliquables_44_px_et_48_px_au_telephone(self):
        page = self.ouvrir(1440, 900)
        self.assertEqual(page.evaluate(ZONES_JS, 44), [])
        self.assertGreater(page.locator("#bento a, #bento button").count(), 15)
        page = self.ouvrir(390, 844, telephone=True)
        self.assertEqual(page.evaluate(ZONES_JS, 48), [])

    def test_zones_pas_de_defilement_horizontal(self):
        page = self.ouvrir(1440, 900)
        for largeur in (1440, 1280, 1100, 1024, 900, 768, 641):
            with self.subTest(largeur=largeur):
                page.set_viewport_size({"width": largeur, "height": 900})
                page.wait_for_timeout(50)
                self.sans_defilement_horizontal(page, "%d px" % largeur)
        for largeur in (390, 360):
            with self.subTest(largeur=largeur):
                page = self.ouvrir(largeur, 800, telephone=True)
                self.sans_defilement_horizontal(page, "%d px" % largeur)
                # Aucune tuile ne déborde de son contenu (le décor « lueur », débordant et rogné exprès, à part)
                largeurs = page.evaluate("""() => { document.querySelectorAll('.bento-lueur').forEach((e) => { e.style.display = 'none'; });
                    return [...document.querySelectorAll('#bento > *')].map((e) => [e.id || e.className, e.scrollWidth, e.clientWidth]); }""")
                for nom, defile, visible in largeurs:
                    self.assertLessEqual(defile, visible + 1, nom)


# ---------------------------------------------------------------------------
# decor et notification
# ---------------------------------------------------------------------------

class TestDecor(CasBento):

    def test_decor_aria_hidden_entete_de_la_demo_et_bandeau_global(self):
        page = self.ouvrir()
        lueur = page.locator("#bento-synthese .bento-lueur")
        self.assertEqual(lueur.count(), 1)
        self.assertEqual(lueur.get_attribute("aria-hidden"), "true")
        self.assertEqual(lueur.locator(".bento-halo").count(), 2)
        self.assertEqual(lueur.locator("a, button, [tabindex]").count(), 0)
        self.assertEqual(page.eval_on_selector("#bento-synthese", "e => getComputedStyle(e).overflow"), "hidden")
        # Mention démo et « Exporter en ZIP » dans l'en-tête de l'accueil ; le bandeau global s'efface ici
        self.assertEqual(self.texte(page, "#accueil-demo"), "Démo — rien n'est enregistré")
        self.assertFalse(page.is_visible("#bandeau-demo"))
        with page.expect_download() as attente:
            page.click("#btn-export-accueil")
        self.assertRegex(attente.value.suggested_filename, r"^prevo-export-2026-10-19\.zip$")
        # … et revient tel quel sur les autres écrans
        page.evaluate("location.hash = '#/ot'")
        page.wait_for_selector(".ot-liste-tableau, .ot-liste-cartes")
        self.assertTrue(page.is_visible("#bandeau-demo"))

    def test_notification_role_status_bulle_courte_et_pas_de_toast_a_l_ouverture_de_la_demo(self):
        page = self.ouvrir()
        page.wait_for_timeout(600)
        self.assertEqual([t for t in page.evaluate("window.__toasts") if "préventif" in t], [])
        # La génération a bien eu lieu à l'ouverture (seule la notification est retirée en démo)
        self.assertTrue(page.evaluate("""() => Donnees.lignes('ordres_travail').some((o) => o.origine === 'préventif'
            && String(o.date_creation).startsWith('2026-10-19'))"""))
        toast = page.locator("#toast")
        self.assertEqual((toast.get_attribute("role"), toast.get_attribute("aria-live")), ("status", "polite"))
        page.evaluate("UI.toast('Rapport figé : rapport-mensuel-2026-09.html', 'succes')")
        page.wait_for_function("getComputedStyle(document.getElementById('toast')).visibility === 'visible'")
        page.wait_for_timeout(300)
        style = page.evaluate("""() => { const t = document.getElementById('toast'); const s = getComputedStyle(t);
            const avant = getComputedStyle(t, '::before'); const r = t.getBoundingClientRect();
            const sonde = document.createElement('i'); document.body.appendChild(sonde);
            const lire = (v) => { sonde.style.color = 'var(' + v + ')'; return getComputedStyle(sonde).color; };
            const res = { fond: s.backgroundColor, texte: s.color, rayon: parseFloat(s.borderTopLeftRadius), coche: avant.content,
              couleurCoche: avant.color, attendus: { fond: lire('--texte'), texte: lire('--fond'), coche: lire('--toast-coche') },
              droite: innerWidth - r.right, bas: innerHeight - r.bottom, gauche: r.left };
            sonde.remove(); return res; }""")
        self.assertEqual((style["fond"], style["texte"]), (style["attendus"]["fond"], style["attendus"]["texte"]))
        self.assertEqual((style["coche"], style["couleurCoche"]), ('"✓"', style["attendus"]["coche"]))
        self.assertGreaterEqual(style["rayon"], 14)
        self.assertLessEqual(style["droite"], 40)
        self.assertLessEqual(style["bas"], 40)
        self.assertGreater(style["gauche"], 700, "en bas à droite")
        self.assertEqual(espaces(toast.inner_text()), "Rapport figé : rapport-mensuel-2026-09.html")
        # Courte durée
        page.wait_for_function("!document.getElementById('toast').classList.contains('visible')", timeout=3600)

        # Téléphone : au-dessus de la barre du bas
        page = self.ouvrir(390, 844, telephone=True)
        page.evaluate("UI.toast('Profil : Responsable.', 'succes')")
        page.wait_for_function("getComputedStyle(document.getElementById('toast')).visibility === 'visible'")
        page.wait_for_timeout(300)
        bas_toast, haut_barre = page.evaluate("""() => [document.getElementById('toast').getBoundingClientRect().bottom,
            document.getElementById('barre-bas').getBoundingClientRect().top]""")
        self.assertLessEqual(bas_toast, haut_barre)
        self.assertGreater(bas_toast, haut_barre - 40)


# ---------------------------------------------------------------------------
# autres
# ---------------------------------------------------------------------------

class TestAutres(CasBento):

    def test_accueils_technicien_et_demandeur_inchanges(self):
        for profil, nom, technicien in (("technicien", "", "TEC-0002"), ("demandeur", "Lucas Perrot", "")):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil=profil, nom=nom, technicien_id=technicien, theme="sombre")
                page.wait_for_selector("#contenu h1")
                page.wait_for_timeout(300)
                structure = page.evaluate(STRUCTURE_JS)
                self.assertEqual(structure, STRUCTURE_AVANT[profil])
                self.assertEqual(page.locator("#bento, .bento").count(), 0)
                self.assertTrue(page.is_visible("#bandeau-demo"))
                if profil == "technicien":
                    grille = page.eval_on_selector(".accueil-instruments-technicien", """e => ({ colonnes: getComputedStyle(e).gridTemplateColumns.split(' ').length,
                        largeur: getComputedStyle(e).maxWidth, trait: getComputedStyle(e.querySelector('a')).borderTopWidth })""")
                    # Trois indicateurs depuis la 2.2 (réserves en retard, T421) : trois colonnes
                    self.assertEqual(grille, {"colonnes": 3, "largeur": "960px", "trait": "2px"})

    def test_couleurs_seulement_dans_les_variables(self):
        motif_css = re.compile(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(|hsla?\(")
        for chemin in ("css/modules/accueil.css", "css/modules/app.css"):
            with self.subTest(fichier=chemin):
                fautives = []
                for numero, ligne in enumerate((RACINE / chemin).read_text(encoding="utf-8").splitlines(), 1):
                    sans_variables = re.sub(r"--[\w-]+\s*:[^;]*;", "", ligne)
                    if motif_css.search(sans_variables):
                        fautives.append("%d: %s" % (numero, ligne.strip()))
                self.assertEqual(fautives, [])
        motif_js = re.compile(r"(?<![\w/&-])#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?(?:[0-9A-Fa-f]{2})?\b(?![\w-])|rgba?\(|hsla?\(")
        for chemin in sorted((RACINE / "js" / "modules").glob("accueil*.js")) + [RACINE / "js" / "modules" / "rapport-ecrans.js"]:
            with self.subTest(fichier=chemin.name):
                fautives = ["%d: %s" % (numero, ligne.strip())
                            for numero, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1)
                            if motif_js.search(ligne)]
                self.assertEqual(fautives, [])
        self.assertTrue((RACINE / "js" / "modules" / "accueil-bento.js").is_file())


if __name__ == "__main__":
    unittest.main()
