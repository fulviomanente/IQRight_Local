#!/usr/bin/env python3
"""
Battery Monitor Utility for IQRight Repeater

Reads battery status from INA219 power monitoring IC and returns
formatted status information.

Usage:
    python3 battery_monitor.py [--format text|json]

Output formats:
    text: Human-readable format (default)
        "85% (3.95V, 450mA, 1.8W)"

    json: JSON format
        {"percent": 85, "voltage": 3.95, "current": 450, "power": 1.8, "status": "Discharging"}
"""

import sys
import json
import argparse
from pathlib import Path

# Add specifics directory to path to import INA219
#SCRIPT_DIR = Path(__file__).parent.parent
#sys.path.insert(0, str(SCRIPT_DIR / "specifics"))
try:
    from INA219 import INA219
    INA219_AVAILABLE = True
except ImportError:
    INA219_AVAILABLE = False


def get_battery_percentage(voltage):
    """
    Calculate battery percentage from voltage.

    Assumes LiPo/Li-ion battery:
    - 3.0V = 0%
    - 4.2V = 100%

    Args:
        voltage: Battery voltage in volts

    Returns:
        Battery percentage (0-100)
    """
    # Linear approximation (simple but effective)
    percent = (voltage - 3.0) / 1.2 * 100

    # Clamp to 0-100 range
    if percent > 100:
        percent = 100
    if percent < 0:
        percent = 0

    return int(percent)


def get_charging_status(current):
    """
    Determine if battery is charging or discharging.

    Args:
        current: Current in mA (positive = discharging, negative = charging)

    Returns:
        Status string: "Charging", "Discharging", or "Full"
    """
    if current < -10:  # Negative current = charging (threshold for noise)
        return "Charging"
    elif current > 10:  # Positive current = discharging
        return "Discharging"
    else:
        return "Full"  # Minimal current = fully charged or idle


def read_battery_status(i2c_addr=0x43):
    """
    Read battery status from INA219.

    Args:
        i2c_addr: I2C address of INA219 (default: 0x43)

    Returns:
        Dictionary with battery information:
        {
            'voltage': float,      # Voltage in V
            'current': float,      # Current in mA
            'power': float,        # Power in W
            'percent': int,        # Battery percentage (0-100)
            'status': str,         # "Charging", "Discharging", or "Full"
            'available': bool      # True if reading successful
        }
    """
    if not INA219_AVAILABLE:
        return {
            'voltage': 0.0,
            'current': 0.0,
            'power': 0.0,
            'percent': 0,
            'status': 'Unavailable',
            'available': False,
            'error': 'INA219 module not found'
        }

    try:
        # Initialize INA219
        ina = INA219(addr=i2c_addr)

        # Read values
        voltage = ina.getBusVoltage_V()
        current = ina.getCurrent_mA()
        power = ina.getPower_W()

        # Calculate percentage
        percent = get_battery_percentage(voltage)

        # Determine charging status
        status = get_charging_status(current)

        return {
            'voltage': round(voltage, 2),
            'current': round(current, 1),
            'power': round(power, 2),
            'percent': percent,
            'status': status,
            'available': True
        }

    except Exception as e:
        return {
            'voltage': 0.0,
            'current': 0.0,
            'power': 0.0,
            'percent': 0,
            'status': 'Error',
            'available': False,
            'error': str(e)
        }


def format_text(battery_info):
    """
    Format battery info as human-readable text.

    Args:
        battery_info: Dictionary from read_battery_status()

    Returns:
        Formatted string
    """
    if not battery_info['available']:
        error_msg = battery_info.get('error', 'Unknown error')
        if 'module not found' in error_msg:
            return "Not Available (INA219 module not installed)"
        else:
            return f"Error: {error_msg}"

    # Format: "85% (3.95V, 450mA, 1.8W) Discharging"
    return (
        f"{battery_info['percent']}% "
        f"({battery_info['voltage']:.2f}V, "
        f"{abs(battery_info['current']):.0f}mA, "
        f"{battery_info['power']:.2f}W) "
        f"{battery_info['status']}"
    )


def format_json(battery_info):
    """
    Format battery info as JSON.

    Args:
        battery_info: Dictionary from read_battery_status()

    Returns:
        JSON string
    """
    return json.dumps(battery_info, indent=2)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Read battery status from INA219 power monitor'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    parser.add_argument(
        '--addr',
        type=lambda x: int(x, 0),  # Accept hex (0x43) or decimal
        default=0x43,
        help='I2C address of INA219 (default: 0x43)'
    )

    args = parser.parse_args()

    # Read battery status
    battery_info = read_battery_status(i2c_addr=args.addr)

    # Format output
    if args.format == 'json':
        print(format_json(battery_info))
    else:
        print(format_text(battery_info))

    # Exit code: 0 = success, 1 = error
    sys.exit(0 if battery_info['available'] else 1)


if __name__ == '__main__':
    main()
