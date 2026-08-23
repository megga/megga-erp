# megga_qr_export — QR-facture pour clients à l'étranger

Chantier n°1 de la Phase 4 du [plan de reprise](../../../PLAN-REPRISE-ODOO.md).

## Le problème (audit suisse, volet 3)

Odoo Community refuse d'imprimer la QR-facture dès que le client est domicilié
hors CH/LI. Vérifié au SHA épinglé (`9188766f`), `l10n_ch/models/res_bank.py` :

```python
def _l10n_ch_qr_debtor_check(self, debtor_partner):
    if not debtor_partner or debtor_partner.country_id.code not in ('CH', 'LI'):
        return _("The debtor partner's address isn't located in Switzerland.")
    return False
```

Or la norme SIX (Swiss Implementation Guidelines QR-bill) n'impose CH/LI
qu'au compte du **créancier** — le débiteur peut être à l'étranger. Odoo est
plus restrictif que la norme (comportement confirmé par son propre test
`test_l10n_ch_qr_print.py` et par le correctif opw-6222417 de juin 2026,
qui rétablit la référence de paiement mais pas l'impression du bulletin).

## La surcharge — et ce qu'elle ne touche pas

Un seul point d'entrée surchargé. Sont **conservés** : le comportement amont
sans partenaire, l'exigence d'un pays sur l'adresse (il alimente le champ
« Ultimate Debtor Country » de la charge utile SPC), et le contrôle de
complétude d'adresse fait en amont par `_check_for_qr_code_errors`
(rue, NPA, localité, pays — vérifié verbatim dans le source).

## Compatibilité avec la suite de tests amont — prouvée avant écriture

Le test amont exige `l10n_ch_is_qr_valid == False` pour `partner_a`. Vérifié
dans `account/tests/common.py` au SHA épinglé : `partner_a` est créé **sans**
pays, rue, NPA ni localité. Notre garde « pays manquant » maintient donc ce
test au vert, module installé.

## Vérification au premier boot

- [ ] `-i megga_qr_export --test-enable --test-tags /megga_qr_export` → 3 tests verts
- [ ] Les tests amont `-test-tags /l10n_ch` restent verts
- [ ] Facture réelle client FR : bulletin QR présent, croix suisse, adresse FR

## ⚠️ Réserve inchangée du volet 3

Ce module atteste une logique, pas une conformité certifiée : **validez un
spécimen sur le portail de test de votre banque** (positionnement, récépissé,
ligne de perforation) avant mise en production.
