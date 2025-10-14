#!/bin/bash
#
# IQRight Repeater Status Display
#
# Displays comprehensive status information for the repeater:
# - Network configuration (IP addresses)
# - Service status
# - Battery level (placeholder)
# - Node ID
# - Recent activity
#
# Usage: ./repeater_status.sh [--watch]
#   --watch: Continuously refresh display every 5 seconds
#

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Service name
SERVICE_NAME="iqright-repeater"

# Function to get battery status using INA219
get_battery_status() {
    # Get script directory to find battery_monitor.py
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    BATTERY_MONITOR="$SCRIPT_DIR/utils/battery_monitor.py"

    # Check if battery monitor script exists
    if [ ! -f "$BATTERY_MONITOR" ]; then
        echo "Battery monitor script not found"
        return
    fi

    # Try to read battery status from INA219
    if command -v python3 &> /dev/null; then
        BATTERY_INFO=$(python3 "$BATTERY_MONITOR" --format text 2>/dev/null)

        # Check if reading was successful
        if [ $? -eq 0 ] && [ -n "$BATTERY_INFO" ]; then
            echo "$BATTERY_INFO"
        else
            # INA219 not available, check for standard battery
            if [ -d "/sys/class/power_supply/BAT0" ] || [ -d "/sys/class/power_supply/BAT1" ]; then
                # Try to read from system battery
                if [ -f "/sys/class/power_supply/BAT0/capacity" ]; then
                    CAPACITY=$(cat /sys/class/power_supply/BAT0/capacity 2>/dev/null)
                    STATUS=$(cat /sys/class/power_supply/BAT0/status 2>/dev/null)
                    echo "${CAPACITY}% (${STATUS})"
                elif [ -f "/sys/class/power_supply/BAT1/capacity" ]; then
                    CAPACITY=$(cat /sys/class/power_supply/BAT1/capacity 2>/dev/null)
                    STATUS=$(cat /sys/class/power_supply/BAT1/status 2>/dev/null)
                    echo "${CAPACITY}% (${STATUS})"
                else
                    echo "Battery info unavailable"
                fi
            else
                echo "AC Power / Not Available"
            fi
        fi
    else
        echo "Python not available"
    fi
}

# Function to get IP addresses
get_ip_addresses() {
    local IPS=""

    # Get wired interface IP (eth0)
    ETH0_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
    if [ -n "$ETH0_IP" ]; then
        IPS="${IPS}eth0: ${ETH0_IP}\n"
    fi

    # Get wireless interface IP (wlan0)
    WLAN0_IP=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
    if [ -n "$WLAN0_IP" ]; then
        IPS="${IPS}wlan0: ${WLAN0_IP}\n"
    fi

    # If no IPs found, show message
    if [ -z "$IPS" ]; then
        IPS="No network connection"
    fi

    echo -e "$IPS"
}

# Function to get node ID from .env file
get_node_id() {
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    ENV_FILE="$SCRIPT_DIR/.env"

    if [ -f "$ENV_FILE" ]; then
        NODE_ID=$(grep "^LORA_NODE_ID=" "$ENV_FILE" | cut -d '=' -f2)
        if [ -n "$NODE_ID" ]; then
            echo "$NODE_ID"
        else
            echo "Not configured"
        fi
    else
        echo "Not configured"
    fi
}

# Function to get service uptime
get_service_uptime() {
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        SINCE=$(systemctl show "$SERVICE_NAME" -p ActiveEnterTimestamp --value)
        if [ -n "$SINCE" ]; then
            START_EPOCH=$(date -d "$SINCE" +%s 2>/dev/null)
            NOW_EPOCH=$(date +%s)
            if [ -n "$START_EPOCH" ]; then
                UPTIME_SECONDS=$((NOW_EPOCH - START_EPOCH))

                # Format uptime
                DAYS=$((UPTIME_SECONDS / 86400))
                HOURS=$(((UPTIME_SECONDS % 86400) / 3600))
                MINUTES=$(((UPTIME_SECONDS % 3600) / 60))

                if [ $DAYS -gt 0 ]; then
                    echo "${DAYS}d ${HOURS}h ${MINUTES}m"
                elif [ $HOURS -gt 0 ]; then
                    echo "${HOURS}h ${MINUTES}m"
                else
                    echo "${MINUTES}m"
                fi
            else
                echo "Unknown"
            fi
        else
            echo "Unknown"
        fi
    else
        echo "Not running"
    fi
}

