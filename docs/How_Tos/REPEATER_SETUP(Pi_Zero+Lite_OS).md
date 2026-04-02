# IQRight Repeater Setup Guide

Complete guide for deploying the IQRight LoRa repeater on a Raspberry Pi Zero W — from building the bundle on your Mac to a fully configured, auto-starting repeater with Cython-compiled source.

---

## Architecture Overview

The repeater runs a **headless service** on a Pi Zero W with Lite OS:

```
    ┌──────────────────┐
    │  Pi Zero W       │
    │                  │
    │  repeater.py     │◀───▶ RFM9x LoRa Radio (SPI)
    │  (systemd svc)   │      ├─ Forwards scanner ↔ server packets
    │                  │      └─ Extends network range
    │                  │
    │  OLED display    │◀──── SSD1306 128x64 (I2C, optional)
    │  PiSugar 3       │◀──── Battery + RTC (I2C, optional)
    └──────────────────┘
```

| Component | Description |
|-----------|-------------|
| `repeater.py` | Main application — packet forwarding, OLED, battery monitoring |
| `run_repeater.py` | Launcher script (imports `repeater`) |
| `lora/` | Binary packet protocol package |
| `utils/config.py` | Repeater configuration |
| `utils/oled_display.py` | OLED display manager (auto-off, battery optimized) |
| `utils/pisugar_monitor.py` | PiSugar 3 battery monitor (optional) |

### Installation Paths

| Component | Path |
|-----------|------|
| Application | `/home/iqright/` |
| Virtual environment | `/home/iqright/.venv/` |
| Configuration | `/home/iqright/.env` |
| Active config | `/home/iqright/utils/config.py` |
| Logs | `/home/iqright/log/` |
| Systemd service | `/etc/systemd/system/iqright-repeater.service` |
| Shutdown cron script | `/usr/local/bin/shutdown_repeater.sh` |

---

## Prerequisites

### Hardware

- Raspberry Pi Zero W
- RFM9x LoRa module (915 MHz for US) connected via SPI
- SD card with Raspberry Pi OS Lite (32-bit)
- (Optional) SSD1306 128x64 I2C OLED display
- (Optional) PiSugar 3 battery UPS with RTC + solar panel
- (Optional) RTC module for scheduled wake-up (if not using PiSugar)

### Hardware Connections

```
Pi Zero W GPIO Pinout:

RFM9x LoRa (SPI):               OLED SSD1306 (I2C):
  MISO → GPIO 9                    VCC → Pin 1 (3.3V)
  MOSI → GPIO 10                   SDA → Pin 3 (GPIO 2)
  SCK  → GPIO 11                   SCL → Pin 5 (GPIO 3)
  CS   → GPIO 7 (CE1)              GND → Pin 6
  RST  → GPIO 25
  VIN  → 3.3V                   PiSugar 3 (I2C):
  GND  → GND                       Connects via pogo pins (no wiring)
                                    I2C address: 0x57
```

> **No pin conflicts** between LoRa (SPI) and OLED/PiSugar (I2C).

### On Your Development Machine

- Access to the IQRight project repository
- FTP server running (default: `192.168.7.151:5009`)

---

## The Image

Use **Raspberry Pi OS Lite (64-bit)** from Raspberry Pi Imager:

- OS: **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (64-bit)**
- In the imager settings (gear icon), configure:
  - **Enable SSH** (password or key)
  - **Set username/password** (e.g., `iqright`)
  - **Configure WiFi** (SSID + password)
  - **Set locale/timezone**

This gives you a headless-ready image with WiFi from first boot.

---

## Step-by-Step Deployment

### Step 1: Build the Repeater Bundle (on your Mac)

From the project root on your development machine:

```bash
cd ~/Documents/Code/IQRight/Local/IQRight_Local
./utility_tools/setup/build_repeater_bundle.sh
```

This creates `repeater_bundle.tar.gz` in the project root containing:

