'use strict';
// AideEcransTextes : textes de l'aide à l'écran (encart de la première visite), validés par Nicolas le 2026-10-25.
// Produit par outils/generer_aide_ecrans.py (source : AIDE-ECRANS.md § 2, dossier de conception du site) : ne pas
// retoucher à la main. Une entrée par identifiant d'écran (App.ecran) : titre, ancre du guide, texte et geste
// « Essayez », ou une variante par profil ; « demo » = phrase ajoutée dans la version web. Un écran sans entrée
// prend celle de son parent ; À propos n'en a pas. Les textes sont dans js/i18n/aide/<langue>.js (clés
// aide.ecran.*) : chaque accesseur les lit dans la langue active au moment de l'affichage (repli français sans
// avertissement, js/i18n.js).

const AideEcransTextes = {
  accueil: {
    get titre() { return I18n.t('aide.ecran.accueil.titre'); },
    ancre: 'accueil',
    profils: {
      responsable: {
        get texte() { return I18n.t('aide.ecran.accueil.responsable.texte'); },
        get essayez() { return I18n.t('aide.ecran.accueil.responsable.essayez'); },
      },
      technicien: {
        get texte() { return I18n.t('aide.ecran.accueil.technicien.texte'); },
        get essayez() { return I18n.t('aide.ecran.accueil.technicien.essayez'); },
      },
      demandeur: {
        get texte() { return I18n.t('aide.ecran.accueil.demandeur.texte'); },
        get essayez() { return I18n.t('aide.ecran.accueil.demandeur.essayez'); },
      },
    },
    get demo() { return I18n.t('aide.ecran.accueil.demo'); },
  },
  "nouvelle-di": {
    get titre() { return I18n.t('aide.ecran.nouvelle_di.titre'); },
    ancre: 'signaler',
    get texte() { return I18n.t('aide.ecran.nouvelle_di.texte'); },
    get essayez() { return I18n.t('aide.ecran.nouvelle_di.essayez'); },
  },
  "liste-di": {
    get titre() { return I18n.t('aide.ecran.liste_di.titre'); },
    ancre: 'demandes',
    profils: {
      responsable: {
        get texte() { return I18n.t('aide.ecran.liste_di.responsable.texte'); },
        get essayez() { return I18n.t('aide.ecran.liste_di.responsable.essayez'); },
      },
      technicien: {
        get texte() { return I18n.t('aide.ecran.liste_di.technicien.texte'); },
        get essayez() { return I18n.t('aide.ecran.liste_di.technicien.essayez'); },
      },
      demandeur: {
        get texte() { return I18n.t('aide.ecran.liste_di.demandeur.texte'); },
        get essayez() { return I18n.t('aide.ecran.liste_di.demandeur.essayez'); },
      },
    },
  },
  "fiche-di": {
    get titre() { return I18n.t('aide.ecran.fiche_di.titre'); },
    ancre: 'demandes',
    get texte() { return I18n.t('aide.ecran.fiche_di.texte'); },
    get essayez() { return I18n.t('aide.ecran.fiche_di.essayez'); },
  },
  "liste-ot": {
    get titre() { return I18n.t('aide.ecran.liste_ot.titre'); },
    ancre: 'ordres',
    profils: {
      responsable: {
        get texte() { return I18n.t('aide.ecran.liste_ot.responsable.texte'); },
        get essayez() { return I18n.t('aide.ecran.liste_ot.responsable.essayez'); },
      },
      technicien: {
        get texte() { return I18n.t('aide.ecran.liste_ot.technicien.texte'); },
        get essayez() { return I18n.t('aide.ecran.liste_ot.technicien.essayez'); },
      },
    },
  },
  "fiche-ot": {
    get titre() { return I18n.t('aide.ecran.fiche_ot.titre'); },
    ancre: 'ordres',
    profils: {
      responsable: {
        get texte() { return I18n.t('aide.ecran.fiche_ot.responsable.texte'); },
        get essayez() { return I18n.t('aide.ecran.fiche_ot.responsable.essayez'); },
      },
      technicien: {
        get texte() { return I18n.t('aide.ecran.fiche_ot.technicien.texte'); },
        get essayez() { return I18n.t('aide.ecran.fiche_ot.technicien.essayez'); },
      },
    },
  },
  planning: {
    get titre() { return I18n.t('aide.ecran.planning.titre'); },
    ancre: 'planning',
    get texte() { return I18n.t('aide.ecran.planning.texte'); },
    get essayez() { return I18n.t('aide.ecran.planning.essayez'); },
  },
  preventif: {
    get titre() { return I18n.t('aide.ecran.preventif.titre'); },
    ancre: 'preventif',
    get texte() { return I18n.t('aide.ecran.preventif.texte'); },
    get essayez() { return I18n.t('aide.ecran.preventif.essayez'); },
  },
  "preventif-gamme": {
    get titre() { return I18n.t('aide.ecran.preventif_gamme.titre'); },
    ancre: 'preventif',
    get texte() { return I18n.t('aide.ecran.preventif_gamme.texte'); },
    get essayez() { return I18n.t('aide.ecran.preventif_gamme.essayez'); },
  },
  magasin: {
    get titre() { return I18n.t('aide.ecran.magasin.titre'); },
    ancre: 'magasin',
    get texte() { return I18n.t('aide.ecran.magasin.texte'); },
    get essayez() { return I18n.t('aide.ecran.magasin.essayez'); },
  },
  "magasin-article": {
    get titre() { return I18n.t('aide.ecran.magasin_article.titre'); },
    ancre: 'magasin',
    get texte() { return I18n.t('aide.ecran.magasin_article.texte'); },
    get essayez() { return I18n.t('aide.ecran.magasin_article.essayez'); },
  },
  parc: {
    get titre() { return I18n.t('aide.ecran.parc.titre'); },
    ancre: 'parc',
    get texte() { return I18n.t('aide.ecran.parc.texte'); },
    get essayez() { return I18n.t('aide.ecran.parc.essayez'); },
  },
  equipement: {
    get titre() { return I18n.t('aide.ecran.equipement.titre'); },
    ancre: 'parc',
    get texte() { return I18n.t('aide.ecran.equipement.texte'); },
    get essayez() { return I18n.t('aide.ecran.equipement.essayez'); },
  },
  "parc-etiquettes": {
    get titre() { return I18n.t('aide.ecran.parc_etiquettes.titre'); },
    ancre: 'parc',
    get texte() { return I18n.t('aide.ecran.parc_etiquettes.texte'); },
    get essayez() { return I18n.t('aide.ecran.parc_etiquettes.essayez'); },
  },
  controles: {
    get titre() { return I18n.t('aide.ecran.controles.titre'); },
    ancre: 'controles',
    get texte() { return I18n.t('aide.ecran.controles.texte'); },
    get essayez() { return I18n.t('aide.ecran.controles.essayez'); },
  },
  "controles-fiche": {
    get titre() { return I18n.t('aide.ecran.controles_fiche.titre'); },
    ancre: 'controles',
    get texte() { return I18n.t('aide.ecran.controles_fiche.texte'); },
    get essayez() { return I18n.t('aide.ecran.controles_fiche.essayez'); },
  },
  equipe: {
    get titre() { return I18n.t('aide.ecran.equipe.titre'); },
    ancre: 'equipe',
    get texte() { return I18n.t('aide.ecran.equipe.texte'); },
    get essayez() { return I18n.t('aide.ecran.equipe.essayez'); },
  },
  "equipe-fiche": {
    get titre() { return I18n.t('aide.ecran.equipe_fiche.titre'); },
    ancre: 'equipe',
    get texte() { return I18n.t('aide.ecran.equipe_fiche.texte'); },
    get essayez() { return I18n.t('aide.ecran.equipe_fiche.essayez'); },
  },
  indicateurs: {
    get titre() { return I18n.t('aide.ecran.indicateurs.titre'); },
    ancre: 'indicateurs',
    get texte() { return I18n.t('aide.ecran.indicateurs.texte'); },
    get essayez() { return I18n.t('aide.ecran.indicateurs.essayez'); },
  },
  parametres: {
    get titre() { return I18n.t('aide.ecran.parametres.titre'); },
    ancre: 'parametres',
    get texte() { return I18n.t('aide.ecran.parametres.texte'); },
    get essayez() { return I18n.t('aide.ecran.parametres.essayez'); },
  },
  import: {
    get titre() { return I18n.t('aide.ecran.import.titre'); },
    ancre: 'import-etapes',
    get texte() { return I18n.t('aide.ecran.import.texte'); },
    get essayez() { return I18n.t('aide.ecran.import.essayez'); },
  },
  controle: {
    get titre() { return I18n.t('aide.ecran.controle.titre'); },
    ancre: 'parametres',
    get texte() { return I18n.t('aide.ecran.controle.texte'); },
    get essayez() { return I18n.t('aide.ecran.controle.essayez'); },
  },
  poste: {
    get titre() { return I18n.t('aide.ecran.poste.titre'); },
    ancre: 'ce-poste',
    get texte() { return I18n.t('aide.ecran.poste.texte'); },
    get essayez() { return I18n.t('aide.ecran.poste.essayez'); },
  },
  wiki: {
    get titre() { return I18n.t('aide.ecran.wiki.titre'); },
    ancre: 'wiki',
    get texte() { return I18n.t('aide.ecran.wiki.texte'); },
    get essayez() { return I18n.t('aide.ecran.wiki.essayez'); },
  },
  "wiki-liste": {
    get titre() { return I18n.t('aide.ecran.wiki_liste.titre'); },
    ancre: 'wiki',
    get texte() { return I18n.t('aide.ecran.wiki_liste.texte'); },
    get essayez() { return I18n.t('aide.ecran.wiki_liste.essayez'); },
  },
  "wiki-page": {
    get titre() { return I18n.t('aide.ecran.wiki_page.titre'); },
    ancre: 'wiki-pages',
    profils: {
      technicien: {
        get texte() { return I18n.t('aide.ecran.wiki_page.technicien.texte'); },
        get essayez() { return I18n.t('aide.ecran.wiki_page.technicien.essayez'); },
      },
      responsable: {
        get texte() { return I18n.t('aide.ecran.wiki_page.responsable.texte'); },
        get essayez() { return I18n.t('aide.ecran.wiki_page.responsable.essayez'); },
      },
      demandeur: {
        get texte() { return I18n.t('aide.ecran.wiki_page.demandeur.texte'); },
        get essayez() { return I18n.t('aide.ecran.wiki_page.demandeur.essayez'); },
      },
    },
  },
  "wiki-ecrire": {
    get titre() { return I18n.t('aide.ecran.wiki_ecrire.titre'); },
    ancre: 'wiki-ecrire',
    get texte() { return I18n.t('aide.ecran.wiki_ecrire.texte'); },
    get essayez() { return I18n.t('aide.ecran.wiki_ecrire.essayez'); },
  },
  "wiki-journal": {
    get titre() { return I18n.t('aide.ecran.wiki_journal.titre'); },
    ancre: 'wiki-journal',
    get texte() { return I18n.t('aide.ecran.wiki_journal.texte'); },
    get essayez() { return I18n.t('aide.ecran.wiki_journal.essayez'); },
    get demo() { return I18n.t('aide.ecran.wiki_journal.demo'); },
  },
};
