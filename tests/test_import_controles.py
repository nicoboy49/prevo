"""Contrôles des formulaires appliqués à l'aperçu de l'import (lot 5, tâche T92 ; question du §6.14 du rapport T80,
décision de Nicolas du 2026-10-22) : une ligne que le formulaire de Prévo refuserait est refusée à l'aperçu, avec la
raison du formulaire (le même texte, préfixé au besoin du champ).

Pour chaque type concerné, la raison attendue est le texte que rend, DANS LA PAGE, la fonction du formulaire appelée
sur les mêmes valeurs (fiche telle qu'elle sera écrite, ou fiche existante complétée des changements) :
    Controles.verifierControle, Parc.verifierEquipement, Parc.verifierLocalisation, Magasin.interne.verifierArticle,
    Magasin.interne.verifierFournisseur, Equipe.verifierTechnicien, Equipe.interne.verifierHabilitation,
    Parametres.verifierCode, Preventif.verifierGamme.
Couvert aussi : une ligne valable passe ; une mise à jour est contrôlée sur la fiche complétée (une cellule vide
n'efface rien, D84) et non sur la seule ligne du fichier (les deux sens : refusée alors que la ligne seule passerait,
acceptée alors que la ligne seule serait refusée) ; l'unicité tient compte des lignes acceptées plus haut dans le
fichier, sans refuser deux fois un doublon du fichier ; ce qui dépend d'une ligne refusée l'est aussi (équipement
enfant, plus haut ou plus bas dans le fichier ; opérations d'une gamme) ; aucune écriture ni référence créée orpheline
(fournisseur ou localisation créé pour une ligne refusée seule : plus créé) ; l'aperçu n'écrit toujours rien.

Page : index.html en file://, démo ; horloge du navigateur fixée à la date de référence de la démo (la démo n'est pas
décalée) et « maintenant » de l'import au même jour : le test passe à toute heure.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_import_controles.py" -v
"""
import datetime
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier
from test_controles import date_reference

REFERENCE = date_reference()
HEURE_FIXE = REFERENCE.isoformat() + "T09:30:00"
MAINTENANT = REFERENCE.isoformat() + " 09:30"
JOUR = REFERENCE.isoformat()

