'''
This Python script is designed to create a graphical user interface (GUI) for a scanner system that uses a LoRa radio module for communication. The GUI is built using the Tkinter library and provides a user-friendly interface for managing the scanning process and displaying scanned data.

Here's a breakdown of the code:

**Importing Libraries**: The script starts by importing necessary libraries, including tkinter for the GUI, queue for managing the queue of scanned data, logging for logging events, and RPi.GPIO for interfacing with the scanner's GPIO pins.

**Logging Setup**: A logging configuration is set up to log events and errors to a file named IQRight_Scanner.debug. The logging level is set to DEBUG if the debug variable is True, otherwise, it's set to INFO.

**Serial Thread**: A SerialThread class is defined, which extends the Thread class. This thread is responsible for handling serial communication with the scanner. It continuously monitors the scanner's input pin and reads scanned data when available. The scanned data is then placed in a queue for further processing.

**App Class**: The App class is defined, which inherits from tk.Tk and serves as the main application window. It contains the GUI elements and logic for managing the scanning process.

**GUI Elements**: The GUI consists of several frames and widgets, including labels, buttons, and a spreadsheet (Sheet) for displaying scanned data.

**LoRa Configuration**: The LoRa radio module is configured with a frequency of 915.23 MHz and node addresses for communication.

**Queue Management**: The queue attribute is used to store scanned data received from the serial thread.

**Event Handlers**: The class defines event handlers for various buttons and actions, such as breaking the queue, releasing scanned data, undoing the last action, resetting the screen, and quitting the application.

**Process Update**: The processUpdate method is responsible for processing scanned data. It checks if the scanned data is a duplicate (already exists in the lstCode list) and displays appropriate messages. If it's a new code, it sends the data to the IQRight server using the LoRa module and updates the GUI accordingly.

**Screen Cleanup**: The screenCleanup method clears all scanned data from the GUI and the lstCode list.

**Break Queue**: The breakQueue method sends a "break" command to the IQRight server using the LoRa module and inserts a "RELEASE POINT" row into the spreadsheet to indicate a break in the queue.

**Release Queue**: The releaseQueue method sends a "release" command to the IQRight server and deletes scanned data up to the last "RELEASE POINT" row from the spreadsheet.

**Undo Last**: The undoLast method sends an "undo" command to the IQRight server and deletes the last row from the spreadsheet.

**Quit Scanner**: The quitScanner method attempts to stop the serial thread and close the application window.

**Process Serial**: The process_serial method continuously checks the queue for new scanned data. When new data is available, it processes it and updates the GUI accordingly.

**Main Loop**: The mainloop method is called to start the main event loop of the GUI. This loop listens for user interactions and updates the GUI as needed.
'''
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
from utils.config import LORA_FREQUENCY, LORA_TX_POWER, LORA_ENABLE_CA
from utils.matching_engine import StudentMatcher


if os.getenv("LOCAL", "FALSE") != "TRUE":
    import serial
    import RPi.GPIO as GPIO
    # Import enhanced LoRa packet handler
    from lora import LoRaTransceiver, LoRaPacket, PacketType, NodeType, MultiPartFlags, CollisionAvoidance


debug = False

#LOGGING Setup
log_filename = "logs/IQRight_Scanner.debug"
os.makedirs("logs", exist_ok=True)
max_log_size = 20 * 1024 * 1024 #20Mb
backup_count = 10
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Daily rotation at midnight, fallback to size-based rotation
daily_handler = logging.handlers.TimedRotatingFileHandler(
    log_filename, when='midnight', interval=1, backupCount=backup_count
)
daily_handler.setFormatter(log_formatter)
daily_handler.suffix = "%Y-%m-%d"

# Size-based rotation as safety net (20MB max)
size_handler = logging.handlers.RotatingFileHandler(
    log_filename, maxBytes=max_log_size, backupCount=backup_count
)
size_handler.setFormatter(log_formatter)

