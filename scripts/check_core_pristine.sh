#!/usr/bin/env bash
# Garde-fou anti-fork (Phase 1 du plan de reprise).
# 1) Le worktree du sous-module erp/odoo ne doit porter aucune modification locale.
# 2) Le SHA epingle doit appartenir a l'historique AMONT de la branche 19.0
#    (jamais un commit local : on etend, on ne modifie pas).
# Usage : check_core_pristine.sh [--offline]   (--offline saute le controle n°2)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SUB="erp/odoo"
BRANCHE_AMONT="19.0"
URL_AMONT="https://github.com/megga/odoo.git"

GITLINK="$(git -C "$ROOT" ls-tree HEAD "$SUB" | awk '$2 == "commit" { print $3 }')"
if [ -z "$GITLINK" ]; then
    echo "ERREUR: aucun gitlink '$SUB' dans HEAD — le sous-module a ete retire de l'index ?"
    echo "        (git add -A avec le repertoire absent peut stager sa suppression)"
    exit 1
fi
echo "gitlink $SUB = $GITLINK"

if [ -e "$ROOT/$SUB/.git" ]; then
    DIRTY="$(git -C "$ROOT/$SUB" status --porcelain)"
    if [ -n "$DIRTY" ]; then
        echo "ERREUR: modifications locales dans $SUB — le coeur est en lecture seule, fork interdit :"
        echo "$DIRTY" | head -20
        exit 1
    fi
    echo "worktree du sous-module : propre"
else
    echo "note: sous-module non materialise — controle du worktree saute"
fi

if [ "${1:-}" = "--offline" ]; then
    echo "mode --offline : controle d'ancetre amont saute"
    exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
# --filter=tree:0 : historique des commits seulement, sans arbres ni blobs
git clone --quiet --filter=tree:0 --no-checkout --single-branch \
    --branch "$BRANCHE_AMONT" "$URL_AMONT" "$TMP/odoo"
if git -C "$TMP/odoo" merge-base --is-ancestor "$GITLINK" HEAD; then
    echo "OK: $GITLINK appartient a l'historique amont de $BRANCHE_AMONT"
else
    echo "ERREUR: $GITLINK n'est PAS un commit amont de $BRANCHE_AMONT (commit local ?)"
    exit 1
fi
