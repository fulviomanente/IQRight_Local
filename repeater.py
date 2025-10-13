#!/usr/bin/env python3
"""
LoRa Repeater Application

A battery/solar-powered repeater node that forwards packets between scanner and server
to extend network range. Runs on Raspberry Pi Zero.

Node ID Range: 200-256
Functionality:
- Receives packets from any node
- Validates packet integrity (CRC)
- Checks if packet should be forwarded (TTL, duplicates)
- Updates sender field and decrements TTL
- Forwards packet with collision avoidance

Usage:
    python repeater.py

    Set LORA_NODE_ID environment variable to unique repeater ID (200-256):
    LORA_NODE_ID=200 python repeater.py
"""

import logging
import logging.handlers
import time
from dotenv import load_dotenv

load_dotenv()

# Import enhanced LoRa packet handler
from lora import LoRaTransceiver, LoRaPacket, PacketType, NodeType, CollisionAvoidance
from utils.config import (
    LORA_NODE_ID, LORA_FREQUENCY, LORA_TX_POWER, LORA_TTL, LORA_ENABLE_CA,
    LOG_FILENAME, MAX_LOG_SIZE, BACKUP_COUNT, DEBUG, HOME_DIR
)
from utils.oled_display import get_oled_display

# Logging setup
try:
    handler = logging.handlers.RotatingFileHandler(
        f'{HOME_DIR}/log/repeater_{LORA_NODE_ID}.log',
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT
    )
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(log_formatter)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG if DEBUG else logging.INFO)
except Exception as e:
    print(f'Error creating log object: {e}')

# Statistics tracking
class RepeaterStats:
    def __init__(self):
        self.packets_received = 0
        self.packets_forwarded = 0
        self.packets_dropped_ttl = 0
        self.packets_dropped_duplicate = 0
        self.packets_dropped_crc = 0
        self.start_time = time.time()

    def log_stats(self):
        """Log statistics periodically"""
        uptime = time.time() - self.start_time
        logging.info(f"=== Repeater Stats (Uptime: {uptime/3600:.1f}h) ===")
        logging.info(f"Received: {self.packets_received}")
        logging.info(f"Forwarded: {self.packets_forwarded}")
        logging.info(f"Dropped (TTL): {self.packets_dropped_ttl}")
        logging.info(f"Dropped (Duplicate): {self.packets_dropped_duplicate}")
        logging.info(f"Dropped (CRC): {self.packets_dropped_crc}")
        logging.info(f"Forward Rate: {self.packets_forwarded/max(self.packets_received, 1)*100:.1f}%")