# Aperçu dans la page : correspondance « une colonne par champ » (en-tête = clé du champ). Rend l'aperçu (JSON), les
# références orphelines des écritures (vérifiées AVANT la sérialisation : un identifiant indéfini disparaîtrait du
# JSON) et l'état de la base avant et après (Donnees.instantane, à l'octet).
APERCU_JS = """([type, entetes, grille, options]) => {
  const etat = () => { const tout = Donnees.instantane(); const r = {};
    Object.keys(tout).forEach((n) => { r[n] = Array.from(tout[n]).join(','); }); return r; };
  const avant = etat();
  const correspondance = entetes.map((champ, colonne) => ({ colonne, entete: champ, champ, statut: 'sure', raison: '' }));
  const apercu = Import.preparer(type, grille, correspondance, options);
  const REFS = { parent_id: null, localisation_id: 'localisations', fournisseur_id: 'fournisseurs', gamme_id: 'gammes',
    article_id: 'articles', equipement_id: 'equipements', compteur_id: 'compteurs', technicien_id: 'techniciens' };
  const crees = {};
  Object.keys(apercu.ecritures).forEach((t) => { crees[t] = new Set(apercu.ecritures[t].creer.map((l) => l.id)); });
  const orphelins = [];
  const verifier = (table, id, nom, valeur) => {
    if (valeur === undefined || valeur === null || typeof valeur === 'object') { orphelins.push(table + ' ' + id + ' : ' + nom + ' sans valeur écrite'); return; }
    if (!Object.prototype.hasOwnProperty.call(REFS, nom) || valeur === '') return;
    const cible = REFS[nom] || table;
    if (!(crees[cible] && crees[cible].has(valeur)) && !Donnees.trouver(cible, valeur)) orphelins.push(table + ' ' + id + ' : ' + nom + ' = ' + valeur + ' (ni créé ni dans la base)');
  };
  Object.keys(apercu.ecritures).forEach((table) => {
    apercu.ecritures[table].creer.forEach((l) => {
      if (!l.id) orphelins.push(table + ' : fiche créée sans identifiant');
      Schema.table(table).champs.forEach((c) => verifier(table, l.id, c.nom, l[c.nom]));
    });
    apercu.ecritures[table].modifier.forEach((m) => Object.keys(m.changes).forEach((n) => verifier(table, m.id, n, m.changes[n])));
  });
  apercu.referencesCreees.forEach((r) => { if (!crees[r.table] || !crees[r.table].has(r.id)) orphelins.push('référence ' + r.libelle + ' annoncée mais pas écrite'); });
  // Une fiche qu'une ligne refusée devait créer n'a pas d'identifiant : la citer écrirait une référence VIDE. Références
  // toujours remplies, et références demandées par la ligne du fichier (parent, fournisseur, localisation).
  const REMPLIES = { gamme_operations: ['gamme_id'], mouvements_stock: ['article_id'], gammes: ['equipement_id'], compteurs: ['equipement_id'],
    controles_reglementaires: ['equipement_id'], habilitations: ['technicien_id'] };
  Object.keys(REMPLIES).forEach((t) => ((apercu.ecritures[t] || {}).creer || []).forEach((l) => REMPLIES[t].forEach((n) => {
    if (!l[n]) orphelins.push(t + ' ' + l.id + ' : ' + n + ' vide'); })));
  const PRINCIPALE = { localisations: 'localisations', equipements: 'equipements', articles: 'articles', fournisseurs: 'fournisseurs',
    techniciens: 'techniciens', habilitations: 'habilitations', codes: 'codes_defaillance', compteurs: 'compteurs',
    controles: 'controles_reglementaires', gammes: 'gammes' }[type];
  const DEMANDEES = { parent: 'parent_id', fournisseur: 'fournisseur_id', chemin_localisation: 'localisation_id', site: 'localisation_id',
    atelier: 'localisation_id', ligne: 'localisation_id' };
  apercu.lignes.filter((l) => l.action === 'creer' && l.cible).forEach((l) => {
    const fiche = apercu.ecritures[PRINCIPALE].creer.find((c) => c.id === l.cible);
    Object.keys(DEMANDEES).forEach((v) => { if (fiche && l.valeurs[v] !== undefined && !fiche[DEMANDEES[v]]) orphelins.push('ligne ' + l.numero + ' : ' + DEMANDEES[v] + ' vide'); });
  });
  return { apercu: JSON.parse(JSON.stringify(apercu)), orphelins, inchangee: JSON.stringify(avant) === JSON.stringify(etat()) };
}"""

# Fonctions des formulaires, appelées dans la page : liste des messages.
FORMULAIRES = {
    "controles": "([v, id, jour]) => Controles.verifierControle(v, jour).map((e) => e.message)",
    "equipements": """([v, id]) => Parc.verifierEquipement(v, Donnees.lignes('equipements'), Donnees.lignes('localisations'), id)
                      .map((e) => e.message)""",
    "localisations": "([v, id]) => Parc.verifierLocalisation(v, Donnees.lignes('localisations'), id).map((e) => e.message)",
    "articles": "([v, id]) => Magasin.interne.verifierArticle(v, Donnees.lignes('articles'), id).map((e) => e.message)",
    "fournisseurs": "([v, id]) => Magasin.interne.verifierFournisseur(v, Donnees.lignes('fournisseurs'), id).map((e) => e.message)",
    "techniciens": "([v, id]) => Equipe.verifierTechnicien(v, Donnees.lignes('techniciens'), id).map((e) => e.message)",
    "habilitations": "([v]) => Equipe.interne.verifierHabilitation(v).map((e) => e.message)",
    # Modification d'un code : l'écran ne garde que les erreurs du libellé (parametres-codes.js, modifierLibelleCode).
    "codes": """([v, id, jour, plus]) => Parametres.verifierCode(v, Donnees.lignes('codes_defaillance').concat(plus || []), id)
                .filter((e) => !id || e.nom === 'libelle').map((e) => e.message)""",
    "gammes": "([v]) => Preventif.verifierGamme(v).map((e) => e.message)",
}


