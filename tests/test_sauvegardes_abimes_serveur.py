"""Un fichier abîmé ne bloque jamais la sauvegarde quotidienne, côté serveur (T206b, chantier i18n-socle).

Règle de Nicolas (04/11) : « un fichier abîmé bloque l'écriture dans les données, jamais la sauvegarde quotidienne.
Une sauvegarde qui contient un fichier abîmé n'est pas un problème : le manifeste le signale ; la rotation ne doit
jamais supprimer les dernières bonnes sauvegardes : garde toujours au moins les 7 plus récentes sans fichier abîmé,
quel que soit leur âge ; tant qu'un fichier est abîmé, le bandeau du responsable rappelle depuis quand. »

Contrat T206 (identique dans les deux modes), points 1 à 4, côté serveur :
  1. ordre : la sauvegarde du jour « si besoin » passe AVANT la garde « fichier abîmé » (ecrire_fichier_de_donnees,
     et la garde de l'ajout) : une écriture refusée fait la quotidienne si elle manque, puis refuse (409
     « fichier_abime ») ; la table reste identique à l'octet ;
  2. manifeste.json : l'entrée d'un CSV abîmé (raisons_fichier_abime) porte "abime": true ; absente sinon ;
  3. rotation : une quotidienne de plus de 30 jours est gardée si elle est parmi les 7 plus récentes sans fichier
     abîmé (QUOTIDIENNES_SAINES_GARDEES) ; une marque suffit à la dire abîmée ; sans marque (manifeste sain d'après
     T206, d'avant T206, ou pas de manifeste) : ses CSV sont analysés seulement quand il faut décider (candidate à la
     suppression et moins de 7 saines retenues ; une jeune sans marque compte comme saine), rien n'y est écrit ;
  4. donnees/fichiers-abimes.json, {"depuis": {table: "AAAA-MM-JJTHH:MM:SS"}} : date à laquelle Prévo a vu la table
     abîmée la première fois ; tenu à jour au démarrage, à chaque sauvegarde et après une restauration ; jamais dans
     une sauvegarde ; GET /api/info → format.abimes_depuis.

Sans navigateur : serveur.py importé et servi dans ce processus avec une horloge simulée (config.horloge), comme
tests/test_sauvegardes_socle.py ; dossiers temporaires, jamais de données réelles.

1. TestQuaranteJours — un CSV abîmé dès J0, une écriture tentée chaque jour pendant 40 jours (409) : une quotidienne
   par jour, marquée « abime » sur ce fichier ; la rotation, comparée chaque jour à une référence écrite ici ; à J40,
   les 7 quotidiennes saines d'avant J0 restent malgré leurs plus de 30 jours, les abîmées de plus de 30 jours sont
   supprimées, les CSV sont identiques à l'octet, format.abimes_depuis donne la date de J0.
2. TestRefusSansSauvegarde — PUT et ajout refusés un jour sans sauvegarde : la quotidienne est faite (manifeste exact,
   marque comprise), les CSV identiques ; un second refus le même jour ne refait rien.
3. TestDepuisQuand — fichiers-abimes.json : date gardée aux redémarrages, table redevenue saine retirée (au démarrage,
   après une restauration de la bonne sauvegarde par POST /api/restauration), nouvelle date si elle s'abîme encore.
4. TestRotationAnalyse — sauvegardes anciennes sans marque (manifeste d'avant T206, sans manifeste) analysées à la
   rotation et jamais modifiées ; la marque suffit ; une incomplète n'est pas saine ; analyse seulement si c'est
   nécessaire (espion sur tables_abimees_de_la_sauvegarde).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_sauvegardes_abimes_serveur.py" -v
"""
import datetime
import hashlib
import json
import shutil
import unittest
from pathlib import Path
from unittest import mock

from test_sauvegardes_socle import (SERVEUR, CasDossier, ServeurDansLeProcessus, csv_de, fichiers_attendus, fichiers_de,
                                    instant, lire_manifeste)
from commun import FORMAT_COURANT

