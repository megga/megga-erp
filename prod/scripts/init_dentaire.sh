#!/usr/bin/env bash
# Initialise une base de PRODUCTION pour la verticale dentaire.
#
# Ce que fait ce script, dans l'ordre :
#  1. cree la base en francais (fr_CH), SANS donnees de demonstration —
#     comportement verifie d'odoo-bin 19.0 : une base creee en CLI est
#     sans demo par defaut, aucun drapeau necessaire ;
#  2. declare la societe SUISSE avant toute comptabilite : c'est le pays
#     de la societe qui decide du plan comptable, donc l10n_ch s'applique
#     de lui-meme a l'etape suivante ;
#  3. installe la pile dentaire (megga_dental + megga_rdv ; le pont
#     megga_dental_rdv s'auto-installe), pose le mot de passe admin,
#     puis VERIFIE : modules installes et plan comptable suisse charges.
#
# Garde-fous :
#  - ADMIN_PASSWORD est exige (jamais de admin/admin en production) ;
#  - une base existante n'est JAMAIS touchee ;
#  - chaque etape s'arrete au premier echec (set -e).
#
# Surcharges : ODOO_BIN, CHEMINS, MODULES, ADMIN_LOGIN (defaut: admin).
# Usage :  ADMIN_PASSWORD='...' bash prod/scripts/init_dentaire.sh [base]
#          (defaut : megga_prod)
set -euo pipefail

if [ -z "${ODOO_BIN:-}" ] && [ -f /opt/odoo/odoo-bin ]; then
    # Conteneur de production (docker-compose.prod.yml) : le coeur et les
    # addons sont montes en /opt, pas de depot git ici. Les identifiants
    # de base viennent de la conf d'exécution (exporter
    # ODOO_RC=/tmp/odoo.runtime.conf, ecrite par l'entrypoint).
    ODOO_BIN=/opt/odoo/odoo-bin
    CHEMINS="${CHEMINS:-/opt/addons,/opt/addons/verticals/dental,/opt/addons-oca,/opt/odoo/addons,/opt/odoo/odoo/addons}"
else
    # Hors conteneur : auto-localisation depuis le depot git, comme
    # run_tests.sh — surcharges ODOO_BIN et CHEMINS toujours possibles.
    ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
    SUB="$(git -C "$ROOT" config -f "$ROOT/.gitmodules" --get-regexp '^submodule\..*\.path$' | awk 'NR==1{print $2}')"
    [ -n "$SUB" ] || { echo "ERREUR: aucun sous-module declare dans .gitmodules"; exit 1; }
    cd "$ROOT"
    BASEDIR="$(dirname "$SUB")"
    [ "$BASEDIR" = "." ] && PREFIXE="" || PREFIXE="$BASEDIR/"
    ODOO_BIN="${ODOO_BIN:-$SUB/odoo-bin}"
    CHEMINS="${CHEMINS:-$SUB/addons,${PREFIXE}addons,${PREFIXE}addons/verticals/dental,${PREFIXE}addons-oca}"
fi
[ -f "$ODOO_BIN" ] || {
    echo "ERREUR: $ODOO_BIN introuvable."
    echo "        Materialisez le sous-module ou exportez ODOO_BIN."
    exit 1
}

BASE="${1:-megga_prod}"
MODULES="${MODULES:-megga_dental,megga_rdv}"
ADMIN_LOGIN="${ADMIN_LOGIN:-admin}"

[ -n "${ADMIN_PASSWORD:-}" ] || {
    echo "ERREUR: exportez ADMIN_PASSWORD — une production ne part jamais"
    echo "        avec admin/admin."
    exit 1
}
if psql -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw "$BASE"; then
    echo "ERREUR: la base « $BASE » existe deja — ce script ne touche"
    echo "        JAMAIS une base existante. Choisissez un autre nom ou"
    echo "        supprimez-la explicitement vous-meme."
    exit 1
fi

echo "=== [1/3] Creation de « $BASE » (fr_CH, sans demo) ==="
python3 "$ODOO_BIN" -d "$BASE" -i base --load-language=fr_CH \
    --addons-path="$CHEMINS" --no-http --stop-after-init \
    --max-cron-threads=0 --log-level=warn

export MEGGA_ADMIN_LOGIN="$ADMIN_LOGIN"
echo "=== [2/3] Societe suisse (le pays decide du plan comptable) ==="
python3 "$ODOO_BIN" shell -d "$BASE" --addons-path="$CHEMINS" --no-http \
    --max-cron-threads=0 --log-level=error <<'PY'
import os
company = env.company
company.partner_id.country_id = env.ref('base.ch')
env['res.lang']._activate_lang('fr_CH')
company.partner_id.lang = 'fr_CH'
admin = env['res.users'].search([('login', '=', os.environ.get('MEGGA_ADMIN_LOGIN', 'admin'))])
assert admin, "compte admin introuvable"
admin.write({
    'lang': 'fr_CH',
    'tz': 'Europe/Zurich',
    'password': os.environ['ADMIN_PASSWORD'],
})
env.cr.commit()
print("societe:", company.name, "| pays:", company.partner_id.country_id.code,
      "| admin:", admin.login, "(mot de passe pose)")
PY

echo "=== [3/3] Installation de la pile dentaire ($MODULES) ==="
python3 "$ODOO_BIN" -d "$BASE" -i "$MODULES" \
    --addons-path="$CHEMINS" --no-http --stop-after-init \
    --max-cron-threads=0 --log-level=warn

echo "=== Verification finale ==="
python3 "$ODOO_BIN" shell -d "$BASE" --addons-path="$CHEMINS" --no-http \
    --max-cron-threads=0 --log-level=error <<'PY'
attendus = ['megga_dental', 'megga_rdv', 'megga_dental_rdv', 'l10n_ch']
installes = env['ir.module.module'].search([
    ('name', 'in', attendus), ('state', '=', 'installed')]).mapped('name')
manquants = set(attendus) - set(installes)
assert not manquants, "modules manquants: %s" % ', '.join(sorted(manquants))
chart = env.company.chart_template or ''
assert chart.startswith('ch'), \
    "plan comptable suisse absent (chart_template=%r)" % chart
assert env.company.currency_id.name == 'CHF', "devise != CHF"
print("OK — base", env.cr.dbname, ": pile dentaire complete,",
      "plan comptable", chart, ", devise CHF, langue fr_CH.")
PY

cat <<FIN

Base « $BASE » prete. RESTE A FAIRE, dans l'application :
  1. Societe : raison sociale, adresse, IDE/TVA, logo.
  2. Banque  : IBAN QR (compte 30000-31999) sur le journal de banque —
     sans lui, pas de QR-facture.
  3. Utilisateurs : un compte par personne, jamais de compte partage.
  4. Catalogue des actes et types de rendez-vous en ligne.
  5. Sauvegardes : timer sur prod/scripts/backup.sh (ODOO_DB_NAME=$BASE),
     et une restauration d'essai avec restore.sh.
FIN
