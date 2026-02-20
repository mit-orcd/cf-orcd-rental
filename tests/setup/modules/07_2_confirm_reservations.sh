#!/usr/bin/env bash
#
# Module 07_2: Confirm Reservations (Approve as Rental Manager)
#
# Approves all PENDING reservations using the rental manager
# account specified in the YAML config's `approval` section.
#
# This is stage 2 of the two-stage reservation workflow:
#   Stage 1 (07_1_create_reservations.sh): Submit reservations as PENDING
#   Stage 2 (this script): Approve as rental manager
#
# Uses `coldfront approve_node_rental` with --force so the module
# is idempotent on re-runs (re-approves already-approved reservations).
#
# Depends on:
#   - 01_1_multiusers.sh          (creates orcd_rem rental manager)
#   - 07_1_create_reservations.sh (creates PENDING reservations)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SETUP_DIR/lib/common.sh"
common_init

# Default config is reservations.yaml
CONFIG_FILE="$SETUP_DIR/config/reservations.yaml"

module_usage() {
    cat << 'EOF'
Usage: 07_2_confirm_reservations.sh [options]
  --config <path>      Path to test_config.yaml
  --output-dir <path>  Output directory for artifacts
  --dry-run            Print actions without applying changes
EOF
}

parse_module_args "$@"
init_module "07_2_confirm_reservations"

RESERV_CONFIG=${CONFIG_FILE}
if [ ! -f "$CONFIG_FILE" ]; then
    die "Config file not found: $CONFIG_FILE"
fi


# ---------------------------------------------------------------------------
# Read approval config from YAML
# ---------------------------------------------------------------------------

python_cmd="$(get_python_cmd)"

APPROVAL_ARGS="$($python_cmd - "$RESERV_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

approval = data.get("approval", {})
processed_by = approval.get("processed_by", "")
manager_notes = approval.get("manager_notes", "")

print(f"{processed_by}\t{manager_notes}")
PY
)"

PROCESSED_BY="$(echo "$APPROVAL_ARGS" | cut -f1)"
MANAGER_NOTES="$(echo "$APPROVAL_ARGS" | cut -f2)"

if [ -z "$PROCESSED_BY" ]; then
    die "approval.processed_by not found in reservations.yaml"
fi

# ---------------------------------------------------------------------------
# Main loop: approve each reservation
# ---------------------------------------------------------------------------

log_step "Approving reservations as rental manager ($PROCESSED_BY)"

APPROVE_LOG="$MODULE_OUTPUT/confirm_reservations.log"
approve_count=0

while IFS=$'\t' read -r node_address project start_date; do
    [ -n "$node_address" ] || continue

    # Resolve relative date expression (e.g. "today+7") to YYYY-MM-DD
    start_date="$(resolve_relative_date "$start_date")"

    cmd=(approve_node_rental "$node_address" "$project"
         --start-date "$start_date"
         --processed-by "$PROCESSED_BY"
         --force)

    [ -n "$MANAGER_NOTES" ] && cmd+=(--manager-notes "$MANAGER_NOTES")

    run_coldfront "$APPROVE_LOG" "${cmd[@]}" >/dev/null

    approve_count=$((approve_count + 1))

done < <($python_cmd - "$RESERV_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

for entry in data.get("reservations", []):
    node_address = entry.get("node_address", "")
    project = entry.get("project", "")
    start_date = entry.get("start_date", "")

    if not all([node_address, project, start_date]):
        continue

    print(f"{node_address}\t{project}\t{start_date}")
PY
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Module 07_2 complete."
echo "  Reservations approved: $approve_count"
echo "  Processed by: $PROCESSED_BY"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - confirm_reservations.log : Command output log"
