#!/usr/bin/env bash
# Enrobage : la verticale garage via le moteur generique init_prod.sh.
# (Le repertoire d'addons de cette verticale s'appelle « auto ».)
# Base par defaut : megga_auto_prod.
exec "$(dirname "${BASH_SOURCE[0]}")/init_prod.sh" auto "$@"
