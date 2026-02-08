#!/usr/bin/env bash
#
# Module 06_1: Create Reservations (Submit as PENDING)
#
# Creates node rental reservations based on YAML config, setting
# them to PENDING status.  Each entry specifies a node, project,
# requesting user, start date, and duration in 12-hour blocks.
#
# This is stage 1 of the two-stage reservation workflow:
#   Stage 1 (this script): Submit reservations as PENDING
#   Stage 2 (06_2_confirm_reservations.sh): Approve as rental manager
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
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SETUP_DIR/lib/common.sh"
common_init

CONFIG_FILE="$SETUP_DIR/config/test_config.yaml"
OUTPUT_DIR_OVERRIDE=""
DRY_RUN="false"

usage() {
    cat << 'EOF'
Usage: 06_1_create_reservations.sh [options]
  --config <path>      Path to test_config.yaml
  --output-dir <path>  Output directory for artifacts
  --dry-run            Print actions without applying changes
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR_OVERRIDE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN="true"
            shift 1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown option: $1"
            ;;
    esac
done

ensure_yaml_support

if [ -n "$OUTPUT_DIR_OVERRIDE" ]; then
    OUTPUT_DIR="$OUTPUT_DIR_OVERRIDE"
fi

MODULE_OUTPUT="$OUTPUT_DIR/06_1_create_reservations"
mkdir -p "$MODULE_OUTPUT"

# ---------------------------------------------------------------------------
# Resolve the reservations config path from test_config.yaml includes
# ---------------------------------------------------------------------------

RESERV_CONFIG="$(python3 - "$CONFIG_FILE" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

includes = data.get("includes", {})
print(includes.get("reservations", ""))
PY
)"

if [ -z "$RESERV_CONFIG" ]; then
    die "reservations config path not found in test_config.yaml includes section"
fi

if [ ! -f "$SETUP_DIR/config/$RESERV_CONFIG" ]; then
    die "Reservations config not found: $SETUP_DIR/config/$RESERV_CONFIG"
fi

RESERV_CONFIG="$SETUP_DIR/config/$RESERV_CONFIG"

# ---------------------------------------------------------------------------
# Set up environment
# ---------------------------------------------------------------------------

ensure_env
activate_env

# ---------------------------------------------------------------------------
# Main loop: parse YAML, call create_node_rental for each entry
# ---------------------------------------------------------------------------

log_step "Creating reservations as PENDING"

RESERV_LOG="$MODULE_OUTPUT/create_reservations.log"
reserv_count=0

while IFS=$'\t' read -r node_address project username start_date num_blocks rental_notes; do
    [ -n "$node_address" ] || continue

    cmd=(create_node_rental "$node_address" "$project" "$username"
         --start-date "$start_date"
         --num-blocks "$num_blocks"
         --status PENDING
         --force)

    [ -n "$rental_notes" ] && cmd+=(--rental-notes "$rental_notes")

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] coldfront ${cmd[*]}" >> "$RESERV_LOG"
    else
        output="$(coldfront "${cmd[@]}" 2>&1)"
        printf "%s\n" "$output" >> "$RESERV_LOG"
    fi

    reserv_count=$((reserv_count + 1))

done < <(python3 - "$RESERV_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

defaults = data.get("defaults", {})
default_num_blocks = defaults.get("num_blocks", 2)

for entry in data.get("reservations", []):
    node_address = entry.get("node_address", "")
    project = entry.get("project", "")
    username = entry.get("requesting_user", "")
    start_date = entry.get("start_date", "")

    if not all([node_address, project, username, start_date]):
        continue

    num_blocks = entry.get("num_blocks", default_num_blocks)
    rental_notes = entry.get("rental_notes", "")

    line = "\t".join([
        str(node_address),
        str(project),
        str(username),
        str(start_date),
        str(num_blocks),
        str(rental_notes),
    ])
    print(line)
PY
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Module 06_1 complete."
echo "  Reservations created (PENDING): $reserv_count"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - create_reservations.log : Command output log"
echo ""
echo "Next step: run 06_2_confirm_reservations.sh to approve"
