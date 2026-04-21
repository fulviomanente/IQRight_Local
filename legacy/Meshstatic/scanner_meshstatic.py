'''
This Python script is designed to create a graphical user interface (GUI) for a scanner system that uses Meshtastic mesh networking for communication. The GUI is built using the Tkinter library and provides a user-friendly interface for managing the scanning process and displaying scanned data.

Key Features:
- Meshtastic mesh networking for extended range and reliability
- Support for ESP32 repeaters in the mesh network
- Asynchronous message handling with pub/sub pattern
- Acknowledgment-based reliable delivery
- QR code scanning via serial interface
- Real-time GUI updates with scan results

Architecture:
- Connects to local meshtasticd daemon via TCP
- Scanner reads QR codes and sends to server via mesh
- Server responds with user information
- GUI displays results and manages queue
'''

import board
import busio
import digitalio
import tkinter as tk
from tkinter import messagebox
from tksheet import Sheet
from threading import Thread
import threading
import serial
import time
import RPi.GPIO as GPIO
import queue
import logging
import logging.handlers
import meshtastic
import meshtastic.tcp_interface
from pubsub import pub

# Import configuration
from utils.config import (
    MESHTASTIC_CLIENT_HOST,
    MESHTASTIC_CLIENT_PORT,
    MESHTASTIC_CLIENT_NODE_ID,
    MESHTASTIC_SERVER_NODE_ID,
    MESHTASTIC_SERVER_NODE_NUM
)

#LOGGING Setup
log_filename = "IQRight_Scanner.debug"
max_log_size = 20 * 1024 * 1024 #20Mb
backup_count = 10
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
debug = True
handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=max_log_size, backupCount=backup_count)

handler.setFormatter(log_formatter)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)

class SerialThread(Thread):
    def __init__(self, queue):
        Thread.__init__(self)
        self._kill = threading.Event()
        self._interval = 10
        self.queue = queue
        # SCANNER SERIAL DEFINITIONS
        self.delay = 0.1
        self.inPin = 22
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.inPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.ser = serial.Serial("/dev/serial0", 115200, timeout=2)
        self.control = False
        ##########################

    def run(self):
        try:
            while True:
                pressed = GPIO.input(self.inPin)
                if pressed == 0:
                    logging.info('Write Serial')
                    self.ser.write(bytes.fromhex("7E000801000201ABCD"))
                    time.sleep(0.1)
                    logging.info('Read Serial')
                    blankReturn = self.ser.read()
                    logging.info(blankReturn)
                    time.sleep(1.3)
                    remaining = self.ser.inWaiting()
                    logging.info(remaining)
                    codeReaded = self.ser.read(remaining)
                    logging.info('codeReaded')
                    #qrCode = str(codeReaded, encoding="UTF-8")
                    #logging.info(qrCode)
                    #logging.info(len(qrCode))
                    #logging.info(qrCode[0:6])
                    #logging.info(qrCode[6:])
                    #self.queue.put(qrCode[6:].strip())
                    self.queue.put("P18710587")
                    logging.info('PUT in the Queue')
                    pressed = 1
                is_killed = self._kill.wait(1)
                if is_killed:
                    break
        except Exception as e:
            logging.info(e)

    def kill(self):
        self._kill.set()

