'use strict';
// AccesTextes : textes d'aide de l'accès et de l'installation, une seule source pour l'assistant, Paramètres,
// Équipe › Accès et le guide (lot 7, CS124, CS130). Produit par outils/generer_acces_textes.py à partir de
// CLES_CONFIGURATION de serveur.py (options) et des textes de l'étude validée (choix) : ne pas retoucher à la main.
// Les textes sont dans js/i18n/aide/<langue>.js (clés aide.acces.*) : chaque accesseur les lit dans la langue
// active au moment de l'affichage (repli français sans avertissement, js/i18n.js).

const AccesTextes = {
  situations: {
    get seul() { return I18n.t('aide.acces.situation.seul'); },
    get equipe() { return I18n.t('aide.acces.situation.equipe'); },
    get informaticien() { return I18n.t('aide.acces.situation.informaticien'); },
  },
  choix: {
    installation: {
      get titre() { return I18n.t('aide.acces.choix.installation.titre'); },
      get qui() { return I18n.t('aide.acces.choix.installation.qui'); },
      get change() { return I18n.t('aide.acces.choix.installation.change'); },
      get pourquoi() { return I18n.t('aide.acces.choix.installation.pourquoi'); },
      conseil: {
        get seul() { return I18n.t('aide.acces.choix.installation.conseil.seul'); },
        get equipe() { return I18n.t('aide.acces.choix.installation.conseil.equipe'); },
        get informaticien() { return I18n.t('aide.acces.choix.installation.conseil.informaticien'); },
      },
    },
    mot_de_passe: {
      get titre() { return I18n.t('aide.acces.choix.mot_de_passe.titre'); },
      get qui() { return I18n.t('aide.acces.choix.mot_de_passe.qui'); },
      get change() { return I18n.t('aide.acces.choix.mot_de_passe.change'); },
      get pourquoi() { return I18n.t('aide.acces.choix.mot_de_passe.pourquoi'); },
      conseil: {
        get seul() { return I18n.t('aide.acces.choix.mot_de_passe.conseil.seul'); },
        get equipe() { return I18n.t('aide.acces.choix.mot_de_passe.conseil.equipe'); },
        get informaticien() { return I18n.t('aide.acces.choix.mot_de_passe.conseil.informaticien'); },
      },
    },
    etiquettes: {
      get titre() { return I18n.t('aide.acces.choix.etiquettes.titre'); },
      get qui() { return I18n.t('aide.acces.choix.etiquettes.qui'); },
      get change() { return I18n.t('aide.acces.choix.etiquettes.change'); },
      get pourquoi() { return I18n.t('aide.acces.choix.etiquettes.pourquoi'); },
      conseil: {
        get seul() { return I18n.t('aide.acces.choix.etiquettes.conseil.seul'); },
        get equipe() { return I18n.t('aide.acces.choix.etiquettes.conseil.equipe'); },
        get informaticien() { return I18n.t('aide.acces.choix.etiquettes.conseil.informaticien'); },
      },
    },
    exterieur: {
      get titre() { return I18n.t('aide.acces.choix.exterieur.titre'); },
      get qui() { return I18n.t('aide.acces.choix.exterieur.qui'); },
      get change() { return I18n.t('aide.acces.choix.exterieur.change'); },
      get pourquoi() { return I18n.t('aide.acces.choix.exterieur.pourquoi'); },
      conseil: {
        get seul() { return I18n.t('aide.acces.choix.exterieur.conseil.seul'); },
        get equipe() { return I18n.t('aide.acces.choix.exterieur.conseil.equipe'); },
        get informaticien() { return I18n.t('aide.acces.choix.exterieur.conseil.informaticien'); },
      },
    },
    demarrage: {
      get titre() { return I18n.t('aide.acces.choix.demarrage.titre'); },
      get qui() { return I18n.t('aide.acces.choix.demarrage.qui'); },
      get change() { return I18n.t('aide.acces.choix.demarrage.change'); },
      get pourquoi() { return I18n.t('aide.acces.choix.demarrage.pourquoi'); },
      conseil: {
        get seul() { return I18n.t('aide.acces.choix.demarrage.conseil.seul'); },
        get equipe() { return I18n.t('aide.acces.choix.demarrage.conseil.equipe'); },
        get informaticien() { return I18n.t('aide.acces.choix.demarrage.conseil.informaticien'); },
      },
    },
    veille: {
      get titre() { return I18n.t('aide.acces.choix.veille.titre'); },
      get qui() { return I18n.t('aide.acces.choix.veille.qui'); },
      get change() { return I18n.t('aide.acces.choix.veille.change'); },
      get pourquoi() { return I18n.t('aide.acces.choix.veille.pourquoi'); },
      conseil: {
        get seul() { return I18n.t('aide.acces.choix.veille.conseil.seul'); },
        get equipe() { return I18n.t('aide.acces.choix.veille.conseil.equipe'); },
        get informaticien() { return I18n.t('aide.acces.choix.veille.conseil.informaticien'); },
      },
    },
    certificat: {
      get titre() { return I18n.t('aide.acces.choix.certificat.titre'); },
      get qui() { return I18n.t('aide.acces.choix.certificat.qui'); },
      get change() { return I18n.t('aide.acces.choix.certificat.change'); },
      get pourquoi() { return I18n.t('aide.acces.choix.certificat.pourquoi'); },
      conseil: {
        get seul() { return I18n.t('aide.acces.choix.certificat.conseil.seul'); },
        get equipe() { return I18n.t('aide.acces.choix.certificat.conseil.equipe'); },
        get informaticien() { return I18n.t('aide.acces.choix.certificat.conseil.informaticien'); },
      },
    },
    sauvegardes: {
      get titre() { return I18n.t('aide.acces.choix.sauvegardes.titre'); },
      get qui() { return I18n.t('aide.acces.choix.sauvegardes.qui'); },
      get change() { return I18n.t('aide.acces.choix.sauvegardes.change'); },
      get pourquoi() { return I18n.t('aide.acces.choix.sauvegardes.pourquoi'); },
      conseil: {
        get seul() { return I18n.t('aide.acces.choix.sauvegardes.conseil.seul'); },
        get equipe() { return I18n.t('aide.acces.choix.sauvegardes.conseil.equipe'); },
        get informaticien() { return I18n.t('aide.acces.choix.sauvegardes.conseil.informaticien'); },
      },
    },
    ia: {
      get titre() { return I18n.t('aide.acces.choix.ia.titre'); },
      get qui() { return I18n.t('aide.acces.choix.ia.qui'); },
      get change() { return I18n.t('aide.acces.choix.ia.change'); },
      get pourquoi() { return I18n.t('aide.acces.choix.ia.pourquoi'); },
      conseil: {
        get seul() { return I18n.t('aide.acces.choix.ia.conseil.seul'); },
        get equipe() { return I18n.t('aide.acces.choix.ia.conseil.equipe'); },
        get informaticien() { return I18n.t('aide.acces.choix.ia.conseil.informaticien'); },
      },
    },
  },
  options: {
    portee: {
      get aide() { return I18n.t('aide.acces.option.portee'); },
      defaut: 'ce-pc',
      genre: 'choix:ce-pc|atelier|dehors',
    },
    ecoute: {
      get aide() { return I18n.t('aide.acces.option.ecoute'); },
      defaut: '127.0.0.1',
      genre: 'choix:127.0.0.1|0.0.0.0',
    },
    port_http: {
      get aide() { return I18n.t('aide.acces.option.port_http'); },
      defaut: 8080,
      genre: 'entier',
    },
    port_https: {
      get aide() { return I18n.t('aide.acces.option.port_https'); },
      defaut: 8443,
      genre: 'entier',
    },
    noms: {
      get aide() { return I18n.t('aide.acces.option.noms'); },
      defaut: '',
      genre: 'liste',
    },
    certificat: {
      get aide() { return I18n.t('aide.acces.option.certificat'); },
      defaut: '',
      genre: 'texte',
    },
    cle: {
      get aide() { return I18n.t('aide.acces.option.cle'); },
      defaut: '',
      genre: 'texte',
    },
    certificat_auto: {
      get aide() { return I18n.t('aide.acces.option.certificat_auto'); },
      defaut: true,
      genre: 'booleen',
    },
    mandataire: {
      get aide() { return I18n.t('aide.acces.option.mandataire'); },
      defaut: false,
      genre: 'booleen',
    },
    comptes: {
      get aide() { return I18n.t('aide.acces.option.comptes'); },
      defaut: false,
      genre: 'booleen',
    },
    demandeurs_avec_compte: {
      get aide() { return I18n.t('aide.acces.option.demandeurs_avec_compte'); },
      defaut: false,
      genre: 'booleen',
    },
    session_heures: {
      get aide() { return I18n.t('aide.acces.option.session_heures'); },
      defaut: 12,
      genre: 'entier',
    },
    session_longue_jours: {
      get aide() { return I18n.t('aide.acces.option.session_longue_jours'); },
      defaut: 30,
      genre: 'entier',
    },
    invitation_heures: {
      get aide() { return I18n.t('aide.acces.option.invitation_heures'); },
      defaut: 24,
      genre: 'entier',
    },
    demarrage: {
      get aide() { return I18n.t('aide.acces.option.demarrage'); },
      defaut: 'aucun',
      genre: 'choix:aucun|systeme|session',
    },
    veille_desactivee: {
      get aide() { return I18n.t('aide.acces.option.veille_desactivee'); },
      defaut: false,
      genre: 'booleen',
    },
    copie_sauvegardes: {
      get aide() { return I18n.t('aide.acces.option.copie_sauvegardes'); },
      defaut: '',
      genre: 'texte',
    },
    quota_documents_mo: {
      get aide() { return I18n.t('aide.acces.option.quota_documents_mo'); },
      defaut: 4096,
      genre: 'entier',
    },
    ia_fournisseur: {
      get aide() { return I18n.t('aide.acces.option.ia_fournisseur'); },
      defaut: 'ollama',
      genre: 'choix:ollama|openai',
    },
    ia_url: {
      get aide() { return I18n.t('aide.acces.option.ia_url'); },
      defaut: 'http://localhost:11434',
      genre: 'texte',
    },
    ia_cle: {
      get aide() { return I18n.t('aide.acces.option.ia_cle'); },
      defaut: '',
      genre: 'texte',
    },
    ia_en_ligne: {
      get aide() { return I18n.t('aide.acces.option.ia_en_ligne'); },
      defaut: false,
      genre: 'booleen',
    },
  },
};
