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

# OLED display switch on GPIO 5 (physical toggle switch)
# ON = display active (no auto-off), OFF = display fully off
OLED_SWITCH_PIN = 16

# GPIO state
WAVESHARE_GPIO_AVAILABLE = False
GPIO_AVAILABLE = False
GPIO = None  # Module-level reference, set in _init_gpio()

if os.getenv("LOCAL") != 'TRUE':
    try:
        import RPi.GPIO as GPIO
    except ImportError:
        pass


# Logging setup — daily rotation at midnight
try:
    log_file = f'{HOME_DIR}/log/repeater_{LORA_NODE_ID}.log'
    handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when='midnight', interval=1, backupCount=BACKUP_COUNT
    )
    handler.suffix = "%Y-%m-%d"
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


def _get_wifi_info() -> tuple:
    """Get WiFi connection status and IP address. Returns (connected: bool, ip: str)."""
    try:
        result = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True, timeout=3
        )
        ips = result.stdout.strip().split()
        if ips:
            return True, ips[0]
    except Exception:
        pass
    return False, ""


def _get_pisugar_wakeup() -> str:
    """Get next PiSugar RTC wakeup time. Returns time string or '--'."""
    try:
        result = subprocess.run(
            ["bash", "-c", "echo 'get rtc_alarm_time' | nc -q 0 127.0.0.1 8423"],
            capture_output=True, text=True, timeout=3
        )
        out = result.stdout.strip()
        # Format: "rtc_alarm_time: 2026-04-23T13:00:00.000-05:00"
        if "rtc_alarm_time:" in out:
            time_str = out.split(": ", 1)[1].strip()
            # Extract just HH:MM
            if "T" in time_str:
                return time_str.split("T")[1][:5]
    except Exception:
        pass
    return "--"