```
repeater_bundle/
├── repeater.py                   # Main application
├── run_repeater.py               # Launcher (imports repeater)
├── build_cython.py               # Cython compilation script
├── setup_repeater.sh             # Pi setup script
├── shutdown_repeater.sh          # Cron shutdown script
├── setup_pisugar_schedule.sh     # PiSugar RTC config (optional)
├── lora/                         # Binary packet protocol
│   ├── __init__.py
│   ├── packet_handler.py
│   ├── node_types.py
│   └── collision_avoidance.py
├── utils/
│   ├── __init__.py
│   ├── config.repeater.py        # Config template (→ config.py)
│   ├── oled_display.py           # OLED display manager
│   └── pisugar_monitor.py        # PiSugar battery monitor (if available)
├── configs/
│   └── requirements.repeater.txt # Python dependencies (minimal)
└── log/                          # Empty log directory
```

### Step 2: Upload the Bundle to FTP

Copy the generated `repeater_bundle.tar.gz` to the root of your FTP server:

```bash
# Example using scp to the FTP server machine
scp repeater_bundle.tar.gz fulviomanente@192.168.7.151:~/
```

Or use any FTP client to place it at the FTP server root.

### Step 3: Flash the SD Card and Boot the Pi

1. Flash Raspberry Pi OS Lite (32-bit) to the SD card using Raspberry Pi Imager
2. Configure SSH, WiFi, username/password in the imager settings
3. Insert the SD card into the Pi Zero W and power on
4. Wait ~60 seconds for first boot

### Step 4: SSH into the Pi and Update

```bash
ssh iqright@raspberrypi.local
```

Update the system first:

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 5: Copy the Setup Script to the Pi

From your Mac:

```bash
# SCP the setup script to the Pi
scp utility_tools/setup/repeater/setup_repeater.sh iqright@<pi-ip>:~/
```

> The setup script is also included inside the bundle, but you need it on the Pi *before* the bundle is downloaded.

### Step 6: Run the Setup Script on the Pi

```bash
chmod +x setup_repeater.sh
sudo ./setup_repeater.sh
```

The script performs **10 automated steps**:

| Step | What It Does |
|------|-------------|
| 1 | Installs system packages: Python 3, pip, venv, dev tools, gcc, I2C tools, FTP client |
| 2 | Downloads `repeater_bundle.tar.gz` from the FTP server |
| 3 | Extracts bundle to `/home/iqright/`, copies `config.repeater.py` → `config.py` |
| 4 | Creates Python venv (`.venv/`), installs dependencies from `requirements.repeater.txt` |
| 5 | **Compiles with Cython** — installs Cython + gcc, compiles `.py` → `.so`, removes source files (10-30 min on Pi Zero) |
| 6 | **Configures repeater node ID** — prompts for ID (200-256), creates `.env` |
| 7 | **Enables I2C** for OLED display and PiSugar, adds user to `i2c` group, configures passwordless shutdown |
| 8 | **Creates systemd service** — `iqright-repeater.service` with auto-restart on crash |
| 9 | **Configures daily shutdown** — cron job at 6:00 PM via `/usr/local/bin/shutdown_repeater.sh` |
| 10 | **Silent boot** — disables splash, quiet kernel, masks console login |

At the end, the script verifies the installation and offers to reboot.

### Step 7: Verify Everything Works

After reboot, the repeater service starts automatically. SSH in to verify:

```bash
ssh iqright@<pi-ip>

# Check the service is running
sudo systemctl status iqright-repeater

# Check application logs
tail -f /home/iqright/log/repeater_*.log

# Check system journal
sudo journalctl -u iqright-repeater -f
```

The OLED display (if connected) should show:
1. "IQRight Scanner Starting..." for 2 seconds
2. "Repeater Ready / Node ID: 200 / Listening..." for 30 seconds
3. Auto-off (display goes dark to save battery)
4. Briefly flashes when forwarding packets

### Step 8: Configure PiSugar Schedule (Optional)

