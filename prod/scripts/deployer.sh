#!/usr/bin/env bash
# Amorce un VRAI serveur (Debian 12 / Ubuntu 24.04, root) : du VPS nu au
# stack Megga durci, en un passage. Idempotent la ou c'est possible : un
# .env existant n'est jamais ecrase, une base existante jamais touchee
# (garde d'init_prod.sh).
#
#   DOMAINE=erp.moncabinet.ch COURRIEL=admin@moncabinet.ch \
#   VERTICALE=dental bash prod/scripts/deployer.sh
#
# Variables :
#   VERTICALE  dental | resto | auto            (defaut : dental)
#   DOMAINE    nom DNS pointant sur ce serveur  (sans lui : certificat
#              auto-signe, pour un essai seulement)
#   COURRIEL   contact Let's Encrypt            (requis avec DOMAINE)
#   DEPOT      URL git du produit  (defaut : https://github.com/megga/megga-erp.git)
#
# Derriere Cloudflare Tunnel (aucun port entrant) : pas de DOMAINE ici —
# le tunnel amene le trafic a nginx ; voir le runbook, section Cloudflare.
set -euo pipefail

VERTICALE="${VERTICALE:-dental}"
DEPOT="${DEPOT:-https://github.com/megga/megga-erp.git}"
case "$VERTICALE" in
    dental) INIT=init_dentaire.sh ;;
    resto)  INIT=init_resto.sh ;;
    auto)   INIT=init_garage.sh ;;
    *) echo "ERREUR: VERTICALE=$VERTICALE inconnue (dental|resto|auto)"; exit 1 ;;
esac
[ "$(id -u)" = "0" ] || { echo "ERREUR: a lancer en root (VPS neuf)."; exit 1; }
command -v apt-get >/dev/null || { echo "ERREUR: Debian/Ubuntu attendu (apt)."; exit 1; }

echo "[1/6] Outils de base et Docker..."
apt-get update -qq
apt-get install -y -qq git openssl curl ca-certificates rsync >/dev/null
if ! command -v docker >/dev/null; then
    curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null || { echo "ERREUR: docker compose absent."; exit 1; }

echo "[2/6] Depot produit et sous-module du coeur..."
if [ -f docker-compose.prod.yml ] && [ -d ../addons ]; then
    RACINE="$(cd .. && pwd)"                     # lance depuis prod/
elif [ -f prod/docker-compose.prod.yml ]; then
    RACINE="$(pwd)"                              # lance depuis la racine
else
    RACINE=/opt/megga-erp
    [ -d "$RACINE/.git" ] || git clone "$DEPOT" "$RACINE"
fi
cd "$RACINE"
git submodule update --init --depth 1 odoo

echo "[3/6] Secrets (.env) — jamais ecrases s'ils existent..."
cd "$RACINE/prod"
if [ ! -f .env ]; then
    {
        echo "POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '=+/')"
        echo "ODOO_ADMIN_PASSWD=$(openssl rand -base64 24 | tr -d '=+/')"
        echo "ODOO_DB_NAME=megga_${VERTICALE}_prod"
        echo "ODOO_WORKERS=$(( $(nproc) * 2 + 1 ))"
        echo "BACKUP_RETENTION_DAYS=30"
    } > .env
    chmod 600 .env
    echo "  .env genere (chmod 600). Copiez ODOO_ADMIN_PASSWD en lieu sur."
else
    echo "  .env existant conserve."
fi

echo "[4/6] Certificat TLS..."
mkdir -p certs
if [ -f certs/fullchain.pem ]; then
    echo "  certificats existants conserves."
elif [ -n "${DOMAINE:-}" ]; then
    : "${COURRIEL:?COURRIEL requis avec DOMAINE (contact ACME/Lets Encrypt)}"
    apt-get install -y -qq certbot >/dev/null
    # nginx n'est pas encore lance : le defi standalone peut prendre le port 80.
    certbot certonly --standalone --non-interactive --agree-tos \
        -m "$COURRIEL" -d "$DOMAINE"
    ln -sf "/etc/letsencrypt/live/${DOMAINE}/fullchain.pem" certs/fullchain.pem
    ln -sf "/etc/letsencrypt/live/${DOMAINE}/privkey.pem"  certs/privkey.pem
    # Renouvellement : certbot pose son timer systemd ; recharger nginx apres.
    mkdir -p /etc/letsencrypt/renewal-hooks/deploy
    printf '#!/bin/sh\ncd %s && docker compose -f docker-compose.prod.yml restart nginx\n' \
        "$RACINE/prod" > /etc/letsencrypt/renewal-hooks/deploy/megga-nginx.sh
    chmod +x /etc/letsencrypt/renewal-hooks/deploy/megga-nginx.sh
else
    echo "  ATTENTION : pas de DOMAINE — certificat auto-signe (essai seulement)."
    openssl req -x509 -newkey rsa:2048 -nodes -days 90 \
        -subj "/CN=$(hostname -f)" \
        -keyout certs/privkey.pem -out certs/fullchain.pem 2>/dev/null
fi
chmod 600 certs/privkey.pem 2>/dev/null || true

echo "[5/6] Lancement du stack..."
docker compose -f docker-compose.prod.yml up -d --build
for i in $(seq 1 60); do
    code=$(curl -sk -o /dev/null -w '%{http_code}' -m 3 https://localhost/web/database/manager || true)
    [ "$code" = "404" ] && break
    sleep 5
done
[ "$code" = "404" ] || { echo "ERREUR: nginx ne repond pas comme attendu (manager=$code)."; exit 1; }
echo "  nginx en TLS, gestionnaire de bases neutralise (404) — posture conforme."

echo "[6/6] Initialisation de la base ${VERTICALE} (garde : jamais une base existante)..."
ADMIN_PASSWORD="$(openssl rand -base64 18 | tr -d '=+/')"
if docker compose -f docker-compose.prod.yml exec -T \
        -e ADMIN_PASSWORD="$ADMIN_PASSWORD" \
        -e ODOO_RC=/tmp/odoo.runtime.conf \
        erp bash "/scripts/${INIT}"; then
    echo
    echo "================================================================"
    echo "Serveur pret."
    [ -n "${DOMAINE:-}" ] && echo "  URL           : https://${DOMAINE}"
    echo "  Compte admin  : admin / ${ADMIN_PASSWORD}"
    echo "  (a changer a la premiere connexion ; le master password est"
    echo "   dans prod/.env — ODOO_ADMIN_PASSWD)"
    echo "  Reste a faire : checklist de premier jour (societe, IBAN QR,"
    echo "  utilisateurs et roles, catalogue metier), et l'expedition des"
    echo "  sauvegardes hors de l'hote (expedier.sh + timer, runbook)."
    echo "================================================================"
else
    echo "Initialisation refusee ou echouee — si la base existe deja, c'est"
    echo "la garde anti-ecrasement : le stack tourne, rien n'a ete touche."
fi
