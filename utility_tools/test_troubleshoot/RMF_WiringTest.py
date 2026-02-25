# SPDX-FileCopyrightText: 2018 Brent Rubell for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
Wiring Check, Pi Radio w/RFM9x
Learn Guide: https://learn.adafruit.com/lora-and-lorawan-for-raspberry-pi
Author: Brent Rubell for Adafruit Industries
"""
import time
import busio
from digitalio import DigitalInOut, Direction, Pull
import board
# Import the RFM9x radio module.
import adafruit_rfm9x
# Button A
btnA = DigitalInOut(board.D5)
btnA.direction = Direction.INPUT
btnA.pull = Pull.UP
# Button B
btnB = DigitalInOut(board.D6)
btnB.direction = Direction.INPUT
btnB.pull = Pull.UP
# Button C
btnC = DigitalInOut(board.D12)
btnC.direction = Direction.INPUT
btnC.pull = Pull.UP
# Create the I2C interface.
i2c = busio.I2C(board.SCL, board.SDA)
# 128x32 OLED Display
reset_pin = DigitalInOut(board.D4)
#$display = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c, reset=reset_pin)
# Clear the display.
#display.fill(0)
#display.show()
#width = display.width
#height = display.height
# Configure RFM9x LoRa Radio
CS = DigitalInOut(board.CE1)
RESET = DigitalInOut(board.D25)
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
while True:
 # Clear the image
 #display.fill(0)
 # Attempt to set up the RFM9x Module
 try:
     rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, 915.0)
     print('RFM9x: Detected')
 except RuntimeError as error:
     # Thrown on version mismatch
     print('RFM9x Error: ', error)
 # Check buttons

 time.sleep(0.1)