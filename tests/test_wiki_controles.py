"""Synthèse du wiki : forme du texte, contrôles et fonction IA syntheseWiki (tâche T97, ARCHITECTURE.md §20.4).

    forme     : puces → texte (rubriques dans l'ordre, citations en fin de puce) → puces, sans perte ;
    contrôles : ligne hors forme, aucune puce, sept puces, plus de 150 mots (citations non comptées), puce
                sans OT, OT hors de ceux permis, vocabulaire de la sécurité (chaque entrée, et des faux amis
                qui ne doivent PAS refuser : « épisodique », « Vatican », « soupape de sécurité »…) ; mêmes
                contrôles pour un texte corrigé à la main, avec son propre message ;
    IA        : avec le faux fournisseur (démo en file://), une réponse valable devient le texte enregistré
                (otSources = les 40 OT les plus récents) ; la requête ne contient ni nom de technicien ou de
                demandeur, ni coût, ni photo ; le compte rendu est coupé à 600 caractères ; le schéma limite
                les citations aux OT envoyés ; Ia.requete rend exactement ce qui est envoyé ;
                Ia.lireReponse suit le même circuit ; chaque réponse piégée est refusée avec sa raison.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_controles.py" -v
"""
import json
import sys
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier
from faux_fournisseur_ia import PIEGE, FauxFournisseur

RUBRIQUES = ["Ce qui revient", "Ce qui a réglé le problème", "À surveiller"]
MARQUEURS_INTERDITS = ["987.65", "77.77", "photo-secrete.jpg"]
COUPE = "MARQUEUR-APRES-600"

DEMANDER_JS = """async ([fonction, donnees]) => {
  try {
    const reponse = await Ia.demander(fonction, donnees);
    return { ok: true, resultat: reponse.resultat, modele: reponse.modele };
  } catch (erreur) {
    return { ok: false, nom: erreur.name, message: erreur.message };
  }
}"""

# Données d'une synthèse, prises dans la démo : l'équipement qui a le plus d'OT clôturés, chaque OT avec
# des valeurs interdites glissées (technicien, coût, photo, taux, prix d'une pièce), un compte rendu long
# coupé à 600 caractères, et 30 OT anciens fabriqués pour dépasser la limite de 40.
DONNEES_JS = """([interdits, coupe]) => {
  const clos = Donnees.lignes('ordres_travail').filter((o) => /^Clôturé/.test(o.statut));
  const parEquipement = new Map();
  clos.forEach((o) => { if (!parEquipement.has(o.equipement_id)) parEquipement.set(o.equipement_id, []); parEquipement.get(o.equipement_id).push(o); });
  const [equipementId, siens] = Array.from(parEquipement.entries()).sort((a, b) => b[1].length - a[1].length)[0];
  const eq = Donnees.trouver('equipements', equipementId);
  const tech = Donnees.lignes('techniciens')[0];
  const extras = { technicien: tech.prenom + ' ' + tech.nom, cout: interdits[0], taux: interdits[1], photo: interdits[2] };
  const libelle = (famille, code) => ((Donnees.lignes('codes_defaillance').find((c) => c.famille === famille && c.code === code) || {}).libelle || '');
  const ot = siens.map((o) => Object.assign({}, extras, { id: o.id, date: (o.date_fin || o.date_creation).slice(0, 10), type: o.type,
    titre: o.titre, symptome: libelle('symptôme', o.symptome_code), cause: libelle('cause', o.cause_code),
    remede: libelle('remède', o.remede_code), compteRendu: o.compte_rendu,
    pieces: [{ designation: 'Joint de tige', quantite: '1', prix_unitaire: interdits[0] }], dureeArret: o.duree_arret_h }));
  ot[0].compteRendu = 'x'.repeat(650) + ' ' + coupe;
  for (let n = 1; n <= 30; n += 1) {
    ot.push(Object.assign({}, extras, { id: 'OT-2019-' + String(n).padStart(4, '0'), date: '2019-01-' + String(n).padStart(2, '0'),
      type: 'correctif différé', titre: 'Ancienne intervention ' + n, compteRendu: 'ancien', pieces: [] }));
  }
  return { equipementId, techNom: extras.technicien,
    donnees: Object.assign({}, extras, { repere: eq.repere, designation: eq.designation, marque: eq.marque, modele: eq.modele, ot }) };
}"""


