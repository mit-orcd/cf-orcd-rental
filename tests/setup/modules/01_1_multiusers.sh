#!/usr/bin/env bash
#
# Module 01_1: Multi-user Test
#
# Creates multiple users from users_multi.yaml config:
# - 3 manager accounts (rate, billing, rental)
# - 10 regular user accounts (orcd_u0 through orcd_u9)
#
# After creation, lists all orcd_* users in JSON format.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SETUP_DIR/lib/common.sh"
common_init

CONFIG_FILE="$SETUP_DIR/config/users_multi.yaml"
OUTPUT_DIR_OVERRIDE=""
DRY_RUN="false"

usage() {
    cat << 'EOF'
Usage: 01_1_multiusers.sh [options]
  --config <path>      Path to users_multi.yaml (default: config/users_multi.yaml)
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

MODULE_OUTPUT="$OUTPUT_DIR/01_1_multiusers"
mkdir -p "$MODULE_OUTPUT"

if [ ! -f "$CONFIG_FILE" ]; then
    die "Config file not found: $CONFIG_FILE"
fi

ensure_env
activate_env

log_step "Creating users from $CONFIG_FILE"

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
    fi
done < <(python3 - "$CONFIG_FILE" << 'PY'
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

for u in data.get("users", []):
    emit(u)
PY
)

# Convert tokens TSV to JSON
if [ "$DRY_RUN" != "true" ]; then
    python3 - "$TOKENS_TSV" "$TOKENS_JSON" << 'PY'
import json
import sys

tokens = []
with open(sys.argv[1], "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if idx == 0:
            continue
        parts = line.strip().split("\t", 1)
        if len(parts) == 2:
            tokens.append({"username": parts[0], "token": parts[1]})

with open(sys.argv[2], "w", encoding="utf-8") as out:
    json.dump(tokens, out, indent=2)
PY
    pretty_json "$TOKENS_JSON" "$TOKENS_PRETTY"
fi

# =============================================================================
# List all orcd_* users via Django ORM
# =============================================================================

log_step "Listing all orcd_* users"

ALL_USERS_JSON="$MODULE_OUTPUT/all_users.json"
ALL_USERS_PRETTY="$MODULE_OUTPUT/all_users_pretty.json"

if [ "$DRY_RUN" != "true" ]; then
    python3 - "$ALL_USERS_JSON" << 'PY'
import json
import sys
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coldfront.config.settings")
django.setup()

from django.contrib.auth.models import User

users_qs = (
    User.objects
    .filter(username__startswith="orcd_")
    .order_by("username")
    .values(
        "id", "username", "first_name", "last_name", "email",
        "is_active", "date_joined",
    )
)

# Merge last_modified from UserAccountTimestamp (if available)
from coldfront_orcd_direct_charge.models import UserAccountTimestamp
ts_map = {
    ts.user_id: ts.last_modified
    for ts in UserAccountTimestamp.objects.filter(user__username__startswith="orcd_")
}

result = []
for u in users_qs:
    u["date_joined"] = u["date_joined"].isoformat() if u["date_joined"] else None
    last_mod = ts_map.get(u["id"])
    u["last_modified"] = last_mod.isoformat() if last_mod else None
    result.append(u)

output_path = sys.argv[1]
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(result, f)
PY

    # Pretty-print with jq if available, otherwise use Python
    if command -v jq >/dev/null 2>&1; then
        jq '.' "$ALL_USERS_JSON" > "$ALL_USERS_PRETTY"
    else
        pretty_json "$ALL_USERS_JSON" "$ALL_USERS_PRETTY"
    fi

    # Display the user list
    echo ""
    echo "All orcd_* users:"
    echo "================="
    cat "$ALL_USERS_PRETTY"
    echo ""
fi

# =============================================================================
# Summary
# =============================================================================

user_count=$(python3 - "$CONFIG_FILE" << 'PY'
import sys
import yaml
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}
print(len(data.get("users", [])))
PY
)

echo ""
echo "Module 01_1 complete."
echo "  Users created: $user_count"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - create_users.log      : User creation log"
echo "  - api_tokens.tsv        : API tokens (TSV format)"
echo "  - api_tokens.json       : API tokens (JSON format)"
echo "  - all_users.json        : All orcd_* users (raw JSON)"
echo "  - all_users_pretty.json : All orcd_* users (pretty JSON)"
