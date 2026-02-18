#!/bin/bash
#
# IQRight Scanner - Full Pi Zero W Setup
#
# Downloads the scanner bundle from SFTP and configures the entire system:
#   - System packages (X11, tkinter, Python, FTP)
#   - Scanner application files
#   - Python virtual environment + dependencies
#   - Node configuration (.env with scanner ID)
#   - Console auto-login
#   - Auto-start on boot (with crash recovery)
#
# Usage:
#   curl/scp this script to the Pi, then:
#   chmod +x setup.sh && ./setup.sh
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
BUNDLE_FILE="scanner_bundle.tar.gz"

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

TOTAL_STEPS=10

# ------------------------------------------------------------------
# Step 1: System packages
# ------------------------------------------------------------------
install_system_packages() {
    print_step 1 "Installing system packages"

    sudo apt update -qq

    PACKAGES="xserver-xorg-core xserver-xorg-legacy xinit x11-xserver-utils xinput xfonts-base fonts-dejavu-core python3-tk python3-pip python3-venv ftp fbi"
    sudo apt install -y $PACKAGES

    print_success "System packages installed"
}

# ------------------------------------------------------------------
# Step 2: Download scanner bundle from SFTP
# ------------------------------------------------------------------
download_bundle() {
    print_step 2 "Downloading scanner bundle from FTP"
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
    print_step 3 "Extracting scanner bundle to ${INSTALL_DIR}"

    # Create install dir if needed
    sudo mkdir -p "$INSTALL_DIR"
    sudo chown "$(whoami):$(whoami)" "$INSTALL_DIR"

    # Extract — tarball contains scanner_bundle/ at top level, strip it
    tar xzf "${DOWNLOAD_DIR}/${BUNDLE_FILE}" -C "$INSTALL_DIR" --strip-components=1

    # Cleanup download
    rm -rf "$DOWNLOAD_DIR"

    # Ensure log directory exists
    mkdir -p "${INSTALL_DIR}/log"

    # Copy scanner config as active config
    if [ -f "${INSTALL_DIR}/utils/config.scanner.py" ]; then
        cp "${INSTALL_DIR}/utils/config.scanner.py" "${INSTALL_DIR}/utils/config.py"
        print_success "Config installed: utils/config.scanner.py → utils/config.py"
    else
        print_error "config.scanner.py not found in bundle"
        exit 1
    fi

    print_success "Scanner files extracted to ${INSTALL_DIR}"
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

    if [ -f "configs/requirements.scanner.txt" ]; then
        pip install -r configs/requirements.scanner.txt
        print_success "Python dependencies installed"
    else
        print_error "requirements.scanner.txt not found"
        exit 1
    fi

    deactivate
}

# ------------------------------------------------------------------
# Step 5: Compile Python source to native code
# ------------------------------------------------------------------
compile_source() {
    print_step 5 "Compiling source code to native extensions"
    print_info "This takes 10-30 minutes on first setup..."

    cd "$INSTALL_DIR"
    source .venv/bin/activate

    # Install Cython and build tools
    pip install cython > /dev/null 2>&1
    sudo apt install -y python3-dev gcc > /dev/null 2>&1
    print_success "Build tools installed"

    # Compile all .py files to .so
    if [ -f "build_cython.py" ]; then
        python build_cython.py build_ext --inplace 2>&1 | tail -5
        COMPILE_STATUS=$?

        if [ $COMPILE_STATUS -eq 0 ]; then
            print_success "Compilation complete"

            # Remove Python source files (keep __init__.py and launcher)
            find . -maxdepth 1 -name "*.py" ! -name "run_scanner.py" ! -name "__init__.py" \
                ! -name "build_cython.py" -delete
            find ./lora -name "*.py" ! -name "__init__.py" -delete
            find ./utils -name "*.py" ! -name "__init__.py" -delete

            # Remove intermediate .c files
            find . -name "*.c" -delete

            # Remove build directory
            rm -rf build/

            print_success "Source files removed — only compiled .so files remain"
        else
            print_warning "Compilation failed — keeping .py source files"
        fi
    else
        print_warning "build_cython.py not found — skipping compilation"
    fi

    deactivate
}

