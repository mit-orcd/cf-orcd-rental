#!/usr/bin/env bash
#
# Smoke Test: HTTP Connectivity and Content Verification
# Verifies the server responds and contains expected content
#
# Expected patterns are extracted from plugin templates.
# If templates change, update the patterns below accordingly.
#

set -e  # Exit on first error
set -u  # Error on undefined variables

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
ENDPOINT="/"
TIMEOUT="${TIMEOUT:-10}"

# Full URL to test
TEST_URL="${BASE_URL}${ENDPOINT}"

echo "========================================"
echo "  Smoke Test: HTTP Connectivity"
echo "========================================"
echo ""
echo "Testing: $TEST_URL"
echo "Timeout: ${TIMEOUT}s"
echo ""

# Check if curl is available
if ! command -v curl &> /dev/null; then
    echo "ERROR: curl is not installed"
    exit 1
fi

# Create temp file for response body
RESPONSE_FILE=$(mktemp)
trap "rm -f $RESPONSE_FILE" EXIT

# Make the request and capture HTTP status code and body
HTTP_STATUS=$(curl -s -o "$RESPONSE_FILE" -w "%{http_code}" \
    --connect-timeout "$TIMEOUT" \
    --max-time "$TIMEOUT" \
    "$TEST_URL" 2>/dev/null) || {
    echo "FAILED: Could not connect to $TEST_URL"
    echo ""
    echo "Possible causes:"
    echo "  - Server is not running"
    echo "  - Wrong port or hostname"
    echo "  - Firewall blocking connection"
    exit 1
}

echo "HTTP Status: $HTTP_STATUS"

# Check for successful response (2xx or 3xx)
if [[ ! "$HTTP_STATUS" =~ ^[23] ]]; then
    echo ""
    echo "FAILED: Server responded with HTTP $HTTP_STATUS (expected 2xx or 3xx)"
    exit 1
fi

echo ""
echo "========================================"
echo "  Content Verification"
echo "========================================"
echo ""

# Define expected patterns with source references
# Update these if the corresponding templates change
#
# Format: "PATTERN|SOURCE_FILE:LINE"
PATTERNS=(
    # From templates/common/base.html:44
    "ORCD Rental Portal|templates/common/base.html:44"
    
    # From templates/portal/nonauthorized_home.html:7
    "Log In To MIT ORCD Rental Portal|templates/portal/nonauthorized_home.html:7"
    
    # From templates/portal/nonauthorized_home.html:18
    "About the Rental Portal|templates/portal/nonauthorized_home.html:18"
    
    # From templates/portal/nonauthorized_home.html:20
    "The Rental Portal lets you rent dedicated GPU and CPU resources|templates/portal/nonauthorized_home.html:20"
)

# Track results
PATTERN_PASSED=0
PATTERN_FAILED=0
FAILED_PATTERNS=""

for pattern_entry in "${PATTERNS[@]}"; do
    # Split pattern and source
    PATTERN="${pattern_entry%%|*}"
    SOURCE="${pattern_entry##*|}"
    
    if grep -q "$PATTERN" "$RESPONSE_FILE"; then
        echo -e "  ✓ Found: \"$PATTERN\""
        PATTERN_PASSED=$((PATTERN_PASSED + 1))
    else
        echo -e "  ✗ Missing: \"$PATTERN\" (from $SOURCE)"
        PATTERN_FAILED=$((PATTERN_FAILED + 1))
        FAILED_PATTERNS="$FAILED_PATTERNS\n    - $PATTERN"
    fi
done

echo ""
echo "Patterns: $PATTERN_PASSED passed, $PATTERN_FAILED failed"
echo ""

# Final result
if [ $PATTERN_FAILED -gt 0 ]; then
    echo "FAILED: Some expected content patterns were not found"
    echo ""
    echo "Missing patterns:$FAILED_PATTERNS"
    echo ""
    echo "If templates have changed, update the PATTERNS array in this test."
    exit 1
fi

echo "PASSED: Server responded with HTTP $HTTP_STATUS and all content patterns verified"
exit 0
