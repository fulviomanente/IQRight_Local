
#!/usr/bin/env python3
"""
Simple QR Scanner Test Script
Tests Waveshare 2D scanner via UART with different configurations
"""

import threading
import time
import queue
import os
import sys
from datetime import datetime

# Check if running locally (Mac) or on Raspberry Pi
IS_LOCAL = os.environ.get("LOCAL") == 'TRUE'

if not IS_LOCAL:
    try:
        import RPi.GPIO as GPIO
        import serial
    except ImportError:
        print("RPi.GPIO not found - setting LOCAL mode")
        IS_LOCAL = True

if IS_LOCAL:
    print("Running in LOCAL mode (Mac) - Serial operations will be mocked")

class QRScannerTest:
    def __init__(self):
        self.queue = queue.Queue()
        self.running = True
        self.scan_count = 0

        if not IS_LOCAL:
            # Raspberry Pi hardware setup
            self.inPin = 21
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.inPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            try:
                self.ser = serial.Serial("/dev/serial0", 115200, timeout=2)
                print(f"Serial port opened: /dev/serial0 @ 115200 baud")
            except Exception as e:
                print(f"Error opening serial port: {e}")
                sys.exit(1)

    def read_scanner(self):
        """Main scanner reading loop"""
        print("\n" + "="*50)
        print("QR Scanner Test Started")
        print("="*50)
        print("Press trigger button to scan (Ctrl+C to exit)")

        if IS_LOCAL:
            print("\nLOCAL MODE: Enter QR codes manually (type 'quit' to exit)")
            self.mock_scanner_loop()
        else:
            self.hardware_scanner_loop()

    def hardware_scanner_loop(self):
        """Real hardware scanner loop for Raspberry Pi"""
        try:
            while self.running:
                pressed = GPIO.input(self.inPin)
                if pressed == 0:  # Button pressed (active low)
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Trigger pressed - scanning...")

                    # Send scan command to scanner
                    self.ser.write(bytes.fromhex("7E000801000201ABCD"))
                    time.sleep(0.1)

                    # Read blank return
                    blankReturn = self.ser.read()
                    time.sleep(1.3)

                    # Read QR code data
                    remaining = self.ser.inWaiting()
                    if remaining > 0:
                        codeReaded = self.ser.read(remaining)
                        qrCode = str(codeReaded, encoding="UTF-8")

                        self.scan_count += 1
                        print(f"Scan #{self.scan_count}")
                        print(f"  RAW DATA: {qrCode}")
                        print(f"  HEX DATA: {codeReaded.hex()}")

                        # Extract actual QR content (skip first 6 chars which are header)
                        qr_content = qrCode[6:].strip() if len(qrCode) > 6 else qrCode.strip()
                        print(f"  BEFORE QUEUE: '{qr_content}'")

                        # Put on queue
                        self.queue.put(qr_content)

                        # Process from queue
                        self.process_queue()
                    else:
                        print("  No data received")

                    # Debounce delay
                    time.sleep(0.5)

                time.sleep(0.01)  # Small delay to prevent CPU hogging

        except KeyboardInterrupt:
            print("\n\nStopping scanner test...")
        except Exception as e:
            print(f"Error in scanner loop: {e}")
        finally:
            self.cleanup()

    def mock_scanner_loop(self):
        """Mock scanner loop for local development"""
        try:
            while self.running:
                qr_input = input("\nEnter QR code (or 'quit'): ")
                if qr_input.lower() == 'quit':
                    break

                self.scan_count += 1
                print(f"\nScan #{self.scan_count}")
                print(f"  MOCK INPUT: '{qr_input}'")
                print(f"  BEFORE QUEUE: '{qr_input}'")

                # Put on queue
                self.queue.put(qr_input)

                # Process from queue
                self.process_queue()

        except KeyboardInterrupt:
            print("\n\nStopping scanner test...")
        finally:
            self.running = False

    def process_queue(self):
        """Process items from the queue"""
        while not self.queue.empty():
            try:
                item = self.queue.get(timeout=0.1)
                print(f"  AFTER QUEUE: '{item}'")
                print(f"  Length: {len(item)} chars")

                # You can add additional processing here to test different configurations
                # For example, parsing different QR formats, checking prefixes, etc.

            except queue.Empty:
                pass
            except Exception as e:
                print(f"Error processing queue: {e}")

    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if not IS_LOCAL:
            if hasattr(self, 'ser'):
                self.ser.close()
                print("Serial port closed")
            GPIO.cleanup()
            print("GPIO cleaned up")
        print("Test completed")
        print(f"Total scans: {self.scan_count}")

def main():
    # Set LOCAL environment variable for Mac development
    if sys.platform == "darwin":
        os.environ["LOCAL"] = "TRUE"
        print("Detected macOS - setting LOCAL=TRUE")

    scanner = QRScannerTest()
    scanner.read_scanner()

if __name__ == "__main__":
    main()