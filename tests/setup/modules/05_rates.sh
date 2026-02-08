#!/usr/bin/env bash
#
# Module 05: Rates
#
# Sets rate amounts and visibility on RentalSKUs based on YAML config.
# Each entry specifies a sku_code, rate amount, effective_date, and
# optional visibility and notes.  The YAML supports a `defaults` block
# so common values (effective_date, set_by, is_public) don't need to
# be repeated.
#
# Uses `coldfront set_sku_rate` with --force so the module is
# idempotent on re-runs.
#
# Depends on:
#   - 01_1_multiusers.sh  (creates orcd_rtm, the rate manager)
#   - Database migrations  (create SKUs with placeholder rates)
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
Usage: 05_rates.sh [options]
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

MODULE_OUTPUT="$OUTPUT_DIR/05_rates"
mkdir -p "$MODULE_OUTPUT"

# ---------------------------------------------------------------------------
# Resolve the rates config path from test_config.yaml includes
# ---------------------------------------------------------------------------

RATES_CONFIG="$(python3 - "$CONFIG_FILE" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

includes = data.get("includes", {})
print(includes.get("rates", ""))
PY
)"

if [ -z "$RATES_CONFIG" ]; then
    die "rates config path not found in test_config.yaml includes section"
fi

if [ ! -f "$SETUP_DIR/config/$RATES_CONFIG" ]; then
    die "Rates config not found: $SETUP_DIR/config/$RATES_CONFIG"
fi

RATES_CONFIG="$SETUP_DIR/config/$RATES_CONFIG"

# ---------------------------------------------------------------------------
# Set up environment
# ---------------------------------------------------------------------------

ensure_env
activate_env

# ---------------------------------------------------------------------------
# Main loop: parse YAML, call set_sku_rate for each entry
# ---------------------------------------------------------------------------

log_step "Setting SKU rates from YAML"

RATE_LOG="$MODULE_OUTPUT/set_rates.log"
rate_count=0

while IFS=$'\t' read -r sku_code rate effective_date set_by notes visibility; do
    [ -n "$sku_code" ] || continue

    cmd=(set_sku_rate "$sku_code" "$rate" --force)

    [ -n "$effective_date" ] && cmd+=(--effective-date "$effective_date")
    [ -n "$set_by" ]         && cmd+=(--set-by "$set_by")
    [ -n "$notes" ]          && cmd+=(--notes "$notes")
    [ -n "$visibility" ]     && cmd+=(--visibility "$visibility")

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] coldfront ${cmd[*]}" >> "$RATE_LOG"
    else
        output="$(coldfront "${cmd[@]}" 2>&1)"
        printf "%s\n" "$output" >> "$RATE_LOG"
    fi

    rate_count=$((rate_count + 1))

done < <(python3 - "$RATES_CONFIG" << 'PY'
import sys
from datetime import date
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

defaults = data.get("defaults", {})
default_is_public = defaults.get("is_public", None)
default_effective_date = str(defaults.get("effective_date", ""))
default_set_by = defaults.get("set_by", "")
default_notes = defaults.get("notes", "")

def resolve_date(value):
    """Resolve date value: 'today' becomes current date, otherwise pass through."""
    s = str(value).strip().lower()
    if s == "today":
        return str(date.today())
    return str(value)

for entry in data.get("rates", []):
    sku_code = entry.get("sku_code", "")
    rate = str(entry.get("rate", ""))
    if not sku_code or not rate:
        continue

    effective_date = resolve_date(entry.get("effective_date", default_effective_date))
    set_by = entry.get("set_by", default_set_by)
    notes = entry.get("notes", default_notes)

    # Resolve is_public: per-entry overrides default
    is_public = entry.get("is_public", default_is_public)
    if is_public is True:
        visibility = "public"
    elif is_public is False:
        visibility = "private"
    else:
        visibility = ""

    line = "\t".join([
        sku_code,
        rate,
        effective_date,
        set_by,
        notes,
        visibility,
    ])
    print(line)
PY
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Module 05 complete."
echo "  Rates set: $rate_count"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - set_rates.log : Command output log"
