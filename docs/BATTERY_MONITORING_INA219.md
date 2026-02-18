# INA219 Battery Monitoring Integration

Complete guide for integrating INA219 power monitoring with the IQRight repeater system.

## Overview

The IQRight repeater now includes real-time battery monitoring using the INA219 precision power monitor IC. This provides accurate voltage, current, and power measurements for battery-powered or solar-powered repeater nodes.

## Hardware Requirements

### INA219 Power Monitor Module

**Specifications:**
- IC: Texas Instruments INA219
- Interface: I2C (address: 0x40-0x4F, configurable)
- Voltage Range: 0-26V (configurable to 16V or 32V)
- Current Range: ±3.2A (with 0.1Ω shunt)
- Accuracy: ±0.5% (typical)
- Resolution: 4mV, 1mA

**Common Modules:**
- Adafruit INA219 Breakout
- Generic INA219 modules (Waveshare, etc.)
- Cost: ~$10 USD

### Battery Setup

**Supported Battery Types:**
- LiPo/Li-ion (3.0V-4.2V) - Recommended
- LiFePO4 (2.5V-3.65V)
- Lead Acid (10.5V-12.6V for 12V systems)

**Typical Repeater Setup:**
- Battery: 18650 Li-ion (3.7V nominal, 2500-3500mAh)
- Solar Panel: 5V 1W (optional)
- Charge Controller: TP4056 or similar
- INA219: Monitors battery side (load voltage/current)

## Wiring

### INA219 to Raspberry Pi

```
INA219          Raspberry Pi
------          ------------
VCC     →       3.3V (Pin 1 or 17)
GND     →       GND (Pin 6, 9, 14, 20, 25, 30, 34, 39)
SDA     →       GPIO 2 (SDA, Pin 3)
SCL     →       GPIO 3 (SCL, Pin 5)
```

### Power Connections

```
Battery (+) → INA219 (VIN+) → Load (+) → Raspberry Pi
Battery (-) → INA219 (VIN-) → Load (-) → Raspberry Pi
```

**Important:**
- INA219 measures on the HIGH side (between battery + and load +)
- Use 0.1Ω shunt resistor (usually built into module)
- Keep wires short to minimize voltage drop

### Complete Repeater Wiring Diagram

```
┌─────────────┐
│  Solar      │
│  Panel 5V   │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  TP4056 Charge  │
│  Controller     │
└────┬────────┬───┘
     │        │
     │        └─► Status LEDs
     │
     ▼
┌─────────────────┐
│  18650 Li-ion   │
│  Battery        │
│  3.7V 3000mAh   │
└────┬────────────┘
     │
     ▼
┌─────────────────┐      ┌──────────────────┐
│  INA219         │◄────►│ Raspberry Pi     │
│  Power Monitor  │ I2C  │ (GPIO 2/3)       │
└────┬────────────┘      └──────────────────┘
     │                            ▲
     └────────────────────────────┘
          (Monitored Load)
```

## Software Installation

### 1. Enable I2C on Raspberry Pi

```bash
# Edit config
sudo raspi-config

# Navigate to:
# 3 Interface Options → I5 I2C → Yes → OK → Finish
# Reboot

# Verify I2C enabled
ls /dev/i2c*
# Should show: /dev/i2c-1
```

### 2. Install I2C Tools

```bash
sudo apt-get update
sudo apt-get install -y i2c-tools python3-smbus
```

### 3. Detect INA219

```bash
# Scan I2C bus
sudo i2cdetect -y 1

# Expected output (INA219 at 0x43):
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 00:          -- -- -- -- -- -- -- -- -- -- -- -- --
# 10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 40: -- -- -- 43 -- -- -- -- -- -- -- -- -- -- -- --
# 50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 70: -- -- -- -- -- -- -- --
```

**Note**: Default address is 0x40, but can be configured to 0x41-0x4F via jumpers.

### 4. Test INA219 Module

```bash
cd ~/IQRight_Local

# Test with the example script
python3 specifics/INA219.py

# Expected output (if connected):
# Load Voltage:  3.850 V
# Current:       0.450 A
# Power:         1.733 W
# Percent:       70.8%
```

### 5. No Additional Installation Needed!

