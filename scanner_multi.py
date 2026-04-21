"""
IQRight Multi-Mode Scanner

Dual-mode scanner application that combines:
- Scanner Mode (default): Full LoRa server communication with break/release/search
- Validation Mode: Offline local CSV lookup for data validation and problem documentation

Toggle between modes using the mode button in the header bar.

Usage:
    python scanner_multi.py
"""
import datetime
import tkinter as tk
from tkinter import messagebox
from tksheet import Sheet
from threading import Thread
import time
import threading
import queue
import logging
import logging.handlers
import os
import re
from utils.config import LORA_FREQUENCY, LORA_TX_POWER, LORA_ENABLE_CA, HOME_DIR, LORA_NODE_ID, IDFACILITY
from utils.matching_engine import StudentMatcher


if os.getenv("LOCAL", "FALSE") != "TRUE":
    import serial
    import RPi.GPIO as GPIO
    from lora import LoRaTransceiver, LoRaPacket, PacketType, NodeType, MultiPartFlags, CollisionAvoidance


debug = False

# LOGGING Setup
log_filename = "logs/IQRight_Scanner.debug"
os.makedirs("logs", exist_ok=True)
max_log_size = 20 * 1024 * 1024  # 20Mb
backup_count = 10
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Single handler — daily rotation at midnight (avoids duplicate lines)
log_handler = logging.handlers.TimedRotatingFileHandler(
    log_filename, when='midnight', interval=1, backupCount=backup_count
)
log_handler.setFormatter(log_formatter)
log_handler.suffix = "%Y-%m-%d"

logging.getLogger().addHandler(log_handler)
logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)


# ---------------------------------------------------------------------------
# Validation Mode helpers (module-level, lazy-loaded)
#
# Uses the same students.csv file that the StudentMatcher (search) uses —
# a single source of truth for both modes. See utility_tools/extract_students_csv.py
# for how to generate this file from the authoritative full_load.iqr.
# ---------------------------------------------------------------------------
_validation_df = None


def _load_validation_db():
    """Lazy-load the shared students.csv. Only imports pandas on first call."""
    global _validation_df
    if _validation_df is not None:
        return _validation_df
    import pandas as pd
    csv_path = os.path.join(HOME_DIR, "data", "students.csv")
    if not os.path.exists(csv_path):
        csv_path = os.path.join("data", "students.csv")
    _validation_df = pd.read_csv(csv_path)
    _validation_df['DeviceID'] = _validation_df['DeviceID'].astype(str)
    logging.info(f"Validation DB loaded: {len(_validation_df)} rows from {csv_path}")
    return _validation_df


def _lookup_validation_db(code: str):
    """Look up a QR code in students.csv. Returns list of dicts or None.

    Returns ChildName and ClassCode — same format as the server's response
    in scanner mode. ClassCode already embeds grade + teacher (e.g., "4P").
    """
    if not code:
        return None
    try:
        df = _load_validation_db()
        filtered = df[df['DeviceID'] == code]
        dedup_col = 'ChildName' if 'ChildName' in df.columns else 'FirstName'
        matches = filtered.drop_duplicates(subset=[dedup_col])
        if matches.empty:
            return None
        results = []
        for _, row in matches.iterrows():
            name = row['ChildName'] if 'ChildName' in df.columns else f"{row['FirstName']} {row['LastName']}"
            class_code = row['ClassCode'] if 'ClassCode' in df.columns else ''
            results.append({
                "name": name,
                "classCode": str(class_code).strip(),
            })
        return results
    except Exception as e:
        logging.error(f"Validation lookup error for {code}: {e}")
        return None


def _format_grade(grade_str: str) -> str:
    """Convert full grade name or code to abbreviation."""
    if not grade_str:
        return 'N/A'
    g = grade_str.strip()
    if g == 'First Grade' or g[:2] == '01':
        return '1st'
    if g == 'Second Grade' or g[:2] == '02':
        return '2nd'
    if g == 'Third Grade' or g[:2] == '03':
        return '3rd'
    if g == 'Fourth Grade' or g[:2] == '04':
        return '4th'
    if g == 'Fifth Grade' or g[:2] == '05':
        return '5th'
    if g == 'Sixth Grade' or g[:2] == '06':
        return '6th'
    if g == 'Seventh Grade' or g[:2] == '07':
        return '7th'
    if g == 'Eighth Grade' or g[:2] == '08':
        return '8th'
    if 'Kinder' in g:
        return 'Kind'
    return 'N/A'


