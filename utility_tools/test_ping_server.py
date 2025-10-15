#!/usr/bin/env python3
"""
LoRa Ping-Pong Test - Server Side

Listens for PING packets from scanners/repeaters and responds with PONG.
Displays RSSI values to help determine optimal repeater placement.

Usage:
    python3 test_ping_server.py
"""

import time
import logging
from dotenv import load_dotenv

load_dotenv()

from lora import LoRaTransceiver, LoRaPacket, PacketType, NodeType
from utils.config import LORA_NODE_ID, LORA_FREQUENCY, LORA_TX_POWER

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Statistics
class PingStats:
    def __init__(self):
        self.pings_received = {}  # {node_id: count}
        self.pongs_sent = {}      # {node_id: count}
        self.rssi_values = {}     # {node_id: [rssi_values]}

    def record_ping(self, node_id: int, rssi: int):
        if node_id not in self.pings_received:
            self.pings_received[node_id] = 0
            self.rssi_values[node_id] = []

        self.pings_received[node_id] += 1
        self.rssi_values[node_id].append(rssi)

        # Keep only last 10 RSSI values
        if len(self.rssi_values[node_id]) > 10:
            self.rssi_values[node_id].pop(0)

    def record_pong(self, node_id: int):
        if node_id not in self.pongs_sent:
            self.pongs_sent[node_id] = 0
        self.pongs_sent[node_id] += 1

    def get_avg_rssi(self, node_id: int) -> float:
        if node_id not in self.rssi_values or not self.rssi_values[node_id]:
            return 0.0
        return sum(self.rssi_values[node_id]) / len(self.rssi_values[node_id])

    def print_stats(self):
        print("\n" + "="*60)
        print("PING-PONG SERVER STATISTICS")
        print("="*60)

        for node_id in sorted(self.pings_received.keys()):
            pings = self.pings_received.get(node_id, 0)
            pongs = self.pongs_sent.get(node_id, 0)
            avg_rssi = self.get_avg_rssi(node_id)
            last_rssi = self.rssi_values[node_id][-1] if self.rssi_values.get(node_id) else 0

            # Determine node type
            if 100 <= node_id <= 199:
                node_type = "Scanner"
            elif 200 <= node_id <= 256:
                node_type = "Repeater"
            else:
                node_type = "Unknown"

            # Signal quality assessment
            if avg_rssi >= -70:
                quality = "EXCELLENT"
            elif avg_rssi >= -85:
                quality = "GOOD"
            elif avg_rssi >= -100:
                quality = "FAIR"
            else:
                quality = "POOR"

            print(f"\nNode {node_id} ({node_type}):")
            print(f"  PINGs received: {pings}")
            print(f"  PONGs sent:     {pongs}")
            print(f"  Last RSSI:      {last_rssi} dBm")
            print(f"  Avg RSSI:       {avg_rssi:.1f} dBm ({quality})")

        print("="*60 + "\n")


def main():
    """Main server loop"""

    # Validate this is server node
    if LORA_NODE_ID != 1:
        print(f"ERROR: This script must run on server (node 1), current: {LORA_NODE_ID}")
        return

    print("="*60)
    print("LoRa PING-PONG TEST - SERVER")
    print("="*60)
    print(f"Node ID:    {LORA_NODE_ID}")
    print(f"Frequency:  {LORA_FREQUENCY} MHz")
    print(f"TX Power:   {LORA_TX_POWER} dBm")
    print("="*60)
    print("\nListening for PING packets...")
    print("Press Ctrl+C to stop and show statistics\n")

    # Initialize transceiver
    transceiver = LoRaTransceiver(
        node_id=LORA_NODE_ID,
        node_type=NodeType.SERVER,
        frequency=LORA_FREQUENCY,
        tx_power=LORA_TX_POWER
    )

    stats = PingStats()
    last_stats_print = time.time()

    try:
        while True:
            # Receive packet
            packet = transceiver.receive_packet(timeout=1.0)

            if packet is None:
                # Print stats every 10 seconds
                if time.time() - last_stats_print > 10:
                    stats.print_stats()
                    last_stats_print = time.time()
                continue

            # Check if it's a PING packet
            if packet.packet_type == PacketType.CMD:
                payload_str = packet.payload.decode('utf-8', errors='ignore')

                if payload_str.startswith("PING|"):
                    # Parse PING payload: "PING|timestamp|sequence"
                    parts = payload_str.split('|')
                    if len(parts) >= 3:
                        original_timestamp = parts[1]
                        sequence = parts[2]
                        source_node = packet.source_node
                        sender_node = packet.sender_node

                        # Get RSSI (if available)
                        rssi = transceiver.rfm9x.last_rssi if transceiver.rfm9x else -999

                        # Record statistics
                        stats.record_ping(source_node, rssi)

                        # Determine if packet came via repeater
                        via_repeater = (sender_node != source_node)
                        route = f"via Repeater {sender_node}" if via_repeater else "direct"

                        print(f"PING #{sequence} from Node {source_node} ({route})")
                        print(f"  RSSI: {rssi} dBm | TTL: {packet.ttl} | Timestamp: {original_timestamp}")

                        # Send PONG response
                        pong_payload = f"PONG|{int(time.time())}|{original_timestamp}|{rssi}"
                        pong_packet = LoRaPacket.create(
                            packet_type=PacketType.CMD,
                            source_node=LORA_NODE_ID,
                            dest_node=source_node,
                            payload=pong_payload.encode('utf-8'),
                            sequence_num=transceiver.sequence_num
                        )

                        transceiver.sequence_num += 1

                        # Send PONG
                        success = transceiver.send_packet(pong_packet, use_ack=False)

                        if success:
                            stats.record_pong(source_node)
                            print(f"  → PONG sent to Node {source_node}\n")
                        else:
                            print(f"  → PONG failed to Node {source_node}\n")

    except KeyboardInterrupt:
        print("\n\nStopping server...")
        stats.print_stats()
        print("Server stopped\n")


if __name__ == "__main__":
    main()
