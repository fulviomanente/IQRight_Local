"""
LoRa Packet Handler

Handles binary packet serialization/deserialization, CRC validation,
multi-packet sequences, and transceiver operations with hardware initialization.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import struct
import time
import logging
import os

from lora.node_types import PacketType, PacketFlags, MultiPartFlags, NodeType


@dataclass
class LoRaPacket:
    """Enhanced LoRa packet with collision avoidance, repeater, and multi-packet support"""

    # Header fields
    packet_type: PacketType
    flags: int
    multi_flags: int
    source_node: int
    dest_node: int
    sender_node: int
    sequence_num: int
    ttl: int
    multi_part_index: int
    multi_part_total: int
    timestamp: int
    payload: bytes

    # Constants
    MAGIC = 0x4951  # "IQ" in hex
    VERSION = 1
    HEADER_SIZE = 22  # Updated to match actual struct size
    CRC_SIZE = 2
    MAX_PAYLOAD = 229  # 253 - 22 - 2

    @property
    def is_repeat(self) -> bool:
        """Check if packet has IS_REPEAT flag set"""
        return bool(self.flags & PacketFlags.IS_REPEAT)

    @classmethod
    def create(cls,
               packet_type: PacketType,
               source_node: int,
               dest_node: int,
               payload: bytes,
               sequence_num: int,
               ttl: int = 3,
               flags: int = 0,
               multi_flags: int = MultiPartFlags.ONLY,
               multi_part_index: int = 0,
               multi_part_total: int = 0) -> 'LoRaPacket':
        """Factory method to create a new packet"""
        return cls(
            packet_type=packet_type,
            flags=flags,
            multi_flags=multi_flags,
            source_node=source_node,
            dest_node=dest_node,
            sender_node=source_node,  # Initially same as source
            sequence_num=sequence_num,
            ttl=ttl,
            multi_part_index=multi_part_index,
            multi_part_total=multi_part_total,
            timestamp=int(time.time()),
            payload=payload[:cls.MAX_PAYLOAD]  # Truncate if needed
        )

    def serialize(self) -> bytes:
        """Convert packet to bytes for transmission"""
        # Pack header (20 bytes total)
        header = struct.pack(
            '>HBBBBHHHHBBBBI',  # Big-endian format (14 fields, 20 bytes)
            self.MAGIC,              # 2 bytes - H
            self.VERSION,            # 1 byte  - B
            self.packet_type,        # 1 byte  - B
            self.flags,              # 1 byte  - B
            self.multi_flags,        # 1 byte  - B
            self.source_node,        # 2 bytes - H
            self.dest_node,          # 2 bytes - H
            self.sender_node,        # 2 bytes - H
            self.sequence_num,       # 2 bytes - H
            self.ttl,                # 1 byte  - B
            len(self.payload),       # 1 byte  - B
            self.multi_part_index,   # 1 byte  - B (0-255)
            self.multi_part_total,   # 1 byte  - B (0-255)
            self.timestamp           # 4 bytes - I
        )

        # Calculate CRC
        data = header + self.payload
        crc = self._calculate_crc16(data)

        return data + struct.pack('>H', crc)

    @classmethod
    def deserialize(cls, data: bytes) -> Optional['LoRaPacket']:
        """Parse bytes into LoRaPacket object"""
        if len(data) < cls.HEADER_SIZE + cls.CRC_SIZE:
            logging.warning(f"Packet too short: {len(data)} bytes")
            return None

        # Extract and validate CRC
        packet_data = data[:-cls.CRC_SIZE]
        received_crc = struct.unpack('>H', data[-cls.CRC_SIZE:])[0]
        calculated_crc = cls._calculate_crc16(packet_data)

        if received_crc != calculated_crc:
            logging.error(f"CRC mismatch: received=0x{received_crc:04X}, calculated=0x{calculated_crc:04X}")
            return None

        # Unpack header
        try:
            header_data = struct.unpack('>HBBBBHHHHBBBBI', data[:cls.HEADER_SIZE])
            (magic, version, pkt_type, flags, multi_flags,
             src, dst, sender, seq, ttl, payload_len,
             multi_idx, multi_total, timestamp) = header_data
        except struct.error as e:
            logging.error(f"Failed to unpack header: {e}")
            return None

        # Validate magic number
        if magic != cls.MAGIC:
            logging.error(f"Invalid magic: 0x{magic:04X}, expected 0x{cls.MAGIC:04X}")
            return None

        # Validate version
        if version != cls.VERSION:
            logging.warning(f"Version mismatch: {version}, expected {cls.VERSION}")

        # Extract payload
        payload = data[cls.HEADER_SIZE:cls.HEADER_SIZE + payload_len]

        return cls(
            packet_type=PacketType(pkt_type),
            flags=flags,
            multi_flags=multi_flags,
            source_node=src,
            dest_node=dst,
            sender_node=sender,
            sequence_num=seq,
            ttl=ttl,
            multi_part_index=multi_idx,
            multi_part_total=multi_total,
            timestamp=timestamp,
            payload=payload
        )

    def should_process(self, my_node_id: int, node_type: NodeType,
                      seen_packets: set) -> Tuple[bool, str]:
        """
        Determine if this packet should be processed

        Returns: (should_process, reason)
        """
        packet_id = (self.source_node, self.sequence_num)

        # Check for duplicate (already seen)
        if packet_id in seen_packets:
            return False, "duplicate"

        # Check if packet originated from self (loop detection)
        if self.source_node == my_node_id:
            return False, "own_packet_looped"

        # Check if we just forwarded this packet (sender is us)
        # This prevents re-forwarding packets we already repeated
        if self.sender_node == my_node_id and node_type == NodeType.REPEATER:
            return False, "own_packet_looped"

        # Check TTL expired
        if self.ttl == 0:
            return False, "ttl_expired"

        # Check if addressed to this node or broadcast
        if self.dest_node not in (my_node_id, 0):
            # Not for us, but repeaters should forward
            if node_type == NodeType.REPEATER:
                return True, "forward"
            return False, "not_for_me"

        return True, "valid"

    def create_repeat(self, repeater_node_id: int) -> 'LoRaPacket':
        """Create a new packet for repeating with updated sender and TTL"""
        return LoRaPacket(
            packet_type=self.packet_type,
            flags=self.flags | PacketFlags.IS_REPEAT,
            multi_flags=self.multi_flags,
            source_node=self.source_node,  # Keep original source
            dest_node=self.dest_node,
            sender_node=repeater_node_id,  # Update to repeater's ID
            sequence_num=self.sequence_num,
            ttl=self.ttl - 1,  # Decrement TTL
            multi_part_index=self.multi_part_index,
            multi_part_total=self.multi_part_total,
            timestamp=self.timestamp,  # Keep original timestamp
            payload=self.payload
        )

    @staticmethod
    def _calculate_crc16(data: bytes) -> int:
        """Calculate CRC16-CCITT checksum"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc = crc << 1
                crc &= 0xFFFF
        return crc

    def get_age_ms(self) -> int:
        """Get packet age in milliseconds"""
        return int((time.time() - self.timestamp) * 1000)

    def is_multi_part(self) -> bool:
        """Check if this is part of a multi-packet sequence"""
        return self.multi_flags != MultiPartFlags.ONLY

    def __str__(self) -> str:
        """String representation for logging"""
        multi_str = ""
        if self.is_multi_part():
            multi_str = f" [{self.multi_part_index}/{self.multi_part_total}]"

        return (f"LoRaPacket(type={self.packet_type.name}, "
                f"src={self.source_node}, dst={self.dest_node}, "
                f"seq={self.sequence_num}, ttl={self.ttl}{multi_str}, "
                f"age={self.get_age_ms()}ms)")


