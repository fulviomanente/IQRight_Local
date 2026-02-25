# IQRight Server Setup Guide

Complete guide for deploying the IQRight server on a Raspberry Pi 4B.

---

## Architecture Overview

The server runs **four services** working together:

```
                    ┌──────────────┐
   Internet ──80──▶ │    Nginx     │
                    │ (reverse     │
                    │  proxy)      │
                    └──────┬───────┘
                           │ :8000
                    ┌──────▼───────┐        ┌──────────────┐
                    │  iqright-web │◀─MQTT──▶│  Mosquitto   │
                    │  (Gunicorn + │        │  (MQTT broker)│
                    │   eventlet)  │        └──────┬───────┘
                    └──────────────┘               │ MQTT
                                            ┌──────▼───────┐
        LoRa Radio ◀──────────────────────▶ │ iqright-lora │
        (scanners)                          │ (CaptureLora) │
                                            └──────────────┘
```

| Service | Description | Port |
|---------|-------------|------|
| `iqright-lora` | LoRa packet receiver + student lookup + MQTT publisher | — (LoRa radio) |
| `iqright-web` | Flask web interface for teachers (Gunicorn + eventlet) | 8000 (local) |
| `nginx` | Reverse proxy, serves static files | 80 (public) |
| `mosquitto` | MQTT message broker | 1883 (local) |

### Installation Paths

| Component | Path |
|-----------|------|
| LoraService | `/etc/iqright/LoraService/` |
| WebApp | `/etc/iqright/WebApp/` |
| LoraService venv | `/etc/iqright/LoraService/.venv/` |
| WebApp venv | `/etc/iqright/WebApp/.venv/` |
| LoraService logs | `/etc/iqright/LoraService/log/` |
| WebApp logs | `/etc/iqright/WebApp/logs/` |
| Data files | `/etc/iqright/LoraService/data/` |
| Credentials | `/etc/iqright/LoraService/data/credentials.iqr` |
| Server .env | `/etc/iqright/LoraService/.env` |
| Nginx config | `/etc/nginx/sites-available/iqright` |
| Mosquitto config | `/etc/mosquitto/mosquitto.conf` |
| Systemd services | `/etc/systemd/system/iqright-lora.service`, `iqright-web.service` |

---

## Prerequisites

### Hardware
- Raspberry Pi 4B (or 3B+)
- RFM9x LoRa module (915 MHz for US) connected via SPI
- SD card with Raspberry Pi OS (Lite or Desktop)
- Network connection (Ethernet or WiFi)

### On Your Development Machine
- Access to the IQRight project repository
- FTP server running (default: `192.168.7.151:5009`)

---

## Step-by-Step Deployment

### Step 1: Build the Server Bundle (on your Mac)

From the project root on your development machine:

```bash
cd ~/Documents/Code/IQRight/Local/IQRight_Local
./utility_tools/setup/build_server_bundle.sh
```

This creates `server_bundle.tar.gz` (~5 MB) in the project root containing:
- `loraservice/` — CaptureLora.py, `lora/` package, `utils/`, `data/` (bundled .iqr/.key files), `credential_setup.py`
- `webapp/` — mqtt_grid_web.py, forms.py, `utils/`, `templates/`, `static/`, `translations/`
- `configs/` — Separate requirements files for each component

### Step 2: Upload the Bundle to FTP

Copy the generated `server_bundle.tar.gz` to the root of your FTP server:

```bash
# Example using scp to the FTP server machine
scp server_bundle.tar.gz fulviomanente@192.168.7.151:~/
```

Or use any FTP client to place it at the FTP server root.

### Step 3: Copy the Setup Script to the Pi

Copy `setup_server.sh` to the Raspberry Pi. You can use SCP, USB drive, or curl:

```bash
# Option A: SCP from your Mac
scp utility_tools/setup/server/setup_server.sh pi@<pi-ip-address>:~/

# Option B: If the Pi has internet access and the file is on a reachable server
# curl -O http://<your-server>/setup_server.sh
```

### Step 4: Run the Setup Script on the Pi

SSH into the Pi and run:

```bash
ssh pi@<pi-ip-address>
chmod +x setup_server.sh
sudo ./setup_server.sh
```

> The script **must** be run with `sudo`. It will use `SUDO_USER` to determine the non-root user for file ownership and service execution.

The script performs **11 automated steps**:

