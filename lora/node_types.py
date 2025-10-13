"""
LoRa Node Types and Enumerations

Defines packet types, flags, and node roles for the LoRa mesh network.
"""

from enum import IntEnum


class PacketType(IntEnum):
    """Type of LoRa packet"""
    DATA = 0x01      # QR code scan data or student info
    ACK = 0x02       # Acknowledgment
    CMD = 0x03       # Command (break, release, undo, cleanup)
    BEACON = 0x04    # Keep-alive/discovery (future use)


class PacketFlags(IntEnum):
    """General packet flags"""
    ACK_REQ = 0x01       # Acknowledgment requested
    IS_REPEAT = 0x02     # Packet was repeated by a repeater


class MultiPartFlags(IntEnum):
    """Multi-packet sequence flags"""
    FIRST = 0x01         # First packet in multi-packet sequence
    MORE = 0x02          # More packets coming after this one
    LAST = 0x04          # Last packet in sequence
    ONLY = 0x08          # Single packet (not part of sequence)


class NodeType(IntEnum):
    """Role of a node in the network"""
    SERVER = 1       # Server (node ID = 1)
    SCANNER = 2      # Scanner (node IDs 100-199)
    REPEATER = 3     # Repeater (node IDs 200-256)
