#!/usr/bin/env bash
#
# Common helpers for setup/module scripts.
#
set -euo pipefail

common_init() {
    local lib_dir
    lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SETUP_DIR="$(cd "$lib_dir/.." && pwd)"
    PLUGIN_DIR="$(cd "$SETUP_DIR/../.." && pwd)"
    WORKSPACE="${WORKSPACE:-$(dirname "$PLUGIN_DIR")}"
    COLDFRONT_DIR="${COLDFRONT_DIR:-$WORKSPACE/coldfront}"
    SERVER_PORT="${SERVER_PORT:-8000}"
    RUNNER_TYPE="${RUNNER_TYPE:-local}"
    USE_UV="${USE_UV:-true}"
    OUTPUT_DIR="${OUTPUT_DIR:-$SETUP_DIR/output}"
    export SETUP_DIR PLUGIN_DIR WORKSPACE COLDFRONT_DIR SERVER_PORT RUNNER_TYPE USE_UV OUTPUT_DIR
}

log_step() {
    echo ""
    echo "==> $1"
    echo ""
}

log_warn() {
    echo "Warning: $1"
}

die() {
    echo "ERROR: $1"
    exit 1
}

db_exists() {
    [ -f "$COLDFRONT_DIR/coldfront.db" ] || [ -f "$COLDFRONT_DIR/db.sqlite3" ]
}

# Get the Python command that has access to installed packages (pyyaml, etc.)
# This checks for the coldfront virtualenv first, then falls back to uv run or system python
get_python_cmd() {
    # Check if coldfront virtualenv exists and has python
    if [ -f "${COLDFRONT_DIR:-.}/.venv/bin/python3" ]; then
        echo "${COLDFRONT_DIR}/.venv/bin/python3"
    elif [ "${USE_UV:-true}" = "true" ] && command -v uv >/dev/null 2>&1 && [ -f "${PLUGIN_DIR:-$PWD}/pyproject.toml" ]; then
        # Use uv run from the plugin directory (which has pyyaml as a dependency)
        echo "uv run --directory ${PLUGIN_DIR:-$PWD} python3"
    else
        echo "python3"
    fi
}

ensure_yaml_support() {
    local python_cmd
    python_cmd="$(get_python_cmd)"
    
    $python_cmd - << 'PY'
try:
    import yaml  # noqa: F401
except Exception:
    raise SystemExit("PyYAML is required for YAML-driven scripts. Install with: pip install pyyaml")
PY
}

yaml_list() {
    local file="$1"
    local path="$2"
    local python_cmd
    python_cmd="$(get_python_cmd)"
    $python_cmd - "$file" "$path" << 'PY'
import json
import sys
import yaml

path = sys.argv[2]
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

node = data
for part in path.split("."):
    if isinstance(node, dict) and part in node:
        node = node[part]
    else:
        node = None
        break

if node is None:
    sys.exit(0)

if not isinstance(node, list):
    node = [node]

for item in node:
    if isinstance(item, (dict, list)):
        print(json.dumps(item))
    else:
        print(item)
PY
}

# Resolve a relative date expression to YYYY-MM-DD.
#
# Supported formats:
#   "2026-03-02"       -> passthrough (absolute date)
#   "today"            -> current date
#   "today+7"          -> 7 days from today
#   "today + 7"        -> 7 days from today (spaces allowed)
#   "today + 7 days"   -> 7 days from today ("days" suffix allowed)
#
# Uses Python for portability (macOS date -v vs Linux date -d).
resolve_relative_date() {
    local expr="$1"
    local python_cmd
    python_cmd="$(get_python_cmd)"
    $python_cmd -c "
from datetime import date, timedelta
import re, sys
s = sys.argv[1].strip()
# Absolute date passthrough (YYYY-MM-DD)
if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
    print(s)
# 'today' alone
elif s.lower() == 'today':
    print(date.today().isoformat())
# 'today+N' or 'today + N' or 'today + N days'
else:
    m = re.fullmatch(r'today\s*\+\s*(\d+)(?:\s*days?)?', s, re.IGNORECASE)
    if m:
        print((date.today() + timedelta(days=int(m.group(1)))).isoformat())
    else:
        print(f'Invalid date expression: {s}', file=sys.stderr)
        sys.exit(1)
" "$expr"
}

server_ready() {
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${SERVER_PORT}/" || true)
    [[ "$code" =~ ^[23] ]]
}

wait_for_server() {
    local max_wait="${1:-60}"
    local waited=0
    while [ $waited -lt "$max_wait" ]; do
        if server_ready; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 1
}

start_server_if_needed() {
    local server_log="$1"
    local pid_file="$2"

    if server_ready; then
        if [ -f /tmp/coldfront_server.log ]; then
            cp /tmp/coldfront_server.log "$server_log" || true
        fi
        return 0
    fi

    nohup coldfront runserver "0.0.0.0:${SERVER_PORT}" > "$server_log" 2>&1 &
    echo "$!" > "$pid_file"
    wait_for_server 60 || die "Server did not become ready"
}

