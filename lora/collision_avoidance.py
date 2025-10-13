"""
Collision Avoidance Mechanisms for LoRa

Implements randomized delays, guard delays, and air time estimation
to reduce packet collisions in multi-node LoRa networks.

NOTE: RSSI-based channel sensing is NOT used because it cannot reliably
detect active LoRa transmissions (it measures all RF signal sources including
distance-varying legitimate traffic). Hardware CAD (Channel Activity Detection)
would be ideal but is not available in the adafruit_rfm9x library.

Primary collision avoidance strategy:
1. Randomized transmission delays (statistical avoidance)
2. Exponential backoff on retry
3. ACK/retry at application layer
"""

import random
import time
import logging


class CollisionAvoidance:
    """Implements collision avoidance mechanisms for LoRa transmission"""

    @staticmethod
    def randomized_delay(min_ms: int = 10, max_ms: int = 100):
        """
        Add random delay before transmission

        Args:
            min_ms: Minimum delay in milliseconds
            max_ms: Maximum delay in milliseconds
        """
        delay = random.uniform(min_ms, max_ms) / 1000.0
        time.sleep(delay)
        logging.debug(f"Random delay: {delay*1000:.1f}ms")

    @staticmethod
    def rx_guard(rfm9x, guard_time_ms: int = 50, rssi_threshold: int = -90) -> bool:
        """
        Simple guard delay before transmission.

        NOTE: RSSI-based channel sensing is DISABLED because:

        1. RSSI measures signal strength from ANY source:
           - Legitimate server communication (varying with distance)
           - Other scanners in the network
           - Environmental RF noise
           - Changes as nodes move closer/farther

        2. RSSI cannot distinguish:
           - "Channel busy with active LoRa transmission" (bad - collision)
           - "Strong baseline signal from nearby server" (good - just close proximity)
           - "Moved from far to near location" (good - natural RSSI increase)

        3. Hardware CAD (Channel Activity Detection) is the proper solution:
           - Detects LoRa preambles (actual transmissions in progress)
           - Hardware feature in SX127x/RFM9x chips
           - NOT available in adafruit_rfm9x library

        Without CAD, collision avoidance relies on:
        - Randomized delays (primary mechanism)
        - Exponential backoff on retry
        - ACK/retry logic at application layer

        Args:
            rfm9x: RFM9x radio object (unused)
            guard_time_ms: Time to wait before transmission
            rssi_threshold: DEPRECATED - not used

        Returns:
            Always True (channel assumed clear after delay)
        """
        # Simple fixed delay (gives other potential transmitters time to start)
        time.sleep(guard_time_ms / 1000.0)
        logging.debug(f"Guard delay: {guard_time_ms}ms (RSSI check disabled)")
        return True  # Assume clear after delay

    @staticmethod
    def estimate_airtime(payload_size: int, spreading_factor: int = 7,
                        bandwidth: int = 125000, coding_rate: int = 5) -> float:
        """
        Estimate LoRa packet air time in milliseconds

        Based on Semtech formula for LoRa air time calculation

        Args:
            payload_size: Payload size in bytes
            spreading_factor: LoRa spreading factor (7-12, default 7)
            bandwidth: Bandwidth in Hz (default 125000 = 125kHz)
            coding_rate: Coding rate (5-8, default 5 = 4/5)

        Returns:
            Estimated air time in milliseconds
        """
        # Symbol duration in seconds
        Ts = (2 ** spreading_factor) / bandwidth

        # Preamble time (8 symbols + 4.25)
        Tpreamble = (8 + 4.25) * Ts

        # Payload symbols
        payload_symb_nb = 8 + max(
            ((8 * payload_size - 4 * spreading_factor + 28 + 16) / (4 * spreading_factor)) * coding_rate,
            0
        )

        # Payload time
        Tpayload = payload_symb_nb * Ts

        # Total time in milliseconds
        total_ms = (Tpreamble + Tpayload) * 1000

        logging.debug(f"Estimated airtime: {total_ms:.1f}ms for {payload_size} bytes")
        return total_ms

    @staticmethod
    def send_with_ca(rfm9x, data: bytes, max_retries: int = 3,
                    enable_rx_guard: bool = True,
                    enable_random_delay: bool = True) -> bool:
        """
        Send with collision avoidance mechanisms

        Combines randomized delay + RX guard (channel sensing) + exponential backoff

        Args:
            rfm9x: RFM9x radio object
            data: Data bytes to send
            max_retries: Maximum retry attempts
            enable_rx_guard: Enable RX guard (channel sensing)
            enable_random_delay: Enable randomized delay

        Returns:
            True if sent successfully, False if failed
        """
        for attempt in range(max_retries):
            # Random backoff (increases with attempts)
            if enable_random_delay:
                min_delay = 10 + (attempt * 20)
                max_delay = 100 + (attempt * 50)
                CollisionAvoidance.randomized_delay(min_delay, max_delay)

            # Check if channel is clear
            if enable_rx_guard:
                if not CollisionAvoidance.rx_guard(rfm9x, 50):
                    # Channel busy, exponential backoff
                    backoff = (2 ** attempt) * 50  # 50ms, 100ms, 200ms
                    logging.debug(f"Channel busy, backoff {backoff}ms")
                    time.sleep(backoff / 1000.0)
                    continue

            # Channel clear, send
            logging.debug(f"Sending with CA (attempt {attempt + 1}/{max_retries})")
            if rfm9x.send_with_ack(data):
                logging.debug("Send successful")
                return True
            else:
                logging.warning(f"Send failed (attempt {attempt + 1}/{max_retries})")

        logging.error(f"Send failed after {max_retries} attempts")
        return False  # Failed after retries
