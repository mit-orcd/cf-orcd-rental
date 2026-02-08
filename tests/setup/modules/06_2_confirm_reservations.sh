#!/usr/bin/env bash
#
# Module 06_2: Confirm Reservations (Approve as Rental Manager)
#
# Approves all PENDING reservations using the rental manager
# account specified in the YAML config's `approval` section.
#
# This is stage 2 of the two-stage reservation workflow:
#   Stage 1 (06_1_create_reservations.sh): Submit reservations as PENDING
#   Stage 2 (this script): Approve as rental manager
#
# Uses `coldfront approve_node_rental` with --force so the module
# is idempotent on re-runs (re-approves already-approved reservations).
#
# Depends on:
#   - 01_1_multiusers.sh          (creates orcd_rem rental manager)
#   - 06_1_create_reservations.sh (creates PENDING reservations)
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
Usage: 06_2_confirm_reservations.sh [options]
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

MODULE_OUTPUT="$OUTPUT_DIR/06_2_confirm_reservations"
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
# Read approval config from YAML
# ---------------------------------------------------------------------------

APPROVAL_ARGS="$(python3 - "$RESERV_CONFIG" << 'PY'
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

    cmd=(approve_node_rental "$node_address" "$project"
         --start-date "$start_date"
         --processed-by "$PROCESSED_BY"
         --force)

    [ -n "$MANAGER_NOTES" ] && cmd+=(--manager-notes "$MANAGER_NOTES")

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] coldfront ${cmd[*]}" >> "$APPROVE_LOG"
    else
        output="$(coldfront "${cmd[@]}" 2>&1)"
        printf "%s\n" "$output" >> "$APPROVE_LOG"
    fi

    approve_count=$((approve_count + 1))

done < <(python3 - "$RESERV_CONFIG" << 'PY'
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
echo "Module 06_2 complete."
echo "  Reservations approved: $approve_count"
echo "  Processed by: $PROCESSED_BY"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - confirm_reservations.log : Command output log"