def date_fr(jour):
    return jour.strftime("%d/%m/%Y")


class CasControles(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.contexte.clock.set_fixed_time(HEURE_FIXE)
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)

    def apercu(self, type_, entetes, grille, mettre_a_jour=True):
        retour = self.page.evaluate(APERCU_JS, [type_, entetes, grille, {"maintenant": MAINTENANT, "mettreAJour": mettre_a_jour}])
        self.assertEqual(retour["orphelins"], [], "aucune écriture ni référence créée orpheline")
        self.assertTrue(retour["inchangee"], "l'aperçu n'écrit rien")
        return retour["apercu"]

    def formulaire(self, type_, valeurs, id_courant="", plus=None):
        return self.page.evaluate(FORMULAIRES[type_], [valeurs, id_courant, JOUR, plus or []])

    def fiche(self, table, identifiant):
        return self.page.evaluate("([t, id]) => Object.assign({}, Donnees.trouver(t, id))", [table, identifiant])

    @staticmethod
    def ligne(apercu, numero):
        return next(l for l in apercu["lignes"] if l["numero"] == numero)

    def verifier_refus(self, ligne, messages):
        """Ligne refusée ; ses dernières raisons sont les messages du formulaire, dans l'ordre (préfixés au besoin)."""
        self.assertEqual(ligne["action"], "refusee", ligne)
        self.assertTrue(messages, "le formulaire refuse bien ces valeurs")
        self.assertGreaterEqual(len(ligne["raisons"]), len(messages), ligne["raisons"])
        for raison, message in zip(ligne["raisons"][-len(messages):], messages):
            self.assertTrue(raison == message or raison.endswith(" : " + message), (raison, message))

    def verifier_actions(self, apercu, attendues):
        self.assertEqual({l["numero"]: l["action"] for l in apercu["lignes"]}, attendues,
                         [(l["numero"], l["action"], l["raisons"]) for l in apercu["lignes"]])


class TestControlesReglementaires(CasControles):

    def test_verifierControle_creation_et_mise_a_jour_sur_la_fiche_completee(self):
        ch01, gf01 = self.fiche("controles_reglementaires", "CTR-0002"), self.fiche("controles_reglementaires", "CTR-0005")
        passe, futur = REFERENCE - datetime.timedelta(days=40), REFERENCE + datetime.timedelta(days=50)
        derniere_ch01 = datetime.date.fromisoformat(ch01["prochaine_date"]) + datetime.timedelta(days=1)
        self.assertLessEqual(derniere_ch01, REFERENCE, "démo : prochaine date de CTR-0002 passée")
        prochaine_gf01 = datetime.date.fromisoformat(gf01["prochaine_date"]) + datetime.timedelta(days=30)
        entetes = ["equipement", "nature", "periodicite_mois", "derniere_date", "prochaine_date"]
        grille = [
            ["PT-01", "Contrôle des freins du pont", "", date_fr(passe), ""],                    # 2 : périodicité vide
            ["PT-01", "Contrôle des fins de course", "12", date_fr(futur), ""],                  # 3 : dernière date future
            ["CU-01", "Contrôle valable", "12", date_fr(passe), ""],                             # 4 : passe
            ["CH-01", ch01["nature"], "", date_fr(derniere_ch01), ""],                           # 5 : complétée → refusée
            ["GF-01", gf01["nature"], "", "", date_fr(prochaine_gf01)],                          # 6 : complétée → passe
        ]
        apercu = self.apercu("controles", entetes, grille)
        self.verifier_actions(apercu, {2: "refusee", 3: "refusee", 4: "creer", 5: "refusee", 6: "mettre_a_jour"})
        nouveau = {"equipement_id": "EQ-0018", "texte_reference": "", "organisme": "", "rapport": "", "observations": ""}
        self.verifier_refus(self.ligne(apercu, 2), self.formulaire("controles", dict(nouveau, nature="Contrôle des freins du pont",
                            periodicite_mois="", derniere_date=passe.isoformat(), prochaine_date="")))
        self.verifier_refus(self.ligne(apercu, 3), self.formulaire("controles", dict(nouveau, nature="Contrôle des fins de course",
                            periodicite_mois="12", derniere_date=futur.isoformat(), prochaine_date="")))
        # Mise à jour : la fiche CTR-0002 complétée (périodicité et prochaine date gardées) est refusée…
        completee = dict(ch01, derniere_date=derniere_ch01.isoformat())
        attendus = self.formulaire("controles", completee, "CTR-0002")
        self.verifier_refus(self.ligne(apercu, 5), attendus)
        seule = {"equipement_id": "EQ-0030", "nature": ch01["nature"], "derniere_date": derniere_ch01.isoformat()}
        self.assertNotEqual(self.formulaire("controles", seule), attendus, "la ligne seule donnerait une autre raison")
        # … et CTR-0005 complétée passe, alors que la ligne seule (sans périodicité) serait refusée.
        self.assertEqual(self.formulaire("controles", dict(gf01, prochaine_date=prochaine_gf01.isoformat()), "CTR-0005"), [])
        self.assertTrue(self.formulaire("controles", {"equipement_id": "EQ-0007", "nature": gf01["nature"],
                                                      "prochaine_date": prochaine_gf01.isoformat()}))
        self.assertEqual([c["nature"] for c in apercu["ecritures"]["controles_reglementaires"]["creer"]], ["Contrôle valable"])
        self.assertEqual([m["id"] for m in apercu["ecritures"]["controles_reglementaires"]["modifier"]], ["CTR-0005"])


