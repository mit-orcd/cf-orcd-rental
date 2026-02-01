#!/usr/bin/env bash
#
# Setup Environment for ColdFront Plugin Testing
#
# This script sets up a complete ColdFront environment with the plugin installed.
# It is CI-agnostic and can be used with GitHub Actions, GitLab CI, Woodpecker, or locally.
#
# Usage:
#   ./setup_environment.sh
#
# Environment Variables:
#   COLDFRONT_VERSION  - ColdFront version to use (default: 1.1.7)
#   WORKSPACE          - Parent directory for ColdFront clone (default: parent of plugin dir)
#   USE_UV             - Use uv for faster installs (default: true)
#   RUNNER_TYPE        - Runner type: github, self-hosted, local (default: github)
#   SERVER_PORT        - Port for test server (default: 8000)
#   SKIP_SERVER        - Skip starting server (default: false)
#   SKIP_FIXTURES      - Skip loading fixtures (default: false, deprecated - use SKIP_INIT)
#   SKIP_INIT          - Skip database initialization (default: false)
#

set -e  # Exit on first error
set -u  # Error on undefined variables

# =============================================================================
# Configuration
# =============================================================================

COLDFRONT_VERSION="${COLDFRONT_VERSION:-1.1.7}"
COLDFRONT_REPO="${COLDFRONT_REPO:-https://github.com/ubccr/coldfront.git}"
SERVER_PORT="${SERVER_PORT:-8000}"
USE_UV="${USE_UV:-true}"
RUNNER_TYPE="${RUNNER_TYPE:-github}"
SKIP_SERVER="${SKIP_SERVER:-false}"
SKIP_FIXTURES="${SKIP_FIXTURES:-false}"
SKIP_INIT="${SKIP_INIT:-false}"

# Get script and plugin directories
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

# =============================================================================
# Helper Functions
# =============================================================================

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

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is required but not installed"
        return 1
    fi
}

# =============================================================================
# Dependency Checks
# =============================================================================

log_step "Checking dependencies"

check_command git
check_command python3
check_command curl

# Check for uv (preferred) or pip
if [ "$USE_UV" = "true" ]; then
    if command -v uv &> /dev/null; then
        INSTALLER="uv"
        echo "Using uv for package management"
    else
        log_warn "uv not found, falling back to pip"
        INSTALLER="pip"
    fi
else
    INSTALLER="pip"
    echo "Using pip for package management"
fi

echo "Python version: $(python3 --version)"
echo "Workspace: $WORKSPACE"
echo "Plugin directory: $PLUGIN_DIR"
echo "Runner type: $RUNNER_TYPE"

# =============================================================================
# Clone ColdFront
# =============================================================================

if [ -d "$COLDFRONT_DIR" ]; then
    log_step "ColdFront directory exists, checking version"
    cd "$COLDFRONT_DIR"
    CURRENT_TAG=$(git describe --tags --exact-match 2>/dev/null || echo "unknown")
    if [ "$CURRENT_TAG" = "v$COLDFRONT_VERSION" ]; then
        echo "ColdFront v$COLDFRONT_VERSION already checked out"
    else
        log_warn "ColdFront exists but is at $CURRENT_TAG, checking out v$COLDFRONT_VERSION"
        git fetch --tags
        git checkout "v$COLDFRONT_VERSION"
    fi
else
    log_step "Cloning ColdFront v$COLDFRONT_VERSION"
    cd "$WORKSPACE"
    git clone --depth 1 --branch "v$COLDFRONT_VERSION" "$COLDFRONT_REPO" coldfront
fi

cd "$COLDFRONT_DIR"

# =============================================================================
# Create Virtual Environment
# =============================================================================

log_step "Setting up Python virtual environment"

if [ "$INSTALLER" = "uv" ]; then
    # uv creates .venv automatically when running commands
    if [ ! -d ".venv" ]; then
        uv venv
    fi
    echo "Virtual environment ready at $COLDFRONT_DIR/.venv"
else
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    pip install --upgrade pip
    echo "Virtual environment activated"
fi