# ------------------------------------------------------------------
# Step 6: Prompt for scanner node ID and create .env
# ------------------------------------------------------------------
configure_node() {
    print_step 6 "Configuring scanner node"

    echo ""
    echo -e "${BOLD}Scanner Node ID Configuration${NC}"
    echo -e "  Valid range: 100-199"
    echo -e "  Current scanners: 102 (Gym Side), 103 (East Side)"
    echo ""

    while true; do
        read -p "  Enter scanner node ID: " NODE_ID

        # Validate: must be a number between 100-199
        if [[ "$NODE_ID" =~ ^[0-9]+$ ]] && [ "$NODE_ID" -ge 100 ] && [ "$NODE_ID" -le 199 ]; then
            break
        else
            print_error "Invalid node ID. Must be between 100 and 199."
        fi
    done

    # Write .env file
    cat > "${INSTALL_DIR}/.env" << EOF
# IQRight Scanner Configuration
# Generated by setup.sh on $(date)
LORA_NODE_TYPE=SCANNER
LORA_NODE_ID=${NODE_ID}
LORA_FREQUENCY=915.23
LORA_TX_POWER=23
LORA_TTL=3
LORA_ENABLE_CA=TRUE
EOF

    print_success "Node configured: Scanner ID ${NODE_ID}"
    print_success ".env created at ${INSTALL_DIR}/.env"
}

# ------------------------------------------------------------------
# Step 7: Configure console auto-login
# ------------------------------------------------------------------
configure_autologin() {
    print_step 7 "Configuring console auto-login and permissions"

    sudo raspi-config nonint do_boot_behaviour B2
    print_success "Console auto-login enabled"

    # Allow console user to start X server
    echo -e "allowed_users=anybody\nneeds_root_rights=yes" | sudo tee /etc/X11/Xwrapper.config > /dev/null
    print_success "X server permissions configured"

    # Rotate display and touchscreen for vertical orientation
    sudo mkdir -p /etc/X11/xorg.conf.d

    sudo tee /etc/X11/xorg.conf.d/10-monitor.conf > /dev/null << 'XEOF'
Section "Monitor"
    Identifier "HDMI-1"
    Option "Rotate" "left"
EndSection
XEOF
    print_success "Display rotation configured (90° CCW)"

    sudo tee /etc/X11/xorg.conf.d/40-libinput.conf > /dev/null << 'XEOF'
Section "InputClass"
    Identifier "libinput touchscreen catchall"
    MatchIsTouchscreen "on"
    MatchDevicePath "/dev/input/*"
    Driver "libinput"
    Option "CalibrationMatrix" "0 -1 1 1 0 0 0 0 1"
EndSection
XEOF
    print_success "Touchscreen rotation configured"

    # User needs tty/video/input groups to run X without root
    CURRENT_USER=$(whoami)
    sudo usermod -aG tty,video,input "$CURRENT_USER"
    print_success "Added ${CURRENT_USER} to tty, video, input groups"

    # Allow passwordless sudo for shutdown (Quit button powers off the Pi)
    echo "${CURRENT_USER} ALL=(ALL) NOPASSWD: /sbin/shutdown" | sudo tee /etc/sudoers.d/scanner-shutdown > /dev/null
    sudo chmod 440 /etc/sudoers.d/scanner-shutdown
    print_success "Passwordless shutdown configured"
}

# ------------------------------------------------------------------
# Step 8: Create startup script
# ------------------------------------------------------------------
create_startup_script() {
    print_step 8 "Creating startup script"

    cat > "${HOME}/start_scanner.sh" << EOF
#!/bin/bash
cd ${INSTALL_DIR}

# Load node configuration (.env)
set -a
source .env
set +a

source .venv/bin/activate

# Wait for X server to be ready
sleep 2

exec python3 run_scanner.py
EOF

    chmod +x "${HOME}/start_scanner.sh"
    print_success "Created ~/start_scanner.sh"
}

# ------------------------------------------------------------------
# Step 9: Configure auto-start on boot
# ------------------------------------------------------------------
configure_autostart() {
    print_step 9 "Configuring auto-start on boot"

    PROFILE="${HOME}/.bash_profile"
    MARKER="# IQRight Scanner Auto-Start"

    # Check if already configured
    if [ -f "$PROFILE" ] && grep -q "$MARKER" "$PROFILE"; then
        print_warning "Auto-start already configured in ~/.bash_profile"
        return
    fi

    cat >> "$PROFILE" << 'EOF'

# IQRight Scanner Auto-Start
# Launches scanner UI on the physical console (tty1 only, not SSH)
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    clear
    echo ""
    echo "    =========================="
    echo "    IQRight Scanner"
    echo "    Starting..."
    echo "    =========================="
    echo ""
    while true; do
        xinit ~/start_scanner.sh -- :0 2>/dev/null
        echo "Scanner exited, restarting in 3 seconds..."
        sleep 3
    done
fi
EOF

    print_success "Auto-start configured in ~/.bash_profile (with crash recovery)"
}

