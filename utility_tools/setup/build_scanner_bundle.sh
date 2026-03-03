#!/bin/bash
#
# Build Scanner Bundle
# Creates a tarball with all files needed to run the scanner on a Pi Zero W.
#
# Gathers files from across the project root into a staging directory,
# then creates scanner_bundle.tar.gz. Follows the same pattern as
# build_server_bundle.sh.
#
# Usage:
#   ./utility_tools/setup/build_scanner_bundle.sh
#
# Output: scanner_bundle.tar.gz in the project root

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUNDLE_NAME="scanner_bundle"
OUTPUT="$PROJECT_ROOT/${BUNDLE_NAME}.tar.gz"

cd "$PROJECT_ROOT"

echo -e "${CYAN}Building scanner bundle from: $PROJECT_ROOT${NC}"

STAGING=$(mktemp -d)
DEST="$STAGING/$BUNDLE_NAME"
mkdir -p "$DEST"

# ---------------------------------------------------------------
# Main application
# ---------------------------------------------------------------
echo -e "${CYAN}  Packaging scanner application...${NC}"

cp scanner_queue.py "$DEST/"

# ---------------------------------------------------------------
# Scanner setup & build utilities (from utility_tools/setup/scanner/)
# ---------------------------------------------------------------
echo -e "${CYAN}  Packaging setup utilities...${NC}"

SCANNER_SETUP="$PROJECT_ROOT/utility_tools/setup/scanner"

for f in run_scanner.py build_cython.py setup_scanner.sh; do
    if [ -f "$SCANNER_SETUP/$f" ]; then
        cp "$SCANNER_SETUP/$f" "$DEST/"
    else
        echo -e "${RED}  WARNING: $SCANNER_SETUP/$f not found — skipping${NC}"
    fi
done

# ---------------------------------------------------------------
# LoRa packet handler package (from project root)
# ---------------------------------------------------------------
echo -e "${CYAN}  Packaging lora/ package...${NC}"

mkdir -p "$DEST/lora"
cp lora/__init__.py "$DEST/lora/"
cp lora/packet_handler.py "$DEST/lora/"
cp lora/node_types.py "$DEST/lora/"
cp lora/collision_avoidance.py "$DEST/lora/"

# ---------------------------------------------------------------
# Utils (config template only — scanner doesn't need api_client)
# ---------------------------------------------------------------
echo -e "${CYAN}  Packaging utils/...${NC}"

mkdir -p "$DEST/utils"
cp utils/__init__.py "$DEST/utils/"
cp configs/config.scanner.py "$DEST/utils/config.scanner.py"

# ---------------------------------------------------------------
# Configs (requirements)
# ---------------------------------------------------------------
echo -e "${CYAN}  Packaging configs...${NC}"

mkdir -p "$DEST/configs"
cp configs/requirements.scanner.txt "$DEST/configs/"

# ---------------------------------------------------------------
# Create empty log directory
# ---------------------------------------------------------------
mkdir -p "$DEST/log"

# ---------------------------------------------------------------
# Cleanup and create tarball
# ---------------------------------------------------------------

# Remove .DS_Store files
find "$DEST" -name '.DS_Store' -delete 2>/dev/null || true

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
echo -e "${GREEN}Total files: $TOTAL${NC}"
echo -e "${CYAN}Upload this file to the SFTP server root.${NC}"
