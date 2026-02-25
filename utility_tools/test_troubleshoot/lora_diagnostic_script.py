#!/usr/bin/env python3
"""
Comprehensive diagnostic script for RFM95x connection issues
Run this to identify hardware/software problems before running the main code
"""

import sys
import os
import subprocess
import time

def run_command(cmd):
    """Run shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def check_system_info():
    """Check basic system information"""
    print("=" * 60)
    print("SYSTEM INFORMATION")
    print("=" * 60)
    
    # Pi model
    success, model, _ = run_command("cat /proc/device-tree/model")
    if success:
        print(f"Pi Model: {model}")
    
    # OS version
    success, version, _ = run_command("cat /etc/os-release | grep PRETTY_NAME")
    if success:
        print(f"OS: {version.split('=')[1].strip('\"')}")
    
    # Python version
    print(f"Python: {sys.version.split()[0]}")
    
    # Kernel version
    success, kernel, _ = run_command("uname -r")
    if success:
        print(f"Kernel: {kernel}")

def check_spi_interface():
    """Check SPI interface status"""
    print("\n" + "=" * 60)
    print("SPI INTERFACE CHECK")
    print("=" * 60)
    
    # Check if SPI is enabled in config
    success, config, _ = run_command("grep -E '^dtparam=spi=on|^#dtparam=spi=on' /boot/config.txt")
    if "dtparam=spi=on" in config and not config.startswith("#"):
        print("✓ SPI enabled in /boot/config.txt")
    else:
        print("✗ SPI not enabled in config - run 'sudo raspi-config'")
    
    # Check SPI module loaded
    success, modules, _ = run_command("lsmod | grep spi")
    if "spi_bcm" in modules:
        print("✓ SPI kernel module loaded")
        print(f"  Modules: {modules}")
    else:
        print("✗ SPI kernel module not loaded")
    
    # Check SPI devices
    if os.path.exists("/dev/spidev0.0"):
        print("✓ SPI device /dev/spidev0.0 exists")
    else:
        print("✗ SPI device /dev/spidev0.0 missing")
        
    if os.path.exists("/dev/spidev0.1"):
        print("✓ SPI device /dev/spidev0.1 exists")
    else:
        print("✗ SPI device /dev/spidev0.1 missing")

def check_gpio_states():
    """Check GPIO pin states"""
    print("\n" + "=" * 60)
    print("GPIO PIN STATUS")
    print("=" * 60)
    
    # Common RFM95x pins
    pins_to_check = [8, 9, 10, 11, 24, 25]  # CE0, MISO, MOSI, SCLK, interrupt, reset
    
    success, gpio_info, _ = run_command(f"raspi-gpio get {','.join(map(str, pins_to_check))}")
    if success:
        for line in gpio_info.split('\n'):
            if line.strip():
                print(f"  {line}")
    else:
        print("✗ Could not read GPIO states (install raspi-gpio)")

def check_power_voltage():
    """Check system voltages"""
    print("\n" + "=" * 60)
    print("POWER & VOLTAGE CHECK")
    print("=" * 60)
    
    # Check vcgencmd for voltages
    voltages = ['core', 'sdram_c', 'sdram_i', 'sdram_p']
    for v in voltages:
        success, voltage, _ = run_command(f"vcgencmd measure_volts {v}")
        if success:
            print(f"  {v}: {voltage}")
    
    # Check for undervoltage
    success, throttle, _ = run_command("vcgencmd get_throttled")
    if success:
        throttle_val = int(throttle.split('=')[1], 16)
        if throttle_val == 0:
            print("✓ No throttling detected")
        else:
            print(f"⚠ Throttling detected: 0x{throttle_val:x}")
            if throttle_val & 0x1:
                print("  - Under-voltage detected")
            if throttle_val & 0x2:
                print("  - ARM frequency capped")
            if throttle_val & 0x4:
                print("  - Currently throttled")

def check_python_libraries():
    """Check required Python libraries"""
    print("\n" + "=" * 60)
    print("PYTHON LIBRARIES CHECK")
    print("=" * 60)
    
    required_libs = [
        'adafruit_circuitpython_rfm9x',
        'adafruit_blinka',
        'board',
        'busio',
        'digitalio'
    ]
    
    for lib in required_libs:
        try:
            __import__(lib)
            print(f"✓ {lib}")
        except ImportError as e:
            print(f"✗ {lib} - {e}")

def test_basic_gpio():
    """Test basic GPIO functionality"""
    print("\n" + "=" * 60)
    print("BASIC GPIO TEST")
    print("=" * 60)
    
    try:
        import board
        import digitalio
        
        # Test reset pin
        print("Testing reset pin (GPIO25)...")
        reset_pin = digitalio.DigitalInOut(board.D25)
        reset_pin.direction = digitalio.Direction.OUTPUT
        
        reset_pin.value = False
        time.sleep(0.1)
        reset_pin.value = True
        print("✓ Reset pin toggle successful")
        
        # Test CS pin
        print("Testing CS pin (GPIO8)...")
        cs_pin = digitalio.DigitalInOut(board.CE0)
        cs_pin.direction = digitalio.Direction.OUTPUT
        cs_pin.value = True
        print("✓ CS pin setup successful")
        
        print("✓ Basic GPIO test passed")
        
    except Exception as e:
        print(f"✗ GPIO test failed: {e}")

def test_spi_bus():
    """Test SPI bus creation"""
    print("\n" + "=" * 60)
    print("SPI BUS TEST")
    print("=" * 60)
    
    try:
        import board
        import busio
        
        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        print("✓ SPI bus created successfully")
        print(f"  SPI object: {spi}")
        
        # Try to lock/unlock SPI bus
        while not spi.try_lock():
            pass
        print("✓ SPI bus lock acquired")
        
        spi.unlock()
        print("✓ SPI bus unlocked")
        
    except Exception as e:
        print(f"✗ SPI test failed: {e}")

def main():
    """Run all diagnostic checks"""
    print("RFM95x Connection Diagnostic Tool")
    print("This will check your Raspberry Pi setup for common issues")
    
    check_system_info()
    check_spi_interface()
    check_gpio_states()
    check_power_voltage()
    check_python_libraries()
    test_basic_gpio()
    test_spi_bus()
    
    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)
    print("\nIf you see any ✗ marks above, those need to be fixed first.")
    print("Common solutions:")
    print("1. Enable SPI: sudo raspi-config → Interface Options → SPI")
    print("2. Install libraries: pip3 install adafruit-circuitpython-rfm9x")
    print("3. Reboot after enabling SPI")
    print("4. Check wiring with multimeter")
    print("5. Ensure 3.3V power supply is adequate")

if __name__ == "__main__":
    main()