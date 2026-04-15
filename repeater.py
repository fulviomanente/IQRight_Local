#!/usr/bin/env python3
"""
LoRa Repeater Application

A battery/solar-powered repeater node that forwards packets between scanner and server
to extend network range. Runs on Raspberry Pi Zero with Waveshare Power Management HAT.

Node ID Range: 200-256
Functionality:
- Receives packets from any node
- Validates packet integrity (CRC)
- Checks if packet should be forwarded (TTL, duplicates)
- Updates sender field and decrements TTL
- Forwards packet with collision avoidance
- Monitors Waveshare HAT power status (Vin, Vout, RTC)
- Listens for HAT shutdown signal on GPIO 20
- Signals running state to HAT on GPIO 21

Usage:
    python repeater.py

    Set LORA_NODE_ID environment variable to unique repeater ID (200-256):
    LORA_NODE_ID=200 python repeater.py
"""

import logging
import logging.handlers
import os
import time
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Import enhanced LoRa packet handler
from lora import LoRaTransceiver, LoRaPacket, PacketType, NodeType, CollisionAvoidance
from utils.config import (
    LORA_NODE_ID, LORA_FREQUENCY, LORA_TX_POWER, LORA_TTL, LORA_ENABLE_CA,
    LOG_FILENAME, MAX_LOG_SIZE, BACKUP_COUNT, DEBUG, HOME_DIR
)
from utils.oled_display import get_oled_display

# Power Management HAT selection (WAVESHARE or PISUGAR, default WAVESHARE)
POWER_HAT = os.getenv('POWER_HAT', 'WAVESHARE').upper()

# Power status monitor (optional, depends on POWER_HAT setting)
POWER_MONITOR_AVAILABLE = False
read_power_status = None
format_power_status_for_lora = None

if POWER_HAT == 'PISUGAR':
    try:
        from utils.pisugar_monitor import read_pisugar_status as read_power_status
        from utils.pisugar_monitor import format_status_for_lora as format_power_status_for_lora
        POWER_MONITOR_AVAILABLE = True
        logging.info("PiSugar power monitor loaded")
    except ImportError:
        logging.info("PiSugar monitor not available")
else:
    try:
        from utils.waveshare_monitor import read_waveshare_status as read_power_status
        from utils.waveshare_monitor import format_status_for_lora as format_power_status_for_lora
        POWER_MONITOR_AVAILABLE = True
        logging.info("Waveshare power monitor loaded")
    except ImportError:
        logging.info("Waveshare monitor not available")

# GPIO pin config from config (Waveshare HAT defaults)
try:
    from utils.config import (
        LORA_CS_PIN, LORA_RST_PIN,
        WAVESHARE_SHUTDOWN_PIN, WAVESHARE_RUNNING_PIN,
        WAVESHARE_SERIAL_DEVICE, WAVESHARE_SERIAL_BAUD
    )
except ImportError:
    # Fallback defaults if config doesn't have these yet
    LORA_CS_PIN = 17
    LORA_RST_PIN = 16
    WAVESHARE_SHUTDOWN_PIN = 20
    WAVESHARE_RUNNING_PIN = 21
    WAVESHARE_SERIAL_DEVICE = '/dev/ttyS0'
    WAVESHARE_SERIAL_BAUD = 115200

# GPIO setup for Waveshare HAT communication (only for Waveshare HAT)
WAVESHARE_GPIO_AVAILABLE = False
if POWER_HAT == 'WAVESHARE' and os.getenv("LOCAL") != 'TRUE':
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        # Pin 20: HAT signals Pi to shutdown (input)
        GPIO.setup(WAVESHARE_SHUTDOWN_PIN, GPIO.IN)
        # Pin 21: Pi tells HAT it's running (output, HIGH = running)
        GPIO.setup(WAVESHARE_RUNNING_PIN, GPIO.OUT)
        GPIO.output(WAVESHARE_RUNNING_PIN, GPIO.HIGH)
        WAVESHARE_GPIO_AVAILABLE = True
        logging.info(f"Waveshare GPIO initialized: shutdown=GPIO{WAVESHARE_SHUTDOWN_PIN}, running=GPIO{WAVESHARE_RUNNING_PIN}")
    except Exception as e:
        logging.warning(f"Waveshare GPIO setup failed: {e}")


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