If using PiSugar 3 for battery + RTC wake-up:

```bash
cd /home/iqright
sudo ./setup_pisugar_schedule.sh
```

This configures:
- Wake-up at 1:00 PM daily via RTC alarm
- Safe shutdown at 5% battery
- Repeat every day of the week

### Step 9: Verify I2C Devices (Optional)

If you connected an OLED display or PiSugar:

```bash
# Check if I2C is enabled
ls /dev/i2c-*
# Should show: /dev/i2c-1

# Scan for I2C devices
sudo i2cdetect -y 1
```

Expected output:
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- 3c -- -- --   ← OLED at 0x3C
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- 57 -- -- -- -- -- -- -- --   ← PiSugar at 0x57
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

---

## Environment Variable Overrides

The setup script accepts optional environment variables to customize the installation:

```bash
# Example: custom FTP server and install directory
FTP_HOST=10.0.0.50 FTP_PORT=21 INSTALL_DIR=/opt/repeater sudo ./setup_repeater.sh
```

| Variable | Default | Description |
|----------|---------|-------------|
| `FTP_HOST` | `192.168.7.151` | FTP server IP address |
| `FTP_PORT` | `5009` | FTP server port |
| `FTP_USER` | `fulviomanente` | FTP username |
| `FTP_PASS` | `1234` | FTP password |
| `INSTALL_DIR` | `/home/iqright` | Installation directory |

---

## Cython Compilation

The setup script compiles all Python source to native `.so` extensions using Cython. This protects the source code on deployed devices.

### What Gets Compiled

- `repeater.py` → `repeater.*.so`
- `lora/packet_handler.py` → `packet_handler.*.so`
- `lora/node_types.py` → `node_types.*.so`
- `lora/collision_avoidance.py` → `collision_avoidance.*.so`
- `utils/config.py` → `config.*.so`
- `utils/oled_display.py` → `oled_display.*.so`
- `utils/pisugar_monitor.py` → `pisugar_monitor.*.so` (if present)

### What Stays as `.py`

- `__init__.py` files (required for Python package imports)
- `run_repeater.py` (launcher — imports `repeater`)
- `build_cython.py` (the build script itself)

### After Compilation

- All `.py` source files are deleted (except the exclusions above)
- All `.c` intermediate files are deleted
- The `build/` directory is removed
- Only `.so` compiled files remain

### If Compilation Fails

The setup script falls back gracefully — it keeps the `.py` source files and the repeater runs normally from Python source. A warning is printed but setup continues.

---

## Repeater Node Configuration

Each repeater needs a unique node ID in the range **200-256**:

| Node ID | Location | Description |
|---------|----------|-------------|
| 200 | (first repeater) | Default repeater |
| 201-256 | (available) | Additional repeaters |

The node ID is stored in `/home/iqright/.env`:

```env
LORA_NODE_TYPE=REPEATER
LORA_NODE_ID=200
LORA_FREQUENCY=915.23
LORA_TX_POWER=23
LORA_TTL=3
LORA_ENABLE_CA=TRUE
```

To change the node ID after setup, edit `.env` and restart the service:

```bash
sudo systemctl restart iqright-repeater
```

---

## Daily Operation Schedule

The repeater is configured for autonomous operation with daily shutdown and RTC wake-up:

```
┌─────────────────────────────────────────────────────┐
│ Daily Schedule                                      │
├─────────────────────────────────────────────────────┤
│ RTC Wake-up         → Pi powers on                  │
│ ~30 seconds later   → Repeater service auto-starts  │
│ (school hours)      → Forwards LoRa packets         │
│ 6:00 PM             → Cron triggers shutdown         │
│ (overnight)         → Pi off / solar charging        │
│ Next day            → RTC wakes Pi again             │
└─────────────────────────────────────────────────────┘
```

**Shutdown mechanism**: A cron job runs `/usr/local/bin/shutdown_repeater.sh` at 6:00 PM daily, which calls `shutdown -h now`. The RTC (either PiSugar or external RTC module) is responsible for waking the Pi on the next day.

