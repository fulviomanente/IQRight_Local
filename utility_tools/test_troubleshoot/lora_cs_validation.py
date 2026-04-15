import spidev
spi = spidev.SpiDev()
spi.open(0, 0)  # try CE0 instead
spi.max_speed_hz = 5000000
spi.mode = 0
resp = spi.xfer2([0x42, 0x00])
print(f"CE0 response: 0x{resp[1]:02X}")
spi.close()