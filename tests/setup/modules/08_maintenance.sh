#!/usr/bin/env bash
#
# Module 08: Maintenance Windows
#
# Creates maintenance windows from a schedule-based YAML config.
# Each schedule defines a recurring pattern (e.g. "3rd Tuesday of
# every month") which is expanded into concrete dates for the next
# N months from today.
#
# Uses `coldfront create_maintenance_window` to create each window.
#
# Note: The create_maintenance_window command does not have a --force
# flag, so re-running this script will create duplicate windows.
# This is expected for test setup against a fresh database.
#
# Depends on:
#   - 01_1_multiusers.sh  (creates user accounts)
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
Usage: 08_maintenance.sh [options]
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

MODULE_OUTPUT="$OUTPUT_DIR/08_maintenance"
mkdir -p "$MODULE_OUTPUT"

# ---------------------------------------------------------------------------
# Resolve the maintenance_windows config path from test_config.yaml includes
# ---------------------------------------------------------------------------

MAINT_CONFIG="$(python3 - "$CONFIG_FILE" << 'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

includes = data.get("includes", {})
print(includes.get("maintenance_windows", ""))
PY
)"

if [ -z "$MAINT_CONFIG" ]; then
    die "maintenance_windows config path not found in test_config.yaml includes section"
fi

if [ ! -f "$SETUP_DIR/config/$MAINT_CONFIG" ]; then
    die "Maintenance windows config not found: $SETUP_DIR/config/$MAINT_CONFIG"
fi

MAINT_CONFIG="$SETUP_DIR/config/$MAINT_CONFIG"

# ---------------------------------------------------------------------------
# Set up environment
# ---------------------------------------------------------------------------

ensure_env
activate_env

# ---------------------------------------------------------------------------
# Main loop: expand schedules to concrete windows, call create_maintenance_window
# ---------------------------------------------------------------------------

log_step "Creating maintenance windows from schedules"

MAINT_LOG="$MODULE_OUTPUT/maintenance_windows.log"
window_count=0

while IFS=$'\t' read -r start_dt end_dt title description; do
    [ -n "$start_dt" ] || continue

    cmd=(create_maintenance_window
         --start "$start_dt"
         --end "$end_dt"
         --title "$title")

    [ -n "$description" ] && cmd+=(--description "$description")

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY-RUN] coldfront ${cmd[*]}" >> "$MAINT_LOG"
    else
        output="$(coldfront "${cmd[@]}" 2>&1)"
        printf "%s\n" "$output" >> "$MAINT_LOG"
    fi

    window_count=$((window_count + 1))

done < <(python3 - "$MAINT_CONFIG" << 'PYEXPAND'
"""
Expand schedule-based maintenance window config into concrete dates.

For each schedule entry, finds the Nth weekday of each month for the
next N months from today and emits one TSV line per concrete window:
    start_datetime\tend_datetime\ttitle\tdescription
"""
import calendar
import sys
from datetime import date, datetime, timedelta

import yaml

WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def nth_weekday_of_month(year, month, weekday, n):
    """Find the nth occurrence of a weekday in a given month.

    Args:
        year: Calendar year
        month: Calendar month (1-12)
        weekday: 0=Monday through 6=Sunday
        n: Which occurrence (1-4) or "last"

    Returns:
        date object, or None if the nth occurrence does not exist
    """
    cal = calendar.monthcalendar(year, month)
    # Collect all days in the month that fall on the target weekday
    days = [week[weekday] for week in cal if week[weekday] != 0]

    if isinstance(n, str) and n.lower() == "last":
        return date(year, month, days[-1]) if days else None

    n = int(n)
    if n < 1 or n > len(days):
        return None
    return date(year, month, days[n - 1])


def months_from(start_date, count):
    """Generate (year, month) tuples for the next `count` months."""
    y, m = start_date.year, start_date.month
    for _ in range(count):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


# -- Main ------------------------------------------------------------------

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

defaults = data.get("defaults", {})
default_months_ahead = defaults.get("months_ahead", 3)
default_start_time = defaults.get("start_time", "06:00")
default_end_time = defaults.get("end_time", "18:00")

today = date.today()

for sched in data.get("schedules", []):
    title_base = sched.get("title", "Maintenance")
    weekday_str = sched.get("weekday", "").strip().lower()
    week_of_month = sched.get("week_of_month", 1)
    start_time = sched.get("start_time", default_start_time)
    end_time = sched.get("end_time", default_end_time)
    months_ahead = sched.get("months_ahead", default_months_ahead)
    description = sched.get("description", "")

    if weekday_str not in WEEKDAY_MAP:
        print(f"WARNING: unknown weekday '{weekday_str}', skipping",
              file=sys.stderr)
        continue

    weekday = WEEKDAY_MAP[weekday_str]

    for year, month in months_from(today, months_ahead):
        target_date = nth_weekday_of_month(year, month, weekday, week_of_month)
        if target_date is None:
            continue
        # Skip dates in the past
        if target_date < today:
            continue

        # Build full datetimes
        start_dt = datetime.strptime(
            f"{target_date.isoformat()} {start_time}", "%Y-%m-%d %H:%M"
        )
        end_dt = datetime.strptime(
            f"{target_date.isoformat()} {end_time}", "%Y-%m-%d %H:%M"
        )

        # If end <= start, assume end is the next day
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        # Format title with the computed date
        title = f"{title_base} ({target_date.strftime('%b %d, %Y')})"

        line = "\t".join([
            start_dt.strftime("%Y-%m-%d %H:%M"),
            end_dt.strftime("%Y-%m-%d %H:%M"),
            title,
            description,
        ])
        print(line)
PYEXPAND
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Module 08 complete."
echo "  Maintenance windows created: $window_count"
echo "  Output directory: $MODULE_OUTPUT"
echo ""
echo "Output files:"
echo "  - maintenance_windows.log : Command output log"