class LoRaTransceiver:
    """
    High-level interface for sending/receiving LoRa packets

    Centralizes hardware initialization and provides clean API for packet operations.
    """

    def __init__(self, node_id: int, node_type: NodeType,
                 frequency: float = 915.0, tx_power: int = 23):
        """
        Initialize LoRa transceiver with hardware setup

        Args:
            node_id: This node's ID (1=server, 100-199=scanner, 200-256=repeater)
            node_type: Role of this node (SERVER, SCANNER, REPEATER)
            frequency: LoRa frequency in MHz (default 915.0)
            tx_power: Transmission power in dBm (default 23)
        """
        self.node_id = node_id
        self.node_type = node_type
        self.sequence_num = 0
        self.seen_packets: set = set()  # Track (source, seq) tuples
        self.max_seen = 1000  # Limit memory usage

        # Initialize hardware only if not in LOCAL mode
        if os.getenv("LOCAL") != 'TRUE':
            import busio
            import digitalio
            import board
            import adafruit_rfm9x

            # Configure LoRa Radio
            CS = digitalio.DigitalInOut(board.CE1)
            RESET = digitalio.DigitalInOut(board.D25)
            spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

            self.rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, frequency)
            self.rfm9x.tx_power = tx_power
            self.rfm9x.node = node_id
            self.rfm9x.ack_delay = 0.1

            logging.info(f'LoRa initialized: Node={node_id}, Type={node_type.name}, Freq={frequency}MHz')
        else:
            self.rfm9x = None
            logging.info('LoRa bypassed (LOCAL mode)')

    def send_packet(self, packet: LoRaPacket, use_ack: bool = True) -> bool:
        """Send a LoRa packet"""
        if self.rfm9x is None:
            logging.debug("LOCAL mode: simulating send")
            return True

        data = packet.serialize()

        if len(data) > 253:
            logging.error(f"Packet too large: {len(data)} bytes")
            return False

        logging.debug(f"Sending {packet}")

        if use_ack:
            return self.rfm9x.send_with_ack(data)
        else:
            return self.rfm9x.send(data)

    def receive_packet(self, timeout: float = 0.5) -> Optional[LoRaPacket]:
        """Receive and parse a LoRa packet"""
        if self.rfm9x is None:
            return None

        raw_data = self.rfm9x.receive(with_header=True, timeout=timeout)

        if raw_data is None:
            return None

        # Skip RFM9x header (first 4 bytes: to, from, id, flags)
        packet_data = raw_data[4:]

        packet = LoRaPacket.deserialize(packet_data)

        if packet is None:
            logging.warning("Failed to deserialize packet")
            return None

        # Validate and track
        should_process, reason = packet.should_process(
            self.node_id, self.node_type, self.seen_packets
        )

        if not should_process:
            logging.debug(f"Discarding packet: {reason} - {packet}")
            return None

        if reason != "forward":
            # Add to seen packets (but not for forwarding)
            packet_id = (packet.source_node, packet.sequence_num)
            self.seen_packets.add(packet_id)

            # Prevent unbounded growth
            if len(self.seen_packets) > self.max_seen:
                # Remove oldest half
                self.seen_packets = set(list(self.seen_packets)[500:])

        logging.info(f"Received {packet}")
        return packet

    def get_next_sequence(self) -> int:
        """Get next sequence number (with wrap)"""
        self.sequence_num = (self.sequence_num + 1) % 65536
        return self.sequence_num

    def create_data_packet(self, dest_node: int, payload: bytes,
                          use_ack: bool = True,
                          multi_part_index: int = 0,
                          multi_part_total: int = 0) -> LoRaPacket:
        """
        Helper to create a data packet

        Args:
            dest_node: Destination node ID
            payload: Payload bytes
            use_ack: Request acknowledgment
            multi_part_index: Index in multi-packet sequence (0 if single)
            multi_part_total: Total packets in sequence (0 if single)
        """
        flags = PacketFlags.ACK_REQ if use_ack else 0

        # Determine multi-packet flags
        if multi_part_total == 0:
            multi_flags = MultiPartFlags.ONLY
        elif multi_part_index == 1:
            multi_flags = MultiPartFlags.FIRST | MultiPartFlags.MORE
        elif multi_part_index == multi_part_total:
            multi_flags = MultiPartFlags.LAST
        else:
            multi_flags = MultiPartFlags.MORE

        return LoRaPacket.create(
            packet_type=PacketType.DATA,
            source_node=self.node_id,
            dest_node=dest_node,
            payload=payload,
            sequence_num=self.get_next_sequence(),
            flags=flags,
            multi_flags=multi_flags,
            multi_part_index=multi_part_index,
            multi_part_total=multi_part_total
        )

    def create_cmd_packet(self, dest_node: int, command: str) -> LoRaPacket:
        """Helper to create a command packet"""
        payload = f"cmd|ack|{command}".encode('utf-8')

        return LoRaPacket.create(
            packet_type=PacketType.CMD,
            source_node=self.node_id,
            dest_node=dest_node,
            payload=payload,
            sequence_num=self.get_next_sequence(),
            flags=PacketFlags.ACK_REQ,
            multi_flags=MultiPartFlags.ONLY
        )

    def create_hello_packet(self, dest_node: int) -> LoRaPacket:
        """
        Create HELLO handshake packet to synchronize sequence numbers

        Sent on startup to notify server of sequence reset.
        Payload format: "HELLO|{current_seq}|{node_type}"

        Args:
            dest_node: Destination node ID (typically server = 1)

        Returns:
            HELLO packet
        """
        node_type_name = self.node_type.name  # "SCANNER", "SERVER", or "REPEATER"
        payload = f"HELLO|{self.sequence_num}|{node_type_name}".encode('utf-8')

        return LoRaPacket.create(
            packet_type=PacketType.HELLO,
            source_node=self.node_id,
            dest_node=dest_node,
            payload=payload,
            sequence_num=self.get_next_sequence(),
            flags=PacketFlags.ACK_REQ,  # Request ACK
            multi_flags=MultiPartFlags.ONLY
        )

    def create_hello_ack_packet(self, dest_node: int) -> LoRaPacket:
        """
        Create HELLO_ACK response packet

        Sent by server in response to HELLO.
        Payload format: "HELLO_ACK|{server_seq}|OK"

        Args:
            dest_node: Node that sent HELLO

        Returns:
            HELLO_ACK packet
        """
        payload = f"HELLO_ACK|{self.sequence_num}|OK".encode('utf-8')

        return LoRaPacket.create(
            packet_type=PacketType.HELLO_ACK,
            source_node=self.node_id,
            dest_node=dest_node,
            payload=payload,
            sequence_num=self.get_next_sequence(),
            flags=0,  # No ACK needed for ACK
            multi_flags=MultiPartFlags.ONLY
        )

    def send_hello_handshake(self, dest_node: int, timeout: float = 3.0,
                            max_retries: int = 3) -> bool:
        """
        Send HELLO and wait for HELLO_ACK

        Used by scanner on startup to synchronize sequence numbers with server.

        Args:
            dest_node: Server node ID (typically 1)
            timeout: Timeout in seconds per attempt
            max_retries: Maximum number of retry attempts

        Returns:
            True if HELLO_ACK received, False if failed
        """
        for attempt in range(max_retries):
            logging.info(f"Sending HELLO to node {dest_node} (attempt {attempt + 1}/{max_retries})")

            # Create and send HELLO
            hello_packet = self.create_hello_packet(dest_node)

            if not self.send_packet(hello_packet, use_ack=False):
                logging.warning(f"Failed to send HELLO packet (attempt {attempt + 1})")
                time.sleep(1.0)  # Wait before retry
                continue

            # Wait for HELLO_ACK
            start_time = time.time()
            while time.time() - start_time < timeout:
                ack_packet = self.receive_packet(timeout=0.5)

                if ack_packet and ack_packet.packet_type == PacketType.HELLO_ACK:
                    if ack_packet.source_node == dest_node:
                        try:
                            payload = ack_packet.payload.decode('utf-8')
                            parts = payload.split('|')
                            if parts[0] == "HELLO_ACK" and parts[2] == "OK":
                                server_seq = int(parts[1])
                                logging.info(f"HELLO_ACK received from node {dest_node}, server_seq={server_seq}")
                                return True
                        except Exception as e:
                            logging.error(f"Error parsing HELLO_ACK: {e}")

                time.sleep(0.1)

            logging.warning(f"HELLO_ACK timeout (attempt {attempt + 1}/{max_retries})")
            time.sleep(1.0)  # Wait before retry

        logging.error(f"HELLO handshake failed after {max_retries} attempts")
        return False
