#!/usr/bin/env python3
"""
LoRa Test Client with GUI - Sends test messages with configurable parameters
Touch-friendly interface for Raspberry Pi with touchscreen
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import busio
import board
import digitalio
import adafruit_rfm9x
from datetime import datetime
import logging
import logging.handlers
import os
import sys
import random
import queue
import RPi.GPIO as GPIO
from meshstatic import MeshNode

# Configuration
RFM9X_FREQUENCE = 915.23  # MHz - same as server
RFM9X_NODE = 102  # Client node ID (from scanner_queue.py)
RFM9X_DESTINATION = 1  # Server node ID
RFM9X_ACK_DELAY = 0.1
RFM9X_TIMEOUT = 5.0

# GPIO Configuration (from scanner_queue.py)
GPIO_BUTTON_PIN = 21

# Default parameters
DEFAULT_TX_POWER = 23
DEFAULT_SPREADING_FACTOR = 9

class LoRaTestClientGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("LoRa Test Client")
        self.geometry("800x600")
        self.configure(bg='#f0f0f0')

        # Make fullscreen for touchscreen
        self.attributes('-fullscreen', True)

        # Variables
        self.tx_power = tk.IntVar(value=DEFAULT_TX_POWER)
        self.spreading_factor = tk.IntVar(value=DEFAULT_SPREADING_FACTOR)
        self.is_running = False
        self.message_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.last_rssi = tk.StringVar(value="N/A")
        self.last_snr = tk.StringVar(value="N/A")
        self.button_status = tk.StringVar(value="Ready")

        # Queue for thread-safe GUI updates
        self.log_queue = queue.Queue()

        # GPIO Setup
        self.setup_gpio()

        # Initialize LoRa
        self.rfm9x = None
        self.lora_lock = threading.Lock()

        # Setup GUI
        self.setup_gui()

        # Setup logging
        self.setup_logging()

        # RSSI/SNR storage for display
        self.current_rssi = None
        self.current_snr = None

        # Initialize LoRa with default parameters
        self.init_lora()
        self.node = MeshNode(self.rfm9x, node_id=RFM9X_NODE)

        def on_msg(pkt, rssi):
            # handle incoming command from server or broadcast
            print(f"[SCANNER {self.node.node_id}] RX src={pkt['src']} seq={pkt['seq']} rssi={rssi} payload={pkt['payload']}")

        self.node.on_message = on_msg

        # Start log processor
        self.process_log_queue()

        # Start button monitoring thread
        self.button_thread = None
        self.start_button_monitor()

    def setup_gui(self):
        """Create the GUI layout"""
        # Top frame for title and exit
        top_frame = tk.Frame(self, bg='#2196F3', height=60)
        top_frame.pack(fill=tk.X, pady=0)

        title_label = tk.Label(top_frame, text="LoRa Test Client",
                               font=("Arial", 24, "bold"),
                               fg="white", bg='#2196F3')
        title_label.pack(side=tk.LEFT, padx=20, pady=10)

        exit_btn = tk.Button(top_frame, text="EXIT",
                            command=self.quit_app,
                            font=("Arial", 14, "bold"),
                            bg="#f44336", fg="white",
                            width=10, height=2)
        exit_btn.pack(side=tk.RIGHT, padx=20, pady=10)

        # Parameter control frame
        param_frame = tk.Frame(self, bg='white', relief=tk.RAISED, bd=2)
        param_frame.pack(fill=tk.X, padx=10, pady=10)

        # TX Power control
        tx_frame = tk.Frame(param_frame, bg='white')
        tx_frame.pack(side=tk.LEFT, padx=20, pady=10)

        tk.Label(tx_frame, text="TX Power (dBm)",
                font=("Arial", 12, "bold"),
                bg='white').pack()

        tx_value_label = tk.Label(tx_frame, textvariable=self.tx_power,
                                 font=("Arial", 20, "bold"),
                                 bg='white', fg='#2196F3')
        tx_value_label.pack(pady=5)

        tx_button_frame = tk.Frame(tx_frame, bg='white')
        tx_button_frame.pack()

        tk.Button(tx_button_frame, text="-",
                 command=lambda: self.adjust_tx_power(-1),
                 font=("Arial", 16, "bold"),
                 width=3, height=2).pack(side=tk.LEFT, padx=2)

        tk.Button(tx_button_frame, text="+",
                 command=lambda: self.adjust_tx_power(1),
                 font=("Arial", 16, "bold"),
                 width=3, height=2).pack(side=tk.LEFT, padx=2)

        # Spreading Factor control
        sf_frame = tk.Frame(param_frame, bg='white')
        sf_frame.pack(side=tk.LEFT, padx=20, pady=10)

        tk.Label(sf_frame, text="Spreading Factor",
                font=("Arial", 12, "bold"),
                bg='white').pack()

        sf_value_label = tk.Label(sf_frame, textvariable=self.spreading_factor,
                                 font=("Arial", 20, "bold"),
                                 bg='white', fg='#2196F3')
        sf_value_label.pack(pady=5)

        sf_button_frame = tk.Frame(sf_frame, bg='white')
        sf_button_frame.pack()

        tk.Button(sf_button_frame, text="-",
                 command=lambda: self.adjust_spreading_factor(-1),
                 font=("Arial", 16, "bold"),
                 width=3, height=2).pack(side=tk.LEFT, padx=2)

        tk.Button(sf_button_frame, text="+",
                 command=lambda: self.adjust_spreading_factor(1),
                 font=("Arial", 16, "bold"),
                 width=3, height=2).pack(side=tk.LEFT, padx=2)

        # Status frame
        status_frame = tk.Frame(param_frame, bg='white')
        status_frame.pack(side=tk.LEFT, padx=30, pady=10)

        tk.Label(status_frame, text="Last RSSI:",
                font=("Arial", 12),
                bg='white').grid(row=0, column=0, sticky='w')

        tk.Label(status_frame, textvariable=self.last_rssi,
                font=("Arial", 12, "bold"),
                bg='white', fg='green').grid(row=0, column=1, padx=10)

        tk.Label(status_frame, text="Last SNR:",
                font=("Arial", 12),
                bg='white').grid(row=1, column=0, sticky='w')

        tk.Label(status_frame, textvariable=self.last_snr,
                font=("Arial", 12, "bold"),
                bg='white', fg='green').grid(row=1, column=1, padx=10)

        tk.Label(status_frame, text="Button:",
                font=("Arial", 12),
                bg='white').grid(row=2, column=0, sticky='w')

        tk.Label(status_frame, textvariable=self.button_status,
                font=("Arial", 12, "bold"),
                bg='white', fg='blue').grid(row=2, column=1, padx=10)

        # Statistics frame
        stats_frame = tk.Frame(param_frame, bg='white')
        stats_frame.pack(side=tk.RIGHT, padx=20, pady=10)

        self.stats_label = tk.Label(stats_frame,
                                   text="Messages: 0\nSuccess: 0\nFailed: 0",
                                   font=("Arial", 11),
                                   bg='white', justify=tk.LEFT)
        self.stats_label.pack()

        # Log display frame
        log_frame = tk.Frame(self, bg='white', relief=tk.SUNKEN, bd=2)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        tk.Label(log_frame, text="Logs",
                font=("Arial", 14, "bold"),
                bg='white').pack(anchor='w', padx=10, pady=5)

        # Scrolled text widget for logs
        self.log_text = scrolledtext.ScrolledText(log_frame,
                                                  wrap=tk.WORD,
                                                  font=("Courier", 10),
                                                  bg='black',
                                                  fg='lime',
                                                  height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Configure text tags for different log levels
        self.log_text.tag_config('INFO', foreground='lime')
        self.log_text.tag_config('SUCCESS', foreground='cyan')
        self.log_text.tag_config('WARNING', foreground='yellow')
        self.log_text.tag_config('ERROR', foreground='red')

    def setup_gpio(self):
        """Setup GPIO for button input"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(GPIO_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.log_message(f"GPIO button initialized on pin {GPIO_BUTTON_PIN}", 'INFO')
        except Exception as e:
            self.log_message(f"GPIO setup error: {e}", 'ERROR')
            logging.error(f"GPIO setup error: {e}")

    def setup_logging(self):
        """Setup logging configuration"""
        log_filename = "lora_test_client_gui.log"
        handler = logging.handlers.RotatingFileHandler(
            log_filename,
            maxBytes=10 * 1024 * 1024,
            backupCount=5
        )
        log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(log_formatter)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)

    def log_message(self, message, level='INFO'):
        """Add message to log queue"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_queue.put((f"[{timestamp}] {message}", level))

    def process_log_queue(self):
        """Process log messages from queue"""
        try:
            while not self.log_queue.empty():
                message, level = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, message + '\n', level)
                self.log_text.see(tk.END)  # Auto-scroll to bottom
        except:
            pass
        finally:
            self.after(100, self.process_log_queue)

    def adjust_tx_power(self, delta):
        """Adjust TX power within limits"""
        new_value = self.tx_power.get() + delta
        if 5 <= new_value <= 23:
            self.tx_power.set(new_value)
            self.log_message(f"TX Power changed to {new_value} dBm", 'INFO')
            self.reinit_lora()

    def adjust_spreading_factor(self, delta):
        """Adjust spreading factor within limits"""
        new_value = self.spreading_factor.get() + delta
        if 6 <= new_value <= 12:
            self.spreading_factor.set(new_value)
            self.log_message(f"Spreading Factor changed to {new_value}", 'INFO')
            self.reinit_lora()

    def init_lora(self):
        """Initialize LoRa radio module - matching scanner_queue.py exactly"""
        try:
            with self.lora_lock:
                if os.environ.get("LOCAL") == 'TRUE':
                    self.log_message("Running in LOCAL mode - LoRa hardware bypassed", 'WARNING')
                    return False

                # Configure LoRa Radio - exactly as scanner_queue.py
                CS = digitalio.DigitalInOut(board.CE1)
                RESET = digitalio.DigitalInOut(board.D25)
                # Initialize SPI bus.
                spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

                # Initialize RFM radio
                self.rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, RFM9X_FREQUENCE)

                # Set parameters - note: scanner_queue.py doesn't explicitly set tx_power or spreading_factor
                # Using library defaults unless we set them
                if self.tx_power.get() != 23:  # Only set if not default
                    self.rfm9x.tx_power = self.tx_power.get()
                if self.spreading_factor.get() != 7:  # Only set if not default
                    self.rfm9x.spreading_factor = self.spreading_factor.get()

                # Set node addresses - exactly as scanner_queue.py
                self.rfm9x.node = RFM9X_NODE
                #self.rfm9x.destination = RFM9X_DESTINATION
                # Note: scanner_queue.py doesn't set ack_delay explicitly

                self.log_message("LoRa initialized successfully", 'SUCCESS')
                self.log_message(f"  Frequency: {RFM9X_FREQUENCE} MHz", 'INFO')
                self.log_message(f"  TX Power: {self.tx_power.get()} dBm", 'INFO')
                self.log_message(f"  Spreading Factor: {self.spreading_factor.get()}", 'INFO')
                self.log_message(f"  Node ID: {RFM9X_NODE} → Destination: {RFM9X_DESTINATION}", 'INFO')
                return True

        except Exception as e:
            self.log_message(f"Failed to initialize LoRa: {e}", 'ERROR')
            logging.error(f"LoRa init error: {e}")
            return False

    def reinit_lora(self):
        """Reinitialize LoRa with new parameters"""
        self.log_message("Reinitializing LoRa module...", 'INFO')
        self.init_lora()

    def generate_test_payload(self):
        """Generate test payload"""
        test_codes = [
            "123456789",
            "987654321",
            "TEST12345",
            "SCAN00001",
            "QRCODE123"
        ]
        test_code = random.choice(test_codes)
        distance = random.randint(1, 10)
        payload = f"{RFM9X_NODE}:{test_code}:{distance}"
        return payload

    def send_message(self):
        """Send a single message - matching scanner_queue.py lora_sender pattern"""
        self.log_message("send message", 'INFO')

        if not self.rfm9x:
            return False

        self.message_count += 1
        self.log_message("Generate Payload...", 'INFO')

        payload = self.generate_test_payload()

        # Match scanner_queue.py's lora_sender method
        startTime = time.time()
        cont = 0
        sending = True

        try:
            while sending:
                cont += 1
                with self.lora_lock:
                    # Send exactly like scanner_queue.py: bytes(f"{node}|{payload}|1", "UTF-8")
                    # But our payload already includes the format
                    self.log_message("Call Unicast...", 'INFO')

                    if self.node.send_request(1, f"{payload}", await_ack=True):
                        self.log_message(f"Info sent to Server and ACK Received", 'INFO')
                        count = 0
                        for line in self.node.full_response:
                            cont += 1
                            self.log_message(f"{count}: {line}", 'INFO')
                        self.button_status.set(f"Sent")
                        self.button_status.set("Ready")
                        sending = False
                        return True
                    else:
                        self.log_message(f"Ack not received - {cont} attempts", 'ERROR')
                        self.button_status.set(f"Error")
                        self.fail_count += 1

                    if self.fail_count > 3:
                        sending = False
                        self.button_status.set("Timeout")
                        return False

        except Exception as e:
            self.fail_count += 1
            self.log_message(f"Send error: {e}", 'ERROR')
            logging.error(f"Send error: {e}")
            return False

    def lora_receiver(self):
        """Receive response - matching scanner_queue.py lora_receiver pattern"""
        startTime = time.time()
        while True:
            # Look for a new packet: only accept if addressed to my_node
            packet = self.rfm9x.receive(with_header=True)

            # If no packet was received during the timeout then None is returned.
            if packet is not None:
                # Received a packet!
                try:
                    strPayload = str(packet[4:], "UTF-8")
                    self.log_message(f"Received: {strPayload}", 'SUCCESS')

                    # Parse response (expecting format like from server)
                    parts = strPayload.split("|")
                    if len(parts) >= 1:
                        # Store RSSI/SNR values for display update
                        self.current_rssi = self.rfm9x.last_rssi if hasattr(self.rfm9x, 'last_rssi') else None
                        self.current_snr = self.rfm9x.last_snr if hasattr(self.rfm9x, 'last_snr') else None

                        self.log_message(f"RSSI: {self.current_rssi} dBm, SNR: {self.current_snr:.1f} dB" if self.current_snr else f"RSSI: {self.current_rssi} dBm", 'SUCCESS')

                        return True
                except Exception as e:
                    self.log_message(f"Error parsing response: {e}", 'ERROR')
                    return False

            # Check timeout - match scanner_queue.py's 5 second timeout
            if time.time() >= startTime + 5:
                return False

    def update_stats(self):
        """Update statistics display"""
        success_rate = (self.success_count / self.message_count * 100) if self.message_count > 0 else 0
        stats_text = f"Messages: {self.message_count}\n"
        stats_text += f"Success: {self.success_count} ({success_rate:.1f}%)\n"
        stats_text += f"Failed: {self.fail_count}"
        self.stats_label.config(text=stats_text)

    def update_rssi_snr_display(self):
        """Update RSSI and SNR display values"""
        if self.current_rssi is not None:
            self.last_rssi.set(f"{self.current_rssi} dBm")
        if self.current_snr is not None:
            self.last_snr.set(f"{self.current_snr:.1f} dB")

    def button_monitor_loop(self):
        """Monitor GPIO button and send messages when pressed"""
        self.log_message("Starting button monitor...", 'INFO')
        self.log_message(f"Press the button on GPIO pin {GPIO_BUTTON_PIN} to send packets", 'INFO')

        button_pressed = False

        while self.is_running:
            try:
                # Read button state (0 = pressed, 1 = not pressed)
                pressed = GPIO.input(GPIO_BUTTON_PIN)

                if pressed == 0 and not button_pressed:
                    # Button just pressed
                    button_pressed = True
                    self.button_status.set("Sending...")
                    self.log_message("Button pressed - sending packet...", 'INFO')

                    # Send message
                    if self.rfm9x:
                        self.log_message("Creating new Thread...", 'INFO')
                        # Run send in a separate thread to not block GUI
                        send_thread = threading.Thread(target=lambda: [
                            self.send_message(),
                            self.after(0, self.update_stats)
                        ])
                        send_thread.daemon = True
                        send_thread.start()

                    # Wait a bit to debounce
                    time.sleep(0.2)

                elif pressed == 1 and button_pressed:
                    # Button released
                    button_pressed = False
                    self.button_status.set("Ready")

            except Exception as e:
                self.log_message(f"Button monitor error: {e}", 'ERROR')
                logging.error(f"Button monitor error: {e}")

            time.sleep(0.05)  # Small delay to avoid CPU overuse

    def start_button_monitor(self):
        """Start the button monitoring thread"""
        if not self.is_running:
            self.is_running = True
            self.button_thread = threading.Thread(target=self.button_monitor_loop, daemon=True)
            self.button_thread.start()
            self.log_message("Button monitor started", 'SUCCESS')

    def stop_button_monitor(self):
        """Stop the button monitoring thread"""
        self.is_running = False
        if self.button_thread:
            self.button_thread.join(timeout=1)
        self.log_message("Button monitor stopped", 'WARNING')

    def quit_app(self):
        """Quit the application"""
        self.stop_button_monitor()
        GPIO.cleanup()
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = LoRaTestClientGUI()
    app.mainloop()
