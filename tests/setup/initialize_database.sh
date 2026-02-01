#!/usr/bin/env bash
#
# Initialize ColdFront Database for Testing
#
# This script initializes the ColdFront database with required data for testing.
# It is called by setup_environment.sh after migrations are applied.
#
# This script performs:
# 1. Run coldfront initial_setup (creates default ColdFront data)
# 2. Create manager groups (rental, billing, rate)
# 3. Load plugin fixtures
# 4. Create a test superuser
#
# Usage:
#   ./initialize_database.sh
#
# Environment Variables:
#   COLDFRONT_DIR      - Path to ColdFront installation (required)
#   PLUGIN_DIR         - Path to plugin directory (required)
#   INSTALLER          - Package installer: 'uv' or 'pip' (default: pip)
#   TEST_SUPERUSER     - Username for test superuser (default: admin)
#   TEST_PASSWORD      - Password for test superuser (default: testpass123)
#   SKIP_SUPERUSER     - Skip creating superuser (default: false)
#

set -e  # Exit on first error

# =============================================================================
# Configuration
# =============================================================================

COLDFRONT_DIR="${COLDFRONT_DIR:-}"
PLUGIN_DIR="${PLUGIN_DIR:-}"
INSTALLER="${INSTALLER:-pip}"
TEST_SUPERUSER="${TEST_SUPERUSER:-admin}"
TEST_PASSWORD="${TEST_PASSWORD:-testpass123}"
SKIP_SUPERUSER="${SKIP_SUPERUSER:-false}"

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
    echo ""
    echo -e "${GREEN}==>${NC} $1"
    echo ""
}

log_warn() {
    echo -e "${YELLOW}Warning:${NC} $1"
}

log_error() {
    echo -e "${RED}Error:${NC} $1"
}

# =============================================================================
# Validation
# =============================================================================

if [ -z "$COLDFRONT_DIR" ]; then
    log_error "COLDFRONT_DIR is not set"
    exit 1
fi

if [ ! -d "$COLDFRONT_DIR" ]; then
    log_error "COLDFRONT_DIR does not exist: $COLDFRONT_DIR"
    exit 1
fi

# =============================================================================
# Helper function to run coldfront commands
# =============================================================================

run_coldfront() {
    local cmd="$1"
    
    if [ "$INSTALLER" = "uv" ]; then
        (cd "$COLDFRONT_DIR" && uv run coldfront $cmd)
    else
        (cd "$COLDFRONT_DIR" && source .venv/bin/activate && coldfront $cmd)
    fi
}

# =============================================================================
# Run initial_setup
# =============================================================================

log_step "Running ColdFront initial_setup"

# initial_setup prompts for confirmation, so we pipe 'yes' to it
if [ "$INSTALLER" = "uv" ]; then
    (cd "$COLDFRONT_DIR" && echo 'yes' | uv run coldfront initial_setup) || log_warn "initial_setup may have already been run"
else
    (cd "$COLDFRONT_DIR" && source .venv/bin/activate && echo 'yes' | coldfront initial_setup) || log_warn "initial_setup may have already been run"
fi

echo "initial_setup complete"

# =============================================================================
# Create Manager Groups
# =============================================================================

log_step "Creating manager groups"

echo "Creating Rental Manager group..."
run_coldfront "setup_rental_manager --create-group" || log_warn "Rental Manager group may already exist"

echo "Creating Billing Manager group..."
run_coldfront "setup_billing_manager --create-group" || log_warn "Billing Manager group may already exist"

echo "Creating Rate Manager group..."
run_coldfront "setup_rate_manager --create-group" || log_warn "Rate Manager group may already exist"

echo "Manager groups created"

# =============================================================================
# Load Plugin Fixtures
# =============================================================================

log_step "Loading plugin fixtures"

# These fixtures provide node types and instances for testing
run_coldfront "loaddata node_types" || log_warn "Could not load node_types fixture"
run_coldfront "loaddata gpu_node_instances" || log_warn "Could not load gpu_node_instances fixture"
run_coldfront "loaddata cpu_node_instances" || log_warn "Could not load cpu_node_instances fixture"
run_coldfront "loaddata node_resource_types" || log_warn "Could not load node_resource_types fixture"

echo "Fixtures loaded"

# =============================================================================
# Create Test Superuser
# =============================================================================

if [ "$SKIP_SUPERUSER" != "true" ]; then
    log_step "Creating test superuser: $TEST_SUPERUSER"
    
    # Use Django's createsuperuser with --noinput and environment variables
    if [ "$INSTALLER" = "uv" ]; then
        (cd "$COLDFRONT_DIR" && \
            DJANGO_SUPERUSER_PASSWORD="$TEST_PASSWORD" \
            uv run coldfront createsuperuser --noinput \
                --username "$TEST_SUPERUSER" \
                --email "${TEST_SUPERUSER}@example.com") || log_warn "Superuser may already exist"
    else
        (cd "$COLDFRONT_DIR" && source .venv/bin/activate && \
            DJANGO_SUPERUSER_PASSWORD="$TEST_PASSWORD" \
            coldfront createsuperuser --noinput \
                --username "$TEST_SUPERUSER" \
                --email "${TEST_SUPERUSER}@example.com") || log_warn "Superuser may already exist"
    fi
    
    echo "Superuser created: $TEST_SUPERUSER"
else
    echo "Skipping superuser creation (SKIP_SUPERUSER=true)"
fi

# =============================================================================
# Summary
# =============================================================================

log_step "Database initialization complete!"

echo "The following has been set up:"
echo "  - ColdFront initial data (fields of science, etc.)"
echo "  - Manager groups: Rental Manager, Billing Manager, Rate Manager"
echo "  - Plugin fixtures: node types, node instances"
if [ "$SKIP_SUPERUSER" != "true" ]; then
    echo "  - Test superuser: $TEST_SUPERUSER (password: $TEST_PASSWORD)"
fi
