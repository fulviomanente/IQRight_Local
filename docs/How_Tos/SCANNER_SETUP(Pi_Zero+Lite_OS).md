# IQRight Scanner Setup Guide

Complete guide for deploying the IQRight scanner on a Raspberry Pi Zero W.

---

## Architecture Overview

The scanner runs a **single application** on a Pi Zero W with Lite OS and minimal X11:

```
    ┌──────────────────┐
    │  Pi Zero W       │
    │                  │
    │  scanner_queue   │◀──── QR Scanner (serial, GPIO 21)
    │  (Tkinter GUI)   │
    │                  │◀───▶ RFM9x LoRa Radio (SPI)
    │                  │      ├─ Direct to Server
    │                  │      └─ Via Repeater(s)
    └──────────────────┘
```

| Component | Description |
|-----------|-------------|
| `scanner_queue.py` | Main application — QR scanning, LoRa communication, Tkinter GUI |
| `run_scanner.py` | Launcher script (imports `scanner_queue`) |
| `lora/` | Binary packet protocol package |
| `utils/config.py` | Scanner configuration |

### Installation Paths

| Component | Path |
|-----------|------|
| Application | `/home/iqright/` |
| Virtual environment | `/home/iqright/.venv/` |
| Configuration | `/home/iqright/.env` |
| Active config | `/home/iqright/utils/config.py` |
| Logs | `/home/iqright/log/` |
| Startup script | `~/start_scanner.sh` |

---

## Prerequisites

### Hardware
- Raspberry Pi Zero W
- RFM9x LoRa module (915 MHz for US) connected via SPI
- QR code scanner (serial, GPIO 21 trigger)
- Touchscreen display (vertical orientation)
- SD card with Raspberry Pi OS Lite (32-bit)

> **Important**: Use the **32-bit** Lite image — Pi Zero W is ARMv6 and the 64-bit image won't boot on it.

### On Your Development Machine
- Access to the IQRight project repository
- FTP server running (default: `192.168.7.151:5009`)

---

## The Image

Use **Raspberry Pi OS Lite (32-bit)** from Raspberry Pi Imager:

- OS: **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (32-bit)**
- In the imager settings (gear icon), configure:
  - **Enable SSH** (password or key)
  - **Set username/password**
  - **Configure WiFi** (SSID + password)
  - **Set locale/timezone**

This gives you a headless-ready image with WiFi from first boot.

---

## Step-by-Step Deployment

### Step 1: Build the Scanner Bundle (on your Mac)

From the project root on your development machine:

```bash
cd ~/Documents/Code/IQRight/Local/IQRight_Local
./utility_tools/setup/build_scanner_bundle.sh
```

This creates `scanner_bundle.tar.gz` (~24 KB) in the project root containing:
- `scanner_queue.py` — Main application
- `run_scanner.py` — Launcher script
- `build_cython.py` — Cython compilation script
- `setup_scanner.sh` — Pi setup script (also included in bundle)
- `lora/` — Binary packet protocol package
- `utils/` — Config template (`config.scanner.py`) and `__init__.py`
- `configs/` — `requirements.scanner.txt`
- `log/` — Empty log directory

### Step 2: Upload the Bundle to FTP

Copy the generated `scanner_bundle.tar.gz` to the root of your FTP server:

```bash
# Example using scp to the FTP server machine
scp scanner_bundle.tar.gz fulviomanente@192.168.7.151:~/
```

Or use any FTP client to place it at the FTP server root.

### Step 3: Copy the Setup Script to the Pi

SSH into the Pi after first boot:

```bash
ssh your_username@raspberrypi.local
```

Update the system first:

```bash
sudo apt update && sudo apt upgrade -y
```

Then copy `setup_scanner.sh` to the Pi:

```bash
# Option A: SCP from your Mac
scp utility_tools/setup/scanner/setup_scanner.sh your_username@<pi-ip>:~/

# Option B: The script is also included inside the bundle
```

### Step 4: Run the Setup Script on the Pi

```bash
chmod +x setup_scanner.sh
./setup_scanner.sh
```

The script performs **10 automated steps**:

