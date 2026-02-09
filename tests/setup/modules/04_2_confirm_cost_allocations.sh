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

module_usage() {
    cat << 'EOF'
Usage: 04_2_confirm_cost_allocations.sh [options]
  --config <path>      Path to test_config.yaml
  --output-dir <path>  Output directory for artifacts
  --dry-run            Print actions without applying changes
EOF
}

parse_module_args "$@"
init_module "04_2_confirm_cost_allocations"

ALLOC_CONFIG="$(resolve_include "$CONFIG_FILE" "cost_allocations" "Cost allocations")"

# ---------------------------------------------------------------------------
# Read approval config from YAML
# ---------------------------------------------------------------------------

python_cmd="$(get_python_cmd)"

APPROVAL_ARGS="$($python_cmd - "$ALLOC_CONFIG" << 'PY'
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

    run_coldfront "$APPROVE_LOG" "${cmd[@]}" >/dev/null

    approve_count=$((approve_count + 1))

done < <($python_cmd - "$ALLOC_CONFIG" << 'PY'
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