# Function to display status
display_status() {
    clear

    # Header
    echo -e "${BOLD}${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${BLUE}║         IQRight LoRa Repeater Status Dashboard         ║${NC}"
    echo -e "${BOLD}${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo

    # Timestamp
    echo -e "${CYAN}📅 Timestamp:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "${CYAN}🖥️  Hostname:${NC} $(hostname)"
    echo

    # Node ID
    NODE_ID=$(get_node_id)
    echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}🔢 Node Configuration${NC}"
    echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    if [ "$NODE_ID" = "Not configured" ]; then
        echo -e "  Node ID: ${RED}${NODE_ID}${NC}"
    else
        echo -e "  Node ID: ${GREEN}${NODE_ID}${NC}"
    fi
    echo

    # Network Status
    echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}🌐 Network Status${NC}"
    echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    IPS=$(get_ip_addresses)
    if echo "$IPS" | grep -q "No network"; then
        echo -e "  ${RED}${IPS}${NC}"
    else
        echo -e "  ${GREEN}${IPS}${NC}" | sed 's/^/  /'
    fi
    echo

    # Service Status
    echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}⚙️  Service Status${NC}"
    echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Check if service exists
    if ! systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
        echo -e "  Status: ${RED}Service not installed${NC}"
        echo -e "  ${YELLOW}Run setup_repeater_service.sh to install${NC}"
    else
        # Service exists, check status
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            echo -e "  Status: ${GREEN}● Running${NC}"

            # Show uptime
            UPTIME=$(get_service_uptime)
            echo -e "  Uptime: ${GREEN}${UPTIME}${NC}"

            # Show if enabled
            if systemctl is-enabled --quiet "$SERVICE_NAME"; then
                echo -e "  Boot:   ${GREEN}Enabled (auto-start)${NC}"
            else
                echo -e "  Boot:   ${YELLOW}Disabled${NC}"
            fi
        elif systemctl is-failed --quiet "$SERVICE_NAME"; then
            echo -e "  Status: ${RED}● Failed${NC}"
            echo -e "  Boot:   $(systemctl is-enabled $SERVICE_NAME 2>/dev/null || echo 'disabled')"
        else
            echo -e "  Status: ${YELLOW}○ Stopped${NC}"
            if systemctl is-enabled --quiet "$SERVICE_NAME"; then
                echo -e "  Boot:   ${GREEN}Enabled${NC}"
            else
                echo -e "  Boot:   ${YELLOW}Disabled${NC}"
            fi
        fi
    fi
    echo

    # Battery Status
    echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}🔋 Power Status${NC}"
    echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    BATTERY=$(get_battery_status)

    # Color code based on battery status
    if echo "$BATTERY" | grep -qE "Not Available|unavailable|not found|Error"; then
        echo -e "  ${CYAN}${BATTERY}${NC}"
    elif echo "$BATTERY" | grep -q "Charging"; then
        echo -e "  ${GREEN}⚡ ${BATTERY}${NC}"
    elif echo "$BATTERY" | grep -qE "^[0-9]+%"; then
        # Extract percentage for color coding
        PERCENT=$(echo "$BATTERY" | grep -oE "^[0-9]+" | head -1)
        if [ -n "$PERCENT" ]; then
            if [ "$PERCENT" -ge 50 ]; then
                echo -e "  ${GREEN}${BATTERY}${NC}"
            elif [ "$PERCENT" -ge 20 ]; then
                echo -e "  ${YELLOW}${BATTERY}${NC}"
            else
                echo -e "  ${RED}⚠️  ${BATTERY}${NC}"
            fi
        else
            echo -e "  ${GREEN}${BATTERY}${NC}"
        fi
    else
        echo -e "  ${GREEN}${BATTERY}${NC}"
    fi
    echo

    # Recent Activity
    if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${BOLD}${YELLOW}📊 Recent Activity (last 5 log entries)${NC}"
            echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

            # Get recent logs
            RECENT_LOGS=$(journalctl -u "$SERVICE_NAME" -n 5 --no-pager -o short-iso 2>/dev/null)
            if [ -n "$RECENT_LOGS" ]; then
                echo "$RECENT_LOGS" | while IFS= read -r line; do
                    # Color code based on log level
                    if echo "$line" | grep -qi "error\|fail\|fatal"; then
                        echo -e "  ${RED}${line}${NC}"
                    elif echo "$line" | grep -qi "warn"; then
                        echo -e "  ${YELLOW}${line}${NC}"
                    else
                        echo -e "  ${line}"
                    fi
                done
            else
                echo -e "  ${YELLOW}No recent logs${NC}"
            fi
            echo
        fi
    fi

    # Footer with commands
    echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}💡 Quick Commands${NC}"
    echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  View logs:    ${CYAN}sudo journalctl -u ${SERVICE_NAME} -f${NC}"
    echo -e "  Restart:      ${CYAN}sudo systemctl restart ${SERVICE_NAME}${NC}"
    echo -e "  Stop:         ${CYAN}sudo systemctl stop ${SERVICE_NAME}${NC}"
    echo -e "  Start:        ${CYAN}sudo systemctl start ${SERVICE_NAME}${NC}"
    echo -e "  Full status:  ${CYAN}sudo systemctl status ${SERVICE_NAME}${NC}"
    echo

    if [ "$1" = "--watch" ]; then
        echo -e "${CYAN}Refreshing every 5 seconds... (Press Ctrl+C to exit)${NC}"
    fi
}

# Main execution
if [ "$1" = "--watch" ]; then
    # Watch mode - continuously refresh
    while true; do
        display_status --watch
        sleep 5
    done
else
    # Single display
    display_status
fi
