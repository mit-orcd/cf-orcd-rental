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

module_usage() {
    cat << 'EOF'
Usage: 03_members.sh [options]
  --config <path>      Path to test_config.yaml
  --output-dir <path>  Output directory for artifacts
  --dry-run            Print actions without applying changes
EOF
}

parse_module_args "$@"
init_module "03_members"

MEMBERS_CONFIG="$(resolve_include "$CONFIG_FILE" "members" "Members")"

# ---------------------------------------------------------------------------
# Main loop: parse YAML, call add_user_to_project for each entry
# ---------------------------------------------------------------------------

log_step "Adding project members from YAML"

MEMBER_LOG="$MODULE_OUTPUT/add_members.log"
member_count=0
python_cmd="$(get_python_cmd)"

while IFS=$'\t' read -r username project role created_date modified_date; do
    [ -n "$username" ] || continue

    cmd=(add_user_to_project "$username" "$project" --role "$role" --force)

    if [ -n "$created_date" ]; then
        cmd+=(--created "$created_date")
    fi

    if [ -n "$modified_date" ]; then
        cmd+=(--modified "$modified_date")
    fi

    run_coldfront "$MEMBER_LOG" "${cmd[@]}" >/dev/null

    member_count=$((member_count + 1))

done < <($python_cmd - "$MEMBERS_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

for entry in data.get("members", []):
    username = entry.get("username", "")
    project = entry.get("project", "")
    role = entry.get("role", "")
    created = str(entry.get("created", ""))
    modified = str(entry.get("modified", ""))

    if not username or not project or not role:
        continue

    line = "\t".join([username, project, role, created, modified])
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
