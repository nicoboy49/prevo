// Généré par outils/generer_catalogue.py à partir de docs/catalogue/*.json : ne pas éditer.
// Catalogue des contrôles réglementaires et des habilitations (France), validé le 2026-11-08.
// Aide au suivi ; la responsabilité reste celle de l'employeur.
(function () {
  "use strict";
  function geler(valeur) {
    if (valeur && typeof valeur === "object") {
      Object.keys(valeur).forEach(function (cle) { geler(valeur[cle]); });
      Object.freeze(valeur);
    }
    return valeur;
  }
  window.CatalogueFR = geler({
    "controles": [
      {
        "id": "C01",
        "famille": "Levage",
        "nature": "VGP pont roulant, palan, potence (installés à demeure)",
        "equipements": "Ponts roulants, portiques, monorails, palans, treuils, grues potences installés à demeure, mus mécaniquement ou à la main, ne servant pas à lever des personnes",
        "periodicite_mois": 12,
        "periodicite_texte": "12 mois",
        "nature_source": "obligation",
        "reference": "Code du travail, art. R4323-23 et R4323-24 ; arrêté du 1er mars 2004, art. 22 et 23 (appareils visés : annexe)",
        "liens": [
          {
            "libelle": "Arrêté du 1er mars 2004, art. 23 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680469"
          },
          {
            "libelle": "Arrêté du 1er mars 2004, texte consolidé (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000000439029"
          },
          {
            "libelle": "Code du travail, art. R4323-23 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000018531479"
          }
        ],
        "qui_verifie": "Personnes qualifiées, appartenant ou non à l'établissement (R4323-24), dont le nom est tenu à la disposition de l'inspection du travail (ED 828)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C02",
        "famille": "Levage",
        "nature": "VGP appareil de levage à main changeant de site",
        "equipements": "Appareils de levage non conçus pour lever des personnes, mus par la force humaine employée directement, qui changent de site d'utilisation (exemples ED 828 : palans, treuils, crics, tire-fort, moufles)",
        "periodicite_mois": 6,
        "periodicite_texte": "6 mois",
        "nature_source": "obligation",
        "reference": "Arrêté du 1er mars 2004, art. 20 III et art. 23 a)",
        "liens": [
          {
            "libelle": "Arrêté du 1er mars 2004, art. 23 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680469"
          },
          {
            "libelle": "Arrêté du 1er mars 2004, art. 20 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680466"
          }
        ],
        "qui_verifie": "Personnes qualifiées, appartenant ou non à l'établissement (R4323-24)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C03",
        "famille": "Levage",
        "nature": "VGP chariot élévateur",
        "equipements": "Chariots élévateurs (chariots automoteurs élévateurs à conducteur porté), y compris chacun de leurs équipements interchangeables",
        "periodicite_mois": 6,
        "periodicite_texte": "6 mois",
        "nature_source": "obligation",
        "reference": "Arrêté du 1er mars 2004, art. 20 II et art. 23 a)",
        "liens": [
          {
            "libelle": "Arrêté du 1er mars 2004, art. 23 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680469"
          },
          {
            "libelle": "Arrêté du 1er mars 2004, art. 20 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680466"
          }
        ],
        "qui_verifie": "Personnes qualifiées, appartenant ou non à l'établissement (R4323-24)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C04",
        "famille": "Levage",
        "nature": "VGP gerbeur électrique (conducteur accompagnant)",
        "equipements": "Gerbeurs et chariots automoteurs élévateurs à conducteur non porté (accompagnant)",
        "periodicite_mois": 6,
        "periodicite_texte": "6 mois par défaut (lecture la plus probable de l'art. 20 II : « chariots élévateurs ») ; 12 mois si l'on suit la règle générale de l'art. 23",
        "nature_source": "obligation",
        "reference": "Arrêté du 1er mars 2004, annexe (appareils visés), art. 20 II et art. 23",
        "liens": [
          {
            "libelle": "Arrêté du 1er mars 2004, annexe (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000023453892"
          },
          {
            "libelle": "Arrêté du 1er mars 2004, art. 20 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680466"
          },
          {
            "libelle": "Arrêté du 1er mars 2004, art. 23 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680469"
          }
        ],
        "qui_verifie": "Personnes qualifiées, appartenant ou non à l'établissement (R4323-24)",
        "a_confirmer": true,
        "relu_le": "2026-11-08",
        "mention": "à confirmer avec votre organisme de contrôle"
      },
      {
        "id": "C05",
        "famille": "Levage",
        "nature": "VGP nacelle (PEMP)",
        "equipements": "Plates-formes élévatrices mobiles de personnes (PEMP, nacelles), automotrices ou non",
        "periodicite_mois": 6,
        "periodicite_texte": "6 mois",
        "nature_source": "obligation",
        "reference": "Arrêté du 1er mars 2004, art. 20 II et art. 23 a)",
        "liens": [
          {
            "libelle": "Arrêté du 1er mars 2004, art. 23 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680469"
          },
          {
            "libelle": "Arrêté du 1er mars 2004, art. 20 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680466"
          }
        ],
        "qui_verifie": "Personnes qualifiées, appartenant ou non à l'établissement (R4323-24)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C06",
        "famille": "Levage",
        "nature": "VGP hayon élévateur",
        "equipements": "Hayons élévateurs (véhicules de livraison)",
        "periodicite_mois": 6,
        "periodicite_texte": "6 mois",
        "nature_source": "obligation",
        "reference": "Arrêté du 1er mars 2004, art. 20 II et art. 23 a)",
        "liens": [
          {
            "libelle": "Arrêté du 1er mars 2004, art. 20 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680466"
          },
          {
            "libelle": "Arrêté du 1er mars 2004, art. 23 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680469"
          }
        ],
        "qui_verifie": "Personnes qualifiées, appartenant ou non à l'établissement (R4323-24)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C07",
        "famille": "Levage",
        "nature": "VGP grue auxiliaire de chargement / bras de levage de bennes",
        "equipements": "Grues auxiliaires de chargement sur véhicules ; bras ou portiques de levage pour bennes amovibles ; engins de terrassement équipés pour le levage",
        "periodicite_mois": 6,
        "periodicite_texte": "6 mois",
        "nature_source": "obligation",
        "reference": "Arrêté du 1er mars 2004, art. 20 II et art. 23 a)",
        "liens": [
          {
            "libelle": "Arrêté du 1er mars 2004, art. 20 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680466"
          },
          {
            "libelle": "Arrêté du 1er mars 2004, art. 23 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680469"
          }
        ],
        "qui_verifie": "Personnes qualifiées, appartenant ou non à l'établissement (R4323-24)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C08",
        "famille": "Levage",
        "nature": "VGP table élévatrice (levage de charges)",
        "equipements": "Tables élévatrices fixes ou mobiles servant à lever des charges (ni personnes, ni poste de travail)",
        "periodicite_mois": 12,
        "periodicite_texte": "12 mois",
        "nature_source": "obligation",
        "reference": "Arrêté du 1er mars 2004, annexe (appareils visés) et art. 23 (règle générale)",
        "liens": [
          {
            "libelle": "Arrêté du 1er mars 2004, annexe (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000023453892"
          },
          {
            "libelle": "Arrêté du 1er mars 2004, art. 23 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680469"
          }
        ],
        "qui_verifie": "Personnes qualifiées, appartenant ou non à l'établissement (R4323-24)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C09",
        "famille": "Levage",
        "nature": "VGP appareil motorisé élevant un poste de travail",
        "equipements": "Appareils mus mécaniquement qui transportent des personnes ou élèvent un poste de travail, hors PEMP (C05) : appareils de manutention à poste de conduite élevable (préparateurs de commandes), plates-formes s'élevant le long de mâts, échafaudages volants motorisés",
        "periodicite_mois": 6,
        "periodicite_texte": "6 mois",
        "nature_source": "obligation",
        "reference": "Arrêté du 1er mars 2004, art. 23 a) (2e tiret) ; annexe (« élévateurs de postes de travail »)",
        "liens": [
          {
            "libelle": "Arrêté du 1er mars 2004, art. 23 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680469"
          },
          {
            "libelle": "Arrêté du 1er mars 2004, annexe (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000023453892"
          }
        ],
        "qui_verifie": "Personnes qualifiées, appartenant ou non à l'établissement (R4323-24)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C10",
        "famille": "Levage",
        "nature": "VGP appareil à main élevant un poste de travail",
        "equipements": "Plates-formes et appareils mus par la force humaine employée directement qui élèvent un poste de travail (plates-formes à élévation manuelle, échafaudages volants non motorisés)",
        "periodicite_mois": 3,
        "periodicite_texte": "3 mois",
        "nature_source": "obligation",
        "reference": "Arrêté du 1er mars 2004, art. 23 b)",
        "liens": [
          {
            "libelle": "Arrêté du 1er mars 2004, art. 23 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006680469"
          }
        ],
        "qui_verifie": "Personnes qualifiées, appartenant ou non à l'établissement (R4323-24)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C11",
        "famille": "Levage",
        "nature": "Vérification périodique des accessoires de levage",
        "equipements": "Élingues (câbles, chaînes, sangles), palonniers, pinces auto-serrantes, aimants, ventouses, clés de levage",
        "periodicite_mois": 12,
        "periodicite_texte": "12 mois",
        "nature_source": "obligation",
        "reference": "Code du travail, art. R4323-23 à R4323-27 ; arrêté du 1er mars 2004, art. 24",
        "liens": [
          {
            "libelle": "Arrêté du 1er mars 2004, art. 24 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000032078725"
          }
        ],
        "qui_verifie": "Personne qualifiée appartenant ou non à l'établissement (ED 828)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C12",
        "famille": "Électricité",
        "nature": "Vérification périodique des installations électriques",
        "equipements": "Installations électriques permanentes des lieux de travail",
        "periodicite_mois": 12,
        "periodicite_texte": "1 an ; 2 ans possible si le rapport précédent ne présente aucune observation, ou si les travaux de mise en conformité ont été réalisés avant l'échéance (l'employeur en informe alors l'inspecteur du travail par lettre recommandée avec AR)",
        "nature_source": "obligation",
        "reference": "Code du travail, art. R4226-16 et R4226-17 ; arrêté du 26 décembre 2011, art. 3",
        "liens": [
          {
            "libelle": "Arrêté du 26 décembre 2011, art. 3 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000025049531"
          },
          {
            "libelle": "Arrêté du 26 décembre 2011, texte consolidé (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000025046978"
          },
          {
            "libelle": "Code du travail, art. R4226-16 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000022765070"
          }
        ],
        "qui_verifie": "Organisme accrédité, ou personne qualifiée appartenant à l'entreprise (R4226-17), dont la compétence répond aux critères de l'arrêté du 22 décembre 2011 (selon ED 828)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C13",
        "famille": "Électricité",
        "nature": "Contrôle par thermographie infrarouge (APSAD D19)",
        "equipements": "Installations électriques (tableaux, connexions, appareillages), surtout sur les sites à risque d'incendie ou quand le matériel électrique est essentiel à la production",
        "periodicite_mois": null,
        "periodicite_texte": "aucune par défaut : à saisir selon le contrat d'assurance",
        "nature_source": "recommandation",
        "reference": "Référentiel APSAD D19 « Thermographie infrarouge – Document technique pour le contrôle d'installations électriques » (CNPP, édition juin 2019) ; compte rendu Q19",
        "liens": [
          {
            "libelle": "CNPP, fiche du référentiel APSAD D19 (édition 2019)",
            "url": "https://cybel.cnpp.com/livre-referentiel-apsad-d19-thermographie-infrarouge-2019.html"
          }
        ],
        "qui_verifie": "Opérateur en thermographie intervenant selon le référentiel D19 et rédigeant le compte rendu Q19 (qualification exacte à confirmer)",
        "a_confirmer": true,
        "relu_le": "2026-11-08",
        "mention": "à confirmer avec votre organisme de contrôle"
      },
      {
        "id": "C14",
        "famille": "Équipements sous pression",
        "nature": "Inspection périodique du réservoir d'air comprimé",
        "equipements": "Réservoirs d'air comprimé (gaz du groupe 2) dont PS > 4 bar et PS × V > 200 bar·L, récipients à pression simples compris",
        "periodicite_mois": 48,
        "periodicite_texte": "4 ans au plus ; première inspection au plus 3 ans après la mise en service ou une modification notable (sauf équipement ayant eu un contrôle de mise en service) ; à réduire si l'état de l'équipement le justifie",
        "nature_source": "obligation",
        "reference": "Code de l'environnement, art. R557-14-1 (champ) ; arrêté du 20 novembre 2017, art. 14 et 15",
        "liens": [
          {
            "libelle": "Arrêté du 20 novembre 2017, art. 15 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000036131127"
          },
          {
            "libelle": "Arrêté du 20 novembre 2017, texte consolidé (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000036128632"
          },
          {
            "libelle": "Code de l'environnement, art. R557-14-1 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000033741441"
          }
        ],
        "qui_verifie": "Personne compétente désignée par l'exploitant (ED 828) ; organisme accrédité pour les équipements revêtus non mis à nu",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C15",
        "famille": "Équipements sous pression",
        "nature": "Requalification périodique du réservoir d'air comprimé",
        "equipements": "Réservoirs d'air comprimé soumis au suivi en service (voir C14)",
        "periodicite_mois": 120,
        "periodicite_texte": "10 ans au plus (6 ans si le fluide est toxique ou corrosif pour les parois)",
        "nature_source": "obligation",
        "reference": "Arrêté du 20 novembre 2017, art. 14 II et art. 18",
        "liens": [
          {
            "libelle": "Arrêté du 20 novembre 2017, art. 18 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000036131133"
          },
          {
            "libelle": "Arrêté du 20 novembre 2017, art. 14 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000036131125"
          }
        ],
        "qui_verifie": "Expert d'un organisme habilité par l'État et accrédité (ED 828)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C16",
        "famille": "Fluides frigorigènes",
        "nature": "Contrôle d'étanchéité du circuit frigorifique (5 à < 50 t éq. CO2)",
        "equipements": "Équipements de réfrigération, climatisation, pompes à chaleur contenant de 5 à moins de 50 t éq. CO2 de gaz fluorés de l'annexe I (ou de 1 à moins de 10 kg de gaz de l'annexe II, section 1)",
        "periodicite_mois": 12,
        "periodicite_texte": "12 mois ; 24 mois si un système de détection des fuites est installé",
        "nature_source": "obligation",
        "reference": "Règlement (UE) 2024/573, art. 5 (§ 1, § 2 a, § 6 a) ; Code de l'environnement, art. R543-79 ; arrêté du 29 février 2016, art. 4",
        "liens": [
          {
            "libelle": "Règlement (UE) 2024/573 (EUR-Lex)",
            "url": "https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX:32024R0573"
          },
          {
            "libelle": "Code de l'environnement, art. R543-79 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050813258"
          },
          {
            "libelle": "Arrêté du 29 février 2016, texte consolidé (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000032173989"
          }
        ],
        "qui_verifie": "Opérateur disposant de l'attestation de capacité prévue à l'art. R543-99 du Code de l'environnement (R543-79)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C17",
        "famille": "Fluides frigorigènes",
        "nature": "Contrôle d'étanchéité du circuit frigorifique (50 à < 500 t éq. CO2)",
        "equipements": "Équipements de réfrigération, climatisation, pompes à chaleur contenant de 50 à moins de 500 t éq. CO2 de gaz fluorés de l'annexe I (ou de 10 à moins de 100 kg de gaz de l'annexe II, section 1)",
        "periodicite_mois": 6,
        "periodicite_texte": "6 mois ; 12 mois si un système de détection des fuites est installé",
        "nature_source": "obligation",
        "reference": "Règlement (UE) 2024/573, art. 5 § 6 b) ; Code de l'environnement, art. R543-79",
        "liens": [
          {
            "libelle": "Règlement (UE) 2024/573 (EUR-Lex)",
            "url": "https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX:32024R0573"
          }
        ],
        "qui_verifie": "Opérateur disposant de l'attestation de capacité (R543-79, R543-99)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C18",
        "famille": "Fluides frigorigènes",
        "nature": "Contrôle d'étanchéité du circuit frigorifique (≥ 500 t éq. CO2)",
        "equipements": "Équipements de réfrigération, climatisation, pompes à chaleur contenant 500 t éq. CO2 ou plus de gaz fluorés de l'annexe I (ou 100 kg ou plus de gaz de l'annexe II, section 1)",
        "periodicite_mois": 3,
        "periodicite_texte": "3 mois ; 6 mois si un système de détection des fuites est installé (obligatoire pour les équipements fixes, donc 6 mois pour un équipement fixe conforme)",
        "nature_source": "obligation",
        "reference": "Règlement (UE) 2024/573, art. 5 § 6 c) et art. 6 § 1 ; Code de l'environnement, art. R543-79",
        "liens": [
          {
            "libelle": "Règlement (UE) 2024/573 (EUR-Lex)",
            "url": "https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX:32024R0573"
          }
        ],
        "qui_verifie": "Opérateur disposant de l'attestation de capacité (R543-79, R543-99)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C19",
        "famille": "Aération et assainissement",
        "nature": "Contrôle de la ventilation, locaux à pollution non spécifique",
        "equipements": "Installations de ventilation des locaux à pollution non spécifique : introduction et extraction d'air, gaines, ventilateurs, filtres, traitement de l'air",
        "periodicite_mois": 12,
        "periodicite_texte": "Au minimum une fois par an",
        "nature_source": "obligation",
        "reference": "Code du travail, art. R4222-20 à R4222-22 ; arrêté du 8 octobre 1987, art. 3",
        "liens": [
          {
            "libelle": "Arrêté du 8 octobre 1987, art. 3 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006678610"
          },
          {
            "libelle": "Arrêté du 8 octobre 1987, texte consolidé (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000000863044"
          },
          {
            "libelle": "Code du travail, art. R4222-20 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000018532294"
          }
        ],
        "qui_verifie": "Non précisé par l'arrêté ; personne compétente (ED 828) ; organisme accrédité sur mise en demeure de l'inspection du travail (arrêté du 9 octobre 1987, selon ED 828)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C20",
        "famille": "Aération et assainissement",
        "nature": "Contrôle du captage, locaux à pollution spécifique",
        "equipements": "Installations des locaux à pollution spécifique : captage, gaines, dépoussiéreurs, épurateurs, apport d'air de compensation",
        "periodicite_mois": 12,
        "periodicite_texte": "Au minimum tous les ans",
        "nature_source": "obligation",
        "reference": "Code du travail, art. R4222-20 à R4222-22 ; arrêté du 8 octobre 1987, art. 4 (2 a)",
        "liens": [
          {
            "libelle": "Arrêté du 8 octobre 1987, art. 4 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006678611"
          }
        ],
        "qui_verifie": "Non précisé par l'arrêté ; personne compétente (ED 828) ; organisme accrédité sur mise en demeure de l'inspection du travail",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C21",
        "famille": "Aération et assainissement",
        "nature": "Contrôle du recyclage d'air, locaux à pollution spécifique",
        "equipements": "Installations des locaux à pollution spécifique équipées d'un système de recyclage de l'air : gaines de recyclage, systèmes de surveillance",
        "periodicite_mois": 6,
        "periodicite_texte": "Au minimum tous les six mois",
        "nature_source": "obligation",
        "reference": "Arrêté du 8 octobre 1987, art. 4 (2 b)",
        "liens": [
          {
            "libelle": "Arrêté du 8 octobre 1987, art. 4 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000006678611"
          }
        ],
        "qui_verifie": "Non précisé par l'arrêté ; personne compétente (ED 828)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C22",
        "famille": "Portes et portails",
        "nature": "Visite d'entretien des portes et portails automatiques",
        "equipements": "Portes et portails automatiques et semi-automatiques des lieux de travail",
        "periodicite_mois": 6,
        "periodicite_texte": "Au minimum semestrielle, adaptée à la fréquence d'utilisation et au type de porte ; et après toute défaillance",
        "nature_source": "obligation",
        "reference": "Code du travail, art. R4224-12 ; arrêté du 21 décembre 1993, art. 9",
        "liens": [
          {
            "libelle": "Arrêté du 21 décembre 1993, art. 9 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000054109592"
          },
          {
            "libelle": "Arrêté du 21 décembre 1993, texte consolidé (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000000728236"
          },
          {
            "libelle": "Code du travail, art. R4224-12 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000018532211"
          }
        ],
        "qui_verifie": "Techniciens dûment qualifiés et spécialisés appartenant à l'entreprise, ou prestataire extérieur sous contrat écrit (art. 9) ; interventions consignées dans un livret d'entretien",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C23",
        "famille": "Incendie",
        "nature": "Exercices et essais incendie (consigne de sécurité)",
        "equipements": "Matériel d'extinction et de secours ; exercices d'alarme, d'évacuation et de maniement des moyens de premier secours",
        "periodicite_mois": 6,
        "periodicite_texte": "Au moins tous les six mois",
        "nature_source": "obligation",
        "reference": "Code du travail, art. R4227-38 et R4227-39",
        "liens": [
          {
            "libelle": "Code du travail, art. R4227-39 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000024769386"
          },
          {
            "libelle": "Code du travail, sous-section « Consigne de sécurité incendie » (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000006072050/LEGISCTA000018489151"
          }
        ],
        "qui_verifie": "Non précisé par le texte ; personne compétente (ED 828) ; date et observations consignées sur un registre tenu à la disposition de l'inspection du travail",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C24",
        "famille": "Incendie",
        "nature": "Extincteurs : maintien en bon état (Code du travail)",
        "equipements": "Extincteurs portatifs (au moins un de 6 L à eau pulvérisée pour 200 m², au moins un par niveau)",
        "periodicite_mois": null,
        "periodicite_texte": "Aucune périodicité fixée par le Code du travail",
        "nature_source": "obligation",
        "reference": "Code du travail, art. R4227-28 et R4227-29",
        "liens": [
          {
            "libelle": "Code du travail, sous-section « Moyens d'extinction » (R4227-28 et R4227-29) (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000006072050/LEGISCTA000018489129"
          }
        ],
        "qui_verifie": "Non précisé par le Code du travail",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C25",
        "famille": "Incendie",
        "nature": "Inspection visuelle des extincteurs",
        "equipements": "Tous les extincteurs portatifs et mobiles : présence, accessibilité, bon état apparent, scellé, étiquette de vérification",
        "periodicite_mois": 3,
        "periodicite_texte": "Au moins tous les 3 mois (de préférence mensuellement)",
        "nature_source": "norme",
        "reference": "Règle APSAD R4 (CNPP, éd. novembre 2016), § 4-1 ; norme NF S 61-919 (juillet 2004), point 4",
        "liens": [
          {
            "libelle": "AFNOR, notice NF S61-919",
            "url": "https://www.boutique.afnor.org/standard/nf-s61-919/maintenance-for-portable-fire-extinguishers/article/662143/fa135996"
          },
          {
            "libelle": "CNPP, référentiel APSAD R4 Extincteurs portatifs et mobiles",
            "url": "https://cybel.cnpp.com/livre-referentiel-apsad-r4-extincteurs-portatifs-et-mobiles-2016.html"
          }
        ],
        "qui_verifie": "Personnel qualifié ou entreprise extérieure compétente (ED 828)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C26",
        "famille": "Incendie",
        "nature": "Vérification annuelle des extincteurs",
        "equipements": "Tous les extincteurs portatifs et mobiles",
        "periodicite_mois": 12,
        "periodicite_texte": "Annuelle (tolérance de ± 2 mois par rapport à la date anniversaire)",
        "nature_source": "norme",
        "reference": "Règle APSAD R4 (CNPP, éd. novembre 2016), § 4-2 ; norme NF S 61-919 (juillet 2004), point 5 et annexe B",
        "liens": [
          {
            "libelle": "AFNOR, notice NF S61-919",
            "url": "https://www.boutique.afnor.org/standard/nf-s61-919/maintenance-for-portable-fire-extinguishers/article/662143/fa135996"
          },
          {
            "libelle": "CNPP, référentiel APSAD R4 Extincteurs portatifs et mobiles",
            "url": "https://cybel.cnpp.com/livre-referentiel-apsad-r4-extincteurs-portatifs-et-mobiles-2016.html"
          }
        ],
        "qui_verifie": "Entreprise certifiée APSAD et NF Service d'installation et de maintenance d'extincteurs, ou personne disposant du CAP d'agent vérificateur d'appareils extincteurs, ou compétence équivalente (ED 828)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C27",
        "famille": "Incendie",
        "nature": "Maintenance approfondie des extincteurs",
        "equipements": "Extincteurs portatifs et mobiles",
        "periodicite_mois": 60,
        "periodicite_texte": "À 5 ans et à 15 ans (l'année 10 : révision en atelier, C28) ; tolérance de ± 2 mois",
        "nature_source": "norme",
        "reference": "Règle APSAD R4 (CNPP, éd. novembre 2016), § 4-4 ; norme NF S 61-919 (juillet 2004), point 5 et annexe C",
        "liens": [
          {
            "libelle": "AFNOR, notice NF S61-919",
            "url": "https://www.boutique.afnor.org/standard/nf-s61-919/maintenance-for-portable-fire-extinguishers/article/662143/fa135996"
          }
        ],
        "qui_verifie": "Entreprise certifiée APSAD et NF Service, ou personne disposant du CAP d'agent vérificateur d'appareils extincteurs, ou compétence équivalente (ED 828)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C28",
        "famille": "Incendie",
        "nature": "Révision en atelier des extincteurs",
        "equipements": "Extincteurs portatifs et mobiles",
        "periodicite_mois": 120,
        "periodicite_texte": "10 ans à partir de la date de fabrication ou de la dernière recharge effective (± 2 mois)",
        "nature_source": "norme",
        "reference": "Règle APSAD R4 (CNPP, éd. novembre 2016), § 4-5 ; norme NF S 61-919 (juillet 2004), point 10 et annexes A et D",
        "liens": [
          {
            "libelle": "AFNOR, notice NF S61-919",
            "url": "https://www.boutique.afnor.org/standard/nf-s61-919/maintenance-for-portable-fire-extinguishers/article/662143/fa135996"
          }
        ],
        "qui_verifie": "Entreprise certifiée APSAD et NF Service, fabricant, ou centre de révision agréé par au moins un fabricant (ED 828)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C29",
        "famille": "Éclairage de sécurité",
        "nature": "Essai mensuel de l'éclairage de sécurité",
        "equipements": "Éclairage de sécurité (blocs autonomes ou source centralisée)",
        "periodicite_mois": 1,
        "periodicite_texte": "Une fois par mois",
        "nature_source": "obligation",
        "reference": "Code du travail, art. R4227-14 ; arrêté du 14 décembre 2011, art. 11",
        "liens": [
          {
            "libelle": "Arrêté du 14 décembre 2011, art. 11 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000025072657"
          },
          {
            "libelle": "Arrêté du 14 décembre 2011, texte consolidé (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000025055364"
          },
          {
            "libelle": "Code du travail, art. R4227-14 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000022764985"
          }
        ],
        "qui_verifie": "L'employeur (art. 11) ; personne qualifiée appartenant à l'entreprise dont la compétence est appréciée par l'employeur (ED 828)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C30",
        "famille": "Éclairage de sécurité",
        "nature": "Contrôle semestriel d'autonomie de l'éclairage de sécurité",
        "equipements": "Éclairage de sécurité (blocs autonomes ou source centralisée)",
        "periodicite_mois": 6,
        "periodicite_texte": "Une fois tous les six mois",
        "nature_source": "obligation",
        "reference": "Code du travail, art. R4227-14 ; arrêté du 14 décembre 2011, art. 11",
        "liens": [
          {
            "libelle": "Arrêté du 14 décembre 2011, art. 11 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000025072657"
          }
        ],
        "qui_verifie": "L'employeur (art. 11) ; personne qualifiée appartenant à l'entreprise (ED 828)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "C31",
        "famille": "Stockage",
        "nature": "Inspection annuelle des rayonnages et racks",
        "equipements": "Rayonnages métalliques, palettiers, racks de stockage",
        "periodicite_mois": 12,
        "periodicite_texte": "Au moins tous les ans (et après tout choc)",
        "nature_source": "recommandation",
        "reference": "INRS ED 771 « Les rayonnages métalliques » (3e édition, septembre 2017) ; norme NF EN 15635 (janvier 2009) ; Code du travail : obligation générale de maintien en état (art. R4322-1, cité par l'INRS), sans périodicité chiffrée",
        "liens": [
          {
            "libelle": "INRS ED 771 (PDF)",
            "url": "https://inrs.fr/dam/jcr:403225a2-ed30-460d-b694-f3e6738143f7/ed771.pdf"
          },
          {
            "libelle": "AFNOR, notice NF EN 15635",
            "url": "https://www.boutique.afnor.org/en-gb/standard/nf-en-15635/steel-static-storage-systems-application-and-maintenance-of-storage-equipme/fa148843/32678"
          }
        ],
        "qui_verifie": "Personne compétente employée par l'utilisateur ou le constructeur, entreprise spécialisée ou organisme de contrôle (ED 771)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      }
    ],
    "habilitations": [
      {
        "id": "H01",
        "famille": "Électricité",
        "type": "Habilitation électrique – non électricien",
        "titres": "B0, H0, H0V (exécutant ou chargé de chantier), BF-HF (travaux en fouilles), BS, BE Manœuvre, HE Manœuvre, BP (opérations élémentaires chaîne photovoltaïque)",
        "duree_mois": 36,
        "duree_texte": "3 ans (périodicité de recyclage recommandée ; la validité du titre est fixée par l'employeur)",
        "nature_source": "recommandation",
        "reference": "Code du travail R4544-9 et R4544-10 (l'employeur délivre, maintient ou renouvelle l'habilitation selon les normes de l'art. R4544-3) ; normes désignées par l'arrêté du 5 juillet 2024 : NF C 18-510 (janvier 2012) et NF C 18-510/A1 (février 2020) ; INRS FAQ habilitation électrique ; INRS ED 6127 § 6.2.1",
        "liens": [
          {
            "libelle": "Code du travail, art. R4544-9 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000022849102"
          },
          {
            "libelle": "Code du travail, art. R4544-10, version au 1er oct. 2025 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051500368"
          },
          {
            "libelle": "Code du travail, art. R4544-3 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000022849139"
          },
          {
            "libelle": "Arrêté du 5 juillet 2024 relatif aux normes (NF C 18-510 janv. 2012, NF C 18-510/A1 févr. 2020, NF C 18-550 août 2015), NOR TSST2417111A (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000049892203"
          },
          {
            "libelle": "INRS, Habilitation électrique : foire aux questions",
            "url": "https://www.inrs.fr/risques/electriques/habilitation-electrique-foire-aux-questions.html"
          },
          {
            "libelle": "INRS ED 6127, L'habilitation électrique, 3e éd. déc. 2020 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6127.pdf"
          }
        ],
        "delivre_par": "Employeur (titre d'habilitation), après formation théorique et pratique",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H02",
        "famille": "Électricité",
        "type": "Habilitation électrique – électricien",
        "titres": "B1, B1V, B2, B2V, B2V Essai, BR (y compris BR « champ d'application photovoltaïque »), BC, BE Essai / Vérification / Mesurage, H1, H1V, H2, H2V, HC, HE Essai / Vérification / Mesurage",
        "duree_mois": 36,
        "duree_texte": "3 ans (périodicité de recyclage recommandée ; la validité du titre est fixée par l'employeur)",
        "nature_source": "recommandation",
        "reference": "Code du travail R4544-9 et R4544-10 ; NF C 18-510 (janvier 2012) et NF C 18-510/A1 (février 2020), désignées par l'arrêté du 5 juillet 2024 ; INRS ED 6127 (3e éd., déc. 2020) § 6.2.1 Périodicité",
        "liens": [
          {
            "libelle": "Code du travail, art. R4544-9 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000022849102"
          },
          {
            "libelle": "Code du travail, art. R4544-10, version au 1er oct. 2025 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051500368"
          },
          {
            "libelle": "Arrêté du 5 juillet 2024 relatif aux normes (NF C 18-510 janv. 2012, NF C 18-510/A1 févr. 2020, NF C 18-550 août 2015), NOR TSST2417111A (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000049892203"
          },
          {
            "libelle": "INRS ED 6127, L'habilitation électrique, 3e éd. déc. 2020 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6127.pdf"
          },
          {
            "libelle": "INRS, Habilitation électrique : foire aux questions",
            "url": "https://www.inrs.fr/risques/electriques/habilitation-electrique-foire-aux-questions.html"
          }
        ],
        "delivre_par": "Employeur (titre d'habilitation), après formation théorique et pratique",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H03",
        "famille": "Électricité",
        "type": "Habilitation électrique – travaux sous tension (TST)",
        "titres": "B1T, B2T, B1N, B2N, H1T, H2T, H1N, H2N (T : travaux sous tension ; N : nettoyage sous tension)",
        "duree_mois": 12,
        "duree_texte": "1 an (validité du titre d'habilitation TST, selon l'INRS)",
        "nature_source": "recommandation",
        "reference": "Code du travail R4544-11 (habilitation spécifique après formation par un organisme agréé, délivrée, maintenue ou renouvelée selon les normes) ; durée : INRS FAQ habilitation électrique et ED 6127 (schéma § 6.2)",
        "liens": [
          {
            "libelle": "Code du travail, art. R4544-11, version au 1er oct. 2025 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051500365"
          },
          {
            "libelle": "INRS, Habilitation électrique : foire aux questions",
            "url": "https://www.inrs.fr/risques/electriques/habilitation-electrique-foire-aux-questions.html"
          },
          {
            "libelle": "INRS ED 6127, L'habilitation électrique, 3e éd. déc. 2020 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6127.pdf"
          }
        ],
        "delivre_par": "Employeur, après obtention d'un document délivré par un organisme de formation agréé par le ministre du Travail (R4544-11)",
        "a_confirmer": true,
        "relu_le": "2026-11-08",
        "mention": "à confirmer avec votre organisme de formation"
      },
      {
        "id": "H04",
        "famille": "Électricité",
        "type": "Habilitation électrique – véhicules et engins (NF C 18-550)",
        "titres": "Symboles terminés par L : B0L, B1L, B1VL, B2L, B2VL, BCL, BRL, BEL (+ attribut), B1XL et B2XL (+ attribut, ex. « Opération batterie », « Dépannage remorquage »), B1TL, B2TL",
        "duree_mois": 36,
        "duree_texte": "3 ans (recyclage recommandé ; ramené à 2 ans pour une pratique occasionnelle ou exceptionnelle)",
        "nature_source": "recommandation",
        "reference": "Code du travail R4544-9 et R4544-10 ; norme NF C 18-550 (août 2015) désignée par l'arrêté du 5 juillet 2024 ; INRS ED 6313 (1re éd., nov. 2018) § 6.2.1 Périodicité",
        "liens": [
          {
            "libelle": "Code du travail, art. R4544-10, version au 1er oct. 2025 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051500368"
          },
          {
            "libelle": "Arrêté du 5 juillet 2024 relatif aux normes (NF C 18-510 janv. 2012, NF C 18-510/A1 févr. 2020, NF C 18-550 août 2015), NOR TSST2417111A (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000049892203"
          },
          {
            "libelle": "INRS ED 6313, L'habilitation électrique. Opérations sur véhicules et engins, 1re éd. nov. 2018 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6313.pdf"
          },
          {
            "libelle": "INRS, Habilitation électrique : foire aux questions",
            "url": "https://www.inrs.fr/risques/electriques/habilitation-electrique-foire-aux-questions.html"
          }
        ],
        "delivre_par": "Employeur (titre d'habilitation), après formation théorique et pratique",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H05",
        "famille": "Électricité",
        "type": "Attestation médicale – habilitation au voisinage / TST",
        "titres": "Attestation d'absence de contre-indications médicales exigée pour les habilitations autorisant les opérations au voisinage de pièces nues sous tension (R4544-10) et pour les habilitations TST (R4544-11)",
        "duree_mois": 60,
        "duree_texte": "5 ans (validité de l'attestation)",
        "nature_source": "obligation",
        "reference": "Code du travail R4544-10, R4544-11 et R4544-11-1 (décret n° 2025-355 du 18 avril 2025, en vigueur le 1er oct. 2025) ; modèle : arrêté du 26 septembre 2025 (NOR TSST2525767A), annexe 2",
        "liens": [
          {
            "libelle": "Code du travail, art. R4544-11-1, en vigueur au 1er oct. 2025 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051496288"
          },
          {
            "libelle": "Code du travail, art. R4544-10, version au 1er oct. 2025 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051500368"
          },
          {
            "libelle": "Code du travail, art. R4544-11, version au 1er oct. 2025 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051500365"
          },
          {
            "libelle": "Arrêté du 26 septembre 2025 fixant les modèles d'attestation d'absence de contre-indications médicales (R4323-56 et R4544-9), NOR TSST2525767A (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052304220"
          },
          {
            "libelle": "Décret n° 2025-355 du 18 avril 2025 (Légifrance, non ouvert : contenu lu via les articles modifiés)",
            "url": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000051491350"
          }
        ],
        "delivre_par": "Médecin du travail, à l'issue d'un examen médical qu'il réalise lui-même",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H06",
        "famille": "CACES",
        "type": "CACES R482 – Engins de chantier",
        "titres": "Cat. A engins compacts ; B1 engins d'extraction à déplacement séquentiel ; B2 engins de sondage ou de forage à déplacement séquentiel ; B3 engins rail-route à déplacement séquentiel ; C1 engins de chargement à déplacement alternatif ; C2 engins de réglage à déplacement alternatif ; C3 engins de nivellement à déplacement alternatif ; D engins de compactage ; E engins de transport ; F chariots de manutention tout-terrain ; G conduite des engins hors production",
        "duree_mois": 120,
        "duree_texte": "10 ans (validité du certificat ; actualisation « au moins tous les 10 ans »)",
        "nature_source": "recommandation",
        "reference": "Recommandation Cnam R.482B (adoptée en 2024 par les CTN B, C, F, G, I ; mises à jour 2025 et 2026), § 3/3/5 « Actualisation » et annexe 1 (catégories)",
        "liens": [
          {
            "libelle": "Recommandation R.482B (adoptée en 2024 par les CTN B, C, F, G, I ; mises à jour 2025 et 2026) (ameli.fr, PDF)",
            "url": "https://www.ameli.fr/sites/default/files/Documents/R482B-sept2026.pdf"
          },
          {
            "libelle": "Assurance Maladie (ameli.fr), tableau des recommandations (page listant R482B à R491)",
            "url": "https://www.ameli.fr/entreprise/tableau_recommandations?page=3"
          },
          {
            "libelle": "INRS, Caces : ce qu'il faut retenir (mis à jour le 30/07/2026)",
            "url": "https://www.inrs.fr/demarche/caces-certificat-aptitude-conduite-securite/ce-qu-il-faut-retenir.html"
          },
          {
            "libelle": "INRS ED 6348, Questions-réponses formation, autorisation de conduite et Caces, 3e éd. sept. 2026 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6348.pdf"
          }
        ],
        "delivre_par": "Organisme testeur certifié (OTC), épreuves sous le contrôle d'un testeur qualifié",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H07",
        "famille": "CACES",
        "type": "CACES R483 – Grues mobiles",
        "titres": "Cat. A grues mobiles à flèche treillis ; Cat. B grues mobiles à flèche télescopique",
        "duree_mois": 60,
        "duree_texte": "5 ans (validité du certificat ; actualisation « au moins tous les 5 ans »)",
        "nature_source": "recommandation",
        "reference": "Recommandation Cnam R.483A (adoptée en 2017 ; mise à jour 2026), § 3/3/5 « Actualisation » et annexe 1 (catégories)",
        "liens": [
          {
            "libelle": "Recommandation R.483A (adoptée en 2017 ; mise à jour 2026) (ameli.fr, PDF)",
            "url": "https://www.ameli.fr/sites/default/files/Documents/R483A-juillet2026.pdf"
          },
          {
            "libelle": "Assurance Maladie (ameli.fr), tableau des recommandations (page listant R482B à R491)",
            "url": "https://www.ameli.fr/entreprise/tableau_recommandations?page=3"
          },
          {
            "libelle": "INRS, Caces : ce qu'il faut retenir (mis à jour le 30/07/2026)",
            "url": "https://www.inrs.fr/demarche/caces-certificat-aptitude-conduite-securite/ce-qu-il-faut-retenir.html"
          },
          {
            "libelle": "INRS ED 6348, Questions-réponses formation, autorisation de conduite et Caces, 3e éd. sept. 2026 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6348.pdf"
          }
        ],
        "delivre_par": "Organisme testeur certifié (OTC), épreuves sous le contrôle d'un testeur qualifié",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H08",
        "famille": "CACES",
        "type": "CACES R484 – Ponts roulants et portiques",
        "titres": "Cat. 1 ponts roulants et portiques à commande au sol ; Cat. 2 ponts roulants et portiques à commande en cabine (option « commande au sol »)",
        "duree_mois": 60,
        "duree_texte": "5 ans (validité du certificat ; actualisation « au moins tous les 5 ans »)",
        "nature_source": "recommandation",
        "reference": "Recommandation Cnam R.484A (adoptée en 2017 ; mise à jour 2026), § 3/3/5 « Actualisation » et annexe 1 (catégories)",
        "liens": [
          {
            "libelle": "Recommandation R.484A (adoptée en 2017 ; mise à jour 2026) (ameli.fr, PDF)",
            "url": "https://www.ameli.fr/sites/default/files/Documents/R484A-juillet2026.pdf"
          },
          {
            "libelle": "Assurance Maladie (ameli.fr), tableau des recommandations (page listant R482B à R491)",
            "url": "https://www.ameli.fr/entreprise/tableau_recommandations?page=3"
          },
          {
            "libelle": "INRS, Caces : ce qu'il faut retenir (mis à jour le 30/07/2026)",
            "url": "https://www.inrs.fr/demarche/caces-certificat-aptitude-conduite-securite/ce-qu-il-faut-retenir.html"
          },
          {
            "libelle": "INRS ED 6348, Questions-réponses formation, autorisation de conduite et Caces, 3e éd. sept. 2026 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6348.pdf"
          }
        ],
        "delivre_par": "Organisme testeur certifié (OTC), épreuves sous le contrôle d'un testeur qualifié",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H09",
        "famille": "CACES",
        "type": "CACES R485 – Chariots gerbeurs à conducteur accompagnant",
        "titres": "Cat. 1 gerbeurs automoteurs à conducteur accompagnant (1,20 m < hauteur de levée ≤ 2,50 m) ; Cat. 2 gerbeurs automoteurs à conducteur accompagnant (hauteur de levée > 2,50 m)",
        "duree_mois": 60,
        "duree_texte": "5 ans (validité du certificat ; actualisation « au moins tous les 5 ans »)",
        "nature_source": "recommandation",
        "reference": "Recommandation Cnam R.485A (adoptée en 2017 ; mise à jour 2026), § 3/3/5 « Actualisation » et annexe 1 (catégories)",
        "liens": [
          {
            "libelle": "Recommandation R.485A (adoptée en 2017 ; mise à jour 2026) (ameli.fr, PDF)",
            "url": "https://www.ameli.fr/sites/default/files/Documents/R485A-juillet2026.pdf"
          },
          {
            "libelle": "Assurance Maladie (ameli.fr), tableau des recommandations (page listant R482B à R491)",
            "url": "https://www.ameli.fr/entreprise/tableau_recommandations?page=3"
          },
          {
            "libelle": "INRS, Caces : ce qu'il faut retenir (mis à jour le 30/07/2026)",
            "url": "https://www.inrs.fr/demarche/caces-certificat-aptitude-conduite-securite/ce-qu-il-faut-retenir.html"
          },
          {
            "libelle": "INRS ED 6348, Questions-réponses formation, autorisation de conduite et Caces, 3e éd. sept. 2026 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6348.pdf"
          }
        ],
        "delivre_par": "Organisme testeur certifié (OTC), épreuves sous le contrôle d'un testeur qualifié",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H10",
        "famille": "CACES",
        "type": "CACES R486 – Plates-formes élévatrices mobiles de personnel (PEMP)",
        "titres": "Cat. A PEMP du groupe A, de type 1 ou 3 ; Cat. B PEMP du groupe B, de type 1 ou 3 ; Cat. C conduite hors production des PEMP des catégories A ou B ; option « chargement / déchargement sur porte-engins »",
        "duree_mois": 60,
        "duree_texte": "5 ans (validité du certificat ; actualisation « au moins tous les 5 ans »)",
        "nature_source": "recommandation",
        "reference": "Recommandation Cnam R.486B (adoptée en 2019 ; mises à jour 2019 et 2026), § 3/3/5 « Actualisation » et annexe 1 (catégories)",
        "liens": [
          {
            "libelle": "Recommandation R.486B (adoptée en 2019 ; mises à jour 2019 et 2026) (ameli.fr, PDF)",
            "url": "https://www.ameli.fr/sites/default/files/Documents/R486B-juillet2026.pdf"
          },
          {
            "libelle": "Assurance Maladie (ameli.fr), tableau des recommandations (page listant R482B à R491)",
            "url": "https://www.ameli.fr/entreprise/tableau_recommandations?page=3"
          },
          {
            "libelle": "INRS, Caces : ce qu'il faut retenir (mis à jour le 30/07/2026)",
            "url": "https://www.inrs.fr/demarche/caces-certificat-aptitude-conduite-securite/ce-qu-il-faut-retenir.html"
          },
          {
            "libelle": "INRS ED 6348, Questions-réponses formation, autorisation de conduite et Caces, 3e éd. sept. 2026 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6348.pdf"
          }
        ],
        "delivre_par": "Organisme testeur certifié (OTC), épreuves sous le contrôle d'un testeur qualifié",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H11",
        "famille": "CACES",
        "type": "CACES R487 – Grues à tour",
        "titres": "Cat. 1 grues à tour à montage par éléments, à flèche distributrice ; Cat. 2 grues à tour à montage par éléments, à flèche relevable ; Cat. 3 grues à tour à montage automatisé",
        "duree_mois": 60,
        "duree_texte": "5 ans (validité du certificat ; actualisation « au moins tous les 5 ans »)",
        "nature_source": "recommandation",
        "reference": "Recommandation Cnam R.487A (adoptée en 2017 ; mise à jour 2026), § 3/3/5 « Actualisation » et annexe 1 (catégories)",
        "liens": [
          {
            "libelle": "Recommandation R.487A (adoptée en 2017 ; mise à jour 2026) (ameli.fr, PDF)",
            "url": "https://www.ameli.fr/sites/default/files/Documents/R487A-juillet2026.pdf"
          },
          {
            "libelle": "Assurance Maladie (ameli.fr), tableau des recommandations (page listant R482B à R491)",
            "url": "https://www.ameli.fr/entreprise/tableau_recommandations?page=3"
          },
          {
            "libelle": "INRS, Caces : ce qu'il faut retenir (mis à jour le 30/07/2026)",
            "url": "https://www.inrs.fr/demarche/caces-certificat-aptitude-conduite-securite/ce-qu-il-faut-retenir.html"
          },
          {
            "libelle": "INRS ED 6348, Questions-réponses formation, autorisation de conduite et Caces, 3e éd. sept. 2026 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6348.pdf"
          }
        ],
        "delivre_par": "Organisme testeur certifié (OTC), épreuves sous le contrôle d'un testeur qualifié",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H12",
        "famille": "CACES",
        "type": "CACES R489 – Chariots de manutention automoteurs à conducteur porté",
        "titres": "Cat. 1A transpalettes à conducteur porté ; 1B gerbeurs à conducteur porté (hauteur de levée > 1,20 m) ; 2A chariots à plateau porteur (≤ 2 t) ; 2B chariots tracteurs industriels (traction ≤ 25 t) ; 3 chariots élévateurs frontaux en porte-à-faux (≤ 6 t) ; 4 chariots élévateurs frontaux en porte-à-faux (> 6 t) ; 5 chariots élévateurs à mât rétractable ; 6 chariots élévateurs à poste de conduite élevable (plancher > 1,20 m) ; 7 conduite hors production des chariots de toutes les catégories",
        "duree_mois": 60,
        "duree_texte": "5 ans (validité du certificat ; actualisation « au moins tous les 5 ans »)",
        "nature_source": "recommandation",
        "reference": "Recommandation Cnam R.489A (adoptée en 2017 ; mise à jour 2026), § 3/3/5 « Actualisation » et annexe 1 (catégories)",
        "liens": [
          {
            "libelle": "Recommandation R.489A (adoptée en 2017 ; mise à jour 2026) (ameli.fr, PDF)",
            "url": "https://www.ameli.fr/sites/default/files/Documents/R489A-juillet2026.pdf"
          },
          {
            "libelle": "Assurance Maladie (ameli.fr), tableau des recommandations (page listant R482B à R491)",
            "url": "https://www.ameli.fr/entreprise/tableau_recommandations?page=3"
          },
          {
            "libelle": "INRS, Caces : ce qu'il faut retenir (mis à jour le 30/07/2026)",
            "url": "https://www.inrs.fr/demarche/caces-certificat-aptitude-conduite-securite/ce-qu-il-faut-retenir.html"
          },
          {
            "libelle": "INRS ED 6348, Questions-réponses formation, autorisation de conduite et Caces, 3e éd. sept. 2026 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6348.pdf"
          }
        ],
        "delivre_par": "Organisme testeur certifié (OTC), épreuves sous le contrôle d'un testeur qualifié",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H13",
        "famille": "CACES",
        "type": "CACES R490 – Grues de chargement",
        "titres": "Catégorie unique : grues de chargement (ex-« grues auxiliaires », norme NF EN 12999+A1:2012) ; option « télécommande »",
        "duree_mois": 60,
        "duree_texte": "5 ans (validité du certificat ; actualisation « au moins tous les 5 ans »)",
        "nature_source": "recommandation",
        "reference": "Recommandation Cnam R.490A (adoptée en 2017 ; mise à jour 2026), § 3/3/5 « Actualisation » et annexe 1 (catégories)",
        "liens": [
          {
            "libelle": "Recommandation R.490A (adoptée en 2017 ; mise à jour 2026) (ameli.fr, PDF)",
            "url": "https://www.ameli.fr/sites/default/files/Documents/R490A-juillet2026.pdf"
          },
          {
            "libelle": "Assurance Maladie (ameli.fr), tableau des recommandations (page listant R482B à R491)",
            "url": "https://www.ameli.fr/entreprise/tableau_recommandations?page=3"
          },
          {
            "libelle": "INRS, Caces : ce qu'il faut retenir (mis à jour le 30/07/2026)",
            "url": "https://www.inrs.fr/demarche/caces-certificat-aptitude-conduite-securite/ce-qu-il-faut-retenir.html"
          },
          {
            "libelle": "INRS ED 6348, Questions-réponses formation, autorisation de conduite et Caces, 3e éd. sept. 2026 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6348.pdf"
          }
        ],
        "delivre_par": "Organisme testeur certifié (OTC), épreuves sous le contrôle d'un testeur qualifié",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H14",
        "famille": "Autorisation de conduite",
        "type": "Autorisation de conduite (employeur)",
        "titres": "Obligatoire pour : grues à tour ; grues mobiles ; grues auxiliaires de chargement ; chariots automoteurs de manutention à conducteur porté ; plates-formes élévatrices mobiles de personnes ; engins de chantier télécommandés ou à conducteur porté (arrêté du 26 sept. 2025, art. 2). Recommandée (Cnam) : ponts roulants et portiques, gerbeurs à conducteur accompagnant.",
        "duree_mois": null,
        "duree_texte": "Aucune durée fixée par les textes ; date limite de validité laissée à l'employeur",
        "nature_source": "obligation",
        "reference": "Code du travail R4323-55 (formation adéquate, « complétée et réactualisée chaque fois que nécessaire »), R4323-56 (autorisation délivrée par l'employeur), R4323-57 ; arrêté du 26 septembre 2025 (NOR TSST2525765A), art. 2 et 3, qui abroge l'arrêté du 2 décembre 1998 depuis le 1er oct. 2025",
        "liens": [
          {
            "libelle": "Code du travail, art. R4323-55 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000018531407"
          },
          {
            "libelle": "Code du travail, art. R4323-56, version au 1er oct. 2025 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051500371"
          },
          {
            "libelle": "Code du travail, art. R4323-57 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000018531403"
          },
          {
            "libelle": "Arrêté du 26 septembre 2025 relatif à la formation à la conduite des équipements de travail mobiles automoteurs et des équipements de levage de charges ou de personnes, NOR TSST2525765A (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052304307"
          },
          {
            "libelle": "Arrêté du 2 décembre 1998 (NOR MEST9811274A) : ABROGÉ au 1er oct. 2025 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/loda/id/LEGITEXT000005627030"
          },
          {
            "libelle": "INRS ED 6348, Questions-réponses formation, autorisation de conduite et Caces, 3e éd. sept. 2026 (PDF)",
            "url": "https://www.inrs.fr/dam/inrs/CataloguePapier/ED/TI-ED-6348.pdf"
          },
          {
            "libelle": "INRS, Caces : autorisation de conduite (mis à jour le 30/07/2026)",
            "url": "https://www.inrs.fr/demarche/caces-certificat-aptitude-conduite-securite/autorisation-conduite.html"
          }
        ],
        "delivre_par": "Employeur (chef d'établissement ou son délégataire)",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      },
      {
        "id": "H15",
        "famille": "Autorisation de conduite",
        "type": "Attestation médicale – conduite d'engins",
        "titres": "Attestation d'absence de contre-indications médicales à la conduite des équipements des 6 familles soumises à autorisation de conduite (arrêté du 26 sept. 2025, art. 2)",
        "duree_mois": 60,
        "duree_texte": "5 ans (validité de l'attestation)",
        "nature_source": "obligation",
        "reference": "Code du travail R4323-56 (version issue du décret n° 2025-355 du 18 avril 2025, en vigueur le 1er oct. 2025) ; arrêté du 26 septembre 2025 (NOR TSST2525765A), art. 3 a) ; modèle : arrêté du 26 septembre 2025 (NOR TSST2525767A), annexe 1",
        "liens": [
          {
            "libelle": "Code du travail, art. R4323-56, version au 1er oct. 2025 (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051500371"
          },
          {
            "libelle": "Arrêté du 26 septembre 2025 relatif à la formation à la conduite des équipements de travail mobiles automoteurs et des équipements de levage de charges ou de personnes, NOR TSST2525765A (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052304307"
          },
          {
            "libelle": "Arrêté du 26 septembre 2025 fixant les modèles d'attestation d'absence de contre-indications médicales (R4323-56 et R4544-9), NOR TSST2525767A (Légifrance)",
            "url": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052304220"
          },
          {
            "libelle": "Décret n° 2025-355 du 18 avril 2025 (Légifrance, non ouvert : contenu lu via les articles modifiés)",
            "url": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000051491350"
          }
        ],
        "delivre_par": "Médecin du travail, à l'issue d'un examen médical qu'il réalise",
        "a_confirmer": false,
        "relu_le": "2026-11-08",
        "mention": ""
      }
    ]
  });
})();