UN_JOUR = datetime.timedelta(days=1)
J0 = datetime.date(2026, 6, 1)
CODE = "fichier_abime"
NOM_FICHIERS_ABIMES = "fichiers-abimes.json"
SAINES_GARDEES = 7
JOURS_GARDES = 30


def abimer(octets):
    """Le CSV plus une ligne qui a une valeur au-delà de l'en-tête (« en trop ») : fichier abîmé."""
    largeur = octets.split(b"\r\n", 1)[0].count(b";") + 1
    return octets + ("X" + ";" * largeur + "en trop").encode("utf-8") + b"\r\n"


def version(octets):
    return hashlib.sha256(octets).hexdigest()[:16]


def a(jour, heure, minute=0):
    """Secondes de l'heure locale « jour à heure:minute »."""
    return instant(jour.year, jour.month, jour.day, heure, minute)


def iso(jour, heure, minute=0):
    return "%sT%02d:%02d:00" % (jour.isoformat(), heure, minute)


def csv_racine(donnees):
    """{nom: octets} des CSV de la racine du dossier de données."""
    return {p.name: p.read_bytes() for p in sorted(Path(donnees).glob("*.csv"))}


def quotidiennes(donnees):
    dossier = Path(donnees) / "sauvegardes"
    return sorted(p.name for p in dossier.iterdir() if SERVEUR.est_une_date(p.name)) if dossier.is_dir() else []


def lire_fichiers_abimes(donnees):
    chemin = Path(donnees) / NOM_FICHIERS_ABIMES
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else None


def rotation_de_reference(presentes, saines, jour):
    """Référence écrite ici (contrat 3) : gardées, les quotidiennes de 30 jours ou moins et les 7 plus récentes
    saines, quel que soit leur âge."""
    plus_recentes_saines = sorted((nom for nom in presentes if nom in saines), reverse=True)[:SAINES_GARDEES]
    return {nom for nom in presentes
            if (jour - datetime.date.fromisoformat(nom)).days <= JOURS_GARDES or nom in plus_recentes_saines}


class CasAbimes(CasDossier):

    def marques(self, dossier_sauvegarde):
        """Noms des fichiers marqués par le manifeste ; la marque, quand elle y est, vaut toujours true."""
        fichiers = lire_manifeste(dossier_sauvegarde)["fichiers"]
        for decrit in fichiers:
            self.assertIs(decrit.get("abime", True), True, decrit)
        return [decrit["nom"] for decrit in fichiers if "abime" in decrit]

    def demarrer(self, donnees, moment):
        """Ce que fait main avant les écouteurs, à l'heure « moment » ; rend la configuration."""
        config = SERVEUR.Configuration(str(donnees), [])
        config.horloge = lambda: moment
        SERVEUR.creer_dossiers(config)
        SERVEUR.preparer_donnees_au_demarrage(config)
        return config

    def serveur(self, donnees, moment):
        """Serveur du processus démarré comme par main (préparation des données comprise)."""
        serveur = ServeurDansLeProcessus(donnees, moment)
        self.addCleanup(serveur.arreter)
        SERVEUR.preparer_donnees_au_demarrage(serveur.config)
        return serveur

    def put(self, serveur, table, octets):
        actuel = (Path(serveur.config.dossier_donnees) / (table + ".csv")).read_bytes()
        return serveur.requete("PUT", "/api/csv/" + table, octets, {"X-Version-Attendue": version(actuel)})

    def verifier_refus(self, statut, reponse, table):
        self.assertEqual(statut, 409, reponse)
        self.assertEqual((reponse.get("code"), reponse.get("table")), (CODE, table), reponse)

    def abimes_depuis(self, serveur):
        statut, info = serveur.requete("GET", "/api/info")
        self.assertEqual(statut, 200, info)
        return info["format"]["abimes_depuis"]

    def avec_version_notee(self, donnees):
        (donnees / "derniere-version.json").write_text(json.dumps({"version": SERVEUR.VERSION_APPLICATION}),
                                                       encoding="utf-8")
        return donnees


# ---------------------------------------------------------------------------
# 1. Quarante jours avec un CSV abîmé
# ---------------------------------------------------------------------------

