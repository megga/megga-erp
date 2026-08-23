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
| [`dental/`](addons/verticals/dental/) | `megga_dental` | Dossier patient (délégué `res.partner`, donc facturable → QR), plans de traitement par dent (référentiel FDI/ISO 3950 complet), rappels de contrôle automatiques (cron + activités), tarif par points (positions, valeur du point du cabinet ou de la convention AA/AI/AM), facturation en un clic, groupes LPD Réception/Soins (champs médicaux protégés par l'ORM) | 35 |
| [`resto/`](addons/verticals/resto/) | `megga_resto` | Carnet de réservations sur les tables du plan de salle (`restaurant.table` de `pos_restaurant`) : conflits de créneaux détectés, non-venus marqués par cron ; fiches techniques par plat (coût matière, marge, report du coût sur l'article) avec conversion d'unités (200 g d'un article au kilo, unité maison type cl) | 30 |
| [`auto/`](addons/verticals/auto/) | `megga_auto` | Parc des véhicules **clients** sur `fleet` (marques, modèles, plaques, journal de compteur) : propriétaire, rappels d'expertise au rythme fédéral 4-3-2 (art. 33 OETV), plausibilité VIN (ISO 3779) ; ordres de réparation atelier avec report du kilométrage et facture en un clic | 17 |
| [`dental/`](addons/verticals/dental/) | `megga_dental_rdv` (**auto_install**) | Pont réservation ↔ dossier : toute réservation en ligne rattache — ou crée — le dossier patient du contact (archivés compris, jamais de doublon), débrayable par type de RDV ; effet système en sudo, lien `patient_id` gardé par les groupes LPD | 9 |
| [`auto/`](addons/verticals/auto/) | `megga_auto_rdv` (**auto_install**) | Pont réservation ↔ atelier : le véhicule du client est rattaché d'office quand il n'en a qu'un, et l'ordre de réparation se crée en un clic depuis la réservation (date locale du fuseau, mécanicien = intervenant, compteur) | 8 |
| [`resto/`](addons/verticals/resto/) | `megga_resto_rdv` (**auto_install**) | Pont réservation en ligne ↔ carnet : le type « réservation de table » demande les couverts, n'occupe pas l'agenda (`show_as='free'` — plusieurs tablées par créneau) et attribue la plus petite table suffisante ; complet = refus propre ; annulations synchronisées dans les deux sens | 11 |

Chaque méta-module tire tout son métier : socle Megga complet + les briques
du cœur (dentaire : CRM + agenda + contacts ; resto : POS restaurant +
contacts ; auto : fleet + CRM + contacts). Note d'architecture : le module
`repair` du cœur n'est PAS utilisé par `auto/` — il répare un produit tenu
en stock (product_id + lot), pas le véhicule d'un client ; l'atelier est
donc un modèle métier propre, adossé à fleet.

Côté dentaire, la prise de RDV en ligne (`megga_rdv`) et les **groupes
LPD** sont livrés : deux rôles — *Réception* (identité, coordonnées,
rendez-vous, facturation) et *Soins* (dossier médical complet, implique
Réception) — avec les champs sensibles (allergies, antécédents,
médication, notes cliniques) protégés par `groups=` **sur les champs
eux-mêmes** (appliqué par l'ORM, pas seulement par les vues) ; sans
groupe dentaire, aucun accès aux dossiers, mais l'automatisation de la
réservation en ligne continue de créer les dossiers (effet système en
sudo, lecture toujours gardée).

Le **tarif par points** est livré aussi : positions tarifaires (numéro,
libellé, points), montant d'un acte = points × valeur du point — valeur
du cabinet en privé (fiche Société), valeur de la convention aux
assurances sociales (AA/AI/AM, point à 1.00), figée sur chaque devis. Le
numéro de position figure sur la facture. Le catalogue officiel étant
une œuvre **sous licence SSO**, il n'est pas embarqué : chaque cabinet
au bénéfice d'une licence importe ses positions (CSV : `code`, `name`,
`points`, `chapter` — exemple fictif dans `megga_dental/docs/`) ou les
saisit à la main ; les lignes à produit (forfaits, fournitures) restent
possibles et se mélangent librement.

Côté resto, les fiches techniques convertissent les unités : chaque
ligne se saisit dans SON unité (200 g d'un article acheté au kilo, 5 cl
d'une huile au litre — les unités maison comme le centilitre se créent
en un clic, relatives au litre), le coût est converti par l'arbre
d'unités du cœur, et seules les unités convertibles (même racine — en
19 les catégories d'unités ont disparu) sont proposées. Chantiers
ouverts : TVA à l'emporter 2.6 % vs sur place 8.1 % (configuration
fiscale POS à documenter par établissement).

Chantiers ouverts côté auto : véhicules d'occasion en stock (reprises,
marge bénéficiaire TVA art. 24a LTVA), carnet d'entretien imprimable ;
le rythme d'expertise est le rythme fédéral — les convocations cantonales
(OCN, SAN…) peuvent s'en écarter.

## Rendez-vous en ligne (`addons/megga_rdv`)

Le chantier commun aux verticales : l'équivalent Community du module
Enterprise `appointment`. Types de rendez-vous (durée, plages
hebdomadaires, intervenants, fuseau, préavis, horizon), page publique
`/rdv` rendue côté serveur qui ne montre que des créneaux réellement
libres — l'agenda `calendar.event` du cœur fait foi, dans les deux sens :
un événement occupe le créneau, une réservation devient un événement chez
l'intervenant le moins chargé du jour. Confirmation par e-mail avec lien
d'annulation à jeton (l'annulation supprime l'événement et libère le
créneau). Rappel de la veille : un cron quotidien idempotent rappelle
par e-mail chaque réservation confirmée qui démarre dans les 24 heures
(lien d'annulation compris, débrayable par type). 24 tests, dont la
réservation de bout en bout par HTTP (CSRF compris). Indépendant des
verticales : il ne dépend que de `calendar`.

## Origine

Ce dépôt a été extrait du dépôt d'audit `megga/rdc` par `git subtree split`,
avec son historique complet (10 commits). Les documents d'analyse — audits CRM,
ERP, conformité suisse, stratégie de surcouche et plan de reprise — restent
dans `megga/rdc`.
