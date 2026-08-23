#!/usr/bin/env bash
# Injecte les secrets depuis l'environnement dans une copie runtime de la
# configuration : le fichier versionne ne contient jamais de mot de passe.
set -euo pipefail

: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD manquant (voir .env.example)}"
: "${ODOO_ADMIN_PASSWD:?ODOO_ADMIN_PASSWD manquant (voir .env.example)}"

CONF=/tmp/odoo.runtime.conf
cp /etc/odoo/odoo.conf "$CONF"
{
    echo "db_password = ${POSTGRES_PASSWORD}"
    echo "admin_passwd = ${ODOO_ADMIN_PASSWD}"
    [ -n "${ODOO_WORKERS:-}" ] && echo "workers = ${ODOO_WORKERS}"
} >> "$CONF"
chmod 600 "$CONF"

exec python3 /opt/odoo/odoo-bin -c "$CONF" "$@"
