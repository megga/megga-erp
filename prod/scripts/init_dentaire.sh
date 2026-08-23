#!/usr/bin/env bash
# Enrobage : la verticale dentaire via le moteur generique init_prod.sh.
# Conserve la base par defaut historique « megga_prod ».
exec "$(dirname "${BASH_SOURCE[0]}")/init_prod.sh" dental "${1:-megga_prod}"