# ---------------------------------------------------------------------------
# Serial Thread (QR scanner hardware)
# ---------------------------------------------------------------------------
class SerialThread(Thread):
    def __init__(self, queue):
        Thread.__init__(self)
        self._kill = threading.Event()
        self._interval = 10
        self.queue = queue
        self.delay = 0.1
        self.inPin = 21
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.inPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.ser = serial.Serial("/dev/serial0", 115200, timeout=2)
        self.control = False

    VALID_QR_PATTERN = re.compile(r'^P\d{7,9}$')

    def clean_qr_code(self, raw_read: str, log_debug: bool = True) -> str:
        logging.debug(f"Raw input ({len(raw_read)} bytes): {repr(raw_read)}")
        fragments = re.split(r'[^0-9A-Za-z]+', raw_read)
        fragments = [f for f in fragments if len(f) > 0]
        logging.debug(f"Fragments after protocol split: {fragments}")

        for frag in fragments:
            cleaned = re.sub(r'[^0-9Pp]', '', frag).upper()
            stripped = cleaned
            while stripped.startswith('31'):
                stripped = stripped[2:]
            if self.VALID_QR_PATTERN.match(stripped):
                logging.debug(f"Valid QR code from fragment: {stripped}")
                return stripped

        cleaned = re.sub(r'[^0-9Pp]', '', raw_read).upper()
        stripped = cleaned
        while stripped.startswith('31'):
            stripped = stripped[2:]

        if len(stripped) > 12:
            match = re.match(r'(P\d{7,9})', stripped)
            if match:
                logging.warning(f"Double-read detected ({len(stripped)} chars): {stripped} -> extracting: {match.group(1)}")
                return match.group(1)
            logging.warning(f"Double-read but no valid pattern found: {stripped}")

        if self.VALID_QR_PATTERN.match(stripped):
            logging.info(f"After filter: {cleaned} -> After 31-strip: {stripped}")
            return stripped

        logging.warning(f"Invalid QR after cleaning: {stripped} (from raw: {repr(raw_read[:40])})")
        return stripped

    def run(self):
        try:
            while True:
                pressed = GPIO.input(self.inPin)
                if pressed == 0:
                    logging.debug('Write Serial')
                    self.ser.write(bytes.fromhex("7E000801000201ABCD"))
                    time.sleep(0.1)
                    logging.debug('Read Serial Blank')
                    blankReturn = self.ser.read()
                    logging.debug(f'blank read: {blankReturn}')
                    time.sleep(1.3)
                    remaining = self.ser.inWaiting()
                    serialRead = self.ser.read(remaining)
                    strRead = str(serialRead, encoding="UTF-8")
                    if len(strRead) > 6:
                        logging.info(f"full read from scanner({len(strRead)} bytes): {strRead}")
                        qrCode = strRead.strip()
                        qrCode = self.clean_qr_code(qrCode)
                        logging.info(f"Clean QRCode ({len(qrCode)} bytes): {qrCode}")
                        if self.VALID_QR_PATTERN.match(qrCode):
                            self.queue.put(qrCode)
                            logging.info(f'PUTTING in the Queue: {qrCode}')
                        else:
                            # Send invalid codes to the queue with prefix so UI can display them
                            self.queue.put(f"INVALID:{qrCode}")
                            logging.warning(f"Rejected invalid QR code: {qrCode}")
                    else:
                        logging.info(f'Invalid String captured from Serial: {strRead}')
                is_killed = self._kill.wait(1)
                if is_killed:
                    break
        except Exception as e:
            logging.info(e)

    def kill(self):
        self._kill.set()


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        # LoRa transceiver setup
        self.scanner_node_id = LORA_NODE_ID
        self.server_node_id = IDFACILITY

        if os.getenv("LOCAL", "FALSE") != "TRUE":
            self.transceiver = LoRaTransceiver(
                node_id=self.scanner_node_id,
                node_type=NodeType.SCANNER,
                frequency=LORA_FREQUENCY,
                tx_power=LORA_TX_POWER
            )
        else:
            self.transceiver = None

        # Shared state
        self.lstCode = []
        self.car_number = 0
        self.breakLineList: list = []
        self.lastReleaseRow = 0
        self.lastCommand = None
        self.previousCommand = None
        self.matcher = None  # Lazy-loaded on first search

        # Mode: "scanner" (default) or "validation"
        self.mode = "scanner"
        self.validation_log: list = []  # Problem documentation

        # Initialize Tkinter
        tk.Tk.__init__(self)
        screenWidth = self.winfo_screenwidth()
        self.attributes('-fullscreen', True)
        self.title("Main Entrance")
        self.configure(bg='white')

        # --- Upper frame (header bar) ---
        self.upperFrame = tk.Frame(height=100, bg="blue")

        # Mode toggle button (top-right)
        self.btn_mode = tk.Button(
            master=self.upperFrame, text="VAL", font=("Arial", 11, "bold"),
            fg="white", bg="#555555", activebackground="#777777",
            width=5, bd=0, command=self._toggle_mode
        )
        self.btn_mode.pack(side=tk.RIGHT, padx=6, pady=4)

        tk.Label(master=self.upperFrame, text="(A)SVDP - East Side",
                 font=("Arial", 18), fg="white", bg="blue").pack()
        self.lbl_name = tk.Label(master=self.upperFrame, text="Ready to Scan",
                                 font=("Arial", 18), fg="white", bg="blue")
        self.lbl_status = tk.Label(master=self.upperFrame, text="Idle",
                                   font=("Arial", 14), fg="white", bg="blue")
        self.lbl_name.pack()
        self.lbl_status.pack()

        # --- Sheet frame ---
        bottomFrame = tk.Frame(height=550, bg="white")
        self.sheet = Sheet(bottomFrame, headers=['Car', 'Name', 'Class'],
                           empty_vertical=0, height=550, width=screenWidth,
                           font=("Arial", 18, "normal"),
                           header_font=("Arial", 18, "normal"),
                           show_row_index=False)
        self.sheet.column_width(0, 60)
        self.sheet.column_width(1, 310)
        self.sheet.column_width(2, 100)
        self.sheet.pack(fill=tk.X)

        # --- Button bar ---
        self.barFrame = tk.Frame(height=60, bg="white", width=480)
        bar_font = ("Arial", 12)

        # Scanner mode buttons
        self.btn_break = tk.Button(master=self.barFrame, text="Break", font=bar_font,
                                   height=4, fg="blue", command=self.breakQueue)
        self.btn_release = tk.Button(master=self.barFrame, text="Release", font=bar_font,
                                     height=4, fg="blue", command=self.releaseQueue)
        self.btn_undo = tk.Button(master=self.barFrame, text="Undo", font=bar_font,
                                  height=4, fg="blue", command=self.undoLast)

        # Validation mode buttons
        self.btn_problem = tk.Button(master=self.barFrame, text="Problem", font=bar_font,
                                     height=4, fg="red", command=self._mark_problem)
        self.btn_note = tk.Button(master=self.barFrame, text="Note", font=bar_font,
                                  height=4, fg="purple", command=self._open_note_overlay)

        # Common buttons (always visible)
        self.btn_search = tk.Button(master=self.barFrame, text="Search", font=bar_font,
                                    height=4, fg="blue", command=self.openSearch)
        self.btn_refresh = tk.Button(master=self.barFrame, text="Reset", font=bar_font,
                                     height=4, fg="blue", command=self.retry_hello_handshake)
        self.btn_quit = tk.Button(master=self.barFrame, text="Quit", font=bar_font,
                                  height=4, fg="blue", command=self.quitScanner)

        # Pack scanner buttons by default
        self._show_scanner_buttons()

        self.upperFrame.pack(fill=tk.X)
        bottomFrame.pack(fill=tk.X)
        self.barFrame.pack(fill=tk.X)

        # Start serial thread
        if os.getenv("LOCAL", "FALSE") != "TRUE":
            self.queue = queue.Queue()
            self.thread = SerialThread(self.queue)
            self.thread.start()

        # HELLO handshake — don't block startup on failure (validation mode works without server)
        if self._perform_hello_handshake():
            self.btn_refresh.config(command=self.screenCleanup)
        else:
            self._handle_hello_failure()

        # Always start serial processing — validation mode needs it even without handshake
        if os.getenv("LOCAL", "FALSE") != "TRUE":
            self.process_serial()

    # -----------------------------------------------------------------------
    # Mode toggle
    # -----------------------------------------------------------------------
    def _toggle_mode(self):
        if self.mode == "scanner":
            self._enter_validation_mode()
        else:
            self._enter_scanner_mode()

    def _reset_session(self):
        """Clear sheet + all session state. Called on every mode switch."""
        self.lstCode = []
        self.car_number = 0
        self.lastReleaseRow = 0
        self.breakLineList = []
        self.validation_log = []
        total = self.sheet.get_total_rows()
        if total > 0:
            self.sheet.delete_rows([x for x in range(0, total)], redraw=True)

    def _enter_validation_mode(self):
        # Lazy-load the validation DB
        self.lbl_status.config(text="Loading validation data...", bg="yellow", fg="black")
        self.update()
        try:
            _load_validation_db()
        except Exception as e:
            logging.error(f"Failed to load validation DB: {e}")
            self.lbl_status.config(text="Validation data unavailable", bg="red", fg="white")
            return

        self.mode = "validation"
        logging.info("[MODE] Switched to VALIDATION mode - session cleared")

        # Clear the sheet and session state
        self._reset_session()

        # Visual: header amber, button shows LIVE
        self.upperFrame.config(bg="#d97706")
        self.lbl_name.config(text="VALIDATION MODE", bg="#d97706", fg="white")
        self.lbl_status.config(text="Ready - Local Lookup", bg="green", fg="white")
        self.btn_mode.config(text="LIVE", bg="#16a34a", activebackground="#15803d")

        self._show_validation_buttons()

    def _enter_scanner_mode(self):
        self.mode = "scanner"
        logging.info("[MODE] Switched to SCANNER mode - session cleared")

        # Export any validation log before clearing
        if self.validation_log:
            self._export_validation_log()

        # Clear the sheet and session state
        self._reset_session()

        # Visual: header blue, button shows VAL
        self.upperFrame.config(bg="blue")
        self.lbl_name.config(text="Ready to Scan", bg="blue", fg="white")
        self.lbl_status.config(text="Ready", bg="green", fg="white")
        self.btn_mode.config(text="VAL", bg="#555555", activebackground="#777777")

        self._show_scanner_buttons()

    def _show_scanner_buttons(self):
        """Show Break/Release/Undo, hide Problem/Note."""
        for btn in [self.btn_break, self.btn_release, self.btn_undo,
                    self.btn_problem, self.btn_note,
                    self.btn_search, self.btn_refresh, self.btn_quit]:
            btn.pack_forget()
        # Repack in order
        for btn in [self.btn_break, self.btn_release, self.btn_undo,
                    self.btn_search, self.btn_refresh, self.btn_quit]:
            btn.pack(fill='x', expand=True, side=tk.LEFT)

    def _show_validation_buttons(self):
        """Show Problem/Note, hide Break/Release/Undo."""
        for btn in [self.btn_break, self.btn_release, self.btn_undo,
                    self.btn_problem, self.btn_note,
                    self.btn_search, self.btn_refresh, self.btn_quit]:
            btn.pack_forget()
        # Repack in order
        for btn in [self.btn_problem, self.btn_note,
                    self.btn_search, self.btn_refresh, self.btn_quit]:
            btn.pack(fill='x', expand=True, side=tk.LEFT)

    # -----------------------------------------------------------------------
    # HELLO handshake
    # -----------------------------------------------------------------------
    def _perform_hello_handshake(self) -> bool:
        if os.getenv("LOCAL", "FALSE") == "TRUE":
            logging.info("LOCAL mode: skipping HELLO handshake")
            return True
        logging.info(f"Initiating HELLO handshake with server (node {self.server_node_id})")
        self.lbl_status.config(text="Connecting to server...", bg="yellow")
        self.update()
        success = self.transceiver.send_hello_handshake(
            dest_node=self.server_node_id, timeout=3.0, max_retries=3
        )
        if success:
            logging.info("HELLO handshake successful - ready to scan")
            self.lbl_status.config(text="Ready", bg="green")
        else:
            logging.error("HELLO handshake failed - cannot communicate with server")
            self.lbl_status.config(text="Server Handshake Failed!", bg="red")
        return success

    def _handle_hello_failure(self):
        self.lbl_name.config(text="CONNECTION ERROR", bg="red", fg="white")
        self.lbl_status.config(text="Server Handshake Failed!", bg="red", fg="white")
        self.btn_break.config(state=tk.DISABLED)
        self.btn_release.config(state=tk.DISABLED)
        self.btn_undo.config(state=tk.DISABLED)
        logging.error("Scanner in error state - user must retry handshake or quit")
        self.update()

    def retry_hello_handshake(self):
        logging.info("User requested HELLO handshake retry")
        self.lbl_name.config(text="Retrying connection...", bg="blue", fg="white")
        self.lbl_status.config(text="Connecting to server...", bg="yellow", fg="black")
        self.update()
        if self._perform_hello_handshake():
            logging.info("HELLO retry successful")
            self.lbl_name.config(text="Ready to Scan", bg="blue", fg="white")
            self.lbl_status.config(text="Ready", bg="green", fg="white")
            self.btn_break.config(state=tk.NORMAL)
            self.btn_release.config(state=tk.NORMAL)
            self.btn_undo.config(state=tk.NORMAL)
            self.btn_refresh.config(command=self.screenCleanup)
            if os.getenv("LOCAL", "FALSE") != "TRUE":
                if not hasattr(self, 'processing_started'):
                    self.processing_started = True
                    self.process_serial()
        else:
            logging.error("HELLO retry failed")
            self._handle_hello_failure()

    # -----------------------------------------------------------------------
    # LoRa communication (scanner mode)
    # -----------------------------------------------------------------------
    def lora_receiver(self, cmd: bool):
        startTime = time.time()
        confirmationReceived = False
        list_received = []

        while True:
            logging.info('Waiting for packet from Server')
            packet = self.transceiver.receive_packet(timeout=0.5)

            if packet is not None:
                logging.info(f'[RX] Response from Server: {packet}')
                try:
                    strPayload = packet.payload.decode('utf-8')
                    logging.info(f'[RX] Payload: {strPayload}')
                    response = strPayload.split("|")

                    if cmd:
                        if response[1] == 'ack' and response[2] == self.lastCommand:
                            self.lbl_name.config(text="Ready to Scan", bg="blue", fg="white")
                            self.lbl_status.config(text='CMD Confirmed ')
                            logging.info('SERVER ACK TRUE')
                            return True
                        else:
                            logging.info('SERVER ACK FALSE')
                            return False
                    else:
                        name = response[0]

                        if name == 'NOT_FOUND':
                            not_found_code = response[1] if len(response) > 1 else 'unknown'
                            logging.warning(f"[NOT_FOUND] Code {not_found_code} not found on server")
                            self.lbl_name.config(text=f"{not_found_code}", bg="blue", fg="white")
                            self.lbl_status.config(text="CODE NOT FOUND", bg="orange", fg="black")
                            self.after(3000, lambda: self.lbl_status.config(text="Ready", bg="green", fg="white"))
                            self._last_response_not_found = True
                            return True

                        if name == 'RESTRICTED':
                            restricted_code = response[1] if len(response) > 1 else 'unknown'
                            logging.warning(f"[RESTRICTED] Code {restricted_code} is restricted grade")
                            self.lbl_name.config(text=f"{restricted_code}", bg="blue", fg="white")
                            self.lbl_status.config(text="NOT IN CAR LINE", bg="orange", fg="black")
                            self.after(3000, lambda: self.lbl_status.config(text="Ready", bg="green", fg="white"))
                            self._last_response_not_found = True
                            return True

                        class_code = response[1]
                        list_received.append({"name": name, "classCode": class_code})

                        if packet.is_multi_part():
                            logging.info(f"Received packet {packet.multi_part_index}/{packet.multi_part_total}")
                            if packet.multi_flags & MultiPartFlags.LAST:
                                confirmationReceived = True
                                break
                        else:
                            confirmationReceived = True
                            break

                except UnicodeDecodeError as e:
                    logging.error(f'Invalid UTF-8 in packet payload: {e}')
                    return False
                except Exception as e:
                    logging.error(f'Error processing packet: {e}')
                    return False

            if time.time() >= startTime + 3:
                logging.warning('[RX] TIMEOUT waiting for response from Server')
                return False

        if confirmationReceived:
            self.car_number += 1
            for student in list_received:
                self.sheet.insert_row([self.car_number, student["name"], student["classCode"]], redraw=True)
            last_row = self.sheet.get_total_rows() - 1
            if last_row >= 0:
                self.sheet.see(last_row, 0)
            if list_received:
                last = list_received[-1]
                self.lbl_name.config(text=f"{last['name']} - {last['classCode']}", bg="blue", fg="white")
                self.lbl_status.config(text=f"Queue Confirmed ({len(list_received)} students)")
            return True
        return False

    def lora_sender(self, sending: bool, payload: str, cmd: bool = False, serverResponseTimeout: int = 3):
        try:
            startTime = time.time()
            cont = 0
            self.lbl_name.config(text="Waiting for Server...", bg="yellow", fg="black")
            self.update_idletasks()

            while sending:
                cont += 1
                msg = f"{self.scanner_node_id}|{payload}|1"

                if cmd:
                    packet = self.transceiver.create_cmd_packet(
                        dest_node=self.server_node_id,
                        command=payload.split(':')[1]
                    )
                else:
                    packet = self.transceiver.create_data_packet(
                        dest_node=self.server_node_id,
                        payload=msg.encode('utf-8'),
                        use_ack=True
                    )

                logging.info(f"[TX] Sending ({cont}): {msg} | seq={packet.sequence_num}")

                if LORA_ENABLE_CA and self.transceiver.rfm9x:
                    data = packet.serialize()
                    success = CollisionAvoidance.send_with_ca(
                        self.transceiver.rfm9x, data, max_retries=3,
                        enable_rx_guard=True, enable_random_delay=True
                    )
                else:
                    success = self.transceiver.send_packet(packet, use_ack=True)

                if not success:
                    logging.warning(f"[TX] LoRa send failed ({cont}): {payload} | seq={packet.sequence_num}")
                    self.lbl_status.config(text=f"Error sending to Server - {cont}", bg="red")
                else:
                    logging.info(f"[TX] Send OK ({cont}): {payload} | seq={packet.sequence_num}")
                    self.lbl_status.config(text=f"Info sent to Server - {cont}", bg="green")
                    if self.lora_receiver(cmd):
                        if not cmd and not getattr(self, '_last_response_not_found', False):
                            self.lstCode.append(payload)
                        self._last_response_not_found = False
                        sending = False
                        return True

                if time.time() >= startTime + serverResponseTimeout:
                    logging.warning(f"[TX] FAILED after {cont} attempts: {payload}")
                    self.lbl_name.config(text="No Response", bg="red", fg="white")
                    self.lbl_status.config(text=f"Ack not received - {cont}", bg="red")
                    return False
        except Exception as e:
            logging.error(f"Error sending to Server: {e}")
            self.lbl_name.config(text="Communication Error", bg="red", fg="white")
            return False

    def _send_critical_command(self, payload: str) -> bool:
        if self.lora_sender(sending=True, payload=payload, cmd=True, serverResponseTimeout=10):
            return True
        logging.warning(f"[CMD-RETRY] First attempt failed for {payload}, retrying...")
        self.lbl_status.config(text="Retrying command...", bg="yellow", fg="black")
        return self.lora_sender(sending=True, payload=payload, cmd=True, serverResponseTimeout=10)

    def _flash_status(self, text: str, bg: str, fg: str = "white"):
        self.lbl_status.config(text=text, bg=bg, fg=fg)
        self.after(3000, lambda: self.lbl_status.config(text="Ready", bg="green", fg="white"))

    def _submit_with_retry(self, payload: str, max_auto_retries: int = 3):
        """Submit a code to the server with automatic retries before prompting."""
        for attempt in range(1, max_auto_retries + 1):
            if self.lora_sender(sending=True, payload=payload):
                return True
            logging.warning(f"[RETRY] Auto-retry {attempt}/{max_auto_retries} for {payload}")
            self.lbl_status.config(text=f"Retry {attempt}/{max_auto_retries}...", bg="yellow", fg="black")
            self.update_idletasks()

        # All auto-retries exhausted — ask user
        retry = messagebox.askyesno("No Response",
                                    f"Server did not respond after {max_auto_retries} attempts.\nResubmit {payload}?")
        if retry:
            logging.info(f"[RETRY] User requested resubmit for {payload}")
            return self._submit_with_retry(payload, max_auto_retries)

        logging.info(f"[RETRY] User declined resubmit for {payload}")
        self.lbl_name.config(text="Ready to Scan", bg="blue", fg="white")
        self.lbl_status.config(text="Ready", bg="green", fg="white")
        return False

    # -----------------------------------------------------------------------
    # Scanner mode: queue management
    # -----------------------------------------------------------------------
    def screenCleanup(self):
        answer = messagebox.askyesno("Confirm", "Erase all Data?")
        if not answer:
            return
        if self.mode == "scanner":
            self.pileCommands("cleanup")
            if not self.lora_sender(sending=True, payload='cmd:cleanup', cmd=True, serverResponseTimeout=10):
                self.unpileCommands()
                return
        # Clear sheet for both modes
        self.lstCode = []
        self.car_number = 0
        self.lastReleaseRow = 0
        self.breakLineList = []
        self.validation_log = []
        self.sheet.delete_rows([x for x in range(0, self.sheet.get_total_rows())], redraw=True)

    def breakQueue(self):
        self.pileCommands("break")
        if self._send_critical_command('cmd:break'):
            self.sheet.insert_row(['', 'RELEASE POINT', ''], redraw=True)
            self.sheet.highlight_rows(rows=[self.sheet.get_total_rows() - 1],
                                      bg='blue', fg='white', highlight_index=True, redraw=True)
            self.breakLineList.append(self.sheet.get_total_rows() - 1)
            self.sheet.see(self.sheet.get_total_rows() - 1, 0)
            self._flash_status("BREAK SET", "blue")
            logging.info("[BREAK] Break confirmed by server")
        else:
            self.unpileCommands()
            self._flash_status("BREAK FAILED - Try Again", "red")
            logging.error("[BREAK] Break failed after retry")

    def releaseQueue(self):
        try:
            self.pileCommands("release")
            if len(self.breakLineList) > 0 and self._send_critical_command('cmd:release'):
                breakLineIndex = self.breakLineList[0]
                released_rows = list(range(self.lastReleaseRow, breakLineIndex + 1))
                self.sheet.highlight_rows(rows=released_rows, bg='#d0d0d0', fg='#888888',
                                          highlight_index=True, redraw=False)
                self.sheet.highlight_rows(rows=[breakLineIndex], bg='#a0a0a0', fg='#666666',
                                          highlight_index=True, redraw=True)
                logging.info(f"[RELEASE] Grayed out rows {self.lastReleaseRow}-{breakLineIndex}")
                self.lastReleaseRow = breakLineIndex + 1
                self.breakLineList.pop(0)
                if self.sheet.get_total_rows() > breakLineIndex + 1:
                    self.sheet.see(breakLineIndex + 1, 0)
                self._flash_status("RELEASED", "green")
                logging.info("[RELEASE] Release confirmed by server")
            else:
                self.unpileCommands()
                self._flash_status("RELEASE FAILED - Try Again", "red")
                logging.error("[RELEASE] Release failed after retry")
        except Exception as e:
            logging.error(f"[RELEASE] Release failed with exception: {e}")

    def undoLast(self):
        self.pileCommands("undo")
        self.lora_sender(sending=True, payload='cmd:undo')
        self.sheet.delete_row(self.sheet.get_total_rows() - 1, redraw=True)

    # -----------------------------------------------------------------------
    # Validation mode: local lookup + problem documentation
    # -----------------------------------------------------------------------
    def _process_validation_scan(self, code: str):
        """Look up a QR code in the local validation DB and display results."""
        self.lbl_name.config(text=f"{code}", bg="#d97706", fg="white")
        self.lbl_status.config(text="Looking up...", bg="yellow", fg="black")
        self.update_idletasks()

        results = _lookup_validation_db(code)
        if not results:
            logging.warning(f"[VAL] Code {code} not found in validation DB")
            self.lbl_status.config(text="NOT FOUND", bg="orange", fg="black")
            self.after(3000, lambda: self.lbl_status.config(text="Ready - Local Lookup", bg="green", fg="white"))
            return

        self.car_number += 1
        for student in results:
            self.sheet.insert_row([self.car_number, student["name"], student["classCode"]], redraw=True)
            logging.info(f"[VAL] {code} -> {student['name']} | {student['classCode']}")

        last_row = self.sheet.get_total_rows() - 1
        if last_row >= 0:
            self.sheet.see(last_row, 0)

        last = results[-1]
        self.lbl_name.config(text=f"{last['name']} - {last['classCode']}", bg="#d97706", fg="white")
        self.lbl_status.config(text=f"Confirmed ({len(results)} students)", bg="green", fg="white")
        self.lstCode.append(code)

    def _mark_problem(self):
        """Mark the last scanned code as having a problem."""
        self.sheet.insert_row(['', 'PROBLEM', ''], redraw=True)
        self.sheet.highlight_rows(rows=[self.sheet.get_total_rows() - 1],
                                  bg='#dc2626', fg='white', highlight_index=True, redraw=True)
        self.sheet.see(self.sheet.get_total_rows() - 1, 0)

        last_code = self.lstCode[-1] if self.lstCode else "unknown"
        self.validation_log.append({
            "code": last_code,
            "category": "PROBLEM",
            "note": "",
            "timestamp": datetime.datetime.now().isoformat(),
        })
        logging.info(f"[VAL] Problem marked for code: {last_code}")
        self._flash_status("PROBLEM MARKED", "#dc2626")

    def _open_note_overlay(self):
        """Open the note overlay for adding detailed problem documentation."""
        last_code = self.lstCode[-1] if self.lstCode else "unknown"
        NoteOverlay(self, last_code, self._save_note)

    def _save_note(self, code: str, category: str, note_text: str):
        """Save a note from the NoteOverlay."""
        display_text = f"NOTE: {category}" + (f" - {note_text}" if note_text else "")
        self.sheet.insert_row(['', display_text, ''], redraw=True)
        self.sheet.highlight_rows(rows=[self.sheet.get_total_rows() - 1],
                                  bg='#fbbf24', fg='black', highlight_index=True, redraw=True)
        self.sheet.see(self.sheet.get_total_rows() - 1, 0)

        self.validation_log.append({
            "code": code,
            "category": category,
            "note": note_text,
            "timestamp": datetime.datetime.now().isoformat(),
        })
        logging.info(f"[VAL] Note saved: {category} - {note_text} (code: {code})")
        self._flash_status("NOTE SAVED", "#d97706", fg="black")

    def _export_validation_log(self):
        """Export validation log to a timestamped CSV file."""
        if not self.validation_log:
            return
        try:
            import pandas as pd
            df = pd.DataFrame(self.validation_log)
            filename = f"data/validation_log_{datetime.datetime.now().strftime('%Y-%m-%d_%H%M')}.csv"
            df.to_csv(filename, index=False)
            logging.info(f"[VAL] Validation log exported: {filename} ({len(self.validation_log)} entries)")
        except Exception as e:
            logging.error(f"[VAL] Failed to export validation log: {e}")

    # -----------------------------------------------------------------------
    # Search (works in both modes)
    # -----------------------------------------------------------------------
    def openSearch(self):
        if self.matcher is None:
            self.lbl_status.config(text="Loading student list...", bg="yellow", fg="black")
            self.update()
            try:
                self.matcher = StudentMatcher("data/students.csv")
                logging.info(f"StudentMatcher loaded ({len(self.matcher.phonetic_index)} students)")
                self.lbl_status.config(text="Ready", bg="green", fg="white")
            except Exception as e:
                logging.error(f"Failed to load StudentMatcher: {e}")
                self.lbl_status.config(text="Search unavailable", bg="red", fg="white")
                return

        if self.mode == "validation":
            callback = self._on_student_selected_validation
        else:
            callback = self._on_student_selected

        SearchOverlay(self, self.matcher, callback)

    def _on_student_selected(self, device_id: str, student_name: str):
        """Callback from search in scanner mode: submit via LoRa."""
        logging.info(f"[SEARCH] Student selected: {student_name} -> {device_id}")
        if device_id in self.lstCode:
            self.lbl_name.config(text=f"{student_name}", bg="blue", fg="white")
            self.lbl_status.config(text="Duplicate - already scanned")
            logging.info(f"[SEARCH] Duplicate skipped: {device_id}")
        else:
            logging.info(f"[SEARCH] Submitting: {device_id}")
            self._submit_with_retry(device_id)

    def _on_student_selected_validation(self, device_id: str, student_name: str):
        """Callback from search in validation mode: local lookup."""
        logging.info(f"[SEARCH-VAL] Student selected: {student_name} -> {device_id}")
        if device_id in self.lstCode:
            self.lbl_name.config(text=f"{student_name}", bg="#d97706", fg="white")
            self.lbl_status.config(text="Duplicate - already scanned")
            logging.info(f"[SEARCH-VAL] Duplicate skipped: {device_id}")
        else:
            self._process_validation_scan(device_id)

    # -----------------------------------------------------------------------
    # Serial processing (routes based on mode)
    # -----------------------------------------------------------------------
    def process_serial(self):
        try:
            if self.queue.qsize():
                qrCode = self.queue.get_nowait()
                logging.info(f'Read from Queue: {qrCode}')

                # Handle invalid QR codes from serial thread
                if qrCode.startswith("INVALID:"):
                    raw_code = qrCode[8:]  # Strip "INVALID:" prefix
                    self.car_number += 1
                    self.sheet.insert_row([self.car_number, raw_code, 'N/A'], redraw=True)
                    self.sheet.highlight_rows(rows=[self.sheet.get_total_rows() - 1],
                                              bg='#fbbf24', fg='black', highlight_index=True, redraw=True)
                    self.sheet.see(self.sheet.get_total_rows() - 1, 0)
                    self.lbl_name.config(text=f"{raw_code}")
                    self.lbl_status.config(text="INVALID QR CODE", bg="orange", fg="black")
                    self.after(3000, lambda: self.lbl_status.config(text="Ready", bg="green", fg="white"))
                    logging.warning(f"[QUEUE] Invalid QR displayed: {raw_code}")
                elif qrCode in self.lstCode:
                    self.lbl_name.config(text=f"{qrCode}")
                    self.lbl_status.config(text="Duplicate QRCode")
                    logging.info(f"[QUEUE] Duplicate skipped: {qrCode}")
                else:
                    logging.info(f"[QUEUE] Processing ({self.mode}): {qrCode}")
                    if self.mode == "validation":
                        self._process_validation_scan(qrCode)
                    else:
                        self._submit_with_retry(qrCode)
        except queue.Empty:
            pass
        except Exception as e:
            logging.error(f"[QUEUE] Error processing item: {e}", exc_info=True)
        finally:
            self.after(100, self.process_serial)

    # -----------------------------------------------------------------------
    # Quit + command tracking
    # -----------------------------------------------------------------------
    def quitScanner(self):
        # Export validation log if there are entries
        if self.validation_log:
            self._export_validation_log()
        try:
            logging.info("Scanner shutdown requested - powering off")
            self.thread.kill()
            self.destroy()
        except Exception as e:
            logging.info(f"Shutdown cleanup error: {e}")
        finally:
            os.system('sudo shutdown -h now')

    def pileCommands(self, command: str):
        logging.info(f"PileCommands current: {command}, previous: {self.previousCommand}")
        self.previousCommand = self.lastCommand
        self.lastCommand = command

    def unpileCommands(self):
        logging.info(f"UN-PileCommands last: {self.lastCommand}, previous: {self.previousCommand}")
        self.lastCommand = self.previousCommand


