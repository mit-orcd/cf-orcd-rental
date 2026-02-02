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
