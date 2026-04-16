# IQRight Repeater Setup Guide

Complete guide for deploying the IQRight LoRa repeater on a Raspberry Pi Zero W — from building the bundle on your Mac to a fully configured, auto-starting repeater with Cython-compiled source.

---

## Architecture Overview

The repeater runs a **headless service** on a Pi Zero W with Lite OS. It supports two power management options:

```
    ┌──────────────────┐
    │  Pi Zero W       │
    │                  │
    │  repeater.py     │◀───▶ RFM9x LoRa Radio (SPI)
    │  (systemd svc)   │      ├─ Forwards scanner ↔ server packets
    │                  │      └─ Extends network range
    │                  │
    │  OLED display    │◀──── SSD1306 128x64 (I2C, optional)
    │                  │
    │  Power HAT       │◀──── Waveshare Power Management HAT (default)
    │  (choose one)    │      └─ Shutdown via GPIO 20, status via serial
    │                  │      OR
    │                  │      PiSugar 3 (alternative)
    │                  │      └─ Battery + RTC via I2C, cron shutdown
    └──────────────────┘
```

| Component | Description |
|-----------|-------------|
| `repeater.py` | Main application — packet forwarding, OLED, power monitoring |
| `run_repeater.py` | Launcher script (imports `repeater`) |
| `lora/` | Binary packet protocol package |
| `utils/config.py` | Repeater configuration (HAT-aware pin selection) |
| `utils/oled_display.py` | OLED display manager (auto-off, battery optimized) |
| `utils/waveshare_monitor.py` | Waveshare HAT power monitor (Vin, Vout, RTC alerts) |
| `utils/pisugar_monitor.py` | PiSugar 3 battery monitor (optional alternative) |

### Installation Paths

| Component | Path |
|-----------|------|
| Application | `/home/iqright/` |
| Virtual environment | `/home/iqright/.venv/` |
| Configuration | `/home/iqright/.env` |
| Active config | `/home/iqright/utils/config.py` |
| Logs | `/home/iqright/log/` |
| Systemd service | `/etc/systemd/system/iqright-repeater.service` |
| Shutdown cron script | `/usr/local/bin/shutdown_repeater.sh` (PiSugar only) |

---

## Prerequisites

### Hardware

- Raspberry Pi Zero W
- RFM9x LoRa module (915 MHz for US) connected via SPI
- SD card with Raspberry Pi OS Lite (64-bit)
- Power management HAT (choose one):
  - **Waveshare Power Management HAT** (default) — RTC, serial monitoring, GPIO shutdown signal
  - **PiSugar 3** (alternative) — Battery UPS with RTC + solar panel, I2C monitoring
- (Optional) SSD1306 128x64 I2C OLED display

### Hardware Connections

>**Waveshare Power Management HAT (default):**
>
> The Waveshare HAT uses GPIO 7 and GPIO 25, so LoRa CS/RST pins must be moved.
> The setup automatically configures the correct pins based on your HAT selection.

```
RFM9x LoRa (SPI):               OLED SSD1306 (I2C):
  MISO → GPIO 9                    VCC → Pin 1 (3.3V)
  MOSI → GPIO 10                   SDA → Pin 3 (GPIO 2)
  SCK  → GPIO 11                   SCL → Pin 5 (GPIO 3)
  CS   → GPIO 17 (moved!)          GND → Pin 6
  RST  → GPIO 16 (moved!)
  VIN  → 3.3V                   Waveshare HAT:
  GND  → GND                       Shutdown signal → GPIO 20 (input)
                                    Running signal  → GPIO 21 (output)
                                    Status serial   → /dev/ttyS0 (115200 baud)
```

>**PiSugar 3 (alternative):**
>
> PiSugar uses I2C only (pogo pins). No GPIO conflict — standard LoRa pins work.

