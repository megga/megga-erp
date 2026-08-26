#!/usr/bin/env bash
# Mise en scene de la base de DEMO du materiel dentaire.
#
# Recree une base JETABLE avec megga_dental_materiel, puis pose le
# decor qui rend le module lisible en trois ecrans :
#
#  1. les fauteuils du cabinet, et le materiel installe AUTOUR de
#     chacun — la question que le cabinet se pose vraiment ;
#  2. du materiel de local technique (compresseur, aspiration) qui ne
#     sert aucun fauteuil en particulier, et dont la panne arrete tout ;
#  3. des entretiens : une validation trimestrielle d'autoclave DEJA
#     close — donc celle du trimestre suivant deja programmee par le
#     coeur —, une revision annuelle a venir, et une panne en cours.
#
# Le semeur est IDEMPOTENT (relançable) et commite explicitement : le
# shell Odoo ne valide pas tout seul.
#
# La base nommee ici est DETRUITE et recreee a chaque lancement : ne
# jamais viser une base de travail.
#
# usage : bash scripts/demo_dental_materiel.sh [nom_de_base]
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

BASE="${1:-megga_demo_dental_materiel}"
MODULES="megga_dental_materiel"
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

equipe = env.ref('megga_dental_materiel.maintenance_team_dental')
sterilisation = env.ref('megga_dental_materiel.equipment_category_sterilisation')
imagerie = env.ref('megga_dental_materiel.equipment_category_imagerie')
famille_fauteuil = env.ref('megga_dental_materiel.equipment_category_fauteuil')
technique = env.ref('megga_dental_materiel.equipment_category_technique')
aujourdhui = fields.Date.context_today(env.user)
maintenant = fields.Datetime.now()

# 1. Les fauteuils : la ressource que les seances se partagent, et
#    autour de laquelle le materiel s'organise.
fauteuils = {}
for nom, ordre in [("Fauteuil 1", 10), ("Fauteuil 2", 20),
                   ("Salle de chirurgie", 30)]:
    fauteuil = env['megga.dental.chair'].search(
        [('name', '=', nom)], limit=1)
    if not fauteuil:
        fauteuil = env['megga.dental.chair'].create(
            {'name': nom, 'sequence': ordre})
    fauteuils[nom] = fauteuil

# 2. Le fournisseur technique du cabinet : celui qu'on appelle quand
#    l'autoclave s'arrete un mardi matin.
fournisseur = env['res.partner'].search(
    [('name', '=', "Technic Dentaire Sarl")], limit=1)
if not fournisseur:
    fournisseur = env['res.partner'].create({
        'name': "Technic Dentaire Sarl",
        'street': "Chemin du Closel 5",
        'zip': "1020", 'city': "Renens",
        'country_id': env.ref('base.ch').id,
        'supplier_rank': 1,
    })

# 3. Le registre. Les appareils rattaches a un fauteuil, et ceux du
#    local technique qui n'en servent aucun en particulier — ce sont
#    justement ceux dont la panne arrete le cabinet entier.
#    (nom, categorie, fauteuil, numero de serie, modele, mise en
#     service il y a N jours, garantie dans N jours, cout)
REGISTRE = [
    ("Autoclave classe B 18 l", sterilisation, None,
     "AC-B18-77421", "Statim 18B", 900, 190, 8900.00),
    ("Thermosoudeuse a rouleaux", sterilisation, None,
     "TS-3300-118", "SealPro 330", 1400, -40, 1450.00),
    ("Bac a ultrasons 5 l", sterilisation, None,
     "BU-5-9080", "SonoClean 5", 620, 380, 890.00),
    ("Unit dentaire complet", famille_fauteuil, "Fauteuil 1",
     "UD-A200-4417", "Anthos A200", 1650, -120, 32500.00),
    ("Scialytique LED", famille_fauteuil, "Fauteuil 1",
     "SC-LED-2291", "Luxia 5000", 1650, -120, 3200.00),
    ("Unit dentaire complet", famille_fauteuil, "Fauteuil 2",
     "UD-A200-4418", "Anthos A200", 430, 665, 33900.00),
    ("Camera intra-orale", imagerie, "Fauteuil 2",
     "CIO-7712", "SoproCare", 300, 430, 4700.00),
    ("Radiographie retro-alveolaire", imagerie, "Fauteuil 1",
     "RX-RA-5514", "Focus X", 1100, 45, 6400.00),
    ("Panoramique dentaire", imagerie, None,
     "PAN-88213", "OrthoPantomo 3D", 750, 340, 48000.00),
    ("Aspiration chirurgicale", famille_fauteuil, "Salle de chirurgie",
     "ASP-CH-3312", "Turbo Smart", 500, 230, 5100.00),
    ("Compresseur sans huile 50 l", technique, None,
     "CP-50-1102", "SilentAir 50", 1980, -350, 4300.00),
    ("Pompe a salive centralisee", technique, None,
     "PS-CTR-6640", "Cattani Uni-Jet", 1980, -350, 2700.00),
]
appareils = {}
for (nom, categorie, fauteuil, serie, modele, service, garantie,
     cout) in REGISTRE:
    appareil = env['maintenance.equipment'].search(
        [('serial_no', '=', serie)], limit=1)
    valeurs = {
        'name': nom,
        'category_id': categorie.id,
        'chair_id': fauteuils[fauteuil].id if fauteuil else False,
        'maintenance_team_id': equipe.id,
        'serial_no': serie,
        'model': modele,
        'partner_id': fournisseur.id,
        'partner_ref': serie,
        'assign_date': aujourdhui - timedelta(days=service),
        'effective_date': aujourdhui - timedelta(days=service),
        'warranty_date': aujourdhui + timedelta(days=garantie),
        'cost': cout,
        'technician_user_id': env.ref('base.user_admin').id,
    }
    if appareil:
        appareil.write(valeurs)
    else:
        appareil = env['maintenance.equipment'].create(valeurs)
    appareils[serie] = appareil

