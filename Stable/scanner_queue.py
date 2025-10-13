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

import board
import busio
import digitalio
import adafruit_rfm9x
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

debug = True

#LOGGING Setup
log_filename = "IQRight_Scanner.debug"
max_log_size = 20 * 1024 * 1024 #20Mb
backup_count = 10
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=max_log_size, backupCount=backup_count)
handler.setFormatter(log_formatter)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)


#def serial_UART_Monitor():
#    while True:
#        result = serial_UART_Loop()
#        if result == False:
#            print('Scanner Fatal error at', datetime.datetime.now())

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
    def run(self):
      try:
        while True:
            pressed = GPIO.input(self.inPin)
            if pressed == 0:
                logging.info('Write Serial')
                self.ser.write(bytes.fromhex("7E000801000201ABCD"))
                time.sleep(0.1)
                logging.info('Read Serial Blank')
                blankReturn = self.ser.read()
                logging.info(f'blank read: {blankReturn}')
                time.sleep(1.3)
                remaining = self.ser.inWaiting()
                serialRead = self.ser.read(remaining)
                #Convert bytes from serial into str
                strRead = str(serialRead, encoding="UTF-8")
                logging.info(f"full read ({len(strRead)} bytes): {strRead}")
                qrCode = strRead[6:].strip()
                if len(qrCode) > 6:
                    self.queue.put(qrCode)
                    logging.info(f'PUT in the Queue: {qrCode}')
                else:
                    logging.info(f'Invalid String captured from Serial: {qrCode}')
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
        # LORA DEFINITIONS
        RADIO_FREQ_MHZ = 915.23
        CS = digitalio.DigitalInOut(board.CE1)
        RESET = digitalio.DigitalInOut(board.D25)
        # Initialize SPI bus.
        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        # Initialze RFM radio
        self.rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, RADIO_FREQ_MHZ)
        # set node addresses
        self.rfm9x.node = 102
        self.rfm9x.destination = 1
        # initialize counter
        counter = 0
        ##########################
        self.lstCode = []
        self.breakLineList: list = []
        tk.Tk.__init__(self)
        self.lastCommand = None
        self.previousCommand = None
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
        self.sheet = Sheet(bottomFrame, headers=['Name', 'Grade', 'Teacher'], empty_vertical=0,
                      height=550, width=screenWidth, font=("Arial", 14, "normal"), header_font=("Arial", 14, "normal"))
        self.sheet.column_width(0, 180)
        self.sheet.column_width(1, 80)
        self.sheet.column_width(2, 160)
        self.sheet.pack(fill=tk.X)
        # sheet.grid(row=2, column=0, padx=10, pady=10, columnspan=2)

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

        self.queue = queue.Queue()
        self.thread = SerialThread(self.queue)
        self.thread.start()
        self.process_serial()

    def lora_receiver(self, cmd: bool):
        startTime = time.time()
        confirmationReceived = False
        list_received = []
        count = 0
        while True:
            # Look for a new packet: only accept if addressed to my_node
            logging.debug('Waiting for packet from Server')
            time.sleep(0.3)
            packet = self.rfm9x.receive(with_header=True)
            # If no packet was received during the timeout then None is returned.
            if packet is not None:
                # Received a packet!
                # Print out the raw bytes of the packet:
                logging.info(f'response from Server: {packet}')
                strPayload = str(packet[4:], "UTF-8")
                logging.info(f'Payload: {strPayload}')
                response = strPayload.split("|")
                logging.info("??".join(response))
                if cmd:
                    if response[1] == 'ack' and response[2] == self.lastCommand:
                        self.lbl_status.config(text='CMD Confirmed ')
                        logging.info('SERVER ACK TRUE')
                        return True
                    else:
                        logging.info('SERVER ACK FALSE')
                        return False
                else:
                    if count == 0:
                        count = int(response[3])
                    name = response[0]
                    level1 = response[1]
                    level2 = response[2]
                    list_received.append({"name": name, "level1": level1, "level2": level2})
                    logging.debug(f"Received packet {len(list_received)}/{count}")
                    if count == 1:
                        confirmationReceived = True
                        break
                    elif len(list_received) == count:
                        logging.debug(f"All packets received/{count}")
                        confirmationReceived = True
                        break
            #else:
            #    return False
            if time.time() >= startTime + 5:
                logging.debug('TIMEOUT: Waiting for packet from Server')
                return False
        if confirmationReceived:
            for student in list_received:
                name = student["name"]
                level1 = student["level1"]
                level2 = student["level2"]
                self.sheet.insert_row([name, level1, level2], redraw=True)
            self.lbl_name.config(text=f"{name} - {level1}")
            self.lbl_status.config(text=f"Queue Confirmed")
            return True

    def lora_sender(self, sending: bool, payload: str, cmd: bool = False, serverResponseTimeout: int = 5):
        comm_status = False
        try:
            startTime = time.time()
            cont = 0
            while sending:
                cont += 1
                logging.info(f"ready to send ({cont}): {self.rfm9x.node}|{payload}|1")
                if not self.rfm9x.send(bytes(f"{self.rfm9x.node}|{payload}|1", "UTF-8")):
                    logging.info(f"error sending on Lora")
                    self.lbl_status.config(text=f"Error sending to Server - {cont}", bg="red")
                else:
                    logging.info(f"Send executed")
                    self.lbl_status.config(text=f"Info sent to Server - {cont}", bg="green")
                    if self.lora_receiver(cmd):
                        self.lstCode.append(payload)
                        sending = False
                if time.time() >= startTime + serverResponseTimeout:
                    self.lbl_status.config(text=f"Ack not received - {cont}", bg="red")
                    return False
        except Exception as e:
            logging.info(f"Error sending to Server: {e}")

    def screenCleanup(self):
        answer = messagebox.askyesno("Confirm", "Erase all Data?")
        if answer == True:
            self.pileCommands("cleanup")
            if self.lora_sender(sending=True, payload='cleanup', cmd=True):
                self.lstCode = []
                self.sheet.delete_rows([x for x in range(0, self.sheet.get_total_rows())], deselect_all=True, redraw=True)
            else:
                self.unpileCommands()
                
    def breakQueue(self):
        self.pileCommands("break") 
        if self.lora_sender(sending=True, payload='break', cmd=True):
            self.sheet.insert_row(['RELEASE POINT', '', ''], redraw=True)
            self.sheet.highlight_rows(rows=[self.sheet.get_total_rows() - 1], bg='blue', fg='white', highlight_index=True,
                                 redraw=True)
            self.breakLineList.append(self.sheet.get_total_rows() - 1)
        else:
            self.unpileCommands()

    def releaseQueue(self):
        self.pileCommands("release")
        if len(self.breakLineList) > 0 and self.lora_sender(sending=True, payload='release', cmd=True):
            breakLineIndex = self.breakLineList[0]
            self.sheet.delete_rows([x for x in range(0, breakLineIndex)], deselect_all=True, redraw=True)
            self.breakLineList.pop(0)
            self.breakLineList = [x - breakLineIndex for x in self.breakLineList]
        else:
            self.unpileCommands()
            

    def undoLast(self):
        self.pileCommands("undo")
        self.lora_sender(sending=True, payload='cmd:undo')
        self.sheet.delete_row(self.sheet.get_total_rows() - 1, deselect_all=True, redraw=True)
        

    def quitScanner(self):
        try:
            self.thread.kill()
            self.destroy()
            quit()
        except Exception as e:
           logging.info("Shutdown error")
           logging.info(e)

    def process_serial(self):
        value = True
        while self.queue.qsize():
            try:
                qrCode = self.queue.get()
                logging.info(f'Read from Queue: {qrCode} value = {value}')
                self.lbl_status.config(text=f"{qrCode}")
                if value:
                    if qrCode in self.lstCode:
                        self.lbl_name.config(text=f"{qrCode}")
                        self.lbl_status.config(text=f"Duplicate QRCode")
                    else:
                        self.lbl_name.config(text=f"{qrCode}")
                        self.lbl_status.config(text=f"Sending to IQRight Server")
                        logging.info(f"QRCode {qrCode}")
                        sending = True
                        self.lora_sender(sending=sending, payload=qrCode)
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


