#!/bin/bash
#
# IQRight Repeater - Full Pi Zero W Setup
#
# Downloads the repeater bundle from FTP and configures the entire system:
#   - System packages (Python, I2C tools, build tools)
#   - Repeater application files
#   - Python virtual environment + dependencies
#   - Cython compilation (source code protection)
#   - Node configuration (.env with repeater ID)
#   - I2C for OLED display and PiSugar battery monitor
#   - Systemd service (auto-start with crash recovery)
#   - Daily shutdown cron job (6:00 PM)
#   - Silent boot
#
# IMPORTANT: This script is designed to be run with sudo.
# All file ownership is set to TARGET_USER (derived from INSTALL_DIR).
#
# Usage:
#   scp this script to the Pi, then:
#   chmod +x setup_repeater.sh && sudo ./setup_repeater.sh
#
# Environment variables (optional overrides):
#   FTP_HOST      - FTP server IP (default: 192.168.7.151)
#   FTP_PORT      - FTP server port (default: 5009)
#   FTP_USER      - FTP username (default: fulviomanente)
#   FTP_PASS      - FTP password (default: 1234)
#   INSTALL_DIR   - Installation directory (default: /home/iqright)
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
INSTALL_DIR="${INSTALL_DIR:-/home/iqright}"
BUNDLE_FILE="repeater_bundle.tar.gz"

# Detect the target user who will own the files and run the repeater.
# When run with sudo, $(whoami) is root — we need the actual user.
TARGET_USER=$(basename "$INSTALL_DIR")
TARGET_GROUP="$TARGET_USER"
TARGET_HOME=$(getent passwd "$TARGET_USER" 2>/dev/null | cut -d: -f6)
TARGET_HOME="${TARGET_HOME:-$INSTALL_DIR}"

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

# Fix ownership of INSTALL_DIR to TARGET_USER.
# Called after every step that creates/modifies files.
fix_ownership() {
    chown -R "${TARGET_USER}:${TARGET_GROUP}" "$INSTALL_DIR"
}

TOTAL_STEPS=10

# ------------------------------------------------------------------
# Step 1: System packages
# ------------------------------------------------------------------
install_system_packages() {
    print_step 1 "Installing system packages"

    apt update -qq

    PACKAGES="python3-pip python3-venv python3-dev gcc i2c-tools ftp fbi"
    apt install -y $PACKAGES

    print_success "System packages installed"
}

# ------------------------------------------------------------------
# Step 2: Download repeater bundle from FTP
# ------------------------------------------------------------------
download_bundle() {
    print_step 2 "Downloading repeater bundle from FTP"
    print_info "Server: ${FTP_USER}@${FTP_HOST}:${FTP_PORT}"

    TMPDIR=$(mktemp -d)

    # Create FTP command script
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

    # Store temp dir for next step
    DOWNLOAD_DIR="$TMPDIR"
}

# ------------------------------------------------------------------
# Step 3: Extract bundle to install directory
# ------------------------------------------------------------------
extract_bundle() {
    print_step 3 "Extracting repeater bundle to ${INSTALL_DIR}"

    # Create install dir if needed
    mkdir -p "$INSTALL_DIR"

    # Extract — tarball contains repeater_bundle/ at top level, strip it
    tar xzf "${DOWNLOAD_DIR}/${BUNDLE_FILE}" -C "$INSTALL_DIR" --strip-components=1

    # Cleanup download
    rm -rf "$DOWNLOAD_DIR"

    # Ensure required directories exist
    mkdir -p "${INSTALL_DIR}/log"

    # Copy repeater config as active config
    if [ -f "${INSTALL_DIR}/utils/config.repeater.py" ]; then
        cp "${INSTALL_DIR}/utils/config.repeater.py" "${INSTALL_DIR}/utils/config.py"
        print_success "Config installed: utils/config.repeater.py -> utils/config.py"
    else
        print_error "config.repeater.py not found in bundle"
        exit 1
    fi

    fix_ownership

    # Verify critical files from bundle
    CRITICAL_FILES="repeater.py run_repeater.py build_cython.py lora/__init__.py lora/packet_handler.py lora/node_types.py lora/collision_avoidance.py utils/__init__.py utils/config.py utils/oled_display.py"
    MISSING=0
    for f in $CRITICAL_FILES; do
        if [ ! -f "${INSTALL_DIR}/$f" ]; then
            print_error "Missing from bundle: $f"
            MISSING=$((MISSING + 1))
        fi
    done
    if [ "$MISSING" -gt 0 ]; then
        print_error "$MISSING critical file(s) missing from bundle — aborting"
        exit 1
    fi

    print_success "Repeater files extracted and verified (${INSTALL_DIR})"
}