# 4. Les entretiens. La validation trimestrielle de l'autoclave est
#    DEJA close : le coeur a donc programme celle du trimestre
#    suivant tout seul — c'est la demonstration du chantier, et il n'y
#    a pas une ligne de code maison derriere.
terminee = env['maintenance.stage'].search([('done', '=', True)], limit=1)
# Le shell tourne en OdooBot : sans cette ligne, toutes les demandes de
# la demo seraient « demandees par » le robot du systeme.
demandeur = env.ref('base.user_admin')
autoclave = appareils["AC-B18-77421"]
validation = env['maintenance.request'].search(
    [('equipment_id', '=', autoclave.id),
     ('maintenance_type', '=', 'preventive')], limit=1)
if not validation:
    validation = env['maintenance.request'].create({
        'name': "Validation trimestrielle de l'autoclave",
        'equipment_id': autoclave.id,
        'maintenance_team_id': equipe.id,
        'owner_user_id': demandeur.id,
        'maintenance_type': 'preventive',
        'recurring_maintenance': True,
        'repeat_interval': 3,
        'repeat_unit': 'month',
        'repeat_type': 'forever',
        'schedule_date': maintenant - timedelta(days=5),
        'duration': 1.5,
        'description': "<p>Test de penetration de vapeur (Helix) et "
                       "controle du cycle 134 °C. Rapport de cycle en "
                       "piece jointe.</p>",
    })
    validation.stage_id = terminee

compresseur = appareils["CP-50-1102"]
revision = env['maintenance.request'].search(
    [('equipment_id', '=', compresseur.id),
     ('maintenance_type', '=', 'preventive')], limit=1)
if not revision:
    env['maintenance.request'].create({
        'name': "Revision annuelle du compresseur",
        'equipment_id': compresseur.id,
        'maintenance_team_id': equipe.id,
        'owner_user_id': demandeur.id,
        'maintenance_type': 'preventive',
        'recurring_maintenance': True,
        'repeat_interval': 1,
        'repeat_unit': 'year',
        'repeat_type': 'forever',
        'schedule_date': maintenant + timedelta(days=12),
        'duration': 2.0,
        'priority': '2',
        'description': "<p>Vidange du separateur, controle des "
                       "courroies et de la soupape de securite.</p>",
    })

# Et la panne en cours : le geste du fauteuil, celui que tout employe
# peut poser sans tenir le registre.
radio = appareils["RX-RA-5514"]
panne = env['maintenance.request'].search(
    [('equipment_id', '=', radio.id),
     ('maintenance_type', '=', 'corrective')], limit=1)
if not panne:
    env['maintenance.request'].create({
        'name': "Declenchement intermittent au fauteuil 1",
        'equipment_id': radio.id,
        'maintenance_team_id': equipe.id,
        'owner_user_id': demandeur.id,
        'maintenance_type': 'corrective',
        'priority': '3',
        'kanban_state': 'blocked',
        'schedule_date': maintenant + timedelta(days=1),
        'description': "<p>Deux cliches perdus ce matin. Fournisseur "
                       "prevenu, piece commandee.</p>",
    })

# 5. Francais suisse : une demo de cabinet romand se lit en francais.
env['res.lang']._activate_lang('fr_CH')
langue = env['res.lang'].search([('code', '=', 'fr_CH')], limit=1)
if langue:
    # _activate_lang ouvre la langue ; il ne recharge PAS les
    # traductions des modules deja installes.
    env['ir.module.module'].search([('state', '=', 'installed')]) \
        ._update_translations(filter_lang=[langue.code])
    env.ref('base.user_admin').lang = langue.code

# 6. L'admin voit le registre : sans le groupe du coeur, le menu
#    « Appareils » ne s'affiche pas (c'est la doctrine, pas un oubli —
#    le coeur ne montre a un employe ordinaire que ce qu'il suit).
admin = env.ref('base.user_admin')
admin.group_ids = [(4, env.ref('maintenance.group_equipment_manager').id),
                   (4, env.ref('megga_dental.group_dental_praticien').id)]

env.cr.commit()
print("Decor pose : %s appareils sur %s fauteuils." % (
    len(appareils), len(fauteuils)))
PYTHON

echo
echo "Base de demo prete : $BASE"
echo "  python3 $ODOO_BIN -d $BASE --addons-path=$CHEMINS --http-port=8069"
echo "  puis Dentaire > Materiel > Appareils"