> **Note**: The repeater software (`repeater.py`) also has a built-in software shutdown at 5:00 PM as a safety net. The cron job at 6:00 PM acts as a fallback in case the software shutdown doesn't trigger.

---

## Updating the Repeater

### Full Update (Rebuild + Redeploy)

```bash
# 1. On your Mac: rebuild the bundle
cd ~/Documents/Code/IQRight/Local/IQRight_Local
./utility_tools/setup/build_repeater_bundle.sh

# 2. Upload to FTP server
scp repeater_bundle.tar.gz fulviomanente@192.168.7.151:~/

# 3. On the Pi: re-run setup (overwrites application files, preserves .env)
sudo ./setup_repeater.sh
```

The setup script is idempotent — it safely overwrites existing files, re-creates the venv, and preserves your `.env`. It will re-compile with Cython.

### Manual File Update (Single File)

```bash
# Example: update just repeater.py (bypasses Cython)
scp repeater.py iqright@<pi-ip>:/home/iqright/
ssh iqright@<pi-ip>
sudo systemctl restart iqright-repeater
```

> Note: Manually copied `.py` files won't be Cython-compiled. For production, always use the full bundle + setup workflow.

---

## What You End Up With

| Aspect | Behavior |
|--------|----------|
| **Boot** | Silent boot → systemd starts repeater service automatically |
| **SSH** | Works normally, full shell access |
| **WiFi** | Stays connected for SSH and troubleshooting |
| **Service** | `iqright-repeater.service` managed by systemd |
| **App crash** | Systemd auto-restarts after 10 seconds (max 5 restarts per 5 min) |
| **Source code** | Compiled to native `.so` — no readable Python on device |
| **OLED** | Shows forwarding activity, stats every 60s, auto-off after 30s |
| **Shutdown** | Cron at 6:00 PM + software shutdown at 5:00 PM (dual safety) |
| **Wake-up** | RTC alarm (PiSugar or external RTC) |

---

## What the Setup Script Creates

| Item | Description |
|------|-------------|
| `/home/iqright/.venv/` | Python virtual environment |
| `/home/iqright/.env` | Node configuration (repeater ID, LoRa settings) |
| `/home/iqright/utils/config.py` | Active config (copied from `config.repeater.py`) |
| `/home/iqright/log/` | Log directory |
| `/etc/systemd/system/iqright-repeater.service` | Systemd service (auto-start, crash recovery) |
| `/usr/local/bin/shutdown_repeater.sh` | Daily shutdown script |
| Root crontab entry | `0 18 * * *` triggers shutdown at 6:00 PM |
| `/etc/sudoers.d/repeater-shutdown` | Passwordless shutdown for repeater user |
| I2C enabled | `/dev/i2c-1` available for OLED and PiSugar |

### Python Dependencies (requirements.repeater.txt)

| Package | Purpose |
|---------|---------|
| `python-dotenv` | Load `.env` configuration |
| `adafruit-circuitpython-rfm9x` | LoRa radio hardware driver |
| `adafruit-blinka` | CircuitPython compatibility layer |
| `adafruit-circuitpython-ssd1306` | OLED display driver (optional) |
| `pillow` | OLED graphics rendering (optional) |

> `cython`, `python3-dev`, and `gcc` are installed during setup for compilation only.
> `smbus` (for PiSugar I2C) is a system package, not installed via pip.

---

## Useful Commands

```bash
# Service management
sudo systemctl start iqright-repeater      # Start
sudo systemctl stop iqright-repeater       # Stop
sudo systemctl restart iqright-repeater    # Restart
sudo systemctl status iqright-repeater     # Status
sudo systemctl disable iqright-repeater    # Disable auto-start

# Logs
sudo journalctl -u iqright-repeater -f     # Live system journal
tail -f /home/iqright/log/repeater_*.log   # Application log

# I2C diagnostics
sudo i2cdetect -y 1                        # Scan I2C bus

# Manual test run
cd /home/iqright
source .venv/bin/activate
python3 run_repeater.py                    # Run in foreground
```

