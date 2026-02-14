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

module_usage() {
    cat << 'EOF'
Usage: 02_projects.sh [options]
  --config <path>      Path to test_config.yaml
  --output-dir <path>  Output directory for artifacts
  --dry-run            Print actions without applying changes
EOF
}

parse_module_args "$@"
init_module "02_projects"

PROJECTS_CONFIG="$(resolve_include "$CONFIG_FILE" "projects" "Projects")"

log_step "Creating projects from YAML"

CREATE_LOG="$MODULE_OUTPUT/create_projects.log"
python_cmd="$(get_python_cmd)"

while IFS=$'\t' read -r name owner; do
    [ -n "$name" ] || continue

    run_coldfront "$CREATE_LOG" create_orcd_project "$owner" --project-name "$name" --force >/dev/null

done < <($python_cmd - "$PROJECTS_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    projects = yaml.safe_load(f) or {}

for proj in projects.get("projects", []):
    name = proj.get("name", "")
    owner = proj.get("owner", "")
    print(f"{name}\t{owner}")
PY
)

echo "Module 02 complete. Output: $MODULE_OUTPUT"
