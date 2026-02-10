# PiSugar 3 Integration for IQRight Repeater

Complete guide for PiSugar 3 battery management, RTC wake-up scheduling, and device status monitoring via LoRa.

## Overview

The IQRight repeater now supports **PiSugar 3** for advanced power management:
- **Battery monitoring** with percentage display on OLED
- **RTC wake-up alarm** for scheduled on/off cycles
- **Status reporting to server** via LoRa (battery, charging, RTC info)
- **Automated daily shutdown** at 5:00 PM
- **Solar-powered operation** with overnight charging

## Hardware Requirements

- **Raspberry Pi Zero W** (or compatible)
- **PiSugar 3** battery UPS with RTC
- **Solar panel** (optional but recommended, 5V 2A)
- **RFM9x LoRa module** (existing)
- **SSD1306 OLED display** (existing)

## PiSugar 3 Features

### What is PiSugar 3?

PiSugar 3 is a UPS (Uninterruptible Power Supply) for Raspberry Pi with:
- **Built-in RTC** (Real-Time Clock) for wake-up scheduling
- **Battery management** (charging, monitoring, safe shutdown)
- **Daemon interface** via netcat (port 8423)
- **Wake-up on schedule** even when powered off

### Key Capabilities

| Feature       | Description                       |
|---------------|-----------------------------------|
| Battery       | 1200mAh Li-Po (3.7V)              |
| Charging      | 5V 2A via USB-C or solar input    |
| RTC Alarm     | Daily wake-up scheduling          |
| Safe Shutdown | Automatic shutdown at low battery |
| Communication | TCP socket on port 8423           |

## Daily Operation Schedule

The repeater is configured for **solar-powered autonomous operation**:

```
┌─────────────────────────────────────────────────┐
│ Daily Schedule (optimized for school pickup)   │
├─────────────────────────────────────────────────┤
│ 1:00 PM (13:00)  → Wake up via PiSugar RTC    │
│ 1:01 PM          → Repeater service starts     │
│ 2:00-4:00 PM     → School pickup operations    │
│ 5:00 PM (17:00)  → Scheduled shutdown          │
│ 5:00 PM - 1:00 PM→ Solar charging (20 hours)   │
└─────────────────────────────────────────────────┘
```

**Why this schedule?**
- **20 hours charging** (5 PM to 1 PM) ensures full battery
- **4 hours operation** (1 PM to 5 PM) covers school pickup time
- **Solar panel recharges** overnight and morning
- **Minimal power consumption** during off-hours

## Installation

### 1. Install PiSugar Daemon

On the Raspberry Pi:

```bash
# Install PiSugar server
curl http://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash

# Verify daemon is running
sudo systemctl status pisugar-server

# Should show: active (running)
```

### 2. Test PiSugar Communication

```bash
# Test netcat connection
nc -q 0 127.0.0.1 8423

# If connected, try a command:
get battery

# Should return:
# battery: 85.5
```

### 3. Install Python Utility

The PiSugar monitor utility is already in `utils/pisugar_monitor.py`.

Test it:

```bash
cd /Users/fulviomanente/Documents/Code/IQRight/Local/IQRight_Local
python3 utils/pisugar_monitor.py
```

Expected output:
```
============================================================
PiSugar 3 Status Monitor
============================================================

Battery:          85.5%
Charging:         No
RTC Time:         2025-10-16T18:37:42.000-05:00
Alarm Enabled:    Yes
Alarm Time:       2000-01-01T13:00:00.000-05:00
Shutdown Level:   5%

LoRa Format:
85.5|false|2025-10-16T18:37:42.000-05:00|true|2000-01-01T13:00:00.000-05:00|127|5
============================================================
```

### 4. Configure Schedule via command line of on the Web using IP and port 8421

Run the setup script:

```bash
./setup_pisugar_schedule.sh
```

This configures:
- Wake-up time: **1:00 PM daily**
- Shutdown battery level: **5%**
- Alarm repeat: **Every day (Mon-Sun)**

### 5. Update Repeater Service

The repeater code is already updated. If running as a service, restart it:

```bash
sudo systemctl restart repeater
```

## Features

### 1. Battery Display on OLED

The repeater OLED now shows battery percentage from PiSugar:

```
┌────────────────────────────────────────┐
│ Repeater              (85%)            │  ← Battery from PiSugar
│────────────────────────────────────────│
│ RX: 1250                               │
│ FWD: 1230                     (98%)    │
│ DROP: 20                               │
└────────────────────────────────────────┘
```

**Update interval**: Every 60 seconds

### 2. Status Reporting to Server

Every **5 minutes**, the repeater sends a STATUS packet to the server with:
- Battery percentage
- Charging status
- RTC time
- Alarm settings
- Safe shutdown level

**LoRa payload format**:
```
85.5|false|2025-10-16T18:37:42|true|2000-01-01T13:00:00|127|5
```

Fields:
1. Battery percentage (85.5%)
2. Charging status (true/false)
3. RTC time (ISO format)
4. Alarm enabled (true/false)
5. Alarm time (ISO format)
6. Alarm repeat bitmask (127 = all days)
7. Safe shutdown level (5%)

### 3. Server Device Status Logging

The server logs all STATUS packets to a separate file:

**File**: `log/device_status.log`

**Format**:
```
2025-10-16 14:23:45 - Node 200 | Battery: 85.5% | Charging: false | RTC: 2025-10-16T18:37:42 | Alarm: true (2000-01-01T13:00:00) | Repeat: 127 | Shutdown@: 5%
2025-10-16 14:28:45 - Node 200 | Battery: 84.2% | Charging: false | RTC: 2025-10-16T18:42:42 | Alarm: true (2000-01-01T13:00:00) | Repeat: 127 | Shutdown@: 5%
```

