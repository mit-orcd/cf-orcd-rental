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

CONFIG_FILE="$SETUP_DIR/config/test_config.yaml"
OUTPUT_DIR_OVERRIDE=""
DRY_RUN="false"

usage() {
    cat << 'EOF'
Usage: 04_1_attach_cost_allocations.sh [options]
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

MODULE_OUTPUT="$OUTPUT_DIR/04_1_attach_cost_allocations"
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
# Main loop: parse YAML, call set_project_cost_allocation for each entry
# ---------------------------------------------------------------------------

log_step "Submitting cost allocations as PENDING"

ALLOC_LOG="$MODULE_OUTPUT/attach_cost_allocations.log"
alloc_count=0

while IFS=$'\t' read -r project co_args submitted_by notes; do
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

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] coldfront ${cmd[*]}" >> "$ALLOC_LOG"
    else
        output="$(coldfront "${cmd[@]}" 2>&1)"
        printf "%s\n" "$output" >> "$ALLOC_LOG"
    fi

    alloc_count=$((alloc_count + 1))

done < <(python3 - "$ALLOC_CONFIG" << 'PY'
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

    line = "\t".join([
        project,
        co_args,
        submitted_by,
        notes,
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
