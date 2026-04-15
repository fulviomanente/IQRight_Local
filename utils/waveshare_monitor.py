#!/usr/bin/env python3
"""
Waveshare Power Management HAT Monitor for IQRight Repeater

Reads power status via serial port (/dev/ttyS0 at 115200 baud).
Returns structured status with alerts for RTC, voltage, and timing issues.

Serial output format from the HAT:
    Now_time is Thursday 2 April 12:51:50 2026
    Power_State : 1
    Rtc_State : 1
    Running_State : 1
    Vin_Voltage(V) : 4.99
    Vout_Voltage(V) : 5.22
    Vout_Current(MA) : 226.00

Usage:
    from utils.waveshare_monitor import read_waveshare_status, format_status_for_lora
"""

import logging
import subprocess
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Thresholds
VIN_WARNING_THRESHOLD = 4.7    # Below this: BATTERY_WARNING
VIN_OK_THRESHOLD = 4.9         # Above this: battery OK
VOUT_WARNING_THRESHOLD = 5.0   # Below this: POWER_WARNING
RTC_TIME_DRIFT_MINUTES = 5     # Max allowed drift between HAT RTC and Pi clock


def _parse_serial_output(output: str) -> Optional[Dict[str, Any]]:
    """
    Parse the serial output from the Waveshare HAT.

    Returns:
        Parsed dictionary or None if parsing failed
    """
    result = {}

    # Parse Now_time: "Now_time is Thursday 2 April 12:51:50 2026"
    time_match = re.search(r'Now_time is\s+\w+\s+(\d+\s+\w+\s+[\d:]+\s+\d{4})', output)
    if time_match:
        try:
            result['hat_time_str'] = time_match.group(1)
            result['hat_time'] = datetime.strptime(
                time_match.group(1), '%d %B %H:%M:%S %Y'
            )
        except ValueError:
            result['hat_time'] = None
            result['hat_time_str'] = time_match.group(1)
    else:
        result['hat_time'] = None
        result['hat_time_str'] = ''

    # Parse key-value pairs
    for key, pattern in [
        ('power_state', r'Power_State\s*:\s*(\d+)'),
        ('rtc_state', r'Rtc_State\s*:\s*(\d+)'),
        ('running_state', r'Running_State\s*:\s*(\d+)'),
        ('vin_voltage', r'Vin_Voltage\(V\)\s*:\s*([\d.]+)'),
        ('vout_voltage', r'Vout_Voltage\(V\)\s*:\s*([\d.]+)'),
        ('vout_current', r'Vout_Current\(MA\)\s*:\s*([\d.]+)'),
    ]:
        match = re.search(pattern, output)
        if match:
            val = match.group(1)
            result[key] = float(val) if '.' in val else int(val)
        else:
            result[key] = None

    return result if result.get('vin_voltage') is not None else None


def read_waveshare_status(serial_device: str = '/dev/ttyS0',
                          baud: int = 115200) -> Dict[str, Any]:
    """
    Read Waveshare Power Management HAT status via serial.

    Uses minicom in non-interactive capture mode to read one status block.

    Returns:
        Dictionary with power status and alerts:
        {
            'available': bool,
            'vin_voltage': float,
            'vout_voltage': float,
            'vout_current': float,
            'power_state': int,
            'rtc_state': int,
            'hat_time_str': str,
            'alerts': [str],        # List of alert codes
            'alert_details': [str], # Human-readable alert messages
            'error': str
        }
    """
    status = {
        'available': False,
        'vin_voltage': 0.0,
        'vout_voltage': 0.0,
        'vout_current': 0.0,
        'power_state': 0,
        'rtc_state': 0,
        'hat_time_str': '',
        'alerts': [],
        'alert_details': [],
        'error': ''
    }

    try:
        # Read serial output using minicom in capture mode
        # -b baud, -o skip init, -D device, -C capture file
        # Timeout after 5 seconds — the HAT sends status every ~1 second
        result = subprocess.run(
            ['minicom', '-b', str(baud), '-o', '-D', serial_device],
            capture_output=True, text=True, timeout=5
        )
        raw_output = result.stdout
    except subprocess.TimeoutExpired as e:
        # This is expected — minicom doesn't exit on its own
        raw_output = e.stdout if e.stdout else ''
        if isinstance(raw_output, bytes):
            raw_output = raw_output.decode('utf-8', errors='replace')
    except FileNotFoundError:
        status['error'] = 'minicom not installed'
        return status
    except Exception as e:
        status['error'] = f'Serial read failed: {e}'
        return status

    if not raw_output or 'Vin_Voltage' not in raw_output:
        status['error'] = f'No valid data from {serial_device}'
        return status

    parsed = _parse_serial_output(raw_output)
    if parsed is None:
        status['error'] = 'Failed to parse serial output'
        return status

    # Populate status
    status['available'] = True
    status['vin_voltage'] = parsed.get('vin_voltage', 0.0)
    status['vout_voltage'] = parsed.get('vout_voltage', 0.0)
    status['vout_current'] = parsed.get('vout_current', 0.0)
    status['power_state'] = parsed.get('power_state', 0)
    status['rtc_state'] = parsed.get('rtc_state', 0)
    status['hat_time_str'] = parsed.get('hat_time_str', '')

    # --- Alert evaluation ---

    # a) RTC time drift check
    hat_time = parsed.get('hat_time')
    if hat_time is not None:
        pi_time = datetime.now()
        drift = abs((pi_time - hat_time).total_seconds())
        if drift > RTC_TIME_DRIFT_MINUTES * 60:
            status['alerts'].append('RTC_TIMING_ERROR')
            status['alert_details'].append(
                f"RTC drift {drift/60:.1f}min (HAT={status['hat_time_str']}, Pi={pi_time.strftime('%H:%M:%S')})"
            )
            logging.warning(f"RTC timing error: drift={drift/60:.1f}min")

    # c) RTC scheduler state
    if status['rtc_state'] != 1:
        status['alerts'].append('RTC_ALARM_ERROR')
        status['alert_details'].append(
            f"RTC scheduler disabled (Rtc_State={status['rtc_state']})"
        )
        logging.warning(f"RTC alarm disabled: Rtc_State={status['rtc_state']}")

    # d) Input voltage (battery/power supply)
    vin = status['vin_voltage']
    if vin < VIN_WARNING_THRESHOLD:
        status['alerts'].append('BATTERY_WARNING')
        status['alert_details'].append(f"Vin low: {vin:.2f}V (threshold {VIN_WARNING_THRESHOLD}V)")
        logging.warning(f"Battery warning: Vin={vin:.2f}V")

    # e) Output voltage to Pi
    vout = status['vout_voltage']
    if vout < VOUT_WARNING_THRESHOLD:
        status['alerts'].append('POWER_WARNING')
        status['alert_details'].append(f"Vout low: {vout:.2f}V (threshold {VOUT_WARNING_THRESHOLD}V)")
        logging.warning(f"Power warning: Vout={vout:.2f}V")

    return status


