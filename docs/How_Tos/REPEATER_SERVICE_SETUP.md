# IQRight Repeater Service Setup Guide

This guide covers the setup and management of the IQRight LoRa repeater as a systemd service with automatic restart capabilities and comprehensive status monitoring.

## Overview

The repeater service system consists of two main scripts:

1. **`setup_repeater_service.sh`** - Registers repeater.py as a systemd service
2. **`repeater_status.sh`** - Displays comprehensive status dashboard

## Quick Start

### 1. Install Repeater Service

```bash
# Run with sudo
sudo ./setup_repeater_service.sh

# Or specify node ID directly (200-256)
sudo ./setup_repeater_service.sh 200
```

**What it does:**
- Validates node ID is in range 200-256
- Creates/updates `.env` file with `LORA_NODE_ID`
- Creates systemd service file with auto-restart on crash
- Enables service to start on boot
- Optionally starts the service immediately

### 2. Check Status

```bash
# Single status check
./repeater_status.sh

# Continuous monitoring (refreshes every 5 seconds)
./repeater_status.sh --watch
```

**What it shows:**
- 📅 Timestamp and hostname
- 🔢 Configured node ID
- 🌐 Network status (eth0 and wlan0 IP addresses)
- ⚙️ Service status (running/stopped/failed)
- ⏱️ Service uptime
- 🔋 Power/battery status (placeholder)
- 📊 Recent activity (last 5 log entries)
- 💡 Quick command reference

## Detailed Usage

### Service Setup Script

**Syntax:**
```bash
sudo ./setup_repeater_service.sh [NODE_ID]
```

**Parameters:**
- `NODE_ID` (optional): Repeater node ID (200-256). Will prompt if not provided.

**Requirements:**
- Must run as root (sudo)
- `repeater.py` must exist in project root
- Python 3.x installed

**Features:**

1. **Node ID Validation**
   - Ensures ID is between 200-256
   - Updates or creates `.env` file

2. **Virtual Environment Detection**
   - Automatically detects `.venv` or `venv` directory
   - Falls back to system Python if not found

3. **Systemd Service Configuration**
   - Auto-restart on crash (`Restart=always`)
   - 10-second delay before restart
   - Rate limiting (5 restarts per 5 minutes)
   - Proper environment variable handling
   - Journal logging integration

4. **Log Directory Setup**
   - Creates `log/` directory if missing
   - Sets proper ownership

**Example Output:**
```
========================================
IQRight Repeater Service Setup
========================================

Running as user: pi
Project root: /home/pi/IQRight_Local

Configuring repeater with Node ID: 200
Using Python from: /home/pi/IQRight_Local/.venv/bin/python3
Created log directory: /home/pi/IQRight_Local/log
Service file created

Reloading systemd daemon...
Enabling service to start on boot...

Do you want to start the repeater service now? (y/n) y
Starting iqright-repeater service...
✓ Service started successfully!

========================================
Setup Complete!
========================================

Useful Commands:
  Start:   sudo systemctl start iqright-repeater
  Stop:    sudo systemctl stop iqright-repeater
  Restart: sudo systemctl restart iqright-repeater
  Status:  sudo systemctl status iqright-repeater
  Logs:    sudo journalctl -u iqright-repeater -f
  Disable: sudo systemctl disable iqright-repeater

Log files:
  Application: /home/pi/IQRight_Local/log/repeater_200.log
  System:      journalctl -u iqright-repeater
```

### Status Dashboard Script

**Syntax:**
```bash
./repeater_status.sh [--watch]
```

**Options:**
- `--watch`: Continuously refresh display every 5 seconds

**Features:**

1. **Network Status**
   - Shows all network interfaces (eth0, wlan0)
   - IP addresses with color coding
   - Connection status

2. **Service Monitoring**
   - Running/stopped/failed status
   - Uptime calculation
   - Boot auto-start status
   - Installation verification

3. **Node Configuration**
   - Displays configured node ID from `.env`
   - Warns if not configured

4. **Power Status**
   - Battery level (placeholder - ready for integration)
   - AC power detection
   - Status indicator

5. **Recent Activity**
   - Last 5 log entries from systemd journal
   - Color-coded by severity (errors in red, warnings in yellow)
   - Timestamp for each entry

6. **Quick Commands**
   - Common management commands
   - Copy-paste ready

