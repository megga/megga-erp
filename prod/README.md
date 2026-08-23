# Mise en production Megga — runbook

Stack durci : PostgreSQL 16 + Odoo en mode prefork + nginx TLS + sauvegarde
quotidienne vérifiée. Complète le [socle de développement](../README.md).

## Démarrage

```bash
git clone https://github.com/megga/megga-erp.git && cd megga-erp
git submodule update --init --depth 1 odoo
cd prod
cp .env.example .env && $EDITOR .env          # mots de passe longs et uniques
mkdir -p certs                                 # fullchain.pem + privkey.pem
docker compose -f docker-compose.prod.yml up -d --build
```

Puis initialisez la base selon la verticale déployée — section suivante.

## Initialiser une verticale (exemple : dentaire)

`scripts/init_dentaire.sh` crée une base de production **suisse, en
français, sans données de démonstration** (comportement vérifié
d'odoo-bin 19.0 : une base créée en CLI est sans démo par défaut) :

1. base + langue `fr_CH` ;
2. société **suisse d'abord** — c'est le pays de la société qui décide du
   plan comptable, donc `l10n_ch` s'applique de lui-même ensuite ;
3. pile dentaire (`megga_dental` + `megga_rdv`, le pont
   `megga_dental_rdv` s'auto-installe), mot de passe admin **exigé**
   (jamais admin/admin), puis vérification : modules installés, plan
   comptable `ch`, devise CHF.

Le script ne touche **jamais** une base existante.

```bash
# Dans le conteneur (scripts/ y est monté en /scripts) :
docker compose -f docker-compose.prod.yml exec \
  -e ADMIN_PASSWORD='...long et unique...' \
  -e ODOO_RC=/tmp/odoo.runtime.conf \
  erp bash /scripts/init_dentaire.sh "$ODOO_DB_NAME"
# Hors docker (recette) : surcharges ODOO_BIN et CHEMINS acceptées.
```

Dépendance système vécue le 23/08/2026 : `account_peppol`
(auto-installé par la chaîne comptable 19.0) exige la bibliothèque
Python **`phonenumbers`** — `pip install phonenumbers` sur l'hôte ou
dans l'image, sinon l'étape 3 échoue proprement.

Les autres verticales s'initialisent pareil en surchargeant
`MODULES` et `CHEMINS` (resto : `megga_resto,megga_rdv` et le chemin
`addons/verticals/resto` ; garage : `megga_auto,megga_rdv` et
`addons/verticals/auto`).

Certificats : en production, Let's Encrypt (`certbot certonly --standalone`,
puis copier `fullchain.pem` et `privkey.pem` dans `certs/`). Un certificat
auto-signé suffit pour une recette locale.

## Ce que le durcissement apporte

| Mesure | Effet |
|---|---|
| `list_db = False` | Aucune énumération des bases, gestionnaire neutralisé |
| Blocage nginx `/web/database/*` | **Vérifié : HTTP 404** — double verrou même si `list_db` était réactivé |
| `db` et `erp` en `expose` (jamais `ports`) | PostgreSQL et Odoo injoignables depuis l'extérieur ; nginx est la seule porte |
| Secrets par `.env` + entrypoint | Aucun mot de passe dans un fichier versionné ; le compose **refuse de démarrer** si un secret manque |
| `workers = 5` (prefork) | Multi-utilisateur réel ; les limites mémoire/CPU recyclent un worker qui dérape |
| `/opt/odoo` en `:ro` | La règle du plan tient jusqu'en production |
| HSTS, TLS 1.2+, `nosniff`, `SAMEORIGIN` | En-têtes de sécurité de base |

## Sauvegardes

Automatique chaque nuit à 02h15 (service `backup`), rétention 30 jours.
Chaque sauvegarde contient `database.dump` (format custom), `filestore.tar.gz`,
`SHA256SUMS` et l'inventaire des tables — et est **vérifiée à l'écriture**
(`pg_restore --list` + seuil de 100 tables minimum).

```bash
# Sauvegarde manuelle avant une opération risquée
docker compose -f docker-compose.prod.yml exec backup /scripts/backup.sh

# Lister
docker compose -f docker-compose.prod.yml exec backup ls -la /backups

# Restaurer (refuse d'écraser sans --force)
docker compose -f docker-compose.prod.yml stop erp
docker compose -f docker-compose.prod.yml exec backup \
  /scripts/restore.sh /backups/megga-AAAAMMJJ-HHMMSS megga --force
docker compose -f docker-compose.prod.yml start erp
```

⚠️ **Sortez les sauvegardes de la machine.** Le volume `backups` vit sur le
même hôte que la base : un incident matériel emporte les deux. Synchronisez
`backups` vers un stockage externe (rsync, S3, NAS) — c'est la seule pièce
que ce stack ne fournit pas.

### Cycle validé en réel (23/08/2026)

Sauvegarde puis restauration complète de la base de test dans une base neuve :
**377 tables identiques**, 5 modules Megga installés, colonnes personnalisées
(`megga_import_ref`, `megga_pain_msg_id`) présentes, filestore restauré,
empreintes conformes. Garde-fous testés : refus d'écraser une base existante
sans `--force`, détection d'une archive corrompue (octets altérés → refus),
refus d'un dump tronqué.

## Exploitation courante

```bash
docker compose -f docker-compose.prod.yml logs -f erp        # journaux
docker compose -f docker-compose.prod.yml restart erp        # redémarrage
docker compose -f docker-compose.prod.yml exec db psql -U odoo -d megga
```

Mise à jour d'un module Megga : `git pull`, puis
`docker compose -f docker-compose.prod.yml exec erp python3 /opt/odoo/odoo-bin
-c /tmp/odoo.runtime.conf -d megga -u megga_camt --stop-after-init`,
**après une sauvegarde manuelle**.

## Avant le premier client réel

- [ ] `.env` avec des mots de passe longs et uniques (pas ceux de l'exemple)
- [ ] Certificat TLS valide (Let's Encrypt) et renouvellement automatique
- [ ] Sauvegardes répliquées **hors de la machine**
- [ ] Une restauration réellement testée sur cette installation
- [ ] `ODOO_WORKERS` ajusté : (2 × cœurs) + 1
- [ ] Spécimens QR-facture et pain.001 validés sur le portail de test bancaire
- [ ] Décompte TVA rapproché avec la fiduciaire
