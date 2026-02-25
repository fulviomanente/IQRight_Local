#!/bin/bash
# Guaranteed Clean SPI Test
# This ensures nothing else is using SPI before testing RFM95x

echo "=== ENSURING CLEAN SPI ENVIRONMENT ==="

# 1. Kill any Python processes that might use SPI
echo "Stopping any Python processes..."
sudo pkill -f python.*spi
sudo pkill -f python.*rfm
sudo pkill -f python.*lora
sleep 2

# 2. Check if SPI is still in use
echo "Checking SPI usage..."
if sudo lsof /dev/spidev* 2>/dev/null; then
    echo "❌ ERROR: SPI is still in use by above processes"
    echo "Please stop these processes and try again"
    exit 1
else
    echo "✅ SPI devices are free"
fi

# 3. Reset SPI module (if safe to do)
echo "Resetting SPI driver..."
sudo modprobe -r spidev
sudo modprobe -r spi_bcm2835  
sleep 1
sudo modprobe spi_bcm2835
sudo modprobe spidev
sleep 1

# 4. Verify SPI devices exist
if [ -e /dev/spidev0.0 ] && [ -e /dev/spidev0.1 ]; then
    echo "✅ SPI devices recreated successfully"
elif [ -e /dev/spidev0.0 ]; then
    echo "✅ SPI device spidev0.0 available (sufficient for RFM95x)"
else
    echo "❌ ERROR: No SPI devices found"
    echo "Check that SPI is enabled: sudo raspi-config"
    exit 1
fi

# 5. Check GPIO states
echo "Checking SPI GPIO states..."
raspi-gpio get 8,9,10,11

# 6. Set file permissions (just in case)
sudo chmod 666 /dev/spidev0.*

echo ""
echo "✅ SPI ENVIRONMENT IS CLEAN"
echo "Now run your RFM95x test..."
echo ""
echo "Test command:"
echo "python3 your_rfm95x_test.py"