**Example Output:**
```
╔════════════════════════════════════════════════════════════╗
║         IQRight LoRa Repeater Status Dashboard         ║
╚════════════════════════════════════════════════════════════╝

📅 Timestamp: 2025-02-14 10:30:45
🖥️  Hostname: repeater-200

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔢 Node Configuration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Node ID: 200

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 Network Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  eth0: 192.168.1.100
  wlan0: 10.0.0.50

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️  Service Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Status: ● Running
  Uptime: 2h 15m
  Boot:   Enabled (auto-start)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔋 Power Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  AC Power / Not Available
  Note: Battery monitoring not yet implemented

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Recent Activity (last 5 log entries)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  2025-02-14T10:28:30+00:00 Forwarding packet: Source=102, Dest=1
  2025-02-14T10:28:25+00:00 Received packet from node 102
  2025-02-14T10:27:15+00:00 === Repeater Stats (Uptime: 2.2h) ===
  2025-02-14T10:27:15+00:00 Forward Rate: 98.5%
  2025-02-14T10:25:00+00:00 Repeater ready, listening for packets...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Quick Commands
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  View logs:    sudo journalctl -u iqright-repeater -f
  Restart:      sudo systemctl restart iqright-repeater
  Stop:         sudo systemctl stop iqright-repeater
  Start:        sudo systemctl start iqright-repeater
  Full status:  sudo systemctl status iqright-repeater
```

## Service Management

### Common Commands

**Start Service:**
```bash
sudo systemctl start iqright-repeater
```

**Stop Service:**
```bash
sudo systemctl stop iqright-repeater
```

**Restart Service:**
```bash
sudo systemctl restart iqright-repeater
```

**Check Status:**
```bash
sudo systemctl status iqright-repeater
```

**View Live Logs:**
```bash
sudo journalctl -u iqright-repeater -f
```

**View Last 50 Log Lines:**
```bash
sudo journalctl -u iqright-repeater -n 50
```

**Enable Auto-Start on Boot:**
```bash
sudo systemctl enable iqright-repeater
```

**Disable Auto-Start:**
```bash
sudo systemctl disable iqright-repeater
```

### Service Configuration File

Location: `/etc/systemd/system/iqright-repeater.service`

**Key Features:**
- `Restart=always` - Auto-restart on crash
- `RestartSec=10` - 10-second delay before restart
- `StartLimitBurst=5` - Max 5 restarts
- `StartLimitInterval=300` - Within 5 minutes

**To modify:**
```bash
sudo nano /etc/systemd/system/iqright-repeater.service
sudo systemctl daemon-reload
sudo systemctl restart iqright-repeater
```

## Log Files

### Application Logs

Location: `{PROJECT_ROOT}/log/repeater_{NODE_ID}.log`

Example: `/home/pi/IQRight_Local/log/repeater_200.log`

**View:**
```bash
tail -f ~/IQRight_Local/log/repeater_200.log
```

**Features:**
- Rotating log files (max 10MB per file)
- 5 backup files maintained
- Detailed packet forwarding info
- Statistics every 5 minutes

### System Logs (Journald)

**View all logs:**
```bash
sudo journalctl -u iqright-repeater
```

**Follow live logs:**
```bash
sudo journalctl -u iqright-repeater -f
```

**Filter by time:**
```bash
# Last hour
sudo journalctl -u iqright-repeater --since "1 hour ago"

# Last 24 hours
sudo journalctl -u iqright-repeater --since "1 day ago"

# Specific date
sudo journalctl -u iqright-repeater --since "2025-02-14"
```

**Filter by priority:**
```bash
# Errors only
sudo journalctl -u iqright-repeater -p err

# Warnings and above
sudo journalctl -u iqright-repeater -p warning
```

## Troubleshooting

### Service Won't Start

**Check status:**
```bash
sudo systemctl status iqright-repeater
```

**Common issues:**

1. **Invalid Node ID**
   - Error: "Invalid repeater node ID"
   - Fix: Ensure `.env` has `LORA_NODE_ID` between 200-256

2. **Python Environment Not Found**
   - Error: "No such file or directory: .venv/bin/python3"
   - Fix: Create virtual environment or update service file to use system Python

3. **LoRa Hardware Not Detected**
   - Error: "Failed to initialize LoRa"
   - Fix: Check SPI enabled, hardware connections

4. **Permission Issues**
   - Error: "Permission denied"
   - Fix: Ensure log directory exists and has correct ownership

### Service Crashes Immediately

**View crash logs:**
```bash
sudo journalctl -u iqright-repeater -n 100
```

**Check application log:**
```bash
tail -n 50 ~/IQRight_Local/log/repeater_*.log
```

**Test manually:**
```bash
cd ~/IQRight_Local
source .venv/bin/activate
LORA_NODE_ID=200 python3 repeater.py
```

### Service Not Restarting After Crash

**Check restart limits:**
```bash
systemctl show iqright-repeater -p NRestarts
systemctl show iqright-repeater -p StartLimitBurst
```

**Reset failed state:**
```bash
sudo systemctl reset-failed iqright-repeater
sudo systemctl start iqright-repeater
```

### No Network Connection

**Check interfaces:**
```bash
ip addr show
```

**Test connectivity:**
```bash
ping -c 3 8.8.8.8  # Test internet
ping -c 3 192.168.1.1  # Test gateway
```

**Restart networking:**
```bash
sudo systemctl restart networking
```

## Advanced Configuration

### Custom Restart Delays

