# Battery Monitor Utility

Quick reference for `battery_monitor.py` - INA219 power monitoring utility.

## Quick Usage

```bash
# Text output (default)
python3 battery_monitor.py
# Output: "85% (3.95V, 450mA, 1.8W) Discharging"

# JSON output
python3 battery_monitor.py --format json

# Custom I2C address
python3 battery_monitor.py --addr 0x40
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--format text` | Human-readable output | text |
| `--format json` | JSON output | - |
| `--addr 0x43` | I2C address (hex or decimal) | 0x43 |

## Output Format

### Text Format
```
85% (3.95V, 450mA, 1.8W) Discharging
└─┬─┘ └──┬──┘ └─┬──┘ └─┬──┘ └────┬─────┘
  │      │      │      │         └─ Status
  │      │      │      └─ Power (W)
  │      │      └─ Current (mA, absolute value)
  │      └─ Voltage (V)
  └─ Battery Percentage (0-100)
```

### JSON Format
```json
{
  "voltage": 3.95,
  "current": 450.1,
  "power": 1.78,
  "percent": 85,
  "status": "Discharging",
  "available": true
}
```

## Status Values

| Status | Meaning |
|--------|---------|
| `Charging` | Negative current (battery receiving charge) |
| `Discharging` | Positive current (battery powering load) |
| `Full` | Minimal current (fully charged or idle) |
| `Unavailable` | INA219 not detected |
| `Error` | Communication error |

## Exit Codes

- `0` - Success (battery data available)
- `1` - Error (INA219 not available or error)

## Python API

```python
from battery_monitor import read_battery_status

battery = read_battery_status(i2c_addr=0x43)

if battery['available']:
    print(f"Battery at {battery['percent']}%")
    print(f"Voltage: {battery['voltage']}V")
    print(f"Current: {battery['current']}mA")
    print(f"Power: {battery['power']}W")
    print(f"Status: {battery['status']}")
else:
    print(f"Error: {battery['error']}")
```

## Integration

### Shell Scripts

```bash
# Get battery info
BATTERY=$(python3 battery_monitor.py)
echo "Battery: $BATTERY"

# Check if available
if python3 battery_monitor.py > /dev/null 2>&1; then
    echo "Battery monitoring available"
else
    echo "No battery monitoring"
fi
```

### Systemd Service

```ini
[Service]
ExecStartPre=/usr/bin/python3 /path/to/battery_monitor.py
ExecStart=/path/to/your/script.sh
```

### Cron Job

```bash
# Log battery every hour
0 * * * * python3 /path/to/battery_monitor.py >> /var/log/battery.log 2>&1
```

## Calibration

Battery percentage is calculated based on voltage:

**Default (Li-ion):**
- 3.0V = 0%
- 4.2V = 100%

**To adjust**, edit function in `battery_monitor.py`:

```python
def get_battery_percentage(voltage):
    # For LiFePO4 (2.5V-3.65V)
    percent = (voltage - 2.5) / 1.15 * 100

    # For 12V Lead Acid (10.5V-12.6V)
    percent = (voltage - 10.5) / 2.1 * 100

    return max(0, min(100, int(percent)))
```

## Troubleshooting

### "INA219 module not found"
- Check `specifics/INA219.py` exists
- Verify Python path includes project root

### "Permission denied: /dev/i2c-1"
```bash
sudo usermod -a -G i2c $USER
newgrp i2c
```

### Reading returns 0V
- Check INA219 wiring (VIN+/VIN-)
- Verify battery connected
- Test with: `sudo i2cdetect -y 1`

### Incorrect percentage
- Check battery chemistry matches calibration
- Measure actual voltage with multimeter
- Adjust calibration constants

## Hardware Setup

**Minimum:**
- INA219 module
- I2C connection to Raspberry Pi (GPIO 2/3)
- Battery connected through INA219

**See**: [docs/BATTERY_MONITORING_INA219.md](BATTERY_MONITORING_INA219.md) for complete wiring guide.

## Dependencies

- Python 3.6+
- `smbus` module (I2C communication)
- `specifics/INA219.py` (driver)

Install:
```bash
sudo apt-get install python3-smbus
```

## Related Files

- `battery_monitor.py` - This utility
- `specifics/INA219.py` - INA219 driver module
- `repeater_status.sh` - Uses this utility
- `docs/BATTERY_MONITORING_INA219.md` - Complete documentation

## Version

- **v1.0** (2025-02-14) - Initial release