class App(tk.Tk):
    def __init__(self):
        # MESHTASTIC DEFINITIONS
        try:
            self.mesh = meshtastic.tcp_interface.TCPInterface(hostname=MESHTASTIC_CLIENT_HOST)
            logging.info(f'Connected to Meshtastic daemon at {MESHTASTIC_CLIENT_HOST}:{MESHTASTIC_CLIENT_PORT}')
            logging.info(f'Client Node ID: {MESHTASTIC_CLIENT_NODE_ID}')
            logging.info(f'Server Node ID: {MESHTASTIC_SERVER_NODE_ID}')

        except Exception as e:
            logging.error(f'Failed to connect to Meshtastic daemon: {e}')
            messagebox.showerror("Connection Error", f"Failed to connect to Meshtastic daemon: {e}")
            exit(1)

        ##########################
        self.lstCode = []
        self.breakLineList: list = []
        tk.Tk.__init__(self)
        self.lastCommand = None
        self.previousCommand = None
        self.response_received = threading.Event()
        self.last_response = None

        # Multi-packet tracking
        self.expected_message_count = 0
        self.received_message_count = 0
        self.current_student_name = ""
        self.current_grade = ""
        self.response_list = []

        # Create the main window
        screenWidth = self.winfo_screenwidth()
        self.attributes('-fullscreen', True)
        self.title("Main Entrance")
        self.configure(bg='white')

        upperFrame = tk.Frame(height=100, bg="blue")
        # Add labels to the window
        lbl_title = tk.Label(master=upperFrame, text=f"CGES - Main Entrance", font=("Arial", 18), fg="white",
                             bg="blue").pack()
        self.lbl_name = tk.Label(master=upperFrame, text=f"Ready to Scan", font=("Arial", 18), fg="white", bg="blue")
        self.lbl_status = tk.Label(master=upperFrame, text=f"Idle", font=("Arial", 14), fg="white", bg="blue")
        self.lbl_name.pack()
        self.lbl_status.pack()

        bottomFrame = tk.Frame(height=550, bg="white")
        self.sheet = Sheet(bottomFrame, headers=['Name', 'Grade', 'Teacher'], empty_vertical=0,
                      height=550, width=screenWidth, font=("Arial", 14, "normal"), header_font=("Arial", 14, "normal"))
        self.sheet.column_width(0, 180)
        self.sheet.column_width(1, 80)
        self.sheet.column_width(2, 160)
        self.sheet.pack(fill=tk.X)

        barFrame = tk.Frame(height=60, bg="white", width=480)
        btn_addBreak = tk.Button(master=barFrame, text="Break", font=("Arial", 16), height=12, fg="blue",
                                 command=self.breakQueue).pack(fill='both', expand=True, side=tk.LEFT)
        btn_removeLast = tk.Button(master=barFrame, text="Release", height=12, font=("Arial", 16), fg="blue",
                                   command=self.releaseQueue).pack(fill='both', expand=True, side=tk.LEFT)
        btn_undo = tk.Button(master=barFrame, text="Undo", height=12, font=("Arial", 16), fg="blue",
                             command=self.undoLast).pack(fill='both', expand=True, side=tk.LEFT)
        btn_refresh = tk.Button(master=barFrame, text="Reset", height=12, font=("Arial", 16), fg="blue",
                                command=self.screenCleanup).pack(fill='both', expand=True, side=tk.LEFT)
        btn_quit = tk.Button(master=barFrame, text="Quit", height=12, font=("Arial", 16), fg="blue",
                             command=self.quitScanner).pack(fill='both', expand=True, side=tk.LEFT)

        idTable: int = 1
        upperFrame.pack(fill=tk.X)
        bottomFrame.pack(fill=tk.X)
        barFrame.pack(fill=tk.X)

        try:
            # Subscribe to Meshtastic events
            pub.subscribe(self.onReceive, "meshtastic.receive.text")
            pub.subscribe(self.onConnection, "meshtastic.connection.established")
            logging.info("Subscribed to Meshtastic events")
        except Exception as e:
            logging.error(f'Failed to subscribe to Meshtastic events: {e}')
            messagebox.showerror("Connection Error", f"Failed to subscribe to Meshtastic events: {e}")
            exit(1)

        self.queue = queue.Queue()
        self.thread = SerialThread(self.queue)
        self.thread.start()
        self.process_serial()

    def onReceive(self, packet, interface):
        """Callback for received Meshtastic messages"""
        try:
            message_text = None

            # Check if this is a DECODED text message (preferred)
            if 'decoded' in packet:
                decoded = packet['decoded']

                # Check for 'text' field first (most common)
                if 'text' in decoded:
                    message_text = decoded['text']
                    logging.info(f"Decoded text: {message_text}")

                # Fallback to 'payload' field
                elif 'payload' in decoded:
                    payload = decoded['payload']
                    if isinstance(payload, str):
                        message_text = payload
                    elif isinstance(payload, bytes):
                        message_text = payload.decode('utf-8', errors='ignore')
                    else:
                        message_text = str(payload)
                    logging.info(f"Decoded payload: {message_text}")

            # If not decoded, check if encrypted (KEY MISMATCH!)
            elif 'encrypted' in packet:
                logging.error("Received ENCRYPTED packet - channel/key mismatch!")
                logging.error("Check: meshtastic --host localhost --info")
                logging.error("Ensure scanner and server use same channel and PSK")
                self.lbl_status.config(text="Encryption Error", bg="red")
                return

            if message_text:
                source_node = packet.get('from', 0)
                logging.info(f"Received from node {source_node}: {message_text}")

                # Only process messages from the server
                if source_node == MESHTASTIC_SERVER_NODE_NUM:
                    # Schedule on main thread for thread-safety
                    self.after(0, self.processResponse, message_text)
                    logging.debug(f"Scheduled processing of message from {source_node}")
                else:
                    logging.warning(f"Node {source_node} not recognized (expected {MESHTASTIC_SERVER_NODE_NUM})")
            else:
                logging.warning(f"No decodable message in packet: {packet.keys()}")

        except Exception as e:
            logging.error(f"Error processing received packet: {e}")
            logging.error(f"Packet: {packet}")

    def onConnection(self, interface, topic=pub.AUTO_TOPIC):
        """Callback when Meshtastic connection is established"""
        logging.info("Meshtastic connection established")
        self.lbl_status.config(text="Meshtastic Connected", bg="green")

    def processResponse(self, response: str):
        """
        Process response from server with multi-packet protocol

        Message format: "name|grade_initial|msg_num/total_msgs"
        Example: "John Smith|5|1/3" means message 1 of 3
        """
        try:
            parts = response.split("|")

            if parts[0] == 'cmd':
                # Command acknowledgment
                if parts[1] == 'ack' and parts[2] == self.lastCommand:
                    self.lbl_status.config(text='CMD Confirmed', bg="green")
                    logging.info('SERVER ACK TRUE')
                    self.last_response = True
                    self.response_received.set()
                else:
                    logging.info('SERVER ACK FALSE')
                    self.last_response = False
                    self.response_received.set()
            else:
                # Student information with packet counter
                name = parts[0]
                grade_initial = parts[1]
                grade_teacher = parts[2]
                packet_info = parts[3]  # Format: "1/3"

                # Parse packet counter
                current_msg, total_msgs = packet_info.split('/')
                current_msg = int(current_msg)
                total_msgs = int(total_msgs)

                logging.info(f"Received packet {current_msg}/{total_msgs}: {name}, Grade: {grade_initial}")

                # If this is the first packet of a multi-packet sequence
                if current_msg == 1:
                    self.expected_message_count = total_msgs
                    self.received_message_count = 1
                    self.current_student_name = name
                    self.current_grade = grade_initial

                    # Update display
                    self.lbl_name.config(text=f"{name}")

                    if total_msgs > 1:
                        # More packets coming - acknowledge receipt started
                        self.lbl_status.config(text=f"Receiving... ({current_msg}/{total_msgs})", bg="yellow")
                        logging.info(f"Expecting {total_msgs} total messages, received {current_msg}")
                        self.response_list.append({"name":name, "grade_initial": grade_initial, "grade_teacher":grade_teacher})
                        # Add all students to a list to be processed at the end
                        self.last_response = False
                    else:
                        # Single packet - complete
                        self.lbl_status.config(text=f"Queue Confirmed", bg="green")
                        self.sheet.insert_row([name, grade_initial, grade_teacher], redraw=True)
                        self.last_response = True

                else:
                    # Subsequent packet
                    self.received_message_count += 1

                    # Update display with latest packet info
                    self.lbl_name.config(text=f"{name}")

                    # Update status
                    self.lbl_status.config(text=f"Receiving... ({current_msg}/{total_msgs})", bg="yellow")
                    logging.info(f"Received {current_msg}/{total_msgs} packets")

                    # Check if this is the last packet
                    if current_msg == total_msgs:
                        # All packets received - complete!
                        # Use the LAST packet's info for the spreadsheet (most recent student)
                        self.lbl_status.config(text=f"Queue Confirmed", bg="green")
                        for student in self.response_list:
                            self.sheet.insert_row([student['name'], student['grade_initial'], student['grade_teacher']], redraw=True)

                        logging.info(f"All {total_msgs} packets received successfully")

                        # Reset counters
                        self.expected_message_count = 0
                        self.received_message_count = 0
                        self.last_response = True
                        self.response_list = []
                self.response_received.set()


        except Exception as e:
            logging.error(f"Error processing response: {e}")
            logging.error(f"Response was: {response}")
            self.lbl_status.config(text=f"Error: {e}", bg="red")
            self.last_response = False
            self.response_received.set()

    def mesh_sender(self, payload: str, cmd: bool = False, timeout: float = 15.0):
        """Send message to server via Meshtastic with acknowledgment"""
        try:
            self.response_received.clear()
            self.last_response = None

            logging.info(f"Sending to server (node {MESHTASTIC_SERVER_NODE_ID}): {payload}")

            # Send with acknowledgment - Meshtastic handles retries automatically
            self.mesh.sendText(
                text=payload,
                destinationId=MESHTASTIC_SERVER_NODE_ID,
                wantAck=True
            )

            self.lbl_status.config(text=f"Message sent, waiting for response...", bg="yellow")

            # Wait for response
            if self.response_received.wait(timeout=timeout):
                if self.last_response:
                    return True
                else:
                    self.lbl_status.config(text=f"Invalid response received", bg="red")
                    return False
            else:
                self.lbl_status.config(text=f"Response timeout", bg="red")
                logging.error(f"Timeout waiting for response from server")
                return False

        except Exception as e:
            logging.error(f"Error sending message: {e}")
            self.lbl_status.config(text=f"Send error: {e}", bg="red")
            return False

    def processUpdate(self, qrCode: str):
        logging.info(f"ProcessUpdate {qrCode}")
        if qrCode in self.lstCode:
            self.lbl_name.config(text=f"{qrCode}")
            self.lbl_status.config(text=f"Duplicate QRCode", bg="orange")
        else:
            self.lbl_name.config(text=f"{qrCode}")
            self.lbl_status.config(text=f"Sending to IQRight Server", bg="blue")

            if len(qrCode) < 3:
                logging.info("Empty Message")
                return
            else:
                logging.info(f"QRCode {qrCode}")
                # Format: {node_id}|{code}|{distance}
                payload = f"{MESHTASTIC_CLIENT_NODE_ID}|{qrCode}|1"

                if self.mesh_sender(payload=payload):
                    self.lstCode.append(qrCode)
                else:
                    self.lbl_status.config(text="Failed to send", bg="red")

    def screenCleanup(self):
        answer = messagebox.askyesno("Confirm", "Erase all Data?")
        if answer == True:
            self.pileCommands("cleanup")
            if self.mesh_sender(payload=f'{MESHTASTIC_CLIENT_NODE_ID}|cmd:cleanup|1', cmd=True):
                self.lstCode = []
                self.sheet.delete_rows([x for x in range(0, self.sheet.get_total_rows())], deselect_all=True, redraw=True)
            else:
                self.unpileCommands()

    def breakQueue(self):
        self.pileCommands("break")
        if self.mesh_sender(payload=f'{MESHTASTIC_CLIENT_NODE_ID}|cmd:break|1', cmd=True):
            self.sheet.insert_row(['RELEASE POINT', '', ''], redraw=True)
            self.sheet.highlight_rows(rows=[self.sheet.get_total_rows() - 1], bg='blue', fg='white', highlight_index=True,
                                 redraw=True)
            self.breakLineList.append(self.sheet.get_total_rows() - 1)
        else:
            self.unpileCommands()

    def releaseQueue(self):
        self.pileCommands("release")
        if len(self.breakLineList) > 0 and self.mesh_sender(payload=f'{MESHTASTIC_CLIENT_NODE_ID}|cmd:release|1', cmd=True):
            breakLineIndex = self.breakLineList[0]
            self.sheet.delete_rows([x for x in range(0, breakLineIndex)], deselect_all=True, redraw=True)
            self.breakLineList.pop(0)
            self.breakLineList = [x - breakLineIndex for x in self.breakLineList]
        else:
            self.unpileCommands()

    def undoLast(self):
        self.pileCommands("undo")
        if self.mesh_sender(payload=f'{MESHTASTIC_CLIENT_NODE_ID}|cmd:undo|1'):
            self.sheet.delete_row(self.sheet.get_total_rows() - 1, deselect_all=True, redraw=True)
        else:
            self.unpileCommands()

    def quitScanner(self):
        try:
            self.thread.kill()
            if self.mesh:
                self.mesh.close()
            self.destroy()
            quit()
        except Exception as e:
           logging.info("Shutdown error")
           logging.info(e)

    def process_serial(self):
        value = True
        while self.queue.qsize():
            try:
                new = self.queue.get()
                logging.info('Read from Queue')
                logging.info(new)
                self.lbl_status.config(text=f"{new}")
                if value:
                    self.processUpdate(new)
                value = False
            except queue.Empty:
                logging.info("EMPTY QUEUE")
                pass
        self.after(100, self.process_serial)

    def pileCommands(self, command: str):
        logging.info(f"PileCommands current: {command}, previous: {self.previousCommand}")
        self.previousCommand = self.lastCommand
        self.lastCommand = command

    def unpileCommands(self):
        logging.info(f"UN-PileCommands last: {self.lastCommand}, previous: {self.previousCommand}")
        self.lastCommand = self.previousCommand

#Run the main loop
app = App()
app.mainloop()
