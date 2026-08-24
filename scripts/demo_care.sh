#!/usr/bin/env bash
# Mise en scene de la base de DEMO de la verticale conciergerie medicale.
#
# Recree une base JETABLE avec les donnees de demonstration du produit
# (le mandat de check-up du transcript fondateur, les accords de
# retrocession), puis pose le decor du deroule de demo :
#
#  1. le cout reel de l'evenement laboratoire est remis a zero — la piece
#     QR recue en seance (scripts/demo/facture-labo.txt, 450.00 CHF) le
#     PROPOSE alors en direct : c'est le moment fort de la sequence 3 ;
#  2. trois factures fournisseurs « Pharmacie du Bourg-de-Four » validees
#     et datees du trimestre en cours (30 000, 22 000, avoir 2 000) — le
#     decompte de retrocession cree en seance affiche 50 000 de volume,
#     soit 5 000 a encaisser a 10 % ;
#  3. l'adresse de l'alias e-mail du journal d'achat est imprimee. Sans
#     passerelle entrante configuree (cas d'une demo locale), le geste
#     equivalent est le bouton « Charger » des factures fournisseurs :
#     meme cadre de decodage, meme resultat.
#
# La base nommee ici est DETRUITE et recreee a chaque lancement : ne
# jamais viser une base de travail.
#
# usage : bash scripts/demo_care.sh [nom_de_base]   (defaut : megga_demo_care)
set -euo pipefail

ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
SUB="$(git -C "$ROOT" config -f "$ROOT/.gitmodules" --get-regexp '^submodule\..*\.path$' | awk 'NR==1{print $2}')"
[ -n "$SUB" ] || { echo "ERREUR: aucun sous-module declare dans .gitmodules"; exit 1; }
cd "$ROOT"

BASEDIR="$(dirname "$SUB")"
[ "$BASEDIR" = "." ] && PREFIXE="" || PREFIXE="$BASEDIR/"

ODOO_BIN="$SUB/odoo-bin"
[ -f "$ODOO_BIN" ] || {
    echo "ERREUR: $ODOO_BIN introuvable."
    echo "        Materialisez le sous-module : git submodule update --init --depth 1 $SUB"
    exit 1
}

BASE="${1:-megga_demo_care}"
MODULES="megga_care,megga_retrocession,megga_care_import"
CHEMINS="$SUB/addons,${PREFIXE}addons,${PREFIXE}addons/verticals/care,${PREFIXE}addons-oca"

echo "Base de demo : $BASE (detruite et recreee)"
dropdb --if-exists "$BASE" 2>/dev/null || true

# Installation AVEC les donnees de demonstration : le mandat de Karim,
# les prestataires et les accords de retrocession arrivent avec les
# modules. --with-demo est INDISPENSABLE — depuis 19.0, une base creee
# en ligne de commande n'embarque plus la demo par defaut (verifie dans
# le source : option with_demo, my_default=False).
python3 "$ODOO_BIN" -d "$BASE" \
    --addons-path="$CHEMINS" \
    -i "$MODULES" --with-demo \
    --stop-after-init --max-cron-threads=0 --log-level=warn

# Le decor, pose par le shell Odoo (ORM direct, pas de serveur a lancer).
python3 "$ODOO_BIN" shell -d "$BASE" \
    --addons-path="$CHEMINS" \
    --max-cron-threads=0 --log-level=warn <<'PYTHON'
from datetime import date, timedelta

from odoo import Command

# 1. Le cout du laboratoire attend sa piece : la QR le proposera.
labo = env.ref('megga_care.demo_event_labo')
labo.cost_price = 0.0

# 2. Le volume du trimestre chez la pharmacie, avoir compris. Dates
#    clampees dans [debut du trimestre ; aujourd'hui] pour que le
#    decompte cree en seance les trouve toutes.
pharma = env.ref('megga_retrocession.demo_partner_pharmacie')
today = date.today()
qstart = date(today.year, 3 * ((today.month - 1) // 3) + 1, 1)
def dans_le_trimestre(jour):
    return max(qstart, min(jour, today))
pieces = (
    ('in_invoice', 30000.0, dans_le_trimestre(qstart + timedelta(days=10)),
     "Volume pharmacie — 1er mois"),
    ('in_invoice', 22000.0, dans_le_trimestre(qstart + timedelta(days=40)),
     "Volume pharmacie — 2e mois"),
    ('in_refund', 2000.0, dans_le_trimestre(today - timedelta(days=2)),
     "Avoir sur retours"),
)
for move_type, montant, jour, libelle in pieces:
    move = env['account.move'].create({
        'move_type': move_type,
        'partner_id': pharma.id,
        'invoice_date': jour,
        'invoice_line_ids': [Command.create({
            'name': libelle, 'quantity': 1.0, 'price_unit': montant,
        })],
    })
    move.action_post()

# 3. L'etat des lieux, imprime pour la checklist de la veille.
mandat = env.ref('megga_care.demo_mandate_checkup')
journal = env['account.journal'].search([('type', '=', 'purchase')], limit=1)
alias = journal.alias_id.display_name if journal.alias_id else "(non configure)"
factures = env['account.move'].search_count([
    ('partner_id', '=', pharma.id),
    ('move_type', 'in', ('in_invoice', 'in_refund')),
    ('state', '=', 'posted')])
print("")
print("=== Decor pose ===")
print("Mandat de demo   : %s (%s), evenements du %s" % (
    mandat.name, dict(mandat._fields['state'].selection)[mandat.state],
    mandat.date_start))
print("Cout labo        : %.2f (la piece QR proposera 450.00)" % labo.cost_price)
print("Pieces pharmacie : %d validees (volume trimestre 50 000, avoir deduit)" % factures)
print("Alias achats     : %s" % alias)
print("Piece de seance  : scripts/demo/facture-labo.txt (par e-mail, ou")
print("                   bouton « Charger » des factures fournisseurs)")
print("Connexion        : admin / admin — a changer si la base sort du poste")
env.cr.commit()
PYTHON

echo ""
echo "Base $BASE prete. Lancer le serveur puis derouler le kit de demo."
