# meshstatic_new.py
"""
Refactored mesh overlay helpers for RFM95X testing.
Single receiver thread architecture to prevent packet stealing.
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
import queue
import logging
import sys

# constants
BROADCAST_ID = 0
MAX_PAYLOAD = 200  # keep below LoRa max for conservative safety
DEFAULT_TTL = 5

# Get logger for this module
logger = logging.getLogger("meshstatic_new")

# Only configure if not already configured
if not logger.handlers:
    # Centralized logging setup
    file_handler = logging.FileHandler("meshstatic_new.log")
    #console_handler = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler.setFormatter(formatter)
    #console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    #logger.addHandler(console_handler)
    logger.setLevel(logging.DEBUG)  # Set to DEBUG for better diagnostics


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
    Refactored MeshNode with single receiver thread architecture.
    All packet reception goes through one thread that dispatches to appropriate handlers.
    """
    def __init__(self, rfm, node_id:int, default_ttl=DEFAULT_TTL, auto_start=True):
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

        # Sequence number management
        self.seq_lock = threading.Lock()
        self._seq = random.randint(0, 65535)
        self.full_response = []

        # Pending ACKs and responses we're waiting for
        self.pending_acks = {}  # {(dst, seq): event}
        #self.pending_acks_lock = threading.Lock()
        #self.received_acks = {}  # {(dst, seq): (pkt, timestamp)}

        # Pending follow-up packets
        #self.pending_responses = {}  # {(src, key): queue}
        self._is_expected_response = False
        self.response_queue = {} #queue.Queue()
        #self.pending_responses_lock = threading.Lock()

        #Pending to send follow-up packets
        self._pending_to_send = False
        self.pending_fup = None

        # Start the single receiver thread if auto_start is True
        if auto_start:
            self.start_receiver()

    def start_receiver(self):
        """Start the single receiver thread"""
        if not self._running:
            self._running = True
            self._recv_thread = threading.Thread(target=self._receiver_loop, daemon=True)
            self._recv_thread.start()
            logger.info(f"Started receiver thread for node {self.node_id}")
            # Give thread time to start
            time.sleep(0.1)
            if self._recv_thread.is_alive():
                logger.info(f"Receiver thread is alive and running for node {self.node_id}")
            else:
                logger.error(f"Receiver thread failed to start for node {self.node_id}")
        else:
            logger.warning(f"Receiver thread already running for node {self.node_id}")

    def stop_receiver(self):
        """Stop the receiver thread"""
        self._running = False
        if self._recv_thread:
            self._recv_thread.join(timeout=2)
            logger.info(f"Stopped receiver thread for node {self.node_id}")

    def _receiver_loop(self):
        """Single receiver loop that handles ALL incoming packets"""
        logger.info(f"[Node {self.node_id}] Receiver loop started")
        last_status = time.time()
        packet_count = 0

        while self._running:
            try:
                # Receive with moderate timeout to ensure we don't miss packets
                # but still allow checking _running flag periodically
                rx = self.rfm.receive(with_header=True, with_ack=False, timeout=2.0)

                # Log periodic status every 10 seconds
                if time.time() - last_status > 10:
                    logger.debug(f"[Node {self.node_id}] Receiver alive - {packet_count} packets received. Send queue {self._pending_to_send}. Receive queue {self.pending_fup}. Ack queue {self.pending_acks}")
                    last_status = time.time()

                if rx is not None:
                    packet_count += 1
                    logger.info(f"[Node {self.node_id}] Raw packet received #{packet_count}: {rx.hex()[:40]}...")
                    pkt = parse_packet(rx)
                    rssi = getattr(self.rfm, "last_rssi", None)

                    if pkt:
                        logger.info(f"[Node {self.node_id}] RECEIVER Got {pkt['type']} from {pkt['src']} to {pkt['dst']} seq={pkt['seq']} ttl={pkt['ttl']} rssi={rssi}")
                        if int(pkt.get("src")) == int(self.node_id):
                            logger.debug("Packet from self -> discarded")
                        else:
                            # Check for duplicates
                            if not self._check_duplicate(pkt.get("src"), pkt.get("seq")):
                                logger.debug(f"Duplicate packet from {pkt['src']} seq={pkt['seq']} - discarded")
                            else:
                                # Route packet to appropriate handler
                                self._route_packet(pkt, rssi)
                    else:
                        logger.warning(f"[Node {self.node_id}] Got unparsable packet (len={len(rx)}) rssi={rssi}")

            except Exception as e:
                logger.error(f"[Node {self.node_id}] Receiver loop error: {e}", exc_info=True)
                time.sleep(0.1)

        logger.info(f"[Node {self.node_id}] Receiver loop stopped")

    def _route_packet(self, pkt, rssi):
        """Route received packet to appropriate handler"""
        dst = pkt.get("dst", BROADCAST_ID)
        pkt_type = pkt.get("type")

        logger.debug(f"[Node {self.node_id}] Routing packet: type={pkt_type}, src={pkt.get('src')}, dst={dst}, seq={pkt.get('seq')}")

        # Check if this is an ACK we're waiting for
        # ACKs should be routed to handler regardless of dst since they're responses
        if pkt_type == "ACK":
            logger.debug(f"[Node {self.node_id}] Routing to ACK handler")
            self._handle_ack(pkt, rssi)
            return  # Don't process ACKs further

        # Check if this is a follow-up MSG we're waiting for
        # If it is, handle it specially and DON'T auto-ACK (we'll ACK in the handler)
        elif pkt_type == "FUP" and self._is_expected_response:
            logger.debug(f"[Node {self.node_id}] Routing to FUP response handler - will ACK there")
            self._handle_expected_response(pkt, rssi)
            return  # Don't process further to avoid double ACK

        # Check if packet is for us or broadcast
        if dst == self.node_id or dst == BROADCAST_ID:
            logger.debug(f"[Node {self.node_id}] Packet is for me or broadcast - handling")
            self._handle_packet_for_me(pkt, rssi)

        # Otherwise, consider forwarding (for replicator mode)
        else:
            logger.debug(f"[Node {self.node_id}] Packet not for me (dst={dst}), considering forward")

    def _handle_ack(self, pkt, rssi):
        """Handle received ACK packets"""
        src = pkt.get("src")
        #The ACK message will have it's own sequecence number but will send the original sequence as payload
        seq = int(pkt.get("payload"))
        dst = pkt.get("dst")

        logger.info(f"[Node {self.node_id}] Handling ACK from {src} to {dst} for seq {seq}")

        # The key should be (src, seq) where src is who we expect the ACK from
        if src in self.pending_acks:
            if seq in self.pending_acks[src]:
                #If Ack was on the list, confirm received and remove from the pending list
                self.pending_acks[src].remove(seq)
                logger.info(f"[Node {self.node_id}] ACK matched and signaled for src={src} seq={seq} rssi={rssi}")

                #Flow to Control receiving multiple packages after ACK
                remaining = pkt.get("remaining", 0)
                if remaining > 0:
                    logger.info(f"ACK received from {src} for seq {seq} with {remaining} follow-up packets")
                    # Wait for follow-up packets
                    self._is_expected_response = True
                    self.response_queue[src] = int(remaining)
                    #return_messages = self._wait_for_responses(dst, remaining, timeout=10.0)
                else:
                    logger.info(f"ACK received from {dst} for seq {seq} with NO follow-up packets")
                    self.full_response = []

                #Flow to Control sending follow up messages as ACKs are being received async
                if self._pending_to_send:
                    if len(self.pending_fup) == 0:
                        self._pending_to_send = False
                        logger.info(f"Disabling pending queue, No additional Packets to deliver")
                    else:
                        if self.send_unicast(pkt["src"], self.pending_fup.pop(0), await_ack=True):
                            logger.info(f"Packet delivered successfully. {len(self.pending_fup)} remaining")
                else:
                    logger.info(f"No additional Packets to deliver")


                return True

            else:
                logger.info(f"WARNING: {seq} not found in {self.pending_acks[src]}")
                return False

        else:
            # Log all pending ACKs to help debug
            logger.warning(f"[Node {self.node_id}] Unexpected ACK from {src} seq={seq}")
            logger.debug(f"[Node {self.node_id}] Pending ACKs: {list(self.pending_acks.keys())}")
            return True

    def _handle_expected_response(self, pkt, rssi):
        """Handle expected follow-up response packets"""
        #src = pkt.get("src")
        #self.response_queue.put((pkt, rssi))
        #logger.info(f"Received expected response from {src}: {pkt['payload'][:40]}")
        if self.response_queue.get(pkt['src'], 0) > 0:
            self.full_response.append(pkt.get("payload"))
            # Send ACK for this follow-up packet
            msg_seq = pkt.get("seq")
            remaining_to_receive = self.response_queue.get(pkt['src'])
            logger.info(f"[Node {self.node_id}] Received follow-up packet {len(self.full_response)}/{remaining_to_receive}")
            self._send_ack(pkt['src'], msg_seq, 0)
            remaining_to_receive = remaining_to_receive - 1
            if remaining_to_receive == 0:
                self._is_expected_response = False
                self.response_queue.pop(pkt['src'])
                logger.info(f"[Node {self.node_id}] No more packets Remaining to receive")
                self._handle_return_complete()
            else:
                self.response_queue[pkt['src']] = remaining_to_receive
                logger.info(f"[Node {self.node_id}] Remaining to receive {remaining_to_receive}")

            return True
        else:
            logger.info(f"[Node {self.node_id}] Got packet from {pkt['src']} but was expecting {self.response_queue}")
        return

    def _handle_return_complete(self):
        for message in self.full_response:
            logger.info(f"Response message: {message}")
        self.full_response = []
        return True

    def _handle_packet_for_me(self, pkt, rssi):
        """Handle packets addressed to this node or broadcast"""
        dst = pkt.get("dst", BROADCAST_ID)
        pkt_type = pkt.get("type")

        logger.info(f"[Node {self.node_id}] RX from={pkt['src']} dst={dst} seq={pkt['seq']} ttl={pkt['ttl']} rssi={rssi} payload={str(pkt.get('payload'))[:60]}")

        # Auto-ACK if unicast to me
        if dst == self.node_id and pkt_type in ["MSG", "REQ"]:
            if pkt_type == "MSG":
                try:
                    logger.debug(f"[Node {self.node_id}] Auto-ACKing MSG from {pkt['src']} seq={pkt['seq']}")
                    self._send_ack(pkt["src"], pkt["seq"])
                except Exception as e:
                    logger.error(f"ACK failed: {e}")
            else:  # REQ
                try:
                    logger.info(f"Processing REQ from {pkt['src']} seq={pkt['seq']}")
                    # Add delay before responding to REQ to avoid collision with replicator forwarding
                    time.sleep(0.5)  # 500ms delay to ensure replicator has finished forwarding

                    if callable(self.on_request):
                        datapackets = self.on_request(pkt)
                        logger.info(f"on_request returned {len(datapackets)} response packets")
                    else:
                        datapackets = []

                    full_package = self._send_ack(pkt["src"], pkt["seq"], len(datapackets))

                    if len(datapackets) > 0:
                        logger.info(f"[Node {self.node_id}] Sending response packet 1/{len(datapackets)} to {pkt['src']}")
                        # Send first packet with await_ack - this will triger async wait for client to ACK this specific MSG
                        if self.send_unicast(pkt["src"], datapackets.pop(0), await_ack=True):
                            logger.info(f"First Response packets delivered successfully")
                            #Check for remaining packets and add to queue to be delivered as the ACKs come
                            if len(datapackets) > 0:
                                self._pending_to_send = True
                                self.pending_fup = datapackets
                        else:
                            logger.warning(f"[Node {self.node_id}] Failed to deliver response packet 1 to {pkt['src']}")
                    else:
                        logger.info(f"ACK successfully delivered with NO additional packets")

                except Exception as e:
                    logger.error(f"Error processing REQ: {e}")

        # Call application hook for message
        if callable(self.on_message):
            try:
                self.on_message(pkt, rssi)
            except Exception:
                logger.exception("on_message handler error")

    def _next_seq(self):
        with self.seq_lock:
            self._seq = (self._seq + 1) & 0xFFFF
            return self._seq

    def _check_duplicate(self, src, seq):
        """Check if packet is duplicate - Returns True if packet is NEW"""
        #with self.seen_lock:
        last = self.seen.get(src)
        if last is None:
            self.seen[src] = seq
            logger.debug(f"First Packet from {src} seq={seq}")
            return True

        # Check if this is the same sequence number (duplicate)
        if seq == last:
            logger.debug(f"Duplicate packet seq={seq} from {src} -> discarded")
            return False
        else:
            logger.debug(f"Valid seq={seq} from {src}, last seen={self.seen}")

            # Handle sequence number wraparound
            # Consider packet new if:
            # 1. seq > last and difference is less than 32768 (normal increment)
            # 2. seq < last and difference is more than 32768 (wraparound)
            diff = (seq - last) & 0xFFFF
            if diff > 0 and diff < 32768:
                self.seen[src] = seq
                logger.debug(f"New Packet from {src} seq={seq}, last seen={last} -> accepted ")
                return True
            else:
                logger.debug(f"Old packet seq={seq} from {src} (last seen={last}) -> discarded")
                return False

    def _send_ack(self, src, seq, datapackets: int = 0):
        # Use higher TTL for ACKs to ensure they can be forwarded through mesh
        ack_ttl = 3  # Allows at least 2 hops (replicator + 1 more)
        # ACK packet: src=me, dst=original_sender, seq=THEIR seq (the one we're ACKing)
        #The original SEQ will be sent as payload to match the packet and a new SEQ is created to improve flow control
        msg_seq = self._next_seq()
        ack = make_packet("ACK", self.node_id, src, msg_seq, ack_ttl, seq, datapackets)
        logger.info(f"[Node {self.node_id}] Sending ACK to {src} for THEIR seq={seq} ttl={ack_ttl}")

        # Just send once, don't retry for long
        result = self.rfm.send(ack)
        if result:
            logger.debug(f"ACK sent successfully to {src}: {datapackets} packets remaining")
        else:
            logger.error(f"Failed to send ACK to {src}")

        return result

    def send_request(self, dst, payload, await_ack=False, ttl=None):
        """Send a REQ packet and optionally wait for ACK and follow-up packets"""
        dst = int(dst)
        ttl = self.default_ttl if ttl is None else int(ttl)
        seq = self._next_seq()
        pkt_bytes = make_packet("REQ", self.node_id, dst, seq, ttl, payload)
        logger.info("TX -> dst=%s seq=%d ttl=%d payload=%s len=%d", dst, seq, ttl, str(payload)[:40], len(pkt_bytes))

        # Send the packet
        send_result = self.rfm.send(pkt_bytes)
        logger.info(f"Send result: {send_result}")

        if await_ack and dst != BROADCAST_ID:
            logger.info("Register Pending ACK")
            #Once the message is sent, add it to the list of pending ACKs
            if dst in self.pending_acks:
                self.pending_acks[dst].append(int(seq))
            else:
                self.pending_acks[dst] = [int(seq)]

            logger.info(f"List of pending ACKs: {self.pending_acks}")

            return True

        else:
            logger.info('bypass ACK')
            return True

    def send_unicast(self, dst, payload, await_ack=False, ttl=None):
        """Send a unicast FUP packet and optionally wait for ACK"""
        dst = int(dst)
        ttl = self.default_ttl if ttl is None else int(ttl)
        seq = self._next_seq()
        pkt_bytes = make_packet("FUP", self.node_id, dst, seq, ttl, payload)
        logger.info("TX -> dst=%s seq=%d ttl=%d payload=%s len=%d", dst, seq, ttl, str(payload)[:40], len(pkt_bytes))

        send_result = self.rfm.send(pkt_bytes)
        logger.debug(f"Send unicast result: {send_result}")

        if await_ack and dst != BROADCAST_ID:
            logger.debug(f"[Node {self.node_id}] Waiting for ACK from {dst} with seq {seq}")
            #Once the message is sent, add it to the list of pending ACKs
            if dst in self.pending_acks:
                self.pending_acks[dst].append(int(seq))
            else:
                self.pending_acks[dst] = [int(seq)]
        else:
            logger.info('bypass ACK')
        return True

    def send_broadcast(self, payload, ttl=None):
        """Send a broadcast MSG packet"""
        ttl = self.default_ttl if ttl is None else int(ttl)
        seq = self._next_seq()
        pkt_bytes = make_packet("MSG", self.node_id, BROADCAST_ID, seq, ttl, payload)
        logger.info("BCAST TX seq=%d ttl=%d payload=%s", seq, ttl, str(payload)[:40])
        self.rfm.send(pkt_bytes)
        return True

