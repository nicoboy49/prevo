'use strict';
// Parc : arborescence des localisations et des équipements, fiche équipement (consignation,
// historique, QR code, valeur de remplacement, relevés de compteur, gammes préventives),
// création et modification (brief §6 « equipements » et « localisations », §9 E7,
// ARCHITECTURE.md §8, §10 et §14.6).
//
// Écrans :
//   #/parc                       arborescence site › atelier › ligne, recherche, inactifs (tous les profils)
//   #/equipement/<id>            fiche complète (tous les profils)
//   #/equipement/nouveau         formulaire de création (responsable)
//   #/equipement/<id>/modifier   formulaire de modification (responsable)
//   Les localisations se créent et se modifient dans une fenêtre, depuis le parc (responsable).
//
// Fonctions offertes aux autres modules :
//   Parc.cheminLocalisation(id)   « Site des Trois Vallées › Atelier Utilités »
//   Parc.libelleEquipement(id)    « PO-02 — Pompe centrifuge eau de refroidissement »
//
// Règles de gestion : un équipement n'est jamais supprimé (champ `actif`), le repère est unique
// parmi les équipements actifs, un équipement ne peut pas être son propre ancêtre.
//
// Le module est découpé en cinq fichiers, chargés dans cet ordre par index.html (ARCHITECTURE.md
// §14.2, décision D28 : 700 lignes au plus par fichier) :
//   parc-regles.js         CE FICHIER, qui crée l'objet Parc :
//                            1. Petits outils (aussi offerts aux autres modules)   2. Contrôles de saisie (purs)
//   parc-arbre.js          3. Écran #/parc : arborescence
//   parc-formulaires.js    4. Localisation : fenêtre de création et de modification
//                          6. Écrans #/equipement/nouveau et #/equipement/<id>/modifier : formulaire
//                          8. Relevé de compteur : fenêtre de saisie et écriture
//   parc-etiquettes.js     9. Étiquettes QR par lot : sélection, planches A4 (lot 3, §15.6)
//   parc-fiche.js          5. Écran #/equipement/<id> : fiche   7. Enregistrement des écrans
// Les fichiers suivants complètent l'objet : Object.assign(Parc, (() => { … return { … }; })()).
// Une fonction dont un autre fichier du module a besoin est rangée dans Parc.interne (usage
// interne au module : ce n'est pas une API, ni les autres modules ni les tests ne s'en servent).