| Step | What It Does |
|------|-------------|
| 1 | Installs system packages: X11, xinit, tkinter, Python 3, pip, venv, FTP client, fbi |
| 2 | Downloads `scanner_bundle.tar.gz` from the FTP server |
| 3 | Extracts bundle to `/home/iqright/`, copies `config.scanner.py` → `config.py` |
| 4 | Creates Python venv (`.venv/`), installs dependencies from `requirements.scanner.txt` |
| 5 | **Compiles with Cython** — installs Cython + gcc, compiles `.py` → `.so`, removes source files (10-30 min on Pi Zero) |
| 6 | **Configures scanner node ID** — prompts for ID (100-199), creates `.env` |
| 7 | Configures console auto-login, X11 permissions, display rotation (90° CCW), touchscreen calibration, passwordless shutdown |
| 8 | Creates `~/start_scanner.sh` startup script |
| 9 | Configures auto-start in `~/.bash_profile` (tty1 only, with crash recovery loop) |
| 10 | Configures silent boot + IQRight splash screen via systemd + fbi |

At the end, the script offers to reboot.

### Step 5: Verify Everything Works

After reboot, the scanner should auto-start on the display. SSH remains available:

```bash
ssh your_username@<pi-ip>

# Check the scanner process is running
ps aux | grep scanner

# Check logs
tail -f /home/iqright/log/IQRight_Scanner.debug
```

The scanner GUI should show:
1. "Connecting to server..." status during HELLO handshake
2. Once connected: scanner name and status in the top bar
3. Spreadsheet area ready for scanned students
4. Buttons at bottom: Break | Release | Undo | Reset | Quit

---

## Environment Variable Overrides

The setup script accepts optional environment variables to customize the installation:

```bash
# Example: custom FTP server and install directory
FTP_HOST=10.0.0.50 FTP_PORT=21 INSTALL_DIR=/opt/scanner ./setup_scanner.sh
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
- `scanner_queue.py` → `scanner_queue.*.so`
- `lora/packet_handler.py` → `packet_handler.*.so`
- `lora/node_types.py` → `node_types.*.so`
- `lora/collision_avoidance.py` → `collision_avoidance.*.so`
- `utils/config.py` → `config.*.so`

### What Stays as `.py`
- `__init__.py` files (required for Python package imports)
- `run_scanner.py` (launcher — imports `scanner_queue`)
- `build_cython.py` (the build script itself)

### After Compilation
- All `.py` source files are deleted (except the exclusions above)
- All `.c` intermediate files are deleted
- The `build/` directory is removed
- Only `.so` compiled files remain

### If Compilation Fails
The setup script falls back gracefully — it keeps the `.py` source files and the scanner runs normally from Python source. A warning is printed but setup continues.

---

## Scanner Node Configuration

Each scanner needs a unique node ID in the range **100-199**:

| Node ID | Location | Description |
|---------|----------|-------------|
| 102 | Gym Side | Default scanner |
| 103 | East Side | Default scanner |
| 104-199 | (available) | Additional scanners |

The node ID is stored in `/home/iqright/.env`:

```env
LORA_NODE_TYPE=SCANNER
LORA_NODE_ID=102
LORA_FREQUENCY=915.23
LORA_TX_POWER=23
LORA_TTL=3
LORA_ENABLE_CA=TRUE
```

To change the node ID after setup, edit `.env` and reboot.

---

## Updating the Scanner

### Full Update (Rebuild + Redeploy)

```bash
# 1. On your Mac: rebuild the bundle
./utility_tools/setup/build_scanner_bundle.sh

# 2. Upload to FTP server

# 3. On the Pi: re-run setup (it will overwrite application files)
./setup_scanner.sh
```

The setup script is idempotent — it safely overwrites existing files, re-creates the venv, and preserves your `.env`. It will re-compile with Cython.

### Manual File Update (Single File)

```bash
# Example: update just scanner_queue.py (bypasses Cython)
scp scanner_queue.py your_username@<pi-ip>:/home/iqright/
ssh your_username@<pi-ip>
sudo reboot
```

> Note: Manually copied `.py` files won't be Cython-compiled. For production, always use the full bundle + setup workflow.

---

## What You End Up With

| Aspect | Behavior |
|--------|----------|
| **Boot** | Auto-login to console → splash screen → X starts → scanner app fullscreen |
| **SSH** | Works normally, no X involved, full shell access |
| **WiFi** | Stays connected for SSH and troubleshooting |
| **RAM** | ~50-60 MB less than full desktop OS |
| **App crash** | Auto-restarts after 3 seconds (crash recovery loop) |
| **Source code** | Compiled to native `.so` — no readable Python on device |
| **Display** | Rotated 90° CCW for vertical touchscreen orientation |
| **Shutdown** | Quit button powers off the Pi (passwordless sudo) |

---

## Troubleshooting

### Scanner doesn't start on boot
- Verify auto-login is enabled: `sudo raspi-config` → System Options → Boot / Auto Login → Console Autologin
- Check `~/.bash_profile` has the `# IQRight Scanner Auto-Start` block
- Check the startup script exists and is executable: `ls -la ~/start_scanner.sh`
- Check X server permissions: `cat /etc/X11/Xwrapper.config` (should say `allowed_users=anybody`)

