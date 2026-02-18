#!/bin/bash
#
# Build Scanner Bundle
# Creates a tarball with only the files needed to run the scanner on a Pi Zero W.
#
# Usage:
#   ./utility_tools/setup/build_scanner_bundle.sh
#
# Output: scanner_bundle.tar.gz in the project root

set -e

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUNDLE_NAME="scanner_bundle"
OUTPUT="$PROJECT_ROOT/${BUNDLE_NAME}.tar.gz"

cd "$PROJECT_ROOT"

SCANNER_SRC="$PROJECT_ROOT/utility_tools/setup/scanner"

if [ ! -d "$SCANNER_SRC" ]; then
    echo -e "${RED}Scanner source not found: $SCANNER_SRC${NC}"
    exit 1
fi

echo -e "${CYAN}Building scanner bundle from: $SCANNER_SRC${NC}"

# Also include configs/requirements.scanner.txt
STAGING=$(mktemp -d)
DEST="$STAGING/$BUNDLE_NAME"

# Copy the entire scanner directory
cp -r "$SCANNER_SRC" "$DEST"

# Add requirements file
mkdir -p "$DEST/configs"
cp configs/requirements.scanner.txt "$DEST/configs/"

# Create empty log directory
mkdir -p "$DEST/log"

# Remove .DS_Store files
find "$DEST" -name '.DS_Store' -delete 2>/dev/null || true

# Create tarball
cd "$STAGING"
tar czf "$OUTPUT" "$BUNDLE_NAME"

# Cleanup
rm -rf "$STAGING"

# Summary
echo ""
echo -e "${GREEN}Bundle created: $OUTPUT${NC}"
echo -e "${CYAN}Contents:${NC}"
tar tzf "$OUTPUT" | head -30
TOTAL=$(tar tzf "$OUTPUT" | wc -l)
if [ "$TOTAL" -gt 30 ]; then
    echo "  ... and $((TOTAL - 30)) more files"
fi
SIZE=$(du -h "$OUTPUT" | cut -f1)
echo -e "\n${GREEN}Size: $SIZE${NC}"
echo -e "${CYAN}Upload this file to the SFTP server root.${NC}"
