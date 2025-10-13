# OLED Display Setup Guide - Repeater

## Hardware: SSD1306 128x64 I2C OLED Display for Repeater Node

### Pin Connections

**No conflicts with RFM9x LoRa module!** I2C and SPI use separate GPIO pins.

```
┌─────────────────────────────────────────────┐
│         Raspberry Pi Zero W GPIO            │
├─────────────────────────────────────────────┤
│ Pin 1  (3.3V)  → OLED VCC                   │
│ Pin 3  (SDA)   → OLED SDA (GPIO 2)          │
│ Pin 5  (SCL)   → OLED SCL (GPIO 3)          │
│ Pin 6  (GND)   → OLED GND                   │
└─────────────────────────────────────────────┘

RFM9x LoRa uses:
  - SPI: GPIO 9, 10, 11 (MISO, MOSI, SCK)
  - CS: GPIO 7 (CE1)
  - RESET: GPIO 25
```

### Wiring Diagram

```
Pi Zero W                   OLED SSD1306
┌──────────┐               ┌──────────┐
│ 3.3V (1) │───────────────│   VCC    │
│ SDA  (3) │───────────────│   SDA    │
│ SCL  (5) │───────────────│   SCL    │
│ GND  (6) │───────────────│   GND    │
└──────────┘               └──────────┘
```

---

## Software Installation

### 1. Enable I2C on Raspberry Pi

```bash
# Enable I2C interface
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable

# Reboot
sudo reboot
```

### 2. Install Required Libraries

```bash
# Activate virtual environment
source .venv/bin/activate

# Install I2C tools
sudo apt-get update
sudo apt-get install -y python3-dev python3-pip i2c-tools

# Install Python libraries
pip3 install adafruit-circuitpython-ssd1306
pip3 install pillow
```

### 3. Verify I2C Connection

```bash
# Check if I2C is enabled
ls /dev/i2c-*
# Should show: /dev/i2c-1

# Scan for I2C devices (with OLED connected)
sudo i2cdetect -y 1
```

**Expected output:**
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- 3c -- -- --   ← OLED detected at 0x3C
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

**Note:** Some OLEDs use address `0x3D` instead of `0x3C`. The code automatically tries both.

---

## Configuration

### Display Settings

Edit `utils/oled_display.py` to customize:

```python
# Auto-off timeout (seconds)
oled = get_oled_display(auto_off_seconds=30)  # Default: 30s

# Display brightness (0-255)
self.display.contrast(128)  # Default: 128 (50% brightness)
```

### What's Displayed

**Startup Screen (2 seconds):**
```
  IQRight Scanner
    Starting...
   Node: 200
```

**Ready Screen (30s, then auto-off):**
```
  Repeater Ready
   Node ID: 200
   Listening...
```

**Forwarding Notification (brief):**
```
   Forwarding
    102 → 1
```

**Stats Screen (updates every 60s):**
```
  Repeater Stats
  ──────────────
  RX: 42
  FWD: 38 (90%)
  DROP: 4
```

**Error Screen (stays on for 10-15s):**
```
     ERROR!
  ─────────────
  Invalid Node ID:
  150
```

---

## Battery Optimization Features

### 1. Auto Power-Off
- Display automatically turns off after **30 seconds** of inactivity
- Saves significant battery power
- Only wakes for:
  - Scan results
  - Errors
  - Critical events

### 2. Low Brightness
- Default brightness: **50%** (128/255)
- Reduces power consumption by ~40% vs full brightness
- Still readable indoors and outdoors

### 3. Minimal Updates
- No continuous refresh (unlike logs)
- Updates only on events:
  - Startup
  - Ready
  - Scan completed
  - Errors
- Reduces I2C bus traffic

### 4. Simple Graphics
- Monochrome display (1-bit per pixel)
- Text-only interface (no images)
- Small font to reduce pixels lit

### Estimated Power Consumption

| Mode | Current Draw | Notes |
|------|--------------|-------|
| Display ON (50% brightness) | ~10-15 mA | Brief periods only |
| Display OFF | ~0.5 mA | Most of the time |
| **Average (30s auto-off)** | **~2-3 mA** | Excellent for battery |

**Comparison:**
- Pi Zero W idle: ~120 mA
- RFM9x LoRa RX: ~15 mA
- RFM9x LoRa TX: ~120 mA (brief)
- **OLED impact: <3% of total power**

---

## Testing

### Test in LOCAL Mode (Mac/Linux)

```bash
# Set LOCAL mode
export LOCAL=TRUE

# Run scanner
python3 scanner_queue.py
```

**Expected:** OLED functions disabled, no errors.

### Test on Hardware

```bash
# Run repeater on Pi Zero
LORA_NODE_ID=200 python3 repeater.py
```

**Check logs:**
```bash
tail -f log/repeater_200.log | grep OLED
```

**Expected output:**
```
2025-10-13 12:00:00,000 - INFO - OLED display initialized: 128x64
2025-10-13 12:00:00,050 - INFO - OLED: Startup screen displayed
2025-10-13 12:00:02,000 - INFO - OLED: Repeater ready screen displayed
2025-10-13 12:00:32,000 - DEBUG - OLED powered off (battery save)
2025-10-13 12:01:00,000 - DEBUG - OLED: Stats displayed - RX:5 FWD:4 DROP:1
```

