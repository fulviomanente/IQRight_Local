#!/bin/bash
#
# IQRight Repeater Service Setup Script
#
# This script creates and registers a systemd service for repeater.py
# with automatic restart on crash.
#
# Usage: sudo ./setup_repeater_service.sh [NODE_ID]
#   NODE_ID: Optional repeater node ID (200-256). Will prompt if not provided.
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}IQRight Repeater Service Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: This script must be run as root${NC}"
    echo "Usage: sudo $0 [NODE_ID]"
    exit 1
fi

# Get the actual user (not root when using sudo)
ACTUAL_USER=${SUDO_USER:-$USER}
if [ "$ACTUAL_USER" = "root" ]; then
    echo -e "${YELLOW}WARNING: Could not determine non-root user. Using 'pi' as default.${NC}"
    ACTUAL_USER="pi"
fi

echo -e "${GREEN}Running as user: $ACTUAL_USER${NC}"

# Determine script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

echo -e "${GREEN}Project root: $PROJECT_ROOT${NC}"

# Prompt for node ID if not provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}Enter Repeater Node ID (200-256):${NC}"
    read -r NODE_ID
else
    NODE_ID=$1
fi

# Validate node ID
if ! [[ "$NODE_ID" =~ ^[0-9]+$ ]] || [ "$NODE_ID" -lt 200 ] || [ "$NODE_ID" -gt 256 ]; then
    echo -e "${RED}ERROR: Invalid node ID. Must be between 200 and 256.${NC}"
    exit 1
fi

echo -e "${GREEN}Configuring repeater with Node ID: $NODE_ID${NC}"

# Check if repeater.py exists
if [ ! -f "$PROJECT_ROOT/repeater.py" ]; then
    echo -e "${RED}ERROR: repeater.py not found at $PROJECT_ROOT/repeater.py${NC}"
    exit 1
fi

# Check if virtual environment exists
VENV_PATH=""
if [ -d "$PROJECT_ROOT/.venv" ]; then
    VENV_PATH="$PROJECT_ROOT/.venv"
elif [ -d "$PROJECT_ROOT/venv" ]; then
    VENV_PATH="$PROJECT_ROOT/venv"
else
    echo -e "${YELLOW}WARNING: No virtual environment found at $PROJECT_ROOT/.venv or $PROJECT_ROOT/venv${NC}"
    echo -e "${YELLOW}Using system Python. Consider creating a virtual environment.${NC}"
fi

if [ -n "$VENV_PATH" ]; then
    PYTHON_EXEC="$VENV_PATH/bin/python3"
    echo -e "${GREEN}Using Python from: $PYTHON_EXEC${NC}"
else
    PYTHON_EXEC="/usr/bin/python3"
    echo -e "${YELLOW}Using system Python: $PYTHON_EXEC${NC}"
fi

# Create or update .env file with NODE_ID
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    # Check if LORA_NODE_ID exists and update it, otherwise append
    if grep -q "^LORA_NODE_ID=" "$ENV_FILE"; then
        sed -i "s/^LORA_NODE_ID=.*/LORA_NODE_ID=$NODE_ID/" "$ENV_FILE"
        echo -e "${GREEN}Updated LORA_NODE_ID in $ENV_FILE${NC}"
    else
        echo "LORA_NODE_ID=$NODE_ID" >> "$ENV_FILE"
        echo -e "${GREEN}Added LORA_NODE_ID to $ENV_FILE${NC}"
    fi
else
    echo "LORA_NODE_ID=$NODE_ID" > "$ENV_FILE"
    chown "$ACTUAL_USER:$ACTUAL_USER" "$ENV_FILE"
    echo -e "${GREEN}Created $ENV_FILE with LORA_NODE_ID${NC}"
fi

# Ensure log directory exists
LOG_DIR="$PROJECT_ROOT/log"
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
    chown -R "$ACTUAL_USER:$ACTUAL_USER" "$LOG_DIR"
    echo -e "${GREEN}Created log directory: $LOG_DIR${NC}"
fi

# Create systemd service file
SERVICE_FILE="/etc/systemd/system/iqright-repeater.service"

echo -e "${BLUE}Creating systemd service file: $SERVICE_FILE${NC}"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=IQRight LoRa Repeater Node $NODE_ID
After=network.target
Wants=network-online.target
Documentation=file://$PROJECT_ROOT/docs/OLED_SETUP.md

[Service]
Type=simple
User=$ACTUAL_USER
Group=$ACTUAL_USER
WorkingDirectory=$PROJECT_ROOT

# Environment
Environment="LORA_NODE_ID=$NODE_ID"
Environment="HOME=/home/$ACTUAL_USER"
Environment="PYTHONUNBUFFERED=1"

# Execute repeater
ExecStart=$PYTHON_EXEC $PROJECT_ROOT/repeater.py

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=300
StartLimitBurst=5

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=iqright-repeater-$NODE_ID

# Security settings (optional, can be adjusted)
# PrivateTmp=yes
# NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}Service file created${NC}"
echo

# Set proper permissions
chown root:root "$SERVICE_FILE"
chmod 644 "$SERVICE_FILE"

# Reload systemd daemon
echo -e "${BLUE}Reloading systemd daemon...${NC}"
systemctl daemon-reload

# Enable service to start on boot
echo -e "${BLUE}Enabling service to start on boot...${NC}"
systemctl enable iqright-repeater.service

# Ask if user wants to start the service now
echo
echo -e "${YELLOW}Do you want to start the repeater service now? (y/n)${NC}"
read -r START_NOW

if [[ "$START_NOW" =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Starting iqright-repeater service...${NC}"
    systemctl start iqright-repeater.service
    sleep 2

    # Check status
    if systemctl is-active --quiet iqright-repeater.service; then
        echo -e "${GREEN}✓ Service started successfully!${NC}"
        echo
        echo -e "${BLUE}Service Status:${NC}"
        systemctl status iqright-repeater.service --no-pager -l
    else
        echo -e "${RED}✗ Service failed to start${NC}"
        echo -e "${YELLOW}Check logs with: sudo journalctl -u iqright-repeater -n 50${NC}"
    fi
else
    echo -e "${YELLOW}Service not started. Start manually with:${NC}"
    echo "  sudo systemctl start iqright-repeater.service"
fi

echo
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo
echo -e "${BLUE}Useful Commands:${NC}"
echo -e "  Start:   ${GREEN}sudo systemctl start iqright-repeater${NC}"
echo -e "  Stop:    ${GREEN}sudo systemctl stop iqright-repeater${NC}"
echo -e "  Restart: ${GREEN}sudo systemctl restart iqright-repeater${NC}"
echo -e "  Status:  ${GREEN}sudo systemctl status iqright-repeater${NC}"
echo -e "  Logs:    ${GREEN}sudo journalctl -u iqright-repeater -f${NC}"
echo -e "  Disable: ${GREEN}sudo systemctl disable iqright-repeater${NC}"
echo
echo -e "${BLUE}Log files:${NC}"
echo -e "  Application: ${GREEN}$LOG_DIR/repeater_$NODE_ID.log${NC}"
echo -e "  System:      ${GREEN}journalctl -u iqright-repeater${NC}"
echo