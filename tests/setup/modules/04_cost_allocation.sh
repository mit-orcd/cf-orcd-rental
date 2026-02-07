#!/usr/bin/env bash
#
# Module 04: Cost Allocation
#
# Creates and approves cost allocations for projects based on YAML config.
# Each entry in the config specifies a project name, one or more cost objects
# (code + percentage, must sum to 100), and optional status/reviewer fields.
#
# The YAML config supports a `defaults` block so that common values (e.g.
# status=APPROVED, reviewed_by=orcd_bim) don't need to be repeated on
# every entry.
#
# Uses `coldfront set_project_cost_allocation` with --force so the module
# is idempotent on re-runs.
#
# Depends on:
#   - 01_1_multiusers.sh  (creates users including orcd_bim billing manager)
#   - 02_projects.sh      (creates the projects referenced in the config)
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
Usage: 04_cost_allocation.sh [options]
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

MODULE_OUTPUT="$OUTPUT_DIR/04_cost_allocation"
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

log_step "Setting cost allocations from YAML"

ALLOC_LOG="$MODULE_OUTPUT/set_cost_allocations.log"
alloc_count=0

while IFS=$'\t' read -r project co_args status reviewed_by review_notes notes; do
    [ -n "$project" ] || continue

    # Build the command array.  $co_args is space-separated CO:PCT pairs
    # and must be unquoted so word-splitting produces individual arguments.
    # shellcheck disable=SC2086
    cmd=(set_project_cost_allocation "$project" $co_args --force)

    [ -n "$status" ]       && cmd+=(--status "$status")
    [ -n "$reviewed_by" ]  && cmd+=(--reviewed-by "$reviewed_by")
    [ -n "$review_notes" ] && cmd+=(--review-notes "$review_notes")
    [ -n "$notes" ]        && cmd+=(--notes "$notes")

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

defaults = data.get("defaults", {})
default_status = defaults.get("status", "")
default_reviewed_by = defaults.get("reviewed_by", "")
default_review_notes = defaults.get("review_notes", "")

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

    # Per-entry values override defaults
    status = entry.get("status", default_status)
    reviewed_by = entry.get("reviewed_by", default_reviewed_by)
    review_notes = entry.get("review_notes", default_review_notes)
    notes = entry.get("notes", "")

    line = "\t".join([
        project,
        co_args,
        status,
        reviewed_by,
        review_notes,
        notes,
    ])
    print(line)
PY
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Module 04 complete."
echo "  Cost allocations set: $alloc_count"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - set_cost_allocations.log : Command output log"
