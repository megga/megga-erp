#!/usr/bin/env bash
# Expedition des sauvegardes HORS DE L'HOTE. Une sauvegarde qui brule
# avec le serveur n'en est pas une : ce script pousse les archives deja
# VERIFIEES vers une destination distante, et ne dit OK que si la copie
# distante est identique au bit pres.
#
# Variables :
#   EXPEDITION_DEST (obligatoire)
#       - NAS/machine par SSH : nas:/volume1/megga-sauvegardes
#         (cle SSH deposee, rsync installe des deux cotes)
#       - point de montage (NFS, disque externe) : /mnt/sauvegardes
#       (S3/objet : passer par rclone, variante documentee au runbook.)
#   BACKUP_DIR       (defaut /backups — la ou backup.sh ecrit)
#   EXPEDITION_ALL=1 pour expedier TOUTES les archives presentes
#                    (defaut : la plus recente de chaque base)
#
# Doctrine :
#   1. une archive dont SHA256SUMS ne se verifie plus NE S'EXPEDIE PAS
#      (on n'exporte pas une corruption) ;
#   2. apres la copie, une passe rsync --checksum a blanc doit ne rien
#      trouver a transferer : la copie distante est identique, sinon
#      echec ;
#   3. le marqueur EXPEDIEE (destination + date) n'est pose qu'apres
#      cette contre-verification.
# S'enchaine au timer de sauvegarde : backup.sh && expedier.sh
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
DEST="${EXPEDITION_DEST:?EXPEDITION_DEST manquant (ex.: nas:/volume1/megga-sauvegardes ou /mnt/sauvegardes)}"

command -v rsync >/dev/null || { echo "ERREUR: rsync introuvable."; exit 1; }

mapfile -t TOUTES < <(find "$BACKUP_DIR" -maxdepth 1 -mindepth 1 -type d -name '*-20*' | sort)
[ "${#TOUTES[@]}" -gt 0 ] || { echo "Rien a expedier dans ${BACKUP_DIR}."; exit 1; }

if [ "${EXPEDITION_ALL:-0}" = "1" ]; then
    DIRS=("${TOUTES[@]}")
else
    # La plus recente par base : le nom est <base>-<AAAAMMJJ>-<HHMMSS>,
    # la liste est triee, la derniere vue gagne.
    declare -A DERNIERE
    for d in "${TOUTES[@]}"; do
        nom="$(basename "$d")"
        DERNIERE["${nom%-*-*}"]="$d"
    done
    mapfile -t DIRS < <(printf '%s\n' "${DERNIERE[@]}" | sort)
fi

EXPEDIEES=0
for d in "${DIRS[@]}"; do
    nom="$(basename "$d")"
    echo "== ${nom}"
    if [ ! -f "${d}/SHA256SUMS" ]; then
        echo "ECHEC : ${nom} sans SHA256SUMS — archive non verifiee, non expediee."
        exit 1
    fi
    echo "  [1/3] Verification locale avant envoi..."
    if ! (cd "$d" && sha256sum -c --quiet SHA256SUMS); then
        echo "ECHEC : ${nom} ne se verifie plus — on n'exporte pas une corruption."
        exit 1
    fi
    echo "  [2/3] Copie vers ${DEST}..."
    rsync -a --exclude='EXPEDIEE' "$d" "${DEST}/"
    echo "  [3/3] Contre-verification bit a bit de la copie distante..."
    DERIVE="$(rsync -ai --checksum --dry-run --exclude='EXPEDIEE' "$d" "${DEST}/" | grep -v '/$' || true)"
    if [ -n "$DERIVE" ]; then
        echo "ECHEC : la copie distante de ${nom} differe :"
        echo "$DERIVE"
        exit 1
    fi
    printf '%s -> %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$DEST" >> "${d}/EXPEDIEE"
    EXPEDIEES=$((EXPEDIEES + 1))
    echo "  OK — copie conforme."
done
echo "OK — ${EXPEDIEES} archive(s) expediee(s) vers ${DEST}."