# ------------------------------------------------------------------
# Step 4: Create virtual environment and install dependencies
# ------------------------------------------------------------------
setup_python() {
    print_step 4 "Setting up Python virtual environment"

    cd "$INSTALL_DIR"

    # Create venv
    python3 -m venv .venv
    print_success "Virtual environment created"

    # Activate and install
    source .venv/bin/activate

    # Upgrade pip first (Pi Zero has old pip)
    pip install --upgrade pip 2>/dev/null || true

    if [ -f "configs/requirements.repeater.txt" ]; then
        pip install -r configs/requirements.repeater.txt
        print_success "Python dependencies installed"
    else
        print_error "requirements.repeater.txt not found"
        exit 1
    fi

    deactivate
    fix_ownership
}

# ------------------------------------------------------------------
# Step 5: Compile Python source to native code
# ------------------------------------------------------------------
compile_source() {
    print_step 5 "Compiling source code to native extensions"
    print_info "This takes 10-30 minutes on Pi Zero..."

    cd "$INSTALL_DIR"
    source .venv/bin/activate

    # Install Cython and build tools
    pip install cython > /dev/null 2>&1
    apt install -y python3-dev gcc > /dev/null 2>&1
    print_success "Build tools installed"

    # Compile all .py files to .so
    if [ ! -f "build_cython.py" ]; then
        print_warning "build_cython.py not found — skipping compilation"
        deactivate
        return
    fi

    # Use pipefail so we capture the python exit code, not tail's
    set +e
    COMPILE_OUTPUT=$(python build_cython.py build_ext --inplace 2>&1)
    COMPILE_STATUS=$?
    set -e

    echo "$COMPILE_OUTPUT" | tail -10

    if [ $COMPILE_STATUS -ne 0 ]; then
        print_warning "Compilation failed (exit code $COMPILE_STATUS) — keeping .py source files"
        deactivate
        fix_ownership
        return
    fi

    # Verify .so files were actually created before deleting source
    SO_COUNT=$(find . -name "*.so" -not -path "./.venv/*" | wc -l)
    if [ "$SO_COUNT" -eq 0 ]; then
        print_warning "No .so files produced — keeping .py source files"
        deactivate
        fix_ownership
        return
    fi

    print_success "Compilation complete ($SO_COUNT .so files created)"

    # Verify each .py has a corresponding .so before deleting
    DELETED=0
    KEPT=0
    for pyfile in $(find . -name "*.py" -not -path "./.venv/*" -not -path "./configs/*" -not -path "./log/*"); do
        basename=$(basename "$pyfile")

        # Never delete these files
        if [ "$basename" = "__init__.py" ] || [ "$basename" = "run_repeater.py" ] || [ "$basename" = "build_cython.py" ]; then
            continue
        fi

        # Check if a corresponding .so exists in the same directory
        pydir=$(dirname "$pyfile")
        pyname="${basename%.py}"
        # Cython .so names include the Python version: repeater.cpython-311-aarch64-linux-gnu.so
        SO_MATCH=$(find "$pydir" -maxdepth 1 -name "${pyname}.cpython-*.so" -o -name "${pyname}.so" 2>/dev/null | head -1)

        if [ -n "$SO_MATCH" ]; then
            rm "$pyfile"
            DELETED=$((DELETED + 1))
        else
            print_warning "No .so found for $pyfile — keeping source"
            KEPT=$((KEPT + 1))
        fi
    done

    # Remove intermediate .c files and build directory
    find . -name "*.c" -not -path "./.venv/*" -delete 2>/dev/null || true
    rm -rf build/

    print_success "Removed $DELETED source files ($KEPT kept without .so)"

    deactivate
    fix_ownership
}