def _show_info_screens(oled, power_status, start_time: float):
    """Show 4 info screens when the OLED switch is turned on.

    Screen 1 (5s): Battery level + charging status
    Screen 2 (5s): RTC wakeup time + current time (sync check)
    Screen 3 (5s): WiFi status + IP address
    Screen 4 (5s): Service start time + Node ID + current time
    """
    try:
        # --- Screen 1: Battery ---
        oled._turn_on()
        oled._clear()
        oled.draw.text((5, 5), "Power Status", font=oled.font, fill=255)
        oled.draw.rectangle((0, 18, oled.width, 20), outline=255, fill=255)

        if power_status and power_status.get('available'):
            if POWER_HAT == 'PISUGAR':
                oled.draw.text((5, 25), f"Battery: {power_status['battery']:.0f}%", font=oled.font, fill=255)
                oled.draw.text((5, 38), f"Voltage: {power_status['voltage']:.2f}V", font=oled.font, fill=255)
                charging = "Yes" if power_status.get('charging') else "No"
                oled.draw.text((5, 51), f"Charging: {charging}", font=oled.font, fill=255)
            else:
                oled.draw.text((5, 25), f"Vin:  {power_status['vin_voltage']:.2f}V", font=oled.font, fill=255)
                oled.draw.text((5, 38), f"Vout: {power_status['vout_voltage']:.2f}V", font=oled.font, fill=255)
        else:
            oled.draw.text((5, 25), "No power data", font=oled.font, fill=255)

        oled._update()
        time.sleep(5)

        # --- Screen 2: Wakeup + Current Time ---
        oled._clear()
        oled.draw.text((5, 5), "RTC Schedule", font=oled.font, fill=255)
        oled.draw.rectangle((0, 18, oled.width, 20), outline=255, fill=255)

        wakeup = _get_pisugar_wakeup() if POWER_HAT == 'PISUGAR' else "--"
        oled.draw.text((5, 25), f"Wakeup: {wakeup}", font=oled.font, fill=255)
        oled.draw.text((5, 42), f"Now:    {datetime.now().strftime('%H:%M:%S')}", font=oled.font, fill=255)

        oled._update()
        time.sleep(5)

        # --- Screen 3: WiFi + IP ---
        oled._clear()
        oled.draw.text((5, 5), "Network", font=oled.font, fill=255)
        oled.draw.rectangle((0, 18, oled.width, 20), outline=255, fill=255)

        connected, ip = _get_wifi_info()
        if connected:
            oled.draw.text((5, 25), "WiFi: Connected", font=oled.font, fill=255)
            oled.draw.text((5, 42), f"IP: {ip}", font=oled.font, fill=255)
        else:
            oled.draw.text((5, 25), "WiFi: Not connected", font=oled.font, fill=255)

        oled._update()
        time.sleep(5)

        # --- Screen 4: Service start + current time ---
        oled._clear()
        oled.draw.text((5, 5), "Service Info", font=oled.font, fill=255)
        oled.draw.rectangle((0, 18, oled.width, 20), outline=255, fill=255)

        start_dt = datetime.fromtimestamp(start_time)
        oled.draw.text((5, 25), f"Started: {start_dt.strftime('%H:%M:%S')}", font=oled.font, fill=255)
        oled.draw.text((5, 38), f"Node ID: {LORA_NODE_ID}", font=oled.font, fill=255)
        oled.draw.text((5, 51), f"Now: {datetime.now().strftime('%H:%M:%S')}", font=oled.font, fill=255)

        oled._update()
        time.sleep(5)

    except Exception as e:
        logging.error(f"Error showing info screens: {e}")


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
    global GPIO_AVAILABLE, WAVESHARE_GPIO_AVAILABLE

    # Initialize GPIO pins (after logging is configured so messages are visible)
    if GPIO is not None:
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # OLED switch (GPIO 5, input with pull-up — switch connects to GND)
            GPIO.setup(OLED_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO_AVAILABLE = True
            switch_val = GPIO.input(OLED_SWITCH_PIN)
            logging.info(f"OLED switch initialized on GPIO{OLED_SWITCH_PIN} (value={switch_val}, {'OFF' if switch_val else 'ON'})")

            # Waveshare HAT pins (only if Waveshare selected)
            if POWER_HAT == 'WAVESHARE':
                GPIO.setup(WAVESHARE_SHUTDOWN_PIN, GPIO.IN)
                GPIO.setup(WAVESHARE_RUNNING_PIN, GPIO.OUT)
                GPIO.output(WAVESHARE_RUNNING_PIN, GPIO.HIGH)
                WAVESHARE_GPIO_AVAILABLE = True
                logging.info(f"Waveshare GPIO initialized: shutdown=GPIO{WAVESHARE_SHUTDOWN_PIN}, running=GPIO{WAVESHARE_RUNNING_PIN}")
        except Exception as e:
            logging.error(f"GPIO setup failed: {e}")

    # Initialize OLED display (auto-off disabled — controlled by GPIO switch)
    oled = get_oled_display(auto_off_seconds=0)

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

    # OLED switch state tracking (GPIO 5)
    oled_switch_was_on = False
    oled_display_active = False
    service_start_time = time.time()

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
                if POWER_HAT == 'WAVESHARE':
                    logging.info(f"Status{label} sent: Vin={status['vin_voltage']:.2f}V, Vout={status['vout_voltage']:.2f}V, Alerts={status['alerts'] or 'none'}")
                else:
                    logging.info(f"Status{label} sent: Battery={status['battery']:.1f}%, Voltage={status['voltage']:.2f}V, Charging={status['charging']}")
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

    # Show ready status on OLED briefly during startup
    time.sleep(2)
    oled.show_ready(LORA_NODE_ID, device_type="Repeater")
    time.sleep(2)

    # Check initial switch state — if OFF, turn display off now
    if GPIO_AVAILABLE:
        initial_switch = not GPIO.input(OLED_SWITCH_PIN)
        if initial_switch:
            oled_switch_was_on = True
            oled_display_active = True
            logging.info("OLED switch is ON at startup — display stays on")
        else:
            oled._turn_off()
            oled_switch_was_on = False
            oled_display_active = False
            logging.info("OLED switch is OFF at startup — display off")
    else:
        # No GPIO — keep display on (fallback behavior)
        oled_display_active = True
        oled_switch_was_on = True

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

                # --- OLED switch control (GPIO 5) ---
                oled_switch_on = (not GPIO.input(OLED_SWITCH_PIN)) if GPIO_AVAILABLE else False

                if oled_switch_on and not oled_switch_was_on:
                    # Switch just turned ON — show info screens then enter normal display
                    logging.info("OLED switch ON — showing info screens")
                    oled_display_active = True
                    _show_info_screens(oled, last_power_status, service_start_time)
                    last_oled_update = 0  # Force immediate stats display after info screens

                elif not oled_switch_on and oled_switch_was_on:
                    # Switch just turned OFF — shut down display
                    logging.info("OLED switch OFF — display off")
                    oled_display_active = False
                    try:
                        oled._turn_off()
                    except Exception:
                        pass

                oled_switch_was_on = oled_switch_on

                # Normal OLED stats (only when switch is ON)
                if oled_display_active and time.time() - last_oled_update > OLED_STATS_INTERVAL:
                    try:
                        total_dropped = (stats.packets_dropped_ttl +
                                       stats.packets_dropped_duplicate +
                                       stats.packets_dropped_crc)
                        vin_display = None
                        if last_power_status and last_power_status.get('available'):
                            if POWER_HAT == 'WAVESHARE':
                                vin_display = int(last_power_status['vin_voltage'] * 100)
                            else:
                                vin_display = int(last_power_status['battery'])
                        oled.show_repeater_stats(
                            stats.packets_received,
                            stats.packets_forwarded,
                            total_dropped,
                            vin_display
                        )
                        last_oled_update = time.time()
                    except Exception as e:
                        logging.error(f"Failed to update OLED: {e}")

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

            logging.info(f"Forwarding packet: {packet}")

            # Show forwarding on OLED (only when switch is ON)
            if oled_display_active:
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
        print("\nRepeater stopped")

    except Exception as e:
        logging.error(f"Fatal error in repeater: {e}")
        try:
            oled.show_error(f"Fatal error: {str(e)[:20]}")
            time.sleep(5)
        except Exception:
            pass
        raise

    finally:
        # Always send SHUTDOWN status to server so device_status.log records the exact time
        try:
            send_status(event="SHUTDOWN")
            logging.info("SHUTDOWN status sent to server")
        except Exception:
            pass

        stats.log_stats()

        # Always turn off OLED on exit — prevents battery drain after shutdown
        try:
            oled.shutdown()
        except Exception:
            pass

        # Clean up GPIO on exit
        if WAVESHARE_GPIO_AVAILABLE:
            try:
                GPIO.output(WAVESHARE_RUNNING_PIN, GPIO.LOW)
                GPIO.cleanup()
            except Exception:
                pass


if __name__ == "__main__":
    main()
