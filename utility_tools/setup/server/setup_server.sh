#!/bin/bash
#
# IQRight Server - Full Raspberry Pi 4B Setup
#
# Downloads the server bundle from SFTP and configures the entire system:
#   - System packages (Python, Nginx, etc.)
#   - LoraService: CaptureLora.py → /etc/iqright/LoraService/
#   - WebApp: mqtt_grid_web.py → /etc/iqright/WebApp/
#   - Separate Python virtual environments for each service
#   - Systemd services (auto-start with crash recovery)
#   - Nginx reverse proxy (port 80 → 8000)
#   - Node configuration (.env with server ID)
#
# Usage:
#   curl/scp this script to the Pi, then:
#   chmod +x setup_server.sh && sudo ./setup_server.sh
#
# Environment variables (optional overrides):
#   FTP_HOST      - FTP server IP (default: 192.168.7.151)
#   FTP_PORT      - FTP server port (default: 5009)
#   FTP_USER      - FTP username (default: fulviomanente)
#   FTP_PASS      - FTP password (default: 1234)
#   LORA_DIR      - LoraService install dir (default: /etc/iqright/LoraService)
#   WEB_DIR       - WebApp install dir (default: /etc/iqright/WebApp)
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Defaults
FTP_HOST="${FTP_HOST:-192.168.7.151}"
FTP_PORT="${FTP_PORT:-5009}"
FTP_USER="${FTP_USER:-fulviomanente}"
FTP_PASS="${FTP_PASS:-1234}"
LORA_DIR="${LORA_DIR:-/etc/iqright/LoraService}"
WEB_DIR="${WEB_DIR:-/etc/iqright/WebApp}"
BUNDLE_FILE="server_bundle.tar.gz"
RUN_USER="${SUDO_USER:-$(whoami)}"

# Print helpers
print_header() {
    echo ""
    echo -e "${BOLD}${BLUE}============================================================${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}============================================================${NC}"
    echo ""
}

print_step() {
    echo -e "${CYAN}[$1/$TOTAL_STEPS] $2${NC}"
}