class TestParc(CasControles):

    def test_equipements_refus_du_formulaire_enfants_et_localisation_creee_pour_eux_seuls(self):
        entetes = ["repere", "designation", "chemin_localisation", "parent", "heures_fonct_jour", "valeur_remplacement", "criticite"]
        grille = [
            ["NV-01", "Nouvelle machine", "Site des Trois Vallées > Atelier Neuf", "", "30", "", ""],   # 2 : heures > 24
            ["NV-01.A", "Sous-ensemble de la nouvelle machine", "", "NV-01", "", "", ""],                # 3 : parent refusé
            ["NV-02", "Machine valable", "Site des Trois Vallées > Atelier Usinage", "", "8", "1500", ""],  # 4 : passe
            ["NV-03", "Machine au montant négatif", "", "", "", "-5", ""],                             # 5 : montant < 0
            ["PO-02", "", "", "", "", "", "A"],                                                        # 6 : complétée → passe
            ["NV-04.A", "Enfant cité avant son parent", "", "NV-04", "", "", ""],                      # 7 : parent plus bas refusé
            ["NV-04", "Parent refusé plus bas", "", "", "25", "", ""],                                 # 8 : heures > 24
            ["NV-05.A", "Enfant d'un parent valable", "", "NV-02", "", "", ""],                        # 9 : passe
        ]
        apercu = self.apercu("equipements", entetes, grille)
        self.verifier_actions(apercu, {2: "refusee", 3: "refusee", 4: "creer", 5: "refusee", 6: "mettre_a_jour",
                                       7: "refusee", 8: "refusee", 9: "creer"})
        self.verifier_refus(self.ligne(apercu, 2), self.formulaire("equipements", {
            "repere": "NV-01", "designation": "Nouvelle machine", "heures_fonct_jour": "30", "criticite": "B", "statut": "en service"}))
        self.verifier_refus(self.ligne(apercu, 5), self.formulaire("equipements", {
            "repere": "NV-03", "designation": "Machine au montant négatif", "valeur_remplacement": "-5", "criticite": "B"}))
        self.verifier_refus(self.ligne(apercu, 8), self.formulaire("equipements", {
            "repere": "NV-04", "designation": "Parent refusé plus bas", "heures_fonct_jour": "25"}))
        self.assertEqual(self.ligne(apercu, 3)["raisons"][-1], "équipement parent refusé (ligne 2)")
        self.assertEqual(self.ligne(apercu, 7)["raisons"][-1], "équipement parent refusé (ligne 8)")
        # PO-02 : la fiche complétée passe ; la ligne seule (sans désignation) aurait été refusée.
        self.assertTrue(self.formulaire("equipements", {"repere": "PO-02", "criticite": "A"}, "EQ-0005"))
        self.assertEqual([c["changes"] for c in apercu["ecritures"]["equipements"]["modifier"]], [{"criticite": "A"}])
        crees = apercu["ecritures"]["equipements"]["creer"]
        self.assertEqual([e["repere"] for e in crees], ["NV-02", "NV-05.A"])
        self.assertEqual(crees[1]["parent_id"], crees[0]["id"])
        # « Atelier Neuf » n'était demandé que par NV-01, refusé : il n'est plus créé.
        self.assertEqual(apercu["ecritures"]["localisations"]["creer"], [])
        self.assertEqual(apercu["referencesCreees"], [])

    def test_equipement_mis_a_jour_refuse_sur_la_fiche_completee(self):
        # Fiche existante devenue invalide pour le formulaire (heures par jour hors bornes) : la compléter d'une
        # criticité ne suffit pas, le formulaire refuserait l'enregistrement.
        self.page.evaluate("""() => Donnees.modifier('equipements', (lignes) => {
          lignes.find((l) => l.id === 'EQ-0007').heures_fonct_jour = '30'; }, { action: 'essai T92' })""")
        apercu = self.apercu("equipements", ["repere", "criticite"], [["GF-01", "C"], ["CP-01", "B"]])
        self.verifier_actions(apercu, {2: "refusee", 3: "mettre_a_jour"})
        completee = dict(self.fiche("equipements", "EQ-0007"), criticite="C")
        attendus = self.formulaire("equipements", completee, "EQ-0007")
        self.verifier_refus(self.ligne(apercu, 2), attendus)
        self.assertNotEqual(self.formulaire("equipements", {"repere": "GF-01", "criticite": "C"}, "EQ-0007"), attendus)

    def test_localisations_verifierLocalisation_sur_la_fiche_completee(self):
        # Deux « Atelier Usinage » sous le même site (données anciennes) : changer le type de l'un, le formulaire le
        # refuserait (« Il existe déjà une localisation… à cet endroit »). Une localisation nouvelle passe.
        self.page.evaluate("""() => Donnees.modifier('localisations', (lignes, outils) => {
          lignes.push({ id: outils.nouvelId(lignes), libelle: 'Atelier Usinage', parent_id: 'LOC-0001', type: 'atelier' }); },
          { action: 'essai T92' })""")
        apercu = self.apercu("localisations", ["chemin", "type"], [
            ["Site des Trois Vallées > Atelier Usinage", "ligne"], ["Site des Trois Vallées > Atelier Neuf", ""]])
        self.verifier_actions(apercu, {2: "refusee", 3: "creer"})
        completee = dict(self.fiche("localisations", "LOC-0002"), type="ligne")
        self.verifier_refus(self.ligne(apercu, 2), self.formulaire("localisations", completee, "LOC-0002"))
        self.assertEqual([(l["libelle"], l["parent_id"], l["type"]) for l in apercu["ecritures"]["localisations"]["creer"]],
                         [("Atelier Neuf", "LOC-0001", "atelier")])