class TestQuaranteJours(CasAbimes):

    def test_quarante_jours_un_csv_abime_des_sauvegardes_saines_restent(self):
        donnees = self.avec_version_notee(self.donnees_d_atelier())
        serveur = self.serveur(donnees, a(J0 - 10 * UN_JOUR, 7, 30))
        presentes, saines, racine = set(), set(), None
        for numero in range(-10, 41):
            jour = J0 + numero * UN_JOUR
            nom = jour.isoformat()
            if numero == 0:                                  # J0, 8 h : equipements.csv s'abîme (Excel, à la main…)
                chemin = donnees / "equipements.csv"
                chemin.write_bytes(abimer(chemin.read_bytes()))
                racine = csv_racine(donnees)
            serveur.instant = a(jour, 9)
            if numero < 0:
                serveur.ecrire_parametres("Jour %d" % numero)        # écriture acceptée
                saines.add(nom)
            else:
                statut, reponse = self.put(serveur, "equipements",
                                           csv_de("equipements", "EQ-0001;'PO-01;Pompe du jour %d" % numero))
                self.verifier_refus(statut, reponse, "equipements")
                self.assertEqual(csv_racine(donnees), racine, "jour %d : table modifiée" % numero)
            presentes = rotation_de_reference(presentes | {nom}, saines, jour)
            self.assertEqual(quotidiennes(donnees), sorted(presentes), "jour %d" % numero)
            self.assertEqual(self.marques(donnees / "sauvegardes" / nom),
                             [] if numero < 0 else ["equipements.csv"], "jour %d" % numero)

        # J40 : les 7 saines d'avant J0 (41 à 47 jours) restent ; les abîmées de plus de 30 jours (J0 à J9) non.
        avant_j0 = [(J0 - k * UN_JOUR).isoformat() for k in range(1, SAINES_GARDEES + 1)]
        depuis_j10 = [(J0 + k * UN_JOUR).isoformat() for k in range(10, 41)]
        self.assertEqual(quotidiennes(donnees), sorted(avant_j0 + depuis_j10))
        jour_40 = J0 + 40 * UN_JOUR
        self.assertTrue(all((jour_40 - datetime.date.fromisoformat(nom)).days > JOURS_GARDES for nom in avant_j0))
        self.assertEqual(csv_racine(donnees), racine)
        self.assertEqual(self.abimes_depuis(serveur), {"equipements": iso(J0, 9)})
        self.assertEqual(lire_fichiers_abimes(donnees), {"depuis": {"equipements": iso(J0, 9)}})
        for nom in quotidiennes(donnees):                    # jamais dans une sauvegarde
            self.assertFalse((donnees / "sauvegardes" / nom / NOM_FICHIERS_ABIMES).exists(), nom)


# ---------------------------------------------------------------------------
# 2. Refus un jour sans sauvegarde
# ---------------------------------------------------------------------------

