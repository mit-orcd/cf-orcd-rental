#!/usr/bin/env bash
#
# User Smoke Test
#
# Creates a single user via management command, queries the API,
# and saves API output for human review.
#
# Usage:
#   ./tests/setup/user_smoke_test.sh
#
# Environment Variables (optional):
#   WORKSPACE       - Parent directory for ColdFront clone
#   COLDFRONT_DIR   - Path to ColdFront installation
#   SERVER_PORT     - Port for test server (default: 8000)
#   SMOKE_USERNAME  - Username to create/search (default: smokeuser)
#   SMOKE_EMAIL     - Email for the user (default: <username>@example.com)
#   OUTPUT_DIR      - Output directory for logs/json (default: tests/setup/output)
#
set -euo pipefail

# =============================================================================
# Paths and configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORKSPACE="${WORKSPACE:-$(dirname "$PLUGIN_DIR")}"
COLDFRONT_DIR="${COLDFRONT_DIR:-$WORKSPACE/coldfront}"
SERVER_PORT="${SERVER_PORT:-8000}"
RUNNER_TYPE="${RUNNER_TYPE:-local}"
USE_UV="${USE_UV:-true}"

SMOKE_USERNAME="${SMOKE_USERNAME:-smokeuser}"
SMOKE_EMAIL="${SMOKE_EMAIL:-${SMOKE_USERNAME}@example.com}"

OUTPUT_DIR="${OUTPUT_DIR:-$SCRIPT_DIR/output}"
SERVER_LOG="${OUTPUT_DIR}/coldfront_server.log"
CREATE_USER_LOG="${OUTPUT_DIR}/create_user.log"
RAW_JSON="${OUTPUT_DIR}/user_search_raw.json"
PRETTY_JSON="${OUTPUT_DIR}/user_search_pretty.json"
PID_FILE="${OUTPUT_DIR}/server.pid"

mkdir -p "$OUTPUT_DIR"

# =============================================================================
# Helper functions
# =============================================================================

log_step() {
    echo ""
    echo "==> $1"
    echo ""
}

db_exists() {
    [ -f "$COLDFRONT_DIR/coldfront.db" ] || [ -f "$COLDFRONT_DIR/db.sqlite3" ]
}

server_ready() {
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${SERVER_PORT}/" || true)
    [[ "$code" =~ ^[23] ]]
}

wait_for_server() {
    local max_wait=60
    local waited=0
    while [ $waited -lt $max_wait ]; do
        if server_ready; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 1
}

# =============================================================================
# Setup environment (reuse DB if present)
# =============================================================================

log_step "Ensuring ColdFront environment is ready"

SKIP_INIT="false"
if db_exists; then
    SKIP_INIT="true"
fi

RUNNER_TYPE="$RUNNER_TYPE" \
WORKSPACE="$WORKSPACE" \
USE_UV="$USE_UV" \
SKIP_SERVER="true" \
SKIP_INIT="$SKIP_INIT" \
"$SCRIPT_DIR/setup_environment.sh"

# =============================================================================
# Activate environment and enable API plugin
# =============================================================================

if [ ! -f "$COLDFRONT_DIR/activate_env.sh" ]; then
    echo "ERROR: activate_env.sh not found at $COLDFRONT_DIR/activate_env.sh"
    exit 1
fi

source "$COLDFRONT_DIR/activate_env.sh"
export PLUGIN_API="true"

# Ensure API migrations are applied (authtoken, etc.)
coldfront migrate --no-input

# =============================================================================
# Create user and capture API token
# =============================================================================

log_step "Creating smoke-test user"

if [ "${#SMOKE_USERNAME}" -lt 2 ]; then
    echo "ERROR: SMOKE_USERNAME must be at least 2 characters"
    exit 1
fi

create_output="$(
    coldfront create_user "$SMOKE_USERNAME" \
        --email "$SMOKE_EMAIL" \
        --with-token \
        --force 2>&1
)"
printf "%s\n" "$create_output" > "$CREATE_USER_LOG"

api_token="$(
    printf "%s\n" "$create_output" | sed -n 's/.*API Token: *//p' | tail -n 1 | tr -d '\r'
)"

if [ -z "$api_token" ]; then
    echo "ERROR: API token not found in create_user output"
    echo "See log: $CREATE_USER_LOG"
    exit 1
fi

# =============================================================================
# Start server (if needed) and call API
# =============================================================================

log_step "Starting server (if needed)"

if ! server_ready; then
    nohup coldfront runserver "0.0.0.0:${SERVER_PORT}" > "$SERVER_LOG" 2>&1 &
    echo "$!" > "$PID_FILE"
    if ! wait_for_server; then
        echo "ERROR: Server did not become ready"
        echo "Server log: $SERVER_LOG"
        exit 1
    fi
else
    # Capture existing server log if available
    if [ -f /tmp/coldfront_server.log ]; then
        cp /tmp/coldfront_server.log "$SERVER_LOG"
    fi
fi

log_step "Querying API and saving output"

api_url="http://localhost:${SERVER_PORT}/nodes/api/user-search/?q=${SMOKE_USERNAME}"

http_code="$(
    curl -sS \
        -H "Authorization: Token ${api_token}" \
        -H "Accept: application/json" \
        -o "$RAW_JSON" \
        -w "%{http_code}" \
        "$api_url" || true
)"

if [ "$http_code" != "200" ]; then
    echo "ERROR: API request failed with status ${http_code}"
    echo "URL: $api_url"
    echo "Raw output saved to: $RAW_JSON"
    exit 1
fi

# Pretty-print JSON for human review
python -m json.tool "$RAW_JSON" > "$PRETTY_JSON"

# Verify the user appears in the response
python - "$RAW_JSON" "$SMOKE_USERNAME" << 'PY'
import json
import sys

path = sys.argv[1]
username = sys.argv[2]

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

if not isinstance(data, list):
    raise SystemExit("Expected a JSON list response from user-search API")

if not any(item.get("username") == username for item in data):
    raise SystemExit(f"User '{username}' not found in API response")
PY

echo ""
echo "Smoke test complete."
echo "  Raw API output: $RAW_JSON"
echo "  Pretty output:  $PRETTY_JSON"
echo "  Create-user log: $CREATE_USER_LOG"
