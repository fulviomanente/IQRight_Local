import spidev
spi = spidev.SpiDev()
spi.open(0, 1)  # bus 0, CE1 = GPIO7
spi.max_speed_hz = 5000000
spi.mode = 0
# Read RFM95x version register (0x42)
resp = spi.xfer2([0x42, 0x00])
print(f"Version register: 0x{resp[1]:02X}")  # should be 0x12
spi.close()