### HELLO handshake fails (red status bar)
- Verify the server (`CaptureLora.py`) is running
- Verify node IDs are unique across all devices
- Move the scanner closer to the server or a repeater
- Click the **Reset** button to retry the handshake
- Check logs: `tail -f /home/iqright/log/IQRight_Scanner.debug`

### Black screen after boot
- The app may be crashing before rendering. Check logs:
  ```bash
  cat /home/iqright/log/IQRight_Scanner.debug
  ```
- Try running manually to see errors:
  ```bash
  cd /home/iqright
  source .venv/bin/activate
  xinit ~/start_scanner.sh -- :0
  ```

### SSH works but screen is blank
- Verify X is running: `ps aux | grep xinit`
- Check X logs: `cat /var/log/Xorg.0.log`
- The `tty1` check in `~/.bash_profile` ensures the scanner only starts on the physical console, not SSH

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

### LoRa packets not received
- Check frequency match across all nodes (default: 915.23 MHz)
- Check TX power setting in `.env` (default: 23 dBm)
- Verify RFM9x hardware is detected (SPI): `ls /dev/spidev*`
- Check CRC errors in scanner logs

### WiFi drops after a while
- Add a keep-alive cron job:
  ```bash
  crontab -e
  ```
  Add:
  ```
  */5 * * * * ping -c 1 8.8.8.8 > /dev/null 2>&1 || sudo systemctl restart networking
  ```

### Testing from SSH (screen attached to Pi)
```bash
export DISPLAY=:0
cd /home/iqright
source .venv/bin/activate
xinit ~/start_scanner.sh -- :0 &
```

---

## File Reference

### What the Build Script Packages

```
scanner_bundle.tar.gz
└── scanner_bundle/
    ├── scanner_queue.py              # Main application
    ├── run_scanner.py                # Launcher (imports scanner_queue)
    ├── build_cython.py               # Cython build script
    ├── setup_scanner.sh              # Pi setup script
    ├── lora/                         # Binary packet protocol
    │   ├── __init__.py
    │   ├── packet_handler.py
    │   ├── node_types.py
    │   └── collision_avoidance.py
    ├── utils/
    │   ├── __init__.py
    │   └── config.scanner.py         # Config template (→ config.py)
    ├── configs/
    │   └── requirements.scanner.txt  # Python dependencies
    └── log/                          # Empty log directory
```

### What Must Be Copied Manually

| File | Source (your Mac) | Destination |
|------|-------------------|-------------|
| `setup_scanner.sh` | `utility_tools/setup/scanner/setup_scanner.sh` | `~/setup_scanner.sh` on the Pi |
| `scanner_bundle.tar.gz` | Project root (after build) | FTP server root |

### What the Setup Script Creates Automatically

| Item | Description |
|------|-------------|
| `/home/iqright/.venv/` | Python virtual environment |
| `/home/iqright/.env` | Node configuration (scanner ID, LoRa settings) |
| `/home/iqright/utils/config.py` | Active config (copied from `config.scanner.py`) |
| `/home/iqright/log/` | Log directory |
| `~/start_scanner.sh` | Startup script (loads .env, activates venv, runs scanner) |
| `~/.bash_profile` | Auto-start block (tty1 only, crash recovery) |
| `/etc/X11/Xwrapper.config` | X server permissions |
| `/etc/X11/xorg.conf.d/10-monitor.conf` | Display rotation (90° CCW) |
| `/etc/X11/xorg.conf.d/40-libinput.conf` | Touchscreen calibration matrix |
| `/etc/sudoers.d/scanner-shutdown` | Passwordless shutdown for Quit button |
| `/opt/splash.png` | Boot splash image |
| `/etc/systemd/system/splash.service` | Boot splash systemd service |

### Python Dependencies (requirements.scanner.txt)

| Package | Purpose |
|---------|---------|
| `python-dotenv` | Load `.env` configuration |
| `pandas` | Teacher name mapping |
| `cryptography` | Encrypted file decryption |
| `tksheet` | Spreadsheet widget for Tkinter GUI |
| `adafruit-circuitpython-rfm9x` | LoRa radio hardware driver |
| `adafruit-blinka` | CircuitPython compatibility layer |
| `pyserial` | QR scanner serial communication |
| `RPi.GPIO` | GPIO pin control (QR trigger) |

> `tkinter` is installed as a system package (`python3-tk` via apt), not via pip.
> `cython`, `python3-dev`, and `gcc` are installed during setup for compilation only.
