#!/usr/bin/env bash
#
# Module 03: Members
#
# Adds non-owner users to projects with specified ORCD roles based on
# YAML config.  Each entry in the config maps to a single call to
# `coldfront add_user_to_project`.
#
# ORCD Roles:
#   financial_admin - Can manage cost allocations and all roles
#   technical_admin - Can manage members, included in reservations
#   member          - Can create reservations, included in billing
#
# A user may hold multiple roles in the same project (each is a
# separate YAML entry and a separate management command call).
# The project owner (PI) cannot be added -- the command enforces this.
#
# Uses --force so the module is idempotent on re-runs.
#
# Depends on:
#   - 01_1_multiusers.sh  (creates the user accounts)
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
Usage: 03_members.sh [options]
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

MODULE_OUTPUT="$OUTPUT_DIR/03_members"
mkdir -p "$MODULE_OUTPUT"

# ---------------------------------------------------------------------------
# Resolve the members config path from test_config.yaml includes
# ---------------------------------------------------------------------------

MEMBERS_CONFIG="$(python3 - "$CONFIG_FILE" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

includes = data.get("includes", {})
print(includes.get("members", ""))
PY
)"

if [ -z "$MEMBERS_CONFIG" ]; then
    die "members config path not found in test_config.yaml includes section"
fi

if [ ! -f "$SETUP_DIR/config/$MEMBERS_CONFIG" ]; then
    die "Members config not found: $SETUP_DIR/config/$MEMBERS_CONFIG"
fi

MEMBERS_CONFIG="$SETUP_DIR/config/$MEMBERS_CONFIG"

# ---------------------------------------------------------------------------
# Set up environment
# ---------------------------------------------------------------------------

ensure_env
activate_env

# ---------------------------------------------------------------------------
# Main loop: parse YAML, call add_user_to_project for each entry
# ---------------------------------------------------------------------------

log_step "Adding project members from YAML"

MEMBER_LOG="$MODULE_OUTPUT/add_members.log"
member_count=0

while IFS=$'\t' read -r username project role; do
    [ -n "$username" ] || continue

    cmd=(add_user_to_project "$username" "$project" --role "$role" --force)

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] coldfront ${cmd[*]}" >> "$MEMBER_LOG"
    else
        output="$(coldfront "${cmd[@]}" 2>&1)"
        printf "%s\n" "$output" >> "$MEMBER_LOG"
    fi

    member_count=$((member_count + 1))

done < <(python3 - "$MEMBERS_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

for entry in data.get("members", []):
    username = entry.get("username", "")
    project = entry.get("project", "")
    role = entry.get("role", "")

    if not username or not project or not role:
        continue

    line = "\t".join([username, project, role])
    print(line)
PY
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Module 03 complete."
echo "  Member roles assigned: $member_count"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - add_members.log : Command output log"
