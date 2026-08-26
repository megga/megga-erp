#!/usr/bin/env bash
# Mise en scene de la base de DEMO de la sterilisation.
#
# Recree une base JETABLE avec megga_dental_sterilisation, puis pose le
# decor qui raconte le module en trois ecrans :
#
#  1. le registre des cycles : des charges validees, une en brouillon,
#     et UNE NON CONFORME — c'est elle qui porte l'histoire ;
#  2. les sets en rayon, dates par leur cycle : le FEFO les range du
#     plus urgent au moins, comme des consommables ;
#  3. le RAPPEL : la charge non conforme nomme la seance qu'elle a
#     servie, et la seance, elle, porte les cycles qui l'ont servie.
#
# Le semeur est IDEMPOTENT (relançable) et commite explicitement : le
# shell Odoo ne valide pas tout seul.
#
# La base nommee ici est DETRUITE et recreee a chaque lancement : ne
# jamais viser une base de travail.
#
# usage : bash scripts/demo_dental_sterilisation.sh [nom_de_base]
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

BASE="${1:-megga_demo_dental_steri}"
MODULES="megga_dental_sterilisation"
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

maintenant = fields.Datetime.now()
categorie_sets = env.ref(
    'megga_dental_sterilisation.product_category_dental_sets')
equipe = env.ref('megga_dental_materiel.maintenance_team_dental')
admin = env.ref('base.user_admin')
# Le shell Odoo tourne en OdooBot : sans cette bascule, tout le decor
# serait signe par le robot du systeme — le praticien de la seance, les
# messages du fil de discussion, l'operateur des charges. Lecon du
# semeur du materiel.
env = env(user=admin)

# 1. L'autoclave du registre : c'est LUI qui signe les charges.
autoclave = env['maintenance.equipment'].search(
    [('serial_no', '=', "AC-B18-77421")], limit=1)
if not autoclave:
    autoclave = env['maintenance.equipment'].create({
        'name': "Autoclave classe B 18 l",
        'serial_no': "AC-B18-77421",
        'model': "Statim 18B",
        'category_id': env.ref(
            'megga_dental_materiel.equipment_category_sterilisation').id,
        'maintenance_team_id': equipe.id,
        'technician_user_id': admin.id,
    })

# 2. Les sets du cabinet. Le DELAI de peremption est ce qui fait vivre
#    la sterilite : sans lui, le coeur ne date rien et la garde ne mord
#    pas. Un sachet pelable tient six mois, un set de chirurgie moins.
CATALOGUE = [
    ("Set d'examen sterilise", "sachet pelable", 180, 14.00),
    ("Set de detartrage sterilise", "sachet pelable", 180, 18.00),
    ("Set de chirurgie sterilise", "double sachet", 90, 46.00),
]
sets = {}
for nom, description, jours, prix in CATALOGUE:
    produit = env['product.product'].search([('name', '=', nom)], limit=1)
    valeurs = {
        'name': nom,
        'type': 'consu',
        'is_storable': True,
        'tracking': 'lot',
        'use_expiration_date': True,
        'expiration_time': jours,
        'alert_time': 21,
        'categ_id': categorie_sets.id,
        'standard_price': prix,
        'list_price': prix,
        'description_sale': description,
    }
    if produit:
        produit.write(valeurs)
    else:
        produit = env['product.product'].create(valeurs)
    sets[nom] = produit

Cycle = env['megga.dental.sterilisation.cycle']


def charge(jours_avant, lignes, **valeurs):
    """Une charge posee il y a N jours. Idempotent par la date."""
    debut = maintenant - timedelta(days=jours_avant)
    existant = Cycle.search([('date_start', '=', debut)], limit=1)
    if existant:
        return existant
    base = {
        'equipment_id': autoclave.id,
        'date_start': debut,
        'user_id': admin.id,
        'helix_ok': True,
        'program': 'b',
        'temperature': 134.0,
        'plateau_minutes': 18.0,
        'line_ids': [(0, 0, {'product_id': sets[nom].id, 'quantity': q})
                     for nom, q in lignes],
    }
    base.update(valeurs)
    return Cycle.create(base)


