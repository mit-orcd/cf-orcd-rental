#!/usr/bin/env bash
#
# Run all setup and test modules in sequence.
#
# This script executes the full setup pipeline: environment setup,
# a quick smoke test, then every numbered module in order.
#
# Usage:
#   ./run_all.sh
#
# Prerequisites:
#   - Run from the tests/setup/ directory, or the script will cd there.
#   - Environment variables expected by setup_environment.sh should
#     already be exported (COLDFRONT_VERSION, WORKSPACE, etc.).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo " ORCD Rental Portal - Full Setup & Test Run"
echo "============================================================"
echo ""

STEPS=(
    "./setup_environment.sh"
    "./user_smoke_test.sh"
    "./modules/01_1_multiusers.sh"
    "./modules/02_projects.sh"
    "./modules/03_members.sh"
    "./modules/04_1_attach_cost_allocations.sh"
    "./modules/04_2_confirm_cost_allocations.sh"
    "./modules/05_rates.sh"
    "./modules/06_add_amf.sh"
    "./modules/07_1_create_reservations.sh"
    "./modules/07_2_confirm_reservations.sh"
    "./modules/08_maintenance.sh"
    "./modules/09_invoices.sh"
)

TOTAL=${#STEPS[@]}
CURRENT=0

for step in "${STEPS[@]}"; do
    CURRENT=$((CURRENT + 1))
    echo "------------------------------------------------------------"
    echo " [$CURRENT/$TOTAL] Running: $step"
    echo "------------------------------------------------------------"
    bash "$step"
    echo ""
done

echo "============================================================"
echo " All $TOTAL steps completed successfully."
echo "============================================================"
