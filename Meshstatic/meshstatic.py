# meshstatic.py
"""
Mesh overlay helpers for RFM95X testing.
Protocol packet structure:
{
  "type": "MSG" | "ACK" | "REQ",
  "src": int,
  "dst": int,        # 0 = broadcast
  "seq": int,
  "ttl": int,
  "payload": "...",
  "remaining:" int #Number of remaining packages to be sent after an ACK as a response to a type = "REQ"
}
"""

import time
import threading
import random

# constants
BROADCAST_ID = 0
MAX_PAYLOAD = 200  # keep below LoRa max for conservative safety
DEFAULT_TTL = 5

import logging
import sys

# Centralized logging setup
logging.basicConfig(
    level=logging.DEBUG,  # Change to INFO in production
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("meshstatic.log"),   # logs to file
        logging.StreamHandler(sys.stdout)        # logs to console
    ]
)

# Shared logger for all modules
logger = logging.getLogger("meshstatic")
logger.setLevel(logging.INFO)
#ch = logging.StreamHandler()
#ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
#logger.addHandler(ch)


def make_packet(pkt_type, src, dst, seq, ttl, payload, remaining: int = 0):
    pkt = f"{pkt_type}|{int(src)}|{int(dst)}|{int(seq)}|{int(ttl)}|{payload}|{remaining}"
    if len(pkt.encode("utf-8")) > MAX_PAYLOAD:
        raise ValueError("payload too large")
    return pkt.encode("utf-8")


def parse_packet(raw_bytes):
    try:
        s = raw_bytes.decode("utf-8", errors="ignore")
        pkt_type, src, dst, seq, ttl, payload, packets = s.split("|")
        pkt =  {"type": pkt_type if len(pkt_type) <= 3 else pkt_type[-3:],
                "src": int(src),
                "dst": int(dst),
                "seq": int(seq),
                "ttl": int(ttl),
                "payload": payload,
                "remaining": int(packets)}
        return pkt
    except Exception as e:
        logger.debug("parse_packet failed: %s", e)
        return None