class TestMagasin(CasControles):

    def test_articles_fournisseur_cree_pour_un_article_refuse_et_doublon_du_fichier(self):
        entetes = ["reference", "designation", "stock_initial", "prix_unitaire", "fournisseur", "delai_jours"]
        grille = [
            ["NV-A01", "Article à prix négatif", "5", "-3", "Fournisseur Fantôme", ""],          # 2 : prix < 0
            ["NV-A02", "Article valable", "4", "2,50", "Fournisseur Partagé", "3"],               # 3 : passe
            ["NV-A03", "Article au délai négatif", "", "", "Fournisseur Partagé", "-1"],          # 4 : délai < 0
            ["NV-A02", "Doublon de la ligne 3", "2", "", "", ""],                                 # 5 : doublon (une raison)
            ["ROU-001", "", "", "5,15", "", ""],                                                  # 6 : complétée → passe
            ["ROU-002", "", "", "-1", "", ""],                                                    # 7 : complétée → refusée
        ]
        apercu = self.apercu("articles", entetes, grille)
        self.verifier_actions(apercu, {2: "refusee", 3: "creer", 4: "refusee", 5: "refusee", 6: "mettre_a_jour", 7: "refusee"})
        self.verifier_refus(self.ligne(apercu, 2), self.formulaire("articles", {
            "reference": "NV-A01", "designation": "Article à prix négatif", "prix_unitaire": "-3", "actif": "1"}))
        self.verifier_refus(self.ligne(apercu, 4), self.formulaire("articles", {
            "reference": "NV-A03", "designation": "Article au délai négatif", "delai_jours": "-1", "actif": "1"}))
        self.verifier_refus(self.ligne(apercu, 7), self.formulaire("articles", dict(self.fiche("articles", "ART-0002"), prix_unitaire="-1"), "ART-0002"))
        # Doublon du fichier : refusé une seule fois, par l'import ; la ligne 3 n'est pas refusée à cause de lui.
        self.assertEqual(self.ligne(apercu, 5)["raisons"], ["doublon dans le fichier, ligne 3"])
        # ROU-001 : la fiche complétée passe ; la ligne seule (sans désignation) aurait été refusée.
        self.assertTrue(self.formulaire("articles", {"reference": "ROU-001", "prix_unitaire": "5.15"}, "ART-0001"))
        # Fournisseurs : « Fantôme » n'était cité que par l'article refusé → plus créé ; « Partagé » l'est une fois.
        self.assertEqual([f["nom"] for f in apercu["ecritures"]["fournisseurs"]["creer"]], ["Fournisseur Partagé"])
        self.assertEqual([r["libelle"] for r in apercu["referencesCreees"]], ["Fournisseur Partagé"])
        article = apercu["ecritures"]["articles"]["creer"]
        self.assertEqual([a["reference"] for a in article], ["NV-A02"])
        self.assertEqual(article[0]["fournisseur_id"], apercu["ecritures"]["fournisseurs"]["creer"][0]["id"])
        self.assertEqual([(m["article_id"], m["quantite"]) for m in apercu["ecritures"]["mouvements_stock"]["creer"]],
                         [(article[0]["id"], "4")])

    def test_fournisseurs_verifierFournisseur(self):
        apercu = self.apercu("fournisseurs", ["nom", "email"], [
            ["Fournisseur Sans Arobase", "contact.example"], ["Fournisseur Correct", "contact@correct.example"],
            ["Fluidalpes Services", "ventes-fluidalpes"], ["Lubrifix Industrie", ""]])
        self.verifier_actions(apercu, {2: "refusee", 3: "creer", 4: "refusee", 5: "identique"})
        self.verifier_refus(self.ligne(apercu, 2), self.formulaire("fournisseurs", {"nom": "Fournisseur Sans Arobase", "email": "contact.example"}))
        self.verifier_refus(self.ligne(apercu, 4), self.formulaire("fournisseurs", dict(self.fiche("fournisseurs", "FOU-0002"),
                                                                                       email="ventes-fluidalpes"), "FOU-0002"))


