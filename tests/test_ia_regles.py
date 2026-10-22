"""Règles et encadré de l'assistant IA (lot 4, ARCHITECTURE.md §17.3 et §17.4 ; tâche T66).

Toujours avec le faux fournisseur (tests/faux_fournisseur_ia.py), jamais un vrai modèle :
    - règles pures (scripts chargés dans une page vide) : portée des adresses, mention, réglages du
      poste, validations (codes, impact, check-list, commentaire à jetons), consignes et données
      envoyées par fonction, erreurs nommées ;
    - appel direct (index.html en file://, démo) : Ollama et API compatible OpenAI avec clé, données
      envoyées par fonction (aucun nom de technicien ni de demandeur), repli json_object, délai,
      annulation, réponse illisible, code inventé, chiffre en clair, aucune requête quand l'IA est
      inactive, fournisseur en ligne refusé puis autorisé par le responsable ;
    - relais du serveur (mode serveur, /api/ia) : Ollama, API compatible OpenAI avec clé (jamais dans
      les CSV, le journal, la console du serveur ni celle du navigateur), repli, délai, aucune requête
      sans IA ;
    - encadré : bouton, progression, Annuler, Utiliser / Modifier / Ignorer, boutons propres, erreur,
      un seul encadré par élément, mention permanente dans la coque (ordinateur et téléphone).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_ia_regles.py" -v
"""
import csv
import json
import re
import sys
import time
import unittest

from commun import (RACINE, CasNavigateur, ServeurPrevo, attendre_pret, charger_scripts,
                    preregler_profil, url_fichier)
from faux_fournisseur_ia import FauxFournisseur

CLE = "sk-test-cle-ia-prevo-5f3a9c"
SCRIPTS_REGLES = ["js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/interface.js",
                  "js/modules/ia.js", "js/modules/ia-prompts.js", "js/modules/ia-encadre.js"]
FONCTIONS = ["reformulerDI", "compteRendu", "codes", "checkList", "commentaireRapport"]
# Valeurs « interdites » glissées dans les données passées à Ia.demander : elles ne doivent jamais partir.
MARQUEURS_INTERDITS = ["77.77", "987.65", "photo-secrete.jpg", "notice-secrete.pdf"]
ERREUR_400 = re.compile(r"Failed to load resource: the server responded with a status of 400")
ERREUR_504 = re.compile(r"Failed to load resource: the server responded with a status of 504")
REFUS_DISTANT = "Le responsable n'a pas autorisé les fournisseurs en ligne"


def noms_de_la_demo():
    """Noms des techniciens (« Prénom Nom » et nom) et des demandeurs du jeu de démo."""
    noms = set()
    dossier = RACINE / "donnees" / "demo"
    with open(dossier / "techniciens.csv", encoding="utf-8-sig", newline="") as fichier:
        for ligne in csv.DictReader(fichier, delimiter=";"):
            noms.update({ligne["prenom"] + " " + ligne["nom"], ligne["nom"]})
    with open(dossier / "demandes.csv", encoding="utf-8-sig", newline="") as fichier:
        noms.update(ligne["demandeur"] for ligne in csv.DictReader(fichier, delimiter=";"))
    noms.discard("")
    return sorted(noms)