# ------------------------------------------------------------------
# Step 6: Prompt for repeater node ID and create .env
# ------------------------------------------------------------------
configure_node() {
    print_step 6 "Configuring repeater node"

    echo ""
    echo -e "${BOLD}Repeater Node ID Configuration${NC}"
    echo -e "  Valid range: 200-256"
    echo ""

    while true; do
        read -p "  Enter repeater node ID: " NODE_ID

        # Validate: must be a number between 200-256
        if [[ "$NODE_ID" =~ ^[0-9]+$ ]] && [ "$NODE_ID" -ge 200 ] && [ "$NODE_ID" -le 256 ]; then
            break
        else
            print_error "Invalid node ID. Must be between 200 and 256."
        fi
    done

    # Write .env file
    cat > "${INSTALL_DIR}/.env" << EOF
# IQRight Repeater Configuration
# Generated by setup_repeater.sh on $(date)
LORA_NODE_TYPE=REPEATER
LORA_NODE_ID=${NODE_ID}
LORA_FREQUENCY=915.23
LORA_TX_POWER=23
LORA_TTL=3
LORA_ENABLE_CA=TRUE
EOF

    chown "${TARGET_USER}:${TARGET_GROUP}" "${INSTALL_DIR}/.env"

    print_success "Node configured: Repeater ID ${NODE_ID}"
    print_success ".env created at ${INSTALL_DIR}/.env"
}

# ------------------------------------------------------------------
# Step 7: Enable I2C for OLED display and PiSugar battery monitor
# ------------------------------------------------------------------
configure_i2c() {
    print_step 7 "Enabling I2C for OLED display and PiSugar"

    # Enable I2C via raspi-config
    raspi-config nonint do_i2c 0
    print_success "I2C enabled"

    # Load I2C kernel modules
    if ! grep -q "^i2c-dev" /etc/modules 2>/dev/null; then
        echo "i2c-dev" >> /etc/modules
    fi
    if ! grep -q "^i2c-bcm2835" /etc/modules 2>/dev/null; then
        echo "i2c-bcm2835" >> /etc/modules
    fi
    print_success "I2C kernel modules configured"

    # Add user to i2c group
    usermod -aG i2c "$TARGET_USER"
    print_success "Added ${TARGET_USER} to i2c group"

    # Allow passwordless sudo for shutdown (repeater software triggers shutdown)
    echo "${TARGET_USER} ALL=(ALL) NOPASSWD: /sbin/shutdown" | tee /etc/sudoers.d/repeater-shutdown > /dev/null
    chmod 440 /etc/sudoers.d/repeater-shutdown
    print_success "Passwordless shutdown configured"
}

# ------------------------------------------------------------------
# Step 8: Create systemd service (auto-start with crash recovery)
# ------------------------------------------------------------------
create_service() {
    print_step 8 "Creating systemd service"

    SERVICE_FILE="/etc/systemd/system/iqright-repeater.service"

    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=IQRight LoRa Repeater Node ${NODE_ID}
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${TARGET_USER}
Group=${TARGET_GROUP}
WorkingDirectory=${INSTALL_DIR}

# Load .env configuration
EnvironmentFile=${INSTALL_DIR}/.env
Environment="HOME=${TARGET_HOME}"
Environment="PYTHONUNBUFFERED=1"

# Execute repeater via venv Python
ExecStart=${INSTALL_DIR}/.venv/bin/python3 ${INSTALL_DIR}/run_repeater.py

# Restart policy — auto-restart on crash
Restart=always
RestartSec=10
StartLimitInterval=300
StartLimitBurst=5

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=iqright-repeater-${NODE_ID}

[Install]
WantedBy=multi-user.target
EOF

    chown root:root "$SERVICE_FILE"
    chmod 644 "$SERVICE_FILE"

    systemctl daemon-reload
    systemctl enable iqright-repeater.service
    print_success "Systemd service created and enabled"
    print_success "Repeater will auto-start on boot with crash recovery"
}

