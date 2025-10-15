#!/usr/bin/env python3
"""
LoRa Ping-Pong Test - Scanner Side

Sends PING packets to server and displays PONG responses with RSSI.
Shows signal strength to help determine if repeater is needed.

Usage:
    python3 test_ping_scanner.py
"""

import os
import time
import tkinter as tk
from tkinter import ttk
from threading import Thread, Lock
from dotenv import load_dotenv

load_dotenv()

from lora import LoRaTransceiver, LoRaPacket, PacketType, NodeType
from utils.config import LORA_NODE_ID, LORA_FREQUENCY, LORA_TX_POWER

# Check if running in LOCAL mode (no hardware)
LOCAL_MODE = os.getenv("LOCAL", "FALSE") == "TRUE"


class PingScannerGUI:
    """GUI for LoRa ping test on scanner"""

    def __init__(self, root):
        self.root = root
        self.root.title(f"LoRa Ping Test - Scanner {LORA_NODE_ID}")
        self.root.geometry("800x600")

        self.transceiver = None
        self.running = False
        self.lock = Lock()

        # Statistics
        self.pings_sent = 0
        self.pongs_received = 0
        self.rssi_values = []
        self.via_repeater_count = 0
        self.direct_count = 0

        self._setup_ui()

        # Start LoRa in background
        if not LOCAL_MODE:
            Thread(target=self._init_lora, daemon=True).start()

    def _setup_ui(self):
        """Setup GUI layout"""

        # Top frame - Status
        status_frame = tk.Frame(self.root, bg="#2c3e50", height=80)
        status_frame.pack(fill=tk.X, padx=10, pady=10)
        status_frame.pack_propagate(False)

        tk.Label(
            status_frame,
            text=f"Scanner Node {LORA_NODE_ID}",
            font=("Arial", 16, "bold"),
            bg="#2c3e50",
            fg="white"
        ).pack(pady=5)

        self.status_label = tk.Label(
            status_frame,
            text="Initializing LoRa...",
            font=("Arial", 12),
            bg="#2c3e50",
            fg="yellow"
        )
        self.status_label.pack()

        # Info frame - Signal strength
        info_frame = tk.Frame(self.root, bg="#34495e")
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        # Current RSSI
        rssi_frame = tk.Frame(info_frame, bg="#34495e")
        rssi_frame.pack(pady=10)

        tk.Label(
            rssi_frame,
            text="Signal Strength (RSSI):",
            font=("Arial", 14, "bold"),
            bg="#34495e",
            fg="white"
        ).pack(side=tk.LEFT, padx=5)

        self.rssi_label = tk.Label(
            rssi_frame,
            text="--- dBm",
            font=("Arial", 14, "bold"),
            bg="#34495e",
            fg="#3498db"
        )
        self.rssi_label.pack(side=tk.LEFT, padx=5)

        self.quality_label = tk.Label(
            rssi_frame,
            text="",
            font=("Arial", 12),
            bg="#34495e",
            fg="white"
        )
        self.quality_label.pack(side=tk.LEFT, padx=10)

        # Stats frame
        stats_frame = tk.Frame(self.root, bg="#ecf0f1")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tk.Label(
            stats_frame,
            text="Statistics",
            font=("Arial", 14, "bold"),
            bg="#ecf0f1"
        ).pack(pady=10)

        # Stats grid
        stats_grid = tk.Frame(stats_frame, bg="#ecf0f1")
        stats_grid.pack(pady=10)

        # PINGs sent
        tk.Label(stats_grid, text="PINGs Sent:", font=("Arial", 12), bg="#ecf0f1").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.pings_sent_label = tk.Label(stats_grid, text="0", font=("Arial", 12, "bold"), bg="#ecf0f1")
        self.pings_sent_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # PONGs received
        tk.Label(stats_grid, text="PONGs Received:", font=("Arial", 12), bg="#ecf0f1").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.pongs_received_label = tk.Label(stats_grid, text="0", font=("Arial", 12, "bold"), bg="#ecf0f1")
        self.pongs_received_label.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # Direct responses
        tk.Label(stats_grid, text="Direct Responses:", font=("Arial", 12), bg="#ecf0f1").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.direct_label = tk.Label(stats_grid, text="0", font=("Arial", 12, "bold"), bg="#ecf0f1", fg="green")
        self.direct_label.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        # Via repeater
        tk.Label(stats_grid, text="Via Repeater:", font=("Arial", 12), bg="#ecf0f1").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.repeater_label = tk.Label(stats_grid, text="0", font=("Arial", 12, "bold"), bg="#ecf0f1", fg="orange")
        self.repeater_label.grid(row=3, column=1, sticky="w", padx=5, pady=5)

        # Average RSSI
        tk.Label(stats_grid, text="Average RSSI:", font=("Arial", 12), bg="#ecf0f1").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.avg_rssi_label = tk.Label(stats_grid, text="--- dBm", font=("Arial", 12, "bold"), bg="#ecf0f1")
        self.avg_rssi_label.grid(row=4, column=1, sticky="w", padx=5, pady=5)

        # Success rate
        tk.Label(stats_grid, text="Success Rate:", font=("Arial", 12), bg="#ecf0f1").grid(row=5, column=0, sticky="e", padx=5, pady=5)
        self.success_rate_label = tk.Label(stats_grid, text="0%", font=("Arial", 12, "bold"), bg="#ecf0f1")
        self.success_rate_label.grid(row=5, column=1, sticky="w", padx=5, pady=5)

        # Log area
        log_frame = tk.Frame(self.root)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tk.Label(log_frame, text="Activity Log", font=("Arial", 12, "bold")).pack()

        self.log_text = tk.Text(log_frame, height=10, font=("Courier", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(self.log_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.log_text.yview)

        # Buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        self.start_button = tk.Button(
            button_frame,
            text="Start Ping Test",
            font=("Arial", 14, "bold"),
            bg="#27ae60",
            fg="white",
            command=self._start_pinging,
            width=15
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(
            button_frame,
            text="Stop Test",
            font=("Arial", 14, "bold"),
            bg="#e74c3c",
            fg="white",
            command=self._stop_pinging,
            width=15,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        tk.Button(
            button_frame,
            text="Quit",
            font=("Arial", 14),
            command=self._quit,
            width=10
        ).pack(side=tk.LEFT, padx=5)

    def _init_lora(self):
        """Initialize LoRa transceiver"""
        try:
            self.transceiver = LoRaTransceiver(
                node_id=LORA_NODE_ID,
                node_type=NodeType.SCANNER,
                frequency=LORA_FREQUENCY,
                tx_power=LORA_TX_POWER
            )
            self._update_status("LoRa initialized. Ready to start ping test.", "green")
            self._log("LoRa transceiver initialized successfully")
        except Exception as e:
            self._update_status(f"LoRa init failed: {e}", "red")
            self._log(f"ERROR: Failed to initialize LoRa: {e}")

    def _start_pinging(self):
        """Start ping test"""
        if not self.transceiver:
            self._log("ERROR: LoRa not initialized yet")
            return

        self.running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self._update_status("Ping test running...", "green")
        self._log("=== Ping test started ===")

        # Start ping thread
        Thread(target=self._ping_loop, daemon=True).start()

        # Start receive thread
        Thread(target=self._receive_loop, daemon=True).start()

    def _stop_pinging(self):
        """Stop ping test"""
        self.running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self._update_status("Ping test stopped", "orange")
        self._log("=== Ping test stopped ===")

    def _ping_loop(self):
        """Send PING packets periodically"""
        sequence = 1

        while self.running:
            try:
                # Create PING packet
                timestamp = int(time.time())
                payload = f"PING|{timestamp}|{sequence}"

                ping_packet = LoRaPacket.create(
                    packet_type=PacketType.CMD,
                    source_node=LORA_NODE_ID,
                    dest_node=1,  # Server
                    payload=payload.encode('utf-8'),
                    sequence_num=self.transceiver.sequence_num
                )

                self.transceiver.sequence_num += 1

                # Send PING
                success = self.transceiver.send_packet(ping_packet, use_ack=False)

                if success:
                    with self.lock:
                        self.pings_sent += 1
                    self._log(f"PING #{sequence} sent to server")
                    self._update_stats()
                else:
                    self._log(f"PING #{sequence} failed to send")

                sequence += 1

                # Wait 2 seconds between pings
                time.sleep(2)

            except Exception as e:
                self._log(f"ERROR in ping loop: {e}")
                time.sleep(2)

    def _receive_loop(self):
        """Receive PONG packets"""
        while self.running:
            try:
                packet = self.transceiver.receive_packet(timeout=1.0)

                if packet is None:
                    continue

                # Check if it's a PONG packet
                if packet.packet_type == PacketType.CMD:
                    payload_str = packet.payload.decode('utf-8', errors='ignore')

                    if payload_str.startswith("PONG|"):
                        # Parse PONG: "PONG|server_timestamp|original_timestamp|server_rssi"
                        parts = payload_str.split('|')
                        if len(parts) >= 3:
                            sender_node = packet.sender_node
                            source_node = packet.source_node

                            # Get RSSI of received PONG
                            rssi = self.transceiver.rfm9x.last_rssi if self.transceiver.rfm9x else -999

                            # Record statistics
                            with self.lock:
                                self.pongs_received += 1
                                self.rssi_values.append(rssi)

                                # Keep only last 20 RSSI values
                                if len(self.rssi_values) > 20:
                                    self.rssi_values.pop(0)

                                # Check if via repeater
                                if sender_node != source_node:
                                    self.via_repeater_count += 1
                                    route = f"via Repeater {sender_node}"
                                else:
                                    self.direct_count += 1
                                    route = "direct"

                            self._log(f"PONG received from server ({route}) - RSSI: {rssi} dBm")
                            self._update_rssi(rssi)
                            self._update_stats()

            except Exception as e:
                self._log(f"ERROR in receive loop: {e}")
                time.sleep(0.5)

    def _update_rssi(self, rssi: int):
        """Update RSSI display"""
        self.rssi_label.config(text=f"{rssi} dBm")

        # Signal quality assessment
        if rssi >= -70:
            quality = "EXCELLENT"
            color = "#27ae60"
        elif rssi >= -85:
            quality = "GOOD"
            color = "#2ecc71"
        elif rssi >= -100:
            quality = "FAIR"
            color = "#f39c12"
        else:
            quality = "POOR"
            color = "#e74c3c"

        self.rssi_label.config(fg=color)
        self.quality_label.config(text=f"({quality})", fg=color)

    def _update_stats(self):
        """Update statistics display"""
        with self.lock:
            self.pings_sent_label.config(text=str(self.pings_sent))
            self.pongs_received_label.config(text=str(self.pongs_received))
            self.direct_label.config(text=str(self.direct_count))
            self.repeater_label.config(text=str(self.via_repeater_count))

            # Success rate
            if self.pings_sent > 0:
                success_rate = (self.pongs_received / self.pings_sent) * 100
                self.success_rate_label.config(text=f"{success_rate:.1f}%")

            # Average RSSI
            if self.rssi_values:
                avg_rssi = sum(self.rssi_values) / len(self.rssi_values)
                self.avg_rssi_label.config(text=f"{avg_rssi:.1f} dBm")

    def _update_status(self, message: str, color: str):
        """Update status label"""
        self.status_label.config(text=message, fg=color)

    def _log(self, message: str):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

    def _quit(self):
        """Quit application"""
        self.running = False
        time.sleep(0.5)
        self.root.destroy()


def main():
    """Main entry point"""

    # Validate node ID is in scanner range
    if LORA_NODE_ID < 100 or LORA_NODE_ID > 199:
        print(f"ERROR: Scanner node ID must be 100-199, got {LORA_NODE_ID}")
        return

    print(f"Starting LoRa Ping Test - Scanner {LORA_NODE_ID}")

    if LOCAL_MODE:
        print("WARNING: Running in LOCAL mode (no hardware)")

    root = tk.Tk()
    app = PingScannerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
