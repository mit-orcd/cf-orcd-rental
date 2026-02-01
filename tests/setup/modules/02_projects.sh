#!/usr/bin/env bash
#
# Module 02: Projects
#
# Creates projects and assigns members based on YAML config.
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

CONFIG_PATHS="$(python3 - "$CONFIG_FILE" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

includes = data.get("includes", {})
print("{}|{}".format(includes.get("projects", ""), includes.get("users", "")))
PY
)"

PROJECTS_CONFIG="${CONFIG_PATHS%%|*}"
USERS_CONFIG="${CONFIG_PATHS#*|}"

if [ -z "$PROJECTS_CONFIG" ] || [ -z "$USERS_CONFIG" ]; then
    die "projects/users config paths not found in test_config.yaml includes section"
fi

if [ ! -f "$SETUP_DIR/config/$PROJECTS_CONFIG" ]; then
    die "Projects config not found: $SETUP_DIR/config/$PROJECTS_CONFIG"
fi
if [ ! -f "$SETUP_DIR/config/$USERS_CONFIG" ]; then
    die "Users config not found: $SETUP_DIR/config/$USERS_CONFIG"
fi

PROJECTS_CONFIG="$SETUP_DIR/config/$PROJECTS_CONFIG"
USERS_CONFIG="$SETUP_DIR/config/$USERS_CONFIG"

ensure_env
activate_env

log_step "Creating projects from YAML"

CREATE_LOG="$MODULE_OUTPUT/create_projects.log"

while IFS=$'\t' read -r name description owner_username members; do
    [ -n "$name" ] || continue

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] create_orcd_project $owner_username --project-name \"$name\"" >> "$CREATE_LOG"
        continue
    fi

    cmd=(create_orcd_project "$owner_username" --project-name "$name" --force)
    [ -n "$description" ] && cmd+=(--description "$description")

    if [ -n "$members" ]; then
        IFS=',' read -r -a member_list <<< "$members"
        for member in "${member_list[@]}"; do
            [ -n "$member" ] && cmd+=(--add-member "$member")
        done
    fi

    output="$(coldfront "${cmd[@]}" 2>&1)"
    printf "%s\n" "$output" >> "$CREATE_LOG"
done < <(python3 - "$PROJECTS_CONFIG" "$USERS_CONFIG" << 'PY'
import sys
import yaml

projects_path = sys.argv[1]
users_path = sys.argv[2]

with open(projects_path, "r", encoding="utf-8") as f:
    projects = yaml.safe_load(f) or {}
with open(users_path, "r", encoding="utf-8") as f:
    users_data = yaml.safe_load(f) or {}

user_map = {}
for u in users_data.get("managers", []):
    user_map[u.get("id")] = u.get("username")
for u in users_data.get("users", []):
    user_map[u.get("id")] = u.get("username")

def resolve_user(user_id):
    return user_map.get(user_id, user_id)

for proj in projects.get("projects", []):
    name = proj.get("name", "")
    description = proj.get("description", "")
    owner = resolve_user(proj.get("owner", ""))
    members = []
    for m in proj.get("members", []):
        member_user = resolve_user(m.get("user_id", ""))
        role = m.get("role", "member")
        if member_user:
            members.append(f"{member_user}:{role}")
    print("\t".join([name, description, owner, ",".join(members)]))
PY
)

echo "Module 02 complete. Output: $MODULE_OUTPUT"