class MeshNode:
    """
    Encapsulates RFM9x and mesh logic:
     - send_unicast(dest, payload, await_ack=False)
     - send_broadcast(payload)
     - run receive loop with callback on inbound application messages
     - internal duplicate suppression and forwarding (for replicators)
    """
    def __init__(self, rfm, node_id:int, default_ttl=DEFAULT_TTL):
        self.rfm = rfm
        self.node_id = int(node_id)
        self.default_ttl = default_ttl
        self._recv_thread = None
        self._running = False

        # duplicate detection: keep last seen seq per src (small cache)
        self.seen = {}  # {src: last_seq}
        self.seen_lock = threading.Lock()

        # application hooks
        self.on_message = None  # function(pkt, rssi)
        self.on_forward = None  # function(pkt, rssi)
        self.on_request = None # function(pkt)
        self.seq_lock = threading.Lock()
        self._seq = random.randint(0, 65535)
        self.full_response = None

    def _next_seq(self):
        with self.seq_lock:
            self._seq = (self._seq + 1) & 0xFFFF
            return self._seq

    def send_request(self, dst, payload, await_ack=False, ttl=None, timeout: int = 5.0):
        dst = int(dst)
        ttl = self.default_ttl if ttl is None else int(ttl)
        seq = self._next_seq()
        pkt_bytes = make_packet("REQ", self.node_id, dst, seq, ttl, payload)
        logger.info("TX -> dst=%s seq=%d ttl=%d payload=%s len=%d", dst, seq, ttl, str(payload)[:40], len(pkt_bytes))
        self.rfm.send(pkt_bytes)

        # await ack and loop for additional packages
        if await_ack and dst != BROADCAST_ID:
            start = time.time()
            ack_received = False
            remaining = 0
            while time.time() - start < timeout:
                rx = self.rfm.receive(with_header=True, with_ack=False, timeout=20)
                if rx != None:
                    pkt = parse_packet(rx)
                    if pkt != None:
                        if self._check_duplicate(pkt.get("src"), pkt.get("seq")):
                            # only process if packet addressed to me
                            if pkt.get("dst", BROADCAST_ID) == self.node_id and pkt.get("type") == "ACK":
                            #if pkt.get("type") == "ACK" and pkt.get("src") == dst and pkt.get("seq") == seq:
                                ack_received = True
                                remaining = pkt.get("remaining")
                                logger.info(f"{remaining} Follow up packets")
                                received = 0
                                break
            if ack_received:
                logger.info("ACK received from %s for seq %d rssi=%s", dst, seq, getattr(self.rfm, "last_rssi", None))
            else:
                logger.warning("No ACK from %s for seq %d", dst, seq)
            #If there are follow up packets, receive all of them
            return_message = []
            logger.info(f"Recieving {remaining} additional packets")
            while (time.time() - start < timeout) and received < remaining:
                rx = self.rfm.receive(with_header=True, with_ack=False, timeout=10)
                if rx != None:
                    logger.info(f"Follow up packet {received} received")
                    pkt = parse_packet(rx)
                    if pkt != None:
                        if pkt.get("type") == "MSG" and pkt.get("src") == dst:
                            return_message.append(pkt.get("payload"))
                            return_package = self._send_ack(pkt["src"], pkt["seq"], 0)
                            received += 1
            if ack_received and (len(return_message) == remaining):
                if len(return_message) > 0:
                    self.full_response = return_message
                else:
                    self.full_response = None
                return True
            else:
                self.full_response = None
                return False
        else:
            logger.info('bypass ACK')
            return True


    def send_unicast(self, dst, payload, await_ack=False, ttl=None, timeout: int = 5.0):
        dst = int(dst)
        ttl = self.default_ttl if ttl is None else int(ttl)
        seq = self._next_seq()
        pkt_bytes = make_packet("MSG", self.node_id, dst, seq, ttl, payload)
        logger.info("TX -> dst=%s seq=%d ttl=%d payload=%s len=%d", dst, seq, ttl, str(payload)[:40], len(pkt_bytes))
        self.rfm.send(pkt_bytes)

        # simple await ack loop (blocking for tests)
        if await_ack and dst != BROADCAST_ID:
            start = time.time()
            ack_received = False
            while time.time() - start < timeout:
                # Use shorter timeout for receive to check more frequently
                rx = self.rfm.receive(with_header=True, with_ack=False, timeout=0.5)

                if rx != None:
                    pkt = parse_packet(rx)
                    if pkt != None:
                        logger.debug(f"While waiting for ACK, received packet type={pkt.get('type')} src={pkt.get('src')} seq={pkt.get('seq')}")
                        if pkt.get("type") == "ACK" and pkt.get("src") == dst and pkt.get("seq") == seq:
                            logger.info(f"Got expected ACK from {dst} for seq {seq}")
                            ack_received = True
                            break
                        else:
                            # Received some other packet, ignore and keep waiting
                            logger.debug(f"Ignoring packet while waiting for ACK from {dst} seq={seq}")
            if ack_received:
                logger.info("ACK received from %s for seq %d rssi=%s", dst, seq, getattr(self.rfm, "last_rssi", None))
            else:
                logger.warning("No ACK from %s for seq %d (timeout after %.1fs)", dst, seq, time.time() - start)
            return ack_received
        else:
            logger.info('bypass ACK')
            return True

    def send_broadcast(self, payload, ttl=None):
        ttl = self.default_ttl if ttl is None else int(ttl)
        seq = self._next_seq()
        pkt_bytes = make_packet("MSG", self.node_id, BROADCAST_ID, seq, ttl, payload)
        logger.info("BCAST TX seq=%d ttl=%d payload=%s", seq, ttl, str(payload)[:40])
        self.rfm.send(pkt_bytes)
        return True

    def _should_forward(self, pkt):
        # Only forward if TTL > 1 and we haven't seen the seq before
        if pkt.get("ttl", 0) <= 1:
            logger.info(f"TTL expired for SEQ: {pkt.get('seq')} Source: {pkt.get('src')}")
            return False
        else:
            logger.info(f"TTL Valid for SEQ: {pkt.get('seq')} Source: {pkt.get('src')}")
            return True

    def _send_ack(self, src, seq, datapackets: int = 0):
        # Use higher TTL for ACKs to ensure they can be forwarded through mesh
        ack_ttl = 3  # Allows at least 2 hops (replicator + 1 more)
        ack = make_packet("ACK", self.node_id, src, seq, ack_ttl, "ok", datapackets)
        logger.debug("Sending ACK to %s seq=%d ttl=%d", src, seq, ack_ttl)
        # Use sendDataScanner pattern - retry with timeout
        startTime = time.time()
        result = False
        while True:
            if self.rfm.send(ack):
                logging.debug(f"ACK sent successfully to {src}: {datapackets} packets remaining")
                result = True
                break
            else:
                logging.debug(f"Failed to send response to {src}")

            if time.time() >= startTime + 5:
                logging.error(f"Timeout sending response to {src}")
                print(f"  → Response timeout to {src}")
                break

            time.sleep(0.1)
        return result

    def _check_duplicate(self, src, seq):
        # duplicate check (basic) - Returns True is packet is NEW
        with self.seen_lock:
            last = self.seen.get(src)
            if last is None:
                self.seen[src] = seq
                return True

            # Check if this is the same sequence number (duplicate)
            if seq == last:
                logger.debug(f"Duplicate packet seq={seq} from {src} -> discarded")
                return False

            # Handle sequence number wraparound
            # Consider packet new if:
            # 1. seq > last and difference is less than 32768 (normal increment)
            # 2. seq < last and difference is more than 32768 (wraparound)
            diff = (seq - last) & 0xFFFF
            if diff > 0 and diff < 32768:
                self.seen[src] = seq
                return True
            else:
                logger.debug(f"Old packet seq={seq} from {src} (last seen={last}) -> discarded")
                return False

    def _forward_packet(self, pkt):
        # Add random delay to avoid collisions with other nodes transmitting
        # This is especially important when server is sending ACKs at the same time
        delay = random.uniform(0.05, 0.2)  # 50-200ms random delay
        logger.debug(f"Waiting {delay:.3f}s before forwarding to avoid collision")
        time.sleep(delay)

        # create modified packet with ttl-1 and forward (keeping original src/seq)
        fwd = make_packet(pkt["type"], pkt["src"], pkt["dst"], pkt["seq"], pkt["ttl"] - 1, pkt.get("payload"), pkt.get("remaining"))
        try:
            logger.info("Forwarding pkt src=%s seq=%s ttl->%s to %s", pkt["src"], pkt["seq"], pkt["ttl"] - 1, pkt["dst"])
            self.rfm.send(fwd)
            if callable(self.on_forward):
                # Pass the packet dict, not the raw bytes
                self.on_forward(pkt, getattr(self.rfm, "last_rssi", None))
        except Exception as e:
            logger.exception("Forward failed: %s", e)

    def received(self, rx):
        pkt = parse_packet(rx)
        rssi = getattr(self.rfm, "last_rssi", None)
        if not pkt:
            logger.debug("Got non-json or unparsable packet (len=%d) rssi=%s", len(rx), rssi)
        else:
            # Filter self-packets
            if int(pkt.get("src")) == int(self.node_id):
                logger.debug("Packet from self -> discarded")
            else:
                # Check for duplicates
                if not self._check_duplicate(pkt.get("src"), pkt.get("seq")):
                    logger.debug(f"Duplicate packet from {pkt['src']} seq={pkt['seq']} - discarded")
                else:
                    # if packet addressed to me or broadcast
                    dst = pkt.get("dst", BROADCAST_ID)
                    if dst == self.node_id or dst == BROADCAST_ID:
                        logger.info("RX from=%s dst=%s seq=%s ttl=%s rssi=%s payload=%s",
                                    pkt.get("src"), dst, pkt.get("seq"), pkt.get("ttl"), rssi, str(pkt.get("payload"))[:60])
                        # auto-ACK if unicast to me
                        if dst == self.node_id and pkt.get("type") in ["MSG", "REQ"]:
                            if pkt.get("type") == "MSG":
                                try:
                                    self._send_ack(pkt["src"], pkt["seq"])
                                except Exception:
                                    logger.debug("ACK failed")
                            else:
                                try:
                                    logger.info(f"Processing REQ from {pkt['src']} seq={pkt['seq']}")
                                    # Add delay before responding to REQ to avoid collision with replicator forwarding
                                    # Longer delay needed when multiple packets will be sent
                                    time.sleep(0.5)  # 500ms delay to ensure replicator has finished forwarding
                                    if callable(self.on_request):
                                        datapackets = self.on_request(pkt)
                                        logger.info(f"on_request returned {len(datapackets)} response packets")
                                    else:
                                        datapackets = []
                                    full_package =  self._send_ack(pkt["src"], pkt["seq"],len(datapackets))
                                    for i, response in enumerate(datapackets):
                                        logger.info(f"Sending response packet {i+1}/{len(datapackets)} to {pkt['src']}")
                                        # Add small delay between packets to avoid collisions
                                        time.sleep(0.1)  # 100ms between follow-up packets
                                        tries = 0
                                        while tries < 3:
                                            if self.send_unicast(pkt["src"], response, await_ack=True, timeout=1) == False:
                                                full_package = False
                                                logger.warning(f"Failed to deliver response packet {i+1} retrying {tries}")
                                                tries += 1
                                            else:
                                                break
                                    if full_package:
                                        logger.info(f"ACK and {len(datapackets)} packets delivered successfully")
                                    else:
                                        logger.warning(f"Not all response packets were delivered")
                                except Exception as e:
                                    logger.error(f"Error processing REQ: {e}")

                            # call application hook for message
                            if callable(self.on_message):
                                try:
                                    self.on_message(pkt, rssi)
                                except Exception:
                                    logger.exception("on_message handler error")
                    else:
                        logger.exception(f"UNKNOWN PACKET - {pkt}")

    def receive_and_replicate(self, rx):
        pkt = parse_packet(rx)
        rssi = getattr(self.rfm, "last_rssi", None)
        if not pkt:
            logger.debug("Got a unparsable packet (len=%d) rssi=%s", len(rx), rssi)
        else:
            if self._check_duplicate(src = pkt.get("src"), seq = pkt.get("seq")):
                # identify source and destination
                dst = pkt.get("dst", BROADCAST_ID)
                logger.info("RX from=%s dst=%s seq=%s ttl=%s rssi=%s payload=%s",
                                pkt.get("src"), dst, pkt.get("seq"), pkt.get("ttl"), rssi, str(pkt.get("payload"))[:60])

                # call application hook for message
                if callable(self.on_message):
                    try:
                        self.on_message(pkt, rssi)
                    except Exception:
                        logger.exception("on_message handler error")

                # Replicator forwarding logic:
                # Forward all packets except those addressed to us or from us
                # The random delays will handle collision avoidance
                should_forward = False

                if pkt.get("src") == self.node_id:
                    # Never forward my own packets
                    should_forward = False
                    logger.debug("Not forwarding - packet from self")
                elif dst == self.node_id:
                    # Don't forward packets addressed to me
                    should_forward = False
                    logger.debug("Not forwarding - packet for me")
                else:
                    # Forward everything else (broadcasts, unicasts to others, ACKs)
                    should_forward = True
                    logger.debug(f"Will forward packet type={pkt.get('type')} from {pkt.get('src')} to {dst}")

                if should_forward:
                    logger.info(f"Checking if should forward packet type={pkt.get('type')} src={pkt.get('src')} dst={dst}")
                    if self._should_forward(pkt):
                        logger.info(f"Forwarding packet type={pkt.get('type')} src={pkt.get('src')} dst={dst} seq={pkt.get('seq')}")
                        self._forward_packet(pkt)
                    else:
                        logger.info("Not forwarding due to TTL expiry")