class TestRefusSansSauvegarde(CasAbimes):

    JOUR = datetime.date(2026, 6, 15)

    def test_put_refuse_fait_la_quotidienne_puis_refuse(self):
        donnees = self.donnees_d_atelier()
        (donnees / "equipements.csv").write_bytes(abimer((donnees / "equipements.csv").read_bytes()))
        avant = fichiers_de(donnees)
        serveur = ServeurDansLeProcessus(donnees, a(self.JOUR, 10))         # pas de préparation : rien ce jour-là
        self.addCleanup(serveur.arreter)
        self.assertEqual(quotidiennes(donnees), [])
        statut, reponse = self.put(serveur, "equipements", csv_de("equipements", "EQ-0001;'PO-01;Pompe"))
        self.verifier_refus(statut, reponse, "equipements")
        nom = self.JOUR.isoformat()
        self.assertEqual(quotidiennes(donnees), [nom])
        dossier = donnees / "sauvegardes" / nom
        attendus = [dict(decrit, abime=True) if decrit["nom"] == "equipements.csv" else decrit
                    for decrit in fichiers_attendus(dossier)]
        self.assertEqual(lire_manifeste(dossier)["fichiers"], attendus)
        self.assertEqual((dossier / "equipements.csv").read_bytes(), avant["equipements.csv"])
        apres = fichiers_de(donnees)
        self.assertEqual({chemin: octets for chemin, octets in apres.items()
                          if not chemin.startswith("sauvegardes/") and chemin != NOM_FICHIERS_ABIMES}, avant)
        self.assertEqual(lire_fichiers_abimes(donnees), {"depuis": {"equipements": iso(self.JOUR, 10)}})

        # Second refus le même jour : la quotidienne est là, rien ne change (elle non plus).
        serveur.instant = a(self.JOUR, 16)
        statut, reponse = self.put(serveur, "equipements", csv_de("equipements", "EQ-0001;'PO-01;Pompe"))
        self.verifier_refus(statut, reponse, "equipements")
        self.assertEqual(fichiers_de(donnees), apres)

    def test_ajout_refuse_fait_la_quotidienne_puis_refuse(self):
        donnees = self.donnees_d_atelier()
        journal = csv_de("journal", "J-1;2026-06-15 08:00;Poste;responsable;equipements;EQ-0001;ajout")
        coupe = journal + 'J-2;2026-06-15 08:01;"Poste coupé'.encode("utf-8")
        (donnees / "journal.csv").write_bytes(coupe)
        avant = csv_racine(donnees)
        serveur = ServeurDansLeProcessus(donnees, a(self.JOUR, 10))
        self.addCleanup(serveur.arreter)
        corps = ";".join(SERVEUR.COLONNES_PAR_TABLE["journal"]).encode("utf-8") + \
            b"\r\nJ-3;2026-06-15 10:00;Poste;responsable;equipements;EQ-0001;essai\r\n"
        statut, reponse = serveur.requete("POST", "/api/csv/journal/ajout", corps)
        self.verifier_refus(statut, reponse, "journal")
        nom = self.JOUR.isoformat()
        self.assertEqual(quotidiennes(donnees), [nom])
        self.assertEqual(self.marques(donnees / "sauvegardes" / nom), ["journal.csv"])
        self.assertEqual((donnees / "sauvegardes" / nom / "journal.csv").read_bytes(), coupe)
        self.assertEqual(csv_racine(donnees), avant)


# ---------------------------------------------------------------------------
# 3. Depuis quand : fichiers-abimes.json et /api/info
# ---------------------------------------------------------------------------