# ------------------------------------------------------------------
# Step 9: Configure daily shutdown cron (6:00 PM)
# ------------------------------------------------------------------
configure_shutdown_cron() {
    print_step 9 "Configuring daily shutdown cron job (6:00 PM)"

    # Install shutdown script
    SHUTDOWN_SCRIPT="/usr/local/bin/shutdown_repeater.sh"
    cat > "$SHUTDOWN_SCRIPT" << 'EOF'
#!/bin/bash
# Daily scheduled shutdown at 6:00 PM

logger "Cron: Repeater daily shutdown initiated at $(date)"
/sbin/shutdown -h now
EOF

    chmod +x "$SHUTDOWN_SCRIPT"
    print_success "Shutdown script installed at ${SHUTDOWN_SCRIPT}"

    # Add cron job for root (shutdown requires root)
    CRON_MARKER="# IQRight Repeater daily shutdown"
    CRON_LINE="0 18 * * * ${SHUTDOWN_SCRIPT} ${CRON_MARKER}"

    # Check if already configured
    if crontab -l 2>/dev/null | grep -q "$CRON_MARKER"; then
        print_warning "Shutdown cron already configured"
    else
        (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
        print_success "Cron job added: shutdown daily at 6:00 PM"
    fi

    print_info "RTC will wake the Pi on the next day"
}

# ------------------------------------------------------------------
# Step 10: Configure silent boot
# ------------------------------------------------------------------
configure_boot() {
    print_step 10 "Configuring silent boot"

    # Remove Pi branding from boot
    if ! grep -q "disable_splash=1" /boot/firmware/config.txt 2>/dev/null; then
        echo "disable_splash=1" | tee -a /boot/firmware/config.txt > /dev/null
    fi
    print_success "Rainbow splash disabled"

    # Silent kernel boot
    CMDLINE="/boot/firmware/cmdline.txt"
    for param in "logo.nologo" "quiet" "loglevel=0" "vt.global_cursor_default=0"; do
        if ! grep -q "$param" "$CMDLINE" 2>/dev/null; then
            sed -i "s/$/ ${param}/" "$CMDLINE"
        fi
    done
    print_success "Silent boot configured"

    # Disable login prompt on console (service handles everything)
    systemctl mask getty@tty1.service 2>/dev/null || true
    print_success "Console login prompt disabled"
}

# ------------------------------------------------------------------
# Final verification: ensure everything is in place
# ------------------------------------------------------------------
verify_installation() {
    print_header "Verifying Installation"

    ERRORS=0

    # Check critical files exist (either .py or .so)
    for mod in repeater lora/packet_handler lora/node_types lora/collision_avoidance utils/oled_display utils/config; do
        PY="${INSTALL_DIR}/${mod}.py"
        # .so name varies by platform: module.cpython-3XX-arch.so
        SO_MATCH=$(find "${INSTALL_DIR}" -path "*/${mod##*/}.cpython-*.so" -o -path "*/${mod##*/}.so" 2>/dev/null | head -1)

        if [ -f "$PY" ] || [ -n "$SO_MATCH" ]; then
            print_success "$mod ($([ -f "$PY" ] && echo '.py' || echo '.so'))"
        else
            print_error "$mod — MISSING (no .py or .so found)"
            ERRORS=$((ERRORS + 1))
        fi
    done

    # Check __init__.py files (never compiled)
    for init in lora/__init__.py utils/__init__.py; do
        if [ -f "${INSTALL_DIR}/$init" ]; then
            print_success "$init"
        else
            print_error "$init — MISSING"
            ERRORS=$((ERRORS + 1))
        fi
    done

    # Check launcher
    if [ -f "${INSTALL_DIR}/run_repeater.py" ]; then
        print_success "run_repeater.py"
    else
        print_error "run_repeater.py — MISSING"
        ERRORS=$((ERRORS + 1))
    fi

    # Check pisugar_monitor (optional)
    PY="${INSTALL_DIR}/utils/pisugar_monitor.py"
    SO_MATCH=$(find "${INSTALL_DIR}" -path "*/pisugar_monitor.cpython-*.so" -o -path "*/pisugar_monitor.so" 2>/dev/null | head -1)
    if [ -f "$PY" ] || [ -n "$SO_MATCH" ]; then
        print_success "utils/pisugar_monitor ($([ -f "$PY" ] && echo '.py' || echo '.so'))"
    else
        print_warning "utils/pisugar_monitor — not found (optional, PiSugar features disabled)"
    fi

    # Check .env
    if [ -f "${INSTALL_DIR}/.env" ]; then
        print_success ".env"
    else
        print_error ".env — MISSING"
        ERRORS=$((ERRORS + 1))
    fi

    # Check venv
    if [ -f "${INSTALL_DIR}/.venv/bin/python3" ]; then
        print_success ".venv/bin/python3"
    else
        print_error ".venv — MISSING or broken"
        ERRORS=$((ERRORS + 1))
    fi

    # Check systemd service
    if systemctl is-enabled iqright-repeater.service &>/dev/null; then
        print_success "iqright-repeater.service (enabled)"
    else
        print_error "iqright-repeater.service — NOT enabled"
        ERRORS=$((ERRORS + 1))
    fi

    # Check shutdown cron
    if crontab -l 2>/dev/null | grep -q "shutdown_repeater.sh"; then
        print_success "Daily shutdown cron (6:00 PM)"
    else
        print_error "Daily shutdown cron — NOT configured"
        ERRORS=$((ERRORS + 1))
    fi

    # Check ownership
    OWNER=$(stat -c '%U' "${INSTALL_DIR}" 2>/dev/null || stat -f '%Su' "${INSTALL_DIR}" 2>/dev/null)
    if [ "$OWNER" = "$TARGET_USER" ]; then
        print_success "Ownership: ${TARGET_USER}"
    else
        print_error "Ownership: ${OWNER} (expected ${TARGET_USER})"
        ERRORS=$((ERRORS + 1))
    fi

    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        print_error "${ERRORS} problem(s) found — review errors above"
        return 1
    else
        print_success "All checks passed"
        return 0
    fi
}

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
main() {
    print_header "IQRight Repeater - Pi Zero W Setup"

    # Warn if not running as root
    if [ "$(id -u)" -ne 0 ]; then
        print_error "This script must be run as root (sudo ./setup_repeater.sh)"
        exit 1
    fi

    # Verify target user exists
    if ! id "$TARGET_USER" &>/dev/null; then
        print_error "Target user '${TARGET_USER}' does not exist. Create it first or set INSTALL_DIR."
        exit 1
    fi

    echo -e "  ${CYAN}FTP Server:${NC}    ${FTP_HOST}:${FTP_PORT}"
    echo -e "  ${CYAN}Install Dir:${NC}   ${INSTALL_DIR}"
    echo -e "  ${CYAN}Target User:${NC}   ${TARGET_USER}"
    echo -e "  ${CYAN}Target Home:${NC}   ${TARGET_HOME}"
    echo ""

    # Check we're on a Pi
    if [ ! -f /proc/device-tree/model ]; then
        print_warning "This doesn't appear to be a Raspberry Pi. Continuing anyway..."
    else
        MODEL=$(cat /proc/device-tree/model | tr -d '\0')
        print_info "Hardware: ${MODEL}"
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
    setup_python
    echo ""
    compile_source
    echo ""
    configure_node
    echo ""
    configure_i2c
    echo ""
    create_service
    echo ""
    configure_shutdown_cron
    echo ""
    configure_boot
    echo ""

    # Final ownership pass (catches anything missed)
    fix_ownership

    # Verify everything
    verify_installation

    # Summary
    print_header "Setup Complete!"

    echo -e "  ${GREEN}Repeater installed to: ${INSTALL_DIR}${NC}"
    echo -e "  ${GREEN}Node ID: $(grep LORA_NODE_ID ${INSTALL_DIR}/.env | cut -d= -f2)${NC}"
    echo ""
    echo -e "  ${CYAN}What happens now:${NC}"
    echo -e "    - On reboot, the repeater service auto-starts"
    echo -e "    - SSH remains available for troubleshooting"
    echo -e "    - If the app crashes, systemd restarts it after 10 seconds"
    echo -e "    - Daily shutdown at 6:00 PM via cron (RTC wakes next day)"
    echo -e "    - OLED display shows forwarding activity and stats"
    echo ""
    echo -e "  ${CYAN}Useful commands:${NC}"
    echo -e "    sudo systemctl status iqright-repeater   # Service status"
    echo -e "    sudo systemctl restart iqright-repeater  # Restart"
    echo -e "    sudo journalctl -u iqright-repeater -f   # Live logs"
    echo -e "    tail -f ${INSTALL_DIR}/log/repeater_*.log  # App logs"
    echo ""
    echo -e "  ${CYAN}To test manually:${NC}"
    echo -e "    cd ${INSTALL_DIR}"
    echo -e "    source .venv/bin/activate"
    echo -e "    python3 run_repeater.py"
    echo ""
    echo -e "  ${CYAN}To update repeater files later:${NC}"
    echo -e "    Run this script again — it will overwrite the application files."
    echo ""
    echo -e "  ${CYAN}PiSugar schedule (optional):${NC}"
    echo -e "    Run setup_pisugar_schedule.sh for RTC wake-up configuration"
    echo ""
    echo -e "  ${YELLOW}Reboot now to start the repeater automatically.${NC}"
    echo ""
    read -p "  Reboot now? (y/N): " REBOOT
    if [[ "$REBOOT" =~ ^[Yy]$ ]]; then
        reboot
    fi
}

main
