#!/usr/bin/env bash
# Sauvegarde Megga : base PostgreSQL (format custom) + filestore.
# Chaque sauvegarde est verifiee immediatement apres ecriture : une archive
# corrompue detectee un mois plus tard n'est plus une sauvegarde.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
DB_NAME="${ODOO_DB_NAME:-megga}"
DB_HOST="${PGHOST:-db}"
DB_USER="${PGUSER:-odoo}"
FILESTORE="${FILESTORE_DIR:-/var/lib/odoo/filestore}"
RETENTION="${BACKUP_RETENTION_DAYS:-30}"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
DEST="${BACKUP_DIR}/${DB_NAME}-${STAMP}"
mkdir -p "$DEST"

echo "[1/4] Dump de la base ${DB_NAME}..."
pg_dump --host="$DB_HOST" --username="$DB_USER" --dbname="$DB_NAME" \
        --format=custom --compress=6 --file="${DEST}/database.dump"

echo "[2/4] Archive du filestore..."
if [ -d "${FILESTORE}/${DB_NAME}" ]; then
    tar -czf "${DEST}/filestore.tar.gz" -C "$FILESTORE" "$DB_NAME"
else
    echo "  ATTENTION : filestore introuvable (${FILESTORE}/${DB_NAME})."
    echo "  Les pieces jointes ne seront PAS restaurables. Verifiez FILESTORE_DIR."
    : > "${DEST}/FILESTORE-ABSENT"
fi

echo "[3/4] Verification de l'archive..."
# pg_restore --list echoue si le dump est tronque ou corrompu.
pg_restore --list "${DEST}/database.dump" > "${DEST}/contenu.txt"
TABLES=$(grep -c 'TABLE DATA' "${DEST}/contenu.txt" || true)
if [ "$TABLES" -lt 100 ]; then
    echo "ECHEC : seulement ${TABLES} tables dans le dump — sauvegarde suspecte."
    exit 1
fi
[ -f "${DEST}/filestore.tar.gz" ] && tar -tzf "${DEST}/filestore.tar.gz" > /dev/null
( cd "$DEST" && sha256sum database.dump $( [ -f filestore.tar.gz ] && echo filestore.tar.gz ) > SHA256SUMS )

echo "[4/4] Purge des sauvegardes de plus de ${RETENTION} jours..."
find "$BACKUP_DIR" -maxdepth 1 -type d -name "${DB_NAME}-*" -mtime "+${RETENTION}" \
     -exec rm -rf {} + 2>/dev/null || true

echo "OK — ${DEST} (${TABLES} tables, $(du -sh "$DEST" | cut -f1))"
