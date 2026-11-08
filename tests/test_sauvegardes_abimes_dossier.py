"""Sauvegardes et fichier abîmé, côté navigateur (chantier i18n-socle, tâche T206a ; contrat commun de T206).

Règle de Nicolas (04/11) : « un fichier abîmé bloque l'écriture dans les données, jamais la sauvegarde quotidienne.
Une sauvegarde qui contient un fichier abîmé n'est pas un problème : le manifeste le signale (marque « abîmé » sur ce
fichier) ; la rotation ne doit jamais supprimer les dernières bonnes sauvegardes : garde toujours au moins les 7 plus
récentes sans fichier abîmé, quel que soit leur âge ; tant qu'un fichier est abîmé, le bandeau du responsable rappelle
depuis quand. »

    1. TestQuaranteJoursDossier : horloge du navigateur simulée (contexte.clock), J0 = 01/10/2026 (changement d'heure du
       25/10 dans l'intervalle). 9 quotidiennes saines avant J0 : J-9 à J-5 d'avant T206 (sans manifeste : analysées à
       la rotation, jamais modifiées), J-4 à J-1 faites par Prévo (une écriture réussie par jour). À J0,
       ordres_travail.csv est abîmé (une valeur au-delà de l'en-tête), vu à l'ouverture ; puis une écriture refusée
       chaque jour jusqu'à J40 : une quotidienne par jour, ordres_travail.csv marqué « abime » dans son manifeste,
       fichiers-abimes.json garde la date de J0. À J40 : les 7 saines les plus récentes restent malgré leurs plus de
       30 jours, les 2 plus anciennes et les abîmées de plus de 30 jours sont supprimées ; la table est identique à
       l'octet ; le responsable voit « Fichier abîmé : ordres_travail.csv, depuis le 01/10/2026 (40 jours). ».
    2. TestRefusUnJourSansSauvegarde : enregistrer puis ajouter refusés (ordres_travail.csv et journal.csv abîmés),
       chacun un jour sans sauvegarde : la quotidienne est faite, les deux CSV y sont marqués, les CSV identiques.
    3. TestFichiersAbimesJson : jamais créé tant qu'aucune table n'est abîmée ; date gardée d'un jour à l'autre
       (ouvertures, sauvegarde) ; table retirée après la restauration de la bonne sauvegarde ; jamais dans une
       sauvegarde ; ensuite, aucun bandeau « Fichier abîmé ».
    4. TestBandeauServeur : mode serveur, le bandeau du responsable lit /api/info (format.abimes_depuis) ; la date est
       préparée dans fichiers-abimes.json de la copie (12 jours avant aujourd'hui). Ce test dépend du serveur (T206b) :
       il échoue tant que serveur.py ne donne pas abimes_depuis.

Règle numéro un : jamais de données réelles (copies des jeux de tests/fixtures/formats/, dans l'OPFS du navigateur de
test ou dans un dossier temporaire).

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_sauvegardes_abimes_dossier.py" -v
"""
import base64
import datetime
import json
import unittest

from commun import ServeurPrevo
from test_garde_abime_navigateur import AJOUTER_DIRECT_JS, ENREGISTRER_DIRECT_JS, avec_ligne_coupee
from test_garde_abime_saisie import avec_valeur_en_trop
from test_recette_socle import (DERNIERE_VERSION, ECRIRE_OPFS_JS, MANIFESTE, MOTIF_QUOTIDIENNE, NOM_DOSSIER,
                                VERSION_APPLI, CasRecetteSocle, csv_de_la_racine, fichiers_du_jeu, requete_json,
                                sauvegardes)

FICHIERS_ABIMES = "fichiers-abimes.json"
J0 = datetime.date(2026, 10, 1)

# Textes des bandeaux de la coque (blancs réduits).
BANDEAUX_JS = """() => Array.from(document.querySelectorAll('#alertes-app > *'))
  .map((e) => e.textContent.replace(/\\s+/g, ' ').trim())"""

# Noms des sauvegardes, manifeste de l'une d'elles (ou null) et fichiers-abimes.json (ou null), lus dans l'OPFS.
ETAT_JS = """async ([nom, sauvegarde]) => {
  const racine = await (await navigator.storage.getDirectory()).getDirectoryHandle(nom, { create: true });
  const lireJson = async (dossier, fichier) => {
    try { return JSON.parse(await (await (await dossier.getFileHandle(fichier)).getFile()).text()); }
    catch (erreur) { return null; }
  };
  let dossier = null;
  try { dossier = await racine.getDirectoryHandle('sauvegardes'); } catch (erreur) { dossier = null; }
  const noms = [];
  if (dossier) {
    for await (const entree of dossier.values()) { if (entree.kind === 'directory') noms.push(entree.name); }
  }
  const manifeste = dossier && sauvegarde && noms.includes(sauvegarde)
    ? await lireJson(await dossier.getDirectoryHandle(sauvegarde), 'manifeste.json') : null;
  return { noms: noms.sort(), manifeste: manifeste, abimes: await lireJson(racine, 'fichiers-abimes.json') };
}"""

