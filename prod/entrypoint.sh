#!/usr/bin/env bash
# Injecte les secrets depuis l'environnement dans une copie runtime de la
# configuration : le fichier versionne ne contient jamais de mot de passe.
set -euo pipefail

: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD manquant (voir .env.example)}"
: "${ODOO_ADMIN_PASSWD:?ODOO_ADMIN_PASSWD manquant (voir .env.example)}"

CONF=/tmp/odoo.runtime.conf
cp /etc/odoo/odoo.conf "$CONF"
# REMPLACER, jamais dupliquer : le configparser de Python 3.12 refuse
# une option en double — avec le workers deja present dans la conf de
# base, le conteneur bouclait sur DuplicateOptionError (constate en
# reel le 23/08/2026). Le [ -n ] && en fin de bloc tuait aussi le
# script sous set -e quand ODOO_WORKERS etait vide.
sed -i '/^db_password[[:space:]]*=/d; /^admin_passwd[[:space:]]*=/d' "$CONF"
{
    echo "db_password = ${POSTGRES_PASSWORD}"
    echo "admin_passwd = ${ODOO_ADMIN_PASSWD}"
} >> "$CONF"
if [ -n "${ODOO_WORKERS:-}" ]; then
    sed -i '/^workers[[:space:]]*=/d' "$CONF"
    echo "workers = ${ODOO_WORKERS}" >> "$CONF"
fi
chmod 600 "$CONF"

exec python3 /opt/odoo/odoo-bin -c "$CONF" "$@"