### Manual Test Script

```python
#!/usr/bin/env python3
"""Test OLED display for repeater"""
from utils.oled_display import get_oled_display
import time

oled = get_oled_display(auto_off_seconds=10)

# Test startup
oled.show_startup()
time.sleep(2)

# Test ready (repeater mode)
oled.show_ready(200, device_type="Repeater")
time.sleep(3)

# Test forwarding
oled.show_packet_forwarded(102, 1)
time.sleep(2)

# Test stats
oled.show_repeater_stats(received=42, forwarded=38, dropped=4)
time.sleep(5)

# Test error
oled.show_error("Node ID invalid")
time.sleep(5)

# Test auto-off (wait 10 seconds)
print("Waiting for auto-off...")
time.sleep(12)
print("Display should be off now")

# Shutdown
oled.shutdown()
```

---

## Troubleshooting

### Problem: `ls /dev/i2c-*` shows nothing

**Solution:**
1. Enable I2C: `sudo raspi-config` → Interface Options → I2C → Enable
2. Reboot: `sudo reboot`
3. Check again: `ls /dev/i2c-*`

### Problem: `i2cdetect` shows no device

**Check:**
1. Wiring connections (VCC, GND, SDA, SCL)
2. OLED power LED (should be lit)
3. Try different I2C address: Edit `oled_display.py`, line 67:
   ```python
   self.display = SSD1306_I2C(width, height, i2c, addr=0x3D)  # Try 0x3D instead of 0x3C
   ```

### Problem: `ImportError: No module named 'adafruit_ssd1306'`

**Solution:**
```bash
source .venv/bin/activate
pip3 install adafruit-circuitpython-ssd1306
pip3 install pillow
```

### Problem: Display shows garbled text

**Solution:**
1. Check I2C bus speed (default 100kHz works best)
2. Add shorter/better quality I2C wires (<15cm)
3. Add 4.7kΩ pull-up resistors on SDA/SCL if using long wires

### Problem: Display flickers or freezes

**Check:**
1. Power supply voltage (must be stable 3.3V)
2. Ground connection quality
3. Reduce display updates (already optimized in code)

### Problem: Display drains battery too fast

**Adjust:**
1. Reduce auto-off timeout:
   ```python
   oled = get_oled_display(auto_off_seconds=15)  # 15s instead of 30s
   ```
2. Lower brightness:
   ```python
   self.display.contrast(64)  # 25% brightness instead of 50%
   ```

---

## Production Deployment Checklist

- [ ] I2C enabled on Pi Zero (`sudo raspi-config`)
- [ ] OLED wired correctly (VCC, GND, SDA, SCL)
- [ ] I2C device detected (`sudo i2cdetect -y 1` shows `3c` or `3d`)
- [ ] Libraries installed (`adafruit-circuitpython-ssd1306`, `pillow`)
- [ ] Repeater starts without errors (`LORA_NODE_ID=200 python3 repeater.py`)
- [ ] OLED shows startup message
- [ ] OLED shows "Repeater Ready" screen
- [ ] OLED turns off after 30 seconds (battery save)
- [ ] OLED wakes when forwarding packets
- [ ] OLED shows stats every 60 seconds
- [ ] OLED shows errors for invalid node ID or fatal errors

---

## Repeater Deployment

The repeater is designed to be **headless** (no HDMI display needed):

- **OLED I2C**: Only display (minimal power consumption)
- **Battery/Solar powered**: Optimized for long runtime
- **Remote deployment**: Can be placed anywhere in LoRa range

**Running repeater:**

```bash
# Set node ID (200-256) and start
LORA_NODE_ID=200 python3 repeater.py

# Run as systemd service (autostart on boot)
sudo systemctl enable repeater@200
sudo systemctl start repeater@200
```

**OLED provides visual confirmation:**
- Repeater is running
- Packets being forwarded
- Stats (RX/FWD/DROP)
- Errors if any

---

## Additional Features (Optional)

### Add QR Code on OLED

```python
# Requires: pip3 install qrcode
from PIL import Image
import qrcode

def show_qr_code(self, data: str):
    """Display QR code on OLED"""
    qr = qrcode.QRCode(version=1, box_size=2, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="white", back_color="black")
    qr_img = qr_img.resize((64, 64))  # Fit half the display
    self.image.paste(qr_img, (32, 0))
    self._update()
```

### Add Battery Level Indicator

```python
def show_battery_level(self, percent: int):
    """Show battery level on OLED"""
    # Draw battery icon
    self.draw.rectangle((100, 2, 125, 10), outline=255, fill=0)
    self.draw.rectangle((125, 4, 127, 8), outline=255, fill=255)
    # Draw fill based on percent
    fill_width = int(23 * percent / 100)
    self.draw.rectangle((101, 3, 101 + fill_width, 9), fill=255)
    self._update()
```

---

## Summary

✅ **Pin-compatible** with existing RFM9x LoRa module
✅ **Battery-optimized** with auto-off and low brightness
✅ **Minimal updates** - only shows critical info
✅ **Easy to install** - standard I2C interface
✅ **Production-ready** - tested and documented

**Average power consumption: <3 mA** (negligible impact on battery life)
