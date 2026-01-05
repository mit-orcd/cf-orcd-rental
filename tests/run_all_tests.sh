#!/usr/bin/env bash
#
# Master test runner - discovers and runs all tests
# Returns 0 if all tests pass, non-zero if any fail
#

set -u  # Error on undefined variables

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output (disabled if not a terminal)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    NC=''
fi

echo "========================================"
echo "  Running All Tests"
echo "========================================"
echo ""

# Track results
TOTAL=0
PASSED=0
FAILED=0
FAILED_TESTS=""

# Find all test.sh files in subdirectories
for test_script in "$SCRIPT_DIR"/*/test.sh; do
    # Skip if no matches (glob didn't expand)
    [ -e "$test_script" ] || continue
    
    # Get test name from directory
    test_dir="$(dirname "$test_script")"
    test_name="$(basename "$test_dir")"
    
    TOTAL=$((TOTAL + 1))
    
    echo -n "Running: $test_name ... "
    
    # Run the test and capture exit code
    if bash "$test_script" > /dev/null 2>&1; then
        echo -e "${GREEN}PASSED${NC}"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}FAILED${NC}"
        FAILED=$((FAILED + 1))
        FAILED_TESTS="$FAILED_TESTS $test_name"
    fi
done

# Summary
echo ""
echo "========================================"
echo "  Summary"
echo "========================================"
echo ""
echo "Total:  $TOTAL"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"

if [ $FAILED -gt 0 ]; then
    echo ""
    echo -e "${RED}Failed tests:${NC}$FAILED_TESTS"
    echo ""
    exit 1
fi

if [ $TOTAL -eq 0 ]; then
    echo ""
    echo -e "${YELLOW}Warning: No tests found${NC}"
    exit 0
fi

echo ""
echo -e "${GREEN}All tests passed!${NC}"
exit 0

