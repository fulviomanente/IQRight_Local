#!/usr/bin/env python3
"""
PiSugar 3 Monitor Utility for IQRight Repeater

Lean implementation using official PiSugar I2C library.
No threads, no continuous monitoring - just read when called.

Usage:
    from utils.pisugar_monitor import read_pisugar_status

    status = read_pisugar_status()
    if status['available']:
        battery_percent = status['battery']
        is_charging = status['charging']
"""

import logging
from typing import Dict, Any, Optional

try:
    import smbus
    SMBUS_AVAILABLE = True
except ImportError:
    SMBUS_AVAILABLE = False
    logging.warning("smbus not available - PiSugar monitoring disabled")

# Pi/agentsSugar I2C addresses
PISUGAR3_ADDRESS = 0x57

# Battery voltage to percentage curve for PiSugar3 (1200mAh)
BATTERY_CURVE_1200_3 = [
    (4.2, 100.0),  # Full charge
    (4.0, 80.0),   # High
    (3.7, 60.0),   # Medium
    (3.5, 20.0),   # Low
    (3.1, 0.0)     # Empty
]


def _check_device(bus, address: int) -> bool:
    """
    Check if PiSugar device exists at address

    Args:
        bus: SMBus instance
        address: I2C address to check

    Returns:
        True if device found
    """
    try:
        bus.read_byte_data(address, 0)
        return True
    except OSError:
        return False


def _read_registers(bus, address: int) -> Optional[list]:
    """
    Read all 256 registers from PiSugar device

    Args:
        bus: SMBus instance
        address: I2C address

    Returns:
        List of 256 register values or None if failed
    """
    try:
        registers = []
        # Read in chunks of 32 bytes (I2C limitation)
        for i in range(0, 256, 32):
            chunk = bus.read_i2c_block_data(address, i, min(32, 256 - i))
            registers.extend(chunk)
        return registers
    except Exception as e:
        logging.error(f"Failed to read PiSugar registers: {e}")
        return None


def _voltage_to_percentage(voltage: float) -> float:
    """
    Convert battery voltage to percentage using PiSugar3 curve

    Args:
        voltage: Battery voltage in volts

    Returns:
        Battery percentage (0-100)
    """
    # Linear interpolation between curve points
    for (v1, p1), (v2, p2) in zip(BATTERY_CURVE_1200_3, BATTERY_CURVE_1200_3[1:]):
        if v2 <= voltage <= v1:
            # Linear interpolation
            return p2 + (p1 - p2) * (voltage - v2) / (v1 - v2)

    # Out of range - clamp to min/max
    if voltage >= BATTERY_CURVE_1200_3[0][0]:
        return BATTERY_CURVE_1200_3[0][1]  # 100%
    else:
        return BATTERY_CURVE_1200_3[-1][1]  # 0%


def read_pisugar_status() -> Dict[str, Any]:
    """
    Read PiSugar3 status via I2C

    Simple one-shot read: connect → read → parse → disconnect
    No threads, no continuous monitoring

    Returns:
        Dictionary with PiSugar status:
        {
            'available': bool,        # True if reading successful
            'battery': float,         # Battery percentage (0-100)
            'voltage': float,         # Battery voltage in volts
            'charging': bool,         # Is power plugged in?
            'temperature': int,       # Temperature in Celsius
            'model': str,            # Device model (PiSugar3)
            'error': str             # Error message if available=False
        }
    """
    status = {
        'available': False,
        'battery': 0.0,
        'voltage': 0.0,
        'charging': False,
        'temperature': 0,
        'model': 'Unknown',
        'error': ''
    }

    if not SMBUS_AVAILABLE:
        status['error'] = 'smbus module not available'
        return status

    bus = None
    try:
        # Initialize I2C bus
        bus = smbus.SMBus(1)

        # Check if PiSugar3 is present
        if not _check_device(bus, PISUGAR3_ADDRESS):
            status['error'] = 'PiSugar3 not found at I2C address 0x57'
            return status

        # Read all registers
        registers = _read_registers(bus, PISUGAR3_ADDRESS)
        if registers is None or len(registers) < 256:
            status['error'] = 'Failed to read PiSugar registers'
            return status

        # Parse battery voltage (registers 0x22-0x23)
        # High byte at 0x22, low byte at 0x23
        high = registers[0x22]
        low = registers[0x23]
        voltage = ((high << 8) + low) / 1000.0  # Convert to volts

        # Parse temperature (register 0x04, offset by -40)
        temperature = registers[0x04] - 40

        # Parse control register 1 (0x02) for power status
        ctr1 = registers[0x02]
        power_plugged = (ctr1 & (1 << 7)) != 0  # Bit 7 = power plugged

        # Calculate battery percentage
        battery_percent = _voltage_to_percentage(voltage)

        # Populate status
        status['available'] = True
        status['battery'] = round(battery_percent, 1)
        status['voltage'] = round(voltage, 2)
        status['charging'] = power_plugged
        status['temperature'] = temperature
        status['model'] = 'PiSugar3'

    except Exception as e:
        status['error'] = str(e)
        logging.error(f"Error reading PiSugar status: {e}")

    finally:
        # Always close bus
        if bus is not None:
            try:
                bus.close()
            except Exception:
                pass

    return status


def format_status_for_lora(status: Dict[str, Any]) -> str:
    """
    Format PiSugar status for LoRa transmission

    Format: "battery|charging|voltage|temperature|model"
    Example: "85.5|true|3.95|25|PiSugar3"

    Args:
        status: Status dictionary from read_pisugar_status()

    Returns:
        Formatted string for LoRa payload
    """
    if not status['available']:
        return "unavailable|false|0.0|0|unknown"

    return (
        f"{status['battery']:.1f}|"
        f"{str(status['charging']).lower()}|"
        f"{status['voltage']:.2f}|"
        f"{status['temperature']}|"
        f"{status['model']}"
    )


def get_battery_percent(status: Dict[str, Any] = None) -> Optional[int]:
    """
    Get battery percentage (for backward compatibility with OLED display)

    Args:
        status: Optional pre-fetched status dict. If None, reads fresh status.

    Returns:
        Battery percentage (0-100) or None if unavailable
    """
    if status is None:
        status = read_pisugar_status()

    if status['available']:
        return int(status['battery'])

    return None


def main():
    """Test utility - print PiSugar status"""
    import sys

    print("="*60)
    print("PiSugar 3 Status Monitor (I2C)")
    print("="*60)

    status = read_pisugar_status()

    if not status['available']:
        print(f"\nERROR: {status['error']}")
        print("\nPossible causes:")
        print("  - PiSugar3 not connected")
        print("  - I2C not enabled (use raspi-config)")
        print("  - smbus module not installed (pip install smbus)")
        print("  - Wrong device (this expects PiSugar3)")
        sys.exit(1)

    print(f"\nModel:            {status['model']}")
    print(f"Battery:          {status['battery']:.1f}%")
    print(f"Voltage:          {status['voltage']:.2f}V")
    print(f"Power Plugged:    {'Yes' if status['charging'] else 'No'}")
    print(f"Temperature:      {status['temperature']}°C")

    print(f"\nLoRa Format:")
    print(format_status_for_lora(status))

    print("="*60)


if __name__ == '__main__':
    main()