logging.getLogger().addHandler(daily_handler)
logging.getLogger().addHandler(size_handler)
logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)


class SerialThread(Thread):
    def __init__(self, queue):
        Thread.__init__(self)
        self._kill = threading.Event()
        self._interval = 10 
        self.queue = queue
        # SCANNER SERIAL DEFINITIONS
        self.delay = 0.1
        self.inPin = 21
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.inPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.ser = serial.Serial("/dev/serial0", 115200, timeout=2)
        self.control = False
        ##########################

    # Pattern for a valid QR code: P followed by 7-8 digits
    VALID_QR_PATTERN = re.compile(r'^P\d{7,9}$')

    def clean_qr_code(self, raw_read: str, log_debug: bool = True) -> str:
        logging.debug(f"Raw input ({len(raw_read)} bytes): {repr(raw_read)}")

        # Step 1: Split on non-printable framing bytes BEFORE stripping.
        # The scanner wraps each QR code in protocol framing (0x00, 0x03, etc.).
        # Splitting here separates multiple reads that landed in the buffer.
        fragments = re.split(r'[^0-9A-Za-z]+', raw_read)
        fragments = [f for f in fragments if len(f) > 0]
        logging.debug(f"Fragments after protocol split: {fragments}")

        # Step 2: Clean each fragment, strip 31-prefix, validate
        for frag in fragments:
            cleaned = re.sub(r'[^0-9Pp]', '', frag).upper()
            stripped = cleaned
            while stripped.startswith('31'):
                stripped = stripped[2:]

            if self.VALID_QR_PATTERN.match(stripped):
                logging.debug(f"Valid QR code from fragment: {stripped}")
                return stripped

        # Step 3: Fallback — full string clean (handles edge cases)
        cleaned = re.sub(r'[^0-9Pp]', '', raw_read).upper()
        stripped = cleaned
        while stripped.startswith('31'):
            stripped = stripped[2:]

        # If too long, it's a double-read — extract first valid code
        if len(stripped) > 12:
            match = re.match(r'(P\d{7,9})', stripped)
            if match:
                logging.warning(f"Double-read detected ({len(stripped)} chars): {stripped} -> extracting: {match.group(1)}")
                return match.group(1)
            logging.warning(f"Double-read but no valid pattern found: {stripped}")

        # Validate final result
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
                #Convert bytes from serial into str
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