| Step | What It Does |
|------|-------------|
| 1 | Installs system packages: Python 3, pip, venv, gcc, Nginx, Mosquitto, FTP client |
| 2 | Downloads `server_bundle.tar.gz` from the FTP server |
| 3 | Extracts LoraService to `/etc/iqright/LoraService/` and WebApp to `/etc/iqright/WebApp/` |
| 4 | Creates LoraService Python venv and installs dependencies (pandas, paho-mqtt, aiohttp, LoRa drivers, etc.) |
| 5 | Creates WebApp Python venv and installs dependencies (Flask, Flask-SocketIO, Gunicorn, eventlet, etc.) |
| 6 | Creates `.env` with server config (Node ID: 1, frequency 915.23 MHz, TX power 23 dBm) |
| 7 | **Configures credentials** — prompts for API username/password, MQTT credentials, offline API credentials, and encrypts them into `credentials.iqr` |
| 8 | **Downloads data files** — uses the API to download `full_load.iqr` and `offline_users.iqr` (falls back to bundled files if API is unavailable) |
| 9 | Creates and enables two systemd services: `iqright-lora` and `iqright-web` |
| 10 | Configures Nginx as reverse proxy (port 80 → 8000) with WebSocket support |
| 11 | Configures Mosquitto MQTT broker with authentication (replaces main `mosquitto.conf`, backs up original) |

At the end, the script offers to reboot.

### Step 5: Verify Everything Is Running

After reboot (or after manually starting services):

```bash
# Check service status
sudo systemctl status iqright-lora
sudo systemctl status iqright-web
sudo systemctl status nginx
sudo systemctl status mosquitto

# Check logs
journalctl -u iqright-lora --no-pager -n 20
journalctl -u iqright-web --no-pager -n 20

# Test web interface
curl -I http://localhost/
```

Open a browser and navigate to `http://<pi-ip-address>/` — you should see the login page.

---

## Environment Variable Overrides

The setup script accepts optional environment variables to customize the installation:

```bash
# Example: custom FTP server and install paths
sudo FTP_HOST=10.0.0.50 FTP_PORT=21 LORA_DIR=/opt/iqright/lora WEB_DIR=/opt/iqright/web ./setup_server.sh
```

| Variable | Default | Description |
|----------|---------|-------------|
| `FTP_HOST` | `192.168.7.151` | FTP server IP address |
| `FTP_PORT` | `5009` | FTP server port |
| `FTP_USER` | `fulviomanente` | FTP username |
| `FTP_PASS` | `1234` | FTP password |
| `LORA_DIR` | `/etc/iqright/LoraService` | LoraService installation directory |
| `WEB_DIR` | `/etc/iqright/WebApp` | WebApp installation directory |

---

## Service Management

### Starting and Stopping

```bash
# Start all IQRight services
sudo systemctl start iqright-lora iqright-web

# Stop all IQRight services
sudo systemctl stop iqright-lora iqright-web

# Restart a specific service
sudo systemctl restart iqright-lora
sudo systemctl restart iqright-web

# Restart everything (including Nginx and MQTT)
sudo systemctl restart iqright-lora iqright-web nginx mosquitto
```

### Viewing Logs

```bash
# Live logs (journalctl)
journalctl -u iqright-lora -f
journalctl -u iqright-web -f

# Application log files
tail -f /etc/iqright/LoraService/log/IQRight_Daemon.debug
tail -f /etc/iqright/WebApp/logs/IQRight_FE_WEB.debug

# Device status (repeater battery, etc.)
tail -f /etc/iqright/LoraService/log/device_status.log
```

### Checking Health

```bash
# Are services running?
systemctl is-active iqright-lora iqright-web nginx mosquitto

# Web interface responding?
curl -s -o /dev/null -w "%{http_code}" http://localhost/

# MQTT broker accepting connections?
mosquitto_pub -h localhost -u IQRight -P 123456 -t test -m "ping"
```

---

## Updating the Server

To deploy updated code without re-running the full setup:

### Quick Update (Code Only)

```bash
# 1. On your Mac: rebuild the bundle
./utility_tools/setup/build_server_bundle.sh

# 2. Upload to FTP server

# 3. On the Pi: re-run setup (it will overwrite application files)
sudo ./setup_server.sh
```

The setup script is idempotent — it safely overwrites existing files, re-creates venvs, and preserves your `.env` and data files. It will ask before overwriting existing credentials.

### Manual File Update (Single File)

```bash
# Example: update just CaptureLora.py
scp CaptureLora.py pi@<pi-ip-address>:/tmp/
ssh pi@<pi-ip-address>
sudo cp /tmp/CaptureLora.py /etc/iqright/LoraService/
sudo systemctl restart iqright-lora
```

---

## Troubleshooting

### Web interface not loading (port 80)

```bash
# Check Nginx is running and config is valid
sudo nginx -t
sudo systemctl status nginx

# Check Gunicorn is listening on 8000
ss -tlnp | grep 8000

# Check Nginx error log
tail -20 /var/log/nginx/error.log
```

### LoRa service not receiving packets

