#!/usr/bin/env python3
"""
Simple test to determine if your RFM95x module is faulty
"""

import time
import board
import busio
import digitalio
import adafruit_rfm9x

def test_rfm95x_module_quality():
    """Quick test to determine if the module itself is the problem"""
    
    print("RFM95x Module Quality Test")
    print("=" * 40)
    
    # Setup
    cs_pin = digitalio.DigitalInOut(board.CE1)
    cs_pin.direction = digitalio.Direction.OUTPUT
    cs_pin.value = True
    
    reset_pin = digitalio.DigitalInOut(board.D25)
    reset_pin.direction = digitalio.Direction.OUTPUT 
    reset_pin.value = True
    
    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
    
    # Test at multiple speeds
    speeds = [100000, 500000, 1000000, 2000000]
    
    for speed in speeds:
        print(f"\nTesting at {speed//1000}kHz:")
        success_count = 0
        
        for attempt in range(20):
            # Reset module
            reset_pin.value = False
            time.sleep(0.1)
            reset_pin.value = True
            time.sleep(0.5)
            
            try:
                rfm = adafruit_rfm9x.RFM9x(
                    spi, cs_pin, reset_pin, 915.0, 
                    baudrate=speed
                )
                
                # Check version register
                version = rfm.version
                if version == 0x12:
                    success_count += 1
                    print("✓", end="")
                else:
                    print(f"✗({version:02X})", end="")
                    
            except Exception as e:
                print("✗", end="")
            
            if (attempt + 1) % 10 == 0:
                print()
        
        success_rate = success_count / 20 * 100
        print(f" → {success_count}/20 ({success_rate:.1f}%)")
        
        if success_rate == 100:
            print(f"  🎉 PERFECT! Use baudrate={speed}")
            break
        elif success_rate > 90:
            print(f"  ✅ GOOD! Use baudrate={speed}")
        elif success_rate < 50:
            print(f"  ❌ POOR - module may be defective")

if __name__ == "__main__":
    test_rfm95x_module_quality()