class TestEquipe(CasControles):

    def test_techniciens_verifierTechnicien(self):
        apercu = self.apercu("techniciens", ["nom", "prenom", "taux_horaire", "capacite_h_semaine"], [
            ["Nouveau", "Paul", "42", "90"], ["Valable", "Anne", "40", "35"], ["Moreau", "Julien", "-2", ""], ["Benali", "Karim", "45", ""]])
        self.verifier_actions(apercu, {2: "refusee", 3: "creer", 4: "refusee", 5: "mettre_a_jour"})
        self.verifier_refus(self.ligne(apercu, 2), self.formulaire("techniciens", {
            "nom": "Nouveau", "prenom": "Paul", "taux_horaire": "42", "capacite_h_semaine": "90", "actif": "1"}))
        self.verifier_refus(self.ligne(apercu, 4), self.formulaire("techniciens", dict(self.fiche("techniciens", "TEC-0001"),
                                                                                      taux_horaire="-2"), "TEC-0001"))

    def test_habilitations_verifierHabilitation_creation_et_fiche_completee(self):
        h0v, br = self.fiche("habilitations", "HAB-0005"), self.fiche("habilitations", "HAB-0008")
        avant = datetime.date.fromisoformat(h0v["date_obtention"]) - datetime.timedelta(days=30)
        plus_tard = datetime.date.fromisoformat(br["date_echeance"]) + datetime.timedelta(days=365)
        apercu = self.apercu("habilitations", ["technicien", "intitule", "date_obtention", "date_echeance"], [
            ["Julien Moreau", "H2V", "", ""],                            # 2 : sans date d'obtention
            ["Julien Moreau", "B1V", "10/03/2025", "10/03/2024"],        # 3 : échéance avant l'obtention
            ["Sophie Lambert", "B2V", "22/09/2025", "22/09/2028"],       # 4 : passe
            ["Karim Benali", "H0V", "", date_fr(avant)],                 # 5 : complétée → refusée
            ["Thomas Garnier", "BR", "", date_fr(plus_tard)],            # 6 : complétée → passe
        ])
        self.verifier_actions(apercu, {2: "refusee", 3: "refusee", 4: "creer", 5: "refusee", 6: "mettre_a_jour"})
        self.verifier_refus(self.ligne(apercu, 2), self.formulaire("habilitations", {
            "technicien_id": "TEC-0001", "intitule": "H2V", "date_obtention": "", "date_echeance": ""}))
        self.verifier_refus(self.ligne(apercu, 3), self.formulaire("habilitations", {
            "technicien_id": "TEC-0001", "intitule": "B1V", "date_obtention": "2025-03-10", "date_echeance": "2024-03-10"}))
        attendus = self.formulaire("habilitations", dict(h0v, date_echeance=avant.isoformat()))
        self.verifier_refus(self.ligne(apercu, 5), attendus)
        seule = {"technicien_id": "TEC-0002", "intitule": "H0V", "date_echeance": avant.isoformat()}
        self.assertNotEqual(self.formulaire("habilitations", seule), attendus, "la ligne seule donnerait une autre raison")
        self.assertTrue(self.formulaire("habilitations", {"technicien_id": "TEC-0004", "intitule": "BR",
                                                          "date_echeance": plus_tard.isoformat()}))
        self.assertEqual([m["id"] for m in apercu["ecritures"]["habilitations"]["modifier"]], ["HAB-0008"])