def _get_lora_pins():
    """Get board pin objects for CS and RST based on config GPIO numbers."""
    if os.getenv("LOCAL") == 'TRUE':
        return None, None
    import board
    import digitalio

    # Map GPIO numbers to board pin objects
    gpio_map = {
        7: board.CE1,
        8: board.CE0,
        16: board.D16,
        17: board.D17,
        25: board.D25,
    }

    cs_board_pin = gpio_map.get(LORA_CS_PIN)
    rst_board_pin = gpio_map.get(LORA_RST_PIN)

    if cs_board_pin is None:
        raise ValueError(f"Unsupported LORA_CS_PIN GPIO {LORA_CS_PIN}")
    if rst_board_pin is None:
        raise ValueError(f"Unsupported LORA_RST_PIN GPIO {LORA_RST_PIN}")

    return cs_board_pin, rst_board_pin


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
    logging.info(f"LoRa Pins: CS=GPIO{LORA_CS_PIN}, RST=GPIO{LORA_RST_PIN}")

    # Show startup on OLED
    oled.show_startup()

    # Initialize transceiver with Waveshare-compatible pins
    cs_pin, rst_pin = _get_lora_pins()
    transceiver = LoRaTransceiver(
        node_id=LORA_NODE_ID,
        node_type=NodeType.REPEATER,
        frequency=LORA_FREQUENCY,
        tx_power=LORA_TX_POWER,
        cs_pin=cs_pin,
        reset_pin=rst_pin
    )

    stats = RepeaterStats()
    last_stats_time = time.time()
    last_oled_update = time.time()
    last_status_sent = time.time()
    last_power_status = None  # Cache last Waveshare reading
    is_transmitting = False   # Track LoRa TX state for status priority
    STATS_INTERVAL = 300      # Log stats every 5 minutes
    OLED_STATS_INTERVAL = 60  # Update OLED stats every 60 seconds
    STATUS_SEND_INTERVAL = 600  # Send status to server every 10 minutes

    # Pending status to send when LoRa becomes idle
    pending_status_event = None
    pending_status_ready = False

    def send_status(event=None):
        """Send a STATUS packet to the server. Only call when LoRa is idle."""
        if not POWER_MONITOR_AVAILABLE:
            return
        try:
            if POWER_HAT == 'WAVESHARE':
                status = read_power_status(WAVESHARE_SERIAL_DEVICE, WAVESHARE_SERIAL_BAUD)
            else:
                status = read_power_status()
            nonlocal last_power_status
            last_power_status = status
            if not status['available']:
                logging.debug(f"Power status unavailable: {status['error']}")
                return
            status_payload = format_power_status_for_lora(status, event=event)
            status_packet = LoRaPacket.create(
                packet_type=PacketType.STATUS,
                source_node=LORA_NODE_ID,
                dest_node=1,
                payload=status_payload.encode('utf-8'),
                sequence_num=transceiver.get_next_sequence()
            )
            success = transceiver.send_packet(status_packet, use_ack=False)
            label = f" ({event})" if event else ""
            if success:
                logging.info(f"Status{label} sent: Vin={status['vin_voltage']:.2f}V, Vout={status['vout_voltage']:.2f}V, Alerts={status['alerts'] or 'none'}")
            else:
                logging.warning(f"Failed to send status{label} to server")
        except Exception as e:
            logging.error(f"Error sending status: {e}")

    def check_hat_shutdown():
        """Check if Waveshare HAT is signaling shutdown via GPIO 20."""
        if not WAVESHARE_GPIO_AVAILABLE:
            return False
        if GPIO.input(WAVESHARE_SHUTDOWN_PIN):
            # Confirm signal is sustained (not a glitch)
            time.sleep(1)
            if GPIO.input(WAVESHARE_SHUTDOWN_PIN):
                return True
        return False

    logging.info("Repeater ready, listening for packets...")

    # Show ready status on OLED
    time.sleep(2)  # Wait for startup message to display
    oled.show_ready(LORA_NODE_ID, device_type="Repeater")

    # Queue STARTUP status to send when idle
    pending_status_event = "STARTUP"
    pending_status_ready = True

    try:
        while True:
            # Check for HAT shutdown signal (highest priority)
            if check_hat_shutdown():
                logging.info("Waveshare HAT signaled shutdown via GPIO 20")
                # Try to send shutdown status but don't block
                send_status(event="SHUTDOWN")
                stats.log_stats()

                # Show shutdown message on OLED
                try:
                    oled._clear()
                    oled.draw.text((10, 20), "HAT Shutdown", font=oled.font, fill=255)
                    oled.draw.text((10, 35), "Signal Received", font=oled.font, fill=255)
                    oled._update()
                    time.sleep(2)
                    oled._turn_off()
                except Exception:
                    pass

                logging.info("Initiating system shutdown")
                subprocess.run(["sudo", "shutdown", "-h", "now"])
                break

            # Receive packet
            packet = transceiver.receive_packet(timeout=1.0)

            if packet is None:
                # No packet received — LoRa is idle, safe for housekeeping
                time.sleep(0.1)

                # Send any pending status (only when idle)
                if pending_status_ready:
                    send_status(event=pending_status_event)
                    pending_status_event = None
                    pending_status_ready = False
                    last_status_sent = time.time()

                # Periodically log stats
                if time.time() - last_stats_time > STATS_INTERVAL:
                    stats.log_stats()
                    last_stats_time = time.time()

                # Periodically read and send power status (only when idle)
                if POWER_MONITOR_AVAILABLE and time.time() - last_status_sent > STATUS_SEND_INTERVAL:
                    send_status()
                    last_status_sent = time.time()

                # Periodically update OLED stats
                if time.time() - last_oled_update > OLED_STATS_INTERVAL:
                    try:
                        total_dropped = (stats.packets_dropped_ttl +
                                       stats.packets_dropped_duplicate +
                                       stats.packets_dropped_crc)
                        # Show Vin voltage on OLED if available
                        vin_display = None
                        if last_power_status and last_power_status.get('available'):
                            vin_display = int(last_power_status['vin_voltage'] * 100)  # e.g. 499 for 4.99V
                        oled.show_repeater_stats(
                            stats.packets_received,
                            stats.packets_forwarded,
                            total_dropped,
                            vin_display
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
        logging.info("Repeater shutting down (manual stop)...")
        send_status(event="SHUTDOWN")
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

    finally:
        # Clean up GPIO on exit
        if WAVESHARE_GPIO_AVAILABLE:
            try:
                GPIO.output(WAVESHARE_RUNNING_PIN, GPIO.LOW)
                GPIO.cleanup()
            except Exception:
                pass


if __name__ == "__main__":
    main()