class App(tk.Tk):
    def __init__(self):
        # Initialize enhanced LoRa transceiver (handles hardware setup internally)
        # Scanner node ID should be 100-199 range
        self.scanner_node_id = 102  # Change this for each scanner
        self.server_node_id = 1

        # Only initialize transceiver in hardware mode (not LOCAL)
        if os.getenv("LOCAL", "FALSE") != "TRUE":
            self.transceiver = LoRaTransceiver(
                node_id=self.scanner_node_id,
                node_type=NodeType.SCANNER,
                frequency=LORA_FREQUENCY,
                tx_power=LORA_TX_POWER
            )
        else:
            self.transceiver = None
        ##########################
        self.lstCode = []
        self.car_number = 0
        self.breakLineList: list = []
        self.lastCommand = None
        self.previousCommand = None
        self.matcher = None  # Lazy-loaded on first search

        # Initialize Tkinter window FIRST
        tk.Tk.__init__(self)

        # Create the main window
        screenWidth = self.winfo_screenwidth()
        self.attributes('-fullscreen', True)
        # root.bind("<Key>", handle_keypress)
        self.title("Main Entrance")
        self.configure(bg='white')
        upperFrame = tk.Frame(height=100, bg="blue")
        # Add labels to the window
        lbl_title = tk.Label(master=upperFrame, text=f"(A)SVDP - East Side", font=("Arial", 18), fg="white",
                             bg="blue").pack()
        self.lbl_name = tk.Label(master=upperFrame, text=f"Ready to Scan", font=("Arial", 18), fg="white", bg="blue")
        self.lbl_status = tk.Label(master=upperFrame, text=f"Idle", font=("Arial", 14), fg="white", bg="blue")
        self.lbl_name.pack()
        self.lbl_status.pack()

        bottomFrame = tk.Frame(height=550, bg="white")
        self.sheet = Sheet(bottomFrame, headers=['Car', 'Name', 'Class'], empty_vertical=0,
                      height=550, width=screenWidth, font=("Arial", 18, "normal"), header_font=("Arial", 18, "normal"),
                      show_row_index=False)
        self.sheet.column_width(0, 60)
        self.sheet.column_width(1, 310)
        self.sheet.column_width(2, 100)
        self.sheet.pack(fill=tk.X)
        # sheet.grid(row=2, column=0, padx=10, pady=10, columnspan=2)

        barFrame = tk.Frame(height=60, bg="white", width=480)

        # Create buttons with references (for enable/disable)
        # Font size 12 to fit 6 buttons on 480px wide screen
        bar_font = ("Arial", 12)
        self.btn_break = tk.Button(master=barFrame, text="Break", font=bar_font, height=4, fg="blue",
                                   command=self.breakQueue)
        self.btn_break.pack(fill='x', expand=True, side=tk.LEFT)

        self.btn_release = tk.Button(master=barFrame, text="Release", height=4, font=bar_font, fg="blue",
                                     command=self.releaseQueue)
        self.btn_release.pack(fill='x', expand=True, side=tk.LEFT)

        self.btn_undo = tk.Button(master=barFrame, text="Undo", height=4, font=bar_font, fg="blue",
                                  command=self.undoLast)
        self.btn_undo.pack(fill='x', expand=True, side=tk.LEFT)

        self.btn_search = tk.Button(master=barFrame, text="Search", height=4, font=bar_font, fg="blue",
                                    command=self.openSearch)
        self.btn_search.pack(fill='x', expand=True, side=tk.LEFT)

        self.btn_refresh = tk.Button(master=barFrame, text="Reset", height=4, font=bar_font, fg="blue",
                                     command=self.retry_hello_handshake)
        self.btn_refresh.pack(fill='x', expand=True, side=tk.LEFT)

        self.btn_quit = tk.Button(master=barFrame, text="Quit", height=4, font=bar_font, fg="blue",
                                  command=self.quitScanner)
        self.btn_quit.pack(fill='x', expand=True, side=tk.LEFT)

        idTable: int = 1
        upperFrame.pack(fill=tk.X)
        bottomFrame.pack(fill=tk.X)
        barFrame.pack(fill=tk.X)


        # Start serial thread if not LOCAL mode
        if os.getenv("LOCAL", "FALSE") != "TRUE":
            self.queue = queue.Queue()
            self.thread = SerialThread(self.queue)
            self.thread.start()

        # NOW perform HELLO handshake (everything is fully loaded)
        if not self._perform_hello_handshake():
            # HELLO failed - show error and disable buttons
            self._handle_hello_failure()
            return
        else:
            # Change Reset button back to normal cleanup function
            self.btn_refresh.config(command=self.screenCleanup)

        # HELLO successful - start processing
        if os.getenv("LOCAL", "FALSE") != "TRUE":
            self.process_serial()


    def _perform_hello_handshake(self) -> bool:
        """
        Perform HELLO handshake with server to synchronize sequence numbers

        Returns:
            True if handshake successful, False if failed
        """
        # Skip HELLO in LOCAL mode (no hardware)
        if os.getenv("LOCAL", "FALSE") == "TRUE":
            logging.info("LOCAL mode: skipping HELLO handshake")
            return True

        logging.info(f"Initiating HELLO handshake with server (node {self.server_node_id})")
        self.lbl_status.config(text="Connecting to server...", bg="yellow")
        self.update()

        success = self.transceiver.send_hello_handshake(
            dest_node=self.server_node_id,
            timeout=3.0,
            max_retries=3
        )

        if success:
            logging.info("HELLO handshake successful - ready to scan")
            self.lbl_status.config(text="Ready", bg="green")
        else:
            logging.error("HELLO handshake failed - cannot communicate with server")
            self.lbl_status.config(text="Server Handshake Failed!", bg="red")

        return success

    def _handle_hello_failure(self):
        """
        Handle HELLO handshake failure
        Show error message and disable all buttons except Quit and Reset
        """
        self.lbl_name.config(text="CONNECTION ERROR", bg="red", fg="white")
        self.lbl_status.config(text="Server Handshake Failed!", bg="red", fg="white")

        # Disable all buttons except Quit and Reset
        self.btn_break.config(state=tk.DISABLED)
        self.btn_release.config(state=tk.DISABLED)
        self.btn_undo.config(state=tk.DISABLED)
        # btn_refresh and btn_quit remain enabled

        logging.error("Scanner in error state - user must retry handshake or quit")
        self.update()

    def retry_hello_handshake(self):
        """
        Retry HELLO handshake (called by Reset button when in error state)
        """
        logging.info("User requested HELLO handshake retry")

        # Re-enable buttons temporarily
        self.lbl_name.config(text="Retrying connection...", bg="blue", fg="white")
        self.lbl_status.config(text="Connecting to server...", bg="yellow", fg="black")
        self.update()

        # Try handshake again
        if self._perform_hello_handshake():
            # Success! Re-enable all buttons and start processing
            logging.info("HELLO retry successful")
            self.lbl_name.config(text="Ready to Scan", bg="blue", fg="white")
            self.lbl_status.config(text="Ready", bg="green", fg="white")

            # Re-enable all buttons
            self.btn_break.config(state=tk.NORMAL)
            self.btn_release.config(state=tk.NORMAL)
            self.btn_undo.config(state=tk.NORMAL)

            # Change Reset button back to normal cleanup function
            self.btn_refresh.config(command=self.screenCleanup)

            # Start processing if not already running
            if os.getenv("LOCAL", "FALSE") != "TRUE":
                if not hasattr(self, 'processing_started'):
                    self.processing_started = True
                    self.process_serial()
        else:
            # Failed again
            logging.error("HELLO retry failed")
            self._handle_hello_failure()

    def lora_receiver(self, cmd: bool):
        """
        Receive packets from server using enhanced packet protocol

        Args:
            cmd: True if expecting command acknowledgment, False for data
        """
        startTime = time.time()
        confirmationReceived = False
        list_received = []
        expected_count = 0

        while True:
            # Look for a new packet using enhanced protocol
            logging.info('Waiting for packet from Server')

            packet = self.transceiver.receive_packet(timeout=0.5)

            if packet is not None:
                # Received a packet!
                logging.info(f'[RX] Response from Server: {packet}')

                try:
                    strPayload = packet.payload.decode('utf-8')
                    logging.info(f'[RX] Payload: {strPayload}')
                    response = strPayload.split("|")
                    logging.debug("??".join(response))
                    if cmd:
                            # Handle command acknowledgment
                        if response[1] == 'ack' and response[2] == self.lastCommand:
                            self.lbl_name.config(text="Ready to Scan", bg="blue", fg="white")
                            self.lbl_status.config(text='CMD Confirmed ')
                            logging.info('SERVER ACK TRUE')
                            return True
                        else:
                            logging.info('SERVER ACK FALSE')
                            return False
                    else:
                            # Handle data packet (student info)
                            # Format: Name|ClassCode
                        name = response[0]

                        # Handle NOT_FOUND response from server
                        if name == 'NOT_FOUND':
                            not_found_code = response[1] if len(response) > 1 else 'unknown'
                            logging.warning(f"[NOT_FOUND] Code {not_found_code} not found on server")
                            self.lbl_name.config(text=f"{not_found_code}", bg="blue", fg="white")
                            self.lbl_status.config(text="CODE NOT FOUND", bg="orange", fg="black")
                            self.after(3000, lambda: self.lbl_status.config(text="Ready", bg="green", fg="white"))
                            self._last_response_not_found = True
                            return True

                        # Handle RESTRICTED response from server (7th/8th grade filtered)
                        if name == 'RESTRICTED':
                            restricted_code = response[1] if len(response) > 1 else 'unknown'
                            logging.warning(f"[RESTRICTED] Code {restricted_code} is restricted grade - not in car line")
                            self.lbl_name.config(text=f"{restricted_code}", bg="blue", fg="white")
                            self.lbl_status.config(text="NOT IN CAR LINE", bg="orange", fg="black")
                            self.after(3000, lambda: self.lbl_status.config(text="Ready", bg="green", fg="white"))
                            self._last_response_not_found = True
                            return True

                        class_code = response[1]  # ClassCode (e.g., "4W" = 4th Grade, Mrs Webb)

                        list_received.append({"name": name, "classCode": class_code})

                        # Check if multi-packet sequence
                        if packet.is_multi_part():
                            expected_count = packet.multi_part_total
                            logging.info(f"Received packet {packet.multi_part_index}/{packet.multi_part_total}")

                            # Check if last packet in sequence
                            if packet.multi_flags & MultiPartFlags.LAST:
                                confirmationReceived = True
                                break
                            # else: continue waiting for more packets (FIRST or MORE flag)
                        else:
                            # Single packet (not multi-part)
                            confirmationReceived = True
                            break

                except UnicodeDecodeError as e:
                    logging.error(f'Invalid UTF-8 in packet payload: {e}')
                    return False
                except Exception as e:
                    logging.error(f'Error processing packet: {e}')
                    return False

            # Check timeout
            if time.time() >= startTime + 5:
                logging.warning('[RX] TIMEOUT waiting for response from Server')
                return False

        # Display all received students
        if confirmationReceived:
            self.car_number += 1
            for student in list_received:
                self.sheet.insert_row([self.car_number, student["name"], student["classCode"]], redraw=True)

            # Auto-scroll to show the last inserted row
            last_row = self.sheet.get_total_rows() - 1
            if last_row >= 0:
                self.sheet.see(last_row, 0)

            # Update status with last student
            if list_received:
                last = list_received[-1]
                self.lbl_name.config(text=f"{last['name']} - {last['classCode']}", bg="blue", fg="white")
                self.lbl_status.config(text=f"Queue Confirmed ({len(list_received)} students)")
            return True

        return False

    def lora_sender(self, sending: bool, payload: str, cmd: bool = False, serverResponseTimeout: int = 5):
        """
        Send data to server using enhanced packet protocol

        Args:
            sending: Control flag for retry loop
            payload: QR code or command to send
            cmd: True if sending command, False for data
            serverResponseTimeout: Timeout in seconds
        """
        try:
            startTime = time.time()
            cont = 0
            # Show waiting indicator
            self.lbl_name.config(text="Waiting for Server...", bg="yellow", fg="black")
            self.update_idletasks()

            while sending:
                cont += 1

                # Build message: "scanner_id|payload|distance"
                msg = f"{self.scanner_node_id}|{payload}|1"

                # Create packet based on type
                if cmd:
                    # Command packet
                    packet = self.transceiver.create_cmd_packet(
                        dest_node=self.server_node_id,
                        command=payload.split(':')[1]  # Extract command from "cmd:break" format
                    )
                else:
                    # Data packet (QR scan request)
                    packet = self.transceiver.create_data_packet(
                        dest_node=self.server_node_id,
                        payload=msg.encode('utf-8'),
                        use_ack=True
                    )

                logging.info(f"[TX] Sending ({cont}): {msg} | seq={packet.sequence_num}")

                # Send with collision avoidance if enabled
                if LORA_ENABLE_CA and self.transceiver.rfm9x:
                    data = packet.serialize()
                    success = CollisionAvoidance.send_with_ca(
                        self.transceiver.rfm9x,
                        data,
                        max_retries=3,
                        enable_rx_guard=True,
                        enable_random_delay=True
                    )
                else:
                    success = self.transceiver.send_packet(packet, use_ack=True)

                if not success:
                    logging.warning(f"[TX] LoRa send failed ({cont}): {payload} | seq={packet.sequence_num}")
                    self.lbl_status.config(text=f"Error sending to Server - {cont}", bg="red")
                else:
                    logging.info(f"[TX] Send OK ({cont}): {payload} | seq={packet.sequence_num}")
                    self.lbl_status.config(text=f"Info sent to Server - {cont}", bg="green")

                    # Wait for response
                    if self.lora_receiver(cmd):
                        if not cmd and not getattr(self, '_last_response_not_found', False):
                            self.lstCode.append(payload)
                        self._last_response_not_found = False
                        sending = False
                        return True

                # Check timeout
                if time.time() >= startTime + serverResponseTimeout:
                    logging.warning(f"[TX] FAILED after {cont} attempts: {payload} | timeout={serverResponseTimeout}s")
                    self.lbl_name.config(text="No Response", bg="red", fg="white")
                    self.lbl_status.config(text=f"Ack not received - {cont}", bg="red")
                    return False
        except Exception as e:
            logging.error(f"Error sending to Server: {e}")
            self.lbl_name.config(text="Communication Error", bg="red", fg="white")
            return False


    def _send_critical_command(self, payload: str) -> bool:
        """Send a critical command (break/release) with automatic retry on failure."""
        if self.lora_sender(sending=True, payload=payload, cmd=True, serverResponseTimeout=10):
            return True
        # One more attempt for critical commands
        logging.warning(f"[CMD-RETRY] First attempt failed for {payload}, retrying...")
        self.lbl_status.config(text="Retrying command...", bg="yellow", fg="black")
        return self.lora_sender(sending=True, payload=payload, cmd=True, serverResponseTimeout=10)

    def _flash_status(self, text: str, bg: str, fg: str = "white"):
        """Briefly flash the status bar then restore to normal after 3 seconds."""
        self.lbl_status.config(text=text, bg=bg, fg=fg)
        self.after(3000, lambda: self.lbl_status.config(text="Ready", bg="green", fg="white"))

    def screenCleanup(self):
        answer = messagebox.askyesno("Confirm", "Erase all Data?")
        if answer == True:
            self.pileCommands("cleanup")
            if self.lora_sender(sending=True, payload='cmd:cleanup', cmd=True, serverResponseTimeout=10):
                self.lstCode = []
                self.car_number = 0
                self.sheet.delete_rows([x for x in range(0, self.sheet.get_total_rows())], redraw=True)
            else:
                self.unpileCommands()

    def breakQueue(self):
        self.pileCommands("break")
        if self._send_critical_command('cmd:break'):
            self.sheet.insert_row(['', 'RELEASE POINT', ''], redraw=True)
            self.sheet.highlight_rows(rows=[self.sheet.get_total_rows() - 1], bg='blue', fg='white', highlight_index=True,
                                 redraw=True)
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
                # Delete all rows from top through the break line (inclusive)
                rows_to_delete = [x for x in range(0, breakLineIndex + 1)]
                logging.info(f"[RELEASE] Deleting rows 0-{breakLineIndex} ({len(rows_to_delete)} rows)")
                self.sheet.delete_rows(rows_to_delete, redraw=True)
                self.breakLineList.pop(0)
                # Adjust remaining break indices by total rows removed
                deleted_count = breakLineIndex + 1
                self.breakLineList = [x - deleted_count for x in self.breakLineList]
                self._flash_status("RELEASED", "green")
                logging.info("[RELEASE] Release confirmed by server")
            else:
                self.unpileCommands()
                self._flash_status("RELEASE FAILED - Try Again", "red")
                logging.error("[RELEASE] Release failed after retry")

        except Exception as e:
            logging.error("[RELEASE] Release failed with exception")
            logging.error(e)

    def undoLast(self):
        self.pileCommands("undo")
        self.lora_sender(sending=True, payload='cmd:undo')
        self.sheet.delete_row(self.sheet.get_total_rows() - 1, redraw=True)
        

    def quitScanner(self):
        try:
            logging.info("Scanner shutdown requested - powering off")
            self.thread.kill()
            self.destroy()
        except Exception as e:
            logging.info(f"Shutdown cleanup error: {e}")
        finally:
            os.system('sudo shutdown -h now')

    def process_serial(self):
        try:
            if self.queue.qsize():
                qrCode = self.queue.get_nowait()
                logging.info(f'Read from Queue: {qrCode}')
                if qrCode in self.lstCode:
                    self.lbl_name.config(text=f"{qrCode}", bg="blue", fg="white")
                    self.lbl_status.config(text=f"Duplicate QRCode")
                    logging.info(f"[QUEUE] Duplicate skipped: {qrCode}")
                else:
                    logging.info(f"[QUEUE] Processing: {qrCode}")
                    self.lora_sender(sending=True, payload=qrCode)
        except queue.Empty:
            pass
        except Exception as e:
            logging.error(f"[QUEUE] Error processing item: {e}", exc_info=True)
        finally:
            # ALWAYS reschedule — never let the polling loop die
            self.after(100, self.process_serial)

    def openSearch(self):
        """Open the fullscreen search overlay for name-based student lookup."""
        # Lazy-load the matcher on first use
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

        SearchOverlay(self, self.matcher, self._on_student_selected)

    def _on_student_selected(self, device_id: str, student_name: str):
        """Called when a student is selected from search. Submits their DeviceID like a QR scan."""
        logging.info(f"[SEARCH] Student selected: {student_name} -> {device_id}")
        if device_id in self.lstCode:
            self.lbl_name.config(text=f"{student_name}", bg="blue", fg="white")
            self.lbl_status.config(text="Duplicate - already scanned")
            logging.info(f"[SEARCH] Duplicate skipped: {device_id}")
        else:
            logging.info(f"[SEARCH] Submitting: {device_id}")
            self.lora_sender(sending=True, payload=device_id)

    def pileCommands(self, command: str):
        logging.info(f"PileCommands current: {command}, previous: {self.previousCommand}")
        self.previousCommand = self.lastCommand
        self.lastCommand = command

    def unpileCommands(self):
        logging.info(f"UN-PileCommands last: {self.lastCommand}, previous: {self.previousCommand}")
        self.lastCommand = self.previousCommand


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
        self.search_field = "last"  # Default: search by last name
        self.query_var = tk.StringVar()

        # Fullscreen - force full screen dimensions
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

        # --- Header bar ---
        header = tk.Frame(self, bg='#3b82f6', height=44)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Search Student", font=("Arial", 16, "bold"),
                 fg="white", bg='#3b82f6').pack(side=tk.LEFT, padx=12)
        tk.Button(header, text="X", font=("Arial", 14, "bold"), fg="white", bg="#ef4444",
                  activebackground="#dc2626", width=4, bd=0,
                  command=self.destroy).pack(side=tk.RIGHT, padx=6, pady=4)

        # --- Mode toggle ---
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

        # --- Search entry display ---
        entry_frame = tk.Frame(self, bg='#1a1d27')
        entry_frame.pack(fill=tk.X, padx=8, pady=4)
        self.lbl_query = tk.Label(entry_frame, textvariable=self.query_var,
                                  font=("Arial", 20), fg="white", bg="#242836",
                                  anchor="w", padx=12, height=2)
        self.lbl_query.pack(fill=tk.X)

        # --- Results area ---
        results_frame = tk.Frame(self, bg='#1a1d27')
        results_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        self.results_canvas = tk.Canvas(results_frame, bg='#1a1d27', highlightthickness=0)
        self.results_inner = tk.Frame(self.results_canvas, bg='#1a1d27')
        self.results_canvas.pack(fill=tk.BOTH, expand=True)
        self.results_window = self.results_canvas.create_window((0, 0), window=self.results_inner,
                                                                 anchor="nw", width=screen_w - 16)
        self.results_inner.bind("<Configure>",
                                lambda e: self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all")))

        # Initial message
        self.no_results_lbl = tk.Label(self.results_inner, text="Type a name to search",
                                       font=("Arial", 14), fg="#8b8fa3", bg='#1a1d27', pady=20)
        self.no_results_lbl.pack()

        # --- Virtual keyboard (480px wide screen) ---
        kb_frame = tk.Frame(self, bg='#0f1117')
        kb_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Bottom row: Space + Backspace + Clear
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

        # Letter rows: Q-row, A-row, Z-row (top to bottom, like a real keyboard)
        for row_keys in self.KEYBOARD_ROWS:
            row_frame = tk.Frame(kb_frame, bg='#0f1117')
            row_frame.pack(fill=tk.X, padx=2, pady=1)
            for key in row_keys:
                tk.Button(row_frame, text=key, font=("Arial", 14), fg="white", bg="#374151",
                          activebackground="#4b5563", height=2, bd=0,
                          command=lambda k=key: self._key_press(k.lower())).pack(
                    side=tk.LEFT, expand=True, fill=tk.X, padx=1)

    def _set_field(self, field: str):
        """Switch between last name and first name search."""
        self.search_field = field
        if field == "last":
            self.btn_last.config(fg="white", bg="#3b82f6", font=("Arial", 13, "bold"))
            self.btn_first.config(fg="#8b8fa3", bg="#242836", font=("Arial", 13))
        else:
            self.btn_first.config(fg="white", bg="#3b82f6", font=("Arial", 13, "bold"))
            self.btn_last.config(fg="#8b8fa3", bg="#242836", font=("Arial", 13))
        # Re-run search with new field
        self._do_search()

    def _key_press(self, char: str):
        """Handle virtual keyboard key press."""
        self.query_var.set(self.query_var.get() + char)
        self._do_search()

    def _backspace(self):
        """Remove last character."""
        current = self.query_var.get()
        if current:
            self.query_var.set(current[:-1])
            self._do_search()

    def _clear(self):
        """Clear the search query."""
        self.query_var.set("")
        self._show_no_results("Type a name to search")

    def _do_search(self):
        """Run fuzzy search and update results."""
        query = self.query_var.get().strip()
        if len(query) < 2:
            self._show_no_results("Type at least 2 letters")
            return

        results = self.matcher.search_by_field(query, field=self.search_field, top_n=8)

        if not results:
            self._show_no_results("No matches found")
            return

        # Clear results
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

            # Bind click to all widgets in the row
            for widget in [row, name_lbl, grade_lbl]:
                widget.bind("<Button-1>", lambda e, d=device_id, n=name: self._select(d, n))

    def _show_no_results(self, message: str):
        """Show a 'no results' message in the results area."""
        for widget in self.results_inner.winfo_children():
            widget.destroy()
        tk.Label(self.results_inner, text=message, font=("Arial", 14),
                 fg="#8b8fa3", bg='#1a1d27', pady=20).pack()

    def _select(self, device_id: str, name: str):
        """Handle student selection - confirm then submit."""
        answer = messagebox.askyesno("Confirm", f"Submit {name}?", parent=self)
        if answer:
            self.destroy()
            self.on_select(device_id, name)


#Run the main loop
app = App()
app.mainloop()


