#!/usr/bin/env python3
"""
OLED Display Manager for Scanner

Manages SSD1306 128x64 I2C OLED display with battery optimization.
Shows minimal information: startup status, errors, and critical events.

Hardware:
- SSD1306 OLED 128x64 I2C
- VCC → Pin 1 (3.3V)
- GND → Pin 6 (GND)
- SDA → Pin 3 (GPIO 2)
- SCL → Pin 5 (GPIO 3)

Battery Optimization Strategy:
- Display turns off after 30 seconds of inactivity
- Only wakes on errors or critical events
- Uses low brightness by default
- Minimal screen updates to reduce I2C traffic
"""

import os
import time
import logging
from threading import Lock

# Only import hardware libs if not in LOCAL mode
if os.getenv("LOCAL", "FALSE") != "TRUE":
    try:
        import board
        import busio
        from PIL import Image, ImageDraw, ImageFont
        from adafruit_ssd1306 import SSD1306_I2C
        OLED_AVAILABLE = True
    except ImportError as e:
        logging.warning(f"OLED libraries not available: {e}")
        OLED_AVAILABLE = False
else:
    OLED_AVAILABLE = False


class OLEDDisplay:
    """Manages OLED display with battery optimization"""

    def __init__(self, width: int = 128, height: int = 64, auto_off_seconds: int = 30):
        """
        Initialize OLED display

        Args:
            width: Display width in pixels
            height: Display height in pixels
            auto_off_seconds: Time in seconds before auto-shutoff (0 = never)
        """
        self.width = width
        self.height = height
        self.auto_off_seconds = auto_off_seconds
        self.display = None
        self.image = None
        self.draw = None
        self.font = None
        self.is_on = False
        self.last_update = 0
        self.lock = Lock()

        if not OLED_AVAILABLE:
            logging.info("OLED display disabled (LOCAL mode or missing libraries)")
            return

        try:
            # Initialize I2C
            i2c = busio.I2C(board.SCL, board.SDA)

            # Initialize OLED (I2C address 0x3C or 0x3D)
            try:
                self.display = SSD1306_I2C(width, height, i2c, addr=0x3C)
            except Exception:
                # Try alternate address
                self.display = SSD1306_I2C(width, height, i2c, addr=0x3D)

            # Create blank image for drawing
            self.image = Image.new("1", (width, height))
            self.draw = ImageDraw.Draw(self.image)

            # Load default font (small to save space)
            try:
                self.font = ImageFont.load_default()
            except Exception:
                self.font = None

            # Set contrast (brightness) to 50% to save power
            self.display.contrast(128)  # 0-255, default 207

            logging.info(f"OLED display initialized: {width}x{height}")

            # Show startup message
            self.show_startup()

        except Exception as e:
            logging.error(f"Failed to initialize OLED display: {e}")
            self.display = None

    def _turn_on(self):
        """Turn display on"""
        if self.display and not self.is_on:
            try:
                self.display.poweron()
                self.is_on = True
                logging.debug("OLED powered on")
            except Exception as e:
                logging.error(f"Failed to power on OLED: {e}")

    def _turn_off(self):
        """Turn display off to save battery"""
        if self.display and self.is_on:
            try:
                self.display.poweroff()
                self.is_on = False
                logging.debug("OLED powered off (battery save)")
            except Exception as e:
                logging.error(f"Failed to power off OLED: {e}")

    def _check_auto_off(self):
        """Check if display should auto-off"""
        if self.auto_off_seconds > 0 and self.is_on:
            elapsed = time.time() - self.last_update
            if elapsed > self.auto_off_seconds:
                self._turn_off()

    def _clear(self):
        """Clear display buffer"""
        if self.draw:
            self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

    def _update(self):
        """Update display with current buffer"""
        if self.display:
            try:
                self.display.image(self.image)
                self.display.show()
                self.last_update = time.time()
            except Exception as e:
                logging.error(f"Failed to update OLED: {e}")

    def show_startup(self):
        """Show startup message"""
        with self.lock:
            if not self.display:
                return

            self._turn_on()
            self._clear()

            # Draw startup screen
            self.draw.text((10, 5), "IQRight Scanner", font=self.font, fill=255)
            self.draw.text((20, 25), "Starting...", font=self.font, fill=255)
            self.draw.text((10, 45), f"Node: {os.getenv('LORA_NODE_ID', '???')}", font=self.font, fill=255)

            self._update()
            logging.info("OLED: Startup screen displayed")

    def show_ready(self, node_id: int = None, device_type: str = "Scanner"):
        """Show ready status"""
        with self.lock:
            if not self.display:
                return

            self._turn_on()
            self._clear()

            # Draw ready screen
            self.draw.text((15, 10), f"{device_type} Ready", font=self.font, fill=255)
            if node_id:
                self.draw.text((10, 30), f"Node ID: {node_id}", font=self.font, fill=255)

            if device_type == "Repeater":
                self.draw.text((10, 50), "Listening...", font=self.font, fill=255)
            else:
                self.draw.text((10, 50), "Waiting for scan", font=self.font, fill=255)

            self._update()
            logging.info(f"OLED: {device_type} ready screen displayed")

    def show_error(self, error_msg: str, duration: int = 10):
        """
        Show error message

        Args:
            error_msg: Error message to display (max 3 lines)
            duration: How long to show error (seconds, 0 = use auto_off)
        """
        with self.lock:
            if not self.display:
                return

            self._turn_on()
            self._clear()

            # Draw error screen
            self.draw.text((10, 5), "ERROR!", font=self.font, fill=255)
            self.draw.rectangle((0, 18, self.width, 20), outline=255, fill=255)

            # Word wrap error message
            words = error_msg.split()
            lines = []
            current_line = ""

            for word in words:
                test_line = f"{current_line} {word}".strip()
                # Rough estimate: 6 pixels per char
                if len(test_line) * 6 < self.width - 10:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word

            if current_line:
                lines.append(current_line)

            # Draw up to 3 lines
            y = 25
            for line in lines[:3]:
                self.draw.text((5, y), line, font=self.font, fill=255)
                y += 12

            self._update()
            logging.info(f"OLED: Error displayed - {error_msg}")

            # Override auto-off for errors
            if duration > 0:
                self.last_update = time.time() + duration - self.auto_off_seconds

    def show_scan_result(self, count: int):
        """
        Show scan result (brief flash)

        Args:
            count: Number of students found
        """
        with self.lock:
            if not self.display:
                return

            self._turn_on()
            self._clear()

            # Draw scan result
            if count == 0:
                self.draw.text((20, 20), "No students", font=self.font, fill=255)
                self.draw.text((30, 40), "found", font=self.font, fill=255)
            elif count == 1:
                self.draw.text((25, 20), "1 student", font=self.font, fill=255)
                self.draw.text((35, 40), "found", font=self.font, fill=255)
            else:
                self.draw.text((15, 20), f"{count} students", font=self.font, fill=255)
                self.draw.text((35, 40), "found", font=self.font, fill=255)

            self._update()
            logging.debug(f"OLED: Scan result displayed - {count} students")

    def show_repeater_stats(self, received: int, forwarded: int, dropped: int):
        """
        Show repeater statistics

        Args:
            received: Total packets received
            forwarded: Total packets forwarded
            dropped: Total packets dropped
        """
        with self.lock:
            if not self.display:
                return

            self._turn_on()
            self._clear()

            # Draw stats
            self.draw.text((20, 5), "Repeater Stats", font=self.font, fill=255)
            self.draw.rectangle((0, 18, self.width, 20), outline=255, fill=255)

            self.draw.text((5, 25), f"RX: {received}", font=self.font, fill=255)
            self.draw.text((5, 38), f"FWD: {forwarded}", font=self.font, fill=255)
            self.draw.text((5, 51), f"DROP: {dropped}", font=self.font, fill=255)

            # Calculate forward rate
            if received > 0:
                rate = int(forwarded / received * 100)
                self.draw.text((70, 38), f"({rate}%)", font=self.font, fill=255)

            self._update()
            logging.debug(f"OLED: Stats displayed - RX:{received} FWD:{forwarded} DROP:{dropped}")

    def show_packet_forwarded(self, src: int, dst: int):
        """
        Show packet forwarding notification (brief)

        Args:
            src: Source node ID
            dst: Destination node ID
        """
        with self.lock:
            if not self.display:
                return

            self._turn_on()
            self._clear()

            self.draw.text((25, 15), "Forwarding", font=self.font, fill=255)
            self.draw.text((10, 35), f"{src} → {dst}", font=self.font, fill=255)

            self._update()
            logging.debug(f"OLED: Forwarding {src} → {dst}")

    def show_lora_error(self):
        """Show LoRa communication error"""
        self.show_error("LoRa communication failed", duration=15)

    def show_teacher_load_error(self):
        """Show teacher file load error"""
        self.show_error("Teacher file load failed", duration=15)

    def update(self):
        """Periodic update - checks for auto-off"""
        with self.lock:
            self._check_auto_off()

    def shutdown(self):
        """Gracefully shutdown display"""
        with self.lock:
            if self.display:
                try:
                    self._clear()
                    self.draw.text((20, 25), "Shutting down", font=self.font, fill=255)
                    self._update()
                    time.sleep(1)
                    self._turn_off()
                    logging.info("OLED display shutdown")
                except Exception as e:
                    logging.error(f"Error during OLED shutdown: {e}")


# Singleton instance
_oled_instance = None


def get_oled_display(auto_off_seconds: int = 30) -> OLEDDisplay:
    """
    Get or create OLED display singleton

    Args:
        auto_off_seconds: Time before auto-shutoff (default: 30s)

    Returns:
        OLEDDisplay instance
    """
    global _oled_instance
    if _oled_instance is None:
        _oled_instance = OLEDDisplay(auto_off_seconds=auto_off_seconds)
    return _oled_instance