ensure_env() {
    if [ "${CF_ENV_READY:-}" = "1" ]; then
        return 0
    fi

    local auto_skip="false"
    if db_exists; then
        auto_skip="true"
    fi

    local skip_init="${SKIP_INIT:-$auto_skip}"

    RUNNER_TYPE="$RUNNER_TYPE" \
    WORKSPACE="$WORKSPACE" \
    USE_UV="$USE_UV" \
    SKIP_SERVER="true" \
    SKIP_INIT="$skip_init" \
    "$SETUP_DIR/setup_environment.sh"

    export CF_ENV_READY=1
}

activate_env() {
    if [ "${CF_ENV_ACTIVATED:-}" = "1" ]; then
        return 0
    fi

    [ -f "$COLDFRONT_DIR/activate_env.sh" ] || die "activate_env.sh not found at $COLDFRONT_DIR/activate_env.sh"
    # shellcheck disable=SC1090
    source "$COLDFRONT_DIR/activate_env.sh"
    export PLUGIN_API="true"
    coldfront migrate --no-input
    export CF_ENV_ACTIVATED=1
}

extract_api_token() {
    sed -n 's/.*API Token: *//p' | tail -n 1 | tr -d '\r'
}

api_get() {
    local url="$1"
    local token="$2"
    local out="$3"
    curl -sS \
        -H "Authorization: Token ${token}" \
        -H "Accept: application/json" \
        -o "$out" \
        -w "%{http_code}" \
        "$url"
}

pretty_json() {
    local raw="$1"
    local pretty="$2"
    local python_cmd
    python_cmd="$(get_python_cmd)"
    $python_cmd -m json.tool "$raw" > "$pretty"
}

# ---------------------------------------------------------------------------
# Module helpers -- shared boilerplate for modules/ scripts
# ---------------------------------------------------------------------------

# Parse standard module CLI arguments.
# Sets globals: CONFIG_FILE, DRY_RUN, OUTPUT_DIR (if --output-dir given).
#
# Each module script must define a module_usage() function before calling
# this so that -h|--help works.  If the module needs a non-default config
# file, set CONFIG_FILE before calling parse_module_args.
#
# Usage: parse_module_args "$@"
parse_module_args() {
    CONFIG_FILE="${CONFIG_FILE:-$SETUP_DIR/config/test_config.yaml}"
    DRY_RUN="false"
    local output_dir_override=""

    while [ $# -gt 0 ]; do
        case "$1" in
            --config)      CONFIG_FILE="$2"; shift 2 ;;
            --output-dir)  output_dir_override="$2"; shift 2 ;;
            --dry-run)     DRY_RUN="true"; shift ;;
            -h|--help)     module_usage; exit 0 ;;
            *)             die "Unknown option: $1" ;;
        esac
    done

    [ -n "$output_dir_override" ] && OUTPUT_DIR="$output_dir_override"
    return 0
}

# Set up module output directory and activate the ColdFront environment.
# Usage: init_module "05_rates"
# Sets: MODULE_OUTPUT
init_module() {
    local module_name="$1"
    ensure_yaml_support
    MODULE_OUTPUT="$OUTPUT_DIR/$module_name"
    mkdir -p "$MODULE_OUTPUT"
    ensure_env
    activate_env
}

# Resolve an include path from test_config.yaml and validate it exists.
# Returns the absolute path to the resolved config file on stdout.
# Usage: RATES_CONFIG="$(resolve_include "$CONFIG_FILE" "rates" "Rates")"
resolve_include() {
    local config_file="$1"
    local key="$2"
    local label="$3"
    local python_cmd
    python_cmd="$(get_python_cmd)"

    local rel_path
    rel_path="$($python_cmd - "$config_file" "$key" << 'PY'
import sys, yaml
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}
print(data.get("includes", {}).get(sys.argv[2], ""))
PY
    )"

    if [ -z "$rel_path" ]; then
        die "$key config path not found in test_config.yaml includes section"
    fi

    local full_path="$SETUP_DIR/config/$rel_path"
    if [ ! -f "$full_path" ]; then
        die "$label config not found: $full_path"
    fi

    echo "$full_path"
}

# Run a coldfront management command, or log it in dry-run mode.
# Captures output to the specified log file.  In non-dry-run mode the
# command output is also printed to stdout so callers can capture it.
#
# Usage: output="$(run_coldfront "$LOG_FILE" "${cmd[@]}")"
run_coldfront() {
    local log_file="$1"
    shift

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] coldfront $*" >> "$log_file"
        return 0
    fi

    local output
    output="$(coldfront "$@" 2>&1)"
    printf "%s\n" "$output" >> "$log_file"
    echo "$output"
}