def format_status_for_lora(status: Dict[str, Any], event: str = None) -> str:
    """
    Format Waveshare status for LoRa transmission.

    Format: "vin|vout|current|rtc_state|alerts|model[|event]"
    Examples:
        "4.99|5.22|226.0|OK|OK|Waveshare"
        "4.55|5.01|180.0|OK|BATTERY_WARNING|Waveshare|STARTUP"
        "4.99|4.85|200.0|RTC_ALARM_ERROR|POWER_WARNING|Waveshare"

    Args:
        status: Status dictionary from read_waveshare_status()
        event: Optional event type (STARTUP, SHUTDOWN, or None for periodic)

    Returns:
        Formatted string for LoRa payload
    """
    if not status['available']:
        base = "0.0|0.0|0.0|ERROR|unavailable|Waveshare"
        return f"{base}|{event}" if event else base

    # RTC status string
    rtc_alerts = [a for a in status['alerts'] if a.startswith('RTC_')]
    rtc_str = ','.join(rtc_alerts) if rtc_alerts else 'OK'

    # Power alerts string
    power_alerts = [a for a in status['alerts'] if a in ('BATTERY_WARNING', 'POWER_WARNING')]
    power_str = ','.join(power_alerts) if power_alerts else 'OK'

    base = (
        f"{status['vin_voltage']:.2f}|"
        f"{status['vout_voltage']:.2f}|"
        f"{status['vout_current']:.1f}|"
        f"{rtc_str}|"
        f"{power_str}|"
        f"Waveshare"
    )
    return f"{base}|{event}" if event else base


def main():
    """Test utility - print Waveshare Power Management status"""
    import sys

    print("=" * 60)
    print("Waveshare Power Management HAT Status")
    print("=" * 60)

    status = read_waveshare_status()

    if not status['available']:
        print(f"\nERROR: {status['error']}")
        print("\nPossible causes:")
        print("  - Waveshare HAT not connected")
        print("  - Serial port not available (/dev/ttyS0)")
        print("  - minicom not installed (sudo apt install minicom)")
        sys.exit(1)

    print(f"\nVin Voltage:    {status['vin_voltage']:.2f}V")
    print(f"Vout Voltage:   {status['vout_voltage']:.2f}V")
    print(f"Vout Current:   {status['vout_current']:.1f}mA")
    print(f"Power State:    {status['power_state']}")
    print(f"RTC State:      {status['rtc_state']}")
    print(f"HAT Time:       {status['hat_time_str']}")

    if status['alerts']:
        print(f"\nAlerts:")
        for alert, detail in zip(status['alerts'], status['alert_details']):
            print(f"  {alert}: {detail}")
    else:
        print(f"\nNo alerts - all OK")

    print(f"\nLoRa Format:")
    print(format_status_for_lora(status))

    print("=" * 60)


if __name__ == '__main__':
    main()