class TestCodes(CasControles):

    def test_codes_verifierCode_et_unicite_dans_le_fichier(self):
        apercu = self.apercu("codes", ["famille", "code", "libelle"], [
            ["cause", "C 77", "Grippage"],             # 2 : code avec une espace
            ["symptôme", "C01", "Bruit sourd"],        # 3 : code déjà pris par une cause
            ["cause", "C78", "Corrosion"],             # 4 : libellé déjà dans la famille
            ["symptôme", "S77", "Claquement"],         # 5 : passe
            ["remède", "S77", "Autre chose"],          # 6 : code pris par la ligne 5, acceptée plus haut
            ["cause", "C01", "Corrosion"],             # 7 : mise à jour du libellé → déjà dans la famille
            ["cause", "C02", "Roulement détruit"],     # 8 : mise à jour → passe
        ])
        self.verifier_actions(apercu, {2: "refusee", 3: "refusee", 4: "refusee", 5: "creer", 6: "refusee", 7: "refusee", 8: "mettre_a_jour"})
        for numero, famille, code, libelle in ((2, "cause", "C 77", "Grippage"), (3, "symptôme", "C01", "Bruit sourd"),
                                               (4, "cause", "C78", "Corrosion")):
            with self.subTest(ligne=numero):
                self.verifier_refus(self.ligne(apercu, numero), self.formulaire("codes", {"famille": famille, "code": code, "libelle": libelle}))
        plus_haut = [{"id": "ligne 5", "famille": "symptôme", "code": "S77", "libelle": "Claquement"}]
        self.verifier_refus(self.ligne(apercu, 6), self.formulaire("codes", {"famille": "remède", "code": "S77", "libelle": "Autre chose"},
                                                                   "", plus_haut))
        self.verifier_refus(self.ligne(apercu, 7), self.formulaire("codes", dict(self.fiche("codes_defaillance", "CD-0012"),
                                                                                 libelle="Corrosion"), "CD-0012"))
        self.assertEqual([c["code"] for c in apercu["ecritures"]["codes_defaillance"]["creer"]], ["S77"])