class TestDepuisQuand(CasAbimes):

    def test_date_gardee_au_redemarrage_retiree_apres_restauration(self):
        donnees = self.avec_version_notee(self.donnees_d_atelier())
        j1, j2, j3 = (J0 + k * UN_JOUR for k in (1, 2, 3))
        equipements = donnees / "equipements.csv"
        techniciens = donnees / "techniciens.csv"
        sain = equipements.read_bytes()

        self.demarrer(donnees, a(J0, 7, 30))                     # J0 : tout est sain, quotidienne saine
        self.assertIsNone(lire_fichiers_abimes(donnees))
        equipements.write_bytes(abimer(sain))
        self.demarrer(donnees, a(j1, 8))                         # J1 : vu abîmé (quotidienne du démarrage)
        self.assertEqual(lire_fichiers_abimes(donnees), {"depuis": {"equipements": iso(j1, 8)}})
        techniciens_sain = csv_de("techniciens", "TEC-0001;Martin;Camille;Mécanicien;30;35;1")
        techniciens.write_bytes(abimer(techniciens_sain))
        self.demarrer(donnees, a(j2, 9, 15))                     # J2 : date de J1 gardée, techniciens ajouté
        self.assertEqual(lire_fichiers_abimes(donnees),
                         {"depuis": {"equipements": iso(j1, 8), "techniciens": iso(j2, 9, 15)}})
        techniciens.write_bytes(techniciens_sain)
        self.demarrer(donnees, a(j2, 10))                        # même jour (pas de quotidienne) : redevenu sain
        self.assertEqual(lire_fichiers_abimes(donnees), {"depuis": {"equipements": iso(j1, 8)}})

        serveur = self.serveur(donnees, a(j2, 11))
        self.assertEqual(self.abimes_depuis(serveur), {"equipements": iso(j1, 8)})
        statut, resultat = serveur.requete("POST", "/api/restauration",
                                           {"sauvegarde": J0.isoformat(), "tables": ["equipements"]})
        self.assertEqual(statut, 200, resultat)
        self.assertEqual(equipements.read_bytes(), sain)
        self.assertEqual(self.marques(donnees / "sauvegardes" / resultat["copie_securite"]), ["equipements.csv"])
        self.assertIsNone(lire_fichiers_abimes(donnees))         # plus rien d'abîmé : fichier retiré
        self.assertEqual(self.abimes_depuis(serveur), {})

        equipements.write_bytes(abimer(sain))                    # J3 : abîmé de nouveau, nouvelle date
        self.demarrer(donnees, a(j3, 8))
        self.assertEqual(lire_fichiers_abimes(donnees), {"depuis": {"equipements": iso(j3, 8)}})
        for chemin in (donnees / "sauvegardes").rglob(NOM_FICHIERS_ABIMES):
            self.fail("fichiers-abimes.json dans une sauvegarde : %s" % chemin)

    def test_date_illisible_remplacee_et_api_info_sans_rien_d_abime(self):
        donnees = self.avec_version_notee(self.donnees_d_atelier())
        serveur = self.serveur(donnees, a(J0, 8))
        self.assertEqual(self.abimes_depuis(serveur), {})
        self.assertIsNone(lire_fichiers_abimes(donnees))
        (donnees / NOM_FICHIERS_ABIMES).write_text('{"depuis": {"equipements": "hier"}}', encoding="utf-8")
        equipements = donnees / "equipements.csv"
        equipements.write_bytes(abimer(equipements.read_bytes()))
        self.demarrer(donnees, a(J0, 9))
        self.assertEqual(lire_fichiers_abimes(donnees), {"depuis": {"equipements": iso(J0, 9)}})


# ---------------------------------------------------------------------------
# 4. Rotation : sauvegardes anciennes sans marque
# ---------------------------------------------------------------------------

