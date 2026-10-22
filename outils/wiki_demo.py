"""Synthèses du wiki de la démo (lot 6, ARCHITECTURE.md §20.8, décision D98 de Nicolas).

Les synthèses de la démo sont rédigées par des sous-agents Claude Code « dans les conditions exactes de
l'API » : Prévo construit la requête réelle (consigne de js/modules/ia-prompts.js + données de
l'équipement), un sous-agent par requête ne reçoit qu'elle et répond comme l'API, puis la réponse
repasse par le circuit normal de Prévo (Ia.lireReponse : forme, OT cités, contrôles du §20.4). Une
réponse refusée est un défaut de la fonction, corrigé dans le code ; aucun texte n'est retouché à la main.
Nicolas relit ensuite et valide.

    py outils/wiki_demo.py exporter                    requêtes → .chantier/wiki-demo/requetes/<repère>.json
    py outils/wiki_demo.py importer --modele LIBELLE   réponses brutes (reponses/<repère>.txt) → verdicts.json
                                                       et, si toutes sont acceptées, outils/demo_wiki_syntheses.csv
                                                       (synthèses « à valider »)
    py outils/wiki_demo.py message REPÈRE              ce que reçoit le sous-agent (phrase fixe + requête)
    py outils/wiki_demo.py relecture                   page de relecture → .chantier/wiki-demo/relecture.html
    py outils/wiki_demo.py valider [REPÈRE…] [--a-valider REPÈRE…]
                                                       choix de Nicolas appliqués au fichier figé

Les calculs se font dans Chromium (Playwright, outil de développement comme les tests), sur les CSV de
donnees/demo tels quels (dates non décalées) et l'horloge fixée à la date de référence de la démo.
outils/generer_demo.py reprend ensuite le fichier figé sans jamais le régénérer.
"""
import argparse
import csv
import html
import io
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DEMO = RACINE / "donnees" / "demo"
DOSSIER_TRAVAIL = RACINE / ".chantier" / "wiki-demo"
FICHIER_FIGE = RACINE / "outils" / "demo_wiki_syntheses.csv"
DATE_REFERENCE = "2026-10-19"                      # = DATE_REFERENCE de outils/generer_demo.py
HEURE_PROPOSITION = DATE_REFERENCE + " 09:00"
HEURE_VALIDATION = DATE_REFERENCE + " 10:00"
VALIDATEUR = "Responsable"                         # profil du journal de la démo (responsable fictif)
FONCTION = "syntheseWiki"
PHRASE_FIXE = "Réponds exactement comme l'API à cette requête, sans utiliser d'outil."
SCRIPTS = ["js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/stockage-demo.js", "js/interface.js",
           "js/modules/causes-frequentes.js", "js/modules/indicateurs-regles.js", "js/modules/ia.js",
           "js/modules/ia-prompts.js", "js/modules/wiki-regles.js", "js/modules/wiki-synthese.js"]
# Contrôle propre à la démo : ses dates sont décalées jusqu'à aujourd'hui à l'ouverture, un texte figé ne
# doit donc citer aucune date, aucun mois, aucune année (la consigne le demande ; une réponse qui le fait
# est un défaut de la fonction).
MOTIF_CITATION = re.compile(r"\[OT-\d{4}-\d{4,}\]")
# Années 2010 à 2039 seulement : « entretien des 2000 heures » n'est pas une date.
MOTIF_DATE = re.compile(r"\b20[1-3]\d\b|\b\d{1,2}/\d{1,2}\b|\b(?:janvier|février|fevrier|mars|avril|mai|juin|"
                        r"juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\b", re.IGNORECASE)

OUVRIR_JS = """async (tables) => {
  const adaptateur = StockageDemo.creer(tables);
  Donnees.initialiser(adaptateur, { poste: 'Outil wiki_demo', profil: 'Responsable' });
  await Donnees.chargerTout();
}"""

LIRE_JS = """([contenu, donnees]) => {
  try {
    return { accepte: true, resultat: Ia.lireReponse('syntheseWiki', contenu, donnees) };
  } catch (erreur) {
    return { accepte: false, raisons: [erreur.name + ' : ' + erreur.message] };
  }
}"""


