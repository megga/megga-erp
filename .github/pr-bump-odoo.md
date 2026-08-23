Rituel mensuel (Phase 5 du plan de reprise).

### Vérifié automatiquement

- Fork `megga/odoo` synchronisé depuis `odoo/odoo` (branche 19.0), et le
  nouveau SHA **vérifié présent dans le fork** avant tout déplacement du
  gitlink — sans quoi le dépôt serait incassable pour quiconque le clone.
- Garde-fou licences : aucun module AGPL dans `addons-oca`.
- Garde-fou anti-fork : le nouveau SHA appartient bien à l'historique amont.
- **Les 17 tests Megga passent contre ce nouveau cœur.**

### À votre charge avant de fusionner

Cette pull request est ouverte par le `GITHUB_TOKEN` par défaut : GitHub ne
déclenche alors **pas** les autres workflows dessus, donc `socle` n'apparaîtra
pas dans les vérifications. Les mêmes garde-fous ont tourné dans le job qui a
produit cette PR — son journal en fait foi.

Relisez les notes de version amont, en particulier si un module de `addons/`
surcharge du code touché par la montée. Les surcharges les plus sensibles :
`megga_base` (xpath sur les gabarits web et e-mail) et `megga_qr_export`
(signature de `_l10n_ch_qr_debtor_check`).
