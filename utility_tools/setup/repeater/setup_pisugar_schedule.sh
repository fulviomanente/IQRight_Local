#!/bin/bash
#
# PiSugar 3 Schedule Setup for IQRight Repeater
#
# Configures PiSugar to:
# - Wake up daily at 1:00 PM (13:00)
# - Shutdown safely at 5% battery
# - Repeat every day of the week
#
# This works with the repeater's scheduled shutdown at 5:00 PM,
# allowing solar charging overnight and operation during school hours (2:00-4:00 PM)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "============================================================"
echo -e "${BLUE}PiSugar 3 Schedule Configuration${NC}"
echo " This config can also be done via browser on {your ip}:8421 "
echo "============================================================"
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo -e "${YELLOW}WARNING: Not running on Raspberry Pi${NC}"
    echo "This script should be run on the repeater device"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if PiSugar daemon is running
if ! nc -z 127.0.0.1 8423 2>/dev/null; then
    echo -e "${RED}ERROR: PiSugar daemon not running!${NC}"
    echo ""
    echo "PiSugar daemon should be listening on port 8423"
    echo "Please ensure:"
    echo "  1. PiSugar 3 is connected"
    echo "  2. PiSugar daemon is installed and running"
    echo "  3. Check: sudo systemctl status pisugar-server"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ PiSugar daemon detected${NC}"
echo ""

# Get current PiSugar status
echo "Current PiSugar Status:"
echo "----------------------"
python3 utils/pisugar_monitor.py 2>/dev/null || {
    echo -e "${RED}Failed to read PiSugar status${NC}"
    exit 1
}
echo ""

# Confirm configuration
echo -e "${BLUE}Proposed Schedule Configuration:${NC}"
echo "  Wake-up time:       1:00 PM (13:00) daily"
echo "  Shutdown trigger:   5% battery level"
echo "  Shutdown time:      5:00 PM (17:00) - managed by repeater software"
echo "  Alarm repeat:       Every day (Mon-Sun)"
echo ""
echo -e "${YELLOW}This allows:${NC}"
echo "  • Solar charging from 5:00 PM to 1:00 PM next day (20 hours)"
echo "  • Device operation from 1:00 PM to 5:00 PM (4 hours)"
echo "  • Coverage for school pickup (2:00-4:00 PM)"
echo ""

read -p "Apply this configuration? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Configuration cancelled"
    exit 0
fi

echo ""
echo "Configuring PiSugar..."

# Function to send command to PiSugar
send_pisugar_cmd() {
    local cmd="$1"
    echo "$cmd" | nc -q 0 127.0.0.1 8423
}

# Set RTC alarm time (1:00 PM / 13:00:00)
# Format: YYYY-MM-DDTHH:MM:SS.sss±HH:MM
# Year/month/day are ignored for repeating alarms
echo -n "  Setting wake-up time to 1:00 PM... "
ALARM_TIME="2000-01-01T13:00:00.000-05:00"
result=$(send_pisugar_cmd "rtc_alarm_set $ALARM_TIME")
if [[ $result == *"done"* ]] || [[ $result == *"ok"* ]]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}? (response: $result)${NC}"
fi

# Enable RTC alarm
echo -n "  Enabling RTC alarm... "
result=$(send_pisugar_cmd "rtc_alarm_enable true")
if [[ $result == *"done"* ]] || [[ $result == *"ok"* ]]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}? (response: $result)${NC}"
fi

# Set alarm repeat for all 7 days
# Bitmask: bit 0=Sunday, bit 1=Monday, ..., bit 6=Saturday
# 127 = 0b01111111 = all days
echo -n "  Setting alarm to repeat daily... "
result=$(send_pisugar_cmd "set_alarm_repeat 127")
if [[ $result == *"done"* ]] || [[ $result == *"ok"* ]]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}? (response: $result)${NC}"
fi

# Set safe shutdown level to 5%
echo -n "  Setting safe shutdown level to 5%... "
result=$(send_pisugar_cmd "set_safe_shutdown_level 5")
if [[ $result == *"done"* ]] || [[ $result == *"ok"* ]]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}? (response: $result)${NC}"
fi

echo ""
echo -e "${GREEN}Configuration complete!${NC}"
echo ""

# Verify configuration
echo "Verifying configuration:"
echo "------------------------"
python3 utils/pisugar_monitor.py 2>/dev/null

echo ""
echo "============================================================"
echo -e "${GREEN}PiSugar Schedule Successfully Configured${NC}"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Ensure repeater service is running: sudo systemctl status repeater"
echo "  2. Check logs: tail -f log/repeater_*.log"
echo "  3. Verify status sent to server: tail -f log/device_status.log (on server)"
echo "  4. Monitor battery on OLED display"
echo ""
echo -e "${YELLOW}Daily Schedule:${NC}"
echo "  1:00 PM - Device wakes up via PiSugar RTC"
echo "  ~1:01 PM - Repeater software starts (if configured as service)"
echo "  2:00-4:00 PM - School pickup operations"
echo "  5:00 PM - Repeater initiates shutdown (software-controlled)"
echo "  5:00 PM - Next Day 1:00 PM - Solar charging period"
echo ""
