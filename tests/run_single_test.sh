#!/bin/bash
# Run a single test file
# Usage: ./run_single_test.sh test_packet_serialization.py

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

if [ -z "$1" ]; then
    echo "Usage: ./run_single_test.sh <test_file.py>"
    echo ""
    echo "Available tests:"
    echo "  test_packet_serialization.py"
    echo "  test_crc_validation.py"
    echo "  test_multi_packet.py"
    echo "  test_duplicate_detection.py"
    echo "  test_repeater_logic.py"
    exit 1
fi

TEST_FILE=$1

if [ ! -f "$TEST_FILE" ]; then
    echo "Error: Test file '$TEST_FILE' not found"
    exit 1
fi

echo "========================================================================"
echo "Running: $TEST_FILE"
echo "========================================================================"
echo ""

python3 "$TEST_FILE"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ TEST PASSED"
else
    echo "❌ TEST FAILED"
fi

exit $EXIT_CODE
