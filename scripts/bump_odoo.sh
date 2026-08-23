#!/usr/bin/env bash
# Rituel de montee du coeur Odoo (Phase 5 du plan de reprise).
#
# 1. Compare le SHA epingle au sommet AMONT de la branche suivie.
# 2. Si rien n'a bouge : sortie 0 sans rien faire (code special 99 pour le CI).
# 3. Sinon : synchronise le fork, materialise le sous-module au nouveau SHA
#    et met a jour le gitlink. Les TESTS ne sont pas lances ici : c'est
#    l'appelant (CI ou humain) qui les lance et decide.
#
# Usage : scripts/bump_odoo.sh [--dry-run]
#   GITHUB_TOKEN : facultatif. S'il est present et autorise a ecrire sur le
#   fork, la synchronisation est automatique ; sinon le script s'arrete avec
#   les instructions de synchronisation manuelle.
set -euo pipefail

DRY_RUN="${1:-}"
UPSTREAM_URL="https://github.com/odoo/odoo.git"

ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
cd "$ROOT"

SUB="$(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | awk 'NR==1{print $2}')"
FORK_URL="$(git config -f .gitmodules --get "submodule.${SUB}.url")"
BRANCHE="$(git config -f .gitmodules --get "submodule.${SUB}.branch")"
FORK_SLUG="$(printf '%s' "$FORK_URL" | sed -E 's#.*github\.com[:/]([^/]+/[^/.]+)(\.git)?#\1#')"

ACTUEL="$(git ls-tree HEAD "$SUB" | awk '$2 == "commit" { print $3 }')"
[ -n "$ACTUEL" ] || { echo "ERREUR: gitlink '$SUB' introuvable dans HEAD"; exit 1; }

echo "sous-module : $SUB ($FORK_SLUG, branche $BRANCHE)"
echo "SHA epingle : $ACTUEL"

AMONT="$(git ls-remote "$UPSTREAM_URL" "refs/heads/${BRANCHE}" | cut -f1)"
[ -n "$AMONT" ] || { echo "ERREUR: branche $BRANCHE introuvable sur l'amont"; exit 1; }
echo "sommet amont : $AMONT"

EXERCICE=0
if [ "$ACTUEL" = "$AMONT" ]; then
    if [ "${FORCER:-0}" = "1" ] && [ "$DRY_RUN" != "--dry-run" ]; then
        # Mode force sans montee : EXERCICE de synchronisation. On
        # deroule la section fork (jeton compris) pour prouver la
        # plomberie, puis on sort en 99 — pas de bump a blanc, pas de
        # tests, pas de PR. C'est le chemin de verification du
        # FORK_SYNC_TOKEN. (Avant cette branche, un run force sans
        # montee sortait en 99 AVANT la section fork : rouge en CI et
        # jeton jamais exerce — constate le 23/08/2026.)
        echo "AMONT INCHANGE — exercice de synchronisation (FORCER=1)."
        EXERCICE=1
    else
        echo "RIEN A FAIRE — le coeur est deja a jour."
        exit 99
    fi
else
    echo "Un bump est disponible : ${ACTUEL:0:12} -> ${AMONT:0:12}"
fi
if [ "$DRY_RUN" = "--dry-run" ]; then
    echo "(--dry-run : on s'arrete ici)"
    exit 0
fi

