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

## Vrai serveur en un passage (`deployer.sh`)

Sur un VPS neuf (Debian 12 / Ubuntu 24.04, 4 Go+, root), avec un
enregistrement DNS `A` pointant sur la machine :

```bash
DOMAINE=erp.moncabinet.ch COURRIEL=admin@moncabinet.ch VERTICALE=dental \
  bash prod/scripts/deployer.sh
```

Le script : installe Docker et les outils, clone le dépôt et matérialise
le sous-module, génère `.env` (jamais écrasé s'il existe), obtient le
certificat Let's Encrypt (défi standalone + hook de renouvellement qui
recharge nginx ; sans `DOMAINE` : auto-signé, pour un essai seulement),
lance le stack, **vérifie la posture** (le gestionnaire de bases doit
répondre 404 à travers nginx avant d'aller plus loin), puis initialise
la verticale (`VERTICALE=dental|resto|auto`) avec un mot de passe admin
généré, affiché une seule fois. La garde d'`init_prod.sh` reste : une
base existante n'est jamais touchée. Prérequis PDF : `wkhtmltopdf` est
dans l'image (carnet d'entretien, rapports).

Après le passage : checklist de premier jour (société, IBAN QR,
utilisateurs et rôles, catalogue métier), timer des sauvegardes déjà
actif dans le stack, et **expédition hors de l'hôte** à brancher
(section Sauvegardes).

## Cloudflare — devant et derrière (pas comme hébergeur)

Cloudflare ne peut pas héberger Odoo (Workers exécute du
JavaScript/WASM sans processus long, D1 est du SQLite — il faut un
Python durable et PostgreSQL). Ses deux vrais rôles ici :

**Devant le serveur.** Deux options :
- *Proxy orange* : la zone DNS chez Cloudflare, l'enregistrement
  proxifié, mode TLS **Full (strict)** — le certificat Let's Encrypt du
  serveur reste en place, Cloudflare ajoute WAF, cache et masquage
  d'IP.
- *Cloudflare Tunnel* (`cloudflared`) : **aucun port entrant ouvert**
  sur le serveur — le tunnel sort du serveur vers Cloudflare et amène
  le trafic à nginx. Firewall fermé à tout sauf SSH. Recommandé pour un
  cabinet : `cloudflared tunnel create megga`, route DNS, service
  systemd — la documentation Cloudflare Zero Trust fait foi.

**Derrière le serveur : R2 comme destination d'expédition.** Le bucket
`megga-sauvegardes` existe (créé le 23/08/2026). R2 étant S3-compatible,
c'est la variante rclone d'`expedier.sh` : créer un jeton d'accès R2
(tableau de bord R2 ▸ Manage API tokens), configurer un remote rclone
de type s3 (provider Cloudflare), et — **obligatoire pour des données de
santé** (nLPD, et bucket hors juridiction suisse/UE) — l'envelopper d'un
remote `crypt` (chiffrement côté client, clés gardées hors du cloud) :

```bash
rclone copy --checksum "$ARCHIVE" crypt-r2:megga-sauvegardes/$(basename "$ARCHIVE")
rclone check "$ARCHIVE" crypt-r2:megga-sauvegardes/$(basename "$ARCHIVE")
```

Sans chiffrement client, n'expédiez vers R2 que les bases sans données
sensibles — ou créez le bucket en juridiction UE et documentez-le au
registre des traitements.

## Initialiser une verticale

Un moteur unique, `scripts/init_prod.sh <dental|resto|auto> [base]`, et
trois enrobages :

| Verticale | Commande | Base par défaut | Pile installée |
|---|---|---|---|
| Dentaire | `scripts/init_dentaire.sh` | `megga_prod` | `megga_dental` + `megga_rdv` (+ pont) |
| Restaurant | `scripts/init_resto.sh` | `megga_resto_prod` | `megga_resto` + `megga_rdv` (+ pont) |
| Garage | `scripts/init_garage.sh` | `megga_auto_prod` | `megga_auto` + `megga_rdv` (+ pont) |

Le moteur crée une base de production **suisse, en français, sans
données de démonstration** (comportement vérifié d'odoo-bin 19.0 : une
base créée en CLI est sans démo par défaut) :

1. base + langue `fr_CH` ;
2. société **suisse d'abord** — c'est le pays de la société qui décide du
   plan comptable, donc `l10n_ch` s'applique de lui-même ensuite ;
