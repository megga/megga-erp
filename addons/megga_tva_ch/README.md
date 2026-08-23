# megga_tva_ch — décompte TVA suisse (formulaire AFC)

Chantier n°4 — le dernier — de la Phase 4 du
[plan de reprise](../../../PLAN-REPRISE-ODOO.md).

## Le constat qui dicte l'architecture

`l10n_ch` Community livre **déjà** la définition complète du décompte :
`data/account_tax_report_data.xml` contient toutes les rubriques AFC
(200–299, 302a/b–399, 400–479, 500/510, 900/910) avec leurs formules.
Ce qui manque en Community est le **moteur de rendu** (`account_reports`,
Enterprise). Ce module ne redéfinit donc aucun mapping fiscal — il évalue
le rapport officiel :

- **`tax_tags`** — sémantique 19.0 vérifiée verbatim dans
  `account_account_tag.py` au SHA épinglé : un tag nommé
  `formula.lstrip('-')`, négation si la formule commence par « - »
  (`balance_negate` = `STARTS_WITH(formula, '-')`). Somme des `balance`
  des écritures **validées** de la période, par société.
- **`aggregation`** — mini-évaluateur (`afc.py`, pur, testé hors Odoo sur
  les formules réelles de l10n_ch) ; `if_above(CHF(0))` plafonne 500/510
  à zéro. **Toute formule non reconnue fait échouer le calcul** plutôt que
  de publier un chiffre faux.

Sortie : PDF QWeb (Comptabilité ▸ Décompte TVA (AFC)) — de quoi remplir le
formulaire en ligne sans ressaisie. `auto_install` sur `l10n_ch`.

## Vérification au premier boot

- [ ] `-i megga_tva_ch --test-enable --test-tags /megga_tva_ch` → 4 tests verts
      (facture + fournisseur, plancher 500/510, filtre de période, avoir)
- [ ] Rapprocher le PDF d'un décompte déjà déposé sur une période passée

## Limites assumées (v1)

- Méthode effective (contre-prestations convenues). Les taux de la dette
  fiscale nette (TDFN) ne sont pas gérés.
- Pas de télétransmission eCH-0217 : le PDF sert à remplir le portail AFC.
- Les chiffres reflètent le paramétrage des taxes de `l10n_ch` : ce module
  restitue, il ne corrige pas un mauvais paramétrage.
- **Le décompte officiel reste à valider avec votre fiduciaire.**
