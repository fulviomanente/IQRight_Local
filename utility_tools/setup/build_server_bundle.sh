#!/bin/bash
#
# Build Server Bundle
# Creates a tarball with all files needed to run the IQRight server on a Pi 4B.
#
# The bundle contains two components:
#   1. LoraService  - CaptureLora.py (LoRa daemon)
#   2. WebApp       - mqtt_grid_web.py (Flask + SocketIO web interface)
#
# Usage:
#   ./utility_tools/setup/build_server_bundle.sh
#
# Output: server_bundle.tar.gz in the project root

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUNDLE_NAME="server_bundle"
OUTPUT="$PROJECT_ROOT/${BUNDLE_NAME}.tar.gz"

cd "$PROJECT_ROOT"

echo -e "${CYAN}Building server bundle from: $PROJECT_ROOT${NC}"

STAGING=$(mktemp -d)
DEST="$STAGING/$BUNDLE_NAME"
mkdir -p "$DEST"

# ---------------------------------------------------------------
# Component 1: LoraService (CaptureLora.py)
# ---------------------------------------------------------------
echo -e "${CYAN}  Packaging LoraService...${NC}"
LORA_DEST="$DEST/loraservice"
mkdir -p "$LORA_DEST"

# Main application
cp CaptureLora.py "$LORA_DEST/"

# LoRa packet handler package
mkdir -p "$LORA_DEST/lora"
cp lora/__init__.py "$LORA_DEST/lora/"
cp lora/packet_handler.py "$LORA_DEST/lora/"
cp lora/node_types.py "$LORA_DEST/lora/"
cp lora/collision_avoidance.py "$LORA_DEST/lora/"

# Utils (config + api_client + offline_data for data download)
mkdir -p "$LORA_DEST/utils"
cp utils/__init__.py "$LORA_DEST/utils/"
cp utils/config.py "$LORA_DEST/utils/"
cp utils/api_client.py "$LORA_DEST/utils/"
cp utils/offline_data.py "$LORA_DEST/utils/"

# Data files (encrypted student database + keys + credentials)
mkdir -p "$LORA_DEST/data"
for f in data/full_load.iqr data/offline_users.iqr data/credentials.key; do
    if [ -f "$f" ]; then
        cp "$f" "$LORA_DEST/data/"
    else
        echo -e "${RED}  WARNING: $f not found — skipping${NC}"
    fi
done

# offline.key may be at project root or in Meshstatic/data/
if [ -f "offline.key" ]; then
    cp "offline.key" "$LORA_DEST/data/"
elif [ -f "Meshstatic/data/offline.key" ]; then
    cp "Meshstatic/data/offline.key" "$LORA_DEST/data/"
else
    echo -e "${RED}  WARNING: offline.key not found — skipping${NC}"
fi

# Credential setup utility (for creating credentials.iqr on the server)
cp utility_tools/credential_setup.py "$LORA_DEST/"

# LoRa wiring test utility (for verifying RFM9x hardware before running services)
cp utility_tools/test_troubleshoot/RMF_WiringTest.py "$LORA_DEST/"

# ---------------------------------------------------------------
# Component 2: WebApp (mqtt_grid_web.py)
# ---------------------------------------------------------------
echo -e "${CYAN}  Packaging WebApp...${NC}"
WEB_DEST="$DEST/webapp"
mkdir -p "$WEB_DEST"

# Main application and forms
cp mqtt_grid_web.py "$WEB_DEST/"
cp forms.py "$WEB_DEST/"

# Utils (config + api_client + offline_data)
mkdir -p "$WEB_DEST/utils"
cp utils/__init__.py "$WEB_DEST/utils/"
cp utils/config.py "$WEB_DEST/utils/"
cp utils/api_client.py "$WEB_DEST/utils/"
cp utils/offline_data.py "$WEB_DEST/utils/"

# Templates
cp -r templates "$WEB_DEST/templates"

# Static assets (css, js, images, sounds)
cp -r static "$WEB_DEST/static"

# Translations (i18n)
cp -r translations "$WEB_DEST/translations"

# ---------------------------------------------------------------
# Shared: configs and requirements
# ---------------------------------------------------------------
echo -e "${CYAN}  Packaging configs...${NC}"
mkdir -p "$DEST/configs"
cp configs/requirements.server.txt "$DEST/configs/" 2>/dev/null || true

# Create LoraService-specific requirements
cat > "$DEST/configs/requirements.loraservice.txt" << 'EOF'
# IQRight LoraService (CaptureLora.py) Dependencies
python-dotenv>=1.0.0
pandas>=2.0.0
cryptography>=41.0.0
paho-mqtt>=1.6.1
aiohttp>=3.9.0
requests>=2.31.0
numpy>=1.24.0
adafruit-circuitpython-rfm9x>=2.2.0
adafruit-blinka>=8.0.0
google-cloud-secret-manager>=2.16.0
EOF

# Create WebApp-specific requirements
cat > "$DEST/configs/requirements.webapp.txt" << 'EOF'
# IQRight WebApp (mqtt_grid_web.py) Dependencies
python-dotenv>=1.0.0
pandas>=2.0.0
cryptography>=41.0.0
paho-mqtt>=1.6.1
flask>=3.0.0
flask-login>=0.6.0
flask-socketio>=5.3.0
flask-babel>=4.0.0
flask-wtf>=1.2.0
wtforms>=3.1.0
eventlet>=0.35.0
gunicorn>=21.2.0
gtts>=2.4.0
requests>=2.31.0
google-cloud-secret-manager>=2.16.0
EOF

# Create empty log directories
mkdir -p "$DEST/loraservice/log"
mkdir -p "$DEST/webapp/logs"

# Remove .DS_Store files
find "$DEST" -name '.DS_Store' -delete 2>/dev/null || true

# ---------------------------------------------------------------
# Create tarball
# ---------------------------------------------------------------
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