PROFIL_RESPONSABLE_JS = """() => { localStorage.setItem('prevo.profil', JSON.stringify(
  { type: 'responsable', nom: 'Claire Recette', technicienId: '' })); }"""


def jour(decalage, depart=J0):
    return depart + datetime.timedelta(days=decalage)


def jeu_de_depart():
    """f3-v1.2.0 (format courant), version de l'appli déjà notée : aucune sauvegarde « avant-… » à l'ouverture."""
    fichiers = fichiers_du_jeu("f3-v1.2.0")
    fichiers[DERNIERE_VERSION] = json.dumps({"version": VERSION_APPLI, "depuis": "2026-01-01T08:00:00"}).encode()
    return fichiers


def marques(manifeste):
    """Fichiers marqués « abime »: true dans un manifeste."""
    return sorted(fichier["nom"] for fichier in manifeste["fichiers"] if fichier.get("abime") is True)


class CasAbimesDossier(CasRecetteSocle):

    def setUp(self):
        super().setUp()
        self.demarrer_statique()

    def a_la_date(self, date):
        self.contexte.clock.set_system_time(date.isoformat() + "T09:00:00")
        self.assertEqual(self.page.evaluate("Donnees.aujourdhui()"), date.isoformat())

    def etat(self, sauvegarde=None):
        return self.page.evaluate(ETAT_JS, [NOM_DOSSIER, sauvegarde])

    def ecrire_dans_le_dossier(self, fichiers):
        """Fichiers changés dans le dossier par un autre programme (Excel…), l'application ouverte."""
        envoyes = {chemin: base64.b64encode(octets).decode("ascii") for chemin, octets in fichiers.items()}
        self.page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, envoyes])

    def ecrire(self, table):
        """Enregistrement direct de la table (contenu inchangé) par l'adaptateur : rend le résultat."""
        return self.page.evaluate(ENREGISTRER_DIRECT_JS, [table, None])

    def refuser(self, resultat):
        self.assertFalse(resultat["ok"], resultat)
        self.assertTrue(resultat["abime"], resultat)

    def passer_responsable(self):
        self.page.evaluate(PROFIL_RESPONSABLE_JS)
        self.rouvrir_dossier()
        self.assertEqual(self.page.evaluate("App.profil.type"), "responsable")

    def bandeaux_abimes(self):
        return [texte for texte in self.page.evaluate(BANDEAUX_JS) if "abîmé" in texte]

    def verifier_hors_des_sauvegardes(self, fichiers):
        dans_une_sauvegarde = [chemin for chemin in fichiers
                               if chemin.startswith("sauvegardes/") and chemin.endswith("/" + FICHIERS_ABIMES)]
        self.assertEqual(dans_une_sauvegarde, [])


# ---------------------------------------------------------------------------
# 1. Quarante jours avec un fichier abîmé
# ---------------------------------------------------------------------------

