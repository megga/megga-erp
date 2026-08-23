#!/usr/bin/env bash
# Restauration Megga. Refuse d'ecraser une base existante sans --force :
# une restauration accidentelle en production est irreversible.
set -euo pipefail

usage() { echo "Usage: restore.sh <repertoire-de-sauvegarde> <base-cible> [--force]"; exit 1; }
[ $# -ge 2 ] || usage

SRC="$1"; TARGET="$2"; FORCE="${3:-}"
DB_HOST="${PGHOST:-db}"
DB_USER="${PGUSER:-odoo}"
FILESTORE="${FILESTORE_DIR:-/var/lib/odoo/filestore}"

[ -f "${SRC}/database.dump" ] || { echo "Dump introuvable dans ${SRC}"; exit 1; }

echo "[1/4] Verification de l'integrite..."
if [ -f "${SRC}/SHA256SUMS" ]; then
    ( cd "$SRC" && sha256sum --check --status SHA256SUMS ) \
        || { echo "ECHEC : empreintes non conformes, archive alteree."; exit 1; }
    echo "  empreintes SHA256 conformes"
fi
pg_restore --list "${SRC}/database.dump" > /dev/null

EXISTS=$(psql --host="$DB_HOST" --username="$DB_USER" --dbname=postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='${TARGET}'" || true)
if [ -n "$EXISTS" ] && [ "$FORCE" != "--force" ]; then
    echo "ECHEC : la base '${TARGET}' existe deja. Relancez avec --force pour l'ecraser."
    exit 1
fi

echo "[2/4] Recreation de la base ${TARGET}..."
if [ -n "$EXISTS" ]; then
    psql --host="$DB_HOST" --username="$DB_USER" --dbname=postgres -q -c \
      "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${TARGET}' AND pid<>pg_backend_pid()" > /dev/null
    dropdb --host="$DB_HOST" --username="$DB_USER" "$TARGET"
fi
createdb --host="$DB_HOST" --username="$DB_USER" "$TARGET"

echo "[3/4] Restauration des donnees..."
pg_restore --host="$DB_HOST" --username="$DB_USER" --dbname="$TARGET" \
           --no-owner --no-privileges --jobs=4 "${SRC}/database.dump"

echo "[4/4] Restauration du filestore..."
if [ -f "${SRC}/filestore.tar.gz" ]; then
    mkdir -p "$FILESTORE"
    rm -rf "${FILESTORE:?}/${TARGET}"
    TMP=$(mktemp -d); tar -xzf "${SRC}/filestore.tar.gz" -C "$TMP"
    mv "$TMP"/* "${FILESTORE}/${TARGET}"; rmdir "$TMP"
    echo "  filestore restaure"
else
    echo "  ATTENTION : aucun filestore dans la sauvegarde — pieces jointes absentes."
fi

COUNT=$(psql --host="$DB_HOST" --username="$DB_USER" --dbname="$TARGET" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
echo "OK — base '${TARGET}' restauree (${COUNT} tables)."
echo "RAPPEL : si cette base est une COPIE (test/recette), neutralisez les"
echo "         actions sortantes avant de la demarrer :"
echo "  UPDATE ir_mail_server SET active=false;"
echo "  UPDATE ir_cron SET active=false;"