```
RFM9x LoRa (SPI):               OLED SSD1306 (I2C):
  MISO → GPIO 9                    VCC → Pin 1 (3.3V)
  MOSI → GPIO 10                   SDA → Pin 3 (GPIO 2)
  SCK  → GPIO 11                   SCL → Pin 5 (GPIO 3)
  CS   → GPIO 7 (CE1, standard)    GND → Pin 6
  RST  → GPIO 25 (standard)
  VIN  → 3.3V                   PiSugar 3 (I2C):
  GND  → GND                       Connects via pogo pins (no wiring)
                                    I2C address: 0x57
```


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
│   └── waveshare_monitor.py      # Waveshare HAT power monitor
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
| 1 | Installs system packages: Python 3, pip, venv, dev tools, gcc, I2C tools, cron, minicom, FTP client |
| 2 | Downloads `repeater_bundle.tar.gz` from the FTP server |
| 3 | Extracts bundle to `/home/iqright/`, copies `config.repeater.py` → `config.py` |
| 4 | Creates Python venv (`.venv/`), installs dependencies from `requirements.repeater.txt` |
| 5 | **Compiles with Cython** — installs Cython + setuptools + gcc, compiles `.py` → `.so`, removes source files (10-30 min on Pi Zero) |
| 6 | **Configures repeater** — prompts for node ID (200-256), prompts for power HAT (Waveshare/PiSugar), creates `.env` |
| 7 | **Enables I2C** for OLED display, adds user to `i2c` group, configures passwordless shutdown |
| 8 | **Creates systemd service** — `iqright-repeater.service` with auto-restart on crash |
| 9 | **Configures daily shutdown** — Waveshare: skipped (HAT handles via GPIO). PiSugar: creates cron job at 6:00 PM |
| 10 | **Silent boot** — disables splash, quiet kernel, disables console login |

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
1. "IQRight Repeater Starting..." for 2 seconds
2. "Repeater Ready / Node ID: 200 / Listening..." for 30 seconds
3. Auto-off (display goes dark to save battery)
4. Briefly flashes when forwarding packets
5. Stats update every 60 seconds (RX/FWD/DROP + Vin voltage if Waveshare)

### Step 8: Install PiSugar Power Manager (PiSugar only)

If using PiSugar 3, the PiSugar daemon must be installed manually because it requires selecting your Pi model during installation:

```bash
# Download the installer
curl http://cdn.pisugar.com/release/pisugar-power-manager.sh > pisugar-pm.sh

# Run the installer (will prompt for Pi model selection)
sudo bash pisugar-pm.sh
```

After the PiSugar daemon is installed and running, configure the RTC schedule:

```bash
cd /home/iqright
sudo ./setup_pisugar_schedule.sh
```

This configures:
- Wake-up at 1:00 PM daily via RTC alarm
- Safe shutdown at 5% battery
- Repeat every day of the week

> The PiSugar web interface is also available at `http://<pi-ip>:8421` for manual configuration.

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

> **Important**: Cython enforces type annotations as strict C-level checks. In pure Python, `bytes` and `bytearray` are interchangeable, but Cython-compiled code will reject a `bytearray` where `bytes` is annotated. Always wrap external data with `bytes()` before passing it to type-hinted functions (e.g., `rfm9x.receive()` returns `bytearray` — convert with `bytes()` before calling `deserialize(data: bytes)`).

### What Gets Compiled

- `repeater.py` → `repeater.*.so`
- `lora/packet_handler.py` → `packet_handler.*.so`
- `lora/node_types.py` → `node_types.*.so`
- `lora/collision_avoidance.py` → `collision_avoidance.*.so`
- `utils/config.py` → `config.*.so`
- `utils/oled_display.py` → `oled_display.*.so`
- `utils/waveshare_monitor.py` → `waveshare_monitor.*.so`
- `utils/pisugar_monitor.py` → `pisugar_monitor.*.so` (if present in bundle)

### What Stays as `.py`

- `__init__.py` files (required for Python package imports)
- `run_repeater.py` (launcher — imports `repeater`)
- `build_cython.py` (the build script itself)
- `config.repeater.py` (config template — dots in filename break Cython module naming)

### After Compilation

- All `.py` source files are deleted (except the exclusions above)
- All `.c` intermediate files are deleted
- The `build/` directory is removed
- Only `.so` compiled files remain

### If Compilation Fails

The setup script falls back gracefully — it keeps the `.py` source files and the repeater runs normally from Python source. A warning is printed but setup continues.

### Full Compilation (Manual)

```bash
cd /home/iqright
source .venv/bin/activate
pip install cython setuptools
python build_cython.py build_ext --inplace
```

After success, remove the source files:

```bash
# Remove compiled source files (keep __init__.py, run_repeater.py, build_cython.py, config.repeater.py)
rm repeater.py
rm lora/collision_avoidance.py lora/node_types.py lora/packet_handler.py
rm utils/config.py utils/oled_display.py utils/waveshare_monitor.py utils/pisugar_monitor.py

# Clean up build artifacts
rm -rf build/ *.c lora/*.c utils/*.c
```

### Single File Recompilation

When patching a deployed repeater, you can recompile individual files without running the full build:

```bash
# 1. Copy the updated .py file from your Mac
scp lora/packet_handler.py iqright@<pi-ip>:/home/iqright/lora/

# 2. On the Pi: cythonize → compile → clean up
cd /home/iqright && source .venv/bin/activate
cython -3 lora/packet_handler.py
gcc -shared -fPIC -O2 -I/usr/include/python3.13 \
    -o lora/packet_handler.cpython-313-aarch64-linux-gnu.so \
    lora/packet_handler.c
rm lora/packet_handler.py lora/packet_handler.c

# 3. Restart the service
sudo systemctl restart iqright-repeater
```

