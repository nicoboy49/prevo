'use strict';
// Langues de Prévo (chantier multilingue, D145 et D147 ; contrat du Lot 2) : une ligne de déclaration par langue —
// code, nom dans sa langue (affiché tel quel par le sélecteur, sans drapeau), locale Intl (dates, nombres, pluriels),
// statut (reference | complete | automatique). Toute langue déclarée fournit js/i18n/<code>.js et
// js/i18n/aide/<code>.js (vide s'il le faut) : js/i18n-chargeur.js charge les deux. L'ordre des lignes est celui du
// sélecteur de langue (UI.selecteurLangue). Anglais : britannique, en-GB (D151 ; Lot 3, T278).
I18n.declarer({ code: 'fr', nom: 'Français', locale: 'fr-FR', statut: 'reference' });
I18n.declarer({ code: 'en', nom: 'English', locale: 'en-GB', statut: 'complete' });