print_success() {
    echo -e "  ${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "  ${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "  ${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "  ${CYAN}ℹ $1${NC}"
}

TOTAL_STEPS=11

# ------------------------------------------------------------------
# Step 1: System packages
# ------------------------------------------------------------------
install_system_packages() {
    print_step 1 "Installing system packages"

    apt update -qq

    PACKAGES="python3 python3-pip python3-venv python3-dev gcc ftp nginx mosquitto mosquitto-clients"
    apt install -y $PACKAGES

    print_success "System packages installed"
}

# ------------------------------------------------------------------
# Step 2: Download server bundle from SFTP
# ------------------------------------------------------------------
download_bundle() {
    print_step 2 "Downloading server bundle from FTP"
    print_info "Server: ${FTP_USER}@${FTP_HOST}:${FTP_PORT}"

    TMPDIR=$(mktemp -d)

    FTP_SCRIPT=$(mktemp)
    cat > "$FTP_SCRIPT" << EOF
user ${FTP_USER} ${FTP_PASS}
binary
lcd ${TMPDIR}
get ${BUNDLE_FILE}
bye
EOF

    ftp -n -v "$FTP_HOST" "$FTP_PORT" < "$FTP_SCRIPT"
    rm -f "$FTP_SCRIPT"

    if [ ! -f "${TMPDIR}/${BUNDLE_FILE}" ]; then
        print_error "Failed to download ${BUNDLE_FILE}"
        rm -rf "$TMPDIR"
        exit 1
    fi

    print_success "Downloaded ${BUNDLE_FILE}"
    DOWNLOAD_DIR="$TMPDIR"
}

# ------------------------------------------------------------------
# Step 3: Extract bundle and install files
# ------------------------------------------------------------------
extract_bundle() {
    print_step 3 "Extracting server bundle"

    # Extract to temp location
    EXTRACT_DIR=$(mktemp -d)
    tar xzf "${DOWNLOAD_DIR}/${BUNDLE_FILE}" -C "$EXTRACT_DIR"
    rm -rf "$DOWNLOAD_DIR"

    BUNDLE_DIR="$EXTRACT_DIR/server_bundle"

    # --- LoraService ---
    print_info "Installing LoraService to ${LORA_DIR}"
    mkdir -p "$LORA_DIR"

    # Copy LoraService files
    cp -r "$BUNDLE_DIR/loraservice/"* "$LORA_DIR/"

    # Create required directories
    mkdir -p "$LORA_DIR/log"
    mkdir -p "$LORA_DIR/data"

    # Copy configs for requirements
    mkdir -p "$LORA_DIR/configs"
    cp "$BUNDLE_DIR/configs/requirements.loraservice.txt" "$LORA_DIR/configs/"

    print_success "LoraService files installed to ${LORA_DIR}"

    # --- WebApp ---
    print_info "Installing WebApp to ${WEB_DIR}"
    mkdir -p "$WEB_DIR"

    # Copy WebApp files
    cp -r "$BUNDLE_DIR/webapp/"* "$WEB_DIR/"

    # Create required directories
    mkdir -p "$WEB_DIR/logs"

    # Copy configs for requirements
    mkdir -p "$WEB_DIR/configs"
    cp "$BUNDLE_DIR/configs/requirements.webapp.txt" "$WEB_DIR/configs/"

    print_success "WebApp files installed to ${WEB_DIR}"

    # Set ownership
    chown -R "$RUN_USER:$RUN_USER" /etc/iqright

    # Cleanup
    rm -rf "$EXTRACT_DIR"

    print_success "Bundle extracted and installed"
}

# ------------------------------------------------------------------
# Step 4: Create LoraService virtual environment
# ------------------------------------------------------------------
setup_loraservice_python() {
    print_step 4 "Setting up LoraService Python virtual environment"

    cd "$LORA_DIR"

    # Create venv as the service user
    sudo -u "$RUN_USER" python3 -m venv .venv
    print_success "LoraService venv created"

    # Install dependencies
    sudo -u "$RUN_USER" .venv/bin/pip install --upgrade pip 2>/dev/null || true

    if [ -f "configs/requirements.loraservice.txt" ]; then
        sudo -u "$RUN_USER" .venv/bin/pip install -r configs/requirements.loraservice.txt
        print_success "LoraService Python dependencies installed"
    else
        print_error "requirements.loraservice.txt not found"
        exit 1
    fi
}

# ------------------------------------------------------------------
# Step 5: Create WebApp virtual environment
# ------------------------------------------------------------------
setup_webapp_python() {
    print_step 5 "Setting up WebApp Python virtual environment"

    cd "$WEB_DIR"

    # Create venv as the service user
    sudo -u "$RUN_USER" python3 -m venv .venv
    print_success "WebApp venv created"

    # Install dependencies
    sudo -u "$RUN_USER" .venv/bin/pip install --upgrade pip 2>/dev/null || true

    if [ -f "configs/requirements.webapp.txt" ]; then
        sudo -u "$RUN_USER" .venv/bin/pip install -r configs/requirements.webapp.txt
        print_success "WebApp Python dependencies installed"
    else
        print_error "requirements.webapp.txt not found"
        exit 1
    fi
}

# ------------------------------------------------------------------
# Step 6: Configure server node (.env)
# ------------------------------------------------------------------
configure_node() {
    print_step 6 "Configuring server node"

    # Server is always Node ID 1
    cat > "${LORA_DIR}/.env" << 'EOF'
# IQRight Server Configuration
LORA_NODE_TYPE=SERVER
LORA_NODE_ID=1
LORA_FREQUENCY=915.23
LORA_TX_POWER=23
LORA_TTL=3
LORA_ENABLE_CA=TRUE
API_ENABLED=TRUE
EOF

    chown "$RUN_USER:$RUN_USER" "${LORA_DIR}/.env"
    print_success "Server .env created at ${LORA_DIR}/.env (Node ID: 1)"

    # WebApp also needs access to config — symlink the .env
    ln -sf "${LORA_DIR}/.env" "${WEB_DIR}/.env"
    print_success "WebApp .env symlinked to LoraService .env"
}

# ------------------------------------------------------------------
# Step 7: Configure credentials (API + MQTT secrets)
# ------------------------------------------------------------------
configure_credentials() {
    print_step 7 "Configuring service credentials"

    CRED_KEY="${LORA_DIR}/data/credentials.key"
    CRED_FILE="${LORA_DIR}/data/credentials.iqr"
    CRED_TOOL="${LORA_DIR}/credential_setup.py"

    if [ ! -f "$CRED_TOOL" ]; then
        print_error "credential_setup.py not found in bundle"
        return
    fi

    # Check if credentials.iqr already exists (re-run scenario)
    if [ -f "$CRED_FILE" ]; then
        print_info "credentials.iqr already exists"
        read -p "  Overwrite existing credentials? (y/N): " OVERWRITE
        if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
            print_info "Keeping existing credentials"
            return
        fi
    fi

    # Ensure credentials.key exists
    if [ ! -f "$CRED_KEY" ]; then
        print_warning "credentials.key not found — generating new key"
        sudo -u "$RUN_USER" "${LORA_DIR}/.venv/bin/python3" "$CRED_TOOL" \
            --generate-key --key-path "$CRED_KEY"
    fi

    echo ""
    echo -e "  ${BOLD}Service Credentials Setup${NC}"
    echo -e "  These are used for API authentication and MQTT broker access."
    echo ""

    # Prompt for each required credential
    read -p "  API Username [localapi]: " API_USER
    API_USER="${API_USER:-localapi}"

    read -s -p "  API Password: " API_PASS
    echo ""

    read -p "  MQTT Username [IQRight]: " MQTT_USER
    MQTT_USER="${MQTT_USER:-IQRight}"

    read -s -p "  MQTT Password [123456]: " MQTT_PASS
    echo ""
    MQTT_PASS="${MQTT_PASS:-123456}"

    read -p "  Offline API User [localuser]: " OFFLINE_USER
    OFFLINE_USER="${OFFLINE_USER:-localuser}"

    read -s -p "  Offline API Password: " OFFLINE_PASS
    echo ""

    read -p "  Auth Service URL [https://integration.iqright.app/api]: " AUTH_URL
    AUTH_URL="${AUTH_URL:-https://integration.iqright.app/api}"

    # Create credentials.iqr with all secrets
    sudo -u "$RUN_USER" "${LORA_DIR}/.venv/bin/python3" "$CRED_TOOL" \
        --add apiUsername "$API_USER" \
        --key-path "$CRED_KEY" --credentials-path "$CRED_FILE"

    sudo -u "$RUN_USER" "${LORA_DIR}/.venv/bin/python3" "$CRED_TOOL" \
        --add apiPassword "$API_PASS" \
        --key-path "$CRED_KEY" --credentials-path "$CRED_FILE"

    sudo -u "$RUN_USER" "${LORA_DIR}/.venv/bin/python3" "$CRED_TOOL" \
        --add mqttUsername "$MQTT_USER" \
        --key-path "$CRED_KEY" --credentials-path "$CRED_FILE"

    sudo -u "$RUN_USER" "${LORA_DIR}/.venv/bin/python3" "$CRED_TOOL" \
        --add mqttpassword "$MQTT_PASS" \
        --key-path "$CRED_KEY" --credentials-path "$CRED_FILE"

    sudo -u "$RUN_USER" "${LORA_DIR}/.venv/bin/python3" "$CRED_TOOL" \
        --add offlineIdUser "$OFFLINE_USER" \
        --key-path "$CRED_KEY" --credentials-path "$CRED_FILE"

    sudo -u "$RUN_USER" "${LORA_DIR}/.venv/bin/python3" "$CRED_TOOL" \
        --add offlinePassword "$OFFLINE_PASS" \
        --key-path "$CRED_KEY" --credentials-path "$CRED_FILE"

    sudo -u "$RUN_USER" "${LORA_DIR}/.venv/bin/python3" "$CRED_TOOL" \
        --add authServiceUrl "$AUTH_URL" \
        --key-path "$CRED_KEY" --credentials-path "$CRED_FILE"

    print_success "Credentials encrypted and stored at ${CRED_FILE}"

    # Symlink so WebApp can find credentials via its own LORASERVICE_PATH
    # (WebApp's config also points to /etc/iqright/LoraService/data/)
    print_success "Credentials available to both LoraService and WebApp"
}

# ------------------------------------------------------------------
# Step 8: Download data files from API
# ------------------------------------------------------------------
download_data_files() {
    print_step 8 "Downloading data files from API"
    print_info "This will download full_load.iqr and offline_users.iqr from the integration API"

    cd "$LORA_DIR"

    # Run a Python script that imports OfflineData and triggers the downloads
    sudo -u "$RUN_USER" "${LORA_DIR}/.venv/bin/python3" -c "
import sys, os
os.chdir('${LORA_DIR}')
from utils.offline_data import OfflineData

print('  Initializing OfflineData (downloads full_load.iqr)...')
offlineData = OfflineData()
print('  full_load.iqr: OK')

print('  Downloading offline_users.iqr...')
offlineData.getOfflineUsers()
print('  offline_users.iqr: OK')

print('  Data files downloaded successfully.')
" 2>&1

    if [ $? -eq 0 ]; then
        print_success "Data files downloaded to ${LORA_DIR}/data/"
    else
        print_warning "Data download failed — the bundled data files will be used instead"
        print_info "You can retry later by restarting the services (they auto-download on startup)"
    fi
}

# ------------------------------------------------------------------
# Step 9: Create systemd services
# ------------------------------------------------------------------
create_services() {
    print_step 9 "Creating systemd services"

    # --- LoraService (CaptureLora.py) ---
    cat > /etc/systemd/system/iqright-lora.service << EOF
[Unit]
Description=IQRight LoRa Service (CaptureLora)
After=network.target mosquitto.service
Wants=mosquitto.service

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${LORA_DIR}
EnvironmentFile=${LORA_DIR}/.env
ExecStart=${LORA_DIR}/.venv/bin/python3 ${LORA_DIR}/CaptureLora.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=iqright-lora

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable iqright-lora.service
    print_success "iqright-lora.service created and enabled"

    # --- WebApp (mqtt_grid_web.py via gunicorn) ---
    cat > /etc/systemd/system/iqright-web.service << EOF
[Unit]
Description=IQRight Web Application (Gunicorn + EventLet)
After=network.target mosquitto.service
Wants=mosquitto.service

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${WEB_DIR}
EnvironmentFile=${LORA_DIR}/.env
ExecStart=${WEB_DIR}/.venv/bin/gunicorn --worker-class eventlet -w 1 -b 127.0.0.1:8000 mqtt_grid_web:app
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=iqright-web

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable iqright-web.service
    print_success "iqright-web.service created and enabled"
}

# ------------------------------------------------------------------
# Step 10: Configure Nginx reverse proxy
# ------------------------------------------------------------------
configure_nginx() {
    print_step 10 "Configuring Nginx reverse proxy"

    # Remove default site
    rm -f /etc/nginx/sites-enabled/default

    cat > /etc/nginx/sites-available/iqright << 'EOF'
server {
    listen 80;
    server_name _;

    # Proxy to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support for Socket.IO
    location /socket.io {
        proxy_pass http://127.0.0.1:8000/socket.io;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Serve static files directly (bypass Gunicorn for performance)
    location /static {
        alias /etc/iqright/WebApp/static;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

    ln -sf /etc/nginx/sites-available/iqright /etc/nginx/sites-enabled/iqright

    # Test nginx config
    if nginx -t 2>/dev/null; then
        print_success "Nginx configuration valid"
    else
        print_error "Nginx configuration test failed"
        nginx -t
        exit 1
    fi

    systemctl enable nginx
    systemctl restart nginx
    print_success "Nginx configured and restarted (port 80 → 8000)"
}

# ------------------------------------------------------------------
# Step 11: Configure Mosquitto MQTT broker
# ------------------------------------------------------------------
configure_mosquitto() {
    print_step 11 "Configuring Mosquitto MQTT broker"

    # Create password file FIRST (must exist before Mosquitto reads the config)
    # Always recreate to avoid corrupt/empty file issues
    # -c = create new file, -b = batch mode (password on command line)
    mosquitto_passwd -c -b /etc/mosquitto/passwd IQRight 123456
    chown mosquitto:mosquitto /etc/mosquitto/passwd
    chmod 640 /etc/mosquitto/passwd
    print_success "MQTT password file created (owner: mosquitto, mode: 640)"

    # Mosquitto 2.0+ no longer allows anonymous by default and requires
    # explicit listener config. Instead of adding a drop-in that may
    # conflict with the main mosquitto.conf, we write a minimal main config.
    MOSQUITTO_CONF="/etc/mosquitto/mosquitto.conf"

    # Back up original config
    if [ -f "$MOSQUITTO_CONF" ] && [ ! -f "${MOSQUITTO_CONF}.bak" ]; then
        cp "$MOSQUITTO_CONF" "${MOSQUITTO_CONF}.bak"
        print_info "Original mosquitto.conf backed up"
    fi

    cat > "$MOSQUITTO_CONF" << 'EOF'
# IQRight Mosquitto Configuration
# Original config backed up to mosquitto.conf.bak

# Persistence
persistence true
persistence_location /var/lib/mosquitto/

# Logging
log_dest file /var/log/mosquitto/mosquitto.log
log_type warning
log_type error
log_type notice

# Listener — bind to localhost only (no external access)
listener 1883 127.0.0.1

# Authentication
allow_anonymous false
password_file /etc/mosquitto/passwd

# Include any additional drop-in configs
include_dir /etc/mosquitto/conf.d
EOF

    # Remove our old drop-in if it exists (avoid double-listener conflict)
    rm -f /etc/mosquitto/conf.d/iqright.conf

    # Ensure log directory exists with correct permissions
    mkdir -p /var/log/mosquitto
    chown mosquitto:mosquitto /var/log/mosquitto

    # Ensure persistence directory exists
    mkdir -p /var/lib/mosquitto
    chown mosquitto:mosquitto /var/lib/mosquitto

    # Test the config before restarting
    if mosquitto -c "$MOSQUITTO_CONF" -t 2>/dev/null; then
        print_success "Mosquitto configuration valid"
    else
        print_warning "Mosquitto config test returned non-zero (may still work)"
    fi

    systemctl enable mosquitto
    systemctl restart mosquitto

    # Verify it actually started
    sleep 2
    if systemctl is-active --quiet mosquitto; then
        print_success "Mosquitto running (port 1883, localhost only)"
    else
        print_error "Mosquitto failed to start — check: sudo cat /var/log/mosquitto/mosquitto.log"
        print_info "You can also try: mosquitto -c /etc/mosquitto/mosquitto.conf -v"
    fi
}

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
main() {
    print_header "IQRight Server - Raspberry Pi 4B Setup"

    # Must run as root
    if [ "$EUID" -ne 0 ]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi

    echo -e "  ${CYAN}FTP Server:${NC}     ${FTP_HOST}:${FTP_PORT}"
    echo -e "  ${CYAN}LoraService:${NC}    ${LORA_DIR}"
    echo -e "  ${CYAN}WebApp:${NC}         ${WEB_DIR}"
    echo -e "  ${CYAN}Run as user:${NC}    ${RUN_USER}"
    echo ""

    # Check hardware
    if [ -f /proc/device-tree/model ]; then
        MODEL=$(cat /proc/device-tree/model | tr -d '\0')
        print_info "Hardware: ${MODEL}"
    else
        print_warning "This doesn't appear to be a Raspberry Pi. Continuing anyway..."
    fi

    echo ""
    read -p "  Press Enter to start setup (Ctrl+C to cancel)... "
    echo ""

    install_system_packages
    echo ""
    download_bundle
    echo ""
    extract_bundle
    echo ""
    setup_loraservice_python
    echo ""
    setup_webapp_python
    echo ""
    configure_node
    echo ""
    configure_credentials
    echo ""
    download_data_files
    echo ""
    create_services
    echo ""
    configure_nginx
    echo ""
    configure_mosquitto

    # Summary
    print_header "Setup Complete!"

    echo -e "  ${GREEN}LoraService installed to: ${LORA_DIR}${NC}"
    echo -e "  ${GREEN}WebApp installed to:      ${WEB_DIR}${NC}"
    echo -e "  ${GREEN}Server Node ID:           1${NC}"
    echo ""
    echo -e "  ${CYAN}Services:${NC}"
    echo -e "    ${GREEN}iqright-lora${NC}  - LoRa packet receiver (CaptureLora.py)"
    echo -e "    ${GREEN}iqright-web${NC}   - Web interface (Gunicorn + eventlet on :8000)"
    echo -e "    ${GREEN}nginx${NC}         - Reverse proxy (port 80 → 8000)"
    echo -e "    ${GREEN}mosquitto${NC}     - MQTT broker (port 1883, localhost only)"
    echo ""
    echo -e "  ${CYAN}Service management:${NC}"
    echo -e "    sudo systemctl status  iqright-lora"
    echo -e "    sudo systemctl status  iqright-web"
    echo -e "    sudo systemctl restart iqright-lora"
    echo -e "    sudo systemctl restart iqright-web"
    echo ""
    echo -e "  ${CYAN}Logs:${NC}"
    echo -e "    journalctl -u iqright-lora -f"
    echo -e "    journalctl -u iqright-web -f"
    echo -e "    tail -f ${LORA_DIR}/log/IQRight_Daemon.debug"
    echo -e "    tail -f ${WEB_DIR}/logs/IQRight_FE_WEB.debug"
    echo ""
    echo -e "  ${CYAN}Web interface:${NC}"
    echo -e "    http://<server-ip>/"
    echo ""
    echo -e "  ${CYAN}Before starting:${NC}"
    echo -e "    1. Copy encrypted data files to ${LORA_DIR}/data/"
    echo -e "       (full_load.iqr, offline.key, offline_users.iqr)"
    echo -e "    2. Review .env at ${LORA_DIR}/.env"
    echo -e "    3. Start services: sudo systemctl start iqright-lora iqright-web"
    echo ""
    echo -e "  ${CYAN}To update server files later:${NC}"
    echo -e "    Run this script again — it will overwrite the application files."
    echo ""
    echo -e "  ${YELLOW}Reboot recommended to verify all services start automatically.${NC}"
    echo ""
    read -p "  Reboot now? (y/N): " REBOOT
    if [[ "$REBOOT" =~ ^[Yy]$ ]]; then
        reboot
    fi
}

main