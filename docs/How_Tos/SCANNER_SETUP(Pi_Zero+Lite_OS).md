# Raspberry Pi Zero W - Scanner Setup (Lite + Minimal X11)

This guide sets up a Raspberry Pi Zero W to run the scanner tkinter app without a full desktop environment. It uses Raspberry Pi OS Lite with only the bare minimum X11 packages needed for tkinter.

## The Image

Use **Raspberry Pi OS Lite (32-bit)** — the 32-bit version is required because Pi Zero W is ARMv6 and the 64-bit image won't boot on it.

In Raspberry Pi Imager:

- OS: **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (32-bit)**
- In the imager settings (gear icon), configure:
  - **Enable SSH** (password or key)
  - **Set username/password**
  - **Configure WiFi** (SSID + password)
  - **Set locale/timezone**

This gives you a headless-ready image with WiFi from first boot.

---

## After First Boot

SSH into the Pi:

```bash
ssh your_username@raspberrypi.local
```

### 1. Update the system

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install minimal X11 + tkinter

```bash
sudo apt install -y xserver-xorg-core xinit python3-tk
```

This is roughly ~80MB. No window manager, no desktop, no file manager — just the bare X server and tkinter bindings.

### 3. Install Python dependencies

```bash
sudo apt install -y python3-pip python3-venv
```

Then set up your venv and install the scanner requirements as you normally would with `./setup.sh`, or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install tksheet pyserial python-dotenv cryptography pandas
```

Install the ftp client

```bash
sudo apt install ftp
```

Download Scanner files to the Pi:


Install requirements
```bash
pip install -r requirements.scanner.txt
```

Plus the LoRa/GPIO libraries per your existing `requirements.scanner.txt`.

### 4. Test manually

With a screen connected to the Pi, from the console (not SSH):

```bash
cd /path/to/IQRight_Local
xinit /usr/bin/env bash -c 'source .venv/bin/activate && python3 scanner_queue.py' -- :0
```

This starts X, runs the scanner app fullscreen, and when the app exits, X exits too. The tkinter UI should appear exactly as it does on the desktop OS.

**If testing from SSH** (screen attached to Pi but typing via SSH):

```bash
export DISPLAY=:0
xinit /usr/bin/env bash -c 'cd /path/to/IQRight_Local && source .venv/bin/activate && python3 scanner_queue.py' -- :0 &
```

### 5. Auto-start on boot

Once confirmed working, set it up to launch automatically on power-on.

#### a. Enable auto-login to console

```bash
sudo raspi-config
```

Navigate to: **System Options** → **Boot / Auto Login** → **Console Autologin**

#### b. Create a startup script

```bash
nano ~/start_scanner.sh
```

Contents:

```bash
#!/bin/bash
cd /path/to/IQRight_Local
source .venv/bin/activate
exec python3 scanner_queue.py
```

Make it executable:

```bash
chmod +x ~/start_scanner.sh
```

#### c. Add xinit to your profile

```bash
nano ~/.bash_profile
```

Add at the bottom:

```bash
# Auto-start scanner UI on the main console (tty1 only, not SSH)
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    xinit ~/start_scanner.sh -- :0 2>/dev/null
fi
```

The `$(tty) = /dev/tty1` check is critical — it ensures the scanner only launches on the physical console login, **not** on SSH sessions. SSH access remains fully available for troubleshooting while the scanner runs on screen.

---

## Optional: Auto-restart on crash

To have the scanner restart automatically if it crashes, change the block in `~/.bash_profile` to:

```bash
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    while true; do
        xinit ~/start_scanner.sh -- :0 2>/dev/null
        echo "Scanner exited, restarting in 3 seconds..."
        sleep 3
    done
fi
```

This loops indefinitely — the scanner only stops if you SSH in and kill the process, or press Ctrl+C on the physical console.

---

## What You End Up With

| Aspect | Behavior |
|--------|----------|
| **Boot** | Auto-login to console → X starts → scanner app fullscreen |
| **SSH** | Works normally, no X involved, full shell access |
| **WiFi** | Stays connected for SSH and troubleshooting |
| **RAM** | ~50-60MB less than full desktop OS |
| **Code changes** | None — existing scanner_queue.py runs as-is |
| **App crash** | X exits, returns to console (or auto-restarts if configured) |

---

## Troubleshooting

### Scanner doesn't start on boot
- Verify auto-login is enabled: `sudo raspi-config` → System Options → Boot / Auto Login → Console Autologin
- Check `~/.bash_profile` has the xinit block
- Check the startup script path is correct and executable: `ls -la ~/start_scanner.sh`

### Black screen after xinit
- The app may be crashing before rendering. Check logs:
  ```bash
  cat /path/to/IQRight_Local/log/IQRight_Scanner.debug
  ```
- Try running the app without xinit first to see errors:
  ```bash
  cd /path/to/IQRight_Local && source .venv/bin/activate && python3 scanner_queue.py
  ```
  (This will fail with "no display" but will show import errors or config issues)

### SSH works but screen is blank
- Make sure you're not accidentally starting X from SSH. The `tty1` check prevents this.
- Verify X is running: `ps aux | grep xinit`
- Check X logs: `cat /var/log/Xorg.0.log`

### WiFi drops after a while
- Add a keep-alive cron job:
  ```bash
  crontab -e
  ```
  Add:
  ```
  */5 * * * * ping -c 1 8.8.8.8 > /dev/null 2>&1 || sudo systemctl restart networking
  ```