The battery monitoring is already integrated:
- ✅ `utils/battery_monitor.py` - Battery reader script
- ✅ `repeater_status.sh` - Automatically uses INA219
- ✅ `specifics/INA219.py` - Driver module

## Usage

### Command-Line Testing

**Test battery reading:**
```bash
# Text format (human-readable)
python3 utils/battery_monitor.py

# Output: "85% (3.95V, 450mA, 1.8W) Discharging"
```

**JSON format:**
```bash
python3 utils/battery_monitor.py --format json

# Output:
# {
#   "voltage": 3.95,
#   "current": 450.1,
#   "power": 1.78,
#   "percent": 85,
#   "status": "Discharging",
#   "available": true
# }
```

**Custom I2C address:**
```bash
python3 utils/battery_monitor.py --addr 0x40
```

### In Repeater Status Script

The `repeater_status.sh` script automatically detects and uses INA219:

```bash
# View status (includes battery)
./repeater_status.sh

# Continuous monitoring
./repeater_status.sh --watch
```

**Battery Display:**
- 🟢 **Green**: 50%+ charge
- 🟡 **Yellow**: 20-49% charge
- 🔴 **Red**: <20% charge (⚠️ warning icon)
- ⚡ **Charging**: Shows lightning bolt icon

**Fallback behavior:**
- If INA219 not detected → falls back to system battery (`/sys/class/power_supply/`)
- If no battery → shows "AC Power / Not Available"

## Configuration

### Adjusting I2C Address

If your INA219 uses a different address (e.g., 0x40):

**Edit `repeater_status.sh`** (around line 43):
```bash
BATTERY_INFO=$(python3 "$BATTERY_MONITOR" --format text --addr 0x40 2>/dev/null)
```

**Or test directly:**
```bash
python3 utils/battery_monitor.py --addr 0x40
```

### Calibrating Battery Percentage

The default calibration assumes Li-ion battery:
- 3.0V = 0%
- 4.2V = 100%

**To adjust** (for LiFePO4 or other chemistries), edit `utils/battery_monitor.py`:

```python
def get_battery_percentage(voltage):
    # For LiFePO4: 2.5V to 3.65V
    percent = (voltage - 2.5) / 1.15 * 100

    # For 12V Lead Acid: 10.5V to 12.6V
    # percent = (voltage - 10.5) / 2.1 * 100

    if percent > 100:
        percent = 100
    if percent < 0:
        percent = 0

    return int(percent)
```

### Adjusting Shunt Resistor

If using a different shunt resistor value, edit `specifics/INA219.py`:

**Line 94** (default is 0.01Ω):
```python
# RSHUNT = 0.01  # Default
RSHUNT = 0.1     # Change to your shunt value
```

Then recalculate calibration values (see INA219 datasheet).

## Integration with Repeater Service

The systemd service automatically includes battery monitoring in logs:

```bash
# View logs with battery info
sudo journalctl -u iqright-repeater -f | grep -i battery
```

**To add periodic battery logging** to the repeater app, edit `repeater.py`:

```python
# Add at top
from utils.battery_monitor import read_battery_status

# In main loop (around line 125)
if time.time() - last_battery_log > 300:  # Every 5 minutes
    battery = read_battery_status()
    if battery['available']:
        logging.info(f"Battery: {battery['percent']}% "
                     f"({battery['voltage']}V, {battery['current']}mA, "
                     f"{battery['power']}W) {battery['status']}")
    last_battery_log = time.time()
```

## Troubleshooting

### INA219 Not Detected

**Symptom**: `i2cdetect` shows no device at expected address

**Solutions:**
1. Check wiring (SDA/SCL correct?)
2. Verify I2C enabled: `ls /dev/i2c*`
3. Try different address: `sudo i2cdetect -y 1`
4. Check 3.3V power to INA219
5. Test with multimeter: VCC = 3.3V, GND = 0V

### Reading Returns 0V

**Symptom**: Voltage shows 0.00V

**Solutions:**
1. Check VIN+ and VIN- connections
2. Verify battery is connected
3. Check shunt resistor not blown
4. Test with multimeter: measure VIN+ to VIN- directly

### Incorrect Percentage

**Symptom**: Battery shows 0% or 100% when clearly not

**Solutions:**
1. Check battery voltage with multimeter
2. Adjust calibration in `battery_monitor.py`
3. Verify battery chemistry matches calibration (Li-ion vs LiFePO4)
4. Check if battery under load during measurement

