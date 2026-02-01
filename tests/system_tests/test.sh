#!/usr/bin/env bash
#
# System Tests Runner
#
# This script runs the Module 01: User Management system tests.
# It is designed to be discovered and executed by tests/run_all_tests.sh.
#
# Prerequisites:
#   - Environment must be set up via tests/setup/setup_environment.sh
#   - Config files must exist (copy from .example files)
#
# Usage:
#   ./test.sh              # Run all system tests
#   ./test.sh --dry-run    # Run in dry-run mode
#   ./test.sh --generate   # Generate command script only
#

set -e  # Exit on first error

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORKSPACE="${WORKSPACE:-$(dirname "$PLUGIN_DIR")}"
COLDFRONT_DIR="$WORKSPACE/coldfront"

# Colors for output
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    NC='\033[0m'
else
    GREEN=''
    YELLOW=''
    RED=''
    NC=''
fi

log_step() {
    echo -e "${GREEN}==>${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}Warning:${NC} $1"
}

log_error() {
    echo -e "${RED}Error:${NC} $1"
}

# Check if ColdFront environment exists
if [ ! -d "$COLDFRONT_DIR/.venv" ]; then
    log_error "ColdFront environment not found at $COLDFRONT_DIR"
    log_error "Run tests/setup/setup_environment.sh first"
    exit 1
fi

# Check for config files
CONFIG_DIR="$SCRIPT_DIR/config"
if [ ! -f "$CONFIG_DIR/users.yaml" ]; then
    if [ -f "$CONFIG_DIR/users.yaml.example" ]; then
        log_warn "Config file not found: $CONFIG_DIR/users.yaml"
        log_warn "Copy from example: cp $CONFIG_DIR/users.yaml.example $CONFIG_DIR/users.yaml"
        log_warn "Skipping system tests (config not set up)"
        exit 0  # Exit with success - tests are optional until configured
    else
        log_error "No config files found in $CONFIG_DIR"
        exit 1
    fi
fi

# Parse arguments
DRY_RUN=""
GENERATE_ONLY=""
VERBOSE=""

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN="--dry-run"
            ;;
        --generate|--generate-commands-only)
            GENERATE_ONLY="--generate-commands-only"
            ;;
        --verbose|-v)
            VERBOSE="--verbose"
            ;;
    esac
done

# Activate ColdFront virtual environment
log_step "Activating ColdFront environment"
source "$COLDFRONT_DIR/.venv/bin/activate"

# Install system test dependencies if needed
if ! python -c "import pytest" 2>/dev/null; then
    log_step "Installing system test dependencies"
    pip install -r "$SCRIPT_DIR/requirements.txt"
fi

# Run the tests
log_step "Running system tests"
cd "$SCRIPT_DIR"

if [ -n "$GENERATE_ONLY" ]; then
    python run_tests.py $GENERATE_ONLY $VERBOSE
elif [ -n "$DRY_RUN" ]; then
    python run_tests.py $DRY_RUN $VERBOSE
else
    python run_tests.py $VERBOSE
fi

log_step "System tests complete"
