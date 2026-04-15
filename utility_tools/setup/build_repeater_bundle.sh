#!/bin/bash
#
# Build Repeater Bundle
# Creates a tarball with all files needed to run the repeater on a Pi Zero W.
#
# Gathers files from across the project root into a staging directory,
# then creates repeater_bundle.tar.gz. Follows the same pattern as
# build_scanner_bundle.sh.
#
# Usage:
#   ./utility_tools/setup/build_repeater_bundle.sh
#
# Output: repeater_bundle.tar.gz in the project root

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUNDLE_NAME="repeater_bundle"
OUTPUT="$PROJECT_ROOT/${BUNDLE_NAME}.tar.gz"

cd "$PROJECT_ROOT"

echo -e "${CYAN}Building repeater bundle from: $PROJECT_ROOT${NC}"

STAGING=$(mktemp -d)
DEST="$STAGING/$BUNDLE_NAME"
mkdir -p "$DEST"

MISSING=0
require_file() {
    if [ ! -f "$1" ]; then
        echo -e "${RED}  MISSING: $1${NC}"
        MISSING=$((MISSING + 1))
    fi
}

# ---------------------------------------------------------------
# Validate required files exist before bundling
# ---------------------------------------------------------------
echo -e "${CYAN}  Validating required files...${NC}"

require_file "repeater.py"
require_file "lora/__init__.py"
require_file "lora/packet_handler.py"
require_file "lora/node_types.py"
require_file "lora/collision_avoidance.py"
require_file "utils/__init__.py"
require_file "utils/oled_display.py"
require_file "configs/config.repeater.py"
require_file "configs/requirements.repeater.txt"
require_file "utility_tools/setup/repeater/run_repeater.py"
require_file "utility_tools/setup/repeater/build_cython.py"
require_file "utility_tools/setup/repeater/setup_repeater.sh"
require_file "utils/waveshare_monitor.py"

if [ "$MISSING" -gt 0 ]; then
    echo -e "${RED}  $MISSING required file(s) missing — aborting bundle${NC}"
    rm -rf "$STAGING"
    exit 1
fi

echo -e "${GREEN}  All required files found${NC}"

# ---------------------------------------------------------------
# Main application file
# ---------------------------------------------------------------
echo -e "${CYAN}  Packaging repeater application...${NC}"

cp repeater.py "$DEST/"

# ---------------------------------------------------------------
# Repeater setup & build utilities (from utility_tools/setup/repeater/)
# ---------------------------------------------------------------
echo -e "${CYAN}  Packaging setup utilities...${NC}"

REPEATER_SETUP="$PROJECT_ROOT/utility_tools/setup/repeater"

for f in run_repeater.py build_cython.py setup_repeater.sh setup_pisugar_schedule.sh; do
    if [ -f "$REPEATER_SETUP/$f" ]; then
        cp "$REPEATER_SETUP/$f" "$DEST/"
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
# Utils (config template + oled display + pisugar monitor)
# ---------------------------------------------------------------
echo -e "${CYAN}  Packaging utils/...${NC}"

mkdir -p "$DEST/utils"
cp utils/__init__.py "$DEST/utils/"
cp utils/oled_display.py "$DEST/utils/"
cp utils/waveshare_monitor.py "$DEST/utils/"
cp configs/config.repeater.py "$DEST/utils/config.repeater.py"

# Include pisugar_monitor if it exists (optional)
if [ -f "utils/pisugar_monitor.py" ]; then
    cp utils/pisugar_monitor.py "$DEST/utils/"
    echo -e "${GREEN}    Included utils/pisugar_monitor.py${NC}"
else
    echo -e "${CYAN}    pisugar_monitor.py not found (optional)${NC}"
fi

# ---------------------------------------------------------------
# Configs (requirements)
# ---------------------------------------------------------------
echo -e "${CYAN}  Packaging configs...${NC}"

mkdir -p "$DEST/configs"
cp configs/requirements.repeater.txt "$DEST/configs/"

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
tar tzf "$OUTPUT" | head -40
TOTAL=$(tar tzf "$OUTPUT" | wc -l)
if [ "$TOTAL" -gt 40 ]; then
    echo "  ... and $((TOTAL - 40)) more files"
fi
SIZE=$(du -h "$OUTPUT" | cut -f1)
echo -e "\n${GREEN}Size: $SIZE${NC}"
echo -e "${GREEN}Total files: $TOTAL${NC}"
echo -e "${CYAN}Upload this file to the SFTP server root.${NC}"