class TestRotationAnalyse(CasAbimes):

    JOUR = datetime.date(2026, 6, 15)

    def fausse_quotidienne(self, donnees, age, abimee=False, manifeste=False, marque=False, en_cours=False):
        """Quotidienne vieille de « age » jours : parametres.csv et equipements.csv (abîmé ou non) ; manifeste.json
        (comme ceux d'avant T206, sans marque) si « manifeste », marque « abime » sur equipements.csv si « marque »."""
        nom = (self.JOUR - age * UN_JOUR).isoformat()
        dossier = donnees / "sauvegardes" / nom
        dossier.mkdir(parents=True)
        equipements = csv_de("equipements", "EQ-0001;'PO-01;Pompe " + nom)
        (dossier / "parametres.csv").write_bytes(csv_de("parametres", "version_schema;'%d" % FORMAT_COURANT, "entreprise_nom;" + nom))
        (dossier / "equipements.csv").write_bytes(abimer(equipements) if abimee else equipements)
        if manifeste or marque:
            fichiers = [dict(decrit, abime=True) if marque and decrit["nom"] == "equipements.csv" else decrit
                        for decrit in fichiers_attendus(dossier)]
            contenu = {"application": "Prévo", "version_appli": "2.0.0", "format": 3, "date": nom + "T08:00:00",
                       "motif": "quotidienne", "mode": "serveur", "fichiers": fichiers}
            (dossier / "manifeste.json").write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8")
        if en_cours:
            (dossier / ".en-cours").write_bytes(b"")
        return nom

    def faire_la_quotidienne(self, donnees):
        """La quotidienne du jour (et sa rotation) ; rend les noms des sauvegardes dont la rotation a analysé les CSV."""
        config = SERVEUR.Configuration(str(donnees), [])
        config.horloge = lambda: a(self.JOUR, 9)
        SERVEUR.creer_dossiers(config)
        espion = mock.patch.object(SERVEUR, "tables_abimees_de_la_sauvegarde",
                                   wraps=SERVEUR.tables_abimees_de_la_sauvegarde)
        with espion as analyse, SERVEUR.VERROU_ECRITURE:
            self.assertEqual(SERVEUR.faire_sauvegarde_du_jour(config), self.JOUR.isoformat())
        return {Path(appel.args[0]).name for appel in analyse.call_args_list}

    def test_anciennes_sans_marque_analysees_jamais_modifiees(self):
        donnees = self.donnees_d_atelier()
        avant_t206_abimee = self.fausse_quotidienne(donnees, 40, abimee=True, manifeste=True)
        avant_t206_saine = self.fausse_quotidienne(donnees, 41, manifeste=True)
        sans_manifeste_saine = self.fausse_quotidienne(donnees, 42)
        sans_manifeste_abimee = self.fausse_quotidienne(donnees, 43, abimee=True)
        marquee = self.fausse_quotidienne(donnees, 44, marque=True)        # la marque suffit (contenu sain)
        incomplete = self.fausse_quotidienne(donnees, 45, en_cours=True)
        gardees = [avant_t206_saine, sans_manifeste_saine]
        avant = {nom: fichiers_de(donnees / "sauvegardes" / nom) for nom in gardees}
        analysees = self.faire_la_quotidienne(donnees)
        # Saines : celle du jour (jeune, sans marque : comptée sans analyse) et les deux anciennes saines ; moins de 7 :
        # chaque ancienne sans marque est analysée ; la marquée et l'incomplète ne le sont pas.
        self.assertEqual(quotidiennes(donnees), sorted(gardees + [self.JOUR.isoformat()]))
        for nom in gardees:                                       # jamais modifiées (manifeste compris)
            self.assertEqual(fichiers_de(donnees / "sauvegardes" / nom), avant[nom], nom)
        self.assertEqual(analysees, {avant_t206_abimee, avant_t206_saine, sans_manifeste_saine, sans_manifeste_abimee})
        self.assertFalse({marquee, incomplete} & set(quotidiennes(donnees)))

    def test_analyse_seulement_si_necessaire(self):
        # Aucune quotidienne de plus de 30 jours : rien à décider, rien d'analysé.
        donnees = self.donnees_d_atelier()
        jeunes = [self.fausse_quotidienne(donnees, age) for age in range(1, 7)]
        self.assertEqual(self.faire_la_quotidienne(donnees), set())
        # Les 7 saines déjà retenues parmi les jeunes (celle du jour et 6, sans marque : sans analyse) : les anciennes
        # sont supprimées sans être analysées.
        anciennes = [self.fausse_quotidienne(donnees, age) for age in (31, 40)]
        shutil.rmtree(donnees / "sauvegardes" / self.JOUR.isoformat())
        self.assertEqual(self.faire_la_quotidienne(donnees), set())
        self.assertEqual(quotidiennes(donnees), sorted(jeunes + [self.JOUR.isoformat()]))
        self.assertFalse(set(anciennes) & set(quotidiennes(donnees)))

        # 6 saines retenues (celle du jour, et 5 jeunes dont une abîmée sans marque, comptée sans analyse) : les
        # anciennes sont analysées jusqu'à la 7e saine (32 jours), les suivantes supprimées sans analyse.
        donnees = self.donnees_d_atelier("donnees-2")
        jeunes = [self.fausse_quotidienne(donnees, age, abimee=age == 2) for age in range(1, 6)]
        abimee_31 = self.fausse_quotidienne(donnees, 31, abimee=True)
        saine_32 = self.fausse_quotidienne(donnees, 32, manifeste=True)
        suivantes = [self.fausse_quotidienne(donnees, 33), self.fausse_quotidienne(donnees, 34, abimee=True)]
        self.assertEqual(self.faire_la_quotidienne(donnees), {abimee_31, saine_32})
        self.assertEqual(quotidiennes(donnees), sorted(jeunes + [saine_32, self.JOUR.isoformat()]))
        self.assertFalse(set(suivantes) & set(quotidiennes(donnees)))


if __name__ == "__main__":
    unittest.main()
