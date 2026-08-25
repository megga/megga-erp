#!/usr/bin/env bash
# Mise en scene de la base de DEMO du magasin dentaire.
#
# Recree une base JETABLE avec megga_dental_stock, puis pose le decor
# qui rend le module lisible en trois ecrans :
#
#  1. quatre consommables du cabinet (compresses, articaine, composite,
#     gants) tracks par lot et a peremption ;
#  2. des lots dates a dessein : un PERIME (decor rouge), un en ALERTE
#     (decor orange), et des lots sains — c'est la liste « Lots et
#     peremption », triee par urgence, qui raconte le module ;
#  3. des quantites en rayon, pour que « Quantites en stock » ne soit
#     pas une page vide.
#
# Le semeur est IDEMPOTENT (relançable) et commite explicitement : le
# shell Odoo ne valide pas tout seul.
#
# La base nommee ici est DETRUITE et recreee a chaque lancement : ne
# jamais viser une base de travail.
#
# usage : bash scripts/demo_dental_stock.sh [nom_de_base]
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

BASE="${1:-megga_demo_dental_stock}"
MODULES="megga_dental_stock"
CHEMINS="$SUB/addons,${PREFIXE}addons,${PREFIXE}addons/verticals/dental,${PREFIXE}addons-oca"

echo "Base de demo : $BASE (detruite et recreee)"
dropdb --if-exists "$BASE" 2>/dev/null || true

python3 "$ODOO_BIN" -d "$BASE" \
    --addons-path="$CHEMINS" \
    -i "$MODULES" \
    --stop-after-init --max-cron-threads=0 --log-level=warn

python3 "$ODOO_BIN" shell -d "$BASE" \
    --addons-path="$CHEMINS" \
    --max-cron-threads=0 --log-level=warn <<'PYTHON'
from datetime import timedelta

from odoo import fields

categ = env.ref('megga_dental_stock.product_category_dental_supplies')
stock = env.ref('stock.stock_location_stock')
maintenant = fields.Datetime.now()

# 1. Les consommables du cabinet. Idempotent : on retrouve par nom.
CATALOGUE = [
    ("Compresses steriles 5x5 cm", "boite de 100", 12.50),
    ("Articaine 4% adrenaline 1:100'000", "cartouche 1.7 ml", 1.35),
    ("Composite photopolymerisable A2", "seringue 4 g", 38.00),
    ("Gants nitrile taille M", "boite de 100", 9.90),
]
produits = {}
for nom, description, prix in CATALOGUE:
    produit = env['product.product'].search([('name', '=', nom)], limit=1)
    valeurs = {
        'name': nom,
        'type': 'consu',
        'is_storable': True,
        'tracking': 'lot',
        'use_expiration_date': True,
        'expiration_time': 540,
        'alert_time': 60,
        'categ_id': categ.id,
        'standard_price': prix,
        'list_price': prix,
        'description_sale': description,
    }
    if produit:
        produit.write(valeurs)
    else:
        produit = env['product.product'].create(valeurs)
    produits[nom] = produit

# 2. Les lots : un perime, un en alerte, des sains. Ce sont les DATES
#    qui racontent le module — la liste se lit du plus urgent au moins.
LOTS = [
    ("Compresses steriles 5x5 cm", "CMP-2024-07", -21, 6),
    ("Compresses steriles 5x5 cm", "CMP-2026-02", 34, 40),
    ("Compresses steriles 5x5 cm", "CMP-2026-05", 210, 60),
    ("Articaine 4% adrenaline 1:100'000", "ART-25-118", -4, 30),
    ("Articaine 4% adrenaline 1:100'000", "ART-26-042", 96, 250),
    ("Composite photopolymerisable A2", "CMP-A2-9911", 51, 12),
    ("Composite photopolymerisable A2", "CMP-A2-1207", 320, 18),
    ("Gants nitrile taille M", "GNT-4471", 275, 24),
]
for nom, reference, jours, quantite in LOTS:
    produit = produits[nom]
    lot = env['stock.lot'].search(
        [('name', '=', reference), ('product_id', '=', produit.id)], limit=1)
    peremption = maintenant + timedelta(days=jours)
    if lot:
        lot.expiration_date = peremption
    else:
        lot = env['stock.lot'].create({
            'name': reference,
            'product_id': produit.id,
            'expiration_date': peremption,
        })
    en_rayon = env['stock.quant']._get_available_quantity(
        produit, stock, lot_id=lot, strict=True)
    manquant = quantite - en_rayon
    if manquant > 0:
        env['stock.quant']._update_available_quantity(
            produit, stock, manquant, lot_id=lot)

# 3. Francais suisse : une demo de cabinet romand se lit en francais.
#    _activate_lang charge les traductions embarquees par le coeur.
env['res.lang']._activate_lang('fr_CH')
langue = env['res.lang'].search([('code', '=', 'fr_CH')], limit=1)
if langue:
    # _activate_lang ouvre la langue ; il ne recharge PAS les
    # traductions des modules deja installes — sans cet appel, les
    # entetes du coeur (Expiration Date, Lot/Serial Number) restent en
    # anglais au milieu d'un ecran francais.
    env['ir.module.module'].search([('state', '=', 'installed')]) \
        ._update_translations(filter_lang=[langue.code])
    env.ref('base.user_admin').lang = langue.code

# 4. L'admin voit le magasin : sans les groupes stock, le menu du
#    cabinet ne s'affiche pas (c'est la doctrine, pas un oubli).
admin = env.ref('base.user_admin')
admin.group_ids = [(4, env.ref('stock.group_stock_user').id),
                   (4, env.ref('stock.group_stock_manager').id),
                   (4, env.ref('megga_dental.group_dental_praticien').id)]

env.cr.commit()
print("Decor pose : %s produits, %s lots." % (len(produits), len(LOTS)))
PYTHON

echo
echo "Base de demo prete : $BASE"
echo "  python3 $ODOO_BIN -d $BASE --addons-path=$CHEMINS --http-port=8069"
echo "  puis Dentaire > Stock du cabinet > Lots et peremption"
