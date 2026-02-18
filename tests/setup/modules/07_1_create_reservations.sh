#!/usr/bin/env bash
#
# Module 07_1: Create Reservations (Submit as PENDING)
#
# Creates node rental reservations based on YAML config, setting
# them to PENDING status.  Each entry specifies a node, project,
# requesting user, start date, and duration in 12-hour blocks.
#
# This is stage 1 of the two-stage reservation workflow:
#   Stage 1 (this script): Submit reservations as PENDING
#   Stage 2 (07_2_confirm_reservations.sh): Approve as rental manager
#
# Uses `coldfront create_node_rental` with --force and --status PENDING
# so the module is idempotent on re-runs.
#
# Depends on:
#   - 01_1_multiusers.sh               (creates user accounts)
#   - 02_projects.sh                   (creates the projects)
#   - 03_members.sh                    (assigns technical admin roles)
#   - 04_1_attach_cost_allocations.sh  (submits cost allocations)
#   - 04_2_confirm_cost_allocations.sh (approves cost allocations)
#   - 06_add_amf.sh                    (sets account maintenance fees)
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
Usage: 07_1_create_reservations.sh [options]
  --config <path>      Path to test_config.yaml
  --output-dir <path>  Output directory for artifacts
  --dry-run            Print actions without applying changes
EOF
}

parse_module_args "$@"
init_module "07_1_create_reservations"

RESERV_CONFIG=${CONFIG_FILE}
if [ ! -f "$CONFIG_FILE" ]; then
    die "Config file not found: $CONFIG_FILE"
fi


# ---------------------------------------------------------------------------
# Main loop: parse YAML, call create_node_rental for each entry
# ---------------------------------------------------------------------------

log_step "Creating reservations as PENDING"

RESERV_LOG="$MODULE_OUTPUT/create_reservations.log"
reserv_count=0
python_cmd="$(get_python_cmd)"

while IFS=$'\t' read -r node_address project username start_date end_date rental_notes; do
    [ -n "$node_address" ] || continue

    # Resolve relative date expression (e.g. "today+7") to YYYY-MM-DD
    start_date="$(resolve_relative_date "$start_date")"
    end_date="$(resolve_relative_date "$end_date")"

    cmd=(create_node_rental "$node_address" "$project" "$username"
         --start-date "$start_date"
         --end-date "$end_date"
         --status PENDING
         --force)

    [ -n "$rental_notes" ] && cmd+=(--rental-notes "$rental_notes")

    run_coldfront "$RESERV_LOG" "${cmd[@]}" >/dev/null

    reserv_count=$((reserv_count + 1))

done < <($python_cmd - "$RESERV_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

defaults = data.get("defaults", {})

for entry in data.get("reservations", []):
    node_address = entry.get("node_address", "")
    project = entry.get("project", "")
    username = entry.get("requesting_user", "")
    start_date = entry.get("start_date", "")
    end_date = entry.get("end_date", "")

    if not all([node_address, project, username, start_date, end_date]):
        continue

    rental_notes = entry.get("rental_notes", "")

    line = "\t".join([
        str(node_address),
        str(project),
        str(username),
        str(start_date),
        str(end_date),
        str(rental_notes),
    ])
    print(line)
PY
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Module 07_1 complete."
echo "  Reservations created (PENDING): $reserv_count"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - create_reservations.log : Command output log"
echo ""
echo "Next step: run 07_2_confirm_reservations.sh to approve"
