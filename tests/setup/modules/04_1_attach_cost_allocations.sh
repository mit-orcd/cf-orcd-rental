#!/usr/bin/env bash
#
# Module 04_1: Attach Cost Allocations (Submit as PENDING)
#
# Creates cost allocations for projects based on YAML config, setting
# them to PENDING status.  Each entry specifies a project, cost objects,
# and the user who submits the allocation (project owner or financial
# admin).
#
# This is stage 1 of the two-stage cost allocation workflow:
#   Stage 1 (this script): Submit allocations as PENDING
#   Stage 2 (04_2_confirm_cost_allocations.sh): Approve as billing manager
#
# Uses `coldfront set_project_cost_allocation` with --force and
# --status PENDING so the module is idempotent on re-runs.
#
# Depends on:
#   - 01_1_multiusers.sh  (creates user accounts)
#   - 02_projects.sh      (creates the projects)
#   - 03_members.sh       (assigns financial admin roles)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SETUP_DIR/lib/common.sh"
common_init

module_usage() {
    cat << 'EOF'
Usage: 04_1_attach_cost_allocations.sh [options]
  --config <path>      Path to test_config.yaml
  --output-dir <path>  Output directory for artifacts
  --dry-run            Print actions without applying changes
EOF
}

parse_module_args "$@"
init_module "04_1_attach_cost_allocations"

ALLOC_CONFIG="$(resolve_include "$CONFIG_FILE" "cost_allocations" "Cost allocations")"

# ---------------------------------------------------------------------------
# Main loop: parse YAML, call set_project_cost_allocation for each entry
# ---------------------------------------------------------------------------

log_step "Submitting cost allocations as PENDING"

ALLOC_LOG="$MODULE_OUTPUT/attach_cost_allocations.log"
alloc_count=0
python_cmd="$(get_python_cmd)"

while IFS=$'\t' read -r project co_args submitted_by notes created_date modified_date; do
    [ -n "$project" ] || continue

    # Build the command array.  $co_args is space-separated CO:PCT pairs
    # and must be unquoted so word-splitting produces individual arguments.
    # shellcheck disable=SC2086
    cmd=(set_project_cost_allocation "$project" $co_args --force --status PENDING)

    # Include submitter in notes for audit trail
    if [ -n "$submitted_by" ] && [ -n "$notes" ]; then
        cmd+=(--notes "Submitted by $submitted_by: $notes")
    elif [ -n "$submitted_by" ]; then
        cmd+=(--notes "Submitted by $submitted_by")
    elif [ -n "$notes" ]; then
        cmd+=(--notes "$notes")
    fi

    if [ -n "$created_date" ]; then
        cmd+=(--created "$created_date")
    fi

    if [ -n "$modified_date" ]; then
        cmd+=(--modified "$modified_date")
    fi

    run_coldfront "$ALLOC_LOG" "${cmd[@]}" >/dev/null

    alloc_count=$((alloc_count + 1))

done < <($python_cmd - "$ALLOC_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

for entry in data.get("cost_allocations", []):
    project = entry.get("project", "")
    if not project:
        continue

    # Build space-separated CO:PCT string
    cost_objects = entry.get("cost_objects", [])
    co_args = " ".join(
        f"{co.get('code', '')}:{co.get('percentage', '')}"
        for co in cost_objects
    )

    submitted_by = entry.get("submitted_by", "")
    notes = entry.get("notes", "")
    created = str(entry.get("created", ""))
    modified = str(entry.get("modified", ""))

    line = "\t".join([
        project,
        co_args,
        submitted_by,
        notes,
        created,
        modified,
    ])
    print(line)
PY
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Module 04_1 complete."
echo "  Cost allocations submitted (PENDING): $alloc_count"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - attach_cost_allocations.log : Command output log"
echo ""
echo "Next step: run 04_2_confirm_cost_allocations.sh to approve"