class ReplicatorNode(MeshNode):
    """
    Specialized node for replicator mode with forwarding enabled.
    Overrides the receiver to enable forwarding logic.
    """
    def __init__(self, rfm, node_id: int, default_ttl=DEFAULT_TTL, auto_start=True):
        self.forwarding_enabled = True
        super().__init__(rfm, node_id, default_ttl, auto_start)

    def _should_forward(self, pkt):
        """Check if packet should be forwarded based on TTL"""
        if pkt.get("ttl", 0) <= 1:
            logger.info(f"TTL expired for SEQ: {pkt.get('seq')} Source: {pkt.get('src')}")
            return False
        else:
            logger.info(f"TTL Valid for SEQ: {pkt.get('seq')} Source: {pkt.get('src')}")
            return True

    def _forward_packet(self, pkt):
        """Forward a packet with TTL-1"""
        # Add random delay to avoid collisions with other nodes transmitting
        delay = random.uniform(0.05, 0.2)  # 50-200ms random delay
        logger.debug(f"Waiting {delay:.3f}s before forwarding to avoid collision")
        time.sleep(delay)

        # create modified packet with ttl-1 and forward (keeping original src/seq)
        fwd = make_packet(pkt["type"], pkt["src"], pkt["dst"], pkt["seq"], pkt["ttl"] - 1,
                         pkt.get("payload"), pkt.get("remaining"))
        try:
            logger.info("Forwarding pkt src=%s seq=%s ttl->%s to %s",
                       pkt["src"], pkt["seq"], pkt["ttl"] - 1, pkt["dst"])
            self.rfm.send(fwd)
            if callable(self.on_forward):
                self.on_forward(pkt, getattr(self.rfm, "last_rssi", None))
        except Exception as e:
            logger.exception("Forward failed: %s", e)

    def _route_packet(self, pkt, rssi):
        """Extended routing for replicator - includes forwarding logic"""

        # Then check if we should forward
        dst = pkt.get("dst", BROADCAST_ID)
        should_forward = False

        if dst == self.node_id:
            # Don't forward packets addressed to me
            should_forward = False
            logger.debug("Not forwarding - packet for me")
        else:
            # Forward everything else (broadcasts, unicasts to others, ACKs)
            should_forward = True
            logger.debug(f"Will forward packet type={pkt.get('type')} from {pkt.get('src')} to {dst}")

        if should_forward and self._should_forward(pkt):
            logger.info(f"Forwarding packet type={pkt.get('type')} src={pkt.get('src')} dst={dst} seq={pkt.get('seq')}")
            self._forward_packet(pkt)


