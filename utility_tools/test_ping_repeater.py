#!/usr/bin/env python3
"""
LoRa Ping-Pong Test - Repeater Side

Forwards PING/PONG packets and displays all info on OLED.
Display stays on during test (no auto-off).

Usage:
    LORA_NODE_ID=200 python3 test_ping_repeater.py
"""

import time
import logging
from dotenv import load_dotenv

load_dotenv()

from lora import LoRaTransceiver, LoRaPacket, PacketType, NodeType, CollisionAvoidance
from utils.config import LORA_NODE_ID, LORA_FREQUENCY, LORA_TX_POWER, LORA_ENABLE_CA
from utils.oled_display import OLEDDisplay

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Statistics
class PingRepeaterStats:
    def __init__(self):
        self.pings_forwarded = 0
        self.pongs_forwarded = 0
        self.total_forwarded = 0
        self.dropped = 0
        self.rssi_values = []  # Last 10 RSSI values

    def record_forward(self, packet_type: str, rssi: int):
        if packet_type == "PING":
            self.pings_forwarded += 1
        elif packet_type == "PONG":
            self.pongs_forwarded += 1

        self.total_forwarded += 1
        self.rssi_values.append(rssi)

        # Keep only last 10
        if len(self.rssi_values) > 10:
            self.rssi_values.pop(0)

    def get_avg_rssi(self) -> float:
        if not self.rssi_values:
            return 0.0
        return sum(self.rssi_values) / len(self.rssi_values)


def update_oled_test_display(oled: OLEDDisplay, stats: PingRepeaterStats,
                              last_packet_type: str = None,
                              last_src: int = None,
                              last_dst: int = None,
                              last_rssi: int = None):
    """
    Update OLED with ping test information

    Layout:
    ┌────────────────────────────┐
    │ PING TEST                  │  ← Header
    │────────────────────────────│
    │ Last: PING 102→1           │  ← Last packet
    │ RSSI: -65 dBm (GOOD)       │  ← Signal strength
    │ ──────────────────────────│
    │ PING→: 15  PONG←: 14       │  ← Counters
    │ Total: 29  Drop: 0         │
    │ Avg RSSI: -68 dBm          │  ← Average
    └────────────────────────────┘
    """

    if not oled.display:
        return

    with oled.lock:
        oled._turn_on()
        oled._clear()

        # Header
        oled.draw.text((5, 2), "PING TEST", font=oled.font, fill=255)
        oled.draw.rectangle((0, 14, oled.width, 16), outline=255, fill=255)

        # Last packet info
        if last_packet_type and last_src and last_dst:
            if last_packet_type == "PING":
                packet_str = f"Last: PING {last_src}->{last_dst}"
            else:
                packet_str = f"Last: PONG {last_src}->{last_dst}"
            oled.draw.text((5, 18), packet_str, font=oled.font, fill=255)

        # RSSI with quality
        if last_rssi is not None:
            # Determine quality
            if last_rssi >= -70:
                quality = "EXCE"  # Abbreviated for space
            elif last_rssi >= -85:
                quality = "GOOD"
            elif last_rssi >= -100:
                quality = "FAIR"
            else:
                quality = "POOR"

            rssi_str = f"RSSI:{last_rssi}dBm ({quality})"
            oled.draw.text((5, 28), rssi_str, font=oled.font, fill=255)

        # Separator
        oled.draw.rectangle((0, 38, oled.width, 39), outline=255, fill=255)

        # Statistics line 1: PING and PONG counts
        stats_line1 = f"PING>:{stats.pings_forwarded:>2} PONG<:{stats.pongs_forwarded:>2}"
        oled.draw.text((5, 41), stats_line1, font=oled.font, fill=255)

        # Statistics line 2: Total and dropped
        stats_line2 = f"Tot:{stats.total_forwarded:>3} Drop:{stats.dropped:>2}"
        oled.draw.text((5, 50), stats_line2, font=oled.font, fill=255)

        # Average RSSI
        avg_rssi = stats.get_avg_rssi()
        if avg_rssi != 0:
            avg_str = f"Avg:{avg_rssi:>4.0f}dBm"
            oled.draw.text((5, 56), avg_str, font=oled.font, fill=255)

        oled._update()


