import tkinter as tk
from tkinter import messagebox

import pandas as pd
from tksheet import Sheet
from threading import Thread
import threading
import time
import queue
import logging
import logging.handlers
import os

# Import LORA Libraries - THIS WILL FAIL IN A NON RASPBERRY PI ENVIRONMENT
if os.environ.get("LOCAL") != 'TRUE':
    import board
    import busio
    import digitalio
    import adafruit_rfm9x
    import RPi.GPIO as GPIO
    import serial

    logging.info('Connected to Lora Module')
else:
    logging.info('Bypassing Lora Module')

# LOGGING Setup
log_filename = "IQRight_Scanner_Validation.debug"
max_log_size = 20 * 1024 * 1024  # 20Mb
backup_count = 10
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
debug = True
handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=max_log_size, backupCount=backup_count)

# else:
#    debug = False
#    logging.basicConfig(filename="IQRight_Daemon.log"), level=logging.INFO)

handler.setFormatter(log_formatter)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)

df = pd.read_csv("/Users/fulviomanente/Documents/Code/IQRight/Local/IQRight_Local/Validation_DB.csv")
# COnvert ExternalNUmber column to String
df['ExternalNumber'] = df['ExternalNumber'].astype(str)


# def serial_UART_Monitor():
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
        if os.environ.get("LOCAL") != 'TRUE':
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
                    self.ser.write(bytes.fromhex("7E000801000201ABCD"))
                    time.sleep(0.1)
                    blankReturn = self.ser.read()
                    logging.info(blankReturn)
                    time.sleep(1.3)
                    remaining = self.ser.inWaiting()
                    logging.info(remaining)
                    codeReaded = self.ser.read(remaining)
                    logging.info('codeReaded')
                    qrCode = str(codeReaded, encoding="UTF-8")
                    logging.info(qrCode)
                    logging.info(len(qrCode))
                    logging.info(qrCode[0:6])
                    logging.info(qrCode[6:])
                    self.queue.put(qrCode[6:].strip())
                    logging.info('Found on Loc')
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
        self.title("Validating")
        self.configure(bg='white')
        upperFrame = tk.Frame(height=100, bg="blue")
        # Add labels to the window
        lbl_title = tk.Label(master=upperFrame, text=f"IQRIght - Validation", font=("Arial", 18), fg="white",
                             bg="blue").pack()
        self.lbl_name = tk.Label(master=upperFrame, text=f"Ready to Scan", font=("Arial", 18), fg="white", bg="blue")
        self.lbl_status = tk.Label(master=upperFrame, text=f"Idle", font=("Arial", 14), fg="white", bg="blue")
        self.lbl_name.pack()
        self.lbl_status.pack()

        bottomFrame = tk.Frame(height=550, bg="white")
        self.sheet = Sheet(bottomFrame, headers=['Name', 'Grade', 'Teacher'], empty_vertical=0,
                           height=550, width=screenWidth, font=("Arial", 14, "normal"),
                           header_font=("Arial", 14, "normal"))
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

    def getGrade(self, strGrade: str):
        if strGrade == 'First Grade' or strGrade[0:2] == '01':
            return '1st'
        elif strGrade == 'Second Grade' or strGrade[0:2] == '02':
            return '2nd'
        elif strGrade == 'Third Grade' or strGrade[0:2] == '03':
            return '3rd'
        elif strGrade == 'Fourth Grade' or strGrade[0:2] == '04':
            return '4th'
        elif strGrade[1] == 'K':
            return 'Kind'
        else:
            return 'N/A'

    def get_user_local(self, code):
        global df
        if not code:  # Return early if code is missing
            logging.error(f'Empty string sent for querying')
            return None
        try:
            filtered_df = df[df['ExternalNumber'] == code]
            matches = filtered_df.drop_duplicates(subset=['ChildName'])
            if matches.empty:
                logging.debug(f"Couldn't find Code: {code} locally")
                return None  # Return None if not found locally
            else:
                results = []
                # Iterate through all matching rows
                for _, row in matches.iterrows():
                    result = {
                        "name": row['ChildName'],
                        "teacher": row['HierarchyLevel2'],
                        "class": self.getGrade(row['HierarchyLevel1']),
                        "externalID": code,
                    }
                    logging.info(f"{code}|{row['ChildName']}|{row['HierarchyLevel2']}|{row['HierarchyLevel1']}")
                    results.append(result)
                return results
        except Exception as e:
            logging.error(f'Error converting local data: {e}')
            return None

    def validation_received(self, sending: bool, payload: str, cmd: bool = False):
        if cmd:
            return True
        else:
            self.lbl_status.config(text='Record Confirmed ')
            results = self.get_user_local(payload)
            if results:
                logging.info(f'{payload}|Record Confirmed')
                for student in results:
                    self.lbl_name.config(text=f"{student['name']} - {student['teacher']}")
                    self.lbl_status.config(text=f"Confirmed")
                    self.sheet.insert_row([student['name'], student['class'], student['teacher']], redraw=True)
                return True
            else:
                logging.info(f'{payload}|NOT FOUND')
                return False

    def processUpdate(self, qrCode: str):
        logging.info(f"ProcessUpdate {qrCode}")
        if qrCode in self.lstCode:
            self.lbl_name.config(text=f"{qrCode}")
            self.lbl_status.config(text=f"Duplicate QRCode")
        else:
            self.lbl_name.config(text=f"{qrCode}")
            self.lbl_status.config(text=f"Validating Names")
            if len(qrCode) < 3:
                logging.info("Empty Message")
                sending = False
            else:
                logging.info(f"QRCode {qrCode}")
                sending = True
            if self.validation_received(sending=False, payload=qrCode):
                self.lstCode.append(qrCode)
                return True

    def screenCleanup(self):
        answer = messagebox.askyesno("Confirm", "Erase all Data?")
        if answer == True:
            self.pileCommands("cleanup")
            if self.validation_received(sending=True, payload='cmd:cleanup}', cmd=True):
                self.lstCode = []
                self.sheet.delete_rows([x for x in range(0, self.sheet.get_total_rows())], deselect_all=True,
                                       redraw=True)
            else:
                self.unpileCommands()

    def breakQueue(self):
        self.pileCommands("break")
        if self.validation_received(sending=True, payload='cmd:break', cmd=True):
            self.sheet.insert_row(['RELEASE POINT', '', ''], redraw=True)
            self.sheet.highlight_rows(rows=[self.sheet.get_total_rows() - 1], bg='blue', fg='white',
                                      highlight_index=True,
                                      redraw=True)
            self.breakLineList.append(self.sheet.get_total_rows() - 1)
        else:
            self.unpileCommands()

    def releaseQueue(self):
        self.processUpdate(qrCode='4710282')
        return True
        self.pileCommands("release")
        if len(self.breakLineList) > 0 and self.validation_received(sending=True, payload='cmd:release', cmd=True):
            breakLineIndex = self.breakLineList[0]
            self.sheet.delete_rows([x for x in range(0, breakLineIndex)], deselect_all=True, redraw=True)
            self.breakLineList.pop(0)
            self.breakLineList = [x - breakLineIndex for x in self.breakLineList]
        else:
            self.unpileCommands()

    def undoLast(self):
        self.pileCommands("undo")
        self.validation_received(sending=True, payload='cmd:undo')
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


# Run the main loop
app = App()
app.mainloop()