# =============================================================================
# Install Dependencies
# =============================================================================

log_step "Installing ColdFront and plugin"

if [ "$INSTALLER" = "uv" ]; then
    # Install ColdFront
    uv pip install -e .
    
    # Install the plugin
    uv pip install -e "$PLUGIN_DIR"
else
    source .venv/bin/activate
    pip install -e .
    pip install -e "$PLUGIN_DIR"
fi

# =============================================================================
# Configure ColdFront
# =============================================================================

log_step "Configuring ColdFront local_settings.py"

LOCAL_SETTINGS="$COLDFRONT_DIR/coldfront/config/local_settings.py"
SETTINGS_TEMPLATE="$SCRIPT_DIR/local_settings.py.template"

if [ -f "$SETTINGS_TEMPLATE" ]; then
    cp "$SETTINGS_TEMPLATE" "$LOCAL_SETTINGS"
    echo "Copied settings from template"
else
    # Create minimal settings inline
    cat > "$LOCAL_SETTINGS" << 'EOF'
# Generated by setup_environment.sh for testing
INSTALLED_APPS += ['coldfront_orcd_direct_charge']

# Plugin settings
AUTO_PI_ENABLE = True
AUTO_DEFAULT_PROJECT_ENABLE = True

# Center branding
CENTER_NAME = 'MIT ORCD Rental Services'

# API support
PLUGIN_API = True
EOF
    echo "Created minimal local_settings.py"
fi

# Add plugin URLs to ColdFront
URLS_FILE="$COLDFRONT_DIR/coldfront/config/urls.py"
if ! grep -q "coldfront_orcd_direct_charge" "$URLS_FILE"; then
    log_step "Adding plugin URLs to ColdFront"
    
    # Add import and URL pattern
    sed -i.bak '/^from django.conf import settings/a\
from django.conf import settings as django_settings
' "$URLS_FILE"
    
    # Append URL pattern at the end
    cat >> "$URLS_FILE" << 'EOF'

# ORCD Direct Charge Plugin URLs (added by setup_environment.sh)
if "coldfront_orcd_direct_charge" in django_settings.INSTALLED_APPS:
    from django.urls import include
    urlpatterns.append(path("nodes/", include("coldfront_orcd_direct_charge.urls")))
EOF
    echo "Added plugin URL patterns"
else
    echo "Plugin URLs already configured"
fi

# =============================================================================
# Apply Migrations
# =============================================================================

log_step "Applying database migrations"

if [ "$INSTALLER" = "uv" ]; then
    uv run coldfront migrate --no-input
else
    source "$COLDFRONT_DIR/.venv/bin/activate"
    coldfront migrate --no-input
fi

# =============================================================================
# Initialize Database (initial_setup, manager groups, fixtures)
# =============================================================================

if [ "$SKIP_INIT" != "true" ]; then
    log_step "Initializing database"
    
    # Call the modular initialization script
    INIT_SCRIPT="$SCRIPT_DIR/initialize_database.sh"
    if [ -f "$INIT_SCRIPT" ]; then
        # Export variables needed by initialize_database.sh
        export COLDFRONT_DIR
        export PLUGIN_DIR
        export INSTALLER
        
        # Run the initialization script
        bash "$INIT_SCRIPT"
    else
        log_warn "initialize_database.sh not found, running basic initialization"
        
        # Fallback: run basic initialization inline
        if [ "$INSTALLER" = "uv" ]; then
            echo 'yes' | uv run coldfront initial_setup || log_warn "initial_setup may have already been run"
            uv run coldfront setup_rental_manager --create-group || true
            uv run coldfront setup_billing_manager --create-group || true
            uv run coldfront setup_rate_manager --create-group || true
            uv run coldfront loaddata node_types || log_warn "Could not load node_types fixture"
            uv run coldfront loaddata gpu_node_instances || log_warn "Could not load gpu_node_instances fixture"
            uv run coldfront loaddata cpu_node_instances || log_warn "Could not load cpu_node_instances fixture"
        else
            source "$COLDFRONT_DIR/.venv/bin/activate"
            echo 'yes' | coldfront initial_setup || log_warn "initial_setup may have already been run"
            coldfront setup_rental_manager --create-group || true
            coldfront setup_billing_manager --create-group || true
            coldfront setup_rate_manager --create-group || true
            coldfront loaddata node_types || log_warn "Could not load node_types fixture"
            coldfront loaddata gpu_node_instances || log_warn "Could not load gpu_node_instances fixture"
            coldfront loaddata cpu_node_instances || log_warn "Could not load cpu_node_instances fixture"
        fi
    fi