Edit service file:
```bash
sudo nano /etc/systemd/system/iqright-repeater.service
```

Modify restart settings:
```ini
[Service]
Restart=always
RestartSec=30           # 30 seconds instead of 10
StartLimitBurst=10      # Allow 10 restarts instead of 5
StartLimitInterval=600  # Within 10 minutes instead of 5
```

Apply changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart iqright-repeater
```

### Running Multiple Repeaters

To run multiple repeater services on the same device (different node IDs):

1. Copy service file:
```bash
sudo cp /etc/systemd/system/iqright-repeater.service \
     /etc/systemd/system/iqright-repeater-201.service
```

2. Edit new service file:
```bash
sudo nano /etc/systemd/system/iqright-repeater-201.service
```

3. Change:
```ini
Description=IQRight LoRa Repeater Node 201
Environment="LORA_NODE_ID=201"
SyslogIdentifier=iqright-repeater-201
```

4. Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable iqright-repeater-201
sudo systemctl start iqright-repeater-201
```

### Auto-Start Status Script on Boot

To show status on login, add to `.bashrc` or `.profile`:

```bash
echo '# IQRight Repeater Status' >> ~/.bashrc
echo '~/IQRight_Local/repeater_status.sh' >> ~/.bashrc
```

Or create a systemd service to display on boot:
```bash
sudo nano /etc/systemd/system/repeater-status-display.service
```

```ini
[Unit]
Description=Display Repeater Status on Boot
After=iqright-repeater.service

[Service]
Type=oneshot
User=pi
ExecStart=/home/pi/IQRight_Local/repeater_status.sh
StandardOutput=journal+console

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable repeater-status-display
```

## Battery Monitoring Integration

The repeater system includes **full INA219 battery monitoring integration**!

### ✅ Already Integrated

Battery monitoring using INA219 power sensor is **fully implemented**:
- ✅ `utils/battery_monitor.py` - Reads voltage, current, power, and calculates percentage
- ✅ `repeater_status.sh` - Automatically detects and uses INA219
- ✅ Color-coded display (green/yellow/red based on charge level)
- ✅ Automatic fallback to system battery if INA219 not available
- ✅ Graceful error handling

### Setup Required

1. **Connect INA219** to Raspberry Pi I2C (GPIO 2/3)
2. **Enable I2C**: `sudo raspi-config` → Interface Options → I2C → Enable
3. **Install I2C tools**: `sudo apt-get install -y i2c-tools python3-smbus`
4. **Test**: `python3 utils/battery_monitor.py`

**That's it!** The status script will automatically start showing real battery data.

### Documentation

For complete INA219 setup, wiring diagrams, calibration, and troubleshooting:
- **See**: [BATTERY_MONITORING_INA219.md](../BATTERY_MONITORING_INA219.md)

## Security Considerations

### Service Runs as Non-Root

The service runs as the configured user (typically `pi`), not root. This is a security best practice.

### File Permissions

Ensure proper permissions:
```bash
# Service file (readable by all, writable by root)
sudo chmod 644 /etc/systemd/system/iqright-repeater.service

# Scripts (executable by owner, readable by all)
chmod 755 setup_repeater_service.sh repeater_status.sh

# Log directory (writable by service user)
chmod 755 log/
```

## Maintenance

### Regular Health Checks

Run status script daily:
```bash
# Add to crontab
crontab -e
```

Add line:
```
0 */4 * * * /home/pi/IQRight_Local/repeater_status.sh >> /home/pi/repeater_health_$(date +\%Y\%m\%d).log 2>&1
```

### Log Rotation

Application logs rotate automatically (RotatingFileHandler).

For journal logs, configure journald:
```bash
sudo nano /etc/systemd/journald.conf
```

Set limits:
```ini
[Journal]
SystemMaxUse=500M
SystemMaxFileSize=50M
```

Apply:
```bash
sudo systemctl restart systemd-journald
```

## See Also

- [BATTERY_MONITORING_INA219.md](../BATTERY_MONITORING_INA219.md) - INA219 battery monitoring setup
- [OLED_SETUP.md](../OLED_SETUP.md) - Repeater OLED display setup
- [OLED_IMPLEMENTATION_SUMMARY.md](../OLED_IMPLEMENTATION_SUMMARY.md) - OLED implementation details
- [CLAUDE.md](../../CLAUDE.md) - Project overview
- [QUICKSTART.md](../QUICKSTART.md) - Quick start guide

## Support

For issues:
1. Check service status: `sudo systemctl status iqright-repeater`
2. View logs: `sudo journalctl -u iqright-repeater -n 100`
3. Run status script: `./repeater_status.sh`
4. Test manually: `LORA_NODE_ID=200 python3 repeater.py`
5. Review this documentation

## Version History

- **v1.0** (2025-02-14) - Initial release
  - Service setup script
  - Status dashboard script
  - Auto-restart on crash
  - Comprehensive monitoring
  - Battery monitoring placeholder