def taire_coupures(faux):
    """Le navigateur abandonne exprès des requêtes (délai dépassé, « Annuler ») : le faux fournisseur,
    qui répond ensuite à une connexion fermée, ne l'écrit plus en console. Toute autre erreur du faux
    fournisseur reste affichée (son fichier n'est pas modifié : seul son serveur lancé est réglé)."""
    serveur = faux._serveur
    gestion_d_origine = serveur.handle_error

    def gerer_erreur(requete, adresse):
        if isinstance(sys.exc_info()[1], (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return
        gestion_d_origine(requete, adresse)
    serveur.handle_error = gerer_erreur


def regler_ia(contexte, **reglages):
    """Mémorise les réglages IA du poste (localStorage prevo.ia) avant tout chargement de page.
    N'écrase pas une valeur déjà présente (un test peut changer les réglages puis recharger)."""
    valeur = dict(actif=True, fournisseur="ollama", modele="faux", cle="", delaiS=30)
    valeur.update(reglages)
    contexte.add_init_script(
        "(() => { try { if (localStorage.getItem('prevo.ia') === null) "
        "localStorage.setItem('prevo.ia', %s); } catch (erreur) { /* about:blank */ } })();"
        % json.dumps(json.dumps(valeur)))


# Contenu texte des 24 fichiers en mémoire (Donnees.instantane() rend des octets).
FICHIERS_JS = """() => Object.fromEntries(Object.entries(Donnees.instantane())
  .map(([nom, octets]) => [nom, new TextDecoder().decode(octets)]))"""


def contenu_envoye(corps):
    """Texte des messages envoyés au fournisseur (système puis utilisateur)."""
    return "\n".join(str(message.get("content", "")) for message in (corps or {}).get("messages", []))


# Lance Ia.demander dans la page ; rend la réponse ou l'erreur nommée (jamais d'exception JS).
DEMANDER_JS = """async ([fonction, donnees, options]) => {
  const reglages = options || {};
  const controleur = new AbortController();
  if (reglages.annulerApresMs) setTimeout(() => controleur.abort(), reglages.annulerApresMs);
  const debut = Date.now();
  try {
    const reponse = await Ia.demander(fonction, donnees, { signal: controleur.signal });
    return { ok: true, resultat: reponse.resultat, modele: reponse.modele, fournisseur: reponse.fournisseur,
             duree: Date.now() - debut };
  } catch (erreur) {
    return { ok: false, nom: erreur.name, message: erreur.message, ia: erreur instanceof Ia.ErreurIa,
             duree: Date.now() - debut };
  }
}"""

# Données de chaque fonction tirées du jeu de démo, PLUS des champs interdits (noms, taux, coûts,
# photo, document) : seules les données du tableau du §17.3 doivent partir.
DONNEES_DEMO_JS = """() => {
  const ot = Donnees.lignes('ordres_travail').find((o) => o.di_id && o.compte_rendu && o.technicien_id && o.titre);
  const di = Donnees.trouver('demandes', ot.di_id);
  const eq = Donnees.trouver('equipements', ot.equipement_id);
  const tech = Donnees.trouver('techniciens', ot.technicien_id);
  const interdits = { demandeur: di.demandeur, technicien: tech.prenom + ' ' + tech.nom, technicien_id: ot.technicien_id,
    nom: tech.nom, taux_horaire: '77.77', cout: '987.65', cout_soustraitance: '987.65',
    photo: 'photo-secrete.jpg', document: 'notice-secrete.pdf' };
  const avec = (objet) => Object.assign({}, interdits, objet);
  const sorties = Donnees.lignes('mouvements_stock').filter((m) => m.type === 'sortie').slice(0, 2);
  const pieces = sorties.map((m) => ({ designation: (Donnees.trouver('articles', m.article_id) || {}).designation || 'Pièce',
    quantite: m.quantite, prix_unitaire: '987.65', utilisateur: tech.prenom + ' ' + tech.nom }));
  const gamme = Donnees.lignes('gammes').find((g) => g.equipement_id && g.libelle && g.declencheur === 'date');
  const eqGamme = Donnees.trouver('equipements', gamme.equipement_id);
  return {
    otId: ot.id,
    donnees: {
      reformulerDI: avec({ symptome: di.symptome, description: di.description, repere: eq.repere, designation: eq.designation }),
      compteRendu: avec({ notes: ot.compte_rendu, titre: ot.titre, type: ot.type, repere: eq.repere, designation: eq.designation, pieces }),
      codes: avec({ compteRendu: ot.compte_rendu, titre: ot.titre, symptomeDI: di.symptome }),
      checkList: avec({ designation: eqGamme.designation, marque: eqGamme.marque, modele: eqGamme.modele, libelle: gamme.libelle,
        declencheur: gamme.declencheur, periodicite: gamme.periodicite_jours + ' jours', causeVisee: 'Garniture usée' }),
      commentaireRapport: avec({ mois: 'septembre 2026', jetons: { disponibilite: '92,5 %', cout_du_mois: '12 340 €' },
        points: ['Pompe de relevage : coût élevé à examiner'] }),
    },
    attendus: {
      reformulerDI: [di.symptome, eq.repere, eq.designation, 'sécurité'],
      compteRendu: [ot.titre, eq.designation, pieces.length ? pieces[0].designation : ot.titre],
      codes: [ot.titre, di.symptome, 'S01', 'C01', 'R01'],
      checkList: [gamme.libelle, eqGamme.designation, 'Garniture usée'],
      commentaireRapport: ['{disponibilite}', '92,5 %', 'Pompe de relevage : coût élevé à examiner'],
    },
  };
}"""

# Ouvre un encadré après un paragraphe de test (#ancre-ia) ; l'issue est notée dans window.__issue.
ENCADRE_JS = """([fonction, donnees, boutonsPropres]) => {
  let ancre = document.getElementById('ancre-ia');
  if (!ancre) {
    ancre = document.createElement('p');
    ancre.id = 'ancre-ia';
    ancre.textContent = 'Champ de test';
    document.getElementById('contenu').prepend(ancre);
  }
  window.__appels = [];
  window.__issue = null;
  const options = { apres: ancre, fonction, donnees,
    utiliser: (resultat) => { window.__appels.push(['utiliser', resultat]); },
    modifier: (resultat) => { window.__appels.push(['modifier', resultat]); } };
  if (boutonsPropres) {
    options.boutons = [{ libelle: 'Ajouter les opérations cochées', valeur: 'ajouter',
      action: (resultat) => { window.__appels.push(['ajouter', resultat]); } }];
  }
  Ia.ouvrirEncadre(options).then((issue) => {
    window.__issue = { choix: issue.choix, erreur: issue.erreur ? issue.erreur.name : null,
                       resultat: issue.resultat || null, modele: issue.modele || null };
  });
}"""


# ---------------------------------------------------------------------------
# Règles pures
# ---------------------------------------------------------------------------

class TestReglesPures(CasNavigateur):
    """Fonctions sans réseau, scripts chargés dans une page vide (file://, sans App ni données)."""

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS_REGLES)

    def test_portee_de_chaque_adresse(self):
        cas = [
            ("http://localhost:11434", "demo", "poste"),
            ("http://localhost:11434", "dossier", "poste"),
            ("http://localhost:11434", "serveur", "pc-atelier"),
            # « *.localhost » : boucle locale pour le navigateur, mais pas sûre pour le relais Python (même
            # règle que fournisseur_distant de serveur.py : refusé sans l'accord du responsable)
            ("http://ia.localhost:11434", "demo", "poste"),
            ("http://ia.localhost:11434", "serveur", "distant"),
            ("http://127.0.0.1:1234/v1", "demo", "poste"),
            ("http://127.0.0.1:1234/v1", "serveur", "pc-atelier"),
            ("http://127.8.9.10:11434", "dossier", "poste"),
            ("http://[::1]:11434", "dossier", "poste"),
            ("http://[::1]:11434", "serveur", "pc-atelier"),
            ("http://192.168.1.20:11434", "demo", "atelier"),
            ("http://192.168.1.20:11434", "serveur", "atelier"),
            ("http://10.0.0.5:11434", "demo", "atelier"),
            ("http://172.16.4.2:1234/v1", "demo", "atelier"),
            ("http://172.31.255.1:1234/v1", "demo", "atelier"),
            ("http://172.32.0.1:1234/v1", "demo", "distant"),
            ("http://192.169.1.20:11434", "demo", "distant"),
            ("http://pc-atelier.local:11434", "demo", "atelier"),
            ("http://[fd12:3456::1]:11434", "demo", "atelier"),
            ("http://[fc00::7]:11434", "serveur", "atelier"),
            ("http://[2001:db8::1]:11434", "demo", "distant"),
            ("https://api.mistral.ai/v1", "demo", "distant"),
            ("https://api.groq.com/openai/v1", "serveur", "distant"),
            ("https://api.openai.com/v1", "dossier", "distant"),
            ("http://localhost.exemple.com:11434", "demo", "distant"),
            ("pas une adresse", "demo", "distant"),
            ("ftp://localhost:11434", "demo", "distant"),
        ]
        resultats = self.page.evaluate("(cas) => cas.map(([url, mode]) => Ia.portee(url, mode))", [c[:2] for c in cas])
        for (url, mode, attendu), obtenu in zip(cas, resultats):
            with self.subTest(url=url, mode=mode):
                self.assertEqual(obtenu, attendu)
        # Sans mode donné : celui de l'application (ici aucune : appel direct, donc « poste »)
        self.assertEqual(self.page.evaluate("Ia.portee('http://localhost:11434')"), "poste")

    def test_mention_de_chaque_portee(self):
        mentions = self.page.evaluate("""() => [
          Ia.mention('poste', 'http://localhost:11434'),
          Ia.mention('pc-atelier', 'http://localhost:11434'),
          Ia.mention('atelier', 'http://192.168.1.20:11434'),
          Ia.mention('distant', 'https://api.mistral.ai/v1'),
          Ia.mention('distant', 'https://api.groq.com/openai/v1'),
          Ia.mention(),
        ]""")
        self.assertEqual(mentions, ["reste sur ce PC", "reste sur le PC atelier", "reste dans l'atelier",
                                    "données envoyées à api.mistral.ai", "données envoyées à api.groq.com",
                                    "reste sur ce PC"])

    def test_reglages_par_defaut_lecture_protegee_et_enregistrement(self):
        resultat = self.page.evaluate("""() => {
          localStorage.removeItem('prevo.ia');
          const defauts = Ia.reglages();
          const etatSansIa = Ia.etat();
          const activeSansIa = Ia.active();
          localStorage.setItem('prevo.ia', '{pas du json');
          const abimes = Ia.reglages();
          localStorage.removeItem('prevo.ia');
          const enregistres = Ia.enregistrerReglages({ actif: true, url: 'http://localhost:11434', modele: 'mistral:7b', delaiS: 9999 });
          const brut = JSON.parse(localStorage.getItem('prevo.ia'));
          const partiels = Ia.enregistrerReglages({ modele: 'qwen2.5:7b', delaiS: 0.2 });
          return { defauts, etatSansIa, activeSansIa, abimes, enregistres, brut, partiels, relus: Ia.reglages(),
                   active: Ia.active(), cles: Object.keys(localStorage), session: Object.keys(sessionStorage) };
        }""")
        defauts = {"actif": False, "fournisseur": "ollama", "url": "http://localhost:11434",
                   "modele": "qwen2.5:7b", "cle": "", "delaiS": 120}
        self.assertEqual(resultat["defauts"], defauts)
        self.assertEqual(resultat["abimes"], defauts)
        self.assertEqual((resultat["etatSansIa"], resultat["activeSansIa"]), ("inconnu", False))
        self.assertEqual(resultat["enregistres"]["delaiS"], 300)          # plafonné comme le relais
        self.assertEqual(resultat["brut"], resultat["enregistres"])
        self.assertEqual(resultat["partiels"], dict(defauts, actif=True, delaiS=1))
        self.assertEqual(resultat["relus"], resultat["partiels"])
        self.assertTrue(resultat["active"])
        self.assertEqual(resultat["cles"], ["prevo.ia"])
        self.assertEqual(resultat["session"], [])

    def test_fournisseur_en_ligne_refuse_sans_autorisation(self):
        resultat = self.page.evaluate("""() => {
          localStorage.setItem('prevo.ia', JSON.stringify({ actif: true, fournisseur: 'openai',
            url: 'https://api.mistral.ai/v1', modele: 'mistral-small-latest', cle: 'x' }));
          let refus = null;
          try { Ia.enregistrerReglages({ actif: true }); } catch (erreur) { refus = { nom: erreur.name, message: erreur.message }; }
          return { autorise: Ia.distantAutorise(), active: Ia.active(), refus };
        }""")
        self.assertFalse(resultat["autorise"])
        self.assertFalse(resultat["active"])
        self.assertEqual(resultat["refus"]["nom"], "IaRefusee")
        self.assertIn(REFUS_DISTANT, resultat["refus"]["message"])

    def test_erreurs_nommees_en_francais(self):
        erreurs = self.page.evaluate("""() => ['IaIndisponible', 'IaDelai', 'IaAnnulee', 'IaReponseInvalide', 'IaRefusee']
          .map((nom) => { const e = new Ia[nom](); return { nom, name: e.name, message: e.message,
            erreur: e instanceof Error, ia: e instanceof Ia.ErreurIa }; })""")
        for erreur in erreurs:
            with self.subTest(erreur=erreur["nom"]):
                self.assertEqual(erreur["name"], erreur["nom"])
                self.assertTrue(erreur["erreur"] and erreur["ia"])
                self.assertRegex(erreur["message"], r"[a-zé]{3,}.*[a-zé]{3,}")
        self.assertIn(REFUS_DISTANT, erreurs[-1]["message"])

    def test_validation_des_codes(self):
        resultat = self.page.evaluate("""() => {
          const lignes = [
            { famille: 'symptôme', code: 'S01', libelle: 'Fuite' }, { famille: 'symptôme', code: 'S02', libelle: 'Bruit' },
            { famille: 'cause', code: 'C01', libelle: 'Garniture usée' }, { famille: 'cause', code: 'C02', libelle: 'Roulement' },
            { famille: 'remède', code: 'R01', libelle: 'Remplacement' },
          ];
          return {
            justes: Ia.valider.codes({ symptome: 'S02', cause: 'C01', remede: 'R01' }, lignes),
            invente: Ia.valider.codes({ symptome: 'S01', cause: 'C42', remede: 'R01' }, lignes),
            autreFamille: Ia.valider.codes({ symptome: 'C01', cause: 'R01', remede: 'S01' }, lignes),
            vides: Ia.valider.codes({ symptome: '', cause: null }, lignes),
            pasObjet: Ia.valider.codes('S01', lignes),
          };
        }""")
        self.assertEqual(resultat["justes"], {"symptome": "S02", "cause": "C01", "remede": "R01", "rejetes": []})
        self.assertEqual(resultat["invente"], {"symptome": "S01", "cause": "", "remede": "R01",
                                               "rejetes": [{"champ": "cause", "code": "C42"}]})
        self.assertEqual(resultat["autreFamille"]["rejetes"], [{"champ": "symptome", "code": "C01"},
                                                               {"champ": "cause", "code": "R01"},
                                                               {"champ": "remede", "code": "S01"}])
        self.assertEqual((resultat["autreFamille"]["symptome"], resultat["autreFamille"]["cause"],
                          resultat["autreFamille"]["remede"]), ("", "", ""))
        self.assertEqual(resultat["vides"], {"symptome": "", "cause": "", "remede": "", "rejetes": []})
        self.assertEqual(resultat["pasObjet"], {"symptome": "", "cause": "", "remede": "", "rejetes": []})

    def test_validation_de_l_impact(self):
        valeurs = self.page.evaluate("""() => ['gêne', 'dégradé', 'arrêt', 'sécurité', ' Dégradé ', 'ARRET',
          'grave', '', null, undefined, 3].map((v) => Ia.valider.impact(v))""")
        self.assertEqual(valeurs, ["gêne", "dégradé", "arrêt", "sécurité", "dégradé", "arrêt", None, None, None, None, None])

    def test_validation_de_la_check_list(self):
        resultat = self.page.evaluate("""() => {
          const op = (i) => ({ operation: 'Contrôler le point ' + i, valeur_attendue: 'Conforme' });
          const vingt = Array.from({ length: 20 }, (_, i) => op(i + 1));
          return {
            vide: Ia.valider.checkList({ operations: [] }),
            vingtEtUne: Ia.valider.checkList({ operations: vingt.concat([op(21)]) }),
            vingt: Ia.valider.checkList({ operations: vingt }),
            texteTropLong: Ia.valider.checkList({ operations: [{ operation: 'x'.repeat(201), valeur_attendue: '' }] }),
            texte200: Ia.valider.checkList({ operations: [{ operation: '  ' + 'x'.repeat(200) + ' ', valeur_attendue: '' }] }),
            valeurTropLongue: Ia.valider.checkList({ operations: [{ operation: 'Contrôler', valeur_attendue: 'v'.repeat(121) }] }),
            operationVide: Ia.valider.checkList({ operations: [{ operation: '  ', valeur_attendue: 'Conforme' }] }),
            sansListe: Ia.valider.checkList({ texte: 'Contrôler' }),
            pasObjet: Ia.valider.checkList(null),
          };
        }""")
        for nom in ("vide", "vingtEtUne", "texteTropLong", "valeurTropLongue", "operationVide", "sansListe", "pasObjet"):
            with self.subTest(cas=nom):
                self.assertFalse(resultat[nom]["ok"])
                self.assertEqual(resultat[nom]["operations"], [])
                self.assertTrue(resultat[nom]["raison"])
        self.assertTrue(resultat["vingt"]["ok"])
        self.assertEqual(len(resultat["vingt"]["operations"]), 20)
        self.assertEqual(resultat["vingt"]["operations"][0], {"operation": "Contrôler le point 1", "valeur_attendue": "Conforme"})
        self.assertTrue(resultat["texte200"]["ok"])
        self.assertEqual(resultat["texte200"]["operations"][0]["operation"], "x" * 200)
        self.assertIn("20", resultat["vingtEtUne"]["raison"])

    def test_validation_du_commentaire_a_jetons(self):
        resultat = self.page.evaluate("""() => {
          const jetons = { disponibilite: '92,5 %', cout_du_mois: '12 340 €', mois: 'septembre 2026' };
          return {
            juste: Ia.valider.commentaire('En {mois}, la disponibilité atteint {disponibilite} ; coût : { cout_du_mois }.', jetons),
            chiffre: Ia.valider.commentaire('La disponibilité atteint 92 % ce mois-ci.', jetons),
            chiffreAvecJetons: Ia.valider.commentaire('Disponibilité {disponibilite}, soit 3 points de mieux.', jetons),
            inconnu: Ia.valider.commentaire('Le MTBF est de {mtbf}.', jetons),
            accolade: Ia.valider.commentaire('La disponibilité {disponibilite progresse.', jetons),
            vide: Ia.valider.commentaire('   ', jetons),
            tropLong: Ia.valider.commentaire('a'.repeat(4001), jetons),
            sansJetons: Ia.valider.commentaire('Mois calme, rien à signaler.', undefined),
          };
        }""")
        self.assertEqual(resultat["juste"], {"ok": True, "raison": "",
                                             "texte": "En septembre 2026, la disponibilité atteint 92,5 % ; coût : 12 340 €."})
        for nom in ("chiffre", "chiffreAvecJetons", "inconnu", "accolade", "vide", "tropLong"):
            with self.subTest(cas=nom):
                self.assertFalse(resultat[nom]["ok"])
                self.assertEqual(resultat[nom]["texte"], "")
                self.assertTrue(resultat[nom]["raison"])
        self.assertIn("92", resultat["chiffre"]["raison"])
        self.assertIn("{mtbf}", resultat["inconnu"]["raison"])
        self.assertEqual(resultat["sansJetons"], {"ok": True, "texte": "Mois calme, rien à signaler.", "raison": ""})

    def test_commentaire_nombres_en_lettres_refuses(self):
        """Relecture du lot 4 (D71 : « tout nombre écrit en clair ») : nombres en lettres refusés ; les mots
        qui en contiennent (septembre, sixième…) et « neuf » (un moteur neuf) restent permis."""
        resultat = self.page.evaluate("""() => {
          const jetons = { disponibilite: '92,5 %' };
          const essai = (texte) => Ia.valider.commentaire(texte, jetons);
          return {
            refuses: ['La disponibilité gagne trois points.', 'Vingt-cinq heures de correctif en plus.',
                      'Le coût baisse de moitié.', 'Deux pannes sur la presse.', 'Plus de mille euros de pièces.']
              .map((t) => [t, essai(t).ok, essai(t).raison]),
            permis: ['En septembre, la disponibilité atteint {disponibilite}.', 'Pompe remplacée par un moteur neuf.',
                     'Le sixième contrôle est fait ; centrale vérifiée.']
              .map((t) => [t, essai(t).ok]),
          };
        }""")
        for texte, ok, raison in resultat["refuses"]:
            with self.subTest(refuse=texte):
                self.assertFalse(ok)
                self.assertIn("lettres", raison)
        for texte, ok in resultat["permis"]:
            with self.subTest(permis=texte):
                self.assertTrue(ok)

    def test_consignes_des_six_fonctions(self):
        consignes = self.page.evaluate("""(fonctions) => fonctions.map((f) => {
          const p = Ia.PROMPTS[f];
          const donnees = { codes: [{ famille: 'symptôme', code: 'S01', libelle: 'Fuite' }, { famille: 'cause', code: 'C01', libelle: 'Garniture usée' },
                                    { famille: 'remède', code: 'R01', libelle: 'Remplacement' }, { famille: 'cause', code: 'C02', libelle: 'Roulement' }],
                            jetons: { disponibilite: '92 %' }, mois: 'septembre 2026' };
          return { f, systeme: p.systeme, utilisateur: p.utilisateur(donnees), schema: p.schema(donnees) };
        })""", FONCTIONS)
        for consigne in consignes:
            with self.subTest(fonction=consigne["f"]):
                self.assertTrue(consigne["systeme"].startswith("Fonction : " + consigne["f"] + "\n"))
                systeme = consigne["systeme"]
                for attendu in ("JSON", "n'invente", "consignation", "sécurité", "bref"):
                    self.assertIn(attendu, systeme)
                self.assertIsInstance(consigne["utilisateur"], str)
                self.assertEqual(consigne["schema"]["type"], "object")
                self.assertFalse(consigne["schema"]["additionalProperties"])
                self.assertEqual(sorted(consigne["schema"]["required"]), sorted(consigne["schema"]["properties"]))
        par_fonction = {c["f"]: c for c in consignes}
        proprietes = par_fonction["codes"]["schema"]["properties"]
        self.assertEqual(proprietes["symptome"]["enum"], ["S01", ""])
        self.assertEqual(proprietes["cause"]["enum"], ["C01", "C02", ""])
        self.assertEqual(proprietes["remede"]["enum"], ["R01", ""])
        self.assertEqual(par_fonction["reformulerDI"]["schema"]["properties"]["impact"]["enum"],
                         ["gêne", "dégradé", "arrêt", "sécurité"])
        self.assertIn("{disponibilite}", par_fonction["commentaireRapport"]["utilisateur"])
        self.assertIn("{mois}", par_fonction["commentaireRapport"]["utilisateur"])
        self.assertRegex(par_fonction["commentaireRapport"]["systeme"], r"(?i)aucun chiffre")

    def test_consignes_n_envoient_que_les_donnees_du_contrat(self):
        textes = self.page.evaluate("""(fonctions) => {
          const interdits = { demandeur: 'Lucie Martin', technicien: 'Julien Moreau', technicien_id: 'TEC-0001',
            taux_horaire: '77.77', cout: '987.65', cout_soustraitance: '987.65', photo: 'photo-secrete.jpg',
            document: 'notice-secrete.pdf', consignes: 'Consigner le sectionneur Q1' };
          const avec = (o) => Object.assign({}, interdits, o);
          const donnees = {
            reformulerDI: avec({ symptome: 'fuite', description: 'ça goutte', repere: 'PO-03', designation: 'Pompe' }),
            compteRendu: avec({ notes: 'garniture changée', titre: 'Fuite', type: 'correctif', repere: 'PO-03', designation: 'Pompe',
              pieces: [avec({ designation: 'Kit garniture', quantite: '1' })] }),
            codes: avec({ compteRendu: 'garniture changée', titre: 'Fuite', symptomeDI: 'fuite', codes: [] }),
            checkList: avec({ designation: 'Pompe', marque: 'KSB', modele: 'Etanorm', libelle: 'Contrôle', declencheur: 'date',
              periodicite: '30 jours', causeVisee: 'Garniture usée' }),
            commentaireRapport: avec({ mois: 'septembre 2026', jetons: { disponibilite: '92 %' }, points: ['Pompe à examiner'] }),
          };
          return fonctions.map((f) => ({ f, texte: Ia.PROMPTS[f].systeme + '\\n' + Ia.PROMPTS[f].utilisateur(donnees[f]) }));
        }""", FONCTIONS)
        for element in textes:
            with self.subTest(fonction=element["f"]):
                for interdit in ["Lucie Martin", "Julien Moreau", "TEC-0001", "Consigner le sectionneur"] + MARQUEURS_INTERDITS:
                    self.assertNotIn(interdit, element["texte"])


# ---------------------------------------------------------------------------
# Appel direct (index.html en file://, démo)
# ---------------------------------------------------------------------------

class CasDemoIa(CasNavigateur):
    """Démo ouverte en file:// ; le faux fournisseur est partagé par la classe (requêtes vidées à chaque test)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur(lenteur_s=3, cle_attendue=CLE)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)
        taire_coupures(cls.faux)

    def setUp(self):
        super().setUp()
        self.faux.requetes.clear()
        self.console = []
        self.page.on("console", lambda message: self.console.append(message.text))
        self.adresses = []
        self.page.on("request", lambda requete: self.adresses.append(requete.url))

    def ouvrir_demo(self, attendre_etat=True):
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        if attendre_etat:
            self.page.wait_for_function("Ia.etat() !== 'inconnu'")
        return self.page

    def demander(self, fonction, donnees, **options):
        return self.page.evaluate(DEMANDER_JS, [fonction, donnees, options or None])

    def attendre(self, condition, delai_s=10):
        fin = time.time() + delai_s
        while time.time() < fin:
            if condition():
                return True
            time.sleep(0.1)
        return condition()


class TestDemanderDirect(CasDemoIa):

    def test_ollama_un_seul_test_a_l_ouverture_et_six_fonctions_conformes(self):
        regler_ia(self.contexte, url=self.faux.url)
        page = self.ouvrir_demo()
        self.assertEqual(page.evaluate("Ia.etat()"), "ok")
        self.assertEqual([(r["methode"], r["chemin"]) for r in self.faux.requetes], [("GET", "/api/tags")])
        page.evaluate("location.hash = '#/ot'")
        page.wait_for_function("location.hash === '#/ot' && document.querySelector('#contenu h1') !== null")
        self.assertEqual(len(self.faux.requetes), 1, "un seul test du fournisseur à l'ouverture")

        jeu = page.evaluate(DONNEES_DEMO_JS)
        noms = noms_de_la_demo()
        attendus = {
            "reformulerDI": {"symptome": "Fuite d'huile sous le vérin de la presse", "impact": "dégradé"},
            "codes": {"symptome": "S01", "cause": "C01", "remede": "R01", "rejetes": []},
        }
        for fonction in FONCTIONS:
            with self.subTest(fonction=fonction):
                avant = len(self.faux.requetes)
                reponse = self.demander(fonction, jeu["donnees"][fonction])
                self.assertTrue(reponse["ok"], reponse)
                self.assertEqual((reponse["modele"], reponse["fournisseur"]), ("faux", "Ollama"))
                if fonction in attendus:
                    self.assertEqual(reponse["resultat"], attendus[fonction])
                requetes = self.faux.requetes[avant:]
                self.assertEqual([(r["methode"], r["chemin"]) for r in requetes], [("POST", "/api/chat")])
                corps = requetes[0]["corps"]
                self.assertEqual((corps["model"], corps["stream"], corps["options"]["temperature"]), ("faux", False, 0.2))
                self.assertEqual(corps["format"]["type"], "object")
                self.assertEqual([m["role"] for m in corps["messages"]], ["system", "user"])
                self.assertTrue(corps["messages"][0]["content"].startswith("Fonction : " + fonction))
                envoye = json.dumps(corps, ensure_ascii=False)
                for interdit in noms + MARQUEURS_INTERDITS:
                    self.assertNotIn(interdit, envoye)
                texte = contenu_envoye(corps)
                for attendu in jeu["attendus"][fonction]:
                    self.assertIn(attendu, texte)
        # Résultats validés : check-list, comptes rendus, commentaire aux jetons remplacés
        self.assertEqual(self.demander("checkList", jeu["donnees"]["checkList"])["resultat"]["operations"][1],
                         {"operation": "Mesurer les vibrations au palier", "valeur_attendue": "< 4,5 mm/s"})
        self.assertIn("Constat", self.demander("compteRendu", jeu["donnees"]["compteRendu"])["resultat"]["texte"])
        commentaire = self.demander("commentaireRapport", jeu["donnees"]["commentaireRapport"])["resultat"]
        self.assertEqual(commentaire["texte"], "La disponibilité du mois s'établit à 92,5 % ; le coût du mois est de 12 340 €.")
        self.assertIn("{disponibilite}", commentaire["texteAJetons"])
        # Schéma des codes : listes fermées construites avec les codes existants de chaque famille
        corps_codes = [r["corps"] for r in self.faux.requetes if r["chemin"] == "/api/chat"
                       and r["corps"]["messages"][0]["content"].startswith("Fonction : codes")][0]
        enum_causes = corps_codes["format"]["properties"]["cause"]["enum"]
        self.assertIn("C01", enum_causes)
        self.assertNotIn("S01", enum_causes)
        self.assertEqual(enum_causes[-1], "")
        # Appel direct : aucune requête vers /api/ia, tout part vers le fournisseur
        self.assertFalse([a for a in self.adresses if "/api/ia" in a])

    def test_openai_direct_cle_transmise_et_jamais_ecrite(self):
        regler_ia(self.contexte, fournisseur="openai", url=self.faux.url + "/v1", cle=CLE)
        page = self.ouvrir_demo()
        self.assertEqual(page.evaluate("Ia.etat()"), "ok")
        self.assertEqual(self.faux.requetes[0]["chemin"], "/v1/models")
        reponse = self.demander("compteRendu", {"notes": "Garniture changée.", "titre": "Fuite garniture"})
        self.assertTrue(reponse["ok"], reponse)
        self.assertIn("garniture", reponse["resultat"]["texte"])
        self.assertEqual(reponse["fournisseur"], "127.0.0.1")
        requete = self.faux.requetes_vers("/v1/chat/completions")[-1]
        self.assertEqual(requete["entetes"]["authorization"], "Bearer " + CLE)
        corps = requete["corps"]
        self.assertEqual(corps["temperature"], 0.2)
        self.assertEqual(corps["response_format"]["type"], "json_schema")
        self.assertEqual(corps["response_format"]["json_schema"]["name"], "compteRendu")
        self.assertTrue(corps["response_format"]["json_schema"]["strict"])
        self.assertNotIn(CLE, json.dumps(corps))
        # Trace d'utilisation (après un enregistrement par l'écran) : journal, sans la clé
        jeu = page.evaluate(DONNEES_DEMO_JS)
        page.evaluate("(id) => Ia.tracerUtilisation('ordres_travail', id, 'compte_rendu', 'faux')", jeu["otId"])
        fichiers = page.evaluate(FICHIERS_JS)
        self.assertEqual(len(fichiers), 24)
        self.assertIn(";ordres_travail;%s;proposition IA utilisée (faux) : compte_rendu" % jeu["otId"], fichiers["journal"])
        for nom, contenu in fichiers.items():
            with self.subTest(fichier=nom):
                self.assertNotIn(CLE, contenu)
        stockage = page.evaluate("""() => ({ session: JSON.stringify(Object.entries(sessionStorage)),
          autres: JSON.stringify(Object.entries(localStorage).filter(([cle]) => cle !== 'prevo.ia')) })""")
        self.assertNotIn(CLE, stockage["session"] + stockage["autres"])
        self.assertFalse([m for m in self.console if CLE in m])

    def test_repli_json_object_si_le_schema_est_refuse(self):
        self.autoriser_erreur(ERREUR_400)      # premier essai refusé par le faux fournisseur (attendu)
        regler_ia(self.contexte, fournisseur="openai", url=self.faux.url + "/v1", cle=CLE, modele="faux-schema")
        self.ouvrir_demo()
        reponse = self.demander("compteRendu", {"notes": "garniture changée"})
        self.assertTrue(reponse["ok"], reponse)
        self.assertIn("Constat", reponse["resultat"]["texte"])
        formats = [r["corps"]["response_format"]["type"] for r in self.faux.requetes_vers("/v1/chat/completions")]
        self.assertEqual(formats, ["json_schema", "json_object"])

    def test_delai_depasse_annulation_et_reponse_illisible(self):
        regler_ia(self.contexte, url=self.faux.url, modele="faux-lent", delaiS=1)
        page = self.ouvrir_demo()
        delai = self.demander("compteRendu", {"notes": "fuite"})
        self.assertEqual((delai["ok"], delai["nom"], delai["ia"]), (False, "IaDelai", True))
        self.assertIn("délai", delai["message"])
        self.assertLess(delai["duree"], 2900)
        page.evaluate("Ia.enregistrerReglages({ delaiS: 30 })")
        annule = self.demander("compteRendu", {"notes": "fuite"}, annulerApresMs=300)
        self.assertEqual((annule["ok"], annule["nom"]), (False, "IaAnnulee"))
        self.assertLess(annule["duree"], 2500)
        page.evaluate("Ia.enregistrerReglages({ modele: 'faux-illisible' })")
        illisible = self.demander("compteRendu", {"notes": "fuite"})
        self.assertEqual((illisible["ok"], illisible["nom"]), (False, "IaReponseInvalide"))
        self.assertTrue(illisible["message"])
        self.assertEqual(page.evaluate("Ia.etat()"), "ok", "un fournisseur lent ou bavard reste joignable")

    def test_code_invente_rejete_et_chiffre_en_clair_refuse(self):
        regler_ia(self.contexte, url=self.faux.url, modele="faux-invente")
        page = self.ouvrir_demo()
        codes = self.demander("codes", {"compteRendu": "garniture changée", "titre": "Fuite"})
        self.assertTrue(codes["ok"], codes)
        self.assertEqual(codes["resultat"], {"symptome": "S01", "cause": "", "remede": "R01",
                                             "rejetes": [{"champ": "cause", "code": "C42"}]})
        page.evaluate("Ia.enregistrerReglages({ modele: 'faux-chiffres' })")
        commentaire = self.demander("commentaireRapport", {"mois": "septembre 2026", "jetons": {"disponibilite": "92 %"}})
        self.assertEqual((commentaire["ok"], commentaire["nom"]), (False, "IaReponseInvalide"))
        self.assertIn("chiffre", commentaire["message"])

    def test_aucune_requete_quand_l_ia_est_inactive(self):
        regler_ia(self.contexte, actif=False, url=self.faux.url)
        page = self.ouvrir_demo(attendre_etat=False)
        time.sleep(1.5)
        page.evaluate("location.hash = '#/di'")
        page.wait_for_function("location.hash === '#/di' && document.querySelector('#contenu h1') !== null")
        time.sleep(0.5)
        self.assertEqual(self.faux.requetes, [])
        self.assertEqual(page.evaluate("[Ia.active(), Ia.etat(), Ia.bouton('Proposer avec l\\'IA', () => {})]"),
                         [False, "inconnu", None])
        self.assertFalse(page.evaluate("Boolean(document.querySelector('#ia-mention:not([hidden])'))"))
        refus = self.demander("compteRendu", {"notes": "fuite"})
        self.assertEqual((refus["ok"], refus["nom"]), (False, "IaIndisponible"))
        self.assertEqual(self.faux.requetes, [])
        self.assertFalse([a for a in self.adresses if a.startswith(self.faux.url)])

    def test_fournisseur_en_ligne_refuse_puis_autorise_par_le_responsable(self):
        appels = []

        def repondre(route):
            requete = route.request
            entetes = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                       "Access-Control-Allow-Headers": "authorization, content-type"}
            if requete.method == "OPTIONS":
                route.fulfill(status=204, headers=entetes)
                return
            appels.append({"methode": requete.method, "url": requete.url, "entetes": requete.headers})
            if requete.url.endswith("/models"):
                corps = {"data": [{"id": "mistral-small-latest"}]}
            else:
                contenu = json.dumps({"texte": "Constat : fuite.\nAction : garniture remplacée."}, ensure_ascii=False)
                corps = {"choices": [{"message": {"role": "assistant", "content": contenu}}]}
            route.fulfill(status=200, headers=dict(entetes, **{"Content-Type": "application/json"}), body=json.dumps(corps))

        # Aucune requête ne quitte le poste : l'adresse en ligne est interceptée par le test.
        self.contexte.route("https://api.mistral.ai/**", repondre)
        regler_ia(self.contexte, fournisseur="openai", url="https://api.mistral.ai/v1", cle=CLE, modele="mistral-small-latest")
        page = self.ouvrir_demo(attendre_etat=False)
        time.sleep(1)
        etat = page.evaluate("""async () => {
          let refusEnregistrement = null;
          try { Ia.enregistrerReglages({ actif: true }); } catch (erreur) { refusEnregistrement = erreur.name; }
          return { active: Ia.active(), etat: Ia.etat(), portee: Ia.portee(Ia.reglages().url), refusEnregistrement,
                   test: await Ia.tester(), mention: Boolean(document.querySelector('#ia-mention:not([hidden])')) };
        }""")
        self.assertEqual((etat["active"], etat["etat"], etat["portee"]), (False, "inconnu", "distant"))
        self.assertEqual(etat["refusEnregistrement"], "IaRefusee")
        self.assertFalse(etat["test"]["ok"])
        self.assertIn(REFUS_DISTANT, etat["test"]["message"])
        self.assertFalse(etat["mention"])
        refus = self.demander("compteRendu", {"notes": "fuite"})
        self.assertEqual((refus["ok"], refus["nom"]), (False, "IaRefusee"))
        self.assertIn(REFUS_DISTANT, refus["message"])
        self.assertEqual(appels, [])

        # Le responsable autorise les fournisseurs en ligne (parametres.csv, réglage partagé)
        page.evaluate("""() => Donnees.modifier('parametres', (lignes) => {
          const ligne = lignes.find((l) => l.cle === 'ia_distant_autorise');
          if (ligne) ligne.valeur = '1'; else lignes.push({ cle: 'ia_distant_autorise', valeur: '1' });
        })""")
        self.assertTrue(page.evaluate("Ia.active()"))
        page.wait_for_selector("#ia-mention.distant", state="visible")
        self.assertEqual(page.inner_text("#ia-mention").strip(), "IA : données envoyées à api.mistral.ai")
        reponse = self.demander("compteRendu", {"notes": "fuite"})
        self.assertTrue(reponse["ok"], reponse)
        self.assertEqual(reponse["fournisseur"], "api.mistral.ai")
        self.assertEqual([a["methode"] for a in appels], ["POST"])
        self.assertTrue(appels[0]["url"].endswith("/v1/chat/completions"))
        self.assertEqual(appels[0]["entetes"]["authorization"], "Bearer " + CLE)

    def test_fournisseur_injoignable_etat_et_boutons_masques(self):
        self.autoriser_erreur("net::ERR_CONNECTION_REFUSED")    # le test d'ouverture échoue (attendu)
        with FauxFournisseur() as eteint:
            adresse = eteint.url
        regler_ia(self.contexte, url=adresse)
        page = self.ouvrir_demo()
        self.assertEqual(page.evaluate("Ia.etat()"), "injoignable")
        self.assertIsNone(page.evaluate("Ia.bouton('Proposer avec l\\'IA', () => {})"))
        self.assertIn("ne répond pas", page.inner_text("#ia-mention"))
        resultat = page.evaluate("Ia.tester()")
        self.assertFalse(resultat["ok"])
        self.assertEqual(resultat["modeles"], [])
        self.assertIn("ne répond pas", resultat["message"])

    def test_cle_jamais_envoyee_a_une_autre_origine(self):
        """Relecture du lot 4 (D66) : la règle est dans ia.js, pas seulement dans « Ce poste » —
        tester ou enregistrer une autre adresse sans clé n'emporte pas la clé enregistrée."""
        self.autoriser_erreur("status of 401")       # sans clé, le faux fournisseur refuse : attendu
        regler_ia(self.contexte, fournisseur="openai", url=self.faux.url + "/v1", cle=CLE, modele="faux")
        page = self.ouvrir_demo()
        self.assertEqual(page.evaluate("Ia.etat()"), "ok")
        autre = self.faux.url.replace("127.0.0.1", "localhost") + "/v1"
        self.faux.requetes.clear()
        page.evaluate("(url) => Ia.tester({ url })", autre)
        self.assertTrue(self.faux.requetes)
        self.assertEqual([r["entetes"].get("authorization") for r in self.faux.requetes], [None] * len(self.faux.requetes))
        page.evaluate("(url) => Ia.enregistrerReglages({ url })", autre)
        self.assertEqual(page.evaluate("Ia.reglages().cle"), "")
        # Même origine : la clé reste (rien n'oblige à la ressaisir)
        page.evaluate("(url) => Ia.enregistrerReglages({ url, cle: 'cle-ressaisie' })", autre)
        page.evaluate("(url) => Ia.enregistrerReglages({ url: url + '/' })", autre)
        self.assertEqual(page.evaluate("Ia.reglages().cle"), "cle-ressaisie")

    def test_fournisseur_en_ligne_qui_refuse_le_navigateur_conseille_le_mode_serveur(self):
        """D66 (ajout de l'orchestrateur) : modes dossier et démo, fournisseur en ligne autorisé mais qui
        refuse les appels d'une page (pas d'en-têtes CORS) → message « passez par le mode serveur »."""
        self.autoriser_erreur(re.compile(r"CORS|Access-Control|ERR_FAILED"))
        # Refus CORS vu par fetch : une TypeError, comme une requête bloquée (une réponse interceptée par
        # Playwright échappe au contrôle CORS) ; aucune requête ne quitte le poste.
        self.contexte.route("https://api.mistral.ai/**", lambda route: route.abort("failed"))
        regler_ia(self.contexte, fournisseur="openai", url="https://api.mistral.ai/v1", cle=CLE, modele="mistral-small-latest")
        page = self.ouvrir_demo(attendre_etat=False)
        page.evaluate("""() => Donnees.modifier('parametres', (lignes) => {
          const ligne = lignes.find((l) => l.cle === 'ia_distant_autorise');
          if (ligne) ligne.valeur = '1'; else lignes.push({ cle: 'ia_distant_autorise', valeur: '1' });
        })""")
        resultat = page.evaluate("Ia.tester()")
        self.assertFalse(resultat["ok"])
        self.assertIn("api.mistral.ai", resultat["message"])
        self.assertIn("passez par le mode serveur", resultat["message"])


# ---------------------------------------------------------------------------
# Relais du serveur (mode serveur, /api/ia)
# ---------------------------------------------------------------------------

class TestDemanderRelais(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.faux = FauxFournisseur(lenteur_s=4, cle_attendue=CLE)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)
        taire_coupures(cls.faux)

    def setUp(self):
        super().setUp()
        self.faux.requetes.clear()
        self.console = []
        self.page.on("console", lambda message: self.console.append(message.text))
        self.adresses = []
        self.page.on("request", lambda requete: self.adresses.append(requete.url))

    def ouvrir(self, attendre_etat=True):
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(self.serveur.url + "/")
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("App.mode"), "serveur")
        if attendre_etat:
            self.page.wait_for_function("Ia.etat() !== 'inconnu'")
        return self.page

    def demander(self, fonction, donnees, **options):
        return self.page.evaluate(DEMANDER_JS, [fonction, donnees, options or None])

    def test_relais_ollama_portee_pc_atelier_et_codes_du_fichier(self):
        regler_ia(self.contexte, url=self.faux.url)
        page = self.ouvrir()
        self.assertEqual(page.evaluate("Ia.etat()"), "ok")
        self.assertEqual(page.evaluate("Ia.portee(Ia.reglages().url)"), "pc-atelier")
        self.assertEqual(page.inner_text("#ia-mention").strip(), "IA : reste sur le PC atelier")
        reponse = self.demander("codes", {"compteRendu": "garniture changée", "titre": "Fuite pompe", "symptomeDI": "fuite"})
        self.assertTrue(reponse["ok"], reponse)
        self.assertEqual(reponse["resultat"], {"symptome": "S01", "cause": "C01", "remede": "R01", "rejetes": []})
        self.assertEqual([r["chemin"] for r in self.faux.requetes], ["/api/tags", "/api/chat"])
        proprietes = self.faux.requetes[-1]["corps"]["format"]["properties"]
        with open(self.serveur.dossier / "codes_defaillance.csv", encoding="utf-8-sig", newline="") as fichier:
            lignes = list(csv.DictReader(fichier, delimiter=";"))
        for champ, famille in (("symptome", "symptôme"), ("cause", "cause"), ("remede", "remède")):
            with self.subTest(champ=champ):
                self.assertEqual(proprietes[champ]["enum"], [l["code"] for l in lignes if l["famille"] == famille] + [""])
        # Mode serveur : tout passe par le relais, rien ne part du navigateur vers le fournisseur
        self.assertFalse([a for a in self.adresses if a.startswith(self.faux.url)])
        self.assertEqual(len([a for a in self.adresses if a == self.serveur.url + "/api/ia"]), 2)

    def test_relais_openai_cle_transmise_jamais_dans_les_fichiers_ni_les_consoles(self):
        regler_ia(self.contexte, fournisseur="openai", url=self.faux.url + "/v1", cle=CLE)
        page = self.ouvrir()
        self.assertEqual(page.evaluate("Ia.etat()"), "ok")
        reponse = self.demander("compteRendu", {"notes": "garniture changée", "titre": "Fuite"})
        self.assertTrue(reponse["ok"], reponse)
        self.assertIn("Constat", reponse["resultat"]["texte"])
        for requete in self.faux.requetes:
            with self.subTest(chemin=requete["chemin"]):
                self.assertEqual(requete["entetes"]["authorization"], "Bearer " + CLE)
        page.evaluate("Ia.tracerUtilisation('ordres_travail', 'OT-2025-0001', 'compte_rendu', 'faux')")
        journal = (self.serveur.dossier / "journal.csv").read_text(encoding="utf-8-sig")
        self.assertIn("proposition IA utilisée (faux) : compte_rendu", journal)
        octets_cle = CLE.encode("utf-8")
        for fichier in sorted(self.serveur.dossier.rglob("*")):
            if fichier.is_file():
                with self.subTest(fichier=fichier.name):
                    self.assertNotIn(octets_cle, fichier.read_bytes())
        self.assertNotIn(CLE, self.serveur.sortie_console())
        self.assertFalse([m for m in self.console if CLE in m])

    def test_relais_repli_json_object_et_delai(self):
        regler_ia(self.contexte, fournisseur="openai", url=self.faux.url + "/v1", cle=CLE, modele="faux-schema")
        page = self.ouvrir()
        reponse = self.demander("compteRendu", {"notes": "fuite"})
        self.assertTrue(reponse["ok"], reponse)
        formats = [r["corps"]["response_format"]["type"] for r in self.faux.requetes_vers("/v1/chat/completions")]
        self.assertEqual(formats, ["json_schema", "json_object"])
        # Délai dépassé : le serveur coupe (504) et l'erreur est nommée IaDelai
        self.autoriser_erreur(ERREUR_504)
        page.evaluate("Ia.enregistrerReglages({ modele: 'faux-lent', delaiS: 1 })")
        delai = self.demander("compteRendu", {"notes": "fuite"})
        self.assertEqual((delai["ok"], delai["nom"]), (False, "IaDelai"))
        self.assertLess(delai["duree"], 3900)

    def test_relais_aucune_requete_quand_l_ia_est_inactive(self):
        regler_ia(self.contexte, actif=False, url=self.faux.url)
        page = self.ouvrir(attendre_etat=False)
        time.sleep(1.5)
        self.assertEqual(self.faux.requetes, [])
        self.assertFalse([a for a in self.adresses if a.endswith("/api/ia")])
        self.assertEqual(page.evaluate("Ia.etat()"), "inconnu")