**Viewing on server**:
```bash
tail -f log/device_status.log
```

### 4. Scheduled Shutdown

At **5:00 PM (17:00)** every day, the repeater:
1. Logs final statistics
2. Shows shutdown message on OLED
3. Executes `sudo shutdown -h now`
4. PiSugar enters sleep mode
5. PiSugar RTC wakes device at 1:00 PM next day

## Commands Reference

### PiSugar Commands (via netcat)

```bash
# Get battery percentage
echo "get battery" | nc -q 0 127.0.0.1 8423

# Get charging status
echo "get battery_charging" | nc -q 0 127.0.0.1 8423

# Get RTC time
echo "get rtc_time" | nc -q 0 127.0.0.1 8423

# Get alarm settings
echo "get rtc_alarm_enabled" | nc -q 0 127.0.0.1 8423
echo "get rtc_alarm_time" | nc -q 0 127.0.0.1 8423
echo "get alarm_repeat" | nc -q 0 127.0.0.1 8423

# Get safe shutdown level
echo "get safe_shutdown_level" | nc -q 0 127.0.0.1 8423

# Set alarm time (1:00 PM)
echo "rtc_alarm_set 2000-01-01T13:00:00.000-05:00" | nc -q 0 127.0.0.1 8423

# Enable alarm
echo "rtc_alarm_enable true" | nc -q 0 127.0.0.1 8423

# Set alarm repeat (127 = all days)
# Bitmask: bit 0=Sunday, 1=Monday, ..., 6=Saturday
echo "set_alarm_repeat 127" | nc -q 0 127.0.0.1 8423

# Set safe shutdown level (5%)
echo "set_safe_shutdown_level 5" | nc -q 0 127.0.0.1 8423
```

### Python Utility

```python
from utils.pisugar_monitor import read_pisugar_status, get_battery_percent, format_status_for_lora

# Read full status
status = read_pisugar_status()
print(status)
# {'available': True, 'battery': 85.5, 'charging': False, ...}

# Get battery percentage only
battery = get_battery_percent()
print(f"Battery: {battery}%")

# Format for LoRa transmission
lora_payload = format_status_for_lora(status)
print(lora_payload)
# "85.5|false|2025-10-16T18:37:42|true|2000-01-01T13:00:00|127|5"
```

## Troubleshooting

### PiSugar Daemon Not Running

**Symptoms**: `nc: Connection refused` when trying to connect to port 8423

**Solution**:
```bash
# Check daemon status
sudo systemctl status pisugar-server

# If not running, start it
sudo systemctl start pisugar-server

# Enable on boot
sudo systemctl enable pisugar-server
```

### Battery Shows 0%

**Symptoms**: Battery percentage always shows 0%

**Possible causes**:
1. PiSugar not connected
2. Battery not installed
3. Daemon not reading battery correctly

**Solution**:
```bash
# Test manually
echo "get battery" | nc -q 0 127.0.0.1 8423

# Should return something like: "battery: 85.5"

# If returns 0 or error, check hardware connection
```

### Repeater Not Shutting Down at 5:00 PM

**Symptoms**: Device stays on past 5:00 PM

**Possible causes**:
1. System time incorrect
2. Shutdown command requires sudo password
3. Script not running

**Solution**:
```bash
# Check system time
date

# Ensure repeater user can shutdown without password
# Add to /etc/sudoers (use visudo):
iqright ALL=(ALL) NOPASSWD: /sbin/shutdown

# Check repeater logs
tail -f log/repeater_*.log | grep -i shutdown
```

### Status Not Received on Server

**Symptoms**: No device status in `log/device_status.log` on server

**Check**:
```bash
# On repeater
tail -f log/repeater_*.log | grep -i status
# Should see: "Status sent to server: Battery=85%"

# On server
tail -f log/IQRight_Server.debug | grep -i status
# Should see: "STATUS from Node 200: Battery=85%"

# Check device_status.log
tail -f log/device_status.log
```

### Device Not Waking Up

**Symptoms**: Device doesn't wake at 1:00 PM

**Check alarm settings**:
```bash
# Verify alarm is enabled
echo "get rtc_alarm_enabled" | nc -q 0 127.0.0.1 8423
# Should return: "rtc_alarm_enabled: true"

# Verify alarm time
echo "get rtc_alarm_time" | nc -q 0 127.0.0.1 8423
# Should return: "rtc_alarm_time: 2000-01-01T13:00:00..."

# Verify alarm repeat
echo "get alarm_repeat" | nc -q 0 127.0.0.1 8423
# Should return: "alarm_repeat: 127"

# Re-run setup if incorrect
./setup_pisugar_schedule.sh
```

## Solar Panel Recommendations

For **autonomous outdoor operation**:

### Panel Specs
- **Voltage**: 5V (USB output)
- **Current**: 2A minimum (3A recommended)
- **Power**: 10W minimum (15W recommended)
- **Connector**: USB-C or USB-A to USB-C cable

### Example Panels
- BigBlue 5V 10W USB Solar Panel
- ALLPOWERS 5V 18W Solar Charger
- Anker 21W Dual Port Solar Charger

### Installation Tips
1. **Angle panel** to maximize sun exposure
2. **Weatherproof enclosure** for Pi and electronics
3. **Ventilation** to prevent overheating
4. **Cable management** to prevent water ingress

### Power Calculations

**Daily power budget**:
- Repeater operation: 4 hours × 500mA = 2000mAh
- PiSugar battery: 1200mAh capacity
- **Charging needed**: ~2000mAh per day

**Solar charging (conservative estimates)**:
- 10W panel in full sun (6 hours): ~12Wh = ~2400mAh @ 5V
- **Result**: Adequate for daily operation + reserve