class TestGammes(CasControles):

    def test_gammes_verifierGamme_operations_de_la_gamme_refusee(self):
        entetes = ["equipement", "libelle", "declencheur", "periodicite_jours", "compteur", "periodicite_unites", "operations"]
        gam3 = self.fiche("gammes", "GAM-0003")
        grille = [
            ["SC-01", "Gamme sans périodicité", "", "", "", "", "Graisser"],                    # 2 : déclencheur date sans périodicité
            ["SC-01", "Gamme sans périodicité", "", "", "", "", "Nettoyer"],                    # 3 : opération de la gamme refusée
            ["CP-01", "Gamme au compteur incomplète", "compteur", "", "", "", "Vidanger"],      # 4 : ni compteur ni périodicité
            ["CV-03", "Gamme valable", "", "60", "", "", "Inspecter"],                          # 5 : passe
            ["CV-03", "Gamme valable", "", "", "", "", "Tendre la bande"],                      # 6 : opération ajoutée
            ["PO-02", gam3["libelle"], "", "0", "", "", ""],                                    # 7 : complétée → refusée
        ]
        apercu = self.apercu("gammes", entetes, grille)
        self.verifier_actions(apercu, {2: "refusee", 3: "refusee", 4: "refusee", 5: "creer", 6: "creer", 7: "refusee"})
        nouvelle = {"equipement_id": "EQ-0019", "libelle": "Gamme sans périodicité", "declencheur": "date", "periodicite_jours": "", "actif": "1"}
        self.verifier_refus(self.ligne(apercu, 2), self.formulaire("gammes", nouvelle))
        self.assertEqual(self.ligne(apercu, 3)["raisons"], ["gamme refusée (ligne 2)"], "sans « opération ajoutée », contredit")
        self.verifier_refus(self.ligne(apercu, 4), self.formulaire("gammes", {
            "equipement_id": "EQ-0001", "libelle": "Gamme au compteur incomplète", "declencheur": "compteur", "actif": "1"}))
        self.verifier_refus(self.ligne(apercu, 7), self.formulaire("gammes", dict(gam3, periodicite_jours="0")))
        gammes = apercu["ecritures"]["gammes"]["creer"]
        self.assertEqual([g["libelle"] for g in gammes], ["Gamme valable"])
        self.assertEqual([(o["gamme_id"], o["operation"]) for o in apercu["ecritures"]["gamme_operations"]["creer"]],
                         [(gammes[0]["id"], "Inspecter"), (gammes[0]["id"], "Tendre la bande")])
        self.assertEqual(apercu["ecritures"]["gammes"]["modifier"], [])


class TestSansControle(CasControles):

    def test_compteurs_sans_formulaire_et_mise_a_jour_non_demandee(self):
        # Compteurs : aucun formulaire de création dans Prévo, rien de nouveau. Mise à jour non demandée : la ligne
        # n'écrit rien (identique), le formulaire n'a pas à la juger.
        apercu = self.apercu("compteurs", ["equipement", "libelle", "unite"], [["CP-01", "Compteur de démarrages", "démarrages"]])
        self.verifier_actions(apercu, {2: "creer"})
        apercu = self.apercu("fournisseurs", ["nom", "email"], [["Fluidalpes Services", "ventes-fluidalpes"]], mettre_a_jour=False)
        self.verifier_actions(apercu, {2: "identique"})


if __name__ == "__main__":
    unittest.main()