---

## Troubleshooting

### Repeater service doesn't start on boot

- Check service status: `sudo systemctl status iqright-repeater`
- Check journal: `sudo journalctl -u iqright-repeater -n 50`
- Verify service is enabled: `sudo systemctl is-enabled iqright-repeater`
- Verify `.env` exists: `cat /home/iqright/.env`
- Verify venv Python exists: `ls -la /home/iqright/.venv/bin/python3`

### Service starts but crashes repeatedly

- Check the application log: `tail -50 /home/iqright/log/repeater_*.log`
- Check if LoRa hardware is detected (SPI): `ls /dev/spidev*`
- Try running manually to see errors:
  ```bash
  cd /home/iqright
  source .venv/bin/activate
  python3 run_repeater.py
  ```
- Check systemd restart count: `systemctl show iqright-repeater --property=NRestarts`

### OLED display not working

- Verify I2C is enabled: `ls /dev/i2c-*` (should show `/dev/i2c-1`)
- Scan I2C bus: `sudo i2cdetect -y 1` (should show `3c` or `3d`)
- Check wiring: VCC→3.3V, SDA→GPIO2, SCL→GPIO3, GND→GND
- Some OLEDs use address `0x3D` instead of `0x3C` — the code tries both

### LoRa packets not forwarded

- Check frequency match across all nodes (default: 915.23 MHz)
- Check TX power setting in `.env` (default: 23 dBm)
- Verify RFM9x hardware is detected: `ls /dev/spidev*`
- Check CRC errors in repeater log
- Verify node ID is in repeater range (200-256)

### Pi doesn't wake up on schedule

- Verify RTC module is working (PiSugar: `echo "get battery" | nc 127.0.0.1 8423`)
- Re-run PiSugar schedule setup: `sudo ./setup_pisugar_schedule.sh`
- For external RTC: verify the alarm is set correctly
- Check RTC battery (PiSugar uses the main battery; external RTCs use coin cells)

### Pi doesn't shut down at 6 PM

- Verify cron job exists: `sudo crontab -l | grep shutdown`
- Verify shutdown script exists: `ls -la /usr/local/bin/shutdown_repeater.sh`
- Check cron logs: `grep CRON /var/log/syslog`
- Test manually: `sudo /usr/local/bin/shutdown_repeater.sh`

### Cython compilation fails during setup

- The setup script continues with `.py` source files if compilation fails
- Common causes: insufficient disk space, missing `python3-dev` or `gcc`
- To retry compilation manually:
  ```bash
  cd /home/iqright
  source .venv/bin/activate
  pip install cython
  sudo apt install -y python3-dev gcc
  python build_cython.py build_ext --inplace
  ```

### WiFi drops after a while

- Add a keep-alive cron job:
  ```bash
  crontab -e
  ```
  Add:
  ```
  */5 * * * * ping -c 1 8.8.8.8 > /dev/null 2>&1 || sudo systemctl restart networking
  ```

---

## Quick Reference Card

```
REPEATER DEPLOYMENT CHEAT SHEET
================================

On Mac:
  1. ./utility_tools/setup/build_repeater_bundle.sh
  2. scp repeater_bundle.tar.gz fulviomanente@192.168.7.151:~/

On Pi (first time):
  3. scp setup_repeater.sh to Pi
  4. sudo ./setup_repeater.sh
  5. Enter node ID (200-256) when prompted
  6. Reboot when prompted

On Pi (updates):
  1. Rebuild bundle on Mac
  2. Upload to FTP
  3. sudo ./setup_repeater.sh on Pi

Verify:
  sudo systemctl status iqright-repeater
  tail -f /home/iqright/log/repeater_*.log
  sudo i2cdetect -y 1
```