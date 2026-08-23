# megga_camt — import camt.053 / camt.054

Chantier n°2 de la Phase 4 du [plan de reprise](../../../PLAN-REPRISE-ODOO.md).
Comble le trou n°1 d'Odoo Community constaté au volet 3 de l'audit : aucun
import de relevés ISO 20022 dans le dépôt (`camt` = 0 sur 4 formulations),
la fonction étant réservée à l'édition Enterprise.

## Architecture

- **`camt_parser.py`** — bibliothèque pure (stdlib uniquement, aucune
  dépendance Odoo), lecture par nom local donc indépendante de la version de
  schéma (`.001.02/.04/.08`, variantes suisses `.ch.02`). Gère camt.053
  (relevés, soldes OPBD/CLBD), camt.054 (avis de crédit en lot — le
  successeur du fichier ESR/V11) et camt.052. Les lots d'encaissements QR
  sont éclatés en une transaction par `TxDtls`, la **référence QRR/SCOR**
  (`RmtInf/Strd/CdtrRefInf/Ref`) est extraite pour le rapprochement.
- **Assistant d'import** (Comptabilité ▸ Accounting ▸ Import camt) —
  multi-fichiers, avec trois garde-fous : devise du journal, IBAN du compte,
  et déduplication à deux niveaux (relevé par nom, transaction par
  `megga_import_ref` — un camt.054 déjà couvert par le camt.053 du soir ne
  crée pas de doublons).

## Validé à la création (sans serveur Odoo)

Le parseur a été exécuté en session sur les deux fixtures suisses :
cohérence des soldes (1000 + 650 = 1650), éclatement des lots, styles de
parties `.04` (`Dbtr/Nm`) et `.08` (`Dbtr/Pty/Nm`), références QRR à
checksum mod10r vérifié indépendamment, refus propre d'un pain.001.

## Vérification au premier boot

- [ ] `-i megga_camt --test-enable --test-tags /megga_camt` → 5 tests verts
- [ ] Import d'un vrai camt.053 de votre banque : soldes et lignes corrects
- [ ] Rapprochement : la référence QRR de la ligne matche la facture

## Limites assumées (v1)

- Fichier dans la devise du journal uniquement (multi-devise refusé avec un
  message clair — importez dans un journal de la bonne devise).
- camt.054 crée un relevé sans soldes (l'avis n'en porte pas).
- Le rapprochement lui-même reste celui d'Odoo (matching sur la référence) ;
  un auto-lettrage QRR dédié pourra devenir un chantier ultérieur.
