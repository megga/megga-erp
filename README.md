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

L'installation de `megga_dental` tire tout le métier : socle Megga complet
+ CRM + agenda + contacts. Prochaines verticales prévues : `resto/`
(assemble `pos_restaurant` du cœur), `auto/` (assemble `repair` + `fleet`).

Chantiers ouverts côté dentaire : prise de RDV en ligne (`megga_rdv`, car
`appointment` est un module Enterprise), tarif SSO par points (le catalogue
officiel est sous licence SSO — chaque cabinet saisit ses actes), groupes
d'accès dédiés au dossier médical (LPD).

## Origine

Ce dépôt a été extrait du dépôt d'audit `megga/rdc` par `git subtree split`,
avec son historique complet (10 commits). Les documents d'analyse — audits CRM,
ERP, conformité suisse, stratégie de surcouche et plan de reprise — restent
dans `megga/rdc`.
