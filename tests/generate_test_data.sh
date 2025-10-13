#!/bin/bash
# Generate test data files with dummy student information

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "GENERATING TEST DATA"
echo "========================================================================"
echo ""

# Generate test data JSON
python3 test_data_generator.py --save test_data.json

echo ""
echo "✅ Test data generation complete!"
echo ""
echo "Generated files:"
echo "  - test_data.json (sample students, QR codes, commands)"
echo ""
echo "You can now use this data for testing by loading it in your test scripts."
