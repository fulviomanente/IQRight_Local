#!/usr/bin/env python3
"""
LoRa Test Replicator - Using refactored single-receiver architecture
Runs on the replicator to forward packets between nodes
"""

import time
import busio
import board
import digitalio
import adafruit_rfm9x
from meshstatic_new import ReplicatorNode
import logging
import logging.handlers
import os
import sys

# Configuration
RFM9X_FREQUENCE = 915.23  # MHz
RFM9X_TX_POWER = 23
RFM9X_NODE = 50  # Replicator node ID
RFM9X_ACK_DELAY = 0.1
RFM9X_TIMEOUT = 5.0


# Logging setup
log_filename = "lora_test_replicator_new.log"
max_log_size = 10 * 1024 * 1024  # 10MB
backup_count = 5
debug = True

def setup_logging():
    """Setup logging configuration"""
    handler = logging.handlers.RotatingFileHandler(
        log_filename,
        maxBytes=max_log_size,
        backupCount=backup_count
    )
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(log_formatter)
    logging.getLogger().addHandler(handler)

    # Also log to console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    logging.getLogger().addHandler(console_handler)

    logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)

def setup_lora():
    """Initialize LoRa radio module"""
    try:
        # Configure LoRa Radio
        CS = digitalio.DigitalInOut(board.CE1)
        RESET = digitalio.DigitalInOut(board.D25)
        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

        rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, RFM9X_FREQUENCE)
        rfm9x.tx_power = RFM9X_TX_POWER
        rfm9x.node = RFM9X_NODE
        rfm9x.ack_delay = RFM9X_ACK_DELAY
        rfm9x.signal_bandwidth = 125000
        rfm9x.coding_rate = 5
        rfm9x.preamble_length = 8
        rfm9x.sync_word = 0x12
        rfm9x.enable_crc = True

        logging.info("LoRa module initialized successfully")
        logging.info(f"Frequency: {RFM9X_FREQUENCE} MHz")
        logging.info(f"TX Power: {RFM9X_TX_POWER} dB")
        logging.info(f"Node ID: {RFM9X_NODE}")

        return rfm9x
    except Exception as e:
        logging.error(f"Failed to initialize LoRa module: {e}")
        sys.exit(1)

def main():
    """Main replicator loop"""
    setup_logging()
    logging.info("=" * 50)
    logging.info("LoRa Replicator (NEW) Starting")
    logging.info("=" * 50)

    # Check if running on Raspberry Pi
    if os.environ.get("LOCAL") == 'TRUE':
        logging.error("This script must run on Raspberry Pi with LoRa hardware")
        sys.exit(1)

    rfm9x = setup_lora()
    # Use ReplicatorNode which has forwarding enabled
    node = ReplicatorNode(rfm9x, node_id=RFM9X_NODE, auto_start=True)

    # hook to process messages
    def on_msg(pkt, rssi):
        print(f"[REPLICATOR] got {pkt['type']} from {pkt['src']} seq={pkt['seq']} rssi={rssi} payload={pkt['payload']}")
        logging.info(f"[REPLICATOR] got {pkt['type']} from {pkt['src']} seq={pkt['seq']} rssi={rssi} payload={pkt['payload']}")

    node.on_message = on_msg

    # hook to track forwarded packets
    def on_fwd(pkt, rssi):
        print(f"[REPLICATOR] forwarding {pkt['type']} from {pkt['src']} to {pkt['dst']} seq={pkt['seq']}")
        logging.info(f"[REPLICATOR] forwarding {pkt['type']} from {pkt['src']} to {pkt['dst']} seq={pkt['seq']}")

    node.on_forward = on_fwd

    # Ensure the receiver is running
    if not node._running:
        logging.error("Receiver thread failed to start!")
    else:
        logging.info("Receiver thread is running")

    start_time = time.time()

    print("\n" + "=" * 60)
    print("LoRa Test Replicator (NEW) - Single Receiver Architecture")
    print("Waiting for packets to forward...")
    print("=" * 60)
    print(f"{'Timestamp':<23} {'RSSI':<6} {'SNR':<6} {'Payload'}")
    print("-" * 60)

    try:
        # The node's receiver thread is already running and handling all packets
        # including forwarding logic. We just need to keep the main thread alive
        while True:
            time.sleep(1)
            # Could add periodic status updates here if desired

    except KeyboardInterrupt:
        print("\n\nReplicator stopped by user")
        elapsed = time.time() - start_time
        node.stop_receiver()  # Clean shutdown of receiver thread
        logging.info("Replicator shutdown")
    except Exception as e:
        logging.error(f"Replicator error: {e}")
        node.stop_receiver()
        raise

if __name__ == "__main__":
    main()