# ------------------------------------------------------------------
# Step 10: Configure silent boot + splash screen
# ------------------------------------------------------------------
configure_boot_splash() {
    print_step 10 "Configuring silent boot and splash screen"

    # Remove Pi branding from boot
    if ! grep -q "disable_splash=1" /boot/firmware/config.txt 2>/dev/null; then
        echo "disable_splash=1" | sudo tee -a /boot/firmware/config.txt > /dev/null
    fi
    print_success "Rainbow splash disabled"

    # Silent kernel boot
    CMDLINE="/boot/firmware/cmdline.txt"
    for param in "logo.nologo" "quiet" "loglevel=0" "vt.global_cursor_default=0"; do
        if ! grep -q "$param" "$CMDLINE" 2>/dev/null; then
            sudo sed -i "s/$/ ${param}/" "$CMDLINE"
        fi
    done
    print_success "Silent boot configured"

    # Create splash image (simple text-based PNG using Python)
    SPLASH="/opt/splash.png"
    if [ ! -f "$SPLASH" ]; then
        python3 -c "
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGB', (480, 800), color=(0, 51, 102))
draw = ImageDraw.Draw(img)
try:
    font_lg = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 36)
    font_sm = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
except:
    font_lg = ImageFont.load_default()
    font_sm = ImageFont.load_default()
draw.text((480/2, 350), 'IQRight', fill='white', font=font_lg, anchor='mm')
draw.text((480/2, 400), 'Scanner', fill='white', font=font_lg, anchor='mm')
draw.text((480/2, 460), 'Starting...', fill=(150,200,255), font=font_sm, anchor='mm')
img.save('$SPLASH')
" 2>/dev/null && print_success "Splash image created" || print_warning "Could not generate splash image (Pillow not available)"
    else
        print_info "Splash image already exists"
    fi

    # Create systemd service for splash screen
    sudo tee /etc/systemd/system/splash.service > /dev/null << 'SVCEOF'
[Unit]
Description=IQRight boot splash
DefaultDependencies=no
After=local-fs.target

[Service]
ExecStart=/usr/bin/fbi -d /dev/fb0 --noverbose -a /opt/splash.png
StandardInput=tty
StandardOutput=tty
TTYPath=/dev/tty1

[Install]
WantedBy=sysinit.target
SVCEOF

    sudo systemctl enable splash.service > /dev/null 2>&1
    print_success "Boot splash service enabled"
}

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
main() {
    print_header "IQRight Scanner - Pi Zero W Setup"

    echo -e "  ${CYAN}FTP Server:${NC}    ${FTP_HOST}:${FTP_PORT}"
    echo -e "  ${CYAN}Install Dir:${NC}   ${INSTALL_DIR}"
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
    configure_autologin
    echo ""
    create_startup_script
    echo ""
    configure_autostart
    echo ""
    configure_boot_splash

    # Summary
    print_header "Setup Complete!"

    echo -e "  ${GREEN}Scanner installed to: ${INSTALL_DIR}${NC}"
    echo -e "  ${GREEN}Node ID: $(grep LORA_NODE_ID ${INSTALL_DIR}/.env | cut -d= -f2)${NC}"
    echo ""
    echo -e "  ${CYAN}What happens now:${NC}"
    echo -e "    • On reboot, the scanner will auto-start on the display"
    echo -e "    • SSH remains available for troubleshooting"
    echo -e "    • If the app crashes, it auto-restarts after 3 seconds"
    echo ""
    echo -e "  ${CYAN}To test manually:${NC}"
    echo -e "    cd ${INSTALL_DIR}"
    echo -e "    source .venv/bin/activate"
    echo -e "    xinit ~/start_scanner.sh -- :0"
    echo ""
    echo -e "  ${CYAN}To update scanner files later:${NC}"
    echo -e "    Run this script again — it will overwrite the application files."
    echo ""
    echo -e "  ${YELLOW}Reboot now to start the scanner automatically.${NC}"
    echo ""
    read -p "  Reboot now? (y/N): " REBOOT
    if [[ "$REBOOT" =~ ^[Yy]$ ]]; then
        sudo reboot
    fi
}

main
