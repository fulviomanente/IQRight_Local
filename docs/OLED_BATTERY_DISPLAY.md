# OLED Battery Display Integration

Guide for the battery monitoring display on the repeater OLED screen.

## Overview

The repeater OLED now displays real-time battery percentage alongside the packet statistics. This provides at-a-glance visibility into power status without SSH access.

## Display Layout

```
┌──────────────────────────────────────────────────┐
│ Repeater                    85% [████████░░] │  ← Battery icon & %
│────────────────────────────────────────────────  │  ← Separator
│ RX: 1250                                       │  ← Packets received
│ FWD: 1230                              (98%)   │  ← Forwarded (with %)
│ DROP: 20                                       │  ← Dropped packets
└──────────────────────────────────────────────────┘
     128 pixels wide × 64 pixels high (SSD1306)
```

### Display Elements

1. **"Repeater" Label** (top-left)
   - Shows node type
   - Always visible

2. **Battery Icon** (top-right)
   - Rectangle outline representing battery
   - Small tip on right side
   - Filled proportionally to charge level
   - Position: x=98, y=2, size=25×12 pixels

3. **Battery Percentage** (below icon)
   - Shows numeric percentage (e.g., "85%")
   - Centered below battery icon
   - Only shown when battery data available

4. **Separator Line** (horizontal)
   - Divides header from stats
   - Full width

5. **Packet Statistics** (main area)
   - RX: Total received
   - FWD: Total forwarded (with forward rate %)
   - DROP: Total dropped

## Battery Icon Visualization

The battery icon fills based on charge level:

```
100%: [██████████]  Full
 75%: [███████░░░]  Good
 50%: [█████░░░░░]  Medium
 25%: [██░░░░░░░░]  Low
 10%: [█░░░░░░░░░]  Critical
  0%: [░░░░░░░░░░]  Empty
```

## Update Intervals

| Data | Update Frequency |
|------|------------------|
| Battery Reading | Every 60 seconds |
| OLED Display | Every 60 seconds |
| Packet Stats | Real-time accumulation |

**Note**: Battery and OLED update on the same 60-second interval to minimize I2C traffic and save power.

## Implementation Details

### Battery Data Source

The repeater reads battery data from **INA219 power monitor** via `utils/battery_monitor.py`:

```python
from utils.battery_monitor import read_battery_status

# Read battery status
battery_info = read_battery_status()

if battery_info and battery_info.get('available'):
    battery_percent = battery_info.get('percent')  # 0-100
    # Pass to OLED display
    oled.show_repeater_stats(rx, fwd, drop, battery_percent)
```

### OLED Display Method

Updated signature with optional battery parameter:

```python
def show_repeater_stats(self, received: int, forwarded: int,
                       dropped: int, battery_percent: int = None):
```

**Parameters:**
- `received` (int): Total packets received
- `forwarded` (int): Total packets forwarded
- `dropped` (int): Total packets dropped
- `battery_percent` (int, optional): Battery percentage (0-100), None if unavailable

### Backward Compatibility

The battery parameter is **optional**. If not provided or `None`, the display works exactly as before (no battery icon shown). This ensures backward compatibility with existing code.

## Power Consumption

**Impact of battery display:**
- Battery reading: ~1mA @ 3.3V (INA219)
- OLED update: ~5mA for ~100ms (brief spike)
- **Total added power**: <0.1% of system consumption

The battery icon itself does not significantly increase OLED power usage because:
1. Updates only every 60 seconds
2. Display auto-powers off after 30 seconds (default)
3. Minimal additional pixels to draw

## Fallback Behavior

If battery monitoring is unavailable:
- Battery icon not shown
- Display shows stats as normal
- No error displayed to user
- Logged to debug: "Failed to read battery"

**Causes of unavailability:**
- INA219 not connected
- I2C communication failure
- `battery_monitor.py` import failed
- Battery reading returned error

## Testing

### Visual Test (No Hardware)

Run the test script to see simulated display:

```bash
python3 test_oled_battery.py
```

This shows how the display will look with different battery levels.

### Hardware Test

On Raspberry Pi with OLED and INA219 connected:

```bash
# Start repeater
python3 repeater.py

# Watch logs for battery updates
tail -f log/repeater_*.log | grep -i battery
```

**Expected log output:**
```
DEBUG - Battery: 85% (3.95V)
DEBUG - OLED: Stats displayed - RX:1250 FWD:1230 DROP:20 BAT:85%
```

### Manual Battery Update

To force an immediate OLED update with battery (for testing):

```python
from utils.oled_display import get_oled_display
from utils.battery_monitor import read_battery_status

oled = get_oled_display()
battery = read_battery_status()

if battery['available']:
    oled.show_repeater_stats(100, 95, 5, battery['percent'])
```

## Troubleshooting

### Battery Icon Not Showing

**Check:**
1. Is INA219 connected?
   ```bash
   sudo i2cdetect -y 1
   # Should show device at 0x43
   ```

2. Can battery_monitor read data?
   ```bash
   python3 utils/battery_monitor.py
   # Should show: "85% (3.95V, 450mA, 1.8W) Discharging"
   ```

3. Check repeater logs:
   ```bash
   grep -i battery log/repeater_*.log
   # Should see: "Battery: XX%"
   ```