The `.so` filename pattern is `<module>.cpython-<version>-<arch>.so`. To find the correct pattern on your Pi:

```bash
ls *.so lora/*.so utils/*.so
```

### Known Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `BrokenProcessPool` during compilation | Pi Zero runs out of RAM with parallel builds | `build_cython.py` uses `nthreads=1` (single-threaded) |
| `No module named 'setuptools'` | Python 3.12+ doesn't bundle setuptools in venvs | `pip install setuptools` (setup script does this automatically) |
| `'._foo' is not a valid module name` | macOS resource fork files in the bundle | `find . -name '._*' -delete` (bundle script strips these automatically) |
| `config.repeater.py` creates wrong `.so` path | Dot in filename treated as package separator | Excluded from compilation (in `EXCLUDE_FILES`) |
| `expected bytes, got bytearray` at runtime | Cython enforces type hints strictly | Wrap with `bytes()` before passing to typed functions |

---

## Repeater Node Configuration

Each repeater needs a unique node ID in the range **200-256**:

| Node ID | Location | Description |
|---------|----------|-------------|
| 200 | (first repeater) | Default repeater |
| 201-256 | (available) | Additional repeaters |

The node ID and power HAT selection are stored in `/home/iqright/.env`:

```env
LORA_NODE_TYPE=REPEATER
LORA_NODE_ID=200
LORA_FREQUENCY=915.23
LORA_TX_POWER=23
LORA_TTL=3
LORA_ENABLE_CA=TRUE
POWER_HAT=WAVESHARE
```

The `POWER_HAT` setting controls:
- **`WAVESHARE`** (default): Loads `waveshare_monitor.py`, enables GPIO shutdown listener (GPIO 20/21), uses moved LoRa pins (CS=GPIO17, RST=GPIO16)
- **`PISUGAR`**: Loads `pisugar_monitor.py`, uses standard LoRa pins (CS=GPIO7, RST=GPIO25), requires cron for daily shutdown

To change settings after setup, edit `.env` and restart the service:

```bash
sudo systemctl restart iqright-repeater
```

---

## Daily Operation Schedule

The repeater is configured for autonomous operation. The shutdown and wake-up mechanisms depend on which power HAT is installed.

### Waveshare Power Management HAT (default)

```
┌─────────────────────────────────────────────────────┐
│ Daily Schedule (Waveshare)                          │
├─────────────────────────────────────────────────────┤
│ RTC Wake-up         → HAT powers on the Pi           │
│ ~30 seconds later   → Repeater service auto-starts   │
│ (school hours)      → Forwards LoRa packets          │
│ Scheduled time      → HAT signals GPIO 20 HIGH       │
│                     → Repeater detects, shuts down    │
│ (overnight)         → Pi off / solar charging         │
│ Next day            → RTC wakes Pi again              │
└─────────────────────────────────────────────────────┘
```

**Shutdown**: The HAT drives GPIO 20 HIGH when it's time to shut down. The repeater detects this in its main loop, sends a SHUTDOWN status to the server, and calls `shutdown -h now`. On startup, the repeater sets GPIO 21 HIGH to tell the HAT the Pi is running. No cron job needed.

**Power monitoring**: Every 10 minutes (when LoRa is idle), the repeater reads the HAT's serial output (`/dev/ttyS0`) to check Vin voltage, Vout voltage, RTC state, and time drift. Alerts are sent to the server as STATUS packets.

### PiSugar 3 (alternative)

```
┌─────────────────────────────────────────────────────┐
│ Daily Schedule (PiSugar)                            │
├─────────────────────────────────────────────────────┤
│ 1:00 PM             → PiSugar RTC wakes Pi           │
│ ~30 seconds later   → Repeater service auto-starts   │
│ (school hours)      → Forwards LoRa packets          │
│ 6:00 PM             → Cron job shuts down Pi          │
│ (overnight)         → Pi off / solar charging         │
│ Next day 1:00 PM    → RTC wakes Pi again              │
└─────────────────────────────────────────────────────┘
```

**Shutdown**: A cron job runs `/usr/local/bin/shutdown_repeater.sh` at 6:00 PM daily. The repeater also sends a SHUTDOWN status to the server on `KeyboardInterrupt` / service stop.

**Power monitoring**: Every 10 minutes, the repeater reads PiSugar battery level, voltage, charging state, and temperature via I2C (address 0x57). Alerts are sent to the server as STATUS packets.

**PiSugar RTC schedule**: Run `setup_pisugar_schedule.sh` after setup to configure the daily wake-up alarm (see Step 8 below).

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
| **Shutdown (Waveshare)** | HAT signals GPIO 20 → repeater shuts down gracefully (no cron) |
| **Shutdown (PiSugar)** | Cron job at 6:00 PM → system shutdown (configured during setup) |
| **Wake-up** | Power HAT RTC alarm powers on the Pi |
| **Power monitoring** | Waveshare: Vin/Vout/RTC via serial. PiSugar: battery/voltage/temp via I2C. Every 10 min → STATUS packet to server |