else
    echo "Skipping database initialization (SKIP_INIT=true)"
fi

# =============================================================================
# Start Server
# =============================================================================

if [ "$SKIP_SERVER" != "true" ]; then
    log_step "Starting development server on port $SERVER_PORT"
    
    # Kill any existing server on the port
    if command -v lsof &> /dev/null; then
        lsof -ti:$SERVER_PORT | xargs kill -9 2>/dev/null || true
    fi
    
    # Start server in background
    cd "$COLDFRONT_DIR"
    if [ "$INSTALLER" = "uv" ]; then
        nohup uv run coldfront runserver "0.0.0.0:$SERVER_PORT" > /tmp/coldfront_server.log 2>&1 &
    else
        source .venv/bin/activate
        nohup coldfront runserver "0.0.0.0:$SERVER_PORT" > /tmp/coldfront_server.log 2>&1 &
    fi
    SERVER_PID=$!
    echo "Server started with PID $SERVER_PID"
    
    # Wait for server to be ready
    log_step "Waiting for server to be ready"
    MAX_WAIT=60
    WAITED=0
    while [ $WAITED -lt $MAX_WAIT ]; do
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$SERVER_PORT/" 2>/dev/null | grep -q "^[23]"; then
            echo "Server is ready!"
            break
        fi
        sleep 1
        WAITED=$((WAITED + 1))
        echo -n "."
    done
    echo ""
    
    if [ $WAITED -ge $MAX_WAIT ]; then
        log_error "Server did not start within ${MAX_WAIT}s"
        echo "Server log:"
        cat /tmp/coldfront_server.log
        exit 1
    fi
else
    echo "Skipping server start (SKIP_SERVER=true)"
fi

# =============================================================================
# Create Environment Activation Script
# =============================================================================

log_step "Creating environment activation script"

ACTIVATE_SCRIPT="$COLDFRONT_DIR/activate_env.sh"

cat > "$ACTIVATE_SCRIPT" << EOF
#!/usr/bin/env bash
# Environment activation script for ColdFront with ORCD plugin
# Generated by setup_environment.sh
#
# Usage: source $ACTIVATE_SCRIPT
#

# Activate Python virtual environment
source "$COLDFRONT_DIR/.venv/bin/activate"

# Set Django settings module
export DJANGO_SETTINGS_MODULE=coldfront.config.settings

# Set Python path to include ColdFront
export PYTHONPATH="$COLDFRONT_DIR:\${PYTHONPATH:-}"

# Plugin location for reference
export ORCD_PLUGIN_DIR="$PLUGIN_DIR"

# Print confirmation
echo "ColdFront environment activated"
echo "  DJANGO_SETTINGS_MODULE=\$DJANGO_SETTINGS_MODULE"
echo "  PYTHONPATH includes: $COLDFRONT_DIR"
EOF

chmod +x "$ACTIVATE_SCRIPT"
echo "Created activation script: $ACTIVATE_SCRIPT"

# =============================================================================
# Summary
# =============================================================================

log_step "Setup complete!"

echo "ColdFront: $COLDFRONT_DIR"
echo "Plugin: $PLUGIN_DIR"
echo "Activation script: $ACTIVATE_SCRIPT"
if [ "$SKIP_SERVER" != "true" ]; then
    echo "Server: http://localhost:$SERVER_PORT/"
fi
echo ""
echo "To activate the environment:"
echo "  source $ACTIVATE_SCRIPT"
echo ""
echo "To run tests:"
echo "  cd $PLUGIN_DIR"
echo "  ./tests/run_all_tests.sh"