class TestQuaranteJoursDossier(CasAbimesDossier):

    def test_quarante_jours_une_quotidienne_par_jour_et_sept_saines_gardees(self):
        fichiers = jeu_de_depart()
        sains = csv_de_la_racine(fichiers)
        anciennes = [jour(n).isoformat() for n in range(-9, -4)]             # J-9 à J-5 : d'avant T206, sans manifeste
        for nom in anciennes:
            fichiers.update({"sauvegardes/%s/%s" % (nom, chemin): octets for chemin, octets in sains.items()})
        self.contexte.clock.install(time=jour(-4).isoformat() + "T09:00:00")
        self.ouvrir_dossier(fichiers, "demandeur")

        # J-4 à J-1 : une écriture réussie par jour → une quotidienne saine faite par Prévo (manifeste sans marque).
        for n in range(-4, 0):
            self.a_la_date(jour(n))
            resultat = self.ecrire("equipements")
            self.assertTrue(resultat["ok"], resultat)
            etat = self.etat(jour(n).isoformat())
            self.assertIsNotNone(etat["manifeste"], jour(n))
            self.assertEqual(marques(etat["manifeste"]), [], jour(n))
            self.assertIsNone(etat["abimes"], "fichiers-abimes.json créé sans table abîmée")

        # J0 : ordres_travail.csv abîmé par un autre programme, vu à l'ouverture.
        self.a_la_date(J0)
        abime = avec_valeur_en_trop(self.instantane()["ordres_travail.csv"])
        self.ecrire_dans_le_dossier({"ordres_travail.csv": abime})
        self.rouvrir_dossier()
        self.assertEqual(self.page.evaluate("Donnees.aujourdhui()"), J0.isoformat())
        self.assertIn("ordres_travail", self.page.evaluate("Donnees.tablesAbimees()"))
        depuis = (self.etat()["abimes"] or {}).get("depuis")
        self.assertEqual(sorted(depuis or {}), ["ordres_travail"], depuis)
        self.assertTrue(depuis["ordres_travail"].startswith(J0.isoformat() + "T"), depuis)

        # J0 à J40 : une écriture refusée chaque jour → la quotidienne du jour, avec la marque ; date de J0 gardée.
        for n in range(0, 41):
            date = jour(n).isoformat()
            self.a_la_date(jour(n))
            self.refuser(self.ecrire("ordres_travail"))
            etat = self.etat(date)
            self.assertIn(date, etat["noms"], "quotidienne du %s absente après le refus" % date)
            self.assertEqual(marques(etat["manifeste"]), ["ordres_travail.csv"], date)
            self.assertEqual(etat["abimes"], {"depuis": depuis}, date)

        # J40 : 7 quotidiennes saines gardées (plus de 30 jours), abîmées de plus de 30 jours supprimées.
        apres = self.instantane()
        self.assertEqual(apres["ordres_travail.csv"], abime, "table abîmée réécrite")
        quotidiennes = sorted(nom for nom in sauvegardes(apres) if MOTIF_QUOTIDIENNE.match(nom))
        saines = [jour(n).isoformat() for n in range(-7, 0)]
        abimees = [jour(n).isoformat() for n in range(10, 41)]
        self.assertEqual(quotidiennes, sorted(saines + abimees))
        for nom in saines:
            self.assertGreater((jour(40) - datetime.date.fromisoformat(nom)).days, 30, nom)
        for nom in [n for n in anciennes if n in saines]:                     # jamais modifiées par la rotation
            self.assertEqual(sauvegardes(apres)[nom], sains, nom)
        self.verifier_hors_des_sauvegardes(apres)

        # Le responsable ouvre Prévo à J40 : le bandeau dit depuis quand.
        self.passer_responsable()
        bandeaux = [texte for texte in self.bandeaux_abimes() if "ordres_travail.csv" in texte]
        self.assertEqual(len(bandeaux), 1, self.bandeaux_abimes())
        self.assertIn("Fichier abîmé : ordres_travail.csv, depuis le 01/10/2026 (40 jours).", bandeaux[0])
        self.assertEqual(self.instantane()["ordres_travail.csv"], abime)


# ---------------------------------------------------------------------------
# 2. Refus un jour sans sauvegarde
# ---------------------------------------------------------------------------

class TestRefusUnJourSansSauvegarde(CasAbimesDossier):

    def test_enregistrer_puis_ajouter_refuses_la_quotidienne_est_faite_avec_la_marque(self):
        origine = jeu_de_depart()
        origine["ordres_travail.csv"] = avec_valeur_en_trop(origine["ordres_travail.csv"])
        origine["journal.csv"] = avec_ligne_coupee(origine["journal.csv"])
        depart = datetime.date(2026, 3, 2)
        self.contexte.clock.install(time=depart.isoformat() + "T09:00:00")
        self.ouvrir_dossier(origine, "demandeur")
        appels = [("enregistrer", lambda: self.ecrire("ordres_travail")),
                  ("ajouter", lambda: self.page.evaluate(AJOUTER_DIRECT_JS))]
        for n, (nom, appel) in enumerate(appels, start=1):
            with self.subTest(appel=nom):
                date = jour(n, depart).isoformat()
                self.a_la_date(jour(n, depart))
                self.assertNotIn(date, self.etat()["noms"], "jour déjà sauvegardé avant l'appel")
                self.refuser(appel())
                etat = self.etat(date)
                self.assertIn(date, etat["noms"], "sauvegarde du jour absente après le refus")
                self.assertEqual(marques(etat["manifeste"]), ["journal.csv", "ordres_travail.csv"])
                apres = self.instantane()
                self.assertEqual(csv_de_la_racine(apres), csv_de_la_racine(origine))
                copie = sauvegardes(apres)[date]
                self.assertEqual(copie["ordres_travail.csv"], origine["ordres_travail.csv"])
                self.assertEqual(copie["journal.csv"], origine["journal.csv"])


# ---------------------------------------------------------------------------
# 3. fichiers-abimes.json : date gardée, table retirée après restauration
# ---------------------------------------------------------------------------