def tables_de_la_demo():
    return {chemin.stem: chemin.read_text(encoding="utf-8-sig") for chemin in sorted(DOSSIER_DEMO.glob("*.csv"))}


def avec_page(travail):
    """Ouvre Chromium sur une page vide, charge les scripts de Prévo et la démo (CSV tels quels)."""
    from playwright.sync_api import sync_playwright   # outil de développement, comme les tests
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        try:
            contexte = navigateur.new_context()
            contexte.clock.set_fixed_time(DATE_REFERENCE + "T12:00:00")
            page = contexte.new_page()
            erreurs = []
            page.on("pageerror", lambda erreur: erreurs.append(str(erreur)))
            page.set_content("<!DOCTYPE html><html lang='fr'><body><main id='contenu'></main></body></html>")
            for script in SCRIPTS:
                page.add_script_tag(path=str(RACINE / script))
            page.evaluate(OUVRIR_JS, tables_de_la_demo())
            if erreurs:
                raise SystemExit("Erreur JavaScript : " + " ; ".join(erreurs))
            return travail(page)
        finally:
            navigateur.close()


def nom_de_fichier(repere):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", repere)


def exporter(_arguments):
    requetes = avec_page(lambda page: page.evaluate("() => Wiki.requetesDemo({ maintenant: '%s 12:00' })" % DATE_REFERENCE))
    dossier = DOSSIER_TRAVAIL / "requetes"
    dossier.mkdir(parents=True, exist_ok=True)
    for ancien in dossier.glob("*.json"):
        ancien.unlink()
    index = []
    for element in requetes:
        fichier = dossier / (nom_de_fichier(element["repere"]) + ".json")
        fichier.write_text(json.dumps({"fonction": FONCTION, "equipementId": element["equipementId"],
                                       "repere": element["repere"], "requete": element["requete"],
                                       "donnees": element["donnees"]}, ensure_ascii=False, indent=2), encoding="utf-8")
        index.append({"repere": element["repere"], "equipementId": element["equipementId"], "fichier": fichier.name,
                      "ot": len(element["donnees"]["ot"])})
    (DOSSIER_TRAVAIL / "requetes.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print("%d requêtes écrites dans %s" % (len(index), dossier))
    for element in index:
        print("  %-10s %-8s %3d OT clôturés" % (element["repere"], element["equipementId"], element["ot"]))
    return 0


def message_pour_sous_agent(requete):
    """Ce que reçoit le sous-agent : la phrase fixe, puis le JSON de la requête (messages et schéma), rien d'autre."""
    return PHRASE_FIXE + "\n\n" + json.dumps(requete, ensure_ascii=False, indent=2)


def message(arguments):
    for requete in lire_requetes():
        if requete["repere"] == arguments.repere:
            print(message_pour_sous_agent(requete["requete"]))
            return 0
    raise SystemExit("Repère inconnu : %s" % arguments.repere)


def lire_requetes():
    index = json.loads((DOSSIER_TRAVAIL / "requetes.json").read_text(encoding="utf-8"))
    return [json.loads((DOSSIER_TRAVAIL / "requetes" / e["fichier"]).read_text(encoding="utf-8")) for e in index]


def importer(arguments):
    requetes = lire_requetes()
    a_lire = []
    for requete in requetes:
        fichier = DOSSIER_TRAVAIL / "reponses" / (nom_de_fichier(requete["repere"]) + ".txt")
        if not fichier.is_file():
            raise SystemExit("Réponse manquante : %s" % fichier)
        a_lire.append((requete, fichier.read_text(encoding="utf-8")))

    def lire(page):
        return [page.evaluate(LIRE_JS, [contenu, requete["donnees"]]) for requete, contenu in a_lire]
    lectures = avec_page(lire)

    verdicts = []
    for (requete, _contenu), lecture in zip(a_lire, lectures):
        verdict = {"repere": requete["repere"], "equipementId": requete["equipementId"], "accepte": lecture["accepte"]}
        if lecture["accepte"]:
            texte = lecture["resultat"]["texte"]
            sans_citations = MOTIF_CITATION.sub(" ", texte)          # « [OT-2026-0012] » n'est pas une date
            dates = sorted(set(m.group(0) for m in MOTIF_DATE.finditer(sans_citations)))
            if dates:
                verdict.update(accepte=False, raisons=["date écrite dans la synthèse (la démo décale ses dates) : "
                                                       + ", ".join(dates)])
            verdict.update(texte=texte, otCites=lecture["resultat"]["otCites"], otSources=lecture["resultat"]["otSources"])
        else:
            verdict["raisons"] = lecture["raisons"]
        verdicts.append(verdict)
    (DOSSIER_TRAVAIL / "verdicts.json").write_text(json.dumps(verdicts, ensure_ascii=False, indent=2), encoding="utf-8")
    refusees = [v for v in verdicts if not v["accepte"]]
    print("%d réponses lues : %d acceptées, %d refusées" % (len(verdicts), len(verdicts) - len(refusees), len(refusees)))
    for verdict in refusees:
        print("  REFUSÉE %s : %s" % (verdict["repere"], " ; ".join(verdict["raisons"])))
    if refusees:
        print("Rien n'est écrit dans %s : corriger la fonction, réexporter et rejouer les requêtes refusées." % FICHIER_FIGE.name)
        return 1
    ecrire_fige(verdicts, arguments.modele)
    print("Fichier figé écrit : %s (%d synthèses « à valider »)" % (FICHIER_FIGE, len(verdicts)))
    return 0


CHAMPS = ["id", "equipement_id", "texte", "ot_cites", "ot_sources", "statut", "modele", "date_proposition",
          "corrigee_par", "date_modification", "valide_par", "date_validation"]


def ecrire_lignes(lignes):
    """CSV au format de Prévo (§3.1) : BOM, « ; », fins de ligne CRLF, guillemets si besoin."""
    sortie = io.StringIO()
    ecrivain = csv.DictWriter(sortie, fieldnames=CHAMPS, delimiter=";", lineterminator="\r\n")
    ecrivain.writeheader()
    for ligne in lignes:
        ecrivain.writerow({champ: ligne.get(champ, "") for champ in CHAMPS})
    FICHIER_FIGE.write_bytes(b"\xef\xbb\xbf" + sortie.getvalue().encode("utf-8"))


def lire_fige():
    return list(csv.DictReader(io.StringIO(FICHIER_FIGE.read_text(encoding="utf-8-sig")), delimiter=";"))


def ecrire_fige(verdicts, modele):
    lignes = []
    for numero, verdict in enumerate(verdicts, start=1):
        lignes.append({"id": "WIKI-%04d" % numero, "equipement_id": verdict["equipementId"],
                       "texte": verdict["texte"].replace("\r\n", "\n"), "ot_cites": ";".join(verdict["otCites"]),
                       "ot_sources": ";".join(verdict["otSources"]), "statut": "à valider", "modele": modele,
                       "date_proposition": HEURE_PROPOSITION})
    ecrire_lignes(lignes)


def relecture(_arguments):
    requetes = {r["repere"]: r for r in lire_requetes()}
    verdicts = json.loads((DOSSIER_TRAVAIL / "verdicts.json").read_text(encoding="utf-8"))
    morceaux = []
    for numero, verdict in enumerate(verdicts, start=1):
        donnees = requetes[verdict["repere"]]["donnees"]
        ots = {ot["id"]: ot for ot in donnees["ot"]}
        cites = []
        for identifiant in verdict.get("otCites", []):
            ot = ots.get(identifiant, {})
            cites.append("<li><b>%s</b> · %s · %s · %s<br><small>symptôme : %s · cause : %s · remède : %s</small>"
                         "<br><span class='cr'>%s</span></li>" % tuple(html.escape(str(v)) for v in (
                             identifiant, ot.get("date", ""), ot.get("type", ""), ot.get("titre", ""),
                             ot.get("symptome", ""), ot.get("cause", ""), ot.get("remede", ""), ot.get("compteRendu", ""))))
        etat = "acceptée par Prévo" if verdict["accepte"] else "REFUSÉE : " + " ; ".join(verdict.get("raisons", []))
        morceaux.append("<section><h2>%d. %s — %s</h2><p class='etat'>%s · %d OT envoyés</p>"
                        "<div class='colonnes'><div><h3>Synthèse [IA] proposée</h3><pre>%s</pre></div>"
                        "<div><h3>OT cités</h3><ul>%s</ul></div></div></section>" % (
                            numero, html.escape(verdict["repere"]), html.escape(donnees["designation"]), html.escape(etat),
                            len(verdict.get("otSources", [])), html.escape(verdict.get("texte", "")), "".join(cites)))
    page = ("<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'><title>Relecture des synthèses de la démo</title>"
            "<style>body{font:15px/1.5 system-ui,sans-serif;margin:24px;max-width:1200px;color:#1b1f2a}"
            "section{border:1px solid #c9cedb;border-radius:10px;padding:12px 16px;margin:16px 0}"
            ".colonnes{display:grid;grid-template-columns:1fr 1fr;gap:16px}pre{white-space:pre-wrap;font:inherit;"
            "background:#f3f5fa;padding:10px;border-radius:8px}.cr{color:#4a5166}.etat{color:#4a5166}"
            "@media(max-width:800px){.colonnes{grid-template-columns:1fr}}</style></head><body>"
            "<h1>Relecture des synthèses de la démo (%d)</h1><p>Rédigées par Claude avec le prompt de Prévo, lues par "
            "Prévo (contrôles du §20.4). Pour chacune : <b>validée</b>, <b>laissée à valider</b> (deux, pour la "
            "démonstration) ou <b>rejetée</b> (la consigne est corrigée et la requête rejouée ; aucun texte retouché "
            "à la main).</p>%s</body></html>") % (len(verdicts), "".join(morceaux))
    chemin = DOSSIER_TRAVAIL / "relecture.html"
    chemin.write_text(page, encoding="utf-8")
    print("Page de relecture : %s" % chemin)
    return 0


def valider(arguments):
    lignes = lire_fige()
    par_repere = {}
    requetes = {r["equipementId"]: r["repere"] for r in lire_requetes()}
    for ligne in lignes:
        par_repere[requetes.get(ligne["equipement_id"], ligne["equipement_id"])] = ligne
    inconnus = [r for r in list(arguments.reperes) + list(arguments.a_valider or []) if r not in par_repere]
    if inconnus:
        raise SystemExit("Repère(s) inconnu(s) : %s" % ", ".join(inconnus))
    for repere in arguments.reperes:
        par_repere[repere].update(statut="validée", valide_par=VALIDATEUR, date_validation=HEURE_VALIDATION)
    for repere in arguments.a_valider or []:
        par_repere[repere].update(statut="à valider", valide_par="", date_validation="")
    ecrire_lignes(lignes)
    compte = {}
    for ligne in lignes:
        compte[ligne["statut"]] = compte.get(ligne["statut"], 0) + 1
    print("Fichier figé mis à jour : %s" % ", ".join("%d %s" % (n, s) for s, n in sorted(compte.items())))
    return 0


def principal(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    analyseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = analyseur.add_subparsers(dest="commande", required=True)
    sous.add_parser("exporter", help="écrit les requêtes réelles de la démo").set_defaults(action=exporter)
    lecture = sous.add_parser("importer", help="lit les réponses par le circuit de Prévo")
    lecture.add_argument("--modele", required=True, help="modèle réellement utilisé (affiché sur chaque synthèse)")
    lecture.set_defaults(action=importer)
    envoi = sous.add_parser("message", help="affiche ce que reçoit le sous-agent pour un repère")
    envoi.add_argument("repere")
    envoi.set_defaults(action=message)
    sous.add_parser("relecture", help="écrit la page de relecture pour Nicolas").set_defaults(action=relecture)
    choix = sous.add_parser("valider", help="applique les choix de Nicolas au fichier figé")
    choix.add_argument("reperes", nargs="*", help="repères des synthèses validées")
    choix.add_argument("--a-valider", nargs="*", default=[], help="repères laissés « à valider »")
    choix.set_defaults(action=valider)
    arguments = analyseur.parse_args(argv)
    return arguments.action(arguments)


if __name__ == "__main__":
    sys.exit(principal())