# --- Synchronisation du fork -------------------------------------------------
# Sans elle, le nouveau SHA n'existe pas dans le fork et le sous-module serait
# incassable pour quiconque clone le depot.
echo "Synchronisation du fork ${FORK_SLUG}..."
SYNC_OK=0
if [ -n "${GITHUB_TOKEN:-}" ]; then
    REPONSE="$(curl -sS -w '\n%{http_code}' -X POST \
        -H "Authorization: Bearer ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/${FORK_SLUG}/merge-upstream" \
        -d "{\"branch\":\"${BRANCHE}\"}" || true)"
    CODE="$(printf '%s' "$REPONSE" | tail -1)"
    if [ "$CODE" = "200" ]; then
        echo "  fork synchronise (merge-upstream)"
        SYNC_OK=1
    else
        echo "  echec de merge-upstream (HTTP $CODE) :"
        printf '%s\n' "$REPONSE" | head -3 | sed 's/^/    /'
        # Repli : mise a jour DIRECTE de la ref (Git Data API) — defense
        # en profondeur si merge-upstream echoue pour une autre raison
        # que les droits. (Constate le 23/08/2026 : un jeton SANS
        # « Contents: write » recolte le meme 403 « Resource not
        # accessible » sur LES DEUX voies — le remede est alors la
        # permission du jeton, pas le repli ; avec Contents: write,
        # merge-upstream passe, fine-grained compris.) Le SHA amont
        # existe deja dans le RESEAU du fork (les forks GitHub partagent
        # leur magasin d'objets avec l'amont) : pointer refs/heads/19.0
        # dessus est une avance rapide sans aucun transfert —
        # force:false, le serveur refuse tout ecrasement d'historique.
        echo "  repli : mise a jour directe de la ref..."
        REPONSE2="$(curl -sS -w '\n%{http_code}' -X PATCH \
            -H "Authorization: Bearer ${GITHUB_TOKEN}" \
            -H "Accept: application/vnd.github+json" \
            "https://api.github.com/repos/${FORK_SLUG}/git/refs/heads/${BRANCHE}" \
            -d "{\"sha\":\"${AMONT}\",\"force\":false}" || true)"
        CODE2="$(printf '%s' "$REPONSE2" | tail -1)"
        if [ "$CODE2" = "200" ]; then
            echo "  fork synchronise (mise a jour directe de la ref)"
            SYNC_OK=1
        else
            echo "  echec de la mise a jour directe (HTTP $CODE2) :"
            printf '%s\n' "$REPONSE2" | head -3 | sed 's/^/    /'
        fi
    fi
fi

# Verification independante : le SHA amont est-il REELLEMENT dans le fork ?
# C'est la seule preuve qui compte — une synchronisation « reussie » qui
# n'aurait pas propage le commit laisserait un depot incassable.
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
if git -c protocol.version=2 ls-remote "$FORK_URL" "refs/heads/${BRANCHE}" \
     | cut -f1 | grep -qx "$AMONT"; then
    echo "  verifie : le fork pointe bien $AMONT"
    if [ "$EXERCICE" = "1" ]; then
        echo
        echo "EXERCICE REUSSI — plomberie de synchronisation verifiee,"
        echo "rien a bumper (le coeur est deja au sommet de l'amont)."
        exit 99
    fi
else
    echo
    echo "ARRET — le fork ${FORK_SLUG} n'est PAS a jour."
    [ "$SYNC_OK" = "0" ] && echo "        (aucun jeton disponible, ou synchronisation refusee)"
    echo
    echo "  Synchronisez-le, puis relancez :"
    echo "    - sur GitHub : ${FORK_URL%.git} ▸ bouton « Sync fork »"
    echo "    - ou en ligne de commande :"
    echo "        git clone --bare $FORK_URL /tmp/fork && cd /tmp/fork"
    echo "        git fetch $UPSTREAM_URL ${BRANCHE}:${BRANCHE} && git push origin ${BRANCHE}"
    exit 1
fi

# --- Montee du gitlink -------------------------------------------------------
echo "Materialisation du sous-module au nouveau SHA (shallow)..."
if [ ! -e "$SUB/.git" ]; then
    git submodule update --init --depth 1 "$SUB" >/dev/null 2>&1 || true
fi
git -C "$SUB" fetch --depth 1 origin "$AMONT" >/dev/null 2>&1 \
    || git -C "$SUB" fetch --depth 50 origin "$BRANCHE" >/dev/null 2>&1
git -C "$SUB" checkout -q "$AMONT"
git add "$SUB"

echo
echo "BUMP PREPARE : ${ACTUEL:0:12} -> ${AMONT:0:12}"
echo "Lancez les tests AVANT de committer :"
echo "  scripts/run_tests.sh"