# 3. Les charges. L'ancienne approche de sa peremption de sterilite :
#    a 165 jours sur 180, elle est dans la fenetre d'alerte du produit.
#    Elle porte un AUTRE set que celui de l'examen — sans quoi le FEFO
#    servirait la seance depuis elle, et la charge dont l'indicateur
#    revient non conforme n'aurait servi personne. Le decor doit rendre
#    l'histoire possible, pas la raconter a cote.
ancienne = charge(165, [("Set de detartrage sterilise", 8.0)])
if ancienne.state == 'draft':
    ancienne.action_validate()

hier = charge(1, [("Set d'examen sterilise", 12.0)],
              indicator='pending')
if hier.state == 'draft':
    hier.action_validate()

chirurgie = charge(3, [("Set de chirurgie sterilise", 4.0)],
                   indicator='pass')
if chirurgie.state == 'draft':
    chirurgie.action_validate()

# Une charge en cours de saisie : l'ecran ne doit pas etre un mur de
# lignes toutes pareilles.
en_cours = charge(0, [("Set de detartrage sterilise", 10.0)])

# 4. Le kit de l'acte : c'est l'ACTE qui sait ce qu'il consomme. Un
#    examen mange un set d'examen — et le decompte de la cloture de
#    seance fait le reste.
position = env['megga.dental.position'].search(
    [('code', '=', "4.0000")], limit=1)
if not position:
    position = env['megga.dental.position'].create({
        'code': "4.0000", 'name': "Examen et bilan", 'points': 35.0})
position.supply_ids.unlink()
position.supply_ids = [(0, 0, {
    'product_id': sets["Set d'examen sterilise"].id, 'quantity': 1.0})]

# 5. Une seance close : elle a consomme un set d'examen, servi par la
#    seule charge qui en porte — celle d'hier, dont l'indicateur
#    biologique n'est pas encore revenu. Le decompte est celui du
#    chantier 2 : la cloture sort le set du rayon toute seule.
patient = env['megga.dental.patient'].search(
    [('name', '=', "Camille Rochat")], limit=1)
if not patient:
    patient = env['megga.dental.patient'].create({'name': "Camille Rochat"})
deja = env['megga.dental.treatment'].search(
    [('patient_id', '=', patient.id), ('state', '=', 'done')], limit=1)
if not deja:
    seance = env['megga.dental.treatment'].create({
        'patient_id': patient.id,
        'line_ids': [(0, 0, {'position_id': position.id, 'quantity': 1.0})],
    })
    seance.action_confirm()
    seance.action_done()
    print("Seance close : %s -> %s" % (
        seance.name, seance.sterilisation_cycle_ids.mapped('name')))

# 6. LE GESTE DU LENDEMAIN. L'indicateur biologique de la charge d'hier
#    revient non conforme : les sets encore en rayon sont bloques, et
#    la seance deja servie est nommee. C'est toute la valeur du module,
#    et la demo doit la montrer — pas la decrire.
if hier.indicator != 'fail':
    hier.indicator = 'fail'
    hier.action_fail()
    print("Rappel : %s" % hier._megga_served_treatments().mapped('name'))

# 7. Francais suisse : une demo de cabinet romand se lit en francais.
env['res.lang']._activate_lang('fr_CH')
langue = env['res.lang'].search([('code', '=', 'fr_CH')], limit=1)
if langue:
    # _activate_lang ouvre la langue ; il ne recharge PAS les
    # traductions des modules deja installes.
    env['ir.module.module'].search([('state', '=', 'installed')]) \
        ._update_translations(filter_lang=[langue.code])
    admin.lang = langue.code

# 8. L'admin voit tout le cabinet : sans les groupes, les menus ne
#    s'affichent pas (c'est la doctrine, pas un oubli).
admin.group_ids = [(4, env.ref('megga_dental.group_dental_praticien').id),
                   (4, env.ref('stock.group_stock_user').id),
                   (4, env.ref('stock.group_stock_manager').id),
                   (4, env.ref('maintenance.group_equipment_manager').id)]

env.cr.commit()
print("Decor pose : %s cycles, %s sets au catalogue." % (
    Cycle.search_count([]), len(sets)))
PYTHON

echo
echo "Base de demo prete : $BASE"
echo "  python3 $ODOO_BIN -d $BASE --addons-path=$CHEMINS --http-port=8069"
echo "  puis Dentaire > Intendance > Sterilisation > Cycles d'autoclave"