---

## What the Setup Script Creates

| Item | Description |
|------|-------------|
| `/home/iqright/.venv/` | Python virtual environment |
| `/home/iqright/.env` | Node configuration (repeater ID, LoRa settings, power HAT selection) |
| `/home/iqright/utils/config.py` | Active config (copied from `config.repeater.py`, HAT-aware pins) |
| `/home/iqright/log/` | Log directory |
| `/etc/systemd/system/iqright-repeater.service` | Systemd service (auto-start, crash recovery) |
| `/etc/sudoers.d/repeater-shutdown` | Passwordless shutdown for repeater user |
| `/usr/local/bin/shutdown_repeater.sh` | Daily shutdown script (PiSugar only) |
| Cron job (6:00 PM) | Daily shutdown via cron (PiSugar only) |
| I2C enabled | `/dev/i2c-1` available for OLED and PiSugar |
| UART enabled | `/dev/ttyS0` available for Waveshare HAT serial monitoring |

### Python Dependencies (requirements.repeater.txt)

| Package | Purpose |
|---------|---------|
| `python-dotenv` | Load `.env` configuration |
| `adafruit-circuitpython-rfm9x` | LoRa radio hardware driver |
| `adafruit-blinka` | CircuitPython compatibility layer |
| `adafruit-circuitpython-ssd1306` | OLED display driver (optional) |
| `pillow` | OLED graphics rendering (optional) |
| `RPi.GPIO` | Waveshare HAT GPIO communication (shutdown signal, running heartbeat) |
| `smbus` | I2C communication for PiSugar 3 battery monitor |

> `cython`, `setuptools`, `python3-dev`, `gcc`, `minicom`, and `cron` are installed as system packages during setup.

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

# Waveshare HAT serial monitor
sudo minicom -b 115200 -o -D /dev/ttyS0   # View HAT status (Ctrl+A then X to exit)

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

- Verify the Waveshare HAT RTC is configured (check via `sudo minicom -b 115200 -o -D /dev/ttyS0`)
- Check `Rtc_State` in serial output — should be `1` (scheduler enabled)
- Verify power source is connected to the HAT (Vin should be > 4.7V)

### Pi doesn't shut down on schedule

**Waveshare HAT:**
- The HAT drives GPIO 20 HIGH when it's time to shut down
- Verify GPIO 20 is connected: `cat /sys/class/gpio/gpio20/value` (or check in Python)
- Check repeater logs for "HAT signaled shutdown" messages: `grep -i shutdown /home/iqright/log/repeater_*.log`
- Verify the repeater service is running (it contains the shutdown listener)
- Test the HAT serial output: `sudo minicom -b 115200 -o -D /dev/ttyS0`

**PiSugar:**
- Verify the cron job exists: `sudo crontab -u root -l | grep shutdown`
- Verify cron service is running: `sudo systemctl status cron`
- Check shutdown script exists and is executable: `ls -la /usr/local/bin/shutdown_repeater.sh`
- To recreate: `(sudo crontab -u root -l; echo "0 18 * * * /usr/local/bin/shutdown_repeater.sh # IQRight Repeater daily shutdown") | sudo crontab -u root -`

### Waveshare HAT serial not working

- Verify serial port exists: `ls /dev/ttyS0`
- Verify UART is enabled: `grep enable_uart /boot/firmware/config.txt` (should say `enable_uart=1`)
- Verify serial console is disabled: `systemctl status serial-getty@ttyS0` (should be disabled/masked)
- Test manually: `sudo minicom -b 115200 -o -D /dev/ttyS0` (should show voltage/RTC data)

### Cython compilation fails during setup

- The setup script continues with `.py` source files if compilation fails
- Common causes:
  - Missing `setuptools` (Python 3.12+ no longer bundles it in venvs) — the setup script now installs it automatically
  - Insufficient disk space
  - Missing `python3-dev` or `gcc`
- To retry compilation manually:
  ```bash
  cd /home/iqright
  source .venv/bin/activate
  pip install cython setuptools
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
  6. Select power HAT (1=Waveshare, 2=PiSugar) when prompted
  7. Reboot when prompted

On Pi (updates):
  1. Rebuild bundle on Mac
  2. Upload to FTP
  3. sudo ./setup_repeater.sh on Pi

Verify:
  sudo systemctl status iqright-repeater
  tail -f /home/iqright/log/repeater_*.log
  sudo i2cdetect -y 1
  cat /home/iqright/.env                         # Check POWER_HAT setting
  sudo minicom -b 115200 -o -D /dev/ttyS0        # Waveshare only
```