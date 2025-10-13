#!/bin/bash
# Master test runner - Run from project root
# Usage: ./run_tests.sh [local|all]

set -e

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================================================"
echo "LoRa Packet Protocol Test Suite"
echo "========================================================================"
echo ""

# Default to local tests
TEST_TYPE=${1:-local}

case "$TEST_TYPE" in
    local)
        echo -e "${YELLOW}Running LOCAL tests (no hardware required)...${NC}"
        echo ""
        cd tests
        ./run_all_local_tests.sh
        ;;

    all)
        echo -e "${YELLOW}Running ALL tests (local + hardware)...${NC}"
        echo ""

        # Run local tests first
        echo "Step 1: Local Tests"
        cd tests
        ./run_all_local_tests.sh

        echo ""
        echo "Step 2: Hardware Tests"
        echo "⚠️  Hardware tests not yet implemented"
        echo "    See LORA_TESTING.md for manual hardware test procedures"
        ;;

    *)
        echo "Usage: ./run_tests.sh [local|all]"
        echo ""
        echo "Options:"
        echo "  local  - Run local tests only (no hardware required) [DEFAULT]"
        echo "  all    - Run local + hardware tests"
        echo ""
        echo "Examples:"
        echo "  ./run_tests.sh          # Run local tests"
        echo "  ./run_tests.sh local    # Run local tests"
        echo "  ./run_tests.sh all      # Run all tests"
        exit 1
        ;;
esac

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
else
    echo "❌ SOME TESTS FAILED"
fi

exit $EXIT_CODE