def main():
    """Main repeater loop"""

    # Initialize OLED display (auto-off after 30s of inactivity)
    oled = get_oled_display(auto_off_seconds=30)

    # Validate node ID is in repeater range
    if LORA_NODE_ID < 200 or LORA_NODE_ID > 256:
        logging.error(f"Invalid repeater node ID: {LORA_NODE_ID}. Must be 200-256.")
        print(f"ERROR: Repeater node ID must be 200-256, got {LORA_NODE_ID}")
        oled.show_error(f"Invalid Node ID: {LORA_NODE_ID}")
        return

    logging.info(f"Starting LoRa Repeater Node {LORA_NODE_ID}")
    logging.info(f"Frequency: {LORA_FREQUENCY}MHz, TX Power: {LORA_TX_POWER}dBm")
    logging.info(f"Collision Avoidance: {'ENABLED' if LORA_ENABLE_CA else 'DISABLED'}")

    # Show startup on OLED
    oled.show_startup()

    # Initialize transceiver
    transceiver = LoRaTransceiver(
        node_id=LORA_NODE_ID,
        node_type=NodeType.REPEATER,
        frequency=LORA_FREQUENCY,
        tx_power=LORA_TX_POWER
    )

    stats = RepeaterStats()
    last_stats_time = time.time()
    last_oled_update = time.time()
    STATS_INTERVAL = 300  # Log stats every 5 minutes
    OLED_STATS_INTERVAL = 60  # Update OLED stats every 60 seconds

    logging.info("Repeater ready, listening for packets...")

    # Show ready status on OLED
    time.sleep(2)  # Wait for startup message to display
    oled.show_ready(LORA_NODE_ID, device_type="Repeater")

    try:
        while True:
            # Receive packet
            packet = transceiver.receive_packet(timeout=1.0)

            if packet is None:
                # No packet received, continue
                time.sleep(0.1)

                # Periodically log stats
                if time.time() - last_stats_time > STATS_INTERVAL:
                    stats.log_stats()
                    last_stats_time = time.time()

                # Periodically update OLED stats
                if time.time() - last_oled_update > OLED_STATS_INTERVAL:
                    try:
                        total_dropped = (stats.packets_dropped_ttl +
                                       stats.packets_dropped_duplicate +
                                       stats.packets_dropped_crc)
                        oled.show_repeater_stats(
                            stats.packets_received,
                            stats.packets_forwarded,
                            total_dropped
                        )
                        last_oled_update = time.time()
                    except Exception as e:
                        logging.error(f"Failed to update OLED: {e}")

                # Check OLED auto-off
                try:
                    oled.update()
                except Exception:
                    pass

                continue

            stats.packets_received += 1

            # Check if packet should be processed
            should_process, reason = packet.should_process(
                LORA_NODE_ID,
                NodeType.REPEATER,
                transceiver.seen_packets
            )

            if not should_process:
                if reason == "duplicate":
                    stats.packets_dropped_duplicate += 1
                    logging.debug(f"Dropped duplicate packet: {packet}")
                elif reason == "ttl_expired":
                    stats.packets_dropped_ttl += 1
                    logging.debug(f"Dropped TTL expired packet: {packet}")
                elif reason == "own_packet_looped":
                    logging.warning(f"Detected own packet loop: {packet}")
                else:
                    logging.debug(f"Dropped packet ({reason}): {packet}")
                continue

            # Mark as seen to prevent re-forwarding
            packet_id = (packet.source_node, packet.sequence_num)
            transceiver.seen_packets.add(packet_id)

            # Prevent unbounded growth
            if len(transceiver.seen_packets) > transceiver.max_seen:
                transceiver.seen_packets = set(list(transceiver.seen_packets)[500:])

            # Special handling for HELLO packets: clear cache for source node
            if packet.packet_type == PacketType.HELLO:
                source_id = packet.source_node
                transceiver.seen_packets = {
                    (src, seq) for src, seq in transceiver.seen_packets
                    if src != source_id
                }
                logging.info(f"HELLO from node {source_id}: cleared sequence cache before forwarding")

            # Create repeated packet with updated sender and TTL
            repeated_packet = packet.create_repeat(LORA_NODE_ID)

            logging.info(f"Forwarding packet: {repeated_packet}")

            # Show forwarding on OLED (brief)
            try:
                oled.show_packet_forwarded(packet.source_node, packet.dest_node)
            except Exception:
                pass

            # Forward with collision avoidance
            try:
                if LORA_ENABLE_CA and transceiver.rfm9x:
                    data = repeated_packet.serialize()
                    success = CollisionAvoidance.send_with_ca(
                        transceiver.rfm9x,
                        data,
                        max_retries=3,
                        enable_rx_guard=True,
                        enable_random_delay=True
                    )
                else:
                    # Use ACK only for DATA packets, not for repeater forwarding
                    # (reduces overhead)
                    success = transceiver.send_packet(repeated_packet, use_ack=False)

                if success:
                    stats.packets_forwarded += 1
                    logging.debug(f"Successfully forwarded packet")
                else:
                    logging.warning(f"Failed to forward packet: {repeated_packet}")

            except Exception as e:
                logging.error(f"Error forwarding packet: {e}")

            # Brief delay to prevent tight loop
            time.sleep(0.05)

    except KeyboardInterrupt:
        logging.info("Repeater shutting down...")
        stats.log_stats()
        try:
            oled.shutdown()
        except Exception as e:
            logging.error(f"Error shutting down OLED: {e}")
        print("\nRepeater stopped")

    except Exception as e:
        logging.error(f"Fatal error in repeater: {e}")
        stats.log_stats()
        try:
            oled.show_error(f"Fatal error: {str(e)[:20]}")
            time.sleep(5)
            oled.shutdown()
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
