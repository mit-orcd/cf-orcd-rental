#!/usr/bin/env bash
#
# Module 09: Invoices
#
# Generates invoice reports for each month listed in the YAML config
# by calling the invoice report API endpoint.  The JSON response for
# each month is saved to the output directory.
#
# Unlike other modules that use `coldfront` management commands, this
# module uses the REST API because invoices are computed on-the-fly
# from reservations and there is no invoice management command.
#
# The API endpoint GET /nodes/api/invoice/YYYY/MM/ returns full
# invoice data including reservations, hours, cost breakdowns,
# maintenance deductions, and overrides.
#
# Depends on:
#   - 01_1_multiusers.sh          (creates user accounts and API tokens)
#   - 07_1_create_reservations.sh (creates PENDING reservations)
#   - 07_2_confirm_reservations.sh (approves reservations)
#   - 08_maintenance.sh           (creates maintenance windows)
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
Usage: 09_invoices.sh [options]
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

MODULE_OUTPUT="$OUTPUT_DIR/09_invoices"
mkdir -p "$MODULE_OUTPUT"

# ---------------------------------------------------------------------------
# Resolve the invoices config path from test_config.yaml includes
# ---------------------------------------------------------------------------

INV_CONFIG="$(python3 - "$CONFIG_FILE" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

includes = data.get("includes", {})
print(includes.get("invoices", ""))
PY
)"

if [ -z "$INV_CONFIG" ]; then
    die "invoices config path not found in test_config.yaml includes section"
fi

if [ ! -f "$SETUP_DIR/config/$INV_CONFIG" ]; then
    die "Invoices config not found: $SETUP_DIR/config/$INV_CONFIG"
fi

INV_CONFIG="$SETUP_DIR/config/$INV_CONFIG"

# ---------------------------------------------------------------------------
# Read billing user from YAML config
# ---------------------------------------------------------------------------

BILLING_USER="$(python3 - "$INV_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

defaults = data.get("defaults", {})
print(defaults.get("billing_user", "orcd_bim"))
PY
)"

# ---------------------------------------------------------------------------
# Set up environment and start server
# ---------------------------------------------------------------------------

ensure_env
activate_env

SERVER_LOG="$MODULE_OUTPUT/coldfront_server.log"
PID_FILE="$MODULE_OUTPUT/server.pid"
start_server_if_needed "$SERVER_LOG" "$PID_FILE"

BASE_URL="http://localhost:${SERVER_PORT}"

# ---------------------------------------------------------------------------
# Read billing manager API token from module 01 output
# ---------------------------------------------------------------------------

TOKENS_FILE="$OUTPUT_DIR/01_1_multiusers/api_tokens.tsv"

if [ ! -f "$TOKENS_FILE" ]; then
    die "API tokens file not found: $TOKENS_FILE (run module 01_1 first)"
fi

TOKEN="$(grep "^${BILLING_USER}	" "$TOKENS_FILE" | cut -f2)"

if [ -z "$TOKEN" ]; then
    die "API token for '${BILLING_USER}' not found in $TOKENS_FILE"
fi

# ---------------------------------------------------------------------------
# Main loop: resolve month expressions, call invoice API for each
# ---------------------------------------------------------------------------

log_step "Generating invoices via API (user: $BILLING_USER)"

INV_LOG="$MODULE_OUTPUT/invoices.log"
inv_count=0

while IFS=$'\t' read -r year month label; do
    [ -n "$year" ] || continue

    # Pad month to 2 digits for filenames
    month_padded="$(printf "%02d" "$month")"

    raw_file="$MODULE_OUTPUT/invoice_${year}_${month_padded}.json"
    pretty_file="$MODULE_OUTPUT/invoice_${year}_${month_padded}_pretty.json"

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] GET ${BASE_URL}/nodes/api/invoice/${year}/${month}/ -> $raw_file" >> "$INV_LOG"
    else
        echo "Fetching invoice for $label ($year-$month_padded)..." >> "$INV_LOG"

        http_code="$(api_get "${BASE_URL}/nodes/api/invoice/${year}/${month}/" "$TOKEN" "$raw_file")"

        if [[ "$http_code" =~ ^2 ]]; then
            echo "  HTTP $http_code - saved to $raw_file" >> "$INV_LOG"
            pretty_json "$raw_file" "$pretty_file" 2>/dev/null || true
        else
            echo "  HTTP $http_code - ERROR fetching invoice" >> "$INV_LOG"
            echo "WARNING: HTTP $http_code for $label ($year-$month_padded)"
        fi
    fi

    inv_count=$((inv_count + 1))

done < <(python3 - "$INV_CONFIG" << 'PYMONTHS'
"""
Resolve relative month expressions to (year, month, label) TSV.

Supported formats:
  "today"              -> current month
  "today - 2 months"   -> 2 months before current
  "today + 1 month"    -> 1 month after current
"""
import re
import sys
from datetime import date

import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

today = date.today()

for expr in data.get("invoice_periods", []):
    s = str(expr).strip().lower()

    if s == "today":
        year, month = today.year, today.month
    else:
        m = re.fullmatch(
            r"today\s*([+-])\s*(\d+)\s+months?",
            s,
            re.IGNORECASE,
        )
        if not m:
            print(f"WARNING: unrecognized month expression: {expr}",
                  file=sys.stderr)
            continue

        sign = 1 if m.group(1) == "+" else -1
        offset = int(m.group(2)) * sign

        # Compute year/month with offset
        total_months = (today.year * 12 + today.month - 1) + offset
        year = total_months // 12
        month = (total_months % 12) + 1

    # Human-readable label for logging
    import calendar
    label = f"{calendar.month_name[month]} {year}"

    print(f"{year}\t{month}\t{label}")
PYMONTHS
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Module 09 complete."
echo "  Invoices generated: $inv_count"
echo "  Billing user: $BILLING_USER"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - invoices.log                   : Request log"

if [ "$DRY_RUN" != "true" ]; then
    echo "  - invoice_YYYY_MM.json           : Raw invoice JSON per month"
    echo "  - invoice_YYYY_MM_pretty.json    : Pretty-printed invoice JSON"
fi
