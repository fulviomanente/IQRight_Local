import spidev
import RPi.GPIO as GPIO
import time

RST = 25
GPIO.setmode(GPIO.BCM)
GPIO.setup(RST, GPIO.OUT)

# Reset sequence
GPIO.output(RST, GPIO.LOW)
time.sleep(0.1)
GPIO.output(RST, GPIO.HIGH)
time.sleep(0.1)

spi = spidev.SpiDev()
spi.open(0, 1)  # CE1
spi.max_speed_hz = 5000000
spi.mode = 0
resp = spi.xfer2([0x42, 0x00])
print(f"After reset: 0x{resp[1]:02X}")
spi.close()
GPIO.cleanup()