const Parc = (() => {

  const SEPARATEUR_CHEMIN = ' › ';

  // ===========================================================================================
  // 1. Petits outils (aussi offerts aux autres modules)
  // ===========================================================================================

  function estActif(ligne) {
    return ligne.actif !== '0';
  }

  function comparerTextes(a, b) {
    return String(a || '').localeCompare(String(b || ''), 'fr', { numeric: true, sensitivity: 'base' });
  }

  function parRepere(a, b) {
    return comparerTextes(a.repere, b.repere);
  }

  /** « Site › Atelier › Ligne » d'une localisation. Identifiant inconnu : l'identifiant lui-même. */
  function cheminLocalisation(id) {
    if (!id) return '';
    let courante = Donnees.trouver('localisations', id);
    if (!courante) return id;
    const libelles = [];
    const dejaVues = new Set();
    while (courante && !dejaVues.has(courante.id)) {      // dejaVues : protège d'une boucle dans les données
      dejaVues.add(courante.id);
      libelles.unshift(courante.libelle || courante.id);
      courante = courante.parent_id ? Donnees.trouver('localisations', courante.parent_id) : null;
    }
    return libelles.join(SEPARATEUR_CHEMIN);
  }

  /** « PO-02 — Pompe centrifuge eau de refroidissement ». Identifiant inconnu : l'identifiant lui-même. */
  function libelleEquipement(id) {
    if (!id) return '';
    const equipement = Donnees.trouver('equipements', id);
    if (!equipement) return id;
    const repere = equipement.repere || equipement.id;
    return equipement.designation ? repere + ' — ' + equipement.designation : repere;
  }

  /** Identifiants de tous les descendants d'une ligne (table à `parent_id`), elle-même exclue. */
  function identifiantsDescendants(nomTable, id) {
    const resultat = new Set();
    const lignes = Donnees.lignes(nomTable);
    const aTraiter = [id];
    while (aTraiter.length) {
      const courant = aTraiter.pop();
      lignes.forEach((ligne) => {
        if (ligne.parent_id === courant && ligne.id !== id && !resultat.has(ligne.id)) {
          resultat.add(ligne.id);
          aTraiter.push(ligne.id);
        }
      });
    }
    return resultat;
  }

  // Vrai si, en remontant les `parent_id` depuis `id`, on retombe sur `id` (boucle dans les données).
  function remonteSurSoi(id, lignesParId) {
    const dejaVus = new Set([id]);
    let courant = lignesParId.get(id);
    while (courant && courant.parent_id) {
      if (dejaVus.has(courant.parent_id)) return courant.parent_id === id;
      dejaVus.add(courant.parent_id);
      courant = lignesParId.get(courant.parent_id);
    }
    return false;
  }

  function abreger(texte, longueurMax) {
    const propre = String(texte || '').replace(/\s+/g, ' ').trim();
    return propre.length > longueurMax ? propre.slice(0, longueurMax - 1).trimEnd() + '…' : propre;
  }

  function badgeCriticite(criticite) {
    const tons = { A: 'ko', B: 'attention', C: 'neutre' };
    const libelles = { A: 'très critique', B: 'critique', C: 'peu critique' };
    if (!tons[criticite]) return UI.html`<span class="badge neutre" title="Criticité non renseignée">Crit. —</span>`;
    return UI.html`<span class="badge ${tons[criticite]}" title="Criticité ${criticite} (${libelles[criticite]})">Crit. ${criticite}</span>`;
  }

  // Badges d'une ligne de l'arbre : criticité, statut s'il n'est pas « en service », mention inactif.
  function badgesEquipement(equipement) {
    return UI.html`${badgeCriticite(equipement.criticite)}
      ${equipement.statut && equipement.statut !== 'en service' ? UI.badgeStatut(equipement.statut) : ''}
      ${estActif(equipement) ? '' : UI.html`<span class="badge neutre barre" title="Équipement désactivé">Inactif</span>`}`;
  }

  // Liste « tableau sur ordinateur, cartes sur téléphone » : le tableau déborderait de l'écran.
  // `carte(ligne)` rend le lien (<a>) d'une carte ; `lien(ligne)` donne la route d'une ligne cliquable.
  function listeAdaptative({ colonnes, lignes, vide, libelle, lien, carte }) {
    if (UI.estTelephone()) {
      if (!lignes.length) return UI.element(UI.html`<p class="muted">${vide}</p>`);
      return UI.element(UI.html`<ul class="liste-cartes">${lignes.map((ligne) => UI.html`<li>${carte(ligne)}</li>`)}</ul>`);
    }
    return UI.tableau({
      colonnes, lignes, vide, libelle,
      surClic: lien ? (ligne) => App.naviguer(lien(ligne)) : undefined,
    });
  }

  // ===========================================================================================
  // 2. Contrôles de saisie (purs : testés sans écran)
  // ===========================================================================================

  /**
   * Contrôle les valeurs d'un équipement. Renvoie [{ nom, message }] (vide si tout va bien).
   *   valeurs : champs du formulaire ; lignesEquipements / lignesLocalisations : données à jour ;
   *   idCourant : identifiant de l'équipement modifié ('' pour une création).
   */
  function verifierEquipement(valeurs, lignesEquipements, lignesLocalisations, idCourant) {
    const erreurs = [];
    const courant = lignesEquipements.find((e) => e.id === idCourant);
    const seraActif = !courant || estActif(courant);
    const repere = String(valeurs.repere || '').trim();

    if (!repere) {
      erreurs.push({ nom: 'repere', message: 'Le repère est obligatoire (ex. PO-02).' });
    } else if (seraActif) {
      const motif = UI.normaliserRecherche(repere);
      const double = lignesEquipements.find((e) => e.id !== idCourant && estActif(e) && UI.normaliserRecherche(e.repere) === motif);
      if (double) {
        erreurs.push({ nom: 'repere', message: 'Le repère « ' + repere + ' » est déjà utilisé par un équipement actif : '
          + libelleEquipement(double.id) + '. Choisissez-en un autre.' });
      }
    }

    if (!String(valeurs.designation || '').trim()) {
      erreurs.push({ nom: 'designation', message: 'La désignation est obligatoire (ex. Pompe centrifuge).' });
    }

    if (valeurs.localisation_id && !lignesLocalisations.some((l) => l.id === valeurs.localisation_id)) {
      erreurs.push({ nom: 'localisation_id', message: 'Cette localisation n\'existe pas.' });
    }

    if (valeurs.parent_id) {
      const parents = new Map(lignesEquipements.map((e) => [e.id, e]));
      if (idCourant && valeurs.parent_id === idCourant) {
        erreurs.push({ nom: 'parent_id', message: 'Un équipement ne peut pas être son propre parent.' });
      } else if (!parents.has(valeurs.parent_id)) {
        erreurs.push({ nom: 'parent_id', message: 'L\'équipement parent n\'existe pas.' });
      } else if (idCourant && remonteParentJusqua(valeurs.parent_id, idCourant, parents)) {
        erreurs.push({ nom: 'parent_id', message: 'Boucle interdite : « ' + libelleEquipement(valeurs.parent_id)
          + ' » est déjà un sous-équipement de celui-ci.' });
      }
    }

    const criticites = ['A', 'B', 'C'];
    if (valeurs.criticite && !criticites.includes(valeurs.criticite)) {
      erreurs.push({ nom: 'criticite', message: 'La criticité doit être A, B ou C.' });
    }
    if (valeurs.statut && !['en service', 'arrêt', 'rebut'].includes(valeurs.statut)) {
      erreurs.push({ nom: 'statut', message: 'Le statut doit être « en service », « arrêt » ou « rebut ».' });
    }
    if (valeurs.heures_fonct_jour) {
      const heures = UI.enNombre(valeurs.heures_fonct_jour);
      if (heures === null || heures < 0 || heures > 24) {
        erreurs.push({ nom: 'heures_fonct_jour', message: 'Saisissez un nombre d\'heures entre 0 et 24 (ex. 16).' });
      }
    }
    if (valeurs.valeur_remplacement) {
      const montant = UI.enNombre(valeurs.valeur_remplacement);
      if (montant === null || montant < 0) {
        erreurs.push({ nom: 'valeur_remplacement', message: 'Saisissez un montant en euros, positif ou nul (ex. 12 500).' });
      }
    }
    return erreurs;
  }

  // Vrai si `ancetre` figure parmi les parents (de parent en parent) de `depart`, lui compris.
  function remonteParentJusqua(depart, ancetre, lignesParId) {
    const dejaVus = new Set();
    let courant = lignesParId.get(depart);
    while (courant && !dejaVus.has(courant.id)) {
      if (courant.id === ancetre) return true;
      dejaVus.add(courant.id);
      courant = courant.parent_id ? lignesParId.get(courant.parent_id) : null;
    }
    return false;
  }

  /** Contrôle les valeurs d'une localisation. Renvoie [{ nom, message }]. */
  function verifierLocalisation(valeurs, lignesLocalisations, idCourant) {
    const erreurs = [];
    const libelle = String(valeurs.libelle || '').trim();
    if (!libelle) {
      erreurs.push({ nom: 'libelle', message: 'Le libellé est obligatoire (ex. Atelier Usinage).' });
    }
    if (!['site', 'atelier', 'ligne'].includes(valeurs.type)) {
      erreurs.push({ nom: 'type', message: 'Choisissez un type : site, atelier ou ligne.' });
    }
    if (valeurs.parent_id) {
      const parents = new Map(lignesLocalisations.map((l) => [l.id, l]));
      if (idCourant && valeurs.parent_id === idCourant) {
        erreurs.push({ nom: 'parent_id', message: 'Une localisation ne peut pas être sa propre parente.' });
      } else if (!parents.has(valeurs.parent_id)) {
        erreurs.push({ nom: 'parent_id', message: 'La localisation parente n\'existe pas.' });
      } else if (idCourant && remonteParentJusqua(valeurs.parent_id, idCourant, parents)) {
        erreurs.push({ nom: 'parent_id', message: 'Boucle interdite : la localisation parente est déjà située dans celle-ci.' });
      }
    }
    if (libelle) {
      const motif = UI.normaliserRecherche(libelle);
      const jumelle = lignesLocalisations.find((l) => l.id !== idCourant && (l.parent_id || '') === (valeurs.parent_id || '')
        && UI.normaliserRecherche(l.libelle) === motif);
      if (jumelle) {
        erreurs.push({ nom: 'libelle', message: 'Il existe déjà une localisation « ' + jumelle.libelle + ' » à cet endroit.' });
      }
    }
    return erreurs;
  }

  // --- Relevés de compteur (lot 2, ARCHITECTURE.md §14.6) -------------------------------------

  /**
   * Dernier relevé d'un compteur parmi `lignesReleves` (le cache, ou les lignes fraîches d'une
   * fonction de mutation) : la ligne du relevé, ou null. Même ordre que Preventif.dernierReleve :
   * la date, puis l'identifiant ; un relevé dont la valeur est illisible est ignoré.
   */
  function dernierReleveDe(lignesReleves, compteurId) {
    let dernier = null;
    lignesReleves.forEach((releve) => {
      if (releve.compteur_id !== compteurId || Donnees.nombre(releve.valeur) === null) return;
      const date = String(releve.date || '').slice(0, 10);
      const dateDernier = dernier ? String(dernier.date || '').slice(0, 10) : '';
      if (!dernier || date > dateDernier || (date === dateDernier && String(releve.id) > String(dernier.id))) {
        dernier = releve;
      }
    });
    return dernier;
  }

  /**
   * Contrôle un relevé saisi : { date: 'AAAA-MM-JJ', valeur: '1234.5' }. Renvoie [{ nom, message }].
   * La date est obligatoire et ne peut pas être après `aujourdhui` ; la valeur est un nombre.
   */
  function verifierReleve(valeurs, aujourdhui) {
    const erreurs = [];
    const date = String(valeurs.date || '').trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      erreurs.push({ nom: 'date', message: 'Indiquez la date du relevé.' });
    } else if (date > aujourdhui) {
      erreurs.push({ nom: 'date', message: 'La date du relevé ne peut pas être dans le futur.' });
    }
    if (String(valeurs.valeur || '').trim() === '') {
      erreurs.push({ nom: 'valeur', message: 'Indiquez la valeur lue sur le compteur.' });
    } else if (Donnees.nombre(valeurs.valeur) === null) {
      erreurs.push({ nom: 'valeur', message: 'Saisissez un nombre (ex. 1 250 ou 0,85).' });
    }
    return erreurs;
  }

  /** Vrai si la valeur saisie est plus basse que le dernier relevé (ligne de releves, ou null). */
  function estEnBaisse(valeur, dernier) {
    const nouvelle = Donnees.nombre(valeur);
    const precedente = dernier ? Donnees.nombre(dernier.valeur) : null;
    return nouvelle !== null && precedente !== null && nouvelle < precedente;
  }

  return {
    cheminLocalisation,
    libelleEquipement,
    verifierEquipement,
    verifierLocalisation,
    // (les écrans afficherListe, afficherFormulaire, afficherFiche : fichiers parc-*.js suivants)
    // Usage interne au module : outils prêtés aux fichiers parc-*.js, qui y ajoutent les leurs par
    // Object.assign(Parc.interne, …). Pas une API : son contenu peut changer à tout moment.
    interne: {
      estActif, comparerTextes, parRepere, identifiantsDescendants, remonteSurSoi, abreger,
      badgeCriticite, badgesEquipement, listeAdaptative,
      dernierReleveDe, verifierReleve, estEnBaisse,
    },
  };
})();
