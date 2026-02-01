#!/usr/bin/env bash
#
# Module 03: Members (placeholder)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SETUP_DIR/lib/common.sh"
common_init

log_step "Module 03 not implemented yet"
echo "This module will manage project member roles from YAML."
exit 2
