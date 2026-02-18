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

# Default config is rates.yaml
CONFIG_FILE="$SETUP_DIR/config/rates.yaml"

module_usage() {
    cat << 'EOF'
Usage: 05_rates.sh [options]
  --config <path>      Path to test_config.yaml
  --output-dir <path>  Output directory for artifacts
  --dry-run            Print actions without applying changes
EOF
}

parse_module_args "$@"
init_module "05_rates"

RATES_CONFIG=${CONFIG_FILE}
if [ ! -f "$CONFIG_FILE" ]; then
    die "Config file not found: $CONFIG_FILE"
fi


# ---------------------------------------------------------------------------
# Main loop: parse YAML, call set_sku_rate for each entry
# ---------------------------------------------------------------------------

log_step "Setting SKU rates from YAML"

RATE_LOG="$MODULE_OUTPUT/set_rates.log"
rate_count=0
python_cmd="$(get_python_cmd)"

while IFS=$'\t' read -r sku_code rate effective_date set_by notes visibility; do
    [ -n "$sku_code" ] || continue

    # Resolve relative date expression (e.g. "today", "today+7") to YYYY-MM-DD
    [ -n "$effective_date" ] && effective_date="$(resolve_relative_date "$effective_date")"

    cmd=(set_sku_rate "$sku_code" "$rate" --force)

    [ -n "$effective_date" ] && cmd+=(--effective-date "$effective_date")
    [ -n "$set_by" ]         && cmd+=(--set-by "$set_by")
    [ -n "$notes" ]          && cmd+=(--notes "$notes")
    [ -n "$visibility" ]     && cmd+=(--visibility "$visibility")

    run_coldfront "$RATE_LOG" "${cmd[@]}" >/dev/null

    rate_count=$((rate_count + 1))

done < <($python_cmd - "$RATES_CONFIG" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

defaults = data.get("defaults", {})
default_is_public = defaults.get("is_public", None)
default_effective_date = str(defaults.get("effective_date", ""))
default_set_by = defaults.get("set_by", "")
default_notes = defaults.get("notes", "")

for entry in data.get("rates", []):
    sku_code = entry.get("sku_code", "")
    rate = str(entry.get("rate", ""))
    if not sku_code or not rate:
        continue

    # Emit the raw date expression -- bash-side resolve_relative_date handles resolution
    effective_date = str(entry.get("effective_date", default_effective_date))
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
