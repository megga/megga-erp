# Socle ERP — Odoo Community 19.0 en surcouche

Phase 1 du [plan de reprise](../PLAN-REPRISE-ODOO.md). Le cœur d'Odoo est un
**sous-module figé, jamais modifié** ; tout le produit vit dans `addons/`.

## Épinglage

- Sous-module : `odoo/` → **`megga/odoo`** (notre fork de `odoo/odoo`), branche `19.0`
- SHA figé : celui du gitlink — `git ls-tree HEAD odoo` fait foi. Il n'avance
  que par le rituel mensuel (`rituel-mensuel.yml`), jamais à la main.

## Démarrer (sur votre machine)

```bash
git clone https://github.com/megga/megga-erp.git && cd megga-erp
git submodule update --init --depth 1 odoo   # ~qq minutes, plusieurs centaines de Mo
docker compose up --build
# puis http://localhost:8069 → créer la base (le master password est dans odoo.conf)
```

## Checklist « Phase 1 terminée »

- [ ] `docker compose up` démarre sans erreur
- [ ] http://localhost:8069 affiche l'écran de création de base
- [ ] Après création : les ~705 modules apparaissent dans Apps
- [ ] CRM + Ventes + Facturation s'installent
- [ ] `python scripts/check_licences.py` → OK
- [ ] `bash scripts/check_core_pristine.sh` → OK

## Les règles du socle (non négociables)

1. **`odoo/` est en lecture seule** — monté `:ro` dans Docker, vérifié par
   `check_core_pristine.sh` en CI. Tout besoin passe par un module `_inherit`
   dans `addons/`.
2. **`addons-oca/` n'accepte que du LGPL-3** — `check_licences.py` refuse
   l'AGPL (2 640 des modules OCA) et toute licence inconnue. Lire le
   `__manifest__.py` AVANT de copier un module.
3. **Jamais `git add -A` à la racine quand `odoo/` n'est pas matérialisé** —
   cela stagerait la suppression du gitlink. Ajouter les chemins explicitement.
4. Refactoring : uniquement `addons/` et `scripts/` (voir `/refactor`).

## Maintenance (Phase 5 du plan)

- **Mensuel** : synchroniser le fork puis le sous-module. Sur GitHub,
  `megga/odoo` ▸ « Sync fork » (ou `git -C odoo fetch upstream 19.0 &&
  git -C odoo push origin FETCH_HEAD:19.0` avec
  `upstream = https://github.com/odoo/odoo.git`), puis
  `git -C odoo fetch origin 19.0 && git -C odoo merge origin/19.0`
  → tests → commit du bump. **Le fork n'avale pas les correctifs amont tout
  seul : sans cette synchronisation, vous ne recevez plus les correctifs de
  sécurité.**
- **Annuel** : migration majeure (rebrancher le sous-module, migrer nos modules).

## Nom du produit : Megga

Décidé le 23/08/2026. Préfixe de tous les modules : `megga_`.

## Modules livrés (Phases 2 et 4 — complètes)

| Module | Rôle | Tests au boot |
|---|---|---|
| [`megga_base`](addons/megga_base/) | Surcouche de marque (titre, favicon, couleur, e-mails, menu) | checklist visuelle |
| [`megga_qr_export`](addons/megga_qr_export/) | QR-facture pour clients hors CH/LI (norme SIX) | 3 |
| [`megga_camt`](addons/megga_camt/) | Import camt.053/054 — encaissements QRR, rapprochement | 5 |
| [`megga_pain001`](addons/megga_pain001/) | Paiements fournisseurs pain.001.001.09.ch.03 | 5 |
| [`megga_tva_ch`](addons/megga_tva_ch/) | Décompte TVA AFC (rendu du rapport l10n_ch) | 4 |

Validation groupée (socle + verticales) : `bash scripts/run_tests.sh`.

La paie reste hors périmètre code (voie connecteur/fiduciaire — volet 3 de
l'audit) ; la Phase 5 (bump mensuel du sous-module, migration annuelle) est
le régime permanent.

## Verticales métier (`addons/verticals/`)

Un cœur, un socle suisse, N secteurs. Chaque verticale est un répertoire
d'addons **supplémentaire** : un déploiement client assemble
`odoo/addons` + `addons` + `addons/verticals/<secteur>`, et le rituel
mensuel teste toutes les verticales contre chaque bump du cœur.

| Verticale | Méta-module | Contenu | Tests |
|---|---|---|---|
| [`dental/`](addons/verticals/dental/) | `megga_dental` | Dossier patient (délégué `res.partner`, donc facturable → QR), plans de traitement par dent (référentiel FDI/ISO 3950 complet), rappels de contrôle automatiques (cron + activités), facturation en un clic | 19 |
| [`resto/`](addons/verticals/resto/) | `megga_resto` | Carnet de réservations sur les tables du plan de salle (`restaurant.table` de `pos_restaurant`) : conflits de créneaux détectés, non-venus marqués par cron ; fiches techniques par plat (coût matière, marge, report du coût sur l'article) | 23 |
| [`auto/`](addons/verticals/auto/) | `megga_auto` | Parc des véhicules **clients** sur `fleet` (marques, modèles, plaques, journal de compteur) : propriétaire, rappels d'expertise au rythme fédéral 4-3-2 (art. 33 OETV), plausibilité VIN (ISO 3779) ; ordres de réparation atelier avec report du kilométrage et facture en un clic | 17 |

Chaque méta-module tire tout son métier : socle Megga complet + les briques
du cœur (dentaire : CRM + agenda + contacts ; resto : POS restaurant +
contacts ; auto : fleet + CRM + contacts). Note d'architecture : le module
`repair` du cœur n'est PAS utilisé par `auto/` — il répare un produit tenu
en stock (product_id + lot), pas le véhicule d'un client ; l'atelier est
donc un modèle métier propre, adossé à fleet.

Chantiers ouverts côté dentaire : prise de RDV en ligne (`megga_rdv`, car
`appointment` est un module Enterprise), tarif SSO par points (le catalogue
officiel est sous licence SSO — chaque cabinet saisit ses actes), groupes
d'accès dédiés au dossier médical (LPD).

Chantiers ouverts côté resto : conversion d'unités dans les fiches
techniques (quantités saisies dans l'unité de l'ingrédient pour l'instant),
réservation en ligne (l'équivalent cœur, `pos_restaurant_appointment`, est
Enterprise), TVA à l'emporter 2.6 % vs sur place 8.1 % (configuration
fiscale POS à documenter par établissement).

Chantiers ouverts côté auto : véhicules d'occasion en stock (reprises,
marge bénéficiaire TVA art. 24a LTVA), carnet d'entretien imprimable,
rendez-vous atelier en ligne (même chantier `megga_rdv` que le dentaire) ;
le rythme d'expertise est le rythme fédéral — les convocations cantonales
(OCN, SAN…) peuvent s'en écarter.

## Origine

Ce dépôt a été extrait du dépôt d'audit `megga/rdc` par `git subtree split`,
avec son historique complet (10 commits). Les documents d'analyse — audits CRM,
ERP, conformité suisse, stratégie de surcouche et plan de reprise — restent
dans `megga/rdc`.
