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

CONFIG_FILE="$SETUP_DIR/config/test_config.yaml"
OUTPUT_DIR_OVERRIDE=""
DRY_RUN="false"

usage() {
    cat << 'EOF'
Usage: 01_users.sh [options]
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

MODULE_OUTPUT="$OUTPUT_DIR/01_users"
mkdir -p "$MODULE_OUTPUT"

USERS_CONFIG="$(python3 - "$CONFIG_FILE" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

includes = data.get("includes", {})
print(includes.get("users", ""))
PY
)"

if [ -z "$USERS_CONFIG" ]; then
    die "users config path not found in test_config.yaml includes.users"
fi

if [ ! -f "$SETUP_DIR/config/$USERS_CONFIG" ]; then
    die "Users config not found: $SETUP_DIR/config/$USERS_CONFIG"
fi

USERS_CONFIG="$SETUP_DIR/config/$USERS_CONFIG"

ensure_env
activate_env

log_step "Creating users from YAML"

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

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] create_user $username ($email)" >> "$CREATE_LOG"
        continue
    fi

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

    output="$(coldfront "${cmd[@]}" 2>&1)"
    printf "%s\n" "$output" >> "$CREATE_LOG"

    token="$(printf "%s\n" "$output" | extract_api_token)"
    if [ -n "$token" ]; then
        echo -e "${username}\t${token}" >> "$TOKENS_TSV"
        if [ -z "$first_token" ]; then
            first_token="$token"
            first_username="$username"
        fi
    fi
done < <(python3 - "$USERS_CONFIG" << 'PY'
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
    python3 - "$TOKENS_TSV" "$TOKENS_JSON" << 'PY'
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
