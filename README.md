# Socle ERP — Odoo Community 19.0 en surcouche

Phase 1 du [plan de reprise](../PLAN-REPRISE-ODOO.md). Le cœur d'Odoo est un
**sous-module figé, jamais modifié** ; tout le produit vit dans `addons/`.

## Épinglage

- Sous-module : `erp/odoo` → `odoo/odoo`, branche `19.0`
- SHA figé : `9188766f5bab9cc7fe25e6812f9e795e5a2c212f` (relevé le 23/08/2026)

## Démarrer (sur votre machine)

```bash
git clone <ce-depot> && cd <ce-depot>
git submodule update --init --depth 1 erp/odoo   # ~qq minutes, plusieurs centaines de Mo
cd erp
docker compose up --build
# puis http://localhost:8069 → créer la base (le master password est dans odoo.conf)
```

## Checklist « Phase 1 terminée »

- [ ] `docker compose up` démarre sans erreur
- [ ] http://localhost:8069 affiche l'écran de création de base
- [ ] Après création : les ~705 modules apparaissent dans Apps
- [ ] CRM + Ventes + Facturation s'installent
- [ ] `python erp/scripts/check_licences.py` → OK
- [ ] `bash erp/scripts/check_core_pristine.sh` → OK

## Les règles du socle (non négociables)

1. **`odoo/` est en lecture seule** — monté `:ro` dans Docker, vérifié par
   `check_core_pristine.sh` en CI. Tout besoin passe par un module `_inherit`
   dans `addons/`.
2. **`addons-oca/` n'accepte que du LGPL-3** — `check_licences.py` refuse
   l'AGPL (2 640 des modules OCA) et toute licence inconnue. Lire le
   `__manifest__.py` AVANT de copier un module.
3. **Jamais `git add -A` à la racine quand `erp/odoo` n'est pas matérialisé** —
   cela stagerait la suppression du gitlink. Ajouter les chemins explicitement.
4. Refactoring : uniquement `addons/` et `scripts/` (voir `/refactor`).

## Maintenance (Phase 5 du plan)

- **Mensuel** : `git -C erp/odoo fetch origin 19.0 && git -C erp/odoo merge origin/19.0`
  → tests → commit du bump. Les correctifs de sécurité arrivent par ce canal.
- **Annuel** : migration majeure (rebrancher le sous-module, migrer nos modules).

## À décider avant la Phase 2

**Le nom du produit.** Il deviendra le préfixe de tous les modules
(`<nom>_base`, `<nom>_camt`, …) — c'est la seule décision coûteuse à changer
après coup. Rien dans la Phase 1 ne le fige. Pas de « odoo » dans le nom :
la marque n'est pas cédée.

## Extraction future vers un dépôt dédié

Le socle vit dans `erp/` du dépôt d'audit. Pour l'extraire proprement :
`git filter-repo --subdirectory-filter erp` sur un clone frais (le workflow CI
`.github/workflows/socle.yml` et `.gitmodules` sont à reporter à la racine).
