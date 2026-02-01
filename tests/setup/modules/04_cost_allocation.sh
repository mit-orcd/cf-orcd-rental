#!/usr/bin/env bash
#
# Module 04: Cost Allocation (placeholder)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SETUP_DIR/lib/common.sh"
common_init

log_step "Module 04 not implemented yet"
echo "This module will create and approve cost allocations from YAML."
exit 2