class TestFichiersAbimesJson(CasAbimesDossier):

    def test_date_gardee_d_un_jour_a_l_autre_puis_table_retiree_apres_restauration(self):
        origine = jeu_de_depart()
        depart = datetime.date(2026, 3, 2)
        self.contexte.clock.install(time=depart.isoformat() + "T09:00:00")
        self.ouvrir_dossier(origine, "demandeur")
        self.assertTrue(self.ecrire("equipements")["ok"])                     # la bonne sauvegarde : quotidienne saine
        bonne = depart.isoformat()
        self.assertEqual(marques(self.etat(bonne)["manifeste"]), [])
        self.assertNotIn(FICHIERS_ABIMES, self.instantane(), "créé alors qu'aucune table n'est abîmée")

        # Lendemain : equipements.csv abîmé par un autre programme, vu à l'ouverture.
        self.a_la_date(jour(1, depart))
        abime = avec_valeur_en_trop(origine["equipements.csv"])
        self.ecrire_dans_le_dossier({"equipements.csv": abime})
        self.rouvrir_dossier()
        depuis = (self.etat()["abimes"] or {}).get("depuis") or {}
        self.assertEqual(sorted(depuis), ["equipements"], depuis)
        self.assertTrue(depuis["equipements"].startswith(jour(1, depart).isoformat() + "T"), depuis)

        # Surlendemain : nouvelle ouverture, puis une écriture refusée (quotidienne marquée) : la date ne bouge pas.
        self.a_la_date(jour(2, depart))
        self.rouvrir_dossier()
        self.assertEqual(self.etat()["abimes"], {"depuis": depuis})
        self.refuser(self.ecrire("equipements"))
        etat = self.etat(jour(2, depart).isoformat())
        self.assertEqual(marques(etat["manifeste"]), ["equipements.csv"])
        self.assertEqual(etat["abimes"], {"depuis": depuis})

        # Restauration de la bonne sauvegarde : equipements.csv redevient sain → retiré de fichiers-abimes.json ;
        # la copie de sécurité (avant-restauration) porte la marque ; le fichier n'est dans aucune sauvegarde.
        resultat = self.page.evaluate("(nom) => App.adaptateur.restaurer(nom)", bonne)
        apres = self.instantane()
        self.assertEqual(apres["equipements.csv"], origine["equipements.csv"])
        self.assertEqual(json.loads(apres[FICHIERS_ABIMES].decode("utf-8")), {"depuis": {}})
        securite = sauvegardes(apres)[resultat["copieSecurite"]]
        self.assertEqual(marques(json.loads(securite[MANIFESTE].decode("utf-8"))), ["equipements.csv"])
        self.verifier_hors_des_sauvegardes(apres)

        # Ouverture suivante, responsable : aucun bandeau « Fichier abîmé », fichiers-abimes.json inchangé.
        self.passer_responsable()
        self.assertEqual(self.bandeaux_abimes(), [])
        self.assertEqual(json.loads(self.instantane()[FICHIERS_ABIMES].decode("utf-8")), {"depuis": {}})


# ---------------------------------------------------------------------------
# 4. Mode serveur : le bandeau lit /api/info (dépend de T206b, serveur.py)
# ---------------------------------------------------------------------------

class TestBandeauServeur(CasRecetteSocle):

    def test_bandeau_du_responsable_depuis_api_info(self):
        source = self.jeu("f3-v1.2.0")
        (source / "demandes.csv").write_bytes(avec_valeur_en_trop((source / "demandes.csv").read_bytes()))
        vu_le = datetime.date.today() - datetime.timedelta(days=12)
        date = vu_le.isoformat() + "T08:00:00"
        (source / FICHIERS_ABIMES).write_text(json.dumps({"depuis": {"demandes": date}}), encoding="utf-8")
        with ServeurPrevo(source=source) as serveur:
            self.ouvrir_serveur(serveur.url, "responsable")
            bandeaux = [texte for texte in self.page.evaluate(BANDEAUX_JS) if "demandes.csv" in texte]
            info = requete_json(serveur.url + "/api/info")
            self.page.goto("about:blank")
        self.assertEqual(len(bandeaux), 1, bandeaux)
        self.assertEqual((info.get("format") or {}).get("abimes_depuis"), {"demandes": date},
                         "/api/info ne donne pas format.abimes_depuis (serveur.py : T206b)")
        self.assertIn("Fichier abîmé : demandes.csv, depuis le %s (12 jours)." % vu_le.strftime("%d/%m/%Y"), bandeaux[0])


if __name__ == "__main__":
    unittest.main()
