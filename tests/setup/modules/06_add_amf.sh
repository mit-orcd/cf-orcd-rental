#!/usr/bin/env bash
#
# Module 06: Account Maintenance Fees (AMF)
#
# Sets account maintenance fee status for each regular user based on
# YAML config.  Each entry specifies a user, their maintenance level
# (basic or advanced), and the project to charge for the service.
#
# Status levels:
#   basic    -> MAINT_STANDARD SKU  (standard maintenance)
#   advanced -> MAINT_ADVANCED SKU  (advanced maintenance)
#
# Uses `coldfront set_user_amf` with --force so the module is
# idempotent on re-runs.
#
# Depends on:
#   - 01_1_multiusers.sh               (creates user accounts)
#   - 02_projects.sh                   (creates the projects)
#   - 03_members.sh                    (assigns roles for eligibility)
#   - 04_1_attach_cost_allocations.sh  (submits cost allocations)
#   - 04_2_confirm_cost_allocations.sh (approves cost allocations)
#   - 05_rates.sh                      (sets SKU rates)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SETUP_DIR/lib/common.sh"
common_init

module_usage() {
    cat << 'EOF'
Usage: 06_add_amf.sh [options]
  --config <path>      Path to test_config.yaml
  --output-dir <path>  Output directory for artifacts
  --dry-run            Print actions without applying changes
EOF
}

parse_module_args "$@"
init_module "06_add_amf"

AMF_CONFIG="$(resolve_include "$CONFIG_FILE" "amf" "AMF")"

# ---------------------------------------------------------------------------
# Main loop: parse YAML, call set_user_amf for each entry
# ---------------------------------------------------------------------------

log_step "Setting account maintenance fees"

AMF_LOG="$MODULE_OUTPUT/add_amf.log"
amf_count=0
python_cmd="$(get_python_cmd)"

while IFS=$'\t' read -r username status project; do
    [ -n "$username" ] || continue

    run_coldfront "$AMF_LOG" set_user_amf "$username" "$status" --project "$project" --force >/dev/null

    amf_count=$((amf_count + 1))

done < <($python_cmd - "$AMF_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

defaults = data.get("defaults", {})
default_status = defaults.get("status", "basic")

for entry in data.get("entries", []):
    username = entry.get("username", "")
    project = entry.get("project", "")

    if not all([username, project]):
        continue

    status = entry.get("status", default_status)

    line = "\t".join([
        str(username),
        str(status),
        str(project),
    ])
    print(line)
PY
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Module 06 complete."
echo "  Account maintenance fees set: $amf_count"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - add_amf.log : Command output log"