# ---------------------------------------------------------------------------
# Search Overlay (reused in both modes)
# ---------------------------------------------------------------------------
class SearchOverlay(tk.Toplevel):
    """Fullscreen search overlay with virtual keyboard for student name lookup."""

    KEYBOARD_ROWS = [
        list("QWERTYUIOP"),
        list("ASDFGHJKL"),
        list("ZXCVBNM"),
    ]

    def __init__(self, parent, matcher: StudentMatcher, on_select_callback):
        super().__init__(parent)
        self.matcher = matcher
        self.on_select = on_select_callback
        self.search_field = "last"
        self.query_var = tk.StringVar()

        self.attributes('-fullscreen', True)
        screen_w = parent.winfo_screenwidth()
        screen_h = parent.winfo_screenheight()
        self.geometry(f"{screen_w}x{screen_h}+0+0")
        self.configure(bg='#1a1d27')
        self.grab_set()
        self.focus_set()

        self._build_ui()

    def _build_ui(self):
        screen_w = self.winfo_screenwidth()

        header = tk.Frame(self, bg='#3b82f6', height=44)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Search Student", font=("Arial", 16, "bold"),
                 fg="white", bg='#3b82f6').pack(side=tk.LEFT, padx=12)
        tk.Button(header, text="X", font=("Arial", 14, "bold"), fg="white", bg="#ef4444",
                  activebackground="#dc2626", width=4, bd=0,
                  command=self.destroy).pack(side=tk.RIGHT, padx=6, pady=4)

        mode_frame = tk.Frame(self, bg='#1a1d27', height=40)
        mode_frame.pack(fill=tk.X, padx=8, pady=(6, 2))
        self.btn_last = tk.Button(mode_frame, text="Last Name", font=("Arial", 13, "bold"),
                                  fg="white", bg="#3b82f6", activebackground="#2563eb",
                                  bd=0, padx=16, pady=6, command=lambda: self._set_field("last"))
        self.btn_last.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.btn_first = tk.Button(mode_frame, text="First Name", font=("Arial", 13),
                                   fg="#8b8fa3", bg="#242836", activebackground="#2d3348",
                                   bd=0, padx=16, pady=6, command=lambda: self._set_field("first"))
        self.btn_first.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        entry_frame = tk.Frame(self, bg='#1a1d27')
        entry_frame.pack(fill=tk.X, padx=8, pady=4)
        self.lbl_query = tk.Label(entry_frame, textvariable=self.query_var,
                                  font=("Arial", 20), fg="white", bg="#242836",
                                  anchor="w", padx=12, height=2)
        self.lbl_query.pack(fill=tk.X)

        results_frame = tk.Frame(self, bg='#1a1d27')
        results_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=2)
        self.results_canvas = tk.Canvas(results_frame, bg='#1a1d27', highlightthickness=0)
        self.results_inner = tk.Frame(self.results_canvas, bg='#1a1d27')
        self.results_canvas.pack(fill=tk.BOTH, expand=True)
        self.results_window = self.results_canvas.create_window(
            (0, 0), window=self.results_inner, anchor="nw", width=screen_w - 16
        )
        self.results_inner.bind(
            "<Configure>",
            lambda e: self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))
        )
        self.no_results_lbl = tk.Label(self.results_inner, text="Type a name to search",
                                       font=("Arial", 14), fg="#8b8fa3", bg='#1a1d27', pady=20)
        self.no_results_lbl.pack()

        kb_frame = tk.Frame(self, bg='#0f1117')
        kb_frame.pack(fill=tk.X, side=tk.BOTTOM)

        bottom_row = tk.Frame(kb_frame, bg='#0f1117')
        bottom_row.pack(fill=tk.X, padx=2, pady=(2, 4))
        tk.Button(bottom_row, text="SPACE", font=("Arial", 11), fg="white", bg="#374151",
                  activebackground="#4b5563", height=2, bd=0,
                  command=lambda: self._key_press(" ")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        tk.Button(bottom_row, text="\u2190 DEL", font=("Arial", 11, "bold"), fg="white", bg="#92400e",
                  activebackground="#a16207", height=2, bd=0,
                  command=self._backspace).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        tk.Button(bottom_row, text="CLEAR", font=("Arial", 11, "bold"), fg="white", bg="#991b1b",
                  activebackground="#b91c1c", height=2, bd=0,
                  command=self._clear).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        for row_keys in self.KEYBOARD_ROWS:
            row_frame = tk.Frame(kb_frame, bg='#0f1117')
            row_frame.pack(fill=tk.X, padx=2, pady=1)
            for key in row_keys:
                tk.Button(row_frame, text=key, font=("Arial", 14), fg="white", bg="#374151",
                          activebackground="#4b5563", height=2, bd=0,
                          command=lambda k=key: self._key_press(k.lower())).pack(
                    side=tk.LEFT, expand=True, fill=tk.X, padx=1)

    def _set_field(self, field: str):
        self.search_field = field
        if field == "last":
            self.btn_last.config(fg="white", bg="#3b82f6", font=("Arial", 13, "bold"))
            self.btn_first.config(fg="#8b8fa3", bg="#242836", font=("Arial", 13))
        else:
            self.btn_first.config(fg="white", bg="#3b82f6", font=("Arial", 13, "bold"))
            self.btn_last.config(fg="#8b8fa3", bg="#242836", font=("Arial", 13))
        self._do_search()

    def _key_press(self, char: str):
        self.query_var.set(self.query_var.get() + char)
        self._do_search()

    def _backspace(self):
        current = self.query_var.get()
        if current:
            self.query_var.set(current[:-1])
            self._do_search()

    def _clear(self):
        self.query_var.set("")
        self._show_no_results("Type a name to search")

    def _do_search(self):
        query = self.query_var.get().strip()
        if len(query) < 2:
            self._show_no_results("Type at least 2 letters")
            return
        results = self.matcher.search_by_field(query, field=self.search_field, top_n=8)
        if not results:
            self._show_no_results("No matches found")
            return

        for widget in self.results_inner.winfo_children():
            widget.destroy()

        for r in results:
            row = tk.Frame(self.results_inner, bg="#242836", pady=2)
            row.pack(fill=tk.X, pady=2)
            device_id = r["device_id"]
            name = r["name"]
            grade = r["grade"]
            name_lbl = tk.Label(row, text=f"  {name}", font=("Arial", 16),
                                fg="white", bg="#242836", anchor="w")
            name_lbl.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4, pady=8)
            grade_lbl = tk.Label(row, text=grade, font=("Arial", 13),
                                 fg="#8b8fa3", bg="#242836", width=4)
            grade_lbl.pack(side=tk.RIGHT, padx=4)
            for widget in [row, name_lbl, grade_lbl]:
                widget.bind("<Button-1>", lambda e, d=device_id, n=name: self._select(d, n))

    def _show_no_results(self, message: str):
        for widget in self.results_inner.winfo_children():
            widget.destroy()
        tk.Label(self.results_inner, text=message, font=("Arial", 14),
                 fg="#8b8fa3", bg='#1a1d27', pady=20).pack()

    def _select(self, device_id: str, name: str):
        answer = messagebox.askyesno("Confirm", f"Submit {name}?", parent=self)
        if answer:
            self.destroy()
            self.on_select(device_id, name)