### Module Not Found Error

**Symptom**: `INA219 module not found`

**Solutions:**
1. Verify `specifics/INA219.py` exists
2. Check file path in `battery_monitor.py` (line 16)
3. Install smbus: `sudo apt-get install python3-smbus`
4. Check Python path: `python3 -c "import sys; print(sys.path)"`

### Permission Denied (I2C)

**Symptom**: `PermissionError: [Errno 13] Permission denied: '/dev/i2c-1'`

**Solutions:**
```bash
# Add user to i2c group
sudo usermod -a -G i2c $USER

# Logout and login, or:
newgrp i2c

# Verify:
groups | grep i2c
```

## Performance Considerations

### Power Consumption

**INA219 Power Usage:**
- Active: ~1mA @ 3.3V (3.3mW)
- Sleep: Not supported
- Impact: <0.1% of total system power

**Reading Frequency:**
- Status script: Every 5 seconds (in watch mode)
- Negligible impact on battery life

### Accuracy

**Expected Accuracy:**
- Voltage: ±4mV
- Current: ±1mA (with 0.1Ω shunt)
- Power: ±0.5%

**Factors affecting accuracy:**
- Temperature (±0.01%/°C typical)
- Shunt resistor tolerance
- Wire resistance (keep short!)

## Advanced Usage

### Reading from Python Code

```python
from utils.battery_monitor import read_battery_status

# Get battery info
battery = read_battery_status(i2c_addr=0x43)

if battery['available']:
    print(f"Battery: {battery['percent']}%")
    print(f"Voltage: {battery['voltage']}V")
    print(f"Current: {battery['current']}mA")
    print(f"Power: {battery['power']}W")
    print(f"Status: {battery['status']}")

    # Low battery warning
    if battery['percent'] < 20:
        print("WARNING: Low battery!")
else:
    print(f"Error: {battery.get('error', 'Unknown')}")
```

### Logging to File

```bash
# Create battery log
while true; do
    echo "$(date): $(python3 utils/battery_monitor.py)" >> battery.log
    sleep 60  # Every minute
done
```

### OLED Display Integration

To show battery on repeater OLED, edit `utils/oled_display.py`:

```python
from battery_monitor import read_battery_status

def show_battery_status(self):
    """Display battery status on OLED"""
    battery = read_battery_status()
    if battery['available']:
        self.draw.rectangle((0, 0, 128, 64), outline=0, fill=0)
        self.draw.text((0, 0), f"Battery: {battery['percent']}%", fill=255)
        self.draw.text((0, 16), f"{battery['voltage']:.2f}V", fill=255)
        self.draw.text((0, 32), f"{battery['current']:.0f}mA", fill=255)
        self.draw.text((0, 48), battery['status'], fill=255)
        self.oled.image(self.image)
        self.oled.show()
```

### Web API Integration

Expose battery status via simple web API:

```python
from flask import Flask, jsonify
from utils.battery_monitor import read_battery_status

app = Flask(__name__)


@app.route('/api/battery')
def battery_api():
    return jsonify(read_battery_status())


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
```

Access: `http://repeater-ip:5001/api/battery`

## Related Documentation

- [REPEATER_SERVICE_SETUP.md](How_Tos/REPEATER_SERVICE_SETUP.md) - Service setup guide
- [OLED_SETUP.md](OLED_SETUP.md) - OLED display setup
- [CLAUDE.md](../CLAUDE.md) - Project overview

## Reference

### INA219 Resources
- [Datasheet](https://www.ti.com/lit/ds/symlink/ina219.pdf) - Texas Instruments
- [Adafruit Guide](https://learn.adafruit.com/adafruit-ina219-current-sensor-breakout)
- [Waveshare Wiki](https://www.waveshare.com/wiki/INA219)

### Battery Resources
- [Li-ion Voltage Chart](https://batterybro.com/blogs/18650-wholesale-battery-reviews/18650-battery-voltage-chart)
- [LiFePO4 Charging](https://www.power-sonic.com/blog/lifepo4-voltage-chart/)

## Version History

- **v1.0** (2025-02-14) - Initial INA219 integration
  - Battery monitoring utility script
  - Repeater status script integration
  - Automatic fallback handling
  - Color-coded status display