# ---------------------------------------------------------------------------
# Encadré, bouton et mention de la coque
# ---------------------------------------------------------------------------

class TestEncadre(CasDemoIa):

    def textes_boutons(self):
        return [t.strip() for t in self.page.locator(".ia-encadre .ia-actions button").all_inner_texts()]

    def attendre_issue(self):
        self.page.wait_for_function("window.__issue !== null")
        return self.page.evaluate("window.__issue")

    def test_bouton_et_mention_permanente_dans_la_coque(self):
        regler_ia(self.contexte, url=self.faux.url)
        page = self.ouvrir_demo()
        bouton = page.evaluate("""() => {
          const b = Ia.bouton('Proposer avec l\\'IA', () => { window.__clic = true; });
          document.getElementById('contenu').prepend(b);
          return { classe: b.className, texte: b.textContent.trim(), type: b.type };
        }""")
        self.assertIn("ia-bouton", bouton["classe"])
        self.assertEqual((bouton["texte"], bouton["type"]), ("Proposer avec l'IA", "button"))
        page.click(".ia-bouton")
        self.assertTrue(page.evaluate("window.__clic === true"))
        self.assertTrue(page.is_visible("#ia-mention"))
        self.assertEqual(page.inner_text("#ia-mention").strip(), "IA : reste sur ce PC")
        # La mention suit les réglages : IA désactivée sur le poste → plus de mention ni de bouton
        page.evaluate("Ia.enregistrerReglages({ actif: false })")
        self.assertTrue(page.is_hidden("#ia-mention"))
        self.assertIsNone(page.evaluate("Ia.bouton('Proposer avec l\\'IA', () => {})"))

    def test_progression_puis_annuler(self):
        regler_ia(self.contexte, url=self.faux.url, modele="faux-lent")
        page = self.ouvrir_demo()
        page.evaluate(ENCADRE_JS, ["compteRendu", {"notes": "fuite garniture"}, False])
        page.wait_for_selector("#ancre-ia + .ia-encadre", state="visible")
        self.assertIn("L'IA rédige", page.inner_text(".ia-encadre"))
        self.assertTrue(page.is_visible(".ia-encadre button:has-text('Annuler')"))
        page.click(".ia-encadre button:has-text('Annuler')")
        self.assertEqual(self.attendre_issue()["choix"], "annuler")
        self.assertEqual(page.locator(".ia-encadre").count(), 0)
        self.assertEqual(page.evaluate("window.__appels"), [])

    def test_proposition_utiliser_modifier_ignorer(self):
        regler_ia(self.contexte, url=self.faux.url)
        page = self.ouvrir_demo()
        self.fichiers_avant = page.evaluate(FICHIERS_JS)
        for choix in ("Utiliser", "Modifier", "Ignorer"):
            with self.subTest(choix=choix):
                page.evaluate(ENCADRE_JS, ["compteRendu", {"notes": "fuite garniture"}, False])
                page.wait_for_selector(".ia-encadre .ia-proposition", state="visible")
                texte = page.inner_text(".ia-encadre")
                self.assertIn("Proposition de l'IA — Ollama, faux", texte)
                self.assertIn("Constat : fuite à la garniture mécanique.", texte)
                self.assertEqual(self.textes_boutons(), ["Utiliser", "Modifier", "Ignorer"])
                page.click(".ia-encadre .ia-actions button:has-text('%s')" % choix)
                issue = self.attendre_issue()
                self.assertEqual(issue["choix"], choix.lower())
                self.assertEqual(page.locator(".ia-encadre").count(), 0)
                appels = page.evaluate("window.__appels")
                if choix == "Ignorer":
                    self.assertEqual(appels, [])
                else:
                    self.assertEqual(appels[0][0], choix.lower())
                    self.assertIn("Constat", appels[0][1]["texte"])
                    self.assertIn("Constat", issue["resultat"]["texte"])
                    self.assertEqual(issue["modele"], "faux")
        # L'encadré n'a rien écrit : aucune entrée « proposition IA » au journal, fichiers inchangés
        fichiers = page.evaluate(FICHIERS_JS)
        self.assertIn("ordres_travail", fichiers)
        self.assertNotIn("proposition IA", fichiers["journal"])
        self.assertEqual(fichiers, self.fichiers_avant)

    def test_boutons_propres_un_seul_encadre_et_erreur(self):
        regler_ia(self.contexte, url=self.faux.url)
        page = self.ouvrir_demo()
        page.evaluate(ENCADRE_JS, ["checkList", {"designation": "Pompe"}, True])
        page.wait_for_selector(".ia-encadre .ia-proposition", state="visible")
        self.assertEqual(self.textes_boutons(), ["Ajouter les opérations cochées", "Ignorer"])
        self.assertIn("Contrôler l'absence de fuite à la garniture", page.inner_text(".ia-encadre"))
        page.click(".ia-encadre .ia-actions button:has-text('Ajouter les opérations cochées')")
        self.assertEqual(self.attendre_issue()["choix"], "ajouter")
        self.assertEqual(page.evaluate("window.__appels[0][0]"), "ajouter")
        self.assertEqual(len(page.evaluate("window.__appels[0][1].operations")), 3)

        # Un seul encadré à la fois par élément : le second remplace le premier
        page.evaluate("Ia.enregistrerReglages({ modele: 'faux-lent' })")
        page.evaluate(ENCADRE_JS, ["compteRendu", {"notes": "a"}, False])
        page.evaluate(ENCADRE_JS, ["compteRendu", {"notes": "b"}, False])
        self.assertEqual(page.locator(".ia-encadre").count(), 1)
        page.click(".ia-encadre button:has-text('Annuler')")
        self.attendre_issue()

        # Erreur : message en français dans l'encadré, aucune proposition ni « Utiliser »
        page.evaluate("Ia.enregistrerReglages({ modele: 'faux-illisible' })")
        page.evaluate(ENCADRE_JS, ["compteRendu", {"notes": "fuite"}, False])
        page.wait_for_selector(".ia-encadre .ia-erreur", state="visible")
        issue = self.attendre_issue()
        self.assertEqual((issue["choix"], issue["erreur"]), ("erreur", "IaReponseInvalide"))
        self.assertEqual(page.locator(".ia-encadre .ia-proposition").count(), 0)
        self.assertEqual(page.locator(".ia-encadre button:has-text('Utiliser')").count(), 0)
        self.assertIn("illisible", page.inner_text(".ia-encadre .ia-erreur"))
        page.click(".ia-encadre button:has-text('Fermer')")
        self.assertEqual(page.locator(".ia-encadre").count(), 0)

    def test_telephone_360px_zones_tactiles_et_sans_defilement(self):
        regler_ia(self.contexte, fournisseur="openai", url=self.faux.url + "/v1", cle=CLE)
        self.page.set_viewport_size({"width": 360, "height": 740})
        page = self.ouvrir_demo()
        self.assertTrue(page.is_visible("#ia-mention"))
        page.evaluate("() => document.getElementById('contenu').prepend(Ia.bouton('Rédiger le compte rendu', () => {}))")
        page.evaluate(ENCADRE_JS, ["compteRendu", {"notes": "fuite garniture"}, False])
        page.wait_for_selector(".ia-encadre .ia-proposition", state="visible")
        hauteurs = page.evaluate("""() => [...document.querySelectorAll('.ia-bouton, .ia-encadre button')]
          .map((e) => Math.round(e.getBoundingClientRect().height))""")
        self.assertTrue(hauteurs)
        self.assertGreaterEqual(min(hauteurs), 48)
        largeur = page.evaluate("document.documentElement.scrollWidth")
        self.assertLessEqual(largeur, 360)


if __name__ == "__main__":
    unittest.main()
