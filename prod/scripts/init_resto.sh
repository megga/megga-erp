#!/usr/bin/env bash
# Enrobage : la verticale restaurant via le moteur generique init_prod.sh.
# Base par defaut : megga_resto_prod.
exec "$(dirname "${BASH_SOURCE[0]}")/init_prod.sh" resto "$@"