# ---------------------------------------------------------------------------
# Note Overlay (validation mode problem documentation)
# ---------------------------------------------------------------------------
class NoteOverlay(tk.Toplevel):
    """Fullscreen overlay for adding problem notes with categories and virtual keyboard."""

    CATEGORIES = ["Wrong Teacher", "Wrong Grade", "Missing Record", "Name Mismatch", "Other"]

    KEYBOARD_ROWS = [
        list("QWERTYUIOP"),
        list("ASDFGHJKL"),
        list("ZXCVBNM"),
    ]

    def __init__(self, parent, code: str, on_save_callback):
        super().__init__(parent)
        self.code = code
        self.on_save = on_save_callback
        self.selected_category = ""
        self.note_var = tk.StringVar()

        self.attributes('-fullscreen', True)
        screen_w = parent.winfo_screenwidth()
        screen_h = parent.winfo_screenheight()
        self.geometry(f"{screen_w}x{screen_h}+0+0")
        self.configure(bg='#1a1d27')
        self.grab_set()
        self.focus_set()

        self._build_ui()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg='#d97706', height=44)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=f"Add Note — {self.code}", font=("Arial", 14, "bold"),
                 fg="white", bg='#d97706').pack(side=tk.LEFT, padx=12)
        tk.Button(header, text="X", font=("Arial", 14, "bold"), fg="white", bg="#ef4444",
                  activebackground="#dc2626", width=4, bd=0,
                  command=self.destroy).pack(side=tk.RIGHT, padx=6, pady=4)

        # Category buttons
        cat_frame = tk.Frame(self, bg='#1a1d27')
        cat_frame.pack(fill=tk.X, padx=4, pady=(8, 4))
        self.cat_buttons = {}
        for cat in self.CATEGORIES:
            btn = tk.Button(cat_frame, text=cat, font=("Arial", 10),
                            fg="white", bg="#374151", activebackground="#4b5563",
                            bd=0, padx=6, pady=8,
                            command=lambda c=cat: self._select_category(c))
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
            self.cat_buttons[cat] = btn

        # Note display
        note_frame = tk.Frame(self, bg='#1a1d27')
        note_frame.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(note_frame, text="Details (optional):", font=("Arial", 12),
                 fg="#8b8fa3", bg='#1a1d27', anchor="w").pack(fill=tk.X)
        self.lbl_note = tk.Label(note_frame, textvariable=self.note_var,
                                 font=("Arial", 16), fg="white", bg="#242836",
                                 anchor="w", padx=12, height=2)
        self.lbl_note.pack(fill=tk.X, pady=4)

        # Save button
        tk.Button(self, text="SAVE NOTE", font=("Arial", 14, "bold"),
                  fg="white", bg="#16a34a", activebackground="#15803d",
                  height=2, bd=0, command=self._save).pack(fill=tk.X, padx=8, pady=4)

        # Virtual keyboard
        kb_frame = tk.Frame(self, bg='#0f1117')
        kb_frame.pack(fill=tk.X, side=tk.BOTTOM)

        bottom_row = tk.Frame(kb_frame, bg='#0f1117')
        bottom_row.pack(fill=tk.X, padx=2, pady=(2, 4))
        tk.Button(bottom_row, text="SPACE", font=("Arial", 11), fg="white", bg="#374151",
                  activebackground="#4b5563", height=2, bd=0,
                  command=lambda: self._key_press(" ")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        tk.Button(bottom_row, text="\u2190 DEL", font=("Arial", 11, "bold"), fg="white", bg="#92400e",
                  activebackground="#a16207", height=2, bd=0,
                  command=self._backspace).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        tk.Button(bottom_row, text="CLEAR", font=("Arial", 11, "bold"), fg="white", bg="#991b1b",
                  activebackground="#b91c1c", height=2, bd=0,
                  command=self._clear_note).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        for row_keys in self.KEYBOARD_ROWS:
            row_frame = tk.Frame(kb_frame, bg='#0f1117')
            row_frame.pack(fill=tk.X, padx=2, pady=1)
            for key in row_keys:
                tk.Button(row_frame, text=key, font=("Arial", 14), fg="white", bg="#374151",
                          activebackground="#4b5563", height=2, bd=0,
                          command=lambda k=key: self._key_press(k.lower())).pack(
                    side=tk.LEFT, expand=True, fill=tk.X, padx=1)

    def _select_category(self, category: str):
        self.selected_category = category
        for cat, btn in self.cat_buttons.items():
            if cat == category:
                btn.config(bg="#d97706", fg="white", font=("Arial", 10, "bold"))
            else:
                btn.config(bg="#374151", fg="white", font=("Arial", 10))

    def _key_press(self, char: str):
        self.note_var.set(self.note_var.get() + char)

    def _backspace(self):
        current = self.note_var.get()
        if current:
            self.note_var.set(current[:-1])

    def _clear_note(self):
        self.note_var.set("")

    def _save(self):
        if not self.selected_category:
            messagebox.showwarning("Select Category", "Please select a category first.", parent=self)
            return
        note_text = self.note_var.get().strip()
        self.destroy()
        self.on_save(self.code, self.selected_category, note_text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
app = App()
app.mainloop()
