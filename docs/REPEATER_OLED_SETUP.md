
SSD1306 128x64 I2C OLED display for the repeater node, controlled by a physical toggle switch.

---

## Wiring

### OLED Display (I2C)

```
Pi Zero W          OLED SSD1306
─────────          ────────────
3.3V (Pin 1)  ───  VCC
SDA  (Pin 3)  ───  SDA  (GPIO 2)
SCL  (Pin 5)  ───  SCL  (GPIO 3)
GND  (Pin 6)  ───  GND
```

No conflicts with LoRa (SPI) or PiSugar (I2C 0x57).

### Display Switch (GPIO 16)

```
GND (Pin 6)  ────  Switch  ────  GPIO 16 (Pin 36)
```

Standard pull-up configuration — switch closed (to GND) = display ON.

---

## I2C Setup

```bash
# Enable I2C
sudo raspi-config   # Interface Options → I2C → Enable
sudo reboot

# Verify
sudo i2cdetect -y 1
# Should show 3c (OLED) and optionally 57 (PiSugar), 68 (PiSugar RTC)
```

---

## Display Behavior

### Switch OFF (default)

Display is completely off. Zero power draw from OLED.

### Switch ON

Shows 4 info screens in sequence (5 seconds each), then enters the normal stats loop.

| Screen | Content |
|--------|---------|
| **1. Power** | Battery %, voltage, charging status |
| **2. RTC Schedule** | Next wakeup time + current time (sync check) |
| **3. Network** | WiFi connected/disconnected + IP address |
| **4. Service** | Service start time + Node ID + current time |

After the 4 screens, the display enters the normal cycle:

| Event | Display |
|-------|---------|
| **Stats** (every 60s) | RX / FWD / DROP counts + forward rate + battery |
| **Packet forwarded** | Brief flash: `102 → 1` |
| **Startup** | "IQRight Repeater Starting..." (2s), then "Repeater Ready" (2s) |
| **Shutdown** | "HAT Shutdown Signal Received" (2s), then off |
| **Error** | Error message (stays 10-15s) |

### Switch OFF again

Display powers off immediately.

---

## Configuration

The switch pin is defined in `repeater.py`:

```python
OLED_SWITCH_PIN = 16
```

The OLED driver is selected via `.env`:

```env
OLED_DRIVER=SSD1306    # 0.96" display (default)
OLED_DRIVER=SH1106     # 1.3" display (if needed)
```

---

## Power Consumption

| State | Current |
|-------|---------|
| Display ON (50% brightness) | ~10-15 mA |
| Display OFF (switch off) | ~0.5 mA |
| Switch off, no cycling | **0 mA from OLED** |

With the switch off, there is no on/off cycling — the display stays fully off until you flip the switch.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `i2cdetect` shows nothing at 0x3C | Check VCC/GND/SDA/SCL wiring. Try `addr=0x3D` |
| Display garbled / half content | Wrong driver. Try `OLED_DRIVER=SH1106` in `.env` for 1.3" displays |
| Switch has no effect | Verify GPIO 16 wiring: `python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_UP); print(GPIO.input(16))"` — should print 0 when switch closed, 1 when open |
| Display stays on after shutdown | Update `repeater.py` — the `finally` block should call `oled.shutdown()` |
| "OLED libraries not available" | `pip install adafruit-circuitpython-ssd1306 pillow` |
