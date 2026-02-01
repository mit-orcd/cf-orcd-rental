#!/usr/bin/env bash
#
# Script-based system test runner.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
common_init

CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/config/test_config.yaml}"
MODULE_FILTER=""
SKIP_LIST=""
OUTPUT_DIR_OVERRIDE=""
DRY_RUN="false"

usage() {
    cat << 'EOF'
Usage: run_workflow.sh [options]

Options:
  --config <path>      Path to test_config.yaml
  --module <name>      Run a single module (e.g., 01_users)
  --skip <list>        Comma-separated module names to skip
  --output-dir <path>  Output directory for artifacts
  --dry-run            Run in dry-run mode (module-defined)
  -h, --help           Show this help
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --module)
            MODULE_FILTER="$2"
            shift 2
            ;;
        --skip)
            SKIP_LIST="$2"
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

[ -f "$CONFIG_FILE" ] || die "Config file not found: $CONFIG_FILE"
ensure_yaml_support

if [ -n "$OUTPUT_DIR_OVERRIDE" ]; then
    OUTPUT_DIR="$OUTPUT_DIR_OVERRIDE"
    export OUTPUT_DIR
fi

BASE_URL="$(python3 - "$CONFIG_FILE" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

env = data.get("environment", {})
print(env.get("base_url", ""))
PY
)"
if [ -n "$BASE_URL" ]; then
    export BASE_URL
fi

MODULES_DIR="$SCRIPT_DIR/modules"
mkdir -p "$OUTPUT_DIR"

ensure_env
activate_env

read_modules() {
    if [ -n "$MODULE_FILTER" ]; then
        echo "$MODULE_FILTER"
        return 0
    fi
    yaml_list "$CONFIG_FILE" "modules.enabled"
}

is_skipped() {
    local name="$1"
    if [ -n "$SKIP_LIST" ]; then
        echo "$SKIP_LIST" | tr ',' '\n' | grep -Fxq "$name" && return 0
    fi
    yaml_list "$CONFIG_FILE" "modules.skip" | grep -Fxq "$name" && return 0
    return 1
}

log_step "Running workflow"

while read -r module_name; do
    [ -n "$module_name" ] || continue
    if is_skipped "$module_name"; then
        log_warn "Skipping module: $module_name"
        continue
    fi

    script_path="$MODULES_DIR/${module_name}.sh"
    [ -f "$script_path" ] || die "Module script not found: $script_path"

    log_step "Module: $module_name"
    if [ "$DRY_RUN" = "true" ]; then
        bash "$script_path" --config "$CONFIG_FILE" --output-dir "$OUTPUT_DIR" --dry-run
    else
        bash "$script_path" --config "$CONFIG_FILE" --output-dir "$OUTPUT_DIR"
    fi

    exit_code=$?
    if [ "$exit_code" -eq 2 ]; then
        log_warn "Module not implemented: $module_name (continuing)"
        continue
    fi
    if [ "$exit_code" -ne 0 ]; then
        exit "$exit_code"
    fi
done < <(read_modules)

echo ""
echo "Workflow complete. Outputs saved to: $OUTPUT_DIR"