### Battery Shows 0%

- Check battery voltage with multimeter
- Verify INA219 wiring (VIN+/VIN-)
- Check calibration in `battery_monitor.py`

### OLED Display Not Updating

- Check OLED power (should auto-power on when stats update)
- Verify I2C connection (GPIO 2/3)
- Check logs for "Failed to update OLED"
- Test OLED manually: `python3 test_oled_battery.py`

### Wrong Battery Percentage

The percentage is calculated for Li-ion (3.0V-4.2V). If using different battery chemistry:

**Edit `utils/battery_monitor.py`:**
```python
def get_battery_percentage(voltage):
    # For LiFePO4: 2.5V to 3.65V
    percent = (voltage - 2.5) / 1.15 * 100

    return max(0, min(100, int(percent)))
```

## Performance Characteristics

### Display Update Timing

| Event | Time |
|-------|------|
| Battery read | ~50ms |
| OLED draw | ~100ms |
| **Total** | **~150ms** |

This occurs every 60 seconds, so average overhead is negligible.

### Power Breakdown

| Component | Power | Notes |
|-----------|-------|-------|
| INA219 | 1mA continuous | Always on |
| OLED active | ~20mA | Only when displaying |
| OLED off | <1µA | Auto-off after 30s |
| Pi Zero W | ~120mA | Base consumption |

Battery display adds <1% to total power consumption.

## Advanced Customization

### Change Battery Icon Position

Edit `utils/oled_display.py`, line ~280:

```python
# Current position (top-right)
batt_x = 98
batt_y = 2

# Move to top-left
batt_x = 5
batt_y = 2

# Move lower
batt_x = 98
batt_y = 50
```

### Change Update Interval

Edit `repeater.py`, line ~117:

```python
BATTERY_READ_INTERVAL = 60  # Change to desired seconds

# For more frequent updates:
BATTERY_READ_INTERVAL = 30  # Every 30 seconds

# For less frequent:
BATTERY_READ_INTERVAL = 120  # Every 2 minutes
```

**Trade-off**: More frequent updates = slightly higher power consumption.

### Change Battery Icon Size

Edit `utils/oled_display.py`, line ~284:

```python
batt_w = 25  # Width in pixels (default: 25)
batt_h = 12  # Height in pixels (default: 12)

# For larger icon:
batt_w = 35
batt_h = 16
```

**Note**: Adjust `batt_x` position if changing width to keep it on screen.

### Add Battery Voltage to Display

Modify `repeater.py` to pass voltage, then update `oled_display.py`:

```python
# In repeater.py (line ~144)
battery_voltage = battery_info.get('voltage')
oled.show_repeater_stats(rx, fwd, drop, battery_percent, battery_voltage)

# In oled_display.py (in show_repeater_stats)
if battery_percent is not None:
    # ... existing battery icon code ...
    if battery_voltage:
        self.draw.text((batt_x, batt_y + 26), f"{battery_voltage:.1f}V", font=self.font, fill=255)
```

## Example Display States

### Normal Operation (75% battery)
```
┌────────────────────────────────────────────┐
│ Repeater              75% [███████░░░]   │
│──────────────────────────────────────────  │
│ RX: 2500                                 │
│ FWD: 2450                         (98%)  │
│ DROP: 50                                 │
└────────────────────────────────────────────┘
```

### Low Battery Warning (15%)
```
┌────────────────────────────────────────────┐
│ Repeater              15% [█░░░░░░░░░]   │
│──────────────────────────────────────────  │
│ RX: 5000                                 │
│ FWD: 4900                         (98%)  │
│ DROP: 100                                │
└────────────────────────────────────────────┘
```

### No Battery Monitoring
```
┌────────────────────────────────────────────┐
│ Repeater                                 │
│──────────────────────────────────────────  │
│ RX: 1000                                 │
│ FWD: 980                          (98%)  │
│ DROP: 20                                 │
└────────────────────────────────────────────┘
```

## Related Files

| File | Purpose |
|------|---------|
| `utils/oled_display.py:261` | Display method with battery |
| `repeater.py:38` | Battery monitor import |
| `repeater.py:113` | Battery reading variables |
| `repeater.py:139` | Battery reading logic |
| `utils/battery_monitor.py` | INA219 interface |
| `test_oled_battery.py` | Visual test script |

## Related Documentation

- [BATTERY_MONITORING_INA219.md](BATTERY_MONITORING_INA219.md) - Complete INA219 setup
- [OLED_SETUP.md](OLED_SETUP.md) - OLED hardware setup
- [OLED_IMPLEMENTATION_SUMMARY.md](OLED_IMPLEMENTATION_SUMMARY.md) - Implementation details
- [REPEATER_SERVICE_SETUP.md](REPEATER_SERVICE_SETUP.md) - Service configuration

## Version History

- **v1.1** (2025-02-14) - Added battery monitoring display
  - Battery icon in top-right corner
  - Percentage display
  - Automatic updates every 60 seconds
  - Graceful fallback if battery unavailable
- **v1.0** (2025-02-10) - Initial OLED implementation
  - Repeater stats display
  - Auto power-off
  - Packet forwarding notifications
