#!/usr/bin/env python3
"""
Test script for OLED battery display integration

Simulates the repeater OLED display with battery monitoring.
Useful for testing layout without actual hardware.
"""

import os
os.environ['LOCAL'] = 'TRUE'  # Force local mode (no hardware)

import time
from utils.oled_display import OLEDDisplay


def test_battery_display():
    """Test OLED display with different battery levels"""

    print("=" * 60)
    print("OLED Battery Display Test")
    print("=" * 60)
    print("\nThis test simulates OLED display with battery monitoring.")
    print("Since hardware is not available, we'll show what would be displayed.\n")

    # Create OLED instance (will be in simulation mode)
    oled = OLEDDisplay(auto_off_seconds=0)  # Disable auto-off for testing

    test_cases = [
        {
            'name': 'Full Battery',
            'rx': 1250,
            'fwd': 1230,
            'drop': 20,
            'battery': 95
        },
        {
            'name': 'Good Battery',
            'rx': 2500,
            'fwd': 2450,
            'drop': 50,
            'battery': 75
        },
        {
            'name': 'Medium Battery',
            'rx': 3750,
            'fwd': 3680,
            'drop': 70,
            'battery': 45
        },
        {
            'name': 'Low Battery',
            'rx': 5000,
            'fwd': 4900,
            'drop': 100,
            'battery': 20
        },
        {
            'name': 'Critical Battery',
            'rx': 6250,
            'fwd': 6100,
            'drop': 150,
            'battery': 8
        },
        {
            'name': 'No Battery Info',
            'rx': 7500,
            'fwd': 7350,
            'drop': 150,
            'battery': None
        }
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"Test Case {i}: {test['name']}")
        print(f"{'='*60}")
        print(f"  Packets RX:  {test['rx']}")
        print(f"  Packets FWD: {test['fwd']}")
        print(f"  Packets DROP: {test['drop']}")
        if test['battery'] is not None:
            print(f"  Battery:     {test['battery']}%")
        else:
            print(f"  Battery:     Not Available")

        # Calculate forward rate
        if test['rx'] > 0:
            rate = int(test['fwd'] / test['rx'] * 100)
            print(f"  Forward Rate: {rate}%")

        # Simulate display update
        print("\n  OLED Display Layout:")
        print("  ┌────────────────────────────────────────┐")

        # Top line with battery
        if test['battery'] is not None:
            # Simulate battery icon
            batt_fill = int(test['battery'] / 10)  # 0-10 chars
            battery_icon = f"[{'█' * batt_fill}{'░' * (10 - batt_fill)}]"
            print(f"  │ Repeater            {test['battery']:>2}% {battery_icon} │")
        else:
            print(f"  │ Repeater                               │")

        print("  │────────────────────────────────────────│")
        print(f"  │ RX: {test['rx']:<34} │")
        print(f"  │ FWD: {test['fwd']:<24} ({rate}%)   │")
        print(f"  │ DROP: {test['drop']:<33} │")
        print("  └────────────────────────────────────────┘")

        # Simulate actual OLED layout (simplified - just percentage text)
        print("\n  Actual OLED Display (128×64 pixels):")
        print("  ┌────────────────────────────────────────┐")

        # Top line with battery percentage
        if test['battery'] is not None:
            print(f"  │ Repeater              ({test['battery']:>2}%)       │")
        else:
            print(f"  │ Repeater                           │")

        print("  │────────────────────────────────────────│")
        print(f"  │ RX: {test['rx']:<34} │")
        print(f"  │ FWD: {test['fwd']:<24} ({rate}%)   │")
        print(f"  │ DROP: {test['drop']:<33} │")
        print("  └────────────────────────────────────────┘")

        # Show what OLED method would be called
        if test['battery'] is not None:
            print(f"\n  Method call: oled.show_repeater_stats({test['rx']}, {test['fwd']}, {test['drop']}, {test['battery']})")
        else:
            print(f"\n  Method call: oled.show_repeater_stats({test['rx']}, {test['fwd']}, {test['drop']})")

        time.sleep(1)  # Pause between tests

    print(f"\n{'='*60}")
    print("Test Complete!")
    print("=" * 60)
    print("\nOn actual hardware, you would see:")
    print("  • 'Repeater' label on top-left")
    print("  • '(XX%)' battery percentage on top-right")
    print("  • Separator line")
    print("  • Stats: RX, FWD (with %), DROP")
    print("\nBattery updates every 60 seconds automatically.")


if __name__ == '__main__':
    try:
        test_battery_display()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nError during test: {e}")
        import traceback
        traceback.print_exc()