def regler_ia(contexte, url, modele="faux"):
    """Réglages IA du poste (localStorage prevo.ia) avant tout chargement de page."""
    valeur = dict(actif=True, fournisseur="ollama", url=url, modele=modele, cle="", delaiS=30)
    contexte.add_init_script("(() => { try { localStorage.setItem('prevo.ia', %s); } catch (e) { /* about:blank */ } })();"
                             % json.dumps(json.dumps(valeur)))


def taire_coupures(faux):
    """Le navigateur peut fermer une connexion en fin de test : rien à écrire en console pour cela."""
    serveur = faux._serveur
    gestion_d_origine = serveur.handle_error

    def gerer_erreur(requete, adresse):
        if isinstance(sys.exc_info()[1], (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return
        gestion_d_origine(requete, adresse)
    serveur.handle_error = gerer_erreur


class TestFormeEtControles(CasNavigateur):
    """Fonctions pures de wiki-regles.js, dans la démo (aucun fournisseur d'IA)."""

    def setUp(self):
        super().setUp()
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)

    def controler(self, texte, permis, origine="ia"):
        return self.page.evaluate("([t, p, o]) => Wiki.controlerSynthese(t, p, { origine: o })", [texte, permis, origine])

    def test_forme_aller_retour(self):
        puces = [
            {"rubrique": "À surveiller", "texte": "Roulement côté moteur", "ot": ["OT-2026-0003"]},
            {"rubrique": "Ce qui revient", "texte": "Fuite au joint [OT-2026-0001], fréquente ici", "ot": ["OT-2026-0002"]},
        ]
        texte = self.page.evaluate("(p) => Wiki.texteDeSynthese(p)", puces)
        self.assertEqual(texte, "Ce qui revient\n- Fuite au joint , fréquente ici [OT-2026-0001] [OT-2026-0002]\n"
                                "À surveiller\n- Roulement côté moteur [OT-2026-0003]")
        lu = self.page.evaluate("(t) => Wiki.lireSynthese(t)", texte)
        self.assertEqual(lu["horsForme"], [])
        self.assertEqual([(p["rubrique"], p["ot"]) for p in lu["puces"]],
                         [("Ce qui revient", ["OT-2026-0001", "OT-2026-0002"]), ("À surveiller", ["OT-2026-0003"])])
        # Titre tapé à la main : casse, accents et « : » final tolérés ; puce « * » ou « • » acceptée.
        lu = self.page.evaluate("(t) => Wiki.lireSynthese(t)", "a surveiller :\n* Courroie [OT-2026-0004]\n\n• Tension [OT-2026-0004]")
        self.assertEqual([p["rubrique"] for p in lu["puces"]], ["À surveiller", "À surveiller"])
        self.assertEqual(self.page.evaluate("Wiki.RUBRIQUES"), RUBRIQUES)

    def test_texte_valable(self):
        texte = "Ce qui revient\n- Fuite au joint de tige [OT-2026-0001]\nÀ surveiller\n- Roulement [OT-2026-0002]"
        resultat = self.controler(texte, ["OT-2026-0001", "OT-2026-0002"])
        self.assertTrue(resultat["ok"], resultat)
        self.assertEqual(resultat["otCites"], ["OT-2026-0001", "OT-2026-0002"])

    def test_chaque_controle_refuse_avec_sa_raison(self):
        permis = ["OT-2026-0001"]
        cas = {
            "hors forme": ("Une phrase libre sans rubrique\nCe qui revient\n- Fuite [OT-2026-0001]", "Ligne 1 hors de la forme"),
            "puce avant toute rubrique": ("- Fuite [OT-2026-0001]", "Ligne 1 hors de la forme"),
            "vide": ("Ce qui revient", "Aucune puce"),
            "sept puces": ("Ce qui revient\n" + "\n".join("- Point %d [OT-2026-0001]" % n for n in range(7)), "7 puces : 6 au plus"),
            "151 mots": ("Ce qui revient\n- " + " ".join(["mot"] * 151) + " [OT-2026-0001]", "151 mots : 150 au plus"),
            "puce sans OT": ("Ce qui revient\n- Fuite [OT-2026-0001]\n- Roulement", "Puce 2 : elle ne cite aucun OT"),
            "OT inventé": ("Ce qui revient\n- Fuite [OT-2026-0001] [OT-1999-9999]", "OT cité absent des OT envoyés à l'IA : OT-1999-9999"),
            "consigne": ("Ce qui revient\n- Consigner la presse [OT-2026-0001]", "L'IA ne rédige jamais de consigne de sécurité"),
        }
        for nom, (texte, raison) in cas.items():
            with self.subTest(cas=nom):
                resultat = self.controler(texte, permis)
                self.assertFalse(resultat["ok"])
                self.assertTrue(any(raison in r for r in resultat["raisons"]), resultat["raisons"])
        # 150 mots tout juste, citations comprises (elles ne comptent pas) : accepté.
        juste = "Ce qui revient\n- " + " ".join(["mot"] * 150) + " [OT-2026-0001] [OT-2026-0001]"
        self.assertTrue(self.controler(juste, permis)["ok"])

    def test_vocabulaire_de_securite_chaque_entree_et_faux_amis(self):
        vocabulaire = self.page.evaluate("Wiki.VOCABULAIRE_SECURITE")
        self.assertTrue(self.page.evaluate("Object.isFrozen(Wiki.VOCABULAIRE_SECURITE)"))
        for entree in vocabulaire:
            mot = entree[:-1] + "ation" if entree.endswith("*") else entree
            with self.subTest(entree=entree):
                texte = "Ce qui revient\n- Pendant l'intervention, %s du poste [OT-2026-0001]" % mot.upper()
                resultat = self.controler(texte, ["OT-2026-0001"])
                self.assertFalse(resultat["ok"], entree)
        # Avec accents et apostrophes réelles.
        for phrase in ("Couper l'alimentation générale", "Vérifier l'absence de tension", "Porter des gants",
                       "Mise en sécurité de la machine", "Poser le cadenas", "Habilitation BR requise"):
            with self.subTest(phrase=phrase):
                self.assertNotEqual(self.page.evaluate("(t) => Wiki.termesDeSecurite(t)", phrase), [])
        # Faux amis : rien ne doit être refusé.
        for phrase in ("Panne épisodique du capteur", "Retour du Vatican", "La soupape de sécurité fuit",
                       "Le pressostat de sécurité déclenche", "Graissage du portique (gantry)", "Épingle cassée"):
            with self.subTest(faux_ami=phrase):
                self.assertEqual(self.page.evaluate("(t) => Wiki.termesDeSecurite(t)", phrase), [])

    def test_correction_a_la_main_memes_controles_et_message_propre(self):
        texte = "Ce qui revient\n- Couper l'alimentation puis changer le joint [OT-2026-0001] [OT-2026-0009]"
        resultat = self.controler(texte, ["OT-2026-0001"], origine="main")
        self.assertFalse(resultat["ok"])
        raisons = " ".join(resultat["raisons"])
        self.assertIn("Le bloc [IA] ne contient pas de consigne de sécurité", raisons)
        self.assertIn("OT cité absent des OT de cet équipement : OT-2026-0009", raisons)
        self.assertNotIn("L'IA ne rédige jamais", raisons)


class TestSyntheseIa(CasNavigateur):
    """Ia.demander('syntheseWiki') avec le faux fournisseur (démo en file://)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur()
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)
        taire_coupures(cls.faux)

    def ouvrir(self, modele="faux"):
        self.faux.requetes.clear()
        regler_ia(self.contexte, self.faux.url, modele)
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.page.wait_for_function("Ia.etat() !== 'inconnu'")
        return self.page.evaluate(DONNEES_JS, [MARQUEURS_INTERDITS, COUPE])

    def demander(self, donnees):
        return self.page.evaluate(DEMANDER_JS, ["syntheseWiki", donnees])

    def derniere_requete(self):
        return [r for r in self.faux.requetes if r["chemin"] == "/api/chat"][-1]["corps"]

    def test_reponse_valable_texte_enregistrable_et_ot_sources(self):
        jeu = self.ouvrir()
        reponse = self.demander(jeu["donnees"])
        self.assertTrue(reponse["ok"], reponse)
        resultat = reponse["resultat"]
        lu = self.page.evaluate("(t) => Wiki.lireSynthese(t)", resultat["texte"])
        self.assertEqual(lu["horsForme"], [])
        self.assertEqual(len(lu["puces"]), 3)
        # Les 40 OT les plus récents, dans l'ordre : aucun des 30 OT fabriqués de 2019 n'y entre s'il y a au moins
        # 10 vrais OT ; tous sont de l'équipement.
        attendus = sorted(jeu["donnees"]["ot"], key=lambda o: (o["date"], o["id"]), reverse=True)[:40]
        self.assertEqual(resultat["otSources"], [o["id"] for o in attendus])
        self.assertTrue(set(resultat["otCites"]) <= set(resultat["otSources"]))
        self.assertTrue(self.page.evaluate("(r) => Wiki.controlerSynthese(r.texte, r.otSources).ok", resultat))

    def test_requete_sans_donnees_interdites_et_compte_rendu_coupe(self):
        jeu = self.ouvrir()
        self.assertTrue(self.demander(jeu["donnees"])["ok"])
        corps = self.derniere_requete()
        systeme, utilisateur = corps["messages"][0]["content"], corps["messages"][1]["content"]
        self.assertTrue(systeme.startswith("Fonction : syntheseWiki"))
        self.assertIn("consigne de sécurité", systeme)
        envoye = json.dumps(corps, ensure_ascii=False)
        for interdit in MARQUEURS_INTERDITS + [jeu["techNom"], COUPE]:
            self.assertNotIn(interdit, envoye, interdit)
        self.assertIn("x" * 600, utilisateur)
        self.assertNotIn("x" * 601, utilisateur)
        self.assertEqual(utilisateur.count("\n- OT-"), 40)
        enum = corps["format"]["properties"]["puces"]["items"]["properties"]["ot"]["items"]["enum"]
        self.assertEqual(len(enum), 40)
        self.assertEqual(corps["format"]["properties"]["puces"]["items"]["properties"]["rubrique"]["enum"], RUBRIQUES)

    def test_ia_requete_egale_a_ce_qui_est_envoye_et_lire_reponse_meme_circuit(self):
        jeu = self.ouvrir()
        attendue = self.page.evaluate("(d) => Ia.requete('syntheseWiki', d)", jeu["donnees"])
        reponse = self.demander(jeu["donnees"])
        corps = self.derniere_requete()
        self.assertEqual(attendue["messages"], corps["messages"])
        self.assertEqual(attendue["schema"], corps["format"])
        self.assertEqual(attendue["temperature"], corps["options"]["temperature"])
        self.assertEqual(attendue["fonction"], "syntheseWiki")
        # La même réponse que celle du faux fournisseur, relue par Ia.lireReponse (en bloc ```json```), donne le
        # même résultat que Ia.demander.
        contenu = json.dumps({"puces": [
            {"rubrique": "Ce qui revient", "texte": "Fuite au joint de tige, fréquente ici",
             "ot": reponse["resultat"]["otSources"][:2]},
            {"rubrique": "Ce qui a réglé le problème", "texte": "Remplacement du joint et serrage des raccords",
             "ot": reponse["resultat"]["otSources"][:1]},
            {"rubrique": "À surveiller", "texte": "Usure du roulement côté moteur",
             "ot": reponse["resultat"]["otSources"][-1:]}]}, ensure_ascii=False)
        relu = self.page.evaluate("([c, d]) => Ia.lireReponse('syntheseWiki', '```json\\n' + c + '\\n```', d)",
                                  [contenu, jeu["donnees"]])
        self.assertEqual(relu, reponse["resultat"])
        erreur = self.page.evaluate("""(d) => { try { Ia.lireReponse('syntheseWiki', 'pas du JSON', d); return null; }
            catch (e) { return e.name; } }""", jeu["donnees"])
        self.assertEqual(erreur, "IaReponseInvalide")

    def test_reponses_piegees_refusees_avec_leur_raison(self):
        cas = {
            "faux-invente": "OT cité absent des OT envoyés à l'IA : OT-1999-9999",
            "faux-sans-ot": "elle ne cite aucun OT",
            "faux-trop-long": "7 puces : 6 au plus",
            "faux-trop-de-mots": "mots : 150 au plus",
            "faux-consigne": "L'IA ne rédige jamais de consigne de sécurité",
            "faux-alimentation": "L'IA ne rédige jamais de consigne de sécurité",
            "faux-illisible": "",
        }
        for modele, raison in cas.items():
            with self.subTest(modele=modele):
                jeu = self.ouvrir(modele)
                reponse = self.demander(jeu["donnees"])
                self.assertFalse(reponse["ok"], reponse)
                self.assertEqual(reponse["nom"], "IaReponseInvalide")
                self.assertIn(raison, reponse["message"])
        # « faux-html » passe les contrôles (le texte n'est pas une consigne) : l'échappement est l'affaire de
        # l'écran (T102) ; ici, le texte arrive tel quel, sans être interprété.
        self.page.evaluate("Ia.enregistrerReglages({ modele: 'faux-html' })")
        reponse = self.demander(self.page.evaluate(DONNEES_JS, [MARQUEURS_INTERDITS, COUPE])["donnees"])
        self.assertTrue(reponse["ok"], reponse)
        self.assertIn(PIEGE, reponse["resultat"]["texte"])
        self.assertFalse(self.page.evaluate("window.__xss === true"))


if __name__ == "__main__":
    unittest.main()