```bash
# Check service is running
sudo systemctl status iqright-lora

# Check LoRa hardware is detected (SPI)
ls /dev/spidev*

# Check logs for errors
journalctl -u iqright-lora --no-pager -n 50
```

### MQTT messages not reaching web interface

```bash
# Test MQTT broker directly
mosquitto_sub -h localhost -u IQRight -P 123456 -t '#' -v

# In another terminal, publish a test message
mosquitto_pub -h localhost -u IQRight -P 123456 -t 'Class01' -m '{"name":"Test","location":"Test"}'
```

### Mosquitto not starting

```bash
# Check Mosquitto logs
sudo cat /var/log/mosquitto/mosquitto.log

# Test config manually with verbose output
mosquitto -c /etc/mosquitto/mosquitto.conf -v

# Verify password file exists and has correct permissions
ls -la /etc/mosquitto/passwd
# Should be: -rw-r----- mosquitto mosquitto
```

### Data files missing

```bash
# Verify data files exist
ls -la /etc/iqright/LoraService/data/

# Re-download data files manually
cd /etc/iqright/LoraService
sudo -u pi .venv/bin/python3 -c "
from utils.offline_data import OfflineData
offlineData = OfflineData()
offlineData.getOfflineUsers()
print('Done')
"
```

### Credential issues

```bash
# Re-run credential setup
cd /etc/iqright/LoraService
sudo -u pi .venv/bin/python3 credential_setup.py --list \
    --key-path data/credentials.key --credentials-path data/credentials.iqr
```

### Permission issues

```bash
# Fix ownership (replace 'pi' with your username)
sudo chown -R pi:pi /etc/iqright/
```

---

## File Reference

### What the Build Script Packages

```
server_bundle.tar.gz
└── server_bundle/
    ├── loraservice/
    │   ├── CaptureLora.py          # LoRa receiver daemon
    │   ├── credential_setup.py     # Credential encryption utility
    │   ├── lora/                   # Binary packet protocol
    │   │   ├── __init__.py
    │   │   ├── packet_handler.py
    │   │   ├── node_types.py
    │   │   └── collision_avoidance.py
    │   ├── utils/
    │   │   ├── __init__.py
    │   │   ├── config.py           # Server configuration
    │   │   ├── api_client.py       # Secret manager + API client
    │   │   └── offline_data.py     # Encrypted data handler
    │   ├── data/                   # Bundled data files (if available)
    │   │   ├── full_load.iqr       # Encrypted student database
    │   │   ├── offline_users.iqr   # Encrypted offline users
    │   │   ├── offline.key         # Data decryption key
    │   │   └── credentials.key     # Credentials encryption key
    │   └── log/                    # Empty log directory
    │
    ├── webapp/
    │   ├── mqtt_grid_web.py        # Flask web application
    │   ├── forms.py                # Password change form
    │   ├── utils/
    │   │   ├── __init__.py
    │   │   ├── config.py           # Server configuration
    │   │   ├── api_client.py       # Secret manager + API client
    │   │   └── offline_data.py     # Encrypted data handler
    │   ├── templates/              # HTML templates
    │   ├── static/                 # CSS, JS, images, sounds
    │   ├── translations/           # i18n (Spanish, Portuguese)
    │   └── logs/                   # Empty log directory
    │
    └── configs/
        ├── requirements.loraservice.txt
        └── requirements.webapp.txt
```

### What Must Be Copied Manually

| File | Source (your Mac) | Destination (the Pi) |
|------|-------------------|----------------------|
| `setup_server.sh` | `utility_tools/setup/server/setup_server.sh` | `~/setup_server.sh` |
| `server_bundle.tar.gz` | Project root (after build) | FTP server root |

> Data files (`full_load.iqr`, `offline_users.iqr`) are downloaded automatically by the setup script (step 8) via the API. Fallback copies are also included in the bundle. The `offline.key` and `credentials.key` are bundled.

### What the Setup Script Creates Automatically

| Item | Description |
|------|-------------|
| `/etc/iqright/LoraService/.venv/` | Python virtual environment for CaptureLora |
| `/etc/iqright/WebApp/.venv/` | Python virtual environment for web app |
| `/etc/iqright/LoraService/.env` | Server environment configuration |
| `/etc/iqright/WebApp/.env` | Symlink → LoraService/.env |
| `/etc/iqright/LoraService/data/credentials.iqr` | Encrypted service credentials (API, MQTT, offline) |
| `/etc/systemd/system/iqright-lora.service` | Systemd service for CaptureLora |
| `/etc/systemd/system/iqright-web.service` | Systemd service for Gunicorn |
| `/etc/nginx/sites-available/iqright` | Nginx reverse proxy config |
| `/etc/mosquitto/mosquitto.conf` | Mosquitto MQTT config (replaces default, original backed up) |
| `/etc/mosquitto/passwd` | MQTT password file |
