#!/usr/bin/env bash
#
# Module 01: Users
#
# Creates users from YAML config and generates API tokens.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SETUP_DIR/lib/common.sh"
common_init

module_usage() {
    cat << 'EOF'
Usage: 01_users.sh [options]
  --config <path>      Path to test_config.yaml
  --output-dir <path>  Output directory for artifacts
  --dry-run            Print actions without applying changes
EOF
}

parse_module_args "$@"
init_module "01_users"

USERS_CONFIG="$(resolve_include "$CONFIG_FILE" "users" "Users")"

log_step "Creating users from YAML"

python_cmd="$(get_python_cmd)"

# Ensure manager groups exist
if [ "$DRY_RUN" != "true" ]; then
    coldfront setup_rental_manager --create-group >/dev/null 2>&1 || true
    coldfront setup_billing_manager --create-group >/dev/null 2>&1 || true
    coldfront setup_rate_manager --create-group >/dev/null 2>&1 || true
fi

CREATE_LOG="$MODULE_OUTPUT/create_users.log"
TOKENS_TSV="$MODULE_OUTPUT/api_tokens.tsv"
TOKENS_JSON="$MODULE_OUTPUT/api_tokens.json"
TOKENS_PRETTY="$MODULE_OUTPUT/api_tokens_pretty.json"

echo -e "username\ttoken" > "$TOKENS_TSV"
first_username=""
first_token=""

while IFS=$'\t' read -r username email password groups date_joined last_modified; do
    [ -n "$username" ] || continue

    cmd=(create_user "$username" --email "$email" --with-token --force)
    if [ -n "$password" ]; then
        cmd+=(--password "$password")
    fi

    if [ -n "$groups" ]; then
        IFS=',' read -r -a group_list <<< "$groups"
        for group in "${group_list[@]}"; do
            [ -n "$group" ] && cmd+=(--add-to-group "$group")
        done
    fi

    if [ -n "$date_joined" ]; then
        cmd+=(--date-joined "$date_joined")
    fi

    if [ -n "$last_modified" ]; then
        cmd+=(--last-modified "$last_modified")
    fi

    output="$(run_coldfront "$CREATE_LOG" "${cmd[@]}")"

    token="$(printf "%s\n" "$output" | extract_api_token)"
    if [ -n "$token" ]; then
        echo -e "${username}\t${token}" >> "$TOKENS_TSV"
        if [ -z "$first_token" ]; then
            first_token="$token"
            first_username="$username"
        fi
    fi
done < <($python_cmd - "$USERS_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

defaults = data.get("defaults", {})
default_password = defaults.get("password", "")
default_domain = defaults.get("email_domain", "")

def emit(user):
    username = user.get("username", "")
    email = user.get("email", "")
    password = user.get("password", default_password)
    groups = user.get("groups", [])
    date_joined = str(user.get("date_joined", ""))
    last_modified = str(user.get("last_modified", ""))

    if not email and default_domain:
        email = f"{username}@{default_domain}"

    line = "\t".join([
        username,
        email,
        password or "",
        ",".join(groups),
        date_joined,
        last_modified,
    ])
    print(line)

# Single users list - all users are equal (all have PI status)
for u in data.get("users", []):
    emit(u)
PY
)

if [ "$DRY_RUN" != "true" ]; then
    $python_cmd - "$TOKENS_TSV" "$TOKENS_JSON" << 'PY'
import json
import sys

tokens = []
with open(sys.argv[1], "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if idx == 0:
            continue
        username, token = line.strip().split("\t", 1)
        tokens.append({"username": username, "token": token})

with open(sys.argv[2], "w", encoding="utf-8") as out:
    json.dump(tokens, out, indent=2)
PY
    pretty_json "$TOKENS_JSON" "$TOKENS_PRETTY"
fi

if [ "$DRY_RUN" != "true" ] && [ -n "$first_token" ]; then
    log_step "Verifying user-search API"
    base_url="${BASE_URL:-http://localhost:${SERVER_PORT}}"
    api_url="${base_url}/nodes/api/user-search/?q=${first_username}"
    raw="$MODULE_OUTPUT/user_search_raw.json"
    pretty="$MODULE_OUTPUT/user_search_pretty.json"
    http_code="$(api_get "$api_url" "$first_token" "$raw" || true)"
    if [ "$http_code" = "200" ]; then
        pretty_json "$raw" "$pretty"
    else
        log_warn "User-search API returned status ${http_code}"
    fi
fi

echo "Module 01 complete. Output: $MODULE_OUTPUT"