3. pile de la verticale (`megga_<verticale>` + `megga_rdv`, le pont
   `megga_<verticale>_rdv` s'auto-installe), mot de passe admin **exigé**
   (jamais admin/admin), puis vérification : modules attendus installés,
   plan comptable `ch`, devise CHF.

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

Cycle exécuté et vérifié en réel le 23/08/2026 pour les TROIS
verticales : init complète, plan comptable `ch`, devise CHF, langue
fr_CH, posture `list_db` contrôlée, sauvegarde vérifiée à l'écriture.
`MODULES` et `CHEMINS` restent surchargables pour les assemblages
sur mesure.

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
même hôte que la base : un incident matériel emporte les deux.

### Expédition hors de l'hôte (`expedier.sh`)

`prod/scripts/expedier.sh` pousse les archives **déjà vérifiées** vers une
destination distante, avec la même doctrine que le reste du runbook :

1. une archive dont `SHA256SUMS` ne se vérifie plus **ne s'expédie pas**
   (on n'exporte pas une corruption) ;
2. après la copie, une passe `rsync --checksum` à blanc doit ne rien
   trouver à transférer — la copie distante est identique au bit près,
   sinon échec ;
3. le marqueur `EXPEDIEE` (journal destination + date) n'est posé
   qu'après cette contre-vérification.

```bash
# NAS ou autre machine, par SSH (clé déposée, rsync des deux côtés)
EXPEDITION_DEST=nas:/volume1/megga-sauvegardes /scripts/expedier.sh

# Point de montage (NFS, disque externe)
EXPEDITION_DEST=/mnt/sauvegardes /scripts/expedier.sh

# Tout l'historique plutôt que la dernière archive de chaque base
EXPEDITION_ALL=1 EXPEDITION_DEST=... /scripts/expedier.sh
```

Enchaînez-le au timer nocturne : `backup.sh && expedier.sh`. Variante
stockage objet (S3 et compatibles) : remplacer l'appel rsync par
`rclone copy --checksum "$d" remote:megga-sauvegardes/$(basename "$d")`
puis `rclone check` — mêmes garde-fous, autre transport.

Cycle validé en réel (23/08/2026) : trois archives de production
expédiées puis re-vérifiées côté destination (`sha256sum -c` sur place),
deuxième passage idempotent, archive volontairement corrompue **refusée
avant tout envoi**, absence de rsync détectée proprement. Le transport
SSH/NAS reste à brancher sur votre infrastructure — la logique, elle,
est éprouvée.

### Cycle validé en réel (23/08/2026)

Sauvegarde puis restauration complète de la base de test dans une base neuve :
**377 tables identiques**, 5 modules Megga installés, colonnes personnalisées
(`megga_import_ref`, `megga_pain_msg_id`) présentes, filestore restauré,
empreintes conformes. Garde-fous testés : refus d'écraser une base existante
sans `--force`, détection d'une archive corrompue (octets altérés → refus),
refus d'un dump tronqué.

### Exercice de restauration sur la PRODUCTION dentaire (23/08/2026)

Restauration de la sauvegarde de `megga_prod` vers une base d'essai,
de bout en bout : empreintes SHA256 conformes, **450 tables**, filestore
restauré ; égalité origine/copie contrôlée sur cinq comptages (tables,
685 modules, contacts, 1 082 vues, 28 crons) ; **neutralisation des
actions sortantes appliquée à la copie** (28 crons désactivés, doctrine
du script) puis **boot réel de la copie** : registre chargé, pile
dentaire complète, plan comptable `ch`, devise CHF. Garde anti-écrasement
re-vérifiée (refus sans `--force`), copie jetée en fin d'exercice, crons
de production intacts (24 actifs). Un exercice pareil vaut d'être rejoué
après chaque changement de schéma majeur — et toujours vers une base
d'ESSAI, jamais vers la production.

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

**Un module ne monte JAMAIS sa dépendance.** `-u <module>` marque ce module et
tout son **aval** — les modules qui dépendent de lui — jamais l'amont :
`button_upgrade` ne parcourt que les dépendants, et `update_list` se contente
d'incrémenter un compteur d'affichage quand la version du manifeste dépasse
celle en base, sans toucher à l'état. Une dépendance restée « installed » ne
rejoue pas ses données. Dès qu'une version référence un identifiant externe
neuf posé par un module dont elle dépend, il faut donc monter le **parent** :
pour la pile dentaire, `-u megga_dental`, qui entraîne `_rdv`, `_portal`,
`_stock`, `_materiel` puis `_sterilisation`. Même règle pour une installation
délibérée sur une base en service : `-u megga_dental -i megga_dental_materiel`
**dans une seule invocation**, jamais `-i megga_dental_materiel` seul — les
scripts de migration ne tournent pas à l'installation.

## Avant le premier client réel

- [ ] `.env` avec des mots de passe longs et uniques (pas ceux de l'exemple)
- [ ] Certificat TLS valide (Let's Encrypt) et renouvellement automatique
- [ ] Sauvegardes répliquées **hors de la machine**
- [ ] Une restauration réellement testée sur cette installation
- [ ] `ODOO_WORKERS` ajusté : (2 × cœurs) + 1
- [ ] Spécimens QR-facture et pain.001 validés sur le portail de test bancaire
- [ ] Décompte TVA rapproché avec la fiduciaire
