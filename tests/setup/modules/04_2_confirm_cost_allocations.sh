#!/usr/bin/env bash
#
# Module 04_2: Confirm Cost Allocations (Approve as Billing Manager)
#
# Approves all PENDING cost allocations using the billing manager
# account specified in the YAML config's `approval` section.
#
# This is stage 2 of the two-stage cost allocation workflow:
#   Stage 1 (04_1_attach_cost_allocations.sh): Submit allocations as PENDING
#   Stage 2 (this script): Approve as billing manager
#
# Uses `coldfront approve_cost_allocation` with --force so the module
# is idempotent on re-runs (re-approves already-approved allocations).
#
# Depends on:
#   - 01_1_multiusers.sh  (creates orcd_bim billing manager)
#   - 04_1_attach_cost_allocations.sh  (creates PENDING allocations)
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
Usage: 04_2_confirm_cost_allocations.sh [options]
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

MODULE_OUTPUT="$OUTPUT_DIR/04_2_confirm_cost_allocations"
mkdir -p "$MODULE_OUTPUT"

# ---------------------------------------------------------------------------
# Resolve the cost_allocations config path from test_config.yaml includes
# ---------------------------------------------------------------------------

ALLOC_CONFIG="$(python3 - "$CONFIG_FILE" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

includes = data.get("includes", {})
print(includes.get("cost_allocations", ""))
PY
)"

if [ -z "$ALLOC_CONFIG" ]; then
    die "cost_allocations config path not found in test_config.yaml includes section"
fi

if [ ! -f "$SETUP_DIR/config/$ALLOC_CONFIG" ]; then
    die "Cost allocations config not found: $SETUP_DIR/config/$ALLOC_CONFIG"
fi

ALLOC_CONFIG="$SETUP_DIR/config/$ALLOC_CONFIG"

# ---------------------------------------------------------------------------
# Set up environment
# ---------------------------------------------------------------------------

ensure_env
activate_env

# ---------------------------------------------------------------------------
# Read approval config from YAML
# ---------------------------------------------------------------------------

APPROVAL_ARGS="$(python3 - "$ALLOC_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

approval = data.get("approval", {})
reviewed_by = approval.get("reviewed_by", "")
review_notes = approval.get("review_notes", "")

print(f"{reviewed_by}\t{review_notes}")
PY
)"

REVIEWED_BY="$(echo "$APPROVAL_ARGS" | cut -f1)"
REVIEW_NOTES="$(echo "$APPROVAL_ARGS" | cut -f2)"

if [ -z "$REVIEWED_BY" ]; then
    die "approval.reviewed_by not found in cost_allocations.yaml"
fi

# ---------------------------------------------------------------------------
# Main loop: approve each project's cost allocation
# ---------------------------------------------------------------------------

log_step "Approving cost allocations as billing manager ($REVIEWED_BY)"

APPROVE_LOG="$MODULE_OUTPUT/confirm_cost_allocations.log"
approve_count=0

while IFS=$'\t' read -r project; do
    [ -n "$project" ] || continue

    cmd=(approve_cost_allocation "$project" --reviewed-by "$REVIEWED_BY" --force)

    [ -n "$REVIEW_NOTES" ] && cmd+=(--review-notes "$REVIEW_NOTES")

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] coldfront ${cmd[*]}" >> "$APPROVE_LOG"
    else
        output="$(coldfront "${cmd[@]}" 2>&1)"
        printf "%s\n" "$output" >> "$APPROVE_LOG"
    fi

    approve_count=$((approve_count + 1))

done < <(python3 - "$ALLOC_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

for entry in data.get("cost_allocations", []):
    project = entry.get("project", "")
    if project:
        print(project)
PY
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Module 04_2 complete."
echo "  Cost allocations approved: $approve_count"
echo "  Reviewed by: $REVIEWED_BY"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - confirm_cost_allocations.log : Command output log"
