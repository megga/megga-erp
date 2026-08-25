#!/usr/bin/env bash
# Lance les tests des modules Megga sur une base jetable.
#
# DEUX garde-fous, parce qu'un rituel non surveille ne doit jamais mentir :
#  1. odoo-bin renvoie un code NON NUL quand un test echoue — verifie dans le
#     source (preload_registries : « if not ..._assertion_report
#     .wasSuccessful(): rc += 1 » puis sys.exit(rc)) ET empiriquement
#     (23/08/2026, test en echec delibere -> code 1).
#  2. UN RUN QUI N'EXECUTE AUCUN TEST EST UN ECHEC. Sans ce controle, une
#     erreur de chemin d'addons produit « 0 failed of 0 tests » et un code 0 :
#     le rituel passerait au vert sans avoir rien verifie. Cas reellement
#     rencontre le 23/08/2026.
#
# Surcharges (diagnostic) : TEST_DB, TEST_MODULES, TEST_TAGS, EXTRA_ADDONS,
#                           TEST_MIN (nombre minimal de tests attendus),
#                           TEST_HTTP_PORT (defaut 8199)
#
# Le serveur HTTP des tests (indispensable aux HttpCase de megga_rdv)
# ecoute sur 127.0.0.1:8199 : SANS ce reglage, odoo-bin prend 8069 et
# entre en collision avec une production locale sur le meme hote —
# constate le 25/08/2026 (la prod dentaire ne pouvait plus se relancer
# tant que la suite tournait).
#
# NOTE : --log-handler=odoo.tests.result:INFO est INDISPENSABLE. A
# --log-level=warn seul, la ligne de resultat d'un run REUSSI est de
# niveau INFO donc masquee : le compteur lirait 0 et le garde-fou n°2
# declarerait un echec sur une suite pourtant verte (piege rencontre
# le 23/08/2026).
set -euo pipefail

# Tout le corps vit dans un bloc { } : bash parse un bloc ENTIER avant
# d'en executer la premiere ligne, au lieu de relire le fichier au fil
# de l'eau. Sans lui, editer ce script pendant qu'un run tourne decale
# les octets sous le lecteur : bash reprend au milieu d'une ligne et
# execute du charabia (constate le 25/08/2026 : un second odoo-bin
# mutile, « 0 of 0 tests », garde-fou n°2 declenche a tort).
{

ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
SUB="$(git -C "$ROOT" config -f "$ROOT/.gitmodules" --get-regexp '^submodule\..*\.path$' | awk 'NR==1{print $2}')"
[ -n "$SUB" ] || { echo "ERREUR: aucun sous-module declare dans .gitmodules"; exit 1; }
cd "$ROOT"

# addons/ et addons-oca/ vivent a cote du sous-module, quelle que soit
# l'arborescence (racine du depot produit, ou sous-repertoire erp/).
BASEDIR="$(dirname "$SUB")"
[ "$BASEDIR" = "." ] && PREFIXE="" || PREFIXE="$BASEDIR/"

ODOO_BIN="$SUB/odoo-bin"
[ -f "$ODOO_BIN" ] || {
    echo "ERREUR: $ODOO_BIN introuvable."
    echo "        Materialisez le sous-module : git submodule update --init --depth 1 $SUB"
    exit 1
}
[ -d "${PREFIXE}addons" ] || { echo "ERREUR: ${PREFIXE}addons introuvable"; exit 1; }

BASE="${TEST_DB:-megga_ci_$$}"
MODULES="${TEST_MODULES:-megga_base,megga_qr_export,megga_camt,megga_pain001,megga_qr_import,megga_tva_ch,megga_rdv,megga_retrocession,megga_dental,megga_dental_rdv,megga_resto,megga_resto_rdv,megga_resto_tva,megga_auto,megga_auto_rdv,megga_auto_occasion,megga_care,megga_care_import}"
TAGS="${TEST_TAGS:-/megga_qr_export,/megga_camt,/megga_pain001,/megga_qr_import,/megga_tva_ch,/megga_rdv,/megga_retrocession,/megga_dental,/megga_dental_rdv,/megga_resto,/megga_resto_rdv,/megga_resto_tva,/megga_auto,/megga_auto_rdv,/megga_auto_occasion,/megga_care,/megga_care_import}"
MIN="${TEST_MIN:-260}"
# Chaque verticale (addons/verticals/<secteur>/) est un chemin d'addons
# supplémentaire : le rituel teste ainsi le cœur + le socle + TOUTES les
# verticales d'un coup à chaque bump.
CHEMINS="$SUB/addons,${PREFIXE}addons,${PREFIXE}addons/verticals/dental,${PREFIXE}addons/verticals/resto,${PREFIXE}addons/verticals/auto,${PREFIXE}addons/verticals/care,${PREFIXE}addons-oca${EXTRA_ADDONS:+,$EXTRA_ADDONS}"

echo "Base de test : $BASE"
echo "Chemins      : $CHEMINS"
dropdb --if-exists "$BASE" 2>/dev/null || true
trap 'dropdb --if-exists "$BASE" 2>/dev/null || true' EXIT

JOURNAL="$(mktemp)"
set +e
python3 "$ODOO_BIN" -d "$BASE" \
    --addons-path="$CHEMINS" \
    -i "$MODULES" \
    --test-enable --test-tags "$TAGS" \
    --http-interface=127.0.0.1 --http-port="${TEST_HTTP_PORT:-8199}" \
    --without-demo=all --stop-after-init --max-cron-threads=0 \
    --log-level=warn --log-handler=odoo.tests.result:INFO 2>&1 | tee "$JOURNAL"
CODE=${PIPESTATUS[0]}
set -e

if [ "$CODE" -ne 0 ]; then
    echo "TESTS EN ECHEC (code $CODE) — ne pas fusionner ce bump."
    rm -f "$JOURNAL"; exit "$CODE"
fi

# Garde-fou n°2 : combien de tests ont REELLEMENT tourne ?
EXECUTES="$(grep -oE 'of [0-9]+ tests' "$JOURNAL" | tail -1 | grep -oE '[0-9]+' || echo 0)"
rm -f "$JOURNAL"
if [ "${EXECUTES:-0}" -lt "$MIN" ]; then
    echo "ECHEC : ${EXECUTES:-0} test(s) execute(s), ${MIN} attendus au minimum."
    echo "        Un run qui ne teste rien n'est pas un run vert — verifiez"
    echo "        les chemins d'addons et les etiquettes de test."
    exit 1
fi
echo "TESTS VERTS (${EXECUTES} tests executes)."
exit 0
}
