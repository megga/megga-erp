# megga_pain001 — export pain.001 (Swiss Payment Standards)

Chantier n°3 de la Phase 4 du [plan de reprise](../../../PLAN-REPRISE-ODOO.md).
Le miroir sortant de `megga_camt` : Odoo Community n'a aucune génération
pain.001 (`account_iso20022` est un module Enterprise absent du dépôt —
constat du volet 3 de l'audit).

## Architecture

- **`pain001.py`** — générateur pur (stdlib, aucune dépendance Odoo) du
  format `pain.001.001.09.ch.03` : en-tête de groupe avec somme de contrôle,
  un lot par fichier (`ReqdExctnDt/Dt` — enveloppe .09 vérifiée dans le XSD),
  et par virement la détection du type de référence — **QRR** (27 chiffres,
  checksum mod10r) exigée sur QR-IBAN et réciproquement, **RF/SCOR**
  (ISO 11649, mod 97), sinon communication libre `Ustrd`. Devises mixtes
  CHF/EUR admises dans un même fichier.
- **Assistant d'export** — depuis le menu Comptabilité ou l'action
  contextuelle de la liste des paiements. Contrôles : paiements sortants
  validés, même journal, compte bénéficiaire présent, **anti double envoi**
  (les paiements exportés portent le MsgId ; ré-export explicite possible).
  Le fichier est attaché au journal et téléchargé.

## Validé à la création (sans serveur Odoo)

Le générateur a été exécuté en session et son XML **validé contre le schéma
XSD officiel de SIX** (`pain.001.001.09.ch.03.xsd`, © SIX — utilisé comme
artefact de test, non redistribué dans ce dépôt) : 0 erreur de schéma sur un
ordre QRR + SCOR + Ustrd en CHF/EUR, sommes de contrôle exactes, et 5 cas
d'erreur métier refusés proprement. Les validateurs QRR/SCOR sont contrôlés
contre des valeurs de référence calculées indépendamment
(`RF18539007547034` valide, checksum décalé refusé).

## Vérification au premier boot

- [ ] `-i megga_pain001 --test-enable --test-tags /megga_pain001` → 5 tests verts
- [ ] Export d'un paiement réel et dépôt sur le **portail de test** de votre
      banque : accepté sans avertissement

## Limites assumées (v1)

- Un lot (`PmtInf`) par fichier : tous les paiements partagent la date
  d'exécution du wizard.
- Virements SEPA/étranger : émis avec IBAN + BIC si connus ; les paiements
  non-IBAN (chèque, SWIFT hors zone IBAN) sont hors périmètre.
- La réserve du volet 3 demeure : la conformité finale se valide sur le
  portail de test de la banque, pas dans un schéma.