def main():
    """Main repeater loop"""

    # Validate node ID is in repeater range
    if LORA_NODE_ID < 200 or LORA_NODE_ID > 256:
        print(f"ERROR: Invalid repeater node ID: {LORA_NODE_ID}. Must be 200-256.")
        return

    print("="*60)
    print(f"LoRa PING-PONG TEST - REPEATER {LORA_NODE_ID}")
    print("="*60)
    print(f"Frequency:  {LORA_FREQUENCY} MHz")
    print(f"TX Power:   {LORA_TX_POWER} dBm")
    print(f"Collision Avoidance: {'ENABLED' if LORA_ENABLE_CA else 'DISABLED'}")
    print("="*60)
    print("\nInitializing OLED display...")

    # Initialize OLED (no auto-off for testing)
    oled = OLEDDisplay(auto_off_seconds=0)

    if not oled.display:
        print("WARNING: OLED display not available (LOCAL mode or missing hardware)")
        print("Continuing with console output only...\n")
    else:
        print("OLED display initialized\n")

    # Show startup on OLED
    if oled.display:
        oled._clear()
        oled.draw.text((15, 15), "PING TEST", font=oled.font, fill=255)
        oled.draw.text((10, 30), f"Repeater {LORA_NODE_ID}", font=oled.font, fill=255)
        oled.draw.text((20, 45), "Starting...", font=oled.font, fill=255)
        oled._update()
        time.sleep(2)

    print("Initializing LoRa transceiver...")

    # Initialize transceiver
    transceiver = LoRaTransceiver(
        node_id=LORA_NODE_ID,
        node_type=NodeType.REPEATER,
        frequency=LORA_FREQUENCY,
        tx_power=LORA_TX_POWER
    )

    stats = PingRepeaterStats()

    # Initial display
    if oled.display:
        update_oled_test_display(oled, stats)

    print("Repeater ready, listening for PING/PONG packets...")
    print("Press Ctrl+C to stop\n")

    # Track last packet for display
    last_packet_type = None
    last_src = None
    last_dst = None
    last_rssi = None

    try:
        while True:
            # Receive packet
            packet = transceiver.receive_packet(timeout=1.0)

            if packet is None:
                time.sleep(0.1)
                continue

            # Check if it's a CMD packet (PING or PONG)
            if packet.packet_type == PacketType.CMD:
                payload_str = packet.payload.decode('utf-8', errors='ignore')

                # Check for PING or PONG
                if payload_str.startswith("PING|") or payload_str.startswith("PONG|"):
                    packet_type = "PING" if payload_str.startswith("PING|") else "PONG"

                    # Check if should process
                    should_process, reason = packet.should_process(
                        LORA_NODE_ID,
                        NodeType.REPEATER,
                        transceiver.seen_packets
                    )

                    if not should_process:
                        if reason == "duplicate":
                            logging.debug(f"Dropped duplicate {packet_type}: {packet}")
                        stats.dropped += 1
                        continue

                    # Get RSSI
                    rssi = transceiver.rfm9x.last_rssi if transceiver.rfm9x else -999

                    # Mark as seen
                    packet_id = (packet.source_node, packet.sequence_num)
                    transceiver.seen_packets.add(packet_id)

                    # Prevent unbounded growth
                    if len(transceiver.seen_packets) > transceiver.max_seen:
                        transceiver.seen_packets = set(list(transceiver.seen_packets)[500:])

                    # Create repeated packet
                    repeated_packet = packet.create_repeat(LORA_NODE_ID)

                    # Record stats
                    stats.record_forward(packet_type, rssi)

                    # Update display variables
                    last_packet_type = packet_type
                    last_src = packet.source_node
                    last_dst = packet.dest_node
                    last_rssi = rssi

                    # Log
                    route_info = f"{packet.source_node} → {packet.dest_node}"
                    print(f"{packet_type} forwarding: {route_info} (RSSI: {rssi} dBm, TTL: {packet.ttl})")

                    # Update OLED
                    if oled.display:
                        update_oled_test_display(
                            oled, stats,
                            last_packet_type, last_src, last_dst, last_rssi
                        )

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
                            success = transceiver.send_packet(repeated_packet, use_ack=False)

                        if success:
                            logging.debug(f"Successfully forwarded {packet_type}")
                        else:
                            print(f"WARNING: Failed to forward {packet_type}")

                    except Exception as e:
                        logging.error(f"Error forwarding {packet_type}: {e}")

            # Brief delay
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nRepeater shutting down...")
        print(f"\nFinal Statistics:")
        print(f"  PINGs forwarded:  {stats.pings_forwarded}")
        print(f"  PONGs forwarded:  {stats.pongs_forwarded}")
        print(f"  Total forwarded:  {stats.total_forwarded}")
        print(f"  Dropped:          {stats.dropped}")
        print(f"  Avg RSSI:         {stats.get_avg_rssi():.1f} dBm")

        # Show shutdown on OLED
        if oled.display:
            oled._clear()
            oled.draw.text((15, 20), "Test Complete", font=oled.font, fill=255)
            oled.draw.text((5, 35), f"Fwd: {stats.total_forwarded}", font=oled.font, fill=255)
            oled.draw.text((5, 50), "Shutting down", font=oled.font, fill=255)
            oled._update()
            time.sleep(2)
            oled._turn_off()

        print("\nRepeater stopped\n")

    except Exception as e:
        logging.error(f"Fatal error in repeater: {e}")
        if oled.display:
            oled.show_error(f"Fatal: {str(e)[:20]}")
            time.sleep(5)
        raise


if __name__ == "__main__":
    main()
