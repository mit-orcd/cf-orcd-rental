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

CONFIG_FILE="$SETUP_DIR/config/test_config.yaml"
OUTPUT_DIR_OVERRIDE=""
DRY_RUN="false"

usage() {
    cat << 'EOF'
Usage: 02_projects.sh [options]
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

MODULE_OUTPUT="$OUTPUT_DIR/02_projects"
mkdir -p "$MODULE_OUTPUT"

PROJECTS_CONFIG="$(python3 - "$CONFIG_FILE" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

includes = data.get("includes", {})
print(includes.get("projects", ""))
PY
)"

if [ -z "$PROJECTS_CONFIG" ]; then
    die "projects config path not found in test_config.yaml includes section"
fi

if [ ! -f "$SETUP_DIR/config/$PROJECTS_CONFIG" ]; then
    die "Projects config not found: $SETUP_DIR/config/$PROJECTS_CONFIG"
fi

PROJECTS_CONFIG="$SETUP_DIR/config/$PROJECTS_CONFIG"

ensure_env
activate_env

log_step "Creating projects from YAML"

CREATE_LOG="$MODULE_OUTPUT/create_projects.log"

while IFS=$'\t' read -r name owner; do
    [ -n "$name" ] || continue

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] create_orcd_project $owner --project-name \"$name\"" >> "$CREATE_LOG"
        continue
    fi

    output="$(coldfront create_orcd_project "$owner" --project-name "$name" --force 2>&1)"
    printf "%s\n" "$output" >> "$CREATE_LOG"
done < <(python3 - "$PROJECTS_CONFIG" << 'PY'
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
