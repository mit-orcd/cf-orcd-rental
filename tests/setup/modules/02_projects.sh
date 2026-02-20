#!/usr/bin/env bash
#
# Module 02: Projects
#
# Creates projects based on YAML config.
# Each project entry specifies a name and owner (username).
# Members are NOT handled here -- see 03_members.sh.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SETUP_DIR/lib/common.sh"
common_init

# Default config is projects.yaml
CONFIG_FILE="$SETUP_DIR/config/projects.yaml"

module_usage() {
    cat << 'EOF'
Usage: 02_projects.sh [options]
  --config <path>      Path to project YAML config file
  --output-dir <path>  Output directory for artifacts
  --dry-run            Print actions without applying changes
EOF
}

parse_module_args "$@"
init_module "02_projects"

PROJECTS_CONFIG=${CONFIG_FILE}
if [ ! -f "$CONFIG_FILE" ]; then
    die "Config file not found: $CONFIG_FILE"
fi

log_step "Creating projects from ${PROJECTS_CONFIG}"

CREATE_LOG="$MODULE_OUTPUT/create_projects.log"
python_cmd="$(get_python_cmd)"

while IFS=$'\t' read -r name owner created_date modified_date; do
    [ -n "$name" ] || continue

    cmd=(create_orcd_project "$owner" --project-name "$name" --force)

    if [ -n "$created_date" ]; then
        cmd+=(--created "$created_date")
    fi

    if [ -n "$modified_date" ]; then
        cmd+=(--modified "$modified_date")
    fi

    run_coldfront "$CREATE_LOG" "${cmd[@]}" >/dev/null

done < <($python_cmd - "$PROJECTS_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    projects = yaml.safe_load(f) or {}

for proj in projects.get("projects", []):
    name = proj.get("name", "")
    owner = proj.get("owner", "")
    created = str(proj.get("created", ""))
    modified = str(proj.get("modified", ""))
    print(f"{name}\t{owner}\t{created}\t{modified}")
PY
)

echo "Module 02 complete. Output: $MODULE_OUTPUT"
